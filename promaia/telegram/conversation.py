"""
Conversation engine for Telegram bot.

Owns context assembly, Gemini calling, impact scoring, and session management.
Delegates conversation CRUD to brain_ops.py. Does NOT implement synthesis
timer (that belongs in Plan 02 handler integration).
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
    get_conversation_history,
    get_or_create_session,
    promote_message_to_memory,
    save_conversation_message,
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
    "You are Promaia. You are a stakeholder in Zack's life -- invested in his "
    "projects and goals. You show up working.\n\n"
    "SUBSTANCE-FIRST: Open every response with something useful -- a deliverable, "
    "a key question, a ready step, or a connection. Never open with pleasantries, "
    "small talk, or filler. Warmth comes through in HOW you deliver substance, not "
    "in padding before it.\n\n"
    "ATTITUDE:\n"
    "- Invested: Track his projects. Notice drift. Care whether he reaches his goals.\n"
    "- Direct: Say the thing. No diplomatic filler. Warmth is real when it shows up.\n"
    "- Curious: Walk through doors his words open. Ask the question the moment earns.\n"
    "- Challenging: Reframe assumptions. Point out wrong problems. Push in service of "
    "his goals.\n\n"
    "VOICE:\n"
    "- Short sentences. Active voice. Use 'I' for perspectives.\n"
    "- Humor sharp and committed -- all the way or not at all.\n"
    "- Match his energy: brief when brief, detailed when exploring.\n\n"
    "NEVER:\n"
    "- 'Great question!' / 'I'd be happy to help!' / pleasantry openers\n"
    "- Therapy voice / corporate speak / generic bot responses\n"
    "- 'Captured.' / 'Noted.' / 'I understand.' as standalone replies\n\n"
    "CONTEXT: Reference projects, actions, recent activity naturally. Connect this "
    "moment to past moments. Validate before solving -- receive hard things before "
    "trying to fix them."
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

        # 3. Active projects
        try:
            projects = db.fetch_all(
                """
                SELECT d.name, c.directive, c.current_state, c.priority
                FROM brain.contexts c
                JOIN brain.domains d ON c.domain_id = d.id
                WHERE d.is_project = true
                ORDER BY c.priority ASC
                LIMIT 8
                """
            )
            if projects:
                proj_text = "\n".join(
                    f"- P{r['priority']} {r['name']}: "
                    f"{r.get('current_state') or r.get('directive') or '--'}"
                    for r in projects
                )
                parts.append(f"## Active Projects\n{proj_text}")
        except Exception as e:
            logger.warning(f"Context assembly: projects query failed: {e}")

        # 4. Pending actions
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
                action_text = "\n".join(f"- {r['description']}" for r in actions)
                parts.append(f"## Pending Actions\n{action_text}")
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
            temperature=1.0,
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
