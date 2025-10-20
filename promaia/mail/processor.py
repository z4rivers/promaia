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
            'inbound_to': thread.get('to', ''),
            'inbound_cc': thread.get('cc', ''),
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
    
    async def refresh_drafts(self, workspaces: List[str], days_back: int = 7) -> int:
        """
        Refresh existing drafts by rebuilding context, thread, and replies.
        
        Only refreshes drafts with status 'pending', 'unsure', or 'skipped'.
        Respects 'sent' and 'archived' statuses (does not touch them).
        
        Args:
            workspaces: List of workspace names
            days_back: Number of days to look back for drafts to refresh
            
        Returns:
            Number of drafts refreshed
        """
        total_refreshed = 0
        
        for workspace in workspaces:
            logger.info(f"🔄 Refreshing drafts for workspace: {workspace}")
            
            try:
                refreshed_count = await self._refresh_workspace_drafts(workspace, days_back)
                total_refreshed += refreshed_count
                logger.info(f"✅ Refreshed {refreshed_count} draft(s) for {workspace}")
                
            except Exception as e:
                logger.error(f"❌ Failed to refresh drafts for workspace {workspace}: {e}")
                continue
        
        logger.info(f"🎉 Total drafts refreshed: {total_refreshed}")
        return total_refreshed
    
    async def _refresh_workspace_drafts(self, workspace: str, days_back: int) -> int:
        """Refresh drafts for a single workspace."""
        from datetime import datetime, timedelta, timezone
        
        # Get drafts that need refreshing
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_back)
        
        # Query drafts with status in ('pending', 'unsure', 'skipped') within date range
        drafts = self.draft_manager.get_refreshable_drafts(
            workspace, 
            cutoff_date.isoformat(),
            statuses=['pending', 'unsure', 'skipped']
        )
        
        if not drafts:
            logger.info(f"No drafts to refresh for {workspace}")
            return 0
        
        logger.info(f"Found {len(drafts)} draft(s) to refresh")
        
        # Group drafts by Gmail database for efficient processing
        drafts_by_db = {}
        for draft in drafts:
            # Extract database info from draft
            # We'll use the workspace to find the right Gmail connector
            db_key = workspace  # Simplified - could be more sophisticated
            if db_key not in drafts_by_db:
                drafts_by_db[db_key] = []
            drafts_by_db[db_key].append(draft)
        
        refreshed_count = 0
        
        # Process each draft
        for draft in drafts:
            try:
                refreshed = await self._refresh_single_draft(draft, workspace)
                if refreshed:
                    refreshed_count += 1
                
                # Small delay to avoid overwhelming API
                await asyncio.sleep(0.5)
                
            except Exception as e:
                logger.error(f"❌ Failed to refresh draft {draft.get('draft_id')}: {e}")
                continue
        
        return refreshed_count
    
    async def _refresh_single_draft(self, draft: Dict[str, Any], workspace: str) -> bool:
        """
        Refresh a single draft by re-fetching thread and regenerating response.
        
        Returns:
            True if draft was refreshed, False otherwise
        """
        from promaia.connectors.gmail_connector import GmailConnector
        from promaia.config.databases import get_database_manager
        
        draft_id = draft.get('draft_id')
        thread_id = draft.get('thread_id')
        subject = draft.get('inbound_subject', 'No Subject')
        
        logger.info(f"Refreshing: {subject}")
        
        # Get Gmail databases for this workspace
        db_manager = get_database_manager()
        gmail_databases = [
            db for db in db_manager.get_workspace_databases(workspace)
            if db.source_type == "gmail"
        ]
        
        if not gmail_databases:
            logger.warning(f"⚠️  No Gmail databases found for workspace {workspace}")
            return False
        
        # Use first Gmail database (in most cases there's only one per workspace)
        gmail_db = gmail_databases[0]
        
        # Create connector with full_thread mode
        connector = GmailConnector({
            "database_id": gmail_db.database_id,
            "workspace": workspace,
            "gmail_content_mode": "full_thread"
        })
        
        await connector.connect()
        
        # Fetch fresh thread data from Gmail
        try:
            # Get the thread by ID
            service = connector.service
            thread_data = service.users().threads().get(
                userId='me', 
                id=thread_id,
                format='full'
            ).execute()
            
            # Process thread data using connector's method
            thread = connector._process_thread_data(thread_data)
            
            if not thread:
                logger.warning(f"⚠️  Could not fetch thread {thread_id}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Failed to fetch thread from Gmail: {e}")
            return False
        
        # Re-classify
        logger.debug("  → Re-classifying...")
        classification = await self.classifier.classify(thread)
        
        logger.info(
            f"  → Classification: "
            f"pertains={classification['pertains_to_me']}, "
            f"spam={classification['is_spam']}, "
            f"addressed_to_user={classification.get('addressed_to_user', 'unknown')}, "
            f"requires_response={classification['requires_response']}"
        )
        
        # Determine new status
        new_status = self.classifier.get_draft_status(classification)
        
        # Check if we should generate a draft
        if not self.classifier.should_generate_draft(classification):
            logger.info(f"  → Updating to skipped (no response needed)")
            # Update to skipped status
            self.draft_manager.update_draft_refresh(
                draft_id=draft_id,
                status=new_status,
                classification=classification,
                thread=thread,
                draft_body='n/a',
                response_context=None,
                system_prompt=None,
                ai_model=None
            )
            logger.info(f"  ⏭️  Draft updated to skipped: {draft_id}")
            return True
        
        # Rebuild context
        logger.debug("  → Rebuilding context...")
        context = await self.context_builder.build_context(thread, workspace)
        logger.info(f"  → Found {context.total_sources} relevant sources")
        
        # Regenerate response
        logger.debug("  → Regenerating response...")
        response = await self.response_generator.generate_response(thread, context)
        logger.info(f"  → Generated {len(response['body'].split())} word response")
        
        # Update draft
        logger.debug("  → Updating draft...")
        status_emoji = "🤷‍♀️" if new_status == "unsure" else "✅"
        logger.info(f"  {status_emoji} Draft status: {new_status}")
        
        self.draft_manager.update_draft_refresh(
            draft_id=draft_id,
            status=new_status,
            classification=classification,
            thread=thread,
            draft_body=response['body'],
            draft_subject=response['subject'],
            response_context=self.context_builder.serialize_context_for_storage(context),
            system_prompt=response.get('prompt'),
            ai_model=response['model']
        )
        
        logger.info(f"  ✅ Draft refreshed: {draft_id}")
        return True

