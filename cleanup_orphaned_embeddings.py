#!/usr/bin/env python3
"""
Clean up orphaned property embeddings where the page no longer exists in unified_content.
"""
import os
import sys
import sqlite3

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from promaia.storage.vector_db import VectorDBManager

def page_exists(page_id):
    """Check if page exists in unified_content."""
    db_path = "data/hybrid_metadata.db"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("SELECT 1 FROM unified_content WHERE page_id = ?", (page_id,))
    result = cursor.fetchone()
    conn.close()

    return result is not None

def main():
    print("🧹 Cleaning up orphaned property embeddings...")

    vector_db = VectorDBManager()

    # Get all property embeddings
    all_results = vector_db.property_collection.get(include=['metadatas'])

    print(f"📊 Checking {len(all_results['ids'])} property embeddings...")

    orphaned = []

    for i, vector_id in enumerate(all_results['ids']):
        metadata = all_results['metadatas'][i]
        prop_name = metadata.get('property_name', 'unknown')

        # Extract page_id from vector_id
        page_id = vector_id.rsplit('_prop_', 1)[0]

        # Check if page exists
        if not page_exists(page_id):
            orphaned.append({
                'vector_id': vector_id,
                'page_id': page_id,
                'property_name': prop_name
            })

        if (i + 1) % 500 == 0:
            print(f"  Checked {i + 1}/{len(all_results['ids'])}...")

    print(f"\n🎯 Found {len(orphaned)} orphaned embeddings")

    if len(orphaned) == 0:
        print("✅ No cleanup needed")
        return

    # Delete orphaned embeddings
    print("🗑️  Deleting orphaned embeddings...")
    ids_to_delete = [item['vector_id'] for item in orphaned]

    try:
        vector_db.property_collection.delete(ids=ids_to_delete)
        print(f"✅ Deleted {len(ids_to_delete)} orphaned embeddings")
    except Exception as e:
        print(f"❌ Error deleting embeddings: {e}")

if __name__ == "__main__":
    main()
