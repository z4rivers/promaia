import json
import logging
from typing import List
from mcp.types import TextContent
from promaia.storage.signals_db import SignalsDB
import httpx
import os

logger = logging.getLogger(__name__)

async def _handle_message_send(args: dict) -> list[TextContent]:
    db = SignalsDB()
    to_agent = args.get("to")
    msg_type = args.get("type", "request")
    subject = args.get("subject", "No subject")
    body = args.get("body", "")
    context_payload = args.get("context")
    priority = args.get("priority", "normal")
    
    if isinstance(context_payload, str):
        try:
            context_payload = json.loads(context_payload)
        except:
            pass
            
    # Defaulting from_agent to claude-code since this is MCP
    msg_uuid = db.send_message("claude-code", to_agent, msg_type, subject, body, context_payload, priority)
    
    # Trigger WebSocket push if Maia or 'any'
    if to_agent == "maia" or to_agent is None:
        try:
            async with httpx.AsyncClient() as client:
                port = os.environ.get("PORT", "8476")
                url = f"http://localhost:{port}/api/brain/broadcast"
                payload = {"type": "message", "uuid": msg_uuid, "from": "claude-code", "subject": subject, "msg_type": msg_type}
                await client.post(url, json={"text": json.dumps(payload)})
        except Exception as e:
            logger.error(f"Failed to push signal to websocket: {e}")

    return [TextContent(type="text", text=f"Message {msg_uuid} sent successfully.")]

async def _handle_message_check(args: dict) -> list[TextContent]:
    db = SignalsDB()
    messages = db.check_inbox("claude-code")
    if not messages:
        return [TextContent(type="text", text="No new messages.")]
        
    out = ["# Inbox"]
    for m in messages:
        out.append(f"[{m['id']}] from {m['from_agent']} - {m['msg_type']} ({m['status']}): {m['subject']}\n{m['body']}")
    return [TextContent(type="text", text="\n".join(out))]

async def _handle_message_pickup(args: dict) -> list[TextContent]:
    db = SignalsDB()
    msg_uuid = args.get("id")
    active_files = args.get("active_files")
    
    if isinstance(active_files, str):
        try:
            active_files = json.loads(active_files)
        except:
            active_files = [active_files]
            
    success = db.pickup_message(msg_uuid, "claude-code", active_files)
    if success:
        return [TextContent(type="text", text=f"Message {msg_uuid} picked up. Presence updated.")]
    return [TextContent(type="text", text=f"Failed to pick up message {msg_uuid}.")]

async def _handle_message_respond(args: dict) -> list[TextContent]:
    db = SignalsDB()
    reply_to = args.get("reply_to")
    body = args.get("body", "")
    msg_type = args.get("type", "response")
    context_payload = args.get("context")
    
    if isinstance(context_payload, str):
        try:
            context_payload = json.loads(context_payload)
        except:
            pass

    parent = db.get_message(reply_to)
    if not parent:
        return [TextContent(type="text", text=f"Parent message {reply_to} not found.")]
        
    to_agent = parent['from_agent']
    subject = f"Re: {parent['subject']}"
    
    msg_uuid = db.send_message("claude-code", to_agent, msg_type, subject, body, context_payload, reply_to=reply_to)
    
    if to_agent == "maia" or to_agent is None:
        try:
            async with httpx.AsyncClient() as client:
                port = os.environ.get("PORT", "8476")
                url = f"http://localhost:{port}/api/brain/broadcast"
                payload = {"type": "message", "uuid": msg_uuid, "from": "claude-code", "subject": subject, "msg_type": msg_type}
                await client.post(url, json={"text": json.dumps(payload)})
        except Exception as e:
            logger.error(f"Failed to push signal to websocket: {e}")
            
    return [TextContent(type="text", text=f"Response {msg_uuid} sent.")]

async def _handle_message_thread(args: dict) -> list[TextContent]:
    db = SignalsDB()
    msg_uuid = args.get("id")
    thread = db.get_thread(msg_uuid)
    if not thread:
        return [TextContent(type="text", text=f"No thread found for {msg_uuid}.")]
        
    out = [f"# Thread for message {msg_uuid}"]
    for m in thread:
        out.append(f"[{m['id']}] {m['from_agent']} -> {m['to_agent'] or 'any'}: {m['body']}")
    return [TextContent(type="text", text="\n".join(out))]

async def _handle_message_done(args: dict) -> list[TextContent]:
    db = SignalsDB()
    msg_uuid = args.get("id")
    success = db.complete_message(msg_uuid, "claude-code")
    if success:
        return [TextContent(type="text", text=f"Thread for message {msg_uuid} marked as done.")]
    return [TextContent(type="text", text=f"Failed to mark done for {msg_uuid}.")]

async def _handle_presence_who(args: dict) -> list[TextContent]:
    db = SignalsDB()
    agents = db.get_online_agents()
    if not agents:
        return [TextContent(type="text", text="No agents online.")]
        
    out = ["# Online Agents"]
    for a in agents:
        working_on = f"(Working on [{a['working_on']}])" if a['working_on'] else ""
        out.append(f"- {a['agent_name']}: {a['status']} {working_on}")
    return [TextContent(type="text", text="\n".join(out))]
