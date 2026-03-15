"""Create all brain tables for libSQL on Windows.

Schema derived from actual production DB via PRAGMA table_info — 2026-03-15.
"""
import sys, os
sys.path.insert(0, r"C:\Users\Zachary Turner\dev\promaia")
os.chdir(r"C:\Users\Zachary Turner\dev\promaia")

from promaia.storage.libsql_db import get_libsql_db
db = get_libsql_db()

tables = [
    ("domains", """CREATE TABLE IF NOT EXISTS domains (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE,
        description TEXT,
        is_project INTEGER DEFAULT 1,
        parent_domain INTEGER REFERENCES domains(id),
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )"""),
    ("contexts", """CREATE TABLE IF NOT EXISTS contexts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        domain_id INTEGER REFERENCES domains(id) NOT NULL,
        directive TEXT,
        current_state TEXT,
        last_updated TEXT DEFAULT CURRENT_TIMESTAMP,
        priority INTEGER DEFAULT 5,
        stale_threshold_days INTEGER DEFAULT 7
    )"""),
    ("memories", """CREATE TABLE IF NOT EXISTS memories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        content TEXT NOT NULL,
        summary TEXT,
        domain TEXT,
        tags TEXT DEFAULT '[]',
        entities TEXT DEFAULT '{}',
        source TEXT,
        source_id TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
        asset_paths TEXT
    )"""),
    ("actions", """CREATE TABLE IF NOT EXISTS actions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        memory_id INTEGER REFERENCES memories(id),
        domain_id INTEGER REFERENCES domains(id),
        description TEXT NOT NULL,
        status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'done', 'stale')),
        extracted_at TEXT DEFAULT CURRENT_TIMESTAMP,
        completed_at TEXT
    )"""),
    ("profile", """CREATE TABLE IF NOT EXISTS profile (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        category TEXT NOT NULL,
        field TEXT NOT NULL,
        value TEXT NOT NULL,
        confidence REAL DEFAULT 0.5,
        source TEXT DEFAULT 'declared' CHECK (source IN ('declared', 'inferred', 'confirmed')),
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(category, field)
    )"""),
    ("profile_narrative", """CREATE TABLE IF NOT EXISTS profile_narrative (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        narrative TEXT NOT NULL,
        field_count INTEGER NOT NULL,
        profile_hash TEXT NOT NULL,
        generated_at TEXT DEFAULT CURRENT_TIMESTAMP
    )"""),
    ("timeline", """CREATE TABLE IF NOT EXISTS timeline (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        event_date TEXT NOT NULL,
        date_precision TEXT DEFAULT 'day' CHECK (date_precision IN ('day', 'month', 'year')),
        title TEXT NOT NULL,
        description TEXT,
        category TEXT DEFAULT 'life' CHECK (category IN (
            'life', 'career', 'relationship', 'education',
            'health', 'location', 'project', 'milestone'
        )),
        significance INTEGER DEFAULT 5 CHECK (significance BETWEEN 1 AND 10),
        domain TEXT,
        tags TEXT DEFAULT '[]',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP
    )"""),
    ("conversations", """CREATE TABLE IF NOT EXISTS conversations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        chat_id INTEGER NOT NULL,
        session_id TEXT NOT NULL,
        role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
        content TEXT NOT NULL,
        impact_score REAL DEFAULT 0.0,
        promoted INTEGER DEFAULT 0,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )"""),
    ("conversation_sessions", """CREATE TABLE IF NOT EXISTS conversation_sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        chat_id INTEGER NOT NULL,
        session_id TEXT NOT NULL UNIQUE,
        started_at TEXT DEFAULT CURRENT_TIMESTAMP,
        last_message_at TEXT DEFAULT CURRENT_TIMESTAMP,
        message_count INTEGER DEFAULT 0,
        synthesized INTEGER DEFAULT 0,
        synthesized_at TEXT,
        synthesis_memory_id INTEGER REFERENCES memories(id)
    )"""),
    ("onboarding_sessions", """CREATE TABLE IF NOT EXISTS onboarding_sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT DEFAULT 'default',
        status TEXT DEFAULT 'active' CHECK (status IN ('active', 'paused', 'complete')),
        started_at TEXT DEFAULT CURRENT_TIMESTAMP,
        last_activity TEXT DEFAULT CURRENT_TIMESTAMP,
        completed_at TEXT,
        metadata TEXT DEFAULT '{}'
    )"""),
    ("onboarding_progress", """CREATE TABLE IF NOT EXISTS onboarding_progress (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id INTEGER REFERENCES onboarding_sessions(id) NOT NULL,
        channel TEXT NOT NULL,
        status TEXT DEFAULT 'not_started' CHECK (status IN ('not_started', 'in_progress', 'complete', 'skipped')),
        started_at TEXT,
        completed_at TEXT,
        fields_populated INTEGER DEFAULT 0,
        notes TEXT,
        UNIQUE(session_id, channel)
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
    ("events", """CREATE TABLE IF NOT EXISTS events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        type TEXT NOT NULL,
        payload TEXT DEFAULT '{}',
        source TEXT,
        session_id TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        urgency TEXT CHECK (urgency IN ('interrupt', 'digest', 'archive')),
        routed_at TEXT,
        channel TEXT,
        held_until TEXT
    )"""),
    ("agent_costs", """CREATE TABLE IF NOT EXISTS agent_costs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        execution_id INTEGER REFERENCES agent_executions(id),
        agent_name TEXT NOT NULL,
        model_id TEXT NOT NULL,
        task_type TEXT,
        input_tokens INTEGER DEFAULT 0,
        output_tokens INTEGER DEFAULT 0,
        cached_tokens INTEGER DEFAULT 0,
        thinking_tokens INTEGER DEFAULT 0,
        cost_usd REAL NOT NULL,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )"""),
    ("modes", """CREATE TABLE IF NOT EXISTS modes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT NOT NULL,
        mode TEXT NOT NULL CHECK (mode IN ('working', 'planning', 'capturing', 'reviewing')),
        entered_at TEXT DEFAULT CURRENT_TIMESTAMP,
        context_snapshot TEXT DEFAULT '{}',
        triggered_by TEXT
    )"""),
    ("reviews", """CREATE TABLE IF NOT EXISTS reviews (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        period_start TEXT,
        period_end TEXT,
        summary TEXT,
        projects_touched TEXT DEFAULT '[]',
        actions_completed INTEGER DEFAULT 0,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )"""),
    ("audio_session_reviews", """CREATE TABLE IF NOT EXISTS audio_session_reviews (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT DEFAULT '00000000-0000-0000-0000-000000000001',
        raw_transcript TEXT,
        summary TEXT,
        proposed_memories TEXT DEFAULT '[]',
        status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'accepted', 'rejected')),
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP
    )"""),
]

indexes = [
    "CREATE INDEX IF NOT EXISTS idx_memories_domain ON memories(domain)",
    "CREATE INDEX IF NOT EXISTS idx_memories_created ON memories(created_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_memories_source ON memories(source, source_id)",
    "CREATE INDEX IF NOT EXISTS idx_actions_status ON actions(status)",
    "CREATE INDEX IF NOT EXISTS idx_actions_domain ON actions(domain_id)",
    "CREATE INDEX IF NOT EXISTS idx_profile_category ON profile(category)",
    "CREATE INDEX IF NOT EXISTS idx_contexts_domain ON contexts(domain_id)",
    "CREATE INDEX IF NOT EXISTS idx_events_type ON events(type)",
    "CREATE INDEX IF NOT EXISTS idx_events_created ON events(created_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_events_source ON events(source, type)",
    "CREATE INDEX IF NOT EXISTS idx_agent_costs_agent ON agent_costs(agent_name, created_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_agent_costs_date ON agent_costs(created_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_agent_costs_exec ON agent_costs(execution_id)",
    "CREATE INDEX IF NOT EXISTS idx_conversations_session ON conversations(session_id, created_at)",
    "CREATE INDEX IF NOT EXISTS idx_conversations_role ON conversations(role, created_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_timeline_date ON timeline(event_date DESC)",
]

print("Creating brain tables...")
for name, sql in tables:
    try:
        db.execute(sql)
        print(f"  OK  {name}")
    except Exception as e:
        print(f"  ERR {name}: {e}")

print("\nCreating indexes...")
for idx_sql in indexes:
    try:
        db.execute(idx_sql)
        idx_name = idx_sql.split("IF NOT EXISTS ")[1].split(" ON")[0]
        print(f"  OK  {idx_name}")
    except Exception as e:
        print(f"  WARN {e}")

all_tables = db.fetch_all("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
print(f"\nTotal tables in database: {len(all_tables)}")
for t in all_tables:
    print(f"  - {t['name']}")

# Verify brain can write
try:
    db.execute("INSERT INTO memories (content, domain) VALUES (?, ?)",
               ("Brain tables verified on Windows libSQL", "promaia"))
    row = db.fetch_one("SELECT id, content FROM memories ORDER BY id DESC LIMIT 1")
    print(f"\nWRITE TEST PASSED: memory id={row['id']}")
except Exception as e:
    print(f"\nWRITE TEST FAILED: {e}")
