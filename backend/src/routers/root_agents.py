"""Root-agent definition and instance management API."""

from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from src.shared.agents.loader import (
    delete_root_agent_definition,
    get_root_agent_detail,
    save_root_agent_definition,
)

router = APIRouter()


class RootAgentCreateRequest(BaseModel):
    """Request body for creating a new root-agent definition."""

    name: str = Field(
        ...,
        description="Unique name for the root agent.",
        examples=["default-orchestrator"],
    )
    yaml_content: str = Field(
        ...,
        description="YAML content defining the root agent's orchestration config, sub-agents, and loop strategy.",
    )


class RootAgentUpdateRequest(BaseModel):
    """Request body for updating a root-agent definition."""

    yaml_content: str = Field(
        ...,
        description="Updated YAML content for the root agent definition.",
    )


class InstanceStartRequest(BaseModel):
    """Request body for starting a new root-agent instance."""

    definition_name: str = Field(
        ...,
        description="Name of the root-agent definition to instantiate.",
        examples=["default-orchestrator"],
    )


# ---------------------------------------------------------------------------
# Definitions CRUD
# ---------------------------------------------------------------------------

@router.get(
    "/definitions",
    tags=["Admin: Root Agents"],
    summary="List root-agent definitions",
    description="Returns all registered root-agent definitions with metadata including "
    "orchestration settings (model, max iterations) and the list of sub-agents.",
    response_description="List of root-agent definitions with orchestration metadata.",
)
async def list_definitions(request: Request):
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


@router.get(
    "/definitions/{name}",
    tags=["Admin: Root Agents"],
    summary="Get root-agent definition",
    description="Returns a single root-agent definition with its raw YAML content and parsed configuration. "
    "Useful for editing in the UI.",
    response_description="Root-agent name, raw YAML, and parsed definition.",
)
async def get_definition(name: str, request: Request):
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


@router.post(
    "/definitions",
    tags=["Admin: Root Agents"],
    summary="Create a root-agent definition",
    description="Creates a new root-agent definition by saving the YAML config to the root agents directory. "
    "The manager is reloaded automatically to pick up the new definition.",
    response_description="Confirmation with the created definition.",
)
async def create_definition(req: RootAgentCreateRequest, request: Request):
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


@router.put(
    "/definitions/{name}",
    tags=["Admin: Root Agents"],
    summary="Update a root-agent definition",
    description="Replaces the YAML configuration of an existing root-agent definition. "
    "Running instances are not affected — they continue using the config they were started with.",
    response_description="Confirmation with the updated definition.",
)
async def update_definition(name: str, req: RootAgentUpdateRequest, request: Request):
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


@router.delete(
    "/definitions/{name}",
    tags=["Admin: Root Agents"],
    summary="Delete a root-agent definition",
    description="Permanently removes a root-agent definition. Running instances of this definition are not affected.",
    response_description="Confirmation with the deleted definition name.",
)
async def delete_definition(name: str, request: Request):
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

@router.get(
    "/instances",
    tags=["Admin: Root Agents"],
    summary="List running instances",
    description="Returns all currently running root-agent instances with their IDs, definition names, and status.",
    response_description="List of running root-agent instances.",
)
async def list_instances(request: Request):
    manager = request.app.state.root_agent_manager
    return {"instances": manager.list_instances()}


@router.post(
    "/instances",
    tags=["Admin: Root Agents"],
    summary="Start a new instance",
    description="Creates and starts a new root-agent instance from the specified definition. "
    "The instance can then receive tasks via the `/api/tasks` endpoint.",
    response_description="Confirmation with the started instance details.",
)
async def start_instance(req: InstanceStartRequest, request: Request):
    manager = request.app.state.root_agent_manager
    try:
        inst = manager.start_instance(req.definition_name)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"status": "started", "instance": inst.to_dict()}


@router.delete(
    "/instances/{instance_id}",
    tags=["Admin: Root Agents"],
    summary="Stop a running instance",
    description="Stops and removes a running root-agent instance. Any in-progress tasks will be cancelled.",
    response_description="Confirmation with the stopped instance ID.",
)
async def stop_instance(instance_id: str, request: Request):
    manager = request.app.state.root_agent_manager
    inst = manager.get_instance(instance_id)
    if not inst:
        raise HTTPException(status_code=404, detail=f"Instance '{instance_id}' not found")
    manager.stop_instance(instance_id)
    return {"status": "stopped", "instance_id": instance_id}
