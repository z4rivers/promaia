"""
Simple LangGraph-based query system for Promaia.
Follows BUILD → DO/TEST → MEASURE/LEARN → REPEAT cycle.
"""
from typing import List, Dict, Any, Optional, TypedDict
from datetime import datetime
import sqlite3
import os
import json

from pydantic import BaseModel, Field
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import StateGraph, END


class QueryState(TypedDict):
    """Simple state that flows through the nodes."""
    user_query: str
    intent: Optional[Dict[str, Any]]
    generated_sql: Optional[str] 
    results: Optional[List[Dict[str, Any]]]
    errors: List[str]
    retry_count: int


# Removed SimpleIntent - using direct JSON parsing instead


class IntelligentQueryProcessor:
    """Simple query processor following BUILD → DO → MEASURE → REPEAT."""
    
    def __init__(self, llm, db_path: str = "data/hybrid_metadata.db"):
        self.llm = llm
        self.db_path = db_path
        self.graph = self._build_graph()
        self.schema = self._load_basic_schema()
    
    def _load_basic_schema(self) -> Dict[str, Any]:
        """BUILD: Load schema with ACTUAL data samples for AI context."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Get available databases with counts
                cursor.execute("""
                    SELECT database_name, COUNT(*) as count,
                           MIN(created_time) as earliest,
                           MAX(created_time) as latest
                    FROM unified_content 
                    GROUP BY database_name
                    ORDER BY count DESC
                """)
                databases = []
                for row in cursor.fetchall():
                    databases.append({
                        "name": row[0], 
                        "count": row[1],
                        "date_range": f"{row[2]} to {row[3]}" if row[2] and row[3] else "No dates"
                    })
                
                # Get actual successful query examples for each data type
                query_templates = self._generate_query_examples(cursor)
                
                return {
                    "databases": databases,
                    "main_table": "unified_content", 
                    "key_columns": ["page_id", "title", "database_name", "created_time", "last_edited_time", "metadata"],
                    "query_templates": query_templates,
                    "date_info": "Dates are in YYYY-MM-DD format. Use created_time or last_edited_time for date filtering."
                }
        except Exception as e:
            print(f"⚠️ Schema loading failed: {e}")
            return {"databases": [], "main_table": "unified_content", "key_columns": [], "query_templates": []}

    def _generate_query_examples(self, cursor) -> List[Dict[str, Any]]:
        """Generate concrete, working query examples for each data type."""
        examples = []
        
        # Check what databases actually exist in the user's system
        cursor.execute("SELECT DISTINCT database_name FROM unified_content LIMIT 20")
        available_dbs = [row[0] for row in cursor.fetchall()]
        
        # GMAIL QUERIES - Handle both gmail and workspace.gmail formats
        gmail_dbs = [db for db in available_dbs if 'gmail' in db.lower()]
        if gmail_dbs:
            gmail_db_list = ', '.join([f"'{db}'" for db in gmail_dbs])
            examples.extend([
                {
                    "query_type": "Gmail - Find by subject keyword",
                    "user_query": "emails about mgm",
                    "sql_pattern": f"SELECT page_id, title, database_name, created_time, metadata FROM unified_content WHERE database_name IN ({gmail_db_list}) AND (title LIKE '%mgm%' OR metadata LIKE '%mgm%') LIMIT 200",
                    "notes": "Gmail: Search in title (=subject) and metadata. Include ALL gmail databases."
                },
                {
                    "query_type": "Gmail - Find by sender/domain", 
                    "user_query": "emails from shipbob.com",
                    "sql_pattern": f"SELECT page_id, title, database_name, created_time, metadata FROM unified_content WHERE database_name IN ({gmail_db_list}) AND metadata LIKE '%shipbob.com%' LIMIT 200",
                    "notes": "Gmail: Search metadata for sender domain info."
                }
            ])
        
        # JOURNAL QUERIES - Date-based content
        journal_dbs = [db for db in available_dbs if 'journal' in db.lower()]
        if journal_dbs:
            journal_db_list = ', '.join([f"'{db}'" for db in journal_dbs])
            examples.extend([
                {
                    "query_type": "Journal - Date range", 
                    "user_query": "journal entries between feb-may 2025",
                    "sql_pattern": f"SELECT page_id, title, database_name, created_time, metadata FROM unified_content WHERE database_name IN ({journal_db_list}) AND DATE(created_time) BETWEEN '2025-02-01' AND '2025-05-31' LIMIT 10000",
                    "notes": "Journal: Use DATE() for date filtering, high limit for 'all' queries."
                },
                {
                    "query_type": "Journal - Content search",
                    "user_query": "journal entries about productivity", 
                    "sql_pattern": f"SELECT page_id, title, database_name, created_time, metadata FROM unified_content WHERE database_name IN ({journal_db_list}) AND (title LIKE '%productivity%' OR metadata LIKE '%productivity%') LIMIT 200",
                    "notes": "Journal: Search both title and metadata for content keywords."
                }
            ])
        
        # DISCORD QUERIES - Direct content search
        discord_dbs = [db for db in available_dbs if 'discord' in db.lower()]
        if discord_dbs:
            discord_db_list = ', '.join([f"'{db}'" for db in discord_dbs])
            examples.append({
                "query_type": "Discord - Content search",
                "user_query": "discord messages about meeting",
                "sql_pattern": f"SELECT page_id, title, database_name, created_time, metadata FROM unified_content WHERE database_name IN ({discord_db_list}) AND (title LIKE '%meeting%' OR metadata LIKE '%meeting%') LIMIT 200", 
                "notes": "Discord: Search title and metadata directly - no special content loading needed."
            })
        
        # NOTION/STORIES QUERIES - Content-based
        notion_dbs = [db for db in available_dbs if 'stories' in db.lower() or 'cms' in db.lower()]
        if notion_dbs:
            notion_db_list = ', '.join([f"'{db}'" for db in notion_dbs])
            examples.append({
                "query_type": "Notion - Content search",
                "user_query": "stories about technology",
                "sql_pattern": f"SELECT page_id, title, database_name, created_time, metadata FROM unified_content WHERE database_name IN ({notion_db_list}) AND (title LIKE '%technology%' OR metadata LIKE '%technology%') LIMIT 200",
                "notes": "Notion: Search title and metadata, content loaded via markdown files."
            })
        
        return examples

    def _build_graph(self) -> StateGraph:
        """BUILD: Simple 3-node workflow."""
        workflow = StateGraph(QueryState)
        
        workflow.add_node("parse", self._parse_node)
        workflow.add_node("execute", self._execute_node) 
        workflow.add_node("measure", self._measure_node)
        
        workflow.set_entry_point("parse")
        workflow.add_edge("parse", "execute")
        workflow.add_edge("execute", "measure")
        
        # Simple retry logic
        workflow.add_conditional_edges(
            "measure",
            self._should_retry,
            {"retry": "parse", "done": END}
        )
        
        return workflow.compile()

    def process_query(self, user_query: str, scope_databases: List[str] = None) -> Dict[str, Any]:
        """Main entry point."""
        initial_state = QueryState(
            user_query=f"From {scope_databases}: {user_query}" if scope_databases else user_query,
            intent=None,
            generated_sql=None,
            results=None,
            errors=[],
            retry_count=0
        )
        
        try:
            final_state = self.graph.invoke(initial_state)
            
            if final_state.get("results"):
                # Group by database_name for compatibility
                grouped = {}
                for item in final_state["results"]:
                    db = item.get("database_name", "unknown")
                    if db not in grouped:
                        grouped[db] = []
                    grouped[db].append(item)
                
                return {
                    "success": True,
                    "results": grouped,
                    "intent": final_state.get("intent", {}),
                    "sql": final_state.get("generated_sql", ""),
                    "errors": final_state.get("errors", [])
                }
            else:
                return {
                    "success": False,
                    "results": {},
                    "intent": final_state.get("intent", {}),
                    "errors": final_state.get("errors", ["No results"])
                }
        except Exception as e:
            return {"success": False, "results": {}, "intent": None, "errors": [str(e)]}

    def _parse_node(self, state: QueryState) -> QueryState:
        """BUILD: Parse query into simple intent."""
        # Handle retry - increment counter if we're coming back from a failure
        if state.get("intent") is not None or state.get("generated_sql") is not None:
            # This is a retry - increment and clear previous attempt
            state["retry_count"] += 1
            print(f"🔄 Retrying (attempt {state['retry_count']})")
            state["intent"] = None
            state["generated_sql"] = None
            state["errors"] = []
            
        try:
            available_dbs = [db["name"] for db in self.schema["databases"]]
            
            prompt = f"""Parse this query into the required format:

Query: "{state['user_query']}"
Available databases: {available_dbs}

Database context:
{chr(10).join([f"- {db['name']}: {db['count']} entries ({db['date_range']})" for db in self.schema['databases'][:8]])}

You must respond with actual values in this exact structure:
{{
    "goal": "what the user wants to find",
    "databases": ["list", "of", "relevant", "databases"],  
    "search_terms": ["key", "content", "search", "terms"],
    "limit": 1000
}}

IMPORTANT PARSING RULES:
- If query mentions "journal", include databases like "journal", "trass.journal", etc.
- If query mentions "gmail/email", include "gmail", "trass.gmail", etc.
- For "find all X entries between dates": search_terms should be empty [] (dates are handled separately)
- For "entries containing X" or "about X": search_terms should include ["X"]
- For "entries from person Y": search_terms should include ["Y"]
- Don't include generic words like "entries", "between", "all" as search terms

LIMIT RULES:
- If query says "find ALL" or "all entries": use limit 10000 (very high)
- If query says "recent" or "few": use limit 50
- If query asks for specific person/topic: use limit 200
- Default: use limit 1000

Examples:
- "find all journal entries between feb-may 2025" → search_terms: [], limit: 10000
- "recent journal entries about graham" → search_terms: ["graham"], limit: 50
- "emails from shipbob" → search_terms: ["shipbob"], limit: 200

Return only the JSON object:"""

            response = self.llm.invoke([
                SystemMessage(content="You are a JSON parser. Return only valid JSON with actual values, never schemas or descriptions."),
                HumanMessage(content=prompt)
            ])
            
            # Parse the JSON manually since structured output isn't working
            import json
            json_str = response.content.strip()
            if json_str.startswith('```json'):
                json_str = json_str[7:-3].strip()
            elif json_str.startswith('```'):
                json_str = json_str[3:-3].strip()
                
            parsed_intent = json.loads(json_str)
            
            state["intent"] = parsed_intent
            print(f"✅ Parsed: {parsed_intent['goal']}")
            
        except Exception as e:
            state["errors"] = [f"Parse failed: {e}"]
            print(f"❌ Parse error: {e}")
        
        return state

    def _execute_node(self, state: QueryState) -> QueryState:
        """DO/TEST: Generate SQL and execute it."""
        if not state.get("intent"):
            state["errors"] = ["No intent to execute"]
            return state
            
        try:
            intent = state["intent"]
            
            # Generate SQL with rich context
            sql_prompt = f"""Generate SQLite query for: {intent['goal']}

=== DATABASE CONTEXT ===
Table: {self.schema['main_table']}
Columns: {', '.join(self.schema['key_columns'])}
{self.schema['date_info']}

Available databases with data:
{chr(10).join([f"- {db['name']}: {db['count']} entries ({db['date_range']})" for db in self.schema['databases']])}

=== PROVEN QUERY TEMPLATES ===
Here are concrete, working examples for your database:
{chr(10).join([f"TYPE: {template['query_type']}" + chr(10) + f"QUERY: \"{template['user_query']}\"" + chr(10) + f"SQL: {template['sql_pattern']}" + chr(10) + f"NOTES: {template['notes']}" + chr(10) for template in self.schema.get('query_templates', [])])}

=== YOUR TASK ===
Query goal: {intent['goal']}
Target databases: {intent['databases']}
Search terms: {intent['search_terms']}
Result limit: {intent['limit']}

CRITICAL INSTRUCTIONS:
1. **FOLLOW THE PROVEN TEMPLATES ABOVE** - These are tested, working patterns for your database
2. **Match query types** - Find the template that matches the user's query type (Gmail keyword, Journal date range, etc.)
3. **Use exact SQL patterns** - Adapt the template SQL to your specific query parameters
4. **Include ALL relevant databases** - If user says "gmail", include both "gmail" AND "workspace.gmail" databases
5. **Handle limits correctly** - Use template limits, but increase to 10000 for "all" queries

Generate the SQLite query:"""

            sql_response = self.llm.invoke([
                SystemMessage(content="Generate working SQLite queries."),
                HumanMessage(content=sql_prompt)
            ])
            
            # Clean SQL
            sql = sql_response.content.strip()
            if "```" in sql:
                import re
                match = re.search(r'```(?:sql)?\s*(.*?)\s*```', sql, re.DOTALL)
                if match:
                    sql = match.group(1).strip()
            
            state["generated_sql"] = sql
            
            # Execute SQL
            if os.getenv("MAIA_DEBUG") == "1":
                print(f"🔍 Executing: {sql}")
                
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute(sql)
                
                results = [dict(row) for row in cursor.fetchall()]
                state["results"] = results
                
            print(f"✅ Executed: {len(results)} results")
            
        except Exception as e:
            state["errors"] = [f"Execute failed: {e}"]
            print(f"❌ Execute error: {e}")
        
        return state

    def _measure_node(self, state: QueryState) -> QueryState:
        """MEASURE: Validate results."""
        results = state.get("results", [])
        errors = state.get("errors", [])
        
        if results and len(results) > 0:
            print(f"✅ Success: {len(results)} results")
            # Success - no changes needed
        elif errors:
            print(f"❌ Failed: {errors}")
            # Errors will trigger retry if count < max
        else:
            print("⚠️ No results found")
            state["errors"] = ["No results found"]
        
        return state

    def _should_retry(self, state: QueryState) -> str:
        """LEARN: Decide whether to retry."""
        # Success - we have results
        if state.get("results"):
            return "done"
        
        # Too many retries
        if state["retry_count"] >= 2:  # Max 2 retries
            print("🛑 Max retries reached")
            return "done"
        
        # Has errors and can still retry
        if state.get("errors"):
            return "retry"
        
        return "done"
