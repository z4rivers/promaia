#!/usr/bin/env python3
"""
Inspect final remaining old property names.
"""
import os
import sys
import sqlite3

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from promaia.storage.vector_db import VectorDBManager

def check_property_in_sql(database_id, column_name):
    """Check if this property exists in SQL schema."""
    db_path = "data/hybrid_metadata.db"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT property_name, notion_type, is_active
        FROM notion_property_schema
        WHERE database_id = ? AND column_name = ?
    """, (database_id, column_name))

    result = cursor.fetchone()
    conn.close()

    return result

def get_page_info(page_id):
    """Look up page info."""
    db_path = "data/hybrid_metadata.db"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT database_id, database_name
        FROM unified_content
        WHERE page_id = ?
    """, (page_id,))

    result = cursor.fetchone()
    conn.close()

    return result if result else (None, None)

def main():
    vector_db = VectorDBManager()

    # Check remaining
    for prop_name in ['name', 'name_3']:
        results = vector_db.property_collection.get(
            where={"property_name": prop_name},
            include=['metadatas']
        )

        if not results['ids']:
            continue

        print(f"\n📌 property_name='{prop_name}' ({len(results['ids'])} embeddings):\n")

        for i, vector_id in enumerate(results['ids']):
            metadata = results['metadatas'][i]
            db_id_meta = metadata.get('database_id', 'N/A')
            page_id = vector_id.replace(f'_prop_{prop_name}', '')

            db_id_sql, db_name = get_page_info(page_id)

            print(f"{i+1}. page_id: {page_id[:40]}...")
            print(f"   database_id (meta): {db_id_meta}")
            print(f"   database_id (SQL): {db_id_sql}")
            print(f"   database_name: {db_name}")

            if db_id_sql:
                prop_info = check_property_in_sql(db_id_sql, prop_name)
                if prop_info:
                    print(f"   SQL schema: property_name={prop_info[0]}, notion_type={prop_info[1]}, is_active={prop_info[2]}")
                else:
                    print(f"   SQL schema: Not found")
            print()

if __name__ == "__main__":
    main()
