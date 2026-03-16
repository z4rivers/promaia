"""
Database initialization and management commands for Promaia (libSQL).

Usage:
    python -m promaia.storage.db_init init          # Initialize public schema
    python -m promaia.storage.db_init init-brain     # Apply brain schema (idempotent)
    python -m promaia.storage.db_init status         # Check connection status
    python -m promaia.storage.db_init reset          # Drop and recreate all tables (DANGER!)
"""
import os
import sys
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def get_schema_path() -> Path:
    """Get path to the schema.sql file."""
    return Path(__file__).parent / "schema.sql"


def init_database():
    """Initialize the libSQL database with all required tables."""
    from promaia.storage.db_factory import get_db

    logger.info("Initializing libSQL database...")

    try:
        db = get_db()

        # Read and execute schema
        schema_path = get_schema_path()
        if not schema_path.exists():
            logger.error(f"Schema file not found: {schema_path}")
            return False

        with open(schema_path, 'r', encoding='utf-8') as f:
            schema_sql = f.read()

        # Split by semicolons and execute each statement
        statements = []
        current_statement = []

        for line in schema_sql.split('\n'):
            stripped = line.strip()

            if not current_statement and (stripped.startswith('--') or not stripped):
                continue

            current_statement.append(line)

            if stripped.endswith(';'):
                full_statement = '\n'.join(current_statement)
                if full_statement.strip():
                    statements.append(full_statement)
                current_statement = []

        with db.get_connection() as conn:
            cursor = conn.cursor()
            for i, statement in enumerate(statements):
                try:
                    if statement.strip():
                        cursor.execute(statement)
                except Exception as e:
                    if 'already exists' not in str(e).lower():
                        logger.warning(f"Statement {i+1} warning: {e}")
            conn.commit()

        logger.info("Database initialized successfully!")
        return True

    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        return False


def check_status():
    """Check database connection and table status."""
    from promaia.storage.db_factory import get_db

    logger.info("Checking libSQL connection...")

    try:
        db = get_db()

        # Test connection
        result = db.fetch_one("SELECT sqlite_version() as version")
        logger.info(f"Connected to SQLite: {result['version']}")

        # Check tables (SQLite uses sqlite_master instead of information_schema)
        tables = db.fetch_all(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )

        logger.info(f"\nTables in database ({len(tables)}):")
        for t in tables:
            count_result = db.fetch_one(f"SELECT COUNT(*) as cnt FROM [{t['name']}]")
            count = count_result['cnt'] if count_result else 0
            logger.info(f"   {t['name']}: {count} rows")

        return True

    except Exception as e:
        logger.error(f"Connection failed: {e}")
        return False


def reset_database():
    """Drop and recreate all tables. DANGER: This will delete all data!"""
    from promaia.storage.db_factory import get_db

    logger.warning("This will DELETE ALL DATA in the database!")
    confirm = input("Type 'RESET' to confirm: ")

    if confirm != 'RESET':
        logger.info("Aborted.")
        return False

    try:
        db = get_db()

        # Get all tables (SQLite)
        tables = db.fetch_all(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        )

        with db.get_connection() as conn:
            cursor = conn.cursor()

            # Drop views first
            views = db.fetch_all(
                "SELECT name FROM sqlite_master WHERE type='view'"
            )
            for v in views:
                cursor.execute(f"DROP VIEW IF EXISTS [{v['name']}]")

            # Drop tables
            for t in tables:
                logger.info(f"Dropping {t['name']}...")
                cursor.execute(f"DROP TABLE IF EXISTS [{t['name']}]")

            conn.commit()

        logger.info("All tables dropped. Reinitializing...")
        return init_database()

    except Exception as e:
        logger.error(f"Reset failed: {e}")
        return False


def apply_brain_schema():
    """Apply the brain schema idempotently for libSQL.

    Creates all brain tables using SQLite-compatible DDL.
    The original Postgres DDL has been archived to brain/schema.sql.postgres-legacy.
    The canonical schema source is now scripts/create_brain_tables_windows.py.

    Returns True on success, False on failure.
    """
    from promaia.storage.db_factory import get_db

    logger.info("Applying brain schema (libSQL)...")

    try:
        db = get_db()

        # SQLite-compatible brain table definitions
        # Translated from Postgres: SERIAL->INTEGER PRIMARY KEY AUTOINCREMENT,
        # TIMESTAMPTZ->TEXT, JSONB->TEXT, TEXT[]->TEXT, vector(768)->omitted,
        # brain.X->X (no schema prefix)
        tables = [
            """CREATE TABLE IF NOT EXISTS domains (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                description TEXT,
                is_project INTEGER DEFAULT 1,
                parent_domain INTEGER REFERENCES domains(id),
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )""",
            """CREATE TABLE IF NOT EXISTS contexts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                domain_id INTEGER REFERENCES domains(id) NOT NULL,
                directive TEXT,
                current_state TEXT,
                last_updated TEXT DEFAULT CURRENT_TIMESTAMP,
                priority INTEGER DEFAULT 5,
                stale_threshold_days INTEGER DEFAULT 7
            )""",
            """CREATE TABLE IF NOT EXISTS memories (
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
            )""",
            """CREATE TABLE IF NOT EXISTS actions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                memory_id INTEGER REFERENCES memories(id),
                domain_id INTEGER REFERENCES domains(id),
                description TEXT NOT NULL,
                status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'done', 'stale')),
                extracted_at TEXT DEFAULT CURRENT_TIMESTAMP,
                completed_at TEXT
            )""",
            """CREATE TABLE IF NOT EXISTS profile (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT NOT NULL,
                field TEXT NOT NULL,
                value TEXT NOT NULL,
                confidence REAL DEFAULT 0.5,
                source TEXT DEFAULT 'declared' CHECK (source IN ('declared', 'inferred', 'confirmed')),
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(category, field)
            )""",
            """CREATE TABLE IF NOT EXISTS profile_narrative (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                narrative TEXT NOT NULL,
                field_count INTEGER NOT NULL,
                profile_hash TEXT NOT NULL,
                generated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )""",
            """CREATE TABLE IF NOT EXISTS timeline (
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
            )""",
            """CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER NOT NULL,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
                content TEXT NOT NULL,
                impact_score REAL DEFAULT 0.0,
                promoted INTEGER DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )""",
            """CREATE TABLE IF NOT EXISTS conversation_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER NOT NULL,
                session_id TEXT NOT NULL UNIQUE,
                started_at TEXT DEFAULT CURRENT_TIMESTAMP,
                last_message_at TEXT DEFAULT CURRENT_TIMESTAMP,
                message_count INTEGER DEFAULT 0,
                synthesized INTEGER DEFAULT 0,
                synthesized_at TEXT,
                synthesis_memory_id INTEGER REFERENCES memories(id)
            )""",
            """CREATE TABLE IF NOT EXISTS onboarding_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT DEFAULT 'default',
                status TEXT DEFAULT 'active' CHECK (status IN ('active', 'paused', 'complete')),
                started_at TEXT DEFAULT CURRENT_TIMESTAMP,
                last_activity TEXT DEFAULT CURRENT_TIMESTAMP,
                completed_at TEXT,
                metadata TEXT DEFAULT '{}'
            )""",
            """CREATE TABLE IF NOT EXISTS onboarding_progress (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER REFERENCES onboarding_sessions(id) NOT NULL,
                channel TEXT NOT NULL,
                status TEXT DEFAULT 'not_started' CHECK (status IN ('not_started', 'in_progress', 'complete', 'skipped')),
                started_at TEXT,
                completed_at TEXT,
                fields_populated INTEGER DEFAULT 0,
                notes TEXT,
                UNIQUE(session_id, channel)
            )""",
            """CREATE TABLE IF NOT EXISTS agent_executions (
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
            )""",
            """CREATE TABLE IF NOT EXISTS events (
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
            )""",
            """CREATE TABLE IF NOT EXISTS agent_costs (
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
            )""",
            """CREATE TABLE IF NOT EXISTS modes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                mode TEXT NOT NULL CHECK (mode IN ('working', 'planning', 'capturing', 'reviewing')),
                entered_at TEXT DEFAULT CURRENT_TIMESTAMP,
                context_snapshot TEXT DEFAULT '{}',
                triggered_by TEXT
            )""",
            """CREATE TABLE IF NOT EXISTS reviews (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                period_start TEXT,
                period_end TEXT,
                summary TEXT,
                projects_touched TEXT DEFAULT '[]',
                actions_completed INTEGER DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )""",
            """CREATE TABLE IF NOT EXISTS audio_session_reviews (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT DEFAULT '00000000-0000-0000-0000-000000000001',
                raw_transcript TEXT,
                summary TEXT,
                proposed_memories TEXT DEFAULT '[]',
                status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'accepted', 'rejected')),
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )""",
        ]

        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_memories_domain ON memories(domain)",
            "CREATE INDEX IF NOT EXISTS idx_memories_created ON memories(created_at DESC)",
            "CREATE INDEX IF NOT EXISTS idx_actions_status ON actions(status)",
            "CREATE INDEX IF NOT EXISTS idx_profile_category ON profile(category)",
            "CREATE INDEX IF NOT EXISTS idx_events_type ON events(type)",
            "CREATE INDEX IF NOT EXISTS idx_events_source ON events(source)",
            "CREATE INDEX IF NOT EXISTS idx_events_created_at ON events(created_at DESC)",
            "CREATE INDEX IF NOT EXISTS idx_events_session_id ON events(session_id)",
            "CREATE INDEX IF NOT EXISTS idx_onboarding_sessions_user_id ON onboarding_sessions(user_id)",
            "CREATE INDEX IF NOT EXISTS idx_onboarding_progress_session_id ON onboarding_progress(session_id)",
            "CREATE INDEX IF NOT EXISTS idx_timeline_event_date ON timeline(event_date)",
            "CREATE INDEX IF NOT EXISTS idx_timeline_category ON timeline(category)",
            "CREATE INDEX IF NOT EXISTS idx_agent_costs_agent ON agent_costs(agent_name, created_at DESC)",
            "CREATE INDEX IF NOT EXISTS idx_agent_costs_date ON agent_costs(created_at DESC)",
            "CREATE INDEX IF NOT EXISTS idx_agent_costs_execution ON agent_costs(execution_id)",
            "CREATE INDEX IF NOT EXISTS idx_conversations_chat_session ON conversations(chat_id, session_id, created_at)",
            "CREATE INDEX IF NOT EXISTS idx_conversations_chat_recent ON conversations(chat_id, created_at DESC)",
            "CREATE INDEX IF NOT EXISTS idx_conv_sessions_chat ON conversation_sessions(chat_id, started_at DESC)",
            "CREATE INDEX IF NOT EXISTS idx_audio_review_status ON audio_session_reviews(status, created_at DESC)",
        ]

        with db.get_connection() as conn:
            cursor = conn.cursor()
            for stmt in tables:
                try:
                    cursor.execute(stmt)
                except Exception as e:
                    if 'already exists' not in str(e).lower():
                        logger.warning(f"Brain table warning: {e}")
            for idx in indexes:
                try:
                    cursor.execute(idx)
                except Exception as e:
                    if 'already exists' not in str(e).lower():
                        logger.warning(f"Brain index warning: {e}")
            conn.commit()

        print("Brain schema applied successfully (libSQL).", file=sys.stderr)
        return True

    except Exception as e:
        logger.error(f"Brain schema application failed: {e}")
        return False


def main():
    """Main entry point for database management."""
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    command = sys.argv[1].lower()

    if command == 'init':
        success = init_database()
        sys.exit(0 if success else 1)

    elif command == 'init-brain':
        success = apply_brain_schema()
        sys.exit(0 if success else 1)

    elif command == 'status':
        success = check_status()
        sys.exit(0 if success else 1)

    elif command == 'reset':
        success = reset_database()
        sys.exit(0 if success else 1)

    else:
        print(f"Unknown command: {command}")
        print(__doc__)
        sys.exit(1)


if __name__ == '__main__':
    main()
