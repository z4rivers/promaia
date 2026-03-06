"""
Brain MCP Server — 15 tools for zBrain.

Exposes Claude's persistent memory system as MCP tools over stdio.
Claude calls these tools to get briefings, capture thoughts, search memories,
manage project context, track actions, maintain a personal profile,
manage the onboarding flow, run data ingestion channels, and perform
cognitive retrieval via MuninnDB.

Tools:
    briefing        — stale projects + pending actions + recent heartbeat activity
    capture         — store memory with embedding, auto-extract actions (dual-writes to MuninnDB)
    search          — semantic vector search + MuninnDB ACTIVATE (parallel trial)
    recall          — recent memories filtered by domain or time range
    context         — read a domain's directive and current state
    update_context  — write/upsert a domain's context
    actions         — list or mark-done brain actions
    profile         — read personal profile (all or by category)
    update_profile  — set a profile field with value, confidence, and source
    onboard         — manage the onboarding flow (start/status/channel_update/complete)
    pc_scan         — scan local git repos, files, and apps for profile data
    gmail_scan      — scan Gmail inbox for contacts, patterns, and topics
    gmail_query     — search stored Gmail content by sender, subject, or full-text
    activate        — MuninnDB cognitive retrieval via ACTIVATE pipeline
    timeline        — reference timeline of life events (add/list/query)

Usage:
    python -m promaia.brain.mcp_server
"""
import asyncio
import json
import logging
import os
import sys
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv

# Load .env from the project root (walk up from this file to find it)
_project_root = Path(__file__).resolve().parents[2]
load_dotenv(_project_root / ".env")

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
from promaia.brain.onboarding import (
    start_onboarding, get_onboarding_status,
    mark_channel_progress, get_profile_coverage,
    complete_onboarding, EXPECTED_FIELDS,
)
from promaia.brain.channels.interview import (
    get_interview_state,
    get_next_question,
    mark_question_answered,
)
from promaia.brain.muninn import get_muninn

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
    """Enumerate all 13 brain tools."""
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
        Tool(
            name="profile",
            description=(
                "Read the user's personal profile. Returns all dimensions or "
                "a specific category. Categories include: identity, cognitive_style, "
                "energy_patterns, emotional_landscape, values_and_motivation, "
                "communication, work_patterns, relationships, neurodivergence."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "category": {
                        "type": "string",
                        "description": "Filter by category (optional). Leave empty for full profile."
                    },
                    "query": {
                        "type": "string",
                        "description": "Semantic search across profile (optional). E.g. 'what motivates me'"
                    }
                },
                "required": []
            }
        ),
        Tool(
            name="update_profile",
            description=(
                "Set or update a personal profile field. Each field has a category, "
                "name, value, confidence score (0.0-1.0), and source "
                "(declared=user said it, inferred=AI observed it, confirmed=user verified inference). "
                "Use this during onboarding interviews, when learning about the user, "
                "or when the user corrects a previous inference."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "category": {
                        "type": "string",
                        "description": "Profile category (e.g. 'cognitive_style', 'communication', 'values_and_motivation')."
                    },
                    "field": {
                        "type": "string",
                        "description": "Field name (e.g. 'decision_making', 'humor_type', 'chronotype')."
                    },
                    "value": {
                        "description": "The value — can be string, number, array, or object."
                    },
                    "confidence": {
                        "type": "number",
                        "description": "Confidence 0.0-1.0 (default 0.8 for declared, 0.5 for inferred)."
                    },
                    "source": {
                        "type": "string",
                        "description": "Source: 'declared', 'inferred', or 'confirmed' (default 'declared')."
                    }
                },
                "required": ["category", "field", "value"]
            }
        ),
        Tool(
            name="onboard",
            description=(
                "Manage the onboarding flow. Actions: "
                "'start' begins or resumes onboarding, "
                "'status' returns current progress and profile coverage gaps, "
                "'next_question' returns the next interview question to ask based on profile gaps, "
                "'channel_update' marks a channel's progress, "
                "'complete' finalizes onboarding. "
                "Call 'next_question' at session start to get a natural question to weave into conversation."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "description": "One of: start, status, next_question, channel_update, complete",
                        "enum": ["start", "status", "next_question", "channel_update", "complete"]
                    },
                    "channel": {
                        "type": "string",
                        "description": "Channel name (for channel_update): interview, pc_scan, gmail, photos"
                    },
                    "channel_status": {
                        "type": "string",
                        "description": "New status (for channel_update): in_progress, complete, skipped"
                    },
                    "fields_populated": {
                        "type": "integer",
                        "description": "Number of profile fields this channel contributed (for channel_update)"
                    },
                    "notes": {
                        "type": "string",
                        "description": "Free-form notes about what was covered (for channel_update)"
                    }
                },
                "required": ["action"]
            }
        ),
        Tool(
            name="pc_scan",
            description=(
                "Run the PC digital fingerprint scan. Analyzes local git repos, "
                "file structure, and installed apps to infer profile data. "
                "Results are stored in brain.profile with source='inferred'. "
                "Safe to run multiple times — results are upserted."
            ),
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        Tool(
            name="gmail_scan",
            description=(
                "Scan Gmail inbox for cleanup, triage, and intelligence extraction. "
                "Supports multiple accounts. Modes: 'cleanup' (categorize junk vs real), "
                "'triage' (surface emails needing attention), 'intelligence' (extract contacts "
                "and patterns for profile), or 'full' (all layers). "
                "Never stores raw email content."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "account": {
                        "type": "string",
                        "description": (
                            "Account label or partial match (e.g. 'zackayak'). "
                            "Omit to scan all connected accounts."
                        ),
                    },
                    "days_back": {
                        "type": "integer",
                        "description": "How many days of email to scan (default 30).",
                        "default": 30
                    },
                    "max_emails": {
                        "type": "integer",
                        "description": "Maximum emails per account to process (default 200).",
                        "default": 200
                    },
                    "mode": {
                        "type": "string",
                        "enum": ["cleanup", "triage", "intelligence", "full"],
                        "description": (
                            "Scan mode. 'cleanup': categorize junk/newsletters/human mail. "
                            "'triage': find emails needing attention. "
                            "'intelligence': extract contacts/patterns for brain profile. "
                            "'full': all of the above. Default: 'full'."
                        ),
                        "default": "full"
                    },
                    "before": {
                        "type": "string",
                        "description": (
                            "Only scan emails before this date (YYYY/MM/DD). "
                            "Use with days_back to scan historical windows."
                        ),
                    }
                },
                "required": []
            }
        ),
        Tool(
            name="gmail_query",
            description=(
                "Search stored Gmail content in the database. "
                "Query by sender, subject keywords, date range, or full-text search. "
                "Returns matching emails with subject, sender, date, and snippet. "
                "Use this to find specific emails or review communication history."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Full-text search across subject and message content.",
                    },
                    "sender": {
                        "type": "string",
                        "description": "Filter by sender email (partial match).",
                    },
                    "days_back": {
                        "type": "integer",
                        "description": "Only search emails from the last N days.",
                        "default": 30
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum results to return (default 20).",
                        "default": 20
                    },
                },
                "required": []
            }
        ),
        Tool(
            name="activate",
            description=(
                "MuninnDB cognitive retrieval using the ACTIVATE pipeline. "
                "Uses context-based associative recall with Hebbian learning, "
                "temporal decay, and graph traversal -- different from vector search. "
                "Returns memories ranked by cognitive relevance, not just similarity. "
                "Use this when you want associative, context-driven recall rather than "
                "keyword or semantic search."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "context": {
                        "type": "string",
                        "description": "Natural language context for cognitive retrieval. Describe what you're thinking about."
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum results (default 10).",
                        "default": 10
                    },
                    "threshold": {
                        "type": "number",
                        "description": "Minimum activation score 0.0-1.0 (default 0.1, lower = more results).",
                        "default": 0.1
                    }
                },
                "required": ["context"]
            }
        ),
        Tool(
            name="timeline",
            description=(
                "Reference timeline of life events. Add milestones, query chronologically, "
                "or find events near a date. Categories: life, career, relationship, education, "
                "health, location, project, milestone. Significance 1-10 (10=most significant). "
                "Supports fuzzy dates (month/year precision)."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["add", "list", "around"],
                        "description": (
                            "'add': record a life event. "
                            "'list': list events (optional category/date filters). "
                            "'around': find events near a specific date."
                        )
                    },
                    "event_date": {
                        "type": "string",
                        "description": "Date as YYYY-MM-DD, YYYY-MM, or YYYY. Required for 'add' and 'around'."
                    },
                    "title": {
                        "type": "string",
                        "description": "Short label for the event (e.g. 'Moved to Portland'). Required for 'add'."
                    },
                    "description": {
                        "type": "string",
                        "description": "Longer description of the event. Optional."
                    },
                    "category": {
                        "type": "string",
                        "enum": ["life", "career", "relationship", "education", "health", "location", "project", "milestone"],
                        "description": "Event category. Default: 'life'."
                    },
                    "significance": {
                        "type": "integer",
                        "description": "1-10 importance (10=most significant). Default: 5."
                    },
                    "domain": {
                        "type": "string",
                        "description": "Optional domain link (e.g. 'heatpup', 'promaia')."
                    },
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional tags for filtering."
                    },
                    "range_days": {
                        "type": "integer",
                        "description": "For 'around': how many days before/after to search (default 365).",
                        "default": 365
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max results for 'list'/'around' (default 20).",
                        "default": 20
                    }
                },
                "required": ["action"]
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
        elif name == "profile":
            return await _handle_profile(arguments)
        elif name == "update_profile":
            return await _handle_update_profile(arguments)
        elif name == "onboard":
            return await _handle_onboard(arguments)
        elif name == "pc_scan":
            return await _handle_pc_scan(arguments)
        elif name == "gmail_scan":
            return await _handle_gmail_scan(arguments)
        elif name == "gmail_query":
            return await _handle_gmail_query(arguments)
        elif name == "activate":
            return await _handle_activate(arguments)
        elif name == "timeline":
            return await _handle_timeline(arguments)
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

    # --- Interview / Profile gaps ---
    try:
        interview_state = get_interview_state(db=db)
        next_q = get_next_question(db=db)

        if next_q:
            lines.append("## Get to Know You")
            lines.append(f"Profile {interview_state['completion_pct']}% covered — "
                         f"{len(interview_state['categories_remaining'])} categories need attention.")
            lines.append(f"**Next question ({next_q['category']}):** {next_q['text']}")
            if next_q.get('ai_disclosure'):
                lines.append(f"*Your disclosure:* {next_q['ai_disclosure']}")
            lines.append("")
        elif interview_state['completion_pct'] < 100:
            lines.append("## Get to Know You")
            lines.append(f"Profile {interview_state['completion_pct']}% covered. "
                         "Use progressive profiling during conversation.")
            lines.append("")
    except Exception as e:
        logger.warning(f"briefing interview state failed: {e}")

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

    # MuninnDB dual-write (best-effort -- never blocks Postgres capture)
    try:
        muninn = await get_muninn()
        if muninn:
            tags = [domain_name] if domain_name else []
            await muninn.write(
                concept=content[:100],
                content=content,
                tags=tags,
            )
    except Exception as e:
        logger.warning(f"MuninnDB write failed (non-fatal): {e}")

    if action_count > 0:
        return [TextContent(type="text", text=f"Captured. Extracted {action_count} action(s).")]
    return [TextContent(type="text", text="Captured.")]


async def _handle_search(args: dict) -> list[TextContent]:
    """Semantic vector search over brain.memories + MuninnDB ACTIVATE (parallel trial)."""
    db = get_db()
    query = args.get("query", "").strip()
    if not query:
        return [TextContent(type="text", text="Error: query is required.")]

    limit = int(args.get("limit", 10))

    # --- pgvector search (existing logic, unchanged) ---
    pg_rows = []
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
                pg_rows = [dict(r) for r in cur.fetchall()]
    except Exception as e:
        logger.error(f"pgvector search failed: {e}", exc_info=True)

    # --- MuninnDB ACTIVATE (best-effort, parallel trial) ---
    muninn_results = []
    try:
        muninn = await get_muninn()
        if muninn:
            response = await muninn.activate(
                context=[query],
                max_results=limit,
                threshold=0.1,
            )
            muninn_results = response.get("activations", [])
    except Exception as e:
        logger.warning(f"MuninnDB activate failed (non-fatal): {e}")

    # --- Format results with source labels ---
    if not pg_rows and not muninn_results:
        return [TextContent(type="text", text="No results found.")]

    lines = [f"# Search Results for: {query}\n"]

    if pg_rows:
        lines.append("## pgvector Results")
        for i, row in enumerate(pg_rows, 1):
            similarity = 1 - float(row['distance'])
            domain_label = f" [{row['domain']}]" if row.get('domain') else ""
            ts = _fmt_ts(row.get('created_at'))
            content_preview = row['content'][:200] + ("..." if len(row['content']) > 200 else "")
            lines.append(f"**{i}.** [pgvector]{domain_label} (similarity: {similarity:.2f}, {ts})")
            lines.append(f"{content_preview}\n")

    if muninn_results:
        lines.append("## MuninnDB ACTIVATE Results")
        for i, a in enumerate(muninn_results, 1):
            score = a.get("score", 0)
            concept = a.get("concept", "")
            content_preview = a.get("content", "")[:200]
            sc = a.get("score_components", {})
            dormant = " [dormant]" if a.get("dormant") else ""
            lines.append(
                f"**{i}.** [muninn] (score: {score:.3f}, "
                f"semantic={sc.get('semantic_similarity', 0):.2f}, "
                f"hebbian={sc.get('hebbian_boost', 0):.2f}, "
                f"decay={sc.get('decay_factor', 0):.3f}){dormant}"
            )
            lines.append(f"{content_preview}\n")

    return [TextContent(type="text", text="\n".join(lines))]


async def _handle_activate(args: dict) -> list[TextContent]:
    """MuninnDB ACTIVATE cognitive retrieval."""
    context_text = args.get("context", "").strip()
    if not context_text:
        return [TextContent(type="text", text="Error: context is required.")]

    max_results = int(args.get("max_results", 10))
    threshold = float(args.get("threshold", 0.1))

    muninn = await get_muninn()
    if not muninn:
        return [TextContent(
            type="text",
            text="MuninnDB is not available. Use 'search' for pgvector-based retrieval.",
        )]

    try:
        response = await muninn.activate(
            context=[context_text],
            max_results=max_results,
            threshold=threshold,
        )

        activations = response.get("activations", [])
        latency = response.get("latency_ms", 0)
        total = response.get("total_found", 0)

        if not activations:
            return [TextContent(
                type="text",
                text=f"No activations above threshold {threshold}. Try lowering the threshold.",
            )]

        lines = [f"# ACTIVATE Results ({total} found, {latency:.1f}ms)\n"]
        for i, a in enumerate(activations, 1):
            score = a.get("score", 0)
            concept = a.get("concept", "")
            content = a.get("content", "")[:300]
            sc = a.get("score_components", {})
            dormant = " [dormant]" if a.get("dormant") else ""

            lines.append(f"**{i}.** (score: {score:.3f}){dormant}")
            lines.append(f"   Concept: {concept}")
            lines.append(f"   {content}")
            lines.append(
                f"   Components: semantic={sc.get('semantic_similarity', 0):.2f}, "
                f"text={sc.get('full_text_relevance', 0):.2f}, "
                f"hebbian={sc.get('hebbian_boost', 0):.2f}, "
                f"decay={sc.get('decay_factor', 0):.3f}"
            )
            lines.append("")

        # Include brief if available
        brief = response.get("brief", [])
        if brief:
            lines.append("## Brief")
            for b in brief:
                lines.append(f"- {b.get('text', '')}")

        return [TextContent(type="text", text="\n".join(lines))]

    except Exception as e:
        logger.error(f"activate failed: {e}", exc_info=True)
        return [TextContent(type="text", text=f"ACTIVATE error: {e}")]


async def _handle_timeline(args: dict) -> list[TextContent]:
    """Reference timeline of life events — add, list, or query around a date."""
    db = get_db()
    action = args.get("action", "list")

    if action == "add":
        raw_date = args.get("event_date", "").strip()
        title = args.get("title", "").strip()
        if not raw_date or not title:
            return [TextContent(type="text", text="Error: event_date and title are required for 'add'.")]

        # Parse fuzzy dates: YYYY, YYYY-MM, YYYY-MM-DD
        if len(raw_date) == 4:  # YYYY
            event_date = f"{raw_date}-01-01"
            precision = "year"
        elif len(raw_date) == 7:  # YYYY-MM
            event_date = f"{raw_date}-01"
            precision = "month"
        else:
            event_date = raw_date
            precision = "day"

        category = args.get("category", "life")
        significance = int(args.get("significance", 5))
        description = args.get("description")
        domain = args.get("domain")
        tags = args.get("tags", [])

        db.execute(
            """
            INSERT INTO brain.timeline (event_date, date_precision, title, description, category, significance, domain, tags)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (event_date, precision, title, description, category, significance, domain, tags),
        )
        return [TextContent(type="text", text=f"Added to timeline: {title} ({event_date}, {category})")]

    elif action == "list":
        category = args.get("category")
        limit = int(args.get("limit", 20))

        if category:
            rows = db.fetch_all(
                "SELECT * FROM brain.timeline WHERE category = %s ORDER BY event_date",
                (category,),
            )
        else:
            rows = db.fetch_all(
                "SELECT * FROM brain.timeline ORDER BY event_date LIMIT %s",
                (limit,),
            )

        if not rows:
            return [TextContent(type="text", text="No timeline events recorded yet.")]

        lines = ["# Life Timeline\n"]
        for r in rows:
            sig = r.get("significance", 5)
            stars = "*" * min(sig, 3) if sig >= 7 else ""
            prec = r.get("date_precision", "day")
            d = str(r["event_date"])
            if prec == "year":
                d = d[:4]
            elif prec == "month":
                d = d[:7]
            cat = r.get("category", "")
            lines.append(f"- **{d}** [{cat}] {r['title']}{' ' + stars if stars else ''}")
            if r.get("description"):
                lines.append(f"  {r['description']}")
        return [TextContent(type="text", text="\n".join(lines))]

    elif action == "around":
        raw_date = args.get("event_date", "").strip()
        if not raw_date:
            return [TextContent(type="text", text="Error: event_date is required for 'around'.")]

        if len(raw_date) == 4:
            center = f"{raw_date}-07-01"
        elif len(raw_date) == 7:
            center = f"{raw_date}-15"
        else:
            center = raw_date

        range_days = int(args.get("range_days", 365))
        limit = int(args.get("limit", 20))

        rows = db.fetch_all(
            """
            SELECT *, ABS(event_date - %s::date) AS days_away
            FROM brain.timeline
            WHERE event_date BETWEEN %s::date - %s AND %s::date + %s
            ORDER BY ABS(event_date - %s::date)
            LIMIT %s
            """,
            (center, center, range_days, center, range_days, center, limit),
        )

        if not rows:
            return [TextContent(type="text", text=f"No events within {range_days} days of {raw_date}.")]

        lines = [f"# Events near {raw_date}\n"]
        for r in rows:
            days = r.get("days_away", 0)
            prec = r.get("date_precision", "day")
            d = str(r["event_date"])
            if prec == "year":
                d = d[:4]
            elif prec == "month":
                d = d[:7]
            cat = r.get("category", "")
            lines.append(f"- **{d}** [{cat}] {r['title']} ({days}d away)")
            if r.get("description"):
                lines.append(f"  {r['description']}")
        return [TextContent(type="text", text="\n".join(lines))]

    return [TextContent(type="text", text=f"Unknown timeline action: {action}. Use add/list/around.")]


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


async def _handle_profile(args: dict) -> list[TextContent]:
    """Read user profile — full, by category, or by semantic search."""
    db = get_db()
    category = args.get("category", "").strip() or None
    query = args.get("query", "").strip() or None

    # Semantic search path
    if query:
        try:
            vector_mgr = get_vector_mgr()
            query_embedding = vector_mgr.generate_embedding(query)
            query_array = np.array(query_embedding)

            with db.get_connection() as conn:
                register_vector(conn)
                with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                    cur.execute(
                        """
                        SELECT category, field, value, confidence, source, updated_at,
                               embedding <=> %s::vector AS distance
                        FROM brain.profile
                        WHERE embedding IS NOT NULL
                        ORDER BY distance ASC
                        LIMIT 10
                        """,
                        (query_array,),
                    )
                    rows = [dict(r) for r in cur.fetchall()]

            if not rows:
                return [TextContent(type="text", text="No profile data found.")]

            lines = [f"# Profile Search: {query}\n"]
            for row in rows:
                similarity = 1 - float(row['distance'])
                lines.append(
                    f"- **{row['category']}.{row['field']}**: "
                    f"{json.dumps(row['value'])} "
                    f"(confidence: {row['confidence']}, source: {row['source']}, "
                    f"similarity: {similarity:.2f})"
                )
            return [TextContent(type="text", text="\n".join(lines))]

        except Exception as e:
            logger.error(f"profile search failed: {e}", exc_info=True)
            return [TextContent(type="text", text=f"Profile search error: {e}")]

    # Category or full profile path
    try:
        if category:
            rows = db.fetch_all(
                """
                SELECT category, field, value, confidence, source, updated_at
                FROM brain.profile
                WHERE category = %s
                ORDER BY field
                """,
                (category,),
            )
        else:
            rows = db.fetch_all(
                """
                SELECT category, field, value, confidence, source, updated_at
                FROM brain.profile
                ORDER BY category, field
                """
            )

        if not rows:
            if category:
                return [TextContent(type="text", text=f"No profile data for category: {category}")]
            return [TextContent(type="text", text="Profile is empty. Start the onboarding interview to populate it.")]

        lines = ["# Personal Profile\n"]
        current_cat = None
        for row in rows:
            if row['category'] != current_cat:
                current_cat = row['category']
                lines.append(f"\n## {current_cat.replace('_', ' ').title()}")

            source_badge = {"declared": "D", "inferred": "I", "confirmed": "C"}.get(row['source'], "?")
            conf_pct = int(row['confidence'] * 100)
            lines.append(
                f"- **{row['field']}**: {json.dumps(row['value'])} "
                f"[{source_badge} {conf_pct}%]"
            )

        return [TextContent(type="text", text="\n".join(lines))]

    except Exception as e:
        logger.error(f"profile read failed: {e}", exc_info=True)
        return [TextContent(type="text", text=f"Profile error: {e}")]


async def _handle_update_profile(args: dict) -> list[TextContent]:
    """Set or update a single profile field with confidence and source tracking."""
    db = get_db()
    category = args.get("category", "").strip()
    field = args.get("field", "").strip()
    value = args.get("value")

    if not category or not field or value is None:
        return [TextContent(type="text", text="Error: category, field, and value are required.")]

    source = args.get("source", "declared")
    if source not in ("declared", "inferred", "confirmed"):
        source = "declared"

    # Default confidence based on source
    default_confidence = {"declared": 0.8, "inferred": 0.5, "confirmed": 0.9}.get(source, 0.5)
    confidence = float(args.get("confidence", default_confidence))

    value_json = json.dumps(value)

    try:
        # Upsert the profile field
        db.execute(
            """
            INSERT INTO brain.profile (category, field, value, confidence, source, updated_at)
            VALUES (%s, %s, %s::jsonb, %s, %s, NOW())
            ON CONFLICT (category, field) DO UPDATE SET
                value = EXCLUDED.value,
                confidence = EXCLUDED.confidence,
                source = EXCLUDED.source,
                updated_at = NOW()
            """,
            (category, field, value_json, confidence, source),
        )

        # Generate embedding for the field description + value (enables semantic search)
        try:
            embed_text = f"{category} {field}: {value_json}"
            vector_mgr = get_vector_mgr()
            embedding = vector_mgr.generate_embedding(embed_text)
            embedding_array = np.array(embedding)

            with db.get_connection() as conn:
                register_vector(conn)
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        UPDATE brain.profile SET embedding = %s
                        WHERE category = %s AND field = %s
                        """,
                        (embedding_array, category, field),
                    )
        except Exception as e:
            logger.warning(f"Profile embedding failed for {category}.{field}: {e}")

        # Log the profile update event
        try:
            db.execute(
                """
                INSERT INTO brain.events (type, payload, source, session_id)
                VALUES ('profile_update', %s::jsonb, 'session', %s)
                """,
                (json.dumps({"category": category, "field": field}), SESSION_ID),
            )
        except Exception as e:
            logger.warning(f"Could not log profile_update event: {e}")

        source_badge = {"declared": "D", "inferred": "I", "confirmed": "C"}.get(source, "?")
        return [TextContent(
            type="text",
            text=f"Profile updated: {category}.{field} = {value_json} [{source_badge} {int(confidence * 100)}%]"
        )]

    except Exception as e:
        logger.error(f"update_profile failed: {e}", exc_info=True)
        return [TextContent(type="text", text=f"Profile update error: {e}")]


async def _handle_onboard(args: dict) -> list[TextContent]:
    """Manage the onboarding flow: start, status, channel_update, complete."""
    db = get_db()
    action = args.get("action", "").strip()

    if action == "start":
        result = start_onboarding(db=db)
        if result.get('error'):
            return [TextContent(type="text", text=f"Error starting onboarding: {result['error']}")]

        lines = ["# Onboarding Started\n"]
        lines.append(f"**Session ID:** {result['session_id']}")
        lines.append(f"**Status:** {result['status']}\n")
        lines.append("## Channels")
        for ch in result.get('channels', []):
            lines.append(f"- **{ch['channel']}**: {ch['status']}")
        return [TextContent(type="text", text="\n".join(lines))]

    elif action == "status":
        result = get_onboarding_status(db=db)
        if result is None:
            return [TextContent(type="text", text="No active onboarding session. Use action='start' to begin.")]

        lines = ["# Onboarding Progress\n"]
        lines.append(f"**Session ID:** {result['session_id']}")
        lines.append(f"**Status:** {result['status']}")
        lines.append(f"**Started:** {result.get('started_at', 'unknown')}")
        lines.append(f"**Last activity:** {result.get('last_activity', 'unknown')}\n")

        # Channel table
        lines.append("## Channel Progress\n")
        lines.append("| Channel | Status | Fields |")
        lines.append("|---------|--------|--------|")
        for ch in result.get('channels', []):
            lines.append(f"| {ch['channel']} | {ch['status']} | {ch['fields_populated']} |")

        # Profile coverage
        coverage = result.get('profile_coverage', {})
        if coverage:
            lines.append("\n## Profile Coverage\n")
            lines.append("| Category | Populated | Expected | Fill % |")
            lines.append("|----------|-----------|----------|--------|")
            total_pop = 0
            total_exp = 0
            lowest = []  # track for suggested next
            for cat, info in sorted(coverage.items()):
                pop = info['populated']
                exp = info['expected']
                total_pop += pop
                total_exp += exp
                pct = int((pop / exp) * 100) if exp > 0 else 0
                lines.append(f"| {cat} | {pop} | {exp} | {pct}% |")
                lowest.append((pct, cat, info.get('missing', [])))

            overall_pct = int((total_pop / total_exp) * 100) if total_exp > 0 else 0
            lines.append(f"\n**Overall:** {total_pop}/{total_exp} fields ({overall_pct}%)")

            # Suggested next: 3 categories with lowest fill
            lowest.sort(key=lambda x: x[0])
            lines.append("\n## Suggested Next\n")
            for pct, cat, missing in lowest[:3]:
                missing_preview = ', '.join(missing[:4])
                if len(missing) > 4:
                    missing_preview += f", +{len(missing) - 4} more"
                lines.append(f"- **{cat}** ({pct}% filled): missing {missing_preview}")

        return [TextContent(type="text", text="\n".join(lines))]

    elif action == "next_question":
        # Get interview state and next question based on profile gaps
        try:
            state = get_interview_state(db=db)
            question = get_next_question(db=db)

            lines = ["# Interview — Next Question\n"]
            lines.append(f"**Phase:** {state['current_phase']}")
            lines.append(f"**Completion:** {state['completion_pct']}%")
            lines.append(f"**Categories covered:** {', '.join(state['categories_covered']) or 'none'}")
            lines.append(f"**Categories remaining:** {', '.join(state['categories_remaining']) or 'none'}\n")

            if question:
                lines.append("## Ask This\n")
                lines.append(f"**Category:** {question['category']}")
                lines.append(f"**Question:** {question['text']}")
                lines.append(f"**Technique:** {question.get('technique', 'open')}")
                lines.append(f"**Fields this populates:** {', '.join(question.get('fields', []))}")
                if question.get('follow_ups'):
                    lines.append(f"**Follow-ups:** {' / '.join(question['follow_ups'])}")
                if question.get('ai_disclosure'):
                    lines.append(f"**Share about yourself:** {question['ai_disclosure']}")
                lines.append("\n*Rephrase naturally. Don't read the question verbatim — make it conversational.*")
            else:
                lines.append("All interview questions covered! Profile gaps may still exist — use progressive profiling during regular conversations.")

            return [TextContent(type="text", text="\n".join(lines))]
        except Exception as e:
            logger.error(f"next_question failed: {e}", exc_info=True)
            return [TextContent(type="text", text=f"Error getting next question: {e}")]

    elif action == "channel_update":
        channel = args.get("channel", "").strip()
        channel_status = args.get("channel_status", "").strip()
        fields_pop = args.get("fields_populated")
        notes = args.get("notes")

        if not channel or not channel_status:
            return [TextContent(type="text", text="Error: channel and channel_status are required for channel_update.")]

        # Get current active session to find session_id
        status_result = get_onboarding_status(db=db)
        if status_result is None:
            return [TextContent(type="text", text="No active onboarding session. Use action='start' first.")]

        session_id = status_result['session_id']
        success = mark_channel_progress(
            session_id=session_id,
            channel=channel,
            status=channel_status,
            fields_populated=fields_pop,
            notes=notes,
            db=db,
        )

        if success:
            return [TextContent(type="text", text=f"Channel '{channel}' updated to '{channel_status}'.")]
        else:
            return [TextContent(type="text", text=f"Failed to update channel '{channel}'.")]

    elif action == "complete":
        # Get current session
        status_result = get_onboarding_status(db=db)
        if status_result is None:
            return [TextContent(type="text", text="No active onboarding session to complete.")]

        session_id = status_result['session_id']
        success = complete_onboarding(session_id=session_id, db=db)

        if success:
            return [TextContent(type="text", text="Onboarding complete! Profile coverage saved.")]
        else:
            return [TextContent(type="text", text="Failed to complete onboarding.")]

    else:
        return [TextContent(type="text", text=f"Unknown onboard action: '{action}'. Use: start, status, channel_update, complete")]


async def _handle_pc_scan(args: dict) -> list[TextContent]:
    """Run the PC digital fingerprint scan and store inferred profile data."""
    db = get_db()

    try:
        from promaia.brain.channels.pc_scan import run_pc_scan
        result = run_pc_scan(db=db)
    except Exception as e:
        logger.error(f"PC scan failed: {e}", exc_info=True)
        return [TextContent(type="text", text=f"PC scan error: {e}")]

    # Format result as readable text
    lines = ["## PC Scan Results\n"]
    lines.append(f"- **Repos scanned:** {result.get('repos_scanned', 0)}")
    lines.append(f"- **Apps found:** {result.get('apps_found', 0)}")
    lines.append(f"- **Fields updated:** {result.get('fields_updated', 0)}")

    insights = result.get("insights", [])
    if insights:
        lines.append("\n### Insights\n")
        for insight in insights:
            lines.append(f"- {insight}")

    # Log event to brain.events
    try:
        db.execute(
            """
            INSERT INTO brain.events (type, payload, source, session_id)
            VALUES ('pc_scan', %s::jsonb, 'onboarding', %s)
            """,
            (
                json.dumps({
                    "repos_scanned": result.get("repos_scanned", 0),
                    "apps_found": result.get("apps_found", 0),
                    "fields_updated": result.get("fields_updated", 0),
                }),
                SESSION_ID,
            ),
        )
    except Exception as e:
        logger.warning(f"Could not log pc_scan event: {e}")

    return [TextContent(type="text", text="\n".join(lines))]


async def _handle_gmail_scan(args: dict) -> list[TextContent]:
    """Scan Gmail inbox for cleanup, triage, and intelligence."""
    db = get_db()
    account = args.get("account")
    days_back = int(args.get("days_back", 30))
    max_emails = int(args.get("max_emails", 200))
    mode = args.get("mode", "full")
    before = args.get("before")

    try:
        from promaia.brain.channels.gmail_read import run_gmail_scan, discover_accounts
    except Exception as e:
        logger.error(f"Gmail module import failed: {e}", exc_info=True)
        return [TextContent(type="text", text=f"Gmail scan error: {e}")]

    # Show available accounts if none connected
    accounts = discover_accounts()
    if not accounts:
        return [TextContent(type="text", text="No Gmail tokens found. Run OAuth setup first.")]

    try:
        result = run_gmail_scan(
            account=account,
            days_back=days_back,
            max_emails=max_emails,
            mode=mode,
            db=db if mode in ("intelligence", "full") else None,
            before=before,
        )
    except Exception as e:
        logger.error(f"Gmail scan failed: {e}", exc_info=True)
        return [TextContent(type="text", text=f"Gmail scan error: {e}")]

    if result.get("error"):
        return [TextContent(type="text", text=f"Gmail scan: {result['error']}")]

    # Load known relationships for cross-referencing
    known_contacts = {}
    try:
        rows = db.fetch_all(
            "SELECT field, value FROM brain.profile WHERE category = 'relationships'"
        )
        for row in rows:
            val = row[1] if isinstance(row[1], dict) else {}
            # Extract emails/names from relationship records
            for key in ("email", "name"):
                if key in val:
                    known_contacts[val[key].lower()] = row[0]
            # Handle email_contacts list
            if isinstance(row[1], list):
                for c in row[1]:
                    if isinstance(c, dict) and c.get("email"):
                        known_contacts[c["email"].lower()] = c.get("name", row[0])
    except Exception as e:
        logger.debug(f"Could not load known contacts: {e}")

    # Format results
    lines = [f"## Gmail Scan Results (mode: {mode})\n"]

    summary = result.get("summary", {})
    lines.append(f"**Accounts scanned:** {summary.get('accounts_scanned', 0)}")
    lines.append(f"**Total emails scanned:** {summary.get('total_emails_scanned', 0)}")

    if summary.get("total_junk_identified"):
        lines.append(f"**Total junk identified:** {summary['total_junk_identified']}")

    for email, acct in result.get("accounts", {}).items():
        if "error" in acct:
            lines.append(f"\n### {email}\nError: {acct['error']}")
            continue

        lines.append(f"\n### {acct.get('email', email)}")
        lines.append(f"Emails scanned: {acct.get('emails_scanned', 0)}")

        # Layer 1: Cleanup categories
        cats = acct.get("categories", {})
        if any(cats.values()):
            lines.append("\n**Email Categories:**")
            lines.append(f"  Human mail: {cats.get('human', 0)}")
            lines.append(f"  Newsletters: {cats.get('newsletter', 0)}")
            lines.append(f"  Promotions: {cats.get('promotion', 0)}")
            lines.append(f"  Automated: {cats.get('automated', 0)}")
            total = sum(cats.values())
            junk = total - cats.get("human", 0)
            if total > 0:
                lines.append(f"  **Junk ratio: {junk}/{total} ({100*junk//total}%)**")

        # Unsubscribe candidates
        unsubs = acct.get("unsubscribe_candidates", [])
        if unsubs:
            lines.append(f"\n**Top Unsubscribe Candidates** ({len(unsubs)} senders):")
            for u in unsubs[:10]:
                relation = known_contacts.get(u['email'].lower(), '')
            tag = f" (KNOWN: {relation})" if relation else ""
            lines.append(f"  - {u['email']}{tag} ({u['count']} emails)")

        # Layer 2: Attention items
        attention = acct.get("attention_needed", [])
        if attention:
            lines.append(f"\n**Needs Attention** ({len(attention)} items):")
            for a in attention[:10]:
                status = "[unread]" if a.get("unread") else "[read]"
                sender = a['from'] or ''
            relation = known_contacts.get(sender.lower(), '')
            tag = f" (KNOWN: {relation})" if relation else ""
            lines.append(f"  - {status} {sender}{tag}: {a['subject']}")

        # Layer 3: Intelligence
        if acct.get("contacts_found"):
            lines.append(f"\nContacts found: {acct['contacts_found']}")
        if acct.get("fields_updated"):
            lines.append(f"Profile fields updated: {acct['fields_updated']}")

    # Log event
    try:
        db.execute(
            """
            INSERT INTO brain.events (type, payload, source, session_id)
            VALUES ('gmail_scan', %s::jsonb, 'onboarding', %s)
            """,
            (
                json.dumps({
                    "mode": mode,
                    "accounts_scanned": summary.get("accounts_scanned", 0),
                    "total_emails_scanned": summary.get("total_emails_scanned", 0),
                    "total_junk_identified": summary.get("total_junk_identified", 0),
                }),
                SESSION_ID,
            ),
        )
    except Exception as e:
        logger.warning(f"Could not log gmail_scan event: {e}")

    return [TextContent(type="text", text="\n".join(lines))]


async def _handle_gmail_query(args: dict) -> list[TextContent]:
    """Query stored Gmail content from the gmail_content table."""
    db = get_db()
    query_text = args.get("query", "")
    sender = args.get("sender", "")
    days_back = args.get("days_back", 30)
    limit = min(args.get("limit", 20), 50)

    conditions = []
    params = []

    if query_text:
        conditions.append(
            "(subject ILIKE %s OR message_content ILIKE %s OR body_snippet ILIKE %s)"
        )
        like = f"%{query_text}%"
        params.extend([like, like, like])

    if sender:
        conditions.append("sender_email ILIKE %s")
        params.append(f"%{sender}%")

    if days_back:
        conditions.append(
            "email_date >= (NOW() - INTERVAL '%s days')::text"
        )
        params.append(days_back)

    where = " AND ".join(conditions) if conditions else "TRUE"
    sql = f"""
        SELECT subject, sender_email, sender_name, email_date,
               body_snippet, thread_id, is_unread, gmail_labels
        FROM gmail_content
        WHERE {where}
        ORDER BY email_date DESC
        LIMIT %s
    """
    params.append(limit)

    try:
        rows = db.fetch_all(sql, tuple(params))
    except Exception as e:
        return [TextContent(type="text", text=f"Gmail query error: {e}")]

    if not rows:
        parts = []
        if query_text:
            parts.append(f"matching '{query_text}'")
        if sender:
            parts.append(f"from '{sender}'")
        return [TextContent(
            type="text",
            text=f"No emails found {' '.join(parts)} in the last {days_back} days."
        )]

    lines = [f"**Gmail Query Results** ({len(rows)} emails)\n"]
    for r in rows:
        date = r.get("email_date", "")[:10] if r.get("email_date") else "?"
        sender_display = r.get("sender_name") or r.get("sender_email", "?")
        unread = " [unread]" if r.get("is_unread") else ""
        snippet = (r.get("body_snippet") or "")[:120]
        lines.append(f"- **{r.get('subject', '(no subject)')}**{unread}")
        lines.append(f"  From: {sender_display} | {date}")
        if snippet:
            lines.append(f"  > {snippet}")
        lines.append("")

    return [TextContent(type="text", text="\n".join(lines))]


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
