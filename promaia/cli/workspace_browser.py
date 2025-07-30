"""Unified browser for interactive source selection (databases + Discord channels)."""

import asyncio
import os
import logging
from typing import List, Optional, Dict, Any, Tuple
from prompt_toolkit import prompt
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.keys import Keys
from prompt_toolkit.application import Application
from prompt_toolkit.layout.containers import HSplit, Window, VSplit
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.layout.layout import Layout
from prompt_toolkit.formatted_text import FormattedText
from prompt_toolkit.widgets import TextArea, Frame
from rich.console import Console

logger = logging.getLogger(__name__)

def safe_parse_days(source_spec: str, fallback_days):
    """Safely parse days from source spec, handling special values like 'all'."""
    if ':' not in source_spec:
        return fallback_days
    
    days_part = source_spec.split(':')[-1]
    
    # Handle special values
    if days_part.lower() in ['all', 'unlimited', 'max']:
        return days_part  # Keep as string for special values
    
    # Try to parse as integer
    try:
        return int(days_part)
    except ValueError:
        # If parsing fails, return fallback
        return fallback_days

def launch_unified_browser(workspace: str, default_days: Optional[int] = None, database_filter: Optional[List[str]] = None, current_sources: Optional[List[str]] = None) -> List[str]:
    """Launch unified browser for both database sources and Discord channels."""
    return asyncio.run(interactive_unified_browser(workspace, default_days, database_filter, current_sources))

# Keep backward compatibility
def launch_workspace_browser(workspace: str, default_days: Optional[int] = None) -> List[str]:
    """Launch interactive workspace source browser (backward compatibility)."""
    return launch_unified_browser(workspace, default_days)

async def interactive_unified_browser(workspace: str, default_days: Optional[int] = None, database_filter: Optional[List[str]] = None, current_sources: Optional[List[str]] = None) -> List[str]:
    """Interactive unified browser with live text fields for databases and Discord channels."""
    from promaia.config.databases import get_database_manager
    
    console = Console()
    
    try:
        db_manager = get_database_manager()
        workspace_databases = db_manager.get_workspace_databases(workspace)
        
        if not workspace_databases:
            console.print(f"❌ No databases found in workspace '{workspace}'", style="red")
            return []
        
        # Filter databases if specified (for Discord-only browsing)
        if database_filter:
            workspace_databases = [db for db in workspace_databases if db.get_qualified_name() in database_filter]
        
        # Build entries for both regular databases and Discord channels
        all_entries = []
        
        # Create lookup for current sources to preserve user edits
        current_source_lookup = {}
        current_enabled_set = set()
        if current_sources:
            for source in current_sources:
                if '#' in source:
                    # Discord channel: trass.discord#channel-name:7
                    db_channel, days_part = source.rsplit(':', 1)
                    current_source_lookup[db_channel] = source
                    current_enabled_set.add(db_channel)
                else:
                    # Regular database: trass.journal:7
                    db_name = source.split(':')[0]
                    current_source_lookup[db_name] = source
                    current_enabled_set.add(db_name)
        
        for db in workspace_databases:
            # Skip disabled databases unless they're specifically requested in the filter
            if not db.sync_enabled and not (database_filter and db.get_qualified_name() in database_filter):
                continue
                
            qualified_name = db.get_qualified_name()
            default_days_for_db = default_days if default_days is not None else db.default_days
            
            if db.source_type == "discord":
                # For Discord databases, load available channels
                channels = get_synced_channels_from_filesystem(db)
                
                if channels:
                    for channel in channels:
                        channel_name = channel['name']
                        # Check if this Discord channel is in current sources
                        db_channel_key = f"{qualified_name}#{channel_name}"
                        
                        if db_channel_key in current_source_lookup:
                            # Use current source spec (preserves user edits)
                            source_spec = current_source_lookup[db_channel_key]
                            # Extract days from current spec
                            current_days = safe_parse_days(source_spec, default_days_for_db)
                        else:
                            # Use default
                            source_spec = f"{qualified_name}#{channel_name}:{default_days_for_db}"
                            current_days = default_days_for_db
                            
                        all_entries.append({
                            'spec': source_spec,
                            'type': 'discord',
                            'database': qualified_name,
                            'channel': channel_name,
                            'days': current_days,
                            'message_count': channel.get('message_count', 0),
                            'last_activity': channel.get('last_activity', 'unknown')
                        })
                else:
                    # Show Discord database even if no channels (user can manually add)
                    if qualified_name in current_source_lookup:
                        source_spec = current_source_lookup[qualified_name]
                        current_days = safe_parse_days(source_spec, 0)
                    else:
                        source_spec = f"{qualified_name}:0"
                        current_days = 0
                        
                    all_entries.append({
                        'spec': source_spec,
                        'type': 'discord_db',
                        'database': qualified_name,
                        'days': current_days,
                        'message_count': 0,
                        'note': '(no synced channels - edit to add manually)'
                    })
            else:
                # Regular database
                if qualified_name in current_source_lookup:
                    # Use current source spec (preserves user edits)
                    source_spec = current_source_lookup[qualified_name]
                    # Extract days from current spec
                    current_days = safe_parse_days(source_spec, default_days_for_db)
                else:
                    # Use default
                    source_spec = f"{qualified_name}:{default_days_for_db}"
                    current_days = default_days_for_db
                    
                all_entries.append({
                    'spec': source_spec,
                    'type': 'database',
                    'database': qualified_name,
                    'days': current_days
                })
        
        if not all_entries:
            # Provide more specific error messaging
            if database_filter:
                disabled_dbs = [db for db in workspace_databases if not db.sync_enabled and db.get_qualified_name() in database_filter]
                if disabled_dbs:
                    db_names = [db.get_qualified_name() for db in disabled_dbs]
                    console.print(f"❌ Requested databases are disabled: {', '.join(db_names)}", style="red")
                    console.print(f"💡 Enable them in config or sync some channels first", style="yellow")
                else:
                    console.print(f"❌ No databases found matching filter: {', '.join(database_filter)}", style="red")
            else:
                console.print(f"❌ No enabled databases or channels in workspace '{workspace}'", style="red")
            return []
        
        # Sort entries: regular databases first, then Discord channels, alphabetically within each group
        def sort_key(entry):
            # Primary sort: type priority (database=0, discord_db=1, discord=2)
            type_priority = {'database': 0, 'discord_db': 1, 'discord': 2}
            primary = type_priority.get(entry['type'], 3)
            
            # Secondary sort: alphabetical by database name
            database_name = entry['database']
            
            # Tertiary sort: for Discord channels, sort by channel name
            if entry['type'] == 'discord':
                # Extract channel name from spec like "trass.tg#customer-support:7"
                if '#' in entry['spec']:
                    channel_part = entry['spec'].split('#')[1].split(':')[0]
                    return (primary, database_name, channel_part)
            
            return (primary, database_name, "")
        
        all_entries.sort(key=sort_key)
        
        # Define helper functions first (before they're used)
        def get_entry_prefix(index: int, enabled_states, entry_info) -> str:
            """Get prefix for an entry (checkbox only, no emojis or counts)."""
            checkbox = "☑" if enabled_states[index] else "☐"
            return f"{checkbox}      "  # Just checkbox + spacing
        
        # Create TextArea widgets for each entry
        text_areas = []
        enabled_states = []
        entry_info = []
        source_windows = []
        
        current_group = None
        
        for entry in all_entries:
            # Determine group for this entry
            entry_group = 'databases' if entry['type'] == 'database' else 'discord'
            
            # Add group header if this is a new group
            if current_group != entry_group:
                # Add spacing before Discord group (but not before first group)
                if current_group is not None:
                    spacer_window = Window(height=1)
                    source_windows.append(spacer_window)
                
                if entry_group == 'databases':
                    header_text = "📄 Regular Databases:"
                else:
                    header_text = "💬 Discord Channels:"
                
                # Create header window (non-focusable)
                header_window = Window(
                    FormattedTextControl(text=header_text),
                    height=1,
                    style="class:header",
                    dont_extend_height=True,
                )
                source_windows.append(header_window)
                current_group = entry_group
            
            # Create a compact TextArea for this source
            text_area = TextArea(
                text=entry['spec'],
                height=1,
                multiline=False,
                wrap_lines=False,
                scrollbar=False,
                focusable=True,
            )
            # Position cursor at end of text for easier editing
            text_area.buffer.cursor_position = len(entry['spec'])
            text_areas.append(text_area)
            
            # Determine if this entry should be enabled based on current sources
            if current_sources:
                # Check if this entry is in the current enabled set
                if entry['type'] == 'discord':
                    key = f"{entry['database']}#{entry['channel']}"
                else:
                    key = entry['database']
                is_enabled = key in current_enabled_set
            else:
                # If no current sources, enable all by default
                is_enabled = True
                
            enabled_states.append(is_enabled)
            entry_info.append(entry)
            
            # Create window for this source entry
            prefix_text = get_entry_prefix(len(enabled_states) - 1, enabled_states, entry_info)
            source_window = VSplit([
                Window(
                    FormattedTextControl(text=prefix_text),
                    width=8,  # Reduced from 12 since no emojis/counts
                    dont_extend_width=True,
                ),
                text_area,
            ])
            source_windows.append(source_window)
        
        # Create mapping from text_area index to source_window index (to handle headers and spacers)
        text_area_to_source_window = []
        for i, window in enumerate(source_windows):
            # Only track windows that contain text areas (not headers or spacers)
            if hasattr(window, 'children') and len(window.children) > 1:
                text_area_to_source_window.append(i)
        
        # State management
        current_focus = 0
        should_exit = False
        confirmed = False
        
        def get_status_display():
            """Generate status line."""
            enabled_count = sum(enabled_states)
            total_count = len(enabled_states)
            discord_count = sum(1 for entry in entry_info if entry['type'] in ['discord', 'discord_db'])
            db_count = total_count - discord_count
            return f"🔍 {workspace} | Sources: {db_count} databases, {discord_count} channels | Selected: {enabled_count}/{total_count} | ↑↓ Navigate SPACE Toggle ENTER Confirm ESC Cancel"
        
        # Status line
        status_window = Window(
            FormattedTextControl(text=get_status_display),
            height=1,
        )
        
        # Main container
        container = HSplit([
            status_window,
            Window(height=1),  # Spacer
            *source_windows
        ])
        
        layout = Layout(container)
        
        # Set initial focus
        layout.focus(text_areas[current_focus])
        
        # Key bindings
        bindings = KeyBindings()
        
        @bindings.add(Keys.Up)
        def move_up(event):
            nonlocal current_focus
            if current_focus > 0:
                current_focus -= 1
                layout.focus(text_areas[current_focus])
        
        @bindings.add(Keys.Down)
        def move_down(event):
            nonlocal current_focus
            if current_focus < len(text_areas) - 1:
                current_focus += 1
                layout.focus(text_areas[current_focus])
        
        @bindings.add(' ')  # Spacebar
        def toggle_source(event):
            nonlocal current_focus
            enabled_states[current_focus] = not enabled_states[current_focus]
            
            # Update prefix display using the correct source window index
            prefix_text = get_entry_prefix(current_focus, enabled_states, entry_info)
            source_window_index = text_area_to_source_window[current_focus]
            source_windows[source_window_index].children[0].content.text = prefix_text
            
            # Update status
            status_window.content.text = get_status_display
        
        @bindings.add(Keys.Enter)
        def confirm_selection(event):
            nonlocal should_exit, confirmed
            should_exit = True
            confirmed = True
            event.app.exit()
        
        @bindings.add(Keys.Escape)
        def cancel(event):
            nonlocal should_exit
            should_exit = True
            event.app.exit()
        
        # Create application
        app = Application(
            layout=layout,
            key_bindings=bindings,
            full_screen=False,
            mouse_support=False,
        )
        
        # Run the application
        await app.run_async()
        
        if confirmed:
            # Return enabled sources with their current text
            result_sources = []
            for i, (text_area, enabled) in enumerate(zip(text_areas, enabled_states)):
                if enabled:
                    result_sources.append(text_area.text.strip())
            return result_sources
        else:
            return []
            
    except Exception as e:
        console.print(f"❌ Error in unified browser: {e}", style="red")
        import traceback
        traceback.print_exc()
        return []


def get_synced_channels_from_filesystem(db_config) -> List[Dict]:
    """Get list of channels that have already been synced by checking filesystem."""
    channels = []
    
    try:
        from pathlib import Path
        
        # Check the markdown directory for this Discord database
        md_dir = db_config.markdown_directory
        
        if os.path.exists(md_dir):
            # Each subdirectory represents a synced channel
            for channel_dir in Path(md_dir).iterdir():
                if channel_dir.is_dir() and not channel_dir.name.startswith('.'):
                    # Count messages in this channel
                    message_files = list(channel_dir.glob("*.md"))
                    last_sync = "unknown"
                    
                    if message_files:
                        # Get the most recent message file for last activity
                        newest_file = max(message_files, key=lambda f: f.stat().st_mtime)
                        last_sync = newest_file.stat().st_mtime
                        import datetime
                        last_sync = datetime.datetime.fromtimestamp(last_sync).strftime("%m/%d %H:%M")
                    
                    channels.append({
                        "id": "unknown",  # We don't need the ID for chat browsing
                        "name": channel_dir.name,  # Use directory name as-is
                        "message_count": len(message_files),
                        "last_activity": last_sync
                    })
    
    except Exception as e:
        logger.error(f"Error reading synced channels from filesystem: {e}")
    
    return channels 