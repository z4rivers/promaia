
from promaia.storage.db_factory import get_db
db = get_db()
rows = db.fetch_all("SELECT content FROM memories WHERE domain = 'promaia' AND content LIKE '%hvac%' LIMIT 5")
print(f"Found {len(rows)} 'promaia' memories mentioning 'hvac'")
for r in rows:
    print(f"- {r['content'][:150]}...")
