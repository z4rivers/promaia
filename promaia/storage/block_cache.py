"""
Persistent block cache for Notion content.
Stores block content keyed by page_id and last_edited_time to avoid redundant API calls.

Now uses PostgreSQL for centralized storage.
"""
import json
import time
import logging
from typing import List, Dict, Any, Optional
from pathlib import Path

from promaia.storage.db_factory import get_db

logger = logging.getLogger(__name__)


class BlockCache:
    """
    Manages persistent cache for Notion blocks using PostgreSQL.
    Caches block content to avoid repeated API calls for unchanged pages.
    """

    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize the block cache.

        Args:
            db_path: Deprecated parameter, kept for backward compatibility.
                    All data is now stored in PostgreSQL.
        """
        self.db = get_db()
        self._ensure_table()
        logger.debug("BlockCache initialized with PostgreSQL backend")

    def _ensure_table(self):
        """Ensure the block_cache table exists."""
        if not self.db.table_exists('block_cache'):
            self.db.execute("""
                CREATE TABLE IF NOT EXISTS block_cache (
                    id SERIAL PRIMARY KEY,
                    page_id TEXT NOT NULL,
                    last_edited_time TEXT NOT NULL,
                    blocks JSONB NOT NULL,
                    cached_at DOUBLE PRECISION NOT NULL,
                    UNIQUE(page_id, last_edited_time)
                )
            """)
            self.db.execute("""
                CREATE INDEX IF NOT EXISTS idx_block_cache_page
                ON block_cache(page_id)
            """)
            self.db.execute("""
                CREATE INDEX IF NOT EXISTS idx_block_cache_time
                ON block_cache(cached_at)
            """)

    def get_blocks(self, page_id: str, last_edited_time: str) -> Optional[List[Dict[str, Any]]]:
        """
        Get cached blocks for a page.

        Args:
            page_id: Notion page ID
            last_edited_time: Last edited timestamp from Notion

        Returns:
            List of block objects or None if not cached or outdated
        """
        result = self.db.fetch_one(
            """
            SELECT blocks FROM block_cache
            WHERE page_id = %s AND last_edited_time = %s
            """,
            (page_id, last_edited_time)
        )
        
        if result:
            blocks = result['blocks']
            # JSONB is automatically deserialized by psycopg2
            if isinstance(blocks, str):
                try:
                    return json.loads(blocks)
                except json.JSONDecodeError:
                    self.remove_blocks(page_id, last_edited_time)
                    return None
            return blocks
        
        return None

    def set_blocks(self, page_id: str, last_edited_time: str, blocks: List[Dict[str, Any]]):
        """
        Store blocks in cache.

        Args:
            page_id: Notion page ID
            last_edited_time: Last edited timestamp from Notion
            blocks: List of block objects to cache
        """
        current_time = time.time()
        
        # Convert blocks to JSON if not already JSONB compatible
        blocks_json = json.dumps(blocks) if isinstance(blocks, list) else blocks

        self.db.execute(
            """
            INSERT INTO block_cache (page_id, last_edited_time, blocks, cached_at)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (page_id, last_edited_time)
            DO UPDATE SET blocks = EXCLUDED.blocks, cached_at = EXCLUDED.cached_at
            """,
            (page_id, last_edited_time, blocks_json, current_time)
        )

    def remove_blocks(self, page_id: str, last_edited_time: Optional[str] = None):
        """
        Remove blocks from cache.

        Args:
            page_id: Notion page ID
            last_edited_time: If specified, only removes blocks with this timestamp
        """
        if last_edited_time:
            self.db.execute(
                "DELETE FROM block_cache WHERE page_id = %s AND last_edited_time = %s",
                (page_id, last_edited_time)
            )
        else:
            # Remove all cached versions for this page
            self.db.execute(
                "DELETE FROM block_cache WHERE page_id = %s",
                (page_id,)
            )

    def cleanup_old_entries(self, days: int = 30):
        """
        Remove cache entries older than specified days.

        Args:
            days: Number of days to keep (default: 30)
        """
        cutoff_time = time.time() - (days * 24 * 60 * 60)
        self.db.execute(
            "DELETE FROM block_cache WHERE cached_at < %s",
            (cutoff_time,)
        )

    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the cache.

        Returns:
            Dictionary with cache statistics
        """
        total_result = self.db.fetch_one("SELECT COUNT(*) as count FROM block_cache")
        total_entries = total_result['count'] if total_result else 0

        unique_result = self.db.fetch_one(
            "SELECT COUNT(DISTINCT page_id) as count FROM block_cache"
        )
        unique_pages = unique_result['count'] if unique_result else 0

        recent_result = self.db.fetch_one(
            """
            SELECT COUNT(*) as count FROM block_cache
            WHERE cached_at > %s
            """,
            (time.time() - (24 * 60 * 60),)
        )
        recent_entries = recent_result['count'] if recent_result else 0

        return {
            'total_entries': total_entries,
            'unique_pages': unique_pages,
            'entries_cached_last_24h': recent_entries,
            'backend': 'postgresql'
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
