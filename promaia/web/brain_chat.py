"""
Thin adapter: web endpoints -> conversation engine.
Web sessions use the whitelisted Telegram chat_id so all
conversations (web + Telegram) share context.
"""
import os
import logging
from promaia.telegram.conversation import generate_response, reset_synthesis_timer

logger = logging.getLogger(__name__)

WEB_CHAT_ID = int(os.environ.get("TELEGRAM_WHITELIST", "6269250506"))


async def chat(message: str) -> str:
    """Send a message to the brain and get a response."""
    response = await generate_response(WEB_CHAT_ID, message)
    await reset_synthesis_timer(WEB_CHAT_ID)
    return response


async def transcribe_audio(audio_bytes: bytes, mime_type: str = "audio/webm") -> str:
    """Transcribe audio bytes via Gemini multimodal (handles noise server-side)."""
    from google import genai
    from google.genai import types
    from promaia.ai.models import GOOGLE_MODELS

    client = genai.Client(api_key=os.environ.get("GOOGLE_API_KEY"))
    response = await client.aio.models.generate_content(
        model=GOOGLE_MODELS["flash"],
        contents=[
            types.Content(parts=[
                types.Part.from_bytes(data=audio_bytes, mime_type=mime_type),
                types.Part(text=(
                    "Transcribe this voice note exactly. The audio may contain "
                    "background road noise, car sounds, or navigation prompts. "
                    "Focus on the primary speaker's voice and ignore background sounds. "
                    "Return only the transcription, no commentary. "
                    "If a word is inaudible due to noise, mark it as [inaudible]."
                )),
            ])
        ],
        config=types.GenerateContentConfig(temperature=0.0),
    )
    if response.candidates and response.candidates[0].content.parts:
        return response.text.strip()
    return ""
