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
            # Check if this is Discord content and use special formatting
            if _is_discord_database(database_name):
                base_prompt += _format_discord_content_for_prompt(database_name, pages)
            else:
                for page in pages:
                    # Try multiple title sources for compatibility
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


def _format_discord_content_for_prompt(database_name: str, pages: List[Dict[str, Any]]) -> str:
    """Format Discord messages in an efficient, grouped format for the system prompt."""
    if not pages:
        return ""
    
    # Parse Discord messages and group by channel
    channels = {}
    
    for page in pages:
        try:
            content = page.get('content', '')
            
            # Extract channel and metadata from Discord message content
            channel_info = _extract_discord_message_info(content)
            if not channel_info:
                continue
            
            channel_name = channel_info['channel']
            author = channel_info['author']
            timestamp = channel_info['timestamp']
            message_content = channel_info['content']
            attachments = channel_info.get('attachments', [])
            reactions = channel_info.get('reactions', '')
            
            if channel_name not in channels:
                channels[channel_name] = {
                    'messages': [],
                    'earliest': timestamp,
                    'latest': timestamp
                }
            
            # Update time range (using string comparison for timestamps)
            # Note: Timestamps should be in ISO format or consistent format for proper comparison
            if timestamp < channels[channel_name]['earliest']:
                channels[channel_name]['earliest'] = timestamp
            if timestamp > channels[channel_name]['latest']:
                channels[channel_name]['latest'] = timestamp
            
            # Add message to channel
            channels[channel_name]['messages'].append({
                'author': author,
                'content': message_content,
                'timestamp': timestamp,
                'attachments': attachments,
                'reactions': reactions
            })
            
        except Exception as e:
            logger.debug(f"Error parsing Discord message: {e}")
            continue
    
    # Format output
    formatted_content = ""
    
    for channel_name, channel_data in channels.items():
        # Sort messages by timestamp
        channel_data['messages'].sort(key=lambda x: x['timestamp'])
        
        # Create channel header with time range
        earliest = _format_time_for_range(channel_data['earliest'])
        latest = _format_time_for_range(channel_data['latest'])
        time_range = f"({earliest} - {latest})" if earliest != latest else f"({earliest})"
        
        formatted_content += f"\n**{database_name}** - #{channel_name} {time_range}:\n\n"
        
        # Add messages without individual timestamps
        for msg in channel_data['messages']:
            author = msg['author']
            content = msg['content'] if msg['content'] else "*[No text content]*"
            
            formatted_content += f"{author}: {content}\n"
            
            # Add attachments if present
            if msg['attachments']:
                formatted_content += "## Attachments\n"
                for attachment in msg['attachments']:
                    formatted_content += f"- {attachment}\n"
                formatted_content += "\n"
            
            # Add reactions if present
            if msg['reactions']:
                formatted_content += f"## Reactions\n{msg['reactions']}\n\n"
        
        formatted_content += "\n"
    
    return formatted_content


def _extract_discord_message_info(content: str) -> Optional[Dict[str, Any]]:
    """Extract Discord message information from the verbose markdown format."""
    try:
        lines = content.split('\n')
        channel = ""
        author = ""
        timestamp = ""
        message_content = ""
        attachments = []
        reactions = ""
        
        # Parse the header section
        in_header = True
        content_lines = []
        in_attachments = False
        in_reactions = False
        
        for line in lines:
            if in_header:
                if line.startswith('**Author:**'):
                    author = line.replace('**Author:**', '').strip()
                elif line.startswith('**Channel:**'):
                    channel = line.replace('**Channel:**', '').strip().lstrip('#')
                elif line.startswith('**Timestamp:**'):
                    timestamp = line.replace('**Timestamp:**', '').strip()
                elif line.strip() == '---':
                    in_header = False
                continue
            
            if line.strip() == '## Attachments':
                in_attachments = True
                continue
            elif line.strip() == '## Reactions':
                in_reactions = True
                continue
            elif line.startswith('##') and line.strip() != '## Attachments' and line.strip() != '## Reactions':
                in_attachments = False
                in_reactions = False
            
            if in_attachments and line.strip().startswith('- **'):
                # Extract attachment info: "- **filename.png** (size bytes)"
                attachment_match = line.strip().replace('- **', '').replace('**', '')
                attachments.append(attachment_match.strip())
            elif in_reactions and line.strip():
                reactions = line.strip()
            elif not in_attachments and not in_reactions and line.strip():
                content_lines.append(line)
        
        message_content = '\n'.join(content_lines).strip()
        
        return {
            'channel': channel,
            'author': author,
            'timestamp': timestamp,
            'content': message_content,
            'attachments': attachments,
            'reactions': reactions
        }
        
    except Exception as e:
        logger.debug(f"Error extracting Discord message info: {e}")
        return None


def _format_time_for_range(timestamp_str: str) -> str:
    """Format timestamp for time range display."""
    try:
        # Parse different timestamp formats
        if 'T' in timestamp_str:
            dt = datetime.datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
        else:
            dt = datetime.datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
        return dt.strftime("%Y-%m-%d %H:%M")
    except:
        return timestamp_str 