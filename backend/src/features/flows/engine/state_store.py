"""State Store - persists flow execution state (in-memory, Redis later)."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class FlowStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    WAITING_INPUT = "waiting_input"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class FlowExecutionState:
    flow_id: str
    flow_name: str
    status: FlowStatus = FlowStatus.PENDING
    current_state: str = ""
    context_snapshot: dict[str, Any] = field(default_factory=dict)
    started_at: datetime | None = None
    updated_at: datetime | None = None
    completed_at: datetime | None = None
    error: str | None = None


class InMemoryStateStore:
    """In-memory state store for flow execution state."""

    def __init__(self):
        self._flows: dict[str, FlowExecutionState] = {}

    async def save(self, state: FlowExecutionState) -> None:
        state.updated_at = datetime.now()
        self._flows[state.flow_id] = state

    async def load(self, flow_id: str) -> FlowExecutionState | None:
        return self._flows.get(flow_id)

    async def list_active(self) -> list[FlowExecutionState]:
        return [
            s for s in self._flows.values() if s.status == FlowStatus.RUNNING
        ]

    async def list_all(self) -> list[FlowExecutionState]:
        return list(self._flows.values())
