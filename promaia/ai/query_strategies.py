"""
Query Strategy Pattern Implementation

Separates SQL and Vector query generation/execution logic
while keeping the shared orchestration pipeline clean.
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Tuple
import sqlite3
import json

from promaia.utils.display import print_text


class QueryStrategy(ABC):
    """Base strategy interface for query generation and execution."""
    
    @abstractmethod
    def initialize(self, verbose: bool = False, debug: bool = False) -> str:
        """
        Initialize strategy-specific components.
        
        Returns:
            Status message about initialization
        """
        pass
    
    @abstractmethod
    def generate_query(
        self,
        intent: Dict[str, Any],
        schema: Dict[str, Any],
        retry_attempt: int,
        llm,
        workspace_context: str,
        schema_summary: str,
        validation_feedback: str,
        verbose: bool,
        debug: bool
    ) -> Optional[Any]:
        """
        Generate query from intent.
        
        Returns:
            SQL string for SQL mode, dict for vector mode
        """
        pass
    
    @abstractmethod
    def display_generated_query(self, query: Any, verbose: bool) -> None:
        """Display the generated query to user."""
        pass
    
    @abstractmethod
    def execute_query(
        self,
        query: Any,
        verbose: bool,
        debug: bool
    ) -> Tuple[Optional[List[Dict[str, Any]]], Optional[str]]:
        """
        Execute the query.
        
        Returns:
            (results, error_message)
        """
        pass
    
    @abstractmethod
    def should_save_pattern(self) -> bool:
        """Whether this strategy supports pattern learning."""
        pass
    
    @abstractmethod
    def save_pattern(self, pattern: Dict[str, Any]) -> None:
        """Save a successful query pattern (if supported)."""
        pass


class SQLQueryStrategy(QueryStrategy):
    """Strategy for SQL query generation and execution."""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.learning_system = None
    
    def initialize(self, verbose: bool = False, debug: bool = False) -> str:
        """Initialize SQL-specific components."""
        from promaia.ai.nl_utilities import QueryLearningSystem
        self.learning_system = QueryLearningSystem()
        return "✅ Initialized agentic NL processor in SQL mode"
    
    def generate_query(
        self,
        intent: Dict[str, Any],
        schema: Dict[str, Any],
        retry_attempt: int,
        llm,
        workspace_context: str,
        schema_summary: str,
        validation_feedback: str,
        verbose: bool,
        debug: bool
    ) -> Optional[str]:
        """Generate SQL query using dynamic schema + learned patterns."""
        
        # Get learned patterns
        learned_patterns = self.learning_system.get_patterns_for_prompt()
        
        # Build concise prompt
        intent_line = f"Goal: {intent['goal']}"
        if intent.get('search_terms'):
            intent_line += f" | Terms: {', '.join(intent.get('search_terms', []))}"
        if intent.get('date_filter', {}).get('description', 'none') != 'none':
            intent_line += f" | Date: {intent.get('date_filter', {}).get('description')}"
        
        # Extract workspace and normalize database names from qualified names
        target_workspaces = set()
        target_dbs = []
        
        for db_name in intent['databases']:
            if '.' in db_name:
                workspace_part, db_nickname = db_name.rsplit('.', 1)
                target_workspaces.add(workspace_part)
                target_dbs.append(db_nickname)
            else:
                target_dbs.append(db_name)
        
        # Build workspace filter clause
        workspace_filter = ""
        if target_workspaces:
            workspace_list = ', '.join(f"'{w}'" for w in sorted(target_workspaces))
            workspace_filter = f"\nWORKSPACE FILTER: Must filter WHERE u.workspace IN ({workspace_list})"
        
        prompt = f"""{workspace_context}

{schema_summary}

{learned_patterns}

{validation_feedback}

QUERY: {intent_line}
TARGET DATABASES: {', '.join(target_dbs)}{workspace_filter}

IMPORTANT: The database_name column stores ONLY the nickname (e.g., "stories", not "trass.stories")

Return SQLite query that:
- SELECTs: u.page_id, u.workspace, u.database_name, u.title, u.created_time (+ any other needed fields)
- IMPORTANT: Always include u.workspace in SELECT to distinguish databases across workspaces
- JOINs specialized tables (gmail_content, etc.) for full-text search
- Uses LIKE '%term%' on ALL text-heavy fields (check sample data above)
- Filters database_name using ONLY the nickname (no workspace prefix)
- If workspace filter specified above include it in your query like this: AND u.workspace IN (...)
- Applies date filters on created_time/email_date columns
- LIMIT 1200

SQL only (no markdown):"""
        
        if debug:
            print_text(f"\n📤 SQL Generation Prompt:", style="cyan")
            print_text(f"   Intent: {intent['goal']}", style="dim")
            print_text(f"   Databases (original): {', '.join(intent['databases'])}", style="dim")
            print_text(f"   Databases (normalized for SQL): {', '.join(target_dbs)}", style="dim")
            if target_workspaces:
                print_text(f"   Workspaces (extracted): {', '.join(sorted(target_workspaces))}", style="yellow")
            print_text(f"   Search terms: {', '.join(intent.get('search_terms', []))}", style="dim")
            print_text(f"   Using {len(self.learning_system.load_successful_patterns())} learned patterns", style="dim")
        
        try:
            # Log AI generation only in verbose mode
            if verbose:
                if retry_attempt == 0:
                    print_text(f"\n💬 Asking AI to generate SQL for: {intent['goal']}", style="cyan")
                else:
                    print_text(f"\n💬 Asking AI to retry SQL generation with feedback:", style="yellow")
                    print_text(f"   Previous feedback: {intent.get('_validation_feedback', 'N/A')}", style="dim")
            
            response = llm.invoke([{"role": "user", "content": prompt}])
            sql = response.content.strip()
            
            if debug:
                print_text(f"\n📥 AI Response (raw):", style="cyan")
                print_text(sql if len(sql) < 400 else sql[:400] + "...", style="dim")
            
            # Clean SQL
            if '```' in sql:
                import re
                match = re.search(r'```(?:sql)?\s*(.*?)\s*```', sql, re.DOTALL)
                if match:
                    sql = match.group(1).strip()
            
            return sql
        
        except Exception as e:
            print_text(f"❌ SQL generation failed: {e}", style="red")
            return None
    
    def display_generated_query(self, query: str, verbose: bool) -> None:
        """Display generated SQL query."""
        if verbose:
            print_text(f"\n📝 Generated SQL:", style="cyan")
            print_text(query, style="dim")
    
    def execute_query(
        self,
        sql: str,
        verbose: bool,
        debug: bool
    ) -> Tuple[Optional[List[Dict[str, Any]]], Optional[str]]:
        """Execute SQL query."""
        if debug:
            print_text("\n" + "=" * 70, style="dim")
            print_text("⚡ CHAIN OF THOUGHT: SQL Execution", style="bold yellow")
            print_text("=" * 70, style="dim")
            print_text(f"\n🔍 Executing query against: {self.db_path}", style="cyan")
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute(sql)
                results = [dict(row) for row in cursor.fetchall()]
                
                if debug:
                    print_text(f"\n✅ Execution successful", style="green")
                    print_text(f"   Returned {len(results)} rows", style="dim")
                    if results:
                        print_text(f"   Sample row keys: {list(results[0].keys())[:5]}", style="dim")
                
                if verbose:
                    print_text(f"✅ Execution successful: {len(results)} rows returned", style="green" if results else "yellow")
                    if results and len(results) > 0:
                        sample = results[0]
                        print_text(f"   Sample columns: {list(sample.keys())[:6]}", style="dim")
                
                return results, None
        
        except sqlite3.OperationalError as e:
            error_msg = f"SQL Error: {str(e)}"
            if debug:
                print_text(f"\n❌ SQL execution error: {error_msg}", style="red")
            print_text(f"❌ {error_msg}", style="red")
            return None, error_msg
        
        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            if debug:
                print_text(f"\n❌ {error_msg}", style="red")
            print_text(f"❌ {error_msg}", style="red")
            return None, error_msg
    
    def should_save_pattern(self) -> bool:
        """SQL mode supports pattern learning."""
        return True
    
    def save_pattern(self, pattern: Dict[str, Any]) -> None:
        """Save successful SQL pattern."""
        self.learning_system.save_successful_pattern(pattern)


class VectorQueryStrategy(QueryStrategy):
    """Strategy for vector search query generation and execution."""
    
    def __init__(self):
        self.vector_db = None
    
    def initialize(self, verbose: bool = False, debug: bool = False) -> str:
        """Initialize vector search components."""
        from promaia.storage.vector_db import VectorDBManager
        self.vector_db = VectorDBManager()
        return "✅ Initialized agentic NL processor in VECTOR mode"
    
    def generate_query(
        self,
        intent: Dict[str, Any],
        schema: Dict[str, Any],
        retry_attempt: int,
        llm,
        workspace_context: str,
        schema_summary: str,
        validation_feedback: str,
        verbose: bool,
        debug: bool
    ) -> Optional[Dict[str, Any]]:
        """Generate vector search parameters from intent."""
        if debug:
            print_text("\n" + "=" * 70, style="dim")
            print_text(f"⚙️  CHAIN OF THOUGHT: Vector Query Generation (Attempt {retry_attempt + 1})", style="bold yellow")
            print_text("=" * 70, style="dim")
        
        prompt = f"""Extract semantic search parameters from this intent:

{workspace_context}

Intent:
- Goal: {intent['goal']}
- Databases: {', '.join(intent.get('databases', []))}
- Search Terms: {', '.join(intent.get('search_terms', []))}
- Date Filter: {intent.get('date_filter', {}).get('description', 'none')}

Return JSON with:
{{
    "search_text": "core semantic query for embedding (just the content to search, not metadata)",
    "explanation": "brief reasoning for search text choice"
}}

Example:
Intent: "find stories about international launch in trass workspace"
Output: {{"search_text": "international launch stories", "explanation": "removed workspace metadata"}}

Use the workspace configuration above to understand database context.

Return ONLY the JSON object:"""
        
        try:
            if verbose:
                if retry_attempt == 0:
                    print_text(f"\n💬 Asking AI to extract semantic search parameters", style="cyan")
                else:
                    print_text(f"\n💬 Retrying search text extraction", style="yellow")
            
            response = llm.invoke([{"role": "user", "content": prompt}])
            content = response.content.strip()
            
            if debug:
                print_text(f"\n📥 LLM Response:", style="cyan")
                print_text(content[:200] + "..." if len(content) > 200 else content, style="dim")
            
            # Clean JSON
            if content.startswith('```json'):
                content = content[7:-3].strip()
            elif content.startswith('```'):
                content = content[3:-3].strip()
            
            extracted = json.loads(content)
            search_text = extracted.get('search_text', ' '.join(intent.get('search_terms', [])))
            
            # Build metadata filters for ChromaDB
            filters = {}
            
            # Database filter
            databases = intent.get('databases', [])
            if databases:
                if len(databases) == 1:
                    filters['database_name'] = databases[0]
                else:
                    filters['database_name'] = {"$in": databases}
            
            query_params = {
                'search_text': search_text,
                'filters': filters if filters else None
            }
            
            if debug:
                print_text(f"\n📝 Vector Query Parameters:", style="cyan")
                print_text(f"   Search text: {search_text}", style="dim")
                print_text(f"   Filters: {filters}", style="dim")
            
            return query_params
        
        except Exception as e:
            print_text(f"❌ Vector query generation failed: {e}", style="red")
            return None
    
    def display_generated_query(self, query: Dict[str, Any], verbose: bool) -> None:
        """Display generated vector search parameters."""
        if verbose:
            print_text(f"\n📝 Vector Search Parameters:", style="cyan")
            search_text = query.get('search_text', 'N/A')
            filters = query.get('filters', {})
            print_text(f"   Search Text: {search_text}", style="dim")
            if filters:
                print_text(f"   Filters:", style="dim")
                for key, value in filters.items():
                    print_text(f"      • {key}: {value}", style="dim")
    
    def execute_query(
        self,
        query_params: Dict[str, Any],
        verbose: bool,
        debug: bool
    ) -> Tuple[Optional[List[Dict[str, Any]]], Optional[str]]:
        """Execute vector search."""
        if debug:
            print_text("\n" + "=" * 70, style="dim")
            print_text("⚡ CHAIN OF THOUGHT: Vector Search Execution", style="bold yellow")
            print_text("=" * 70, style="dim")
            print_text(f"\n🔍 Searching with: {query_params.get('search_text')}", style="cyan")
        
        try:
            # Get config for defaults
            config_path = "promaia.config.json"
            with open(config_path, 'r') as f:
                config = json.load(f)
            vector_config = config.get('global', {}).get('vector_search', {})
            n_results = vector_config.get('default_n_results', 20)
            min_similarity = vector_config.get('default_similarity_threshold', 0.75)
            
            if verbose:
                print_text(f"   Max results: {n_results}, Min similarity: {min_similarity}", style="dim")
            
            # Execute vector search
            search_results = self.vector_db.search(
                query_text=query_params['search_text'],
                filters=query_params.get('filters'),
                n_results=n_results,
                min_similarity=min_similarity
            )
            
            if debug:
                print_text(f"\n✅ Search successful", style="green")
                print_text(f"   Returned {len(search_results)} results above {min_similarity} similarity", style="dim")
                if search_results:
                    print_text(f"   Top score: {search_results[0].get('similarity_score', 0):.3f}", style="dim")
            
            if verbose:
                print_text(f"✅ Execution successful: {len(search_results)} results returned", style="green" if search_results else "yellow")
                if search_results:
                    top_score = search_results[0].get('similarity_score', 0)
                    bottom_score = search_results[-1].get('similarity_score', 0)
                    print_text(f"   Similarity range: {bottom_score:.3f} - {top_score:.3f}", style="dim")
                    sample = search_results[0].get('metadata', {})
                    print_text(f"   Sample result: {sample.get('database_name', 'unknown')} database", style="dim")
            
            # Convert to unified_content-like format for compatibility
            results = []
            for result in search_results:
                results.append({
                    'page_id': result['page_id'],
                    'similarity_score': result['similarity_score'],
                    'database_name': result['metadata'].get('database_name', ''),
                    'workspace': result['metadata'].get('workspace', ''),
                    'created_time': result['metadata'].get('created_time', ''),
                    'content_type': result['metadata'].get('content_type', ''),
                })
            
            return results, None
        
        except Exception as e:
            error_msg = f"Vector search error: {str(e)}"
            if debug:
                print_text(f"\n❌ {error_msg}", style="red")
            print_text(f"❌ {error_msg}", style="red")
            return None, error_msg
    
    def should_save_pattern(self) -> bool:
        """Vector mode doesn't support pattern learning."""
        return False
    
    def save_pattern(self, pattern: Dict[str, Any]) -> None:
        """Vector mode doesn't save patterns."""
        pass

