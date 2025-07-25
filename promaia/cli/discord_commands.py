"""
Discord integration commands for the Maia CLI.
"""
import os
import json
import asyncio
import logging
from typing import Dict, Any, List, Tuple, Optional

from rich.console import Console
from rich.prompt import Prompt
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich.layout import Layout
from rich.live import Live
from rich import box

logger = logging.getLogger(__name__)

async def handle_discord_setup(args):
    """Handle 'maia workspace discord-setup' command."""
    workspace = args.workspace
    server_id = getattr(args, 'server_id', None)
    
    print(f"🔧 Setting up Discord bot for workspace '{workspace}'")
    if server_id:
        print(f"🏰 Server ID: {server_id}")
    print()
    
    # Create workspace credentials directory
    config_dir = os.path.join("credentials", workspace)
    os.makedirs(config_dir, exist_ok=True)
    
    credentials_file = os.path.join(config_dir, "discord_credentials.json")
    
    # Check if credentials already exist
    if os.path.exists(credentials_file):
        overwrite = input(f"Discord credentials already exist for workspace '{workspace}'. Overwrite? (y/n): ").strip().lower()
        if overwrite != 'y':
            print("Setup cancelled.")
            return
    
    print("🤖 Discord Bot Setup Instructions:")
    print()
    print("1. Go to the Discord Developer Portal: https://discord.com/developers/applications")
    print("2. Click 'New Application' and give it a name")
    print("3. Go to the 'Bot' section in the left sidebar")
    print("4. Click 'Add Bot' (if not already created)")
    print("5. Under 'Token', click 'Copy' to copy your bot token")
    print("6. Under 'Privileged Gateway Intents', enable:")
    print("   ✅ Message Content Intent")
    print("   ✅ Server Members Intent")
    print("7. Go to 'OAuth2' > 'URL Generator':")
    print("   - Scopes: Select 'bot'")
    print("   - Bot Permissions: Select 'Read Message History' and 'View Channels'")
    print("8. Copy the generated URL and use it to invite the bot to your Discord server")
    print()
    
    # Get bot token from user
    bot_token = input("🔑 Enter your Discord bot token: ").strip()
    
    if not bot_token:
        print("❌ Bot token is required.")
        return
    
    # Get server ID if not provided
    if not server_id:
        server_id = input("🏰 Enter Discord server ID (optional, press Enter to skip): ").strip()
        if not server_id:
            server_id = None
    
    # Create credentials structure
    creds_data = {
        "bot_token": bot_token,
        "default_server_id": server_id,
        "workspace": workspace,
        "created_at": asyncio.get_event_loop().time()
    }
    
    # Save credentials
    try:
        with open(credentials_file, 'w') as f:
            json.dump(creds_data, f, indent=2)
        
        print(f"✅ Credentials saved to {credentials_file}")
        
    except Exception as e:
        print(f"❌ Error saving credentials: {e}")
        return
    
    # Test the bot connection
    print()
    print("🔑 Testing Discord bot connection...")
    
    try:
        # Import here to handle optional dependencies
        from promaia.connectors.discord_connector import DiscordConnector
        
        # Create a test connector to verify bot connection
        test_config = {
            "database_id": server_id,
            "workspace": workspace,
            "bot_token": bot_token
        }
        
        connector = DiscordConnector(test_config)
        
        if await connector.test_connection():
            print("✅ Discord bot setup completed successfully!")
            if server_id:
                print(f"🏰 Connected to Discord server: {connector.guild.name}")
            print()
            print("You can now add Discord as a database source:")
            print(f"  maia database add discord_general \\")
            print(f"    --source-type discord \\")
            print(f"    --database-id {server_id or 'YOUR_SERVER_ID'} \\")
            print(f"    --workspace {workspace}")
            print()
            print("To sync a specific channel:")
            print(f"  maia sync discord_general --filters channel_id=YOUR_CHANNEL_ID")
        else:
            print("❌ Discord bot connection failed.")
            print("Please check your bot token and server permissions.")
            
        # Cleanup the connection
        await connector.cleanup()
        
    except ImportError:
        print("❌ Discord integration not available.")
        print("Please install discord.py: pip install discord.py")
    except Exception as e:
        print(f"❌ Error testing Discord connection: {e}")
        logger.error(f"Discord setup error: {e}")

async def handle_discord_list_channels(args):
    """Handle 'maia discord list-channels' command."""
    workspace = args.workspace
    server_id = getattr(args, 'server_id', None)
    
    try:
        # Load credentials
        config_dir = os.path.join("credentials", workspace)
        credentials_file = os.path.join(config_dir, "discord_credentials.json")
        
        if not os.path.exists(credentials_file):
            print(f"❌ Discord credentials not found for workspace '{workspace}'")
            print(f"Please run: maia workspace discord-setup {workspace}")
            return
        
        with open(credentials_file, 'r') as f:
            creds_data = json.load(f)
        
        bot_token = creds_data.get("bot_token")
        if not server_id:
            server_id = creds_data.get("default_server_id")
        
        if not server_id:
            print("❌ Server ID is required")
            print("Either provide --server-id or set it during setup")
            return
        
        # Import here to handle optional dependencies
        from promaia.connectors.discord_connector import DiscordConnector
        
        # Create connector
        connector = DiscordConnector({
            "database_id": server_id,
            "workspace": workspace,
            "bot_token": bot_token
        })
        
        if not await connector.connect():
            print("❌ Failed to connect to Discord")
            return
        
        # Get guild data using the new method
        guild_data = await connector._get_guild_data()
        
        if not guild_data:
            print("❌ Failed to fetch guild data")
            return
        
        print(f"📋 Channels in server '{guild_data['name']}':")
        print()
        
        text_channels = [ch for ch in guild_data['channels'] if ch['type'] == 'text']
        
        if not text_channels:
            print("No accessible text channels found.")
            return
        
        for channel in text_channels:
            print(f"  #{channel['name']} (ID: {channel['id']})")
            print()
        
        print(f"Total: {len(text_channels)} text channels")
        print()
        print("To sync a channel, use:")
        print(f"  maia sync DATABASE_NAME --filters channel_id=CHANNEL_ID")
        
        # Cleanup
        await connector.cleanup()
        
    except ImportError:
        print("❌ Discord integration not available.")
        print("Please install discord.py: pip install discord.py")
    except Exception as e:
        print(f"❌ Error listing Discord channels: {e}")
        logger.error(f"Discord list channels error: {e}")

async def handle_discord_sync(args):
    """Handle 'maia discord sync' command."""
    database_name = args.database
    workspace = getattr(args, 'workspace', 'koii')
    channel_id = getattr(args, 'channel_id', None)
    days = getattr(args, 'days', 7)
    limit = getattr(args, 'limit', 100)
    
    if not channel_id:
        print("❌ Channel ID is required for Discord sync")
        print("Use: maia discord sync DATABASE_NAME --channel-id CHANNEL_ID")
        return
    
    try:
        from promaia.config.databases import get_database_manager
        from promaia.storage.unified_storage import get_unified_storage
        from promaia.connectors.base import QueryFilter, DateRangeFilter
        from datetime import datetime, timedelta
        
        # Get database config
        db_manager = get_database_manager()
        db_config = db_manager.get_database(database_name)
        
        if not db_config:
            print(f"❌ Database '{database_name}' not found")
            print("Add it first with: maia database add")
            return
        
        if db_config.source_type != "discord":
            print(f"❌ Database '{database_name}' is not a Discord database")
            return
        
        # Load credentials
        config_dir = os.path.join("credentials", workspace)
        credentials_file = os.path.join(config_dir, "discord_credentials.json")
        
        if not os.path.exists(credentials_file):
            print(f"❌ Discord credentials not found for workspace '{workspace}'")
            print(f"Please run: maia workspace discord-setup {workspace}")
            return
        
        with open(credentials_file, 'r') as f:
            creds_data = json.load(f)
        
        # Create connector
        from promaia.connectors.discord_connector import DiscordConnector
        
        connector = DiscordConnector({
            "database_id": db_config.database_id,
            "workspace": workspace,
            "bot_token": creds_data.get("bot_token"),
            "sync_limit": limit
        })
        
        # Create filters
        filters = [QueryFilter("channel_id", "eq", str(channel_id))]
        date_filter = DateRangeFilter("timestamp", days_back=days)
        
        # Get storage
        storage = get_unified_storage()
        
        print(f"🔄 Syncing Discord messages from channel {channel_id}...")
        print(f"📅 Days back: {days}")
        print(f"📊 Limit: {limit}")
        print()
        
        # Perform sync
        result = await connector.sync_to_local_unified(
            storage=storage,
            db_config=db_config,
            filters=filters,
            date_filter=date_filter,
            include_properties=True,
            force_update=False
        )
        
        # Display results
        print("📊 Sync Results:")
        print(f"  📥 Messages fetched: {result.pages_fetched}")
        print(f"  💾 Messages saved: {result.pages_saved}")
        print(f"  ⏭️  Messages skipped: {result.pages_skipped}")
        print(f"  ❌ Errors: {result.pages_failed}")
        
        if result.errors:
            print()
            print("🚨 Errors encountered:")
            for error in result.errors:
                print(f"  - {error}")
        
        print()
        print("✅ Discord sync completed!")
        
        # Cleanup
        await connector.cleanup()
        
    except ImportError:
        print("❌ Discord integration not available.")
        print("Please install discord.py: pip install discord.py")
    except Exception as e:
        print(f"❌ Discord sync failed: {e}")
        logger.error(f"Discord sync error: {e}")

async def handle_discord_browse(args):
    """Handle 'maia discord browse' command - Interactive channel browser."""
    workspace = args.workspace
    
    try:
        # Import here to handle optional dependencies
        from promaia.connectors.discord_connector import DiscordConnector
        from promaia.config.databases import get_database_manager
        
        console = Console()
        
        # Get all Discord databases for this workspace
        db_manager = get_database_manager()
        discord_databases = []
        
        for db_name, db_config in db_manager.databases.items():
            if db_config.workspace == workspace and db_config.source_type == "discord":
                discord_databases.append((db_name, db_config))
        
        if not discord_databases:
            console.print(f"❌ No Discord databases found for workspace '{workspace}'", style="red")
            return
        
        # Load credentials
        config_dir = os.path.join("credentials", workspace)
        credentials_file = os.path.join(config_dir, "discord_credentials.json")
        
        if not os.path.exists(credentials_file):
            console.print(f"❌ Discord credentials not found for workspace '{workspace}'", style="red")
            console.print(f"Please run: maia workspace discord-setup {workspace}")
            return
        
        with open(credentials_file, 'r') as f:
            creds_data = json.load(f)
        
        bot_token = creds_data.get("bot_token")
        
        # Fetch channels for each server
        all_channels = []
        
        for db_name, db_config in discord_databases:
            with console.status(f"[bold blue]Checking permissions for {db_name}..."):
                try:
                    connector = DiscordConnector({
                        "database_id": db_config.database_id,
                        "workspace": workspace,
                        "bot_token": bot_token
                    })
                    
                    # Get server info and channels
                    server_info = await get_server_channels(connector, db_config.database_id)
                    
                    # Get already synced channels from filesystem (fast)
                    synced_channels = get_synced_channels_from_filesystem(db_config)
                    
                    # Combine server info with synced channels
                    all_channels.append({
                        "db_name": db_name,
                        "db_config": db_config,
                        "server_name": server_info.get("server_name", "Unknown Server"),
                        "channels": synced_channels  # Only show channels that have been synced
                    })
                    
                except Exception as e:
                    console.print(f"⚠️  Error fetching channels for {db_name}: {e}", style="yellow")
        
        if not any(server["channels"] for server in all_channels):
            console.print("❌ No accessible channels found", style="red")
            return
        
        # Start interactive browser
        selected_channels = await interactive_channel_browser(console, all_channels, workspace)
        
        if selected_channels:
            console.print(f"\n🎉 Selected {len(selected_channels)} channels!")
            
            # Return the selected channels for chat integration
            return selected_channels
        else:
            console.print("ℹ️  No channels selected", style="cyan")
            return []
        
    except ImportError:
        console.print("❌ Discord integration not available.")
        console.print("Please install discord.py: pip install discord.py")
    except Exception as e:
        console.print(f"❌ Error in Discord browse: {e}", style="red")
        logger.error(f"Discord browse error: {e}")


async def handle_discord_browse_filtered(args, previous_selections=None):
    """Handle filtered Discord channel browser - only show specific databases."""
    workspace = args.workspace
    filter_databases = getattr(args, 'databases', None)  # List of database names to filter by
    database_days = getattr(args, 'database_days', {})  # Map of database -> days
    previous_selections = previous_selections or []  # Previous channel selections for pre-population
    
    # Initialize console first so it's available in except blocks
    console = Console()
    
    try:
        # Import here to handle optional dependencies
        from promaia.connectors.discord_connector import DiscordConnector
        from promaia.config.databases import get_database_manager
        
        # Show date filtering info if specified
        if database_days:
            console.print("📅 Date filtering active:")
            for db_name, days in database_days.items():
                console.print(f"   • {db_name}: last {days} days")
            console.print()
        
        # Get all Discord databases for this workspace
        db_manager = get_database_manager()
        discord_databases = []
        
        if filter_databases is None:
            # No filter - include all Discord databases in workspace
            for db_name, db_config in db_manager.databases.items():
                if db_config.workspace == workspace and db_config.source_type == "discord":
                    days = 30  # Default
                    discord_databases.append((db_name, db_config, days))
        else:
            # Filter specified - resolve each filter name properly
            for filter_name in filter_databases:
                # Strip day specification to get just the database name
                db_name_only = filter_name.split(':')[0] if ':' in filter_name else filter_name
                
                # Use proper database resolution (handles nicknames)
                db_config = db_manager.get_database_by_qualified_name(db_name_only)
                
                if db_config and db_config.workspace == workspace and db_config.source_type == "discord":
                    # Get the actual database key (config name)
                    db_name = db_config.name
                    
                    # Determine days for this database for display
                    days = None
                    if filter_name in database_days:
                        days = database_days[filter_name]
                    elif db_name in database_days:
                        days = database_days[db_name]
                    elif db_config.get_qualified_name() in database_days:
                        days = database_days[db_config.get_qualified_name()]
                    else:
                        days = 30  # Default
                    
                    discord_databases.append((db_name, db_config, days))
        
        if not discord_databases:
            if filter_databases:
                console.print(f"❌ No Discord databases found matching: {', '.join(filter_databases)}", style="red")
                
                # Show available Discord databases to help user
                all_discord_dbs = []
                for db_name, db_config in db_manager.databases.items():
                    if db_config.workspace == workspace and db_config.source_type == "discord":
                        qualified_name = db_config.get_qualified_name()
                        # Show both qualified name and full config name if different
                        if qualified_name != db_name:
                            all_discord_dbs.append(f"{qualified_name} (or {db_name})")
                        else:
                            all_discord_dbs.append(qualified_name)
                
                if all_discord_dbs:
                    console.print(f"📋 Available Discord databases for workspace '{workspace}':", style="cyan")
                    for db in all_discord_dbs:
                        console.print(f"   • {db}", style="dim cyan")
                    # For suggestion, use the qualified name (which includes nickname)
                    first_suggestion = all_discord_dbs[0].split(' (or ')[0]  # Get just the qualified name part
                    console.print(f"\n💡 Try: -b {first_suggestion}:7", style="dim yellow")
                else:
                    console.print(f"ℹ️  No Discord databases configured for workspace '{workspace}'", style="yellow")
                    console.print(f"💡 Set up Discord integration: maia workspace discord-setup {workspace}", style="dim yellow")
            else:
                console.print(f"❌ No Discord databases found for workspace '{workspace}'", style="red")
            return []
        
        # Load credentials
        config_dir = os.path.join("credentials", workspace)
        credentials_file = os.path.join(config_dir, "discord_credentials.json")
        
        if not os.path.exists(credentials_file):
            console.print(f"❌ Discord credentials not found for workspace '{workspace}'", style="red")
            console.print(f"Please run: maia workspace discord-setup {workspace}")
            return []
        
        with open(credentials_file, 'r') as f:
            creds_data = json.load(f)
        
        bot_token = creds_data.get("bot_token")
        
        # Fetch channels for each server
        all_channels = []
        
        for db_name, db_config, days in discord_databases:
            with console.status(f"[bold blue]Checking permissions for {db_name} ({days} days)..."):
                try:
                    connector = DiscordConnector({
                        "database_id": db_config.database_id,
                        "workspace": workspace,
                        "bot_token": bot_token
                    })
                    
                    # Get server info and channels
                    server_info = await get_server_channels(connector, db_config.database_id)
                    
                    # Get accessible channels from cache (with auto-discovery on first use)
                    accessible_channels = await get_accessible_channels_cached(db_config, bot_token)
                    
                    # Combine server info with accessible channels
                    all_channels.append({
                        "db_name": db_name,
                        "db_config": db_config,
                        "days": days,
                        "server_name": server_info.get("server_name", "Unknown Server"),
                        "channels": accessible_channels  # Show all accessible channels
                    })
                    
                except Exception as e:
                    console.print(f"⚠️  Error fetching channels for {db_name}: {e}", style="yellow")
        
        if not any(server["channels"] for server in all_channels):
            console.print("❌ No accessible channels found", style="red")
            return []
        
        # Start interactive browser
        selected_channels, updated_days = await interactive_channel_browser(console, all_channels, workspace, previous_selections)
        
        if selected_channels:
            console.print(f"\n🎉 Selected {len(selected_channels)} channels!")
            
            # Show any date range changes
            if updated_days:
                for db_name, days in updated_days.items():
                    original_days = None
                    for orig_db_name, _, orig_days in discord_databases:
                        if orig_db_name == db_name:
                            original_days = orig_days
                            break
                    if original_days and original_days != days:
                        console.print(f"📅 Updated {db_name}: {original_days} → {days} days", style="cyan")
            
            # Return the selected channels for chat integration
            # For now, we'll still return the original format for compatibility
            # but in the future, we could return updated days too
            return selected_channels
        else:
            console.print("ℹ️  No channels selected", style="cyan")
            return []
        
    except ImportError:
        console.print("❌ Discord integration not available.")
        console.print("Please install discord.py: pip install discord.py")
        return []
    except Exception as e:
        console.print(f"❌ Error in Discord browse: {e}", style="red")
        logger.error(f"Discord browse error: {e}")
        return []


async def get_server_channels(connector, server_id: str) -> Dict:
    """Get channels for a Discord server that have already been synced (fast lookup)."""
    try:
        # Use the same approach as the working _get_guild_data method  
        import discord
        
        client = discord.Client(intents=connector.intents)
        
        try:
            await client.login(connector.bot_token)
            guild = await client.fetch_guild(int(server_id))
            
            return {
                "server_name": guild.name,
                "channels": []  # Will be populated by checking existing synced channels
            }
            
        finally:
            await client.close()
            
    except Exception as e:
        logger.error(f"Error fetching server info: {e}")
        return {"server_name": "Unknown Server", "channels": []}

def get_synced_channels_from_filesystem(db_config) -> List[Dict]:
    """Get list of channels that have already been synced by checking filesystem."""
    channels = []
    
    try:
        import os
        from pathlib import Path
        
        # Check the markdown directory for this Discord database
        md_dir = db_config.markdown_directory
        
        if os.path.exists(md_dir):
            # Each subdirectory represents a synced channel
            for channel_dir in Path(md_dir).iterdir():
                if channel_dir.is_dir() and not channel_dir.name.startswith('.'):
                    # Count messages in this channel
                    message_files = list(channel_dir.glob("*.md"))
                    last_sync = "unknown"
                    
                    if message_files:
                        # Get the most recent message file for last activity
                        newest_file = max(message_files, key=lambda f: f.stat().st_mtime)
                        last_sync = newest_file.stat().st_mtime
                        import datetime
                        last_sync = datetime.datetime.fromtimestamp(last_sync).strftime("%m/%d %H:%M")
                    
                    channels.append({
                        "id": "unknown",  # We don't need the ID for chat browsing
                        "name": channel_dir.name,  # Use directory name as-is
                        "message_count": len(message_files),
                        "last_activity": last_sync
                    })
    
    except Exception as e:
        logger.error(f"Error reading synced channels from filesystem: {e}")
    
    return channels

async def get_accessible_channels_cached(db_config, bot_token) -> List[Dict]:
    """Get accessible channels from cache, with auto-discovery on first use."""
    try:
        from promaia.connectors.discord_connector import DiscordConnector
        
        connector = DiscordConnector({
            "database_id": db_config.database_id,
            "workspace": db_config.workspace,
            "bot_token": bot_token
        })
        
        # Get cached accessible channels (will auto-discover if cache doesn't exist)
        channel_data = await connector.get_cached_accessible_channels()
        accessible_channels = channel_data.get('channels', [])
        
        # Convert to format expected by browser and add sync status
        synced_channels = get_synced_channels_from_filesystem(db_config)
        synced_names = {ch['name'] for ch in synced_channels}
        synced_counts = {ch['name']: ch['message_count'] for ch in synced_channels}
        synced_activity = {ch['name']: ch['last_activity'] for ch in synced_channels}
        
        formatted_channels = []
        for channel in accessible_channels:
            channel_name = channel['name']
            formatted_channels.append({
                "id": channel['id'],
                "name": channel_name,
                "message_count": synced_counts.get(channel_name, 0),
                "last_activity": synced_activity.get(channel_name, "not synced"),
                "is_synced": channel_name in synced_names,
                "discovered_at": channel.get('discovered_at', 'unknown')
            })
        
        return formatted_channels
        
    except Exception as e:
        logger.error(f"Error getting accessible channels: {e}")
        # Fall back to filesystem-only approach
        return get_synced_channels_from_filesystem(db_config)

async def interactive_channel_browser(console: Console, servers: List[Dict], workspace: str, previous_selections=None) -> Tuple[List[Tuple[str, str, str, int]], Dict[Tuple[str, str], int]]:
    """Interactive channel browser with real keyboard navigation."""
    from prompt_toolkit import prompt
    from prompt_toolkit.key_binding import KeyBindings
    from prompt_toolkit.keys import Keys
    from prompt_toolkit.application import Application
    from prompt_toolkit.layout.containers import HSplit, Window
    from prompt_toolkit.layout.controls import FormattedTextControl
    from prompt_toolkit.layout.layout import Layout
    from prompt_toolkit.formatted_text import FormattedText
    import asyncio
    
    # Flatten channels for navigation
    nav_items = []
    channel_days = {}  # Track days for each individual channel
    previous_selections = previous_selections or []
    
    # Create lookup set for previous selections for faster matching
    previous_selection_set = set()
    previous_days_map = {}
    for prev_db_name, prev_channel_id, prev_channel_name, prev_days in previous_selections:
        prev_key = (prev_db_name, prev_channel_name)
        previous_selection_set.add(prev_key)
        previous_days_map[prev_key] = prev_days
    
    for server in servers:
        server_default_days = server.get("days", 30)
        for channel in server["channels"]:
            # Use channel name as part of key since channel["id"] might not be unique
            channel_key = (server["db_name"], channel["name"])
            
            # Check if this channel was previously selected
            is_previously_selected = channel_key in previous_selection_set
            
            # Use previous days if available, otherwise server default
            if channel_key in previous_days_map:
                channel_days[channel_key] = previous_days_map[channel_key]
            else:
                channel_days[channel_key] = server_default_days
            
            nav_items.append({
                "server_name": server["server_name"],
                "db_name": server["db_name"],
                "channel": channel,
                "selected": is_previously_selected
            })
    
    if not nav_items:
        return []
    
    current_selection = 0
    filter_text = ""
    should_exit = False
    confirmed = False
    
    def get_filtered_items():
        """Get filtered list of items."""
        if filter_text:
            return [item for item in nav_items if filter_text.lower() in item["channel"]["name"].lower()]
        return nav_items
    
    def render_content():
        """Render the browser content."""
        filtered_items = get_filtered_items()
        
        if not filtered_items:
            return FormattedText([
                ("class:title", "🎮 Discord Channel Browser"),
                ("", "\n\n"),
                ("class:warning", "No channels match filter"),
                ("", "\n\n"),
                ("class:instruction", "ESC to cancel")
            ])
        
        content = []
        content.append(("class:title", "🎮 Discord Channel Browser"))
        content.append(("", "\n\n"))
        
        # Filter display
        filter_display = f"🔍 Filter: {filter_text}_" if filter_text else "🔍 Filter: (type to search)"
        content.append(("class:filter", filter_display))
        content.append(("", "\n\n"))
        
        # Channels
        current_server = None
        current_db = None
        for i, item in enumerate(filtered_items):
            # Server header
            if current_server != item["server_name"] or current_db != item["db_name"]:
                current_server = item["server_name"]
                current_db = item["db_name"]
                content.append(("class:server", f"📂 {current_server} ({current_db})"))
                content.append(("", "\n"))
            
            # Channel line with individual days
            checkbox = "☑" if item["selected"] else "☐"
            channel_name = item["channel"]["name"]
            channel_key = (item["db_name"], item["channel"]["name"])
            days = channel_days.get(channel_key, 30)
            
            if i == current_selection:
                content.append(("class:selected", f">>> {checkbox} #{channel_name} ({days} days)"))
            else:
                content.append(("", f"    {checkbox} #{channel_name} ({days} days)"))
            content.append(("", "\n"))
        
        # Selection info
        selected_count = sum(1 for item in nav_items if item["selected"])
        content.append(("", "\n"))
        content.append(("class:info", f"📊 Selected: {selected_count} channels"))
        content.append(("", "\n\n"))
        
        # Instructions
        content.append(("class:instruction", "↑↓ Navigate  SPACE Toggle  D Cycle Days (1→7→14→30→60→90)  ENTER Confirm  ESC Cancel"))
        
        return FormattedText(content)
    
    # Create key bindings
    bindings = KeyBindings()
    
    @bindings.add(Keys.Up)
    def move_up(event):
        nonlocal current_selection
        filtered_items = get_filtered_items()
        if filtered_items and current_selection > 0:
            current_selection -= 1
    
    @bindings.add(Keys.Down) 
    def move_down(event):
        nonlocal current_selection
        filtered_items = get_filtered_items()
        if filtered_items and current_selection < len(filtered_items) - 1:
            current_selection += 1
    
    @bindings.add(' ')  # Space key
    def toggle_selection(event):
        nonlocal current_selection
        filtered_items = get_filtered_items()
        if filtered_items and current_selection < len(filtered_items):
            # Find the actual item in nav_items and toggle it
            selected_item = filtered_items[current_selection]
            for item in nav_items:
                if (item["db_name"] == selected_item["db_name"] and 
                    item["channel"]["name"] == selected_item["channel"]["name"]):
                    item["selected"] = not item["selected"]
                    break
    
    @bindings.add(Keys.Enter)
    def confirm_selection(event):
        nonlocal should_exit, confirmed
        should_exit = True
        confirmed = True
        event.app.exit()
    
    @bindings.add(Keys.Escape)
    def cancel(event):
        nonlocal should_exit
        should_exit = True
        event.app.exit()
    
    @bindings.add('d')
    def edit_date_range(event):
        nonlocal current_selection
        filtered_items = get_filtered_items()
        if filtered_items and current_selection < len(filtered_items):
            selected_item = filtered_items[current_selection]
            channel_key = (selected_item["db_name"], selected_item["channel"]["name"])
            current_days = channel_days.get(channel_key, 30)
            
            # Cycle through common values: 1, 7, 14, 30, 60, 90 days
            common_days = [1, 7, 14, 30, 60, 90]
            try:
                current_index = common_days.index(current_days)
                next_index = (current_index + 1) % len(common_days)
            except ValueError:
                # Current days not in common list, start with 30
                next_index = 3  # 30 days
            
            new_days = common_days[next_index]
            channel_days[channel_key] = new_days
    
    @bindings.add(Keys.Backspace)
    def handle_backspace(event):
        nonlocal filter_text, current_selection
        if filter_text:
            filter_text = filter_text[:-1]
            current_selection = 0
    
    # Handle character input for filtering
    @bindings.add(Keys.Any)
    def handle_character(event):
        nonlocal filter_text, current_selection
        if event.data and len(event.data) == 1 and event.data.isprintable():
            filter_text += event.data.lower()
            current_selection = 0
    
    # Create the application
    content_control = FormattedTextControl(
        text=render_content,
        focusable=True
    )
    
    container = HSplit([
        Window(content=content_control, height=None)
    ])
    
    layout = Layout(container)
    
    app = Application(
        layout=layout,
        key_bindings=bindings,
        full_screen=False,
        style_transformation=None
    )
    
    # Run the application
    await app.run_async()
    
    # Return selected channels with their specific days
    if confirmed:
        selected_channels = []
        for item in nav_items:
            if item["selected"]:
                channel_key = (item["db_name"], item["channel"]["name"])
                days = channel_days.get(channel_key, 30)
                selected_channels.append((
                    item["db_name"],
                    item["channel"]["id"],
                    item["channel"]["name"],
                    days  # Add days to the tuple
                ))
        return selected_channels, channel_days
    else:
        return [], {}

async def bulk_sync_channels(console: Console, selected_channels: List[Tuple[str, str, str, int]], workspace: str, limit: int):
    """Perform bulk sync of selected channels."""
    from promaia.cli.database_commands import handle_database_sync
    from promaia.config.databases import get_database_manager
    
    console.print(f"\n🚀 Starting bulk sync of {len(selected_channels)} channels...")
    
    db_manager = get_database_manager()
    
    for i, (db_name, channel_id, channel_name, channel_days) in enumerate(selected_channels, 1):
        console.print(f"\n[{i}/{len(selected_channels)}] Syncing #{channel_name} ({channel_days} days)...")
        
        try:
            # Create a mock args object for the sync function
            class MockArgs:
                def __init__(self):
                    self.database = db_name
                    self.channel_id = channel_id
                    self.workspace = workspace
                    self.days = channel_days  # Use channel-specific days
                    self.limit = limit
            
            # Use the existing Discord sync function
            await handle_discord_sync(MockArgs())
            console.print(f"   ✅ Synced #{channel_name}", style="green")
            
        except Exception as e:
            console.print(f"   ❌ Failed to sync #{channel_name}: {e}", style="red")
    
    console.print(f"\n🎉 Bulk sync completed!")

async def handle_discord_debug_channels(args):
    """Handle 'maia discord debug-channels' command to list available Discord channels."""
    from promaia.config.databases import get_database_manager
    
    # Get workspace (default to current or prompt user)
    workspace = getattr(args, 'workspace', None)
    if not workspace:
        from promaia.config.workspaces import get_workspace_manager
        workspace_manager = get_workspace_manager()
        workspace = workspace_manager.get_default_workspace()
        if not workspace:
            print("❌ No workspace specified and no default workspace configured.")
            return
    
    print(f"🔍 Debugging Discord channels for workspace: {workspace}")
    
    # Get all Discord databases for this workspace
    db_manager = get_database_manager()
    discord_dbs = []
    
    for db_name in db_manager.list_databases():
        db_config = db_manager.get_database(db_name)
        if db_config and db_config.source_type == 'discord' and db_config.workspace == workspace:
            discord_dbs.append((db_name, db_config))
    
    if not discord_dbs:
        print(f"❌ No Discord databases found for workspace '{workspace}'")
        return
    
    print(f"📋 Found {len(discord_dbs)} Discord database(s):")
    
    for db_name, db_config in discord_dbs:
        print(f"\n🗃️  Database: {db_name} (ID: {db_config.database_id})")
        
        # Create Discord connector for this database
        try:
            # Load Discord credentials
            import os
            import json
            
            config_dir = os.path.join("credentials", workspace)
            credentials_file = os.path.join(config_dir, "discord_credentials.json")
            
            if not os.path.exists(credentials_file):
                print(f"   ❌ Discord credentials not found for workspace '{workspace}'")
                continue
            
            with open(credentials_file, 'r') as f:
                creds_data = json.load(f)
            
            # Create connector config
            connector_config = db_config.to_dict()
            connector_config['bot_token'] = creds_data.get("bot_token")
            
            # Create connector
            from promaia.connectors.discord_connector import DiscordConnector
            connector = DiscordConnector(connector_config)
            
            # List channels
            await connector.list_server_channels()
            
        except Exception as e:
            print(f"   ❌ Error debugging channels for {db_name}: {e}")
            import traceback
            traceback.print_exc()

async def handle_discord_refresh(args):
    """Handle 'maia discord refresh' command to refresh accessible channel cache."""
    workspace = args.workspace
    
    try:
        from promaia.connectors.discord_connector import DiscordConnector
        from promaia.config.databases import get_database_manager
        
        console = Console()
        
        # Get all Discord databases for this workspace
        db_manager = get_database_manager()
        discord_databases = []
        
        for db_name, db_config in db_manager.databases.items():
            if db_config.workspace == workspace and db_config.source_type == "discord":
                discord_databases.append((db_name, db_config))
        
        if not discord_databases:
            console.print(f"❌ No Discord databases found for workspace '{workspace}'", style="red")
            return
        
        # Load credentials
        config_dir = os.path.join("credentials", workspace)
        credentials_file = os.path.join(config_dir, "discord_credentials.json")
        
        if not os.path.exists(credentials_file):
            console.print(f"❌ Discord credentials not found for workspace '{workspace}'", style="red")
            console.print(f"Please run: maia workspace discord-setup {workspace}")
            return
        
        with open(credentials_file, 'r') as f:
            creds_data = json.load(f)
        
        bot_token = creds_data.get("bot_token")
        
        # Refresh cache for each Discord database
        total_refreshed = 0
        total_tested = 0
        
        import time
        start_time = time.time()
        
        for db_name, db_config in discord_databases:
            with console.status(f"[bold blue]Testing channel permissions for {db_name}..."):
                try:
                    connector = DiscordConnector({
                        "database_id": db_config.database_id,
                        "workspace": workspace,
                        "bot_token": bot_token
                    })
                    
                    # Refresh the channel cache with improved permission checking
                    channel_data = await connector.refresh_channel_cache()
                    accessible_count = len(channel_data.get('channels', []))
                    tested_count = channel_data.get('total_tested', 0)
                    
                    total_refreshed += accessible_count
                    total_tested += tested_count
                    
                    console.print(f"✅ {db_name}: {accessible_count}/{tested_count} channels accessible")
                    
                except Exception as e:
                    console.print(f"❌ Error refreshing {db_name}: {e}", style="red")
        
        end_time = time.time()
        duration = end_time - start_time
        
        console.print()
        console.print(f"🎉 Refresh complete in {duration:.1f}s!")
        console.print(f"📊 Results: {total_refreshed}/{total_tested} channels accessible across {len(discord_databases)} Discord server(s)")
        if total_tested > total_refreshed:
            console.print(f"ℹ️  {total_tested - total_refreshed} channels visible but not readable (missing permissions)", style="dim")
        console.print("💡 You can now use 'maia sync -b' or 'maia chat -b' to browse accessible channels only.")
        
    except Exception as e:
        console.print(f"❌ Error refreshing Discord channels: {e}", style="red")
        logger.error(f"Discord refresh error: {e}")

def setup_discord_commands(subparsers):
    """Set up Discord-related CLI commands."""
    
    # Main Discord command group
    discord_parser = subparsers.add_parser('discord', help='Discord integration commands')
    discord_subparsers = discord_parser.add_subparsers(dest='discord_command', help='Discord commands')
    
    # Browse command (new interactive browser)
    browse_parser = discord_subparsers.add_parser('browse', help='Interactive channel browser for Discord')
    browse_parser.add_argument('workspace', help='Workspace name')
    browse_parser.set_defaults(func=handle_discord_browse)
    
    # List channels command
    list_channels_parser = discord_subparsers.add_parser('list-channels', help='List Discord channels')
    list_channels_parser.add_argument('workspace', help='Workspace name')
    list_channels_parser.add_argument('--server-id', help='Discord server ID (optional if set during setup)')
    list_channels_parser.set_defaults(func=handle_discord_list_channels)
    
    # Debug channels command
    debug_channels_parser = discord_subparsers.add_parser('debug-channels', help='Debug Discord channel connectivity')
    debug_channels_parser.add_argument('--workspace', help='Workspace name (defaults to current workspace)')
    debug_channels_parser.set_defaults(func=handle_discord_debug_channels)
    
    # Refresh channels command
    refresh_parser = discord_subparsers.add_parser('refresh', help='Refresh accessible channel cache')
    refresh_parser.add_argument('workspace', help='Workspace name')
    refresh_parser.set_defaults(func=handle_discord_refresh)
    
    # Sync command
    sync_parser = discord_subparsers.add_parser('sync', help='Sync Discord messages')
    sync_parser.add_argument('database', help='Database name to sync')
    sync_parser.add_argument('--channel-id', required=True, help='Discord channel ID to sync')
    sync_parser.add_argument('--workspace', default='koii', help='Workspace name')
    sync_parser.add_argument('--days', type=int, default=7, help='Number of days to sync back')
    sync_parser.add_argument('--limit', type=int, default=100, help='Maximum number of messages to sync')
    sync_parser.set_defaults(func=handle_discord_sync)

def add_discord_workspace_commands(workspace_subparsers):
    """Add Discord setup to workspace commands."""
    discord_setup_parser = workspace_subparsers.add_parser('discord-setup', help='Set up Discord bot for workspace')
    discord_setup_parser.add_argument('workspace', help='Workspace name')
    discord_setup_parser.add_argument('--server-id', help='Discord server ID (optional)')
    discord_setup_parser.set_defaults(func=handle_discord_setup) 