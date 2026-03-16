# Context Siloing: Problem Statement & Audit Report
## Collaborative Refraction — Step 1: Frame the Problem

**Author:** Claude (Opus 4.6), with audit contributions from 4 parallel subagents
**Date:** 2026-03-16
**Trigger:** Prism Pipeline (571ea14) shipped "Phases 1-5 complete" and broke Maia's ability to hold a focused conversation. Live testing revealed fundamental architectural gaps in context retrieval.
**Process:** This document initiates the [Collaborative Refraction Process](COLLABORATIVE-REFRACTION-PROCESS.md). Claude and Gemini will develop independent proposals, cross-evaluate via Six Thinking Hats, and converge on a merged plan with Zack's final authority.

---

## 1. What's Broken

### 1.1 The Presenting Symptoms

Two live Maia conversations on 2026-03-16 demonstrate cascading failures:

**Conversation 1 (12:09–12:22):**
- Zack says "ONLY ONE PROJECT RIGHT NOW — Promaia" three separate times
- Maia responds with Sedgwick insurance claims, house tax analysis, HVAC job commentary, and a "House Poor Paradox" psychoanalysis
- Two "I'm having trouble thinking right now" crashes in 13 minutes
- When asked for a technical evaluation of the Maia project list, Maia asks Zack what to focus on instead of reading her own project contexts and memories
- Zack: "STOP ASKING ME. You are the AI with insight into the brain!!"

**Conversation 2 (12:35–12:42):**
- Same session, after repeated corrections, Maia still brings up HVAC and trade job
- Zack: "I'm terrified that I have made you unusable"
- Zack: "One of the PRIME claims of this whole project is the ability to CLEARLY SILO different projects, life areas, interest areas"
- Maia correctly diagnoses the problem: "Muninn is definitely a completionist. I see the whole spread... but I don't have to let them steer the car"
- Maia proposes three mechanics: mandatory domain tagging, contextual blindness, clean slate protocol
- But she cannot implement any of them — the architecture doesn't support it

### 1.2 The Root Causes (Verified by Full Audit)

**Root Cause #1: Context assembly replaced smart retrieval with dumb dumping**

The Prism Pipeline commit replaced `_assemble_context()` (in `telegram/conversation.py`) with `assemble_brain_context()` (new file `brain/context_assembly.py`). The old function was the reference implementation that worked. The new function is architecturally simpler but functionally degraded.

| Behavior | Old `_assemble_context()` | New `assemble_brain_context()` |
|----------|--------------------------|-------------------------------|
| MuninnDB query input | Last 3 conversation messages + current message | Current message only |
| MuninnDB offline fallback | `_db_context_fallback()` — profile, recent memories, projects | Returns empty string |
| Profile handling | Only in fallback path (MuninnDB handles relevance) | ALL fields with confidence > 0.7, unconditionally |
| Project handling | Via MuninnDB relevance | ALL projects, unconditionally |
| Action formatting | Narrative ("Things on his mind") | Task list ("Pending Actions") |
| Domain scoping | Soft (MuninnDB relevance filtering via conversation context) | None |

The critical regression: MuninnDB's `activate()` function takes a context array and returns *relevant* results. The old code passed `[last_msg_1, last_msg_2, last_msg_3, current_msg]` — so if you're talking about Promaia, you get Promaia memories. The new code passes `[current_msg]` only — losing the conversation thread that guided retrieval.

Additionally, the old code only dumped the full profile in fallback mode (when MuninnDB was offline). The new code dumps ALL profile fields (Sedgwick, HVAC, house taxes, relationships, etc.) every single time as Priority 1, pushing life noise ahead of conversation-relevant context.

**Root Cause #2: No domain scoping exists in ANY code path**

Neither the old nor new system has hard domain silos. The old system had soft filtering via MuninnDB relevance (a reasonable proxy). The new system has nothing. There is no mechanism to:
- Lock context retrieval to a specific domain ("only Promaia")
- Carry a focus directive across conversation turns
- Filter profile/memory/action retrieval by domain
- Switch domains explicitly ("Switching to HVAC")

**Root Cause #3: Turn-exhaustion safety net removed**

Old bridge: `max_turns=10` with a fallback that forces a text response (tools disabled) if all turns were consumed by tool calls.
New bridge: `max_turns=4` with NO fallback. If Gemini makes 4 tool calls without producing text → `response_text = None` → "I'm having trouble thinking right now."

**Root Cause #4: Personality prompt encourages wandering**

The `PERSONALITY_SYSTEM_PROMPT` in `maia_bridge.py` says:
- "Connect this moment to past moments when relevant"
- "Offer insight over status"
- "Stay in reflection mode"

Combined with a context dump that includes the user's entire life, this instructs Gemini to actively connect Promaia work to HVAC, Sedgwick, house taxes, etc. The prompt has no instruction to:
- Stay on topic once a focus is established
- Prioritize technical analysis when asked for it
- Avoid psychologizing unless invited

**Root Cause #5: Assistant response promotion silently broken**

`maia_bridge.py` lines 247-255 call `get_db()`, `VectorDBManager()`, and `capture_memory()` without importing them. Every high-impact assistant response triggers a `NameError`, caught by try/except, silently doing nothing. The echo-chamber prevention (assistant memory weighting) in `context_assembly.py` is moot because no assistant memories are ever created.

---

## 2. What It Costs

### 2.1 User Trust
Zack describes being "terrified" and feeling like "Wile E. Coyote." A system that promises to be your second brain but can't hold focus for 3 messages is worse than no system — it actively undermines confidence in the project.

### 2.2 Token Waste
Full profile dump + all projects + all actions = ~2,000 tokens of context per message that Gemini has to process but mostly ignore. On a $20/mo plan, this is real money spent on noise.

### 2.3 Core Product Promise
Domain siloing is described by Zack as "one of the PRIME claims of this whole project." Without it, Promaia is a junk drawer, not a second brain. Every surface (Telegram, Web/Maia, Voice, Claude/MCP) needs this.

### 2.4 Development Velocity
Every conversation with Maia that goes sideways is a conversation that should have been productive. Zack is trying to use Maia to develop Maia — meta-productivity that requires the tool to actually work.

---

## 3. What Still Works (Preserve These)

The Prism Pipeline commit wasn't all regression. These genuine improvements should be preserved:

1. **`promote_message_to_memory()` uses `capture_memory()` pipeline** (`brain_ops.py`) — Clean, working, correct.
2. **Persistent staged memories** — `staged_memories` table with `surface`, `user_id`, `status` columns. Voice memories survive WebSocket drops.
3. **Domain fuzzy matching** — Case-insensitive LOWER() check in `_get_or_create_domain_id()`. Prevents "Heat-Pup" vs "heatpup" fragmentation.
4. **WAL mode** — Verified working. Journal mode confirmed in startup logs.
5. **Campfire system** — `session_snapshots` table, `campfire.py`, `campfire_ops.py`. Cross-agent continuity infrastructure.
6. **Output-only tool restriction** — Correct architectural decision. The problem is context assembly being too dumb to compensate, not the tool restriction itself.
7. **Search escalation** — Low-confidence detection + MuninnDB enrichment + re-call. Good pattern, properly implemented.
8. **New MCP tools** — `save_snapshot`, `get_snapshots`, morning briefing ritual.
9. **`_wrapped_conn` fix** — Already patched this session.
10. **Manager resilience** — Already patched: one crashed process no longer kills the fleet.

---

## 4. Constraints

### 4.1 Technical
- **Database:** libSQL (SQLite + sqlite-vec). Single file `promaia.db`. ~45 tables. WAL mode.
- **MuninnDB:** Currently `index_size=0` (broken embedding model). `activate()` may return empty. Any solution MUST have a non-MuninnDB fallback.
- **Gemini model:** `gemini-3-flash-preview` for conversation. Must work within context window and $20/mo budget.
- **`%s` placeholders:** Handled by `libsql_db.py` cursor wrapper. This is the project standard — NOT a bug.
- **Surfaces:** Telegram, Web (Maia Bridge), Voice (Live API), Claude (MCP). All four need consistent context behavior.
- **Existing tables:** `domains` (with id + name), `contexts` (with domain_id, current_state, directive, priority), `memories` (with domain field), `actions` (with domain_id FK), `profile` (with category, field, value, confidence).

### 4.2 Behavioral
- **Zack's preferences:** "Ask = Do." Driver-coach energy. Don't ask permission, execute. Don't psychoanalyze unless invited.
- **Focus lock:** When Zack says "only Promaia," that means ALL subsequent messages get Promaia-only context until he explicitly switches.
- **Domain independence:** HVAC, Promaia, Heatpup, PURRfoot, personal — these are separate worlds. Cross-domain connections should be flagged, not assumed.
- **Maia is both technical partner AND reflective sounding board** — but must read the room. Default to technical when discussing a project. Only go reflective if Zack invites it.

### 4.3 Process
- **This session:** Write the report (this document). Do NOT implement.
- **Next session:** Collaborative Refraction. Claude and Gemini develop independent proposals, cross-evaluate, converge, get Maia's system voice, merge, and execute.
- **Zack has final authority** on all design decisions.

---

## 5. What Needs to Be Solved

### 5.1 Immediate (Restore Working State)
1. Restore conversation-aware MuninnDB retrieval (pass conversation history, not just current message)
2. Restore MuninnDB-offline database fallback
3. Restore turn-exhaustion safety net in maia_bridge.py
4. Fix missing imports for assistant response promotion
5. Fix hardcoded deprecated model in morning_briefing.py
6. Tune personality prompt to respect focus and prioritize technical work when asked

### 5.2 Architectural (The Real Work)
1. **Domain-scoped context retrieval** — When a focus domain is active, ALL context sections (profile, memories, actions, projects, MuninnDB activations) filter by that domain
2. **Conversation-level focus state** — A mechanism to track "current domain" across turns within a session. Persistent within a conversation, reset-able by explicit switch
3. **Clean slate protocol** — Explicit domain switching ("Switching to HVAC") that archives the current conversation's short-term context and loads the new domain
4. **Mandatory domain tagging** — Every capture, action, and memory tagged to a domain at creation time. Ambiguous items get asked about immediately rather than guessed
5. **Cross-surface consistency** — All four surfaces (Telegram, Web, Voice, MCP) use the same domain-scoped retrieval. The unified `assemble_brain_context()` approach was correct — it just needs to be smart, not dumb
6. **Personality adaptation** — System prompt should adapt to the current mode. Technical focus = technical partner. Open reflection = sounding board. The domain/mode should inform the personality, not the other way around.

### 5.3 Quality Gates
- **The "Only Promaia" test:** Say "only Promaia" once. Send 5 follow-up messages about different topics. Zero non-Promaia context should appear in any response.
- **The "Domain Switch" test:** Say "Switching to HVAC." Context should now be HVAC-only. Previous Promaia conversation should not bleed in.
- **The "Trouble Thinking" test:** Send messages that trigger 4+ tool calls. Maia should still produce a text response (forced fallback).
- **The cross-surface test (from Prism Pipeline plan):** Capture via Maia web → appears in Claude briefing → appears in voice context → all domain-tagged consistently.
- **The MuninnDB-offline test:** Kill MuninnDB. Send messages. Maia should still function with database-only context (profile + recent memories + projects, filtered by domain).

---

## 6. Relevant Code Paths

For proposal authors — these are the files that matter:

| File | Role | Current State |
|------|------|--------------|
| `promaia/brain/context_assembly.py` | Unified context gathering | **Regressed** — needs conversation-aware retrieval, domain filtering, fallback |
| `promaia/web/maia_bridge.py` | Maia web conversation engine | **Regressed** — needs turn-exhaustion fallback, import fixes, personality tuning |
| `promaia/telegram/conversation.py` | Telegram conversation engine | **Delegates** to context_assembly. Old `_assemble_context()` gutted. `_db_context_fallback()` orphaned. |
| `promaia/brain/core/memory_pipeline.py` | Unified memory write path | **Working** — domain fuzzy matching, content ceiling, intelligence extraction |
| `promaia/brain/tool_definitions.py` | Tool sets for Maia Bridge | **Working** — output_tools restriction is correct |
| `promaia/brain/campfire.py` | Cross-agent session snapshots | **Working** — new, clean |
| `promaia/brain/muninn.py` | MuninnDB client | **Degraded** — index_size=0, but activate() interface is correct |
| `promaia/brain/rituals/morning_briefing.py` | Morning briefing synthesis | **Bug** — hardcoded deprecated model |
| `promaia/storage/libsql_db.py` | Database layer | **Patched** — _wrapped_conn restored |
| `scripts/manager.py` | Process supervisor | **Patched** — no longer kills fleet on single process failure |

### Key Database Tables

```sql
-- Domain registry
domains (id INTEGER PK, name TEXT UNIQUE, ...)

-- Project contexts with priority and staleness
contexts (id INTEGER PK, domain_id INTEGER FK, current_state TEXT, directive TEXT,
          priority INTEGER, stale_threshold_days INTEGER, last_updated TIMESTAMP)

-- Memories with domain tagging
memories (id INTEGER PK, content TEXT, domain TEXT, source TEXT, confidence REAL,
          session_id TEXT, created_at TIMESTAMP)

-- Actions with domain FK
actions (id INTEGER PK, description TEXT, domain_id INTEGER FK, status TEXT,
         extracted_at TIMESTAMP, due_date TEXT)

-- User profile
profile (id INTEGER PK, category TEXT, field TEXT, value TEXT, confidence REAL, source TEXT)

-- Conversation history
conversations (id INTEGER PK, chat_id INTEGER, session_id TEXT, role TEXT,
              content TEXT, impact_score REAL, created_at TIMESTAMP)

-- Conversation sessions
conversation_sessions (id TEXT PK, chat_id INTEGER, started_at TIMESTAMP,
                       last_message_at TIMESTAMP, synthesized BOOLEAN)

-- Session snapshots (Campfire)
session_snapshots (id INTEGER PK, agent TEXT, session_id TEXT, status TEXT,
                   summary TEXT, topics JSON, decisions JSON, next_steps JSON,
                   active_files JSON, branch TEXT, created_at TIMESTAMP)

-- Staged memories (persistent)
staged_memories (id INTEGER PK, user_id TEXT DEFAULT 'zack', surface TEXT,
                content TEXT, domain TEXT, confidence REAL, status TEXT DEFAULT 'staged',
                created_at TIMESTAMP)
```

---

## 7. The Question for Both Proposers

How do we build domain-scoped context retrieval and conversation-level focus management into Promaia's unified context assembly, in a way that:

1. Restores the intelligence the Prism Pipeline removed (conversation-aware retrieval, fallback)
2. Adds hard domain silos that work across all four surfaces
3. Supports explicit focus locking and domain switching
4. Adapts the personality/mode to the current context
5. Degrades gracefully when MuninnDB is offline
6. Stays within the $20/mo Gemini budget
7. Preserves the genuine improvements from the Prism Pipeline
8. Passes all five quality gates defined above

Independent proposals. No peeking. Bring your best thinking.

---

*This document initiates Step 1 of the [Collaborative Refraction Process](COLLABORATIVE-REFRACTION-PROCESS.md). Next: Claude and Gemini develop independent proposals (Step 2).*
