"""
Functions for creating and managing AI model system prompts.
"""
import os
import datetime
from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

def load_prompt_templates(prompt_file_path: str, default_system_prompt: str) -> Dict[str, str]:
    """Loads a prompt template from a file."""
    try:
        # Ensure the path is correct, potentially relative to the project root.
        with open(prompt_file_path, 'r', encoding='utf-8') as f:
            prompt_md_content = f.read()
        logger.debug(f"Loaded {prompt_file_path}: {len(prompt_md_content)} characters")
        return {"system_prompt": prompt_md_content, "project_instructions": ""}
    except FileNotFoundError:
        logger.error(f"Prompt file not found at {prompt_file_path}. Using default.")
        return {"system_prompt": default_system_prompt, "project_instructions": ""}
    except Exception as e:
        logger.error(f"Error loading {prompt_file_path}: {e}")
        return {"system_prompt": default_system_prompt.replace("not found", "could not be loaded"), "project_instructions": ""}

def create_system_prompt(
    multi_source_data: Dict[str, List[Dict[str, Any]]],
) -> str:
    """
    Create a system prompt that includes content from multiple data sources.
    """
    today = datetime.datetime.now()
    today_str = today.strftime("%Y-%m-%d")
    
    # Base prompt for multi-source mode
    base_prompt = f"""I am an AI assistant named Maia. Today's date is {today_str}. I have access to content from multiple data sources with different types of information. My tone is direct, casual, and very concise.

I serve as your journal, companion, and professional assistant. The purpose of this project is to support your growth to your highest potential, optimizing for holistic, long-term sustainable success as measured by:

- Financial freedom
- Professional growth
- Mental, emotional, and spiritual health
- Quality relationships

I will:
- Act as a reflective mirror to help you examine habits objectively
- Serve as a guide to identify blindspots
- Highlight opportunities for growth
- Provide feedback on areas for improvement, with sighted evidence

When referencing content, always specify which database it comes from and use the filename for context.
When discussing time periods (e.g. 'this week', 'today', 'yesterday'), use {today_str} as the reference point.

## Content from Multiple Data Sources ({sum(len(pages) for pages in multi_source_data.values())} total entries):
"""
    
    for database_name, pages in multi_source_data.items():
        base_prompt += f"\n### === {database_name.upper()} DATABASE ({len(pages)} entries) ===\n"
        
        # Add database-specific descriptions
        if 'journal' in database_name.lower():
            base_prompt += "These are personal journal entries and daily reflections:\n"
        elif 'cms' in database_name.lower():
            base_prompt += "These are blog posts and published content:\n"
        else:
            base_prompt += f"These are {database_name} entries:\n"
        
        if not pages:
            base_prompt += "No entries found for this database.\n"
        else:
            for page in pages:
                page_filename = page.get('filename', 'Unknown File')
                page_content = page.get('content', '')
                base_prompt += f"\n**{database_name}** entry (File: `{page_filename}`):\n{page_content}\n"

    return base_prompt 