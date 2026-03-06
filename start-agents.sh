#!/usr/bin/env bash
# Start the Promaia agent scheduler daemon
# Run from project root: bash start-agents.sh
#
# Usage:
#   bash start-agents.sh          # Start daemon (foreground)
#   bash start-agents.sh stop     # Stop running daemon
#   bash start-agents.sh status   # Check daemon status
#   bash start-agents.sh test     # Run morning-briefing once

set -euo pipefail
cd "$(dirname "$0")"

export PYTHONIOENCODING=utf-8

# Load .env if present
if [ -f .env ]; then
    set -a
    source .env
    set +a
fi

# Unset CLAUDECODE so SDK can work as standalone daemon
unset CLAUDECODE

case "${1:-start}" in
    start)
        echo "Starting Promaia agent scheduler..."
        python -m promaia.agents.scheduler_cli start
        ;;
    stop)
        python -m promaia.agents.scheduler_cli stop
        ;;
    status)
        python -m promaia.agents.scheduler_cli status
        ;;
    test)
        AGENT="${2:-morning-briefing}"
        echo "Running agent '$AGENT' once..."
        python -m promaia.agents.scheduler_cli run "$AGENT"
        ;;
    *)
        echo "Usage: $0 {start|stop|status|test [agent-name]}"
        exit 1
        ;;
esac
