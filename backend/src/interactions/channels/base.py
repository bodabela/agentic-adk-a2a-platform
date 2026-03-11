"""Abstract base for channel adapters."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi import FastAPI
    from src.interactions.models import Interaction


class ChannelAdapter(ABC):
    """Base class for messaging channel integrations.

    Each adapter knows how to:
    - Send a question/prompt to its channel
    - Receive responses via webhooks or polling
    - Format messages for the specific platform
    """

    name: str  # channel identifier: "web_ui", "teams", "whatsapp", etc.

    @abstractmethod
    async def send_question(self, interaction: Interaction) -> None:
        """Deliver the interaction prompt to the user through this channel."""

    async def send_notification(self, message: str, context_id: str = "", metadata: dict | None = None) -> None:
        """Send a one-way notification (no response expected).

        Used for delivering task results, status updates, etc.
        Override in subclasses that support outbound messages.
        """

    async def setup_routes(self, app: FastAPI) -> None:
        """Register any webhook/callback routes needed by this channel.

        Override in subclasses that receive inbound messages via HTTP.
        """

    async def startup(self) -> None:
        """Called once during application startup. Override for init logic."""

    async def shutdown(self) -> None:
        """Called during application shutdown. Override for cleanup."""

    def format_prompt(self, interaction: Interaction) -> str:
        """Format the interaction into a human-readable message.

        Override for channel-specific formatting (Adaptive Cards, etc.).
        """
        parts = [interaction.prompt]
        if interaction.options:
            options_text = "\n".join(
                f"  {i+1}. {opt.get('label', opt.get('id', ''))}"
                for i, opt in enumerate(interaction.options)
            )
            parts.append(f"\nOptions:\n{options_text}")
        return "\n".join(parts)
