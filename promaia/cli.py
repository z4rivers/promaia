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
from promaia.markdown.converter import page_to_markdown
from promaia.storage.files import save_page_to_file, get_existing_page_ids
from promaia.utils.config import update_last_sync_time, get_last_sync_time, get_sync_days_setting, set_sync_days_setting, load_environment, get_config, update_config
from promaia.utils.config_loader import get_notion_database_id

# Import database management commands
from promaia.cli.database_commands import (
    handle_database_list, handle_database_add, handle_database_remove,
    handle_database_test, handle_database_sync, handle_database_info,
    handle_database_push, handle_database_status, handle_database_list_sources,
    handle_register_markdown_files, handle_validate_registry,
    add_database_commands, add_database_commands_to_existing_parser
)
from promaia.cli.conversion_commands import add_conversion_commands
# from promaia.cli.edit_commands import edit  # Remove this import as we're using argparse handlers

# Import newsletter commands
from promaia.newsletter.commands import newsletter_sync_command

# Import workspace commands
from promaia.cli.workspace_commands import (
    add_workspace_commands, add_workspace_commands_to_existing_parser
)

# Import migration commands
from promaia.cli.migration_commands import (
    add_migration_commands, add_migration_commands_to_existing_parser
)

# Import Gmail commands (optional)
try:
    from promaia.cli.gmail_commands import add_gmail_commands
    gmail_commands_available = True
except ImportError:
    gmail_commands_available = False

# Load environment variables
load_environment()

# Initialize console for rich output - Replaced with standard print
# console = Console()

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

# ==================== JOURNAL COMMAND HANDLERS ====================

logger = logging.getLogger(__name__) # Module-level logger

async def handle_journal_pull(args):
    """Handles 'maia journal pull' command."""
    days_arg = args.days
    force_pull_value = args.force # Get the force flag
    summarize_journal = args.summarize # Get summarize flag
    start_date = getattr(args, 'start_date', None)
    end_date = getattr(args, 'end_date', None)
    chunk_days = getattr(args, 'chunk_days', 3)
    no_chunking = getattr(args, 'no_chunking', False)
    
    # Sub-page functionality
    include_sub_pages = getattr(args, 'include_sub_pages', False)
    disable_sub_pages = getattr(args, 'disable_sub_pages', False)
    max_sub_page_depth = getattr(args, 'max_sub_page_depth', 3)
    
    # Determine final sub-page setting
    if disable_sub_pages:
        use_sub_pages = False
        logger.info("Sub-page syncing explicitly disabled via --disable-sub-pages")
    elif include_sub_pages:
        use_sub_pages = True
        logger.info(f"Sub-page syncing enabled via --include-sub-pages (max depth: {max_sub_page_depth})")
    else:
        use_sub_pages = False  # Default to disabled unless explicitly enabled
    
    if force_pull_value:
        logger.info(f"--force flag detected. Journal entries will be re-fetched from Notion ignoring last sync time optimizations and modification times.")

    logger.info("Starting journal pull from Notion")

    try:
        database_id = get_notion_database_id("journal")
    except (FileNotFoundError, ValueError) as e:
        logger.error(f"Error loading Notion database ID for journal: {e}")
        logger.error("Please ensure 'NOTION_JOURNAL_DATABASE_ID' environment variable is set.")
        return

    logger.info(f"Using database ID: {database_id}")

    # Check if date range mode is being used
    if start_date and end_date:
        # Date range mode - for now, date range mode doesn't support sub-pages
        if use_sub_pages:
            logger.warning("Sub-page syncing is not yet supported in date range mode. Using standard sync.")
            use_sub_pages = False
            
        logger.info(f"Date range mode: {start_date} to {end_date} (chunking: {not no_chunking}, chunk_days: {chunk_days})")
        
        try:
            # Validate date formats
            from datetime import datetime
            datetime.strptime(start_date, "%Y-%m-%d")
            datetime.strptime(end_date, "%Y-%m-%d")
        except ValueError as e:
            logger.error(f"Invalid date format. Use YYYY-MM-DD. Error: {e}")
            return
        
        try:
            (journal_files, summary_files, 
             saved_originals_count, saved_summaries_count, 
             skipped_originals_count) = await handle_journal_pull_date_range(
                database_id=database_id,
                start_date=start_date,
                end_date=end_date,
                use_chunking=not no_chunking,
                chunk_days=chunk_days,
                force_pull=force_pull_value,
                summarize_flag=summarize_journal
            )
            
            # Log results for date range mode
            if saved_originals_count > 0:
                logger.info(f"Successfully saved {saved_originals_count} new/updated original journal entries:")
                for filepath in journal_files:
                    logger.info(f"  - {filepath}")
            
            if skipped_originals_count > 0:
                logger.info(f"Skipped {skipped_originals_count} original journal entries (already up-to-date).")
            
            if not saved_originals_count and not skipped_originals_count:
                 logger.info("No original journal entries found or processed in the specified date range.")

            if summarize_journal:
                if saved_summaries_count > 0:
                    logger.info(f"Successfully generated {saved_summaries_count} summaries:")
                    for filepath in summary_files:
                        logger.info(f"  - {filepath}")
                elif journal_files:
                    logger.info("No entries were newly summarized (or summaries failed to generate).")
            
            logger.info("Date range journal pull completed successfully!")
            return
            
        except Exception as e:
            logger.error(f"Error processing journal entries in date range: {str(e)}")
            if os.getenv("MAIA_DEBUG") == "1":
                traceback.print_exc()
            return
    elif start_date or end_date:
        logger.error("Both --start-date and --end-date must be provided for date range mode.")
        return

    # Continue with original logic for non-date-range mode
    days_to_process = None
    fetch_all_pages = False
    specific_date = None # Ensure specific_date is initialized

    # Simplified days_arg parsing logic, assuming journal_router or pages.py handles detailed interpretation
    if days_arg is not None:
        if isinstance(days_arg, str) and days_arg.lower() == 'all':
            logger.info("Processing ALL journal entries from Notion.")
            fetch_all_pages = True
        elif isinstance(days_arg, str):
            try: # Check if it's a date
                datetime.strptime(days_arg, "%Y-%m-%d")
                specific_date = days_arg
                days_to_process = None # Explicitly None if specific_date is used
                logger.info(f"Processing journal entries for specific date: {specific_date}")
            except ValueError:
                try: # Try as int
                    days_to_process = int(days_arg)
                    if days_to_process < 0:
                        logger.warning(f"Invalid value for --days ('{days_arg}'). Using default.")
                        days_to_process = get_sync_days_setting()
                    else:
                        logger.info(f"Processing journal entries from the last {days_to_process} days.")
                except ValueError:
                    logger.warning(f"Invalid format for --days: '{days_arg}'. Using default.")
                    days_to_process = get_sync_days_setting()
        elif isinstance(days_arg, int):
            if days_arg < 0:
                logger.warning(f"Invalid value for --days ('{days_arg}'). Using default.")
                days_to_process = get_sync_days_setting()
            else:
                days_to_process = days_arg
                logger.info(f"Processing journal entries from the last {days_to_process} days.")    
        else:
            logger.warning(f"Unhandled --days format: '{days_arg}'. Using default.")
            days_to_process = get_sync_days_setting()
    else:
        days_to_process = get_sync_days_setting()
        logger.info(f"No --days specified, using default sync days setting for journal: {days_to_process} days.")

    if summarize_journal:
        logger.info("--summarize flag detected. Summaries will be generated for journal entries.")

    try:
        # MODIFIED: Capture new return values from handle_journal_pull
        if use_sub_pages:
            # Use enhanced journal pull with sub-page support
            (journal_files, summary_files, 
             saved_originals_count, saved_summaries_count, 
             skipped_originals_count) = await handle_journal_pull_with_sub_pages(
                database_id=database_id,
                days=days_to_process,
                specific_date=specific_date, 
                fetch_all=fetch_all_pages,
                force_pull=force_pull_value,
                summarize_flag=summarize_journal,
                include_sub_pages=use_sub_pages,
                max_sub_page_depth=max_sub_page_depth
            )
        else:
            # Use standard journal pull
            (journal_files, summary_files, 
             saved_originals_count, saved_summaries_count, 
             skipped_originals_count) = await _perform_journal_pull(
                database_id=database_id,
                days=days_to_process,
                specific_date=specific_date, 
                fetch_all=fetch_all_pages,
                force_pull=force_pull_value,
                summarize_flag=summarize_journal 
            )
        
        if saved_originals_count > 0:
            logger.info(f"Successfully saved {saved_originals_count} new/updated original journal entries:")
            for filepath in journal_files: # journal_files now only contains newly saved/updated ones
                logger.info(f"  - {filepath}")
        
        if skipped_originals_count > 0:
            logger.info(f"Skipped {skipped_originals_count} original journal entries (already up-to-date).")
        
        if not saved_originals_count and not skipped_originals_count:
             logger.info("No original journal entries found or processed based on criteria.")

        if summarize_journal:
            if saved_summaries_count > 0:
                logger.info(f"Successfully generated {saved_summaries_count} summaries:")
                for filepath in summary_files: # summary_files only contains newly generated ones
                    logger.info(f"  - {filepath}")
            elif journal_files: # Only print if originals were processed but no summaries made
                logger.info("No entries were newly summarized (or summaries failed to generate).")
        
        # Only update last_sync_time if it was not a forced pull (and not fetching all, which implies force)
        if not force_pull_value and not fetch_all_pages and not specific_date:
            update_last_sync_time() # Consider if this should be journal-specific
            logger.info("Last sync time updated.")
        elif force_pull_value:
            logger.info("Last sync time NOT updated due to --force flag.")
        elif fetch_all_pages:
             logger.info("Last sync time NOT updated because all entries were fetched.")
        elif specific_date:
             logger.info("Last sync time NOT updated because a specific date was processed.")

        logger.info("Journal pull completed successfully!")
        
    except Exception as e:
        logger.error(f"Error processing journal entries: {str(e)}")
        if os.getenv("MAIA_DEBUG") == "1": # Check environment variable
            traceback.print_exc()

async def handle_journal_summarize_file(args):
    """Handles 'maia journal summarize-file' command to summarize a specific journal file."""
    from promaia.summarize.interface import summarize_journal_entry, save_summary_entry
    
    file_path = args.file_path
    force = args.force
    
    if not os.path.exists(file_path):
        logger.error(f"File does not exist: {file_path}")
        return
    
    logger.info(f"Reading journal entry from: {file_path}")
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        file_name = os.path.basename(file_path)
        logger.info(f"Summarizing entry: {file_name}")
        
        # Get the date from the filename
        date_match = re.search(r'(\d{4}-\d{2}-\d{2})', file_name)
        if not date_match:
            logger.warning(f"Could not extract date from filename: {file_name}. Using filename as title.")
            title = file_name
        else:
            title = date_match.group(1)
            
        # Generate summary
        summarized_content = await summarize_journal_entry(content, title)
        
        # Save summary
        summary_path = save_summary_entry(summarized_content, title)
        logger.info(f"Summary saved to: {summary_path}")
        
        # Show the first 200 characters of the summary
        summary_preview = summarized_content[:200] + "..." if len(summarized_content) > 200 else summarized_content
        logger.info(f"Summary Preview:\n{summary_preview}")
        
    except Exception as e:
        logger.error(f"Failed to summarize file: {e}")
        if os.getenv("MAIA_DEBUG") == "1":
            traceback.print_exc()

# ==================== CMS COMMAND HANDLERS ====================

async def pull_db_pages(database_id: str, output_dir: str, days: Optional[int] = None, content_type: str = "pages", fetch_all: bool = False, force_pull: bool = False):
    os.makedirs(output_dir, exist_ok=True)
    existing_page_ids = get_existing_page_ids(output_dir)
    logger.info(f"Found {len(existing_page_ids)} existing local '{content_type}' entries in {output_dir}.")
    
    last_sync = None
    if not fetch_all and not force_pull:
        last_sync = get_last_sync_time(content_type)
        logger.info(f"Last sync time for '{content_type}': {last_sync if last_sync else 'Never'}")
    elif force_pull:
        logger.info(f"Force pull enabled, ignoring last sync time for '{content_type}'.")

    logger.info(f"Querying Notion for '{content_type}' entries...")
    try:
        pages = await get_pages_by_date(database_id, days=days, fetch_all=fetch_all, last_sync_time_override=last_sync, force_pull=force_pull, content_type=content_type)
        logger.info(f"Successfully retrieved {len(pages)} pages from Notion for '{content_type}'.")
    except Exception as e:
        logger.error(f"Error retrieving pages from Notion for '{content_type}': {str(e)}")
        return

    pages_to_sync_ids = []
    skipped_count = 0

    if fetch_all or force_pull:
        pages_to_sync_ids = [page["id"] for page in pages]
        logger.info(f"Marked all {len(pages_to_sync_ids)} retrieved '{content_type}' pages for sync (fetch_all={fetch_all}, force_pull={force_pull}).")
    else:
        for page in pages:
            page_id = page["id"]
            last_edited_time_str = page.get("last_edited_time")
            last_edited_time_dt = None
            if last_edited_time_str:
                try:
                    last_edited_time_dt = datetime.fromisoformat(last_edited_time_str.replace("Z", "+00:00"))
                except ValueError:
                    logger.warning(f"Could not parse last_edited_time '{last_edited_time_str}' for page {page_id}")
            
            if page_id not in existing_page_ids or not last_sync or (last_edited_time_dt and last_edited_time_dt > last_sync):
                pages_to_sync_ids.append(page_id)
            else:
                skipped_count +=1
        logger.info(f"Found {len(pages_to_sync_ids)} '{content_type}' entries to pull (skipped {skipped_count} unmodified).")

    if not pages_to_sync_ids:
        logger.info(f"No '{content_type}' entries to pull based on the criteria.")
    else:
        logger.info(f"Pulling {len(pages_to_sync_ids)} '{content_type}' entries...")
        for i, page_id in enumerate(pages_to_sync_ids, 1):
            try:
                logger.info(f"  [{i}/{len(pages_to_sync_ids)}] Fetching & saving: {page_id}")
                clear_block_cache()
                title = await get_page_title(page_id)
                blocks = await get_block_content(page_id)
                markdown_content = page_to_markdown(blocks)
                filepath = await save_page_to_file(page_id, title, markdown_content, content_type)
                logger.info(f"  [{i}/{len(pages_to_sync_ids)}] ✓ Saved: {filepath}")
            except Exception as e:
                logger.error(f"  [{i}/{len(pages_to_sync_ids)}] ERROR processing page {page_id}: {e}")
                if os.getenv("MAIA_DEBUG") == "1":
                    traceback.print_exc()
    
    if not fetch_all and not force_pull:
        update_last_sync_time(content_type)

async def handle_cms_pull(args):
    """Handles 'maia cms pull' command - pulls CMS entries for KOii chat context."""
    logger.info("Starting CMS pull for KOii chat context")
    
    try:
        from promaia.config.databases import get_database_config
        database_config = get_database_config("cms")
        if not database_config:
            raise ValueError("CMS database not found in configuration")
    except (FileNotFoundError, ValueError) as e:
        logger.error(f"Error loading CMS database configuration: {e}")
        return

    await pull_cms_filtered(
        database_config=database_config,
        output_dir="KOii-chat-context", 
        property_filters={"KOii chat": True},
        days=args.days,
        force=args.force,
        description="KOii chat context"
    )

async def handle_cms_push(args):
    """Handles 'maia cms push' command."""
    logger.info(f"Initiating push to CMS")
    
    title = args.title

    try:
        database_id = get_notion_database_id("cms")
    except (FileNotFoundError, ValueError) as e:
        logger.error(f"Error loading Notion database ID for CMS: {e}")
        return

    logger.info(f"Pushing to Notion database ID: {database_id}")

    draft_file_path = args.draft
    if not draft_file_path:
        draft_files = glob.glob("drafts/*.md")
        if not draft_files:
            logger.error("No draft files found in drafts/ directory. Specify with --draft <filepath>.")
            return
        draft_files.sort(key=os.path.getmtime, reverse=True)
        draft_file_path = draft_files[0]
        logger.info(f"No --draft specified, using most recent: {draft_file_path}")

    if not os.path.exists(draft_file_path):
        logger.error(f"Draft file not found: {draft_file_path}")
        return

    with open(draft_file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    final_title = title
    if not final_title:
        title_match = re.search(r'^#\\s+(.+)$', content, re.MULTILINE)
        if title_match:
            final_title = title_match.group(1).strip()
        else:
            final_title = os.path.basename(draft_file_path).replace('.md', '').replace('_', ' ').title()
    
    logger.info(f"Creating Notion page with title: '{final_title}'")
    
    try:
        notion_client = ensure_default_client()
        response = await notion_client.pages.create(
            parent={"database_id": database_id},
            properties={
                "Name": {"title": [{"text": {"content": final_title}}]},
                "Status": {"select": {"name": "Draft"}},
                "Publish Date": {"date": {"start": now_utc().strftime("%Y-%m-%d")}}
            },
            children=[
                {"object": "block", "type": "paragraph", "paragraph": {
                    "rich_text": [{"type": "text", "text": {"content": "Content will be added by the editor. Full content from local draft."}}]
                }}
            ]
        )
        page_id = response["id"]
        page_url = f"https://notion.so/{page_id.replace('-', '')}"
        logger.info(f"SUCCESS: Created Notion page with ID: {page_id}")
        logger.info(f"Page URL: {page_url}")
        logger.info("\nCMS push completed successfully!")
        logger.info("Note: You'll need to manually copy the content from the draft into the Notion page.")
    except Exception as e:
        logger.error(f"Error pushing to Notion: {str(e)}")
        if hasattr(e, 'body'): logger.error(f"Details: {e.body}")

async def handle_cms_sync(args):
    """Handles 'maia cms sync' command."""
    from promaia.webflow.sync import sync_to_webflow

    logger.info(f"Initiating sync for CMS with Webflow.")
    
    try:
        notion_db_id = get_notion_database_id("cms")
    except (FileNotFoundError, ValueError) as e:
        logger.error(f"Error loading Notion database ID for CMS: {e}")
        return

    webflow_collection_id = args.collection or os.getenv("WEBFLOW_COLLECTION_ID")
    blog_status_prop = args.blog_status_property
    force = args.force_update

    if not webflow_collection_id:
        logger.error("Webflow Collection ID not specified (use --collection or WEBFLOW_COLLECTION_ID env var).")
        return

    logger.info(f"Syncing Notion DB (CMS: {notion_db_id}) to Webflow Collection: {webflow_collection_id}")
    logger.info(f"Using Notion status property: '{blog_status_prop}'")
    if force: logger.info("--force-update flag is active.")

    try:
        await sync_to_webflow(
            notion_database_id=notion_db_id,
            webflow_collection_id=webflow_collection_id,
            blog_status_property_name=blog_status_prop,
            force_update=force
        )
    except Exception as e:
        logger.error(f"Error during Notion-Webflow sync: {str(e)}")
        traceback.print_exc()

async def pull_cms_filtered(database_config, output_dir, property_filters, days, force, description):
    """Helper function to pull filtered CMS content to a specific directory."""
    import os
    import json
    from datetime import datetime
    from promaia.connectors import ConnectorRegistry
    from promaia.config.workspaces import get_workspace_api_key
    
    # Create output directory
    full_output_dir = os.path.join(os.getcwd(), output_dir)
    os.makedirs(full_output_dir, exist_ok=True)
    
    logger.info(f"Saving {description} to: {full_output_dir}")
    
    # Get workspace-specific API key
    api_key = get_workspace_api_key(database_config.workspace)
    if not api_key:
        logger.error(f"No API key configured for workspace '{database_config.workspace}'")
        return
    
    # Configure connector
    connector_config = database_config.to_dict()
    connector_config['api_key'] = api_key
    
    connector = ConnectorRegistry.get_connector(database_config.source_type, connector_config)
    if not connector:
        logger.error(f"Could not create connector for {database_config.source_type}")
        return
    
    # Parse days argument
    if days is not None:
        if isinstance(days, str) and days.lower() == 'all':
            days = None  # All entries
        else:
            try:
                days = int(days)
            except ValueError:
                days = database_config.default_days
    else:
        days = database_config.default_days
    
    logger.info(f"Filtering CMS pages with {property_filters}, days: {days or 'all'}")
    
    try:
        # Build filters
        from promaia.connectors.base import QueryFilter, DateRangeFilter
        from datetime import datetime
        from promaia.utils.timezone_utils import days_ago_utc, now_utc
        
        filters = []
        for prop_name, prop_value in property_filters.items():
            filters.append(QueryFilter(
                property_name=prop_name,
                operator="eq",
                value=prop_value
            ))
        
        # Create date filter if days is specified
        date_filter = None
        if days:
            start_date = days_ago_utc(days)
            date_filter = DateRangeFilter(
                property_name="last_edited_time",
                start_date=start_date,
                end_date=None
            )
        
        pages = await connector.query_pages(filters=filters, date_filter=date_filter)
        logger.info(f"Found {len(pages)} pages matching filters")
        
        # Save pages
        saved_count = 0
        for page in pages:
            try:
                page_id = page.get("id", "unknown")
                
                # Extract title
                title = "Untitled"
                properties = page.get("properties", {})
                for prop_name, prop_data in properties.items():
                    if prop_data.get("type") == "title" and prop_data.get("title"):
                        title = prop_data["title"][0].get("plain_text", "Untitled")
                        break
                
                # Get page content
                try:
                    from promaia.notion.pages import get_block_content
                    from promaia.markdown.converter import page_to_markdown
                    content_blocks = await get_block_content(page_id)
                    markdown_content = page_to_markdown(content_blocks)
                    page["content"] = markdown_content
                except Exception as content_error:
                    logger.warning(f"Could not fetch content for page {page_id}: {content_error}")
                    page["content"] = ""
                
                # Clean title for filename
                clean_title = "".join(c for c in title if c.isalnum() or c in (' ', '-', '_')).rstrip()
                clean_title = clean_title.replace(' ', '_')
                if not clean_title:
                    clean_title = f"untitled_{page_id[:8]}"
                
                # Save as JSON
                json_filename = f"{clean_title}_{page_id[:8]}.json"
                json_path = os.path.join(full_output_dir, json_filename)
                with open(json_path, 'w', encoding='utf-8') as f:
                    json.dump(page, f, indent=2, ensure_ascii=False)
                
                # Save as markdown if content exists
                if page.get("content"):
                    md_filename = f"{clean_title}_{page_id[:8]}.md"
                    md_path = os.path.join(full_output_dir, md_filename)
                    with open(md_path, 'w', encoding='utf-8') as f:
                        f.write(f"# {title}\n\n")
                        f.write(page["content"])
                
                saved_count += 1
                logger.info(f"Saved: {clean_title}")
                
            except Exception as e:
                logger.error(f"Error saving page {page_id}: {e}")
        
        logger.info(f"Successfully saved {saved_count} {description} pages")
        
        # Create metadata file
        metadata = {
            "created_at": now_utc().isoformat(),
            "filter_applied": property_filters,
            "days_filter": days,
            "total_pages": len(pages),
            "saved_pages": saved_count,
            "description": description
        }
        
        metadata_path = os.path.join(full_output_dir, "_metadata.json")
        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)
        
    except Exception as e:
        logger.error(f"Error querying CMS pages: {e}")
        import traceback
        traceback.print_exc()

# ==================== CORE COMMANDS ====================

def chat_run(args):
    """Run the chat interface."""
    from promaia.chat.interface import chat
    from promaia.config.workspaces import get_workspace_manager
    
    sources = getattr(args, 'sources', None)
    filters = getattr(args, 'filters', None)
    workspace = getattr(args, 'workspace', None)
    
    # Non-interactive mode for the desktop app
    if not sys.stdout.isatty():
        # In non-interactive mode, the chat function is expected to 
        # initialize and then enter a loop to process messages from stdin.
        # This requires the `chat` function to be adapted for this behavior.
        # For now, we assume `chat` handles this.
        logging.info("Running in non-interactive mode.")

    try:
        # Validate workspace if specified
        if workspace:
            workspace_manager = get_workspace_manager()
            if not workspace_manager.validate_workspace(workspace):
                print(f"✗ Workspace '{workspace}' is not properly configured.", file=sys.stderr)
                return
        else:
            # Use default workspace
            workspace_manager = get_workspace_manager()
            workspace = workspace_manager.get_default_workspace()
            if not workspace:
                print("No workspace specified and no default workspace configured.", file=sys.stderr)
                return
        
        # The `chat` function will now need to handle the main loop
        chat(sources=sources, filters=filters, workspace=workspace, non_interactive=not sys.stdout.isatty())

    except ImportError as e:
        print(f"Error importing chat interface: {e}", file=sys.stderr)
        print("Please check your dependencies.", file=sys.stderr)
    except Exception as e:
        logging.error(f"An unexpected error occurred in chat_run: {e}", exc_info=True)
        print(f"An unexpected error occurred: {e}", file=sys.stderr)

async def write_run_async(args):
    """Run the write blog post command."""
    try:
        from promaia.write.interface import write_blog_post
    except ImportError as e:
        print(f"Error importing write interface: {e}")
        print("Please check your dependencies or run 'pip install -r requirements.txt'")
        return
        
    days_to_use = args.days
    if days_to_use is None:
        try:
            days_input = input("Enter number of days to look back for journal entries (default: from settings): ").strip()
            if days_input:
                days_to_use = int(days_input)
                if days_to_use < 0: days_to_use = 0
            else:
                days_to_use = get_sync_days_setting()
        except ValueError:
            days_to_use = get_sync_days_setting()
            logger.warning(f"Invalid input. Using default: {days_to_use} days.")
    
    if days_to_use == 0:
        logger.info("INFO: Journal entries will NOT be used as reference (--days 0).")

    await write_blog_post(
        days=days_to_use,
        custom_prompt=args.prompt,
        push_to_notion=not args.no_push,
        max_entries=args.max_entries,
        force_openai=args.force_openai,
        no_journal=(days_to_use == 0)
    )

def write_run(args):
    asyncio.run(write_run_async(args))

def model_run(args):
    """Set the default AI model for chat and write commands."""
    try:
        from promaia.chat.interface import get_api_preference, save_api_preference
    except ImportError as e:
        print(f"Error importing chat interface: {e}")
        print("Please check your dependencies or run 'pip install -r requirements.txt'")
        return
    
    current_model = get_api_preference()
    logger.info(f"Current model: {current_model}")
    logger.info("\nAvailable models:")
    options = {"1": "anthropic", "2": "openai", "3": "gemini"}
    api_keys = {
        "anthropic": "ANTHROPIC_API_KEY",
        "openai": "OPENAI_API_KEY",
        "gemini": "GOOGLE_API_KEY"
    }
    
    for key, name in options.items():
        key_status = "API Key Found" if os.getenv(api_keys[name]) else "API Key Missing"
        logger.info(f"{key}. {name.capitalize()} ({key_status})")
    
    choice_key = input("\nSelect a model (1-3, or Enter to keep current): ").strip()
    
    if not choice_key:
        logger.info("Model selection unchanged.")
        return
        
    if choice_key in options:
        chosen_model = options[choice_key]
        if not os.getenv(api_keys[chosen_model]):
            logger.error(f"ERROR: Cannot switch to {chosen_model.capitalize()}: {api_keys[chosen_model]} environment variable not set." )
            return
        save_api_preference(chosen_model)
        logger.info(f"SUCCESS: Switched default model to: {chosen_model.capitalize()}")
    else:
        logger.error("ERROR: Invalid choice. Please select from the available options.")

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

    # Add top-level sync command (alias for database sync)
    sync_parser = subparsers.add_parser('sync', help='Sync databases (alias for database sync)')
    sync_parser.add_argument('--source', '-s', dest='sources', action='append',
                            help='Source specifications (e.g., journal:30, trass.stories:7). Can be used multiple times.')
    sync_parser.add_argument('--days', type=int, help='Number of days to sync')
    sync_parser.add_argument('--force', action='store_true', help='Force update all files')
    sync_parser.set_defaults(func=handle_database_sync)

    # Gmail commands (optional)
    if gmail_commands_available:
        add_gmail_commands(subparsers)

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
        help="Add property filters in format 'property_name=value' or 'property_name>value' or 'property_name<value'. Can be used multiple times. Examples: 'status=published', 'created_time>2025-03-01', 'priority<5'"
    )
    chat_parser.add_argument(
        "--workspace", "-ws",
        help="Specify which workspace to use for chat (defaults to default workspace)"
    )
    chat_parser.set_defaults(func=chat_run)

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
    
    newsletter_push_parser = newsletter_subparsers.add_parser("push", help="Send newsletters via Resend for eligible CMS pages")
    newsletter_push_parser.set_defaults(func=newsletter_sync_command)
    
    # Add 'news' alias for newsletter
    news_parser = subparsers.add_parser("news", help="Newsletter operations (alias for newsletter)")
    news_subparsers = news_parser.add_subparsers(dest="newsletter_action", required=True, help="Newsletter action")
    
    news_push_parser = news_subparsers.add_parser("push", help="Send newsletters via Resend for eligible CMS pages")
    news_push_parser.set_defaults(func=newsletter_sync_command)

    # Add conversion commands
    add_conversion_commands(subparsers)

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

    args = parser.parse_args()

    # Configure logging
    log_level = logging.DEBUG if args.debug else logging.INFO
    
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
    if not args.debug:
        logging.getLogger("httpx").setLevel(logging.WARNING)
        logging.getLogger("notion_client").setLevel(logging.WARNING)
        logging.getLogger("urllib3.connectionpool").setLevel(logging.WARNING)
    
    logger = logging.getLogger(__name__)

    if args.debug:
        os.environ["MAIA_DEBUG"] = "1"
        logger.info("Maia Debug Mode Enabled")
    else:
        if "MAIA_DEBUG" in os.environ:
            del os.environ["MAIA_DEBUG"]

    # Startup registry validation (only for data operations)
    data_commands = ["sync", "chat", "database", "db", "cms", "write"]
    if args.command in data_commands:
        try:
            from promaia.config.registry_sync import validate_startup_registry
            validate_startup_registry(auto_fix=True)
        except Exception as e:
            logger.warning(f"Registry validation failed: {e}")

    if args.command is None:
        parser.print_help()
        return

    # Handle commands
    if args.command in ["chat", "model", "write"]:
        args.func(args)
    elif args.command == "cms":
        if hasattr(args, 'func'):
            asyncio.run(args.func(args))
        else:
            cms_parser.print_help()
    elif args.command == "newsletter":
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
            else:
                print(f"Unknown database command: {args.database_command}")
        else:
            print("Database command requires a subcommand. Use 'maia database --help' for options.")
    elif args.command in ["workspace", "ws"]:
        # Handle workspace commands (NEW) - use func attribute for dynamic routing
        if hasattr(args, 'func'):
            asyncio.run(args.func(args))
        else:
            print("Workspace command requires a subcommand. Use 'maia workspace --help' for options.")
    elif args.command in ["migration", "mig"]:
        # Handle migration commands
        if hasattr(args, 'migration_command') and args.migration_command:
            if hasattr(args, 'func'):
                args.func(args)
            else:
                print(f"No function assigned to migration command: {args.migration_command}")
        else:
            print("Migration command requires a subcommand. Use 'maia migration --help' for options.")
    elif args.command == "sync":
        # Handle top-level sync command (alias for database sync)
        asyncio.run(handle_database_sync(args))
    elif args.command in ["convert", "list-formats", "cleanup"]:
        # Handle conversion commands
        if hasattr(args, 'func'):
            asyncio.run(args.func(args))
        else:
            print(f"No function assigned to command: {args.command}")
    elif args.command == "edit":
        # Handle edit command
        if hasattr(args, 'func'):
            args.func(args)
        else:
            edit_parser.print_help()
    elif args.command == "gmail":
        # Handle Gmail commands
        if hasattr(args, 'gmail_command') and args.gmail_command:
            if hasattr(args, 'func'):
                asyncio.run(args.func(args))
            else:
                print(f"No function assigned to gmail command: {args.gmail_command}")
        else:
            print("Gmail command requires a subcommand. Use 'maia gmail --help' for options.")
    else:
        parser.print_help()

if __name__ == "__main__":
    main() 