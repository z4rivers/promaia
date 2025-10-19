"""
Review UI - prompt_toolkit-based review interface with full information display.

Provides a complete email review experience without needing to open Gmail:
- Progress tracking (X/Y threads resolved)
- Full visibility of all draft information
- Context view showing what sources were used
- Navigation and action commands
"""
import asyncio
import json
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional

from prompt_toolkit.application import Application
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.keys import Keys
from prompt_toolkit.layout.containers import HSplit, Window
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.layout.layout import Layout
from prompt_toolkit.formatted_text import FormattedText

from promaia.mail.draft_manager import DraftManager
from promaia.mail.gmail_sender import GmailSender
from promaia.mail.learning_system import EmailResponseLearningSystem
from promaia.utils.display import print_text, print_separator

logger = logging.getLogger(__name__)


class EmailReviewUI:
    """prompt_toolkit-based review interface with full information display."""
    
    def __init__(self):
        """Initialize review UI."""
        self.draft_manager = DraftManager()
        self.learning_system = EmailResponseLearningSystem()
    
    def _calculate_stats(self, drafts: List[Dict[str, Any]]) -> Dict[str, int]:
        """Calculate session statistics."""
        return {
            'total': len(drafts),
            'pending': len([d for d in drafts if d['status'] == 'pending']),
            'sent': len([d for d in drafts if d['status'] == 'sent']),
            'rejected': len([d for d in drafts if d['status'] == 'rejected']),
            'resolved': len([d for d in drafts if d['status'] in ['sent', 'rejected']])
        }
    
    def _render_status_bar(self, stats: Dict[str, int]) -> str:
        """Render top status bar with completion count."""
        resolved = stats['resolved']
        total = stats['total']
        percentage = int((resolved / total * 100)) if total > 0 else 0
        
        # Progress bar
        bar_width = 30
        filled = int(bar_width * resolved / total) if total > 0 else 0
        bar = '█' * filled + '░' * (bar_width - filled)
        
        return f"""
╭──────────────────────────────────────────────────────────────────────────────────────╮
│  Maia Mail - Draft Review Queue                                                     │
│                                                                                      │
│  Progress: [{bar}] {resolved}/{total} resolved ({percentage}%)        │
│  Status: ✅ {stats['sent']} sent  •  ❌ {stats['rejected']} rejected  •  ⏳ {stats['pending']} pending   │
╰──────────────────────────────────────────────────────────────────────────────────────╯
"""
    
    def _render_review_list(self, drafts: List[Dict[str, Any]], current_selection: int) -> str:
        """Render list with full visibility of all threads."""
        if not drafts:
            return "\n📭 No pending drafts. All caught up!\n"
        
        output = []
        
        for idx, draft in enumerate(drafts):
            is_selected = idx == current_selection
            status_icon = {
                'pending': '⏳',
                'sent': '✅',
                'rejected': '❌',
                'edited': '✏️'
            }.get(draft['status'], '•')
            
            # Selection indicator
            selector = '▶' if is_selected else ' '
            
            # Format timestamp
            received_time = draft.get('inbound_date', '')
            if received_time:
                try:
                    dt = datetime.fromisoformat(received_time.replace('Z', '+00:00'))
                    time_str = dt.strftime('%b %d, %I:%M %p')
                except:
                    time_str = 'Unknown'
            else:
                time_str = 'Unknown'
            
            # Draft word count
            draft_words = len(draft.get('draft_body', '').split())
            
            # Context count
            try:
                context_data = json.loads(draft.get('response_context', '{}'))
                context_count = len(context_data.get('documents', []))
            except:
                context_count = 0
            
            subject = draft.get('inbound_subject', 'No Subject')[:60]
            from_addr = draft.get('inbound_from', 'Unknown')[:50]
            snippet = draft.get('inbound_snippet', '')[:70]
            
            output.append(
                f"{selector} [{idx+1}] {status_icon} {subject}\n"
                f"       From: {from_addr} | {time_str}\n"
                f"       Preview: {snippet}...\n"
                f"       Draft: {draft_words} words | Context: {context_count} sources\n"
            )
        
        return '\n'.join(output)
    
    def _render_draft_detail(self, draft: Dict[str, Any]) -> str:
        """Show full detail view - everything needed to make a decision."""
        # Parse response context
        try:
            context_data = json.loads(draft.get('response_context', '{}'))
            context_sources = context_data.get('documents', [])
            context_count = len(context_sources)
            context_summary = ', '.join([s.get('database', 'unknown') for s in context_sources[:3]])
            if len(context_sources) > 3:
                context_summary += f" + {len(context_sources) - 3} more"
        except:
            context_count = 0
            context_summary = "None"
        
        # Format timestamps
        try:
            received_dt = datetime.fromisoformat(draft.get('inbound_date', '').replace('Z', '+00:00'))
            received_str = received_dt.strftime('%A, %B %d, %Y at %I:%M %p')
        except:
            received_str = draft.get('inbound_date', 'Unknown')
        
        # Thread context
        thread_context = draft.get('thread_context', '')
        thread_summary = f"\n{thread_context[:200]}...\n" if thread_context and len(thread_context) > 50 else ""
        
        # Word count
        draft_words = len(draft.get('draft_body', '').split())
        
        return f"""
╭──────────────────────────────────────────────────────────────────────────────────────╮
│  Draft Review - Full View                                                           │
╰──────────────────────────────────────────────────────────────────────────────────────╯

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  INBOUND MESSAGE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

From:     {draft.get('inbound_from', 'Unknown')}
Subject:  {draft.get('inbound_subject', 'No Subject')}
Date:     {received_str}
Thread:   {draft.get('message_count', 1)} message(s) in thread
{thread_summary}
{draft.get('inbound_body', 'No body available')}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  YOUR DRAFT RESPONSE ({draft_words} words)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

{draft.get('draft_body', 'No draft available')}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  CONTEXT USED
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Sources:     {context_count} documents from knowledge base
Databases:   {context_summary}
AI Model:    {draft.get('ai_model', 'unknown')}
Generated:   {draft.get('created_time', 'unknown')}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  ACTIONS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  s  - Send this draft (with confirmation)
  c  - Open chat to refine the draft
  r  - Reject (won't send, mark as handled)
  v  - View full context sources
  Esc - Back to list

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
            "╭──────────────────────────────────────────────────────────────────────────────────────╮",
            "│  Context Sources Used for Draft Generation                                          │",
            "╰──────────────────────────────────────────────────────────────────────────────────────╯\n"
        ]
        
        for idx, source in enumerate(context_sources, 1):
            output.append(f"[{idx}] {source.get('title', 'Untitled')}")
            output.append(f"    Database: {source.get('database', 'unknown')} | Relevance: {source.get('similarity', 0):.0%}")
            snippet = source.get('snippet', '')[:100]
            output.append(f"    Preview: {snippet}...")
            output.append("")
        
        output.append("\nPress Esc to return to draft view...")
        return '\n'.join(output)
    
    async def launch_review(self, workspaces: List[str]):
        """Main review flow with full information display."""
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
        
        # Display executive summary
        print()
        print(self._render_status_bar(stats))
        print()
        print_text(f"Found {stats['total']} draft(s) for review\n", style="cyan")
        
        # State
        current_selection = 0
        current_view = 'list'  # 'list', 'detail', 'context'
        should_refresh = False
        
        # Main loop using prompt_toolkit
        while True:
            try:
                bindings = KeyBindings()
                
                # Navigation
                @bindings.add(Keys.Up)
                def move_up(event):
                    nonlocal current_selection
                    if current_view == 'list' and current_selection > 0:
                        current_selection -= 1
                        event.app.exit(result='refresh')
                
                @bindings.add(Keys.Down)
                def move_down(event):
                    nonlocal current_selection
                    if current_view == 'list' and current_selection < len(all_drafts) - 1:
                        current_selection += 1
                        event.app.exit(result='refresh')
                
                @bindings.add(Keys.Enter)
                def view_detail(event):
                    nonlocal current_view
                    if current_view == 'list':
                        current_view = 'detail'
                    else:
                        current_view = 'list'
                    event.app.exit(result='refresh')
                
                @bindings.add('v')
                def view_context(event):
                    nonlocal current_view
                    if current_view == 'detail':
                        current_view = 'context'
                        event.app.exit(result='refresh')
                
                @bindings.add('s')
                def send_draft(event):
                    nonlocal should_refresh
                    if current_view == 'detail':
                        should_refresh = True
                        event.app.exit(result='send')
                
                @bindings.add('c')
                def open_chat(event):
                    nonlocal should_refresh
                    if current_view == 'detail':
                        should_refresh = True
                        event.app.exit(result='chat')
                
                @bindings.add('r')
                def reject_draft(event):
                    nonlocal should_refresh, stats
                    if current_view == 'detail':
                        draft = all_drafts[current_selection]
                        self.draft_manager.update_draft_status(draft['draft_id'], 'rejected')
                        draft['status'] = 'rejected'
                        stats = self._calculate_stats(all_drafts)
                        current_view = 'list'
                        should_refresh = True
                        event.app.exit(result='refresh')
                
                @bindings.add(Keys.Escape)
                def go_back(event):
                    nonlocal current_view
                    if current_view in ['detail', 'context']:
                        current_view = 'list'
                        event.app.exit(result='refresh')
                    else:
                        event.app.exit(result='quit')
                
                @bindings.add('q')
                def quit_review(event):
                    event.app.exit(result='quit')
                
                # Render content
                def render_view():
                    output = [self._render_status_bar(stats)]
                    
                    if current_view == 'list':
                        output.append(self._render_review_list(all_drafts, current_selection))
                        output.append("\nNavigation: ↑/↓ select | Enter view | q quit\n")
                    elif current_view == 'detail':
                        output.append(self._render_draft_detail(all_drafts[current_selection]))
                    elif current_view == 'context':
                        output.append(self._render_context_view(all_drafts[current_selection]))
                    
                    return '\n'.join(output)
                
                # Create application
                content_control = FormattedTextControl(text=render_view)
                container = HSplit([Window(content=content_control, height=None)])
                layout = Layout(container)
                
                app = Application(
                    layout=layout,
                    key_bindings=bindings,
                    full_screen=False,
                    mouse_support=False
                )
                
                # Run and get result
                result = await app.run_async()
                
                if result == 'quit':
                    break
                
                elif result == 'send':
                    await self._handle_send(all_drafts[current_selection], stats)
                    stats = self._calculate_stats(all_drafts)
                    current_view = 'list'
                
                elif result == 'chat':
                    await self._handle_chat(all_drafts[current_selection])
                    # Reload draft
                    updated_draft = self.draft_manager.get_draft(all_drafts[current_selection]['draft_id'])
                    all_drafts[current_selection] = updated_draft
                    stats = self._calculate_stats(all_drafts)
                    current_view = 'list'
                
            except KeyboardInterrupt:
                break
        
        # Final summary
        final_stats = self._calculate_stats(all_drafts)
        print()
        print_text(
            f"✅ Session complete: {final_stats['sent']} sent, "
            f"{final_stats['rejected']} rejected, {final_stats['pending']} pending",
            style="green"
        )
    
    async def _handle_send(self, draft: Dict[str, Any], stats: Dict[str, int]):
        """Handle sending a draft."""
        # This will be called from outside the prompt_toolkit app
        print()
        print_text(f"⚠️  Ready to send draft", style="bold yellow")
        print_text(f"Type the first 5 characters to confirm: {draft['inbound_subject'][:20]}...", style="yellow")
        
        confirmation = input("Confirm: ").strip()
        
        if confirmation != draft['safety_string']:
            print_text("❌ Confirmation failed\n", style="red")
            return
        
        print_text("\n📤 Sending email...", style="cyan")
        
        # Get Gmail config
        from promaia.config.databases import get_database_manager
        db_manager = get_database_manager()
        gmail_dbs = [
            db for db in db_manager.get_workspace_databases(draft['workspace'])
            if db.source_type == "gmail"
        ]
        
        if not gmail_dbs:
            print_text("❌ No Gmail database found\n", style="red")
            return
        
        sender = GmailSender(draft['workspace'], gmail_dbs[0].database_id)
        success = await sender.send_reply(
            thread_id=draft['thread_id'],
            message_id=draft['message_id'],
            subject=draft['draft_subject'],
            body_text=draft['draft_body']
        )
        
        if success:
            print_text("✅ Email sent!\n", style="green")
            self.draft_manager.mark_sent(draft['draft_id'])
            draft['status'] = 'sent'
            
            # Save to learning
            await self._save_to_learning(draft)
        else:
            print_text("❌ Failed to send\n", style="red")
        
        input("Press Enter to continue...")
    
    async def _handle_chat(self, draft: Dict[str, Any]):
        """Handle opening chat for a draft."""
        from promaia.mail.draft_chat import DraftChatInterface
        
        chat = DraftChatInterface(draft['draft_id'], draft['workspace'])
        await chat.run_chat_loop()
    
    async def _save_to_learning(self, draft: Dict[str, Any]):
        """Save successful send to learning system."""
        try:
            pattern = {
                "inbound": {
                    "from": draft['inbound_from'],
                    "subject": draft['inbound_subject'],
                    "body_snippet": draft['inbound_snippet'],
                    "thread_context": draft.get('thread_context', '')
                },
                "response": {
                    "subject": draft['draft_subject'],
                    "body": draft['draft_body'],
                    "tone": "professional",
                    "length": len(draft['draft_body'].split())
                },
                "metadata": {
                    "workspace": draft['workspace'],
                    "sent_time": draft.get('sent_time', ''),
                    "was_successful": True,
                    "notes": "Sent via review UI"
                }
            }
            
            self.learning_system.save_successful_response(pattern)
        except Exception as e:
            logger.warning(f"Could not save to learning: {e}")

