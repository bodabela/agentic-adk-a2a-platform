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

import re
from typing import Any, TYPE_CHECKING

from src.shared.logging import get_logger
from src.shared.interactions.channels.base import ChannelAdapter

if TYPE_CHECKING:
    from fastapi import FastAPI
    from src.shared.interactions.broker import InteractionBroker
    from src.shared.interactions.models import Interaction

logger = get_logger("interactions.channels.whatsapp")


class WhatsAppChannel(ChannelAdapter):
    """WhatsApp Business integration via Twilio API."""

    name = "whatsapp"
    capabilities = frozenset({"text"})

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

    # -- Outbound: notifications ------------------------------------------------

    async def send_notification(self, message: str, context_id: str = "", metadata: dict | None = None) -> None:
        """Send a one-way notification via WhatsApp."""
        metadata = metadata or {}
        to_number = metadata.get("phone")
        if len(message) > 4000:
            message = message[:3997] + "..."

        if to_number:
            await self._send_text(to_number, message)
        elif self._allowed_numbers:
            for number in self._allowed_numbers:
                await self._send_text(number, message)
        else:
            logger.error("whatsapp_notification_no_recipient", context_id=context_id)

    # -- Outbound: questions ----------------------------------------------------

    async def send_question(self, interaction: Interaction) -> None:
        """Send a WhatsApp message for an interaction."""
        to_number = interaction.metadata.get("phone")
        if not to_number:
            if self._allowed_numbers:
                for number in self._allowed_numbers:
                    await self._send_question_to(number, interaction)
            else:
                logger.error("whatsapp_no_recipient", interaction_id=interaction.interaction_id)
            return
        await self._send_question_to(to_number, interaction)

    async def _send_question_to(self, to_number: str, interaction: Interaction) -> None:
        """Format and send interaction as WhatsApp message."""
        body = self._format_message(interaction)
        await self._send_text(to_number, body)
        logger.info(
            "whatsapp_sent",
            to=to_number,
            interaction_id=interaction.interaction_id,
            interaction_type=interaction.interaction_type.value,
        )

    # -- Outbound: low-level Twilio API -----------------------------------------

    async def _send_text(self, to_number: str, body: str) -> None:
        """Send a plain text WhatsApp message via Twilio."""
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
                if resp.status >= 300:
                    resp_body = await resp.text()
                    logger.error("whatsapp_send_failed", status=resp.status, body=resp_body[:500])

    # -- Inbound: webhook -------------------------------------------------------

    async def setup_routes(self, app: FastAPI) -> None:
        """Register the Twilio webhook endpoint."""
        from fastapi import APIRouter, Request
        from fastapi.responses import Response
        router = APIRouter()

        @router.post("/api/channels/whatsapp/webhook", response_class=Response)
        async def whatsapp_webhook(request: Request):
            form = await request.form()
            await self._handle_incoming(dict(form))
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
        # Interactive message replies come in ButtonText or ListTitle
        button_text = str(form_data.get("ButtonText", "")).strip()
        list_id = str(form_data.get("ListId", "")).strip()

        reply = button_text or list_id or body
        if not reply:
            return {"status": "empty"}

        if self._allowed_numbers and from_number not in self._allowed_numbers:
            logger.warning("whatsapp_unauthorized", from_number=from_number)
            return {"status": "unauthorized"}

        logger.info("whatsapp_received", from_number=from_number, body=reply[:200])

        if self._broker:
            pending = self._broker.get_pending(channel="whatsapp")
            if pending:
                interaction = pending[0]
                response: Any = self._parse_response(reply, interaction)
                await self._broker.submit_response(
                    interaction.interaction_id,
                    response,
                    responder=f"whatsapp:{from_number}",
                )
                return {"status": "response_accepted"}

        logger.info("whatsapp_no_pending", from_number=from_number)
        return {"status": "no_pending_interaction"}

    # -- Message formatting -----------------------------------------------------

    def _format_message(self, interaction: Interaction) -> str:
        """Format interaction as WhatsApp-friendly text."""
        parts: list[str] = []

        if interaction.prompt:
            parts.append(f"*{interaction.prompt}*")

        # Multi-question with sub-questions
        if interaction.questions and len(interaction.questions) > 0:
            parts.append("")
            for i, q in enumerate(interaction.questions, 1):
                q_text = q.get("text", q.get("label", ""))
                q_type = q.get("question_type", "free_text")
                q_options = q.get("options", [])

                parts.append(f"*{i}. {q_text}*")
                if q_type == "choice" and q_options:
                    for opt in q_options:
                        label = opt.get("label", opt.get("id", ""))
                        parts.append(f"   • {label}")
                parts.append("")

            parts.append("_Reply with your answers, one per line._")
            parts.append("_For choices, reply with the option name._")

        # Simple choice interaction
        elif interaction.options:
            parts.append("")
            for i, opt in enumerate(interaction.options, 1):
                label = opt.get("label", opt.get("id", ""))
                parts.append(f"  {i}. {label}")
            parts.append("")
            parts.append("_Reply with the number or name of your choice._")

        # Free text
        else:
            parts.append("\n_Reply with your answer._")

        parts.append(f"\n`{interaction.interaction_id[:8]}`")
        return "\n".join(parts)

    # -- Response parsing -------------------------------------------------------

    def _parse_response(self, reply: str, interaction: Interaction) -> Any:
        """Parse a WhatsApp reply into the appropriate response format."""
        i_type = interaction.interaction_type.value

        # Multi-question: parse numbered answers
        if i_type == "multi_question" and interaction.questions:
            return self._parse_multi_answer(reply, interaction.questions)

        # Choice: match by number or label
        if i_type == "choice" and interaction.options:
            return self._match_choice(reply, interaction.options)

        return reply

    @staticmethod
    def _parse_multi_answer(body: str, questions: list[dict]) -> dict[str, str]:
        """Parse numbered answers from WhatsApp reply into {question_id: answer} dict.

        Accepts:  1. Python  2. Web app  3. Flask
        or line-by-line answers.
        """
        lines = [l.strip() for l in body.strip().split("\n") if l.strip()]
        answers: dict[str, str] = {}

        for i, q in enumerate(questions):
            q_id = q.get("id", f"q{i+1}")
            q_options = q.get("options", [])

            if i < len(lines):
                answer = re.sub(r"^\d+[.)]\s*", "", lines[i])
                # If this question has choices, try to match by label/number
                if q_options:
                    matched = WhatsAppChannel._match_choice(answer, q_options)
                    answers[q_id] = matched
                else:
                    answers[q_id] = answer
            else:
                answers[q_id] = ""

        return answers

    @staticmethod
    def _match_choice(reply: str, options: list[dict]) -> str:
        """Match reply to a choice option by number, id, or label."""
        reply_lower = reply.strip().lower()

        # Try numeric match ("1", "2", etc.)
        try:
            idx = int(reply_lower) - 1
            if 0 <= idx < len(options):
                return options[idx].get("id", options[idx].get("label", reply))
        except ValueError:
            pass

        # Try exact label/id match (case-insensitive)
        for opt in options:
            if reply_lower == opt.get("label", "").lower():
                return opt.get("id", opt.get("label", ""))
            if reply_lower == opt.get("id", "").lower():
                return opt.get("id", "")

        # Partial match
        for opt in options:
            if reply_lower in opt.get("label", "").lower():
                return opt.get("id", opt.get("label", ""))

        return reply
