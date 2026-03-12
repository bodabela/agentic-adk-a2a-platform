"""Microsoft Teams channel adapter.

Uses the Bot Framework REST API to send/receive messages.
Requires: pip install botbuilder-core botbuilder-schema
(or lightweight HTTP calls to the Bot Framework connector API).

Configuration (in channels.yaml or env vars):
    teams:
        enabled: true
        app_id: "..."
        app_password: "..."
        default_conversation_id: "..."  # for proactive messages
"""

from __future__ import annotations

import json
from typing import Any, TYPE_CHECKING

from src.shared.logging import get_logger
from src.shared.interactions.channels.base import ChannelAdapter

if TYPE_CHECKING:
    from fastapi import FastAPI, Request
    from src.shared.interactions.broker import InteractionBroker
    from src.shared.interactions.models import Interaction

logger = get_logger("interactions.channels.teams")


class TeamsChannel(ChannelAdapter):
    """Microsoft Teams Bot Framework integration."""

    name = "teams"

    def __init__(
        self,
        app_id: str = "",
        app_password: str = "",
        service_url: str = "https://smba.trafficmanager.net/emea/",
        default_conversation_id: str = "",
        broker: InteractionBroker | None = None,
    ) -> None:
        self._app_id = app_id
        self._app_password = app_password
        self._service_url = service_url
        self._default_conversation_id = default_conversation_id
        self._broker = broker
        self._token: str | None = None
        self._token_expires: float = 0

    async def send_question(self, interaction: Interaction) -> None:
        """Send an Adaptive Card or text message to Teams."""
        conversation_id = (
            interaction.metadata.get("teams_conversation_id")
            or self._default_conversation_id
        )
        if not conversation_id:
            logger.error("teams_no_conversation", interaction_id=interaction.interaction_id)
            return

        token = await self._get_token()
        if not token:
            logger.error("teams_no_token", interaction_id=interaction.interaction_id)
            return

        # Build Adaptive Card for rich interaction
        card = self._build_adaptive_card(interaction)
        payload = {
            "type": "message",
            "attachments": [
                {
                    "contentType": "application/vnd.microsoft.card.adaptive",
                    "content": card,
                }
            ],
        }

        url = f"{self._service_url}v3/conversations/{conversation_id}/activities"
        import aiohttp
        async with aiohttp.ClientSession() as session:
            async with session.post(
                url,
                json=payload,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
            ) as resp:
                if resp.status < 300:
                    logger.info("teams_message_sent", interaction_id=interaction.interaction_id)
                else:
                    body = await resp.text()
                    logger.error("teams_send_failed", status=resp.status, body=body[:500])

    async def setup_routes(self, app: FastAPI) -> None:
        """Register the Teams webhook endpoint."""
        from fastapi import APIRouter, Request
        router = APIRouter()

        @router.post("/api/channels/teams/webhook")
        async def teams_webhook(request: Request):
            """Receive incoming messages/card actions from Teams."""
            body = await request.json()
            return await self._handle_incoming(body)

        app.include_router(router, tags=["channels-teams"])
        logger.info("teams_webhook_registered")

    async def _handle_incoming(self, activity: dict) -> dict:
        """Process an incoming Bot Framework activity."""
        activity_type = activity.get("type", "")

        if activity_type == "message":
            text = activity.get("text", "").strip()
            from_user = activity.get("from", {}).get("name", "teams_user")

            # Check for pending interaction response
            if self._broker:
                pending = self._broker.get_pending(channel="teams")
                if pending:
                    # Route response to first pending interaction
                    interaction = pending[0]
                    await self._broker.submit_response(
                        interaction.interaction_id,
                        text,
                        responder=from_user,
                    )
                    return {"status": "response_accepted"}

            # No pending interaction — could create a new task
            logger.info("teams_new_message", text=text[:200], from_user=from_user)
            return {"status": "received"}

        elif activity_type == "invoke":
            # Adaptive Card action
            value = activity.get("value", {})
            interaction_id = value.get("interaction_id")
            response = value.get("response")

            if interaction_id and response and self._broker:
                from_user = activity.get("from", {}).get("name", "teams_user")
                await self._broker.submit_response(
                    interaction_id, response, responder=from_user
                )
                return {
                    "status": 200,
                    "body": {"type": "message", "value": "Response received!"},
                }

        return {"status": "ignored"}

    def _build_adaptive_card(self, interaction: Interaction) -> dict:
        """Build a Teams Adaptive Card from the interaction."""
        body: list[dict] = [
            {
                "type": "TextBlock",
                "text": interaction.prompt,
                "wrap": True,
                "size": "Medium",
            },
        ]

        actions: list[dict] = []
        if interaction.options:
            for opt in interaction.options:
                actions.append({
                    "type": "Action.Submit",
                    "title": opt.get("label", opt.get("id", "")),
                    "data": {
                        "interaction_id": interaction.interaction_id,
                        "response": opt.get("id", opt.get("label", "")),
                    },
                })
        else:
            # Free text: input field + submit
            body.append({
                "type": "Input.Text",
                "id": "user_response",
                "placeholder": "Type your response...",
                "isMultiline": True,
            })
            actions.append({
                "type": "Action.Submit",
                "title": "Submit",
                "data": {"interaction_id": interaction.interaction_id},
            })

        return {
            "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
            "type": "AdaptiveCard",
            "version": "1.4",
            "body": body,
            "actions": actions,
        }

    async def _get_token(self) -> str | None:
        """Get or refresh Bot Framework OAuth token."""
        import time
        if self._token and time.time() < self._token_expires:
            return self._token

        if not self._app_id or not self._app_password:
            return None

        import aiohttp
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://login.microsoftonline.com/botframework.com/oauth2/v2.0/token",
                data={
                    "grant_type": "client_credentials",
                    "client_id": self._app_id,
                    "client_secret": self._app_password,
                    "scope": "https://api.botframework.com/.default",
                },
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    self._token = data["access_token"]
                    self._token_expires = time.time() + data.get("expires_in", 3500) - 60
                    return self._token
                else:
                    logger.error("teams_token_failed", status=resp.status)
                    return None
