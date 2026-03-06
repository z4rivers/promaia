"""
Gmail cleanup channel -- unsubscribe automation and bulk delete.

Operates directly via Gmail API using existing OAuth tokens.
Supports:
    - Unsubscribe via List-Unsubscribe headers (mailto: and https:)
    - Permanent batch delete of junk from specified senders
    - Dry-run mode for previewing actions

Usage:
    python -m promaia.brain.channels.gmail_cleanup [--dry-run] [--max-delete 1000]
"""
import json
import logging
import re
import time
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
from urllib.parse import urlparse

import requests

from promaia.brain.channels.gmail_read import (
    _get_gmail_service,
    discover_accounts,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Unsubscribe targets -- senders to unsubscribe from and delete
# ---------------------------------------------------------------------------

# Permanent delete: clearly dead or unwanted bulk senders
DELETE_TARGETS = [
    # Promotions -- high volume junk
    "noreply@r.groupon.com",
    "rei_gearmail@notices.rei.com",
    "rei_email@email.rei.com",
    "cs@emails.zappos.com",
    "gap@email.gap.com",
    "bananarepublic@email.bananarepublic.com",
    "rewards@e.officedepot.com",
    "officedepot@em.officedepot.com",
    "bedbath&beyond@emailbedbathandbeyond.com",
    "news@e.lenscrafters.com",
    "hello@mail.bludot.com",
    "hello@mpix.com",
    "southwestairlines@iluv.southwest.com",
    "promotions@newsletter.petedge.com",
    "timberland@t.timberland.com",
    "no-reply@radpowerbikes.com",
    "support@trueclassictees.com",
    "landsend@offer.landsend.com",
    "hallo@lingster.de",
    # Political -- user explicitly wants zero political email
    "info@e.elissaslotkin.org",
    "info@e.votevets.org",
    "info@dscc.org",
    "info@janepac.com",
    "info@e.leaderswedeserve.com",
    "info@actblue.com",
    "info+ab178570366@actblue.com",
    "info+ab178502725@actblue.com",
    # Social noise
    "friendupdates@facebookmail.com",
    # Dead services / low value
    "noreply@medium.com",
    "ancestry@email.ancestry.com",
    "adventureawaits@recreation.gov",
    "contactus@news.kiva.org",
    "team@mint.com",
    "jeremy@7thlevelhqteam.com",
    "achrnews@custom-bnp.com",
    "redmail@redfin.com",
    "listings@redfin.com",
    # Automated noise
    "google-maps-noreply@google.com",
]

# Domain-level delete: trash everything from these domains
DELETE_DOMAINS = [
    "emailbedbathandbeyond.com",  # company is dead
    "groupon.com",
    "e.votevets.org",
    "e.elissaslotkin.org",
    "janepac.com",
    "e.leaderswedeserve.com",
]


# ---------------------------------------------------------------------------
# Core functions
# ---------------------------------------------------------------------------

def run_cleanup(
    account: Optional[str] = None,
    dry_run: bool = False,
    max_delete: int = 5000,
    unsubscribe: bool = True,
) -> Dict[str, Any]:
    """Run the full cleanup pipeline.

    Args:
        account: Account label or None for default.
        dry_run: If True, log actions without executing.
        max_delete: Max messages to delete per account.
        unsubscribe: Whether to attempt List-Unsubscribe.

    Returns:
        Summary dict with counts.
    """
    accounts = discover_accounts()
    if not accounts:
        return {"error": "No Gmail tokens found."}

    if account:
        matched = {k: v for k, v in accounts.items() if account.lower() in k.lower()}
        if not matched:
            return {"error": f"No account matching '{account}'."}
        accounts = matched

    results = {}

    for label, token_path in accounts.items():
        # Skip zackayak -- dead junk account
        if "zackayak" in label.lower():
            continue

        try:
            service = _get_gmail_service(token_path)
            email = service.users().getProfile(userId="me").execute()["emailAddress"]
            logger.info(f"Cleaning up {email}...")

            result = _cleanup_account(
                service=service,
                email=email,
                dry_run=dry_run,
                max_delete=max_delete,
                unsubscribe=unsubscribe,
            )
            results[email] = result

        except Exception as e:
            logger.error(f"Cleanup failed for {label}: {e}", exc_info=True)
            results[label] = {"error": str(e)}

    return results


def _cleanup_account(
    service,
    email: str,
    dry_run: bool,
    max_delete: int,
    unsubscribe: bool,
) -> Dict[str, Any]:
    """Clean up a single Gmail account."""
    result = {
        "unsubscribed": [],
        "unsubscribe_failed": [],
        "deleted_count": 0,
        "deleted_by_sender": {},
        "errors": [],
    }

    # Phase 1: Find all messages from target senders
    all_target_ids = []
    unsubscribe_headers = {}  # message_id -> header value

    for sender in DELETE_TARGETS:
        msg_ids, unsub_headers = _find_messages_from_sender(
            service, sender, max_results=500
        )
        all_target_ids.extend(msg_ids)
        if msg_ids:
            result["deleted_by_sender"][sender] = len(msg_ids)
        unsubscribe_headers.update(unsub_headers)

    # Also search by domain
    for domain in DELETE_DOMAINS:
        msg_ids, unsub_headers = _find_messages_from_domain(
            service, domain, max_results=500
        )
        # Deduplicate
        existing = set(all_target_ids)
        new_ids = [mid for mid in msg_ids if mid not in existing]
        all_target_ids.extend(new_ids)
        if new_ids:
            result["deleted_by_sender"][f"*@{domain}"] = len(new_ids)
        unsubscribe_headers.update(unsub_headers)

    logger.info(f"Found {len(all_target_ids)} messages to delete from {len(DELETE_TARGETS)} senders + {len(DELETE_DOMAINS)} domains")

    # Phase 2: Unsubscribe (before deleting)
    if unsubscribe:
        # Deduplicate unsubscribe targets by sender domain
        unsub_attempted: Set[str] = set()
        for msg_id, header_val in unsubscribe_headers.items():
            # Extract sender domain to avoid duplicate unsubscribes
            domain_key = _extract_unsub_domain(header_val)
            if domain_key in unsub_attempted:
                continue
            unsub_attempted.add(domain_key)

            success = _attempt_unsubscribe(service, email, header_val, dry_run)
            if success:
                result["unsubscribed"].append(domain_key)
            else:
                result["unsubscribe_failed"].append(domain_key)

    # Phase 3: Batch delete
    to_delete = all_target_ids[:max_delete]
    if to_delete:
        if dry_run:
            logger.info(f"[DRY RUN] Would permanently delete {len(to_delete)} messages")
            result["deleted_count"] = 0
            result["would_delete"] = len(to_delete)
        else:
            deleted = _batch_delete(service, to_delete)
            result["deleted_count"] = deleted

    return result


def _find_messages_from_sender(
    service, sender_email: str, max_results: int = 500
) -> Tuple[List[str], Dict[str, str]]:
    """Find all message IDs from a specific sender.

    Returns (message_ids, {msg_id: unsubscribe_header}).
    """
    query = f"from:{sender_email}"
    return _collect_message_ids(service, query, max_results)


def _find_messages_from_domain(
    service, domain: str, max_results: int = 500
) -> Tuple[List[str], Dict[str, str]]:
    """Find all message IDs from a domain."""
    query = f"from:@{domain}"
    return _collect_message_ids(service, query, max_results)


def _collect_message_ids(
    service, query: str, max_results: int
) -> Tuple[List[str], Dict[str, str]]:
    """Collect message IDs matching a query, plus any unsubscribe headers."""
    msg_ids = []
    unsub_headers = {}
    page_token = None

    while len(msg_ids) < max_results:
        try:
            kwargs = {
                "userId": "me",
                "q": query,
                "maxResults": min(100, max_results - len(msg_ids)),
            }
            if page_token:
                kwargs["pageToken"] = page_token

            response = service.users().messages().list(**kwargs).execute()
            batch = response.get("messages", [])

            if not batch:
                break

            for msg_stub in batch:
                msg_ids.append(msg_stub["id"])

            # Grab unsubscribe header from first message only (same sender = same link)
            if batch and not unsub_headers:
                try:
                    msg = service.users().messages().get(
                        userId="me",
                        id=batch[0]["id"],
                        format="metadata",
                        metadataHeaders=["List-Unsubscribe", "List-Unsubscribe-Post"],
                    ).execute()
                    headers = {
                        h["name"].lower(): h["value"]
                        for h in msg.get("payload", {}).get("headers", [])
                    }
                    if headers.get("list-unsubscribe"):
                        unsub_headers[batch[0]["id"]] = headers["list-unsubscribe"]
                except Exception:
                    pass

            page_token = response.get("nextPageToken")
            if not page_token:
                break

        except Exception as e:
            logger.warning(f"Query failed '{query}': {e}")
            break

    return msg_ids, unsub_headers


def _attempt_unsubscribe(
    service, user_email: str, header_value: str, dry_run: bool
) -> bool:
    """Attempt to unsubscribe using List-Unsubscribe header.

    Supports both mailto: and https: unsubscribe methods.
    Returns True if successful.
    """
    # Parse the header -- can contain multiple URLs: <mailto:...>, <https://...>
    urls = re.findall(r'<([^>]+)>', header_value)

    # Prefer https over mailto (one-click is cleaner)
    https_urls = [u for u in urls if u.startswith("https://") or u.startswith("http://")]
    mailto_urls = [u for u in urls if u.startswith("mailto:")]

    if https_urls:
        url = https_urls[0]
        if dry_run:
            logger.info(f"[DRY RUN] Would GET unsubscribe: {url}")
            return True
        try:
            # RFC 8058 one-click: POST with List-Unsubscribe=One-Click-Unsubscribe
            resp = requests.post(
                url,
                data={"List-Unsubscribe": "One-Click-Unsubscribe"},
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=10,
                allow_redirects=True,
            )
            if resp.status_code < 400:
                logger.info(f"Unsubscribed via HTTPS: {url} (status {resp.status_code})")
                return True
            # Fall back to GET
            resp = requests.get(url, timeout=10, allow_redirects=True)
            if resp.status_code < 400:
                logger.info(f"Unsubscribed via HTTPS GET: {url}")
                return True
            logger.warning(f"Unsubscribe failed: {url} -> {resp.status_code}")
        except Exception as e:
            logger.warning(f"Unsubscribe request failed: {url} -> {e}")

    if mailto_urls:
        mailto = mailto_urls[0]
        # Extract email address from mailto:unsub@example.com?subject=...
        parsed = mailto.replace("mailto:", "")
        parts = parsed.split("?", 1)
        unsub_email = parts[0]
        subject = "Unsubscribe"
        if len(parts) > 1:
            params = dict(p.split("=", 1) for p in parts[1].split("&") if "=" in p)
            subject = params.get("subject", subject)

        if dry_run:
            logger.info(f"[DRY RUN] Would send unsubscribe to: {unsub_email}")
            return True

        try:
            import base64
            from email.mime.text import MIMEText

            msg = MIMEText("")
            msg["to"] = unsub_email
            msg["from"] = user_email
            msg["subject"] = subject
            raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
            service.users().messages().send(
                userId="me", body={"raw": raw}
            ).execute()
            logger.info(f"Unsubscribe email sent to: {unsub_email}")
            return True
        except Exception as e:
            logger.warning(f"Unsubscribe email failed: {unsub_email} -> {e}")

    return False


def _extract_unsub_domain(header_value: str) -> str:
    """Extract a domain key from an unsubscribe header for dedup."""
    urls = re.findall(r'<([^>]+)>', header_value)
    for url in urls:
        if url.startswith("http"):
            try:
                return urlparse(url).netloc
            except Exception:
                pass
        if url.startswith("mailto:"):
            addr = url.replace("mailto:", "").split("?")[0]
            if "@" in addr:
                return addr.split("@")[1]
    return header_value[:50]


def _batch_delete(service, message_ids: List[str]) -> int:
    """Permanently delete messages in batches of 100.

    Uses batchDelete which is permanent -- messages are NOT recoverable.
    """
    deleted = 0
    batch_size = 100

    for i in range(0, len(message_ids), batch_size):
        batch = message_ids[i:i + batch_size]
        try:
            service.users().messages().batchDelete(
                userId="me",
                body={"ids": batch},
            ).execute()
            deleted += len(batch)
            logger.info(f"Deleted batch {i // batch_size + 1}: {len(batch)} messages (total: {deleted})")
            # Small delay to avoid rate limits
            if i + batch_size < len(message_ids):
                time.sleep(0.5)
        except Exception as e:
            logger.error(f"Batch delete failed at offset {i}: {e}")
            # Try individual deletes for this batch
            for msg_id in batch:
                try:
                    service.users().messages().delete(
                        userId="me", id=msg_id
                    ).execute()
                    deleted += 1
                except Exception as e2:
                    logger.warning(f"Individual delete failed {msg_id}: {e2}")

    return deleted


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    parser = argparse.ArgumentParser(description="Gmail cleanup: unsubscribe and delete junk")
    parser.add_argument("--dry-run", action="store_true", help="Preview without executing")
    parser.add_argument("--max-delete", type=int, default=5000, help="Max messages to delete")
    parser.add_argument("--no-unsubscribe", action="store_true", help="Skip unsubscribe step")
    parser.add_argument("--account", type=str, default="default", help="Account label")
    args = parser.parse_args()

    results = run_cleanup(
        account=args.account,
        dry_run=args.dry_run,
        max_delete=args.max_delete,
        unsubscribe=not args.no_unsubscribe,
    )

    print(json.dumps(results, indent=2, default=str))
