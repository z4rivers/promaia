"""
Draft Chat Interface - Specialized chat for refining email drafts.

Shows inbound message at top, then uses regular chat with artifacts.
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
from promaia.mail.context_builder import ResponseContext
from promaia.utils.display import print_text, print_separator
from promaia.utils.timezone_utils import to_local, get_local_timezone_name, now_utc

logger = logging.getLogger(__name__)


class DraftChatInterface:
    """
    Specialized chat interface for refining email drafts.
    Supports inline artifacts and draft-specific commands.
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
    
    def render_artifact(self, draft_number: int, draft_text: str) -> str:
        """
        Render draft as a numbered artifact (like Claude).
        
        Args:
            draft_number: Artifact number
            draft_text: Draft content
            
        Returns:
            Formatted artifact string
        """
        lines = draft_text.split('\n')
        wrapped_lines = []
        
        for line in lines:
            if len(line) <= 78:
                wrapped_lines.append(f"│ {line:<78} │")
            else:
                # Wrap long lines
                while len(line) > 78:
                    wrapped_lines.append(f"│ {line[:78]:<78} │")
                    line = line[78:]
                if line:
                    wrapped_lines.append(f"│ {line:<78} │")
        
        artifact = [
            f"╭──── Draft #{draft_number} ────────────────────────────────────────────────────────╮",
            "│                                                                                  │"
        ]
        artifact.extend(wrapped_lines)
        artifact.extend([
            "│                                                                                  │",
            "╰──────────────────────────────────────────────────────────────────────────────────╯"
        ])
        
        return '\n'.join(artifact)
    
    async def run_chat_loop(self):
        """
        Main chat loop for refining drafts.
        
        Supports commands:
        - /send [draft-number] - Send specified draft
        - /q - Quit to review queue
        - /resolve - Mark as resolved
        - /reject - Mark as rejected
        - Regular chat to refine the draft
        """
        try:
            # Load current draft
            draft = self.draft_manager.get_draft(self.draft_id)
            
            if not draft:
                print_text(f"❌ Draft {self.draft_id} not found", style="red")
                return
            
            # Format date
            try:
                received_dt = datetime.fromisoformat(draft.get('inbound_date', '').replace('Z', '+00:00'))
                local_received = to_local(received_dt)
                tz_name = get_local_timezone_name()
                received_str = local_received.strftime(f'%A, %B %d, %Y at %I:%M %p {tz_name}')
            except:
                received_str = draft.get('inbound_date', 'Unknown')
            
            # Clean email body
            cleaned_body = self._clean_email_body(draft.get('inbound_body', ''))
            
            # Display inbound message header (once at top)
            print()
            print_separator()
            print(f"""
╭──────────────────────────────────────────────────────────────────────────────────────╮
│  INBOUND MESSAGE                                                                     │
╰──────────────────────────────────────────────────────────────────────────────────────╯

From:     {draft['inbound_from']}
Subject:  {draft['inbound_subject']}
Date:     {received_str}
Thread:   {draft.get('message_count', 1)} message(s) in thread

{cleaned_body}
""")
            print_separator()
            print()
            
            # Check if response is needed
            requires_response = draft.get('requires_response', True)
            draft_body = draft.get('draft_body', '')
            
            if requires_response and draft_body:
                # Display current draft as artifact #1
                self.current_artifact_number = 1
                self.artifacts[1] = draft_body
                print(self.render_artifact(1, draft_body))
                print()
                
                print_text("💬 Chat to refine the draft, or use commands:", style="dim")
                print_text("   /send [number] - Send draft (e.g., /send 1)", style="dim")
                print_text("   /resolve - Mark as resolved without sending", style="dim")
                print_text("   /reject - Reject this draft", style="dim")
                print_text("   /q - Return to draft list", style="dim")
            else:
                # Show AI assessment
                print_text("AI ASSESSMENT:", style="bold yellow")
                print()
                print(draft_body if draft_body else "No response needed for this email.")
                print()
                print_text(f"Classification:", style="dim")
                print_text(f"  Pertains to me: {draft.get('pertains_to_me', 'Unknown')}", style="dim")
                print_text(f"  Is spam: {draft.get('is_spam', 'Unknown')}", style="dim")
                print_text(f"  Requires response: {draft.get('requires_response', 'Unknown')}", style="dim")
                if draft.get('classification_reasoning'):
                    print_text(f"  Reasoning: {draft.get('classification_reasoning')}", style="dim")
                print()
                print_text("Commands:", style="dim")
                print_text("   /resolve - Mark as resolved", style="dim")
                print_text("   /q - Return to draft list", style="dim")
            
            print()
            
            # Chat loop
            while True:
                try:
                    user_input = input("💬 You: ").strip()
                    
                    if not user_input:
                        continue
                    
                    # Handle commands
                    if user_input.startswith('/'):
                        cmd = user_input.lower()
                        
                        if cmd in ['/q', '/quit']:
                            print_text("\n↩️  Returning to draft list...\n", style="cyan")
                            break
                        
                        elif cmd.startswith('/send'):
                            should_exit = await self._handle_send_command(user_input, draft)
                            if should_exit:
                                break
                            continue
                        
                        elif cmd in ['/resolve', '/r']:
                            self.draft_manager.update_draft_status(self.draft_id, 'resolved')
                            print_text("\n✅ Marked as resolved\n", style="green")
                            break
                        
                        elif cmd == '/reject':
                            self.draft_manager.update_draft_status(self.draft_id, 'rejected')
                            print_text("\n❌ Marked as rejected\n", style="yellow")
                            break
                        
                        else:
                            print_text(f"❌ Unknown command: {user_input}", style="red")
                            print_text("Available: /send [number], /resolve, /reject, /q", style="dim")
                            continue
                    
                    if not requires_response or not draft_body:
                        print_text("⚠️  No draft to refine. Use /resolve or /q", style="yellow")
                        continue
                    
                    # Regular chat - refine the draft
                    print_text("🤔 Refining draft...", style="cyan")
                    
                    # Generate refined draft
                    refined_draft = await self._refine_draft(draft, user_input)
                    
                    # Increment artifact number
                    self.current_artifact_number += 1
                    self.artifacts[self.current_artifact_number] = refined_draft
                    
                    # Display new artifact inline
                    print()
                    print(self.render_artifact(self.current_artifact_number, refined_draft))
                    print()
                    
                    # Update draft in DB
                    self.draft_manager.update_draft_body(
                        self.draft_id,
                        refined_draft,
                        version=self.current_artifact_number
                    )
                    
                    print_text(f"✅ Updated to Draft #{self.current_artifact_number}", style="green")
                    print()
                    
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
            
            # Use ResponseGenerator to refine (it has the AI client setup)
            refined = await self.response_generator.refine_response(
                current_draft=current_draft,
                user_feedback=user_feedback,
                email_thread={
                    'from': draft['inbound_from'],
                    'subject': draft['inbound_subject'],
                    'date': draft['inbound_date'],
                    'body': draft['inbound_body'],
                    'conversation_body': draft.get('thread_context', '')
                },
                context=ResponseContext(
                    thread_history=draft.get('thread_context', ''),
                    relevant_docs=[],
                    relevant_docs_text="(Using cached context)",
                    workspace=self.workspace,
                    total_sources=0
                )
            )
            return refined
            
        except Exception as e:
            logger.error(f"❌ Failed to refine draft: {e}")
            print_text(f"⚠️  Refinement failed: {e}", style="yellow")
            # Return current draft on error
            return self.artifacts.get(self.current_artifact_number, draft['draft_body'])
    
    async def _handle_send_command(self, command: str, draft: Dict[str, Any]) -> bool:
        """
        Handle /send [draft-number] command.
        
        Args:
            command: The /send command string
            draft: Draft data
            
        Returns:
            True if should exit chat, False to continue
        """
        parts = command.split()
        
        # Default to current artifact if no number specified
        if len(parts) == 1:
            draft_num = self.current_artifact_number
        elif len(parts) == 2:
            try:
                draft_num = int(parts[1])
            except ValueError:
                print_text("❌ Draft number must be an integer", style="red")
                return False
        else:
            print_text("❌ Usage: /send [draft-number] (or just /send for current)", style="yellow")
            return False
        
        if draft_num not in self.artifacts:
            print_text(f"❌ Draft #{draft_num} not found", style="red")
            print_text(f"   Available drafts: {list(self.artifacts.keys())}", style="dim")
            return False
        
        # Get the draft to send
        draft_to_send = self.artifacts[draft_num]
        
        # Safety confirmation
        print()
        print_text(f"⚠️  Ready to send Draft #{draft_num}", style="bold yellow")
        print_text(f"Subject: {draft['inbound_subject']}", style="yellow")
        print_text(f"\nType the first 5 characters of the subject to confirm: '{draft['safety_string']}'", style="yellow")
        print_text(f"Or type 'cancel' (or press Enter) to abort", style="dim")
        
        confirmation = input("\nConfirm: ").strip()
        
        if not confirmation or confirmation.lower() == 'cancel':
            print_text("\n↩️  Send cancelled\n", style="cyan")
            return False
        
        if confirmation != draft['safety_string']:
            print_text("\n❌ Confirmation failed\n", style="red")
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
            return False
        
        sender = GmailSender(draft['workspace'], gmail_dbs[0].database_id)
        success = await sender.send_reply(
            thread_id=draft['thread_id'],
            message_id=draft['message_id'],
            subject=draft['draft_subject'],
            body_text=draft_to_send
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
                    "body": draft_to_send,
                    "tone": "professional",
                    "length": len(draft_to_send.split())
                },
                "metadata": {
                    "workspace": draft['workspace'],
                    "ai_model": draft.get('ai_model', 'unknown'),
                    "timestamp": now_utc().isoformat()
                }
            }
            self.learning_system.save_successful_response(pattern)
            
            print()
            print_text("↩️  Returning to draft list...", style="cyan")
            print()
            return True
        else:
            print_text("❌ Failed to send\n", style="red")
            return False
