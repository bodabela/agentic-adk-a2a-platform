"""Pydantic models for declarative agent and root-agent YAML definitions."""

from __future__ import annotations

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Agent definition (agent.yaml)
# ---------------------------------------------------------------------------

class MCPToolConfig(BaseModel):
    """Single MCP server connection."""
    transport: str = "stdio"                    # "stdio" | "sse"
    server: str | None = None                   # relative path for stdio
    workspace: str | None = None                # template: "{{ workspace_dir }}"
    url: str | None = None                      # for sse transport


class ToolsConfig(BaseModel):
    """Tools block inside an agent definition."""
    mcp: list[MCPToolConfig] = Field(default_factory=list)
    builtin: list[str] = Field(default_factory=list)   # "exit_loop", "ask_user"


class GenerateContentConfig(BaseModel):
    """Subset of genai GenerateContentConfig exposed in YAML."""
    thinking: bool = False


class AgentDefinition(BaseModel):
    """Full agent definition parsed from agent.yaml."""
    name: str
    version: str = "0.1.0"
    description: str = ""
    category: str = "general"
    model: str = "gemini-2.5-flash"
    model_fallback: str | None = None
    instruction: str = ""                       # inline text OR relative .md path
    output_key: str | None = None               # defaults to "{name}_output"
    capabilities: list[str] = Field(default_factory=list)
    generate_content_config: GenerateContentConfig = Field(
        default_factory=GenerateContentConfig,
    )
    tools: ToolsConfig = Field(default_factory=ToolsConfig)
    # Peer transfer control
    disallow_transfer_to_peers: bool = False     # ADK default: peers CAN transfer
    disallow_transfer_to_parent: bool = False    # ADK default: CAN transfer to parent

    @property
    def effective_output_key(self) -> str:
        return self.output_key or f"{self.name}_output"


# ---------------------------------------------------------------------------
# Root-agent definition (*.root.yaml)
# ---------------------------------------------------------------------------

class OrchestrationConfig(BaseModel):
    """How the root agent orchestrates sub-agents."""
    strategy: str = "loop"                      # "loop" (LoopAgent)
    max_iterations: int = 10


class RootAgentDefinition(BaseModel):
    """Declarative root-agent / orchestrator definition."""
    name: str
    version: str = "1.0.0"
    description: str = ""
    model: str = "gemini-2.5-flash"
    orchestration: OrchestrationConfig = Field(
        default_factory=OrchestrationConfig,
    )
    sub_agents: list[str] = Field(default_factory=list)   # agent names
    instruction: str = ""                       # inline or file path
    generate_content_config: GenerateContentConfig = Field(
        default_factory=GenerateContentConfig,
    )
