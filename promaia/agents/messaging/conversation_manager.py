"""
Platform-agnostic conversation manager for Promaia agents.

Orchestrates multi-turn conversations between agents and users across
any registered messaging platform (Discord, Slack, etc.).

Used by:
- Agent executor (_send_to_messaging_platform) for posting results
- Discord bot (bot.py) for handling mentions and commands
- Future Slack bot for similar functionality
"""
from __future__ import annotations

import logging
import uuid
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum

from .base_platform import BasePlatform, MessagePayload, SendResult

logger = logging.getLogger(__name__)


class ConversationState(Enum):
    """States a conversation can be in."""
    PENDING = "pending"        # Waiting for initial response
    ACTIVE = "active"          # Ongoing back-and-forth
    WAITING = "waiting"        # Agent sent message, waiting for user reply
    COMPLETED = "completed"    # Conversation ended normally
    TIMED_OUT = "timed_out"    # No response within timeout
    ERROR = "error"            # Something went wrong


@dataclass
class ConversationTurn:
    """A single turn in a conversation."""
    role: str  # "agent" or "user"
    content: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    message_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Conversation:
    """Tracks state of a multi-turn conversation."""
    conversation_id: str
    agent_id: str
    platform: str
    channel_id: str
    state: ConversationState = ConversationState.PENDING
    turns: List[ConversationTurn] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    timeout_minutes: int = 15
    max_turns: Optional[int] = None
    thread_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def turn_count(self) -> int:
        return len(self.turns)

    @property
    def is_active(self) -> bool:
        return self.state in (
            ConversationState.ACTIVE,
            ConversationState.WAITING,
            ConversationState.PENDING,
        )

    def add_turn(self, role: str, content: str, message_id: Optional[str] = None) -> ConversationTurn:
        """Add a turn and update conversation state."""
        turn = ConversationTurn(
            role=role,
            content=content,
            message_id=message_id,
        )
        self.turns.append(turn)
        self.updated_at = datetime.now(timezone.utc)

        # Update state based on who spoke
        if role == "agent":
            self.state = ConversationState.WAITING
        elif role == "user":
            self.state = ConversationState.ACTIVE

        # Check max turns
        if self.max_turns and self.turn_count >= self.max_turns:
            self.state = ConversationState.COMPLETED

        return turn


class ConversationManager:
    """
    Manages multi-turn conversations across messaging platforms.

    Responsibilities:
    - Register platform implementations (Discord, Slack, etc.)
    - Start and track conversations
    - Route incoming messages to the right conversation
    - Handle timeouts and conversation lifecycle
    """

    def __init__(self):
        self.platforms: Dict[str, BasePlatform] = {}
        self.conversations: Dict[str, Conversation] = {}
        self._channel_conversations: Dict[str, str] = {}  # channel_id -> conversation_id

    def register_platform(self, name: str, platform: BasePlatform) -> None:
        """Register a messaging platform implementation."""
        self.platforms[name] = platform
        logger.info(f"Registered messaging platform: {name}")

    def get_platform(self, name: str) -> Optional[BasePlatform]:
        """Get a registered platform by name."""
        return self.platforms.get(name)

    async def start_conversation(
        self,
        agent_id: str,
        platform: str,
        channel_id: str,
        initial_message: str,
        timeout_minutes: int = 15,
        max_turns: Optional[int] = None,
        thread_id: Optional[str] = None,
    ) -> Conversation:
        """
        Start a new conversation on a platform.

        Sends the initial message and begins tracking the conversation state.

        Args:
            agent_id: ID of the agent initiating
            platform: Platform name ("discord", "slack")
            channel_id: Channel to converse in
            initial_message: First message to send
            timeout_minutes: How long to wait for replies
            max_turns: Maximum conversation turns (None = unlimited)
            thread_id: Optional thread to start in

        Returns:
            Conversation object tracking the interaction
        """
        platform_impl = self.platforms.get(platform)
        if not platform_impl:
            raise ValueError(f"Platform '{platform}' not registered. Available: {list(self.platforms.keys())}")

        # Create conversation
        conversation = Conversation(
            conversation_id=str(uuid.uuid4()),
            agent_id=agent_id,
            platform=platform,
            channel_id=channel_id,
            timeout_minutes=timeout_minutes,
            max_turns=max_turns,
            thread_id=thread_id,
        )

        # Format and send initial message
        formatted = platform_impl.format_message(initial_message, agent_name=agent_id)
        chunks = platform_impl.split_message(formatted)

        first_message_id = None
        for i, chunk in enumerate(chunks):
            result = await platform_impl.send_message(
                channel_id=channel_id,
                content=chunk,
                thread_id=thread_id,
            )
            if result.success and i == 0:
                first_message_id = result.message_id

        # Track the conversation
        conversation.add_turn("agent", initial_message, message_id=first_message_id)
        self.conversations[conversation.conversation_id] = conversation
        self._channel_conversations[channel_id] = conversation.conversation_id

        logger.info(
            f"Started conversation {conversation.conversation_id} on {platform} "
            f"in channel {channel_id} (agent: {agent_id})"
        )

        return conversation

    async def post_message(
        self,
        platform: str,
        channel_id: str,
        content: str,
        agent_name: Optional[str] = None,
        thread_id: Optional[str] = None,
    ) -> SendResult:
        """
        Send a one-way message (no conversation tracking).

        Used for agent result posting where no reply is expected.

        Args:
            platform: Platform name
            channel_id: Channel to post to
            content: Message content
            agent_name: Optional agent name for attribution
            thread_id: Optional thread context

        Returns:
            SendResult with delivery status
        """
        platform_impl = self.platforms.get(platform)
        if not platform_impl:
            return SendResult(
                success=False,
                error=f"Platform '{platform}' not registered",
                platform=platform,
            )

        formatted = platform_impl.format_message(content, agent_name=agent_name)
        chunks = platform_impl.split_message(formatted)

        last_result = None
        for chunk in chunks:
            last_result = await platform_impl.send_message(
                channel_id=channel_id,
                content=chunk,
                thread_id=thread_id,
            )
            if not last_result.success:
                return last_result

        return last_result or SendResult(success=False, error="No chunks to send")

    def get_conversation(self, conversation_id: str) -> Optional[Conversation]:
        """Get a conversation by ID."""
        return self.conversations.get(conversation_id)

    def get_active_conversation(self, channel_id: str) -> Optional[Conversation]:
        """Get the active conversation for a channel, if any."""
        conv_id = self._channel_conversations.get(channel_id)
        if conv_id:
            conv = self.conversations.get(conv_id)
            if conv and conv.is_active:
                return conv
        return None

    def end_conversation(self, conversation_id: str) -> None:
        """Mark a conversation as completed."""
        conv = self.conversations.get(conversation_id)
        if conv:
            conv.state = ConversationState.COMPLETED
            conv.updated_at = datetime.now(timezone.utc)
            # Clean up channel mapping
            if conv.channel_id in self._channel_conversations:
                if self._channel_conversations[conv.channel_id] == conversation_id:
                    del self._channel_conversations[conv.channel_id]
            logger.info(f"Ended conversation {conversation_id}")

    def list_active_conversations(self) -> List[Conversation]:
        """List all currently active conversations."""
        return [c for c in self.conversations.values() if c.is_active]
