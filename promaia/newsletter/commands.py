"""
Newsletter CLI commands.
"""
import os
import asyncio
import re
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timezone
import urllib.parse
from bs4 import BeautifulSoup

from promaia.notion.client import ensure_default_client
from promaia.notion.pages import get_page_title, get_block_content
from promaia.html_converter.converter import block_to_html, page_to_html
from promaia.newsletter.resend_client import get_resend_client
from promaia.newsletter.template import create_plain_text_newsletter, notion_blocks_to_plain_text
from promaia.webflow.client import webflow_client
from promaia.utils.config import get_config

# Default database ID (uses the same as Webflow CMS)
WEBFLOW_CMS_DATABASE_ID = os.getenv("WEBFLOW_CMS_DATABASE_ID", "10dd13396967807ab987c92a4d29b9b8")

# Default collection ID for Webflow
DEFAULT_WEBFLOW_COLLECTION_ID = os.getenv("WEBFLOW_COLLECTION_ID")

def truncate_url(url: str, max_length: int = 50) -> str:
    """Truncate a URL for display purposes."""
    if len(url) <= max_length:
        return url
    return url[:max_length] + "..."

# Function to convert Notion blocks to plain text
async def notion_to_plain_text(page_id: str) -> str:
    """
    Convert Notion page content to plain text.
    
    Args:
        page_id: The ID of the Notion page
        
    Returns:
        Plain text string of the page content
    """
    blocks = await get_block_content(page_id)
    return notion_blocks_to_plain_text(blocks)

# Function to convert Notion blocks to HTML (keeping for backward compatibility)
async def notion_to_html(page_id: str) -> str:
    """
    Convert Notion page content to HTML.
    DEPRECATED: Use notion_to_plain_text instead for plain text newsletters.
    
    Args:
        page_id: The ID of the Notion page
        
    Returns:
        HTML string of the page content
    """
    blocks = await get_block_content(page_id)
    return page_to_html(blocks)

async def check_webflow_published(page: Dict[str, Any]) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Check if a Notion page has been published to Webflow.
    
    Args:
        page: Notion page object
        
    Returns:
        Tuple of (is_published, webflow_id, webflow_slug)
    """
    page_id = page["id"]
    properties = page.get("properties", {})
    
    # Check if the page has a Webflow ID
    webflow_id = None
    if "Webflow ID" in properties:
        webflow_id_prop = properties["Webflow ID"]
        if webflow_id_prop and webflow_id_prop.get("type") == "rich_text":
            rich_text = webflow_id_prop.get("rich_text", [])
            if rich_text:
                webflow_id = "".join([text.get("plain_text", "") for text in rich_text if text])
    
    if not webflow_id:
        print(f"   ❌ No Webflow ID found for page: {page_id}")
        return False, None, None
    
    # Get the slug
    slug = None
    if "Slug" in properties:
        slug_prop = properties["Slug"]
        if slug_prop and slug_prop.get("type") == "rich_text":
            rich_text = slug_prop.get("rich_text", [])
            if rich_text:
                slug = "".join([text.get("plain_text", "") for text in rich_text if text])
    
    # If no slug found in the Slug property, try to extract from the Name property
    if not slug and "Name" in properties:
        from slugify import slugify
        name_prop = properties["Name"]
        if name_prop and name_prop.get("type") == "title":
            title_array = name_prop.get("title", [])
            if title_array:
                title = "".join([text.get("plain_text", "") for text in title_array if text])
                if title:
                    slug = slugify(title)
    
    if not slug:
        print(f"   ❌ No slug found for page: {page_id}")
        return False, webflow_id, None
    
    # Try to verify the item exists in Webflow
    collection_id = DEFAULT_WEBFLOW_COLLECTION_ID
    if not collection_id:
        print(f"   ❌ No Webflow collection ID configured")
        return False, webflow_id, slug
    
    try:
        # Check if the item exists in Webflow
        webflow_item = webflow_client.get_item(collection_id, webflow_id)
        if webflow_item:
            print(f"   ✅ Found published blog post in Webflow (ID: {webflow_id})")
            return True, webflow_id, slug
        else:
            print(f"   ❌ Blog post with ID {webflow_id} not found in Webflow")
            return False, webflow_id, slug
    except Exception as e:
        print(f"   ❌ Error checking Webflow: {str(e)}")
        return False, webflow_id, slug

def replace_notion_images_with_webflow(html_content: str, webflow_id: str, header_image: str = None) -> str:
    """
    Replace Notion image URLs with Webflow URLs in HTML content.
    
    Args:
        html_content: HTML content with Notion image URLs
        webflow_id: Webflow item ID (to fetch the correct item)
        header_image: Optional URL of the header image to exempt from replacement
        
    Returns:
        HTML content with Webflow image URLs
    """
    # Parse the HTML
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Find all image tags
    images = soup.find_all('img')
    print(f"   Found {len(images)} images in newsletter content")
    
    # Replace Notion image URLs with Webflow URLs
    for img in images:
        src = img.get('src')
        if not src:
            continue
            
        # Skip if already a Webflow URL
        if 'webflow.com' in src or 'website-files.com' in src:
            continue
        
        # Skip if it's the header image from Notion properties
        if header_image and src == header_image:
            print(f"   ℹ️ Keeping Notion header image: {truncate_url(src)}")
            continue
            
        # Skip if it's a Notion cover image (used as header in email template)
        # Notion cover images are hosted on Notion's servers and won't be in Webflow
        parent = img.parent
        if parent and parent.name == 'td' and 'Header Image' in str(parent.get('alt', '')):
            print(f"   ℹ️ Keeping Notion cover image in email template: {truncate_url(src)}")
            continue
            
        # Mark Notion URLs to be replaced
        if 'notion.so' in src or 's3.us-west-2.amazonaws.com/secure.notion-static.com' in src:
            print(f"   ⚠️ Notion URL detected: {truncate_url(src)}")
            # Add a data attribute to mark this image for replacement
            img['data-notion-url'] = 'true'
            
    # Print a warning message about Notion images
    notion_images = [img for img in images if img.get('data-notion-url')]
    if notion_images:
        print(f"   ⚠️ Found {len(notion_images)} Notion images that need to be replaced with Webflow URLs")
        print(f"   📝 These images may not display correctly in emails until the blog post is published")
    
    # Return the updated HTML content
    return str(soup)

async def query_pages_by_status(database_id: str, status: str) -> List[Dict[str, Any]]:
    """
    Query Notion database for pages with a specific Newsletter Status.
    
    Args:
        database_id: Notion database ID
        status: Newsletter Status value to filter by
        
    Returns:
        List of page objects
    """
    status_filter = {
        "property": "Newsletter Status",
        "status": {
            "equals": status
        }
    }
    
    notion_client = ensure_default_client()
    response = await notion_client.databases.query(
        database_id=database_id,
        filter=status_filter
    )
    
    return response.get("results", [])

async def get_eligible_newsletter_pages(database_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Get pages eligible for newsletter syncing.
    
    Only includes pages with Newsletter Status "To push".
    
    Args:
        database_id: Notion database ID (defaults to WEBFLOW_CMS_DATABASE_ID)
        
    Returns:
        List of page objects with "To push" status
    """
    # Use default database ID if not provided
    db_id = database_id or WEBFLOW_CMS_DATABASE_ID
    
    # Query for pages with "To push" status only
    to_push_pages = await query_pages_by_status(db_id, "To push")
    
    return to_push_pages

async def update_page_newsletter_status(page_id: str, status: str):
    """
    Update the Newsletter Status property of a Notion page.
    
    Args:
        page_id: The ID of the Notion page
        status: The new status value
    """
    # Get the Notion client
    notion_client = ensure_default_client()
    
    # Update as rich_text property
    await notion_client.pages.update(
        page_id=page_id,
        properties={
            "Newsletter Status": {
                "status": {
                    "name": status
                }
            }
        }
    )

async def update_page_last_synced(page_id: str):
    """
    Update the Newsletter Last Synced property of a Notion page with the current datetime.
    
    Args:
        page_id: The ID of the Notion page
    """
    # Get the Notion client
    notion_client = ensure_default_client()
    
    # Use current time for sync timestamp
    now = datetime.now(timezone.utc).isoformat()
    
    # Update as rich_text property
    await notion_client.pages.update(
        page_id=page_id,
        properties={
            "Newsletter Last Synced": {
                "rich_text": [
                    {
                        "text": {
                            "content": now
                        }
                    }
                ]
            }
        }
        )


async def send_newsletter_via_resend(page: Dict[str, Any]) -> Tuple[bool, str, Optional[str]]:
    """
    Send newsletter via Resend based on Notion page content.
    
    Args:
        page: Notion page object
        
    Returns:
        Tuple of (success, message, email_id)
    """
    page_id = page["id"]
    properties = page.get("properties", {})
    
    # Debug: Print available properties
    print("   Available properties:", ", ".join(properties.keys()))
    
    # Get required properties
    title = get_property_value(page, "Title") or get_property_value(page, "Name") or ""
    if not title:
        return False, "❌ Missing page title", None
    
    # Check if the blog post has been published to Webflow
    is_published, webflow_id, webflow_slug = await check_webflow_published(page)
    if not is_published:
        print(f"   ⚠️  Blog post not found in Webflow, but continuing for newsletter testing...")
        # Use a default slug based on title
        webflow_slug = title.lower().replace(' ', '-').replace(',', '').replace('.', '')
    
    # Generate the "read on website" URL using the blog slug
    post_link = f"https://www.koiibenvenutto.com/post/{webflow_slug}" if webflow_slug else f"https://www.koiibenvenutto.com/"
    print(f"   📄 Using 'read on website' URL: {post_link}")
    
    # Get additional properties for email template
    subtitle = get_property_value(page, "Newsletter Subtitle") or ""
    print(f"   📄 Subtitle: {subtitle}")
    
    # Convert page content to plain text
    try:
        content_text = await notion_to_plain_text(page_id)
        print(f"   📄 Generated plain text content length: {len(content_text)} characters")
        print(f"   📄 Plain text preview: {content_text[:200]}...")
    except Exception as e:
        return False, f"❌ Error converting page to plain text: {str(e)}", None

    # Create plain text newsletter content
    try:
        print(f"   📧 Creating newsletter content...")
        email_content = create_plain_text_newsletter(
            content_text=content_text,
            newsletter_title=title,
            subtitle=subtitle,
            post_link=post_link
        )
        print(f"   📧 Generated email content length: {len(email_content)} characters")
        print(f"   📧 Email content preview: {email_content[:200]}...")
    except Exception as e:
        return False, f"❌ Error creating newsletter content: {str(e)}", None
    
    # Create email subject
    email_subject = title
    if subtitle:
        email_subject += f" | {subtitle}"
    print(f"   📧 Email subject: {email_subject}")
    
    # Send via Resend
    try:
        resend_client = get_resend_client()
        
        result = resend_client.send_newsletter(
            subject=email_subject,
            plain_text=email_content
        )
        
        if result["success"]:
            email_id = result["email_id"]
            return True, f"✅ Newsletter sent successfully (Email ID: {email_id})", email_id
        else:
            return False, f"❌ Failed to send newsletter: {result['error']}", None
            
    except Exception as e:
        return False, f"❌ Error with Resend API: {str(e)}", None


def format_datetime(iso_date: str) -> str:
    """Format ISO datetime for display."""
    try:
        dt = datetime.fromisoformat(iso_date.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except (ValueError, AttributeError):
        return iso_date

def get_property_value(page: Dict[str, Any], property_name: str) -> Any:
    """Extract a property value from a Notion page."""
    properties = page.get("properties", {})
    prop = properties.get(property_name, {})
    prop_type = prop.get("type")
    
    if not prop_type:
        return None
    
    if prop_type == "title":
        title_array = prop.get("title", [])
        if title_array:
            # Concatenate all text content from the title array
            return "".join([text.get("text", {}).get("content", "") for text in title_array if text.get("text", {}).get("content")])
        return ""
    
    elif prop_type == "rich_text":
        text_array = prop.get("rich_text", [])
        if text_array:
            # Concatenate all text content from the rich_text array
            return "".join([text.get("text", {}).get("content", "") for text in text_array if text.get("text", {}).get("content")])
        return ""
    
    elif prop_type == "select":
        return prop.get("select", {}).get("name")
    
    elif prop_type == "status":
        return prop.get("status", {}).get("name")
    
    elif prop_type == "url":
        return prop.get("url")
    
    elif prop_type == "date":
        return prop.get("date", {}).get("start")
    
    elif prop_type == "checkbox":
        return prop.get("checkbox")
    
    elif prop_type == "files":
        files = prop.get("files", [])
        if files and len(files) > 0:
            file = files[0]
            if file.get("type") == "external":
                return file.get("external", {}).get("url", "")
            elif file.get("type") == "file":
                return file.get("file", {}).get("url", "")
        return None
    
    return None

def get_page_display_title(page: Dict[str, Any]) -> str:
    """
    Extract a human-readable title from a Notion page.
    
    Args:
        page: Notion page object
        
    Returns:
        Human-readable title string
    """
    page_id = page["id"]
    properties = page.get("properties", {})
    
    # Get the full page title
    title_property = properties.get("Title", properties.get("Name", {}))
    
    if title_property and title_property.get("type") == "title":
        title_parts = []
        for text_obj in title_property.get("title", []):
            if text_obj.get("text", {}).get("content"):
                title_parts.append(text_obj["text"]["content"])
        title = "".join(title_parts) if title_parts else f"Untitled ({page_id[:8]})"
    else:
        # Fallback to the get_property_value function
        title = get_property_value(page, "Title") or get_property_value(page, "Name") or f"Untitled ({page_id[:8]})"
    
    return title

async def list_eligible_newsletter_pages(args):
    """
    List pages eligible for newsletter syncing.
    
    Args:
        args: Command line arguments
    """
    print("Finding newsletter pages eligible for syncing...")
    
    # Get database ID from args or use default
    database_id = getattr(args, "database", None) or WEBFLOW_CMS_DATABASE_ID
    
    # Get eligible pages
    eligible_pages = await get_eligible_newsletter_pages(database_id)
    
    if not eligible_pages:
        print("No pages eligible for newsletter syncing found.")
        return
    
    print(f"\nFound {len(eligible_pages)} eligible pages:\n")
    
    for i, page in enumerate(eligible_pages, 1):
        # Get page details
        page_id = page["id"]
        
        # Get the title using the helper function
        title = get_page_display_title(page)
        
        status = get_property_value(page, "Newsletter Status")
        last_edited = format_datetime(page.get("last_edited_time"))
        last_synced = get_property_value(page, "Newsletter Last Synced")
        last_synced_display = format_datetime(last_synced) if last_synced else "Never"
        
        # Check if the blog post has been published to Webflow
        is_published, webflow_id, _ = await check_webflow_published(page)
        webflow_status = "✅ Published" if is_published else "❌ Not published"
        
        # Display page information
        print(f"{i}. {title}")
        print(f"   ID: {page_id}")
        print(f"   Status: {status}")
        print(f"   Last edited: {last_edited}")
        print(f"   Last synced: {last_synced_display}")
        print(f"   Webflow: {webflow_status}")
        print()

async def newsletter_sync_command(args):
    """
    Send newsletters via Resend for eligible CMS pages.
    Takes pages with "Newsletter Status" = "To push" from the CMS database
    and sends newsletters via Resend, then updates status to "Sent".
    
    Args:
        args: Command line arguments
    """
    print("Starting newsletter push from CMS database...")
    
    # Always use the CMS database
    database_id = WEBFLOW_CMS_DATABASE_ID
    
    # Get eligible pages
    eligible_pages = await get_eligible_newsletter_pages(database_id)
    
    if not eligible_pages:
        print("No CMS pages eligible for newsletter push found.")
        print("Make sure pages have Newsletter Status set to 'To push'.")
        return
    
    print(f"\nFound {len(eligible_pages)} eligible CMS pages for newsletter sending:\n")
    
    success_count = 0
    failure_count = 0
    
    for i, page in enumerate(eligible_pages, 1):
        page_id = page["id"]
        
        # Get title using the helper function
        title = get_page_display_title(page)
        
        print(f"\n{i}. Processing: {title}")
        print(f"   ID: {page_id}")
        
        # Send newsletter via Resend
        success, message, email_id = await send_newsletter_via_resend(page)
        print(f"   {message}")
        
        if success:
            # Update page status and last synced date
            status_to_set_after_push = "Sent"
            # Check if current status was "To push" before updating
            current_status = get_property_value(page, "Newsletter Status")
            if current_status == "To push":
                await update_page_newsletter_status(page_id, status_to_set_after_push)
                print(f"   ✅ Updated page status from 'To push' to '{status_to_set_after_push}'")
            
            await update_page_last_synced(page_id)
            print(f"   ✅ Updated last synced timestamp")
            success_count += 1
        else:
            # Don't update page if push failed
            failure_count += 1
    
    # Print summary
    print(f"\nNewsletter push completed: {success_count} succeeded, {failure_count} failed")
    if success_count > 0:
        print(f"Successfully sent {success_count} newsletters via Resend with 'Sent' status.")
        print(f"Newsletters have been sent directly via Resend!")
    
    if failure_count > 0:
        print(f"\n{failure_count} pages failed to push. Check the error messages above for details.") 