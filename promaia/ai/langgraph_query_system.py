"""
LangGraph-based intelligent query system for Promaia.
Uses AI reasoning with structured outputs instead of hard-coded patterns.
"""
from typing import List, Dict, Any, Optional, TypedDict, Annotated
from datetime import datetime, timedelta
import json
import sqlite3
import operator
import os
from dataclasses import dataclass

from pydantic import BaseModel, Field
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import create_react_agent


class QueryState(TypedDict):
    """State that flows through the LangGraph nodes."""
    user_query: str
    parsed_intent: Optional[Dict[str, Any]]
    available_schemas: Optional[Dict[str, Any]]
    execution_plan: Optional[Dict[str, Any]]
    generated_sql: Optional[str]
    execution_results: Optional[List[Dict[str, Any]]]
    errors: List[str]  # Current errors (no auto-accumulation)
    retry_count: int
    final_results: Optional[Dict[str, List[Dict[str, Any]]]]


# Structured output models
class TimeConstraint(BaseModel):
    """Structured time constraint with AI reasoning."""
    constraint_type: str = Field(description="Type: 'specific_dates', 'relative_period', 'sampling_strategy', 'multiple_periods'")
    periods: List[Dict[str, Any]] = Field(description="List of time periods with start/end dates or descriptions")
    sampling_approach: Optional[str] = Field(description="How to sample: 'random', 'recent', 'distributed', 'first_N', 'last_N'")
    total_limit: Optional[int] = Field(description="Maximum total results across all periods")


class ContentScope(BaseModel):
    """What content types to search."""
    primary_sources: List[str] = Field(description="Main databases to search: journal, gmail, notion, discord, etc.")
    content_types: List[str] = Field(description="Specific content types within sources")
    workspace_filter: Optional[str] = Field(description="Workspace constraint if explicitly mentioned")


class SearchStrategy(BaseModel):
    """How to execute the search."""
    search_type: str = Field(description="'metadata_only', 'content_search', 'hybrid'")
    search_terms: List[str] = Field(description="Specific terms to search for in content")
    property_filters: Dict[str, str] = Field(description="Property/value filters for metadata")
    person_filters: List[str] = Field(description="Names/emails to filter by")


class QueryIntent(BaseModel):
    """Complete structured intent from natural language query."""
    user_goal: str = Field(description="What the user actually wants to accomplish")
    content_scope: ContentScope
    time_constraints: Optional[TimeConstraint] = None
    search_strategy: SearchStrategy
    complexity_level: str = Field(description="'simple', 'moderate', 'complex' - affects execution approach")
    expected_result_count: Optional[str] = Field(description="'few', 'many', 'comprehensive', or specific number")


class IntelligentQueryProcessor:
    """
    LangGraph-powered query processor using AI reasoning instead of patterns.
    """
    
    def __init__(self, llm, db_path: str = "data/hybrid_metadata.db"):
        self.llm = llm
        self.db_path = db_path
        self.graph = self._build_graph()
        self._load_schema_info()
    
    def _load_schema_info(self):
        """Load comprehensive SQLite schema information for the AI."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Get all table schemas
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                tables = [row[0] for row in cursor.fetchall()]
                
                table_schemas = {}
                for table in tables:
                    cursor.execute(f"PRAGMA table_info({table})")
                    columns = cursor.fetchall()
                    table_schemas[table] = {
                        "columns": [{"name": col[1], "type": col[2], "nullable": not col[3]} for col in columns],
                        "primary_key": [col[1] for col in columns if col[5]]
                    }
                
                # Get unified_content detailed schema
                cursor.execute("PRAGMA table_info(unified_content)")
                unified_columns = cursor.fetchall()
                
                # Get database statistics with sample data
                cursor.execute("""
                    SELECT database_name, COUNT(*) as count, 
                           MIN(created_time) as earliest, MAX(created_time) as latest,
                           GROUP_CONCAT(DISTINCT content_type) as content_types
                    FROM unified_content 
                    GROUP BY database_name
                """)
                db_stats = cursor.fetchall()
                
                # Get sample of actual data to help AI understand structure
                cursor.execute("""
                    SELECT database_name, title, created_time, content_type
                    FROM unified_content 
                    ORDER BY RANDOM() 
                    LIMIT 5
                """)
                sample_data = cursor.fetchall()
                
                # Load database configuration for proper naming context
                try:
                    from promaia.config.databases import get_database_manager
                    db_manager = get_database_manager()
                    config_mapping = {}
                    
                    for config_key, db_config in db_manager.databases.items():
                        workspace = db_config.workspace
                        nickname = db_config.nickname
                        database_id = db_config.database_id
                        
                        config_mapping[config_key] = {
                            "workspace": workspace,
                            "nickname": nickname,
                            "database_id": database_id,
                            "source_type": db_config.source_type,
                            "description": getattr(db_config, 'description', '')
                        }
                    
                except Exception as e:
                    print(f"Warning: Could not load database config: {e}")
                    config_mapping = {}
                
                self.schema_info = {
                    "database_type": "SQLite",
                    "available_functions": [
                        "SUBSTR", "LENGTH", "LOWER", "UPPER", "TRIM", "REPLACE",
                        "DATE", "DATETIME", "STRFTIME", "JULIANDAY",
                        "COUNT", "SUM", "AVG", "MIN", "MAX", "GROUP_CONCAT",
                        "CASE", "COALESCE", "IFNULL", "RANDOM"
                    ],
                    "not_available": ["ARRAY_AGG", "STRING_AGG", "UNNEST"],
                    "all_tables": table_schemas,
                    "unified_content_columns": [{"name": col[1], "type": col[2]} for col in unified_columns],
                    "database_statistics": [
                        {
                            "name": row[0], 
                            "count": row[1], 
                            "earliest": row[2], 
                            "latest": row[3],
                            "content_types": row[4].split(',') if row[4] else []
                        } for row in db_stats
                    ],
                    "sample_data": [
                        {
                            "database_name": row[0],
                            "title": row[1], 
                            "created_time": row[2],
                            "content_type": row[3]
                        } for row in sample_data
                    ],
                    "database_config": config_mapping
                }
                
                print(f"✅ Schema loaded: {len(table_schemas)} tables, {len(db_stats)} databases")
                
        except Exception as e:
            print(f"Warning: Could not load schema info: {e}")
            self.schema_info = {
                "database_type": "SQLite",
                "available_functions": ["SUBSTR", "LENGTH", "COUNT", "DATE"],
                "not_available": ["ARRAY_AGG", "STRING_AGG"],
                "all_tables": {},
                "unified_content_columns": [],
                "database_statistics": [],
                "sample_data": []
            }

    def _build_graph(self) -> StateGraph:
        """Build the LangGraph workflow for intelligent query processing."""
        
        workflow = StateGraph(QueryState)
        
        # Add nodes
        workflow.add_node("parse_intent", self._parse_intent_node)
        workflow.add_node("analyze_schema", self._analyze_schema_node) 
        workflow.add_node("plan_execution", self._plan_execution_node)
        workflow.add_node("generate_sql", self._generate_sql_node)
        workflow.add_node("execute_query", self._execute_query_node)
        workflow.add_node("validate_results", self._validate_results_node)
        workflow.add_node("refine_approach", self._refine_approach_node)
        
        # Define the flow
        workflow.set_entry_point("parse_intent")
        
        workflow.add_edge("parse_intent", "analyze_schema")
        workflow.add_edge("analyze_schema", "plan_execution")  
        workflow.add_edge("plan_execution", "generate_sql")
        workflow.add_edge("generate_sql", "execute_query")
        workflow.add_edge("execute_query", "validate_results")
        
        # Conditional edges for retry logic
        workflow.add_conditional_edges(
            "validate_results",
            self._should_retry,
            {
                "retry": "refine_approach",
                "success": END
            }
        )
        
        workflow.add_edge("refine_approach", "generate_sql")  # Loop back to generate new SQL
        
        return workflow.compile()

    def process_query(self, user_query: str, scope_databases: List[str] = None) -> Dict[str, Any]:
        """Main entry point: process query using LangGraph intelligence."""
        
        initial_state = QueryState(
            user_query=user_query,
            parsed_intent=None,
            available_schemas=None,
            execution_plan=None,
            generated_sql=None,
            execution_results=None,
            errors=[],
            retry_count=0,
            final_results=None
        )
        
        # Include scope constraint in query context
        if scope_databases:
            initial_state["user_query"] = f"From databases [{', '.join(scope_databases)}]: {user_query}"
        
        try:
            # Run the graph
            final_state = self.graph.invoke(initial_state)
            
            if final_state.get("final_results"):
                return {
                    "success": True,
                    "results": final_state["final_results"],
                    "intent": final_state.get("parsed_intent", {}),
                    "sql": final_state.get("generated_sql", ""),
                    "errors": final_state.get("errors", [])
                }
            else:
                return {
                    "success": False,
                    "results": {},
                    "intent": final_state.get("parsed_intent", {}),
                    "errors": final_state.get("errors", ["No results generated"])
                }
                
        except Exception as e:
            return {
                "success": False,
                "results": {},
                "intent": None,
                "errors": [str(e)]
            }

    def _parse_intent_node(self, state: QueryState) -> QueryState:
        """Parse natural language into structured intent using AI reasoning."""
        
        system_prompt = f"""You are an expert at understanding user intent for database queries.
        
Available databases: {[db['name'] for db in self.schema_info['database_statistics']]}
Current date: {datetime.now().strftime('%Y-%m-%d')}

Parse this natural language query into structured intent. Pay special attention to:
1. Complex time expressions like "first week of march and first week of april"
2. Sampling strategies like "a smattering" or "some from each month"  
3. Content vs metadata search requirements
4. Multiple time periods or date ranges

User query: {state['user_query']}

Return structured JSON matching the QueryIntent schema."""
        
        try:
            # Use LLM with structured output
            intent_response = self.llm.with_structured_output(QueryIntent).invoke([
                SystemMessage(content=system_prompt),
                HumanMessage(content=state['user_query'])
            ])
            
            state["parsed_intent"] = intent_response.dict()
            print(f"✅ Intent parsed: {intent_response.user_goal}")
            
        except Exception as e:
            self._add_error_if_new(state, f"Intent parsing failed: {str(e)}")
            print(f"❌ Intent parsing error: {e}")
            # Ensure parsed_intent is None so other nodes can handle this gracefully
            state["parsed_intent"] = None
            
        return state

    def _analyze_schema_node(self, state: QueryState) -> QueryState:
        """Analyze available schema and determine optimal query approach."""
        
        if not state.get("parsed_intent"):
            self._add_error_if_new(state, "No parsed intent available for schema analysis")
            return state
            
        intent = state["parsed_intent"]
        
        # Determine which tables and columns are relevant
        relevant_sources = intent["content_scope"]["primary_sources"]
        search_type = intent["search_strategy"]["search_type"]
        
        # Build schema context for SQL generation
        schema_context = {
            "unified_content_schema": {
                "table": "unified_content",
                "key_columns": self.schema_info["unified_content_columns"],
                "database_stats": [
                    db for db in self.schema_info["database_statistics"] 
                    if not relevant_sources or db["name"] in relevant_sources
                ]
            },
            "search_requirements": {
                "needs_content_tables": search_type in ["content_search", "hybrid"],
                "needs_property_tables": bool(intent["search_strategy"]["property_filters"]),
                "available_tables": list(self.schema_info["all_tables"].keys())
            }
        }
        
        state["available_schemas"] = schema_context
        print(f"✅ Schema analyzed: {len(schema_context['unified_content_schema']['database_stats'])} relevant databases")
        
        return state

    def _plan_execution_node(self, state: QueryState) -> QueryState:
        """Plan the execution strategy based on intent and schema."""
        
        if not all([state.get("parsed_intent"), state.get("available_schemas")]):
            self._add_error_if_new(state, "Missing intent or schema information for execution planning")
            return state
            
        intent = state["parsed_intent"]
        complexity = intent["complexity_level"]
        
        execution_plan = {
            "approach": "single_query" if complexity == "simple" else "multi_step",
            "time_handling": self._plan_time_constraints(intent.get("time_constraints")),
            "result_limiting": self._plan_result_limits(intent),
            "join_strategy": self._plan_joins(intent, state["available_schemas"])
        }
        
        state["execution_plan"] = execution_plan
        print(f"✅ Execution planned: {execution_plan['approach']} approach")
        
        return state

    def _generate_sql_node(self, state: QueryState) -> QueryState:
        """Generate SQL using AI reasoning with comprehensive SQLite context."""
        
        if not all([state.get("parsed_intent"), state.get("available_schemas"), state.get("execution_plan")]):
            self._add_error_if_new(state, "Missing information for SQL generation")
            return state
        
        # Build comprehensive SQLite-specific context
        sql_prompt = f"""You are generating a SQLite query. Follow these requirements strictly:

DATABASE TYPE: SQLite
AVAILABLE FUNCTIONS: {', '.join(self.schema_info['available_functions'])}
FORBIDDEN FUNCTIONS: {', '.join(self.schema_info['not_available'])} (DO NOT USE THESE)

UNIFIED_CONTENT TABLE SCHEMA:
{json.dumps(self.schema_info['unified_content_columns'], indent=2)}

AVAILABLE DATABASES:
{json.dumps(self.schema_info['database_statistics'], indent=2)}

DATABASE CONFIGURATION MAPPING:
{json.dumps(self.schema_info['database_config'], indent=2)}

SAMPLE DATA (for reference):
{json.dumps(self.schema_info['sample_data'], indent=2)}

USER REQUEST: {state['parsed_intent']['user_goal']}

CONTENT SCOPE: {json.dumps(state['parsed_intent']['content_scope'], indent=2)}

TIME CONSTRAINTS: {json.dumps(state['parsed_intent'].get('time_constraints'), indent=2)}

PREVIOUS ERRORS (if any): {state.get('errors', [])}

REFINEMENT CONTEXT (if retry): {state.get('refinement_context', '')}

CRITICAL REQUIREMENTS:
1. Use ONLY SQLite-compatible functions
2. NEVER use ARRAY_AGG, STRING_AGG, or similar PostgreSQL/MySQL functions
3. Use GROUP_CONCAT for string aggregation if needed
4. Use SUBSTR for string manipulation, not SUBSTRING
5. Use STRFTIME for date formatting
6. Query the unified_content table primarily
7. Handle date/time filtering carefully - created_time is stored as text
8. Return page_id, title, created_time, database_name at minimum
9. Use LIMIT to control result size
10. Group results logically
11. WORKSPACE FILTERING: When workspace is specified, ALWAYS include "AND workspace = 'workspace_name'" 
12. DATABASE NAMES: Use only the "nickname" values from DATABASE CONFIGURATION MAPPING as database_name (e.g., 'gmail' not 'trass.gmail')
13. WORKSPACE + DATABASE: For queries like "trass gmail", use "WHERE workspace = 'trass' AND database_name = 'gmail'"
14. CONTENT SEARCH: For text searches, search in BOTH title AND metadata using LIKE '%term%'
15. EMAIL CONTENT: For Gmail searches, most content is in metadata JSON, not title

Generate a working SQLite query. Return ONLY the SQL, no explanation or markdown."""

        try:
            sql_response = self.llm.invoke([
                SystemMessage(content="You are a SQLite expert. Generate only valid SQLite queries that will execute successfully."),
                HumanMessage(content=sql_prompt)
            ])
            
            generated_sql = sql_response.content.strip()
            
            # Clean up any markdown formatting more aggressively
            if "```" in generated_sql:
                # Extract SQL from markdown blocks
                import re
                sql_match = re.search(r'```(?:sql)?\s*(.*?)\s*```', generated_sql, re.DOTALL | re.IGNORECASE)
                if sql_match:
                    generated_sql = sql_match.group(1).strip()
                else:
                    # Remove all markdown formatting
                    generated_sql = generated_sql.replace("```sql", "").replace("```", "").strip()
            
            state["generated_sql"] = generated_sql
            print(f"✅ SQL generated: {len(generated_sql)} characters")
            
        except Exception as e:
            self._add_error_if_new(state, f"SQL generation failed: {str(e)}")
            print(f"❌ SQL generation error: {e}")
            
        return state

    def _execute_query_node(self, state: QueryState) -> QueryState:
        """Execute the generated SQL query."""
        
        if not state.get("generated_sql"):
            self._add_error_if_new(state, "No SQL to execute")
            return state
            
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                # Debug: Print the actual SQL being executed
                if os.getenv("MAIA_DEBUG") == "1":
                    print(f"🔍 Executing SQL: {state['generated_sql']}")
                
                cursor.execute(state["generated_sql"])
                
                results = []
                for row in cursor.fetchall():
                    results.append(dict(row))
                
                state["execution_results"] = results
                print(f"✅ Query executed: {len(results)} results")
                
        except Exception as e:
            self._add_error_if_new(state, f"SQL execution failed: {str(e)}")
            print(f"❌ SQL execution error: {e}")
            
        return state

    def _validate_results_node(self, state: QueryState) -> QueryState:
        """Validate results match the user's intent."""
        
        if not state.get("execution_results"):
            # Add error only if it's new
            self._add_error_if_new(state, "No results to validate")
            return state
            
        results = state["execution_results"]
        intent = state.get("parsed_intent", {})
        
        # Group results by database_name for expected format
        grouped_results = {}
        for item in results:
            db_name = item.get("database_name", "unknown")
            if db_name not in grouped_results:
                grouped_results[db_name] = []
            grouped_results[db_name].append(item)
        
        # Basic validation
        total_results = len(results)
        expected_sources = intent.get("content_scope", {}).get("primary_sources", [])
        
        validation_passed = True
        
        # Check if we got results from expected sources
        if expected_sources:
            found_sources = set(grouped_results.keys())
            expected_sources_set = set(expected_sources)
            if not found_sources.intersection(expected_sources_set):
                validation_passed = False
                self._add_error_if_new(state, f"No results from expected sources: {expected_sources}")
        
        # Check reasonable result count
        expected_count = intent.get("expected_result_count", "")
        if expected_count == "few" and total_results > 50:
            print(f"⚠️  Got {total_results} results when user expected 'few'")
        elif expected_count == "many" and total_results < 10:
            print(f"⚠️  Got {total_results} results when user expected 'many'")
        
        # Accept results even if validation had minor issues, unless there are truly no results
        if validation_passed or total_results > 0:
            state["final_results"] = grouped_results
            print(f"✅ Results validated: {total_results} results across {len(grouped_results)} databases")
        else:
            self._add_error_if_new(state, "No results found matching criteria")
            print(f"❌ Result validation failed - no results found")
            
        return state

    def _add_error_if_new(self, state: QueryState, error_msg: str):
        """Add error message only if it's not already present."""
        if not state.get("errors"):
            state["errors"] = []
        if error_msg not in state["errors"]:
            state["errors"].append(error_msg)
    
    def _refine_approach_node(self, state: QueryState) -> QueryState:
        """Refine the approach based on errors and retry with better context."""
        
        state["retry_count"] += 1
        
        if state["retry_count"] > 3:
            self._add_error_if_new(state, "Max retries exceeded")
            return state
        
        # Get the most recent unique error
        recent_errors = list(set(state["errors"][-5:]))  # Last 5 unique errors
        last_sql = state.get("generated_sql", "")
        
        # Create a targeted refinement based on error type
        refinement_context = f"""
RETRY ATTEMPT #{state['retry_count']}

ORIGINAL REQUEST: {state.get('parsed_intent', {}).get('user_goal', 'Unknown')}

RECENT ERRORS: {recent_errors}

FAILED SQL: {last_sql}

CRITICAL ISSUES TO FIX:
"""
        
        if any("ARRAY_AGG" in error for error in recent_errors):
            refinement_context += "\n- NEVER use ARRAY_AGG - use GROUP_CONCAT instead"
            
        if any("no such function" in error for error in recent_errors):
            refinement_context += f"\n- Only use these SQLite functions: {', '.join(self.schema_info['available_functions'])}"
            
        if any("no such table" in error for error in recent_errors):
            available_tables = list(self.schema_info.get('all_tables', {}).keys())
            refinement_context += f"\n- Only query these tables: {', '.join(available_tables)}"
            
        if any("syntax error" in error for error in recent_errors):
            refinement_context += "\n- Fix SQL syntax - check parentheses, quotes, commas"
            
        if len(recent_errors) == 0 or all("No results" in error for error in recent_errors):
            refinement_context += "\n- Broaden the search criteria - check date formats, database names, etc."
        
        try:
            print(f"🔄 Refining approach (attempt {state['retry_count']})")
            
            # Add the refinement context to the state for the next SQL generation
            state["refinement_context"] = refinement_context
            
            # Reset SQL to force regeneration with new context
            state["generated_sql"] = None
            
        except Exception as e:
            self._add_error_if_new(state, f"Refinement failed: {str(e)}")
            
        return state

    def _should_retry(self, state: QueryState) -> str:
        """Decide whether to retry or finish."""
        
        # If intent parsing failed completely, don't retry
        if not state.get("parsed_intent") and any("Intent parsing failed" in error for error in state.get("errors", [])):
            return "success"  # Stop processing
        
        # If we have final results, we're done
        if state.get("final_results"):
            return "success"
        
        # If we've hit max retries, stop
        if state["retry_count"] >= 3:
            return "success"  # Stop retrying
        
        # If the only error is "No results to validate" and we've tried at least once,
        # stop retrying to prevent infinite loops
        errors = state.get("errors", [])
        if errors and "No results to validate" in errors and state["retry_count"] > 0:
            return "success"  # Stop retrying on repeated "no results" errors
        
        # Otherwise, retry
        return "retry"

    # Helper methods for planning
    def _plan_time_constraints(self, time_constraints: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Plan how to handle time constraints."""
        if not time_constraints:
            return {"strategy": "no_time_filter"}
        
        constraint_type = time_constraints.get("constraint_type", "relative_period")
        
        if constraint_type == "multiple_periods":
            return {
                "strategy": "union_query",
                "periods": time_constraints.get("periods", []),
                "sampling": time_constraints.get("sampling_approach", "distributed")
            }
        else:
            return {
                "strategy": "single_period",
                "constraint": time_constraints
            }

    def _plan_result_limits(self, intent: Dict[str, Any]) -> Dict[str, Any]:
        """Plan result limiting strategy."""
        expected_count = intent.get("expected_result_count", "")
        
        limit_mapping = {
            "few": 20,
            "many": 200, 
            "comprehensive": 1000,
            "smattering": 15
        }
        
        # Handle time_constraints safely - it might be None
        time_constraints = intent.get("time_constraints") or {}
        periods = time_constraints.get("periods", [1])
        
        return {
            "global_limit": limit_mapping.get(expected_count, 100),
            "per_period_limit": limit_mapping.get(expected_count, 20) // max(1, len(periods))
        }

    def _plan_joins(self, intent: Dict[str, Any], schema: Dict[str, Any]) -> Dict[str, Any]:
        """Plan table joining strategy."""
        search_strategy = intent["search_strategy"]
        
        if search_strategy["search_type"] == "content_search":
            return {"strategy": "content_tables", "required": True}
        elif search_strategy["property_filters"]:
            return {"strategy": "property_tables", "required": True}
        else:
            return {"strategy": "unified_only", "required": False}