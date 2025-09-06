"""
Email template handling functions for newsletters - Plain Text Version.
"""
import html
import re
import os
from typing import Optional, Dict, Any, List

# Load the email template
email_template_path = os.path.join(os.path.dirname(__file__), 'templates', 'email_template.html')

def get_email_template() -> str:
    """Get the newsletter email template HTML."""
    # If template file exists, use it
    if os.path.exists(email_template_path):
        with open(email_template_path, 'r', encoding='utf-8') as f:
            return f.read()
    
    # Otherwise, return the embedded template
    return """<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<html xmlns="http://www.w3.org/1999/xhtml">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <meta http-equiv="X-UA-Compatible" content="IE=edge">
    <title>✳️NEWSLETTER_TITLE✳️</title>
</head>
<body style="background-color: #ffffff; margin: 0 !important; padding: 0 !important; font-family: Arial, sans-serif; font-size: 18px; line-height: 1.5; color: #333333;">
    <div style="display: none; font-size: 1px; color: #fefefe; line-height: 1px; font-family: Arial, sans-serif; max-height: 0px; max-width: 0px; opacity: 0; overflow: hidden;">
        ✳️NEWSLETTER_TITLE✳️ - Your newsletter has arrived!
    </div>
    <!-- START CENTERED CONTAINER -->
    <table border="0" cellpadding="0" cellspacing="0" width="100%" style="max-width: 600px;" align="center">
        <tr>
            <td align="center" valign="top">
                <!-- MARGIN WRAPPER -->
                <table border="0" cellpadding="4" cellspacing="0" width="100%" style="max-width: 600px;">
                    <tr>
                        <td>
                            <!-- START MAIN CONTENT AREA -->
                            <table border="0" cellpadding="0" cellspacing="0" width="100%" style="background-color: #FFFFF5; border: 1px solid #333333;">
                                <!-- START HEADER AREA -->
                                <tr>
                                    <td align="center" valign="middle" style="padding: 20px; border-bottom: 1px solid #333333;">
                                        <table border="0" cellpadding="0" cellspacing="0" width="100%">
                                            <tr>
                                                <td width="50%" align="left" valign="middle">
                                                    <a href="https://www.koiibenvenutto.com/" target="_blank">
                                                        <img src="https://cdn.prod.website-files.com/66bfca27c52b542e8bae67c3/6704c9a84b9aa737d0db1ab0_KOii_dark.png" alt="KOii Logo" style="display: block; height: 24px; width: auto;" />
                                                    </a>
                                                </td>
                                                <td width="50%" align="right" valign="middle">
                                                    <span style="color: #333333; font-size: 32px; line-height: 32px; display: inline-block;">☁️🌻🤲</span>
                                                </td>
                                            </tr>
                                        </table>
                                    </td>
                                </tr>
                                <!-- END HEADER AREA -->
                                <!-- START HEADER IMAGE AREA -->
                                <tr>
                                    <td align="center" valign="top" style="padding: 20px 20px 0 20px;">
                                        <img src="✳️HEADER_IMAGE✳️" alt="Header Image" style="max-width: 100%; height: auto; display: block; margin: 0 auto; border-radius: 1rem; border: 1px solid #333333;" />
                                    </td>
                                </tr>
                                <!-- END HEADER IMAGE AREA -->
                                <!-- START TITLE AND SUBTITLE -->
                                <tr>
                                    <td align="center" valign="top" style="padding: 20px 20px 0 20px; font-family: Arial, sans-serif;">
                                        <h1 style="margin: 0 0 16px 0; font-size: 32px; line-height: 1.3; color: #1B1B1B; font-weight: bold; font-family: Arial, sans-serif;">✳️NEWSLETTER_TITLE✳️</h1>
                                        ✳️SUBTITLE_PLACEHOLDER✳️
                                        <p style="font-family: Arial, sans-serif; font-size: 16px; line-height: 1.5; color: #333333; margin: 16px 0 0 0;">
                                            <a href="✳️POST_LINK✳️" target="_blank" style="color: #03305c;">Read on website</a><br>
                                            Forwarded this email? <a href="https://www.koiibenvenutto.com/" target="_blank" style="color: #03305c;">Subscribe here</a>!
                                        </p>
                                    </td>
                                </tr>
                                <!-- END TITLE AND SUBTITLE -->
                                <tr>
                                    <td align="left" valign="top" style="padding: 20px; font-family: Arial, sans-serif; font-size: 18px; line-height: 1.5; color: #333333;">
                                        ✳️NEWSLETTER_CONTENT✳️
                                    </td>
                                </tr>
                                <!-- END MAIN CONTENT AREA -->
                            </table>
                        </td>
                    </tr>
                </table>
                <!-- END MARGIN WRAPPER -->
            </td>
        </tr>
    </table>
    <!-- END CENTERED CONTAINER -->
</body>
</html>"""

def escape_html(text: Optional[str]) -> str:
    """
    Escape HTML special characters (equivalent to escapeHTML in the JS code).
    
    Args:
        text: Text to escape
        
    Returns:
        HTML-escaped text
    """
    if not text:
        return ""
    return html.escape(text)

def unitalicize_emojis(text: Optional[str]) -> str:
    """
    Prevent emojis from being italicized by wrapping them in normal style spans.
    
    Args:
        text: Text that may contain emojis
        
    Returns:
        Text with emojis wrapped in normal style spans
    """
    if not text:
        return ""
    
    # Regular expression to match emoji characters (similar to the JS version)
    emoji_regex = r'[\U0001F000-\U0001FFFF\u2600-\u27FF]'
    
    # Replace emojis with wrapped versions
    return re.sub(
        emoji_regex,
        lambda match: f'<span style="font-style: normal;">{match.group(0)}</span>',
        text
    )

def style_content(html_content: Optional[str]) -> str:
    """
    Add necessary inline styles to HTML content for email compatibility.
    
    Args:
        html_content: Raw HTML content
        
    Returns:
        HTML with inline styles added
    """
    if not html_content:
        return ""
    
    # Style images for email clients
    styled_html = re.sub(
        r'<img',
        '<img style="max-width: 100%; height: auto; display: block; margin: 24px auto; border-radius: 1rem; border: 1px solid #333333;"',
        html_content
    )
    
    # Style headings for hierarchy and consistency across email clients
    heading_styles = {
        "h1": "font-family: Arial, sans-serif; margin: 24px 0 16px 0; font-size: 24px; line-height: 1.3; font-weight: bold;",
        "h2": "font-family: Arial, sans-serif; margin: 24px 0 16px 0; font-size: 22px; line-height: 1.3; font-weight: bold;",
        "h3": "font-family: Arial, sans-serif; margin: 24px 0 16px 0; font-size: 20px; line-height: 1.3; font-weight: bold;",
        "h4": "font-family: Arial, sans-serif; margin: 24px 0 16px 0; font-size: 18px; line-height: 1.3; font-weight: bold;",
        "h5": "font-family: Arial, sans-serif; margin: 24px 0 16px 0; font-size: 16px; line-height: 1.3; font-weight: bold;",
        "h6": "font-family: Arial, sans-serif; margin: 24px 0 16px 0; font-size: 14px; line-height: 1.3; font-weight: bold;"
    }
    
    for tag, style in heading_styles.items():
        styled_html = re.sub(
            f'<{tag}([^>]*)>',
            f'<{tag}\\1 style="{style}">',
            styled_html
        )
    
    # Style paragraphs for consistent spacing
    styled_html = re.sub(
        r'<p',
        '<p style="margin: 0 0 16px 0;"',
        styled_html
    )
    
    return styled_html

def populate_email_template(
    content_html: str,
    newsletter_title: str,
    header_image: Optional[str] = None,
    subtitle: Optional[str] = None,
    post_link: Optional[str] = None
) -> str:
    """
    Populate the email template with content.
    
    Args:
        content_html: Main HTML content for the newsletter
        newsletter_title: Title of the newsletter
        header_image: URL for the header image
        subtitle: Optional subtitle text
        post_link: URL to the original post
        
    Returns:
        Complete HTML for the email
    """
    # Basic input validation
    if not content_html or not newsletter_title:
        raise ValueError("Missing required inputs: content and title are required")
    
    # Get email template
    email_template = get_email_template()
    
    # Prepare subtitle HTML if provided, otherwise use empty string
    subtitle_html = ""
    if subtitle:
        subtitle_html = f'<p style="font-family: Arial, sans-serif; font-size: 24px; font-style: italic; color: #17191a; margin: 0 0 16px 0; line-height: 1.3;">{unitalicize_emojis(escape_html(subtitle))}</p>'
    
    # Handle header image
    # If no header image is provided, remove the entire image section
    if not header_image:
        # Remove the entire header image table row section
        email_template = re.sub(
            r'<!-- START HEADER IMAGE AREA -->.*?<!-- END HEADER IMAGE AREA -->', 
            '', 
            email_template, 
            flags=re.DOTALL
        )
    
    # Style the content
    styled_content = style_content(content_html)
    
    # Populate the template with the data
    populated_email = email_template\
        .replace("✳️NEWSLETTER_TITLE✳️", escape_html(newsletter_title))\
        .replace("✳️HEADER_IMAGE✳️", header_image or "")\
        .replace("✳️SUBTITLE_PLACEHOLDER✳️", subtitle_html)\
        .replace("✳️POST_LINK✳️", post_link or "#")\
        .replace("✳️NEWSLETTER_CONTENT✳️", styled_content)
    
    return populated_email


def notion_blocks_to_plain_text(blocks: List[Dict[str, Any]]) -> str:
    """
    Convert Notion blocks to plain text format with proper formatting.

    Args:
        blocks: List of Notion block objects

    Returns:
        Plain text representation of the blocks
    """
    if not blocks:
        return ""

    text_parts = []

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
                        # Convert page mentions to readable links
                        plain_text = f"[{plain_text}](https://notion.so/{page_id.replace('-', '')})"
                    elif mention.get("type") == "database":
                        database_id = mention.get("database", {}).get("id", "")
                        plain_text = f"[{plain_text}](https://notion.so/{database_id.replace('-', '')})"
                    elif mention.get("type") == "user":
                        # Keep user mentions as plain text for now
                        pass
                    elif mention.get("type") == "link_preview":
                        url = mention.get("link_preview", {}).get("url", "")
                        plain_text = f"[{plain_text}]({url})"

                # Apply text formatting - use plain text formatting instead of markdown
                if annotations.get("bold"):
                    plain_text = plain_text.upper()  # Use uppercase for bold in plain text
                if annotations.get("italic"):
                    plain_text = f"*{plain_text}*"  # Keep italics as they work in most email clients
                if annotations.get("strikethrough"):
                    plain_text = f"---{plain_text}---"  # Use dashes for strikethrough
                if annotations.get("code"):
                    plain_text = f"\"{plain_text}\""  # Use quotes for code

                text_content += plain_text

        if not text_content.strip():
            continue

        # Format based on block type
        if block_type == "heading_1":
            text_parts.append(f"\n**{text_content}**")
        elif block_type == "heading_2":
            text_parts.append(f"\n**{text_content}**")
        elif block_type == "heading_3":
            text_parts.append(f"\n**{text_content}**")
        elif block_type == "paragraph":
            text_parts.append(f"\n{text_content}")
        elif block_type == "bulleted_list_item":
            text_parts.append(f"\n• {text_content}")
        elif block_type == "numbered_list_item":
            text_parts.append(f"\n1. {text_content}")
        elif block_type == "quote":
            # Put quotes in actual quotation marks
            text_parts.append(f'\n"{text_content}"')
        elif block_type == "code":
            text_parts.append(f"\n```\n{text_content}\n```")
        elif block_type == "divider":
            text_parts.append(f"\n---")
        else:
            # Default formatting for other block types
            text_parts.append(f"\n{text_content}")

    # Join all parts and clean up extra whitespace
    full_text = "".join(text_parts)

    # Clean up multiple consecutive newlines
    full_text = re.sub(r'\n{3,}', '\n\n', full_text)

    return full_text.strip()


def create_plain_text_newsletter(
    content_text: str,
    newsletter_title: str,
    subtitle: Optional[str] = None,
    post_link: Optional[str] = None,
    from_name: Optional[str] = None,
    cover_image_url: Optional[str] = None
) -> str:
    """
    Create a plain text newsletter from content.
    
    Args:
        content_text: Plain text content
        newsletter_title: Title of the newsletter (used for subject, not repeated in body)
        subtitle: Optional subtitle
        post_link: Optional link to full post
        from_name: Optional sender name
        cover_image_url: Optional cover image URL (will be included in plain text)
        
    Returns:
        Plain text newsletter ready to send
    """
    # Basic input validation
    if not content_text:
        raise ValueError("Missing required input: content is required")
    
    # Get sender name from environment or use default
    sender_name = from_name or os.getenv("RESEND_FROM_NAME", "Koii Benvenutto")
    
    # Build the plain text email
    email_parts = []
    
    # Include cover image if provided (simple approach)
    if cover_image_url:
        email_parts.append(f"🖼️ {cover_image_url}")
        email_parts.append("")
    
    # Subtitle if provided (but no title since it's in the subject)
    if subtitle:
        email_parts.append(subtitle)
        email_parts.append("")
    
    # Content
    email_parts.append(content_text)
    email_parts.append("")
    
    # Footer
    email_parts.append("---")
    email_parts.append("")
    if post_link:
        email_parts.append(f"📖 Read on website: {post_link}")
    email_parts.append("💌 Forwarded this email? Subscribe: https://www.koiibenvenutto.com/")
    email_parts.append("Thanks for reading!")
    email_parts.append(f"- {sender_name}")
    
    return "\n".join(email_parts)