# zBrain (Promaia Fork)

## What This Is

A personal AI operating system built on top of Promaia. zBrain extends Josie's platform with a persistent brain layer (semantic memory, autonomous agents, personal profile, proactive briefings) and cloud-native storage. The system remembers everything, keeps projects moving, and reaches Zack through his phone.

## Core Value

A proactive AI assistant that reaches YOU -- not a dashboard you check, but a system that initiates, remembers, and acts autonomously while you're walking the dog.

## Current State (v1.0 shipped 2026-03-06)

Foundation live: Postgres+pgvector, brain MCP server (15 tools), onboarding (98 traits), MuninnDB sidecar, 3-agent scheduler, web dashboard. Agents run successfully via Claude SDK ($0.011/run). No mobile access yet. No cost optimization yet.

## Promaia vs zBrain Attribution

**This section tracks what's native Promaia vs what zBrain added. Full tables in `.planning/milestones/v1.0-ROADMAP.md`.**

### New modules (zBrain created):

- **`promaia/brain/mcp_server.py`** (~800L) -- FastMCP server exposing 15 tools (briefing, capture, search, recall, context, update_context, actions, profile, update_profile, onboard, pc_scan, gmail_scan, activate, timeline, gmail_query) over stdio. Each tool queries Postgres directly and returns structured results for Claude to use in conversation.

- **`promaia/brain/engine.py`** (~420L) -- Deterministic brain functions: mode detection (build/research/chat/capture), guardrails (max commits per cycle, budget caps), time/session tracking, context save/restore, project staleness scoring. No LLM calls — pure logic.

- **`promaia/brain/schema.sql`** (~200L) -- Seven tables in a `brain` schema: `memories` (text + vector(768) with HNSW index), `domains` (hierarchical life categories), `contexts` (per-project standing directives with stale thresholds), `actions` (extracted tasks with status tracking), `reviews` (periodic self-assessment), `events` (audit log), `modes` (session state). All with GIN indexes on tags/entities.

- **`promaia/brain/extraction.py`** (~150L) -- Extracts actionable items from free text using Gemini Flash + instructor (Pydantic structured output). Identifies commitments, deadlines, and tasks from natural conversation and stores them as tracked actions.

- **`promaia/brain/onboarding.py`** (~200L) -- State machine for multi-session onboarding: start, pause, resume, complete. Tracks which channels have run (interview, PC scan, Gmail scan, photos) and overall profile coverage percentage. Designed for short bursts that save progress automatically.

- **`promaia/brain/channels/question_bank.py`** -- 16 interview questions across 9 categories (identity, cognitive style, energy, emotions, values, communication, work, relationships, neurodivergence), phase-ordered from warm-up to commitment. Each question maps to specific profile fields it fills.

- **`promaia/brain/channels/interview.py`** -- Selects the next question based on profile coverage gaps. Prioritizes categories with the lowest fill rate so the interview adapts to what's already known.

- **`promaia/brain/channels/pc_scan.py`** -- Scans local machine for personality signals: git repos (languages, commit patterns, project names), file structure, installed apps, desktop state. Extracts inferences about work patterns and interests, stores as profile traits with source="inferred".

- **`promaia/brain/channels/gmail_read.py`** -- Scans Gmail inbox for contacts, communication patterns, and topic clusters. Builds relationship map (who you email most, when) and interest signals. Stores summaries only — no raw email content in profile.

- **`promaia/brain/muninn.py`** (~150L) -- REST client for MuninnDB cognitive memory server (localhost:8475). Implements dual-write pattern: every brain.capture writes to both Postgres (primary, always succeeds) and MuninnDB (best-effort, never blocks). MuninnDB adds Hebbian association strengthening, temporal decay, and graph-based retrieval that pgvector alone can't do.

- **`promaia/brain/gmail_ingest.py`** (~200L) -- Syncs Gmail messages into a `gmail_content` Postgres table via OAuth. Stores metadata, snippets, labels, and thread structure. Separate from Josie's `mail/` module — this feeds the brain, while `mail/` does classification and response generation.

- **`promaia/brain/seed.py`** (~100L) -- Idempotent seeder that creates 10 life domains (zbrain, promaia, heatpup, personal, hvac, etc.) and 5 project contexts with standing directives. Safe to re-run.

- **`promaia/web/routers/dashboard.py`** (~300L) -- Five FastAPI routes (/, /dashboard, /projects, /email, /profile) that query Postgres directly and render Jinja2 templates. Shows live brain data: memories, actions, project contexts, email summaries, profile traits.

- **`promaia/web/templates/*.html`** (5 files) -- Jinja2 templates: base.html (nav, skin loading, conditional fonts), dashboard.html (memory/action widgets), projects.html (project cards from brain.contexts), email.html (gmail summaries), profile.html (trait display by category).

- **`promaia/web/static/skins/superflat.css`** (~80L) -- CSS custom properties design system inspired by Murakami/Persona 5. All visual theming via `--var` properties so swapping skins only requires loading a different CSS file. Template structure stays identical.

- **`prompts/agent_*.md`** (3 files) -- System prompts for morning-briefing (calendar + priorities + brain state), email-triage (classify and surface urgent items), evening-digest (day recap + momentum + suggestions). Each prompt tells the agent what brain tools to call and how to format output.

- **`scripts/migrate_embeddings.py`** (~100L) -- One-time migration script that re-embeds all existing content from ChromaDB format to pgvector using gemini-embedding-001 (768 dims). Run once during Postgres cutover.

- **`CLAUDE.md`** (~150L) -- System instructions loaded into every Claude session. Defines brain behavior: auto-briefing at session start, when to capture memories, ambient onboarding, energy adaptation, profile-driven tone calibration.

- **`ZBRAIN.md`** -- Running changelog of every zBrain change with reasoning, so Josie can see exactly what was modified in her codebase and why.

### Modified Promaia code:

- **`storage/files.py`** -- Two changes: (1) Added Postgres connection pool initialization via `DATABASE_URL` env var pointing to Supabase session pooler, replacing local SQLite file paths. (2) Fixed KeyError at line 780 where `row[0]` assumed tuple but psycopg2 returns dict rows — changed to `row['thread_id']`. To re-implement: search for `DATABASE_URL` connection setup and the `load_content_by_page_ids` method.

- **`storage/vector_db.py`** -- Replaced ChromaDB client with pgvector operations. Vector search now uses `SELECT ... ORDER BY embedding <=> $1 LIMIT $2` (cosine distance via pgvector's `<=>` operator) instead of ChromaDB's `.query()`. HNSW index on the embedding column handles ANN search. To re-implement: replace ChromaDB `Collection` calls with pgvector SQL queries using the `<=>` operator.

- **`storage/db_init.py`** -- Added brain schema initialization: runs `brain/schema.sql` during Postgres startup to create the 7 brain tables if they don't exist. Additive — doesn't touch existing public schema tables. To re-implement: add a `CREATE SCHEMA IF NOT EXISTS brain` call and execute the schema.sql file in the db init sequence.

- **`storage/postgres_db.py`** -- Changed connection config to use Supabase session pooler URL (port 5432 via `DATABASE_URL`). Original targeted local Postgres at 192.168.0.69. To re-implement: update the connection string source to read from env var.

- **`chat/interface.py`** -- Created `GeminiModelAdapter` class (~80L) that wraps the new `google-genai` Client and exposes the old `GenerativeModel` interface (`.generate_content()` with compatible response.text). This avoids rewriting 3+ deeply-nested callers in the 8,700-line file. To re-implement: either use this adapter pattern again or refactor the callers to use the new SDK directly.

- **`ai/*.py`** (5 files: models.py, nl_orchestrator.py, nl_utilities.py, query_strategies.py, sql_generator.py) -- Updated import paths from `google.generativeai` to `google.genai` and adjusted API call signatures for the new SDK. The old `google-generativeai` package is deprecated. To re-implement: search for `google.generativeai` imports and replace with `google.genai` equivalents; main difference is `Client()` instantiation and `types.GenerateContentConfig` instead of `GenerationConfig`.

- **`agents/executor.py`** -- Two additions: (1) Brain context injection — before each agent run, loads pending actions, project contexts, and recent memories from Postgres and prepends them to the agent's initial prompt. (2) Claude Agent SDK mode — detects `SDK_AVAILABLE` flag and uses `claude_agent_sdk` for execution instead of legacy subprocess. To re-implement: look for `_load_brain_context()` method and the `ClaudeSDKClient` class.

- **`connectors/gmail_connector.py`** -- Fixed OAuth token refresh flow that was failing silently. The refresh token wasn't being persisted after renewal. To re-implement: check the token refresh callback and ensure it writes back to the credentials file.

- **`requirements.txt`** -- Added: `psycopg2-binary` (Postgres driver), `pgvector` (vector extension support), `jsonref` (JSON reference resolution, needed by instructor), `httpx` (async HTTP for MuninnDB client), `instructor` (structured LLM output via Pydantic). All pip-installable with no system dependencies on Windows.

### Untouched Promaia (used as-is):
- chat/ (10,900L), mail/ (5,600L), notion/ (2,250L), gcal/ (540L), agents/scheduler.py, CLI, web/routers/chat+mcp+nodes

## Current Milestone: v2.0 Proactive Agent

**Goal:** Transform from "brain you check" into "agent that reaches you." Mobile access, cost optimization, event routing, push notifications, memory deepening.

**Target features:**
- Phase 5: Validate & Activate (fix agent data pipeline, kill extra skins, first real agent runs)
- Phase 6: Cost Controls + Model Routing (Gemini for cheap tasks, Opus for reasoning, budget tracking, prompt caching)
- Phase 7: Event Bus + Notification Layer (Postgres polling, urgency tiers, dashboard notification badge)
- Phase 8: Telegram Bot (aiogram 3.x, Deepgram voice transcription, brain commands from phone)
- Phase 9: Proactive Push (morning briefing auto-push, evening digest, fatigue prevention, inline replies)
- Phase 10: Memory Deepening + Polish (decay tiers, association strengthening, profile-driven prompts, session handoff)

## Requirements

### Validated (v1.0)

- STOR-01 through STOR-05 -- Postgres+pgvector on Supabase (v1.0)
- BRAIN-01 through BRAIN-06 -- Brain schema + MCP tools (v1.0)
- ONBOARD-01 through ONBOARD-10 -- Onboarding module (v1.0)
- MUNINN-01 through MUNINN-06 -- MuninnDB integration (v1.0)
- DOCS-01 through DOCS-03 -- Documentation (v1.0)

### Active (v2.0)

See: `.planning/REQUIREMENTS.md` for full REQ-ID list

### Out of Scope

| Feature | Reason |
|---------|--------|
| Desktop Electron app | Josie's domain |
| React web chat app | Josie's domain |
| OpenAI API dependency | Using Gemini instead |
| Idea-to-Repo pipeline | Deferred, scope creep |
| Twilio voice calls | Deferred, cost + complexity |
| Dashboard redesign | Works well enough, agents first |

## Context

**Upstream:** Promaia by Josie (Koii Benvenutto) and Rose. Python platform, ~180 files, ~50K+ lines. Josie/Rose are re-architecting Python -> TypeScript. Zack builds on `zbrain` branch, Josie cherry-picks.

**Infrastructure:** Supabase Pro ($27.49/mo), Claude Max ($199/mo), Google AI ($20/mo planned, currently on $125 intro rate going away). Agent runs ~$0.01 each via SDK.

**Branch:** `zbrain` (base: `feature/agent-scheduler`)

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Supabase over local Postgres | iPhone day-1 access | Good -- cloud-native works |
| pgvector over ChromaDB | Cloud-native, SQL-queryable | Good -- simpler stack |
| Gemini for cheap tasks | Already paying Google AI Premium | Good -- $0.01/agent run |
| Brain as separate schema | Clean separation from Promaia | Good -- no conflicts |
| MuninnDB as sidecar | Novel cognitive primitives (Hebbian, temporal decay, graph traversal) | Working -- embeddings waiting on upstream fix |
| Dashboard as display layer | Web dashboard renders live data; Notion remains agent workspace | Good |
| Superflat CSS skin | Custom properties design system, single skin, Murakami/Persona 5 aesthetic | Working |
| Telegram over Twilio | Free, excellent bot API, async | Pending (v2) |
| Postgres polling as event bus | Zero new dependencies | Pending (v2) |

## Constraints

- **Cost**: No new API subscriptions. Use existing Claude Max, Google AI Premium, Supabase Pro.
- **Platform**: Windows 11, Claude Code CLI.
- **Upstream compatibility**: Changes should be mergeable back to Promaia.
- **Python**: Promaia is Python. Stay in Python for backend.
- **Embeddings**: gemini-embedding-001 (not OpenAI).

---
*Last updated: 2026-03-06 after v2.0 milestone start*
