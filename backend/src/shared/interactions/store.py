"""SQLite-backed persistent store for interactions."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from src.shared.logging import get_logger
from src.shared.interactions.models import Interaction, InteractionStatus

logger = get_logger("interactions.store")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS interactions (
    interaction_id TEXT PRIMARY KEY,
    context_id     TEXT NOT NULL,
    context_type   TEXT NOT NULL,
    channel        TEXT NOT NULL DEFAULT 'web_ui',
    interaction_type TEXT NOT NULL DEFAULT 'free_text',
    prompt         TEXT NOT NULL DEFAULT '',
    options        TEXT,
    questions      TEXT,
    metadata       TEXT DEFAULT '{}',
    status         TEXT NOT NULL DEFAULT 'pending',
    response       TEXT,
    responder      TEXT DEFAULT '',
    created_at     TEXT NOT NULL,
    answered_at    TEXT,
    expires_at     TEXT
);

CREATE INDEX IF NOT EXISTS idx_interactions_status ON interactions(status);
CREATE INDEX IF NOT EXISTS idx_interactions_context ON interactions(context_id);
CREATE INDEX IF NOT EXISTS idx_interactions_channel ON interactions(channel);
"""


class InteractionStore:
    """Thread-safe SQLite store for interaction records."""

    def __init__(self, db_path: str | Path = "interactions.db"):
        self._db_path = str(db_path)
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.executescript(_SCHEMA)
        logger.info("store_initialized", db_path=self._db_path)

    def save(self, interaction: Interaction) -> None:
        """Insert or update an interaction record."""
        self._conn.execute(
            """
            INSERT OR REPLACE INTO interactions
                (interaction_id, context_id, context_type, channel,
                 interaction_type, prompt, options, questions, metadata,
                 status, response, responder, created_at, answered_at, expires_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                interaction.interaction_id,
                interaction.context_id,
                interaction.context_type,
                interaction.channel,
                interaction.interaction_type.value,
                interaction.prompt,
                json.dumps(interaction.options) if interaction.options else None,
                json.dumps(interaction.questions) if interaction.questions else None,
                json.dumps(interaction.metadata),
                interaction.status.value,
                json.dumps(interaction.response) if interaction.response is not None else None,
                interaction.responder,
                interaction.created_at.isoformat(),
                interaction.answered_at.isoformat() if interaction.answered_at else None,
                interaction.expires_at.isoformat() if interaction.expires_at else None,
            ),
        )
        self._conn.commit()

    def get(self, interaction_id: str) -> Interaction | None:
        """Fetch a single interaction by ID."""
        row = self._conn.execute(
            "SELECT * FROM interactions WHERE interaction_id = ?",
            (interaction_id,),
        ).fetchone()
        return self._row_to_model(row) if row else None

    def get_pending(
        self,
        channel: str | None = None,
        context_id: str | None = None,
    ) -> list[Interaction]:
        """List pending interactions, optionally filtered."""
        query = "SELECT * FROM interactions WHERE status = 'pending'"
        params: list[Any] = []
        if channel:
            query += " AND channel = ?"
            params.append(channel)
        if context_id:
            query += " AND context_id = ?"
            params.append(context_id)
        query += " ORDER BY created_at ASC"
        rows = self._conn.execute(query, params).fetchall()
        return [self._row_to_model(r) for r in rows]

    def update_status(
        self,
        interaction_id: str,
        status: InteractionStatus,
        response: Any = None,
        responder: str = "",
    ) -> bool:
        """Update the status (and optionally response) of an interaction."""
        answered_at = datetime.utcnow().isoformat() if status == InteractionStatus.answered else None
        resp_json = json.dumps(response) if response is not None else None
        cursor = self._conn.execute(
            """
            UPDATE interactions
            SET status = ?, response = ?, responder = ?, answered_at = ?
            WHERE interaction_id = ?
            """,
            (status.value, resp_json, responder, answered_at, interaction_id),
        )
        self._conn.commit()
        return cursor.rowcount > 0

    def expire_old(self) -> int:
        """Mark expired interactions based on expires_at."""
        now = datetime.utcnow().isoformat()
        cursor = self._conn.execute(
            """
            UPDATE interactions
            SET status = 'expired'
            WHERE status = 'pending' AND expires_at IS NOT NULL AND expires_at < ?
            """,
            (now,),
        )
        self._conn.commit()
        return cursor.rowcount

    def get_all(self, limit: int = 100) -> list[Interaction]:
        """Get recent interactions across all statuses."""
        rows = self._conn.execute(
            "SELECT * FROM interactions ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [self._row_to_model(r) for r in rows]

    def close(self) -> None:
        self._conn.close()

    # -- internal -----------------------------------------------------------

    @staticmethod
    def _row_to_model(row: sqlite3.Row) -> Interaction:
        d = dict(row)
        if d.get("options"):
            d["options"] = json.loads(d["options"])
        if d.get("questions"):
            d["questions"] = json.loads(d["questions"])
        if d.get("metadata"):
            d["metadata"] = json.loads(d["metadata"])
        if d.get("response"):
            d["response"] = json.loads(d["response"])
        if d.get("created_at"):
            d["created_at"] = datetime.fromisoformat(d["created_at"])
        if d.get("answered_at"):
            d["answered_at"] = datetime.fromisoformat(d["answered_at"])
        if d.get("expires_at"):
            d["expires_at"] = datetime.fromisoformat(d["expires_at"])
        return Interaction(**d)
