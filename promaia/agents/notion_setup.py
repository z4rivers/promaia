"""
Setup and creation of agent structures in Notion.

This module handles:
- Auto-creating Agents database at workspace root
- Creating agent pages with substructure (System Prompt, Instructions, Journal)
- Converting markdown prompts to Notion blocks
"""

import asyncio
import logging
import webbrowser
from typing import Optional, List, Dict, Any
from rich.console import Console

logger = logging.getLogger(__name__)
console = Console()


async def ensure_agents_database_exists(workspace: str) -> str:
    """
    Ensure Agents database exists in workspace, create if not.

    Args:
        workspace: Workspace name

    Returns:
        Database ID of Agents database
    """
    from promaia.config.workspaces import get_workspace_manager
    from promaia.notion.client import get_client

    workspace_mgr = get_workspace_manager()
    workspace_config = workspace_mgr.get_workspace(workspace)

    # Check if already exists
    if workspace_config and workspace_config.config.get("agents_database_id"):
        return workspace_config.config["agents_database_id"]

    # Need to create it
    console.print("\n📊 Setting up Agents database...", style="cyan")
    console.print("   (This only happens once per workspace)", style="dim")

    client = get_client(workspace)

    try:
        # Create database at workspace root
        database = await client.databases.create({
            "parent": {"type": "workspace", "workspace": True},
            "title": [{"text": {"content": "Agents"}}],
            "properties": {
                "Name": {"title": {}},
                "Agent ID": {"rich_text": {}},
                "Status": {
                    "select": {
                        "options": [
                            {"name": "Active", "color": "green"},
                            {"name": "Paused", "color": "yellow"},
                            {"name": "Archived", "color": "gray"}
                        ]
                    }
                },
                "Last Run": {"date": {}}
            }
        })

        db_id = database["id"]

        # Save to workspace config
        if not workspace_config.config:
            workspace_config.config = {}
        workspace_config.config["agents_database_id"] = db_id
        workspace_mgr.save_workspace(workspace, workspace_config)

        console.print(f"\n✅ Agents database created!", style="green")
        console.print(f"   https://notion.so/{db_id}", style="dim")

        # Open in browser
        webbrowser.open(f"https://notion.so/{db_id}")

        return db_id

    except Exception as e:
        logger.error(f"Failed to create Agents database: {e}")
        console.print(f"\n❌ Error creating Agents database: {e}", style="red")
        raise


async def create_agent_in_notion(agent_config, workspace: str) -> str:
    """
    Create complete agent page structure in Notion.

    Creates:
    - Agent page in Agents database
    - System Prompt subpage
    - Instructions sub-database
    - Journal sub-database

    Args:
        agent_config: AgentConfig object
        workspace: Workspace name

    Returns:
        Agent page ID
    """
    from promaia.notion.client import get_client

    agents_db_id = await ensure_agents_database_exists(workspace)
    client = get_client(workspace)

    console.print(f"\n⏳ Creating agent structure in Notion...", style="cyan")

    try:
        # 1. Create agent PAGE in Agents database
        agent_page = await client.pages.create({
            "parent": {"database_id": agents_db_id},
            "properties": {
                "Name": {"title": [{"text": {"content": agent_config.name}}]},
                "Agent ID": {"rich_text": [{"text": {"content": agent_config.agent_id}}]},
                "Status": {"select": {"name": "Active"}}
            }
        })

        agent_page_id = agent_page["id"]
        console.print(f"   ✓ Created agent page", style="dim")

        # 2. Create "System Prompt" subpage
        system_prompt_page = await client.pages.create({
            "parent": {"page_id": agent_page_id},
            "properties": {
                "title": {"title": [{"text": {"content": "System Prompt"}}]}
            }
        })

        # Add prompt content as blocks
        prompt_blocks = markdown_to_notion_blocks(agent_config.prompt_file)
        await client.blocks.children.append(
            block_id=system_prompt_page["id"],
            children=prompt_blocks[:100]  # Notion limit: 100 blocks per request
        )
        console.print(f"   ✓ Added system prompt", style="dim")

        # 3. Create "Instructions" sub-database
        instructions_db = await client.databases.create({
            "parent": {"page_id": agent_page_id},
            "title": [{"text": {"content": "Instructions"}}],
            "properties": {
                "Name": {"title": {}},
                "Category": {
                    "select": {
                        "options": [
                            {"name": "Procedure", "color": "blue"},
                            {"name": "Template", "color": "green"},
                            {"name": "Reference", "color": "gray"}
                        ]
                    }
                },
                "Content": {"rich_text": {}}
            }
        })
        console.print(f"   ✓ Created Instructions database", style="dim")

        # 4. Create "Journal" sub-database
        journal_db = await client.databases.create({
            "parent": {"page_id": agent_page_id},
            "title": [{"text": {"content": "Journal"}}],
            "properties": {
                "Date": {"date": {}},
                "Type": {
                    "select": {
                        "options": [
                            {"name": "Execution", "color": "blue"},
                            {"name": "Note", "color": "green"},
                            {"name": "Error", "color": "red"}
                        ]
                    }
                },
                "Content": {"rich_text": {}},
                "Execution ID": {"number": {}}
            }
        })
        console.print(f"   ✓ Created Journal database", style="dim")

        # Store IDs in agent config
        agent_config.system_prompt_page_id = system_prompt_page["id"]
        agent_config.instructions_db_id = instructions_db["id"]
        agent_config.journal_db_id = journal_db["id"]

        console.print(f"\n✅ Agent structure created in Notion!", style="green")

        return agent_page_id

    except Exception as e:
        logger.error(f"Failed to create agent structure: {e}")
        console.print(f"\n❌ Error creating agent structure: {e}", style="red")
        import traceback
        traceback.print_exc()
        raise


def markdown_to_notion_blocks(markdown: str) -> List[Dict[str, Any]]:
    """
    Convert markdown to Notion block format.

    Args:
        markdown: Markdown content

    Returns:
        List of Notion block objects
    """
    blocks = []
    lines = markdown.split('\n')

    for line in lines:
        line = line.rstrip()

        if not line:
            # Skip empty lines
            continue

        # Headings
        if line.startswith('### '):
            blocks.append({
                "type": "heading_3",
                "heading_3": {"rich_text": [{"text": {"content": line[4:]}}]}
            })
        elif line.startswith('## '):
            blocks.append({
                "type": "heading_2",
                "heading_2": {"rich_text": [{"text": {"content": line[3:]}}]}
            })
        elif line.startswith('# '):
            blocks.append({
                "type": "heading_1",
                "heading_1": {"rich_text": [{"text": {"content": line[2:]}}]}
            })
        # Lists
        elif line.startswith('- ') or line.startswith('* '):
            blocks.append({
                "type": "bulleted_list_item",
                "bulleted_list_item": {"rich_text": [{"text": {"content": line[2:]}}]}
            })
        elif line.strip() and line.lstrip()[0].isdigit() and '. ' in line:
            # Numbered list
            content = line.split('. ', 1)[1] if '. ' in line else line
            blocks.append({
                "type": "numbered_list_item",
                "numbered_list_item": {"rich_text": [{"text": {"content": content}}]}
            })
        # Regular paragraph
        else:
            # Truncate to Notion's limit (2000 chars per rich_text)
            content = line[:2000] if len(line) > 2000 else line
            blocks.append({
                "type": "paragraph",
                "paragraph": {"rich_text": [{"text": {"content": content}}]}
            })

    return blocks


def generate_agent_id(name: str, existing_agents: List[Any]) -> str:
    """
    Generate unique agent ID from name.

    Args:
        name: Agent name (e.g., "Grace", "Daily Summary")
        existing_agents: List of existing AgentConfig objects

    Returns:
        Unique agent ID (e.g., "grace", "daily-summary", "grace-2")
    """
    # Convert to lowercase, replace spaces/underscores with hyphens
    agent_id = name.lower().replace(' ', '-').replace('_', '-')
    # Remove any non-alphanumeric except hyphens
    import re
    agent_id = re.sub(r'[^a-z0-9-]', '', agent_id)

    # Get existing IDs
    existing_ids = {a.agent_id for a in existing_agents if hasattr(a, 'agent_id') and a.agent_id}

    # Check uniqueness
    if agent_id not in existing_ids:
        return agent_id

    # Add numeric suffix
    suffix = 2
    while f"{agent_id}-{suffix}" in existing_ids:
        suffix += 1

    return f"{agent_id}-{suffix}"
