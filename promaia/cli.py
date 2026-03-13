#!/usr/bin/env python
"""
Command Line Interface for Maia.
"""
import os
import asyncio
import argparse
import glob
import re
from typing import List, Dict, Any, Optional
import traceback
from datetime import datetime, timedelta
import logging
import sys

# Import modules for CMS functionality
from promaia.notion.client import ensure_default_client
from promaia.notion.pages import get_pages_by_date, get_page_title, get_block_content, clear_block_cache
from promaia.notion.journal_router import handle_journal_pull_date_range, handle_journal_pull_with_sub_pages
from promaia.markdown.converter import page_to_markdown
from promaia.storage.files import save_page_to_file, get_existing_page_ids
from promaia.utils.config import update_last_sync_time, get_last_sync_time, get_sync_days_setting, set_sync_days_setting, load_environment, get_config, update_config
from promaia.utils.timezone_utils import now_utc

# Load environment variables from .env file at startup
load_environment()
from promaia.utils.config_loader import get_notion_database_id
from promaia.utils.display import print_text, print_markdown, print_separator

# Import database management commands
from promaia.cli.database_commands import (
    handle_database_list, handle_database_add, handle_database_remove,
    handle_database_test, handle_database_sync, handle_database_info,
    handle_database_push, handle_database_status, handle_database_list_sources,
    handle_register_markdown_files, handle_validate_registry,
    handle_database_add_channels, handle_database_remove_channels,
    handle_database_remove_with_data_purge, handle_database_remove_interactive,
    handle_channel_remove_interactive,
    add_database_commands, add_database_commands_to_existing_parser
)
from promaia.cli.conversion_commands import add_conversion_commands
# from promaia.cli.edit_commands import edit  # Remove this import as we're using argparse handlers

# Import newsletter commands
from promaia.newsletter.commands import newsletter_sync_command, newsletter_test_command

# Import mail commands
from promaia.cli.mail_commands import add_mail_commands

# Import Gmail commands
from promaia.cli.gmail_commands import add_gmail_commands

# Import prompt sync commands
from promaia.cli.prompt_sync_commands import add_prompt_commands

# Import agent commands
from promaia.cli.agent_commands import add_agent_commands
# Note: scheduled_agent_commands lazy-loaded (below) to keep imports clean



# Import workspace commands
from promaia.cli.workspace_commands import (
    add_workspace_commands, add_workspace_commands_to_existing_parser
)

# Import migration commands
from promaia.cli.migration_commands import (
    add_migration_commands, add_migration_commands_to_existing_parser
)

# Load environment variables
load_environment()

# Initialize console for rich output - Replaced with standard print
# console = Console()

# Import query parsing utilities
from promaia.utils.query_parsing import parse_vs_queries_with_params

# ==================== EDIT COMMAND HANDLERS ====================

def handle_edit_list_pages(args):
    """Handle edit list-pages command"""
    import os
    from rich.console import Console
    from rich.table import Table
    from datetime import datetime
    from promaia.storage.json_editor import NotionJSONEditor
    
    console = Console(width=9999, soft_wrap=False)
    
    try:
        editor = NotionJSONEditor()
        content_dir = editor._get_content_type_dir(args.content_type)
        
        if not os.path.exists(content_dir):
            console.print(f"[red]No data found for content type: {args.content_type}[/red]")
            return
        
        table = Table(title=f"Pages in {args.content_type}")
        table.add_column("Title", style="cyan")
        table.add_column("Page ID", style="green")
        table.add_column("Last Modified", style="yellow")
        table.add_column("Sync Status", style="magenta")
        
        for filename in sorted(os.listdir(content_dir)):
            if filename.endswith('.json') and 'backup' not in filename:
                try:
                    import json
                    with open(os.path.join(content_dir, filename), 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    
                    title = data.get('title', 'Unknown')
                    page_id_val = data.get('page_id', 'Unknown')
                    saved_at = data.get('saved_at', 'Unknown')
                    last_synced = data.get('last_synced', 'Never')
                    
                    # Apply filters
                    if args.page_id and args.page_id not in page_id_val:
                        continue
                    if args.title_filter and args.title_filter.lower() not in title.lower():
                        continue
                    
                    # Determine sync status
                    if last_synced == 'Never':
                        sync_status = "[red]Not synced[/red]"
                    else:
                        saved_dt = datetime.fromisoformat(saved_at)
                        synced_dt = datetime.fromisoformat(last_synced)
                        if saved_dt > synced_dt:
                            sync_status = "[yellow]Modified[/yellow]"
                        else:
                            sync_status = "[green]Synced[/green]"
                    
                    table.add_row(title[:50], page_id_val, saved_at[:19], sync_status)
                    
                except Exception as e:
                    console.print(f"[red]Error reading {filename}: {e}[/red]")
        
        console.print(table)
        
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")

def handle_edit_update(args):
    """Handle edit update command"""
    from rich.console import Console
    from promaia.storage.json_editor import NotionJSONEditor
    
    console = Console(width=9999, soft_wrap=False)
    
    try:
        editor = NotionJSONEditor()
        
        # Load the page
        data = editor.load_page(args.content_type, args.page_id)
        console.print(f"[green]Loaded page: {data['title']}[/green]")
        
        # Update title if provided
        if args.title:
            data = editor.update_title(data, args.title)
            console.print(f"[cyan]Updated title to: {args.title}[/cyan]")
        
        # Update properties if provided
        if args.property:
            for prop in args.property:
                if '=' not in prop:
                    console.print(f"[red]Invalid property format: {prop}. Use 'Name=Value'[/red]")
                    continue
                
                prop_name, prop_value = prop.split('=', 1)
                
                # Handle different property types (simplified)
                if prop_name in data['notion_data']['properties']:
                    prop_type = data['notion_data']['properties'][prop_name]['type']
                    
                    if prop_type == 'select':
                        prop_value = {"name": prop_value, "color": "default"}
                    elif prop_type == 'rich_text':
                        prop_value = [{
                            "type": "text",
                            "text": {"content": prop_value},
                            "plain_text": prop_value
                        }]
                else:
                    # Default to rich_text for new properties
                    prop_type = 'rich_text'
                    prop_value = [{
                        "type": "text", 
                        "text": {"content": prop_value},
                        "plain_text": prop_value
                    }]
                
                data = editor.update_property(data, prop_name, prop_value, prop_type)
                console.print(f"[cyan]Updated property {prop_name}: {str(prop_value)[:50]}[/cyan]")
        
        # Add content blocks if provided
        if args.add_paragraph:
            block = editor.create_paragraph_block(args.add_paragraph)
            data = editor.add_content_block(data, block)
            console.print(f"[cyan]Added paragraph: {args.add_paragraph[:50]}[/cyan]")
        
        if args.add_heading:
            block = editor.create_heading_block(args.add_heading, args.heading_level)
            data = editor.add_content_block(data, block)
            console.print(f"[cyan]Added heading {args.heading_level}: {args.add_heading[:50]}[/cyan]")
        
        # Save the changes
        filepath = editor.save_page(data, backup=not args.no_backup)
        console.print(f"[green]Saved changes to: {filepath}[/green]")
        
        # Show changes summary
        changes = editor.get_changes_summary()
        if changes:
            console.print("\n[bold]Changes made:[/bold]")
            for change in changes:
                console.print(f"  • {change['description']}")
        
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")

def handle_edit_show(args):
    """Handle edit show command"""
    from rich.console import Console
    from rich.tree import Tree
    from promaia.storage.json_editor import NotionJSONEditor
    
    console = Console(width=9999, soft_wrap=False)
    
    try:
        editor = NotionJSONEditor()
        data = editor.load_page(args.content_type, args.page_id)
        
        console.print(f"[bold cyan]Page: {data['title']}[/bold cyan]")
        console.print(f"[dim]ID: {data['page_id']}[/dim]")
        console.print(f"[dim]Type: {data['content_type']}[/dim]")
        console.print(f"[dim]Last saved: {data['saved_at']}[/dim]")
        console.print(f"[dim]Last synced: {data.get('last_synced', 'Never')}[/dim]")
        
        # Show properties
        console.print("\n[bold]Properties:[/bold]")
        props = data['notion_data']['properties']
        for name, prop in props.items():
            prop_type = prop.get('type', 'unknown')
            value = prop.get(prop_type, 'N/A')
            
            # Format value based on type
            if prop_type == 'title' and isinstance(value, list) and value:
                display_value = value[0].get('plain_text', 'N/A')
            elif prop_type == 'rich_text' and isinstance(value, list) and value:
                display_value = value[0].get('plain_text', 'N/A')
            elif prop_type == 'select' and isinstance(value, dict):
                display_value = value.get('name', 'N/A')
            elif prop_type == 'relation' and isinstance(value, list):
                display_value = f"{len(value)} related items"
            else:
                display_value = str(value)[:100]
            
            console.print(f"  [cyan]{name}[/cyan] ({prop_type}): {display_value}")
        
        # Show content summary
        content = data['notion_data']['content']
        console.print(f"\n[bold]Content blocks: {len(content)}[/bold]")
        
        if content:
            tree = Tree("Content Structure")
            for i, block in enumerate(content[:10]):  # Show first 10 blocks
                block_type = block.get('type', 'unknown')
                block_content = ""
                
                if block_type == 'paragraph' and 'paragraph' in block:
                    rich_text = block['paragraph'].get('rich_text', [])
                    if rich_text:
                        block_content = rich_text[0].get('plain_text', '')[:50]
                elif block_type.startswith('heading_') and block_type in block:
                    rich_text = block[block_type].get('rich_text', [])
                    if rich_text:
                        block_content = rich_text[0].get('plain_text', '')[:50]
                
                tree.add(f"[{i}] {block_type}: {block_content}")
            
            if len(content) > 10:
                tree.add(f"... and {len(content) - 10} more blocks")
            
            console.print(tree)
        
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")

def handle_edit_sync(args):
    """Handle edit sync command"""
    from rich.console import Console
    from rich.table import Table
    from promaia.storage.notion_sync import NotionSyncer
    from promaia.utils.config import get_config
    
    console = Console(width=9999, soft_wrap=False)
    
    try:
        syncer = NotionSyncer()
        
        if args.dry_run:
            console.print("[yellow]DRY RUN - No changes will be made[/yellow]\n")
            
            if args.content_type:
                plan = syncer.create_sync_plan(args.content_type)
            else:
                plan = syncer.create_sync_plan()
            
            if not plan:
                console.print("[green]No pages need syncing[/green]")
                return
            
            console.print("[bold]Sync Plan:[/bold]")
            for ct, pages in plan.items():
                console.print(f"\n[cyan]{ct}:[/cyan]")
                for page_id in pages:
                    console.print(f"  • {page_id}")
            return
        
        if args.page_id:
            # Sync single page
            if not args.content_type:
                console.print("[red]Content type required when syncing specific page[/red]")
                return
            
            console.print(f"[yellow]Syncing page {args.page_id} in {args.content_type}...[/yellow]")
            result = syncer.sync_page(args.content_type, args.page_id, force=args.force)
            
            if result.success:
                console.print(f"[green]✓ Successfully synced {result.changes_applied} changes[/green]")
            else:
                console.print(f"[red]✗ Sync failed[/red]")
                for error in result.errors:
                    console.print(f"  [red]Error: {error}[/red]")
                for conflict in result.conflicts:
                    console.print(f"  [yellow]Conflict: {conflict}[/yellow]")
        
        elif args.content_type:
            # Sync entire database
            console.print(f"[yellow]Syncing all pages in {args.content_type}...[/yellow]")
            results = syncer.sync_database(args.content_type, force=args.force)
            
            success_count = sum(1 for r in results if r.success)
            total_count = len(results)
            
            console.print(f"\n[bold]Sync Results: {success_count}/{total_count} successful[/bold]")
            
            for result in results:
                if result.success:
                    console.print(f"[green]✓ {result.page_id}: {result.changes_applied} changes[/green]")
                else:
                    console.print(f"[red]✗ {result.page_id}: Failed[/red]")
                    for error in result.errors[:2]:  # Show first 2 errors
                        console.print(f"    [red]{error}[/red]")
        
        else:
            # Sync all databases
            config = get_config()
            all_results = []
            
            for ct in config.keys():
                console.print(f"[yellow]Syncing {ct}...[/yellow]")
                results = syncer.sync_database(ct, force=args.force)
                all_results.extend(results)
            
            success_count = sum(1 for r in all_results if r.success)
            total_count = len(all_results)
            
            console.print(f"\n[bold]Total Sync Results: {success_count}/{total_count} successful[/bold]")
        
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")

async def handle_discord_bot(args):
    """Handle discord-bot command to start the Promaia Discord bot."""
    import asyncio
    from promaia.discord.bot import run_bot

    print(f"🤖 Starting Promaia Discord bot for workspace: {args.workspace}")
    print("Press Ctrl+C to stop the bot")

    try:
        await run_bot(workspace=args.workspace, token=args.token)
    except KeyboardInterrupt:
        print("\n✅ Bot stopped")
    except Exception as e:
        print(f"❌ Error starting bot: {e}")
        import traceback
        traceback.print_exc()

def handle_edit_status(args):
    """Handle edit status command"""
    from rich.console import Console
    from rich.table import Table
    from promaia.storage.notion_sync import NotionSyncer
    from promaia.utils.config import get_config
    
    console = Console(width=9999, soft_wrap=False)
    
    try:
        syncer = NotionSyncer()
        
        if args.content_type:
            content_types = [args.content_type]
        else:
            config = get_config()
            content_types = list(config.keys())
        
        table = Table(title="Sync Status")
        table.add_column("Database", style="cyan")
        table.add_column("Modified Pages", style="yellow")
        table.add_column("Status", style="green")
        
        for ct in content_types:
            modified = syncer.get_modified_pages(ct)
            if modified:
                status_text = f"[yellow]{len(modified)} need sync[/yellow]"
                pages_text = ", ".join(modified[:3])
                if len(modified) > 3:
                    pages_text += f" and {len(modified) - 3} more"
            else:
                status_text = "[green]All synced[/green]"
                pages_text = "None"
            
            table.add_row(ct, pages_text, status_text)
        
        console.print(table)
        
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")


# ---------------------------------------------------------------------------
# Extracted command handlers — now live in their own modules
# ---------------------------------------------------------------------------
from promaia.cli.journal_commands import handle_journal_pull, handle_journal_summarize_file
from promaia.cli.cms_commands import (
    pull_db_pages, handle_cms_pull, handle_cms_push, handle_cms_sync, pull_cms_filtered
)
from promaia.cli.chat_commands import (
    extract_database_names_from_sources, chat_run, chat_run_recents, chat_run_browse,
    chat_run_inline_browse, history_run, write_run_async, write_run, model_run,
    chat_run_workspace_browse, chat_run_multi_workspace_browse
)

logger = logging.getLogger(__name__)

# ==================== MAIN ENTRY POINT ====================

def main():
    """Main function for the Maia CLI."""
    parser = argparse.ArgumentParser(description="Promaia CLI - Your personal AI assistant")
    parser.add_argument('--debug', action='store_true', help='Enable debug logging.')
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Let database_commands module add its own subparsers
    add_database_commands(subparsers)
    
    # Add 'db' alias for database commands
    db_parser = subparsers.add_parser('db', help='Manage databases (alias for database)')
    db_subparsers = db_parser.add_subparsers(dest='database_command', help='Database commands')
    add_database_commands_to_existing_parser(db_parser, db_subparsers)

    # Let workspace_commands module add its own subparsers
    add_workspace_commands(subparsers)
    
    # Add 'ws' alias for workspace commands  
    ws_parser = subparsers.add_parser('ws', help='Manage workspaces (alias for workspace)')
    ws_subparsers = ws_parser.add_subparsers(dest='workspace_command', help='Workspace commands')
    add_workspace_commands_to_existing_parser(ws_parser, ws_subparsers)
    
    # Add migration commands
    add_migration_commands(subparsers)
    
    # Add 'mig' alias for migration commands
    mig_parser = subparsers.add_parser('mig', help='Data migration commands (alias for migration)')
    mig_subparsers = mig_parser.add_subparsers(dest='migration_command', help='Migration commands')
    add_migration_commands_to_existing_parser(mig_parser, mig_subparsers)
    
    # Add hybrid architecture commands
    from promaia.cli.hybrid_commands import add_hybrid_commands, add_hybrid_commands_to_existing_parser
    add_hybrid_commands(subparsers)
    
    # Add 'hyb' alias for hybrid commands
    hyb_parser = subparsers.add_parser('hyb', help='Hybrid architecture commands (alias for hybrid)')
    hyb_subparsers = hyb_parser.add_subparsers(dest='hybrid_command', help='Hybrid commands')
    add_hybrid_commands_to_existing_parser(hyb_parser, hyb_subparsers)
    
    # Add mail commands
    add_mail_commands(subparsers)
    
    # Add Gmail commands
    add_gmail_commands(subparsers)

    # Add prompt sync commands
    add_prompt_commands(subparsers)

    # Add OCR commands
    from promaia.cli.ocr_commands import register_ocr_commands
    register_ocr_commands(subparsers)

    # Add agent commands (both external and scheduled)
    agent_subparsers = add_agent_commands(subparsers, include_scheduled=True)
    if agent_subparsers:
        # Lazy import to keep module loading cleaner
        from promaia.cli.scheduled_agent_commands import add_scheduled_agent_commands
        add_scheduled_agent_commands(agent_subparsers)

    # Add top-level sync command (alias for database sync)
    sync_parser = subparsers.add_parser('sync', help='Sync databases (alias for database sync)')
    sync_parser.add_argument('--source', '-s', dest='sources', action='append',
                            help='Source specifications (e.g., journal:30, trass.stories:7). Can be used multiple times.')
    sync_parser.add_argument('--browse', '-b', action='append', nargs='*', help='Browse and select Discord channels to sync. Optionally specify databases (e.g., -b trass.discord trass.yeeps_discord)')
    sync_parser.add_argument('--workspace', '-ws', help='Workspace to sync (expands to all enabled databases in workspace with default days)')
    sync_parser.add_argument('--days', type=int, help='Number of days to sync')
    sync_parser.add_argument('--force', action='store_true', help='Force update all files')
    sync_parser.set_defaults(func=handle_database_sync)



    # Chat command
    chat_parser = subparsers.add_parser("chat", help="Interactive chat with multi-source support")
    chat_parser.add_argument(
        "--source", "-s",
        action="append", 
        dest="sources",
        help="Load data from specific database with day filter: 'database_name:days' (e.g., 'journal:7', 'awakenings:all'). Repeat for multiple sources."
    )
    chat_parser.add_argument(
        "--filter", "-f",
        action="append",
        dest="filters",
        help="Add property filters in format 'property_name=value' or '\"Property Name\"=value'. Use quotes for properties with spaces. Can be used multiple times. Examples: 'status=published', '\"Reference\"=true', '\"Blog Status\"=live and created_time>2025-03-01'"
    )
    chat_parser.add_argument(
        "--workspace", "-ws",
        help="Specify which workspace to use for chat (defaults to default workspace)"
    )
    chat_parser.add_argument(
        "--recent", "-r",
        action="store_true",
        help="Show recent queries for selection and re-execution"
    )
    chat_parser.add_argument(
        "--browse", "-b",
        action="append",
        nargs="*",
        help="Launch interactive browser to select sources. For workspaces: '-b workspace_name' (e.g., -b trass). For Discord channels: '-b discord' or specific databases (e.g., -b trass.yp). Without arguments, shows all available sources."
    )
    chat_parser.add_argument(
        "--non-interactive",
        action="store_true",
        help="Run in non-interactive mode for testing"
    )
    chat_parser.add_argument(
        "--sql-query", "-sql",
        action="append",
        nargs="+",
        dest="sql_query",
        help="Use SQL-based natural language queries to search content. Can be used multiple times for separate queries. Example: maia chat -sql 'emails about avask' -sql 'stories about canada'"
    )
    # Deprecated: Keep -nl as an alias for backward compatibility
    chat_parser.add_argument(
        "--natural-language", "-nl",
        action="append",
        nargs="+",
        dest="sql_query",
        help=argparse.SUPPRESS  # Hide from help, deprecated in favor of -sql
    )
    # NOTE: This -sql argument definition MUST stay in sync with:
    # 1. Edit mode parsing in promaia/chat/interface.py (lines ~2148-2163)
    # 2. Top-level processing above (lines ~1507-1520)
    # These are two sides of one feature and must handle multiple -sql arguments identically.
    chat_parser.add_argument(
        "--vector-search", "-vs",
        action="append",
        nargs="+",
        help="Use semantic vector search to find similar content. Can be used multiple times for separate queries. IMPORTANT: Quote queries with special characters like parentheses. Examples: maia chat -vs \"story with (Shared) in title\" -tk 1 or maia chat -vs 'international launch stories' -vs 'product planning discussions'"
    )
    chat_parser.add_argument(
        "--top-k", "-tk",
        type=int,
        default=20,
        help="Maximum number of results to return from vector search (default: 20)"
    )
    chat_parser.add_argument(
        "--threshold", "-th",
        type=float,
        default=0.2,
        help="Minimum similarity threshold for vector search results, 0-1 scale (default: 0.2)"
    )
    chat_parser.add_argument(
        "--mcp", "-mcp",
        action="append",
        dest="mcp_servers",
        help="Include MCP (Model Context Protocol) servers in chat context. Specify server names from mcp_servers.json. Can be used multiple times. Example: maia chat -mcp filesystem -mcp git"
    )
    chat_parser.add_argument(
        "-dc", "--draft-context",
        action="store_true",
        dest="draft_context",
        help="Enable draft context in draft chat (includes email thread and related context)"
    )
    chat_parser.set_defaults(func=chat_run)
    
    # Add 'r' alias for chat with recents
    r_parser = subparsers.add_parser("r", help="Recent chat queries (alias for 'chat --recent')")
    r_parser.add_argument(
        "--workspace", "-ws",
        help="Specify which workspace to use for chat (defaults to default workspace)"
    )
    r_parser.set_defaults(func=lambda args: chat_run_recents(args))

    # History command
    history_parser = subparsers.add_parser("history", help="Browse and load saved chat conversations")
    history_parser.add_argument("--clean", action="store_true", help="Clean up duplicate threads")
    history_parser.set_defaults(func=history_run)
    
    # Add 'h' alias for history
    h_parser = subparsers.add_parser("h", help="Browse and load saved chat conversations (alias for 'history')")
    h_parser.add_argument("--clean", action="store_true", help="Clean up duplicate threads")
    h_parser.set_defaults(func=history_run)

    # Write command
    write_parser = subparsers.add_parser("write", help="Generate blog content using AI")
    write_parser.add_argument("--days", type=int, help="Number of past days of journal entries to use as context (0 to skip journal).")
    write_parser.add_argument("--prompt", type=str, help="Custom prompt/instructions for the blog post generation.")
    write_parser.add_argument("--no-push", action="store_true", help="Save generated post to local 'drafts/' dir instead of pushing to Notion CMS.")
    write_parser.add_argument("--max-entries", type=int, help="Maximum number of journal entries to include in the prompt context.")
    write_parser.add_argument("--force-openai", action="store_true", help="Force using OpenAI for generation, overriding default model.")
    write_parser.set_defaults(func=write_run)

    # Model command
    model_parser = subparsers.add_parser("model", help="Set the default AI model for chat and writing tasks")
    model_parser.set_defaults(func=model_run)

    # CMS command (legacy support for blog/newsletter workflow)
    cms_parser = subparsers.add_parser("cms", help="Content management system operations")
    cms_subparsers = cms_parser.add_subparsers(dest="cms_action", required=True, help="CMS action to perform")
    
    cms_pull_parser = cms_subparsers.add_parser("pull", help="Pull CMS entries for KOii chat context")
    cms_pull_parser.add_argument("--days", type=lambda x: x.lower() if x.lower() == 'all' else int(x), default=30, help="Number of days to look back (default: 30)")
    cms_pull_parser.add_argument("--force", action="store_true", default=False, help="Force pull ignoring last sync time.")
    cms_pull_parser.set_defaults(func=handle_cms_pull)
    
    cms_sync_parser = cms_subparsers.add_parser("sync", help="Sync CMS content to Webflow")
    cms_sync_parser.add_argument("--collection", help="Webflow collection ID (or use WEBFLOW_COLLECTION_ID env var)")
    cms_sync_parser.add_argument("--blog-status-property", default="Blog Status", help="Notion property name for blog status (default: 'Blog Status')")
    cms_sync_parser.add_argument("--force-update", action="store_true", help="Force update even if already synced")
    cms_sync_parser.set_defaults(func=handle_cms_sync)
    
    # Newsletter command
    newsletter_parser = subparsers.add_parser("newsletter", help="Newsletter operations")
    newsletter_subparsers = newsletter_parser.add_subparsers(dest="newsletter_action", required=True, help="Newsletter action")
    
    newsletter_send_parser = newsletter_subparsers.add_parser("send", help="Send newsletters via Resend for eligible CMS pages")
    newsletter_send_parser.add_argument("--force", action="store_true", help="Skip confirmation prompt (use with caution)")
    newsletter_send_parser.set_defaults(func=newsletter_sync_command)
    
    newsletter_test_parser = newsletter_subparsers.add_parser("test", help="Test newsletter generation without sending")
    newsletter_test_parser.add_argument("--email", action="append", help="Email address to send test to (can be used multiple times)")
    newsletter_test_parser.set_defaults(func=newsletter_test_command)

    # Add 'news' alias for newsletter
    news_parser = subparsers.add_parser("news", help="Newsletter operations (alias for newsletter)")
    news_subparsers = news_parser.add_subparsers(dest="newsletter_action", required=True, help="Newsletter action")

    news_send_parser = news_subparsers.add_parser("send", help="Send newsletters via Resend for eligible CMS pages")
    news_send_parser.add_argument("--force", action="store_true", help="Skip confirmation prompt (use with caution)")
    news_send_parser.set_defaults(func=newsletter_sync_command)

    news_test_parser = news_subparsers.add_parser("test", help="Test newsletter generation without sending")
    news_test_parser.add_argument("--email", action="append", help="Email address to send test to (can be used multiple times)")
    news_test_parser.set_defaults(func=newsletter_test_command)
    


    # Add conversion commands
    add_conversion_commands(subparsers)

    # Add Discord commands (optional)
    try:
        from promaia.cli.discord_commands import setup_discord_commands
        setup_discord_commands(subparsers)
    except ImportError:
        pass  # Discord commands not available

    # Add edit command group
    edit_parser = subparsers.add_parser("edit", help="Commands for editing local JSON files and syncing with Notion")
    edit_subparsers = edit_parser.add_subparsers(dest="edit_action", required=True, help="Edit action to perform")
    
    # Edit list-pages command
    edit_list_parser = edit_subparsers.add_parser("list-pages", help="List pages available for editing")
    edit_list_parser.add_argument("content_type", help="Content type to list pages for")
    edit_list_parser.add_argument("--page-id", help="Specific page ID to filter")
    edit_list_parser.add_argument("--title-filter", help="Filter pages by title")
    edit_list_parser.set_defaults(func=handle_edit_list_pages)
    
    # Edit update command
    edit_update_parser = edit_subparsers.add_parser("update", help="Update a page's properties and content")
    edit_update_parser.add_argument("content_type", help="Content type of the page")
    edit_update_parser.add_argument("page_id", help="Page ID to update")
    edit_update_parser.add_argument("--title", help="New title for the page")
    edit_update_parser.add_argument("--property", action="append", help="Update property: --property 'Name=Value'")
    edit_update_parser.add_argument("--add-paragraph", help="Add a paragraph with this text")
    edit_update_parser.add_argument("--add-heading", help="Add a heading with this text")
    edit_update_parser.add_argument("--heading-level", type=int, default=1, help="Heading level (1-3)")
    edit_update_parser.add_argument("--no-backup", action="store_true", help="Don't create backup before editing")
    edit_update_parser.set_defaults(func=handle_edit_update)
    
    # Edit show command
    edit_show_parser = edit_subparsers.add_parser("show", help="Show detailed information about a page")
    edit_show_parser.add_argument("content_type", help="Content type of the page")
    edit_show_parser.add_argument("page_id", help="Page ID to show")
    edit_show_parser.set_defaults(func=handle_edit_show)
    
    # Edit sync command
    edit_sync_parser = edit_subparsers.add_parser("sync", help="Sync local changes back to Notion")
    edit_sync_parser.add_argument("content_type", nargs="?", help="Content type to sync (optional)")
    edit_sync_parser.add_argument("--page-id", help="Sync specific page only")
    edit_sync_parser.add_argument("--force", action="store_true", help="Force sync even if conflicts detected")
    edit_sync_parser.add_argument("--dry-run", action="store_true", help="Show what would be synced without actually syncing")
    edit_sync_parser.set_defaults(func=handle_edit_sync)
    
    # Edit status command
    edit_status_parser = edit_subparsers.add_parser("status", help="Show sync status of local pages")
    edit_status_parser.add_argument("content_type", nargs="?", help="Content type to check status for (optional)")
    edit_status_parser.set_defaults(func=handle_edit_status)

    # Status command
    status_parser = subparsers.add_parser("status", help="Check system health and core module connections")
    from promaia.cli.status_commands import handle_status
    status_parser.set_defaults(func=handle_status)

    # Discord bot command
    discord_parser = subparsers.add_parser("discord-bot", help="Start Promaia Discord bot")
    discord_parser.add_argument("--workspace", "-w", default="koii", help="Workspace to use for bot configuration")
    discord_parser.add_argument("--token", help="Discord bot token (optional, will use credentials file if not provided)")
    discord_parser.set_defaults(func=handle_discord_bot)

    # Unified dev runner — one command starts everything
    subparsers.add_parser("dev", help="Start Promaia (scheduler + Telegram bot + web dashboard)")

    args = parser.parse_args()

    # Configure logging
    # Check both CLI flag and environment variable for debug mode
    debug_mode = args.debug or os.getenv("MAIA_DEBUG", "0") == "1"
    log_level = logging.DEBUG if debug_mode else logging.WARNING  # Use WARNING to suppress INFO messages
    
    # In non-interactive mode (like in the app), send logs to a file
    # and only critical errors to stderr.
    if not sys.stdout.isatty():
        logging.basicConfig(level=log_level,
                            format='%(asctime)s - %(levelname)s - %(name)s - %(message)s',
                            filename='maia_desktop.log',
                            filemode='w')
        # Also log critical errors to stderr for the app to see
        stderr_handler = logging.StreamHandler(sys.stderr)
        stderr_handler.setLevel(logging.ERROR)
        logging.getLogger().addHandler(stderr_handler)
    else:
        # Standard terminal logging
        logging.basicConfig(level=log_level, format='%(asctime)s - %(levelname)s - %(name)s - %(message)s')
    
    # Suppress noisy HTTP request logging unless in debug mode
    if not debug_mode:
        logging.getLogger("httpx").setLevel(logging.WARNING)
        logging.getLogger("notion_client").setLevel(logging.WARNING)
        logging.getLogger("urllib3.connectionpool").setLevel(logging.WARNING)
    
    logger = logging.getLogger(__name__)

    # Ensure MAIA_DEBUG environment variable matches the determined debug mode
    if debug_mode:
        os.environ["MAIA_DEBUG"] = "1"
        logger.info("Maia Debug Mode Enabled")
    else:
        os.environ["MAIA_DEBUG"] = "0"

    # Legacy registry validation disabled - hybrid database system handles this now
    # The hybrid storage architecture provides all necessary validation and functionality

    if args.command is None:
        parser.print_help()
        return

    # Unified dev runner
    if args.command == "dev":
        from promaia.runner import main as run_dev
        run_dev()
        return

    # Handle commands
    if args.command in ["chat", "model", "write", "r", "history", "h", "status"]:
        args.func(args)
    elif args.command == "cms":
        if hasattr(args, 'func'):
            asyncio.run(args.func(args))
        else:
            cms_parser.print_help()
    elif args.command in ["newsletter", "news"]:
        if hasattr(args, 'func'):
            asyncio.run(args.func(args))
        else:
            newsletter_parser.print_help()
    elif args.command in ["database", "db"]:
        if hasattr(args, 'database_command') and args.database_command:
            if args.database_command in ["list", "ls"]:
                asyncio.run(handle_database_list(args))
            elif args.database_command == "add":
                asyncio.run(handle_database_add(args))
            elif args.database_command in ["remove", "rm"]:
                asyncio.run(handle_database_remove(args))
            elif args.database_command == "test":
                asyncio.run(handle_database_test(args))
            elif args.database_command == "sync":
                asyncio.run(handle_database_sync(args))
            elif args.database_command == "info":
                asyncio.run(handle_database_info(args))
            elif args.database_command == "push":
                asyncio.run(handle_database_push(args))
            elif args.database_command in ["status", "st"]:
                asyncio.run(handle_database_status(args))
            elif args.database_command in ["list-sources", "sources"]:
                asyncio.run(handle_database_list_sources(args))
            elif args.database_command == "register-markdown-files":
                asyncio.run(handle_register_markdown_files(args))
            elif args.database_command == "validate-registry":
                asyncio.run(handle_validate_registry(args))
            elif args.database_command == "add-channels":
                asyncio.run(handle_database_add_channels(args))
            elif args.database_command == "remove-channels":
                asyncio.run(handle_database_remove_channels(args))
            elif args.database_command == "purge":
                asyncio.run(handle_database_remove_with_data_purge(args))
            elif args.database_command in ["remove-interactive", "rmi"]:
                asyncio.run(handle_database_remove_interactive(args))
            elif args.database_command in ["remove-channels-interactive", "rmci"]:
                asyncio.run(handle_channel_remove_interactive(args))
            else:
                print_text(f"Unknown database command: {args.database_command}", style="red")
        else:
            print_text("Database command requires a subcommand. Use 'maia database --help' for options.", style="red")
    elif args.command in ["workspace", "ws"]:
        # Handle workspace commands (NEW) - use func attribute for dynamic routing
        if hasattr(args, 'func'):
            asyncio.run(args.func(args))
        else:
            print_text("Workspace command requires a subcommand. Use 'maia workspace --help' for options.", style="red")
    elif args.command in ["migration", "mig"]:
        # Handle migration commands
        if hasattr(args, 'migration_command') and args.migration_command:
            if hasattr(args, 'func'):
                args.func(args)
            else:
                print_text(f"No function assigned to migration command: {args.migration_command}", style="red")
        else:
            print_text("Migration command requires a subcommand. Use 'maia migration --help' for options.", style="red")
    elif args.command in ["hybrid", "hyb"]:
        # Handle hybrid architecture commands
        if hasattr(args, 'hybrid_command') and args.hybrid_command:
            if hasattr(args, 'func'):
                args.func(args)
            else:
                print_text(f"No function assigned to hybrid command: {args.hybrid_command}", style="red")
        else:
            print_text("Hybrid command requires a subcommand. Use 'maia hybrid --help' for options.", style="red")
    elif args.command == "sync":
        # Handle top-level sync command (alias for database sync)
        asyncio.run(handle_database_sync(args))
    elif args.command in ["convert", "list-formats", "cleanup"]:
        # Handle conversion commands
        if hasattr(args, 'func'):
            asyncio.run(args.func(args))
        else:
            print_text(f"No function assigned to command: {args.command}", style="red")
    elif args.command == "edit":
        # Handle edit command
        if hasattr(args, 'func'):
            args.func(args)
        else:
            edit_parser.print_help()
    elif args.command == "mail":
        # Handle mail commands
        if hasattr(args, 'func'):
            asyncio.run(args.func(args))
        else:
            print_text("Mail command error: no function assigned", style="red")
    elif args.command == "gmail":
        # Handle Gmail commands
        if hasattr(args, 'gmail_command') and args.gmail_command:
            if hasattr(args, 'func'):
                asyncio.run(args.func(args))
            else:
                print_text(f"No function assigned to gmail command: {args.gmail_command}", style="red")
        else:
            print_text("Gmail command requires a subcommand. Use 'maia gmail --help' for options.", style="red")
    elif args.command == "prompt":
        # Handle prompt commands
        if hasattr(args, 'prompt_action') and args.prompt_action:
            if hasattr(args, 'func'):
                args.func(args)
            else:
                print_text(f"No function assigned to prompt command: {args.prompt_action}", style="red")
        else:
            print_text("Prompt command requires a subcommand. Use 'maia prompt --help' for options.", style="red")
    elif args.command == "discord":
        # Handle Discord commands
        if hasattr(args, 'discord_command') and args.discord_command:
            if hasattr(args, 'func'):
                asyncio.run(args.func(args))
            else:
                print_text(f"No function assigned to discord command: {args.discord_command}", style="red")
        else:
            print_text("Discord command requires a subcommand. Use 'maia discord --help' for options.", style="red")
    elif args.command == "team":
        # Handle team commands
        if hasattr(args, 'team_command') and args.team_command:
            if hasattr(args, 'func'):
                asyncio.run(args.func(args))
            else:
                print_text(f"No function assigned to team command: {args.team_command}", style="red")
        else:
            print_text("Team command requires a subcommand. Use 'maia team --help' for options.", style="red")
    elif args.command == "ocr":
        # Handle OCR commands
        if hasattr(args, 'ocr_command') and args.ocr_command:
            if hasattr(args, 'func'):
                asyncio.run(args.func(args))
            else:
                print_text(f"No function assigned to OCR command: {args.ocr_command}", style="red")
        else:
            print_text("OCR command requires a subcommand. Use 'maia ocr --help' for options.", style="red")
    elif args.command == "agent":
        # Handle agent commands
        if hasattr(args, 'agent_command') and args.agent_command:
            if hasattr(args, 'func'):
                asyncio.run(args.func(args))
            else:
                print_text(f"No function assigned to agent command: {args.agent_command}", style="red")
        else:
            print_text("Agent command requires a subcommand. Use 'maia agent --help' for options.", style="red")
    elif args.command == "discord-bot":
        # Handle Discord bot command
        if hasattr(args, 'func'):
            asyncio.run(args.func(args))
        else:
            print_text("Discord bot command not properly configured", style="red")
    else:
        parser.print_help()

if __name__ == "__main__":
    main() 
