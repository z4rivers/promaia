#!/usr/bin/env python3
"""
Migrate existing title property embeddings to use standardized 'title' property name.

This script:
1. Queries all property embeddings from ChromaDB
2. Identifies title-type properties (by checking SQL schema)
3. Updates their IDs and metadata to use 'title' instead of column name
4. No re-embedding needed - just renaming the existing embeddings
"""
import os
import sys
import json
import sqlite3
from typing import Dict, Set

# Add promaia to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from promaia.storage.vector_db import VectorDBManager

def get_title_column_names() -> Dict[str, str]:
    """
    Get mapping of database_id -> title column name from SQL schema.
    Returns: {database_id: column_name}
    """
    db_path = "data/hybrid_metadata.db"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT database_id, column_name
        FROM notion_property_schema
        WHERE notion_type = 'title' AND is_active = 1
    """)

    title_columns = {}
    for db_id, col_name in cursor.fetchall():
        title_columns[db_id] = col_name

    conn.close()
    return title_columns

def main():
    print("🔄 Migrating title property embeddings to standardized naming...")

    # Get title column names from SQL
    title_columns = get_title_column_names()
    print(f"📋 Found {len(title_columns)} databases with title properties")

    # Initialize vector DB
    vector_db = VectorDBManager()

    # Get all property embeddings
    print("📊 Querying all property embeddings...")
    all_results = vector_db.property_collection.get(include=['metadatas'])

    ids = all_results['ids']
    metadatas = all_results['metadatas']

    print(f"Found {len(ids)} total property embeddings")

    # Find title properties that need migration
    to_update = []

    for i, (vector_id, metadata) in enumerate(zip(ids, metadatas)):
        database_id = metadata.get('database_id')
        property_name = metadata.get('property_name')

        # Check if this is a title property that needs migration
        if database_id in title_columns:
            expected_col = title_columns[database_id]

            # If property_name matches the old column name, it needs migration
            if property_name == expected_col and property_name != 'title':
                # Extract page_id from vector_id
                page_id = vector_id.replace(f'_prop_{property_name}', '')
                new_vector_id = f'{page_id}_prop_title'

                to_update.append({
                    'old_id': vector_id,
                    'new_id': new_vector_id,
                    'page_id': page_id,
                    'database_id': database_id,
                    'old_property_name': property_name
                })

    print(f"🎯 Found {len(to_update)} title properties to migrate")

    if len(to_update) == 0:
        print("✅ No migration needed - all title properties already use standardized naming")
        return

    # Perform migration
    print("🔧 Starting migration...")
    migrated = 0
    errors = 0

    for item in to_update:
        try:
            # Get the existing embedding and metadata
            result = vector_db.property_collection.get(
                ids=[item['old_id']],
                include=['embeddings', 'metadatas', 'documents']
            )

            if not result['ids']:
                print(f"⚠️  Skipping {item['old_id']} - not found")
                continue

            # Extract data
            embedding = result['embeddings'][0]
            metadata = result['metadatas'][0]
            document = result['documents'][0] if result['documents'] else None

            # Update metadata to use 'title' as property_name
            metadata['property_name'] = 'title'

            # Add new embedding with updated ID
            vector_db.property_collection.add(
                ids=[item['new_id']],
                embeddings=[embedding],
                metadatas=[metadata],
                documents=[document] if document else None
            )

            # Delete old embedding
            vector_db.property_collection.delete(ids=[item['old_id']])

            migrated += 1
            if migrated % 100 == 0:
                print(f"  Migrated {migrated}/{len(to_update)}...")

        except Exception as e:
            print(f"❌ Error migrating {item['old_id']}: {e}")
            errors += 1

    print(f"\n✅ Migration complete!")
    print(f"   Migrated: {migrated}")
    print(f"   Errors: {errors}")
    print(f"   Total processed: {len(to_update)}")

if __name__ == "__main__":
    main()
