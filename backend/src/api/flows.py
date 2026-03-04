"""Flow management API."""

import asyncio
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from src.flow_engine.dsl.parser import FlowParser
from src.flow_engine.dsl.validator import FlowValidator
from src.flow_engine.engine import FlowEngine

router = APIRouter()

# Module-level registry of active flow engines
_active_engines: dict[str, FlowEngine] = {}


class FlowStartRequest(BaseModel):
    flow_file: str
    input: dict[str, Any] = {}
    provider: str | None = None
    model: str | None = None


class FlowStartResponse(BaseModel):
    flow_id: str | None = None
    status: str
    flow_name: str
    states: list[str] = []


class InteractionResponse(BaseModel):
    interaction_id: str
    response: Any


def _build_default_input(schema: dict[str, Any] | None) -> dict[str, Any]:
    """Generate a default input object from a JSON Schema-style input_schema."""
    if not schema or "properties" not in schema:
        return {}
    result: dict[str, Any] = {}
    for key, prop in schema["properties"].items():
        prop_type = prop.get("type", "string")
        if prop_type == "string":
            result[key] = ""
        elif prop_type in ("number", "integer"):
            result[key] = 0
        elif prop_type == "boolean":
            result[key] = False
        elif prop_type == "array":
            result[key] = []
        elif prop_type == "object":
            result[key] = {}
    return result


@router.get("/")
async def list_flows(request: Request):
    """List available flow definition files with metadata."""
    settings = request.app.state.settings
    flows_dir = Path(settings.flows_dir)

    flows = []
    if flows_dir.exists():
        parser = FlowParser()
        for f in flows_dir.glob("*.flow.yaml"):
            try:
                parsed = parser.parse_file(f)
                default_input = _build_default_input(parsed.definition.trigger.input_schema)
                flows.append({
                    "name": f.stem,
                    "file": f.name,
                    "description": parsed.definition.description,
                    "default_input": default_input,
                })
            except Exception:
                flows.append({"name": f.stem, "file": f.name, "description": "", "default_input": {}})

    return {"flows": flows}


@router.post("/start", response_model=FlowStartResponse)
async def start_flow(req: FlowStartRequest, request: Request):
    """Parse, validate, and start a flow execution."""
    flow_path = Path(req.flow_file)
    if not flow_path.exists():
        # Try relative to flows dir
        settings = request.app.state.settings
        flow_path = Path(settings.flows_dir) / req.flow_file
        if not flow_path.exists():
            raise HTTPException(status_code=404, detail=f"Flow file not found: {req.flow_file}")

    parser = FlowParser()
    validator = FlowValidator()

    flow = parser.parse_file(flow_path)

    errors = validator.validate(flow)
    hard_errors = [e for e in errors if e.severity == "error"]
    if hard_errors:
        raise HTTPException(
            status_code=400,
            detail=f"Flow validation errors: {hard_errors}",
        )

    engine = FlowEngine(
        event_bus=request.app.state.event_bus,
        cost_tracker=request.app.state.cost_tracker,
        llm_config=request.app.state.llm_config,
        runtime_provider=req.provider,
        runtime_model=req.model,
        agent_registry=request.app.state.agent_registry,
    )

    _active_engines[flow.name] = engine

    # Run flow asynchronously
    asyncio.create_task(engine.execute_flow(flow, req.input))

    return FlowStartResponse(
        status="started",
        flow_name=flow.name,
        states=list(flow.nodes.keys()),
    )


@router.post("/interact")
async def submit_interaction(req: InteractionResponse):
    """Submit a user response to a pending human_interaction node."""
    responded = False
    for engine in _active_engines.values():
        if await engine.submit_interaction_response(req.interaction_id, req.response):
            responded = True
            break

    if not responded:
        raise HTTPException(
            status_code=404,
            detail=f"No pending interaction found: {req.interaction_id}",
        )

    return {"status": "ok", "interaction_id": req.interaction_id}


@router.get("/definition/{flow_file:path}")
async def get_flow_definition(flow_file: str, request: Request):
    """Return the full parsed flow definition (states, transitions, config)."""
    settings = request.app.state.settings
    flow_path = Path(settings.flows_dir) / flow_file
    if not flow_path.exists():
        raise HTTPException(status_code=404, detail=f"Flow file not found: {flow_file}")

    parser = FlowParser()
    try:
        parsed = parser.parse_file(flow_path)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Failed to parse flow: {exc}")

    # Serialize each node back to dict
    states: dict[str, Any] = {}
    for state_name, node in parsed.nodes.items():
        states[state_name] = node.model_dump(exclude_none=True)

    config = parsed.definition.config.model_dump(exclude_none=True)

    return {
        "name": parsed.definition.name,
        "description": parsed.definition.description,
        "version": parsed.definition.version,
        "config": config,
        "states": states,
    }


@router.get("/active")
async def list_active_flows():
    """List currently active flow engines."""
    return {
        "active_flows": [
            {"name": name}
            for name in _active_engines
        ]
    }
