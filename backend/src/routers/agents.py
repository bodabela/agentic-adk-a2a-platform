"""Agent definition CRUD API."""

import re
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from src.shared.agents.loader import (
    delete_agent_definition,
    get_agent_detail,
    save_agent_definition,
)

router = APIRouter()

# Regex to find @mcp.tool() decorated functions in MCP server source files
_MCP_TOOL_PATTERN = re.compile(r"@mcp\.tool\(\)\s*\n\s*(?:async\s+)?def\s+(\w+)")


def _extract_mcp_tool_names(server_path: Path) -> list[str]:
    """Parse an MCP server .py file and extract @mcp.tool() function names."""
    try:
        if not server_path.is_file():
            return []
        source = server_path.read_text(encoding="utf-8")
        return _MCP_TOOL_PATTERN.findall(source)
    except Exception:
        return []


class AgentCreateRequest(BaseModel):
    name: str
    yaml_content: str
    prompt_content: str | None = None


class AgentUpdateRequest(BaseModel):
    yaml_content: str | None = None
    prompt_content: str | None = None


# ---------------------------------------------------------------------------
# List
# ---------------------------------------------------------------------------

@router.get("/")
async def list_agents(request: Request):
    """List all agent definitions."""
    factory = request.app.state.agent_factory
    agents_dir = Path(request.app.state.settings.agents_dir).resolve()
    agents = []
    for name, defn in factory.definitions.items():
        # Build a flat tool name list for display
        tool_names: list[str] = list(defn.tools.builtin)
        for mcp_conf in defn.tools.mcp:
            if mcp_conf.server:
                # Try to extract @mcp.tool() function names from server source
                agent_dir = agents_dir / defn.name
                server_path = (agent_dir / mcp_conf.server).resolve()
                mcp_tools = _extract_mcp_tool_names(server_path)
                if mcp_tools:
                    tool_names.extend(mcp_tools)
                else:
                    tool_names.append(f"mcp:{Path(mcp_conf.server).stem}")
        agents.append({
            "name": defn.name,
            "version": defn.version,
            "description": defn.description,
            "category": defn.category,
            "model": defn.model,
            "model_fallback": defn.model_fallback,
            "capabilities": defn.capabilities,
            "tools": tool_names,
        })
    return {"agents": agents}


# ---------------------------------------------------------------------------
# Detail
# ---------------------------------------------------------------------------

@router.get("/{agent_name}")
async def get_agent(agent_name: str, request: Request):
    """Get full agent definition including YAML and prompt content."""
    agents_dir = Path(request.app.state.settings.agents_dir).resolve()
    detail = get_agent_detail(agents_dir, agent_name)
    if not detail:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_name}' not found")

    factory = request.app.state.agent_factory
    defn = factory.definitions.get(agent_name)

    return {
        "name": agent_name,
        "yaml_content": detail["yaml_content"],
        "prompt_content": detail["prompt_content"],
        "definition": defn.model_dump() if defn else None,
    }


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------

@router.post("/")
async def create_agent(req: AgentCreateRequest, request: Request):
    """Create a new agent definition."""
    agents_dir = Path(request.app.state.settings.agents_dir).resolve()
    factory = request.app.state.agent_factory

    if factory.has_agent(req.name):
        raise HTTPException(status_code=409, detail=f"Agent '{req.name}' already exists")

    try:
        defn = save_agent_definition(agents_dir, req.name, req.yaml_content, req.prompt_content)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    factory.reload()
    return {"status": "created", "agent": defn.model_dump()}


# ---------------------------------------------------------------------------
# Update
# ---------------------------------------------------------------------------

@router.put("/{agent_name}")
async def update_agent(agent_name: str, req: AgentUpdateRequest, request: Request):
    """Update an existing agent definition."""
    agents_dir = Path(request.app.state.settings.agents_dir).resolve()
    factory = request.app.state.agent_factory

    if not factory.has_agent(agent_name):
        raise HTTPException(status_code=404, detail=f"Agent '{agent_name}' not found")

    # Read existing content for fields not provided
    detail = get_agent_detail(agents_dir, agent_name) or {}
    yaml_content = req.yaml_content or detail.get("yaml_content", "")
    prompt_content = req.prompt_content if req.prompt_content is not None else detail.get("prompt_content")

    try:
        defn = save_agent_definition(agents_dir, agent_name, yaml_content, prompt_content)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    factory.reload()
    return {"status": "updated", "agent": defn.model_dump()}


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------

@router.delete("/{agent_name}")
async def delete_agent(agent_name: str, request: Request):
    """Delete an agent definition."""
    agents_dir = Path(request.app.state.settings.agents_dir).resolve()
    factory = request.app.state.agent_factory

    if not factory.has_agent(agent_name):
        raise HTTPException(status_code=404, detail=f"Agent '{agent_name}' not found")

    delete_agent_definition(agents_dir, agent_name)
    factory.reload()
    return {"status": "deleted", "name": agent_name}
