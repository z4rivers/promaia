"""
Draft Chat Interface - The main review interface for email drafts.

This IS the draft review screen. When you select a draft from the list,
you enter this interface which shows:
- The inbound message
- The AI's draft response (or explanation if no response needed)
- Chat interface for refinement
- Commands: /send, /quit, /resolve, /reject
"""
import asyncio
import logging
import os
from typing import Dict, Any, Optional
from datetime import datetime

from promaia.mail.draft_manager import DraftManager
from promaia.mail.gmail_sender import GmailSender
from promaia.mail.response_generator import ResponseGenerator
from promaia.mail.learning_system import EmailResponseLearningSystem
from promaia.utils.display import print_text
from promaia.utils.timezone_utils import to_local, get_local_timezone_name, now_utc

logger = logging.getLogger(__name__)


class DraftChatInterface:
    """
    The main draft review and refinement interface.
    
    This combines viewing the email, the draft, and refining/sending it
    all in one conversational interface.
    """
    
    def __init__(self, draft_id: str, workspace: str):
        """
        Initialize draft chat interface.
        
        Args:
            draft_id: Draft ID to work with
            workspace: Workspace name
        """
        self.draft_id = draft_id
        self.workspace = workspace
        self.draft_manager = DraftManager()
        self.response_generator = ResponseGenerator()
        self.learning_system = EmailResponseLearningSystem()
        
        # Artifacts: draft_number -> draft_text
        self.artifacts = {}
        self.current_artifact_number = 0
    
    def _clear_screen(self):
        """Clear terminal screen."""
        os.system('clear' if os.name != 'nt' else 'cls')
    
    def _clean_email_body(self, body: str) -> str:
        """Remove redundant email headers from body content."""
        if not body:
            return body
        
        lines = body.split('\n')
        cleaned_lines = []
        skip_headers = True
        
        for line in lines:
            if skip_headers:
                if line.strip().startswith(('From:', 'Sent:', 'To:', 'Subject:', 'Date:', 'Cc:', 'Bcc:')):
                    continue
                elif not line.strip():
                    continue
                else:
                    skip_headers = False
                    cleaned_lines.append(line)
            else:
                cleaned_lines.append(line)
        
        return '\n'.join(cleaned_lines).strip()
    
    def _render_interface(self, draft: Dict[str, Any], show_draft: bool = True):
        """
        Render the full draft review interface.
        
        Args:
            draft: Draft data
            show_draft: Whether to show the latest artifact number in the display
        """
        self._clear_screen()
        
        # Format date
        try:
            received_dt = datetime.fromisoformat(draft.get('inbound_date', '').replace('Z', '+00:00'))
            local_received = to_local(received_dt)
            tz_name = get_local_timezone_name()
            received_str = local_received.strftime(f'%A, %B %d, %Y at %I:%M %p {tz_name}')
        except:
            received_str = draft.get('inbound_date', 'Unknown')
        
        # Clean email body
        cleaned_body = self._clean_email_body(draft.get('inbound_body', 'No body available'))
        
        # Determine if this needs a response
        requires_response = draft.get('requires_response', True)
        draft_body = draft.get('draft_body', '')
        
        print(f"""
╭──────────────────────────────────────────────────────────────────────────────────────╮
│  Draft Review Chat - {draft.get('inbound_subject', 'No Subject')[:50]:50}                 │
╰──────────────────────────────────────────────────────────────────────────────────────╯

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  INBOUND MESSAGE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

From:     {draft.get('inbound_from', 'Unknown')}
Subject:  {draft.get('inbound_subject', 'No Subject')}
Date:     {received_str}
Thread:   {draft.get('message_count', 1)} message(s) in thread

{cleaned_body}
""")
        
        if requires_response and draft_body:
            # Show draft as an artifact
            word_count = len(draft_body.split())
            artifact_num = self.current_artifact_number if show_draft else ""
            artifact_label = f" #{artifact_num}" if artifact_num else ""
            
            print(f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  DRAFT RESPONSE{artifact_label} ({word_count} words)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

{draft_body}
""")
        else:
            # AI determined no response needed - show explanation
            print(f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  AI ASSESSMENT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

{draft_body if draft_body else 'No response needed for this email.'}

Classification:
  Pertains to me: {draft.get('pertains_to_me', 'Unknown')}
  Is spam: {draft.get('is_spam', 'Unknown')}
  Requires response: {draft.get('requires_response', 'Unknown')}

Reasoning: {draft.get('classification_reasoning', 'No reasoning provided')}
""")
        
        # Show commands
        if requires_response and draft_body:
            print("""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  COMMANDS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  /send        Send the current draft
  /quit        Return to draft list (or just type /q)
  /resolve     Mark as resolved without sending
  /reject      Reject this draft
  
  Or chat naturally to refine the draft - each refinement creates a new artifact.

""")
        else:
            print("""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  COMMANDS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  /quit        Return to draft list (or just type /q)
  /resolve     Mark as resolved without sending
  
  You can also chat to request a draft if you think one is needed.

""")
    
    async def run_chat_loop(self):
        """
        Main chat loop for the draft review interface.
        
        This is where the user reviews the email, sees the draft,
        and can refine/send/reject it through chat commands.
        """
        try:
            # Load current draft
            draft = self.draft_manager.get_draft(self.draft_id)
            
            if not draft:
                print_text(f"❌ Draft {self.draft_id} not found", style="red")
                return
            
            # Initialize with current draft as artifact #1
            requires_response = draft.get('requires_response', True)
            draft_body = draft.get('draft_body', '')
            
            if requires_response and draft_body:
                self.current_artifact_number = 1
                self.artifacts[1] = draft_body
            
            # Display interface
            self._render_interface(draft, show_draft=True)
            
            # Chat loop
            while True:
                try:
                    user_input = input("💬 ").strip()
                    
                    if not user_input:
                        continue
                    
                    # Handle commands
                    if user_input.startswith('/'):
                        command = user_input.lower()
                        
                        if command in ['/q', '/quit']:
                            print_text("\n↩️  Returning to draft list...\n", style="cyan")
                            break
                        
                        elif command in ['/send', '/s']:
                            should_exit = await self._handle_send_command(draft)
                            if should_exit:
                                break
                            # Redraw interface
                            self._render_interface(draft, show_draft=True)
                            continue
                        
                        elif command in ['/resolve', '/r']:
                            self.draft_manager.update_draft_status(self.draft_id, 'resolved')
                            print_text("\n✅ Marked as resolved\n", style="green")
                            break
                        
                        elif command in ['/reject']:
                            self.draft_manager.update_draft_status(self.draft_id, 'rejected')
                            print_text("\n❌ Marked as rejected\n", style="yellow")
                            break
                        
                        else:
                            print_text(f"❌ Unknown command: {user_input}", style="red")
                            print_text("Available commands: /send, /quit, /resolve, /reject", style="dim")
                            input("\nPress Enter to continue...")
                            self._render_interface(draft, show_draft=True)
                            continue
                    
                    # Regular chat - refine the draft or create one
                    print_text("\n🤔 Processing your request...", style="cyan")
                    
                    if not requires_response or not draft_body:
                        # User is requesting a draft be created
                        print_text("Creating a draft based on your feedback...", style="cyan")
                        # TODO: Implement draft creation from user request
                        print_text("⚠️  Draft creation from chat not yet implemented", style="yellow")
                        input("\nPress Enter to continue...")
                        self._render_interface(draft, show_draft=True)
                    else:
                        # Refine existing draft
                        refined_draft = await self._refine_draft(draft, user_input)
                        
                        # Increment artifact number
                        self.current_artifact_number += 1
                        self.artifacts[self.current_artifact_number] = refined_draft
                        
                        # Update draft in DB
                        self.draft_manager.update_draft_body(
                            self.draft_id,
                            refined_draft,
                            version=self.current_artifact_number
                        )
                        
                        # Update local draft reference
                        draft['draft_body'] = refined_draft
                        
                        # Redraw with new artifact
                        self._render_interface(draft, show_draft=True)
                        print_text(f"✅ Updated to Draft #{self.current_artifact_number}", style="green")
                    
                except KeyboardInterrupt:
                    print_text("\n\n↩️  Returning to draft list...\n", style="cyan")
                    break
                except EOFError:
                    print_text("\n\n↩️  Returning to draft list...\n", style="cyan")
                    break
        
        except Exception as e:
            logger.error(f"❌ Error in draft chat: {e}")
            print_text(f"\n❌ Error: {e}\n", style="red")
            import traceback
            traceback.print_exc()
    
    async def _refine_draft(self, draft: Dict[str, Any], user_feedback: str) -> str:
        """
        Refine draft based on user feedback.
        
        Args:
            draft: Draft data
            user_feedback: User's refinement request
            
        Returns:
            Refined draft text
        """
        try:
            # Get current draft (latest artifact)
            current_draft = self.artifacts.get(self.current_artifact_number, draft['draft_body'])
            
            # Simple refinement prompt
            from promaia.ai.client import get_ai_client
            client = get_ai_client()
            
            refinement_prompt = f"""You are refining an email draft based on user feedback.

**Original Inbound Email:**
From: {draft['inbound_from']}
Subject: {draft['inbound_subject']}
Body: {draft['inbound_body'][:500]}...

**Current Draft:**
{current_draft}

**User Feedback:**
{user_feedback}

Please provide the refined email draft incorporating the user's feedback. Return ONLY the email text, no explanations."""

            response = await client.generate_completion(refinement_prompt)
            return response.strip()
            
        except Exception as e:
            logger.error(f"❌ Failed to refine draft: {e}")
            print_text(f"⚠️  Refinement failed: {e}", style="yellow")
            # Return current draft on error
            return self.artifacts.get(self.current_artifact_number, draft['draft_body'])
    
    async def _handle_send_command(self, draft: Dict[str, Any]) -> bool:
        """
        Handle /send command.
        
        Args:
            draft: Draft data
            
        Returns:
            True if should exit chat, False to continue
        """
        # Get the current draft to send
        current_draft = self.artifacts.get(self.current_artifact_number, draft['draft_body'])
        
        if not current_draft or not draft.get('requires_response'):
            print_text("\n❌ No draft to send\n", style="red")
            input("Press Enter to continue...")
            return False
        
        # Safety confirmation
        print_text(f"\n⚠️  Ready to send draft", style="bold yellow")
        print_text(f"Subject: {draft['inbound_subject']}", style="yellow")
        print_text(f"\nType the first 5 characters of the subject to confirm: '{draft['safety_string']}'", style="yellow")
        
        confirmation = input("\nConfirm: ").strip()
        
        if confirmation != draft['safety_string']:
            print_text("\n❌ Confirmation failed\n", style="red")
            input("Press Enter to continue...")
            return False
        
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
            input("Press Enter to continue...")
            return False
        
        sender = GmailSender(draft['workspace'], gmail_dbs[0].database_id)
        success = await sender.send_reply(
            thread_id=draft['thread_id'],
            message_id=draft['message_id'],
            subject=draft['draft_subject'],
            body_text=current_draft
        )
        
        if success:
            print_text("✅ Email sent!", style="green")
            self.draft_manager.mark_sent(self.draft_id)
            
            # Save to learning system
            pattern = {
                "inbound": {
                    "from": draft['inbound_from'],
                    "subject": draft['inbound_subject'],
                    "body_snippet": draft['inbound_snippet'],
                },
                "response": {
                    "subject": draft['draft_subject'],
                    "body": current_draft,
                    "tone": "professional",
                    "length": len(current_draft.split())
                },
                "metadata": {
                    "workspace": draft['workspace'],
                    "ai_model": draft.get('ai_model', 'unknown'),
                    "timestamp": now_utc().isoformat()
                }
            }
            self.learning_system.save_successful_response(pattern)
            
            input("\nPress Enter to return to draft list...")
            return True
        else:
            print_text("❌ Failed to send\n", style="red")
            input("Press Enter to continue...")
            return False
