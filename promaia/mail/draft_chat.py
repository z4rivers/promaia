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
from promaia.mail.context_builder import ResponseContext, ResponseContextBuilder
from promaia.mail.thread_formatter import format_thread_for_display
from promaia.utils.display import print_text, print_separator
from promaia.utils.timezone_utils import to_local, get_local_timezone_name, now_utc
from promaia.connectors.gmail_connector import GmailConnector
from promaia.config.databases import get_database_manager


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
        self.learning_system = EmailResponseLearningSystem(workspace=workspace)
        self.context_builder = ResponseContextBuilder()
        
        # Artifacts: draft_number -> draft_text
        self.artifacts = {}
        self.current_artifact_number = 0
        
        # Context cache (for skipped drafts that load context on-demand)
        self.cached_context = None
        
        # Load existing version and history
        self._load_draft_history()
    
    def _load_draft_history(self):
        """Load draft version and history from database."""
        import json
        draft = self.draft_manager.get_draft(self.draft_id)
        
        if not draft:
            return
        
        # Load version number
        self.current_artifact_number = draft.get('version', 1)
        
        # Try to load draft history from a JSON field (if it exists)
        draft_history_str = draft.get('draft_history')
        if draft_history_str:
            try:
                history = json.loads(draft_history_str)
                self.artifacts = {int(k): v for k, v in history.items()}
            except:
                # If no history field, just use current draft as artifact 1
                self.artifacts = {self.current_artifact_number: draft.get('draft_body', '')}
        else:
            # No history saved, use current draft
            self.artifacts = {self.current_artifact_number: draft.get('draft_body', '')}
    
    def _save_draft_history(self):
        """Save draft history to database."""
        import json
        import sqlite3
        
        history_json = json.dumps(self.artifacts)
        
        try:
            with sqlite3.connect(self.draft_manager.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE email_drafts SET draft_history = ? WHERE draft_id = ?",
                    (history_json, self.draft_id)
                )
                conn.commit()
        except Exception as e:
            logger.warning(f"Could not save draft history: {e}")
    
    async def _load_message_context(self):
        """Load context for the email thread on-demand (for skipped drafts)."""
        print_text("\n🔍 Loading message context...", style="cyan")
        
        draft = self.draft_manager.get_draft(self.draft_id)
        if not draft:
            print_text("❌ Draft not found", style="red")
            return
        
        # Build email thread dict for context builder
        thread = {
            'thread_id': draft.get('thread_id'),
            'subject': draft.get('inbound_subject'),
            'body': draft.get('inbound_body'),
            'conversation_body': draft.get('thread_context', ''),
            'from': draft.get('inbound_from'),
            'date': draft.get('inbound_date'),
            'message_count': draft.get('message_count', 1)
        }
        
        # Build context
        context = await self.context_builder.build_context(thread, self.workspace)
        self.cached_context = context
        
        # Update draft in DB with context
        import json
        context_json = self.context_builder.serialize_context_for_storage(context)
        
        try:
            import sqlite3
            with sqlite3.connect(self.draft_manager.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE email_drafts SET response_context = ? WHERE draft_id = ?",
                    (context_json, self.draft_id)
                )
                conn.commit()
        except Exception as e:
            logger.warning(f"Could not save context: {e}")
        
        print_text(f"✅ Loaded {context.total_sources} sources from your knowledge base\n", style="green")
        
        # Display context summary
        if context.relevant_docs:
            print_text("📚 Top sources:", style="dim")
            for i, doc in enumerate(context.relevant_docs[:5], 1):
                print_text(f"  {i}. {doc.get('title', 'Untitled')} ({doc.get('database', 'unknown')})", style="dim")
            print()
    
    async def _refetch_full_thread_if_needed(self, draft: Dict[str, Any]) -> Dict[str, Any]:
        """If inbound_body is just a summary, refetch the full thread."""
        inbound_body = draft.get('inbound_body', '')
        if "Showing latest message only" not in inbound_body:
            return draft

        print_text("\n🔄 Detected summarized thread, fetching full conversation...", style="cyan")
        
        try:
            workspace = draft.get('workspace')
            thread_id = draft.get('thread_id')
            
            if not workspace or not thread_id:
                print_text("⚠️  Missing workspace or thread_id, cannot refetch.", style="yellow")
                return draft

            db_manager = get_database_manager()
            gmail_dbs = [
                db for db in db_manager.get_workspace_databases(workspace)
                if db.source_type == "gmail"
            ]
            
            if not gmail_dbs:
                print_text(f"⚠️  No Gmail database found for workspace {workspace}.", style="yellow")
                return draft

            connector = GmailConnector({
                "database_id": gmail_dbs[0].database_id,
                "workspace": workspace,
                "gmail_content_mode": "full_thread"
            })
            await connector.connect()
            
            full_thread_data = await connector.get_page_content(page_id=f"thread_{thread_id}")
            
            if full_thread_data and 'conversation_body' in full_thread_data:
                new_body = full_thread_data['conversation_body']
                draft['inbound_body'] = new_body
                
                # Update in database so we don't refetch next time
                self.draft_manager.update_inbound_body(self.draft_id, new_body)
                print_text("✅ Full thread loaded.", style="green")
            else:
                print_text("⚠️  Failed to fetch full thread.", style="yellow")

        except Exception as e:
            logger.error(f"Failed to refetch full thread: {e}")
            print_text(f"❌ Error fetching full thread: {e}", style="red")
            
        return draft

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
        artifact = [
            f"Draft #{draft_number}",
            "─────────────────────────────────────────────────────────────────",
            "",
            draft_text,
            "",
            "─────────────────────────────────────────────────────────────────"
        ]
        
        return '\n'.join(artifact)
    
    async def run_chat_loop(self):
        """
        Main chat loop for refining drafts.
        
        Supports commands:
        - /send [draft-number] - Send specified draft
        - /q - Quit to review queue
        - /archive or /a - Archive email (clear from queue)
        - Regular chat to refine the draft
        """
        try:
            # Load current draft
            draft = self.draft_manager.get_draft(self.draft_id)
            
            if not draft:
                print_text(f"❌ Draft {self.draft_id} not found", style="red")
                return

            # If the draft only has a summary, fetch the full thread content
            draft = await self._refetch_full_thread_if_needed(draft)
            
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
            
            # Display full email thread with copy-friendly formatting (naturally scrolls to bottom)
            print()
            print_separator()
            
            message_count = draft.get('message_count', 1)
            thread_display = format_thread_for_display(
                conversation_body=cleaned_body,
                message_count=message_count,
                from_addr=draft['inbound_from'],
                subject=draft['inbound_subject'],
                received_str=received_str,
                use_colors=True
            )
            
            print(thread_display)
            print_separator()
            
            if message_count > 1:
                print()
                print_text("📜 Tip: Scroll up ↑ to see earlier messages in the thread", style="dim")
            print()
            
            # Check if response is needed
            draft_status = draft.get('status', 'pending')
            draft_body = draft.get('draft_body', '')
            
            if draft_status == 'skipped':
                # Skipped draft - show AI reasoning and allow user to override
                print_text("⏭️  SKIPPED - No response needed", style="bold yellow")
                print()
                print_text("AI Assessment:", style="dim")
                if draft.get('classification_reasoning'):
                    print_text(f"  {draft.get('classification_reasoning')}", style="dim")
                print()
                print_text("💬 Want to reply anyway? Just start chatting to create a draft.", style="cyan")
                print_text("   Use /mc to load context from your knowledge base first.", style="cyan")
                print()
                print_text("Commands:", style="dim")
                print_text("   /mc - Load message context (recommended before replying)", style="dim")
                print_text("   /archive or /a - Archive this email (🗄️)", style="dim")
                print_text("   /q - Return to draft list", style="dim")
            elif draft_body and draft_body != 'n/a':
                # Normal draft with AI-generated response
                # Display all existing artifacts (version history)
                if not self.artifacts:
                    # First time, initialize with current draft
                    self.current_artifact_number = 1
                    self.artifacts[1] = draft_body
                
                # Display all artifacts in order
                for artifact_num in sorted(self.artifacts.keys()):
                    print(self.render_artifact(artifact_num, self.artifacts[artifact_num]))
                    print()
                
                print_text("💬 Chat to refine the draft, or use commands:", style="dim")
                print_text("   /send [number] - Send draft (e.g., /send 1)", style="dim")
                print_text("   /archive or /a - Archive this email (🗄️)", style="dim")
                print_text("   /q - Return to draft list", style="dim")
            else:
                # Edge case: draft exists but no body (shouldn't happen normally)
                print_text("⚠️  No draft available", style="yellow")
                print()
                print_text("Commands:", style="dim")
                print_text("   /archive or /a - Archive this email (🗄️)", style="dim")
                print_text("   /q - Return to draft list", style="dim")
            
            print()
            
            # Chat loop
            while True:
                try:
                    user_input = input("💬 You: ").strip()
                    # Remove any carriage returns or other control characters
                    user_input = user_input.replace('\r', '').replace('\n', ' ').strip()
                    
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
                        
                        elif cmd in ['/mc', '/messagecontext']:
                            # Load message context on-demand (for skipped drafts)
                            await self._load_message_context()
                            continue
                        
                        elif cmd in ['/archive', '/a']:
                            # Archive: clear from queue with that satisfying feeling
                            self.draft_manager.update_draft_status(self.draft_id, 'archived')
                            print_text("\n🗄️  Archived - cleared from your queue\n", style="green")
                            break
                        
                        else:
                            print_text(f"❌ Unknown command: {user_input}", style="red")
                            print_text("Available: /send [number], /mc, /archive, /q", style="dim")
                            continue
                    
                    # Check if this is a skipped draft and user wants to reply
                    if draft_status == 'skipped':
                        print_text("🔄 Converting skipped draft to pending...", style="cyan")
                        # Update status to pending
                        self.draft_manager.update_draft_status(self.draft_id, 'pending')
                        draft_status = 'pending'
                        
                        # If no context loaded yet, warn user
                        if not self.cached_context and not draft.get('response_context'):
                            print_text("💡 Tip: Use /mc to load context from your knowledge base first", style="yellow")
                    
                    # Check if we can generate a draft
                    if not draft_body or draft_body == 'n/a':
                        # First draft for a skipped email - generate from scratch
                        print_text("🤔 Generating draft based on your message...", style="cyan")
                        
                        # Get user email from workspace gmail database
                        user_email = None
                        try:
                            from promaia.config.databases import get_database_manager
                            db_manager = get_database_manager()
                            gmail_databases = [
                                db for db in db_manager.get_workspace_databases(self.workspace)
                                if db.source_type == "gmail"
                            ]
                            if gmail_databases:
                                user_email = gmail_databases[0].database_id
                        except Exception as e:
                            logger.debug(f"Could not get user email from workspace: {e}")
                        
                        # Get context - try cached first, then stored, then empty
                        context = None
                        if self.cached_context:
                            context = self.cached_context
                        elif draft.get('response_context'):
                            # Deserialize stored context
                            context = self.context_builder.deserialize_context_from_storage(
                                draft['response_context'],
                                thread_history=draft.get('thread_context', '')
                            )
                        
                        # Fallback to empty context if deserialization failed or no context available
                        if context is None:
                            context = ResponseContext(
                                thread_history=draft.get('thread_context', ''),
                                relevant_docs=[],
                                relevant_docs_text="",
                                workspace=self.workspace,
                                total_sources=0
                            )
                        
                        # Generate initial draft
                        # Note: user_input is incorporated as feedback via refine_response
                        response = await self.response_generator.refine_response(
                            current_draft="",  # No existing draft
                            user_feedback=f"Generate a reply. User guidance: {user_input}",
                            email_thread={
                                'from': draft['inbound_from'],
                                'subject': draft['inbound_subject'],
                                'date': draft['inbound_date'],
                                'body': draft['inbound_body'],
                                'conversation_body': draft.get('thread_context', '')
                            },
                            context=context,
                            user_email=user_email,
                            workspace=self.workspace
                        )
                        refined_draft = response
                    else:
                        # Refine existing draft
                        print_text("🤔 Refining draft...", style="cyan")
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
                    
                    # Save draft history
                    self._save_draft_history()
                    
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
            
            # Get user email from workspace gmail database
            user_email = None
            try:
                from promaia.config.databases import get_database_manager
                db_manager = get_database_manager()
                gmail_databases = [
                    db for db in db_manager.get_workspace_databases(self.workspace)
                    if db.source_type == "gmail"
                ]
                if gmail_databases:
                    user_email = gmail_databases[0].database_id
            except Exception as e:
                logger.debug(f"Could not get user email from workspace: {e}")
            
            # Get context - try cached first, then stored, then empty
            context = None
            if self.cached_context:
                context = self.cached_context
            elif draft.get('response_context'):
                # Deserialize stored context
                context = self.context_builder.deserialize_context_from_storage(
                    draft['response_context'],
                    thread_history=draft.get('thread_context', '')
                )
            
            # Fallback to empty context if deserialization failed or no context available
            if context is None:
                context = ResponseContext(
                    thread_history=draft.get('thread_context', ''),
                    relevant_docs=[],
                    relevant_docs_text="",
                    workspace=self.workspace,
                    total_sources=0
                )
            
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
                context=context,
                user_email=user_email,
                workspace=self.workspace
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
        
        # Get user email from workspace gmail database
        user_email = None
        try:
            from promaia.config.databases import get_database_manager
            db_manager = get_database_manager()
            gmail_databases = [
                db for db in db_manager.get_workspace_databases(self.workspace)
                if db.source_type == "gmail"
            ]
            if gmail_databases:
                user_email = gmail_databases[0].database_id
        except Exception as e:
            logger.debug(f"Could not get user email from workspace: {e}")
        
        # Show recipient selector
        from promaia.mail.recipient_selector import RecipientSelector
        
        selector = RecipientSelector(
            from_addr=draft.get('inbound_from', ''),
            to_addr=draft.get('inbound_to', ''),
            cc_addr=draft.get('inbound_cc', ''),
            thread_context=draft.get('thread_context', ''),
            user_email=user_email
        )
        
        print_text("\n📧 Select recipients for this email...", style="cyan")
        confirmed, recipients = await selector.run()
        
        if not confirmed:
            print_text("\n↩️  Send cancelled\n", style="cyan")
            return False
        
        if not recipients:
            print_text("\n❌ No recipients selected\n", style="red")
            return False
        
        print_text(f"\n✅ Sending to: {', '.join(recipients)}", style="green")
        
        # Format the draft to remove hard line breaks before sending
        draft_to_send = self.response_generator._format_email_body(draft_to_send)
        
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
            body_text=draft_to_send,
            recipients=recipients
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
