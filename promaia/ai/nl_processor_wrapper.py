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

def get_nl_processor() -> AgenticNLQueryProcessor:
    """Get or create the global agentic NL processor."""
    global _processor
    if _processor is None:
        _processor = AgenticNLQueryProcessor(debug=os.getenv("MAIA_DEBUG") == "1")
    return _processor


def process_natural_language_to_content(
    nl_prompt: str, 
    workspace: str = None, 
    database_names: List[str] = None
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Process natural language queries using the new agentic system.
    
    This is the main integration point that replaces the old LangGraph system.
    It provides a backward-compatible interface for the CLI and Chat.
    
    Args:
        nl_prompt: The natural language query
        workspace: Optional workspace filter
        database_names: Optional list of databases to search
    
    Returns:
        Dict mapping database_name -> list of content entries
    """
    try:
        processor = get_nl_processor()
        
        # Process the query with the agentic system (includes modification support)
        result = processor.process_query_with_modification(nl_prompt, workspace=workspace, max_retries=2)
        
        # Check if user chose to quit (exit to terminal)
        if result.get("action") == "quit":
            return {}  # Return empty results to prevent chat from loading
        
        if result["success"] and result["results"]:
            total_count = sum(len(items) for items in result["results"].values())
            
            print(f"Intelligent query processed: {total_count} results")
            print(f"Goal: {result.get('intent', {}).get('goal', 'Unknown')}")
            print(f"Complexity: Agentic (with retry)")
            print(f"Sources: {list(result['results'].keys())}")
            
            # Return the results in the expected format
            return result["results"]
        
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


# Alias for backward compatibility
process_nl_query = process_natural_language_to_content

