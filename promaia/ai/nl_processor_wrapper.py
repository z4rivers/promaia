"""
Wrapper for agentic NL processor to integrate with existing CLI/Chat interface.
Provides backward-compatible API while using the new agentic system.
"""
from typing import Dict, List, Optional, Any
import os

from promaia.ai.intelligent_nl_processor_agentic import AgenticNLQueryProcessor
from promaia.utils.display import print_text


# Global processor instance
_processor = None

def get_nl_processor(verbose: bool = False, query_mode: str = "sql") -> AgenticNLQueryProcessor:
    """Get or create the global agentic NL processor."""
    global _processor
    # Note: We don't cache the processor because verbose mode may change between calls
    # This ensures the correct verbose setting is always used
    _processor = AgenticNLQueryProcessor(
        query_mode=query_mode,
        debug=os.getenv("MAIA_DEBUG") == "1",
        verbose=verbose
    )
    return _processor


def process_natural_language_to_content(
    nl_prompt: str, 
    workspace: str = None, 
    database_names: List[str] = None,
    verbose: bool = False
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Process natural language queries using the new agentic system.
    
    This is the main integration point that replaces the old LangGraph system.
    It provides a backward-compatible interface for the CLI and Chat.
    
    Args:
        nl_prompt: The natural language query
        workspace: Optional workspace filter
        database_names: Optional list of databases to search
        verbose: Show detailed processing steps
    
    Returns:
        Dict mapping database_name -> list of content entries
    """
    try:
        processor = get_nl_processor(verbose=verbose)
        
        # Process the query with the agentic system (includes modification support)
        result = processor.process_query_with_modification(nl_prompt, workspace=workspace, max_retries=2)
        
        # Check if user chose to quit (exit to terminal)
        if result.get("action") == "quit":
            return {}  # Return empty results to prevent chat from loading
        
        if result["success"] and result["results"]:
            # Extract page IDs from the results
            page_ids = []
            for db_name, entries in result["results"].items():
                for entry in entries:
                    if entry.get('page_id'):
                        page_ids.append(entry['page_id'])
            
            if not page_ids:
                if verbose:
                    print_text("⚠️  No page IDs found in query results", style="yellow")
                return {}
            
            # Use the universal adapter to load full content
            if verbose:
                print_text(f"📄 Loading full content for {len(page_ids)} pages...", style="dim")
            
            from promaia.storage.files import load_content_by_page_ids
            
            full_content = load_content_by_page_ids(
                page_ids=page_ids,
                db_path="data/hybrid_metadata.db",
                expand_gmail_threads=True
            )
            
            if full_content:
                total_loaded = sum(len(pages) for pages in full_content.values())
                if verbose:
                    print(f"Intelligent query processed: {total_loaded} results loaded")
                    print(f"Goal: {result.get('intent', {}).get('goal', 'Unknown')}")
                    print(f"Complexity: Agentic (with retry)")
                    print(f"Sources: {list(full_content.keys())}")
                    if total_loaded > len(page_ids):
                        print(f"   (expanded {total_loaded - len(page_ids)} Gmail thread messages)")
            
            # Return the full content in the expected format
            return full_content
        
        else:
            # Query failed after retries
            error_msg = result.get("error", "Unknown error")
            print_text(f"⚠️  Natural language query failed: {error_msg}", style="yellow")
            return {}
    
    except Exception as e:
        print_text(f"❌ Error in natural language processing: {e}", style="red")
        if os.getenv("MAIA_DEBUG") == "1":
            import traceback
            traceback.print_exc()
        return {}


def process_vector_search_to_content(
    vs_prompt: str,
    workspace: str = None,
    database_names: List[str] = None,
    verbose: bool = False,
    n_results: int = 20,
    min_similarity: float = 0.75
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Process vector search queries using semantic similarity.
    
    This uses the same agentic system as NL queries but in vector mode.
    
    Args:
        vs_prompt: The vector search query
        workspace: Optional workspace filter
        database_names: Optional list of databases to search
        verbose: Show detailed processing steps
        n_results: Maximum number of results to return (default: 20)
        min_similarity: Minimum similarity threshold 0-1 (default: 0.75)
    
    Returns:
        Dict mapping database_name -> list of content entries
    """
    try:
        processor = get_nl_processor(verbose=verbose, query_mode="vector")
        
        # Process the query with the agentic system (includes modification support)
        result = processor.process_query_with_modification(vs_prompt, workspace=workspace, max_retries=2)
        
        # Check if user chose to quit (exit to terminal)
        if result.get("action") == "quit":
            return {}  # Return empty results to prevent chat from loading
        
        if result["success"] and result["results"]:
            # Extract page IDs from the results
            page_ids = []
            for db_name, entries in result["results"].items():
                for entry in entries:
                    if entry.get('page_id'):
                        page_ids.append(entry['page_id'])
            
            if not page_ids:
                if verbose:
                    print_text("⚠️  No page IDs found in search results", style="yellow")
                return {}
            
            # Use the universal adapter to load full content
            if verbose:
                print_text(f"📄 Loading full content for {len(page_ids)} pages...", style="dim")
            
            from promaia.storage.files import load_content_by_page_ids
            
            full_content = load_content_by_page_ids(
                page_ids=page_ids,
                db_path="data/hybrid_metadata.db",
                expand_gmail_threads=True
            )
            
            if full_content:
                total_loaded = sum(len(pages) for pages in full_content.values())
                if verbose:
                    print(f"Vector search processed: {total_loaded} results loaded")
                    print(f"Goal: {result.get('intent', {}).get('goal', 'Unknown')}")
                    print(f"Mode: Semantic search (vector)")
                    print(f"Sources: {list(full_content.keys())}")
                    if total_loaded > len(page_ids):
                        print(f"   (expanded {total_loaded - len(page_ids)} Gmail thread messages)")
            
            # Return the full content in the expected format
            return full_content
        
        else:
            # Query failed after retries
            error_msg = result.get("error", "Unknown error")
            print_text(f"⚠️  Vector search failed: {error_msg}", style="yellow")
            return {}
    
    except Exception as e:
        print_text(f"❌ Error in vector search processing: {e}", style="red")
        if os.getenv("MAIA_DEBUG") == "1":
            import traceback
            traceback.print_exc()
        return {}


# Alias for backward compatibility
process_nl_query = process_natural_language_to_content

