"""
Slack connector implementation for Promaia.

This module provides a Slack Web API connector that integrates with the existing
Promaia architecture for message synchronization and storage.

Uses the slack-sdk for API access. Requires a bot token with appropriate OAuth scopes:
- channels:history     — Read public channel messages
- groups:history       — Read private channel messages
- channels:read        — List and get info about channels
- groups:read          — List and get info about private channels
- users:read           — Get user info for display names
- files:read           — Access shared files/attachments
- reactions:read       — Read reactions on messages
"""
from __future__ import annotations

import os
import json
import logging
import asyncio
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List, Optional, Union
from pathlib import Path

from .base import BaseConnector, QueryFilter, DateRangeFilter, SyncResult

logger = logging.getLogger(__name__)

# Lazy import for slack_sdk
_slack_sdk = None


def _ensure_slack_imported():
    """Ensure slack-sdk is imported. Raises ImportError if not available."""
    global _slack_sdk
    if _slack_sdk is None:
        try:
            import slack_sdk
            _slack_sdk = slack_sdk
        except ImportError:
            raise ImportError(
                "Slack integration requires slack-sdk\n"
                "Install with: pip install slack-sdk"
            )


class SlackConnector(BaseConnector):
    """Slack Web API connector for message synchronization."""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        _ensure_slack_imported()

        self.workspace = config.get("workspace", "koii")
        self.bot_token = config.get("bot_token") or os.environ.get("SLACK_BOT_TOKEN")

        self._client = None
        self._connected = False
        self._user_cache: Dict[str, Dict[str, Any]] = {}  # user_id -> user info

        # Rate limiting — Slack Tier 3 methods allow ~50 req/min
        self._last_request_time = 0
        self._rate_limit_delay = 1.2  # Conservative: ~50 req/min

    def _get_client(self):
        """Get or create the Slack WebClient."""
        if self._client is None:
            from slack_sdk import WebClient
            self._client = WebClient(token=self.bot_token)
        return self._client

    async def _rate_limit(self):
        """Ensure we don't exceed Slack's rate limits."""
        current_time = asyncio.get_event_loop().time()
        time_since_last = current_time - self._last_request_time
        if time_since_last < self._rate_limit_delay:
            await asyncio.sleep(self._rate_limit_delay - time_since_last)
        self._last_request_time = asyncio.get_event_loop().time()

    async def connect(self) -> bool:
        """Establish connection to Slack API using bot token."""
        try:
            if not self.bot_token:
                raise ValueError(
                    "Slack bot token not provided. "
                    "Set SLACK_BOT_TOKEN in environment or pass bot_token in config."
                )

            client = self._get_client()

            # Test the connection with auth.test
            await self._rate_limit()
            result = client.auth_test()

            if result["ok"]:
                self._connected = True
                bot_user = result.get("user", "unknown")
                team = result.get("team", "unknown")
                self.logger.info(f"Slack connector authenticated as {bot_user} in workspace {team}")
                return True
            else:
                self.logger.error(f"Slack auth failed: {result.get('error', 'unknown')}")
                return False

        except Exception as e:
            self.logger.error(f"Failed to connect to Slack: {e}")
            return False

    async def test_connection(self) -> bool:
        """Test if the Slack connection is working."""
        try:
            if not self._connected:
                return await self.connect()

            client = self._get_client()
            await self._rate_limit()
            result = client.auth_test()
            return result.get("ok", False)

        except Exception as e:
            self.logger.error(f"Slack connection test failed: {e}")
            return False

    async def get_database_schema(self) -> Dict[str, Any]:
        """Get the schema/properties for Slack messages."""
        return {
            "user_id": {"type": "text", "description": "Message author user ID"},
            "user_name": {"type": "text", "description": "Message author username"},
            "display_name": {"type": "text", "description": "Message author display name"},
            "channel_id": {"type": "text", "description": "Channel ID where message was sent"},
            "channel_name": {"type": "text", "description": "Channel name"},
            "text": {"type": "text", "description": "Message text content"},
            "ts": {"type": "date", "description": "Message timestamp (Slack ts format)"},
            "thread_ts": {"type": "text", "description": "Thread parent timestamp"},
            "subtype": {"type": "select", "description": "Message subtype (bot_message, channel_join, etc.)"},
            "has_files": {"type": "checkbox", "description": "Has file attachments"},
            "file_count": {"type": "number", "description": "Number of file attachments"},
            "reaction_count": {"type": "number", "description": "Number of reactions"},
            "reply_count": {"type": "number", "description": "Number of thread replies"},
        }

    # ======== Channel Discovery ========

    async def discover_accessible_channels(self) -> Dict[str, Any]:
        """
        Discover all channels the bot has access to.

        Returns:
            Dict with 'channels' list containing channel info dicts
        """
        client = self._get_client()
        channels = []
        cursor = None

        try:
            while True:
                await self._rate_limit()

                params = {"limit": 200, "types": "public_channel,private_channel"}
                if cursor:
                    params["cursor"] = cursor

                result = client.conversations_list(**params)

                if not result["ok"]:
                    self.logger.error(f"Failed to list channels: {result.get('error')}")
                    break

                for ch in result.get("channels", []):
                    # Only include channels the bot is a member of
                    if ch.get("is_member", False):
                        channels.append({
                            "id": ch["id"],
                            "name": ch.get("name", ""),
                            "is_private": ch.get("is_private", False),
                            "is_archived": ch.get("is_archived", False),
                            "num_members": ch.get("num_members", 0),
                            "topic": ch.get("topic", {}).get("value", ""),
                            "purpose": ch.get("purpose", {}).get("value", ""),
                        })

                # Pagination
                cursor = result.get("response_metadata", {}).get("next_cursor")
                if not cursor:
                    break

        except Exception as e:
            self.logger.error(f"Error discovering Slack channels: {e}")

        self.logger.info(f"Discovered {len(channels)} accessible Slack channels")
        return {"channels": channels}

    # ======== User Resolution ========

    async def _resolve_user(self, user_id: str) -> Dict[str, Any]:
        """Resolve a Slack user ID to profile info, with caching."""
        if user_id in self._user_cache:
            return self._user_cache[user_id]

        try:
            client = self._get_client()
            await self._rate_limit()
            result = client.users_info(user=user_id)

            if result["ok"]:
                user = result["user"]
                profile = user.get("profile", {})
                info = {
                    "id": user_id,
                    "name": user.get("name", "unknown"),
                    "real_name": user.get("real_name", profile.get("real_name", "")),
                    "display_name": profile.get("display_name", "") or user.get("name", ""),
                    "is_bot": user.get("is_bot", False),
                }
                self._user_cache[user_id] = info
                return info
        except Exception as e:
            self.logger.debug(f"Could not resolve user {user_id}: {e}")

        # Fallback
        fallback = {"id": user_id, "name": user_id, "real_name": "", "display_name": user_id, "is_bot": False}
        self._user_cache[user_id] = fallback
        return fallback

    # ======== Message Fetching ========

    async def query_pages(
        self,
        filters: Optional[List[QueryFilter]] = None,
        date_filter: Optional[DateRangeFilter] = None,
        sort_by: Optional[str] = None,
        sort_direction: str = "desc",
        limit: Optional[int] = None,
        complex_filter: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Query messages from Slack channels."""
        if not self._connected:
            await self.connect()

        try:
            # Determine which channels to query
            channel_ids = self._extract_channel_filters(filters, complex_filter)

            if not channel_ids:
                # No filter — query all accessible channels
                discovery = await self.discover_accessible_channels()
                channel_ids = [ch["id"] for ch in discovery.get("channels", []) if not ch.get("is_archived")]
                self.logger.info(f"No channel filter — querying all {len(channel_ids)} accessible channels")

            all_messages = []
            for channel_id in channel_ids:
                messages = await self._fetch_channel_messages(
                    channel_id=channel_id,
                    date_filter=date_filter,
                    limit=limit,
                )
                all_messages.extend(messages)

            # Sort
            if sort_direction == "desc":
                all_messages.sort(key=lambda m: m.get("ts", "0"), reverse=True)
            else:
                all_messages.sort(key=lambda m: m.get("ts", "0"))

            # Apply limit
            if limit:
                all_messages = all_messages[:limit]

            return all_messages

        except Exception as e:
            self.logger.error(f"Failed to query Slack messages: {e}")
            return []

    async def _fetch_channel_messages(
        self,
        channel_id: str,
        date_filter: Optional[DateRangeFilter] = None,
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Fetch messages from a single Slack channel."""
        client = self._get_client()
        messages = []
        cursor = None
        page_limit = min(limit or 200, 200)  # Slack max is 200 per page

        # Build API params
        params: Dict[str, Any] = {"channel": channel_id, "limit": page_limit}

        if date_filter:
            if date_filter.start_date:
                params["oldest"] = str(date_filter.start_date.timestamp())
            if date_filter.end_date:
                params["latest"] = str(date_filter.end_date.timestamp())

        try:
            # Get channel name for metadata
            channel_name = await self._get_channel_name(channel_id)

            while True:
                await self._rate_limit()
                if cursor:
                    params["cursor"] = cursor

                result = client.conversations_history(**params)

                if not result["ok"]:
                    self.logger.error(f"Failed to fetch messages from {channel_id}: {result.get('error')}")
                    break

                for msg in result.get("messages", []):
                    # Skip subtypes we don't care about
                    subtype = msg.get("subtype")
                    if subtype in ("channel_join", "channel_leave", "channel_topic", "channel_purpose"):
                        continue

                    # Resolve user info
                    user_id = msg.get("user", "")
                    user_info = await self._resolve_user(user_id) if user_id else {}

                    # Parse timestamp
                    ts = msg.get("ts", "0")
                    try:
                        msg_datetime = datetime.fromtimestamp(float(ts), tz=timezone.utc)
                    except (ValueError, OSError):
                        msg_datetime = datetime.now(timezone.utc)

                    # Build normalized message structure
                    normalized = {
                        "page_id": f"slack-{channel_id}-{ts}",
                        "title": f"Message from {user_info.get('display_name', user_id)} in #{channel_name}",
                        "content": msg.get("text", ""),
                        "properties": {
                            "user_id": user_id,
                            "user_name": user_info.get("name", ""),
                            "display_name": user_info.get("display_name", ""),
                            "channel_id": channel_id,
                            "channel_name": channel_name,
                            "ts": ts,
                            "thread_ts": msg.get("thread_ts"),
                            "subtype": subtype,
                            "has_files": bool(msg.get("files")),
                            "file_count": len(msg.get("files", [])),
                            "reaction_count": sum(r.get("count", 0) for r in msg.get("reactions", [])),
                            "reply_count": msg.get("reply_count", 0),
                            "timestamp": msg_datetime.isoformat(),
                        },
                        "timestamp": msg_datetime,
                        "database": f"slack",
                    }

                    # Include file metadata if present
                    if msg.get("files"):
                        normalized["attachments"] = [
                            {
                                "id": f.get("id"),
                                "name": f.get("name", ""),
                                "mimetype": f.get("mimetype", ""),
                                "size": f.get("size", 0),
                                "url_private": f.get("url_private", ""),
                                "url_private_download": f.get("url_private_download", ""),
                            }
                            for f in msg["files"]
                        ]

                    # Include reactions
                    if msg.get("reactions"):
                        normalized["reactions"] = [
                            {"name": r["name"], "count": r["count"]}
                            for r in msg["reactions"]
                        ]

                    messages.append(normalized)

                # Pagination
                if not result.get("has_more", False):
                    break
                cursor = result.get("response_metadata", {}).get("next_cursor")
                if not cursor:
                    break

                # Check limit
                if limit and len(messages) >= limit:
                    break

            self.logger.info(f"Fetched {len(messages)} messages from #{channel_name} ({channel_id})")

        except Exception as e:
            self.logger.error(f"Error fetching messages from channel {channel_id}: {e}")

        return messages

    async def _get_channel_name(self, channel_id: str) -> str:
        """Get channel name from ID."""
        try:
            client = self._get_client()
            await self._rate_limit()
            result = client.conversations_info(channel=channel_id)
            if result["ok"]:
                return result["channel"].get("name", channel_id)
        except Exception:
            pass
        return channel_id

    # ======== Content & Properties (BaseConnector interface) ========

    async def get_page_content(self, page_id: str, include_properties: bool = True) -> Dict[str, Any]:
        """Get full content of a specific message by page_id."""
        # page_id format: slack-{channel_id}-{ts}
        parts = page_id.split("-", 2)
        if len(parts) < 3 or parts[0] != "slack":
            return {"error": f"Invalid Slack page_id: {page_id}"}

        channel_id = parts[1]
        ts = parts[2]

        try:
            client = self._get_client()
            await self._rate_limit()

            # Fetch specific message using conversations.history with latest/oldest=ts
            result = client.conversations_history(
                channel=channel_id, latest=ts, oldest=ts, inclusive=True, limit=1
            )

            if result["ok"] and result.get("messages"):
                msg = result["messages"][0]
                user_info = await self._resolve_user(msg.get("user", ""))
                return {
                    "page_id": page_id,
                    "content": msg.get("text", ""),
                    "user": user_info,
                    "ts": ts,
                    "channel_id": channel_id,
                    "files": msg.get("files", []),
                    "reactions": msg.get("reactions", []),
                }

        except Exception as e:
            self.logger.error(f"Error fetching message {page_id}: {e}")

        return {"page_id": page_id, "error": "Message not found"}

    async def get_page_properties(self, page_id: str) -> Dict[str, Any]:
        """Get properties of a specific message."""
        content = await self.get_page_content(page_id)
        return content.get("properties", content)

    # ======== Sync to Local ========

    async def sync_to_local(
        self,
        output_directory: str,
        filters: Optional[List[QueryFilter]] = None,
        date_filter: Optional[DateRangeFilter] = None,
        include_properties: bool = True,
        force_update: bool = False,
        excluded_properties: List[str] = None,
    ) -> SyncResult:
        """Sync Slack messages to local markdown storage."""
        result = SyncResult()
        result.start_time = datetime.now(timezone.utc)
        result.database_name = f"slack-{self.workspace}"

        if not self._connected:
            await self.connect()

        try:
            messages = await self.query_pages(
                filters=filters, date_filter=date_filter
            )
            result.pages_fetched = len(messages)

            output_path = Path(output_directory)
            output_path.mkdir(parents=True, exist_ok=True)

            for msg in messages:
                try:
                    # Build markdown content
                    md_content = self._message_to_markdown(msg)
                    page_id = msg.get("page_id", "unknown")

                    # Determine filename
                    props = msg.get("properties", {})
                    channel_name = props.get("channel_name", "unknown")
                    ts = props.get("ts", "0")
                    display_name = props.get("display_name", "unknown")

                    # Create channel subdirectory
                    channel_dir = output_path / channel_name
                    channel_dir.mkdir(exist_ok=True)

                    # Write file
                    filename = f"{ts}_{display_name}.md"
                    filepath = channel_dir / filename

                    if filepath.exists() and not force_update:
                        result.add_skip()
                        continue

                    filepath.write_text(md_content, encoding="utf-8")
                    result.add_success(str(filepath))

                except Exception as e:
                    result.add_error(f"Error saving message {msg.get('page_id')}: {e}")

        except Exception as e:
            result.add_error(f"Sync failed: {e}")

        result.end_time = datetime.now(timezone.utc)
        return result

    def _message_to_markdown(self, msg: Dict[str, Any]) -> str:
        """Convert a normalized message to markdown format."""
        props = msg.get("properties", {})
        content = msg.get("content", "")

        lines = [
            f"# Message from {props.get('display_name', 'unknown')}",
            f"",
            f"**Channel:** #{props.get('channel_name', 'unknown')}",
            f"**Timestamp:** {props.get('timestamp', '')}",
            f"**User:** {props.get('display_name', '')} (@{props.get('user_name', '')})",
        ]

        if props.get("thread_ts"):
            lines.append(f"**Thread:** {props['thread_ts']}")
        if props.get("reply_count"):
            lines.append(f"**Replies:** {props['reply_count']}")
        if props.get("reaction_count"):
            lines.append(f"**Reactions:** {props['reaction_count']}")

        lines.extend(["", "---", "", content])

        # Attachments
        attachments = msg.get("attachments", [])
        if attachments:
            lines.extend(["", "## Attachments", ""])
            for att in attachments:
                lines.append(f"- [{att.get('name', 'file')}] ({att.get('mimetype', '')}, {att.get('size', 0)} bytes)")

        # Reactions
        reactions = msg.get("reactions", [])
        if reactions:
            lines.extend(["", "## Reactions", ""])
            for r in reactions:
                lines.append(f"- :{r['name']}: × {r['count']}")

        return "\n".join(lines)

    # ======== Unified Sync (hybrid storage) ========

    async def sync_to_local_unified(
        self,
        db_config,
        date_filter: Optional[DateRangeFilter] = None,
        message_limit: Optional[int] = None,
        channel_ids: Optional[List[str]] = None,
        **kwargs,
    ) -> SyncResult:
        """
        Sync Slack messages using the unified hybrid storage pipeline.

        This mirrors DiscordConnector.sync_to_local_unified for consistency.
        """
        from promaia.storage.hybrid_storage import get_hybrid_registry
        from promaia.storage.content_writer import ContentWriter

        result = SyncResult()
        result.start_time = datetime.now(timezone.utc)
        result.database_name = db_config.get_qualified_name() if hasattr(db_config, 'get_qualified_name') else "slack"

        if not self._connected:
            await self.connect()

        try:
            # Build filters from channel_ids
            filters = None
            if channel_ids:
                filters = [QueryFilter("channel_id", "in", channel_ids)]
            elif hasattr(db_config, 'property_filters') and db_config.property_filters.get('channel_id'):
                ch_filter = db_config.property_filters['channel_id']
                if isinstance(ch_filter, str):
                    ch_filter = [ch_filter]
                filters = [QueryFilter("channel_id", "in", ch_filter)]

            messages = await self.query_pages(filters=filters, date_filter=date_filter, limit=message_limit)
            result.pages_fetched = len(messages)

            # Write to hybrid storage
            registry = get_hybrid_registry()
            writer = ContentWriter()

            for msg in messages:
                try:
                    page_id = msg.get("page_id", "")
                    content = msg.get("content", "")
                    title = msg.get("title", "Slack message")
                    props = msg.get("properties", {})
                    timestamp = msg.get("timestamp")

                    # Build metadata for registry
                    metadata = {
                        "source_type": "slack",
                        "slack_channel_id": props.get("channel_id", ""),
                        "slack_channel_name": props.get("channel_name", ""),
                        "slack_user_id": props.get("user_id", ""),
                        "slack_display_name": props.get("display_name", ""),
                        "slack_ts": props.get("ts", ""),
                        "timestamp": timestamp.isoformat() if timestamp else None,
                        "has_files": props.get("has_files", False),
                    }

                    # Write through unified pipeline
                    md_content = self._message_to_markdown(msg)
                    filepath = writer.write_content(
                        content=md_content,
                        page_id=page_id,
                        title=title,
                        workspace=self.workspace,
                        database_name=result.database_name,
                        metadata=metadata,
                    )

                    if filepath:
                        result.add_success(str(filepath))
                    else:
                        result.add_skip()

                except Exception as e:
                    result.add_error(f"Error saving message: {e}")

        except Exception as e:
            result.add_error(f"Unified sync failed: {e}")

        result.end_time = datetime.now(timezone.utc)
        self.logger.info(
            f"Slack sync complete: {result.pages_saved} saved, "
            f"{result.pages_skipped} skipped, {result.pages_failed} failed "
            f"({result.duration_seconds:.1f}s)"
        )
        return result

    # ======== Helpers ========

    def _extract_channel_filters(
        self,
        filters: Optional[List[QueryFilter]],
        complex_filter: Optional[Dict[str, Any]] = None,
    ) -> List[str]:
        """Extract channel IDs from query filters."""
        channel_ids = []

        if filters:
            for f in filters:
                if f.property_name == "channel_id":
                    if isinstance(f.value, list):
                        channel_ids.extend(f.value)
                    else:
                        channel_ids.append(f.value)

        if complex_filter and "channel_id" in complex_filter:
            val = complex_filter["channel_id"]
            if isinstance(val, list):
                channel_ids.extend(val)
            else:
                channel_ids.append(val)

        return list(set(channel_ids))
