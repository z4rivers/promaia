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
) -> str:
    """
    Create a system prompt that includes content from multiple data sources.

    Args:
        multi_source_data: Dict mapping database names to lists of page data
        mcp_tools_info: Optional formatted MCP tools information
        include_query_tools: Whether to include built-in query tools (default: True)
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

    # Append context data
    base_prompt += format_context_data(multi_source_data, mcp_tools_info)

    return base_prompt


def _is_discord_database(database_name: str) -> bool:
    """Check if a database is a Discord source based on its name or content."""
    return 'discord' in database_name.lower() or database_name.lower().endswith('.ds')


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

#### 1. query_sql
**Description**: Query databases using natural language. The system will convert your query to SQL and retrieve relevant content.

**When to use**: When you need to find specific information based on content, properties, or dates (e.g., "find emails from Federico about the product launch", "journal entries from last month about meetings")

**Parameters**:
- `query`* (string): Natural language description of what you're looking for
- `workspace` (string): Optional workspace name to search in (defaults to current workspace)
- `max_results` (integer): Optional maximum number of results to return (default: 50)

**Example**:
```
<tool_call>
  <tool_name>query_sql</tool_name>
  <parameters>
    <query>find emails from Federico about product launch</query>
    <workspace>default</workspace>
    <max_results>20</max_results>
  </parameters>
</tool_call>
```

#### 2. query_vector
**Description**: Search databases using semantic similarity. Finds content that is conceptually similar to your search text.

**When to use**: When you need to find information based on meaning rather than exact terms (e.g., finding discussions about a topic even if different words were used)

**Parameters**:
- `query`* (string): Text to search for semantically similar content
- `workspace` (string): Optional workspace name to search in (defaults to current workspace)
- `top_k` (integer): Maximum number of results to return (default: 20)
- `min_similarity` (float): Minimum similarity threshold 0.0-1.0 (default: 0.75)

**Example**:
```
<tool_call>
  <tool_name>query_vector</tool_name>
  <parameters>
    <query>international expansion strategy</query>
    <top_k>15</top_k>
    <min_similarity>0.8</min_similarity>
  </parameters>
</tool_call>
```

#### 3. query_source
**Description**: Load content directly from specific databases and time ranges. Most direct way to add context.

**When to use**: When you know exactly which database and time range you need (e.g., "last 7 days of Gmail", "30 days of journal entries")

**Parameters**:
- `source`* (string): Database specification in format "database_name:days" (e.g., "gmail:7", "journal:30")
- `workspace` (string): Optional workspace name (defaults to current workspace)
- `filters` (object): Optional property filters to apply

**Example**:
```
<tool_call>
  <tool_name>query_source</tool_name>
  <parameters>
    <source>gmail:7</source>
  </parameters>
</tool_call>
```

### Important Notes About Query Tools

1. **Permission Required**: When you use a query tool, the user will be asked to approve the query before it executes. They can approve (y), modify (m), or decline (n).

2. **Context Updates**: After a query executes, the results are merged into your context. You'll receive a summary of what was loaded.

3. **Iterative Querying**: You can make multiple query tool calls if you need to refine or expand context. However, be judicious - each query requires user approval and uses tokens.

4. **Deduplication**: If a query returns content already in context, it will be deduplicated automatically. You won't see duplicate entries.

5. **When to Query**:
   - User asks about something not in your current context
   - User's question would benefit from more recent or more specific information
   - You notice you're missing key information to give a complete answer

6. **When NOT to Query**:
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
  </parameters>
</tool_call>

[User approves, context is loaded]

AI: Based on the emails I found, Federico mentioned...
```
"""

    return tools_section