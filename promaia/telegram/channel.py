"""
Telegram notification channel for event delivery.

Implements the NotificationChannel ABC so the event router can push
interrupt and digest events to a Telegram chat. Runs in the scheduler
process (separate from the bot polling process) -- two processes can
share a bot token since sending is stateless.
"""
import json
import logging

from aiogram import Bot

from promaia.events.channels import NotificationChannel
from promaia.storage.db_factory import get_db

logger = logging.getLogger(__name__)


class TelegramChannel(NotificationChannel):
    """Deliver events to a Telegram chat via the Bot API."""

    def __init__(self, bot_token: str, chat_id: int):
        self._bot = Bot(token=bot_token)
        self._chat_id = chat_id

    @property
    def name(self) -> str:
        return "telegram"

    def supports_urgency(self, urgency: str) -> bool:
        """Handle interrupt and digest events."""
        return urgency in ("interrupt", "digest")

    async def deliver(self, event: dict) -> bool:
        """Send event summary to Telegram and mark as routed.

        Returns True on success, False on failure. Never raises.
        """
        try:
            # Extract summary from payload (JSONB -- may be dict or string)
            payload = event.get("payload", {})
            if isinstance(payload, str):
                try:
                    payload = json.loads(payload)
                except (json.JSONDecodeError, TypeError):
                    payload = {}

            summary = (
                payload.get("summary")
                if isinstance(payload, dict)
                else None
            ) or str(event.get("payload", "New notification"))

            # Format based on urgency
            urgency = event.get("urgency", "digest")
            if urgency == "interrupt":
                text = f"URGENT: {summary}"
            else:
                text = summary

            # Send to Telegram
            await self._bot.send_message(self._chat_id, text)

            # Mark event as routed
            db = get_db()
            db.execute(
                "UPDATE events SET routed_at = datetime('now'), channel = 'telegram' WHERE id = ?",
                (event["id"],),
            )

            logger.info(f"Telegram: delivered event {event['id']} to chat {self._chat_id}")
            return True

        except Exception as e:
            logger.error(
                f"Telegram delivery failed for event {event.get('id')}: {e}",
                exc_info=True,
            )
            return False
