"""
Dashboard router — serves the Promaia web dashboard.

Wire into main.py:
    from fastapi.staticfiles import StaticFiles
    from promaia.web.routers import dashboard as dashboard_router
    app.mount("/static", StaticFiles(directory=os.path.join(os.path.dirname(__file__), "static")), name="static")
    app.include_router(dashboard_router.router)
"""

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from datetime import datetime
import os

router = APIRouter(tags=["dashboard"])

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


@router.get("/", response_class=HTMLResponse)
@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request, skin: str = None):
    """Render the main dashboard."""
    # Resolve skin
    if skin not in VALID_SKINS:
        skin = DEFAULT_SKIN

    # Time-aware greeting
    hour = datetime.now().hour
    if hour < 12:
        greeting = "Good morning"
    elif hour < 17:
        greeting = "Good afternoon"
    else:
        greeting = "Good evening"

    # Date
    now = datetime.now()
    date_str = _format_day(now)

    # TODO: Wire to real brain data via brain.recall / brain.actions
    context = {
        "request": request,
        "skin": skin,
        "valid_skins": VALID_SKINS,
        "greeting": greeting,
        "date_str": date_str,
        "user_name": "Zack",
        "brain_status": {"memories": 14, "actions": 3, "contexts": 2},
        "actions": [
            {"text": "Review dashboard skins", "domain": "promaia", "status": "active"},
            {"text": "Set up Gmail ingest", "domain": "promaia", "status": "pending"},
        ],
        "projects": [
            {"name": "Promaia Brain", "status": "active", "detail": "Dashboard build in progress"},
            {"name": "Heatpup", "status": "resting", "detail": "Last touched 2 weeks ago"},
        ],
        "recent_memories": [
            {
                "content": "Dashboard is the primary display layer, not Notion",
                "domain": "promaia",
                "created_at": "today",
            },
            {
                "content": "6-skin design system approved: 3 traditional + 3 young",
                "domain": "promaia",
                "created_at": "today",
            },
            {
                "content": "MCP router needs 3 fixes to wire in",
                "domain": "promaia",
                "created_at": "yesterday",
            },
        ],
    }

    return templates.TemplateResponse("dashboard.html", context)
