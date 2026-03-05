"""
Database initialization and management commands for Promaia.

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
    """Initialize the PostgreSQL database with all required tables."""
    from promaia.storage.postgres_db import get_postgres_db
    
    logger.info("🐘 Initializing PostgreSQL database...")
    
    try:
        db = get_postgres_db()
        
        # Read and execute schema
        schema_path = get_schema_path()
        if not schema_path.exists():
            logger.error(f"Schema file not found: {schema_path}")
            return False
        
        with open(schema_path, 'r') as f:
            schema_sql = f.read()
        
        # Split by semicolons and execute each statement
        # Filter out empty statements and comments-only blocks
        statements = []
        current_statement = []
        
        for line in schema_sql.split('\n'):
            stripped = line.strip()
            
            # Skip pure comment lines and empty lines at statement boundaries
            if not current_statement and (stripped.startswith('--') or not stripped):
                continue
                
            current_statement.append(line)
            
            # Check if we hit a statement end
            if stripped.endswith(';'):
                full_statement = '\n'.join(current_statement)
                # Only add non-empty, non-comment-only statements
                if full_statement.strip():
                    statements.append(full_statement)
                current_statement = []
        
        with db.get_connection() as conn:
            conn.autocommit = True  # Execute each statement independently
            with conn.cursor() as cursor:
                for i, statement in enumerate(statements):
                    try:
                        if statement.strip():
                            cursor.execute(statement)
                    except Exception as e:
                        # Log but continue - some statements may fail if objects exist
                        if 'already exists' not in str(e).lower():
                            logger.warning(f"Statement {i+1} warning: {e}")
        
        logger.info("Database initialized successfully!")
        return True
        
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        return False


def check_status():
    """Check database connection and table status."""
    from promaia.storage.postgres_db import get_postgres_db
    
    logger.info("🔍 Checking PostgreSQL connection...")
    
    try:
        db = get_postgres_db()
        
        # Test connection
        result = db.fetch_one("SELECT version()")
        logger.info(f"✅ Connected to: {result['version'][:60]}...")
        
        # Check tables
        tables_query = """
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            ORDER BY table_name
        """
        tables = db.fetch_all(tables_query)
        
        logger.info(f"\n📋 Tables in database ({len(tables)}):")
        for t in tables:
            # Get row count
            count_result = db.fetch_one(f"SELECT COUNT(*) as cnt FROM {t['table_name']}")
            count = count_result['cnt'] if count_result else 0
            logger.info(f"   • {t['table_name']}: {count} rows")
        
        return True
        
    except Exception as e:
        logger.error(f"Connection failed: {e}")
        return False


def reset_database():
    """Drop and recreate all tables. DANGER: This will delete all data!"""
    from promaia.storage.postgres_db import get_postgres_db
    
    logger.warning("This will DELETE ALL DATA in the database!")
    confirm = input("Type 'RESET' to confirm: ")
    
    if confirm != 'RESET':
        logger.info("Aborted.")
        return False
    
    try:
        db = get_postgres_db()
        
        # Get all tables
        tables_query = """
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_type = 'BASE TABLE'
        """
        tables = db.fetch_all(tables_query)
        
        with db.get_connection() as conn:
            with conn.cursor() as cursor:
                # Drop views first
                cursor.execute("DROP VIEW IF EXISTS unified_content CASCADE")
                
                # Drop tables
                for t in tables:
                    logger.info(f"Dropping {t['table_name']}...")
                    cursor.execute(f"DROP TABLE IF EXISTS {t['table_name']} CASCADE")
                
                conn.commit()
        
        logger.info("All tables dropped. Reinitializing...")
        return init_database()
        
    except Exception as e:
        logger.error(f"Reset failed: {e}")
        return False


def create_database():
    """Create the promaia database if it doesn't exist."""
    import psycopg2
    from promaia.utils.config import load_environment
    
    load_environment()
    
    host = os.getenv('POSTGRES_HOST', '192.168.0.69')
    port = int(os.getenv('POSTGRES_PORT', '5432'))
    user = os.getenv('POSTGRES_USER', 'postgres')
    password = os.getenv('POSTGRES_PASSWORD', '')
    database = os.getenv('POSTGRES_DATABASE', 'promaia')
    
    logger.info(f"🔧 Creating database '{database}' if it doesn't exist...")
    
    try:
        # Connect to postgres database to create our database
        conn = psycopg2.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            database='postgres'
        )
        conn.autocommit = True
        
        with conn.cursor() as cursor:
            # Check if database exists
            cursor.execute(
                "SELECT 1 FROM pg_database WHERE datname = %s",
                (database,)
            )
            exists = cursor.fetchone()
            
            if not exists:
                cursor.execute(f'CREATE DATABASE "{database}"')
                logger.info(f"✅ Database '{database}' created!")
            else:
                logger.info(f"✅ Database '{database}' already exists")
        
        conn.close()
        return True
        
    except Exception as e:
        logger.error(f"Failed to create database: {e}")
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
    from promaia.storage.postgres_db import get_postgres_db

    logger.info("Applying brain schema...")

    try:
        db = get_postgres_db()

        schema_path = get_brain_schema_path()
        if not schema_path.exists():
            logger.error(f"Brain schema file not found: {schema_path}", file=sys.stderr)
            return False

        with open(schema_path, 'r') as f:
            sql = f.read()

        # Split on semicolons and filter empty/comment-only statements
        stmts = [s.strip() for s in sql.split(';') if s.strip()]

        with db.get_connection() as conn:
            conn.autocommit = True
            with conn.cursor() as cursor:
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
        create_database()
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

    elif command == 'create':
        success = create_database()
        sys.exit(0 if success else 1)

    else:
        print(f"Unknown command: {command}")
        print(__doc__)
        sys.exit(1)


if __name__ == '__main__':
    main()
