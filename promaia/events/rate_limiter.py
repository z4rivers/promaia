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
        self.cooldown_minutes = cooldown_minutes

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

            # Check hourly cap
            row = db.fetch_one(
                "SELECT COUNT(*) AS cnt FROM brain.events "
                "WHERE routed_at IS NOT NULL AND channel = %s "
                "AND routed_at > NOW() - INTERVAL '1 hour'",
                (channel_name,),
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
