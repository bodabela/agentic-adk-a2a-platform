"""Task management API."""

import asyncio
import traceback
import uuid

from fastapi import APIRouter, Request
from pydantic import BaseModel

from src.common.logging import get_logger

logger = get_logger("tasks")

router = APIRouter()


class TaskSubmission(BaseModel):
    description: str
    context: dict | None = None


class TaskResponse(BaseModel):
    task_id: str
    status: str
    description: str


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

        async for event in runner.run_async(
            user_id="user", session_id=session.id, new_message=user_message
        ):
            event_type = type(event).__name__

            # Extract meaningful details from the ADK event
            author = getattr(event, "author", None) or ""
            content = getattr(event, "content", None)
            text_parts = []
            if content and hasattr(content, "parts"):
                for part in content.parts:
                    if hasattr(part, "text") and part.text:
                        text_parts.append(part.text)
                    elif hasattr(part, "function_call") and part.function_call:
                        fc = part.function_call
                        text_parts.append(f"call:{fc.name}({dict(fc.args) if fc.args else {}})")
                    elif hasattr(part, "function_response") and part.function_response:
                        fr = part.function_response
                        text_parts.append(f"result:{fr.name}={fr.response}")

            summary = " | ".join(text_parts) if text_parts else str(event)

            logger.debug(
                "task_event",
                task_id=task_id,
                event_type=event_type,
                author=author,
                summary=summary[:500],
            )
            await event_bus.emit("task_event", {
                "task_id": task_id,
                "event_type": event_type,
                "author": author,
                "summary": summary[:1000],
            })

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
