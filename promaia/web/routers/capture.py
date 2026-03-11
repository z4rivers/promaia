"""
API endpoints for photo capture from the PWA.
"""
import logging
import os

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from promaia.ai.models import GOOGLE_MODELS
from promaia.telegram.brain_ops import capture_memory

logger = logging.getLogger(__name__)

router = APIRouter()

MAX_PHOTO_SIZE = 20 * 1024 * 1024

@router.post("")
async def receive_capture(
    photo: UploadFile = File(...),
    caption: str = Form(None)
):
    """Receive a photo, analyze via Gemini Vision, and save to brain."""
    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise HTTPException(status_code=503, detail="GOOGLE_API_KEY not configured.")

    image_bytes = await photo.read()
    if len(image_bytes) > MAX_PHOTO_SIZE:
        raise HTTPException(status_code=413, detail="Photo is too large to process.")

    # Analyze via Gemini
    try:
        from google import genai
        from google.genai import types

        prompt = "Describe this image in detail. Be observant and specific. If it's a document, summarize the key points."
        if caption:
            prompt += f"\n\nContext from user: {caption}"

        client = genai.Client(api_key=api_key)
        response = await client.aio.models.generate_content(
            model=GOOGLE_MODELS["flash"],
            contents=[
                types.Content(parts=[
                    types.Part.from_bytes(data=image_bytes, mime_type=photo.content_type or "image/jpeg"),
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
                _log_cost(response, "pwa-vision")
            except Exception:
                pass
    except Exception as e:
        logger.error(f"Gemini vision payload failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Image analysis failed.")

    if not description:
        raise HTTPException(status_code=500, detail="Could not analyze the image.")

    # Save to memory
    memory_content = f"User captured an image via web interface:\n{description}"
    if caption:
        memory_content = f"User captured an image via web interface with caption '{caption}':\n{description}"
        
    try:
        await capture_memory(memory_content, domain="vision")
        return {"status": "ok", "description": description}
    except Exception as e:
        logger.error(f"Memory capture failed for PWA photo: {e}", exc_info=True)
        return JSONResponse(status_code=207, content={"status": "partial", "description": description, "message": "Analyzed but failed to save memory."})
