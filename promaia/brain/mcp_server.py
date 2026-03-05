"""
Brain MCP Server — 7 tools for zBrain.

Exposes Claude's persistent memory system as MCP tools over stdio.
Claude calls these tools to get briefings, capture thoughts, search memories,
manage project context, and track actions.

Tools:
    briefing       — stale projects + pending actions + recent heartbeat activity
    capture        — store memory with embedding, auto-extract actions
    search         — semantic vector search across brain.memories
    recall         — recent memories filtered by domain or time range
    context        — read a domain's directive and current state
    update_context — write/upsert a domain's context
    actions        — list or mark-done brain actions

Usage:
    python -m promaia.brain.mcp_server
"""
import asyncio
import json
import logging
import os
import sys
import uuid
from typing import Any, Dict, List, Optional

import numpy as np
import psycopg2.extras
from pgvector.psycopg2 import register_vector

try:
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp.types import Tool, TextContent
except ImportError:
    print("ERROR: mcp package not installed. Install with: pip install 'mcp>=1.26.0'", file=sys.stderr)
    sys.exit(1)

from promaia.storage.postgres_db import get_postgres_db
from promaia.storage.vector_db import VectorDBManager
from promaia.brain import engine
from promaia.brain.extraction import extract_actions

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Server + session state
# ---------------------------------------------------------------------------
server = Server("zbrain-brain")
SESSION_ID = str(uuid.uuid4())

# Lazy-initialised singletons so the server can start without a live DB
_db = None
_vector_manager = None


def get_db():
    global _db
    if _db is None:
        _db = get_postgres_db()
    return _db


def get_vector_mgr():
    global _vector_manager
    if _vector_manager is None:
        _vector_manager = VectorDBManager()
    return _vector_manager


# ---------------------------------------------------------------------------
# Tool registry
# ---------------------------------------------------------------------------

@server.list_tools()
async def list_tools() -> list[Tool]:
    """Enumerate all 7 brain tools."""
    return [
        Tool(
            name="briefing",
            description=(
                "Return a session briefing: stale projects, pending actions, "
                "and recent heartbeat activity from the last 24 hours. "
                "Call this at the start of every session."
            ),
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        Tool(
            name="capture",
            description=(
                "Store a thought, note, or observation as a persistent memory. "
                "Automatically extracts any actionable items and generates a "
                "semantic embedding for future search."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "content": {
                        "type": "string",
                        "description": "The text to store as a memory."
                    },
                    "domain": {
                        "type": "string",
                        "description": "Optional domain name (e.g. 'promaia', 'heatpup')."
                    }
                },
                "required": ["content"]
            }
        ),
        Tool(
            name="search",
            description=(
                "Semantic vector search across all brain memories. "
                "Returns the most relevant memories ranked by cosine similarity."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Natural language search query."
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum results to return (default 10).",
                        "default": 10
                    }
                },
                "required": ["query"]
            }
        ),
        Tool(
            name="recall",
            description=(
                "Retrieve recent memories, optionally filtered by domain and time range."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "domain": {
                        "type": "string",
                        "description": "Filter by domain name (optional)."
                    },
                    "days": {
                        "type": "integer",
                        "description": "How many days back to look (default 30).",
                        "default": 30
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum results (default 20).",
                        "default": 20
                    }
                },
                "required": []
            }
        ),
        Tool(
            name="context",
            description=(
                "Read the standing directive and current state for a domain. "
                "Use this to understand what's happening in a specific project."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "domain": {
                        "type": "string",
                        "description": "Domain name to look up (e.g. 'promaia')."
                    }
                },
                "required": ["domain"]
            }
        ),
        Tool(
            name="update_context",
            description=(
                "Write or update the standing directive and current state for a domain. "
                "Creates the domain and context if they don't exist yet."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "domain": {
                        "type": "string",
                        "description": "Domain name to update."
                    },
                    "directive": {
                        "type": "string",
                        "description": "Standing directive for this domain (optional)."
                    },
                    "current_state": {
                        "type": "string",
                        "description": "Current status or state of this domain (optional)."
                    },
                    "priority": {
                        "type": "integer",
                        "description": "Priority 1-10 (1=highest). Default 5 (optional)."
                    }
                },
                "required": ["domain"]
            }
        ),
        Tool(
            name="actions",
            description=(
                "List pending actions, optionally filtered by domain. "
                "Pass mark_done with an action ID to mark it complete."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "status": {
                        "type": "string",
                        "description": "Filter by status: 'pending', 'done', 'stale' (default 'pending').",
                        "default": "pending"
                    },
                    "domain": {
                        "type": "string",
                        "description": "Filter by domain name (optional)."
                    },
                    "mark_done": {
                        "type": "integer",
                        "description": "Action ID to mark as completed (optional)."
                    }
                },
                "required": []
            }
        ),
    ]


# ---------------------------------------------------------------------------
# Tool dispatcher
# ---------------------------------------------------------------------------

@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Dispatch tool calls to handler functions."""
    logger.info(f"Brain tool call: {name}")
    try:
        if name == "briefing":
            return await _handle_briefing(arguments)
        elif name == "capture":
            return await _handle_capture(arguments)
        elif name == "search":
            return await _handle_search(arguments)
        elif name == "recall":
            return await _handle_recall(arguments)
        elif name == "context":
            return await _handle_context(arguments)
        elif name == "update_context":
            return await _handle_update_context(arguments)
        elif name == "actions":
            return await _handle_actions(arguments)
        else:
            return [TextContent(type="text", text=f"Unknown tool: {name}")]
    except Exception as e:
        logger.error(f"Tool {name} failed: {e}", exc_info=True)
        return [TextContent(type="text", text=f"Error in {name}: {str(e)}")]


# ---------------------------------------------------------------------------
# Tool handlers
# ---------------------------------------------------------------------------

async def _handle_briefing(args: dict) -> list[TextContent]:
    """Return stale projects, pending actions, and recent heartbeat activity."""
    db = get_db()
    lines = ["# Session Briefing\n"]

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
            lines.append("## Stale Projects")
            for row in stale:
                days_stale = _days_ago(row.get('last_updated'))
                lines.append(
                    f"- **{row['name']}** (priority {row['priority']}, "
                    f"{days_stale:.0f} days stale): {row.get('current_state') or row.get('directive') or '—'}"
                )
            lines.append("")
        else:
            lines.append("## Stale Projects\nNone — all projects up to date.\n")
    except Exception as e:
        logger.warning(f"briefing stale query failed: {e}")
        lines.append("## Stale Projects\n(query error)\n")

    # --- Pending actions ---
    try:
        pending = db.fetch_all(
            """
            SELECT a.id, a.description, d.name AS domain_name,
                   a.extracted_at
            FROM brain.actions a
            LEFT JOIN brain.domains d ON d.id = a.domain_id
            WHERE a.status = 'pending'
            ORDER BY a.extracted_at DESC
            LIMIT 10
            """
        )
        if pending:
            lines.append("## Pending Actions")
            for row in pending:
                domain_label = f" [{row['domain_name']}]" if row.get('domain_name') else ""
                lines.append(f"- [{row['id']}]{domain_label} {row['description']}")
            lines.append("")
        else:
            lines.append("## Pending Actions\nNone pending.\n")
    except Exception as e:
        logger.warning(f"briefing pending actions query failed: {e}")
        lines.append("## Pending Actions\n(query error)\n")

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
            lines.append("## Heartbeat Activity (last 24h)")
            for ev in heartbeat_events:
                ts = _fmt_ts(ev.get('created_at'))
                lines.append(f"- {ts} {ev['type']}")
            lines.append("")
        else:
            lines.append("## Heartbeat Activity (last 24h)\nNo heartbeat events.\n")
    except Exception as e:
        logger.warning(f"briefing heartbeat query failed: {e}")
        lines.append("## Heartbeat Activity (last 24h)\n(query error)\n")

    # Log briefing event (idempotent per session day)
    try:
        today = _today_str()
        existing = db.fetch_one(
            """
            SELECT id FROM brain.events
            WHERE type = 'briefing'
              AND session_id = %s
              AND created_at::date = %s::date
            LIMIT 1
            """,
            (SESSION_ID, today),
        )
        if not existing:
            db.execute(
                """
                INSERT INTO brain.events (type, payload, source, session_id)
                VALUES ('briefing', %s::jsonb, 'session', %s)
                """,
                (json.dumps({"session_id": SESSION_ID}), SESSION_ID),
            )
    except Exception as e:
        logger.warning(f"Could not log briefing event: {e}")

    return [TextContent(type="text", text="\n".join(lines))]


async def _handle_capture(args: dict) -> list[TextContent]:
    """Insert memory, generate embedding, extract actions."""
    db = get_db()
    content = args.get("content", "").strip()
    if not content:
        return [TextContent(type="text", text="Error: content is required.")]

    domain_name = args.get("domain")

    # Insert memory row (without embedding first)
    try:
        memory_id = db.insert_returning(
            """
            INSERT INTO brain.memories (content, domain, source, source_id)
            VALUES (%s, %s, 'session', %s)
            RETURNING id
            """,
            (content, domain_name, SESSION_ID),
        )
    except Exception as e:
        logger.error(f"capture insert failed: {e}")
        return [TextContent(type="text", text=f"Error storing memory: {e}")]

    # Generate embedding and update row
    try:
        vector_mgr = get_vector_mgr()
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
        # Non-fatal — memory is stored, just without embedding

    # Extract actions
    action_count = 0
    try:
        extraction_result = extract_actions(content)
        if extraction_result.has_actions:
            # Resolve domain_id if domain provided
            domain_id = _get_or_create_domain_id(db, domain_name) if domain_name else None

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

    # Log capture event
    try:
        db.execute(
            """
            INSERT INTO brain.events (type, payload, source, session_id)
            VALUES ('capture', %s::jsonb, 'session', %s)
            """,
            (json.dumps({"memory_id": memory_id, "action_count": action_count}), SESSION_ID),
        )
    except Exception as e:
        logger.warning(f"Could not log capture event: {e}")

    if action_count > 0:
        return [TextContent(type="text", text=f"Captured. Extracted {action_count} action(s).")]
    return [TextContent(type="text", text="Captured.")]


async def _handle_search(args: dict) -> list[TextContent]:
    """Semantic vector search over brain.memories."""
    db = get_db()
    query = args.get("query", "").strip()
    if not query:
        return [TextContent(type="text", text="Error: query is required.")]

    limit = int(args.get("limit", 10))

    try:
        vector_mgr = get_vector_mgr()
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
                rows = [dict(r) for r in cur.fetchall()]

        if not rows:
            return [TextContent(type="text", text="No memories found matching your query.")]

        lines = [f"# Search Results for: {query}\n"]
        for i, row in enumerate(rows, 1):
            similarity = 1 - float(row['distance'])
            domain_label = f" [{row['domain']}]" if row.get('domain') else ""
            ts = _fmt_ts(row.get('created_at'))
            content_preview = row['content'][:200] + ("..." if len(row['content']) > 200 else "")
            lines.append(f"**{i}.**{domain_label} (similarity: {similarity:.2f}, {ts})")
            lines.append(f"{content_preview}\n")

        return [TextContent(type="text", text="\n".join(lines))]

    except Exception as e:
        logger.error(f"search failed: {e}", exc_info=True)
        return [TextContent(type="text", text=f"Search error: {e}")]


async def _handle_recall(args: dict) -> list[TextContent]:
    """Return recent memories filtered by domain and/or time range."""
    db = get_db()
    domain_name = args.get("domain")
    days = int(args.get("days", 30))
    limit = int(args.get("limit", 20))

    try:
        query = """
            SELECT id, content, domain, created_at
            FROM brain.memories
            WHERE created_at > NOW() - %s * INTERVAL '1 day'
        """
        params: list = [days]

        if domain_name:
            query += " AND domain = %s"
            params.append(domain_name)

        query += " ORDER BY created_at DESC LIMIT %s"
        params.append(limit)

        rows = db.fetch_all(query, tuple(params))

        if not rows:
            msg = f"No memories found"
            if domain_name:
                msg += f" in domain '{domain_name}'"
            msg += f" from the last {days} days."
            return [TextContent(type="text", text=msg)]

        lines = [f"# Recent Memories (last {days} days)\n"]
        for row in rows:
            domain_label = f" [{row['domain']}]" if row.get('domain') else ""
            ts = _fmt_ts(row.get('created_at'))
            content_preview = row['content'][:300] + ("..." if len(row['content']) > 300 else "")
            lines.append(f"**[{ts}]**{domain_label} {content_preview}\n")

        return [TextContent(type="text", text="\n".join(lines))]

    except Exception as e:
        logger.error(f"recall failed: {e}", exc_info=True)
        return [TextContent(type="text", text=f"Recall error: {e}")]


async def _handle_context(args: dict) -> list[TextContent]:
    """Read directive and current state for a domain."""
    db = get_db()
    domain_name = args.get("domain", "").strip()
    if not domain_name:
        return [TextContent(type="text", text="Error: domain is required.")]

    try:
        row = db.fetch_one(
            """
            SELECT c.directive, c.current_state, c.last_updated,
                   c.priority, c.stale_threshold_days, d.name AS domain_name
            FROM brain.contexts c
            JOIN brain.domains d ON d.id = c.domain_id
            WHERE d.name = %s
            ORDER BY c.last_updated DESC
            LIMIT 1
            """,
            (domain_name,),
        )

        if not row:
            return [TextContent(type="text", text=f"No context found for domain: {domain_name}")]

        days_stale = _days_ago(row.get('last_updated'))
        stale_note = ""
        if days_stale > row.get('stale_threshold_days', 7):
            stale_note = f" ** STALE ({days_stale:.0f} days since update) **"

        lines = [
            f"# Context: {row['domain_name']}{stale_note}\n",
            f"**Priority:** {row['priority']}",
            f"**Last updated:** {_fmt_ts(row.get('last_updated'))}",
            f"**Directive:** {row.get('directive') or '(none)'}",
            f"**Current state:** {row.get('current_state') or '(none)'}",
        ]
        return [TextContent(type="text", text="\n".join(lines))]

    except Exception as e:
        logger.error(f"context query failed: {e}", exc_info=True)
        return [TextContent(type="text", text=f"Context error: {e}")]


async def _handle_update_context(args: dict) -> list[TextContent]:
    """Upsert directive and current state for a domain."""
    db = get_db()
    domain_name = args.get("domain", "").strip()
    if not domain_name:
        return [TextContent(type="text", text="Error: domain is required.")]

    directive = args.get("directive")
    current_state = args.get("current_state")
    priority = args.get("priority")

    if directive is None and current_state is None and priority is None:
        return [TextContent(type="text", text="Nothing to update — provide directive, current_state, or priority.")]

    try:
        # Get or create domain
        domain_id = _get_or_create_domain_id(db, domain_name)

        # Check if context row exists
        existing = db.fetch_one(
            "SELECT id FROM brain.contexts WHERE domain_id = %s",
            (domain_id,),
        )

        if existing:
            # Build partial update
            set_parts = ["last_updated = NOW()"]
            params: list = []
            if directive is not None:
                set_parts.append("directive = %s")
                params.append(directive)
            if current_state is not None:
                set_parts.append("current_state = %s")
                params.append(current_state)
            if priority is not None:
                set_parts.append("priority = %s")
                params.append(int(priority))

            params.append(domain_id)
            db.execute(
                f"UPDATE brain.contexts SET {', '.join(set_parts)} WHERE domain_id = %s",
                tuple(params),
            )
        else:
            # Insert new context
            db.execute(
                """
                INSERT INTO brain.contexts (domain_id, directive, current_state, priority)
                VALUES (%s, %s, %s, %s)
                """,
                (domain_id, directive, current_state, int(priority) if priority else 5),
            )

        # Log event
        try:
            db.execute(
                """
                INSERT INTO brain.events (type, payload, source, session_id)
                VALUES ('context_update', %s::jsonb, 'session', %s)
                """,
                (json.dumps({"domain": domain_name}), SESSION_ID),
            )
        except Exception as e:
            logger.warning(f"Could not log context_update event: {e}")

        return [TextContent(type="text", text=f"Context updated for: {domain_name}")]

    except Exception as e:
        logger.error(f"update_context failed: {e}", exc_info=True)
        return [TextContent(type="text", text=f"Update context error: {e}")]


async def _handle_actions(args: dict) -> list[TextContent]:
    """List actions or mark one done."""
    db = get_db()
    mark_done = args.get("mark_done")

    # Mark done path
    if mark_done is not None:
        try:
            rowcount = db.execute(
                """
                UPDATE brain.actions
                SET status = 'done', completed_at = NOW()
                WHERE id = %s
                """,
                (int(mark_done),),
            )
            if rowcount:
                return [TextContent(type="text", text=f"Action {mark_done} marked done.")]
            else:
                return [TextContent(type="text", text=f"Action {mark_done} not found.")]
        except Exception as e:
            logger.error(f"mark_done failed: {e}", exc_info=True)
            return [TextContent(type="text", text=f"Error marking action done: {e}")]

    # List path
    status = args.get("status", "pending")
    domain_name = args.get("domain")

    try:
        query = """
            SELECT a.id, a.description, a.status, a.extracted_at,
                   d.name AS domain_name
            FROM brain.actions a
            LEFT JOIN brain.domains d ON d.id = a.domain_id
            WHERE a.status = %s
        """
        params: list = [status]

        if domain_name:
            query += " AND d.name = %s"
            params.append(domain_name)

        query += " ORDER BY a.extracted_at DESC LIMIT 50"

        rows = db.fetch_all(query, tuple(params))

        if not rows:
            msg = f"No {status} actions"
            if domain_name:
                msg += f" in domain '{domain_name}'"
            msg += "."
            return [TextContent(type="text", text=msg)]

        lines = [f"# {status.title()} Actions\n"]
        for row in rows:
            domain_label = f" [{row['domain_name']}]" if row.get('domain_name') else ""
            ts = _fmt_ts(row.get('extracted_at'))
            lines.append(f"- **[{row['id']}]**{domain_label} {row['description']} _(captured {ts})_")

        lines.append(f"\nTotal: {len(rows)}")
        return [TextContent(type="text", text="\n".join(lines))]

    except Exception as e:
        logger.error(f"actions query failed: {e}", exc_info=True)
        return [TextContent(type="text", text=f"Actions error: {e}")]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_or_create_domain_id(db, domain_name: str) -> int:
    """Return the domain.id for domain_name, creating it if absent."""
    existing = db.fetch_one(
        "SELECT id FROM brain.domains WHERE name = %s",
        (domain_name,),
    )
    if existing:
        return existing['id']

    return db.insert_returning(
        "INSERT INTO brain.domains (name) VALUES (%s) RETURNING id",
        (domain_name,),
    )


def _days_ago(ts) -> float:
    """Return number of days between ts and now. Returns 0 if ts is None."""
    if ts is None:
        return 0.0
    from datetime import datetime, timezone
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
    from datetime import datetime, timezone
    if isinstance(ts, str):
        try:
            ts = datetime.fromisoformat(ts)
        except ValueError:
            return str(ts)
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return ts.strftime("%Y-%m-%d %H:%M UTC")


def _today_str() -> str:
    """Return today's date as YYYY-MM-DD."""
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

async def main():
    """Run the Brain MCP server over stdio."""
    logging.basicConfig(level=logging.INFO, stream=sys.stderr)
    logger.info(f"Starting zBrain MCP server (session: {SESSION_ID[:8]}...)")
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Brain MCP server stopped")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)
