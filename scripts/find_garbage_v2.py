
from promaia.storage.db_factory import get_db

db = get_db()
print("--- SHORT ASSISTANT MEMORIES ---")
# Finding assistant memories shorter than 50 characters
rows = db.fetch_all("SELECT id, content FROM memories WHERE content LIKE '%Assistant:%' AND length(content) < 100")
for r in rows:
    print(f"{r['id']}: {r['content']}")

# Also check for tags like 'hallucination'
rows = db.fetch_all("SELECT id, content FROM memories WHERE content LIKE '%hallucination%'")
for r in rows:
    print(f"Hallucination tag found: {r['id']}: {r['content'][:100]}")
