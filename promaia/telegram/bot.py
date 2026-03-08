"""
Telegram bot main module.

Sets up the aiogram Dispatcher, registers middleware and routers,
and starts polling (default) or webhook mode for cloud deployment.

Webhook mode activates when TELEGRAM_WEBHOOK_URL is set. In webhook mode,
the bot registers a FastAPI route at /telegram/webhook that receives updates.
"""
import logging
import os

from aiogram import Bot, Dispatcher
from aiogram.utils.backoff import BackoffConfig

from promaia.telegram.auth import WhitelistMiddleware
from promaia.telegram.handlers import commands, messages, voice, replies

logger = logging.getLogger(__name__)

# Module-level references so the webhook route can access them
_bot: Bot | None = None
_dp: Dispatcher | None = None


def _setup_dispatcher() -> tuple[Bot, Dispatcher]:
    """Create and configure Bot + Dispatcher (shared by both modes)."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN not set -- cannot start bot")

    bot = Bot(token=token)
    dp = Dispatcher()

    # Register whitelist middleware on all incoming messages
    dp.message.middleware(WhitelistMiddleware())

    # Include routers in order: commands > voice > replies > messages (catch-all last)
    dp.include_router(commands.router)
    dp.include_router(voice.router)
    dp.include_router(replies.router)
    dp.include_router(messages.router)

    return bot, dp


async def start_bot() -> None:
    """
    Start the Telegram bot.

    If TELEGRAM_WEBHOOK_URL is set, registers a webhook with Telegram
    and keeps the bot alive (updates arrive via the /telegram/webhook
    FastAPI route added by setup_webhook_route()).

    Otherwise, falls back to polling mode.
    """
    global _bot, _dp

    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        logger.error("TELEGRAM_BOT_TOKEN not set -- cannot start bot")
        return

    _bot, _dp = _setup_dispatcher()

    webhook_url = os.environ.get("TELEGRAM_WEBHOOK_URL", "").strip()
    if webhook_url:
        # Webhook mode: set the webhook URL with Telegram
        full_url = f"{webhook_url.rstrip('/')}/telegram/webhook"
        await _bot.set_webhook(
            url=full_url,
            drop_pending_updates=True,
        )
        logger.info(f"Telegram bot webhook set: {full_url}")

        # In webhook mode, we just keep the task alive -- updates come via HTTP
        import asyncio
        try:
            while True:
                await asyncio.sleep(3600)
        except asyncio.CancelledError:
            # Clean shutdown: remove webhook
            await _bot.delete_webhook()
            logger.info("Telegram webhook removed on shutdown")
    else:
        # Polling mode (default for local development)
        logger.info("Telegram bot starting polling...")
        await _dp.start_polling(
            _bot,
            backoff_config=BackoffConfig(
                min_delay=1.0,
                max_delay=30.0,
                factor=1.5,
                jitter=0.1,
            ),
            polling_timeout=30,
        )


def setup_webhook_route(app) -> None:
    """
    Register the /telegram/webhook POST route on a FastAPI app.

    Call this during app startup if TELEGRAM_WEBHOOK_URL is set.
    The route receives Telegram updates and feeds them to the dispatcher.
    """
    from aiogram.types import Update

    @app.post("/telegram/webhook", include_in_schema=False)
    async def telegram_webhook(request):
        if _bot is None or _dp is None:
            from starlette.responses import JSONResponse
            return JSONResponse({"ok": False}, status_code=503)

        from starlette.responses import JSONResponse
        data = await request.json()
        update = Update.model_validate(data, context={"bot": _bot})
        await _dp.feed_update(bot=_bot, update=update)
        return JSONResponse({"ok": True})
