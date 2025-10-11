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
    NLContextLogger,
    ResultValidator,
    format_result_summary_for_user
)

# Import query strategies
from .query_strategies import QueryStrategy, SQLQueryStrategy, VectorQueryStrategy

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
    
    Uses Strategy Pattern to support both SQL and vector search modes:
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
        
        # Initialize shared agentic components
        self.schema_explorer = SchemaExplorer(db_path)
        self.context_logger = NLContextLogger()
        self.validator = ResultValidator()
        
        # Load workspace config for AI context
        self.workspace_config = self._load_workspace_config()
        
        # Initialize strategy based on mode
        if query_mode == "sql":
            self.strategy = SQLQueryStrategy(db_path)
        elif query_mode == "vector":
            self.strategy = VectorQueryStrategy()
        else:
            raise ValueError(f"Unknown query_mode: {query_mode}")
        
        # Initialize strategy-specific components
        status_msg = self.strategy.initialize(verbose=self.verbose, debug=self.debug)
        if self.verbose:
            print_text(status_msg, style="green")
        
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
            
            # Delegate to strategy - NO if/else branches!
            validation_feedback = ""
            if attempt > 0 and intent.get('_validation_feedback'):
                validation_feedback = f"""
PREVIOUS ATTEMPT FAILED:
{intent['_validation_feedback']}

Please adjust the query to fix this issue.
"""
            
            generated_query = self.strategy.generate_query(
                intent=intent,
                schema=schema,
                retry_attempt=attempt,
                llm=self.llm,
                workspace_context=self._format_workspace_config(),
                schema_summary=self._format_schema_for_prompt(schema),
                validation_feedback=validation_feedback,
                verbose=self.verbose,
                debug=self.debug
            )
            
            if not generated_query:
                attempt += 1
                continue
            
            # Display query using strategy - NO if/else branches!
            self.strategy.display_generated_query(generated_query, self.verbose)
            
            if self.verbose:
                print_text(f"\n🔍 Executing query...", style="dim")
            
            # Execute query using strategy - NO if/else branches!
            results, sql_error = self.strategy.execute_query(
                query=generated_query,
                verbose=self.verbose,
                debug=self.debug
            )
            
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
            # Save to learning index (only if strategy supports it)
            if self.strategy.should_save_pattern():
                pattern = {
                    "user_query": user_query,
                    "intent": intent,
                    "generated_sql": generated_query,
                    "result_count": summary['total_count'],
                    "databases": summary['databases'],
                    "notes": f"Validated successfully. {validation_result['message']}"
                }
                self.strategy.save_pattern(pattern)
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

Rules for database names - CRITICAL:
- ONLY include databases that are EXPLICITLY mentioned in the query (e.g., "gmail", "stories", "notion")
- If the user specifies a database type, use ONLY that database - do not add others from the same workspace
- ALWAYS use qualified names (workspace.database) when a workspace is mentioned in the query
- If the query mentions BOTH a workspace AND a database, you MUST combine them as "workspace.database"
- If ONLY a database is mentioned with no workspace context, use the simple name
- Extract specific search terms from the query
- Parse date expressions: "last N months" → days_back: N*30, "past week" → days_back: 7
- If no date mentioned, set days_back: null

Examples of CORRECT database naming:
- "trass gmail about X" → databases: ["trass.gmail"] ✓ (workspace + database = qualified name)
- "koii stories with Y" → databases: ["koii.stories"] ✓ (workspace + database = qualified name)
- "stories in the koii workspace" → databases: ["koii.stories"] ✓ (workspace + database = qualified name)
- "koii workspace notion stories" → databases: ["koii.stories"] ✓ (workspace + database, ignore "notion" as descriptor)
- "find X in stories" → databases: ["stories"] ✓ (no workspace mentioned = simple name)
- "trass gmail about X" → databases: ["trass.gmail", "trass.yp"] ✗ WRONG (don't add unrequested databases)

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

