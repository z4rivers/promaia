
from promaia.storage.db_factory import get_db
db = get_db()
for table in ['actions', 'contexts', 'agent_tasks']:
    res = db.fetch_one(f"SELECT sql FROM sqlite_master WHERE name='{table}'")
    if res:
        print(f"--- SCHEMA: {table} ---")
        print(res['sql'])
        print()
