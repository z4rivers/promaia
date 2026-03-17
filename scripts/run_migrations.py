import logging
import sys
from pathlib import Path

# Ensure project root is in path
sys.path.append(str(Path(__file__).parent.parent))

from promaia.storage.db_factory import get_db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("migrations")

def run_startup_migrations():
    """Runs one-time schema updates and data migrations for the Layered Brain deployment."""
    logger.info("--- Running Pre-flight Database Migrations ---")
    db = get_db()
    
    # 1. Add active_domain to conversation_sessions
    try:
        db.execute("ALTER TABLE conversation_sessions ADD COLUMN active_domain TEXT DEFAULT NULL")
        logger.info("Successfully added 'active_domain' column to conversation_sessions.")
    except Exception as e:
        # SQLite throws 'duplicate column name' if it exists.
        logger.info(f"Skipped adding 'active_domain' column (likely already exists): {e}")

    # 2. Normalize memory tags (Option A Data Fix)
    try:
        from scripts.normalize_memories import normalize_memories
        normalize_memories()
        logger.info("Successfully normalized memory domains.")
    except Exception as e:
        logger.error(f"Failed to normalize memories: {e}")

    # 3. Purge Sedgwick domain and reclassify memories
    try:
        db.execute("DELETE FROM domains WHERE LOWER(name) = 'sedgwick'")
        db.execute("UPDATE memories SET domain = 'general' WHERE LOWER(domain) = 'sedgwick'")
        logger.info("Successfully purged 'sedgwick' domain.")
    except Exception as e:
        logger.error(f"Failed to purge sedgwick domain: {e}")

    logger.info("--- Pre-flight Migrations Complete ---")

if __name__ == "__main__":
    run_startup_migrations()
