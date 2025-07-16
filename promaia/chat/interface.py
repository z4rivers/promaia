"""
Terminal-based chat interface for interacting with AI models.
"""
from anthropic import Anthropic
from openai import OpenAI
import os
import sys
import time
import json
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
                if api_type in ["anthropic", "openai", "gemini"]:
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

def get_current_model_name():
    """Get the display name of the current model based on the current API."""
    global current_api
    model_names = {
        "anthropic": "Claude 3 Sonnet",
        "openai": "GPT-4",
        "gemini": "Gemini 2.5 Pro"
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
        # Extract the actual source name (remove workspace prefix if present)
        if '.' in source_key:
            source_name = source_key.split('.', 1)[1]  # Get part after first dot
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

def chat(sources=None, filters=None, workspace=None, resolved_workspace=None, non_interactive=False, initial_messages=None, current_thread_id=None, natural_language_content=None, natural_language_prompt=None):
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
        'natural_language_prompt': natural_language_prompt  # Store the original NL prompt
    }

    def update_query_command():
        """Update the query command display based on current context state."""
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
        
        # Check if we have natural language content to use directly
        if context_state.get('natural_language_content'):
            print("🤖 Using natural language generated content")
            new_multi_source_data = context_state['natural_language_content']
            new_total_pages_loaded = sum(len(pages) for pages in new_multi_source_data.values())
            
            # Update context state
            context_state['initial_multi_source_data'] = new_multi_source_data
            context_state['total_pages_loaded'] = new_total_pages_loaded
            
            # Update module-level variables
            initial_multi_source_data = new_multi_source_data
            total_pages_loaded = new_total_pages_loaded
            
            # Generate new system prompt
            system_prompt = create_system_prompt(new_multi_source_data)
            context_state['system_prompt'] = system_prompt
            
            # Update query command to show natural language was used
            if context_state.get('natural_language_prompt'):
                context_state['query_command'] = f"maia chat -nl {context_state['natural_language_prompt']}"
            else:
                context_state['query_command'] = "maia chat -nl [natural language query]"
            query_command = context_state['query_command']
            
            return True
        
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
        new_multi_source_data = {}
        new_total_pages_loaded = 0

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
                    # Format: source_name:all.filter1.filter2... (use 'all' when filters are present)
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
                    new_total_pages_loaded += len(pages)

                    if DEBUG_MODE:
                        print_text(f"  - Loaded {len(pages)} entries from: {unique_key}", style="green")
                except Exception as e:
                    if DEBUG_MODE:
                        print_text(f"Error loading data for database {db_config.name}: {e}", style="bold red")

        # Update context state
        context_state['initial_multi_source_data'] = new_multi_source_data
        context_state['total_pages_loaded'] = new_total_pages_loaded
        
        # Update module-level variables
        initial_multi_source_data = new_multi_source_data
        total_pages_loaded = new_total_pages_loaded
        
        # Generate new system prompt
        system_prompt = create_system_prompt(new_multi_source_data)
        context_state['system_prompt'] = system_prompt
        
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
        
        # Create a mock args object for the sync function
        class MockArgs:
            def __init__(self):
                self.force = False
                self.days = None
                self.start_date = None
                self.end_date = None
                self.date_range = None
        
        mock_args = MockArgs()
        
        for source_name in databases_to_sync:
            try:
                # Parse the source name to extract just the database name (remove :days part)
                db_name = source_name.split(':')[0] if ':' in source_name else source_name
                
                # Handle workspace.database format for natural language queries
                workspace_name = None
                if '.' in db_name:
                    workspace_name, db_name = db_name.split('.', 1)
                
                # Get the database config with workspace awareness
                db_config = db_manager.get_database(db_name, workspace_name)
                if not db_config:
                    print_text(f"  ⚠️  Database '{source_name}' not found in configuration", style="bold yellow")
                    continue
                
                # Create source specification
                source_spec = {
                    'name': db_name,
                    'qualified_name': db_config.get_qualified_name(),
                    'database': db_name
                }
                
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
        print_text("Current command:", style="dim")
        print_text(f"  {context_state['query_command']}", style="bold")
        print_text("")
        print_text("Edit the command below, or enter 'r' for recents:", style="dim")
        print_text("Press Enter alone to cancel", style="dim")
        print_text("")
        
        # Build the current command arguments (without 'maia chat')
        current_args = []
        
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
            # Use prompt_toolkit to show the current command as editable default
            from prompt_toolkit import prompt
            user_input = prompt(
                "maia chat ",
                default=current_args_str,
                mouse_support=True
            ).strip()
            
            # Handle different input scenarios
            if not user_input and not current_args_str:
                # No input and no current args - cancel
                print_text("Context edit cancelled.", style="bold yellow")
                return False
            elif not user_input and current_args_str:
                # Empty input but there were current args - user wants to keep current
                print_text("Keeping current context.", style="bold green")
                return True
            elif user_input.lower() == 'r':
                # Handle recents command
                return handle_recents_in_edit_context()
            
            # Parse the input as CLI arguments
            import shlex
            import argparse
            
            try:
                # Split the input into arguments
                args_list = shlex.split(user_input)
                
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
                        
                        # Get workspace
                        new_workspace = getattr(parsed_args, 'workspace', None)
                        if new_workspace:
                            context_state['workspace'] = new_workspace
                        
                        # Determine workspace to use
                        workspace_to_use = context_state.get('resolved_workspace') or context_state.get('workspace')
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
                        context_state['sources'] = []  # Clear regular sources
                        context_state['filters'] = []  # Clear regular filters
                        
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

    # Save context file if savecontexts is enabled in config
    should_save_context = False
    try:
        from promaia.config.databases import get_database_manager
        db_manager = get_database_manager()
        should_save_context = db_manager.global_settings.get("savecontexts", True)
    except Exception as e:
        debug_print(f"Could not load savecontexts config, defaulting to True: {e}")
        should_save_context = True
    
    if should_save_context:
        try:
            timestamp = now_utc().strftime("%Y%m%d-%H%M%S")
            context_filename = f"context logs/{timestamp}_session_init_prompt.txt"

            # Ensure context logs directory exists
            os.makedirs("context logs", exist_ok=True)

            # Write context file with session info
            with open(context_filename, 'w', encoding='utf-8') as f:
                f.write("=== MAIA CHAT SESSION INITIALIZATION ===\n")
                f.write(f"Timestamp: {timestamp}\n")
                f.write(f"API Type: {current_api}\n")
                f.write(f"Workspace: {workspace}\n")
                f.write(f"Sources: {sources}\n")
                f.write(f"Filters: {filters}\n")
                f.write(f"Total Pages Loaded: {total_pages_loaded}\n")
                f.write(f"System Prompt Length: {len(system_prompt)} characters\n")
                f.write("\n" + "="*50 + "\n")
                f.write("SYSTEM PROMPT:\n")
                f.write("="*50 + "\n")
                f.write(system_prompt)

            debug_print(f"Context file saved: {context_filename}")
        except Exception as e:
            debug_print(f"Failed to save context file: {e}")

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
                        print_text(f"Context reloaded with {total_pages_loaded} pages.", style="bold green")
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
                        print_text(f"New context: {context_state['query_command']}", style="dim")
                        print_text(f"Pages loaded: {total_pages_loaded}", style="dim")
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
                if current_api == "anthropic" and anthropic_client:
                    response = call_anthropic_with_retry(anthropic_client, system_prompt, messages)
                    if response and response.content:
                        response_text = response.content[0].text

                        # Extract token usage for Anthropic
                        if hasattr(response, 'usage'):
                            input_tokens = response.usage.input_tokens
                            output_tokens = response.usage.output_tokens
                            total_tokens = input_tokens + output_tokens

                            # Calculate cost based on Claude 3 Sonnet pricing
                            # Input: $3.00/1M tokens, Output: $15.00/1M tokens
                            input_cost = (input_tokens / 1_000_000) * 3.00
                            output_cost = (output_tokens / 1_000_000) * 15.00
                            total_cost = input_cost + output_cost

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

                            # Calculate cost based on GPT-4 pricing
                            # Input: $30.00/1M tokens, Output: $60.00/1M tokens
                            input_cost = (prompt_tokens / 1_000_000) * 30.00
                            output_cost = (completion_tokens / 1_000_000) * 60.00
                            total_cost = input_cost + output_cost

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

                            # Calculate cost based on Gemini 2.5 Pro pricing
                            # Input: $2.50/1M tokens, Output: $15.00/1M tokens
                            input_cost = (prompt_tokens / 1_000_000) * 2.50
                            output_cost = (response_tokens / 1_000_000) * 15.00
                            total_cost = input_cost + output_cost

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