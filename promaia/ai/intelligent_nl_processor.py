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

# Import our LangGraph system with REAL examples
from .langgraph_query_system_new import IntelligentQueryProcessor


class PromaiLLMAdapter:
    """Adapter to make existing Promaia LLM clients work with LangChain interfaces."""
    
    def __init__(self, client_type: str = "auto"):
        self.client_type = client_type
        self._setup_client()
    
    def _setup_client(self):
        """Setup the appropriate LLM client with fallback handling."""
        if self.client_type == "auto":
            # Try clients in order with proper error handling - CLAUDE FIRST for better constraint following
            api_keys = [
                ("ANTHROPIC_API_KEY", "anthropic"),
                ("OPENAI_API_KEY", "openai"),
                ("GOOGLE_API_KEY", "gemini")
            ]
            
            for env_key, client_type in api_keys:
                if os.getenv(env_key):
                    try:
                        if client_type == "openai":
                            self.client_type = "openai"
                            self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
                            return  # Success
                        elif client_type == "anthropic":
                            self.client_type = "anthropic"
                            self.client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
                            # Test the client with a minimal call
                            test_response = self.client.messages.create(
                                model="claude-3-5-sonnet-20241022",
                                max_tokens=10,
                                messages=[{"role": "user", "content": "test"}]
                            )
                            return  # Success
                        elif client_type == "gemini":
                            self.client_type = "gemini"
                            genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
                            self.client = genai.GenerativeModel('gemini-2.5-pro')
                            return  # Success
                    except Exception as e:
                        print(f"⚠️  Failed to setup {client_type} client: {e}")
                        continue
            
            # If all clients fail, raise an error
            raise ValueError("No working LLM API clients found")
        
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
        if self.client_type == "openai":
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt.strip()}],
                max_tokens=4000
            )
            return MockResponse(response.choices[0].message.content)
            
        elif self.client_type == "anthropic":
            response = self.client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=4000,
                messages=[{"role": "user", "content": prompt.strip()}]
            )
            return MockResponse(response.content[0].text)
            
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
        self.llm = None
        self.processor = None
        self.enabled = False
        
        try:
            # Setup LLM adapter with error handling
            self.llm = PromaiLLMAdapter()
            
            # Create the intelligent processor
            self.processor = IntelligentQueryProcessor(self.llm, db_path)
            self.enabled = True
            
            print(f"✅ Intelligent NL processor initialized with {self.llm.client_type} client")
        except Exception as e:
            print(f"⚠️  didn't work sorry: {e}")

    def process_query(self, user_query: str, scope_databases: List[str] = None) -> Dict[str, Any]:
        """
        Process natural language query using intelligent LangGraph system.
        
        Args:
            user_query: Natural language query
            scope_databases: Optional database scope from -b parameter
            
        Returns:
            Dictionary with grouped results and metadata
        """
        if not self.enabled or not self.processor:
            return {
                "success": False,
                "results": {},
                "intent": None,
                "errors": ["Intelligent processor not available - API credits insufficient or no working LLM client"]
            }
            
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


def _load_full_content_for_entries(db_name: str, metadata_entries: List[Dict[str, Any]], workspace: str = None) -> List[Dict[str, Any]]:
    """
    Load full content for entries that were found by LangGraph but only have metadata.
    
    Args:
        db_name: Database name (e.g., 'gmail')
        metadata_entries: List of entries with just page_id, created_time, etc.
        workspace: Workspace name (e.g., 'trass')
        
    Returns:
        List of entries with full content loaded
    """
    try:
        # Get database configuration - need to find by workspace and nickname
        db_manager = get_database_manager()
        db_config = None
        
        if os.getenv("MAIA_DEBUG") == "1":
            print(f"🔍 Looking for config: db_name='{db_name}', workspace='{workspace}'")
        
        # PRIORITIZE workspace matching - search by workspace and nickname first
        if workspace:
            # Try workspace.db_name format first
            full_db_name = f"{workspace}.{db_name}"
            db_config = db_manager.get_database(full_db_name)
            if db_config and os.getenv("MAIA_DEBUG") == "1":
                print(f"   Found via full name: {full_db_name}")
            
            # If not found, search by workspace and nickname
            if not db_config:
                for config_key, config in db_manager.databases.items():
                    if config.workspace == workspace and config.nickname == db_name:
                        db_config = config
                        if os.getenv("MAIA_DEBUG") == "1":
                            print(f"   Found via search: {config_key} (workspace={config.workspace}, nickname={config.nickname})")
                        break
        
        # Fallback: try direct lookup only if workspace method failed
        if not db_config:
            db_config = db_manager.get_database(db_name)
            if db_config and os.getenv("MAIA_DEBUG") == "1":
                print(f"   Found via direct lookup: {db_name} (workspace={getattr(db_config, 'workspace', 'unknown')})")
        
        if not db_config:
            print(f"⚠️  Database config not found for '{db_name}' (workspace: {workspace}). Returning metadata only.")
            if os.getenv("MAIA_DEBUG") == "1":
                print(f"   Available configs: {list(db_manager.databases.keys())}")
            return metadata_entries
        
        # Extract page IDs from metadata entries
        target_page_ids = set(entry.get('page_id') for entry in metadata_entries if entry.get('page_id'))
        
        if os.getenv("MAIA_DEBUG") == "1":
            print(f"   Target page IDs: {len(target_page_ids)} entries")
            if len(target_page_ids) > 0:
                print(f"   Sample page IDs: {list(target_page_ids)[:3]}")
        
        if not target_page_ids:
            print(f"⚠️  No page IDs found in metadata for '{db_name}'. Returning empty.")
            return []
        
        # For Gmail, we need to load full content from the gmail_content table
        # since the metadata entries only have basic info
        if db_config.source_type in ['gmail']:
            if os.getenv("MAIA_DEBUG") == "1":
                print(f"   Gmail source detected - loading full content from gmail_content table")
            
            try:
                # Load full Gmail content from the specialized gmail_content table
                import sqlite3
                
                # Get the database path - use the standard path
                db_path = "data/hybrid_metadata.db"
                if not os.path.exists(db_path):
                    print(f"⚠️  Database not found at {db_path}")
                    return metadata_entries
                
                with sqlite3.connect(db_path) as conn:
                    conn.row_factory = sqlite3.Row
                    cursor = conn.cursor()
                    
                    # Create a query to get full Gmail content for the target page IDs
                    # Handle both page_id formats: with and without 'msg_' prefix
                    all_page_ids = []
                    for pid in target_page_ids:
                        all_page_ids.append(pid)  # Original format
                        if not pid.startswith('msg_'):
                            all_page_ids.append(f'msg_{pid}')  # Add msg_ prefix
                        else:
                            all_page_ids.append(pid[4:])  # Remove msg_ prefix
                    
                    if os.getenv("MAIA_DEBUG") == "1":
                        print(f"   Searching gmail_content for page_ids: {all_page_ids[:10]}...")
                    
                    placeholders = ','.join(['?' for _ in all_page_ids])
                    query = f"""
                        SELECT 
                            page_id,
                            subject as title,
                            sender_email,
                            sender_name,
                            recipient_emails,
                            message_content,
                            body_snippet,
                            gmail_labels,
                            thread_id,
                            message_id,
                            email_date as created_time,
                            workspace,
                            'gmail' as database_name,
                            'gmail' as content_type
                        FROM gmail_content 
                        WHERE page_id IN ({placeholders})
                    """
                    
                    cursor.execute(query, all_page_ids)
                    gmail_results = []
                    for row in cursor.fetchall():
                        gmail_entry = dict(row)
                        # Add the message content as content for the chat
                        gmail_entry['content'] = gmail_entry.get('message_content', '') or gmail_entry.get('body_snippet', '')
                        gmail_entry['metadata'] = {
                            'sender_email': gmail_entry.get('sender_email', ''),
                            'sender_name': gmail_entry.get('sender_name', ''),
                            'recipient_emails': gmail_entry.get('recipient_emails', ''),
                            'gmail_labels': gmail_entry.get('gmail_labels', ''),
                            'thread_id': gmail_entry.get('thread_id', ''),
                            'message_id': gmail_entry.get('message_id', ''),
                            'body_snippet': gmail_entry.get('body_snippet', ''),
                        }
                        gmail_results.append(gmail_entry)
                    
                    if os.getenv("MAIA_DEBUG") == "1":
                        print(f"   Loaded {len(gmail_results)} full Gmail entries with content")
                    
                    return gmail_results
                    
            except Exception as e:
                print(f"⚠️  Error loading full Gmail content: {e}")
                return metadata_entries
        
        # For Discord and other non-markdown sources, return metadata entries directly
        # since they don't have individual markdown files
        if db_config.source_type in ['discord']:
            if os.getenv("MAIA_DEBUG") == "1":
                print(f"   Discord source detected - returning metadata entries directly")
                print(f"   Discord entries to return: {len(metadata_entries)}")
                if metadata_entries:
                    sample = metadata_entries[0]
                    print(f"   Sample Discord entry content length: {len(str(sample.get('content', '')))}")
            return metadata_entries
        
        # Load all content from database and filter to matching entries
        if os.getenv("MAIA_DEBUG") == "1":
            print(f"   Loading content via markdown files for {db_config.source_type} source")
        
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
        
        if os.getenv("MAIA_DEBUG") == "1":
            print(f"   Loaded {len(all_pages)} total pages from registry")
            if len(all_pages) > 0:
                sample_page = all_pages[0]
                print(f"   Sample page keys: {list(sample_page.keys()) if hasattr(sample_page, 'keys') else 'Not a dict'}")
                print(f"   Sample page_id: {sample_page.get('page_id') if hasattr(sample_page, 'get') else 'No get method'}")
            print(f"   Found {len(matching_pages)} matching pages")
            if matching_pages:
                sample_match = matching_pages[0]
                print(f"   Sample matching page content length: {len(str(sample_match.get('content', '')))}")
        
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
    with true AI reasoning. Falls back to pattern-based processing if intelligent processing fails.
    """
    
    try:
        # Try intelligent processor first
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
            
            # DEBUG: Show what was found by the intelligent processor
            if os.getenv("MAIA_DEBUG") == "1":
                print(f"\n🔍 RAW RESULTS FROM LANGGRAPH:")
                for db_name, entries in result["results"].items():
                    print(f"   {db_name}: {len(entries)} entries")
                    if entries:
                        sample_entry = entries[0]
                        print(f"   Sample entry keys: {list(sample_entry.keys())}")
                        print(f"   Sample page_id: {sample_entry.get('page_id', 'N/A')}")
                        print(f"   Sample content preview: {str(sample_entry.get('content', sample_entry.get('message_content', 'N/A')))[:100]}...")
            
            # IMPORTANT: Load full content for each found entry
            # The LangGraph system only returns metadata - we need actual content for chat
            enriched_results = {}
            for db_name, entries in result["results"].items():
                if os.getenv("MAIA_DEBUG") == "1":
                    print(f"\n🔄 LOADING FULL CONTENT for {db_name} ({len(entries)} entries)")
                enriched_results[db_name] = _load_full_content_for_entries(db_name, entries, workspace)
            
            return enriched_results
        else:
            # Intelligent processing failed, try pattern-based fallback
            print("⚠️  Intelligent processing failed, trying pattern-based fallback...")
            return _try_pattern_based_fallback(nl_prompt, workspace, database_names)
            
    except Exception as e:
        print(f"⚠️  Intelligent NL processing error: {e}")
        print("   Trying pattern-based fallback...")
        return _try_pattern_based_fallback(nl_prompt, workspace, database_names)


def _try_pattern_based_fallback(nl_prompt: str, workspace: str = None, 
                               database_names: List[str] = None) -> Dict[str, List[Dict[str, Any]]]:
    """Fallback to pattern-based processing when intelligent processing fails."""
    try:
        from .pattern_based_nl import PatternBasedNLProcessor
        
        pattern_processor = PatternBasedNLProcessor()
        # Use the pattern-based processor's process_query method if available
        if hasattr(pattern_processor, 'process_query'):
            results = pattern_processor.process_query(nl_prompt, workspace, database_names)
            if results:
                print(f"✅ Pattern-based fallback succeeded: {sum(len(v) for v in results.values())} results")
                return results
        
        print("❌ Pattern-based fallback also failed")
        return {}
    except Exception as e:
        print(f"❌ Pattern-based fallback error: {e}")
        return {}