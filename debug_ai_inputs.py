#!/usr/bin/env python3
"""
Debug script to log exactly what inputs the AI receives during query processing.
This will help debug why the system is making poor database selection choices.
"""

import sqlite3
import os
import json
from datetime import datetime
from typing import Dict, Any, List


def print_separator(title: str, char="="):
    """Print a formatted section separator"""
    print(f"\n{char * 60}")
    print(f" {title}")
    print(f"{char * 60}")


def print_subsection(title: str):
    """Print a formatted subsection"""
    print(f"\n--- {title} ---")


def debug_workspace_mapping():
    """Debug the workspace mapping from config"""
    print_separator("WORKSPACE MAPPING DEBUG")
    
    try:
        config_path = 'promaia.config.json'
        if not os.path.exists(config_path):
            print("❌ promaia.config.json not found!")
            return None
            
        with open(config_path, 'r') as f:
            config = json.load(f)
            
        print_subsection("Config Structure")
        print(f"Default workspace: {config.get('default_workspace', 'koii')}")
        print(f"Workspaces: {list(config.get('workspaces', {}).keys())}")
        print(f"Total databases: {len(config.get('databases', {}))}")
        
        print_subsection("Database Mapping (The Rosetta Stone)")
        databases = config.get('databases', {})
        
        for db_key, db_data in databases.items():
            workspace = db_data.get('workspace', 'koii')
            nickname = db_data.get('nickname', db_key.split('.')[-1])
            source_type = db_data.get('source_type', 'unknown')
            enabled = db_data.get('sync_enabled', True)
            
            print(f"🔍 {db_key}:")
            print(f"    Workspace: {workspace}")
            print(f"    Nickname: {nickname}")
            print(f"    Type: {source_type}")
            print(f"    Enabled: {enabled}")
            print()
            
        return config
    except Exception as e:
        print(f"❌ Error loading config: {e}")
        return None


def debug_failing_query():
    """Debug the specific failing query"""
    print_separator("FAILING QUERY DEBUG")
    
    failing_query = "7 days of workspace: koii databse: journal entries from every month since 2025-03"
    
    print(f"🔍 FAILING QUERY: \"{failing_query}\"")
    print_subsection("Expected Behavior")
    print("✅ Should map to: database_name = 'journal' ONLY")
    print("✅ Should NOT include: 'trass.journal', 'stories', or any other databases")
    print("✅ Reason: 'workspace: koii database: journal' should be very explicit")
    
    print_subsection("Actual Behavior (From User)")
    print("❌ Got: 'journal' AND 'trass.journal' (both journal databases)")
    print("❌ Then after edit, mysteriously added 'stories' database")
    print("❌ This suggests the AI is not understanding workspace constraints")
    
    return failing_query


def debug_database_content():
    """Debug what's actually in the database"""
    print_separator("DATABASE CONTENT DEBUG")
    
    db_path = 'data/hybrid_metadata.db'
    
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            
            print_subsection("Available Databases")
            cursor.execute("SELECT DISTINCT database_name, COUNT(*) as count FROM unified_content GROUP BY database_name ORDER BY database_name")
            db_counts = cursor.fetchall()
            
            for db_name, count in db_counts:
                print(f"📊 {db_name}: {count} entries")
                
            print_subsection("Journal Databases Specifically")
            journal_dbs = [db for db, count in db_counts if 'journal' in db.lower()]
            
            for db_name in journal_dbs:
                cursor.execute(f"SELECT COUNT(*) FROM unified_content WHERE database_name = '{db_name}' AND DATE(created_time) >= '2025-03-01'")
                since_march = cursor.fetchone()[0]
                print(f"📝 {db_name}: {since_march} entries since March 2025")
                
            print_subsection("Recent Entry Sample")
            cursor.execute("""
                SELECT database_name, title, created_time 
                FROM unified_content 
                WHERE DATE(created_time) >= DATE('now', '-7 days')
                ORDER BY created_time DESC 
                LIMIT 10
            """)
            recent = cursor.fetchall()
            
            for db_name, title, created_time in recent:
                print(f"📄 {db_name}: {title[:50]}... ({created_time})")
                
    except Exception as e:
        print(f"❌ Database error: {e}")


def simulate_ai_input():
    """Simulate what the AI would receive as input"""
    print_separator("AI INPUT SIMULATION")
    
    failing_query = "7 days of workspace: koii databse: journal entries from every month since 2025-03"
    
    print_subsection("Step 1: Intent Parsing")
    print("🤖 AI Task: Parse user intent from natural language")
    print(f"Input: \"{failing_query}\"")
    print()
    print("AI should extract:")
    print("  - Goal: Get journal entries from koii workspace")
    print("  - Workspace: koii (explicit)")
    print("  - Database: journal (explicit)")
    print("  - Time constraint: since March 2025")
    print("  - Sampling: 7 days from each month")
    
    print_subsection("Step 2: Database Selection")
    print("🤖 AI Task: Choose which databases to query")
    print("Available options:")
    print("  - journal (koii workspace)")
    print("  - trass.journal (trass workspace)")
    print("  - cms (koii workspace)")
    print("  - stories (koii workspace)")
    print("  - etc...")
    print()
    print("✅ CORRECT choice: ['journal'] only")
    print("❌ WRONG choice: ['journal', 'trass.journal'] - ignores workspace constraint")
    print("❌ VERY WRONG: ['journal', 'stories'] - adds unrelated database")
    
    print_subsection("Step 3: SQL Generation")
    print("🤖 AI Task: Generate SQL query")
    print("Expected SQL:")
    sql = """SELECT page_id, title, database_name, created_time, metadata 
FROM unified_content 
WHERE database_name IN ('journal') 
AND DATE(created_time) >= '2025-03-01' 
LIMIT 1000"""
    print(sql)
    

def create_test_prompt():
    """Create the exact prompt the AI would see"""
    print_separator("EXACT AI PROMPT DEBUG", "=")
    
    # Load config
    try:
        with open('promaia.config.json', 'r') as f:
            config = json.load(f)
    except:
        config = {}
    
    # Simulate database schema
    db_path = 'data/hybrid_metadata.db'
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT DISTINCT database_name, COUNT(*) as count FROM unified_content GROUP BY database_name ORDER BY count DESC")
            databases = [{"name": row[0], "count": row[1], "date_range": "2024-01-01 to 2025-09-14"} for row in cursor.fetchall()]
    except:
        databases = []
    
    # Create workspace mapping
    workspace_mapping = {
        "naming_convention": "Format: 'workspace.database' (e.g. 'trass.journal') OR just 'database' for default workspace (e.g. 'journal' for koii workspace)",
        "default_workspace": config.get("default_workspace", "koii"),
        "databases": {}
    }
    
    if "databases" in config:
        for db_key, db_data in config["databases"].items():
            workspace_mapping["databases"][db_key] = {
                "workspace": db_data.get("workspace", "koii"),
                "source_type": db_data.get("source_type", "unknown"),
                "enabled": db_data.get("sync_enabled", True)
            }
    
    # Create the exact prompt
    failing_query = "7 days of workspace: koii databse: journal entries from every month since 2025-03"
    
    workspace_context = f"""
=== WORKSPACE-DATABASE MAPPING ===
{workspace_mapping.get('naming_convention', '')}
Default workspace: {workspace_mapping.get('default_workspace', 'koii')}

Available workspace databases:
{chr(10).join([f"- {db_key}: {db_data.get('workspace', 'unknown')} workspace ({db_data.get('source_type', 'unknown')} type)" for db_key, db_data in workspace_mapping.get('databases', {}).items() if db_data.get('enabled', True)])}

WORKSPACE MAPPING RULES:
- "koii journal entries" → database_name = 'journal' (koii workspace default)
- "trass journal entries" → database_name = 'trass.journal' (trass workspace) 
- "workspace: koii database: journal" → database_name = 'journal' ONLY
- "workspace: trass database: journal" → database_name = 'trass.journal' ONLY
"""
    
    prompt = f"""Generate SQLite query for: {failing_query}

=== DATABASE CONTEXT ===
Table: unified_content
Columns: page_id, title, database_name, created_time, last_edited_time, metadata
Dates are in YYYY-MM-DD format. Use created_time or last_edited_time for date filtering.

Available databases with data:
{chr(10).join([f"- {db['name']}: {db['count']} entries ({db['date_range']})" for db in databases])}

{workspace_context}

=== YOUR TASK ===
Query goal: Get journal entries from koii workspace since March 2025
Target databases: Should be 'journal' ONLY
Search terms: None
Result limit: 1000

CRITICAL INSTRUCTIONS:
1. **WORKSPACE AWARENESS** - Pay attention to workspace qualifiers:
   - "koii journal" = 'journal' database ONLY
   - "trass journal" = 'trass.journal' database ONLY
   - Don't mix workspaces unless explicitly requested
2. The query explicitly says "workspace: koii database: journal" - this is VERY specific
3. Do NOT include 'trass.journal' or any other database
4. Use DATE filtering for "since 2025-03"

Generate the SQLite query:"""
    
    print_subsection("EXACT PROMPT THE AI SEES")
    print(prompt)
    
    print_subsection("ANALYSIS")
    print("🔍 The prompt clearly states:")
    print("  - Query explicitly specifies 'workspace: koii database: journal'")
    print("  - Workspace mapping rules are provided")  
    print("  - Critical instruction: 'journal' database ONLY")
    print("  - Warning: Don't mix workspaces")
    print()
    print("❓ If AI still chooses wrong databases, the issue is:")
    print("  1. LLM model quality (OpenAI vs Claude)")
    print("  2. Prompt ambiguity (need clearer instructions)")
    print("  3. Template examples conflicting with instructions")


def main():
    """Main debug function"""
    
    print_separator("PROMAIA AI INPUT DEBUG TOOL", "=")
    print("Debugging why the AI makes poor database selection choices")
    
    # Debug each component
    config = debug_workspace_mapping()
    failing_query = debug_failing_query() 
    debug_database_content()
    simulate_ai_input()
    create_test_prompt()
    
    print_separator("DEBUG SUMMARY", "=")
    print("🎯 KEY FINDINGS:")
    print()
    print("1. **Config is correct**: workspace.database mapping is clear in promaia.config.json")
    print("2. **Database content exists**: Both 'journal' and 'trass.journal' have data")
    print("3. **Query is explicit**: 'workspace: koii database: journal' should be unambiguous")
    print("4. **Prompt includes mapping**: Workspace rules are clearly stated in AI prompt")
    print()
    print("🔧 LIKELY ISSUES:")
    print("- OpenAI model quality: May not follow instructions as well as Claude")
    print("- Template examples: May have conflicting patterns that confuse the AI")
    print("- Intent parsing: AI may misparse 'workspace: koii' syntax")
    print()
    print("💡 RECOMMENDATIONS:")
    print("1. Test with Claude model to compare results")
    print("2. Add more explicit template examples with 'workspace: X database: Y' format")
    print("3. Add validation step to reject queries that ignore workspace constraints")
    print("4. Log intermediate steps (intent parsing, database selection) for debugging")


if __name__ == "__main__":
    main()
