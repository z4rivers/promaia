"""
Promaia Watchdog — standalone health checker.

Runs independently of the Promaia server. Checks if Promaia is reachable
at localhost:8000. If down during waking hours (07:00–23:00 local time),
sends a Telegram alert.

Designed to run via Windows Task Scheduler every 60 minutes.
Does NOT import anything from promaia — completely self-contained.

Setup: see scripts/install_watchdog.ps1
"""

import os
import sys
import json
import urllib.request
import urllib.error
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Configuration — reads from .env in the project root
# ---------------------------------------------------------------------------

def _load_env() -> dict:
    """Load key=value pairs from the project root .env file."""
    env_path = Path(__file__).parent.parent / ".env"
    result = {}
    if not env_path.exists():
        return result
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        result[key.strip()] = val.strip().strip("'\"")
    return result


_env = _load_env()

PROMAIA_URL    = os.environ.get("PROMAIA_URL",        _env.get("PROMAIA_URL",        "http://localhost:8000"))
BOT_TOKEN      = os.environ.get("TELEGRAM_BOT_TOKEN", _env.get("TELEGRAM_BOT_TOKEN", ""))
CHAT_ID        = os.environ.get("TELEGRAM_CHAT_ID",   _env.get("TELEGRAM_WHITELIST",  "6269250506")).split(",")[0].strip()
WAKING_START   = int(os.environ.get("WATCHDOG_WAKE_START", "7"))   # 07:00
WAKING_END     = int(os.environ.get("WATCHDOG_WAKE_END",   "23"))  # 23:00


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

def is_promaia_up() -> bool:
    """Return True if Promaia /api/health responds 200."""
    try:
        req = urllib.request.Request(
            f"{PROMAIA_URL}/api/health",
            headers={"User-Agent": "promaia-watchdog/1.0"},
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status == 200
    except Exception:
        return False

def is_brain_up() -> bool:
    """Return True if Brain MCP /health responds 200 with ok or degraded status."""
    try:
        req = urllib.request.Request(
            "http://127.0.0.1:8751/health",
            headers={"User-Agent": "promaia-watchdog/1.0"},
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())
            return data.get("status") in ("ok", "degraded")
    except Exception:
        return False


def is_muninn_up() -> bool:
    """Return True if MuninnDB /api/health responds 200."""
    try:
        req = urllib.request.Request(
            "http://localhost:8475/api/health",
            headers={"User-Agent": "promaia-watchdog/1.0"},
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status == 200
    except Exception:
        return False


def is_waking_hours() -> bool:
    """Return True if current local time is within waking hours."""
    hour = datetime.now().hour
    return WAKING_START <= hour < WAKING_END


# ---------------------------------------------------------------------------
# Telegram notification
# ---------------------------------------------------------------------------

def send_telegram(message: str) -> bool:
    """Send a Telegram message via Bot API. Returns True on success."""
    if not BOT_TOKEN or not CHAT_ID:
        print("ERROR: TELEGRAM_BOT_TOKEN or TELEGRAM_WHITELIST not configured.", file=sys.stderr)
        return False

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = json.dumps({
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "Markdown",
    }).encode("utf-8")

    try:
        req = urllib.request.Request(
            url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status == 200
    except Exception as e:
        print(f"Telegram send failed: {e}", file=sys.stderr)
        return False


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def _restart_brain():
    """Restart brain via lifecycle (idempotent `brain start` command)."""
    import subprocess as _sp
    project_root = Path(__file__).parent.parent
    try:
        result = _sp.run(
            [sys.executable, "-m", "promaia", "brain", "start"],
            cwd=str(project_root),
            capture_output=True, text=True, timeout=30,
        )
        return result.returncode == 0, result.stdout.strip()
    except Exception as e:
        return False, str(e)


def main():
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    if not is_waking_hours():
        print(f"[{now}] Outside waking hours ({WAKING_START}:00–{WAKING_END}:00). Skipping.")
        return

    brain_up = is_brain_up()
    promaia_up = is_promaia_up()
    muninn_up = is_muninn_up()

    if brain_up and promaia_up and muninn_up:
        print(f"[{now}] Brain, Promaia, and MuninnDB are UP. All good.")
        return

    # Brain is the most critical — handle it first
    if not brain_up:
        print(f"[{now}] Brain is DOWN. Attempting auto-restart...")
        ok, detail = _restart_brain()

        message = (
            f"⚠️ *Brain MCP Server is OFFLINE*\n"
            f"Checked at {now}\n"
            f"Health endpoint: `http://127.0.0.1:8751/health`\n\n"
        )
        if ok:
            message += f"✅ Auto-restart succeeded.\n{detail}"
            print(f"[{now}] Brain restarted successfully.")
        else:
            message += f"❌ Auto-restart failed: {detail}"
            print(f"[{now}] Brain restart FAILED: {detail}")

        send_telegram(message)

    if not promaia_up:
        message = (
            f"⚠️ *Promaia Web Server is OFFLINE*\n"
            f"Checked at {now}\n"
            f"Health endpoint: `{PROMAIA_URL}/api/health`\n\n"
            f"Attempting auto-restart via manager.py...\n"
        )

        try:
            import subprocess
            import shutil
            project_root = Path(__file__).parent.parent
            pythonw = shutil.which("pythonw")
            if pythonw:
                env = os.environ.copy()
                env["PYTHONPATH"] = str(project_root)
                subprocess.Popen(
                    [pythonw, "-m", "promaia.manager"],
                    cwd=str(project_root),
                    env=env,
                )
                message += "✅ Launched pythonw -m promaia.manager"
            else:
                message += "❌ Failed to restart: pythonw.exe not found on PATH."
        except Exception as e:
            message += f"❌ Failed to restart: {e}"

        send_telegram(message)

    if not muninn_up and promaia_up:
        message = (
            f"⚠️ *MuninnDB is OFFLINE*\n"
            f"Checked at {now}\n"
            f"Promaia server is running, but the cognitive memory substrate is unreachable.\n"
            f"Voice memory, text search, and AI association are severely degraded.\n"
        )
        send_telegram(message)


if __name__ == "__main__":
    main()
