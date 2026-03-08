"""
Unified runner — starts scheduler, Telegram bot, and web dashboard together.

Usage:
    python -m promaia dev
"""
import asyncio
import logging
import os

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
        # In production behind a reverse proxy, trust forwarded headers
        forwarded_allow_ips="*" if os.environ.get("PYTHON_ENV") == "production" else None,
    )
    server = uvicorn.Server(config)
    await server.serve()


async def _run_telegram():
    """Run the Telegram bot polling loop with auto-restart on crash.

    Telegram long-polling is inherently flaky — timeout errors are normal
    network weather.  Wrap in a restart loop so a transient failure doesn't
    kill the entire process (web server + scheduler).
    """
    from promaia.telegram.bot import start_bot

    while True:
        try:
            logger.info("Starting Telegram bot...")
            await start_bot()
            logger.warning("Telegram bot exited cleanly — restarting in 5s")
        except asyncio.CancelledError:
            logger.info("Telegram task cancelled, shutting down")
            break
        except Exception as e:
            logger.error(f"Telegram bot crashed: {e} — restarting in 5s")
        await asyncio.sleep(5)


async def _run_scheduler():
    """Run the agent scheduler."""
    from promaia.agents.scheduler import AgentScheduler

    scheduler = AgentScheduler()

    try:
        await scheduler.start()
    except asyncio.CancelledError:
        logger.info("Scheduler task cancelled, stopping")
        scheduler.stop()


async def run_all():
    """Start all three services concurrently."""
    # Load env before anything else
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    load_dotenv(os.path.join(project_root, ".env"))

    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "8000"))

    auth_status = "ON" if os.environ.get("DASHBOARD_PASSWORD") else "OFF (no DASHBOARD_PASSWORD)"
    logger.info(f"Starting Promaia (scheduler + telegram + web) on {host}:{port}")
    logger.info(f"Dashboard auth: {auth_status}")

    tasks = [
        asyncio.create_task(_run_web(host=host, port=port), name="web"),
        asyncio.create_task(_run_scheduler(), name="scheduler"),
        asyncio.create_task(_run_telegram(), name="telegram"),
    ]

    try:
        # FIRST_EXCEPTION: only shut down if a task raises an unhandled error.
        # Telegram now self-heals, so only a fatal web/scheduler crash triggers this.
        done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_EXCEPTION)

        for task in done:
            if task.exception():
                logger.error(f"Fatal: {task.get_name()} crashed: {task.exception()}")
    finally:
        for task in tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        logger.info("All Promaia services shut down")


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
