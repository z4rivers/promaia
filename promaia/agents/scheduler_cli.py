"""
Standalone CLI for the agent scheduler daemon.

Usage:
    python -m promaia.agents.scheduler_cli start    # Start daemon
    python -m promaia.agents.scheduler_cli stop     # Stop daemon
    python -m promaia.agents.scheduler_cli status   # Check status
    python -m promaia.agents.scheduler_cli run <name>  # Run one agent
"""
import sys
import logging

# Ensure UTF-8 output on Windows
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    datefmt="%H:%M:%S",
)

from promaia.utils.config import load_environment
load_environment()


def cmd_start():
    from promaia.agents.scheduler import run_scheduler_daemon_sync
    run_scheduler_daemon_sync()


def cmd_stop():
    from promaia.agents.scheduler import stop_scheduler, is_scheduler_running
    if not is_scheduler_running():
        print("No scheduler running.")
        return
    if stop_scheduler():
        print("Scheduler stopped.")
    else:
        print("Failed to stop scheduler.")


def cmd_status():
    from promaia.agents.scheduler import is_scheduler_running, read_pid_file
    from promaia.agents.agent_config import load_agents

    if is_scheduler_running():
        pid = read_pid_file()
        print(f"Scheduler is RUNNING (PID: {pid})")
    else:
        print("Scheduler is NOT running.")

    agents = load_agents()
    enabled = [a for a in agents if a.enabled]
    print(f"\nEnabled agents ({len(enabled)}):")
    for a in enabled:
        interval = f"every {a.interval_minutes}m" if a.interval_minutes else "schedule-based"
        last = a.last_run_at or "never"
        print(f"  {a.name} ({interval}) - last run: {last}")


def cmd_run(agent_name: str):
    import asyncio
    from promaia.agents.agent_config import get_agent
    from promaia.agents.executor import AgentExecutor

    agent = get_agent(agent_name)
    if not agent:
        print(f"Agent '{agent_name}' not found.")
        sys.exit(1)

    print(f"Running '{agent.name}'...")
    executor = AgentExecutor(agent)
    result = asyncio.run(executor.execute())

    if result["success"]:
        print(f"\nSuccess! ({result['metrics']['duration_seconds']:.1f}s)")
        if result.get("output"):
            print(f"\n{'='*60}")
            print(result["output"])
            print(f"{'='*60}")
    else:
        print(f"\nFailed: {result.get('error')}")
        sys.exit(1)


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "start":
        cmd_start()
    elif cmd == "stop":
        cmd_stop()
    elif cmd == "status":
        cmd_status()
    elif cmd == "run":
        if len(sys.argv) < 3:
            print("Usage: python -m promaia.agents.scheduler_cli run <agent-name>")
            sys.exit(1)
        cmd_run(sys.argv[2])
    else:
        print(f"Unknown command: {cmd}")
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
