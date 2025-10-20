"""
Draft Chat Interface - Thin wrapper around maia chat for email drafts.

Displays the email thread, then launches unified chat with DraftMode
for artifact-based draft composition.
"""
import logging
from typing import Dict, Any, Optional
from datetime import datetime

from promaia.mail.draft_manager import DraftManager
from promaia.utils.display import print_text, print_separator
from promaia.utils.timezone_utils import to_local, get_local_timezone_name, now_utc
from promaia.connectors.gmail_connector import GmailConnector
from promaia.config.databases import get_database_manager
from promaia.mail.thread_formatter import format_thread_for_display
from promaia.mail.context_builder import ResponseContext, ResponseContextBuilder

logger = logging.getLogger(__name__)


class DraftChatInterface:
    """
    Thin wrapper around maia chat for email drafts.
    
    Displays email thread, loads context, then launches unified chat
    with DraftMode for specialized email drafting behavior.
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
        self.context_builder = ResponseContextBuilder()
    
    def _get_user_email(self) -> Optional[str]:
        """Get user's email from workspace gmail database."""
        try:
            db_manager = get_database_manager()
            gmail_databases = [
                db for db in db_manager.get_workspace_databases(self.workspace)
                if db.source_type == "gmail"
            ]
            if gmail_databases:
                return gmail_databases[0].database_id
        except Exception as e:
            logger.debug(f"Could not get user email from workspace: {e}")
        return None
    
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
    
    async def _load_message_context(self, draft: Dict[str, Any]) -> Dict[str, list]:
        """
        Load context for the email thread.
        
        Returns message context formatted for chat (database_name -> pages).
        """
        print_text("\n🔍 Loading message context...", style="cyan")
        
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
        
        # Build context using dual vector search
        context = await self.context_builder.build_context(thread, self.workspace)
        
        print_text(f"✅ Loaded {context.total_sources} sources from your knowledge base\n", style="green")
        
        # Convert ResponseContext to the format expected by chat
        # (database_name -> list of page dicts)
        message_context = {}
        for doc in context.relevant_docs:
            db_name = doc.get('database', 'unknown')
            if db_name not in message_context:
                message_context[db_name] = []
            
            # Convert doc format to page format
            page = {
                'title': doc.get('title', 'Untitled'),
                'content': doc.get('content', ''),
                'metadata': doc.get('metadata', {}),
                'database': db_name,
            }
            message_context[db_name].append(page)
        
        return message_context
    
    async def run_chat_loop(self):
        """
        Main entry point - display email thread then launch unified chat with DraftMode.
        """
        try:
            # Load current draft
            draft = self.draft_manager.get_draft(self.draft_id)
            
            if not draft:
                print_text(f"❌ Draft {self.draft_id} not found", style="red")
                return

            # If the draft only has a summary, fetch the full thread content
            draft = await self._refetch_full_thread_if_needed(draft)
            
            # Get user email
            user_email = self._get_user_email()
            if not user_email:
                print_text("⚠️  Could not determine user email", style="yellow")
                user_email = "unknown@example.com"
            
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
            
            # Display full email thread
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
            
            # Load message context (vector search results)
            message_context = await self._load_message_context(draft)
            
            logger.info(f"Loaded message context: {len(message_context)} databases")
            
            # Check draft status
            draft_status = draft.get('status', 'pending')
            draft_body = draft.get('draft_body', '')
            
            if draft_status == 'skipped':
                # Skipped draft - show AI reasoning
                print_text("⏭️  SKIPPED - No response needed", style="bold yellow")
                print()
                print_text("AI Assessment:", style="dim")
                if draft.get('classification_reasoning'):
                    print_text(f"  {draft.get('classification_reasoning')}", style="dim")
                print()
                print_text("💬 Want to reply anyway? Just start chatting to create a draft.", style="cyan")
                print()
            
            # Create DraftMode
            from promaia.chat.modes import DraftMode
            
            mode = DraftMode(
                workspace=self.workspace,
                draft_id=self.draft_id,
                draft_data=draft,
                draft_manager=self.draft_manager,
                user_email=user_email
            )
            
            # If there's an existing draft, pre-populate as an artifact
            initial_messages = []
            if draft_body and draft_body != 'n/a':
                # Create an initial artifact with the existing draft
                initial_messages.append({
                    "role": "assistant",
                    "content": f"<artifact>{draft_body}</artifact>"
                })
            
            # Launch unified chat with DraftMode
            from promaia.chat.interface import chat
            
            logger.info(f"🚀 Launching unified chat with DraftMode")
            logger.info(f"   Workspace: {self.workspace}")
            logger.info(f"   Mode: {mode}")
            logger.info(f"   Message context: {len(message_context)} databases")
            logger.info(f"   Initial messages: {len(initial_messages) if initial_messages else 0}")
            
            # Note: chat() is not async, so we call it directly
            result = chat(
                workspace=self.workspace,
                mode=mode,
                natural_language_content=message_context,  # Pre-loaded context
                initial_messages=initial_messages,  # Pre-populate first draft
            )
            
            logger.info(f"✅ Chat returned: {result}")
        
        except KeyboardInterrupt:
            print_text("\n\n↩️  Returning to draft list...\n", style="cyan")
        except EOFError:
            print_text("\n\n↩️  Returning to draft list...\n", style="cyan")
        except Exception as e:
            logger.error(f"❌ Error in draft chat: {e}")
            print_text(f"\n❌ Error: {e}\n", style="red")
            import traceback
            traceback.print_exc()
