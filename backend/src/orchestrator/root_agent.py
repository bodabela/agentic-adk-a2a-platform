"""Root Agent - central orchestrator that delegates to module agents."""

import sys
from pathlib import Path

from google.adk.agents import Agent
from google.genai import types as genai_types
from mcp.client.stdio import StdioServerParameters
from google.adk.tools.mcp_tool import McpToolset, StdioConnectionParams

from src.orchestrator.agent_registry import AgentRegistry

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
    ):
        self.registry = registry
        self.model = model
        self.modules_dir = Path(modules_dir).resolve()
        self.workspace_dir = str(Path(workspace_dir).resolve())

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
            generate_content_config=_THINKING_CONFIG,
        )

    def create_root_agent(self) -> Agent:
        """Build root agent with sub-agents for each discovered module."""
        sub_agents = []

        for agent_info in self.registry.list_agents():
            local_agent = self._create_coder_agent(agent_info)
            sub_agents.append(local_agent)

        return Agent(
            model=self.model,
            name="root_agent",
            description="Root orchestrator that coordinates task execution across specialized agent modules.",
            instruction=(
                "You are the root orchestrator agent. "
                "Understand the user's request and delegate to the appropriate sub-agent. "
                "Synthesize and present results back to the user."
            ),
            sub_agents=sub_agents,
            generate_content_config=_THINKING_CONFIG,
        )
