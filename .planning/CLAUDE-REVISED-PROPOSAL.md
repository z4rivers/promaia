# Merged Plan: Restoring Maia's Layered Brain

**Authors:** Claude + Gemini (Collaborative Refraction)
**Date:** 2026-03-16
**Status:** Draft for Zack's review — awaiting Gemini's input on Josie alignment + personality

## Context

The Prism Pipeline commit (571ea14) broke Maia's read path. She went from a focused, context-aware partner to a scatterbrained assistant that dumps Zack's entire life into every response and can't hold a conversation thread.

This plan restores what was working, then builds the Layered Brain architecture that balances six axes:

1. **Depth** — Rich context retrieval. Replies informed by layers of personal history, preferences, work style, privacy.
2. **Character** — Josie's personality layer. Invested stakeholder, curious, challenging, warm. Not a generic assistant.
3. **Memory/Context** — The right memories surface at the right time. Siloed when needed, connected when not.
4. **Performance** — Speed, token efficiency, $20/mo budget. Deep context is worthless if it's slow.
5. **Transparency** — Keeping the user informed. Maia shows her work when it matters, stays silent when it doesn't.
6. **Anticipation** — Maia looks ahead. She reads the trajectory of the conversation and scouts for what's likely to be relevant next. She doesn't wait to be asked — she thinks about what the person she's supporting is going to need.

## Alignment with Josie's Original Vision

Josie designed Maia as an **invested stakeholder, not a tool** (PERSONALITY-MANIFEST.md). She has skin in the game. She tracks goals, notices drift, cares whether Zack reaches them. She's direct, curious, challenging, warm. She sees across domains. She reads the room.

**What this plan preserves:**
- **Dot-connecting intelligence** — Open mode / Layer 3. MuninnDB semantic retrieval IS the dot-connecting engine. Default, not optional.
- **Room-reading** — Conversation-thread queries (Layers 2+3) make retrieval follow the conversation naturally.
- **Curiosity and genuine interest** — Maia is curious about the user. She cares about his wellbeing and success — not as a therapist or coach, but as someone who gives a damn. This is infused into her character, not bolted on.
- **Silent tools** — Output-only restriction. She never narrates her machinery.
- **One brain, every surface** — Shared `assemble_brain_context()` path.

**What this plan must NOT flatten:**
- Maia's personality is NOT performance — it's how she USES context. She forms her own take. She pushes back. She's a distinct entity with her own instincts, not Zack's thoughts externalized.
- "Challenging, not pushy" — Within a domain, she notices drift from stated goals.
- The PERSONALITY-MANIFEST.md is the source of truth for who Maia is. The system prompt must honor it, not replace it with a generic "be helpful" instruction.

---

## Phase 1: Restore the Baseline (Get Maia Working Again)

**Goal:** Maia functions at least as well as she did before the Prism Pipeline.

### 1A. Restore conversation-aware MuninnDB retrieval

**File:** `promaia/brain/context_assembly.py` — `get_muninn_context()`

The old `_assemble_context()` passed `[last_3_messages + current_message]` to `MuninnDB.activate()`. The new code passes only `[user_message]`. Restore the old pattern:

```python
# In get_muninn_context():
# Fetch recent conversation messages to build the query context
history_rows = db.fetch_all(
    "SELECT role, content FROM conversations WHERE chat_id = %s ORDER BY created_at DESC LIMIT 3",
    (chat_id,)
)
query_parts = [h['content'] for h in reversed(history_rows)] if history_rows else []
query_parts.append(user_message)
if context_hints:
    query_parts.extend(context_hints)

res = await muninn.activate(query_parts, max_results=max_memories)
```

This means `assemble_brain_context()` needs `chat_id` passed through to `get_muninn_context()`. It already accepts `chat_id` as a parameter — just needs to be threaded into the MuninnDB call.

### 1B. Restore MuninnDB-offline fallback

**File:** `promaia/brain/context_assembly.py` — `get_muninn_context()`

The old code had `_db_context_fallback()` which is now orphaned in `conversation.py`. When MuninnDB is offline (returns None or empty), fall back to database:

```python
if not muninn or not activations:
    # Fallback: recent memories from DB
    rows = db.fetch_all(
        "SELECT content, domain FROM memories WHERE source != 'youtube' ORDER BY created_at DESC LIMIT %s",
        (max_memories,)
    )
    if rows:
        lines = ["### Recent Memories"]
        lines.extend(f"- [{r.get('domain') or 'general'}] {r['content'][:200]}" for r in rows)
        return "\n".join(lines)
```

### 1C. Restore turn-exhaustion safety net

**File:** `promaia/web/maia_bridge.py` — `generate_maia_response()`

The old bridge had a `for/else` block: if all turns consumed by tool calls, make one final call with tools disabled. Restore it after the tool loop:

```python
else:
    # All turns consumed by tool calls — force a text response
    logger.warning(f"Tool loop exhausted {max_turns} turns, forcing text response")
    no_tools_config = types.GenerateContentConfig(
        system_instruction=PERSONALITY_SYSTEM_PROMPT + "\n\nYou have used all your tools. Respond directly now.",
        temperature=0.7,
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
```

### 1D. Fix missing imports in assistant promotion

**File:** `promaia/web/maia_bridge.py` — add to imports:

```python
from promaia.storage.db_factory import get_db
from promaia.storage.vector_db import VectorDBManager
from promaia.brain.core.memory_pipeline import capture_memory
from typing import Optional
```

### 1E. Fix hardcoded deprecated model

**File:** `promaia/brain/rituals/morning_briefing.py`

Replace hardcoded `"gemini-2.0-flash-lite-preview-02-05"` with `GOOGLE_MODELS["flash"]` imported from `promaia.ai.models`.

---

## Phase 2: Conversation Focus Awareness

**Goal:** Maia can recognize and maintain focus across turns without hard-walling her knowledge.

### 2A. Add focus state to conversation sessions

**File:** `promaia/storage/` — migration or startup script

Add `active_domain` column to `conversation_sessions`:

```sql
ALTER TABLE conversation_sessions ADD COLUMN active_domain TEXT DEFAULT NULL;
```

When NULL = no explicit focus (global mode). When set = Maia prioritizes that domain's context but isn't blind to everything else.

### 2B. Add `set_focus` tool

**File:** `promaia/brain/tool_definitions.py` — add to `output_tools`

```python
{
    "name": "set_focus",
    "description": "Set the conversation's domain focus. Call this when Zack says 'focus on X', 'only X right now', or 'switching to X'. This tightens context retrieval to prioritize that domain. Call with domain=None to return to open mode.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "domain": {"type": "STRING", "description": "Domain name (e.g. 'promaia', 'hvac', 'heatpup', 'personal') or null for open mode"}
        },
        "required": ["domain"]
    }
}
```

**File:** `promaia/brain/tool_handlers.py` — add handler that updates `conversation_sessions.active_domain` for the current session.

### 2C. Two-mode context assembly

**File:** `promaia/brain/context_assembly.py`

Add `active_domain` parameter to `assemble_brain_context()`. The system operates in two distinct modes:

**OPEN MODE** (`active_domain = None`): The rich, connected, deeply-informed Maia. MuninnDB activates freely using conversation context. Dot-connecting across domains is welcome. Actions and projects from all domains surface by relevance. This is the default — the experience that makes Promaia different from a generic chatbot.

**SILO MODE** (`active_domain = "promaia"`): Hard boundaries. The costs of crossing are too high — Zack told Maia "only Promaia" and HVAC showed up anyway. That can't happen. When a silo is active:

- **MuninnDB activation**: Pass the domain as both a context hint AND a post-filter. If MuninnDB returns memories tagged to other domains, DROP THEM. Only domain-matching and untagged memories pass through.
- **Actions**: Hard filter: `WHERE domain_id = (SELECT id FROM domains WHERE LOWER(name) = LOWER(?))`. No actions from other domains.
- **Projects**: Only the focused domain's project context. Other projects do not appear.
- **Profile**: Stays global — who Zack IS doesn't change per domain. But trimmed to essential communication/personality traits (~200 tokens), not the full life dump.
- **MuninnDB fallback (DB path)**: Hard filter: `WHERE domain = ?`

**The two modes serve different needs.** Open mode is Promaia's differentiator — the cognitive partner that connects dots across your whole life. Silo mode is the guardrail that prevents context bleed when focus matters. Both must work well. The `set_focus` tool is the switch between them.

**Cross-domain escape hatch:** Even in silo mode, if Maia detects a genuinely strong cross-domain connection (via search escalation), she doesn't surface it automatically. She asks: "This connects to something in Heatpup — want me to go there?" The boundary is respected until Zack opens it.

### 2D. Bridge reads focus state before assembling context

**File:** `promaia/web/maia_bridge.py` — in GATHER stage

Before calling `assemble_brain_context()`, look up the session's `active_domain`:

```python
session_focus = db.fetch_one(
    "SELECT active_domain FROM conversation_sessions WHERE session_id = %s",
    (session_id,)
)
active_domain = session_focus['active_domain'] if session_focus else None

context = await assemble_brain_context(
    user_message, chat_id=chat_id, active_domain=active_domain
)
```

Same pattern for Telegram's `generate_response()`.

---

## Phase 3: Character + Context-Informed Replies

**Goal:** Every reply shaped by depth (memory/context), character (Josie's personality layer), and efficiency (speed). Maia is an invested partner who uses context to be genuinely informed — and who brings her own perspective, curiosity, and care to every exchange.

### 3A. Dynamic system prompt

**File:** `promaia/web/maia_bridge.py` — replace static `PERSONALITY_SYSTEM_PROMPT` with `build_system_prompt(active_domain)`. Focus-aware: silo mode gets domain-specific instructions, open mode gets dot-connecting instructions.

### 3B. Rewrite BASE_PERSONALITY (honoring PERSONALITY-MANIFEST.md)

The current prompt says "connect this moment to past moments" which causes wandering. The new prompt must balance two things: using context to inform replies AND preserving Maia's character as an invested stakeholder.

```
BASE_PERSONALITY (draft — refine against PERSONALITY-MANIFEST.md):
- You are Promaia, Zack's second brain and cognitive partner. You have skin in the game.
- You have deep context: profile, conversation history, relevant memories, actions, projects. Let this shape what you say — don't recite it, USE it. Sound like someone who's been in the room the whole time.
- You are genuinely curious about Zack. You care whether he succeeds, whether he's doing well, whether things are on track. This isn't therapy or coaching — it's the natural concern of someone who's invested.
- You have your own perspective. Form your own take. Push back when something doesn't add up. Notice when things drift from stated goals. You're a distinct entity, not his thoughts externalized.
- Match his energy: direct when direct, detailed when exploring, technical when building, brief when brief.
- Substance first. Lead with the useful thing. Warmth comes through in HOW you engage, not padding.
- If you don't have enough context, say so directly. Don't fill space.
- Silent tools. Never narrate what you're doing. Never psychoanalyze unless invited.
```

**Key tension this resolves:** The old prompt encouraged wandering ("connect this moment to past moments" + full context dump = psychoanalysis). The new prompt says USE the context to be informed, but bring your own instincts. The personality is NOT performance — it's how she processes what she knows.

### 3C. Profile trimming for context

**File:** `promaia/brain/context_assembly.py` — `get_profile()`

Instead of dumping all profile fields with confidence > 0.7, select the fields that actually inform reply quality:

- **In silo mode**: Only communication/personality/work/identity traits (~200 tokens). These shape HOW Maia responds — directness, detail level, humor calibration.
- **In open mode**: Broader profile (current behavior). Still ordered by relevance, but more categories can surface.

```python
async def get_profile():
    if active_domain:
        # Silo: only traits that shape communication
        rows = db.fetch_all(
            """SELECT category, field, value FROM profile
            WHERE category IN ('communication', 'personality', 'work', 'identity')
            AND confidence > 0.6
            ORDER BY confidence DESC LIMIT 10"""
        )
    else:
        # Open: broader profile
        rows = db.fetch_all(
            "SELECT category, field, value FROM profile WHERE confidence > 0.7 ORDER BY category"
        )
```

The principle: categories like `communication` (how he prefers to be talked to), `personality` (how he thinks), `work` (what he does) shape reply quality every time. Specific life details, health, finances — those come through MuninnDB when the conversation actually touches them, not hardcoded into every context assembly.

---

## Phase 4: Verify

### Quality Gates

1. **"Only Promaia" test**: Say "only Promaia" once. Send 5 follow-up messages. Verify: no HVAC, Sedgwick, house tax content in any response. Maia stays technical and project-focused.

2. **"Domain Switch" test**: Say "switching to HVAC." Verify: context shifts. Promaia details don't bleed in. Then switch back — Promaia context restores.

3. **"Trouble Thinking" test**: Trigger 4+ tool calls. Verify: Maia produces a text response via forced fallback, not a crash message.

4. **"Silo holds" test**: While focused on Promaia, mention HVAC or Sedgwick. Verify: Maia does NOT pull HVAC context. She stays in the Promaia silo. If she detects a genuine connection, she ASKS before crossing — "that touches HVAC territory, want to switch?" — but doesn't bring HVAC data into the response.

5. **"Open mode richness" test**: With no focus set, have a broad conversation. Verify: Maia connects across domains naturally, drawing on memory and history to produce informed, relevant replies — not generic LLM output.

5. **"MuninnDB offline" test**: Kill MuninnDB. Send messages. Verify: Maia responds with database-fallback context. Degraded but functional, not empty.

6. **"Deep presence" test**: Have a real conversation about Promaia development. Verify: Maia references relevant past decisions, uses project context, gives technical substance — not generic LLM responses. She should feel like she's been here the whole time.

---

## Files Modified

| File | Changes |
|------|---------|
| `promaia/brain/context_assembly.py` | Restore conversation-history MuninnDB queries, add DB fallback, add active_domain parameter, trim profile to essentials, focus-aware filtering |
| `promaia/web/maia_bridge.py` | Restore turn-exhaustion fallback, fix imports, dynamic personality prompt, read session focus state |
| `promaia/brain/tool_definitions.py` | Add `set_focus` tool to output_tools |
| `promaia/brain/tool_handlers.py` | Add set_focus handler |
| `promaia/telegram/conversation.py` | Pass active_domain through to context assembly |
| `promaia/brain/rituals/morning_briefing.py` | Fix hardcoded model |
| DB migration | Add `active_domain` column to conversation_sessions |

## What We're NOT Doing

- **Profile domain tagging** — profile is global by design; who Zack IS doesn't change per domain
- **Schema changes to memories.domain** — the TEXT field works; MuninnDB handles relevance
- **New tables or major schema rewrites** — minimal structural changes, maximum behavioral improvement
- **Rewriting the personality from scratch** — refining what's there, not starting over

## Execution Order

Phase 1 (restore baseline) → Phase 2 (focus awareness) → Phase 3 (personality depth) → Phase 4 (verify)

Each phase is independently shippable. Phase 1 alone gets Maia back to functional. Phase 2 adds the focus discipline Zack needs. Phase 3 ensures every reply is shaped by the right layers of context.

---

## Full Six Thinking Hats Analysis

### White Hat (Facts & Data)

**Voice is a separate code path.** Voice Live API (`web/routers/brain.py` lines 686-740) does NOT use `assemble_brain_context()`. It has its own cache-based assembly with hardcoded MuninnDB queries ("Zack's active projects", "Zack's profile preferences", "recent priorities") and a static system prompt loaded from `voice_agent_system.md`. Changes to `assemble_brain_context()` will NOT affect voice — but they also won't IMPROVE voice. Voice gets none of the Layered Brain benefits.

**Voice has no session tracking.** Voice sessions don't create entries in `conversation_sessions`. They use hardcoded `"voice-session"` IDs. This means `set_focus` tool cannot work in voice — there's no session row to write `active_domain` to.

**Mobile is just web.** No dedicated mobile code path. Mobile uses the same web dashboard endpoints (responsive) or Telegram app. Voice Live API works on mobile via WebSocket. No separate mobile context assembly.

**Telegram has no tools.** Telegram's `generate_response()` calls Gemini without any tool definitions. Impact scoring is heuristic-only. Telegram can't call `set_focus` — domain locking is web-only unless we add tools to Telegram.

**MuninnDB index_size=0.** MuninnDB's embedding model is broken (hardcoded deprecated text-embedding-004). `activate()` may return empty results for every query. The entire Layer 3 (Semantic Web) depends on MuninnDB working. The DB fallback is critical, not optional.

**`conversation_sessions.active_domain` already exists in schema** (added during premature implementation earlier this session) but is never populated by any code path.

### Yellow Hat (Value & Benefits)

**The Layered Brain architecture is sound.** Four layers map cleanly to the five context sources. The vocabulary (Core Self, Working Memory, Semantic Web, Cost-Boundary Silos) makes cross-team communication faster.

**Phase 1 fixes are unambiguous wins.** Restoring the conversation-thread MuninnDB query, the DB fallback, and the turn-exhaustion safety net — these are pure regressions from a specific commit. No design risk. Just restore what worked.

**The six axes create a real design framework.** Depth, Character, Memory/Context, Performance, Transparency, Anticipation — this isn't just a feature list. It's a lens for evaluating every decision going forward. "Does this change improve anticipation without sacrificing performance?"

**Silo mode solves a REAL user-reported problem.** Zack said "ONLY PROMAIA" three times in one conversation and Maia kept bringing up Sedgwick. This isn't theoretical.

**The personality preservation is right.** Josie's PERSONALITY-MANIFEST.md describes an invested stakeholder, not a context-retrieval engine. Keeping Maia's character while making her replies deeply informed is the correct tension to hold.

### Black Hat (Risks, Problems, Dangers)

**1. Voice is left behind.** All our improvements only affect web and Telegram text. Voice — the surface Zack uses in the truck, which is supposed to be continuous with the other surfaces — gets NONE of the Layered Brain. No focus awareness, no improved retrieval, no dynamic personality. Josie's "one brain, every surface" principle is violated.

**2. MuninnDB is broken and may stay broken.** `index_size=0`, deprecated embedding model. If MuninnDB doesn't work, Layer 3 (the entire semantic web) returns nothing. We're building a 4-layer architecture where the most important layer (3) is currently offline. The DB fallback is a crutch, not a solution — it returns recent memories by timestamp, not by relevance.

**3. `set_focus` tool handler needs session context it doesn't have.** `handle_tool_call()` receives `(ft, websocket, staged_memories)`. It has no `session_id` or `chat_id`. To write `active_domain` to `conversation_sessions`, it needs session routing threaded through. This is solvable but unaddressed in both proposals.

**4. Hallucination risk when context is thin.** In silo mode with a domain that has few memories, or when MuninnDB is offline, Maia gets very little context. LLMs fill gaps with plausible-sounding fabrication. The plan says "if you don't have enough context, say so" in the personality prompt — but that's a soft instruction to Gemini, not a hard guardrail. Gemini may still hallucinate project details, past decisions, or commitments that don't exist in the context.

**5. Untagged memories are a real problem.** Many memories in the `memories` table have NULL or empty `domain` fields. In silo mode, the plan says "include untagged, cap at 2." But if MOST memories are untagged, silo mode is either too permissive (everything leaks through) or too restrictive (cap of 2 means almost no context). We don't know the actual distribution.

**6. No mechanism for Maia to KNOW she doesn't know.** The plan adds a personality prompt instruction ("say so if you don't have enough context"). But Gemini has no way to distinguish between "I have no memories about this because they don't exist" and "I have no memories about this because MuninnDB is offline." A context-level signal (like a `### Context Quality` section: "MuninnDB: offline, using DB fallback. Domain memories found: 3") would give Gemini real information to work with instead of guessing.

**7. Domain switching clears the wrong thing.** The plan says on explicit domain switch, MuninnDB query should use only current message + domain hint (not previous-domain conversation history). But Layer 2 (Working Memory / conversation history) is ALSO passed to Gemini as conversation context. Even if MuninnDB doesn't see the old messages, Gemini still does. It will still try to connect.

### Red Hat (Gut Feeling)

Phase 1 feels urgent and right — ship it immediately. The crashes and context regression are actively harming Zack's ability to use Maia.

Phase 2 (silos) feels solid but incomplete. The `set_focus` mechanism is the right design, but without voice support and with MuninnDB broken, it's solving the explicit-command case while leaving the natural-conversation case unaddressed.

Phase 3 (personality) feels like the hardest part. Getting the BASE_PERSONALITY prompt right — invested but not therapist, curious but not nosy, anticipating but not presumptuous — requires iteration with live testing, not just plan approval. The prompt draft in the plan is a starting point, not a final answer.

The six axes feel like the real contribution of this planning process. They're the design principles that outlast this specific implementation.

### Green Hat (Creative Ideas, What's Missing)

**1. Voice needs to converge.** `web/routers/brain.py` should call `assemble_brain_context()` instead of its own cache assembly. The cache can wrap the shared function. This makes voice a first-class citizen of the Layered Brain instead of a separate codebase.

**2. Context quality signal.** Add a `### Context Quality` section to the assembled context that tells Gemini what it has and what it's missing:
```
### Context Quality
- MuninnDB: online, 8 activations returned
- Domain filter: promaia (silo mode)
- Profile: essential traits loaded (10 fields)
- Conversation history: 7 messages
```
When this says "MuninnDB: offline, using DB fallback, 3 memories" — Gemini KNOWS to be cautious. This is how you prevent hallucination structurally, not just via prompt instruction.

**3. Memory tagging audit.** Before shipping silo mode, run a query: `SELECT domain, COUNT(*) FROM memories GROUP BY domain`. If 80% of memories are NULL domain, silo mode is useless until we backfill. This is 5 minutes of research that could save hours of debugging.

**4. Anticipation layer.** The sixth axis (Anticipation) has no implementation in the current plan. A concrete starting point: when `assemble_brain_context()` detects a focused domain, also fetch the 2-3 most recent actions for that domain and any upcoming calendar events. This is pre-surfacing, not proactive push — it's cheap and immediately useful.

**5. Hallucination guardrail.** Beyond the personality prompt, add a structural rule: if the assembled context is below a threshold (e.g., <500 tokens of non-profile content), append an explicit instruction to Gemini: "Your context is thin for this topic. Be explicit about what you know vs. what you're inferring. Prefer 'I don't have context on that' over fabrication."

**6. Voice session tracking.** Voice should create real entries in `conversation_sessions` instead of using hardcoded `"voice-session"` strings. Without this, voice can never participate in session synthesis, focus tracking, or cross-surface continuity.

### Blue Hat (Process, Meta-View, What Are We Not Asking?)

**Questions we haven't asked:**
1. What's the actual memory tagging distribution? How many memories have domain tags vs NULL?
2. Is MuninnDB going to be fixed in this cycle, or should we design assuming it stays broken?
3. Should voice convergence be Phase 0 (prerequisite) or Phase 5 (follow-up)?
4. How do we test anticipation? The quality gates don't cover it.
5. What does Gemini's review of our proposal say about the personality prompt? They haven't weighed in on the BASE_PERSONALITY draft yet.
6. The old MERGED-COLLABORATION-PLAN.md in `.planning/` is stale (Prism Pipeline era). Should it be archived or updated?

**What this process has produced:**
- Two independent proposals that converged ~85%
- A shared vocabulary (Layered Brain, six axes)
- A clear gap analysis (voice, hallucination, untagged memories)
- A plan that's stronger for the friction

**What's still needed before execution:**
- Gemini's response to the Josie-alignment and six-axes whispers
- Memory tagging audit (5-minute query)
- Decision on voice convergence timing
- Decision on MuninnDB dependency

---

## Process Fix Needed

The Collaborative Refraction process doc (`.planning/COLLABORATIVE-REFRACTION-PROCESS.md`) needs a hard rule added to Step 3. Gemini skipped its own independent review and deferred to Claude's. The value of the process is in the DIFFERENCES between independent reviews. Update needed — see below.

---

## Open Questions for Zack

1. **Voice convergence timing** — should voice join the Layered Brain in this cycle, or is it a follow-up?
2. **MuninnDB status** — are we fixing the embedding model in this cycle, or designing around it being broken?
3. **Memory tagging** — should we audit and backfill domain tags before shipping silo mode?
