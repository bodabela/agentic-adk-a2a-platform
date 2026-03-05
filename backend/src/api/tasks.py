"""Task management API."""

import asyncio
import time
import traceback
import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from src.common.logging import get_logger

logger = get_logger("tasks")

router = APIRouter()

# Module-level registry of pending interactions: interaction_id -> asyncio.Future
_pending_interactions: dict[str, asyncio.Future] = {}


class TaskSubmission(BaseModel):
    description: str
    context: dict | None = None


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
    asyncio.create_task(
        _execute_task(task_id, submission, request)
    )

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
    future = _pending_interactions.get(req.interaction_id)
    if future and not future.done():
        future.set_result(req.response)
        return {"status": "ok", "interaction_id": req.interaction_id}
    raise HTTPException(
        status_code=404,
        detail=f"No pending interaction found: {req.interaction_id}",
    )


async def _execute_task(task_id: str, submission: TaskSubmission, request: Request):
    """Run the root agent to process the task."""
    event_bus = request.app.state.event_bus

    logger.info("task_execution_start", task_id=task_id, description=submission.description)

    try:
        from google.adk.runners import Runner
        from google.adk.sessions import InMemorySessionService
        from google.genai import types
        from src.orchestrator.root_agent import RootAgentFactory

        registry = request.app.state.agent_registry
        llm_config = request.app.state.llm_config
        default_model = llm_config.defaults.model
        logger.info("task_creating_agent", task_id=task_id, model=default_model)

        settings = request.app.state.settings
        factory = RootAgentFactory(
            registry,
            model=default_model,
            modules_dir=settings.modules_dir,
            workspace_dir=settings.workspace_dir,
            event_bus=event_bus,
            task_id=task_id,
            pending_interactions=_pending_interactions,
        )
        root_agent = factory.create_root_agent()
        logger.info("task_agent_created", task_id=task_id, agent=root_agent.name)

        session_service = InMemorySessionService()
        runner = Runner(
            agent=root_agent,
            app_name="agent_platform",
            session_service=session_service,
        )
        session = await session_service.create_session(
            app_name="agent_platform", user_id="user"
        )

        user_message = types.Content(
            role="user",
            parts=[types.Part(text=submission.description)],
        )

        logger.info("task_runner_start", task_id=task_id, session_id=session.id)

        from google.adk.agents.run_config import RunConfig, StreamingMode

        cost_tracker = request.app.state.cost_tracker
        default_provider = llm_config.defaults.provider or "google"
        last_event_time = time.monotonic()

        async for event in runner.run_async(
            user_id="user", session_id=session.id, new_message=user_message,
            run_config=RunConfig(streaming_mode=StreamingMode.SSE),
        ):
            author = getattr(event, "author", None) or ""
            content = getattr(event, "content", None)
            is_partial = getattr(event, "partial", False)

            # Record cost from usage_metadata on non-partial events
            usage = getattr(event, "usage_metadata", None)
            if usage and not is_partial:
                now = time.monotonic()
                latency = int((now - last_event_time) * 1000)
                last_event_time = now
                input_tokens = usage.prompt_token_count or 0
                output_tokens = usage.candidates_token_count or 0
                model_version = getattr(event, "model_version", None) or default_model
                try:
                    await cost_tracker.record_llm_call(
                        task_id=task_id,
                        module=author or "root_agent",
                        agent=author or "root_agent",
                        model=model_version,
                        input_tokens=input_tokens,
                        output_tokens=output_tokens,
                        latency_ms=latency,
                        provider=default_provider,
                    )
                except Exception as cost_err:
                    logger.warning("cost_tracking_failed", error=str(cost_err))

            if not content or not hasattr(content, "parts"):
                continue

            # Partial text — stream token chunks
            if is_partial:
                for part in content.parts:
                    if hasattr(part, "text") and part.text:
                        if hasattr(part, "function_call") and part.function_call:
                            continue  # skip partial function_call arg streaming
                        is_thought = getattr(part, "thought", False)
                        await event_bus.emit("task_event", {
                            "task_id": task_id,
                            "event_type": "streaming_text",
                            "agent": author,
                            "author": author,
                            "model": default_model,
                            "text": part.text,
                            "is_thought": bool(is_thought),
                        })
                        await asyncio.sleep(0)
                continue

            for part in content.parts:
                if hasattr(part, "text") and part.text:
                    is_thought = getattr(part, "thought", False)
                    if is_thought or not event.is_final_response():
                        await event_bus.emit("task_event", {
                            "task_id": task_id,
                            "event_type": "thinking",
                            "agent": author,
                            "author": author,
                            "model": default_model,
                            "text": part.text,
                            "is_thought": bool(is_thought),
                        })
                    else:
                        await event_bus.emit("task_event", {
                            "task_id": task_id,
                            "event_type": "agent_response",
                            "agent": author,
                            "author": author,
                            "model": default_model,
                            "text": part.text,
                        })
                    await asyncio.sleep(0)
                elif hasattr(part, "function_call") and part.function_call:
                    fc = part.function_call
                    await event_bus.emit("task_event", {
                        "task_id": task_id,
                        "event_type": "tool_call",
                        "agent": author,
                        "author": author,
                        "model": default_model,
                        "tool_name": fc.name,
                        "tool_args": dict(fc.args) if fc.args else {},
                    })
                    await asyncio.sleep(0)
                elif hasattr(part, "function_response") and part.function_response:
                    fr = part.function_response
                    resp_data = fr.response
                    if hasattr(resp_data, "model_dump"):
                        resp_data = resp_data.model_dump()
                    elif not isinstance(resp_data, (dict, list, str, int, float, bool, type(None))):
                        resp_data = str(resp_data)
                    await event_bus.emit("task_event", {
                        "task_id": task_id,
                        "event_type": "tool_result",
                        "agent": author,
                        "author": author,
                        "model": default_model,
                        "tool_name": fr.name,
                        "tool_response": resp_data,
                    })
                    await asyncio.sleep(0)

        logger.info("task_execution_completed", task_id=task_id)
        await event_bus.emit("task_completed", {
            "task_id": task_id,
            "status": "success",
        })

    except Exception as e:
        tb = traceback.format_exc()
        error_type = type(e).__name__
        error_msg = str(e) or repr(e)
        logger.error(
            "task_execution_failed",
            task_id=task_id,
            error_type=error_type,
            error=error_msg,
            traceback=tb,
        )
        await event_bus.emit("task_failed", {
            "task_id": task_id,
            "status": "failed",
            "error": f"[{error_type}] {error_msg}",
        })
    finally:
        # Clean up any orphaned pending interactions
        orphaned = [iid for iid, f in _pending_interactions.items() if not f.done()]
        for iid in orphaned:
            future = _pending_interactions.pop(iid, None)
            if future and not future.done():
                future.cancel()
