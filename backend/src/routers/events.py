"""Server-Sent Events endpoint for real-time updates."""

import asyncio
import json

from fastapi import APIRouter, Request
from sse_starlette.sse import EventSourceResponse

router = APIRouter()


@router.get(
    "/stream",
    tags=["Client: Events"],
    summary="Real-time event stream (SSE)",
    description="Opens a Server-Sent Events connection that streams platform events in real time. "
    "Event types include:\n\n"
    "- **task_submitted** / **task_completed** / **task_failed** — task lifecycle\n"
    "- **flow_state_entered** / **flow_completed** — flow state transitions\n"
    "- **llm_call** / **cost_update** — LLM usage and cost tracking\n"
    "- **interaction_requested** — human-in-the-loop prompt\n"
    "- **agent_message** — agent output chunks\n\n"
    "A `ping` event is sent every 30 seconds to keep the connection alive. "
    "Each event's `data` field is a JSON-encoded object.",
    response_description="SSE stream of JSON-encoded platform events.",
)
async def event_stream(request: Request):
    event_bus = request.app.state.event_bus

    async def generate():
        queue: asyncio.Queue = asyncio.Queue(maxsize=100)
        unsubscribe = event_bus.subscribe(queue)
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=30.0)
                    yield {
                        "event": event.get("type", "message"),
                        "data": json.dumps(event, default=str),
                    }
                except asyncio.TimeoutError:
                    yield {"event": "ping", "data": ""}
        finally:
            unsubscribe()

    return EventSourceResponse(generate())
