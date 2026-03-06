"""
Gmail read channel -- inbox scanning for cleanup, triage, and profile extraction.

Connects directly to Gmail API via OAuth token files in credentials/default/.
Does NOT depend on GmailConnector (avoids import chain issues).

Supports multiple accounts -- discovers all gmail_token*.json files automatically.

Layers:
    1. Cleanup   -- categorize inbox (junk, newsletters, promotions, human mail)
    2. Triage    -- surface emails that warrant attention
    3. Intelligence -- extract contacts, patterns, topics for brain profile
    4. Composition  -- (future) write/send on behalf

Usage via MCP:
    mcp__brain__gmail_scan(account="zachary4rivers", days_back=30, max_emails=200)
"""
import json
import logging
import os
import re
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
CONFIDENCE_EMAIL = 0.5
_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_CREDS_DIR = _PROJECT_ROOT / "credentials" / "default"

# Known junk patterns
_NOREPLY_PATTERNS = [
    "noreply", "no-reply", "donotreply", "do-not-reply",
    "notifications", "notify", "mailer-daemon", "postmaster",
    "newsletter", "marketing", "updates@", "info@", "support@",
    "billing@", "receipts@", "orders@", "shipping@",
]

_PROMOTION_DOMAINS = [
    "marketing", "promo", "deals", "offers", "sale",
    "campaign", "mailchimp", "sendgrid", "constantcontact",
    "hubspot", "klaviyo", "mailgun", "amazonses",
]


# ---------------------------------------------------------------------------
# Account discovery
# ---------------------------------------------------------------------------

def discover_accounts() -> Dict[str, Path]:
    """Find all Gmail token files in credentials/default/.

    Returns:
        dict mapping account label -> token file path
        e.g. {"zachary4rivers": Path(...), "zackayak": Path(...)}
    """
    accounts = {}
    if not _CREDS_DIR.exists():
        return accounts

    for f in _CREDS_DIR.glob("gmail_token*.json"):
        # gmail_token.json -> "default"
        # gmail_token_zackayak.json -> "zackayak"
        name = f.stem  # gmail_token or gmail_token_zackayak
        if name == "gmail_token":
            # Try to read the token to get the actual email
            label = _label_from_token(f) or "default"
        else:
            label = name.replace("gmail_token_", "")
        accounts[label] = f

    return accounts


def _label_from_token(token_path: Path) -> Optional[str]:
    """Try to extract email prefix from token file."""
    try:
        with open(token_path) as f:
            data = json.load(f)
        # Token doesn't always have the email, but we can check via API
        return None
    except Exception:
        return None


def _get_gmail_service(token_path: Path):
    """Build a Gmail API service from a token file."""
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build

    with open(token_path) as f:
        token_data = json.load(f)

    # Add client info for token refresh
    creds_file = _CREDS_DIR / "gmail_credentials.json"
    if creds_file.exists():
        with open(creds_file) as f:
            client_data = json.load(f).get("installed", {})
        token_data.setdefault("client_id", client_data.get("client_id"))
        token_data.setdefault("client_secret", client_data.get("client_secret"))
        token_data.setdefault("token_uri", client_data.get("token_uri", "https://oauth2.googleapis.com/token"))

    creds = Credentials.from_authorized_user_info(token_data)

    # Refresh if expired
    if creds.expired and creds.refresh_token:
        from google.auth.transport.requests import Request
        creds.refresh(Request())
        # Save refreshed token
        with open(token_path, "w") as f:
            f.write(creds.to_json())

    return build("gmail", "v1", credentials=creds)


def get_account_email(token_path: Path) -> str:
    """Get the email address associated with a token."""
    service = _get_gmail_service(token_path)
    profile = service.users().getProfile(userId="me").execute()
    return profile["emailAddress"]


# ---------------------------------------------------------------------------
# Main scan function
# ---------------------------------------------------------------------------

def run_gmail_scan(
    account: Optional[str] = None,
    days_back: int = 30,
    max_emails: int = 200,
    mode: str = "full",
    db=None,
    before: Optional[str] = None,
) -> Dict[str, Any]:
    """Scan Gmail inbox and return categorized results.

    Args:
        account: Account label (e.g. "zackayak") or None for all accounts.
        days_back: How many days back to scan.
        max_emails: Max emails per account.
        mode: "cleanup" (Layer 1), "triage" (Layer 2), "intelligence" (Layer 3), or "full" (all).
        db: PostgresDB instance for profile storage (Layer 3).
        before: Optional date string (YYYY/MM/DD) to scan only before this date.

    Returns:
        dict with scan results per account.
    """
    accounts = discover_accounts()
    if not accounts:
        return {"error": "No Gmail tokens found in credentials/default/. Run OAuth setup first."}

    # Filter to requested account
    if account:
        # Match by label or partial match
        matched = {k: v for k, v in accounts.items() if account.lower() in k.lower()}
        if not matched:
            return {"error": f"No account matching '{account}'. Available: {list(accounts.keys())}"}
        accounts = matched

    results = {"accounts": {}, "summary": {}}

    for label, token_path in accounts.items():
        try:
            service = _get_gmail_service(token_path)
            email = service.users().getProfile(userId="me").execute()["emailAddress"]

            account_result = _scan_account(
                service=service,
                email=email,
                days_back=days_back,
                max_emails=max_emails,
                mode=mode,
                db=db,
                before=before,
            )
            account_result["email"] = email
            results["accounts"][email] = account_result

        except Exception as e:
            logger.error(f"Scan failed for {label}: {e}", exc_info=True)
            results["accounts"][label] = {"error": str(e)}

    # Build summary across accounts
    total_scanned = sum(
        a.get("emails_scanned", 0)
        for a in results["accounts"].values()
        if isinstance(a, dict) and "error" not in a
    )
    total_junk = sum(
        sum(v for k, v in a.get("categories", {}).items() if k != "human")
        for a in results["accounts"].values()
        if isinstance(a, dict) and "error" not in a
    )
    results["summary"] = {
        "accounts_scanned": len([a for a in results["accounts"].values() if "error" not in a]),
        "total_emails_scanned": total_scanned,
        "total_junk_identified": total_junk,
    }

    return results


def _scan_account(
    service,
    email: str,
    days_back: int,
    max_emails: int,
    mode: str,
    db,
    before: Optional[str] = None,
) -> Dict[str, Any]:
    """Scan a single Gmail account."""
    result = {
        "emails_scanned": 0,
        "categories": {"human": 0, "newsletter": 0, "promotion": 0, "automated": 0, "junk": 0},
        "contacts_found": 0,
        "fields_updated": 0,
        "top_senders": [],
        "attention_needed": [],
        "unsubscribe_candidates": [],
    }

    # Fetch messages
    threads = _fetch_recent_messages(service, days_back, max_emails, before_date=before)
    result["emails_scanned"] = len(threads)

    if not threads:
        return result

    # Layer 1: Cleanup -- categorize everything
    if mode in ("cleanup", "full"):
        _categorize_emails(threads, result)

    # Layer 2: Triage -- find what needs attention
    if mode in ("triage", "full"):
        _find_attention_items(threads, result, email)

    # Layer 3: Intelligence -- extract profile data
    if mode in ("intelligence", "full") and db:
        _extract_profile_intelligence(threads, result, db)

    return result


# ---------------------------------------------------------------------------
# Message fetching
# ---------------------------------------------------------------------------

def _fetch_recent_messages(service, days_back: int, max_emails: int, before_date: Optional[str] = None) -> List[Dict]:
    """Fetch recent email metadata from Gmail API."""
    # Calculate after_date relative to before_date (not now) when scanning historical windows
    if before_date:
        try:
            anchor = datetime.strptime(before_date, "%Y/%m/%d").replace(tzinfo=timezone.utc)
        except ValueError:
            anchor = datetime.now(timezone.utc)
    else:
        anchor = datetime.now(timezone.utc)
    after_date = (anchor - timedelta(days=days_back)).strftime("%Y/%m/%d")
    query = f"after:{after_date}"
    if before_date:
        query += f" before:{before_date}"

    messages = []
    page_token = None

    while len(messages) < max_emails:
        try:
            kwargs = {
                "userId": "me",
                "q": query,
                "maxResults": min(100, max_emails - len(messages)),
            }
            if page_token:
                kwargs["pageToken"] = page_token

            response = service.users().messages().list(**kwargs).execute()
            msg_list = response.get("messages", [])

            if not msg_list:
                break

            for msg_stub in msg_list:
                if len(messages) >= max_emails:
                    break
                try:
                    msg = service.users().messages().get(
                        userId="me",
                        id=msg_stub["id"],
                        format="metadata",
                        metadataHeaders=[
                            "From", "To", "Cc", "Subject", "Date",
                            "List-Unsubscribe", "Precedence", "X-Mailer",
                        ],
                    ).execute()
                    messages.append(_parse_message(msg))
                except Exception as e:
                    logger.warning(f"Could not fetch message {msg_stub['id']}: {e}")

            page_token = response.get("nextPageToken")
            if not page_token:
                break

        except Exception as e:
            logger.error(f"Message list request failed: {e}")
            break

    return messages


def _parse_message(msg_data: Dict) -> Dict:
    """Parse a Gmail message into a metadata-only structure."""
    headers = {}
    for h in msg_data.get("payload", {}).get("headers", []):
        headers[h["name"].lower()] = h["value"]

    sender = _extract_email_parts(headers.get("from", ""))
    recipients = []
    for field in ("to", "cc"):
        if headers.get(field):
            for addr in headers[field].split(","):
                recipients.append(_extract_email_parts(addr.strip()))

    # Parse date
    date = None
    if headers.get("date"):
        try:
            from email.utils import parsedate_to_datetime
            dt = parsedate_to_datetime(headers["date"])
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            date = dt
        except Exception:
            pass

    return {
        "id": msg_data.get("id"),
        "thread_id": msg_data.get("threadId"),
        "labels": msg_data.get("labelIds", []),
        "snippet": msg_data.get("snippet", "")[:150],
        "sender": sender,
        "recipients": recipients,
        "subject": headers.get("subject", ""),
        "date": date,
        "has_unsubscribe": bool(headers.get("list-unsubscribe")),
        "precedence": headers.get("precedence", ""),
        "x_mailer": headers.get("x-mailer", ""),
    }


def _extract_email_parts(addr_str: str) -> Dict[str, str]:
    """Extract name and email from 'Name <email>' format."""
    addr_str = addr_str.strip()
    match = re.match(r'^"?([^"<]*)"?\s*<([^>]+)>', addr_str)
    if match:
        return {"name": match.group(1).strip(), "email": match.group(2).strip().lower()}
    return {"name": "", "email": addr_str.lower()}


# ---------------------------------------------------------------------------
# Layer 1: Cleanup -- categorize emails
# ---------------------------------------------------------------------------

def _categorize_emails(messages: List[Dict], result: Dict) -> None:
    """Categorize each email and identify cleanup opportunities."""
    sender_counts = Counter()
    unsubscribe_senders = Counter()

    for msg in messages:
        category = _classify_message(msg)
        result["categories"][category] += 1

        sender_email = msg["sender"].get("email", "")
        sender_name = msg["sender"].get("name", "") or sender_email
        sender_counts[sender_email] += 1

        if msg["has_unsubscribe"] and category != "human":
            unsubscribe_senders[sender_email] += 1

    # Top senders (volume)
    result["top_senders"] = [
        {"email": email, "count": count}
        for email, count in sender_counts.most_common(20)
    ]

    # Unsubscribe candidates (non-human senders with unsubscribe headers, sorted by volume)
    result["unsubscribe_candidates"] = [
        {"email": email, "count": count}
        for email, count in unsubscribe_senders.most_common(30)
    ]


def _classify_message(msg: Dict) -> str:
    """Classify a single message into a category."""
    sender_email = msg["sender"].get("email", "").lower()
    sender_name = msg["sender"].get("name", "").lower()
    subject = msg["subject"].lower()

    # Check for automated/noreply patterns
    for pattern in _NOREPLY_PATTERNS:
        if pattern in sender_email:
            if msg["has_unsubscribe"]:
                return "newsletter"
            return "automated"

    # Check for promotion domains
    for pattern in _PROMOTION_DOMAINS:
        if pattern in sender_email:
            return "promotion"

    # Gmail's own categorization via labels
    labels = msg.get("labels", [])
    if "CATEGORY_PROMOTIONS" in labels:
        return "promotion"
    if "CATEGORY_UPDATES" in labels:
        return "automated"
    if "CATEGORY_SOCIAL" in labels:
        return "automated"
    if "CATEGORY_FORUMS" in labels:
        return "newsletter"

    # Has unsubscribe header = likely newsletter/bulk
    if msg["has_unsubscribe"]:
        return "newsletter"

    # Precedence: bulk or list = automated
    if msg["precedence"] in ("bulk", "list"):
        return "newsletter"

    # Default: probably human
    return "human"


# ---------------------------------------------------------------------------
# Layer 2: Triage -- find what needs attention
# ---------------------------------------------------------------------------

def _find_attention_items(messages: List[Dict], result: Dict, user_email: str) -> None:
    """Identify emails that warrant the user's attention."""
    attention = []

    for msg in messages:
        category = _classify_message(msg)
        if category != "human":
            continue

        # Skip emails FROM the user (sent mail)
        if msg["sender"].get("email", "").lower() == user_email.lower():
            continue

        # Human email, not from self -- potentially needs attention
        labels = msg.get("labels", [])
        is_unread = "UNREAD" in labels
        is_starred = "STARRED" in labels
        is_important = "IMPORTANT" in labels

        if is_unread or is_starred or is_important:
            attention.append({
                "from": msg["sender"].get("name") or msg["sender"].get("email"),
                "subject": msg["subject"],
                "date": msg["date"].isoformat() if msg["date"] else "",
                "unread": is_unread,
                "starred": is_starred,
                "snippet": msg["snippet"],
            })

    # Sort by date, most recent first
    attention.sort(key=lambda x: x.get("date", ""), reverse=True)
    result["attention_needed"] = attention[:25]


# ---------------------------------------------------------------------------
# Layer 3: Intelligence -- profile extraction
# ---------------------------------------------------------------------------

def _extract_profile_intelligence(messages: List[Dict], result: Dict, db) -> None:
    """Extract contacts, communication patterns, and topics for brain profile."""
    # Contacts
    contact_freq: Dict[str, Dict] = {}
    for msg in messages:
        if _classify_message(msg) != "human":
            continue

        for contact in [msg["sender"]] + msg["recipients"]:
            email = contact.get("email", "").lower()
            if not email or "@" not in email:
                continue
            if email not in contact_freq:
                contact_freq[email] = {
                    "name": contact.get("name", ""),
                    "email": email,
                    "frequency": 0,
                    "last_contact": None,
                }
            contact_freq[email]["frequency"] += 1
            if contact.get("name") and not contact_freq[email]["name"]:
                contact_freq[email]["name"] = contact["name"]
            if msg["date"]:
                existing = contact_freq[email]["last_contact"]
                if existing is None or msg["date"] > existing:
                    contact_freq[email]["last_contact"] = msg["date"]

    result["contacts_found"] = len(contact_freq)

    if contact_freq:
        top_contacts = sorted(contact_freq.values(), key=lambda c: c["frequency"], reverse=True)[:15]
        for c in top_contacts:
            if c["last_contact"]:
                c["last_contact"] = c["last_contact"].isoformat()
        _upsert_profile(db, "relationships", "email_contacts", top_contacts, CONFIDENCE_EMAIL)
        result["fields_updated"] = result.get("fields_updated", 0) + 1

    # Activity timing
    hours = [msg["date"].hour for msg in messages if msg["date"]]
    if hours:
        hour_counts = Counter(hours)
        peak = [h for h, _ in hour_counts.most_common(4)]
        peak.sort()
        _upsert_profile(
            db, "energy_patterns", "email_activity_hours",
            ", ".join(f"{h}:00" for h in peak),
            CONFIDENCE_EMAIL,
        )
        result["fields_updated"] = result.get("fields_updated", 0) + 1

    # Subject topics (human emails only)
    subjects = [msg["subject"] for msg in messages if _classify_message(msg) == "human" and msg["subject"]]
    if subjects:
        words = _extract_keywords(subjects)
        if words:
            top_topics = [w for w, _ in Counter(words).most_common(15)]
            _upsert_profile(db, "context", "email_topics", top_topics, CONFIDENCE_EMAIL)
            result["fields_updated"] = result.get("fields_updated", 0) + 1


def _extract_keywords(subjects: List[str]) -> List[str]:
    """Extract meaningful keywords from subject lines."""
    stop_words = {
        "re", "fwd", "fw", "the", "a", "an", "is", "it", "to", "for", "of",
        "and", "in", "on", "at", "by", "with", "from", "this", "that", "your",
        "you", "we", "our", "my", "me", "be", "was", "were", "been", "are",
        "have", "has", "had", "do", "does", "did", "will", "would", "could",
        "should", "can", "may", "might", "not", "no", "but", "or", "if",
        "about", "up", "out", "just", "so", "all", "get", "got",
    }
    words = []
    for subject in subjects:
        cleaned = re.sub(r"^(Re|Fwd|Fw):\s*", "", subject, flags=re.IGNORECASE).strip()
        for word in cleaned.split():
            word = re.sub(r"[^\w]", "", word).lower()
            if word and len(word) > 2 and word not in stop_words:
                words.append(word)
    return words


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _upsert_profile(db, category: str, field: str, value: Any, confidence: float) -> None:
    """Upsert a profile field in brain.profile."""
    value_json = json.dumps(value, default=str)
    try:
        db.execute(
            """
            INSERT INTO brain.profile (category, field, value, confidence, source, updated_at)
            VALUES (%s, %s, %s::jsonb, %s, 'inferred', NOW())
            ON CONFLICT (category, field) DO UPDATE SET
                value = EXCLUDED.value,
                confidence = EXCLUDED.confidence,
                source = EXCLUDED.source,
                updated_at = NOW()
            """,
            (category, field, value_json, confidence),
        )
    except Exception as e:
        logger.error(f"Profile upsert failed for {category}.{field}: {e}")
