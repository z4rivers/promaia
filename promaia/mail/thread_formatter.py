"""
Thread Formatter - Format email threads with copy-friendly styling and position indicators.

Applies the copy-friendly Rich display rules with colored message headers
that show "Message: x/y" so users can orient themselves when scrolling.
"""
from typing import List, Dict, Any, Optional
from rich.console import Console
from rich.text import Text


def parse_thread_messages(conversation_body: str) -> List[Dict[str, str]]:
    """
    Parse conversation body into individual messages.
    
    Messages are separated by "─" * 80 separators in the conversation body.
    
    Args:
        conversation_body: Full conversation body with messages separated by dashes
        
    Returns:
        List of message dictionaries with headers and content
    """
    if not conversation_body:
        return []
    
    # Split by the standard message separator (80 dashes or longer)
    # Use regex to match separator lines
    import re
    separator_pattern = r'\n─{70,}\n'
    parts = re.split(separator_pattern, conversation_body)
    
    messages = []
    for part in parts:
        part = part.strip()
        if not part:
            continue
        
        # Remove any remaining separator dashes at start/end
        while part.startswith('─'):
            part = part[1:].strip()
        while part.endswith('─'):
            part = part[:-1].strip()
        
        # Parse message headers
        lines = part.split('\n')
        headers = {}
        content_start_idx = 0
        
        # Extract headers (From:, Date:, Subject:, etc.)
        for i, line in enumerate(lines):
            line = line.strip()
            if not line:
                content_start_idx = i + 1
                break
            
            # Check for header pattern
            if ':' in line:
                key, value = line.split(':', 1)
                key = key.strip().lower()
                value = value.strip()
                
                if key in ['from', 'date', 'sent', 'to', 'subject']:
                    headers[key] = value
                else:
                    # Not a header, this is content
                    content_start_idx = i
                    break
            else:
                # Not a header line, this is content
                content_start_idx = i
                break
        
        # Extract content (everything after headers)
        content = '\n'.join(lines[content_start_idx:]).strip()
        
        # Handle summary header if present
        if content.startswith('**Thread Summary:**'):
            # Skip the summary line
            content_lines = content.split('\n')
            # Find where actual headers start
            for i, line in enumerate(content_lines):
                if line.startswith('From:') or line.startswith('Sent:'):
                    # Re-parse from this point
                    remaining = '\n'.join(content_lines[i:])
                    sub_lines = remaining.split('\n')
                    sub_headers = {}
                    sub_content_start = 0
                    
                    for j, sub_line in enumerate(sub_lines):
                        if not sub_line.strip():
                            sub_content_start = j + 1
                            break
                        if ':' in sub_line:
                            sub_key, sub_value = sub_line.split(':', 1)
                            sub_key = sub_key.strip().lower()
                            sub_value = sub_value.strip()
                            if sub_key in ['from', 'date', 'sent', 'to', 'subject']:
                                sub_headers[sub_key] = sub_value
                    
                    headers.update(sub_headers)
                    content = '\n'.join(sub_lines[sub_content_start:]).strip()
                    break
        
        messages.append({
            'headers': headers,
            'content': content
        })
    
    return messages


def format_thread_for_display(
    conversation_body: str, 
    message_count: int,
    from_addr: str,
    subject: str,
    received_str: str,
    use_colors: bool = True
) -> str:
    """
    Format email thread with copy-friendly styling and position indicators.
    
    Args:
        conversation_body: Full conversation body
        message_count: Total number of messages in thread
        from_addr: Sender's email address
        subject: Email subject
        received_str: Formatted received date string
        use_colors: Whether to use ANSI color codes (default: True)
        
    Returns:
        Formatted thread string with message position indicators
    """
    # Parse messages from conversation body
    messages = parse_thread_messages(conversation_body)
    
    # If parsing failed or only one message, use simple format
    if len(messages) <= 1:
        # Single message or unparseable - show as simple format
        if use_colors:
            return f"""\033[1;36mINBOUND MESSAGE\033[0m

\033[1mFrom:\033[0m     {from_addr}
\033[1mSubject:\033[0m  {subject}
\033[1mDate:\033[0m     {received_str}

{conversation_body}"""
        else:
            return f"""INBOUND MESSAGE

From:     {from_addr}
Subject:  {subject}
Date:     {received_str}

{conversation_body}"""
    
    # Multi-message thread - show each message with position indicator
    output = []
    
    if use_colors:
        # Header with color
        output.append(f"\033[1;36mEMAIL THREAD ({message_count} messages)\033[0m\n")
        output.append(f"\033[1mSubject:\033[0m  {subject}")
        output.append(f"\033[2mScroll up ↑ to see earlier messages in the thread\033[0m\n")
    else:
        output.append(f"EMAIL THREAD ({message_count} messages)\n")
        output.append(f"Subject:  {subject}")
        output.append(f"Scroll up ↑ to see earlier messages in the thread\n")
    
    # Display each message with position indicator
    for i, msg in enumerate(messages, 1):
        # Message header with position - using simple dashes for copy-friendliness
        header_text = f"Message: {i}/{message_count}"
        separator_length = max(70 - len(header_text), 10)
        
        if use_colors:
            # Alternate colors for visual distinction
            if i % 2 == 1:
                # Cyan for odd messages
                output.append(f"\033[1;36m{header_text} {'─' * separator_length}\033[0m")
            else:
                # Blue for even messages
                output.append(f"\033[1;34m{header_text} {'─' * separator_length}\033[0m")
        else:
            output.append(f"{header_text} {'─' * separator_length}")
        
        # Message headers (skip subject since it's shown at top)
        headers = msg['headers']
        if 'from' in headers:
            output.append(f"From: {headers['from']}")
        if 'date' in headers or 'sent' in headers:
            date = headers.get('date') or headers.get('sent')
            output.append(f"Date: {date}")
        if 'to' in headers:
            output.append(f"To: {headers['to']}")
        # Note: Subject is omitted since it's already shown in the thread header
        
        # Empty line before content
        output.append("")
        
        # Message content (no prefix for cleaner copying)
        output.append(msg['content'])
        
        # Message footer - simple separator
        if use_colors:
            if i % 2 == 1:
                output.append(f"\033[2;36m{'─' * 80}\033[0m\n")
            else:
                output.append(f"\033[2;34m{'─' * 80}\033[0m\n")
        else:
            output.append(f"{'─' * 80}\n")
    
    return '\n'.join(output)


def print_thread(
    conversation_body: str,
    message_count: int,
    from_addr: str,
    subject: str,
    received_str: str,
    use_colors: bool = True
) -> None:
    """
    Print formatted email thread to console.
    
    Args:
        conversation_body: Full conversation body
        message_count: Total number of messages in thread
        from_addr: Sender's email address
        subject: Email subject
        received_str: Formatted received date string
        use_colors: Whether to use ANSI color codes (default: True)
    """
    formatted = format_thread_for_display(
        conversation_body,
        message_count,
        from_addr,
        subject,
        received_str,
        use_colors
    )
    print(formatted)

