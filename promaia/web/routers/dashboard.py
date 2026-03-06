"""
Dashboard router — serves the Promaia web dashboard with live brain data.
"""

import logging
import os
from datetime import datetime

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

router = APIRouter(tags=["dashboard"])
logger = logging.getLogger(__name__)

# Templates directory relative to this file
templates_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates")
templates = Jinja2Templates(directory=templates_dir)

VALID_SKINS = [
    "stone-garden",
    "ink-wash",
    "evening-garden",
    "data-temple",
    "superflat",
    "neo-tokyo",
]
DEFAULT_SKIN = "stone-garden"


def _format_day(dt: datetime) -> str:
    """Format date as 'Wednesday, March 5' — handles Windows vs Unix strftime."""
    try:
        return dt.strftime("%A, %B %-d")
    except ValueError:
        # Windows uses %#d instead of %-d
        return dt.strftime("%A, %B %#d")


def _get_brain_data() -> dict:
    """Query live brain data from Postgres. Returns dashboard-ready dicts."""
    try:
        from promaia.storage.postgres_db import get_postgres_db
        db = get_postgres_db()

        # Counts (single roundtrip)
        counts = db.fetch_one(
            """
            SELECT
                (SELECT COUNT(*) FROM brain.memories) as memory_count,
                (SELECT COUNT(*) FROM brain.actions WHERE status = 'pending') as action_count,
                (SELECT COUNT(*) FROM brain.contexts) as context_count
            """
        ) or {"memory_count": 0, "action_count": 0, "context_count": 0}

        # Pending/active actions
        actions_rows = db.fetch_all(
            """
            SELECT a.description, a.status, d.name AS domain_name
            FROM brain.actions a
            LEFT JOIN brain.domains d ON d.id = a.domain_id
            WHERE a.status IN ('pending', 'active')
            ORDER BY a.extracted_at DESC
            LIMIT 10
            """
        )
        actions = [
            {
                "text": row["description"],
                "domain": row.get("domain_name") or "general",
                "status": row["status"],
            }
            for row in actions_rows
        ]

        # Projects from contexts
        project_rows = db.fetch_all(
            """
            SELECT d.name, c.current_state, c.last_updated, c.priority,
                   EXTRACT(DAY FROM NOW() - c.last_updated)::int as days_stale
            FROM brain.contexts c
            JOIN brain.domains d ON d.id = c.domain_id
            ORDER BY c.priority ASC, c.last_updated DESC
            """
        )
        projects = []
        for row in project_rows:
            days = row.get("days_stale") or 0
            if days > 14:
                status = "resting"
            else:
                status = "active"
            detail = row.get("current_state") or ""
            if len(detail) > 80:
                detail = detail[:77] + "..."
            projects.append({
                "name": row["name"],
                "status": status,
                "detail": detail,
            })

        # Recent memories
        memory_rows = db.fetch_all(
            """
            SELECT content, domain, created_at
            FROM brain.memories
            ORDER BY created_at DESC
            LIMIT 5
            """
        )
        recent_memories = []
        for row in memory_rows:
            created = row.get("created_at")
            if created:
                now = datetime.now(created.tzinfo) if created.tzinfo else datetime.now()
                delta = (now - created).days
                if delta == 0:
                    time_str = "today"
                elif delta == 1:
                    time_str = "yesterday"
                else:
                    time_str = f"{delta} days ago"
            else:
                time_str = ""
            content = row.get("content") or ""
            if len(content) > 120:
                content = content[:117] + "..."
            recent_memories.append({
                "content": content,
                "domain": row.get("domain") or "general",
                "created_at": time_str,
            })

        return {
            "brain_status": {
                "memories": counts["memory_count"],
                "actions": counts["action_count"],
                "contexts": counts["context_count"],
            },
            "actions": actions,
            "projects": projects,
            "recent_memories": recent_memories,
        }

    except Exception as e:
        logger.warning(f"Brain data unavailable: {e}")
        return {
            "brain_status": {"memories": 0, "actions": 0, "contexts": 0},
            "actions": [],
            "projects": [],
            "recent_memories": [],
        }


@router.get("/", response_class=HTMLResponse)
@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request, skin: str = None):
    """Render the main dashboard with live brain data."""
    if skin not in VALID_SKINS:
        skin = DEFAULT_SKIN

    hour = datetime.now().hour
    if hour < 12:
        greeting = "Good morning"
    elif hour < 17:
        greeting = "Good afternoon"
    else:
        greeting = "Good evening"

    now = datetime.now()
    date_str = _format_day(now)

    brain = _get_brain_data()

    context = {
        "request": request,
        "skin": skin,
        "valid_skins": VALID_SKINS,
        "greeting": greeting,
        "date_str": date_str,
        "user_name": "Zack",
        **brain,
    }

    return templates.TemplateResponse("dashboard.html", context)
