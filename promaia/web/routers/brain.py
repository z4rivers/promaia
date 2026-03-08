"""
Brain chat + voice + TTS API endpoints for the web interface.

POST /api/brain/chat     — text message in, response out
POST /api/brain/voice    — audio blob in, transcription + response out
POST /api/brain/tts      — text in, WAV audio out (Gemini native TTS)
"""
import base64
import logging
import os
from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import Response
from pydantic import BaseModel

from promaia.web.brain_chat import chat, transcribe_audio

logger = logging.getLogger(__name__)
router = APIRouter()


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
            model="gemini-2.5-flash",
            contents=f"Read this aloud naturally: {req.message}",
            config=types.GenerateContentConfig(
                response_modalities=["AUDIO"],
                speech_config=types.SpeechConfig(
                    voice_config=types.VoiceConfig(
                        prebuilt_voice_config=types.PrebuiltVoiceConfig(
                            voice_name="Kore"
                        )
                    )
                ),
            ),
        )

        # Extract audio data from response
        if (response.candidates
                and response.candidates[0].content
                and response.candidates[0].content.parts):
            part = response.candidates[0].content.parts[0]
            if hasattr(part, 'inline_data') and part.inline_data:
                audio_data = part.inline_data.data
                mime_type = part.inline_data.mime_type or "audio/wav"

                # If data is base64 encoded string, decode it
                if isinstance(audio_data, str):
                    audio_data = base64.b64decode(audio_data)

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
