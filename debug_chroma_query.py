#!/usr/bin/env python3
"""Debug ChromaDB query to see what it returns."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from promaia.utils.config import load_environment
load_environment()

import chromadb
from openai import OpenAI

print("🔍 Debug ChromaDB Raw Query\n")
print("=" * 60)

# Connect to ChromaDB
client = chromadb.PersistentClient(path="chroma_db")
collection = client.get_or_create_collection(name="promaia_content")

print(f"Collection: {collection.name}")
print(f"Count: {collection.count()}")

# Generate query embedding using OpenAI
print("\n📝 Generating query embedding...")
openai_client = OpenAI()
query_text = "email"
response = openai_client.embeddings.create(
    input=query_text,
    model="text-embedding-3-small"
)
query_embedding = response.data[0].embedding
print(f"   Query: '{query_text}'")
print(f"   Embedding dimensions: {len(query_embedding)}")

# Query collection directly
print("\n🔍 Querying collection...")
results = collection.query(
    query_embeddings=[query_embedding],
    n_results=5
)

print(f"\n📊 Raw Results:")
print(f"   Type: {type(results)}")
print(f"   Keys: {results.keys() if isinstance(results, dict) else 'N/A'}")

if isinstance(results, dict):
    print(f"\n   IDs: {len(results.get('ids', [[]])[0])} results" if results.get('ids') else "   IDs: None")
    if results.get('ids') and len(results['ids'][0]) > 0:
        print(f"      First ID: {results['ids'][0][0]}")
    
    print(f"   Distances: {results.get('distances', [[]])[0][:3] if results.get('distances') else 'None'}")
    print(f"   Metadatas: {'Present' if results.get('metadatas') else 'None'}")
    print(f"   Documents: {'Present' if results.get('documents') else 'None'}")
    
    # Check if we got any results
    if results.get('ids') and len(results['ids'][0]) > 0:
        print("\n✅ Query returned results!")
        for i in range(min(3, len(results['ids'][0]))):
            print(f"\n   Result {i+1}:")
            print(f"      ID: {results['ids'][0][i]}")
            print(f"      Distance: {results['distances'][0][i]}")
            print(f"      Similarity: {1 - results['distances'][0][i]:.3f}")
    else:
        print("\n❌ Query returned NO results!")

print("\n" + "=" * 60)
