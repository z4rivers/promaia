import os
import asyncio
import logging
from google import genai
from google.genai import types

from promaia.ai.models import GOOGLE_MODELS
from promaia.telegram.conversation import (
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
from typing import Optional, List, Dict, Any
from promaia.storage.db_factory import get_db
from promaia.storage.vector_db import VectorDBManager
from promaia.brain.core.memory_pipeline import capture_memory
from promaia.brain.tool_definitions import output_tools
from promaia.brain.tool_handlers import handle_tool_call
from promaia.brain.context_assembly import assemble_brain_context, get_personality_prompt

logger = logging.getLogger(__name__)

WEB_CHAT_ID = int(os.environ.get("TELEGRAM_WHITELIST", "6269250506"))


# Web personality override REMOVED — consolidated into context_assembly.get_personality_prompt()
# The one unique directive (SILENT TOOLS) was migrated to the core personality.

async def _check_escalation(response_text: str, user_message: str) -> Optional[str]:
    """
    If Maia is unsure or lacks context, perform a targeted search and return enriched context.
    Phase 2 Search Escalation logic.
    """
    low_confidence_signals = ["not sure", "don't have context", "don't recall", "don't have info", "i don't know"]
    if any(sig in response_text.lower() for sig in low_confidence_signals):
        logger.info("Low confidence detected, escalating search...")
        from promaia.brain.muninn import get_muninn
        muninn = await get_muninn()
        if muninn:
            # Targeted search based on the user's message
            res = await muninn.activate([user_message], max_results=5)
            activations = res.get("activations", [])
            if activations:
                enriched = "\n\n### Additional Found Context\n"
                enriched += "\n".join(f"- {a['content']}" for a in activations)
                return enriched
    return None

async def generate_maia_response(user_message: str, status_callback=None, image_paths=None, audio_paths=None, document_paths=None, websocket=None) -> str:
    """
    Generate a conversational response for the web dashboard using Gemini.
    Three-stage pipeline: GATHER -> GENERATE -> PERSIST.
    """
    chat_id = WEB_CHAT_ID
    db = get_db()
    
    # 1. GATHER
    if status_callback:
        await status_callback("GATHERING brain context...")
        
    session_id = await get_or_create_session(chat_id, gap_minutes=SESSION_GAP_MINUTES)
    
    # NEW: Fetch active domain focus for this session
    session_row = db.fetch_one(
        "SELECT active_domain FROM conversation_sessions WHERE session_id = %s",
        (session_id,)
    )
    active_domain = session_row['active_domain'] if session_row else None
    
    known_projects = _get_known_projects()
    impact = score_impact(user_message, known_projects)

    msg_id = await save_conversation_message(
        chat_id, session_id, "user", user_message, impact_score=impact
    )

    # Auto-promote if high-impact
    if impact >= IMPACT_PROMOTION_THRESHOLD:
        try:
            await promote_message_to_memory(msg_id, user_message)
        except Exception as e:
            logger.warning(f"Failed to promote message {msg_id} to memory: {e}")

    # Unified context assembly (Phase 2 Focus-Aware)
    context = await assemble_brain_context(user_message, chat_id=chat_id, active_domain=active_domain)

    # 2. GENERATE
    if status_callback:
        await status_callback("GENERATING response...")

    user_parts = [types.Part.from_text(text=f"{context}\n\nUser: {user_message}")]
    
    # [Asset attachment logic remains same...]
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

    history = [types.Content(role="user", parts=user_parts)]

    try:
        client = _get_genai_client()
        gemini_tools = [{"function_declarations": output_tools["function_declarations"]}]
        
        # Use dynamic personality prompt (Phase 3)
        current_prompt = get_personality_prompt(active_domain)

        config = types.GenerateContentConfig(
            system_instruction=current_prompt,
            temperature=1.0,  # Gemini 3 requires 1.0 — lower causes looping/degradation
            tools=gemini_tools
        )
        
        max_turns = 4 # Reduced turns as bridge pre-gathers context
        response_text = None
        failed_tools = set()

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
                history.append(response.candidates[0].content)
                tool_responses = []
                for ft in response.function_calls:
                    if ft.name in failed_tools:
                        tool_responses.append(types.FunctionResponse(
                            name=ft.name, id=ft.id,
                            response={"result": "skipped", "reason": "This tool already failed."}
                        ))
                        continue

                    if status_callback:
                        await status_callback(f"Executing {ft.name}...")

                    # Staged memories table is now persistent, so we don't need to pass a list
                    func_res = await handle_tool_call(ft, websocket, None, session_id=session_id)
                    tool_responses.append(func_res)

                    if isinstance(func_res.response, dict):
                        if func_res.response.get("result") == "error":
                            failed_tools.add(ft.name)

                history.append(
                    types.Content(
                        role="user",
                        parts=[types.Part.from_function_response(name=tr.name, response=tr.response) for tr in tool_responses]
                    )
                )
                continue

            response_text = response.text if response and response.text else None
            break
        else:
            # All turns consumed by tool calls — force a text response
            logger.warning(f"Tool loop exhausted {max_turns} turns, forcing text response")
            no_tools_config = types.GenerateContentConfig(
                system_instruction=get_personality_prompt(active_domain) + "\n\nYou have used all your tools. Respond directly now.",
                temperature=1.0,  # Gemini 3 requires 1.0
                tools=[],
                tool_config=types.ToolConfig(
                    function_calling_config=types.FunctionCallingConfig(mode="NONE")
                ),
            )
            final_response = await asyncio.wait_for(
                client.aio.models.generate_content(
                    model=GOOGLE_MODELS["flash"],
                    contents=history,
                    config=no_tools_config,
                ),
                timeout=30.0,
            )
            response_text = final_response.text if final_response and final_response.text else None
        
        # SEARCH ESCALATION
        if response_text:
            enriched_ctx = await _check_escalation(response_text, user_message)
            if enriched_ctx:
                if status_callback:
                    await status_callback("ENRICHING context...")
                
                # Re-call Gemini with enriched context
                history.append(types.Content(role="model", parts=[types.Part.from_text(text=response_text)]))
                history.append(types.Content(role="user", parts=[types.Part.from_text(text=f"{enriched_ctx}\n\nBased on this new info, please refine your response.")]))
                
                final_res = await client.aio.models.generate_content(
                    model=GOOGLE_MODELS["flash"],
                    contents=history,
                    config=config
                )
                if final_res:
                    _log_cost(final_res, "maia-web-bridge-escalation")
                    response_text = final_res.text

    except Exception as e:
        logger.error(f"Maia Bridge GENERATE failed: {e}", exc_info=True)
        response_text = "I'm having trouble thinking right now. Try again?"

    # 3. PERSIST
    if not response_text:
        response_text = "I'm having trouble thinking right now. Try again?"

    try:
        # Score the response itself for impact (Phase 2 requirement)
        res_impact = score_impact(response_text, known_projects)
        res_id = await save_conversation_message(
            chat_id, session_id, "assistant", response_text, impact_score=res_impact
        )
        
        # Auto-promote assistant response if high-impact
        if res_impact >= IMPACT_PROMOTION_THRESHOLD:
            try:
                # Source as 'assistant' to allow retrieval penalty in context assembly
                from promaia.brain.core.memory_pipeline import capture_memory
                await capture_memory(
                    db=get_db(),
                    vector_mgr=VectorDBManager(),
                    content=response_text,
                    session_id=f"assistant-{res_id}",
                    source="assistant",
                    confidence=0.6 # Lower confidence for machine-generated
                )
            except Exception as e:
                logger.warning(f"Assistant promotion failed: {e}")
                
    except Exception as e:
        logger.warning(f"Failed to persist response: {e}")

    if status_callback:
        await status_callback("Idle")

    return response_text
