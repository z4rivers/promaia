"""
Response Context Builder - Builds context using vector search.

Searches across all databases in the workspace to find relevant context
for generating email responses.
"""
import json
import logging
from typing import Dict, List, Any, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ResponseContext:
    """Container for response generation context."""
    thread_history: str
    relevant_docs: List[Dict[str, Any]]
    relevant_docs_text: str
    workspace: str
    total_sources: int


class ResponseContextBuilder:
    """Builds context using vector search across databases."""
    
    def __init__(self):
        """Initialize context builder."""
        self.vector_db = None
    
    def _get_vector_db(self):
        """Lazy load vector DB manager."""
        if self.vector_db is None:
            from promaia.storage.vector_db import VectorDBManager
            self.vector_db = VectorDBManager()
        return self.vector_db
    
    async def build_context(
        self,
        email_thread: Dict[str, Any],
        workspace: str,
        n_results: int = 20,
        min_similarity: float = 0.3
    ) -> ResponseContext:
        """
        Build response context using vector search.
        
        Args:
            email_thread: Email thread data
            workspace: Workspace to search in
            n_results: Maximum number of vector search results
            min_similarity: Minimum similarity threshold
            
        Returns:
            ResponseContext with thread history and relevant documents
        """
        try:
            # Extract thread history
            thread_history = self._extract_thread_history(email_thread)
            
            # Build search query from email content
            search_query = self._build_search_query(email_thread)
            
            # Search across all databases in workspace using vector DB
            vector_db = self._get_vector_db()
            
            filters = {
                "workspace": workspace
                # No database_name filter = search all databases
            }
            
            logger.info(f"🔍 Searching {workspace} workspace for relevant context...")
            results = vector_db.search(
                query_text=search_query,
                filters=filters,
                n_results=n_results,
                min_similarity=min_similarity
            )
            
            # Load full content for top results
            relevant_docs = self._load_document_content(results[:10])  # Top 10 only
            
            # Format documents as text for prompt
            relevant_docs_text = self._format_docs_for_prompt(relevant_docs)
            
            logger.info(f"✅ Found {len(relevant_docs)} relevant documents for context")
            
            return ResponseContext(
                thread_history=thread_history,
                relevant_docs=relevant_docs,
                relevant_docs_text=relevant_docs_text,
                workspace=workspace,
                total_sources=len(results)
            )
            
        except Exception as e:
            logger.error(f"❌ Failed to build response context: {e}")
            # Return minimal context
            return ResponseContext(
                thread_history=self._extract_thread_history(email_thread),
                relevant_docs=[],
                relevant_docs_text="No additional context available.",
                workspace=workspace,
                total_sources=0
            )
    
    def _extract_thread_history(self, email_thread: Dict[str, Any]) -> str:
        """Extract formatted thread history."""
        # Get conversation body (which includes full thread for full_thread mode)
        conversation = email_thread.get('conversation_body', '')
        
        if not conversation:
            # Fallback to basic info
            from_addr = email_thread.get('from', 'Unknown')
            subject = email_thread.get('subject', 'No Subject')
            date = email_thread.get('date', 'Unknown')
            body = email_thread.get('body', '')
            
            return f"""From: {from_addr}
Subject: {subject}
Date: {date}

{body}"""
        
        return conversation
    
    def _build_search_query(self, email_thread: Dict[str, Any]) -> str:
        """
        Build search query from email content.
        Combines subject and body for comprehensive search.
        """
        subject = email_thread.get('subject', '')
        body = email_thread.get('conversation_body', '') or email_thread.get('body', '')
        
        # Combine subject and body, truncate if too long
        query = f"{subject}\n\n{body}"
        
        if len(query) > 2000:
            query = query[:2000]
        
        return query
    
    def _load_document_content(self, search_results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Load full content for search results.
        
        Args:
            search_results: Results from vector search
            
        Returns:
            List of documents with full content
        """
        docs = []
        
        for result in search_results:
            try:
                page_id = result.get('page_id')
                metadata = result.get('metadata', {})
                
                # Try to read the markdown file
                from promaia.storage.hybrid_storage import get_hybrid_registry
                registry = get_hybrid_registry()
                
                # Get file path from registry
                with registry.get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute(
                        "SELECT file_path, title, database_name FROM unified_content WHERE page_id = ?",
                        (page_id,)
                    )
                    row = cursor.fetchone()
                    
                    if row:
                        file_path, title, database_name = row
                        
                        # Read markdown content
                        import os
                        if os.path.exists(file_path):
                            with open(file_path, 'r', encoding='utf-8') as f:
                                content = f.read()
                            
                            # Truncate if too long (keep first 500 chars)
                            if len(content) > 500:
                                content = content[:500] + "..."
                            
                            docs.append({
                                'page_id': page_id,
                                'title': title,
                                'database': database_name,
                                'content_snippet': content,
                                'similarity': result.get('similarity_score', 0),
                                'metadata': metadata
                            })
            
            except Exception as e:
                logger.warning(f"⚠️  Could not load content for {page_id}: {e}")
                continue
        
        return docs
    
    def _format_docs_for_prompt(self, docs: List[Dict[str, Any]]) -> str:
        """Format documents as text for AI prompt."""
        if not docs:
            return "No relevant documents found in knowledge base."
        
        formatted = []
        formatted.append(f"Found {len(docs)} relevant documents from your knowledge base:\n")
        
        for i, doc in enumerate(docs, 1):
            formatted.append(f"[{i}] {doc['title']}")
            formatted.append(f"    Database: {doc['database']} | Relevance: {doc['similarity']:.0%}")
            formatted.append(f"    {doc['content_snippet']}")
            formatted.append("")
        
        return '\n'.join(formatted)
    
    def serialize_context_for_storage(self, context: ResponseContext) -> str:
        """
        Serialize context for storage in database.
        
        Args:
            context: ResponseContext object
            
        Returns:
            JSON string
        """
        return json.dumps({
            'total_sources': context.total_sources,
            'documents': [
                {
                    'page_id': doc['page_id'],
                    'title': doc['title'],
                    'database': doc['database'],
                    'similarity': doc['similarity'],
                    'snippet': doc['content_snippet'][:200]  # Store short snippet
                }
                for doc in context.relevant_docs
            ]
        })

