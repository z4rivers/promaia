"""
Natural language query processing for chat context generation.
Converts natural language to SQL and executes directly against the hybrid unified_content view.
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


def process_natural_language_to_content(nl_prompt: str, workspace: str = None, schema_info: str = None) -> Dict[str, List[Dict[str, Any]]]:
    """
    Process natural language prompt to generate content directly using SQL against hybrid architecture.
    
    Args:
        nl_prompt: Natural language description of what content to load
        workspace: Optional workspace name for context (defaults to cross-workspace queries)
        schema_info: Schema information (auto-detected as hybrid)
        
    Returns:
        Dictionary with source names as keys and lists of page data as values,
        matching the format expected by the chat interface
    """
    # Get database context using hybrid query interface
    from promaia.storage.unified_query import get_query_interface
    query_interface = get_query_interface()
    
    # For cross-workspace queries, we don't need specific workspace context
    # We'll use a default workspace just to establish database connection
    workspace_for_db = workspace or "koii"  # Use any available workspace for DB connection
    
    try:
        db_context = query_interface.get_database_context(workspace_for_db)
        
        if not db_context:
            # Try to find any available workspace
            from promaia.config.workspaces import get_workspace_manager
            workspace_manager = get_workspace_manager()
            available_workspaces = workspace_manager.list_workspaces()
            if available_workspaces:
                workspace_for_db = available_workspaces[0]
                db_context = query_interface.get_database_context(workspace_for_db)
            
        if not db_context:
            raise ValueError("No databases found in any workspace")
            
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error getting database context: {e}")
        raise ValueError(f"Could not access databases: {e}")
    
    # Use provided schema info or default hybrid schema
    if schema_info is None:
        schema_info = f"""
HYBRID ARCHITECTURE - Optimized separate tables for each content type:

IMPORTANT: This system uses the 'unified_content' view for all queries.
DEFAULT BEHAVIOR: Query across ALL workspaces unless specifically mentioned.

OPTIMIZED TABLES BY CONTENT TYPE:

1. GMAIL (gmail_content table):
   Direct columns: subject, sender_email, sender_name, recipient_emails, gmail_labels,
                  thread_id, message_id, has_attachments, is_unread, body_snippet, email_date
   Examples:
   - "emails from john": WHERE sender_email LIKE '%john%' OR sender_name LIKE '%john%'
   - "unread emails": WHERE is_unread = 1
   - "emails with attachments": WHERE has_attachments = 1
   - "emails from last week": WHERE datetime(email_date) >= datetime('now', '-7 days')

2. NOTION JOURNAL (notion_journal table):
   Direct columns: title, status, date_value, tags, featured, author_name
   Examples:
   - "published journal entries": WHERE status = 'Published'
   - "featured journal entries": WHERE featured = 1
   - "entries by author": WHERE author_name = 'Koii Benvenutto'
   
3. NOTION STORIES (notion_stories table):
   Direct columns: title, status, epic_relation, author_name, story_points, priority, labels
   Examples:
   - "completed stories": WHERE status = 'Done'
   - "high priority stories": WHERE priority = 'High'
   - "stories with 5 points": WHERE story_points = 5
   
4. NOTION CMS (notion_cms table):
   Direct columns: title, status, category, featured, author_name, slug, tags, publish_date
   Examples:
   - "published blog posts": WHERE status = 'Published'
   - "featured content": WHERE featured = 1
   - "posts in tech category": WHERE category = 'Tech'

5. GENERIC CONTENT (generic_content table):
   For unknown content types, use metadata JSON extraction

UNIFIED VIEW SCHEMA:
The unified_content view provides these direct columns for fast access:

Core columns (all content types):
- page_id, workspace, database_name, content_type, file_path, title
- created_time, last_edited_time, synced_time, file_size, checksum

Direct filterable columns:
- status (TEXT): Content status - 'Published', 'Draft', 'Done', 'In Progress', etc.
- featured (INTEGER): 1 for featured content, 0 for normal, NULL if not applicable
- priority (TEXT): Priority level - 'High', 'Medium', 'Low', etc.
- category (TEXT): Content category 
- sender_email (TEXT): Email sender for Gmail content
- sender_name (TEXT): Sender name for Gmail content  
- has_attachments (INTEGER): 1 if Gmail has attachments, 0 if not
- is_unread (INTEGER): 1 if Gmail is unread, 0 if read

SEARCH STRATEGY:
- For text search: Always use content_filters, never try to search file content in SQL
- For property searches: Use direct columns when available (status, featured, priority, etc.)
- For date ranges: Use datetime() functions on created_time or last_edited_time
- For Gmail: Use direct columns like sender_email, has_attachments, is_unread

Cross-workspace queries enabled - query any combination of workspaces and databases.
"""

    # Get current date and time for temporal context
    from datetime import datetime
    current_datetime = datetime.now()
    current_date_str = current_datetime.strftime("%Y-%m-%d")
    current_time_str = current_datetime.strftime("%H:%M:%S")
    current_year = current_datetime.year
    current_month = current_datetime.strftime("%B")  # Full month name
    current_month_num = current_datetime.month

    # Create AI prompt for generating SQL - ENHANCED for multiple queries
    system_prompt = f"""You are an expert SQL query generator for a hybrid content management system. You can handle both simple and complex multi-part requests by generating multiple independent queries when needed.

CURRENT DATE AND TIME CONTEXT:
- Current Date: {current_date_str}
- Current Time: {current_time_str}
- Current Year: {current_year}
- Current Month: {current_month} ({current_month_num})

TEMPORAL REFERENCE RULES:
1. When users mention months without years (e.g., "march through june"), assume the CURRENT YEAR ({current_year})
2. "This year" = {current_year}
3. "Last year" = {current_year - 1}
4. "Next year" = {current_year + 1}
5. Relative terms like "last week", "last month" should use datetime('now', '-X days/months')
6. When users say "march through june" without a year, interpret as "March {current_year} through June {current_year}"
7. Always be explicit about years in date ranges to avoid confusion

HYBRID ARCHITECTURE - Always use unified_content view
{schema_info}

MULTI-QUERY DETECTION:
For complex requests that involve different databases with different requirements, generate multiple separate queries instead of trying to combine everything into one query.

SIMPLE QUERIES (use single query):
- "recent journal entries"
- "emails from john"
- "last week of trass.gmail"
- "published blog posts and completed stories" (same filtering logic)

COMPLEX QUERIES (use multiple queries):
- "emails containing X and recent journal entries" (different content filters)
- "gmail with meetings and all stories from last month" (selective content filtering)
- "avask emails and last 15 days of stories and journal" (content filter only applies to emails)

EXAMPLES OF MULTI-QUERY RESPONSES:

Query: "emails containing avask and last 15 days of stories"
Response:
{{
    "query_type": "multiple",
    "queries": [
        {{
            "sql_query": "SELECT page_id, title, created_time, last_edited_time, file_path, metadata, database_name FROM unified_content WHERE database_name = 'gmail'",
            "content_filters": ["avask"],
            "description": "emails containing avask"
        }},
        {{
            "sql_query": "SELECT page_id, title, created_time, last_edited_time, file_path, metadata, database_name FROM unified_content WHERE database_name = 'stories' AND (datetime(created_time) >= datetime('now', '-15 days') OR datetime(last_edited_time) >= datetime('now', '-15 days'))",
            "content_filters": [],
            "description": "last 15 days of stories"
        }}
    ]
}}

Query: "trass.gmail emails with avask and last 14 days of trass.journal and last 15 days of trass.stories"
Response:
{{
    "query_type": "multiple", 
    "queries": [
        {{
            "sql_query": "SELECT page_id, title, created_time, last_edited_time, file_path, metadata, database_name FROM unified_content WHERE workspace = 'trass' AND database_name = 'gmail'",
            "content_filters": ["avask"],
            "description": "trass.gmail emails with avask"
        }},
        {{
            "sql_query": "SELECT page_id, title, created_time, last_edited_time, file_path, metadata, database_name FROM unified_content WHERE workspace = 'trass' AND database_name = 'journal' AND (datetime(created_time) >= datetime('now', '-14 days') OR datetime(last_edited_time) >= datetime('now', '-14 days'))",
            "content_filters": [],
            "description": "last 14 days of trass.journal"
        }},
        {{
            "sql_query": "SELECT page_id, title, created_time, last_edited_time, file_path, metadata, database_name FROM unified_content WHERE workspace = 'trass' AND database_name = 'stories' AND (datetime(created_time) >= datetime('now', '-15 days') OR datetime(last_edited_time) >= datetime('now', '-15 days'))",
            "content_filters": [],
            "description": "last 15 days of trass.stories"
        }}
    ]
}}

EXAMPLES OF SINGLE QUERY RESPONSES:

Query: "recent journal entries"
Response:
{{
    "query_type": "single",
    "sql_query": "SELECT page_id, title, created_time, last_edited_time, file_path, metadata, database_name FROM unified_content WHERE database_name = 'journal' AND (datetime(created_time) >= datetime('now', '-7 days') OR datetime(last_edited_time) >= datetime('now', '-7 days'))",
    "content_filters": []
}}

Query: "published blog posts and completed stories"
Response:
{{
    "query_type": "single",
    "sql_query": "SELECT page_id, title, created_time, last_edited_time, file_path, metadata, database_name FROM unified_content WHERE ((database_name = 'cms' AND status = 'Published') OR (database_name = 'stories' AND status = 'Done'))",
    "content_filters": []
}}

DECISION LOGIC:
- Use "multiple" when different parts of the request need different content_filters
- Use "multiple" when combining time-based filters with content-based filters
- Use "single" when all databases can use the same filtering logic
- Always provide clear "description" fields for each query

User request: "{nl_prompt}"
"""

    try:
        # Get AI client and generate response
        client = get_ai_client()
        
        if isinstance(client, Anthropic):  # Anthropic
            response = client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=2000,
                messages=[{"role": "user", "content": system_prompt}],
                temperature=0.1
            )
            ai_response = response.content[0].text
        elif hasattr(client, 'chat'):  # OpenAI
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": system_prompt}],
                max_tokens=2000,
                temperature=0.1
            )
            ai_response = response.choices[0].message.content
        else:  # Gemini
            response = client.GenerativeModel('gemini-1.5-flash').generate_content(
                system_prompt,
                generation_config=genai.types.GenerationConfig(
                    max_output_tokens=2000,
                    temperature=0.1
                )
            )
            ai_response = response.text
        
        # Parse JSON response
        try:
            # Clean up response to extract JSON
            json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', ai_response, re.DOTALL)
            if json_match:
                parsed_response = json.loads(json_match.group())
            else:
                # Fallback parsing
                parsed_response = json.loads(ai_response)
        except json.JSONDecodeError:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Failed to parse AI response as JSON: {ai_response}")
            return {}
        
        # Handle both single and multiple query responses
        query_type = parsed_response.get('query_type', 'single')
        
        if query_type == 'multiple':
            queries = parsed_response.get('queries', [])
            if not queries:
                import logging
                logger = logging.getLogger(__name__)
                logger.error("No queries found in multiple query response")
                return {}
            
            # Display queries to user for debugging
            print(f"🔍 Generated {len(queries)} separate queries:")
            for i, query_info in enumerate(queries, 1):
                sql_query = query_info.get('sql_query', '')
                content_filters = query_info.get('content_filters', [])
                description = query_info.get('description', f'Query {i}')
                print(f"   {i}. {description}")
                print(f"      SQL: {sql_query}")
                if content_filters:
                    print(f"      Content Filters: {content_filters}")
            print()
            
            # Execute all queries and merge results
            return execute_multiple_queries(queries, workspace_for_db)
            
        else:  # single query
            sql_query = parsed_response.get('sql_query', '')
            content_filters = parsed_response.get('content_filters', [])
            
            # Display SQL query to user for debugging
            print(f"🔍 Generated SQL Query:")
            print(f"   {sql_query}")
            if content_filters:
                print(f"📝 Content Filters: {content_filters}")
            print()
            
            if not sql_query:
                import logging
                logger = logging.getLogger(__name__)
                logger.error("No SQL query generated")
                return {}
            
            # Execute single query
            return execute_single_query(sql_query, content_filters, workspace_for_db)
        
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error in natural language processing: {e}")
        return {}


def execute_multiple_queries(queries: List[Dict[str, Any]], workspace: str) -> Dict[str, List[Dict[str, Any]]]:
    """Execute multiple queries and merge their results by database name."""
    merged_results = {}
    
    for query_info in queries:
        sql_query = query_info.get('sql_query', '')
        content_filters = query_info.get('content_filters', [])
        
        if not sql_query:
            continue
            
        # Execute this query
        query_results = execute_single_query(sql_query, content_filters, workspace)
        
        # Merge results by database name
        for db_name, pages in query_results.items():
            if db_name not in merged_results:
                merged_results[db_name] = []
            merged_results[db_name].extend(pages)
    
    return merged_results


def execute_single_query(sql_query: str, content_filters: List[str], workspace: str) -> Dict[str, List[Dict[str, Any]]]:
    """Execute a single SQL query against hybrid storage and filter content."""
    try:
        # Get hybrid database path
        from promaia.storage.unified_query import get_query_interface
        query_interface = get_query_interface()
        
        with sqlite3.connect(query_interface.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(sql_query)
            results = cursor.fetchall()
            
            # Group results by database_name
            grouped_results = {}
            
            for row in results:
                # Assume columns: page_id, title, created_time, last_edited_time, file_path, metadata, database_name
                page_data = {
                    'page_id': row[0],
                    'title': row[1],
                    'created_time': row[2],
                    'last_edited_time': row[3],
                    'file_path': row[4],
                    'metadata': json.loads(row[5]) if row[5] else {},
                    'database_name': row[6]
                }
                
                # Apply content filters if any (now properly scoped to this query)
                if content_filters and not content_matches_filters(page_data, content_filters):
                    continue
                
                # Load actual file content for chat interface
                file_path = page_data.get('file_path', '')
                if file_path and os.path.exists(file_path):
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            file_content = f.read()
                            page_data['content'] = file_content
                            
                            # Extract title from content if title is empty
                            if not page_data.get('title') or page_data.get('title').strip() == '':
                                # Try to extract from "Name: ..." line in content
                                name_match = re.search(r'^Name:\s*(.+)$', file_content, re.MULTILINE)
                                if name_match:
                                    page_data['title'] = name_match.group(1).strip()
                                else:
                                    # Fallback to filename without extension
                                    filename = os.path.basename(file_path)
                                    page_data['title'] = os.path.splitext(filename)[0]
                    except Exception as e:
                        print(f"Warning: Could not read file {file_path}: {e}")
                        page_data['content'] = f"Error reading file: {e}"
                        # Still try to set title from filename
                        if not page_data.get('title') or page_data.get('title').strip() == '':
                            filename = os.path.basename(file_path)
                            page_data['title'] = os.path.splitext(filename)[0]
                else:
                    page_data['content'] = "File not found or path missing"
                
                # Group by database name
                db_name = page_data['database_name']
                if db_name not in grouped_results:
                    grouped_results[db_name] = []
                grouped_results[db_name].append(page_data)
            
            return grouped_results
            
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error executing query: {e}")
        return {}


def content_matches_filters(page_data: Dict[str, Any], filters: List[str]) -> bool:
    """Check if content matches the specified filters."""
    if not filters:
        return True
    
    # Search in multiple content sources
    searchable_content = []
    
    # 1. Search in title
    title = page_data.get('title', '')
    if title:
        searchable_content.append(title.lower())
    
    # 2. Search in metadata (especially for Gmail entries)
    metadata = page_data.get('metadata', {})
    if metadata:
        # Common searchable fields
        searchable_fields = ['subject', 'sender_email', 'sender_name', 'body', 'body_snippet', 'labels']
        for field in searchable_fields:
            if field in metadata and metadata[field]:
                searchable_content.append(str(metadata[field]).lower())
    
    # 3. Search in file content (fallback for markdown files)
    file_path = page_data.get('file_path', '')
    if file_path and os.path.exists(file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                file_content = f.read().lower()
                searchable_content.append(file_content)
        except Exception:
            pass  # Continue even if file reading fails
    
    # Check if any filter matches any content source
    all_content = ' '.join(searchable_content)
    for filter_term in filters:
        if filter_term.lower() in all_content:
            return True
    
    return False 