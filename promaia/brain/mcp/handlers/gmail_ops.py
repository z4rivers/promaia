import json
import logging
import uuid
import numpy as np
import psycopg2.extras
from mcp.types import TextContent
from datetime import datetime, timezone
from promaia.storage.postgres_db import PostgresDB
from promaia.storage.vector_db import VectorDBManager
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
from promaia.brain.mcp.core_context import SESSION_ID, get_db, get_vector_mgr, get_muninn_client
from promaia.brain.mcp.handlers.common import _get_or_create_domain_id, _days_ago, _fmt_ts, _today_str

logger = logging.getLogger(__name__)

# Helpers
def _get_or_create_domain_id(db, domain_name: str) -> int:
    existing = db.fetch_one("SELECT id FROM brain.domains WHERE name = %s", (domain_name,))
    if existing: return existing['id']
    return db.insert_returning("INSERT INTO brain.domains (name) VALUES (%s) RETURNING id", (domain_name,))

def _days_ago(ts) -> float:
    if ts is None: return 0.0
    now = datetime.now(timezone.utc)
    if isinstance(ts, str):
        try: ts = datetime.fromisoformat(ts)
        except ValueError: return 0.0
    if getattr(ts, 'tzinfo', None) is None: ts = ts.replace(tzinfo=timezone.utc)
    return (now - ts).total_seconds() / 86400.0

def _fmt_ts(ts) -> str:
    if ts is None: return "unknown"
    if isinstance(ts, str):
        try: ts = datetime.fromisoformat(ts)
        except ValueError: return str(ts)
    if getattr(ts, 'tzinfo', None) is None: ts = ts.replace(tzinfo=timezone.utc)
    return ts.strftime("%Y-%m-%d %H:%M UTC")

def _today_str() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


async def _handle_gmail_scan(args: dict) -> list[TextContent]:
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
    accounts = discover_accounts()
    if not accounts:
        return [TextContent(type="text", text="No Gmail tokens found. Run OAuth setup first.")]

    try:
        result = run_gmail_scan(
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
            "SELECT field, value FROM brain.profile WHERE category = 'relationships'"
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
            INSERT INTO brain.events (type, payload, source, session_id)
            VALUES ('gmail_scan', %s::jsonb, 'onboarding', %s)
            """,
            (
                json.dumps({
                    "mode": mode,
                    "accounts_scanned": summary.get("accounts_scanned", 0),
                    "total_emails_scanned": summary.get("total_emails_scanned", 0),
                    "total_junk_identified": summary.get("total_junk_identified", 0),
                }),
                SESSION_ID,
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
        conditions.append(
            "(subject ILIKE %s OR message_content ILIKE %s OR body_snippet ILIKE %s)"
        )
        like = f"%{query_text}%"
        params.extend([like, like, like])

    if sender:
        conditions.append("sender_email ILIKE %s")
        params.append(f"%{sender}%")

    if days_back:
        conditions.append(
            "email_date >= (NOW() - INTERVAL '%s days')::text"
        )
        params.append(days_back)

    where = " AND ".join(conditions) if conditions else "TRUE"
    sql = f"""
        SELECT subject, sender_email, sender_name, email_date,
               body_snippet, thread_id, is_unread, gmail_labels
        FROM gmail_content
        WHERE {where}
        ORDER BY email_date DESC
        LIMIT %s
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
        date = r.get("email_date", "")[:10] if r.get("email_date") else "?"
        sender_display = r.get("sender_name") or r.get("sender_email", "?")
        unread = " [unread]" if r.get("is_unread") else ""
        snippet = (r.get("body_snippet") or "")[:120]
        lines.append(f"- **{r.get('subject', '(no subject)')}**{unread}")
        lines.append(f"  From: {sender_display} | {date}")
        if snippet:
            lines.append(f"  > {snippet}")
        lines.append("")

    return [TextContent(type="text", text="\n".join(lines))]

