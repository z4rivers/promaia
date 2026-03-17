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

    # Fast path: 'python -m promaia brain check'
    # Import health module directly (not mcp_server) to avoid heavy server init.
    # Token is read from .env via dotenv, same as mcp_server does.
    if len(sys.argv) > 1 and sys.argv[1] == "brain":
        if len(sys.argv) > 2 and sys.argv[2] == "check":
            from pathlib import Path
            from dotenv import load_dotenv
            _root = Path(__file__).resolve().parents[1]
            load_dotenv(_root / ".env")

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
            print("Usage: python -m promaia brain check")
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
