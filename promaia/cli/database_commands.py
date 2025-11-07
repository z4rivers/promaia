"""
Database management commands for the enhanced Maia CLI.
"""
import asyncio
import argparse
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta, timezone
from promaia.utils.timezone_utils import days_ago_utc, now_local, now_utc, log_timezone_info
import json
import os
import re
from pathlib import Path

from promaia.config.databases import get_database_manager, get_database_config
from promaia.config.paths import get_project_root
from promaia.connectors import ConnectorRegistry
from promaia.connectors.base import QueryFilter, DateRangeFilter

logger = logging.getLogger(__name__)

async def remove_channel_from_config(db_config, channel_name: str, db_manager) -> bool:
    """
    Remove a Discord channel from database configuration by mapping channel name to ID.
    
    Args:
        db_config: Database configuration object
        channel_name: Name of the channel to remove
        db_manager: Database manager instance
        
    Returns:
        True if channel was found and removed, False otherwise
    """
    try:
        # Check if this database has channel_id filters
        if not hasattr(db_config, 'property_filters') or 'channel_id' not in db_config.property_filters:
            return True  # No channel filters to update
            
        channel_ids = db_config.property_filters.get('channel_id', [])
        if not channel_ids:
            return True  # No channel IDs configured
            
        # Try to map channel name to channel ID using existing data
        channel_id_to_remove = None
        
        # Look through registry entries to find a mapping
        from promaia.storage.hybrid_storage import get_hybrid_registry
        registry = get_hybrid_registry()
        
        try:
            # Get content for this database
            content_items = registry.list_content(
                workspace=db_config.workspace,
                database_name=db_config.get_qualified_name()
            )
            
            # Look for items from this channel to extract channel ID
            for item in content_items:
                metadata = item.get('metadata', {})
                item_channel_name = metadata.get('channel_name') or metadata.get('discord_channel_name')
                
                if item_channel_name == channel_name:
                    # Try to extract channel ID from metadata or file path
                    channel_id = metadata.get('channel_id') or metadata.get('discord_channel_id')
                    if channel_id and channel_id in channel_ids:
                        channel_id_to_remove = channel_id
                        break
                        
        except Exception as e:
            logger.debug(f"Could not find channel ID mapping through registry: {e}")
        
        # If we found a channel ID to remove, update the config
        if channel_id_to_remove:
            updated_channel_ids = [cid for cid in channel_ids if cid != channel_id_to_remove]
            db_config.property_filters['channel_id'] = updated_channel_ids
            db_manager.save_config()
            logger.info(f"Removed channel ID {channel_id_to_remove} from database {db_config.get_qualified_name()}")
            return True
        else:
            logger.warning(f"Could not find channel ID for channel name '{channel_name}' in database {db_config.get_qualified_name()}")
            return False
            
    except Exception as e:
        logger.error(f"Error removing channel from config: {e}")
        return False

async def handle_database_list(args):
    """Handle 'maia database list' command."""
    db_manager = get_database_manager()
    
    # Check if workspace filter is specified
    workspace_filter = getattr(args, 'workspace', None)
    
    if workspace_filter:
        databases = db_manager.list_databases(workspace_filter)
        print(f"Databases in workspace '{workspace_filter}':")
    else:
        databases = db_manager.list_databases()
        # Group by workspace for better display
        workspace_databases = db_manager.list_databases_by_workspace()
        
        if not workspace_databases:
            print("No databases configured.")
            print("Add a database with: maia database add <name> --source-type notion --database-id <id>")
            return
        
        print("Configured databases by workspace:")
        for workspace, db_names in workspace_databases.items():
            print(f"\n  Workspace: {workspace}")
            for db_name in db_names:
                db_config = db_manager.get_database(db_name)
                status = "✓" if db_config.sync_enabled else "✗"
                print(f"    {status} {db_config.get_qualified_name()} ({db_config.source_type}) - {db_config.description}")
        return
    
    if not databases:
        print(f"No databases configured in workspace '{workspace_filter}'.")
        return
    
    for db_name in databases:
        db_config = db_manager.get_database(db_name)
        status = "✓" if db_config.sync_enabled else "✗"
        print(f"  {status} {db_config.get_qualified_name()} ({db_config.source_type}) - {db_config.description}")

async def handle_database_add(args):
    """Handle 'maia database add' command."""
    db_manager = get_database_manager()
    
    # Get workspace information
    workspace = getattr(args, 'workspace', None)
    
    # Interactive configuration
    name = args.name or input("Database name: ")
    source_type = args.source_type or input("Source type (notion): ") or "notion"
    database_id = args.database_id or input("Database ID: ")
    description = args.description or input("Description (optional): ")
    
    if not workspace:
        # Get available workspaces and prompt
        from promaia.config.workspaces import get_workspace_manager
        workspace_manager = get_workspace_manager()
        workspaces = workspace_manager.list_workspaces()
        default_workspace = workspace_manager.get_default_workspace()
        
        if workspaces:
            print(f"Available workspaces: {', '.join(workspaces)}")
            if default_workspace:
                workspace = input(f"Workspace ({default_workspace}): ") or default_workspace
            else:
                workspace = input("Workspace: ")
        else:
            print("No workspaces configured. Using 'personal' workspace.")
            workspace = "personal"
    
    config = {
        "source_type": source_type,
        "database_id": database_id,
        "description": description,
        "workspace": workspace,  # Add workspace for proper connector initialization
        "sync_enabled": True,
        "include_properties": True,
        "default_days": 7,
        "save_markdown": True
    }
    
    try:
        if db_manager.add_database(name, config, workspace):
            # For lookup, we need to use the actual stored key format
            # If name contains workspace prefix, use it directly; otherwise build qualified name
            if '.' in name and name.startswith(f"{workspace}."):
                lookup_name = name
            else:
                lookup_name = name
            
            db_config = db_manager.get_database(lookup_name, workspace)
            if not db_config:
                # Fallback: try by qualified name lookup
                if '.' in name:
                    db_config = db_manager.get_database_by_qualified_name(name)
                else:
                    qualified_name = f"{workspace}.{name}" if workspace != "koii" else name
                    db_config = db_manager.get_database_by_qualified_name(qualified_name)
            
            if db_config:
                print(f"✓ Added database '{db_config.get_qualified_name()}' successfully")
            else:
                print(f"✓ Added database '{name}' successfully")
                return  # Skip connection test if we can't retrieve the config
            
            # Test connection with full database config (includes workspace info)
            connector = ConnectorRegistry.get_connector(source_type, db_config.to_dict())
            if connector and await connector.test_connection():
                print("✓ Connection test successful")
            else:
                print("⚠ Warning: Connection test failed")
        else:
            print(f"✗ Failed to add database '{name}' (may already exist)")
            
    except Exception as e:
        print(f"✗ Failed to add database: {e}")

async def handle_database_remove(args):
    """Handle 'maia database remove' command."""
    db_manager = get_database_manager()
    
    if not args.name:
        print("Database name is required")
        return
    
    # Parse workspace.database format if provided
    workspace = getattr(args, 'workspace', None)
    name = args.name
    original_name = name
    
    if '.' in name and not workspace:
        workspace, name = name.split('.', 1)
    
    # Try multiple resolution strategies
    db_config = None
    
    # First try: use get_database with parsed workspace and name
    db_config = db_manager.get_database(name, workspace)
    
    # Second try: if that fails and we have a qualified name, try direct lookup
    if not db_config and '.' in original_name:
        db_config = db_manager.get_database_by_qualified_name(original_name)
    
    # Third try: try direct key lookup in databases dict
    if not db_config and original_name in db_manager.databases:
        db_config = db_manager.databases[original_name]
    
    if db_config:
        # Find the actual key to remove
        key_to_remove = None
        for key, config in db_manager.databases.items():
            if config == db_config:
                key_to_remove = key
                break
        
        if key_to_remove:
            del db_manager.databases[key_to_remove]
            db_manager.save_config()
            print(f"✓ Removed database '{key_to_remove}'")
        else:
            print(f"✗ Could not find database key for '{original_name}'")
    else:
        print(f"✗ Database '{original_name}' not found")

async def handle_database_remove_channels(args):
    """Handle 'maia database remove-channels' command to remove Discord channels via browser."""
    from promaia.storage.hybrid_storage import get_hybrid_registry
    from promaia.cli.discord_commands import interactive_channel_browser, get_accessible_channels_cached
    from promaia.connectors.discord_connector import DiscordConnector
    from rich.console import Console
    
    console = Console()
    db_manager = get_database_manager()
    
    if not args.database_name:
        print("✗ Database name is required")
        return
    
    # Parse database name (handle workspace.database format)
    workspace = None
    if '.' in args.database_name:
        workspace, db_name = args.database_name.split('.', 1)
    else:
        db_name = args.database_name
    
    # Get database config
    db_config = db_manager.get_database(db_name, workspace)
    if not db_config:
        print(f"✗ Database '{args.database_name}' not found")
        return
    
    # Check if it's a Discord database
    if db_config.source_type != 'discord':
        print(f"✗ Database '{args.database_name}' is not a Discord database (type: {db_config.source_type})")
        return
    
    try:
        print(f"🔍 Loading channels for Discord database '{args.database_name}'...")
        
        # Get current channel filters from config
        current_channel_ids = []
        channel_filter = db_config.property_filters.get('channel_id', [])
        if isinstance(channel_filter, str):
            current_channel_ids = [channel_filter]
        elif isinstance(channel_filter, list):
            current_channel_ids = channel_filter
        
        if not current_channel_ids:
            print(f"✓ No channels configured for database '{args.database_name}'")
            return
        
        # Create a fake server structure for the browser to show current channels
        servers = [{
            "server_id": db_config.database_id,
            "server_name": f"Discord Server ({db_config.nickname})",
            "db_name": db_config.nickname,
            "channels": [{"channel_id": cid, "name": f"Channel {cid}", "channel_name": f"Channel {cid}", "accessible": True} for cid in current_channel_ids]
        }]
        
        print(f"📋 Select channels to REMOVE from database '{args.database_name}':")
        print("   Use SPACE to select channels, ENTER to confirm, ESC to cancel")
        
        # Use the existing interactive browser to let user select channels to remove
        selected_channels, _ = await interactive_channel_browser(console, servers, db_config.workspace)
        
        if not selected_channels:
            print("No channels selected for removal.")
            return
        
        # Extract channel IDs from selection
        channels_to_remove = [channel[1] for channel in selected_channels]  # channel[1] is channel_id
        
        print(f"\n🗑️  Will remove {len(channels_to_remove)} channels from database '{args.database_name}':")
        for channel_id in channels_to_remove:
            print(f"   - {channel_id}")
        
        # Confirm removal
        if not args.force:
            response = input(f"\nThis will:\n1. Remove channels from config\n2. Delete all stored data for these channels\n\nContinue? (y/N): ")
            if response.lower() not in ['y', 'yes']:
                print("Operation cancelled")
                return
        
        # Update config - remove channels from filter
        remaining_channels = [cid for cid in current_channel_ids if cid not in channels_to_remove]
        
        if remaining_channels:
            db_config.property_filters['channel_id'] = remaining_channels if len(remaining_channels) > 1 else remaining_channels[0]
        else:
            # Remove the filter entirely if no channels left
            if 'channel_id' in db_config.property_filters:
                del db_config.property_filters['channel_id']
        
        db_manager.save_config()
        print(f"✓ Updated config for database '{args.database_name}'")
        
        # Remove stored data for these channels
        registry = get_hybrid_registry()
        total_removed = 0
        
        for channel_id in channels_to_remove:
            # Get content for this specific channel
            content_list = registry.list_content(
                content_type=db_config.nickname,
                workspace=db_config.workspace
            )
            
            channel_content = [
                item for item in content_list 
                if item.get('discord_channel_id') == channel_id
            ]
            
            print(f"🗑️  Removing {len(channel_content)} items from channel {channel_id}...")
            
            for item in channel_content:
                page_id = item.get('page_id')
                if page_id and registry.remove_content(page_id):
                    total_removed += 1
                else:
                    print(f"✗ Failed to remove item with page_id: {page_id}")
        
        print(f"✅ Successfully removed {len(channels_to_remove)} channels and {total_removed} stored items from database '{args.database_name}'")
        
    except Exception as e:
        print(f"✗ Error removing channels: {e}")
        import traceback
        traceback.print_exc()

async def handle_database_purge_data(database_config):
    """Purge all locally stored data for a database."""
    from promaia.storage.hybrid_storage import get_hybrid_registry
    import shutil
    
    try:
        # Get the database's markdown directory
        md_dir = getattr(database_config, 'markdown_directory', None)
        
        # Purge from registry database
        registry = get_hybrid_registry()
        db_name = database_config.nickname
        workspace = database_config.workspace
        qualified_name = f"{workspace}.{db_name}" if workspace else db_name
        
        # Count items to be removed
        removed_count = 0
        
        # Query registry for all content from this database
        try:
            # Get all content for this database
            content_items = registry.get_content_by_database(qualified_name)
            
            # Remove each item from registry
            for item in content_items:
                page_id = item.get('page_id')
                if page_id and registry.remove_content(page_id):
                    removed_count += 1
        except Exception as e:
            print(f"⚠️  Warning: Could not clean registry for database '{qualified_name}': {e}")
        
        # Remove markdown directory if it exists
        if md_dir and os.path.exists(md_dir):
            try:
                shutil.rmtree(md_dir)
                print(f"🗂️  Removed markdown directory: {md_dir}")
            except Exception as e:
                print(f"⚠️  Warning: Could not remove directory '{md_dir}': {e}")
        
        return removed_count
        
    except Exception as e:
        print(f"✗ Error purging data for database: {e}")
        return 0

async def handle_database_remove_with_data_purge(args):
    """Handle 'maia database remove' command with data purging."""
    db_manager = get_database_manager()
    
    if not args.name:
        print("Database name is required")
        return
    
    # Parse workspace.database format if provided
    workspace = getattr(args, 'workspace', None)
    name = args.name
    original_name = name
    
    if '.' in name and not workspace:
        workspace, name = name.split('.', 1)
    
    # Try multiple resolution strategies
    db_config = None
    
    # First try: use get_database with parsed workspace and name
    db_config = db_manager.get_database(name, workspace)
    
    # Second try: if that fails and we have a qualified name, try direct lookup
    if not db_config and '.' in original_name:
        db_config = db_manager.get_database_by_qualified_name(original_name)
    
    # Third try: try direct key lookup in databases dict
    if not db_config and original_name in db_manager.databases:
        db_config = db_manager.databases[original_name]
    
    if not db_config:
        print(f"✗ Database '{original_name}' not found")
        return
    
    # Confirm removal
    if not getattr(args, 'force', False):
        response = input(f"This will:\n1. Remove database '{original_name}' from config\n2. Delete all locally stored data for this database\n\nContinue? (y/N): ")
        if response.lower() not in ['y', 'yes']:
            print("Operation cancelled")
            return
    
    # Find the actual key to remove
    key_to_remove = None
    for key, config in db_manager.databases.items():
        if config == db_config:
            key_to_remove = key
            break
    
    if not key_to_remove:
        print(f"✗ Could not find database key for '{original_name}'")
        return
    
    # Purge data first
    print(f"🗑️  Purging locally stored data for database '{original_name}'...")
    removed_count = await handle_database_purge_data(db_config)
    
    # Remove from config
    del db_manager.databases[key_to_remove]
    db_manager.save_config()
    
    print(f"✅ Successfully removed database '{key_to_remove}' and purged {removed_count} stored items")

async def handle_database_remove_interactive(args):
    """Handle interactive database removal using simple selector."""
    from promaia.cli.simple_selector import interactive_simple_selector
    from promaia.config.workspaces import get_workspace_manager
    
    # Get workspace
    workspace_manager = get_workspace_manager()
    workspace = getattr(args, 'workspace', None)
    
    if not workspace:
        workspace = workspace_manager.get_default_workspace()
        
    if not workspace:
        print("✗ No workspace specified and no default workspace set")
        return
    
    # Launch selector
    print(f"🔍 Launching database selector for workspace '{workspace}'...")
    selected_databases = await interactive_simple_selector(workspace, "databases", "Select Databases to Remove")
    
    if not selected_databases:
        print("ℹ️  No databases selected for removal")
        return
    
    # Check for dry-run mode
    dry_run = getattr(args, 'dry_run', False)
    
    if dry_run:
        print(f"\n🔍 DRY RUN - Would remove {len(selected_databases)} databases:")
        for db_name in selected_databases:
            print(f"   - {db_name}")
        print("\nActions that would be performed:")
        print("1. Remove databases from config")
        print("2. Delete all locally stored data for these databases")
        print("3. Clean registry entries")
        print("\nRun without --dry-run to actually perform these actions.")
        return
    
    # Confirm removal
    if not getattr(args, 'force', False):
        print(f"\n🗑️  Will remove {len(selected_databases)} databases:")
        for db_name in selected_databases:
            print(f"   - {db_name}")
        
        response = input(f"\nThis will:\n1. Remove databases from config\n2. Delete all locally stored data for these databases\n\nContinue? (y/N): ")
        if response.lower() not in ['y', 'yes']:
            print("Operation cancelled")
            return
    
    # Remove each database
    db_manager = get_database_manager()
    total_removed = 0
    successfully_removed = 0
    
    for db_name in selected_databases:
        try:
            # Get database config
            if '.' in db_name:
                workspace_part, name_part = db_name.split('.', 1)
                db_config = db_manager.get_database(name_part, workspace_part)
            else:
                db_config = db_manager.get_database(db_name, workspace)
            
            if not db_config:
                print(f"✗ Database '{db_name}' not found")
                continue
            
            # Purge data
            removed_count = await handle_database_purge_data(db_config)
            
            # Find the actual key to remove
            key_to_remove = None
            for key, config in db_manager.databases.items():
                if config == db_config:
                    key_to_remove = key
                    break
            
            if key_to_remove:
                del db_manager.databases[key_to_remove]
                print(f"✅ Removed database '{key_to_remove}' and purged {removed_count} items")
                total_removed += removed_count
                successfully_removed += 1
            else:
                print(f"✗ Could not find database key for '{db_name}'")
                
        except Exception as e:
            print(f"✗ Error removing database '{db_name}': {e}")
    
    # Save config once at the end
    if successfully_removed > 0:
        db_manager.save_config()
        print(f"🎉 Successfully removed {successfully_removed} databases and purged {total_removed} total items")

async def handle_channel_remove_interactive(args):
    """Handle interactive Discord channel removal using simple selector.""" 
    from promaia.cli.simple_selector import interactive_simple_selector
    from promaia.config.workspaces import get_workspace_manager
    from promaia.storage.hybrid_storage import get_hybrid_registry
    import shutil
    from pathlib import Path
    
    # Get workspace
    workspace_manager = get_workspace_manager()
    workspace = getattr(args, 'workspace', None)
    
    if not workspace:
        workspace = workspace_manager.get_default_workspace()
        
    if not workspace:
        print("✗ No workspace specified and no default workspace set")
        return
    
    # Launch selector
    print(f"🔍 Launching Discord channel selector for workspace '{workspace}'...")
    selected_channels = await interactive_simple_selector(workspace, "channels", "Select Discord Channels to Remove")
    
    if not selected_channels:
        print("ℹ️  No channels selected for removal")
        return
    
    # Check for dry-run mode
    dry_run = getattr(args, 'dry_run', False)
    
    if dry_run:
        print(f"\n🔍 DRY RUN - Would remove {len(selected_channels)} Discord channels:")
        for channel_spec in selected_channels:
            print(f"   - {channel_spec}")
        print("\nActions that would be performed:")
        print("1. Remove channels from database config")
        print("2. Delete all locally stored data for these channels")
        print("3. Clean registry entries")
        print("\nRun without --dry-run to actually perform these actions.")
        return
    
    # Confirm removal
    if not getattr(args, 'force', False):
        print(f"\n🗑️  Will remove {len(selected_channels)} Discord channels:")
        for channel_spec in selected_channels:
            print(f"   - {channel_spec}")
        
        response = input(f"\nThis will:\n1. Remove channels from database config\n2. Delete all locally stored data for these channels\n\nContinue? (y/N): ")
        if response.lower() not in ['y', 'yes']:
            print("Operation cancelled")
            return
    
    # Process each channel for removal
    db_manager = get_database_manager()
    registry = get_hybrid_registry()
    total_removed_items = 0
    total_removed_channels = 0
    
    # Group channels by database
    channels_by_database = {}
    for channel_spec in selected_channels:
        if '#' not in channel_spec:
            continue
            
        db_name, channel_name = channel_spec.split('#', 1)
        if db_name not in channels_by_database:
            channels_by_database[db_name] = []
        channels_by_database[db_name].append(channel_name)
    
    # Process each database
    for db_name, channel_names in channels_by_database.items():
        try:
            # Get database config
            if '.' in db_name:
                workspace_part, name_part = db_name.split('.', 1)
                db_config = db_manager.get_database(name_part, workspace_part)
            else:
                db_config = db_manager.get_database(db_name, workspace)
            
            if not db_config:
                print(f"✗ Database '{db_name}' not found")
                continue
                
            if db_config.source_type != 'discord':
                print(f"✗ Database '{db_name}' is not a Discord database")
                continue
            
            # Remove each channel
            for channel_name in channel_names:
                try:
                    # Remove from registry by channel
                    removed_count = 0
                    try:
                        # Get all content for this database
                        content_items = registry.list_content(
                            workspace=db_config.workspace,
                            database_name=db_config.get_qualified_name()
                        )
                        
                        # Filter for this specific channel and remove
                        for item in content_items:
                            # Check if this item is from the channel we want to remove
                            metadata = item.get('metadata', {})
                            if (metadata.get('channel_name') == channel_name or 
                                metadata.get('discord_channel_name') == channel_name):
                                page_id = item.get('page_id')
                                if page_id and registry.remove_content(page_id):
                                    removed_count += 1
                    except Exception as e:
                        print(f"⚠️  Warning: Could not clean registry for channel '{channel_name}': {e}")
                    
                    # Remove channel directory
                    md_dir = Path(db_config.markdown_directory) / channel_name
                    if md_dir.exists():
                        try:
                            shutil.rmtree(md_dir)
                            print(f"📁 Removed channel directory: {md_dir}")
                        except Exception as e:
                            print(f"⚠️  Warning: Could not remove directory '{md_dir}': {e}")
                    
                    # Remove from database config (channel_id filter)
                    channel_id_removed = await remove_channel_from_config(db_config, channel_name, db_manager)
                    if not channel_id_removed:
                        print(f"⚠️  Note: Channel '{channel_name}' data removed, but could not remove from database config")
                    
                    print(f"✅ Removed channel '{db_name}#{channel_name}' and purged {removed_count} items")
                    total_removed_items += removed_count
                    total_removed_channels += 1
                    
                except Exception as e:
                    print(f"✗ Error removing channel '{channel_name}': {e}")
                    
        except Exception as e:
            print(f"✗ Error processing database '{db_name}': {e}")
    
    if total_removed_channels > 0:
        print(f"🎉 Successfully removed {total_removed_channels} channels and purged {total_removed_items} total items")

async def handle_database_add_channels(args):
    """Handle 'maia database add-channels' command to add Discord channels via browser."""
    from promaia.cli.discord_commands import interactive_channel_browser, get_accessible_channels_cached
    from promaia.connectors.discord_connector import DiscordConnector
    from rich.console import Console
    
    console = Console()
    db_manager = get_database_manager()
    
    if not args.database_name:
        print("✗ Database name is required")
        return
    
    # Parse database name (handle workspace.database format)
    workspace = None
    if '.' in args.database_name:
        workspace, db_name = args.database_name.split('.', 1)
    else:
        db_name = args.database_name
    
    # Get database config
    db_config = db_manager.get_database(db_name, workspace)
    if not db_config:
        print(f"✗ Database '{args.database_name}' not found")
        return
    
    # Check if it's a Discord database
    if db_config.source_type != 'discord':
        print(f"✗ Database '{args.database_name}' is not a Discord database (type: {db_config.source_type})")
        return
    
    try:
        print(f"🔍 Loading available channels for Discord server...")
        
        # Get workspace-specific API key and create connector
        from promaia.config.workspaces import get_workspace_api_key
        api_key = get_workspace_api_key(db_config.workspace)
        
        if not api_key:
            print(f"✗ No API key configured for workspace '{db_config.workspace}'")
            return
            
        # Create Discord connector to get available channels
        connector_config = db_config.to_dict()
        connector_config['api_key'] = api_key
        
        # Get all available channels for this server
        servers = []
        try:
            # Use the cached channel method that works with the existing system
            channels = await get_accessible_channels_cached(db_config, api_key)
            if channels:
                servers = [{
                    "server_id": db_config.database_id,
                    "server_name": f"Discord Server ({db_config.nickname})",
                    "db_name": db_config.nickname,
                    "channels": channels
                }]
        except Exception as e:
            print(f"⚠️  Could not fetch live channels: {e}")
            print("You may need to run 'maia discord refresh' first to update channel cache.")
            return
        
        if not servers or not servers[0]["channels"]:
            print(f"✗ No accessible channels found for database '{args.database_name}'")
            print("Try running 'maia discord refresh' to update the channel cache.")
            return
        
        print(f"📋 Select channels to ADD to database '{args.database_name}':")
        print("   Use SPACE to select channels, ENTER to confirm, ESC to cancel")
        
        # Use the existing interactive browser
        selected_channels, _ = await interactive_channel_browser(console, servers, db_config.workspace)
        
        if not selected_channels:
            print("No channels selected.")
            return
        
        # Extract channel IDs from selection
        channels_to_add = [channel[1] for channel in selected_channels]  # channel[1] is channel_id
        
        print(f"\n➕ Will add {len(channels_to_add)} channels to database '{args.database_name}':")
        for channel in selected_channels:
            print(f"   - {channel[2]} ({channel[1]})")  # channel[2] is channel_name
        
        # Get current channel filters from config
        current_channel_ids = []
        channel_filter = db_config.property_filters.get('channel_id', [])
        if isinstance(channel_filter, str):
            current_channel_ids = [channel_filter]
        elif isinstance(channel_filter, list):
            current_channel_ids = channel_filter
        
        # Combine current and new channels (avoid duplicates)
        all_channels = list(set(current_channel_ids + channels_to_add))
        
        # Update config
        if len(all_channels) == 1:
            db_config.property_filters['channel_id'] = all_channels[0]
        else:
            db_config.property_filters['channel_id'] = all_channels
        
        db_manager.save_config()
        
        print(f"✅ Successfully added {len(channels_to_add)} channels to database '{args.database_name}'")
        print(f"💡 Run 'maia database sync {args.database_name}' to sync the new channels")
        
    except Exception as e:
        print(f"✗ Error adding channels: {e}")
        import traceback
        traceback.print_exc()

async def handle_database_test(args):
    """Handle 'maia database test' command."""
    db_manager = get_database_manager()
    
    databases_to_test = []
    
    if args.names:
        # Test specific databases
        for name in args.names:
            workspace = None
            if '.' in name:
                workspace, db_name = name.split('.', 1)
            else:
                db_name = name
            
            db_config = db_manager.get_database(db_name, workspace)
            if db_config:
                databases_to_test.append((name, db_config))
            else:
                print(f"✗ {name}: Database not found")
    else:
        # Test all databases
        all_databases = db_manager.list_databases()
        for db_name in all_databases:
            db_config = db_manager.get_database(db_name)
            if db_config:
                databases_to_test.append((db_config.get_qualified_name(), db_config))
    
    for display_name, db_config in databases_to_test:
        try:
            # Get workspace-specific API key
            from promaia.config.workspaces import get_workspace_api_key
            api_key = get_workspace_api_key(db_config.workspace)
            
            if not api_key:
                print(f"✗ {display_name}: No API key configured for workspace '{db_config.workspace}'")
                continue
            
            # Create connector with workspace-specific API key
            connector_config = db_config.to_dict()
            connector_config['api_key'] = api_key
            
            connector = ConnectorRegistry.get_connector(db_config.source_type, connector_config)
            if connector and await connector.test_connection():
                print(f"✓ {display_name}: Connection successful")
            else:
                print(f"✗ {display_name}: Connection failed")
        except Exception as e:
            print(f"✗ {display_name}: {e}")

async def handle_database_sync(args):
    """Handle 'maia database sync' command."""
    # Check if browse mode is requested
    if hasattr(args, 'browse') and args.browse is not None:
        await handle_database_sync_with_browse(args)
        return
    
    # MONITORING: Track overall sync performance
    overall_start_time = datetime.now()
    
    db_manager = get_database_manager()
    
    # Handle workspace expansion if provided
    if hasattr(args, 'workspace') and args.workspace and not args.sources:
        # Expand workspace to individual database source specifications
        workspace_databases = db_manager.get_workspace_databases(args.workspace)
        
        # Build source specifications with qualified names and default days
        # Only include enabled databases to avoid syncing disabled/problematic ones
        expanded_sources = []
        for db in workspace_databases:
            if not db.sync_enabled:
                print(f"⚠️  Skipping disabled database: {db.get_qualified_name()}")
                continue
                
            qualified_name = db.get_qualified_name()
            default_days = db.default_days
            source_spec = f"{qualified_name}:{default_days}"
            expanded_sources.append(source_spec)
            print(f"📦 Adding to sync: {source_spec}")
        
        if not expanded_sources:
            print(f"❌ No enabled databases configured for workspace '{args.workspace}'")
            return
        else:
            print(f"📦 Workspace '{args.workspace}' expanded to {len(expanded_sources)} databases")
            # Set the expanded sources as if they were provided via -s arguments
            args.sources = expanded_sources
    
    # Parse source specifications (now supports workspace.database format)
    sources = parse_source_specs(args.sources) if args.sources else []
    
    if not sources:
        # Sync all enabled databases
        for db_name in db_manager.list_databases():
            db_config = db_manager.get_database(db_name)
            if db_config and db_config.sync_enabled:
                sources.append({"name": db_name, "qualified_name": db_config.get_qualified_name()})
    
    if not sources:
        print("No databases to sync")
        return
    
    print(f"🚀 Syncing {len(sources)} database(s) with optimized performance...")
    
    # OPTIMIZATION: Sync databases in parallel with maximum safe concurrency
    # Chunk databases to prevent overwhelming the system while maximizing throughput
    MAX_CONCURRENT_DATABASES = 15  # Optimal for most systems
    all_results = []
    
    for i in range(0, len(sources), MAX_CONCURRENT_DATABASES):
        chunk = sources[i:i + MAX_CONCURRENT_DATABASES]
        chunk_tasks = [sync_database(source_spec, args) for source_spec in chunk]
        
        # Execute chunk concurrently
        chunk_results = await asyncio.gather(*chunk_tasks, return_exceptions=True)
        all_results.extend(chunk_results)
        
        # Minimal delay between chunks to prevent system overload
        if i + MAX_CONCURRENT_DATABASES < len(sources):
            await asyncio.sleep(0.05)
    
    # MONITORING: Report overall performance
    overall_duration = (datetime.now() - overall_start_time).total_seconds()
    
    # Display comprehensive summary
    display_sync_summary(all_results, overall_duration)

async def sync_database(source_spec: Dict[str, Any], args):
    """Sync a single database based on source specification."""
    db_name = source_spec["name"]
    qualified_name = source_spec.get("qualified_name", db_name)
    
    db_manager = get_database_manager()
    
    # Parse workspace.database if needed
    workspace = None
    if '.' in db_name:
        workspace, db_name = db_name.split('.', 1)
    
    db_config = db_manager.get_database(db_name, workspace)
    
    if not db_config:
        print(f"✗ Database '{qualified_name}' not found")
        # Return a synthetic result for missing databases
        from promaia.connectors.base import SyncResult
        result = SyncResult()
        result.database_name = qualified_name
        result.errors = [f"Database '{qualified_name}' not found"]
        result.start_time = datetime.now()
        result.end_time = datetime.now()
        return result
    
    # Enhanced logging for sync parameters
    force_status = getattr(args, 'force', False)
    days_arg = getattr(args, 'days', None)
    source_days = source_spec.get("days")
    
    # Detailed log for debugging, but keep user output clean
    log_message = f"Initiating sync for database: '{qualified_name}'. Workspace: '{db_config.workspace}'. Force: {force_status}."
    
    if source_days is not None:
        log_message += f" Days from source: {source_days}."
    elif days_arg is not None:
        log_message += f" Days from --days: {days_arg}."
    else:
        log_message += " Days: not specified (will use incremental or default)."
        
    if source_spec.get("filters"):
        log_message += f" Filters from spec: {source_spec.get('filters')}."
    if db_config.property_filters:
        log_message += f" Filters from config: {db_config.property_filters}."
    logger.debug(log_message)  # Changed from info to debug level
    
    # Clean user output - start sync
    print(f"🔄 Syncing {qualified_name}...")
    
    try:
        # Create connector with appropriate credentials
        connector_config = db_config.to_dict()
        
        if db_config.source_type == 'discord':
            # Load Discord bot token from credentials file
            import os
            import json
            config_dir = os.path.join("credentials", db_config.workspace)
            credentials_file = os.path.join(config_dir, "discord_credentials.json")
            
            if not os.path.exists(credentials_file):
                print(f"✗ {qualified_name}: Discord credentials not found for workspace '{db_config.workspace}'")
                print(f"Please run: maia workspace discord-setup {db_config.workspace}")
                # Return a synthetic result for credential errors
                from promaia.connectors.base import SyncResult
                result = SyncResult()
                result.database_name = qualified_name
                result.errors = [f"Discord credentials not found for workspace '{db_config.workspace}'"]
                result.start_time = datetime.now()
                result.end_time = datetime.now()
                return result
            
            try:
                with open(credentials_file, 'r') as f:
                    creds_data = json.load(f)
                connector_config['bot_token'] = creds_data.get("bot_token")
            except Exception as e:
                print(f"✗ {qualified_name}: Failed to load Discord credentials: {e}")
                from promaia.connectors.base import SyncResult
                result = SyncResult()
                result.database_name = qualified_name
                result.errors = [f"Failed to load Discord credentials: {e}"]
                result.start_time = datetime.now()
                result.end_time = datetime.now()
                return result
        elif db_config.source_type == 'conversation':
            # Conversation connector doesn't need API key - it uses local chat history file
            # Add history_file from config if available
            if hasattr(db_config, 'auth') and isinstance(db_config.auth, dict):
                connector_config['history_file'] = db_config.auth.get('history_file', '~/.maia_chat_history.json')
            elif 'history_file' in connector_config:
                # Already in connector_config from db_config.to_dict()
                pass
            else:
                connector_config['history_file'] = '~/.maia_chat_history.json'
        else:
            # This block handles non-Discord, non-conversation connectors by fetching the API key.
            from promaia.config.workspaces import get_workspace_api_key
            api_key = get_workspace_api_key(db_config.workspace)

            if not api_key:
                print(f"✗ {qualified_name}: No API key configured for workspace '{db_config.workspace}'")
                # Return a synthetic result for API key errors
                from promaia.connectors.base import SyncResult
                result = SyncResult()
                result.database_name = qualified_name
                result.errors = [f"No API key configured for workspace '{db_config.workspace}'"]
                result.start_time = datetime.now()
                result.end_time = datetime.now()
                return result

            connector_config['api_key'] = api_key
            
        
        connector = ConnectorRegistry.get_connector(db_config.source_type, connector_config)
        if not connector:
            print(f"✗ No connector available for {db_config.source_type}")
            # Return a synthetic result for connector errors
            from promaia.connectors.base import SyncResult
            result = SyncResult()
            result.database_name = qualified_name
            result.errors = [f"No connector available for {db_config.source_type}"]
            result.start_time = datetime.now()
            result.end_time = datetime.now()
            return result
        
        # Build filters from source spec and config
        filters = build_filters(source_spec, db_config)
        date_filter = build_date_filter(source_spec, db_config, args)
        
        # Extract complex filter from source spec
        complex_filter = source_spec.get('complex_filter')
        
        # Use the new unified storage system instead of old output_directory
        from promaia.storage.unified_storage import get_unified_storage
        storage = get_unified_storage()

        # Build sync arguments - properties_only only supported by Notion connector
        sync_args = {
            'storage': storage,
            'db_config': db_config,
            'filters': filters,
            'date_filter': date_filter if date_filter else None,
            'include_properties': db_config.include_properties,
            'force_update': getattr(args, 'force', False),
            'excluded_properties': db_config.excluded_properties,
            'complex_filter': complex_filter
        }

        # Only pass properties_only to Notion connectors
        if db_config.source_type == 'notion':
            sync_args['properties_only'] = getattr(args, 'properties_only', False)

        # Perform sync using unified storage
        result = await connector.sync_to_local_unified(**sync_args)
        
        # Ensure database name is set in result
        if not result.database_name:
            result.database_name = qualified_name
        
        # Update last sync time on successful sync
        # Update sync time if sync completed successfully (even if no new/updated pages found)
        if not result.errors or result.pages_saved > 0 or result.pages_skipped > 0:
            # Update the last sync time in the database config
            db_config.last_sync_time = now_utc().isoformat()
            db_manager.save_config()

        # MONITORING: Report results with performance metrics
        duration = result.duration_seconds
        duration_str = f" in {duration:.1f}s" if duration else ""
        
        print(f"✅ {qualified_name}: {result.pages_saved} saved, {result.pages_skipped} skipped{duration_str}")
        # MONITORING: Display performance metrics
        if hasattr(result, 'api_calls_count') and result.api_calls_count > 0:
            print(f"  API calls: {result.api_calls_count}")
            if result.api_rate_limit_hits > 0:
                print(f"  Rate limit hits: {result.api_rate_limit_hits}")
            if result.api_errors_count > 0:
                print(f"  API errors: {result.api_errors_count}")
        
        if result.errors:
            print(f"  Errors: {len(result.errors)}")
            for error in result.errors[:3]:  # Show first 3 errors
                print(f"    - {error}")
        
        return result
        
    except Exception as e:
        # MONITORING: Include timing even for failed syncs
        duration = (datetime.now() - (result.start_time if 'result' in locals() else datetime.now())).total_seconds()
        duration_str = f" (failed after {duration:.1f}s)" if duration > 0 else ""
        print(f"✗ {qualified_name}: Sync failed{duration_str} - {e}")
        
        # Return a synthetic result for general errors
        from promaia.connectors.base import SyncResult
        error_result = SyncResult()
        error_result.database_name = qualified_name
        error_result.errors = [f"Sync failed: {e}"]
        error_result.start_time = datetime.now()
        error_result.end_time = datetime.now()
        return error_result

def display_sync_summary(sync_results: List, overall_duration: float):
    """Display a comprehensive summary of all database sync results."""
    from promaia.connectors.base import SyncResult
    from promaia.utils.display import print_text, print_markdown
    
    # Separate successful results from exceptions
    successful_results = []
    failed_results = []
    
    for result in sync_results:
        if isinstance(result, Exception):
            # Handle exceptions that occurred during sync
            failed_results.append({
                'database_name': 'Unknown',
                'error': str(result),
                'duration': 0
            })
        elif isinstance(result, SyncResult):
            if result.errors:
                failed_results.append({
                    'database_name': result.database_name or 'Unknown',
                    'error': '; '.join(result.errors),
                    'duration': result.duration_seconds or 0
                })
            else:
                successful_results.append(result)
        else:
            # Unexpected result type
            failed_results.append({
                'database_name': 'Unknown',
                'error': f'Unexpected result type: {type(result)}',
                'duration': 0
            })
    
    # Calculate summary stats
    total_databases = len(successful_results) + len(failed_results)
    success_rate = (len(successful_results) / total_databases * 100) if total_databases > 0 else 0
    
    # Header
    print("🔄 DATABASE SYNC SUMMARY")
    print("─" * 30)
    # Display successful syncs
    if successful_results:
        print(f"✅ SUCCESSFUL SYNCS ({len(successful_results)} databases)")
        total_saved = 0
        total_skipped = 0
        total_api_calls = 0
        
        for result in successful_results:
            # Format timing
            duration_str = f"{result.duration_seconds:.1f}s" if result.duration_seconds else "0.0s"
            
            # Format counters with colors
            saved_color = "green" if result.pages_saved > 0 else "dim"
            skipped_color = "yellow" if result.pages_skipped > 0 else "dim"
            
            saved_str = f"{result.pages_saved} saved"
            skipped_str = f"{result.pages_skipped} skipped"
            
            # Database name with formatting
            db_name = result.database_name
            if '.' in db_name:
                workspace, name = db_name.split('.', 1)
                db_display = f"{workspace}.{name}"
            else:
                db_display = f"{db_name}"
            
            api_calls_str = ""
            if hasattr(result, 'api_calls_count') and result.api_calls_count > 0:
                api_calls_str = f" • 🌐 {result.api_calls_count} API calls"
                total_api_calls += result.api_calls_count

            print(f"  📊 {db_display} • 💾 {saved_str} • {skipped_str} • ⏱️ {duration_str}{api_calls_str}")

            total_saved += result.pages_saved
            total_skipped += result.pages_skipped
        
        # Totals section
        print("📈 TOTALS")
        print(f"   💾 {total_saved} saved • ⏭️ {total_skipped} skipped" + (f" • 🌐 {total_api_calls} API calls" if total_api_calls > 0 else ""))
    
    # Display failed syncs
    if failed_results:
        print(f"❌ FAILED SYNCS ({len(failed_results)} databases)")
        for failure in failed_results:
            duration_str = f" ({failure['duration']:.1f}s)" if failure['duration'] > 0 else ""
            
            db_name = failure['database_name']
            if '.' in db_name:
                workspace, name = db_name.split('.', 1) 
                db_display = f"{workspace}.{name}"
            else:
                db_display = db_name
                
            print(f"  ⚠️  {db_display}{duration_str} • {failure['error']}")
    # Overall summary
    print("🎯 OVERALL RESULTS")
    
    # Success rate with color coding
    if success_rate == 100:
        rate_emoji = "🎉"
    elif success_rate >= 80:
        rate_emoji = "✅"
    else:
        rate_emoji = "⚠️"
    
    print(f"   {rate_emoji} {len(successful_results)}/{total_databases} databases synced ({success_rate:.1f}%) • ⏱️ {overall_duration:.1f}s")
    print("─" * 30)


async def handle_database_sync_with_browse(args):
    """Handle database sync with Discord channel browser (combining regular sources with Discord selection)."""
    import asyncio
    import sys
    from promaia.cli.discord_commands import handle_discord_browse_filtered
    from promaia.config.workspaces import get_workspace_manager
    
    try:
        # Get workspace
        workspace_manager = get_workspace_manager()
        original_workspace = getattr(args, 'workspace', None)
        
        # Resolve workspace (same logic as chat)
        resolved_workspace = original_workspace
        sources = getattr(args, 'sources', None) or []
        
        # Get browse databases
        browse_databases = getattr(args, 'browse', [])
        
        # Workspace inference logic (same as chat)
        if not resolved_workspace and sources:
            for source in sources:
                if '.' in source:
                    inferred_workspace = source.split('.')[0]
                    if workspace_manager.validate_workspace(inferred_workspace):
                        resolved_workspace = inferred_workspace
                        print(f"INFO: Inferred workspace '{resolved_workspace}' from source '{source}'.")
                        break
        
        # If still no workspace from sources, try to infer from browse databases
        if not resolved_workspace and browse_databases:
            for browse_db in browse_databases:
                # Extract database name from potential database:days format
                db_name = browse_db.split(':')[0] if ':' in browse_db else browse_db
                if '.' in db_name:
                    inferred_workspace = db_name.split('.')[0]
                    if workspace_manager.validate_workspace(inferred_workspace):
                        resolved_workspace = inferred_workspace
                        print(f"INFO: Inferred workspace '{resolved_workspace}' from browse database '{browse_db}'.")
                        break
        
        # If still no workspace, use the default
        if not resolved_workspace:
            resolved_workspace = workspace_manager.get_default_workspace()
            if not resolved_workspace:
                print("No workspace specified, none could be inferred, and no default workspace is configured.", file=sys.stderr)
                return
        
        # Validate workspace
        if not workspace_manager.validate_workspace(resolved_workspace):
            print(f"✗ Workspace '{resolved_workspace}' is not properly configured.", file=sys.stderr)
            return
        
        # Parse browse databases to extract database names and day specifications
        parsed_browse_databases = []
        database_days = {}  # Map database -> days
        
        if browse_databases:
            for browse_spec in browse_databases:
                if ':' in browse_spec:
                    # Format: database:days
                    db_name, days_str = browse_spec.rsplit(':', 1)
                    try:
                        days = int(days_str)
                        parsed_browse_databases.append(db_name)
                        database_days[db_name] = days
                    except ValueError:
                        # If days_str is not a number, treat whole thing as database name
                        parsed_browse_databases.append(browse_spec)
                else:
                    # Just database name, no days specified
                    parsed_browse_databases.append(browse_spec)
        
        # Create args for Discord browse
        class BrowseArgs:
            def __init__(self, workspace, databases=None, database_days=None):
                self.workspace = workspace
                self.databases = databases  # Specific databases to browse, or None for all
                self.database_days = database_days or {}  # Map of database -> days
        
        browse_args = BrowseArgs(resolved_workspace, parsed_browse_databases if parsed_browse_databases else None, database_days)
        
        # Show what we're browsing
        if parsed_browse_databases:
            db_display = []
            for db in parsed_browse_databases:
                if db in database_days:
                    db_display.append(f"{db}:{database_days[db]}")
                else:
                    db_display.append(db)
            print(f"🎮 Launching Discord channel browser for sync - databases: {', '.join(db_display)}...")
        else:
            print(f"🎮 Launching Discord channel browser for sync - workspace '{resolved_workspace}'...")
        
        # Run the Discord browser and get selected channels
        selected_channels = await handle_discord_browse_filtered(browse_args)
        
        if not selected_channels:
            print("ℹ️  No channels selected. Proceeding with regular sources only.")
            # Continue with just the regular sources
            sync_sources = sources
        else:
            print(f"✅ Selected {len(selected_channels)} Discord channels for sync:")
            
            # Convert selected channels to sync source format
            # Group channels by database to avoid redundant syncs
            discord_sources = []
            channels_by_db = {}
            
            # Group channels by database
            for db_name, channel_id, channel_name, days in selected_channels:
                if db_name not in channels_by_db:
                    channels_by_db[db_name] = {'days': days, 'channels': []}
                channels_by_db[db_name]['channels'].append(channel_name)
                
                # Show what was selected
                print(f"   • {db_name}:{days} → #{channel_name}")
            
            # Create consolidated source specs for each database
            for db_name, info in channels_by_db.items():
                days = info['days']
                channels = info['channels']
                
                if len(channels) == 1:
                    # Single channel - simple filter
                    source_spec = f'{db_name}:{days}:"channel_name={channels[0]}"'
                    discord_sources.append(source_spec)
                else:
                    # Multiple channels - use complex filter format
                    # Create OR expression for multiple channels
                    channel_conditions = []
                    for channel in channels:
                        channel_conditions.append(f'discord_channel_name={channel}')
                    complex_expr = ' or '.join(channel_conditions)
                    source_spec = f'{db_name}:{days}:({complex_expr})'
                    discord_sources.append(source_spec)
            
            # Combine regular sources with Discord sources
            sync_sources = sources + discord_sources
        
        if sync_sources:
            print(f"\n🚀 Starting sync with combined sources:")
            print(f"   Regular sources: {sources if sources else 'None'}")
            if 'discord_sources' in locals() and discord_sources:
                print(f"   Discord sources: {discord_sources}")
            else:
                print(f"   Discord sources: None")
        
        # Create modified args for sync (without browse to avoid recursion)
        class SyncArgs:
            def __init__(self, sources, original_args):
                self.sources = sources
                self.workspace = original_workspace
                self.days = getattr(original_args, 'days', None)
                self.force = getattr(original_args, 'force', False)
                self.start_date = getattr(original_args, 'start_date', None)
                self.end_date = getattr(original_args, 'end_date', None)
                self.date_range = getattr(original_args, 'date_range', None)
                self.browse = None  # Clear browse to avoid recursion
        
        sync_args = SyncArgs(sync_sources, args)
        
        # Start sync with combined sources
        await handle_database_sync(sync_args)
        
    except Exception as e:
        print(f"❌ Error in sync with browse: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()


def parse_source_specs(source_specs: List[str]) -> List[Dict[str, Any]]:
    """
    Parse source specifications with support for property filtering.

    Formats supported:
    - database_name
    - database_name:days (e.g., 'journal:7')
    - database_name:all (e.g., 'cms:all')
    - database_name.property=value (e.g., 'cms.Reference=true')
    - database_name:days.property=value (e.g., 'cms:30.KOii_chat=true')
    - database_name#channel:days (e.g., 'trass.tg#koii-work:7')

    Args:
        source_specs: List of source specification strings

    Returns:
        List of parsed source configurations
    """
    parsed_sources = []

    # Get database manager to check for existing databases
    db_manager = get_database_manager()

    # Log timezone information for debugging
    log_timezone_info()

    for spec in source_specs:
        try:
            # Initialize with defaults
            database = None
            days = None
            days_was_specified = False
            property_filters = {}
            comparison_filters = {}
            complex_filter = None  # New: store complex filter expressions

            # Handle Discord channel format: database#channel:days
            # This must be processed before splitting on ':' to extract the database name correctly
            discord_channel_name = None
            if '#' in spec:
                # Split on '#' to separate database from channel
                before_hash = spec.split('#', 1)[0]
                after_hash = spec.split('#', 1)[1]

                # Extract channel name (everything between # and : or end of string)
                if ':' in after_hash:
                    discord_channel_name = after_hash.split(':', 1)[0]
                    # Reconstruct spec without the #channel part for normal parsing
                    # e.g., 'trass.tg#koii-work:7' becomes 'trass.tg:7'
                    spec = before_hash + ':' + after_hash.split(':', 1)[1]
                else:
                    discord_channel_name = after_hash
                    # e.g., 'trass.tg#koii-work' becomes 'trass.tg'
                    spec = before_hash

            # Logic to separate database name from days/filters
            spec_parts = spec.split(':', 1)
            db_spec_part = spec_parts[0]

            db_config = db_manager.get_database_by_qualified_name(db_spec_part)
            if not db_config:
                logger.warning(f"Database '{db_spec_part}' not found in configuration. Skipping.")
                continue

            # If we extracted a Discord channel name, add it as a property filter
            if discord_channel_name:
                property_filters['discord_channel_name'] = discord_channel_name
            
            database = db_config.get_qualified_name()
            
            if len(spec_parts) > 1:
                days_and_filters_part = spec_parts[1]
                days_was_specified = True
                
                # Handle complex filter format: days:(expression)
                if days_and_filters_part.count(':') == 1 and days_and_filters_part.endswith(')') and '(' in days_and_filters_part:
                    # Complex filter format: days:(expression)
                    days_str, filter_part = days_and_filters_part.split(':', 1)
                    
                    # Parse days
                    if days_str.lower() == 'all':
                        days = None
                    else:
                        try:
                            days = int(days_str)
                        except ValueError:
                            logger.warning(f"Invalid days format '{days_str}' in spec '{spec}', using default from config.")
                            days = db_config.default_days
                            days_was_specified = False
                    
                    # Parse complex expression: (discord_channel_name=a or discord_channel_name=b)
                    if filter_part.startswith('(') and filter_part.endswith(')'):
                        complex_expr = filter_part[1:-1]  # Remove parentheses
                        from promaia.cli.database_commands import parse_complex_filter_expression
                        try:
                            complex_filter = parse_complex_filter_expression(complex_expr)
                            logger.info(f"Parsed complex filter for '{database}': {complex_filter}")
                        except Exception as e:
                            logger.warning(f"Failed to parse complex filter '{complex_expr}' in spec '{spec}': {e}")
                    
                    # Set parts to empty for complex filters (no additional processing needed)
                    parts = [days_str]  # Single element list so len(parts) == 1
                
                # Handle Discord channel filter format: days:"channel_name=value"
                elif days_and_filters_part.count(':') == 1 and '"' in days_and_filters_part:
                    # Discord channel filter format: days:"filter"
                    days_str, filter_part = days_and_filters_part.split(':', 1)
                    
                    # Parse days
                    if days_str.lower() == 'all':
                        days = None
                    else:
                        try:
                            days = int(days_str)
                        except ValueError:
                            logger.warning(f"Invalid days format '{days_str}' in spec '{spec}', using default from config.")
                            days = db_config.default_days
                            days_was_specified = False
                    
                    # Parse Discord channel filter: "channel_name=value"
                    if filter_part.startswith('"') and filter_part.endswith('"') and '=' in filter_part:
                        # Extract content within quotes: "channel_name=value" -> channel_name=value
                        inner_content = filter_part[1:-1]  # Remove surrounding quotes
                        if '=' in inner_content:
                            prop_name, prop_value = inner_content.split('=', 1)
                            property_filters[prop_name] = prop_value
                        else:
                            logger.warning(f"Invalid Discord filter format '{filter_part}' in spec '{spec}' - no = found")
                    else:
                        logger.warning(f"Invalid Discord filter format '{filter_part}' in spec '{spec}' - not properly quoted")
                    
                    # Set parts to empty for Discord filters (no additional processing needed)
                    parts = [days_str]  # Single element list so len(parts) == 1
                        
                else:
                    # Regular format: days.property=value
                    parts = days_and_filters_part.split('.', 1)
                    days_str = parts[0]
                    
                    if days_str.lower() == 'all':
                        days = None  # None means all, respecting the existing convention
                    else:
                        try:
                            days = int(days_str)
                        except ValueError:
                            logger.warning(f"Invalid days format '{days_str}' in spec '{spec}', using default from config.")
                            days = db_config.default_days
                            days_was_specified = False # Treat as unspecified if format is bad

                if len(parts) > 1:
                    filter_parts_str = parts[1]
                    for filter_part in filter_parts_str.split('.'):
                        # Check for complex expression
                        if filter_part.startswith('__COMPLEX_EXPR__'):
                            # Extract the actual expression (remove the prefix)
                            complex_expr = filter_part[16:]  # Remove '__COMPLEX_EXPR__' prefix (16 chars)
                            complex_filter = parse_complex_filter_expression(complex_expr)
                        elif '=' in filter_part:
                            prop_name, prop_value = filter_part.split('=', 1)
                            prop_name = prop_name.strip()
                            prop_value = prop_value.strip()
                            
                            # Handle quoted property names and values
                            if prop_name.startswith('"') and prop_value.endswith('"'):
                                prop_name = prop_name[1:]  # Remove leading quote
                                prop_value = prop_value[:-1]  # Remove trailing quote
                            
                            # Handle comparison filters (_after, _before)
                            if prop_name.endswith('_after') or prop_name.endswith('_before'):
                                # Store multiple values for the same filter key in a list
                                if prop_name not in comparison_filters:
                                    comparison_filters[prop_name] = []
                                comparison_filters[prop_name].append(prop_value)
                            else:
                                # Handle regular property filters
                                # Convert string values to appropriate types
                                if prop_value.lower() == 'true':
                                    prop_value = True
                                elif prop_value.lower() == 'false':
                                    prop_value = False
                                elif prop_value.isdigit():
                                    prop_value = int(prop_value)
                                else:
                                    # Special case: don't convert underscores for page_id and Discord properties
                                    discord_properties = ['channel_name', 'data_source', 'page_id']
                                    if prop_name not in discord_properties:
                                        prop_name = prop_name.replace('_', ' ')
                                property_filters[prop_name] = prop_value
                        else:
                             logger.warning(f"Invalid property filter format '{filter_part}' in spec '{spec}'")

            # If days were not specified in the spec string, use the default from the config
            # UNLESS filters are present, in which case ignore days constraint entirely
            if not days_was_specified:
                # Check if any filters are present
                has_filters = (property_filters or comparison_filters or complex_filter)
                if has_filters:
                    days = None  # Ignore days constraint when filters are present
                else:
                    days = db_config.default_days

            parsed_source = {
                'name': database,
                'database': database,
                'qualified_name': database,
                'days': days,
                'property_filters': property_filters,
                'comparison_filters': comparison_filters,
                'complex_filter': complex_filter  # New: include complex filter
            }
            
            parsed_sources.append(parsed_source)
            
            if complex_filter:
                days_desc = "all (filters override)" if days is None and (property_filters or comparison_filters or complex_filter) else days
                logger.info(f"Parsed source: {database}, days: {days_desc}, complex_filter: {complex_filter}")
            else:
                days_desc = "all (filters override)" if days is None and (property_filters or comparison_filters) else days
                logger.info(f"Parsed source: {database}, days: {days_desc}, filters: {property_filters}, comparison_filters: {comparison_filters}")
            
        except Exception as e:
            logger.error(f"Error parsing source spec '{spec}': {e}")
            continue
    
    return parsed_sources

def parse_filter_expression(filter_expr: str) -> Dict[str, Any]:
    """
    Parse a single filter expression and convert it to a format that includes source information.
    
    Now supports source-specific filtering:
        'cms:"Reference"=true' -> {'source': 'cms', 'filter': '"Reference"=true'}
        'journal:created_time>2025-01-01' -> {'source': 'journal', 'filter': 'created_time_after=2025-01-01'}
    
    And complex expressions within a single source:
        'cms:"Reference"=true and "Blog status"=live' -> {'source': 'cms', 'filter': '__COMPLEX_EXPR__"Reference"=true and "Blog status"=live'}
    
    Simple expressions without source prefix (backward compatibility):
        'status=published' -> {'source': None, 'filter': 'status=published'}
    
    Args:
        filter_expr: A filter expression string
        
    Returns:
        Dictionary with 'source' and 'filter' keys, or converted filter expression for backward compatibility
    """
    filter_expr = filter_expr.strip()
    
    # Check for source prefix (source:filter_expression or source.filter_expression)
    # But exclude global contains:"..." syntax which doesn't have a source prefix
    # Updated regex to handle day specifications in source names (e.g., trass.yeeps_discord:30, trass.yp:all)
    # Also handle period separator for simple filters (e.g., trass.yp:14.discord_channel_name=value)
    source_match = re.match(r'^([a-zA-Z0-9_.-]+(?::[0-9]+|:all)?)[:.](.+)$', filter_expr)
    if source_match and not (filter_expr.startswith('contains:"') and ':' not in filter_expr[9:]):
        source = source_match.group(1)
        filter_part = source_match.group(2)
        
        # Check if this is a complex expression with 'or', 'and', or parentheses
        if (' or ' in filter_part.lower() or ' and ' in filter_part.lower() or 
            (filter_part.startswith('(') and filter_part.endswith(')'))):
            # Return source-specific complex filter
            return {'source': source, 'filter': f"__COMPLEX_EXPR__{filter_part}"}
        
        # Check for contains:"search term" syntax in source-specific filters
        if filter_part.startswith('contains:"') and filter_part.endswith('"'):
            # This is a complex filter since it uses the 'contains' operator
            return {'source': source, 'filter': f"__COMPLEX_EXPR__{filter_part}"}
        
        # Check for simplified quoted search syntax: source:"search term"
        if filter_part.startswith('"') and filter_part.endswith('"') and '=' not in filter_part and '>' not in filter_part and '<' not in filter_part:
            # Convert to contains syntax: "search term" -> contains:"search term"
            search_term = filter_part[1:-1]  # Remove quotes
            return {'source': source, 'filter': f"__COMPLEX_EXPR__contains:\"{search_term}\""}
        
        # Handle simple comparison operators
        if '>' in filter_part:
            prop, value = filter_part.split('>', 1)
            converted_filter = f"{prop.strip()}_after={value.strip()}"
        elif '<' in filter_part:
            prop, value = filter_part.split('<', 1)
            converted_filter = f"{prop.strip()}_before={value.strip()}"
        elif '=' in filter_part:
            # Direct equality - no conversion needed
            converted_filter = filter_part
        else:
            # Invalid format
            raise ValueError(f"Invalid filter format: '{filter_part}'. Use 'property=value', 'property>value', 'property<value', '\"search term\"', or contains:\"search term\"")
        
        return {'source': source, 'filter': converted_filter}
    
    # No source prefix - handle as before for backward compatibility
    # Check for contains:"search term" syntax first
    if filter_expr.startswith('contains:"') and filter_expr.endswith('"'):
        # This is a complex filter since it uses the 'contains' operator
        return f"__COMPLEX_EXPR__{filter_expr}"
    
    # Check for simplified quoted search syntax: "search term"
    if filter_expr.startswith('"') and filter_expr.endswith('"') and '=' not in filter_expr and '>' not in filter_expr and '<' not in filter_expr:
        # Convert to contains syntax: "search term" -> contains:"search term"
        search_term = filter_expr[1:-1]  # Remove quotes
        return f"__COMPLEX_EXPR__contains:\"{search_term}\""
    
    # Check if this is a complex expression with 'or' or 'and'
    if ' or ' in filter_expr.lower() or ' and ' in filter_expr.lower():
        # Return a special marker to indicate this needs complex parsing
        return f"__COMPLEX_EXPR__{filter_expr}"
    
    # Handle simple comparison operators (existing logic)
    if '>' in filter_expr:
        prop, value = filter_expr.split('>', 1)
        return f"{prop.strip()}_after={value.strip()}"
    elif '<' in filter_expr:
        prop, value = filter_expr.split('<', 1)
        return f"{prop.strip()}_before={value.strip()}"
    elif '=' in filter_expr:
        # Direct equality - no conversion needed
        return filter_expr
    else:
        # Invalid format
        raise ValueError(f"Invalid filter format: '{filter_expr}'. Use 'property=value', 'property>value', 'property<value', '\"search term\"', or complex expressions with 'and'/'or', or contains:\"search term\"")


def parse_complex_filter_expression(expr: str) -> Dict[str, Any]:
    """
    Parse a complex filter expression with 'or' and 'and' operators.
    
    Examples:
        "created_time<2024-12-30 or created_time>2025-06-30"
        "status=published and created_time>2025-01-01" 
        "created_time<2024-12-30 or created_time>2025-06-30 and status=planned"
        "(channel_name=announcements or channel_name=release-notes)"
    
    Returns:
        Dictionary with parsed conditions and operators for SQL generation
    """
    from typing import List, Union
    
    # Handle parentheses - remove outer parentheses if present
    expr = expr.strip()
    if expr.startswith('(') and expr.endswith(')'):
        expr = expr[1:-1].strip()
    
    # Split on 'or' first (lowest precedence)
    or_clauses = []
    for or_part in expr.split(' or '):
        or_part = or_part.strip()
        
        # Split each OR clause on 'and' (higher precedence)
        and_conditions = []
        for and_part in or_part.split(' and '):
            and_part = and_part.strip()
            
            # Parse individual condition
            condition = parse_single_condition(and_part)
            and_conditions.append(condition)
        
        or_clauses.append(and_conditions)
    
    return {
        'type': 'complex',
        'or_clauses': or_clauses  # List of lists: [[and_conds], [and_conds], ...]
    }


def parse_single_condition(condition: str) -> Dict[str, str]:
    """
    Parse a single condition like 'created_time<2024-12-30' or 'status=published'.
    Now supports quoted property names like '"Reference"=true' and '"Blog status"=live'.
    Also supports contains:"search term" for full content search.
    
    Returns:
        Dictionary with property, operator, and value
    """
    condition = condition.strip()
    
    # Handle contains:"search term" syntax for full content search
    contains_match = re.match(r'^contains:"([^"]*)"$', condition)
    if contains_match:
        search_term = contains_match.group(1)
        return {'property': '_content', 'operator': 'contains', 'value': search_term}
    
    # Handle simplified quoted search syntax: "search term"
    if condition.startswith('"') and condition.endswith('"') and '=' not in condition and '>' not in condition and '<' not in condition:
        search_term = condition[1:-1]  # Remove quotes
        return {'property': '_content', 'operator': 'contains', 'value': search_term}
    
    # Handle quoted property names
    # Look for patterns like "Property Name"=value or "Property Name">value
    quoted_prop_match = re.match(r'^"([^"]+)"([><=]+)(.*)$', condition)
    if quoted_prop_match:
        prop = quoted_prop_match.group(1)
        operator = quoted_prop_match.group(2)
        value = quoted_prop_match.group(3).strip()
        return {'property': prop, 'operator': operator, 'value': value}
    
    # Handle unquoted property names (existing logic)
    if '>=' in condition:
        prop, value = condition.split('>=', 1)
        return {'property': prop.strip(), 'operator': '>=', 'value': value.strip()}
    elif '<=' in condition:
        prop, value = condition.split('<=', 1)
        return {'property': prop.strip(), 'operator': '<=', 'value': value.strip()}
    elif '>' in condition:
        prop, value = condition.split('>', 1)
        return {'property': prop.strip(), 'operator': '>', 'value': value.strip()}
    elif '<' in condition:
        prop, value = condition.split('<', 1)
        return {'property': prop.strip(), 'operator': '<', 'value': value.strip()}
    elif '=' in condition:
        prop, value = condition.split('=', 1)
        return {'property': prop.strip(), 'operator': '=', 'value': value.strip()}
    else:
        raise ValueError(f"Invalid condition format: '{condition}'. Use 'property=value', 'property>value', 'property<value', '\"search term\"', or contains:\"search term\"")


def build_sql_from_complex_filter(complex_filter: Dict[str, Any], date_filter_prop: str) -> tuple[str, List[str]]:
    """
    Build SQL WHERE clause and parameters from a complex filter expression.
    
    Args:
        complex_filter: Parsed complex filter from parse_complex_filter_expression
        date_filter_prop: The date property name to use for date comparisons (fallback)
        
    Returns:
        Tuple of (sql_where_clause, parameters_list)
    """
    if complex_filter['type'] != 'complex':
        raise ValueError("Expected complex filter type")
    
    or_clauses_sql = []
    params = []
    
    for and_conditions in complex_filter['or_clauses']:
        and_clauses_sql = []
        
        for condition in and_conditions:
            prop = condition['property']
            op = condition['operator']
            value = condition['value']
            
            # Handle date properties - use the actual property specified in the filter
            if prop in ['created_time', 'last_edited_time']:
                # Use the property specified in the filter, not the default
                actual_date_prop = prop
                if op == '>':
                    and_clauses_sql.append(f"datetime({actual_date_prop}) > datetime(?)")
                elif op == '>=':
                    and_clauses_sql.append(f"datetime({actual_date_prop}) >= datetime(?)")
                elif op == '<':
                    and_clauses_sql.append(f"datetime({actual_date_prop}) < datetime(?)")
                elif op == '<=':
                    and_clauses_sql.append(f"datetime({actual_date_prop}) <= datetime(?)")
                elif op == '=':
                    and_clauses_sql.append(f"date({actual_date_prop}) = date(?)")
                params.append(value)
            elif prop == date_filter_prop:
                # Handle case where filter uses the configured date property
                if op == '>':
                    and_clauses_sql.append(f"datetime({date_filter_prop}) > datetime(?)")
                elif op == '>=':
                    and_clauses_sql.append(f"datetime({date_filter_prop}) >= datetime(?)")
                elif op == '<':
                    and_clauses_sql.append(f"datetime({date_filter_prop}) < datetime(?)")
                elif op == '<=':
                    and_clauses_sql.append(f"datetime({date_filter_prop}) <= datetime(?)")
                elif op == '=':
                    and_clauses_sql.append(f"date({date_filter_prop}) = date(?)")
                params.append(value)
            else:
                # Handle regular properties (these would need to be in JSON metadata)
                # For now, we'll note that these can't be filtered at SQL level
                # and need to be handled post-query
                and_clauses_sql.append("1=1")  # Always true, will filter later
                # We'll store these for post-SQL filtering
        
        if and_clauses_sql:
            or_clauses_sql.append(f"({' AND '.join(and_clauses_sql)})")
    
    if or_clauses_sql:
        where_clause = f"({' OR '.join(or_clauses_sql)})"
        return where_clause, params
    else:
        return "", []

def parse_filter_string(filter_str: str) -> Dict[str, Any]:
    """Parse filter string like 'date>-30d,status=published'."""
    filters = {}
    
    for filter_expr in filter_str.split(','):
        filter_expr = filter_expr.strip()
        
        # Handle date filters
        if '>' in filter_expr or '<' in filter_expr:
            if '>' in filter_expr:
                prop, value = filter_expr.split('>', 1)
                filters[f"{prop.strip()}_after"] = value.strip()
            elif '<' in filter_expr:
                prop, value = filter_expr.split('<', 1)
                filters[f"{prop.strip()}_before"] = value.strip()
        
        # Handle equality filters
        elif '=' in filter_expr:
            prop, value = filter_expr.split('=', 1)
            filters[prop.strip()] = value.strip()
    
    return filters

def build_filters(source_spec: Dict[str, Any], db_config) -> List[QueryFilter]:
    """Build QueryFilter objects from source specification and database config."""
    filters = []
    
    # Add filters from source specification
    logger.debug(f"Source spec property_filters: {source_spec.get('property_filters', {})}")
    for key, value in source_spec.get("property_filters", {}).items():
        if not key.endswith(('_after', '_before')):  # Skip date filters
            logger.debug(f"Adding source filter: {key} = {value}")
            filters.append(QueryFilter(key, "eq", value))
    
    # Add filters from database configuration
    logger.debug(f"Database config property_filters: {db_config.property_filters}")
    for prop_name, prop_values in db_config.property_filters.items():
        if isinstance(prop_values, list):
            logger.debug(f"Adding config filter: {prop_name} in {prop_values}")
            filters.append(QueryFilter(prop_name, "in", prop_values))
        else:
            logger.debug(f"Adding config filter: {prop_name} = {prop_values}")
            filters.append(QueryFilter(prop_name, "eq", prop_values))
    
    logger.debug(f"Final filters: {[(f.property_name, f.operator, f.value) for f in filters]}")
    return filters

def build_date_filter(source_spec: Dict[str, Any], db_config, args) -> Optional[DateRangeFilter]:
    """Build DateRangeFilter from source specification and arguments."""
    force_sync = getattr(args, 'force', False)
    
    # Check if days or date ranges were specified
    has_days_spec = source_spec.get("days") is not None
    has_days_arg = hasattr(args, 'days') and args.days is not None
    has_date_range = hasattr(args, 'date_range') and args.date_range
    has_start_date = hasattr(args, 'start_date') and args.start_date
    has_end_date = hasattr(args, 'end_date') and args.end_date
    
    # Check for date filters in source spec (e.g., database[date_after>2023-01-01])
    spec_filters = source_spec.get("filters", {})
    comparison_filters = source_spec.get("comparison_filters", {})
    all_filters = {**spec_filters, **comparison_filters}
    has_spec_date_filters = any(key.endswith('_after') or key.endswith('_before') for key in all_filters.keys())
    
    # Case 1: --force without any date/days specification (sync all, respecting other filters if any)
    if force_sync and not has_days_spec and not has_days_arg and not has_date_range and not has_start_date and not has_end_date and not has_spec_date_filters:
        # No specific date range, sync all (or based on other non-date filters)
        # If a date_prop was specified in db_config (e.g. for "Date" field), respect it for Notion query
        # otherwise, no date filter is applied here by default for --force. Connector might have its own.
        logger.debug(f"Using --force without days specification, so no date filter will be applied.")
        return None
    
    date_prop = db_config.date_filters.get("property") # Default to None, will be handled
    
    spec_start_date_str = None
    spec_end_date_str = None
    
    for key, value in all_filters.items():
        if key.endswith('_after'):
            spec_start_date_str = value
            if not date_prop: # If a date filter is in spec, use its property
                date_prop = key.replace('_after', '')
        elif key.endswith('_before'):
            spec_end_date_str = value
            if not date_prop: # If a date filter is in spec, use its property
                date_prop = key.replace('_before', '')

    start_date = parse_date_value(spec_start_date_str) if spec_start_date_str else None
    end_date = parse_date_value(spec_end_date_str) if spec_end_date_str else None

    # Handle new command-line date arguments
    if hasattr(args, 'date_range') and args.date_range:
        # Parse date range like "2025-02-01,2025-03-31"
        try:
            range_parts = args.date_range.split(',')
            if len(range_parts) == 2:
                start_date = parse_date_value(range_parts[0].strip())
                end_date = parse_date_value(range_parts[1].strip())
                if not date_prop:
                    date_prop = "created_time"  # Default for date ranges
        except Exception as e:
            logger.warning(f"Invalid date range format '{args.date_range}': {e}")
    
    # Handle individual start/end date arguments (override date_range if both specified)
    explicit_dates_provided = False
    if hasattr(args, 'start_date') and args.start_date:
        start_date = parse_date_value(args.start_date)
        explicit_dates_provided = True
        if not date_prop:
            date_prop = "created_time"
    
    if hasattr(args, 'end_date') and args.end_date:
        end_date = parse_date_value(args.end_date)
        explicit_dates_provided = True
        if not date_prop:
            date_prop = "created_time"

    # Case 2: Source-specific days (e.g., journal:30) - but only if no explicit dates provided
    if source_spec.get("days") is not None and not explicit_dates_provided:
        source_days = source_spec.get("days")
        if source_days == 'all':
            # Sync all for this source
            effective_date_prop = date_prop or db_config.date_filters.get("property", "created_time")
            logger.debug(f"Using source days 'all'. Date prop: {effective_date_prop}. No date range limit.")
            return DateRangeFilter(property_name=effective_date_prop, start_date=None, end_date=None)
        else:
            days_to_sync = int(source_days)
            effective_date_prop = "created_time" if force_sync else db_config.date_filters.get("property", "last_edited_time")
            if not date_prop: date_prop = effective_date_prop

            start_date_from_days = days_ago_utc(days_to_sync)
            if start_date and start_date > start_date_from_days:
                pass # start_date from spec is already set and more restrictive
            else:
                start_date = start_date_from_days

            logger.debug(f"Using source days ({days_to_sync}). Date prop: {date_prop}. Start: {start_date}, End: {end_date}")
            return DateRangeFilter(property_name=date_prop or "last_edited_time", start_date=start_date, end_date=end_date)

    # Case 3: --days argument is provided - but only if no explicit dates provided
    if hasattr(args, 'days') and args.days is not None and not explicit_dates_provided:
        days_to_sync = args.days if isinstance(args.days, int) else db_config.default_days
        # If --force, use created_time to get all items within the --days range
        # If not --force, it will effectively get items *created* within --days 
        # AND *modified* since last sync (Notion connector handles this with force=False)
        # However, a simpler approach for --days without --force is to get items *modified* in the last N days.
        effective_date_prop = "created_time" if force_sync else db_config.date_filters.get("property", "last_edited_time")
        if not date_prop: date_prop = effective_date_prop # Ensure date_prop is set if not from spec

        start_date_from_days = days_ago_utc(days_to_sync)
        # If start_date from spec is more recent, use it
        if start_date and start_date > start_date_from_days:
            pass # start_date from spec is already set and more restrictive
        else:
            start_date = start_date_from_days
        # end_date from spec can remain if set

        logger.debug(f"Using --days ({days_to_sync}). Date prop: {date_prop}. Start: {start_date}, End: {end_date}")
        return DateRangeFilter(property_name=date_prop or "last_edited_time", start_date=start_date, end_date=end_date)

    # Case 4: Date filters are provided in the source specification (e.g., journal[date_prop_after>2023-01-01])
    if start_date or end_date:
        if not date_prop: # Should have been set if _after or _before was found
            logger.warning("Date filter found in spec, but date property could not be determined. Defaulting to 'last_edited_time'.")
            date_prop = "last_edited_time"
        logger.debug(f"Using date filter from source spec. Date prop: {date_prop}. Start: {start_date}, End: {end_date}")
        return DateRangeFilter(property_name=date_prop, start_date=start_date, end_date=end_date)

    # Case 5: Default incremental sync (no --days, no --force, no date spec)
    # Use last_sync_time and 'last_edited_time'
    if db_config.last_sync_time:
        try:
            last_sync = datetime.fromisoformat(db_config.last_sync_time)
            # Add a small buffer to avoid precision issues with Notion's last_edited_time
            # Sync items edited strictly *after* the last sync time.
            start_date = last_sync + timedelta(seconds=1) 
            date_prop_for_incremental = "last_edited_time" # Notion's standard property
            logger.debug(f"Incremental sync. Date prop: {date_prop_for_incremental}. Start: {start_date} (from last_sync_time: {db_config.last_sync_time})")
            return DateRangeFilter(property_name=date_prop_for_incremental, start_date=start_date, end_date=None)
        except ValueError:
            logger.warning(f"Could not parse last_sync_time '{db_config.last_sync_time}'. Defaulting to full sync for relevant period or default_days.")
            # Fallback to default_days if last_sync_time is invalid
            days_to_sync = db_config.default_days
            effective_date_prop = db_config.date_filters.get("property", "last_edited_time")
            start_date = days_ago_utc(days_to_sync)
            logger.debug(f"Fallback to default_days ({days_to_sync}) due to invalid last_sync_time. Date prop: {effective_date_prop}. Start: {start_date}")
            return DateRangeFilter(property_name=effective_date_prop, start_date=start_date, end_date=None)
            
    # Case 6: Initial sync or no last_sync_time (and no --force, no --days, no date spec)
    # Sync based on default_days using 'created_time' or configured date_prop
    logger.debug(f"Initial sync or no valid last_sync_time. Using default_days: {db_config.default_days}")
    days_to_sync = db_config.default_days
    # For initial sync, it's common to get recently *created* items.
    # Or, if db_config specifies a date_filter property like "Date", use that.
    initial_sync_date_prop = db_config.date_filters.get("property", "created_time") 
    start_date = days_ago_utc(days_to_sync)
    return DateRangeFilter(property_name=initial_sync_date_prop, start_date=start_date, end_date=None)

def parse_date_value(value: str) -> Optional[datetime]:
    """Parse date value like '-30d', '2024-01-01', etc."""
    if value.startswith('-') and value.endswith('d'):
        # Relative days
        try:
            days = int(value[1:-1])
            return days_ago_utc(days)
        except ValueError:
            return None
    
    # Try parsing as ISO date
    try:
        dt = datetime.fromisoformat(value)
        # If timezone-naive, assume UTC
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        return None

async def handle_database_info(args):
    """Handle 'maia database info' command."""
    if not args.name:
        print("Database name is required")
        return
    
    db_config = get_database_config(args.name)
    if not db_config:
        print(f"Database '{args.name}' not found")
        return
    
    print(f"Database: {args.name}")
    print(f"  Type: {db_config.source_type}")
    print(f"  ID: {db_config.database_id}")
    print(f"  Description: {db_config.description}")
    print(f"  Sync enabled: {db_config.sync_enabled}")
    print(f"  Output directory: {db_config.output_directory}")
    print(f"  Default days: {db_config.default_days}")
    
    if db_config.property_filters:
        print("  Property filters:")
        for prop, values in db_config.property_filters.items():
            print(f"    {prop}: {values}")
    
    # Test connection and get schema
    try:
        connector = ConnectorRegistry.get_connector(db_config.source_type, db_config.to_dict())
        if connector:
            if await connector.test_connection():
                print("  Connection: ✓ Working")
                
                if args.schema:
                    schema = await connector.get_database_schema()
                    if schema:
                        print("  Schema:")
                        for prop_name, prop_type in schema.items():
                            print(f"    {prop_name}: {prop_type}")
            else:
                print("  Connection: ✗ Failed")
    except Exception as e:
        print(f"  Connection: ✗ Error - {e}")

async def handle_database_push(args):
    """Handle 'maia database push' command - push local changes to Notion."""
    from promaia.storage.json_editor import NotionJSONEditor
    from promaia.notion.client import notion_client
    from promaia.notion.schema import create_page_with_schema, get_database_schema
    from promaia.utils.config_loader import get_notion_database_id
    from promaia.config.workspaces import get_workspace_manager
    
    # Parse what to push
    target = getattr(args, 'target', 'all')
    dry_run = getattr(args, 'dry_run', False)
    
    # Get workspace information
    workspace_manager = get_workspace_manager()
    workspace = getattr(args, 'workspace', None) or workspace_manager.get_default_workspace()
    
    if not workspace:
        print("❌ No workspace available. Please configure a workspace first.")
        return
    
    # Create workspace-aware editor
    editor = NotionJSONEditor(workspace_root=os.getcwd())
    editor.data_dir = os.path.join(os.getcwd(), "data", workspace, "json")
    
    if target == 'all':
        # Find all content types with pending changes
        content_types = []
        data_dir = os.path.join(os.getcwd(), "data", workspace, "json")
        if os.path.exists(data_dir):
            for item in os.listdir(data_dir):
                item_path = os.path.join(data_dir, item)
                if os.path.isdir(item_path):
                    content_types.append(item)
    else:
        content_types = [target]
    
    total_pushed = 0
    total_errors = 0
    
    print(f"🌐 Using workspace: {workspace}")
    
    for content_type in content_types:
        print(f"\n=== Processing {content_type} ===")
        
        try:
            # Get database ID for this content type with workspace context
            # First try workspace.content_type format, then just content_type
            database_id = None
            
            # Try workspace-qualified name first
            qualified_content_type = f"{workspace}.{content_type}"
            try:
                database_id = get_notion_database_id(qualified_content_type)
            except (FileNotFoundError, ValueError):
                pass
            
            # Fall back to simple content type
            if not database_id:
                try:
                    database_id = get_notion_database_id(content_type)
                except (FileNotFoundError, ValueError):
                    pass
            
            if not database_id:
                print(f"❌ No database configured for content type '{content_type}' in workspace '{workspace}'")
                continue
                
            # Get database schema for property validation
            schema = await get_database_schema(database_id)
            
            # Find all pages that need to be pushed
            content_dir = os.path.join(os.getcwd(), "data", workspace, "json", content_type)
            if not os.path.exists(content_dir):
                print(f"📂 No local data found for {content_type}")
                continue
            
            pages_to_create = []
            pages_to_update = []
            
            for filename in os.listdir(content_dir):
                if filename.endswith('.json') and 'backup' not in filename:
                    filepath = os.path.join(content_dir, filename)
                    try:
                        with open(filepath, 'r', encoding='utf-8') as f:
                            page_data = json.load(f)
                        
                        # Check if this page needs to be pushed
                        if page_data.get('created_locally', False) or page_data.get('sync_status') == 'pending_creation':
                            pages_to_create.append((filepath, page_data))
                        elif page_data.get('sync_status') == 'pending_update' or should_push_page(page_data):
                            pages_to_update.append((filepath, page_data))
                            
                    except Exception as e:
                        print(f"⚠️  Error reading {filename}: {e}")
                        total_errors += 1
            
            print(f"📋 Found {len(pages_to_create)} pages to create, {len(pages_to_update)} pages to update")
            
            if dry_run:
                print("🔍 DRY RUN - No changes will be made to Notion")
                for filepath, page_data in pages_to_create:
                    print(f"  CREATE: {page_data['title']}")
                for filepath, page_data in pages_to_update:
                    print(f"  UPDATE: {page_data['title']} (ID: {page_data['page_id']})")
                continue
            
            # Create new pages
            for filepath, page_data in pages_to_create:
                try:
                    print(f"📝 Creating: {page_data['title']}")
                    
                    # Extract initial content from the local page
                    initial_content = extract_content_for_creation(page_data)
                    
                    # Create the page in Notion
                    response = await create_page_with_schema(database_id, page_data['title'], initial_content)
                    
                    if response and response.get('id'):
                        # Update local page with real Notion ID and clear creation flags
                        page_data['page_id'] = response['id']
                        page_data['created_locally'] = False
                        page_data['sync_status'] = 'synced'
                        page_data['last_synced'] = datetime.now().isoformat()
                        page_data['notion_url'] = response.get('url')
                        
                        # Save updated local page
                        with open(filepath, 'w', encoding='utf-8') as f:
                            json.dump(page_data, f, indent=2, ensure_ascii=False)
                        
                        # Update registry sync status
                        from promaia.storage.hybrid_storage import get_hybrid_registry
                        registry = get_hybrid_registry()
                        # Note: sync status tracking will be implemented in hybrid registry if needed
                        # For now, just log the successful creation
                        logger.info(f"Page {response['id']} created successfully")
                        
                        print(f"✅ Created successfully: {response['id']}")
                        total_pushed += 1
                    else:
                        print(f"❌ Failed to create page: Unexpected response")
                        total_errors += 1
                        
                except Exception as e:
                    print(f"❌ Error creating {page_data['title']}: {e}")
                    total_errors += 1
            
            # Update existing pages
            for filepath, page_data in pages_to_update:
                try:
                    print(f"📝 Updating: {page_data['title']} (ID: {page_data['page_id']})")
                    
                    # Prepare properties for update (excluding read-only ones)
                    readonly_props = {'Last edited time', 'Created time', 'Created by', 'Last edited by'}
                    props = page_data['notion_data']['properties']
                    syncable_props = {k: v for k, v in props.items() if k not in readonly_props}
                    
                    # Update page properties
                    await notion_client.pages.update(
                        page_id=page_data['page_id'],
                        properties=syncable_props
                    )
                    
                    # TODO: Handle content block updates here if needed
                    
                    # Update local sync status
                    page_data['sync_status'] = 'synced'
                    page_data['last_synced'] = datetime.now().isoformat()
                    
                    with open(filepath, 'w', encoding='utf-8') as f:
                        json.dump(page_data, f, indent=2, ensure_ascii=False)
                    
                    # Update registry sync status
                    from promaia.storage.hybrid_storage import get_hybrid_registry
                    registry = get_hybrid_registry()
                    # Note: sync status tracking will be implemented in hybrid registry if needed
                    # For now, just log the successful update
                    logger.info(f"Page {page_data['page_id']} updated successfully")
                    
                    print(f"✅ Updated successfully")
                    total_pushed += 1
                    
                except Exception as e:
                    print(f"❌ Error updating {page_data['title']}: {e}")
                    total_errors += 1
            
        except Exception as e:
            print(f"❌ Error processing {content_type}: {e}")
            total_errors += 1
    
    print(f"\n=== SUMMARY ===")
    print(f"✅ Successfully pushed: {total_pushed}")
    print(f"❌ Errors: {total_errors}")
    if dry_run:
        print("🔍 This was a dry run - no actual changes were made")

def should_push_page(page_data: Dict[str, Any]) -> bool:
    """Determine if a page should be pushed based on its sync status."""
    # Check if page has been modified since last sync
    saved_at = page_data.get('saved_at')
    last_synced = page_data.get('last_synced')
    
    if not last_synced:
        return True  # Never synced
    
    if not saved_at:
        return False  # No save timestamp
    
    try:
        saved_dt = datetime.fromisoformat(saved_at)
        synced_dt = datetime.fromisoformat(last_synced)
        return saved_dt > synced_dt
    except ValueError:
        return True  # Can't parse dates, assume needs sync

def extract_content_for_creation(page_data: Dict[str, Any]) -> str:
    """Extract content from local page data for creation in Notion."""
    content_blocks = page_data.get('notion_data', {}).get('content', [])
    
    if not content_blocks:
        return ""
    
    # Convert blocks to plain text for initial content
    text_parts = []
    for block in content_blocks:
        block_type = block.get('type')
        if block_type in ['paragraph', 'heading_1', 'heading_2', 'heading_3', 'bulleted_list_item']:
            rich_text = block.get(block_type, {}).get('rich_text', [])
            
            block_text_parts = []
            for item in rich_text:
                # Handle both formats: plain_text (from Notion API) and text.content (from local creation)
                text_content = item.get('plain_text', '')
                if not text_content:
                    # Try the local creation format
                    text_content = item.get('text', {}).get('content', '')
                
                if text_content:
                    block_text_parts.append(text_content)
            
            block_text = ''.join(block_text_parts)
            if block_text.strip():
                text_parts.append(block_text)
    
    return '\n\n'.join(text_parts)

async def handle_database_status(args):
    """Handle 'maia database status' command - show what needs to be synced."""
    from promaia.storage.hybrid_storage import get_hybrid_registry
    from promaia.config.databases import get_database_manager
    
    target = getattr(args, 'target', 'all')
    registry = get_hybrid_registry()
    db_manager = get_database_manager()
    
    if target == 'all':
        # Get unique database names from actual content
        content_list = registry.list_content()
        content_types = list(set(item['database_name'] for item in content_list))
    else:
        content_types = [target]
    
    total_to_sync = 0
    total_synced = 0
    
    for content_type in content_types:
        print(f"\n=== {content_type} ===")
        
        # Get pages from hybrid_metadata.db for this content type
        content_list = registry.list_content(database_name=content_type)
        
        if not content_list:
            print(f"📂 No local data found")
            continue
        
        needs_sync = []
        is_synced = []
        
        for item in content_list:
            title = item.get('title', 'Unknown')
            sync_status = item.get('sync_status', 'unknown')
            
            if sync_status != 'synced':
                needs_sync.append(title)
            else:
                is_synced.append(title)
        
        if needs_sync:
            print(f"📝 Needs sync ({len(needs_sync)}):")
            for title in needs_sync[:5]:  # Show first 5
                print(f"  • {title}")
            if len(needs_sync) > 5:
                print(f"  ... and {len(needs_sync) - 5} more")
        
        if is_synced:
            print(f"✅ Synced: {len(is_synced)} pages")
        
        total_to_sync += len(needs_sync)
        total_synced += len(is_synced)
    
    print(f"\n=== OVERALL STATUS ===")
    print(f"📝 Needs sync: {total_to_sync}")
    print(f"✅ Synced: {total_synced}")
    
    if total_to_sync > 0:
        if target == 'all':
            print(f"\nTo push all changes: maia database push all")
        else:
            print(f"\nTo push changes: maia database push {target}")

async def handle_database_list_sources(args):
    """Handle 'maia database list-sources' command."""
    db_manager = get_database_manager()
    databases = db_manager.list_databases()
    
    source_names = []
    for db_name in databases:
        db_config = db_manager.get_database(db_name)
        if db_config:
            source_names.append(db_config.get_qualified_name())
            
    print(json.dumps(source_names))

async def handle_validate_registry(args):
    """Handle 'maia database validate-registry' command."""
    from promaia.config.registry_sync import get_config_registry_sync
    
    try:
        sync_manager = get_config_registry_sync()
        
        print("🔍 Validating registry synchronization with configuration...")
        validation = sync_manager.validate_registry_sync()
        
        print(f"\n📊 Validation Results:")
        print(f"  Databases checked: {validation['databases_checked']}")
        print(f"  Registry in sync: {'✓ Yes' if validation['in_sync'] else '✗ No'}")
        
        if validation['issues']:
            print(f"\n⚠️  Issues found:")
            for issue in validation['issues']:
                print(f"    - {issue}")
        
        if validation['missing_registrations']:
            print(f"\n📝 Missing registrations:")
            for missing in validation['missing_registrations']:
                print(f"    - {missing['database']}: {missing['count']} files not registered")
        
        if validation['orphaned_entries']:
            print(f"\n🗑️  Orphaned registry entries:")
            for orphaned in validation['orphaned_entries']:
                print(f"    - {orphaned['database']}: {orphaned['count']} entries without files")
        
        if validation['recommendations']:
            print(f"\n💡 Recommendations:")
            for rec in validation['recommendations']:
                print(f"    - {rec}")
        
        if args.auto_fix and not validation['in_sync']:
            print(f"\n🔧 Auto-fixing issues...")
            fix_results = sync_manager.auto_register_missing_files(dry_run=args.dry_run)
            
            if fix_results['success']:
                if args.dry_run:
                    print(f"Would register {fix_results['registered_count']} files")
                else:
                    print(f"✓ Successfully registered {fix_results['registered_count']} files")
                
                if fix_results['databases_processed']:
                    print("  Processed databases:")
                    for db in fix_results['databases_processed']:
                        print(f"    - {db}")
            else:
                print("✗ Auto-fix failed:")
                for error in fix_results['errors']:
                    print(f"    - {error}")
        
        print("\n" + "="*50)
        
    except Exception as e:
        print(f"Error: {e}")
        raise

async def handle_register_markdown_files(args):
    """Handle 'maia database register-markdown-files' command."""
    import glob
    from datetime import datetime
    from promaia.storage.hybrid_storage import get_hybrid_registry
    
    try:
        db_manager = get_database_manager()
        registry = get_hybrid_registry()
        
        # Get databases to process
        databases_to_process = []
        for db_name in db_manager.list_databases():
            db_config = db_manager.get_database(db_name)
            
            # Filter by workspace and database if specified
            if args.workspace and db_config.workspace != args.workspace:
                continue
            if args.database and db_config.nickname != args.database:
                continue
            databases_to_process.append(db_config)
        
        if not databases_to_process:
            print("No databases found matching criteria.")
            return
        
        total_registered = 0
        
        for db_config in databases_to_process:
            print(f"\nProcessing {db_config.get_qualified_name()}...")
            
            # Check if markdown directory exists
            md_dir = db_config.markdown_directory
            if not md_dir or not os.path.exists(md_dir):
                print(f"  Warning: Markdown directory not found or not configured: {md_dir}")
                continue
            
            # Get existing registry entries for this database
            existing_entries = registry.query_content(
                workspace=db_config.workspace,
                database_name=db_config.get_qualified_name()
            )
            existing_page_ids = {entry['page_id'] for entry in existing_entries if entry.get('page_id')}
            
            # Find markdown files recursively
            md_files = glob.glob(os.path.join(md_dir, "**/*.md"), recursive=True)
            print(f"  Found {len(md_files)} markdown files")
            print(f"  Found {len(existing_entries)} existing registry entries")
            
            registered_count = 0
            
            for md_file in md_files:
                try:
                    import re  # Import at the beginning to avoid scope issues
                    filename = os.path.basename(md_file)
                    
                    # Extract page ID from filename - supports Notion UUIDs, Gmail threads, and Discord messages
                    page_id_match = re.search(r'(?:msg_|thread_)?([a-f0-9-]{16,}|[a-f0-9]{32})', filename, re.IGNORECASE)
                    if not page_id_match:
                        # Fallback for Notion pages with format: Title last-part-of-uuid.md
                        page_id_match = re.search(r'([a-f0-9]{32})\.md$', filename)
                        if not page_id_match:
                            logger.debug(f"Skipping {filename}: No page ID found in standard formats.")
                            continue
                    
                    page_id = page_id_match.group(1)
                    
                    # Skip if already registered
                    if page_id in existing_page_ids:
                        continue
                    
                    # Extract title and date from filename
                    title_match = re.match(r'(\d{4}-\d{2}-\d{2})\s+(.+?)\s+', filename)
                    if title_match:
                        date_str = title_match.group(1)
                        title = title_match.group(2).strip()
                        created_time = f"{date_str}T00:00:00Z"
                    else:
                        title = re.sub(r'\s+[a-f0-9-]{16,}\.md$', '', filename, flags=re.IGNORECASE).strip()
                        file_mtime = datetime.fromtimestamp(os.path.getmtime(md_file))
                        created_time = file_mtime.isoformat() + "Z"
                    
                    if args.dry_run:
                        print(f"    Would register: {title} ({page_id})")
                        registered_count += 1
                    else:
                        # Extract metadata based on content type
                        metadata = {}
                        
                        # For Discord files, extract channel information
                        if db_config.source_type == 'discord':
                            # Extract channel from file path
                            rel_path = os.path.relpath(md_file, get_project_root())
                            path_parts = rel_path.split(os.sep)
                            
                            # Find channel name in path (usually the parent directory)
                            channel_name = None
                            if len(path_parts) >= 2:
                                channel_name = path_parts[-2]  # Parent directory is usually channel
                            
                            # Read file content to extract Discord-specific metadata
                            try:
                                with open(md_file, 'r', encoding='utf-8') as f:
                                    content = f.read()
                                    
                                # Extract channel from content if available
                                channel_match = re.search(r'\*\*Channel:\*\*\s*(#[^*\n]+)', content)
                                if channel_match:
                                    channel_name = channel_match.group(1).strip()
                                
                                # Extract timestamp 
                                timestamp_match = re.search(r'\*\*Timestamp:\*\*\s*([^\n]+)', content)
                                if timestamp_match:
                                    metadata['timestamp'] = timestamp_match.group(1).strip()
                                
                                # Extract author
                                author_match = re.search(r'\*\*Author:\*\*\s*([^\n]+)', content)
                                if author_match:
                                    metadata['author'] = author_match.group(1).strip()
                                    
                            except Exception as e:
                                print(f"Warning: Could not read Discord file {md_file}: {e}")
                            
                            if channel_name:
                                metadata['channel_name'] = channel_name
                                # Also set discord_channel_name for filter compatibility
                                metadata['discord_channel_name'] = channel_name
                                
                        # Create content data for registration
                        content_data = {
                            'title': title,
                            'created_time': created_time,
                            'last_edited_time': created_time,
                            'synced_time': datetime.now().isoformat() + "Z",
                            'page_id': page_id,
                            'source': 'markdown_file_registration',
                            'workspace': db_config.workspace,
                            'database_id': db_config.database_id,  # Add immutable database identifier
                            'database_name': db_config.get_qualified_name(),
                            'file_path': os.path.relpath(md_file, get_project_root()),
                            'content_type': db_config.source_type,
                            'metadata': metadata 
                        }
                        
                        # Register in database using generic content table
                        success = registry.add_generic_content(content_data)
                        
                        if success:
                            # print(f"    Registered: {title} ({page_id})")
                            registered_count += 1
                        else:
                            print(f"    Failed to register: {title} ({page_id})")
                            
                except Exception as e:
                    print(f"    Error processing {md_file}: {e}")
                    import traceback
                    traceback.print_exc()
                    continue
            
            action = "Would register" if args.dry_run else "Registered"
            print(f"  {action} {registered_count} new files")
            total_registered += registered_count
        
        action = "Would register" if args.dry_run else "Registered"
        print(f"\n{action} {total_registered} total files across all databases.")
        
        if args.dry_run:
            print("\nRun without --dry-run to actually register the files.")
        
    except Exception as e:
        print(f"Error: {e}")
        raise

# Add argument parsers for database commands
def add_database_commands(subparsers):
    """Adds database-related subparsers to the main parser."""
    db_parser = subparsers.add_parser('database', help='Manage databases')
    db_subparsers = db_parser.add_subparsers(dest='database_command', help='Database commands')
    add_database_commands_to_existing_parser(db_parser, db_subparsers)
    return db_parser

def add_database_commands_to_existing_parser(parent_parser, subparsers):
    """Helper function to add database subcommands to any parser with aliases."""
    
    # List databases
    list_parser = subparsers.add_parser('list', help='List configured databases')
    list_parser.set_defaults(func=handle_database_list)
    
    # Add 'ls' alias for list
    ls_parser = subparsers.add_parser('ls', help='List configured databases (alias for list)')
    ls_parser.set_defaults(func=handle_database_list)
    
    # Add database
    add_parser = subparsers.add_parser('add', help='Add a new database')
    add_parser.add_argument('name', nargs='?', help='Name of the database (e.g., "journal")')
    add_parser.add_argument('--source-type', help='Source type (e.g., notion)')
    add_parser.add_argument('--id', '--database-id', dest='database_id', help='Database ID (get from Notion URL: notion.so/workspace/DATABASE_ID?v=...)')
    add_parser.add_argument('--description', help='Database description')
    add_parser.add_argument('--workspace', help='Workspace name')
    add_parser.set_defaults(func=handle_database_add)
    
    # Remove database
    remove_parser = subparsers.add_parser('remove', help='Remove a database')
    remove_parser.add_argument('name', help='Database name to remove')
    remove_parser.set_defaults(func=handle_database_remove)
    
    # Add 'rm' alias for remove
    rm_parser = subparsers.add_parser('rm', help='Remove a database (alias for remove)')
    rm_parser.add_argument('name', help='Database name to remove')
    rm_parser.set_defaults(func=handle_database_remove)
    
    # Add channels to Discord database
    add_channels_parser = subparsers.add_parser('add-channels', help='Add Discord channels to database via browser')
    add_channels_parser.add_argument('database_name', help='Discord database name (e.g., "dgs" or "trass.discord")')
    add_channels_parser.set_defaults(func=handle_database_add_channels)
    
    # Remove channels from Discord database
    remove_channels_parser = subparsers.add_parser('remove-channels', help='Remove Discord channels from database via browser')
    remove_channels_parser.add_argument('database_name', help='Discord database name (e.g., "dgs" or "trass.discord")')
    remove_channels_parser.add_argument('--force', action='store_true', help='Skip confirmation prompt')
    remove_channels_parser.set_defaults(func=handle_database_remove_channels)
    
    # Enhanced remove operations with data purging
    remove_with_data_parser = subparsers.add_parser('purge', help='Remove a database and purge all its locally stored data')
    remove_with_data_parser.add_argument('name', help='Database name to remove and purge')
    remove_with_data_parser.add_argument('--force', action='store_true', help='Skip confirmation prompt')
    remove_with_data_parser.set_defaults(func=handle_database_remove_with_data_purge)
    
    # Interactive database removal using simple selector
    remove_interactive_parser = subparsers.add_parser('remove-interactive', help='Interactively select and remove databases with data purging')
    remove_interactive_parser.add_argument('--workspace', '-ws', help='Workspace to show databases from (defaults to default workspace)')
    remove_interactive_parser.add_argument('--force', action='store_true', help='Skip confirmation prompt')
    remove_interactive_parser.add_argument('--dry-run', action='store_true', help='Show what would be removed without making changes')
    remove_interactive_parser.set_defaults(func=handle_database_remove_interactive)
    
    # Interactive channel removal using simple selector
    remove_channels_interactive_parser = subparsers.add_parser('remove-channels-interactive', help='Interactively select and remove Discord channels with data purging')
    remove_channels_interactive_parser.add_argument('--workspace', '-ws', help='Workspace to show channels from (defaults to default workspace)')
    remove_channels_interactive_parser.add_argument('--force', action='store_true', help='Skip confirmation prompt')
    remove_channels_interactive_parser.add_argument('--dry-run', action='store_true', help='Show what would be removed without making changes')
    remove_channels_interactive_parser.set_defaults(func=handle_channel_remove_interactive)
    
    # Add shorter aliases for the interactive commands
    rmi_parser = subparsers.add_parser('rmi', help='Interactively remove databases (alias for remove-interactive)')
    rmi_parser.add_argument('--workspace', '-ws', help='Workspace to show databases from (defaults to default workspace)')
    rmi_parser.add_argument('--force', action='store_true', help='Skip confirmation prompt')
    rmi_parser.add_argument('--dry-run', action='store_true', help='Show what would be removed without making changes')
    rmi_parser.set_defaults(func=handle_database_remove_interactive)
    
    rmci_parser = subparsers.add_parser('rmci', help='Interactively remove channels (alias for remove-channels-interactive)')
    rmci_parser.add_argument('--workspace', '-ws', help='Workspace to show channels from (defaults to default workspace)')
    rmci_parser.add_argument('--force', action='store_true', help='Skip confirmation prompt')
    rmci_parser.add_argument('--dry-run', action='store_true', help='Show what would be removed without making changes')
    rmci_parser.set_defaults(func=handle_channel_remove_interactive)
    
    # Test database connection
    test_parser = subparsers.add_parser('test', help='Test database connections')
    test_parser.add_argument('names', nargs='*', help='Database names to test (default: all)')
    test_parser.set_defaults(func=handle_database_test)
    
    # Sync databases
    sync_parser = subparsers.add_parser('sync', help='Sync databases')
    sync_parser.add_argument('--source', '-s', action='append', dest='sources', help='Source specifications (e.g., journal:30, trass.stories:7). Can be used multiple times.')
    sync_parser.add_argument('--browse', '-b', nargs='*', help='Browse and select Discord channels to sync. Optionally specify databases (e.g., -b trass.discord trass.yeeps_discord)')
    sync_parser.add_argument('--workspace', '-ws', help='Workspace to sync (expands to all enabled databases in workspace with default days)')
    sync_parser.add_argument('--days', type=int, help='Number of days to sync')
    sync_parser.add_argument('--force', action='store_true', help='Force update all files')
    sync_parser.add_argument('--properties-only', action='store_true', help='Only sync properties without re-downloading page content (much faster)')

    # Add simple date range arguments
    sync_parser.add_argument('--start-date', help='Start date for sync (e.g., 2025-02-01)')
    sync_parser.add_argument('--end-date', help='End date for sync (e.g., 2025-03-31)')
    sync_parser.add_argument('--date-range', help='Date range for sync (e.g., 2025-02-01,2025-03-31)')
    
    sync_parser.set_defaults(func=handle_database_sync)
    
    # Database info
    info_parser = subparsers.add_parser('info', help='Show database information')
    info_parser.add_argument('name', help='Database name')
    info_parser.add_argument('--schema', action='store_true', help='Show database schema')
    info_parser.set_defaults(func=handle_database_info)
    
    # Push database
    push_parser = subparsers.add_parser('push', help='Push local changes to Notion')
    push_parser.add_argument('target', nargs='?', default='all', help='Content type to push (default: all)')
    push_parser.add_argument('--dry-run', action='store_true', help='Dry run mode')
    push_parser.add_argument('--workspace', help='Workspace to push from (defaults to default workspace)')
    push_parser.set_defaults(func=handle_database_push)
    
    # Database status
    status_parser = subparsers.add_parser('status', help='Show what needs to be synced')
    status_parser.add_argument('target', nargs='?', default='all', help='Content type to show status for (default: all)')
    status_parser.set_defaults(func=handle_database_status)
    
    # Add 'st' alias for status
    st_parser = subparsers.add_parser('st', help='Show what needs to be synced (alias for status)')
    st_parser.add_argument('target', nargs='?', default='all', help='Content type to show status for (default: all)')
    st_parser.set_defaults(func=handle_database_status)
    
    # List sources command
    list_sources_parser = subparsers.add_parser('list-sources', help='List all available database sources in JSON format')
    list_sources_parser.set_defaults(func=handle_database_list_sources)
    
    # Add 'sources' alias for list-sources
    sources_parser = subparsers.add_parser('sources', help='List all available database sources in JSON format (alias for list-sources)')
    sources_parser.set_defaults(func=handle_database_list_sources)

    # Validate registry command
    validate_parser = subparsers.add_parser('validate-registry', help='Validate that registry is in sync with configuration')
    validate_parser.add_argument('--auto-fix', action='store_true', help='Automatically fix issues by registering missing files')
    validate_parser.add_argument('--dry-run', action='store_true', help='Show what would be done without making changes')
    validate_parser.set_defaults(func=handle_validate_registry)

    # Register markdown files command
    register_parser = subparsers.add_parser('register-markdown-files', help='Register existing markdown files in the SQLite registry')
    register_parser.add_argument('--workspace', help='Workspace to register files for (optional)')
    register_parser.add_argument('--database', help='Database nickname to register files for (optional)')
    register_parser.add_argument('--dry-run', action='store_true', help='Show what would be registered without making changes')
    register_parser.set_defaults(func=handle_register_markdown_files)
