"""
Hybrid Query Interface - Optimized storage system with separate tables per content type.

This module provides a query interface for the hybrid storage architecture with
separate optimized tables for each content type (Gmail, Notion databases, etc.)
unified through the unified_content view.
"""
from promaia.storage.db_factory import db_connect
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
            with db_connect() as conn:
                cursor = conn.cursor()

                # --- Gmail Thread Logic ---
                # This logic will now be primary and will handle all cases.
                
                # Check for cross-workspace databases (workspace_scope="all")
                cross_workspace_sources = []
                if sources:
                    try:
                        from promaia.config.databases import get_database_config
                        for source in sources:
                            db_config = get_database_config(source)
                            if db_config and getattr(db_config, 'workspace_scope', 'single') == 'all':
                                cross_workspace_sources.append(source)
                    except Exception as e:
                        logger.warning(f"Could not check workspace_scope: {e}")

                # Default WHERE conditions and params with cross-workspace support
                if cross_workspace_sources:
                    # Include content from specified workspace OR cross-workspace databases
                    cross_workspace_list = ', '.join(f"'{s}'" for s in cross_workspace_sources)
                    where_conditions = [f"(workspace = %s OR database_name IN ({cross_workspace_list}))"]
                else:
                    where_conditions = ["workspace = %s"]
                params = [workspace]

                # Add source filtering
                if sources:
                    source_conditions = []
                    for source in sources:
                        source_conditions.append("database_name = %s")
                        params.append(source)
                    where_conditions.append(f"({' OR '.join(source_conditions)})")
                
                # Date filtering cutoff
                cutoff_date = None
                if days:
                    # Handle special case for 'all' - no date filtering
                    if isinstance(days, str) and days.lower() == 'all':
                        # Skip date filtering for 'all'
                        pass
                    else:
                        try:
                            days_int = int(days) if isinstance(days, str) else days
                            cutoff_date = (datetime.now() - timedelta(days=days_int)).isoformat()
                        except (ValueError, TypeError) as e:
                            print(f"Warning: Invalid days parameter '{days}': {e}")
                            # Continue without date filtering if days parameter is invalid
                
                # Step 1: Find thread_ids of all Gmail messages that meet the date criteria.
                gmail_thread_ids = set()
                if 'gmail' in (sources or []) and cutoff_date:
                    gmail_thread_query = """
                        SELECT DISTINCT metadata->>'thread_id'
                        FROM unified_content
                        WHERE database_name = 'gmail' AND workspace = %s AND (created_time >= %s OR last_edited_time >= %s)
                    """
                    cursor.execute(gmail_thread_query, (workspace, cutoff_date, cutoff_date))
                    gmail_thread_ids.update(row[0] for row in cursor.fetchall() if row[0])

                # Step 2: Build the final query
                # We will fetch:
                # - All messages from the identified Gmail threads.
                # - All non-Gmail content that meets the original filters.
                
                final_where_clauses = []
                final_params = []
                
                # A) Clause for non-Gmail content (with cross-workspace support)
                if cross_workspace_sources:
                    cross_workspace_list = ', '.join(f"'{s}'" for s in cross_workspace_sources)
                    non_gmail_conditions = ["database_name != 'gmail'", f"(workspace = %s OR database_name IN ({cross_workspace_list}))"]
                else:
                    non_gmail_conditions = ["database_name != 'gmail'", "workspace = %s"]
                non_gmail_params = [workspace]
                
                if sources:
                    other_sources = [s for s in sources if s != 'gmail']
                    if other_sources:
                        source_placeholders = ','.join('%s' for _ in other_sources)
                        non_gmail_conditions.append(f"database_name IN ({source_placeholders})")
                        non_gmail_params.extend(other_sources)

                if cutoff_date:
                    non_gmail_conditions.append("(created_time >= %s OR last_edited_time >= %s)")
                    non_gmail_params.extend([cutoff_date, cutoff_date])
                
                # Add custom filters to non-gmail part
                if filters:
                    for key, value in filters.items():
                        non_gmail_conditions.append(f"{key} = %s") # simplified for now
                        non_gmail_params.append(value)
                
                non_gmail_full_clause = f"({' AND '.join(non_gmail_conditions)})"
                
                # B) Clause for Gmail content
                if gmail_thread_ids:
                    placeholders = ','.join('%s' for _ in gmail_thread_ids)
                    gmail_full_clause = f"(database_name = 'gmail' AND workspace = %s AND metadata->>'thread_id' IN ({placeholders}))"
                    
                    # Combine clauses with OR
                    final_query_clause = f"{non_gmail_full_clause} OR {gmail_full_clause}"
                    final_params.extend(non_gmail_params)
                    final_params.append(workspace) # for the gmail part
                    final_params.extend(list(gmail_thread_ids))
                else:
                    # No recent gmail threads, just use the non-gmail clause
                    # but we also need to include gmail if it was in sources and no date filter was applied
                    if 'gmail' in (sources or []) and not cutoff_date:
                         # This case should fetch all gmail content if no date filter
                         final_query_clause = f"{non_gmail_full_clause} OR (database_name = 'gmail' AND workspace = %s)"
                         final_params.extend(non_gmail_params)
                         final_params.append(workspace)
                    else:
                         final_query_clause = non_gmail_full_clause
                         final_params = non_gmail_params


                # Construct and execute the final query
                query = f"""
                    SELECT *
                    FROM unified_content 
                    WHERE {final_query_clause}
                    ORDER BY last_edited_time IS NULL, last_edited_time DESC, created_time IS NULL, created_time DESC
                """

                # Temporary fix for when no sources are provided, which would lead to an empty `other_sources` list and invalid SQL
                if not sources:
                    # If no sources, we should query everything respecting the date filter if present
                    base_conditions = ["workspace = %s"]
                    base_params = [workspace]
                    if cutoff_date:
                        base_conditions.append("(created_time >= %s OR last_edited_time >= %s)")
                        base_params.extend([cutoff_date, cutoff_date])

                    final_query_clause = ' AND '.join(base_conditions)
                    final_params = base_params

                    query = f"""
                        SELECT *
                        FROM unified_content
                        WHERE {final_query_clause}
                        ORDER BY last_edited_time IS NULL, last_edited_time DESC, created_time IS NULL, created_time DESC
                    """


                cursor.execute(query, final_params)
                results = cursor.fetchall()
                
                # Convert to format expected by chat interface
                content_list = []
                columns = [desc[0] for desc in cursor.description]
                for row in results:
                    content_list.append(dict(zip(columns, row)))
                
                return content_list
                
        except Exception as e:
            print(f"Error querying content: {e}")
            return []
    
    def get_content_by_id(self, page_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific content item by page ID."""
        try:
            with db_connect() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT page_id, workspace, database_name, content_type, file_path, title,
                           created_time, last_edited_time, synced_time, metadata
                    FROM unified_content 
                    WHERE page_id = %s
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
            with db_connect() as conn:
                cursor = conn.cursor()
                
                where_conditions = ["(title LIKE %s OR metadata LIKE %s)"]
                params = [f"%{query}%", f"%{query}%"]
                
                if workspace:
                    where_conditions.append("workspace = %s")
                    params.append(workspace)
                
                if sources:
                    source_conditions = []
                    for source in sources:
                        source_conditions.append("database_name = %s")
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
    
    def natural_language_query(self, nl_prompt: str, workspace: str = None, database_names: List[str] = None, verbose: bool = True) -> Dict[str, List[Dict[str, Any]]]:
        """Process natural language queries using the agentic system with retry logic."""
        try:
            from promaia.ai.nl_processor_wrapper import process_natural_language_to_content
        except ImportError as e:
            print(f"❌ Natural language processing not available: {e}")
            return {}
        
        # For cross-workspace queries, we don't need specific workspace context
        # The agentic AI will handle workspace filtering in the SQL when specifically mentioned
        
        # Process using new agentic system (with schema exploration, learning, retry)
        # Enable verbose mode by default to show SQL generation and chain of thought
        return process_natural_language_to_content(nl_prompt, workspace, database_names, verbose=verbose)
    
    def get_database_context(self, workspace: str) -> Dict[str, Any]:
        """Get available databases for a workspace."""
        try:
            with db_connect() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT database_name, COUNT(*) as count
                    FROM unified_content 
                    WHERE workspace = %s
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
        """Migrate from legacy architecture to hybrid - DEPRECATED."""
        logger.warning("Legacy migration is deprecated. System now uses hybrid architecture exclusively.")
        return False

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
    """Get the hybrid query interface instance (legacy compatibility function).
    
    DEPRECATED: Use get_query_interface() directly instead.
    """
    return get_query_interface(hybrid_db_path) 