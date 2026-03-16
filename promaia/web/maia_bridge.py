import os
import asyncio
import logging
from google import genai
from google.genai import types

from promaia.ai.models import GOOGLE_MODELS
from promaia.telegram.conversation import (
    _assemble_context,
    _get_genai_client,
    get_or_create_session,
    score_impact,
    save_conversation_message,
    promote_message_to_memory,
    SESSION_GAP_MINUTES,
    IMPACT_PROMOTION_THRESHOLD,
    _get_known_projects,
    _log_cost
)
from promaia.brain.tool_definitions import memory_tools
from promaia.brain.tool_handlers import handle_tool_call

logger = logging.getLogger(__name__)

WEB_CHAT_ID = int(os.environ.get("TELEGRAM_WHITELIST", "6269250506"))

PERSONALITY_SYSTEM_PROMPT = (
    "You are Promaia, Zack's second brain. You are a conversational mirror and "
    "sounding board on the web dashboard.\n\n"
    "CORE DIRECTIVE:\n"
    "Respond to the specific thought he just shared. Connect this "
    "moment to past moments when relevant. If something doesn't add up or could be "
    "helpful, point it out or ask about it.\n\n"
    "HOW TO USE CONTEXT:\n"
    "You have awareness of Zack's current state (projects, memories, profile). Use this "
    "ONLY to understand what he is talking about. Offer insight over status.\n\n"
    "VOICE: Short sentences. Direct. Match his energy: brief when brief, detailed when "
    "exploring."
)

async def generate_maia_response(user_message: str, status_callback=None, image_paths=None, audio_paths=None, document_paths=None) -> str:
    """
    Generate a conversational response for the web dashboard using Gemini.
    status_callback is an async function that takes a string to update the UI "Active Session" feed.
    """
    chat_id = WEB_CHAT_ID
    
    if status_callback:
        await status_callback("Assembling brain context...")
        
    session_id = await get_or_create_session(chat_id, gap_minutes=SESSION_GAP_MINUTES)
    known_projects = _get_known_projects()
    impact = score_impact(user_message, known_projects)

    msg_id = await save_conversation_message(
        chat_id, session_id, "user", user_message, impact_score=impact
    )

    if impact >= IMPACT_PROMOTION_THRESHOLD:
        try:
            await promote_message_to_memory(msg_id, user_message)
        except Exception as e:
            logger.warning(f"Failed to promote message {msg_id} to memory: {e}")

    context = await _assemble_context(chat_id, user_message)

    if status_callback:
        await status_callback("Consulting LLM models...")

    user_parts = [types.Part.from_text(text=f"{context}\n\nUser: {user_message}")]
    
    if image_paths:
        for img_path in image_paths:
            try:
                with open(img_path, 'rb') as f:
                    image_bytes = f.read()
                lower = img_path.lower()
                mime = 'image/png' if lower.endswith('.png') else 'image/webp' if lower.endswith('.webp') else 'image/jpeg'
                user_parts.append(types.Part.from_bytes(data=image_bytes, mime_type=mime))
            except Exception as e:
                logger.error(f"Failed to attach image {img_path} to Maia context: {e}")

    if audio_paths:
        for aud_path in audio_paths:
            try:
                with open(aud_path, 'rb') as f:
                    audio_bytes = f.read()
                lower = aud_path.lower()
                mime = 'audio/wav' if lower.endswith('.wav') else 'audio/ogg' if lower.endswith('.ogg') else 'audio/mpeg'
                user_parts.append(types.Part.from_bytes(data=audio_bytes, mime_type=mime))
            except Exception as e:
                logger.error(f"Failed to attach audio {aud_path} to Maia context: {e}")
                
    if document_paths:
        for doc_path in document_paths:
            try:
                with open(doc_path, 'rb') as f:
                    doc_bytes = f.read()
                lower = doc_path.lower()
                if lower.endswith('.pdf'):
                    mime = 'application/pdf'
                elif lower.endswith('.csv'):
                    mime = 'text/csv'
                elif lower.endswith('.md'):
                    mime = 'text/markdown'
                else:
                    mime = 'text/plain'
                user_parts.append(types.Part.from_bytes(data=doc_bytes, mime_type=mime))
            except Exception as e:
                logger.error(f"Failed to attach document {doc_path} to Maia context: {e}")

    # We will maintain a conversation history for tool loops
    history = [
        types.Content(role="user", parts=user_parts)
    ]

    try:
        client = _get_genai_client()
        
        # We need to map the dict schema to types.Tool objects for Gemini 2.0 API
        gemini_tools = [{"function_declarations": memory_tools["function_declarations"]}]
        
        config = types.GenerateContentConfig(
            system_instruction=PERSONALITY_SYSTEM_PROMPT,
            temperature=0.7,
            tools=gemini_tools
        )
        
        max_turns = 5
        staged_memories = [] # Tool state
        response_text = None  # Ensure defined even if loop exhausts all turns on tool calls

        for turn in range(max_turns):
            response = await asyncio.wait_for(
                client.aio.models.generate_content(
                    model=GOOGLE_MODELS["flash"],
                    contents=history,
                    config=config,
                ),
                timeout=30.0,
            )
            
            if response:
                _log_cost(response, "maia-web-bridge")
                
            if response.function_calls:
                # Add the model's tool calls to History so Gemini knows what it asked for
                history.append(response.candidates[0].content)
                
                tool_responses = []
                for ft in response.function_calls:
                    if status_callback:
                        await status_callback(f"Executing tool {ft.name}...")
                        
                    func_res = await handle_tool_call(ft, None, staged_memories)
                    tool_responses.append(func_res)
                    
                # Add function responses back to history
                history.append(
                    types.Content(
                        role="user", # The tool response is sent as user role in this SDK version or function role
                        parts=[types.Part.from_function_response(name=tr.name, response=tr.response) for tr in tool_responses]
                    )
                )
                continue # Loop again to let Gemini see the tool result
                
            # If no function calls, we have our final text!
            response_text = response.text if response and response.text else None
            break
            
    except asyncio.TimeoutError:
        logger.error("Gemini call timed out after 30 seconds")
        response_text = None
    except Exception as e:
        logger.error(f"Gemini call failed: {e}", exc_info=True)
        response_text = None

    if not response_text:
        response_text = "I'm having trouble thinking right now. Try again?"

    try:
        await save_conversation_message(
            chat_id, session_id, "assistant", response_text, impact_score=0.0
        )
    except Exception as e:
        logger.warning(f"Failed to save assistant response: {e}")

    if status_callback:
        await status_callback("Idle")

    return response_text
