import json
import logging
import uuid
import urllib.request
import numpy as np
import psycopg2.extras
from mcp.types import TextContent
from datetime import datetime, timezone
from promaia.storage.postgres_db import PostgresDB
from promaia.storage.vector_db import VectorDBManager
from promaia.brain import engine
from promaia.brain.extraction import extract_actions, extract_insights
from promaia.brain.core.memory_pipeline import capture_memory
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
from promaia.brain.mcp.core_context import SESSION_ID, get_db, get_vector_mgr, get_muninn_client
from promaia.brain.mcp.handlers.common import _get_or_create_domain_id, _days_ago, _fmt_ts, _today_str

logger = logging.getLogger(__name__)




async def _handle_briefing(args: dict) -> list[TextContent]:
    """Return stale projects, pending actions, and recent heartbeat activity."""
    db = get_db()
    lines = ["# Session Briefing\n"]

    # --- Promaia server health check (always first) ---
    try:
        promaia_url = "http://localhost:8000/api/health"
        req = urllib.request.Request(promaia_url, headers={"User-Agent": "antigravity-briefing/1.0"})
        with urllib.request.urlopen(req, timeout=3) as resp:
            promaia_up = resp.status == 200
    except Exception:
        promaia_up = False

    if not promaia_up:
        lines.append(
            "## \u26a0\ufe0f PROMAIA IS OFFLINE\n"
            "The Promaia server is not responding at localhost:8000.\n"
            "**The heartbeat, memory capture, and voice bridge are all paused.**\n"
            "Restart: open a terminal in `dev/promaia` and run:\n"
            "`python -m uvicorn promaia.web.main:app --host 0.0.0.0 --port 8000`\n"
        )
    else:
        lines.append("## Promaia: Online\n")


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

    # --- Profile gap awareness ---
    try:
        from promaia.brain.channels.interview import _get_populated_fields, _category_fill_pct
        populated = _get_populated_fields(db=db)

        # Build gap analysis: thin vs rich categories
        thin = []  # < 3 fields populated
        moderate = []  # 3-5 fields
        rich = []  # 5+ fields
        for cat in EXPECTED_FIELDS:
            count = len(populated.get(cat, set()))
            fill = _category_fill_pct(cat, populated)
            if count == 0:
                thin.append((cat, count))
            elif fill < 0.4:
                thin.append((cat, count))
            elif fill < 0.7:
                moderate.append((cat, count))
            else:
                rich.append((cat, count))

        # Also check categories NOT in EXPECTED_FIELDS but in the profile
        # (ambient capture may create categories the schema doesn't expect)
        all_profile_cats = set(populated.keys())
        expected_cats = set(EXPECTED_FIELDS.keys())
        extra_cats = all_profile_cats - expected_cats
        for cat in extra_cats:
            count = len(populated.get(cat, set()))
            rich.append((cat, count))

        total_fields = sum(len(fs) for fs in populated.values())

        if thin or moderate:
            lines.append("## Profile Gaps")
            lines.append(f"{total_fields} fields across {len(all_profile_cats)} categories.")
            if thin:
                thin_str = ", ".join(f"{c} ({n})" for c, n in sorted(thin, key=lambda x: x[1]))
                lines.append(f"**Thin areas:** {thin_str}")
            if moderate:
                mod_str = ", ".join(f"{c} ({n})" for c, n in sorted(moderate, key=lambda x: x[1]))
                lines.append(f"**Moderate:** {mod_str}")
            lines.append("If a natural moment arises, explore a thin area — "
                         "but only from genuine curiosity, not a script.")
            lines.append("")
        else:
            lines.append("## Profile\n"
                         f"{total_fields} fields across {len(all_profile_cats)} categories. "
                         "Well-covered — rely on progressive profiling.\n")
    except Exception as e:
        logger.warning(f"briefing profile gaps failed: {e}")

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

