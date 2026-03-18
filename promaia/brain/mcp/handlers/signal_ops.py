import json
import logging
import os
from typing import List
from mcp.types import TextContent

logger = logging.getLogger(__name__)

# Map old priority names to Whispers priorities for backward compat
_PRIORITY_MAP = {
    "normal": "routine",
    "high": "priority",
    "urgent": "flash",
    # New names pass through directly
    "routine": "routine",
    "priority": "priority",
    "flash": "flash",
    "system": "system",
}

# Map old msg_type names to Whispers MsgType values
_MSGTYPE_MAP = {
    "request": "request",
    "response": "inform",
    "correction": "inform",
    "heads_up": "heads_up",
    "handoff": "handoff",
    # New names pass through
    "inform": "inform",
    "propose": "propose",
    "accept": "accept",
    "reject": "reject",
    "checkpoint": "checkpoint",
}

# ---------------------------------------------------------------------------
# Lazy-init shared WhispersClient
# ---------------------------------------------------------------------------
_client = None

def _get_client():
    global _client
    if _client is None:
        from whispers.client import WhispersClient
        db_path = os.environ.get("WHISPERS_DB_PATH", "./whispers.db")
        _client = WhispersClient("claude-code", db_path=db_path)
    return _client

def _get_db():
    """Get the underlying WhispersDB for operations WhispersClient doesn't expose."""
    return _get_client().db

# ---------------------------------------------------------------------------
# Existing 7 MCP tools — identical signatures, Whispers backend
# ---------------------------------------------------------------------------

async def _handle_message_send(args: dict) -> list[TextContent]:
    client = _get_client()
    to_agent = args.get("to")
    msg_type = args.get("type", "request")
    subject = args.get("subject", "No subject")
    body = args.get("body", "")
    context_payload = args.get("context")
    priority = args.get("priority", "normal")

    if isinstance(context_payload, str):
        try:
            context_payload = json.loads(context_payload)
        except Exception:
            pass

    # Map old names to Whispers enums
    w_priority = _PRIORITY_MAP.get(priority, "routine")
    w_msgtype = _MSGTYPE_MAP.get(msg_type, "inform")

    try:
        msg_uuid = client.send(
            to=to_agent,
            subject=subject,
            body=body,
            priority=w_priority,
            msg_type=w_msgtype,
            payload=context_payload if isinstance(context_payload, dict) else None,
        )
    except Exception as e:
        logger.error(f"Whispers dispatch failed: {e}")
        return [TextContent(type="text", text=f"Failed to send message: {e}")]

    return [TextContent(type="text", text=f"Message {msg_uuid} sent successfully.")]


async def _handle_message_check(args: dict) -> list[TextContent]:
    client = _get_client()
    agent = args.get("agent", "claude-code")
    messages = client.check_inbox(limit=50, mark_seen=True)

    if not messages:
        return [TextContent(type="text", text="No new messages.")]

    out = ["# Inbox"]
    for m in messages:
        out.append(
            f"[{m['uuid']}] from {m['from_agent']} - {m['msg_type']} ({m['status']}): {m['subject']}\n{m['body'] or ''}"
        )
    return [TextContent(type="text", text="\n".join(out))]


async def _handle_message_pickup(args: dict) -> list[TextContent]:
    db = _get_db()
    msg_uuid = str(args.get("id"))
    active_files = args.get("active_files")

    if isinstance(active_files, str):
        try:
            active_files = json.loads(active_files)
        except Exception:
            active_files = [active_files]

    try:
        with db.get_connection() as conn:
            cursor = conn.cursor()
            # Mark message as in_progress
            cursor.execute(
                "UPDATE messages SET status = 'in_progress', acked_at = CURRENT_TIMESTAMP WHERE uuid = ?",
                (msg_uuid,)
            )
            # Update presence
            files_json = json.dumps(active_files) if active_files else None
            cursor.execute(
                "UPDATE presence SET working_on = ?, last_active = CURRENT_TIMESTAMP WHERE agent_name = ?",
                (msg_uuid, "claude-code")
            )
            conn.commit()
        return [TextContent(type="text", text=f"Message {msg_uuid} picked up. Presence updated.")]
    except Exception as e:
        logger.error(f"Pickup failed: {e}")
        return [TextContent(type="text", text=f"Failed to pick up message {msg_uuid}.")]


async def _handle_message_respond(args: dict) -> list[TextContent]:
    client = _get_client()
    db = _get_db()
    reply_to = str(args.get("reply_to"))
    body = args.get("body", "")
    msg_type = args.get("type", "response")
    context_payload = args.get("context")

    if isinstance(context_payload, str):
        try:
            context_payload = json.loads(context_payload)
        except Exception:
            pass

    # Look up parent message
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM messages WHERE uuid = ?", (reply_to,))
        parent = cursor.fetchone()

    if not parent:
        return [TextContent(type="text", text=f"Parent message {reply_to} not found.")]

    to_agent = parent['from_agent']
    subject = f"Re: {parent['subject']}"
    w_msgtype = _MSGTYPE_MAP.get(msg_type, "inform")

    try:
        msg_uuid = client.send(
            to=to_agent,
            subject=subject,
            body=body,
            msg_type=w_msgtype,
            payload=context_payload if isinstance(context_payload, dict) else None,
            reply_to=reply_to,
            context_id=parent['context_id'],
        )
    except Exception as e:
        logger.error(f"Whispers respond failed: {e}")
        return [TextContent(type="text", text=f"Failed to respond: {e}")]

    return [TextContent(type="text", text=f"Response {msg_uuid} sent.")]


async def _handle_message_thread(args: dict) -> list[TextContent]:
    db = _get_db()
    msg_uuid = str(args.get("id"))

    with db.get_connection() as conn:
        cursor = conn.cursor()
        # Get the context_id from the message
        cursor.execute("SELECT context_id FROM messages WHERE uuid = ?", (msg_uuid,))
        row = cursor.fetchone()
        if not row or not row['context_id']:
            return [TextContent(type="text", text=f"No thread found for {msg_uuid}.")]

        # Fetch all messages in this thread
        cursor.execute(
            "SELECT * FROM messages WHERE context_id = ? ORDER BY created_at ASC",
            (row['context_id'],)
        )
        thread = cursor.fetchall()

    if not thread:
        return [TextContent(type="text", text=f"No thread found for {msg_uuid}.")]

    out = [f"# Thread for message {msg_uuid}"]
    for m in thread:
        out.append(f"[{m['uuid']}] {m['from_agent']} -> {m['to_agent']}: {m['body'] or ''}")
    return [TextContent(type="text", text="\n".join(out))]


async def _handle_message_done(args: dict) -> list[TextContent]:
    db = _get_db()
    msg_uuid = str(args.get("id"))

    try:
        with db.get_connection() as conn:
            cursor = conn.cursor()
            # Get context_id to mark whole thread done
            cursor.execute("SELECT context_id FROM messages WHERE uuid = ?", (msg_uuid,))
            row = cursor.fetchone()

            if row and row['context_id']:
                cursor.execute(
                    "UPDATE messages SET status = 'done' WHERE context_id = ?",
                    (row['context_id'],)
                )
            else:
                cursor.execute(
                    "UPDATE messages SET status = 'done' WHERE uuid = ?",
                    (msg_uuid,)
                )

            # Clear presence working_on
            cursor.execute(
                "UPDATE presence SET working_on = NULL, last_active = CURRENT_TIMESTAMP WHERE agent_name = ?",
                ("claude-code",)
            )
            conn.commit()

        return [TextContent(type="text", text=f"Thread for message {msg_uuid} marked as done.")]
    except Exception as e:
        logger.error(f"Done failed: {e}")
        return [TextContent(type="text", text=f"Failed to mark done for {msg_uuid}.")]


async def _handle_presence_who(args: dict) -> list[TextContent]:
    db = _get_db()

    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT agent_name, status, working_on, reception_mode FROM presence WHERE status IN ('online', 'idle')"
        )
        agents = cursor.fetchall()

    if not agents:
        return [TextContent(type="text", text="No agents online.")]

    out = ["# Online Agents"]
    for a in agents:
        working_on = f"(Working on [{a['working_on']}])" if a['working_on'] else ""
        mode = f"[{a['reception_mode'].upper()}]" if a['reception_mode'] != 'open' else ""
        out.append(f"- {a['agent_name']}: {a['status']} {mode} {working_on}")
    return [TextContent(type="text", text="\n".join(out))]


# ---------------------------------------------------------------------------
# New Whispers tools — mode control
# ---------------------------------------------------------------------------

async def _handle_signal_mode_set(args: dict) -> list[TextContent]:
    client = _get_client()
    mode = args.get("mode", "open")
    allow_senders = args.get("allow_senders")

    if isinstance(allow_senders, str):
        try:
            allow_senders = json.loads(allow_senders)
        except Exception:
            allow_senders = [allow_senders]

    try:
        client.set_mode(mode, allow_senders=allow_senders)
        filter_desc = f" (allow: {allow_senders})" if allow_senders else ""
        return [TextContent(type="text", text=f"Reception mode set to {mode.upper()}{filter_desc}.")]
    except Exception as e:
        return [TextContent(type="text", text=f"Failed to set mode: {e}")]


async def _handle_signal_mode_get(args: dict) -> list[TextContent]:
    db = _get_db()
    agent = args.get("agent", "claude-code")

    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT reception_mode, mode_filter, mode_set_at, mode_set_by FROM presence WHERE agent_name = ?",
            (agent,)
        )
        row = cursor.fetchone()

    if not row:
        return [TextContent(type="text", text=f"Agent {agent} not found in presence.")]

    mode = row['reception_mode'] or 'open'
    filter_str = row['mode_filter'] or '{}'
    set_at = row['mode_set_at'] or 'unknown'
    set_by = row['mode_set_by'] or 'unknown'

    return [TextContent(type="text", text=f"Agent {agent}: mode={mode.upper()}, filter={filter_str}, set_at={set_at}, set_by={set_by}")]
