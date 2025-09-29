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
                
                # Load workspace-database mapping from config
                workspace_mapping = self._load_workspace_mapping()
                
                return {
                    "databases": databases,
                    "main_table": "unified_content", 
                    "key_columns": ["page_id", "title", "database_name", "created_time", "last_edited_time", "metadata"],
                    "query_templates": query_templates,
                    "workspace_mapping": workspace_mapping,
                    "date_info": "Dates are in YYYY-MM-DD format. Use created_time or last_edited_time for date filtering."
                }
        except Exception as e:
            print(f"⚠️ Schema loading failed: {e}")
            return {"databases": [], "main_table": "unified_content", "key_columns": [], "query_templates": [], "workspace_mapping": {}}

    def _load_workspace_mapping(self) -> Dict[str, Any]:
        """Load workspace-database mapping from promaia.config.json"""
        try:
            import json
            import os
            
            config_path = os.path.join(os.path.dirname(self.db_path), '../promaia.config.json')
            config_path = os.path.normpath(config_path)
            
            if not os.path.exists(config_path):
                return {"workspaces": {}, "databases": {}, "naming_convention": "workspace.database or database (for default workspace)"}
            
            with open(config_path, 'r') as f:
                config = json.load(f)
            
            workspace_info = {
                "workspaces": {},
                "databases": {},
                "naming_convention": "Format: 'workspace.database' (e.g. 'trass.journal') OR just 'database' for default workspace (e.g. 'journal' for koii workspace)",
                "default_workspace": config.get("default_workspace", "koii")
            }
            
            # Extract workspace info
            if "workspaces" in config:
                for ws_name, ws_data in config["workspaces"].items():
                    if ws_data.get("enabled", True):
                        workspace_info["workspaces"][ws_name] = {
                            "description": ws_data.get("description", ""),
                            "enabled": ws_data.get("enabled", True)
                        }
            
            # Extract database info with workspace mapping
            if "databases" in config:
                for db_key, db_data in config["databases"].items():
                    workspace = db_data.get("workspace", "koii")
                    nickname = db_data.get("nickname", db_key.split('.')[-1])
                    source_type = db_data.get("source_type", "unknown")
                    
                    workspace_info["databases"][db_key] = {
                        "nickname": nickname,
                        "workspace": workspace, 
                        "source_type": source_type,
                        "description": db_data.get("description", ""),
                        "enabled": db_data.get("sync_enabled", True)
                    }
            
            return workspace_info
            
        except Exception as e:
            print(f"⚠️ Config loading failed: {e}")
            return {"workspaces": {}, "databases": {}, "naming_convention": "workspace.database or database (for default workspace)"}

    def _generate_query_examples(self, cursor) -> List[Dict[str, Any]]:
        """Generate REAL query examples based on actual user query patterns from chat history."""
        examples = []
        
        # Check what databases actually exist in the user's system
        cursor.execute("SELECT DISTINCT database_name FROM unified_content LIMIT 20")
        available_dbs = [row[0] for row in cursor.fetchall()]
        
        # GMAIL QUERIES - Based on real user patterns with workspace.database naming
        gmail_dbs = [db for db in available_dbs if 'gmail' in db.lower()]
        if gmail_dbs:
            trass_gmail_dbs = [f"'{db}'" for db in gmail_dbs if 'trass' in db.lower()]
            gmail_db_list = ', '.join(trass_gmail_dbs) if trass_gmail_dbs else "('gmail')"
            all_gmail_dbs = ', '.join([f"'{db}'" for db in gmail_dbs])
            examples.extend([
                {
                    "query_type": "Gmail - Business partner search with workspace qualifier",
                    "user_query": "all trass gmail entries that include the term mgm",
                    "sql_pattern": f"SELECT u.page_id, g.subject as title, u.database_name, g.email_date as created_time, u.metadata FROM unified_content u JOIN gmail_content g ON u.page_id = SUBSTR(g.page_id, 5) WHERE u.database_name IN ({gmail_db_list}) AND (g.subject LIKE '%mgm%' OR g.message_content LIKE '%mgm%' OR g.sender_email LIKE '%mgm%' OR g.sender_name LIKE '%mgm%') LIMIT 1000",
                    "notes": "Gmail: JOIN unified_content with gmail_content to search actual email content (subject, message_content, sender info). Search across all relevant Gmail fields for comprehensive results."
                },
                {
                    "query_type": "Gmail - Content search with date filtering",
                    "user_query": "emails with the term mgm from the last 3 months",
                    "sql_pattern": f"SELECT u.page_id, g.subject as title, u.database_name, g.email_date as created_time, u.metadata FROM unified_content u JOIN gmail_content g ON u.page_id = SUBSTR(g.page_id, 5) WHERE u.database_name IN ({gmail_db_list}) AND (g.subject LIKE '%mgm%' OR g.message_content LIKE '%mgm%' OR g.sender_email LIKE '%mgm%' OR g.sender_name LIKE '%mgm%') AND g.email_date >= DATE('now', '-90 days') LIMIT 1000",
                    "notes": "Gmail: JOIN with gmail_content for full text search, use email_date for accurate date filtering. Search subject, content, and sender fields."
                },
                {
                    "query_type": "Gmail - General content search (no workspace qualifier)",
                    "user_query": "emails about mgm",
                    "sql_pattern": f"SELECT u.page_id, g.subject as title, u.database_name, g.email_date as created_time, u.metadata FROM unified_content u JOIN gmail_content g ON u.page_id = SUBSTR(g.page_id, 5) WHERE u.database_name IN ({all_gmail_dbs}) AND (g.subject LIKE '%mgm%' OR g.message_content LIKE '%mgm%' OR g.sender_email LIKE '%mgm%' OR g.sender_name LIKE '%mgm%') LIMIT 1000",
                    "notes": "Gmail: When no workspace specified, search ALL Gmail databases. JOIN with gmail_content for comprehensive email content search."
                }
            ])
        
        # JOURNAL QUERIES - Based on real user patterns with workspace.database naming
        journal_dbs = [db for db in available_dbs if 'journal' in db.lower()]
        if journal_dbs:
            all_journal_dbs = ', '.join([f"'{db}'" for db in journal_dbs])
            # koii workspace: use 'journal' database (no prefix)
            koii_journal_dbs = ', '.join([f"'{db}'" for db in journal_dbs if not '.' in db])  # 'journal'
            # trass workspace: use 'trass.journal' database 
            trass_journal_dbs = ', '.join([f"'{db}'" for db in journal_dbs if 'trass' in db.lower()])  # 'trass.journal'
            
            examples.extend([
                {
                    "query_type": "Journal - Natural date range with formal phrasing",
                    "user_query": "find all the journal entries between february 2025 and may 2025",
                    "sql_pattern": f"SELECT page_id, title, database_name, created_time, metadata FROM unified_content WHERE database_name IN ({all_journal_dbs}) AND DATE(created_time) BETWEEN '2025-02-01' AND '2025-05-31' LIMIT 10000",
                    "notes": "Journal: User uses natural date formats ('february 2025 and may 2025'), formal tone ('find all the'), expects comprehensive results from all journal databases."
                },
                {
                    "query_type": "Journal - Person/content search with 'relate to' phrasing",
                    "user_query": "find all the journal entries that relate to graham",
                    "sql_pattern": f"SELECT page_id, title, database_name, created_time, metadata FROM unified_content WHERE database_name IN ({all_journal_dbs}) AND (title LIKE '%graham%' OR metadata LIKE '%graham%') LIMIT 1000",
                    "notes": "Journal: User searches for real people ('graham'), uses 'relate to' instead of 'about', formal 'find all the' phrasing."
                },
                {
                    "query_type": "Journal - Workspace-specific query (koii workspace)",
                    "user_query": "last 3 weeks of koii journal entries",
                    "sql_pattern": f"SELECT page_id, title, database_name, created_time, metadata FROM unified_content WHERE database_name IN ({koii_journal_dbs}) AND DATE(created_time) >= DATE('now', '-21 days') LIMIT 1000",
                    "notes": "Journal: 'koii journal entries' maps to 'journal' database (koii workspace default). User uses casual time phrases."
                },
                {
                    "query_type": "Journal - Workspace qualifier with 'from the last' pattern",
                    "user_query": "koii journal entries from the last 7 days",
                    "sql_pattern": f"SELECT page_id, title, database_name, created_time, metadata FROM unified_content WHERE database_name IN ({koii_journal_dbs}) AND DATE(created_time) >= DATE('now', '-7 days') LIMIT 1000",
                    "notes": "Journal: 'koii journal entries' maps to 'journal' database only, NOT 'trass.journal'. Common pattern 'from the last X days'."
                },
                {
                    "query_type": "Journal - Dot notation workspace format (CRITICAL EXCLUSION EXAMPLE)",
                    "user_query": "koii.journals",
                    "sql_pattern": f"SELECT page_id, title, database_name, created_time, metadata FROM unified_content WHERE database_name IN ({koii_journal_dbs}) LIMIT 1000",
                    "notes": "Journal: 'koii.journals' maps to 'journal' database ONLY. CRITICAL: Do NOT include 'trass.journal' - user specified koii workspace, exclude trass workspace entirely."
                },
                {
                    "query_type": "Journal - Cross-workspace simplified phrasing (trass workspace)", 
                    "user_query": "last 1 week of trass journals",
                    "sql_pattern": f"SELECT page_id, title, database_name, created_time, metadata FROM unified_content WHERE database_name IN ({trass_journal_dbs}) AND DATE(created_time) >= DATE('now', '-7 days') LIMIT 1000",
                    "notes": "Journal: 'trass journals' maps to 'trass.journal' database only. User simplifies to 'journals' instead of 'journal entries'."
                },
                {
                    "query_type": "Journal - Explicit workspace:database format",
                    "user_query": "7 days of workspace: koii database: journal entries from every month since 2025-03",
                    "sql_pattern": f"SELECT page_id, title, database_name, created_time, metadata FROM unified_content WHERE database_name IN ({koii_journal_dbs}) AND DATE(created_time) >= '2025-03-01' LIMIT 1000",
                    "notes": "Journal: 'workspace: koii database: journal' maps to 'journal' database only. Complex temporal 'every month since' pattern with specific date."
                }
            ])
        
        # NOTION/CMS QUERIES - Based on real user patterns
        notion_dbs = [db for db in available_dbs if 'stories' in db.lower() or 'cms' in db.lower()]
        if notion_dbs:
            notion_db_list = ', '.join([f"'{db}'" for db in notion_dbs])
            examples.append({
                "query_type": "Notion - Person search with workspace and 'contain the word' phrasing",
                "user_query": "koii notion entries that contain the word eddie",
                "sql_pattern": f"SELECT page_id, title, database_name, created_time, metadata FROM unified_content WHERE database_name IN ({notion_db_list}) AND (title LIKE '%eddie%' OR metadata LIKE '%eddie%') LIMIT 1000",
                "notes": "Notion: User searches for real people ('eddie'), uses specific phrasing 'contain the word', workspace qualifier ('koii notion entries')."
            })
        
        # COMPLEX TEMPORAL PATTERNS - Based on real user advanced queries
        if journal_dbs:
            examples.extend([
                {
                    "query_type": "Journal - Complex multi-month sampling pattern",
                    "user_query": "a couple days of journal entries from every month since 2024-12",
                    "sql_pattern": f"SELECT page_id, title, database_name, created_time, metadata FROM unified_content WHERE database_name IN ({all_journal_dbs}) AND DATE(created_time) >= '2024-12-01' LIMIT 200",
                    "notes": "Journal: User uses casual phrasing ('a couple days'), complex temporal logic ('every month since YYYY-MM'), expects sampling not exhaustive results."
                },
                {
                    "query_type": "Journal - Multi-month pattern with specific day counts",
                    "user_query": "7 days of koii journal entries from each of the last 7 months", 
                    "sql_pattern": f"SELECT page_id, title, database_name, created_time, metadata FROM unified_content WHERE database_name IN ({koii_journal_dbs}) AND DATE(created_time) >= DATE('now', '-7 months') LIMIT 1000",
                    "notes": "Journal: Complex temporal pattern ('from each of the last X months'), specific day counts, workspace-aware, used with browse mode."
                }
            ])
        
        return examples

    def _build_graph(self) -> StateGraph:
        """BUILD: 4-node workflow with confirmation step."""
        workflow = StateGraph(QueryState)
        
        workflow.add_node("parse", self._parse_node)
        workflow.add_node("confirm", self._confirm_node)
        workflow.add_node("execute", self._execute_node) 
        workflow.add_node("measure", self._measure_node)
        
        workflow.set_entry_point("parse")
        workflow.add_edge("parse", "confirm")
        workflow.add_edge("confirm", "execute")
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
            
            # Get workspace information dynamically
            workspace_info = self.schema.get('workspace_mapping', {})
            available_workspaces = list(workspace_info.get('workspaces', {}).keys())
            if not available_workspaces:
                available_workspaces = ['koii', 'trass']  # fallback
            
            prompt = f"""Parse this query into the required format:

Query: "{state['user_query']}"
Available databases: {available_dbs}
Available workspaces: {available_workspaces}

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

WORKSPACE INTELLIGENCE RULES (CRITICAL):
{self._generate_workspace_rules(available_workspaces)}
- If NO workspace mentioned → include ALL relevant databases (will be filtered to default workspace later)
- Default workspace ({workspace_info.get('default_workspace', 'koii')}) is used when no workspace specified
- User feedback will refine database selection after initial parsing

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
            
            # Enhance workspace detection and default handling
            parsed_intent = self._enhance_workspace_detection(parsed_intent, state['user_query'])
            
            state["intent"] = parsed_intent
            print(f"✅ Parsed: {parsed_intent['goal']}")
            
        except Exception as e:
            state["errors"] = [f"Parse failed: {e}"]
            print(f"❌ Parse error: {e}")
        
        return state

    def _generate_workspace_rules(self, available_workspaces: list) -> str:
        """Generate dynamic workspace rules based on available workspaces."""
        workspace_info = self.schema.get('workspace_mapping', {})
        default_workspace = workspace_info.get('default_workspace', 'koii')
        
        rules = []
        for workspace in available_workspaces:
            if workspace == default_workspace:
                # Default workspace uses unprefixed databases
                rules.append(f'- If query mentions "{workspace}" or "{workspace}." → ONLY include non-prefixed databases (journal, not other-workspace.journal)')
            else:
                # Non-default workspaces use prefixed databases
                rules.append(f'- If query mentions "{workspace}" or "{workspace}." → ONLY include {workspace}-prefixed databases ({workspace}.journal, not journal)')
        
        return '\n'.join(rules)

    def _enhance_workspace_detection(self, parsed_intent: dict, user_query: str) -> dict:
        """Enhance workspace detection with intelligent default handling."""
        import re
        
        # Get workspace mapping
        workspace_info = self.schema.get('workspace_mapping', {})
        default_workspace = workspace_info.get('default_workspace', 'koii')
        available_workspaces = list(workspace_info.get('workspaces', {}).keys())
        if not available_workspaces:
            available_workspaces = ['koii', 'trass']  # fallback
        
        # Detect explicit workspace mentions dynamically
        query_lower = user_query.lower()
        workspaces_mentioned = []
        
        # Check for explicit workspace mentions across all available workspaces
        for workspace in available_workspaces:
            if (workspace.lower() in query_lower or 
                f'workspace: {workspace.lower()}' in query_lower or 
                f'{workspace.lower()}.' in query_lower):
                workspaces_mentioned.append(workspace)
        
        # Apply dynamic workspace handling
        enhanced_databases = []
        databases = parsed_intent.get('databases', [])
        
        if workspaces_mentioned:
            # User explicitly mentioned workspace(s) - only include databases from those workspaces
            print(f"🎯 Workspace(s) {workspaces_mentioned} explicitly mentioned - filtering databases")
            for db in databases:
                for workspace in workspaces_mentioned:
                    if workspace == default_workspace:
                        # For default workspace, include unprefixed databases
                        if '.' not in db:  # default workspace databases don't have workspace prefix
                            enhanced_databases.append(db)
                            break
                    else:
                        # For non-default workspaces, include only workspace-prefixed databases
                        if db.startswith(f'{workspace}.'):
                            enhanced_databases.append(db)
                            break
        else:
            # No explicit workspace - ONLY use default workspace
            print(f"🧠 No explicit workspace mentioned - defaulting to ONLY {default_workspace} workspace")
            
            for db in databases:
                if '.' in db:
                    # This is a prefixed database - only include if it's from default workspace
                    workspace_prefix = db.split('.', 1)[0]
                    if workspace_prefix == default_workspace:
                        enhanced_databases.append(db)
                        print(f"   ✅ Including '{db}' (default workspace)")
                    else:
                        # Non-default workspace database - check if default has equivalent
                        base_name = db.split('.', 1)[1]
                        has_default = any(avail_db['name'] == base_name for avail_db in self.schema['databases'])
                        
                        if has_default:
                            enhanced_databases.append(base_name)
                            print(f"   📍 Using '{base_name}' instead of '{db}' (default workspace only)")
                        else:
                            print(f"   ❌ Skipping '{db}' (not in default workspace and no equivalent)")
                else:
                    # Unprefixed database - assume it's from default workspace
                    enhanced_databases.append(db)
                    print(f"   ✅ Including '{db}' (default workspace)")
        
        # Remove duplicates and ensure clean list
        parsed_intent['databases'] = list(dict.fromkeys(enhanced_databases))
        
        # Add workspace context for debugging
        if workspaces_mentioned:
            parsed_intent['_workspace_context'] = f"Explicit workspaces: {', '.join(workspaces_mentioned)}"
        else:
            parsed_intent['_workspace_context'] = f"Default workspace only (default: {default_workspace})"
        
        return parsed_intent

    def _confirm_node(self, state: QueryState) -> QueryState:
        """Show parsed intent and get user confirmation before execution."""
        import os
        
        # Skip confirmation if in non-interactive mode or env var set
        if os.getenv("MAIA_SKIP_CONFIRM") == "1" or os.getenv("MAIA_NON_INTERACTIVE") == "1":
            return state
        
        intent = state.get("intent")
        if not intent:
            state["errors"] = ["No intent to confirm"]
            return state
        
        # Show formatted intent summary
        print("\n🤖 AI Query Interpretation")
        print(f"Goal: {intent['goal']}")
        print(f"Databases: {', '.join(intent['databases'])}")
        if intent.get('search_terms'):
            print(f"Search terms: {', '.join(intent['search_terms'])}")
        else:
            print("Search terms: (none - using date filtering)")
        print(f"Result limit: {intent['limit']}")
        
        if intent.get('_workspace_context'):
            print(f"Workspace: {intent['_workspace_context']}")
        print()
        
        # Get user choice
        while True:
            try:
                choice = input("\n👉 Continue? (c)ontinue, (m)odify, (q)uit: ").strip().lower()
                
                if choice in ['c', 'continue', '']:
                    print("Proceeding with execution...")
                    return state
                elif choice in ['m', 'modify']:
                    return self._handle_modification(state)
                elif choice in ['q', 'quit']:
                    print("❌ Query cancelled by user")
                    state["errors"] = ["Query cancelled by user"]
                    return state
                else:
                    print("⚠️  Please enter 'c' (continue), 'm' (modify), or 'q' (quit)")
                    
            except KeyboardInterrupt:
                print("\n❌ Query cancelled by user")
                state["errors"] = ["Query cancelled by user"]
                return state
            except EOFError:
                print("\n✅ Proceeding with execution...")
                return state
    
    def _handle_modification(self, state: QueryState) -> QueryState:
        """Handle user request to modify the parsed intent using natural language."""
        print("\n🗣️  Tell me what to change in natural language:")
        print("   Examples:")
        print("   • 'only search journal database'")
        print("   • 'increase limit to 5000'") 
        print("   • 'search for meetings instead of graham'")
        print("   • 'include trass workspace too'")
        print("   • 'cancel' or 'back' to return")
        
        try:
            modification = input("\n👉 What would you like to change? ").strip()
            
            if modification.lower() in ['cancel', 'back', 'quit', '']:
                print("Returning to confirmation...")
                return self._confirm_node(state)
                
            # Use AI to interpret the modification
            intent = state["intent"]
            modified_intent = self._interpret_modification(intent, modification)
            
            if modified_intent:
                state["intent"] = modified_intent
                print("✅ Applied your changes:")
                print(f"   📝 Goal: {modified_intent['goal']}")
                print(f"   🗄️  Databases: {', '.join(modified_intent['databases'])}")
                print(f"   🔍 Search terms: {', '.join(modified_intent.get('search_terms', []))}")
                print(f"   📊 Limit: {modified_intent['limit']}")
            else:
                print("⚠️  Could not interpret modification. Returning to confirmation...")
                
            # Return to confirmation after modification
            return self._confirm_node(state)
            
        except (KeyboardInterrupt, EOFError):
            print("\n❌ Modification cancelled")
            return self._confirm_node(state)

    def _interpret_modification(self, current_intent: dict, modification: str) -> dict:
        """Use AI to interpret natural language modifications to the intent."""
        try:
            available_dbs = [db["name"] for db in self.schema["databases"]]
            
            prompt = f"""Modify this query intent based on user feedback.

CURRENT INTENT:
Goal: {current_intent['goal']}
Databases: {current_intent['databases']}
Search terms: {current_intent.get('search_terms', [])}
Limit: {current_intent['limit']}

USER MODIFICATION REQUEST: "{modification}"

Available databases: {available_dbs}

Apply the user's requested changes and return the modified intent in this exact JSON format:
{{
    "goal": "updated goal if changed",
    "databases": ["updated", "database", "list"],
    "search_terms": ["updated", "search", "terms"],
    "limit": updated_limit_number
}}

Modification rules:
- If user mentions specific databases, update the databases list
- If user mentions search terms/keywords, update search_terms
- If user mentions numbers/limits, update the limit  
- If user mentions "only X", replace databases with just X
- If user mentions "add X" or "include X", add X to existing list
- If user mentions "remove X", remove X from existing list
- Keep other fields unchanged unless specifically mentioned

Return only the JSON object:"""

            response = self.llm.invoke([
                SystemMessage(content="You are a JSON modifier. Return only valid JSON that applies user modifications."),
                HumanMessage(content=prompt)
            ])
            
            # Parse the JSON response
            import json
            json_str = response.content.strip()
            if json_str.startswith('```json'):
                json_str = json_str[7:-3].strip()
            elif json_str.startswith('```'):
                json_str = json_str[3:-3].strip()
                
            modified_intent = json.loads(json_str)
            
            # Validate the modification makes sense
            if (isinstance(modified_intent.get('databases'), list) and 
                isinstance(modified_intent.get('search_terms'), list) and 
                isinstance(modified_intent.get('limit'), int)):
                return modified_intent
            else:
                print(f"⚠️  Invalid modification result: {modified_intent}")
                return None
                
        except Exception as e:
            print(f"⚠️  Error interpreting modification: {e}")
            return None

    def _execute_node(self, state: QueryState) -> QueryState:
        """DO/TEST: Generate SQL and execute it."""
        if not state.get("intent"):
            state["errors"] = ["No intent to execute"]
            return state
            
        try:
            intent = state["intent"]
            
            # Check for temporal grouping
            temporal_grouping = intent.get('temporal_grouping', {})
            if temporal_grouping.get('enabled', False):
                # Generate temporal grouping SQL
                sql = self._generate_temporal_grouping_sql(intent)
                state["generated_sql"] = sql
            else:
                # Generate regular SQL with workspace context
                workspace_info = self.schema.get('workspace_mapping', {})
                workspace_context = ""
                if workspace_info:
                    workspace_context = f"""
=== WORKSPACE-DATABASE MAPPING ===
{workspace_info.get('naming_convention', '')}
Default workspace: {workspace_info.get('default_workspace', 'koii')}

Available workspace databases:
{chr(10).join([f"- {db_key}: {db_data.get('workspace', 'unknown')} workspace ({db_data.get('source_type', 'unknown')} type)" for db_key, db_data in workspace_info.get('databases', {}).items() if db_data.get('enabled', True)])}

WORKSPACE MAPPING RULES (CRITICAL - FOLLOW EXACTLY):
- "koii journal" / "koii.journal" / "koii journals" → database_name = 'journal' ONLY
  ❌ DO NOT include 'trass.journal' or any other journal database
- "trass journal" / "trass.journal" / "trass journals" → database_name = 'trass.journal' ONLY  
  ❌ DO NOT include 'journal' or any other journal database
- "workspace: koii database: journal" → database_name = 'journal' ONLY
  ❌ DO NOT include 'trass.journal' - user specified koii workspace explicitly
- "workspace: trass database: journal" → database_name = 'trass.journal' ONLY
  ❌ DO NOT include 'journal' - user specified trass workspace explicitly

EXCLUSION LOGIC: When user specifies a workspace (koii, trass), exclude ALL databases from other workspaces.
"""

                sql_prompt = f"""Generate SQLite query for: {intent['goal']}

=== DATABASE CONTEXT ===
Table: {self.schema['main_table']}
Columns: {', '.join(self.schema['key_columns'])}
{self.schema['date_info']}

Target databases (ONLY use these):
{chr(10).join([f"- {db_name}: {next((db['count'] for db in self.schema['databases'] if db['name'] == db_name), 'unknown')} entries" for db_name in intent['databases']])}

{workspace_context}

=== PROVEN QUERY TEMPLATES ===
Here are concrete, working examples for your database:
{chr(10).join([f"TYPE: {template['query_type']}" + chr(10) + f"QUERY: \"{template['user_query']}\"" + chr(10) + f"SQL: {template['sql_pattern']}" + chr(10) + f"NOTES: {template['notes']}" + chr(10) for template in self.schema.get('query_templates', [])])}

=== YOUR TASK ===
Query goal: {intent['goal']}
Target databases: {intent['databases']}
Search terms: {intent['search_terms']}
Result limit: {intent['limit']}

CRITICAL INSTRUCTIONS:
1. **ONLY USE TARGET DATABASES** - Use EXCLUSIVELY the databases listed in "Target databases" above
2. **NEVER include other databases** - Even if templates show other databases, stick to target list
3. **Follow workspace filtering** - Target databases have already been filtered for workspace logic
4. **Generate WHERE clause** - Use: WHERE database_name IN ({', '.join([f"'{db}'" for db in intent['databases']])})
5. **Handle limits correctly** - Use limit: {intent['limit']}

⚠️  CRITICAL: The target databases list above is the FINAL filtered list. Do not add or modify databases.

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
            sql = state["generated_sql"]
            if os.getenv("MAIA_DEBUG") == "1":
                print(f"🔍 Executing: {sql}")
                
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute(sql)
                
                results = [dict(row) for row in cursor.fetchall()]
                state["results"] = results
                
            print(f"Executed: {len(results)} results")
            
        except Exception as e:
            state["errors"] = [f"Execute failed: {e}"]
            print(f"❌ Execute error: {e}")
        
        return state

    def _generate_temporal_grouping_sql(self, intent: Dict[str, Any]) -> str:
        """Generate SQL for temporal grouping queries like 'X entries from every month'."""
        temporal_grouping = intent.get('temporal_grouping', {})
        period = temporal_grouping.get('period', 'month')
        per_period_limit = temporal_grouping.get('per_period_limit', 3)
        start_date = temporal_grouping.get('start_date', '2025-01-01')
        databases = intent.get('databases', [])
        
        # Build database filter
        db_filter = ""
        if databases:
            db_placeholders = ", ".join(f"'{db}'" for db in databases)
            db_filter = f"AND database_name IN ({db_placeholders})"
        
        if period == 'month':
            # Generate monthly grouping SQL with per-month limit
            sql = f"""
WITH ranked_entries AS (
    SELECT 
        page_id, title, database_name, created_time, metadata,
        ROW_NUMBER() OVER (
            PARTITION BY strftime('%Y-%m', created_time) 
            ORDER BY created_time DESC
        ) as rn
    FROM unified_content
    WHERE created_time >= '{start_date}' {db_filter}
)
SELECT page_id, title, database_name, created_time, metadata
FROM ranked_entries 
WHERE rn <= {per_period_limit}
ORDER BY created_time DESC
"""
        elif period == 'week':
            # Generate weekly grouping SQL with per-week limit
            sql = f"""
WITH ranked_entries AS (
    SELECT 
        page_id, title, database_name, created_time, metadata,
        ROW_NUMBER() OVER (
            PARTITION BY strftime('%Y-%W', created_time) 
            ORDER BY created_time DESC
        ) as rn
    FROM unified_content
    WHERE created_time >= '{start_date}' {db_filter}
)
SELECT page_id, title, database_name, created_time, metadata
FROM ranked_entries 
WHERE rn <= {per_period_limit}
ORDER BY created_time DESC
"""
        elif period == 'day':
            # Generate daily grouping SQL with per-day limit
            sql = f"""
WITH ranked_entries AS (
    SELECT 
        page_id, title, database_name, created_time, metadata,
        ROW_NUMBER() OVER (
            PARTITION BY DATE(created_time) 
            ORDER BY created_time DESC
        ) as rn
    FROM unified_content
    WHERE created_time >= '{start_date}' {db_filter}
)
SELECT page_id, title, database_name, created_time, metadata
FROM ranked_entries 
WHERE rn <= {per_period_limit}
ORDER BY created_time DESC
"""
        else:
            # Fallback to simple query
            sql = f"""
SELECT page_id, title, database_name, created_time, metadata
FROM unified_content
WHERE created_time >= '{start_date}' {db_filter}
ORDER BY created_time DESC
LIMIT {per_period_limit * 12}
"""
        
        return sql.strip()

    def _measure_node(self, state: QueryState) -> QueryState:
        """MEASURE: Validate results."""
        results = state.get("results", [])
        errors = state.get("errors", [])
        
        if results and len(results) > 0:
            print(f"Success: {len(results)} results")
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


class LangGraphQuerySystem:
    """Main interface for the LangGraph query system with real examples."""
    
    def __init__(self, db_path: str = "data/hybrid_metadata.db"):
        self.db_path = db_path
        # Use the new intelligent processor with adapter
        from .intelligent_nl_processor import PromaiLLMAdapter
        
        # Create LLM adapter (will prioritize Claude now)
        llm_adapter = PromaiLLMAdapter()
        
        # Initialize processor with Claude-first LLM
        self.processor = IntelligentQueryProcessor(llm_adapter, db_path)
    
    def process_natural_language_query(self, query: str) -> Dict[str, Any]:
        """Process a natural language query and return results."""
        return self.processor.process(query)
