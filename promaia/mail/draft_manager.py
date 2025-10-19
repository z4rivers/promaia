"""
Draft Manager - SQLite operations for email drafts.

Manages the email_drafts table in hybrid_metadata.db with CRUD operations.
"""
import sqlite3
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from pathlib import Path

logger = logging.getLogger(__name__)


class DraftManager:
    """SQLite operations for email drafts."""
    
    def __init__(self, db_path: str = "data/hybrid_metadata.db"):
        self.db_path = db_path
        self._ensure_table()
    
    def _ensure_table(self):
        """Create email_drafts table if it doesn't exist."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS email_drafts (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        draft_id TEXT UNIQUE NOT NULL,
                        workspace TEXT NOT NULL,
                        thread_id TEXT NOT NULL,
                        message_id TEXT NOT NULL,
                        inbound_subject TEXT,
                        inbound_from TEXT,
                        inbound_snippet TEXT,
                        inbound_date TEXT,
                        inbound_body TEXT,
                        
                        -- Classification results
                        pertains_to_me BOOLEAN DEFAULT TRUE,
                        is_spam BOOLEAN DEFAULT FALSE,
                        requires_response BOOLEAN DEFAULT TRUE,
                        classification_reasoning TEXT,
                        
                        -- Draft response
                        draft_subject TEXT,
                        draft_body TEXT,
                        draft_body_html TEXT,
                        
                        -- Context used for generation
                        response_context TEXT,
                        system_prompt TEXT,
                        ai_model TEXT,
                        
                        -- Draft versioning and chat
                        draft_number INTEGER DEFAULT 1,
                        chat_session_id TEXT,
                        previous_draft_id TEXT,
                        version INTEGER DEFAULT 1,
                        draft_history TEXT,  -- JSON array of all draft versions
                        
                        -- Status tracking
                        status TEXT DEFAULT 'pending',
                        created_time TEXT NOT NULL,
                        reviewed_time TEXT,
                        sent_time TEXT,
                        
                        -- Safety mechanism
                        safety_string TEXT,
                        
                        -- Thread context
                        thread_context TEXT,
                        message_count INTEGER DEFAULT 1,
                        
                        UNIQUE(draft_id)
                    )
                """)
                
                # Create indexes for common queries
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_drafts_workspace_status 
                    ON email_drafts(workspace, status)
                """)
                
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_drafts_thread_id 
                    ON email_drafts(thread_id)
                """)
                
                conn.commit()
                logger.info("✅ Email drafts table initialized")
                
        except Exception as e:
            logger.error(f"❌ Failed to initialize email_drafts table: {e}")
            raise
    
    def save_draft(self, draft: Dict[str, Any]) -> str:
        """
        Save a new draft, return draft_id.
        
        Args:
            draft: Dictionary containing all draft fields
            
        Returns:
            draft_id of the saved draft
        """
        draft_id = draft.get('draft_id') or str(uuid.uuid4())
        
        # Generate safety string (first 5 chars of subject)
        subject = draft.get('inbound_subject', '')
        safety_string = subject[:5] if len(subject) >= 5 else subject
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    INSERT INTO email_drafts (
                        draft_id, workspace, thread_id, message_id,
                        inbound_subject, inbound_from, inbound_snippet, inbound_date, inbound_body,
                        pertains_to_me, is_spam, requires_response, classification_reasoning,
                        draft_subject, draft_body, draft_body_html,
                        response_context, system_prompt, ai_model,
                        draft_number, chat_session_id, previous_draft_id, version,
                        status, created_time, safety_string, thread_context, message_count
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    draft_id,
                    draft.get('workspace'),
                    draft.get('thread_id'),
                    draft.get('message_id'),
                    draft.get('inbound_subject'),
                    draft.get('inbound_from'),
                    draft.get('inbound_snippet'),
                    draft.get('inbound_date'),
                    draft.get('inbound_body'),
                    draft.get('pertains_to_me', True),
                    draft.get('is_spam', False),
                    draft.get('requires_response', True),
                    draft.get('classification_reasoning'),
                    draft.get('draft_subject'),
                    draft.get('draft_body'),
                    draft.get('draft_body_html'),
                    json.dumps(draft.get('response_context', [])) if draft.get('response_context') else None,
                    draft.get('system_prompt'),
                    draft.get('ai_model'),
                    draft.get('draft_number', 1),
                    draft.get('chat_session_id'),
                    draft.get('previous_draft_id'),
                    draft.get('version', 1),
                    draft.get('status', 'pending'),
                    draft.get('created_time', datetime.now(timezone.utc).isoformat()),
                    safety_string,
                    draft.get('thread_context'),
                    draft.get('message_count', 1)
                ))
                
                conn.commit()
                logger.info(f"✅ Saved draft {draft_id}")
                return draft_id
                
        except Exception as e:
            logger.error(f"❌ Failed to save draft: {e}")
            raise
    
    def get_draft(self, draft_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific draft by ID."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                cursor.execute("SELECT * FROM email_drafts WHERE draft_id = ?", (draft_id,))
                row = cursor.fetchone()
                
                if row:
                    return dict(row)
                return None
                
        except Exception as e:
            logger.error(f"❌ Failed to get draft {draft_id}: {e}")
            return None
    
    def get_pending_drafts(self, workspace: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get drafts with status='pending'."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                if workspace:
                    cursor.execute(
                        "SELECT * FROM email_drafts WHERE status = 'pending' AND workspace = ? ORDER BY created_time DESC",
                        (workspace,)
                    )
                else:
                    cursor.execute(
                        "SELECT * FROM email_drafts WHERE status = 'pending' ORDER BY created_time DESC"
                    )
                
                rows = cursor.fetchall()
                return [dict(row) for row in rows]
                
        except Exception as e:
            logger.error(f"❌ Failed to get pending drafts: {e}")
            return []
    
    def get_drafts_for_workspace(self, workspace: str, include_resolved: bool = True) -> List[Dict[str, Any]]:
        """Get all drafts for a workspace, optionally including resolved ones."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                if include_resolved:
                    cursor.execute(
                        "SELECT * FROM email_drafts WHERE workspace = ? ORDER BY created_time DESC",
                        (workspace,)
                    )
                else:
                    cursor.execute(
                        "SELECT * FROM email_drafts WHERE workspace = ? AND status = 'pending' ORDER BY created_time DESC",
                        (workspace,)
                    )
                
                rows = cursor.fetchall()
                return [dict(row) for row in rows]
                
        except Exception as e:
            logger.error(f"❌ Failed to get drafts for workspace {workspace}: {e}")
            return []
    
    def update_draft_status(self, draft_id: str, status: str):
        """Update draft status."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute(
                    "UPDATE email_drafts SET status = ?, reviewed_time = ? WHERE draft_id = ?",
                    (status, datetime.now(timezone.utc).isoformat(), draft_id)
                )
                
                conn.commit()
                logger.info(f"✅ Updated draft {draft_id} status to {status}")
                
        except Exception as e:
            logger.error(f"❌ Failed to update draft status: {e}")
            raise
    
    def update_draft_body(self, draft_id: str, body: str, version: Optional[int] = None):
        """Update draft body (for refinements)."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                if version:
                    cursor.execute(
                        "UPDATE email_drafts SET draft_body = ?, version = ? WHERE draft_id = ?",
                        (body, version, draft_id)
                    )
                else:
                    cursor.execute(
                        "UPDATE email_drafts SET draft_body = ? WHERE draft_id = ?",
                        (body, draft_id)
                    )
                
                conn.commit()
                logger.info(f"✅ Updated draft {draft_id} body")
                
        except Exception as e:
            logger.error(f"❌ Failed to update draft body: {e}")
            raise
    
    def mark_sent(self, draft_id: str):
        """Mark draft as sent with timestamp."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute(
                    "UPDATE email_drafts SET status = 'sent', sent_time = ? WHERE draft_id = ?",
                    (datetime.now(timezone.utc).isoformat(), draft_id)
                )
                
                conn.commit()
                logger.info(f"✅ Marked draft {draft_id} as sent")
                
        except Exception as e:
            logger.error(f"❌ Failed to mark draft as sent: {e}")
            raise
    
    def thread_has_draft(self, thread_id: str, workspace: str) -> bool:
        """Check if a thread already has a draft."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute(
                    "SELECT COUNT(*) FROM email_drafts WHERE thread_id = ? AND workspace = ?",
                    (thread_id, workspace)
                )
                
                count = cursor.fetchone()[0]
                return count > 0
                
        except Exception as e:
            logger.error(f"❌ Failed to check for existing draft: {e}")
            return False
    
    def get_draft_count_by_status(self, workspace: Optional[str] = None) -> Dict[str, int]:
        """Get count of drafts by status."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                if workspace:
                    cursor.execute(
                        "SELECT status, COUNT(*) FROM email_drafts WHERE workspace = ? GROUP BY status",
                        (workspace,)
                    )
                else:
                    cursor.execute("SELECT status, COUNT(*) FROM email_drafts GROUP BY status")
                
                results = cursor.fetchall()
                return {row[0]: row[1] for row in results}
                
        except Exception as e:
            logger.error(f"❌ Failed to get draft counts: {e}")
            return {}

