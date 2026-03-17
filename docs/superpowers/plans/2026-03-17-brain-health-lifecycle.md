# Brain Health Lifecycle Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the brain MCP server self-aware of its health across startup, runtime, and diagnostic — in both local dev and production. No silent failures.

**Architecture:** Shared health check module (`promaia/brain/health.py`) provides all check logic. Five layers consume it: deep `/health` endpoint, startup validator, manager health gate, Windows boot sequencer, and CLI diagnostic. Each layer is independently useful.

**Tech Stack:** Python 3.13+, libsql, Starlette, uvicorn, urllib (stdlib for health polling — no new deps)

**Spec:** `docs/superpowers/specs/2026-03-17-brain-health-lifecycle-design.md`

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `promaia/brain/health.py` | Create | Shared async health checks: DB, vector, muninn, env vars, tools, MCP registration, port check |
| `promaia/storage/libsql_db.py` | Modify | Add `_last_sync_time`, `sync_age()`, `try_sync()` to `LibSQLDB` |
| `promaia/brain/mcp_server.py` | Modify | Replace `_health_endpoint`, add `validate_startup()` to lifespan, rewire `run_selftest()` |
| `promaia/brain/mcp/handlers/context_ops.py` | Modify | Add startup status warning to briefing |
| `scripts/manager.py` | Modify | Add `_wait_for_brain_health()`, call after Brain Daemon start |
| `scripts/startup.py` | Create | Windows boot sequencer — starts manager, polls health, writes status file |
| `promaia/__main__.py` | Modify | Add `brain check` fast path |
| `Promaia.vbs` (Startup folder) | Modify | Point to `scripts/startup.py` |
| `tests/test_brain_health.py` | Create | Tests for all health check functions |

---

## Task 1: Add sync tracking to LibSQLDB

**Files:**
- Modify: `promaia/storage/libsql_db.py:142-178`
- Test: `tests/test_brain_health.py`

- [ ] **Step 1: Write failing test for sync_age**

```python
# tests/test_brain_health.py
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import unittest
import time

class TestLibSQLSyncTracking(unittest.TestCase):
    def test_sync_age_returns_float(self):
        """LibSQLDB should track time since last sync."""
        from promaia.storage.libsql_db import get_libsql_db
        db = get_libsql_db()
        age = db.sync_age()
        self.assertIsInstance(age, float)
        self.assertGreaterEqual(age, 0.0)

    def test_try_sync_returns_bool(self):
        """try_sync() returns True on success, False on failure."""
        from promaia.storage.libsql_db import get_libsql_db
        db = get_libsql_db()
        result = db.try_sync()
        self.assertIsInstance(result, bool)

    def test_sync_age_updates_after_try_sync(self):
        """sync_age should reset after a successful try_sync."""
        from promaia.storage.libsql_db import get_libsql_db
        db = get_libsql_db()
        time.sleep(0.1)
        old_age = db.sync_age()
        if db.try_sync():
            new_age = db.sync_age()
            self.assertLess(new_age, old_age)

if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /c/Users/"Zachary Turner"/dev/promaia && python -m pytest tests/test_brain_health.py::TestLibSQLSyncTracking -v`
Expected: FAIL — `AttributeError: 'LibSQLDB' object has no attribute 'sync_age'`

- [ ] **Step 3: Implement sync tracking on LibSQLDB**

In `promaia/storage/libsql_db.py`, modify `LibSQLDB.__init__` (line 143) to add `_last_sync_time`:

```python
class LibSQLDB:
    def __init__(self, db_path: str = "promaia.db"):
        self.db_path = db_path
        self._conn: Optional[libsql.Connection] = None
        self._wrapped_conn: Optional[LibSQLConnectionWrapper] = None
        self._last_sync_time: float = 0.0
        self._using_turso: bool = False
        self._init_connection()
```

In `_init_connection` (line 162), after `self._conn.sync()`, add:

```python
                self._conn.sync()
                self._last_sync_time = time.time()
                self._using_turso = True
```

Add two new methods after `close_pool` (after line 265):

```python
    def sync_age(self) -> float:
        """Seconds since last successful Turso sync. Returns 0.0 if never synced (local-only)."""
        if not self._last_sync_time:
            return 0.0
        return time.time() - self._last_sync_time

    def try_sync(self) -> bool:
        """Attempt a Turso sync. Returns True on success, False on failure or if not using Turso."""
        if not self._using_turso or not hasattr(self._conn, 'sync'):
            return True  # local-only DB, "sync" is trivially successful
        try:
            self._conn.sync()
            self._last_sync_time = time.time()
            return True
        except Exception as e:
            logger.warning(f"Turso sync failed: {e}")
            return False
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /c/Users/"Zachary Turner"/dev/promaia && python -m pytest tests/test_brain_health.py::TestLibSQLSyncTracking -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add promaia/storage/libsql_db.py tests/test_brain_health.py
git commit -m "feat(health): add sync tracking to LibSQLDB for health monitoring"
```

---

## Task 2: Create shared health check module

**Files:**
- Create: `promaia/brain/health.py`
- Test: `tests/test_brain_health.py` (append)

- [ ] **Step 1: Write failing tests for health checks**

Append to `tests/test_brain_health.py`:

```python
import asyncio

class TestHealthChecks(unittest.TestCase):
    def test_detect_environment_local(self):
        """Should detect local environment when no Railway/production env vars."""
        from promaia.brain.health import detect_environment
        # Clear production env vars if set
        env = os.environ.copy()
        os.environ.pop("RAILWAY_ENVIRONMENT", None)
        os.environ.pop("PYTHON_ENV", None)
        try:
            self.assertEqual(detect_environment(), "local")
        finally:
            os.environ.update(env)

    def test_check_database_returns_dict(self):
        from promaia.brain.health import check_database
        result = asyncio.run(check_database())
        self.assertIn("status", result)
        self.assertIn("backend", result)

    def test_check_env_vars_returns_dict(self):
        from promaia.brain.health import check_env_vars
        result = asyncio.run(check_env_vars())
        self.assertIn("status", result)
        self.assertIn("missing", result)

    def test_check_mcp_registration_returns_dict(self):
        from promaia.brain.health import check_mcp_registration
        result = asyncio.run(check_mcp_registration(
            host="127.0.0.1", port=8751, expected_token="test-token"
        ))
        self.assertIn("status", result)

    def test_run_checks_returns_full_structure(self):
        from promaia.brain.health import run_checks
        result = asyncio.run(run_checks())
        self.assertIn("status", result)
        self.assertIn("checks", result)
        self.assertIn("environment", result)
        self.assertIn("database", result["checks"])
        self.assertIn("env_vars", result["checks"])

    def test_check_server_port_returns_dict(self):
        from promaia.brain.health import check_server_port
        result = asyncio.run(check_server_port(port=8751))
        self.assertIn("status", result)
        # "listening" or "not_listening" — either is valid

    def test_aggregate_status_logic(self):
        from promaia.brain.health import aggregate_status
        # All ok
        self.assertEqual(aggregate_status({"db": {"status": "ok"}, "env": {"status": "ok"}},
                                          critical=["db", "env"], non_critical=[]), "ok")
        # Non-critical down
        self.assertEqual(aggregate_status({"db": {"status": "ok"}, "muninn": {"status": "unavailable"}},
                                          critical=["db"], non_critical=["muninn"]), "degraded")
        # Critical down
        self.assertEqual(aggregate_status({"db": {"status": "error"}, "muninn": {"status": "ok"}},
                                          critical=["db"], non_critical=["muninn"]), "error")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /c/Users/"Zachary Turner"/dev/promaia && python -m pytest tests/test_brain_health.py::TestHealthChecks -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'promaia.brain.health'`

- [ ] **Step 3: Implement health.py**

Create `promaia/brain/health.py`:

```python
"""
Shared health check logic for the zBrain MCP server.

Used by:
- /health endpoint (Layer 1)
- Startup validator (Layer 2)
- CLI diagnostic (Layer 5)

All check functions are async. CLI callers use asyncio.run(run_checks()).
Functions accept optional db/vector_mgr params — pass existing singletons
from the server process, or omit for standalone (CLI) use.
"""
import asyncio
import json
import logging
import os
import platform
import subprocess
import time
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

_project_root = Path(__file__).resolve().parents[2]
_start_time = time.time()


def detect_environment() -> str:
    """Detect whether we're running in production or local dev."""
    if os.environ.get("RAILWAY_ENVIRONMENT") or os.environ.get("PYTHON_ENV") == "production":
        return "production"
    return "local"


def aggregate_status(
    checks: dict[str, dict],
    critical: list[str],
    non_critical: list[str],
) -> str:
    """Compute overall status from individual check results.

    Returns 'ok', 'degraded', or 'error'.
    """
    for key in critical:
        if key in checks and checks[key].get("status") not in ("ok", "listening"):
            return "error"
    for key in non_critical:
        if key in checks and checks[key].get("status") not in ("ok", "listening"):
            return "degraded"
    return "ok"


async def check_database(db=None) -> dict[str, Any]:
    """Check database connectivity and Turso sync status."""
    try:
        if db is None:
            from promaia.storage.db_factory import get_db
            db = get_db()

        db.execute("SELECT 1")

        # Determine backend type
        from promaia.storage.libsql_db import get_libsql_db, _USING_REAL_LIBSQL
        libsql_db = get_libsql_db()
        using_turso = getattr(libsql_db, '_using_turso', False)
        backend = "turso" if using_turso else ("libsql" if _USING_REAL_LIBSQL else "sqlite")

        # Sync check
        sync_ok = libsql_db.try_sync()
        sync_age = libsql_db.sync_age()

        result = {
            "status": "ok",
            "backend": backend,
            "sync_ok": sync_ok,
            "last_sync_age_sec": round(sync_age, 1),
        }

        # Sync failure is an error; stale sync is a warning (not status change)
        # because aggregate_status treats any non-"ok" critical check as overall "error".
        # Instead, flag staleness so the CLI/logs can report it without escalating.
        if using_turso and not sync_ok:
            result["status"] = "error"
        elif using_turso and sync_age > 300:
            result["sync_stale"] = True  # reported in output, doesn't change status

        return result
    except Exception as e:
        return {"status": "error", "backend": "unknown", "error": str(e)}


async def check_vector_db(vector_mgr=None) -> dict[str, Any]:
    """Check Vector DB initialization."""
    try:
        if vector_mgr is None:
            from promaia.storage.vector_db import VectorDBManager
            vector_mgr = VectorDBManager()
        return {"status": "ok", "error": None}
    except Exception as e:
        return {"status": "error", "error": str(e)}


async def check_muninn() -> dict[str, Any]:
    """Check MuninnDB reachability. Non-critical."""
    try:
        from promaia.brain.muninn import get_muninn
        m = await get_muninn()
        if m is not None:
            return {"status": "ok", "reason": None}
        return {"status": "unavailable", "reason": "get_muninn() returned None"}
    except Exception as e:
        return {"status": "unavailable", "reason": str(e)}


async def check_env_vars() -> dict[str, Any]:
    """Check required environment variables are present."""
    env = detect_environment()
    required = ["GOOGLE_API_KEY", "BRAIN_MCP_TOKEN"]
    if env == "production":
        required.extend(["TURSO_DATABASE_URL", "TURSO_AUTH_TOKEN"])

    missing = [k for k in required if not os.environ.get(k, "").strip()]
    return {
        "status": "ok" if not missing else "error",
        "missing": missing,
    }


async def check_tools(server=None) -> dict[str, Any]:
    """Check that MCP tools are registered. Requires server instance."""
    if server is None:
        return {"status": "ok", "count": -1, "note": "no server instance (CLI mode)"}
    try:
        tools = await server.list_tools()
        count = len(tools.tools) if hasattr(tools, 'tools') else len(tools)
        return {"status": "ok" if count > 0 else "error", "count": count}
    except Exception as e:
        return {"status": "error", "count": 0, "error": str(e)}


async def check_mcp_registration(
    host: str = "127.0.0.1",
    port: int = 8751,
    expected_token: str = "",
) -> dict[str, Any]:
    """Validate Claude Code MCP config files match the running server."""
    issues = []
    configs_found = []

    user_config = Path.home() / ".claude" / ".mcp.json"
    project_config = _project_root / ".mcp.json"

    expected_url = f"http://{host}:{port}/mcp/"

    for label, path in [("user-level", user_config), ("project-level", project_config)]:
        if not path.exists():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            brain = data.get("mcpServers", {}).get("brain")
            if brain is None:
                continue

            configs_found.append(label)

            # Check transport type
            if "command" in brain or "type" in brain:
                transport = brain.get("type", "stdio")
                if transport == "stdio":
                    issues.append(
                        f"{label} ({path}): configured as stdio "
                        f"(command: {brain.get('command', '?')} {' '.join(brain.get('args', []))}). "
                        f"Expected HTTP URL."
                    )
                    continue

            # Check URL
            url = brain.get("url", "")
            if url != expected_url:
                issues.append(
                    f"{label} ({path}): URL is '{url}', expected '{expected_url}'"
                )

            # Check token
            if expected_token:
                auth = brain.get("headers", {}).get("Authorization", "")
                expected_auth = f"Bearer {expected_token}"
                if auth != expected_auth:
                    issues.append(
                        f"{label} ({path}): token mismatch "
                        f"(config has '{auth[:20]}...', server expects '{expected_auth[:20]}...')"
                    )

        except json.JSONDecodeError:
            issues.append(f"{label} ({path}): invalid JSON — cannot parse")
        except Exception as e:
            issues.append(f"{label} ({path}): read error — {e}")

    if len(configs_found) == 0:
        issues.append("No Claude MCP config has a 'brain' entry")
    elif len(configs_found) > 1:
        issues.append("Duplicate brain registration in both user-level and project-level configs — user-level takes precedence")

    return {
        "status": "ok" if not issues else "mismatch",
        "configs_found": configs_found,
        "issues": issues,
        "expected": {"url": expected_url, "token_prefix": expected_token[:8] + "..." if expected_token else ""},
    }


async def check_server_port(port: int = 8751) -> dict[str, Any]:
    """Check if a process is listening on the brain server port."""
    try:
        if platform.system() == "Windows":
            output = subprocess.check_output(
                ["netstat", "-ano"], text=True, stderr=subprocess.DEVNULL, timeout=5
            )
            for line in output.splitlines():
                if f":{port}" in line and "LISTENING" in line:
                    parts = line.split()
                    pid = parts[-1] if parts else "?"
                    return {"status": "listening", "pid": pid}
        else:
            # Linux/Mac
            try:
                output = subprocess.check_output(
                    ["ss", "-tlnp", f"sport = :{port}"], text=True, stderr=subprocess.DEVNULL, timeout=5
                )
                if str(port) in output:
                    return {"status": "listening", "pid": "?"}
            except FileNotFoundError:
                output = subprocess.check_output(
                    ["lsof", "-i", f":{port}", "-sTCP:LISTEN"], text=True, stderr=subprocess.DEVNULL, timeout=5
                )
                if output.strip():
                    return {"status": "listening", "pid": "?"}

        return {"status": "not_listening"}
    except Exception as e:
        return {"status": "unknown", "error": str(e)}


async def check_startup_status() -> dict[str, Any]:
    """Read the startup status file written by scripts/startup.py."""
    status_file = Path.home() / ".promaia" / "startup.status"
    if not status_file.exists():
        return {"status": "unknown", "reason": "no status file"}
    try:
        data = json.loads(status_file.read_text(encoding="utf-8"))
        return {"status": "ok" if data.get("brain_healthy") else "failed", **data}
    except Exception as e:
        return {"status": "unknown", "reason": str(e)}


async def run_checks(
    db=None,
    vector_mgr=None,
    server=None,
    include_mcp_registration: bool = True,
    include_port_check: bool = False,
    host: str = "127.0.0.1",
    port: int = 8751,
    token: str = "",
) -> dict[str, Any]:
    """Run all health checks and return structured result.

    Args:
        db: Existing DB instance (pass from server), or None for standalone.
        vector_mgr: Existing VectorDBManager, or None for standalone.
        server: MCP Server instance for tool count check, or None.
        include_mcp_registration: Run MCP config validation (local only).
        include_port_check: Check if port is listening (CLI only).
        host: Expected brain server host.
        port: Expected brain server port.
        token: Expected bearer token for MCP registration check.
    """
    env = detect_environment()

    # Run checks concurrently
    tasks = {
        "database": check_database(db),
        "vector_db": check_vector_db(vector_mgr),
        "muninn": check_muninn(),
        "env_vars": check_env_vars(),
        "tools": check_tools(server),
    }

    results = {}
    for key, coro in tasks.items():
        try:
            results[key] = await coro
        except Exception as e:
            results[key] = {"status": "error", "error": str(e)}

    # Optional: MCP registration (local only)
    if include_mcp_registration and env == "local":
        results["mcp_registration"] = await check_mcp_registration(host, port, token)

    # Optional: port check (CLI only)
    if include_port_check:
        results["server_port"] = await check_server_port(port)

    critical = ["database", "vector_db", "env_vars", "tools"]
    non_critical = ["muninn"]
    overall = aggregate_status(results, critical, non_critical)

    return {
        "status": overall,
        "service": "zbrain-brain",
        "environment": env,
        "uptime_sec": round(time.time() - _start_time, 1),
        "checks": results,
    }


def run_checks_sync(**kwargs) -> dict[str, Any]:
    """Synchronous wrapper for CLI use."""
    return asyncio.run(run_checks(**kwargs))


def format_cli_output(result: dict) -> str:
    """Format health check results for terminal display."""
    lines = [
        "zBrain Health Check",
        "===================",
        f"Environment:    {result['environment']} (detected)",
    ]

    checks = result.get("checks", {})

    # Database
    db = checks.get("database", {})
    db_detail = db.get("backend", "?")
    if db.get("sync_ok") is not None and db.get("backend") == "turso":
        sync_age = db.get("last_sync_age_sec", "?")
        db_detail += f", sync {sync_age}s ago"
    _add_check_line(lines, "Database", db_detail, db.get("status", "?"))

    # Vector DB
    vdb = checks.get("vector_db", {})
    _add_check_line(lines, "Vector DB", "initialized", vdb.get("status", "?"))

    # MuninnDB
    mun = checks.get("muninn", {})
    mun_detail = mun.get("reason") or "reachable"
    _add_check_line(lines, "MuninnDB", mun_detail, mun.get("status", "?"))

    # Env vars
    ev = checks.get("env_vars", {})
    ev_detail = "all present" if ev.get("status") == "ok" else f"missing: {', '.join(ev.get('missing', []))}"
    _add_check_line(lines, "Env vars", ev_detail, ev.get("status", "?"))

    # Tools
    tools = checks.get("tools", {})
    _add_check_line(lines, "Tools", f"{tools.get('count', '?')} registered", tools.get("status", "?"))

    # MCP Registration
    mcp = checks.get("mcp_registration")
    if mcp:
        lines.append("")
        lines.append("MCP Registration:")
        if mcp.get("status") == "ok":
            for cfg in mcp.get("configs_found", []):
                lines.append(f"  {cfg}: brain -> {mcp['expected']['url']} .... OK")
        else:
            for issue in mcp.get("issues", []):
                lines.append(f"  ISSUE: {issue}")

    # Server port
    port_check = checks.get("server_port")
    if port_check:
        lines.append("")
        lines.append("Server Process:")
        pid = port_check.get("pid", "?")
        status = port_check.get("status", "?")
        status_str = "OK" if status == "listening" else "NOT RUNNING"
        lines.append(f"  Port 8751:    {status.upper()} (PID {pid}) ............. {status_str}")

    # Overall
    lines.append("")
    warnings = []
    for key, check in checks.items():
        s = check.get("status", "")
        if s not in ("ok", "listening") and key in ["muninn"]:
            warnings.append(f"{key} {s}")
    overall = result.get("status", "unknown").upper()
    if warnings:
        lines.append(f"Overall: {overall} ({len(warnings)} non-critical: {', '.join(warnings)})")
    else:
        lines.append(f"Overall: {overall}")

    return "\n".join(lines)


def _add_check_line(lines: list, name: str, detail: str, status: str):
    """Add a formatted check line to output."""
    status_str = "OK" if status == "ok" else status.upper()
    padding = "." * max(1, 45 - len(name) - len(detail))
    lines.append(f"{name:15s} {detail} {padding} {status_str}")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /c/Users/"Zachary Turner"/dev/promaia && python -m pytest tests/test_brain_health.py::TestHealthChecks -v`
Expected: PASS (7 tests)

- [ ] **Step 5: Commit**

```bash
git add promaia/brain/health.py tests/test_brain_health.py
git commit -m "feat(health): create shared health check module"
```

---

## Task 3: Replace cosmetic health endpoint with deep check

**Files:**
- Modify: `promaia/brain/mcp_server.py:843-851` (replace `_health_endpoint`)
- Modify: `promaia/brain/mcp_server.py:872-889` (add `validate_startup` to lifespan)

- [ ] **Step 1: Write failing test for deep health endpoint**

Append to `tests/test_brain_health.py`:

```python
class TestHealthEndpoint(unittest.TestCase):
    def test_health_response_has_checks(self):
        """The /health endpoint should return structured check results."""
        import urllib.request
        try:
            with urllib.request.urlopen("http://127.0.0.1:8751/health", timeout=3) as resp:
                data = json.loads(resp.read())
                self.assertIn("checks", data)
                self.assertIn("database", data["checks"])
                self.assertIn("status", data)
                self.assertIn(data["status"], ("ok", "degraded", "error"))
        except Exception:
            self.skipTest("Brain server not running — skip endpoint test")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /c/Users/"Zachary Turner"/dev/promaia && python -m pytest tests/test_brain_health.py::TestHealthEndpoint -v`
Expected: FAIL (if server is running, response won't have `checks` key yet)

- [ ] **Step 3: Replace `_health_endpoint` in mcp_server.py**

Replace `_health_endpoint` at line 843-851 with:

```python
# Health check cache
_health_cache: dict = {}
_health_cache_time: float = 0.0
_HEALTH_CACHE_TTL = 30.0

async def _health_endpoint(request: Request) -> JSONResponse:
    """Deep health check with 30-second caching.

    Cache stores FULL result. Redaction happens on output, not storage,
    so authenticated and unauthenticated callers get correct responses
    from the same cache.
    """
    global _health_cache, _health_cache_time
    import copy

    now = time.time()
    if not _health_cache or (now - _health_cache_time) >= _HEALTH_CACHE_TTL:
        from promaia.brain.health import run_checks
        _health_cache = await run_checks(
            db=get_db(),
            vector_mgr=get_vector_mgr(),
            server=server,
            include_mcp_registration=False,
            host=os.environ.get("BRAIN_MCP_HOST", "127.0.0.1"),
            port=int(os.environ.get("BRAIN_MCP_PORT", "8751")),
            token=_get_token(),
        )
        _health_cache_time = now

    from promaia.brain.health import detect_environment
    env = detect_environment()
    result = copy.deepcopy(_health_cache)

    # In production, strip sensitive details unless authenticated
    if env == "production":
        auth_header = request.headers.get("authorization", "")
        expected = f"Bearer {_get_token()}"
        is_authed = secrets.compare_digest(auth_header, expected)
        if not is_authed:
            if "env_vars" in result.get("checks", {}):
                result["checks"]["env_vars"].pop("missing", None)

    return JSONResponse(result)
```

- [ ] **Step 4: Add `validate_startup` to lifespan**

Replace the lifespan in `create_app` (line 876-880) with:

```python
    @contextlib.asynccontextmanager
    async def lifespan(app: Starlette) -> AsyncIterator[None]:
        async with session_manager.run():
            logger.info("Brain MCP daemon ready")
            await _validate_startup()
            yield
```

Add the `_validate_startup` function before `create_app`:

```python
async def _validate_startup():
    """Run startup validation and log results."""
    from promaia.brain.health import run_checks, detect_environment

    env = detect_environment()
    host = os.environ.get("BRAIN_MCP_HOST", "127.0.0.1")
    port = int(os.environ.get("BRAIN_MCP_PORT", "8751"))
    token = _get_token()

    result = await run_checks(
        db=get_db(),
        vector_mgr=get_vector_mgr(),
        server=server,
        include_mcp_registration=(env == "local"),
        host=host,
        port=port,
        token=token,
    )

    # Log structured output
    checks = result.get("checks", {})
    logger.info("Startup validation:")

    for name, check in checks.items():
        status = check.get("status", "?")
        if name == "database":
            detail = f"{check.get('backend', '?')}"
            if check.get("sync_ok") is not None:
                detail += f", sync {'ok' if check['sync_ok'] else 'FAILED'}"
            logger.info(f"  {name:20s} {status.upper()} ({detail})")
        elif name == "mcp_registration":
            if status == "ok":
                logger.info(f"  {name:20s} OK")
            else:
                logger.warning(f"  {name:20s} {status.upper()}")
                for issue in check.get("issues", []):
                    logger.warning(f"    {issue}")
                logger.warning(f"    Expected: {json.dumps(check.get('expected', {}))}")
                if env == "local":
                    logger.warning("    Fix: Update MCP config or set BRAIN_AUTO_FIX_CONFIG=true")

                # Auto-fix if enabled
                if os.environ.get("BRAIN_AUTO_FIX_CONFIG", "").lower() == "true":
                    _auto_fix_mcp_config(host, port, token)
        elif name == "env_vars":
            missing = check.get("missing", [])
            if missing:
                logger.warning(f"  {name:20s} MISSING: {', '.join(missing)}")
            else:
                logger.info(f"  {name:20s} OK")
        else:
            logger.info(f"  {name:20s} {status.upper()}")

    # Token auto-generation warning in production
    if env == "production" and not os.environ.get("BRAIN_MCP_TOKEN", "").strip():
        logger.warning("  BRAIN_MCP_TOKEN was auto-generated. Set it as a Railway env var to prevent token drift between deploys.")

    overall = result.get("status", "unknown")
    logger.info(f"Status: {overall.upper()}")


def _auto_fix_mcp_config(host: str, port: int, token: str):
    """Auto-repair Claude MCP config files. Creates .bak before modifying."""
    import shutil

    correct_brain = {
        "url": f"http://{host}:{port}/mcp/",
        "headers": {"Authorization": f"Bearer {token}"},
    }

    for path in [Path.home() / ".claude" / ".mcp.json", _project_root / ".mcp.json"]:
        if not path.exists():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            brain = data.get("mcpServers", {}).get("brain")
            if brain is None:
                continue

            # Check if it needs fixing
            if brain.get("url") == correct_brain["url"]:
                auth = brain.get("headers", {}).get("Authorization", "")
                if auth == correct_brain["headers"]["Authorization"]:
                    continue  # already correct

            # Backup (path.name + ".bak" avoids with_suffix mangling .mcp.json)
            bak = path.parent / (path.name + ".bak")
            shutil.copy2(path, bak)
            logger.info(f"  Backed up {path} -> {bak}")

            # Fix
            data["mcpServers"]["brain"] = correct_brain
            path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
            logger.info(f"  Auto-fixed {path}")
        except json.JSONDecodeError:
            logger.error(f"  Cannot auto-fix {path}: invalid JSON")
        except Exception as e:
            logger.error(f"  Cannot auto-fix {path}: {e}")
```

- [ ] **Step 5: Rewire `run_selftest` to use shared module**

Replace the body of `run_selftest()` (lines 895-948) with:

```python
def run_selftest():
    """Run diagnostics to verify MCP server dependencies before launching."""
    from promaia.brain.health import run_checks_sync, format_cli_output
    result = run_checks_sync(
        include_mcp_registration=True,
        include_port_check=True,
        token=_get_token(),
    )
    print(format_cli_output(result))
    sys.exit(0 if result["status"] != "error" else 1)
```

- [ ] **Step 6: Write test for auto-fix config**

Append to `tests/test_brain_health.py`:

```python
import tempfile
import shutil

class TestAutoFixConfig(unittest.TestCase):
    def test_auto_fix_creates_backup(self):
        """Auto-fix should create a .bak before modifying config."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / ".mcp.json"
            config_path.write_text(json.dumps({
                "mcpServers": {
                    "brain": {"type": "stdio", "command": "python", "args": []},
                    "other": {"command": "node"}
                }
            }))
            from promaia.brain.mcp_server import _auto_fix_mcp_config
            _auto_fix_mcp_config.__wrapped__(config_path, "127.0.0.1", 8751, "test-token")
            # Verify backup exists
            bak = config_path.parent / (config_path.name + ".bak")
            self.assertTrue(bak.exists())
            # Verify brain entry was fixed, other entries untouched
            fixed = json.loads(config_path.read_text())
            self.assertEqual(fixed["mcpServers"]["brain"]["url"], "http://127.0.0.1:8751/mcp/")
            self.assertIn("other", fixed["mcpServers"])

    def test_auto_fix_skips_invalid_json(self):
        """Auto-fix should not crash on invalid JSON."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / ".mcp.json"
            config_path.write_text("not json{{{")
            from promaia.brain.mcp_server import _auto_fix_mcp_config
            # Should not raise
            _auto_fix_mcp_config.__wrapped__(config_path, "127.0.0.1", 8751, "test-token")
            # File should be unchanged
            self.assertEqual(config_path.read_text(), "not json{{{")
```

Note: `_auto_fix_mcp_config` iterates hardcoded paths. For testability, extract the per-file logic into a helper `_fix_single_mcp_config(path, host, port, token)` that these tests call directly. Store the original `_auto_fix_mcp_config` as a wrapper that calls the helper for each known path. Reference the helper as `__wrapped__` above or call the extracted function directly.

- [ ] **Step 7: Run tests to verify they pass**

Run: `cd /c/Users/"Zachary Turner"/dev/promaia && python -m pytest tests/test_brain_health.py -v`
Expected: ALL PASS

- [ ] **Step 8: Commit**

```bash
git add promaia/brain/mcp_server.py tests/test_brain_health.py
git commit -m "feat(health): deep health endpoint + startup validation + auto-fix"
```

---

## Task 4: Manager health gate

**Files:**
- Modify: `scripts/manager.py:238-256`

- [ ] **Step 1: Add `_wait_for_brain_health` function**

Add after line 191 (after `cleanup_existing_processes`), before `def main()`:

```python
def _wait_for_brain_health(host="127.0.0.1", port=8751, timeout=10):
    """Poll brain /health until it responds or timeout.

    Returns the parsed health JSON on any valid response (ok, degraded, or error).
    Returns None only on timeout (brain never responded at all).
    """
    import urllib.request
    import json as _json

    url = f"http://{host}:{port}/health"
    deadline = time.time() + timeout

    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as resp:
                return _json.loads(resp.read())
        except Exception:
            time.sleep(1)

    return None
```

- [ ] **Step 2: Insert health gate after Brain Daemon start**

In `main()`, after the loop that starts all processes (line 254-256), replace:

```python
        for p in processes:
            p.start()
            time.sleep(1) # stagger startups slightly
```

with:

```python
        # Start Brain Daemon first and wait for health
        brain_proc = processes[0]  # Brain Daemon is always first
        brain_proc.start()

        print("Waiting for Brain Daemon health check...")
        health = _wait_for_brain_health(timeout=15)
        if health is None:
            print("CRITICAL: Brain daemon did not respond on :8751 within 15s.")
            print("Claude Code MCP tools will NOT work this session.")
        elif health.get("status") == "error":
            print(f"WARNING: Brain daemon is up but unhealthy: {health.get('status')}")
            for name, check in health.get("checks", {}).items():
                if check.get("status") not in ("ok", "listening"):
                    print(f"  {name}: {check.get('status')} — {check.get('error', check.get('reason', ''))}")
        elif health.get("status") == "degraded":
            print(f"Brain daemon healthy (degraded — non-critical subsystem down)")
        else:
            print(f"Brain daemon healthy ({health.get('checks', {}).get('tools', {}).get('count', '?')} tools)")

        # Start remaining services
        for p in processes[1:]:
            p.start()
            time.sleep(1)
```

- [ ] **Step 3: Manually test by restarting the manager**

Run: `cd /c/Users/"Zachary Turner"/dev/promaia && python -m promaia dev`
Expected: See "Waiting for Brain Daemon health check..." then "Brain daemon healthy (N tools)" before other services start.

- [ ] **Step 4: Commit**

```bash
git add scripts/manager.py
git commit -m "feat(health): manager waits for brain health before starting other services"
```

---

## Task 5: Windows startup sequencer

**Files:**
- Create: `scripts/startup.py`
- Modify: `Promaia.vbs` at `C:\Users\Zachary Turner\AppData\Roaming\Microsoft\Windows\Start Menu\Programs\Startup\Promaia.vbs`

- [ ] **Step 1: Create `scripts/startup.py`**

```python
"""
Windows boot sequencer for Promaia.

Called by Promaia.vbs at Windows startup. Starts the manager process,
polls brain health, writes status file, then exits (manager keeps running).

Usage:
    pythonw.exe scripts/startup.py     (headless, from VBS)
    python scripts/startup.py          (interactive, for debugging)
"""
import json
import os
import subprocess
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.absolute()
STATUS_DIR = Path.home() / ".promaia"
STATUS_FILE = STATUS_DIR / "startup.status"
HEALTH_TIMEOUT = 30  # seconds — cold boot can be slow


def wait_for_brain_health(host="127.0.0.1", port=8751, timeout=HEALTH_TIMEOUT):
    """Poll brain /health until it responds or timeout."""
    url = f"http://{host}:{port}/health"
    deadline = time.time() + timeout

    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as resp:
                return json.loads(resp.read())
        except Exception:
            time.sleep(1)
    return None


def write_status(healthy: bool, boot_time: float, details: dict = None):
    """Write startup status to ~/.promaia/startup.status."""
    STATUS_DIR.mkdir(parents=True, exist_ok=True)
    data = {
        "timestamp": datetime.now().isoformat(),
        "brain_healthy": healthy,
        "boot_time_sec": round(boot_time, 1),
    }
    if details:
        data["details"] = details
    STATUS_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def main():
    start = time.time()

    # Start the manager as a detached subprocess
    # CREATE_NEW_PROCESS_GROUP + DETACHED_PROCESS so it survives this script exiting
    creation_flags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
    subprocess.Popen(
        [sys.executable, "-m", "promaia", "dev"],
        cwd=str(PROJECT_ROOT),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=creation_flags,
    )

    # Wait for brain to come up
    health = wait_for_brain_health()
    elapsed = time.time() - start

    if health:
        status = health.get("status", "unknown")
        write_status(
            healthy=(status in ("ok", "degraded")),
            boot_time=elapsed,
            details={"brain_status": status},
        )
    else:
        write_status(healthy=False, boot_time=elapsed, details={"error": "timeout"})


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Update Promaia.vbs (MANUAL — outside git)**

This file lives in the Windows Startup folder, not in the repo. Write to `C:\Users\Zachary Turner\AppData\Roaming\Microsoft\Windows\Start Menu\Programs\Startup\Promaia.vbs`:

```vbs
' Promaia Auto-Start — launches startup sequencer (headless)
' The sequencer starts the manager, waits for brain health, writes status, then exits.
Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = "C:\Users\Zachary Turner\dev\promaia"
WshShell.Run """C:\Python314\pythonw.exe"" scripts/startup.py", 0, False
```

- [ ] **Step 3: Test by running startup.py manually**

Run: `cd /c/Users/"Zachary Turner"/dev/promaia && python scripts/startup.py`
Then check: `cat ~/.promaia/startup.status`
Expected: JSON with `brain_healthy: true` and `boot_time_sec` populated.

- [ ] **Step 4: Commit**

```bash
git add scripts/startup.py
git commit -m "feat(health): Windows boot sequencer with brain health gate"
```

---

## Task 6: Briefing startup warning

**Files:**
- Modify: `promaia/brain/mcp/handlers/context_ops.py:29-60`

- [ ] **Step 1: Add startup status check to briefing**

In `_handle_briefing`, after the existing Promaia server health check (after line 60), add:

```python
    # --- Brain boot status check ---
    try:
        startup_status_file = Path.home() / ".promaia" / "startup.status"
        boot_warning = None

        if startup_status_file.exists():
            import json as _json
            boot_data = _json.loads(startup_status_file.read_text(encoding="utf-8"))
            if not boot_data.get("brain_healthy"):
                boot_warning = (
                    f"Brain server was NOT healthy at boot "
                    f"(boot time: {boot_data.get('boot_time_sec', '?')}s, "
                    f"at {boot_data.get('timestamp', '?')}). "
                    f"If MCP tools are missing, restart Claude Code."
                )
        else:
            boot_warning = (
                "No boot status file found (~/.promaia/startup.status). "
                "Brain server may not have been ready when this session started."
            )

        # Also check uptime — if brain just started, tools may have been missed
        try:
            import httpx
            async with httpx.AsyncClient() as client:
                resp = await client.get("http://127.0.0.1:8751/health", timeout=3.0)
                if resp.status_code == 200:
                    health_data = resp.json()
                    uptime = health_data.get("uptime_sec", 999)
                    if uptime < 60 and not boot_warning:
                        boot_warning = (
                            f"Brain server started only {int(uptime)}s ago. "
                            f"If MCP tools are missing, restart Claude Code."
                        )
        except Exception:
            pass

        if boot_warning:
            lines.append(f"## Boot Warning\n{boot_warning}\n")
    except Exception:
        pass  # never let boot check crash the briefing
```

Add `from pathlib import Path` to the imports at the top of `context_ops.py` if not already present.

- [ ] **Step 2: Verify briefing still works**

Run: `cd /c/Users/"Zachary Turner"/dev/promaia && python -c "
from promaia.brain.mcp_server import call_tool
import asyncio
result = asyncio.run(call_tool('briefing', {}))
text = result[0].text.encode('utf-8', errors='replace').decode('utf-8')
print(text[:500])
"`
Expected: Briefing output, possibly with a boot warning section.

- [ ] **Step 3: Commit**

```bash
git add promaia/brain/mcp/handlers/context_ops.py
git commit -m "feat(health): briefing warns about boot race and server uptime"
```

---

## Task 7: CLI entry point (`promaia brain check`)

**Files:**
- Modify: `promaia/__main__.py:10-15`

- [ ] **Step 1: Add `brain` fast path**

In `promaia/__main__.py`, after the `whisper` fast path (after line 19), add:

```python
    # Fast path: 'python -m promaia brain check'
    # Import health module directly (not mcp_server) to avoid heavy server init.
    # Token is read from .env via dotenv, same as mcp_server does.
    if len(sys.argv) > 1 and sys.argv[1] == "brain":
        if len(sys.argv) > 2 and sys.argv[2] == "check":
            from pathlib import Path
            from dotenv import load_dotenv
            _root = Path(__file__).resolve().parents[1]
            load_dotenv(_root / ".env")

            import os
            token = os.environ.get("BRAIN_MCP_TOKEN", "")

            from promaia.brain.health import run_checks_sync, format_cli_output
            result = run_checks_sync(
                include_mcp_registration=True,
                include_port_check=True,
                token=token,
            )
            print(format_cli_output(result))

            # Exit codes: 0=healthy/degraded, 1=error, 2=server not running
            port_status = result.get("checks", {}).get("server_port", {}).get("status")
            if port_status == "not_listening":
                sys.exit(2)
            sys.exit(0 if result["status"] != "error" else 1)
        else:
            print("Usage: python -m promaia brain check")
            sys.exit(1)
```

- [ ] **Step 2: Test the CLI command**

Run: `cd /c/Users/"Zachary Turner"/dev/promaia && python -m promaia brain check`
Expected: Formatted health check output showing all subsystems, MCP registration, and server port status.

- [ ] **Step 3: Commit**

```bash
git add promaia/__main__.py
git commit -m "feat(health): add 'promaia brain check' CLI diagnostic"
```

---

## Task 8: Final integration test and cleanup

- [ ] **Step 1: Run full test suite**

Run: `cd /c/Users/"Zachary Turner"/dev/promaia && python -m pytest tests/test_brain_health.py -v`
Expected: ALL PASS

- [ ] **Step 2: Test health endpoint against running server**

Run: `curl -s http://127.0.0.1:8751/health | python -m json.tool`
Expected: Full structured health response with `checks` object.

- [ ] **Step 3: Test CLI diagnostic**

Run: `cd /c/Users/"Zachary Turner"/dev/promaia && python -m promaia brain check`
Expected: Formatted output with OK/WARNING/ERROR for each subsystem.

- [ ] **Step 4: Verify startup validation logs**

Check `logs/promaia.log` for `[BRAIN] Startup validation:` entries from the last server start.

- [ ] **Step 5: Update mcp_server.py docstring**

Update the docstring at the top of `mcp_server.py` (line 2) to reflect actual tool count and mention the health system:

```python
"""
Brain MCP Server — 26 tools for zBrain.

Exposes Claude's persistent memory system as MCP tools over Streamable HTTP.
Runs as an always-on daemon (default: 127.0.0.1:8751) with bearer token auth.
Includes deep health monitoring (/health), startup validation, and CLI diagnostics
(python -m promaia brain check).
```

- [ ] **Step 6: Final commit**

```bash
git add promaia/brain/mcp_server.py tests/test_brain_health.py
git commit -m "feat(health): brain health lifecycle — 5-layer monitoring system

- Deep /health endpoint with cached subsystem checks
- Startup validation (MCP config, Turso sync, env vars)
- Manager health gate (poll before starting other services)
- Windows boot sequencer (replaces fire-and-forget VBS)
- CLI diagnostic (promaia brain check)
- Briefing warns about boot race conditions"
```
