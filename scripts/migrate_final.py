"""Fix the final 3 tables: actions, conversations, onboarding_sessions."""
import os, sys, json
from datetime import datetime, date, time, timedelta
from decimal import Decimal

# Add project root to sys.path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
import psycopg2, psycopg2.extras

env_path = os.path.join(project_root, ".env")
if os.path.exists(env_path):
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

def sv(val):
    if val is None: return None
    if isinstance(val, datetime): return val.isoformat()
    if isinstance(val, date): return val.isoformat()
    if isinstance(val, time): return val.isoformat()
    if isinstance(val, timedelta): return str(val.total_seconds())
    if isinstance(val, Decimal): return float(val)
    if isinstance(val, (dict, list)): return json.dumps(val)
    if isinstance(val, memoryview): return bytes(val)
    if isinstance(val, bool): return 1 if val else 0
    return val

def get_common_cols(pg_conn, db, pg_schema, pg_table, libsql_table):
    """Get intersecting columns (minus id)."""
    meta_cur = pg_conn.cursor()
    meta_cur.execute("""SELECT column_name FROM information_schema.columns
        WHERE table_schema = %s AND table_name = %s ORDER BY ordinal_position""",
        (pg_schema, pg_table))
    pg_cols = [r[0] for r in meta_cur.fetchall()]
    
    info = db.fetch_all(f"PRAGMA table_info({libsql_table})")
    ls_cols = [r['name'] for r in info]
    
    return [c for c in pg_cols if c in ls_cols and c != 'id']

def main():
    pg_conn = psycopg2.connect(os.environ.get("DATABASE_URL"), connect_timeout=15)
    db = get_db()
    
    # ── 1. ACTIONS ──
    print("📦 actions (456 rows)...")
    common = get_common_cols(pg_conn, db, "brain", "actions", "actions")
    print(f"   Common columns: {common}")
    
    pg_cur = pg_conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    pg_cur.execute('SELECT * FROM brain.actions')
    rows = pg_cur.fetchall()
    
    db.execute('DELETE FROM actions')
    col_list = ", ".join(f'"{c}"' for c in common)
    placeholders = ", ".join(["?"] * len(common))
    sql = f'INSERT OR IGNORE INTO actions ({col_list}) VALUES ({placeholders})'
    
    inserted = errors = 0
    for row in rows:
        vals = []
        for c in common:
            v = sv(row[c])
            if c == 'content' and v is None:
                v = row.get('description', '') or ''
            vals.append(v)
        try:
            db.execute(sql, tuple(vals))
            inserted += 1
        except Exception as e:
            errors += 1
            if errors <= 3: print(f"   ⚠️ {e}")
    print(f"   ✅ {inserted}/{len(rows)} rows" + (f", {errors} err" if errors else ""))

    # ── 2. CONVERSATIONS ──
    print("\n📦 conversations (200 rows)...")
    common = get_common_cols(pg_conn, db, "brain", "conversations", "conversations")
    print(f"   Common columns: {common}")
    
    pg_cur.execute('SELECT * FROM brain.conversations ORDER BY created_at')
    rows = pg_cur.fetchall()
    
    db.execute('DELETE FROM conversations')
    col_list = ", ".join(f'"{c}"' for c in common)
    placeholders = ", ".join(["?"] * len(common))
    sql = f'INSERT OR IGNORE INTO conversations ({col_list}) VALUES ({placeholders})'
    
    inserted = errors = 0
    for row in rows:
        vals = tuple(sv(row[c]) for c in common)
        try:
            db.execute(sql, vals)
            inserted += 1
        except Exception as e:
            errors += 1
            if errors <= 3: print(f"   ⚠️ {e}")
    print(f"   ✅ {inserted}/{len(rows)} rows" + (f", {errors} err" if errors else ""))

    # ── 3. ONBOARDING_SESSIONS ──
    print("\n📦 onboarding_sessions (1 row)...")
    common = get_common_cols(pg_conn, db, "brain", "onboarding_sessions", "onboarding_sessions")
    print(f"   Common columns: {common}")
    
    pg_cur.execute('SELECT * FROM brain.onboarding_sessions')
    rows = pg_cur.fetchall()
    
    db.execute('DELETE FROM onboarding_sessions')
    col_list = ", ".join(f'"{c}"' for c in common)
    placeholders = ", ".join(["?"] * len(common))
    sql = f'INSERT OR IGNORE INTO onboarding_sessions ({col_list}) VALUES ({placeholders})'
    
    inserted = 0
    for row in rows:
        vals = []
        for c in common:
            v = sv(row[c])
            if c == 'session_id' and v is None:
                v = 'legacy-session-001'
            vals.append(v)
        try:
            db.execute(sql, tuple(vals))
            inserted += 1
        except Exception as e:
            print(f"   ⚠️ {e}")
    print(f"   ✅ {inserted}/{len(rows)} rows")

    # ── FINAL COMPARISON ──
    print("\n" + "=" * 55)
    print(f"{'Table':<30} {'PG':>6} {'libSQL':>8} {'Match':>6}")
    print("-" * 55)
    pg_cur2 = pg_conn.cursor()
    pairs = [
        ("brain","domains","domains"), ("brain","contexts","contexts"),
        ("brain","memories","memories"), ("brain","actions","actions"),
        ("brain","events","events"), ("brain","profile","profile"),
        ("brain","profile_narrative","profile_narrative"),
        ("brain","timeline","timeline"), ("brain","conversations","conversations"),
        ("brain","conversation_sessions","conversation_sessions"),
        ("brain","onboarding_sessions","onboarding_sessions"),
        ("brain","onboarding_progress","onboarding_progress"),
        ("brain","agent_costs","agent_costs"),
        ("public","agent_executions","agent_executions"),
        ("public","email_drafts","email_drafts"),
        ("public","gmail_content","gmail_content"),
        ("public","mail_sync_state","mail_sync_state"),
        ("public","ocr_uploads","ocr_uploads"),
    ]
    total_pg = total_ls = 0
    for s, pt, lt in pairs:
        pg_cur2.execute(f'SELECT COUNT(*) FROM "{s}"."{pt}"')
        pc = pg_cur2.fetchone()[0]
        r = db.fetch_one(f"SELECT COUNT(*) as cnt FROM {lt}")
        lc = r['cnt'] if r else 0
        d = pc - lc
        m = "✅" if d == 0 else f"⚠️ -{d}"
        print(f"  {s}.{pt:<24} {pc:>6} {lc:>8}   {m}")
        total_pg += pc; total_ls += lc
    print("-" * 55)
    print(f"  {'TOTAL':<28} {total_pg:>6} {total_ls:>8}   {'✅' if total_pg==total_ls else f'⚠️ -{total_pg-total_ls}'}")
    
    pg_conn.close()

if __name__ == "__main__":
    main()
