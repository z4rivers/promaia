"""
Gmail ingest pipeline -- sync Gmail messages into the gmail_content table.

Uses the same account discovery as gmail_read.py but stores full message
content for later querying via the gmail_query MCP tool.

Supports incremental sync: only fetches messages newer than the last sync.

Usage via MCP (brain server):
    Called internally or scheduled. Not exposed as a direct MCP tool yet.

Usage via CLI:
    python -m promaia.brain.gmail_ingest [--account zachary4rivers] [--days-back 30]
"""
import hashlib
import json
import logging
import base64
import os
import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from promaia.brain.channels.gmail_read import (
    _CREDS_DIR,
    _get_gmail_service,
    discover_accounts,
)
from promaia.storage.db_factory import get_db

logger = logging.getLogger(__name__)


def run_gmail_ingest(
    account: Optional[str] = None,
    days_back: int = 7,
    max_emails: int = 200,
    workspace: str = "zbrain",
) -> Dict[str, Any]:
    """Sync Gmail messages into the gmail_content table.

    Args:
        account: Account label filter (e.g. "zachary4rivers"). None = all.
        days_back: How far back to look for messages.
        max_emails: Max messages per account per run.
        workspace: Workspace label for stored records.

    Returns:
        Summary dict with counts.
    """
    accounts = discover_accounts()
    if not accounts:
        return {"error": "No Gmail tokens found in credentials/default/."}

    if account:
        matched = {k: v for k, v in accounts.items() if account.lower() in k.lower()}
        if not matched:
            return {"error": f"No account matching '{account}'. Available: {list(accounts.keys())}"}
        accounts = matched

    db = get_db()
    results = {"accounts": {}, "total_synced": 0, "total_skipped": 0}

    for label, token_path in accounts.items():
        try:
            service = _get_gmail_service(token_path)
            email = service.users().getProfile(userId="me").execute()["emailAddress"]

            # Check last sync time for incremental
            last_sync = _get_last_sync(db, email)
            effective_days = days_back
            if last_sync:
                delta = datetime.now(timezone.utc) - last_sync
                effective_days = min(days_back, max(1, int(delta.days) + 1))

            acct_result = _ingest_account(
                service=service,
                email=email,
                days_back=effective_days,
                max_emails=max_emails,
                workspace=workspace,
                db=db,
            )
            results["accounts"][email] = acct_result
            results["total_synced"] += acct_result.get("inserted", 0)
            results["total_skipped"] += acct_result.get("skipped", 0)

        except Exception as e:
            logger.error(f"Ingest failed for {label}: {e}", exc_info=True)
            results["accounts"][label] = {"error": str(e)}

    return results


def _get_last_sync(db, email: str) -> Optional[datetime]:
    """Get the most recent synced_time for an account."""
    row = db.fetch_one(
        "SELECT MAX(synced_time) as last_sync FROM gmail_content WHERE sender_email = %s OR recipient_emails LIKE %s",
        (email, f"%{email}%"),
    )
    if row and row.get("last_sync"):
        try:
            return datetime.fromisoformat(row["last_sync"])
        except (ValueError, TypeError):
            pass
    return None


def _ingest_account(
    service, email: str, days_back: int, max_emails: int,
    workspace: str, db,
) -> Dict[str, Any]:
    """Ingest messages from a single Gmail account."""
    result = {"fetched": 0, "inserted": 0, "skipped": 0, "errors": 0}

    after_date = (datetime.now(timezone.utc) - timedelta(days=days_back)).strftime("%Y/%m/%d")
    query = f"after:{after_date}"

    messages = []
    page_token = None

    # Fetch message IDs
    while len(messages) < max_emails:
        kwargs = {
            "userId": "me",
            "q": query,
            "maxResults": min(100, max_emails - len(messages)),
        }
        if page_token:
            kwargs["pageToken"] = page_token

        try:
            response = service.users().messages().list(**kwargs).execute()
        except Exception as e:
            logger.error(f"Message list failed: {e}")
            break

        msg_list = response.get("messages", [])
        if not msg_list:
            break

        messages.extend(msg_list)
        page_token = response.get("nextPageToken")
        if not page_token:
            break

    result["fetched"] = len(messages)
    now_iso = datetime.now(timezone.utc).isoformat()

    for msg_stub in messages:
        msg_id = msg_stub["id"]
        try:
            # Check if we already have this message
            existing = db.fetch_one(
                "SELECT id FROM gmail_content WHERE message_id = %s",
                (msg_id,),
            )
            if existing:
                result["skipped"] += 1
                continue

            # Fetch full message
            msg = service.users().messages().get(
                userId="me", id=msg_id, format="full",
            ).execute()

            row = _parse_full_message(msg, email, workspace, now_iso)
            _insert_message(db, row)
            result["inserted"] += 1

            # Multimodal Assets Capture
            if row.get("attachments"):
                atts = json.loads(row["attachments"])
                downloaded_paths = []
                for att in atts:
                    if att.get("attachmentId") and att.get("mimeType", "").startswith(("image/", "application/pdf", "audio/")):
                        logger.info(f"Downloading attachment {att['filename']} for message {msg_id}")
                        local_path = _download_attachment(service, msg_id, att["attachmentId"], att["filename"])
                        if local_path:
                            downloaded_paths.append(local_path)
                
                if downloaded_paths:
                    from promaia.brain.core.memory_pipeline import capture_memory
                    from promaia.storage.vector_db import VectorDBManager
                    
                    vector_mgr = VectorDBManager(db)
                    
                    image_paths = [p for p in downloaded_paths if p.lower().endswith(('.jpg', '.jpeg', '.png', '.webp'))]
                    audio_paths = [p for p in downloaded_paths if p.lower().endswith(('.mp3', '.wav', '.m4a', '.ogg'))]
                    doc_paths = [p for p in downloaded_paths if p.lower().endswith(('.pdf',))]
                    
                    context_str = f"Email Date: {row['email_date']}\nFrom: {row['sender_name']} <{row['sender_email']}>\nSubject: {row['subject']}\n\nEmail snippet: {row.get('body_snippet', '')}"
                    
                    try:
                        _run_async(
                            capture_memory(
                                db=db,
                                vector_mgr=vector_mgr,
                                content=context_str,
                                session_id="gmail_ingest",
                                domain_name=workspace,
                                confidence=1.0,  # Exact file
                                image_paths=image_paths if image_paths else None,
                                audio_paths=audio_paths if audio_paths else None,
                                document_paths=doc_paths if doc_paths else None,
                                source="gmail_attachment"
                            )
                        )
                        logger.info(f"Successfully captured multimodal memory for email {msg_id}")
                    except Exception as e:
                        logger.error(f"Failed to capture multimodal memory for {msg_id}: {e}")

        except Exception as e:
            logger.warning(f"Failed to ingest message {msg_id}: {e}")
            result["errors"] += 1

    return result

def _download_attachment(service, message_id: str, attachment_id: str, filename: str) -> Optional[str]:
    """Download an attachment, save it to disk, and return the local path."""
    try:
        attachment = service.users().messages().attachments().get(
            userId='me', messageId=message_id, id=attachment_id
        ).execute()
        
        file_data = base64.urlsafe_b64decode(attachment['data'])
        
        save_dir = os.path.join(os.getcwd(), 'data', 'multimodal_assets', 'gmail')
        os.makedirs(save_dir, exist_ok=True)
        
        safe_filename = "".join(c for c in filename if c.isalnum() or c in (' ', '.', '_', '-')).rstrip()
        file_path = os.path.join(save_dir, f"{message_id}_{safe_filename}")
        
        with open(file_path, 'wb') as f:
            f.write(file_data)
        
        return file_path
    except Exception as e:
        logger.error(f"Failed to download attachment {filename} for msg {message_id}: {e}")
        return None

def _run_async(coro):
    """Safely run a coroutine whether an event loop is currently running or not."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
        
    if loop and loop.is_running():
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(asyncio.run, coro).result()
    else:
        return asyncio.run(coro)


def _parse_full_message(
    msg: dict, user_email: str, workspace: str, synced_time: str,
) -> Dict[str, Any]:
    """Parse a full Gmail message into a gmail_content row."""
    headers = {}
    for h in msg.get("payload", {}).get("headers", []):
        headers[h["name"].lower()] = h["value"]

    # Extract sender
    from_str = headers.get("from", "")
    sender_email, sender_name = _parse_address(from_str)

    # Extract recipients
    to_list = _parse_address_list(headers.get("to", ""))
    cc_list = _parse_address_list(headers.get("cc", ""))

    # Extract body
    body = _extract_body(msg.get("payload", {}))
    snippet = msg.get("snippet", "")[:500]

    # Labels
    labels = msg.get("labelIds", [])

    # Attachments
    attachments = _extract_attachment_info(msg.get("payload", {}))

    # Thread info
    thread_id = msg.get("threadId", "")

    # Date
    email_date = headers.get("date", "")

    # Checksum for dedup
    content_for_hash = f"{msg.get('id', '')}{headers.get('subject', '')}{email_date}"
    checksum = hashlib.md5(content_for_hash.encode()).hexdigest()

    return {
        "page_id": f"gmail_{msg['id']}",
        "workspace": workspace,
        "database_id": user_email,
        "file_path": f"gmail/{user_email}/{msg['id']}",
        "subject": headers.get("subject", ""),
        "sender_email": sender_email,
        "sender_name": sender_name,
        "recipient_emails": json.dumps(to_list),
        "cc_recipients": json.dumps(cc_list),
        "gmail_labels": json.dumps(labels),
        "thread_id": thread_id,
        "message_id": msg["id"],
        "has_attachments": len(attachments) > 0,
        "is_unread": "UNREAD" in labels,
        "body_snippet": snippet,
        "message_content": body[:10000] if body else None,
        "attachments": json.dumps(attachments) if attachments else None,
        "thread_position": 0,
        "is_latest_in_thread": True,
        "email_date": email_date,
        "created_time": email_date,
        "last_edited_time": email_date,
        "synced_time": synced_time,
        "file_size": len(body) if body else 0,
        "checksum": checksum,
    }


def _parse_address(addr_str: str):
    """Extract (email, name) from 'Name <email>' format."""
    import re
    addr_str = addr_str.strip()
    match = re.match(r'^"?([^"<]*)"?\s*<([^>]+)>', addr_str)
    if match:
        return match.group(2).strip().lower(), match.group(1).strip()
    return addr_str.lower(), ""


def _parse_address_list(addr_str: str) -> list:
    """Parse a comma-separated list of addresses."""
    if not addr_str:
        return []
    result = []
    for addr in addr_str.split(","):
        email, name = _parse_address(addr.strip())
        if email:
            result.append({"email": email, "name": name})
    return result


def _extract_body(payload: dict) -> str:
    """Extract text body from a Gmail message payload."""
    import base64

    # Simple text/plain part
    if payload.get("mimeType") == "text/plain" and payload.get("body", {}).get("data"):
        return base64.urlsafe_b64decode(payload["body"]["data"]).decode("utf-8", errors="replace")

    # Multipart: recurse into parts
    parts = payload.get("parts", [])
    for part in parts:
        if part.get("mimeType") == "text/plain" and part.get("body", {}).get("data"):
            return base64.urlsafe_b64decode(part["body"]["data"]).decode("utf-8", errors="replace")

    # Fallback: try text/html
    for part in parts:
        if part.get("mimeType") == "text/html" and part.get("body", {}).get("data"):
            html = base64.urlsafe_b64decode(part["body"]["data"]).decode("utf-8", errors="replace")
            # Strip HTML tags for storage
            import re
            return re.sub(r"<[^>]+>", "", html)[:10000]

    # Nested multipart
    for part in parts:
        if part.get("parts"):
            body = _extract_body(part)
            if body:
                return body

    return ""


def _extract_attachment_info(payload: dict) -> list:
    """Extract attachment metadata (not content) from payload."""
    attachments = []
    for part in payload.get("parts", []):
        if part.get("filename"):
            attachments.append({
                "filename": part["filename"],
                "mimeType": part.get("mimeType", ""),
                "size": part.get("body", {}).get("size", 0),
                "attachmentId": part.get("body", {}).get("attachmentId", ""),
            })
        if part.get("parts"):
            attachments.extend(_extract_attachment_info(part))
    return attachments


def _insert_message(db, row: dict):
    """Insert a parsed message into gmail_content."""
    columns = list(row.keys())
    placeholders = ", ".join(["%s"] * len(columns))
    col_names = ", ".join(columns)

    db.execute(
        f"INSERT INTO gmail_content ({col_names}) VALUES ({placeholders}) ON CONFLICT (message_id) DO NOTHING",
        tuple(row.values()),
    )


def resync_missing_bodies(workspace: str = "zbrain", max_messages: int = 200) -> Dict[str, Any]:
    """Re-fetch full bodies for gmail_content rows where message_content is NULL."""
    db = get_db()
    rows = db.fetch_all(
        "SELECT message_id, database_id FROM gmail_content WHERE message_content IS NULL OR message_content = '' LIMIT %s",
        (max_messages,)
    )
    if not rows:
        return {"updated": 0, "message": "All messages already have content"}

    result: Dict[str, Any] = {"total": len(rows), "updated": 0, "failed": 0, "by_account": {}}

    accounts = discover_accounts()
    # Group rows by database_id (email address)
    by_account: Dict[str, list] = {}
    for row in rows:
        acct = row['database_id']
        by_account.setdefault(acct, []).append(row['message_id'])

    for email, msg_ids in by_account.items():
        # Find matching account token
        token_path = None
        for label, tp in accounts.items():
            try:
                svc = _get_gmail_service(tp)
                profile_email = svc.users().getProfile(userId="me").execute()["emailAddress"]
                if profile_email == email:
                    token_path = tp
                    break
            except Exception:
                continue

        if not token_path:
            result["by_account"][email] = {"error": "No token found"}
            continue

        service = _get_gmail_service(token_path)
        updated = 0
        for msg_id in msg_ids:
            try:
                msg = service.users().messages().get(userId="me", id=msg_id, format="full").execute()
                body = _extract_body(msg.get("payload", {}))
                if body:
                    db.execute(
                        "UPDATE gmail_content SET message_content = %s WHERE message_id = %s",
                        (body[:10000], msg_id)
                    )
                    updated += 1
                else:
                    # Store snippet as fallback, flagged
                    snippet = msg.get("snippet", "")
                    if snippet:
                        db.execute(
                            "UPDATE gmail_content SET message_content = %s WHERE message_id = %s",
                            (f"[snippet only] {snippet}", msg_id)
                        )
                        updated += 1
            except Exception as e:
                logger.warning(f"Failed to resync {msg_id}: {e}")
                result["failed"] += 1

        result["updated"] += updated
        result["by_account"][email] = {"updated": updated, "total": len(msg_ids)}

    return result


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    parser = argparse.ArgumentParser(description="Gmail ingest pipeline")
    parser.add_argument("--account", help="Account label filter")
    parser.add_argument("--days-back", type=int, default=7)
    parser.add_argument("--max-emails", type=int, default=200)
    parser.add_argument("--workspace", default="zbrain")
    parser.add_argument("--resync-bodies", action="store_true",
                        help="Re-fetch bodies for messages with NULL message_content")
    args = parser.parse_args()

    if args.resync_bodies:
        result = resync_missing_bodies(
            workspace=args.workspace,
            max_messages=args.max_emails,
        )
    else:
        result = run_gmail_ingest(
            account=args.account,
            days_back=args.days_back,
            max_emails=args.max_emails,
            workspace=args.workspace,
        )
    print(json.dumps(result, indent=2, default=str))
