#!/usr/bin/env python3
"""
Fix property collection HNSW parameters by recreating with proper settings.
"""
import chromadb
from promaia.utils.config import load_environment

load_environment()

def fix_property_collection():
    """Recreate property collection with proper HNSW parameters."""
    print("🔧 Fixing property collection HNSW parameters...")
    print("⚠️  WARNING: This will delete and recreate the property collection.")
    print("    Property embeddings will need to be regenerated via sync.")

    client = chromadb.PersistentClient(path="chroma_db")

    # Delete existing collection (don't try to backup if corrupted)
    try:
        prop_col = client.get_collection("promaia_properties")
        count = prop_col.count()
        print(f"📊 Current collection has {count} items")

        print("🗑️  Deleting old collection (skipping backup due to corruption)...")
        client.delete_collection("promaia_properties")
        print("✅ Old collection deleted")

    except ValueError as e:
        if "does not exist" in str(e):
            print("📭 Collection doesn't exist, will create new one")
        else:
            print(f"⚠️  Error accessing collection: {e}")
            raise
    except Exception as e:
        print(f"⚠️  Error during deletion: {e}")
        import traceback
        traceback.print_exc()
        raise

    # Create new collection with proper HNSW parameters
    print("🆕 Creating new collection with updated HNSW parameters...")
    new_col = client.create_collection(
        name="promaia_properties",
        metadata={
            "hnsw:space": "cosine",
            "hnsw:construction_ef": 200,
            "hnsw:search_ef": 100,
            "hnsw:M": 32
        }
    )
    print("✅ New collection created")

    print("\n🎉 Property collection fix complete!")
    print("   Updated HNSW parameters:")
    print("   - hnsw:construction_ef: 200 (was 100)")
    print("   - hnsw:search_ef: 100 (was 10) ← Key fix")
    print("   - hnsw:M: 32 (was 16)")
    print("\n📝 Next steps:")
    print("   Run 'maia database sync' to regenerate property embeddings")

if __name__ == "__main__":
    fix_property_collection()
