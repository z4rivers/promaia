"""
Sliding-window rate limiter for notification channels.

Uses SQL count queries against brain.events as source of truth
(no in-memory state), so limits survive scheduler restarts (07-02).
"""
import logging
from datetime import datetime, timedelta

from promaia.storage.postgres_db import get_postgres_db

logger = logging.getLogger(__name__)


class RateLimiter:
    """Enforce per-channel rate limits using the database as source of truth.

    Rules:
    - ``interrupt`` urgency always bypasses rate limiting.
    - Non-interrupt: max ``max_per_hour`` push notifications per hour per channel.
    - Non-interrupt: ``cooldown_minutes`` between consecutive pushes per channel.
    """

    def __init__(self, max_per_hour: int = 10, cooldown_minutes: int = 30):
        self.max_per_hour = max_per_hour
        self.max_per_day = 10
        self.cooldown_minutes = cooldown_minutes

    def _check_daily_cap(self) -> bool:
        """Check if daily notification cap has been reached across all channels."""
        db = get_postgres_db()
        row = db.fetch_one(
            "SELECT COUNT(DISTINCT id) AS cnt FROM brain.events "
            "WHERE routed_at IS NOT NULL "
            "AND routed_at::date = CURRENT_DATE "
            "AND urgency != 'archive'",
        )
        daily_count = row["cnt"] if row else 0
        if daily_count >= self.max_per_day:
            logger.info(f"Rate limit: daily cap reached ({daily_count}/{self.max_per_day})")
            return False
        return True

    def allow(self, channel_name: str, urgency: str) -> bool:
        """Check whether sending another notification is allowed.

        Args:
            channel_name: Channel identifier (e.g. 'dashboard').
            urgency: Event urgency level.

        Returns:
            True if the send is allowed, False if rate-limited.
        """
        # Interrupt events always go through
        if urgency == "interrupt":
            return True

        try:
            db = get_postgres_db()

            # Check daily cap across all channels
            if not self._check_daily_cap():
                return False

            # Check hourly cap (cross-channel dedup: count unique events, not deliveries)
            row = db.fetch_one(
                "SELECT COUNT(DISTINCT id) AS cnt FROM brain.events "
                "WHERE routed_at IS NOT NULL "
                "AND routed_at > NOW() - INTERVAL '1 hour' "
                "AND urgency != 'archive'",
            )
            hourly_count = row["cnt"] if row else 0
            if hourly_count >= self.max_per_hour:
                logger.info(
                    f"Rate limit: {channel_name} hit hourly cap "
                    f"({hourly_count}/{self.max_per_hour})"
                )
                return False

            # Check cooldown between non-urgent pushes
            row = db.fetch_one(
                "SELECT MAX(routed_at) AS last_routed FROM brain.events "
                "WHERE routed_at IS NOT NULL AND channel = %s "
                "AND urgency != 'interrupt'",
                (channel_name,),
            )
            last_routed = row["last_routed"] if row else None
            if last_routed is not None:
                # Ensure timezone-naive comparison
                now = datetime.utcnow()
                if hasattr(last_routed, "replace"):
                    last_routed_naive = last_routed.replace(tzinfo=None)
                else:
                    last_routed_naive = last_routed
                elapsed = now - last_routed_naive
                if elapsed < timedelta(minutes=self.cooldown_minutes):
                    remaining = self.cooldown_minutes - (elapsed.total_seconds() / 60)
                    logger.info(
                        f"Rate limit: {channel_name} cooldown active "
                        f"({remaining:.0f}min remaining)"
                    )
                    return False

            return True

        except Exception as e:
            # On DB error, allow the send (fail-open for delivery)
            logger.warning(f"Rate limiter DB check failed (allowing): {e}")
            return True
