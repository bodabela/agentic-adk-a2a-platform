"""Session management API — list, stop, and delete ADK sessions."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from src.features.tasks.executor import running_tasks
from src.shared.logging import get_logger

logger = get_logger("sessions")

router = APIRouter()


@router.get(
    "/",
    tags=["Admin: Sessions"],
    summary="List all sessions",
    description="Returns all persisted ADK sessions with derived status. Sessions are sorted with "
    "running sessions first, then by last update time (descending). "
    "Status is derived from whether an asyncio task is still active for the session.",
    response_description="List of sessions with status, event counts, and timestamps.",
)
async def list_sessions(request: Request):
    session_manager = request.app.state.session_manager
    sessions = await session_manager.list_sessions()

    # Build a set of session_ids that have a running asyncio task
    running_session_ids: set[str] = set()
    for task_id, atask in running_tasks.items():
        if not atask.done():
            sid = session_manager.get_session_id(task_id)
            if sid:
                running_session_ids.add(sid)

    result = []
    for s in sessions:
        is_running = s.id in running_session_ids
        # Derive status from running task presence
        status = "running" if is_running else "completed"

        result.append({
            "session_id": s.id,
            "app_name": s.app_name,
            "user_id": s.user_id,
            "status": status,
            "create_time": s.events[0].timestamp if s.events else None,
            "update_time": s.last_update_time,
            "event_count": len(s.events),
        })

    # Sort: running first, then by update_time descending
    result.sort(key=lambda x: (x["status"] != "running", -(x["update_time"] or 0)))
    return {"sessions": result}


@router.post(
    "/{session_id}/stop",
    tags=["Admin: Sessions"],
    summary="Stop a running session",
    description="Cancels the asyncio task associated with a running session. The session's ADK state "
    "is preserved in the database — only the execution is stopped. "
    "Returns 404 if no running task is found, or 409 if the task already finished.",
    response_description="Confirmation with session and task IDs.",
)
async def stop_session(session_id: str, request: Request):
    session_manager = request.app.state.session_manager

    # Find the task_id that maps to this session_id
    target_task_id = None
    for task_id, atask in running_tasks.items():
        sid = session_manager.get_session_id(task_id)
        if sid == session_id and not atask.done():
            target_task_id = task_id
            break

    if not target_task_id:
        raise HTTPException(status_code=404, detail="No running task found for this session")

    atask = running_tasks.get(target_task_id)
    if atask and not atask.done():
        atask.cancel()
        logger.info("session_stop_requested", session_id=session_id, task_id=target_task_id)
        return {"status": "stopping", "session_id": session_id, "task_id": target_task_id}

    raise HTTPException(status_code=409, detail="Task already finished")


@router.delete(
    "/{session_id}",
    tags=["Admin: Sessions"],
    summary="Delete a session",
    description="Permanently removes a completed or failed session from the database. "
    "Running sessions cannot be deleted — stop them first using the stop endpoint. "
    "All session events and state are removed.",
    response_description="Confirmation with the deleted session ID.",
)
async def delete_session(session_id: str, request: Request):
    session_manager = request.app.state.session_manager

    # Don't allow deleting running sessions
    for task_id, atask in running_tasks.items():
        sid = session_manager.get_session_id(task_id)
        if sid == session_id and not atask.done():
            raise HTTPException(
                status_code=409,
                detail="Cannot delete a running session. Stop it first.",
            )

    try:
        await session_manager.delete_session(session_id)
        logger.info("session_deleted", session_id=session_id)
        return {"status": "deleted", "session_id": session_id}
    except Exception as exc:
        raise HTTPException(status_code=404, detail=f"Session not found: {exc}")
