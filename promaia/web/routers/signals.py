from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel
from typing import Optional, List, Any
import logging
import json
from promaia.storage.signals_db import SignalsDB

logger = logging.getLogger(__name__)

router = APIRouter()

class MessageSendReq(BaseModel):
    from_agent: str = "maia"
    to_agent: Optional[str] = None
    msg_type: str = "request"
    subject: str
    body: str = ""
    context_payload: Optional[dict] = None
    priority: str = "normal"
    reply_to: Optional[str] = None

class MessagePickupReq(BaseModel):
    active_files: Optional[List[str]] = None

@router.post("/message")
async def send_message(req: MessageSendReq):
    db = SignalsDB()
    msg_uuid = db.send_message(req.from_agent, req.to_agent, req.msg_type, req.subject, req.body, req.context_payload, req.priority, req.reply_to)
    return {"status": "success", "uuid": msg_uuid}

@router.get("/inbox/{agent}")
async def check_inbox(agent: str):
    db = SignalsDB()
    messages = db.check_inbox(agent)
    return {"status": "success", "messages": messages}

@router.get("/message/{uuid}/thread")
async def get_thread(uuid: str):
    db = SignalsDB()
    thread = db.get_thread(id)
    return {"status": "success", "thread": thread}

@router.post("/message/{uuid}/ack")
async def pickup_message(uuid: str, req: MessagePickupReq):
    db = SignalsDB()
    # Assume Maia picks it up, or generic
    success = db.pickup_message(uuid, "maia", req.active_files)
    return {"status": "success" if success else "failed"}

@router.get("/presence")
async def get_presence():
    db = SignalsDB()
    agents = db.get_online_agents()
    return {"status": "success", "agents": agents}

@router.post("/message/{uuid}/close")
async def close_message(uuid: str):
    db = SignalsDB()
    success = db.complete_message(uuid, "maia")
    return {"status": "success" if success else "failed"}
