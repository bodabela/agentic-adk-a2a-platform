"""In-memory async event bus for broadcasting events."""

import asyncio
from typing import Callable


class EventBus:
    def __init__(self):
        self._subscribers: list[asyncio.Queue] = []

    def subscribe(self, queue: asyncio.Queue) -> Callable:
        """Subscribe to events. Returns unsubscribe function."""
        self._subscribers.append(queue)

        def unsubscribe():
            if queue in self._subscribers:
                self._subscribers.remove(queue)

        return unsubscribe

    async def emit(self, event_type: str, data: dict) -> None:
        """Broadcast an event to all subscribers."""
        event = {"type": event_type, **data}
        for queue in self._subscribers:
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                pass  # Drop event if subscriber queue is full

    async def shutdown(self) -> None:
        self._subscribers.clear()
