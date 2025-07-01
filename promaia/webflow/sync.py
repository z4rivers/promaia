"""
Sync Notion pages to Webflow CMS.
"""
import os
import re
import asyncio
import json
from typing import Dict, Any, List, Tuple, Optional
from datetime import datetime
from slugify import slugify
import requests
from bs4 import BeautifulSoup
import urllib.parse
import hashlib
import shutil

from promaia.notion.pages import (
    get_sync_pages, 
    get_pages_edited_after, 
    get_block_content, 
    get_page_title, 
    update_webflow_id, 
    get_pages_by_blog_status,
    update_page_blog_status,
    get_page_property
)
from promaia.html_converter.converter import page_to_html
from promaia.webflow.client import webflow_client, WebflowClient
from promaia.utils.config import update_last_sync_time, get_last_sync_time
from promaia.utils.config_loader import get_notion_database_id

# Default database IDs from environment variables
# DEFAULT_NOTION_DATABASE_ID = os.getenv("NOTION_WEBFLOW_DATABASE_ID") # Will be replaced by config loader
DEFAULT_WEBFLOW_COLLECTION_ID = os.getenv("WEBFLOW_COLLECTION_ID")

# Mapping between Notion property names and Webflow field names
DEFAULT_FIELD_MAPPING = {
    "Name": "name",              # Required
    "Slug": "slug",              # Required
    "Publish Date": "publish-date",     # DateTime
    "Author Name": "author-name",       # PlainText
    "Tag": "tag",                # PlainText
    "Emoji Tags": "emoji-tags",  # PlainText
    "Description": "post-summary",      # PlainText
    "Thumbnail Image": "main-image",    # Image
    "Featured": "featured",      # Switch
    "Webflow ID": "webflow-id"   # Internal use only
}

def truncate_url(url: str, max_length: int = 60) -> str:
    """Truncate a URL for display in logs."""
    if not url or len(url) <= max_length:
        return url
    
    # Split into parts
    parts = url.split('://')
    if len(parts) < 2:
        return url[:max_length-3] + '...'
    
    protocol = parts[0]
    rest = parts[1]
    
    # Calculate how much space we have left
    remaining = max_length - len(protocol) - 6  # 6 = len('://...') + len('...')
    
    # If not enough space, just do basic truncation
    if remaining < 10:
        return url[:max_length-3] + '...'
    
    # Divide remaining space between start and end of the URL
    start_length = remaining // 2
    end_length = remaining - start_length
    
    return f"{protocol}://{rest[:start_length]}...{rest[-end_length:]}"

def process_html_images(html_content: str, page_id: str) -> str:
    """
    Process all images in HTML content, uploading them to Webflow and replacing URLs.
    The formatted HTML must follow Webflow's RichText field requirements.
    
    Args:
        html_content: HTML content containing images
        page_id: ID of the page (used to create unique filenames)
        
    Returns:
        HTML content with Notion image URLs replaced with Webflow URLs in proper format
    """
    # Parse the HTML
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Find all image tags
    images = soup.find_all('img')
    print(f"Found {len(images)} images in content")
    
    # Keep track of processed images to avoid duplicates
    processed_urls = {}
    
    # Process each image
    for img in images:
        src = img.get('src')
        
        # Skip if no src attribute or already processed
        if not src or src in processed_urls:
            if src in processed_urls:
                img['src'] = processed_urls[src]
            continue
        
        # Skip if image is already on Webflow
        if 'webflow.com' in src or 'website-files.com' in src:
            continue
        
        try:
            # Generate a unique filename for the image
            parsed_url = urllib.parse.urlparse(src)
            original_filename = os.path.basename(parsed_url.path)
            
            # Create a hash from the URL to ensure uniqueness
            url_hash = hashlib.md5(src.encode()).hexdigest()[:8]
            
            # Create a filename with page ID and hash
            if '.' in original_filename:
                name, ext = os.path.splitext(original_filename)
                filename = f"{page_id[:8]}_{url_hash}{ext}"
            else:
                filename = f"{page_id[:8]}_{url_hash}.jpg"
            
            print(f"Processing image: {truncate_url(src)} -> {filename}")
            
            # Upload the image to Webflow
            result = webflow_client.upload_asset_from_url(src, filename)
            
            if result and 'url' in result:
                # Get the new URL from Webflow
                new_url = result['url']
                
                # Create a new figure element with the proper Webflow structure
                # This follows the structure required by Webflow's RichText field
                figure = soup.new_tag('figure')
                figure['class'] = 'w-richtext-figure-type-image w-richtext-align-fullwidth'
                
                # Create a new img element with the Webflow URL
                new_img = soup.new_tag('img')
                new_img['src'] = new_url
                
                # Add alt text if present
                if img.get('alt'):
                    new_img['alt'] = img.get('alt')
                    
                # Add the image to the figure
                figure.append(new_img)
                
                # Create a figcaption if there's a title
                if img.get('title'):
                    figcaption = soup.new_tag('figcaption')
                    figcaption.string = img.get('title')
                    figure.append(figcaption)
                
                # Replace the original img with the figure
                img.replace_with(figure)
                
                # Keep track of this URL
                processed_urls[src] = new_url
                print(f"  ✓ Replaced image URL: {truncate_url(src)} -> {truncate_url(new_url)}")
            else:
                print(f"  ✗ Failed to upload image: {truncate_url(src)}")
        except Exception as e:
            print(f"  ✗ Error processing image {truncate_url(src)}: {str(e)}")
    
    # Return the updated HTML content
    return str(soup)

async def notion_to_webflow_item(page: Dict[str, Any], 
                                 field_mapping: Dict[str, str] = None, 
                                 webflow_id_property_name: str = "Webflow ID"
                                 ) -> Tuple[Dict[str, Any], Optional[str]]:
    """
    Convert a Notion page to a Webflow CMS item format.
    
    Args:
        page: Notion page object
        field_mapping: Optional custom mapping of Notion property names to Webflow field names
        webflow_id_property_name: Name of the Notion property storing the Webflow ID.
        
    Returns:
        Tuple of (Webflow item data, stored Webflow ID or None)
    """
    # Use default mapping if none provided
    if field_mapping is None:
        field_mapping = DEFAULT_FIELD_MAPPING
    
    # Get page properties - adding defensive check
    properties = page.get("properties", {}) if page else {}
    if not properties:
        raise ValueError(f"Page has no properties or is malformed")
        
    webflow_data = {}
    
    # Extract the page ID
    page_id = page.get("id", "") if page else ""
    if not page_id:
        raise ValueError(f"Page has no ID")
    
    # Extract Webflow ID if it exists using get_page_property
    # This is more robust than direct property access if the property name changes
    # However, notion_to_webflow_item primarily *constructs* the data.
    # The stored_webflow_id should ideally be fetched *before* calling this,
    # but we can also retrieve it here for completeness or if page object is all we have.
    # For now, we'll assume it's passed or handled by the caller fetching it with get_page_property.
    # The original logic for extracting from properties was:
    stored_webflow_id = None
    if webflow_id_property_name in properties:
        webflow_id_prop_value = properties[webflow_id_property_name]
        if webflow_id_prop_value and webflow_id_prop_value.get("type") == "rich_text":
            rich_text_list = webflow_id_prop_value.get("rich_text", [])
            if rich_text_list:
                stored_webflow_id = "".join([text.get("plain_text", "") for text in rich_text_list if text])
                if stored_webflow_id and stored_webflow_id.strip():
                    # This function returns data payload and ID; it doesn't put _webflow_id in payload.
                    pass # stored_webflow_id is now correctly populated
                else:
                    stored_webflow_id = None

    # Get the page title from the Name property
    if "Name" in properties:
        name_prop = properties["Name"]
        if name_prop and name_prop.get("type") == "title":
            title_array = name_prop.get("title", [])
            if title_array:
                title = "".join([text.get("plain_text", "") for text in title_array if text])
                if title:
                    webflow_data[field_mapping.get("Name", "name")] = title
                else:
                    raise ValueError(f"Page title is empty")
            else:
                raise ValueError(f"Page title array is empty")
        else:
            raise ValueError(f"Name property has unexpected format")
    else:
        # If Name property is missing, this is a required field - throw an error
        raise ValueError(f"Missing required field: Name")
    
    # Generate slug if not present
    slug_field = field_mapping.get("Slug", "slug")
    if "Slug" in properties:
        slug_prop = properties["Slug"]
        if slug_prop and slug_prop.get("type") == "rich_text":
            # Get slug from rich text
            rich_text = slug_prop.get("rich_text", [])
            if rich_text:
                slug = "".join([text.get("plain_text", "") for text in rich_text if text])
                if slug:
                    webflow_data[slug_field] = slug
                else:
                    webflow_data[slug_field] = slugify(title)
            else:
                webflow_data[slug_field] = slugify(title)
        else:
            webflow_data[slug_field] = slugify(title)
    else:
        webflow_data[slug_field] = slugify(title)
    
    # Process date field
    date_field = field_mapping.get("Publish Date", "publish-date")
    if "Publish Date" in properties:
        date_prop = properties["Publish Date"]
        if date_prop and date_prop.get("type") == "date":
            date_value = date_prop.get("date")
            if date_value and date_value.get("start"):
                # Format the date for Webflow (ISO format)
                webflow_data[date_field] = date_value.get("start")
    
    # If no date is found, use current date
    if date_field not in webflow_data or not webflow_data.get(date_field):
        current_date = datetime.now().isoformat().split("T")[0]  # Format as YYYY-MM-DD
        webflow_data[date_field] = current_date
    
    # Process author field
    author_field = field_mapping.get("Author Name", "author-name")
    if "Author Name" in properties:
        author_prop = properties["Author Name"]
        if author_prop and author_prop.get("type") == "rich_text":
            rich_text = author_prop.get("rich_text", [])
            if rich_text:
                author = "".join([text.get("plain_text", "") for text in rich_text if text])
                if author:
                    webflow_data[author_field] = author
                else:
                    # Use a default author name if empty
                    webflow_data[author_field] = "Anonymous"
            else:
                webflow_data[author_field] = "Anonymous"
        else:
            webflow_data[author_field] = "Anonymous"
    else:
        # Use a default author if missing
        webflow_data[author_field] = "Anonymous"
    
    # Process tag field
    tag_field = field_mapping.get("Tag", "tag")
    if "Tag" in properties:
        tag_prop = properties["Tag"]
        if tag_prop and tag_prop.get("type") == "select":
            select = tag_prop.get("select")
            if select:
                tag_name = select.get("name")
                if tag_name:
                    webflow_data[tag_field] = tag_name
    
    # Process emoji tags field
    emoji_tags_field = field_mapping.get("Emoji Tags", "emoji-tags")
    if "Emoji Tags" in properties:
        emoji_prop = properties["Emoji Tags"]
        if emoji_prop and emoji_prop.get("type") == "rich_text":
            rich_text = emoji_prop.get("rich_text", [])
            if rich_text:
                emoji_tags = "".join([text.get("plain_text", "") for text in rich_text if text])
                if emoji_tags:
                    webflow_data[emoji_tags_field] = emoji_tags
    
    # Process description field (for post-summary)
    description_field = field_mapping.get("Description", "post-summary")
    if "Description" in properties:
        desc_prop = properties["Description"]
        if desc_prop and desc_prop.get("type") == "rich_text":
            rich_text = desc_prop.get("rich_text", [])
            if rich_text:
                description = "".join([text.get("plain_text", "") for text in rich_text if text])
                if description:
                    webflow_data[description_field] = description
    
    # Process featured image field as Webflow asset
    image_field = field_mapping.get("Thumbnail Image", "main-image")
    if "Thumbnail Image" in properties:
        img_prop = properties["Thumbnail Image"]
        if img_prop and img_prop.get("type") == "files":
            files = img_prop.get("files", [])
            if files and len(files) > 0:
                file = files[0]
                if file:
                    image_url = None
                    
                    if file.get("type") == "external":
                        external = file.get("external")
                        if external:
                            image_url = external.get("url", "")
                    elif file.get("type") == "file":
                        file_obj = file.get("file")
                        if file_obj:
                            image_url = file_obj.get("url", "")
                    
                    if image_url:
                        # Use the Notion URL directly for the main image
                        # Notion URLs are stable so we don't need to re-upload
                        webflow_data[image_field] = image_url
                        print(f"  ✓ Using Notion thumbnail image URL directly: {truncate_url(image_url)}")
    
    # Handle page cover image if present but no thumbnail was provided
    if image_field not in webflow_data and page and "cover" in page:
        cover = page.get("cover", {})
        if cover:
            image_url = None
            
            if cover.get("type") == "external":
                external = cover.get("external")
                if external:
                    image_url = external.get("url", "")
            elif cover.get("type") == "file":
                file_obj = cover.get("file")
                if file_obj:
                    image_url = file_obj.get("url", "")
                    
            if image_url:
                # Use the cover image URL directly 
                webflow_data[image_field] = image_url
                print(f"  ✓ Using Notion page cover image URL directly: {truncate_url(image_url)}")
    
    # Process featured field (checkbox)
    featured_field = field_mapping.get("Featured", "featured")
    if "Featured" in properties:
        featured_prop = properties["Featured"]
        if featured_prop and featured_prop.get("type") == "checkbox":
            webflow_data[featured_field] = featured_prop.get("checkbox", False)
    
    try:
        # Get page content
        blocks = await get_block_content(page_id)
        
        # Convert blocks to HTML
        html_content = page_to_html(blocks)
        
        # Process images in the HTML content
        processed_html = process_html_images(html_content, page_id)
        
        # Set HTML content field - always supported
        webflow_data["post-body"] = processed_html
    except Exception as e:
        # If there's an error with content processing, just use a placeholder
        print(f"  ✗ Error processing content: {str(e)}")
        webflow_data["post-body"] = f"<p>Content unavailable. Please check the original Notion page.</p>"
    
    # Remove internal fields that shouldn't be sent to Webflow
    # The _webflow_id logic was specific to how this function used to return.
    # Now it explicitly returns webflow_data and stored_webflow_id.
    
    return (webflow_data, stored_webflow_id)

async def sync_to_webflow(notion_database_id: str = None, 
                         webflow_collection_id: str = None,
                         field_mapping: Dict[str, str] = None,
                         blog_status_property_name: str = "Blog Status",
                         webflow_id_property_name: str = "Webflow ID",
                         force_update: bool = False
                         ) -> Tuple[int, int, int, int, int]:
    """
    Sync Notion pages to Webflow CMS based on a 'Blog Status' property.
    
    Args:
        notion_database_id: ID of the Notion database. If None, will be fetched from config using nickname 'cms'.
        webflow_collection_id: ID of the Webflow collection.
        field_mapping: Custom mapping of Notion property names to Webflow field names.
        blog_status_property_name: Name of the Notion select property for blog status (default: "Blog Status").
        webflow_id_property_name: Name of the Notion rich_text property storing the Webflow item ID (default: "Webflow ID").
        force_update: If True, attempts to update items even if status doesn't force it (e.g. "Live" items if modified).
                                               However, "To sync" and "Update on sync" will always force update.
        
    Returns:
        Tuple of (created_count, updated_count, deleted_count, skipped_count, error_count)
    """
    # notion_database_id = notion_database_id or DEFAULT_NOTION_DATABASE_ID # Old way
    if notion_database_id is None:
        try:
            notion_database_id = get_notion_database_id("cms")
            print(f"Using Notion database ID for 'cms' from config: {notion_database_id}") # Optional: for logging
        except (FileNotFoundError, ValueError) as e:
            raise ValueError(f"Error loading Notion database ID for 'cms': {e}. Please specify or configure in notion_config.json.") from e

    webflow_collection_id = webflow_collection_id or DEFAULT_WEBFLOW_COLLECTION_ID
    
    if not notion_database_id:
        raise ValueError("No Notion database ID provided or configured for nickname 'cms'. Please specify or set in notion_config.json.")
    if not webflow_collection_id:
        raise ValueError("No Webflow collection ID provided. Please specify or set WEBFLOW_COLLECTION_ID.")

    created_count, updated_count, deleted_count, skipped_count, error_count = 0, 0, 0, 0, 0
    
    target_statuses_for_fetch = ["To sync", "Update on sync", "Don't sync", "Live"]
    print(f"Getting pages from Notion database {notion_database_id} with '{blog_status_property_name}' in {target_statuses_for_fetch}...")
    try:
        pages_to_process = await get_pages_by_blog_status(notion_database_id, blog_status_property_name, target_statuses_for_fetch)
    except Exception as e:
        print(f"Error getting pages from Notion: {str(e)}")
        return 0, 0, 0, 0, 1 # error_count = 1
    
    if not pages_to_process:
        print(f"No pages found with '{blog_status_property_name}' in {target_statuses_for_fetch}.")
        # Update last sync time even if no pages, as an attempt was made
        new_sync_time = update_last_sync_time()
        print(f"Updated last sync time to: {new_sync_time}")
        return 0, 0, 0, 0, 0

    print(f"Found {len(pages_to_process)} pages to potentially process based on '{blog_status_property_name}'.")

    print("Getting all current items from Webflow collection...")
    try:
        webflow_items = webflow_client.get_collection_items(webflow_collection_id) or []
        print(f"Found {len(webflow_items)} existing items in Webflow.")
    except Exception as e:
        print(f"Error getting Webflow items: {str(e)}. Proceeding with empty Webflow item list.")
        webflow_items = []
        # Potentially increment error_count here or decide if it's fatal
    
    webflow_id_map = {item["id"]: item for item in webflow_items if item and "id" in item}
    processed_webflow_ids_in_this_run = set() # Tracks Webflow IDs handled (created, updated, explicitly kept for "Live")

    # Get collection schema (required fields)
    try:
        collection_fields = webflow_client.get_collection_fields(webflow_collection_id) or {}
        required_fields = [slug for slug, info in collection_fields.items() if info and info.get("required")]
        print(f"Required fields in Webflow collection: {required_fields}")
    except Exception as e:
        print(f"Error getting collection fields: {str(e)}. Proceeding without required field validation.")
        required_fields = []


    for i, page_data_from_list in enumerate(pages_to_process, 1):
        page_id = page_data_from_list.get("id")
        if not page_id:
            print(f"\n[{i}/{len(pages_to_process)}] Skipping invalid page data (no ID).")
            error_count += 1
            continue

        print(f"\n[{i}/{len(pages_to_process)}] Processing Notion page: {page_id}")
        
        try:
            current_blog_status = await get_page_property(page_id, blog_status_property_name)
            stored_webflow_id_on_notion = await get_page_property(page_id, webflow_id_property_name)
            
            # Ensure stored_webflow_id_on_notion is a string or None
            if not isinstance(stored_webflow_id_on_notion, str) or not stored_webflow_id_on_notion.strip():
                stored_webflow_id_on_notion = None

            print(f"  Notion Page ID: {page_id}, Status: '{current_blog_status}', Stored Webflow ID: {stored_webflow_id_on_notion}")

            if current_blog_status == "Live":
                print(f"  Status is 'Live'. Skipping active sync. Ensuring it's not deleted from Webflow if present.")
                if stored_webflow_id_on_notion and stored_webflow_id_on_notion in webflow_id_map:
                    processed_webflow_ids_in_this_run.add(stored_webflow_id_on_notion)
                skipped_count += 1
                continue

            elif current_blog_status == "Don't sync":
                print(f"  Status is 'Don't sync'.")
                if stored_webflow_id_on_notion and stored_webflow_id_on_notion in webflow_id_map:
                    print(f"  Attempting to delete Webflow item ID: {stored_webflow_id_on_notion}")
                    try:
                        delete_success = webflow_client.delete_item(webflow_collection_id, stored_webflow_id_on_notion)
                        if delete_success:
                            print(f"  ✓ Successfully deleted Webflow item: {stored_webflow_id_on_notion}")
                            deleted_count += 1
                            # Clear Webflow ID from Notion
                            await update_webflow_id(page_id, None, property_name=webflow_id_property_name)
                        else:
                            print(f"  ✗ Webflow client indicated delete failed for item: {stored_webflow_id_on_notion}")
                            error_count +=1
                    except Exception as e_del:
                        print(f"  ✗ Error deleting Webflow item {stored_webflow_id_on_notion}: {str(e_del)}")
                        error_count += 1
                elif stored_webflow_id_on_notion: # ID in Notion but not in Webflow map
                     print(f"  Webflow ID {stored_webflow_id_on_notion} found in Notion but not in Webflow. Clearing from Notion.")
                     await update_webflow_id(page_id, None, property_name=webflow_id_property_name)
                else:
                    print("  No Webflow ID in Notion. Nothing to delete.")
                # Item handled, even if just by doing nothing for deletion
                if stored_webflow_id_on_notion: # if there was an ID, it's "handled"
                     processed_webflow_ids_in_this_run.add(stored_webflow_id_on_notion) # Add to prevent re-deletion if error occurs
                skipped_count += 1 # Counts as skipped if no active push/update
                continue

            elif current_blog_status in ["To sync", "Update on sync"]:
                # Convert Notion page to Webflow data
                webflow_data_payload, _ = await notion_to_webflow_item(page_data_from_list, field_mapping, webflow_id_property_name)
                slug = webflow_data_payload.get("slug", f"page-{page_id[:8]}")
                
                # Validate required fields
                missing_fields = [rf for rf in required_fields if rf not in webflow_data_payload or not webflow_data_payload.get(rf)]
                if missing_fields:
                    print(f"  ✗ Missing required fields: {', '.join(missing_fields)}")
                    error_count += 1
                    continue

                # Simple logic: ID exists in Webflow = UPDATE, else = CREATE
                if stored_webflow_id_on_notion and stored_webflow_id_on_notion in webflow_id_map:
                    # UPDATE: Remove slug from payload
                    update_payload = webflow_data_payload.copy()
                    update_payload.pop("slug", None)
                    print(f"  Updating Webflow item: {stored_webflow_id_on_notion}")
                    
                    response = webflow_client.update_item(webflow_collection_id, stored_webflow_id_on_notion, update_payload)
                    if response:
                        updated_count += 1
                        processed_webflow_ids_in_this_run.add(stored_webflow_id_on_notion)
                        print(f"  ✓ Updated: {slug}")
                    else:
                        print(f"  ✗ Update failed: {slug}")
                        error_count += 1
                        
                else:
                    # CREATE: Include slug in payload
                    print(f"  Creating new Webflow item: {slug}")
                    
                    response = webflow_client.create_item(webflow_collection_id, webflow_data_payload)
                    if response and response.get("id"):
                        new_webflow_id = response["id"]
                        created_count += 1
                        processed_webflow_ids_in_this_run.add(new_webflow_id)
                        print(f"  ✓ Created: {slug} (ID: {new_webflow_id})")
                        
                        # Update Notion with new Webflow ID
                        await update_webflow_id(page_id, new_webflow_id, property_name=webflow_id_property_name)
                        
                        # Clear stale ID if we had one
                        if stored_webflow_id_on_notion:
                            print(f"  ✓ Replaced stale ID with new ID")
                    else:
                        print(f"  ✗ Create failed: {slug}")
                        error_count += 1
                
                # Update status: "To sync" → "Update on sync"
                if current_blog_status == "To sync":
                    await update_page_blog_status(page_id, blog_status_property_name, "Update on sync")
            else:
                print(f"  Unknown blog status: '{current_blog_status}'. Skipping page.")
                skipped_count += 1
                error_count +=1 # Or just skip without error, depending on desired strictness
        
        except Exception as e:
            print(f"  ✗ Error processing page: {str(e)}")
            error_count += 1
        finally:
            print("-" * 40)

    print(f"\nSync completed: {created_count} created, {updated_count} updated, {deleted_count} deleted, {skipped_count} skipped, {error_count} errors")
    return created_count, updated_count, deleted_count, skipped_count, error_count 