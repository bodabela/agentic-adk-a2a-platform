"""Communication guide prompt fragments for channel-aware user interaction.

Based on channel capabilities, the appropriate guide is injected into
root agent prompts so they know how to communicate with the user.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

_DIR = Path(__file__).parent


@lru_cache(maxsize=4)
def _load(filename: str) -> str:
    return (_DIR / filename).read_text(encoding="utf-8")


def get_communication_guide(capabilities: frozenset[str]) -> str:
    """Return the communication guide appropriate for the channel's capabilities."""
    if "a2ui" in capabilities:
        return _load("a2ui_guide.md")
    return _load("text_only_guide.md")
