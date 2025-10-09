"""
Enhanced Agentic Natural Language Processor

This replaces the hardcoded example-based system with a fully agentic approach:
- Dynamic schema exploration
- Learning from successful queries
- Result validation and iteration
- User confirmation with detailed summaries
"""
import os
import json
from typing import List, Dict, Any, Optional

# Load environment variables
from promaia.utils.config import load_environment
load_environment()

from promaia.config.databases import get_database_manager
from promaia.utils.display import print_text

# Import our agentic components
from .nl_utilities import (
    SchemaExplorer,
    QueryLearningSystem,
    NLContextLogger,
    ResultValidator,
    format_result_summary_for_user
)

# LLM Adapter (copied to avoid langchain dependencies)
from anthropic import Anthropic
from openai import OpenAI
import google.generativeai as genai


class MockResponse:
    """Mock response object for compatibility."""
    def __init__(self, content):
        self.content = content


class PromaiLLMAdapter:
    """Adapter to make existing Promaia LLM clients work with our interface."""
    
    def __init__(self, client_type: str = "auto"):
        self.client_type = client_type
        self._setup_client()
    
    def _setup_client(self):
        """Setup the appropriate LLM client with fallback handling."""
        if self.client_type == "auto":
            # Try clients in order
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
                            return
                        elif client_type == "anthropic":
                            self.client_type = "anthropic"
                            self.client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
                            return
                        elif client_type == "gemini":
                            self.client_type = "gemini"
                            genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
                            self.client = genai.GenerativeModel('gemini-2.5-pro')
                            return
                    except Exception as e:
                        print(f"⚠️  Failed to setup {client_type} client: {e}")
                        continue
            
            raise ValueError("No working LLM API clients found")
        
    def invoke(self, messages):
        """Simple invoke method."""
        # Extract message content
        if isinstance(messages, list):
            # Handle dict-based messages
            prompt = ""
            for msg in messages:
                if isinstance(msg, dict):
                    prompt += msg.get('content', '') + "\n"
                else:
                    prompt += str(msg) + "\n"
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


class AgenticNLQueryProcessor:
    """
    Agentic NL query processor that learns and adapts.
    
    Supports both SQL and vector search modes:
    - SQL mode: Generates SQL queries, learns from patterns
    - Vector mode: Uses semantic embeddings for similarity search
    
    Key features:
    1. Uses PRAGMA to discover schema dynamically
    2. Learns from successful queries (rolling index of 20) - SQL mode only
    3. Validates results and retries if needed
    4. Saves context logs for user inspection
    5. Asks for user confirmation before saving patterns
    """
    
    def __init__(self, db_path: str = "data/hybrid_metadata.db", query_mode: str = "sql", 
                 debug: bool = False, verbose: bool = False):
        self.db_path = db_path
        self.query_mode = query_mode  # "sql" or "vector"
        self.debug = debug or os.getenv("MAIA_DEBUG") == "1"
        self.verbose = verbose or self.debug  # Verbose mode includes debug info
        
        # Initialize agentic components
        self.schema_explorer = SchemaExplorer(db_path)
        self.learning_system = QueryLearningSystem()  # Only used in SQL mode
        self.context_logger = NLContextLogger()
        self.validator = ResultValidator()
        
        # Load workspace config for AI context
        self.workspace_config = self._load_workspace_config()
        
        # Initialize vector DB if in vector mode
        if self.query_mode == "vector":
            from promaia.storage.vector_db import VectorDBManager
            self.vector_db = VectorDBManager()
            if self.verbose:
                print_text(f"✅ Initialized agentic NL processor in VECTOR mode", style="green")
        else:
            self.vector_db = None
            if self.verbose:
                print_text(f"✅ Initialized agentic NL processor in SQL mode", style="green")
        
        # Initialize LLM
        self.llm = PromaiLLMAdapter(client_type="auto")
        if self.verbose:
            print_text(f"   Using {self.llm.client_type} for query generation", style="dim")
        if self.debug:
            print_text("🐛 Debug mode enabled - showing chain of thought", style="yellow")
    
    def _load_workspace_config(self, config_file: str = "promaia.config.json") -> Dict[str, Any]:
        """Load workspace configuration to provide context to AI."""
        try:
            if os.path.exists(config_file):
                with open(config_file, 'r') as f:
                    config = json.load(f)
                    # Filter out sensitive info and return just structure
                    return {
                        'workspaces': list(config.get('workspaces', {}).keys()),
                        'default_workspace': config.get('default_workspace'),
                        'databases': {
                            name: {
                                'nickname': db.get('nickname'),
                                'description': db.get('description'),
                                'workspace': db.get('workspace'),
                                'source_type': db.get('source_type'),
                                'default_include': db.get('default_include', False),
                                'default_days': db.get('default_days')
                            }
                            for name, db in config.get('databases', {}).items()
                        }
                    }
        except Exception as e:
            if self.debug:
                print_text(f"⚠️  Could not load workspace config: {e}", style="yellow")
        
        return {}
    
    def _format_workspace_config(self) -> str:
        """Format workspace config for AI prompt."""
        if not self.workspace_config:
            return "No workspace configuration available."
        
        output = "=== WORKSPACE CONFIGURATION ===\n\n"
        
        # Workspaces
        output += f"Workspaces: {', '.join(self.workspace_config.get('workspaces', []))}\n"
        output += f"Default: {self.workspace_config.get('default_workspace', 'N/A')}\n\n"
        
        # Databases grouped by workspace
        databases = self.workspace_config.get('databases', {})
        by_workspace = {}
        for name, db in databases.items():
            workspace = db.get('workspace', 'unknown')
            if workspace not in by_workspace:
                by_workspace[workspace] = []
            by_workspace[workspace].append((name, db))
        
        output += "Databases by Workspace:\n"
        for workspace, dbs in sorted(by_workspace.items()):
            output += f"\n  {workspace.upper()} workspace:\n"
            for name, db in dbs:
                output += f"    • {name} ({db.get('nickname')}): {db.get('description', 'N/A')}\n"
                output += f"      Type: {db.get('source_type')}, Default: {db.get('default_include')}\n"
        
        return output
    
    def process_query_with_modification(
        self,
        user_query: str,
        workspace: Optional[str] = None,
        max_retries: int = 2
    ) -> Dict[str, Any]:
        """
        Process NL query with support for user modification.
        
        If user chooses to modify the query (presses 'm'), prompts for
        a new query and re-runs with same schema context.
        
        Args:
            user_query: The natural language query from the user
            workspace: Optional workspace filter
            max_retries: Maximum number of retry attempts if validation fails
        
        Returns:
            Dictionary with results, SQL, intent, and learning info
        """
        while True:
            result = self.process_query(user_query, workspace, max_retries)
            
            # If user wants to quit, return immediately (exit to terminal)
            if result.get('action') == 'quit':
                return result
            
            # If user wants to modify, ask for new query and loop
            elif result.get('action') == 'modify':
                print_text("\n✏️  Modify your query (edit and press Enter, or Ctrl+C to cancel):", style="bold cyan")
                try:
                    # Pre-fill input with original query for editing
                    modified_query = self._get_input_with_prefill("   Query: ", user_query)
                    if not modified_query:
                        print_text("   Empty query, returning to previous results.", style="yellow")
                        result.pop('action')  # Remove 'modify' action
                        return result
                    user_query = modified_query
                    # Loop will re-run with new query
                except (KeyboardInterrupt, EOFError):
                    print_text("\n   Quitting...", style="dim")
                    result['action'] = 'quit'  # Change to quit action
                    return result
            else:
                # Normal completion (user pressed Enter to save)
                return result
    
    def _get_input_with_prefill(self, prompt: str, prefill: str) -> str:
        """Get user input with pre-filled text for editing."""
        try:
            from prompt_toolkit import prompt as pt_prompt
            
            # Use prompt_toolkit for reliable pre-filling
            user_input = pt_prompt(prompt, default=prefill)
            return user_input.strip()
        
        except ImportError:
            # Fallback to readline if prompt_toolkit not available
            try:
                import readline
                
                # Set up readline to pre-fill the input buffer
                def startup_hook():
                    readline.insert_text(prefill)
                    readline.redisplay()
                
                readline.set_startup_hook(startup_hook)
                try:
                    user_input = input(prompt)
                finally:
                    readline.set_startup_hook()  # Clear the hook
                
                return user_input.strip()
            
            except ImportError:
                # No readline available (Windows), show the original and get fresh input
                print_text(f"   Original: {prefill}", style="dim")
                return input(prompt).strip()
    
    def process_query(
        self,
        user_query: str,
        workspace: Optional[str] = None,
        max_retries: int = 2
    ) -> Dict[str, Any]:
        """
        Process a natural language query with agentic features.
        
        Args:
            user_query: The natural language query from the user
            workspace: Optional workspace filter
            max_retries: Maximum number of retry attempts if validation fails
        
        Returns:
            Dictionary with results, SQL, intent, and learning info
        """
        if self.verbose:
            print_text(f"\n🤖 Processing query: '{user_query}'", style="cyan")
        else:
            print_text("🤖 Processing natural language query...", style="cyan")
        
        # Step 1: Explore schema dynamically
        if self.verbose:
            print_text("🔍 Step 1: Exploring database schema...", style="dim")
        schema = self.schema_explorer.explore_schema()
        
        # Step 2: Parse intent
        if self.verbose:
            print_text("🧠 Step 2: Parsing intent...", style="dim")
        intent = self._parse_intent(user_query, schema, workspace)
        
        if not intent:
            return {
                "success": False,
                "error": "Failed to parse query intent",
                "results": {}
            }
        
        # Show parsed intent to user (only in verbose mode)
        if self.verbose:
            self._display_intent(intent)
        
        # Step 3: Generate and execute query (with retries)
        attempt = 0
        results = None
        generated_query = None
        validation_result = None
        
        while attempt <= max_retries:
            if attempt > 0 and self.verbose:
                print_text(f"\n🔄 Retry attempt {attempt}/{max_retries}", style="yellow")
            
            if self.verbose:
                query_type = "vector search parameters" if self.query_mode == "vector" else "SQL query"
                print_text(f"⚙️  Step 3: Generating {query_type}...", style="dim")
            generated_query = self._generate_query(intent, schema, attempt)
            
            if not generated_query:
                attempt += 1
                continue
            
            # Show generated query only in verbose mode
            if self.verbose:
                if self.query_mode == "sql":
                    print_text(f"\n📝 Generated SQL:", style="cyan")
                    print_text(generated_query, style="dim")  # Show ENTIRE SQL query
                else:
                    print_text(f"\n📝 Vector Search Parameters:", style="cyan")
                    print_text(f"   Search: {generated_query.get('search_text', 'N/A')}", style="dim")
            
            if self.verbose:
                print_text(f"\n🔍 Executing query...", style="dim")
            results, sql_error = self._execute_query(generated_query)
            
            # If SQL error, use that as validation feedback
            if sql_error:
                if self.verbose:
                    print_text(f"❌ SQL Error during execution", style="red")
                intent['_validation_feedback'] = sql_error
                attempt += 1
                continue
            
            if results is None:
                attempt += 1
                continue
            
            # Step 4: Validate results
            if self.verbose:
                print_text("🔍 Step 4: Validating results...", style="dim")
            is_valid, message = self.validator.validate_results(intent, results, query_mode=self.query_mode)
            validation_result = {"is_valid": is_valid, "message": message}
            
            if self.debug:
                print_text("\n" + "=" * 70, style="dim")
                print_text("✅ CHAIN OF THOUGHT: Result Validation", style="bold yellow")
                print_text("=" * 70, style="dim")
                print_text(f"\n🔍 Validation checks:", style="cyan")
                print_text(f"   • Results exist: {'✓' if results else '✗'}", style="dim")
                print_text(f"   • Count: {len(results) if results else 0}", style="dim")
                if results:
                    result_dbs = set(r.get('database_name') for r in results)
                    intent_dbs = set(intent.get('databases', []))
                    print_text(f"   • Database match: {result_dbs} vs expected {intent_dbs}", style="dim")
                    search_terms = intent.get('search_terms', [])
                    if search_terms:
                        print_text(f"   • Search terms check: {search_terms}", style="dim")
                print_text(f"\n🎯 Validation result: {'PASS ✓' if is_valid else 'FAIL ✗'}", style="green" if is_valid else "yellow")
                print_text(f"   Reason: {message}", style="dim")
            
            if is_valid:
                if self.verbose:
                    print_text(f"✅ {message}", style="green")
                break
            else:
                if self.verbose:
                    print_text(f"⚠️  {message}", style="yellow")
                # Update intent with validation feedback for retry
                intent['_validation_feedback'] = message
                attempt += 1
        
        # If all retries failed
        if results is None or not validation_result['is_valid']:
            return {
                "success": False,
                "error": validation_result['message'] if validation_result else "Query execution failed",
                "intent": intent,
                "query": generated_query,
                "results": {}
            }
        
        # Step 5: Generate result summary
        summary = self.validator.generate_result_summary(results)
        
        # Step 6: Save draft context log
        query_info = {
            "user_query": user_query,
            "intent": intent,
            "generated_query": generated_query,
            "query_mode": self.query_mode,
            "result_count": summary['total_count'],
            "databases_in_results": summary['databases'],
            "database_breakdown": summary['database_breakdown'],
            "sample_results": summary['sample_results'],
            "validation": validation_result,
            "retries": attempt
        }
        
        log_file = self.context_logger.save_draft_context(query_info)
        summary_file = self.context_logger.save_summary(query_info)
        
        # Step 7: Show summary (verbose or compact mode)
        if self.verbose:
            # Show sample results
            print_text(format_result_summary_for_user(summary, intent), style="white")
            # Don't show log file paths in verbose mode - they're saved silently
        else:
            # Compact summary for non-verbose mode
            print_text("✅ Query processed successfully\n", style="green")
            self._display_compact_summary(summary, intent)
        
        # Step 8: Group results by database with minimal metadata
        # Return only page_id and content_type for the adapter to load content
        # Use qualified names (workspace.database) to avoid collisions
        grouped_results = {}
        for result in results:
            workspace = result.get('workspace', '')
            db_name = result.get('database_name', 'unknown')
            
            # Create qualified key: workspace.database (unless already qualified)
            if workspace and '.' not in db_name:
                qualified_key = f"{workspace}.{db_name}"
            else:
                qualified_key = db_name
            
            if qualified_key not in grouped_results:
                grouped_results[qualified_key] = []
            
            # Return minimal metadata: page_id and content_type
            grouped_results[qualified_key].append({
                'page_id': result.get('page_id'),
                'content_type': result.get('content_type', db_name),
                'database_name': db_name,
                'workspace': workspace,
                'created_time': result.get('created_time'),
                'title': result.get('title', '')  # Include title for display
            })
        
        if self.verbose:
            total_pages = sum(len(pages) for pages in grouped_results.values())
            print_text(f"📋 Prepared {total_pages} page references for adapter to load", style="dim")
        
        # Ask user if query was successful
        user_action = self._ask_user_confirmation(summary)
        
        if user_action == 'save':
            # Save to learning index (only for SQL mode)
            if self.query_mode == "sql":
                pattern = {
                    "user_query": user_query,
                    "intent": intent,
                    "generated_sql": generated_query,
                    "result_count": summary['total_count'],
                    "databases": summary['databases'],
                    "notes": f"Validated successfully. {validation_result['message']}"
                }
                self.learning_system.save_successful_pattern(pattern)
        elif user_action == 'modify':
            # User wants to modify the query - signal to wrapper
            return {
                "success": True,
                "action": "modify",
                "results": grouped_results,
                "intent": intent,
                "query": generated_query,
                "query_mode": self.query_mode,
                "validation": validation_result
            }
        elif user_action == 'quit':
            # User wants to exit to terminal (don't continue to chat)
            return {
                "success": True,
                "action": "quit",
                "results": grouped_results,
                "intent": intent,
                "query": generated_query,
                "query_mode": self.query_mode,
                "summary": summary,
                "learned": False
            }
        
        return {
            "success": True,
            "results": grouped_results,
            "intent": intent,
            "query": generated_query,
            "query_mode": self.query_mode,
            "summary": summary,
            "learned": (user_action == 'save')
        }
    
    def _parse_intent(
        self,
        user_query: str,
        schema: Dict[str, Any],
        workspace: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Parse user query into structured intent using LLM."""
        available_dbs = schema.get('available_databases', [])
        
        workspace_context = self._format_workspace_config()
        
        prompt = f"""Parse this natural language query into structured intent:

Query: "{user_query}"
{f'Workspace filter: {workspace}' if workspace else ''}

{workspace_context}

Available databases: {available_dbs}

Available tables and their columns:
{self._format_schema_for_prompt(schema)}

Respond with JSON in this exact format:
{{
    "goal": "what the user wants to find",
    "databases": ["list", "of", "relevant", "databases"],
    "search_terms": ["key", "content", "search", "terms"],
    "date_filter": {{"days_back": null, "description": ""}}
}}

Rules:
- Include ALL relevant databases that might contain the data
- Use the workspace configuration above to understand which databases belong to which workspace
- Extract specific search terms from the query
- Parse date expressions: "last N months" → days_back: N*30, "past week" → days_back: 7
- If no date mentioned, set days_back: null

Return ONLY the JSON object:"""
        
        if self.debug:
            print_text("\n" + "=" * 70, style="dim")
            print_text("🧠 CHAIN OF THOUGHT: Intent Parsing", style="bold yellow")
            print_text("=" * 70, style="dim")
            print_text(f"\n📤 Prompt to LLM ({self.llm.client_type}):", style="cyan")
            print_text(prompt[:500] + "..." if len(prompt) > 500 else prompt, style="dim")
        
        try:
            response = self.llm.invoke([{"role": "user", "content": prompt}])
            content = response.content.strip()
            
            if self.debug:
                print_text(f"\n📥 LLM Response:", style="cyan")
                print_text(content[:300] + "..." if len(content) > 300 else content, style="dim")
            
            # Clean JSON
            if content.startswith('```json'):
                content = content[7:-3].strip()
            elif content.startswith('```'):
                content = content[3:-3].strip()
            
            import json
            intent = json.loads(content)
            return intent
        
        except Exception as e:
            print_text(f"❌ Intent parsing failed: {e}", style="red")
            return None
    
    def _generate_query(
        self,
        intent: Dict[str, Any],
        schema: Dict[str, Any],
        retry_attempt: int = 0
    ) -> Optional[Any]:
        """
        Generate query based on mode.
        
        SQL mode: Returns SQL string
        Vector mode: Returns dict with search_text and filters
        """
        if self.query_mode == "sql":
            return self._generate_sql_query(intent, schema, retry_attempt)
        elif self.query_mode == "vector":
            return self._generate_vector_query(intent, schema, retry_attempt)
        else:
            raise ValueError(f"Unknown query_mode: {self.query_mode}")
    
    def _generate_sql_query(
        self,
        intent: Dict[str, Any],
        schema: Dict[str, Any],
        retry_attempt: int = 0
    ) -> Optional[str]:
        """Generate SQL using dynamic schema + learned patterns."""
        
        # Get learned patterns
        learned_patterns = self.learning_system.get_patterns_for_prompt()
        
        # Get schema with samples (not just summary - we need the actual sample data!)
        schema_summary = self._format_schema_for_prompt(schema)
        
        # Build prompt
        validation_feedback = ""
        if retry_attempt > 0 and intent.get('_validation_feedback'):
            validation_feedback = f"""
PREVIOUS ATTEMPT FAILED:
{intent['_validation_feedback']}

Please adjust the query to fix this issue.
"""
        
        if self.debug:
            print_text("\n" + "=" * 70, style="dim")
            print_text(f"⚙️  CHAIN OF THOUGHT: SQL Generation (Attempt {retry_attempt + 1})", style="bold yellow")
            print_text("=" * 70, style="dim")
            if retry_attempt > 0:
                print_text(f"\n🔄 Retry Reasoning:", style="cyan")
                print_text(f"   Previous attempt failed: {intent.get('_validation_feedback', 'Unknown')}", style="dim")
                print_text(f"   Strategy: Adjusting query based on feedback", style="dim")
        
        # Build concise prompt
        intent_line = f"Goal: {intent['goal']}"
        if intent.get('search_terms'):
            intent_line += f" | Terms: {', '.join(intent.get('search_terms', []))}"
        if intent.get('date_filter', {}).get('description', 'none') != 'none':
            intent_line += f" | Date: {intent.get('date_filter', {}).get('description')}"
        
        workspace_context = self._format_workspace_config()
        
        # Extract workspace and normalize database names from qualified names
        # e.g., "trass.stories" -> workspace="trass", db_name="stories"
        # This ensures we filter by BOTH workspace AND database
        target_workspaces = set()
        target_dbs = []
        
        for db_name in intent['databases']:
            if '.' in db_name:
                # Qualified name: extract workspace and db nickname
                workspace_part, db_nickname = db_name.rsplit('.', 1)
                target_workspaces.add(workspace_part)
                target_dbs.append(db_nickname)
            else:
                # Simple name: just the database nickname
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
        
        if self.debug:
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
            if self.verbose:
                if retry_attempt == 0:
                    print_text(f"\n💬 Asking AI to generate SQL for: {intent['goal']}", style="cyan")
                else:
                    print_text(f"\n💬 Asking AI to retry SQL generation with feedback:", style="yellow")
                    print_text(f"   Previous feedback: {intent.get('_validation_feedback', 'N/A')}", style="dim")
            
            response = self.llm.invoke([{"role": "user", "content": prompt}])
            sql = response.content.strip()
            
            if self.debug:
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
    
    def _generate_vector_query(
        self,
        intent: Dict[str, Any],
        schema: Dict[str, Any],
        retry_attempt: int = 0
    ) -> Optional[Dict[str, Any]]:
        """
        Generate vector search parameters from intent.
        
        Extracts:
        - search_text: Core semantic query (cleaned of metadata)
        - filters: Metadata filters for ChromaDB (workspace, databases, date range)
        """
        if self.debug:
            print_text("\n" + "=" * 70, style="dim")
            print_text(f"⚙️  CHAIN OF THOUGHT: Vector Query Generation (Attempt {retry_attempt + 1})", style="bold yellow")
            print_text("=" * 70, style="dim")
        
        # Build prompt to extract search text from intent
        workspace_context = self._format_workspace_config()
        
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
            if self.verbose:
                if retry_attempt == 0:
                    print_text(f"\n💬 Extracting search text for: {intent['goal']}", style="cyan")
                else:
                    print_text(f"\n💬 Retrying search text extraction", style="yellow")
            
            response = self.llm.invoke([{"role": "user", "content": prompt}])
            content = response.content.strip()
            
            if self.debug:
                print_text(f"\n📥 LLM Response:", style="cyan")
                print_text(content[:200] + "..." if len(content) > 200 else content, style="dim")
            
            # Clean JSON
            if content.startswith('```json'):
                content = content[7:-3].strip()
            elif content.startswith('```'):
                content = content[3:-3].strip()
            
            import json
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
            
            # Date filter (if needed in future)
            # date_filter = intent.get('date_filter', {})
            # if date_filter.get('days_back'):
            #     # Could add date filtering here
            
            query_params = {
                'search_text': search_text,
                'filters': filters if filters else None
            }
            
            if self.debug:
                print_text(f"\n📝 Vector Query Parameters:", style="cyan")
                print_text(f"   Search text: {search_text}", style="dim")
                print_text(f"   Filters: {filters}", style="dim")
            
            return query_params
        
        except Exception as e:
            print_text(f"❌ Vector query generation failed: {e}", style="red")
            return None
    
    def _execute_query(self, query: Any) -> tuple[Optional[List[Dict[str, Any]]], Optional[str]]:
        """
        Execute query based on mode.
        
        SQL mode: query is SQL string
        Vector mode: query is dict with search_text and filters
        
        Returns: (results, error_message)
        - On success: ([{...}], None)
        - On error: (None, "error message")
        """
        if self.query_mode == "sql":
            return self._execute_sql_query(query)
        elif self.query_mode == "vector":
            return self._execute_vector_query(query)
        else:
            return None, f"Unknown query_mode: {self.query_mode}"
    
    def _execute_sql_query(self, sql: str) -> tuple[Optional[List[Dict[str, Any]]], Optional[str]]:
        """
        Execute SQL query and return results with optional error message.
        Returns: (results, error_message)
        - On success: ([{...}], None)
        - On SQL error: (None, "error message")
        """
        import sqlite3
        
        if self.debug:
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
                
                if self.debug:
                    print_text(f"\n✅ Execution successful", style="green")
                    print_text(f"   Returned {len(results)} rows", style="dim")
                    if results:
                        print_text(f"   Sample row keys: {list(results[0].keys())[:5]}", style="dim")
                
                # Show execution results only in verbose mode
                if self.verbose:
                    print_text(f"✅ Execution successful: {len(results)} rows returned", style="green" if results else "yellow")
                    if results and len(results) > 0:
                        sample = results[0]
                        print_text(f"   Sample columns: {list(sample.keys())[:6]}", style="dim")
                
                return results, None
        
        except sqlite3.OperationalError as e:
            error_msg = f"SQL Error: {str(e)}"
            if self.debug:
                print_text(f"\n❌ SQL execution error: {error_msg}", style="red")
            print_text(f"❌ {error_msg}", style="red")
            return None, error_msg
        
        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            if self.debug:
                print_text(f"\n❌ {error_msg}", style="red")
            print_text(f"❌ {error_msg}", style="red")
            return None, error_msg
    
    def _execute_vector_query(self, query_params: Dict[str, Any]) -> tuple[Optional[List[Dict[str, Any]]], Optional[str]]:
        """
        Execute vector search and return results.
        
        Returns: (results, error_message)
        - On success: ([{page_id, similarity_score, ...}], None)
        - On error: (None, "error message")
        """
        if self.debug:
            print_text("\n" + "=" * 70, style="dim")
            print_text("⚡ CHAIN OF THOUGHT: Vector Search Execution", style="bold yellow")
            print_text("=" * 70, style="dim")
            print_text(f"\n🔍 Searching with: {query_params.get('search_text')}", style="cyan")
        
        try:
            # Get config for defaults - load from main config file
            import json
            config_path = "promaia.config.json"
            with open(config_path, 'r') as f:
                config = json.load(f)
            vector_config = config.get('global', {}).get('vector_search', {})
            n_results = vector_config.get('default_n_results', 20)
            min_similarity = vector_config.get('default_similarity_threshold', 0.75)
            
            # Execute vector search
            search_results = self.vector_db.search(
                query_text=query_params['search_text'],
                filters=query_params.get('filters'),
                n_results=n_results,
                min_similarity=min_similarity
            )
            
            if self.debug:
                print_text(f"\n✅ Search successful", style="green")
                print_text(f"   Returned {len(search_results)} results above {min_similarity} similarity", style="dim")
                if search_results:
                    print_text(f"   Top score: {search_results[0].get('similarity_score', 0):.3f}", style="dim")
            
            if self.verbose:
                print_text(f"✅ Execution successful: {len(search_results)} results returned", style="green" if search_results else "yellow")
                if search_results:
                    print_text(f"   Similarity range: {search_results[-1].get('similarity_score', 0):.3f} - {search_results[0].get('similarity_score', 0):.3f}", style="dim")
            
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
            if self.debug:
                print_text(f"\n❌ {error_msg}", style="red")
            print_text(f"❌ {error_msg}", style="red")
            return None, error_msg
    
    def _display_intent(self, intent: Dict[str, Any]):
        """Display parsed intent to user (verbose mode only)."""
        print_text("\n🎯 Parsed Intent:", style="cyan")
        print_text(f"   Goal: {intent['goal']}", style="white")
        print_text(f"   Databases: {', '.join(intent['databases'])}", style="white")
        if intent.get('search_terms'):
            print_text(f"   Search Terms: {', '.join(intent['search_terms'])}", style="white")
        date_filter = intent.get('date_filter', {})
        if date_filter.get('days_back'):
            print_text(f"   Date Filter: {date_filter['description']}", style="white")
        print()
    
    def _display_compact_summary(self, summary: Dict[str, Any], intent: Dict[str, Any]):
        """Display a compact summary of query results (non-verbose mode)."""
        total = summary['total_count']
        
        # Format database breakdown compactly
        db_breakdown = []
        for db, count in summary['database_breakdown'].items():
            # Shorten database name if needed
            short_db = db.split('.')[-1] if '.' in db else db
            db_breakdown.append(f"{short_db}: {count}")
        
        print_text("📊 Results Summary:", style="bold white")
        print_text(f"• Total: {total} entries ({', '.join(db_breakdown)})", style="white")
        
        # Show date filter if present
        date_filter = intent.get('date_filter', {})
        if date_filter.get('description'):
            print_text(f"• Date Filter: {date_filter['description']}", style="white")
        
        print()  # Blank line before prompt
    
    def _ask_user_confirmation(self, summary: Dict[str, Any]) -> str:
        """
        Ask user if the query was successful and should be learned.
        
        Returns:
            'save' - Save the pattern and continue
            'modify' - Modify the query and try again
            'quit' - Exit to terminal (don't continue to chat)
        """
        try:
            response = input("\nEnter (accept) / m(odify) / q(uit): ").strip().lower()
            
            if response == 'm':
                return 'modify'
            elif response == 'q':
                print_text("   Quitting...", style="dim")
                return 'quit'
            else:  # Enter or any other key = accept
                return 'save'
        
        except (KeyboardInterrupt, EOFError):
            print_text("\n   Quitting...", style="dim")
            return 'quit'
    
    def _format_schema_for_prompt(self, schema: Dict[str, Any]) -> str:
        """Format schema with sample rows - let LLM infer semantics from examples."""
        output = ""
        
        main_table = schema.get('main_content_table', 'unified_content')
        important_tables = [main_table, 'gmail_content', 'generic_content', 'unified_content']
        
        for table, info in schema['tables'].items():
            if table in important_tables:
                output += f"\n{table} ({info['row_count']} rows):\n"
                
                # Show sample rows with ALL columns - LLM infers semantics from actual data
                samples = info.get('samples', [])
                if samples:
                    output += "  Sample rows (recent data):\n"
                    for i, sample in enumerate(samples, 1):
                        output += f"\n  Row {i}:\n"
                        for col_name, value in sample.items():
                            if value is not None:
                                # Format value
                                if isinstance(value, str):
                                    val_str = f'"{value}"' if len(value) < 70 else f'"{value[:70]}..."'
                                else:
                                    val_str = str(value)
                                output += f"    {col_name}: {val_str}\n"
                    output += "\n"
                else:
                    # Fallback: just show columns if no samples
                    output += "  Columns: " + ", ".join(col['name'] for col in info['columns'][:15]) + "\n"
        
        return output


# Convenience function for integration with existing code
def get_agentic_query_processor():
    """Get the agentic query processor instance."""
    return AgenticNLQueryProcessor()

