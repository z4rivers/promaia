"""
Email Draft Review UI - Interactive review interface for email drafts.
"""
import json
import logging
import os
import subprocess
import sys
from typing import List, Dict, Any, Optional
from datetime import datetime

from prompt_toolkit import prompt
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.keys import Keys

from promaia.mail.draft_manager import DraftManager
from promaia.mail.gmail_sender import GmailSender
from promaia.mail.thread_formatter import format_thread_for_display
from promaia.utils.display import print_text, print_separator
from promaia.utils.timezone_utils import to_local, get_local_timezone_name, now_utc

logger = logging.getLogger(__name__)


class EmailReviewUI:
    """Interactive review interface for email drafts."""
    
    def __init__(self):
        self.draft_manager = DraftManager()
        self.session_stats = {
            'sent': 0,
            'pending': 0
        }
    
    def _clear_screen_and_home(self):
        """Clear terminal screen and position cursor at top."""
        # Use ANSI escape sequences for better control
        # ESC[r resets scroll region
        # ESC[H moves cursor to home (1,1) 
        # ESC[2J clears entire screen
        # ESC[3J clears scrollback buffer
        print('\033[r\033[H\033[2J\033[3J', end='', flush=True)
    
    def _enter_alternate_screen(self):
        """Enter alternate screen buffer (like vim/less)."""
        # ESC[?1049h switches to alternate screen
        # ESC[?7l disables auto-wrap
        # ESC[H moves cursor to top immediately
        # ESC[2J clears the alternate screen
        print('\033[?1049h\033[?7l\033[H\033[2J', end='', flush=True)
    
    def _exit_alternate_screen(self):
        """Exit alternate screen buffer."""
        # ESC[?1049l switches back to main screen
        print('\033[?1049l', end='', flush=True)
    
    def _jump_to_top(self):
        """Force terminal viewport to top using tput."""
        try:
            # Use tput home command - more reliable than cup
            os.system('tput home >/dev/null 2>&1')
        except Exception:
            pass
        # Also use ANSI home sequence
        print('\033[H', end='', flush=True)
    
    def _clean_email_body(self, body: str) -> str:
        """
        Remove redundant email headers from body content.
        
        Email bodies often start with headers like:
        From: ...
        Sent: ...
        To: ...
        Subject: ...
        
        We strip these out since we display them separately.
        """
        if not body:
            return body
        
        lines = body.split('\n')
        cleaned_lines = []
        skip_headers = True
        
        for line in lines:
            # Check if line looks like an email header
            if skip_headers:
                # Common email header patterns
                if line.strip().startswith(('From:', 'Sent:', 'To:', 'Subject:', 'Date:', 'Cc:', 'Bcc:')):
                    continue
                # Empty line often follows headers
                elif not line.strip():
                    continue
                else:
                    # Found actual content, stop skipping
                    skip_headers = False
                    cleaned_lines.append(line)
            else:
                cleaned_lines.append(line)
        
        return '\n'.join(cleaned_lines).strip()
    
    async def _get_keystroke(self) -> str:
        """Capture a single keystroke without requiring Enter."""
        from prompt_toolkit.application import Application
        from prompt_toolkit.layout import Layout
        from prompt_toolkit.layout.containers import Window
        from prompt_toolkit.layout.controls import FormattedTextControl
        
        kb = KeyBindings()
        result = {'value': None}
        
        # Navigation keys
        @kb.add(Keys.Up)
        def _(event):
            result['value'] = 'up'
            event.app.exit()
        
        @kb.add(Keys.Down)
        def _(event):
            result['value'] = 'down'
            event.app.exit()
        
        @kb.add(Keys.Escape)
        def _(event):
            result['value'] = 'escape'
            event.app.exit()
        
        @kb.add(Keys.ControlC)
        def _(event):
            result['value'] = 'q'
            event.app.exit()
        
        @kb.add('q')
        def _(event):
            result['value'] = 'q'
            event.app.exit()
        
        # Enter to open chat
        @kb.add(Keys.Enter)
        def _(event):
            result['value'] = 'enter'
            event.app.exit()
            
        # Archive key
        @kb.add('a')
        def _(event):
            result['value'] = 'a'
            event.app.exit()
        
        # Create minimal application to capture keystroke
        app = Application(
            layout=Layout(Window(FormattedTextControl(text=''))),
            key_bindings=kb,
            full_screen=False,
            mouse_support=False
        )
        
        try:
            await app.run_async()
            return result['value'] or ''
        except KeyboardInterrupt:
            return 'q'
    
    def _calculate_stats(self, drafts: List[Dict[str, Any]]) -> Dict[str, int]:
        """Calculate stats from draft list."""
        stats = {
            'total': len(drafts),
            'sent': sum(1 for d in drafts if d.get('status') == 'sent'),
            'pending': sum(1 for d in drafts if d.get('status') == 'pending'),
            'skipped': sum(1 for d in drafts if d.get('status') == 'skipped'),
            'archived': sum(1 for d in drafts if d.get('status') == 'archived'),
        }
        stats['resolved'] = stats['sent'] + stats['archived']
        if stats['total'] > 0:
            stats['percent'] = int((stats['resolved'] / stats['total']) * 100)
        else:
            stats['percent'] = 0
        return stats
    
    def _render_progress_bar(self, stats: Dict[str, int]) -> str:
        """Render just the progress bar."""
        total_width = 30
        filled = int((stats['percent'] / 100) * total_width)
        bar = '█' * filled + '░' * (total_width - filled)
        return bar
    
    def _render_status_bar(self, stats: Dict[str, int]) -> str:
        """Render progress and status bar."""
        bar = self._render_progress_bar(stats)
        
        return (
            f"Maia Mail - Draft Review Queue\n\n"
            f"Progress: [{bar}] {stats['resolved']}/{stats['total']} resolved ({stats['percent']}%)\n"
            f"Status: ✅ {stats['sent']} sent  •  🗄️ {stats['archived']} archived  •  ⏳ {stats['pending']} pending  •  ⏭️ {stats['skipped']} skipped\n\n"
        )
    
    def _render_review_list(self, drafts: List[Dict[str, Any]], current_selection: int, start_offset: int = 0) -> str:
        """Render list of drafts for review.
        
        Args:
            drafts: List of drafts to render
            current_selection: Index of currently selected draft (relative to drafts list)
            start_offset: Offset to add to draft numbers for display (for pagination)
        """
        output = []
        
        for idx, draft in enumerate(drafts):
            # Status icon
            if draft.get('status') == 'sent':
                icon = '✅'
            elif draft.get('status') == 'archived':
                icon = '🗄️'
            elif draft.get('status') == 'skipped':
                icon = '⏭️'
            else:
                icon = '⏳'
            
            # Selection indicator
            selector = '▶' if idx == current_selection else ' '
            
            # Format date (convert to local timezone)
            try:
                date_obj = datetime.fromisoformat(draft.get('inbound_date', '').replace('Z', '+00:00'))
                local_date = to_local(date_obj)
                tz_name = get_local_timezone_name()
                date_str = local_date.strftime(f'%b %d, %I:%M %p {tz_name}')
            except:
                date_str = 'Unknown'
            
            # Preview
            from_addr = draft.get('inbound_from', 'Unknown')
            if '<' in from_addr and '>' in from_addr:
                from_name = from_addr.split('<')[0].strip()
            else:
                from_name = from_addr
            
            subject = draft.get('inbound_subject', 'No Subject')
            snippet = draft.get('inbound_snippet', '')[:80]
            
            # Actual draft number in full list (1-based)
            draft_number = start_offset + idx + 1
            
            # Handle skipped drafts differently
            if draft.get('status') == 'skipped':
                reasoning = draft.get('classification_reasoning', 'No response needed')
                output.append(f"{selector} [{draft_number}] {icon} {subject}")
                output.append(f"       From: {from_name} | {date_str}")
                output.append(f"       Preview: {snippet}...")
                output.append(f"       Draft: n/a  •  {reasoning}")
                output.append("")
            else:
                # Context count
                try:
                    context_data = json.loads(draft.get('response_context', '{}'))
                    context_count = len(context_data.get('documents', []))
                except:
                    context_count = 0
                
                # Word count
                word_count = len(draft.get('draft_body', '').split())
                
                output.append(f"{selector} [{draft_number}] {icon} {subject}")
                output.append(f"       From: {from_name} | {date_str}")
                output.append(f"       Preview: {snippet}...")
                output.append(f"       Draft: {word_count} words | Context: {context_count} sources")
                output.append("")
        
        return '\n'.join(output)
    
    def _render_draft_detail(self, draft: Dict[str, Any]) -> str:
        """Render full draft details."""
        # Get context
        try:
            context_data = json.loads(draft.get('response_context', '{}'))
            context_sources = context_data.get('documents', [])
            context_count = len(context_sources)
        except:
            context_count = 0
            context_sources = []
        
        # Format date (convert to local timezone)
        try:
            received_dt = datetime.fromisoformat(draft.get('inbound_date', '').replace('Z', '+00:00'))
            local_received = to_local(received_dt)
            tz_name = get_local_timezone_name()
            received_str = local_received.strftime(f'%A, %B %d, %Y at %I:%M %p {tz_name}')
        except:
            received_str = draft.get('inbound_date', 'Unknown')
        
        # Word count
        draft_words = len(draft.get('draft_body', '').split())
        
        # Context summary
        if context_sources:
            context_summary = ', '.join([s.get('database', 'unknown') for s in context_sources[:3]])
            if len(context_sources) > 3:
                context_summary += f" + {len(context_sources) - 3} more"
        else:
            context_summary = "None"
        
        # Clean email body to remove redundant headers
        cleaned_body = self._clean_email_body(draft.get('inbound_body', 'No body available'))
        
        # Format thread with copy-friendly styling and position indicators
        message_count = draft.get('message_count', 1)
        thread_display = format_thread_for_display(
            conversation_body=cleaned_body,
            message_count=message_count,
            from_addr=draft.get('inbound_from', 'Unknown'),
            subject=draft.get('inbound_subject', 'No Subject'),
            received_str=received_str,
            use_colors=True
        )
        
        return f"""
Draft Review - Full View

{thread_display}

─────────────────────────────────────────────────────────────────

YOUR DRAFT RESPONSE ({draft_words} words)

{draft.get('draft_body', 'No draft available')}

─────────────────────────────────────────────────────────────────

CONTEXT USED

Sources:     {context_count} documents from knowledge base
Databases:   {context_summary}
AI Model:    {draft.get('ai_model', 'unknown')}
Generated:   {draft.get('created_time', 'unknown')}

─────────────────────────────────────────────────────────────────

ACTIONS

[Enter] Chat  [a] Archive  [v] Context  [b] Back  [q] Quit

"""
    
    def _render_context_view(self, draft: Dict[str, Any]) -> str:
        """Show full context sources used for generation."""
        try:
            context_data = json.loads(draft.get('response_context', '{}'))
            context_sources = context_data.get('documents', [])
        except:
            return "\n❌ No context sources available\n"
        
        if not context_sources:
            return "\n📭 No context sources were used for this draft\n"
        
        output = [
            "\nContext Sources Used for Draft Generation\n"
        ]
        
        for idx, source in enumerate(context_sources, 1):
            output.append(f"[{idx}] {source.get('title', 'Untitled')}")
            output.append(f"    Database: {source.get('database', 'unknown')} | Relevance: {source.get('similarity', 0):.0%}")
            snippet = source.get('snippet', '')[:100]
            output.append(f"    Preview: {snippet}...")
            output.append("")
        
        output.append("\n[b] Back  [q] Quit")
        return '\n'.join(output)
    
    async def launch_review(self, workspaces: List[str]):
        """Main review flow."""
        # Load drafts for specified workspaces
        all_drafts = []
        for workspace in workspaces:
            drafts = self.draft_manager.get_drafts_for_workspace(workspace, include_resolved=True)
            all_drafts.extend(drafts)
        
        if not all_drafts:
            print_text("\n📭 No email drafts to review. All caught up!\n", style="green")
            return
        
        # Initial stats
        stats = self._calculate_stats(all_drafts)
        
        # State
        current_selection = 0
        page_start = 0  # Start of current page window
        
        # Get terminal height for pagination
        try:
            rows, _ = os.popen('stty size', 'r').read().split()
            terminal_height = int(rows)
        except:
            terminal_height = 24  # Default fallback
        
        # Reserve lines for header (5) + controls (2) + pagination (2) + prompt (1) = 10 lines
        # Each draft takes ~5 lines
        max_visible_drafts = max(1, (terminal_height - 10) // 5)
        
        # Main loop - just show list and open chat
        while True:
            try:
                # --- 1. Calculate Pagination ---
                # Fixed window pagination - window only moves when selection reaches edges
                page_start = max(0, min(page_start, len(all_drafts) - max_visible_drafts))
                if len(all_drafts) <= max_visible_drafts:
                    page_start = 0
                
                start_idx = page_start
                end_idx = min(len(all_drafts), start_idx + max_visible_drafts)

                # --- 2. Build Display String ---
                # Build the entire display as a single string for atomic rendering
                display_parts = []
                
                # Header
                display_parts.append(self._render_status_bar(stats))
                
                # Controls
                controls_line = "Navigation: ↑/↓ | Enter to open chat | a archive | q quit"
                display_parts.append(controls_line + "\n")
                
                # Pagination info
                if len(all_drafts) > max_visible_drafts:
                    display_parts.append(f"Showing {start_idx + 1}-{end_idx} of {len(all_drafts)} drafts\n")
                
                # Queue list
                visible_drafts = all_drafts[start_idx:end_idx]
                visible_selection = current_selection - start_idx
                queue_list = self._render_review_list(visible_drafts, visible_selection, start_offset=start_idx)
                display_parts.append(queue_list)
                
                final_output = "".join(display_parts)
                
                # --- 3. Atomic Render ---
                # Use a single write call with ANSI codes for a flicker-free update
                # \033[?25l = hide cursor
                # \033[H = move to home (top-left)
                # \033[J = clear screen from cursor down
                # \033[?25h = show cursor
                atomic_render_sequence = f"\033[?25l\033[H\033[J{final_output}\033[?25h"
                sys.stdout.write(atomic_render_sequence)
                sys.stdout.flush()
                
                # --- 4. Get Input ---
                action = await self._get_keystroke()
                
                # --- 5. Handle Input ---
                if action == 'q' or action == 'escape':
                    break
                elif action == 'enter':
                    # Open draft chat for selected draft
                    await self._handle_chat(all_drafts[current_selection])
                    # Reload draft after chat
                    updated_draft = self.draft_manager.get_draft(all_drafts[current_selection]['draft_id'])
                    if updated_draft:
                        all_drafts[current_selection] = updated_draft
                    stats = self._calculate_stats(all_drafts)
                elif action == 'a':
                    # Archive: mark as archived to clear from queue
                    await self._handle_archive(all_drafts[current_selection])
                    # Reload draft after archiving
                    updated_draft = self.draft_manager.get_draft(all_drafts[current_selection]['draft_id'])
                    if updated_draft:
                        all_drafts[current_selection] = updated_draft
                    stats = self._calculate_stats(all_drafts)
                elif action == 'up':
                    if current_selection > 0:
                        current_selection -= 1
                        # Scroll page up if selection goes above visible window
                        if current_selection < page_start:
                            page_start = current_selection
                elif action == 'down':
                    if current_selection < len(all_drafts) - 1:
                        current_selection += 1
                        # Scroll page down if selection goes below visible window
                        if current_selection >= page_start + max_visible_drafts:
                            page_start = current_selection - max_visible_drafts + 1
                        
            except KeyboardInterrupt:
                break
            except Exception as e:
                logger.error(f"Error in review loop: {e}")
                print_text(f"\n❌ Error: {e}\n", style="red")
                input("Press Enter to continue...")
        
        # Final summary (back on main screen now)
        final_stats = self._calculate_stats(all_drafts)
        print()
        print_text(
            f"✅ Session complete: {final_stats['sent']} sent, "
            f"{final_stats['archived']} archived, {final_stats['pending']} pending",
            style="green"
        )
    
    async def _handle_archive(self, draft: Dict[str, Any]):
        """
        Handle archiving a draft.
        
        Archive clears the item from your queue - gives the satisfying feeling
        of clearing papers off your desk.
        """
        self.draft_manager.update_draft_status(draft['draft_id'], 'archived')
        logger.info(f"Draft {draft['draft_id']} archived")
    
    async def _handle_chat(self, draft: Dict[str, Any]):
        """Handle opening chat for a draft."""
        from promaia.mail.draft_chat import DraftChatInterface
        
        chat = DraftChatInterface(draft['draft_id'], draft['workspace'])
        await chat.run_chat_loop()
    
    async def _save_to_learning(self, draft: Dict[str, Any]):
        """Save successful send to learning system."""
        try:
            from promaia.mail.learning_system import EmailResponseLearningSystem
            learning = EmailResponseLearningSystem()
            
            pattern = {
                "inbound": {
                    "from": draft['inbound_from'],
                    "subject": draft['inbound_subject'],
                    "body_snippet": draft['inbound_snippet'],
                },
                "response": {
                    "subject": draft['draft_subject'],
                    "body": draft['draft_body'],
                    "tone": "professional",
                    "length": len(draft['draft_body'].split())
                },
                "metadata": {
                    "workspace": draft['workspace'],
                    "ai_model": draft.get('ai_model', 'unknown'),
                    "context_sources": draft.get('response_context', '{}'),
                    "timestamp": now_utc().isoformat()
                }
            }
            
            learning.save_successful_response(pattern)
            logger.info("✅ Saved response pattern to learning system")
            
        except Exception as e:
            logger.warning(f"⚠️  Could not save to learning system: {e}")
