"""
Persistent caching system for CMS sync operations.
Tracks content hashes to skip unchanged pages between sync runs.

Now uses libSQL for centralized storage.
"""
import hashlib
import json
import time
import logging
from typing import Dict, Any, Optional
from pathlib import Path
import os

from promaia.storage.db_factory import get_db

logger = logging.getLogger(__name__)


class SyncCache:
    """
    Manages persistent cache for sync operations using libSQL.
    Stores content hashes to detect changes and avoid unnecessary processing.
    """

    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize the sync cache.

        Args:
            db_path: Deprecated parameter, kept for backward compatibility.
                    All data is now stored in libSQL.
        """
        self.db = get_db()
        self._ensure_table()
        logger.debug("SyncCache initialized with libSQL backend")

    def _ensure_table(self):
        """Ensure the page_cache table exists."""
        if not self.db.table_exists('page_cache'):
            self.db.execute("""
                CREATE TABLE IF NOT EXISTS page_cache (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    page_id TEXT UNIQUE NOT NULL,
                    content_hash TEXT NOT NULL,
                    last_edited_time TEXT,
                    last_synced_at REAL NOT NULL,
                    webflow_id TEXT
                )
            """)
            self.db.execute("""
                CREATE INDEX IF NOT EXISTS idx_page_cache_synced
                ON page_cache(last_synced_at)
            """)

    def compute_content_hash(self, page_data: Dict[str, Any]) -> str:
        """
        Compute a hash of the page content for change detection.

        Args:
            page_data: Notion page object

        Returns:
            SHA256 hash of the page content
        """
        # Include key fields that affect sync output
        content = {
            'last_edited_time': page_data.get('last_edited_time'),
            'properties': page_data.get('properties', {})
        }

        # Create a stable JSON representation
        content_json = json.dumps(content, sort_keys=True)
        return hashlib.sha256(content_json.encode()).hexdigest()

    def should_process_page(self, page_id: str, page_data: Dict[str, Any]) -> bool:
        """
        Check if a page should be processed based on content changes.

        Args:
            page_id: Notion page ID
            page_data: Notion page object

        Returns:
            True if page should be processed (changed or new), False if unchanged
        """
        current_hash = self.compute_content_hash(page_data)
        last_edited_time = page_data.get('last_edited_time')

        result = self.db.fetch_one(
            """
            SELECT content_hash, last_edited_time
            FROM page_cache
            WHERE page_id = %s
            """,
            (page_id,)
        )

        if not result:
            # New page, should process
            return True

        cached_hash = result['content_hash']
        cached_time = result['last_edited_time']

        # Check if content has changed
        if current_hash != cached_hash:
            return True

        # Check if last_edited_time has changed
        if last_edited_time != cached_time:
            return True

        # No changes detected
        return False

    def update_cache(self, page_id: str, page_data: Dict[str, Any], webflow_id: Optional[str] = None):
        """
        Update the cache for a processed page.

        Args:
            page_id: Notion page ID
            page_data: Notion page object
            webflow_id: Webflow item ID (optional)
        """
        content_hash = self.compute_content_hash(page_data)
        last_edited_time = page_data.get('last_edited_time')
        current_time = time.time()

        self.db.upsert(
            'page_cache',
            {
                'page_id': page_id,
                'content_hash': content_hash,
                'last_edited_time': last_edited_time,
                'last_synced_at': current_time,
                'webflow_id': webflow_id
            },
            conflict_columns=['page_id']
        )

    def get_cached_webflow_id(self, page_id: str) -> Optional[str]:
        """
        Get the cached Webflow ID for a page.

        Args:
            page_id: Notion page ID

        Returns:
            Webflow item ID or None if not cached
        """
        result = self.db.fetch_one(
            "SELECT webflow_id FROM page_cache WHERE page_id = %s",
            (page_id,)
        )
        return result['webflow_id'] if result and result.get('webflow_id') else None

    def remove_page(self, page_id: str):
        """
        Remove a page from the cache.

        Args:
            page_id: Notion page ID
        """
        self.db.execute("DELETE FROM page_cache WHERE page_id = %s", (page_id,))

    def cleanup_old_entries(self, days: int = 90):
        """
        Remove cache entries older than specified days.

        Args:
            days: Number of days to keep (default: 90)
        """
        cutoff_time = time.time() - (days * 24 * 60 * 60)
        self.db.execute(
            "DELETE FROM page_cache WHERE last_synced_at < %s",
            (cutoff_time,)
        )

    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the cache.

        Returns:
            Dictionary with cache statistics
        """
        total_result = self.db.fetch_one("SELECT COUNT(*) as count FROM page_cache")
        total_entries = total_result['count'] if total_result else 0

        recent_result = self.db.fetch_one(
            """
            SELECT COUNT(*) as count FROM page_cache
            WHERE last_synced_at > %s
            """,
            (time.time() - (24 * 60 * 60),)
        )
        recent_entries = recent_result['count'] if recent_result else 0

        return {
            'total_entries': total_entries,
            'entries_synced_last_24h': recent_entries,
            'backend': 'libsql'
        }

    def close(self):
        """Close the database connection (no-op for pooled connections)."""
        # Connection pooling handles this
        pass

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
