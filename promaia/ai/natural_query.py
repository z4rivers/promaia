"""
Natural language query processing for chat context generation.
Converts natural language to SQL and executes directly against content_registry.
"""
import json
import re
import os
import sqlite3
import glob
from typing import List, Tuple, Optional, Dict, Any
from datetime import datetime, timedelta

from anthropic import Anthropic
from openai import OpenAI
import google.generativeai as genai

from promaia.utils.config import load_environment
from promaia.config.databases import get_database_manager
from promaia.storage.json_registry import get_json_registry

# Load environment variables
load_environment()


def get_ai_client():
    """Get an available AI client, preferring Anthropic, then Gemini, then OpenAI."""
    if os.getenv("ANTHROPIC_API_KEY"):
        return Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    elif os.getenv("GOOGLE_API_KEY"):
        genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
        return genai
    elif os.getenv("OPENAI_API_KEY"):
        return OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    else:
        raise ValueError("No AI API key configured. Please set ANTHROPIC_API_KEY, GOOGLE_API_KEY, or OPENAI_API_KEY")


def process_natural_language_to_content(nl_prompt: str, workspace: str) -> Dict[str, List[Dict[str, Any]]]:
    """
    Process natural language prompt to generate content directly using SQL.
    
    Args:
        nl_prompt: Natural language description of what content to load
        workspace: Workspace name to use for context
        
    Returns:
        Dictionary with source names as keys and lists of page data as values,
        matching the format expected by the chat interface
    """
    # Get workspace databases for context
    db_manager = get_database_manager()
    workspace_databases = db_manager.get_workspace_databases(workspace)
    
    if not workspace_databases:
        raise ValueError(f"No databases configured for workspace '{workspace}'")
    
    # Build context about available databases and schema
    db_context = []
    for db in workspace_databases:
        db_context.append({
            "nickname": db.nickname,
            "database_name": db.name,
            "type": db.source_type,
            "description": f"{db.source_type} database containing {db.name} data"
        })
    
    # Database schema information for AI
    schema_info = """
    The content_registry database has this schema:
    
    TABLE: content_registry
    - page_id (TEXT): Unique identifier for each page/email
    - workspace (TEXT): Workspace name (e.g., 'koii')  
    - database_name (TEXT): Database nickname (e.g., 'gmail', 'journal', 'stories')
    - file_path (TEXT): Path to the markdown file containing content
    - title (TEXT): Title of the page/email
    - created_time (TEXT): ISO timestamp when created (e.g., '2025-06-30T07:00:00.000Z')
    - last_edited_time (TEXT): ISO timestamp when last edited
    - synced_time (TEXT): ISO timestamp when synced to local
    - metadata (TEXT): JSON string containing properties (structure varies by source type)
    
    IMPORTANT: Metadata Structure by Source Type:
    
    1. NOTION DATABASES (journal, stories, cms, epics, projects):
       - Have 'properties' key with nested Notion property objects
       - Each property has: {'id': 'abc', 'type': 'property_type', 'property_type': {actual_value}}
       
       Common property types and JSON extraction patterns:
       - Status: json_extract(metadata, '$.properties.Status.status.name') = 'Done'|'Backlog'|'In Progress'
       - Rich Text: json_extract(metadata, '$.properties."Author Name".rich_text[0].plain_text') = 'Koii Benvenutto'
       - Checkbox: json_extract(metadata, '$.properties.Featured.checkbox') = true|false
       - Date: json_extract(metadata, '$.properties.Date.date.start') = '2025-06-30'
       - Created Time: json_extract(metadata, '$.properties."Created time".created_time') = '2025-06-30T07:00:00.000Z'
       
       Example metadata for stories database:
       {"properties": {"Status": {"type": "status", "status": {"name": "Done", "color": "green"}}, "Author Name": {"type": "rich_text", "rich_text": [{"plain_text": "Koii"}]}}}
    
    2. GMAIL DATABASE:
       - Currently has empty/minimal properties in metadata
       - IMPORTANT: Many Gmail entries have empty created_time/last_edited_time fields
       - For Gmail searches:
         * For recent emails: Use last_edited_time IS NOT NULL AND last_edited_time != '' AND datetime(last_edited_time) >= datetime('now', '-X days')
         * For older emails or general searches: Skip date filtering, use database_name = 'gmail' only
         * For text search: Always rely on content_filters
         * Subject line may be in title field
       - Example: For "emails from last week", use: WHERE database_name = 'gmail' AND last_edited_time IS NOT NULL AND last_edited_time != '' AND datetime(last_edited_time) >= datetime('now', '-7 days')
    
    3. Other sources (awakenings, cpj):
       - May have limited or no metadata properties
       - Rely on content_filters and date fields
    
    SEARCH STRATEGY:
    - For text search: Always use content_filters, never try to search file content in SQL
    - For Notion property searches: Use json_extract with proper path based on property type
    - For date ranges: Use datetime() functions on created_time or last_edited_time
    - For Gmail: Focus on date filtering and content_filters, avoid metadata searches
    """
    
    # Create AI prompt for generating SQL
    system_prompt = f"""You are a SQL query generator for a content management system. You understand that this system stores content from different sources (Notion databases, Gmail, etc.) with varying metadata structures.

Available databases in workspace '{workspace}':
{json.dumps(db_context, indent=2)}

{schema_info}

Your task is to convert natural language requests into:
1. A SQL query against the content_registry table
2. Content filters for text search within markdown files

CRITICAL RULES:
1. ALWAYS include WHERE workspace = '{workspace}'
2. Use database_name to filter by specific data sources
3. For Notion databases: Use json_extract(metadata, '$.properties.PropertyName.type.value') patterns
4. For Gmail: Avoid metadata searches, use content_filters and date filtering only
5. For date comparisons: Use datetime(created_time) or datetime(last_edited_time) 
6. For content text search: Specify in content_filters array, NOT in SQL
7. Property names with spaces need quotes: json_extract(metadata, '$.properties."Created time".created_time')

EXAMPLES:

Query: "emails from last week"
→ SQL: WHERE database_name = 'gmail' AND datetime(created_time) >= datetime('now', '-7 days')
→ Content filters: []

Query: "journal entries with status Done"  
→ SQL: WHERE database_name = 'journal' AND json_extract(metadata, '$.properties.Status.status.name') = 'Done'
→ Content filters: []

Query: "stories about productivity that are in progress"
→ SQL: WHERE database_name = 'stories' AND json_extract(metadata, '$.properties.Status.status.name') = 'In Progress'  
→ Content filters: ['productivity', 'productive']

Query: "emails containing avask"
→ SQL: WHERE database_name = 'gmail'
→ Content filters: ['avask']

Respond with JSON:
{{
    "sql_query": "SELECT page_id, title, created_time, last_edited_time, file_path, metadata, database_name FROM content_registry WHERE workspace = '{workspace}' AND ...",
    "content_filters": ["text", "to", "search", "in", "content"]
}}

User request: "{nl_prompt}"
"""

    try:
        # Get AI client and generate response
        client = get_ai_client()
        
        if isinstance(client, Anthropic):  # Anthropic
            response = client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=1000,
                system=system_prompt,
                messages=[{"role": "user", "content": nl_prompt}]
            )
            content = response.content[0].text
        elif hasattr(client, 'chat') and hasattr(client.chat, 'completions'):  # OpenAI
            response = client.chat.completions.create(
                model="gpt-4",
                max_tokens=1000,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": nl_prompt}
                ]
            )
            content = response.choices[0].message.content
        else:  # Gemini
            model = genai.GenerativeModel('gemini-pro')
            response = model.generate_content(f"{system_prompt}\n\nUser: {nl_prompt}")
            content = response.text
        
        # Parse the JSON response
        try:
            # Clean the response and extract JSON
            content = content.strip()
            
            # Find JSON object boundaries more robustly
            start_idx = content.find('{')
            end_idx = content.rfind('}') + 1
            
            if start_idx != -1 and end_idx > start_idx:
                json_str = content[start_idx:end_idx]
                
                # Clean control characters that might cause parsing issues
                json_str = ''.join(char for char in json_str if ord(char) >= 32 or char in '\n\r\t')
                
                result = json.loads(json_str)
            else:
                raise json.JSONDecodeError("No JSON object found", content, 0)
            
            sql_query = result.get('sql_query', '')
            content_filters = result.get('content_filters', [])
            
            print(f"🔍 Generated SQL: {sql_query}")
            if content_filters:
                print(f"📝 Content filters: {content_filters}")
            
            # Execute the SQL query and load content
            return execute_sql_and_load_content(sql_query, content_filters, workspace)
            
        except json.JSONDecodeError as e:
            print(f"⚠️  Warning: Could not parse AI response as JSON: {e}")
            print(f"Raw response: {content}")
            return {}
            
    except Exception as e:
        print(f"⚠️  Warning: Error processing natural language query: {e}")
        return {}


def execute_sql_and_load_content(sql_query: str, content_filters: List[str], workspace: str) -> Dict[str, List[Dict[str, Any]]]:
    """
    Execute SQL query against content_registry and load the corresponding markdown files.
    
    Args:
        sql_query: SQL query to execute
        content_filters: Text filters to apply to content
        workspace: Workspace name
        
    Returns:
        Dictionary with database names as keys and lists of page data as values
    """
    try:
        # Get the registry database
        registry = get_json_registry()
        
        # Execute the SQL query
        with sqlite3.connect(registry.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(sql_query)
            rows = cursor.fetchall()
            
        print(f"📊 SQL query returned {len(rows)} entries")
        
        # Group results by database_name
        results_by_database = {}
        
        for row in rows:
            try:
                # Unpack the row (adjust based on SQL SELECT fields)
                page_id, title, created_time, last_edited_time, file_path, metadata, database_name = row
                
                # Read the markdown file
                if not os.path.exists(file_path):
                    continue
                    
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Apply content filters if specified
                if content_filters:
                    content_lower = content.lower()
                    matches_content = any(filter_text.lower() in content_lower for filter_text in content_filters)
                    if not matches_content:
                        continue
                
                # Parse created_time for sorting
                try:
                    if created_time:
                        date_obj = datetime.fromisoformat(created_time.replace("Z", "+00:00"))
                    elif last_edited_time:
                        date_obj = datetime.fromisoformat(last_edited_time.replace("Z", "+00:00"))
                    else:
                        # Fallback to file mtime
                        date_obj = datetime.fromtimestamp(os.path.getmtime(file_path))
                except (ValueError, TypeError):
                    date_obj = datetime.fromtimestamp(os.path.getmtime(file_path))
                
                # Create page data in the same format as read_markdown_files_with_registry
                page_data = {
                    'page_id': page_id,
                    'date': date_obj.strftime("%Y-%m-%d"),
                    'date_obj': date_obj,
                    'content': content,
                    'file_path': file_path,
                    'filename': os.path.basename(file_path),
                    'title': title or "Untitled",
                    'created_time': created_time,
                    'last_edited_time': last_edited_time,
                    'metadata': metadata,
                    'debug_info': "loaded via natural language SQL query"
                }
                
                # Add to results grouped by database
                if database_name not in results_by_database:
                    results_by_database[database_name] = []
                results_by_database[database_name].append(page_data)
                
            except Exception as e:
                print(f"Warning: Error processing row: {e}")
                continue
        
        # Sort each database's results by date (newest first)
        for db_name, pages in results_by_database.items():
            pages.sort(key=lambda x: x['date_obj'], reverse=True)
        
        total_pages = sum(len(pages) for pages in results_by_database.values())
        print(f"📋 Loaded {total_pages} pages across {len(results_by_database)} databases")
        
        return results_by_database
        
    except Exception as e:
        print(f"❌ Error executing SQL query: {e}")
        return {}


def debug_print(message: str):
    """Print debug message if debug mode is enabled."""
    if os.getenv("MAIA_DEBUG", "0") == "1":
        print(f"[DEBUG] {message}") 