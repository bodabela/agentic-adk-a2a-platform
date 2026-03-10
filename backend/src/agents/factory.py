"""Unified AgentFactory — creates ADK Agent instances from declarative YAML definitions."""

from __future__ import annotations

import asyncio
import json
import sys
import uuid
from pathlib import Path
from typing import Any

from google.adk.agents import Agent
from google.adk.tools.mcp_tool import McpToolset, StdioConnectionParams
from google.genai import types as genai_types
from mcp.client.stdio import StdioServerParameters

from src.agents.loader import load_agent_definitions, resolve_instruction
from src.agents.schema import AgentDefinition, MCPToolConfig
from src.common.logging import get_logger

logger = get_logger("agents.factory")


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
    ):
        self._agents_dir = agents_dir
        self._workspace_dir = workspace_dir
        self._event_bus = event_bus
        self._llm_config = llm_config
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
            Dict to store asyncio.Future objects for ask_user.
        event_bus:
            EventBus for emitting interaction events (falls back to factory default).
        peer_agents:
            List of already-created peer Agent instances. When provided, the
            agent's instruction is enriched with peer descriptions so it knows
            who it can transfer_to directly.
        """
        defn = self._agent_defs.get(name)
        if not defn:
            available = ", ".join(sorted(self._agent_defs.keys()))
            raise KeyError(f"Agent definition '{name}' not found. Available: {available}")

        model = model_override or defn.model
        instruction = resolve_instruction(defn, self._agents_dir)
        tools = self._build_tools(defn, task_id, pending_interactions, event_bus, context_type)
        config = self._build_generate_config(defn)

        # Inject peer agent awareness into instruction
        if peer_agents:
            instruction = self._inject_peer_context(instruction, peer_agents)

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
        )

    # -- private helpers ----------------------------------------------------

    def _build_tools(
        self,
        defn: AgentDefinition,
        task_id: str | None,
        pending_interactions: dict | None,
        event_bus_override: Any | None,
        context_type: str = "task",
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
            )
            if tool:
                tools.append(tool)

        return tools

    def _build_mcp_tool(self, mcp_conf: MCPToolConfig, agent_name: str) -> McpToolset | None:
        if mcp_conf.transport == "stdio":
            if not mcp_conf.server:
                logger.warning("mcp_missing_server", agent=agent_name)
                return None
            # Resolve server path relative to the agent's own directory
            agent_dir = self._agents_dir / agent_name
            server_path = (agent_dir / mcp_conf.server).resolve()
            if not server_path.is_file():
                logger.warning("mcp_server_not_found", path=str(server_path), agent=agent_name)
                return None

            # Resolve workspace template
            workspace = str(self._workspace_dir)
            if mcp_conf.workspace:
                workspace = mcp_conf.workspace.replace("{{ workspace_dir }}", str(self._workspace_dir))

            return McpToolset(
                connection_params=StdioConnectionParams(
                    server_params=StdioServerParameters(
                        command=sys.executable,
                        args=[str(server_path), "--workspace", workspace],
                    ),
                ),
            )

        if mcp_conf.transport == "sse":
            logger.info("mcp_sse_not_supported_yet", agent=agent_name)
            return None

        return None

    def _resolve_builtin(
        self,
        name: str,
        task_id: str | None,
        pending_interactions: dict | None,
        event_bus: Any | None,
        context_type: str = "task",
    ):
        if name == "exit_loop":
            from google.adk.tools.exit_loop_tool import exit_loop
            return exit_loop

        if name == "ask_user":
            return self._create_ask_user_tool(task_id, pending_interactions, event_bus, context_type)

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
