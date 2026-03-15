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

        with open(schema_path, 'r') as f:
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


def get_brain_schema_path() -> Path:
    """Get path to the brain schema.sql file."""
    return Path(__file__).parent.parent / "brain" / "schema.sql"


def apply_brain_schema():
    """Apply the brain schema idempotently.

    Reads promaia/brain/schema.sql, splits statements by semicolons,
    and executes each within a transaction. Safe to run multiple times
    (all DDL uses CREATE IF NOT EXISTS).

    Returns True on success, False on failure.
    """
    from promaia.storage.db_factory import get_db

    logger.info("Applying brain schema...")

    try:
        db = get_db()

        schema_path = get_brain_schema_path()
        if not schema_path.exists():
            logger.error(f"Brain schema file not found: {schema_path}")
            return False

        with open(schema_path, 'r') as f:
            sql = f.read()

        # Split on semicolons and filter empty/comment-only statements
        stmts = [s.strip() for s in sql.split(';') if s.strip()]

        with db.get_connection() as conn:
            cursor = conn.cursor()
            for stmt in stmts:
                # Skip pure comment blocks
                non_comment = '\n'.join(
                    line for line in stmt.splitlines()
                    if not line.strip().startswith('--')
                ).strip()
                if not non_comment:
                    continue
                try:
                    cursor.execute(stmt)
                except Exception as e:
                    if 'already exists' not in str(e).lower():
                        logger.warning(f"Brain schema statement warning: {e}")
            conn.commit()

        print("Brain schema applied successfully.", file=sys.stderr)
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
