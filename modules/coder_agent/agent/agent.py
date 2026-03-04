"""ADK Agent definition for coder_agent."""

from pathlib import Path

from google.adk.agents import Agent
from google.adk.tools.mcp_tool import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import SseConnectionParams

MODULE_DIR = Path(__file__).parent.parent


def load_system_prompt() -> str:
    prompt_path = MODULE_DIR / "agent" / "prompts" / "system_prompt.md"
    return prompt_path.read_text(encoding="utf-8")


# The MCP toolset connects to the local code_generator MCP server via stdio
code_generator_mcp = McpToolset(
    connection_params=SseConnectionParams(
        url="http://localhost:8010/sse",
    ),
)

# ADK Agent definition
root_agent = Agent(
    model="gemini-2.0-flash",
    name="coder_agent",
    description=(
        "Code generation and modification. Can generate, review, and modify code "
        "based on specifications or error diagnostics."
    ),
    instruction=load_system_prompt(),
    tools=[code_generator_mcp],
)
