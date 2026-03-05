"""
Gmail read channel — automated profile extraction from inbox.

Scans recent Gmail inbox to extract contacts, communication patterns,
recurring topics, and activity timing. Results are stored in brain.profile
with source='inferred'. Never stores raw email content — only metadata
and summaries.

Requires Gmail OAuth to be configured first via:
    python -m promaia.cli.main workspace gmail-setup default <email>

Usage:
    from promaia.brain.channels.gmail_read import run_gmail_scan
    result = run_gmail_scan(db=some_db)
"""
import asyncio
import json
import logging
import os
import re
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
CONFIDENCE_EMAIL = 0.5  # Lower than direct observation


def run_gmail_scan(
    email_address: Optional[str] = None,
    days_back: int = 30,
    max_emails: int = 100,
    db=None,
) -> Dict[str, Any]:
    """Scan recent Gmail inbox and extract profile-relevant data.

    Connects to Gmail via existing GmailConnector, reads recent threads,
    and extracts contacts, communication patterns, topics, and timing.
    NEVER stores raw email content — only metadata and summaries.

    Args:
        email_address: Gmail address (default: GMAIL_ADDRESS from .env).
        days_back: How many days of email to scan (default 30).
        max_emails: Maximum emails to process (default 100).
        db: PostgresDB instance. If None, imports and creates one.

    Returns:
        dict with {contacts_found, emails_scanned, fields_updated, error}
    """
    result = {
        "contacts_found": 0,
        "emails_scanned": 0,
        "fields_updated": 0,
        "error": None,
    }

    # --- Resolve email address ---
    if not email_address:
        email_address = os.environ.get("GMAIL_ADDRESS")
    if not email_address:
        result["error"] = (
            "Gmail address not configured. Set GMAIL_ADDRESS in .env or pass email_address parameter."
        )
        return result

    # --- Import GmailConnector (graceful failure if deps missing) ---
    try:
        from promaia.connectors.gmail_connector import GmailConnector
    except ImportError as e:
        result["error"] = (
            f"Gmail packages not installed: {e}. "
            "Install with: pip install google-auth google-auth-oauthlib google-api-python-client"
        )
        return result

    # --- Get DB ---
    if db is None:
        try:
            from promaia.storage.postgres_db import get_postgres_db
            db = get_postgres_db()
        except Exception as e:
            result["error"] = f"Database connection failed: {e}"
            return result

    # --- Connect to Gmail ---
    try:
        connector = GmailConnector({
            "database_id": email_address,
            "workspace": "default",
        })
        # Use asyncio to run the async connect method
        connected = _run_async(connector.connect(allow_interactive=False))
        if not connected:
            result["error"] = (
                f"Gmail OAuth not configured for {email_address}. "
                f"Run: python -m promaia.cli.main workspace gmail-setup default {email_address}"
            )
            return result
    except Exception as e:
        error_msg = str(e)
        if "credentials not found" in error_msg.lower() or "authentication required" in error_msg.lower():
            result["error"] = (
                f"Gmail OAuth not configured for {email_address}. "
                f"Run: python -m promaia.cli.main workspace gmail-setup default {email_address}"
            )
        else:
            result["error"] = f"Gmail connection failed: {error_msg}"
        return result

    # --- Fetch recent threads ---
    try:
        threads = _fetch_recent_threads(connector, days_back, max_emails)
        result["emails_scanned"] = len(threads)
    except Exception as e:
        result["error"] = f"Failed to fetch emails: {e}"
        return result

    if not threads:
        result["error"] = "No emails found in the specified date range."
        return result

    # --- Extract profile signals ---
    try:
        contacts_result = _extract_contacts(threads, db)
        result["contacts_found"] = contacts_result["contacts_found"]
        result["fields_updated"] += contacts_result["fields_updated"]
    except Exception as e:
        logger.error(f"Contact extraction failed: {e}", exc_info=True)

    try:
        patterns_result = _extract_communication_patterns(threads, db)
        result["fields_updated"] += patterns_result["fields_updated"]
    except Exception as e:
        logger.error(f"Communication pattern extraction failed: {e}", exc_info=True)

    try:
        topics_result = _extract_topics(threads, db)
        result["fields_updated"] += topics_result["fields_updated"]
    except Exception as e:
        logger.error(f"Topic extraction failed: {e}", exc_info=True)

    try:
        timing_result = _extract_activity_patterns(threads, db)
        result["fields_updated"] += timing_result["fields_updated"]
    except Exception as e:
        logger.error(f"Activity pattern extraction failed: {e}", exc_info=True)

    logger.info(
        f"Gmail scan complete: {result['emails_scanned']} emails, "
        f"{result['contacts_found']} contacts, {result['fields_updated']} fields"
    )
    return result


# ---------------------------------------------------------------------------
# Thread fetching
# ---------------------------------------------------------------------------

def _fetch_recent_threads(
    connector,
    days_back: int,
    max_emails: int,
) -> List[Dict[str, Any]]:
    """Fetch recent email threads via GmailConnector's service.

    Uses the Gmail API directly through the connector's authenticated service
    to list and fetch thread metadata without storing raw content.
    """
    service = connector.service
    if not service:
        return []

    after_date = (datetime.now(timezone.utc) - timedelta(days=days_back)).strftime("%Y/%m/%d")
    query = f"after:{after_date}"

    threads: List[Dict[str, Any]] = []
    page_token = None

    while len(threads) < max_emails:
        try:
            kwargs = {
                "userId": "me",
                "q": query,
                "maxResults": min(50, max_emails - len(threads)),
            }
            if page_token:
                kwargs["pageToken"] = page_token

            response = service.users().threads().list(**kwargs).execute()
            thread_list = response.get("threads", [])

            if not thread_list:
                break

            # Fetch metadata for each thread (minimal format)
            for thread_stub in thread_list:
                if len(threads) >= max_emails:
                    break
                try:
                    thread_data = service.users().threads().get(
                        userId="me",
                        id=thread_stub["id"],
                        format="metadata",
                        metadataHeaders=["From", "To", "Cc", "Subject", "Date"],
                    ).execute()
                    threads.append(_parse_thread_metadata(thread_data))
                except Exception as e:
                    logger.warning(f"Could not fetch thread {thread_stub['id']}: {e}")

            page_token = response.get("nextPageToken")
            if not page_token:
                break

        except Exception as e:
            logger.error(f"Thread list request failed: {e}")
            break

    return threads


def _parse_thread_metadata(thread_data: Dict[str, Any]) -> Dict[str, Any]:
    """Parse a Gmail thread into a minimal metadata-only structure.

    PRIVACY: Only extracts sender, recipients, subject, date, and snippet.
    Never stores email body content.
    """
    messages = thread_data.get("messages", [])
    parsed = {
        "id": thread_data.get("id"),
        "message_count": len(messages),
        "senders": [],
        "recipients": [],
        "subjects": [],
        "dates": [],
        "snippet": thread_data.get("snippet", "")[:100],  # Truncated snippet only
    }

    for msg in messages:
        headers = {
            h["name"].lower(): h["value"]
            for h in msg.get("payload", {}).get("headers", [])
        }

        sender = headers.get("from", "")
        if sender:
            parsed["senders"].append(_extract_email_parts(sender))

        to = headers.get("to", "")
        if to:
            for addr in to.split(","):
                parsed["recipients"].append(_extract_email_parts(addr.strip()))

        cc = headers.get("cc", "")
        if cc:
            for addr in cc.split(","):
                parsed["recipients"].append(_extract_email_parts(addr.strip()))

        subject = headers.get("subject", "")
        if subject:
            parsed["subjects"].append(subject)

        date_str = headers.get("date", "")
        if date_str:
            try:
                from email.utils import parsedate_to_datetime
                dt = parsedate_to_datetime(date_str)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                parsed["dates"].append(dt)
            except Exception:
                pass

    return parsed


def _extract_email_parts(addr_str: str) -> Dict[str, str]:
    """Extract name and email from 'Name <email>' format."""
    addr_str = addr_str.strip()
    match = re.match(r'^"?([^"<]*)"?\s*<([^>]+)>', addr_str)
    if match:
        return {"name": match.group(1).strip(), "email": match.group(2).strip().lower()}
    # Plain email
    return {"name": "", "email": addr_str.lower()}


# ---------------------------------------------------------------------------
# Signal extraction
# ---------------------------------------------------------------------------

def _extract_contacts(threads: List[Dict], db) -> Dict[str, Any]:
    """Build frequency map of email contacts, store top 10."""
    result = {"contacts_found": 0, "fields_updated": 0}

    contact_freq: Dict[str, Dict[str, Any]] = {}  # email -> {name, count, last_seen}

    for thread in threads:
        latest_date = max(thread["dates"]) if thread["dates"] else None

        for contact in thread["senders"] + thread["recipients"]:
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

            # Keep the most descriptive name
            if contact.get("name") and not contact_freq[email]["name"]:
                contact_freq[email]["name"] = contact["name"]

            if latest_date:
                existing = contact_freq[email]["last_contact"]
                if existing is None or latest_date > existing:
                    contact_freq[email]["last_contact"] = latest_date

    result["contacts_found"] = len(contact_freq)

    if contact_freq:
        # Sort by frequency, take top 10
        top_contacts = sorted(
            contact_freq.values(),
            key=lambda c: c["frequency"],
            reverse=True,
        )[:10]

        # Serialize for storage (convert datetimes to strings)
        for c in top_contacts:
            if c["last_contact"]:
                c["last_contact"] = c["last_contact"].isoformat()

        _upsert_profile(db, "relationships", "people", top_contacts, CONFIDENCE_EMAIL)
        result["fields_updated"] += 1

        # Store individual contact summaries as memories
        for c in top_contacts[:5]:
            name = c["name"] or c["email"]
            summary = f"Communicates frequently with {name} ({c['frequency']} emails in scanned period)"
            try:
                db.execute(
                    """
                    INSERT INTO brain.memories (content, domain, source, source_id)
                    VALUES (%s, 'personal', 'gmail_scan', %s)
                    """,
                    (summary, f"contact_{c['email']}"),
                )
            except Exception as e:
                logger.warning(f"Could not store contact memory: {e}")

    return result


def _extract_communication_patterns(threads: List[Dict], db) -> Dict[str, Any]:
    """Analyze reply patterns and formality indicators."""
    result = {"fields_updated": 0}

    # Message count per thread (reply depth)
    msg_counts = [t["message_count"] for t in threads]
    if msg_counts:
        avg_thread_depth = sum(msg_counts) / len(msg_counts)
        _upsert_profile(
            db, "communication", "email_thread_depth",
            f"{avg_thread_depth:.1f} messages per thread (avg)",
            CONFIDENCE_EMAIL,
        )
        result["fields_updated"] += 1

    # Subject line analysis for formality
    subjects = []
    for t in threads:
        subjects.extend(t.get("subjects", []))

    if subjects:
        # Simple formality heuristic: formal subjects tend to be longer
        avg_subject_len = sum(len(s) for s in subjects) / len(subjects)
        formality = "formal" if avg_subject_len > 40 else "informal" if avg_subject_len < 20 else "moderate"
        _upsert_profile(
            db, "communication", "email_formality",
            formality,
            CONFIDENCE_EMAIL,
        )
        result["fields_updated"] += 1

    return result


def _extract_topics(threads: List[Dict], db) -> Dict[str, Any]:
    """Cluster subjects by keyword to identify recurring themes."""
    result = {"fields_updated": 0}

    # Collect all subjects
    subjects: List[str] = []
    for t in threads:
        subjects.extend(t.get("subjects", []))

    if not subjects:
        return result

    # Simple keyword extraction (strip Re:, Fwd:, etc.)
    words: List[str] = []
    stop_words = {
        "re", "fwd", "fw", "the", "a", "an", "is", "it", "to", "for", "of",
        "and", "in", "on", "at", "by", "with", "from", "this", "that", "your",
        "you", "we", "our", "my", "me", "be", "was", "were", "been", "are",
        "have", "has", "had", "do", "does", "did", "will", "would", "could",
        "should", "can", "may", "might", "not", "no", "but", "or", "if",
        "about", "up", "out", "just", "so", "all", "get", "got",
    }

    for subject in subjects:
        # Remove Re: Fwd: prefixes
        cleaned = re.sub(r"^(Re|Fwd|Fw):\s*", "", subject, flags=re.IGNORECASE).strip()
        for word in cleaned.split():
            word = re.sub(r"[^\w]", "", word).lower()
            if word and len(word) > 2 and word not in stop_words:
                words.append(word)

    if words:
        word_freq = Counter(words)
        top_topics = [w for w, _ in word_freq.most_common(15)]

        # Infer domains from topic keywords
        work_keywords = {"meeting", "project", "update", "review", "report", "deadline", "budget"}
        personal_keywords = {"dinner", "birthday", "vacation", "family", "weekend", "trip"}
        tech_keywords = {"api", "deploy", "bug", "release", "merge", "build", "server", "code"}

        topic_categories: Dict[str, List[str]] = defaultdict(list)
        for topic in top_topics:
            if topic in work_keywords:
                topic_categories["work"].append(topic)
            elif topic in personal_keywords:
                topic_categories["personal"].append(topic)
            elif topic in tech_keywords:
                topic_categories["tech"].append(topic)
            else:
                topic_categories["other"].append(topic)

        _upsert_profile(db, "context", "email_topics", top_topics, CONFIDENCE_EMAIL)
        result["fields_updated"] += 1

        # Store topic summaries as memories
        for domain, topics in topic_categories.items():
            if topics:
                summary = f"Recurring email topics ({domain}): {', '.join(topics)}"
                try:
                    db.execute(
                        """
                        INSERT INTO brain.memories (content, domain, source, source_id)
                        VALUES (%s, %s, 'gmail_scan', %s)
                        """,
                        (summary, domain if domain != "other" else "personal", f"topics_{domain}"),
                    )
                except Exception as e:
                    logger.warning(f"Could not store topic memory: {e}")

    return result


def _extract_activity_patterns(threads: List[Dict], db) -> Dict[str, Any]:
    """Analyze email send/receive times to augment chronotype data."""
    result = {"fields_updated": 0}

    hours: List[int] = []
    for t in threads:
        for dt in t.get("dates", []):
            hours.append(dt.hour)

    if hours:
        hour_counts = Counter(hours)
        peak_email_hours = [h for h, _ in hour_counts.most_common(4)]
        peak_email_hours.sort()

        peak_str = ", ".join(f"{h}:00" for h in peak_email_hours)
        _upsert_profile(
            db, "energy_patterns", "email_activity_hours",
            peak_str,
            CONFIDENCE_EMAIL,
        )
        result["fields_updated"] += 1

    return result


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _upsert_profile(
    db,
    category: str,
    field: str,
    value: Any,
    confidence: float = CONFIDENCE_EMAIL,
    source: str = "inferred",
) -> None:
    """Upsert a single profile field in brain.profile."""
    value_json = json.dumps(value, default=str)
    try:
        db.execute(
            """
            INSERT INTO brain.profile (category, field, value, confidence, source, updated_at)
            VALUES (%s, %s, %s::jsonb, %s, %s, NOW())
            ON CONFLICT (category, field) DO UPDATE SET
                value = EXCLUDED.value,
                confidence = EXCLUDED.confidence,
                source = EXCLUDED.source,
                updated_at = NOW()
            """,
            (category, field, value_json, confidence, source),
        )
    except Exception as e:
        logger.error(f"Profile upsert failed for {category}.{field}: {e}")


def _run_async(coro):
    """Run an async coroutine from synchronous context."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # If we're already in an async context, create a new thread
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                return pool.submit(asyncio.run, coro).result()
        else:
            return loop.run_until_complete(coro)
    except RuntimeError:
        return asyncio.run(coro)
