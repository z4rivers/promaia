"""
Main entry point for the maia package.
"""
# Import main from the main CLI file (not the cli package)
import sys
import os

# Add the maia directory to the path
maia_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, maia_dir)

# Import main from cli.py directly
import importlib.util
cli_file_path = os.path.join(maia_dir, 'cli.py')
spec = importlib.util.spec_from_file_location("cli", cli_file_path)
cli_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cli_module)

main = cli_module.main

if __name__ == "__main__":
    main() 