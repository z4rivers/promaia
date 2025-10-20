"""
Email Processor - Main orchestrator for email processing pipeline.

Processes new emails through the complete workflow:
1. Sync recent emails from Gmail
2. Classify each thread
3. Build response context
4. Generate draft responses
5. Save to database for review
"""
import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any

from promaia.mail.draft_manager import DraftManager
from promaia.mail.classifier import EmailClassifier
from promaia.mail.context_builder import ResponseContextBuilder
from promaia.mail.response_generator import ResponseGenerator

logger = logging.getLogger(__name__)


class EmailProcessor:
    """Main orchestrator for email processing pipeline."""
    
    def __init__(self):
        """Initialize email processor."""
        self.draft_manager = DraftManager()
        self.classifier = EmailClassifier()
        self.context_builder = ResponseContextBuilder()
        self.response_generator = ResponseGenerator()
    
    async def process_new_emails(self, workspaces: List[str], hours_back: int = 2) -> int:
        """
        Process new emails for specified workspaces.
        
        Args:
            workspaces: List of workspace names
            hours_back: How many hours back to check for new emails
            
        Returns:
            Number of drafts generated
        """
        total_drafts = 0
        
        for workspace in workspaces:
            logger.info(f"📧 Processing emails for workspace: {workspace}")
            
            try:
                drafts_count = await self._process_workspace(workspace, hours_back)
                total_drafts += drafts_count
                logger.info(f"✅ Generated {drafts_count} draft(s) for {workspace}")
                
            except Exception as e:
                logger.error(f"❌ Failed to process workspace {workspace}: {e}")
                continue
        
        logger.info(f"🎉 Total drafts generated: {total_drafts}")
        return total_drafts
    
    async def _process_workspace(self, workspace: str, hours_back: int) -> int:
        """Process emails for a single workspace."""
        from promaia.config.databases import get_database_manager
        
        # Get Gmail databases for this workspace
        db_manager = get_database_manager()
        gmail_databases = [
            db for db in db_manager.get_workspace_databases(workspace)
            if db.source_type == "gmail"
        ]
        
        if not gmail_databases:
            logger.warning(f"⚠️  No Gmail databases found for workspace {workspace}")
            return 0
        
        total_drafts = 0
        
        for gmail_db in gmail_databases:
            try:
                drafts = await self._process_gmail_database(gmail_db, workspace, hours_back)
                total_drafts += drafts
            except Exception as e:
                logger.error(f"❌ Failed to process Gmail database {gmail_db.get_qualified_name()}: {e}")
                continue
        
        return total_drafts
    
    async def _process_gmail_database(self, db_config, workspace: str, hours_back: int) -> int:
        """Process a single Gmail database."""
        from promaia.connectors.gmail_connector import GmailConnector
        from promaia.connectors.base import DateRangeFilter
        
        logger.info(f"📬 Checking {db_config.get_qualified_name()} for new emails...")
        
        # Create connector with full_thread mode for maia mail
        # (Users need full context to review and refine draft responses)
        connector = GmailConnector({
            "database_id": db_config.database_id,
            "workspace": workspace,
            "gmail_content_mode": "full_thread"  # Get complete conversation history
        })
        
        await connector.connect()
        
        # Query recent emails (last N hours)
        start_date = datetime.now(timezone.utc) - timedelta(hours=hours_back)
        date_filter = DateRangeFilter(
            property_name="date",
            start_date=start_date
        )
        
        # Get recent threads
        threads = await connector.query_pages(
            date_filter=date_filter,
            limit=50  # Process max 50 threads per run
        )
        
        if not threads:
            logger.info("No new threads found")
            return 0
        
        # Filter out threads where the user sent the last message
        # We only want to process inbound messages that need responses
        inbound_threads = [t for t in threads if not t.get('last_message_from_user', False)]
        
        if len(inbound_threads) < len(threads):
            filtered_count = len(threads) - len(inbound_threads)
            logger.info(f"Filtered out {filtered_count} thread(s) where you sent the last message")
        
        if not inbound_threads:
            logger.info("No inbound threads found (all last messages were from you)")
            return 0
        
        logger.info(f"Found {len(inbound_threads)} inbound thread(s) to process")
        
        # Process each thread
        drafts_created = 0
        
        for thread in inbound_threads:
            try:
                # Check if we already have a draft for this thread
                thread_id = thread.get('thread_id')
                if self.draft_manager.thread_has_draft(thread_id, workspace):
                    logger.debug(f"Skipping thread {thread_id} - draft already exists")
                    continue
                
                # Process thread
                draft_created = await self._process_thread(thread, workspace, db_config.database_id)
                if draft_created:
                    drafts_created += 1
                
                # Small delay to avoid overwhelming API
                await asyncio.sleep(0.5)
                
            except Exception as e:
                logger.error(f"❌ Failed to process thread {thread.get('thread_id')}: {e}")
                continue
        
        return drafts_created
    
    async def _process_thread(self, thread: Dict[str, Any], workspace: str, email: str) -> bool:
        """
        Process a single email thread through the pipeline.
        
        Returns:
            True if draft was created, False otherwise
        """
        thread_id = thread.get('thread_id')
        subject = thread.get('subject', 'No Subject')
        
        logger.info(f"Processing: {subject}")
        
        # Step 1: Classify
        logger.debug("  → Classifying...")
        classification = await self.classifier.classify(thread)
        
        logger.info(
            f"  → Classification: "
            f"pertains={classification['pertains_to_me']}, "
            f"spam={classification['is_spam']}, "
            f"addressed_to_user={classification.get('addressed_to_user', 'unknown')}, "
            f"requires_response={classification['requires_response']}"
        )
        
        # Determine draft status
        draft_status = self.classifier.get_draft_status(classification)
        
        # Check if we should generate a draft
        if not self.classifier.should_generate_draft(classification):
            logger.info(f"  → No response needed - creating skipped draft for review")
            # Create a "skipped" draft (no AI generation, no context loading)
            # User can override by entering draft chat and using /mc to load context
            draft_data = {
                'workspace': workspace,
                'thread_id': thread_id,
                'message_id': thread.get('message_ids', [])[-1] if thread.get('message_ids') else thread_id,
                'inbound_subject': subject,
                'inbound_from': thread.get('from'),
                'inbound_snippet': thread.get('snippet', ''),
                'inbound_date': thread.get('date'),
                'inbound_body': thread.get('conversation_body', ''),
                'pertains_to_me': classification['pertains_to_me'],
                'is_spam': classification['is_spam'],
                'requires_response': classification['requires_response'],
                'classification_reasoning': classification['reasoning'],
                'draft_subject': f"Re: {subject}",
                'draft_body': 'n/a',  # No draft generated
                'response_context': None,  # No context loaded (user can load with /mc in chat)
                'system_prompt': None,
                'ai_model': None,
                'thread_context': thread.get('conversation_body', '')[:500],  # Store snippet
                'message_count': thread.get('message_count', 1),
                'status': draft_status,
                'addressed_to_user': classification.get('addressed_to_user', 'unknown')
            }
            
            draft_id = self.draft_manager.save_draft(draft_data)
            logger.info(f"  ⏭️  Skipped draft saved: {draft_id}")
            return True  # Count as created so it shows in review queue
        
        # Step 2: Build context (for both "pending" and "unsure")
        logger.debug("  → Building context...")
        context = await self.context_builder.build_context(thread, workspace)
        logger.info(f"  → Found {context.total_sources} relevant sources")
        
        # Step 3: Generate response (for both "pending" and "unsure")
        logger.debug("  → Generating response...")
        response = await self.response_generator.generate_response(thread, context)
        logger.info(f"  → Generated {len(response['body'].split())} word response")
        
        # Step 4: Save draft
        logger.debug("  → Saving draft...")
        status_emoji = "🤷‍♀️" if draft_status == "unsure" else "✅"
        logger.info(f"  {status_emoji} Draft status: {draft_status}")
        
        draft_data = {
            'workspace': workspace,
            'thread_id': thread_id,
            'message_id': thread.get('message_ids', [])[-1] if thread.get('message_ids') else thread_id,
            'inbound_subject': subject,
            'inbound_from': thread.get('from'),
            'inbound_snippet': thread.get('snippet', ''),
            'inbound_date': thread.get('date'),
            'inbound_body': thread.get('conversation_body', ''),
            'pertains_to_me': classification['pertains_to_me'],
            'is_spam': classification['is_spam'],
            'requires_response': classification['requires_response'],
            'classification_reasoning': classification['reasoning'],
            'draft_subject': response['subject'],
            'draft_body': response['body'],
            'response_context': self.context_builder.serialize_context_for_storage(context),
            'system_prompt': response.get('prompt'),
            'ai_model': response['model'],
            'thread_context': context.thread_history[:500],  # Store snippet
            'message_count': thread.get('message_count', 1),
            'status': draft_status,
            'addressed_to_user': classification.get('addressed_to_user', True)
        }
        
        draft_id = self.draft_manager.save_draft(draft_data)
        logger.info(f"  ✅ Draft saved: {draft_id}")
        
        return True

