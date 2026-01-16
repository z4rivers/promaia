#!/usr/bin/env python3
"""Debug ChromaDB to see what's actually stored."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from promaia.utils.config import load_environment
load_environment()

import chromadb

print("🔍 Debugging ChromaDB Contents\n")
print("=" * 60)

# Connect to ChromaDB
client = chromadb.PersistentClient(path="chroma_db")
collection = client.get_or_create_collection(name="promaia_content")

print(f"Collection: {collection.name}")
print(f"Count: {collection.count()}")

# Get a few documents
results = collection.get(limit=5, include=["documents", "metadatas"])

print(f"\n📄 First {min(5, len(results['ids']))} Documents:")
for i, (doc_id, metadata) in enumerate(zip(results['ids'], results['metadatas']), 1):
    print(f"\n{i}. ID: {doc_id}")
    print(f"   Database: {metadata.get('database_name', 'N/A')}")
    print(f"   Workspace: {metadata.get('workspace', 'N/A')}")
    print(f"   Content Type: {metadata.get('content_type', 'N/A')}")
    doc = results['documents'][i-1] if i-1 < len(results['documents']) else ""
    print(f"   Content Preview: {doc[:100]}..." if doc else "   Content: Empty")

# Try a simple query
print("\n" + "=" * 60)
print("🔍 Testing Simple Query...")

from promaia.storage.vector_db import VectorDBManager
vdb = VectorDBManager(chroma_path="chroma_db")

# Generate an embedding for the query
query_text = "email"
print(f"\nQuery: '{query_text}'")
results = vdb.search(query_text=query_text, n_results=5, min_similarity=0.0)

print(f"Results: {len(results)}")
if results:
    for r in results[:3]:
        print(f"  - Similarity: {r['similarity_score']:.3f}, DB: {r['metadata'].get('database_name')}")
