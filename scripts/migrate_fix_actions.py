"""Fix actions table migration - column mismatch."""
import os, sys, json
from datetime import datetime, date, time, timedelta
from decimal import Decimal
sys.path.insert(0, "/home/zack/dev/promaia")

import psycopg2
import psycopg2.extras

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

def serialize_value(val):
    if val is None:
        return None
    if isinstance(val, datetime):
        return val.isoformat()
    if isinstance(val, date):
        return val.isoformat()
    if isinstance(val, time):
        return val.isoformat()
    if isinstance(val, timedelta):
        return str(val.total_seconds())
    if isinstance(val, Decimal):
        return float(val)
    if isinstance(val, (dict, list)):
        return json.dumps(val)
    if isinstance(val, memoryview):
        return bytes(val)
    if isinstance(val, bool):
        return 1 if val else 0
    return val

def main():
    pg_conn = psycopg2.connect(os.environ.get("DATABASE_URL"), connect_timeout=15)
    pg_cur = pg_conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    db = get_db()
    
    # Show column comparison
    pg_meta_cur = pg_conn.cursor()
    pg_meta_cur.execute("""
        SELECT column_name FROM information_schema.columns
        WHERE table_schema = 'brain' AND table_name = 'actions'
        ORDER BY ordinal_position
    """)
    pg_cols = [r[0] for r in pg_meta_cur.fetchall()]
    
    info = db.fetch_all("PRAGMA table_info(actions)")
    libsql_cols = [r['name'] for r in info]
    
    print(f"PG columns:     {pg_cols}")
    print(f"libSQL columns: {libsql_cols}")
    
    common = [c for c in pg_cols if c in libsql_cols and c != 'id']
    pg_only = [c for c in pg_cols if c not in libsql_cols]
    libsql_only = [c for c in libsql_cols if c not in pg_cols]
    
    print(f"Common: {common}")
    print(f"PG-only: {pg_only}")
    print(f"libSQL-only: {libsql_only}")
    
    # Migrate using only common columns, fixing NULLs for NOT NULL fields
    pg_cur.execute('SELECT * FROM brain.actions')
    rows = pg_cur.fetchall()
    
    db.execute('DELETE FROM actions')
    inserted = 0
    errors = 0
    for row in rows:
        values = []
        for c in common:
            v = serialize_value(row[c])
            if c == 'content' and v is None:
                v = ''
            values.append(v)
        placeholders = ", ".join(["?"] * len(common))
        col_list = ", ".join(f'"{c}"' for c in common)
        try:
            db.execute(f'INSERT INTO actions ({col_list}) VALUES ({placeholders})', tuple(values))
            inserted += 1
        except Exception as e:
            errors += 1
            if errors <= 5:
                print(f"  ⚠️  {e}")
    print(f"\n✅ Actions: {inserted} rows migrated" + (f", {errors} errors" if errors else ""))
    
    # Also fix onboarding_sessions (was empty)
    pg_cur.execute('SELECT * FROM brain.onboarding_sessions')
    rows = pg_cur.fetchall()
    if rows:
        pg_cols_os = [desc[0] for desc in pg_cur.description]
        info_os = db.fetch_all("PRAGMA table_info(onboarding_sessions)")
        ls_cols = [r['name'] for r in info_os]
        common_os = [c for c in pg_cols_os if c in ls_cols and c != 'id']
        
        db.execute('DELETE FROM onboarding_sessions')
        for row in rows:
            values = tuple(serialize_value(row[c]) for c in common_os)
            placeholders = ", ".join(["?"] * len(common_os))
            col_list = ", ".join(f'"{c}"' for c in common_os)
            db.execute(f'INSERT INTO onboarding_sessions ({col_list}) VALUES ({placeholders})', values)
        print(f"✅ Onboarding sessions: {len(rows)} rows migrated")
    
    # Final verification
    print("\n" + "=" * 60)
    print("  FINAL VERIFICATION")
    print("=" * 60)
    tables = [
        "domains", "contexts", "memories", "actions", "events",
        "profile", "profile_narrative", "timeline", "conversations",
        "conversation_sessions", "onboarding_sessions", "onboarding_progress",
        "agent_costs", "agent_executions", "email_drafts", "gmail_content",
        "mail_sync_state", "ocr_uploads"
    ]
    total = 0
    for t in tables:
        row = db.fetch_one(f"SELECT COUNT(*) as cnt FROM {t}")
        cnt = row['cnt'] if row else 0
        if cnt > 0:
            print(f"  {t}: {cnt}")
            total += cnt
    print(f"\n  TOTAL: {total} rows in libSQL (target: 7,896)")
    
    pg_conn.close()

if __name__ == "__main__":
    main()
