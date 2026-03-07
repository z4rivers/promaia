"""
Free-text message handler for Telegram bot.

Routes all non-command text messages through the conversation engine
for Gemini-powered responses using brain context.
"""
import logging

from aiogram import Router
from aiogram.types import Message

from promaia.telegram.conversation import generate_response, reset_synthesis_timer
from promaia.telegram.formatting import send_long_message

logger = logging.getLogger(__name__)

router = Router()


@router.message()
async def handle_free_text(message: Message) -> None:
    """Route all free-text messages through the conversation engine."""
    text = message.text
    if not text:
        return

    # Show typing indicator while Gemini thinks
    await message.bot.send_chat_action(message.chat.id, "typing")

    # Generate conversational response (handles session, impact scoring, context, Gemini)
    response = await generate_response(message.chat.id, text)

    # Reset synthesis timer (background -- never blocks response)
    await reset_synthesis_timer(message.chat.id)

    # Send response (handles splitting at 4096 char limit)
    await send_long_message(message, response)
