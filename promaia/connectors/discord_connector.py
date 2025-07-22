"""
Discord connector implementation for Maia.

This module provides a Discord bot API connector that integrates with the existing
Maia architecture for message synchronization and storage.
"""
import os
import json
import logging
import asyncio
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List, Optional, Union
from pathlib import Path

try:
    import discord
    from discord.ext import commands
except ImportError:
    print("Discord integration requires discord.py")
    print("Install with: pip install discord.py")
    raise

from .base import BaseConnector, QueryFilter, DateRangeFilter, SyncResult

logger = logging.getLogger(__name__)

class DiscordConnector(BaseConnector):
    """Discord bot API connector for message synchronization."""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        
        self.server_id = config.get("database_id")  # Use server_id as database_id for consistency
        self.workspace = config.get("workspace", "koii")
        
        # Bot configuration
        self.bot_token = config.get("bot_token")
        self.intents = discord.Intents.default()
        self.intents.message_content = True  # Required to read message content
        self.intents.guilds = True
        self.intents.guild_messages = True
        
        self.client = None
        self.guild = None
        self._connected = False
        
        # Rate limiting for API compliance (1 request per second for message history)
        self._last_request_time = 0
        self._rate_limit_delay = 1.0  # 1 second between requests
        
    async def _rate_limit(self):
        """Ensure we don't exceed Discord's rate limits."""
        current_time = asyncio.get_event_loop().time()
        time_since_last = current_time - self._last_request_time
        
        if time_since_last < self._rate_limit_delay:
            sleep_time = self._rate_limit_delay - time_since_last
            await asyncio.sleep(sleep_time)
        
        self._last_request_time = asyncio.get_event_loop().time()

    async def connect(self) -> bool:
        """Establish connection to Discord API using bot token."""
        try:
            if not self.bot_token:
                raise ValueError("Discord bot token not provided in config")
            
            # For data access, we'll use a temporary client approach
            # Store connection info for later use
            self._connected = True
            
            self.logger.info(f"Discord connector initialized for server {self.server_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to connect to Discord: {e}")
            return False
    
    async def _get_guild_data(self):
        """Get guild data using a temporary client connection."""
        if not self.bot_token or not self.server_id:
            return None
            
        # Create temporary client for data access
        client = discord.Client(intents=self.intents)
        
        try:
            await client.login(self.bot_token)
            
            # Get guild using HTTP API (no gateway connection needed)
            guild = await client.fetch_guild(int(self.server_id))
            channels = await guild.fetch_channels()
            
            # Convert to simple data structure
            guild_data = {
                'id': guild.id,
                'name': guild.name,
                'channels': []
            }
            
            for channel in channels:
                if hasattr(channel, 'send'):  # Text channel
                    guild_data['channels'].append({
                        'id': channel.id,
                        'name': channel.name,
                        'type': 'text'
                    })
            
            return guild_data
            
        finally:
            await client.close()

    async def test_connection(self) -> bool:
        """Test if the Discord connection is working."""
        if not self.client:
            if not await self.connect():
                return False
        
        try:
            # Test basic API access
            if self.guild:
                # Guild channels should be available after connection
                channels = self.guild.channels
                self.logger.info(f"Connected to Discord server: {self.guild.name}")
            return True
        except Exception as e:
            self.logger.error(f"Discord connection test failed: {e}")
            return False

    async def get_database_schema(self) -> Dict[str, Any]:
        """Get the schema/properties for Discord messages."""
        return {
            "author_id": {"type": "text", "description": "Message author user ID"},
            "author_name": {"type": "text", "description": "Message author username"},
            "author_display_name": {"type": "text", "description": "Message author display name"},
            "channel_id": {"type": "text", "description": "Channel ID where message was sent"},
            "channel_name": {"type": "text", "description": "Channel name"},
            "content": {"type": "text", "description": "Message content"},
            "timestamp": {"type": "date", "description": "Message timestamp"},
            "edited_timestamp": {"type": "date", "description": "Last edit timestamp"},
            "message_type": {"type": "select", "description": "Type of message (default, reply, etc.)"},
            "has_attachments": {"type": "checkbox", "description": "Has file attachments"},
            "attachment_count": {"type": "number", "description": "Number of attachments"},
            "has_embeds": {"type": "checkbox", "description": "Has embedded content"},
            "reaction_count": {"type": "number", "description": "Number of reactions"},
            "thread_id": {"type": "text", "description": "Thread ID if message is in a thread"},
            "reference_message_id": {"type": "text", "description": "ID of referenced message (for replies)"},
        }

    async def query_pages(self, 
                         filters: Optional[List[QueryFilter]] = None,
                         date_filter: Optional[DateRangeFilter] = None,
                         sort_by: Optional[str] = None,
                         sort_direction: str = "desc",
                         limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Query messages from Discord channels."""
        if not self._connected:
            await self.connect()
        
        try:
            # Get channel to sync (for now, sync one channel at a time)
            channel_id = self._extract_channel_filter(filters)
            if not channel_id:
                self.logger.error("No channel specified in filters")
                return []
            
            # Create temporary client for message fetching
            client = discord.Client(intents=self.intents)
            
            try:
                await client.login(self.bot_token)
                guild = await client.fetch_guild(int(self.server_id))
                channel = await guild.fetch_channel(int(channel_id))
                
                if not channel:
                    self.logger.error(f"Could not access channel {channel_id}")
                    return []
                
                # Apply rate limiting
                await self._rate_limit()
                
                # Calculate date range for filtering
                after_date = None
                before_date = None
                if date_filter:
                    after_date = date_filter.start_date
                    before_date = date_filter.end_date
                
                # Fetch messages with pagination
                messages = []
                async for message in channel.history(
                    limit=limit,
                    after=after_date,
                    before=before_date,
                    oldest_first=(sort_direction == "asc")
                ):
                    message_data = await self._convert_message_to_data(message)
                    messages.append(message_data)
                    
                    # Apply rate limiting between message fetches for large syncs
                    if len(messages) % 50 == 0:  # Every 50 messages
                        await self._rate_limit()
                
                self.logger.info(f"Found {len(messages)} messages in channel {channel.name}")
                return messages
                
            finally:
                await client.close()
            
        except Exception as e:
            self.logger.error(f"Failed to query Discord messages: {e}")
            return []

    async def get_page_content(self, page_id: str, include_properties: bool = True) -> Dict[str, Any]:
        """Get full content of a specific Discord message."""
        # page_id format: "msg_{message_id}"
        message_id = page_id.replace('msg_', '')
        
        try:
            # We need channel context to fetch a specific message
            # This is a limitation of Discord API - we need to know which channel
            # For now, search through all accessible channels
            for channel in self.guild.text_channels:
                try:
                    await self._rate_limit()
                    message = await channel.fetch_message(int(message_id))
                    return await self._convert_message_to_data(message)
                except discord.NotFound:
                    continue
                except discord.Forbidden:
                    continue
            
            self.logger.warning(f"Message {message_id} not found in any accessible channel")
            return {}
            
        except Exception as e:
            self.logger.error(f"Failed to get Discord message content for {page_id}: {e}")
            return {}

    async def get_page_properties(self, page_id: str) -> Dict[str, Any]:
        """Get properties of a specific Discord message."""
        content = await self.get_page_content(page_id, include_properties=True)
        
        return {
            "author_id": content.get("author_id"),
            "author_name": content.get("author_name"),
            "channel_id": content.get("channel_id"),
            "channel_name": content.get("channel_name"),
            "timestamp": content.get("timestamp"),
            "content": content.get("content"),
            "has_attachments": content.get("has_attachments", False),
            "has_embeds": content.get("has_embeds", False),
        }

    async def sync_to_local(self, 
                           output_directory: str,
                           filters: Optional[List[QueryFilter]] = None,
                           date_filter: Optional[DateRangeFilter] = None,
                           include_properties: bool = True,
                           force_update: bool = False,
                           excluded_properties: List[str] = None) -> SyncResult:
        """Sync Discord messages to local storage - placeholder for backwards compatibility."""
        # This will be implemented as sync_to_local_unified following the pattern
        raise NotImplementedError("Use sync_to_local_unified for Discord connector")

    async def sync_to_local_unified(self, 
                                   storage,
                                   db_config,
                                   filters: Optional[List[QueryFilter]] = None,
                                   date_filter: Optional[DateRangeFilter] = None,
                                   include_properties: bool = True,
                                   force_update: bool = False,
                                   excluded_properties: List[str] = None) -> SyncResult:
        """Sync Discord messages to local storage using unified storage system."""
        result = SyncResult()
        result.start_time = datetime.now()
        
        try:
            limit = self.config.get("sync_limit", 100)
            
            # Query Discord for recent messages
            self.logger.info(f"Querying Discord with date_filter: {date_filter}")
            messages = await self.query_pages(
                filters=filters, 
                date_filter=date_filter,
                limit=limit
            )
            
            if not messages:
                self.logger.info("No new Discord messages found from query.")
                return result
            
            self.logger.info(f"Found {len(messages)} Discord messages from query.")
            result.pages_fetched = len(messages)
            
            pages_to_save = []
            for message in messages:
                # Prepare page data for unified storage
                page_data = self._prepare_page_for_storage(message, db_config, excluded_properties)
                pages_to_save.append(page_data)
            
            if not pages_to_save:
                self.logger.info("No new or updated messages to save after filtering.")
                return result
            
            # Process pages with proper skipping logic  
            saved_count = 0
            skipped_count = 0
            
            for page_data in pages_to_save:
                try:
                    # Save using unified storage (JSON format)
                    saved_files = storage.save_content(
                        page_id=page_data["page_id"],
                        title=page_data["metadata"]["title"],
                        content_data=page_data["metadata"],
                        database_config=db_config,
                        markdown_content=page_data["content"]
                    )
                    
                    if saved_files:
                        result.add_success(saved_files.get('markdown', ''))
                        saved_count += 1
                    else:
                        result.add_skip()
                        skipped_count += 1
                        
                except Exception as e:
                    self.logger.error(f"Error saving Discord message {page_data['page_id']}: {e}")
                    result.add_error(f"Failed to save message {page_data['page_id']}: {e}")
            
            self.logger.info(f"Discord sync completed: {saved_count} saved, {skipped_count} skipped")
            result.end_time = datetime.now()
            
            return result
            
        except Exception as e:
            self.logger.error(f"Discord sync failed: {e}")
            result.add_error(f"Discord sync failed: {e}")
            result.end_time = datetime.now()
            return result

    def _extract_channel_filter(self, filters: Optional[List[QueryFilter]]) -> Optional[str]:
        """Extract channel ID from filters."""
        if not filters:
            return None
        
        for filter_obj in filters:
            if filter_obj.property_name == "channel_id" and filter_obj.operator == "eq":
                return filter_obj.value
        
        return None

    async def _convert_message_to_data(self, message: discord.Message) -> Dict[str, Any]:
        """Convert a Discord message to our data format."""
        # Handle thread context
        thread_id = None
        if hasattr(message.channel, 'parent_id') and message.channel.parent_id:
            thread_id = str(message.channel.id)
        
        # Handle message references (replies)
        reference_message_id = None
        if message.reference and message.reference.message_id:
            reference_message_id = str(message.reference.message_id)
        
        # Process attachments
        attachments = []
        for attachment in message.attachments:
            attachments.append({
                "id": str(attachment.id),
                "filename": attachment.filename,
                "size": attachment.size,
                "url": attachment.url,
                "content_type": attachment.content_type
            })
        
        # Process embeds
        embeds = []
        for embed in message.embeds:
            embed_data = {
                "title": embed.title,
                "description": embed.description,
                "url": embed.url,
                "color": embed.color.value if embed.color else None,
                "timestamp": embed.timestamp.isoformat() if embed.timestamp else None,
            }
            if embed.author:
                embed_data["author"] = {
                    "name": embed.author.name,
                    "url": embed.author.url,
                    "icon_url": embed.author.icon_url
                }
            embeds.append(embed_data)
        
        # Process reactions
        reactions = []
        for reaction in message.reactions:
            reactions.append({
                "emoji": str(reaction.emoji),
                "count": reaction.count,
                "me": reaction.me
            })
        
        return {
            "id": f"msg_{message.id}",
            "message_id": str(message.id),
            "channel_id": str(message.channel.id),
            "channel_name": message.channel.name,
            "server_id": str(message.guild.id),
            "server_name": message.guild.name,
            "author_id": str(message.author.id),
            "author_name": message.author.name,
            "author_display_name": message.author.display_name,
            "content": message.content,
            "timestamp": message.created_at.isoformat(),
            "edited_timestamp": message.edited_at.isoformat() if message.edited_at else None,
            "message_type": str(message.type),
            "has_attachments": len(message.attachments) > 0,
            "attachment_count": len(message.attachments),
            "attachments": attachments,
            "has_embeds": len(message.embeds) > 0,
            "embeds": embeds,
            "reaction_count": len(message.reactions),
            "reactions": reactions,
            "thread_id": thread_id,
            "reference_message_id": reference_message_id,
            "pinned": message.pinned,
        }

    def _prepare_page_for_storage(self, message: Dict[str, Any], db_config, excluded_properties: List[str] = None) -> Dict[str, Any]:
        """Prepare message data for the unified storage format."""
        
        page_id = message['id']
        markdown_content = self._message_to_markdown(message)
        
        # Extract properties from message data
        properties = {
            "title": f"{message.get('author_name', 'Unknown')}: {message.get('content', '')[:50]}...",
            "author_id": message.get('author_id'),
            "author_name": message.get('author_name'),
            "channel_name": message.get('channel_name'),
            "timestamp": message.get('timestamp'),
            "has_attachments": message.get('has_attachments', False),
            "content": message.get('content', ''),
        }
        
        # Metadata for registry
        metadata = {
            "page_id": page_id,
            "title": properties["title"],
            "created_time": message.get('timestamp'),
            "last_edited_time": message.get('edited_timestamp') or message.get('timestamp'),
            "synced_time": datetime.now(timezone.utc).isoformat(),
            "source_id": message.get('message_id'),
            "data_source": "discord",
            "content_type": "message",
            "properties": properties,
            "raw_message_data": message
        }
        
        return {
            "page_id": page_id,
            "content": markdown_content,
            "metadata": metadata
        }

    def _message_to_markdown(self, message: Dict[str, Any]) -> str:
        """Convert a Discord message dictionary to a markdown string."""
        author = message.get("author_name", "Unknown")
        content = message.get("content", "")
        timestamp = message.get("timestamp", "")
        channel = message.get("channel_name", "unknown")
        
        # Parse timestamp for display
        try:
            dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            time_str = dt.strftime("%Y-%m-%d %H:%M:%S")
        except:
            time_str = timestamp
        
        # Create header
        header = f"""# Discord Message

**Author:** {author}  
**Channel:** #{channel}  
**Timestamp:** {time_str}  

---

"""
        
        # Add main content
        main_content = content if content else "*[No text content]*"
        
        # Add attachment information
        attachments_section = ""
        if message.get("has_attachments", False):
            attachments = message.get("attachments", [])
            attachments_section = "\n\n## Attachments\n\n"
            for attachment in attachments:
                attachments_section += f"- **{attachment.get('filename', 'Unknown')}** ({attachment.get('size', 0)} bytes)\n"
        
        # Add embed information
        embeds_section = ""
        if message.get("has_embeds", False):
            embeds = message.get("embeds", [])
            embeds_section = "\n\n## Embeds\n\n"
            for embed in embeds:
                if embed.get("title"):
                    embeds_section += f"### {embed['title']}\n\n"
                if embed.get("description"):
                    embeds_section += f"{embed['description']}\n\n"
        
        # Add reaction information
        reactions_section = ""
        if message.get("reaction_count", 0) > 0:
            reactions = message.get("reactions", [])
            reactions_section = "\n\n## Reactions\n\n"
            for reaction in reactions:
                reactions_section += f"{reaction.get('emoji', '?')} x{reaction.get('count', 0)}  "
        
        return header + main_content + attachments_section + embeds_section + reactions_section

    async def cleanup(self):
        """Clean up Discord connector."""
        # No persistent connections to clean up with the new approach
        pass 