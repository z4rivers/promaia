"""Check what data exists in the PostgreSQL database."""
import psycopg2
import os, sys

# Try loading .env from promaia project root
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

db_url = os.environ.get("DATABASE_URL")
if not db_url:
    # Fallback: try scanning the .env file directly
    env_path = "/home/zack/dev/promaia/.env"
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line.startswith("DATABASE_URL="):
                    db_url = line.split("=", 1)[1].strip().strip("'\"")
                    break

if not db_url:
    print("ERROR: DATABASE_URL not found")
    sys.exit(1)

print(f"Connecting to: {db_url[:50]}...")

conn = psycopg2.connect(db_url, connect_timeout=10)
cur = conn.cursor()

# Get all tables in brain schema
cur.execute("""
    SELECT schemaname, tablename 
    FROM pg_tables 
    WHERE schemaname IN ('brain', 'public') 
    ORDER BY schemaname, tablename
""")
tables = cur.fetchall()

print("\n=== PostgreSQL Data Inventory ===\n")
total_rows = 0
for schema, table in tables:
    try:
        cur.execute(f'SELECT COUNT(*) FROM "{schema}"."{table}"')
        count = cur.fetchone()[0]
        if count > 0:
            print(f"  {schema}.{table}: {count} rows")
            total_rows += count
    except Exception as e:
        print(f"  {schema}.{table}: ERROR - {e}")
        conn.rollback()

print(f"\nTotal rows to migrate: {total_rows}")
conn.close()
