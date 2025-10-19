"""
Draft Chat Interface - Specialized chat for refining email drafts.

Reuses promaia/chat/interface.py infrastructure with draft-specific features:
- Numbered artifacts (like Claude)
- /send [draft-number] command
- Context awareness of the email thread
"""
import asyncio
import logging
from typing import Dict, Any, Optional
from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.keys import Keys
from prompt_toolkit.styles import Style

from promaia.mail.draft_manager import DraftManager
from promaia.mail.gmail_sender import GmailSender
from promaia.mail.response_generator import ResponseGenerator
from promaia.mail.learning_system import EmailResponseLearningSystem
from promaia.mail.context_builder import ResponseContext
from promaia.utils.display import print_text, print_separator

logger = logging.getLogger(__name__)


class DraftChatInterface:
    """
    Specialized chat interface for refining email drafts.
    Supports artifacts and draft-specific commands.
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
        
        # Conversation history for this draft
        self.conversation_history = []
        
        # Set up prompt_toolkit
        self.bindings = self._setup_keybindings()
        self.session = PromptSession(
            history=FileHistory(f'.mail_draft_history_{draft_id}'),
            multiline=True,
            key_bindings=self.bindings
        )
        
        self.style = Style.from_dict({
            'prompt': 'ansicyan bold',
            'input': 'ansiwhite',
        })
    
    def _setup_keybindings(self) -> KeyBindings:
        """Set up key bindings for chat."""
        bindings = KeyBindings()
        
        @bindings.add('enter')
        def _(event):
            """Enter key sends the message/command."""
            event.app.exit(result=event.app.current_buffer.text)
        
        @bindings.add('c-j')
        def _(event):
            """Ctrl+J adds a new line (Shift+Enter on many terminals)."""
            event.current_buffer.insert_text('\n')
        
        return bindings
    
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
            if len(line) <= 80:
                wrapped_lines.append(f"│ {line:<78} │")
            else:
                # Wrap long lines
                while len(line) > 80:
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
        - Regular chat to refine the draft
        """
        try:
            # Load current draft
            draft = self.draft_manager.get_draft(self.draft_id)
            
            if not draft:
                print_text(f"❌ Draft {self.draft_id} not found", style="red")
                return
            
            # Display inbound message
            print()
            print_separator()
            print_text("===== Inbound Message =====", style="bold cyan")
            print(f"From: {draft['inbound_from']}")
            print(f"Subject: {draft['inbound_subject']}")
            print(f"Date: {draft['inbound_date']}")
            print()
            print(draft['inbound_body'])
            print()
            
            # Display current draft as artifact #1
            self.current_artifact_number = 1
            self.artifacts[1] = draft['draft_body']
            print(self.render_artifact(1, draft['draft_body']))
            print()
            
            print_text("💬 Chat to refine the draft, or type a command:", style="dim")
            print_text("   /send [number] - Send draft", style="dim")
            print_text("   /q - Return to review queue", style="dim")
            print()
            
            # Chat loop
            while True:
                try:
                    user_input = await self.session.prompt_async(
                        "You: ",
                        style=self.style
                    )
                    
                    if not user_input.strip():
                        continue
                    
                    # Handle commands
                    if user_input.startswith('/'):
                        if user_input.strip() == '/q':
                            print_text("\n↩️  Returning to review queue...\n", style="cyan")
                            break
                        
                        elif user_input.startswith('/send'):
                            should_exit = await self._handle_send_command(user_input, draft)
                            if should_exit:
                                break
                            continue
                        
                        else:
                            print_text(f"❌ Unknown command: {user_input}", style="red")
                            print_text("Available commands: /send [number], /q", style="dim")
                            continue
                    
                    # Regular chat - refine the draft
                    print_text("\n🤔 Refining draft...", style="cyan")
                    
                    # Generate refined draft
                    refined_draft = await self._refine_draft(draft, user_input)
                    
                    # Increment artifact number
                    self.current_artifact_number += 1
                    self.artifacts[self.current_artifact_number] = refined_draft
                    
                    # Display new artifact
                    print()
                    print(self.render_artifact(self.current_artifact_number, refined_draft))
                    print()
                    
                    # Update draft in DB
                    self.draft_manager.update_draft_body(
                        self.draft_id,
                        refined_draft,
                        version=self.current_artifact_number
                    )
                    
                    print_text(f"✅ Updated to Draft #{self.current_artifact_number}\n", style="green")
                    
                except KeyboardInterrupt:
                    print_text("\n\n↩️  Returning to review queue...\n", style="cyan")
                    break
                except EOFError:
                    print_text("\n\n↩️  Returning to review queue...\n", style="cyan")
                    break
        
        except Exception as e:
            logger.error(f"❌ Error in draft chat: {e}")
            print_text(f"\n❌ Error: {e}\n", style="red")
    
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
            
            # Build email thread data for context
            email_thread = {
                'from': draft['inbound_from'],
                'subject': draft['inbound_subject'],
                'date': draft['inbound_date'],
                'body': draft['inbound_body'],
                'conversation_body': draft.get('thread_context', '')
            }
            
            # Create minimal context (we don't need to re-search)
            context = ResponseContext(
                thread_history=draft.get('thread_context', ''),
                relevant_docs=[],
                relevant_docs_text="(Using cached context from original generation)",
                workspace=self.workspace,
                total_sources=0
            )
            
            # Refine using response generator
            refined = await self.response_generator.refine_response(
                current_draft=current_draft,
                user_feedback=user_feedback,
                email_thread=email_thread,
                context=context
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
        if len(parts) != 2:
            print_text("❌ Usage: /send [draft-number]", style="yellow")
            print_text(f"   Example: /send {self.current_artifact_number}", style="dim")
            return False
        
        try:
            draft_num = int(parts[1])
        except ValueError:
            print_text("❌ Draft number must be an integer", style="red")
            return False
        
        if draft_num not in self.artifacts:
            print_text(f"❌ Draft #{draft_num} not found", style="red")
            print_text(f"   Available drafts: {list(self.artifacts.keys())}", style="dim")
            return False
        
        # Safety confirmation
        safety_string = draft['safety_string']
        print()
        print_text(f"⚠️  Ready to send Draft #{draft_num}", style="bold yellow")
        print_text(f"Safety check: Type the first 5 characters of the subject to confirm", style="yellow")
        print_text(f"Subject: {draft['inbound_subject']}", style="dim")
        print()
        
        confirmation = input("Confirm: ").strip()
        
        if confirmation != safety_string:
            print_text("❌ Confirmation failed. Email not sent.\n", style="red")
            return False
        
        # Send the email
        print_text(f"\n📤 Sending Draft #{draft_num}...", style="cyan")
        
        # Get email from database for workspace
        gmail_email = draft.get('inbound_from')  # We'll need to get the actual sending email
        # For now, use the workspace's Gmail database ID
        from promaia.config.databases import get_database_manager
        db_manager = get_database_manager()
        gmail_dbs = [
            db for db in db_manager.get_workspace_databases(self.workspace)
            if db.source_type == "gmail"
        ]
        
        if not gmail_dbs:
            print_text("❌ No Gmail database found for this workspace", style="red")
            return False
        
        gmail_email = gmail_dbs[0].database_id  # Use first Gmail database
        
        sender = GmailSender(self.workspace, gmail_email)
        success = await sender.send_reply(
            thread_id=draft['thread_id'],
            message_id=draft['message_id'],
            subject=draft['draft_subject'],
            body_text=self.artifacts[draft_num]
        )
        
        if success:
            print_text("\n✅ Email sent successfully!\n", style="bold green")
            
            # Mark as sent
            self.draft_manager.mark_sent(self.draft_id)
            
            # Save to learning system
            await self._save_to_learning_system(draft, self.artifacts[draft_num])
            
            print_text("Returning to review queue...\n", style="dim")
            return True  # Exit chat
        else:
            print_text("\n❌ Failed to send email\n", style="red")
            return False
    
    async def _save_to_learning_system(self, draft: Dict[str, Any], sent_body: str):
        """Save successful response to learning system."""
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
                    "body": sent_body,
                    "tone": "professional",
                    "length": len(sent_body.split())
                },
                "metadata": {
                    "workspace": self.workspace,
                    "sent_time": draft.get('sent_time', ''),
                    "was_successful": True,
                    "notes": "Successfully sent via maia mail"
                }
            }
            
            self.learning_system.save_successful_response(pattern)
            logger.info("✅ Saved response pattern to learning system")
            
        except Exception as e:
            logger.warning(f"⚠️  Could not save to learning system: {e}")

