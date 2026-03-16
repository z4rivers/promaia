import json
import time
import uuid
from typing import List, Dict, Any, Optional
from promaia.storage.db_factory import get_db
import logging

logger = logging.getLogger(__name__)

class SignalsDB:
    def __init__(self):
        self.db = get_db()
        self._ensure_presence("maia")
        self._ensure_presence("claude-code")
        self._ensure_presence("gemini")
        self._ensure_presence("morning-briefing")

    def _ensure_presence(self, agent_name: str):
        query = """
        INSERT INTO presence (agent_name, status, last_active)
        VALUES (?, 'offline', CURRENT_TIMESTAMP)
        ON CONFLICT(agent_name) DO NOTHING;
        """
        try:
            self.db.execute(query, (agent_name,))
        except Exception as e:
            logger.error(f"Error ensuring presence for {agent_name}: {e}")

    def update_presence(self, agent_name: str, status: str = 'online', working_on: str = None, active_files: List[str] = None):
        """Update the agent's presence status. Automatically updates last_active."""
        active_files_json = json.dumps(active_files) if active_files is not None else None
        
        query = """
        UPDATE presence
        SET status = ?, 
            last_active = CURRENT_TIMESTAMP,
            working_on = COALESCE(?, working_on),
            active_files = COALESCE(?, active_files)
        WHERE agent_name = ?;
        """
        res = self.db.execute(query, (status, working_on, active_files_json, agent_name))
        if res == 0:
            # Agent didn't exist, insert
            ins_query = """
            INSERT INTO presence (agent_name, status, last_active, working_on, active_files)
            VALUES (?, ?, CURRENT_TIMESTAMP, ?, ?)
            """
            self.db.execute(ins_query, (agent_name, status, working_on, active_files_json))

    def get_online_agents(self) -> List[Dict[str, Any]]:
        """Return a list of agents currently online."""
        # Also do a quick GC check here just in case
        self.run_garbage_collection()
        
        query = "SELECT * FROM presence WHERE status IN ('online', 'idle') ORDER BY last_active DESC;"
        return self.db.fetch_all(query)

    def send_message(self, from_agent: str, to_agent: Optional[str], msg_type: str, subject: str, 
                     body: str, context_payload: dict = None, priority: str = 'normal', reply_to: str = None) -> str:
        context_json = json.dumps(context_payload) if context_payload else None
        msg_uuid = str(uuid.uuid4())
        
        # If reply_to is provided, inherit context_id from parent if not present
        context_id = None
        if reply_to:
            parent = self.get_message(reply_to)
            if parent:
                context_id = parent.get("context_id")
        
        if not context_id:
            context_id = f"ctx_{int(time.time()*1000)}"
            
        query = """
        INSERT INTO messages 
        (uuid, from_agent, to_agent, context_id, msg_type, subject, body, context, priority, status, reply_to)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'new', ?)
        """
        self.db.execute(query, (msg_uuid, from_agent, to_agent, context_id, msg_type, subject, body, context_json, priority, reply_to))
        
        # Log to structured JSONL for observability (simulated via events table for now)
        event_query = "INSERT INTO events (type, source, payload) VALUES (?, ?, ?)"
        self.db.execute(event_query, ("message_sent", from_agent, json.dumps({"uuid": msg_uuid, "to": to_agent, "type": msg_type})))
        
        self.update_presence(from_agent, status='online')
        return msg_uuid

    def get_message(self, msg_uuid: str) -> Optional[Dict[str, Any]]:
        query = "SELECT * FROM messages WHERE uuid = ?"
        return self.db.fetch_one(query, (msg_uuid,))

    def check_inbox(self, agent_name: str) -> List[Dict[str, Any]]:
        """Check for 'new' or 'seen' messages for this agent, or broadcast messages."""
        # GC first
        self.run_garbage_collection()
        self.update_presence(agent_name, status='online')
        
        query = """
        SELECT * FROM messages 
        WHERE (to_agent = ? OR to_agent IS NULL) 
        AND status IN ('new', 'seen')
        ORDER BY created_at ASC;
        """
        return self.db.fetch_all(query, (agent_name,))

    def pickup_message(self, msg_uuid: str, agent_name: str, active_files: List[str] = None) -> bool:
        """Mark a message as 'in_progress' and update presence to reflect it."""
        msg = self.get_message(msg_uuid)
        if not msg:
            return False
            
        query = "UPDATE messages SET status = 'in_progress', acked_at = (STRFTIME('%Y-%m-%dT%H:%M:%fZ', 'NOW')) WHERE uuid = ?;"
        self.db.execute(query, (msg_uuid,))
            
        self.update_presence(agent_name, status='online', working_on=msg_uuid, active_files=active_files)
        return True

    def complete_message(self, msg_uuid: str, agent_name: str) -> bool:
        """Mark a message and its entire context thread as 'done'."""
        msg = self.get_message(msg_uuid)
        if not msg:
            return False
            
        # Complete all messages in this context
        ctx = msg['context_id']
        query = "UPDATE messages SET status = 'done' WHERE context_id = ?;"
        self.db.execute(query, (ctx,))
            
        # Clear presence working_on if it was this
        clear_query = "UPDATE presence SET working_on = NULL, active_files = NULL WHERE agent_name = ? AND working_on = ?"
        self.db.execute(clear_query, (agent_name, msg_uuid))
            
        return True

    def get_thread(self, msg_uuid: str) -> List[Dict[str, Any]]:
        """Get all messages with the same context_id as this message."""
        msg = self.get_message(msg_uuid)
        if not msg:
            return []
            
        ctx = msg['context_id']
        query = "SELECT * FROM messages WHERE context_id = ? ORDER BY created_at ASC;"
        return self.db.fetch_all(query, (ctx,))

    def run_garbage_collection(self):
        """Revert 'in_progress' messages to 'new' if agent is offline > 15 mins."""
        try:
            # 1. Update status to idle if > 5 mins, offline if > 15 mins
            idle_query = "UPDATE presence SET status = 'idle' WHERE status = 'online' AND datetime(last_active) < datetime('now', '-5 minutes');"
            offline_query = "UPDATE presence SET status = 'offline' WHERE status != 'offline' AND datetime(last_active) < datetime('now', '-15 minutes');"
            
            self.db.execute(idle_query)
            self.db.execute(offline_query)
            
            # 2. Revert in_progress messages for offline agents
            revert_query = """
            UPDATE messages 
            SET status = 'new', acked_at = NULL 
            WHERE status = 'in_progress' 
            AND uuid IN (
                SELECT working_on FROM presence WHERE status = 'offline' AND working_on IS NOT NULL
            );
            """
            clear_presence = """
            UPDATE presence SET working_on = NULL, active_files = NULL WHERE status = 'offline' AND working_on IS NOT NULL;
            """
            
            self.db.execute(revert_query)
            self.db.execute(clear_presence)
                
        except Exception as e:
            logger.error(f"Error running garbage collection: {e}")
