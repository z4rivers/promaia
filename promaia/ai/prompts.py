"""
Functions for creating and managing AI model system prompts.
"""
import os
import datetime
from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

PROMPT_FILE_PATH = "prompts/prompt.md"

def create_system_prompt(
    multi_source_data: Dict[str, List[Dict[str, Any]]],
) -> str:
    """
    Create a system prompt that includes content from multiple data sources.
    """
    today = datetime.datetime.now()
    today_str = today.strftime("%Y-%m-%d")

    try:
        with open(PROMPT_FILE_PATH, 'r', encoding='utf-8') as f:
            base_prompt = f.read()
        logger.debug(f"Loaded system prompt from {PROMPT_FILE_PATH}")
    except FileNotFoundError:
        logger.error(f"System prompt file not found at {PROMPT_FILE_PATH}. Using a fallback prompt.")
        base_prompt = "You are a helpful AI assistant. Today's date is {today_date}."
    
    base_prompt = base_prompt.replace("{today_date}", today_str)
    
    # Append data sources
    base_prompt += f"\n\n## Context ({sum(len(pages) for pages in multi_source_data.values())} total entries):"
    
    for database_name, pages in multi_source_data.items():
        base_prompt += f"\n\n### === {database_name.upper()} DATABASE ({len(pages)} entries) ===\n"
        
        # Add database-specific descriptions
        if 'journal' in database_name.lower():
            base_prompt += "These are personal journal entries and daily reflections:\n"
        elif 'cms' in database_name.lower():
            base_prompt += "These are blog posts and published content:\n"
        elif _is_discord_database(database_name):
            base_prompt += "These are Discord server messages:\n"
        else:
            base_prompt += f"These are {database_name} entries:\n"
        
        if not pages:
            base_prompt += "No entries found for this database.\n"
        else:
            if _is_discord_database(database_name):
                # Group Discord messages by channel
                channels = {}
                for page in pages:
                    channel_name = "unknown_channel"
                    if page.get('metadata') and page['metadata'].get('discord_channel_name'):
                        channel_name = page['metadata']['discord_channel_name']
                    
                    if channel_name not in channels:
                        channels[channel_name] = []
                    channels[channel_name].append(page)
                
                # Format content with channel subheadings
                for channel_name, channel_pages in channels.items():
                    base_prompt += f"\n#### Channel: #{channel_name}\n"
                    for page in channel_pages:
                        page_filename = page.get('filename', 'Unknown File')
                        page_content = page.get('content', '')
                        base_prompt += f"\n**{page_filename}**:\n{page_content}\n"
            else:
                for page in pages:
                    page_filename = (page.get('filename') or 
                                   page.get('title') or 
                                   page.get('name') or 
                                   'Unknown File')
                    page_content = page.get('content', '')
                    base_prompt += f"\n**{database_name}** entry (File: `{page_filename}`):\n{page_content}\n"

    return base_prompt


def _is_discord_database(database_name: str) -> bool:
    """Check if a database is a Discord source based on its name or content."""
    return 'discord' in database_name.lower() or database_name.lower().endswith('.ds')