"""Debug: test CREATE TABLE directly on the libSQL connection."""
import sys
sys.path.insert(0, "/home/zack/dev/promaia")
import os
os.chdir("/home/zack/dev/promaia")
os.environ["STORE_BACKEND"] = "libsql"

from promaia.storage.libsql_db import get_libsql_db

db = get_libsql_db()
conn = db.get_connection()

# Try creating a single table
try:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type TEXT NOT NULL,
            payload TEXT DEFAULT '{}',
            source TEXT,
            session_id TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    print("events table created OK")
except Exception as e:
    print(f"FAIL: {e}")

# Check if it exists
try:
    result = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='events'").fetchall()
    print(f"events in sqlite_master: {result}")
except Exception as e:
    print(f"Check failed: {e}")
