#!/usr/bin/env python3
"""
Migration script to populate workspaces_used for existing conversations.

This script reads the conversation history from ~/.maia_chat_history.json
and extracts workspace information from each thread's context, then updates
the database accordingly.
"""

import json
import sqlite3
import os
from pathlib import Path


def extract_workspaces_from_context(context):
    """Extract workspace names from a thread's context object."""
    workspaces_used = set()

    if not context:
        return None

    # Add primary workspace if specified
    if context.get('workspace'):
        workspaces_used.add(context.get('workspace'))

    # Extract workspaces from source specifications
    for source in context.get('sources', []):
        base_name = source.split(':')[0]  # Remove day specification
        if '.' in base_name:
            workspace = base_name.split('.')[0]
            workspaces_used.add(workspace)

    # Add from resolved_workspace if different
    if context.get('resolved_workspace'):
        workspaces_used.add(context.get('resolved_workspace'))

    # Return as sorted JSON array
    if workspaces_used:
        return json.dumps(sorted(list(workspaces_used)))
    return None


def migrate_conversations():
    """Migrate existing conversations to include workspace information."""
    history_path = Path.home() / '.maia_chat_history.json'
    db_path = 'data/hybrid_metadata.db'

    if not history_path.exists():
        print(f"❌ Chat history file not found: {history_path}")
        return

    if not Path(db_path).exists():
        print(f"❌ Database not found: {db_path}")
        return

    # Load chat history
    print(f"📖 Loading chat history from {history_path}...")
    with open(history_path, 'r') as f:
        history_data = json.load(f)

    threads = history_data.get('threads', [])
    print(f"Found {len(threads)} threads in history")

    # Connect to database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    updated_count = 0
    skipped_count = 0
    not_in_db_count = 0

    for thread in threads:
        thread_id = thread.get('id')
        if not thread_id:
            continue

        # Check if this thread exists in the database
        cursor.execute(
            "SELECT page_id, workspaces_used FROM conversation_content WHERE thread_id = ?",
            (thread_id,)
        )
        result = cursor.fetchone()

        if not result:
            not_in_db_count += 1
            continue

        page_id, current_workspaces = result

        # Skip if already has workspace data
        if current_workspaces:
            skipped_count += 1
            continue

        # Extract workspace information from context
        context = thread.get('context', {})
        workspaces_json = extract_workspaces_from_context(context)

        if workspaces_json:
            # Update the database
            cursor.execute(
                "UPDATE conversation_content SET workspaces_used = ? WHERE page_id = ?",
                (workspaces_json, page_id)
            )

            workspaces = json.loads(workspaces_json)
            print(f"✓ Updated '{thread.get('name', 'Untitled')}' with workspaces: {workspaces}")
            updated_count += 1
        else:
            print(f"⚠ No workspace info found for '{thread.get('name', 'Untitled')}'")
            skipped_count += 1

    # Commit changes
    conn.commit()
    conn.close()

    print(f"\n📊 Migration complete:")
    print(f"  ✓ Updated: {updated_count}")
    print(f"  ⊘ Skipped (already had data): {skipped_count}")
    print(f"  ⚠ Not in database: {not_in_db_count}")


if __name__ == '__main__':
    migrate_conversations()
