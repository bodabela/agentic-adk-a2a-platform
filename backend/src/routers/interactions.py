"""Interactions API — unified endpoint for submitting responses across all channels."""

import json
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from opentelemetry import trace
from pydantic import BaseModel, Field

from src.shared.logging import get_logger

logger = get_logger("api.interactions")

router = APIRouter()


class InteractionResponseBody(BaseModel):
    """Request body for submitting a response to a pending interaction."""

    interaction_id: str = Field(
        ...,
        description="ID of the pending interaction to respond to.",
        examples=["int-abc123"],
    )
    response: Any = Field(
        ...,
        description="The response value. Type depends on the interaction: free text (string), "
        "choice selection (string), or confirmation (boolean).",
        examples=["Yes, approve the deployment"],
    )
    responder: str = Field(
        default="",
        description="Optional identifier of who responded (e.g. username, email, channel user ID).",
        examples=["alice@example.com"],
    )


@router.post(
    "/respond",
    tags=["Client: Interactions"],
    summary="Submit an interaction response",
    description="Submit a user response to any pending human-in-the-loop interaction, regardless of channel. "
    "This is the **preferred unified endpoint** — it routes the response to the correct handler "
    "(task executor, flow engine, or interaction broker) automatically.\n\n"
    "Falls back to legacy task and flow interaction handlers for backward compatibility.",
    response_description="Confirmation with the interaction ID and routing info.",
)
async def submit_interaction_response(body: InteractionResponseBody, request: Request):
    # Set Langfuse trace input on the active (FastAPI root) span
    span = trace.get_current_span()
    if span and span.is_recording():
        trace_input = {"interaction_id": body.interaction_id, "response": str(body.response)[:500]}
        span.set_attribute("langfuse.trace.input", json.dumps(trace_input, ensure_ascii=False))

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


@router.get(
    "/pending",
    tags=["Client: Interactions"],
    summary="List pending interactions",
    description="Returns all interactions currently awaiting a human response. "
    "Optionally filter by communication channel or context ID (task/flow ID).",
    response_description="List of pending interactions with metadata.",
)
async def list_pending_interactions(
    request: Request,
    channel: str | None = None,
    context_id: str | None = None,
):
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


@router.get(
    "/",
    tags=["Admin: Interactions"],
    summary="List recent interactions",
    description="Returns recent interactions across all statuses (pending, answered, expired). "
    "Useful for audit trails and debugging interaction flows.",
    response_description="List of interactions with status and responder info.",
)
async def list_all_interactions(request: Request, limit: int = 50):
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


@router.get(
    "/channels",
    tags=["Client: Interactions"],
    summary="List available channels",
    description="Returns the names of all registered communication channels (e.g. `web_ui`, `teams`, `whatsapp`). "
    "A channel is available if it was configured and registered at startup.",
    response_description="List of available channel names.",
)
async def list_channels(request: Request):
    broker = request.app.state.interaction_broker
    return {"channels": broker.available_channels}


# ---------- Channel webhooks (static routes) ----------

_whatsapp_router = APIRouter(prefix="/channels/whatsapp")


@_whatsapp_router.post(
    "/webhook",
    tags=["Client: Channels"],
    summary="WhatsApp incoming webhook",
    description="Receives incoming WhatsApp messages via Twilio's webhook. "
    "The message is routed to the interaction broker which matches it to any pending interaction. "
    "Returns TwiML XML response.",
    response_description="Empty TwiML response.",
)
async def whatsapp_webhook(request: Request):
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
