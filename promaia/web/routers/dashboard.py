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


def _resolve_skin(skin: str) -> str:
    return skin if skin in VALID_SKINS else DEFAULT_SKIN


def _base_context(request: Request, skin: str) -> dict:
    return {"request": request, "skin": skin, "valid_skins": VALID_SKINS}


@router.get("/projects", response_class=HTMLResponse)
async def projects_page(request: Request, skin: str = None):
    """Render the projects detail page."""
    skin = _resolve_skin(skin)
    try:
        from promaia.storage.postgres_db import get_postgres_db
        db = get_postgres_db()

        project_rows = db.fetch_all(
            """
            SELECT d.name, c.directive, c.current_state, c.last_updated, c.priority,
                   EXTRACT(DAY FROM NOW() - c.last_updated)::int as days_stale
            FROM brain.contexts c
            JOIN brain.domains d ON d.id = c.domain_id
            ORDER BY c.priority ASC
            """
        )

        projects = []
        for row in project_rows:
            # Get actions for this project
            action_rows = db.fetch_all(
                """
                SELECT a.description FROM brain.actions a
                JOIN brain.domains d ON d.id = a.domain_id
                WHERE d.name = %s AND a.status = 'pending'
                ORDER BY a.extracted_at DESC LIMIT 5
                """,
                (row["name"],),
            )

            last_updated = row.get("last_updated")
            if last_updated:
                delta = (datetime.now(last_updated.tzinfo) - last_updated).days
                if delta == 0:
                    updated_str = "today"
                elif delta == 1:
                    updated_str = "yesterday"
                else:
                    updated_str = f"{delta} days ago"
            else:
                updated_str = "unknown"

            projects.append({
                "name": row["name"],
                "directive": row.get("directive") or "",
                "current_state": row.get("current_state") or "",
                "last_updated": updated_str,
                "priority": row.get("priority") or 5,
                "days_stale": row.get("days_stale") or 0,
                "actions": [a["description"] for a in action_rows],
            })
    except Exception as e:
        logger.warning(f"Projects data unavailable: {e}")
        projects = []

    return templates.TemplateResponse("projects.html", {
        **_base_context(request, skin),
        "projects": projects,
    })


@router.get("/email", response_class=HTMLResponse)
async def email_page(request: Request, skin: str = None):
    """Render the email intelligence page."""
    skin = _resolve_skin(skin)
    emails = []
    stats = {"total": 0, "unread": 0, "today": 0}
    email_account = "zachary4rivers@gmail.com"

    try:
        from promaia.storage.postgres_db import get_postgres_db
        db = get_postgres_db()

        # Stats
        stat_row = db.fetch_one(
            """
            SELECT
                COUNT(*) as total,
                COUNT(*) FILTER (WHERE is_unread) as unread,
                COUNT(*) FILTER (WHERE email_date::date = CURRENT_DATE) as today
            FROM gmail_content
            """
        )
        if stat_row:
            stats = {
                "total": stat_row["total"],
                "unread": stat_row["unread"],
                "today": stat_row["today"],
            }

        # Recent emails
        email_rows = db.fetch_all(
            """
            SELECT sender_name, sender_email, subject, body_snippet,
                   is_unread, email_date
            FROM gmail_content
            ORDER BY synced_time DESC
            LIMIT 30
            """
        )
        for row in email_rows:
            date_str = row.get("email_date") or ""
            if len(date_str) > 25:
                date_str = date_str[:25]
            emails.append({
                "sender_name": row.get("sender_name") or "",
                "sender_email": row.get("sender_email") or "",
                "subject": row.get("subject") or "(no subject)",
                "snippet": row.get("body_snippet") or "",
                "is_unread": row.get("is_unread") or False,
                "date": date_str,
            })
    except Exception as e:
        logger.warning(f"Email data unavailable: {e}")

    return templates.TemplateResponse("email.html", {
        **_base_context(request, skin),
        "emails": emails,
        "stats": stats,
        "email_account": email_account,
    })


@router.get("/profile", response_class=HTMLResponse)
async def profile_page(request: Request, skin: str = None):
    """Render the personal profile page."""
    skin = _resolve_skin(skin)
    categories = {}
    trait_count = 0
    declared_count = 0
    inferred_count = 0

    try:
        from promaia.storage.postgres_db import get_postgres_db
        db = get_postgres_db()

        rows = db.fetch_all(
            """
            SELECT category, field, value, confidence, source
            FROM brain.profile
            ORDER BY category, field
            """
        )

        for row in rows:
            cat = row.get("category") or "other"
            if cat not in categories:
                categories[cat] = []

            value = row.get("value") or ""
            # Truncate long JSON values for display
            if len(value) > 200:
                value = value[:197] + "..."

            confidence = row.get("confidence") or 0
            source = row.get("source") or "unknown"

            source_labels = {
                "declared": "D",
                "inferred": "I",
                "confirmed": "C",
            }

            categories[cat].append({
                "field": row.get("field") or "",
                "display_value": value,
                "confidence_pct": int(confidence * 100),
                "source_label": source_labels.get(source, source[0].upper()),
            })

            trait_count += 1
            if source == "declared":
                declared_count += 1
            elif source == "inferred":
                inferred_count += 1

    except Exception as e:
        logger.warning(f"Profile data unavailable: {e}")

    return templates.TemplateResponse("profile.html", {
        **_base_context(request, skin),
        "user_name": "Zack",
        "categories": categories,
        "trait_count": trait_count,
        "category_count": len(categories),
        "declared_count": declared_count,
        "inferred_count": inferred_count,
    })
