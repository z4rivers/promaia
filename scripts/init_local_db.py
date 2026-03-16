"""
Initialize promaia.db with ALL tables needed for local dev.
Combines:
  - Storage tables from schema_libsql.sql (minus vector tables that need libSQL-specific syntax)
  - Brain tables translated from brain/schema.sql (Postgres -> SQLite)
  
Run: python scripts/init_local_db.py
"""
import sqlite3
import os
import sys

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "promaia.db")

# ---- Brain tables (translated from brain/schema.sql) ----
# Key changes from Postgres:
#   SERIAL -> INTEGER PRIMARY KEY AUTOINCREMENT
#   TIMESTAMPTZ -> TEXT
#   JSONB -> TEXT  (we store JSON as text, parse in Python)
#   TEXT[] -> TEXT  (store as JSON array string)
#   vector(768) -> (omitted for now, handled separately)
#   brain.X -> X  (no schema prefix in SQLite)
#   CHECK constraints preserved where compatible

BRAIN_SCHEMA = """
-- ============================================================
-- memories
-- ============================================================
CREATE TABLE IF NOT EXISTS memories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    content TEXT NOT NULL,
    summary TEXT,
    domain TEXT,
    tags TEXT DEFAULT '[]',
    entities TEXT DEFAULT '{}',
    source TEXT,
    source_id TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_memories_domain ON memories(domain);
CREATE INDEX IF NOT EXISTS idx_memories_created ON memories(created_at DESC);

-- ============================================================
-- domains
-- ============================================================
CREATE TABLE IF NOT EXISTS domains (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    description TEXT,
    is_project INTEGER DEFAULT 1,
    parent_domain INTEGER REFERENCES domains(id),
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================
-- contexts
-- ============================================================
CREATE TABLE IF NOT EXISTS contexts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    domain_id INTEGER REFERENCES domains(id) NOT NULL,
    directive TEXT,
    current_state TEXT,
    last_updated TEXT DEFAULT CURRENT_TIMESTAMP,
    priority INTEGER DEFAULT 5,
    stale_threshold_days INTEGER DEFAULT 7
);

-- ============================================================
-- actions
-- ============================================================
CREATE TABLE IF NOT EXISTS actions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    memory_id INTEGER REFERENCES memories(id),
    domain_id INTEGER REFERENCES domains(id),
    description TEXT NOT NULL,
    status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'done', 'stale')),
    extracted_at TEXT DEFAULT CURRENT_TIMESTAMP,
    completed_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_actions_status ON actions(status);

-- ============================================================
-- reviews
-- ============================================================
CREATE TABLE IF NOT EXISTS reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    period_start TEXT,
    period_end TEXT,
    summary TEXT,
    projects_touched TEXT DEFAULT '[]',
    actions_completed INTEGER DEFAULT 0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================
-- events
-- ============================================================
CREATE TABLE IF NOT EXISTS events (
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
);

CREATE INDEX IF NOT EXISTS idx_events_type ON events(type);
CREATE INDEX IF NOT EXISTS idx_events_source ON events(source);
CREATE INDEX IF NOT EXISTS idx_events_created_at ON events(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_events_session_id ON events(session_id);

-- ============================================================
-- profile
-- ============================================================
CREATE TABLE IF NOT EXISTS profile (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category TEXT NOT NULL,
    field TEXT NOT NULL,
    value TEXT NOT NULL,
    confidence REAL DEFAULT 0.5,
    source TEXT DEFAULT 'declared' CHECK (source IN ('declared', 'inferred', 'confirmed')),
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(category, field)
);

CREATE INDEX IF NOT EXISTS idx_profile_category ON profile(category);

-- ============================================================
-- modes
-- ============================================================
CREATE TABLE IF NOT EXISTS modes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    mode TEXT NOT NULL CHECK (mode IN ('working', 'planning', 'capturing', 'reviewing')),
    entered_at TEXT DEFAULT CURRENT_TIMESTAMP,
    context_snapshot TEXT DEFAULT '{}',
    triggered_by TEXT
);

-- ============================================================
-- onboarding_sessions
-- ============================================================
CREATE TABLE IF NOT EXISTS onboarding_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT DEFAULT 'default',
    status TEXT DEFAULT 'active' CHECK (status IN ('active', 'paused', 'complete')),
    started_at TEXT DEFAULT CURRENT_TIMESTAMP,
    last_activity TEXT DEFAULT CURRENT_TIMESTAMP,
    completed_at TEXT,
    metadata TEXT DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_onboarding_sessions_user_id ON onboarding_sessions(user_id);

-- ============================================================
-- onboarding_progress
-- ============================================================
CREATE TABLE IF NOT EXISTS onboarding_progress (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER REFERENCES onboarding_sessions(id) NOT NULL,
    channel TEXT NOT NULL,
    status TEXT DEFAULT 'not_started' CHECK (status IN ('not_started', 'in_progress', 'complete', 'skipped')),
    started_at TEXT,
    completed_at TEXT,
    fields_populated INTEGER DEFAULT 0,
    notes TEXT,
    UNIQUE(session_id, channel)
);

CREATE INDEX IF NOT EXISTS idx_onboarding_progress_session_id ON onboarding_progress(session_id);

-- ============================================================
-- timeline
-- ============================================================
CREATE TABLE IF NOT EXISTS timeline (
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
);

CREATE INDEX IF NOT EXISTS idx_timeline_event_date ON timeline(event_date);
CREATE INDEX IF NOT EXISTS idx_timeline_category ON timeline(category);

-- ============================================================
-- agent_executions (needed before agent_costs FK)
-- ============================================================
CREATE TABLE IF NOT EXISTS agent_executions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_name TEXT NOT NULL,
    status TEXT DEFAULT 'running',
    started_at TEXT DEFAULT CURRENT_TIMESTAMP,
    completed_at TEXT,
    result TEXT,
    error TEXT,
    metadata TEXT DEFAULT '{}'
);

-- ============================================================
-- agent_costs
-- ============================================================
CREATE TABLE IF NOT EXISTS agent_costs (
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
);

CREATE INDEX IF NOT EXISTS idx_agent_costs_agent ON agent_costs(agent_name, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_agent_costs_date ON agent_costs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_agent_costs_execution ON agent_costs(execution_id);

-- ============================================================
-- conversations
-- ============================================================
CREATE TABLE IF NOT EXISTS conversations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id INTEGER NOT NULL,
    session_id TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content TEXT NOT NULL,
    impact_score REAL DEFAULT 0.0,
    promoted INTEGER DEFAULT 0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_conversations_chat_session ON conversations(chat_id, session_id, created_at);
CREATE INDEX IF NOT EXISTS idx_conversations_chat_recent ON conversations(chat_id, created_at DESC);

-- ============================================================
-- conversation_sessions
-- ============================================================
CREATE TABLE IF NOT EXISTS conversation_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id INTEGER NOT NULL,
    session_id TEXT NOT NULL UNIQUE,
    started_at TEXT DEFAULT CURRENT_TIMESTAMP,
    last_message_at TEXT DEFAULT CURRENT_TIMESTAMP,
    message_count INTEGER DEFAULT 0,
    synthesized INTEGER DEFAULT 0,
    synthesized_at TEXT,
    synthesis_memory_id INTEGER REFERENCES memories(id)
);

CREATE INDEX IF NOT EXISTS idx_conv_sessions_chat ON conversation_sessions(chat_id, started_at DESC);

-- ============================================================
-- profile_narrative
-- ============================================================
CREATE TABLE IF NOT EXISTS profile_narrative (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    narrative TEXT NOT NULL,
    field_count INTEGER NOT NULL,
    profile_hash TEXT NOT NULL,
    generated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================
-- audio_session_reviews
-- ============================================================
CREATE TABLE IF NOT EXISTS audio_session_reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT DEFAULT '00000000-0000-0000-0000-000000000001',
    raw_transcript TEXT,
    summary TEXT,
    proposed_memories TEXT DEFAULT '[]',
    status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'accepted', 'rejected')),
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_audio_review_status ON audio_session_reviews(status, created_at DESC);

-- ============================================================
-- staged_memories
-- ============================================================
CREATE TABLE IF NOT EXISTS staged_memories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT DEFAULT 'zack',
    surface TEXT NOT NULL,         -- 'voice', 'web', etc.
    content TEXT NOT NULL,
    domain TEXT,
    confidence REAL DEFAULT 0.8,
    status TEXT DEFAULT 'staged',  -- 'staged', 'committed', 'expired'
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_staged_memories_user_status ON staged_memories(user_id, status);

-- ============================================================
-- session_snapshots (The Campfire)
-- ============================================================
CREATE TABLE IF NOT EXISTS session_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    agent TEXT NOT NULL,           -- 'claude', 'maia', 'voice', 'morning-briefing'
    session_id TEXT,
    status TEXT DEFAULT 'complete' CHECK (status IN ('in_progress', 'complete', 'awaiting_review', 'handed_off')),
    summary TEXT NOT NULL,
    topics TEXT DEFAULT '[]',      -- JSON array
    decisions TEXT DEFAULT '[]',   -- JSON array
    next_steps TEXT DEFAULT '[]',  -- JSON array
    active_files TEXT DEFAULT '[]',-- JSON array
    branch TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_snapshots_agent_recent ON session_snapshots(agent, created_at DESC);
"""

def main():
    print(f"Initializing database at: {DB_PATH}")
    
    db = sqlite3.connect(DB_PATH)
    
    # 1. Run storage schema (non-vector portion)
    storage_schema_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        "promaia", "storage", "schema_libsql.sql"
    )
    
    if os.path.exists(storage_schema_path):
        print("  [1/3] Reading storage schema...")
        with open(storage_schema_path) as f:
            storage_sql = f.read()
        
        # Remove the vector-specific tables that use F32_BLOB and libsql_vector_idx
        # We'll handle those separately once we have the vector engine sorted
        lines = storage_sql.split('\n')
        filtered_lines = []
        skip = False
        for line in lines:
            # Skip content_embeddings and property_embeddings table blocks
            if 'CONTENT EMBEDDINGS TABLE' in line or 'PROPERTY EMBEDDINGS TABLE' in line:
                skip = True
            if skip and line.strip() == '' and filtered_lines and filtered_lines[-1].strip() == '':
                continue
            if not skip:
                filtered_lines.append(line)
            # Stop skipping at the next section header or end
            if skip and line.startswith('-- =====') and ('CONTENT EMBEDDINGS' not in line and 'PROPERTY EMBEDDINGS' not in line):
                skip = False
                filtered_lines.append(line)
        
        storage_sql_filtered = '\n'.join(filtered_lines)
        
        try:
            db.executescript(storage_sql_filtered)
            print("  [1/3] ✅ Storage tables created")
        except Exception as e:
            print(f"  [1/3] ⚠️  Storage schema partial: {e}")
    else:
        print(f"  [1/3] ⚠️  Storage schema not found at {storage_schema_path}")
    
    # 2. Run brain schema
    print("  [2/3] Creating brain tables...")
    try:
        db.executescript(BRAIN_SCHEMA)
        print("  [2/3] ✅ Brain tables created")
    except Exception as e:
        print(f"  [2/3] ❌ Brain schema error: {e}")
        sys.exit(1)
    
    # 3. Verify
    print("  [3/3] Verifying tables...")
    cursor = db.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = [row[0] for row in cursor.fetchall()]
    print(f"  [3/3] ✅ {len(tables)} tables found:")
    for t in tables:
        count = db.execute(f"SELECT COUNT(*) FROM [{t}]").fetchone()[0]
        print(f"         - {t} ({count} rows)")
    
    db.close()
    print(f"\n✅ Database initialized at {DB_PATH}")

if __name__ == "__main__":
    main()
