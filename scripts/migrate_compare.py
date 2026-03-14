"""Compare row counts between PG and libSQL to find stragglers."""
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
pg_cur = pg_conn.cursor()
db = get_db()

pairs = [
    ("brain", "domains", "domains"),
    ("brain", "contexts", "contexts"),
    ("brain", "memories", "memories"),
    ("brain", "actions", "actions"),
    ("brain", "events", "events"),
    ("brain", "profile", "profile"),
    ("brain", "profile_narrative", "profile_narrative"),
    ("brain", "timeline", "timeline"),
    ("brain", "conversations", "conversations"),
    ("brain", "conversation_sessions", "conversation_sessions"),
    ("brain", "onboarding_sessions", "onboarding_sessions"),
    ("brain", "onboarding_progress", "onboarding_progress"),
    ("brain", "agent_costs", "agent_costs"),
    ("public", "agent_executions", "agent_executions"),
    ("public", "email_drafts", "email_drafts"),
    ("public", "gmail_content", "gmail_content"),
    ("public", "mail_sync_state", "mail_sync_state"),
    ("public", "ocr_uploads", "ocr_uploads"),
]

print(f"{'Table':<30} {'PG':>6} {'libSQL':>8} {'Diff':>6}")
print("-" * 55)
total_pg = total_ls = 0
for schema, pg_table, ls_table in pairs:
    pg_cur.execute(f'SELECT COUNT(*) FROM "{schema}"."{pg_table}"')
    pg_count = pg_cur.fetchone()[0]
    
    row = db.fetch_one(f"SELECT COUNT(*) as cnt FROM {ls_table}")
    ls_count = row['cnt'] if row else 0
    
    diff = pg_count - ls_count
    marker = "  ⚠️" if diff != 0 else "  ✅"
    print(f"{schema}.{pg_table:<24} {pg_count:>6} {ls_count:>8} {diff:>6}{marker}")
    total_pg += pg_count
    total_ls += ls_count

print("-" * 55)
print(f"{'TOTAL':<30} {total_pg:>6} {total_ls:>8} {total_pg - total_ls:>6}")

pg_conn.close()
