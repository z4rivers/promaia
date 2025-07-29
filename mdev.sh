#!/bin/bash
# mdev - Quick navigation to Maia DEV directory and environment activation
# Usage: mdev (from anywhere) - navigates to maia-dev directory and activates venv

# The absolute path to your Maia DEV directory
PROMAIA_DIR="/Users/kb20250422/Documents/dev/promaia-dev"

# Navigate to the Maia Dev directory
if ! cd "$PROMAIA_DIR"; then
    echo -e "\033[31m[ERROR]\033[0m Failed to navigate to Maia Dev directory"
    exit 1
fi

# Check if virtual environment exists and activate it
if [ -d "$PROMAIA_DIR/venv" ]; then
    source "$PROMAIA_DIR/venv/bin/activate"
else
    echo -e "\033[31m[ERROR]\033[0m Virtual environment not found. Run 'python3 -m venv venv'"
    exit 1
fi

# Show brief ready status
echo -e "\033[32m🐙 Maia Dev ready\033[0m"

# Start a new shell to keep the environment active
exec $SHELL 