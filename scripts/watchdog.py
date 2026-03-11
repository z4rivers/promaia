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

def main():
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    if not is_waking_hours():
        print(f"[{now}] Outside waking hours ({WAKING_START}:00–{WAKING_END}:00). Skipping.")
        return

    promaia_up = is_promaia_up()
    muninn_up = is_muninn_up()

    if promaia_up and muninn_up:
        print(f"[{now}] Promaia and MuninnDB are UP. All good.")
        return

    # Something is down during waking hours — alert
    if not promaia_up:
        message = (
            f"⚠️ *Promaia is OFFLINE*\n"
            f"Checked at {now}\n"
            f"Health endpoint: `{PROMAIA_URL}/api/health`\n\n"
            f"Attempting auto-restart via manager.py...\n"
        )
        
        try:
            import subprocess
            script_dir = Path(__file__).parent
            vbs_script = script_dir / "start_promaia_hidden.vbs"
            if vbs_script.exists():
                subprocess.Popen(["wscript.exe", str(vbs_script)], cwd=str(script_dir.parent))
                message += "✅ Executed start_promaia_hidden.vbs"
            else:
                message += "❌ Failed to restart: start_promaia_hidden.vbs not found."
        except Exception as e:
            message += f"❌ Failed to restart: {e}"
    else:
        message = (
            f"⚠️ *MuninnDB is OFFLINE*\n"
            f"Checked at {now}\n"
            f"Promaia server is running, but the cognitive memory substrate is unreachable.\n"
            f"Voice memory, text search, and AI association are severely degraded.\n"
        )

    sent = send_telegram(message)
    if sent:
        status_msg = "Promaia DOWN" if not promaia_up else "Muninn DOWN"
        print(f"[{now}] {status_msg} — Telegram alert sent.")
    else:
        print(f"[{now}] Alert FAILED to send.", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
