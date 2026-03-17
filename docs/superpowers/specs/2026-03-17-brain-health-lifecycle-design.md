# Brain Health Lifecycle — Design Spec

**Date:** 2026-03-17
**Status:** Review
**Problem:** The brain MCP server fails silently when misconfigured, leaving Claude Code sessions without tools and no error visible to the user. Production (zbrain.online) has the same class of problem — Turso connection drops, env vars missing, server reports "ok" when half-dead.

## Goal

Make the brain server self-aware of its own health across the full lifecycle: startup, runtime, and diagnostic. In both local dev and production (Railway/zbrain.online). No silent failures.

---

## Layer 1: Deep Health Endpoint

**File:** `promaia/brain/mcp_server.py` (modify `_health_endpoint`)

Replace the current cosmetic `/health` response with a real diagnostic.

### Checks performed

| Check | Critical? | What it validates |
|-------|-----------|-------------------|
| database | Yes | Execute `SELECT 1` against Turso/libSQL. Report backend type. Attempt `sync()` and report success/failure + elapsed time since last successful sync (tracked manually via `LibSQLDB._last_sync_time`). |
| vector_db | Yes | `VectorDBManager()` initializes without error. |
| muninn | No | `get_muninn()` returns non-None. Connection refused = degraded, not error. |
| env_vars | Yes | Required vars present: `GOOGLE_API_KEY`, `BRAIN_MCP_TOKEN`. In production: `TURSO_DATABASE_URL`, `TURSO_AUTH_TOKEN`. |
| tools | Yes | Server has >0 registered tools. |

### Response schema

```json
{
  "status": "ok | degraded | error",
  "service": "zbrain-brain",
  "environment": "production | local",
  "uptime_sec": 3421,
  "checks": {
    "database": {
      "status": "ok | error",
      "backend": "turso | sqlite",
      "sync_ok": true,
      "last_sync_age_sec": 12
    },
    "vector_db": {
      "status": "ok | error",
      "error": null
    },
    "muninn": {
      "status": "ok | unavailable",
      "reason": null
    },
    "env_vars": {
      "status": "ok | error",
      "missing": []
    },
    "tools": {
      "status": "ok | error",
      "count": 26
    }
  }
}
```

### Status logic

- `"ok"` — all critical checks pass
- `"degraded"` — all critical pass, but non-critical (MuninnDB) is down
- `"error"` — any critical check fails

### Caching

Results cached for 30 seconds. Subsequent calls within the window return the cached result. Cache key is just a timestamp — no parameterization needed.

### Environment detection

```python
def _detect_environment() -> str:
    if os.environ.get("RAILWAY_ENVIRONMENT") or os.environ.get("PYTHON_ENV") == "production":
        return "production"
    return "local"
```

---

## Layer 2: Startup Validation

**File:** `promaia/brain/mcp_server.py` (new function `validate_startup`, called from `create_app` lifespan)

Runs once during the Starlette lifespan context (before uvicorn starts accepting connections). Validates config correctness and subsystem connectivity — but does not test that the server itself is reachable from outside, since it hasn't started listening yet. Two modes based on environment.

### Common checks (both environments)

1. Database connectivity — execute a test query
2. Required env vars present
3. Bearer token is set (not auto-generated on ephemeral containers)
4. Tools registered on the server instance (assert `len(server.list_tools()) > 0`)

### Production-only checks

1. `TURSO_DATABASE_URL` and `TURSO_AUTH_TOKEN` are set
2. Embedded replica can sync — call `db.sync()` inside try/except. Track `_last_sync_time` on `LibSQLDB` (set at init and after each successful sync). Report `last_sync_age_sec` in health. Note: `libsql` Python client does not expose sync metadata natively, so we track it manually.
3. `BRAIN_MCP_TOKEN` is explicitly set (auto-generation on Railway means the token changes every deploy, breaking any config that references it)

### Local-only checks: MCP Registration Validation

Scan Claude Code MCP config files and validate they match the running server.

**Config file locations:**
- User-level: `~/.claude/.mcp.json`
- Project-level: `{_project_root}/.mcp.json`

**Validation rules:**
1. At least one config file has a `brain` entry
2. The entry uses URL transport (has `"url"` key), not stdio (`"command"` key)
3. The URL matches `http://{host}:{port}/mcp/` where host/port are from env vars or defaults
4. The `Authorization` header contains `Bearer {_get_token()}`
5. If both files have a `brain` entry, warn: "Duplicate registration — user-level takes precedence"

**On mismatch:**
- Log `WARNING` with the exact problem and the correct config
- If `BRAIN_AUTO_FIX_CONFIG=true`, overwrite the incorrect entry with the correct one
- Never block startup

### Output format

All validation results logged with the `BRAIN` prefix:

```
[BRAIN] Startup validation:
[BRAIN]   Database:        OK (turso, replica synced 2s ago)
[BRAIN]   Env vars:        OK
[BRAIN]   Bearer token:    OK (9Aps8JMH...)
[BRAIN]   Tools:           OK (26 registered)
[BRAIN]   MCP registration: OK (~/.claude/.mcp.json -> http://127.0.0.1:8751/mcp/)
[BRAIN] Status: HEALTHY
```

Or on failure:

```
[BRAIN] Startup validation:
[BRAIN]   Database:        OK (turso)
[BRAIN]   Env vars:        OK
[BRAIN]   Bearer token:    OK
[BRAIN]   Tools:           OK (26 registered)
[BRAIN]   MCP registration: MISMATCH
[BRAIN]     ~/.claude/.mcp.json has brain as stdio (command: python -m promaia.brain.mcp_server)
[BRAIN]     Expected: {"url": "http://127.0.0.1:8751/mcp/", "headers": {"Authorization": "Bearer 9Aps8JMH..."}}
[BRAIN]     Fix: Update ~/.claude/.mcp.json or set BRAIN_AUTO_FIX_CONFIG=true
[BRAIN] Status: HEALTHY (1 warning)
```

---

## Layer 3: Manager Integration

**File:** `scripts/manager.py` (modify `main()`)

### Change: Health-gated startup sequence

After starting the Brain Daemon process and before starting other services, poll the health endpoint.

```python
def _wait_for_brain_health(host="127.0.0.1", port=8751, timeout=10):
    """Poll brain /health until it responds or timeout.

    Returns the parsed health JSON on any valid response (ok, degraded, or error).
    Returns None only on timeout (brain never responded at all).
    """
    import urllib.request
    import json

    url = f"http://{host}:{port}/health"
    deadline = time.time() + timeout

    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as resp:
                return json.loads(resp.read())  # any valid response = brain is up
        except Exception:
            time.sleep(1)

    return None  # timeout — brain never responded
```

### Behavior

1. Start Brain Daemon process
2. Call `_wait_for_brain_health()` (10 second timeout)
3. If healthy: log checks summary, proceed to start other services
4. If degraded: log warning with which subsystem is down, proceed anyway
5. If error: log CRITICAL with structured check details, proceed anyway (other services shouldn't be blocked)
6. If timeout (None): log `"CRITICAL: Brain daemon did not respond on :8751 within 10s. Claude Code MCP tools will NOT work this session."`, proceed anyway

### Why not block?

The web dashboard, Telegram bot, and scheduler have value independent of the brain MCP server. Blocking them because the brain is down makes a partial failure into a total outage.

---

## Layer 4: Windows Startup Sequencing

**Files:**
- `scripts/startup.py` (new — replaces `Promaia.vbs`)
- `Promaia.vbs` in `%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\` (update to call new script)

### Problem

Current startup: `Promaia.vbs` fires `pythonw.exe -m promaia dev` and exits immediately. The manager takes several seconds to start the brain daemon (cleanup, migrations, uvicorn bind). If Claude Code launches in that window, it tries `http://127.0.0.1:8751/mcp/`, gets connection refused, and silently gives up. MCP tools are gone for the entire session.

### Design

Replace the fire-and-forget VBS with a Python startup script that:

1. Starts the manager (`promaia dev`) as a subprocess
2. Polls `http://127.0.0.1:8751/health` until it responds (reuses `_wait_for_brain_health` from Layer 3, 30-second timeout for cold boot)
3. Writes a status file at `~/.promaia/startup.status` with timestamp and result:
   ```json
   {"timestamp": "2026-03-17T03:01:45", "brain_healthy": true, "boot_time_sec": 4.2}
   ```
4. Exits (manager continues running as a detached subprocess)

### Updated VBS

```vbs
' Promaia Auto-Start — launches startup sequencer (headless)
Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = "C:\Users\Zachary Turner\dev\promaia"
WshShell.Run """C:\Python314\pythonw.exe"" scripts/startup.py", 0, False
```

### Briefing integration

The briefing tool checks `~/.promaia/startup.status` on every call. If `brain_healthy` is false, or if the file is missing (manual launch, no startup script), the briefing includes:

```
WARNING: Brain server may not have been ready when this session started.
If MCP tools are missing, restart Claude Code or run: /mcp
Boot status: [healthy | failed | unknown (no status file)]
```

If `uptime_sec` (from the health endpoint) is less than 60 and the briefing is being called for the first time this session, append the same warning — this catches the case where the server came up *after* Claude Code connected.

### Why not use Task Scheduler?

Task Scheduler supports startup triggers with delays, but:
- VBS in the Startup folder is simpler to inspect, modify, and debug
- The Python startup script gives us HTTP polling that VBS can't do
- No registry/XML complexity

---

## Layer 5: CLI Diagnostic (`promaia brain check`)

**Files:**
- `promaia/brain/health.py` (new — shared health check logic)
- `promaia/__main__.py` (add `brain` subcommand routing)

### Design

Extract the health check logic into a shared module (`health.py`) so it can be used by:
- The `/health` endpoint (Layer 1)
- The startup validator (Layer 2)
- The CLI command (Layer 4)

The CLI runs all checks without needing a running server (it checks DB, env vars, configs directly) PLUS checks if the server process is running.

### Entry point

```
python -m promaia brain check
```

Added to `promaia/__main__.py` as a fast-path like `dev` and `whisper`.

### Output

```
zBrain Health Check
===================
Environment:    local (detected)
Database:       turso (TURSO_DATABASE_URL set) .... OK
Replica sync:   last sync 4s ago .................. OK
Vector DB:      initialized ....................... OK
MuninnDB:       127.0.0.1:8108 ................... UNAVAILABLE
API Keys:       GOOGLE_API_KEY .................... OK
Bearer Token:   9Aps8JMH... (matches .env) ....... OK

MCP Registration:
  ~/.claude/.mcp.json:     brain -> http://127.0.0.1:8751/mcp/ .... OK
  promaia/.mcp.json:       brain -> (not registered) .............. OK (no duplicate)

Server Process:
  Port 8751:    LISTENING (PID 12345) ............. OK

Overall: HEALTHY (1 non-critical warning: MuninnDB unavailable)
```

### Exit codes

- `0` — healthy or degraded
- `1` — error (critical check failed)
- `2` — brain server not running

---

## File Organization

### New files

| File | Purpose |
|------|---------|
| `promaia/brain/health.py` | Shared health check logic: `run_checks()`, `check_database()`, `check_mcp_registration()`, etc. All check functions accept an optional `db` parameter — when called from the server (Layers 1/2), pass the existing singleton; when called from the CLI (Layer 5), omit it and the function creates its own connection. All check functions are async-first with a `run_checks_sync()` wrapper for CLI use. |
| `scripts/startup.py` | Windows boot sequencer — starts manager, polls brain health, writes `~/.promaia/startup.status`. Replaces fire-and-forget VBS launch. |

### Modified files

| File | Change |
|------|--------|
| `promaia/brain/mcp_server.py` | Replace `_health_endpoint` with deep check. Add `validate_startup()` to lifespan. Update `run_selftest()` to delegate to shared health module. |
| `promaia/storage/libsql_db.py` | Add `_last_sync_time: float` attribute, update on init and after successful `sync()`. Add `sync_age() -> float` method. |
| `scripts/manager.py` | Add `_wait_for_brain_health()`. Call it after Brain Daemon start, before other services. |
| `promaia/__main__.py` | Add `brain check` fast path (alongside existing `dev` and `whisper`). |
| `Promaia.vbs` (Startup folder) | Update to call `scripts/startup.py` instead of `promaia dev` directly. |

### Removed/deprecated

| Item | Reason |
|------|--------|
| `run_selftest()` in mcp_server.py | Replaced by `promaia brain check` CLI and shared health module. Keep `--selftest` flag as alias that calls the new code. |

---

## Edge Cases

1. **Railway ephemeral containers:** `BRAIN_MCP_TOKEN` must be set as a Railway env var, not auto-generated. Auto-generation creates a new token every deploy, which won't match any client config. Startup validation warns if token was auto-generated in production.

2. **Config auto-repair scope:** Only repairs `~/.claude/.mcp.json` and `{project}/.mcp.json`. Never touches other MCP server entries (kapture, gmail, etc.). Implementation: read file, parse JSON, modify only `mcpServers.brain`, write back. Create a `.bak` copy before writing. If JSON parse fails, log error and skip (don't corrupt a manually-edited file).

3. **Multiple project roots:** The local MCP registration check uses `_project_root` (already defined in mcp_server.py as `Path(__file__).resolve().parents[2]`). This is always the promaia repo root.

4. **Health endpoint under load:** 30-second cache prevents DB spam from dashboard polling or monitoring. Note: this means a state change (ok -> error) can be masked for up to 30 seconds. Acceptable for monitoring; irrelevant for the manager's startup gate (always a fresh call).

5. **Production health endpoint exposure:** The deep health response is unauthenticated (needed for load balancer/monitoring probes). In production, omit sensitive details from the unauthenticated response: no `missing` env var names, no bearer token prefixes. Full details available via authenticated `/health?detail=true` (requires bearer token).

6. **Turso sync age:** If `last_sync_age_sec` exceeds 300 (5 minutes), report database as degraded. This catches silent sync failures.

7. **Windows port check for CLI:** Use `netstat -ano` filtered for port 8751 to check if the server process is listening. No additional dependency (psutil) needed — `netstat` is available on all Windows installs. On Linux/Mac, fall back to `ss` or `lsof`.

8. **Async/sync duality:** `health.py` functions are async-first. CLI uses `asyncio.run(run_checks())`. The existing `run_selftest()` in mcp_server.py also uses `asyncio.run()` for the MuninnDB check, so this pattern is established.

---

## What This Prevents

| Failure mode | How it's caught |
|---|---|
| MCP config says stdio, server is HTTP | Layer 2 startup validation, Layer 4 CLI |
| Bearer token mismatch between .env and config | Layer 2 startup validation, Layer 4 CLI |
| Brain server not running when Claude starts | Layer 3 manager health gate, Layer 4 CLI |
| Turso connection lost in production | Layer 1 health endpoint, Layer 2 startup |
| Env vars missing on Railway deploy | Layer 2 startup validation |
| Server says "ok" but can't query DB | Layer 1 deep health replaces cosmetic check |
| Token auto-generated on ephemeral container | Layer 2 production-specific warning |
| Claude Code starts before brain server is up (boot race) | Layer 4 startup sequencer waits for health before exiting, Layer 1 briefing warns if uptime < 60s |
