
from promaia.storage.db_factory import get_db
db = get_db()
tables = db.fetch_all("SELECT name FROM sqlite_master WHERE type='table'")
print("TABLES IN PROMAIA.DB:")
for t in tables:
    print(f"- {t['name']}")
