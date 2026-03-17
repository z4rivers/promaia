
from promaia.storage.db_factory import get_db
db = get_db()
res = db.fetch_one("SELECT sql FROM sqlite_master WHERE name='conversation_sessions'")
print(res['sql'])
