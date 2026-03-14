"""
kill_server.py — FALLBACK nuclear option for zombie Promaia servers on Windows.

NOTE: The primary shutdown path is POST /api/shutdown (graceful).
      Only use this script when the graceful endpoint is unreachable
      (server is hung, port is locked, etc.)

Usage:
    python scripts/kill_server.py          # Kill all processes on port 8000
    python scripts/kill_server.py 3000     # Kill all processes on port 3000

Finds every PID listening on the target port via netstat,
kills the entire process tree, and verifies the port is free.
"""
import subprocess
import sys
import time
import re


def get_listening_pids(port: int) -> set[int]:
    """Find all PIDs with LISTENING sockets on the given port."""
    try:
        result = subprocess.run(
            ["netstat", "-ano"],
            capture_output=True, text=True, timeout=10
        )
    except Exception as e:
        print(f"  ❌ netstat failed: {e}")
        return set()

    pids = set()
    pattern = re.compile(rf"TCP\s+\S+:{port}\s+\S+\s+LISTENING\s+(\d+)")
    for line in result.stdout.splitlines():
        m = pattern.search(line)
        if m:
            pids.add(int(m.group(1)))
    return pids


def kill_pid(pid: int) -> bool:
    """Force-kill a process tree by PID. Returns True if successful."""
    try:
        result = subprocess.run(
            ["taskkill", "/F", "/T", "/PID", str(pid)],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            print(f"  ✅ Killed PID {pid} (and children)")
            return True
        elif "not found" in result.stderr.lower() or "not found" in result.stdout.lower():
            print(f"  ⚠️  PID {pid} already gone")
            return True
        else:
            print(f"  ❌ Failed to kill PID {pid}: {result.stderr.strip()}")
            return False
    except Exception as e:
        print(f"  ❌ taskkill error for PID {pid}: {e}")
        return False


def get_promaia_pids() -> set[int]:
    """Find ALL python processes with 'promaia' in their command line.
    
    This catches the orchestrator (python -m promaia dev), the web server
    (uvicorn promaia.web.main:app), the scheduler, telegram bot, etc.
    Excludes the current kill_server.py process itself.
    """
    my_pid = subprocess.os.getpid()
    try:
        result = subprocess.run(
            ["powershell", "-Command",
             "Get-WmiObject Win32_Process | Where-Object { $_.CommandLine -match 'promaia' -and $_.Name -eq 'python.exe' } | Select-Object -ExpandProperty ProcessId"],
            capture_output=True, text=True, timeout=10
        )
    except Exception as e:
        print(f"  ❌ Process scan failed: {e}")
        return set()
    
    pids = set()
    for line in result.stdout.strip().splitlines():
        line = line.strip()
        if line.isdigit():
            pid = int(line)
            if pid != my_pid:
                pids.add(pid)
    return pids


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000

    # Phase 1: Kill port holders (web server)
    print(f"\n🔍 Phase 1: Scanning port {port}...")
    pids = get_listening_pids(port)

    if pids:
        print(f"  Found {len(pids)} process(es) on port: {pids}")
        for pid in pids:
            kill_pid(pid)
    else:
        print(f"  ✅ Port {port} is already free.")

    # Phase 2: Kill ALL promaia processes (orchestrator, scheduler, telegram)
    # This prevents DB locks from lingering child processes
    print(f"\n🔍 Phase 2: Scanning for ALL promaia processes...")
    promaia_pids = get_promaia_pids()
    
    if promaia_pids:
        print(f"  Found {len(promaia_pids)} promaia process(es): {promaia_pids}")
        for pid in promaia_pids:
            kill_pid(pid)
    else:
        print(f"  ✅ No lingering promaia processes found.")

    # Wait for sockets + file handles to release
    print("\n⏳ Waiting 2s for sockets and DB locks to release...")
    time.sleep(2)

    # Verify port
    remaining = get_listening_pids(port)
    if not remaining:
        print(f"  ✅ Port {port} is free. Safe to start server.")
    else:
        print(f"  ⚠️  PIDs still showing in netstat: {remaining}")
        print(f"     (May be TIME_WAIT ghosts — usually safe to proceed)")
    
    # Verify no promaia processes remain
    remaining_promaia = get_promaia_pids()
    if not remaining_promaia:
        print(f"  ✅ All promaia processes terminated.")
    else:
        print(f"  ⚠️  Lingering promaia PIDs: {remaining_promaia}")


if __name__ == "__main__":
    main()
