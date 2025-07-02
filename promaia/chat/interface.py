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
from typing import List, Dict, Any

from promaia.storage.files import read_markdown_files_with_registry
from promaia.utils.config import load_environment, get_last_sync_time
from promaia.config.workspaces import get_workspace_manager
from promaia.ai.prompts import create_system_prompt
from promaia.utils.display import print_markdown, print_text

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
    """Displays a message with a timestamp."""
    if role == 'assistant':
        print_markdown(f"**Maia:** {content}")
    elif role == 'user':
        print_text(f"You: {content}", style="bold cyan")
    else:
        print_text(content, style="yellow")

def print_welcome_message():
    """Prints the welcome message for a chat session."""
    print("\n" + "=" * 40)
    print("Welcome to Maia Chat!")
    print("\nType your message and press Enter to chat.")
    print("Available commands:")
    print("  /quit  - Exit the chat")
    print("  /debug - Toggle debug mode")
    print("  /push  - Push the current chat session to Notion")
    print("  /help  - Show this help message")
    print("=" * 40 + "\n")

# --- Core Chat Logic ---

async def push_chat_to_notion(messages):
    """Pushes the current chat history to a new Notion page."""
    # This is a placeholder for the actual implementation
    print("\n[Pushing chat to Notion...]")
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

    # 1. Determine Workspace
    workspace_manager = get_workspace_manager()
    if not workspace:
        workspace = workspace_manager.get_default_workspace()
    if not workspace:
        print("ERROR: No workspace available. Please configure one.")
        return

    # 2. Determine and Process Sources
    from promaia.config.databases import get_database_manager
    from promaia.cli.database_commands import parse_source_specs, parse_filter_expression

    db_manager = get_database_manager()
    initial_multi_source_data = {}

    if not sources:
        debug_print(f"No sources provided, loading all databases for workspace '{workspace}'.")
        workspace_databases = db_manager.get_workspace_databases(workspace)
        sources = [db.nickname for db in workspace_databases]
        if not sources:
            print(f"Warning: No databases configured for workspace '{workspace}'. Chat will lack context.")

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
                        print(f"Warning: Invalid filter '{filter_expr}': {e}")
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
            print(f"Warning: Error parsing source specifications: {e}")

    if parsed_sources_init:
        print("Loading context from sources...")
        for source_conf in parsed_sources_init:
            db_name = source_conf['database']
            db_config = db_manager.get_database(db_name)
            if not db_config:
                print(f"Warning: Config for database '{db_name}' not found. Skipping.")
                continue

            try:
                pages = read_markdown_files_with_registry(
                    db_config,
                    days=source_conf.get('days'),
                    comparison_filters=source_conf.get('comparison_filters', {}),
                    complex_filter=source_conf.get('complex_filter')
                )
                initial_multi_source_data[db_config.nickname] = pages
                print(f"  - Loaded {len(pages)} entries from: {db_config.nickname}")
            except Exception as e:
                print(f"Error loading data for database {db_config.name}: {e}")

    # 5. Generate System Prompt
    system_prompt = create_system_prompt(initial_multi_source_data)
    debug_print(f"System prompt generated ({len(system_prompt)} chars).")

    # 6. Save debug file if debug mode is enabled
    if DEBUG_MODE:
        debug_dir = "debug"
        os.makedirs(debug_dir, exist_ok=True)
        timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        debug_file = os.path.join(debug_dir, f"{timestamp}_session_init_prompt.txt")
        
        try:
            with open(debug_file, "w", encoding="utf-8") as f:
                f.write(f"Chat Session Debug Info\n")
                f.write(f"======================\n")
                f.write(f"Timestamp: {datetime.datetime.now().isoformat()}\n")
                f.write(f"API Type: {current_api}\n")
                f.write(f"Workspace: {workspace}\n")
                f.write(f"Sources: {sources}\n")
                f.write(f"Filters: {filters}\n")
                f.write(f"Processed Sources: {processed_sources}\n")
                f.write(f"System Prompt Length: {len(system_prompt)} chars\n\n")
                f.write(f"System Prompt Content:\n")
                f.write(f"=====================\n")
                f.write(system_prompt)
            debug_print(f"Debug file saved: {debug_file}")
        except Exception as e:
            debug_print(f"Failed to save debug file: {e}")

    # 7. Display Welcome Message
    print_welcome_message()

    # 8. Initialize Messages
    messages = []
    if current_api != "anthropic":
        messages.append({"role": "system", "content": system_prompt})

    # 9. Non-interactive Mode
    if non_interactive:
        print("---MAIA_BACKEND_READY---", flush=True)
        return

    # 10. Interactive Chat Loop
    while True:
        try:
            user_input = session.prompt(HTML('<style fg="green">You: </style>')).strip()
            if not user_input:
                continue

            if user_input.lower().startswith('/'):
                if user_input.lower() in ['/exit', '/quit']:
                    print("Goodbye!")
                    break
                elif user_input.lower() == '/help':
                    print_welcome_message()
                elif user_input.lower() == '/debug':
                    DEBUG_MODE = not DEBUG_MODE
                    os.environ["MAIA_DEBUG"] = "1" if DEBUG_MODE else "0"
                    print(f"Debug mode {'enabled' if DEBUG_MODE else 'disabled'}.")
                elif user_input.lower() == '/push':
                    asyncio.run(push_chat_to_notion(messages))
                else:
                    print(f"Unknown command: {user_input}")
                continue

            messages.append({"role": "user", "content": user_input})
            ai_reply_content = ""

            if current_api == "anthropic" and anthropic_client:
                response = call_anthropic_with_retry(anthropic_client, system_prompt, messages)
                if response:
                    ai_reply_content = response.content[0].text
            elif current_api == "openai" and openai_client:
                chat_completion = openai_client.chat.completions.create(messages=messages, model="gpt-4-turbo-preview")
                ai_reply_content = chat_completion.choices[0].message.content
            elif current_api == "gemini" and gemini_client:
                # Convert messages to the format expected by the Gemini API
                gemini_messages = []
                for m in messages:
                    if m['role'] == 'system':
                        continue # System role is handled separately in Gemini
                    
                    # Gemini uses 'model' for the assistant's role
                    role = 'user' if m['role'] == 'user' else 'model'
                    gemini_messages.append({'role': role, 'parts': [m['content']]})
                
                # The system prompt is now passed during model initialization,
                # but if we needed to pass it here, it would be different.
                # For this model, we re-create it with the system prompt.
                gemini_model = genai.GenerativeModel(
                    'gemini-2.5-pro',
                    system_instruction=system_prompt
                )
                
                response = gemini_model.generate_content(gemini_messages)
                ai_reply_content = response.text
            else:
                print(f"ERROR: API client for '{current_api}' is not available. Check your API keys.")
                continue

            if ai_reply_content:
                messages.append({"role": "assistant", "content": ai_reply_content})
                display_message_with_timestamp('assistant', ai_reply_content)

        except KeyboardInterrupt:
            print("\nGoodbye!")
            break
        except Exception as e:
            print(f"\nAn unexpected error occurred: {e}")
            debug_print(traceback.format_exc())
            break

def main():
    """Entry point for the chat interface, run from CLI."""
    import argparse
    parser = argparse.ArgumentParser(description="Maia Chat Interface")
    parser.add_argument("-s", "--sources", nargs='*', help="List of sources to load, e.g., 'journal:7'.")
    parser.add_argument("-f", "--filters", nargs='*', help="List of filters to apply.")
    parser.add_argument("-w", "--workspace", help="The workspace to use.")
    parser.add_argument("--non-interactive", action="store_true", help="Run in non-interactive mode.")
    args = parser.parse_args()
    chat(sources=args.sources, filters=args.filters, workspace=args.workspace, non_interactive=args.non_interactive)

if __name__ == '__main__':
    main() 