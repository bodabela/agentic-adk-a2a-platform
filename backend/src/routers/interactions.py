"""Interactions API — unified endpoint for submitting responses across all channels."""

from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from src.shared.logging import get_logger

logger = get_logger("api.interactions")

router = APIRouter()


class InteractionResponseBody(BaseModel):
    interaction_id: str
    response: Any
    responder: str = ""


@router.post("/respond")
async def submit_interaction_response(body: InteractionResponseBody, request: Request):
    """Submit a response to any pending interaction (from any channel).

    This is the unified endpoint that replaces the separate
    /api/tasks/interact and /api/flows/interact endpoints.
    Both old endpoints still work for backward compatibility,
    but new code should use this one.
    """
    broker = request.app.state.interaction_broker

    success = await broker.submit_response(
        interaction_id=body.interaction_id,
        response=body.response,
        responder=body.responder,
    )
    if not success:
        # Fallback: try legacy pending_interactions dicts
        from src.features.tasks.executor import pending_interactions as task_pending
        future = task_pending.get(body.interaction_id)
        if future and not future.done():
            future.set_result(body.response)
            return {"status": "ok", "interaction_id": body.interaction_id, "via": "legacy_task"}

        # Fallback: try active flow engines (legacy flow path without broker)
        from src.routers.flows import _active_engines
        for engine in _active_engines.values():
            if await engine.submit_interaction_response(body.interaction_id, body.response):
                return {"status": "ok", "interaction_id": body.interaction_id, "via": "legacy_flow"}

        raise HTTPException(
            status_code=404,
            detail=f"No pending interaction found: {body.interaction_id}",
        )

    return {"status": "ok", "interaction_id": body.interaction_id}


@router.get("/pending")
async def list_pending_interactions(
    request: Request,
    channel: str | None = None,
    context_id: str | None = None,
):
    """List all pending interactions, optionally filtered by channel or context."""
    broker = request.app.state.interaction_broker
    pending = broker.get_pending(channel=channel, context_id=context_id)
    return {
        "interactions": [
            {
                "interaction_id": i.interaction_id,
                "context_id": i.context_id,
                "context_type": i.context_type,
                "channel": i.channel,
                "interaction_type": i.interaction_type.value,
                "prompt": i.prompt,
                "options": i.options,
                "status": i.status.value,
                "created_at": i.created_at.isoformat(),
                "expires_at": i.expires_at.isoformat() if i.expires_at else None,
            }
            for i in pending
        ],
    }


@router.get("/")
async def list_all_interactions(request: Request, limit: int = 50):
    """List recent interactions across all statuses."""
    broker = request.app.state.interaction_broker
    interactions = broker.get_all(limit=limit)
    return {
        "interactions": [
            {
                "interaction_id": i.interaction_id,
                "context_id": i.context_id,
                "context_type": i.context_type,
                "channel": i.channel,
                "interaction_type": i.interaction_type.value,
                "prompt": i.prompt,
                "status": i.status.value,
                "responder": i.responder,
                "created_at": i.created_at.isoformat(),
                "answered_at": i.answered_at.isoformat() if i.answered_at else None,
            }
            for i in interactions
        ],
    }


@router.get("/channels")
async def list_channels(request: Request):
    """List available communication channels."""
    broker = request.app.state.interaction_broker
    return {"channels": broker.available_channels}


# ---------- Channel webhooks (static routes) ----------

_whatsapp_router = APIRouter(prefix="/channels/whatsapp", tags=["channels-whatsapp"])


@_whatsapp_router.post("/webhook")
async def whatsapp_webhook(request: Request):
    """Receive incoming WhatsApp messages via Twilio."""
    broker = getattr(request.app.state, "interaction_broker", None)
    channel = broker.get_channel("whatsapp") if broker else None
    if not channel:
        from fastapi.responses import Response
        return Response(content="<Response></Response>", media_type="application/xml")

    form = await request.form()
    await channel._handle_incoming(dict(form))

    from fastapi.responses import Response
    return Response(
        content="<Response></Response>",
        media_type="application/xml",
        status_code=200,
    )
