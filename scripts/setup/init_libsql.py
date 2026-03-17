"""Initialize the libSQL database with the schema."""
import sys
sys.path.insert(0, "/home/zack/dev/promaia")
import os
os.chdir("/home/zack/dev/promaia")

# Force libSQL backend
os.environ["STORE_BACKEND"] = "libsql"

from promaia.storage.libsql_db import get_libsql_db

# Initialize the db (creates promaia.db if it doesn't exist)
db = get_libsql_db()
print(f"DB connected: {db.db_path}")

# Load and execute the schema
schema_path = "promaia/storage/schema_libsql.sql"
with open(schema_path) as f:
    schema = f.read()

conn = db.get_connection()
# Execute each statement separately
for stmt in schema.split(";"):
    stmt = stmt.strip()
    if stmt and not stmt.startswith("--"):
        try:
            conn.execute(stmt)
        except Exception as e:
            print(f"  Warning: {str(e)[:100]}")
conn.commit()
print("Schema initialized successfully")

# Verify
tables = db.fetch_all("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
print(f"Tables created: {len(tables)}")
for t in tables:
    print(f"  - {t['name']}")
