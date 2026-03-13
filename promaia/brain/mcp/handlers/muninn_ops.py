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




async def _handle_activate(args: dict) -> list[TextContent]:
    """MuninnDB ACTIVATE cognitive retrieval."""
    context_text = args.get("context", "").strip()
    if not context_text:
        return [TextContent(type="text", text="Error: context is required.")]

    max_results = int(args.get("max_results", 10))
    threshold = float(args.get("threshold", 0.1))

    muninn = await get_muninn_client()
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

