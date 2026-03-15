# Brain MCP Daemon — Design Spec

## Problem
The brain MCP server runs as a stdio subprocess of Claude Code. When the Claude session ends, the brain dies. This means:
- Dashboard shows "brain disconnected" between sessions
- Maiachat can't access brain tools without an active Claude session
- Every new Claude session spawns a fresh MCP process (no continuity)
- Zack has to think about whether the brain is running — multiple times daily

## Solution
Convert the brain MCP server from stdio transport to Streamable HTTP transport. It becomes an always-on daemon that any client connects to via URL + bearer token.

## Architecture

### Transport
- Streamable HTTP (MCP SDK v1.26.0 `StreamableHTTPSessionManager`)
- Default bind: `127.0.0.1:8751`
- Configurable via `BRAIN_MCP_HOST` and `BRAIN_MCP_PORT` env vars

### Multi-Session Support
Multiple clients connect simultaneously (Claude Code, maiachat, dashboard). The SDK's `StreamableHTTPSessionManager` handles this:
- Creates a new `StreamableHTTPServerTransport` per client session
- Routes requests to the correct transport via `Mcp-Session-Id` header
- Manages session lifecycle and cleanup

### Authentication
- Bearer token required on `/mcp` endpoint
- `/health` endpoint is unauthenticated (dashboard needs to poll it freely)
- Token in `.env` as `BRAIN_MCP_TOKEN`
- Auto-generated on first run if not present
- Lightweight Starlette middleware checks `Authorization: Bearer <token>` — not the SDK's full OAuth stack

### Hosting
Standalone Starlette app on port 8751 (separate from the web server on 8000):
```python
from starlette.applications import Starlette
from starlette.routing import Route, Mount

app = Starlette(
    routes=[
        Route("/health", health_endpoint),
        Mount("/mcp", app=auth_middleware(session_manager.handle_request)),
    ],
    lifespan=lifespan,  # manages session_manager lifecycle
)
```
Served by uvicorn as a managed subprocess.

### Startup Integration
Added to `scripts/manager.py` as a `ManagedProcess` alongside web server, scheduler, and Telegram bot. `python -m promaia dev` starts all five services. Also runnable standalone: `python -m promaia.brain.mcp_server`.

### Dashboard Integration
- Web server polls brain daemon health: `GET http://localhost:8751/health`
- Replaces the current heartbeat push model (brain→web server)
- Dashboard JS updated to poll a proxy endpoint on the web server (avoids CORS), which internally fetches from the brain daemon
- Old heartbeat endpoints (`POST/GET /api/brain/heartbeat`) deprecated

### Claude Code Registration
```bash
claude mcp add brain --transport http --header "Authorization: Bearer $BRAIN_MCP_TOKEN" http://localhost:8751/mcp
```

### Cleanup
- Remove `SESSION_ID` globals from `mcp_server.py` and `core_context.py`
- Remove `_heartbeat_loop()` and `_heartbeat_running` from `mcp_server.py`
- Deprecate `POST/GET /api/brain/heartbeat` in `promaia/web/routers/brain.py`

## What Changes

| Component | Before | After |
|-----------|--------|-------|
| Transport | stdio (session-bound) | Streamable HTTP (daemon) |
| Lifecycle | Dies with Claude session | Runs with `promaia dev` |
| Clients | Claude Code only | Claude Code + maiachat + dashboard |
| Sessions | Single | Multi-session via SessionManager |
| Heartbeat | Brain pushes to web server | Web server pulls from brain |
| Auth | None (stdio pipe) | Bearer token on /mcp |
| Entry point | `stdio_server()` | Starlette + uvicorn on port 8751 |

## What Stays the Same
- All 17 tools (briefing, capture, search, recall, context, update_context, actions, profile, update_profile, onboard, pc_scan, gmail_scan, gmail_query, activate, timeline, brain_costs, ide_activity_broadcast)
- All handler code in `promaia/brain/mcp/handlers/`
- Tool registry and dispatch logic
- The `Server("zbrain-brain")` instance and its decorators

## Files to Modify
- `promaia/brain/mcp_server.py` — replace stdio entry point with Starlette HTTP app, add bearer auth middleware, add `/health` endpoint, remove heartbeat loop
- `scripts/manager.py` — add brain daemon as a managed subprocess
- `promaia/web/routers/dashboard.py` — add `/api/brain/health` proxy that polls brain daemon
- `promaia/web/templates/dashboard.html` — update JS heartbeat poller to use new proxy endpoint
- `promaia/web/routers/brain.py` — deprecate old heartbeat endpoints
- `.env` — add `BRAIN_MCP_TOKEN`, `BRAIN_MCP_PORT`

### Auto-Start on Boot
Windows Task Scheduler task runs `python -m promaia dev` on user login. All services (brain daemon, web server, scheduler, Telegram bot) start automatically. No manual intervention needed.

## Success Criteria
1. `python -m promaia dev` starts web + scheduler + telegram + brain daemon
2. Dashboard shows "brain connected" without any Claude session active
3. Claude Code connects via HTTP URL and all 17 tools work
4. Maiachat can query brain tools via the same HTTP endpoint
5. Closing a Claude session does NOT disconnect the brain
6. Bearer token rejects unauthorized requests
7. Multiple clients connected simultaneously (Claude + maiachat)
