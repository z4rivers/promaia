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
                
                # Get detailed schema information for specialized content tables  
                specialized_schemas = {}
                
                # Find all tables that contain content (excluding system tables)
                content_tables = [name for name in tables if not name.startswith('sqlite_') 
                                 and name not in ['unified_content', 'content_registry']
                                 and ('content' in name or 'notion_' in name or 'gmail_' in name)]
                
                for table_name in content_tables:
                    if table_name in table_schemas:
                        # Get sample data to understand the structure
                        cursor.execute(f"SELECT * FROM {table_name} LIMIT 3")
                        sample_rows = cursor.fetchall()
                        
                        # Get column info for proper parsing
                        cursor.execute(f"PRAGMA table_info({table_name})")
                        column_info = cursor.fetchall()
                        column_names = [col[1] for col in column_info]
                        
                        # Parse sample data for schema understanding
                        sample_data = []
                        for row in sample_rows:
                            row_dict = {}
                            for i, col_name in enumerate(column_names):
                                if i < len(row):
                                    value = row[i]
                                    # Truncate long values for schema display
                                    if isinstance(value, str) and len(value) > 50:
                                        value = value[:50] + "..."
                                    row_dict[col_name] = value
                            sample_data.append(row_dict)
                        
                        specialized_schemas[table_name] = {
                            "columns": table_schemas[table_name]["columns"],
                            "sample_data": sample_data
                        }
                
                # Detect potential relationships automatically by looking for foreign key patterns
                relationship_info = {}
                for table_name, schema in specialized_schemas.items():
                    # Look for columns that might be foreign keys to unified_content
                    potential_fk_columns = []
                    for col in schema["columns"]:
                        col_name = col["name"].lower()
                        # Common patterns for foreign keys to page_id
                        if (col_name.endswith('_relation') or col_name.endswith('_id') or 
                            col_name.endswith('_reference') or col_name.endswith('_link')):
                            potential_fk_columns.append(col["name"])
                    
                    if potential_fk_columns:
                        # Test if these columns contain page_ids that exist in unified_content
                        for fk_col in potential_fk_columns:
                            try:
                                cursor.execute(f"""
                                    SELECT t.{fk_col}, uc.title, uc.database_name
                                    FROM {table_name} t
                                    LEFT JOIN unified_content uc ON t.{fk_col} = uc.page_id
                                    WHERE t.{fk_col} IS NOT NULL AND uc.page_id IS NOT NULL
                                    LIMIT 3
                                """)
                                test_relationships = cursor.fetchall()
                                if test_relationships:
                                    if table_name not in relationship_info:
                                        relationship_info[table_name] = {}
                                    
                                    # Determine the target database types from samples
                                    target_db_names = list(set(rel[2] for rel in test_relationships if rel[2]))
                                    
                                    relationship_info[table_name][fk_col] = {
                                        "description": f"{table_name}.{fk_col} links to unified_content.page_id",
                                        "target_databases": target_db_names,
                                        "sample_relationships": test_relationships,
                                        "query_pattern": f"JOIN unified_content related ON {table_name}.{fk_col} = related.page_id WHERE related.database_name IN ({', '.join([f'{db!r}' for db in target_db_names])})"
                                    }
                            except Exception:
                                # Ignore failed relationship tests
                                pass
                
                if relationship_info:
                    specialized_schemas['detected_relationships'] = relationship_info
                
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
                    "database_config": config_mapping,
                    "specialized_schemas": specialized_schemas
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

        # Enhanced database context with workspace awareness
        available_databases = [db['name'] for db in self.schema_info['database_statistics']]
        workspace_aware_databases = self._get_workspace_aware_databases(state.get('user_query', ''))

        system_prompt = f"""You are an expert at understanding user intent for database queries.

Available databases: {available_databases}
Current date: {datetime.now().strftime('%Y-%m-%d')}

WORKSPACE-AWARE DATABASE SELECTION:
When users mention "all [workspace] [type]" (e.g., "all trass gmail"), they typically want ALL databases of that type in that workspace.
For example:
- "all trass gmail" should include both "gmail" and "trass.gmail" if both exist
- "all koii journal" should include both "journal" and "koii.journal" if both exist

Do NOT limit to just workspace-specific databases unless the user is being very specific.

Parse this natural language query into structured intent. Pay special attention to:
1. Complex time expressions like "first week of march and first week of april"
2. Sampling strategies like "a smattering" or "some from each month"
3. Content vs metadata search requirements
4. Multiple time periods or date ranges
5. Complex AND queries that should be broken down into multiple sub-queries
6. When the user mentions multiple distinct criteria with "AND", mark as complex

IMPORTANT: If the user query contains multiple distinct search criteria joined by "AND"
(like searching for different company names AND different email patterns),
mark the complexity_level as "complex" to enable multi-step processing.

Examples of complex queries:
- "emails containing X AND emails from Y domain"
- "documents about A AND documents mentioning B person"
- "entries with term1 AND entries with term2 in different contexts"

IMPORTANT FOR RESULT COUNT EXPECTATIONS:
- If user says "all [type]" (e.g., "all gmail", "all emails"), set expected_result_count to "all"
- If user wants comprehensive results, use "comprehensive"
- If user wants just a few examples, use "few"

User query: {state['user_query']}

Return structured JSON matching the QueryIntent schema."""
        
        try:
            # Use LLM with structured output
            intent_response = self.llm.with_structured_output(QueryIntent).invoke([
                SystemMessage(content=system_prompt),
                HumanMessage(content=state['user_query'])
            ])

            # Post-process the intent to handle workspace-aware database selection
            processed_intent = self._post_process_intent(intent_response.dict(), state.get('user_query', ''))

            state["parsed_intent"] = processed_intent
            print(f"✅ Intent parsed: {intent_response.user_goal}")

        except Exception as e:
            self._add_error_if_new(state, f"Intent parsing failed: {str(e)}")
            print(f"❌ Intent parsing error: {e}")
            # Ensure parsed_intent is None so other nodes can handle this gracefully
            state["parsed_intent"] = None

        return state

    def _get_workspace_aware_databases(self, user_query: str) -> List[str]:
        """Get databases with workspace awareness for better AI understanding."""
        # This method helps provide context but the actual logic is in _post_process_intent
        return [db['name'] for db in self.schema_info['database_statistics']]

    def _post_process_intent(self, intent: Dict[str, Any], user_query: str) -> Dict[str, Any]:
        """Post-process the AI-generated intent to handle workspace-aware database selection."""

        query_lower = user_query.lower()
        expanded_sources = []

        # Handle complex queries with multiple sources or "ALSO" clauses
        # Split the query on "ALSO" and process each part separately
        query_parts = [part.strip() for part in query_lower.split(" also ")]
        if len(query_parts) <= 1:
            # Also try splitting on comma + "also" pattern
            query_parts = [part.strip() for part in query_lower.split(", also ")]

        if len(query_parts) <= 1:
            # Fall back to single part processing
            query_parts = [query_lower]

        # Process each part to find workspace and content type combinations
        for part in query_parts:
            # Check if this part mentions specific database types
            workspace = None
            content_types = []

            # Look for workspace names in this part
            for db_stat in self.schema_info['database_statistics']:
                db_name = db_stat['name']
                if '.' in db_name:
                    potential_workspace = db_name.split('.')[0]
                    if potential_workspace in part:
                        workspace = potential_workspace
                        break

            # If no workspace found in qualified names, look for standalone workspace names
            if not workspace:
                for db_stat in self.schema_info['database_statistics']:
                    db_name = db_stat['name']
                    if '.' in db_name:
                        potential_workspace = db_name.split('.')[0]
                        if potential_workspace in part and potential_workspace not in ['gmail', 'email', 'journal', 'stories', 'cms']:
                            workspace = potential_workspace
                            break

            # Look for all content types mentioned in this part
            content_keywords = {
                'gmail': ['gmail', 'email', 'emails'],
                'journal': ['journal'],
                'stories': ['stories', 'story', 'notion'],
                'cms': ['cms', 'content']
            }

            for db_type, keywords in content_keywords.items():
                if any(keyword in part for keyword in keywords):
                    content_types.append(db_type)

            # If we found workspace and content types, expand sources for this part
            if workspace and content_types:
                for content_type in content_types:
                    # Add both workspace-specific and general databases
                    for db_stat in self.schema_info['database_statistics']:
                        db_name = db_stat['name']

                        # Add the general database (e.g., "gmail")
                        if db_name == content_type:
                            if db_name not in expanded_sources:
                                expanded_sources.append(db_name)

                        # Add workspace-specific database (e.g., "trass.gmail", "trass.stories")
                        if db_name == f"{workspace}.{content_type}":
                            if db_name not in expanded_sources:
                                expanded_sources.append(db_name)

        # If no expansion was done but we have "all" queries, try the original logic
        if not expanded_sources and ("all" in query_lower and
            any(word in query_lower for word in ["gmail", "email", "journal", "stories", "cms"])):

            # Extract workspace and content type from the query
            workspace = None
            content_type = None

            # Look for workspace names
            for db_stat in self.schema_info['database_statistics']:
                db_name = db_stat['name']
                if '.' in db_name:
                    potential_workspace = db_name.split('.')[0]
                    if potential_workspace in query_lower:
                        workspace = potential_workspace
                        break

            # Look for content types
            content_keywords = {
                'gmail': ['gmail', 'email', 'emails'],
                'journal': ['journal'],
                'stories': ['stories', 'story'],
                'cms': ['cms', 'content']
            }

            for db_type, keywords in content_keywords.items():
                if any(keyword in query_lower for keyword in keywords):
                    content_type = db_type
                    break

            # If we found both workspace and content type, expand the primary sources
            if workspace and content_type:
                # Add both workspace-specific and general databases
                for db_stat in self.schema_info['database_statistics']:
                    db_name = db_stat['name']

                    # Add the general database (e.g., "gmail")
                    if db_name == content_type:
                        expanded_sources.append(db_name)

                    # Add workspace-specific database (e.g., "trass.gmail")
                    if db_name == f"{workspace}.{content_type}":
                        expanded_sources.append(db_name)

        # Update the intent with expanded sources if we found any
        if expanded_sources:
            # Remove duplicates
            expanded_sources = list(set(expanded_sources))

            # Update the intent's primary sources
            current_sources = intent['content_scope']['primary_sources']
            # Merge with existing sources, preferring the expanded ones
            final_sources = expanded_sources + [s for s in current_sources if s not in expanded_sources]
            intent['content_scope']['primary_sources'] = final_sources

            print(f"📊 Expanded database selection for '{user_query}': {final_sources}")

        return intent

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
        user_goal = intent.get("user_goal", "")
        user_query = state.get("user_query", "")
        
        # Check for complex AND queries that should be broken down
        should_use_multi_step = (
            complexity == "complex" and 
            (" AND " in user_query.upper() or " and " in user_query) and
            self._has_distinct_search_criteria(user_query)
        )
        
        execution_plan = {
            "approach": "multi_step" if should_use_multi_step else "single_query",
            "time_handling": self._plan_time_constraints(intent.get("time_constraints")),
            "result_limiting": self._plan_result_limits(intent, state),
            "join_strategy": self._plan_joins(intent, state["available_schemas"]),
            "multi_step_queries": self._plan_multi_step_queries(user_query) if should_use_multi_step else None
        }
        
        state["execution_plan"] = execution_plan
        print(f"✅ Execution planned: {execution_plan['approach']} approach")
        
        if should_use_multi_step:
            print(f"   Will execute {len(execution_plan['multi_step_queries'])} separate queries")
        
        return state

    def _generate_schema_documentation(self) -> str:
        """Generate dynamic schema documentation based on user's actual database structure."""
        
        doc_sections = []
        
        # 1. Main unified_content table
        doc_sections.append("=== MAIN TABLE: unified_content ===")
        doc_sections.append("This is your primary table containing all content across databases.")
        doc_sections.append("COLUMNS:")
        for col in self.schema_info['unified_content_columns']:
            doc_sections.append(f"  {col['name']} ({col['type']}) - Primary content field")
        
        # 2. Available databases (user's specific setup)
        doc_sections.append("\n=== USER'S DATABASES ===")
        for db_stat in self.schema_info['database_statistics']:
            doc_sections.append(f"Database: {db_stat['name']}")
            doc_sections.append(f"  Count: {db_stat['count']} entries")
            doc_sections.append(f"  Content types: {', '.join(db_stat['content_types'])}")
            if db_stat['earliest']:
                doc_sections.append(f"  Date range: {db_stat['earliest']} to {db_stat['latest']}")
            doc_sections.append("")
        
        # 3. Specialized tables (user's specific content tables)
        specialized_schemas = self.schema_info.get('specialized_schemas', {})
        if specialized_schemas:
            doc_sections.append("=== SPECIALIZED CONTENT TABLES ===")
            doc_sections.append("These tables contain detailed properties for specific content types:")
            
            for table_name, schema in specialized_schemas.items():
                if table_name == 'detected_relationships':
                    continue
                    
                doc_sections.append(f"\nTable: {table_name}")
                doc_sections.append("Columns:")
                for col in schema.get('columns', []):
                    doc_sections.append(f"  {col['name']} ({col['type']})")
                
                # Add sample data to show structure
                if schema.get('sample_data'):
                    doc_sections.append("Sample data:")
                    for i, sample in enumerate(schema['sample_data'][:1]):  # Just one sample
                        doc_sections.append(f"  Row {i+1}: {sample}")
        
        # 4. Relationships (user's specific relationships)
        relationships = specialized_schemas.get('detected_relationships', {})
        if relationships:
            doc_sections.append("\n=== DETECTED RELATIONSHIPS ===")
            doc_sections.append("Foreign key relationships in your database:")
            
            for table_name, table_relationships in relationships.items():
                doc_sections.append(f"\n{table_name}:")
                for fk_col, rel_info in table_relationships.items():
                    doc_sections.append(f"  {fk_col} -> {rel_info['description']}")
                    doc_sections.append(f"  Links to: {', '.join(rel_info['target_databases'])}")
                    doc_sections.append(f"  Query pattern: {rel_info['query_pattern']}")
        
        # 5. Sample queries based on user's actual data
        doc_sections.append("\n=== SQL PATTERNS FOR YOUR DATABASE ===")
        
        # Basic search patterns
        if self.schema_info['database_statistics']:
            sample_db = self.schema_info['database_statistics'][0]['name']
            doc_sections.append(f"Basic content search:")
            doc_sections.append(f"  SELECT page_id, title, created_time, database_name FROM unified_content")
            doc_sections.append(f"  WHERE workspace = 'workspace_name' AND database_name = '{sample_db}'")
            doc_sections.append(f"  AND (title LIKE '%term%' OR metadata LIKE '%term%') LIMIT 100")
        
        # Relationship query patterns
        for table_name, table_relationships in relationships.items():
            for fk_col, rel_info in table_relationships.items():
                doc_sections.append(f"\nRelationship query for {table_name}:")
                doc_sections.append(f"  SELECT uc.page_id, uc.title, related.title as related_name")
                doc_sections.append(f"  FROM unified_content uc")
                doc_sections.append(f"  JOIN {table_name} st ON uc.page_id = st.page_id")
                doc_sections.append(f"  JOIN unified_content related ON st.{fk_col} = related.page_id")
                doc_sections.append(f"  WHERE uc.database_name = '{table_name.replace('notion_', '').replace('_content', '')}'")
                doc_sections.append(f"  AND related.database_name IN ({', '.join([f'{db!r}' for db in rel_info['target_databases']])})")
                break  # Just show one example per table
        
        return "\n".join(doc_sections)

    def _generate_sql_node(self, state: QueryState) -> QueryState:
        """Generate SQL using AI reasoning with comprehensive SQLite context."""
        
        if not all([state.get("parsed_intent"), state.get("available_schemas"), state.get("execution_plan")]):
            self._add_error_if_new(state, "Missing information for SQL generation")
            return state
        
        # Generate dynamic schema documentation based on user's actual database
        schema_documentation = self._generate_schema_documentation()
        
        # Build comprehensive SQLite-specific context
        sql_prompt = f"""You are generating a SQLite query. Follow these requirements strictly:

DATABASE TYPE: SQLite
AVAILABLE FUNCTIONS: {', '.join(self.schema_info['available_functions'])}
FORBIDDEN FUNCTIONS: {', '.join(self.schema_info['not_available'])} (DO NOT USE THESE)

{schema_documentation}


USER REQUEST: {state['parsed_intent']['user_goal']}

CONTENT SCOPE: {json.dumps(state['parsed_intent']['content_scope'], indent=2)}

TIME CONSTRAINTS: {json.dumps(state['parsed_intent'].get('time_constraints'), indent=2)}

PREVIOUS ERRORS (if any): {state.get('errors', [])}

REFINEMENT CONTEXT (if retry): {state.get('refinement_context', '')}

EXECUTION PLAN (includes result limits): {json.dumps(state.get('execution_plan', {}), indent=2)}

CRITICAL REQUIREMENTS:
1. Use ONLY SQLite-compatible functions from the AVAILABLE FUNCTIONS list
2. NEVER use functions listed in FORBIDDEN FUNCTIONS
3. Use GROUP_CONCAT for string aggregation, not ARRAY_AGG
4. Use SUBSTR for string manipulation, not SUBSTRING
5. Use STRFTIME for date formatting
6. Follow the SQL patterns shown in the schema documentation above
7. Return page_id, title, created_time, database_name at minimum
8. Use the limit from execution plan: {state['execution_plan']['result_limiting']['global_limit']}
9. WORKSPACE FILTERING: Always include "AND workspace = 'workspace_name'" when workspace is specified
10. DATABASE SELECTION: If CONTENT SCOPE lists multiple primary_sources, use "database_name IN (list)" not just one database
11. For content search, use: (title LIKE '%term%' OR metadata LIKE '%term%')
12. For OR searches, combine conditions: (term1_conditions OR term2_conditions)
13. For relationship queries, use the patterns shown in DETECTED RELATIONSHIPS section above
14. IMPORTANT: Check CONTENT SCOPE primary_sources - if multiple databases are listed, query ALL of them using IN clause
15. TIME CONSTRAINTS: If TIME CONSTRAINTS are provided, you MUST apply date filtering using the unified_content table's last_edited_time column (which is in ISO format and works with SQLite DATE() function). Use the start_date and end_date from the periods array. Format: AND DATE(uc.last_edited_time) BETWEEN 'start_date' AND 'end_date'

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
        """Execute the generated SQL query or multiple queries for multi-step approach."""
        
        execution_plan = state.get("execution_plan", {})
        
        # Handle multi-step execution
        if execution_plan.get("approach") == "multi_step" and execution_plan.get("multi_step_queries"):
            return self._execute_multi_step_queries(state)
        
        # Handle single query execution
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

    def _plan_result_limits(self, intent: Dict[str, Any], state: QueryState = None) -> Dict[str, Any]:
        """Plan result limiting strategy."""
        expected_count = intent.get("expected_result_count", "")
        complexity = intent.get("complexity_level", "moderate")
        user_query = state.get("user_query", "") if state else ""
        
        limit_mapping = {
            "few": 20,
            "many": 200, 
            "comprehensive": 2000,  # Increased from 1000
            "all": 5000,  # New category for "all" queries
            "smattering": 15
        }
        
        # For complex queries or when no specific count is mentioned, use higher limits
        if expected_count == "":
            if complexity == "complex":
                default_limit = 300  # Higher limit for complex queries
            elif complexity == "moderate":
                default_limit = 200
            else:
                default_limit = 100
        else:
            default_limit = 100
        
        # Handle time_constraints safely - it might be None
        time_constraints = intent.get("time_constraints") or {}
        periods = time_constraints.get("periods", [1])
        
        global_limit = limit_mapping.get(expected_count, default_limit)
        
        # For queries with "AND" conditions that might need to combine results,
        # increase the limit to ensure we get enough results
        user_goal = intent.get("user_goal", "")
        
        if " AND " in user_goal.upper() or " and " in user_goal:
            global_limit = min(global_limit * 2, 1000)  # Double the limit but cap at 1000
            
        # Check if user explicitly asks for "all" results
        if ("all" in user_query.lower() and 
            any(word in user_query.lower() for word in ["gmail", "emails", "messages", "entries"])):
            global_limit = 5000  # Use very high limit for explicit "all" requests
        
        return {
            "global_limit": global_limit,
            "per_period_limit": limit_mapping.get(expected_count, 50) // max(1, len(periods))
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

    def _has_distinct_search_criteria(self, user_query: str) -> bool:
        """Check if the query has distinct search criteria that warrant multi-step processing."""
        # Split on AND and see if we have different types of criteria
        and_parts = [part.strip() for part in user_query.split(" AND ")]
        if len(and_parts) <= 1:
            and_parts = [part.strip() for part in user_query.split(" and ")]
        
        if len(and_parts) <= 1:
            return False
        
        # Look for different types of search patterns
        patterns = {
            'email_domain': any(word in part.lower() for part in and_parts for word in ['@', 'email', 'domain', 'address']),
            'company_names': any(word in part.lower() for part in and_parts for word in ['"', 'company', 'term']),
            'person_names': any(word in part.lower() for part in and_parts for word in ['andrew', 'person', 'from', 'to']),
            'content_search': any(word in part.lower() for part in and_parts for word in ['contain', 'about', 'mention'])
        }
        
        # If we have multiple different types of criteria, use multi-step
        return sum(patterns.values()) >= 2

    def _plan_multi_step_queries(self, user_query: str) -> List[str]:
        """Break down a complex query into multiple simpler queries based on ALSO clauses."""
        # Split on ALSO patterns (case insensitive)
        query_lower = user_query.lower()

        # Check for "ALSO" patterns first
        also_patterns = [" also ", ", also "]
        parts = [user_query]

        for pattern in also_patterns:
            if pattern in query_lower:
                parts = [part.strip() for part in query_lower.split(pattern)]
                # Reconstruct with original casing but split parts
                temp_parts = []
                remaining = user_query
                for i, part in enumerate(parts):
                    if i < len(parts) - 1:
                        split_pos = remaining.lower().find(pattern)
                        temp_parts.append(remaining[:split_pos].strip())
                        remaining = remaining[split_pos + len(pattern):].strip()
                    else:
                        temp_parts.append(remaining.strip())
                parts = temp_parts
                break

        # If no ALSO patterns found, try AND patterns
        if len(parts) == 1:
            if " AND " in user_query:
                parts = [part.strip() for part in user_query.split(" AND ")]
            elif " and " in user_query:
                parts = [part.strip() for part in user_query.split(" and ")]

        # If still no split, return original query
        if len(parts) == 1:
            return [user_query]

        # Clean up each part to be a standalone query
        queries = []
        for part in parts:
            # Skip empty parts
            if not part.strip():
                continue

            # For parts that mention specific database types, keep them as-is
            part_lower = part.lower()
            has_specific_db = any(keyword in part_lower for keyword in [
                'gmail', 'email', 'journal', 'stories', 'story', 'notion', 'cms'
            ])

            if has_specific_db:
                queries.append(part)
            else:
                # For generic parts, assume they apply to the primary context
                # Look at the previous part to determine context
                if queries and any(keyword in queries[-1].lower() for keyword in ['gmail', 'email']):
                    # Previous part was about gmail, so this might be too
                    queries.append(f"gmail {part}")
                else:
                    queries.append(part)

        return queries

    def _execute_multi_step_queries(self, state: QueryState) -> QueryState:
        """Execute multiple queries for complex AND conditions and combine results."""
        execution_plan = state.get("execution_plan", {})
        multi_step_queries = execution_plan.get("multi_step_queries", [])
        
        if not multi_step_queries:
            self._add_error_if_new(state, "No multi-step queries to execute")
            return state
        
        print(f"🔄 Executing {len(multi_step_queries)} separate queries for complex AND condition")
        
        all_results = []
        
        try:
            # Process each sub-query separately
            for i, sub_query in enumerate(multi_step_queries):
                print(f"   Step {i+1}: {sub_query}")
                
                # Create a temporary sub-state for this query
                sub_state = {
                    "user_query": sub_query,
                    "parsed_intent": None,
                    "available_schemas": state.get("available_schemas"),
                    "execution_plan": {"approach": "single_query"},  # Force single query for sub-steps
                    "generated_sql": None,
                    "execution_results": None,
                    "errors": [],
                    "retry_count": 0
                }
                
                # Parse intent for this sub-query
                sub_state = self._parse_intent_for_substep(sub_state)
                
                # Generate SQL for this sub-query
                if sub_state.get("parsed_intent"):
                    sub_state = self._generate_sql_for_substep(sub_state)
                
                # Execute this sub-query
                if sub_state.get("generated_sql"):
                    sub_state = self._execute_single_query(sub_state)
                    
                    if sub_state.get("execution_results"):
                        all_results.extend(sub_state["execution_results"])
                        print(f"      Got {len(sub_state['execution_results'])} results")
                    else:
                        print(f"      No results from sub-query {i+1}")
                else:
                    print(f"      Failed to generate SQL for sub-query {i+1}")
            
            # Remove duplicates based on page_id
            seen_page_ids = set()
            unique_results = []
            for result in all_results:
                page_id = result.get('page_id')
                if page_id not in seen_page_ids:
                    seen_page_ids.add(page_id)
                    unique_results.append(result)
            
            state["execution_results"] = unique_results
            print(f"✅ Multi-step execution completed: {len(unique_results)} unique results ({len(all_results)} total)")
            
        except Exception as e:
            self._add_error_if_new(state, f"Multi-step execution failed: {str(e)}")
            print(f"❌ Multi-step execution error: {e}")
            
        return state

    def _parse_intent_for_substep(self, sub_state: Dict) -> Dict:
        """Parse intent for a single sub-query with intelligent database detection."""
        try:
            user_query = sub_state["user_query"]
            query_lower = user_query.lower()

            # Detect which database types this sub-query should target
            primary_sources = []
            content_types = []

            # Check for explicit database mentions
            if any(keyword in query_lower for keyword in ['gmail', 'email', 'emails']):
                primary_sources.extend(['gmail', 'trass.gmail'])
                content_types.append('email')
            if any(keyword in query_lower for keyword in ['stories', 'story', 'notion']):
                primary_sources.extend(['stories', 'trass.stories'])
                content_types.append('story')
            if any(keyword in query_lower for keyword in ['journal']):
                primary_sources.extend(['journal', 'trass.journal'])
                content_types.append('journal')
            if any(keyword in query_lower for keyword in ['cms', 'content']):
                primary_sources.extend(['cms', 'trass.cms'])
                content_types.append('cms')

            # If no specific databases detected, default to gmail (for backward compatibility)
            if not primary_sources:
                primary_sources = ['gmail', 'trass.gmail']
                content_types = ['email']

            # Extract workspace from query if mentioned
            workspace_filter = None
            for db_stat in self.schema_info['database_statistics']:
                db_name = db_stat['name']
                if '.' in db_name:
                    potential_workspace = db_name.split('.')[0]
                    if potential_workspace in query_lower:
                        workspace_filter = potential_workspace
                        break

            # Create intent structure for the sub-query
            sub_intent = {
                "user_goal": f"Find content: {user_query}",
                "content_scope": {
                    "primary_sources": list(set(primary_sources)),  # Remove duplicates
                    "content_types": list(set(content_types)),  # Remove duplicates
                    "workspace_filter": workspace_filter
                },
                "search_strategy": {
                    "search_type": "content_search",
                    "search_terms": self._extract_search_terms(user_query),
                    "property_filters": {},
                    "person_filters": []
                },
                "complexity_level": "simple",
                "expected_result_count": ""
            }

            sub_state["parsed_intent"] = sub_intent

        except Exception as e:
            print(f"⚠️  Sub-query intent parsing error: {e}")

        return sub_state

    def _extract_search_terms(self, query: str) -> List[str]:
        """Extract search terms from a query string."""
        import re
        
        # Extract quoted terms first - these are the most important
        quoted_terms = re.findall(r'"([^"]*)"', query)
        
        # For Gmail searches, focus on specific entities and avoid generic words
        stop_words = {
            'the', 'and', 'that', 'contain', 'from', 'trass', 'gmail', 'all', 'email', 'address',
            'databases', 'following', 'terms', 'either', 'content', 'term', 'contains'
        }
        
        # Extract other significant words but be more selective
        words = query.replace('"', '').replace(',', '').split()
        significant_words = []
        
        for word in words:
            word_clean = word.strip('():[]').lower()
            # Only include words that look like company names, person names, or specific terms
            if (len(word_clean) > 3 and 
                word_clean not in stop_words and
                not word_clean.startswith('[') and
                not word_clean.endswith(':') and
                word_clean not in ['gmail', 'email']):
                
                # Prefer capitalized words (likely proper nouns) or known entities
                if (word[0].isupper() or 
                    word_clean in ['andrew', 'shipbob', 'expandly', 'avask', 'canusa']):
                    significant_words.append(word_clean)
        
        # Combine and deduplicate
        all_terms = []
        for term in quoted_terms + significant_words:
            if term and term.lower() not in [t.lower() for t in all_terms]:
                all_terms.append(term)
        
        return all_terms

    def _generate_sql_for_substep(self, sub_state: Dict) -> Dict:
        """Generate SQL for a single sub-query step."""
        try:
            intent = sub_state["parsed_intent"]
            search_terms = intent["search_strategy"]["search_terms"]
            
            # Build a targeted SQL query for this sub-step
            base_conditions = ["workspace = 'trass'", "database_name = 'gmail'"]
            
            # Add search conditions - use OR for terms within the same sub-query
            if search_terms:
                search_conditions = []
                for term in search_terms:
                    search_conditions.append(f"(title LIKE '%{term}%' OR metadata LIKE '%{term}%')")
                
                # Combine search conditions with OR
                search_clause = " OR ".join(search_conditions)
                all_conditions = base_conditions + [f"({search_clause})"]
            else:
                all_conditions = base_conditions
            
            where_clause = " AND ".join(all_conditions)
            
            sql = f"""
                SELECT DISTINCT page_id, title, created_time, database_name, workspace, metadata
                FROM unified_content 
                WHERE {where_clause}
                ORDER BY created_time DESC
                LIMIT 150
            """
            
            sub_state["generated_sql"] = sql.strip()
            
            # Debug: Print the generated SQL
            if os.getenv("MAIA_DEBUG") == "1":
                print(f"      Generated SQL: {sql.strip()}")
                print(f"      Search terms: {search_terms}")
            
        except Exception as e:
            print(f"⚠️  Sub-query SQL generation error: {e}")
            
        return sub_state

    def _execute_single_query(self, sub_state: Dict) -> Dict:
        """Execute a single SQL query."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                cursor.execute(sub_state["generated_sql"])
                
                results = []
                for row in cursor.fetchall():
                    results.append(dict(row))
                
                sub_state["execution_results"] = results
                
        except Exception as e:
            print(f"⚠️  Sub-query execution error: {e}")
            sub_state["execution_results"] = []
            
        return sub_state