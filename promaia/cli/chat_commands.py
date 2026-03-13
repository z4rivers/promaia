"""
Chat Command Handlers - extracted from cli.py

Contains the legacy interactive terminal REPL, workspace browsing,
history management, write/model commands, and all browse variants.
This is the "quarantine zone" - moved wholesale without internal refactoring.
"""
import os
import sys
import asyncio
import argparse
import logging
from typing import List

from promaia.utils.config import get_sync_days_setting, load_environment
load_environment()
from promaia.utils.display import print_text, print_markdown, print_separator
from promaia.utils.query_parsing import parse_vs_queries_with_params

logger = logging.getLogger(__name__)
# ==================== CORE COMMANDS ====================

def extract_database_names_from_sources(sources: List[str]) -> List[str]:
    """Extract database nicknames from source selections (e.g., 'koii.journal' -> 'journal')."""
    database_names = []
    for source in sources:
        if '.' in source:
            # Extract database name from workspace.database format
            _, db_name = source.split('.', 1)
            database_names.append(db_name)
        else:
            # Source is already just the database name
            database_names.append(source)
    return list(set(database_names))  # Remove duplicates

def chat_run(args):
    """Run the chat interface."""
    from promaia.chat.interface import chat
    from promaia.config.workspaces import get_workspace_manager
    
    # Handle recents option
    if getattr(args, 'recent', False):
        return chat_run_recents(args)
    
    # Handle -ws shortcut by converting to -b browse mode
    workspace_arg = getattr(args, 'workspace', None)
    if workspace_arg and not getattr(args, 'sources', None) and not getattr(args, 'browse', None):
        # Convert -ws workspace to -b workspace
        args.browse = [workspace_arg]
        args.workspace = None  # Clear original workspace arg
    
    # ========================================================================
    # ⚠️  CRITICAL BROWSE ARGUMENT PARSING - KEEP IN SYNC WITH EDIT MODE ⚠️
    # ========================================================================
    # This section parses -b (browse) arguments for the TOP-LEVEL browser.
    # The EDIT MODE browser (in chat/interface.py) must parse stored browse
    # commands using THE SAME LOGIC to maintain consistency.
    #
    # When modifying this parsing:
    # 1. Update handle_manual_browse_edit() in promaia/chat/interface.py
    # 2. Update handle_browse_in_edit_context() in promaia/chat/interface.py
    # 3. Test both: `maia chat -b X` AND /e editing with browse commands
    #
    # See: promaia/chat/interface.py - handle_manual_browse_edit()
    # See: promaia/chat/interface.py - handle_browse_in_edit_context()
    # ========================================================================
    
    # Handle browse option for workspace or Discord channel selection
    raw_browse_args = getattr(args, 'browse', None)
    sources = getattr(args, 'sources', None)

    # Initialize selected_sources to avoid scoping issues
    selected_sources = None
    
    # Flatten nested lists from multiple -b flags: [['trass'], ['trass.tg']] -> ['trass', 'trass.tg']
    # Also handles single -b with multiple args: [['trass', 'trass.tg']] -> ['trass', 'trass.tg']
    browse_args = None
    if raw_browse_args is not None:
        browse_args = []
        for item in raw_browse_args:
            if isinstance(item, list):
                browse_args.extend(item)
            else:
                browse_args.append(item)
    
    # Detect mixed commands: when user provides sources + browse, OR browse + SQL query, OR browse + vector search
    # ANY command with browse args should be treated as a mixed command to ensure browser launches first
    has_mixed_command = bool(browse_args) and (bool(sources) or (hasattr(args, 'sql_query') and args.sql_query) or (hasattr(args, 'vector_search') and args.vector_search))
    
    if browse_args is not None:
        # If this is a mixed command, handle it specially
        if has_mixed_command:
            if sources and browse_args:
                print_text("🔄 Detected mixed command with sources and browse. Browser will launch first...", style="cyan")
            elif hasattr(args, 'vector_search') and args.vector_search:
                print_text("🔄 Detected mixed command with browse and vector search. Browser will launch first...", style="cyan")
            else:
                print_text("🔄 Detected mixed command with browse and SQL query. Browser will launch first...", style="cyan")
            
            # browse_args is already flattened earlier
            browse_databases = browse_args or []

            # Get other arguments
            filters = getattr(args, 'filters', None)
            original_workspace = getattr(args, 'workspace', None)
            mcp_servers = getattr(args, 'mcp_servers', None)
            sql_prompt = None
            
            # Handle SQL query processing
            sql_prompts = []
            if hasattr(args, 'sql_query') and args.sql_query:
                # Handle both formats: list of strings (pre-processed) or list of lists (from argparse)
                if args.sql_query:
                    if isinstance(args.sql_query[0], list):
                        # From argparse: list of lists
                        sql_prompts = [' '.join(sql_args) for sql_args in args.sql_query if sql_args]
                    else:
                        # Pre-processed: list of strings
                        sql_prompts = args.sql_query
                else:
                    sql_prompts = []

                if len(sql_prompts) > 1:
                    print_text(f"🤖 Will process {len(sql_prompts)} SQL queries after browser", style="white")
                    for i, prompt in enumerate(sql_prompts):
                        print_text(f"   {i+1}. '{prompt}'", style="dim")
                elif sql_prompts:
                    print_text(f"🤖 Will process SQL query after browser: '{sql_prompts[0]}'", style="white")

            # Handle vector search processing
            vs_prompts = []
            if hasattr(args, 'vector_search') and args.vector_search:
                # Handle both formats: list of strings (pre-processed) or list of lists (from argparse)
                if args.vector_search:
                    if isinstance(args.vector_search[0], list):
                        # From argparse: list of lists
                        vs_prompts = [' '.join(vs_args) for vs_args in args.vector_search if vs_args]
                    else:
                        # Pre-processed: list of strings
                        vs_prompts = args.vector_search
                else:
                    vs_prompts = []

                # Vector search prompts will be shown later when processing with selected sources
            
            # Build original browse command to preserve user command for display
            original_command_parts = ["maia", "chat"]
            # For mixed commands, include sources in the command reconstruction
            if sources:
                for source in sources:
                    original_command_parts.extend(["-s", source])
            if browse_args:
                original_command_parts.append("-b")
                original_command_parts.extend(browse_args)
            if sql_prompts:
                # For original command reconstruction, combine all SQL prompts
                # Don't add quotes - the -sql argument parser handles multiple words with nargs="*"
                combined_sql = " ".join([f'-sql {prompt}' for prompt in sql_prompts])
                original_command_parts.append(combined_sql)
            if vs_prompts:
                # For original command reconstruction, combine all VS prompts
                # Don't add quotes - the -vs argument parser handles multiple words with nargs="*"
                combined_vs = " ".join([f'-vs {prompt}' for prompt in vs_prompts])
                original_command_parts.append(combined_vs)
            if mcp_servers:
                for server in mcp_servers:
                    original_command_parts.extend(["-mcp", server])
            original_browse_command = " ".join(original_command_parts)

            # For mixed commands with browse: -s + -b, -b + -sql, or -b + -vs combinations
            if browse_databases and (sources or sql_prompts or vs_prompts):
                print_text("🔄 Processing mixed command with browse. Launching browser first...", style="cyan")

                # Use the same browser launch logic as regular browse commands
                try:
                    # Determine workspace and setup browser parameters (copied from browse logic below)
                    from promaia.config.workspaces import get_workspace_manager
                    from promaia.config.databases import get_database_manager
                    workspace_manager = get_workspace_manager()
                    db_manager = get_database_manager()

                    # Detect multiple workspaces and handle accordingly
                    workspace_names_found = []

                    # First pass: collect all workspace names from browse arguments
                    for browse_spec in browse_databases:
                        # Remove day specification if present
                        base_name = browse_spec.split(':')[0] if ':' in browse_spec else browse_spec

                        # Check if this is a workspace name directly
                        if workspace_manager.validate_workspace(base_name):
                            if base_name not in workspace_names_found:
                                workspace_names_found.append(base_name)
                        # Check if this is a database name (workspace.database format)
                        elif '.' in base_name:
                            potential_workspace = base_name.split('.')[0]
                            if workspace_manager.validate_workspace(potential_workspace):
                                if potential_workspace not in workspace_names_found:
                                    workspace_names_found.append(potential_workspace)

                    # Determine workspace parameter for browser
                    if len(workspace_names_found) > 1:
                        # Multiple workspaces - use None and let browser handle via database_filter
                        original_workspace = None
                        use_workspace_expansion = False  # Don't expand to individual databases
                        print_text(f"INFO: Detected multiple workspaces: {', '.join(workspace_names_found)}", style="cyan")
                    elif len(workspace_names_found) == 1:
                        # Single workspace
                        original_workspace = workspace_names_found[0]
                        use_workspace_expansion = True  # Expand to individual databases
                    else:
                        original_workspace = None
                        use_workspace_expansion = False

                    # Build database filter for browser
                    database_filter = []
                    default_days = None

                    for browse_spec in browse_databases:
                        if ':' in browse_spec:
                            db_name, days_str = browse_spec.rsplit(':', 1)
                            try:
                                days = int(days_str)
                                if default_days is None:
                                    default_days = days
                                database_filter.append(db_name)
                            except ValueError:
                                database_filter.append(browse_spec)
                        else:
                            if workspace_manager.validate_workspace(browse_spec):
                                if use_workspace_expansion:
                                    # Single workspace - expand to all its databases
                                    workspace_databases = db_manager.get_workspace_databases(browse_spec)
                                    for db in workspace_databases:
                                        if db.browser_include:
                                            database_filter.append(db.get_qualified_name())
                                else:
                                    # Multiple workspaces - keep workspace name for browser to handle
                                    database_filter.append(browse_spec)
                            else:
                                database_filter.append(browse_spec)

                    # For mixed commands, launch browser UI with pre-selected sources
                    print_text(f"🔍 Launching browser UI for workspaces: {', '.join(workspace_names_found)}...", style="cyan")

                    # Build pre-selected sources prioritizing user's explicit sources
                    preselected_sources = []
                    
                    # Get default sources from chat config
                    from promaia.utils.config import get_chat_default_sources, get_chat_default_days
                    default_chat_sources = get_chat_default_sources()
                    default_chat_days = get_chat_default_days()

                    # First, create a map of user's explicit sources for overriding
                    user_source_map = {}
                    if sources:  # Only iterate if sources is not None
                        for source_spec in sources:
                            if ':' in source_spec:
                                db_name, days_part = source_spec.rsplit(':', 1)
                                user_source_map[db_name] = source_spec
                            else:
                                user_source_map[source_spec] = source_spec

                    # Add user's explicit sources first (only if they exist)
                    if sources:
                        preselected_sources.extend(sources)

                    # Then add databases with default_include that aren't already specified
                    for workspace_name in workspace_names_found:
                        # Get all databases for this workspace
                        workspace_databases = db_manager.get_workspace_databases(workspace_name)
                        for db in workspace_databases:
                            if db.browser_include:
                                qualified_name = db.get_qualified_name()

                                # Only add if not already specified by user and has default_include=true
                                if qualified_name not in user_source_map and db.default_include:
                                    # Use appropriate default days
                                    if default_days and isinstance(default_days, int) and default_days > 0:
                                        days_to_use = default_days
                                    elif db.default_days and isinstance(db.default_days, int) and db.default_days > 0:
                                        days_to_use = db.default_days
                                    else:
                                        days_to_use = default_chat_days
                                    preselected_sources.append(f"{qualified_name}:{days_to_use}")

                    print_text(f"🎯 Pre-selecting {len(preselected_sources)} sources (user + config defaults)", style="green")
                    
                    # Launch the browser UI with pre-selected sources
                    from promaia.cli.workspace_browser import launch_unified_browser
                    selected_sources = launch_unified_browser(
                        original_workspace,
                        default_days,
                        database_filter,
                        preselected_sources  # Pass pre-selected sources for UI
                    )

                    print_text(f"✅ Selected {len(selected_sources) if selected_sources else 0} sources from browser", style="green")

                    # Check if user cancelled browser selection
                    if not selected_sources:
                        print_text("❌ No sources selected from browser. Mixed command cancelled.", style="yellow")
                        return

                    # DEBUG: Check if we reach this point
                    print(f"DEBUG: After browser selection, about to process sources and call chat function")
                    print(f"DEBUG: selected_sources = {selected_sources}")

                    # Process Discord channel sources and convert to database + filter format
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

                    # Browser already includes user preferences, so just use the processed sources
                    all_sources = processed_sources
                    all_filters = processed_filters

                    print_text(f"🔄 Using sources from browser: {len(all_sources)} total", style="green")

                    # Process queries sequentially, then merge results
                    sql_query_content= None

                    # Step 1: Process SQL queries (if present)
                    if sql_prompts:
                        try:
                            from promaia.storage.unified_query import get_query_interface
                            query_interface = get_query_interface()

                            combined_sql_content = {}
                            for i, sql_prompt in enumerate(sql_prompts):
                                if len(sql_prompts) > 1:
                                    print_text(f"🔍 Processing SQL query {i+1}/{len(sql_prompts)}: '{sql_prompt}'", style="cyan")

                                # Process with verbose output (includes user interaction)
                                sql_content = query_interface.natural_language_query(sql_prompt, None, None, verbose=True)

                                if sql_content:
                                    # Merge results
                                    for db_name, entries in sql_content.items():
                                        if db_name not in combined_sql_content:
                                            combined_sql_content[db_name] = []
                                        combined_sql_content[db_name].extend(entries)

                            sql_query_content= combined_sql_content if combined_sql_content else None

                        except Exception as e:
                            print_text(f"❌ Error processing SQL query: {e}", style="red")
                            # Continue with VS query if present

                    # Step 2: Process vector search queries (if present)
                    if vs_prompts:
                        try:
                            from promaia.ai.nl_processor_wrapper import process_vector_search_to_content

                            combined_vs_content = {}
                            for i, vs_prompt in enumerate(vs_prompts):
                                if len(vs_prompts) > 1:
                                    print_text(f"🔍 Processing VS query {i+1}/{len(vs_prompts)}: '{vs_prompt}'", style="cyan")

                                # Process with verbose output (includes user interaction)
                                vs_content = process_vector_search_to_content(
                                    vs_prompt,
                                    workspace=None,
                                    verbose=True,
                                    n_results=getattr(args, 'top_k', 20),
                                    min_similarity=getattr(args, 'threshold', 0.75)
                                )

                                if vs_content:
                                    # Merge results
                                    for db_name, entries in vs_content.items():
                                        if db_name not in combined_vs_content:
                                            combined_vs_content[db_name] = []
                                        combined_vs_content[db_name].extend(entries)

                        except Exception as e:
                            print_text(f"❌ Error processing vector search query: {e}", style="red")

                    # Step 3: Launch chat with separate SQL and VS content (don't merge here)
                    from promaia.chat.interface import chat

                    # Prepare cache parameters for separate SQL and VS caching
                    combined_sql_prompt = " ".join(sql_prompts) if sql_prompts else None
                    combined_vs_prompt = " ".join(vs_prompts) if vs_prompts else None

                    chat(
                        sources=all_sources,
                        filters=all_filters,
                        workspace=original_workspace,
                        mcp_servers=mcp_servers,
                        original_browse_command=original_browse_command,
                        browse_selections=selected_sources,
                        sql_query_content=None,  # Will be set from initial_nl_content in chat()
                        sql_query_prompt=None,  # Already processed
                        is_vector_search=False,  # Already processed
                        # Pass separate SQL and VS content for independent tracking
                        initial_nl_prompt=combined_sql_prompt if sql_prompts else None,
                        initial_nl_content=combined_sql_content if sql_prompts and 'combined_sql_content' in locals() else None,
                        initial_vs_prompt=combined_vs_prompt if vs_prompts else None,
                        initial_vs_content=combined_vs_content if vs_prompts and 'combined_vs_content' in locals() else None,
                        top_k=getattr(args, 'top_k', None),
                        threshold=getattr(args, 'threshold', None)
                    )
                    return

                except Exception as e:
                    print_text(f"❌ Error in mixed command execution: {e}", style="red")
                    return

            # For -b + -sql combinations (no explicit sources), launch browser first
            elif not sources and browse_databases and sql_prompts:
                try:
                    # Determine workspace and setup browser parameters (copied from browse logic below)
                    from promaia.config.workspaces import get_workspace_manager
                    from promaia.config.databases import get_database_manager
                    workspace_manager = get_workspace_manager()
                    db_manager = get_database_manager()

                    # Detect multiple workspaces and handle accordingly
                    workspace_names_found = []

                    # First pass: collect all workspace names from browse arguments
                    for browse_spec in browse_databases:
                        # Remove day specification if present
                        base_name = browse_spec.split(':')[0] if ':' in browse_spec else browse_spec

                        # Check if this is a workspace name directly
                        if workspace_manager.validate_workspace(base_name):
                            if base_name not in workspace_names_found:
                                workspace_names_found.append(base_name)
                        # Check if this is a database name (workspace.database format)
                        elif '.' in base_name:
                            potential_workspace = base_name.split('.')[0]
                            if workspace_manager.validate_workspace(potential_workspace):
                                if potential_workspace not in workspace_names_found:
                                    workspace_names_found.append(potential_workspace)

                    # Determine workspace parameter for browser
                    if len(workspace_names_found) > 1:
                        # Multiple workspaces - use None and let browser handle via database_filter
                        original_workspace = None
                        use_workspace_expansion = False  # Don't expand to individual databases
                        print_text(f"INFO: Detected multiple workspaces: {', '.join(workspace_names_found)}", style="cyan")
                    elif len(workspace_names_found) == 1:
                        # Single workspace
                        original_workspace = workspace_names_found[0]
                        use_workspace_expansion = True  # Expand to individual databases
                    else:
                        # No workspaces found in browse args, fall back to original logic
                        if not original_workspace:
                            original_workspace = workspace_manager.get_default_workspace()
                        use_workspace_expansion = True
                    
                    # Parse browse databases
                    database_filter = []
                    default_days = None
                    
                    for browse_spec in browse_databases:
                        if ':' in browse_spec:
                            db_name, days_str = browse_spec.rsplit(':', 1)
                            try:
                                days = int(days_str)
                                if default_days is None:
                                    default_days = days
                                database_filter.append(db_name)
                            except ValueError:
                                database_filter.append(browse_spec)
                        else:
                            if workspace_manager.validate_workspace(browse_spec):
                                if use_workspace_expansion:
                                    # Single workspace - expand to all its databases
                                    workspace_databases = db_manager.get_workspace_databases(browse_spec)
                                    for db in workspace_databases:
                                        if db.browser_include:
                                            database_filter.append(db.get_qualified_name())
                                else:
                                    # Multiple workspaces - keep workspace name for browser to handle
                                    database_filter.append(browse_spec)
                            else:
                                database_filter.append(browse_spec)
                    
                    # For mixed commands, launch browser with pre-selected sources based on config and workspace
                    print_text(f"🔍 Launching browser for workspaces: {', '.join(workspace_names_found)}...", style="cyan")
                    
                    # Build pre-selected sources from config defaults and workspace context
                    preselected_sources = []
                    
                    # Get default sources from chat config
                    from promaia.utils.config import get_chat_default_sources, get_chat_default_days
                    default_chat_sources = get_chat_default_sources()
                    default_chat_days = get_chat_default_days()
                    
                    # For each workspace, add sources based on their default_include setting
                    for workspace_name in workspace_names_found:
                        workspace_databases = db_manager.get_workspace_databases(workspace_name)
                        for db in workspace_databases:
                            if db.browser_include:
                                qualified_name = db.get_qualified_name()
                                
                                # Check if this database should be pre-selected based on default_include
                                if db.default_include:
                                    # Use specified days or fall back to database/chat defaults
                                    days_to_use = default_days or db.default_days or default_chat_days
                                    if days_to_use:
                                        preselected_sources.append(f"{qualified_name}:{days_to_use}")
                                    else:
                                        preselected_sources.append(qualified_name)
                    
                    print_text(f"🎯 Pre-selecting {len(preselected_sources)} default sources based on config", style="green")
                    
                    # Launch unified browser with pre-selected sources
                    from promaia.cli.workspace_browser import launch_unified_browser
                    selected_sources = launch_unified_browser(
                        original_workspace,
                        default_days,
                        database_filter,
                        preselected_sources  # Pass pre-selected sources for UI
                    )
                    
                    # Process Discord channel sources and convert to database + filter format
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
                    for db_key, channels in discord_db_groups.items():
                        processed_sources.append(db_key)
                        # Create a single filter for all channels in this database with source prefix
                        channel_filter = " OR ".join(f'channel:"{channel}"' for channel in channels)
                        processed_filters.append(f"{db_key}:({channel_filter})")
                    
                    # Now call chat with the selected sources and natural language prompt
                    sources = processed_sources
                    if processed_filters:
                        filters = (filters or []) + processed_filters

                except Exception as e:
                    print_text(f"❌ Error in browser launch for mixed command: {e}", style="red")
                    return
            

            # For mixed commands, process queries sequentially then merge results
            try:
                sql_query_content= None

                # Step 1: Process natural language queries (if present)
                if sql_prompts:
                    try:
                        from promaia.storage.unified_query import get_query_interface
                        query_interface = get_query_interface()

                        combined_sql_content = {}
                        for i, sql_prompt in enumerate(sql_prompts):
                            if len(sql_prompts) > 1:
                                print_text(f"🔍 Processing NL query {i+1}/{len(sql_prompts)}: '{sql_prompt}'", style="cyan")

                            # Process with verbose output (includes user interaction)
                            sql_content = query_interface.natural_language_query(sql_prompt, None, None, verbose=True)

                            if sql_content:
                                # Merge results
                                for db_name, entries in sql_content.items():
                                    if db_name not in combined_sql_content:
                                        combined_sql_content[db_name] = []
                                    combined_sql_content[db_name].extend(entries)

                        sql_query_content= combined_sql_content if combined_sql_content else None

                    except Exception as e:
                        print_text(f"❌ Error processing natural language query: {e}", style="red")
                        # Continue with VS query if present

                # Step 2: Process vector search queries (if present)
                if vs_prompts:
                    try:
                        from promaia.ai.nl_processor_wrapper import process_vector_search_to_content

                        combined_vs_content = {}
                        for i, vs_prompt in enumerate(vs_prompts):
                            if len(vs_prompts) > 1:
                                print_text(f"🔍 Processing VS query {i+1}/{len(vs_prompts)}: '{vs_prompt}'", style="cyan")

                            # Process with verbose output (includes user interaction)
                            vs_content = process_vector_search_to_content(
                                vs_prompt,
                                workspace=None,
                                verbose=True,
                                n_results=getattr(args, 'top_k', 20),
                                min_similarity=getattr(args, 'threshold', 0.75)
                            )

                            if vs_content:
                                # Merge results
                                for db_name, entries in vs_content.items():
                                    if db_name not in combined_vs_content:
                                        combined_vs_content[db_name] = []
                                    combined_vs_content[db_name].extend(entries)

                    except Exception as e:
                        print_text(f"❌ Error processing vector search query: {e}", style="red")

                # Step 3: Pass separate NL and VS content to chat (don't merge here)
                # Prepare cache parameters for separate NL and VS caching
                combined_sql_prompt = " ".join(sql_prompts) if sql_prompts else None
                combined_vs_prompt = " ".join(vs_prompts) if vs_prompts else None

                chat(
                    sources=sources,
                    filters=filters,
                    workspace=original_workspace,
                    non_interactive=getattr(args, 'non_interactive', False),
                    sql_query_content=None,  # Will be set from initial_nl_content in chat()
                    sql_query_prompt=None,  # Already processed
                    browse_databases=None,
                    original_browse_command=original_browse_command,
                    browse_selections=selected_sources,
                    mcp_servers=mcp_servers,
                    is_vector_search=False,  # Already processed
                    # Pass separate NL and VS content for independent tracking
                    initial_nl_prompt=combined_sql_prompt if sql_prompts else None,
                    initial_nl_content=combined_sql_content if sql_prompts and 'combined_sql_content' in locals() else None,
                    initial_vs_prompt=combined_vs_prompt if vs_prompts else None,
                    initial_vs_content=combined_vs_content if vs_prompts and 'combined_vs_content' in locals() else None,
                    top_k=getattr(args, 'top_k', None),
                    threshold=getattr(args, 'threshold', None)
                )
                return
            except Exception as e:
                print_text(f"❌ Error in mixed command execution: {e}", style="red")
                return


        # Handle non-mixed browse commands (existing logic)
        # If browse is provided without other sources, determine type of browse
        elif not getattr(args, 'sources', None) and not browse_args:
            return chat_run_browse(args)  # Default Discord browse
        # Check if this is a workspace browse or Discord browse
        elif browse_args is not None and len(browse_args) == 1:
            browse_target = browse_args[0]
            # Check if it's a workspace name
            from promaia.config.workspaces import get_workspace_manager
            workspace_manager = get_workspace_manager()
            if workspace_manager.validate_workspace(browse_target):
                return chat_run_workspace_browse(args, browse_target)
            else:
                # Treat as Discord database browse
                return chat_run_inline_browse(args)
        # Check if this is a multi-workspace browse
        elif browse_args is not None and len(browse_args) > 1:
            from promaia.config.workspaces import get_workspace_manager
            workspace_manager = get_workspace_manager()
            
            # Check if all arguments are workspace names
            all_workspaces = all(workspace_manager.validate_workspace(arg) for arg in browse_args)
            
            if all_workspaces:
                # Multi-workspace browse - pass all workspaces
                return chat_run_multi_workspace_browse(args, browse_args)
            else:
                # Mixed or Discord database browse
                return chat_run_inline_browse(args)
        # Otherwise, handle inline browse functionality (Discord)
        elif browse_args is not None:  # browse_args could be empty list or list with databases
            return chat_run_inline_browse(args)
    
    # Handle regular commands (no browse)
    sources = getattr(args, 'sources', None)
    filters = getattr(args, 'filters', None)
    original_workspace = getattr(args, 'workspace', None)
    mcp_servers = getattr(args, 'mcp_servers', None)
    sql_prompt = None
    
    # Handle SQL query processing
    # NOTE: This -sql parsing MUST stay in sync with:
    # 1. Edit mode parsing in promaia/chat/interface.py (lines ~2148-2163)
    # 2. safe_split_command() function in interface.py (line ~514)
    # These are two sides of one feature and must handle multiple -sql arguments identically.
    sql_prompts = []
    if hasattr(args, 'sql_query') and args.sql_query:
        # With action="append" and nargs="+", we get a list of lists
        # Each inner list contains the tokens for one -sql argument
        sql_prompts = [' '.join(sql_args) for sql_args in args.sql_query if sql_args]
        # Note: Don't print "Processing..." messages here - the processor handles output

        try:
            from promaia.storage.unified_query import get_query_interface

            # Resolve workspace first for natural language processing
            workspace_manager = get_workspace_manager()
            if original_workspace:
                if not workspace_manager.validate_workspace(original_workspace):
                    print_text(f"✗ Workspace '{original_workspace}' is not properly configured.", style="red")
                    return
                resolved_workspace = original_workspace
            else:
                resolved_workspace = workspace_manager.get_default_workspace()
                if not resolved_workspace:
                    print_text("No workspace specified and no default workspace configured.", style="red")
                    return

            # Process natural language using hybrid query interface
            query_interface = get_query_interface()

            # Process each NL query separately and combine results
            combined_sql_content = {}
            total_results = 0

            for i, sql_prompt in enumerate(sql_prompts):
                # Show query number only for multiple queries
                if len(sql_prompts) > 1:
                    print_text(f"🔍 Processing query {i+1}/{len(sql_prompts)}: '{sql_prompt}'", style="cyan")

                # Always allow cross-workspace queries for natural language
                # Workspace is just a classifier/tag, not a mandatory constraint
                # Enable verbose=True to show SQL generation steps and chain of thought
                sql_content = query_interface.natural_language_query(sql_prompt, None, None, verbose=True)

                if sql_content:
                    # Merge results from this query into combined content
                    for db_name, entries in sql_content.items():
                        if db_name not in combined_sql_content:
                            combined_sql_content[db_name] = []
                        combined_sql_content[db_name].extend(entries)

                    query_results = sum(len(entries) for entries in sql_content.values())
                    total_results += query_results
                    if len(sql_prompts) > 1:
                        print_text(f"   ✅ Query {i+1} found {query_results} results", style="green")
                else:
                    if len(sql_prompts) > 1:
                        print_text(f"   ⚠️  Query {i+1} found no results", style="yellow")

            if not combined_sql_content:
                return

            if len(sql_prompts) > 1:
                print_text(f"🎯 Combined {len(sql_prompts)} queries: {total_results} total results", style="green")
            sql_query_content= combined_sql_content

            # Keep both regular sources and natural language content
            # The chat interface will combine them
            
        except ImportError as e:
            print_text(f"Error importing natural language processor: {e}", style="red")
            return
        except Exception as e:
            print_text(f"Error processing natural language query: {e}", style="red")
            return
    else:
        sql_query_content= None
    
    # Process vector search queries (similar to natural language but uses semantic search)
    # Parse -vs queries with their per-query -tk/-th parameters from sys.argv
    vs_queries_structured = []
    if hasattr(args, 'vector_search') and args.vector_search:
        vs_queries_structured = parse_vs_queries_with_params(sys.argv)

        # Backward compatibility: extract simple query list
        vs_prompts = [q['query'] for q in vs_queries_structured]

        try:
            from promaia.ai.nl_processor_wrapper import process_vector_search_to_content
            
            # Resolve workspace first for vector search processing
            workspace_manager = get_workspace_manager()
            if original_workspace:
                if not workspace_manager.validate_workspace(original_workspace):
                    print_text(f"✗ Workspace '{original_workspace}' is not properly configured.", style="red")
                    return
                resolved_workspace = original_workspace
            else:
                resolved_workspace = workspace_manager.get_default_workspace()
                if not resolved_workspace:
                    print_text("No workspace specified and no default workspace configured.", style="red")
                    return
            
            # Process each vector search query separately and combine results
            combined_vs_content = {}
            total_results = 0
            vs_per_query_cache = {}  # Build cache for initial queries

            for i, vs_query_obj in enumerate(vs_queries_structured):
                vs_prompt = vs_query_obj['query']
                query_top_k = vs_query_obj['top_k']
                query_threshold = vs_query_obj['threshold']

                # Show query number only for multiple queries
                if len(vs_queries_structured) > 1:
                    print_text(f"🔍 Processing query {i+1}/{len(vs_queries_structured)}: '{vs_prompt}'", style="cyan")

                # Process vector search with per-query parameters
                vs_content = process_vector_search_to_content(
                    vs_prompt,
                    workspace=None,  # Allow cross-workspace searches
                    verbose=True,  # Show detailed processing steps (matching SQL mode)
                    n_results=query_top_k,
                    min_similarity=query_threshold
                )

                if vs_content:
                    # Cache this query's LOADED CONTENT with query+params as key
                    cache_key = f"{vs_prompt}|{query_top_k}|{query_threshold}"
                    vs_per_query_cache[cache_key] = vs_content

                    # Merge results from this query into combined content
                    for db_name, entries in vs_content.items():
                        if db_name not in combined_vs_content:
                            combined_vs_content[db_name] = []
                        combined_vs_content[db_name].extend(entries)

                    query_results = sum(len(entries) for entries in vs_content.values())
                    total_results += query_results
                    if len(vs_prompts) > 1:
                        print_text(f"   ✅ Query {i+1} found {query_results} results", style="green")
                else:
                    # Cache empty result with query+params as key
                    cache_key = f"{vs_prompt}|{query_top_k}|{query_threshold}"
                    vs_per_query_cache[cache_key] = {}
                    if len(vs_prompts) > 1:
                        print_text(f"   ⚠️  Query {i+1} found no results", style="yellow")
            
            if not combined_vs_content:
                print_text("❌ No content found for any vector search queries", style="red")
                return
            
            if len(vs_prompts) > 1:
                print_text(f"🎯 Combined {len(vs_prompts)} queries: {total_results} total results", style="green")
            
            # Store vector search content for passing to chat
            # IMPORTANT: DO NOT add vs_prompts to sql_prompts - they are separate query types!
            # The browser uses sql_prompts/combined_sql_prompt to create new queries, so we must keep VS separate
            if sql_query_content:
                # Merge VS results with existing NL results (content only, not prompts)
                for db_name, entries in combined_vs_content.items():
                    if db_name not in sql_query_content:
                        sql_query_content[db_name] = []
                    sql_query_content[db_name].extend(entries)
            else:
                # Just use VS content directly (content only, not prompts)
                sql_query_content= combined_vs_content
        
        except ImportError as e:
            print_text(f"Error importing vector search processor: {e}", style="red")
            return
        except Exception as e:
            print_text(f"Error processing vector search query: {e}", style="red")
            return
    
    # Non-interactive mode for the desktop app
    if not sys.stdout.isatty():
        # In non-interactive mode, the chat function is expected to 
        # initialize and then enter a loop to process messages from stdin.
        # This requires the `chat` function to be adapted for this behavior.
        # For now, we assume `chat` handles this.
        logging.info("Running in non-interactive mode.")

    try:
        # Resolve the actual workspace to use
        workspace_manager = get_workspace_manager()
        resolved_workspace = original_workspace
        
        # If no workspace is explicitly provided, try to determine from sources
        if not resolved_workspace and sources:
            for source in sources:
                if '.' in source:
                    # This is not an inference, but a direct determination from the qualified source name.
                    determined_workspace = source.split('.')[0]
                    if workspace_manager.validate_workspace(determined_workspace):
                        resolved_workspace = determined_workspace
                        print_text(f"INFO: Using workspace '{resolved_workspace}' from source '{source}'.", style="white")
                        break
        
        # If still no workspace, use the default
        if not resolved_workspace:
            resolved_workspace = workspace_manager.get_default_workspace()
            if not resolved_workspace:
                print_text("No workspace specified, none could be inferred, and no default workspace is configured.", style="red")
                return

        # Validate the final resolved workspace
        if not workspace_manager.validate_workspace(resolved_workspace):
            print_text(f"✗ Workspace '{resolved_workspace}' is not properly configured.", style="red")
            return
        
        # Save query to recents before executing (for both traditional and NL queries)
        # Skip if this is being called from browse mode (which handles its own recents saving)
        skip_recents = getattr(args, 'skip_recents_save', False)
        combined_sql_prompt = " ".join(sql_prompts) if sql_prompts else None
        if not skip_recents and (sources or filters or original_workspace or combined_sql_prompt):
            from promaia.storage.recents import RecentsManager
            recents_manager = RecentsManager()
            recents_manager.add_query(
                sources=sources,
                filters=filters,
                workspace=original_workspace,
                sql_query_prompt=combined_sql_prompt
            )
        
        # The `chat` function will now need to handle the main loop
        non_interactive = getattr(args, 'non_interactive', False) or not sys.stdout.isatty()
        
        # Check if this came from browse mode and extract browse information
        original_browse_command = getattr(args, 'original_browse_command', None)
        browse_selections = getattr(args, 'browse_selections', None)

        # Determine if this is vector search mode - check if we have vector search prompts
        is_vector_search_mode = bool(hasattr(args, 'vector_search') and args.vector_search)

        # Pass per-query cache if available (from vector search processing)
        vs_cache = vs_per_query_cache if is_vector_search_mode and 'vs_per_query_cache' in locals() else None

        chat(sources=sources, filters=filters, workspace=original_workspace, resolved_workspace=resolved_workspace, non_interactive=non_interactive, sql_query_content=sql_query_content, sql_query_prompt=combined_sql_prompt, original_browse_command=original_browse_command, browse_selections=browse_selections, mcp_servers=mcp_servers, is_vector_search=is_vector_search_mode, top_k=getattr(args, 'top_k', None), threshold=getattr(args, 'threshold', None), vector_search_queries=vs_queries_structured if is_vector_search_mode else None, initial_vs_per_query_cache=vs_cache)

    except ImportError as e:
        print_text(f"Error importing chat interface: {e}", style="red")
        print_text("Please check your dependencies.", style="red")
    except Exception as e:
        logging.error(f"An unexpected error occurred in chat_run: {e}", exc_info=True)
        print_text(f"An unexpected error occurred: {e}", style="red")


def chat_run_recents(args):
    """Run the chat interface with recent queries selection."""
    from promaia.chat.recents_interface import RecentsSelector, edit_query_string
    from promaia.config.workspaces import get_workspace_manager
    
    try:
        selector = RecentsSelector()
        action, selected_query = selector.select_query()
        
        if action == 'quit' or not selected_query:
            return
        
        if action == 'edit':
            # Allow user to edit the query
            edited_query = edit_query_string(selected_query)
            if not edited_query:
                return
            selected_query = edited_query
        
        # Handle special "chat_raw" command type for browse mode and complex commands
        if hasattr(selected_query, 'command') and selected_query.command == "chat_raw":
            # Execute the raw command stored in sources[0]
            raw_command = selected_query.sources[0] if selected_query.sources else ""
            print_text(f"\nExecuting: maia chat {raw_command}", style="white")
            
            # Parse the raw command and execute it
            try:
                from promaia.chat.recents_interface import safe_split_command
                raw_args = safe_split_command(raw_command)

                # Pre-process to handle multiple -nl arguments
                # NOTE: This logic MUST match edit mode in promaia/chat/interface.py
                # Both edit mode and top-level query are two sides of one feature.
                processed_args = []
                nl_arguments = []
                i = 0
                while i < len(raw_args):
                    arg = raw_args[i]
                    if arg in ['-nl', '--natural-language']:
                        # Collect the -nl argument and its value
                        nl_value = []
                        i += 1  # Move past the -nl flag
                        while i < len(raw_args) and not raw_args[i].startswith('-'):
                            nl_value.append(raw_args[i])
                            i += 1
                        if nl_value:
                            nl_arguments.append(' '.join(nl_value))
                    else:
                        processed_args.append(arg)
                        i += 1

                # Create a new argument parser and parse the processed command
                import argparse
                parser = argparse.ArgumentParser(description="Execute raw chat command")
                parser.add_argument("--source", "-s", action="append", dest="sources")
                parser.add_argument("--filter", "-f", action="append", dest="filters")
                parser.add_argument("--workspace", "-ws", dest="workspace")
                parser.add_argument("--browse", "-b", action="append", nargs="*", dest="browse")
                parser.add_argument("--sql-query", "-sql", nargs="*", dest="sql_query")
                parser.add_argument("--natural-language", "-nl", nargs="*", dest="sql_query")  # Deprecated alias

                parsed_args = parser.parse_args(processed_args)
                parsed_args.recent = False  # Prevent recursion

                # Add the collected SQL arguments
                if nl_arguments:
                    parsed_args.sql_query = nl_arguments
                
                # Execute using the main chat function
                chat_run(parsed_args)
                return
                
            except Exception as e:
                print_text(f"Error executing raw command: {e}", style="red")
                return
        
        # Create args object for the selected/edited query
        class QueryArgs:
            def __init__(self, query):
                self.sources = query.sources
                self.filters = query.filters
                self.workspace = query.workspace or getattr(args, 'workspace', None)
                self.recent = False  # Prevent infinite recursion
                self.browse = None  # No browse mode for regular queries
                # Add SQL query support
                if hasattr(query, 'sql_query_prompt') and query.sql_query_prompt:
                    self.natural_language = [query.sql_query_prompt]
                else:
                    self.natural_language = None
        
        query_args = QueryArgs(selected_query)
        
        # Execute the selected query
        print_text(f"\nExecuting: {str(selected_query).split(' (')[0]}", style="white")
        chat_run(query_args)
        
    except ImportError as e:
        print_text(f"Error importing recents interface: {e}", style="red")
        print_text("Please check your dependencies.", style="red")
    except Exception as e:
        logging.error(f"An unexpected error occurred in chat_run_recents: {e}", exc_info=True)
        print_text(f"An unexpected error occurred: {e}", style="red")

def chat_run_browse(args):
    """Run the chat interface with Discord channel browser."""
    import asyncio
    from promaia.cli.discord_commands import handle_discord_browse
    from promaia.config.workspaces import get_workspace_manager
    from promaia.chat.interface import chat
    
    try:
        # Get workspace
        workspace_manager = get_workspace_manager()
        workspace = getattr(args, 'workspace', None)
        
        if not workspace:
            workspace = workspace_manager.get_default_workspace()
            if not workspace:
                print_text("No workspace specified and no default workspace configured.", style="red")
                return
        
        # Validate workspace
        if not workspace_manager.validate_workspace(workspace):
            print_text(f"✗ Workspace '{workspace}' is not properly configured.", style="red")
            return
        
        # Create args for Discord browse
        class BrowseArgs:
            def __init__(self, workspace):
                self.workspace = workspace
        
        browse_args = BrowseArgs(workspace)
        
        # Run the Discord browser and get selected channels
        print_text(f"🎮 Launching Discord channel browser for workspace '{workspace}'...", style="white")
        
        # Run the async Discord browse function
        async def run_browse():
            from promaia.cli.discord_commands import handle_discord_browse
            return await handle_discord_browse(browse_args)
        
        selected_channels = asyncio.run(run_browse())
        
        if not selected_channels:
            print_text("ℹ️  No channels selected for chat.", style="dim")
            return
        
        # Convert selected channels to chat sources format
        sources = []
        filters = []
        
        # Group channels by database
        db_channels = {}
        for db_name, channel_id, channel_name in selected_channels:
            if db_name not in db_channels:
                db_channels[db_name] = []
            db_channels[db_name].append(channel_name)
        
        # Create sources and filters
        for db_name, channels in db_channels.items():
            sources.append(db_name)  # Just the database name
            
            # Create source-prefixed channel filter for this database
            if len(channels) == 1:
                filters.append(f'{db_name}:"channel_name={channels[0]}"')
            else:
                # Multiple channels - use OR filter within the source
                channel_filter = " OR ".join([f"channel_name={ch}" for ch in channels])
                filters.append(f'{db_name}:"({channel_filter})"')
        
        print_text(f"✅ Selected {len(selected_channels)} Discord channels for chat:", style="white")
        for db_name, channels in db_channels.items():
            for channel in channels:
                print_text(f"   • {db_name} → #{channel}", style="white")
        
        # Create modified args for chat
        class ChatArgs:
            def __init__(self, sources, filters, workspace):
                self.sources = sources
                self.workspace = workspace
                self.filters = filters
                self.recent = False
                self.browse = False
                self.non_interactive = False
                self.natural_language = None
        
        chat_args = ChatArgs(sources, filters, workspace)
        
        # Start chat with selected sources
        print_text(f"\n💬 Starting chat with selected Discord channels...", style="white")
        chat_run(chat_args)
        
    except Exception as e:
        logging.error(f"An unexpected error occurred in chat_run_browse: {e}", exc_info=True)
        print_text(f"An unexpected error occurred: {e}", style="red")


def chat_run_inline_browse(args):
    """
    Run the chat interface with unified browser for Discord databases.
    
    ⚠️  CRITICAL: TOP-LEVEL BROWSER - KEEP IN SYNC WITH EDIT MODE BROWSER ⚠️
    
    This function implements the TOP-LEVEL browser used when starting chat with -b flag.
    It has a TWIN in promaia/chat/interface.py called handle_browse_in_edit_context() and
    handle_manual_browse_edit() that implement the EDIT MODE browser (accessed via /e).
    
    IMPORTANT SYNCHRONIZATION RULES FOR AI ASSISTANTS:
    1. These two browsers MUST work identically - same arguments, same database parsing, same behavior
    2. When you modify THIS function's argument parsing or database handling, you MUST update the
       edit mode browser functions in chat/interface.py with the same logic
    3. When you modify browse-related args.browse parsing here, update it in edit mode too
    4. The context_state dict in chat/interface.py stores browse info - keep format consistent
    5. Both use launch_unified_browser() - any changes to that affect both
    
    BEFORE MODIFYING THIS FUNCTION:
    - Read handle_browse_in_edit_context() in promaia/chat/interface.py
    - Read handle_manual_browse_edit() in promaia/chat/interface.py  
    - Understand how they parse commands and launch browsers
    - Make parallel changes to keep them synchronized
    
    TEST REQUIREMENTS:
    - Test both: `maia chat -b trass.tg` AND using /e to change browse context
    - Verify workspace names work: `maia chat -b trass` AND /e with workspace
    - Verify Discord servers work: `maia chat -b trass.tg` AND /e with servers
    - Verify multi-workspace: `maia chat -b trass koii` AND /e with multiple
    
    See: promaia/chat/interface.py - handle_browse_in_edit_context()
    See: promaia/chat/interface.py - handle_manual_browse_edit()
    """
    from promaia.cli.workspace_browser import launch_unified_browser
    from promaia.config.workspaces import get_workspace_manager
    from promaia.chat.interface import chat
    
    try:
        # Get workspace
        workspace_manager = get_workspace_manager()
        original_workspace = getattr(args, 'workspace', None)
        
        # Resolve workspace
        resolved_workspace = original_workspace
        sources = getattr(args, 'sources', None) or []
        # Flatten nested lists from multiple -b flags: [['trass.tg'], ['trass']] -> ['trass.tg', 'trass']
        raw_browse = getattr(args, 'browse', [])
        browse_databases = []
        if raw_browse:
            for item in raw_browse:
                if isinstance(item, list):
                    browse_databases.extend(item)
                else:
                    browse_databases.append(item)
        
        # If no workspace, try to determine from sources or browse databases
        if not resolved_workspace and sources:
            for source in sources:
                if '.' in source:
                    determined_workspace = source.split('.')[0]
                    if workspace_manager.validate_workspace(determined_workspace):
                        resolved_workspace = determined_workspace
                        print_text(f"INFO: Using workspace '{resolved_workspace}' from source '{source}'.", style="white")
                        break
        
        if not resolved_workspace and browse_databases:
            for browse_db in browse_databases:
                db_name = browse_db.split(':')[0] if ':' in browse_db else browse_db
                if '.' in db_name:
                    determined_workspace = db_name.split('.')[0]
                    if workspace_manager.validate_workspace(determined_workspace):
                        resolved_workspace = determined_workspace
                        print_text(f"INFO: Using workspace '{resolved_workspace}' from browse database '{browse_db}'.", style="white")
                        break
        
        # If still no workspace, use the default
        if not resolved_workspace:
            resolved_workspace = workspace_manager.get_default_workspace()
            if not resolved_workspace:
                print_text("No workspace specified, none could be inferred, and no default workspace is configured.", style="red")
                return
        
        # Validate workspace
        if not workspace_manager.validate_workspace(resolved_workspace):
            print_text(f"✗ Workspace '{resolved_workspace}' is not properly configured.", style="red")
            return
        
        # Parse browse databases and expand workspace names
        database_filter = None
        default_days = None
        
        if browse_databases:
            from promaia.config.workspaces import get_workspace_manager
            from promaia.config.databases import get_database_manager
            workspace_manager = get_workspace_manager()
            db_manager = get_database_manager()
            
            database_filter = []
            for browse_spec in browse_databases:
                if ':' in browse_spec:
                    db_name, days_str = browse_spec.rsplit(':', 1)
                    try:
                        days = int(days_str)
                        if default_days is None:
                            default_days = days
                        
                        # Check if db_name is a workspace
                        if workspace_manager.validate_workspace(db_name):
                            # Expand workspace to all its databases
                            workspace_databases = db_manager.get_workspace_databases(db_name)
                            for db in workspace_databases:
                                if db.browser_include:  # Only include databases visible in browser
                                    database_filter.append(db.get_qualified_name())
                        else:
                            database_filter.append(db_name)
                    except ValueError:
                        database_filter.append(browse_spec)
                else:
                    # Check if this is a workspace name
                    if workspace_manager.validate_workspace(browse_spec):
                        # Expand workspace to all its databases
                        workspace_databases = db_manager.get_workspace_databases(browse_spec)
                        for db in workspace_databases:
                            if db.browser_include:  # Only include databases visible in browser
                                database_filter.append(db.get_qualified_name())
                    else:
                        # It's a specific database name
                        database_filter.append(browse_spec)
        
        # Show what we're browsing
        if database_filter:
            print_text(f"🔍 Launching unified browser for databases: {', '.join(database_filter)}...", style="cyan")
        else:
            print_text(f"🔍 Launching unified browser for workspace '{resolved_workspace}'...", style="cyan")
        
        # Launch unified browser
        selected_sources = launch_unified_browser(resolved_workspace, default_days, database_filter)
        
        if not selected_sources:
            print_text("ℹ️  No sources selected. Continuing with regular sources only.", style="dim")
            # Continue with just the regular sources
            all_sources = sources
            all_filters = getattr(args, 'filters', None) or []
        else:
            print_text(f"✅ Selected {len(selected_sources)} sources from unified browser", style="green")
            
            # Process Discord channel sources and convert to database + filter format
            processed_sources = []
            processed_filters = []
            
            # Group Discord channels by database to create proper source + filter combinations
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
            
            # Combine regular sources with processed sources
            all_sources = sources + processed_sources
            
            # Combine original filters with Discord filters
            original_filters = getattr(args, 'filters', None) or []
            all_filters = original_filters + processed_filters
        
        # Build the original browse command for display
        original_command_parts = ["maia", "chat"]
        
        if sources:
            for source in sources:
                original_command_parts.extend(["-s", source])
        
        if browse_databases:
            original_command_parts.append("-b")
            for browse_spec in browse_databases:
                original_command_parts.append(browse_spec)
        
        original_filters = getattr(args, 'filters', None) or []
        for filter_expr in original_filters:
            original_command_parts.extend(["-f", f'"{filter_expr}"'])
        
        if original_workspace:
            original_command_parts.extend(["-ws", original_workspace])
        
        original_browse_command = " ".join(original_command_parts)
        
        # Store original Discord channel selections for /e context preservation
        original_discord_selections = []
        if 'selected_sources' in locals():
            for source in selected_sources:
                if '#' in source:
                    original_discord_selections.append(source)
        
        # Start chat with selected sources
        print_text(f"\n💬 Starting chat with selected sources...", style="white")
        
        chat(
            sources=all_sources, 
            filters=all_filters,
            workspace=resolved_workspace,
            non_interactive=getattr(args, 'non_interactive', False),
            original_browse_command=original_browse_command,
            browse_selections=original_discord_selections  # Store for /e preservation
        )
        
    except Exception as e:
        logging.error(f"An unexpected error occurred in chat_run_inline_browse: {e}", exc_info=True)
        print_text(f"An unexpected error occurred: {e}", style="red")


def history_run(args):
    """Run the chat history interface."""
    from promaia.chat.history_interface import HistorySelector
    from promaia.chat.interface import chat
    from promaia.config.workspaces import get_workspace_manager
    from promaia.storage.chat_history import ChatHistoryManager
    
    # Handle --clean option
    if getattr(args, 'clean', False):
        try:
            history_manager = ChatHistoryManager()
            removed_count = history_manager.clean_duplicates()
            if removed_count > 0:
                print_text(f"Cleaned up {removed_count} duplicate thread(s).", style="white")
            else:
                print_text("No duplicate threads found.", style="white")
            return
        except Exception as e:
            print_text(f"Error cleaning duplicates: {e}", style="red")
            return
    
    try:
        selector = HistorySelector()
        action, selected_thread = selector.select_thread()
        
        if action == 'quit' or not selected_thread:
            return
        
        if action == 'load':
            # Update the thread's last_accessed timestamp
            from promaia.storage.chat_history import ChatHistoryManager
            history_manager = ChatHistoryManager()
            history_manager.update_thread_access(selected_thread.id)
            
            # Reconstruct the context from the saved thread
            context = selected_thread.context
            
            # Check if this is a SQL query thread
            sql_prompt = context.get('sql_query_prompt')

            print_text(f"\nLoading conversation: {selected_thread.name}", style="white")

            if sql_prompt:
                # This is a SQL query thread - restore using SQL query
                print_text(f"Context: maia chat -sql {sql_prompt}", style="dim")

                # Use cached SQL query content if available, otherwise regenerate
                try:
                    # Check if we have cached content from the saved thread
                    sql_query_content= context.get('sql_query_content')
                    
                    if sql_query_content:
                        print_text("🔄 Using cached natural language results from history", style="dim")
                    else:
                        # Fall back to regenerating if no cached content available
                        from promaia.storage.unified_query import get_query_interface
                        
                        workspace_manager = get_workspace_manager()
                        workspace = context.get('workspace')
                        resolved_workspace = context.get('resolved_workspace')
                        actual_workspace = resolved_workspace or workspace or workspace_manager.get_default_workspace()
                        
                        if actual_workspace:
                            print_text("🤖 Regenerating context from natural language query...", style="white")
                            query_interface = get_query_interface()
                            sql_query_content= query_interface.natural_language_query(sql_prompt, actual_workspace, None)
                        else:
                            print_text("❌ No workspace available to regenerate natural language context", style="red")
                            return
                    
                    if sql_query_content:
                        # Start chat with natural language content (cached or regenerated)
                        workspace = context.get('workspace')
                        resolved_workspace = context.get('resolved_workspace')
                        chat(
                            sources=None,
                            filters=None,
                            workspace=workspace,
                            resolved_workspace=resolved_workspace,
                            non_interactive=False,
                            initial_messages=selected_thread.messages,
                            current_thread_id=selected_thread.id,
                            sql_query_content=sql_query_content,
                            sql_query_prompt=sql_prompt
                        )
                    else:
                        print_text("❌ No natural language content available", style="red")
                        return
                        
                except Exception as e:
                    print_text(f"❌ Error regenerating natural language context: {e}", style="red")
                    print_text("Falling back to empty context...", style="yellow")
                    # Fall back to basic chat without context
                    chat(
                        sources=None,
                        filters=None,
                        workspace=context.get('workspace'),
                        resolved_workspace=context.get('resolved_workspace'),
                        non_interactive=False,
                        initial_messages=selected_thread.messages,
                        current_thread_id=selected_thread.id
                    )
            else:
                # Traditional sources/filters thread
                sources = context.get('sources')
                filters = context.get('filters')
                workspace = context.get('workspace')
                resolved_workspace = context.get('resolved_workspace')
                original_query_format = context.get('original_query_format')
                browse_selections = context.get('browse_selections')
                sql_query_prompt= context.get('sql_query_prompt')
                
                # Check if this was originally a browse command
                if original_query_format and '-b ' in original_query_format:
                    print_text(f"Context: {original_query_format}", style="white")
                    
                    # Restore browse command properly by passing the original format
                    chat(
                        sources=None,  # Don't use decomposed sources for browse commands
                        filters=None,  # Don't use decomposed filters for browse commands
                        workspace=workspace,
                        resolved_workspace=resolved_workspace,
                        non_interactive=False,
                        initial_messages=selected_thread.messages,
                        current_thread_id=selected_thread.id,
                        original_browse_command=original_query_format,
                        browse_selections=browse_selections
                    )
                    return  # Early return for browse commands
                
                # Regular command or fallback
                if context.get('query_command'):
                    print_text(f"Context: {context['query_command']}", style="white")
                
                # Show warning if context might be missing
                if sources:
                    workspace_manager = get_workspace_manager()
                    actual_workspace = resolved_workspace or workspace_manager.get_default_workspace()
                    if actual_workspace:
                        from promaia.config.databases import get_database_manager
                        db_manager = get_database_manager()
                        missing_sources = []
                        for source in sources:
                            source_name = source.split(':')[0]  # Handle source:days format
                            if not db_manager.get_database(source_name):
                                missing_sources.append(source_name)
                        
                        if missing_sources:
                            print_text(f"⚠️  Warning: Some sources from this conversation are no longer available: {', '.join(missing_sources)}", style="yellow")
                            print_text("Continuing with available context...\n", style="white")
                
                # Start chat with the saved context and messages
                chat(
                    sources=sources,
                    filters=filters,
                    workspace=workspace,
                    resolved_workspace=resolved_workspace,
                    non_interactive=False,
                    initial_messages=selected_thread.messages,
                    current_thread_id=selected_thread.id,
                    sql_query_prompt=sql_query_prompt
                )
        
    except ImportError as e:
        print_text(f"Error importing history interface: {e}", style="red")
        print_text("Please check your dependencies.", style="red")
    except Exception as e:
        logging.error(f"An unexpected error occurred in history_run: {e}", exc_info=True)
        print_text(f"An unexpected error occurred: {e}", style="red")

async def write_run_async(args):
    """Run the write blog post command."""
    try:
        from promaia.write.interface import write_blog_post
    except ImportError as e:
        print_text(f"Error importing write interface: {e}", style="red")
        print_text("Please check your dependencies or run 'pip install -r requirements.txt'", style="yellow")
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
        print_text(f"Error importing chat interface: {e}", style="red")
        print_text("Please check your dependencies or run 'pip install -r requirements.txt'", style="yellow")
        return
    
    current_model = get_api_preference()
    logger.info(f"Current model: {current_model}")
    logger.info("\nAvailable models:")
    options = {"1": "anthropic", "2": "openai", "3": "gemini", "4": "llama"}
    api_keys = {
        "anthropic": "ANTHROPIC_API_KEY",
        "openai": "OPENAI_API_KEY",
        "gemini": "GOOGLE_API_KEY",
        "llama": "LLAMA_BASE_URL"
    }
    
    for key, name in options.items():
        if name == "llama":
            # Check if local Llama server is available
            llama_url = os.getenv("LLAMA_BASE_URL", "http://localhost:11434")
            try:
                import requests
                test_url = f"{llama_url.rstrip('/')}/api/tags" if "ollama" in llama_url or ":11434" in llama_url else f"{llama_url.rstrip('/')}/v1/models"
                response = requests.get(test_url, timeout=2)
                key_status = "Server Available" if response.status_code == 200 else "Server Not Responding"
            except Exception:
                key_status = "Server Not Available"
        else:
            key_status = "API Key Found" if os.getenv(api_keys[name]) else "API Key Missing"
        logger.info(f"{key}. {name.capitalize()} ({key_status})")
    
    # Create a more descriptive prompt showing actual model names
    model_names = [f"{key}={name.capitalize()}" for key, name in options.items()]
    prompt = f"\nSelect a model ({', '.join(model_names)}, or Enter to keep current): "
    choice_key = input(prompt).strip()
    
    if not choice_key:
        logger.info("Model selection unchanged.")
        return
    
    if choice_key in options:
        chosen_model = options[choice_key]
        if chosen_model == "llama":
            # Check if local Llama server is available
            llama_url = os.getenv("LLAMA_BASE_URL", "http://localhost:11434")
            try:
                import requests
                test_url = f"{llama_url.rstrip('/')}/api/tags" if "ollama" in llama_url or ":11434" in llama_url else f"{llama_url.rstrip('/')}/v1/models"
                response = requests.get(test_url, timeout=2)
                if response.status_code != 200:
                    logger.error(f"ERROR: Cannot switch to Local Llama: Server not responding at {llama_url}")
                    return
            except Exception as e:
                logger.error(f"ERROR: Cannot switch to Local Llama: Server not available at {llama_url} ({e})")
                return
        elif not os.getenv(api_keys[chosen_model]):
            logger.error(f"ERROR: Cannot switch to {chosen_model.capitalize()}: {api_keys[chosen_model]} environment variable not set." )
            return
        save_api_preference(chosen_model)
        logger.info(f"SUCCESS: Switched default model to: {chosen_model.capitalize()}")
    else:
        logger.error("ERROR: Invalid choice. Please select from the available options.")

def chat_run_workspace_browse(args, workspace_name):
    """Run the chat interface with unified browser for workspace."""
    from promaia.chat.interface import chat
    from promaia.config.workspaces import get_workspace_manager
    
    try:
        workspace_manager = get_workspace_manager()
        
        # Validate workspace
        if not workspace_manager.validate_workspace(workspace_name):
            print_text(f"✗ Workspace '{workspace_name}' is not properly configured.", style="red")
            return
        
        # Get other args
        sources = getattr(args, 'sources', None) or []
        filters = getattr(args, 'filters', None) or []
        mcp_servers = getattr(args, 'mcp_servers', None)
        
        # Add workspace to args so chat function can use it
        args.workspace = workspace_name
        
        # Build the original browse command for display
        original_command_parts = ["maia", "chat"]
        
        # Add browse argument
        original_command_parts.extend(["-b", workspace_name])
        
        # Add any regular sources
        if sources:
            for source in sources:
                original_command_parts.extend(["-s", source])
        
        # Add filters
        if filters:
            for filter_expr in filters:
                original_command_parts.extend(["-f", f'"{filter_expr}"'])
        
        # Add MCP servers
        if mcp_servers:
            for server in mcp_servers:
                original_command_parts.extend(["-mcp", server])
        
        original_browse_command = " ".join(original_command_parts)
        
        # Launch unified browser to get user selections
        from promaia.cli.workspace_browser import launch_unified_browser
        print_text(f"🔍 Launching unified browser for workspace '{workspace_name}'...", style="cyan")
        
        selected_sources = launch_unified_browser(workspace_name)
        
        if not selected_sources:
            print_text(f"No sources selected from workspace '{workspace_name}'. Chat will lack context.", style="bold yellow")
            # Continue anyway, but with empty sources
            final_sources = sources
            final_filters = filters
            browse_selections = []
        else:
            print_text(f"📦 Selected {len(selected_sources)} sources from workspace '{workspace_name}'", style="cyan")
            
            # Process browser selections to handle Discord channels correctly
            from promaia.chat.interface import process_browser_selections
            processed_sources, processed_filters = process_browser_selections(selected_sources)
            
            # Combine with any regular sources and filters
            final_sources = sources + processed_sources
            final_filters = filters + processed_filters
            browse_selections = selected_sources.copy()  # Store raw selections for /e preservation
        
        # Call the chat function with workspace and original command format
        chat(
            sources=final_sources,
            filters=final_filters,
            workspace=workspace_name,
            resolved_workspace=workspace_name,
            non_interactive=getattr(args, 'non_interactive', False),
            mcp_servers=mcp_servers,
            original_browse_command=original_browse_command,
            browse_selections=browse_selections  # Store for /e preservation
        )
        
    except Exception as e:
        logging.error(f"An unexpected error occurred in chat_run_workspace_browse: {e}", exc_info=True)
        print_text(f"An unexpected error occurred: {e}", style="red")

def chat_run_multi_workspace_browse(args, workspace_names):
    """Run the chat interface with unified browser for multiple workspaces."""
    from promaia.chat.interface import chat
    from promaia.config.workspaces import get_workspace_manager
    
    try:
        workspace_manager = get_workspace_manager()
        
        # Validate all workspaces
        invalid_workspaces = [ws for ws in workspace_names if not workspace_manager.validate_workspace(ws)]
        if invalid_workspaces:
            print_text(f"✗ Invalid workspaces: {', '.join(invalid_workspaces)}", style="red")
            return
        
        # Get other args
        sources = getattr(args, 'sources', None) or []
        filters = getattr(args, 'filters', None) or []
        mcp_servers = getattr(args, 'mcp_servers', None)
        
        # Build the original browse command for display and recents
        original_command_parts = ["maia", "chat"]
        
        # Add browse arguments
        original_command_parts.append("-b")
        original_command_parts.extend(workspace_names)
        
        # Add any regular sources
        if sources:
            for source in sources:
                original_command_parts.extend(["-s", source])
        
        # Add filters
        if filters:
            for filter_expr in filters:
                original_command_parts.extend(["-f", f'"{filter_expr}"'])
        
        # Add MCP servers
        if mcp_servers:
            for server in mcp_servers:
                original_command_parts.extend(["-mcp", server])
        
        original_browse_command = " ".join(original_command_parts)
        
        # Launch unified browser for multiple workspaces
        from promaia.cli.workspace_browser import launch_unified_browser
        print_text(f"🔍 Launching unified browser for workspaces: {', '.join(workspace_names)}...", style="cyan")
        
        # For multi-workspace, we need to pass the workspace names to the browser
        # We'll use the first workspace as primary but show databases from all
        primary_workspace = workspace_names[0]
        
        # For multi-workspace browse, pass workspace names directly in the database_filter
        # The browser will detect workspace names and expand to show all databases
        selected_sources = launch_unified_browser(None, database_filter=workspace_names)
        
        if not selected_sources:
            print_text("ℹ️  No sources selected. Continuing with regular sources only.", style="dim")
            # Continue with just the regular sources
            all_sources = sources
            all_filters = filters or []
        else:
            print_text(f"✅ Selected {len(selected_sources)} sources from unified browser", style="green")
            all_sources = sources + selected_sources
            all_filters = filters or []
        
        # Store browse selections for /e preservation
        browse_selections = selected_sources.copy() if selected_sources else []
        
        # Start chat with the combined sources
        chat(
            sources=all_sources,
            filters=all_filters,
            workspace=primary_workspace,  # Use primary workspace for default
            mcp_servers=mcp_servers,
            original_browse_command=original_browse_command,
            browse_selections=browse_selections  # Store for /e preservation
        )
        
    except Exception as e:
        logging.error(f"An unexpected error occurred in chat_run_multi_workspace_browse: {e}", exc_info=True)
        print_text(f"An unexpected error occurred: {e}", style="red")

