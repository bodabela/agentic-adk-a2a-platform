"""WhatsApp channel adapter via Twilio.

Configuration (in channels.yaml or env vars):
    whatsapp:
        enabled: true
        provider: "twilio"
        account_sid: "..."
        auth_token: "..."
        from_number: "+14155238886"
        allowed_numbers:
            - "+36301234567"
"""

from __future__ import annotations

import hashlib
import hmac
from typing import Any, TYPE_CHECKING
from urllib.parse import urlencode

from src.common.logging import get_logger
from src.interactions.channels.base import ChannelAdapter

if TYPE_CHECKING:
    from fastapi import FastAPI
    from src.interactions.broker import InteractionBroker
    from src.interactions.models import Interaction

logger = get_logger("interactions.channels.whatsapp")


class WhatsAppChannel(ChannelAdapter):
    """WhatsApp Business integration via Twilio API."""

    name = "whatsapp"

    def __init__(
        self,
        account_sid: str = "",
        auth_token: str = "",
        from_number: str = "",
        allowed_numbers: list[str] | None = None,
        broker: InteractionBroker | None = None,
    ) -> None:
        self._account_sid = account_sid
        self._auth_token = auth_token
        self._from_number = from_number
        self._allowed_numbers = set(allowed_numbers or [])
        self._broker = broker

    async def send_notification(self, message: str, context_id: str = "", metadata: dict | None = None) -> None:
        """Send a one-way notification via WhatsApp."""
        metadata = metadata or {}
        to_number = metadata.get("phone")
        # Truncate for WhatsApp 4096 char limit
        if len(message) > 4000:
            message = message[:3997] + "..."

        if to_number:
            await self._send_text(to_number, message)
        elif self._allowed_numbers:
            for number in self._allowed_numbers:
                await self._send_text(number, message)
        else:
            logger.error("whatsapp_notification_no_recipient", context_id=context_id)

    async def _send_text(self, to_number: str, body: str) -> None:
        """Send a plain text WhatsApp message."""
        if not self._account_sid or not self._auth_token:
            logger.error("whatsapp_not_configured")
            return

        import aiohttp
        import base64
        url = (
            f"https://api.twilio.com/2010-04-01/Accounts/"
            f"{self._account_sid}/Messages.json"
        )
        auth = base64.b64encode(
            f"{self._account_sid}:{self._auth_token}".encode()
        ).decode()

        async with aiohttp.ClientSession() as session:
            async with session.post(
                url,
                data={
                    "From": f"whatsapp:{self._from_number}",
                    "To": f"whatsapp:{to_number}",
                    "Body": body,
                },
                headers={"Authorization": f"Basic {auth}"},
            ) as resp:
                if resp.status < 300:
                    logger.info("whatsapp_notification_sent", to=to_number)
                else:
                    resp_body = await resp.text()
                    logger.error("whatsapp_notification_failed", status=resp.status, body=resp_body[:500])

    async def send_question(self, interaction: Interaction) -> None:
        """Send a WhatsApp message via Twilio."""
        to_number = interaction.metadata.get("phone")
        if not to_number:
            # Fallback: send to all allowed numbers
            if self._allowed_numbers:
                for number in self._allowed_numbers:
                    await self._send_message(number, interaction)
            else:
                logger.error("whatsapp_no_recipient", interaction_id=interaction.interaction_id)
            return

        await self._send_message(to_number, interaction)

    async def _send_message(self, to_number: str, interaction: Interaction) -> None:
        """Send a single WhatsApp message."""
        if not self._account_sid or not self._auth_token:
            logger.error("whatsapp_not_configured")
            return

        body = self._format_message(interaction)

        import aiohttp
        import base64
        url = (
            f"https://api.twilio.com/2010-04-01/Accounts/"
            f"{self._account_sid}/Messages.json"
        )
        auth = base64.b64encode(
            f"{self._account_sid}:{self._auth_token}".encode()
        ).decode()

        async with aiohttp.ClientSession() as session:
            async with session.post(
                url,
                data={
                    "From": f"whatsapp:{self._from_number}",
                    "To": f"whatsapp:{to_number}",
                    "Body": body,
                },
                headers={"Authorization": f"Basic {auth}"},
            ) as resp:
                if resp.status < 300:
                    logger.info(
                        "whatsapp_sent",
                        to=to_number,
                        interaction_id=interaction.interaction_id,
                    )
                else:
                    resp_body = await resp.text()
                    logger.error(
                        "whatsapp_send_failed",
                        status=resp.status,
                        body=resp_body[:500],
                    )

    async def setup_routes(self, app: FastAPI) -> None:
        """Register the Twilio webhook endpoint."""
        from fastapi import APIRouter, Request
        from fastapi.responses import Response
        router = APIRouter()

        @router.post("/api/channels/whatsapp/webhook", response_class=Response)
        async def whatsapp_webhook(request: Request):
            """Receive incoming WhatsApp messages via Twilio."""
            form = await request.form()
            result = await self._handle_incoming(dict(form))
            # Twilio expects TwiML response; empty is fine for acknowledgement
            return Response(
                content="<Response></Response>",
                media_type="application/xml",
                status_code=200,
            )

        app.include_router(router, tags=["channels-whatsapp"])
        logger.info("whatsapp_webhook_registered")

    async def _handle_incoming(self, form_data: dict) -> dict:
        """Process an incoming Twilio webhook."""
        from_number = str(form_data.get("From", "")).replace("whatsapp:", "")
        body = str(form_data.get("Body", "")).strip()

        if not body:
            return {"status": "empty"}

        # Security check: only accept from allowed numbers
        if self._allowed_numbers and from_number not in self._allowed_numbers:
            logger.warning("whatsapp_unauthorized", from_number=from_number)
            return {"status": "unauthorized"}

        logger.info("whatsapp_received", from_number=from_number, body=body[:200])

        # Route to pending interaction
        if self._broker:
            pending = self._broker.get_pending(channel="whatsapp")
            if pending:
                interaction = pending[0]
                await self._broker.submit_response(
                    interaction.interaction_id,
                    body,
                    responder=f"whatsapp:{from_number}",
                )
                return {"status": "response_accepted"}

        # No pending interaction — could create a task
        logger.info("whatsapp_no_pending", from_number=from_number)
        return {"status": "no_pending_interaction"}

    def _format_message(self, interaction: Interaction) -> str:
        """Format interaction as WhatsApp-friendly text."""
        parts = [f"*Agent Question:*\n{interaction.prompt}"]

        if interaction.options:
            options_text = "\n".join(
                f"  {i+1}. {opt.get('label', opt.get('id', ''))}"
                for i, opt in enumerate(interaction.options)
            )
            parts.append(f"\n*Options:*\n{options_text}\n\n_Reply with the number or text of your choice._")
        else:
            parts.append("\n_Reply with your answer._")

        parts.append(f"\n`ID: {interaction.interaction_id[:8]}`")
        return "\n".join(parts)
