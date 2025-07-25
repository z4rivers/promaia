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
            # Get channel to sync 
            channel_identifier = self._extract_channel_filter(filters)
            if not channel_identifier:
                # No specific channel filter - this shouldn't happen in normal usage
                # Users should use browse mode to select channels first
                self.logger.warning("No specific channel filter provided for Discord sync")
                self.logger.info("Use browse mode (-b) to select Discord channels before syncing")
                return []
            
            # Create temporary client for message fetching
            client = discord.Client(intents=self.intents)
            
            try:
                await client.login(self.bot_token)
                guild = await client.fetch_guild(int(self.server_id))
                
                # Fetch the channels for this guild
                guild_channels = await guild.fetch_channels()
                
                # Handle both channel ID and channel name
                if channel_identifier.startswith("name:"):
                    # Channel name filter - find channel by name (with sanitized name mapping)
                    sanitized_channel_name = channel_identifier[5:]  # Remove "name:" prefix
                    channel = None
                    
                    # First try exact match
                    for ch in guild_channels:
                        if hasattr(ch, 'send') and ch.name == sanitized_channel_name:
                            channel = ch
                            break
                    
                    # If no exact match, try reverse sanitization lookup
                    if not channel:
                        channel = self._find_channel_by_sanitized_name(guild_channels, sanitized_channel_name)
                    
                    if not channel:
                        self.logger.error(f"Channel '{sanitized_channel_name}' not found in server")
                        return []
                else:
                    # Channel ID filter - fetch by ID
                    channel = await guild.fetch_channel(int(channel_identifier))
                
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
                    # For Discord, create channel-specific subdirectories
                    channel_name = page_data.get("channel_name", "unknown")
                    
                    # Create a safe channel directory name
                    safe_channel_name = "".join(c if c.isalnum() or c in " -_" else "_" for c in channel_name)
                    safe_channel_name = safe_channel_name.strip("_").replace(" ", "_")
                    
                    # Create modified database config with channel-specific directory
                    import copy
                    discord_db_config = copy.deepcopy(db_config)
                    original_md_dir = discord_db_config.markdown_directory
                    channel_md_dir = os.path.join(original_md_dir, safe_channel_name)
                    discord_db_config.markdown_directory = channel_md_dir
                    
                    # Ensure channel directory exists
                    os.makedirs(channel_md_dir, exist_ok=True)
                    
                    # Save using unified storage with channel-specific directory
                    saved_files = storage.save_content(
                        page_id=page_data["page_id"],
                        title=page_data["metadata"]["title"],
                        content_data=page_data["metadata"],
                        database_config=discord_db_config,
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
        """Extract channel identifier from filters (supports both channel_id and channel_name)."""
        if not filters:
            return None
        
        # First, try to find channel_id filter (returns actual channel ID)
        for filter_obj in filters:
            if filter_obj.property_name == "channel_id" and filter_obj.operator == "eq":
                return filter_obj.value
        
        # If no channel_id filter, try channel_name filter (return the name, we'll handle it differently)
        for filter_obj in filters:
            if filter_obj.property_name == "channel_name" and filter_obj.operator == "eq":
                # Return the channel name prefixed to indicate it's a name, not ID
                return f"name:{filter_obj.value}"
        
        return None
    
    async def _query_all_accessible_channels(self, 
                                           date_filter: Optional[DateRangeFilter] = None,
                                           sort_direction: str = "desc", 
                                           limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Query messages from all accessible channels in the Discord server."""
        try:
            # Create temporary client for message fetching
            client = discord.Client(intents=self.intents)
            all_messages = []
            
            try:
                await client.login(self.bot_token)
                guild = await client.fetch_guild(int(self.server_id))
                
                # Get all accessible channels
                guild_channels = await guild.fetch_channels()
                text_channels = [ch for ch in guild_channels if hasattr(ch, 'send')]  # Text channels only
                
                self.logger.info(f"Found {len(text_channels)} text channels to sync")
                
                # Calculate date range for filtering
                after_date = None
                before_date = None
                if date_filter:
                    after_date = date_filter.start_date
                    before_date = date_filter.end_date
                
                # Query each channel
                for channel in text_channels:
                    try:
                        # Apply rate limiting between channels
                        await self._rate_limit()
                        
                        # Determine per-channel limit
                        channel_limit = limit // len(text_channels) if limit else 100
                        if channel_limit < 10:  # Ensure minimum per channel
                            channel_limit = 10
                        
                        channel_messages = []
                        async for message in channel.history(
                            limit=channel_limit,
                            after=after_date,
                            before=before_date,
                            oldest_first=(sort_direction == "asc")
                        ):
                            message_data = await self._convert_message_to_data(message)
                            channel_messages.append(message_data)
                            
                            # Apply rate limiting for large channel syncs
                            if len(channel_messages) % 50 == 0:
                                await self._rate_limit()
                        
                        if channel_messages:
                            self.logger.info(f"Found {len(channel_messages)} messages in channel #{channel.name}")
                            all_messages.extend(channel_messages)
                        
                    except discord.Forbidden:
                        self.logger.warning(f"No access to channel #{channel.name}")
                        continue
                    except Exception as e:
                        self.logger.warning(f"Error fetching from channel #{channel.name}: {e}")
                        continue
                
                # Sort all messages by timestamp if needed
                if sort_direction == "desc":
                    all_messages.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
                else:
                    all_messages.sort(key=lambda x: x.get('timestamp', ''))
                
                # Apply global limit after sorting
                if limit and len(all_messages) > limit:
                    all_messages = all_messages[:limit]
                
                self.logger.info(f"Total messages collected from all channels: {len(all_messages)}")
                return all_messages
                
            finally:
                await client.close()
                
        except Exception as e:
            self.logger.error(f"Failed to query all Discord channels: {e}")
            return []
    
    def _find_channel_by_sanitized_name(self, channels, sanitized_name: str):
        """Find a Discord channel by its sanitized name (reverse lookup)."""
        for channel in channels:
            if hasattr(channel, 'send'):  # Text channel
                # Apply the same sanitization logic used when saving files
                safe_channel_name = "".join(c if c.isalnum() or c in " -_" else "_" for c in channel.name)
                safe_channel_name = safe_channel_name.strip("_").replace(" ", "_")
                
                if safe_channel_name == sanitized_name:
                    self.logger.info(f"Mapped sanitized name '{sanitized_name}' to Discord channel '{channel.name}'")
                    return channel
        
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
        
        # Extract channel information for Discord-specific organization
        channel_name = message.get('channel_name', 'unknown')
        channel_id = message.get('channel_id', 'unknown')

        # Format timestamp for filename
        timestamp_str = "unknown_time"
        if message.get('timestamp'):
            try:
                dt = datetime.fromisoformat(message['timestamp'].replace('Z', '+00:00'))
                timestamp_str = dt.strftime("%Y-%m-%d_%H-%M-%S")
            except ValueError:
                pass

        # Create a filename-safe title
        author_name = message.get('author_name', 'Unknown')
        
        # New filename format: YYYY-MM-DD_HH-MM-SS_author_msg_id.md
        filename_title = f"{timestamp_str}_{author_name}_{page_id}"

        # Extract properties from message data
        properties = {
            "title": filename_title,
            "author_id": message.get('author_id'),
            "author_name": message.get('author_name'),
            "channel_name": channel_name,
            "channel_id": channel_id,
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
            "raw_message_data": message,
            # Add Discord-specific channel information
            "discord_channel_name": channel_name,
            "discord_channel_id": channel_id,
            "discord_server_id": message.get('server_id'),
            "discord_server_name": message.get('server_name')
        }
        
        return {
            "page_id": page_id,
            "content": markdown_content,
            "metadata": metadata,
            # Add channel info for storage path organization
            "channel_name": channel_name,
            "channel_id": channel_id
        }

    def _message_to_markdown(self, message: Dict[str, Any]) -> str:
        """Convert a Discord message dictionary to a markdown string."""
        content = message.get("content", "")
        
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
        
        return main_content + attachments_section + embeds_section + reactions_section

    async def list_server_channels(self):
        """Debug method to list all channels in the Discord server."""
        if not self.bot_token or not self.server_id:
            self.logger.error("Bot token or server ID not available")
            return []
            
        # Create temporary client for data access
        client = discord.Client(intents=self.intents)
        
        try:
            await client.login(self.bot_token)
            guild = await client.fetch_guild(int(self.server_id))
            
            print(f'🎮 Discord Server: {guild.name} (ID: {guild.id})')
            print('📢 Available Channels:')
            
            channels = await guild.fetch_channels()
            text_channels = []
            
            for channel in channels:
                if hasattr(channel, 'send'):  # Text channel
                    print(f'  #{channel.name} (ID: {channel.id})')
                    text_channels.append({
                        'name': channel.name,
                        'id': str(channel.id)
                    })
                    
            return text_channels
            
        except Exception as e:
            self.logger.error(f"Error listing Discord channels: {e}")
            return []
        finally:
            await client.close()

    async def test_channel_access(self, channel, guild) -> bool:
        """Test if the bot has read access to a specific channel using permissions."""
        try:
            # Get the bot's user ID from the client
            bot_user_id = guild._state.self_id if hasattr(guild._state, 'self_id') else None
            if not bot_user_id:
                # Fallback to current user from guild
                bot_user_id = guild._state.user.id if hasattr(guild._state, 'user') else None
            
            if bot_user_id:
                # Get bot member object
                bot_member = guild.get_member(bot_user_id)
                if not bot_member:
                    bot_member = await guild.fetch_member(bot_user_id)
                
                # Check permissions directly (much faster than reading messages)
                permissions = channel.permissions_for(bot_member)
                
                # Check for all required read permissions
                has_read_permission = (
                    permissions.read_messages and 
                    permissions.read_message_history and 
                    permissions.view_channel
                )
                
                return has_read_permission
            else:
                # If we can't get bot ID, fall back to message test
                raise Exception("Could not determine bot user ID")
            
        except Exception as e:
            self.logger.debug(f"Error testing channel permissions for {channel.name}: {e}")
            # Fallback to message reading test if permissions check fails
            try:
                async for _ in channel.history(limit=1):
                    return True
                return True
            except discord.Forbidden:
                return False
            except Exception:
                return False

    async def discover_accessible_channels(self) -> Dict[str, Any]:
        """Discover all channels the bot has read access to."""
        if not self.bot_token or not self.server_id:
            self.logger.error("Bot token or server ID not available")
            return {"server_name": "Unknown", "channels": []}
            
        # Create temporary client for data access
        client = discord.Client(intents=self.intents)
        
        try:
            await client.login(self.bot_token)
            guild = await client.fetch_guild(int(self.server_id))
            
            # Get bot member once for efficiency
            bot_user_id = client.user.id
            bot_member = guild.get_member(bot_user_id)
            if not bot_member:
                bot_member = await guild.fetch_member(bot_user_id)
            
            channels = await guild.fetch_channels()
            
            accessible_channels = []
            tested_count = 0
            
            # Filter to only text channels first
            text_channels = [ch for ch in channels if hasattr(ch, 'send')]
            self.logger.info(f"Testing {len(text_channels)} text channels for read permissions...")
            
            for channel in text_channels:
                tested_count += 1
                
                # Fast permission check using pre-fetched bot member
                try:
                    permissions = channel.permissions_for(bot_member)
                    has_read_permission = (
                        permissions.read_messages and 
                        permissions.read_message_history and 
                        permissions.view_channel
                    )
                    
                    if has_read_permission:
                        accessible_channels.append({
                            'name': channel.name,
                            'id': str(channel.id),
                            'discovered_at': datetime.now().isoformat()
                        })
                        self.logger.debug(f"✓ #{channel.name} - readable")
                    else:
                        self.logger.debug(f"✗ #{channel.name} - no read access")
                        
                except Exception as e:
                    self.logger.debug(f"! #{channel.name} - permission check failed: {e}")
                
                # Progress indicator for large servers
                if tested_count % 20 == 0:
                    self.logger.info(f"Tested {tested_count}/{len(text_channels)} channels...")
                    
            self.logger.info(f"Discovery complete: {len(accessible_channels)}/{len(text_channels)} channels accessible")
                    
            return {
                "server_name": guild.name,
                "server_id": str(guild.id),
                "channels": accessible_channels,
                "discovered_at": datetime.now().isoformat(),
                "total_tested": len(text_channels)
            }
            
        except Exception as e:
            self.logger.error(f"Error discovering accessible channels: {e}")
            return {"server_name": "Unknown", "channels": []}
        finally:
            await client.close()

    def get_cache_file_path(self) -> Path:
        """Get the path for the channel cache file."""
        cache_dir = Path.home() / ".promaia" / "cache"
        cache_dir.mkdir(parents=True, exist_ok=True)
        return cache_dir / f"discord_channels_{self.workspace}_{self.server_id}.json"

    async def get_cached_accessible_channels(self, force_refresh: bool = False) -> Dict[str, Any]:
        """Get cached accessible channels, discovering them if cache doesn't exist."""
        cache_file = self.get_cache_file_path()
        
        # Check if we need to discover/refresh
        if force_refresh or not cache_file.exists():
            self.logger.info(f"Discovering accessible channels for server {self.server_id}")
            channel_data = await self.discover_accessible_channels()
            
            # Cache the results
            try:
                with open(cache_file, 'w') as f:
                    json.dump(channel_data, f, indent=2)
                self.logger.info(f"Cached {len(channel_data.get('channels', []))} accessible channels")
            except Exception as e:
                self.logger.error(f"Error caching channel data: {e}")
            
            return channel_data
        
        # Load from cache
        try:
            with open(cache_file, 'r') as f:
                channel_data = json.load(f)
            self.logger.debug(f"Loaded {len(channel_data.get('channels', []))} channels from cache")
            return channel_data
        except Exception as e:
            self.logger.error(f"Error loading cached channels: {e}")
            # Fall back to discovery
            return await self.discover_accessible_channels()

    async def refresh_channel_cache(self):
        """Refresh the channel access cache."""
        return await self.get_cached_accessible_channels(force_refresh=True)

    async def cleanup(self):
        """Clean up Discord connector."""
        # No persistent connections to clean up with the new approach
        pass 