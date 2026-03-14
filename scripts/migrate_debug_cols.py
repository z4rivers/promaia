"""Debug: show full column comparison for problem tables."""
import os, sys
sys.path.insert(0, "/home/zack/dev/promaia")
import psycopg2

env_path = "/home/zack/dev/promaia/.env"
with open(env_path) as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, val = line.split("=", 1)
            val = val.strip().strip("'\"")
            if key.strip() not in os.environ:
                os.environ[key.strip()] = val

os.environ["STORE_BACKEND"] = "libsql"
from promaia.storage.db_factory import get_db

pg_conn = psycopg2.connect(os.environ.get("DATABASE_URL"), connect_timeout=15)
db = get_db()

for schema, table in [("brain","actions"), ("brain","conversations"), ("brain","onboarding_sessions")]:
    meta_cur = pg_conn.cursor()
    meta_cur.execute("""SELECT column_name, data_type FROM information_schema.columns
        WHERE table_schema = %s AND table_name = %s ORDER BY ordinal_position""",
        (schema, table))
    pg_cols = meta_cur.fetchall()
    
    info = db.fetch_all(f"PRAGMA table_info({table})")
    
    print(f"\n{'='*60}")
    print(f"  {schema}.{table}")
    print(f"{'='*60}")
    print(f"\n  PostgreSQL columns:")
    for name, dtype in pg_cols:
        print(f"    {name:<30} {dtype}")
    print(f"\n  libSQL columns:")
    for r in info:
        print(f"    {r['name']:<30} {r['type']}")

pg_conn.close()
