"""
Command handlers for Telegram bot.

Handles /start, /briefing, /search, /capture, /projects, /actions.
"""
import logging

from aiogram import Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message

from promaia.telegram.brain_ops import (
    get_briefing,
    capture_memory,
    search_brain,
    get_actions,
    get_projects,
)
from promaia.telegram.formatting import send_long_message

logger = logging.getLogger(__name__)

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    """Welcome message listing available commands."""
    await message.answer(
        "Promaia Brain Bot\n\n"
        "Commands:\n"
        "  /briefing -- Session briefing (stale projects, actions, heartbeat)\n"
        "  /search <query> -- Semantic search across memories\n"
        "  /capture <text> -- Capture a thought or note\n"
        "  /projects -- List all projects\n"
        "  /actions -- List pending actions\n\n"
        "Or just send any text to auto-capture it."
    )


@router.message(Command("briefing"))
async def cmd_briefing(message: Message) -> None:
    """Return the current session briefing."""
    result = await get_briefing()
    await send_long_message(message, result)


@router.message(Command("search"))
async def cmd_search(message: Message) -> None:
    """Semantic search across brain memories."""
    # Extract query text after /search
    text = (message.text or "").strip()
    # Remove the /search command prefix
    query = text.split(maxsplit=1)[1] if len(text.split(maxsplit=1)) > 1 else ""
    if not query:
        await message.answer("Usage: /search <query>\n\nExample: /search telegram bot setup")
        return
    result = await search_brain(query)
    await send_long_message(message, result)


@router.message(Command("capture"))
async def cmd_capture(message: Message) -> None:
    """Capture a thought or note to brain."""
    text = (message.text or "").strip()
    content = text.split(maxsplit=1)[1] if len(text.split(maxsplit=1)) > 1 else ""
    if not content:
        await message.answer("Usage: /capture <text>\n\nExample: /capture Need to review PR by Friday")
        return
    result = await capture_memory(content)
    await message.answer(result)


@router.message(Command("projects"))
async def cmd_projects(message: Message) -> None:
    """List all projects with priority and staleness."""
    result = await get_projects()
    await send_long_message(message, result)


@router.message(Command("actions"))
async def cmd_actions(message: Message) -> None:
    """List pending actions."""
    result = await get_actions()
    await send_long_message(message, result)
