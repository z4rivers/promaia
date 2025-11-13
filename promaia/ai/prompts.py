"""
Functions for creating and managing AI model system prompts.
"""
import os
import datetime
from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

PROMPT_FILE_PATH = "prompts/prompt.md"
ARTIFACT_GUIDELINES_PATH = "prompts/artifact_guidelines.md"

def format_context_data(
    multi_source_data: Dict[str, List[Dict[str, Any]]],
    mcp_tools_info: Optional[str] = None,
) -> str:
    """
    Format context data from multiple sources into a string.

    This can be appended to any base prompt to provide context.
    """
    if not multi_source_data and not mcp_tools_info:
        return ""

    context_str = ""

    if multi_source_data:
        # Append data sources
        context_str += f"\n\n## Context ({sum(len(pages) for pages in multi_source_data.values())} total entries):"
    
        for database_name, pages in multi_source_data.items():
            context_str += f"\n\n### === {database_name.upper()} DATABASE ({len(pages)} entries) ===\n"

            # Add database-specific descriptions
            if 'journal' in database_name.lower():
                context_str += "These are personal journal entries and daily reflections:\n"
            elif 'cms' in database_name.lower():
                context_str += "These are blog posts and published content:\n"
            elif _is_discord_database(database_name):
                context_str += "These are Discord server messages:\n"
            else:
                context_str += f"These are {database_name} entries:\n"

            if not pages:
                context_str += "No entries found for this database.\n"
            else:
                if _is_discord_database(database_name):
                    # Group Discord messages by channel
                    channels = {}
                    for page in pages:
                        channel_name = "unknown_channel"

                        # Handle metadata that might be a JSON string or dict
                        metadata = page.get('metadata')
                        if metadata:
                            if isinstance(metadata, str):
                                try:
                                    import json
                                    metadata = json.loads(metadata)
                                except (json.JSONDecodeError, TypeError):
                                    metadata = {}

                            # Try multiple ways to get channel name
                            if metadata.get('discord_channel_name'):
                                channel_name = metadata['discord_channel_name']
                            elif metadata.get('channel_name'):
                                # Remove # prefix if present
                                channel_name = metadata['channel_name'].lstrip('#')
                            elif metadata.get('properties', {}).get('channel_name'):
                                channel_name = metadata['properties']['channel_name'].lstrip('#')

                        if channel_name not in channels:
                            channels[channel_name] = []
                        channels[channel_name].append(page)

                    # Format content with channel subheadings
                    for channel_name, channel_pages in channels.items():
                        context_str += f"\n#### Channel: #{channel_name}\n"
                        for page in channel_pages:
                            page_filename = page.get('filename', 'Unknown File')
                            page_content = page.get('content', '')

                            # Extract timestamp and author from metadata for minimal format
                            metadata = page.get('metadata')
                            timestamp_display = "unknown_time"
                            author_display = "unknown_author"

                            if metadata:
                                if isinstance(metadata, str):
                                    try:
                                        import json
                                        metadata = json.loads(metadata)
                                    except (json.JSONDecodeError, TypeError):
                                        metadata = {}

                                # Get timestamp in readable format
                                timestamp_str = metadata.get('timestamp') or metadata.get('created_time')
                                if timestamp_str:
                                    try:
                                        dt = datetime.datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                                        timestamp_display = dt.strftime("%Y-%m-%d %H:%M:%S")
                                    except ValueError:
                                        pass

                                # Get author name (try multiple field names)
                                author_display = (metadata.get('author_name') or
                                                metadata.get('author') or
                                                metadata.get('properties', {}).get('author_name') or
                                                'unknown_author')

                            # Use minimal format: **`timestamp author #channel filename`**
                            context_str += f"\n**`{timestamp_display}  {author_display}  #{channel_name}  {page_filename}`**\n\n{page_content}\n"
                else:
                    for page in pages:
                        page_filename = (page.get('filename') or
                                       page.get('title') or
                                       page.get('name') or
                                       'Unknown File')
                        page_content = page.get('content', '')
                        context_str += f"\n**{database_name}** entry (File: `{page_filename}`):\n{page_content}\n"

    # Add MCP tools information if provided
    if mcp_tools_info:
        context_str += f"\n\n{mcp_tools_info}"

    return context_str


def create_system_prompt(
    multi_source_data: Dict[str, List[Dict[str, Any]]],
    mcp_tools_info: Optional[str] = None,
    include_query_tools: bool = True,
    workspace: Optional[str] = None,
) -> str:
    """
    Create a system prompt that includes content from multiple data sources.

    Args:
        multi_source_data: Dict mapping database names to lists of page data
        mcp_tools_info: Optional formatted MCP tools information
        include_query_tools: Whether to include built-in query tools (default: True)
        workspace: Current workspace for database preview (default: None)
    """
    today = datetime.datetime.now()
    today_str = today.strftime("%Y-%m-%d")
    current_time_str = today.strftime("%H:%M")

    try:
        with open(PROMPT_FILE_PATH, 'r', encoding='utf-8') as f:
            base_prompt = f.read()
        logger.debug(f"Loaded system prompt from {PROMPT_FILE_PATH}")
    except FileNotFoundError:
        logger.error(f"System prompt file not found at {PROMPT_FILE_PATH}. Using a fallback prompt.")
        base_prompt = "You are a helpful AI assistant. Today's date is {today_date}."

    base_prompt = base_prompt.replace("{today_date}", today_str)
    base_prompt = base_prompt.replace("{current_time}", current_time_str)

    # Load artifact guidelines
    try:
        with open(ARTIFACT_GUIDELINES_PATH, 'r', encoding='utf-8') as f:
            artifact_guidelines = f.read()
        base_prompt += "\n\n" + artifact_guidelines
        logger.debug(f"Loaded artifact guidelines from {ARTIFACT_GUIDELINES_PATH}")
    except FileNotFoundError:
        logger.warning(f"Artifact guidelines file not found at {ARTIFACT_GUIDELINES_PATH}. Continuing without them.")

    # Add query tools if enabled
    if include_query_tools:
        base_prompt += "\n\n" + format_query_tools_for_prompt()

        # Add database preview (the "map on the wall") showing what data sources exist
        # Exclude databases already in loaded context to avoid duplication
        loaded_databases = list(multi_source_data.keys())
        db_preview = generate_database_preview(workspace=workspace, exclude_databases=loaded_databases)
        if db_preview:
            base_prompt += "\n\n" + db_preview

    # Append context data
    base_prompt += format_context_data(multi_source_data, mcp_tools_info)

    return base_prompt


def _is_discord_database(database_name: str) -> bool:
    """Check if a database is a Discord source based on its name or content."""
    return 'discord' in database_name.lower() or database_name.lower().endswith('.ds')


def generate_database_preview(workspace: Optional[str] = None, exclude_databases: Optional[List[str]] = None) -> str:
    """
    Generate a preview/map of available databases with sample content.

    Similar to what the SQL query AI sees, this gives the chat AI a "heads up display"
    showing what data sources exist and what they contain.

    Args:
        workspace: Optional workspace to filter databases (None for all)
        exclude_databases: List of database names already in loaded context (to avoid duplication)

    Returns:
        Formatted database preview string with samples
    """
    import sqlite3
    import json
    from datetime import datetime

    db_path = "data/hybrid_metadata.db"

    if exclude_databases is None:
        exclude_databases = []

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Get list of all databases in workspace
        if workspace:
            cursor.execute("""
                SELECT DISTINCT database_name, workspace
                FROM unified_content
                WHERE workspace = ?
                ORDER BY database_name
            """, (workspace,))
        else:
            cursor.execute("""
                SELECT DISTINCT database_name, workspace
                FROM unified_content
                ORDER BY workspace, database_name
            """)

        databases = cursor.fetchall()

        if not databases:
            return ""

        preview = "## Available Data Sources"
        if workspace:
            preview += f" (Workspace: {workspace})"
        preview += "\n\n"

        for db_name, db_workspace in databases:
            # Skip if already in loaded context
            if db_name in exclude_databases:
                continue

            # Get count
            cursor.execute("""
                SELECT COUNT(*)
                FROM unified_content
                WHERE database_name = ? AND workspace = ?
            """, (db_name, db_workspace))
            count = cursor.fetchone()[0]

            # Get date range
            cursor.execute("""
                SELECT MIN(created_time), MAX(created_time)
                FROM unified_content
                WHERE database_name = ? AND workspace = ?
                AND created_time IS NOT NULL
            """, (db_name, db_workspace))
            date_range = cursor.fetchone()
            date_min = date_range[0] if date_range[0] else "unknown"
            date_max = date_range[1] if date_range[1] else "unknown"

            # Format dates
            if date_min != "unknown":
                try:
                    date_min = datetime.fromisoformat(date_min.replace('Z', '+00:00')).strftime("%Y-%m-%d")
                except:
                    date_min = "unknown"
            if date_max != "unknown":
                try:
                    date_max = datetime.fromisoformat(date_max.replace('Z', '+00:00')).strftime("%Y-%m-%d")
                except:
                    date_max = "unknown"

            # Get 3 most recent samples
            cursor.execute("""
                SELECT page_id, title, created_time, metadata
                FROM unified_content
                WHERE database_name = ? AND workspace = ?
                ORDER BY created_time DESC
                LIMIT 3
            """, (db_name, db_workspace))
            samples = cursor.fetchall()

            # Determine emoji based on database type
            if 'gmail' in db_name.lower():
                emoji = "📧"
            elif 'discord' in db_name.lower() or db_name.endswith('.ds'):
                emoji = "💬"
            elif 'journal' in db_name.lower():
                emoji = "📓"
            elif 'stories' in db_name.lower() or 'cms' in db_name.lower():
                emoji = "📝"
            else:
                emoji = "📁"

            # Build database section
            preview += f"{emoji} **{db_name}** ({count:,} entries"
            if date_min != "unknown" and date_max != "unknown":
                preview += f" | {date_min} to {date_max}"
            preview += ")\n"

            # Add sample entries
            if samples:
                preview += "\n  Recent examples:\n"
                for i, (page_id, title, created, metadata_str) in enumerate(samples, 1):
                    # Truncate title
                    title_display = title[:80] + "..." if title and len(title) > 80 else (title or "Untitled")

                    # Format date
                    date_display = "unknown"
                    if created:
                        try:
                            date_display = datetime.fromisoformat(created.replace('Z', '+00:00')).strftime("%b %d, %Y")
                        except:
                            pass

                    preview += f"  {i}. \"{title_display}\" ({date_display})\n"

                    # Parse metadata for key properties
                    if metadata_str:
                        try:
                            metadata = json.loads(metadata_str) if isinstance(metadata_str, str) else metadata_str
                            properties = metadata.get('properties', {})

                            # Show top 3 interesting properties
                            prop_display = []
                            interesting_props = ['status', 'sender', 'author', 'tags', 'epic', 'channel', 'mood']

                            for prop_name in interesting_props:
                                if prop_name in properties:
                                    prop_value = properties[prop_name]
                                    # Handle different property value formats
                                    if isinstance(prop_value, dict):
                                        # Notion property format
                                        if 'select' in prop_value and prop_value['select']:
                                            prop_display.append(f"{prop_name}: {prop_value['select']['name']}")
                                        elif 'multi_select' in prop_value and prop_value['multi_select']:
                                            tags = [t['name'] for t in prop_value['multi_select'][:2]]
                                            prop_display.append(f"{prop_name}: {', '.join(tags)}")
                                    elif isinstance(prop_value, str) and prop_value:
                                        prop_display.append(f"{prop_name}: {prop_value}")

                                if len(prop_display) >= 3:
                                    break

                            if prop_display:
                                preview += f"     {' | '.join(prop_display)}\n"

                        except:
                            pass  # Skip metadata parsing errors

                preview += "\n"
            else:
                preview += "  (No recent entries)\n\n"

        conn.close()

        if not preview.strip().endswith("## Available Data Sources"):
            return preview
        else:
            return ""  # No databases found

    except Exception as e:
        logger.error(f"Error generating database preview: {e}")
        return ""


def format_query_tools_for_prompt() -> str:
    """
    Format built-in query tools for inclusion in system prompt.

    These tools allow the AI to query and load additional context as needed.

    Returns:
        Formatted query tools information
    """
    tools_section = """## Built-in Query Tools

You have access to built-in tools that allow you to query and load additional context from the user's databases. Use these tools when you need more information to answer the user's question effectively.

### Available Query Tools

**Quick Selection Guide**:
- User says "I think", "something like", "might be" → Use **query_vector**
- Searching by fuzzy/uncertain name or title → Use **query_vector**
- Need specific property filters (sender, date, exact terms) → Use **query_sql**
- Know exact database + time range needed → Use **query_source**

#### 1. query_sql
**Description**: Query databases using natural language. The system will convert your query to SQL and retrieve relevant content.

**When to use**:
- Filtering by specific properties (sender name, date ranges, database fields)
- Multiple structured filters (from X about Y in last Z days)
- Exact text terms the user explicitly mentioned
- **NOT for fuzzy/uncertain names or titles** - use query_vector instead if user says "I think", "something like", or you're unsure of exact wording

**Parameters**:
- `query`* (string): Natural language description of the SQL query itself, specifying workspace, database, search terms, and time filters. Format: "{workspace} {database} from/with/about {search_terms} {time_filter}". Examples: "trass gmail from federico about launch last 30 days", "default stories with status done from last week", "trass journal with term meeting last month"
- `reasoning`* (string): **REQUIRED** - Explain: (1) Why you need this information (what's missing from current context), (2) What you expect to find, (3) Why you formulated the query this way
- `workspace` (string): Optional workspace name to search in (defaults to current workspace if not in query)
- `max_results` (integer): Optional maximum number of results to return (default: 50)

**Example**:
```
<tool_call>
  <tool_name>query_sql</tool_name>
  <parameters>
    <query>trass gmail from federico about launch last 30 days</query>
    <reasoning>User asked "What did Federico say about the product launch?" My current context doesn't contain any emails from Federico. I'm querying the gmail database because Federico communicates via email. I'm searching for messages where Federico is the sender AND the content mentions "product launch" or "launch" from the last 30 days. I expect to find 5-15 recent emails with his feedback, concerns, and updates about the launch timeline and strategy.</reasoning>
    <max_results>20</max_results>
  </parameters>
</tool_call>
```

#### 2. query_vector
**Description**: Search databases using semantic similarity. Finds content that is conceptually similar to your search text.

**When to use**:
- **Uncertain or fuzzy names/titles** (user says "I think", "something like", "might be called")
- Finding content by semantic meaning rather than exact keywords
- When different wording might be used for the same concept
- Searching for themes, topics, or concepts across content
- **PREFER this over query_sql when names/titles are approximate**

**Parameters**:
- `query`* (string): Text to search for semantically similar content
- `reasoning`* (string): **REQUIRED** - Explain: (1) Why you need this information (what's missing from current context), (2) What you expect to find, (3) Why semantic search is appropriate for this query
- `workspace` (string): Optional workspace name to search in (defaults to current workspace)
- `top_k` (integer): Maximum number of results to return (default: 20)
- `min_similarity` (float): Minimum similarity threshold 0.0-1.0 (default: 0.65). Use 0.5-0.6 for very fuzzy title searches

**Examples**:
```
<tool_call>
  <tool_name>query_vector</tool_name>
  <parameters>
    <query>technical assets promo code dashboard</query>
    <reasoning>User said "I think it's in the technical assets trass story" - the phrase "I think" indicates uncertainty about the exact title. Using semantic search will find stories with similar titles like "Technical Assets", "Tech Assets", "Technical Resources", etc., even if not exact matches. I expect to find 1-3 stories with URLs, dashboards, or technical documentation links.</reasoning>
    <top_k>10</top_k>
    <min_similarity>0.55</min_similarity>
  </parameters>
</tool_call>
```

```
<tool_call>
  <tool_name>query_vector</tool_name>
  <parameters>
    <query>international expansion strategy</query>
    <reasoning>User asked about our plans for international markets. I'm using semantic search because the relevant content might use different terminology like "global growth", "overseas markets", "foreign markets", etc. I expect to find 10-20 documents discussing market expansion and geographic strategy.</reasoning>
    <top_k>15</top_k>
  </parameters>
</tool_call>
```

#### 3. query_source
**Description**: Load content directly from specific databases and time ranges. Most direct way to add context.

**When to use**: When you know exactly which database and time range you need (e.g., "last 7 days of Gmail", "30 days of journal entries")

**Parameters**:
- `source`* (string): Database specification in format "database_name:days" (e.g., "gmail:7", "journal:30")
- `reasoning`* (string): **REQUIRED** - Explain: (1) Why you need this specific database (what information is it expected to contain), (2) Why you chose this time range, (3) What you expect to find
- `workspace` (string): Optional workspace name (defaults to current workspace)
- `filters` (object): Optional property filters to apply

**Example**:
```
<tool_call>
  <tool_name>query_source</tool_name>
  <parameters>
    <source>gmail:7</source>
    <reasoning>User asked "Any important emails this week?" My context doesn't have recent email data. I'm loading the last 7 days of gmail because the user specifically said "this week" and emails are the communication channel where important updates come through. I expect to find 20-50 recent emails including project updates, meeting invitations, and urgent requests that need the user's attention.</reasoning>
  </parameters>
</tool_call>
```

### Important Notes About Query Tools

1. **Reasoning is REQUIRED**: Every query tool call MUST include a `reasoning` parameter that explains:
   - WHY you need this information (what's missing from your current context)
   - WHAT you expect to find
   - HOW/WHY you formulated the query this way

   The reasoning will be shown to the user during approval, so be specific and clear.

2. **Permission Required**: When you use a query tool, the user will be asked to approve the query before it executes. They can approve (y), modify (m), or decline (n). Your reasoning helps them make this decision.

3. **Context Updates**: After a query executes, the results are merged into your context. You'll receive a summary of what was loaded.

4. **Iterative Querying**: You can make multiple query tool calls if you need to refine or expand context. However, be judicious - each query requires user approval and uses tokens.

5. **Deduplication**: If a query returns content already in context, it will be deduplicated automatically. You won't see duplicate entries.

6. **When to Query**:
   - User asks about something not in your current context
   - User's question would benefit from more recent or more specific information
   - You notice you're missing key information to give a complete answer

7. **When NOT to Query**:
   - The answer is already in your context
   - The question doesn't require database content (general knowledge questions)
   - You're unsure what to query for (ask the user to clarify first)

### Query Tool Usage Pattern

The recommended pattern for using query tools is:

1. **Assess**: Determine if you have sufficient context to answer the user's question
2. **Decide**: If not, determine what specific information you need
3. **Query**: Use the appropriate query tool to request that information
4. **Wait**: Wait for the tool result and updated context
5. **Reassess**: Check if you now have enough information, or if you need to query again
6. **Answer**: Once you have sufficient context, provide your answer

**Example conversation flow**:
```
User: "What did Federico say about the product launch?"

AI: I need to search for emails from Federico about the product launch.

<tool_call>
  <tool_name>query_sql</tool_name>
  <parameters>
    <query>emails from Federico about product launch</query>
    <reasoning>User asked what Federico said about the product launch. My current context doesn't contain any emails from Federico. I'm querying the gmail database because that's where Federico's communications would be stored. I'm searching for messages where Federico is the sender and the content mentions "product launch" or "launch". I expect to find several emails with his feedback, questions, or updates about the launch.</reasoning>
  </parameters>
</tool_call>

[User sees reasoning, approves, context is loaded]

AI: Based on the emails I found, Federico mentioned...
```
"""

    return tools_section