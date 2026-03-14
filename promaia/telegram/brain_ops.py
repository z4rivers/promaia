"""
Brain operations for Telegram bot.

Plain async functions that call Postgres directly (NOT MCP protocol).
Each function returns a string suitable for sending as a Telegram message.
All synchronous DB calls are wrapped in asyncio.to_thread() to avoid
blocking the event loop.
"""
import asyncio
import json
import logging
import random
import uuid
from datetime import datetime, timezone
from typing import Optional

import numpy as np
import psycopg2.extras

from promaia.storage.db_factory import get_db
from promaia.storage.vector_db import VectorDBManager
from promaia.brain.extraction import extract_actions

logger = logging.getLogger(__name__)

# Lazy-initialised singletons
_db = None
_vector_manager = None


def _get_db():
    global _db
    if _db is None:
        _db = get_db()
    return _db


def _get_vector_mgr():
    global _vector_manager
    if _vector_manager is None:
        _vector_manager = VectorDBManager()
    return _vector_manager


# ---------------------------------------------------------------------------
# Helpers (same as mcp_server.py)
# ---------------------------------------------------------------------------

def _days_ago(ts) -> float:
    """Return number of days between ts and now. Returns 0 if ts is None."""
    if ts is None:
        return 0.0
    now = datetime.now(timezone.utc)
    if isinstance(ts, str):
        try:
            ts = datetime.fromisoformat(ts)
        except ValueError:
            return 0.0
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return (now - ts).total_seconds() / 86400.0


def _fmt_ts(ts) -> str:
    """Format a datetime or None as a short human-readable string."""
    if ts is None:
        return "unknown"
    if isinstance(ts, str):
        try:
            ts = datetime.fromisoformat(ts)
        except ValueError:
            return str(ts)
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return ts.strftime("%Y-%m-%d %H:%M UTC")


def _get_or_create_domain_id(db, domain_name: str) -> int:
    """Return the domain.id for domain_name, creating it if absent."""
    existing = db.fetch_one(
        "SELECT id FROM domains WHERE name = %s",
        (domain_name,),
    )
    if existing:
        return existing["id"]
    return db.insert_returning(
        "INSERT INTO domains (name) VALUES (%s) RETURNING id",
        (domain_name,),
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def get_briefing() -> str:
    """Return stale projects, pending actions, and recent heartbeat activity."""

    def _sync():
        db = _get_db()
        lines = ["Session Briefing\n"]

        # --- Stale projects ---
        try:
            stale = db.fetch_all(
                """
                SELECT d.name, c.directive, c.current_state, c.last_updated,
                       c.stale_threshold_days, c.priority
                FROM contexts c
                JOIN domains d ON d.id = c.domain_id
                WHERE julianday('now') - julianday(c.last_updated) > c.stale_threshold_days
                ORDER BY c.priority ASC, c.last_updated ASC
                LIMIT 10
                """
            )
            if stale:
                lines.append("Stale Projects")
                for row in stale:
                    days = _days_ago(row.get("last_updated"))
                    state = row.get("current_state") or row.get("directive") or "--"
                    lines.append(
                        f"  {row['name']} (P{row['priority']}, {days:.0f}d stale): {state}"
                    )
                lines.append("")
            else:
                lines.append("Stale Projects: None -- all up to date.\n")
        except Exception as e:
            logger.warning(f"briefing stale query failed: {e}")
            lines.append("Stale Projects: (query error)\n")

        # --- Pending actions ---
        try:
            pending = db.fetch_all(
                """
                SELECT a.id, a.description, d.name AS domain_name, a.extracted_at
                FROM actions a
                LEFT JOIN domains d ON d.id = a.domain_id
                WHERE a.status = 'pending'
                ORDER BY a.extracted_at DESC
                LIMIT 10
                """
            )
            if pending:
                lines.append("Pending Actions")
                for row in pending:
                    domain_label = f" [{row['domain_name']}]" if row.get("domain_name") else ""
                    lines.append(f"  [{row['id']}]{domain_label} {row['description']}")
                lines.append("")
            else:
                lines.append("Pending Actions: None.\n")
        except Exception as e:
            logger.warning(f"briefing pending actions query failed: {e}")
            lines.append("Pending Actions: (query error)\n")

        # --- Recent heartbeat activity ---
        try:
            heartbeat_events = db.fetch_all(
                """
                SELECT type, payload, created_at
                FROM events
                WHERE source = 'heartbeat'
                  AND created_at > datetime('now', '-24 hours')
                ORDER BY created_at DESC
                LIMIT 5
                """
            )
            if heartbeat_events:
                lines.append("Heartbeat Activity (last 24h)")
                for ev in heartbeat_events:
                    ts = _fmt_ts(ev.get("created_at"))
                    lines.append(f"  {ts} {ev['type']}")
                lines.append("")
            else:
                lines.append("Heartbeat Activity (last 24h): None.\n")
        except Exception as e:
            logger.warning(f"briefing heartbeat query failed: {e}")
            lines.append("Heartbeat Activity: (query error)\n")

        return "\n".join(lines)

    return await asyncio.to_thread(_sync)


async def capture_memory(content: str, domain: Optional[str] = None) -> str:
    """Insert memory, generate embedding, extract actions. Returns confirmation string."""
    if not content or not content.strip():
        return "Error: content is required."

    def _sync():
        db = _get_db()

        # Insert memory row
        try:
            memory_id = db.insert_returning(
                """
                INSERT INTO memories (content, domain, source, source_id)
                VALUES (%s, %s, 'telegram', 'telegram')
                RETURNING id
                """,
                (content, domain),
            )
        except Exception as e:
            logger.error(f"capture insert failed: {e}")
            return f"Error storing memory: {e}"

        # Generate embedding and update row
        try:
            vector_mgr = _get_vector_mgr()
            embedding = vector_mgr.generate_embedding(content)
            embedding_array = json.dumps(embedding)
            db.execute(
                        "UPDATE memories SET embedding = %s WHERE id = %s",
                        (embedding_array, memory_id),
                    )
        except Exception as e:
            logger.warning(f"Embedding generation failed for memory {memory_id}: {e}")

        # Extract actions
        action_count = 0
        try:
            extraction_result = extract_actions(content)
            if extraction_result.has_actions:
                domain_id = _get_or_create_domain_id(db, domain) if domain else None
                for action in extraction_result.actions:
                    db.execute(
                        """
                        INSERT INTO actions (memory_id, domain_id, description)
                        VALUES (%s, %s, %s)
                        """,
                        (memory_id, domain_id, action.description),
                    )
                action_count = len(extraction_result.actions)
        except Exception as e:
            logger.warning(f"Action extraction/insert failed: {e}")

        if action_count > 0:
            action_confirmations = [
                f"Got it -- I pulled out {action_count} thing{'s' if action_count > 1 else ''} to track from that.",
                f"Stored. Found {action_count} action{'s' if action_count > 1 else ''} in there too.",
                f"Noted, and I spotted {action_count} to-do{'s' if action_count > 1 else ''} in that.",
                f"On it. {action_count} action{'s' if action_count > 1 else ''} queued up.",
            ]
            return random.choice(action_confirmations)

        simple_confirmations = [
            "Got it.",
            "Noted.",
            "Stored that away.",
            "On it.",
            "Tucked away.",
            "Logged.",
            "Heard.",
            "Saved.",
        ]
        return random.choice(simple_confirmations)

    return await asyncio.to_thread(_sync)


async def search_brain(query: str, limit: int = 5) -> str:
    """Semantic vector search over memories. Returns formatted results."""
    if not query or not query.strip():
        return "Error: query is required."

    def _sync():
        db = _get_db()
        pg_rows = []
        try:
            vector_mgr = _get_vector_mgr()
            query_embedding = vector_mgr.generate_embedding(query, task_type="RETRIEVAL_QUERY")
            query_array = np.array(query_embedding)

            with db.get_connection() as conn:
                with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                    cur.execute(
                        """
                        SELECT id, content, domain, created_at,
                               embedding <=> %s::vector AS distance
                        FROM memories
                        WHERE embedding IS NOT NULL
                        ORDER BY distance ASC
                        LIMIT %s
                        """,
                        (query_array, limit),
                    )
                    pg_rows = [dict(r) for r in cur.fetchall()]
        except Exception as e:
            logger.error(f"pgvector search failed: {e}", exc_info=True)

        if not pg_rows:
            return "No results found."

        lines = [f"Search: {query}\n"]
        for i, row in enumerate(pg_rows, 1):
            similarity = 1 - float(row["distance"])
            domain_label = f" [{row['domain']}]" if row.get("domain") else ""
            ts = _fmt_ts(row.get("created_at"))
            preview = row["content"][:200] + ("..." if len(row["content"]) > 200 else "")
            lines.append(f"{i}.{domain_label} (sim: {similarity:.2f}, {ts})")
            lines.append(f"   {preview}\n")
        return "\n".join(lines)

    return await asyncio.to_thread(_sync)


async def get_actions(status: str = "pending") -> str:
    """List actions by status. Returns formatted list."""

    def _sync():
        db = _get_db()
        try:
            rows = db.fetch_all(
                """
                SELECT a.id, a.description, a.status, a.extracted_at,
                       d.name AS domain_name
                FROM actions a
                LEFT JOIN domains d ON d.id = a.domain_id
                WHERE a.status = %s
                ORDER BY a.extracted_at DESC
                LIMIT 50
                """,
                (status,),
            )
            if not rows:
                return f"No {status} actions."

            lines = [f"{status.title()} Actions\n"]
            for row in rows:
                domain_label = f" [{row['domain_name']}]" if row.get("domain_name") else ""
                ts = _fmt_ts(row.get("extracted_at"))
                lines.append(f"  [{row['id']}]{domain_label} {row['description']} ({ts})")
            lines.append(f"\nTotal: {len(rows)}")
            return "\n".join(lines)
        except Exception as e:
            logger.error(f"actions query failed: {e}", exc_info=True)
            return f"Actions error: {e}"

    return await asyncio.to_thread(_sync)


async def get_projects() -> str:
    """List all projects with priority, staleness, and current state."""

    def _sync():
        db = _get_db()
        try:
            rows = db.fetch_all(
                """
                SELECT d.name, c.directive, c.current_state, c.last_updated,
                       c.stale_threshold_days, c.priority
                FROM contexts c
                JOIN domains d ON d.id = c.domain_id
                ORDER BY c.priority ASC, d.name ASC
                """
            )
            if not rows:
                return "No projects found."

            lines = ["Projects\n"]
            for row in rows:
                days = _days_ago(row.get("last_updated"))
                stale_marker = " [STALE]" if days > (row.get("stale_threshold_days") or 14) else ""
                state = row.get("current_state") or row.get("directive") or "--"
                lines.append(
                    f"  P{row['priority']} {row['name']}{stale_marker} "
                    f"({days:.0f}d ago): {state}"
                )
            return "\n".join(lines)
        except Exception as e:
            logger.error(f"projects query failed: {e}", exc_info=True)
            return f"Projects error: {e}"

    return await asyncio.to_thread(_sync)


# ---------------------------------------------------------------------------
# Conversation CRUD
# ---------------------------------------------------------------------------

async def save_conversation_message(
    chat_id: int,
    session_id: str,
    role: str,
    content: str,
    impact_score: float = 0.0,
) -> int:
    """Insert a message into conversations and update session counters.

    Returns the conversation message id.
    """

    def _sync():
        db = _get_db()
        msg_id = db.insert_returning(
            """
            INSERT INTO conversations
                (chat_id, session_id, role, content, impact_score)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id
            """,
            (chat_id, session_id, role, content, impact_score),
        )
        # Update session counters
        db.execute(
            """
            UPDATE conversation_sessions
            SET message_count = message_count + 1,
                last_message_at = datetime('now')
            WHERE session_id = %s
            """,
            (session_id,),
        )
        return msg_id

    return await asyncio.to_thread(_sync)


async def get_conversation_history(chat_id: int, limit: int = 10) -> list[dict]:
    """Fetch last N messages for a chat in chronological order.

    Returns list of dicts with keys: role, content, created_at.
    """

    def _sync():
        db = _get_db()
        rows = db.fetch_all(
            """
            SELECT role, content, created_at
            FROM conversations
            WHERE chat_id = %s
            ORDER BY created_at DESC
            LIMIT %s
            """,
            (chat_id, limit),
        )
        # Reverse to chronological (ASC) order
        rows.reverse()
        return rows

    return await asyncio.to_thread(_sync)


async def get_or_create_session(chat_id: int, gap_minutes: int = 30) -> str:
    """Return the current session_id, creating a new one if needed.

    A session is reused if its last_message_at is within gap_minutes of now
    AND it has not been synthesized. Otherwise a new session is created.
    """

    def _sync():
        db = _get_db()
        row = db.fetch_one(
            """
            SELECT session_id, last_message_at, synthesized
            FROM conversation_sessions
            WHERE chat_id = %s
            ORDER BY started_at DESC
            LIMIT 1
            """,
            (chat_id,),
        )
        if row and not row["synthesized"]:
            last_msg = row["last_message_at"]
            if isinstance(last_msg, str):
                try:
                    last_msg = datetime.fromisoformat(last_msg)
                except ValueError:
                    last_msg = None
            if last_msg is not None:
                if last_msg.tzinfo is None:
                    last_msg = last_msg.replace(tzinfo=timezone.utc)
                now = datetime.now(timezone.utc)
                gap = (now - last_msg).total_seconds() / 60.0
                if gap <= gap_minutes:
                    return row["session_id"]

        # Create a new session
        new_session_id = str(uuid.uuid4())
        db.execute(
            """
            INSERT INTO conversation_sessions (chat_id, session_id)
            VALUES (%s, %s)
            """,
            (chat_id, new_session_id),
        )
        return new_session_id

    return await asyncio.to_thread(_sync)


async def update_session_synthesized(session_id: str, memory_id: int) -> None:
    """Mark a session as synthesized with the resulting memory id."""

    def _sync():
        db = _get_db()
        db.execute(
            """
            UPDATE conversation_sessions
            SET synthesized = TRUE,
                synthesized_at = datetime('now'),
                synthesis_memory_id = %s
            WHERE session_id = %s
            """,
            (memory_id, session_id),
        )

    await asyncio.to_thread(_sync)


async def get_session_messages(session_id: str) -> list[dict]:
    """Fetch ALL messages for a session in chronological order.

    Returns list of dicts with keys: role, content, impact_score, created_at.
    """

    def _sync():
        db = _get_db()
        return db.fetch_all(
            """
            SELECT role, content, impact_score, created_at
            FROM conversations
            WHERE session_id = %s
            ORDER BY created_at ASC
            """,
            (session_id,),
        )

    return await asyncio.to_thread(_sync)


async def promote_message_to_memory(
    conversation_id: int,
    content: str,
    domain: str = None,
) -> int:
    """Promote a conversation message to memories.

    Inserts the content as a permanent memory with source='telegram-conversation',
    generates an embedding, and marks the conversation row as promoted.
    Returns the new memory_id.
    """

    def _sync():
        db = _get_db()

        # Insert into memories
        memory_id = db.insert_returning(
            """
            INSERT INTO memories (content, domain, source, source_id)
            VALUES (%s, %s, 'telegram-conversation', 'promoted')
            RETURNING id
            """,
            (content, domain),
        )

        # Generate embedding
        try:
            vector_mgr = _get_vector_mgr()
            embedding = vector_mgr.generate_embedding(content)
            embedding_array = json.dumps(embedding)
            db.execute(
                        "UPDATE memories SET embedding = %s WHERE id = %s",
                        (embedding_array, memory_id),
                    )
        except Exception as e:
            logger.warning(f"Embedding generation failed for promoted memory {memory_id}: {e}")

        # Mark conversation message as promoted
        db.execute(
            "UPDATE conversations SET promoted = 1 WHERE id = %s",
            (conversation_id,),
        )

        return memory_id

    return await asyncio.to_thread(_sync)
