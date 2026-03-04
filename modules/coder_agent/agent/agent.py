"""ADK Agent definition for coder_agent."""

import os
import sys
from pathlib import Path

import yaml
from google.adk.agents import Agent
from mcp.client.stdio import StdioServerParameters
from google.adk.tools.mcp_tool import McpToolset, StdioConnectionParams, SseConnectionParams

MODULE_DIR = Path(__file__).parent.parent


def load_system_prompt() -> str:
    prompt_path = MODULE_DIR / "agent" / "prompts" / "system_prompt.md"
    return prompt_path.read_text(encoding="utf-8")


def _load_manifest() -> dict:
    return yaml.safe_load(
        (MODULE_DIR / "module.yaml").read_text(encoding="utf-8")
    )


_manifest = _load_manifest()


def _build_mcp_toolset() -> McpToolset:
    """Build MCP toolset from module.yaml config — supports both stdio and sse."""
    mcp_conf = _manifest.get("tools", {}).get("mcp", {})
    transport = mcp_conf.get("transport", "stdio")

    if transport == "sse":
        url = mcp_conf.get("url") or os.environ.get(
            "MCP_SSE_URL", "http://localhost:8010/sse"
        )
        return McpToolset(connection_params=SseConnectionParams(url=url))

    # Default: stdio — launch the MCP server as a child process
    server_script = str(MODULE_DIR / mcp_conf.get("server", "tools/mcp_server.py"))
    # workspace at project root (modules/../.. = project root)
    workspace = str(MODULE_DIR.parent.parent / "workspace")
    return McpToolset(
        connection_params=StdioConnectionParams(
            server_params=StdioServerParameters(
                command=sys.executable,
                args=[server_script, "--workspace", workspace],
            ),
        ),
    )


code_generator_mcp = _build_mcp_toolset()

# ADK Agent definition — model from module.yaml (agent.model)
_agent_model = _manifest.get("agent", {}).get("model", "gemini-2.5-flash")

root_agent = Agent(
    model=_agent_model,
    name="coder_agent",
    description=(
        "Code generation and modification. Can generate, review, and modify code "
        "based on specifications or error diagnostics."
    ),
    instruction=load_system_prompt(),
    tools=[code_generator_mcp],
)
