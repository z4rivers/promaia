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
from fastapi import APIRouter, HTTPException, UploadFile, File, WebSocket, WebSocketDisconnect
from fastapi.responses import Response
from pydantic import BaseModel

from promaia.web.brain_chat import chat, transcribe_audio
from promaia.storage.postgres_db import get_postgres_db, pg_connect
from promaia.storage.vector_db import VectorDBManager
from promaia.brain.core.memory_pipeline import capture_memory
import time
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)
router = APIRouter()

active_text_listeners = set()

@router.websocket("/stream/text")
async def text_stream_endpoint(websocket: WebSocket):
    await websocket.accept()
    active_text_listeners.add(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        active_text_listeners.remove(websocket)

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
    """Background task to summarize a completed voice session and propose memories to the dashboard."""
    if not transcript_log:
        return
        
    if rescued_memories is None:
        rescued_memories = []
        
    try:
        logger.info(f"Generating async session review for {len(transcript_log)} turns...")
        from google import genai
        from google.genai import types
        client = genai.Client(api_key=os.environ.get("GOOGLE_API_KEY"))
        
        # Format transcript
        lines = []
        for t in transcript_log:
            role = "Promaia" if t["role"] == "promaia" else "Zack"
            lines.append(f"{role}: {t['text']}")
        full_transcript = "\n".join(lines)
        
        prompt = (
            "You are reviewing a raw audio transcript between Zack and his AI assistant Promaia. "
            "Write a very concise 2-3 sentence summary of the conversation. "
            "Also, extract any significant decisions, facts, or context that Promaia should remember. "
            f"\n\nTRANSCRIPT:\n{full_transcript}"
        )
        
        # We need a proper JSON schema
        schema = {
            "type": "OBJECT",
            "properties": {
                "summary": {"type": "STRING", "description": "Concise 2-3 sentence summary"},
                "proposed_memories": {
                    "type": "ARRAY",
                    "items": {
                        "type": "OBJECT",
                        "properties": {
                            "content": {"type": "STRING", "description": "The extracted fact"},
                            "domain": {"type": "STRING", "description": "e.g., personal, project, heatpup"}
                        },
                        "required": ["content", "domain"]
                    }
                }
            },
            "required": ["summary", "proposed_memories"]
        }
        
        response = await client.aio.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=schema,
            ),
        )
        
        result_json = json.loads(response.text)
        
        proposed = result_json.get("proposed_memories", [])
        for rm in rescued_memories:
            proposed.append({
                "content": rm.get("content", ""),
                "domain": rm.get("domain", "general")
            })
        
        # Save to PostgreSQL
        with pg_connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO brain.audio_session_reviews 
                    (raw_transcript, summary, proposed_memories, status)
                    VALUES (%s, %s, %s, 'pending')
                    """,
                    (json.dumps(transcript_log), result_json.get("summary", ""), json.dumps(proposed))
                )
        logger.info("Successfully saved AudioSessionReview to Postgres database.")
    except Exception as e:
        logger.error(f"Failed to generate session review: {e}", exc_info=True)



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
    
    # 0. Inject Phase 0 Clock & Calendar Context
    current_time_str = datetime.now().strftime("%A, %B %d, %Y at %I:%M %p")
    system_ctx = f"The current time is: {current_time_str}\n\n"
    
    try:
        from promaia.brain.context_loaders import get_calendar_context
        system_ctx += await get_calendar_context()
    except Exception as e:
        logger.warning(f"Calendar fetch failed for Live API context: {e}")

    # 1. Core Identity & Behavioral Instructions (PERSONALITY-MANIFEST led)
    try:
        prompt_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "prompts", "voice_agent_system.md")
        with open(prompt_path, "r", encoding="utf-8") as f:
            system_ctx += f.read() + "\n\n"
    except Exception as e:
        logger.warning(f"Failed to load voice agent system prompt from {prompt_path}: {e}")
        # Fallback to a minimal instruction set if file read fails
        system_ctx += "You are Promaia, a helpful voice assistant.\n\n"
    
    try:
        from promaia.brain.context_loaders import get_muninn_context
        system_ctx += await get_muninn_context()
    except Exception as e:
        logger.warning(f"Muninn context fetch for Live API failed: {e}. Degrading gracefully.")

    # 2. Inject recent conversation summaries (Compressed)
    try:
        from promaia.storage.postgres_db import get_postgres_db
        db = get_postgres_db()
        recent_sessions = db.fetch_all(
            """
            SELECT summary, status, created_at 
            FROM brain.audio_session_reviews 
            WHERE summary IS NOT NULL AND status IN ('pending', 'accepted')
            ORDER BY created_at DESC 
            LIMIT 2
            """
        )
        if recent_sessions:
            system_ctx += "\n[RECENT CONVERSATIONS]\n"
            for s in recent_sessions:
                dt_str = s['created_at'].strftime("%Y-%m-%d %H:%M") if hasattr(s['created_at'], 'strftime') else str(s['created_at'])
                status_label = "UNAPPROVED" if s['status'] == 'pending' else "APPROVED"
                # Token budget: limit summary length
                sum_text = s['summary'][:300] + "..." if len(s['summary']) > 300 else s['summary']
                system_ctx += f"- [{dt_str}] [{status_label}] {sum_text}\n"
            system_ctx += (
                "These are background context. Use them to maintain conversational continuity "
                "when he brings them up. His immediate question always comes first.\n"
            )
            logger.info(f"Live API populated with {len(recent_sessions)} compressed session summaries.")
    except Exception as e:
        logger.warning(f"Failed to fetch recent sessions for context: {e}")

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
                                        # Text/Transcript payload (can be logged or displayed)
                                        elif part.text:
                                            transcript_log.append({"role": "promaia", "text": part.text, "time": time.time()})
                                            await broadcast_chat_log("assistant", part.text)
                                            await websocket.send_json({
                                                "serverContent": {
                                                    "modelTurn": {
                                                        "parts": [{"text": part.text}]
                                                    }
                                                }
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
                                    await session.send(input={"function_responses": tool_responses})
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

