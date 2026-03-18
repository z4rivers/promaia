#!/usr/bin/env python3
"""Claude Code UserPromptSubmit hook — checks Whispers inbox for pending signals.

Fires on every user message. If pending signals exist, they're returned as
additional context that Claude sees alongside the user's message.

Register in .claude/settings.local.json:
{
    "hooks": {
        "UserPromptSubmit": [{
            "type": "command",
            "command": "python scripts/hooks/signal_check.py"
        }]
    }
}
"""

import os
import sys
import json
import sqlite3

def main():
    db_path = os.environ.get("WHISPERS_DB_PATH", "./whispers.db")

    if not os.path.exists(db_path):
        return  # No whispers DB yet — nothing to check

    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute(
            "SELECT uuid, from_agent, msg_type, subject, priority, created_at "
            "FROM messages WHERE to_agent = 'claude-code' AND status = 'new' "
            "ORDER BY CASE priority "
            "  WHEN 'system' THEN 0 WHEN 'flash' THEN 1 "
            "  WHEN 'priority' THEN 2 ELSE 3 END, "
            "created_at ASC LIMIT 10"
        )
        rows = cursor.fetchall()
        conn.close()

        if not rows:
            return  # No pending signals

        lines = [f"Pending Whispers ({len(rows)}):"]
        for r in rows:
            priority_tag = f"[{r['priority'].upper()}]" if r['priority'] != 'routine' else ""
            lines.append(
                f"  {priority_tag} From {r['from_agent']}: \"{r['subject']}\" ({r['msg_type']}, {r['created_at']})"
            )

        # Output to stdout — Claude Code captures this as context
        print("\n".join(lines))

    except Exception:
        pass  # Fail silently — don't block user input

if __name__ == "__main__":
    main()
