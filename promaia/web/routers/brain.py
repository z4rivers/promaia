"""
Brain chat + voice + TTS API endpoints for the web interface.

POST /api/brain/chat     — text message in, response out
POST /api/brain/voice    — audio blob in, transcription + response out
POST /api/brain/tts      — text in, WAV audio out (Gemini native TTS)
"""
import asyncio
import base64
import json
import logging
import os
from fastapi import APIRouter, HTTPException, UploadFile, File, WebSocket, WebSocketDisconnect, Form
from fastapi.responses import Response
from pydantic import BaseModel
from typing import List, Optional

from promaia.web.brain_chat import chat, transcribe_audio
from promaia.storage.db_factory import get_db, db_connect
from promaia.storage.vector_db import VectorDBManager
from promaia.brain.core.memory_pipeline import capture_memory
import time
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)
router = APIRouter()

active_text_listeners = set()
room_listeners: dict[int, set] = {1: set()}

# Dependency to inject DB into routes
def get_db_instance():
    return get_db()


# ---------------------------------------------------------------------------
# DEPRECATED: Old heartbeat push model — replaced by brain daemon /health
# The brain is now an always-on daemon. Dashboard polls /api/brain/health
# (proxy to daemon's /health endpoint) instead of these push-based endpoints.
# Kept temporarily for backward compatibility — will be removed in v4.0.
# ---------------------------------------------------------------------------

class HeartbeatRequest(BaseModel):
    session_id: str | None = None
    agent_name: str | None = None


@router.post("/heartbeat")
async def mcp_heartbeat(req: HeartbeatRequest = HeartbeatRequest()):
    """DEPRECATED: Brain is now an always-on daemon. This endpoint is a no-op."""
    return {"status": "deprecated", "message": "Brain is now a daemon. Use /api/brain/health instead."}


@router.get("/heartbeat")
async def mcp_heartbeat_status():
    """DEPRECATED: Use /api/brain/health instead."""
    import httpx
    port = int(os.environ.get("BRAIN_MCP_PORT", "8751"))
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"http://127.0.0.1:{port}/health", timeout=3.0)
            return {"connected": True, "deprecated": True, "message": "Use /api/brain/health"}
    except Exception:
        return {"connected": False, "deprecated": True, "message": "Use /api/brain/health"}

# ---------------------------------------------------------------------------
# Voice Context Cache — keeps calendar/Muninn/prompt ready so connect is instant
# ---------------------------------------------------------------------------
_voice_ctx_cache = {
    "calendar": {"text": "", "ts": 0, "ttl": 120},   # 2 min TTL
    "muninn":   {"text": "", "ts": 0, "ttl": 60},     # 60s TTL
    "prompt":   {"text": "", "ts": 0, "ttl": 3600},   # 1 hour (file rarely changes)
}

async def _refresh_single(key: str):
    """Refresh one cache entry if stale. Returns immediately if still warm."""
    entry = _voice_ctx_cache[key]
    if time.time() - entry["ts"] <= entry["ttl"]:
        return  # Still warm
    
    t0 = time.time()
    try:
        if key == "calendar":
            from promaia.brain.context_loaders import get_calendar_context
            entry["text"] = await asyncio.wait_for(get_calendar_context(), timeout=4.0)
        elif key == "muninn":
            from promaia.brain.context_loaders import get_muninn_context
            entry["text"] = await asyncio.wait_for(get_muninn_context(), timeout=4.0)
        elif key == "prompt":
            prompt_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), "prompts", "voice_agent_system.md")
            with open(prompt_path, "r", encoding="utf-8") as f:
                entry["text"] = f.read()
        entry["ts"] = time.time()
        logger.info(f"[VoiceCache] {key} refreshed in {time.time()-t0:.2f}s")
    except asyncio.TimeoutError:
        logger.warning(f"[VoiceCache] {key} timed out after {time.time()-t0:.2f}s — keeping stale data")
    except Exception as e:
        logger.warning(f"[VoiceCache] {key} refresh failed ({time.time()-t0:.2f}s): {e}")
        if key == "prompt" and not entry["text"]:
            entry["text"] = "You are Promaia, a helpful voice assistant."

async def _refresh_voice_context():
    """Refresh all stale cache entries IN PARALLEL. 5s hard ceiling."""
    try:
        await asyncio.wait_for(
            asyncio.gather(
                _refresh_single("prompt"),
                _refresh_single("calendar"),
                _refresh_single("muninn"),
                return_exceptions=True
            ),
            timeout=5.0
        )
    except asyncio.TimeoutError:
        logger.warning("[VoiceCache] Overall refresh timed out at 5s — proceeding with what we have")

async def prewarm_voice_context():
    """Call at server startup to ensure first voice connect is instant."""
    logger.info("[VoiceCache] Pre-warming voice context...")
    await _refresh_voice_context()
    logger.info("[VoiceCache] Pre-warm complete")



@router.websocket("/stream/text")
async def text_stream_endpoint(websocket: WebSocket):
    from promaia.web.auth import COOKIE_NAME, _verify_token, is_auth_enabled
    
    # Authenticate via cookie from handshake before accepting
    if is_auth_enabled() and os.environ.get("PYTHON_ENV") == "production":
        cookie = websocket.cookies.get(COOKIE_NAME)
        if not cookie or not _verify_token(cookie):
            await websocket.close(code=1008)
            return
            
    await websocket.accept()
    active_text_listeners.add(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        active_text_listeners.remove(websocket)

@router.websocket("/maia_stream")
async def maia_stream_endpoint(websocket: WebSocket, room_id: int = 1):
    """Additive WebSocket endpoint specifically for the Maia Web Widget OR topic rooms."""
    from promaia.web.auth import COOKIE_NAME, _verify_token, is_auth_enabled
    
    # Authenticate via cookie from handshake before accepting
    if is_auth_enabled() and os.environ.get("PYTHON_ENV") == "production":
        cookie = websocket.cookies.get(COOKIE_NAME)
        if not cookie or not _verify_token(cookie):
            await websocket.close(code=1008)
            return
            
    await websocket.accept()
    if room_id not in room_listeners:
        room_listeners[room_id] = set()
    room_listeners[room_id].add(websocket)
    
    from promaia.storage.signals_db import SignalsDB
    SignalsDB().update_presence("maia", status="online")
    
    from promaia.web.maia_bridge import generate_maia_response
    
    async def status_callback(status: str):
        try:
            await websocket.send_json({"type": "activity", "text": status})
        except Exception:
            pass

    try:
        while True:
            data = await websocket.receive_text()
            try:
                payload = json.loads(data)
                user_message = payload.get("message", data)
            except json.JSONDecodeError:
                user_message = data
                
            if not isinstance(user_message, str) or not user_message.strip():
                continue
                
            reply = await generate_maia_response(user_message, status_callback=status_callback)
            
            try:
                await websocket.send_json({
                    "type": "response",
                    "text": reply
                })
            except Exception:
                pass
                
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f"Maia stream error: {e}", exc_info=True)
    finally:
        if room_id in room_listeners and websocket in room_listeners[room_id]:
            room_listeners[room_id].remove(websocket)
        from promaia.storage.signals_db import SignalsDB
        if not any(room_listeners.values()):
            SignalsDB().update_presence("maia", status="offline")

async def broadcast_maia_activity(text: str, signal_data: dict = None, room_id: int = 1):
    """Broadcast an activity message to all open sessions in a specific room."""
    dead_sockets = set()
    listeners = room_listeners.get(room_id, set())
    
    for ws in listeners:
        try:
            if signal_data:
                await ws.send_json(signal_data)
            else:
                await ws.send_json({"type": "activity", "text": text})
        except Exception:
            dead_sockets.add(ws)
            
    for ws in dead_sockets:
        listeners.remove(ws)

class BroadcastRequest(BaseModel):
    text: str
    signal_data: Optional[dict] = None
    room_id: int = 1

@router.post("/broadcast")
async def api_broadcast(req: BroadcastRequest):
    """Endpoint for IDEs and MCP servers to broadcast activity to the dashboard."""
    await broadcast_maia_activity(req.text, req.signal_data, req.room_id)
    return {"status": "broadcast_sent"}

# --- Room CRUD Endpoints ---
class CreateRoomRequest(BaseModel):
    name: str
    topic: str
    artifact_ref: Optional[str] = None
    created_by: str = "zack"

@router.post("/rooms", tags=["Rooms"])
async def create_room(req: CreateRoomRequest):
    from promaia.storage.signals_db import SignalsDB
    db = SignalsDB()
    room_id = db.create_room(req.name, req.topic, req.created_by, 'topic', req.artifact_ref)
    return {"room_id": room_id}

@router.get("/rooms", tags=["Rooms"])
async def list_active_rooms():
    from promaia.storage.signals_db import SignalsDB
    db = SignalsDB()
    rooms = db.get_active_rooms()
    return {"rooms": rooms}

@router.get("/rooms/{room_id}/members", tags=["Rooms"])
async def get_room_members(room_id: int):
    from promaia.storage.signals_db import SignalsDB
    db = SignalsDB()
    members = db.get_room_members(room_id)
    return {"members": members}

@router.get("/rooms/{room_id}/messages", tags=["Rooms"])
async def get_room_messages_api(room_id: int, limit: int = 50):
    from promaia.storage.signals_db import SignalsDB
    db = SignalsDB()
    messages = db.get_room_messages(room_id, limit)
    return {"messages": messages}

class SummonRequest(BaseModel):
    agent_name: str
    role: str = "member"

@router.post("/rooms/{room_id}/summon", tags=["Rooms"])
async def summon_agent(room_id: int, req: SummonRequest):
    from promaia.storage.signals_db import SignalsDB
    db = SignalsDB()
    success = db.join_room(room_id, req.agent_name, req.role)
    if success:
        return {"status": "summoned", "agent": req.agent_name}
    raise HTTPException(status_code=400, detail="Failed to summon agent")

@router.post("/rooms/{room_id}/dissolve", tags=["Rooms"])
async def dissolve_room(room_id: int):
    from promaia.storage.signals_db import SignalsDB
    db = SignalsDB()
    success = db.dissolve_room(room_id)
    if success:
        return {"status": "dissolved"}
    raise HTTPException(status_code=400, detail="Failed to dissolve room")


class CommitCaptureRequest(BaseModel):
    commit_hash: str
    message: str
    branch: str
    files_changed: str

@router.post("/capture_commit")
async def api_capture_commit(req: CommitCaptureRequest):
    """Webhook triggered by post-commit git hooks to auto-log work into MuninnDB."""
    content = (
        f"Git Commit on branch '{req.branch}': {req.message}\\n"
        f"Hash: {req.commit_hash}\\n"
        f"Files changed:\\n{req.files_changed}"
    )
    # Using the existing MuninnDB capture pipeline
    import traceback
    try:
        from promaia.brain.core.memory_pipeline import capture_memory
        from promaia.storage.db_factory import get_db
        from promaia.storage.vector_db import VectorDBManager
        db = get_db()
        # Dual-writes to MuninnDB
        await capture_memory(db=db, vector_mgr=VectorDBManager(), content=content, session_id=req.commit_hash, domain_name="promaia_codebase", source="git_hook")
        
        # Broadcast that a commit was captured
        await broadcast_maia_activity("Captured new branch commit into permanent memory.")
        return {"status": "captured"}
    except Exception as e:
        logger.error(f"Failed to capture commit: {e}\\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail="Failed to capture commit")


@router.post("/capture_multimodal")
async def api_capture_multimodal(
    message: str = Form(...),
    files: List[UploadFile] = File(None),
    room_id: int = Form(1)
):
    """Hybrid out-of-band capture for heavy media. Broadcasts response down the WebSocket."""
    import uuid
    import shutil
    
    image_paths = []
    audio_paths = []
    document_paths = []
    
    if files:
        asset_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))), "data", "media")
        os.makedirs(asset_dir, exist_ok=True)
        
        for file in files:
            if not file.filename:
                continue
            ext = os.path.splitext(file.filename)[1].lower()
            file_id = str(uuid.uuid4())
            safe_filename = f"{file_id}{ext}"
            save_path = os.path.join(asset_dir, safe_filename)
            
            try:
                with open(save_path, "wb") as buffer:
                    shutil.copyfileobj(file.file, buffer)
                    
                mime = file.content_type or ""
                if mime.startswith("image/") or ext in [".png", ".jpg", ".jpeg", ".webp"]:
                    image_paths.append(save_path)
                elif mime.startswith("audio/") or ext in [".wav", ".mp3", ".ogg", ".aac"]:
                    audio_paths.append(save_path)
                elif mime == "application/pdf" or mime.startswith("text/") or ext in [".pdf", ".txt", ".csv", ".md"]:
                    document_paths.append(save_path)
            except Exception as e:
                logger.error(f"Failed to save uploaded file {file.filename}: {e}")
                
    # Alert the widget we're working (broadcast)
    await broadcast_maia_activity("Analyzing multimodal input...", room_id=room_id)
    
    # Process through the Maia Bridge (brain_chat handles Muninn search & formatting)
    from promaia.web.maia_bridge import generate_maia_response
    
    async def status_callback(status: str):
        await broadcast_maia_activity(status, room_id=room_id)
        
    try:
        reply = await generate_maia_response(
            message, 
            status_callback=status_callback, 
            image_paths=image_paths, 
            audio_paths=audio_paths,
            document_paths=document_paths
        )
        
        # Now do the dual-write capture with the media
        from promaia.storage.db_factory import get_db
        from promaia.storage.vector_db import VectorDBManager
        from promaia.brain.core.memory_pipeline import capture_memory
        
        db = get_db()
        # This will use generate_multimodal_embedding under the hood
        await capture_memory(
            db=db, 
            vector_mgr=VectorDBManager(), 
            content=message, 
            session_id=str(uuid.uuid4()), 
            domain_name="promaia_multimodal", 
            source="dashboard_widget",
            image_paths=image_paths,
            audio_paths=audio_paths,
            document_paths=document_paths
        )
        
        # Broadcast the actual response back to the websocket
        for ws in room_listeners.get(room_id, set()):
            try:
                await ws.send_json({
                    "type": "response",
                    "text": reply
                })
            except Exception:
                pass
                
        return {"status": "success", "images": len(image_paths), "audio": len(audio_paths)}
    except Exception as e:
        logger.error(f"Multimodal capture failed: {e}", exc_info=True)
        await broadcast_maia_activity(f"Error: {e}")
        raise HTTPException(status_code=500, detail="Multimodal engine failed")

async def broadcast_chat_log(role: str, text: str):
    dead_sockets = set()
    for ws in active_text_listeners:
        try:
            await ws.send_json({
                "type": "chat_log",
                "role": role,
                "text": text
            })
        except Exception:
            dead_sockets.add(ws)
    for ws in dead_sockets:
        active_text_listeners.remove(ws)

async def generate_session_review(transcript_log: list, rescued_memories: list = None):
    """Background task to route voice session transcripts and staged memories.
    Replaces the old 'audio_session_reviews' queue with a silent Triage + Capture pipeline.
    """
    import uuid
    from google import genai
    from google.genai import types

    if not transcript_log:
        return
        
    if rescued_memories is None:
        rescued_memories = []

    session_id = str(uuid.uuid4())
    
    # Process staged (rescued) memories independently immediately
    if rescued_memories:
        logger.info(f"Processing {len(rescued_memories)} rescued memories outside of triage.")
        for rm in rescued_memories:
            # We don't want strict triage on these - they were explicitly staged by tool calls
            asyncio.create_task(_commit_signal(
                content=rm.get("content", ""),
                session_id=session_id,
                domain_name=rm.get("domain", "voice_session"),
                source="voice_rescued"
            ))

    # 1. Zero-Cost Heuristic (Gate 1)
    # Check length
    word_count = sum(len(t['text'].split()) for t in transcript_log)
    user_turns = sum(1 for t in transcript_log if t["role"] == "user")
    
    # We already checked len(transcript_log) > 2 before calling this, but double check user participation
    if word_count < 15 or user_turns == 0:
        logger.info(f"Voice session failed zero-cost heuristic (words: {word_count}, user_turns: {user_turns}). Logging as noise and dropping.")
        _log_brain_event("voice_noise", {"reason": "too_short", "word_count": word_count}, session_id)
        return

    # Prepare transcript string for Opus
    lines = []
    for t in transcript_log:
        role = "Promaia" if t["role"] == "promaia" else "Zack"
        lines.append(f"{role}: {t['text']}")
    full_transcript = "\n".join(lines)

    # 2. Strict Triage Filter
    logger.info(f"Running triage filter on voice session ({word_count} words)...")
    try:
        from google import genai
        from google.genai import types
        import json
        
        api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        client = genai.Client(api_key=api_key)
        
        triage_prompt = (
            "You are reviewing a raw audio transcript between Zack and his AI assistant Promaia.\n"
            "Evaluate the transcript and classify it into exactly one of these four categories:\n"
            "1. 'signal' - A genuine conversation with substance, requests, ideas, or back-and-forth.\n"
            "2. 'noise' - Audio tests ('hello?', 'can you hear me?'), connection issues, false triggers, or endless loops.\n"
            "3. 'fragment' - Cut-off sentences or abrupt endings where no complete thought was communicated.\n"
            "4. 'feedback' - Zack is explicitly commenting on Promaia's voice, capability, or bugs, rather than doing work.\n"
            "\n"
            "Return ONLY a JSON object with 'category' (string) and 'reason' (short string explanation).\n"
            f"\n\nTRANSCRIPT:\n{full_transcript}"
        )
        
        schema = {
            "type": "OBJECT",
            "properties": {
                "category": {"type": "STRING", "enum": ["signal", "noise", "fragment", "feedback"]},
                "reason": {"type": "STRING"}
            },
            "required": ["category", "reason"]
        }
        
        from promaia.ai.models import GOOGLE_MODELS
        response = await client.aio.models.generate_content(
            model=GOOGLE_MODELS["flash"],
            contents=triage_prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=schema,
            ),
        )
        triage_result = json.loads(response.text)
        category = triage_result.get("category", "noise")
        reason = triage_result.get("reason", "unknown")
        
        logger.info(f"Voice triage result: {category.upper()} ({reason})")
        
        # 3. Routing
        if category in ["noise", "fragment"]:
            _log_brain_event("voice_noise", {"reason": reason, "category": category, "preview": full_transcript[:100]}, session_id)
            return
            
        elif category == "feedback":
            # For feedback, we log it and maybe capture it as a specific feedback memory
            _log_brain_event("voice_feedback", {"reason": reason, "preview": full_transcript[:100]}, session_id)
            # Route it through capture as well so it's not lost
            asyncio.create_task(_commit_signal(full_transcript, session_id, "promaia", "voice_feedback"))
            
        elif category == "signal":
            _log_brain_event("voice_signal", {"reason": reason, "word_count": word_count}, session_id)
            asyncio.create_task(_commit_signal(full_transcript, session_id, "voice_session", "voice_transcript"))
            
    except Exception as e:
        logger.error(f"Voice triage pipeline failed: {e}", exc_info=True)


def _log_brain_event(event_type: str, payload: dict, session_id: str):
    """Helper to cleanly log noise/signal events to SQLite."""
    try:
        from promaia.storage.db_factory import get_db
        db = get_db()
        db.execute(
            """
            INSERT INTO events (type, payload, source, session_id)
            VALUES (?, ?, 'voice_pipeline', ?)
            """,
            (event_type, json.dumps(payload), session_id)
        )
    except Exception as e:
        logger.warning(f"Could not log brain event (type={event_type}): {e}")


async def _commit_signal(content: str, session_id: str, domain_name: str, source: str):
    """Background task to run capture_memory for a vetted voice signal."""
    try:
        if not content.strip():
            return
        from promaia.storage.db_factory import get_db
        from promaia.storage.vector_db import VectorDBManager
        from promaia.brain.core.memory_pipeline import capture_memory
        
        db = get_db()
        vector_mgr = VectorDBManager()
        
        logger.info(f"Capturing voice signal ({source})...")
        await capture_memory(
            db=db,
            vector_mgr=vector_mgr,
            content=content,
            session_id=session_id,
            domain_name=domain_name,
            source=source
        )
    except Exception as e:
        logger.error(f"Async memory capture failed for voice signal: {e}", exc_info=True)



class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    reply: str
    transcript: str | None = None


@router.post("/chat", response_model=ChatResponse)
async def brain_chat(req: ChatRequest):
    """Send a text message, get a brain-powered response."""
    try:
        reply = await chat(req.message)
        return ChatResponse(reply=reply)
    except Exception as e:
        logger.error(f"Brain chat failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Brain unavailable")


@router.post("/voice", response_model=ChatResponse)
async def brain_voice(audio: UploadFile = File(...)):
    """Send recorded audio, get transcription + brain response."""
    audio_bytes = await audio.read()
    if len(audio_bytes) > 10 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Audio too large (max 10MB)")

    mime = audio.content_type or "audio/webm"
    transcript = await transcribe_audio(audio_bytes, mime)
    if not transcript:
        raise HTTPException(status_code=422, detail="Could not transcribe audio")

    reply = await chat(transcript)
    return ChatResponse(reply=reply, transcript=transcript)


@router.post("/tts")
async def brain_tts(req: ChatRequest):
    """Convert text to speech via Gemini native TTS, return audio."""
    try:
        from google import genai
        from google.genai import types
        from promaia.ai.models import GOOGLE_MODELS

        client = genai.Client(api_key=os.environ.get("GOOGLE_API_KEY"))

        # Gemini native TTS — uses the same API key as everything else
        response = await client.aio.models.generate_content(
            model=GOOGLE_MODELS["tts"],
            contents=f"Read this aloud naturally: {req.message}",
            config=types.GenerateContentConfig(
                response_modalities=["AUDIO"],
            ),
        )

        # Extract audio data from response
        if response.candidates and response.candidates[0].content and response.candidates[0].content.parts:
            part = response.candidates[0].content.parts[0]
            if hasattr(part, 'inline_data') and part.inline_data:
                audio_data = part.inline_data.data
                mime_type = part.inline_data.mime_type or "audio/wav"

                # If data is base64 encoded string, decode it
                if isinstance(audio_data, str):
                    audio_data = base64.b64decode(audio_data)

                # Gemini TTS currently returns raw PCM (audio/L16;codec=pcm;rate=24000).
                # The browser <audio> tag cannot play raw headerless PCM bytes. We must wrap it in a WAV header.
                if "audio/L16" in mime_type or "pcm" in mime_type.lower():
                    import io
                    import wave
                    
                    # Gemini defaults to 24000Hz, 1 channel, 16-bit PCM for its TTS models
                    sample_rate = 24000
                    if "rate=16000" in mime_type:
                        sample_rate = 16000
                        
                    wav_io = io.BytesIO()
                    with wave.open(wav_io, 'wb') as wav_file:
                        wav_file.setnchannels(1)
                        wav_file.setsampwidth(2) # 16-bit = 2 bytes
                        wav_file.setframerate(sample_rate)
                        wav_file.writeframes(audio_data)
                    
                    audio_data = wav_io.getvalue()
                    mime_type = "audio/wav"

                return Response(
                    content=audio_data,
                    media_type=mime_type,
                    headers={"Cache-Control": "no-cache"},
                )

        logger.warning("Gemini TTS returned no audio data")
        raise HTTPException(status_code=500, detail="TTS returned no audio")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"TTS failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"TTS failed: {e}")


@router.websocket("/stream")
async def brain_stream(websocket: WebSocket):
    """
    Real-time bidirectional audio stream using Gemini Multimodal Live API.
    Client sends 16kHz PCM base64 chunks. We send 24kHz PCM base64 chunks back.
    Includes Phase 10 MuninnDB context injection and Phase 11.5 Extraction logic.
    """
    await websocket.accept()
    t_start = time.time()
    
    # Refresh any stale cache entries (parallel, with 4s per-source timeout)
    await _refresh_voice_context()
    
    # Assemble system context from cache (instant — all in memory)
    current_time_str = datetime.now().strftime("%A, %B %d, %Y at %I:%M %p")
    system_ctx = f"The current time is: {current_time_str}\n\n"
    system_ctx += _voice_ctx_cache["prompt"]["text"] + "\n\n"
    system_ctx += _voice_ctx_cache["calendar"]["text"]
    system_ctx += _voice_ctx_cache["muninn"]["text"]
    
    logger.info(f"[Voice Connect] Context assembled in {time.time()-t_start:.2f}s")

    # 11.5 Tool Definitions for Staging and Committing Memories
    from promaia.brain.tool_definitions import memory_tools

    from google import genai
    from google.genai import types
    from promaia.ai.models import GOOGLE_MODELS

    client = genai.Client(api_key=os.environ.get("GOOGLE_API_KEY"))
    model_id = "gemini-2.5-flash-native-audio-preview-12-2025"

    # Setup config
    config = types.LiveConnectConfig(
        response_modalities=[types.Modality.AUDIO],
        system_instruction=types.Content(parts=[types.Part.from_text(text=system_ctx)]),
        tools=[memory_tools],
        realtime_input_config=types.RealtimeInputConfig(
            automatic_activity_detection=types.AutomaticActivityDetection(
                disabled=False,
                start_of_speech_sensitivity=types.StartSensitivity.START_SENSITIVITY_LOW,
                end_of_speech_sensitivity=types.EndSensitivity.END_SENSITIVITY_LOW,
                prefix_padding_ms=20,
                silence_duration_ms=500,
            )
        ),
    )

    try:
        transcript_log = []
        staged_memories = []
        async with client.aio.live.connect(model=model_id, config=config) as session:
            logger.info("Connected to Gemini Live API.")

            # Background task to receive from user (Browser -> Server -> Gemini)
            async def receive_from_client():
                try:
                    while True:
                        dataStr = await websocket.receive_text()
                        msg = json.loads(dataStr)
                        
                        if msg.get("realtimeInput"):
                            # Audio chunk sent from frontend (base64 PCM)
                            chunk_b64 = msg["realtimeInput"]["mediaChunks"][0]["data"]
                            chunk_bytes = base64.b64decode(chunk_b64)
                            # Use send_realtime_input per official Live API docs
                            await session.send_realtime_input(
                                audio={"data": chunk_bytes, "mime_type": "audio/pcm"}
                            )
                            
                        elif msg.get("clientContent"):
                            # Text turn or interrupt signal from frontend
                            turn_complete = msg.get("turnComplete", True)
                            text_msg = msg["clientContent"]["turns"][0]["parts"][0]["text"]
                            
                            transcript_log.append({"role": "user", "text": text_msg, "time": time.time()})
                            await broadcast_chat_log("user", text_msg)
                            
                            await session.send_client_content(
                                turns=[types.Content(parts=[types.Part.from_text(text=text_msg)])],
                                turn_complete=turn_complete
                            )
                except WebSocketDisconnect:
                    logger.info("WebSocket disconnected by client.")
                except Exception as e:
                    logger.error(f"Client receive loop error: {e}", exc_info=True)

            # Background task to receive from Gemini (Gemini -> Server -> Browser)
            async def receive_from_gemini():
                try:
                    while True:
                        async for response in session.receive():
                            server_content = response.server_content
                            if server_content is not None:
                                # Forward audio to frontend
                                if server_content.model_turn is not None:
                                    for part in server_content.model_turn.parts:
                                        # Audio payload
                                        if part.inline_data:
                                            audio_b64 = base64.b64encode(part.inline_data.data).decode('utf-8')
                                            await websocket.send_json({
                                                "serverContent": {
                                                    "modelTurn": {
                                                        "parts": [{"inlineData": {"data": audio_b64, "mimeType": part.inline_data.mime_type}}]
                                                    }
                                                }
                                            })
                                        # Text/Transcript payload — filter out internal tool-reasoning narration
                                        elif part.text:
                                            transcript_log.append({"role": "promaia", "text": part.text, "time": time.time()})
                                            # Only broadcast clean spoken responses, not tool-call narration
                                            # Tool reasoning starts with markdown bold (e.g. "**Logging User Feedback**")
                                            # or references tool names — this is internal and should never face the user
                                            _t = part.text.strip()
                                            _is_tool_narration = (
                                                _t.startswith("**") or
                                                "tool" in _t.lower() and any(kw in _t.lower() for kw in ["i'll", "i plan", "i am", "utilize", "capture", "log_system", "save_conversation"])
                                            )
                                            if not _is_tool_narration:
                                                await broadcast_chat_log("assistant", part.text)
                                            await websocket.send_json({
                                                "serverContent": {
                                                    "modelTurn": {
                                                        "parts": [{"text": part.text}]
                                                    }
                                                }
                                            })
    
                                # Handle interruption signal from Gemini's VAD
                                if server_content.interrupted:
                                    logger.info("[Voice] Gemini detected user interruption")
                                    await websocket.send_json({
                                        "serverContent": {"interrupted": True}
                                    })

                                # Handle Turn Complete signal
                                if server_content.turn_complete:
                                    await websocket.send_json({
                                        "serverContent": {"turnComplete": True}
                                    })
    
                            # Check for Function Calls (Step 11.5 Trigger 3 & Commit)
                            if response.tool_call is not None:
                                from promaia.brain.tool_handlers import handle_tool_call
                                tool_responses = []
                                for ft in response.tool_call.function_calls:
                                    func_res = await handle_tool_call(ft, websocket, staged_memories)
                                    tool_responses.append(func_res)
                                
                                if tool_responses:
                                    await session.send_tool_response(function_responses=tool_responses)
                except asyncio.CancelledError:
                    pass
                except Exception as e:
                    logger.error(f"Gemini receive loop error: {e}", exc_info=True)

            # Run both loops
            client_task = asyncio.create_task(receive_from_client())
            gemini_task = asyncio.create_task(receive_from_gemini())

            done, pending = await asyncio.wait(
                [client_task, gemini_task],
                return_when=asyncio.FIRST_COMPLETED
            )
            for p in pending:
                p.cancel()
                
            # Session ended. Pass rescued memories to async extraction along with transcript
            if transcript_log:
                # Only summarize if it was a real conversation (more than just a 1 turn greeting)
                if len(transcript_log) > 2:
                    logger.info(f"Voice session ended. Captured {len(transcript_log)} turns. Triggering async dashboard review extraction.")
                    asyncio.create_task(generate_session_review(transcript_log, rescued_memories=staged_memories))

    except Exception as e:
        logger.error(f"Live API connection failed: {e}", exc_info=True)
        try:
            await websocket.close(code=1011)
        except:
            pass

