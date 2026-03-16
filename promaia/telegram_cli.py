"""
Standalone CLI for the Telegram bot daemon.

Usage:
    python -m promaia.telegram_cli start    # Start bot daemon
    python -m promaia.telegram_cli stop     # Stop bot daemon
    python -m promaia.telegram_cli status   # Check status
"""
import sys
import os
import signal
import logging
import asyncio
from pathlib import Path

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


# PID file for daemon control
PID_FILE = Path.home() / ".promaia" / "telegram_bot.pid"


def write_pid_file():
    """Write the current process ID to the PID file."""
    PID_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(PID_FILE, "w", encoding='utf-8') as f:
        f.write(str(os.getpid()))
    logging.getLogger(__name__).info(f"PID file written: {PID_FILE}")


def read_pid_file():
    """Read the process ID from the PID file."""
    if not PID_FILE.exists():
        return None
    try:
        with open(PID_FILE, "r", encoding='utf-8') as f:
            return int(f.read().strip())
    except Exception as e:
        logging.getLogger(__name__).error(f"Error reading PID file: {e}")
        return None


def remove_pid_file():
    """Remove the PID file."""
    if PID_FILE.exists():
        PID_FILE.unlink()
        logging.getLogger(__name__).info(f"PID file removed: {PID_FILE}")


def is_bot_running():
    """Check if the bot is currently running."""
    pid = read_pid_file()
    if not pid:
        return False
    try:
        os.kill(pid, 0)  # Check if process exists
        return True
    except OSError:
        # Process doesn't exist, clean up stale PID file
        remove_pid_file()
        return False


def cmd_start():
    """Start the Telegram bot daemon."""
    if is_bot_running():
        pid = read_pid_file()
        print(f"Bot is already running (PID: {pid})")
        return

    write_pid_file()

    try:
        from promaia.telegram.bot import start_bot
        asyncio.run(start_bot())
    finally:
        remove_pid_file()


def cmd_stop():
    """Stop the running Telegram bot daemon."""
    if not is_bot_running():
        print("Bot is NOT running.")
        return

    pid = read_pid_file()
    try:
        os.kill(pid, signal.SIGTERM)
        print(f"Stop signal sent to bot (PID: {pid})")

        import time
        time.sleep(2)

        try:
            os.kill(pid, 0)
            print("Bot still running, forcing stop...")
            if sys.platform == "win32":
                os.kill(pid, signal.SIGTERM)  # Windows doesn't have SIGKILL
            else:
                os.kill(pid, signal.SIGKILL)
        except OSError:
            pass  # Process stopped

        remove_pid_file()
        print("Bot stopped.")

    except ProcessLookupError:
        print("Bot process not found (already stopped)")
        remove_pid_file()
    except Exception as e:
        print(f"Error stopping bot: {e}")


def cmd_status():
    """Check if the bot is running."""
    if is_bot_running():
        pid = read_pid_file()
        print(f"Bot is RUNNING (PID: {pid})")
    else:
        print("Bot is NOT running.")


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
    else:
        print(f"Unknown command: {cmd}")
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
