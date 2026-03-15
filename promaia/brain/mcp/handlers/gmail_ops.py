import asyncio
import json
import logging
import uuid
import numpy as np
from email.utils import parsedate_to_datetime
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional
from mcp.types import TextContent
from promaia.brain import engine
from promaia.brain.extraction import extract_actions, extract_insights
from promaia.brain.core.memory_pipeline import capture_memory
from promaia.brain.onboarding import (
    start_onboarding, get_onboarding_status,
    mark_channel_progress, get_profile_coverage,
    complete_onboarding, EXPECTED_FIELDS,
)
from promaia.brain.channels.interview import (
    get_interview_state,
    get_next_question,
    mark_question_answered,
)
from promaia.brain.mcp.core_context import get_db, get_vector_mgr, get_muninn_client

logger = logging.getLogger(__name__)




async def _handle_gmail_scan(args: dict) -> list[TextContentManager]:
    """Scan Gmail inbox for cleanup, triage, and intelligence."""
    db = get_db()
    account = args.get("account")
    days_back = int(args.get("days_back", 30))
    max_emails = int(args.get("max_emails", 200))
    mode = args.get("mode", "full")
    before = args.get("before")

    try:
        from promaia.brain.channels.gmail_read import run_gmail_scan, discover_accounts
    except Exception as e:
        logger.error(f"Gmail module import failed: {e}", exc_info=True)
        return [TextContent(type="text", text=f"Gmail scan error: {e}")]

    # Show available accounts if none connected
    accounts = await asyncio.to_thread(discover_accounts)
    if not accounts:
        return [TextContent(type="text", text="No Gmail tokens found. Run OAuth setup first.")]

    try:
        result = await asyncio.to_thread(
            run_gmail_scan,
            account=account,
            days_back=days_back,
            max_emails=max_emails,
            mode=mode,
            db=db if mode in ("intelligence", "full") else None,
            before=before,
        )
    except Exception as e:
        logger.error(f"Gmail scan failed: {e}", exc_info=True)
        return [TextContent(type="text", text=f"Gmail scan error: {e}")]

    if result.get("error"):
        return [TextContent(type="text", text=f"Gmail scan: {result['error']}")]

    # Load known relationships for cross-referencing
    known_contacts = {}
    try:
        rows = db.fetch_all(
            "SELECT field, value FROM profile WHERE category = 'relationships'"
        )
        for row in rows:
            val = row[1] if isinstance(row[1], dict) else {}
            # Extract emails/names from relationship records
            for key in ("email", "name"):
                if key in val:
                    known_contacts[val[key].lower()] = row[0]
            # Handle email_contacts list
            if isinstance(row[1], list):
                for c in row[1]:
                    if isinstance(c, dict) and c.get("email"):
                        known_contacts[c["email"].lower()] = c.get("name", row[0])
    except Exception as e:
        logger.debug(f"Could not load known contacts: {e}")

    # Format results
    lines = [f"## Gmail Scan Results (mode: {mode})\n"]

    summary = result.get("summary", {})
    lines.append(f"**Accounts scanned:** {summary.get('accounts_scanned', 0)}")
    lines.append(f"**Total emails scanned:** {summary.get('total_emails_scanned', 0)}")

    if summary.get("total_junk_identified"):
        lines.append(f"**Total junk identified:** {summary['total_junk_identified']}")

    for email, acct in result.get("accounts", {}).items():
        if "error" in acct:
            lines.append(f"\n### {email}\nError: {acct['error']}")
            continue

        lines.append(f"\n### {acct.get('email', email)}")
        lines.append(f"Emails scanned: {acct.get('emails_scanned', 0)}")

        # Layer 1: Cleanup categories
        cats = acct.get("categories", {})
        if any(cats.values()):
            lines.append("\n**Email Categories:**")
            lines.append(f"  Human mail: {cats.get('human', 0)}")
            lines.append(f"  Newsletters: {cats.get('newsletter', 0)}")
            lines.append(f"  Promotions: {cats.get('promotion', 0)}")
            lines.append(f"  Automated: {cats.get('automated', 0)}")
            total = sum(cats.values())
            junk = total - cats.get("human", 0)
            if total > 0:
                lines.append(f"  **Junk ratio: {junk}/{total} ({100*junk//total}%)**")

        # Unsubscribe candidates
        unsubs = acct.get("unsubscribe_candidates", [])
        if unsubs:
            lines.append(f"\n**Top Unsubscribe Candidates** ({len(unsubs)} senders):")
            for u in unsubs[:10]:
                relation = known_contacts.get(u['email'].lower(), '')
                tag = f" (KNOWN: {relation})" if relation else ""
                lines.append(f"  - {u['email']}{tag} ({u['count']} emails)")

        # Layer 2: Attention items
        attention = acct.get("attention_needed", [])
        if attention:
            lines.append(f"\n**Needs Attention** ({len(attention)} items):")
            for a in attention[:10]:
                status = "[unread]" if a.get("unread") else "[read]"
                sender = a['from'] or ''
                relation = known_contacts.get(sender.lower(), '')
                tag = f" (KNOWN: {relation})" if relation else ""
                lines.append(f"  - {status} {sender}{tag}: {a['subject']}")

        # Layer 3: Intelligence
        if acct.get("contacts_found"):
            lines.append(f"\nContacts found: {acct['contacts_found']}")
        if acct.get("fields_updated"):
            lines.append(f"Profile fields updated: {acct['fields_updated']}")

    # Log event
    try:
        db.execute(
            """
            INSERT INTO events (type, payload, source)
            VALUES ('gmail_scan', ?, 'background')
            """,
            (
                json.dumps({
                    "mode": mode,
                    "accounts_scanned": summary.get("accounts_scanned", 0),
                    "total_emails_scanned": summary.get("total_emails_scanned", 0),
                    "total_junk_identified": summary.get("total_junk_identified", 0),
                }),
            ),
        )
    except Exception as e:
        logger.warning(f"Could not log gmail_scan event: {e}")

    return [TextContent(type="text", text="\n".join(lines))]

async def _handle_gmail_query(args: dict) -> list[TextContent]:
    """Query stored Gmail content from the gmail_content table."""
    db = get_db()
    query_text = args.get("query", "")
    sender = args.get("sender", "")
    days_back = args.get("days_back", 30)
    limit = min(args.get("limit", 20), 50)

    conditions = []
    params = []

    if query_text:
        conditions.append("(subject LIKE ? OR body_snippet LIKE ? OR sender_name LIKE ?)")
        params.extend([f"%{query_text}%", f"%{query_text}%", f"%{query_text}%"])

    if sender:
        conditions.append("(sender_email LIKE ? OR sender_name LIKE ?)")
        params.extend([f"%{sender}%", f"%{sender}%"])

    if days_back:
        conditions.append("email_date >= datetime('now', ?)")
        params.append(f"-{int(days_back)} days")

    where_clause = " AND ".join(conditions) if conditions else "1=1"
    sql = f"""
        SELECT subject, sender_email, sender_name, body_snippet,
               email_date, is_unread
        FROM gmail_content
        WHERE {where_clause}
        ORDER BY email_date DESC
        LIMIT ?
    """
    params.append(limit)

    try:
        rows = db.fetch_all(sql, tuple(params))
    except Exception as e:
        return [TextContent(type="text", text=f"Gmail query error: {e}")]

    if not rows:
        parts = []
        if query_text:
            parts.append(f"matching '{query_text}'")
        if sender:
            parts.append(f"from '{sender}'")
        return [TextContent(
            type="text",
            text=f"No emails found {' '.join(parts)} in the last {days_back} days."
        )]

    lines = [f"**Gmail Query Results** ({len(rows)} emails)\n"]
    for r in rows:
        date = (r.get("email_date") or "")[:10] or "?"
        sender_name = r.get("sender_name") or ""
        sender_email = r.get("sender_email") or ""
        sender_display = f"{sender_name} <{sender_email}>" if sender_name else sender_email or "?"
        snippet = (r.get("body_snippet") or "")[:120]
        unread_tag = " [unread]" if r.get("is_unread") else ""
        lines.append(f"- **{r.get('subject') or '(no subject)'}**{unread_tag}")
        lines.append(f"  From: {sender_display} | {date}")
        if snippet:
            lines.append(f"  > {snippet}")
        lines.append("")

    return [TextContent(type="text", text="\n".join(lines))]

