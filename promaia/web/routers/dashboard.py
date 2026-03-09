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

        # Recent Voice Session Reviews
        audio_reviews_rows = db.fetch_all(
            """
            SELECT id, summary, proposed_memories, raw_transcript, created_at
            FROM brain.audio_session_reviews
            WHERE status = 'pending'
            ORDER BY created_at DESC
            """
        )
        audio_reviews = []
        import json
        for row in audio_reviews_rows:
            # Handle JSON values whether they are strings or already parsed dicts
            prop_mems = row["proposed_memories"]
            if isinstance(prop_mems, str):
                try: prop_mems = json.loads(prop_mems)
                except: prop_mems = []
            
            raw_trans = row["raw_transcript"]
            if isinstance(raw_trans, str):
                try: raw_trans = json.loads(raw_trans)
                except: raw_trans = []
                
            created = row.get("created_at")
            if created:
                now = datetime.now(created.tzinfo) if created.tzinfo else datetime.now()
                delta = (now - created).days
                if delta == 0:
                    time_str = "today"
                else:
                    time_str = f"{delta} days ago"
            else:
                time_str = ""
                
            audio_reviews.append({
                "id": row["id"],
                "summary": row["summary"],
                "proposed_memories": prop_mems,
                "raw_transcript": raw_trans,
                "created_at": time_str
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
            "audio_reviews": audio_reviews,
        }

    except Exception as e:
        logger.warning(f"Brain data unavailable: {e}")
        return {
            "brain_status": {"memories": 0, "actions": 0, "contexts": 0},
            "actions": [],
            "projects": [],
            "recent_memories": [],
            "audio_reviews": [],
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

@router.post("/api/dashboard/review/{review_id}/accept")
async def accept_audio_review(review_id: int):
    try:
        from promaia.storage.postgres_db import get_postgres_db, pg_connect
        db = get_postgres_db()
        review_row = db.fetch_one("SELECT * FROM brain.audio_session_reviews WHERE id = %s", (review_id,))
        if not review_row:
            raise HTTPException(status_code=404, detail="Review not found")
            
        import json
        proposed_memories = review_row["proposed_memories"]
        if isinstance(proposed_memories, str):
            try: proposed_memories = json.loads(proposed_memories)
            except: proposed_memories = []
            
        # Commit memories to Muninn
        if proposed_memories:
            from promaia.brain.muninn import get_muninn
            muninn = await get_muninn()
            if muninn:
                await muninn.write_batch([
                    {"content": m.get("content"), "domain": m.get("domain", "general"), "confidence": 0.9}
                    for m in proposed_memories if m.get("content")
                ])
                
        # Update status and null out transcript
        with pg_connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "UPDATE brain.audio_session_reviews SET status = 'accepted', raw_transcript = NULL WHERE id = %s",
                    (review_id,)
                )
        return {"status": "ok"}
    except Exception as e:
        logger.error(f"Failed to accept review {review_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/dashboard/review/{review_id}/reject")
async def reject_audio_review(review_id: int):
    try:
        from promaia.storage.postgres_db import pg_connect
        with pg_connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "UPDATE brain.audio_session_reviews SET status = 'rejected', raw_transcript = NULL WHERE id = %s",
                    (review_id,)
                )
        return {"status": "ok"}
    except Exception as e:
        logger.error(f"Failed to reject review {review_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/dashboard/review/{review_id}/update")
async def update_audio_review(review_id: int, request: Request):
    """Update a review's summary (used by Edit button before Accept)."""
    try:
        body = await request.json()
        new_summary = body.get("summary", "").strip()
        if not new_summary:
            raise HTTPException(status_code=400, detail="Summary cannot be empty")

        from promaia.storage.postgres_db import pg_connect
        with pg_connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "UPDATE brain.audio_session_reviews SET summary = %s WHERE id = %s",
                    (new_summary, review_id)
                )
        return {"status": "ok"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update review {review_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))



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
        from promaia.storage.postgres_db import get_postgres_db
        db = get_postgres_db()
        row = db.fetch_one(
            """
            SELECT content FROM brain.conversations
            WHERE role = 'assistant'
            ORDER BY created_at DESC LIMIT 1
            """
        )
        if row:
            content = row["content"] or ""
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
        **_base_context(request, "projects"),
        "projects": projects,
    })


@router.get("/email", response_class=HTMLResponse)
async def email_page(request: Request):
    emails = []
    stats = {"total": 0, "unread": 0, "today": 0}
    email_account = "zachary4rivers@gmail.com"

    try:
        from promaia.storage.postgres_db import get_postgres_db
        db = get_postgres_db()

        # Stats — email_date is RFC 2822 text, use synced_time for "today"
        stat_row = db.fetch_one(
            """
            SELECT
                COUNT(*) as total,
                COUNT(*) FILTER (WHERE is_unread) as unread,
                COUNT(*) FILTER (WHERE synced_time::date = CURRENT_DATE) as today
            FROM gmail_content
            """
        )
        if stat_row:
            stats = {
                "total": stat_row["total"],
                "unread": stat_row["unread"],
                "today": stat_row["today"],
            }

        # Recent emails — order by created_time parsed as timestamp
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
    """Return count of unrouted events for dashboard badge."""
    try:
        from promaia.storage.postgres_db import get_postgres_db
        db = get_postgres_db()
        row = db.fetch_one(
            """
            SELECT COUNT(*) as count
            FROM brain.events
            WHERE urgency IS NOT NULL
              AND routed_at IS NULL
              AND (held_until IS NULL OR held_until <= NOW())
            """
        )
        return {"unread": row["count"] if row else 0}
    except Exception as e:
        logger.warning(f"Notification count unavailable: {e}")
        return {"unread": 0}


@router.get("/api/scheduler/health")
async def scheduler_health():
    """Return scheduler heartbeat status for dashboard health indicator."""
    try:
        from promaia.storage.postgres_db import get_postgres_db
        db = get_postgres_db()
        row = db.fetch_one(
            """
            SELECT created_at, payload
            FROM brain.events
            WHERE source = 'heartbeat' AND type = 'scheduler_heartbeat'
            ORDER BY created_at DESC
            LIMIT 1
            """
        )
        if row:
            created = row["created_at"]
            now = datetime.now(created.tzinfo) if created.tzinfo else datetime.now(timezone.utc)
            minutes_ago = (now - created).total_seconds() / 60
            return {
                "status": "online" if minutes_ago < 10 else "stale",
                "last_seen_minutes": round(minutes_ago, 1),
                "last_seen": created.isoformat(),
            }
        return {"status": "unknown", "last_seen_minutes": None}
    except Exception as e:
        logger.warning(f"Scheduler health check failed: {e}")
        return {"status": "error"}


@router.post("/api/notifications/read")
async def notifications_mark_read():
    """Mark all unrouted events as read via dashboard channel."""
    try:
        from promaia.storage.postgres_db import get_postgres_db
        db = get_postgres_db()
        count = db.execute(
            """
            UPDATE brain.events
            SET routed_at = NOW(), channel = 'dashboard'
            WHERE urgency IS NOT NULL
              AND routed_at IS NULL
              AND (held_until IS NULL OR held_until <= NOW())
            """
        )
        return {"status": "ok", "marked": count}
    except Exception as e:
        logger.warning(f"Mark read failed: {e}")
        return {"status": "error", "marked": 0}
