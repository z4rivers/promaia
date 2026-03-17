"""
Brain MCP Server Lifecycle Management.

Single source of truth for brain process lifecycle — PID tracking,
status file, start/stop/restart, health gating. Used by:
  - CLI: python -m promaia brain {start|stop|restart|status}
  - Manager: scripts/manager.py (supervisor loop)
  - Windows autostart: scripts/startup.py (boot sequence)

Lightweight — stdlib only (no heavy imports from promaia).
"""
import json
import os
import signal
import subprocess
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PROMAIA_DIR = Path.home() / ".promaia"
PID_FILE = PROMAIA_DIR / "brain.pid"
STATUS_FILE = PROMAIA_DIR / "brain.status"

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8751

HEALTH_POLL_INTERVAL = 1.0   # seconds between health polls
HEALTH_TIMEOUT = 20           # seconds to wait for brain to become healthy
STOP_TIMEOUT = 5              # seconds to wait for graceful stop
STOP_POLL_INTERVAL = 0.5      # seconds between process alive checks during stop

# Crash loop protection
MAX_CRASHES = 5
CRASH_WINDOW_SECS = 600       # 10 minutes

PROJECT_ROOT = Path(__file__).resolve().parents[2]


# ---------------------------------------------------------------------------
# PID file management
# ---------------------------------------------------------------------------

def write_pid(pid: int = None) -> None:
    """Write current (or given) PID to the brain PID file."""
    PROMAIA_DIR.mkdir(parents=True, exist_ok=True)
    PID_FILE.write_text(str(pid or os.getpid()), encoding="utf-8")


def read_pid() -> int | None:
    """Read PID from the brain PID file. Returns None if missing or invalid."""
    if not PID_FILE.exists():
        return None
    try:
        return int(PID_FILE.read_text(encoding="utf-8").strip())
    except (ValueError, OSError):
        return None


def remove_pid() -> None:
    """Remove the brain PID file if it exists."""
    try:
        PID_FILE.unlink(missing_ok=True)
    except OSError:
        pass


def _is_pid_alive(pid: int) -> bool:
    """Raw check: is this PID alive? No side effects.

    On Windows, os.kill(pid, 0) fails for detached processes with WinError 87.
    Use tasklist as a reliable cross-platform fallback.
    """
    if sys.platform == "win32":
        try:
            output = subprocess.check_output(
                ["tasklist", "/fi", f"PID eq {pid}", "/fo", "csv", "/nh"],
                text=True, stderr=subprocess.DEVNULL,
            )
            # tasklist returns the process info or "INFO: No tasks..."
            return str(pid) in output
        except Exception:
            return False
    else:
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False


def is_brain_alive(pid: int | None = None) -> bool:
    """Check if the brain process is alive. Cleans up stale PID file if not."""
    pid = pid or read_pid()
    if not pid:
        return False
    if _is_pid_alive(pid):
        return True
    # Process is dead — clean up stale PID file
    remove_pid()
    return False


def is_port_free(port: int = DEFAULT_PORT) -> bool:
    """Check if the brain port is free (nothing listening)."""
    return find_brain_pid_by_port(port) is None


def wait_for_port_free(port: int = DEFAULT_PORT, timeout: int = STOP_TIMEOUT) -> bool:
    """Wait until the port is free or timeout. Returns True if free."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if is_port_free(port):
            return True
        time.sleep(STOP_POLL_INTERVAL)
    return is_port_free(port)


# ---------------------------------------------------------------------------
# Status file management
# ---------------------------------------------------------------------------

def write_status(state: str, **kwargs) -> None:
    """Write a complete status file."""
    PROMAIA_DIR.mkdir(parents=True, exist_ok=True)
    data = {
        "pid": os.getpid(),
        "state": state,
        "timestamp": datetime.now().isoformat(),
        **kwargs,
    }
    STATUS_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def read_status() -> dict | None:
    """Read the brain status file. Returns None if missing or invalid."""
    if not STATUS_FILE.exists():
        return None
    try:
        return json.loads(STATUS_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def update_status(**kwargs) -> None:
    """Merge fields into the existing status file."""
    current = read_status() or {}
    current.update(kwargs)
    current["timestamp"] = datetime.now().isoformat()
    PROMAIA_DIR.mkdir(parents=True, exist_ok=True)
    STATUS_FILE.write_text(json.dumps(current, indent=2), encoding="utf-8")


# ---------------------------------------------------------------------------
# Health gating
# ---------------------------------------------------------------------------

def _health_url(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> str:
    return f"http://{host}:{port}/health"


def check_health(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT,
                  timeout: float = 2.0) -> dict | None:
    """Single health check. Returns parsed JSON or None on failure."""
    try:
        req = urllib.request.Request(
            _health_url(host, port),
            headers={"User-Agent": "brain-lifecycle/1.0"},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read())
    except Exception:
        return None


def wait_for_healthy(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT,
                     timeout: int = HEALTH_TIMEOUT) -> dict | None:
    """Poll /health until brain reports ok or degraded, or timeout.

    Returns the health JSON on success, None on timeout.
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        health = check_health(host, port)
        if health and health.get("status") in ("ok", "degraded"):
            return health
        time.sleep(HEALTH_POLL_INTERVAL)
    return None


# ---------------------------------------------------------------------------
# Port detection (fallback when PID file is stale or missing)
# ---------------------------------------------------------------------------

def find_brain_pid_by_port(port: int = DEFAULT_PORT) -> int | None:
    """Find the PID listening on the brain port via netstat. Windows-only fallback."""
    try:
        output = subprocess.check_output(
            ["netstat", "-ano"], text=True, stderr=subprocess.DEVNULL,
        )
        for line in output.splitlines():
            if f":{port}" in line and "LISTENING" in line:
                parts = line.split()
                if parts:
                    return int(parts[-1])
    except Exception:
        pass
    return None


# ---------------------------------------------------------------------------
# Process control
# ---------------------------------------------------------------------------

def start_brain(foreground: bool = False, wait_healthy: bool = True,
                timeout: int = HEALTH_TIMEOUT,
                host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> bool:
    """Start the brain MCP server.

    Idempotent — returns True immediately if brain is already running and healthy.

    Args:
        foreground: If True, run in the current process (blocks).
        wait_healthy: If True, poll /health until brain is confirmed ready.
        timeout: Max seconds to wait for health.
        host: Brain bind host.
        port: Brain bind port.

    Returns:
        True if brain is running and healthy (or started successfully).
        False on failure.
    """
    # Check if already running
    existing_pid = read_pid()
    if existing_pid and is_brain_alive(existing_pid):
        health = check_health(host, port)
        if health and health.get("status") in ("ok", "degraded"):
            return True
        # Process alive but not healthy — give it a moment
        if wait_healthy:
            health = wait_for_healthy(host, port, timeout=min(timeout, 10))
            if health:
                return True
        # Alive but unhealthy — don't start a second one
        return False

    # Clean up stale PID file if process is dead
    if existing_pid:
        remove_pid()

    # Check for rogue process on our port
    rogue_pid = find_brain_pid_by_port(port)
    if rogue_pid:
        # Something else is on our port — could be a brain without a PID file
        health = check_health(host, port)
        if health and "zbrain" in health.get("service", ""):
            # It's actually our brain, just missing PID file — adopt it
            write_pid(rogue_pid)
            update_status(state="healthy", pid=rogue_pid, adopted=True)
            return True
        # Unknown process on our port — report and fail
        print(f"ERROR: Port {port} is occupied by PID {rogue_pid} (not brain). Cannot start.")
        return False

    # Double-check port is truly free (catches TIME_WAIT sockets)
    if not is_port_free(port):
        print(f"WARNING: Port {port} appears occupied (possibly TIME_WAIT). Waiting...")
        if not wait_for_port_free(port, timeout=10):
            print(f"ERROR: Port {port} still not free after 10s. Cannot start.")
            return False

    if foreground:
        # Run brain in the current process (used by mcp_server.py itself)
        # This doesn't return until brain stops
        return _run_foreground(host, port)

    # Start brain as a background subprocess
    return _start_background(host, port, wait_healthy, timeout)


def _start_background(host: str, port: int,
                      wait_healthy: bool, timeout: int) -> bool:
    """Spawn brain as a detached background process."""
    cmd = [sys.executable, "-m", "promaia.brain.mcp_server"]
    env = os.environ.copy()
    env.setdefault("PYTHONPATH", str(PROJECT_ROOT))
    env["BRAIN_MCP_HOST"] = host
    env["BRAIN_MCP_PORT"] = str(port)

    kwargs = {
        "cwd": str(PROJECT_ROOT),
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
        "env": env,
    }

    if sys.platform == "win32":
        kwargs["creationflags"] = (
            subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
        )

    proc = subprocess.Popen(cmd, **kwargs)

    # Write PID for the newly spawned process
    write_pid(proc.pid)
    update_status(state="starting", pid=proc.pid,
                  started_at=datetime.now().isoformat())

    if not wait_healthy:
        return True

    health = wait_for_healthy(host, port, timeout)
    if health:
        tool_count = health.get("checks", {}).get("tools", {}).get("count", "?")
        update_status(
            state="healthy",
            pid=proc.pid,
            started_at=datetime.now().isoformat(),
            last_health_check=datetime.now().isoformat(),
            last_health_result=health.get("status", "ok"),
            tools_count=tool_count,
            crash_count=0,
        )
        return True

    # Timeout — brain didn't become healthy
    # Check if process is even still alive
    if proc.poll() is not None:
        print(f"ERROR: Brain process exited immediately (code {proc.returncode}).")
        remove_pid()
        update_status(state="crashed", exit_code=proc.returncode)
    else:
        print(f"WARNING: Brain started (PID {proc.pid}) but not healthy after {timeout}s.")
        update_status(state="starting", pid=proc.pid)

    return False


def _run_foreground(host: str, port: int) -> bool:
    """Placeholder — foreground mode is handled by mcp_server.py directly."""
    return True


def stop_brain(timeout: int = STOP_TIMEOUT, port: int = DEFAULT_PORT) -> bool:
    """Stop the brain process gracefully.

    1. Read PID from file (or detect by port)
    2. Send SIGTERM / taskkill
    3. Wait for process to exit
    4. Force kill if timeout
    5. Clean up PID file and status

    Returns True if brain is stopped, False if we couldn't stop it.
    """
    pid = read_pid()

    # If no PID file, check port for an orphaned process
    if not pid:
        pid = find_brain_pid_by_port(port)
        if not pid:
            # Nothing to stop
            update_status(state="stopped")
            return True

    if not is_brain_alive(pid):
        remove_pid()
        update_status(state="stopped")
        return True

    # Send termination signal
    if sys.platform == "win32":
        # On Windows, headless Python processes ignore WM_CLOSE (taskkill without /F).
        # Use /F directly — uvicorn doesn't have a graceful Windows shutdown handler.
        subprocess.run(
            ["taskkill", "/F", "/T", "/PID", str(pid)],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
    else:
        try:
            os.kill(pid, signal.SIGTERM)
        except OSError:
            pass

    # Wait for process to fully exit AND port to free up
    deadline = time.time() + timeout
    while time.time() < deadline:
        pid_gone = not _is_pid_alive(pid)
        port_free = is_port_free(port)
        if pid_gone and port_free:
            remove_pid()
            update_status(state="stopped")
            return True
        time.sleep(STOP_POLL_INTERVAL)

    # Final check — report what's still stuck
    pid_alive = _is_pid_alive(pid)
    port_occupied = not is_port_free(port)

    if pid_alive:
        print(f"WARNING: Process {pid} still alive after force kill + {timeout}s wait.")
    if port_occupied:
        occupant = find_brain_pid_by_port(port)
        print(f"WARNING: Port {port} still occupied by PID {occupant}.")

    if not pid_alive and not port_occupied:
        remove_pid()
        update_status(state="stopped")
        return True

    return False


def restart_brain(timeout: int = HEALTH_TIMEOUT,
                  host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> bool:
    """Stop the brain, then start it fresh. Returns True if new instance is healthy."""
    stopped = stop_brain(port=port)
    if not stopped:
        print("ERROR: Failed to stop brain. Cannot restart.")
        return False

    # Wait for port to be fully released (critical on Windows — TIME_WAIT can linger)
    if not wait_for_port_free(port, timeout=10):
        print(f"ERROR: Port {port} still occupied after stop. Cannot restart.")
        return False

    return start_brain(
        foreground=False, wait_healthy=True,
        timeout=timeout, host=host, port=port,
    )


# ---------------------------------------------------------------------------
# Composite status (for CLI display)
# ---------------------------------------------------------------------------

def get_brain_status(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> dict:
    """Get a comprehensive brain status for display.

    Returns a dict with:
        pid, alive, state, uptime, port_listening,
        health, tools_count, crash_count, started_at
    """
    pid = read_pid()
    alive = is_brain_alive(pid) if pid else False
    status_data = read_status() or {}

    # Always try the health check — brain may be running even without a PID file
    health = check_health(host, port)
    port_listening = health is not None

    # If no PID from file, try port detection
    if not pid or not alive:
        port_pid = find_brain_pid_by_port(port)
        if port_pid:
            pid = port_pid
            alive = _is_pid_alive(port_pid)
            if alive and not PID_FILE.exists():
                # Adopt the orphaned brain — restore PID file
                write_pid(port_pid)

    # Compute state
    if alive and health and health.get("status") in ("ok", "degraded"):
        state = "HEALTHY" if health["status"] == "ok" else "DEGRADED"
    elif alive and port_listening:
        state = "STARTING"
    elif alive:
        state = "ALIVE (not responding)"
    else:
        state = "STOPPED"

    # Compute uptime
    uptime_sec = health.get("uptime_sec") if health else None
    if uptime_sec is None and status_data.get("started_at"):
        try:
            started = datetime.fromisoformat(status_data["started_at"])
            uptime_sec = (datetime.now() - started).total_seconds()
        except (ValueError, TypeError):
            uptime_sec = None

    # Tools count
    tools_count = None
    if health:
        tools_count = health.get("checks", {}).get("tools", {}).get("count")
    if tools_count is None:
        tools_count = status_data.get("tools_count")

    return {
        "pid": pid,
        "alive": alive,
        "state": state,
        "uptime_sec": uptime_sec,
        "port": port,
        "port_listening": port_listening,
        "health_status": health.get("status") if health else None,
        "tools_count": tools_count,
        "crash_count": status_data.get("crash_count", 0),
        "started_at": status_data.get("started_at"),
        "last_health_check": datetime.now().isoformat() if health else status_data.get("last_health_check"),
    }


def format_status(status: dict) -> str:
    """Format status dict for CLI display."""
    lines = [
        "Brain MCP Server",
        "=" * 30,
        f"State:     {status['state']}",
        f"PID:       {status['pid'] or 'N/A'}",
        f"Uptime:    {_format_uptime(status.get('uptime_sec'))}",
        f"Port:      {status['port']} ({'LISTENING' if status['port_listening'] else 'NOT LISTENING'})",
        f"Tools:     {status['tools_count'] or 'N/A'} registered",
        f"Health:    {status['health_status'] or 'N/A'}",
        f"Crashes:   {status['crash_count']}",
    ]
    return "\n".join(lines)


def _format_uptime(seconds: float | None) -> str:
    """Format seconds into human-readable uptime."""
    if seconds is None:
        return "N/A"
    seconds = int(seconds)
    if seconds < 60:
        return f"{seconds}s"
    minutes = seconds // 60
    secs = seconds % 60
    if minutes < 60:
        return f"{minutes}m {secs}s"
    hours = minutes // 60
    mins = minutes % 60
    if hours < 24:
        return f"{hours}h {mins}m {secs}s"
    days = hours // 24
    hrs = hours % 24
    return f"{days}d {hrs}h {mins}m"
