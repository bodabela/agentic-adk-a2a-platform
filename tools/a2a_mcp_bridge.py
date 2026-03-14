"""A2A → MCP Bridge — exposes platform agents as MCP tools for Claude Code.

On startup, fetches the A2A catalog from the platform and registers each
exposed agent/root-agent/flow as an MCP tool. When Claude Code calls a tool,
the bridge sends an A2A JSON-RPC `message/send` request and returns the result.

Usage:
    python tools/a2a_mcp_bridge.py [--base-url http://localhost:8000]

Configure in Claude Code (.mcp.json at project root):
    {
      "mcpServers": {
        "agent-platform": {
          "command": "python",
          "args": ["tools/a2a_mcp_bridge.py"],
          "env": { "A2A_BASE_URL": "http://localhost:8000" }
        }
      }
    }
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import uuid
from typing import Any

import httpx
from mcp.server.fastmcp import FastMCP

logging.basicConfig(level=logging.INFO, stream=sys.stderr)
logger = logging.getLogger("a2a_mcp_bridge")

mcp = FastMCP("agent-platform")

# Resolved at startup
_BASE_URL = ""
_ENDPOINTS: list[dict] = []


# ── A2A JSON-RPC helpers ─────────────────────────────────


def _jsonrpc_request(method: str, params: dict) -> dict:
    return {
        "jsonrpc": "2.0",
        "id": str(uuid.uuid4()),
        "method": method,
        "params": params,
    }


def _build_send_message(task_description: str, task_id: str | None = None) -> dict:
    """Build a message/send JSON-RPC request, optionally continuing a task."""
    message: dict[str, Any] = {
        "role": "user",
        "parts": [{"kind": "text", "text": task_description}],
        "messageId": str(uuid.uuid4()),
    }
    if task_id:
        message["taskId"] = task_id
    return _jsonrpc_request("message/send", {"message": message})


def _extract_question(task_result: dict) -> str:
    """Extract the ask_user question from an input-required task response.

    The question can appear in:
    1. DataPart with function call args (ask_user arguments)
    2. Text parts in the history/artifacts
    3. Status message
    """
    # Check history messages for the ask_user function call
    history = task_result.get("history", [])
    for msg in reversed(history):
        for part in msg.get("parts", []):
            # DataPart with function call containing ask_user args
            if part.get("kind") == "data" and isinstance(part.get("data"), dict):
                data = part["data"]
                if "ask_user" in data.get("name", ""):
                    args = data.get("args", {})
                    q = args.get("question", "")
                    opts = args.get("options")
                    qtype = args.get("question_type", "free_text")
                    if q:
                        result_parts = [q]
                        if qtype == "choice" and opts:
                            result_parts.append("Options: " + ", ".join(str(o) for o in opts))
                        return "\n".join(result_parts)

    # Check artifacts
    for artifact in task_result.get("artifacts", []):
        for part in artifact.get("parts", []):
            if part.get("kind") == "text" and part.get("text"):
                return part["text"]

    # Check status message
    status = task_result.get("status", {})
    status_msg = status.get("message", {})
    if isinstance(status_msg, dict):
        for part in status_msg.get("parts", []):
            if part.get("kind") == "text" and part.get("text"):
                return part["text"]
    elif isinstance(status_msg, str) and status_msg:
        return status_msg

    return "The agent needs more information from you."


def _extract_text(result: dict) -> str | None:
    """Extract text content from a completed A2A task result."""
    texts: list[str] = []

    # Standard A2A task result — artifacts
    for artifact in result.get("artifacts", []):
        for part in artifact.get("parts", []):
            if part.get("kind") == "text":
                texts.append(part["text"])
            elif "text" in part:
                texts.append(part["text"])
    if texts:
        return "\n\n".join(texts)

    # Try status message
    status = result.get("status", {})
    status_msg = status.get("message", {})
    if isinstance(status_msg, dict):
        for part in status_msg.get("parts", []):
            if part.get("kind") == "text":
                texts.append(part["text"])
    elif isinstance(status_msg, str):
        texts.append(status_msg)
    if texts:
        return "\n\n".join(texts)

    return None


async def _call_a2a(rpc_url: str, task_description: str, task_id: str | None = None) -> str:
    """Send a task to an A2A agent and return the text result.

    If ``task_id`` is provided, the message is sent as a follow-up to an
    existing task (multi-turn continuation).
    """
    url = f"{_BASE_URL}{rpc_url}" if rpc_url.startswith("/") else rpc_url
    payload = _build_send_message(task_description, task_id=task_id)

    async with httpx.AsyncClient(timeout=300) as client:
        resp = await client.post(
            url,
            json=payload,
            headers={"Content-Type": "application/json"},
        )
        resp.raise_for_status()
        body = resp.json()

    result = body.get("result", {})
    if isinstance(result, dict):
        state = result.get("status", {}).get("state", "")

        # ── Multi-turn: detect input-required ────────────────
        if state == "input-required":
            question = _extract_question(result)
            return json.dumps({
                "status": "input-required",
                "task_id": result.get("id", ""),
                "question": question,
                "instructions": (
                    "The agent needs your input. Ask the human user the question above, "
                    "then call this tool again with their answer as 'task' and this 'task_id'."
                ),
            }, indent=2, ensure_ascii=False)

        # ── Completed task ───────────────────────────────────
        text = _extract_text(result)
        if text:
            return text

    # Fallback: return raw JSON
    error = body.get("error")
    if error:
        return f"A2A Error: {json.dumps(error)}"
    return json.dumps(body, indent=2, ensure_ascii=False)


# ── Dynamic tool registration ────────────────────────────


def _register_agent_tool(endpoint: dict) -> None:
    """Register a single A2A endpoint as an MCP tool."""
    name = endpoint["name"]
    kind = endpoint["kind"]
    card = endpoint.get("card", {})
    rpc_url = endpoint["rpc_url"]
    description = card.get("description", f"{kind}: {name}")

    # Sanitize tool name (MCP tool names must be [a-zA-Z0-9_-])
    tool_name = f"{name}"
    if kind == "root_agent":
        tool_name = f"root_{name}"
    elif kind == "flow":
        tool_name = f"flow_{name}"

    # Create the tool function with closure-captured variables
    def _make_fn(captured_rpc: str, captured_name: str):
        async def fn(task: str, task_id: str = "") -> str:
            logger.info(f"Calling A2A agent: {captured_name} at {captured_rpc}"
                        + (f" (continuing task {task_id})" if task_id else ""))
            return await _call_a2a(captured_rpc, task, task_id=task_id or None)
        return fn

    _tool_fn = _make_fn(rpc_url, name)

    # Set proper metadata
    _tool_fn.__name__ = tool_name
    _tool_fn.__doc__ = (
        f"{description}\n\n"
        f"Send a task to the '{name}' agent on the platform via A2A protocol.\n\n"
        f"Args:\n"
        f"    task: Natural language description of what you want the agent to do, "
        f"or your answer if responding to an agent question.\n"
        f"    task_id: (Optional) Task ID from a previous input-required response. "
        f"Provide this to continue an existing conversation with the agent.\n\n"
        f"Multi-turn: If the response JSON contains '\"status\": \"input-required\"', "
        f"the agent needs human input. Ask the user the question, then call this tool "
        f"again with their answer as 'task' and the returned 'task_id'."
    )

    mcp.tool()(_tool_fn)
    logger.info(f"Registered tool: {tool_name} → {rpc_url}")


async def _load_catalog() -> None:
    """Fetch the A2A catalog and register tools."""
    global _ENDPOINTS
    catalog_url = f"{_BASE_URL}/a2a/catalog"
    logger.info(f"Fetching A2A catalog from {catalog_url}")

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(catalog_url)
        resp.raise_for_status()
        catalog = resp.json()

    _ENDPOINTS = catalog.get("endpoints", [])
    logger.info(f"Found {len(_ENDPOINTS)} A2A endpoints")

    for ep in _ENDPOINTS:
        _register_agent_tool(ep)


# ── Startup + list_agents discovery tool ─────────────────


@mcp.tool()
def list_agents() -> str:
    """List all available agents on the platform.

    Returns a summary of all A2A-exposed agents, root agents, and flows
    that you can interact with using the other tools.
    """
    if not _ENDPOINTS:
        return "No agents found. Is the platform running?"

    lines = ["Available agents on the platform:\n"]
    for ep in _ENDPOINTS:
        card = ep.get("card", {})
        name = ep["name"]
        kind = ep["kind"]
        desc = card.get("description", "")
        tool_name = f"root_{name}" if kind == "root_agent" else f"flow_{name}" if kind == "flow" else name
        lines.append(f"- **{tool_name}** ({kind}): {desc}")
    return "\n".join(lines)


# ── Main ─────────────────────────────────────────────────


def main():
    global _BASE_URL

    parser = argparse.ArgumentParser(description="A2A → MCP Bridge")
    parser.add_argument(
        "--base-url",
        default=os.environ.get("A2A_BASE_URL", "http://localhost:8000"),
        help="Base URL of the agent platform (default: http://localhost:8000)",
    )
    args = parser.parse_args()
    _BASE_URL = args.base_url.rstrip("/")

    logger.info(f"A2A MCP Bridge starting (platform: {_BASE_URL})")

    # Load catalog before starting MCP server
    import asyncio
    try:
        asyncio.run(_load_catalog())
    except Exception as e:
        logger.warning(f"Could not load A2A catalog at startup: {e}")
        logger.warning("Tools will not be available. Ensure the platform is running.")

    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
