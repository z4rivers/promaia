# Maia Hardening Plan: From Weekend Hack to Professional Product

## The Problem

Maia's conversation engine is a single `for` loop that hands Gemini 16 live tools
and hopes for the best. When it works, it's magic. When it doesn't, she loops,
crashes, or "has trouble thinking." We've spent an entire session adding safety
nets (turn limits, forced responses, tool blocking) — all necessary, all band-aids.

The root cause: **Maia has no architecture. She has a loop.**

## The Vision

Maia responds in under 3 seconds. She never loops. She never crashes. She always
has context. She gets smarter every week without manual patches. She feels the
same on web, Telegram, and voice. She is a product, not a prototype.

---

## Phase 1: Context-First Architecture (The Big One)

**Goal:** Maia never gathers context during conversation. She already has it.

### Current State (broken)
```
User message → Gemini gets 16 tools → freewheels for 10 turns →
  maybe answers, maybe loops, maybe crashes
```

### Target State
```
User message → Bridge gathers context (no LLM) → Gemini gets
  context + message + output-only tools → responds in 1 turn
```

### Implementation

**1.1 — Extract and unify `_assemble_context`**
- Currently lives only in `promaia/telegram/conversation.py:326-407`
- Extract to `promaia/ai/context_engine.py` as a shared module
- Both web bridge and Telegram import from the same source
- Inputs: user_message, chat_id, session_id
- Outputs: structured context block (profile, memories, actions, projects, conversation history)

**1.2 — Smart context routing**
The context engine should do lightweight intent detection BEFORE calling Gemini:
- Message mentions a file path → `read_file` automatically, add to context
- Message asks about a project → query brain for project context
- Message references "that email" or "my schedule" → pull relevant data
- Message is casual conversation → minimal context (profile + recent history)

This is NOT an LLM call. It's keyword/pattern matching + brain queries.
Fast, deterministic, predictable.

**1.3 — Split tools into input vs output**
```python
INPUT_TOOLS = [
    "recall_memory",        # Brain search
    "query_workspace",      # NL database search
    "read_file",            # Source code access
    "sync_youtube_context", # YouTube pull
    "query_youtube_transcript",
    "run_workspace_sync",   # Data refresh
]

OUTPUT_TOOLS = [
    "save_conversation_memory",  # Persist insights
    "commit_staged_memories",    # Confirm saves
    "create_action",             # Create action items
    "create_calendar_event",     # Schedule events
    "delete_calendar_event",     # Remove events
    "send_email_draft",          # Draft emails
    "write_content",             # Generate documents
    "log_system_feedback",       # Report issues
    "switch_cognitive_mode",     # Change thinking mode
    "hang_up_call",              # End voice call
]
```

Phase 2 (response generation) only gets OUTPUT_TOOLS.
Phase 1 (context gathering) uses INPUT_TOOLS via code, not Gemini.

**1.4 — Rewrite `maia_bridge.py`**
```python
async def generate_maia_response(user_message, ...):
    # Phase 1: Gather (no LLM, <500ms)
    context = await context_engine.assemble(
        user_message=user_message,
        chat_id=chat_id,
        session_id=session_id,
    )

    # Phase 2: Respond (LLM, output tools only, 1-3s)
    response = await client.aio.models.generate_content(
        model=GOOGLE_MODELS["flash"],
        contents=[context.to_prompt() + f"\n\nUser: {user_message}"],
        config=GenerateContentConfig(
            system_instruction=PERSONALITY_SYSTEM_PROMPT,
            tools=[{"function_declarations": OUTPUT_TOOL_DECLARATIONS}],
            temperature=0.7,
        ),
    )
    # Handle output tool calls (save memory, create action, etc.)
    # Max 3 output tool turns, then done
```

**Files changed:** 4
- NEW: `promaia/ai/context_engine.py`
- REWRITE: `promaia/web/maia_bridge.py`
- EDIT: `promaia/telegram/conversation.py` (import shared context engine)
- EDIT: `promaia/brain/tool_definitions.py` (split input/output declarations)

**Success criteria:**
- Maia responds to any message in <3 seconds
- Zero "trouble thinking" errors
- Tool calls limited to output actions (save, create, schedule)
- Context is always fresh and relevant

---

## Phase 2: Response Quality

**Goal:** Maia's answers are sharp, specific, and connected — not generic chatbot filler.

### 2.1 — Prompt unification
- Web prompt is 86 words. Telegram is 258. voice_agent_system.md is 331.
- Canonical prompt lives in ONE place: `promaia/ai/maia_prompt.py`
- All surfaces (web, Telegram, voice) import from the same source
- Surface-specific additions (e.g., "on the web dashboard") are appended, not duplicated

### 2.2 — Context quality scoring
Not all context is equal. The context engine should rank what it surfaces:
- Recent conversation history: always included
- Profile fields: top 10 by relevance to current message (semantic match)
- Memories: top 5 by semantic similarity to user message
- Actions: only pending, max 5, most recent first
- Projects: only active, sorted by staleness (freshest first)

Result: Maia gets a FOCUSED context window, not a dump of everything.

### 2.3 — Response post-processing
- Strip any "Let me check that for you" narration (SILENT TOOLS enforcement)
- Strip any tool call narration that leaked into text
- Ensure response starts with substance, not filler

---

## Phase 3: Reliability & Self-Healing

**Goal:** Maia monitors herself and recovers without human intervention.

### 3.1 — Health dashboard
- Response time tracking (p50, p95, p99)
- Tool call frequency per message (target: <1 average)
- Error rate tracking (target: 0% "trouble thinking")
- Context assembly time tracking (target: <500ms)

### 3.2 — Automatic recovery
- If Gemini returns empty text: retry once with simplified context
- If context assembly fails: respond with profile-only context (never blank)
- If a tool handler crashes: log it, continue without it, surface in health dashboard
- Circuit breaker: if error rate >10% in 5 minutes, switch to minimal mode (no tools, just talk)

### 3.3 — Structured error responses
Replace "I'm having trouble thinking right now" with useful feedback:
```
"I couldn't find what I was looking for in [source]. Can you be more specific?"
"My workspace search came up empty. Try asking about [related topic I do know about]."
"I hit a technical snag reading [file]. The rest of my context is fine — here's what I know..."
```

---

## Phase 4: Memory That Works

**Goal:** Maia's memory retrieval is surgical, not scattershot.

### 4.1 — Fix MuninnDB or replace it
- Currently blocked: hardcoded embedding model, zero index
- Options: (a) fix MuninnDB embedding config, (b) use brain's own sqlite-vec embeddings
- Decision needed: is MuninnDB still the right choice, or do we consolidate on sqlite-vec?

### 4.2 — Proactive memory surfacing
- Context engine checks: "Has anything changed since last conversation?"
- If new actions completed, new memories captured, or project context updated → surface it
- "Since we last talked, your morning briefing flagged [X] and [Y] got marked done."

### 4.3 — Memory decay and refresh
- Old memories lose relevance weight over time
- Recently confirmed/referenced memories get boosted
- Stale profile fields get flagged for ambient re-verification

---

## Phase 5: Multi-Surface Consistency

**Goal:** Same Maia everywhere. Different surfaces, same brain.

### 5.1 — Shared session state
- Web and Telegram currently have separate conversation histories
- Unify: one conversation session per user, accessible from any surface
- "I told Maia on Telegram about X" should be visible on web

### 5.2 — Surface-appropriate formatting
- Web: markdown rendering, collapsible sections, inline links
- Telegram: plain text, short paragraphs, emoji sparingly
- Voice: spoken-word optimized, no lists, no URLs, conversational cadence

### 5.3 — Handoff awareness
- If Maia was mid-conversation on Telegram, web should know
- "Picking up from where we left off on Telegram..."

---

## Execution Priority

| Phase | Impact | Effort | When |
|-------|--------|--------|------|
| 1 (Context-First) | MASSIVE | Medium (4 files) | NEXT SESSION |
| 2 (Response Quality) | HIGH | Small (prompt unification) | Same session or next |
| 3 (Self-Healing) | HIGH | Medium | After Phase 1 proves stable |
| 4 (Memory) | MEDIUM | Depends on MuninnDB decision | After Phase 3 |
| 5 (Multi-Surface) | MEDIUM | Large | After Phase 4 |

Phase 1 is the heavy equipment. Everything else builds on it.

---

## What Tonight's Session Proved

8 commits. 20 bugs fixed. Maia still "has trouble thinking."

The plumbing works now — no more crashes, no more Postgres ghosts, no more stale
model refs. But the architecture is still a single loop handing Gemini 16 tools.
No amount of patching fixes that. Phase 1 does.
