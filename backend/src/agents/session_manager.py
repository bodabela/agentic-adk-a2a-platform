"""Unified session manager for task and flow executions."""

from __future__ import annotations

from google.adk.sessions import InMemorySessionService

from src.common.logging import get_logger

logger = get_logger("agents.session_manager")


class SessionManager:
    """Maps context IDs (task_id or flow_id+agent_name) to ADK sessions.

    Usage:
        Tasks:  context_id = task_id
        Flows:  context_id = f"{flow_id}_{agent_name}"

    Sessions are kept in memory. Designed to be replaceable with a persistent
    store later.
    """

    def __init__(self) -> None:
        self._services: dict[str, InMemorySessionService] = {}
        self._session_ids: dict[str, str] = {}

    async def get_or_create(
        self,
        context_id: str,
        app_name: str = "agent_platform",
        user_id: str = "user",
    ) -> tuple[InMemorySessionService, str]:
        """Return (session_service, session_id) for the given context.

        Creates a new session on first call; returns the existing one on
        subsequent calls with the same context_id.
        """
        if context_id in self._session_ids:
            return self._services[context_id], self._session_ids[context_id]

        service = InMemorySessionService()
        session = await service.create_session(
            app_name=app_name, user_id=user_id,
        )
        self._services[context_id] = service
        self._session_ids[context_id] = session.id

        logger.info("session_created", context_id=context_id, session_id=session.id)
        return service, session.id

    def remove(self, context_id: str) -> None:
        """Remove session state for a context (e.g. after task completes)."""
        self._services.pop(context_id, None)
        self._session_ids.pop(context_id, None)

    def has_session(self, context_id: str) -> bool:
        return context_id in self._session_ids
