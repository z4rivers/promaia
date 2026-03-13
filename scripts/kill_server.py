"""
kill_server.py — Nuclear option for zombie Promaia servers on Windows.

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


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000

    print(f"\n🔍 Scanning port {port}...")
    pids = get_listening_pids(port)

    if not pids:
        print(f"  ✅ Port {port} is already free. Nothing to kill.")
        return

    print(f"  Found {len(pids)} process(es): {pids}\n")
    print("💀 Killing all processes...")

    for pid in pids:
        kill_pid(pid)

    # Wait for sockets to release
    print("\n⏳ Waiting 2s for sockets to release...")
    time.sleep(2)

    # Verify
    remaining = get_listening_pids(port)
    if not remaining:
        print(f"  ✅ Port {port} is free. Safe to start server.")
    else:
        print(f"  ⚠️  PIDs still showing in netstat: {remaining}")
        print(f"     (May be TIME_WAIT ghosts — usually safe to proceed)")


if __name__ == "__main__":
    main()
