"""Create all brain tables one at a time."""
import sys
sys.path.insert(0, "/home/zack/dev/promaia")
import os
os.chdir("/home/zack/dev/promaia")
os.environ["STORE_BACKEND"] = "libsql"

from promaia.storage.libsql_db import get_libsql_db
db = get_libsql_db()
conn = db.get_connection()

tables = [
    ("domains", """CREATE TABLE IF NOT EXISTS domains (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL,
        priority INTEGER DEFAULT 5,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )"""),
    ("contexts", """CREATE TABLE IF NOT EXISTS contexts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        domain_id INTEGER NOT NULL,
        directive TEXT,
        current_state TEXT,
        stale_threshold_days INTEGER DEFAULT 7,
        last_updated TEXT DEFAULT CURRENT_TIMESTAMP,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )"""),
    ("memories", """CREATE TABLE IF NOT EXISTS memories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        content TEXT NOT NULL,
        domain TEXT,
        tags TEXT,
        memory_type TEXT DEFAULT 'observation',
        importance REAL DEFAULT 0.5,
        embedding TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )"""),
    ("actions", """CREATE TABLE IF NOT EXISTS actions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        domain TEXT,
        content TEXT NOT NULL,
        priority TEXT DEFAULT 'normal',
        status TEXT DEFAULT 'pending',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        completed_at TEXT
    )"""),
    ("profile", """CREATE TABLE IF NOT EXISTS profile (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        category TEXT NOT NULL,
        field TEXT NOT NULL,
        value TEXT NOT NULL,
        confidence REAL DEFAULT 0.8,
        source TEXT DEFAULT 'declared',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(category, field)
    )"""),
    ("profile_narrative", """CREATE TABLE IF NOT EXISTS profile_narrative (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        narrative TEXT NOT NULL,
        generated_at TEXT DEFAULT CURRENT_TIMESTAMP,
        profile_hash TEXT
    )"""),
    ("timeline", """CREATE TABLE IF NOT EXISTS timeline (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        description TEXT,
        event_date TEXT NOT NULL,
        category TEXT DEFAULT 'life',
        significance INTEGER DEFAULT 5,
        domain TEXT,
        tags TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )"""),
    ("conversations", """CREATE TABLE IF NOT EXISTS conversations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT UNIQUE NOT NULL,
        channel TEXT DEFAULT 'web',
        messages TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP
    )"""),
    ("conversation_sessions", """CREATE TABLE IF NOT EXISTS conversation_sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT UNIQUE NOT NULL,
        channel TEXT DEFAULT 'web',
        started_at TEXT DEFAULT CURRENT_TIMESTAMP,
        last_activity TEXT DEFAULT CURRENT_TIMESTAMP,
        metadata TEXT
    )"""),
    ("onboarding_progress", """CREATE TABLE IF NOT EXISTS onboarding_progress (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        channel TEXT NOT NULL UNIQUE,
        status TEXT DEFAULT 'pending',
        fields_populated INTEGER DEFAULT 0,
        notes TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP
    )"""),
    ("onboarding_sessions", """CREATE TABLE IF NOT EXISTS onboarding_sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT NOT NULL,
        started_at TEXT DEFAULT CURRENT_TIMESTAMP,
        completed_at TEXT,
        status TEXT DEFAULT 'active'
    )"""),
    ("agent_executions", """CREATE TABLE IF NOT EXISTS agent_executions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        agent_name TEXT NOT NULL,
        started_at TEXT NOT NULL,
        completed_at TEXT,
        status TEXT NOT NULL,
        iterations_used INTEGER DEFAULT 0,
        tokens_used INTEGER DEFAULT 0,
        cost_estimate REAL DEFAULT 0.0,
        output_notion_page_id TEXT,
        error_message TEXT,
        context_summary TEXT,
        created_at TEXT NOT NULL
    )"""),
]

indexes = [
    "CREATE INDEX IF NOT EXISTS idx_events_type ON events(type)",
    "CREATE INDEX IF NOT EXISTS idx_events_created ON events(created_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_memories_domain ON memories(domain)",
    "CREATE INDEX IF NOT EXISTS idx_actions_status ON actions(status)",
    "CREATE INDEX IF NOT EXISTS idx_profile_category ON profile(category)",
    "CREATE INDEX IF NOT EXISTS idx_agent_costs_agent ON agent_costs(agent_name, created_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_agent_costs_date ON agent_costs(created_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_contexts_domain ON contexts(domain_id)",
]

for name, sql in tables:
    try:
        conn.execute(sql)
        conn.commit()
        print(f"  ✅ {name}")
    except Exception as e:
        print(f"  ❌ {name}: {e}")

for idx_sql in indexes:
    try:
        conn.execute(idx_sql)
        conn.commit()
    except Exception as e:
        idx_name = idx_sql.split("IF NOT EXISTS ")[1].split(" ON")[0] if "IF NOT EXISTS" in idx_sql else "?"
        print(f"  ⚠️  index {idx_name}: {e}")

# Final count
all_tables = db.fetch_all("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
print(f"\nTotal tables in database: {len(all_tables)}")
