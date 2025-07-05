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

def display_message_with_timestamp(role, content):
    """Displays a message with a timestamp using copy-friendly Rich display."""
    if role == 'assistant':
        print_markdown(f"**Maia:** {content}")
    elif role == 'user':
        print_text(f"You: {content}", style="bold cyan")
    else:
        print_text(content, style="yellow")

def print_welcome_message(query_command, total_pages):
    """Prints the welcome message for the chat interface."""
    print_text("🐙 maia chat", style="bold magenta")
    print_text(f"Query: {query_command}", style="dim")
    if total_pages > 0:
        print_text(f"Pages loaded: {total_pages}", style="dim")
    print_text("Available commands: /quit /debug /push /help", style="dim")
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

def chat(sources=None, filters=None, workspace=None, non_interactive=False):
    """Main chat function with simplified, unified logic."""
    global current_api, DEBUG_MODE

    # Reconstruct the query command for display
    query_parts = ["maia", "chat"]
    if sources:
        if len(sources) == 1:
            query_parts.extend(["-s", sources[0]])
        else:
            query_parts.extend(["-s"] + sources)
    if filters:
        for filter_expr in filters:
            query_parts.extend(["-f", f'"{filter_expr}"'])
    if workspace:
        query_parts.extend(["-w", workspace])
    query_command = " ".join(query_parts)

    # 1. Determine Workspace
    workspace_manager = get_workspace_manager()
    if not workspace:
        workspace = workspace_manager.get_default_workspace()
    if not workspace:
        print_text("ERROR: No workspace available. Please configure one.", style="bold red")
        return

    # 2. Determine and Process Sources
    from promaia.config.databases import get_database_manager
    from promaia.cli.database_commands import parse_source_specs, parse_filter_expression

    db_manager = get_database_manager()
    initial_multi_source_data = {}
    total_pages_loaded = 0

    if not sources:
        debug_print(f"No sources provided, loading all databases for workspace '{workspace}'.")
        workspace_databases = db_manager.get_workspace_databases(workspace)
        sources = [db.nickname for db in workspace_databases]
        if not sources:
            print_text(f"Warning: No databases configured for workspace '{workspace}'. Chat will lack context.", style="bold yellow")

    if filters and sources:
        debug_print(f"Applying filters: {filters}")

    # 3. Process filters and integrate them into source specifications
    processed_sources = []
    source_specific_filters = {}  # Dict of source -> list of filters
    global_filters = []  # Filters without source prefix (backward compatibility)
    
    # Parse and categorize filters
    if filters:
        debug_print(f"Processing filters: {filters}")
        
        for filter_expr in filters:
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
    if sources and len(sources) > 1:
        if global_filters:
            print_text(
                "Error: In multi-source scenarios, all filters must specify a source prefix.\n"
                f"Example: Instead of '{global_filters[0]}', use 'source:\"{global_filters[0]}\"'\n"
                "Available sources: " + ", ".join(sources),
                style="bold red"
            )
            return
        
        # Check that all filter sources are valid
        for filter_source in source_specific_filters.keys():
            if filter_source not in sources:
                print_text(
                    f"Error: Filter source '{filter_source}' not found in specified sources.\n"
                    f"Available sources: {', '.join(sources)}",
                    style="bold red"
                )
                return
    
    # Build processed sources with appropriate filters
    if sources:
        for source in sources:
            # Determine which filters apply to this source
            applicable_filters = []
            
            # Add source-specific filters
            if source in source_specific_filters:
                applicable_filters.extend(source_specific_filters[source])
            
            # Add global filters (only in single-source scenarios or backward compatibility)
            if len(sources) == 1 or not source_specific_filters:
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
        for source in sources or []:
            filters_for_source = []
            if source in source_specific_filters:
                filters_for_source.extend([f"source-specific: {f}" for f in source_specific_filters[source]])
            if len(sources) == 1 or not source_specific_filters:
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
                initial_multi_source_data[db_config.nickname] = pages
                total_pages_loaded += len(pages)
                
                if DEBUG_MODE:
                    print_text(f"  - Loaded {len(pages)} entries from: {db_config.nickname}", style="green")
            except Exception as e:
                if DEBUG_MODE:
                    print_text(f"Error loading data for database {db_config.name}: {e}", style="bold red")

    # 5. Generate System Prompt
    system_prompt = create_system_prompt(initial_multi_source_data)
    debug_print(f"System prompt generated ({len(system_prompt)} chars).")

    # Save debug file if debug mode is enabled
    if DEBUG_MODE:
        try:
            timestamp = now_utc().strftime("%Y%m%d-%H%M%S")
            debug_filename = f"debug/{timestamp}_session_init_prompt.txt"
            
            # Ensure debug directory exists
            os.makedirs("debug", exist_ok=True)
            
            # Write debug file with session info
            with open(debug_filename, 'w', encoding='utf-8') as f:
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
            
            debug_print(f"Debug file saved: {debug_filename}")
        except Exception as e:
            debug_print(f"Failed to save debug file: {e}")

    # 6. Display Welcome Message
    print()
    print_welcome_message(query_command=query_command, total_pages=total_pages_loaded)

    # 7. Handle Non-interactive Mode
    if non_interactive:
        return

    # 8. Start Interactive Chat Loop
    messages = []
    
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
            elif user_input.strip().lower() == '/help':
                print_welcome_message(query_command=query_command, total_pages=total_pages_loaded)
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
    
    asyncio.run(chat(
        sources=args.sources,
        filters=args.filters,
        workspace=args.workspace,
        non_interactive=args.non_interactive
    ))

if __name__ == "__main__":
    main() 