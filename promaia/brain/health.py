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
    if os.environ.get("RAILWAY_ENVIRONMENT") or os.environ.get("PYTHON_ENV") == "production":
        return "production"
    return "local"


def aggregate_status(
    checks: dict[str, dict],
    critical: list[str],
    non_critical: list[str],
) -> str:
    for key in critical:
        if key in checks and checks[key].get("status") not in ("ok", "listening"):
            return "error"
    for key in non_critical:
        if key in checks and checks[key].get("status") not in ("ok", "listening"):
            return "degraded"
    return "ok"


async def check_database(db=None) -> dict[str, Any]:
    try:
        if db is None:
            from promaia.storage.db_factory import get_db
            db = get_db()
        db.execute("SELECT 1")
        from promaia.storage.libsql_db import get_libsql_db, _USING_REAL_LIBSQL
        libsql_db = get_libsql_db()
        using_turso = getattr(libsql_db, '_using_turso', False)
        backend = "turso" if using_turso else ("libsql" if _USING_REAL_LIBSQL else "sqlite")
        sync_ok = libsql_db.try_sync()
        sync_age = libsql_db.sync_age()
        result = {
            "status": "ok",
            "backend": backend,
            "sync_ok": sync_ok,
            "last_sync_age_sec": round(sync_age, 1),
        }
        if using_turso and not sync_ok:
            result["status"] = "error"
        elif using_turso and sync_age > 300:
            result["sync_stale"] = True
        return result
    except Exception as e:
        return {"status": "error", "backend": "unknown", "error": str(e)}


async def check_vector_db(vector_mgr=None) -> dict[str, Any]:
    try:
        if vector_mgr is None:
            from promaia.storage.vector_db import VectorDBManager
            vector_mgr = VectorDBManager()
        return {"status": "ok", "error": None}
    except Exception as e:
        return {"status": "error", "error": str(e)}


async def check_muninn() -> dict[str, Any]:
    try:
        from promaia.brain.muninn import get_muninn
        m = await get_muninn()
        if m is not None:
            return {"status": "ok", "reason": None}
        return {"status": "unavailable", "reason": "get_muninn() returned None"}
    except Exception as e:
        return {"status": "unavailable", "reason": str(e)}


async def check_env_vars() -> dict[str, Any]:
    env = detect_environment()
    required = ["GOOGLE_API_KEY", "BRAIN_MCP_TOKEN"]
    if env == "production":
        required.extend(["TURSO_DATABASE_URL", "TURSO_AUTH_TOKEN"])
    missing = [k for k in required if not os.environ.get(k, "").strip()]
    return {"status": "ok" if not missing else "error", "missing": missing}


async def check_tools(server=None) -> dict[str, Any]:
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
    issues = []
    configs_found = []
    expected_url = f"http://{host}:{port}/mcp/"
    user_config = Path.home() / ".claude" / ".mcp.json"
    project_config = _project_root / ".mcp.json"

    for label, path in [("user-level", user_config), ("project-level", project_config)]:
        if not path.exists():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            brain = data.get("mcpServers", {}).get("brain")
            if brain is None:
                continue
            configs_found.append(label)
            if "command" in brain or brain.get("type") == "stdio":
                issues.append(
                    f"{label} ({path}): configured as stdio "
                    f"(command: {brain.get('command', '?')} {' '.join(brain.get('args', []))}). "
                    f"Expected HTTP URL."
                )
                continue
            url = brain.get("url", "")
            if url != expected_url:
                issues.append(f"{label} ({path}): URL is '{url}', expected '{expected_url}'")
            if expected_token:
                auth = brain.get("headers", {}).get("Authorization", "")
                expected_auth = f"Bearer {expected_token}"
                if auth != expected_auth:
                    issues.append(
                        f"{label} ({path}): token mismatch "
                        f"(config has '{auth[:20]}...', server expects '{expected_auth[:20]}...')"
                    )
        except json.JSONDecodeError:
            issues.append(f"{label} ({path}): invalid JSON")
        except Exception as e:
            issues.append(f"{label} ({path}): read error — {e}")

    if len(configs_found) == 0:
        issues.append("No Claude MCP config has a 'brain' entry")
    elif len(configs_found) > 1:
        issues.append("Duplicate brain registration in both user-level and project-level configs")

    return {
        "status": "ok" if not issues else "mismatch",
        "configs_found": configs_found,
        "issues": issues,
        "expected": {"url": expected_url, "token_prefix": expected_token[:8] + "..." if expected_token else ""},
    }


async def check_server_port(port: int = 8751) -> dict[str, Any]:
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
    env = detect_environment()
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

    if include_mcp_registration and env == "local":
        results["mcp_registration"] = await check_mcp_registration(host, port, token)
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
    return asyncio.run(run_checks(**kwargs))


def format_cli_output(result: dict) -> str:
    lines = [
        "zBrain Health Check",
        "===================",
        f"Environment:    {result['environment']} (detected)",
    ]
    checks = result.get("checks", {})

    db = checks.get("database", {})
    db_detail = db.get("backend", "?")
    if db.get("backend") == "turso":
        sync_age = db.get("last_sync_age_sec", "?")
        db_detail += f", sync {sync_age}s ago"
        if db.get("sync_stale"):
            db_detail += " (STALE)"
    _add_check_line(lines, "Database", db_detail, db.get("status", "?"))

    vdb = checks.get("vector_db", {})
    _add_check_line(lines, "Vector DB", "initialized", vdb.get("status", "?"))

    mun = checks.get("muninn", {})
    mun_detail = mun.get("reason") or "reachable"
    _add_check_line(lines, "MuninnDB", mun_detail, mun.get("status", "?"))

    ev = checks.get("env_vars", {})
    ev_detail = "all present" if ev.get("status") == "ok" else f"missing: {', '.join(ev.get('missing', []))}"
    _add_check_line(lines, "Env vars", ev_detail, ev.get("status", "?"))

    tools = checks.get("tools", {})
    _add_check_line(lines, "Tools", f"{tools.get('count', '?')} registered", tools.get("status", "?"))

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

    port_check = checks.get("server_port")
    if port_check:
        lines.append("")
        lines.append("Server Process:")
        pid = port_check.get("pid", "?")
        status = port_check.get("status", "?")
        status_str = "OK" if status == "listening" else "NOT RUNNING"
        lines.append(f"  Port 8751:    {status.upper()} (PID {pid}) ............. {status_str}")

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
    status_str = "OK" if status == "ok" else status.upper()
    padding = "." * max(1, 45 - len(name) - len(detail))
    lines.append(f"{name:15s} {detail} {padding} {status_str}")
