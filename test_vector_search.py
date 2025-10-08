#!/usr/bin/env python3
"""Quick test of vector search functionality."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from promaia.utils.config import load_environment
load_environment()

from promaia.storage.vector_db import VectorDBManager

# Test ChromaDB
print("🧪 Testing Vector Search\n")
print("=" * 60)

# Initialize
print("\n1. Initializing VectorDBManager...")
vdb = VectorDBManager(chroma_path="chroma_db")

# Get stats
stats = vdb.get_stats()
print(f"   ✅ Provider: {stats['embedding_provider']}")
print(f"   ✅ Model: {stats['embedding_model']}")
print(f"   ✅ Total documents: {stats['total_documents']}")

# Test search
print("\n2. Testing search...")
query = "international launch stories"
print(f"   Query: '{query}'")

results = vdb.search(
    query_text=query,
    n_results=10,
    min_similarity=0.0  # Lower threshold to see any results
)

print(f"   ✅ Found {len(results)} results")

if results:
    print("\n3. Top results:")
    for i, result in enumerate(results[:5], 1):
        print(f"   {i}. Similarity: {result['similarity_score']:.3f}")
        print(f"      Page ID: {result['page_id']}")
        print(f"      Database: {result['metadata'].get('database_name', 'unknown')}")
        print()
else:
    print("   ⚠️  No results found")

print("=" * 60)
print("✅ Test complete!")
