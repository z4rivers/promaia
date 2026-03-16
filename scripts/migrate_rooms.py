import sys
import os
import logging

# Ensure absolute import path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from promaia.storage.db_factory import get_db

logger = logging.getLogger(__name__)

def migrate_rooms():
    db = get_db()
    
    # 1. Create rooms table
    logger.info("Creating rooms table...")
    db.execute("""
    CREATE TABLE IF NOT EXISTS rooms (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        name        TEXT NOT NULL,
        room_type   TEXT DEFAULT 'topic',      -- "main", "topic", "summon"
        topic       TEXT,                      -- what this room is about
        artifact_ref TEXT,                     -- optional: the thing being worked on
        created_by  TEXT NOT NULL,             -- who created it
        status      TEXT DEFAULT 'active',     -- "active", "dissolved"
        created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        dissolved_at TIMESTAMP                 -- when room was completed
    );
    """)
    
    # 2. Extract current rows to check if Main room exists
    res = db.fetch_all("SELECT id FROM rooms WHERE id = 1")
    if not res:
        logger.info("Seeding Main room (id 1)...")
        db.execute("INSERT INTO rooms (id, name, room_type, created_by) VALUES (1, 'Main', 'main', 'zack')")
        
    # 3. Create room_members table
    logger.info("Creating room_members table...")
    db.execute("""
    CREATE TABLE IF NOT EXISTS room_members (
        room_id     INTEGER NOT NULL,
        agent_name  TEXT NOT NULL,
        role        TEXT DEFAULT 'member',     -- "owner", "member"
        invited_by  TEXT NOT NULL,
        joined_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (room_id, agent_name)
    );
    """)
    
    # Check if Main room members exist
    res = db.fetch_all("SELECT agent_name FROM room_members WHERE room_id = 1")
    if not res:
        logger.info("Seeding Main room members (zack, maia)...")
        db.execute("INSERT INTO room_members (room_id, agent_name, role, invited_by) VALUES (1, 'zack', 'owner', 'zack')")
        db.execute("INSERT INTO room_members (room_id, agent_name, role, invited_by) VALUES (1, 'maia', 'member', 'zack')")

    # 4. Add room_id to messages
    logger.info("Adding room_id column to messages table (if it doesn't exist)...")
    try:
        db.execute("ALTER TABLE messages ADD COLUMN room_id INTEGER DEFAULT NULL;")
    except Exception as e:
        if "duplicate column name" in str(e).lower() or "already exists" in str(e).lower() or "syntax error" in str(e).lower():
            # libSQL/SQLite alter table error handling is sometimes weird, but usually duplicate column returns an error
            logger.info(f"room_id might already exist. Ignored. (Msg: {e})")
        else:
            logger.error(f"Error adding room_id: {e}")
            
    logger.info("Migration complete!")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    migrate_rooms()
