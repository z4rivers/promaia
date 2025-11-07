"""
Email template handling functions for newsletters - Simple Markdown Version.
"""
import html
import re
import os
from typing import Optional, Dict, Any, List

# Resend unsubscribe URL placeholder (will be replaced by Resend when sending)
RESEND_UNSUBSCRIBE_PLACEHOLDER = "{{{RESEND_UNSUBSCRIBE_URL}}}"

def escape_html(text: Optional[str]) -> str:
    """
    Escape HTML special characters.
    
    Args:
        text: Text to escape
        
    Returns:
        HTML-escaped text
    """
    if not text:
        return ""
    return html.escape(text)

def markdown_to_html(markdown_text: str) -> str:
    """
    Convert markdown text to HTML with proper formatting.
    
    This is a simple implementation that supports common markdown features.
    
    Args:
        markdown_text: Markdown formatted text
        
    Returns:
        HTML string
    """
    if not markdown_text:
        return ""
    
    # Split into lines for processing
    lines = markdown_text.split('\n')
    html_lines = []
    in_code_block = False
    code_block_lines = []
    in_list = False
    
    for line in lines:
        # Handle code blocks
        if line.strip().startswith('```'):
            if in_code_block:
                # End code block
                html_lines.append('<pre><code>' + escape_html('\n'.join(code_block_lines)) + '</code></pre>')
                code_block_lines = []
                in_code_block = False
            else:
                # Start code block
                in_code_block = True
            continue
        
        if in_code_block:
            code_block_lines.append(line)
            continue
        
        # Handle headings
        if line.startswith('# '):
            html_lines.append(f'<h1>{escape_html(line[2:])}</h1>')
            in_list = False
        elif line.startswith('## '):
            html_lines.append(f'<h2>{escape_html(line[3:])}</h2>')
            in_list = False
        elif line.startswith('### '):
            html_lines.append(f'<h3>{escape_html(line[4:])}</h3>')
            in_list = False
        # Handle blockquotes
        elif line.startswith('> '):
            html_lines.append(f'<blockquote><p>{format_inline_markdown(line[2:])}</p></blockquote>')
            in_list = False
        # Handle unordered lists
        elif line.startswith('- ') or line.startswith('* '):
            if not in_list:
                html_lines.append('<ul>')
                in_list = 'ul'
            html_lines.append(f'<li>{format_inline_markdown(line[2:])}</li>')
        # Handle ordered lists
        elif re.match(r'^\d+\.\s', line):
            content = re.sub(r'^\d+\.\s', '', line)
            if in_list != 'ol':
                if in_list:
                    html_lines.append(f'</{in_list}>')
                html_lines.append('<ol>')
                in_list = 'ol'
            html_lines.append(f'<li>{format_inline_markdown(content)}</li>')
        # Handle horizontal rules
        elif line.strip() == '---' or line.strip() == '***':
            if in_list:
                html_lines.append(f'</{in_list}>')
                in_list = False
            html_lines.append('<hr />')
        # Handle empty lines
        elif not line.strip():
            if in_list:
                html_lines.append(f'</{in_list}>')
                in_list = False
            html_lines.append('')
        # Regular paragraphs
        else:
            if in_list:
                html_lines.append(f'</{in_list}>')
                in_list = False
            html_lines.append(f'<p>{format_inline_markdown(line)}</p>')
    
    # Close any open lists
    if in_list:
        html_lines.append(f'</{in_list}>')
    
    return '\n'.join(html_lines)


def format_inline_markdown(text: str) -> str:
    """
    Format inline markdown elements like bold, italic, links, and code.
    
    Args:
        text: Text with inline markdown
        
    Returns:
        HTML-formatted text
    """
    # Handle images: ![alt](url)
    text = re.sub(r'!\[([^\]]*)\]\(([^\)]+)\)', r'<img src="\2" alt="\1" />', text)
    
    # Handle links: [text](url)
    text = re.sub(r'\[([^\]]+)\]\(([^\)]+)\)', r'<a href="\2">\1</a>', text)
    
    # Handle bold: **text** or __text__
    text = re.sub(r'\*\*([^\*]+)\*\*', r'<strong>\1</strong>', text)
    text = re.sub(r'__([^_]+)__', r'<strong>\1</strong>', text)
    
    # Handle italic: *text* or _text_
    text = re.sub(r'\*([^\*]+)\*', r'<em>\1</em>', text)
    text = re.sub(r'_([^_]+)_', r'<em>\1</em>', text)
    
    # Handle strikethrough: ~~text~~
    text = re.sub(r'~~([^~]+)~~', r'<del>\1</del>', text)
    
    # Handle inline code: `code`
    text = re.sub(r'`([^`]+)`', lambda m: f'<code>{escape_html(m.group(1))}</code>', text)
    
    return text

def create_simple_newsletter_html(
    content_markdown: str,
    title: str,
    header_image_url: Optional[str] = None,
    subtitle: Optional[str] = None,
    post_link: Optional[str] = None
) -> str:
    """
    Create a simple newsletter HTML from markdown content.
    
    This template is intentionally simple to maximize deliverability.
    It includes:
    - Optional header image (shows as actual image, not link)
    - Title in h1 below the header image
    - Properly formatted markdown content
    - Footer with website link
    
    Args:
        content_markdown: Markdown content for the newsletter body
        title: Newsletter title (will be shown in h1)
        header_image_url: Optional URL for header image
        subtitle: Optional subtitle text
        post_link: Optional link to read on website
        
    Returns:
        Complete HTML email ready to send
    """
    # Convert markdown content to HTML
    content_html = markdown_to_html(content_markdown)
    
    # Build header image section if provided
    header_image_html = ""
    if header_image_url:
        header_image_html = f'''
        <div style="position: relative; width: 100%; padding-bottom: 66.67%; margin: 0 0 20px 0; overflow: hidden; border-radius: 8px;">
            <img src="{header_image_url}" alt="Header Image" style="position: absolute; top: 0; left: 0; width: 100%; height: 100%; object-fit: cover; display: block;" />
        </div>
        '''
    
    # Build subtitle section if provided
    subtitle_html = ""
    if subtitle:
        subtitle_html = f'<p style="font-size: 18px; color: #666; margin: 0 0 20px 0; font-style: italic;">{escape_html(subtitle)}</p>'
    
    # Build footer link section
    footer_link_html = ""
    if post_link:
        footer_link_html = f'''
        <p style="margin: 20px 0 10px 0; font-size: 14px;">
            <a href="{post_link}" style="color: #007acc; text-decoration: none;">Read on website →</a>
        </p>
        '''
    
    # Create the complete HTML email
    html_email = f'''<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{escape_html(title)}</title>
</head>
<body style="margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif; background-color: #ffffff;">
    <div style="max-width: 600px; margin: 0 auto; background-color: #ffffff; padding: 40px 30px;">
        {header_image_html}
        
        <h1 style="font-size: 28px; font-weight: 600; color: #1a1a1a; margin: 0 0 10px 0; line-height: 1.3;">{escape_html(title)}</h1>
        
        {subtitle_html}
        
        <div style="color: #333; font-size: 16px; line-height: 1.6; margin: 20px 0;">
            {content_html}
        </div>
        
        {footer_link_html}
        
        <div style="margin-top: 40px; padding-top: 20px; border-top: 1px solid #e0e0e0; font-size: 14px; color: #888;">
            <p style="margin: 0;">Forwarded this email? <a href="https://www.koiibenvenutto.com/" style="color: #007acc; text-decoration: none;">Subscribe here</a></p>
        </div>

        <div style="margin-top: 20px; font-size: 12px; color: #888;">
            <a href="{RESEND_UNSUBSCRIBE_PLACEHOLDER}" style="color: #888; text-decoration: underline;">Unsubscribe</a>
        </div>
    </div>
</body>
</html>'''
    
    return html_email


def notion_blocks_to_markdown(blocks: List[Dict[str, Any]]) -> str:
    """
    Convert Notion blocks to markdown format.

    Args:
        blocks: List of Notion block objects

    Returns:
        Markdown representation of the blocks
    """
    if not blocks:
        return ""

    markdown_parts = []

    for block in blocks:
        block_type = block.get("type", "")
        content = block.get(block_type, {})

        # Extract rich text content with proper formatting
        rich_text = content.get("rich_text", [])
        text_content = ""

        for text_obj in rich_text:
            if text_obj and "plain_text" in text_obj:
                plain_text = text_obj["plain_text"]
                annotations = text_obj.get("annotations", {})

                # Handle mentions
                if text_obj.get("type") == "mention":
                    mention = text_obj.get("mention", {})
                    if mention.get("type") == "page":
                        page_id = mention.get("page", {}).get("id", "")
                        plain_text = f"[{plain_text}](https://notion.so/{page_id.replace('-', '')})"
                    elif mention.get("type") == "database":
                        database_id = mention.get("database", {}).get("id", "")
                        plain_text = f"[{plain_text}](https://notion.so/{database_id.replace('-', '')})"
                    elif mention.get("type") == "link_preview":
                        url = mention.get("link_preview", {}).get("url", "")
                        plain_text = f"[{plain_text}]({url})"

                # Apply markdown formatting
                if annotations.get("bold"):
                    plain_text = f"**{plain_text}**"
                if annotations.get("italic"):
                    plain_text = f"*{plain_text}*"
                if annotations.get("strikethrough"):
                    plain_text = f"~~{plain_text}~~"
                if annotations.get("code"):
                    plain_text = f"`{plain_text}`"

                # Handle links
                if text_obj.get("href"):
                    plain_text = f"[{plain_text}]({text_obj['href']})"

                text_content += plain_text

        if not text_content.strip():
            # Handle empty blocks
            if block_type == "divider":
                markdown_parts.append("\n---\n")
            continue

        # Format based on block type
        if block_type == "heading_1":
            markdown_parts.append(f"\n# {text_content}\n")
        elif block_type == "heading_2":
            markdown_parts.append(f"\n## {text_content}\n")
        elif block_type == "heading_3":
            markdown_parts.append(f"\n### {text_content}\n")
        elif block_type == "paragraph":
            markdown_parts.append(f"\n{text_content}\n")
        elif block_type == "bulleted_list_item":
            markdown_parts.append(f"- {text_content}\n")
        elif block_type == "numbered_list_item":
            markdown_parts.append(f"1. {text_content}\n")
        elif block_type == "quote":
            markdown_parts.append(f"\n> {text_content}\n")
        elif block_type == "code":
            language = content.get("language", "")
            markdown_parts.append(f"\n```{language}\n{text_content}\n```\n")
        elif block_type == "divider":
            markdown_parts.append("\n---\n")
        elif block_type == "image":
            # Handle images
            image_url = ""
            if content.get("type") == "external":
                image_url = content.get("external", {}).get("url", "")
            elif content.get("type") == "file":
                image_url = content.get("file", {}).get("url", "")
            
            if image_url:
                caption = ""
                if content.get("caption"):
                    caption_parts = [t.get("plain_text", "") for t in content.get("caption", [])]
                    caption = "".join(caption_parts)
                
                markdown_parts.append(f"\n![{caption}]({image_url})\n")
        else:
            # Default formatting for other block types
            if text_content.strip():
                markdown_parts.append(f"\n{text_content}\n")

    # Join all parts
    full_markdown = "".join(markdown_parts)

    # Clean up excessive newlines
    full_markdown = re.sub(r'\n{3,}', '\n\n', full_markdown)

    return full_markdown.strip()


def notion_blocks_to_plain_text(blocks: List[Dict[str, Any]]) -> str:
    """
    Convert Notion blocks to plain text format (deprecated - use notion_blocks_to_markdown instead).
    
    This function is kept for backward compatibility.

    Args:
        blocks: List of Notion block objects

    Returns:
        Plain text representation of the blocks
    """
    # Just convert to markdown which can be rendered as plain text if needed
    return notion_blocks_to_markdown(blocks)


def create_plain_text_newsletter(
    content_text: str,
    newsletter_title: str,
    subtitle: Optional[str] = None,
    post_link: Optional[str] = None,
    from_name: Optional[str] = None,
    cover_image_url: Optional[str] = None
) -> str:
    """
    Create a plain text newsletter from content (deprecated - kept for backward compatibility).
    
    Args:
        content_text: Plain text/markdown content
        newsletter_title: Title of the newsletter
        subtitle: Optional subtitle
        post_link: Optional link to full post
        from_name: Optional sender name
        cover_image_url: Optional cover image URL
        
    Returns:
        Plain text newsletter ready to send
    """
    # Basic input validation
    if not content_text:
        raise ValueError("Missing required input: content is required")
    
    # Build the plain text email
    email_parts = []
    
    # Title
    email_parts.append(newsletter_title)
    email_parts.append("")
    
    # Include cover image if provided (as URL in plain text)
    if cover_image_url:
        email_parts.append(f"🖼️ {cover_image_url}")
        email_parts.append("")
    
    # Subtitle if provided
    if subtitle:
        email_parts.append(subtitle)
        email_parts.append("")
    
    # Content
    email_parts.append(content_text)
    email_parts.append("")
    
    # Footer
    email_parts.append("")
    if post_link:
        email_parts.append(f"Read on website: {post_link}")
    email_parts.append("")
    email_parts.append("Forwarded this email? Subscribe: https://www.koiibenvenutto.com/")
    
    return "\n".join(email_parts)