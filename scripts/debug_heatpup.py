
from promaia.storage.db_factory import get_db
db = get_db()
rows = db.fetch_all("SELECT id, domain, content FROM memories WHERE domain = 'heatpup'")
print(f"Count: {len(rows)}")
for r in rows:
    print(f"ID: {r['id']}, Domain: {r['domain']}, Content: {r['content'][:100]}...")
