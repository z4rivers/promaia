"""
Natural language query processing using Vanna AI for text-to-SQL generation.
Converts natural language to SQL using trained AI models and executes against the unified_content view.
"""
import json
import re
import os
import sqlite3
import glob
from typing import List, Tuple, Optional, Dict, Any
from datetime import datetime, timedelta

from promaia.utils.config import load_environment
from promaia.config.databases import get_database_manager
from anthropic import Anthropic
from openai import OpenAI
import google.generativeai as genai

# Load environment variables
load_environment()


class VannaSQLGenerator:
    """Vanna AI-based SQL generator for natural language queries."""
    
    def __init__(self):
        self.vn_client = None
        self.initialized = False
        self._setup_vanna()
    
    def _setup_vanna(self):
        """Initialize Vanna AI with our schema and training data."""
        try:
            import vanna as vn
            from vanna.chromadb import ChromaDB_VectorStore
            from vanna.openai import OpenAI_Chat
            
            # Get OpenAI API key from environment
            import os
            
            # Load environment variables if needed
            try:
                from promaia.utils.config import load_environment
                load_environment()
            except:
                # Fallback to loading .env manually
                from dotenv import load_dotenv
                load_dotenv()
            
            openai_api_key = os.getenv('OPENAI_API_KEY')
            
            if not openai_api_key:
                print("⚠️  No OPENAI_API_KEY found in environment")
                print("📄 Using fallback SQL generation only")
                self.initialized = False
                return
            
            # Create a simple Vanna class with local storage
            class SimpleVanna(ChromaDB_VectorStore, OpenAI_Chat):
                def __init__(self, config=None):
                    ChromaDB_VectorStore.__init__(self, config=config)
                    OpenAI_Chat.__init__(self, config=config)
            
            # Initialize with better model and configuration for complex queries
            self.vn_client = SimpleVanna(config={
                'model': 'gpt-4o-mini',  # Use GPT-4 for better reasoning
                'api_key': openai_api_key,
                'temperature': 0.1,  # Lower temperature for more consistent results
                'max_tokens': 1000
            })
            
            # Train on our schema and examples
            self._train_on_schema()
            self.initialized = True
            print("✅ Vanna AI initialized successfully with OpenAI API")
            
        except Exception as e:
            print(f"⚠️  Vanna AI initialization failed: {e}")
            print("📄 Using fallback SQL generation")
            self.initialized = False
    
    def _train_on_schema(self):
        """Train Vanna on our database schema and key examples."""
        # Define our schema
        schema_sql = """
        CREATE VIEW unified_content AS
        SELECT 
            page_id, workspace, database_name, content_type, file_path, title,
            created_time,  -- ISO 8601: '2024-12-26T02:05:00.000Z'
            last_edited_time, synced_time, file_size, checksum,
            status, featured, priority, category,
            sender_email, sender_name, has_attachments, is_unread, thread_id,
            metadata
        FROM hybrid_content_registry;
        """
        
        # Train on schema
        self.vn_client.train(ddl=schema_sql)
        
        # Comprehensive training examples - covering complex temporal patterns
        examples = [
            # The key problematic query - first week of every month pattern
            ("first week of journal entries from every month since December 2024", 
             "SELECT page_id, title, created_time, last_edited_time, file_path, metadata, database_name FROM unified_content WHERE database_name = 'journal' AND created_time >= '2024-12-01' AND ((SUBSTR(created_time, 1, 7) = '2024-12' AND CAST(SUBSTR(created_time, 9, 2) AS INTEGER) <= 7) OR (SUBSTR(created_time, 1, 7) = '2025-01' AND CAST(SUBSTR(created_time, 9, 2) AS INTEGER) <= 7) OR (SUBSTR(created_time, 1, 7) = '2025-02' AND CAST(SUBSTR(created_time, 9, 2) AS INTEGER) <= 7) OR (SUBSTR(created_time, 1, 7) = '2025-03' AND CAST(SUBSTR(created_time, 9, 2) AS INTEGER) <= 7) OR (SUBSTR(created_time, 1, 7) = '2025-04' AND CAST(SUBSTR(created_time, 9, 2) AS INTEGER) <= 7) OR (SUBSTR(created_time, 1, 7) = '2025-05' AND CAST(SUBSTR(created_time, 9, 2) AS INTEGER) <= 7) OR (SUBSTR(created_time, 1, 7) = '2025-06' AND CAST(SUBSTR(created_time, 9, 2) AS INTEGER) <= 7) OR (SUBSTR(created_time, 1, 7) = '2025-07' AND CAST(SUBSTR(created_time, 9, 2) AS INTEGER) <= 7) OR (SUBSTR(created_time, 1, 7) = '2025-08' AND CAST(SUBSTR(created_time, 9, 2) AS INTEGER) <= 7))"),
            
            # Variations of the same pattern
            ("first week of journal entries from every month since 2024-12", 
             "SELECT page_id, title, created_time, last_edited_time, file_path, metadata, database_name FROM unified_content WHERE database_name = 'journal' AND created_time >= '2024-12-01' AND ((SUBSTR(created_time, 1, 7) = '2024-12' AND CAST(SUBSTR(created_time, 9, 2) AS INTEGER) <= 7) OR (SUBSTR(created_time, 1, 7) = '2025-01' AND CAST(SUBSTR(created_time, 9, 2) AS INTEGER) <= 7) OR (SUBSTR(created_time, 1, 7) = '2025-02' AND CAST(SUBSTR(created_time, 9, 2) AS INTEGER) <= 7) OR (SUBSTR(created_time, 1, 7) = '2025-03' AND CAST(SUBSTR(created_time, 9, 2) AS INTEGER) <= 7) OR (SUBSTR(created_time, 1, 7) = '2025-04' AND CAST(SUBSTR(created_time, 9, 2) AS INTEGER) <= 7) OR (SUBSTR(created_time, 1, 7) = '2025-05' AND CAST(SUBSTR(created_time, 9, 2) AS INTEGER) <= 7) OR (SUBSTR(created_time, 1, 7) = '2025-06' AND CAST(SUBSTR(created_time, 9, 2) AS INTEGER) <= 7) OR (SUBSTR(created_time, 1, 7) = '2025-07' AND CAST(SUBSTR(created_time, 9, 2) AS INTEGER) <= 7) OR (SUBSTR(created_time, 1, 7) = '2025-08' AND CAST(SUBSTR(created_time, 9, 2) AS INTEGER) <= 7))"),
            
            # Other "first week" patterns to reinforce the concept
            ("first week of April 2025 journal entries", 
             "SELECT page_id, title, created_time, last_edited_time, file_path, metadata, database_name FROM unified_content WHERE database_name = 'journal' AND created_time >= '2025-04-01' AND created_time < '2025-04-08'"),
            
            ("first week of this month journal entries", 
             "SELECT page_id, title, created_time, last_edited_time, file_path, metadata, database_name FROM unified_content WHERE database_name = 'journal' AND SUBSTR(created_time, 1, 7) = SUBSTR(date('now'), 1, 7) AND CAST(SUBSTR(created_time, 9, 2) AS INTEGER) <= 7"),
            
            # Simple temporal queries
            ("recent journal entries", 
             "SELECT page_id, title, created_time, last_edited_time, file_path, metadata, database_name FROM unified_content WHERE database_name = 'journal' AND created_time >= date('now', '-7 days')"),
            
            ("journal entries from December 2024", 
             "SELECT page_id, title, created_time, last_edited_time, file_path, metadata, database_name FROM unified_content WHERE database_name = 'journal' AND created_time LIKE '2024-12%'"),
            
            # Email queries with sender filters
            ("emails from john", 
             "SELECT page_id, title, created_time, last_edited_time, file_path, metadata, database_name FROM unified_content WHERE database_name = 'gmail' AND (sender_email LIKE '%john%' OR sender_name LIKE '%john%')"),
            
            # Email content-based searches
            ("emails about invoice", 
             "SELECT page_id, title, created_time, last_edited_time, file_path, metadata, database_name FROM unified_content WHERE database_name = 'gmail' AND (title LIKE '%invoice%' OR metadata LIKE '%invoice%')"),
            
            ("emails containing receipt", 
             "SELECT page_id, title, created_time, last_edited_time, file_path, metadata, database_name FROM unified_content WHERE database_name = 'gmail' AND (title LIKE '%receipt%' OR metadata LIKE '%receipt%')"),
            
            ("gmails that contain meeting", 
             "SELECT page_id, title, created_time, last_edited_time, file_path, metadata, database_name FROM unified_content WHERE database_name = 'gmail' AND (title LIKE '%meeting%' OR metadata LIKE '%meeting%')"),
            
            ("emails with keywords urgent or important", 
             "SELECT page_id, title, created_time, last_edited_time, file_path, metadata, database_name FROM unified_content WHERE database_name = 'gmail' AND (title LIKE '%urgent%' OR metadata LIKE '%urgent%' OR title LIKE '%important%' OR metadata LIKE '%important%')"),
            
            ("all emails that contain any of the following keywords: payment, invoice, bill", 
             "SELECT page_id, title, created_time, last_edited_time, file_path, metadata, database_name FROM unified_content WHERE database_name = 'gmail' AND (title LIKE '%payment%' OR metadata LIKE '%payment%' OR title LIKE '%invoice%' OR metadata LIKE '%invoice%' OR title LIKE '%bill%' OR metadata LIKE '%bill%')"),
            
            ("all trass gmails that contain any of the following keywords: project, deadline, client", 
             "SELECT page_id, title, created_time, last_edited_time, file_path, metadata, database_name FROM unified_content WHERE database_name = 'gmail' AND (title LIKE '%project%' OR metadata LIKE '%project%' OR title LIKE '%deadline%' OR metadata LIKE '%deadline%' OR title LIKE '%client%' OR metadata LIKE '%client%')"),
            
            # Journal content-based searches
            ("journal entries about work", 
             "SELECT page_id, title, created_time, last_edited_time, file_path, metadata, database_name FROM unified_content WHERE database_name = 'journal' AND (title LIKE '%work%' OR metadata LIKE '%work%')"),
            
            ("notes containing ideas or brainstorm", 
             "SELECT page_id, title, created_time, last_edited_time, file_path, metadata, database_name FROM unified_content WHERE database_name = 'journal' AND (title LIKE '%ideas%' OR metadata LIKE '%ideas%' OR title LIKE '%brainstorm%' OR metadata LIKE '%brainstorm%')"),
            
            # Workspace.database format handling - extract just the database name
            ("trass.journal entries from last week", 
             "SELECT page_id, title, created_time, last_edited_time, file_path, metadata, database_name FROM unified_content WHERE database_name = 'journal' AND created_time >= date('now', '-7 days')"),
            
            ("koii.gmail emails from yesterday", 
             "SELECT page_id, title, created_time, last_edited_time, file_path, metadata, database_name FROM unified_content WHERE database_name = 'gmail' AND created_time >= date('now', '-1 day')"),
            
            ("trass.journal first week of journal entries from april 2025", 
             "SELECT page_id, title, created_time, last_edited_time, file_path, metadata, database_name FROM unified_content WHERE database_name = 'journal' AND created_time >= '2025-04-01' AND created_time < '2025-04-08'"),
            
            # More temporal patterns
            ("entries from this month", 
             "SELECT page_id, title, created_time, last_edited_time, file_path, metadata, database_name FROM unified_content WHERE database_name = 'journal' AND SUBSTR(created_time, 1, 7) = SUBSTR(date('now'), 1, 7)"),
            
            # Last week of each month pattern (to teach the AI about complex date logic)
            ("last week of each month journal entries since January 2025",
             "SELECT page_id, title, created_time, last_edited_time, file_path, metadata, database_name FROM unified_content WHERE database_name = 'journal' AND created_time >= '2025-01-01' AND ((SUBSTR(created_time, 1, 7) = '2025-01' AND CAST(SUBSTR(created_time, 9, 2) AS INTEGER) >= 25) OR (SUBSTR(created_time, 1, 7) = '2025-02' AND CAST(SUBSTR(created_time, 9, 2) AS INTEGER) >= 22) OR (SUBSTR(created_time, 1, 7) = '2025-03' AND CAST(SUBSTR(created_time, 9, 2) AS INTEGER) >= 25) OR (SUBSTR(created_time, 1, 7) = '2025-04' AND CAST(SUBSTR(created_time, 9, 2) AS INTEGER) >= 24) OR (SUBSTR(created_time, 1, 7) = '2025-05' AND CAST(SUBSTR(created_time, 9, 2) AS INTEGER) >= 25) OR (SUBSTR(created_time, 1, 7) = '2025-06' AND CAST(SUBSTR(created_time, 9, 2) AS INTEGER) >= 24) OR (SUBSTR(created_time, 1, 7) = '2025-07' AND CAST(SUBSTR(created_time, 9, 2) AS INTEGER) >= 25) OR (SUBSTR(created_time, 1, 7) = '2025-08' AND CAST(SUBSTR(created_time, 9, 2) AS INTEGER) >= 25))")
        ]
        
        # Train on examples
        for question, sql in examples:
            self.vn_client.train(question=question, sql=sql)
    
    def generate_sql(self, question: str) -> str:
        """Generate SQL query from natural language question."""
        if not self.initialized:
            return self._fallback_sql_generation(question)
        
        try:
            # Configure Vanna to not require database introspection
            sql_query = self.vn_client.generate_sql(question, allow_llm_to_see_data=False)
            
            # Check if it's an intermediate query or explanation - if so, use fallback
            if any(phrase in sql_query for phrase in [
                "intermediate_sql", 
                "The LLM is not allowed",
                "cannot be answered",
                "requires extracting data",
                "additional information",
                "This question cannot"
            ]):
                print("⚠️  Vanna returned explanation instead of SQL, using fallback")
                return self._fallback_sql_generation(question)
            
            # Also check if it doesn't look like SQL at all
            if not sql_query.strip().upper().startswith("SELECT"):
                print("⚠️  Vanna didn't return valid SQL, using fallback")
                return self._fallback_sql_generation(question)
            
            # Ensure the query has a database_name filter
            if "database_name" not in sql_query:
                sql_query = self._ensure_database_filter(sql_query, question)
            
            return sql_query
        except Exception as e:
            print(f"⚠️  Vanna SQL generation failed: {e}")
            return self._fallback_sql_generation(question)
    
    def _ensure_database_filter(self, sql_query: str, question: str) -> str:
        """Ensure the SQL query has a database_name filter."""
        # Simple heuristic: if the question mentions database types, add appropriate filter
        if any(word in question.lower() for word in ['journal', 'diary', 'note']):
            if "WHERE" in sql_query:
                return sql_query.replace("WHERE", "WHERE database_name = 'journal' AND")
            else:
                return sql_query.replace("FROM unified_content", "FROM unified_content WHERE database_name = 'journal'")
        elif any(word in question.lower() for word in ['email', 'gmail', 'mail']):
            if "WHERE" in sql_query:
                return sql_query.replace("WHERE", "WHERE database_name = 'gmail' AND")
            else:
                return sql_query.replace("FROM unified_content", "FROM unified_content WHERE database_name = 'gmail'")
        
        # Default to journal
        if "WHERE" in sql_query:
            return sql_query.replace("WHERE", "WHERE database_name = 'journal' AND")
        else:
            return sql_query.replace("FROM unified_content", "FROM unified_content WHERE database_name = 'journal'")
    
    def _fallback_sql_generation(self, nl_prompt: str) -> str:
        """Simple fallback SQL generation when Vanna fails - handles only basic cases."""
        import re
        from datetime import datetime, timedelta
        
        # Clean and normalize the prompt
        prompt_lower = nl_prompt.lower().strip()
        
        # Determine database type
        database_name = 'journal'  # Default
        if any(word in prompt_lower for word in ['email', 'gmail', 'mail']):
            database_name = 'gmail'
        elif any(word in prompt_lower for word in ['story', 'stories']):
            database_name = 'stories'
        elif any(word in prompt_lower for word in ['epic', 'epics']):
            database_name = 'epics'
        elif any(word in prompt_lower for word in ['cpj', 'project']):
            database_name = 'cpj'
        
        # Extract workspace.database format and convert to just database name
        workspace_db_match = re.search(r'\b(\w+)\.(\w+)\b', prompt_lower)
        if workspace_db_match:
            _, db_part = workspace_db_match.groups()
            database_name = db_part
        
        # Base SQL structure
        base_sql = f"SELECT page_id, title, created_time, last_edited_time, file_path, metadata, database_name FROM unified_content WHERE database_name = '{database_name}'"
        
        # Only handle simple date patterns - let Vanna handle complex ones
        current_date = datetime.now()
        
        if re.search(r'last\s*week|recent', prompt_lower):
            week_ago = (current_date - timedelta(days=7)).strftime('%Y-%m-%d')
            base_sql += f" AND created_time >= '{week_ago}'"
        
        elif re.search(r'yesterday', prompt_lower):
            yesterday = (current_date - timedelta(days=1)).strftime('%Y-%m-%d')
            base_sql += f" AND created_time >= '{yesterday}'"
        
        elif re.search(r'december\s*2024', prompt_lower):
            base_sql += " AND created_time LIKE '2024-12%'"
        
        # Email-specific filters (only for gmail database)
        if database_name == 'gmail':
            sender_match = re.search(r'from\s+(\w+)', prompt_lower)
            if sender_match:
                sender = sender_match.group(1)
                base_sql += f" AND (sender_email LIKE '%{sender}%' OR sender_name LIKE '%{sender}%')"
        
        # Order by created_time for recency
        if 'recent' in prompt_lower:
            base_sql += " ORDER BY created_time DESC"
        
        # For complex queries that we can't handle, add a comment to explain
        if any(phrase in prompt_lower for phrase in ['first week.*every month', 'each month', 'every month']):
            print("⚠️  Complex temporal query detected - this should be handled by Vanna AI training")
        
        return base_sql


# Global instance
_sql_generator = None

def get_sql_generator() -> VannaSQLGenerator:
    """Get singleton instance of VannaSQLGenerator."""
    global _sql_generator
    if _sql_generator is None:
        _sql_generator = VannaSQLGenerator()
    return _sql_generator


def get_ai_client():
    """Get an available AI client, preferring Anthropic, then Gemini, then Local Llama, then OpenAI."""
    if os.getenv("ANTHROPIC_API_KEY"):
        return Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    elif os.getenv("GOOGLE_API_KEY"):
        genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
        return genai
    elif os.getenv("LLAMA_BASE_URL"):
        # Try to initialize local Llama client
        try:
            import requests
            llama_url = os.getenv("LLAMA_BASE_URL", "http://localhost:11434")
            test_url = f"{llama_url.rstrip('/')}/api/tags" if "ollama" in llama_url or ":11434" in llama_url else f"{llama_url.rstrip('/')}/v1/models"
            response = requests.get(test_url, timeout=2)
            if response.status_code == 200:
                return OpenAI(
                    base_url=f"{llama_url.rstrip('/')}/v1",
                    api_key=os.getenv("LLAMA_API_KEY", "local-llama")
                )
        except Exception:
            pass
    elif os.getenv("OPENAI_API_KEY"):
        return OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    else:
        raise ValueError("No AI API key configured. Please set ANTHROPIC_API_KEY, GOOGLE_API_KEY, LLAMA_BASE_URL, or OPENAI_API_KEY")


def extract_json_from_response(text: str) -> Dict[str, Any]:
    """
    Extract JSON from AI response that may contain conversational text.
    
    This function handles cases where the AI includes explanatory text
    before or after the JSON response.
    """
    # Try to find JSON blocks using multiple approaches
    
    # Method 1: Look for balanced braces with proper nesting
    brace_count = 0
    start_idx = -1
    
    for i, char in enumerate(text):
        if char == '{':
            if brace_count == 0:
                start_idx = i
            brace_count += 1
        elif char == '}':
            brace_count -= 1
            if brace_count == 0 and start_idx != -1:
                # Found a complete JSON block
                json_candidate = text[start_idx:i+1]
                try:
                    return json.loads(json_candidate)
                except json.JSONDecodeError:
                    # Continue looking for other JSON blocks
                    continue
    
    # Method 2: Look for content between markdown code blocks
    code_block_patterns = [
        r'```json\s*\n(.*?)\n```',
        r'```\s*\n(.*?)\n```',
        r'`(.*?)`'
    ]
    
    for pattern in code_block_patterns:
        matches = re.findall(pattern, text, re.DOTALL)
        for match in matches:
            try:
                return json.loads(match.strip())
            except json.JSONDecodeError:
                continue
    
    # Method 3: Try to parse the entire text as JSON (fallback)
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        pass
    
    # Method 4: Look for lines that start with { and try to parse from there
    lines = text.split('\n')
    for i, line in enumerate(lines):
        if line.strip().startswith('{'):
            # Try to parse from this line to the end
            remaining_text = '\n'.join(lines[i:])
            try:
                return json.loads(remaining_text)
            except json.JSONDecodeError:
                # Try to find the end of the JSON object
                brace_count = 0
                json_end = -1
                for j, char in enumerate(remaining_text):
                    if char == '{':
                        brace_count += 1
                    elif char == '}':
                        brace_count -= 1
                        if brace_count == 0:
                            json_end = j + 1
                            break
                
                if json_end > 0:
                    json_text = remaining_text[:json_end]
                    try:
                        return json.loads(json_text)
                    except json.JSONDecodeError:
                        continue
                
                # Try just this line
                try:
                    return json.loads(line.strip())
                except json.JSONDecodeError:
                    continue
    
    return {}


def process_natural_language_query(nl_prompt: str, workspace: str = None, schema_info: str = None) -> Tuple[Optional[str], List[str]]:
    """
    Process natural language query using Vanna AI to generate SQL.
    
    Returns:
        Tuple of (sql_query, errors)
    """
    try:
        sql_generator = get_sql_generator()
        sql_query = sql_generator.generate_sql(nl_prompt)
        
        print(f"🔍 Generated SQL Query:")
        print(f"   {sql_query}")
        
        return sql_query, []
    except Exception as e:
        error_msg = f"Failed to generate SQL query: {e}"
        return None, [error_msg]


def execute_natural_language_queries(nl_prompt: str, workspace: str = None) -> Tuple[List[Dict[str, Any]], List[str]]:
    """
    Execute natural language queries using Vanna AI.
    
    Returns:
        Tuple of (results, errors)
    """
    # Generate SQL using Vanna AI
    sql_query, errors = process_natural_language_query(nl_prompt, workspace)
    
    if not sql_query or errors:
        return [], errors
    
    # Execute the SQL query
    try:
        from promaia.storage.unified_query import get_query_interface
        query_interface = get_query_interface()
        
        # Get workspace for database context
        workspace_for_db = workspace
        if not workspace_for_db:
            from promaia.config.workspaces import get_workspace_manager
            workspace_manager = get_workspace_manager()
            available_workspaces = workspace_manager.list_workspaces()
            workspace_for_db = available_workspaces[0] if available_workspaces else "koii"
        
        # Get database context - handle both dict and object returns
        db_context = query_interface.get_database_context(workspace_for_db)
        
        # Handle different return types from query_interface
        connection = None
        if hasattr(db_context, 'connection'):
            connection = db_context.connection
        elif isinstance(db_context, dict) and 'connection' in db_context:
            connection = db_context['connection']
        elif hasattr(query_interface, 'db_path'):
            # Fallback: create direct SQLite connection
            import sqlite3
            connection = sqlite3.connect(query_interface.db_path)
        
        if not connection:
            return [], ["No database connection available"]
        
        # Execute SQL query
        cursor = connection.cursor()
        cursor.execute(sql_query)
        
        # Get column names
        columns = [desc[0] for desc in cursor.description]
        
        # Fetch results and convert to dictionaries
        results = []
        for row in cursor.fetchall():
            row_dict = dict(zip(columns, row))
            results.append(row_dict)
        
        print(f"✅ Found {len(results)} metadata results from natural language query")
        return results, []
        
    except Exception as e:
        error_msg = f"Failed to execute SQL query: {e}"
        print(f"❌ {error_msg}")
        return [], [error_msg]


def execute_content_search(nl_prompt: str, workspace: str = None) -> List[Dict[str, Any]]:
    """
    Execute content-based search for natural language queries.
    
    This searches through the actual content files stored in /data/ directory.
    
    Args:
        nl_prompt: Natural language query
        workspace: Optional workspace filter
        
    Returns:
        List of content results with file content matches
    """
    try:
        from promaia.storage.content_search import get_content_searcher
        
        # Extract search terms from natural language prompt
        search_terms = extract_search_terms(nl_prompt)
        
        if not search_terms:
            print("🔍 No specific search terms extracted from query")
            return []
        
        print(f"🔍 Searching content for terms: {search_terms}")
        
        # Get content searcher
        content_searcher = get_content_searcher()
        
        # Determine database filters from the prompt
        database_names = extract_database_types(nl_prompt)
        
        # Search content files
        content_results = content_searcher.search_content(
            search_terms=search_terms,
            workspace=workspace,
            database_names=database_names,
            limit=500  # Reasonable limit for content search
        )
        
        print(f"✅ Found {len(content_results)} content results")
        return content_results
        
    except Exception as e:
        print(f"❌ Content search failed: {e}")
        return []


def extract_search_terms(nl_prompt: str) -> List[str]:
    """
    Extract search terms from natural language prompt.
    
    This tries to identify key terms that should be searched in content.
    """
    import re
    
    # Common words to exclude from content search
    stop_words = {
        'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with',
        'by', 'from', 'as', 'is', 'are', 'was', 'were', 'be', 'been', 'being', 'have', 'has',
        'had', 'do', 'does', 'did', 'will', 'would', 'should', 'could', 'can', 'may', 'might',
        'must', 'shall', 'this', 'that', 'these', 'those', 'i', 'you', 'he', 'she', 'it', 'we',
        'they', 'me', 'him', 'her', 'us', 'them', 'my', 'your', 'his', 'her', 'its', 'our',
        'their', 'all', 'any', 'some', 'each', 'every', 'no', 'none', 'not', 'only', 'just',
        'also', 'even', 'still', 'more', 'most', 'very', 'too', 'so', 'now', 'then', 'here',
        'there', 'where', 'when', 'how', 'what', 'who', 'which', 'why', 'emails', 'email',
        'contain', 'contains', 'containing', 'word', 'words', 'entries', 'entry', 'messages',
        'message', 'notes', 'note', 'content', 'text'
    }
    
    # Clean the prompt
    prompt_lower = nl_prompt.lower()
    
    # Remove common natural language patterns
    patterns_to_remove = [
        r'\b(all|any|some)\s+(emails?|messages?|entries?|notes?)\s+(that|which)\s+',
        r'\bcontains?\s+(the\s+)?word\s+',
        r'\bwith\s+(the\s+)?word\s+',
        r'\bin\s+(the\s+)?(subject|title|body)\s+',
    ]
    
    cleaned_prompt = prompt_lower
    for pattern in patterns_to_remove:
        cleaned_prompt = re.sub(pattern, ' ', cleaned_prompt)
    
    # Extract quoted terms (these are usually important)
    quoted_terms = re.findall(r'"([^"]+)"', cleaned_prompt)
    quoted_terms.extend(re.findall(r"'([^']+)'", cleaned_prompt))
    
    # Extract individual words
    words = re.findall(r'\b[a-zA-Z][a-zA-Z0-9]*\b', cleaned_prompt)
    
    # Filter words
    search_terms = []
    
    # Add quoted terms (high priority)
    for term in quoted_terms:
        if len(term.strip()) > 1:
            search_terms.append(term.strip())
    
    # Add significant words
    for word in words:
        if (len(word) > 2 and 
            word.lower() not in stop_words and
            word.lower() not in [term.lower() for term in search_terms]):
            search_terms.append(word)
    
    # Remove duplicates while preserving order
    unique_terms = []
    seen = set()
    for term in search_terms:
        if term.lower() not in seen:
            unique_terms.append(term)
            seen.add(term.lower())
    
    return unique_terms[:10]  # Limit to 10 terms to avoid overly broad searches


def extract_database_types(nl_prompt: str) -> Optional[List[str]]:
    """
    Extract database type filters from natural language prompt.
    
    Returns:
        List of database names to filter by, or None for all databases
    """
    prompt_lower = nl_prompt.lower()
    
    database_keywords = {
        'gmail': ['email', 'emails', 'gmail', 'mail'],
        'journal': ['journal', 'journals', 'diary', 'note', 'notes'],
        'stories': ['story', 'stories', 'user story', 'user stories'],
        'cms': ['cms', 'blog', 'article', 'post', 'content'],
        'discord': ['discord', 'chat', 'message', 'channel'],
        'epics': ['epic', 'epics']
    }
    
    matched_databases = []
    
    for db_name, keywords in database_keywords.items():
        for keyword in keywords:
            if keyword in prompt_lower:
                if db_name not in matched_databases:
                    matched_databases.append(db_name)
                break
    
    # If no specific database types mentioned, return None (search all)
    return matched_databases if matched_databases else None


def determine_search_strategy(nl_prompt: str) -> str:
    """
    Determine the best search strategy based on the natural language query.
    
    Returns:
        - 'structured': Use SQL/metadata search only (for precise temporal/criteria queries)
        - 'semantic': Use content search only (for thematic/conceptual queries)  
        - 'hybrid': Use both approaches (for complex queries)
    """
    prompt_lower = nl_prompt.lower()
    
    # Structured indicators (dates, specific timeframes, precise criteria)
    structured_indicators = [
        'first week', 'last week', 'this month', 'last month', 'this year', 'last year',
        'january', 'february', 'march', 'april', 'may', 'june', 
        'july', 'august', 'september', 'october', 'november', 'december',
        '2024', '2025', '2026', 'since', 'before', 'after', 'between',
        'recent', 'latest', 'oldest', 'created', 'modified', 'status=', 'from='
    ]
    
    # Semantic indicators (concepts, themes, content-based queries)
    semantic_indicators = [
        'about', 'containing', 'mentions', 'discusses', 'related to', 'similar to',
        'theme', 'topic', 'concept', 'ideas', 'thoughts', 'feelings', 'experience',
        'what did i', 'how did i', 'when did i feel', 'summarize', 'analyze'
    ]
    
    structured_score = sum(1 for indicator in structured_indicators if indicator in prompt_lower)
    semantic_score = sum(1 for indicator in semantic_indicators if indicator in prompt_lower)
    
    # Decision logic
    if structured_score > 0 and semantic_score == 0:
        print(f"🎯 Using structured search strategy (temporal/criteria query)")
        return 'structured'
    elif semantic_score > 0 and structured_score == 0:
        print(f"🧠 Using semantic search strategy (conceptual query)")
        return 'semantic'
    elif structured_score > 0 and semantic_score > 0:
        print(f"⚡ Using hybrid search strategy (complex query)")
        return 'hybrid'
    else:
        # Default to structured for simple, clear queries
        print(f"📊 Using structured search strategy (default)")
        return 'structured'


def load_content_for_result(result: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Load actual content for a database result by reading from the file path.
    Transforms raw database results into the format expected by the chat interface.
    """
    try:
        import os
        
        file_path = result.get('file_path')
        if not file_path or not os.path.exists(file_path):
            print(f"⚠️ File not found: {file_path}")
            return None
            
        # Read the actual content from the file
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Transform database result into chat interface format
        loaded_result = {
            'content': content,
            'filename': os.path.basename(file_path),
            'title': result.get('title', os.path.basename(file_path)),
            'database_name': result.get('database_name'),
            'created_time': result.get('created_time'),
            'last_edited_time': result.get('last_edited_time'),
            'page_id': result.get('page_id'),
            'file_path': file_path,
            'metadata': result.get('metadata', {})
        }
        
        return loaded_result
        
    except Exception as e:
        print(f"❌ Failed to load content for {result.get('file_path', 'unknown')}: {e}")
        return None


def process_natural_language_to_content(nl_prompt: str, workspace: str = None, schema_info: str = None) -> Dict[str, Any]:
    """
    Process natural language to content with intelligent search strategy selection.
    This is the function that unified_query.py expects to import.
    Returns just the data dictionary, not errors (for compatibility).
    """
    # Determine the best search strategy based on query type
    search_strategy = determine_search_strategy(nl_prompt)
    
    metadata_results = []
    content_results = []
    
    if search_strategy in ['structured', 'hybrid']:
        # Execute SQL-based metadata search for structured queries
        metadata_results, errors = execute_natural_language_queries(nl_prompt, None)
        if errors:
            print(f"⚠️ Metadata search errors: {errors}")
    
    if search_strategy in ['semantic', 'hybrid']:
        # Execute content-based search for semantic queries
        content_results = execute_content_search(nl_prompt, workspace)
    
    # Merge results, avoiding duplicates
    all_results = metadata_results.copy()
    
    # Add content results that aren't already in metadata results
    metadata_page_ids = {result.get('page_id') for result in metadata_results}
    for content_result in content_results:
        if content_result.get('page_id') not in metadata_page_ids:
            all_results.append(content_result)

    # Display search results summary
    if search_strategy == 'structured':
        print(f"📊 Search Results Summary (Structured): {len(all_results)} results from SQL query")
    elif search_strategy == 'semantic':
        print(f"🧠 Search Results Summary (Semantic): {len(all_results)} results from content search")
    elif search_strategy == 'hybrid':
        print(f"⚡ Search Results Summary (Hybrid):")
        print(f"   Metadata matches: {len(metadata_results)}")
        print(f"   Content matches: {len(content_results)}")
        print(f"   Total unique results: {len(all_results)}")

    # Convert results to the format expected by the interface by loading actual content
    formatted_results = {}

    if all_results:
        # Load actual content for each result
        content_loaded_results = []
        for result in all_results:
            loaded_result = load_content_for_result(result)
            if loaded_result:  # Only include results where content was successfully loaded
                content_loaded_results.append(loaded_result)
        
        all_results = content_loaded_results
        # Group results by database for the interface
        for result in all_results:
            db_name = result.get('database_name', 'unknown')
            if db_name not in formatted_results:
                formatted_results[db_name] = []
            formatted_results[db_name].append(result)

    # Log any errors but don't return them (compatibility)
    if errors:
        for error in errors:
            print(f"❌ Natural language processing error: {error}")
    
    # Log search results summary
    metadata_count = len(metadata_results)
    content_count = len(content_results)
    total_count = len(all_results)
    
    print(f"🔍 Search Results Summary:")
    print(f"   Metadata matches: {metadata_count}")
    print(f"   Content matches: {content_count}")
    print(f"   Total unique results: {total_count}")

    return formatted_results


# Utility functions for query execution (preserved from old system)
def execute_multiple_queries(queries: List[Dict[str, Any]], workspace: str) -> Dict[str, List[Dict[str, Any]]]:
    """Execute multiple queries and merge their results by database name."""
    merged_results = {}
    
    for query_info in queries:
        query_type = query_info.get("query_type", "single")
        if query_type == "single":
            sql_query = query_info.get("sql_query")
            content_filters = query_info.get("content_filters", [])
            
            if sql_query:
                result = execute_single_query(sql_query, content_filters, workspace)
                
                # Merge results by database name
                for db_name, pages in result.items():
                    if db_name not in merged_results:
                        merged_results[db_name] = []
                    merged_results[db_name].extend(pages)
    
    return merged_results


def execute_single_query(sql_query: str, content_filters: List[str], workspace: str) -> Dict[str, List[Dict[str, Any]]]:
    """Execute a single SQL query and return results grouped by database name."""
    try:
        from promaia.storage.unified_query import get_query_interface
        query_interface = get_query_interface()
        
        # Get database context - handle both dict and object returns
        db_context = query_interface.get_database_context(workspace)
        
        # Handle different return types from query_interface
        connection = None
        if hasattr(db_context, 'connection'):
            connection = db_context.connection
        elif isinstance(db_context, dict) and 'connection' in db_context:
            connection = db_context['connection']
        elif hasattr(query_interface, 'db_path'):
            # Fallback: create direct SQLite connection
            import sqlite3
            connection = sqlite3.connect(query_interface.db_path)
        
        if not connection:
            print(f"❌ No database connection available for workspace: {workspace}")
            return {}
        
        print(f"🔍 Executing SQL query:")
        print(f"   {sql_query}")
        
        # Execute the query
        cursor = connection.cursor()
        cursor.execute(sql_query)
        
        # Get column names
        columns = [desc[0] for desc in cursor.description]
        
        # Fetch results and convert to dictionaries
        results = []
        for row in cursor.fetchall():
            row_dict = dict(zip(columns, row))
            results.append(row_dict)
        
        # Apply content filters if specified
        if content_filters:
            filtered_results = []
            for page_data in results:
                if content_matches_filters(page_data, content_filters):
                    filtered_results.append(page_data)
            results = filtered_results
        
        # Group results by database name
        grouped_results = {}
        for page_data in results:
            db_name = page_data.get('database_name', 'unknown')
            if db_name not in grouped_results:
                grouped_results[db_name] = []
            grouped_results[db_name].append(page_data)
        
        # Print summary
        total_results = len(results)
        if total_results > 0:
            print(f"✅ Found {total_results} results from natural language query")
            
            # Print breakdown by database
            for db_name, pages in grouped_results.items():
                print(f"   {db_name}: {len(pages)} results")
        else:
            print("❌ No content found for natural language query")
        
        return grouped_results
        
    except Exception as e:
        print(f"❌ Query execution failed: {e}")
        print(f"   SQL: {sql_query}")
        return {}


def content_matches_filters(page_data: Dict[str, Any], filters: List[str]) -> bool:
    """Check if page content matches the specified filters."""
    if not filters:
        return True
    
    # Get text content from various fields
    searchable_text = ""
    
    # Add title and content
    if page_data.get('title'):
        searchable_text += page_data['title'] + " "
    
    # Add metadata if it's a string or convert to string
    metadata = page_data.get('metadata', '')
    if isinstance(metadata, dict):
        # Convert dict to searchable string
        searchable_text += str(metadata) + " "
    elif metadata:
        searchable_text += str(metadata) + " "
    
    # Add any other relevant text fields
    for field in ['sender_name', 'sender_email', 'file_path']:
        if page_data.get(field):
            searchable_text += str(page_data[field]) + " "
    
    searchable_text = searchable_text.lower()
    
    # Check if any filter matches
    for filter_term in filters:
        filter_term = filter_term.lower().strip()
        if filter_term and filter_term in searchable_text:
            return True
    
    return False
