"""Langfuse SDK initialization for agent tracing.

Uses the Langfuse Python SDK's native ``@observe()`` decorator approach.
The SDK automatically handles OTLP export with proper observation types
(AGENT, TOOL, GENERATION) that enable the Agent Graph visualization.

This module initializes the Langfuse client and exposes ``langfuse_observe``
for use in ADK callbacks.
"""

from __future__ import annotations

import logging

logger = logging.getLogger("tracing.langfuse")

_langfuse_initialized = False


def init_langfuse(public_key: str, secret_key: str, host: str) -> None:
    """Initialize the Langfuse SDK with OTLP auto-export enabled."""
    global _langfuse_initialized
    try:
        from langfuse import Langfuse
        Langfuse(
            public_key=public_key,
            secret_key=secret_key,
            host=host,
        )
        _langfuse_initialized = True
        logger.info("Langfuse SDK initialized (OTLP auto-export): %s", host)
    except ImportError:
        logger.warning("langfuse package not installed — Langfuse disabled")
    except Exception as exc:
        logger.warning("Langfuse SDK init failed: %s", exc)


def is_langfuse_initialized() -> bool:
    return _langfuse_initialized
