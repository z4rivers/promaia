"""
Unified runner — starts scheduler, Telegram bot, and web dashboard together.

Usage:
    python -m promaia dev
"""
import asyncio
import logging
import os
import signal
import sys

from dotenv import load_dotenv

logger = logging.getLogger("promaia.runner")


async def _run_web(host: str = "0.0.0.0", port: int = 8000):
    """Run the FastAPI web dashboard via uvicorn."""
    import uvicorn

    config = uvicorn.Config(
        "promaia.web.main:app",
        host=host,
        port=port,
        log_level="warning",
    )
    server = uvicorn.Server(config)
    await server.serve()


async def _run_telegram():
    """Run the Telegram bot polling loop."""
    from promaia.telegram.bot import start_bot
    await start_bot()


async def _run_scheduler():
    """Run the agent scheduler."""
    from promaia.agents.scheduler import AgentScheduler

    scheduler = AgentScheduler()

    # Wire up shutdown signal
    def handle_signal(signum, frame):
        scheduler.stop()

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    await scheduler.start()


async def run_all():
    """Start all three services concurrently."""
    # Load env before anything else
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    load_dotenv(os.path.join(project_root, ".env"))

    port = int(os.environ.get("PORT", "8000"))

    logger.info("Starting Promaia (scheduler + telegram + web)...")

    tasks = [
        asyncio.create_task(_run_scheduler(), name="scheduler"),
        asyncio.create_task(_run_telegram(), name="telegram"),
        asyncio.create_task(_run_web(port=port), name="web"),
    ]

    # Wait until any task exits (usually means shutdown was requested)
    done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)

    # Cancel remaining tasks
    for task in pending:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    # Check for unexpected exits
    for task in done:
        if task.exception():
            logger.error(f"{task.get_name()} exited with error: {task.exception()}")


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(message)s",
        datefmt="%H:%M:%S",
    )
    logging.getLogger("googleapiclient.discovery_cache").setLevel(logging.ERROR)
    logging.getLogger("aiogram").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)

    try:
        asyncio.run(run_all())
    except KeyboardInterrupt:
        logger.info("Shutting down.")


if __name__ == "__main__":
    main()
