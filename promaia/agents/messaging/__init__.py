"""
Messaging platform abstraction layer for Promaia agents.

Provides a platform-agnostic interface for sending messages, managing
conversations, and integrating with external messaging services (Discord, Slack, etc.).

Architecture:
    BasePlatform → DiscordPlatform, SlackPlatform
    ConversationManager → orchestrates conversations across any platform
"""

from .base_platform import BasePlatform
from .conversation_manager import ConversationManager

__all__ = [
    'BasePlatform',
    'ConversationManager',
]
