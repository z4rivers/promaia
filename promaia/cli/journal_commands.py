"""
Journal Command Handlers - extracted from cli.py

Handles pulling journal entries from Notion and saving them locally.
"""
import os
import re
import traceback
import logging
from datetime import datetime
from typing import Optional

from promaia.utils.config import update_last_sync_time, get_last_sync_time, get_sync_days_setting, load_environment
load_environment()
from promaia.utils.config_loader import get_notion_database_id
from promaia.notion.journal_router import handle_journal_pull_date_range, handle_journal_pull_with_sub_pages

logger = logging.getLogger(__name__)
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
            if days_to_process < 0:
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
            # Standard journal pull not implemented - use handle_journal_pull_with_sub_pages instead
            logger.error("Standard journal pull without sub_pages is deprecated. Use --sub-pages flag.")
            return
        
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
    # Summarize functionality has been removed/deprecated
    logger.error("Journal summarize functionality is no longer available.")
    logger.info("This feature has been deprecated and removed from the codebase.")
    return
    
    # Dead code below - keeping for reference but unreachable
    # from promaia.summarize.interface import summarize_journal_entry, save_summary_entry
    
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

