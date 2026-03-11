import logging
import os
import mimetypes
from urllib.parse import unquote

from dotenv import load_dotenv

# Load environment variables BEFORE importing routers (they read env vars at module level)
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
dotenv_path = os.path.join(PROJECT_ROOT, '.env')
load_dotenv(dotenv_path=dotenv_path)

from fastapi import FastAPI, Form, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from promaia.web.auth import (
    COOKIE_NAME,
    COOKIE_MAX_AGE,
    DashboardAuthMiddleware,
    create_session_cookie,
    is_auth_enabled,
    verify_credentials,
)
from promaia.web.config import get_config
from promaia.web.routers import brain as brain_router
from promaia.web.routers import chat as chat_router
from promaia.web.routers import mcp as mcp_router
from promaia.web.routers import capture as capture_router
from promaia.web.routers import dashboard as dashboard_router

import uvicorn
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)

config = get_config()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    from promaia.brain.heartbeat import start_heartbeat, stop_heartbeat
    try:
        start_heartbeat(interval_minutes=15)
    except Exception as e:
        logger.error(f"Failed to start Subconscious heartbeat: {e}")
    yield
    # Shutdown
    try:
        stop_heartbeat()
    except Exception as e:
        logger.error(f"Failed to stop Subconscious heartbeat: {e}")

app = FastAPI(
    title="Promaia Web API",
    description="API + dashboard for the Promaia personal AI brain.",
    version="0.2.0",
    lifespan=lifespan,
)


# HTTPS redirect middleware (production only — Railway terminates SSL at edge)
if os.environ.get("PYTHON_ENV") == "production":
    from starlette.middleware.base import BaseHTTPMiddleware
    from starlette.responses import RedirectResponse as StarletteRedirect

    class HTTPSRedirectMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request, call_next):
            # Only redirect if x-forwarded-proto is explicitly present and "http".
            # Railway's internal health checks don't send this header — don't redirect those.
            forwarded_proto = request.headers.get("x-forwarded-proto")
            if forwarded_proto == "http":
                url = str(request.url).replace("http://", "https://", 1)
                return StarletteRedirect(url, status_code=301)
            response = await call_next(request)
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
            return response

    app.add_middleware(HTTPSRedirectMiddleware)

# Cross-Origin Isolation middleware (Required for ONNX threaded WASM / SharedArrayBuffer)
@app.middleware("http")
async def add_cross_origin_isolation_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
    response.headers["Cross-Origin-Embedder-Policy"] = "require-corp"
    return response

# Auth middleware (must be added BEFORE CORS so login redirects work)
app.add_middleware(DashboardAuthMiddleware)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=config["cors_origins"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files and MIME Type Polyfills for WASM/MJS
mimetypes.add_type("application/javascript", ".js")
mimetypes.add_type("application/javascript", ".mjs")
mimetypes.add_type("application/wasm", ".wasm")

_web_dir = os.path.dirname(os.path.abspath(__file__))
_static_dir = os.path.join(_web_dir, "static")
_templates_dir = os.path.join(_web_dir, "templates")
if os.path.isdir(_static_dir):
    app.mount("/static", StaticFiles(directory=_static_dir), name="static")

_templates = Jinja2Templates(directory=_templates_dir)


# --- Login / Logout routes ---

@app.get("/login", response_class=HTMLResponse, tags=["Auth"])
async def login_page(request: Request, next: str = "/", error: str = ""):
    if not is_auth_enabled():
        return RedirectResponse(url="/", status_code=303)
    return _templates.TemplateResponse("login.html", {
        "request": request,
        "next_url": next,
        "error": error,
    })


@app.post("/login", response_class=HTMLResponse, tags=["Auth"])
async def login_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    next: str = Form("/"),
):
    if not is_auth_enabled():
        return RedirectResponse(url="/", status_code=303)

    if verify_credentials(username, password):
        redirect_to = unquote(next) if next else "/"
        response = RedirectResponse(url=redirect_to, status_code=303)
        response.set_cookie(
            key=COOKIE_NAME,
            value=create_session_cookie(username),
            max_age=COOKIE_MAX_AGE,
            httponly=True,
            samesite="lax",
            secure=os.environ.get("PYTHON_ENV") == "production",
        )
        logger.info(f"Login successful for user '{username}'")
        return response

    logger.warning(f"Failed login attempt for user '{username}'")
    return _templates.TemplateResponse("login.html", {
        "request": request,
        "next_url": next,
        "error": "Invalid username or password.",
    })


@app.get("/logout", tags=["Auth"])
async def logout():
    response = RedirectResponse(url="/login", status_code=303)
    response.delete_cookie(key=COOKIE_NAME)
    return response


# Include routers
app.include_router(brain_router.router, prefix="/api/brain", tags=["Brain"])
app.include_router(chat_router.router, prefix="/api/chat", tags=["Chat"])
app.include_router(mcp_router.router, prefix="/api", tags=["MCP"])
app.include_router(capture_router.router, prefix="/api/capture", tags=["Capture"])
app.include_router(dashboard_router.router, tags=["Dashboard"])


# Telegram webhook route (only when TELEGRAM_WEBHOOK_URL is configured)
if config["telegram_webhook_url"]:
    try:
        from promaia.telegram.bot import setup_webhook_route
        setup_webhook_route(app)
        logger.info("Telegram webhook route registered at /telegram/webhook")
    except Exception as e:
        logger.warning(f"Could not register Telegram webhook route: {e}")


@app.get("/api/health", tags=["Health"])
async def health_check():
    return {"status": "healthy", "auth": "enabled" if is_auth_enabled() else "disabled"}


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    host = os.getenv("HOST", "0.0.0.0")
    uvicorn.run(app, host=host, port=port)