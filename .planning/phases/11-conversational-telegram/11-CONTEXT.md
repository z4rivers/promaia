---
phase: 11-conversational-telegram
type: context
created: 2026-03-07
---

# Phase 11 Context: Conversational Telegram Bot

## Phase Boundary

Telegram becomes a real conversational surface. Gemini-powered responses using brain context, personality manifest, conversation history, and profile. Messages are captured to a two-tier memory system with impact-based promotion.

**Not in scope:** Impact decay/re-evaluation over time (Phase 10), dashboard changes, new Telegram commands, web deployment.

## Decisions

### D1: Context Window — Maximalist

Load everything useful into each Gemini call. Google models handle large contexts well. Per-message context includes:
- Full profile prefix (identity, preferences, communication style, current projects)
- Last N conversation messages (from brain.conversations)
- Recent relevant memories (semantic search against the user's message)
- Active project contexts (from brain.contexts)
- Pending actions (from brain.actions)
- No token budgeting. Let Gemini handle it.

**Rationale:** "Google can handle context. Throw everything at it that could help."

### D2: Two-Tier Memory — Conversations vs Memories

Everything hits `brain.conversations` (ephemeral session history for continuity).
Only high-impact items graduate to `brain.memories` (permanent, embedded, searchable).

**Impact test:** "Would it make a difference if this weren't recorded?" Specifically:
- Is it likely to be referenced or retrieved later?
- Is it memorable, impactful, or unique?
- Is it noise/formality, or is it saying something?
- Tone matters: mundane words said with intensity or unusual context = important
- Something not "important" but genuinely funny or memorable = worth keeping

**Impact judge:** NOT Gemini (bad at judging impact). Use heuristics:
- Entity detection (people, projects, decisions, commitments, dates)
- Action language ("I decided", "I need to", "I'm going to")
- Emotional markers (strong sentiment, frustration, celebration)
- Novelty (first mention of a topic vs repetition)
- Length and specificity (detailed thought vs one-word response)

### D3: Session Lifecycle — Hybrid Timer + Retrospective Synthesis

**Immediate promotion:** Messages likely to be referenced later go straight to `brain.memories`. Not "critical" in the urgency sense — just worth keeping. Heuristic-based (same as D2 impact test).

**Synthesis cycle:** Hybrid trigger — fires after N minutes of silence OR after M messages, whichever comes first. Start with reasonable defaults (e.g., 4 min silence or 8 messages) and adjust after testing.

**Retrospective meaning-check:** Each synthesis cycle looks back at the last few summaries/messages to see if meaning has changed with larger context. Example: "thinking about switching jobs" at minute 1 becomes historically significant when "I told my boss" arrives at minute 3. The synthesis should catch this and upgrade significance of earlier context.

**Visibility:** Synthesis is invisible infrastructure. User doesn't see it happening. But a "Ctrl+O"-like mechanism should exist for users who want to inspect what was captured/synthesized — this is a future UI feature, not blocking for Phase 11.

### D4: Personality System Prompt — Short and Simple

The PERSONALITY-MANIFEST.md (126 lines) defines the PRODUCT, not the system prompt. The actual Gemini system prompt should be:
- Short — condensed essence of the manifest, not the full document
- Direct anti-pattern guidance: "Don't exaggerate, don't be theatrical, don't be overly literal"
- Gemini cannot be contained by elaborate guardrails. Brevity works better than walls of instructions.
- The personality emerges from the SYSTEM (brain context, profile, conversation history) more than from the prompt itself

## Code Context

### Existing infrastructure to build on
- `promaia/telegram/brain_ops.py` — capture_memory, search_brain, get_briefing, get_actions, get_projects (all async)
- `promaia/telegram/handlers/messages.py` — greeting/question/capture routing, _is_greeting(), _is_question()
- `promaia/telegram/bot.py` — router order: commands > voice > replies > messages
- `promaia/agents/executor.py` — Gemini execution path (genai.generate_content, model routing from Phase 6)
- `promaia/brain/engine.py` — detect_mode() for domain classification
- `promaia/storage/vector_db.py` — VectorDBManager for embeddings
- `promaia/storage/postgres_db.py` — get_postgres_db() for all DB operations

### New artifacts needed
- `brain.conversations` table — chat_id, role (user/assistant), content, created_at, session_id
- `promaia/telegram/conversation.py` — generate_response(), session management, synthesis timer
- Personality system prompt (stored in brain or as a config, not hardcoded in code)
- Impact heuristic function (scores messages for memory promotion)

### Integration points
- `handlers/messages.py` — after capture, call generate_response() for the reply instead of canned strings
- `handlers/voice.py` — same flow: transcribe → capture → generate conversational response
- `brain_ops.py` — add conversation history read/write functions
- Gemini API — direct genai.generate_content call (not through agent executor, which is for scheduled agents)

## Deferred Ideas

- Impact decay and re-evaluation over time → Phase 10 (dynamic memory)
- "Ctrl+O" inspection UI for synthesis → future dashboard feature
- Conversation search across sessions → future brain tool
- Multi-user conversation support → not needed (single user)
