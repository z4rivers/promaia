import os, sys
sys.path.insert(0, "/home/zack/dev/promaia")
os.environ["STORE_BACKEND"] = "libsql"
from promaia.storage.db_factory import get_db
db = get_db()

for table in ["contexts", "domains", "actions", "memories"]:
    info = db.fetch_all(f"PRAGMA table_info({table})")
    cols = [r['name'] for r in info]
    print(f"{table}: {cols}")
