"""Pydantic models for the interaction system."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class InteractionStatus(str, Enum):
    pending = "pending"
    answered = "answered"
    expired = "expired"
    cancelled = "cancelled"
    suspended = "suspended"  # agent suspended, waiting for long-lived response


class InteractionType(str, Enum):
    free_text = "free_text"
    choice = "choice"
    confirmation = "confirmation"
    form = "form"
    multi_question = "multi_question"
    a2ui = "a2ui"  # Rich UI via A2UI declarative JSON


class Interaction(BaseModel):
    """A single user-facing interaction (question, approval, etc.)."""

    interaction_id: str
    context_id: str  # task_id or flow_id
    context_type: str  # "task" | "flow"
    channel: str = "web_ui"  # target delivery channel
    interaction_type: InteractionType = InteractionType.free_text
    prompt: str = ""
    options: list[dict[str, str]] | None = None  # for choice type
    questions: list[dict[str, Any]] | None = None  # for form type
    a2ui_payload: list[dict[str, Any]] | None = None  # A2UI declarative UI JSON
    metadata: dict[str, Any] = Field(default_factory=dict)
    status: InteractionStatus = InteractionStatus.pending
    response: Any = None
    responder: str = ""
    created_at: datetime = Field(default_factory=datetime.utcnow)
    answered_at: datetime | None = None
    expires_at: datetime | None = None


class AgentSuspended(Exception):
    """Raised when an agent must suspend to wait for a long-lived response."""

    def __init__(self, interaction_id: str, context_id: str, message: str = ""):
        self.interaction_id = interaction_id
        self.context_id = context_id
        self.message = message or f"Agent suspended waiting for interaction {interaction_id}"
        super().__init__(self.message)
