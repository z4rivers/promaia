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

# Helpers
def _get_or_create_domain_id(db, domain_name: str) -> int:
    existing = db.fetch_one("SELECT id FROM brain.domains WHERE name = %s", (domain_name,))
    if existing: return existing['id']
    return db.insert_returning("INSERT INTO brain.domains (name) VALUES (%s) RETURNING id", (domain_name,))

def _days_ago(ts) -> float:
    if ts is None: return 0.0
    now = datetime.now(timezone.utc)
    if isinstance(ts, str):
        try: ts = datetime.fromisoformat(ts)
        except ValueError: return 0.0
    if getattr(ts, 'tzinfo', None) is None: ts = ts.replace(tzinfo=timezone.utc)
    return (now - ts).total_seconds() / 86400.0

def _fmt_ts(ts) -> str:
    if ts is None: return "unknown"
    if isinstance(ts, str):
        try: ts = datetime.fromisoformat(ts)
        except ValueError: return str(ts)
    if getattr(ts, 'tzinfo', None) is None: ts = ts.replace(tzinfo=timezone.utc)
    return ts.strftime("%Y-%m-%d %H:%M UTC")

def _today_str() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


async def _handle_brain_costs(args: dict) -> list[TextContent]:
    """Return formatted cost summary for the user."""
    days = args.get("days", 7)
    try:
        from promaia.agents.cost_tracker import CostTracker

        tracker = CostTracker()
        today_spend = tracker.get_daily_spend()
        summary = tracker.get_daily_summary(days=days)

        lines = ["## Agent Costs", ""]
        lines.append("### Today")
        lines.append(f"Total: ${today_spend:.4f}")
        lines.append("")

        lines.append(f"### Last {days} days")
        if summary:
            lines.append(
                "| Date | Agent | Calls | Input Tokens | Output Tokens | Cached Tokens | Cost |"
            )
            lines.append(
                "|------|-------|-------|-------------|--------------|--------------|------|"
            )
            total_cost = 0.0
            for row in summary:
                day_str = str(row.get("day", ""))
                agent = row.get("agent_name", "")
                calls = row.get("calls", 0)
                inp = row.get("input_tokens", 0) or 0
                out = row.get("output_tokens", 0) or 0
                cached = row.get("cached_tokens", 0) or 0
                cost = row.get("cost", 0.0) or 0.0
                total_cost += cost
                lines.append(
                    f"| {day_str} | {agent} | {calls} | {inp:,} | {out:,} | {cached:,} | ${cost:.4f} |"
                )
            lines.append("")
            lines.append("### Totals")
            lines.append(f"Total spend (last {days} days): ${total_cost:.4f}")
        else:
            lines.append("No cost data recorded yet.")

        result = "\n".join(lines)
        logger.info(f"brain_costs: today=${today_spend:.4f}, {len(summary)} rows")
        return [TextContent(type="text", text=result)]

    except Exception as e:
        logger.error(f"brain_costs failed: {e}", exc_info=True)
        return [TextContent(type="text", text=f"Error fetching costs: {e}")]

