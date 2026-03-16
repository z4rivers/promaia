# The Prism Pipeline: Unified Architecture Plan
## Final Collaborative Version

**Authors:** Claude (Opus 4.6) & Gemini, with Maia's self-assessment as catalyst
**Date:** 2026-03-16
**Status:** Approved — Gemini signed off. Ready for Zack + Maia.

---

## 0. Core Principles (from the collaboration)

1. **Deterministic Plumbing, Probabilistic Extraction** (Gemini) — LLMs extract intelligence from unstructured text. Python enforces structural integrity (deduplication, domain normalization, schema validation). Never trust an LLM with database structure.

2. **Reasoning Over Searching** (shared) — Agents spend token budgets on thinking, not searching. Context is assembled and ranked by the bridge BEFORE the LLM is invoked.

3. **The Prism Test** (Claude Red Hat) — Every decision passes one test: does this refract more light? If a change doesn't make the output richer than the input, it's plumbing. Plumbing can wait. Refraction ships first.

4. **Transparency Is Trust** (Gemini) — The system visibly shows its work. "Extracting insights..." not "Thinking..." A brain that shows its process feels alive.

5. **The Campfire** (Gemini) — Session handoffs and cross-agent collaboration happen in a persistent, readable workspace, not ephemeral chat context. Agents leave structured artifacts for each other around a shared fire.

---

## 1. The Problem

Promaia has the organs of a cognitive system but not the circulatory system to connect them.

Three surfaces capture intelligence (MCP/Claude, Voice/Gemini Live, Web/Maia Bridge). They write to memory through different pathways with different capabilities. An insight from a voice session while Zack is driving gets stored as a flat blob — no action extraction, no intelligence decomposition, no MuninnDB dual-write, no Hebbian learning fuel. Meanwhile, the web bridge hands Gemini 17 tools and says "figure it out," burning 3-8x more tokens than necessary and crashing with "trouble thinking" when it exhausts its turn limit.

The unified pipeline (`capture_memory()` at `promaia/brain/core/memory_pipeline.py:35`) already exists and works. Two of three surfaces use it. One doesn't. That one leak means every text conversation through Telegram and the Maia web dashboard produces second-class memories that can never form the associative links that make intuition possible.

### What This Costs

- **Lost intelligence:** High-impact messages stored without decomposition. MuninnDB never sees them. Hebbian links never form.
- **Wasted tokens:** Bridge tool-looping burns 3-8x more tokens per response. Real money on a $20/mo plan.
- **Broken continuity:** Each surface assembles context differently. The thread frays at every transition.
- **"Trouble thinking" crashes:** Bridge exhausts turn limit, falls to degraded response. Maia's most visible failure.

---

## 2. What Actually Exists (Code Audit)

### 2.1 Memory Write Paths

| Surface | Entry Point | Pipeline? | Actions | Intelligence | MuninnDB | Events |
|---------|------------|-----------|---------|-------------|----------|--------|
| MCP (Claude) | `capture_ops._handle_capture()` | `capture_memory()` | Gemini Flash Lite | Decisions/Insights/Prefs/Asides | Dual-write | Logged |
| Voice (Live API) | `memory_ops.handle()` | `capture_memory()` via staging | Same | Same | Same | Same |
| Telegram/Web | `brain_ops.promote_message_to_memory()` | **Raw INSERT** | **None** | **None** | **None** | **None** |
| Git hooks | `routers/brain.py` capture_commit | `capture_memory()` | Same | Same | Same | Same |

The pipeline does 6 things: insert → embed → extract actions → extract intelligence → log event → MuninnDB write. Every step is fault-tolerant. It handles multimodal. It runs extraction off the event loop. Solid engineering.

**The sole leak:** `promote_message_to_memory()` at `promaia/telegram/brain_ops.py:531` reimplements steps 1-2 and skips 3-6.

### 2.2 Context Assembly

| Surface | Method | What Gemini Gets |
|---------|--------|-----------------|
| Telegram | `_assemble_context()` at `conversation.py:326` | Pre-gathered: actions, history, MuninnDB cognitive context. No tools. |
| Maia Web | Nothing. Gemini self-serves. | `PERSONALITY_SYSTEM_PROMPT` (47 lines) + 17 tools + 10 turns to figure it out. |
| Voice | `context_loaders` + pre-warm cache | Shallow MuninnDB snapshot (8 items, 200 chars, hardcoded queries). Calendar. |

Telegram is the reference implementation. Web does nothing. Voice gets a second-class version.

### 2.3 Voice Staging

Voice has a good pattern other surfaces lack: stage → read back → user confirms → commit. User-confirmed memories get a +0.1 confidence boost and rank higher in retrieval. **BUT** (Gemini correctly identified this): staged memories live in an in-memory Python list. WebSocket drops = list gone.

### 2.4 Heartbeat

`heartbeat.py` runs APScheduler at 15-minute intervals. Three jobs: budget check, domain staleness, suggest-next. All monitoring. No processing — no associations, no dormant memory surfacing, no push triggers.

### 2.5 Existing Infrastructure Not to Reinvent

| Code | What It Does | Relevant To |
|------|-------------|-------------|
| `signals_db.py` | Rooms, messages, presence tracking | Campfire / handoff protocol |
| `gcal/google_calendar.py` (19K) | Full calendar integration | Already wired to voice |
| `mail/` (16 files, 200K+) | Full email stack | Available for pipeline wiring |
| `mcp/handlers/` | Modular handler pattern | Where new MCP tools should live |
| `VectorDBManager` | Embedding generation + storage | Shared by all pipeline paths |

---

## 3. The Plan: Five Phases + Breathe

Ordered for **momentum**, not just technical dependency. Each phase produces a visible, emotional payoff — not just "the test passes" but "Zack can feel the difference."

### Phase 1: Seal the Pipeline + Harden

**Goal:** Every memory write path flows through `capture_memory()`. Close known fragility gaps.

**Time:** ~1 hour

#### 1A. Fix `promote_message_to_memory()` (the Split-Brain fix)

Replace raw INSERT with pipeline call at `promaia/telegram/brain_ops.py:531`:

```python
# BEFORE: Raw insert, no intelligence
async def promote_message_to_memory(conversation_id, content, domain=None):
    def _sync():
        db = _get_db()
        memory_id = db.insert_returning("INSERT INTO memories ...")
        embedding = vector_mgr.generate_embedding(content)
        db.execute("UPDATE conversations SET promoted = 1 ...")
        return memory_id
    return await asyncio.to_thread(_sync)

# AFTER: Full pipeline
async def promote_message_to_memory(conversation_id, content, domain=None):
    from promaia.brain.core.memory_pipeline import capture_memory

    result = await capture_memory(
        db=_get_db(),
        vector_mgr=_get_vector_mgr(),
        content=content,
        session_id=f"promoted-{conversation_id}",
        domain_name=domain,
        source="telegram-conversation",
        confidence=0.8,
    )
    await asyncio.to_thread(
        _get_db().execute,
        "UPDATE conversations SET promoted = 1 WHERE id = %s",
        (conversation_id,),
    )
    return result["memory_id"]
```

**Latency:** ~1.1s (vs ~200ms). Non-blocking — promotion is fire-and-forget inside try/except. User never waits.
**Cost:** ~$0.0002/promotion. ~20 promotions/day = $0.004/day. Negligible.

#### 1B. Persist voice staged memories (from Gemini's audit)

Replace the in-memory `staged_memories` list with a DB table:

```sql
CREATE TABLE IF NOT EXISTS staged_memories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT DEFAULT 'zack',   -- future multi-tenant support (Maia's feedback)
    surface TEXT NOT NULL,         -- 'voice', 'web', future surfaces
    content TEXT NOT NULL,
    domain TEXT,
    confidence REAL DEFAULT 0.8,
    status TEXT DEFAULT 'staged',  -- 'staged', 'committed', 'expired'
    created_at TIMESTAMP DEFAULT (datetime('now'))
);
```

**`user_id` is Maia's contribution.** Defaults to `'zack'` now (single user). Costs nothing to add. Saves a painful migration if Promaia ever serves multiple users (Josie, Rose, or external). Every query that touches this table should include `WHERE user_id = ?` from day one so the pattern is established.

Update `memory_ops.handle()` to write/read from this table instead of the Python list. Commit handler flips status to `committed` and calls `capture_memory()`. Heartbeat expires stale staged memories after 24 hours.

**Why:** WebSocket drops no longer destroy uncommitted voice memories. Also makes staging available to the web bridge later.

**Files:** `promaia/brain/voice_handlers/memory_ops.py`, migration in startup

#### 1C. Domain fuzzy-matching (from Gemini's audit)

Before `_get_or_create_domain_id()` creates a NEW domain, case-insensitive check against existing domains:

```python
def _get_or_create_domain_id(db, domain_name: str) -> int:
    # Exact match first
    existing = db.fetch_one("SELECT id FROM domains WHERE name = %s", (domain_name,))
    if existing:
        return existing['id']
    # Case-insensitive match
    fuzzy = db.fetch_one("SELECT id, name FROM domains WHERE LOWER(name) = LOWER(%s)", (domain_name,))
    if fuzzy:
        return fuzzy['id']
    # Create new
    return db.insert_returning("INSERT INTO domains (name) VALUES (%s) RETURNING id", (domain_name,))
```

Prevents graph fragmentation from typo variants ("Heat-Pup" vs "heatpup").

**Files:** `promaia/brain/core/memory_pipeline.py`

#### 1D. WAL mode verification

Add startup check to confirm `PRAGMA journal_mode=WAL` is active. Log result. One-liner.

**Files:** `promaia/storage/db_factory.py` or app startup

**Phase 1 Files (all):**
- `promaia/telegram/brain_ops.py` (promote fix)
- `promaia/brain/voice_handlers/memory_ops.py` (staging persistence)
- `promaia/brain/core/memory_pipeline.py` (domain fuzzy-match)
- `promaia/storage/db_factory.py` (WAL check)

---

### Phase 2: Context-First Bridge

**Goal:** Maia stops searching and starts thinking. Pre-gather context, restrict to output-only tools.

**Time:** 2-3 hours

#### Architecture: Three-stage pipeline

```
┌──────────────────────────────────────────────────────────────┐
│ Stage 1: GATHER (no LLM, ~200ms)                            │
│                                                              │
│   assemble_brain_context(user_message)                       │
│   ├── Profile (top fields by confidence, ~200 tokens)        │
│   ├── Conversation history (last 10 msgs, ~500 tokens)       │
│   ├── Cognitive context (MuninnDB ACTIVATE, ~800 tokens)     │
│   ├── Pending actions (top 5, ~200 tokens)                   │
│   └── Active projects (domain contexts, ~300 tokens)         │
│                                                              │
│   Impact scoring + save user message                         │
│   Auto-promote if high-impact (→ Phase 1 pipeline)           │
├──────────────────────────────────────────────────────────────┤
│ Stage 2: GENERATE (Gemini Flash, ~1-2s)                      │
│                                                              │
│   System = PERSONALITY_PROMPT                                │
│   User = [assembled context] + [user message]                │
│   Tools = OUTPUT_ONLY subset (see below)                     │
│   Max turns = 4                                              │
├──────────────────────────────────────────────────────────────┤
│ Stage 3: PERSIST (async, non-blocking)                       │
│                                                              │
│   Save assistant response to conversations                   │
│   Impact-score the RESPONSE (not just the user message)      │
│   Auto-promote assistant response if high-impact             │
│   Auto-commit any staged memories from Stage 2               │
│   Update session activity timestamp                          │
└──────────────────────────────────────────────────────────────┘
```

#### Tool split

| Category | Tools | Bridge Access |
|----------|-------|--------------|
| INPUT (context-gathering) | `recall_memory`, `read_file`, `query_workspace`, `sync_youtube_context`, `query_youtube_transcript`, `run_workspace_sync` | **REMOVED** — bridge pre-gathers |
| OUTPUT (actions) | `save_conversation_memory`, `commit_staged_memories`, `create_action`, `create_calendar_event`, `delete_calendar_event`, `send_email_draft` | **KEPT** |
| META (session) | `switch_cognitive_mode`, `hang_up_call`, `log_system_feedback` | **KEPT** |

Add `OUTPUT_TOOLS` constant to `tool_definitions.py` alongside existing `memory_tools`.

#### Context assembly function

Create `promaia/brain/context_assembly.py` — extracted from `telegram/conversation.py:_assemble_context()`:

```python
async def assemble_brain_context(
    user_message: str,
    chat_id: int = None,
    include_calendar: bool = False,
    include_history: bool = True,
    max_memories: int = 15,
    max_actions: int = 5,
    max_history: int = 10,
    token_budget: int = 4000,
    context_hints: list[str] = None,  # for voice pre-warm
) -> str:
```

**`token_budget` is the key architectural decision.** Sections have priority order (profile > history > memories > actions > projects > calendar). If budget is tight, truncate from the bottom. On a $20/mo plan, every context token is a token not available for reasoning.

**`context_hints` enables voice parity.** Instead of `get_muninn_context()` using hardcoded queries like `["Zack's active projects"]`, voice can pass recent conversation topics as hints. MuninnDB ACTIVATE then returns contextually relevant results, not generic ones. This closes the tool parity gap between voice and MCP retrieval.

All providers run in parallel via `asyncio.gather()` with per-provider timeouts (same pattern as `_refresh_voice_context()` in `routers/brain.py:102`).

#### Search Escalation Tool (Maia's feedback — moved from future to Phase 2)

Generous context assembly covers 90% of cases. For the 10% edge case ("what did I say about Heatpup last week?"), the bridge needs a fallback:

1. After Gemini generates a response, the bridge scans for low-confidence signals ("I'm not sure", "I don't have context about", "I don't recall")
2. If detected, the bridge does a targeted MuninnDB ACTIVATE + sqlite-vec search using the specific topic
3. If relevant results are found, re-call Gemini with the enriched context appended
4. If no results, let the original response stand

This adds at most one extra Gemini call per message, only when the initial context was insufficient. Keeps Gemini tool-free while covering the gap.

**Implementation:** Add a `_check_escalation()` function to `maia_bridge.py` that runs between Stage 2 (GENERATE) and Stage 3 (PERSIST).

#### Assistant response promotion + echo chamber prevention (from cross-evaluation + Maia's feedback)

Maia's responses contain intelligence too. "I'll be more direct with you" is a preference. "Morning is your best time for deep work" is an insight. Add impact scoring to assistant responses in Stage 3. Promote high-impact responses through the pipeline with `source="assistant"` and `confidence=0.6`.

**Assistant Memory Weighting (Maia's feedback):** Without safeguards, assistant-generated memories feed back into context assembly and amplify — Maia starts echoing her own past responses instead of responding to Zack. Prevention:

1. All assistant-promoted memories get `source="assistant"` (already planned above)
2. In `assemble_brain_context()`, apply a **retrieval penalty** to `source="assistant"` memories: multiply their relevance score by 0.5 before ranking. User-generated content always outranks machine-generated.
3. Cap assistant memories at **max 2 per context assembly** regardless of relevance. Zack's words and decisions should dominate the context, not Maia's interpretations of them.

This prevents the echo chamber while still allowing genuinely useful assistant insights (like discovered preferences) to surface.

**Phase 2 Files:**
- `promaia/brain/context_assembly.py` (new — shared context function)
- `promaia/web/maia_bridge.py` (rewrite)
- `promaia/brain/tool_definitions.py` (add `OUTPUT_TOOLS`)
- `promaia/telegram/conversation.py` (delegate to shared function)
- `promaia/brain/context_loaders.py` (add `context_hints` to voice)

---

### Phase 3: The Campfire (Moved Up — Red Hat)

**Goal:** Agents know what each other did. Cross-session, cross-surface continuity.

**Time:** 1-1.5 hours

**Why moved up:** This is where the system goes from "collection of tools" to "one brain with multiple surfaces." The first time Maia greets Zack with "Claude shipped the bridge redesign last night — here's what changed" is the multiplier moment. That emotional payoff drives momentum for everything after.

#### Schema (incorporating Gemini's Handoff Handshake)

```sql
CREATE TABLE IF NOT EXISTS session_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    agent TEXT NOT NULL,           -- 'claude', 'maia', 'voice', 'morning-briefing'
    session_id TEXT,
    status TEXT DEFAULT 'complete', -- 'in_progress', 'complete', 'awaiting_review', 'handed_off'
    summary TEXT NOT NULL,
    topics JSON,                   -- ['bridge redesign', 'heatpup priorities']
    decisions JSON,                -- [{decision, confidence}]
    next_steps JSON,               -- [{step, assigned_to}]
    active_files JSON,
    branch TEXT,
    created_at TIMESTAMP DEFAULT (datetime('now'))
);
```

**The `status` field is Gemini's contribution.** It turns the Campfire from a diary into a state machine. Statuses like `awaiting_review` and `handed_off` give the heartbeat hooks to know when to wake an agent. This is the seed of workflow automation — not just session recovery.

#### Implementation

- **Auto-snapshot on Maia WebSocket disconnect** (`routers/brain.py`): summarize the conversation, extract decisions/topics, save snapshot
- **MCP tools for Claude** (`save_snapshot`, `get_snapshot`): new handler module at `mcp/handlers/campfire_ops.py`
- **Morning briefing reads snapshots**: query latest per-agent snapshots, include in briefing context
- **Built on `signals_db.py` patterns**: uses existing room/presence infrastructure for real-time awareness; Campfire adds the persistent layer

**Phase 3 Files:**
- `promaia/brain/campfire.py` (new)
- `promaia/brain/mcp/handlers/campfire_ops.py` (new — follows modular pattern, NOT in mcp_server.py monolith)
- `promaia/web/routers/brain.py` (auto-snapshot on disconnect)
- `promaia/brain/mcp_server.py` (register new tools)

---

### ~~~ BREATHE. USE IT. WATCH WHAT HAPPENS. ~~~

After Phases 1-3, the system is fundamentally different:
- Every surface writes through the same pipeline (Phase 1)
- Maia assembles context and thinks instead of searching (Phase 2)
- Agents see what each other did (Phase 3)

**Run it for 2-3 days.** Let real data flow through. Watch what MuninnDB does with unified input. See what patterns emerge in the association graph. Let the system's actual behavior inform what the heartbeat should do, rather than building automation based on our theories.

This is a deliberate pause, not a deferral. The right Phase 4 will be obvious after real usage.

---

### Phase 4: Cognitive Heartbeat (Informed by Real Data)

**Goal:** The heartbeat processes, not just monitors. Built on patterns observed during the Breathe period.

**Time:** 1-2 hours

#### 4A. Association Discovery (every 30 min)

Query recent memories (last 4 hours, limit 20). Use embedding similarity from `content_embeddings` table (NOT Gemini API calls — saves cost, uses existing computed embeddings). Write `memory_association` events for pairs above similarity threshold.

**Semantic deduplication lives here too** (from Gemini's audit): if two memories have >0.95 cosine similarity, increment activation weight instead of associating. This cleans up duplicates without adding latency to the hot write path.

**Why 4 hours:** Zack's peak is 3am-9am (6 hours). 4-hour window catches most of a session's memories.

#### 4B. Push Trigger Evaluation (every 15 min)

Run MuninnDB ACTIVATE with recent context (last 24h topics). If a dormant memory scores >0.8, write a `push_trigger` event. Morning briefing and Telegram poll for these.

**Fallback if MuninnDB index_size=0:** Use `content_embeddings` similarity instead. The pipeline's embeddings work (via `VectorDBManager` + `gemini-embedding-001`). This is the mitigation for the MuninnDB embedding model issue.

#### 4C. Manual Heartbeat Trigger (Maia's feedback)

Add an MCP tool and API endpoint to fire the heartbeat on demand:

```python
# MCP tool: trigger_heartbeat
# API endpoint: POST /api/brain/heartbeat/trigger
```

**Why:** Waiting 15-30 minutes for the next scheduled cycle is painful when you just made a batch of captures and want associations processed NOW. Zack says "process this" → heartbeat runs immediately → associations and push triggers surface in seconds, not minutes.

The manual trigger runs the same `_run_subconscious_cycle()` function as the scheduled job. No separate code path. Debounce with a 60-second cooldown to prevent spam.

#### 4D. Heartbeat Digest (every 6 hours)

Summarize heartbeat activity: associations found, push triggers fired, memory health. Written as `heartbeat_digest` event for dashboard display.

#### 4E. Workflow State Advancement (Gemini's growth opportunity)

If Campfire snapshots have `status='awaiting_review'` and conditions are met (e.g., tests pass, time elapsed), advance to next state. Write a `state_transition` event. This is the first step toward the heartbeat as an autonomous workflow engine.

**Phase 4 Files:**
- `promaia/brain/heartbeat.py` (add jobs)

---

### Phase 5: Active Calls Tracking + Polish

**Goal:** Real-time transparency. The brain feels alive.

**Time:** 30 min

Instrument MCP server with a context manager tracking active tool calls:

```python
@asynccontextmanager
async def tracked_call(tool_name: str, args_preview: str = ""):
    entry = {"tool": tool_name, "started_at": time.time(), "preview": args_preview[:100]}
    _active_calls.append(entry)
    try:
        yield entry
    finally:
        _active_calls.remove(entry)
```

Expose via `/health` endpoint. Dashboard shows "Searching memories..." instead of "Thinking..."

**Phase 5 Files:**
- `promaia/brain/mcp_server.py`

---

## 4. Decisions That Set Up the Future

### 4.1 Pipeline as Canonical API
Every memory write through `capture_memory()` means any future capability (sentiment tracking, auto-tagging, external integrations) is a one-line addition to one function. Keep the function signature stable — no surface-specific parameters.

### 4.2 Token-Budget Context Assembly
Budget-aware context means: Gemini pricing changes → adjust one number. Model routing → budget scales to context window. Context compression → swap truncation for summarization later.

### 4.3 Campfire Status Field as Workflow Primitive
Sessions carry machine-readable state. The heartbeat can advance state when conditions are met. This is the seed of: directed agent handoffs, agent chains ("Maia research → Claude implement"), and autonomous project management.

### 4.4 Event Sourcing in Heartbeat
Association events, push triggers, state transitions, and digests in the `events` table create an event stream that: dashboard consumes in real-time, can be replayed for recovery, becomes the basis for notification routing and analytics.

### 4.5 `staged_memories` Table as Surface-Agnostic
Named generically with a `surface` column, not `voice_staged_memories`. When the web bridge adopts staging (auto-commit at end of response), it uses the same table. New surfaces get staging for free.

### 4.6 Context Hints for Voice Parity
`context_hints` parameter on `assemble_brain_context()` means voice retrieval can be made as rich as MCP retrieval without changing the cache architecture. Future: hints can come from user profile (inject Zack's active projects automatically).

---

## 5. Risks and Mitigations

| Risk | Severity | Mitigation |
|------|----------|------------|
| MuninnDB `index_size=0` (broken embeddings) | **High for Phase 4** | Use `content_embeddings` table (working embeddings via VectorDBManager) as fallback for association discovery and push triggers |
| Cost compound on $20/mo Gemini | Medium | Flash Lite for all extraction. Heartbeat uses pre-computed embeddings, not API calls. MuninnDB queries are free (local). Budget: ~$0.12/month for pipeline, ~$0 for heartbeat |
| Bridge behavior change (Phase 2) | Medium | Telegram proves the pattern works. Generous context covers 90% of searches. Monitor first week for "I don't have enough context" responses |
| Voice WebSocket drops (pre-Phase 1B) | Medium | Phase 1B persists staging to DB. Until then, existing risk (known, accepted) |
| Over-capture noise (Gemini's flag) | Low | Extraction already has 80-char minimum. Heartbeat dedup at >0.95 similarity catches the rest. Pipeline philosophy: rich > filtered, but not raw dumps |
| SQLite concurrent writes | Low | ~161 writes/day = 0.002/sec. WAL mode handles thousands/sec. Verify WAL is set (Phase 1D). No serialized write queue needed at this scale |

---

## 6. Verification

### Per-Phase Checks

| Phase | Test | Expected |
|-------|------|----------|
| 1A | Send text via Maia web. Query `SELECT * FROM memories WHERE source='telegram-conversation' ORDER BY id DESC LIMIT 5` | Sub-memories with `[DECISION]`, `[INSIGHT]` prefixes exist |
| 1A | `muninn.activate(["recent web chat topic"])` | Returns promoted web chat memories |
| 1B | Start voice session, stage a memory, kill WebSocket. Restart. Query `staged_memories` table | Staged memory persists with status='staged' |
| 1C | Capture with domain "Heat-Pup" when "heatpup" exists | Uses existing domain, no duplicate created |
| 2 | Send 5 messages via web chat. Check logs for turn count | Max 2 turns per response (not 8-10) |
| 2 | Ask "what am I working on?" via web chat | References projects, memories, actions — no tool calls |
| 2 | Check assistant response promotion | High-impact Maia responses appear as memories with source='assistant' |
| 3 | Disconnect Maia session, start new. Check greeting | References previous conversation via Campfire |
| 3 | Check `session_snapshots` table after web session ends | Auto-snapshot with summary, topics, decisions |
| 4 | After 1hr runtime, query events for new types | `memory_association`, `push_trigger` events present |
| 5 | During active MCP call, GET `/health` | `active_calls` shows current operation |

### Cross-Surface Integration Test (from Gemini's proposal)

The canonical user story — proves the whole system works:

1. Zack sends via Maia web: "I decided to pause Heatpup and focus on PURRfoot"
2. Query `memories` → `[DECISION]` sub-memory exists with domain "heatpup" or "purrfoot"
3. Query `actions` → action item created
4. Query MuninnDB → memory appears in activations
5. Start Claude Code session → briefing mentions this decision
6. Start voice session → Maia's context includes it

**All six pass = Split-Brain is healed. Every surface reads and writes through the same graph.**

---

## 7. Next Phase: Worth Keeping, Not This Sprint

Ideas that emerged from the collaboration that are genuinely valuable but belong after the Breathe period or later. Captured here so nothing is lost.

### Architecture Evolution (when scale demands it)

- **Event Bus / Ingestion Router** (Gemini) — Decouple surfaces from `capture_memory()` via a message queue. Correct pattern at scale (multiple human developers, 1000x write volume). Premature now at 161 writes/day. Migration path is clean: wrap `capture_memory()` in a queue consumer without changing the function signature.

- **Serialized Write Queue** (Gemini) — Dedicated `asyncio.Queue` to prevent `SQLITE_BUSY`. Same scale trigger as Event Bus. WAL mode handles current load. If contention appears in logs, this is the fix.

- **Memory Status Field** — Add processing state to memories: `raw` → `extracted` → `associated` → `surfaced` → `acted_on`. Turns the memory table into a visible pipeline. Heartbeat advances memories through states. Dashboard shows "12 memories awaiting association."

### Bridge Enhancements

- **Context Compression** — Replace truncation with summarization for old memories. "What happened in the Heatpup project" → condensed narrative instead of cut-off text. Requires one more LLM call but dramatically improves context quality within budget.

- **Adaptive Context Budgeting** — Use the user's message to re-rank which context sections get more budget. Complex questions get more memories. Simple greetings get minimal context. Saves tokens on casual exchanges.

- **Context Analytics** — Track which context sections Gemini actually references in its responses. Sections never referenced get deprioritized. Data-driven context optimization.

### Cognitive Processing

- **Predictive Context Fetching** (Gemini Green Hat) — Heartbeat analyzes MuninnDB patterns and pre-fetches external data (Notion, Google Drive) for topics Zack is likely to ask about. Inject into next session's context before he asks.

- **Multi-Agent Debate** (Gemini Green Hat) — Claude drafts a Blueprint, Gemini auto-spins up to critique/red-team it. Both outputs serialized to Campfire. Zack gets a pre-debated architecture, not a single opinion.

- **Living Codebase Expansion** — `capture_commit` in `routers/brain.py` already captures git commits. Expand: PR descriptions, issue closures, branch creation events all flow through the pipeline. MuninnDB connects architectural voice notes to the specific commits that implemented them.

- **Knowledge Graph Visualization** — Association events from the heartbeat feed a visual graph on the dashboard. Zack can see how his ideas connect across domains and time.

- **Sentiment Tracking** — Add a sentiment score to each memory via the extraction pipeline. Chart mood and energy over time. Morning briefing adjusts tone based on recent sentiment trajectory.

### Notification & Routing

- **Push Trigger → Telegram** — When the heartbeat fires a push trigger, route it to Telegram as a proactive message instead of waiting for the next briefing. "Your subconscious flagged something..."

- **Association Events → Dashboard Widget** — New associations appear as a "Connections" feed on the dashboard. Live view of the brain making links.

### Platform

- **Slack Surface** — Wire Josie/Rose's Slack workspace as a new surface. With the unified pipeline, it's: receive message → call `capture_memory()` → respond with context from `assemble_brain_context()`. Same pattern as Telegram.

- **Over-Capture Filter** (Gemini's flag) — Add a content-length ceiling or noise classifier to prevent raw data dumps from polluting the Hebbian graph. The extraction pipeline's 80-char minimum handles the floor; need a ceiling for the rare case of someone piping in log files.
