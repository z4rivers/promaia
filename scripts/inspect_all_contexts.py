
from promaia.storage.db_factory import get_db
db = get_db()
rows = db.fetch_all("SELECT d.name, c.current_state, c.directive FROM domains d JOIN contexts c ON d.id = c.domain_id")
for r in rows:
    print(f"Project: {r['name']}")
    print(f"  State: {r['current_state']}")
    print(f"  Directive: {r['directive']}")
    print("-" * 20)
