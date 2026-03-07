"""
Voice note handler for Telegram bot.

Downloads voice notes, transcribes via Deepgram Nova-3, shows the
transcription to the user, and auto-captures it to the brain.

Degrades gracefully when DEEPGRAM_API_KEY is not set.
"""
import logging
import os
from io import BytesIO

from aiogram import Router
from aiogram.types import Message

from promaia.telegram.brain_ops import capture_memory
from promaia.telegram.formatting import send_long_message

logger = logging.getLogger(__name__)

router = Router()

# 10 MB limit for voice notes (~10 minutes of Telegram OGG Opus)
MAX_VOICE_SIZE = 10 * 1024 * 1024


@router.message(lambda msg: msg.voice is not None)
async def handle_voice(message: Message) -> None:
    """Download, transcribe, and auto-capture a voice note."""
    # Check for Deepgram API key
    api_key = os.environ.get("DEEPGRAM_API_KEY")
    if not api_key:
        await message.answer(
            "Voice transcription unavailable -- DEEPGRAM_API_KEY not configured."
        )
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

    # Transcribe via Deepgram Nova-3
    try:
        from deepgram import AsyncDeepgramClient

        client = AsyncDeepgramClient(api_key=api_key)
        response = await client.listen.v1.media.transcribe_file(
            request=audio_bytes,
            model="nova-3",
            smart_format=True,
        )
        transcript = (
            response.results.channels[0].alternatives[0].transcript
        )
    except Exception as e:
        logger.error(f"Deepgram transcription failed: {e}", exc_info=True)
        await message.answer("Transcription failed. Try again?")
        return

    if not transcript or not transcript.strip():
        await message.answer("Could not transcribe the voice note.")
        return

    # Show the transcription
    await send_long_message(message, f"Heard: {transcript}")

    # Auto-capture to brain
    result = await capture_memory(transcript)
    await message.answer(result)
