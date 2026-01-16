#!/usr/bin/env python3
"""
Check which databases still have old-style property names.
"""
import os
import sys
import sqlite3

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from promaia.storage.vector_db import VectorDBManager

def get_title_databases():
    """Get all databases that have title properties."""
    db_path = "data/hybrid_metadata.db"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT database_id, column_name, notion_type, is_active
        FROM notion_property_schema
        WHERE notion_type = 'title'
        ORDER BY database_id
    """)

    results = cursor.fetchall()
    conn.close()
    return results

def main():
    vector_db = VectorDBManager()

    # Check old property names
    old_names = ['name', 'name_2', 'name_3', 'name_4', 'epic_name']

    print("🔍 Checking unmigrated properties...\n")

    for old_name in old_names:
        results = vector_db.property_collection.get(
            where={"property_name": old_name},
            include=['metadatas']
        )

        if results['ids']:
            print(f"📌 property_name='{old_name}' ({len(results['ids'])} embeddings):")
            # Group by database
            db_counts = {}
            for metadata in results['metadatas']:
                db_id = metadata.get('database_id', 'unknown')
                db_counts[db_id] = db_counts.get(db_id, 0) + 1

            for db_id, count in sorted(db_counts.items()):
                print(f"   {db_id}: {count} embeddings")
            print()

    # Check SQL schema
    print("\n📋 SQL Schema - All title properties:")
    title_dbs = get_title_databases()
    for db_id, col_name, notion_type, is_active in title_dbs:
        status = "✅ active" if is_active else "❌ inactive"
        print(f"   {db_id}: column={col_name}, {status}")

if __name__ == "__main__":
    main()
