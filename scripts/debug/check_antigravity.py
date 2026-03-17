
from promaia.storage.db_factory import get_db
db = get_db()
rows = db.fetch_all("SELECT id FROM memories WHERE domain = 'antigravity'")
print(f"Memory count for antigravity: {len(rows)}")
rows2 = db.fetch_all("SELECT d.id FROM domains d WHERE LOWER(d.name) = 'antigravity'")
print(f"Domain count for antigravity: {len(rows2)}")
