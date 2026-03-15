"""
Dashboard router — serves the Promaia web dashboard with live brain data.
"""

import logging
import os
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

router = APIRouter(tags=["dashboard"])
logger = logging.getLogger(__name__)

# Templates directory relative to this file
templates_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates")
templates = Jinja2Templates(directory=templates_dir)

SKIN = "superflat"


def _format_day(dt: datetime) -> str:
    """Format date as 'Wednesday, March 5' — handles Windows vs Unix strftime."""
    try:
        return dt.strftime("%A, %B %-d")
    except ValueError:
        # Windows uses %#d instead of %-d
        return dt.strftime("%A, %B %#d")


def _parse_iso_age(iso_str: str) -> str:
    """Parse an ISO timestamp string and return a human-friendly age like 'today' or '3 days ago'."""
    if not iso_str:
        return ""
    try:
        created = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        delta = (now - created).days
        if delta <= 0:
            return "today"
        elif delta == 1:
            return "yesterday"
        else:
            return f"{delta} days ago"
    except (ValueError, TypeError):
        return ""


def _get_brain_data() -> dict:
    """Query live brain data from libSQL. Returns dashboard-ready dicts."""
    try:
        from promaia.storage.db_factory import get_db
        db = get_db()

        # Counts
        counts = db.fetch_one(
            """
            SELECT
                (SELECT COUNT(*) FROM memories) as memory_count,
                (SELECT COUNT(*) FROM actions WHERE status = 'pending') as action_count,
                (SELECT COUNT(*) FROM contexts) as context_count
            """
        ) or {"memory_count": 0, "action_count": 0, "context_count": 0}

        # Pending/active actions
        actions_rows = db.fetch_all(
            """
            SELECT a.description as content, a.status, d.name as domain
            FROM actions a
            LEFT JOIN domains d ON a.domain_id = d.id
            WHERE a.status IN ('pending', 'active')
            ORDER BY a.extracted_at DESC
            LIMIT 10
            """
        )
        actions = [
            {
                "text": row["content"],
                "domain": row.get("domain") or "general",
                "status": row["status"],
            }
            for row in actions_rows
        ]

        # Projects from contexts  (contexts.domain_id FK → domains.id, priority is on domains)
        project_rows = db.fetch_all(
            """
            SELECT d.name, c.current_state, c.last_updated, c.priority,
                   CAST(julianday('now') - julianday(c.last_updated) AS INTEGER) as days_stale
            FROM contexts c
            JOIN domains d ON d.id = c.domain_id
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

        # Recent memories  (memories.domain is flat TEXT)
        memory_rows = db.fetch_all(
            """
            SELECT content, domain, created_at
            FROM memories
            ORDER BY created_at DESC
            LIMIT 10
            """
        )
        recent_memories = []
        for row in memory_rows:
            time_str = _parse_iso_age(row.get("created_at") or "")
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
async def dashboard(request: Request):
    """Render the main dashboard with live brain data."""
    from zoneinfo import ZoneInfo
    pacific = ZoneInfo("America/Los_Angeles")
    now = datetime.now(pacific)
    hour = now.hour
    if hour < 12:
        greeting = "Good morning"
    elif hour < 17:
        greeting = "Good afternoon"
    else:
        greeting = "Good evening"

    date_str = _format_day(now)

    brain = _get_brain_data()

    calendar_events = _get_calendar_events()

    context = {
        **_base_context(request, "dashboard"),
        "greeting": greeting,
        "date_str": date_str,
        "user_name": "Zack",
        "calendar_events": calendar_events,
        **brain,
    }

    return templates.TemplateResponse("dashboard.html", context)





def _get_calendar_events(days_ahead: int = 7) -> list:
    """Fetch upcoming events from all Google Calendars."""
    try:
        from promaia.gcal.google_calendar import GoogleCalendarManager
        mgr = GoogleCalendarManager()
        if not mgr.authenticate():
            return []

        now = datetime.now(timezone.utc)
        time_max = now + timedelta(days=days_ahead)
        time_min_str = now.isoformat().replace("+00:00", "Z")
        time_max_str = time_max.isoformat().replace("+00:00", "Z")

        all_events = []
        calendars = mgr.service.calendarList().list().execute().get("items", [])

        for cal in calendars:
            cal_id = cal["id"]
            try:
                result = mgr.service.events().list(
                    calendarId=cal_id,
                    timeMin=time_min_str,
                    timeMax=time_max_str,
                    singleEvents=True,
                    orderBy="startTime",
                    maxResults=10,
                ).execute()
                for ev in result.get("items", []):
                    start = ev.get("start", {})
                    start_str = start.get("dateTime") or start.get("date", "")
                    # Parse for display
                    try:
                        if "T" in start_str:
                            dt = datetime.fromisoformat(start_str)
                            display_time = dt.strftime("%a %b %#d, %I:%M %p")
                        else:
                            dt = datetime.strptime(start_str, "%Y-%m-%d")
                            display_time = dt.strftime("%a %b %#d") + " (all day)"
                    except (ValueError, TypeError):
                        display_time = start_str

                    all_events.append({
                        "summary": ev.get("summary", "(no title)"),
                        "time": display_time,
                        "calendar": cal.get("summary", ""),
                        "sort_key": start_str,
                    })
            except Exception:
                continue

        all_events.sort(key=lambda e: e["sort_key"])
        return all_events[:15]

    except Exception as e:
        logger.warning(f"Calendar data unavailable: {e}")
        return []


def _base_context(request: Request, active_page: str = "") -> dict:
    return {"request": request, "skin": SKIN, "active_page": active_page}


@router.get("/talk", response_class=HTMLResponse)
async def talk_page(request: Request):
    """Render the Talk page — mobile hub with voice + compact info feeds."""
    brain = _get_brain_data()

    # Last assistant message for continuity
    last_message = None
    try:
        from promaia.storage.db_factory import get_db
        db = get_db()
        row = db.fetch_one(
            """
            SELECT content FROM conversations
            WHERE role = 'assistant'
            ORDER BY created_at DESC LIMIT 1
            """
        )
        if row and row["content"]:
            content = row["content"]
            last_message = content[:200] + ("..." if len(content) > 200 else "")
    except Exception as e:
        logger.warning(f"Last message unavailable: {e}")

    return templates.TemplateResponse("talk.html", {
        **_base_context(request, "talk"),
        **brain,
        "last_message": last_message,
    })


@router.get("/projects", response_class=HTMLResponse)
async def projects_page(request: Request):
    try:
        from promaia.storage.db_factory import get_db
        db = get_db()

        project_rows = db.fetch_all(
            """
            SELECT d.id, d.name, c.directive, c.current_state, c.last_updated, c.priority,
                   CAST(julianday('now') - julianday(c.last_updated) AS INTEGER) as days_stale
            FROM contexts c
            JOIN domains d ON d.id = c.domain_id
            ORDER BY c.priority ASC, c.last_updated DESC
            """
        )

        projects = []
        for row in project_rows:
            action_rows = db.fetch_all(
                """
                SELECT description FROM actions
                WHERE domain_id = ? AND status = 'pending'
                ORDER BY extracted_at DESC LIMIT 5
                """,
                (row["id"],)
            )

            updated_str = _parse_iso_age(row.get("last_updated") or "")
            if not updated_str:
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
        **_base_context(request, "projects"),
        "projects": projects,
    })


@router.get("/email", response_class=HTMLResponse)
async def email_page(request: Request):
    emails = []
    stats = {"total": 0, "unread": 0, "today": 0}
    email_account = "zachary4rivers@gmail.com"

    try:
        from promaia.storage.db_factory import get_db
        db = get_db()

        # Stats — SQLite doesn't have FILTER, use SUM+CASE
        stat_row = db.fetch_one(
            """
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN is_unread = 1 THEN 1 ELSE 0 END) as unread,
                SUM(CASE WHEN DATE(synced_time) = DATE('now') THEN 1 ELSE 0 END) as today
            FROM gmail_content
            """
        )
        if stat_row:
            stats = {
                "total": stat_row["total"] or 0,
                "unread": stat_row["unread"] or 0,
                "today": stat_row["today"] or 0,
            }

        # Recent emails
        email_rows = db.fetch_all(
            """
            SELECT sender_name, sender_email, subject, body_snippet,
                   is_unread, email_date
            FROM gmail_content
            ORDER BY synced_time DESC, id DESC
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
        **_base_context(request, "email"),
        "emails": emails,
        "stats": stats,
        "email_account": email_account,
    })


@router.get("/profile", response_class=HTMLResponse)
async def profile_page(request: Request):
    categories = {}
    trait_count = 0
    declared_count = 0
    inferred_count = 0

    try:
        from promaia.storage.db_factory import get_db
        db = get_db()

        rows = db.fetch_all(
            """
            SELECT category, field, value, confidence, source
            FROM profile
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
        **_base_context(request, "profile"),
        "user_name": "Zack",
        "categories": categories,
        "trait_count": trait_count,
        "category_count": len(categories),
        "declared_count": declared_count,
        "inferred_count": inferred_count,
    })


@router.get("/api/notifications/unread")
async def notifications_unread():
    """Return count of unrouted events for dashboard badge.
    Note: events table in libSQL has no urgency/routed_at columns.
    Return 0 until notification routing is implemented."""
    return {"unread": 0}


@router.get("/api/scheduler/health")
async def scheduler_health():
    """Return scheduler heartbeat status for dashboard health indicator."""
    try:
        from promaia.storage.db_factory import get_db
        db = get_db()
        row = db.fetch_one(
            """
            SELECT created_at
            FROM events
            WHERE source = 'heartbeat' AND type = 'scheduler_heartbeat'
            ORDER BY created_at DESC
            LIMIT 1
            """
        )
        if row:
            created_str = row["created_at"]
            try:
                created = datetime.fromisoformat(created_str.replace("Z", "+00:00"))
                # SQLite datetime('now') stores UTC without tzinfo — treat as UTC
                if created.tzinfo is None:
                    created = created.replace(tzinfo=timezone.utc)
                now = datetime.now(timezone.utc)
                minutes_ago = (now - created).total_seconds() / 60
                return {
                    "status": "online" if minutes_ago < 10 else "stale",
                    "last_seen_minutes": round(minutes_ago, 1),
                    "last_seen": created_str,
                }
            except (ValueError, TypeError):
                return {"status": "unknown", "last_seen_minutes": None}
        return {"status": "unknown", "last_seen_minutes": None}
    except Exception as e:
        logger.warning(f"Scheduler health check failed: {e}")
        return {"status": "error"}


@router.get("/api/brain/health")
async def brain_daemon_health():
    """Proxy to the brain MCP daemon's /health endpoint.
    Dashboard JS polls this instead of hitting port 8751 directly (avoids CORS).
    """
    import httpx

    port = int(os.environ.get("BRAIN_MCP_PORT", "8751"))
    url = f"http://127.0.0.1:{port}/health"
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, timeout=3.0)
            data = resp.json()
            return {"connected": True, "port": port, **data}
    except Exception:
        return {"connected": False, "port": port, "status": "unreachable"}


@router.post("/api/notifications/read")
async def notifications_mark_read():
    """Mark all unrouted events as read via dashboard channel.
    Note: events table in libSQL has no routed_at/urgency columns.
    No-op until notification routing is implemented."""
    return {"status": "ok", "marked": 0}
