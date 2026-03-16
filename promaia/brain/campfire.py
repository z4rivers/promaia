"""
The Campfire: persistent session snapshots for cross-agent continuity.
Allows Claude, Maia, and Voice Agent to see what each other did.
"""
import json
import logging
from typing import Optional, List, Dict, Any
from promaia.storage.db_factory import get_db

logger = logging.getLogger(__name__)

async def save_snapshot(
    agent: str,
    summary: str,
    session_id: Optional[str] = None,
    status: str = "complete",
    topics: List[str] = None,
    decisions: List[Dict[str, Any]] = None,
    next_steps: List[Dict[str, Any]] = None,
    active_files: List[str] = None,
    branch: Optional[str] = None,
) -> int:
    """Saves a session snapshot to the Campfire."""
    db = get_db()
    
    topics_json = json.dumps(topics or [])
    decisions_json = json.dumps(decisions or [])
    next_steps_json = json.dumps(next_steps or [])
    files_json = json.dumps(active_files or [])
    
    try:
        snapshot_id = db.insert_returning(
            """
            INSERT INTO session_snapshots (
                agent, session_id, status, summary, topics, 
                decisions, next_steps, active_files, branch
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (agent, session_id, status, summary, topics_json, 
             decisions_json, next_steps_json, files_json, branch)
        )
        logger.info(f"Campfire snapshot saved for {agent} (ID: {snapshot_id})")
        return snapshot_id
    except Exception as e:
        logger.error(f"Failed to save Campfire snapshot: {e}")
        return 0

async def get_latest_snapshots(limit: int = 5) -> List[Dict[str, Any]]:
    """Retrieves the latest snapshots from all agents."""
    db = get_db()
    try:
        rows = db.fetch_all(
            "SELECT * FROM session_snapshots ORDER BY created_at DESC LIMIT %s",
            (limit,)
        )
        return rows
    except Exception as e:
        logger.error(f"Failed to retrieve Campfire snapshots: {e}")
        return []

async def get_agent_status() -> Dict[str, str]:
    """Returns the latest status for each agent."""
    db = get_db()
    try:
        rows = db.fetch_all(
            """
            SELECT agent, status, created_at 
            FROM session_snapshots 
            WHERE id IN (SELECT MAX(id) FROM session_snapshots GROUP BY agent)
            """
        )
        return {r['agent']: r['status'] for r in rows}
    except Exception as e:
        logger.error(f"Failed to get agent statuses: {e}")
        return {}
