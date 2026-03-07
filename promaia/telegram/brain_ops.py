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
from datetime import datetime, timezone
from typing import Optional

import numpy as np
import psycopg2.extras
from pgvector.psycopg2 import register_vector

from promaia.storage.postgres_db import get_postgres_db
from promaia.storage.vector_db import VectorDBManager
from promaia.brain.extraction import extract_actions

logger = logging.getLogger(__name__)

# Lazy-initialised singletons
_db = None
_vector_manager = None


def _get_db():
    global _db
    if _db is None:
        _db = get_postgres_db()
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
        "SELECT id FROM brain.domains WHERE name = %s",
        (domain_name,),
    )
    if existing:
        return existing["id"]
    return db.insert_returning(
        "INSERT INTO brain.domains (name) VALUES (%s) RETURNING id",
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
                FROM brain.contexts c
                JOIN brain.domains d ON d.id = c.domain_id
                WHERE NOW() - c.last_updated > c.stale_threshold_days * INTERVAL '1 day'
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
                FROM brain.actions a
                LEFT JOIN brain.domains d ON d.id = a.domain_id
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
                FROM brain.events
                WHERE source = 'heartbeat'
                  AND created_at > NOW() - INTERVAL '24 hours'
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
                INSERT INTO brain.memories (content, domain, source, source_id)
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
            embedding_array = np.array(embedding)
            with db.get_connection() as conn:
                register_vector(conn)
                with conn.cursor() as cur:
                    cur.execute(
                        "UPDATE brain.memories SET embedding = %s WHERE id = %s",
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
                        INSERT INTO brain.actions (memory_id, domain_id, description)
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
    """Semantic vector search over brain.memories. Returns formatted results."""
    if not query or not query.strip():
        return "Error: query is required."

    def _sync():
        db = _get_db()
        pg_rows = []
        try:
            vector_mgr = _get_vector_mgr()
            query_embedding = vector_mgr.generate_embedding(query)
            query_array = np.array(query_embedding)

            with db.get_connection() as conn:
                register_vector(conn)
                with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                    cur.execute(
                        """
                        SELECT id, content, domain, created_at,
                               embedding <=> %s::vector AS distance
                        FROM brain.memories
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
                FROM brain.actions a
                LEFT JOIN brain.domains d ON d.id = a.domain_id
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
                FROM brain.contexts c
                JOIN brain.domains d ON d.id = c.domain_id
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
