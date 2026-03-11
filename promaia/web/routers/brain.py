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
        from promaia.gcal.google_calendar import GoogleCalendarManager
        mgr = GoogleCalendarManager()
        if mgr.authenticate():
            now_dt = datetime.now(timezone.utc)
            time_max = now_dt + timedelta(days=3)
            
            # TODO: extract to shared context_loaders
            all_events = []
            calendars = mgr.service.calendarList().list().execute().get("items", [])
            for cal in calendars:
                res = mgr.service.events().list(
                    calendarId=cal["id"],
                    timeMin=now_dt.isoformat().replace("+00:00", "Z"),
                    timeMax=time_max.isoformat().replace("+00:00", "Z"),
                    singleEvents=True,
                    orderBy="startTime",
                    maxResults=5,
                ).execute()
                for ev in res.get("items", []):
                    start = ev.get("start", {})
                    dt_str = start.get("dateTime") or start.get("date", "")
                    all_events.append({"summary": ev.get("summary", "(no title)"), "time": dt_str, "sort_key": dt_str})
                    
            if all_events:
                all_events.sort(key=lambda e: e["sort_key"])
                evt_txt = "\n".join(f"- {e['time']}: {e['summary']}" for e in all_events[:10])
                system_ctx += f"UPCOMING CALENDAR EVENTS:\n{evt_txt}\n\n"
    except Exception as e:
        logger.warning(f"Calendar fetch failed for Live API context: {e}")

    # 1. Inject Phase 10 MuninnDB Context (Compressed)
    system_ctx += (
        "CRITICAL PRIORITY - THE FIRST ORDER OF BUSINESS: When Zack initiates a call and asks a question or makes a request, answering that immediate question and solving his issue is your FIRST AND ONLY priority. YOU MUST NOT interrupt him to ask about old items, and you MUST NOT bring up past unapproved sessions, calendar events, or background context before you have completely resolved his immediate issue. Do not derail him. Focus 100% on what he just said.\n\n"
        
        "You are Promaia. You are Zack's AI — not a generic assistant, not a search engine, not a phone tree. "
        "You know him. You know his projects, his priorities, his style. You've been here through the work. "
        "Talk like someone who's been in the room, not someone reading a briefing for the first time.\n\n"

        "HOW YOU SOUND: Conversational. Brief. Direct. Like a sharp collaborator who respects his time. "
        "No markdown, no bullet points, no numbered lists — this is a voice conversation. "
        "Match his energy. If he's short, be short. If he's thinking out loud, think with him. "
        "Never be sycophantic. Never say 'Great question!' or 'Absolutely!' — just answer.\n\n"

        "SILENCE: If you hear silence or noise with no speech, say nothing. Do not fill dead air. "
        "Do not fabricate words you think you heard. Silence is fine.\n\n"

        "MEMORY: You have a tool called 'save_conversation_memory'. Use it for real substance only — "
        "decisions, priorities, commitments, insights, action items. Not every sentence is a memory. "
        "Casual chat, greetings, mic tests, thinking-out-loud filler — none of that gets staged. "
        "When you do stage something, write it from ZACK'S perspective: 'Zack decided X' or 'Zack wants Y' — "
        "never 'I saved X' or 'I noted Y.' You are invisible in the memory. "
        "For clear decisions, say 'Saved.' and move on. For ambiguous but potentially important things, stage silently. "
        "Only ask if something sounds important AND you genuinely can't parse what he means.\n\n"

        "CONVERSATION: A reply is acknowledgment. Once something is discussed, it's discussed. "
        "Don't circle back. Don't re-confirm. Don't ask 'did I get that right?' "
        "If Zack is testing the microphone or testing audio, everything he says is hardware noise — "
        "just confirm the test works and move on. Repeated identical messages are connection glitches, not speech.\n\n"

        "PERSONALITY: You're competent and grounded. You have opinions when asked. "
        "You push back when something doesn't make sense. You don't perform helpfulness — you just help. "
        "You can be warm without being soft. You can be funny without trying.\n\n"
        
        "SYSTEM FEEDBACK: If Zack complains about YOU, your performance, a bug in the app, or gives you instructions on how you should behave differently (e.g. 'Stop doing that', 'You need to be faster', 'This button is broken'): DO NOT ARGUE. DO NOT EXPLAIN YOURSELF. DO NOT APOLOGIZE. "
        "Simply say 'Feedback logged.' and IMMEDIATELY use the 'log_system_feedback' tool. This sends the issue directly to the developer agent who can actually fix your code. Do not try to solve systemic issues yourself.\n\n"
    )
    
    try:
        from promaia.brain.muninn import get_muninn
        muninn = await get_muninn()
        if muninn:
            # Token budget: Limit to 8 items, 200 chars each
            res = await muninn.activate(["Zack's active projects", "Zack's profile preferences", "recent priorities"], max_results=8)
            activations = res.get("activations", [])
            if activations:
                mem_text = "\n".join(f"- {a['content'][:200]}..." if len(a['content']) > 200 else f"- {a['content']}" for a in activations)
                system_ctx += f"\n[CURRENT KNOWLEDGE]\n{mem_text}\n"
                logger.info("Live API session populated with compressed MuninnDB context.")
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
                "These are background context only. NEVER ask about them unprompted. NEVER ask for verification of these items at the beginning of a call or before addressing his immediate problem. "
                "Use them exclusively to maintain conversational continuity if he brings them up — never to re-open closed topics.\n"
            )
            logger.info(f"Live API populated with {len(recent_sessions)} compressed session summaries.")
    except Exception as e:
        logger.warning(f"Failed to fetch recent sessions for context: {e}")

    # 11.5 Tool Definitions for Staging and Committing Memories
    memory_tools = {
        "function_declarations": [
            {
                "name": "save_conversation_memory",
                "description": "Stage a memory for significant decisions, facts, or commitments. Write the summary from the USER's perspective (e.g. 'Zack decided...' not 'I noted...'). Do NOT call for casual chat, greetings, or filler.",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "summary": { "type": "STRING", "description": "Concise summary of fact/decision" },
                        "memory_type": { "type": "STRING", "description": "profile_update, project_decision, action_item" }
                    },
                    "required": ["summary", "memory_type"]
                }
            },
            {
                "name": "commit_staged_memories",
                "description": "Call this ONLY AFTER you have read the staged memories aloud to the user and they have verbally confirmed they are correct and should be saved.",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "confirmation_note": { "type": "STRING", "description": "A brief note on what the user said to confirm (e.g. 'User said exactly')" }
                    },
                    "required": ["confirmation_note"]
                }
            },
            {
                "name": "create_calendar_event",
                "description": "Schedule a new event or reminder on Zack's calendar. ALWAYS verbally confirm details before calling.",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "summary": { "type": "STRING", "description": "Event title/summary" },
                        "description": { "type": "STRING", "description": "Event description (optional)" },
                        "start_time": { "type": "STRING", "description": "Start time (ISO 8601 format: 2026-03-10T14:00:00)" },
                        "end_time": { "type": "STRING", "description": "End time (ISO 8601 format: 2026-03-10T15:00:00)" }
                    },
                    "required": ["summary", "start_time", "end_time"]
                }
            },
            {
                "name": "send_email_draft",
                "description": "Create an email draft in the Promaia Dashboard based on user's request. ALWAYS verbally confirm before calling.",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "to": { "type": "STRING", "description": "Recipient email address" },
                        "subject": { "type": "STRING", "description": "Email subject" },
                        "body": { "type": "STRING", "description": "Email body text" }
                    },
                    "required": ["to", "subject", "body"]
                }
            },
            {
                "name": "switch_cognitive_mode",
                "description": "Switch your thinking style based on natural user cues. Call this when the user asks you to: think critically / play devil's advocate / poke holes / what could go wrong (-> critical mode); brainstorm / wild ideas / what else could we try (-> creative mode); just the facts / what do we actually know (-> facts mode); what's your gut say / forget the logic (-> instinct mode); what's the upside / make the case for it (-> optimist mode); step back / help me think through this / big picture (-> process mode). NEVER mention mode names or thinking styles to the user.",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "hat_color": { "type": "STRING", "description": "critical, creative, instinct, facts, optimist, or process" }
                    },
                    "required": ["hat_color"]
                }
            },
            {
                "name": "hang_up_call",
                "description": "End the current voice call and hang up the connection. Use this ONLY when Zack explicitly says 'hang up', 'goodbye', 'end call', etc. Say your goodbye FIRST, then call this tool."
            },
            {
                "name": "log_system_feedback",
                "description": "Log a bug report, behavior correction, or system feature request directly to the developer codebase. Call this IMMEDIATELY whenever Zack gives feedback on your performance, complains about the app, or suggests an improvement.",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "feedback": { "type": "STRING", "description": "The exact complaint, bug, or feedback Zack provided." }
                    },
                    "required": ["feedback"]
                }
            },
            {
                "name": "create_action",
                "description": "Create a new action item or reminder for Zack. Requires title, optional due date, and domain.",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "description": { "type": "STRING", "description": "Action item description/title" },
                        "due_date": { "type": "STRING", "description": "Due date (e.g. YYYY-MM-DD) or 'ASAP' (optional)" },
                        "domain": { "type": "STRING", "description": "Domain/project (e.g. 'heatpup', 'promaia', 'personal')" }
                    },
                    "required": ["description", "domain"]
                }
            },
            {
                "name": "recall_memory",
                "description": "Recall specific facts or context from MuninnDB based on a semantic search query.",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "query": { "type": "STRING", "description": "The concept or fact you are trying to remember." }
                    },
                    "required": ["query"]
                }
            }
        ]
    }

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
                                tool_responses = []
                                for ft in response.tool_call.function_calls:
                                    if ft.name == "save_conversation_memory":
                                        args = ft.args
                                        staged_memories.append({
                                            "content": args.get("summary"),
                                            "domain": args.get("memory_type", "user"),
                                            "confidence": 0.8
                                        })
                                        logger.info(f"Memory explicitly staged by Gemini: {args.get('summary')}")
                                        tool_responses.append(types.FunctionResponse(
                                            name=ft.name,
                                            id=ft.id,
                                            response={"result": "staged_successfully", "total_staged_count": len(staged_memories)}
                                        ))
                                    
                                    elif ft.name == "commit_staged_memories":
                                        if staged_memories:
                                            # Bump confidence because of verbal confirmation
                                            for m in staged_memories:
                                                m['confidence'] = min(1.0, m['confidence'] + 0.1)
                                            
                                            try:
                                                db = get_postgres_db()
                                                vector_mgr = VectorDBManager()
                                                # Write through unified pipeline
                                                for m in staged_memories:
                                                    await capture_memory(
                                                        db=db,
                                                        vector_mgr=vector_mgr,
                                                        content=m['content'],
                                                        session_id="voice-session",
                                                        domain_name=m.get('domain'),
                                                        source="voice",
                                                        confidence=m['confidence']
                                                    )
                                                logger.info(f"Successfully COMMITTED {len(staged_memories)} memories through pipeline after user confirmation.")
                                                staged_memories.clear()
                                                tool_responses.append(types.FunctionResponse(
                                                    name=ft.name,
                                                    id=ft.id,
                                                    response={"result": "committed_successfully"}
                                                ))
                                            except Exception as e:
                                                logger.error(f"Failed to commit batch through pipeline: {e}", exc_info=True)
                                                tool_responses.append(types.FunctionResponse(
                                                    name=ft.name,
                                                    id=ft.id,
                                                    response={"result": "error_committing"}
                                                ))
                                        else:
                                            tool_responses.append(types.FunctionResponse(
                                                name=ft.name,
                                                id=ft.id,
                                                response={"result": "no_staged_memories_found"}
                                            ))
                                        
                                    elif ft.name == "create_calendar_event":
                                        args = ft.args
                                        try:
                                            from promaia.gcal.google_calendar import GoogleCalendarManager
                                            mgr = GoogleCalendarManager()
                                            if mgr.authenticate():
                                                event_body = {
                                                    'summary': args.get('summary'),
                                                    'start': {'dateTime': args.get('start_time'), 'timeZone': 'America/Los_Angeles'}, # Local time or UTC based on 'start_time' string format
                                                    'end': {'dateTime': args.get('end_time'), 'timeZone': 'America/Los_Angeles'}
                                                }
                                                if args.get('description'):
                                                    event_body['description'] = args.get('description')
                                                
                                                # Need to adjust timeZone to UTC if the AI provides native UTC Z time. 
                                                # But if they don't, America/Los_Angeles helps (assuming user locale).
                                                # It's better to force the AI to provide the correct TZ in the prompt, or just pass it through.
                                                if 'Z' in str(args.get('start_time')):
                                                    event_body['start']['timeZone'] = 'UTC'
                                                    event_body['end']['timeZone'] = 'UTC'

                                                event = mgr.service.events().insert(
                                                    calendarId='primary',
                                                    body=event_body
                                                ).execute()
                                                
                                                logger.info(f"Successfully created calendar event: {args.get('summary')}")
                                                tool_responses.append(types.FunctionResponse(
                                                    name=ft.name,
                                                    id=ft.id,
                                                    response={"result": "event_created", "event_id": event.get('id'), "link": event.get('htmlLink')}
                                                ))
                                            else:
                                                tool_responses.append(types.FunctionResponse(
                                                    name=ft.name,
                                                    id=ft.id,
                                                    response={"result": "authentication_failed", "error": "Google Calendar authentication failed"}
                                                ))
                                        except Exception as e:
                                            logger.error(f"Failed to create calendar event: {e}", exc_info=True)
                                            tool_responses.append(types.FunctionResponse(
                                                name=ft.name,
                                                id=ft.id,
                                                response={"result": "error_creating_event", "error": str(e)}
                                            ))

                                    elif ft.name == "send_email_draft":
                                        args = ft.args
                                        try:
                                            from promaia.mail.email_send_helpers import EmailSendHelper
                                            helper = EmailSendHelper(workspace="zbrain")
                                            draft_id = helper.create_draft_from_info(
                                                recipient=args.get("to"),
                                                subject=args.get("subject"),
                                                message_body=args.get("body")
                                            )
                                            logger.info(f"Successfully created email draft to: {args.get('to')}")
                                            tool_responses.append(types.FunctionResponse(
                                                name=ft.name,
                                                id=ft.id,
                                                response={"result": "draft_created", "draft_id": draft_id}
                                            ))
                                        except Exception as e:
                                            logger.error(f"Failed to create email draft: {e}", exc_info=True)
                                            tool_responses.append(types.FunctionResponse(
                                                name=ft.name,
                                                id=ft.id,
                                                response={"result": "error_creating_draft", "error": str(e)}
                                            ))
                                            
                                    elif ft.name == "switch_cognitive_mode":
                                        args = ft.args
                                        color = args.get("hat_color", "").lower()
                                        modes = {
                                            "critical":  "CRITICAL INSTRUCTION: Shift to devil's advocate mode. Focus on risks, flaws, and potential failures. Be honest and direct — your job is to bulletproof the idea, not to encourage it.",
                                            "black":     "CRITICAL INSTRUCTION: Shift to devil's advocate mode. Focus on risks, flaws, and potential failures. Be honest and direct — your job is to bulletproof the idea, not to encourage it.",
                                            "creative":  "CRITICAL INSTRUCTION: Shift to brainstorm mode. Generate alternatives, new angles, and unexpected ideas. No criticism — everything is on the table.",
                                            "green":     "CRITICAL INSTRUCTION: Shift to brainstorm mode. Generate alternatives, new angles, and unexpected ideas. No criticism — everything is on the table.",
                                            "instinct":  "CRITICAL INSTRUCTION: Shift to gut-check mode. Set logic aside. Respond from intuition — how does this feel? What's the emotional undercurrent?",
                                            "red":       "CRITICAL INSTRUCTION: Shift to gut-check mode. Set logic aside. Respond from intuition — how does this feel? What's the emotional undercurrent?",
                                            "facts":     "CRITICAL INSTRUCTION: Shift to just-the-facts mode. Only discuss what is known and verifiable. Flag what is unknown. No opinions or speculation.",
                                            "white":     "CRITICAL INSTRUCTION: Shift to just-the-facts mode. Only discuss what is known and verifiable. Flag what is unknown. No opinions or speculation.",
                                            "optimist":  "CRITICAL INSTRUCTION: Shift to upside mode. Focus on the best-case outcome and the logical reasons this will work. Be genuinely enthusiastic without ignoring reality.",
                                            "yellow":    "CRITICAL INSTRUCTION: Shift to upside mode. Focus on the best-case outcome and the logical reasons this will work. Be genuinely enthusiastic without ignoring reality.",
                                            "process":   "CRITICAL INSTRUCTION: Shift to big-picture mode. Zoom out. Organize what has been covered, identify what's missing, and set a clear direction for what's next.",
                                            "blue":      "CRITICAL INSTRUCTION: Shift to big-picture mode. Zoom out. Organize what has been covered, identify what's missing, and set a clear direction for what's next.",
                                        }
                                        instruction = modes.get(color, "Return to your normal balanced mode.")
                                        logger.info(f"Switched to cognitive mode: {color}")
                                        tool_responses.append(types.FunctionResponse(
                                            name=ft.name,
                                            id=ft.id,
                                            response={"result": "mode_switched", "new_instructions": instruction}
                                        ))
                                        
                                    elif ft.name == "hang_up_call":
                                        logger.info(f"Agent decided to hang up the call.")
                                        tool_responses.append(types.FunctionResponse(
                                            name=ft.name,
                                            id=ft.id,
                                            response={"result": "hanging_up"}
                                        ))
                                        await websocket.send_json({
                                            "serverContent": {
                                                "control": "hang_up"
                                            }
                                        })
                                        
                                    elif ft.name == "log_system_feedback":
                                        args = ft.args
                                        feedback = args.get("feedback")
                                        logger.info(f"USER SUBMITTED SYSTEM FEEDBACK: {feedback}")
                                        
                                        try:
                                            db = get_postgres_db()
                                            vector_mgr = VectorDBManager()
                                            await capture_memory(
                                                db=db,
                                                vector_mgr=vector_mgr,
                                                content=f"[SYSTEM BUG/FEEDBACK]: {feedback}",
                                                session_id="voice-session-feedback",
                                                domain_name="system_feedback",
                                                source="voice",
                                                confidence=1.0
                                            )
                                            tool_responses.append(types.FunctionResponse(
                                                name=ft.name,
                                                id=ft.id,
                                                response={"result": "feedback_logged_to_devs"}
                                            ))
                                        except Exception as e:
                                            logger.error(f"Failed to log system feedback: {e}", exc_info=True)
                                            tool_responses.append(types.FunctionResponse(
                                                name=ft.name,
                                                id=ft.id,
                                                response={"result": "error_logging_feedback"}
                                            ))
                                            
                                    elif ft.name == "create_action":
                                        args = ft.args
                                        try:
                                            db = get_postgres_db()
                                            db.execute(
                                                """
                                                INSERT INTO brain.actions (description, due_date, domain, status, created_at)
                                                VALUES (%s, %s, %s, 'pending', NOW())
                                                """,
                                                (args.get("description"), args.get("due_date"), args.get("domain"))
                                            )
                                            logger.info(f"Successfully created action item: {args.get('description')}")
                                            tool_responses.append(types.FunctionResponse(
                                                name=ft.name,
                                                id=ft.id,
                                                response={"result": "action_created"}
                                            ))
                                        except Exception as e:
                                            logger.error(f"Failed to create action item: {e}", exc_info=True)
                                            tool_responses.append(types.FunctionResponse(
                                                name=ft.name,
                                                id=ft.id,
                                                response={"result": "error_creating_action", "error": str(e)}
                                            ))
                                            
                                    elif ft.name == "recall_memory":
                                        args = ft.args
                                        query = args.get("query")
                                        try:
                                            from promaia.brain.muninn import get_muninn
                                            muninn = await get_muninn()
                                            if muninn:
                                                res = await muninn.activate([query], max_results=3)
                                                activations = res.get("activations", [])
                                                if activations:
                                                    mem_text = "\n".join(f"- {a['content']}" for a in activations)
                                                    tool_responses.append(types.FunctionResponse(
                                                        name=ft.name,
                                                        id=ft.id,
                                                        response={"result": "memory_recalled", "memories": mem_text}
                                                    ))
                                                else:
                                                    tool_responses.append(types.FunctionResponse(
                                                        name=ft.name,
                                                        id=ft.id,
                                                        response={"result": "no_memories_found"}
                                                    ))
                                            else:
                                                tool_responses.append(types.FunctionResponse(
                                                    name=ft.name,
                                                    id=ft.id,
                                                    response={"result": "muninndb_offline"}
                                                ))
                                        except Exception as e:
                                            logger.error(f"Failed to recall memory: {e}", exc_info=True)
                                            tool_responses.append(types.FunctionResponse(
                                                name=ft.name,
                                                id=ft.id,
                                                response={"result": "error_recalling_memory"}
                                            ))
                                        
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

