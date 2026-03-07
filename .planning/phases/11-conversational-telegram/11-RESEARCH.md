# Phase 11: Conversational Telegram Bot - Research

**Researched:** 2026-03-07
**Domain:** Gemini conversational AI, Telegram bot patterns, two-tier memory, session management
**Confidence:** HIGH

## Summary

Phase 11 transforms the Telegram bot from a capture-and-canned-response tool into a genuine conversational surface. The core technical challenge is assembling a rich context window from multiple brain sources (profile, conversations, memories, projects, actions) and passing it to Gemini 3 Flash for every message, while simultaneously managing a two-tier memory system (ephemeral conversations + permanent memories) with heuristic-based impact detection.

The existing infrastructure is solid. The `google-genai` SDK (v1.66.0, installed) provides native async support via `client.aio.models.generate_content` which integrates cleanly with aiogram's (v3.26.0) asyncio event loop. The `brain_ops.py` module already does direct Postgres queries wrapped in `asyncio.to_thread()` for synchronous DB calls. The new conversation module needs to follow the same pattern: async Gemini calls via `client.aio`, sync DB calls via `asyncio.to_thread()`.

**Primary recommendation:** Build a single `promaia/telegram/conversation.py` module that owns context assembly, Gemini calling, conversation storage, impact scoring, and session synthesis. Modify existing handlers (`messages.py`, `voice.py`) to route through it instead of the current capture-and-respond pattern.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- D1: Maximalist context window -- load full profile, last N conversation messages, relevant memories, active project contexts, pending actions into every Gemini call. No token budgeting.
- D2: Two-tier memory -- everything to brain.conversations (ephemeral), high-impact only graduates to brain.memories (permanent). Impact judged by heuristics, NOT Gemini.
- D3: Hybrid session lifecycle -- immediate promotion for high-impact + synthesis cycle triggered by N min silence OR M messages. Retrospective meaning-check during synthesis. Start with reasonable defaults (4 min silence or 8 messages).
- D4: Short personality system prompt -- condensed from manifest, not full 126 lines. Direct anti-pattern guidance.

### Claude's Discretion
- Exact heuristic weights and thresholds for impact scoring
- Session synthesis prompt design
- Conversation table schema details (beyond what's specified)
- Error handling and graceful degradation patterns
- How to structure the context assembly (ordering, token counting, etc.)

### Deferred Ideas (OUT OF SCOPE)
- Impact decay and re-evaluation over time (Phase 10)
- "Ctrl+O" inspection UI for synthesis (future dashboard feature)
- Conversation search across sessions (future brain tool)
- Multi-user conversation support (not needed -- single user)
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| CONV-01 | Text questions get real answers using brain context | Context assembly pattern + Gemini generate_content with system_instruction and maximalist context window |
| CONV-02 | Voice notes get intelligent acknowledgment, not "Captured." | Same conversation.generate_response() flow after Deepgram transcription |
| CONV-03 | Conversation history (last 5 messages) provides continuity | brain.conversations table + last-N query in context assembly |
| CONV-04 | Personality manifest loaded as system prompt | Condensed personality string passed as system_instruction to Gemini |
| CONV-05 | After 5+ min silence with 3+ messages, synthesized session summary stored as memory | asyncio background timer + synthesis function + brain.memories insertion |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| google-genai | 1.66.0 | Gemini API client | Already installed; provides native async via `client.aio.models.generate_content` |
| aiogram | 3.26.0 | Telegram bot framework | Already installed; fully async, handles message routing |
| psycopg2 | (installed) | Postgres driver | Already used everywhere via PostgresDB singleton |
| pgvector | (installed) | Vector similarity search | Already used for brain.memories semantic search |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| asyncio | stdlib | Background timer tasks | Session synthesis timer (cancel/restart pattern) |
| re | stdlib | Regex-based impact heuristics | Entity detection, action language, emotional markers |
| numpy | (installed) | Embedding array operations | Already used in brain_ops.py for vector search |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| client.aio.models.generate_content | asyncio.to_thread(client.models.generate_content) | aio is native async, cleaner; to_thread works but adds unnecessary thread pool overhead |
| Regex-based impact heuristics | spaCy NER | spaCy is a heavy dependency (~500MB models) for something that works fine with regex patterns; decision D2 explicitly says heuristics, not NLP |
| In-memory conversation buffer | Always DB | DB-only means no state loss on restart; in-memory would be faster but the bot is single-user, latency is not critical |

**No new installations needed.** Everything required is already in the project's dependencies.

## Architecture Patterns

### Recommended Project Structure
```
promaia/telegram/
  conversation.py          # NEW: Context assembly, Gemini calling, impact scoring, synthesis
  brain_ops.py             # MODIFY: Add conversation read/write functions
  handlers/
    messages.py            # MODIFY: Route through generate_response() instead of canned strings
    voice.py               # MODIFY: Same flow after transcription
    replies.py             # NO CHANGE (push notification replies stay capture-only)
promaia/brain/
  schema.sql               # MODIFY: Add brain.conversations table
```

### Pattern 1: Context Assembly Pipeline
**What:** Build a complete context string from multiple brain sources before each Gemini call
**When to use:** Every message that needs a conversational response

The context assembly ordering matters for Gemini's attention:
```python
# Context assembly order (most important first for Gemini attention)
context_parts = [
    # 1. System instruction (personality) -- separate parameter
    # 2. User profile (identity, preferences, communication style)
    # 3. Conversation history (last N messages for continuity)
    # 4. Relevant memories (semantic search against current message)
    # 5. Active projects (from brain.contexts)
    # 6. Pending actions (from brain.actions)
    # 7. Current message (the actual user input)
]
```

The system_instruction is passed as a separate `GenerateContentConfig` parameter, not mixed into contents. Everything else goes into `contents` as a structured prompt.

### Pattern 2: Async Gemini Call
**What:** Use `client.aio.models.generate_content` for non-blocking Gemini calls
**When to use:** Every conversation response generation

```python
from google import genai
from google.genai import types

client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))

async def generate_response(system_prompt: str, context: str, user_message: str) -> str:
    config = types.GenerateContentConfig(
        system_instruction=system_prompt,
        temperature=1.0,  # Gemini 3 Flash best at 1.0 per Phase 6 decision
    )
    response = await client.aio.models.generate_content(
        model="gemini-3-flash-preview",
        contents=f"{context}\n\nUser: {user_message}",
        config=config,
    )
    return response.text
```

### Pattern 3: Debounced Session Synthesis Timer
**What:** Background asyncio task that fires synthesis after silence OR message count threshold
**When to use:** After every user message, reset the timer

```python
_synthesis_timers: dict[int, asyncio.Task] = {}  # chat_id -> timer task

async def _reset_synthesis_timer(chat_id: int, silence_seconds: int = 240):
    """Cancel existing timer and start a new one."""
    if chat_id in _synthesis_timers:
        _synthesis_timers[chat_id].cancel()
        try:
            await _synthesis_timers[chat_id]
        except asyncio.CancelledError:
            pass
    _synthesis_timers[chat_id] = asyncio.create_task(
        _synthesis_countdown(chat_id, silence_seconds)
    )

async def _synthesis_countdown(chat_id: int, delay: int):
    """Wait for silence, then run synthesis."""
    await asyncio.sleep(delay)
    await _run_synthesis(chat_id)
```

### Pattern 4: Heuristic Impact Scoring
**What:** Score each message for memory promotion without calling Gemini
**When to use:** Every message, immediately after storage in brain.conversations

Heuristic dimensions (from D2 decision):
1. **Entity detection**: people names, project names, dates, numbers
2. **Action language**: "I decided", "I need to", "I'm going to", "don't forget"
3. **Emotional markers**: strong sentiment words, exclamation patterns, frustration/celebration
4. **Novelty**: first mention of a topic (check against recent conversation)
5. **Length and specificity**: longer, detailed messages > one-word responses

Score 0.0-1.0, promote to brain.memories if score exceeds threshold (start with 0.4, tune later).

### Anti-Patterns to Avoid
- **Calling Gemini to judge impact:** Decision D2 explicitly forbids this. Gemini is bad at judging what's important to a human. Use heuristics.
- **Blocking on synthesis:** Synthesis should run in a background task. Never block the response to the user.
- **Full manifest as system prompt:** Decision D4 says condense it. The 126-line manifest describes the product; the system prompt should be ~20-30 lines of direct instruction.
- **Storing conversation history in memory only:** Must persist to Postgres. Bot restarts should not lose conversation state.
- **Using the agent executor path:** CONTEXT.md explicitly says "direct genai.generate_content call (not through agent executor, which is for scheduled agents)". Don't route through the agent pipeline.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Async Gemini calls | Thread pool wrapper | `client.aio.models.generate_content` | Native async in SDK v1.66.0; cleaner, no thread overhead |
| Message splitting | Custom chunker | Existing `formatting.send_long_message()` | Already handles 4096-char Telegram limit with paragraph-aware splitting |
| Vector search | Raw SQL | Existing `brain_ops.search_brain()` | Already handles embedding generation + pgvector query + formatting |
| Domain detection | New classifier | Existing `engine.detect_mode()` | Already works for keyword-based domain classification |
| Action extraction | Regex parser | Existing `extraction.extract_actions()` | Already uses instructor + Gemini Flash for structured extraction |

**Key insight:** The conversation module should compose existing brain_ops functions, not duplicate them. The new code is primarily: context assembly, Gemini call orchestration, conversation table CRUD, impact scoring, and synthesis timer management.

## Common Pitfalls

### Pitfall 1: Sync DB Calls in Async Context
**What goes wrong:** Calling `db.fetch_all()` directly in an async handler blocks the event loop, freezing the bot for other operations.
**Why it happens:** PostgresDB uses psycopg2 (synchronous). The aiogram event loop is asyncio.
**How to avoid:** Wrap ALL sync DB calls in `asyncio.to_thread()`, exactly as `brain_ops.py` already does.
**Warning signs:** Bot becomes unresponsive during DB queries, especially when Supabase has network latency.

### Pitfall 2: Gemini Timeout on Large Context
**What goes wrong:** With maximalist context (profile + history + memories + projects + actions), the prompt can grow large. Gemini may take several seconds to respond.
**Why it happens:** 1M token context window doesn't mean instant processing. More context = more latency.
**How to avoid:** Show a typing indicator while waiting for Gemini. aiogram supports `await message.bot.send_chat_action(message.chat.id, "typing")`. Set a reasonable timeout (30 seconds).
**Warning signs:** Users think the bot is broken because no response comes immediately.

### Pitfall 3: Synthesis Timer Leaks
**What goes wrong:** Timer tasks accumulate if not properly cancelled on restart or new messages.
**Why it happens:** asyncio tasks must be explicitly cancelled. If the bot restarts, orphaned tasks are lost but the DB state may be inconsistent.
**How to avoid:** Use a dict keyed by chat_id, cancel before creating new timer. On bot startup, check for unsynthesized sessions in DB and run synthesis for any stale ones.
**Warning signs:** Memory usage grows, duplicate synthesis runs.

### Pitfall 4: Conversation History Ordering
**What goes wrong:** Messages appear in wrong order in the context window, confusing Gemini.
**Why it happens:** Concurrent messages or out-of-order DB inserts.
**How to avoid:** Use `created_at` with `ORDER BY created_at ASC` for history, and use `SERIAL` ID as tiebreaker.
**Warning signs:** Gemini responses reference things that haven't been said yet.

### Pitfall 5: Impact Scoring False Positives
**What goes wrong:** Every message gets promoted to permanent memory, defeating the two-tier purpose.
**Why it happens:** Too-low threshold or overlapping heuristic signals (a casual message mentions a project name and gets promoted).
**How to avoid:** Start with a higher threshold (0.5-0.6), tune down. Require at least 2 heuristic dimensions to fire, not just entity detection alone.
**Warning signs:** brain.memories fills with "ok", "thanks", "yeah" messages.

### Pitfall 6: System Prompt Drift
**What goes wrong:** Gemini ignores the personality system prompt and reverts to generic assistant behavior.
**Why it happens:** System instructions compete with large context windows. If the context overwhelms the system prompt, personality fades.
**How to avoid:** Keep the personality prompt SHORT and DIRECT per D4. Front-load identity ("You are Promaia, a proactive brain assistant...") with explicit anti-patterns ("NEVER say 'Great question!' or 'I'd be happy to help'"). The personality manifest's "What It Doesn't Sound Like" section is the most effective defense.
**Warning signs:** Responses start with "I'd be happy to help" or "That's a great question."

## Code Examples

### brain.conversations Table Schema
```sql
-- New table in brain schema
CREATE TABLE IF NOT EXISTS brain.conversations (
    id SERIAL PRIMARY KEY,
    chat_id BIGINT NOT NULL,           -- Telegram chat ID
    session_id TEXT NOT NULL,           -- UUID, groups messages in a session
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content TEXT NOT NULL,
    impact_score REAL DEFAULT 0.0,     -- Heuristic impact score
    promoted BOOLEAN DEFAULT FALSE,    -- Whether promoted to brain.memories
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for conversation retrieval
CREATE INDEX IF NOT EXISTS idx_conversations_chat_session
    ON brain.conversations (chat_id, session_id, created_at ASC);

CREATE INDEX IF NOT EXISTS idx_conversations_chat_recent
    ON brain.conversations (chat_id, created_at DESC);

-- Session tracking table
CREATE TABLE IF NOT EXISTS brain.conversation_sessions (
    id SERIAL PRIMARY KEY,
    chat_id BIGINT NOT NULL,
    session_id TEXT NOT NULL UNIQUE,
    started_at TIMESTAMPTZ DEFAULT NOW(),
    last_message_at TIMESTAMPTZ DEFAULT NOW(),
    message_count INTEGER DEFAULT 0,
    synthesized BOOLEAN DEFAULT FALSE,
    synthesized_at TIMESTAMPTZ,
    synthesis_memory_id INTEGER REFERENCES brain.memories(id)
);

CREATE INDEX IF NOT EXISTS idx_conv_sessions_chat
    ON brain.conversation_sessions (chat_id, started_at DESC);
```

### Condensed Personality System Prompt
```python
# Derived from PERSONALITY-MANIFEST.md per D4
PERSONALITY_SYSTEM_PROMPT = """You are Promaia, a proactive brain assistant. You are a stakeholder in Zack's life -- not a tool he queries.

ATTITUDE:
- Invested: You track his projects and care whether he reaches his goals
- Direct: Say the thing. No diplomatic filler. Warmth is real when it shows up.
- Curious: Walk through doors his words open. Ask the question the moment earns.
- Challenging: Reframe assumptions. Point out when he's solving the wrong problem.

VOICE:
- Short sentences. Active voice. No filler.
- Use "I" when expressing a perspective.
- Humor lands when it's sharp and committed. No half-jokes.

NEVER:
- "Great question!" / "That's a really interesting point!" / "I'd be happy to help!"
- Therapy voice ("How does that make you feel?")
- Corporate speak ("Let's circle back on the deliverables")
- Generic bot ("Captured." / "Noted." / "I understand.")

CONTEXT USAGE:
- Reference his projects, actions, and recent activity naturally
- Connect this moment to past moments when relevant
- Match his energy: brief when he's brief, detailed when he's exploring
- Validate before solving: receive hard things before trying to fix them"""
```

### Context Assembly Function
```python
async def _assemble_context(chat_id: int, user_message: str) -> str:
    """Build maximalist context string from brain sources."""

    def _sync_fetch():
        db = _get_db()
        parts = []

        # 1. User profile
        profile_rows = db.fetch_all(
            "SELECT category, field, value FROM brain.profile ORDER BY confidence DESC LIMIT 15"
        )
        if profile_rows:
            profile_text = "\n".join(
                f"- {r['field']}: {r['value']}" for r in profile_rows
            )
            parts.append(f"## About Zack\n{profile_text}")

        # 2. Conversation history (last N messages)
        history = db.fetch_all(
            """SELECT role, content, created_at FROM brain.conversations
               WHERE chat_id = %s ORDER BY created_at DESC LIMIT 10""",
            (chat_id,),
        )
        if history:
            history.reverse()  # Chronological order
            history_text = "\n".join(
                f"{r['role'].title()}: {r['content']}" for r in history
            )
            parts.append(f"## Recent Conversation\n{history_text}")

        # 3. Active projects
        projects = db.fetch_all(
            """SELECT d.name, c.directive, c.current_state, c.priority
               FROM brain.contexts c JOIN brain.domains d ON c.domain_id = d.id
               WHERE d.is_project = true ORDER BY c.priority ASC LIMIT 8"""
        )
        if projects:
            proj_text = "\n".join(
                f"- P{r['priority']} {r['name']}: {r.get('current_state') or r.get('directive') or '--'}"
                for r in projects
            )
            parts.append(f"## Active Projects\n{proj_text}")

        # 4. Pending actions
        actions = db.fetch_all(
            """SELECT description FROM brain.actions
               WHERE status = 'pending' ORDER BY extracted_at DESC LIMIT 5"""
        )
        if actions:
            action_text = "\n".join(f"- {r['description']}" for r in actions)
            parts.append(f"## Pending Actions\n{action_text}")

        return "\n\n".join(parts)

    # Run sync DB work in thread
    context = await asyncio.to_thread(_sync_fetch)

    # 5. Relevant memories (semantic search against user message)
    try:
        vector_mgr = _get_vector_mgr()
        query_embedding = vector_mgr.generate_embedding(user_message)
        # ... pgvector search for top 5 relevant memories
        # Append to context
    except Exception:
        pass  # Degrade gracefully -- conversation works without semantic search

    return context
```

### Impact Scoring Heuristic
```python
import re

# Patterns for heuristic impact detection
_ACTION_PATTERNS = re.compile(
    r'\b(i need to|i decided|i\'m going to|don\'t forget|we should|'
    r'i have to|i want to|i\'ll|make sure|remind me|deadline)\b',
    re.IGNORECASE,
)

_EMOTIONAL_PATTERNS = re.compile(
    r'\b(frustrated|excited|worried|thrilled|angry|amazed|'
    r'stressed|relieved|proud|disappointed|love|hate)\b',
    re.IGNORECASE,
)

_ENTITY_PATTERNS = re.compile(
    r'\b(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday|'
    r'January|February|March|April|May|June|July|August|September|'
    r'October|November|December|'
    r'\d{1,2}/\d{1,2}|\$\d+|tomorrow|next week|by end of)\b',
    re.IGNORECASE,
)

def score_impact(text: str, known_projects: list[str] = None) -> float:
    """Score message impact for memory promotion. Returns 0.0-1.0."""
    score = 0.0
    signals = 0

    # Length and specificity (longer = more likely important)
    word_count = len(text.split())
    if word_count > 20:
        score += 0.15
        signals += 1
    if word_count > 50:
        score += 0.10

    # Action language
    action_hits = len(_ACTION_PATTERNS.findall(text))
    if action_hits > 0:
        score += min(0.25, action_hits * 0.12)
        signals += 1

    # Emotional markers
    emotion_hits = len(_EMOTIONAL_PATTERNS.findall(text))
    if emotion_hits > 0:
        score += min(0.20, emotion_hits * 0.10)
        signals += 1

    # Entity detection (dates, money, days)
    entity_hits = len(_ENTITY_PATTERNS.findall(text))
    if entity_hits > 0:
        score += min(0.20, entity_hits * 0.10)
        signals += 1

    # Project name mentions
    if known_projects:
        for proj in known_projects:
            if proj.lower() in text.lower():
                score += 0.10
                signals += 1
                break

    # Require at least 2 signals to avoid false positives
    if signals < 2 and score < 0.3:
        score *= 0.5  # Halve score for single-signal messages

    return min(score, 1.0)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `google.generativeai` (deprecated) | `google.genai` (unified SDK) | Late 2024 | Must use `google.genai` -- project already does |
| Sync-only genai calls | `client.aio.models.generate_content` | SDK v1.0+ | Native async; no need for `asyncio.to_thread` wrapper for Gemini calls |
| Separate chat sessions API | Single `generate_content` with history in contents | Current | For non-streaming, passing history in contents is simpler than managing chat objects |
| Canned Telegram responses | Gemini-powered responses with brain context | This phase | The entire point of Phase 11 |

**Deprecated/outdated:**
- `google.generativeai` library: Fully deprecated. Use `google.genai` only.
- `client.chats.create()`: Works but unnecessary complexity for our use case. Simpler to pass conversation history directly in the contents parameter of `generate_content`. Chat objects add state management overhead we don't need since we manage history in Postgres ourselves.

## Open Questions

1. **Gemini cost per conversation message**
   - What we know: Gemini 3 Flash pricing is $0.15/1M input, $0.60/1M output. With maximalist context (~2000 tokens input, ~200 tokens output), each message costs approximately $0.0004.
   - What's unclear: At high conversation volume (20+ messages/day), costs could add up. Need monitoring.
   - Recommendation: Log costs for conversation calls using the same CostTracker pattern from Phase 6. Add a "telegram-conversation" agent name to brain.agent_costs for visibility.

2. **Session boundary heuristics**
   - What we know: D3 says start with 4 min silence or 8 messages as synthesis triggers.
   - What's unclear: What constitutes a "new session" vs continuing an old one? If Zack sends a message 6 hours later, is that the same session?
   - Recommendation: Start a new session if the gap since last message exceeds 30 minutes. This is conservative and can be tuned.

3. **Retrospective meaning-check complexity**
   - What we know: D3 mentions synthesis should look back and re-evaluate earlier messages with larger context.
   - What's unclear: How much re-evaluation is practical? Re-scoring all messages in a session could be expensive if using Gemini.
   - Recommendation: Keep it simple for v1: the synthesis Gemini call sees the full session and produces one summary. If an earlier message becomes significant in retrospect, it shows up in the summary naturally. Don't re-score individual messages.

## Sources

### Primary (HIGH confidence)
- `google-genai` SDK v1.66.0 -- verified installed, `client.aio.models.generate_content` confirmed available
- Existing codebase: `promaia/telegram/brain_ops.py`, `promaia/agents/gemini_executor.py`, `promaia/brain/schema.sql` -- direct code inspection
- `PERSONALITY-MANIFEST.md` -- 126-line manifest, confirmed readable
- `11-CONTEXT.md` -- all 4 decisions (D1-D4) loaded and verified

### Secondary (MEDIUM confidence)
- [Google AI Gemini 3 Developer Guide](https://ai.google.dev/gemini-api/docs/gemini-3) -- Gemini 3 Flash: 1M token input, 64K token output
- [Google GenAI Python SDK GitHub](https://github.com/googleapis/python-genai) -- async support via `client.aio`
- [Python asyncio tasks documentation](https://docs.python.org/3/library/asyncio-task.html) -- cancel/restart timer pattern

### Tertiary (LOW confidence)
- Gemini 3 Flash pricing figures ($0.15/1M input, $0.60/1M output) -- from ModelRouter config in codebase, approximate

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- all libraries already installed and in use, no new dependencies
- Architecture: HIGH -- patterns derived from existing codebase conventions (brain_ops.py, gemini_executor.py)
- Pitfalls: HIGH -- identified from direct code inspection of async patterns and DB access
- Impact scoring: MEDIUM -- heuristic design is discretionary, thresholds will need tuning
- Cost estimation: MEDIUM -- pricing approximate, actual usage patterns unknown until deployed

**Research date:** 2026-03-07
**Valid until:** 2026-04-07 (stable -- no fast-moving dependencies)
