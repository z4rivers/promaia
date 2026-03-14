"""
Event router -- polls brain.events and dispatches to notification channels.

Runs as an asyncio task inside the agent scheduler, polling every
``poll_interval`` seconds for unrouted events with urgency set.
Applies quiet hours and rate limiting before channel dispatch (07-02).
"""
import asyncio
import json
import logging
import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from promaia.storage.db_factory import get_db
from promaia.events.channels import DashboardChannel, NotificationChannel
from promaia.events.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)


class EventRouter:
    """Poll brain.events for unrouted events and dispatch to channels.

    The router uses ``WHERE routed_at IS NULL`` (not a since-last-poll
    timestamp), so it catches up on missed events after a restart.
    """

    def __init__(self, poll_interval: int = 30):
        self.poll_interval = poll_interval
        self.channels: list[NotificationChannel] = [DashboardChannel()]
        self.rate_limiter = RateLimiter()
        self.user_timezone = "America/New_York"

        # Conditionally register TelegramChannel if configured
        telegram_token = os.getenv("TELEGRAM_BOT_TOKEN")
        telegram_whitelist = os.getenv("TELEGRAM_WHITELIST", "")
        if telegram_token and telegram_whitelist:
            try:
                from promaia.telegram.channel import TelegramChannel

                chat_id = int(telegram_whitelist.split(",")[0].strip())
                self.channels.append(TelegramChannel(bot_token=telegram_token, chat_id=chat_id))
                logger.info(f"TelegramChannel registered for chat_id={chat_id}")
            except ImportError:
                logger.warning(
                    "aiogram not installed -- TelegramChannel not registered. "
                    "Install with: pip install aiogram"
                )
            except (ValueError, IndexError) as e:
                logger.warning(f"Invalid TELEGRAM_WHITELIST format: {e}")

    async def run(self):
        """Main polling loop -- runs until cancelled."""
        logger.info(f"Event router started (polling every {self.poll_interval}s)")

        while True:
            try:
                events = self._fetch_unrouted_events()
                if events:
                    logger.info(f"Event router: {len(events)} unrouted event(s) found")
                for event in events:
                    await self._route_event(event)
            except asyncio.CancelledError:
                logger.info("Event router cancelled")
                raise
            except Exception as e:
                logger.error(f"Event router error (will retry): {e}")

            try:
                await asyncio.sleep(self.poll_interval)
            except asyncio.CancelledError:
                logger.info("Event router cancelled during sleep")
                raise

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _fetch_unrouted_events(self) -> list[dict]:
        """Query brain.events for unrouted events ready to be dispatched."""
        db = get_db()
        return db.fetch_all(
            """
            SELECT id, type, payload, source, urgency, created_at, held_until
            FROM brain.events
            WHERE urgency IS NOT NULL
              AND routed_at IS NULL
              AND (held_until IS NULL OR held_until <= NOW())
            ORDER BY
              CASE urgency
                WHEN 'interrupt' THEN 1
                WHEN 'digest'    THEN 2
                WHEN 'archive'   THEN 3
              END,
              created_at ASC
            """
        )

    async def _route_event(self, event: dict):
        """Route a single event through the appropriate channel(s)."""
        event_id = event["id"]
        urgency = event.get("urgency", "digest")

        # Archive events: mark routed immediately, skip channels
        if urgency == "archive":
            self._mark_archive(event_id)
            return

        # Quiet hours: hold non-interrupt events until morning
        if self._is_quiet_hours() and urgency != "interrupt":
            self._hold_for_morning(event_id)
            return

        # Dispatch to matching channels
        for channel in self.channels:
            if not channel.supports_urgency(urgency):
                continue

            if not self.rate_limiter.allow(channel.name, urgency):
                logger.info(
                    f"Event {event_id} rate-limited on {channel.name}, skipping"
                )
                continue

            try:
                success = await channel.deliver(event)
                if success:
                    logger.info(
                        f"Event {event_id} delivered via {channel.name}"
                    )
                else:
                    logger.warning(
                        f"Event {event_id} delivery failed on {channel.name}"
                    )
            except Exception as e:
                logger.error(
                    f"Event {event_id} delivery error on {channel.name}: {e}"
                )

    def _is_quiet_hours(self) -> bool:
        """Return True if current local time is in quiet hours (9pm-6am)."""
        tz = ZoneInfo(self.user_timezone)
        now_local = datetime.now(tz)
        return now_local.hour >= 21 or now_local.hour < 6

    def _hold_for_morning(self, event_id: int):
        """Set held_until to the next 6am in the user's timezone."""
        tz = ZoneInfo(self.user_timezone)
        now_local = datetime.now(tz)

        # Calculate next 6am
        if now_local.hour >= 6:
            # After 6am today -> next 6am is tomorrow
            next_morning = (now_local + timedelta(days=1)).replace(
                hour=6, minute=0, second=0, microsecond=0
            )
        else:
            # Before 6am today -> 6am is today
            next_morning = now_local.replace(
                hour=6, minute=0, second=0, microsecond=0
            )

        db = get_db()
        db.execute(
            "UPDATE brain.events SET held_until = %s WHERE id = %s",
            (next_morning, event_id),
        )
        logger.info(f"Event {event_id} held until {next_morning.isoformat()}")

    def _mark_archive(self, event_id: int):
        """Mark an archive event as routed without channel delivery."""
        db = get_db()
        db.execute(
            "UPDATE brain.events SET routed_at = NOW(), channel = 'archive' WHERE id = %s",
            (event_id,),
        )
        logger.info(f"Event {event_id} archived (no channel delivery)")
