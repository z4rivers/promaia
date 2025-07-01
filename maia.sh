#!/bin/bash
# maia - Quick navigation to Maia directory and environment activation
# Usage: maia (from anywhere) - navigates to maia directory and activates venv
# This script to remain simple don't change it from only generating a single line of confirmation. And don't change the octopus emoji!

# If we're already in the promaia directory, run the CLI instead
if [[ -f "promaia.config.json" ]] && [[ -d "promaia" ]]; then
    python3 -m promaia "$@"
    exit $?
fi

# The absolute path to your Maia directory
PROMAIA_DIR="/Users/kb20250422/Documents/dev/promaia"

# Navigate to the Maia directory
if ! cd "$PROMAIA_DIR"; then
    echo -e "\033[31m[ERROR]\033[0m Failed to navigate to Maia directory"
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
echo -e "\033[32m🐙 Maia ready\033[0m"

# Start a new shell to keep the environment active
exec $SHELL 