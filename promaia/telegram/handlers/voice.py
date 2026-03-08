"""
Voice note handler for Telegram bot.

Downloads voice notes, transcribes via Gemini, shows the
transcription to the user, and generates a conversational response.
"""
import logging
import os
from io import BytesIO

from aiogram import Router
from aiogram.types import Message

from promaia.ai.models import GOOGLE_MODELS
from promaia.telegram.conversation import generate_response, reset_synthesis_timer
from promaia.telegram.formatting import send_long_message

logger = logging.getLogger(__name__)

router = Router()

# 10 MB limit for voice notes (~10 minutes of Telegram OGG Opus)
MAX_VOICE_SIZE = 10 * 1024 * 1024


@router.message(lambda msg: msg.voice is not None)
async def handle_voice(message: Message) -> None:
    """Download, transcribe via Gemini, and respond conversationally."""
    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        await message.answer("Voice transcription unavailable -- GOOGLE_API_KEY not configured.")
        return

    # Check file size
    if message.voice.file_size and message.voice.file_size > MAX_VOICE_SIZE:
        await message.answer("Voice note too large (max ~10 minutes).")
        return

    # Download the voice file into memory
    try:
        bot = message.bot
        file = await bot.get_file(message.voice.file_id)
        buffer = BytesIO()
        await bot.download_file(file.file_path, buffer)
        audio_bytes = buffer.getvalue()
    except Exception as e:
        logger.error(f"Voice download failed: {e}", exc_info=True)
        await message.answer("Failed to download voice note. Try again?")
        return

    # Transcribe via Gemini
    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=api_key)
        response = await client.aio.models.generate_content(
            model=GOOGLE_MODELS["flash"],
            contents=[
                types.Content(parts=[
                    types.Part.from_bytes(data=audio_bytes, mime_type="audio/ogg"),
                    types.Part(text="Transcribe this voice note exactly. Return only the transcription, no commentary."),
                ])
            ],
            config=types.GenerateContentConfig(temperature=0.0),
        )
        transcript = ""
        if response.candidates and response.candidates[0].content.parts:
            transcript = response.text.strip()
    except Exception as e:
        logger.error(f"Gemini transcription failed: {e}", exc_info=True)
        await message.answer("Transcription failed. Try again?")
        return

    if not transcript:
        await message.answer("Could not transcribe the voice note.")
        return

    # Show the transcription
    await send_long_message(message, f"Heard: {transcript}")

    # Show typing indicator while Gemini thinks
    await message.bot.send_chat_action(message.chat.id, "typing")

    # Generate conversational response based on the transcription
    response = await generate_response(message.chat.id, transcript)

    # Reset synthesis timer
    await reset_synthesis_timer(message.chat.id)

    # Send response
    await send_long_message(message, response)
