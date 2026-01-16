#!/usr/bin/env python3
"""
Sync all existing database content to vector embeddings.

This script:
1. Queries all pages from the unified_content table
2. For each page, checks if it has an embedding in ChromaDB
3. If not, reads the markdown file and embeds it
4. Uses chunking for large pages (>6000 tokens)
"""
import os
import sys
import json
import logging
from typing import Dict, Any, List

# Add promaia to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from promaia.storage.hybrid_storage import get_hybrid_registry
from promaia.storage.vector_db import VectorDBManager
from promaia.storage.page_chunker import chunk_page_content, estimate_tokens

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def load_config() -> Dict[str, Any]:
    """Load configuration from promaia.config.json."""
    config_path = "promaia.config.json"
    try:
        with open(config_path, 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load config: {e}")
        sys.exit(1)


def sync_all_embeddings(
    workspace: str = None,
    database_name: str = None,
    dry_run: bool = False,
    skip_existing: bool = True
):
    """
    Sync all database content to vector embeddings.
    
    Args:
        workspace: Optional workspace filter
        database_name: Optional database filter  
        dry_run: If True, only analyze without making changes
        skip_existing: If True, skip pages that already have embeddings
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
    
    # Get chunking config
    chunking_config = vector_config.get('chunking', {})
    chunking_enabled = chunking_config.get('enabled', True)
    max_tokens = chunking_config.get('max_tokens_per_chunk', 6000)
    
    # Get all pages from unified_content
    logger.info("Querying all pages from unified_content...")
    
    try:
        import sqlite3
        with sqlite3.connect("data/hybrid_metadata.db") as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Build query with optional filters
            query = "SELECT page_id, file_path, workspace, database_name, created_time FROM unified_content"
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
        'already_embedded': 0,
        'newly_embedded': 0,
        'chunked_pages': 0,
        'failed_pages': 0,
        'missing_files': 0,
        'empty_files': 0,
        'total_chunks_created': 0
    }
    
    # Process each page
    for i, page in enumerate(pages, 1):
        page_id = page['page_id']
        file_path = page['file_path']
        
        if i % 100 == 0:
            logger.info(f"Progress: {i}/{len(pages)} pages processed...")
        
        # Check if already embedded (if skip_existing is True)
        if skip_existing:
            try:
                existing = vector_db.collection.get(ids=[page_id])
                if existing['ids']:
                    stats['already_embedded'] += 1
                    logger.debug(f"Skipping {page_id}: already embedded")
                    continue
            except:
                pass  # Not found, proceed with embedding
        
        # Check if file exists
        if not os.path.exists(file_path):
            stats['missing_files'] += 1
            logger.debug(f"Skipping {page_id}: File not found at {file_path}")
            continue
        
        # Read content
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception as e:
            logger.warning(f"Failed to read {file_path}: {e}")
            stats['failed_pages'] += 1
            continue
        
        # Skip empty or very short content
        if not content or len(content.strip()) < 10:
            stats['empty_files'] += 1
            continue
        
        if dry_run:
            logger.debug(f"[DRY RUN] Would embed: {page_id}")
            stats['newly_embedded'] += 1
            continue
        
        # Estimate tokens
        estimated_tokens = estimate_tokens(content, provider=vector_db.embedding_provider)
        
        # Prepare metadata
        metadata = {
            'database_name': page['database_name'],
            'workspace': page['workspace'],
            'created_time': page.get('created_time', ''),
            'content_type': page['database_name'],
        }
        
        # Determine if chunking is needed
        if chunking_enabled and estimated_tokens > max_tokens:
            # Use chunking
            try:
                from datetime import datetime
                
                chunks = chunk_page_content(
                    markdown_content=content,
                    page_id=page_id,
                    block_metadata=None,
                    max_tokens=max_tokens,
                    provider=vector_db.embedding_provider
                )
                
                if not chunks:
                    logger.error(f"Failed to chunk {page_id}")
                    stats['failed_pages'] += 1
                    continue
                
                # Store chunks in database
                synced_time = datetime.utcnow().isoformat()
                for chunk in chunks:
                    chunk_data = {
                        'chunk_id': chunk['chunk_id'],
                        'page_id': page_id,
                        'chunk_index': chunk['chunk_index'],
                        'total_chunks': chunk['total_chunks'],
                        'workspace': page['workspace'],
                        'database_name': page['database_name'],
                        'char_start': chunk['char_start'],
                        'char_end': chunk['char_end'],
                        'estimated_tokens': chunk['estimated_tokens'],
                        'date_boundary': chunk.get('date_boundary'),
                        'parent_file_path': file_path,
                        'created_time': page.get('created_time'),
                        'synced_time': synced_time
                    }
                    registry.add_page_chunk(chunk_data)
                
                # Embed chunks
                success = vector_db.add_content_with_chunking(
                    page_id=page_id,
                    content_text=content,
                    metadata=metadata,
                    chunks=chunks
                )
                
                if success:
                    stats['chunked_pages'] += 1
                    stats['newly_embedded'] += 1
                    stats['total_chunks_created'] += len(chunks)
                    logger.debug(f"✅ Chunked and embedded {page_id}: {len(chunks)} chunks")
                else:
                    stats['failed_pages'] += 1
                    logger.error(f"❌ Failed to embed chunks for {page_id}")
                    
            except Exception as e:
                logger.error(f"Error chunking {page_id}: {e}")
                stats['failed_pages'] += 1
        else:
            # Standard single embedding
            try:
                success = vector_db.add_content(
                    page_id=page_id,
                    content_text=content,
                    metadata=metadata
                )
                
                if success:
                    stats['newly_embedded'] += 1
                    logger.debug(f"✅ Embedded {page_id} ({estimated_tokens} tokens)")
                else:
                    stats['failed_pages'] += 1
                    logger.error(f"❌ Failed to embed {page_id}")
                    
            except Exception as e:
                logger.error(f"Error embedding {page_id}: {e}")
                stats['failed_pages'] += 1
    
    # Print summary
    print("\n" + "="*60)
    print("EMBEDDING SYNC SUMMARY")
    print("="*60)
    print(f"Total pages processed:     {stats['total_pages']}")
    print(f"Already embedded:          {stats['already_embedded']}")
    print(f"Newly embedded:            {stats['newly_embedded']}")
    print(f"  - Standard embeddings:   {stats['newly_embedded'] - stats['chunked_pages']}")
    print(f"  - Chunked pages:         {stats['chunked_pages']}")
    print(f"  - Total chunks created:  {stats['total_chunks_created']}")
    print(f"Failed:                    {stats['failed_pages']}")
    print(f"Skipped (missing files):   {stats['missing_files']}")
    print(f"Skipped (empty):           {stats['empty_files']}")
    print("="*60)
    
    if dry_run:
        print("\n💡 This was a DRY RUN. No changes were made.")
        print("   Run without --dry-run to perform the sync.")


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Sync all existing database content to vector embeddings"
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
        help='Re-embed pages that already have embeddings'
    )
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Show detailed debug output'
    )
    
    args = parser.parse_args()
    
    # Set log level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Run sync
    sync_all_embeddings(
        workspace=args.workspace,
        database_name=args.database,
        dry_run=args.dry_run,
        skip_existing=not args.force
    )


if __name__ == "__main__":
    main()
