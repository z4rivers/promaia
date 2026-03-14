"""List all tables in the libSQL database."""
import os, sys
sys.path.insert(0, "/home/zack/dev/promaia")
os.environ["STORE_BACKEND"] = "libsql"

from promaia.storage.db_factory import get_db
db = get_db()
rows = db.fetch_all("SELECT name, type FROM sqlite_master WHERE type IN ('table', 'view') ORDER BY type, name")
for r in rows:
    print(f"  {r['type']}: {r['name']}")
