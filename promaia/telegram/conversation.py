"""
Conversation engine for Telegram bot.

Owns context assembly, Gemini calling, impact scoring, session management,
and session synthesis. Delegates conversation CRUD to brain_ops.py.
"""
import asyncio
import logging
import os
import re
import time
from typing import Optional

import numpy as np
import psycopg2.extras
from google import genai
from google.genai import types
from pgvector.psycopg2 import register_vector

from promaia.storage.postgres_db import get_postgres_db
from promaia.storage.vector_db import VectorDBManager
from promaia.telegram.brain_ops import (
    capture_memory,
    get_conversation_history,
    get_or_create_session,
    get_session_messages,
    promote_message_to_memory,
    save_conversation_message,
    update_session_synthesized,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SESSION_GAP_MINUTES = 30
SYNTHESIS_SILENCE_SECONDS = 240  # 4 minutes
SYNTHESIS_MESSAGE_THRESHOLD = 8
IMPACT_PROMOTION_THRESHOLD = 0.5

# Condensed from PERSONALITY-MANIFEST.md per D4.
# Short, direct, substance-first. Under 300 words.
PERSONALITY_SYSTEM_PROMPT = (
    "You are Promaia, Zack's second brain. You are a conversational mirror and "
    "sounding board on Telegram.\n\n"
    "CORE DIRECTIVE:\n"
    "Zack has other tools for project management. He uses you for clarity, reflection, "
    "and connecting dots. Respond to the specific thought he just shared. Connect this "
    "moment to past moments when relevant. If something doesn't add up or could be "
    "helpful, point it out or ask about it.\n\n"
    "HOW TO USE CONTEXT:\n"
    "You have awareness of Zack's current state (projects, memories, profile). Use this "
    "ONLY to understand what he is talking about. Offer insight over status. Instead of "
    "'You have 3 tasks due', try 'Sounds like Heatpup keeps pulling at you -- is that "
    "worth revisiting?' If he asks for planning or prioritization help, give it. "
    "Otherwise, stay in reflection mode.\n\n"
    "SUBSTANCE-FIRST: Open every response with something useful -- a reaction, a key "
    "question, a connection. Warmth comes through in HOW you engage, not in padding.\n\n"
    "VOICE: Short sentences. Direct. Match his energy: brief when brief, detailed when "
    "exploring. Humor sharp and committed. Validate before solving -- receive hard "
    "things before trying to fix them."
)

# ---------------------------------------------------------------------------
# Lazy singletons
# ---------------------------------------------------------------------------

_genai_client = None
_db = None
_vector_manager = None

# Simple cache for known projects
_project_cache: Optional[list[str]] = None
_project_cache_time: float = 0.0
_PROJECT_CACHE_TTL = 300  # 5 minutes


def _get_genai_client():
    global _genai_client
    if _genai_client is None:
        _genai_client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))
    return _genai_client


def _get_db():
    global _db
    if _db is None:
        _db = get_postgres_db()
    return _db


def _get_vector_mgr():
    global _vector_manager
    if _vector_manager is None:
        _vector_manager = VectorDBManager()
    return _vector_manager


# ---------------------------------------------------------------------------
# Cost tracking (Gemini 3 Flash pricing per Phase 6)
# ---------------------------------------------------------------------------

# Gemini 3 Flash: $0.15/1M input, $0.60/1M output
_FLASH_INPUT_PRICE_PER_M = 0.15
_FLASH_OUTPUT_PRICE_PER_M = 0.60


def _log_cost(response, agent_name: str) -> None:
    """Log Gemini API cost to brain.agent_costs. Never fails."""
    try:
        usage = getattr(response, "usage_metadata", None)
        if usage is None:
            return
        input_tokens = getattr(usage, "prompt_token_count", 0) or 0
        output_tokens = getattr(usage, "candidates_token_count", 0) or 0
        cached_tokens = getattr(usage, "cached_content_token_count", 0) or 0

        cost = (
            input_tokens * _FLASH_INPUT_PRICE_PER_M / 1_000_000
            + output_tokens * _FLASH_OUTPUT_PRICE_PER_M / 1_000_000
        )

        db = _get_db()
        db.execute(
            """
            INSERT INTO brain.agent_costs
                (agent_name, model_id, task_type, input_tokens, output_tokens,
                 cached_tokens, thinking_tokens, cost_usd)
            VALUES (%s, %s, %s, %s, %s, %s, 0, %s)
            """,
            (agent_name, "gemini-3-flash-preview", "conversation",
             input_tokens, output_tokens, cached_tokens, cost),
        )
        logger.debug(
            f"Cost logged: {agent_name} in={input_tokens} out={output_tokens} "
            f"cost=${cost:.6f}"
        )
    except Exception as e:
        logger.warning(f"Cost logging failed (non-fatal): {e}")


# ---------------------------------------------------------------------------
# Impact scoring (heuristic, no Gemini -- per D2)
# ---------------------------------------------------------------------------

_ACTION_PATTERNS = re.compile(
    r"\b(i need to|i decided|i'm going to|don't forget|we should|"
    r"i have to|i want to|i'll|make sure|remind me|deadline|"
    r"by end of|i'm going|let's)\b",
    re.IGNORECASE,
)

_EMOTIONAL_PATTERNS = re.compile(
    r"\b(frustrated|excited|worried|thrilled|angry|amazed|"
    r"stressed|relieved|proud|disappointed|love|hate|"
    r"anxious|overwhelmed|grateful|furious|ecstatic)\b",
    re.IGNORECASE,
)

_ENTITY_PATTERNS = re.compile(
    r"\b(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday|"
    r"January|February|March|April|May|June|July|August|September|"
    r"October|November|December|"
    r"\d{1,2}/\d{1,2}|\$\d+|tomorrow|next week|by end of|"
    r"yesterday|tonight|this morning|last night|next month)\b",
    re.IGNORECASE,
)


def score_impact(text: str, known_projects: list[str] = None) -> float:
    """Score message impact for memory promotion. Returns 0.0-1.0.

    Five heuristic dimensions, no Gemini calls. Requires at least 2 signals
    to avoid false positives (per Research pitfall 5).
    """
    score = 0.0
    signals = 0

    # 1. Length and specificity
    word_count = len(text.split())
    if word_count > 20:
        score += 0.15
        signals += 1
    if word_count > 50:
        score += 0.10

    # 2. Action language
    action_hits = len(_ACTION_PATTERNS.findall(text))
    if action_hits > 0:
        score += min(0.25, action_hits * 0.12)
        signals += 1

    # 3. Emotional markers
    emotion_hits = len(_EMOTIONAL_PATTERNS.findall(text))
    if emotion_hits > 0:
        score += min(0.20, emotion_hits * 0.10)
        signals += 1

    # 4. Entity detection (dates, money, days of week)
    entity_hits = len(_ENTITY_PATTERNS.findall(text))
    if entity_hits > 0:
        score += min(0.20, entity_hits * 0.10)
        signals += 1

    # 5. Project name mentions
    if known_projects:
        for proj in known_projects:
            if proj.lower() in text.lower():
                score += 0.10
                signals += 1
                break

    # Require at least 2 signals to avoid false positives
    if signals < 2 and score < 0.3:
        score *= 0.5

    return min(score, 1.0)


# ---------------------------------------------------------------------------
# Known projects helper (cached)
# ---------------------------------------------------------------------------

def _get_known_projects() -> list[str]:
    """Return list of project names from brain.domains. Cached for 5 minutes."""
    global _project_cache, _project_cache_time

    now = time.time()
    if _project_cache is not None and (now - _project_cache_time) < _PROJECT_CACHE_TTL:
        return _project_cache

    try:
        db = _get_db()
        rows = db.fetch_all(
            "SELECT name FROM brain.domains WHERE is_project = true"
        )
        _project_cache = [r["name"] for r in rows] if rows else []
    except Exception as e:
        logger.warning(f"Failed to load known projects: {e}")
        _project_cache = []

    _project_cache_time = now
    return _project_cache


# ---------------------------------------------------------------------------
# Context assembly (maximalist per D1)
# ---------------------------------------------------------------------------

async def _assemble_context(chat_id: int, user_message: str) -> str:
    """Build maximalist context string from brain sources.

    Order (most important first for Gemini attention):
    1. User profile (top 15 by confidence)
    2. Conversation history (last 10 messages)
    3. Relevant memories (semantic search, top 5)
    4. Active projects
    5. Pending actions
    """

    def _sync_fetch():
        db = _get_db()
        parts = []

        # 1. User profile
        try:
            profile_rows = db.fetch_all(
                """
                SELECT category, field, value
                FROM brain.profile
                ORDER BY confidence DESC
                LIMIT 15
                """
            )
            if profile_rows:
                profile_text = "\n".join(
                    f"- {r['field']}: {r['value']}" for r in profile_rows
                )
                parts.append(f"## About Zack\n{profile_text}")
        except Exception as e:
            logger.warning(f"Context assembly: profile query failed: {e}")

        # 2. Conversation history is fetched via brain_ops (async), handled outside

        # 3. Active projects (narrative format to avoid triggering manager behavior)
        try:
            projects = db.fetch_all(
                """
                SELECT d.name, c.current_state
                FROM brain.contexts c
                JOIN brain.domains d ON c.domain_id = d.id
                WHERE d.is_project = true
                ORDER BY c.priority ASC
                LIMIT 8
                """
            )
            if projects:
                proj_parts = []
                for r in projects:
                    state = r.get('current_state') or ''
                    proj_parts.append(f"{r['name']} ({state})" if state else r['name'])
                parts.append(f"## What Zack is working on\n{'. '.join(proj_parts)}.")
        except Exception as e:
            logger.warning(f"Context assembly: projects query failed: {e}")

        # 4. Pending actions (narrative, not a task list)
        try:
            actions = db.fetch_all(
                """
                SELECT description
                FROM brain.actions
                WHERE status = 'pending'
                ORDER BY extracted_at DESC
                LIMIT 5
                """
            )
            if actions:
                action_summary = ". ".join(r['description'] for r in actions)
                parts.append(f"## Things on his mind\n{action_summary}.")
        except Exception as e:
            logger.warning(f"Context assembly: actions query failed: {e}")

        return parts

    # Run sync DB queries in thread
    parts = await asyncio.to_thread(_sync_fetch)

    # 2. Conversation history (async via brain_ops)
    try:
        history = await get_conversation_history(chat_id, limit=10)
        if history:
            history_text = "\n".join(
                f"{r['role'].title()}: {r['content']}" for r in history
            )
            # Insert after profile (position 1) for Gemini attention ordering
            insert_pos = 1 if len(parts) > 0 else 0
            parts.insert(insert_pos, f"## Recent Conversation\n{history_text}")
    except Exception as e:
        logger.warning(f"Context assembly: history query failed: {e}")

    # 3. Relevant memories (semantic search)
    try:
        vector_mgr = _get_vector_mgr()
        query_embedding = vector_mgr.generate_embedding(user_message)
        query_array = np.array(query_embedding)

        def _search_memories():
            db = _get_db()
            with db.get_connection() as conn:
                register_vector(conn)
                with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                    cur.execute(
                        """
                        SELECT content, domain, created_at,
                               embedding <=> %s::vector AS distance
                        FROM brain.memories
                        WHERE embedding IS NOT NULL
                        ORDER BY distance ASC
                        LIMIT 5
                        """,
                        (query_array,),
                    )
                    return [dict(r) for r in cur.fetchall()]

        memory_rows = await asyncio.to_thread(_search_memories)
        if memory_rows:
            mem_text = "\n".join(
                f"- {r['content'][:200]}" for r in memory_rows
            )
            # Insert after conversation history
            insert_pos = min(2, len(parts))
            parts.insert(insert_pos, f"## Relevant Memories\n{mem_text}")
    except Exception as e:
        logger.warning(f"Context assembly: semantic search failed (degrading gracefully): {e}")

    return "\n\n".join(parts)


# ---------------------------------------------------------------------------
# Response generation (Gemini 3 Flash)
# ---------------------------------------------------------------------------

async def generate_response(chat_id: int, user_message: str) -> str:
    """Generate a conversational response using Gemini with full brain context.

    Flow:
    1. Get or create session
    2. Score user message impact
    3. Save user message to conversations
    4. Promote to brain.memories if high-impact
    5. Assemble maximalist context
    6. Call Gemini 3 Flash with personality system prompt
    7. Save assistant response to conversations
    8. Return response text
    """
    # 1. Get or create session
    session_id = await get_or_create_session(chat_id, gap_minutes=SESSION_GAP_MINUTES)

    # 2. Score impact
    known_projects = _get_known_projects()
    impact = score_impact(user_message, known_projects)

    # 3. Save user message
    msg_id = await save_conversation_message(
        chat_id, session_id, "user", user_message, impact_score=impact
    )

    # 4. Promote high-impact messages to brain.memories
    if impact >= IMPACT_PROMOTION_THRESHOLD:
        try:
            await promote_message_to_memory(msg_id, user_message)
        except Exception as e:
            logger.warning(f"Failed to promote message {msg_id} to memory: {e}")

    # 5. Assemble context
    context = await _assemble_context(chat_id, user_message)

    # 6. Call Gemini
    try:
        client = _get_genai_client()
        config = types.GenerateContentConfig(
            system_instruction=PERSONALITY_SYSTEM_PROMPT,
            temperature=0.7,
        )
        response = await asyncio.wait_for(
            client.aio.models.generate_content(
                model="gemini-3-flash-preview",
                contents=f"{context}\n\nUser: {user_message}",
                config=config,
            ),
            timeout=30.0,
        )
        response_text = response.text if response and response.text else None
        # Log cost (non-blocking, never fails)
        if response:
            _log_cost(response, "telegram-conversation")
    except asyncio.TimeoutError:
        logger.error("Gemini call timed out after 30 seconds")
        response_text = None
    except Exception as e:
        logger.error(f"Gemini call failed: {e}", exc_info=True)
        response_text = None

    # 7. Fallback if Gemini failed
    if not response_text:
        response_text = "I'm having trouble thinking right now. Try again?"

    # 8. Save assistant response
    try:
        await save_conversation_message(
            chat_id, session_id, "assistant", response_text, impact_score=0.0
        )
    except Exception as e:
        logger.warning(f"Failed to save assistant response: {e}")

    return response_text


# ---------------------------------------------------------------------------
# Session synthesis
# ---------------------------------------------------------------------------

_synthesis_timers: dict[int, asyncio.Task] = {}

_SYNTHESIS_SYSTEM_PROMPT = (
    "You are a session summarizer. Produce a concise synthesis of this "
    "conversation. Focus on: decisions made, commitments stated, emotional "
    "context, project updates, and ideas worth revisiting. If meaning of "
    "earlier messages changed with later context, note that. Be specific "
    "-- names, projects, dates. 2-4 sentences max."
)


async def reset_synthesis_timer(chat_id: int) -> None:
    """Reset the synthesis timer for a chat. Called by handlers after each message.

    If message count >= SYNTHESIS_MESSAGE_THRESHOLD, runs synthesis immediately.
    Otherwise starts a silence countdown (SYNTHESIS_SILENCE_SECONDS).
    """
    # Cancel any existing timer for this chat
    existing = _synthesis_timers.pop(chat_id, None)
    if existing is not None:
        existing.cancel()
        try:
            await asyncio.sleep(0)  # Let cancellation propagate
        except Exception:
            pass

    # Check message count threshold
    try:
        session_id = await get_or_create_session(chat_id, gap_minutes=SESSION_GAP_MINUTES)
        messages = await get_session_messages(session_id)
        if len(messages) >= SYNTHESIS_MESSAGE_THRESHOLD:
            # Enough messages -- synthesize immediately in background
            asyncio.create_task(_run_synthesis(chat_id))
            return
    except Exception as e:
        logger.warning(f"Synthesis timer message count check failed: {e}")

    # Start silence countdown
    _synthesis_timers[chat_id] = asyncio.create_task(_synthesis_countdown(chat_id))


async def _synthesis_countdown(chat_id: int) -> None:
    """Wait for silence period, then run synthesis."""
    try:
        await asyncio.sleep(SYNTHESIS_SILENCE_SECONDS)
        await _run_synthesis(chat_id)
    except asyncio.CancelledError:
        # Normal -- timer was reset by a new message
        pass
    except Exception as e:
        logger.error(f"Synthesis countdown error for chat {chat_id}: {e}", exc_info=True)


async def _run_synthesis(chat_id: int) -> None:
    """Synthesize a session into a permanent memory.

    Gets the current session's messages, calls Gemini with a synthesis prompt,
    stores the result as a brain.memories entry, and marks the session synthesized.
    """
    try:
        # Get current session
        session_id = await get_or_create_session(chat_id, gap_minutes=SESSION_GAP_MINUTES)

        # Get all messages in this session
        messages = await get_session_messages(session_id)

        # Skip if fewer than 3 messages (not enough substance per CONV-05)
        if len(messages) < 3:
            logger.debug(f"Session {session_id}: only {len(messages)} messages, skipping synthesis")
            return

        # Format transcript
        transcript = "\n".join(
            f"{m['role'].title()}: {m['content']}" for m in messages
        )

        # Call Gemini for synthesis
        client = _get_genai_client()
        config = types.GenerateContentConfig(
            system_instruction=_SYNTHESIS_SYSTEM_PROMPT,
            temperature=0.3,  # Low for factual synthesis
        )
        response = await asyncio.wait_for(
            client.aio.models.generate_content(
                model="gemini-3-flash-preview",
                contents=transcript,
                config=config,
            ),
            timeout=30.0,
        )

        synthesis_text = response.text if response and response.text else None

        # Log synthesis cost
        if response:
            _log_cost(response, "telegram-synthesis")

        if not synthesis_text:
            logger.warning(f"Session {session_id}: synthesis returned empty response")
            return

        # Store as permanent memory
        memory_result = await capture_memory(synthesis_text, domain="conversation-synthesis")
        logger.info(f"Session {session_id} synthesized: {synthesis_text[:100]}...")

        # Get the memory ID from brain.memories (most recent with this domain)
        try:
            db = _get_db()
            row = await asyncio.to_thread(
                lambda: db.fetch_one(
                    """
                    SELECT id FROM brain.memories
                    WHERE domain = 'conversation-synthesis'
                    ORDER BY created_at DESC LIMIT 1
                    """
                )
            )
            if row:
                await update_session_synthesized(session_id, row["id"])
        except Exception as e:
            logger.warning(f"Failed to link synthesis memory to session: {e}")

    except asyncio.CancelledError:
        raise  # Let cancellation propagate
    except Exception as e:
        # Synthesis failure must NEVER crash the bot
        logger.error(f"Session synthesis failed for chat {chat_id}: {e}", exc_info=True)
    finally:
        # Clean up timer reference
        _synthesis_timers.pop(chat_id, None)


async def cleanup_stale_sessions() -> None:
    """Synthesize any sessions orphaned by bot restart.

    Checks brain.conversation_sessions for unsynthesized sessions where
    last_message_at is older than SYNTHESIS_SILENCE_SECONDS. Runs synthesis
    for each to prevent lost session data.
    """
    try:
        db = _get_db()

        def _find_stale():
            return db.fetch_all(
                f"""
                SELECT chat_id, session_id
                FROM brain.conversation_sessions
                WHERE synthesized = FALSE
                  AND last_message_at < NOW() - INTERVAL '{SYNTHESIS_SILENCE_SECONDS} seconds'
                ORDER BY last_message_at ASC
                """
            )

        stale_sessions = await asyncio.to_thread(_find_stale)

        if not stale_sessions:
            logger.info("No stale sessions to synthesize on startup")
            return

        logger.info(f"Found {len(stale_sessions)} stale session(s) to synthesize")
        for session in stale_sessions:
            try:
                await _run_synthesis(session["chat_id"])
            except Exception as e:
                logger.warning(
                    f"Stale session synthesis failed for {session['session_id']}: {e}"
                )

    except Exception as e:
        logger.error(f"Stale session cleanup failed: {e}", exc_info=True)
