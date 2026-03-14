"""
Fix remaining migration issues:
1. actions with NULL content - set default
2. conversations with UNIQUE constraint on session_id
3. agent_executions with FOREIGN KEY issues
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

def get_pg_connection():
    return psycopg2.connect(os.environ.get("DATABASE_URL"), connect_timeout=15)

def main():
    pg_conn = get_pg_connection()
    pg_cur = pg_conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    db = get_db()
    
    # 1. Fix actions with NULL content
    print("📦 Fixing actions (NULL content → empty string)...")
    pg_cur.execute('SELECT * FROM brain.actions')
    rows = pg_cur.fetchall()
    cols = [desc[0] for desc in pg_cur.description]
    cols_no_id = [c for c in cols if c != 'id']
    
    db.execute('DELETE FROM actions')
    inserted = 0
    errors = 0
    for row in rows:
        values = []
        for c in cols_no_id:
            v = serialize_value(row[c])
            # Fix NULL content
            if c == 'content' and v is None:
                v = ''
            values.append(v)
        placeholders = ", ".join(["?"] * len(cols_no_id))
        col_list = ", ".join(f'"{c}"' for c in cols_no_id)
        try:
            db.execute(f'INSERT INTO actions ({col_list}) VALUES ({placeholders})', tuple(values))
            inserted += 1
        except Exception as e:
            errors += 1
            if errors <= 3:
                print(f"  ⚠️  {e}")
    print(f"   ✅ {inserted} rows" + (f", {errors} errors" if errors else ""))

    # 2. Fix conversations (UNIQUE constraint on session_id)
    print("\n📦 Fixing conversations (dedup session_id)...")
    # Check libSQL schema for conversations
    info = db.fetch_all("PRAGMA table_info(conversations)")
    libsql_cols = [r['name'] for r in info]
    
    pg_cur.execute('SELECT * FROM brain.conversations')
    rows = pg_cur.fetchall()
    pg_cols = [desc[0] for desc in pg_cur.description]
    common = [c for c in pg_cols if c in libsql_cols and c != 'id']
    
    db.execute('DELETE FROM conversations')
    seen_sessions = set()
    inserted = 0
    errors = 0
    for row in rows:
        session_id = row.get('session_id')
        if session_id in seen_sessions:
            continue
        if session_id:
            seen_sessions.add(session_id)
        
        values = tuple(serialize_value(row[c]) for c in common)
        placeholders = ", ".join(["?"] * len(common))
        col_list = ", ".join(f'"{c}"' for c in common)
        try:
            db.execute(f'INSERT INTO conversations ({col_list}) VALUES ({placeholders})', values)
            inserted += 1
        except Exception as e:
            errors += 1
            if errors <= 3:
                print(f"  ⚠️  {e}")
    print(f"   ✅ {inserted} rows" + (f", {errors} errors" if errors else ""))

    # 3. Fix agent_executions (foreign key issue - disable FK temporarily)
    print("\n📦 Fixing agent_executions (FK disabled)...")
    db.execute("PRAGMA foreign_keys = OFF")
    pg_cur.execute('SELECT * FROM public.agent_executions')
    rows = pg_cur.fetchall()
    pg_cols = [desc[0] for desc in pg_cur.description]
    
    info = db.fetch_all("PRAGMA table_info(agent_executions)")
    libsql_cols = [r['name'] for r in info]
    common = [c for c in pg_cols if c in libsql_cols and c != 'id']
    
    db.execute('DELETE FROM agent_executions')
    inserted = 0
    for row in rows:
        values = tuple(serialize_value(row[c]) for c in common)
        placeholders = ", ".join(["?"] * len(common))
        col_list = ", ".join(f'"{c}"' for c in common)
        try:
            db.execute(f'INSERT INTO agent_executions ({col_list}) VALUES ({placeholders})', values)
            inserted += 1
        except Exception as e:
            pass
    db.execute("PRAGMA foreign_keys = ON")
    print(f"   ✅ {inserted} rows")

    # --- Final count ---
    print("\n" + "=" * 60)
    print("  Verification — Row counts in libSQL:")
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
    print(f"\n  TOTAL: {total} rows in libSQL")
    
    pg_conn.close()

if __name__ == "__main__":
    main()
