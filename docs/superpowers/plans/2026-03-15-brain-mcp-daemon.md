# Brain MCP Daemon Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convert the brain MCP server from stdio (session-bound) to Streamable HTTP (always-on daemon) so the brain stays alive between Claude sessions and supports multiple clients.

**Architecture:** Replace the stdio entry point in `mcp_server.py` with a Starlette ASGI app serving the MCP protocol over Streamable HTTP on port 8751. The MCP SDK's `StreamableHTTPSessionManager` (from `mcp.server.streamable_http_manager`) handles multi-client session routing. Bearer token auth protects `/mcp`, while `/health` stays open for dashboard polling. The manager process (`scripts/manager.py`) adds the daemon as a managed subprocess.

**Tech Stack:** Python 3.14, MCP SDK 1.26.0 (`StreamableHTTPSessionManager`), Starlette (already installed via FastAPI), uvicorn, httpx (already installed)

---

## Research Summary

### MCP SDK Streamable HTTP API (verified against installed v1.26.0)

**Module:** `mcp.server.streamable_http_manager`

**Class:** `StreamableHTTPSessionManager`
```python
StreamableHTTPSessionManager(
    app: MCPServer,           # The Server("zbrain-brain") instance
    event_store: EventStore | None = None,
    json_response: bool = False,
    stateless: bool = False,
    security_settings: TransportSecuritySettings | None = None,
    retry_interval: int | None = None,
)
```

**Lifecycle:** Must be used via `async with session_manager.run(): yield` inside a Starlette lifespan context manager. Creates an anyio task group that manages all session lifecycles.

**ASGI handler:** `session_manager.handle_request` is an ASGI callable (`scope, receive, send`). Mount it on a Starlette route.

**Session management:** Stateful mode (default) — creates a new `StreamableHTTPServerTransport` per client, tracks via `Mcp-Session-Id` header. Old sessions cleaned up automatically on crash or disconnect.

**Key import:**
```python
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from mcp.server.lowlevel.server import Server as MCPServer
```

Note: The `Server` class used in `mcp_server.py` is `mcp.server.Server` which re-exports `mcp.server.lowlevel.server.Server`. The `StreamableHTTPSessionManager` expects this same type — no adapter needed.

### Current Architecture (what we're changing)

**`promaia/brain/mcp_server.py` (800 lines):**
- Lines 48-54: Imports `Server` from `mcp.server` and `stdio_server` from `mcp.server.stdio`
- Line 81: `server = Server("zbrain-brain")` — THE server instance (stays)
- Line 82: `SESSION_ID = str(uuid.uuid4())` — REMOVE (transport manages sessions now)
- Lines 84: Imports from `core_context` including `get_db`, `get_vector_mgr`
- Lines 91-613: Tool registry (`@server.list_tools()`) — STAYS UNCHANGED
- Lines 620-669: Tool dispatcher (`@server.call_tool()`) — STAYS UNCHANGED
- Lines 678-683: Handler imports — STAYS UNCHANGED
- Lines 688-704: `_heartbeat_running` + `_heartbeat_loop()` — REMOVE
- Lines 710-728: `async def main()` — REPLACE with Starlette HTTP app
- Lines 731-793: `run_selftest()` + `if __name__` — UPDATE entry point

**`promaia/brain/mcp/core_context.py` (25 lines):**
- Line 6: `SESSION_ID = str(uuid.uuid4())` — REPURPOSE to stable daemon ID (5 handler files import it)

**Handler files that import SESSION_ID (DO NOT MODIFY — they keep working):**
- `promaia/brain/mcp/handlers/capture_ops.py:21,43` — passes SESSION_ID to `capture_memory(session_id=...)`
- `promaia/brain/mcp/handlers/context_ops.py:22,194,202,311` — uses SESSION_ID in event logging and briefing queries
- `promaia/brain/mcp/handlers/profile_ops.py:21,188,384` — uses SESSION_ID in profile update events
- `promaia/brain/mcp/handlers/metrics_ops.py:21` — imports SESSION_ID
- `promaia/brain/mcp/handlers/muninn_ops.py:21` — imports SESSION_ID

All 5 files do `from promaia.brain.mcp.core_context import SESSION_ID, get_db, get_vector_mgr, get_muninn_client`. By keeping SESSION_ID as a stable string in core_context.py, all handlers continue to work unchanged.

**`scripts/manager.py` (275 lines):**
- Line 227-229: Process list — ADD brain daemon
- Lines 132-136: `target_signatures` for cleanup — ADD brain daemon signature

**`promaia/web/routers/dashboard.py` (510 lines):**
- ADD: `/api/brain/health` proxy endpoint that polls `localhost:8751/health`

**`promaia/web/routers/brain.py` (794 lines):**
- Lines 34-69: Heartbeat tracking + endpoints — DEPRECATE (add deprecation response)

**`promaia/web/templates/dashboard.html`:**
- Lines 679-709: JS heartbeat poller — UPDATE to poll new `/api/brain/health` proxy

**`.env`:**
- ADD: `BRAIN_MCP_TOKEN` (auto-generated if missing)
- ADD: `BRAIN_MCP_PORT=8751`

---

## Chunk 1: Core Daemon (mcp_server.py + core_context.py)

### Task 1: Add BRAIN_MCP_TOKEN to .env

**Files:**
- Modify: `.env` (gitignored — local only, no commit)
- Modify: `.env.example` or `.env.template` (if exists — to document new vars)

- [ ] **Step 1: Add brain daemon environment variables to .env**

Append to end of `.env`:
```
# Brain MCP Daemon (Streamable HTTP)
BRAIN_MCP_HOST=127.0.0.1
BRAIN_MCP_PORT=8751
BRAIN_MCP_TOKEN=
```

The token is left blank intentionally — the server will auto-generate one on first run and write it back to `.env` via `python-dotenv`'s `set_key()`.

**No commit** — `.env` is in `.gitignore` (contains secrets).

---

### Task 2: Repurpose SESSION_ID in core_context.py

**Files:**
- Modify: `promaia/brain/mcp/core_context.py`

**Why repurpose, not remove:** 5 handler files import `SESSION_ID` from `core_context` and use it for event logging, memory capture, and briefing queries. Removing it would cause `ImportError` on every tool call. The MCP transport now manages its own per-client session IDs, but the handlers need a stable process-level identifier for their DB operations. Changing it from a random UUID to a fixed `"brain-daemon"` string makes event logs clearer and keeps all handlers working unchanged.

- [ ] **Step 1: Replace random UUID with stable daemon identifier**

Before:
```python
import uuid
from promaia.storage.db_factory import get_db as _get_db_factory
from promaia.storage.vector_db import VectorDBManager
from promaia.brain.muninn import get_muninn

SESSION_ID = str(uuid.uuid4())

_db = None
_vector_manager = None
```

After:
```python
from promaia.storage.db_factory import get_db as _get_db_factory
from promaia.storage.vector_db import VectorDBManager
from promaia.brain.muninn import get_muninn

# Stable process-level identifier for event logging and memory capture.
# Previously a random UUID per stdio session — now fixed because the daemon
# is always-on. MCP transport manages per-client session IDs separately.
SESSION_ID = "brain-daemon"

_db = None
_vector_manager = None
```

- [ ] **Step 2: Verify handler imports still resolve**

Run: `python -c "from promaia.brain.mcp.core_context import SESSION_ID; print(f'SESSION_ID={SESSION_ID}')"`
Expected: `SESSION_ID=brain-daemon`

- [ ] **Step 3: Commit**

```bash
git add promaia/brain/mcp/core_context.py
git commit -m "refactor: repurpose SESSION_ID to stable daemon identifier

Changed from random UUID (per stdio session) to fixed 'brain-daemon' string.
5 handler files import this for event logging — all continue unchanged.
MCP transport manages per-client sessions separately."
```

---

### Task 3: Convert mcp_server.py to Streamable HTTP daemon

This is the core change. The tool registry (lines 91-613), tool dispatcher (lines 620-669), and handler imports (lines 678-683) stay **exactly the same**. We're only changing: imports, SESSION_ID removal, heartbeat removal, and the entry point.

**Files:**
- Modify: `promaia/brain/mcp_server.py`

- [ ] **Step 1: Update imports**

Replace the current import block (lines 31-36 and 48-54):

Old:
```python
import asyncio
import json
import logging
import os
import sys
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv

# Load .env from the project root (walk up from this file to find it)
_project_root = Path(__file__).resolve().parents[2]
load_dotenv(_project_root / ".env")

import numpy as np

try:
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp.types import Tool, TextContent
except ImportError:
    print("ERROR: mcp package not installed. Install with: pip install 'mcp>=1.26.0'", file=sys.stderr)
    sys.exit(1)
```

New:
```python
import asyncio
import contextlib
import json
import logging
import os
import secrets
import sys
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv, set_key

# Load .env from the project root (walk up from this file to find it)
_project_root = Path(__file__).resolve().parents[2]
_env_path = _project_root / ".env"
load_dotenv(_env_path)

import numpy as np

try:
    from mcp.server import Server
    from mcp.types import Tool, TextContent
except ImportError:
    print("ERROR: mcp package not installed. Install with: pip install 'mcp>=1.26.0'", file=sys.stderr)
    sys.exit(1)

from mcp.server.streamable_http_manager import StreamableHTTPSessionManager

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Mount, Route
from starlette.types import Receive, Scope, Send
```

Note: `stdio_server` import is removed. `uuid` is removed (was only for SESSION_ID). New imports added: `contextlib`, `secrets`, `AsyncIterator`, `set_key`, `StreamableHTTPSessionManager`, and Starlette components.

- [ ] **Step 2: Remove SESSION_ID global**

Delete line 82:
```python
SESSION_ID = str(uuid.uuid4())
```

- [ ] **Step 3: Remove heartbeat loop**

Delete the entire heartbeat section (lines 688-704):
```python
_heartbeat_running = False

async def _heartbeat_loop():
    """POST to the web server every 30 seconds so the dashboard shows ..."""
    global _heartbeat_running
    _heartbeat_running = True
    import httpx
    url = "http://localhost:8000/api/brain/heartbeat"
    payload = {"session_id": SESSION_ID[:8], "agent_name": "ide-mcp-stdio"}

    while _heartbeat_running:
        try:
            async with httpx.AsyncClient() as client:
                await client.post(url, json=payload, timeout=3.0)
        except Exception:
            pass  # Web server might not be up yet -- that's fine
        await asyncio.sleep(30)
```

- [ ] **Step 4: Replace entry point with Starlette HTTP app**

Replace the entire entry point section (from `async def main()` through end of file) with:

```python
# ---------------------------------------------------------------------------
# Auth + Health
# ---------------------------------------------------------------------------
def _get_token() -> str:
    """Read BRAIN_MCP_TOKEN from env, auto-generate if missing."""
    token = os.environ.get("BRAIN_MCP_TOKEN", "").strip()
    if not token:
        token = secrets.token_urlsafe(32)
        # Persist to .env so it survives restarts
        try:
            set_key(str(_env_path), "BRAIN_MCP_TOKEN", token)
        except Exception:
            pass  # .env might not be writable — log and continue
        os.environ["BRAIN_MCP_TOKEN"] = token
        logger.info("Auto-generated BRAIN_MCP_TOKEN (saved to .env)")
    return token


async def _health_endpoint(request: Request) -> JSONResponse:
    """Unauthenticated health check for dashboard polling."""
    return JSONResponse({"status": "ok", "service": "zbrain-brain"})


def _bearer_auth_middleware(app):
    """Wrap an ASGI app with bearer token verification."""
    async def middleware(scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http":
            request = Request(scope, receive)
            auth_header = request.headers.get("authorization", "")
            expected = f"Bearer {_get_token()}"
            if auth_header != expected:
                response = Response("Unauthorized", status_code=401)
                await response(scope, receive, send)
                return
        await app(scope, receive, send)
    return middleware


# ---------------------------------------------------------------------------
# Starlette app factory
# ---------------------------------------------------------------------------
def create_app() -> Starlette:
    """Build the Starlette ASGI app with MCP session manager."""
    session_manager = StreamableHTTPSessionManager(app=server)

    @contextlib.asynccontextmanager
    async def lifespan(app: Starlette) -> AsyncIterator[None]:
        async with session_manager.run():
            logger.info("Brain MCP daemon ready")
            yield

    app = Starlette(
        routes=[
            Route("/health", _health_endpoint),
            Mount("/mcp", app=_bearer_auth_middleware(session_manager.handle_request)),
        ],
        lifespan=lifespan,
    )
    return app


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def run_selftest():
    """Run diagnostics to verify MCP server dependencies before launching."""
    print("Running zBrain MCP Server Self-Test...\n")
    success = True

    # 1. Database Check
    try:
        from promaia.storage.db_factory import get_db
        db = get_db()
        db.execute("SELECT 1")
        print("  Database Connection: OK")
    except Exception as e:
        print(f"  Database Connection: FAILED ({e})")
        success = False

    # 2. Vector DB Check
    try:
        from promaia.storage.vector_db import VectorDBManager
        mgr = VectorDBManager()
        print("  Vector DB Manager: OK")
    except Exception as e:
        print(f"  Vector DB Manager: FAILED ({e})")
        success = False

    # 3. MuninnDB Check
    try:
        from promaia.brain.muninn import get_muninn
        import asyncio
        m = asyncio.run(get_muninn())
        if m is not None:
            print("  MuninnDB Access: OK")
        else:
            print("  MuninnDB Access: FAILED (Returned None - Server may be down)")
            success = False
    except Exception as e:
        print(f"  MuninnDB Access: FAILED ({e})")
        success = False

    # 4. LLM API Keys
    import os
    keys = {"ANTHROPIC": os.getenv("ANTHROPIC_API_KEY"), "OPENAI": os.getenv("OPENAI_API_KEY"), "GEMINI": os.getenv("GOOGLE_API_KEY")}
    found = [k for k, v in keys.items() if v]
    if found:
        print(f"  LLM API Keys: OK ({', '.join(found)})")
    else:
        print("  LLM API Keys: FAILED (No core generation keys found)")
        success = False

    # 5. Bearer token check
    token = _get_token()
    print(f"  Bearer Token: OK (first 8 chars: {token[:8]}...)")

    print(f"\nSelf-Test {'PASSED' if success else 'FAILED'}")
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        run_selftest()
    else:
        import uvicorn

        host = os.environ.get("BRAIN_MCP_HOST", "127.0.0.1")
        port = int(os.environ.get("BRAIN_MCP_PORT", "8751"))
        log_level = os.environ.get("BRAIN_LOG_LEVEL", "info").lower()

        logger.info(f"Starting zBrain MCP daemon on {host}:{port}")
        try:
            uvicorn.run(
                create_app(),
                host=host,
                port=port,
                log_level=log_level,
            )
        except KeyboardInterrupt:
            logger.info("Brain MCP daemon stopped")
        except Exception as e:
            logger.error(f"Fatal error: {e}", exc_info=True)
            sys.exit(1)
        finally:
            try:
                from promaia.storage.db_factory import get_db
                get_db().close_pool()
            except Exception as e:
                logger.error(f"Failed to close database connection pool: {e}")
```

- [ ] **Step 5: Update the module docstring**

Replace lines 1-5 of the docstring. Fix the tool count (actual: 17, docstring says 16) and update transport description:

Old:
```
Brain MCP Server — 16 tools for zBrain.

Exposes Claude's persistent memory system as MCP tools over stdio.
```

New:
```
Brain MCP Server — 17 tools for zBrain.

Exposes Claude's persistent memory system as MCP tools over Streamable HTTP.
Runs as an always-on daemon (default: 127.0.0.1:8751) with bearer token auth.
```

- [ ] **Step 6: Verify the file is syntactically valid**

Run: `python -c "import ast; ast.parse(open('promaia/brain/mcp_server.py').read()); print('Syntax OK')"`
Expected: `Syntax OK`

- [ ] **Step 7: Run selftest to verify dependencies**

Run: `python -m promaia.brain.mcp_server --selftest`
Expected: All checks pass (DB, Vector, MuninnDB optional, LLM keys, Bearer token)

- [ ] **Step 8: Commit**

```bash
git add promaia/brain/mcp_server.py
git commit -m "feat(brain): convert MCP server from stdio to Streamable HTTP daemon

Replace stdio_server() entry point with Starlette + StreamableHTTPSessionManager.
Bearer token auth on /mcp, unauthenticated /health endpoint.
Auto-generates BRAIN_MCP_TOKEN on first run. Default port 8751.
All 17 tools and handler code unchanged."
```

---

## Chunk 2: Manager Integration + Dashboard Wiring

### Task 4: Add brain daemon to manager.py

**Files:**
- Modify: `scripts/manager.py`

- [ ] **Step 1: Add brain daemon signature to cleanup_existing_processes**

In `cleanup_existing_processes()`, add `"promaia.brain.mcp_server"` to `target_signatures` list (line 132-136):

Before:
```python
    target_signatures = [
        "uvicorn promaia.web.main:app",
        "promaia.telegram_cli",
        "promaia.agents.scheduler_cli"
    ]
```

After:
```python
    target_signatures = [
        "uvicorn promaia.web.main:app",
        "promaia.telegram_cli",
        "promaia.agents.scheduler_cli",
        "promaia.brain.mcp_server",
    ]
```

- [ ] **Step 2: Add brain daemon ManagedProcess to process list**

In `main()`, add the brain daemon as the FIRST process in the list (it should start before the web server so the dashboard can poll it immediately):

Before (line 227-229):
```python
        processes = [
            ManagedProcess("Web Server", [sys.executable, "-m", "uvicorn", "promaia.web.main:app", "--host", "0.0.0.0", "--port", "8000"], "WEB"),
            ManagedProcess("Agent Scheduler", [sys.executable, "-m", "promaia.agents.scheduler_cli", "start"], "SCHED")
        ]
```

After:
```python
        processes = [
            ManagedProcess("Brain Daemon", [sys.executable, "-m", "promaia.brain.mcp_server"], "BRAIN"),
            ManagedProcess("Web Server", [sys.executable, "-m", "uvicorn", "promaia.web.main:app", "--host", "0.0.0.0", "--port", "8000"], "WEB"),
            ManagedProcess("Agent Scheduler", [sys.executable, "-m", "promaia.agents.scheduler_cli", "start"], "SCHED")
        ]
```

- [ ] **Step 3: Update module docstring**

Add `- Brain MCP Daemon` to the list in the module docstring (line 5-8):

Before:
```
Supervises Promaia subprocesses:
- FastAPI Web Server (uvicorn)
- Telegram Bot
- Agent Scheduler
- MuninnDB (optional local instance)
```

After:
```
Supervises Promaia subprocesses:
- Brain MCP Daemon (Streamable HTTP)
- FastAPI Web Server (uvicorn)
- Telegram Bot
- Agent Scheduler
- MuninnDB (optional local instance)
```

- [ ] **Step 4: Commit**

```bash
git add scripts/manager.py
git commit -m "feat(manager): add brain MCP daemon as managed subprocess

Brain daemon starts first (port 8751) so dashboard can poll health
immediately. Added to cleanup_existing_processes kill list."
```

---

### Task 5: Add /api/brain/health proxy to dashboard router

The web server needs a proxy endpoint that the dashboard JS can poll (avoids CORS issues since the brain daemon is on port 8751, not 8000).

**Files:**
- Modify: `promaia/web/routers/dashboard.py`

- [ ] **Step 1: Add the health proxy endpoint**

Add this endpoint after the existing `/api/scheduler/health` endpoint (after line 501):

```python
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
```

- [ ] **Step 2: Commit**

```bash
git add promaia/web/routers/dashboard.py
git commit -m "feat(dashboard): add /api/brain/health proxy to brain daemon"
```

---

### Task 6: Update dashboard JS heartbeat poller

The dashboard template's JavaScript polls `/api/brain/heartbeat` (the old push-based model). Update it to poll `/api/brain/health` (the new pull-based proxy).

**Files:**
- Modify: `promaia/web/templates/dashboard.html`

- [ ] **Step 1: Update the checkHeartbeat function**

In `dashboard.html`, replace the `checkHeartbeat` function body (lines 679-706). The old code expected `{connected, last_seen_seconds_ago, session_id, agent_name}` from the heartbeat endpoint. The new proxy returns `{connected, status, service}`.

Old (lines 679-706):
```javascript
    function checkHeartbeat() {
        fetch('/api/brain/heartbeat')
            .then(function(r) { return r.json(); })
            .then(function(data) {
                if (data.connected) {
                    dot.className = 'brain-connection__dot brain-connection__dot--connected';
                    label.textContent = 'Brain: connected';
                    var ago = data.last_seen_seconds_ago;
                    wrapper.title = 'IDE MCP session ' + (data.session_id || '?') + ' — last ping ' + Math.round(ago) + 's ago';

                    initialGrace = false;
                    if (disconnectedSince) {
                        hideAlert(true);
                    }
                    disconnectedSince = null;
                    wasConnected = true;
                } else {
                    wrapper.title = data.last_seen_seconds_ago
                        ? 'Last seen ' + Math.round(data.last_seen_seconds_ago) + 's ago'
                        : 'No heartbeat ever received';
                    handleDisconnected(initialGrace ? 'Brain: connecting...' : 'Brain: disconnected');
                }
            })
            .catch(function() {
                wrapper.title = 'Could not reach heartbeat endpoint';
                handleDisconnected(initialGrace ? 'Brain: connecting...' : 'Brain: unreachable');
            });
    }
```

New:
```javascript
    function checkHeartbeat() {
        fetch('/api/brain/health')
            .then(function(r) { return r.json(); })
            .then(function(data) {
                if (data.connected) {
                    dot.className = 'brain-connection__dot brain-connection__dot--connected';
                    label.textContent = 'Brain: connected';
                    wrapper.title = 'Brain daemon running on port ' + (data.port || '8751');

                    initialGrace = false;
                    if (disconnectedSince) {
                        hideAlert(true);
                    }
                    disconnectedSince = null;
                    wasConnected = true;
                } else {
                    wrapper.title = 'Brain daemon unreachable';
                    handleDisconnected(initialGrace ? 'Brain: connecting...' : 'Brain: disconnected');
                }
            })
            .catch(function() {
                wrapper.title = 'Could not reach brain health endpoint';
                handleDisconnected(initialGrace ? 'Brain: connecting...' : 'Brain: unreachable');
            });
    }
```

- [ ] **Step 2: Update alert fix text**

The alert currently says "Reload IDE window to reconnect" — this no longer applies since the brain is a daemon, not an IDE subprocess. Update the HTML (line 403):

Old:
```html
        <span class="brain-alert__fix" id="brain-alert-fix">Reload IDE window to reconnect</span>
```

New:
```html
        <span class="brain-alert__fix" id="brain-alert-fix">Run: python -m promaia dev</span>
```

- [ ] **Step 3: Commit**

```bash
git add promaia/web/templates/dashboard.html
git commit -m "feat(dashboard): update brain status poller to use daemon health proxy

Polls /api/brain/health (daemon proxy) instead of /api/brain/heartbeat
(old push model). Updated alert fix text for daemon architecture."
```

---

### Task 7: Deprecate old heartbeat endpoints in brain.py

The old `POST/GET /api/brain/heartbeat` endpoints are no longer needed — the brain daemon has its own `/health` endpoint and the dashboard polls via the proxy. Mark them deprecated so existing clients get a clear signal.

**Files:**
- Modify: `promaia/web/routers/brain.py`

- [ ] **Step 1: Add deprecation responses to heartbeat endpoints**

Replace the heartbeat section (lines 34-69) with deprecated versions:

Old:
```python
_mcp_heartbeat: dict = {
    "last_seen": 0.0,
    "session_id": None,
    "agent_name": None,
}
_MCP_HEARTBEAT_TIMEOUT_SECONDS = 90


class HeartbeatRequest(BaseModel):
    session_id: str | None = None
    agent_name: str | None = None


@router.post("/heartbeat")
async def mcp_heartbeat(req: HeartbeatRequest = HeartbeatRequest()):
    """Receive a heartbeat ping from an IDE MCP server."""
    _mcp_heartbeat["last_seen"] = time.time()
    if req.session_id:
        _mcp_heartbeat["session_id"] = req.session_id
    if req.agent_name:
        _mcp_heartbeat["agent_name"] = req.agent_name
    return {"status": "ok"}


@router.get("/heartbeat")
async def mcp_heartbeat_status():
    """Return whether an MCP brain connection is alive."""
    last = _mcp_heartbeat["last_seen"]
    elapsed = time.time() - last if last > 0 else float("inf")
    connected = elapsed < _MCP_HEARTBEAT_TIMEOUT_SECONDS
    return {
        "connected": connected,
        "last_seen_seconds_ago": round(elapsed, 1) if last > 0 else None,
        "session_id": _mcp_heartbeat["session_id"],
        "agent_name": _mcp_heartbeat["agent_name"],
    }
```

New:
```python
# ---------------------------------------------------------------------------
# DEPRECATED: Old heartbeat push model — replaced by brain daemon /health
# The brain is now an always-on daemon. Dashboard polls /api/brain/health
# (proxy to daemon's /health endpoint) instead of these push-based endpoints.
# Kept temporarily for backward compatibility — will be removed in v4.0.
# ---------------------------------------------------------------------------

class HeartbeatRequest(BaseModel):
    session_id: str | None = None
    agent_name: str | None = None


@router.post("/heartbeat")
async def mcp_heartbeat(req: HeartbeatRequest = HeartbeatRequest()):
    """DEPRECATED: Brain is now an always-on daemon. This endpoint is a no-op."""
    return {"status": "deprecated", "message": "Brain is now a daemon. Use /api/brain/health instead."}


@router.get("/heartbeat")
async def mcp_heartbeat_status():
    """DEPRECATED: Use /api/brain/health instead."""
    import httpx
    port = int(os.environ.get("BRAIN_MCP_PORT", "8751"))
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"http://127.0.0.1:{port}/health", timeout=3.0)
            return {"connected": True, "deprecated": True, "message": "Use /api/brain/health"}
    except Exception:
        return {"connected": False, "deprecated": True, "message": "Use /api/brain/health"}
```

- [ ] **Step 2: Commit**

```bash
git add promaia/web/routers/brain.py
git commit -m "deprecate: old heartbeat push endpoints — brain is now a daemon

POST/GET /api/brain/heartbeat now return deprecation notices.
Dashboard uses /api/brain/health (proxy to daemon) instead."
```

---

## Chunk 3: Claude Code Registration + Smoke Test

### Task 8: Register Claude Code to use HTTP transport

After the daemon is running, Claude Code needs to be re-registered to connect via HTTP instead of stdio.

**Files:** None (CLI commands only)

- [ ] **Step 1: Remove old stdio registration**

Run: `claude mcp remove brain`

- [ ] **Step 2: Get the bearer token**

Run: `grep BRAIN_MCP_TOKEN .env`

Note the token value. If it's empty, start the daemon once (`python -m promaia.brain.mcp_server`) — it will auto-generate and save the token to `.env`.

- [ ] **Step 3: Register with HTTP transport**

Run (substituting the actual token):
```bash
claude mcp add brain --transport http --header "Authorization: Bearer <TOKEN>" http://localhost:8751/mcp
```

- [ ] **Step 4: Verify registration**

Run: `claude mcp list`
Expected: brain entry shows `http` transport with URL `http://localhost:8751/mcp`

---

### Task 9: Full integration smoke test

- [ ] **Step 1: Start the daemon standalone**

Run: `python -m promaia.brain.mcp_server`
Expected: Logs show `Brain MCP daemon ready` and `Uvicorn running on http://127.0.0.1:8751`

- [ ] **Step 2: Test health endpoint**

In a separate terminal:
```bash
curl http://localhost:8751/health
```
Expected: `{"status":"ok","service":"zbrain-brain"}`

- [ ] **Step 3: Test auth rejection**

```bash
curl -X POST http://localhost:8751/mcp -H "Content-Type: application/json" -d '{"jsonrpc":"2.0","method":"initialize","id":1}'
```
Expected: `401 Unauthorized`

- [ ] **Step 4: Test auth acceptance**

```bash
curl -X POST http://localhost:8751/mcp \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <TOKEN>" \
  -d '{"jsonrpc":"2.0","method":"initialize","id":1,"params":{"protocolVersion":"2025-03-26","capabilities":{},"clientInfo":{"name":"test","version":"0.1"}}}'
```
Expected: JSON-RPC response with server capabilities

- [ ] **Step 5: Test via promaia dev**

Stop standalone daemon, then run: `python -m promaia dev`
Expected: Logs show Brain Daemon, Web Server, Scheduler all starting. Brain on port 8751, Web on 8000.

- [ ] **Step 6: Test dashboard brain status**

Open `http://localhost:8000` in browser.
Expected: Brain status indicator shows green "Brain: connected"

- [ ] **Step 7: Test Claude Code integration**

Open a new Claude Code session with brain MCP registered.
Run `mcp__brain__briefing` — should return a normal briefing.
Close the Claude session.
Check dashboard — brain should STILL show connected (not disconnected like before).

This is the key success criterion: closing Claude no longer kills the brain.

---

## Success Criteria (from design spec)

1. `python -m promaia dev` starts web + scheduler + telegram + brain daemon
2. Dashboard shows "brain connected" without any Claude session active
3. Claude Code connects via HTTP URL and all 17 tools work
4. Maiachat can query brain tools via the same HTTP endpoint (deferred — maiachat not yet wired)
5. Closing a Claude session does NOT disconnect the brain
6. Bearer token rejects unauthorized requests
7. Multiple clients connected simultaneously (Claude + maiachat) (testable once maiachat is wired)

## Deferred (out of scope for this plan)

- **Windows Task Scheduler auto-start:** The spec mentions a Task Scheduler task that runs `python -m promaia dev` on user login. This is a deployment concern, not a code change — create separately after smoke testing.
- **Maiachat integration:** Success criteria 4 and 7 require maiachat to be wired to the HTTP endpoint. Maiachat is a separate feature — this plan ensures the daemon is ready to accept maiachat connections, but doesn't modify maiachat itself.
- **Token caching in auth middleware:** `_get_token()` reads `os.environ` on every request. Negligible cost for local daemon but could be cached if this ever sees high traffic.
