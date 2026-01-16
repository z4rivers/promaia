#!/usr/bin/env python3
"""
Inspect embeddings with unknown database_id to see if they're title properties.
"""
import os
import sys
import sqlite3

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from promaia.storage.vector_db import VectorDBManager

def get_page_info(page_id: str):
    """Look up page info in unified_content."""
    db_path = "data/hybrid_metadata.db"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT database_id, database_name, title
        FROM unified_content
        WHERE page_id = ?
    """, (page_id,))

    result = cursor.fetchone()
    conn.close()

    return result if result else (None, None, None)

def main():
    vector_db = VectorDBManager()

    # Check one old property name
    results = vector_db.property_collection.get(
        where={"property_name": "name"},
        limit=10,
        include=['metadatas']
    )

    print(f"📊 Inspecting {len(results['ids'])} 'name' property embeddings:\n")

    for i, vector_id in enumerate(results['ids']):
        metadata = results['metadatas'][i]
        prop_name = metadata.get('property_name')
        db_id_meta = metadata.get('database_id', 'N/A')
        notion_type = metadata.get('notion_type', 'N/A')

        # Extract page_id
        page_id = vector_id.replace(f'_prop_{prop_name}', '')

        # Look up in unified_content
        db_id_sql, db_name, title = get_page_info(page_id)

        print(f"{i+1}. vector_id: {vector_id[:40]}...")
        print(f"   property_name: {prop_name}")
        print(f"   notion_type: {notion_type}")
        print(f"   database_id (metadata): {db_id_meta}")
        print(f"   database_id (SQL): {db_id_sql}")
        print(f"   database_name: {db_name}")
        print(f"   page_title: {title[:50] if title else 'N/A'}...")
        print()

if __name__ == "__main__":
    main()
