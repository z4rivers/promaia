# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-06)

**Core value:** Proactive AI assistant that reaches YOU -- not a dashboard you check, but a system that initiates, remembers, and acts autonomously.
**Current focus:** Phase 7: Event Bus + Notification Layer

## Current Position

Phase: 7 of 10 (Event Bus + Notification Layer)
Plan: 1 of 3 in current phase -- COMPLETE
Status: In Progress
Last activity: 2026-03-07 -- Plan 07-01 complete (Event schema + emitter)

Progress: [##########--------------------] 33% (v2.0 Phase 7: 1/3 plans complete)

## Performance Metrics

**Velocity:**
- Total plans completed: 10 (v1.0)
- Average duration: --
- Total execution time: --

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 01. Postgres Foundation | 3 | -- | -- |
| 02. Brain Schema + MCP | 3 | -- | -- |
| 03.1 Onboarding Module | 3 | -- | -- |
| 04. Platform Activation | 1 | -- | -- |
| 05. Validate & Activate | 3 | ~12min | ~4min |
| 06. Waste Elim + Spend Vis | 4/4 | 39min | ~10min |
| 07. Event Bus + Notif Layer | 1/3 | 3min | 3min |

**Recent Trend:** Phase 7 in progress. Event schema extended, emitter wired into executor. All agents now produce routable events after each run.

## What's Live

- Brain MCP server: 16 tools (added brain_costs), 56+ memories, 10 domains, 98 profile traits
- Agent scheduler: PID running, 3 agents (morning-briefing, email-triage, evening-digest)
- Agent cost: ~$0.004/run avg via Gemini 3 Flash ($0.0125 total for 3-agent cycle, down from $0.132 Claude)
- Web dashboard: localhost:8000, 5 pages, Superflat skin
- Gmail pipeline: OAuth working, emails ingested

## Known Issues (Phase 5 targets)

- ~~Gmail context loads from .md files~~ FIXED: Postgres fallback in load_content_by_page_ids
- ~~SQL dialect bugs: jsonb operators~~ FIXED: GIN index + type documentation
- Agent token tracking shows $0.00 in legacy mode
- MuninnDB embeddings broken (text-embedding-004 deprecated)

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- v2.0: Linear phase dependency (5->6->7->8->9->10) -- each phase builds on prior
- v2.0: Telegram over Twilio for mobile channel (free, excellent bot API)
- v2.0: Postgres polling as event bus (zero new dependencies)
- v2.0: Gemini for cheap agent tasks, Opus reserved for reasoning
- 05-02: 480-min interval for email-triage (3x/day) rather than time-of-day scheduling
- 05-02: Grounding Rules section placed before content instructions with override priority
- 05-01: Gmail Postgres fallback activates only when md_file is None AND entry is Gmail
- 05-01: GIN index replaces B-tree on gmail_labels for proper JSONB operator support
- 05-03: Human-verified agent output quality -- all three agents approved with zero hallucination
- 05-03: morning-briefing inferring "Office day" from profile data (not calendar) accepted as valid
- 06-01: All 3 agents use Gemini 3 Flash per user decision COST-04
- 06-01: thinking_budget=0 for Flash-Lite (no thinking support)
- 06-01: Thinking tokens billed separately via thinking_price_per_m
- 06-02: Office day detection hardcoded to Thursday (matches Zack's schedule)
- 06-02: AGENT_TOOL_REGISTRY static mapping for 3 known agents (no dynamic discovery)
- 06-02: Prompt restructuring already applied by 06-01 -- verified, no redundant changes
- 06-03: Synchronous genai.generate_content (matching nl_orchestrator.py pattern, not asyncio.to_thread)
- 06-03: Single-level fallback only (no cascade) to prevent cost explosion
- 06-03: RunawayDetector uses word-set Jaccard overlap (no external deps)
- 06-03: Budget-blocked agents sleep for full interval before retry
- 06-04: All 3 agents validated on Gemini 3 Flash with human-approved output quality
- 06-04: 91% cost reduction confirmed ($0.0125 vs $0.132 Claude baseline)
- 06-04: Fixed datetime variable shadowing in executor.py (auto-fix Rule 1)
- 07-01: Deterministic agent-to-urgency mapping (no LLM classification) for zero-cost routing
- 07-01: Unknown agents default to digest urgency as safe fallback
- 07-01: Event emission non-fatal -- never crashes agent pipeline

### Pending Todos

None yet.

### Blockers/Concerns

- Google AI pricing: $125/mo intro rate going away. Budget projections assume $20/mo plan.
- MuninnDB v0.3.7 needed for embedding fix (Windows binary not yet available)

## Session Continuity

Last session: 2026-03-07
Stopped at: Completed 07-01-PLAN.md (Event schema + emitter wired into executor)
Resume file: None
Next: 07-02-PLAN.md -- Notification Router
