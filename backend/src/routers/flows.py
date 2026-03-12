"""Flow management API."""

import asyncio
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from src.features.flows.engine.dsl.parser import FlowParser
from src.features.flows.engine.dsl.validator import FlowValidator
from src.features.flows.engine.engine import FlowEngine

router = APIRouter()

# Module-level registry of active flow engines
_active_engines: dict[str, FlowEngine] = {}


class FlowStartRequest(BaseModel):
    """Request body for starting a flow execution."""

    flow_file: str = Field(
        ...,
        description="Filename of the flow definition (e.g. `onboarding.flow.yaml`). "
        "Resolved relative to the configured flows directory.",
        examples=["onboarding.flow.yaml"],
    )
    input: dict[str, Any] = Field(
        default={},
        description="Input variables for the flow's trigger. Keys must match the flow's `input_schema`.",
        examples=[{"customer_name": "Acme Corp", "tier": "enterprise"}],
    )
    provider: str | None = Field(
        default=None,
        description="LLM provider override for this flow run (e.g. `google`, `anthropic`, `openai`).",
    )
    model: str | None = Field(
        default=None,
        description="LLM model override for this flow run (e.g. `gemini-2.0-flash`, `claude-sonnet-4-20250514`).",
    )
    channel: str | None = Field(
        default=None,
        description="Communication channel for human interaction nodes (`web_ui`, `teams`, `whatsapp`).",
        examples=["web_ui"],
    )


class FlowStartResponse(BaseModel):
    """Response returned when a flow is successfully started."""

    flow_id: str | None = Field(default=None, description="Unique identifier for the flow execution (if assigned).")
    status: str = Field(..., description="Execution status.", examples=["started"])
    flow_name: str = Field(..., description="Name of the flow definition.", examples=["onboarding"])
    states: list[str] = Field(
        default=[],
        description="Ordered list of state names defined in the flow.",
        examples=[["init", "collect_info", "review", "approve", "done"]],
    )


class InteractionResponse(BaseModel):
    """Request body for responding to a pending flow interaction."""

    interaction_id: str = Field(..., description="ID of the pending interaction.", examples=["int-xyz789"])
    response: Any = Field(..., description="The user's response value.", examples=["Approved"])


class FlowCreateRequest(BaseModel):
    """Request body for creating a new flow definition."""

    filename: str = Field(
        ...,
        description="Filename for the new flow (must end with `.flow.yaml`).",
        examples=["invoice-approval.flow.yaml"],
    )
    content: str = Field(
        ...,
        description="Raw YAML content of the flow definition.",
    )


class FlowUpdateRequest(BaseModel):
    """Request body for updating an existing flow definition."""

    content: str = Field(
        ...,
        description="Updated YAML content for the flow definition.",
    )


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


@router.get(
    "/",
    tags=["Client: Flows"],
    summary="List flow definitions",
    description="Returns all available flow definition files from the configured flows directory, "
    "including parsed metadata (name, description) and default input values derived from the flow's input schema.",
    response_description="List of flow definitions with metadata.",
)
async def list_flows(request: Request):
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


@router.post(
    "/start",
    tags=["Client: Flows"],
    response_model=FlowStartResponse,
    summary="Start a flow execution",
    description="Parses and validates the specified flow definition, then starts asynchronous execution. "
    "The flow engine processes states sequentially, emitting events via SSE for each transition. "
    "Human interaction nodes will pause execution until a response is submitted.",
    response_description="Flow execution details including the list of states to be executed.",
)
async def start_flow(req: FlowStartRequest, request: Request):
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
        agent_factory=request.app.state.agent_factory,
        session_manager=request.app.state.session_manager,
        interaction_broker=getattr(request.app.state, "interaction_broker", None),
        channel=req.channel or "web_ui",
    )

    _active_engines[flow.name] = engine

    # Run flow asynchronously
    asyncio.create_task(engine.execute_flow(flow, req.input))

    return FlowStartResponse(
        status="started",
        flow_name=flow.name,
        states=list(flow.nodes.keys()),
    )


@router.post(
    "/interact",
    tags=["Client: Flows"],
    summary="Respond to a flow interaction (legacy)",
    description="Submit a user response to a pending `human_interaction` node in an active flow. "
    "**Note:** prefer the unified `/api/interactions/respond` endpoint for new integrations.",
    response_description="Confirmation that the response was delivered.",
    deprecated=True,
)
async def submit_interaction(req: InteractionResponse):
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


@router.get(
    "/definition/{flow_file:path}",
    tags=["Admin: Flows"],
    summary="Get parsed flow definition",
    description="Returns the fully parsed flow definition including all states, transitions, "
    "configuration, and metadata. Useful for visualizing the flow graph in the UI.",
    response_description="Parsed flow structure with states and configuration.",
)
async def get_flow_definition(flow_file: str, request: Request):
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


@router.get(
    "/active",
    tags=["Admin: Flows"],
    summary="List active flows",
    description="Returns the names of all currently executing flow engines. "
    "A flow remains active until it reaches a terminal state or is explicitly stopped.",
    response_description="List of active flow names.",
)
async def list_active_flows():
    return {
        "active_flows": [
            {"name": name}
            for name in _active_engines
        ]
    }


# ---------------------------------------------------------------------------
# Flow CRUD
# ---------------------------------------------------------------------------


@router.get(
    "/raw/{flow_file:path}",
    tags=["Admin: Flows"],
    summary="Get raw flow YAML",
    description="Returns the raw YAML content of a flow definition file for editing in the UI.",
    response_description="Flow filename and its raw YAML content.",
)
async def get_flow_raw(flow_file: str, request: Request):
    settings = request.app.state.settings
    flow_path = Path(settings.flows_dir) / flow_file
    if not flow_path.exists():
        raise HTTPException(status_code=404, detail=f"Flow file not found: {flow_file}")
    return {"file": flow_file, "content": flow_path.read_text(encoding="utf-8")}


@router.post(
    "/upload",
    tags=["Admin: Flows"],
    summary="Create a new flow definition",
    description="Uploads and validates a new flow YAML definition. The file is validated before saving — "
    "if the YAML is invalid or contains schema errors, the request is rejected with details.",
    response_description="Confirmation with the created filename.",
)
async def upload_flow(req: FlowCreateRequest, request: Request):
    settings = request.app.state.settings
    flows_dir = Path(settings.flows_dir)
    flows_dir.mkdir(parents=True, exist_ok=True)

    flow_path = flows_dir / req.filename
    if flow_path.exists():
        raise HTTPException(status_code=409, detail=f"Flow '{req.filename}' already exists")

    # Validate before saving
    parser = FlowParser()
    try:
        import tempfile, os
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False, encoding="utf-8") as tmp:
            tmp.write(req.content)
            tmp_path = tmp.name
        try:
            parser.parse_file(Path(tmp_path))
        finally:
            os.unlink(tmp_path)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid flow YAML: {e}")

    flow_path.write_text(req.content, encoding="utf-8")
    return {"status": "created", "file": req.filename}


@router.put(
    "/{flow_file:path}",
    tags=["Admin: Flows"],
    summary="Update a flow definition",
    description="Replaces the content of an existing flow definition. The new YAML is validated before saving.",
    response_description="Confirmation with the updated filename.",
)
async def update_flow(flow_file: str, req: FlowUpdateRequest, request: Request):
    settings = request.app.state.settings
    flow_path = Path(settings.flows_dir) / flow_file
    if not flow_path.exists():
        raise HTTPException(status_code=404, detail=f"Flow file not found: {flow_file}")

    # Validate before saving
    parser = FlowParser()
    try:
        import tempfile, os
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False, encoding="utf-8") as tmp:
            tmp.write(req.content)
            tmp_path = tmp.name
        try:
            parser.parse_file(Path(tmp_path))
        finally:
            os.unlink(tmp_path)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid flow YAML: {e}")

    flow_path.write_text(req.content, encoding="utf-8")
    return {"status": "updated", "file": flow_file}


@router.delete(
    "/{flow_file:path}",
    tags=["Admin: Flows"],
    summary="Delete a flow definition",
    description="Permanently removes a flow definition file from the flows directory. "
    "This does not affect already-running flow executions.",
    response_description="Confirmation with the deleted filename.",
)
async def delete_flow(flow_file: str, request: Request):
    settings = request.app.state.settings
    flow_path = Path(settings.flows_dir) / flow_file
    if not flow_path.exists():
        raise HTTPException(status_code=404, detail=f"Flow file not found: {flow_file}")
    flow_path.unlink()
    return {"status": "deleted", "file": flow_file}
