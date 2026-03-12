"""Task management API."""

import asyncio
import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from src.features.tasks.executor import execute_task, pending_interactions, running_tasks

router = APIRouter()


class TaskSubmission(BaseModel):
    description: str
    context: dict | None = None
    root_agent_definition: str | None = None    # which root-agent def to use
    root_agent_instance_id: str | None = None   # or which running instance
    channel: str | None = None                  # interaction channel override


class TaskResponse(BaseModel):
    task_id: str
    status: str
    description: str


class TaskInteractionResponse(BaseModel):
    interaction_id: str
    response: Any


@router.post("/", response_model=TaskResponse)
async def create_task(submission: TaskSubmission, request: Request):
    """Submit a new task to the root agent."""
    task_id = str(uuid.uuid4())
    event_bus = request.app.state.event_bus

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


@router.get("/{task_id}")
async def get_task(task_id: str, request: Request):
    """Get task status and cost report."""
    cost_tracker = request.app.state.cost_tracker
    report = cost_tracker.get_report(task_id)
    return {
        "task_id": task_id,
        "cost_report": report.model_dump() if report else None,
    }


@router.post("/interact")
async def submit_task_interaction(req: TaskInteractionResponse):
    """Submit a user response to a pending task interaction."""
    future = pending_interactions.get(req.interaction_id)
    if future and not future.done():
        future.set_result(req.response)
        return {"status": "ok", "interaction_id": req.interaction_id}
    raise HTTPException(
        status_code=404,
        detail=f"No pending interaction found: {req.interaction_id}",
    )
