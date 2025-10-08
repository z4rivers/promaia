"""
File storage operations for saving and reading markdown files.
"""
import os
import glob
import json
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import re
from promaia.utils.timezone_utils import now_utc
from pathlib import Path
import logging
import sqlite3

# Import the new centralized path function
from promaia.config.paths import get_project_root

# Use the centralized function to define PROJECT_ROOT
PROJECT_ROOT = get_project_root()

# Dynamic path functions that load from config
def get_journal_directory() -> str:
    """
    Get the journal markdown directory path from config.
    
    Returns:
        Journal directory path from database config
    """
    try:
        from promaia.config.databases import get_database_config
        db_config = get_database_config("journal")
        if db_config and hasattr(db_config, 'markdown_directory'):
            return db_config.markdown_directory
    except Exception as e:
        print(f"Warning: Could not load journal directory from config: {e}")
    
    # Fallback to default path if config loading fails
    return "data/md/notion/koii/journal"

def get_cms_directory() -> str:
    """
    Get the CMS markdown directory path from config.
    
    Returns:
        CMS directory path from database config
    """
    try:
        from promaia.config.databases import get_database_config
        db_config = get_database_config("cms")
        if db_config and hasattr(db_config, 'markdown_directory'):
            return db_config.markdown_directory
    except Exception as e:
        print(f"Warning: Could not load CMS directory from config: {e}")
    
    # Fallback to default path if config loading fails
    return "data/md/notion/koii/cms"

def get_public_entries_directory() -> str:
    """
    Get the public entries directory path.
    This is currently hardcoded as it's not in config yet.
    
    Returns:
        Public entries directory path
    """
    return "KOii-chat-entries"

# Legacy constants for backward compatibility (DEPRECATED - use functions above)
PUBLIC_ENTRIES_DIR_NAME = get_public_entries_directory()  # For scrubbed, public entries for web app

# The old get_output_dir and ensure_output_dir relied on os.getcwd(), which is brittle.
# We will make read_markdown_files more robust by using PROJECT_ROOT directly.
# These functions remain for other uses but their cwd-dependency is noted.
def get_output_dir(content_type: str) -> str:
    """
    Get the output directory for a specific content type.
    Constructs path relative to PROJECT_ROOT using dynamic config loading.

    Args:
        content_type: Type of content (e.g., "journal", "cms", "example")
    Returns:
        Absolute path to the output directory
    """
    dir_name = ""
    if content_type == "journal":
        dir_name = get_journal_directory()
    elif content_type == "cms": # Explicitly "cms"
        dir_name = get_cms_directory()
    else:
        # For any other content_type, create a directory named notion-<content_type>
        # e.g., if content_type is "example", dir_name will be "notion-example"
        dir_name = f"notion-{content_type}"
    
    return os.path.join(PROJECT_ROOT, dir_name)

def ensure_output_dir(content_type: str):
    """Ensure the output directory exists. Uses PROJECT_ROOT via get_output_dir."""
    # This function is problematic due to get_output_dir's reliance on CWD. # This comment is now less relevant
    # For read_markdown_files, we will handle directory creation directly. # This comment might be outdated
    # For save_page_to_file, it will continue to use this potentially brittle path. # Path is now robust
    output_dir_path = get_output_dir(content_type)
    os.makedirs(output_dir_path, exist_ok=True)

async def save_page_to_file(page_id: str, title: str, markdown_content: str, content_type: str = "journal") -> str:
    """
    Save a page to a markdown file.
    
    Args:
        page_id: ID of the page
        title: Title of the page
        markdown_content: Markdown content to save
        content_type: Type of content ("journal", "webflow", "cms")
        
    Returns:
        Path to the saved file
    """
    ensure_output_dir(content_type)
    output_dir = get_output_dir(content_type)
    
    # Create a safe filename from the title
    safe_title = "".join(c if c.isalnum() or c in " -_" else "_" for c in title)
    
    # Create the filename with just the title and page ID
    filename = f"{safe_title} {page_id}.md"
    filepath = os.path.join(output_dir, filename)
    
    # Save the markdown content to the file
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(markdown_content)
    
    return filepath

# ADDED: Helper function to predict journal entry filepath
def get_journal_entry_filepath(title: str, page_id: str) -> str:
    """
    Construct the expected filepath for a journal entry, mirroring save_page_to_file logic.
    
    Args:
        title: The title of the journal entry.
        page_id: The Notion page ID of the journal entry.
        
    Returns:
        The predicted absolute filepath for the journal entry.
    """
    output_dir = get_output_dir("journal") # Specifically for journal content type
    safe_title = "".join(c if c.isalnum() or c in " -_" else "_" for c in title)
    filename = f"{safe_title} {page_id}.md"
    return os.path.join(output_dir, filename)

def get_existing_page_ids(content_type: str = "journal") -> set:
    """
    Get the IDs of existing saved pages.
    
    Args:
        content_type: Type of content ("journal" or "webflow" or "cms")
        
    Returns:
        Set of page IDs that have already been saved
    """
    output_dir = get_output_dir(content_type)
    existing_ids = set()
    for file in glob.glob(os.path.join(output_dir, "*.md")):
        # Extract page ID from filename (last part after the last space)
        try:
            page_id = file.split()[-1].replace('.md', '')
            existing_ids.add(page_id)
        except:
            # Skip files with invalid format
            pass
    return existing_ids

def cleanup_old_pages(days: int = 30) -> int:
    """
    This function previously removed markdown files older than the specified 
    number of days, but we're now disabling this behavior to prevent unwanted
    file deletion. The files will remain in the OUTPUT_DIR.
    
    Args:
        days: Number of days parameter (ignored)
        
    Returns:
        Always returns 0 (no files removed)
    """
    # We no longer remove older files
    return 0

def read_markdown_files(
    days: Optional[int] = None, 
    content_type: str = "journal", # Deprecated for choosing source, use target_data_source
    target_data_source: str = "private" # "private" for notion-journal, "public" for public-entries
) -> List[Dict[str, Any]]:
    """
    Read markdown files and return their content as a list of dictionaries.
    Uses target_data_source to choose between private ('notion-journal') and public ('public-entries') sources.
    The content_type arg is kept for backward compatibility for non-journal types but ignored for journal source selection if target_data_source is used.
    """
    source_dir_name = ""
    # Prioritize webflow content_type check
    if content_type == "webflow" or content_type == "cms":
        source_dir_name = get_cms_directory()
    # Then check target_data_source for journal types
    elif target_data_source == "private":
        source_dir_name = get_journal_directory()
    elif target_data_source == "public":
        source_dir_name = get_public_entries_directory()
    # elif content_type == "prompts": # REMOVED
    #     source_dir_name = PROMPTS_DIR_NAME # REMOVED
    else:
        # Fallback or error if no valid source can be determined
        # This case might need review - should it ever happen now?
        print(f"Warning: Could not determine data source. Defaulting to private journal. target_data_source: {target_data_source}, content_type: {content_type}")
        source_dir_name = get_journal_directory() # Default to private journal if ambiguous

    # Construct the absolute path to the source directory using PROJECT_ROOT
    data_directory_path = os.path.join(PROJECT_ROOT, source_dir_name)

    if not os.path.isdir(data_directory_path):
        print(f"Error: Source directory not found: {data_directory_path}")
        # If public is specified and not found, do not fallback to private here unless explicitly desired.
        # For now, we simply return empty if the intended directory is missing.
        if target_data_source == "public":
            print(f"Specifically, public entries directory '{data_directory_path}' does not exist.")
        return []
    
    # Ensure the directory exists (primarily for save operations, but good check)
    # os.makedirs(data_directory_path, exist_ok=True) # Not strictly needed for read if check above is done
    
    pages = []
    markdown_files_glob = os.path.join(data_directory_path, "*.md")
    markdown_files = glob.glob(markdown_files_glob)
    
    total_files = 0
    filtered_files = 0
    all_dates = []
    
    # Collect all dates from filenames for reference
    for file_path_iter in markdown_files: # Renamed to avoid conflict with outer scope var if any
        try:
            filename_iter = os.path.basename(file_path_iter)
            date_match = re.search(r'(\d{4}-\d{2}-\d{2})', filename_iter)
            if date_match:
                try:
                    date_str_iter = date_match.group(1)
                    file_date_iter = datetime.strptime(date_str_iter, "%Y-%m-%d")
                    all_dates.append(file_date_iter)
                except ValueError:
                    pass
        except Exception:
            pass # ... (original exception handling)
    
    if all_dates:
        all_dates.sort(reverse=True)
    
    cutoff_date = None
    if days is not None:
        reference_date = max(all_dates) if all_dates else datetime.now()
        cutoff_date = reference_date - timedelta(days=days)
    
    for file_path in markdown_files:
        total_files += 1
        try:
            filename = os.path.basename(file_path)
            file_mtime = os.path.getmtime(file_path)
            mod_date_obj = datetime.fromtimestamp(file_mtime)
            date_from_filename = None
            # Using simplified content_type check here for date extraction context
            # The primary directory choice is done by target_data_source
            is_journal_context = (source_dir_name == get_journal_directory() or source_dir_name == get_public_entries_directory()) # Removed PROMPTS_DIR_NAME

            if is_journal_context: 
                date_match = re.search(r'^(\d{4}-\d{2}-\d{2})', filename) 
                if not date_match: 
                    date_match = re.search(r'(\d{4}-\d{2}-\d{2})', filename) 
                if not date_match: 
                    id_match = re.search(r'([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})', filename.lower()) 
                    if id_match: 
                        page_id = id_match.group(1) 
                        for other_file in markdown_files: 
                            other_filename = os.path.basename(other_file) 
                            if page_id in other_filename.lower() and re.search(r'(\d{4}-\d{2}-\d{2})', other_filename): 
                                date_match = re.search(r'(\d{4}-\d{2}-\d{2})', other_filename) 
                                break 
                if date_match: 
                    try: 
                        date_str = date_match.group(1) 
                        date_from_filename = datetime.strptime(date_str, "%Y-%m-%d") 
                    except ValueError: 
                        pass 
                elif all_dates and ("alweyssamer" in filename.lower() or "today" in filename.lower()): 
                    date_from_filename = all_dates[0]
            
            # IMPROVED DATE LOGIC: Always prioritize date from filename over mtime for better chronological ordering
            date_obj = mod_date_obj
            debug_info = "date from mtime"
            
            # First priority: date extracted from filename (most reliable)
            if date_from_filename:
                date_obj = date_from_filename
                debug_info = "date in filename"
            # Second priority: use mtime but ensure it's reasonable
            elif all_dates and is_journal_context:
                # If file mtime seems unreliable (very different from other files), use reference date
                if abs(max(all_dates).year - datetime.now().year) > 1:
                    if date_obj.year != max(all_dates).year:
                        date_obj = max(all_dates)
                        debug_info = "newest file date (due to year diff, simplified)"
            
            date_str_display = date_obj.strftime("%Y-%m-%d")
            
            if cutoff_date is not None and date_obj.date() < cutoff_date.date():
                filtered_files += 1
                continue
            
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            pages.append({
                'date': date_str_display,
                'date_obj': date_obj,
                'content': content,
                'file_path': file_path,
                'filename': filename,
                'debug_info': debug_info
            })
        except Exception as e:
            print(f"Error reading file {file_path}: {str(e)}")
    
    pages.sort(key=lambda x: x['date_obj'], reverse=True)
    print(f"Read {len(pages)} pages from {data_directory_path}. Total files scanned: {total_files}, initially filtered out by date: {filtered_files}")
    return pages

def test_days_filtering(days=7):
    """Test function to debug the date filtering in read_markdown_files."""
    print(f"\nTESTING DAYS FILTERING WITH {days} DAYS\n" + "="*50)
    
    # Get the pages filtered by days
    pages = read_markdown_files(days=days)
    
    # Print summary of included pages
    print(f"\nINCLUDED PAGES ({len(pages)}):")
    for page in pages:
        print(f"  - {page['filename']} (Date: {page['date']}, Source: {'filename' if 'date in filename' in page.get('debug_info', '') else 'mtime'})")
    
    # Get all pages without filtering
    all_pages = read_markdown_files(days=None)
    
    # Find excluded pages
    excluded_filenames = set(p['filename'] for p in all_pages) - set(p['filename'] for p in pages)
    
    print(f"\nEXCLUDED PAGES ({len(excluded_filenames)}):")
    for filename in sorted(excluded_filenames):
        page = next((p for p in all_pages if p['filename'] == filename), None)
        if page:
            print(f"  - {page['filename']} (Date: {page['date']})")
    
    print("\n" + "="*50)
    
    return pages

def read_markdown_files_from_sources(sources: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    """
    Read markdown files from multiple sources with different day filters.
    
    Args:
        sources: List of source configurations, each containing:
                - database: database name (matches directory name in data/)
                - days: number of days to filter (int or 'all')
    
    Returns:
        Dictionary with database names as keys and lists of pages as values:
        {
            'koii_journal': [page1, page2, ...],
            'awakenings': [page1, page2, ...],
            ...
        }
    """
    source_data = {}
    total_pages = 0
    
    for source in sources:
        database_name = source.get('database')
        days = source.get('days')
        
        if not database_name:
            print(f"Warning: Skipping source with missing database name: {source}")
            continue
            
        # Convert 'all' to None for the read function
        days_filter = None if days == 'all' else days
        
        # Construct the path to the database directory
        database_path = os.path.join(PROJECT_ROOT, "data", database_name)
        
        if not os.path.isdir(database_path):
            print(f"Warning: Database directory not found: {database_path}")
            continue
            
        print(f"Loading from {database_name} with {days} days filter...")
        
        # Use the existing read_markdown_files logic but with custom directory
        pages = read_markdown_files_from_directory(database_path, days_filter)
        
        # Add source information to each page
        for page in pages:
            page['source_database'] = database_name
            
        # Sort pages by date (newest first)
        pages.sort(key=lambda x: x['date_obj'], reverse=True)
        
        source_data[database_name] = pages
        total_pages += len(pages)
        print(f"Loaded {len(pages)} pages from {database_name}")
    
    print(f"Total loaded: {total_pages} pages from {len(sources)} sources")
    return source_data

def read_markdown_files_from_directory(directory_path: str, days: Optional[int] = None) -> List[Dict[str, Any]]:
    """
    Read markdown files from a specific directory with date filtering.
    Similar to read_markdown_files but takes a direct directory path.
    
    Args:
        directory_path: Absolute path to the directory containing markdown files
        days: Number of days to look back (None for all files)
    
    Returns:
        List of page data dictionaries
    """
    if not os.path.isdir(directory_path):
        return []

    pages = []
    markdown_files_glob = os.path.join(directory_path, "*.md")
    markdown_files = glob.glob(markdown_files_glob)
    
    total_files = 0
    filtered_files = 0
    all_dates = []
    
    # Collect all dates from filenames for reference
    for file_path_iter in markdown_files:
        try:
            filename_iter = os.path.basename(file_path_iter)
            date_match = re.search(r'(\d{4}-\d{2}-\d{2})', filename_iter)
            if date_match:
                try:
                    date_str_iter = date_match.group(1)
                    file_date_iter = datetime.strptime(date_str_iter, "%Y-%m-%d")
                    all_dates.append(file_date_iter)
                except ValueError:
                    pass
        except Exception:
            pass
    
    if all_dates:
        all_dates.sort(reverse=True)
    
    cutoff_date = None
    if days is not None:
        reference_date = max(all_dates) if all_dates else datetime.now()
        cutoff_date = reference_date - timedelta(days=days)
    
    for file_path in markdown_files:
        total_files += 1
        try:
            filename = os.path.basename(file_path)
            file_mtime = os.path.getmtime(file_path)
            mod_date_obj = datetime.fromtimestamp(file_mtime)
            date_from_filename = None
            
            # IMPROVED DATE EXTRACTION: Try to extract date from filename with better patterns
            date_from_filename = None
            
            # First: try YYYY-MM-DD at start of filename (preferred format)
            date_match = re.search(r'^(\d{4}-\d{2}-\d{2})', filename)
            if date_match:
                try:
                    date_str = date_match.group(1)
                    date_from_filename = datetime.strptime(date_str, "%Y-%m-%d")
                except ValueError:
                    pass
            
            # Second: try YYYY-MM-DD anywhere in filename
            if not date_from_filename:
                date_match = re.search(r'(\d{4}-\d{2}-\d{2})', filename)
                if date_match:
                    try:
                        date_str = date_match.group(1)
                        date_from_filename = datetime.strptime(date_str, "%Y-%m-%d")
                    except ValueError:
                        pass
            
            # Third: look for cross-references by page ID if no date found
            if not date_from_filename:
                id_match = re.search(r'([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})', filename.lower())
                if id_match:
                    page_id = id_match.group(1)
                    for other_file in markdown_files:
                        other_filename = os.path.basename(other_file)
                        if page_id in other_filename.lower() and re.search(r'(\d{4}-\d{2}-\d{2})', other_filename):
                            date_match = re.search(r'(\d{4}-\d{2}-\d{2})', other_filename)
                            if date_match:
                                try:
                                    date_str = date_match.group(1)
                                    date_from_filename = datetime.strptime(date_str, "%Y-%m-%d")
                                    break
                                except ValueError:
                                    pass
            
            # Fourth: special case handling for legacy filenames
            if not date_from_filename and all_dates and ("alweyssamer" in filename.lower() or "today" in filename.lower()):
                date_from_filename = all_dates[0]
            
            # IMPROVED DATE LOGIC: Always prioritize date from filename over mtime for better chronological ordering
            date_obj = mod_date_obj
            debug_info = "date from mtime"
            
            # First priority: date extracted from filename (most reliable)
            if date_from_filename:
                date_obj = date_from_filename
                debug_info = "date in filename"
            # Second priority: use mtime but ensure it's reasonable  
            elif all_dates:
                # If file mtime seems unreliable (very different from other files), use reference date
                if abs(max(all_dates).year - datetime.now().year) > 1:
                    if date_obj.year != max(all_dates).year:
                        date_obj = max(all_dates)
                        debug_info = "newest file date (due to year diff, simplified)"
            
            date_str_display = date_obj.strftime("%Y-%m-%d")
            
            if cutoff_date is not None and date_obj.date() < cutoff_date.date():
                filtered_files += 1
                continue
            
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            pages.append({
                'date': date_str_display,
                'date_obj': date_obj,
                'content': content,
                'file_path': file_path,
                'filename': filename,
                'debug_info': debug_info
            })
        except Exception as e:
            print(f"Error reading file {file_path}: {str(e)}")
    
    pages.sort(key=lambda x: x['date_obj'], reverse=True)
    return pages

def load_json_files_with_property_filter(property_filters: Dict[str, Any], json_directory: str = "data/json") -> List[str]:
    """
    Load JSON files and return page IDs that match the specified property filters.
    
    Args:
        property_filters: Dictionary of property_name -> value filters
        json_directory: Directory containing JSON files
        
    Returns:
        List of page IDs that match all property filters
    """
    if not property_filters:
        return []
    
    json_dir_path = os.path.join(PROJECT_ROOT, json_directory)
    
    if not os.path.exists(json_dir_path):
        print(f"Warning: JSON directory not found: {json_dir_path}")
        return []
    
    matching_page_ids = []
    json_files = glob.glob(os.path.join(json_dir_path, "*.json"))
    
    for json_file in json_files:
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                page_data = json.load(f)
            
            # Check if this page matches all property filters
            matches_all_filters = True
            page_properties = page_data.get('properties', {})
            
            for prop_name, expected_value in property_filters.items():
                prop_data = page_properties.get(prop_name)
                if not prop_data:
                    matches_all_filters = False
                    break
                
                # Extract the actual value based on property type
                prop_type = prop_data.get('type')
                actual_value = None
                
                if prop_type == 'checkbox':
                    actual_value = prop_data.get('checkbox', False)
                elif prop_type == 'select' and prop_data.get('select'):
                    actual_value = prop_data['select'].get('name')
                elif prop_type == 'status' and prop_data.get('status'):
                    actual_value = prop_data['status'].get('name')
                elif prop_type == 'title' and prop_data.get('title'):
                    actual_value = ''.join([t.get('plain_text', '') for t in prop_data['title']])
                elif prop_type == 'rich_text' and prop_data.get('rich_text'):
                    actual_value = ''.join([t.get('plain_text', '') for t in prop_data['rich_text']])
                # Add more property types as needed
                
                # Compare values
                if actual_value != expected_value:
                    matches_all_filters = False
                    break
            
            if matches_all_filters:
                page_id = page_data.get('page_id') or page_data.get('id')  # Try both keys
                if page_id:
                    matching_page_ids.append(page_id)
                    
        except Exception as e:
            print(f"Warning: Error processing JSON file {json_file}: {e}")
            continue
    
    return matching_page_ids

def read_markdown_files_by_page_ids(page_ids: List[str], directory_path: str, days: Optional[int] = None) -> List[Dict[str, Any]]:
    """
    Read specific markdown files by page IDs from a directory.
    
    Args:
        page_ids: List of page IDs to load
        directory_path: Directory containing markdown files
        days: Optional days filter for additional time-based filtering
        
    Returns:
        List of page data dictionaries for matching files
    """
    if not page_ids:
        return []
    
    if not os.path.exists(directory_path):
        print(f"Warning: Markdown directory not found: {directory_path}")
        return []
    
    pages = []
    markdown_files = glob.glob(os.path.join(directory_path, "*.md"))
    
    # Create a set for faster lookup
    target_page_ids = set(page_ids)
    
    for file_path in markdown_files:
        try:
            filename = os.path.basename(file_path)
            
            # Extract page ID from filename (assuming format: "title page_id.md")
            # Handle both UUID format and Gmail thread ID format
            page_id_match = re.search(r'([a-f0-9-]{36}|thread_[a-f0-9]{16})\.md$', filename)
            if not page_id_match:
                continue
                
            file_page_id = page_id_match.group(1)
            
            # Only process if this page ID is in our target list
            if file_page_id not in target_page_ids:
                continue
            
            # Apply days filter if specified
            if days is not None:
                file_mtime = datetime.fromtimestamp(os.path.getmtime(file_path))
                cutoff_date = datetime.now() - timedelta(days=days)
                if file_mtime < cutoff_date:
                    continue
            
            # Read the markdown content
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Create page data structure
            page_data = {
                'id': file_page_id,
                'filename': filename,
                'content': content,
                'file_path': file_path,
                'modified_time': datetime.fromtimestamp(os.path.getmtime(file_path))
            }
            
            pages.append(page_data)
            
        except Exception as e:
            print(f"Warning: Error processing markdown file {file_path}: {e}")
            continue
    
    return pages

def create_channel_or_filter(channel_names: List[str]) -> Dict[str, Any]:
    """
    Create a complex filter that matches any of the specified Discord channel names.
    
    Args:
        channel_names: List of channel names to match
        
    Returns:
        Complex filter with OR logic for channel names
    """
    if not channel_names:
        return {}
    
    if len(channel_names) == 1:
        # Single channel - return simple filter
        return {'discord_channel_name': channel_names[0]}
    
    # Multiple channels - create complex filter with OR logic
    or_clauses = []
    for channel_name in channel_names:
        or_clauses.append([{
            'property': 'discord_channel_name',
            'operator': '=', 
            'value': channel_name
        }])
    
    return {
        'type': 'complex',
        'or_clauses': or_clauses
    }

def read_markdown_files_with_registry(
    database_config, 
    days: Optional[int] = None,
    comparison_filters: Optional[Dict[str, Any]] = None,
    complex_filter: Optional[Dict[str, Any]] = None,
    property_filters: Optional[Dict[str, Any]] = None
) -> List[Dict[str, Any]]:
    """
    Read markdown files using the database registry as the source of truth for ordering.
    
    This function provides more accurate chronological ordering by using the SQLite
    registry which contains the actual date information from the original data sources.
    
    Args:
        database_config: DatabaseConfig object with workspace and nickname
        days: Number of days to look back (None for all files) - filters based on last_edited_time by default
        comparison_filters: Dictionary of comparison filters (e.g., {'created_time_after': [...]})
        complex_filter: Dictionary representing a complex filter expression with 'or'/'and' operators
        property_filters: Dictionary of simple property filters (e.g., {'Reference': True, 'status': 'published'})
    
    Returns:
        List of page data dictionaries ordered by the configured date property (last_edited_time by default)
    """
    from promaia.storage.hybrid_storage import get_hybrid_registry
    
    pages = []
    
    try:
        # Get registry entries for this database, ordered by date property
        registry = get_hybrid_registry()
        
        # Query registry for files in this database
        with sqlite3.connect(registry.db_path) as conn:
            cursor = conn.cursor()
            
            # Determine which date property to use from config, default to last_edited_time
            # Use last_edited_time as default to show recently modified content first
            date_filter_prop = database_config.date_filters.get("property", "last_edited_time")
            
            # Basic sanitization to prevent SQL injection from config values
            # This is a safeguard; config should be trusted but it's good practice
            allowed_props = ["created_time", "last_edited_time", "synced_time"] # Use columns that exist in unified_content view
            if date_filter_prop not in allowed_props:
                # If the configured property is not a direct column, use last_edited_time as fallback
                if DEBUG_MODE:
                    print(f"Info: date_filter property '{date_filter_prop}' in config is not a direct column. Using 'last_edited_time' for query.")
                date_filter_prop = "last_edited_time"

            # Query the unified_content view for this database
            # Use database_id for reliable lookup across all database types
            where_conditions = ["workspace = ?", "database_id = ?"]
            params = [database_config.workspace, database_config.database_id]
            
            # Add date filtering if days parameter is provided
            if days:
                # Handle special case for 'all' - no date filtering
                if isinstance(days, str) and days.lower() == 'all':
                    # Skip date filtering for 'all'
                    pass
                else:
                    # Ensure days is an integer (handle string input)
                    try:
                        days_int = int(days) if isinstance(days, str) else days
                        cutoff_date = (datetime.now() - timedelta(days=days_int)).isoformat()
                        where_conditions.append(f"({date_filter_prop} >= ?)")
                        params.append(cutoff_date)
                    except (ValueError, TypeError) as e:
                        print(f"Warning: Invalid days parameter '{days}': {e}")
                        # Continue without date filtering if days parameter is invalid
            
            where_clause = " AND ".join(where_conditions)
            query = f"""
                SELECT page_id, title, created_time, last_edited_time, synced_time, file_path, metadata
                FROM unified_content 
                WHERE {where_clause}
                ORDER BY {date_filter_prop} DESC
            """
            cursor.execute(query, params)
            registry_entries = cursor.fetchall()

        # Correctly get project root
        project_root = get_project_root()
        
        # Get markdown directory for fallback lookups
        # Ensure md_dir is an absolute path
        md_dir = database_config.markdown_directory
        if not os.path.isabs(md_dir):
            md_dir = os.path.join(project_root, md_dir)
        
        for page_id, title, created_time, last_edited_time, synced_time, file_path, metadata in registry_entries:
            try:
                # Optimized approach: Try direct file path first, then limited search
                md_files = []
                
                # First try: Use registry file_path if available and exists
                # Resolve relative paths against project_root
                if file_path:
                    full_path = file_path if os.path.isabs(file_path) else os.path.join(project_root, file_path)
                    if os.path.exists(full_path):
                        md_files = [full_path]
                
                if not md_files:
                    # Second try: Build expected path from page_id and check if it exists
                    expected_paths = [
                        os.path.join(md_dir, f"{page_id}.md"),
                        os.path.join(md_dir, f"{page_id}_{title}.md") if title else None,
                        os.path.join(md_dir, f"{title}_{page_id}.md") if title else None
                    ]
                    
                    for expected_path in expected_paths:
                        if expected_path and os.path.exists(expected_path):
                            md_files = [expected_path]
                            break
                    
                    # Last resort: Limited recursive search (only if really needed)
                    if not md_files:
                        try:
                            # Limit search to prevent hangs - only search immediate subdirectories
                            for subdir in [md_dir] + [os.path.join(md_dir, d) for d in os.listdir(md_dir) if os.path.isdir(os.path.join(md_dir, d))]:
                                pattern = os.path.join(subdir, f"*{page_id}*.md")
                                matches = glob.glob(pattern)
                                if matches:
                                    md_files = matches
                                    break
                        except (OSError, PermissionError):
                            # Skip if directory issues
                            continue
                
                if not md_files:
                    # Only warn if we truly can't find the file by page_id
                    continue  # Skip warning for missing files - they may have been deleted intentionally
                
                # Use the most recent file if multiple matches (shouldn't happen but just in case)
                md_files.sort(key=lambda f: os.path.getmtime(f), reverse=True)
                md_file = md_files[0]
                
                # Update the registry with the correct file path
                try:
                    relative_path = os.path.relpath(md_file, project_root)
                    cursor.execute(
                        "UPDATE unified_content SET file_path = ? WHERE page_id = ?",
                        (relative_path, page_id)
                    )
                    # Note: connection.commit() is handled by the caller
                except Exception:
                    pass  # Silent fail for registry updates

                # Read the markdown content
                with open(md_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Parse created_time from registry
                try:
                    if created_time:
                        date_obj = datetime.fromisoformat(created_time.replace("Z", "+00:00"))
                    else:
                        # Fallback to file mtime
                        date_obj = datetime.fromtimestamp(os.path.getmtime(md_file))
                except (ValueError, TypeError):
                    date_obj = datetime.fromtimestamp(os.path.getmtime(md_file))
                
                pages.append({
                    'page_id': page_id,
                    'date': date_obj.strftime("%Y-%m-%d"),
                    'date_obj': date_obj,
                    'content': content,
                    'file_path': md_file,
                    'filename': os.path.basename(md_file),
                    'title': title or "Untitled",
                    'created_time': created_time,
                    'last_edited_time': last_edited_time,
                    'synced_time': synced_time,
                    'metadata': metadata,  # Include the metadata from the registry!
                    'debug_info': "date from database registry"
                })
                
            except Exception as e:
                print(f"Error processing registry entry {page_id}: {e}")
                continue
    
        # Commit any registry path updates that were made during the loop
        try:
            conn.commit()
        except Exception:
            pass
    
    except Exception as e:
        print(f"Error reading from registry: {e}")
        print(f"✗ Registry-first architecture requires functional metadata database.")
        print(f"  Run 'maia database register-markdown-files' to fix registry.")
        return []
    
    initial_page_count = len(pages)
    if os.environ.get("MAIA_DEBUG") == "1":
        print(f"Read {initial_page_count} pages from database registry for {database_config.workspace}.{database_config.nickname}")
    
    # Apply custom property filters
    filters_applied = False
    
    # Apply complex filters first
    if complex_filter:
        pages = apply_custom_property_filters(pages, complex_filter)
        filters_applied = True
    
    # Apply simple property filters
    if property_filters:
        pages = apply_simple_property_filters(pages, property_filters)
        filters_applied = True
    
    # Report filtering results
    if filters_applied and len(pages) != initial_page_count:
        print(f"Applied property filters: {len(pages)} pages remain after filtering")
    
    # Registry-first: if no results, that's the authoritative answer
    if len(pages) == 0:
        # Use database_id for the error message since that's what we actually queried
        print(f"No entries found in registry for {database_config.workspace}.{database_config.nickname} (database_id: {database_config.database_id})")
        print(f"Registry is the authoritative source - if files exist but aren't registered:")
        print(f"  Run 'maia database register-markdown-files --database {database_config.nickname} --workspace {database_config.workspace}'")
        
        # Additional debugging for Discord databases
        if database_config.source_type == "discord":
            print(f"Debug: Found {len(registry_entries)} raw entries in registry before file processing")
            if len(registry_entries) > 0:
                print(f"Debug: Entries exist but no markdown files could be loaded - check file paths and permissions")
        
        return []
    
    return pages

def apply_custom_property_filters(pages: List[Dict[str, Any]], complex_filter: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """
    Apply custom property filters to pages based on their metadata.
    
    Args:
        pages: List of page dictionaries with metadata
        complex_filter: Complex filter expression with custom properties
        
    Returns:
        Filtered list of pages
    """
    if not complex_filter or complex_filter.get('type') != 'complex':
        return pages
    
    filtered_pages = []
    
    for page in pages:
        # Parse metadata to get properties
        metadata = page.get('metadata', '{}')
        try:
            if isinstance(metadata, str):
                metadata_dict = json.loads(metadata) if metadata else {}
            else:
                metadata_dict = metadata
            
            properties = metadata_dict.get('properties', {})
            
            # Check if page matches the complex filter
            page_content = page.get('content', '')
            matches = evaluate_complex_filter(properties, complex_filter, page_content, metadata_dict)
            
            if matches:
                filtered_pages.append(page)
                
        except (json.JSONDecodeError, TypeError) as e:
            continue
    
    return filtered_pages


def apply_simple_property_filters(pages: List[Dict[str, Any]], property_filters: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Apply simple property filters to pages based on their metadata.
    
    Args:
        pages: List of page dictionaries with metadata
        property_filters: Dictionary of property_name -> expected_value filters
        
    Returns:
        Filtered list of pages
    """
    if not property_filters:
        return pages
    
    filtered_pages = []
    
    for page in pages:
        # Parse metadata to get properties
        metadata = page.get('metadata', '{}')
        try:
            if isinstance(metadata, str):
                metadata_dict = json.loads(metadata) if metadata else {}
            else:
                metadata_dict = metadata
            
            # Get Notion-style nested properties
            properties = metadata_dict.get('properties', {})
            
            # Check if page matches all property filters
            matches = True
            for prop_name, expected_value in property_filters.items():
                
                # For Discord and other flat metadata, check directly in metadata first
                if prop_name in metadata_dict:
                    actual_value = metadata_dict[prop_name]
                    if not evaluate_condition(actual_value, '=', expected_value):
                        matches = False
                        break
                    continue
                
                # For Notion-style nested properties
                prop_data = properties.get(prop_name, {})
                actual_value = extract_property_value(prop_data)
                
                # For Discord and other flat metadata, also check directly in metadata_dict
                if actual_value is None and prop_name in metadata_dict:
                    actual_value = metadata_dict[prop_name]
                
                # Apply the condition using the existing evaluate_condition function
                if not evaluate_condition(actual_value, '=', expected_value):
                    matches = False
                    break
            
            if matches:
                filtered_pages.append(page)
                
        except (json.JSONDecodeError, TypeError) as e:
            print(f"Warning: Could not parse metadata for page {page.get('page_id', 'unknown')}: {e}")
            continue
    return filtered_pages


def evaluate_complex_filter(properties: Dict[str, Any], complex_filter: Dict[str, Any], page_content: str = "", metadata_dict: Dict[str, Any] = {}) -> bool:
    """
    Evaluate a complex filter expression against page properties.
    
    Args:
        properties: Dictionary of page properties from Notion/Gmail
        complex_filter: Complex filter expression
        page_content: Full page content for content-based searches (e.g., contains operator)
        metadata_dict: The full metadata dictionary for Discord compatibility
        
    Returns:
        True if the properties match the filter, False otherwise
    """
    if complex_filter.get('type') != 'complex':
        return True
    
    or_clauses = complex_filter.get('or_clauses', [])
    
    # Evaluate each OR clause
    for i, and_conditions in enumerate(or_clauses):
        # All conditions in an AND clause must be true
        and_result = True
        has_non_date_conditions = False
        
        for condition in and_conditions:
            prop_name = condition.get('property', '')
            operator = condition.get('operator', '=')
            expected_value = condition.get('value', '')
            
            # Date properties are handled at SQL level, but we need to mark that we had conditions
            # to avoid empty AND clauses defaulting to True
            if prop_name in ['created_time', 'last_edited_time']:
                # For complex expressions, we assume date filtering was already applied at SQL level
                # So we treat date conditions as satisfied but don't count them as processed conditions
                continue
            
            has_non_date_conditions = True
            
            # Handle special 'contains' operator for full content search
            if operator == 'contains':
                # Search the full page content instead of properties
                condition_result = evaluate_condition(page_content, operator, expected_value)
            else:
                # Gmail property mapping: 'subject' -> 'title'
                # Gmail stores email subjects in the 'title' property, not 'subject'
                if prop_name == 'subject':
                    # Check if this looks like Gmail data by checking for common Gmail properties
                    if 'from' in properties or 'to' in properties:
                        prop_name = 'title'
            
            # Get the actual property value from the page
            prop_data = properties.get(prop_name, {})
            actual_value = extract_property_value(prop_data)
            
            # For Discord and other flat metadata, also check directly in metadata_dict
            if actual_value is None and prop_name in metadata_dict:
                actual_value = metadata_dict[prop_name]
            
            # Apply the condition
            condition_result = evaluate_condition(actual_value, operator, expected_value)
            
            if not condition_result:
                and_result = False
                break
        
        # If we had only date conditions in this AND clause, we need to be more careful
        # An AND clause with only date conditions should not automatically be True
        if not has_non_date_conditions:
            # This AND clause only had date conditions, which are handled at SQL level
            # We assume the SQL filtering already applied these correctly, so we skip this clause
            # rather than defaulting it to True
            continue
        
        # If any OR clause is satisfied, return True
        if and_result:
            return True
    
    # If no OR clause was satisfied, return False
    return False


def extract_property_value(prop_data: Dict[str, Any]) -> Any:
    """
    Extract the actual value from a property data structure.
    
    Handles both:
    - Notion-style properties: {"type": "email", "email": "value"}  
    - Gmail-style properties: "value" (simple values)
    
    Args:
        prop_data: Property data from Notion or Gmail
        
    Returns:
        The actual value of the property
    """
    if not prop_data:
        return None
    
    # Handle Gmail-style simple values (string, number, boolean, list)
    if not isinstance(prop_data, dict):
        return prop_data
    
    # Check if this is a Notion-style property with a "type" field
    if 'type' not in prop_data:
        # This is a Gmail-style simple property stored as a dict
        # or a malformed property, return the whole thing
        return prop_data
    
    # Handle Notion-style typed properties
    prop_type = prop_data.get('type')
    
    if prop_type == 'checkbox':
        return prop_data.get('checkbox', False)
    elif prop_type == 'select' and prop_data.get('select'):
        return prop_data['select'].get('name', '')
    elif prop_type == 'status' and prop_data.get('status'):
        return prop_data['status'].get('name', '')
    elif prop_type == 'title' and prop_data.get('title'):
        return ''.join([t.get('plain_text', '') for t in prop_data['title']])
    elif prop_type == 'rich_text' and prop_data.get('rich_text'):
        return ''.join([t.get('plain_text', '') for t in prop_data['rich_text']])
    elif prop_type == 'number':
        return prop_data.get('number')
    elif prop_type == 'url':
        return prop_data.get('url', '')
    elif prop_type == 'email':
        return prop_data.get('email', '')
    elif prop_type == 'phone_number':
        return prop_data.get('phone_number', '')
    elif prop_type == 'date' and prop_data.get('date'):
        return prop_data['date'].get('start', '')
    elif prop_type == 'multi_select':
        return [item.get('name', '') for item in prop_data.get('multi_select', [])]
    # Add more property types as needed
    
    return None


def normalize_discord_channel_name(channel_name: str) -> str:
    """Normalize Discord channel name by removing emojis and special characters."""
    if not isinstance(channel_name, str):
        return str(channel_name)
    
    import re
    # Remove emojis and Discord-specific separators
    normalized = re.sub(r'[^\w\s-]', '', channel_name)
    # Remove extra whitespace and normalize hyphens
    normalized = re.sub(r'\s+', '-', normalized.strip())
    # Remove leading/trailing hyphens
    normalized = normalized.strip('-')
    return normalized.lower()

def evaluate_condition(actual_value: Any, operator: str, expected_value: str) -> bool:
    """
    Evaluate a single condition against property values.
    
    Args:
        actual_value: The actual value from the property
        operator: The comparison operator (=, >, <, etc.)
        expected_value: The expected value from the filter
        
    Returns:
        True if the condition is satisfied, False otherwise
    """
    # Handle None values
    if actual_value is None:
        return False
    
    # Convert expected_value to appropriate type
    if isinstance(actual_value, bool):
        if isinstance(expected_value, bool):
            # expected_value is already a boolean, use as-is
            pass
        elif isinstance(expected_value, str) and expected_value.lower() in ['true', 'false']:
            expected_value = expected_value.lower() == 'true'
        else:
            return False
    elif isinstance(actual_value, (int, float)):
        try:
            expected_value = float(expected_value)
        except ValueError:
            return False
    elif isinstance(actual_value, list):
        # For multi-select properties, check if expected value is in the list
        if operator == '=':
            return expected_value in actual_value
        else:
            return False
    else:
        # String comparison
        actual_value = str(actual_value)
        expected_value = str(expected_value)
    
    # Apply the operator
    if operator == '=':
        # For Discord channel filtering, use exact matching to avoid "announcements" matching "plush-announcements"
        # For Gmail email filtering, support partial matching (contains)
        # This allows "from=avask" to match "someone@avask.com" 
        if isinstance(actual_value, str) and isinstance(expected_value, str):
            # Check if this is a Discord channel name filter - use exact matching
            # Note: We can't easily pass context here, so we'll check if both values look like channel names
            if (actual_value.count('-') > 0 or actual_value.count('・') > 0 or 
                expected_value.count('-') > 0 or expected_value.count('・') > 0):
                # Looks like Discord channel names - normalize and compare
                # This handles emojis and special characters: "💬・plush-and-merch-general" == "plush-and-merch-general"
                return normalize_discord_channel_name(actual_value) == normalize_discord_channel_name(expected_value)
            else:
                # Gmail-style partial matching for emails
                return expected_value.lower() in actual_value.lower()
        return actual_value == expected_value
    elif operator == 'contains':
        # Full content search for contains operator
        if isinstance(actual_value, str) and isinstance(expected_value, str):
            return expected_value.lower() in actual_value.lower()
        return False
    elif operator == '>':
        return actual_value > expected_value
    elif operator == '<':
        return actual_value < expected_value
    elif operator == '>=':
        return actual_value >= expected_value
    elif operator == '<=':
        return actual_value <= expected_value
    else:
        return False

# If this file is run directly, run the test
if __name__ == "__main__":
    import sys
    days = int(sys.argv[1]) if len(sys.argv) > 1 else 7
    test_days_filtering(days) 