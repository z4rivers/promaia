"""
Interactive interface for selecting and managing recent chat queries.
Provides keyboard navigation and editing capabilities.
"""
import shlex
from typing import List, Optional, Tuple
from prompt_toolkit import prompt
from prompt_toolkit.application import Application
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout.containers import HSplit, Window
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.layout.layout import Layout
from prompt_toolkit.formatted_text import FormattedText
from prompt_toolkit.styles import Style

from promaia.storage.recents import RecentsManager, RecentQuery

class RecentsSelector:
    """Interactive selector for recent chat queries."""
    
    def __init__(self):
        self.recents_manager = RecentsManager()
        self.selected_index = 0
        self.queries = []
        self.result = None
        
    def _create_formatted_text(self) -> FormattedText:
        """Create formatted text for display."""
        lines = []
        
        # Header
        lines.append(("class:header", "Recent Chat Queries"))
        lines.append(("", "\n"))
        lines.append(("class:instructions", "Use ↑/↓ to navigate, Enter to execute, E to edit, Q to quit"))
        lines.append(("", "\n\n"))
        
        if not self.queries:
            lines.append(("class:error", "No recent queries found."))
            lines.append(("", "\n"))
            lines.append(("class:instructions", "Press Q to quit."))
            return FormattedText(lines)
        
        # Query list
        for i, query in enumerate(self.queries):
            if i == self.selected_index:
                lines.append(("class:selected", f"  {i + 1}. {str(query)}"))
            else:
                lines.append(("class:unselected", f"  {i + 1}. {str(query)}"))
            lines.append(("", "\n"))
        
        lines.append(("", "\n"))
        lines.append(("class:instructions", "Commands: [Enter] Execute | [E] Edit | [↑/↓] Navigate | [Q] Quit"))
        
        return FormattedText(lines)
    
    def _create_key_bindings(self) -> KeyBindings:
        """Create key bindings for navigation."""
        kb = KeyBindings()
        
        @kb.add('up')
        def move_up(event):
            if self.queries and self.selected_index > 0:
                self.selected_index -= 1
                event.app.invalidate()
        
        @kb.add('down')
        def move_down(event):
            if self.queries and self.selected_index < len(self.queries) - 1:
                self.selected_index += 1
                event.app.invalidate()
        
        @kb.add('enter')
        def execute_query(event):
            if self.queries:
                self.result = ('execute', self.queries[self.selected_index])
                event.app.exit()
        
        @kb.add('e')
        def edit_query(event):
            if self.queries:
                self.result = ('edit', self.queries[self.selected_index])
                event.app.exit()
        
        @kb.add('q')
        def quit_app(event):
            self.result = ('quit', None)
            event.app.exit()
        
        @kb.add('c-c')  # Ctrl+C
        def force_quit(event):
            self.result = ('quit', None)
            event.app.exit()
        
        return kb
    
    def select_query(self) -> Tuple[str, Optional[RecentQuery]]:
        """
        Show the selection interface and return the user's choice.
        
        Returns:
            Tuple of (action, query) where action is 'execute', 'edit', or 'quit'
        """
        import sys
        
        self.queries = self.recents_manager.get_recents()
        
        if not self.queries:
            print("No recent queries found. Use 'maia chat' with some options first.")
            return ('quit', None)
        
        # Check if we're in a proper terminal
        if not sys.stdin.isatty() or not sys.stdout.isatty():
            print("Interactive selection not available (not running in a terminal).")
            print("Available recent queries:")
            for i, query in enumerate(self.queries, 1):
                print(f"  {i}. {query}")
            print("\nUse 'maia chat' with specific parameters to execute a query.")
            return ('quit', None)
        
        try:
            # Create the application
            root_container = HSplit([
                Window(
                    content=FormattedTextControl(
                        lambda: self._create_formatted_text()
                    ),
                    height=len(self.queries) + 8,  # Adjust height based on content
                ),
            ])
            
            layout = Layout(root_container)
            
            # Define styles
            style = Style.from_dict({
                'header': 'bold cyan',
                'instructions': 'italic',
                'selected': 'reverse bold',
                'unselected': '',
                'error': 'red',
            })
            
            # Create and run the application
            app = Application(
                layout=layout,
                key_bindings=self._create_key_bindings(),
                style=style,
                full_screen=False,
            )
            
            app.run()
            
            return self.result or ('quit', None)
            
        except (EOFError, KeyboardInterrupt):
            print("\nRecents selection cancelled.")
            return ('quit', None)
        except Exception as e:
            print(f"Error with interactive interface: {e}")
            print("Available recent queries:")
            for i, query in enumerate(self.queries, 1):
                print(f"  {i}. {query}")
            print("\nUse 'maia chat' with specific parameters to execute a query.")
            return ('quit', None)

def edit_query_string(query: RecentQuery) -> Optional[RecentQuery]:
    """
    Allow user to edit a query string and return the modified query.
    
    Args:
        query: The original query to edit
        
    Returns:
        Modified query or None if cancelled
    """
    # Create the command string for editing
    parts = []
    if query.sources:
        for source in query.sources:
            parts.extend(['-s', source])
    if query.filters:
        for filter_expr in query.filters:
            parts.extend(['-f', filter_expr])
    if query.workspace:
        parts.extend(['-ws', query.workspace])
    
    current_command = ' '.join(parts) if parts else ''
    
    try:
        print(f"\nCurrent command: maia chat {current_command}")
        print("Edit the arguments (without 'maia chat'):")
        
        edited_command = prompt(
            "Arguments: ",
            default=current_command,
            mouse_support=True
        ).strip()
        
        if not edited_command and not current_command:
            # Empty command is valid
            return RecentQuery(command="chat")
        
        if edited_command == current_command:
            # No changes made
            return query
        
        # Parse the edited command
        if edited_command:
            try:
                args = shlex.split(edited_command)
            except ValueError as e:
                print(f"Error parsing command: {e}")
                return None
        else:
            args = []
        
        # Parse arguments manually (simple parsing)
        sources = []
        filters = []
        workspace = None
        
        i = 0
        while i < len(args):
            if args[i] in ['-s', '--source'] and i + 1 < len(args):
                sources.append(args[i + 1])
                i += 2
            elif args[i] in ['-f', '--filter'] and i + 1 < len(args):
                filters.append(args[i + 1])
                i += 2
            elif args[i] in ['-ws', '--workspace'] and i + 1 < len(args):
                workspace = args[i + 1]
                i += 2
            else:
                print(f"Unknown argument: {args[i]}")
                return None
        
        return RecentQuery(
            command="chat",
            sources=sources if sources else None,
            filters=filters if filters else None,
            workspace=workspace
        )
        
    except (KeyboardInterrupt, EOFError):
        print("\nEdit cancelled.")
        return None 