# ZBRAIN.md -- zBrain Changes & Architecture

## What is zBrain?

zBrain is a personal AI operating system built on top of Promaia. It adds a persistent brain layer (semantic memory, autonomous agents, personal profile, proactive briefings), a Telegram interface with voice and conversational AI, a web dashboard, event-driven notification routing, and cost-optimized model routing via Gemini. All changes are additive or confined to the `brain.*` Postgres schema. Existing Promaia features are preserved.

---

## Table of Contents

1. [Module Overview](#module-overview)
2. [Modified Promaia Code](#modified-promaia-code)
3. [Architecture](#architecture)
4. [Current Capabilities](#current-capabilities)
5. [Database Schema](#database-schema)
6. [Agent System](#agent-system)
7. [Event Bus & Notifications](#event-bus--notifications)
8. [Telegram Bot](#telegram-bot)
9. [Web Dashboard](#web-dashboard)
10. [Cost Tracking & Model Routing](#cost-tracking--model-routing)
11. [Onboarding & Profile](#onboarding--profile)
12. [MCP Server (Brain Tools)](#mcp-server-brain-tools)
13. [In Progress](#in-progress)
14. [Phase History](#phase-history)

---

## Module Overview

### New modules (zBrain created)

| Module | Files | Purpose |
|--------|-------|---------|
| `promaia/brain/` | 8 files + `channels/` (6 files) | Core brain: MCP server, memory engine, action extraction, onboarding, Gmail ingest, MuninnDB client, schema, seeder |
| `promaia/telegram/` | 8 files + `handlers/` (5 files) | Telegram bot: auth, brain ops, conversation engine, voice transcription, formatting, notification channel |
| `promaia/events/` | 5 files | Event bus: emitter, router, rate limiter, channel abstraction, data models |
| `promaia/agents/` (new files) | 5 files | Model router, cost tracker, budget guard, Gemini executor, agent context |
| `promaia/web/routers/dashboard.py` | 1 file | Dashboard routes serving brain data |
| `promaia/web/templates/` | 6 HTML files | Jinja2 templates for dashboard, projects, email, profile, login |
| `promaia/web/static/skins/` | 1 CSS file | Superflat skin (CSS custom properties) |
| `prompts/agent_*.md` | 3 files | System prompts for morning-briefing, email-triage, evening-digest |
| `CLAUDE.md` | 1 file | Session instructions for Claude: auto-briefing, ambient capture, onboarding, relational principles |
| `scripts/migrate_embeddings.py` | 1 file | One-time re-embedding migration for pgvector |

### `promaia/brain/` detail

| File | Lines | Purpose |
|------|-------|---------|
| `mcp_server.py` | ~2000 | FastMCP server exposing 16 tools over stdio. Queries Postgres directly. |
| `engine.py` | ~420 | Deterministic brain logic: mode detection, guardrails, time tracking, staleness scoring. No LLM calls. |
| `schema.sql` | ~355 | 13 tables in `brain` schema (memories, domains, contexts, actions, reviews, events, profile, modes, onboarding_sessions, onboarding_progress, timeline, agent_costs, conversations, conversation_sessions). |
| `extraction.py` | ~150 | Extracts actionable items from text via Gemini Flash + instructor (Pydantic structured output). |
| `onboarding.py` | ~200 | State machine for multi-session onboarding: start, pause, resume, complete. |
| `gmail_ingest.py` | ~200 | Syncs Gmail messages into `gmail_content` table via OAuth. Includes `resync_missing_bodies()`. |
| `muninn.py` | ~150 | REST client for MuninnDB cognitive memory server. Dual-write pattern (Postgres primary, MuninnDB best-effort). |
| `seed.py` | ~100 | Idempotent seeder: 10 life domains, 5 project contexts with standing directives. |

### `promaia/brain/channels/` detail

| File | Purpose |
|------|---------|
| `question_bank.py` | 16 interview questions across 9 categories, phase-ordered from warm-up to commitment. |
| `interview.py` | Selects next question based on profile coverage gaps. |
| `pc_scan.py` | Scans local machine for git repos, file structure, installed apps. Stores inferences as profile traits. |
| `gmail_read.py` | Scans Gmail for contacts, communication patterns, topic clusters. Stores summaries only. |
| `gmail_cleanup.py` | Gmail account cleanup utilities. |

### `promaia/telegram/` detail

| File | Purpose |
|------|---------|
| `bot.py` | Dispatcher setup, middleware + router registration, polling with BackoffConfig (auto-reconnect). |
| `auth.py` | WhitelistMiddleware: silently drops messages from non-whitelisted Telegram chat IDs. |
| `brain_ops.py` | 11+ async brain operations (get_briefing, capture_memory, search_brain, get_actions, get_projects, conversation CRUD). Wraps Postgres queries in `asyncio.to_thread()`. |
| `conversation.py` | Gemini 3 Flash conversation engine: context assembly, personality system prompt, impact scoring, memory promotion. |
| `formatting.py` | Telegram-safe message splitting at 4096 char limit. |
| `channel.py` | TelegramChannel implementing NotificationChannel ABC for event delivery from the event bus. |
| `handlers/commands.py` | /start, /briefing, /search, /capture, /projects, /actions command handlers. |
| `handlers/messages.py` | Catch-all free-text handler with domain detection and auto-capture. |
| `handlers/voice.py` | Voice note download, Deepgram Nova-3 transcription, auto-capture pipeline. |
| `handlers/replies.py` | Inline reply handler for push notifications with context capture. |

### `promaia/events/` detail

| File | Purpose |
|------|---------|
| `models.py` | Urgency enum (interrupt/digest/archive) and frozen Event dataclass. |
| `emitter.py` | `emit_agent_events()` with deterministic agent-to-urgency mapping. Non-fatal (never crashes agent pipeline). |
| `router.py` | EventRouter: 30-second polling loop, quiet hours (9pm-6am ET), priority ordering, channel dispatch. |
| `channels.py` | NotificationChannel ABC and DashboardChannel implementation. |
| `rate_limiter.py` | SQL-backed sliding window: 10/hour cap, 30-min cooldown, interrupt bypass, DB-backed state. |

### `promaia/agents/` new files

| File | Purpose |
|------|---------|
| `model_router.py` | TaskType enum, ModelConfig dataclass, MODELS registry, TASK_MODEL_MAP, AGENT_MODEL_MAP, fallback chain. |
| `cost_tracker.py` | CostRecord dataclass, CostTracker with `log_call()`, `compute_cost()`, `get_daily_summary()`. Logs to `brain.agent_costs`. |
| `gemini_executor.py` | GeminiExecutor wrapping `google.genai` with per-call cost logging and automatic model fallback. |
| `budget_guard.py` | BudgetGuard (per-run $0.50, daily $2.00 caps) and RunawayDetector (iteration + cost + output similarity checks). |
| `agent_context.py` | AgentContext dataclass with `load_from_brain()` (batched context loader) and `get_agent_tools_docs()` (per-agent tool injection). |

---

## Modified Promaia Code

These are changes to existing Promaia files. Each entry describes what changed and how to re-implement independently.

| File | Change | Reason |
|------|--------|--------|
| `storage/files.py` | Added Postgres fallback in `load_content_by_page_ids` for Gmail entries; fixed `row[0]` -> `row['thread_id']` KeyError; replaced emoji prints with ASCII for Windows | Gmail content loads from Postgres when .md files are absent |
| `storage/vector_db.py` | Replaced ChromaDB with pgvector. Vector search uses `<=>` operator with HNSW index. | Cloud-native vectors in same DB |
| `storage/db_init.py` | Added brain schema initialization: runs `brain/schema.sql` during startup | Create brain tables alongside public schema |
| `storage/postgres_db.py` | Connection targets Supabase session pooler via `DATABASE_URL` | Cloud-native, accessible from anywhere |
| `storage/hybrid_storage.py` | Replaced B-tree with GIN index on `gmail_labels` (JSONB); added column type docs; `unified_content` view uses `jsonb_build_object` | Fix SQL type mismatches |
| `chat/interface.py` | Added `GeminiModelAdapter` (~80L) wrapping new `google-genai` Client with old `GenerativeModel` interface | Avoid rewriting 3+ callers in 8700-line file |
| `ai/*.py` (5 files) | Updated `google.generativeai` -> `google.genai` imports | Old SDK deprecated (EOL Aug 2025) |
| `agents/executor.py` | Added brain context injection, Gemini execution path, event emission hook, model routing, budget guard integration | Core agent pipeline wiring |
| `agents/scheduler.py` | Added time-of-day scheduling, direct Telegram push, budget check, event router task, Gmail check loop | Proactive agent pipeline |
| `connectors/gmail_connector.py` | Fixed OAuth token refresh persistence | Token wasn't being written back after renewal |
| `requirements.txt` | Added: `psycopg2-binary`, `pgvector`, `google-genai`, `httpx`, `instructor`, `aiogram`, `jsonref` | New dependencies |

### Untouched Promaia code (used as-is)

`chat/` (10,900L), `mail/` (5,600L), `notion/` (2,250L), `gcal/` (540L), CLI, `web/routers/chat+mcp+nodes`

---

## Architecture

```
                         +------------------+
                         |   Claude Code    |
                         |   (MCP Client)   |
                         +--------+---------+
                                  |
                           MCP (stdio)
                                  |
                         +--------v---------+
                         |  Brain MCP       |
                         |  Server (16      |
                         |  tools)          |
                         +--------+---------+
                                  |
                    +-------------+-------------+
                    |                           |
           +--------v---------+       +--------v---------+
           |   Postgres       |       |   MuninnDB       |
           |   (Supabase)     |       |   (cognitive     |
           |                  |       |    sidecar)       |
           |  brain.* schema  |       |   localhost:8475  |
           |  public.* schema |       +------------------+
           +--------+---------+
                    |
        +-----------+-----------+
        |           |           |
+-------v--+ +-----v----+ +----v-------+
| Agent     | | Event    | | Web        |
| Scheduler | | Router   | | Dashboard  |
| (Gemini)  | | (30s     | | (FastAPI + |
|           | |  poll)   | |  Jinja2)   |
+-+---+---+-+ +----+-----+ +------------+
  |   |   |        |
  |   |   |   +----v-----+
  |   |   |   | Telegram  |
  |   |   |   | Channel   |
  |   |   |   +----+------+
  |   |   |        |
  |   |   +--------+
  |   |
  v   v
+-----+------+    +-----------+
| Morning    |    | Telegram  |
| Briefing   |    | Bot       |
| Email      |    | (aiogram) |
| Triage     |    |           |
| Evening    |    | Commands  |
| Digest     |    | Voice     |
+------------+    | Chat      |
                  +-----------+
```

### Data flow

1. **Capture:** User input (Claude Code, Telegram, agents) -> `brain.memories` (+ optional MuninnDB dual-write)
2. **Embed:** Memories get `gemini-embedding-001` vectors (768 dims) stored in pgvector column
3. **Retrieve:** Semantic search via HNSW index (`<=>` cosine distance) or keyword search on tags/entities
4. **Inject:** Agent context loader batches profile, actions, projects, memories into a single prompt block
5. **Execute:** Agents run via Gemini Flash, producing structured output
6. **Emit:** Agent output -> `emit_agent_events()` -> `brain.events` with urgency classification
7. **Route:** EventRouter polls every 30s, respects quiet hours and rate limits, dispatches to channels
8. **Deliver:** Dashboard badge (polling), Telegram push (direct message), or held for morning

---

## Current Capabilities

- **Brain MCP server** with 16 tools callable from Claude Code: briefing, capture, search, recall, context, update_context, actions, profile, update_profile, onboard, pc_scan, gmail_scan, activate, timeline, gmail_query, brain_costs
- **3 autonomous agents** (morning-briefing at 6:00 AM, email-triage at 8h intervals + on-demand, evening-digest at 4:30 PM) running on Gemini 3 Flash at ~$0.01/cycle
- **Telegram bot** with text commands (/briefing, /search, /capture, /projects, /actions), free-text auto-capture, voice note transcription (Deepgram Nova-3), and inline reply handling
- **Conversational AI** via Telegram using Gemini 3 Flash with maximalist context injection (profile + history + memories + projects + actions)
- **Event bus** with Postgres-backed polling, 3 urgency tiers (interrupt/digest/archive), quiet hours (9pm-6am), rate limiting (10/hour), and pluggable channel architecture
- **Push notifications** to Telegram for scheduled agent output and urgent events
- **Web dashboard** (FastAPI + Jinja2) showing live brain data: memories, actions, projects, email summaries, profile traits. Superflat CSS skin. Notification badge with 60s polling.
- **Cost tracking** with per-call logging to `brain.agent_costs`, daily/weekly summaries via `brain_costs` MCP tool, per-run ($0.50) and daily ($2.00) budget caps
- **Model routing** via TASK_MODEL_MAP and AGENT_MODEL_MAP with automatic fallback chain
- **Onboarding system** with ambient interview (16 questions), PC scan, Gmail scan channels. 98 profile traits captured.
- **Gmail ingestion** pipeline syncing messages into Postgres with OAuth, including body resync
- **Semantic memory** with pgvector HNSW indexes for approximate nearest neighbor search

---

## Database Schema

All tables live under a `brain` Postgres schema. Applied idempotently via `apply_brain_schema()`.

| Table | Purpose | Key columns |
|-------|---------|-------------|
| `brain.memories` | Persistent memory store with semantic embeddings | content, summary, domain, tags[], entities JSONB, embedding vector(768) |
| `brain.domains` | Life categories (hierarchical via parent_domain) | name, description, is_project |
| `brain.contexts` | Standing directives per domain/project | directive, current_state, priority, stale_threshold_days |
| `brain.actions` | Extracted actionable items | description, status (pending/done/stale), memory_id, domain_id |
| `brain.reviews` | Periodic review summaries | period_start, period_end, summary, projects_touched JSONB |
| `brain.events` | Event log + notification routing | type, payload JSONB, urgency (interrupt/digest/archive), routed_at, channel, held_until |
| `brain.profile` | Key-value profile traits with confidence scoring | category, field, value JSONB, confidence, source (declared/inferred/confirmed), embedding |
| `brain.modes` | Session mode tracking | mode (working/planning/capturing/reviewing), context_snapshot JSONB |
| `brain.onboarding_sessions` | Onboarding session lifecycle | status (active/paused/complete), metadata JSONB |
| `brain.onboarding_progress` | Per-channel progress within onboarding | channel, status, fields_populated |
| `brain.timeline` | Biographical anchors and life events | event_date, date_precision, title, category, significance |
| `brain.agent_costs` | Per-API-call cost tracking | agent_name, model_id, input/output/cached/thinking tokens, cost_usd |
| `brain.conversations` | Ephemeral session message history | chat_id, session_id, role, content, impact_score, promoted |
| `brain.conversation_sessions` | Session lifecycle and synthesis state | chat_id, session_id, message_count, synthesized |

Indexes: HNSW on embedding columns, GIN on tags/entities/labels, B-tree on timestamps and foreign keys, partial index on unrouted events.

---

## Agent System

Three agents configured in `promaia.config.json`, running via `AgentScheduler`:

| Agent | Schedule | Model | Purpose |
|-------|----------|-------|---------|
| `morning-briefing` | Daily at 06:00 ET | Gemini 3 Flash | Calendar + priorities + brain state. Pushed to Telegram. |
| `email-triage` | Every 480 min (safety net) + on-demand via Gmail check loop | Gemini 3 Flash | Classify emails, surface urgent items. Interrupt events for action-needed. |
| `evening-digest` | Daily at 16:30 ET | Gemini 3 Flash | Day recap, momentum, suggestions for rest of day. Pushed to Telegram. |

Each agent prompt contains:
1. **Grounding Rules** (top, overrides all): no hallucination, no fabricated data, explicit empty-state reporting
2. **Tool injection placeholder**: per-agent MCP tool documentation
3. **Context tier** (bottom, dynamic): few-shot examples, data instructions

Agent output is pushed directly to Telegram for scheduled runs. Events are emitted to `brain.events` with atomic pre-routing to prevent double delivery.

---

## Event Bus & Notifications

The event pipeline uses Postgres polling (no external message broker):

1. `emit_agent_events()` writes to `brain.events` with deterministic urgency mapping
2. `EventRouter` polls every 30 seconds for `WHERE urgency IS NOT NULL AND routed_at IS NULL`
3. Quiet hours (9pm-6am ET): non-interrupt events held until 6am
4. Rate limiting: 10/hour, 30-min cooldown for non-urgent, interrupt bypasses all limits
5. Channels: DashboardChannel (marks routed), TelegramChannel (sends message). Pluggable via ABC.
6. Dashboard shows unread badge (60s JS polling), clears on visit

---

## Telegram Bot

Built with aiogram 3.x. Runs as a persistent daemon with auto-reconnect (BackoffConfig).

- **Security:** WhitelistMiddleware checks chat IDs from `TELEGRAM_WHITELIST` env var. Non-whitelisted messages silently dropped.
- **Commands:** /start, /briefing, /search, /capture, /projects, /actions
- **Free text:** Auto-captured to brain with domain detection
- **Voice:** Deepgram Nova-3 transcription (OGG Opus native), auto-capture
- **Replies:** Inline replies to push notifications captured with original context
- **Conversation:** Gemini 3 Flash with maximalist context assembly (profile, history, memories, projects, actions). Two-tier memory: conversations (ephemeral) -> memories (permanent, via impact scoring).
- **CLI:** `python -m promaia.telegram_cli start|stop|status`

---

## Web Dashboard

FastAPI routes in `promaia/web/routers/dashboard.py` serving Jinja2 templates:

| Route | Template | Content |
|-------|----------|---------|
| `/` | `dashboard.html` | Memory feed, action items, notification badge |
| `/projects` | `projects.html` | Project cards from `brain.contexts` |
| `/email` | `email.html` | Gmail summaries from `gmail_content` |
| `/profile` | `profile.html` | Profile traits by category |

Superflat skin (`superflat.css`): CSS custom properties design system. All visual theming via `--var` properties.

---

## Cost Tracking & Model Routing

- **ModelRouter:** Maps 7 task types and 3 agents to Gemini models. Fallback chain: flash-lite -> flash -> pro.
- **CostTracker:** Logs every API call to `brain.agent_costs` with model, tokens, cached tokens, thinking tokens, USD cost.
- **BudgetGuard:** Per-run cap ($0.50), daily cap ($2.00). Checked before each agent run in scheduler.
- **RunawayDetector:** Triple-check: iteration count, cumulative cost, and word-set Jaccard overlap for repetitive output.
- **MCP tool:** `brain_costs` returns formatted daily/weekly cost table.
- **Cost baseline:** Full 3-agent cycle costs ~$0.01 on Gemini 3 Flash (91% reduction from $0.132 Claude baseline).

---

## Onboarding & Profile

- **Interview:** 16 questions across 9 categories (identity, cognitive style, energy, emotions, values, communication, work, relationships, neurodivergence). Ambient -- surfaced via briefing each session.
- **PC scan:** Scans git repos, file structure for work pattern inferences.
- **Gmail scan:** Analyzes email for contacts and communication patterns.
- **Profile storage:** Key-value in `brain.profile` with confidence scoring, source tracking (declared/inferred/confirmed), and semantic embeddings.
- **Current state:** 98 profile traits captured.

---

## MCP Server (Brain Tools)

16 tools registered in `promaia/brain/mcp_server.py`:

| Tool | Purpose |
|------|---------|
| `briefing` | Morning briefing with stale projects, pending actions, profile coverage, interview question |
| `capture` | Store a memory with embedding, domain detection, action extraction |
| `search` | Semantic + keyword search across memories |
| `recall` | Retrieve specific memory by ID |
| `context` | Get current state and standing directive for a project |
| `update_context` | Update project state or directive |
| `actions` | List pending/done/stale actions, optionally filtered by domain |
| `profile` | Load full user profile grouped by category |
| `update_profile` | Add or update a profile trait |
| `onboard` | Control onboarding: next_question, channel_update, start, complete |
| `pc_scan` | Scan local machine for personality signals |
| `gmail_scan` | Scan Gmail for contacts and communication patterns |
| `gmail_query` | Query Gmail content stored in Postgres |
| `activate` | Activate MuninnDB cognitive retrieval |
| `timeline` | Query biographical timeline events |
| `brain_costs` | Daily/weekly cost summary from agent_costs table |

---

## In Progress

### Phase 11: Conversational Telegram Bot

Replaces the command-response pattern with real conversation. Status: Plan 01 complete, Plan 02 (handler integration) in progress.

**Completed:**
- `brain.conversations` and `brain.conversation_sessions` tables
- Six async conversation CRUD functions in `brain_ops.py`
- `conversation.py`: Gemini 3 Flash conversation engine with maximalist context assembly, personality system prompt (condensed from 126-line manifest), heuristic impact scoring (5 dimensions, 2-signal minimum for promotion)

**Remaining:**
- Handler integration: wire `generate_response()` into `handlers/messages.py` and `handlers/voice.py`
- Synthesis timer: hybrid trigger (N minutes silence OR M messages) producing summary memories
- Retrospective meaning-check: upgrade earlier message significance when later context changes meaning

### Phase 9 Plan 02: Proactive Push Completion

Planned but not yet executed:
- Lightweight Gmail API check loop (60s polling for sub-minute email detection)
- Rate limiter daily cap and cross-channel dedup
- Inline reply handler integration

### Phase 10: MuninnDB Integration

Research and plan complete (`10-MUNINNDB-SUCCESS-PLAN.md`). Not yet implemented. Depends on MuninnDB embedding provider resolution (currently blocked on deprecated text-embedding-004).

---

## Phase History

| Phase | Name | Status | Key Deliverable |
|-------|------|--------|-----------------|
| 1 | Postgres Foundation | Complete | Supabase + pgvector replacing ChromaDB, google-genai SDK migration |
| 2 | Brain Schema | Complete | 7 core brain tables, MCP server, memory engine |
| 3 | Onboarding Module | Complete | Interview system, PC scan, Gmail scan, profile storage |
| 4 | Platform Activation | Complete | Agent scheduler, Gmail OAuth, dashboard wiring |
| 5 | Validate & Activate | Complete | Gmail content pipeline fix, agent prompt hardening, end-to-end validation |
| 6 | Waste Elimination | Complete | Model routing (Gemini), cost tracking, budget guard, 91% cost reduction |
| 7 | Event Bus | Complete | Postgres event routing, urgency tiers, quiet hours, rate limiting, dashboard badge |
| 8 | Telegram Bot | Complete | aiogram bot, brain commands, voice transcription, notification channel |
| 9 | Proactive Push | Partial | Time-of-day scheduling, direct Telegram push (Plan 01). Gmail polling + reply handler planned (Plan 02). |
| 10 | Memory Polish | Planned | MuninnDB cognitive-first architecture. Research complete. |
| 11 | Conversational Telegram | In Progress | Gemini conversation engine, two-tier memory, impact scoring |

---

## Branch & Infrastructure

- **Branch:** `zbrain` (base: `feature/agent-scheduler`)
- **Database:** Supabase Postgres with pgvector
- **LLM for agents:** Gemini 3 Flash (via `google-genai` SDK)
- **LLM for conversation:** Gemini 3 Flash (direct API)
- **LLM for Claude sessions:** Claude (via Max subscription, MCP)
- **Voice transcription:** Deepgram Nova-3
- **Bot framework:** aiogram 3.x
- **Web framework:** FastAPI + Jinja2
- **Embeddings:** gemini-embedding-001 (768 dims)

---

*Last updated: 2026-03-07*
