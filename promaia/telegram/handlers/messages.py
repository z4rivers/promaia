"""
Free-text message handler for Telegram bot.

Catches all text messages not matched by command handlers and auto-captures
them to the brain with domain detection.
"""
import logging
import random
import re

from aiogram import Router
from aiogram.types import Message

from promaia.brain.engine import detect_mode
from promaia.telegram.brain_ops import capture_memory

logger = logging.getLogger(__name__)

router = Router()

_GREETING_PATTERNS = re.compile(
    r"^\s*(hey|hi|hello|yo|sup|morning|good morning|good evening|good afternoon|"
    r"gm|what's up|whats up|are you there|you there|howdy|hola)\s*[!?.]*\s*$",
    re.IGNORECASE,
)

_GREETING_RESPONSES = [
    "Hey! What's on your mind?",
    "Morning -- ready when you are.",
    "Hey. What's up?",
    "I'm here. What do you need?",
    "Hey! Go ahead.",
]


def _is_greeting(text: str) -> bool:
    return bool(_GREETING_PATTERNS.match(text.strip()))


def _is_question(text: str) -> bool:
    stripped = text.strip()
    if stripped.endswith("?"):
        return True
    lower = stripped.lower()
    return any(lower.startswith(w) for w in (
        "who ", "what ", "when ", "where ", "why ", "how ",
        "can you ", "could you ", "do you ", "does ", "is ", "are ",
        "will ", "should ",
    ))


@router.message()
async def handle_free_text(message: Message) -> None:
    """Auto-capture free-text messages to brain with domain detection."""
    text = message.text
    if not text:
        return

    # Greetings get a conversational reply, no capture
    if _is_greeting(text):
        await message.answer(random.choice(_GREETING_RESPONSES))
        return

    # Detect domain from message content
    mode_result = detect_mode(text)
    domain = mode_result.get("mode", "working")

    # Still capture everything to brain
    result = await capture_memory(text, domain=domain)

    # Questions get an honest acknowledgment
    if _is_question(text):
        question_responses = [
            "I heard you, but I can't answer questions yet -- I've saved it though.",
            "Can't answer that one yet, but it's stored.",
            "Saved your question. Answering is on the roadmap.",
            "Noted the question -- can't reason on it yet, but it's in the brain.",
        ]
        await message.answer(random.choice(question_responses))
        return

    await message.answer(result)
