"""Tools discovery API — lists all MCP and builtin tools with full schemas."""

import ast
import re
from pathlib import Path

from fastapi import APIRouter, Request

router = APIRouter()

# ---------------------------------------------------------------------------
# AST-based MCP tool extraction
# ---------------------------------------------------------------------------

def _extract_mcp_tools_ast(server_path: Path) -> list[dict]:
    """Parse an MCP server .py file via AST and extract @mcp.tool() decorated
    functions with their name, docstring and parameters."""
    if not server_path.is_file():
        return []
    try:
        source = server_path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(server_path))
    except Exception:
        return []

    tools: list[dict] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        # Check for @mcp.tool() decorator
        is_mcp_tool = False
        for dec in node.decorator_list:
            if isinstance(dec, ast.Call) and isinstance(dec.func, ast.Attribute):
                if dec.func.attr == "tool":
                    is_mcp_tool = True
            elif isinstance(dec, ast.Attribute) and dec.attr == "tool":
                is_mcp_tool = True
        if not is_mcp_tool:
            continue

        # Extract docstring
        docstring = ast.get_docstring(node) or ""

        # Extract parameters (skip 'self')
        params: list[dict] = []
        for arg in node.args.args:
            if arg.arg == "self":
                continue
            annotation = ""
            if arg.annotation:
                annotation = ast.unparse(arg.annotation)
            params.append({
                "name": arg.arg,
                "type": annotation or "str",
                "required": True,
            })

        # Mark params with defaults as optional
        num_defaults = len(node.args.defaults)
        if num_defaults:
            for i, default in enumerate(node.args.defaults):
                idx = len(params) - num_defaults + i
                if 0 <= idx < len(params):
                    params[idx]["required"] = False
                    try:
                        params[idx]["default"] = ast.literal_eval(default)
                    except (ValueError, TypeError):
                        params[idx]["default"] = ast.unparse(default)

        # Parse docstring for per-param descriptions
        param_descs = _parse_param_descriptions(docstring)
        for p in params:
            if p["name"] in param_descs:
                p["description"] = param_descs[p["name"]]

        # Split docstring: first paragraph = summary, rest = full
        summary = docstring.split("\n\n")[0].replace("\n", " ").strip() if docstring else ""

        tools.append({
            "name": node.name,
            "description": summary,
            "docstring": docstring,
            "parameters": params,
        })

    return tools


_PARAM_RE = re.compile(r"^\s{4,}(\w+):\s*(.+)", re.MULTILINE)


def _parse_param_descriptions(docstring: str) -> dict[str, str]:
    """Extract parameter descriptions from Google-style docstrings."""
    result: dict[str, str] = {}
    in_args = False
    for line in docstring.splitlines():
        stripped = line.strip()
        if stripped.startswith("Args:"):
            in_args = True
            continue
        if stripped.startswith("Returns:") or stripped.startswith("Raises:"):
            in_args = False
            continue
        if in_args:
            m = _PARAM_RE.match(line)
            if m:
                result[m.group(1)] = m.group(2).strip()
    return result


# ---------------------------------------------------------------------------
# Builtin tool definitions (static metadata — the actual implementations
# are closures created at runtime by AgentFactory)
# ---------------------------------------------------------------------------

BUILTIN_TOOLS: dict[str, dict] = {
    "exit_loop": {
        "name": "exit_loop",
        "description": "Signal the orchestrator to stop the agent loop and return the final result.",
        "category": "builtin",
        "parameters": [],
    },
    "ask_user": {
        "name": "ask_user",
        "description": "Ask the human user a question and wait for their response. Delivered through the configured communication channel.",
        "category": "builtin",
        "parameters": [
            {"name": "question", "type": "str", "required": True,
             "description": "The question to ask the user."},
            {"name": "question_type", "type": "str", "required": False,
             "default": "free_text",
             "description": 'One of "free_text", "choice", or "confirmation".'},
            {"name": "options", "type": "list[str] | None", "required": False,
             "default": None,
             "description": 'For "choice" type, the list of options to present.'},
        ],
    },
    "send_notification": {
        "name": "send_notification",
        "description": "Send a one-way notification to a communication channel without expecting a response.",
        "category": "builtin",
        "parameters": [
            {"name": "message", "type": "str", "required": True,
             "description": "The notification text to send."},
            {"name": "channel", "type": "str", "required": False,
             "default": "",
             "description": 'Target channel ("web_ui", "whatsapp", "teams"). Defaults to the task\'s channel.'},
            {"name": "metadata", "type": "str", "required": False,
             "default": "{}",
             "description": "Optional JSON string with extra data."},
        ],
    },
    "list_channels": {
        "name": "list_channels",
        "description": "List all available communication channels. Returns a JSON array of channel names.",
        "category": "builtin",
        "parameters": [],
    },
}


# ---------------------------------------------------------------------------
# API endpoint
# ---------------------------------------------------------------------------

def _mcp_server_key(mcp_conf, agents_dir: Path, agent_name: str) -> str:
    """Return a unique key for deduplication of MCP server configs."""
    if mcp_conf.url:
        return mcp_conf.url
    if mcp_conf.command:
        return f"cmd:{mcp_conf.command}:{' '.join(mcp_conf.args)}"
    if mcp_conf.server:
        agent_dir = agents_dir / agent_name
        return str((agent_dir / mcp_conf.server).resolve())
    return ""


def _mcp_server_label(mcp_conf, agents_dir: Path, agent_name: str) -> str:
    """Human-readable label for an MCP server."""
    if mcp_conf.url:
        return f"{mcp_conf.transport}:{mcp_conf.url}"
    if mcp_conf.command:
        return f"{mcp_conf.command} {' '.join(mcp_conf.args[:2])}"
    if mcp_conf.server:
        agent_dir = agents_dir / agent_name
        return (agent_dir / mcp_conf.server).resolve().name
    return "unknown"


@router.get(
    "/",
    tags=["Admin: Tools"],
    summary="List all available tools",
    description="Discovers and returns all tools available to agents on the platform, including:\n\n"
    "- **MCP tools** — extracted via AST parsing from local MCP server source files, or listed as "
    "remote endpoints for SSE/command-based servers\n"
    "- **Built-in tools** — platform-provided tools like `ask_user`, `send_notification`, `exit_loop`\n\n"
    "Each tool includes its name, description, parameter schema, and which agents use it.",
    response_description="Categorized tool list with parameter schemas and a summary count.",
)
async def list_tools(request: Request):
    factory = request.app.state.agent_factory
    agents_dir = Path(request.app.state.settings.agents_dir).resolve()

    # Collect MCP tools per server (deduplicate across agents)
    mcp_tools: list[dict] = []
    seen_servers: set[str] = set()

    for name, defn in factory.definitions.items():
        for mcp_conf in defn.tools.mcp:
            key = _mcp_server_key(mcp_conf, agents_dir, name)
            if not key or key in seen_servers:
                continue
            seen_servers.add(key)

            label = _mcp_server_label(mcp_conf, agents_dir, name)
            transport = mcp_conf.transport

            if mcp_conf.server and transport == "stdio":
                # Local Python MCP server — extract tools via AST
                agent_dir = agents_dir / defn.name
                server_path = (agent_dir / mcp_conf.server).resolve()
                tools = _extract_mcp_tools_ast(server_path)
                for t in tools:
                    t["category"] = "mcp"
                    t["transport"] = transport
                    t["server"] = label
                    t["used_by"] = []
                mcp_tools.extend(tools)
            else:
                # Remote or command-based MCP — can't parse source, show as single entry
                mcp_tools.append({
                    "name": f"[{transport}] {label}",
                    "description": f"External MCP server ({transport}). Tools are discovered at runtime via MCP protocol.",
                    "category": "mcp",
                    "transport": transport,
                    "server": label,
                    "url": mcp_conf.url or None,
                    "command": mcp_conf.command or None,
                    "parameters": [],
                    "used_by": [],
                })

    # Tag which agents use each MCP tool
    for name, defn in factory.definitions.items():
        for mcp_conf in defn.tools.mcp:
            key = _mcp_server_key(mcp_conf, agents_dir, name)
            if not key:
                continue
            # For stdio with source, match by extracted tool names
            if mcp_conf.server and mcp_conf.transport == "stdio":
                agent_dir = agents_dir / defn.name
                server_path = (agent_dir / mcp_conf.server).resolve()
                server_tool_names = {t["name"] for t in _extract_mcp_tools_ast(server_path)}
                for mt in mcp_tools:
                    if mt["name"] in server_tool_names and name not in mt["used_by"]:
                        mt["used_by"].append(name)
            else:
                # For remote/command MCP, match by server key
                label = _mcp_server_label(mcp_conf, agents_dir, name)
                for mt in mcp_tools:
                    if mt.get("server") == label and name not in mt["used_by"]:
                        mt["used_by"].append(name)

    # Collect builtin tools and tag which agents use them
    builtin_tools: list[dict] = []
    builtin_usage: dict[str, list[str]] = {}  # tool_name -> [agent_names]

    for name, defn in factory.definitions.items():
        for tool_name in defn.tools.builtin:
            if tool_name not in builtin_usage:
                builtin_usage[tool_name] = []
            builtin_usage[tool_name].append(name)

    for tool_name, agent_names in builtin_usage.items():
        tool_info = BUILTIN_TOOLS.get(tool_name, {
            "name": tool_name,
            "description": f"Builtin tool: {tool_name}",
            "category": "builtin",
            "parameters": [],
        })
        builtin_tools.append({**tool_info, "used_by": agent_names})

    return {
        "tools": mcp_tools + builtin_tools,
        "summary": {
            "mcp_count": len(mcp_tools),
            "builtin_count": len(builtin_tools),
            "total": len(mcp_tools) + len(builtin_tools),
        },
    }
