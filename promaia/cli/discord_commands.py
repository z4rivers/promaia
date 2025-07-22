"""
Discord integration commands for the Maia CLI.
"""
import os
import json
import asyncio
import logging
from typing import Dict, Any

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

def setup_discord_commands(subparsers):
    """Set up Discord-related CLI commands."""
    
    # Main Discord command group
    discord_parser = subparsers.add_parser('discord', help='Discord integration commands')
    discord_subparsers = discord_parser.add_subparsers(dest='discord_command', help='Discord commands')
    
    # List channels command
    list_channels_parser = discord_subparsers.add_parser('list-channels', help='List Discord channels')
    list_channels_parser.add_argument('workspace', help='Workspace name')
    list_channels_parser.add_argument('--server-id', help='Discord server ID (optional if set during setup)')
    list_channels_parser.set_defaults(func=handle_discord_list_channels)
    
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