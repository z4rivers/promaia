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
HEALTH_TIMEOUT = 30


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

    # Ensure lifecycle module is importable
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))

    # Phase 1: Start brain FIRST via lifecycle (fast — ~5-10s)
    # This ensures brain is accepting MCP connections before anything else.
    from promaia.brain.lifecycle import start_brain, read_pid

    brain_ok = start_brain(foreground=False, wait_healthy=True, timeout=20)
    brain_elapsed = time.time() - start

    if brain_ok:
        brain_pid = read_pid()
        write_status(
            healthy=True,
            boot_time=brain_elapsed,
            details={"brain_status": "ok", "brain_pid": brain_pid},
        )
    else:
        write_status(
            healthy=False,
            boot_time=brain_elapsed,
            details={"error": "brain failed to start or become healthy"},
        )

    # Phase 2: Start the manager for remaining services (--skip-brain since brain is up)
    creation_flags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
    subprocess.Popen(
        [sys.executable, "-m", "promaia", "dev", "--skip-brain"],
        cwd=str(PROJECT_ROOT),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=creation_flags,
    )


if __name__ == "__main__":
    main()
