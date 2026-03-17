
from promaia.storage.db_factory import get_db
db = get_db()
rows = db.fetch_all("SELECT d.name FROM domains d JOIN contexts c ON d.id = c.domain_id WHERE LOWER(d.name) = 'heatpup'")
print(f"Project Context Count for heatpup: {len(rows)}")
