
from promaia.storage.db_factory import get_db

db = get_db()
db.execute("DELETE FROM domains WHERE name = 'sedgwick'")
db.execute("UPDATE memories SET domain = 'general' WHERE domain = 'sedgwick'")
print("Purged Sedgwick domain and reclassified related memories to 'general'.")
