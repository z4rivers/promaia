"""Full schema audit: show actual data in key tables. Output to file."""
import os, sys
sys.path.insert(0, "/home/zack/dev/promaia")
os.environ["STORE_BACKEND"] = "libsql"
from promaia.storage.db_factory import get_db
db = get_db()

out = []

out.append("=" * 60)
out.append("  FULL SCHEMA AUDIT")
out.append("=" * 60)
for t in ["domains","contexts","actions","memories","events","profile","conversations","agent_costs"]:
    info = db.fetch_all(f"PRAGMA table_info({t})")
    cols = [(r['name'], r['type'], 'NOT NULL' if r['notnull'] else '') for r in info]
    out.append(f"\n  {t}:")
    for name, typ, nn in cols:
        out.append(f"    {name} | {typ} | {nn}")

out.append("")
out.append("=" * 60)
out.append("  JOIN TESTS")
out.append("=" * 60)

# contexts JOIN test via domain_id
try:
    rows = db.fetch_all("SELECT d.name, c.current_state FROM contexts c JOIN domains d ON d.id = c.domain_id LIMIT 3")
    out.append("  JOIN domains ON id = domain_id: OK")
    for r in rows:
        state = str(r.get('current_state',''))[:60]
        out.append(f"    {r['name']}: {state}")
except Exception as e:
    out.append(f"  JOIN domains ON id = domain_id: FAIL: {e}")

# actions sample
out.append("")
out.append("  actions sample:")
for r in db.fetch_all("SELECT domain, content, status FROM actions WHERE status='pending' LIMIT 3"):
    out.append(f"    [{r.get('status')}] {r.get('domain')}: {str(r.get('content',''))[:60]}")

pending = db.fetch_one("SELECT COUNT(*) as c FROM actions WHERE status='pending'")
out.append(f"  Total pending actions: {pending['c']}")

# memories sample
out.append("")
out.append("  memories sample (latest 3):")
for r in db.fetch_all("SELECT domain, content FROM memories ORDER BY created_at DESC LIMIT 3"):
    out.append(f"    [{r.get('domain')}] {str(r.get('content',''))[:60]}")

# events columns
out.append("")
out.append("  events sample (latest 2):")
for r in db.fetch_all("SELECT type, source, created_at FROM events ORDER BY created_at DESC LIMIT 2"):
    out.append(f"    type={r.get('type')} source={r.get('source')} at={r.get('created_at')}")

# Write to file
with open("/tmp/schema_audit.txt", "w") as f:
    f.write("\n".join(out))
print("Written to /tmp/schema_audit.txt")
