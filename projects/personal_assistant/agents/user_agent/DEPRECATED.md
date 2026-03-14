# DEPRECATED — user_agent

This agent has been replaced by platform-level user communication.

## What changed

- The root orchestrator now communicates with users directly via the `ask_user` builtin tool
- Channel capabilities (`text`, `a2ui`) are declared on channel adapters
- The appropriate communication guide (A2UI or text-only) is injected into the root agent's prompt based on the channel
- A2UI prompt knowledge was migrated to `backend/src/shared/interactions/prompts/a2ui_guide.md`

## Why

- Eliminates an unnecessary LLM roundtrip per user interaction
- Preserves domain context (the orchestrator knows why it's asking)
- Simplifies the agent topology

## Safe to delete

This directory can be safely deleted. No root agent references `user_agent` anymore.
