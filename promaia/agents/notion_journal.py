"""
Write execution logs and notes to agent's Notion Journal database.
"""

import logging
from datetime import datetime
from typing import Optional
from promaia.agents.agent_config import load_agents as load_agents_from_json

logger = logging.getLogger(__name__)


async def write_journal_entry(
    agent_id: str,
    workspace: str,
    entry_type: str,
    content: str,
    execution_id: Optional[int] = None
):
    """
    Write entry to agent's Journal database.

    Args:
        agent_id: Agent ID (e.g., "grace")
        workspace: Workspace name
        entry_type: "Execution", "Note", or "Error"
        content: Entry content (text)
        execution_id: Optional execution ID for linking
    """
    from promaia.notion.client import get_client

    # Get agent config
    json_agents = load_agents_from_json()
    agent = None

    for a in json_agents:
        if hasattr(a, 'agent_id') and a.agent_id == agent_id:
            agent = a
            break

    if not agent or not hasattr(agent, 'journal_db_id') or not agent.journal_db_id:
        logger.warning(f"Agent '{agent_id}' has no Journal database, skipping journal entry")
        return

    try:
        client = get_client(workspace)

        # Create journal entry properties (NO Content property - that goes in page body)
        properties = {
            "Date": {"date": {"start": datetime.utcnow().isoformat()}},
            "Type": {"select": {"name": entry_type}}
        }

        # Add execution ID if provided
        if execution_id is not None:
            properties["Execution ID"] = {"number": execution_id}

        # Split content into chunks of ~2000 chars per paragraph block (Notion's limit)
        # This allows for much longer journal entries without truncation
        children = []
        chunk_size = 1900

        for i in range(0, len(content), chunk_size):
            chunk = content[i:i + chunk_size]
            children.append({
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [{"type": "text", "text": {"content": chunk}}]
                }
            })

        # Create page with content as body blocks
        await client.pages.create(
            parent={"database_id": agent.journal_db_id},
            properties=properties,
            children=children
        )

        logger.info(f"Wrote {entry_type} entry to journal for agent '{agent_id}'")

    except Exception as e:
        logger.error(f"Error writing journal entry: {e}")
        # Non-critical, don't raise


async def get_recent_journal_entries(
    agent_id: str,
    workspace: str,
    limit: int = 10
) -> list:
    """
    Get recent journal entries for an agent.

    Args:
        agent_id: Agent ID
        workspace: Workspace name
        limit: Maximum number of entries to return

    Returns:
        List of journal entry dictionaries
    """
    from promaia.notion.client import get_client

    # Get agent config
    json_agents = load_agents_from_json()
    agent = None

    for a in json_agents:
        if hasattr(a, 'agent_id') and a.agent_id == agent_id:
            agent = a
            break

    if not agent or not hasattr(agent, 'journal_db_id') or not agent.journal_db_id:
        return []

    try:
        client = get_client(workspace)

        # Query journal database
        response = await client.databases.query(
            database_id=agent.journal_db_id,
            sorts=[{"property": "Date", "direction": "descending"}],
            page_size=limit
        )

        entries = []
        for page in response["results"]:
            props = page["properties"]

            # Read content from page blocks instead of Content property
            page_id = page["id"]
            content = ""
            try:
                # Fetch page blocks to get content
                blocks_response = await client.blocks.children.list(block_id=page_id)
                for block in blocks_response.get("results", []):
                    if block["type"] == "paragraph":
                        paragraph = block.get("paragraph", {})
                        rich_text = paragraph.get("rich_text", [])
                        for text_obj in rich_text:
                            content += text_obj.get("text", {}).get("content", "")
            except Exception as e:
                logger.warning(f"Could not load blocks for journal entry {page_id}: {e}")

            entry = {
                "date": props.get("Date", {}).get("date", {}).get("start"),
                "type": props.get("Type", {}).get("select", {}).get("name"),
                "content": content,
                "execution_id": props.get("Execution ID", {}).get("number")
            }

            entries.append(entry)

        return entries

    except Exception as e:
        logger.error(f"Error loading journal entries: {e}")
        return []
