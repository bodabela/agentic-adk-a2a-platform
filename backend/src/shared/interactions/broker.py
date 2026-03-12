"""InteractionBroker — persistent, channel-agnostic interaction management.

This replaces the in-memory asyncio.Future dicts used in tasks.py and flows.py.
It persists interactions to SQLite, dispatches to channel adapters, and supports
both short-wait (in-memory event) and long-wait (agent suspension) patterns.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timedelta
from typing import Any, TYPE_CHECKING

from src.shared.logging import get_logger
from src.shared.interactions.models import (
    AgentSuspended,
    Interaction,
    InteractionStatus,
    InteractionType,
)
from src.shared.interactions.store import InteractionStore

if TYPE_CHECKING:
    from src.shared.interactions.channels.base import ChannelAdapter

logger = get_logger("interactions.broker")


class InteractionBroker:
    """Central hub for all user interactions across all channels.

    Lifecycle of an interaction:
    1. Agent calls ask_user → broker.create_interaction()
    2. Broker persists to DB, dispatches to channel adapter
    3. Short wait: asyncio.Event with timeout
    4. If answered in time → return response to agent
    5. If timeout → raise AgentSuspended, agent state preserved in session
    6. Later: external webhook delivers response → broker.submit_response()
    7. Broker triggers agent resume via callback
    """

    def __init__(
        self,
        store: InteractionStore,
        default_channel: str = "web_ui",
    ):
        self._store = store
        self._default_channel = default_channel
        self._channels: dict[str, ChannelAdapter] = {}
        # In-memory waiters for short-lived interactions
        self._waiters: dict[str, asyncio.Event] = {}
        self._responses: dict[str, Any] = {}
        # Callback for agent resume (set by startup code)
        self._resume_callback: Any = None

    # -- Channel management --------------------------------------------------

    def register_channel(self, adapter: ChannelAdapter) -> None:
        """Register a channel adapter."""
        self._channels[adapter.name] = adapter
        logger.info("channel_registered", channel=adapter.name)

    def get_channel(self, name: str) -> ChannelAdapter | None:
        return self._channels.get(name)

    @property
    def available_channels(self) -> list[str]:
        return list(self._channels.keys())

    def set_resume_callback(self, callback: Any) -> None:
        """Set the callback to invoke when a suspended agent should resume."""
        self._resume_callback = callback

    # -- Create interaction --------------------------------------------------

    async def create_interaction(
        self,
        context_id: str,
        context_type: str = "task",
        interaction_type: str = "free_text",
        prompt: str = "",
        options: list[dict[str, str]] | None = None,
        questions: list[dict[str, Any]] | None = None,
        channel: str | None = None,
        ttl_hours: int = 72,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Create and dispatch a new interaction. Returns interaction_id."""
        interaction_id = str(uuid.uuid4())
        channel = channel or self._default_channel

        interaction = Interaction(
            interaction_id=interaction_id,
            context_id=context_id,
            context_type=context_type,
            channel=channel,
            interaction_type=InteractionType(interaction_type),
            prompt=prompt,
            options=options,
            questions=questions,
            metadata=metadata or {},
            status=InteractionStatus.pending,
            created_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(hours=ttl_hours),
        )

        # Persist
        self._store.save(interaction)

        # Set up in-memory waiter
        event = asyncio.Event()
        self._waiters[interaction_id] = event

        # Dispatch to channel
        adapter = self._channels.get(channel)
        if adapter:
            try:
                await adapter.send_question(interaction)
            except Exception as e:
                logger.error("channel_dispatch_failed", channel=channel, error=str(e))
                # Fallback to web_ui if available and different
                if channel != "web_ui" and "web_ui" in self._channels:
                    logger.info("channel_fallback", from_channel=channel, to="web_ui")
                    await self._channels["web_ui"].send_question(interaction)
        else:
            logger.warning("no_channel_adapter", channel=channel)

        logger.info(
            "interaction_created",
            interaction_id=interaction_id,
            context_id=context_id,
            channel=channel,
            interaction_type=interaction_type,
        )
        return interaction_id

    # -- Wait for response ---------------------------------------------------

    async def wait_for_response(
        self,
        interaction_id: str,
        timeout: float = 300,
        suspend_on_timeout: bool = False,
        context_id: str = "",
    ) -> str:
        """Wait for a response to an interaction.

        Args:
            interaction_id: The interaction to wait for.
            timeout: Seconds to wait before timing out.
            suspend_on_timeout: If True, raise AgentSuspended on timeout
                                instead of returning a timeout message.
            context_id: Required if suspend_on_timeout is True.

        Returns:
            The user's response as a string.

        Raises:
            AgentSuspended: If suspend_on_timeout is True and no response
                           arrives within the timeout.
        """
        event = self._waiters.get(interaction_id)
        if not event:
            # Check if already answered in DB
            interaction = self._store.get(interaction_id)
            if interaction and interaction.status == InteractionStatus.answered:
                return self._format_response(interaction.response)
            event = asyncio.Event()
            self._waiters[interaction_id] = event

        try:
            await asyncio.wait_for(event.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            if suspend_on_timeout:
                # Mark as suspended in DB
                self._store.update_status(
                    interaction_id, InteractionStatus.suspended
                )
                self._waiters.pop(interaction_id, None)
                logger.info(
                    "agent_suspending",
                    interaction_id=interaction_id,
                    context_id=context_id,
                )
                raise AgentSuspended(
                    interaction_id=interaction_id,
                    context_id=context_id,
                )
            else:
                self._waiters.pop(interaction_id, None)
                logger.warning("interaction_timeout", interaction_id=interaction_id)
                return "The user did not respond within the timeout period."

        # Response arrived
        self._waiters.pop(interaction_id, None)
        response = self._responses.pop(interaction_id, None)
        if response is None:
            # Fetch from DB
            interaction = self._store.get(interaction_id)
            response = interaction.response if interaction else ""
        return self._format_response(response)

    # -- Submit response -----------------------------------------------------

    async def submit_response(
        self,
        interaction_id: str,
        response: Any,
        responder: str = "",
    ) -> bool:
        """Submit a response to a pending/suspended interaction.

        Returns True if a matching interaction was found and updated.
        """
        interaction = self._store.get(interaction_id)
        if not interaction:
            logger.warning("response_no_interaction", interaction_id=interaction_id)
            return False

        if interaction.status not in (
            InteractionStatus.pending,
            InteractionStatus.suspended,
        ):
            logger.warning(
                "response_wrong_status",
                interaction_id=interaction_id,
                status=interaction.status,
            )
            return False

        was_suspended = interaction.status == InteractionStatus.suspended

        # Update DB
        self._store.update_status(
            interaction_id,
            InteractionStatus.answered,
            response=response,
            responder=responder,
        )

        # Notify in-memory waiter (if agent is still waiting)
        self._responses[interaction_id] = response
        event = self._waiters.get(interaction_id)
        if event:
            event.set()

        logger.info(
            "response_submitted",
            interaction_id=interaction_id,
            responder=responder,
            was_suspended=was_suspended,
        )

        # If agent was suspended, trigger resume
        if was_suspended and self._resume_callback:
            try:
                await self._resume_callback(interaction)
            except Exception as e:
                logger.error("resume_callback_failed", error=str(e))

        return True

    # -- Query ---------------------------------------------------------------

    def get_pending(
        self, channel: str | None = None, context_id: str | None = None
    ) -> list[Interaction]:
        """Get all pending interactions, optionally filtered."""
        return self._store.get_pending(channel=channel, context_id=context_id)

    def get_interaction(self, interaction_id: str) -> Interaction | None:
        return self._store.get(interaction_id)

    def get_all(self, limit: int = 100) -> list[Interaction]:
        return self._store.get_all(limit=limit)

    def expire_stale(self) -> int:
        """Expire interactions that have passed their TTL."""
        return self._store.expire_old()

    # -- Notifications -------------------------------------------------------

    async def notify_channel(
        self,
        channel: str,
        message: str,
        context_id: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        """Send a one-way notification to a channel (no response expected).

        Returns True if the notification was sent successfully.
        """
        adapter = self._channels.get(channel)
        if not adapter:
            logger.warning("notify_no_channel", channel=channel)
            return False
        try:
            await adapter.send_notification(message, context_id=context_id, metadata=metadata)
            logger.info("notification_sent", channel=channel, context_id=context_id)
            return True
        except Exception as e:
            logger.error("notification_failed", channel=channel, error=str(e))
            return False

    # -- Helpers -------------------------------------------------------------

    @staticmethod
    def _format_response(response: Any) -> str:
        if response is None:
            return ""
        if isinstance(response, str):
            return response
        import json
        return json.dumps(response)
