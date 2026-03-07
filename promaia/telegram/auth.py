"""
Whitelist middleware for Telegram bot.

Silently drops messages from non-whitelisted chat IDs.
Whitelisted chat IDs are loaded from the TELEGRAM_WHITELIST env var
(comma-separated integers).
"""
import os
import logging
from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import Message

logger = logging.getLogger(__name__)


class WhitelistMiddleware(BaseMiddleware):
    """Drop messages from chat IDs not in the TELEGRAM_WHITELIST env var."""

    def __init__(self):
        super().__init__()
        raw = os.environ.get("TELEGRAM_WHITELIST", "")
        self.allowed: set[int] = set()
        for part in raw.split(","):
            part = part.strip()
            if part:
                try:
                    self.allowed.add(int(part))
                except ValueError:
                    logger.warning(f"Invalid chat ID in TELEGRAM_WHITELIST: {part!r}")
        if self.allowed:
            logger.info(f"WhitelistMiddleware loaded {len(self.allowed)} allowed chat ID(s)")
        else:
            logger.warning("TELEGRAM_WHITELIST is empty -- all messages will be dropped")

    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: Dict[str, Any],
    ) -> Any:
        if event.chat.id not in self.allowed:
            # Silent drop -- no response, no error log
            return
        return await handler(event, data)
