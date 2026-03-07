"""
Reply handler for inline responses to pushed notifications.

Intercepts replies to bot-sent push notifications (urgent alerts, briefings,
digests) and captures them to the brain with original notification context.
Does NOT intercept replies to command responses -- those fall through to
the catch-all free-text handler.

Must be registered BEFORE messages.router (catch-all) in bot.py.
"""
import logging

from aiogram import Router, F
from aiogram.types import Message

from promaia.telegram.brain_ops import capture_memory
from promaia.telegram.conversation import generate_response, reset_synthesis_timer
from promaia.telegram.formatting import send_long_message

logger = logging.getLogger(__name__)

router = Router()


def _is_reply_to_bot(message: Message) -> bool:
    """Filter: message is a reply to a bot-sent message."""
    return (
        message.reply_to_message is not None
        and message.reply_to_message.from_user is not None
        and message.reply_to_message.from_user.is_bot
    )


# Push notification prefixes from scheduler._push_agent_output() and TelegramChannel.deliver()
_URGENT_PREFIX = "URGENT:"
_BRIEFING_PREFIX = "Good morning."
_DIGEST_PREFIX = "Evening digest:"


@router.message(_is_reply_to_bot)
async def handle_reply(message: Message) -> None:
    """Process inline replies to pushed notifications.

    Matches only replies to push notifications (urgent alerts, briefings,
    digests). Replies to command responses are ignored and fall through
    to the catch-all free-text handler.
    """
    reply_text = message.text
    if not reply_text:
        return

    original = message.reply_to_message
    original_text = original.text or ""

    # Determine which type of push notification was replied to
    if original_text.startswith(_URGENT_PREFIX):
        # Urgent email / interrupt notification
        content = (
            f"Reply to urgent notification: {original_text[:200]}\n\n"
            f"Zack's response: {reply_text}"
        )
        domain = "email"

    elif original_text.startswith(_BRIEFING_PREFIX):
        # Morning briefing
        content = f"Reply to morning briefing:\n\n{reply_text}"
        domain = "working"

    elif original_text.startswith(_DIGEST_PREFIX):
        # Evening digest
        content = f"Reply to evening digest:\n\n{reply_text}"
        domain = "working"

    else:
        # Not a push notification reply (e.g., reply to /briefing command response)
        # Return without responding -- let the message fall through to catch-all
        return

    logger.info(f"Reply to push notification captured (domain={domain})")
    # Capture push notification context as standalone memory
    await capture_memory(content, domain=domain)

    # Generate contextual conversational response about the reply
    await message.bot.send_chat_action(message.chat.id, "typing")
    response = await generate_response(message.chat.id, reply_text)
    await reset_synthesis_timer(message.chat.id)
    await send_long_message(message, response)
