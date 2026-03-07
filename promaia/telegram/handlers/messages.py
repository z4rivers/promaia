"""
Free-text message handler for Telegram bot.

Catches all text messages not matched by command handlers and auto-captures
them to the brain with domain detection.
"""
import logging

from aiogram import Router
from aiogram.types import Message

from promaia.brain.engine import detect_mode
from promaia.telegram.brain_ops import capture_memory

logger = logging.getLogger(__name__)

router = Router()


@router.message()
async def handle_free_text(message: Message) -> None:
    """Auto-capture free-text messages to brain with domain detection."""
    text = message.text
    if not text:
        return

    # Detect domain from message content
    mode_result = detect_mode(text)
    domain = mode_result.get("mode", "working")

    result = await capture_memory(text, domain=domain)
    await message.answer(result)
