#!/usr/bin/env python3
"""
Migration script to backfill existing content into ChromaDB for vector search.

This script:
1. Queries all content from unified_content table
2. Reads markdown files for each page_id
3. Generates embeddings and stores in ChromaDB
4. Shows progress and allows resuming from interruptions

Usage:
    python3 migrate_to_vector_db.py [--limit N] [--resume]
"""
import sys
import os
import sqlite3
import argparse
from pathlib import Path
from typing import List, Dict, Any
from tqdm import tqdm

# Add project to path
sys.path.insert(0, str(Path(__file__).parent))

from promaia.utils.config import load_environment
from promaia.storage.vector_db import VectorDBManager
from promaia.utils.display import print_text

# Load environment
load_environment()


def get_all_content(db_path: str = "data/hybrid_metadata.db") -> List[Dict[str, Any]]:
    """
    Query all content from unified_content view.
    
    Returns list of dicts with page_id, file_path, database_name, workspace, etc.
    """
    try:
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            query = """
            SELECT 
                page_id,
                file_path,
                database_name,
                workspace,
                created_time,
                content_type
            FROM unified_content
            WHERE file_path IS NOT NULL
            ORDER BY created_time DESC
            """
            
            cursor.execute(query)
            rows = cursor.fetchall()
            
            return [dict(row) for row in rows]
    
    except Exception as e:
        print_text(f"❌ Error querying database: {e}", style="red")
        return []


def read_markdown_content(file_path: str) -> str:
    """Read markdown content from file."""
    try:
        if not os.path.exists(file_path):
            return ""
        
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        return content
    
    except Exception as e:
        return ""


def migrate_content(
    vector_db: VectorDBManager,
    content_items: List[Dict[str, Any]],
    resume: bool = False
) -> Dict[str, int]:
    """
    Migrate content to ChromaDB with progress tracking.
    
    Args:
        vector_db: VectorDBManager instance
        content_items: List of content items from unified_content
        resume: If True, skip items that already exist in ChromaDB
    
    Returns:
        Dict with counts: {embedded, skipped, failed, total}
    """
    stats = {
        'embedded': 0,
        'skipped': 0,
        'failed': 0,
        'total': len(content_items)
    }
    
    print_text(f"\n📊 Migration Stats:", style="bold cyan")
    print_text(f"   Total items to process: {stats['total']}", style="white")
    
    if resume:
        print_text(f"   Resume mode: Will skip existing embeddings", style="yellow")
    
    print()
    
    # Process with progress bar
    with tqdm(total=stats['total'], desc="Embedding content", unit="items") as pbar:
        for item in content_items:
            page_id = item['page_id']
            file_path = item['file_path']
            
            try:
                # Check if already exists (for resume)
                if resume and vector_db.check_exists(page_id):
                    stats['skipped'] += 1
                    pbar.update(1)
                    continue
                
                # Read markdown content
                content_text = read_markdown_content(file_path)
                
                if not content_text or len(content_text.strip()) < 10:
                    stats['failed'] += 1
                    pbar.update(1)
                    continue
                
                # Prepare metadata
                metadata = {
                    'database_name': item.get('database_name', ''),
                    'workspace': item.get('workspace', ''),
                    'created_time': item.get('created_time', ''),
                    'content_type': item.get('content_type', ''),
                }
                
                # Add to vector DB
                success = vector_db.add_content(
                    page_id=page_id,
                    content_text=content_text,
                    metadata=metadata
                )
                
                if success:
                    stats['embedded'] += 1
                else:
                    stats['failed'] += 1
            
            except Exception as e:
                stats['failed'] += 1
                # Continue processing other items
            
            pbar.update(1)
    
    return stats


def main():
    """Main migration script."""
    parser = argparse.ArgumentParser(
        description="Migrate existing content to ChromaDB for vector search"
    )
    parser.add_argument(
        '--limit',
        type=int,
        default=None,
        help='Limit number of items to process (for testing)'
    )
    parser.add_argument(
        '--resume',
        action='store_true',
        help='Skip items that already exist in ChromaDB'
    )
    parser.add_argument(
        '--db-path',
        type=str,
        default='data/hybrid_metadata.db',
        help='Path to hybrid metadata database'
    )
    
    args = parser.parse_args()
    
    print_text("\n🚀 Vector Database Migration", style="bold green")
    print_text("=" * 60, style="dim")
    
    # Check config - load from main config file
    import json
    config_path = "promaia.config.json"
    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
        vector_config = config.get('global', {}).get('vector_search', {})
    except Exception as e:
        print_text(f"\n⚠️  Could not load config from {config_path}: {e}", style="yellow")
        vector_config = {}
    
    if not vector_config.get('enabled', False):
        print_text("\n⚠️  Vector search is disabled in config", style="yellow")
        print_text("   Enable it in promaia.config.json to use vector search", style="dim")
        # Check if running interactively
        if sys.stdin.isatty():
            response = input("\n   Continue anyway? [y/N]: ")
            if response.lower() != 'y':
                print_text("   Migration cancelled", style="dim")
                return
        else:
            print_text("\n   Continuing in non-interactive mode...", style="dim")
    
    # Initialize vector DB
    print_text("\n📦 Initializing vector database...", style="cyan")
    try:
        chroma_path = vector_config.get('chroma_path', 'chroma_db')
        vector_db = VectorDBManager(chroma_path=chroma_path)
        
        stats = vector_db.get_stats()
        print_text(f"   Provider: {stats.get('embedding_provider', 'unknown')}", style="white")
        print_text(f"   Model: {stats.get('embedding_model', 'unknown')}", style="white")
        print_text(f"   Existing documents: {stats.get('total_documents', 0)}", style="white")
        
    except Exception as e:
        print_text(f"\n❌ Failed to initialize vector DB: {e}", style="red")
        print_text("   Make sure dependencies are installed: pip install chromadb sentence-transformers", style="dim")
        return
    
    # Get all content
    print_text(f"\n📖 Querying content from {args.db_path}...", style="cyan")
    content_items = get_all_content(args.db_path)
    
    if not content_items:
        print_text("   No content found to migrate", style="yellow")
        return
    
    # Apply limit if specified
    if args.limit:
        content_items = content_items[:args.limit]
        print_text(f"   Limited to first {args.limit} items", style="yellow")
    
    # Start migration
    print_text(f"\n⚡ Starting migration...", style="cyan")
    stats = migrate_content(vector_db, content_items, resume=args.resume)
    
    # Show results
    print_text("\n" + "=" * 60, style="dim")
    print_text("✅ Migration Complete!", style="bold green")
    print_text("=" * 60, style="dim")
    print_text(f"\n📊 Results:", style="bold white")
    print_text(f"   Total processed: {stats['total']}", style="white")
    print_text(f"   ✅ Successfully embedded: {stats['embedded']}", style="green")
    
    if stats['skipped'] > 0:
        print_text(f"   ⏭️  Skipped (already exist): {stats['skipped']}", style="yellow")
    
    if stats['failed'] > 0:
        print_text(f"   ❌ Failed: {stats['failed']}", style="red")
    
    # Final stats
    final_stats = vector_db.get_stats()
    print_text(f"\n📚 ChromaDB now contains {final_stats.get('total_documents', 0)} documents", style="cyan")
    
    print_text("\n🎉 You can now use vector search with: maia chat -vs 'your search query'", style="bold green")
    print()


if __name__ == "__main__":
    main()
