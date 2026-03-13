"""
Slack messaging platform implementation.

Implements BasePlatform for Slack message sending and formatting.
Uses the Slack Web API via slack-sdk (optional dependency).
"""
from __future__ import annotations

import re
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime

from .base_platform import BasePlatform, MessagePayload, SendResult

logger = logging.getLogger(__name__)

# Slack limits
SLACK_MAX_MESSAGE_LENGTH = 40000  # Slack allows up to 40K chars
SLACK_MAX_BLOCKS = 50  # Max blocks per message
SLACK_RECOMMENDED_LENGTH = 4000  # Keep messages readable


class SlackPlatform(BasePlatform):
    """
    Slack implementation of the messaging platform interface.

    Uses the Slack Web API (slack-sdk) for all operations.
    Requires a bot token with appropriate scopes:
    - chat:write (send messages)
    - channels:history (read messages)
    - channels:read (channel info)
    - reactions:write (add reactions)
    """

    def __init__(self, bot_token: str, **kwargs):
        super().__init__(platform_name="slack", bot_token=bot_token, **kwargs)
        self._client = None

    def _get_client(self):
        """Lazy-init the Slack WebClient."""
        if self._client is None:
            try:
                from slack_sdk.web.async_client import AsyncWebClient
                self._client = AsyncWebClient(token=self.bot_token)
                self._connected = True
            except ImportError:
                raise ImportError(
                    "Slack integration requires slack-sdk. "
                    "Install with: pip install slack-sdk"
                )
        return self._client

    async def connect(self) -> bool:
        """Verify Slack connection by testing auth."""
        try:
            client = self._get_client()
            result = await client.auth_test()
            if result["ok"]:
                self._connected = True
                logger.info(f"Slack connected as: {result.get('user', 'unknown')}")
                return True
            else:
                logger.error(f"Slack auth failed: {result.get('error', 'unknown')}")
                return False
        except Exception as e:
            logger.error(f"Slack connection failed: {e}")
            return False

    async def send_message(
        self,
        channel_id: str,
        content: str,
        thread_id: Optional[str] = None,
        **kwargs,
    ) -> SendResult:
        """Send a message to a Slack channel."""
        try:
            client = self._get_client()

            # Build API call params
            params = {
                "channel": channel_id,
                "text": content,
                "mrkdwn": True,
            }

            # Thread support: Slack uses thread_ts
            if thread_id:
                params["thread_ts"] = thread_id

            result = await client.chat_postMessage(**params)

            if result["ok"]:
                return SendResult(
                    success=True,
                    message_id=result["ts"],  # Slack uses timestamp as message ID
                    platform="slack",
                    metadata={"channel": result.get("channel", channel_id)},
                )
            else:
                return SendResult(
                    success=False,
                    error=result.get("error", "Unknown Slack API error"),
                    platform="slack",
                )

        except Exception as e:
            logger.error(f"Failed to send Slack message: {e}")
            return SendResult(success=False, error=str(e), platform="slack")

    def format_message(
        self,
        content: str,
        agent_name: Optional[str] = None,
        max_length: Optional[int] = None,
    ) -> str:
        """
        Format content for Slack's mrkdwn syntax.

        Slack mrkdwn differences from standard markdown:
        - *bold* (not **bold**)
        - _italic_ (not *italic*)
        - ~strikethrough~ (not ~~strikethrough~~)
        - ```code blocks``` (same)
        - > blockquotes (same)
        - No heading support (# doesn't work)
        """
        limit = max_length or SLACK_RECOMMENDED_LENGTH

        # Add agent attribution header
        if agent_name:
            header = f":robot_face: *{agent_name}*\n\n"
            content = header + content

        # Convert standard markdown to Slack mrkdwn
        # Bold: **text** → *text*
        content = re.sub(r'\*\*(.+?)\*\*', r'*\1*', content)

        # Headings: # Title → *Title*
        content = re.sub(r'^#{1,6}\s+(.+)$', r'*\1*', content, flags=re.MULTILINE)

        # Convert HTML if present
        content = re.sub(r'<b>(.*?)</b>', r'*\1*', content)
        content = re.sub(r'<i>(.*?)</i>', r'_\1_', content)
        content = re.sub(r'<br\s*/?>', '\n', content)
        content = re.sub(r'<[^>]+>', '', content)

        return content

    def split_message(self, content: str) -> List[str]:
        """
        Split content for Slack's 40K char limit.

        Slack is more generous than Discord (40K vs 2K), so splitting
        is rarely needed. Uses SLACK_RECOMMENDED_LENGTH (4K) for readability.
        """
        limit = SLACK_RECOMMENDED_LENGTH
        if len(content) <= limit:
            return [content]

        chunks = []
        remaining = content

        while remaining:
            if len(remaining) <= limit:
                chunks.append(remaining)
                break

            # Find split point — same logic as Discord but with larger window
            split_at = limit

            # Try paragraph break
            para_break = remaining.rfind('\n\n', 0, limit)
            if para_break > limit // 3:
                split_at = para_break + 2
            else:
                line_break = remaining.rfind('\n', 0, limit)
                if line_break > limit // 3:
                    split_at = line_break + 1
                else:
                    space = remaining.rfind(' ', 0, limit)
                    if space > limit // 3:
                        split_at = space + 1

            chunks.append(remaining[:split_at])
            remaining = remaining[split_at:]

        return chunks

    async def fetch_messages(
        self,
        channel_id: str,
        limit: int = 50,
        after: Optional[datetime] = None,
        thread_id: Optional[str] = None,
    ) -> List[MessagePayload]:
        """Fetch recent messages from a Slack channel."""
        messages = []

        try:
            client = self._get_client()

            params = {
                "channel": channel_id,
                "limit": limit,
            }

            if after:
                params["oldest"] = str(after.timestamp())

            if thread_id:
                # Fetch thread replies
                result = await client.conversations_replies(
                    channel=channel_id, ts=thread_id, limit=limit
                )
            else:
                result = await client.conversations_history(**params)

            if result["ok"]:
                for msg in result.get("messages", []):
                    messages.append(
                        MessagePayload(
                            content=msg.get("text", ""),
                            channel_id=channel_id,
                            author_id=msg.get("user"),
                            author_name=msg.get("username"),
                            timestamp=datetime.fromtimestamp(float(msg["ts"])),
                            thread_id=msg.get("thread_ts"),
                            metadata={"subtype": msg.get("subtype")},
                        )
                    )

        except Exception as e:
            logger.error(f"Failed to fetch Slack messages: {e}")

        return messages

    async def send_typing_indicator(self, channel_id: str) -> bool:
        """Slack doesn't have a typing indicator API for bots."""
        return False

    async def react_to_message(
        self, channel_id: str, message_id: str, emoji: str
    ) -> bool:
        """Add a reaction to a Slack message."""
        try:
            client = self._get_client()
            # Strip colons from emoji name (Slack API expects name without colons)
            emoji_name = emoji.strip(':')
            result = await client.reactions_add(
                channel=channel_id, timestamp=message_id, name=emoji_name
            )
            return result["ok"]
        except Exception as e:
            logger.warning(f"Could not add Slack reaction: {e}")
            return False

    async def get_channel_info(self, channel_id: str) -> Dict[str, Any]:
        """Get Slack channel metadata."""
        try:
            client = self._get_client()
            result = await client.conversations_info(channel=channel_id)
            if result["ok"]:
                ch = result["channel"]
                return {
                    "id": ch["id"],
                    "name": ch.get("name", ""),
                    "is_private": ch.get("is_private", False),
                    "topic": ch.get("topic", {}).get("value", ""),
                    "purpose": ch.get("purpose", {}).get("value", ""),
                    "num_members": ch.get("num_members", 0),
                    "platform": "slack",
                }
        except Exception as e:
            logger.warning(f"Could not get Slack channel info: {e}")
        return {"id": channel_id, "platform": "slack"}
