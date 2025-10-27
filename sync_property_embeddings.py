#!/usr/bin/env python3
"""
Sync property embeddings for all existing database content.

This script:
1. Queries all pages from the unified_content table
2. For each page, checks if property embeddings exist in ChromaDB
3. If not, creates embeddings for all embeddable properties (title, text, rich_text, relation)
4. Skips pages that already have property embeddings (unless --force is used)
"""
import os
import sys
import json
import logging
import sqlite3
import time
from typing import Dict, Any, List, Optional

# Add promaia to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from promaia.storage.hybrid_storage import get_hybrid_registry
from promaia.storage.vector_db import VectorDBManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Define embeddable property types
EMBEDDABLE_TYPES = {'title', 'text', 'rich_text', 'relation'}

# Rate limiting configuration
RATE_LIMIT_DELAY = 0.05  # 50ms delay between embeddings (20 requests/sec, well under OpenAI's 3000 RPM)
BATCH_SIZE = 50  # Process in batches for progress tracking
BATCH_DELAY = 1.0  # 1 second delay between batches
MAX_RETRIES = 5  # Max retry attempts for rate limit errors
RETRY_DELAY = 2.0  # Initial retry delay in seconds (doubles with each retry)


def load_config() -> Dict[str, Any]:
    """Load configuration from promaia.config.json."""
    config_path = "promaia.config.json"
    try:
        with open(config_path, 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load config: {e}")
        sys.exit(1)


def get_database_id_from_config(config: Dict[str, Any], workspace: str, database_name: str) -> Optional[str]:
    """Get database_id from config for a workspace.database_name combination."""
    # Strip workspace prefix if present in database_name
    db_name_clean = database_name.split('.')[-1] if '.' in database_name else database_name

    # Check all databases in config
    databases = config.get('databases', {})
    for db_key, db_config in databases.items():
        # Match by nickname and workspace
        if db_config.get('nickname') == db_name_clean and db_config.get('workspace') == workspace:
            return db_config.get('database_id')

    return None


def _format_property_for_embedding(
    value: Any,
    prop_type: str,
    page_id: str,
    registry
) -> Optional[str]:
    """Format property value as text for embedding (same as hybrid_storage)."""
    MAX_TOKENS = 8000  # Maximum tokens for property embeddings

    if value is None or value == '':
        return None

    # Format value based on type
    formatted_value = None

    if prop_type == 'relation':
        # Resolve relation IDs to titles
        formatted_value = _resolve_relation_titles(value, registry)

    elif prop_type in ['people', 'multi_select']:
        # Already comma-separated strings or JSON arrays
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
                if isinstance(parsed, list):
                    formatted_value = ", ".join(str(item) for item in parsed)
            except:
                pass
        if formatted_value is None:
            formatted_value = str(value)

    else:
        # title, text, rich_text, select, status
        formatted_value = str(value)

    if formatted_value is None:
        return None

    # Truncate if exceeds max tokens
    try:
        # Try using tiktoken for accurate token counting (OpenAI)
        try:
            import tiktoken
            encoding = tiktoken.get_encoding("cl100k_base")
            tokens = encoding.encode(formatted_value)

            if len(tokens) > MAX_TOKENS:
                # Truncate to max tokens
                truncated_tokens = tokens[:MAX_TOKENS]
                formatted_value = encoding.decode(truncated_tokens)
                logger.warning(
                    f"⚠️ Property value truncated from {len(tokens)} to {MAX_TOKENS} tokens "
                    f"(page: {page_id}, type: {prop_type})"
                )
        except ImportError:
            # Fallback: rough character-based estimation (1 token ≈ 4 chars)
            estimated_tokens = len(formatted_value) // 4
            if estimated_tokens > MAX_TOKENS:
                max_chars = MAX_TOKENS * 4
                formatted_value = formatted_value[:max_chars]
                logger.warning(
                    f"⚠️ Property value truncated (estimated {estimated_tokens} tokens, "
                    f"max {MAX_TOKENS} tokens, page: {page_id}, type: {prop_type})"
                )
    except Exception as e:
        logger.debug(f"Could not check token length, using value as-is: {e}")

    return formatted_value


def _extract_property_value(prop_data: Dict[str, Any], prop_type: str) -> Any:
    """
    Extract the actual value from a Notion property data structure.

    Args:
        prop_data: Notion property data dict
        prop_type: Notion property type

    Returns:
        Extracted value (string, list, or None)
    """
    if not prop_data:
        return None

    try:
        if prop_type == 'title':
            if prop_data.get('title'):
                return ''.join([t.get('plain_text', '') for t in prop_data['title']])

        elif prop_type in ['text', 'rich_text']:
            if prop_data.get('rich_text'):
                return ''.join([t.get('plain_text', '') for t in prop_data['rich_text']])

        elif prop_type == 'relation':
            if prop_data.get('relation'):
                # Return list of page IDs as comma-separated string
                page_ids = [r.get('id') for r in prop_data['relation'] if r.get('id')]
                return ','.join(page_ids) if page_ids else None

        elif prop_type == 'select':
            if prop_data.get('select'):
                return prop_data['select'].get('name')

        elif prop_type == 'status':
            if prop_data.get('status'):
                return prop_data['status'].get('name')

        elif prop_type == 'multi_select':
            if prop_data.get('multi_select'):
                return [item.get('name') for item in prop_data['multi_select']]

        elif prop_type == 'date':
            if prop_data.get('date'):
                return prop_data['date'].get('start')

        elif prop_type == 'checkbox':
            return prop_data.get('checkbox', False)

        elif prop_type == 'number':
            return prop_data.get('number')

        elif prop_type == 'url':
            return prop_data.get('url')

        elif prop_type == 'email':
            return prop_data.get('email')

        elif prop_type == 'phone_number':
            return prop_data.get('phone_number')

        elif prop_type == 'people':
            if prop_data.get('people'):
                return [p.get('name', p.get('id')) for p in prop_data['people']]

    except Exception as e:
        logger.debug(f"Error extracting property value for type {prop_type}: {e}")

    return None


def _resolve_relation_titles(relation_value: str, registry) -> Optional[str]:
    """Resolve relation page IDs to titles (same as hybrid_storage)."""
    if not relation_value:
        return None

    try:
        # Parse relation value (could be JSON array or comma-separated)
        if relation_value.startswith('['):
            page_ids = json.loads(relation_value)
        else:
            page_ids = [pid.strip() for pid in relation_value.split(',') if pid.strip()]

        if not page_ids:
            return None

        titles = []
        not_found = []
        with sqlite3.connect(registry.db_path) as conn:
            cursor = conn.cursor()

            for page_id in page_ids:
                cursor.execute(
                    "SELECT title FROM unified_content WHERE page_id = ?",
                    (page_id,)
                )
                row = cursor.fetchone()
                if row and row[0]:
                    titles.append(row[0])
                else:
                    not_found.append(page_id)
                    logger.debug(f"Relation page not found (may have been deleted): {page_id}")

        if not_found and not titles:
            logger.debug(f"All relation pages not found: {len(not_found)} missing")
            return None  # All relations are broken

        return ", ".join(titles) if titles else None

    except Exception as e:
        logger.warning(f"Failed to resolve relation titles: {e}")
        return None


def _add_property_embedding_with_retry(
    vector_db: VectorDBManager,
    page_id: str,
    property_name: str,
    property_value: str,
    property_type: str,
    base_metadata: Dict[str, Any],
    rate_limit_delay: float = RATE_LIMIT_DELAY,
    max_retries: int = MAX_RETRIES
) -> bool:
    """
    Add property embedding with retry logic for rate limit errors.

    Args:
        vector_db: VectorDBManager instance
        page_id: Page ID
        property_name: Property name
        property_value: Formatted property value
        property_type: Property type
        base_metadata: Base metadata dict
        rate_limit_delay: Delay in seconds between embeddings
        max_retries: Maximum retry attempts

    Returns:
        True if successful, False otherwise
    """
    retry_delay = RETRY_DELAY

    for attempt in range(max_retries):
        try:
            success = vector_db.add_property_embedding(
                page_id=page_id,
                property_name=property_name,
                property_value=property_value,
                property_type=property_type,
                base_metadata=base_metadata
            )

            if success:
                # Add delay between successful embeddings to respect rate limits
                time.sleep(rate_limit_delay)
                return True
            else:
                return False

        except Exception as e:
            error_str = str(e).lower()

            # Check if it's a rate limit error
            is_rate_limit = any(indicator in error_str for indicator in [
                'rate limit', 'rate_limit', '429', 'too many requests'
            ])

            if is_rate_limit and attempt < max_retries - 1:
                logger.warning(
                    f"⚠️ Rate limit hit for {page_id}.{property_name}, "
                    f"retrying in {retry_delay:.1f}s (attempt {attempt + 1}/{max_retries})..."
                )
                time.sleep(retry_delay)
                retry_delay *= 2  # Exponential backoff
                continue
            else:
                # Not a rate limit error or max retries exceeded
                logger.error(f"❌ Failed to embed {page_id}.{property_name}: {e}")
                return False

    return False


def sync_property_embeddings(
    workspace: str = None,
    database_name: str = None,
    dry_run: bool = False,
    skip_existing: bool = True,
    rate_limit_delay: float = RATE_LIMIT_DELAY,
    batch_delay: float = BATCH_DELAY
):
    """
    Sync all property embeddings for database content.

    Args:
        workspace: Optional workspace filter
        database_name: Optional database filter
        dry_run: If True, only analyze without making changes
        skip_existing: If True, skip pages that already have property embeddings
        rate_limit_delay: Delay in seconds between embedding API calls (default: 0.05s)
        batch_delay: Delay in seconds between batches of embeddings (default: 1.0s)
    """
    # Load configuration
    config = load_config()
    vector_config = config.get('global', {}).get('vector_search', {})

    if not vector_config.get('enabled', False):
        logger.error("Vector search is disabled in config. Please enable it first.")
        sys.exit(1)

    # Initialize registry and vector DB
    registry = get_hybrid_registry()
    vector_db = VectorDBManager(chroma_path=vector_config.get('chroma_path', 'chroma_db'))

    logger.info("Querying all pages from unified_content...")

    # Get all pages with their database info
    try:
        with sqlite3.connect("data/hybrid_metadata.db") as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # Build query with optional filters
            query = "SELECT page_id, workspace, database_name, database_id, content_type FROM unified_content"
            params = []
            where_clauses = []

            if workspace:
                where_clauses.append("workspace = ?")
                params.append(workspace)

            if database_name:
                where_clauses.append("database_name = ?")
                params.append(database_name)

            if where_clauses:
                query += " WHERE " + " AND ".join(where_clauses)

            cursor.execute(query, params)
            pages = [dict(row) for row in cursor.fetchall()]
    except Exception as e:
        logger.error(f"Failed to query pages: {e}")
        sys.exit(1)

    logger.info(f"Found {len(pages)} pages to process")

    # Statistics
    stats = {
        'total_pages': len(pages),
        'pages_with_properties': 0,
        'already_embedded_properties': 0,
        'newly_embedded_properties': 0,
        'total_properties_created': 0,
        'failed_pages': 0,
        'skipped_no_schema': 0
    }

    # Group pages by database to get property schemas once
    pages_by_db = {}
    for page in pages:
        db_key = (page['workspace'], page['database_name'])
        if db_key not in pages_by_db:
            pages_by_db[db_key] = []
        pages_by_db[db_key].append(page)

    # Process each database
    for (db_workspace, db_name), db_pages in pages_by_db.items():
        logger.info(f"\nProcessing database: {db_workspace}.{db_name} ({len(db_pages)} pages)")

        # Get database_id from config
        database_id = get_database_id_from_config(config, db_workspace, db_name)
        if not database_id:
            logger.warning(f"  No database_id found in config for {db_workspace}.{db_name}, skipping...")
            stats['skipped_no_schema'] += len(db_pages)
            continue

        # Get property schema for this database (by database_id, not name)
        property_schema = registry.get_property_schema(database_id)

        if not property_schema:
            logger.info(f"  No property schema found for database {database_id}, skipping...")
            stats['skipped_no_schema'] += len(db_pages)
            continue

        # Filter to embeddable properties
        embeddable_props = [
            prop for prop in property_schema
            if prop['notion_type'] in EMBEDDABLE_TYPES
        ]

        if not embeddable_props:
            logger.info(f"  No embeddable properties in schema, skipping...")
            stats['skipped_no_schema'] += len(db_pages)
            continue

        logger.info(f"  Found {len(embeddable_props)} embeddable properties: {', '.join(p['column_name'] for p in embeddable_props)}")

        # Get table name for this database (from first property schema entry)
        table_name = property_schema[0]['table_name'] if property_schema else None
        if not table_name:
            logger.warning(f"  Could not determine table name for {db_name}, skipping...")
            stats['skipped_no_schema'] += len(db_pages)
            continue

        # Process each page in this database (with batching for progress tracking)
        total_properties_in_db = 0
        for i, page in enumerate(db_pages, 1):
            page_id = page['page_id']

            # Progress reporting every 50 pages or at key milestones
            if i % BATCH_SIZE == 0 or i == len(db_pages):
                logger.info(
                    f"  Progress: {i}/{len(db_pages)} pages | "
                    f"{stats['total_properties_created']} embeddings created | "
                    f"{stats['already_embedded_properties']} already exist"
                )

            stats['pages_with_properties'] += 1

            # Get property values for this page from table columns
            try:
                with sqlite3.connect("data/hybrid_metadata.db") as conn:
                    cursor = conn.cursor()

                    # Build query to fetch page with properties
                    column_names = [prop['column_name'] for prop in embeddable_props]
                    columns_str = ', '.join(column_names)
                    query = f"SELECT {columns_str} FROM {table_name} WHERE page_id = ?"

                    cursor.execute(query, (page_id,))
                    row = cursor.fetchone()

                    if not row:
                        continue

                    # Process each embeddable property
                    props_created = 0
                    for idx, prop_schema_item in enumerate(embeddable_props):
                        col_name = prop_schema_item['column_name']
                        prop_type = prop_schema_item['notion_type']
                        value = row[idx]

                        if value is None or value == '':
                            continue

                        # Check if property embedding already exists
                        vector_id = f"{page_id}_prop_{col_name}"

                        if skip_existing:
                            try:
                                existing = vector_db.property_collection.get(ids=[vector_id])
                                if existing['ids']:
                                    stats['already_embedded_properties'] += 1
                                    continue
                            except:
                                pass  # Not found, proceed

                        # Format value for embedding
                        formatted_value = _format_property_for_embedding(
                            value, prop_type, page_id, registry
                        )

                        if not formatted_value:
                            continue

                        if dry_run:
                            logger.debug(f"[DRY RUN] Would embed property: {page_id}.{col_name}")
                            props_created += 1
                            continue

                        # Create property embedding with retry logic
                        success = _add_property_embedding_with_retry(
                            vector_db=vector_db,
                            page_id=page_id,
                            property_name=col_name,
                            property_value=formatted_value,
                            property_type=prop_type,
                            base_metadata={
                                'workspace': page['workspace'],
                                'database_name': page['database_name'],
                                'database_id': page.get('database_id'),
                                'content_type': page.get('content_type')
                            },
                            rate_limit_delay=rate_limit_delay
                        )

                        if success:
                            props_created += 1
                            logger.debug(f"  ✅ Created property embedding: {page_id}.{col_name}")
                        else:
                            logger.warning(f"  ❌ Failed to create embedding for {page_id}.{col_name}")

                    if props_created > 0:
                        stats['newly_embedded_properties'] += props_created
                        stats['total_properties_created'] += props_created
                        total_properties_in_db += props_created

                    # Add batch delay after processing BATCH_SIZE properties
                    if total_properties_in_db > 0 and total_properties_in_db % BATCH_SIZE == 0:
                        logger.debug(f"  Batch complete ({total_properties_in_db} embeddings), pausing {batch_delay}s...")
                        time.sleep(batch_delay)

            except Exception as e:
                logger.error(f"  Failed to process page {page_id}: {e}")
                stats['failed_pages'] += 1

    # Print summary
    print("\n" + "="*60)
    print("PROPERTY EMBEDDINGS SYNC SUMMARY")
    print("="*60)
    print(f"Total pages processed:         {stats['total_pages']}")
    print(f"Pages with properties:         {stats['pages_with_properties']}")
    print(f"Already embedded properties:   {stats['already_embedded_properties']}")
    print(f"Newly embedded properties:     {stats['total_properties_created']}")
    print(f"Failed pages:                  {stats['failed_pages']}")
    print(f"Skipped (no schema):           {stats['skipped_no_schema']}")
    print("="*60)

    if dry_run:
        print("\n💡 This was a DRY RUN. No changes were made.")
        print("   Run without --dry-run to perform the sync.")


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Sync property embeddings for all existing database content"
    )
    parser.add_argument(
        '--workspace',
        type=str,
        help='Filter by workspace'
    )
    parser.add_argument(
        '--database',
        type=str,
        help='Filter by database name'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Analyze without making changes'
    )
    parser.add_argument(
        '--force',
        action='store_true',
        help='Re-embed properties that already exist'
    )
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Show detailed debug output'
    )
    parser.add_argument(
        '--rate-limit-delay',
        type=float,
        default=RATE_LIMIT_DELAY,
        help=f'Delay in seconds between embedding API calls (default: {RATE_LIMIT_DELAY}s). '
             'Decrease for faster processing if you have higher rate limits.'
    )
    parser.add_argument(
        '--batch-delay',
        type=float,
        default=BATCH_DELAY,
        help=f'Delay in seconds between batches of {BATCH_SIZE} embeddings (default: {BATCH_DELAY}s)'
    )

    args = parser.parse_args()

    # Set log level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Run sync
    sync_property_embeddings(
        workspace=args.workspace,
        database_name=args.database,
        dry_run=args.dry_run,
        skip_existing=not args.force,
        rate_limit_delay=args.rate_limit_delay,
        batch_delay=args.batch_delay
    )


if __name__ == "__main__":
    main()
