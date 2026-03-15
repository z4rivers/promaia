import json
import logging
import uuid
import numpy as np
from mcp.types import TextContent
from datetime import datetime, timezone
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




async def _handle_profile(args: dict) -> list[TextContent]:
    """Read user profile — narrative, full, by category, or by semantic search."""
    mode = args.get("mode", "").strip() or None

    # Narrative mode — synthesized portrait
    if mode == "narrative":
        from promaia.profile_narrative import get_or_generate_narrative
        narrative = await get_or_generate_narrative()
        return [TextContent(type="text", text=f"# Profile Portrait\n\n{narrative}")]

    db = get_db()
    category = args.get("category", "").strip() or None
    query = args.get("query", "").strip() or None

    # Semantic search path
    if query:
        try:
            vector_mgr = get_vector_mgr()
            query_embedding = vector_mgr.generate_embedding(query, task_type="RETRIEVAL_QUERY")
            query_array = json.dumps(query_embedding)

            rows = db.fetch_all(
                """
                SELECT p.category, p.field, p.value, p.confidence, p.source, p.updated_at,
                       vec_distance_cosine(ce.embedding, ?) AS distance
                FROM content_embeddings ce
                JOIN profile p ON ce.page_id = 'profile:' || p.category || ':' || p.field
                WHERE ce.database_name = 'brain_profile'
                ORDER BY distance ASC
                LIMIT 10
                """,
                (query_array,),
            )
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
                FROM profile
                WHERE category = ?
                ORDER BY field
                """,
                (category,),
            )
        else:
            rows = db.fetch_all(
                """
                SELECT category, field, value, confidence, source, updated_at
                FROM profile
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
            INSERT INTO profile (category, field, value, confidence, source, updated_at)
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT (category, field) DO UPDATE SET
                value = EXCLUDED.value,
                confidence = EXCLUDED.confidence,
                source = EXCLUDED.source,
                updated_at = CURRENT_TIMESTAMP
            """,
            (category, field, value_json, confidence, source),
        )

        # Generate embedding for the field description + value (enables semantic search)
        try:
            embed_text = f"{category} {field}: {value_json}"
            vector_mgr = get_vector_mgr()
            embedding = vector_mgr.generate_embedding(embed_text)
            embedding_array = json.dumps(embedding)

            page_id = f"profile:{category}:{field}"
            db.execute(
                        "DELETE FROM content_embeddings WHERE page_id = %s AND chunk_id IS NULL",
                        (page_id,),
                    )
            db.execute(
                        """INSERT INTO content_embeddings (page_id, content, embedding, database_name, created_at, updated_at)
                           VALUES (%s, %s, %s, 'brain_profile', datetime('now'), datetime('now'))""",
                        (page_id, embed_text, embedding_array),
                    )
        except Exception as e:
            logger.warning(f"Profile embedding failed for {category}.{field}: {e}")

        # Log the profile update event
        try:
            db.execute(
                """
                INSERT INTO events (type, payload, source, session_id)
                VALUES ('profile_update', ?, 'session', ?)
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

    # Log event to events
    try:
        db.execute(
            """
            INSERT INTO events (type, payload, source, session_id)
            VALUES ('pc_scan', ?, 'onboarding', ?)
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
            INSERT INTO timeline (event_date, date_precision, title, description, category, significance, domain, tags)
            VALUES (?, ?, ?, ?, ?, ?, ?, coalesce(json(?), '[]'))
            """,
            (event_date, precision, title, description, category, significance, domain, json.dumps(tags)),
        )
        return [TextContent(type="text", text=f"Added to timeline: {title} ({event_date}, {category})")]

    elif action == "list":
        category = args.get("category")
        limit = int(args.get("limit", 20))

        if category:
            rows = db.fetch_all(
                "SELECT * FROM timeline WHERE category = ? ORDER BY event_date",
                (category,),
            )
        else:
            rows = db.fetch_all(
                "SELECT * FROM timeline ORDER BY event_date LIMIT ?",
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
            SELECT *, ABS(julianday(event_date) - julianday(date(?))) AS days_away
            FROM timeline
            WHERE date(event_date) BETWEEN date(?, '-' || ? || ' days') AND date(?, '+' || ? || ' days')
            ORDER BY ABS(julianday(event_date) - julianday(date(?)))
            LIMIT ?
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

