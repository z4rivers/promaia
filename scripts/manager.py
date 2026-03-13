"""
Promaia Unified Startup Manager.

Supervises Promaia subprocesses:
- FastAPI Web Server (uvicorn)
- Telegram Bot
- Agent Scheduler
- MuninnDB (optional local instance)

Implements restart limits, logging with prefixes, and unified shutdown.
"""
import sys
import os
import time
import subprocess
import threading
from pathlib import Path
from collections import deque
from datetime import datetime, timedelta

# Self-configure PYTHONPATH so this works when launched headlessly
# (e.g. from Task Scheduler via pythonw.exe -m promaia.manager)
_project_root = str(Path(__file__).parent.parent.absolute())
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)
os.environ.setdefault("PYTHONPATH", _project_root)

# Create logs directory
LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / "promaia.log"

MAX_RESTARTS = 5
RESTART_WINDOW_MINS = 10

class ManagedProcess:
    def __init__(self, name: str, cmd: list[str], prefix: str, shell: bool = False):
        self.name = name
        self.cmd = cmd
        self.prefix = prefix
        self.shell = shell
        self.process: subprocess.Popen | None = None
        self.restart_times: deque[datetime] = deque()
        self.should_stop = False
        self.log_file = open(LOG_FILE, "a", encoding="utf-8")

    def log(self, stream_name: str, line: str):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        msg = f"[{timestamp}] [{self.prefix}] {line.rstrip()}"
        print(msg)
        self.log_file.write(msg + "\n")
        self.log_file.flush()

    def _stream_reader(self, stream, stream_name: str):
        try:
            for line in iter(stream.readline, b''):
                try:
                    text_line = line.decode('utf-8', errors='replace')
                    self.log(stream_name, text_line)
                except Exception:
                    pass
        except Exception:
            pass

    def start(self):
        self.log("SYS", f"Starting {self.name}...")
        self.process = subprocess.Popen(
            self.cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            shell=self.shell,
            cwd=str(Path(__file__).parent.parent.absolute())
        )
        # Start a thread to read stdout/stderr (which are combined)
        t = threading.Thread(target=self._stream_reader, args=(self.process.stdout, "OUT"), daemon=True)
        t.start()

    def stop(self):
        self.should_stop = True
        if self.process:
            self.log("SYS", f"Stopping {self.name}...")
            if sys.platform == "win32":
                # Windows doesn't support SIGTERM well on subprocesses sometimes, but terminate() usually uses TerminateProcess
                self.process.terminate()
            else:
                self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
            self.log("SYS", f"{self.name} stopped.")

    def check_and_restart(self) -> bool:
        """Return False if max restarts exceeded, True otherwise."""
        if self.should_stop or self.process is None:
            return True

        retcode = self.process.poll()
        if retcode is not None:
            if retcode == 0:
                self.log("SYS", "Process exited cleanly (code 0). Not restarting.")
                self.should_stop = True
                return True
                
            self.log("SYS", f"Process exited with code {retcode}.")
            now = datetime.now()
            
            # Clean up old restart times
            cutoff = now - timedelta(minutes=RESTART_WINDOW_MINS)
            while self.restart_times and self.restart_times[0] < cutoff:
                self.restart_times.popleft()
            
            if len(self.restart_times) >= MAX_RESTARTS:
                self.log("SYS", f"CRITICAL: {self.name} exceeded {MAX_RESTARTS} restarts in {RESTART_WINDOW_MINS} minutes. Giving up.")
                return False
            
            self.restart_times.append(now)
            self.log("SYS", f"Restarting {self.name} (Restart {len(self.restart_times)}/{MAX_RESTARTS} in last {RESTART_WINDOW_MINS}m)...")
            
            # If it's a python script that uses PID files, we might occasionally need a small delay
            time.sleep(2)
            self.start()
            
        return True

def cleanup_existing_processes():
    """Kill any lingering Promaia processes to prevent port collisions (Windows native)."""
    import subprocess
    print("Pre-flight check: cleaning up any lingering processes...")
    
    # Signatures of processes we own
    target_signatures = [
        "uvicorn promaia.web.main:app",
        "promaia.telegram_cli",
        "promaia.agents.scheduler_cli"
    ]
    
    killed = 0
    try:
        # Use wmic to get command lines of all python processes
        output = subprocess.check_output(
            ["wmic", "process", "where", "name='python.exe'", "get", "ProcessId,CommandLine", "/format:csv"],
            text=True, stderr=subprocess.DEVNULL
        )
        
        my_pid = str(os.getpid())
        
        for line in output.splitlines():
            line = line.strip()
            if not line or "Node,CommandLine,ProcessId" in line:
                continue
                
            parts = line.split(",")
            if len(parts) >= 3:
                # Format is usually Node,CommandLine,ProcessId
                cmdline = parts[1]
                pid = parts[2]
                
                if pid == my_pid:
                    continue
                    
                if any(sig in cmdline for sig in target_signatures):
                    print(f"  Killing lingering python process (PID: {pid}) -> {cmdline[:60]}...")
                    subprocess.run(["taskkill", "/F", "/PID", pid], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    killed += 1
                    
        # Catch muninn.exe directly
        muninn_out = subprocess.check_output(
            ["tasklist", "/fi", "Imagename eq muninn.exe", "/fo", "csv", "/nh"],
            text=True, stderr=subprocess.DEVNULL
        )
        if "muninn.exe" in muninn_out.lower():
            print("  Killing lingering muninn.exe...")
            subprocess.run(["taskkill", "/F", "/IM", "muninn.exe"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            killed += 1
            
    except Exception as e:
        print(f"  Warning during cleanup: {e}")
        
    if killed > 0:
        print(f"Cleaned up {killed} old processes. Waiting 2 seconds for ports to free...")
        time.sleep(2)
    else:
        print("No lingering processes found.")

def main():
    print(f"Starting Promaia Unified Manager. Logging to {LOG_FILE.absolute()}")
    
    LOCK_FILE = Path.home() / ".promaia" / "manager.lock"
    LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
    if LOCK_FILE.exists():
        try:
            pid = int(LOCK_FILE.read_text().strip())
            os.kill(pid, 0)
            print(f"Manager is already running (PID {pid}). Exiting to prevent circular restart.")
            sys.exit(0)
        except Exception:
            pass # stale lock or not running
            
    LOCK_FILE.write_text(str(os.getpid()))
    
    try:
        # Kill anything already running to prevent address-in-use errors
        cleanup_existing_processes()
        
        # Check .env configuration
        env_path = Path(__file__).parent.parent / ".env"
        muninn_enabled = True
        telegram_enabled = True
        
        if env_path.exists():
            content = env_path.read_text(encoding="utf-8")
            if "MUNINN_LOCAL=false" in content.lower():
                muninn_enabled = False
                
            for line in content.splitlines():
                if line.strip().startswith("TELEGRAM_WEBHOOK_URL="):
                    val = line.split("=", 1)[1].strip().strip("'\"")
                    if val:
                        telegram_enabled = False
                        print(f"TELEGRAM_WEBHOOK_URL is set ({val}). Skipping local Telegram Bot process.")

        if muninn_enabled:
            print("Starting MuninnDB daemon...")
            subprocess.run(["muninn", "start"], shell=(sys.platform == "win32"), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        processes = [
            ManagedProcess("Web Server", [sys.executable, "-m", "uvicorn", "promaia.web.main:app", "--host", "0.0.0.0", "--port", "8000"], "WEB"),
            ManagedProcess("Agent Scheduler", [sys.executable, "-m", "promaia.agents.scheduler_cli", "start"], "SCHED")
        ]
        
        if telegram_enabled:
            # Insert before scheduler
            processes.insert(1, ManagedProcess("Telegram Bot", [sys.executable, "-m", "promaia.telegram_cli", "start"], "TG"))

        for p in processes:
            p.start()
            time.sleep(1) # stagger startups slightly

        while True:
            time.sleep(2)
            # If all processes exited cleanly, we should probably stop
            all_stopped = True
            for p in processes:
                if not p.should_stop:
                    all_stopped = False
                if not p.check_and_restart():
                    print(f"FATAL: {p.name} failed to stabilize. Shutting down entire system.")
                    sys.exit(1)
                    
            if all_stopped:
                print("All supervised processes have exited cleanly. Shutting down.")
                break

    except KeyboardInterrupt:
        print("\nReceived KeyboardInterrupt. Shutting down all processes...")
    finally:
        for p in reversed(processes):
            p.stop()
            
        if muninn_enabled:
            print("Stopping MuninnDB daemon...")
            subprocess.run(["muninn", "stop"], shell=(sys.platform == "win32"), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            
        if LOCK_FILE.exists():
            try:
                LOCK_FILE.unlink()
            except Exception:
                pass
                
        print("Shutdown complete.")

if __name__ == "__main__":
    main()
