#!/usr/bin/env python3
"""
Verify that title property embeddings are using standardized naming.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from promaia.storage.vector_db import VectorDBManager

def main():
    vector_db = VectorDBManager()

    # Query property embeddings with property_name='title'
    title_results = vector_db.property_collection.get(
        where={"property_name": "title"},
        include=['metadatas']
    )

    print(f"✅ Found {len(title_results['ids'])} embeddings with property_name='title'")

    # Group by database
    db_counts = {}
    for metadata in title_results['metadatas']:
        db_id = metadata.get('database_id', 'unknown')
        db_counts[db_id] = db_counts.get(db_id, 0) + 1

    print("\n📊 Title embeddings by database:")
    for db_id, count in sorted(db_counts.items(), key=lambda x: x[1], reverse=True):
        print(f"   {db_id[:8]}...: {count} title embeddings")

    # Check for old-style property names that should have been migrated
    old_names = ['name', 'name_2', 'name_3', 'name_4', 'epic_name']
    print(f"\n🔍 Checking for unmigrated title properties...")

    found_old = False
    for old_name in old_names:
        old_results = vector_db.property_collection.get(
            where={"property_name": old_name},
            limit=5,
            include=['metadatas']
        )
        if old_results['ids']:
            print(f"   ⚠️  Found {len(old_results['ids'])} embeddings with property_name='{old_name}'")
            found_old = True

    if not found_old:
        print("   ✅ No old-style title property names found - migration successful!")

if __name__ == "__main__":
    main()
