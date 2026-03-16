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
