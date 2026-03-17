"""
Main entry point for the promaia package.

Intercepts 'dev' command before loading the heavy CLI to avoid
import issues in the full Josie/Rose CLI module tree.
"""
import sys


def main():
    # Fast path: 'python -m promaia dev' skips CLI entirely
    if len(sys.argv) > 1 and sys.argv[1] == "dev":
        from scripts.manager import main as run_dev
        run_dev()
        return

    # Fast path: 'python -m promaia whisper ...'
    if len(sys.argv) > 1 and sys.argv[1] == "whisper":
        from promaia.cli_whisper import whisper_main
        whisper_main(sys.argv[2:])
        return

    # Fast path: 'python -m promaia brain {start|stop|restart|status|check}'
    # Imports only lightweight lifecycle module (not mcp_server) to avoid heavy server init.
    if len(sys.argv) > 1 and sys.argv[1] == "brain":
        from pathlib import Path
        from dotenv import load_dotenv
        _root = Path(__file__).resolve().parents[1]
        load_dotenv(_root / ".env")

        subcmd = sys.argv[2] if len(sys.argv) > 2 else ""

        if subcmd == "start":
            from promaia.brain.lifecycle import start_brain, get_brain_status, format_status
            ok = start_brain(foreground=False, wait_healthy=True)
            if ok:
                print(format_status(get_brain_status()))
                sys.exit(0)
            else:
                print("ERROR: Brain failed to start or become healthy.")
                sys.exit(1)

        elif subcmd == "stop":
            from promaia.brain.lifecycle import stop_brain
            if stop_brain():
                print("Brain stopped.")
                sys.exit(0)
            else:
                print("ERROR: Failed to stop brain.")
                sys.exit(1)

        elif subcmd == "restart":
            from promaia.brain.lifecycle import restart_brain, get_brain_status, format_status
            if restart_brain():
                print(format_status(get_brain_status()))
                sys.exit(0)
            else:
                print("ERROR: Brain restart failed.")
                sys.exit(1)

        elif subcmd == "status":
            from promaia.brain.lifecycle import get_brain_status, format_status
            status = get_brain_status()
            print(format_status(status))
            sys.exit(0 if status["alive"] else 2)

        elif subcmd == "check":
            import os
            token = os.environ.get("BRAIN_MCP_TOKEN", "")

            from promaia.brain.health import run_checks_sync, format_cli_output
            result = run_checks_sync(
                include_mcp_registration=True,
                include_port_check=True,
                token=token,
            )
            print(format_cli_output(result))

            # Exit codes: 0=healthy/degraded, 1=error, 2=server not running
            port_status = result.get("checks", {}).get("server_port", {}).get("status")
            if port_status == "not_listening":
                sys.exit(2)
            sys.exit(0 if result["status"] != "error" else 1)

        else:
            print("Usage: python -m promaia brain {start|stop|restart|status|check}")
            sys.exit(1)

    # Full CLI — load cli.py (not cli/ package) via importlib
    import importlib.util
    import os

    cli_file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cli.py")
    spec = importlib.util.spec_from_file_location("promaia_cli_main", cli_file_path)
    cli_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cli_module)
    cli_module.main()


if __name__ == "__main__":
    main()
