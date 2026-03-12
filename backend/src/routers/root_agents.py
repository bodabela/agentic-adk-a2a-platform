"""Root-agent definition and instance management API."""

from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from src.shared.agents.loader import (
    delete_root_agent_definition,
    get_root_agent_detail,
    save_root_agent_definition,
)

router = APIRouter()


class RootAgentCreateRequest(BaseModel):
    name: str
    yaml_content: str


class RootAgentUpdateRequest(BaseModel):
    yaml_content: str


class InstanceStartRequest(BaseModel):
    definition_name: str


# ---------------------------------------------------------------------------
# Definitions CRUD
# ---------------------------------------------------------------------------

@router.get("/definitions")
async def list_definitions(request: Request):
    """List all root-agent definitions."""
    manager = request.app.state.root_agent_manager
    defs = []
    for name, defn in manager.definitions.items():
        defs.append({
            "name": defn.name,
            "version": defn.version,
            "description": defn.description,
            "model": defn.model,
            "max_iterations": defn.orchestration.max_iterations,
            "sub_agents": defn.sub_agents,
        })
    return {"definitions": defs}


@router.get("/definitions/{name}")
async def get_definition(name: str, request: Request):
    """Get a single root-agent definition with raw YAML."""
    root_agents_dir = Path(request.app.state.settings.root_agents_dir).resolve()
    detail = get_root_agent_detail(root_agents_dir, name)
    if not detail:
        raise HTTPException(status_code=404, detail=f"Root-agent '{name}' not found")

    manager = request.app.state.root_agent_manager
    defn = manager.definitions.get(name)
    return {
        "name": name,
        "yaml_content": detail["yaml_content"],
        "definition": defn.model_dump() if defn else None,
    }


@router.post("/definitions")
async def create_definition(req: RootAgentCreateRequest, request: Request):
    """Create a new root-agent definition."""
    root_agents_dir = Path(request.app.state.settings.root_agents_dir).resolve()
    manager = request.app.state.root_agent_manager

    if req.name in manager.definitions:
        raise HTTPException(status_code=409, detail=f"Root-agent '{req.name}' already exists")

    try:
        defn = save_root_agent_definition(root_agents_dir, req.name, req.yaml_content)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    manager.reload()
    return {"status": "created", "definition": defn.model_dump()}


@router.put("/definitions/{name}")
async def update_definition(name: str, req: RootAgentUpdateRequest, request: Request):
    """Update a root-agent definition."""
    root_agents_dir = Path(request.app.state.settings.root_agents_dir).resolve()
    manager = request.app.state.root_agent_manager

    if name not in manager.definitions:
        raise HTTPException(status_code=404, detail=f"Root-agent '{name}' not found")

    try:
        defn = save_root_agent_definition(root_agents_dir, name, req.yaml_content)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    manager.reload()
    return {"status": "updated", "definition": defn.model_dump()}


@router.delete("/definitions/{name}")
async def delete_definition(name: str, request: Request):
    """Delete a root-agent definition."""
    root_agents_dir = Path(request.app.state.settings.root_agents_dir).resolve()
    manager = request.app.state.root_agent_manager

    if name not in manager.definitions:
        raise HTTPException(status_code=404, detail=f"Root-agent '{name}' not found")

    delete_root_agent_definition(root_agents_dir, name)
    manager.reload()
    return {"status": "deleted", "name": name}


# ---------------------------------------------------------------------------
# Instances
# ---------------------------------------------------------------------------

@router.get("/instances")
async def list_instances(request: Request):
    """List running root-agent instances."""
    manager = request.app.state.root_agent_manager
    return {"instances": manager.list_instances()}


@router.post("/instances")
async def start_instance(req: InstanceStartRequest, request: Request):
    """Start a new root-agent instance."""
    manager = request.app.state.root_agent_manager
    try:
        inst = manager.start_instance(req.definition_name)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"status": "started", "instance": inst.to_dict()}


@router.delete("/instances/{instance_id}")
async def stop_instance(instance_id: str, request: Request):
    """Stop a running root-agent instance."""
    manager = request.app.state.root_agent_manager
    inst = manager.get_instance(instance_id)
    if not inst:
        raise HTTPException(status_code=404, detail=f"Instance '{instance_id}' not found")
    manager.stop_instance(instance_id)
    return {"status": "stopped", "instance_id": instance_id}
