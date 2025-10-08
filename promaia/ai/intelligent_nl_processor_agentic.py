"""
Enhanced Agentic Natural Language Processor

This replaces the hardcoded example-based system with a fully agentic approach:
- Dynamic schema exploration
- Learning from successful queries
- Result validation and iteration
- User confirmation with detailed summaries
"""
import os
from typing import List, Dict, Any, Optional

# Load environment variables
from promaia.utils.config import load_environment
load_environment()

from promaia.config.databases import get_database_manager
from promaia.utils.display import print_text

# Import our agentic components
from .agentic_nl_processor import (
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
    
    Key differences from basic system:
    1. Uses PRAGMA to discover schema dynamically
    2. Learns from successful queries (rolling index of 20)
    3. Validates results and retries if needed
    4. Saves context logs for user inspection
    5. Asks for user confirmation before saving patterns
    """
    
    def __init__(self, db_path: str = "data/hybrid_metadata.db", debug: bool = False):
        self.db_path = db_path
        self.debug = debug or os.getenv("MAIA_DEBUG") == "1"
        
        # Initialize agentic components
        self.schema_explorer = SchemaExplorer(db_path)
        self.learning_system = QueryLearningSystem()
        self.context_logger = NLContextLogger()
        self.validator = ResultValidator()
        
        # Initialize LLM
        self.llm = PromaiLLMAdapter(client_type="auto")
        print_text(f"✅ Initialized agentic NL processor with {self.llm.client_type}", style="green")
        if self.debug:
            print_text("🐛 Debug mode enabled - showing chain of thought", style="yellow")
    
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
        print_text(f"\n🤖 Processing query: '{user_query}'", style="cyan")
        
        # Step 1: Explore schema dynamically
        print_text("🔍 Step 1: Exploring database schema...", style="dim")
        schema = self.schema_explorer.explore_schema()
        
        # Step 2: Parse intent
        print_text("🧠 Step 2: Parsing intent...", style="dim")
        intent = self._parse_intent(user_query, schema, workspace)
        
        if not intent:
            return {
                "success": False,
                "error": "Failed to parse query intent",
                "results": {}
            }
        
        # Show parsed intent to user
        self._display_intent(intent)
        
        # Step 3: Generate and execute query (with retries)
        attempt = 0
        results = None
        generated_sql = None
        validation_result = None
        
        while attempt <= max_retries:
            if attempt > 0:
                print_text(f"\n🔄 Retry attempt {attempt}/{max_retries}", style="yellow")
            
            print_text("⚙️  Step 3: Generating SQL query...", style="dim")
            generated_sql = self._generate_sql(intent, schema, attempt)
            
            if not generated_sql:
                attempt += 1
                continue
            
            # Always show generated SQL
            print_text(f"\n📝 Generated SQL:", style="cyan")
            print_text(generated_sql if len(generated_sql) < 300 else generated_sql[:300] + "...", style="dim")
            
            print_text(f"\n🔍 Executing query...", style="dim")
            results, sql_error = self._execute_sql(generated_sql)
            
            # If SQL error, use that as validation feedback
            if sql_error:
                print_text(f"❌ SQL Error during execution", style="red")
                intent['_validation_feedback'] = sql_error
                attempt += 1
                continue
            
            if results is None:
                attempt += 1
                continue
            
            # Step 4: Validate results
            print_text("✅ Step 4: Validating results...", style="dim")
            is_valid, message = self.validator.validate_results(intent, results)
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
                print_text(f"✅ {message}", style="green")
                break
            else:
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
                "sql": generated_sql,
                "results": {}
            }
        
        # Step 5: Generate result summary
        summary = self.validator.generate_result_summary(results)
        
        # Step 6: Save draft context log
        query_info = {
            "user_query": user_query,
            "intent": intent,
            "generated_sql": generated_sql,
            "result_count": summary['total_count'],
            "databases_in_results": summary['databases'],
            "database_breakdown": summary['database_breakdown'],
            "sample_results": summary['sample_results'],
            "validation": validation_result,
            "retries": attempt
        }
        
        log_file = self.context_logger.save_draft_context(query_info)
        summary_file = self.context_logger.save_summary(query_info)
        
        # Step 7: Show summary and ask for user confirmation
        print_text(format_result_summary_for_user(summary, intent), style="white")
        
        if log_file:
            print_text(f"📝 Draft context saved to: {log_file}", style="dim")
        if summary_file:
            print_text(f"📄 Summary saved to: {summary_file}", style="dim")
        
        # Ask user if query was successful
        should_learn = self._ask_user_confirmation(summary)
        
        if should_learn:
            # Save to learning index
            pattern = {
                "user_query": user_query,
                "intent": intent,
                "generated_sql": generated_sql,
                "result_count": summary['total_count'],
                "databases": summary['databases'],
                "notes": f"Validated successfully. {validation_result['message']}"
            }
            self.learning_system.save_successful_pattern(pattern)
        
        # Group results by database for compatibility with existing code
        grouped_results = {}
        for result in results:
            db = result.get('database_name', 'unknown')
            if db not in grouped_results:
                grouped_results[db] = []
            grouped_results[db].append(result)
        
        return {
            "success": True,
            "results": grouped_results,
            "intent": intent,
            "sql": generated_sql,
            "summary": summary,
            "learned": should_learn
        }
    
    def _parse_intent(
        self,
        user_query: str,
        schema: Dict[str, Any],
        workspace: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Parse user query into structured intent using LLM."""
        available_dbs = schema.get('available_databases', [])
        
        prompt = f"""Parse this natural language query into structured intent:

Query: "{user_query}"

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
    
    def _generate_sql(
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
        
        prompt = f"""Generate a SQLite query based on this intent:

{schema_summary}

{learned_patterns}

{validation_feedback}

INTENT:
Goal: {intent['goal']}
Target Databases: {intent['databases']}
Search Terms: {intent.get('search_terms', [])}
Date Filter: {intent.get('date_filter', {}).get('description', 'none')}

INSTRUCTIONS:
1. Use table aliases (e.g., FROM unified_content u)
2. Review sample data above to understand which fields contain searchable content
3. For content searches, look at the sample values to identify text-heavy fields
4. JOIN with specialized tables (gmail_content, etc.) to access full content
5. Apply date filtering using appropriate timestamp columns
6. Use LIKE '%term%' for text searches, and search ALL relevant text fields
7. Limit results to 1000

Generate the SQL query (return only the SQL, no markdown):"""
        
        if self.debug:
            print_text(f"\n📤 SQL Generation Prompt:", style="cyan")
            print_text(f"   Intent: {intent['goal']}", style="dim")
            print_text(f"   Databases: {', '.join(intent['databases'])}", style="dim")
            print_text(f"   Search terms: {', '.join(intent.get('search_terms', []))}", style="dim")
            print_text(f"   Using {len(self.learning_system.load_successful_patterns())} learned patterns", style="dim")
        
        try:
            # Always log what we're asking the AI
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
    
    def _execute_sql(self, sql: str) -> tuple[Optional[List[Dict[str, Any]]], Optional[str]]:
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
                
                # Always show execution results
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
    
    def _display_intent(self, intent: Dict[str, Any]):
        """Display parsed intent to user."""
        print_text("\n🎯 Parsed Intent:", style="cyan")
        print_text(f"   Goal: {intent['goal']}", style="white")
        print_text(f"   Databases: {', '.join(intent['databases'])}", style="white")
        if intent.get('search_terms'):
            print_text(f"   Search Terms: {', '.join(intent['search_terms'])}", style="white")
        date_filter = intent.get('date_filter', {})
        if date_filter.get('days_back'):
            print_text(f"   Date Filter: {date_filter['description']}", style="white")
        print()
    
    def _ask_user_confirmation(self, summary: Dict[str, Any]) -> bool:
        """Ask user if the query was successful and should be learned."""
        try:
            print_text("\n💭 Save this query pattern for future learning?", style="bold cyan")
            print_text("   • Press Enter to accept and save", style="dim")
            print_text("   • Type 'm' to modify the query", style="dim")
            print_text("   • Type 'q' to skip saving", style="dim")
            
            response = input("\n   Your choice [Enter/m/q]: ").strip().lower()
            
            if response == 'm':
                print_text("\n   Query modification not yet implemented.", style="yellow")
                print_text("   Pattern not saved.", style="dim")
                return False
            elif response == 'q':
                print_text("   Pattern not saved.", style="dim")
                return False
            else:  # Enter or any other key = accept
                return True
        
        except (KeyboardInterrupt, EOFError):
            print_text("\n   Skipped learning step.", style="dim")
            return False
    
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

