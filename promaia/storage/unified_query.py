"""
Hybrid Query Interface - Optimized storage system with separate tables per content type.

This module provides a query interface for the hybrid storage architecture with
separate optimized tables for each content type (Gmail, Notion databases, etc.)
unified through the unified_content view.
"""
import sqlite3
import os
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union
from pathlib import Path

from promaia.storage.hybrid_storage import get_hybrid_registry, HybridContentRegistry

logger = logging.getLogger(__name__)

class HybridQueryInterface:
    """Query interface for the hybrid storage architecture."""
    
    def __init__(self, db_path: str = "data/hybrid_metadata.db"):
        self.db_path = db_path
        self.registry = get_hybrid_registry(db_path)
        logger.info("Using hybrid storage architecture")
    
    def query_content_for_chat(self, workspace: str, sources: List[str] = None, 
                             days: int = None, filters: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """Query content for chat interface."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Build WHERE clause
                where_conditions = ["workspace = ?"]
                params = [workspace]
                
                # Add source filtering
                if sources:
                    source_conditions = []
                    for source in sources:
                        source_conditions.append("database_name = ?")
                        params.append(source)
                    where_conditions.append(f"({' OR '.join(source_conditions)})")
                
                # Add date filtering
                if days:
                    cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()
                    where_conditions.append("(last_edited_time >= ? OR created_time >= ?)")
                    params.extend([cutoff_date, cutoff_date])
                
                # Add custom filters
                if filters:
                    for key, value in filters.items():
                        if key == 'status':
                            where_conditions.append("status = ?")
                            params.append(value)
                        elif key == 'featured':
                            where_conditions.append("featured = ?")
                            params.append(1 if value else 0)
                        elif key == 'priority':
                            where_conditions.append("priority = ?")
                            params.append(value)
                        elif key == 'category':
                            where_conditions.append("category = ?")
                            params.append(value)
                        elif key.endswith('_time') or key.endswith('_date'):
                            where_conditions.append(f"{key} >= ?")
                            params.append(value)
                
                where_clause = " AND ".join(where_conditions)
                
                query = f"""
                    SELECT page_id, workspace, database_name, content_type, file_path, title,
                           created_time, last_edited_time, synced_time, metadata
                    FROM unified_content 
                    WHERE {where_clause}
                    ORDER BY last_edited_time DESC NULLS LAST, created_time DESC NULLS LAST
                """
                
                cursor.execute(query, params)
                results = cursor.fetchall()
                
                # Convert to format expected by chat interface
                content_list = []
                for row in results:
                    content_dict = {
                        'page_id': row[0],
                        'workspace': row[1],
                        'database_name': row[2],
                        'content_type': row[3],
                        'file_path': row[4],
                        'title': row[5],
                        'created_time': row[6],
                        'last_edited_time': row[7],
                        'synced_time': row[8],
                        'metadata': json.loads(row[9]) if row[9] else {}
                    }
                    content_list.append(content_dict)
                
                return content_list
                
        except Exception as e:
            logger.error(f"Error querying hybrid content: {e}")
            return []
    
    def get_content_by_id(self, page_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific content item by page ID."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT page_id, workspace, database_name, content_type, file_path, title,
                           created_time, last_edited_time, synced_time, metadata
                    FROM unified_content 
                    WHERE page_id = ?
                """, (page_id,))
                
                row = cursor.fetchone()
                if not row:
                    return None
                
                return {
                    'page_id': row[0],
                    'workspace': row[1],
                    'database_name': row[2],
                    'content_type': row[3],
                    'file_path': row[4],
                    'title': row[5],
                    'created_time': row[6],
                    'last_edited_time': row[7],
                    'synced_time': row[8],
                    'metadata': json.loads(row[9]) if row[9] else {}
                }
        except Exception as e:
            logger.error(f"Error getting content by ID: {e}")
            return None
    
    def search_content(self, query: str, workspace: str = None, sources: List[str] = None) -> List[Dict[str, Any]]:
        """Search content by title or metadata."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                where_conditions = ["(title LIKE ? OR metadata LIKE ?)"]
                params = [f"%{query}%", f"%{query}%"]
                
                if workspace:
                    where_conditions.append("workspace = ?")
                    params.append(workspace)
                
                if sources:
                    source_conditions = []
                    for source in sources:
                        source_conditions.append("database_name = ?")
                        params.append(source)
                    where_conditions.append(f"({' OR '.join(source_conditions)})")
                
                where_clause = " AND ".join(where_conditions)
                
                cursor.execute(f"""
                    SELECT page_id, workspace, database_name, content_type, file_path, title,
                           created_time, last_edited_time, synced_time, metadata
                    FROM unified_content 
                    WHERE {where_clause}
                    ORDER BY last_edited_time DESC
                """, params)
                
                results = cursor.fetchall()
                
                content_list = []
                for row in results:
                    content_dict = {
                        'page_id': row[0],
                        'workspace': row[1],
                        'database_name': row[2],
                        'content_type': row[3],
                        'file_path': row[4],
                        'title': row[5],
                        'created_time': row[6],
                        'last_edited_time': row[7],
                        'synced_time': row[8],
                        'metadata': json.loads(row[9]) if row[9] else {}
                    }
                    content_list.append(content_dict)
                
                return content_list
                
        except Exception as e:
            logger.error(f"Error searching content: {e}")
            return []
    
    def natural_language_query(self, nl_prompt: str, workspace: str = None) -> Dict[str, List[Dict[str, Any]]]:
        """Process natural language queries using hybrid schema across all workspaces by default."""
        from promaia.ai.natural_query import process_natural_language_to_content
        
        # For cross-workspace queries, we don't need specific workspace context
        # The AI will handle workspace filtering in the SQL when specifically mentioned
        
        # Enhanced schema info for hybrid architecture
        schema_info = f"""
        HYBRID ARCHITECTURE - Optimized separate tables for each content type:
        
        IMPORTANT: In this hybrid architecture, you MUST use the 'unified_content' view for all queries.
        
        OPTIMIZED TABLES BY CONTENT TYPE:
        
        1. GMAIL (gmail_content table):
           Direct columns: subject, sender_email, sender_name, recipient_emails, gmail_labels,
                          thread_id, message_id, has_attachments, is_unread, body_snippet, email_date
           Examples:
           - "emails from john": WHERE sender_email LIKE '%john%' OR sender_name LIKE '%john%'
           - "unread emails": WHERE is_unread = 1
           - "emails with attachments": WHERE has_attachments = 1
           - "emails from last week": WHERE datetime(email_date) >= datetime('now', '-7 days')
        
        2. NOTION JOURNAL (notion_journal table):
           Direct columns: title, status, date_value, tags, featured, author_name
           Examples:
           - "published journal entries": WHERE status = 'Published'
           - "featured journal entries": WHERE featured = 1
           - "entries by author": WHERE author_name = 'Koii Benvenutto'
           
        3. NOTION STORIES (notion_stories table):
           Direct columns: title, status, epic_relation, author_name, story_points, priority, labels
           Examples:
           - "completed stories": WHERE status = 'Done'
           - "high priority stories": WHERE priority = 'High'
           - "stories with 5 points": WHERE story_points = 5
           
        4. NOTION CMS (notion_cms table):
           Direct columns: title, status, category, featured, author_name, slug, tags, publish_date
           Examples:
           - "published blog posts": WHERE status = 'Published'
           - "featured content": WHERE featured = 1
           - "posts in tech category": WHERE category = 'Tech'
        
        5. GENERIC CONTENT (generic_content table):
           For unknown content types, use metadata JSON extraction
        
        UNIFIED VIEW SCHEMA:
        The unified_content view provides these direct columns for fast access:
        
        Core columns (all content types):
        - page_id, workspace, database_name, content_type, file_path, title
        - created_time, last_edited_time, synced_time, file_size, checksum
        
        Direct filterable columns:
        - status (TEXT): Content status - 'Published', 'Draft', 'Done', 'In Progress', etc.
        - featured (INTEGER): 1 for featured content, 0 for normal, NULL if not applicable
        - priority (TEXT): Priority level - 'High', 'Medium', 'Low', etc.
        - category (TEXT): Content category 
        - sender_email (TEXT): Email sender for Gmail content
        - sender_name (TEXT): Sender name for Gmail content  
        - has_attachments (INTEGER): 1 if Gmail has attachments, 0 if not
        - is_unread (INTEGER): 1 if Gmail is unread, 0 if read
        
        QUERY PATTERNS:
        SELECT page_id, title, created_time, last_edited_time, file_path, metadata, database_name 
        FROM unified_content 
        WHERE [your conditions using direct columns - workspace filters only when specified]
        
        Cross-workspace queries enabled - query any combination of workspaces and databases.
        """
        
        return process_natural_language_to_content(nl_prompt, workspace, schema_info)
    
    def get_database_context(self, workspace: str) -> Dict[str, Any]:
        """Get available databases for a workspace."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT database_name, COUNT(*) as count
                    FROM unified_content 
                    WHERE workspace = ?
                    GROUP BY database_name
                """, (workspace,))
                
                databases = {}
                for row in cursor.fetchall():
                    databases[row[0]] = {
                        'count': row[1],
                        'type': 'notion' if row[0] in ['journal', 'stories', 'cms'] else 'gmail'
                    }
                
                return databases
        except Exception:
            return {}
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get comprehensive statistics about the storage system."""
        stats = self.registry.get_content_statistics()
        stats['architecture'] = 'hybrid'
        return stats
    
    def migrate_from_legacy(self, legacy_db_path: str = "data/metadata.db") -> bool:
        """Migrate from legacy architecture to hybrid."""
        if not os.path.exists(legacy_db_path):
            logger.error("Legacy database not found")
            return False
        
        return self.registry.migrate_from_legacy(legacy_db_path)


# Global instance
_query_interface = None

def get_query_interface(db_path: str = "data/hybrid_metadata.db") -> HybridQueryInterface:
    """Get the global hybrid query interface instance."""
    global _query_interface
    if _query_interface is None:
        _query_interface = HybridQueryInterface(db_path)
    return _query_interface

# Keep the old function name for backward compatibility during transition
def get_unified_query(legacy_db_path: str = "data/metadata.db",
                     hybrid_db_path: str = "data/hybrid_metadata.db",
                     prefer_hybrid: bool = True) -> HybridQueryInterface:
    """Get the hybrid query interface instance (legacy compatibility function)."""
    return get_query_interface(hybrid_db_path) 