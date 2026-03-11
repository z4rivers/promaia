import logging
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)

async def get_calendar_context() -> str:
    """Fetches upcoming calendar events and returns a formatted string."""
    system_ctx = ""
    try:
        from promaia.gcal.google_calendar import get_calendar_manager
        mgr = get_calendar_manager()
        if mgr.authenticate():
            now_dt = datetime.now(timezone.utc)
            time_max = now_dt + timedelta(days=3)
            
            all_events = []
            calendars = mgr.service.calendarList().list().execute().get("items", [])
            for cal in calendars:
                res = mgr.service.events().list(
                    calendarId=cal["id"],
                    timeMin=now_dt.isoformat().replace("+00:00", "Z"),
                    timeMax=time_max.isoformat().replace("+00:00", "Z"),
                    singleEvents=True,
                    orderBy="startTime",
                    maxResults=5,
                ).execute()
                for ev in res.get("items", []):
                    start = ev.get("start", {})
                    dt_str = start.get("dateTime") or start.get("date", "")
                    all_events.append({"summary": ev.get("summary", "(no title)"), "time": dt_str, "sort_key": dt_str})
                    
            if all_events:
                all_events.sort(key=lambda e: e["sort_key"])
                evt_txt = "\n".join(f"- {e['time']}: {e['summary']}" for e in all_events[:10])
                system_ctx += f"UPCOMING CALENDAR EVENTS:\n{evt_txt}\n\n"
    except Exception as e:
        logger.warning(f"Calendar fetch failed for Live API context: {e}")
    
    return system_ctx

async def get_muninn_context() -> str:
    """Fetches relevant context from MuninnDB and returns a formatted string."""
    system_ctx = ""
    try:
        from promaia.brain.muninn import get_muninn
        muninn = await get_muninn()
        if muninn:
            # Token budget: Limit to 8 items, 200 chars each
            res = await muninn.activate(["Zack's active projects", "Zack's profile preferences", "recent priorities"], max_results=8)
            activations = res.get("activations", [])
            if activations:
                mem_text = "\n".join(f"- {a['content'][:200]}..." if len(a['content']) > 200 else f"- {a['content']}" for a in activations)
                system_ctx += f"[CURRENT KNOWLEDGE]\n{mem_text}\n\n"
                logger.info("Live API session populated with compressed MuninnDB context.")
    except Exception as e:
        logger.warning(f"Failed to fetch MuninnDB context: {e}")
        
    return system_ctx
