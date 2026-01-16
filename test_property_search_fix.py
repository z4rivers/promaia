#!/usr/bin/env python3
"""Test that property search works with updated HNSW parameters."""
import sys
sys.path.insert(0, '/Users/kb20250422/Documents/dev/promaia')

from promaia.storage.vector_db import VectorDBManager

# Initialize vector DB
vector_db = VectorDBManager(chroma_path="chroma_db")

print("🧪 Testing property search with updated HNSW parameters...")
print(f"   Property collection count: {vector_db.property_collection.count()}")
print(f"   HNSW parameters: {vector_db.property_collection.metadata}\n")

# Test the original failing query
try:
    print("🔍 Testing property search: epic='2025 Holiday Launch' in trass.stories")
    results = vector_db.search_property(
        property_name="epic",
        query_text="2025 Holiday Launch",
        filters={
            "$and": [
                {"workspace": "trass"},
                {"database_name": "stories"}
            ]
        },
        n_results=60,
        min_similarity=0.5
    )

    print(f"✅ Property search succeeded!")
    print(f"   Found {len(results)} results")

    if results:
        print(f"\n📋 Sample results:")
        for i, result in enumerate(results[:5], 1):
            print(f"   {i}. Page: {result['page_id'][:8]}... | Similarity: {result['similarity_score']:.3f} | Value: {result['property_value'][:50]}...")
    else:
        print("   ℹ️  No results found (may be expected if no pages match)")

    print("\n🎉 SUCCESS! Property search is working without errors.")

except Exception as e:
    print(f"\n❌ ERROR: Property search failed with: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
