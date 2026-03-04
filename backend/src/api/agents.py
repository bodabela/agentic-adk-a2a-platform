"""Agent module listing API."""

from fastapi import APIRouter, Request

router = APIRouter()


@router.get("/")
async def list_agents(request: Request):
    """List all discovered agent modules with their capabilities."""
    registry = request.app.state.agent_registry
    agents = []
    for info in registry.list_agents():
        agent_conf = info.module_yaml.get("agent", {})
        tools_conf = info.module_yaml.get("tools", {})
        # Support both old (local/remote) and new (mcp) tool formats
        tool_names = []
        if "mcp" in tools_conf:
            tool_names = [t.get("name", "") for t in tools_conf["mcp"].get("tools", [])]
        else:
            tool_names = (
                [t.get("name", "") for t in tools_conf.get("local", [])]
                + [t.get("ref", "") for t in tools_conf.get("remote", [])]
            )

        agents.append({
            "name": info.name,
            "version": info.version,
            "description": info.description,
            "capabilities": info.capabilities,
            "category": info.module_yaml.get("module", {}).get("category", ""),
            "model": agent_conf.get("model", ""),
            "tools": tool_names,
        })

    return {"agents": agents}
