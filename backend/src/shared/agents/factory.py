"""Unified AgentFactory — creates ADK Agent instances from declarative YAML definitions."""

from __future__ import annotations

import asyncio
import json
import sys
import uuid
from pathlib import Path
from typing import Any

from google.adk.agents import Agent
from google.adk.tools.mcp_tool import McpToolset, StdioConnectionParams, SseConnectionParams, StreamableHTTPConnectionParams
from google.genai import types as genai_types
from mcp.client.stdio import StdioServerParameters

from src.shared.agents.loader import load_agent_definitions, resolve_instruction
from src.shared.agents.schema import AgentDefinition, MCPToolConfig
from src.shared.logging import get_logger

logger = get_logger("agents.factory")


def _extract_a2ui(text: str) -> list[dict] | None:
    """Extract A2UI JSON payload from text containing <a2ui>...</a2ui> tags.

    LLMs produce JSON with varying levels of escaping depending on how many
    serialization layers the text passes through. This function handles it
    by iteratively unescaping until valid JSON is found (up to 5 rounds).

    Returns the parsed JSON list if found and valid, otherwise None.
    """
    import re
    match = re.search(r"<a2ui>(.*?)</a2ui>", text, re.DOTALL)
    if not match:
        return None

    raw = match.group(1).strip()

    def _try_parse(s: str) -> list[dict] | None:
        s = s.strip()
        if not s:
            return None
        try:
            payload = json.loads(s)
            if isinstance(payload, list):
                return payload
        except (json.JSONDecodeError, TypeError):
            pass
        # Try extracting just the JSON array (LLM may add text around it)
        m = re.search(r"(\[.*\])", s, re.DOTALL)
        if m:
            try:
                payload = json.loads(m.group(1))
                if isinstance(payload, list):
                    return payload
            except (json.JSONDecodeError, TypeError):
                pass
        return None

    def _unescape_round(s: str) -> str:
        """One round of unescaping — handles one level of string escaping."""
        s = s.replace("\\\\", "\x00BACKSLASH\x00")  # protect real escaped backslashes
        s = s.replace("\\n", "\n")       # \n → newline
        s = s.replace("\\t", "\t")       # \t → tab
        s = s.replace('\\"', '"')        # \" → "
        s = s.replace("\\'", "'")        # \' → '
        s = re.sub(r"\\\n", "\n", s)     # trailing \ before newline (line continuation)
        s = s.replace("\x00BACKSLASH\x00", "\\")  # restore single backslashes
        s = re.sub(r",\s*([}\]])", r"\1", s)  # trailing commas
        return s

    # Try as-is first
    result = _try_parse(raw)
    if result:
        return result

    # Iteratively unescape up to 5 rounds (each round handles one escaping layer)
    candidate = raw
    for _ in range(5):
        candidate = _unescape_round(candidate)
        result = _try_parse(candidate)
        if result:
            return result

    logger.warning("a2ui_extract_failed", raw_length=len(raw), raw_preview=raw[:200])
    return None


class AgentFactory:
    """Creates ADK Agent instances from declarative YAML definitions.

    This is the single source of truth for agent creation — used by both
    the Tasks path (via RootAgentManager) and the Flows path (via FlowEngine).
    """

    def __init__(
        self,
        agents_dir: Path,
        workspace_dir: Path,
        event_bus: Any | None = None,
        llm_config: Any | None = None,
        tracing_enabled: bool = False,
        venv_manager: Any | None = None,
    ):
        self._agents_dir = agents_dir
        self._workspace_dir = workspace_dir
        self._event_bus = event_bus
        self._llm_config = llm_config
        self._tracing_enabled = tracing_enabled
        self._venv_manager = venv_manager
        self._agent_defs: dict[str, AgentDefinition] = {}

    # -- lifecycle ----------------------------------------------------------

    def load_definitions(self) -> None:
        """(Re)load all agent definitions from disk."""
        self._agent_defs = load_agent_definitions(self._agents_dir)
        logger.info("definitions_loaded", count=len(self._agent_defs))

    def reload(self) -> None:
        """Alias for load_definitions — call after CRUD operations."""
        self.load_definitions()

    @property
    def definitions(self) -> dict[str, AgentDefinition]:
        return dict(self._agent_defs)

    def has_agent(self, name: str) -> bool:
        return name in self._agent_defs

    # -- agent creation -----------------------------------------------------

    def create_agent(
        self,
        name: str,
        *,
        model_override: str | None = None,
        task_id: str | None = None,
        pending_interactions: dict | None = None,
        event_bus: Any | None = None,
        peer_agents: list[Agent] | None = None,
        context_type: str = "task",
        interaction_broker: Any | None = None,
        channel: str = "web_ui",
    ) -> Agent:
        """Create an ADK Agent from its YAML definition.

        Parameters
        ----------
        name:
            Agent definition name (must exist in loaded definitions).
        model_override:
            Override the model declared in the YAML.
        task_id:
            Required when the agent uses the ``ask_user`` builtin tool.
        pending_interactions:
            Legacy: Dict to store asyncio.Future objects for ask_user.
            Deprecated in favor of ``interaction_broker``.
        event_bus:
            EventBus for emitting interaction events (falls back to factory default).
        peer_agents:
            List of already-created peer Agent instances. When provided, the
            agent's instruction is enriched with peer descriptions so it knows
            who it can transfer_to directly.
        interaction_broker:
            InteractionBroker instance for persistent, channel-agnostic interactions.
            When provided, ask_user uses the broker instead of raw asyncio.Future.
        channel:
            Target channel for interactions (e.g. "web_ui", "teams", "whatsapp").
        """
        defn = self._agent_defs.get(name)
        if not defn:
            available = ", ".join(sorted(self._agent_defs.keys()))
            raise KeyError(f"Agent definition '{name}' not found. Available: {available}")

        model = model_override or defn.model
        instruction = resolve_instruction(defn, self._agents_dir)
        tools = self._build_tools(
            defn, task_id, pending_interactions, event_bus, context_type,
            interaction_broker=interaction_broker, channel=channel,
        )
        config = self._build_generate_config(defn)

        # Inject peer agent awareness into instruction
        if peer_agents:
            instruction = self._inject_peer_context(instruction, peer_agents)

        # Inject OTel tracing callbacks when enabled
        tracing_kwargs: dict = {}
        if self._tracing_enabled:
            from src.shared.tracing.callbacks import make_adk_callbacks
            tracing_kwargs = make_adk_callbacks()

        return Agent(
            model=model,
            name=defn.name,
            description=defn.description,
            instruction=instruction,
            tools=tools,
            output_key=defn.effective_output_key,
            generate_content_config=config,
            disallow_transfer_to_peers=defn.disallow_transfer_to_peers,
            disallow_transfer_to_parent=defn.disallow_transfer_to_parent,
            **tracing_kwargs,
        )

    # -- private helpers ----------------------------------------------------

    def _build_tools(
        self,
        defn: AgentDefinition,
        task_id: str | None,
        pending_interactions: dict | None,
        event_bus_override: Any | None,
        context_type: str = "task",
        interaction_broker: Any | None = None,
        channel: str = "web_ui",
    ) -> list:
        tools: list = []
        event_bus = event_bus_override or self._event_bus

        # MCP tools
        for mcp_conf in defn.tools.mcp:
            tool = self._build_mcp_tool(mcp_conf, defn.name)
            if tool:
                tools.append(tool)

        # Builtin tools
        for builtin_name in defn.tools.builtin:
            tool = self._resolve_builtin(
                builtin_name, task_id, pending_interactions, event_bus, context_type,
                interaction_broker=interaction_broker, channel=channel,
            )
            if tool:
                tools.append(tool)

        return tools

    def _build_mcp_tool(self, mcp_conf: MCPToolConfig, agent_name: str) -> McpToolset | None:
        """Build an McpToolset for any supported transport."""
        tool_filter = mcp_conf.tool_filter or None
        ws_dir = str(self._workspace_dir)

        # --- stdio transport ---
        if mcp_conf.transport == "stdio":
            return self._build_mcp_stdio(mcp_conf, agent_name, ws_dir, tool_filter)

        # --- sse transport ---
        if mcp_conf.transport == "sse":
            return self._build_mcp_sse(mcp_conf, agent_name, ws_dir, tool_filter)

        # --- streamable_http transport ---
        if mcp_conf.transport == "streamable_http":
            return self._build_mcp_streamable_http(mcp_conf, agent_name, ws_dir, tool_filter)

        logger.warning("mcp_unknown_transport", transport=mcp_conf.transport, agent=agent_name)
        return None

    def _build_mcp_stdio(
        self, mcp_conf: MCPToolConfig, agent_name: str, ws_dir: str, tool_filter: list[str] | None,
    ) -> McpToolset | None:
        """Build stdio McpToolset — either simple (server=) or advanced (command=)."""
        if mcp_conf.command:
            # Advanced mode: arbitrary command (npx, node, uvx, etc.)
            args = [self._resolve_templates(a, ws_dir) for a in mcp_conf.args]
            env = {k: self._resolve_templates(v, ws_dir) for k, v in mcp_conf.env.items()} or None
            logger.info("mcp_stdio_command", agent=agent_name, command=mcp_conf.command, args=args)
            return McpToolset(
                connection_params=StdioConnectionParams(
                    server_params=StdioServerParameters(
                        command=mcp_conf.command,
                        args=args,
                        env=env,
                    ),
                    timeout=30,
                ),
                tool_filter=tool_filter,
            )

        if not mcp_conf.server:
            logger.warning("mcp_missing_server_or_command", agent=agent_name)
            return None

        # Simple mode: Python MCP server relative to agent directory
        agent_dir = self._agents_dir / agent_name
        server_path = (agent_dir / mcp_conf.server).resolve()
        if not server_path.is_file():
            logger.warning("mcp_server_not_found", path=str(server_path), agent=agent_name)
            return None

        workspace = ws_dir
        if mcp_conf.workspace:
            workspace = self._resolve_templates(mcp_conf.workspace, ws_dir)

        # Use agent-specific venv Python when available (per-agent/project deps)
        python_exec = sys.executable
        if self._venv_manager:
            python_exec = self._venv_manager.get_python(agent_name)
            if python_exec != sys.executable:
                logger.info("mcp_using_venv", agent=agent_name, python=python_exec)

        return McpToolset(
            connection_params=StdioConnectionParams(
                server_params=StdioServerParameters(
                    command=python_exec,
                    args=[str(server_path), "--workspace", workspace],
                ),
                timeout=30,
            ),
            tool_filter=tool_filter,
        )

    def _build_mcp_sse(
        self, mcp_conf: MCPToolConfig, agent_name: str, ws_dir: str, tool_filter: list[str] | None,
    ) -> McpToolset | None:
        """Build SSE McpToolset."""
        if not mcp_conf.url:
            logger.warning("mcp_sse_missing_url", agent=agent_name)
            return None

        url = self._resolve_templates(mcp_conf.url, ws_dir)
        headers = {k: self._resolve_templates(v, ws_dir) for k, v in mcp_conf.headers.items()} or None
        logger.info("mcp_sse_connect", agent=agent_name, url=url)
        return McpToolset(
            connection_params=SseConnectionParams(
                url=url,
                headers=headers,
                timeout=mcp_conf.timeout,
                sse_read_timeout=mcp_conf.sse_read_timeout,
            ),
            tool_filter=tool_filter,
        )

    def _build_mcp_streamable_http(
        self, mcp_conf: MCPToolConfig, agent_name: str, ws_dir: str, tool_filter: list[str] | None,
    ) -> McpToolset | None:
        """Build Streamable HTTP McpToolset."""
        if not mcp_conf.url:
            logger.warning("mcp_streamable_http_missing_url", agent=agent_name)
            return None

        url = self._resolve_templates(mcp_conf.url, ws_dir)
        headers = {k: self._resolve_templates(v, ws_dir) for k, v in mcp_conf.headers.items()} or None
        logger.info("mcp_streamable_http_connect", agent=agent_name, url=url)
        return McpToolset(
            connection_params=StreamableHTTPConnectionParams(
                url=url,
                headers=headers,
                timeout=mcp_conf.timeout,
                sse_read_timeout=mcp_conf.sse_read_timeout,
            ),
            tool_filter=tool_filter,
        )

    @staticmethod
    def _resolve_templates(value: str, workspace_dir: str) -> str:
        """Replace template variables in a string value."""
        import os
        result = value.replace("{{ workspace_dir }}", workspace_dir)
        # Support {{ env.VAR_NAME }} for environment variable interpolation
        import re
        for match in re.finditer(r"\{\{\s*env\.(\w+)\s*\}\}", result):
            env_val = os.environ.get(match.group(1), "")
            result = result.replace(match.group(0), env_val)
        return result

    def _resolve_builtin(
        self,
        name: str,
        task_id: str | None,
        pending_interactions: dict | None,
        event_bus: Any | None,
        context_type: str = "task",
        interaction_broker: Any | None = None,
        channel: str = "web_ui",
    ):
        if name == "exit_loop":
            from google.adk.tools.exit_loop_tool import exit_loop
            return exit_loop

        if name == "ask_user":
            # Prefer broker-based ask_user if broker is available
            if interaction_broker:
                return self._create_ask_user_tool_broker(
                    task_id, interaction_broker, context_type, channel,
                )
            return self._create_ask_user_tool(task_id, pending_interactions, event_bus, context_type)

        if name == "send_notification":
            return self._create_send_notification_tool(task_id, interaction_broker, channel)

        if name == "list_channels":
            return self._create_list_channels_tool(interaction_broker)

        logger.warning("unknown_builtin_tool", name=name)
        return None

    def _create_ask_user_tool(
        self,
        task_id: str | None,
        pending_interactions: dict | None,
        event_bus: Any | None,
        context_type: str = "task",
    ):
        """Create the ask_user async function tool for human interaction."""
        if not event_bus or not task_id or pending_interactions is None:
            logger.warning("ask_user_skipped", reason="missing interaction infrastructure")
            return None

        _event_bus = event_bus
        _task_id = task_id
        _pending = pending_interactions
        # Use context-appropriate event names so frontend routes correctly
        _input_event = "task_input_required" if context_type == "task" else "flow_input_required"
        _response_event = "task_user_response" if context_type == "task" else "flow_user_response"
        _id_field = "task_id" if context_type == "task" else "flow_id"

        async def ask_user(
            question: str,
            question_type: str = "free_text",
            options: list[str] | None = None,
        ) -> str:
            """Ask the human user a question and wait for their response.

            Use this tool to get clarification, preferences, or decisions from the user.

            Args:
                question: The question to ask the user.
                question_type: One of "free_text", "choice", or "confirmation".
                options: For "choice" type, the list of options to present.

            Returns:
                The user's response as a string.
            """
            interaction_id = str(uuid.uuid4())

            options_payload = None
            if question_type == "choice" and options:
                options_payload = [{"id": opt, "label": opt} for opt in options]

            logger.info(
                "ask_user_emitting",
                task_id=_task_id,
                interaction_id=interaction_id,
                question_type=question_type,
            )

            await _event_bus.emit(_input_event, {
                _id_field: _task_id,
                "interaction_id": interaction_id,
                "interaction_type": question_type,
                "prompt": question,
                "options": options_payload,
            })

            future: asyncio.Future = asyncio.get_event_loop().create_future()
            _pending[interaction_id] = future

            try:
                response = await asyncio.wait_for(future, timeout=300)
            except asyncio.TimeoutError:
                logger.warning("ask_user_timeout", task_id=_task_id, interaction_id=interaction_id)
                return "The user did not respond within the timeout period."
            finally:
                _pending.pop(interaction_id, None)

            await _event_bus.emit(_response_event, {
                _id_field: _task_id,
                "interaction_id": interaction_id,
                "response": str(response)[:1000],
            })

            logger.info("ask_user_response_received", task_id=_task_id, interaction_id=interaction_id)
            return str(response) if isinstance(response, str) else json.dumps(response)

        return ask_user

    def _create_ask_user_tool_broker(
        self,
        task_id: str | None,
        broker: Any,
        context_type: str = "task",
        channel: str = "web_ui",
    ):
        """Create ask_user using InteractionBroker for persistent, multi-channel interactions."""
        if not task_id:
            logger.warning("ask_user_broker_skipped", reason="missing task_id")
            return None

        _broker = broker
        _context_id = task_id
        _context_type = context_type
        _channel = channel

        async def ask_user(
            question: str,
            question_type: str = "free_text",
            options: list[str] | None = None,
        ) -> str:
            """Ask the human user a question and wait for their response.

            Use this tool to get clarification, preferences, or decisions from the user.
            The question is delivered through the configured communication channel
            (browser, Teams, WhatsApp, etc.).

            The question may contain A2UI rich UI markup wrapped in <a2ui>...</a2ui> tags.
            When present, the frontend renders an interactive graphical UI instead of plain text.

            Args:
                question: The question to ask the user. May contain <a2ui> tagged JSON for rich UI.
                question_type: One of "free_text", "choice", or "confirmation".
                options: For "choice" type, the list of options to present.

            Returns:
                The user's response as a string.
            """
            options_payload = None
            if question_type == "choice" and options:
                options_payload = [{"id": opt, "label": opt} for opt in options]

            # Extract A2UI payload from question if present
            a2ui_payload = None
            clean_prompt = question
            a2ui_json = _extract_a2ui(question)
            if a2ui_json is not None:
                a2ui_payload = a2ui_json
                # Strip the <a2ui>...</a2ui> block from the prompt, keep fallback text
                import re
                clean_prompt = re.sub(r"<a2ui>.*?</a2ui>", "", question, flags=re.DOTALL).strip()
                if not clean_prompt:
                    clean_prompt = "Please interact with the form above."
                question_type = "a2ui"

            interaction_id = await _broker.create_interaction(
                context_id=_context_id,
                context_type=_context_type,
                interaction_type=question_type,
                prompt=clean_prompt,
                options=options_payload,
                a2ui_payload=a2ui_payload,
                channel=_channel,
                metadata={"agent": "ask_user"},
            )

            logger.info(
                "ask_user_broker_waiting",
                context_id=_context_id,
                interaction_id=interaction_id,
                channel=_channel,
                has_a2ui=a2ui_payload is not None,
            )

            # Wait with suspension support for external channels
            suspend_on_timeout = _channel != "web_ui"
            response = await _broker.wait_for_response(
                interaction_id,
                timeout=300,
                suspend_on_timeout=suspend_on_timeout,
                context_id=_context_id,
            )

            logger.info("ask_user_broker_response", context_id=_context_id, interaction_id=interaction_id)
            return response

        return ask_user

    def _create_send_notification_tool(
        self,
        task_id: str | None,
        broker: Any | None,
        channel: str = "web_ui",
    ):
        """Create a tool that lets the agent send one-way notifications to channels."""
        if not broker:
            logger.warning("send_notification_skipped", reason="no interaction_broker")
            return None

        _broker = broker
        _default_channel = channel
        _context_id = task_id or ""

        async def send_notification(
            message: str,
            channel: str = "",
            metadata: str = "{}",
        ) -> str:
            """Send a one-way notification message to a communication channel.

            Use this tool to proactively inform the user about progress, results,
            or important updates without expecting a response.

            Args:
                message: The notification text to send.
                channel: Target channel ("web_ui", "whatsapp", "teams"). Defaults to the task's channel.
                metadata: Optional JSON string with extra data (e.g. {"phone": "+36..."}).

            Returns:
                Confirmation of delivery.
            """
            target = channel or _default_channel
            try:
                meta = json.loads(metadata) if metadata and metadata != "{}" else {}
            except (json.JSONDecodeError, TypeError):
                meta = {}

            success = await _broker.notify_channel(
                channel=target,
                message=message,
                context_id=_context_id,
                metadata=meta,
            )

            if success:
                logger.info("send_notification_ok", channel=target, context_id=_context_id)
                return f"Notification sent to {target}."
            else:
                logger.warning("send_notification_failed", channel=target)
                return f"Channel '{target}' is not available. Available: {', '.join(_broker.available_channels)}"

        return send_notification

    @staticmethod
    def _create_list_channels_tool(broker: Any | None):
        """Create a tool that lists available communication channels."""
        if not broker:
            logger.warning("list_channels_skipped", reason="no interaction_broker")
            return None

        _broker = broker

        async def list_channels() -> str:
            """List all available communication channels.

            Returns a JSON array of channel names (e.g. ["web_ui", "whatsapp", "teams"]).
            Use this to discover which channels are available before sending notifications.

            Returns:
                JSON array of channel name strings.
            """
            return json.dumps(_broker.available_channels)

        return list_channels

    @staticmethod
    def _inject_peer_context(instruction: str, peer_agents: list[Agent]) -> str:
        """Append peer agent descriptions to the instruction so the agent
        knows who it can communicate with via transfer_to_<name>."""
        if not peer_agents:
            return instruction
        lines = [
            "\n\n## Peer Agents",
            "You can directly communicate with the following peer agents "
            "using `transfer_to_<agent_name>` tools:",
        ]
        for peer in peer_agents:
            desc = peer.description or "no description"
            lines.append(f"- **{peer.name}**: {desc}")
        lines.append(
            "\nWhen you need another agent's help, you can transfer directly "
            "to them without going through the orchestrator."
        )
        return instruction + "\n".join(lines)

    @staticmethod
    def _build_generate_config(defn: AgentDefinition) -> genai_types.GenerateContentConfig | None:
        if defn.generate_content_config.thinking:
            return genai_types.GenerateContentConfig(
                thinking_config=genai_types.ThinkingConfig(include_thoughts=True),
            )
        return None
