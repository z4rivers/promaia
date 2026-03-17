
from promaia.storage.db_factory import get_db

db = get_db()
rows = db.fetch_all("SELECT content FROM memories WHERE domain = 'general' LIMIT 50")
print("--- GENERAL BUCKET SAMPLES ---")
for r in rows:
    print(f"- {r['content'][:150]}...")
