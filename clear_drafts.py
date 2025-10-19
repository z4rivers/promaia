#!/usr/bin/env python3
"""Quick script to clear pending email drafts for testing."""
import sqlite3

db_path = "data/hybrid_metadata.db"

with sqlite3.connect(db_path) as conn:
    cursor = conn.cursor()
    
    # Show current drafts
    cursor.execute("SELECT draft_id, inbound_subject, status FROM email_drafts WHERE status = 'pending'")
    drafts = cursor.fetchall()
    
    if not drafts:
        print("No pending drafts to clear")
    else:
        print(f"Found {len(drafts)} pending draft(s):")
        for draft_id, subject, status in drafts:
            print(f"  - {subject[:50]}")
        
        # Delete them
        cursor.execute("DELETE FROM email_drafts WHERE status = 'pending'")
        conn.commit()
        print(f"\n✅ Cleared {len(drafts)} pending draft(s)")
        print("\nNow run: maia mail -p -v")

