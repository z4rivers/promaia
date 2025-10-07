"""
Terminal-based chat interface for interacting with AI models.
"""

# Import models
from anthropic import Anthropic
from openai import OpenAI

import os
import sys
import time
import json
import shlex
from prompt_toolkit import PromptSession
from prompt_toolkit.styles import Style
from prompt_toolkit.history import FileHistory
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.keys import Keys
import datetime
import asyncio
import traceback
from typing import List, Dict, Any, Optional
from pathlib import Path

from promaia.storage.files import read_markdown_files_with_registry
from promaia.utils.config import load_environment, get_last_sync_time
from promaia.config.workspaces import get_workspace_manager
from promaia.ai.prompts import create_system_prompt
from promaia.ai.models import LLAMA_MODELS, ANTHROPIC_MODELS
from promaia.utils.display import print_markdown, print_code, print_text, print_separator
from promaia.utils.timezone_utils import now_utc
from promaia.storage.chat_history import ChatHistoryManager
from promaia.storage.recents import RecentsManager

import google.generativeai as genai

# Load environment variables
load_environment()

# Initialize DEBUG_MODE at the global scope
DEBUG_MODE = os.getenv("MAIA_DEBUG", "0") == "1"

# Configuration file for API preferences
API_PREFERENCE_FILE = os.path.join(os.path.expanduser("~"), ".maia_api_preference")

# --- API Client Initialization ---

def get_api_preference():
    """Get the saved API preference."""
    try:
        if os.path.exists(API_PREFERENCE_FILE):
            with open(API_PREFERENCE_FILE, 'r') as f:
                api_type = f.read().strip()
                if api_type in ["anthropic", "openai", "gemini", "llama"]:
                    return api_type
    except Exception as e:
        debug_print(f"Error reading API preference: {str(e)}")
    return "anthropic"

def save_api_preference(api_type):
    """Save the API preference."""
    try:
        with open(API_PREFERENCE_FILE, 'w') as f:
            f.write(api_type)
        debug_print(f"API preference saved: {api_type}")
    except Exception as e:
        debug_print(f"Error saving API preference: {str(e)}")

anthropic_client = None
if os.getenv("ANTHROPIC_API_KEY"):
    anthropic_client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

openai_client = None
if os.getenv("OPENAI_API_KEY"):
    openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

gemini_client = None
if os.getenv("GOOGLE_API_KEY"):
    genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
    gemini_client = genai.GenerativeModel('gemini-2.5-pro')

current_api = get_api_preference()
os.environ["API_TYPE"] = current_api

# --- UI Components ---

# Create key bindings for intuitive chat input
from prompt_toolkit.filters import Condition

bindings = KeyBindings()

@bindings.add('enter')
def _(event):
    """Enter key sends the message/command."""
    event.app.exit(result=event.app.current_buffer.text)

@bindings.add('c-j')
def _(event):
    """Ctrl+J adds a new line. On many terminals, Shift+Enter sends Ctrl+J."""
    event.current_buffer.insert_text('\n')

session = PromptSession(
    history=FileHistory('.chat_history'),
    multiline=True,  # Keep multiline for editing capabilities
    key_bindings=bindings
)

style = Style.from_dict({
    'prompt': 'ansicyan bold',
    'input': 'ansiwhite',
    'assistant': 'ansigreen',
    'user': 'ansiblue',
})

def get_local_timestamp():
    """Get current local timestamp formatted as YYYY-MM-DD HH:MM:SS."""
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def debug_print(message):
    """Print debug messages if debug mode is enabled."""
    if DEBUG_MODE:
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        caller_name = ""
        try:
            caller_name = f" [{sys._getframe(1).f_code.co_name}]"
        except Exception:
            pass
        print(f"DEBUG ({timestamp}){caller_name}: {message}")

# Local Llama client initialization (after debug_print is defined)
def initialize_llama_client():
    """Initialize local Llama client if available."""
    global llama_client
    llama_client = None
    llama_base_url = os.getenv("LLAMA_BASE_URL", "http://localhost:11434")
    if llama_base_url:
        try:
            # Test if local Llama server is available
            import requests
            test_url = f"{llama_base_url.rstrip('/')}/api/tags" if "ollama" in llama_base_url or ":11434" in llama_base_url else f"{llama_base_url.rstrip('/')}/v1/models"
            response = requests.get(test_url, timeout=2)
            if response.status_code == 200:
                # Use OpenAI client with custom base URL for local Llama
                llama_client = OpenAI(
                    base_url=f"{llama_base_url.rstrip('/')}/v1",
                    api_key=os.getenv("LLAMA_API_KEY", "local-llama")  # Many local setups don't need real API keys
                )
                debug_print(f"Local Llama client initialized at {llama_base_url}")
            else:
                debug_print(f"Local Llama server not responding at {llama_base_url}")
        except Exception as e:
            debug_print(f"Could not connect to local Llama server: {e}")

# Initialize llama client (will be initialized lazily when needed)
llama_client = None

def get_current_model_name():
    """Get the display name of the current model based on the current API."""
    global current_api
    from promaia.ai.models import get_model_display_name, ANTHROPIC_MODELS, GOOGLE_MODELS, LLAMA_MODELS
    
    # Get the actual model ID being used for each API type
    if current_api == "anthropic":
        model_id = ANTHROPIC_MODELS.get("sonnet", "claude-sonnet-4-5-20250929")
        return get_model_display_name(model_id, "anthropic")
    elif current_api == "openai":
        return get_model_display_name("gpt-4o", "openai")
    elif current_api == "gemini":
        model_id = GOOGLE_MODELS.get("pro", "gemini-2.5-pro-preview-05-06")
        return get_model_display_name(model_id, "gemini")
    elif current_api == "llama":
        model_id = os.getenv('LLAMA_DEFAULT_MODEL', 'llama3:latest')
        return get_model_display_name(model_id, "llama")
    
    return "Unknown Model"

def switch_model(target_model=None):
    """Switch to a different AI model during chat session."""
    global current_api
    from promaia.ai.models import get_model_display_name, ANTHROPIC_MODELS, GOOGLE_MODELS
    
    # Build available models dynamically
    available_models = {
        "1": ("anthropic", get_model_display_name(ANTHROPIC_MODELS.get("sonnet", "claude-sonnet-4-5-20250929"), "anthropic")),
        "2": ("openai", get_model_display_name("gpt-4o", "openai")), 
        "3": ("gemini", get_model_display_name(GOOGLE_MODELS.get("pro", "gemini-2.5-pro-preview-05-06"), "gemini")),
        "4": ("llama", get_model_display_name(os.getenv('LLAMA_DEFAULT_MODEL', 'llama3:latest'), "llama"))
    }
    
    # Check availability of each model
    available_choices = {}
    if anthropic_client:
        available_choices["1"] = available_models["1"]
    if openai_client:
        available_choices["2"] = available_models["2"]  
    if gemini_client:
        available_choices["3"] = available_models["3"]
    # Llama is always available if configured
    if os.getenv("LLAMA_BASE_URL"):
        available_choices["4"] = available_models["4"]
    
    if not available_choices:
        print_text("No AI models are available. Check your API keys.", style="bold red")
        return False
    
    # If target_model is specified, try to use it directly
    if target_model:
        target_model = target_model.lower()
        model_map = {
            "claude": "anthropic", "anthropic": "anthropic",
            "gpt": "openai", "openai": "openai", 
            "gemini": "gemini", "google": "gemini",
            "llama": "llama", "local": "llama"
        }
        
        if target_model in model_map:
            new_api = model_map[target_model]
            # Check if this model is available
            for choice_num, (api, name) in available_choices.items():
                if api == new_api:
                    current_api = new_api
                    os.environ["API_TYPE"] = current_api
                    save_api_preference(current_api)
                    print_text(f"Switched to {name}", style="bold green")
                    return True
            
            print_text(f"Model '{target_model}' is not available. Check API keys.", style="bold red")
            return False
    
    # Interactive model selection
    print_text("Available models:", style="bold")
    for choice, (api, name) in available_choices.items():
        current_indicator = " (current)" if api == current_api else ""
        print_text(f"  {choice}. {name}{current_indicator}", style="cyan")
    
    try:
        choice = input("Select model (1-4): ").strip()
        if choice in available_choices:
            new_api, model_name = available_choices[choice]
            if new_api != current_api:
                current_api = new_api
                os.environ["API_TYPE"] = current_api
                save_api_preference(current_api)
                print_text(f"Switched to {model_name}", style="bold green")
            else:
                print_text(f"Already using {model_name}", style="bold yellow")
            return True
        else:
            print_text("Invalid choice.", style="bold red")
            return False
    except (KeyboardInterrupt, EOFError):
        print_text("\nModel switch cancelled.", style="bold yellow")
        return False

def display_message_with_timestamp(role, content):
    """Displays a message with a timestamp using copy-friendly Rich display."""
    if role == 'assistant':
        print_markdown(f"**Maia:** {content}")
    elif role == 'user':
        print_text(f"You: {content}", style="bold cyan")
    else:
        print_text(content, style="yellow")

def generate_source_breakdown(multi_source_data):
    """Generate a dictionary of source names to page counts."""
    if not multi_source_data:
        return None
    
    breakdown = {}
    for source_key, pages in multi_source_data.items():
        # Create a display name that avoids collisions
        if '.' in source_key:
            workspace, source = source_key.split('.', 1)
            # Check if we need to include workspace to avoid collision
            base_source = source
            potential_collision = any(
                other_key != source_key and 
                (other_key.endswith('.' + source) or other_key == source)
                for other_key in multi_source_data.keys()
            )
            
            if potential_collision:
                # Include workspace prefix to disambiguate
                source_name = f"{workspace}.{source}"
            else:
                # No collision, use just the source name
                source_name = source
        else:
            source_name = source_key
            
        breakdown[source_name] = len(pages)
    
    return breakdown


def print_help_message(query_command, total_pages, model_name=None, source_breakdown=None):
    """Prints the detailed help message with command explanations."""
    print_text("🐙 maia chat", style="bold magenta")
    print_text(f"Query: {query_command}", style="dim")
    if total_pages > 0:
        print_text(f"Pages loaded: {total_pages}", style="dim")
        
        # Show breakdown by source if available
        if source_breakdown:
            for source_name, page_count in source_breakdown.items():
                print_text(f"{source_name}: {page_count}", style="dim")
                
    if model_name:
        print_text(f"Model: {model_name}", style="dim")
    print_text("Available commands: /quit /debug /push /help /s /e /save /model", style="dim")
    print_text("  /s - Sync databases in current context", style="dim")
    print_text("  /e - Edit context (sources, filters, natural language)", style="dim")
    print_text("  /save - Save current conversation to history", style="dim")
    print_text("  /model - Switch AI model (Claude, GPT-4o, Gemini, Llama)", style="dim")
    print_text("")


def print_welcome_message(query_command, total_pages, model_name=None, source_breakdown=None):
    """Prints the welcome message for the chat interface."""
    print_text("🐙 maia chat", style="bold magenta")
    print_text(f"Query: {query_command}", style="dim")
    if total_pages > 0:
        print_text(f"Pages loaded: {total_pages}", style="dim")
        
        # Show breakdown by source if available
        if source_breakdown:
            for source_name, page_count in source_breakdown.items():
                print_text(f"{source_name}: {page_count}", style="dim")
                
    if model_name:
        print_text(f"Model: {model_name}", style="dim")
    print_text("Available commands: /quit /debug /push /help /s /e /save /model", style="dim")
    print_text("")


# --- Core Chat Logic ---

async def push_chat_to_notion(messages):
    """Pushes the current chat history to a new Notion page."""
    # This is a placeholder for the actual implementation
    print_text("\n[Pushing chat to Notion...]", style="yellow")
    await asyncio.sleep(1) # Simulate async operation
    return "Successfully pushed chat to Notion."

def call_anthropic_with_retry(client, system_prompt, messages, max_tokens=4096, temperature=0.7, max_retries=3):
    """Calls the Anthropic API with retry logic."""
    from promaia.ai.models import ANTHROPIC_MODELS
    
    # Determine which model to use based on current selection
    # Check if we're using Claude Opus via the display name
    current_model_name = get_current_model_name()
    if "Opus" in current_model_name:
        model_to_use = ANTHROPIC_MODELS.get("opus", "claude-opus-4-1-20250805")
    else:
        model_to_use = ANTHROPIC_MODELS.get("sonnet", "claude-sonnet-4-5-20250929")
    
    debug_print(f"Using Anthropic model: {model_to_use} (selected: {current_model_name})")
    
    for attempt in range(max_retries):
        try:
            response = client.messages.create(
                model=model_to_use,
                system=system_prompt,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
            )
            return response
        except Exception as e:
            debug_print(f"Anthropic API call failed on attempt {attempt + 1}: {e}")
            if attempt + 1 == max_retries:
                return None
            time.sleep(2) # Wait before retrying
    return None

def run_non_interactive_chat(messages: List[Dict[str, Any]], system_prompt: str, for_api: str):
    """Handles a single, non-interactive chat exchange."""
    pass

def _split_respecting_escaped_spaces(text: str) -> list[str]:
    """
    Split text on spaces while respecting escaped spaces (backslash followed by space).
    
    Args:
        text: Text to split
        
    Returns:
        List of parts with escaped spaces properly handled
    """
    import re
    
    # Replace escaped spaces with a placeholder
    placeholder = "__ESCAPED_SPACE__"
    text_with_placeholder = text.replace('\\ ', placeholder)
    
    # Split on regular spaces
    parts = text_with_placeholder.split()
    
    # Restore escaped spaces by removing backslash and replacing placeholder
    restored_parts = []
    for part in parts:
        restored_part = part.replace(placeholder, ' ')
        restored_parts.append(restored_part)
    
    return restored_parts

def _parse_image_paths_and_message(input_text: str) -> tuple[list[str], str]:
    """
    Parse multiple image paths and message text from input.
    
    Args:
        input_text: The text after '/image' command
        
    Returns:
        Tuple of (image_paths, message_text)
    """
    import re
    from pathlib import Path
    
    # Use smart splitting that respects escaped spaces
    parts = _split_respecting_escaped_spaces(input_text)
    image_paths = []
    message_parts = []
    
    for part in parts:
        # Check if this looks like a file path and has an image extension
        if _is_likely_image_path(part):
            image_paths.append(part)
        else:
            message_parts.append(part)
    
    message_text = ' '.join(message_parts)
    return image_paths, message_text

def _is_likely_image_path(text: str) -> bool:
    """
    Check if a string looks like an image file path.
    
    Args:
        text: String to check
        
    Returns:
        True if it looks like an image path
    """
    # Common image extensions
    image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.tiff', '.tif', '.svg'}
    
    # Check if it has an image extension
    path = Path(text.lower())
    if path.suffix in image_extensions:
        return True
    
    # Check if it looks like a path (contains / or \ and doesn't look like a sentence)
    if ('/' in text or '\\' in text) and not text.endswith('.'):
        # Must be a single word/path, not a sentence
        if len(text.split()) != 1:
            return False
        
        # Additional validation to avoid false positives like "VAT/EORI"
        
        # 1. Check if it starts with path indicators (relative/absolute paths)
        if text.startswith(('./', '../', '~/', '/', '\\')):
            return True
        
        # 2. Check if it has multiple path components (not just "word/word")
        path_parts = [p for p in text.replace('\\', '/').split('/') if p]
        if len(path_parts) >= 3:  # At least something like "dir/subdir/file"
            return True
        
        # 3. Check if any component has a file extension (even non-image)
        for part in path_parts:
            if '.' in part and not part.startswith('.'):
                # Has an extension, could be a file path
                return True
        
        # 4. Avoid acronym patterns (e.g., "VAT/EORI" - uppercase words with slash)
        if all(part.isupper() or part.isdigit() for part in path_parts if part):
            return False
        
        # 5. Check if it's a common path pattern with current directory
        if len(path_parts) == 2:
            # Could be "dir/file" - check if second part looks like a filename
            last_part = path_parts[-1]
            if '.' in last_part or any(char.isdigit() for char in last_part):
                return True
    
    return False

def _detect_image_paths_in_message(user_input: str) -> tuple[str, list[str]]:
    """
    Detect image paths in a regular message without /image prefix.
    
    Args:
        user_input: The full user message
        
    Returns:
        Tuple of (cleaned_message, image_paths)
    """
    # Use smart splitting that respects escaped spaces
    words = _split_respecting_escaped_spaces(user_input)
    image_paths = []
    remaining_words = []
    
    for word in words:
        if _is_likely_image_path(word):
            image_paths.append(word)
        else:
            remaining_words.append(word)
    
    cleaned_message = ' '.join(remaining_words)
    return cleaned_message, image_paths

def safe_split_command(user_input):
    """
    Safely split command arguments, handling natural language queries with apostrophes.
    """
    # Clean up whitespace first
    cleaned = ' '.join(user_input.split())
    
    # For natural language queries, handle them specially
    if '-nl' in cleaned:
        # Split on -nl and handle the parts separately
        parts = cleaned.split('-nl', 1)
        if len(parts) == 2:
            pre_nl, post_nl = parts
            
            # Parse the pre-nl part normally (should be safe)
            try:
                pre_args = shlex.split(pre_nl.strip()) if pre_nl.strip() else []
            except ValueError:
                # If even the pre-nl part fails, fall back to simple split
                pre_args = pre_nl.strip().split() if pre_nl.strip() else []
            
            # For the post-nl part (natural language), just strip and keep as-is
            nl_prompt = post_nl.strip()
            
            # Combine them
            return pre_args + ['-nl'] + nl_prompt.split()
    
    # For non-natural language commands, try normal shlex first
    try:
        return shlex.split(cleaned)
    except ValueError:
        # Fall back to simple split if shlex fails
        return cleaned.split()

def save_context_log(context_state, system_prompt, total_pages_loaded, current_api, log_type="session_init"):
    """Save a context log file with current session information."""
    try:
        from promaia.config.databases import get_database_manager
        db_manager = get_database_manager()
        should_save_context = db_manager.global_settings.get("savecontexts", True)
    except Exception as e:
        debug_print(f"Could not load savecontexts config, defaulting to True: {e}")
        should_save_context = True
    
    if not should_save_context:
        return
    
    try:
        timestamp = now_utc().strftime("%Y%m%d-%H%M%S")
        context_filename = f"context logs/{timestamp}_{log_type}_prompt.txt"

        # Ensure context logs directory exists
        os.makedirs("context logs", exist_ok=True)

        # Write context file with session info
        with open(context_filename, 'w', encoding='utf-8') as f:
            if log_type == "session_init":
                f.write("=== MAIA CHAT SESSION INITIALIZATION ===\n")
            elif log_type == "context_update":
                f.write("=== MAIA CHAT CONTEXT UPDATE ===\n")
            else:
                f.write(f"=== MAIA CHAT {log_type.upper()} ===\n")
                
            f.write(f"Timestamp: {timestamp}\n")
            f.write(f"API Type: {current_api}\n")
            f.write(f"Workspace: {context_state.get('workspace')}\n")
            f.write(f"Resolved Workspace: {context_state.get('resolved_workspace')}\n")
            f.write(f"Sources: {context_state.get('sources')}\n")
            f.write(f"Filters: {context_state.get('filters')}\n")
            f.write(f"Natural Language Prompt: {context_state.get('natural_language_prompt')}\n")
            f.write(f"Query Command: {context_state.get('query_command')}\n")
            f.write(f"Total Pages Loaded: {total_pages_loaded}\n")
            f.write(f"System Prompt Length: {len(system_prompt)} characters\n")
            f.write("\n" + "="*50 + "\n")
            f.write("SYSTEM PROMPT:\n")
            f.write("="*50 + "\n")
            f.write(system_prompt)

        debug_print(f"Context log saved: {context_filename}")
        return context_filename
    except Exception as e:
        debug_print(f"Failed to save context log: {e}")
        return None


def process_browser_selections(selected_sources):
    processed_sources = []
    processed_filters = []
    discord_db_groups = {}
    
    for source in selected_sources:
        if '#' in source:
            db_channel, days_part = source.rsplit(':', 1)
            db_name, channel_name = db_channel.split('#', 1)
            db_key = f"{db_name}:{days_part}"
            if db_key not in discord_db_groups:
                discord_db_groups[db_key] = []
            discord_db_groups[db_key].append(channel_name)
        else:
            processed_sources.append(source)
            
    for db_spec, channels in discord_db_groups.items():
        processed_sources.append(db_spec)
        if len(channels) == 1:
            filter_spec = f"{db_spec}:discord_channel_name={channels[0]}"
            processed_filters.append(filter_spec)
        else:
            channel_conditions = [f"discord_channel_name={ch}" for ch in channels]
            combined_filter = " or ".join(channel_conditions)
            filter_spec = f"{db_spec}:({combined_filter})"
            processed_filters.append(filter_spec)
            
    return processed_sources, processed_filters


def chat(sources=None, filters=None, workspace=None, resolved_workspace=None, non_interactive=False, initial_messages=None, current_thread_id=None, natural_language_content=None, natural_language_prompt=None, original_browse_command=None, browse_selections=None, browse_databases=None, mcp_servers=None):
    """Main chat function with simplified, unified logic."""
    global current_api, DEBUG_MODE

    # Detect mixed commands: when user provides both sources and browse arguments
    has_regular_sources = bool(sources)
    has_browse_command = bool(browse_databases) or bool(original_browse_command and '-b' in original_browse_command)
    has_natural_language = bool(natural_language_prompt)

    
    # Detect mixed browse+NL commands from CLI: sources from browser + natural language
    # These should use OR logic (independent operation) not AND logic (filtering)
    # CLI mixed commands have: sources (from browser) + natural_language_prompt + original_browse_command + browse_databases=None
    is_cli_mixed_command = has_regular_sources and has_natural_language and browse_selections and not browse_databases
    debug_print(f"🐛 Mixed command check: has_regular_sources={has_regular_sources}, has_natural_language={has_natural_language}, browse_selections={bool(browse_selections)}, has_browse_command={has_browse_command}, browse_databases={bool(browse_databases)}")
    is_mixed_browse_nl_command = is_cli_mixed_command
    
    if is_mixed_browse_nl_command:
        debug_print(f"🔍 Detected mixed browse+NL command: sources={bool(sources)}, nl={bool(natural_language_prompt)}, browse_sel={bool(browse_selections)}, browse_cmd={has_browse_command}")
    else:
        debug_print(f"🚫 NOT detected as mixed browse+NL command")
    
    # Mixed command flow: -s sources + -b browse + -nl (optional)
    # This should: 1) Load -s sources first, 2) Launch browser with sources as context, 3) Process -nl last
    # Handle both cases: CLI launching browser first, or CLI already processed browser and calling with results
    if has_regular_sources and has_browse_command and not browse_selections:
        debug_print("🔄 Detected mixed command: sources + browse. Processing in sequence...")
        print_text("🔄 Processing mixed command: loading sources first, then launching browser...", style="cyan")
        
        
        # Step 1: Parse and prepare regular sources first
        print_text(f"📦 Preparing {len(sources)} regular sources for browser context...", style="cyan")
        
        # Import unified browser and workspace management
        from promaia.cli.workspace_browser import launch_unified_browser
        from promaia.config.workspaces import get_workspace_manager
        from promaia.config.databases import get_database_manager
        
        workspace_manager = get_workspace_manager()
        db_manager = get_database_manager()
        
        # Determine workspace and database filter from browse_databases
        database_filter = None
        default_days = None
        browse_workspace = resolved_workspace or workspace
        
        if browse_databases:
            database_filter = []
            workspace_names = []
            
            for browse_spec in browse_databases:
                if ':' in browse_spec:
                    db_name, days_str = browse_spec.rsplit(':', 1)
                    try:
                        days = int(days_str)
                        if default_days is None:
                            default_days = days
                        
                        # Check if db_name is a workspace
                        if workspace_manager.validate_workspace(db_name):
                            # Don't expand workspace - let browser handle it
                            workspace_names.append(db_name)
                            if not browse_workspace:
                                browse_workspace = db_name
                        else:
                            database_filter.append(browse_spec)  # Keep the full spec with days
                    except ValueError:
                        database_filter.append(browse_spec)
                else:
                    # Check if this is a workspace name
                    if workspace_manager.validate_workspace(browse_spec):
                        # Don't expand workspace - let browser handle it
                        workspace_names.append(browse_spec)
                        if not browse_workspace:
                            browse_workspace = browse_spec
                    else:
                        # It's a specific database name
                        database_filter.append(browse_spec)
            
            # If we only have workspace names, clear the database filter
            if workspace_names and not database_filter:
                database_filter = None  # Let browser show all databases in the workspace
        
        # Step 2: Launch browser with regular sources as context
        print_text("🔍 Launching browser with regular sources as context...", style="cyan")
        
        # For workspace browse commands, we want to default to ALL workspace sources selected
        # Plus include the regular sources (like journal:30)
        browser_current_sources = list(sources)  # Start with regular sources like journal:30
        
        # Check if this is a workspace browse by seeing if we have a workspace but no specific database filter
        is_workspace_browse = browse_workspace and database_filter is None
        
        if is_workspace_browse:
            # For workspace browse, add all workspace databases as selected by default
            workspace_databases = db_manager.get_workspace_databases(browse_workspace)
            for db in workspace_databases:
                if db.sync_enabled:  # Only include enabled databases
                    if default_days:
                        source_with_days = f"{db.get_qualified_name()}:{default_days}"
                    else:
                        source_with_days = f"{db.get_qualified_name()}:7"  # Default to 7 days
                    browser_current_sources.append(source_with_days)
        
        # Launch unified browser with existing sources as context
        selected_sources = launch_unified_browser(
            workspace=browse_workspace,
            default_days=default_days,
            database_filter=database_filter,
            current_sources=browser_current_sources  # Pre-populate with all workspace sources + regular sources
        )
        
        if not selected_sources:
            print_text("ℹ️  No sources selected from browser. Using only the regular sources.", style="yellow")
            # Keep browser selections empty - only use regular sources
            browse_selections = []
        else:
            # Store ALL browser selections for persistence (not just additional ones)
            browse_selections = selected_sources.copy()  # Store all selected sources
            
            print_text(f"✅ Browser selections: {len(browse_selections)} sources selected (will be stored for persistence)", style="green")
            
            # Store in context_state for /e functionality
            context_state['browse_selections'] = browse_selections
        
        # Step 3: Store the original mixed command format and browser selections
        # Build the original command format to preserve -s and -b structure
        query_parts = ["maia", "chat"]
        if sources:
            for source in sources:
                query_parts.extend(["-s", source])
        if browse_databases:
            query_parts.append("-b")
            query_parts.extend(browse_databases)
        if filters:
            for filter_expr in filters:
                query_parts.extend(["-f", f'"{filter_expr}"'])
        if workspace:
            query_parts.extend(["-ws", workspace])
        if natural_language_prompt:
            query_parts.extend(["-nl", natural_language_prompt])
        if mcp_servers:
            for server in mcp_servers:
                query_parts.extend(["-mcp", server])
        
        # Store the original command format and browser selections
        original_mixed_command = " ".join(query_parts)
        print_text(f"📝 Preserving original command format: {original_mixed_command}", style="dim")
        
        # Step 4: Combine all sources for the main chat flow
        all_sources = list(sources)  # Start with regular sources like journal:30
        
        if selected_sources:
            # Add all browser selections to sources for the main chat flow
            for selected in selected_sources:
                # Only add if not already in sources
                source_base = selected.split(':')[0].split('#')[0]
                already_in_sources = any(source_base in existing for existing in sources)
                if not already_in_sources:
                    all_sources.append(selected)
        
        # Update sources to include all selections for the main chat flow
        sources = all_sources
        print_text(f"🔗 Combined sources: {len(sources)} total sources for chat", style="blue")
        
        # Set these for context state initialization
        original_browse_command = f"maia chat {original_browse_command}" if original_browse_command else None
        
        # Clear browse_databases since we've processed it and stored the results
        browse_databases = None
        print_text("🚀 Proceeding with normal chat flow preserving original format...", style="green")
        
        # Continue to normal chat processing below with the combined sources

    # Parse original_browse_command if provided (from history loading)
    if original_browse_command and not sources and not filters:
        try:
            # Parse the browse command to extract sources and filters
            import shlex
            import argparse
            
            # Extract arguments from the command
            if original_browse_command.startswith("maia chat "):
                command_args = original_browse_command[10:]  # Remove "maia chat "
            else:
                command_args = original_browse_command
            
            # Parse the command
            args_list = safe_split_command(command_args)
            
            parser = argparse.ArgumentParser(add_help=False)
            parser.add_argument("-s", "--source", action="append", dest="sources")
            parser.add_argument("-f", "--filter", action="append", dest="filters")
            parser.add_argument("-w", "--workspace", dest="workspace")
            parser.add_argument("-b", "--browse", nargs="*", dest="browse")
            parser.add_argument("-nl", "--natural-language", nargs="*", dest="natural_language")
            parser.add_argument("-mcp", action="append", dest="mcp_servers")
            
            parsed_args, unknown = parser.parse_known_args(args_list)
            
            # Extract parsed values
            if parsed_args.sources:
                sources = parsed_args.sources
            if parsed_args.filters:
                filters = parsed_args.filters
            if parsed_args.workspace and not workspace:
                workspace = parsed_args.workspace
            if parsed_args.natural_language and not natural_language_prompt:
                natural_language_prompt = " ".join(parsed_args.natural_language)
            if parsed_args.mcp_servers and not mcp_servers:
                mcp_servers = parsed_args.mcp_servers
                
            debug_print(f"Parsed browse command: sources={sources}, filters={filters}, workspace={workspace}")
            
        except Exception as e:
            debug_print(f"Error parsing original_browse_command: {e}")
            # Continue with original values

    # Context state tracking for dynamic changes
    context_state = {
        'sources': sources,
        'filters': filters,
        'workspace': workspace,
        'resolved_workspace': resolved_workspace,
        'initial_multi_source_data': {},
        'total_pages_loaded': 0,
        'system_prompt': None,
        'query_command': None,
        'current_thread_id': current_thread_id,  # Track if we're continuing a thread
        'natural_language_content': natural_language_content,  # Track if using natural language
        'browse_selections': browse_selections if browse_selections is not None else [],  # Store browser selections from CLI
        'natural_language_prompt': natural_language_prompt,  # Store the original NL prompt
        'mcp_servers': mcp_servers,  # Store MCP server names to include
        'mcp_tools_info': None,  # Store MCP tools information for prompt
        'original_browse_mode': bool(original_browse_command),  # Track if session started with browse mode
        'enable_search': False,  # Store search functionality flag (starts disabled)
        'original_query_format': original_browse_command,  # Store the original query format for display
        'is_mixed_browse_nl_command': is_mixed_browse_nl_command  # Flag for OR logic in NL processing
    }

    # Update context_state with browse_selections if they were set during browser interaction
    # This handles the case where browse_selections were set locally but not captured in the parameter
    if 'browse_selections' in locals() and browse_selections:
        context_state['browse_selections'] = browse_selections
    # Also store browse_selections if passed as parameter (for CLI mixed commands)
    elif browse_selections:
        context_state['browse_selections'] = browse_selections
    
    # Debug: Show what browse_selections were stored
    # if browse_selections:
    #     debug_print(f"STORED browse_selections in context_state: {browse_selections}")

    def update_query_command():
        """Update the query command display based on current context state."""
        # If we have an original query format (mixed commands, browse commands, etc.), show it
        if context_state.get('original_query_format'):
            context_state['query_command'] = context_state['original_query_format']
            return
        
        # Otherwise, build the command from current state
        query_parts = ["maia", "chat"]
        if context_state['sources']:
            if len(context_state['sources']) == 1:
                query_parts.extend(["-s", context_state['sources'][0]])
            else:
                for source in context_state['sources']:
                    query_parts.extend(["-s", source])
        if context_state['filters']:
            for filter_expr in context_state['filters']:
                query_parts.extend(["-f", f'"{filter_expr}"'])
        if context_state['workspace']:  # Only show workspace if explicitly provided by user
            query_parts.extend(["-ws", context_state['workspace']])
        if context_state['natural_language_prompt']:
            nl_prompt = context_state['natural_language_prompt']
            # Don't add quotes - the -nl argument parser handles multiple words with nargs="*"
            # Adding quotes is redundant and makes commands harder to read and copy
            query_parts.extend(["-nl", nl_prompt])
        if context_state['mcp_servers']:
            for server in context_state['mcp_servers']:
                query_parts.extend(["-mcp", server])
        
        # Update query_command but preserve original_query_format if it exists
        built_command = " ".join(query_parts)
        context_state['query_command'] = built_command
        # Only update original_query_format if it doesn't exist
        if not context_state.get('original_query_format'):
            context_state['original_query_format'] = built_command

    # Initial query command setup - capture original format for regular commands too
    if not context_state.get('original_query_format'):
        if original_browse_command:
            # Use the provided original browse command
            context_state['original_query_format'] = original_browse_command
        elif sources or filters or workspace or natural_language_prompt or mcp_servers:
            # Build and store the original query format for regular commands to preserve day specifications
            query_parts = ["maia", "chat"]
            if sources:
                for source in sources:
                    query_parts.extend(["-s", source])
            if filters:
                for filter_expr in filters:
                    query_parts.extend(["-f", f'"{filter_expr}"'])
            if workspace:
                query_parts.extend(["-ws", workspace])
            if natural_language_prompt:
                query_parts.extend(["-nl", natural_language_prompt])
            if mcp_servers:
                for server in mcp_servers:
                    query_parts.extend(["-mcp", server])
            context_state['original_query_format'] = " ".join(query_parts)
    
    update_query_command()
    query_command = context_state['query_command']

    def reload_context(skip_nl_cache_messages=False):
        """Reload the chat context with current state configuration."""
        nonlocal initial_multi_source_data, total_pages_loaded, system_prompt, query_command, natural_language_content, sources
        
        # Initialize combined data container
        combined_multi_source_data = {}
        
        # Process natural language query if present
        natural_language_data = {}
        if context_state.get('natural_language_prompt'):
            nl_prompt = context_state['natural_language_prompt']
            
            # Check if we already have content from CLI (first time) or cached results
            existing_nl_content = context_state.get('natural_language_content', {})
            cached_nl_prompt = context_state.get('cached_natural_language_prompt', '')
            
            # DEBUG: Add logging to understand cache behavior
            debug_print(f"🔍 NL Cache Debug:")
            debug_print(f"  Current prompt: '{nl_prompt}'")
            debug_print(f"  Cached prompt: '{cached_nl_prompt}'")
            debug_print(f"  Prompts match: {nl_prompt == cached_nl_prompt}")
            debug_print(f"  Has existing content: {bool(existing_nl_content)}")
            debug_print(f"  Content count: {len(existing_nl_content) if existing_nl_content else 0}")
            
            # If we have content and no cached prompt yet, this is CLI-provided content (first time)
            if existing_nl_content and not cached_nl_prompt:
                if not skip_nl_cache_messages:
                    print_text("🔄 Using natural language results from CLI", style="dim")
                natural_language_data = existing_nl_content
                # Set up cache for future reloads
                context_state['cached_natural_language_prompt'] = nl_prompt
                debug_print(f"  → Using CLI content, caching prompt")
            # If we have cached content for this exact prompt, reuse it (no re-processing needed)
            elif nl_prompt == cached_nl_prompt and existing_nl_content:
                if not skip_nl_cache_messages:
                    print_text("🔄 Using cached natural language results (browse context changed, query unchanged)", style="dim")
                natural_language_data = existing_nl_content
                debug_print(f"  → Using cached content (cache hit)")
                # IMPORTANT: Don't re-process the query, just use cached results
            # Otherwise, process fresh query
            else:
                debug_print(f"  → Cache miss, will re-process query")
                
                try:
                    from promaia.storage.unified_query import get_query_interface
                    
                    # Determine workspace to use - preserve from original context
                    workspace = context_state.get('resolved_workspace') or context_state.get('workspace')
                    
                    # If no explicit workspace, try to infer from original sources
                    if not workspace and context_state.get('sources'):
                        # Try to extract workspace from source names (e.g., "trass.gmail" -> "trass")
                        for source in context_state['sources']:
                            if '.' in source:
                                potential_workspace = source.split('.')[0]
                                workspace = potential_workspace
                                break
                    
                    # Fall back to default workspace
                    if not workspace:
                        from promaia.config.workspaces import get_workspace_manager
                        workspace_manager = get_workspace_manager()
                        workspace = workspace_manager.get_default_workspace()
                    
                    if not workspace:
                        print_text("Error: No workspace available for natural language query.", style="bold red")
                        return False
                    
                    # Process natural language query fresh
                    query_interface = get_query_interface()
                    
                    # For OR logic: Natural language searches ALL databases (not restricted to browser selections)
                    # Browser selections will be loaded separately and combined with NL results
                    database_names = None  # Search all databases for maximum content discovery
                    
                    # IMPORTANT: For mixed browse+NL commands, always use None to ensure OR logic
                    # Don't extract database names from current sources - that would create AND logic
                    if context_state.get('is_mixed_browse_nl_command'):
                        database_names = None  # Explicit OR logic for browse + NL independence
                        debug_print("🔄 Mixed browse+NL command: using database_names=None for OR logic")
                    
                    # Always allow cross-workspace queries for natural language
                    # Workspace is just a classifier/tag, not a mandatory constraint
                    natural_language_content = query_interface.natural_language_query(nl_prompt, None, database_names)
                    
                    if not natural_language_content:
                        print_text("❌ No content found for natural language query", style="bold red")
                        return False
                    
                    # Cache both the results and prompt for future use
                    context_state['natural_language_content'] = natural_language_content
                    context_state['cached_natural_language_prompt'] = nl_prompt
                    
                    # IMPORTANT: Set natural_language_data for integration with combined_multi_source_data
                    natural_language_data = natural_language_content
                    
                except Exception as e:
                    print_text(f"Error processing natural language content: {e}", style="bold red")
                    # Continue with regular sources even if NL fails
                    # Clear cache on error
                    context_state['natural_language_content'] = {}
                    context_state['cached_natural_language_prompt'] = ''
            
            # Add natural language data to combined results (whether cached or fresh)
            if natural_language_data:
                combined_multi_source_data.update(natural_language_data)
        
        # Process MCP servers if present
        mcp_tools_info = ""
        if context_state.get('mcp_servers'):
            try:
                print_text("🔧 Connecting to MCP servers...", style="white")
                
                # Load environment variables for MCP servers
                from dotenv import load_dotenv
                load_dotenv()
                
                from promaia.config.mcp_servers import get_mcp_manager
                from promaia.mcp.client import McpClient
                from promaia.mcp.execution import McpToolExecutor
                
                mcp_manager = get_mcp_manager()
                mcp_client = McpClient()
                
                connected_servers = []
                for server_name in context_state['mcp_servers']:
                    server_config = mcp_manager.get_server(server_name)
                    if server_config:
                        if server_config.enabled:
                            print(f"  Connecting to {server_name}...")
                            # For now, simulate connection - in real implementation this would be async
                            import asyncio
                            success = asyncio.run(mcp_client.connect_to_server(server_config))
                            if success:
                                connected_servers.append(server_name)
                                print(f"  ✅ Connected to {server_name}")
                            else:
                                print(f"  ❌ Failed to connect to {server_name}")
                        else:
                            print(f"  ⚠️ Server {server_name} is disabled in config")
                    else:
                        print(f"  ❌ Server {server_name} not found in config")
                
                if connected_servers:
                    # Use compact format if we have other content to avoid prompt issues
                    # Also use compact format when we have no content at all to prevent content filtering
                    has_other_content = bool(sources or natural_language_content)
                    compact_format = has_other_content or (not sources and not natural_language_content)
                    
                    # Format tools information for the system prompt
                    mcp_tools_info = mcp_client.format_tools_for_prompt(connected_servers, compact=compact_format)
                    context_state['mcp_tools_info'] = mcp_tools_info
                    context_state['mcp_client'] = mcp_client
                    context_state['mcp_executor'] = McpToolExecutor(mcp_client)
                    print(f"🔧 Connected to {len(connected_servers)} MCP server(s): {', '.join(connected_servers)}")
                else:
                    print("⚠️ No MCP servers were successfully connected")
                    
            except Exception as e:
                print_text(f"Error processing MCP servers: {e}", style="bold red")
                # Continue even if MCP fails
        
        # Use current state - ensure sources is always a list
        current_sources = context_state.get('sources', []) or []
        
        # Debug: Check if we have browser selections that should be loaded as regular sources
        if DEBUG_MODE and current_sources:
            print_text(f"🔍 Current sources to load: {current_sources}", style="dim cyan")
        current_filters = context_state.get('filters', []) or []
        current_workspace = context_state.get('workspace')
        current_resolved_workspace = context_state.get('resolved_workspace')
        
        # 1. Determine Workspace (use resolved_workspace if provided, otherwise fallback)
        if current_resolved_workspace:
            actual_workspace = current_resolved_workspace
        else:
            from promaia.config.workspaces import get_workspace_manager
            workspace_manager = get_workspace_manager()
            if not current_workspace:
                actual_workspace = workspace_manager.get_default_workspace()
            else:
                actual_workspace = current_workspace
        
        if not actual_workspace:
            print_text("ERROR: No workspace available. Please configure one.", style="bold red")
            return False

        # 2. Determine and Process Sources
        from promaia.config.databases import get_database_manager
        from promaia.cli.database_commands import parse_source_specs, parse_filter_expression

        db_manager = get_database_manager()
        # Initialize new data container (don't include natural language yet to avoid duplication)
        new_multi_source_data = {}
        # Don't calculate total here - calculate it from final data to ensure consistency

        # Only auto-load workspace databases if user provided NO arguments at all
        user_provided_args = bool(sources or filters or natural_language_prompt or browse_selections or mcp_servers)
        
        # Check if user provided workspace but no sources (workspace browse mode)
        # BUT don't launch browser if we already have sources (e.g., from edit context)
        # Only launch browser if user explicitly provided a workspace (not defaulted)
        user_provided_workspace_only = bool(current_workspace and not sources and not filters and not natural_language_prompt)
        
        if user_provided_workspace_only and not current_sources:
            debug_print(f"Opening workspace browser for '{actual_workspace}'.")
            print_text(f"🔍 Launching unified browser for '{actual_workspace}'...", style="bold cyan")
            
            # Launch the workspace browser
            from promaia.cli.workspace_browser import launch_workspace_browser
            selected_sources = launch_workspace_browser(actual_workspace)
            
            if selected_sources:
                current_sources = selected_sources
                context_state['sources'] = current_sources
                # Store the original workspace command for display  
                context_state['original_query_format'] = f"maia chat -b {actual_workspace}"
                print_text(f"📦 Selected {len(selected_sources)} sources from workspace '{actual_workspace}'", style="cyan")
            else:
                print_text(f"No sources selected from workspace '{actual_workspace}'. Chat will lack context.", style="bold yellow")
                # Continue with blank slate - don't return
        elif not current_sources and len(combined_multi_source_data) == 0 and not user_provided_args:
            # For plain "maia chat" with no args, start with blank slate instead of loading defaults
            debug_print(f"No arguments provided, starting with blank slate (no default databases loaded).")
            print_text("💬 Starting chat with blank slate (no context loaded)", style="bold cyan")
            context_state['blank_slate_message_shown'] = True  # Track that we've shown this message
        elif len(combined_multi_source_data) > 0 and not current_sources:
            debug_print(f"Have natural language content only (no browser selections) - using NL content only")
            # Only skip regular sources if we don't have browser selections
            # This preserves OR logic: browser selections + natural language results
        elif user_provided_args and not current_sources and len(combined_multi_source_data) == 0:
            debug_print(f"User provided arguments but no sources - MCP or other tools will provide context.")

        if current_filters and current_sources:
            debug_print(f"Applying filters: {current_filters}")

        # 3. Process filters and integrate them into source specifications
        processed_sources = []
        discord_filters = []  # Separate list for complete Discord filters
        source_specific_filters = {}  # Dict of source -> list of filters
        global_filters = []

        # Parse and categorize filters
        if current_filters:
            debug_print(f"Processing filters: {current_filters}")

            for filter_expr in current_filters:
                try:
                    parsed_filter = parse_filter_expression(filter_expr)

                    # Check if this is a source-specific filter (new format)
                    if isinstance(parsed_filter, dict) and 'source' in parsed_filter:
                        source = parsed_filter['source']
                        filter_spec = parsed_filter['filter']

                        # Check if this is a complete Discord filter specification (includes days and filter)
                        # Format: trass.discord:7:discord_channel_name=koii-work or trass.discord:7:(discord_channel_name=...)
                        # Also handle "all" day values: trass.discord:all:discord_channel_name=...
                        source_parts = source.split(':')
                        source_has_days = (len(source_parts) > 1 and 
                                         (source_parts[-1].isdigit() or source_parts[-1] == 'all'))
                        filter_is_discord = ('discord_channel_name' in filter_spec or 
                                           ('(' in filter_spec and 'discord_channel_name' in filter_spec))
                        
                        if source_has_days and filter_is_discord:
                            # This is a complete Discord filter - handle separately
                            discord_filters.append(filter_expr)
                            debug_print(f"Added complete Discord filter: {filter_expr}")
                            continue

                        if source not in source_specific_filters:
                            source_specific_filters[source] = []
                        source_specific_filters[source].append(filter_spec)
                        debug_print(f"Added source-specific filter: {source} -> {filter_spec}")
                    else:
                        # Backward compatibility - filter without source prefix
                        global_filters.append(parsed_filter)
                        debug_print(f"Added global filter: {parsed_filter}")

                except Exception as e:
                    print_text(f"Warning: Invalid filter '{filter_expr}': {e}", style="bold yellow")
                    continue

        # Validation for multi-source scenarios
        if current_sources and len(current_sources) > 1:
            if global_filters:
                print_text(
                    "Error: In multi-source scenarios, all filters must specify a source prefix.\n"
                    f"Example: Instead of '{global_filters[0]}', use 'source:\"{global_filters[0]}\"'\n"
                    "Available sources: " + ", ".join(current_sources),
                    style="bold red"
                )
                return False

            # Check that all filter sources are valid
            for filter_source in source_specific_filters.keys():
                if filter_source not in current_sources:
                    print_text(
                        f"Error: Filter source '{filter_source}' not found in specified sources.\n"
                        f"Available sources: {', '.join(current_sources)}",
                        style="bold red"
                    )
                    return False

        # Build processed sources with appropriate filters
        if current_sources:
            for source in current_sources:
                # Determine which filters apply to this source
                applicable_filters = []

                # Add source-specific filters
                if source in source_specific_filters:
                    applicable_filters.extend(source_specific_filters[source])

                # Add global filters (only in single-source scenarios or backward compatibility)
                if len(current_sources) == 1 or not source_specific_filters:
                    applicable_filters.extend(global_filters)

                # Build the source specification
                if applicable_filters:
                    # Create a source spec with integrated filters
                    # Check if source already has a day specification (e.g., "trass.discord:30")
                    if ':' in source:
                        # Source already has day spec, just append filters
                        source_with_filters = f"{source}.{'.'.join(applicable_filters)}"
                    else:
                        # Source has no day spec, use 'all' for unlimited days
                        source_with_filters = f"{source}:all.{'.'.join(applicable_filters)}"
                    processed_sources.append(source_with_filters)
                    debug_print(f"Created filtered source spec: {source_with_filters}")
                else:
                    processed_sources.append(source)
                    debug_print(f"Using unfiltered source: {source}")

        # Log final filter application
        if DEBUG_MODE and (source_specific_filters or global_filters):
            print_text("Filter Summary:", style="bold cyan")
            for source in current_sources or []:
                filters_for_source = []
                if source in source_specific_filters:
                    filters_for_source.extend([f"source-specific: {f}" for f in source_specific_filters[source]])
                if len(current_sources) == 1 or not source_specific_filters:
                    filters_for_source.extend([f"global: {f}" for f in global_filters])

                if filters_for_source:
                    print_text(f"  {source}: {', '.join(filters_for_source)}", style="dim")
                else:
                    print_text(f"  {source}: no filters", style="dim")

        # 4. Parse the processed source specifications
        parsed_sources_init = []
        if processed_sources:
            if DEBUG_MODE:
                print_text(f"🔍 Processed sources to parse: {processed_sources}", style="dim cyan")
            try:
                parsed_sources_init = parse_source_specs(processed_sources)
                if DEBUG_MODE:
                    print_text(f"🔍 Parsed sources result: {len(parsed_sources_init)} sources", style="dim cyan")
            except Exception as e:
                print_text(f"Warning: Error parsing source specifications: {e}", style="bold yellow")
                return False
        else:
            if DEBUG_MODE:
                print_text("🔍 No processed sources to parse", style="dim cyan")

        # 5. Parse Discord filters separately (they need special handling)
        if discord_filters:
            try:
                # Manually construct Discord filter objects to avoid parser warnings
                for discord_filter in discord_filters:
                    parsed_filter = parse_filter_expression(discord_filter)
                    if isinstance(parsed_filter, dict) and 'source' in parsed_filter:
                        source = parsed_filter['source']
                        filter_spec = parsed_filter['filter']
                        
                        # Extract database and days from source (e.g., "trass.discord:7")
                        source_parts = source.split(':')
                        database = source_parts[0]
                        days = int(source_parts[1]) if len(source_parts) > 1 and source_parts[1].isdigit() else None
                        
                        # Get database config for validation
                        db_config = db_manager.get_database_by_qualified_name(database)
                        if not db_config:
                            debug_print(f"Warning: Database config for '{database}' not found. Skipping Discord filter.")
                            continue
                        
                        # Parse the filter specification
                        property_filters = {}
                        complex_filter = None
                        
                        # Handle complex filters (multiple channels with OR)
                        if filter_spec.startswith('__COMPLEX_EXPR__'):
                            # Extract complex expression
                            complex_expr = filter_spec[16:]  # Remove '__COMPLEX_EXPR__' prefix
                            # For Discord filters, convert to property filters format
                            if '(' in complex_expr and 'discord_channel_name=' in complex_expr:
                                # Extract channel names from (discord_channel_name=a or discord_channel_name=b)
                                # For now, use the complex filter as-is - the file reader will handle it
                                from promaia.cli.database_commands import parse_complex_filter_expression
                                complex_filter = parse_complex_filter_expression(complex_expr)
                        else:
                            # Simple single channel filter
                            if '=' in filter_spec:
                                prop_name, prop_value = filter_spec.split('=', 1)
                                property_filters[prop_name] = prop_value
                        
                        # Construct parsed source object
                        discord_parsed_source = {
                            'name': db_config.get_qualified_name(),
                            'database': db_config.get_qualified_name(),
                            'qualified_name': db_config.get_qualified_name(),
                            'days': days,
                            'property_filters': property_filters,
                            'comparison_filters': {},
                            'complex_filter': complex_filter
                        }
                        
                        parsed_sources_init.append(discord_parsed_source)
                        debug_print(f"Manually parsed Discord filter: {database}, days: {days}, filters: {property_filters}, complex: {complex_filter}")
                        
            except Exception as e:
                print_text(f"Warning: Error parsing Discord filters: {e}", style="bold yellow")
                # Continue anyway - don't fail completely on Discord filter errors
        else:
            debug_print("No Discord filters detected. discord_filters list is empty.")

        # Load content from sources
        sources_loaded_successfully = False
        if parsed_sources_init:
            if DEBUG_MODE:
                print_text("Loading context from sources...", style="cyan")
            for source_conf in parsed_sources_init:
                db_name = source_conf['database']
                # Try to get database by qualified name first, then fallback to regular lookup
                db_config = db_manager.get_database_by_qualified_name(db_name)
                if not db_config:
                    db_config = db_manager.get_database(db_name)
                if not db_config:
                    if DEBUG_MODE:
                        print_text(f"Warning: Config for database '{db_name}' not found. Skipping.", style="bold yellow")
                    continue

                try:
                    # Check if this source has a complex filter with date conditions
                    has_date_filter_in_complex = False
                    if source_conf.get('complex_filter'):
                        complex_filter = source_conf.get('complex_filter')
                        if complex_filter.get('type') == 'complex':
                            for or_clause in complex_filter.get('or_clauses', []):
                                for condition in or_clause:
                                    if condition.get('property') in ['created_time', 'last_edited_time']:
                                        has_date_filter_in_complex = True
                                        break
                                if has_date_filter_in_complex:
                                    break

                    # Don't use days constraint if complex filter already has date conditions
                    days_to_use = None if has_date_filter_in_complex else source_conf.get('days')

                    pages = read_markdown_files_with_registry(
                        db_config,
                        days=days_to_use,
                        comparison_filters=source_conf.get('comparison_filters', {}),
                        complex_filter=source_conf.get('complex_filter'),
                        property_filters=source_conf.get('property_filters', {})
                    )
                    # Use qualified name to avoid collisions between workspaces
                    unique_key = db_config.get_qualified_name()
                    new_multi_source_data[unique_key] = pages
                    # Don't increment total here - calculate from final data to ensure consistency

                    # Only mark as successful if we actually got pages
                    if len(pages) > 0:
                        sources_loaded_successfully = True
                    if DEBUG_MODE:
                        print_text(f"  - Loaded {len(pages)} entries from: {unique_key}", style="green")
                except Exception as e:
                    if DEBUG_MODE:
                        print_text(f"Error loading data for database {db_config.name}: {e}", style="bold red")
                    # Continue trying other sources instead of failing completely
        else:
            # No regular sources to load, but might have natural language content
            if len(combined_multi_source_data) > 0:
                sources_loaded_successfully = True  # We have content from natural language
                print_text("ℹ️  No regular sources specified, using natural language content only", style="cyan")

        # Calculate total from final data to ensure consistency with breakdown
        new_total_pages_loaded = sum(len(pages) for pages in new_multi_source_data.values())
        
        # Always merge natural language content if it exists
        if len(combined_multi_source_data) > 0:
            # Merge natural language content with regular sources
            for source_name, pages in combined_multi_source_data.items():
                if source_name not in new_multi_source_data:
                    new_multi_source_data[source_name] = pages
                else:
                    # If source already exists, combine the pages (shouldn't happen but handle it)
                    new_multi_source_data[source_name].extend(pages)
            
            # Recalculate total after merging
            new_total_pages_loaded = sum(len(pages) for pages in new_multi_source_data.values())
            
            if not sources_loaded_successfully:
                print_text("ℹ️  Using natural language content (regular sources had no data)", style="cyan")
        
        # Check if we have any data at all
        if new_total_pages_loaded == 0:
            # If we have MCP servers, we can still chat even without content
            if context_state.get('mcp_servers'):
                print_text("❌ No content could be loaded from any source", style="bold red")
                print_text("💡 MCP tools are available for interaction", style="cyan")
            else:
                # Only show blank slate message if we haven't already shown it
                if not context_state.get('blank_slate_message_shown'):
                    print_text("💬 Starting chat with blank slate (no context loaded)", style="bold cyan")
                # Continue with blank slate - don't return False
        
        # Update context state
        context_state['initial_multi_source_data'] = new_multi_source_data
        context_state['total_pages_loaded'] = new_total_pages_loaded
        
        # Update sources list to reflect only the sources that were actually loaded
        # This ensures session logs show accurate source information
        # However, preserve the original sources format if we have user-provided args
        # to maintain day specifications in the query display
        if not context_state.get('original_query_format') and not user_provided_args and not context_state.get('sources'):
            # Only overwrite if sources were auto-generated AND we don't already have sources
            context_state['sources'] = list(new_multi_source_data.keys())
        # else: keep the existing sources with their day specifications for display
        
        # Update module-level variables
        initial_multi_source_data = new_multi_source_data
        total_pages_loaded = new_total_pages_loaded
        
        # Generate new system prompt
        mcp_tools_info = context_state.get('mcp_tools_info')
        system_prompt = create_system_prompt(new_multi_source_data, mcp_tools_info)
        context_state['system_prompt'] = system_prompt
        
        # Save context log when MCP servers are connected (for transparency)
        if context_state.get('mcp_servers') and mcp_tools_info:
            save_context_log(context_state, system_prompt, new_total_pages_loaded, current_api, "mcp_connection")
        
        # Debug: Log context reload details
        if DEBUG_MODE:
            debug_print(f"Context Reload: {len(new_multi_source_data)} data sources loaded")
            debug_print(f"Context Reload: {new_total_pages_loaded} total pages")
            debug_print(f"Context Reload: System prompt length: {len(system_prompt)}")
            debug_print(f"Context Reload: Data sources: {list(new_multi_source_data.keys())}")
            debug_print(f"Context Reload: Updated context_state sources: {context_state.get('sources')}")
        
        # Update query command
        update_query_command()
        query_command = context_state['query_command']
        
        return True

    async def sync_current_context_databases():
        """Sync the databases currently in the chat context."""
        nonlocal initial_multi_source_data
        
        # Determine what databases to sync based on current context
        databases_to_sync = []
        
        # Check if we have sources from traditional source specification
        if context_state['sources']:
            databases_to_sync = context_state['sources']
        # Check if we have databases from natural language queries
        elif context_state.get('natural_language_content'):
            databases_to_sync = list(context_state['natural_language_content'].keys())
        # Check if we have databases from initial multi-source data
        elif context_state.get('initial_multi_source_data'):
            databases_to_sync = list(context_state['initial_multi_source_data'].keys())
        # Fallback to global initial_multi_source_data if available
        elif initial_multi_source_data:
            databases_to_sync = list(initial_multi_source_data.keys())
        
        if not databases_to_sync:
            print_text("No databases in current context to sync.", style="bold yellow")
            return
        
        from promaia.cli.database_commands import sync_database
        from promaia.config.databases import get_database_manager
        
        db_manager = get_database_manager()
        
        print_text(f"Syncing {len(databases_to_sync)} database(s) from current context...", style="bold cyan")
        print_text("Note: This only syncs databases in your current chat context.", style="dim")
        print_text("Use 'maia sync' outside chat to sync all enabled databases.", style="dim")
        
        # Create a mock args object for the sync function
        # Use same logic as standalone maia sync - pure incremental sync
        class MockArgs:
            def __init__(self):
                self.force = False
                self.days = None
                self.start_date = None
                self.end_date = None
                self.date_range = None
        
        mock_args = MockArgs()
        
        # Use the same source parsing logic as standalone sync, but include filters
        from promaia.cli.database_commands import parse_source_specs
        from promaia.config.databases import get_database_manager
        
        db_manager = get_database_manager()
        current_filters = context_state.get('filters', [])
        
        # For Discord sources with browse-mode channel filters, use the filtered specs
        # For regular sources, use the source as-is
        sources_to_sync = []
        
        for source in databases_to_sync:
            # Check if this is a Discord source
            source_name = source.split(':')[0] if ':' in source else source
            db_config = db_manager.get_database_by_qualified_name(source_name)
            
            if db_config and db_config.source_type == "discord":
                # Check if we have channel-specific filters for this Discord source
                # Match by database name (not including days) to handle day specification mismatches
                db_base_name = db_config.name  # Get the full database name (e.g., 'trass.yeeps_discord')
                
                # Find filters that match this database (regardless of day specification)
                sync_discord_filters = []
                for f in current_filters:
                    filter_db_name = f.split(':')[0] if ':' in f else f
                    # Check if this filter belongs to the same database
                    filter_db_config = db_manager.get_database_by_qualified_name(filter_db_name)
                    if filter_db_config and filter_db_config.name == db_base_name:
                        sync_discord_filters.append(f)
                
                if sync_discord_filters:
                    # Use the filtered specifications (one per channel)
                    sources_to_sync.extend(sync_discord_filters)
                    print_text(f"📺 Discord source {source}: syncing {len(sync_discord_filters)} selected channels", style="cyan")
                else:
                    # No channel filters - skip Discord sources without browse selection
                    print_text(f"⚠️  Discord source {source}: No channels selected. Use browse mode (-b) to select channels first.", style="bold yellow")
                    continue
            else:
                # Regular source - use as-is
                sources_to_sync.append(source)
        
        if not sources_to_sync:
            print_text("No sources available to sync after filtering.", style="bold yellow")
            print_text("💡 For Discord sources, use browse mode (-b) to select specific channels first.", style="dim yellow")
            return
        
        # Parse all sources at once using the same logic as standalone sync
        parsed_sources = parse_source_specs(sources_to_sync)
        
        for source_spec in parsed_sources:
            try:
                source_name = source_spec.get('qualified_name', source_spec.get('name', 'Unknown'))
                
                # The sync_database function will print its own "🔄 Syncing..." and result messages
                result = await sync_database(source_spec, mock_args)
                
                # Only show additional error details if needed (sync_database shows the main error)
                if result.errors and len(result.errors) > 1:
                    for error in result.errors[1:3]:  # Show additional errors (first one already shown)
                        print_text(f"  - {error}", style="red")
                
            except Exception as e:
                print_text(f"  ❌ {source_name}: Sync failed - {e}", style="bold red")
                debug_print(f"Sync error for {source_name}: {e}")

    def edit_context():
        """CLI-style context editing interface."""
        print_text("\n🔧 Edit Context", style="bold cyan")
        
        # Show current context summary
        print_text("Current command:", style="dim")
        # Always show with maia chat prefix for consistency and copy-ability
        command_to_display = context_state['query_command']
        if not command_to_display.startswith("maia chat"):
            command_to_display = f"maia chat {command_to_display}"
        print_text(f"  {command_to_display}", style="bold")
        
        # Show helpful info for Discord contexts
        if context_state.get('sources') and any('discord' in src.lower() or src.endswith('.ds') for src in context_state['sources']):
            workspace = context_state.get('resolved_workspace') or context_state.get('workspace')
            if workspace:
                print_text(f"  Discord workspace: {workspace}", style="dim cyan")
            if context_state.get('filters'):
                channel_count = len([f for f in context_state['filters'] if 'channel_name=' in f])
                if channel_count > 0:
                    print_text(f"  Discord channels selected: {channel_count}", style="dim cyan")
        
            # Show if this was originally a browse mode session
            if context_state.get('original_browse_mode'):
                print_text(f"  Original format: browse mode", style="dim cyan")
        
        print_text("")
        print_text("Options:", style="dim")
        print_text("  • Edit command manually (shown below)", style="dim")
        print_text("  • Ctrl+R for recent queries", style="dim")
        print_text("  • Ctrl+B for browse mode", style="dim")
        print_text("  • Press Enter alone to cancel", style="dim")
        print_text("")
        
        # Build the current command arguments (without 'maia chat')
        current_args = []
        current_args_str = ""  # Initialize to ensure it's never None
        
        # If we have an original query format, extract args from that
        if context_state.get('original_query_format'):
            # Extract everything after "maia chat "
            original_cmd = context_state['original_query_format']
            if original_cmd and original_cmd.startswith("maia chat "):
                current_args_str = original_cmd[10:]  # Remove "maia chat "
            elif original_cmd == "maia chat":
                current_args_str = ""  # No args when command is just "maia chat"
            else:
                current_args_str = original_cmd  # Use the whole thing as args
        else:
            # Check if we're in natural language mode
            if context_state.get('natural_language_prompt'):
                current_args.extend(['-nl', context_state['natural_language_prompt']])
            else:
                # Regular mode with sources and filters
                if context_state['sources']:
                    for source in context_state['sources']:
                        current_args.extend(['-s', source])
                if context_state['filters']:
                    for filter_expr in context_state['filters']:
                        current_args.extend(['-f', filter_expr])
                if context_state['workspace']:
                    current_args.extend(['-ws', context_state['workspace']])
            
            current_args_str = ' '.join(current_args) if current_args else ''
        
        try:
            # Create custom key bindings for Ctrl+R and Ctrl+B
            from prompt_toolkit.key_binding import KeyBindings
            from prompt_toolkit import prompt
            
            bindings = KeyBindings()
            action_taken = {'type': None}
            
            @bindings.add('c-r')  # Ctrl+R
            def handle_recents(event):
                action_taken['type'] = 'recents'
                event.app.exit()
            
            @bindings.add('c-b')  # Ctrl+B  
            def handle_browse(event):
                action_taken['type'] = 'browse'
                event.app.exit()
            
            # Use prompt_toolkit to show the current command as editable default
            user_input = prompt(
                "maia chat ",
                default=current_args_str or "",
                mouse_support=True,
                key_bindings=bindings
            )
            
            # Ensure user_input is never None
            if user_input is None:
                user_input = ""
            else:
                user_input = user_input.strip()
                
            # Handle case where user types full command including "maia chat"
            if user_input.startswith("maia chat "):
                user_input = user_input[10:]  # Remove "maia chat " prefix
            elif user_input == "maia chat":
                user_input = ""  # Treat as empty input (reset to no args)
            
            # Check if a special action was triggered
            if action_taken['type'] == 'recents':
                return handle_recents_in_edit_context()
            elif action_taken['type'] == 'browse':
                return handle_browse_in_edit_context()
            
            # Handle different input scenarios
            if DEBUG_MODE:
                print_text(f"DEBUG: user_input='{user_input}', current_args_str='{current_args_str}'", style="dim yellow")
            
            if not user_input and not current_args_str:
                # No input and no current args - cancel
                print_text("Context edit cancelled.", style="bold yellow")
                return False
            elif not user_input and current_args_str:
                # Empty input but there were current args - user wants to keep current
                print_text("Keeping current context.", style="bold green")
                return True
            elif user_input == current_args_str:
                # User didn't change anything - keep current context
                print_text("No changes made. Keeping current context.", style="bold green")
                return True
            
            # Parse the input as CLI arguments
            import shlex
            import argparse
            
            try:
                # Check if this is a browse mode command that was manually edited
                if '-b' in user_input and user_input.strip() != current_args_str.strip():
                        # User manually edited a browse command - handle it with CLI logic
                        print_text("📝 Processing manually edited command...", style="bold cyan")
                        return handle_manual_browse_edit(user_input)
                
                # Use safe parsing that handles natural language queries with apostrophes
                args_list = safe_split_command(user_input)
                
                # Create a minimal parser for chat arguments
                parser = argparse.ArgumentParser(description="Chat context editor", add_help=False)
                parser.add_argument(
                    "--source", "-s",
                    action="append", 
                    dest="sources",
                    help="Load data from specific database with day filter"
                )
                parser.add_argument(
                    "--filter", "-f",
                    action="append",
                    dest="filters",
                    help="Add property filters"
                )
                parser.add_argument(
                    "--workspace", "-ws",
                    help="Specify which workspace to use"
                )
                parser.add_argument(
                    "--natural-language", "-nl",
                    action="append",
                    nargs="+",
                    help="Use natural language to specify what content to load for chat context. Can be used multiple times."
                )
                parser.add_argument(
                    "--mcp", "-mcp",
                    action="append",
                    dest="mcp_servers",
                    help="Include MCP servers in chat context"
                )
                
                # Parse the arguments
                parsed_args = parser.parse_args(args_list)
                
                # Check if natural language mode is being used
                natural_language_args = getattr(parsed_args, 'natural_language', None)
                
                if natural_language_args is not None:
                    # Natural language mode - handle multiple -nl queries
                    # With action="append" and nargs="+", we get a list of lists
                    nl_prompts = [' '.join(nl_args) for nl_args in natural_language_args if nl_args]
                    
                    if not nl_prompts:
                        print_text("Error: Natural language prompt is empty.", style="bold red")
                        return False
                    
                    # Create combined prompt for caching
                    combined_nl_prompt = " ".join([f'-nl {prompt}' for prompt in nl_prompts])
                    
                    # Check if we already have cached results for this exact NL prompt
                    cached_nl_content = context_state.get('natural_language_content', {})
                    cached_nl_prompt = context_state.get('cached_natural_language_prompt', '')
                    
                    # DEBUG: Log cache check in edit context
                    debug_print(f"🔍 Edit Context NL Cache Check:")
                    debug_print(f"  New prompt(s): {nl_prompts}")
                    debug_print(f"  Cached prompt: '{cached_nl_prompt}'")
                    debug_print(f"  Prompts match: {combined_nl_prompt == cached_nl_prompt}")
                    debug_print(f"  Has cached content: {bool(cached_nl_content)}")
                    
                    if combined_nl_prompt == cached_nl_prompt and cached_nl_content:
                        print_text("🔄 Reusing cached natural language results (prompt unchanged)", style="dim")
                        natural_language_content = cached_nl_content
                        debug_print(f"  → Using cached results (edit context cache hit)")
                    else:
                        # Only clear cache if the prompt is actually different (not empty)
                        if cached_nl_prompt and combined_nl_prompt != cached_nl_prompt:
                            debug_print(f"  → Prompt changed, clearing cache")
                            context_state['natural_language_content'] = None
                            context_state['cached_natural_language_prompt'] = ''
                        elif not cached_nl_prompt:
                            debug_print(f"  → No cached prompt yet, will process and cache")
                        else:
                            debug_print(f"  → Cache miss, will re-process")
                        
                        # Process multiple natural language queries
                        try:
                            from promaia.storage.unified_query import get_query_interface
                            
                            if len(nl_prompts) > 1:
                                print_text(f"🤖 Processing {len(nl_prompts)} separate natural language queries", style="dim")
                                for i, prompt in enumerate(nl_prompts):
                                    print_text(f"   {i+1}. '{prompt}'", style="dim")
                            else:
                                print_text(f"🤖 Processing natural language query: '{nl_prompts[0]}'", style="dim")
                            
                            # Determine workspace to use
                            workspace = context_state.get('resolved_workspace') or context_state.get('workspace')
                            
                            # If no explicit workspace, try to infer from original sources
                            if not workspace and context_state.get('sources'):
                                # Try to extract workspace from source names (e.g., "trass.gmail" -> "trass")
                                for source in context_state['sources']:
                                    if '.' in source:
                                        potential_workspace = source.split('.')[0]
                                        workspace = potential_workspace
                                        break
                            
                            # Fall back to default workspace
                            if not workspace:
                                from promaia.config.workspaces import get_workspace_manager
                                workspace_manager = get_workspace_manager()
                                workspace = workspace_manager.get_default_workspace()
                            
                            if not workspace:
                                print_text("Error: No workspace available for natural language query.", style="bold red")
                                return False
                            
                            # Process multiple natural language queries and combine results
                            query_interface = get_query_interface()
                            
                            # For OR logic: Natural language searches ALL databases (not restricted to browser selections)
                            # Browser selections will be loaded separately and combined with NL results  
                            database_names = None  # Search all databases for maximum content discovery
                            
                            # Process each NL query separately and combine results
                            combined_nl_content = {}
                            total_results = 0
                            
                            for i, nl_prompt in enumerate(nl_prompts):
                                print_text(f"🔍 Processing query {i+1}/{len(nl_prompts)}: '{nl_prompt}'", style="cyan")
                                
                                # Always allow cross-workspace queries for natural language
                                # Workspace is just a classifier/tag, not a mandatory constraint
                                nl_content = query_interface.natural_language_query(nl_prompt, None, database_names)
                                
                                if nl_content:
                                    # Merge results from this query into combined content
                                    for db_name, entries in nl_content.items():
                                        if db_name not in combined_nl_content:
                                            combined_nl_content[db_name] = []
                                        combined_nl_content[db_name].extend(entries)
                                    
                                    query_results = sum(len(entries) for entries in nl_content.values())
                                    total_results += query_results
                                    print_text(f"   ✅ Query {i+1} found {query_results} results", style="green")
                                else:
                                    print_text(f"   ⚠️  Query {i+1} found no results", style="yellow")
                            
                            if not combined_nl_content:
                                print_text("❌ No content found for any natural language queries", style="bold red")
                                return False
                            
                            print_text(f"🎯 Combined {len(nl_prompts)} queries: {total_results} total results", style="green")
                            natural_language_content = combined_nl_content
                            
                            # Cache both the results and combined prompt for future use
                            context_state['natural_language_content'] = natural_language_content
                            context_state['cached_natural_language_prompt'] = combined_nl_prompt
                            
                        except Exception as e:
                            print_text(f"Error processing natural language query: {e}", style="bold red")
                            return False
                    
                    # Update context state for natural language mode
                    # natural_language_content is already set above (either from cache or fresh query)
                    context_state['natural_language_prompt'] = combined_nl_prompt
                    
                    # NOTE: Don't update cached_natural_language_prompt here!
                    # Let reload_context() handle cache updates after processing new queries
                    
                    # Update sources and filters based on the edited command, not the old state
                    new_sources = getattr(parsed_args, 'sources', []) or []
                    new_filters = getattr(parsed_args, 'filters', []) or []
                    new_workspace = getattr(parsed_args, 'workspace', None)
                    new_mcp_servers = getattr(parsed_args, 'mcp_servers', []) or []
                    
                    context_state['sources'] = new_sources
                    context_state['filters'] = new_filters
                    context_state['mcp_servers'] = new_mcp_servers
                    if new_workspace:
                        context_state['workspace'] = new_workspace
                    
                    # Only clear browse state if user is explicitly switching away from browse mode
                    # Don't clear if they're just editing other aspects of the command
                    if not any('-b' in arg for arg in args_list):
                        # User removed browse flag - clear browse state but preserve other context
                        context_state['original_browse_mode'] = False
                        context_state['browse_selections'] = []
                        # Don't clear original_query_format to preserve command display
                    
                    # Update the original query format for natural language mode
                    full_command = f"maia chat {user_input}"
                    context_state['original_query_format'] = full_command
                    
                    # Reload with natural language content and updated sources
                    # Pass flag to indicate this is after manual editing to avoid confusing cache messages
                    if reload_context(skip_nl_cache_messages=True):
                        print_text("Context updated successfully!", style="bold green")
                        return True
                    else:
                        print_text("Failed to reload context with natural language content.", style="bold red")
                        return False
                else:
                    # Regular mode with sources and filters
                    new_sources = getattr(parsed_args, 'sources', []) or []
                    new_filters = getattr(parsed_args, 'filters', []) or []
                    new_workspace = getattr(parsed_args, 'workspace', None)
                    new_mcp_servers = getattr(parsed_args, 'mcp_servers', []) or []
                    
                    # Check if we're switching from NL mode to regular mode
                    had_nl_content = bool(context_state.get('natural_language_content'))
                    had_nl_prompt = bool(context_state.get('natural_language_prompt'))
                    nl_was_removed = had_nl_content or had_nl_prompt
                    
                    # Update context state
                    context_state['sources'] = new_sources
                    context_state['filters'] = new_filters
                    context_state['mcp_servers'] = new_mcp_servers
                    
                    if new_workspace:
                        context_state['workspace'] = new_workspace
                    
                    # Update the original query format for regular mode
                    full_command = f"maia chat {user_input}"
                    context_state['original_query_format'] = full_command
                    
                    # If we had NL content and now we don't, properly remove it
                    if nl_was_removed:
                        print_text("🔄 Natural language prompt removed - switching to regular mode", style="cyan")
                        print_text("🔄 Removing natural language results from context...", style="cyan")
                        
                        # IMPORTANT: Capture NL sources before clearing state to prevent any confusion  
                        nl_sources_to_remove = set(context_state.get('natural_language_content', {}).keys() if context_state.get('natural_language_content') else [])
                        context_state['natural_language_content'] = None
                        context_state['natural_language_prompt'] = None
                        context_state['cached_natural_language_prompt'] = ''
                        
                        try:
                            nonlocal initial_multi_source_data, total_pages_loaded
                            
                            # Get the current multi-source data
                            current_data = dict(initial_multi_source_data)
                            
                            # Build set of sources that should be kept based on new regular sources
                            sources_to_keep = set()
                            if new_sources:
                                for source_spec in new_sources:
                                    # Extract just the database name part (before :)
                                    db_name = source_spec.split(':')[0]
                                    sources_to_keep.add(db_name)
                            
                            # Remove sources that came from NL and are not in the new sources to keep
                            keys_to_remove = []
                            for key in current_data.keys():
                                # Check if this source was loaded via natural language
                                is_from_nl = key in nl_sources_to_remove
                                
                                # Check if this source should be kept based on new regular sources
                                should_keep = any(keep_src in key for keep_src in sources_to_keep) if sources_to_keep else False
                                
                                # Remove if it's from NL and shouldn't be kept
                                if is_from_nl and not should_keep:
                                    keys_to_remove.append(key)
                                    debug_print(f"Will remove NL source: {key} (not in new sources: {sources_to_keep})")
                            
                            # Remove the identified keys
                            for key in keys_to_remove:
                                if key in current_data:
                                    debug_print(f"Removing NL source from context: {key}")
                                    del current_data[key]
                            
                            # Update the global variables with the cleaned data
                            initial_multi_source_data = current_data
                            total_pages_loaded = sum(len(pages) for pages in current_data.values())
                            
                            # Update context state as well
                            context_state['initial_multi_source_data'] = current_data
                            context_state['total_pages_loaded'] = total_pages_loaded
                            
                            # Update the system prompt with the remaining data
                            mcp_tools_info = context_state.get('mcp_tools_info')
                            system_prompt = create_system_prompt(current_data, mcp_tools_info)
                            context_state['system_prompt'] = system_prompt
                            
                            debug_print(f"After NL removal: {len(current_data)} sources, {total_pages_loaded} pages")
                            print_text("Context updated successfully!", style="bold green")
                            return True
                            
                        except Exception as e:
                            print_text(f"❌ Error updating context after NL removal: {e}", style="red")
                            debug_print(f"NL removal error: {e}")
                            # Fall back to full reload if manual update fails
                            # Ensure NL state is still cleared before reload
                            context_state['natural_language_content'] = None
                            context_state['natural_language_prompt'] = None
                            context_state['cached_natural_language_prompt'] = ''
                            if reload_context():
                                print_text("Context updated successfully via reload!", style="bold green")
                                return True
                            else:
                                print_text("❌ Failed to reload context after removing natural language", style="red")
                                return False
                    else:
                        # No NL content to remove, just reload normally
                        if reload_context():
                            print_text("Context updated successfully!", style="bold green")
                            return True
                        else:
                            print_text("Failed to reload context with new settings.", style="bold red")
                            return False
                    
            except SystemExit:
                # argparse calls sys.exit on invalid arguments
                print_text("Invalid command syntax.", style="bold red")
                print_text("Examples:", style="dim")
                print_text("  -s journal:5 -s gmail:10 -f 'last week'", style="dim")
                print_text("  -nl emails from last week about project updates", style="dim")
                return False
            except Exception as e:
                print_text(f"Error parsing command: {e}", style="bold red")
                print_text("Examples:", style="dim")
                print_text("  -s journal:5 -s gmail:10 -f 'last week'", style="dim")
                print_text("  -nl emails from last week about project updates", style="dim")
                return False
                
        except (KeyboardInterrupt, EOFError):
            print_text("\nContext edit cancelled.", style="bold yellow")
            return False
    
    def handle_manual_browse_edit(user_input):
        """Handle manually edited browse commands."""
        try:
            # Import CLI functions we need
            import argparse
            import asyncio
            
            # Get original format from context state early (used throughout function)
            original_format = context_state.get('original_query_format', '')
            
            # Parse the browse command
            args_list = safe_split_command(user_input)
            
            # Create parser that handles browse commands
            parser = argparse.ArgumentParser(description="Manual browse command editor", add_help=False)
            parser.add_argument("--source", "-s", action="append", dest="sources")
            parser.add_argument("--filter", "-f", action="append", dest="filters") 
            parser.add_argument("--workspace", "-ws", dest="workspace")
            parser.add_argument("--browse", "-b", action="append", nargs="*", dest="browse")
            parser.add_argument("--natural-language", "-nl", nargs="*", dest="natural_language")
            
            parsed_args = parser.parse_args(args_list)
            
            # Extract components
            regular_sources = parsed_args.sources or []
            # Flatten nested lists from multiple -b flags: [['trass'], ['trass.tg']] -> ['trass', 'trass.tg']
            raw_browse = parsed_args.browse or []
            browse_databases = []
            if raw_browse:
                for item in raw_browse:
                    if isinstance(item, list):
                        browse_databases.extend(item)
                    else:
                        browse_databases.append(item)
            original_filters = parsed_args.filters or []
            workspace = parsed_args.workspace or context_state.get('workspace')
            natural_language_parts = parsed_args.natural_language or []
            
            # Detect if the browse part of the command actually changed
            original_command = context_state.get('original_query_format', '')
            browse_changed = False
            
            if browse_databases:
                # Extract browse databases from original command
                import re
                original_browse_match = re.findall(r'-b\s+([^\s-]+(?:\s+[^\s-]+)*)', original_command)
                original_browse_databases = []
                for match in original_browse_match:
                    original_browse_databases.extend(match.split())
                
                # Compare current browse databases with original
                browse_changed = set(browse_databases) != set(original_browse_databases)
                
                # Check if the browse scope expanded (new databases added) or reduced (databases removed)
                # Only launch browser if new databases were added, not if databases were removed
                if browse_changed and context_state.get('browse_selections'):
                    # Build set of database/workspace names from NEW browse command
                    new_browse_db_set = set()
                    for browse_db in browse_databases:
                        base_name = browse_db.split(':')[0] if ':' in browse_db else browse_db
                        new_browse_db_set.add(base_name)
                    
                    old_browse_db_set = set()
                    for browse_db in original_browse_databases:
                        base_name = browse_db.split(':')[0] if ':' in browse_db else browse_db
                        old_browse_db_set.add(base_name)
                    
                    # Determine if scope expanded (new databases) or reduced (removed databases)
                    added_databases = new_browse_db_set - old_browse_db_set
                    removed_databases = old_browse_db_set - new_browse_db_set
                    
                    if added_databases and not removed_databases:
                        # Pure expansion: new databases added, none removed
                        debug_print(f"Detected scope expansion: new databases {added_databases} added")
                        browse_changed = True
                    elif removed_databases and not added_databases:
                        # Pure reduction: databases removed, none added
                        debug_print(f"Detected scope reduction: databases {removed_databases} removed, keeping browser closed")
                        browse_changed = False  # Don't launch browser for reductions
                    elif added_databases and removed_databases:
                        # Mixed: both added and removed - treat as changed, launch browser
                        debug_print(f"Detected scope change: added {added_databases}, removed {removed_databases}")
                        browse_changed = True
                    else:
                        # No actual change (shouldn't happen but handle it)
                        browse_changed = False
            elif context_state.get('browse_selections'):
                # If no browse databases now but we had them before, that's a change
                browse_changed = True
            
            # Detect if natural language was removed FIRST (before processing)
            nl_was_removed = False
            nl_sources_to_remove = set()  # Initialize for use throughout function
            if not natural_language_parts and (context_state.get('natural_language_content') or context_state.get('natural_language_prompt')):
                print_text("🔄 Natural language prompt removed - switching to regular browse mode", style="dim")
                nl_was_removed = True
                # Capture NL sources before any state changes
                nl_sources_to_remove = set(context_state.get('natural_language_content', {}).keys() if context_state.get('natural_language_content') else [])
                
            # Process natural language query if present
            nl_prompt = None
            natural_language_content = None
            if natural_language_parts:
                nl_prompt = ' '.join(natural_language_parts)
                
                # Check cache first - similar logic to edit_context
                cached_nl_content = context_state.get('natural_language_content', {})
                cached_nl_prompt = context_state.get('cached_natural_language_prompt', '')
                
                debug_print(f"🔍 Manual Browse Edit NL Cache Check:")
                debug_print(f"  New prompt: '{nl_prompt}'")
                debug_print(f"  Cached prompt: '{cached_nl_prompt}'")
                debug_print(f"  Prompts match: {nl_prompt == cached_nl_prompt}")
                debug_print(f"  Has cached content: {bool(cached_nl_content)}")
                
                if nl_prompt == cached_nl_prompt and cached_nl_content:
                    print_text("🔄 Reusing cached natural language results (prompt unchanged)", style="cyan")
                    natural_language_content = cached_nl_content
                    debug_print(f"  → Using cached results (browse edit cache hit)")
                else:
                    debug_print(f"  → Cache miss, will re-process query")
                    print_text(f"🤖 Processing natural language query: '{nl_prompt}'", style="cyan")
                    
                    # Process the natural language query
                    try:
                        from promaia.storage.unified_query import get_query_interface
                        
                        # Determine workspace for natural language processing
                        nl_workspace = workspace or context_state.get('resolved_workspace') or context_state.get('workspace')
                        if not nl_workspace:
                            from promaia.config.workspaces import get_workspace_manager
                            workspace_manager = get_workspace_manager()
                            nl_workspace = workspace_manager.get_default_workspace()
                        
                        if nl_workspace:
                            # Process the natural language query
                            query_interface = get_query_interface()
                            
                            # For OR logic: Natural language searches ALL databases (not restricted to browser selections)
                            # Browser selections will be loaded separately and combined with NL results
                            database_names = None  # Search all databases for maximum content discovery
                                
                            natural_language_content = query_interface.natural_language_query(nl_prompt, nl_workspace, database_names)
                            
                            if natural_language_content:
                                print_text("🔄 Using natural language results from CLI", style="cyan")
                                # Update context state with natural language content AND cache
                                context_state['natural_language_content'] = natural_language_content
                                context_state['natural_language_prompt'] = nl_prompt
                                context_state['cached_natural_language_prompt'] = nl_prompt
                                debug_print(f"  → Processed and cached new results")
                            else:
                                print_text("❌ No content found for natural language query", style="yellow")
                        else:
                            print_text("❌ No workspace available for natural language processing", style="yellow")
                            
                    except Exception as e:
                        print_text(f"❌ Error processing natural language query: {e}", style="yellow")
            elif nl_was_removed:
                # Clear NL state when removed
                context_state['natural_language_content'] = None
                context_state['natural_language_prompt'] = None
                context_state['cached_natural_language_prompt'] = ''
            
            # Parse browse databases and expand workspace names (same logic as cli.py)
            database_filter = None
            default_days = None
            
            if browse_databases:
                from promaia.config.workspaces import get_workspace_manager
                from promaia.config.databases import get_database_manager
                workspace_manager = get_workspace_manager()
                db_manager = get_database_manager()
                
                database_filter = []
                workspace_names = []
                
                for browse_spec in browse_databases:
                    if ':' in browse_spec:
                        db_name, days_str = browse_spec.rsplit(':', 1)
                        try:
                            days = int(days_str)
                            if default_days is None:
                                default_days = days
                            
                            # Check if db_name is a workspace
                            if workspace_manager.validate_workspace(db_name):
                                # Don't expand workspace - let browser handle it
                                workspace_names.append(db_name)
                            else:
                                database_filter.append(browse_spec)  # Keep the full spec with days
                        except ValueError:
                            database_filter.append(browse_spec)
                    else:
                        # Check if this is a workspace name
                        if workspace_manager.validate_workspace(browse_spec):
                            # Don't expand workspace - let browser handle it
                            workspace_names.append(browse_spec)
                        else:
                            # It's a specific database name
                            database_filter.append(browse_spec)
                
                # If we only have workspace names, clear the database filter
                if workspace_names and not database_filter:
                    database_filter = None  # Let browser show all databases in the workspace
            
            # Resolve workspace from browse databases if needed
            resolved_workspace = workspace
            multiple_workspaces = []
            
            if browse_databases and not workspace:
                # First, collect all unique workspaces from the browse arguments
                for browse_db in browse_databases:
                    if workspace_manager.validate_workspace(browse_db):
                        if browse_db not in multiple_workspaces:
                            multiple_workspaces.append(browse_db)
                
                # Also check database_filter for workspace prefixes
                if database_filter:
                    for db_name in database_filter:
                        if '.' in db_name:
                            determined_workspace = db_name.split('.')[0]
                            if workspace_manager.validate_workspace(determined_workspace):
                                if determined_workspace not in multiple_workspaces:
                                    multiple_workspaces.append(determined_workspace)
                
                # Handle workspace resolution based on how many workspaces we found
                if len(multiple_workspaces) == 1:
                    # Single workspace - use it normally
                    resolved_workspace = multiple_workspaces[0]
                    print_text(f"INFO: Using workspace '{resolved_workspace}' from browse argument.", style="cyan")
                elif len(multiple_workspaces) > 1:
                    # Multiple workspaces - don't resolve to a single one, use database_filter instead
                    resolved_workspace = None
                    print_text(f"INFO: Using multiple workspaces: {', '.join(multiple_workspaces)}", style="cyan")
                else:
                    # No workspace found in browse args, try to determine from database_filter
                    if database_filter:
                        for browse_db in database_filter:
                            if '.' in browse_db:
                                determined_workspace = browse_db.split('.')[0]
                                if workspace_manager.validate_workspace(determined_workspace):
                                    resolved_workspace = determined_workspace
                                    print_text(f"INFO: Using workspace '{resolved_workspace}' from browse database '{browse_db}'.", style="cyan")
                                    break
            
            if not resolved_workspace:
                resolved_workspace = context_state.get('resolved_workspace')
            
            # Update context state with the resolved workspace(s)
            if resolved_workspace:
                context_state['workspace'] = resolved_workspace
                context_state['resolved_workspace'] = resolved_workspace
            elif multiple_workspaces:
                # For multiple workspaces, store them in a special way
                context_state['workspace'] = None  # No single workspace
                context_state['resolved_workspace'] = None
                context_state['multiple_workspaces'] = multiple_workspaces
            
            # Handle mixed commands (browse + regular sources) differently
            if browse_databases and regular_sources:
                # This is a mixed command - update context directly without launching browser
                print_text(f"🔄 Updating context with browse databases and regular sources...", style="cyan")
                
                # Start with regular sources
                all_sources = regular_sources.copy()
                # Hmm seems odd that regular sources gets stored as all sources. but maybe it makes sense.
                
                # For workspaces mentioned in -b, preserve existing browser selections instead of expanding
                existing_sources = context_state.get('sources', [])
                preserved_workspace_sources = []
                
                for browse_db in browse_databases:
                    if workspace_manager.validate_workspace(browse_db):
                        # This is a workspace - preserve existing browser selections for this workspace
                        for existing_source in existing_sources:
                            source_db = existing_source.split(':')[0] if ':' in existing_source else existing_source
                            if '.' in source_db:
                                source_workspace = source_db.split('.')[0]
                                if source_workspace == browse_db:
                                    preserved_workspace_sources.append(existing_source)
                
                # Add preserved workspace sources
                all_sources.extend(preserved_workspace_sources)
                
                # Only add database_filter sources that aren't already covered by preserved sources
                if database_filter:
                    for db_name in database_filter:
                        # Check if this database is already preserved
                        db_base = db_name.split(':')[0] if ':' in db_name else db_name
                        already_preserved = any(
                            existing.split(':')[0] == db_base 
                            for existing in preserved_workspace_sources
                        )
                        
                        if not already_preserved:
                            # Check if this is a workspace name that was expanded
                            workspace_found = False
                            for browse_db in browse_databases:
                                if workspace_manager.validate_workspace(browse_db) and db_name.startswith(f"{browse_db}."):
                                    # This database came from workspace expansion - add with default days
                                    if default_days:
                                        source_with_days = f"{db_name}:{default_days}"
                                    else:
                                        source_with_days = db_name
                                    if source_with_days not in all_sources:
                                        all_sources.append(source_with_days)
                                    workspace_found = True
                                    break
                            
                            # If not from workspace expansion, add the database as-is
                            if not workspace_found and db_name not in all_sources and f"{db_name}:" not in str(all_sources):
                                all_sources.append(db_name)
                
                # Update context state
                context_state['sources'] = all_sources
                context_state['filters'] = original_filters
                
                # Update the original query format to the manually edited command
                context_state['original_query_format'] = user_input
                update_query_command()
                
                # Reload context with the updated information
                if reload_context():
                    print_text("Context updated successfully with mixed command!", style="green")
                    return True
                else:
                    print_text("❌ Failed to reload context after mixed command update", style="red")
                    return False
            
            # Handle case where browse databases exist but didn't change (or changed via reduction)
            elif browse_databases and not browse_changed:
                # Check if this is a scope reduction (databases removed from browse list)
                # In this case, we need to filter out sources and reload context
                if set(browse_databases) != set(original_browse_databases if original_browse_databases else []):
                    # Scope changed but browse_changed=False means it was a reduction
                    removed_databases = set(original_browse_databases) - set(browse_databases)
                    debug_print(f"Applying scope reduction: {removed_databases} removed")
                    
                    # Build the new browse scope - what databases/sources should be kept
                    # We need to check against the ACTUAL browse_selections, not all workspace databases
                    # Because when you go from "-b trass trass.tg" to "-b trass", trass.tg should be removed
                    # even though it's part of the trass workspace
                    
                    from promaia.config.workspaces import get_workspace_manager
                    workspace_manager = get_workspace_manager()
                    
                    # Determine which specific databases were in the OLD command but not in the NEW command
                    old_db_set = set()
                    new_db_set = set()
                    
                    for browse_db in original_browse_databases:
                        old_db_set.add(browse_db.split(':')[0])
                    
                    for browse_db in browse_databases:
                        new_db_set.add(browse_db.split(':')[0])
                    
                    removed_dbs = old_db_set - new_db_set
                    debug_print(f"Databases to remove: {removed_dbs}")
                    
                    # Filter sources: keep only those NOT from removed databases
                    current_sources = context_state.get('sources', []) or []
                    filtered_sources = []
                    for source in current_sources:
                        source_db = source.split(':')[0] if ':' in source else source
                        
                        # Check if this source's database is in the removed set
                        should_remove = False
                        for removed_db in removed_dbs:
                            if source_db == removed_db or source_db.startswith(f"{removed_db}."):
                                should_remove = True
                                break
                        
                        if not should_remove:
                            filtered_sources.append(source)
                        else:
                            debug_print(f"Removing source from removed database: {source}")
                    
                    # Update context_state with filtered sources
                    debug_print(f"Filtered sources after removal: {filtered_sources}")
                    context_state['sources'] = filtered_sources
                    context_state['original_query_format'] = user_input
                    
                    # Also update browse_selections to match
                    context_state['browse_selections'] = filtered_sources.copy()
                    
                    # CRITICAL: Also filter out any filters that apply to the removed databases
                    current_filters = context_state.get('filters', []) or []
                    if current_filters:
                        filtered_filters = []
                        for filter_expr in current_filters:
                            # Check if this filter applies to a removed database
                            # Filter format can be: "trass.tg:7:discord_channel_name=koii-work"
                            filter_db = filter_expr.split(':')[0] if ':' in filter_expr else filter_expr
                            
                            # Check if this filter's database is in the removed set
                            should_remove_filter = False
                            for removed_db in removed_dbs:
                                if filter_db == removed_db or filter_db.startswith(f"{removed_db}."):
                                    should_remove_filter = True
                                    break
                            
                            if not should_remove_filter:
                                filtered_filters.append(filter_expr)
                            else:
                                debug_print(f"Removing filter for removed database: {filter_expr}")
                        
                        context_state['filters'] = filtered_filters
                        debug_print(f"Filtered filters after removal: {filtered_filters}")
                    
                    update_query_command()
                    
                    if reload_context(skip_nl_cache_messages=True):
                        print_text("Context updated successfully after scope reduction!", style="green")
                        return True
                    else:
                        print_text("❌ Failed to reload context after scope reduction", style="red")
                        return False
                
                # Update only natural language context without re-launching browser
                if natural_language_content:
                    print_text("🔄 Updating natural language context (browse unchanged)...", style="dim")
                    context_state['natural_language_content'] = natural_language_content
                    context_state['natural_language_prompt'] = nl_prompt
                    
                    # Update the original query format to reflect the new natural language query
                    context_state['original_query_format'] = f"maia chat {user_input}"
                    update_query_command()
                    
                    # Reload context to apply the new natural language results
                    if reload_context(skip_nl_cache_messages=True):
                        print_text("Context updated successfully!", style="bold green")
                        return True
                    else:
                        print_text("❌ Failed to reload context with new natural language results", style="red")
                        return False
                elif nl_was_removed:
                    print_text("🔄 Removing natural language results from context...", style="cyan")
                    
                    # Update the original query format to reflect removal of natural language
                    context_state['original_query_format'] = f"maia chat {user_input}"
                    update_query_command()
                    
                    # Instead of full reload, just update the system prompt without NL content
                    # This preserves browser sources while removing NL results
                    try:
                        nonlocal initial_multi_source_data, total_pages_loaded
                        
                        # Get the current multi-source data
                        current_data = dict(initial_multi_source_data)
                        
                        # Build set of sources that should be kept based on browse selections
                        browse_selections = context_state.get('browse_selections', [])
                        sources_to_keep = set()
                        if browse_selections:
                            for browse_sel in browse_selections:
                                # Extract database name from selection (may include workspace prefix)
                                sources_to_keep.add(browse_sel.lower())
                        
                        # Remove sources that came from NL and are not in browser selections
                        keys_to_remove = []
                        for key in current_data.keys():
                            # Check if this source was loaded via natural language
                            is_from_nl = key in nl_sources_to_remove
                            
                            # Check if this source should be kept based on browser selections
                            should_keep = any(keep_src in key.lower() for keep_src in sources_to_keep) if sources_to_keep else False
                            
                            # Remove if it's from NL and not selected in browser
                            if is_from_nl and not should_keep:
                                keys_to_remove.append(key)
                                debug_print(f"Will remove NL source: {key} (not in browse selections: {sources_to_keep})")
                        
                        # Remove the identified keys
                        for key in keys_to_remove:
                            if key in current_data:
                                debug_print(f"Removing NL source from context: {key}")
                                del current_data[key]
                        
                        # Update the global variables with the cleaned data
                        initial_multi_source_data = current_data
                        total_pages_loaded = sum(len(pages) for pages in current_data.values())
                        
                        # Update context state as well
                        context_state['initial_multi_source_data'] = current_data
                        context_state['total_pages_loaded'] = total_pages_loaded
                        
                        # Update the system prompt with the remaining data
                        mcp_tools_info = context_state.get('mcp_tools_info')
                        system_prompt = create_system_prompt(current_data, mcp_tools_info)
                        context_state['system_prompt'] = system_prompt
                        
                        debug_print(f"After NL removal: {len(current_data)} sources, {total_pages_loaded} pages")
                        print_text("Context updated successfully!", style="bold green")
                        return True
                    except Exception as e:
                        print_text(f"❌ Error updating context after NL removal: {e}", style="red")
                        debug_print(f"NL removal error: {e}")
                        # Fall back to full reload if manual update fails
                        # Ensure NL state is still cleared before reload
                        context_state['natural_language_content'] = None
                        context_state['natural_language_prompt'] = None
                        context_state['cached_natural_language_prompt'] = ''
                        if reload_context(skip_nl_cache_messages=True):
                            print_text("Context updated successfully via reload!", style="bold green")
                            return True
                        else:
                            print_text("❌ Failed to reload context after removing natural language", style="red")
                            return False
                else:
                    print_text("ℹ️  No changes detected. Context unchanged.", style="yellow")
                    return False
            
            # Handle browse mode using unified browser - but only if browse part actually changed
            elif browse_databases and browse_changed:
                try:
                    from promaia.cli.workspace_browser import launch_unified_browser
                    
                    # Show what we're browsing
                    if database_filter:
                        if len(database_filter) == 1:
                            print_text(f"🔍 Launching unified browser for database: {database_filter[0]}...", style="cyan")
                        else:
                            print_text(f"🔍 Launching unified browser for databases: {', '.join(database_filter)}...", style="cyan")
                    elif multiple_workspaces:
                        print_text(f"🔍 Launching unified browser for workspaces: {', '.join(multiple_workspaces)}...", style="cyan")
                    elif resolved_workspace:
                        print_text(f"🔍 Launching unified browser for workspace '{resolved_workspace}'...", style="cyan")
                    else:
                        print_text("🔍 Launching unified browser...", style="cyan")
                    
                    # Get current sources for pre-population (handle mixed commands properly)
                    current_sources = []
                    
                    # Get what we have in context_state
                    stored_browser_selections = context_state.get('browse_selections', [])
                    current_regular_sources = context_state.get('sources', [])
                    
                    # Debug: Show what was retrieved
                    # debug_print(f"RETRIEVED stored_browser_selections: {stored_browser_selections}")
                    # debug_print(f"RETRIEVED current_regular_sources: {current_regular_sources}")
                    
                    # Ensure stored_browser_selections is never None to avoid iteration errors
                    if stored_browser_selections is None:
                        stored_browser_selections = []
                    
                    # For workspace browse commands (like -b trass), we want to default to ALL workspace sources selected
                    # BUT only if there are no existing browser selections (for persistence)
                    # Check if this is a workspace browse command by looking at the original format
                    is_workspace_browse = False
                    if original_format and '-b ' in original_format and workspace and not database_filter:
                        is_workspace_browse = True
                    
                    if is_workspace_browse:
                        # Check if we have previous browser selections
                        has_previous_selections = bool(stored_browser_selections)
                        
                        # Debug: Show the decision logic
                        # debug_print(f"is_workspace_browse: {is_workspace_browse}, has_previous_selections: {has_previous_selections}")
                        
                        if has_previous_selections:
                            # Filter stored selections to only include sources from the current workspace
                            # This prevents sources from other workspaces/databases from persisting
                            for sel in stored_browser_selections:
                                # Extract the database name from the selection
                                if '#' in sel:
                                    # Discord channel: trass.tg#channel-name:7
                                    db_name = sel.split('#')[0]
                                else:
                                    # Regular database: trass.journal:7
                                    db_name = sel.split(':')[0]
                                
                                # Only include if it belongs to the current workspace
                                if db_name.startswith(workspace + '.'):
                                    current_sources.append(sel)
                            
                            # Include regular sources that aren't part of this workspace
                            if current_regular_sources:
                                for source in current_regular_sources:
                                    source_db = source.split(':')[0] if ':' in source else source
                                    # Check if this source is from a different workspace
                                    if '.' in source_db:
                                        source_workspace = source_db.split('.')[0]
                                        if source_workspace != workspace:
                                            current_sources.append(source)
                                    else:
                                        # Non-workspace source (like journal:30), always include
                                        current_sources.append(source)
                        else:
                            # First time browsing workspace - default to all workspace databases
                            from promaia.config.databases import get_database_manager
                            db_manager = get_database_manager()
                            workspace_databases = db_manager.get_workspace_databases(workspace)
                            
                            # Add all workspace databases with their default days
                            for db in workspace_databases:
                                if db.sync_enabled:  # Only include enabled databases
                                    if default_days:
                                        source_with_days = f"{db.get_qualified_name()}:{default_days}"
                                    else:
                                        source_with_days = f"{db.get_qualified_name()}:7"  # Default to 7 days
                                    current_sources.append(source_with_days)
                            
                            # Include regular sources that aren't part of this workspace
                            if current_regular_sources:
                                for source in current_regular_sources:
                                    source_db = source.split(':')[0] if ':' in source else source
                                    # Check if this source is from a different workspace
                                    if '.' in source_db:
                                        source_workspace = source_db.split('.')[0]
                                        if source_workspace != workspace:
                                            current_sources.append(source)
                                    else:
                                        # Non-workspace source (like journal:30), always include
                                        current_sources.append(source)
                    else:
                        # For specific database browse or mixed commands, use existing logic
                        # First, get any stored Discord channel selections
                        if stored_browser_selections:
                            # Filter stored selections to only include sources that match the current browse scope
                            for sel in stored_browser_selections:
                                should_include = False
                                
                                # Extract the database name from the selection
                                if '#' in sel:
                                    # Discord channel: trass.tg#channel-name:7
                                    db_name = sel.split('#')[0]
                                else:
                                    # Regular database: trass.journal:7
                                    db_name = sel.split(':')[0]
                                
                                # Check if this selection matches the current browse scope
                                if database_filter:
                                    # If we have a database filter, check if the selection matches any filter item
                                    for filter_item in database_filter:
                                        filter_base = filter_item.split(':')[0]
                                        if db_name == filter_base or db_name.startswith(filter_base + '.'):
                                            should_include = True
                                            break
                                elif workspace:
                                    # If browsing a workspace, check if the selection belongs to that workspace
                                    if db_name.startswith(workspace + '.'):
                                        should_include = True
                                elif multiple_workspaces:
                                    # If browsing multiple workspaces, check if selection belongs to any of them
                                    for ws in multiple_workspaces:
                                        if db_name.startswith(ws + '.'):
                                            should_include = True
                                            break
                                
                                if should_include:
                                    current_sources.append(sel)
                        
                        # For mixed commands, we also need to include regular database sources
                        # Get current regular sources (but exclude those that are handled by Discord)
                        if current_regular_sources:
                            # Extract database names from Discord selections to avoid duplicates
                            discord_db_names = set()
                            for discord_sel in stored_browser_selections:
                                if '#' in discord_sel:
                                    db_name = discord_sel.split('#')[0]
                                    discord_db_names.add(db_name)
                            
                            # Add regular sources that aren't Discord databases
                            for source in current_regular_sources:
                                source_db = source.split(':')[0] if ':' in source else source
                                if source_db not in discord_db_names:
                                    current_sources.append(source)
                    
                    # Launch unified browser
                    # Handle multiple workspaces case
                    if multiple_workspaces and not resolved_workspace:
                        # For multiple workspaces, pass None as workspace and workspaces as database_filter
                        selected_sources = launch_unified_browser(
                            workspace=None,
                            default_days=default_days,
                            database_filter=multiple_workspaces,
                            current_sources=current_sources
                        )
                    else:
                        # Single workspace case
                        selected_sources = launch_unified_browser(
                            workspace=resolved_workspace,
                            default_days=default_days,
                            database_filter=database_filter,
                            current_sources=current_sources
                        )
                    
                    if not selected_sources:
                        print_text("ℹ️  No sources selected. Keeping current context unchanged.", style="yellow")
                        return False
                    
                    print_text(f"✅ Selected {len(selected_sources)} sources from unified browser", style="green")
                    
                    # Process Discord channel sources and convert to database + filter format (same logic as cli.py)
                    processed_sources = []
                    processed_filters = []
                    discord_db_groups = {}
                    
                    for source in selected_sources:
                        if '#' in source:
                            # Discord channel: trass.tg#customer-support:7
                            db_channel, days_part = source.rsplit(':', 1)
                            db_name, channel_name = db_channel.split('#', 1)
                            
                            # Group by database + days combination
                            db_key = f"{db_name}:{days_part}"
                            if db_key not in discord_db_groups:
                                discord_db_groups[db_key] = []
                            discord_db_groups[db_key].append(channel_name)
                        else:
                            # Regular database source
                            processed_sources.append(source)
                    
                    # Convert Discord groups to source + filter combinations
                    for db_spec, channels in discord_db_groups.items():
                        processed_sources.append(db_spec)
                        
                        # Create filter for channels
                        if len(channels) == 1:
                            # Single channel
                            filter_spec = f"{db_spec}:discord_channel_name={channels[0]}"
                            processed_filters.append(filter_spec)
                        else:
                            # Multiple channels - use OR logic
                            channel_conditions = [f"discord_channel_name={ch}" for ch in channels]
                            combined_filter = " or ".join(channel_conditions)
                            filter_spec = f"{db_spec}:({combined_filter})"
                            processed_filters.append(filter_spec)
                    
                    # Update context with processed sources and filters
                    # When browse scope changes, we need to handle sources intelligently:
                    # 1. Keep sources that are OUTSIDE the current browse scope (e.g., other workspaces)
                    # 2. Replace sources that are WITHIN the current browse scope with new selections
                    original_sources = context_state.get('sources', []) or []
                    final_sources = []

                    # Build set of database names that are IN the current browse scope
                    browse_scope_db_names = set()
                    
                    # Determine which databases are in scope for this browse operation
                    if database_filter:
                        # Specific database filter (e.g., -b trass.tg)
                        for filter_item in database_filter:
                            filter_base = filter_item.split(':')[0]
                            browse_scope_db_names.add(filter_base)
                            # Also add any databases that start with this prefix
                            # (e.g., if filter is "trass", include "trass.journal", "trass.tg", etc.)
                            if workspace:
                                from promaia.config.databases import get_database_manager
                                db_manager = get_database_manager()
                                workspace_databases = db_manager.get_workspace_databases(workspace)
                                for db in workspace_databases:
                                    db_name = db.get_qualified_name()
                                    if db_name.startswith(filter_base) or filter_base.startswith(db_name):
                                        browse_scope_db_names.add(db_name)
                    elif workspace:
                        # Workspace browse (e.g., -b trass) - all databases in the workspace are in scope
                        from promaia.config.databases import get_database_manager
                        db_manager = get_database_manager()
                        workspace_databases = db_manager.get_workspace_databases(workspace)
                        for db in workspace_databases:
                            browse_scope_db_names.add(db.get_qualified_name())
                    elif multiple_workspaces:
                        # Multiple workspaces - all databases in those workspaces are in scope
                        from promaia.config.databases import get_database_manager
                        db_manager = get_database_manager()
                        for ws in multiple_workspaces:
                            workspace_databases = db_manager.get_workspace_databases(ws)
                            for db in workspace_databases:
                                browse_scope_db_names.add(db.get_qualified_name())
                    
                    # Keep original sources that are OUTSIDE the current browse scope
                    for source in original_sources:
                        source_db = source.split(':')[0] if ':' in source else source
                        # Keep source only if it's NOT in the current browse scope
                        if source_db not in browse_scope_db_names:
                            final_sources.append(source)
                    
                    # Add the new browser selections (which are all within the browse scope)
                    final_sources.extend(processed_sources)
                    
                    context_state['sources'] = final_sources
                    context_state['filters'] = processed_filters
                    
                    # Store ALL browser selections for future /e preservation (not just Discord)
                    # This includes both regular database selections and Discord channel selections
                    if selected_sources:
                        context_state['browse_selections'] = selected_sources.copy()
                    
                    # For browse commands, use the manually edited command; for others, use reconstructed
                    if '-b ' in user_input:
                        # This was manually edited with browse arguments - use the new command
                        context_state['original_query_format'] = f"maia chat {user_input}"
                    else:
                        # Reconstruct command from current state
                        cmd_parts = ["maia", "chat"]
                        for source in processed_sources:
                            cmd_parts.extend(["-s", source])
                        for filter_expr in processed_filters:
                            cmd_parts.extend(["-f", filter_expr])
                        if workspace:
                            cmd_parts.extend(["-ws", workspace])
                        context_state['original_query_format'] = " ".join(cmd_parts)
                    
                    # Update the query command display to reflect the new state
                    update_query_command()
                    
                    # Reload context with the updated information
                    if reload_context():
                        print_text("Context updated successfully from unified browser!", style="green")
                        return True
                    else:
                        print_text("❌ Failed to reload context after browser selection", style="red")
                        return False
                            
                except Exception as e:
                    print_text(f"Error handling manual browse edit: {e}", style="bold red")
                    return False
        except Exception as e:
            print_text(f"Error handling manual browse edit: {e}", style="bold red")
            return False
    
    def handle_browse_in_edit_context():
        """Handle unified browse mode selection within edit context."""
        try:
            # Initialize variables
            database_filter = None
            default_days = None
            workspace = None
            multiple_workspaces = None

            # Always respect the stored selections as the primary source of truth for pre-population
            stored_browser_selections = context_state.get('browse_selections', [])

            # Parse the original command to determine the scope of the browser
            original_format = context_state.get('original_query_format', '')
            if '-b' in original_format:
                import shlex
                from promaia.config.workspaces import get_workspace_manager
                workspace_manager = get_workspace_manager()

                try:
                    # Try to parse with shlex, but handle quote errors gracefully
                    try:
                        parsed_args = shlex.split(original_format)
                    except ValueError as quote_error:
                        if "No closing quotation" in str(quote_error):
                            # Handle unclosed quotes by adding a closing quote
                            fixed_format = original_format + '"' if original_format.count('"') % 2 == 1 else original_format
                            parsed_args = shlex.split(fixed_format)
                        else:
                            raise quote_error
                    
                    browse_databases = []
                    i = 0
                    while i < len(parsed_args):
                        if parsed_args[i] == '-b':
                            i += 1
                            while i < len(parsed_args) and not parsed_args[i].startswith('-'):
                                browse_databases.append(parsed_args[i])
                                i += 1
                        else:
                            i += 1
                    
                    if browse_databases:
                        database_filter = browse_databases.copy()
                        
                        # Correctly identify workspaces from the full browse filter
                        workspace_names_found = []
                        for browse_spec in database_filter:
                            browse_name = browse_spec.split(':')[0]
                            if workspace_manager.validate_workspace(browse_name):
                                if browse_name not in workspace_names_found:
                                    workspace_names_found.append(browse_name)
                            elif '.' in browse_name:
                                potential_ws = browse_name.split('.')[0]
                                if workspace_manager.validate_workspace(potential_ws):
                                    if potential_ws not in workspace_names_found:
                                        workspace_names_found.append(potential_ws)
                        
                        if len(workspace_names_found) > 1:
                            workspace = None
                            multiple_workspaces = workspace_names_found
                        elif len(workspace_names_found) == 1:
                            workspace = workspace_names_found[0]

                        # Extract default_days without altering the main filter logic
                        for browse_spec in browse_databases:
                            if ':' in browse_spec:
                                try:
                                    days = int(browse_spec.rsplit(':', 1)[1])
                                    if default_days is None:
                                        default_days = days
                                except ValueError:
                                    continue
                except Exception as e:
                    print_text(f"Warning: Could not parse browse arguments from original format: {e}", style="yellow")

            # Fallback to context if not determined from original command
            if workspace is None and multiple_workspaces is None:
                workspace = context_state.get('resolved_workspace') or context_state.get('workspace')

            # If no workspace context, try to get the default
            if workspace is None and multiple_workspaces is None:
                from promaia.config.workspaces import get_workspace_manager
                workspace_manager = get_workspace_manager()
                workspace = workspace_manager.get_default_workspace()
            
            # Determine current sources for pre-populating the browser
            current_sources = []
            if stored_browser_selections:
                # Filter stored selections to only include sources that match the current browse scope
                # This prevents sources from previous browse scopes (e.g., trass.tg) from persisting
                # when browsing a different scope (e.g., just workspace 'trass')
                filtered_selections = []
                
                for sel in stored_browser_selections:
                    should_include = False
                    
                    # Extract the database name from the selection
                    if '#' in sel:
                        # Discord channel: trass.tg#channel-name:7
                        db_name = sel.split('#')[0]
                    else:
                        # Regular database: trass.journal:7
                        db_name = sel.split(':')[0]
                    
                    # Check if this selection matches the current browse scope
                    if database_filter:
                        # If we have a database filter, check if the selection matches any filter item
                        for filter_item in database_filter:
                            filter_base = filter_item.split(':')[0]
                            if db_name == filter_base or db_name.startswith(filter_base + '.'):
                                should_include = True
                                break
                    elif workspace:
                        # If browsing a workspace, check if the selection belongs to that workspace
                        if db_name.startswith(workspace + '.'):
                            should_include = True
                    elif multiple_workspaces:
                        # If browsing multiple workspaces, check if selection belongs to any of them
                        for ws in multiple_workspaces:
                            if db_name.startswith(ws + '.'):
                                should_include = True
                                break
                    
                    if should_include:
                        filtered_selections.append(sel)
                
                current_sources.extend(filtered_selections)
            else:
                # If no selections are stored, and it's a workspace browse, populate with all sources
                is_workspace_browse = bool(workspace and not database_filter)
                if is_workspace_browse:
                    from promaia.config.databases import get_database_manager
                    db_manager = get_database_manager()
                    workspace_databases = db_manager.get_workspace_databases(workspace)
                    for db in workspace_databases:
                        if db.sync_enabled:
                            days = default_days if default_days is not None else 7
                            current_sources.append(f"{db.get_qualified_name()}:{days}")

            # Display what we're browsing
            if database_filter:
                print_text(f"🔍 Launching unified browser for: {', '.join(database_filter)}...", style="cyan")
            elif multiple_workspaces:
                print_text(f"🔍 Launching unified browser for workspaces: {', '.join(multiple_workspaces)}...", style="cyan")
            elif workspace:
                print_text(f"🔍 Launching unified browser for workspace '{workspace}'...", style="cyan")
            else:
                print_text("Error: No workspace available for browse mode.", style="bold red")
                return False

            # Launch unified browser
            from promaia.cli.workspace_browser import launch_unified_browser
            
            # Handle multiple workspaces case
            if multiple_workspaces and not workspace:
                # For multiple workspaces, pass None as workspace and workspaces as database_filter
                selected_sources = launch_unified_browser(
                    workspace=None,
                    default_days=default_days,
                    database_filter=multiple_workspaces,
                    current_sources=current_sources
                )
            else:
                # Single workspace case
                selected_sources = launch_unified_browser(
                    workspace=workspace,
                    default_days=default_days,
                    database_filter=database_filter,
                    current_sources=current_sources
                )
            
            if not selected_sources:
                print_text("ℹ️  No sources selected. Keeping current context unchanged.", style="yellow")
                return False
            
            print_text(f"✅ Selected {len(selected_sources)} sources from unified browser", style="green")

            # Process selections and update context
            processed_sources, processed_filters = process_browser_selections(selected_sources)
            
            # When browse scope changes, we need to handle sources intelligently:
            # 1. Keep sources that are OUTSIDE the current browse scope (e.g., other workspaces)
            # 2. Replace sources that are WITHIN the current browse scope with new selections
            original_sources = context_state.get('sources', []) or []
            final_sources = []

            # Build set of database names that are IN the current browse scope
            browse_scope_db_names = set()
            
            # Determine which databases are in scope for this browse operation
            if database_filter:
                # Specific database filter (e.g., -b trass.tg)
                for filter_item in database_filter:
                    filter_base = filter_item.split(':')[0]
                    browse_scope_db_names.add(filter_base)
                    # Also add any databases that start with this prefix
                    if workspace:
                        from promaia.config.databases import get_database_manager
                        db_manager = get_database_manager()
                        workspace_databases = db_manager.get_workspace_databases(workspace)
                        for db in workspace_databases:
                            db_name = db.get_qualified_name()
                            if db_name.startswith(filter_base) or filter_base.startswith(db_name):
                                browse_scope_db_names.add(db_name)
            elif workspace:
                # Workspace browse (e.g., -b trass) - all databases in the workspace are in scope
                from promaia.config.databases import get_database_manager
                db_manager = get_database_manager()
                workspace_databases = db_manager.get_workspace_databases(workspace)
                for db in workspace_databases:
                    browse_scope_db_names.add(db.get_qualified_name())
            elif multiple_workspaces:
                # Multiple workspaces - all databases in those workspaces are in scope
                from promaia.config.databases import get_database_manager
                db_manager = get_database_manager()
                for ws in multiple_workspaces:
                    workspace_databases = db_manager.get_workspace_databases(ws)
                    for db in workspace_databases:
                        browse_scope_db_names.add(db.get_qualified_name())
            
            # Keep original sources that are OUTSIDE the current browse scope
            for source in original_sources:
                source_db = source.split(':')[0] if ':' in source else source
                # Keep source only if it's NOT in the current browse scope
                if source_db not in browse_scope_db_names:
                    final_sources.append(source)
            
            # Add the new browser selections (which are all within the browse scope)
            final_sources.extend(processed_sources)
            
            # Update context state with merged sources
            context_state['sources'] = final_sources
            context_state['filters'] = processed_filters
            context_state['browse_selections'] = selected_sources.copy()
            
            # Don't overwrite the original command format - preserve user's browser selections
            # The original_query_format should maintain the user's initial command structure
            # Only update if we don't have an existing format, or if we need to maintain consistency
            if not context_state.get('original_query_format'):
                # Only set if we don't have one already
                cmd_parts = ["maia", "chat", "-b"]
                cmd_parts.extend(database_filter if database_filter else [workspace] if workspace else multiple_workspaces)
                context_state['original_query_format'] = " ".join(cmd_parts)
            update_query_command()
            
            # Reload context with updated info - preserve NL cache since only browse changed
            if reload_context(skip_nl_cache_messages=True):
                print_text("Context updated successfully from unified browser!", style="green")
                return True
            else:
                print_text("❌ Failed to reload context after browser selection", style="red")
                return False
                
        except Exception as e:
            print_text(f"Error in browse mode: {e}", style="bold red")
            debug_print(f"Browse error: {traceback.format_exc()}")
            return False

    def handle_recents_in_edit_context():
        """Handle recents selection within edit context."""
        from promaia.chat.recents_interface import RecentsSelector
        
        try:
            selector = RecentsSelector()
            action, selected_query = selector.select_query()
            
            if action == 'quit' or not selected_query:
                print_text("No recent selected.", style="bold yellow")
                return False
            
            if action in ['execute', 'edit']:
                # Extract the command components from the selected query
                if action == 'edit':
                    from promaia.chat.recents_interface import edit_query_string
                    edited_query = edit_query_string(selected_query)
                    if not edited_query:
                        print_text("Edit cancelled.", style="bold yellow")
                        return False
                    selected_query = edited_query
                
                # Check if this is a natural language query
                if hasattr(selected_query, 'natural_language_prompt') and selected_query.natural_language_prompt:
                    # Natural language query - process it
                    try:
                        from promaia.storage.unified_query import get_query_interface
                        
                        # Determine workspace to use
                        workspace = context_state.get('resolved_workspace') or context_state.get('workspace')
                        if not workspace:
                            from promaia.config.workspaces import get_workspace_manager
                            workspace_manager = get_workspace_manager()
                            workspace = workspace_manager.get_default_workspace()
                        
                        if not workspace:
                            print_text("Error: No workspace available for natural language query.", style="bold red")
                            return False
                        
                        print_text(f"🤖 Processing natural language query from recent: '{selected_query.natural_language_prompt}'", style="dim")
                        
                        # Process the natural language query
                        query_interface = get_query_interface()
                        
                        # Extract database names from browse selections if available
                        database_names = None
                        if context_state.get('browse_selections'):
                            from promaia.cli import extract_database_names_from_sources
                            database_names = extract_database_names_from_sources(context_state['browse_selections'])
                            
                        natural_language_content = query_interface.natural_language_query(
                            selected_query.natural_language_prompt, workspace, database_names
                        )
                        
                        if not natural_language_content:
                            print_text("❌ No content found for natural language query", style="bold red")
                            return False
                        
                        # Update context state for natural language mode
                        context_state['natural_language_content'] = natural_language_content
                        context_state['natural_language_prompt'] = selected_query.natural_language_prompt
                        context_state['sources'] = []  # Clear regular sources
                        context_state['filters'] = []  # Clear regular filters
                        
                        # Reload with natural language content
                        if reload_context():
                            query_desc = f"Recent NL: {selected_query.natural_language_prompt}"
                            if action == 'edit':
                                query_desc = f"Edited recent NL: {selected_query.natural_language_prompt}"
                            print_text(f"Context updated from {query_desc.lower()}", style="bold green")
                            return True
                        else:
                            print_text("Failed to reload context with natural language content.", style="bold red")
                            return False
                    
                    except Exception as e:
                        print_text(f"Error processing natural language query: {e}", style="bold red")
                        return False
                else:
                    # Traditional query - update context state with the selected query
                    context_state['sources'] = selected_query.sources or []
                    context_state['filters'] = selected_query.filters or []
                    if selected_query.workspace:
                        context_state['workspace'] = selected_query.workspace
                    
                    # Clear natural language state
                    context_state['natural_language_content'] = None
                    context_state['natural_language_prompt'] = None
                    
                    # Reload context with the new settings
                    if reload_context():
                        query_desc = f"Recent: {selected_query}"
                        if action == 'edit':
                            query_desc = f"Edited recent: {selected_query}"
                        print_text(f"Context updated from {query_desc.lower()}", style="bold green")
                        return True
                    else:
                        print_text("Failed to reload context with recent query.", style="bold red")
                        return False
            
        except Exception as e:
            print_text(f"Error accessing recents: {e}", style="bold red")
            debug_print(f"Recents error: {e}")
            return False

    # Declare variables that will be used in the nested function
    initial_multi_source_data = {}
    total_pages_loaded = 0
    system_prompt = None

    # Initial context load
    if not reload_context():
        return

    # Save initial context log
    save_context_log(context_state, system_prompt, total_pages_loaded, current_api, "session_init")

    # MCP Tool Execution Functions
    async def execute_mcp_tools_in_response(response_text: str) -> str:
        """Execute any MCP tools found in the AI response and return updated response."""
        mcp_executor = context_state.get('mcp_executor')
        
        if not mcp_executor:
            return response_text
        
        # Check if there are tool calls in the response
        if not mcp_executor.has_tool_calls(response_text):
            return response_text
        
        try:
            # Parse tool calls from the response
            tool_calls = mcp_executor.parse_tool_calls(response_text)
            
            if not tool_calls:
                return response_text
            
            print_text(f"🔧 Executing {len(tool_calls)} tool call(s)...", style="bold cyan")
            
            # Execute the tools
            results = await mcp_executor.execute_tool_calls(tool_calls)
            
            # Format the results
            results_text = mcp_executor.format_tool_results(results, show_raw=DEBUG_MODE)
            
            # Add results to the response
            updated_response = response_text + "\n" + results_text
            
            return updated_response
            
        except Exception as e:
            error_text = f"\n❌ Error executing MCP tools: {e}"
            return response_text + error_text

    # Display Welcome Message
    print()
    print_welcome_message(query_command=query_command, total_pages=total_pages_loaded, model_name=get_current_model_name(), source_breakdown=generate_source_breakdown(initial_multi_source_data))

    # Handle Non-interactive Mode
    if non_interactive:
        return

    # Start Interactive Chat Loop
    messages = initial_messages.copy() if initial_messages else []
    
    # If loading from history, display the previous conversation
    if initial_messages:
        print_text("--- Previous Conversation ---", style="bold yellow")
        for msg in initial_messages:
            role = msg.get('role', '')
            content = msg.get('content', '')
            if role == 'user':
                print_text(f"You: {content}", style="bold cyan")
            elif role == 'assistant':
                print_markdown(f"**Maia:** {content}")
        print_text("--- Continuing Conversation ---", style="bold yellow")
        print()

    while True:
        try:
            user_input = session.prompt("You: ", style=style)

            if user_input.strip().lower() in ['/quit', '/exit']:
                print_text("Goodbye!", style="bold cyan")
                break
            elif user_input.strip().lower() == '/debug':
                DEBUG_MODE = not DEBUG_MODE
                status = "enabled" if DEBUG_MODE else "disabled"
                print_text(f"Debug mode {status}.", style="bold yellow")
                continue
            elif user_input.strip().lower() == '/push':
                try:
                    import asyncio
                    result = asyncio.run(push_chat_to_notion(messages))
                    print_text(result, style="bold green")
                except Exception as e:
                    print_text(f"Error pushing to Notion: {e}", style="bold red")
                continue
            elif user_input.strip().lower() == '/s':
                # Sync current context databases
                try:
                    import asyncio
                    asyncio.run(sync_current_context_databases())
                    print_text("Context databases synced successfully. Reloading context...", style="bold green")
                    if reload_context():
                        print()
                        # Show the same detailed breakdown as when starting a new chat
                        print_welcome_message(
                            query_command=context_state['query_command'], 
                            total_pages=total_pages_loaded, 
                            model_name=get_current_model_name(), 
                            source_breakdown=generate_source_breakdown(initial_multi_source_data)
                        )
                        # Save context log for sync-triggered update
                        save_context_log(context_state, system_prompt, total_pages_loaded, current_api, "context_sync")
                    else:
                        print_text("Failed to reload context after sync.", style="bold red")
                except Exception as e:
                    print_text(f"Error syncing context databases: {e}", style="bold red")
                    debug_print(f"Sync error details: {e}")
                continue

            elif user_input.strip().lower() == '/e':
                # Edit context
                try:
                    if edit_context():
                        print()
                        
                        # Save the updated command to recents
                        try:
                            recents_manager = RecentsManager()
                            current_sources = context_state.get('sources', [])
                            current_filters = context_state.get('filters', [])
                            current_workspace = context_state.get('workspace')
                            current_nl_prompt = context_state.get('natural_language_prompt')
                            # Clean up extra spaces in natural language prompt
                            if current_nl_prompt:
                                current_nl_prompt = ' '.join(current_nl_prompt.split())
                            current_browse_command = context_state.get('original_query_format')
                            
                            # Only save if we have meaningful content to save
                            if current_sources or current_filters or current_nl_prompt or current_browse_command:
                                recents_manager.add_query(
                                    sources=current_sources,
                                    filters=current_filters,
                                    workspace=current_workspace,
                                    natural_language_prompt=current_nl_prompt,
                                    original_browse_command=current_browse_command
                                )
                        except Exception as e:
                            # Don't let recents saving errors break the flow
                            debug_print(f"Failed to save updated command to recents: {e}")
                        
                        # Show the same detailed breakdown as when starting a new chat
                        print_welcome_message(
                            query_command=context_state['query_command'], 
                            total_pages=total_pages_loaded, 
                            model_name=get_current_model_name(), 
                            source_breakdown=generate_source_breakdown(initial_multi_source_data)
                        )
                        # Save context log for edit-triggered update
                        save_context_log(context_state, system_prompt, total_pages_loaded, current_api, "context_edit")
                        # Keep debug info if needed
                        if DEBUG_MODE:
                            print_text(f"Debug: System prompt length: {len(system_prompt)}", style="dim")
                            print_text(f"Debug: Sources in context_state: {context_state.get('sources')}", style="dim")
                            print_text(f"Debug: Multi-source data keys: {list(initial_multi_source_data.keys())}", style="dim")
                    else:
                        print_text("Context editing cancelled.", style="bold yellow")
                except Exception as e:
                    print_text(f"Error editing context: {e}", style="bold red")
                    debug_print(f"Context edit error: {e}")
                continue
            elif user_input.strip().lower() == '/help':
                print_help_message(query_command=query_command, total_pages=total_pages_loaded, model_name=get_current_model_name(), source_breakdown=generate_source_breakdown(initial_multi_source_data))
                continue
            elif user_input.strip().lower().startswith('/image'):
                # Handle multiple image attachments
                try:
                    parts = user_input.strip().split(' ', 1)
                    if len(parts) < 2:
                        print_text("Usage: /image <path1> [path2] [path3] ... [optional message]", style="bold yellow")
                        print_text("Example: /image /path/to/photo1.jpg /path/to/photo2.png What do you see in these images?", style="dim")
                        continue
                    
                    image_part = parts[1].strip()
                    
                    # Parse multiple image paths and message
                    image_paths, message_text = _parse_image_paths_and_message(image_part)
                    
                    if not image_paths:
                        print_text("No valid image paths found.", style="bold red")
                        continue
                    
                    # Process the images
                    from promaia.utils.image_processing import (
                        encode_image_from_path, is_vision_supported, get_model_image_limits
                    )
                    
                    # Check if current model supports vision
                    if not is_vision_supported(current_api):
                        print_text(f"Current model '{current_api}' does not support image inputs.", style="bold red")
                        print_text("Try switching to a vision-capable model with '/model'.", style="dim")
                        continue
                    
                    # Get model limits
                    model_limits = get_model_image_limits(current_api)
                    max_images = model_limits['max_images']
                    
                    # Limit images to model capacity
                    if len(image_paths) > max_images:
                        print_text(f"⚠️  {current_api.title()} supports max {max_images} images. Processing first {max_images} images.", style="bold yellow")
                        image_paths = image_paths[:max_images]
                    
                    # Encode all images
                    current_images = []
                    successful_paths = []
                    
                    for image_path in image_paths:
                        try:
                            encoded_image = encode_image_from_path(image_path)
                            current_images.append(encoded_image)
                            successful_paths.append(image_path)
                            print_text(f"📸 Image loaded: {image_path}", style="bold green")
                        except Exception as img_error:
                            print_text(f"❌ Failed to load image: {image_path} - {img_error}", style="bold red")
                    
                    if not current_images:
                        print_text("No images were successfully loaded.", style="bold red")
                        continue
                    
                    # Prompt for message if none provided
                    if not message_text:
                        message_text = session.prompt("Message (optional): ", style=style).strip()
                    
                    # Prepare message with images
                    user_input = message_text  # Set the text part
                    img_word = "image" if len(current_images) == 1 else "images"
                    print_text(f"📸 Processing {len(current_images)} {img_word} with {current_api.title()}...", style="bold green")
                    
                except Exception as e:
                    print_text(f"Error processing images: {e}", style="bold red")
                    continue
            elif user_input.strip().lower().startswith('/model'):
                # Switch AI model
                input_parts = user_input.strip().split(' ', 1)
                target_model = input_parts[1] if len(input_parts) > 1 else None
                
                if switch_model(target_model):
                    # Show updated model info
                    print_text(f"Now using: {get_current_model_name()}", style="bold cyan")
                continue
            elif user_input.strip().lower().startswith('/save'):
                # Save current conversation to history
                if not messages:
                    print_text("No conversation to save.", style="bold yellow")
                    continue
                
                try:
                    history_manager = ChatHistoryManager()
                    
                    # Extract custom name if provided: /save "My Custom Name"
                    input_parts = user_input.strip().split(' ', 1)
                    custom_name = None
                    if len(input_parts) > 1:
                        custom_name = input_parts[1].strip().strip('"\'')
                    
                    # Prepare context for saving
                    thread_context = {
                        'sources': context_state.get('sources'),
                        'filters': context_state.get('filters'),
                        'workspace': context_state.get('workspace'),
                        'resolved_workspace': context_state.get('resolved_workspace'),
                        'query_command': context_state.get('query_command'),
                        'natural_language_prompt': context_state.get('natural_language_prompt'),
                        'natural_language_content': context_state.get('natural_language_content'),  # Save the actual content for faster restore
                        'original_query_format': context_state.get('original_query_format'),  # Save original browse command
                        'browse_selections': context_state.get('browse_selections')  # Save browse selections for re-editing
                    }
                    
                    # Check if we're continuing an existing thread
                    current_thread_id = context_state.get('current_thread_id')
                    if current_thread_id:
                        # Update existing thread
                        success = history_manager.update_thread(
                            thread_id=current_thread_id,
                            messages=messages,
                            context=thread_context,
                            thread_name=custom_name
                        )
                        
                        if success:
                            updated_thread = history_manager.get_thread(current_thread_id)
                            if updated_thread:
                                print_text(f"Conversation updated: {updated_thread.name}", style="bold green")
                            else:
                                print_text("Conversation updated successfully!", style="bold green")
                        else:
                            print_text("Error: Could not find thread to update. Creating new thread instead.", style="bold yellow")
                            # Fallback to creating new thread
                            thread_id = history_manager.save_thread(
                                messages=messages,
                                context=thread_context,
                                thread_name=custom_name
                            )
                            context_state['current_thread_id'] = thread_id
                            saved_thread = history_manager.get_thread(thread_id)
                            if saved_thread:
                                print_text(f"New conversation saved as: {saved_thread.name}", style="bold green")
                    else:
                        # Create new thread
                        thread_id = history_manager.save_thread(
                            messages=messages,
                            context=thread_context,
                            thread_name=custom_name
                        )
                        
                        # Update context to track this thread for future saves
                        context_state['current_thread_id'] = thread_id
                        
                        # Get the saved thread to show the generated name
                        saved_thread = history_manager.get_thread(thread_id)
                        if saved_thread:
                            print_text(f"Conversation saved as: {saved_thread.name}", style="bold green")
                        else:
                            print_text("Conversation saved successfully!", style="bold green")
                        
                except Exception as e:
                    print_text(f"Error saving conversation: {e}", style="bold red")
                    debug_print(f"Save error details: {e}")
                continue
            elif user_input.strip().lower() == '/mcp search':
                # Toggle internet search functionality
                current_search = context_state.get('enable_search', False)
                context_state['enable_search'] = not current_search

                if context_state['enable_search']:
                    # Enable search - add search MCP server if not already present
                    if 'search' not in (context_state.get('mcp_servers') or []):
                        if context_state.get('mcp_servers') is None:
                            context_state['mcp_servers'] = ['search']
                        else:
                            context_state['mcp_servers'].append('search')

                        # Reconnect MCP servers to include search
                        if context_state.get('mcp_client'):
                            try:
                                # Disconnect existing servers
                                import asyncio
                                asyncio.run(context_state['mcp_client'].disconnect_all())

                                # Reconnect with search server included
                                from promaia.config.mcp_servers import get_mcp_manager
                                from promaia.mcp.client import McpClient
                                from promaia.mcp.execution import McpToolExecutor

                                mcp_manager = get_mcp_manager()
                                mcp_client = McpClient()

                                connected_servers = []
                                for server_name in context_state['mcp_servers']:
                                    server_config = mcp_manager.get_server(server_name)
                                    if server_config:
                                        success = asyncio.run(mcp_client.connect_to_server(server_config))
                                        if success:
                                            connected_servers.append(server_name)

                                # Update context with new MCP client
                                context_state['mcp_client'] = mcp_client
                                context_state['mcp_executor'] = McpToolExecutor(mcp_client)

                                # Update system prompt with new tools
                                mcp_tools_info = mcp_client.format_tools_for_prompt(connected_servers, compact=True)
                                context_state['mcp_tools_info'] = mcp_tools_info

                                # Regenerate system prompt with new tools
                                system_prompt = create_system_prompt(initial_multi_source_data, mcp_tools_info)
                                context_state['system_prompt'] = system_prompt

                                # Save context log when MCP servers are connected (for transparency)
                                save_context_log(context_state, system_prompt, total_pages_loaded, current_api, "mcp_connection")

                                print_text("🔍 Internet search enabled and MCP servers reconnected!", style="bold green")
                                print_text("💡 You can now ask the AI to search the web by saying things like:", style="cyan")
                                print_text("   'search the web for information about X' or 'find Y online'", style="dim cyan")
                            except Exception as e:
                                print_text(f"Error reconnecting MCP servers: {e}", style="bold red")
                        else:
                            # Connect to MCP servers for the first time
                            try:
                                import asyncio
                                from promaia.config.mcp_servers import get_mcp_manager
                                from promaia.mcp.client import McpClient
                                from promaia.mcp.execution import McpToolExecutor

                                mcp_manager = get_mcp_manager()
                                mcp_client = McpClient()

                                # Connect to search server
                                connected_servers = []
                                for server_name in context_state.get('mcp_servers', []):
                                    server_config = mcp_manager.get_server(server_name)
                                    if server_config:
                                        success = asyncio.run(mcp_client.connect_to_server(server_config))
                                        if success:
                                            connected_servers.append(server_name)

                                if connected_servers:
                                    # Update context with new MCP client
                                    context_state['mcp_client'] = mcp_client
                                    context_state['mcp_executor'] = McpToolExecutor(mcp_client)

                                    # Update system prompt with new tools
                                    mcp_tools_info = mcp_client.format_tools_for_prompt(connected_servers, compact=True)
                                    context_state['mcp_tools_info'] = mcp_tools_info

                                    # Regenerate system prompt with new tools
                                    system_prompt = create_system_prompt(initial_multi_source_data, mcp_tools_info)
                                    context_state['system_prompt'] = system_prompt

                                    # Save context log when MCP servers are connected (for transparency)
                                    save_context_log(context_state, system_prompt, total_pages_loaded, current_api, "mcp_connection")

                                    print_text("🔍 Internet search enabled and MCP servers connected!", style="bold green")
                                    print_text("💡 You can now ask the AI to search the web by saying things like:", style="cyan")
                                    print_text("   'search the web for information about X' or 'find Y online'", style="dim cyan")
                                else:
                                    print_text("🔍 Internet search enabled but no servers connected", style="bold yellow")
                            except Exception as e:
                                print_text(f"Error connecting MCP servers: {e}", style="bold red")
                    else:
                        print_text("🔍 Internet search enabled", style="bold green")
                else:
                    # Disable search - remove search MCP server
                    if context_state.get('mcp_servers') and 'search' in context_state['mcp_servers']:
                        context_state['mcp_servers'].remove('search')

                        # Reconnect MCP servers without search
                        if context_state.get('mcp_client'):
                            try:
                                import asyncio
                                from promaia.config.mcp_servers import get_mcp_manager
                                from promaia.mcp.client import McpClient
                                from promaia.mcp.execution import McpToolExecutor

                                # Disconnect existing servers
                                asyncio.run(context_state['mcp_client'].disconnect_all())

                                # Reconnect without search server
                                mcp_manager = get_mcp_manager()
                                mcp_client = McpClient()

                                connected_servers = []
                                for server_name in context_state['mcp_servers']:
                                    server_config = mcp_manager.get_server(server_name)
                                    if server_config:
                                        success = asyncio.run(mcp_client.connect_to_server(server_config))
                                        if success:
                                            connected_servers.append(server_name)

                                # Update context with new MCP client
                                context_state['mcp_client'] = mcp_client
                                context_state['mcp_executor'] = McpToolExecutor(mcp_client)

                                # Update system prompt with new tools
                                mcp_tools_info = mcp_client.format_tools_for_prompt(connected_servers, compact=True)
                                context_state['mcp_tools_info'] = mcp_tools_info

                                # Regenerate system prompt with new tools
                                system_prompt = create_system_prompt(initial_multi_source_data, mcp_tools_info)
                                context_state['system_prompt'] = system_prompt

                                print_text("🔍 Internet search disabled and MCP servers reconnected", style="bold yellow")
                            except Exception as e:
                                print_text(f"Error reconnecting MCP servers: {e}", style="bold red")
                        else:
                            # Update MCP tools info even without reconnection
                            from promaia.config.mcp_servers import get_mcp_manager
                            from promaia.mcp.client import McpClient
                            mcp_manager = get_mcp_manager()
                            mcp_client = McpClient()

                            # Get tools info for current servers
                            connected_servers = context_state.get('mcp_servers', [])
                            mcp_tools_info = mcp_client.format_tools_for_prompt(connected_servers, compact=True)
                            context_state['mcp_tools_info'] = mcp_tools_info

                            # Regenerate system prompt with new tools
                            system_prompt = create_system_prompt(initial_multi_source_data, mcp_tools_info)
                            context_state['system_prompt'] = system_prompt

                            print_text("🔍 Internet search disabled - web search tools removed", style="bold yellow")
                    else:
                        print_text("🔍 Internet search disabled", style="bold yellow")

                continue

            if not user_input.strip():
                continue

            # Initialize current_images if not set (for non-image commands)
            if 'current_images' not in locals():
                current_images = []
            
            # Auto-detect image paths in regular messages (if no images already set)
            if not current_images:
                cleaned_message, detected_paths = _detect_image_paths_in_message(user_input.strip())
                
                if detected_paths:
                    try:
                        from promaia.utils.image_processing import (
                            encode_image_from_path, is_vision_supported, get_model_image_limits
                        )
                        
                        # Check if current model supports vision
                        if not is_vision_supported(current_api):
                            print_text(f"📸 Detected {len(detected_paths)} image path(s) but {current_api} doesn't support images.", style="bold yellow")
                            print_text("Try switching to a vision-capable model with '/model' or use text-only.", style="dim")
                        else:
                            # Get model limits
                            model_limits = get_model_image_limits(current_api)
                            max_images = model_limits['max_images']
                            
                            # Limit images to model capacity
                            if len(detected_paths) > max_images:
                                print_text(f"📸 Detected {len(detected_paths)} images, but {current_api.title()} supports max {max_images}. Processing first {max_images}.", style="bold yellow")
                                detected_paths = detected_paths[:max_images]
                            
                            # Try to encode detected images
                            successful_images = []
                            
                            for image_path in detected_paths:
                                try:
                                    if os.path.exists(image_path):
                                        encoded_image = encode_image_from_path(image_path)
                                        successful_images.append(encoded_image)
                                    else:
                                        print_text(f"📸 Image path not found: {image_path}", style="dim yellow")
                                except Exception as img_error:
                                    print_text(f"❌ Failed to load detected image: {image_path} - {img_error}", style="bold red")
                            
                            if successful_images:
                                current_images = successful_images
                                user_input = cleaned_message  # Use cleaned message without image paths
                                
                    except Exception as e:
                        print_text(f"Error processing detected images: {e}", style="bold red")
                        # Continue with original message
                        pass
            
            # Prepare message with potential images
            if current_images:
                debug_print(f"Processing message with {len(current_images)} images")
            
            messages.append({"role": "user", "content": user_input, "images": current_images})

            # Call the appropriate API
            response_content = None
            try:
                if DEBUG_MODE:
                    debug_print(f"AI Call Debug: System prompt length: {len(system_prompt)}")
                    debug_print(f"AI Call Debug: Total pages in context: {total_pages_loaded}")
                    debug_print(f"AI Call Debug: Context sources: {context_state.get('sources')}")
                
                # Check for images in current message
                current_message_images = []
                if messages and "images" in messages[-1]:
                    current_message_images = messages[-1].get("images", [])
                    if current_message_images:
                        img_word = "image" if len(current_message_images) == 1 else "images"
                        print_text(f"📸 Processing {len(current_message_images)} {img_word} with {current_api.title()}...", style="bold green")
                        
                    # Clean messages for existing handlers (but keep full messages for image processing)
                    clean_messages = []
                    for msg in messages:
                        clean_msg = {"role": msg["role"], "content": msg["content"]}
                        clean_messages.append(clean_msg)
                    messages_for_api = messages  # Keep full messages for image handlers
                else:
                    messages_for_api = messages

                # Direct API calls (streaming removed for reliability)
                if current_api == "anthropic" and anthropic_client:
                    if current_message_images:
                        # Handle images with Anthropic
                        formatted_messages = _format_anthropic_with_images(messages_for_api, current_message_images)
                        response = call_anthropic_with_retry(anthropic_client, system_prompt, formatted_messages)
                    else:
                        # Regular text-only message - clean messages to remove extra fields
                        clean_messages = []
                        for msg in messages_for_api:
                            clean_msg = {"role": msg["role"], "content": msg["content"]}
                            clean_messages.append(clean_msg)
                        response = call_anthropic_with_retry(anthropic_client, system_prompt, clean_messages)
                    if response and response.content:
                        response_text = response.content[0].text

                        # Execute MCP tools if present
                        import asyncio
                        response_text = asyncio.run(execute_mcp_tools_in_response(response_text))

                        # Extract token usage for Anthropic
                        if hasattr(response, 'usage'):
                            input_tokens = response.usage.input_tokens
                            output_tokens = response.usage.output_tokens
                            total_tokens = input_tokens + output_tokens

                            # Calculate cost using centralized function
                            from promaia.utils.ai import calculate_ai_cost
                            debug_print(f"Cost calculation: input_tokens={input_tokens}, output_tokens={output_tokens}")
                            cost_data = calculate_ai_cost(input_tokens, output_tokens, "claude-sonnet-4")
                            total_cost = cost_data["total_cost"]
                            debug_print(f"Calculated cost: ${total_cost:.6f}")

                            debug_print(f"Token usage: {input_tokens:,} input + {output_tokens:,} output = {total_tokens:,} total")

                            response_content = {
                                'text': response_text,
                                'tokens': {
                                    'prompt_tokens': input_tokens,
                                    'response_tokens': output_tokens,
                                    'total_tokens': total_tokens,
                                    'cost': total_cost,
                                    'model': 'Claude 3 Sonnet'
                                }
                            }
                        else:
                            response_content = {
                                'text': response_text,
                                'tokens': None
                            }
                elif current_api == "openai" and openai_client:
                    if current_message_images:
                        # Handle images with OpenAI
                        formatted_messages = _format_openai_with_images(system_prompt, messages_for_api, current_message_images)
                    else:
                        # Regular text-only message
                        formatted_messages = [{"role": "system", "content": system_prompt}] + messages_for_api
                    
                    response = openai_client.chat.completions.create(
                        model="gpt-4o",
                        messages=formatted_messages,
                        max_tokens=4096,
                        temperature=0.7
                    )
                    if response.choices:
                        response_text = response.choices[0].message.content

                        # Execute MCP tools if present
                        import asyncio
                        response_text = asyncio.run(execute_mcp_tools_in_response(response_text))

                        # Extract token usage for OpenAI
                        if hasattr(response, 'usage') and response.usage:
                            prompt_tokens = response.usage.prompt_tokens
                            completion_tokens = response.usage.completion_tokens
                            total_tokens = response.usage.total_tokens

                            # Calculate cost using centralized function
                            from promaia.utils.ai import calculate_ai_cost
                            cost_data = calculate_ai_cost(prompt_tokens, completion_tokens, "gpt-4o")
                            total_cost = cost_data["total_cost"]

                            debug_print(f"Token usage: {prompt_tokens:,} prompt + {completion_tokens:,} completion = {total_tokens:,} total")

                            response_content = {
                                'text': response_text,
                                'tokens': {
                                    'prompt_tokens': prompt_tokens,
                                    'response_tokens': completion_tokens,
                                    'total_tokens': total_tokens,
                                    'cost': total_cost,
                                    'model': 'GPT-4'
                                }
                            }
                        else:
                            response_content = {
                                'text': response_text,
                                'tokens': None
                            }
                elif current_api == "gemini" and gemini_client:
                    response_text_with_tools = None
                    try:
                        if current_message_images:
                            # Handle images with Gemini
                            current_gemini_model, gemini_messages = _format_gemini_with_images(system_prompt, messages_for_api, current_message_images)
                            response = current_gemini_model.generate_content(
                                contents=gemini_messages,
                                generation_config={
                                    "temperature": 0.7,
                                }
                            )
                        else:
                            # Regular text-only message
                            formatted_prompt = f"System: {system_prompt}\n\nConversation:\n"
                            for msg in messages_for_api:
                                formatted_prompt += f"{msg['role'].title()}: {msg['content']}\n"
                            response = gemini_client.generate_content(formatted_prompt)
                        if response.text:
                            response_text = response.text

                            # Execute MCP tools if present
                            import asyncio
                            response_text_with_tools = asyncio.run(execute_mcp_tools_in_response(response_text))
                        else:
                            response_text_with_tools = f"I encountered an error: No response text generated. Please try again."
                    except Exception as e:
                        error_msg = str(e)
                        debug_print(f"Error calling Gemini API: {error_msg}")
                        debug_print(f"Gemini error traceback: {traceback.format_exc()}")
                        
                        # Check for specific Gemini error types
                        if "quota" in error_msg.lower() or "rate" in error_msg.lower():
                            response_text_with_tools = f"I encountered a rate limit issue with Gemini: {error_msg}. Please try switching to Anthropic with 'maia model' command."
                        elif "blocked" in error_msg.lower() or "safety" in error_msg.lower():
                            response_text_with_tools = f"I encountered a content filter issue: {error_msg}. Please try rephrasing your question."
                        elif "api" in error_msg.lower() and "key" in error_msg.lower():
                            response_text_with_tools = f"I encountered an API key issue: {error_msg}. Please check your GOOGLE_API_KEY environment variable."
                        elif "model" in error_msg.lower() and ("not found" in error_msg.lower() or "unavailable" in error_msg.lower()):
                            response_text_with_tools = f"I encountered a model availability issue: {error_msg}. The Gemini model may be temporarily unavailable. Please try switching to Anthropic with 'maia model' command."
                        elif "500" in error_msg or "internal" in error_msg.lower():
                            # Try fallback to Anthropic for 500 errors
                            if anthropic_client:
                                debug_print("Attempting fallback to Anthropic due to Gemini 500 error")
                                try:
                                    fallback_messages = [{"role": "user", "content": formatted_prompt}]
                                    fallback_response = call_anthropic_with_retry(anthropic_client, "", fallback_messages)
                                    if fallback_response and fallback_response.content and len(fallback_response.content) > 0:
                                        response_text_with_tools = fallback_response.content[0].text
                                        debug_print("Successfully fell back to Anthropic")
                                    else:
                                        response_text_with_tools = f"I encountered a server error with Gemini: {error_msg}. Fallback to Anthropic also failed. Please try again or switch models with 'maia model' command."
                                except Exception as fallback_error:
                                    debug_print(f"Fallback to Anthropic failed: {fallback_error}")
                                    response_text_with_tools = f"I encountered a server error with Gemini: {error_msg}. Fallback to Anthropic also failed. Please try again or switch models with 'maia model' command."
                            else:
                                response_text_with_tools = f"I encountered a server error with Gemini: {error_msg}. Please try switching to Anthropic with 'maia model' command."
                        else:
                            response_text_with_tools = f"I encountered an error with Gemini: {error_msg}. Please try again, or switch to Anthropic with 'maia model' command."
                    
                    if response_text_with_tools:
                        response_content = {
                            'text': response_text_with_tools,
                            'tokens': None
                        }
                        
                        # Extract and display token usage for Gemini (moved outside except block)
                        if 'response' in locals() and hasattr(response, 'usage_metadata') and response.usage_metadata:
                            prompt_tokens = response.usage_metadata.prompt_token_count
                            completion_tokens = response.usage_metadata.candidates_token_count
                            total_tokens = response.usage_metadata.total_token_count

                            # Calculate cost using centralized function
                            from promaia.utils.ai import calculate_ai_cost
                            debug_print(f"Cost calculation: prompt_tokens={prompt_tokens}, completion_tokens={completion_tokens}")
                            
                            # Determine Gemini model for pricing (use short context pricing for now)
                            gemini_model = "gemini-2.5-pro-short" if total_tokens <= 128000 else "gemini-2.5-pro-long"
                            cost_data = calculate_ai_cost(prompt_tokens, completion_tokens, gemini_model)
                            total_cost = cost_data["total_cost"]
                            debug_print(f"Calculated cost: ${total_cost:.6f}")

                            debug_print(f"Token usage: {prompt_tokens:,} prompt + {completion_tokens:,} completion = {total_tokens:,} total")

                            response_content = {
                                'text': response_text_with_tools,
                                'tokens': {
                                    'prompt_tokens': prompt_tokens,
                                    'response_tokens': completion_tokens,
                                    'total_tokens': total_tokens,
                                    'cost': total_cost,
                                    'model': 'Gemini 2.5 Pro'
                                }
                            }
                elif current_api == "llama":
                    # Ensure llama client is initialized with current environment
                    if not llama_client:
                        # Force reload environment to ensure LLAMA_API_KEY is available
                        from promaia.utils.config import load_environment
                        load_environment()
                        initialize_llama_client()
                    
                    if llama_client:
                        if current_message_images:
                            # Handle images with Llama
                            formatted_messages = _format_llama_with_images(system_prompt, messages_for_api, current_message_images)
                        else:
                            # Regular text-only message
                            formatted_messages = [{"role": "system", "content": system_prompt}] + messages_for_api
                        model_name = os.getenv("LLAMA_DEFAULT_MODEL", LLAMA_MODELS.get("llama3", "llama3:latest"))
                        
                        try:
                            response = llama_client.chat.completions.create(
                                model=model_name,
                                messages=formatted_messages,
                                max_tokens=4096,
                                temperature=0.7
                            )
                            if response.choices:
                                response_text = response.choices[0].message.content

                                # Execute MCP tools if present
                                import asyncio
                                response_text = asyncio.run(execute_mcp_tools_in_response(response_text))

                                # Extract token usage for local Llama if available
                                if hasattr(response, 'usage') and response.usage:
                                    prompt_tokens = response.usage.prompt_tokens
                                    completion_tokens = response.usage.completion_tokens
                                    total_tokens = response.usage.total_tokens

                                    debug_print(f"Token usage: {prompt_tokens:,} prompt + {completion_tokens:,} completion = {total_tokens:,} total")

                                    response_content = {
                                        'text': response_text,
                                        'tokens': {
                                            'prompt_tokens': prompt_tokens,
                                            'response_tokens': completion_tokens,
                                            'total_tokens': total_tokens,
                                            'cost': 0.0,  # Local models are free
                                            'model': f'Local Llama ({model_name})'
                                        }
                                    }
                                else:
                                    response_content = {
                                        'text': response_text,
                                        'tokens': None
                                    }
                        except Exception as e:
                            debug_print(f"Error calling local Llama: {e}")
                            response_content = f"Error calling local Llama: {e}"
                    else:
                        response_content = "Local Llama client not available. Check server connection."
                else:
                    print_text(f"Error: {current_api} API client not available.", style="bold red")
                    continue

                # Handle API responses
                if response_content:
                    if isinstance(response_content, dict):
                        # AI response with token data
                        response_text = response_content['text']
                        token_data = response_content.get('tokens')

                        timestamp = get_local_timestamp()
                        metadata_parts = [f"{timestamp} Maia"]
                        if token_data:
                            metadata_parts.append(f"{token_data['prompt_tokens']:,}, {token_data['response_tokens']:,}, {token_data['total_tokens']:,}")
                            metadata_parts.append(f"${token_data['cost']:.6f}")

                        # Print each metadata part on its own line
                        print()
                        if metadata_parts:
                            print_text(metadata_parts[0])  # Print timestamp line without dim
                        for part in metadata_parts[1:]:
                            print_text(part, style="dim")  # Print rest of metadata with dim
                        print()

                        # Use copy-friendly markdown display
                        print_markdown(response_text)

                        messages.append({"role": "assistant", "content": response_text})
                    else:
                        # String response (fallback for responses without token data)
                        timestamp = get_local_timestamp()
                        print()
                        print_text(f"{timestamp} Maia") # No style
                        print()
                        print_markdown(response_content)
                        messages.append({"role": "assistant", "content": response_content})
                else:
                    print_text("Error: No response generated.", style="bold red")

            except Exception as e:
                print_text(f"Error calling {current_api} API: {e}", style="bold red")
                debug_print(f"Full API error: {e}")

        except KeyboardInterrupt:
            print_text("\nGoodbye!", style="bold cyan")
            break
        except EOFError:
            print_text("\nGoodbye!", style="bold cyan")
            break

# CLI Image Helper Functions

def _format_anthropic_with_images(messages_for_api, current_message_images):
    """Format Anthropic messages with image support."""
    from promaia.utils.image_processing import format_image_for_anthropic
    
    # Build message history
    formatted_messages = []
    total_images = 0
    
    # Add all previous messages (including their images)
    for msg in messages_for_api[:-1]:  # Exclude current message
        if msg.get("images"):
            # Message has images - format as multimodal content
            msg_content = []
            
            # Add text if present
            if msg.get("content"):
                msg_content.append({"type": "text", "text": msg["content"]})
            
            # Add all images from this message
            for img in msg["images"]:
                msg_content.append(format_image_for_anthropic(img["data"], img["media_type"]))
                total_images += 1
            
            formatted_messages.append({
                "role": msg["role"],
                "content": msg_content
            })
        else:
            # Text-only message
            formatted_messages.append({
                "role": msg["role"],
                "content": msg["content"]
            })
    
    # Add current user message with images
    current_content = []
    
    # Add text if present
    if messages_for_api:
        last_msg = messages_for_api[-1]
        if last_msg.get("content"):
            current_content.append({"type": "text", "text": last_msg["content"]})
    
    # Add current message images
    for img in current_message_images:
        current_content.append(format_image_for_anthropic(img["data"], img["media_type"]))
        total_images += 1
    
    formatted_messages.append({
        "role": "user",
        "content": current_content
    })
    
    debug_print(f"Calling Anthropic with {len(formatted_messages)} messages and {total_images} total images ({len(current_message_images)} current)")
    return formatted_messages

def _format_openai_with_images(system_prompt, messages_for_api, current_message_images):
    """Format OpenAI messages with image support."""
    from promaia.utils.image_processing import format_image_for_openai
    
    # Start with system message
    formatted_messages = [{"role": "system", "content": system_prompt}]
    total_images = 0
    
    # Add all previous messages (including their images)
    for msg in messages_for_api[:-1]:  # Exclude current message
        if msg.get("images"):
            # Message has images - format as multimodal content
            msg_content = []
            
            # Add text if present
            if msg.get("content"):
                msg_content.append({"type": "text", "text": msg["content"]})
            
            # Add all images from this message
            for img in msg["images"]:
                msg_content.append(format_image_for_openai(img["data"], img["media_type"]))
                total_images += 1
            
            formatted_messages.append({
                "role": msg["role"],
                "content": msg_content
            })
        else:
            # Text-only message
            formatted_messages.append({
                "role": msg["role"],
                "content": msg["content"]
            })
    
    # Add current user message with images
    current_content = []
    
    # Add text if present
    if messages_for_api:
        last_msg = messages_for_api[-1]
        if last_msg.get("content"):
            current_content.append({"type": "text", "text": last_msg["content"]})
    
    # Add current message images
    for img in current_message_images:
        current_content.append(format_image_for_openai(img["data"], img["media_type"]))
        total_images += 1
    
    formatted_messages.append({
        "role": "user", 
        "content": current_content if current_content else "Please analyze the image"
    })
    
    debug_print(f"Calling OpenAI with {len(formatted_messages)} messages and {total_images} total images ({len(current_message_images)} current)")
    return formatted_messages

def _format_gemini_with_images(system_prompt, messages_for_api, current_message_images):
    """Format Gemini content with image support."""
    from promaia.utils.image_processing import format_image_for_gemini
    import google.generativeai as genai
    
    # Gemini uses a different approach - we need to create a model with system instruction
    # and then format the conversation with images
    
    current_gemini_model = genai.GenerativeModel(
        model_name="gemini-2.5-pro",
        system_instruction=system_prompt
    )
    
    # Build conversation history
    gemini_messages = []
    total_images = 0
    
    # Add previous messages (including their images)
    for msg in messages_for_api[:-1]:  # Exclude current message
        role = 'user' if msg['role'] == 'user' else 'model'
        
        if msg.get("images"):
            # Message has images - include text and images
            msg_parts = []
            
            # Add text if present
            if msg.get("content"):
                msg_parts.append(msg["content"])
            
            # Add all images from this message
            for img in msg["images"]:
                msg_parts.append(format_image_for_gemini(img["data"], img["media_type"]))
                total_images += 1
            
            gemini_messages.append({'role': role, 'parts': msg_parts})
        else:
            # Text-only message
            gemini_messages.append({'role': role, 'parts': [msg['content']]})
    
    # Add current user message with images
    current_parts = []
    
    # Add text if present
    if messages_for_api:
        last_msg = messages_for_api[-1]
        if last_msg.get("content"):
            current_parts.append(last_msg["content"])
    
    # Add current message images
    for img in current_message_images:
        current_parts.append(format_image_for_gemini(img["data"], img["media_type"]))
        total_images += 1
    
    gemini_messages.append({'role': 'user', 'parts': current_parts})
    
    debug_print(f"Calling Gemini with {len(gemini_messages)} messages and {total_images} total images ({len(current_message_images)} current)")
    return current_gemini_model, gemini_messages

def _format_llama_with_images(system_prompt, messages_for_api, current_message_images):
    """Format Llama messages with image support (OpenAI-compatible format)."""
    from promaia.utils.image_processing import format_image_for_llama
    
    # Start with system message
    formatted_messages = [{"role": "system", "content": system_prompt}]
    
    # Find the first image across all messages (most local vision models support only 1 image)
    first_image = None
    first_image_msg = None
    total_images_available = 0
    
    # Check historical messages for images
    for msg in messages_for_api[:-1]:  # Exclude current message
        if msg.get("images") and not first_image:
            first_image = msg["images"][0]  # Take first image
            first_image_msg = msg
        if msg.get("images"):
            total_images_available += len(msg["images"])
    
    # Check current message for images
    if current_message_images:
        total_images_available += len(current_message_images)
        if not first_image:
            first_image = current_message_images[0]
    
    # Add all previous messages (text only, except the one with the first image)
    for msg in messages_for_api[:-1]:  # Exclude current message
        if msg.get("images") and msg == first_image_msg:
            # This message has the first image we're using - format as multimodal
            msg_content = []
            
            # Add text if present
            if msg.get("content"):
                msg_content.append({"type": "text", "text": msg["content"]})
            
            # Add first image
            msg_content.append(format_image_for_llama(first_image["data"], first_image["media_type"]))
            
            formatted_messages.append({
                "role": msg["role"],
                "content": msg_content
            })
        else:
            # Text-only message or message with images we're not using
            formatted_messages.append({
                "role": msg["role"],
                "content": msg["content"]
            })
    
    # Add current user message
    current_content = []
    
    # Add text if present
    if messages_for_api:
        last_msg = messages_for_api[-1]
        if last_msg.get("content"):
            current_content.append({"type": "text", "text": last_msg["content"]})
    
    # Add image only if we haven't used one from history
    if current_message_images and not first_image_msg:
        current_content.append(format_image_for_llama(current_message_images[0]["data"], current_message_images[0]["media_type"]))
    
    formatted_messages.append({
        "role": "user",
        "content": current_content if current_content else "Please analyze the image"
    })
    
    images_used = 1 if first_image else 0
    debug_print(f"Calling Llama with {len(formatted_messages)} messages and {images_used} image (from {total_images_available} available)")
    return formatted_messages

def main():
    """Entry point for the chat interface."""
    import argparse

    parser = argparse.ArgumentParser(description="Interactive chat with Maia")
    parser.add_argument("-s", "--sources", nargs="+", help="Data sources to load")
    parser.add_argument("-f", "--filters", nargs="+", help="Filters to apply to sources")
    parser.add_argument("-w", "--workspace", help="Workspace to use")
    parser.add_argument("--non-interactive", action="store_true", help="Run in non-interactive mode")

    args = parser.parse_args()

    chat(
        sources=args.sources,
        filters=args.filters,
        workspace=args.workspace,
        non_interactive=args.non_interactive
    )

if __name__ == "__main__":
    main()
