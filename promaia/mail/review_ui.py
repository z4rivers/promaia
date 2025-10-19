"""
Email Draft Review UI - Interactive review interface for email drafts.
"""
import json
import logging
import os
from typing import List, Dict, Any, Optional
from datetime import datetime

from promaia.mail.draft_manager import DraftManager
from promaia.mail.gmail_sender import GmailSender
from promaia.utils.formatting import print_text, print_separator

logger = logging.getLogger(__name__)


class EmailReviewUI:
    """Interactive review interface for email drafts."""
    
    def __init__(self):
        self.draft_manager = DraftManager()
        self.session_stats = {
            'sent': 0,
            'rejected': 0,
            'pending': 0
        }
    
    def _clear_screen(self):
        """Clear terminal screen."""
        os.system('clear' if os.name != 'nt' else 'cls')
    
    def _calculate_stats(self, drafts: List[Dict[str, Any]]) -> Dict[str, int]:
        """Calculate stats from draft list."""
        stats = {
            'total': len(drafts),
            'sent': sum(1 for d in drafts if d.get('status') == 'sent'),
            'rejected': sum(1 for d in drafts if d.get('status') == 'rejected'),
            'pending': sum(1 for d in drafts if d.get('status') == 'pending'),
        }
        stats['resolved'] = stats['sent'] + stats['rejected']
        if stats['total'] > 0:
            stats['percent'] = int((stats['resolved'] / stats['total']) * 100)
        else:
            stats['percent'] = 0
        return stats
    
    def _render_status_bar(self, stats: Dict[str, int]) -> str:
        """Render progress and status bar."""
        # Progress bar
        total_width = 30
        filled = int((stats['percent'] / 100) * total_width)
        bar = '█' * filled + '░' * (total_width - filled)
        
        return f"""
╭──────────────────────────────────────────────────────────────────────────────────────╮
│  Maia Mail - Draft Review Queue                                                     │
│                                                                                      │
│  Progress: [{bar}] {stats['resolved']}/{stats['total']} resolved ({stats['percent']}%)        │
│  Status: ✅ {stats['sent']} sent  •  ❌ {stats['rejected']} rejected  •  ⏳ {stats['pending']} pending   │
╰──────────────────────────────────────────────────────────────────────────────────────╯
"""
    
    def _render_review_list(self, drafts: List[Dict[str, Any]], current_selection: int) -> str:
        """Render list of drafts for review."""
        output = []
        
        for idx, draft in enumerate(drafts):
            # Status icon
            if draft.get('status') == 'sent':
                icon = '✅'
            elif draft.get('status') == 'rejected':
                icon = '❌'
            else:
                icon = '⏳'
            
            # Selection indicator
            selector = '▶' if idx == current_selection else ' '
            
            # Format date
            try:
                date_obj = datetime.fromisoformat(draft.get('inbound_date', '').replace('Z', '+00:00'))
                date_str = date_obj.strftime('%b %d, %I:%M %p')
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
            
            # Context count
            try:
                context_data = json.loads(draft.get('response_context', '{}'))
                context_count = len(context_data.get('documents', []))
            except:
                context_count = 0
            
            # Word count
            word_count = len(draft.get('draft_body', '').split())
            
            output.append(f"{selector} [{idx + 1}] {icon} {subject}")
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
        
        # Format date
        try:
            received_dt = datetime.fromisoformat(draft.get('inbound_date', '').replace('Z', '+00:00'))
            received_str = received_dt.strftime('%A, %B %d, %Y at %I:%M %p')
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
  b  - Back to list

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
        
        output.append("\nPress 'b' to return to draft view...")
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
        current_view = 'list'  # 'list', 'detail', 'context'
        
        # Main loop
        while True:
            try:
                # Clear and render
                self._clear_screen()
                print(self._render_status_bar(stats))
                print()
                
                if current_view == 'list':
                    print(self._render_review_list(all_drafts, current_selection))
                    print("\nNavigation: ↑/↓ select | Enter view | q quit")
                    print("Action: ", end='', flush=True)
                    
                    # Get input
                    action = input().strip().lower()
                    
                    if action == 'q':
                        break
                    elif action == '' or action == 'enter':
                        # View details
                        current_view = 'detail'
                    elif action in ['up', 'u', 'k']:
                        if current_selection > 0:
                            current_selection -= 1
                    elif action in ['down', 'd', 'j']:
                        if current_selection < len(all_drafts) - 1:
                            current_selection += 1
                    elif action.isdigit():
                        idx = int(action) - 1
                        if 0 <= idx < len(all_drafts):
                            current_selection = idx
                            current_view = 'detail'
                
                elif current_view == 'detail':
                    print(self._render_draft_detail(all_drafts[current_selection]))
                    print("Action: ", end='', flush=True)
                    
                    action = input().strip().lower()
                    
                    if action == 'b' or action == 'q':
                        current_view = 'list'
                    elif action == 's':
                        await self._handle_send(all_drafts[current_selection])
                        # Reload draft
                        updated_draft = self.draft_manager.get_draft(all_drafts[current_selection]['draft_id'])
                        all_drafts[current_selection] = updated_draft
                        stats = self._calculate_stats(all_drafts)
                        current_view = 'list'
                    elif action == 'c':
                        await self._handle_chat(all_drafts[current_selection])
                        # Reload draft
                        updated_draft = self.draft_manager.get_draft(all_drafts[current_selection]['draft_id'])
                        all_drafts[current_selection] = updated_draft
                        stats = self._calculate_stats(all_drafts)
                        current_view = 'list'
                    elif action == 'r':
                        self.draft_manager.update_draft_status(all_drafts[current_selection]['draft_id'], 'rejected')
                        all_drafts[current_selection]['status'] = 'rejected'
                        stats = self._calculate_stats(all_drafts)
                        current_view = 'list'
                    elif action == 'v':
                        current_view = 'context'
                
                elif current_view == 'context':
                    print(self._render_context_view(all_drafts[current_selection]))
                    print("\nAction: ", end='', flush=True)
                    
                    action = input().strip().lower()
                    if action == 'b' or action == 'q':
                        current_view = 'detail'
                        
            except KeyboardInterrupt:
                break
            except Exception as e:
                logger.error(f"Error in review loop: {e}")
                print_text(f"\n❌ Error: {e}\n", style="red")
                input("Press Enter to continue...")
        
        # Final summary
        self._clear_screen()
        final_stats = self._calculate_stats(all_drafts)
        print()
        print_text(
            f"✅ Session complete: {final_stats['sent']} sent, "
            f"{final_stats['rejected']} rejected, {final_stats['pending']} pending",
            style="green"
        )
    
    async def _handle_send(self, draft: Dict[str, Any]):
        """Handle sending a draft."""
        self._clear_screen()
        print_text(f"\n⚠️  Ready to send draft", style="bold yellow")
        print_text(f"Subject: {draft['inbound_subject']}", style="yellow")
        print_text(f"\nType the first 5 characters of the subject to confirm: '{draft['safety_string']}'", style="yellow")
        
        confirmation = input("\nConfirm: ").strip()
        
        if confirmation != draft['safety_string']:
            print_text("❌ Confirmation failed. Press Enter to continue...", style="red")
            input()
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
            print_text("❌ No Gmail database found. Press Enter to continue...", style="red")
            input()
            return
        
        sender = GmailSender(draft['workspace'], gmail_dbs[0].database_id)
        success = await sender.send_reply(
            thread_id=draft['thread_id'],
            message_id=draft['message_id'],
            subject=draft['draft_subject'],
            body_text=draft['draft_body']
        )
        
        if success:
            print_text("✅ Email sent!", style="green")
            self.draft_manager.mark_sent(draft['draft_id'])
            draft['status'] = 'sent'
            
            # Save to learning
            await self._save_to_learning(draft)
        else:
            print_text("❌ Failed to send", style="red")
        
        input("\nPress Enter to continue...")
    
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
                    "timestamp": datetime.utcnow().isoformat()
                }
            }
            
            learning.save_successful_response(pattern)
            logger.info("✅ Saved response pattern to learning system")
            
        except Exception as e:
            logger.warning(f"⚠️  Could not save to learning system: {e}")
