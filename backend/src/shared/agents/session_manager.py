"""Unified session manager for task and flow executions.

Uses Google ADK DatabaseSessionService backed by SQLite for persistent
session storage across application restarts.
"""

from __future__ import annotations

import os
from typing import Optional

from google.adk.sessions import DatabaseSessionService
from google.adk.sessions.session import Session

from src.shared.logging import get_logger

logger = get_logger("agents.session_manager")

APP_NAME = "agent_platform"
DEFAULT_USER = "user"


class SessionManager:
    """Maps context IDs (task_id or flow_id+agent_name) to ADK sessions.

    Usage:
        Tasks:  context_id = task_id
        Flows:  context_id = f"{flow_id}_{agent_name}"

    Sessions are persisted to SQLite via DatabaseSessionService.
    """

    def __init__(self, db_url: str = "sqlite+aiosqlite:///data/adk/sessions.db") -> None:
        # Ensure the directory for the SQLite file exists
        if "sqlite" in db_url:
            # Extract path from URL like "sqlite+aiosqlite:///data/adk/sessions.db"
            # Three slashes = relative, four = absolute
            path_part = db_url.split("///", 1)[-1] if "///" in db_url else ""
            if path_part:
                db_dir = os.path.dirname(path_part)
                if db_dir:
                    os.makedirs(db_dir, exist_ok=True)

        self._service = DatabaseSessionService(db_url=db_url)
        # context_id → session_id mapping (cache to avoid repeated lookups)
        self._session_ids: dict[str, str] = {}

    @property
    def service(self) -> DatabaseSessionService:
        """Expose underlying service for direct operations (list, delete)."""
        return self._service

    async def get_or_create(
        self,
        context_id: str,
        app_name: str = APP_NAME,
        user_id: str = DEFAULT_USER,
    ) -> tuple[DatabaseSessionService, str]:
        """Return (session_service, session_id) for the given context.

        Creates a new session on first call; returns the existing one on
        subsequent calls with the same context_id.
        """
        if context_id in self._session_ids:
            return self._service, self._session_ids[context_id]

        session = await self._service.create_session(
            app_name=app_name, user_id=user_id,
        )
        self._session_ids[context_id] = session.id

        logger.info("session_created", context_id=context_id, session_id=session.id)
        return self._service, session.id

    async def remove(self, context_id: str) -> None:
        """Delete session from DB and clear cache for a context."""
        session_id = self._session_ids.pop(context_id, None)
        if session_id:
            try:
                await self._service.delete_session(
                    app_name=APP_NAME, user_id=DEFAULT_USER, session_id=session_id,
                )
                logger.info("session_deleted", context_id=context_id, session_id=session_id)
            except Exception as exc:
                logger.warning("session_delete_failed", context_id=context_id, error=str(exc))

    def has_session(self, context_id: str) -> bool:
        return context_id in self._session_ids

    def get_session_id(self, context_id: str) -> Optional[str]:
        """Return session_id for a context_id, or None."""
        return self._session_ids.get(context_id)

    async def list_sessions(
        self, app_name: str = APP_NAME, user_id: Optional[str] = DEFAULT_USER,
    ) -> list[Session]:
        """List all sessions from the database."""
        resp = await self._service.list_sessions(app_name=app_name, user_id=user_id)
        return resp.sessions

    async def get_session(
        self, session_id: str, app_name: str = APP_NAME, user_id: str = DEFAULT_USER,
    ) -> Optional[Session]:
        """Get a single session by ID."""
        return await self._service.get_session(
            app_name=app_name, user_id=user_id, session_id=session_id,
        )

    async def delete_session(
        self, session_id: str, app_name: str = APP_NAME, user_id: str = DEFAULT_USER,
    ) -> None:
        """Delete a session by ID (also clears cache if present)."""
        # Clear from cache
        to_remove = [k for k, v in self._session_ids.items() if v == session_id]
        for k in to_remove:
            del self._session_ids[k]

        await self._service.delete_session(
            app_name=app_name, user_id=user_id, session_id=session_id,
        )
        logger.info("session_deleted_by_id", session_id=session_id)

    async def close(self) -> None:
        """Close the database connection."""
        await self._service.close()
