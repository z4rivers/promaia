"""
Discord messaging platform implementation.

Implements BasePlatform for Discord message sending and formatting.
Used by both the Discord bot (bot.py) and agent executor for posting results.
"""
from __future__ import annotations

import re
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime

from .base_platform import BasePlatform, MessagePayload, SendResult

logger = logging.getLogger(__name__)

# Discord limits
DISCORD_MAX_MESSAGE_LENGTH = 2000
DISCORD_MAX_EMBED_LENGTH = 4096


class DiscordPlatform(BasePlatform):
    """
    Discord implementation of the messaging platform interface.

    Can operate in two modes:
    1. API mode (standalone): Uses discord.py HTTP client directly
    2. Bot-attached mode: Uses an existing bot's connection (set via attach_bot)
    """

    def __init__(self, bot_token: str, **kwargs):
        super().__init__(platform_name="discord", bot_token=bot_token, **kwargs)
        self._bot = None  # Optional: attached discord.py Bot instance
        self._http_client = None  # Lazy-init standalone HTTP client

    def attach_bot(self, bot) -> None:
        """
        Attach a running discord.py Bot instance for message sending.

        When attached, messages are sent through the bot's existing connection
        rather than creating a separate HTTP client.
        """
        self._bot = bot
        self._connected = True
        logger.info("Discord platform attached to running bot instance")

    async def send_message(
        self,
        channel_id: str,
        content: str,
        thread_id: Optional[str] = None,
        **kwargs,
    ) -> SendResult:
        """Send a message to a Discord channel."""
        try:
            if self._bot:
                # Use attached bot connection
                channel = self._bot.get_channel(int(channel_id))
                if not channel:
                    channel = await self._bot.fetch_channel(int(channel_id))

                if thread_id:
                    thread = channel.get_thread(int(thread_id))
                    if thread:
                        msg = await thread.send(content)
                    else:
                        msg = await channel.send(content)
                else:
                    msg = await channel.send(content)

                return SendResult(
                    success=True,
                    message_id=str(msg.id),
                    platform="discord",
                )
            else:
                # Standalone HTTP mode — use aiohttp directly
                import aiohttp

                url = f"https://discord.com/api/v10/channels/{channel_id}/messages"
                headers = {
                    "Authorization": f"Bot {self.bot_token}",
                    "Content-Type": "application/json",
                }
                payload = {"content": content}

                async with aiohttp.ClientSession() as session:
                    async with session.post(url, json=payload, headers=headers) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            return SendResult(
                                success=True,
                                message_id=data.get("id"),
                                platform="discord",
                            )
                        else:
                            error_text = await resp.text()
                            return SendResult(
                                success=False,
                                error=f"Discord API error {resp.status}: {error_text}",
                                platform="discord",
                            )

        except Exception as e:
            logger.error(f"Failed to send Discord message: {e}")
            return SendResult(success=False, error=str(e), platform="discord")

    def format_message(
        self,
        content: str,
        agent_name: Optional[str] = None,
        max_length: Optional[int] = None,
    ) -> str:
        """
        Format content for Discord's markdown dialect and character limits.

        Discord uses a subset of markdown:
        - **bold**, *italic*, __underline__, ~~strikethrough~~
        - ```code blocks```
        - > blockquotes
        - No HTML support
        """
        limit = max_length or DISCORD_MAX_MESSAGE_LENGTH

        # Add agent attribution header if specified
        if agent_name:
            header = f"**🤖 {agent_name}**\n\n"
            content = header + content

        # Convert any HTML tags to discord markdown (cleanup from other platforms)
        content = re.sub(r'<b>(.*?)</b>', r'**\1**', content)
        content = re.sub(r'<i>(.*?)</i>', r'*\1*', content)
        content = re.sub(r'<br\s*/?>', '\n', content)
        content = re.sub(r'<[^>]+>', '', content)  # Strip remaining HTML

        return content

    def split_message(self, content: str) -> List[str]:
        """
        Split content into chunks that fit Discord's 2000 char limit.

        Tries to split at natural boundaries:
        1. Double newlines (paragraph breaks)
        2. Single newlines
        3. Spaces
        4. Hard cut (last resort)
        """
        limit = DISCORD_MAX_MESSAGE_LENGTH
        if len(content) <= limit:
            return [content]

        chunks = []
        remaining = content

        while remaining:
            if len(remaining) <= limit:
                chunks.append(remaining)
                break

            # Find the best split point
            split_at = limit

            # Try paragraph break
            para_break = remaining.rfind('\n\n', 0, limit)
            if para_break > limit // 2:
                split_at = para_break + 2
            else:
                # Try line break
                line_break = remaining.rfind('\n', 0, limit)
                if line_break > limit // 2:
                    split_at = line_break + 1
                else:
                    # Try space
                    space = remaining.rfind(' ', 0, limit)
                    if space > limit // 2:
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
        """Fetch recent messages from a Discord channel."""
        messages = []

        try:
            if self._bot:
                channel = self._bot.get_channel(int(channel_id))
                if not channel:
                    channel = await self._bot.fetch_channel(int(channel_id))

                async for msg in channel.history(limit=limit, after=after):
                    messages.append(
                        MessagePayload(
                            content=msg.content,
                            channel_id=str(msg.channel.id),
                            author_id=str(msg.author.id),
                            author_name=msg.author.display_name,
                            timestamp=msg.created_at,
                            thread_id=str(msg.thread.id) if hasattr(msg, 'thread') and msg.thread else None,
                        )
                    )
        except Exception as e:
            logger.error(f"Failed to fetch Discord messages: {e}")

        return messages

    async def send_typing_indicator(self, channel_id: str) -> bool:
        """Show typing indicator in a Discord channel."""
        if self._bot:
            try:
                channel = self._bot.get_channel(int(channel_id))
                if channel:
                    await channel.typing()
                    return True
            except Exception as e:
                logger.warning(f"Could not send typing indicator: {e}")
        return False

    async def react_to_message(
        self, channel_id: str, message_id: str, emoji: str
    ) -> bool:
        """Add a reaction to a Discord message."""
        if self._bot:
            try:
                channel = self._bot.get_channel(int(channel_id))
                if channel:
                    msg = await channel.fetch_message(int(message_id))
                    await msg.add_reaction(emoji)
                    return True
            except Exception as e:
                logger.warning(f"Could not add reaction: {e}")
        return False
