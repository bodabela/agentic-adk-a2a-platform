"""Task management API."""

import asyncio
import json
import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from opentelemetry import trace
from pydantic import BaseModel, Field

from src.features.tasks.executor import execute_task, pending_interactions, running_tasks

router = APIRouter()


class TaskSubmission(BaseModel):
    """Request body for submitting a new task to the platform."""

    description: str = Field(
        ...,
        description="Natural-language description of what the task should accomplish.",
        examples=["Summarize the latest sales report and send it to the team"],
    )
    context: dict | None = Field(
        default=None,
        description="Optional key-value context passed to the agent (e.g. user info, prior results).",
        examples=[{"user_email": "alice@example.com", "priority": "high"}],
    )
    root_agent_definition: str | None = Field(
        default=None,
        description="Name of the root-agent definition to use. Mutually exclusive with `root_agent_instance_id`.",
        examples=["default-orchestrator"],
    )
    root_agent_instance_id: str | None = Field(
        default=None,
        description="ID of an already-running root-agent instance to route the task to.",
    )
    channel: str | None = Field(
        default=None,
        description="Communication channel override for human interactions (e.g. `web_ui`, `teams`, `whatsapp`). "
        "Defaults to the platform default.",
        examples=["web_ui"],
    )


class TaskResponse(BaseModel):
    """Response returned when a task is successfully submitted."""

    task_id: str = Field(..., description="Unique identifier for the created task.", examples=["a1b2c3d4-e5f6-7890-abcd-ef1234567890"])
    status: str = Field(..., description="Current task status.", examples=["submitted"])
    description: str = Field(..., description="Echo of the submitted task description.")


class TaskInteractionResponse(BaseModel):
    """Request body for responding to a pending human-in-the-loop interaction."""

    interaction_id: str = Field(
        ...,
        description="ID of the pending interaction to respond to.",
        examples=["int-abc123"],
    )
    response: Any = Field(
        ...,
        description="The user's response value. Can be free text, a choice selection, or a boolean confirmation.",
        examples=["Yes, approve the deployment"],
    )


@router.post(
    "/",
    tags=["Client: Tasks"],
    response_model=TaskResponse,
    summary="Submit a new task",
    description="Creates a new task and routes it to the specified (or default) root agent for execution. "
    "The task runs asynchronously — subscribe to the SSE stream at `/api/events/stream` to receive "
    "real-time progress updates, cost events, and interaction requests.",
    response_description="The created task with its assigned ID and initial status.",
)
async def create_task(submission: TaskSubmission, request: Request):
    task_id = str(uuid.uuid4())
    event_bus = request.app.state.event_bus

    # Set Langfuse trace input on the active (FastAPI root) span
    span = trace.get_current_span()
    if span and span.is_recording():
        trace_input = {"description": submission.description}
        if submission.context:
            trace_input["context"] = submission.context
        if submission.root_agent_definition:
            trace_input["agent"] = submission.root_agent_definition
        span.set_attribute("langfuse.trace.input", json.dumps(trace_input, ensure_ascii=False))
        span.set_attribute("langfuse.trace.session.id", task_id)
        span.set_attribute("langfuse.trace.user.id", "user")

    await event_bus.emit("task_submitted", {
        "task_id": task_id,
        "description": submission.description,
    })

    # Execute via the root agent (async, non-blocking)
    task = asyncio.create_task(execute_task(task_id, submission, request))
    running_tasks[task_id] = task

    return TaskResponse(
        task_id=task_id,
        status="submitted",
        description=submission.description,
    )


@router.get(
    "/{task_id}",
    tags=["Client: Tasks"],
    summary="Get task status",
    description="Retrieves the current status and accumulated LLM cost report for a task. "
    "The cost report includes per-model token counts and estimated cost in USD.",
    response_description="Task status with optional cost breakdown.",
)
async def get_task(task_id: str, request: Request):
    cost_tracker = request.app.state.cost_tracker
    report = cost_tracker.get_report(task_id)
    return {
        "task_id": task_id,
        "cost_report": report.model_dump() if report else None,
    }


@router.post(
    "/interact",
    tags=["Client: Tasks"],
    summary="Respond to a task interaction (legacy)",
    description="Submit a user response to a pending human-in-the-loop interaction within a task. "
    "**Note:** prefer the unified `/api/interactions/respond` endpoint for new integrations.",
    response_description="Confirmation that the response was delivered.",
    deprecated=True,
)
async def submit_task_interaction(req: TaskInteractionResponse):
    future = pending_interactions.get(req.interaction_id)
    if future and not future.done():
        future.set_result(req.response)
        return {"status": "ok", "interaction_id": req.interaction_id}
    raise HTTPException(
        status_code=404,
        detail=f"No pending interaction found: {req.interaction_id}",
    )
