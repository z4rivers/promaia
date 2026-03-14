"""
Migrate all data from PostgreSQL (Supabase) to libSQL.
Reads rows from each Postgres table and inserts them into the corresponding libSQL table.

Handles type conversion: datetime -> ISO string, dict/list -> JSON, Decimal -> float.
"""
import os, sys, json
from datetime import datetime, date, time, timedelta
from decimal import Decimal
sys.path.insert(0, "/home/zack/dev/promaia")

import psycopg2
import psycopg2.extras

# Load env
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

# --- Configuration ---
TABLE_MAP = [
    # Brain schema tables (order matters: domains before contexts, etc.)
    ("brain", "domains",               "domains"),
    ("brain", "contexts",              "contexts"),
    ("brain", "memories",              "memories"),
    ("brain", "actions",               "actions"),
    ("brain", "events",                "events"),
    ("brain", "profile",               "profile"),
    ("brain", "profile_narrative",     "profile_narrative"),
    ("brain", "timeline",              "timeline"),
    ("brain", "conversations",         "conversations"),
    ("brain", "conversation_sessions", "conversation_sessions"),
    ("brain", "onboarding_sessions",   "onboarding_sessions"),
    ("brain", "onboarding_progress",   "onboarding_progress"),
    ("brain", "agent_costs",           "agent_costs"),
    # Public schema tables
    ("public", "agent_executions",     "agent_executions"),
    ("public", "email_drafts",         "email_drafts"),
    ("public", "gmail_content",        "gmail_content"),
    ("public", "mail_sync_state",      "mail_sync_state"),
    ("public", "ocr_uploads",          "ocr_uploads"),
]

def get_pg_connection():
    db_url = os.environ.get("DATABASE_URL")
    return psycopg2.connect(db_url, connect_timeout=15)

def get_pg_columns(pg_cur, schema, table):
    pg_cur.execute("""
        SELECT column_name FROM information_schema.columns
        WHERE table_schema = %s AND table_name = %s
        ORDER BY ordinal_position
    """, (schema, table))
    return [r[0] for r in pg_cur.fetchall()]

def get_libsql_columns(db, table):
    rows = db.fetch_all(f"PRAGMA table_info({table})")
    return [r["name"] for r in rows]

def serialize_value(val):
    """Convert Python values to libSQL-compatible types."""
    if val is None:
        return None
    # datetime/date/time -> ISO string
    if isinstance(val, datetime):
        return val.isoformat()
    if isinstance(val, date):
        return val.isoformat()
    if isinstance(val, time):
        return val.isoformat()
    if isinstance(val, timedelta):
        return str(val.total_seconds())
    # Decimal -> float
    if isinstance(val, Decimal):
        return float(val)
    # dict/list -> JSON string
    if isinstance(val, (dict, list)):
        return json.dumps(val)
    # memoryview/bytes -> bytes
    if isinstance(val, memoryview):
        return bytes(val)
    # bool -> int (SQLite)
    if isinstance(val, bool):
        return 1 if val else 0
    return val

def migrate_table(pg_conn, db, pg_schema, pg_table, libsql_table):
    """Migrate a single table from Postgres to libSQL."""
    pg_cur = pg_conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    
    # Get columns from both sides
    pg_cols = get_pg_columns(pg_conn.cursor(), pg_schema, pg_table)
    libsql_cols = get_libsql_columns(db, libsql_table)
    
    # Find common columns (skip 'id' to let autoincrement work)
    common_cols = [c for c in pg_cols if c in libsql_cols and c != "id"]
    
    if not common_cols:
        print(f"  ⚠️  No common columns found!")
        pg_only = set(pg_cols) - set(libsql_cols)
        libsql_only = set(libsql_cols) - set(pg_cols)
        if pg_only:
            print(f"       PG-only columns: {pg_only}")
        if libsql_only:
            print(f"       libSQL-only columns: {libsql_only}")
        return 0, 0
    
    # Read all rows from Postgres
    col_list = ", ".join(f'"{c}"' for c in common_cols)
    pg_cur.execute(f'SELECT {col_list} FROM "{pg_schema}"."{pg_table}"')
    rows = pg_cur.fetchall()
    
    if not rows:
        print(f"  ℹ️  Empty table, skipping")
        return 0, 0
    
    # Clear existing data in libSQL table first (clean migration)
    db.execute(f'DELETE FROM "{libsql_table}"')
    
    # Build INSERT statement
    placeholders = ", ".join(["?"] * len(common_cols))
    insert_col_list = ", ".join(f'"{c}"' for c in common_cols)
    insert_sql = f'INSERT INTO "{libsql_table}" ({insert_col_list}) VALUES ({placeholders})'
    
    # Insert rows
    inserted = 0
    errors = 0
    for row in rows:
        try:
            values = tuple(serialize_value(row[c]) for c in common_cols)
            db.execute(insert_sql, values)
            inserted += 1
        except Exception as e:
            errors += 1
            if errors <= 3:
                # Debug: show which column caused the issue
                for c in common_cols:
                    v = row[c]
                    if v is not None:
                        sv = serialize_value(v)
                        if type(sv).__name__ not in ('str', 'int', 'float', 'bytes', 'NoneType'):
                            print(f"    ⚠️  Column '{c}': type={type(v).__name__}, serialized_type={type(sv).__name__}")
                print(f"    ⚠️  Row error: {e}")
    
    return inserted, errors

def main():
    print("=" * 60)
    print("  PostgreSQL → libSQL Data Migration")
    print("=" * 60)
    print()
    
    print("Connecting to PostgreSQL (Supabase)...")
    pg_conn = get_pg_connection()
    print("✅ PostgreSQL connected")
    
    print("Connecting to libSQL...")
    db = get_db()
    print("✅ libSQL connected")
    print()
    
    total_migrated = 0
    total_errors = 0
    
    for pg_schema, pg_table, libsql_table in TABLE_MAP:
        print(f"📦 {pg_schema}.{pg_table} → {libsql_table}...")
        try:
            inserted, errors = migrate_table(pg_conn, db, pg_schema, pg_table, libsql_table)
            total_migrated += inserted
            total_errors += errors
            status = "✅" if errors == 0 else "⚠️"
            if inserted > 0 or errors > 0:
                print(f"   {status} {inserted} rows" + (f", {errors} errors" if errors else ""))
        except Exception as e:
            print(f"   ❌ FAILED: {e}")
            import traceback
            traceback.print_exc()
            total_errors += 1
    
    print()
    print("=" * 60)
    print(f"  ✅ Migration complete!")
    print(f"  Total rows migrated: {total_migrated}")
    if total_errors:
        print(f"  ⚠️  Total errors: {total_errors}")
    print("=" * 60)
    
    pg_conn.close()

if __name__ == "__main__":
    main()
