"""
Intelligent natural language processor using LangGraph.
Integrates with existing Promaia LLM clients (Anthropic, OpenAI, Gemini).
"""
import os
from typing import List, Dict, Any
from anthropic import Anthropic
from openai import OpenAI
import google.generativeai as genai
from promaia.config.databases import get_database_manager
from promaia.storage.files import read_markdown_files_with_registry

# Load environment variables
from promaia.utils.config import load_environment
load_environment()

# Import our LangGraph system
from .langgraph_query_system import IntelligentQueryProcessor


class PromaiLLMAdapter:
    """Adapter to make existing Promaia LLM clients work with LangChain interfaces."""
    
    def __init__(self, client_type: str = "auto"):
        self.client_type = client_type
        self._setup_client()
    
    def _setup_client(self):
        """Setup the appropriate LLM client."""
        if self.client_type == "auto":
            # Use the same logic as existing system
            if os.getenv("ANTHROPIC_API_KEY"):
                self.client_type = "anthropic"
                self.client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
            elif os.getenv("OPENAI_API_KEY"):
                self.client_type = "openai" 
                self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
            elif os.getenv("GOOGLE_API_KEY"):
                self.client_type = "gemini"
                genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
                self.client = genai.GenerativeModel('gemini-2.5-pro')
            else:
                raise ValueError("No LLM API keys found")
        
    def invoke(self, messages):
        """LangChain-compatible invoke method."""
        # Extract message content
        if isinstance(messages, list):
            # Combine system and user messages
            system_msg = ""
            user_msg = ""
            
            for msg in messages:
                if hasattr(msg, 'content'):
                    content = msg.content
                    if 'SystemMessage' in str(type(msg)):
                        system_msg += content + "\n"
                    else:
                        user_msg += content + "\n"
                else:
                    user_msg += str(msg) + "\n"
            
            prompt = system_msg + "\n" + user_msg
        else:
            prompt = str(messages)
            
        # Call the appropriate client
        if self.client_type == "anthropic":
            response = self.client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=4000,
                messages=[{"role": "user", "content": prompt.strip()}]
            )
            return MockResponse(response.content[0].text)
            
        elif self.client_type == "openai":
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt.strip()}],
                max_tokens=4000
            )
            return MockResponse(response.choices[0].message.content)
            
        elif self.client_type == "gemini":
            response = self.client.generate_content(prompt.strip())
            return MockResponse(response.text)
        
        else:
            raise ValueError(f"Unknown client type: {self.client_type}")
    
    def with_structured_output(self, schema_class):
        """Mock structured output for compatibility."""
        return StructuredOutputAdapter(self, schema_class)


class MockResponse:
    """Mock response object for LangChain compatibility."""
    def __init__(self, content):
        self.content = content


class StructuredOutputAdapter:
    """Adapter for structured output generation."""
    
    def __init__(self, llm_adapter, schema_class):
        self.llm_adapter = llm_adapter
        self.schema_class = schema_class
        
    def invoke(self, messages):
        """Generate structured output by prompting for JSON."""
        
        # Add JSON schema instruction
        json_instruction = f"""
        
IMPORTANT: Return your response as valid JSON that matches this exact schema:
{self.schema_class.schema_json(indent=2)}

Return ONLY the JSON object, no other text or formatting.
"""
        
        # Add instruction to messages
        if isinstance(messages, list) and messages:
            messages[-1].content += json_instruction
        
        # Get response
        response = self.llm_adapter.invoke(messages)
        response_text = response.content.strip()
        
        # Clean up response (remove markdown formatting if present)
        if response_text.startswith("```json"):
            response_text = response_text.replace("```json", "").replace("```", "").strip()
        elif response_text.startswith("```"):
            response_text = response_text.replace("```", "").strip()
            
        # Parse JSON and return structured object
        try:
            import json
            parsed_data = json.loads(response_text)
            return self.schema_class(**parsed_data)
        except Exception as e:
            print(f"⚠️  Structured output parsing failed: {e}")
            print(f"Response was: {response_text[:200]}...")
            # Return a default instance
            return self._create_default_instance()
    
    def _create_default_instance(self):
        """Create a default instance when parsing fails."""
        try:
            # Try to create with minimal required fields
            if hasattr(self.schema_class, '__fields__'):
                defaults = {}
                for field_name, field_info in self.schema_class.__fields__.items():
                    if field_info.default is not None:
                        defaults[field_name] = field_info.default
                    elif hasattr(field_info, 'default_factory') and field_info.default_factory:
                        defaults[field_name] = field_info.default_factory()
                    else:
                        # Set basic defaults based on type
                        if field_info.type_ == str:
                            defaults[field_name] = "unknown"
                        elif field_info.type_ == list:
                            defaults[field_name] = []
                        elif field_info.type_ == dict:
                            defaults[field_name] = {}
                            
                return self.schema_class(**defaults)
        except:
            pass
            
        # Ultimate fallback
        return None


class IntelligentNaturalLanguageProcessor:
    """
    Main processor that integrates LangGraph intelligence with Promaia's existing systems.
    """
    
    def __init__(self, db_path: str = "data/hybrid_metadata.db"):
        self.db_path = db_path
        
        # Setup LLM adapter  
        self.llm = PromaiLLMAdapter()
        
        # Create the intelligent processor
        self.processor = IntelligentQueryProcessor(self.llm, db_path)
        
        print(f"✅ Intelligent NL processor initialized with {self.llm.client_type} client")

    def process_query(self, user_query: str, scope_databases: List[str] = None) -> Dict[str, Any]:
        """
        Process natural language query using intelligent LangGraph system.
        
        Args:
            user_query: Natural language query
            scope_databases: Optional database scope from -b parameter
            
        Returns:
            Dictionary with grouped results and metadata
        """
        try:
            return self.processor.process_query(user_query, scope_databases)
        except Exception as e:
            print(f"❌ Intelligent processing failed: {e}")
            return {
                "success": False,
                "results": {},
                "intent": None,
                "errors": [str(e)]
            }


def _load_full_content_for_entries(db_name: str, metadata_entries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Load full content for entries that were found by LangGraph but only have metadata.
    
    Args:
        db_name: Database name (e.g., 'journal')
        metadata_entries: List of entries with just page_id, created_time, etc.
        
    Returns:
        List of entries with full content loaded
    """
    try:
        # Get database configuration
        db_manager = get_database_manager()
        db_config = db_manager.get_database(db_name)
        
        if not db_config:
            print(f"⚠️  Database config not found for '{db_name}'. Returning metadata only.")
            return metadata_entries
        
        # Extract page IDs from metadata entries
        target_page_ids = set(entry.get('page_id') for entry in metadata_entries if entry.get('page_id'))
        
        if not target_page_ids:
            print(f"⚠️  No page IDs found in metadata for '{db_name}'. Returning empty.")
            return []
        
        # Load all content from database and filter to matching entries
        all_pages = read_markdown_files_with_registry(
            database_config=db_config,
            days=None,  # Load all entries to find the ones we need
            comparison_filters={},
            property_filters={}
        )
        
        # Filter to only the entries we want based on page_id or date matching
        matching_pages = []
        for page in all_pages:
            # Try to match by page_id if available
            if hasattr(page, 'get') and page.get('page_id') in target_page_ids:
                matching_pages.append(page)
            # Otherwise try to match by date/title for fallback
            elif hasattr(page, 'get'):
                page_date = page.get('created_time', '')
                for meta_entry in metadata_entries:
                    if meta_entry.get('created_time') == page_date:
                        matching_pages.append(page)
                        break
        
        print(f"📄 Loaded {len(matching_pages)} full content entries for {db_name}")
        return matching_pages
        
    except Exception as e:
        print(f"⚠️  Error loading full content for '{db_name}': {e}")
        return metadata_entries  # Return metadata if content loading fails


def process_natural_language_to_content(nl_prompt: str, workspace: str = None, 
                                      database_names: List[str] = None) -> Dict[str, List[Dict[str, Any]]]:
    """
    Drop-in replacement for the old system using intelligent LangGraph processing.
    
    This is the main integration point that replaces both Vanna.ai and my regex patterns
    with true AI reasoning.
    """
    
    try:
        # Create intelligent processor
        processor = IntelligentNaturalLanguageProcessor()
        
        # Process the query with AI reasoning
        result = processor.process_query(nl_prompt, database_names)
        
        if result["success"] and result["results"]:
            total_count = sum(len(items) for items in result["results"].values())
            intent = result.get("intent", {})
            
            print(f"✅ Intelligent query processed: {total_count} results")
            print(f"   Goal: {intent.get('user_goal', 'Unknown')}")
            print(f"   Complexity: {intent.get('complexity_level', 'Unknown')}")
            print(f"   Sources: {list(result['results'].keys())}")
            
            # IMPORTANT: Load full content for each found entry
            # The LangGraph system only returns metadata - we need actual content for chat
            enriched_results = {}
            for db_name, entries in result["results"].items():
                enriched_results[db_name] = _load_full_content_for_entries(db_name, entries)
            
            return enriched_results
        else:
            errors = result.get("errors", ["Unknown error"])
            print(f"❌ Intelligent query failed: {'; '.join(errors)}")
            return {}
            
    except Exception as e:
        print(f"❌ Intelligent NL processing error: {e}")
        return {}