"""
Terminal-based chat interface for interacting with AI models.
"""
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
import datetime
import asyncio
import traceback
from typing import List, Dict, Any, Optional
from pathlib import Path

from promaia.storage.files import read_markdown_files_with_registry
from promaia.utils.config import load_environment, get_last_sync_time
from promaia.config.workspaces import get_workspace_manager
from promaia.ai.prompts import create_system_prompt
from promaia.ai.models import LLAMA_MODELS
from promaia.utils.display import print_markdown, print_code, print_text
from promaia.utils.timezone_utils import now_utc
from promaia.storage.chat_history import ChatHistoryManager

import google.generativeai as genai

# Load environment variables
load_environment()

# Initialize DEBUG_MODE at the global scope
DEBUG_MODE = os.getenv("MAIA_DEBUG", "0") == "1"

# Configuration file for API preferences
API_PREFERENCE_FILE = os.path.join(os.path.expanduser("~"), ".maia_api_preference")

# Initialize rich console for better formatting with copy-friendly settings
console = os.getenv("MAIA_DEBUG", "0") == "1"

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

session = PromptSession(history=FileHistory('.chat_history'))

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
    model_names = {
        "anthropic": "Claude 3 Sonnet",
        "openai": "GPT-4",
        "gemini": "Gemini 2.5 Pro",
        "llama": f"Local Llama ({os.getenv('LLAMA_DEFAULT_MODEL', 'llama3:latest')})"
    }
    return model_names.get(current_api, "Unknown Model")

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
    print_text("Available commands: /quit /debug /push /help /s /e /save", style="dim")
    print_text("  /s - Sync databases in current context", style="dim")
    print_text("  /e - Edit context (sources, filters, natural language)", style="dim")
    print_text("  /save - Save current conversation to history", style="dim")
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
    print_text("Available commands: /quit /debug /push /help /s /e /save", style="dim")
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
    for attempt in range(max_retries):
        try:
            response = client.messages.create(
                model="claude-3-sonnet-20240229",
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


def chat(sources=None, filters=None, workspace=None, resolved_workspace=None, non_interactive=False, initial_messages=None, current_thread_id=None, natural_language_content=None, natural_language_prompt=None, original_browse_command=None, browse_selections=None):
    """Main chat function with simplified, unified logic."""
    global current_api, DEBUG_MODE

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
        'natural_language_prompt': natural_language_prompt,  # Store the original NL prompt
        'original_browse_mode': bool(original_browse_command),  # Track if session started with browse mode
        'browse_selections': browse_selections,  # Store original browse selections for re-editing
        'original_query_format': original_browse_command  # Store the original query format for display
    }

    def update_query_command():
        """Update the query command display based on current context state."""
        # If we have an original query format (like -b), prefer showing that
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
            query_parts.extend(["-w", context_state['workspace']])
        if context_state['natural_language_prompt']:
            query_parts.extend(["-nl", context_state['natural_language_prompt']])
        context_state['query_command'] = " ".join(query_parts)

    # Initial query command setup
    update_query_command()
    query_command = context_state['query_command']

    def reload_context():
        """Reload the chat context with current state configuration."""
        nonlocal initial_multi_source_data, total_pages_loaded, system_prompt, query_command
        
        # Initialize combined data container
        combined_multi_source_data = {}
        
        # Process natural language query if present
        natural_language_data = {}
        if context_state.get('natural_language_prompt'):
            nl_prompt = context_state['natural_language_prompt']
            print("🤖 Processing natural language content")
            
            try:
                from promaia.storage.unified_query import get_query_interface
                
                # Determine workspace to use - preserve from original context
                workspace_to_use = context_state.get('resolved_workspace') or context_state.get('workspace')
                
                # If no explicit workspace, try to infer from original sources
                if not workspace_to_use and context_state.get('sources'):
                    # Try to extract workspace from source names (e.g., "trass.gmail" -> "trass")
                    for source in context_state['sources']:
                        if '.' in source:
                            potential_workspace = source.split('.')[0]
                            workspace_to_use = potential_workspace
                            break
                
                # Fall back to default workspace
                if not workspace_to_use:
                    from promaia.config.workspaces import get_workspace_manager
                    workspace_manager = get_workspace_manager()
                    workspace_to_use = workspace_manager.get_default_workspace()
                
                if not workspace_to_use:
                    print_text("Error: No workspace available for natural language query.", style="bold red")
                    return False
                
                # Process the natural language query fresh
                query_interface = get_query_interface()
                natural_language_data = query_interface.natural_language_query(nl_prompt, workspace_to_use)
                
                if natural_language_data:
                    print(f"🤖 Natural language query found {sum(len(pages) for pages in natural_language_data.values())} pages")
                    # Add to combined data
                    combined_multi_source_data.update(natural_language_data)
                    # Update stored NL content
                    context_state['natural_language_content'] = natural_language_data
                else:
                    print_text("⚠️ No content found for natural language query", style="bold yellow")
                
            except Exception as e:
                print_text(f"Error processing natural language content: {e}", style="bold red")
                # Continue with regular sources even if NL fails
        
        # Use current state
        current_sources = context_state['sources']
        current_filters = context_state['filters']
        current_workspace = context_state['workspace']
        current_resolved_workspace = context_state['resolved_workspace']
        
        # 1. Determine Workspace (use resolved_workspace if provided, otherwise fallback)
        if current_resolved_workspace:
            actual_workspace = current_resolved_workspace
        else:
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
        # Use combined data that may already contain natural language results
        new_multi_source_data = combined_multi_source_data
        # Don't calculate total here - calculate it from final data to ensure consistency

        if not current_sources:
            debug_print(f"No sources provided, loading all databases for workspace '{actual_workspace}'.")
            workspace_databases = db_manager.get_workspace_databases(actual_workspace)
            current_sources = [db.nickname for db in workspace_databases]
            context_state['sources'] = current_sources
            if not current_sources:
                print_text(f"Warning: No databases configured for workspace '{actual_workspace}'. Chat will lack context.", style="bold yellow")

        if current_filters and current_sources:
            debug_print(f"Applying filters: {current_filters}")

        # 3. Process filters and integrate them into source specifications
        processed_sources = []
        source_specific_filters = {}  # Dict of source -> list of filters
        global_filters = []  # Filters without source prefix (backward compatibility)

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
            try:
                parsed_sources_init = parse_source_specs(processed_sources)
            except Exception as e:
                print_text(f"Warning: Error parsing source specifications: {e}", style="bold yellow")
                return False

        # Load content from sources
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

                    if DEBUG_MODE:
                        print_text(f"  - Loaded {len(pages)} entries from: {unique_key}", style="green")
                except Exception as e:
                    if DEBUG_MODE:
                        print_text(f"Error loading data for database {db_config.name}: {e}", style="bold red")

        # Calculate total from final data to ensure consistency with breakdown
        new_total_pages_loaded = sum(len(pages) for pages in new_multi_source_data.values())
        
        # Update context state
        context_state['initial_multi_source_data'] = new_multi_source_data
        context_state['total_pages_loaded'] = new_total_pages_loaded
        
        # Update sources list to reflect only the sources that were actually loaded
        # This ensures session logs show accurate source information
        context_state['sources'] = list(new_multi_source_data.keys())
        
        # Update module-level variables
        initial_multi_source_data = new_multi_source_data
        total_pages_loaded = new_total_pages_loaded
        
        # Generate new system prompt
        system_prompt = create_system_prompt(new_multi_source_data)
        context_state['system_prompt'] = system_prompt
        
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
                discord_filters = []
                for f in current_filters:
                    filter_db_name = f.split(':')[0] if ':' in f else f
                    # Check if this filter belongs to the same database
                    filter_db_config = db_manager.get_database_by_qualified_name(filter_db_name)
                    if filter_db_config and filter_db_config.name == db_base_name:
                        discord_filters.append(f)
                
                if discord_filters:
                    # Use the filtered specifications (one per channel)
                    sources_to_sync.extend(discord_filters)
                    print_text(f"📺 Discord source {source}: syncing {len(discord_filters)} selected channels", style="dim cyan")
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
                
                print_text(f"🔄 Syncing {source_name}...", style="cyan")
                result = await sync_database(source_spec, mock_args)
                
                if result.errors:
                    print_text(f"❌ {source_name}: {len(result.errors)} errors", style="bold red")
                    for error in result.errors[:2]:  # Show first 2 errors
                        print_text(f"  - {error}", style="red")
                else:
                    print_text(f"✅ {source_name}: {result.pages_saved} saved, {result.pages_skipped} skipped", style="bold green")
                
            except Exception as e:
                print_text(f"  ❌ {source_name}: Sync failed - {e}", style="bold red")
                debug_print(f"Sync error for {source_name}: {e}")

    def edit_context():
        """CLI-style context editing interface."""
        print_text("\n🔧 Edit Context", style="bold cyan")
        
        # Show current context summary
        print_text("Current command:", style="dim")
        print_text(f"  {context_state['query_command']}", style="bold")
        
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
        print_text("  • Ctrl+B for Discord browse mode", style="dim")
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
            else:
                current_args_str = ""
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
                # Check if this is a browse mode command
                if '-b' in user_input:
                    # If user didn't change the browse command, launch browser
                    if user_input.strip() == current_args_str.strip():
                        print_text("📝 Launching browser for browse mode command...", style="bold cyan")
                        return handle_browse_in_edit_context()
                    else:
                        # User manually edited a browse command - handle it with CLI logic
                        print_text("📝 Processing manually edited browse command...", style="bold cyan")
                        print_text("Note: You'll need to reselect Discord channels after this change.", style="dim yellow")
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
                    nargs="*",
                    help="Use natural language to specify what content to load for chat context"
                )
                
                # Parse the arguments
                parsed_args = parser.parse_args(args_list)
                
                # Check if natural language mode is being used
                natural_language_args = getattr(parsed_args, 'natural_language', None)
                
                if natural_language_args is not None:
                    # Natural language mode
                    nl_prompt = " ".join(natural_language_args) if natural_language_args else ""
                    if not nl_prompt:
                        print_text("Error: Natural language prompt is empty.", style="bold red")
                        return False
                    
                    # Process natural language query
                    try:
                        from promaia.storage.unified_query import get_query_interface
                        
                        # Determine workspace to use
                        workspace_to_use = context_state.get('resolved_workspace') or context_state.get('workspace')
                        
                        # If no explicit workspace, try to infer from original sources
                        if not workspace_to_use and context_state.get('sources'):
                            # Try to extract workspace from source names (e.g., "trass.gmail" -> "trass")
                            for source in context_state['sources']:
                                if '.' in source:
                                    potential_workspace = source.split('.')[0]
                                    workspace_to_use = potential_workspace
                                    break
                        
                        # Fall back to default workspace
                        if not workspace_to_use:
                            from promaia.config.workspaces import get_workspace_manager
                            workspace_manager = get_workspace_manager()
                            workspace_to_use = workspace_manager.get_default_workspace()
                        
                        if not workspace_to_use:
                            print_text("Error: No workspace available for natural language query.", style="bold red")
                            return False
                        
                        print_text(f"🤖 Processing natural language query: '{nl_prompt}'", style="dim")
                        
                        # Process the natural language query
                        query_interface = get_query_interface()
                        natural_language_content = query_interface.natural_language_query(nl_prompt, workspace_to_use)
                        
                        if not natural_language_content:
                            print_text("❌ No content found for natural language query", style="bold red")
                            return False
                        
                        # Update context state for natural language mode
                        context_state['natural_language_content'] = natural_language_content
                        context_state['natural_language_prompt'] = nl_prompt
                        # Keep existing regular sources and filters - they'll be combined
                        
                        # Reload with natural language content
                        if reload_context():
                            print_text("Context updated successfully!", style="bold green")
                            return True
                        else:
                            print_text("Failed to reload context with natural language content.", style="bold red")
                            return False
                            
                    except Exception as e:
                        print_text(f"Error processing natural language query: {e}", style="bold red")
                        return False
                else:
                    # Regular mode with sources and filters
                    new_sources = getattr(parsed_args, 'sources', []) or []
                    new_filters = getattr(parsed_args, 'filters', []) or []
                    new_workspace = getattr(parsed_args, 'workspace', None)
                    
                    # Update context state
                    context_state['sources'] = new_sources
                    context_state['filters'] = new_filters
                    context_state['natural_language_content'] = None  # Clear NL content
                    context_state['natural_language_prompt'] = None   # Clear NL prompt
                    if new_workspace:
                        context_state['workspace'] = new_workspace
                    
                    # Always reload context with new settings
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
            
            # Parse the browse command
            args_list = safe_split_command(user_input)
            
            # Create parser that handles browse commands
            parser = argparse.ArgumentParser(description="Manual browse command editor", add_help=False)
            parser.add_argument("--source", "-s", action="append", dest="sources")
            parser.add_argument("--filter", "-f", action="append", dest="filters") 
            parser.add_argument("--workspace", "-ws", dest="workspace")
            parser.add_argument("--browse", "-b", nargs="*", dest="browse")
            parser.add_argument("--natural-language", "-nl", nargs="*", dest="natural_language")
            
            parsed_args = parser.parse_args(args_list)
            
            # Extract components
            regular_sources = parsed_args.sources or []
            browse_databases = parsed_args.browse or []
            original_filters = parsed_args.filters or []
            workspace = parsed_args.workspace or context_state.get('workspace')
            
            # Resolve workspace from browse databases if needed
            from promaia.config.workspaces import get_workspace_manager
            workspace_manager = get_workspace_manager()
            resolved_workspace = workspace
            if browse_databases and not workspace:
                # Try to determine workspace from browse databases
                for browse_db in browse_databases:
                    if '.' in browse_db:
                        determined_workspace = browse_db.split('.')[0]
                        if workspace_manager.validate_workspace(determined_workspace):
                            resolved_workspace = determined_workspace
                            print_text(f"INFO: Using workspace '{resolved_workspace}' from browse database '{browse_db}'.", style="cyan")
                            break
            
            if not resolved_workspace:
                resolved_workspace = context_state.get('resolved_workspace')
            
            # Validate that the requested databases exist before launching browser
            from promaia.config.databases import get_database_manager
            db_manager = get_database_manager()
            
            # Check if the browse databases actually exist using proper name resolution
            invalid_databases = []
            valid_databases = []
            for browse_db in browse_databases:
                # Strip day specification to get database name
                db_name = browse_db.split(':')[0] if ':' in browse_db else browse_db
                
                # Use proper database resolution (handles nicknames)
                db_config = db_manager.get_database_by_qualified_name(db_name)
                
                if db_config and db_config.workspace == resolved_workspace and db_config.source_type == "discord":
                    valid_databases.append(browse_db)
                else:
                    invalid_databases.append(db_name)
            
            # If there are invalid databases, show helpful error
            if invalid_databases:
                print_text(f"❌ Invalid Discord database(s): {', '.join(invalid_databases)}", style="bold red")
                
                # Show available databases
                available_dbs = []
                for db_name, db_config in db_manager.databases.items():
                    if db_config.workspace == resolved_workspace and db_config.source_type == "discord":
                        qualified_name = db_config.get_qualified_name()
                        # Show both qualified name and full config name if different
                        if qualified_name != db_name:
                            available_dbs.append(f"{qualified_name} (or {db_name})")
                        else:
                            available_dbs.append(qualified_name)
                
                if available_dbs:
                    print_text(f"📋 Available Discord databases for workspace '{resolved_workspace}':", style="cyan")
                    for db in available_dbs:
                        print_text(f"   • {db}", style="dim cyan")
                    # For suggestion, use the qualified name (which includes nickname)
                    first_suggestion = available_dbs[0].split(' (or ')[0]  # Get just the qualified name part
                    suggestion_cmd = f"-s {' '.join(regular_sources)} -b {first_suggestion}:7" if regular_sources else f"-b {first_suggestion}:7"
                    print_text(f"\n💡 Try: {suggestion_cmd}", style="dim yellow")
                else:
                    print_text(f"ℹ️  No Discord databases configured for workspace '{resolved_workspace}'", style="yellow")
                    print_text(f"💡 Set up Discord integration: maia workspace discord-setup {resolved_workspace}", style="dim yellow")
                
                return False
            
            # Handle browse mode - import and use the browse logic
            from promaia.cli.discord_commands import handle_discord_browse_filtered
            
            print_text(f"🎮 Launching Discord channel browser for databases: {' '.join(browse_databases)}...", style="cyan")
            
            # Create browse args locally (BrowseArgs is defined locally in cli modules)
            class BrowseArgs:
                def __init__(self, workspace, databases=None, database_days=None):
                    self.workspace = workspace
                    self.databases = databases
                    self.database_days = database_days or {}
            
            browse_args = BrowseArgs(resolved_workspace, browse_databases, {})
            
            # Check if we can reuse previous Discord selections
            previous_selections = context_state.get('browse_selections', [])
            previous_browse_dbs = []
            if previous_selections:
                # Extract database names from previous selections
                previous_browse_dbs = list(set([sel[0] for sel in previous_selections]))
            
            # If browse databases haven't changed, reuse previous selections
            if (previous_selections and 
                set(browse_databases) == set(previous_browse_dbs)):
                print_text("ℹ️  Browse databases unchanged - reusing previous Discord channel selections", style="dim cyan")
                selected_channels = previous_selections
            else:
                # Run the Discord browser (databases changed, need new selections)
                print_text("ℹ️  Browse databases changed - launching Discord channel browser", style="dim yellow")
                selected_channels = asyncio.run(handle_discord_browse_filtered(browse_args))
            
            if not selected_channels:
                print_text("ℹ️  No channels selected. Context unchanged.", style="bold yellow")
                return False
            
            print_text(f"✅ Selected {len(selected_channels)} Discord channels:", style="bold green")
            
            # Convert selected channels to source specifications
            discord_sources = []
            discord_filters = []
            browse_parts = []
            
            # Group selections by database for cleaner browse command
            db_selections = {}
            for db_name, channel_id, channel_name, days in selected_channels:
                if db_name not in db_selections:
                    db_selections[db_name] = {'days': days, 'channels': []}
                db_selections[db_name]['channels'].append(channel_name)
                
                # Show what was selected
                print_text(f"   • {db_name}:{days} → #{channel_name}", style="dim")
            
            # Create one source per database with combined channel filter
            for db_name, selection_info in db_selections.items():
                source_spec = f"{db_name}:{selection_info['days']}"
                discord_sources.append(source_spec)
                
                # Create combined filter for all channels in this database
                if len(selection_info['channels']) == 1:
                    # Single channel - simple filter
                    filter_spec = f'{source_spec}:"channel_name={selection_info["channels"][0]}"'
                    discord_filters.append(filter_spec)
                else:
                    # Multiple channels - create complex filter with OR logic
                    channel_conditions = []
                    for channel_name in selection_info['channels']:
                        channel_conditions.append(f'channel_name={channel_name}')
                    combined_filter = ' or '.join(channel_conditions)
                    filter_spec = f'{source_spec}:"({combined_filter})"'
                    discord_filters.append(filter_spec)
            
            # Build browse command format for display
            for db_name, selection_info in db_selections.items():
                if selection_info['days'] != 30:  # Only show days if not default
                    browse_parts.append(f"{db_name}:{selection_info['days']}")
                else:
                    browse_parts.append(db_name)
            
            # Combine regular sources with Discord sources
            combined_sources = regular_sources + discord_sources
            combined_filters = original_filters + discord_filters
            
            # Build complete command format
            command_parts = ["maia", "chat"]
            
            # Add regular sources first
            for reg_source in regular_sources:
                command_parts.extend(["-s", reg_source])
            
            # Add browse part
            command_parts.extend(["-b"] + browse_parts)
            
            # Add any regular filters
            for reg_filter in original_filters:
                command_parts.extend(["-f", f'"{reg_filter}"'])
            
            # Add workspace if specified
            if workspace:
                command_parts.extend(["-w", workspace])
            
            complete_command = " ".join(command_parts)
            
            # Update context state
            context_state['sources'] = combined_sources
            context_state['filters'] = combined_filters
            context_state['workspace'] = workspace
            context_state['resolved_workspace'] = resolved_workspace
            context_state['natural_language_content'] = None
            context_state['natural_language_prompt'] = None
            context_state['original_browse_mode'] = True
            context_state['browse_selections'] = selected_channels
            context_state['original_query_format'] = complete_command
            
            # Update the main query command for logging
            context_state['query_command'] = complete_command
            
            # Reload context with new settings
            print_text("🔄 Reloading context with new browse selections...", style="bold cyan")
            return reload_context()
            
        except Exception as e:
            print_text(f"❌ Error processing browse command: {e}", style="bold red")
            if DEBUG_MODE:
                import traceback
                print_text(traceback.format_exc(), style="dim red")
            return False
    
    def handle_browse_in_edit_context():
        """Handle browse mode selection within edit context."""
        try:
            # Import browse functionality
            from promaia.cli.discord_commands import handle_discord_browse_filtered
            from promaia.config.databases import get_database_manager
            
            # Determine workspace from current context
            workspace_to_use = context_state.get('resolved_workspace') or context_state.get('workspace')
            
            # If no workspace in context, try to infer from current sources
            if not workspace_to_use and context_state.get('sources'):
                for source in context_state['sources']:
                    if '.' in source:
                        potential_workspace = source.split('.')[0].split(':')[0]
                        workspace_to_use = potential_workspace
                        break
            
            # Fall back to default workspace
            if not workspace_to_use:
                from promaia.config.workspaces import get_workspace_manager
                workspace_manager = get_workspace_manager()
                workspace_to_use = workspace_manager.get_default_workspace()
            
            if not workspace_to_use:
                print_text("Error: No workspace available for browse mode.", style="bold red")
                return False
            
            print_text(f"🎮 Launching Discord channel browser for workspace '{workspace_to_use}'...", style="cyan")
            
            # Create browse args locally (BrowseArgs is defined locally in cli modules)
            class BrowseArgs:
                def __init__(self, workspace, databases=None, database_days=None):
                    self.workspace = workspace
                    self.databases = databases
                    self.database_days = database_days or {}
            
            browse_args = BrowseArgs(workspace_to_use, None, {})  # No specific databases, no day filtering
            
            # If we have previous browse selections, we'll need to pass them to the browser
            # For now, let's use the standard browser and enhance it later
            previous_selections = context_state.get('browse_selections', [])
            
            # Run the Discord browser with previous selections context
            async def run_browse_with_preselect():
                if previous_selections:
                    print_text(f"ℹ️  Pre-populating with {len(previous_selections)} previous channel selections", style="dim cyan")
                return await handle_discord_browse_filtered(browse_args, previous_selections)
            
            selected_channels = asyncio.run(run_browse_with_preselect())
            
            if not selected_channels:
                print_text("ℹ️  No channels selected. Context unchanged.", style="bold yellow")
                return False
            
            print_text(f"✅ Selected {len(selected_channels)} Discord channels:", style="bold green")
            
            # Convert selected channels to source specifications
            discord_sources = []
            discord_filters = []
            browse_parts = []
            
            # Group selections by database for cleaner browse command
            db_selections = {}
            for db_name, channel_id, channel_name, days in selected_channels:
                if db_name not in db_selections:
                    db_selections[db_name] = {'days': days, 'channels': []}
                db_selections[db_name]['channels'].append(channel_name)
                
                # Show what was selected
                print_text(f"   • {db_name}:{days} → #{channel_name}", style="dim")
            
            # Create one source per database with combined channel filter
            for db_name, selection_info in db_selections.items():
                source_spec = f"{db_name}:{selection_info['days']}"
                discord_sources.append(source_spec)
                
                # Create combined filter for all channels in this database
                if len(selection_info['channels']) == 1:
                    # Single channel - simple filter
                    filter_spec = f'{source_spec}:"channel_name={selection_info["channels"][0]}"'
                    discord_filters.append(filter_spec)
                else:
                    # Multiple channels - create complex filter with OR logic
                    channel_conditions = []
                    for channel_name in selection_info['channels']:
                        channel_conditions.append(f'channel_name={channel_name}')
                    combined_filter = ' or '.join(channel_conditions)
                    filter_spec = f'{source_spec}:"({combined_filter})"'
                    discord_filters.append(filter_spec)
            
            # Build browse command format for display
            for db_name, selection_info in db_selections.items():
                if selection_info['days'] != 30:  # Only show days if not default
                    browse_parts.append(f"{db_name}:{selection_info['days']}")
                else:
                    browse_parts.append(db_name)
            
            # PRESERVE existing regular sources and combine with new Discord sources
            existing_regular_sources = [s for s in context_state.get('sources', []) 
                                      if not ('discord' in s.lower() or s.endswith('.ds'))]
            
            combined_sources = existing_regular_sources + discord_sources
            
            # PRESERVE existing non-Discord filters and combine with new Discord filters  
            existing_regular_filters = [f for f in context_state.get('filters', [])
                                      if not any(discord_name in f for discord_name in [ds.split(':')[0] for ds in discord_sources])]
            
            combined_filters = existing_regular_filters + discord_filters
            
            # Build COMPLETE command format including regular sources
            command_parts = ["maia", "chat"]
            
            # Add regular sources first
            for reg_source in existing_regular_sources:
                command_parts.extend(["-s", reg_source])
            
            # Add browse part
            command_parts.extend(["-b"] + browse_parts)
            
            # Add any regular filters
            for reg_filter in existing_regular_filters:
                command_parts.extend(["-f", f'"{reg_filter}"'])
            
            complete_command = " ".join(command_parts)
            
            # Update context state
            context_state['sources'] = combined_sources
            context_state['filters'] = combined_filters
            context_state['natural_language_content'] = None  # Clear NL content
            context_state['natural_language_prompt'] = None   # Clear NL prompt
            context_state['original_browse_mode'] = True      # Mark as browse-originated
            context_state['browse_selections'] = selected_channels  # Store for re-editing
            context_state['original_query_format'] = complete_command  # Store complete original format
            
            # Reload context with new settings
            if reload_context():
                print_text("Context updated successfully from browse selection!", style="bold green")
                return True
            else:
                print_text("Failed to reload context with browse selection.", style="bold red")
                return False
                
        except ImportError as e:
            print_text(f"Browse mode not available: {e}", style="bold red")
            return False
        except Exception as e:
            print_text(f"Error in browse mode: {e}", style="bold red")
            debug_print(f"Browse error: {e}")
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
                        workspace_to_use = context_state.get('resolved_workspace') or context_state.get('workspace')
                        if not workspace_to_use:
                            from promaia.config.workspaces import get_workspace_manager
                            workspace_manager = get_workspace_manager()
                            workspace_to_use = workspace_manager.get_default_workspace()
                        
                        if not workspace_to_use:
                            print_text("Error: No workspace available for natural language query.", style="bold red")
                            return False
                        
                        print_text(f"🤖 Processing natural language query from recent: '{selected_query.natural_language_prompt}'", style="dim")
                        
                        # Process the natural language query
                        query_interface = get_query_interface()
                        natural_language_content = query_interface.natural_language_query(
                            selected_query.natural_language_prompt, workspace_to_use
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
                    result = asyncio.run(push_chat_to_notion(messages))
                    print_text(result, style="bold green")
                except Exception as e:
                    print_text(f"Error pushing to Notion: {e}", style="bold red")
                continue
            elif user_input.strip().lower() == '/s':
                # Sync current context databases
                try:
                    asyncio.run(sync_current_context_databases())
                    print_text("Context databases synced successfully. Reloading context...", style="bold green")
                    if reload_context():
                        print_text("Context reloaded successfully!", style="bold green")
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
                        print_text("Context updated successfully!", style="bold green")
                        print()
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
                        'natural_language_content': None  # Don't save the actual content, regenerate on restore
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

            if not user_input.strip():
                continue

            messages.append({"role": "user", "content": user_input})

            # Call the appropriate API
            response_content = None
            try:
                # Debug: Log system prompt info before AI call
                if DEBUG_MODE:
                    debug_print(f"AI Call Debug: System prompt length: {len(system_prompt)}")
                    debug_print(f"AI Call Debug: Total pages in context: {total_pages_loaded}")
                    debug_print(f"AI Call Debug: Context sources: {context_state.get('sources')}")
                
                if current_api == "anthropic" and anthropic_client:
                    response = call_anthropic_with_retry(anthropic_client, system_prompt, messages)
                    if response and response.content:
                        response_text = response.content[0].text

                        # Extract token usage for Anthropic
                        if hasattr(response, 'usage'):
                            input_tokens = response.usage.input_tokens
                            output_tokens = response.usage.output_tokens
                            total_tokens = input_tokens + output_tokens

                            # Calculate cost using centralized function
                            from promaia.utils.ai import calculate_ai_cost
                            cost_data = calculate_ai_cost(input_tokens, output_tokens, "claude-3.5-sonnet")
                            total_cost = cost_data["total_cost"]

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
                    formatted_messages = [{"role": "system", "content": system_prompt}] + messages
                    response = openai_client.chat.completions.create(
                        model="gpt-4",
                        messages=formatted_messages,
                        max_tokens=4096,
                        temperature=0.7
                    )
                    if response.choices:
                        response_text = response.choices[0].message.content

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
                    formatted_prompt = f"System: {system_prompt}\n\nConversation:\n"
                    for msg in messages:
                        formatted_prompt += f"{msg['role'].title()}: {msg['content']}\n"

                    response = gemini_client.generate_content(formatted_prompt)
                    if response.text:
                        response_content = response.text

                        # Extract and display token usage for Gemini
                        if hasattr(response, 'usage_metadata') and response.usage_metadata:
                            usage = response.usage_metadata
                            prompt_tokens = getattr(usage, 'prompt_token_count', 0)
                            response_tokens = getattr(usage, 'candidates_token_count', 0)
                            total_tokens = getattr(usage, 'total_token_count', 0)

                            # Calculate cost using centralized function with appropriate model tier
                            from promaia.utils.ai import calculate_ai_cost
                            model_tier = "gemini-2.5-pro-short" if prompt_tokens <= 128000 else "gemini-2.5-pro-long"
                            cost_data = calculate_ai_cost(prompt_tokens, response_tokens, model_tier)
                            total_cost = cost_data["total_cost"]

                            debug_print(f"Token usage: {prompt_tokens:,} prompt + {response_tokens:,} response = {total_tokens:,} total")

                            # Store token info for display after response
                            response_content = {
                                'text': response_content,
                                'tokens': {
                                    'prompt_tokens': prompt_tokens,
                                    'response_tokens': response_tokens,
                                    'total_tokens': total_tokens,
                                    'cost': total_cost,
                                    'model': 'Gemini 2.5 Pro'
                                }
                            }
                        else:
                            # Fallback for when usage metadata is not available
                            response_content = {
                                'text': response_content,
                                'tokens': None
                            }
                elif current_api == "llama":
                    # Ensure llama client is initialized with current environment
                    if not llama_client:
                        # Force reload environment to ensure LLAMA_API_KEY is available
                        from promaia.utils.config import load_environment
                        load_environment()
                        initialize_llama_client()
                    
                    if llama_client:
                        formatted_messages = [{"role": "system", "content": system_prompt}] + messages
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

                if response_content:
                    # Handle different response formats
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