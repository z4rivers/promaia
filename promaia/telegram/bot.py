"""
Telegram bot main module.

Sets up the aiogram Dispatcher, registers middleware and routers,
and starts polling with automatic reconnect backoff.
"""
import logging
import os

from aiogram import Bot, Dispatcher
from aiogram.utils.backoff import BackoffConfig

from promaia.telegram.auth import WhitelistMiddleware
from promaia.telegram.handlers import commands, messages, voice

logger = logging.getLogger(__name__)


async def start_bot() -> None:
    """
    Start the Telegram bot with polling.

    Reads TELEGRAM_BOT_TOKEN from environment, sets up the dispatcher
    with WhitelistMiddleware, registers command and message routers,
    and starts polling with backoff-based auto-reconnect.
    """
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        logger.error("TELEGRAM_BOT_TOKEN not set -- cannot start bot")
        return

    bot = Bot(token=token)
    dp = Dispatcher()

    # Register whitelist middleware on all incoming messages
    dp.message.middleware(WhitelistMiddleware())

    # Include routers in order: commands FIRST, voice SECOND, messages LAST (catch-all)
    dp.include_router(commands.router)
    dp.include_router(voice.router)
    dp.include_router(messages.router)

    logger.info("Telegram bot starting polling...")

    await dp.start_polling(
        bot,
        backoff_config=BackoffConfig(
            min_delay=1.0,
            max_delay=30.0,
            factor=1.5,
            jitter=0.1,
        ),
        polling_timeout=30,
    )
