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
from promaia.web.routers import signals as signals_router
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
    
    # Pre-warm voice context cache so first voice connect is instant
    try:
        pass
        # from promaia.web.routers.brain import prewarm_voice_context
        # await prewarm_voice_context()
    except Exception as e:
        logger.warning(f"Voice context pre-warm failed (non-fatal): {e}")
    
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
# Also sets no-cache on HTML to prevent mobile browsers from serving stale pages.
@app.middleware("http")
async def add_cross_origin_isolation_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
    response.headers["Cross-Origin-Embedder-Policy"] = "require-corp"
    # Prevent mobile browsers from caching HTML pages
    content_type = response.headers.get("content-type", "")
    if "text/html" in content_type:
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
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
            samesite="strict",
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
app.include_router(signals_router.router, prefix="/api/brain/signals", tags=["Signals"])
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


@app.post("/api/shutdown", tags=["Health"])
async def graceful_shutdown():
    """Gracefully shut down the web server.
    
    Drains active background tasks, closes database connections,
    stops the heartbeat, and signals uvicorn to exit cleanly.
    Replaces the old kill_server.py sledgehammer approach.
    """
    import signal
    import asyncio

    logger.info("🛑 Graceful shutdown requested via /api/shutdown")

    # 1. Stop the heartbeat
    try:
        from promaia.brain.heartbeat import stop_heartbeat
        stop_heartbeat()
        logger.info("  ✅ Heartbeat stopped")
    except Exception as e:
        logger.warning(f"  ⚠️ Heartbeat stop failed: {e}")

    # 2. Close database connection pool
    try:
        from promaia.storage.db_factory import get_db
        get_db().close_pool()
        logger.info("  ✅ Database pool closed")
    except Exception as e:
        logger.warning(f"  ⚠️ Database pool close failed: {e}")

    # 3. Signal uvicorn to shut down after this response is sent
    async def _delayed_exit():
        await asyncio.sleep(0.5)  # Let the response flush
        logger.info("  🛑 Sending SIGTERM to self")
        os.kill(os.getpid(), signal.SIGTERM)

    asyncio.create_task(_delayed_exit())

    return {"status": "shutting_down", "message": "Server will exit in ~1 second."}


@app.get("/api/health", tags=["Health"])
async def health_check():
    health_status = {
        "status": "healthy",
        "auth": "enabled" if is_auth_enabled() else "disabled",
        "components": {}
    }
    
    # 1. Check Database
    try:
        from promaia.storage.db_factory import get_db
        db = get_db()
        db.execute("SELECT 1")
        health_status["components"]["database"] = "connected"
    except Exception as e:
        import traceback
        health_status["status"] = "degraded"
        health_status["components"]["database"] = f"error: {str(e)} - {traceback.format_exc()}"
        
    # 2. Check MCP Configuration
    try:
        from promaia.config.mcp_servers import get_mcp_manager
        mcp_manager = get_mcp_manager()
        configured_servers = len(mcp_manager.get_enabled_servers())
        health_status["components"]["mcp_config"] = f"{configured_servers} servers enabled"
    except Exception as e:
        health_status["status"] = "degraded"
        health_status["components"]["mcp_config"] = f"error: {str(e)}"

    # 3. Check MuninnDB Cognitive Memory
    try:
        from promaia.brain.muninn import get_muninn
        m = await get_muninn()
        if m is not None:
            health_status["components"]["muninn"] = "connected"
        else:
            health_status["components"]["muninn"] = "unreachable"
            health_status["status"] = "degraded"
    except Exception as e:
        health_status["status"] = "degraded"
        health_status["components"]["muninn"] = f"error: {str(e)}"

    # 4. Check Background Heartbeat
    try:
        from promaia.brain.heartbeat import is_heartbeat_running
        if is_heartbeat_running():
            health_status["components"]["heartbeat"] = "running"
        else:
            health_status["components"]["heartbeat"] = "stopped"
    except Exception as e:
        health_status["components"]["heartbeat"] = f"error: {str(e)}"

    # 5. Check Core API Keys
    try:
        keys = {
            "anthropic": os.getenv("ANTHROPIC_API_KEY"),
            "openai": os.getenv("OPENAI_API_KEY"),
            "gemini": os.getenv("GOOGLE_API_KEY")
        }
        available = [k for k, v in keys.items() if v]
        if available:
            health_status["components"]["llm_keys"] = f"available ({', '.join(available)})"
        else:
            health_status["components"]["llm_keys"] = "missing - AI generation offline!"
            health_status["status"] = "degraded"
    except Exception as e:
        health_status["components"]["llm_keys"] = f"error: {str(e)}"

    return health_status


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    host = os.getenv("HOST", "0.0.0.0")
    # Use reload=True and import string to enable Uvicorn's process manager.
    # This prevents Windows from stranding port 8000 on Ctrl+C.
    uvicorn.run("promaia.web.main:app", host=host, port=port, reload=True)