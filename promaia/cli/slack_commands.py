"""
Slack integration commands for the Maia CLI.
"""
import os
import json
import asyncio
import logging
from typing import Dict, Any, List, Optional

from rich.console import Console
from rich.table import Table
from rich import box

from promaia.utils.display import print_text, print_separator

logger = logging.getLogger(__name__)

def add_slack_workspace_commands(subparsers):
    """Add Slack-specific workspace setup commands."""
    setup_parser = subparsers.add_parser('slack-setup', help='Set up Slack credentials for a workspace')
    setup_parser.add_argument('workspace', help='Workspace name')
    setup_parser.set_defaults(func=handle_slack_setup)

def setup_slack_commands(subparsers):
    """Set up Slack-related CLI commands."""
    slack_parser = subparsers.add_parser('slack', help='Slack integration commands')
    slack_subparsers = slack_parser.add_subparsers(dest='slack_command', help='Slack commands')
    
    # List channels command
    list_channels_parser = slack_subparsers.add_parser('list-channels', help='List accessible Slack channels')
    list_channels_parser.add_argument('workspace', help='Workspace name')
    list_channels_parser.set_defaults(func=handle_slack_list_channels)
    
    # Sync command
    sync_parser = slack_subparsers.add_parser('sync', help='Sync Slack messages')
    sync_parser.add_argument('database', help='Database name to sync (hybrid storage alias)')
    sync_parser.add_argument('--channel-id', required=True, help='Slack channel ID to sync')
    sync_parser.add_argument('--workspace', default='koii', help='Workspace name')
    sync_parser.add_argument('--days', type=int, default=7, help='Number of days to sync back')
    sync_parser.add_argument('--limit', type=int, default=1000, help='Maximum number of messages to sync')
    sync_parser.set_defaults(func=handle_slack_sync)

async def handle_slack_setup(args):
    """Handle 'maia workspace slack-setup' command."""
    workspace = args.workspace
    
    print_text(f"🔧 Setting up Slack integration for workspace '{workspace}'")
    print()
    
    config_dir = os.path.join("credentials", workspace)
    os.makedirs(config_dir, exist_ok=True)
    credentials_file = os.path.join(config_dir, "slack_credentials.json")
    
    if os.path.exists(credentials_file):
        overwrite = input(f"Slack credentials already exist for workspace '{workspace}'. Overwrite? (y/n): ").strip().lower()
        if overwrite != 'y':
            print("Setup cancelled.")
            return

    print("🤖 Slack App Setup Instructions:")
    print()
    print("1. Go to https://api.slack.com/apps and create an app from scratch")
    print("2. Go to 'OAuth & Permissions' in the sidebar")
    print("3. Add these Bot Token Scopes:")
    print("   ✅ channels:history     — Read public channel messages")
    print("   ✅ groups:history       — Read private channel messages")
    print("   ✅ channels:read        — List channels")
    print("   ✅ groups:read          — List private channels")
    print("   ✅ users:read           — Get user info")
    print("   ✅ files:read           — Access shared files")
    print("   ✅ reactions:read       — Read message reactions")
    print("4. Click 'Install to Workspace' at the top")
    print("5. Copy the 'Bot User OAuth Token' (starts with xoxb-)")
    print()
    
    bot_token = input("🔑 Enter your Slack bot token (xoxb-...): ").strip()
    
    if not bot_token:
        print("❌ Bot token is required.")
        return
        
    creds_data = {
        "bot_token": bot_token,
        "workspace": workspace,
        "created_at": asyncio.get_event_loop().time()
    }
    
    try:
        with open(credentials_file, 'w', encoding='utf-8') as f:
            json.dump(creds_data, f, indent=2)
        print_text(f"✅ Credentials saved to {credentials_file}")
    except Exception as e:
        print(f"❌ Error saving credentials: {e}")
        return
        
    print()
    print("🔑 Testing Slack connection...")
    
    try:
        from promaia.connectors.slack_connector import SlackConnector
        connector = SlackConnector({
            "workspace": workspace,
            "bot_token": bot_token
        })
        
        if await connector.test_connection():
            print("✅ Slack setup completed successfully!")
            print()
            print("You can now add Slack channels as database sources:")
            print(f"  maia database add YOUR_DB_NAME \\")
            print(f"    --source-type slack \\")
            print(f"    --database-id slack \\")
            print(f"    --workspace {workspace}")
            print()
            print("Then, sync a specific channel using its ID:")
            print(f"  maia slack sync YOUR_DB_NAME --channel-id CHANNEL_ID --workspace {workspace}")
            print()
            print("To list channels the bot has access to:")
            print(f"  maia slack list-channels {workspace}")
            print()
            print("💡 IMPORTANT: Add your Slack bot to private channels by typing '@YourBotName' in them.")
        else:
            print("❌ Slack connection failed. Check your token and permissions.")
            
    except ImportError:
        print("❌ Slack integration not available. Please install slack-sdk.")
    except Exception as e:
        print(f"❌ Error testing Slack connection: {e}")

async def handle_slack_list_channels(args):
    """Handle 'maia slack list-channels' command."""
    workspace = args.workspace
    
    config_dir = os.path.join("credentials", workspace)
    credentials_file = os.path.join(config_dir, "slack_credentials.json")
    
    if not os.path.exists(credentials_file):
        print_text(f"❌ Slack credentials not found for workspace '{workspace}'")
        print_text(f"Run: maia workspace slack-setup {workspace}")
        return
        
    with open(credentials_file, 'r', encoding='utf-8') as f:
        creds_data = json.load(f)
        
    try:
        from promaia.connectors.slack_connector import SlackConnector
        connector = SlackConnector({
            "workspace": workspace,
            "bot_token": creds_data.get("bot_token")
        })
        
        if not await connector.connect():
            print("❌ Failed to connect to Slack")
            return
            
        print("🔍 Discovering accessible channels...")
        result = await connector.discover_accessible_channels()
        channels = result.get("channels", [])
        
        if not channels:
            print("\n❌ No accessible channels found.")
            print("💡 Remember to invite your bot to channels by typing '@YourBotName' in them.")
            return
            
        table = Table(title=f"Accessible Slack Channels ({len(channels)})", box=box.ROUNDED)
        table.add_column("Channel Name", style="bold cyan")
        table.add_column("Channel ID", style="dim")
        table.add_column("Type", style="green")
        table.add_column("Members", justify="right")
        
        for ch in channels:
            ch_type = "Private" if ch["is_private"] else "Public"
            if ch.get("is_archived"):
                ch_type += " (Archived)"
            table.add_row(
                f"#{ch['name']}", 
                ch['id'], 
                ch_type, 
                str(ch.get('num_members', 0))
            )
            
        console = Console()
        console.print(table)
        print()
        print("To sync a specific channel:")
        print(f"  maia slack sync MY_DB_NAME --channel-id CHANNEL_ID --workspace {workspace}")
        
    except ImportError:
        print("❌ Slack integration not available. Please install slack-sdk.")
    except Exception as e:
        print(f"❌ Error listing channels: {e}")

async def handle_slack_sync(args):
    """Handle 'maia slack sync' command."""
    workspace = args.workspace
    database = args.database
    channel_id = args.channel_id
    
    config_dir = os.path.join("credentials", workspace)
    credentials_file = os.path.join(config_dir, "slack_credentials.json")
    
    if not os.path.exists(credentials_file):
        print_text(f"❌ Slack credentials not found for workspace '{workspace}'")
        print_text(f"Run: maia workspace slack-setup {workspace}")
        return
        
    with open(credentials_file, 'r', encoding='utf-8') as f:
        creds_data = json.load(f)
        
    from datetime import datetime, timedelta, timezone
    from promaia.connectors.base import DateRangeFilter
    
    end_date = datetime.now(timezone.utc)
    start_date = end_date - timedelta(days=args.days)
    date_filter = DateRangeFilter(start_date=start_date, end_date=end_date)
    
    print_text(f"🔄 Syncing Slack channel {channel_id} to database {database}...")
    print_text(f"📅 Date range: {args.days} days ({start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')})")
    
    try:
        from promaia.connectors.slack_connector import SlackConnector
        connector = SlackConnector({
            "workspace": workspace,
            "bot_token": creds_data.get("bot_token")
        })
        
        # Mocking a DB config for unified pipeline
        class MockConfig:
            def __init__(self, name):
                self.name = name
            def get_qualified_name(self):
                return self.name
                
        db_config = MockConfig(database)
        
        result = await connector.sync_to_local_unified(
            db_config=db_config,
            date_filter=date_filter,
            message_limit=args.limit,
            channel_ids=[channel_id]
        )
        
        if result.has_errors():
            print_text(f"\n⚠️ Sync completed with errors:", style="yellow")
            for error in result.errors[:5]:
                print(f"  - {error}")
            if len(result.errors) > 5:
                print(f"  ... and {len(result.errors) - 5} more errors")
                
        print_text(f"\n✅ Sync Complete for {database}!")
        print(f"  📥 Messages fetched: {result.pages_fetched}")
        print(f"  💾 Messages saved: {result.pages_saved}")
        print(f"  ⏭️ Messages skipped: {result.pages_skipped}")
        print(f"  ⏱️ Duration: {result.duration_seconds:.1f}s")
        
    except ImportError:
        print("❌ Slack integration not available. Please install slack-sdk.")
    except Exception as e:
        print(f"❌ Error during sync: {e}")
        logger.exception("Slack sync error")
