"""
CMS Command Handlers - extracted from cli.py

Handles pushing/pulling content pages between local drafts and Notion CMS.
"""
import os
import glob
import traceback
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

from promaia.notion.client import ensure_default_client
from promaia.notion.pages import get_pages_by_date, get_page_title, get_block_content, clear_block_cache
from promaia.markdown.converter import page_to_markdown
from promaia.storage.files import save_page_to_file, get_existing_page_ids
from promaia.utils.config import update_last_sync_time, get_last_sync_time, load_environment
from promaia.utils.timezone_utils import now_utc
load_environment()
from promaia.utils.config_loader import get_notion_database_id
from promaia.utils.display import print_text

logger = logging.getLogger(__name__)
# ==================== CMS COMMAND HANDLERS ====================

async def pull_db_pages(database_id: str, output_dir: str, days: Optional[int] = None, content_type: str = "pages", fetch_all: bool = False, force_pull: bool = False):
    os.makedirs(output_dir, exist_ok=True)
    existing_page_ids = get_existing_page_ids(output_dir)
    logger.info(f"Found {len(existing_page_ids)} existing local '{content_type}' entries in {output_dir}.")
    
    last_sync = None
    if not fetch_all and not force_pull:
        last_sync = get_last_sync_time(content_type)
        logger.info(f"Last sync time for '{content_type}': {last_sync if last_sync else 'Never'}")
    elif force_pull:
        logger.info(f"Force pull enabled, ignoring last sync time for '{content_type}'.")

    logger.info(f"Querying Notion for '{content_type}' entries...")
    try:
        pages = await get_pages_by_date(database_id, days=days, fetch_all=fetch_all, last_sync_time_override=last_sync, force_pull=force_pull, content_type=content_type)
        logger.info(f"Successfully retrieved {len(pages)} pages from Notion for '{content_type}'.")
    except Exception as e:
        logger.error(f"Error retrieving pages from Notion for '{content_type}': {str(e)}")
        return

    pages_to_sync_ids = []
    skipped_count = 0

    if fetch_all or force_pull:
        pages_to_sync_ids = [page["id"] for page in pages]
        logger.info(f"Marked all {len(pages_to_sync_ids)} retrieved '{content_type}' pages for sync (fetch_all={fetch_all}, force_pull={force_pull}).")
    else:
        for page in pages:
            page_id = page["id"]
            last_edited_time_str = page.get("last_edited_time")
            last_edited_time_dt = None
            if last_edited_time_str:
                try:
                    last_edited_time_dt = datetime.fromisoformat(last_edited_time_str.replace("Z", "+00:00"))
                except ValueError:
                    logger.warning(f"Could not parse last_edited_time '{last_edited_time_str}' for page {page_id}")
            
            if page_id not in existing_page_ids or not last_sync or (last_edited_time_dt and last_edited_time_dt > last_sync):
                pages_to_sync_ids.append(page_id)
            else:
                skipped_count +=1
        logger.info(f"Found {len(pages_to_sync_ids)} '{content_type}' entries to pull (skipped {skipped_count} unmodified).")

    if not pages_to_sync_ids:
        logger.info(f"No '{content_type}' entries to pull based on the criteria.")
    else:
        logger.info(f"Pulling {len(pages_to_sync_ids)} '{content_type}' entries...")
        for i, page_id in enumerate(pages_to_sync_ids, 1):
            try:
                logger.info(f"  [{i}/{len(pages_to_sync_ids)}] Fetching & saving: {page_id}")
                clear_block_cache()
                title = await get_page_title(page_id)
                blocks = await get_block_content(page_id)
                markdown_content = page_to_markdown(blocks)
                filepath = await save_page_to_file(page_id, title, markdown_content, content_type)
                logger.info(f"  [{i}/{len(pages_to_sync_ids)}] ✓ Saved: {filepath}")
            except Exception as e:
                logger.error(f"  [{i}/{len(pages_to_sync_ids)}] ERROR processing page {page_id}: {e}")
                if os.getenv("MAIA_DEBUG") == "1":
                    traceback.print_exc()
    
    if not fetch_all and not force_pull:
        update_last_sync_time(content_type)

async def handle_cms_pull(args):
    """Handles 'maia cms pull' command - pulls CMS entries for KOii chat context."""
    logger.info("Starting CMS pull for KOii chat context")
    
    try:
        from promaia.config.databases import get_database_config
        database_config = get_database_config("cms")
        if not database_config:
            raise ValueError("CMS database not found in configuration")
    except (FileNotFoundError, ValueError) as e:
        logger.error(f"Error loading CMS database configuration: {e}")
        return

    await pull_cms_filtered(
        database_config=database_config,
        output_dir="KOii-chat-context", 
        property_filters={"KOii chat": True},
        days=args.days,
        force=args.force,
        description="KOii chat context"
    )

async def handle_cms_push(args):
    """Handles 'maia cms push' command."""
    logger.info(f"Initiating push to CMS")
    
    title = args.title

    try:
        database_id = get_notion_database_id("cms")
    except (FileNotFoundError, ValueError) as e:
        logger.error(f"Error loading Notion database ID for CMS: {e}")
        return

    logger.info(f"Pushing to Notion database ID: {database_id}")

    draft_file_path = args.draft
    if not draft_file_path:
        draft_files = glob.glob("drafts/*.md")
        if not draft_files:
            logger.error("No draft files found in drafts/ directory. Specify with --draft <filepath>.")
            return
        draft_files.sort(key=os.path.getmtime, reverse=True)
        draft_file_path = draft_files[0]
        logger.info(f"No --draft specified, using most recent: {draft_file_path}")

    if not os.path.exists(draft_file_path):
        logger.error(f"Draft file not found: {draft_file_path}")
        return

    with open(draft_file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    final_title = title
    if not final_title:
        title_match = re.search(r'^#\\s+(.+)$', content, re.MULTILINE)
        if title_match:
            final_title = title_match.group(1).strip()
        else:
            final_title = os.path.basename(draft_file_path).replace('.md', '').replace('_', ' ').title()
    
    logger.info(f"Creating Notion page with title: '{final_title}'")
    
    try:
        notion_client = ensure_default_client()
        response = await notion_client.pages.create(
            parent={"database_id": database_id},
            properties={
                "Name": {"title": [{"text": {"content": final_title}}]},
                "Status": {"select": {"name": "Draft"}},
                "Publish Date": {"date": {"start": now_utc().strftime("%Y-%m-%d")}}
            },
            children=[
                {"object": "block", "type": "paragraph", "paragraph": {
                    "rich_text": [{"type": "text", "text": {"content": "Content will be added by the editor. Full content from local draft."}}]
                }}
            ]
        )
        page_id = response["id"]
        page_url = f"https://notion.so/{page_id.replace('-', '')}"
        logger.info(f"SUCCESS: Created Notion page with ID: {page_id}")
        logger.info(f"Page URL: {page_url}")
        logger.info("\nCMS push completed successfully!")
        logger.info("Note: You'll need to manually copy the content from the draft into the Notion page.")
    except Exception as e:
        logger.error(f"Error pushing to Notion: {str(e)}")
        if hasattr(e, 'body'): logger.error(f"Details: {e.body}")

async def handle_cms_sync(args):
    """Handles 'maia cms sync' command."""
    from promaia.webflow.sync import sync_to_webflow

    logger.info(f"Initiating sync for CMS with Webflow.")
    
    try:
        notion_db_id = get_notion_database_id("cms")
    except (FileNotFoundError, ValueError) as e:
        logger.error(f"Error loading Notion database ID for CMS: {e}")
        return

    webflow_collection_id = args.collection or os.getenv("WEBFLOW_COLLECTION_ID")
    blog_status_prop = args.blog_status_property
    force = args.force_update

    if not webflow_collection_id:
        logger.error("Webflow Collection ID not specified (use --collection or WEBFLOW_COLLECTION_ID env var).")
        return

    logger.info(f"Syncing Notion DB (CMS: {notion_db_id}) to Webflow Collection: {webflow_collection_id}")
    logger.info(f"Using Notion status property: '{blog_status_prop}'")
    if force: logger.info("--force-update flag is active.")

    try:
        await sync_to_webflow(
            notion_database_id=notion_db_id,
            webflow_collection_id=webflow_collection_id,
            blog_status_property_name=blog_status_prop,
            force_update=force
        )
    except Exception as e:
        logger.error(f"Error during Notion-Webflow sync: {str(e)}")
        traceback.print_exc()

async def pull_cms_filtered(database_config, output_dir, property_filters, days, force, description):
    """Helper function to pull filtered CMS content to a specific directory."""
    import os
    import json
    from datetime import datetime
    from promaia.connectors import ConnectorRegistry
    from promaia.config.workspaces import get_workspace_api_key
    
    # Create output directory
    full_output_dir = os.path.join(os.getcwd(), output_dir)
    os.makedirs(full_output_dir, exist_ok=True)
    
    logger.info(f"Saving {description} to: {full_output_dir}")
    
    # Configure connector with appropriate credentials
    connector_config = database_config.to_dict()
    
    if database_config.source_type == 'discord':
        # Load Discord bot token from credentials file
        config_dir = os.path.join("credentials", database_config.workspace)
        credentials_file = os.path.join(config_dir, "discord_credentials.json")
        
        if not os.path.exists(credentials_file):
            logger.error(f"Discord credentials not found for workspace '{database_config.workspace}'")
            logger.error(f"Please run: maia workspace discord-setup {database_config.workspace}")
            return
        
        try:
            with open(credentials_file, 'r', encoding='utf-8') as f:
                creds_data = json.load(f)
            connector_config['bot_token'] = creds_data.get("bot_token")
        except Exception as e:
            logger.error(f"Failed to load Discord credentials: {e}")
            return
    else:
        # This block handles non-Discord connectors
        # Get workspace-specific API key for other services (Notion, etc.)
        api_key = get_workspace_api_key(database_config.workspace)
        if not api_key:
            logger.error(f"No API key configured for workspace '{database_config.workspace}'")
            return
        connector_config['api_key'] = api_key
    
    connector = ConnectorRegistry.get_connector(database_config.source_type, connector_config)
    if not connector:
        logger.error(f"Could not create connector for {database_config.source_type}")
        return
    
    # Parse days argument
    if days is not None:
        if isinstance(days, str) and days.lower() == 'all':
            days = None  # All entries
        else:
            try:
                days = int(days)
            except ValueError:
                days = database_config.default_days
    else:
        days = database_config.default_days
    
    logger.info(f"Filtering CMS pages with {property_filters}, days: {days or 'all'}")
    
    try:
        # Build filters
        from promaia.connectors.base import QueryFilter, DateRangeFilter
        from datetime import datetime
        from promaia.utils.timezone_utils import days_ago_utc, now_utc
        
        filters = []
        for prop_name, prop_value in property_filters.items():
            filters.append(QueryFilter(
                property_name=prop_name,
                operator="eq",
                value=prop_value
            ))
        
        # Create date filter if days is specified
        date_filter = None
        if days:
            start_date = days_ago_utc(days)
            date_filter = DateRangeFilter(
                property_name="last_edited_time",
                start_date=start_date,
                end_date=None
            )
        
        pages = await connector.query_pages(filters=filters, date_filter=date_filter)
        logger.info(f"Found {len(pages)} pages matching filters")
        
        # Save pages
        saved_count = 0
        for page in pages:
            try:
                page_id = page.get("id", "unknown")
                
                # Extract title
                title = "Untitled"
                properties = page.get("properties", {})
                for prop_name, prop_data in properties.items():
                    if prop_data.get("type") == "title" and prop_data.get("title"):
                        title = prop_data["title"][0].get("plain_text", "Untitled")
                        break
                
                # Get page content
                try:
                    from promaia.notion.pages import get_block_content
                    from promaia.markdown.converter import page_to_markdown
                    content_blocks = await get_block_content(page_id)
                    markdown_content = page_to_markdown(content_blocks)
                    page["content"] = markdown_content
                except Exception as content_error:
                    logger.warning(f"Could not fetch content for page {page_id}: {content_error}")
                    page["content"] = ""
                
                # Clean title for filename
                clean_title = "".join(c for c in title if c.isalnum() or c in (' ', '-', '_')).rstrip()
                clean_title = clean_title.replace(' ', '_')
                if not clean_title:
                    clean_title = f"untitled_{page_id[:8]}"
                
                # Save as JSON
                json_filename = f"{clean_title}_{page_id[:8]}.json"
                json_path = os.path.join(full_output_dir, json_filename)
                with open(json_path, 'w', encoding='utf-8') as f:
                    json.dump(page, f, indent=2, ensure_ascii=False)
                
                # Save as markdown if content exists
                if page.get("content"):
                    md_filename = f"{clean_title}_{page_id[:8]}.md"
                    md_path = os.path.join(full_output_dir, md_filename)
                    with open(md_path, 'w', encoding='utf-8') as f:
                        f.write(f"# {title}\n\n")
                        f.write(page["content"])
                
                saved_count += 1
                logger.info(f"Saved: {clean_title}")
                
            except Exception as e:
                logger.error(f"Error saving page {page_id}: {e}")
        
        logger.info(f"Successfully saved {saved_count} {description} pages")
        
        # Create metadata file
        metadata = {
            "created_at": now_utc().isoformat(),
            "filter_applied": property_filters,
            "days_filter": days,
            "total_pages": len(pages),
            "saved_pages": saved_count,
            "description": description
        }
        
        metadata_path = os.path.join(full_output_dir, "_metadata.json")
        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)
        
    except Exception as e:
        logger.error(f"Error querying CMS pages: {e}")
        import traceback
        traceback.print_exc()

