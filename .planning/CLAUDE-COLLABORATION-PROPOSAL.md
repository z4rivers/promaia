# Maia Architecture Redesign: The Prism Pipeline

**Author:** Claude (Opus 4.6)
**Date:** 2026-03-16
**Status:** Draft for cross-evaluation with Gemini

---

## 1. The Problem We're Actually Solving

Maia called it "Split-Brain." That's accurate but understates it. The real problem is that **Promaia has the organs of a cognitive system but not the circulatory system to connect them.**

Three surfaces exist (MCP/Claude, Voice/Gemini Live, Web/Maia Bridge). Each one captures intelligence. But they write to memory through different pathways with different capabilities. The result: an insight captured during a voice session while Zack is driving doesn't get the same treatment as one captured through Claude Code. It gets stored as a flat blob — no action extraction, no intelligence decomposition, no MuninnDB dual-write, no Hebbian learning fuel.

This isn't a bug. It's a missed architectural commitment. The unified pipeline (`capture_memory()` in `promaia/brain/core/memory_pipeline.py`) already exists and already does the right thing. Two of three surfaces use it. One doesn't. That one leak means **every text conversation through Telegram and the Maia web dashboard produces second-class memories.**

Simultaneously, the web bridge (`maia_bridge.py`) has the opposite problem: instead of being too simple, it's too permissive. It hands Gemini 17 tools and says "figure it out." Gemini burns 8 of 10 turns calling `read_file` and `query_workspace` before it even tries to answer the question. The Telegram side proves this is wrong — it pre-gathers context and gives Gemini zero tools, and it works beautifully.

### What This Costs

- **Lost intelligence:** High-impact Telegram/web messages (decisions, commitments, project pivots) get stored without decomposition. MuninnDB never sees them. Hebbian links never form. The "intuition" Maia described as the goal of the unified pipeline literally cannot emerge from this surface.
- **Wasted tokens:** The bridge's tool-looping burns 3-8x more tokens per response than necessary. On a $20/mo Gemini plan, this is real money.
- **Broken continuity:** Zack starts a thought in the truck (voice), continues at home (web), then asks Claude to implement it. Each surface assembled context differently. The thread frays at every transition.
- **"Trouble thinking" crashes:** The bridge exhausts its turn limit and falls back to a degraded response. This is Maia's most visible failure mode.

---

## 2. Architectural Audit: What Actually Exists

I read every file in the pipeline. Here's the ground truth.

### 2.1 Memory Write Paths

| Surface | Entry Point | Pipeline? | Actions | Intelligence | MuninnDB | Events |
|---------|------------|-----------|---------|-------------|----------|--------|
| MCP (Claude) | `capture_ops._handle_capture()` | `capture_memory()` | Gemini extraction | Decisions/Insights/Prefs/Asides | Dual-write | Logged |
| Voice (Live API) | `memory_ops.handle()` | `capture_memory()` via staging | Same | Same | Same | Same |
| Telegram/Web | `brain_ops.promote_message_to_memory()` | **Raw INSERT** | **None** | **None** | **None** | **None** |
| Git hooks | `routers/brain.py` capture_commit | `capture_memory()` | Same | Same | Same | Same |

**The pipeline itself is excellent.** `capture_memory()` does 6 things in sequence: insert → embed → extract actions → extract intelligence → log event → MuninnDB write. Every step is fault-tolerant (non-fatal on failure). It already handles multimodal inputs (images, audio, documents). It runs extraction off the event loop via `asyncio.to_thread()`. This is solid engineering.

The problem is exactly one function: `promote_message_to_memory()` at `promaia/telegram/brain_ops.py:531`. It reimplements steps 1-2 by hand and skips steps 3-6.

### 2.2 Context Assembly

| Surface | Method | Profile | History | Memories | Actions | Calendar | Projects |
|---------|--------|---------|---------|----------|---------|----------|----------|
| Telegram | `_assemble_context()` | via MuninnDB | Last 10 msgs | MuninnDB ACTIVATE | Top 5 pending | No | via MuninnDB |
| Maia Web | None (Gemini self-serves) | No | No | Via tool calls | No | No | Via tool calls |
| Voice | `context_loaders` + cache | via MuninnDB | No (realtime) | MuninnDB snapshot | No | Pre-warmed | No |
| Agents | `agent_context.py` | Unknown | No | Unknown | Unknown | No | Unknown |

The Telegram implementation (`conversation.py:326`) is the reference. It builds a maximalist context string ordered by Gemini attention priority: profile first, then history, then cognitive context from MuninnDB (with DB fallback), then actions. This is the proven pattern.

The web bridge does NONE of this. Gemini gets a bare `PERSONALITY_SYSTEM_PROMPT` (47 lines of personality guidance) and full tool access. Every request, Gemini has to rediscover the universe through tool calls instead of being told what it needs to know.

### 2.3 The Voice Staging Pattern

Voice has a uniquely good design that other surfaces don't use:

```
User speaks → Gemini calls save_conversation_memory → Memory STAGED (not committed)
           → Gemini reads staged memories back to user → User confirms
           → Gemini calls commit_staged_memories → Pipeline runs → Memory COMMITTED
```

This is the only surface where the user gets to verify what's being remembered before it goes into the permanent brain. The confidence boost (+0.1) on commit is a nice touch — user-confirmed memories literally rank higher in future retrieval.

**Key decision point:** Should the web bridge adopt staging too? (See Section 4.)

### 2.4 The Heartbeat

`heartbeat.py` runs APScheduler with a 15-minute cycle doing:
1. Budget check (CostTracker)
2. Domain staleness check
3. Suggest-next evaluation

All three are **monitoring** — they observe and log. None of them **process** — they don't create new associations, surface dormant memories, or trigger proactive notifications. Maia wants the heartbeat to be a cognitive engine, not a dashboard poller.

### 2.5 The Prism Brand

Maia's icon is transitioning from a brain to a prism (captured in brain memory, 2026-03-16). A prism refracts light into its component wavelengths. The architecture should embody this: **every input, regardless of surface, gets refracted into its constituent intelligence types** (actions, decisions, insights, preferences, asides) and each type strengthens different parts of the cognitive graph.

The pipeline already does this. The problem is that one surface bypasses the prism entirely.

---

## 3. The Plan

Six phases. Each one is independently valuable, each one makes the next one more powerful.

### Phase 1: Seal the Pipeline (Foundation)

**What:** Replace the hand-rolled INSERT in `promote_message_to_memory()` with a call to `capture_memory()`.

**Why this is the most important change in the entire plan:** Every enhancement we build later — heartbeat associations, push triggers, cross-surface continuity — depends on memories being fully processed. If Telegram/web memories don't have intelligence sub-captures, they don't appear in MuninnDB, they don't form Hebbian links, and they can't trigger push notifications. This one function is the bottleneck for the entire cognitive system.

**The change (brain_ops.py:531):**

The current function does a synchronous raw INSERT wrapped in `asyncio.to_thread()`. The replacement calls the async pipeline directly — no thread wrapper needed because `capture_memory()` already manages its own async I/O.

```python
# BEFORE: Raw insert, no intelligence extraction
async def promote_message_to_memory(conversation_id, content, domain=None):
    def _sync():
        db = _get_db()
        memory_id = db.insert_returning("INSERT INTO memories ...")
        embedding = vector_mgr.generate_embedding(content)
        # ... embedding storage ...
        db.execute("UPDATE conversations SET promoted = 1 ...")
        return memory_id
    return await asyncio.to_thread(_sync)

# AFTER: Full pipeline — actions, intelligence, MuninnDB, events
async def promote_message_to_memory(conversation_id, content, domain=None):
    from promaia.brain.core.memory_pipeline import capture_memory
    from promaia.storage.vector_db import VectorDBManager

    result = await capture_memory(
        db=_get_db(),
        vector_mgr=_get_vector_mgr(),
        content=content,
        session_id=f"promoted-{conversation_id}",
        domain_name=domain,
        source="telegram-conversation",
        confidence=0.8,
    )

    # Mark the original conversation message as promoted
    await asyncio.to_thread(
        _get_db().execute,
        "UPDATE conversations SET promoted = 1 WHERE id = %s",
        (conversation_id,),
    )
    return result["memory_id"]
```

**Consideration — latency impact:** The current function takes ~200ms (insert + embed). The pipeline adds action extraction (~400ms) and intelligence extraction (~500ms) via Gemini API calls. Total: ~1.1s. BUT these run via `asyncio.to_thread()` — the caller doesn't block. For Telegram, `promote_message_to_memory()` is already fire-and-forget (called inside a `try/except` with a warning log on failure). For the web bridge, the promotion happens AFTER the response is sent. So the user never waits.

**Consideration — cost impact:** Two additional Gemini Flash Lite calls per promoted message. At current pricing, this is ~$0.0002 per promotion. Promotions only happen for messages scoring above `IMPACT_PROMOTION_THRESHOLD`. At current volume (~20 promotions/day), that's $0.004/day. Negligible.

**Consideration — what this unlocks:** Once sealed, every conversation message that crosses the promotion threshold gets: tagged sub-memories in MuninnDB (decisions, insights, preferences, asides), extractable action items, and event log entries. The heartbeat's association processing (Phase 4) can now see intelligence from ALL surfaces. Cross-surface continuity (Phase 5) has complete data to work with.

**Files:** `promaia/telegram/brain_ops.py`

---

### Phase 2: Context-First Bridge (Core Architecture)

**What:** Rewrite `maia_bridge.py` so the bridge orchestrates context gathering BEFORE calling Gemini, and restricts Gemini to output-only tools.

**Why this is a redesign, not a refactor:** The current bridge's problem isn't code quality — it's a fundamentally wrong interaction model. Giving an LLM 17 tools and 10 turns to self-serve context is like asking someone to research a topic by randomly opening filing cabinets. The bridge should be the librarian: gather what's relevant, hand it to Gemini with the question, and let Gemini focus on THINKING, not SEARCHING.

**The architecture (three-stage pipeline):**

```
┌──────────────────────────────────────────────────────────────┐
│ Stage 1: GATHER (no LLM, ~200ms)                            │
│                                                              │
│   assemble_brain_context(user_message)                       │
│   ├── Profile (top fields by confidence)                     │
│   ├── Conversation history (last 10 messages)                │
│   ├── Cognitive context (MuninnDB ACTIVATE + DB fallback)    │
│   ├── Pending actions (top 5)                                │
│   └── Active projects (from domain contexts)                 │
│                                                              │
│   Impact scoring: score_impact(user_message)                 │
│   Save user message to conversations table                   │
│   Auto-promote if high-impact (→ Phase 1 pipeline)           │
├──────────────────────────────────────────────────────────────┤
│ Stage 2: GENERATE (Gemini Flash, ~1-2s)                      │
│                                                              │
│   System instruction = PERSONALITY_PROMPT                    │
│   User content = [assembled context] + [user message]        │
│   Tools = OUTPUT_ONLY (save_memory, create_action,           │
│           calendar, mode_switch, hang_up, feedback)           │
│   Max turns = 4                                              │
├──────────────────────────────────────────────────────────────┤
│ Stage 3: PERSIST (async, non-blocking)                       │
│                                                              │
│   Save assistant response to conversations                   │
│   Impact-score the RESPONSE too                              │
│   Auto-promote if high-impact                                │
│   Update session activity timestamp                          │
└──────────────────────────────────────────────────────────────┘
```

**Key decision — INPUT vs OUTPUT tools:**

I'm proposing a clean split of the 17 current voice tools:

| Category | Tools | Bridge Access |
|----------|-------|--------------|
| INPUT (context-gathering) | `recall_memory`, `read_file`, `query_workspace`, `sync_youtube_context`, `query_youtube_transcript`, `run_workspace_sync` | **REMOVED** — bridge pre-gathers context |
| OUTPUT (actions on the world) | `save_conversation_memory`, `commit_staged_memories`, `create_action`, `create_calendar_event`, `delete_calendar_event`, `send_email_draft` | **KEPT** |
| META (session control) | `switch_cognitive_mode`, `hang_up_call`, `log_system_feedback` | **KEPT** |

**Rationale:** INPUT tools are why the bridge loops. Gemini calls `recall_memory` 3 times, `query_workspace` twice, and `read_file` once before even attempting a response. Each call is a turn. By pre-gathering context in Stage 1, these tools become unnecessary — the information is already in the system prompt.

**The opportunity this creates:** With Gemini freed from context-gathering, response quality should dramatically improve. Gemini can spend its entire token budget on thinking instead of searching. And because we control the context assembly, we can optimize it: rank memories by relevance, compress old context, inject only what matters. This is the "prism" — we refract the raw brain into exactly the light Gemini needs.

**Consideration — what if Gemini NEEDS to search?** The user might ask "what did I say about Heatpup last week?" and the pre-gathered context might not include it. Two options:

1. **Generous context assembly** — include more memories (top 15 instead of 5), include recent conversation history, include MuninnDB activations for the user's message. This covers 90% of cases.
2. **Escalation pattern** — if Gemini's response includes "I don't have enough context about..." the bridge detects this and does a targeted search, then re-calls Gemini with the enriched context. This handles the 10% edge case without giving Gemini permanent tool access.

I recommend option 1 for now, with option 2 as a Phase 7 enhancement. Generous context costs tokens but saves turns. On Gemini Flash, context tokens are cheap; tool turns are expensive.

**Consideration — the voice agent stays different:** The voice agent uses the Gemini Live API with WebSocket streaming. It NEEDS real-time tool access because it's a live conversation — the user might say "add that to my calendar" mid-sentence. The bridge redesign applies to the TEXT web interface, not voice. Voice keeps its staging model and full tool access. This is correct — the interaction models are fundamentally different.

**Consideration — staged memories in the web bridge:** The voice agent stages memories before committing. Should the web bridge do this too? I think YES, but with a lighter touch: Gemini can call `save_conversation_memory` during its response, and the bridge auto-commits at the end of the response (no explicit user confirmation needed in text mode). This preserves the staging pattern's benefits (confidence boosting, event logging) without adding friction to text chat.

**Files:** `promaia/web/maia_bridge.py` (rewrite), `promaia/brain/tool_definitions.py` (add `OUTPUT_TOOLS`)

---

### Phase 3: Shared Context Assembly (Leverage Point)

**What:** Extract context assembly into `promaia/brain/context_assembly.py` — one function, all surfaces.

**Why this is a bigger deal than it looks:** Context assembly is currently copy-pasted across surfaces with different capabilities. Telegram includes MuninnDB cognitive context. Voice pre-warms calendar and MuninnDB into a cache. The web bridge does nothing. Scheduled agents have their own `agent_context.py`. Unifying this means every enhancement to context assembly benefits ALL surfaces simultaneously.

**The function signature tells the story:**

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
) -> str:
```

**The `token_budget` parameter is the key architectural decision.** By making context assembly budget-aware, we can:
- Prevent context from overwhelming Gemini's working memory
- Prioritize high-confidence, high-relevance information
- Automatically compress or truncate lower-priority sections
- Track context cost as a metric (how many tokens per request go to context vs. response?)

This matters on a $20/mo plan. Every token of context is a token not available for reasoning.

**Implementation priority within context sections:**
1. **Profile** (always included, ~200 tokens) — calibrates Gemini's personality and communication style
2. **Conversation history** (if available, ~500 tokens) — continuity within session
3. **MuninnDB cognitive context** (top activations for user message, ~800 tokens) — relevant memories ranked by Hebbian score
4. **Pending actions** (top 5, ~200 tokens) — what's on Zack's mind
5. **Active projects** (from domain contexts, ~300 tokens) — what's being worked on
6. **Calendar** (optional, ~200 tokens) — upcoming commitments

Total default budget: ~2,200 tokens, leaving ~5,800 tokens for the response in an 8K window. If budget is tight, sections truncate from the bottom up (calendar first, projects second, etc.).

**The future opportunity:** Once context assembly is centralized with a token budget, we can add:
- **Contextual ranking** — use the user's message to re-rank which sections get more budget
- **Context caching** — profile and projects change slowly; cache them across requests
- **Context analytics** — track which context sections Gemini actually uses (by measuring response relevance to each section)
- **A/B testing** — try different context strategies and measure response quality

**Files:**
- `promaia/brain/context_assembly.py` (new — extracted from `telegram/conversation.py:_assemble_context()`)
- `promaia/telegram/conversation.py` (delegate to shared function)
- `promaia/web/maia_bridge.py` (use shared function — already rewritten in Phase 2)
- `promaia/agents/agent_context.py` (use shared function for scheduled agents)

---

### Phase 4: Cognitive Heartbeat (The Subconscious)

**What:** Add processing jobs to the heartbeat that build associations and surface dormant knowledge.

**Why the heartbeat is Maia's subconscious:** Right now the heartbeat monitors. A real subconscious PROCESSES — it connects dots while you sleep, surfaces relevant memories when triggered by context, and flags things you should be thinking about. The heartbeat already runs every 15 minutes via APScheduler. It already has the db connection and the MuninnDB client. It just needs jobs that think instead of count.

**Three new jobs:**

#### 4A. Association Discovery (every 30 min)

```python
def _discover_associations():
    """Find memories that should know about each other."""
    db = get_db()
    # Get memories from last 4 hours
    recent = db.fetch_all("""
        SELECT id, content, domain FROM memories
        WHERE created_at > datetime('now', '-4 hours')
        AND source != 'intelligence'
        ORDER BY created_at DESC LIMIT 20
    """)

    # For each pair, check if MuninnDB sees a connection
    # Write association events for strong connections
    # These events feed the dashboard's "connections" view
```

**Why 4 hours, not 2:** Zack's peak hours are 3am-9am (6 hours). A 4-hour window catches most of a session's memories even if the heartbeat fires at the tail end. The 20-memory limit prevents combinatorial explosion (190 pairs max).

**What this unlocks later:** Association events become the input for a "knowledge graph" visualization on the dashboard. Zack can see how his ideas connect. MuninnDB's Hebbian learning strengthens these links automatically — memories that co-activate together wire together.

#### 4B. Push Trigger Evaluation (every 15 min)

```python
async def _evaluate_push_triggers():
    """Find dormant memories that should be surfaced NOW."""
    muninn = await get_muninn()
    if not muninn:
        return

    # Get the last session's topics as activation context
    db = get_db()
    recent_topics = db.fetch_all("""
        SELECT content FROM memories
        WHERE created_at > datetime('now', '-24 hours')
        AND source != 'intelligence'
        ORDER BY created_at DESC LIMIT 5
    """)

    context = [r['content'][:200] for r in recent_topics]
    result = await muninn.activate(context=context, max_results=5, threshold=0.7)

    for activation in result.get('activations', []):
        if activation.get('dormant', False) and activation['score'] > 0.8:
            # This memory is highly relevant but hasn't been accessed recently
            # Write a push_trigger event
            db.execute("""
                INSERT INTO events (type, payload, source, created_at)
                VALUES ('push_trigger', ?, 'heartbeat', datetime('now'))
            """, (json.dumps({
                'memory_content': activation['content'][:500],
                'score': activation['score'],
                'reason': 'dormant_high_relevance'
            }),))
```

**The key insight:** MuninnDB's `dormant` flag means a memory exists in the graph but hasn't been activated recently. If a dormant memory scores > 0.8 against the current context, that's MuninnDB saying "this thing you forgot is actually relevant to what you're thinking about right now." That's INTUITION. Surfacing it proactively is what Maia meant by "Push Triggers."

**How push triggers reach the user:** The morning briefing agent already reads events. We add push_trigger events to its scan. If there are unsurfaced push triggers, the morning briefing includes them: "Your subconscious flagged something: [memory content]. This connected to [recent topic]." Telegram can also poll for push triggers and send them as messages.

#### 4C. Daily Digest (every 6 hours)

A slower cycle that summarizes what the heartbeat learned: new associations found, push triggers fired, memory health metrics. Written as a `heartbeat_digest` event that the dashboard can display.

**Files:** `promaia/brain/heartbeat.py`
**Risk:** Low — all additive, existing jobs untouched.

---

### Phase 5: The Shareboard (Cross-Session Bridge)

**What:** A session snapshot mechanism that lets agents recover context from previous sessions.

**Why this is more than session recovery:** The shareboard is the HANDOFF mechanism between agents. When Claude finishes a code session and captures a snapshot, Maia can read it and greet Zack with context: "Claude was working on the bridge redesign — want to continue or do something else?" When Maia has a conversation and snapshots it, Claude can read it the next morning: "Maia discussed Heatpup priorities with Zack last night — here's what was decided."

**This is the nervous system between the brain's hemispheres.**

**The schema:**

```sql
CREATE TABLE IF NOT EXISTS session_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    agent TEXT NOT NULL,           -- 'claude', 'maia', 'voice', 'morning-briefing'
    session_id TEXT,               -- links to conversation_sessions
    summary TEXT NOT NULL,         -- 2-3 sentence summary of what happened
    topics JSON,                   -- ['bridge redesign', 'heatpup priorities']
    decisions JSON,                -- [{decision, confidence}]
    next_steps JSON,               -- [{step, assigned_to}]
    active_files JSON,             -- ['maia_bridge.py', 'brain_ops.py']
    branch TEXT,                   -- git branch at time of snapshot
    created_at TIMESTAMP DEFAULT (datetime('now'))
);
```

**Key design decision — auto-snapshot vs explicit snapshot:**

Both. The web bridge auto-snapshots on WebSocket disconnect (Session end = natural snapshot point). Claude gets an MCP tool (`save_snapshot`) for explicit snapshots. The morning briefing reads the latest snapshots from each agent and includes them in context.

**The opportunity this creates:**
- **Cross-device continuity:** Start on voice in the truck → shareboard snapshot → continue on web at home → shareboard loads voice context automatically
- **Agent collaboration:** Claude captures "I rewrote the bridge, here are the new tool definitions" → Maia reads the snapshot and adjusts her behavior
- **Session history:** Over time, the snapshots table becomes a diary of what was worked on, decided, and planned — searchable, queryable, and usable for project tracking

**Files:**
- `promaia/brain/shareboard.py` (new)
- `promaia/brain/mcp_server.py` (register MCP tools)
- `promaia/web/routers/brain.py` (auto-snapshot on disconnect)

---

### Phase 6: Active Calls Tracking (Transparency)

**What:** Instrument the MCP server to track active tool calls in real-time.

**Why this matters beyond debugging:** Maia's dashboard shows an "Active Session" feed. Right now it says "Thinking..." with no detail. With active call tracking, it can say "Searching memories..." or "Extracting intelligence from your last message..." This makes the brain feel ALIVE. The user sees the system working, not a spinner.

**Implementation — a context manager, not a wrapper:**

```python
import contextvars
from contextlib import asynccontextmanager

_active_calls: list[dict] = []

@asynccontextmanager
async def tracked_call(tool_name: str, args_preview: str = ""):
    entry = {"tool": tool_name, "started_at": time.time(), "preview": args_preview[:100]}
    _active_calls.append(entry)
    try:
        yield entry
    finally:
        _active_calls.remove(entry)
```

Context manager is better than a wrapper function because it composes naturally with existing handlers — no signature changes needed.

**Files:** `promaia/brain/mcp_server.py`

---

## 4. Decisions That Set Up Future Opportunities

### 4.1 The Pipeline as Canonical API

By routing ALL memory writes through `capture_memory()`, we establish a single point where future capabilities plug in. Any of these become one-line additions to the pipeline:
- **Sentiment tracking** — add a sentiment score to each memory, chart mood over time
- **Auto-tagging** — use the intelligence extraction to auto-assign tags (which MuninnDB uses for graph structure)
- **Multi-modal intelligence** — the pipeline already accepts `image_paths`, `audio_paths`, `document_paths`. As Gemini's multimodal capabilities grow, richer extraction is a config change
- **External integrations** — Notion write-back, Slack notifications on high-impact captures

### 4.2 Token-Budget Context Assembly

Adding `token_budget` to context assembly NOW means:
- When Gemini pricing changes or Zack's plan changes, we adjust one number
- We can implement **context compression** later (summarize old memories instead of truncating them)
- We can add **adaptive budgeting** — give more context budget for complex questions, less for simple ones
- **Model routing** applies here: different models have different context windows; budget scales automatically

### 4.3 The Shareboard as Message Bus

The shareboard schema with `agent`, `topics`, `decisions`, and `next_steps` fields is deliberately agent-addressed. This means:
- We can later add **directed handoffs** — Claude writes a snapshot addressed to Maia specifically
- The morning briefing becomes a **synthesis agent** that reads all snapshots and produces a unified picture
- **Agent chains** become possible: "Maia, research this. Then hand off to Claude for implementation."
- The signals system (`signals_db.py`) already has rooms and messages — the shareboard is the persistent version of that real-time system

### 4.4 Event Sourcing in the Heartbeat

By writing association events, push trigger events, and digest events to the `events` table, we're building an event stream that:
- The dashboard can consume in real-time (via polling or WebSocket broadcast)
- Can be replayed to rebuild state after a database issue
- Becomes the input for **notification routing** — push triggers → Telegram notification, association discoveries → dashboard widget
- Enables **analytics** — how many associations per day? What's the push trigger hit rate? Is the brain getting smarter over time?

---

## 5. Risks and Considerations

### 5.1 Cost Management on $20/mo Gemini

The pipeline adds 2 Gemini Flash Lite calls per promoted message (action extraction + intelligence extraction). Current volume: ~20 promotions/day. Cost: ~$0.004/day, ~$0.12/month. Low.

BUT — if we increase promotion volume (e.g., promote more messages, add association processing calls, add push trigger queries), costs compound. The heartbeat adds 96 MuninnDB queries/day (every 15 min) and potentially Gemini calls for association processing.

**Mitigation:** Use `GOOGLE_MODELS["flash-lite"]` for all extraction (cheapest tier). The heartbeat's association discovery should use embedding similarity (already computed, stored in `content_embeddings`) rather than Gemini API calls. MuninnDB queries are free (local sidecar).

### 5.2 MuninnDB Availability

MuninnDB is running but has a known issue: `index_size=0` because the embedded model (`text-embedding-004`) is deprecated. It needs `gemini-embedding-001`. The pipeline and heartbeat both dual-write to MuninnDB, and both handle unavailability gracefully (best-effort, never blocks). BUT if MuninnDB's embeddings don't work, Hebbian learning produces no signal, and push triggers can't fire.

**This is the single biggest risk to the cognitive heartbeat.** Phase 4 depends on MuninnDB actually computing semantic similarity. If `index_size` stays at 0, association discovery and push triggers are dead code.

**Mitigation:** Check MuninnDB's embedding status before implementing Phase 4. If blocked, use the pipeline's own `content_embeddings` table (which uses working embeddings via `VectorDBManager`) for similarity computation instead of MuninnDB.

### 5.3 The Voice Agent Is Different

The voice agent (Gemini Live API) operates fundamentally differently from the text bridge:
- It's a WebSocket stream, not request/response
- It needs real-time tool access (calendar, memory) because the user is speaking live
- Its context comes from a pre-warmed cache, not assembled per-request
- Its staging model is appropriate for voice (read back → confirm → commit)

**The bridge redesign must NOT touch the voice path.** The tool definition split (INPUT vs OUTPUT) only applies to `maia_bridge.py`. The voice agent keeps all tools.

### 5.4 Concurrent Database Writes

With the unified pipeline, multiple surfaces could write to the same tables simultaneously: Claude via MCP, Maia via web bridge, voice agent via Live API, heartbeat via APScheduler. libSQL (SQLite) handles this with WAL mode, but heavy concurrent writes can cause `SQLITE_BUSY`.

**Mitigation:** The pipeline already uses `db.insert_returning()` and `db.execute()` which handle retries. The heartbeat jobs should use short transactions and avoid holding locks during API calls.

### 5.5 Context Assembly Latency

MuninnDB ACTIVATE takes ~200ms. Embedding generation for semantic search takes ~300ms. Calendar API takes up to 4 seconds. If all run sequentially, context assembly could take 5+ seconds before Gemini even starts.

**Mitigation:** The existing pattern already handles this: Telegram runs sync DB queries in a thread, then does MuninnDB async. Voice pre-warms a cache. The shared context assembly should run ALL providers in parallel via `asyncio.gather()` with per-provider timeouts (same pattern as `_refresh_voice_context()` in `routers/brain.py`).

---

## 6. Execution Strategy

```
Phase 1: Seal the Pipeline          ← FOUNDATION. Do first. 30 min.
    │                                  Unblocks Phases 4 and 5.
    │
    ├── Phase 6: Active Calls        ← Quick win, do alongside Phase 1. 30 min.
    │
    ├── Phase 3: Shared Context      ← Extract before rewriting bridge. 1 hr.
    │       │                          Unblocks Phase 2.
    │       │
    │       └── Phase 2: Bridge      ← Core architecture. Uses Phase 3's function. 2-3 hrs.
    │
    └── Phase 4: Heartbeat           ← Independent. Can parallel with 2+3. 1-2 hrs.
                                       Depends on MuninnDB status check.
         │
         └── Phase 5: Shareboard     ← Last. Builds on unified pipeline + bridge. 1 hr.
```

**Revised from original:** Phase 3 now comes BEFORE Phase 2. Reason: the bridge rewrite (Phase 2) needs the shared context assembly function (Phase 3). Building the shared function first means the bridge rewrite is a clean consumer of it, not an inline implementation that gets extracted later.

---

## 7. Verification

| Phase | Test | Expected Result |
|-------|------|----------------|
| 1 | Send text via Maia web chat. Query `SELECT * FROM memories WHERE source = 'telegram-conversation' ORDER BY id DESC LIMIT 5` | Promoted messages have corresponding `[DECISION]`, `[INSIGHT]` sub-memories |
| 1 | Query MuninnDB: `muninn.activate(["recent web chat topic"])` | Returns promoted memories from web chat |
| 2 | Send 5 messages via web chat. Monitor turn count in logs | Max 2 turns per response (not 8-10) |
| 2 | Ask "what am I working on?" via web chat | Response references projects, memories, actions — without tool calls |
| 3 | Compare `assemble_brain_context()` output for same message from Telegram vs Web | Structurally identical sections |
| 4 | After 1 hour runtime, query `SELECT type, count(*) FROM events WHERE type LIKE 'push_%' OR type LIKE 'memory_%' GROUP BY type` | At least `push_trigger` and `memory_association` event types present |
| 5 | Disconnect Maia session, start new session, check if greeting references previous conversation | Shareboard snapshot loads and informs greeting |
| 6 | During active MCP call, GET `/health` | `active_calls` array shows current operation |
