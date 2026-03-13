import json
import logging
import uuid
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




async def _handle_capture(args: dict) -> list[TextContent]:
    """Insert memory, generate embedding, extract actions + conversation intelligence."""
    db = get_db()
    content = args.get("content", "").strip()
    if not content:
        return [TextContent(type="text", text="Error: content is required.")]

    domain_name = args.get("domain")

    try:
        results = await capture_memory(
            db=db,
            vector_mgr=get_vector_mgr(),
            content=content,
            session_id=SESSION_ID,
            domain_name=domain_name,
            source='session',
            confidence=0.9
        )
    except Exception as e:
        logger.error(f"capture insert failed: {e}")
        return [TextContent(type="text", text=f"Error storing memory: {e}")]

    action_count = results.get("action_count", 0)
    intel_counts = results.get("intel_counts", {})

    # Build response summary
    parts = ["Captured."]
    if action_count > 0:
        parts.append(f"Extracted {action_count} action(s).")
    total_intel = sum(intel_counts.values()) if intel_counts else 0
    if total_intel > 0:
        intel_parts = []
        if intel_counts.get("decisions"):
            intel_parts.append(f"{intel_counts['decisions']} decision(s)")
        if intel_counts.get("insights"):
            intel_parts.append(f"{intel_counts['insights']} insight(s)")
        if intel_counts.get("preferences"):
            intel_parts.append(f"{intel_counts['preferences']} preference(s)")
        if intel_counts.get("asides"):
            intel_parts.append(f"{intel_counts['asides']} aside(s)")
        parts.append(f"Intelligence: {', '.join(intel_parts)}.")
    return [TextContent(type="text", text=" ".join(parts))]

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
        query_embedding = vector_mgr.generate_embedding(query, task_type="RETRIEVAL_QUERY")
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
        muninn = await get_muninn_client()
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

async def _handle_recall(args: dict) -> list[TextContent]:
    """Return recent memories filtered by domain and/or time range."""
    db = get_db()
    domain_name = args.get("domain")
    days = int(args.get("days", 30))
    limit = int(args.get("limit", 20))
    has_media = bool(args.get("has_media", False))

    try:
        query = """
            SELECT id, content, domain, created_at, asset_paths
            FROM brain.memories
            WHERE created_at > NOW() - %s * INTERVAL '1 day'
        """
        params: list = [days]

        if domain_name:
            query += " AND domain = %s"
            params.append(domain_name)
            
        if has_media:
            query += " AND jsonb_array_length(asset_paths) > 0"

        query += " ORDER BY created_at DESC LIMIT %s"
        params.append(limit)

        rows = db.fetch_all(query, tuple(params))

        if not rows:
            msg = f"No memories found"
            if domain_name:
                msg += f" in domain '{domain_name}'"
            if has_media:
                msg += f" with attached media"
            msg += f" from the last {days} days."
            return [TextContent(type="text", text=msg)]

        lines = [f"# Recent Memories (last {days} days)\n"]
        for row in rows:
            domain_label = f" [{row['domain']}]" if row.get('domain') else ""
            ts = _fmt_ts(row.get('created_at'))
            
            assets = row.get('asset_paths') or []
            asset_label = f" 📎 {len(assets)} file(s)" if assets else ""
            
            content_preview = row['content'][:300] + ("..." if len(row['content']) > 300 else "")
            lines.append(f"**[{ts}]**{domain_label}{asset_label} {content_preview}\n")

        return [TextContent(type="text", text="\n".join(lines))]

    except Exception as e:
        logger.error(f"recall failed: {e}", exc_info=True)
        return [TextContent(type="text", text=f"Recall error: {e}")]

