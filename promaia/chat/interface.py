"""
Terminal-based chat interface for interacting with AI models.
"""
from anthropic import Anthropic
from openai import OpenAI
import os
import glob
import sys
import time
import json
import tiktoken
import random
from prompt_toolkit import PromptSession
from prompt_toolkit.styles import Style
from prompt_toolkit.history import FileHistory
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.formatted_text import HTML
import datetime
import asyncio
import traceback  # Added for detailed error tracing
import subprocess
from typing import List, Dict, Any, Optional
from rich.console import Console
from rich.table import Table
import functools # Add this import at the top or with other imports
import concurrent.futures
import shlex

from promaia.storage.files import read_markdown_files, get_existing_page_ids, read_markdown_files_from_sources
from promaia.storage.unified_reader import read_database_content
from promaia.utils.config import get_chat_days_setting, set_chat_days_setting, get_sync_days_setting, set_sync_days_setting, load_environment, get_last_sync_time, get_chat_default_sources, get_chat_default_days, is_multi_source_default_enabled # Added get_last_sync_time
from promaia.notion.pages import get_pages_by_date, get_block_content, get_page_title
from promaia.notion.client import ensure_default_client
from promaia.utils.config_loader import get_notion_database_id # Add this import
from promaia.storage.files import read_markdown_files_from_directory, read_markdown_files_by_page_ids # ADDED IMPORT
from promaia.storage.unified_storage import load_metadata_with_filters
from promaia.storage.markdown_files import get_md_output_dir_for_database # MODIFIED IMPORT
from promaia.config.workspaces import get_workspace_manager
from promaia.ai.models import ANTHROPIC_MODELS, GOOGLE_MODELS
from promaia.utils.display import print_markdown, print_text, print_separator

# Load environment variables
load_environment()

# Initialize DEBUG_MODE at the global scope
DEBUG_MODE = os.getenv("MAIA_DEBUG", "0") == "1"

# Configuration file for API preferences
API_PREFERENCE_FILE = os.path.join(os.path.expanduser("~"), ".maia_api_preference")

# Global variables for rate limiting
ANTHROPIC_RATE_LIMIT_TOKENS = 40000  # Tokens per minute for Anthropic
ANTHROPIC_LAST_REQUEST_TIME = 0
ANTHROPIC_TOKEN_USAGE = 0
ANTHROPIC_TOKEN_USAGE_RESET_TIME = 0
# Rate limiting queue system
RATE_LIMIT_QUEUE = []
RATE_LIMIT_PROCESSING = False
# Token budget - we'll aim to stay under 80% of the limit to be safe
TOKEN_BUDGET_PERCENTAGE = 0.8

# Global variable for the persistent event loop for chat-related async operations
_persistent_chat_loop = None

# Initialize rich console for better formatting with copy-friendly settings
console = Console(
    width=9999,  # Very large width to prevent wrapping
    soft_wrap=False  # Prevent automatic line wrapping for copy-friendly output
)

# Function to get saved API preference
def get_api_preference():
    """Get the saved API preference."""
    try:
        if os.path.exists(API_PREFERENCE_FILE):
            with open(API_PREFERENCE_FILE, 'r') as f:
                api_type = f.read().strip()
                if api_type in ["anthropic", "openai", "gemini"]:
                    return api_type
    except Exception as e:
        debug_print(f"Error reading API preference: {str(e)}")
    
    return "anthropic"  # Default to anthropic if no valid preference found

# Function to save API preference
def save_api_preference(api_type):
    """Save the API preference."""
    try:
        with open(API_PREFERENCE_FILE, 'w') as f:
            f.write(api_type)
        debug_print(f"API preference saved: {api_type}")
        return True
    except Exception as e:
        debug_print(f"Error saving API preference: {str(e)}")
        return False

# Initialize API clients if API keys are available
anthropic_client = None
if os.getenv("ANTHROPIC_API_KEY"):
    anthropic_client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

openai_client = None
if os.getenv("OPENAI_API_KEY"):
    openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

gemini_client = None
if os.getenv("GOOGLE_API_KEY"):
    import google.generativeai as genai
    genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
    # System instruction will be set dynamically in the chat() function before the first call
    # Don't initialize the model here - it will be created with proper system instruction in chat()

# Global variable to track which API is being used - now reads from saved preference
current_api = get_api_preference()
os.environ["API_TYPE"] = current_api  # Ensure environment variable matches saved preference

# Create a session for the prompt
session = PromptSession(history=FileHistory('.chat_history'))

# Define styles
style = Style.from_dict({
    'prompt': 'ansicyan bold',
    'input': 'ansiwhite',
    'assistant': 'ansigreen',
    'user': 'ansiblue',
})

def debug_print(message):
    """Print debug messages if debug mode is enabled."""
    # Check the environment variable directly inside the function
    if os.getenv("MAIA_DEBUG", "0") == "1":
        # Get the current time for the timestamp
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3] # Milliseconds
        # Try to get the name of the calling function for more context
        caller_name = ""
        try:
            caller_name = f" [{sys._getframe(1).f_code.co_name}]"
        except Exception:
            pass # Couldn't get caller name, proceed without it
        print(f"DEBUG ({timestamp}){caller_name}: {message}")

def load_prompt_templates():
    """Load prompt templates based on MAIA_CHAT_CONTEXT environment variable."""
    chat_context = os.getenv("MAIA_CHAT_CONTEXT", "local")
    
    if chat_context == "web":
        prompt_file_path = "prompts/KOii-chat-prompt.md"
        default_system_prompt = "You are KOii, an AI assistant. [Error: KOii-chat-prompt.md not found]"
    else: # local or default
        prompt_file_path = "prompts/prompt.md" # Updated to use prompts directory
        default_system_prompt = "You are a helpful local assistant. [Error: prompt.md not found]"

    try:
        # Ensure the path is correct, potentially relative to the project root or this file's location.
        with open(prompt_file_path, 'r', encoding='utf-8') as f:
            prompt_md_content = f.read()
        debug_print(f"Loaded {prompt_file_path} for {chat_context} context: {len(prompt_md_content)} characters")
        return {"system_prompt": prompt_md_content, "project_instructions": ""}
    except FileNotFoundError:
        print(f"ERROR: Prompt file not found at {prompt_file_path} for {chat_context} context. Please ensure it exists.")
        return {"system_prompt": default_system_prompt, "project_instructions": ""}
    except Exception as e:
        print(f"ERROR: Error loading {prompt_file_path} for {chat_context} context: {str(e)}")
        return {"system_prompt": default_system_prompt.replace("not found", "could not be loaded"), "project_instructions": ""}

def create_system_prompt(
    original_journal_pages: List[Dict[str, Any]], 
    cms_entries: List[Dict[str, Any]],
    for_api: str = "anthropic",
    multi_source_data: Optional[Dict[str, List[Dict[str, Any]]]] = None
) -> str:
    """
    Create a system prompt that includes the KOii-chat base prompt, 
    original journal entries (for local), and CMS content (for web).
    
    Args:
        original_journal_pages: List of original page data (used in local mode)
        cms_entries: List of CMS entry data (used in web mode)
        for_api: Which API to format for (currently less critical with unified approach)
        multi_source_data: Optional dictionary of source_name -> pages for multi-source mode
        
    Returns:
        Formatted system prompt
    """
    templates = load_prompt_templates() # Loads conditionally based on MAIA_CHAT_CONTEXT
    base_prompt = templates["system_prompt"]
    # debug_print(f"[create_system_prompt] Initial base_prompt (first 100 chars): {base_prompt[:100]}") # DEBUG

    today = datetime.datetime.now()
    today_str = today.strftime("%Y-%m-%d")

    # Replace {today_date} placeholder in the base_prompt
    base_prompt = base_prompt.replace("{today_date}", today_str)



    # Handle multi-source mode
    if multi_source_data:
        debug_print(f"Multi-source mode detected with {len(multi_source_data)} sources and {sum(len(pages) for pages in multi_source_data.values())} total entries")
        # Multi-source system prompt - COMPLETELY OVERRIDE base_prompt for multi-source mode
        base_prompt = f"""I am an AI assistant named Maia. Today's date is {today_str}. I have access to content from multiple data sources with different types of information. My tone is direct, casual, and very concise.

I serve as your journal, companion, and professional assistant. The purpose of this project is to support your growth to your highest potential, optimizing for holistic, long-term sustainable success as measured by:

- Financial freedom
- Professional growth
- Mental, emotional, and spiritual health
- Quality relationships

I will:
- Act as a reflective mirror to help you examine habits objectively
- Serve as a guide to identify blindspots
- Highlight opportunities for growth
- Provide feedback on areas for improvement, with sighted evidence

When referencing content, always specify which database it comes from and use the filename for context.
When discussing time periods (e.g. 'this week', 'today', 'yesterday'), use {today_str} as the reference point.

## Content from Multiple Data Sources ({sum(len(pages) for pages in multi_source_data.values())} total entries):
"""
        
        for database_name, pages in multi_source_data.items():
            base_prompt += f"\n### === {database_name.upper()} DATABASE ({len(pages)} entries) ===\n"
            
            # Add database-specific descriptions
            if 'journal' in database_name.lower():
                base_prompt += "These are personal journal entries and daily reflections:\n"
            elif 'awakenings' in database_name.lower():
                base_prompt += "These are manifestations, affirmations, and wisdom insights (not tied to specific dates):\n"
            elif 'cms' in database_name.lower():
                base_prompt += "These are blog posts and published content:\n"
            elif 'project' in database_name.lower():
                base_prompt += "These are project notes and work-related content:\n"
            elif 'stories' in database_name.lower():
                base_prompt += "These are story ideas and narrative content:\n"
            elif 'epic' in database_name.lower():
                base_prompt += "These are epic/feature planning and development notes:\n"
            else:
                base_prompt += f"These are {database_name} entries:\n"
            
            if not pages:
                base_prompt += "No entries found for this database.\n"
            else:
                for page in pages:
                    page_filename = page.get('filename', 'Unknown File')
                    page_content = page['content']
                    base_prompt += f"\n**{database_name}** entry (File: {page_filename}):\n{page_content}\n"
            
            base_prompt += f"\n### === END {database_name.upper()} DATABASE ===\n"
        
        base_prompt += f"\n\n---\nRemember: Today is {today_str}. When referencing content, clearly specify which database it comes from and what type of content it is (e.g., 'from your journal entries on [date]', 'from your awakenings collection', 'from your project notes'). Different databases contain different types of content with different relationships to time - journal entries are date-specific, while awakenings/manifestations are timeless insights you can draw from."
        

        return base_prompt

    # Original single-source logic continues here...
    debug_print(f"Single-source mode: multi_source_data is None or empty")
    chat_context = os.getenv("MAIA_CHAT_CONTEXT", "local")
    # debug_print(f"[create_system_prompt] Detected MAIA_CHAT_CONTEXT: {chat_context}") # DEBUG
    # debug_print(f"[create_system_prompt] Received {len(cms_entries)} cms_entries.") # DEBUG
    # debug_print(f"[create_system_prompt] Received {len(original_journal_pages)} original_journal_pages.") # DEBUG
    # ---- START TEMP FILE DEBUG ----
    with open(debug_log_path, "a", encoding="utf-8") as f_debug:
        f_debug.write(f"Detected MAIA_CHAT_CONTEXT: {chat_context}\n")
        f_debug.write(f"Received {len(cms_entries)} cms_entries.\n")
        f_debug.write(f"Received {len(original_journal_pages)} original_journal_pages.\n")
    # ---- END TEMP FILE DEBUG ----

    if chat_context == "web":
        # debug_print("[create_system_prompt] Entering WEB context block.") # DEBUG
        # ---- START TEMP FILE DEBUG ----
        with open(debug_log_path, "a", encoding="utf-8") as f_debug:
            f_debug.write(f"Entering WEB context block.\n")
        # ---- END TEMP FILE DEBUG ----
        # Web context: Use KOii-chat-prompt.md base + CMS content (no more sanitized journal entries)
        base_prompt += "\n\n## Context from CMS Content (Newest First):\n"
        # Web context: Add CMS entries for context
        if cms_entries:
            base_prompt += "\n\n## Available Context:\n"
            for entry in cms_entries[:10]:  # Limit to avoid bloat
                entry_title = entry.get('title', 'Untitled')
                entry_date = entry.get('date', 'No date')
                base_prompt += f"- {entry_title} ({entry_date})\n"
    else:
        # Local context: Add journal entries for context
        if original_journal_pages:
            base_prompt += "\n\n## Recent Journal Entries:\n"
            sorted_pages = sorted(original_journal_pages, key=lambda x: x.get('date_obj', datetime.datetime.min), reverse=True)
            for page in sorted_pages[:5]:  # Limit to recent entries
                page_filename = page.get('filename', 'Unknown File')
                page_date = page.get('date', today_str)
                base_prompt += f"- {page_date} ({page_filename})\n"
    
    return base_prompt

def load_cms_entries(days_to_load: Optional[int] = None) -> List[Dict[str, Any]]:
    """
    Load CMS entries from the notion-cms/ directory.
    If days_to_load is specified, filters entries to include only those from the last `days_to_load` days.
    Otherwise, loads all entries.
    Args:
        days_to_load: Optional number of past days to load entries from.
    Returns:
        A list of dictionaries, where each dictionary represents a page
        and contains 'filename', 'date', 'content', and 'date_obj'.
    """
    if days_to_load:
        debug_print(f"Loading CMS entries (content_type='cms') for the last {days_to_load} days...")
    else:
        debug_print(f"Loading all CMS entries (content_type='cms')...")
    pages_data_list = read_database_content("cms", days=days_to_load)
    loaded_count = len(pages_data_list)
    if days_to_load:
        debug_print(f"Read {loaded_count} pages using content_type='cms'. Filtering is handled by read_database_content.")
    else:
        debug_print(f"Read {loaded_count} pages using content_type='cms' (all entries).")
    return pages_data_list

def format_message(role, content):
    """Format a message without rendering markdown."""
    # Return the raw content instead of converting to Markdown
    return content

def display_message_with_timestamp(role, content):
    """
    Display a message with timestamp using copy-friendly Rich formatting.
    Avoids panels, boxes, and other formatting that breaks during copy/paste.
    """
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    
    if role == "user":
        print_text(content, style="bold blue", title=f"You ({timestamp})")
    elif role == "assistant":
        # For AI responses, use markdown rendering for better formatting
        # but in a copy-friendly way
        print_markdown(content, title=f"AI ({timestamp})")
    else:
        print_text(content, title=f"{role} ({timestamp})")
    
    print_separator()  # Simple separator instead of complex formatting

def print_welcome_message():
    """Print the welcome message for a read-only chat session."""
    print("\n" + "=" * 40)
    print("Welcome to Maia Chat! (Read-Only Mode)")
    print("\nType your message and press Enter to chat with the AI.")
    print("Available commands:")
    print("  /quit  - Exit the chat")
    print("  /debug - Toggle debug mode")
    print("  /push  - Push the current chat session to Notion")
    print("  /help  - Show this help message")
    print("")

def switch_api(target_model=None):
    # This function is no longer called from within chat,
    # but maia/cli.py model command might still use it.
    # Its internal logic for saving preference is still valid.
    global current_api
    debug_print(f"Switching API from {current_api}. Target: {target_model}")
    
    models = ["anthropic", "openai", "gemini"]
    available_models = []
    if os.getenv("ANTHROPIC_API_KEY"):
        available_models.append("anthropic")
    if os.getenv("OPENAI_API_KEY"):
        available_models.append("openai")
    if os.getenv("GOOGLE_API_KEY"):
        available_models.append("gemini")

    if not available_models:
        print("ERROR: No valid API keys found for any model.")
        print("Please set at least one of: ANTHROPIC_API_KEY, OPENAI_API_KEY, or GOOGLE_API_KEY")
        return current_api

    if target_model:
        # Normalize target_model name (claude -> anthropic)
        if target_model.lower() == "claude":
            target_model = "anthropic"
            
        if target_model in available_models:
            current_api = target_model
            os.environ["API_TYPE"] = target_model
            save_api_preference(current_api)
            if target_model == "anthropic":
                print("Switched to Anthropic (Claude)")
            elif target_model == "openai":
                print("Switched to OpenAI (GPT-4)")
            elif target_model == "gemini":
                print("Switched to Google (Gemini)")
            return current_api
        else:
            print(f"ERROR: API key for {target_model.capitalize()} not found or model not supported.")
            print(f"Available models with API keys: {[m.capitalize() for m in available_models]}")
            return current_api
    else:
        # Cycle through models
        try:
            current_index = models.index(current_api)
        except ValueError:
            # If current_api is not in models (e.g. after an error or manual config change)
            # or if it's not in available_models, start from the first available model.
             if current_api not in available_models or not available_models:
                 current_api = available_models[0] # Default to the first available if any
                 current_index = models.index(current_api) if current_api in models else -1
             else: # current_api is valid and available, find its index in the main `models` list
                 current_index = models.index(current_api)


        # Try each model in sequence until we find one with a valid API key
        # This loop ensures we cycle through all *possible* models, then check availability
        for i in range(len(models)):
            next_index_in_cycle = (current_index + i + 1) % len(models)
            next_model_in_cycle = models[next_index_in_cycle]
            
            if next_model_in_cycle in available_models:
                current_api = next_model_in_cycle
                os.environ["API_TYPE"] = current_api
                save_api_preference(current_api)
                if current_api == "anthropic":
                    print("Switched to Anthropic (Claude)")
                elif current_api == "openai":
                    print("Switched to OpenAI (GPT-4)")
                elif current_api == "gemini":
                    print("Switched to Google (Gemini)")
                return current_api
        
        # This part should ideally not be reached if available_models is not empty
        # and logic above correctly sets initial current_api to an available one.
        print("ERROR: Could not switch to a new model. Please check API key configurations.")
        return current_api

def set_days():
    """
    Set the number of days of journal entries to include in context.
    Now supports advanced options like 'all' and date ranges.
    
    Returns:
        Integer representing the new setting, or -1 for 'all' mode
    """
    try:
        current_days = get_chat_days_setting()
        print(f"Current chat context days setting: {current_days} days")
        print("\nOptions:")
        print("  - Enter a number (e.g., 30, 120)")
        print("  - Enter 'all' to load all available entries")
        print("  - Enter 'range' for date range selection")
        print("  - Press Enter to keep current setting")
        
        # Get user input for new value
        days_str = input("\nEnter days option: ").strip()
        
        if not days_str:
            print(f"Keeping current setting: {current_days} days")
            return current_days
        
        # Handle 'all' option
        if days_str.lower() == 'all':
            print("Setting chat context to load ALL available journal entries...")
            print("Note: This may take longer to load and use more memory.")
            confirm = input("Continue with loading all entries? (y/n): ").strip().lower()
            if confirm == 'y':
                # Use -1 to indicate 'all' mode
                set_chat_days_setting(9999)  # Store a very large number to approximate 'all'
                print("Chat context set to load ALL available entries.")
                return 9999
            else:
                print("Cancelled. Keeping current setting.")
                return current_days
        
        # Handle 'range' option for date range selection
        elif days_str.lower() == 'range':
            print("\nDate Range Selection:")
            print("Enter start and end dates to load specific date ranges.")
            print("Format: YYYY-MM-DD")
            
            start_date = input("Start date (YYYY-MM-DD): ").strip()
            end_date = input("End date (YYYY-MM-DD): ").strip()
            
            # Validate date formats
            try:
                start_dt = datetime.datetime.strptime(start_date, "%Y-%m-%d")
                end_dt = datetime.datetime.strptime(end_date, "%Y-%m-%d")
                
                if start_dt > end_dt:
                    print("ERROR: Start date cannot be after end date.")
                    return current_days
                
                # Calculate days between dates
                days_diff = (end_dt - start_dt).days + 1
                today = datetime.datetime.now()
                days_from_today = (today - start_dt).days
                
                print(f"Date range: {start_date} to {end_date} ({days_diff} days)")
                print(f"Starting {days_from_today} days ago from today")
                
                confirm = input("Load this date range? (y/n): ").strip().lower()
                if confirm == 'y':
                    # For simplicity, convert to days from today based on start date
                    # This is an approximation since we're still using the days-based system
                    effective_days = max(days_from_today + days_diff, 1)
                    set_chat_days_setting(effective_days)
                    print(f"Chat context set to approximately {effective_days} days to cover the selected range.")
                    return effective_days
                else:
                    print("Cancelled. Keeping current setting.")
                    return current_days
                    
            except ValueError:
                print("ERROR: Invalid date format. Use YYYY-MM-DD format.")
                return current_days
        
        # Handle numeric input
        else:
            try:
                days = int(days_str)
                if days < 1:
                    print("WARNING: Days must be at least 1. Setting to 1.")
                    days = 1
                    
                # Update the setting
                set_chat_days_setting(days)
                print(f"Updated chat context days setting: {days} days")
                
                debug_print(f"Chat context days setting updated from {current_days} to {days}")
                return days
                
            except ValueError:
                print("ERROR: Invalid input. Please enter a number, 'all', or 'range'.")
                return current_days
            
    except Exception as e:
        print(f"ERROR: Error setting days: {str(e)}")
        debug_print(f"Exception in set_days: {traceback.format_exc()}")
        return get_chat_days_setting()  # Fall back to current setting

# Utility functions for token counting and rate limit handling
def estimate_token_count(text, model="claude"):
    """
    Estimate the number of tokens in a given text.
    Using a simple approximation for Claude (4 chars = 1 token).
    For OpenAI, uses tiktoken library.
    """
    if model == "claude":
        # Simple approximation for Claude (4 characters = 1 token)
        return len(text) // 4 + 1
    elif model.startswith("gpt"):
        try:
            # Use tiktoken for OpenAI models
            encoder = tiktoken.encoding_for_model(model)
            return len(encoder.encode(text))
        except Exception as e:
            debug_print(f"Error using tiktoken: {str(e)}")
            # Fallback to simple approximation if tiktoken fails
            return len(text) // 4 + 1
    else:
        # Default approximation
        return len(text) // 4 + 1

def handle_rate_limit(response_headers=None):
    """
    Update token usage based on response headers and handle rate limits
    Returns the wait time needed before the next request (in seconds)
    """
    global ANTHROPIC_TOKEN_USAGE, ANTHROPIC_TOKEN_USAGE_RESET_TIME
    
    now = time.time()
    
    # Parse headers if provided
    if response_headers:
        # Get rate limit headers if available
        rate_limit_tokens_remaining = response_headers.get('anthropic-rate-limit-remaining', None)
        rate_limit_tokens_reset = response_headers.get('anthropic-rate-limit-reset', None)
        
        if rate_limit_tokens_remaining and rate_limit_tokens_reset:
            try:
                ANTHROPIC_TOKEN_USAGE = ANTHROPIC_RATE_LIMIT_TOKENS - int(rate_limit_tokens_remaining)
                reset_seconds = int(rate_limit_tokens_reset)
                ANTHROPIC_TOKEN_USAGE_RESET_TIME = now + reset_seconds
                debug_print(f"Rate limit info: {ANTHROPIC_TOKEN_USAGE}/{ANTHROPIC_RATE_LIMIT_TOKENS} tokens used, resets in {reset_seconds}s")
            except Exception as e:
                debug_print(f"Error parsing rate limit headers: {str(e)}")
    
    # Check if we need to wait for token reset
    if ANTHROPIC_TOKEN_USAGE_RESET_TIME > now:
        wait_time = ANTHROPIC_TOKEN_USAGE_RESET_TIME - now
        
        # Proactive rate limiting: If we're approaching the limit, throttle more aggressively
        if ANTHROPIC_TOKEN_USAGE > ANTHROPIC_RATE_LIMIT_TOKENS * TOKEN_BUDGET_PERCENTAGE:
            # Calculate what percentage of the token budget we've used
            budget_used = ANTHROPIC_TOKEN_USAGE / (ANTHROPIC_RATE_LIMIT_TOKENS * TOKEN_BUDGET_PERCENTAGE)
            
            # Scale wait time based on how close we are to the budget
            if budget_used > 0.95:  # Over 95% of our safe budget
                debug_print(f"Critical token usage ({ANTHROPIC_TOKEN_USAGE}/{ANTHROPIC_RATE_LIMIT_TOKENS}), waiting for reset: {wait_time:.1f}s")
                return wait_time  # Wait for full reset
            elif budget_used > 0.8:  # Over 80% of our safe budget
                throttle_factor = 4.0  # Aggressive throttling
                throttle_wait = wait_time / 2  # Wait half the time until reset
                debug_print(f"High token usage ({ANTHROPIC_TOKEN_USAGE}/{ANTHROPIC_RATE_LIMIT_TOKENS}), throttling: {throttle_wait:.1f}s")
                return max(throttle_wait, 3.0)  # Wait at least 3 seconds
            else:
                throttle_factor = 2.0  # Moderate throttling
                throttle_wait = wait_time / 4  # Wait quarter the time until reset
                debug_print(f"Moderate token usage ({ANTHROPIC_TOKEN_USAGE}/{ANTHROPIC_RATE_LIMIT_TOKENS}), throttling: {throttle_wait:.1f}s")
                return max(throttle_wait, 1.0)  # Wait at least 1 second
    else:
        # Reset usage if the reset time has passed
        ANTHROPIC_TOKEN_USAGE = 0
        ANTHROPIC_TOKEN_USAGE_RESET_TIME = now + 60  # Default to 1 minute if no header info
    
    # No need to wait
    return 0

async def push_chat_to_notion(messages):
    """
    Push the raw chat log to the latest journal entry in Notion.
    
    Args:
        messages: List of message objects from the chat
        
    Returns:
        Success or error message string
    """
    if not messages:
        return "No chat messages to push."
    
    try:
        print(f"Fetching the latest journal entry from Notion...") # Updated log message
        # database_id = os.getenv("NOTION_JOURNAL_DATABASE_ID") # Old way
        try:
            database_id = get_notion_database_id("journal") # New way
        except (FileNotFoundError, ValueError) as e:
            error_message = f"Error loading Notion database ID for 'journal': {e}"
            print(error_message)
            debug_print(error_message) # Assuming debug_print is available
            return f"ERROR: {error_message}"

        if not database_id: # Should be caught by get_notion_database_id, but as a safeguard
            return "ERROR: NOTION_JOURNAL_DATABASE_ID (nickname 'journal') not found in configuration."
        
        # Fetch only the single most recent page using the new get_latest parameter
        entries = await get_pages_by_date(database_id, get_latest=True, content_type="journal")
        if not entries:
            # If no pages exist at all, create one for today?
            # For now, error out if no pages are found.
            # A more robust solution might create a page for the current day if none exists.
            return "No journal entries found in the database."
        
        latest_entry = entries[0] # Since get_latest_only=True returns a list with one item (or empty)
        entry_id = latest_entry["id"]
        entry_title = await get_page_title(entry_id)
        
        print(f"Using latest journal entry: {entry_title}")
        
        # Prepare chat log for Notion blocks
        chat_blocks = []
        
        # Add a header with the date of the chat session
        chat_date = datetime.datetime.now().strftime("%Y-%m-%d")
        chat_blocks.append({
            "object": "block",
            "type": "heading_2",
            "heading_2": {
                "rich_text": [{
                    "type": "text",
                    "text": {
                        "content": f"Chat Session - {chat_date}"
                    }
                }]
            }
        })
        
        # Add a divider
        chat_blocks.append({
            "object": "block",
            "type": "divider",
            "divider": {}
        })
        
        # Format each message from the chat history
        for i, msg in enumerate(messages):
            # Use a unique timestamp for each message, incrementing by a small amount for each
            # This is a rough approximation as we don't store exact timestamps per message in the simple list
            message_time = datetime.datetime.now() - datetime.timedelta(seconds=(len(messages) - i - 1) * 5) 
            timestamp = message_time.strftime("%H:%M:%S")
            role_display = "You" if msg["role"] == "user" else "AI"
            content = msg["content"]
            
            # Add Role & Timestamp as H3
            chat_blocks.append({
                "object": "block",
                "type": "heading_3",
                "heading_3": {
                    "rich_text": [{
                        "type": "text",
                        "text": {
                            "content": f"{timestamp} | {role_display}"
                        }
                    }]
                }
            })
            
            # Add message content as paragraph(s)
            # Split content by newlines to create separate paragraph blocks in Notion for better readability
            content_paragraphs = content.split('\n')
            for para_content in content_paragraphs:
                if para_content.strip(): # Avoid creating empty paragraph blocks
                    chat_blocks.append({
                        "object": "block",
                        "type": "paragraph",
                        "paragraph": {
                            "rich_text": [{
                                "type": "text",
                                "text": {
                                    "content": para_content
                                }
                            }]
                        }
                    })
            
            # Add a small spacer (empty paragraph) between messages if not the last message
            if i < len(messages) - 1:
                chat_blocks.append({
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {"rich_text": []} # Empty rich_text for a blank line
                })

        # Get the existing blocks from the latest entry to find or create the chat toggle
        existing_page_blocks = await get_block_content(entry_id)
        
        chat_header_block_id = None
        for block in existing_page_blocks:
            # Check for both H1 toggles and regular toggle blocks containing "promaia chat"
            if block["type"] == "toggle" or (block["type"] == "heading_1" and block.get("heading_1", {}).get("is_toggleable", False)):
                rich_text_list = block.get(block["type"], {}).get("rich_text", [])
                block_text_content = "".join(text_item.get("text", {}).get("content", "") for text_item in rich_text_list)
                if "promaia chat" in block_text_content:
                    chat_header_block_id = block["id"]
                    break
        
        if chat_header_block_id:
            print("Found existing 'promaia chat' toggle section. Appending new session.")
            # Append a divider before adding the new chat session if appending to existing toggle
            notion_client = ensure_default_client()
            await notion_client.blocks.children.append(
                block_id=chat_header_block_id,
                children=[{
                    "object": "block",
                    "type": "divider",
                    "divider": {}
                }]
            )
            response = await notion_client.blocks.children.append(
                block_id=chat_header_block_id,
                children=chat_blocks
            )
        else:
            print("Creating new 'promaia chat' toggle section.")
            new_toggle_header = {
                "object": "block",
                "type": "toggle",
                "toggle": {
                    "rich_text": [{"type": "text", "text": {"content": "promaia chat"}}],
                    "color": "default"
                }
            }
            notion_client = ensure_default_client()
            append_response = await notion_client.blocks.children.append(
                block_id=entry_id,
                children=[new_toggle_header]
            )
            chat_header_block_id = append_response["results"][0]["id"]
            
            print(f"Appending chat log to new toggle section (ID: {chat_header_block_id})")
            response = await notion_client.blocks.children.append(
                block_id=chat_header_block_id,
                children=chat_blocks
            )
        
        return f"Successfully pushed chat log to '{entry_title}'"
    
    except Exception as e:
        error_details = traceback.format_exc()
        debug_print(f"Error pushing chat to Notion: {error_details}")
        return f"ERROR: Failed to push chat to Notion: {str(e)}"

def call_anthropic_with_retry(anthropic_client, system_prompt, messages, max_tokens=4096, temperature=0.7, max_retries=3):
    """
    Calls the Anthropic API with an exponential backoff retry mechanism.
    Handles rate limiting by checking the queue.
    """
    global ANTHROPIC_LAST_REQUEST_TIME, ANTHROPIC_TOKEN_USAGE, ANTHROPIC_TOKEN_USAGE_RESET_TIME
    
    # Estimate token usage
    system_tokens = estimate_token_count(system_prompt, "claude")
    message_tokens = sum(estimate_token_count(msg["content"], "claude") for msg in messages)
    estimated_tokens = system_tokens + message_tokens
    
    # Check against rate limit *before* making a request
    current_time = time.time()
    if current_time - ANTHROPIC_TOKEN_USAGE_RESET_TIME > 60:
        ANTHROPIC_TOKEN_USAGE = 0
        ANTHROPIC_TOKEN_USAGE_RESET_TIME = current_time

    if ANTHROPIC_TOKEN_USAGE + estimated_tokens > ANTHROPIC_RATE_LIMIT_TOKENS * TOKEN_BUDGET_PERCENTAGE:
        # Simplified: just wait. A more robust solution would queue requests.
        wait_time = 60 - (current_time - ANTHROPIC_TOKEN_USAGE_RESET_TIME)
        debug_print(f"Approaching Anthropic token limit. Waiting for {wait_time:.2f} seconds...")
        time.sleep(wait_time)
        # Reset after waiting
        ANTHROPIC_TOKEN_USAGE = 0
        ANTHROPIC_TOKEN_USAGE_RESET_TIME = time.time()

    attempt = 0
    while attempt < max_retries:
        try:
            response = anthropic_client.messages.create(
                model=ANTHROPIC_MODELS.get("sonnet", "claude-sonnet-4-20250514"), # Use Sonnet by default
                max_tokens=max_tokens,
                system=system_prompt,
                messages=messages,
                temperature=temperature,
            )
            
            # Update token usage based on actual response
            usage = response.usage
            input_tokens = usage.input_tokens
            output_tokens = usage.output_tokens
            total_tokens = input_tokens + output_tokens
            ANTHROPIC_TOKEN_USAGE += total_tokens # Add to our tracked usage
            debug_print(f"Anthropic API call successful. Tokens used (Input: {input_tokens}, Output: {output_tokens}). Total in window: {ANTHROPIC_TOKEN_USAGE}")

            # Extract assistant message
            assistant_message = ""
            if response.content:
                for block in response.content:
                    if block.type == "text":
                        assistant_message += block.text
            
            response_tokens = estimate_token_count(assistant_message, "claude") # Approximate
            return assistant_message, response_tokens

        except Exception as e:
            error_details = str(e)
            if "rate_limit_error" in error_details or "429" in error_details:
                # Rate limit hit - use exponential backoff with jitter
                wait_seconds = (2 ** attempt) + random.uniform(0, 1)
                
                # Extract the reset time if possible
                try:
                    # Try to extract rate limit reset time from error message
                    if hasattr(e, 'response') and hasattr(e.response, 'headers'):
                        handle_rate_limit(e.response.headers)
                except Exception:
                    pass
                
                # Increase wait time if close to a minute boundary
                seconds_to_next_minute = 60 - (time.time() % 60)
                if seconds_to_next_minute < 10:
                    wait_seconds += seconds_to_next_minute
                
                if attempt < max_retries - 1:
                    print(f"Rate limit reached. Waiting {wait_seconds:.1f} seconds before retry {attempt+1}/{max_retries}...")
                    time.sleep(wait_seconds)
                else:
                    raise Exception(f"Rate limit reached and max retries ({max_retries}) exceeded. Please try again later.")
            else:
                # For non-rate limit errors, just raise the exception
                raise
    
    # If we get here, all retries failed
    raise Exception(f"Failed to get response after {max_retries} retries")

def run_non_interactive_chat(messages: List[Dict[str, Any]], system_prompt: str, for_api: str):
    """
    Handles the chat loop for non-interactive sessions (e.g., desktop app).
    Reads from stdin and prints responses to stdout.
    """
    import sys
    debug_print("Starting non-interactive chat loop.")

    while True:
        try:
            line = sys.stdin.readline()
            if not line:
                debug_print("No more input, ending chat loop.")
                break # End of stream
            
            user_input = line.strip()
            if not user_input:
                continue

            debug_print(f"Received non-interactive input: {user_input}")
            messages.append({"role": "user", "content": user_input})
            
            # Call the appropriate API and get the complete response
            assistant_message = ""
            
            if for_api == 'anthropic':
                if not anthropic_client:
                    print("ERROR: Anthropic API key not found.", file=sys.stderr, flush=True)
                    continue
                    
                try:
                    assistant_message, _ = call_anthropic_with_retry(
                        anthropic_client=anthropic_client,
                        system_prompt=system_prompt,
                        messages=messages,
                        max_tokens=4096,
                        temperature=0.7,
                        max_retries=3
                    )
                except Exception as e:
                    print(f"ERROR: Anthropic API call failed: {str(e)}", file=sys.stderr, flush=True)
                    continue
                    
            elif for_api == 'gemini':
                if not gemini_client:
                    print("ERROR: Gemini client not initialized.", file=sys.stderr, flush=True)
                    continue
                    
                try:
                    # Convert messages to Gemini format
                    gemini_messages = []
                    for msg in messages:
                        if msg["role"] in ["user", "assistant"]:
                            gemini_messages.append({
                                "role": "user" if msg["role"] == "user" else "model",
                                "parts": [msg["content"]]
                            })
                    
                    response = gemini_client.generate_content(
                        contents=gemini_messages,
                        generation_config={"temperature": 0.7, "max_output_tokens": 4096}
                    )
                    
                    if hasattr(response, 'text') and response.text:
                        assistant_message = response.text
                    else:
                        print("ERROR: Gemini returned empty response.", file=sys.stderr, flush=True)
                        continue
                        
                except Exception as e:
                    print(f"ERROR: Gemini API call failed: {str(e)}", file=sys.stderr, flush=True)
                    continue
                    
            else:  # OpenAI
                if not openai_client:
                    print("ERROR: OpenAI API key not found.", file=sys.stderr, flush=True)
                    continue
                    
                try:
                    response = openai_client.chat.completions.create(
                        model="gpt-4",
                        messages=[{"role": "system", "content": system_prompt}] + messages,
                        max_tokens=4096,
                        temperature=0.7
                    )
                    assistant_message = response.choices[0].message.content
                except Exception as e:
                    print(f"ERROR: OpenAI API call failed: {str(e)}", file=sys.stderr, flush=True)
                    continue
            
            # Print the response and add to messages
            if assistant_message:
                print(assistant_message, flush=True)
                messages.append({"role": "assistant", "content": assistant_message})
            
        except Exception as e:
            debug_print(f"ERROR in chat loop: {str(e)}")
            print(f"ERROR in chat loop: {str(e)}", file=sys.stderr, flush=True)

def apply_comparison_filters(pages: List[Dict[str, Any]], comparison_filters: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Apply comparison filters (like date ranges) to already-loaded pages.
    
    Args:
        pages: List of page dictionaries from markdown files
        comparison_filters: Dict of comparison filters like {'created_time_after': ['2025-02-01', '2025-03-01'], 'created_time_before': ['2025-02-28', '2025-03-31']}
    
    Returns:
        Filtered list of pages
    """
    from datetime import datetime
    import re
    
    if not comparison_filters:
        return pages
    
    # Group filters by property name and pair them correctly
    date_ranges = []
    single_filters = {}
    
    # Find all unique property names
    prop_names = set()
    for filter_key in comparison_filters.keys():
        if filter_key.endswith('_after'):
            prop_names.add(filter_key.replace('_after', ''))
        elif filter_key.endswith('_before'):
            prop_names.add(filter_key.replace('_before', ''))
    
    # For each property, pair after/before filters by index
    for prop_name in prop_names:
        after_key = f"{prop_name}_after"
        before_key = f"{prop_name}_before"
        
        after_values = comparison_filters.get(after_key, [])
        before_values = comparison_filters.get(before_key, [])
        
        # Handle both single values and lists
        if not isinstance(after_values, list):
            after_values = [after_values] if after_values else []
        if not isinstance(before_values, list):
            before_values = [before_values] if before_values else []
        
        # Pair filters by index to create date ranges
        max_pairs = max(len(after_values), len(before_values))
        for i in range(max_pairs):
            after_value = after_values[i] if i < len(after_values) else None
            before_value = before_values[i] if i < len(before_values) else None
            
            if after_value and before_value:
                # Complete date range
                date_ranges.append({
                    'prop_name': prop_name,
                    'after': after_value,
                    'before': before_value
                })
            elif after_value:
                # Only after filter
                single_filters[f"{prop_name}_after"] = after_value
            elif before_value:
                # Only before filter
                single_filters[f"{prop_name}_before"] = before_value
    
    # Use OR logic for multiple date ranges
    use_or_logic = len(date_ranges) > 1 or len(single_filters) > 0
    
    filtered_pages = []
    
    for page in pages:
        include_page = False
        
        # Check date ranges (always OR logic for multiple ranges)
        if date_ranges:
            for date_range in date_ranges:
                prop_name = date_range['prop_name']
                after_value = date_range['after']
                before_value = date_range['before']
                
                # Check if page is within this date range
                after_match = check_date_filter(page, prop_name, after_value, 'after')
                before_match = check_date_filter(page, prop_name, before_value, 'before')
                
                if after_match and before_match:
                    include_page = True
                    break  # Found one matching range, that's enough
        
        # Check single filters
        if not include_page and single_filters:
            if use_or_logic:
                # OR logic: include if matches any single filter
                for filter_key, filter_value in single_filters.items():
                    page_matches_filter = False
                    
                    if filter_key.endswith('_after'):
                        prop_name = filter_key.replace('_after', '')
                        page_matches_filter = check_date_filter(page, prop_name, filter_value, 'after')
                    elif filter_key.endswith('_before'):
                        prop_name = filter_key.replace('_before', '')
                        page_matches_filter = check_date_filter(page, prop_name, filter_value, 'before')
                    
                    if page_matches_filter:
                        include_page = True
                        break
            else:
                # AND logic: include only if matches all single filters
                include_page = True
                for filter_key, filter_value in single_filters.items():
                    page_matches_filter = False
                    
                    if filter_key.endswith('_after'):
                        prop_name = filter_key.replace('_after', '')
                        page_matches_filter = check_date_filter(page, prop_name, filter_value, 'after')
                    elif filter_key.endswith('_before'):
                        prop_name = filter_key.replace('_before', '')
                        page_matches_filter = check_date_filter(page, prop_name, filter_value, 'before')
                    
                    if not page_matches_filter:
                        include_page = False
                        break
        
        # If no date ranges and no single filters matched, exclude
        if not date_ranges and not single_filters:
            include_page = True  # No filters means include everything
        
        if include_page:
            filtered_pages.append(page)
    
    logic_type = "OR" if use_or_logic else "AND"
    debug_print(f"Applied comparison filters ({logic_type} logic): {len(date_ranges)} date ranges, {len(single_filters)} single filters -> {len(pages)} -> {len(filtered_pages)} pages")
    return filtered_pages


def check_date_filter(page: Dict[str, Any], prop_name: str, filter_value: str, comparison_type: str) -> bool:
    """
    Check if a page matches a specific date filter.
    
    Args:
        page: Page dictionary
        prop_name: Property name (e.g., 'created_time')
        filter_value: Filter value (e.g., '2025-03-01')
        comparison_type: 'after' or 'before'
    
    Returns:
        True if page matches the filter, False otherwise
    """
    from datetime import datetime
    import re
    
    try:
        filter_date = datetime.strptime(filter_value, '%Y-%m-%d')
        page_date = None
        
        # Try to get date from various sources in the page data
        if 'date_obj' in page:
            page_date = page['date_obj']
        elif 'date' in page:
            if isinstance(page['date'], str):
                try:
                    page_date = datetime.strptime(page['date'], '%Y-%m-%d')
                except ValueError:
                    return False
            elif hasattr(page['date'], 'date'):
                page_date = page['date']
        elif 'created_time' in page:
            if isinstance(page['created_time'], str):
                try:
                    page_date = datetime.fromisoformat(page['created_time'].replace('Z', '+00:00'))
                except ValueError:
                    return False
        
        if page_date is None:
            # Try to extract date from filename if available
            filename = page.get('filename', '')
            date_match = re.search(r'(\d{4}-\d{2}-\d{2})', filename)
            if date_match:
                try:
                    page_date = datetime.strptime(date_match.group(1), '%Y-%m-%d')
                except ValueError:
                    return False
        
        if page_date:
            if comparison_type == 'after':
                return page_date.date() >= filter_date.date()
            elif comparison_type == 'before':
                return page_date.date() <= filter_date.date()
        
        return False
        
    except ValueError:
        debug_print(f"Invalid date format in filter {prop_name}_{comparison_type}: {filter_value}")
        return False


def chat(sources=None, filters=None, workspace=None, non_interactive=False):
    """
    Main chat function.
    
    Args:
        sources (list, optional): List of source strings like 'journal:7'.
        filters (dict, optional): Dictionary of filters for filtering pages.
        workspace (str, optional): The workspace to use.
        non_interactive (bool): If True, run in a mode suitable for IPC.
    """
    global ANTHROPIC_TOKEN_USAGE, ANTHROPIC_TOKEN_USAGE_RESET_TIME, current_api, gemini_client, DEBUG_MODE

    # System prompts are generated once and are static for the session.
    anthropic_system_prompt = ""
    non_anthropic_system_prompt = ""

    ANTHROPIC_TOKEN_USAGE = 0
    ANTHROPIC_TOKEN_USAGE_RESET_TIME = time.time() + 60
    print("Rate limit management enabled.")

    # Get workspace info
    workspace_manager = get_workspace_manager()
    
    # Use provided workspace or default
    if not workspace:
        workspace = workspace_manager.get_default_workspace()
    
    if not workspace:
        print("ERROR: No workspace available. Please configure a workspace first.")
        return

    # Process filters and combine them with sources
    if filters and sources:
        # Combine filters with sources - apply filters to all sources
        enhanced_sources = []
        has_comparison_filters = False
        
        # Check if any filters are comparison filters (date ranges)
        for filter_expr in filters:
            if '>' in filter_expr or '<' in filter_expr:
                has_comparison_filters = True
                break
        
        for source in sources:
            enhanced_source = source
            
            # If we have comparison filters and the source doesn't specify a day count,
            # automatically append ':all' to ensure we load enough data for date filtering
            if has_comparison_filters and ':' not in source:
                enhanced_source = source + ':all'
                debug_print(f"Auto-expanded '{source}' to '{enhanced_source}' due to date filters")
            
            for filter_expr in filters:
                try:
                    # Import the helper function and convert the filter to the format expected by parse_source_specs
                    from promaia.cli.database_commands import parse_filter_expression
                    converted_filter = parse_filter_expression(filter_expr)
                    
                    # Check if this is a complex expression
                    if converted_filter.startswith("__COMPLEX_EXPR__"):
                        # For complex expressions, we need to handle them specially
                        # Store the original expression for later parsing
                        enhanced_source = enhanced_source + "." + converted_filter
                    else:
                        # Simple expression, use existing logic
                        enhanced_source = enhanced_source + "." + converted_filter
                except ValueError as e:
                    print(f"ERROR: {e}")
                    return
                except Exception as e:
                    print(f"ERROR: Failed to process filter '{filter_expr}': {e}")
                    return
            enhanced_sources.append(enhanced_source)
        sources = enhanced_sources
        debug_print(f"Enhanced sources with filters: {sources}")
    elif filters and not sources:
        print("ERROR: --filter/-f requires at least one --source/-s to be specified.")
        print("Example: maia chat -s journal -f 'created_time>2025-03-01'")
        return

    # Initial context setup (static for the session)
    is_multi_source_session = False
    initial_multi_source_data = {} # Initialize here

    if sources: 
        from promaia.cli.database_commands import parse_source_specs
        try:
            parsed_sources_init = parse_source_specs(sources)
        except Exception as e:
            print(f"Warning: Error parsing source specifications: {e}")
            parsed_sources_init = []
        
        if parsed_sources_init:
            is_multi_source_session = True
            print("\n" + "=" * 40)
            print("Welcome to Maia Chat! (Multi-Source Mode)")
            print("Context for this session:")
            print(f"  Workspace: {workspace}")
            print(f"  API Model: {current_api.capitalize()}")
            print("  Sources:")
            for source_conf in parsed_sources_init:
                days_display = "all" if source_conf['days'] is None else f"{source_conf['days']} days"
                print(f"    - {source_conf['database']}: {days_display}")
            last_sync = get_last_sync_time()
            sync_time_display = last_sync.strftime("%Y-%m-%d %H:%M:%S") if isinstance(last_sync, datetime.datetime) else "Never"
            print(f"  Last global sync: {sync_time_display}")
            print("Available commands: /quit, /debug, /push, /help")
            print("=" * 40 + "\n")
            
            # MODIFIED: Load multi-source data from derived Markdown files
            # initial_multi_source_data = {} # Moved initialization up
            for source_conf in parsed_sources_init:
                db_name = source_conf['database']
                days_to_load_for_db = source_conf['days']
                
                # Use workspace-qualified database name if not already qualified
                if '.' not in db_name:
                    qualified_db_name = f"{workspace}.{db_name}"
                else:
                    qualified_db_name = db_name
                
                md_dir = get_md_output_dir_for_database(qualified_db_name) # Get workspace-aware path
                debug_print(f"Loading data for explicit source: {qualified_db_name} from {md_dir}, days: {days_to_load_for_db}")
                
                actual_days_param = None if days_to_load_for_db is None or days_to_load_for_db == 'all' else days_to_load_for_db
                
                # Check if we have property filters - if so, use hybrid JSON+MD approach
                property_filters = source_conf.get('property_filters', {})
                comparison_filters = source_conf.get('comparison_filters', {})
                complex_filter = source_conf.get('complex_filter', None)  # New: get complex filter
                
                if property_filters:
                    debug_print(f"Property filters detected for {qualified_db_name}: {property_filters}")
                    # First, get page IDs that match the property filters from JSON files
                    matching_page_ids = load_metadata_with_filters(property_filters)
                    debug_print(f"Found {len(matching_page_ids)} pages matching property filters")
                    # Then load only the corresponding markdown files
                    pages_from_markdown = read_markdown_files_by_page_ids(matching_page_ids, md_dir, actual_days_param)
                else:
                    # No property filters, try database registry first, fallback to directory loading
                    from promaia.config.databases import get_database_manager
                    from promaia.storage.files import read_markdown_files_with_registry
                    
                    db_manager = get_database_manager()
                    db_config = db_manager.get_database(db_name)
                    
                    if db_config:
                        debug_print(f"Using database registry for {qualified_db_name}")
                        if complex_filter:
                            debug_print(f"Complex filter detected: {complex_filter}")
                        pages_from_markdown = read_markdown_files_with_registry(
                            db_config, 
                            days=actual_days_param,
                            comparison_filters=comparison_filters,
                            complex_filter=complex_filter
                        )
                    else:
                        debug_print(f"No database config found for {qualified_db_name}, using directory method")
                        pages_from_markdown = read_markdown_files_from_directory(md_dir, days=actual_days_param)
                
                initial_multi_source_data[db_name] = pages_from_markdown
                debug_print(f"Loaded {len(pages_from_markdown)} MD entries for explicit source: {qualified_db_name}")

            total_entries = sum(len(pages) for pages in initial_multi_source_data.values())
            print(f"Loading {total_entries} total entries from specified sources...")
            
            anthropic_system_prompt = create_system_prompt([], [], "anthropic", multi_source_data=initial_multi_source_data)
            non_anthropic_system_prompt = create_system_prompt([], [], "openai", multi_source_data=initial_multi_source_data)
            print(f"System prompt generated for multi-source context.")
        else:
            print("No valid --source arguments provided. Falling back to default single-source mode.")
            # Let is_multi_source_session remain False
            sources = None # Ensure single-source logic is triggered if parsing failed

    # Default loading from database registry if no explicit --source or if --source parsing failed
    if not sources and not initial_multi_source_data: # Only if not already populated by --source
        # Check if multi-source mode is enabled by default in config
        use_multi_source_default = is_multi_source_default_enabled()
        
        if use_multi_source_default:
            debug_print(f"Multi-source default mode enabled. Loading all databases for workspace '{workspace}' from database registry.")
            
            # Use database manager to get all databases for this workspace
            from promaia.config.databases import get_database_manager
            from promaia.storage.files import read_markdown_files_with_registry
            
            db_manager = get_database_manager()
            workspace_databases = db_manager.get_workspace_databases(workspace)
            
            if workspace_databases:
                is_multi_source_session = True # Treat as multi-source if we find anything
                days_to_load_default = get_chat_default_days() # Use new chat config
                actual_days_param_default = None if days_to_load_default == 'all' or days_to_load_default >= 9999 else days_to_load_default

                print("\n" + "=" * 40)
                print("Welcome to Maia Chat! (Multi-Source Default Mode)")
                print(f"Context for this session (loaded from database registry):")
                print(f"  Workspace: {workspace}")
                print(f"  API Model: {current_api.capitalize()}")
                print(f"  Default Days Loaded: {days_to_load_default}")
                print("  Sources (from registered databases):")

                for db_config in workspace_databases:
                    debug_print(f"Loading Markdown data for registered database: {db_config.name} from {db_config.markdown_directory}, days: {actual_days_param_default}")
                    
                    try:
                        pages_from_markdown = read_markdown_files_with_registry(db_config, days=actual_days_param_default)
                        # Use the database nickname for the key in initial_multi_source_data
                        initial_multi_source_data[db_config.nickname] = pages_from_markdown
                        print(f"    - {db_config.nickname} ({db_config.source_type}): {len(pages_from_markdown)} entries loaded.")
                        debug_print(f"Loaded {len(pages_from_markdown)} MD entries for registered database: {db_config.name}")
                    except Exception as e:
                        debug_print(f"Error loading data for database {db_config.name}: {e}")
                        initial_multi_source_data[db_config.nickname] = []
                        print(f"    - {db_config.nickname} ({db_config.source_type}): 0 entries (error: {e})")
                
                last_sync = get_last_sync_time()
                sync_time_display = last_sync.strftime("%Y-%m-%d %H:%M:%S") if isinstance(last_sync, datetime.datetime) else "Never"
                print(f"  Last global sync: {sync_time_display}")
                print("Available commands: /quit, /debug, /push, /help")
                print("=" * 40 + "\n")

            else:
                debug_print(f"No databases found for workspace '{workspace}' in database registry.")
        else:
            # Use simplified default mode - only load configured default sources
            debug_print(f"Simplified default mode enabled. Loading only default sources for workspace '{workspace}'.")
            
            default_sources = get_chat_default_sources()
            days_to_load_default = get_chat_default_days()
            actual_days_param_default = None if days_to_load_default == 'all' or days_to_load_default >= 9999 else days_to_load_default
            
            # Use database manager to get specific databases
            from promaia.config.databases import get_database_manager
            from promaia.storage.files import read_markdown_files_with_registry
            
            db_manager = get_database_manager()
            
            print("\n" + "=" * 40)
            print("Welcome to Maia Chat! (Simplified Default Mode)")
            print(f"Context for this session:")
            print(f"  Workspace: {workspace}")
            print(f"  API Model: {current_api.capitalize()}")
            print(f"  Default Days Loaded: {days_to_load_default}")
            print(f"  Default Sources: {', '.join(default_sources)}")
            print("  Loaded sources:")
            
            sources_loaded = False
            for source_nickname in default_sources:
                # Try to find the database config for this source
                workspace_databases = db_manager.get_workspace_databases(workspace)
                matching_db = None
                for db_config in workspace_databases:
                    if db_config.nickname == source_nickname:
                        matching_db = db_config
                        break
                
                if matching_db:
                    try:
                        pages_from_markdown = read_markdown_files_with_registry(matching_db, days=actual_days_param_default)
                        initial_multi_source_data[matching_db.nickname] = pages_from_markdown
                        print(f"    - {matching_db.nickname} ({matching_db.source_type}): {len(pages_from_markdown)} entries loaded.")
                        debug_print(f"Loaded {len(pages_from_markdown)} MD entries for default source: {matching_db.name}")
                        sources_loaded = True
                        is_multi_source_session = True # Use multi-source mode even for single source for consistency
                    except Exception as e:
                        debug_print(f"Error loading data for database {matching_db.name}: {e}")
                        initial_multi_source_data[matching_db.nickname] = []
                        print(f"    - {matching_db.nickname} ({matching_db.source_type}): 0 entries (error: {e})")
                else:
                    debug_print(f"Warning: Default source '{source_nickname}' not found in workspace '{workspace}' databases.")
                    print(f"    - {source_nickname}: not found in workspace")
            
            if sources_loaded:
                last_sync = get_last_sync_time()
                sync_time_display = last_sync.strftime("%Y-%m-%d %H:%M:%S") if isinstance(last_sync, datetime.datetime) else "Never"
                print(f"  Last global sync: {sync_time_display}")
                print("Available commands: /quit, /debug, /push, /help")
                print(f"  To load all sources: maia chat --source all")
                print("=" * 40 + "\n")
            else:
                debug_print(f"No default sources could be loaded for workspace '{workspace}'.")

    # After --source processing OR default loading, generate prompts if we have multi_source data
    if initial_multi_source_data: # Check if any data was loaded either way
        is_multi_source_session = True # Ensure this is true if data was loaded
        total_entries = sum(len(pages) for pages in initial_multi_source_data.values())
        print(f"Loading {total_entries} total entries from specified/discovered sources...")
        
        anthropic_system_prompt = create_system_prompt([], [], "anthropic", multi_source_data=initial_multi_source_data)
        non_anthropic_system_prompt = create_system_prompt([], [], "openai", multi_source_data=initial_multi_source_data) # Gemini uses this too
        
        print(f"System prompt generated for multi-source context ({len(initial_multi_source_data)} sources).")

    elif not is_multi_source_session: # Fallback to original single-source if nothing from multi-source logic
        days_to_load = get_chat_default_days()  # Use new config setting
        chat_context_mode = os.getenv("MAIA_CHAT_CONTEXT", "local")
        
        print("\n" + "=" * 40)
        print("Welcome to Maia Chat! (Legacy Single-Source Mode)")
        print("Context for this session:")
        print(f"  Workspace: {workspace}")
        print(f"  API Model: {current_api.capitalize()}")
        print(f"  Mode: {chat_context_mode}")
        print(f"  Journal Days Loaded: {days_to_load}")
        last_sync = get_last_sync_time()
        sync_time_display = last_sync.strftime("%Y-%m-%d %H:%M:%S") if isinstance(last_sync, datetime.datetime) else "Never"
        print(f"  Last journal sync: {sync_time_display}")
        print("Available commands: /quit, /debug, /push, /help")
        print("  Note: This is legacy mode. Configure databases in promaia.config.json for better experience.")
        print("=" * 40 + "\n")

        print(f"Loading data for single-source mode (Workspace: {workspace}, Context: {chat_context_mode}, Days: {days_to_load})...")
        original_journal_pages = []
        cms_content = []
        if chat_context_mode == "web":
            cms_content = load_cms_entries(days_to_load)
        else: 
            original_journal_pages = read_markdown_files(days=days_to_load, target_data_source="private")
        
        anthropic_system_prompt = create_system_prompt(original_journal_pages, cms_content, "anthropic")
        non_anthropic_system_prompt = create_system_prompt(original_journal_pages, cms_content, "openai")
        print(f"System prompt generated for {chat_context_mode} context.")

    # Save initial system prompts to debug directory (useful for verifying static prompt)
    try:
        os.makedirs("debug", exist_ok=True)
        timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        # Determine which prompt is active based on current_api (set before chat starts)
        active_initial_prompt = anthropic_system_prompt if current_api == "anthropic" else non_anthropic_system_prompt
        # Gemini uses non_anthropic_system_prompt for its system_instruction
        if current_api == "gemini":
             # Initialize Gemini client with system instruction here, once.
            debug_print(f"Initializing Gemini client with static system prompt (hash: {hash(active_initial_prompt)}).")
            
            gemini_client = genai.GenerativeModel(
                model_name=GOOGLE_MODELS.get("pro", "gemini-2.5-pro-preview-05-06"), # Use Pro by default
                system_instruction=active_initial_prompt,
                safety_settings={
                    'HARM_CATEGORY_HARASSMENT': 'block_none',
                    'HARM_CATEGORY_HATE_SPEECH': 'block_none',
                    'HARM_CATEGORY_SEXUALLY_EXPLICIT': 'block_none',
                    'HARM_CATEGORY_DANGEROUS_CONTENT': 'block_none'
                }
            )
            gemini_client.__maia_system_prompt_set_hash__ = hash(active_initial_prompt)


        with open(f"debug/{timestamp}_session_init_prompt.txt", "w", encoding="utf-8") as f:
            f.write(active_initial_prompt)
        debug_print(f"Saved initial system prompt for session to debug/{timestamp}_session_init_prompt.txt")
    except Exception as e:
        debug_print(f"Error saving initial system prompt for session: {str(e)}")

    print("---\n") 

    messages = []

    if non_interactive:
        # Let the app know the backend is ready
        print("---MAIA_BACKEND_READY---", flush=True)
        # Choose the correct system prompt based on current API
        active_system_prompt = anthropic_system_prompt if current_api == "anthropic" else non_anthropic_system_prompt
        run_non_interactive_chat(messages, active_system_prompt, current_api)
        return # Exit after the loop

    while True:
        try:
            user_input = session.prompt(HTML('<style fg="green">You: </style>')).strip()

            if user_input.lower().startswith('/'):
                command_parts = user_input.lower().split()
                command = command_parts[0]
                args = command_parts[1:]  # Re-enable command arguments parsing

                if command == '/exit' or command == '/quit':
                    print("Goodbye!")
                    break
                # Removed /clear, /switch, /days, /pull and API specific switches
                elif command == '/help':
                    print_welcome_message() # Shows simplified command list
                    # Display current static context again for clarity with /help
                    if is_multi_source_session and parsed_sources_init: # Check parsed_sources_init exists
                        print("Current session context (Multi-Source):")
                        print(f"  API Model: {current_api.capitalize()}")
                        print("  Sources:")
                        for src_cfg in parsed_sources_init: print(f"    - {src_cfg['database']}: {src_cfg['days']} days")
                    elif not is_multi_source_session:
                        print("Current session context (Single-Source):")
                        print(f"  API Model: {current_api.capitalize()}")
                        print(f"  Mode: {os.getenv('MAIA_CHAT_CONTEXT', 'local')}")
                        print(f"  Journal Days Loaded: {get_chat_days_setting()}")
                    print("---\n")
                    continue
                elif command == '/debug':
                    DEBUG_MODE = not DEBUG_MODE
                    os.environ["MAIA_DEBUG"] = "1" if DEBUG_MODE else "0"
                    print(f"Debug mode {'enabled' if DEBUG_MODE else 'disabled'}. Other modules might need a restart or use this env var.")
                    print("---")
                    continue
                elif command == '/push':
                    debug_print("Running push command")
                    print("Starting push to Notion...")
                    if not messages:
                        print("No chat messages to push. Have a conversation first!")
                        print("---\n")
                        continue
                    try:
                        result_push = asyncio.run(push_chat_to_notion(messages))
                        print(result_push)
                        if "Successfully" in result_push:
                            clear_input = input("Chat pushed successfully. Clear chat history? (y/n): ").strip().lower()
                            if clear_input == 'y':
                                messages = [] # Keep ability to clear after a successful push
                                print("Chat history cleared post-push.")
                    except Exception as e_push_outer:
                        error_details = traceback.format_exc()
                        print(f"ERROR: Failed to push chat to Notion: {str(e_push_outer)}")
                        debug_print(f"Error details:\n{error_details}")
                    print("---\n")
                    continue
                else:
                    print(f"Unknown command: {user_input}")
                    print("Available commands: /quit, /debug, /push, /help")
                    print("For page editing and data management, use: python -m maia edit <command>")
                    print("---\n")
                    continue

            messages.append({"role": "user", "content": user_input})
            active_system_prompt = ""
            if current_api == "anthropic":
                if not anthropic_client:
                    print("ERROR: Anthropic API key not found. Please set ANTHROPIC_API_KEY.")
                    continue
                active_system_prompt = anthropic_system_prompt
            elif current_api == "gemini":
                if not gemini_client: # Should have been initialized if GOOGLE_API_KEY exists
                    print("ERROR: Google API key not found or Gemini client not initialized. Please set GOOGLE_API_KEY.")
                    continue
                # The system prompt for Gemini is set at initialization (see above)
                active_system_prompt = non_anthropic_system_prompt # This is what was used for Gemini init
            else:  # OpenAI
                if not openai_client:
                    print("ERROR: OpenAI API key not found. Please set OPENAI_API_KEY.")
                    continue
                active_system_prompt = non_anthropic_system_prompt
            
            debug_print(f"Using API: {current_api.capitalize()}. System prompt hash: {hash(active_system_prompt)}")

            if current_api == "anthropic":
                try:
                    assistant_message, response_tokens = call_anthropic_with_retry(
                        anthropic_client=anthropic_client,
                        system_prompt=active_system_prompt,
                        messages=messages,
                        max_tokens=4096,
                        temperature=0.7,
                        max_retries=3
                    )
                except Exception as e:
                    # ... error handling ...
                    print(f"ERROR: Error calling Anthropic API: {str(e)}")
                    debug_print(f"Anthropic API error details:\n{traceback.format_exc()}")
                    continue
            elif current_api == "gemini":
                try:
                    gemini_messages = []
                    for msg in messages:
                        if msg["role"] in ["user", "assistant"]:
                            gemini_messages.append({
                                "role": "user" if msg["role"] == "user" else "model",
                                "parts": [msg["content"]]
                            })
                    
                    # Gemini client is now initialized with system_instruction at the start of chat()
                    # No need to re-initialize or check hash here repeatedly.

                    response = gemini_client.generate_content(
                        contents=gemini_messages,
                        generation_config={"temperature": 0.7, "max_output_tokens": 4096}
                    )
                    
                    # Check if response is valid before accessing .text
                    if hasattr(response, 'candidates') and response.candidates:
                        candidate = response.candidates[0]
                        if hasattr(candidate, 'finish_reason'):
                            if candidate.finish_reason == 2:  # MAX_TOKENS
                                print("ERROR: Context too large for Gemini. Please reduce the number of sources or days.")
                                print("Try: maia chat --source trass.journal:7 --source trass.stories:10")
                                continue
                            elif candidate.finish_reason == 3:  # SAFETY
                                print("ERROR: Gemini safety filters blocked the content. Try rephrasing your question.")
                                continue
                            elif candidate.finish_reason == 4:  # RECITATION
                                print("ERROR: Gemini blocked response due to potential recitation. Try a different question.")
                                continue
                    
                    # Try to get the text response
                    if hasattr(response, 'text') and response.text:
                        assistant_message = response.text
                    elif hasattr(response, 'candidates') and response.candidates and hasattr(response.candidates[0], 'content'):
                        # Fallback: try to extract text from candidate content
                        candidate_content = response.candidates[0].content
                        if hasattr(candidate_content, 'parts') and candidate_content.parts:
                            assistant_message = candidate_content.parts[0].text
                        else:
                            print("ERROR: Gemini returned empty response. Try reducing context size or rephrasing.")
                            continue
                    else:
                        print("ERROR: Gemini returned invalid response format. Try reducing context size.")
                        continue
                    
                    # Extract and display token usage information
                    if hasattr(response, 'usage_metadata') and response.usage_metadata:
                        usage = response.usage_metadata
                        prompt_tokens = getattr(usage, 'prompt_token_count', 0)
                        response_tokens = getattr(usage, 'candidates_token_count', 0)
                        total_tokens = getattr(usage, 'total_token_count', 0)
                        
                        print(f"\n💭 Token Usage: {prompt_tokens:,} prompt + {response_tokens:,} response = {total_tokens:,} total")
                    else:
                        debug_print("No usage_metadata found in Gemini response")
                        
                except Exception as e:
                    # ... error handling ...
                    print(f"ERROR: Error calling Gemini API: {str(e)}")
                    debug_print(f"Gemini API error details:\n{traceback.format_exc()}")
                    continue
            else:  # OpenAI
                try:
                    response = openai_client.chat.completions.create(
                        model="gpt-4",
                        messages=[
                            {"role": "system", "content": active_system_prompt},
                            *messages
                        ],
                        temperature=0.7,
                        max_tokens=4096
                    )
                    assistant_message = response.choices[0].message.content
                except Exception as e:
                    # ... error handling ...
                    print(f"ERROR: Error calling OpenAI API: {str(e)}")
                    debug_print(f"OpenAI API error details:\n{traceback.format_exc()}")
                    continue

            # Add assistant message to history (remove duplicate)
            messages.append({"role": "assistant", "content": assistant_message})
            display_message_with_timestamp("assistant", assistant_message)

        except KeyboardInterrupt:
            print("\nUse '/exit' or '/quit' to quit.")
            continue
        except Exception as e:
            error_details = traceback.format_exc()
            print(f"ERROR in chat loop: {str(e)}")
            debug_print(f"Chat loop exception details:\n{error_details}")
            continue

def main():
    """Entry point for the chat interface."""
    try:
        chat()
    except KeyboardInterrupt:
        print("\nGoodbye!")
    except Exception as e:
        print(f"ERROR: {e}")
        debug_print(f"Main error: {traceback.format_exc()}")

if __name__ == '__main__':
    main() 