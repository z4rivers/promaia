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

def print_welcome_message(query_command=None, total_pages=0):
    """Prints the welcome message for a chat session."""
    # Use clean format for both debug and non-debug modes
    print_text("🐙 maia chat", style="bold cyan")
    if query_command:
        print_text(f"Query: {query_command}", style="dim")
    print_text(f"Pages loaded: {total_pages}", style="green")
    print_text("Available commands:")
    print_text("  /quit  - Exit the chat")
    print_text("  /debug - Toggle debug mode")
    print_text("  /push  - Push the current chat session to Notion")
    print_text("  /help  - Show this help message")
    print_text("")  # Empty line for spacing

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
    if sources:
        # Convert sources to proper format and integrate filters
        for source in sources:
            if filters:
                # Integrate filters into the source specification
                # Convert each filter expression and add to the source
                filter_parts = []
                for filter_expr in filters:
                    try:
                        converted_filter = parse_filter_expression(filter_expr)
                        filter_parts.append(converted_filter)
                    except Exception as e:
                        print_text(f"Warning: Invalid filter '{filter_expr}': {e}", style="bold yellow")
                        continue
                
                if filter_parts:
                    # Create a source spec with integrated filters
                    # Format: source_name:days.filter1.filter2...
                    source_with_filters = f"{source}:7.{'.'.join(filter_parts)}"
                    processed_sources.append(source_with_filters)
                else:
                    processed_sources.append(source)
            else:
                processed_sources.append(source)
    
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
                    complex_filter=source_conf.get('complex_filter')
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
                        response_content = response.content[0].text
                elif current_api == "openai" and openai_client:
                    formatted_messages = [{"role": "system", "content": system_prompt}] + messages
                    response = openai_client.chat.completions.create(
                        model="gpt-4",
                        messages=formatted_messages,
                        max_tokens=4096,
                        temperature=0.7
                    )
                    if response.choices:
                        response_content = response.choices[0].message.content
                elif current_api == "gemini" and gemini_client:
                    formatted_prompt = f"System: {system_prompt}\n\nConversation:\n"
                    for msg in messages:
                        formatted_prompt += f"{msg['role'].title()}: {msg['content']}\n"
                    
                    response = gemini_client.generate_content(formatted_prompt)
                    if response.text:
                        response_content = response.text
                else:
                    print_text(f"Error: {current_api} API client not available.", style="bold red")
                    continue
                
                if response_content:
                    # Use copy-friendly markdown display
                    print_markdown(response_content, title="Maia")
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