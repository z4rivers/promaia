#!/usr/bin/env python3
"""
Migrate title property embeddings that have database_id='unknown'.

These embeddings were created before we properly tracked database_id in metadata.
We'll look up the correct database_id from the unified_content table and migrate them.
"""
import os
import sys
import sqlite3

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from promaia.storage.vector_db import VectorDBManager

def get_page_database_id(page_id: str) -> str:
    """Look up database_id for a page_id in unified_content."""
    db_path = "data/hybrid_metadata.db"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("SELECT database_id FROM unified_content WHERE page_id = ?", (page_id,))
    result = cursor.fetchone()
    conn.close()

    return result[0] if result else None

def get_title_column_for_database(database_id: str) -> str:
    """Get the title column name for a database."""
    db_path = "data/hybrid_metadata.db"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT column_name
        FROM notion_property_schema
        WHERE database_id = ? AND notion_type = 'title' AND is_active = 1
    """, (database_id,))

    result = cursor.fetchone()
    conn.close()

    return result[0] if result else None

def main():
    print("🔄 Migrating title properties with unknown database_id...")

    vector_db = VectorDBManager()

    # Get all property embeddings with old column names and unknown database
    old_names = ['name', 'name_2', 'name_3', 'name_4', 'epic_name', 'name_1']

    to_migrate = []

    for old_name in old_names:
        # Get all embeddings with this property name (no database_id filter)
        results = vector_db.property_collection.get(
            where={"property_name": old_name},
            include=['metadatas', 'embeddings', 'documents']
        )

        for i, vector_id in enumerate(results['ids']):
            metadata = results['metadatas'][i]
            embedding = results['embeddings'][i]
            document = results['documents'][i] if results['documents'] else None

            # Only process if database_id is missing or unknown
            db_id_meta = metadata.get('database_id')
            if db_id_meta and db_id_meta != 'unknown':
                continue  # Skip - already has correct database_id

            # Extract page_id from vector_id
            page_id = vector_id.replace(f'_prop_{old_name}', '')

            # Look up correct database_id
            db_id = get_page_database_id(page_id)

            if db_id:
                # Check if this database has a title property with this column name
                title_col = get_title_column_for_database(db_id)

                if title_col == old_name:
                    # This is a title property that needs migration
                    to_migrate.append({
                        'old_id': vector_id,
                        'new_id': f'{page_id}_prop_title',
                        'page_id': page_id,
                        'database_id': db_id,
                        'embedding': embedding,
                        'metadata': metadata,
                        'document': document
                    })

    print(f"🎯 Found {len(to_migrate)} title properties to migrate")

    if len(to_migrate) == 0:
        print("✅ No migration needed")
        return

    # Perform migration
    migrated = 0
    errors = 0

    for item in to_migrate:
        try:
            # Update metadata with correct database_id and property_name
            new_metadata = item['metadata'].copy()
            new_metadata['database_id'] = item['database_id']
            new_metadata['property_name'] = 'title'

            # Add new embedding
            vector_db.property_collection.add(
                ids=[item['new_id']],
                embeddings=[item['embedding']],
                metadatas=[new_metadata],
                documents=[item['document']] if item['document'] else None
            )

            # Delete old embedding
            vector_db.property_collection.delete(ids=[item['old_id']])

            migrated += 1
            if migrated % 50 == 0:
                print(f"  Migrated {migrated}/{len(to_migrate)}...")

        except Exception as e:
            if "Insert of existing embedding ID" in str(e):
                # Already exists, just delete the old one
                vector_db.property_collection.delete(ids=[item['old_id']])
                migrated += 1
            else:
                print(f"❌ Error migrating {item['old_id']}: {e}")
                errors += 1

    print(f"\n✅ Migration complete!")
    print(f"   Migrated: {migrated}")
    print(f"   Errors: {errors}")

if __name__ == "__main__":
    main()
