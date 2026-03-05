"""Root Agent - central orchestrator that delegates to module agents."""

import asyncio
import json
import sys
import uuid
from pathlib import Path
from typing import Any

from google.adk.agents import Agent
from google.adk.agents.loop_agent import LoopAgent
from google.adk.tools.exit_loop_tool import exit_loop
from google.genai import types as genai_types
from mcp.client.stdio import StdioServerParameters
from google.adk.tools.mcp_tool import McpToolset, StdioConnectionParams

from src.common.logging import get_logger
from src.orchestrator.agent_registry import AgentRegistry

logger = get_logger("root_agent")

_THINKING_CONFIG = genai_types.GenerateContentConfig(
    thinking_config=genai_types.ThinkingConfig(include_thoughts=True),
)


class RootAgentFactory:
    """Creates and configures the root orchestrator agent."""

    def __init__(
        self,
        registry: AgentRegistry,
        model: str = "gemini-2.5-flash",
        modules_dir: str = "../modules",
        workspace_dir: str = "../workspace",
        event_bus: Any | None = None,
        task_id: str | None = None,
        pending_interactions: dict | None = None,
    ):
        self.registry = registry
        self.model = model
        self.modules_dir = Path(modules_dir).resolve()
        self.workspace_dir = str(Path(workspace_dir).resolve())
        self.event_bus = event_bus
        self.task_id = task_id
        self.pending_interactions = pending_interactions

    def _create_coder_agent(self, agent_info) -> Agent:
        """Build the coder agent as a local sub-agent connected to its MCP server."""
        agent_conf = agent_info.module_yaml.get("agent", {})
        agent_model = agent_conf.get("model", self.model)

        # Load system prompt from module
        system_prompt_path = (
            Path(agent_info.agent_card_path).parent / "prompts" / "system_prompt.md"
        )
        if system_prompt_path.exists():
            instruction = system_prompt_path.read_text(encoding="utf-8")
        else:
            instruction = "You are a code generation agent."

        # Resolve the module's MCP server path
        mcp_server_path = self.modules_dir / agent_info.name / "tools" / "mcp_server.py"

        mcp_tools = McpToolset(
            connection_params=StdioConnectionParams(
                server_params=StdioServerParameters(
                    command=sys.executable,
                    args=[str(mcp_server_path), "--workspace", self.workspace_dir],
                ),
            ),
        )

        return Agent(
            model=agent_model,
            name=agent_info.name,
            description=agent_info.description,
            instruction=instruction,
            tools=[mcp_tools],
            output_key=f"{agent_info.name}_output",
            generate_content_config=_THINKING_CONFIG,
        )

    def _create_user_agent(self, agent_info) -> Agent | None:
        """Create the user_agent with an ask_user tool that pauses for human input."""
        if not self.event_bus or not self.task_id or self.pending_interactions is None:
            logger.warning("user_agent_skipped", reason="missing interaction infrastructure")
            return None

        agent_conf = agent_info.module_yaml.get("agent", {})
        agent_model = agent_conf.get("model", self.model)

        # Load system prompt from module
        system_prompt_path = (
            Path(agent_info.agent_card_path).parent / "prompts" / "system_prompt.md"
        )
        if system_prompt_path.exists():
            instruction = system_prompt_path.read_text(encoding="utf-8")
        else:
            instruction = (
                "You are the user interaction agent. Use the ask_user tool "
                "to pose questions to the human. Return the user's response clearly."
            )

        event_bus = self.event_bus
        task_id = self.task_id
        pending = self.pending_interactions

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
                task_id=task_id,
                interaction_id=interaction_id,
                question_type=question_type,
            )

            await event_bus.emit("task_input_required", {
                "task_id": task_id,
                "interaction_id": interaction_id,
                "interaction_type": question_type,
                "prompt": question,
                "options": options_payload,
            })

            future: asyncio.Future = asyncio.get_event_loop().create_future()
            pending[interaction_id] = future

            try:
                response = await asyncio.wait_for(future, timeout=300)
            except asyncio.TimeoutError:
                logger.warning("ask_user_timeout", task_id=task_id, interaction_id=interaction_id)
                return "The user did not respond within the timeout period."
            finally:
                pending.pop(interaction_id, None)

            await event_bus.emit("task_user_response", {
                "task_id": task_id,
                "interaction_id": interaction_id,
                "response": str(response)[:1000],
            })

            logger.info("ask_user_response_received", task_id=task_id, interaction_id=interaction_id)
            return str(response) if isinstance(response, str) else json.dumps(response)

        return Agent(
            model=agent_model,
            name=agent_info.name,
            description=agent_info.description,
            instruction=instruction,
            tools=[ask_user],
            output_key=f"{agent_info.name}_output",
        )

    def create_root_agent(self) -> LoopAgent:
        """Build root agent as a LoopAgent wrapping an orchestrator with sub-agents.

        The LoopAgent runs the orchestrator repeatedly. Each iteration the
        orchestrator reviews session state (previous agent outputs) and decides
        the next action: transfer to a specialized agent, ask the user, or
        call exit_loop when the task is complete.
        """
        sub_agents = []

        for agent_info in self.registry.list_agents():
            agent_conf = agent_info.module_yaml.get("agent", {})
            agent_type = agent_conf.get("type", "tool_agent")

            if agent_type == "user_interaction":
                agent = self._create_user_agent(agent_info)
            else:
                agent = self._create_coder_agent(agent_info)

            if agent:
                sub_agents.append(agent)

        # Build dynamic instruction with available agents and state references
        agents_desc = "\n".join(
            f"- {a.name}: {a.description}" for a in sub_agents
        )
        output_keys_desc = "\n".join(
            f"- {a.name}_output" for a in sub_agents
        )

        instruction = (
            "You are the orchestrator agent that coordinates task execution.\n\n"
            f"Available agents you can transfer to:\n{agents_desc}\n\n"
            "After an agent completes, its response is saved to session state under these keys:\n"
            f"{output_keys_desc}\n"
            "Check these in the conversation history to see what agents have responded.\n\n"
            "WORKFLOW:\n"
            "1. Analyze the user's request and the current state.\n"
            "2. If no agent has responded yet, transfer to the appropriate specialized agent.\n"
            "3. If an agent responded with questions or needs clarification, "
            "transfer to user_agent to ask the human user.\n"
            "4. If user_agent returned the user's answer, transfer back to the "
            "specialized agent with the user's answer included in context.\n"
            "5. If the task is fully completed with a satisfactory result, "
            "present the final result and then call exit_loop to finish.\n"
            "6. Repeat until the task is done.\n\n"
            "IMPORTANT:\n"
            "- Each turn you can do ONE action: transfer to an agent OR call exit_loop.\n"
            "- Always review agent outputs before deciding the next step.\n"
            "- If the task is ambiguous from the start, transfer to user_agent first."
        )

        orchestrator = Agent(
            model=self.model,
            name="orchestrator",
            description="Orchestrates task execution by delegating to specialized agents.",
            instruction=instruction,
            sub_agents=sub_agents,
            tools=[exit_loop],
            generate_content_config=_THINKING_CONFIG,
        )

        return LoopAgent(
            name="root_agent",
            sub_agents=[orchestrator],
            max_iterations=10,
        )
