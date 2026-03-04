"""Root Agent - central orchestrator that delegates to module agents."""

import sys
from pathlib import Path

from google.adk.agents import Agent
from google.adk.tools.mcp_tool.mcp_toolset import McpToolset, StdioServerParameters

from src.orchestrator.agent_registry import AgentRegistry


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
            connection_params=StdioServerParameters(
                command=sys.executable,
                args=[str(mcp_server_path), "--workspace", self.workspace_dir],
            ),
        )

        return Agent(
            model=agent_model,
            name=agent_info.name,
            description=agent_info.description,
            instruction=instruction,
            tools=[mcp_tools],
        )

    def create_root_agent(self) -> Agent:
        """Build root agent with sub-agents for each discovered module."""
        sub_agents = []
        agent_descriptions = []

        for agent_info in self.registry.list_agents():
            local_agent = self._create_coder_agent(agent_info)
            sub_agents.append(local_agent)

            agent_descriptions.append(
                f"- {agent_info.name}: {agent_info.description} "
                f"(capabilities: {', '.join(agent_info.capabilities)})"
            )

        instruction = self._build_instruction(agent_descriptions)

        return Agent(
            model=self.model,
            name="root_agent",
            description="Root orchestrator that coordinates task execution across specialized agent modules.",
            instruction=instruction,
            sub_agents=sub_agents,
        )

    def _build_instruction(self, agent_descriptions: list[str]) -> str:
        agents_list = "\n".join(agent_descriptions) if agent_descriptions else "No agents available yet."
        return f"""You are the root orchestrator agent. Your job is to:
1. Understand the user's request
2. Delegate code-related tasks to the coder_agent
3. Coordinate the work and synthesize results

Available agents:
{agents_list}

When the user asks you to generate, write, or modify code, ALWAYS delegate to coder_agent.
The coder_agent has file tools (generate_code_files, read_code_file, write_code_file) via MCP.
"""
