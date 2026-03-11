"""
Photo handler for Telegram bot.

Downloads photos, describes via Gemini Vision, and captures to memory.
"""
import logging
import os
from io import BytesIO

from aiogram import F, Router
from aiogram.types import Message

from promaia.ai.models import GOOGLE_MODELS
from promaia.telegram.brain_ops import capture_memory

logger = logging.getLogger(__name__)

router = Router()

# Maximum image size ~20MB (Telegram's limit for get_file)
MAX_PHOTO_SIZE = 20 * 1024 * 1024

@router.message(F.photo)
async def handle_photo(message: Message) -> None:
    """Download, describe via Gemini Vision, and save to brain."""
    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        await message.answer("Vision unavailable -- GOOGLE_API_KEY not configured.")
        return

    # Telegram provides various sizes. Get the largest one.
    photo = message.photo[-1]

    if photo.file_size and photo.file_size > MAX_PHOTO_SIZE:
        await message.answer("Photo is too large to process.")
        return

    # Show "uploading photo" action
    await message.bot.send_chat_action(message.chat.id, "upload_photo")

    try:
        bot = message.bot
        file = await bot.get_file(photo.file_id)
        buffer = BytesIO()
        await bot.download_file(file.file_path, buffer)
        image_bytes = buffer.getvalue()
    except Exception as e:
        logger.error(f"Photo download failed: {e}", exc_info=True)
        await message.answer("Failed to download the photo. Try again?")
        return

    # Analyze via Gemini
    try:
        from google import genai
        from google.genai import types

        prompt = "Describe this image in detail. Be observant and specific. If it's a document, summarize the key points."
        if message.caption:
            prompt += f"\n\nContext from user: {message.caption}"

        client = genai.Client(api_key=api_key)
        response = await client.aio.models.generate_content(
            model=GOOGLE_MODELS["flash"],
            contents=[
                types.Content(parts=[
                    types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg"),
                    types.Part(text=prompt),
                ])
            ],
            config=types.GenerateContentConfig(temperature=0.4),
        )
        description = ""
        if response.candidates and response.candidates[0].content.parts:
            description = response.text.strip()
            
            # Log cost
            try:
                from promaia.telegram.conversation import _log_cost
                _log_cost(response, "telegram-vision")
            except Exception:
                pass
    except Exception as e:
        logger.error(f"Gemini vision failed: {e}", exc_info=True)
        await message.answer("Image analysis failed. Try again?")
        return

    if not description:
        await message.answer("I couldn't analyze the image.")
        return

    # Save to memory
    await message.bot.send_chat_action(message.chat.id, "typing")
    
    memory_content = f"User shared an image:\n{description}"
    if message.caption:
        memory_content = f"User shared an image with caption '{message.caption}':\n{description}"
        
    try:
        await capture_memory(memory_content, domain="vision")
        await message.answer(f"Got it. I saved this description to my memory:\n\n{description}")
    except Exception as e:
        logger.error(f"Memory capture failed for photo: {e}", exc_info=True)
        await message.answer(f"I analyzed the image, but couldn't save it to memory:\n\n{description}")
