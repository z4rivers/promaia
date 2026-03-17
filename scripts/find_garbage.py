
from promaia.storage.db_factory import get_db

db = get_db()
print("--- SEDGWICK MEMORIES ---")
rows = db.fetch_all("SELECT id, content FROM memories WHERE domain = 'sedgwick'")
for r in rows:
    print(f"{r['id']}: {r['content'][:100]}...")

print("\n--- VOICE SESSION MEMORIES (Potential Garbage) ---")
# Fragmented tags might include 'voice_session' or similar
rows = db.fetch_all("SELECT id, content FROM memories WHERE content LIKE '%voice session%' OR content LIKE '%empty transcript%' LIMIT 20")
for r in rows:
    print(f"{r['id']}: {r['content'][:100]}...")
