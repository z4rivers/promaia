"""
JSON Content Registry - SQLite database for tracking JSON content files.

This module provides a registry system for managing JSON content files in a flat structure,
making them easily accessible without requiring a navigable directory hierarchy.

DEPRECATED: This module is deprecated in favor of the hybrid storage architecture.
Use HybridContentRegistry from promaia.storage.hybrid_storage instead.
"""
import sqlite3
import os
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from pathlib import Path

logger = logging.getLogger(__name__)

class JSONContentRegistry:
    """SQLite-based registry for tracking JSON content files.
    
    DEPRECATED: Use HybridContentRegistry instead for new functionality.
    """
    
    def __init__(self, db_path: str = "data/hybrid_metadata.db"):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """Initialize the SQLite database with required tables."""
        # Ensure directory exists
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Create content registry table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS content_registry (
                    page_id TEXT PRIMARY KEY,
                    workspace TEXT NOT NULL,
                    database_name TEXT NOT NULL,
                    content_type TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    title TEXT,
                    created_time TEXT,
                    last_edited_time TEXT,
                    synced_time TEXT DEFAULT CURRENT_TIMESTAMP,
                    file_size INTEGER,
                    checksum TEXT,
                    metadata TEXT,
                    sync_status TEXT DEFAULT 'synced',
                    last_synced TEXT
                )
            """)
            
            # Create indexes for faster queries
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_workspace_db 
                ON content_registry(workspace, database_name)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_last_edited 
                ON content_registry(last_edited_time)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_sync_status 
                ON content_registry(sync_status)
            """)
            
            conn.commit()
            logger.debug(f"Initialized JSON content registry at {self.db_path}")
    
    def register_content(self, 
                        page_id: str, 
                        workspace: str, 
                        database_name: str, 
                        file_path: str, 
                        content_data: Dict[str, Any]) -> bool:
        """Register a JSON content file in the registry."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Extract metadata from content
                title = content_data.get('title', '')
                created_time = content_data.get('created_time', '')
                last_edited_time = content_data.get('last_edited_time', '')
                
                # Calculate file stats
                file_size = os.path.getsize(file_path) if os.path.exists(file_path) else 0
                
                # Store additional metadata as JSON
                metadata = {
                    'properties': content_data.get('properties', {}),
                    'has_content': bool(content_data.get('content', [])),
                    'url': content_data.get('url', ''),
                    'parent': content_data.get('parent', {}),
                    'archived': content_data.get('archived', False)
                }
                
                cursor.execute("""
                    INSERT OR REPLACE INTO content_registry 
                    (page_id, workspace, database_name, file_path, title, 
                     created_time, last_edited_time, synced_time, file_size, metadata,
                     sync_status, last_synced)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    page_id, workspace, database_name, file_path, title,
                    created_time, last_edited_time, datetime.now().isoformat(),
                    file_size, json.dumps(metadata), 'synced', datetime.now().isoformat()
                ))
                
                conn.commit()
                logger.debug(f"Registered content: {page_id} -> {file_path}")
                return True
                
        except Exception as e:
            logger.error(f"Error registering content {page_id}: {e}")
            return False
    
    def get_content_info(self, page_id: str) -> Optional[Dict[str, Any]]:
        """Get content information by page ID."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT * FROM content_registry WHERE page_id = ?
                """, (page_id,))
                
                row = cursor.fetchone()
                if row:
                    result = dict(row)
                    # Parse metadata JSON
                    if result['metadata']:
                        result['metadata'] = json.loads(result['metadata'])
                    return result
                return None
                
        except Exception as e:
            logger.error(f"Error getting content info for {page_id}: {e}")
            return None
    
    def list_content(self, 
                    workspace: Optional[str] = None, 
                    database_name: Optional[str] = None,
                    limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """List content with optional filtering."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                query = "SELECT * FROM content_registry"
                params = []
                conditions = []
                
                if workspace:
                    conditions.append("workspace = ?")
                    params.append(workspace)
                
                if database_name:
                    conditions.append("database_name = ?")
                    params.append(database_name)
                
                if conditions:
                    query += " WHERE " + " AND ".join(conditions)
                
                query += " ORDER BY synced_time DESC"
                
                if limit:
                    query += " LIMIT ?"
                    params.append(limit)
                
                cursor.execute(query, params)
                rows = cursor.fetchall()
                
                results = []
                for row in rows:
                    result = dict(row)
                    # Parse metadata JSON
                    if result['metadata']:
                        result['metadata'] = json.loads(result['metadata'])
                    results.append(result)
                
                return results
                
        except Exception as e:
            logger.error(f"Error listing content: {e}")
            return []
    
    def remove_content(self, page_id: str) -> bool:
        """Remove content from registry."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM content_registry WHERE page_id = ?", (page_id,))
                conn.commit()
                return cursor.rowcount > 0
                
        except Exception as e:
            logger.error(f"Error removing content {page_id}: {e}")
            return False
    
    def get_stats(self) -> Dict[str, Any]:
        """Get registry statistics."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Total count
                cursor.execute("SELECT COUNT(*) FROM content_registry")
                total_count = cursor.fetchone()[0]
                
                # Count by workspace
                cursor.execute("""
                    SELECT workspace, COUNT(*) 
                    FROM content_registry 
                    GROUP BY workspace
                """)
                workspace_counts = dict(cursor.fetchall())
                
                # Count by database
                cursor.execute("""
                    SELECT workspace, database_name, COUNT(*) 
                    FROM content_registry 
                    GROUP BY workspace, database_name
                """)
                database_counts = {}
                for workspace, db_name, count in cursor.fetchall():
                    if workspace not in database_counts:
                        database_counts[workspace] = {}
                    database_counts[workspace][db_name] = count
                
                # Recent activity
                cursor.execute("""
                    SELECT COUNT(*) FROM content_registry 
                    WHERE synced_time > datetime('now', '-1 day')
                """)
                recent_count = cursor.fetchone()[0]
                
                return {
                    'total_content': total_count,
                    'by_workspace': workspace_counts,
                    'by_database': database_counts,
                    'recent_syncs': recent_count,
                    'db_path': self.db_path
                }
                
        except Exception as e:
            logger.error(f"Error getting stats: {e}")
            return {}
    
    def cleanup_orphaned_entries(self) -> int:
        """Remove registry entries for files that no longer exist."""
        try:
            removed_count = 0
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute("SELECT page_id, file_path FROM content_registry")
                entries = cursor.fetchall()
                
                for page_id, file_path in entries:
                    if not os.path.exists(file_path):
                        cursor.execute("DELETE FROM content_registry WHERE page_id = ?", (page_id,))
                        removed_count += 1
                        logger.debug(f"Removed orphaned entry: {page_id} -> {file_path}")
                
                conn.commit()
                logger.info(f"Cleaned up {removed_count} orphaned registry entries")
                return removed_count
                
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
            return 0
    
    def update_sync_status(self, page_id: str, status: str, timestamp: Optional[str] = None) -> bool:
        """Update sync status for a page."""
        try:
            if timestamp is None:
                timestamp = datetime.now().isoformat()
                
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE content_registry 
                    SET sync_status = ?, last_synced = ?
                    WHERE page_id = ?
                """, (status, timestamp, page_id))
                conn.commit()
                return cursor.rowcount > 0
                
        except Exception as e:
            logger.error(f"Error updating sync status for {page_id}: {e}")
            return False
    
    def get_pages_needing_sync(self, workspace: Optional[str] = None, database_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get pages that need to be synced (status != 'synced')."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                query = """
                    SELECT * FROM content_registry 
                    WHERE sync_status != 'synced' OR sync_status IS NULL
                """
                params = []
                
                if workspace:
                    query += " AND workspace = ?"
                    params.append(workspace)
                
                if database_name:
                    query += " AND database_name = ?"
                    params.append(database_name)
                
                query += " ORDER BY last_edited_time DESC"
                
                cursor.execute(query, params)
                rows = cursor.fetchall()
                
                results = []
                for row in rows:
                    result = dict(row)
                    # Parse metadata JSON
                    if result['metadata']:
                        result['metadata'] = json.loads(result['metadata'])
                    results.append(result)
                
                return results
                
        except Exception as e:
            logger.error(f"Error getting pages needing sync: {e}")
            return []
    
    def get_latest_journal_entry(self, workspace: str) -> Optional[Dict[str, Any]]:
        """Get the latest journal entry for push command."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT * FROM content_registry 
                    WHERE workspace = ? AND database_name = 'journal'
                    ORDER BY last_edited_time DESC
                    LIMIT 1
                """, (workspace,))
                
                row = cursor.fetchone()
                if row:
                    result = dict(row)
                    if result['metadata']:
                        result['metadata'] = json.loads(result['metadata'])
                    return result
                return None
                
        except Exception as e:
            logger.error(f"Error getting latest journal entry: {e}")
            return None

# Global registry instance
_registry_instance = None

def get_json_registry(db_path: Optional[str] = None) -> JSONContentRegistry:
    """Get the global JSON content registry instance."""
    global _registry_instance
    if _registry_instance is None or (db_path and db_path != _registry_instance.db_path):
        _registry_instance = JSONContentRegistry(db_path or "data/hybrid_metadata.db")
    return _registry_instance 