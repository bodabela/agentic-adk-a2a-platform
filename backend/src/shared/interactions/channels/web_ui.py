"""WebUI channel adapter — delivers interactions via SSE to the browser."""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

from src.shared.logging import get_logger
from src.shared.interactions.channels.base import ChannelAdapter

if TYPE_CHECKING:
    from src.shared.events.bus import EventBus
    from src.shared.interactions.models import Interaction

logger = get_logger("interactions.channels.web_ui")


class WebUIChannel(ChannelAdapter):
    """Sends interaction prompts to the browser via SSE events.

    This replaces the direct event_bus.emit() calls that were previously
    scattered across ask_user closures in the factory.
    """

    name = "web_ui"

    def __init__(self, event_bus: Any) -> None:
        self._event_bus: EventBus = event_bus

    async def send_question(self, interaction: Interaction) -> None:
        """Emit the appropriate SSE event for the frontend."""
        ctx_type = interaction.context_type
        event_name = (
            "task_input_required" if ctx_type == "task"
            else "flow_input_required"
        )
        id_field = "task_id" if ctx_type == "task" else "flow_id"

        payload: dict[str, Any] = {
            id_field: interaction.context_id,
            "interaction_id": interaction.interaction_id,
            "interaction_type": interaction.interaction_type.value,
            "prompt": interaction.prompt,
            "options": interaction.options,
            "channel": self.name,
        }
        if interaction.questions:
            payload["questions"] = interaction.questions
        if interaction.a2ui_payload:
            payload["a2ui_payload"] = interaction.a2ui_payload

        await self._event_bus.emit(event_name, payload)
        logger.info(
            "question_sent",
            interaction_id=interaction.interaction_id,
            event=event_name,
        )

    async def send_notification(self, message: str, context_id: str = "", metadata: dict | None = None) -> None:
        """Emit a task_notification SSE event for the frontend."""
        metadata = metadata or {}
        await self._event_bus.emit("task_notification", {
            "context_id": context_id,
            "message": message,
            "channel": self.name,
            "notification_type": metadata.get("notification_type", "notification"),
            **{k: v for k, v in metadata.items() if k in ("task_id", "status")},
        })
        logger.info("notification_sent", context_id=context_id)
