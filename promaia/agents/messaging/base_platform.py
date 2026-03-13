"""
Abstract base class for messaging platforms.

Defines the interface that Discord, Slack, and future platforms must implement
to participate in Promaia's agent messaging system.
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


@dataclass
class MessagePayload:
    """Platform-agnostic message representation."""
    content: str
    channel_id: str
    author_id: Optional[str] = None
    author_name: Optional[str] = None
    timestamp: Optional[datetime] = None
    thread_id: Optional[str] = None
    attachments: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now(timezone.utc)


@dataclass
class SendResult:
    """Result of sending a message through a platform."""
    success: bool
    message_id: Optional[str] = None
    error: Optional[str] = None
    platform: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class BasePlatform(ABC):
    """
    Abstract base class for messaging platform integrations.

    Subclasses must implement the core messaging operations:
    - send_message: Post a message to a channel
    - format_message: Format agent output for the platform's constraints
    - fetch_messages: Retrieve recent messages from a channel

    Optional overrides:
    - send_typing_indicator: Show "typing" in the channel
    - react_to_message: Add a reaction to a message
    - get_channel_info: Retrieve channel metadata
    """

    def __init__(self, platform_name: str, bot_token: str, **kwargs):
        self.platform_name = platform_name
        self.bot_token = bot_token
        self._connected = False
        self.logger = logging.getLogger(f"{__name__}.{platform_name}")

    @abstractmethod
    async def send_message(
        self,
        channel_id: str,
        content: str,
        thread_id: Optional[str] = None,
        **kwargs
    ) -> SendResult:
        """
        Send a message to a channel.

        Args:
            channel_id: Platform-specific channel identifier
            content: Message text to send
            thread_id: Optional thread/reply context

        Returns:
            SendResult with success status and message ID
        """
        ...

    @abstractmethod
    def format_message(
        self,
        content: str,
        agent_name: Optional[str] = None,
        max_length: Optional[int] = None
    ) -> str:
        """
        Format agent output for the platform's message constraints.

        Handles:
        - Character limits (Discord: 2000, Slack: 40000)
        - Markdown dialect differences
        - Agent attribution headers

        Args:
            content: Raw agent output text
            agent_name: Optional agent name for attribution
            max_length: Override default platform character limit

        Returns:
            Formatted message string
        """
        ...

    @abstractmethod
    def split_message(self, content: str) -> List[str]:
        """
        Split a long message into chunks that fit the platform's limits.

        Args:
            content: Full message text

        Returns:
            List of message chunks
        """
        ...

    @abstractmethod
    async def fetch_messages(
        self,
        channel_id: str,
        limit: int = 50,
        after: Optional[datetime] = None,
        thread_id: Optional[str] = None
    ) -> List[MessagePayload]:
        """
        Fetch recent messages from a channel.

        Args:
            channel_id: Channel to read from
            limit: Maximum messages to fetch
            after: Only fetch messages after this timestamp
            thread_id: Fetch from a specific thread

        Returns:
            List of MessagePayload objects
        """
        ...

    async def send_typing_indicator(self, channel_id: str) -> bool:
        """Show typing indicator in a channel. Override if platform supports it."""
        return False

    async def react_to_message(
        self, channel_id: str, message_id: str, emoji: str
    ) -> bool:
        """Add a reaction to a message. Override if platform supports it."""
        return False

    async def get_channel_info(self, channel_id: str) -> Dict[str, Any]:
        """Get channel metadata. Override if platform supports it."""
        return {"id": channel_id, "platform": self.platform_name}

    async def connect(self) -> bool:
        """Establish connection to the platform API. Override for platforms that need it."""
        self._connected = True
        return True

    async def disconnect(self) -> None:
        """Clean up platform connection."""
        self._connected = False

    @property
    def is_connected(self) -> bool:
        return self._connected

    def __repr__(self) -> str:
        status = "connected" if self._connected else "disconnected"
        return f"<{self.__class__.__name__} platform={self.platform_name} status={status}>"
