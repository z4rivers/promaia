"""
Notification channels for event delivery.

Defines the abstract NotificationChannel interface and the
DashboardChannel implementation. Phase 8 will add TelegramChannel
without modifying the router (07-02).
"""
from abc import ABC, abstractmethod
import logging

from promaia.storage.db_factory import get_db

logger = logging.getLogger(__name__)


class NotificationChannel(ABC):
    """Abstract base class for notification delivery channels."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Channel identifier (e.g. 'dashboard', 'telegram')."""
        ...

    @abstractmethod
    async def deliver(self, event: dict) -> bool:
        """Deliver an event through this channel.

        Args:
            event: Event dict from events row.

        Returns:
            True if delivery succeeded, False otherwise.
        """
        ...

    @abstractmethod
    def supports_urgency(self, urgency: str) -> bool:
        """Whether this channel handles the given urgency level.

        Args:
            urgency: One of 'interrupt', 'digest', 'archive'.

        Returns:
            True if the channel should receive events of this urgency.
        """
        ...


class DashboardChannel(NotificationChannel):
    """Passive dashboard channel -- marks events as routed for badge display.

    Dashboard delivery is passive: the badge query in the web layer picks up
    routed-but-unread events. 'Delivering' here means marking the event as
    dashboard-bound so the router considers it handled.
    """

    @property
    def name(self) -> str:
        return "dashboard"

    def supports_urgency(self, urgency: str) -> bool:
        """Dashboard shows interrupt and digest events; archive is just logged."""
        return urgency in ("interrupt", "digest")

    async def deliver(self, event: dict) -> bool:
        """Mark the event as routed to the dashboard channel."""
        try:
            db = get_db()
            db.execute(
                "UPDATE events SET routed_at = datetime('now'), channel = 'dashboard' WHERE id = ?",
                (event["id"],),
            )
            logger.info(f"Dashboard: routed event {event['id']} (type={event.get('type')})")
            return True
        except Exception as e:
            logger.error(f"Dashboard delivery failed for event {event.get('id')}: {e}")
            return False
