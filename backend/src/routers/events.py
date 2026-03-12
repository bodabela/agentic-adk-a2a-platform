"""Server-Sent Events endpoint for real-time updates."""

import asyncio
import json

from fastapi import APIRouter, Request
from sse_starlette.sse import EventSourceResponse

router = APIRouter()


@router.get("/stream")
async def event_stream(request: Request):
    """SSE endpoint for real-time task and flow events."""
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
