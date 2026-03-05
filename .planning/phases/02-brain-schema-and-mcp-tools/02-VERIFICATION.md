---
phase: 02-brain-schema-and-mcp-tools
verified: 2026-03-05T03:00:00Z
status: human_needed
score: 7/7 must-haves verified
re_verification: false
human_verification:
  - test: "Start a new Claude Code session in the promaia repo and confirm the briefing fires automatically on the first message without being asked"
    expected: "Claude calls mcp__brain__briefing before responding to the first message, reports stale projects or 'None', pending actions, and heartbeat activity"
    why_human: "System instruction behavior (CLAUDE.md auto-triggering MCP call on session start) cannot be verified by reading files — requires a live Claude Code session"
  - test: "Say 'I need to update the calculator pricing' and observe the response"
    expected: "Claude calls mcp__brain__capture, response includes 'Captured. Extracted 1 action(s).' — confirms action extraction pipeline is live (Gemini Flash API call)"
    why_human: "Requires live GOOGLE_API_KEY, active Gemini Flash connection, and real extraction — cannot verify API round-trip from files alone"
  - test: "Confirm brain schema tables exist in Supabase Dashboard"
    expected: "7 tables visible in Table Editor: brain.memories, brain.domains, brain.contexts, brain.actions, brain.reviews, brain.events, brain.modes"
    why_human: "Schema is applied at runtime via apply_brain_schema() — file existence and SQL content are verified but actual Supabase deployment requires human confirmation"
  - test: "Run 'python -m promaia.brain.seed' and verify 10 domains and 5 contexts in Supabase"
    expected: "seed.py runs without error, Supabase brain.domains shows 10 rows, brain.contexts shows 5 rows with directives"
    why_human: "Requires live DATABASE_URL connection to Supabase — cannot verify actual row presence from files"
---

# Phase 2: Brain Schema and MCP Tools Verification Report

**Phase Goal:** Add proactive brain layer — memories, domains, contexts, actions, reviews, events tables plus MCP tools for briefing, capture, search, and system instructions
**Verified:** 2026-03-05
**Status:** human_needed — all automated checks pass; 4 items require live environment confirmation
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths (from ROADMAP.md Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Brain schema tables created (memories, domains, contexts, actions, reviews, events, modes) | VERIFIED | `promaia/brain/schema.sql` has all 7 `CREATE TABLE IF NOT EXISTS brain.*` statements with correct DDL |
| 2 | MCP tools working: briefing, capture, search, recall, context, update_context, actions | VERIFIED | `promaia/brain/mcp_server.py` registers exactly 7 tools with full handlers (818 lines, no stubs) |
| 3 | Session briefing runs automatically on startup | VERIFIED (code) / NEEDS HUMAN (live) | CLAUDE.md instructs `mcp__brain__briefing` on first message; handler queries stale/pending/heartbeat |
| 4 | Action extraction detects actionable items from conversation | VERIFIED (code) / NEEDS HUMAN (live) | `extraction.py` implements dual-path (instructor + raw Gemini fallback), never raises, returns `ActionExtractionResult` |
| 5 | Standing directives per project stored and queryable | VERIFIED | `brain.contexts` table with `directive`, `stale_threshold_days`, `priority` columns; context tool queries via JOIN |
| 6 | Stale project alerts surface in briefings | VERIFIED | Briefing handler queries `NOW() - c.last_updated > c.stale_threshold_days * INTERVAL '1 day'` with stale note in context tool response |
| 7 | brain/engine.py deterministic functions operational | VERIFIED | All 8 functions present: detect_mode, confirm_mode, enforce_guardrails, track_time, budget_check, save_context, restore_context, suggest_next — no LLM imports |

**Score:** 7/7 truths verified (4 confirmed in-code; 3 of those also require live environment confirmation)

---

## Required Artifacts

### Plan 02-01 Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `promaia/brain/__init__.py` | Brain package init | VERIFIED | Exists, has docstring listing package contents |
| `promaia/brain/schema.sql` | All brain schema DDL | VERIFIED | 148 lines; all 7 tables, HNSW on memories.embedding (vector_cosine_ops), GIN on memories.tags, B-tree on events (type, source, created_at DESC, session_id) |
| `promaia/brain/engine.py` | 8 deterministic functions | VERIFIED | 420 lines; all 8 functions present with correct signatures and optional `db=` parameter; no genai/anthropic imports |
| `promaia/storage/db_init.py` | apply_brain_schema() function | VERIFIED | 305 lines; `apply_brain_schema()` at line 216, `get_brain_schema_path()` at line 211, `init-brain` subcommand wired at line 281 |

### Plan 02-02 Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `promaia/brain/mcp_server.py` | Brain MCP server with 7 tools | VERIFIED | 818 lines (exceeds min_lines: 200); `server = Server("zbrain-brain")` at line 60; all 7 tools in list_tools() with full handlers |
| `promaia/brain/extraction.py` | Action extraction via instructor + Gemini Flash | VERIFIED | 158 lines; `ExtractedAction` and `ActionExtractionResult` Pydantic models; `extract_actions()` with instructor primary + raw Gemini fallback |

### Plan 02-03 Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `CLAUDE.md` | System instructions for proactive brain behavior | VERIFIED | 28 lines (exceeds min_lines: 15); contains `mcp__brain__briefing`, `mcp__brain__capture`, `mcp__brain__context`, `mcp__brain__update_context` — 5 total references |
| `.mcp.json` | Project-scoped MCP server registration | VERIFIED (partial) | Contains `promaia.brain.mcp_server` in args; `env` block absent (server uses `load_dotenv()` instead — functionally equivalent) |
| `promaia/brain/seed.py` | Domain and context seed data script | VERIFIED | 198 lines; `brain.domains` inserts, `brain.contexts` inserts; 10 domains and 5 contexts defined; idempotent via ON CONFLICT + existence check |

---

## Key Link Verification

### Plan 02-01 Key Links

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `promaia/storage/db_init.py` | `promaia/brain/schema.sql` | reads SQL file and executes against Postgres | WIRED | `get_brain_schema_path()` returns `Path(__file__).parent.parent / "brain" / "schema.sql"`, opened and split/executed in `apply_brain_schema()` |
| `promaia/brain/engine.py` | `promaia/storage/postgres_db.py` | imports PostgresDB for SQL queries | WIRED | Lazy import `from promaia.storage.postgres_db import get_postgres_db` inside each DB-touching function (track_time, budget_check, save_context, restore_context) |

### Plan 02-02 Key Links

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `promaia/brain/mcp_server.py` | `promaia/storage/postgres_db.py` | `get_postgres_db()` for all brain.* SQL queries | WIRED | Line 47: `from promaia.storage.postgres_db import get_postgres_db`; `get_db()` singleton wrapper used throughout all 7 handlers |
| `promaia/brain/mcp_server.py` | `promaia/brain/engine.py` | imports engine functions | WIRED | Line 49: `from promaia.brain import engine` — engine imported as module namespace |
| `promaia/brain/mcp_server.py` | `promaia/brain/extraction.py` | imports extract_actions for capture tool | WIRED | Line 50: `from promaia.brain.extraction import extract_actions`; called in `_handle_capture()` |
| `promaia/brain/mcp_server.py` | `promaia/storage/vector_db.py` | uses VectorDBManager.generate_embedding() | WIRED | Line 48: via `from promaia.storage.vector_db import VectorDBManager`; `get_vector_mgr()` called in capture and search handlers; `register_vector(conn)` called per-connection before embedding queries |

### Plan 02-03 Key Links

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `CLAUDE.md` | `promaia/brain/mcp_server.py` | system instructions reference brain MCP tool names | WIRED | 5 occurrences of `mcp__brain__` in CLAUDE.md (briefing, capture x2, context, update_context) |
| `.mcp.json` | `promaia/brain/mcp_server.py` | registers MCP server as stdio transport | WIRED | `"args": ["-m", "promaia.brain.mcp_server"]` with `"type": "stdio"` |
| `promaia/brain/seed.py` | `promaia/storage/postgres_db.py` | inserts seed data into brain.domains and brain.contexts | WIRED | Line 13: `from promaia.storage.postgres_db import get_postgres_db`; used in `seed_domains()` and `seed_contexts()` |

---

## Requirements Coverage

| Requirement | Plans | Description | Status | Evidence |
|-------------|-------|-------------|--------|----------|
| BRAIN-01 | 02-01, 02-02 | Brain schema stores memories with embeddings (semantic search) | SATISFIED | `brain.memories` with `embedding vector(768)` + HNSW; search tool uses cosine distance via pgvector |
| BRAIN-02 | 02-01, 02-03 | Domains represent life categories and projects | SATISFIED | `brain.domains` with `is_project`, `parent_domain INTEGER REFERENCES brain.domains(id)`; seed.py populates 10 domains |
| BRAIN-03 | 02-01, 02-03 | Standing directives per project | SATISFIED | `brain.contexts` with `directive TEXT`, `stale_threshold_days INTEGER`; context tool queries and returns directive |
| BRAIN-04 | 02-02 | Actions auto-extracted from conversations | SATISFIED (code) | `extraction.py` + instructor/Gemini Flash fallback; `_handle_capture()` inserts into `brain.actions` if `has_actions=True` |
| BRAIN-05 | 02-02, 02-03 | Session briefing on startup (stale projects, pending actions, recent activity) | SATISFIED (code) | `_handle_briefing()` queries all 3 data sources; CLAUDE.md instructs call on first message |
| BRAIN-06 | 02-01, 02-02 | Stale alerts flag projects past threshold | SATISFIED | Briefing SQL: `NOW() - c.last_updated > c.stale_threshold_days * INTERVAL '1 day'`; context tool annotates stale with "** STALE **"; `suggest_next()` scores by staleness ratio |

**Orphaned requirements check:** REQUIREMENTS.md maps BRAIN-01 through BRAIN-06 to Phase 2. All 6 are claimed by plans and verified above. No orphaned requirements.

---

## Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `promaia/brain/engine.py` | 294, 332, 356, 416 | `return {}` | INFO | These are legitimate error fallbacks in save_context (failure), restore_context (not found), suggest_next (empty input/no scored) — not stubs. All have surrounding logic. |
| `.mcp.json` | all | Missing `env` block with `DATABASE_URL` / `GOOGLE_API_KEY` | WARNING | Plan 02-03 specified env passthrough. Server compensates with `load_dotenv()` at startup — functionally equivalent but means the MCP server requires a `.env` file at repo root. If env vars are set at system level, this is fine. If not, the `load_dotenv()` path must find the file. |

No blocker anti-patterns found.

---

## Human Verification Required

### 1. Auto-briefing on Session Start

**Test:** Open a new Claude Code session in the promaia repo directory. Send any first message (e.g., "Hi").
**Expected:** Before responding to your message, Claude automatically calls the `briefing` MCP tool and presents output with stale projects, pending actions, and heartbeat activity sections. Response ends with a numbered suggestion and "Start with #1?"
**Why human:** CLAUDE.md system instructions trigger the briefing call — this is behavioral, not code-verifiable. Requires a live Claude Code session with the brain MCP server connected.

### 2. Action Extraction Pipeline (Live API)

**Test:** In a Claude Code session with brain connected, say "I need to update the Heatpup calculator pricing to include the new Mitsubishi rebates."
**Expected:** Claude calls `mcp__brain__capture` with the content. Response is "Captured. Extracted 1 action(s)." The extracted action is stored in `brain.actions` in Supabase.
**Why human:** Requires live `GOOGLE_API_KEY`, active Gemini Flash API call, and successful instructor or raw-Gemini extraction. The code path is verified but the API round-trip cannot be tested from files.

### 3. Brain Schema Deployed to Supabase

**Test:** Run `python -m promaia.storage.db_init init-brain` from the repo root. Open Supabase Dashboard -> Table Editor.
**Expected:** 7 tables visible in the `brain` schema: memories, domains, contexts, actions, reviews, events, modes. No error in terminal output.
**Why human:** `apply_brain_schema()` is fully implemented and wired, but actual Supabase deployment requires a live DATABASE_URL connection. The schema SQL and the function are both verified in code.

### 4. Seed Data Populated in Supabase

**Test:** Run `python -m promaia.brain.seed`. Check Supabase Dashboard -> brain.domains (should show 10 rows) and brain.contexts (should show 5 rows with directives).
**Expected:** 10 domains: Heatpup, HVAC Brand, PURRfoot, Promaia, zBrain, Catpool, Hopecookie, Maybecat, HVAC Work, Personal. 5 contexts with directives for the 5 project domains.
**Why human:** Seed data and seed script are fully verified in code. Actual Supabase row presence requires live connection confirmation.

---

## Summary

All Phase 2 implementation artifacts exist, are substantive, and are correctly wired together. No stubs, no missing files, no broken connections detected.

**Automated checks confirmed:**
- `promaia/brain/schema.sql` — 7 tables with vector(768), HNSW, GIN, and B-tree indexes as specified
- `promaia/brain/engine.py` — all 8 deterministic functions, no LLM imports, correct optional `db=` parameter pattern
- `promaia/storage/db_init.py` — `apply_brain_schema()` and `init-brain` subcommand present and wired
- `promaia/brain/extraction.py` — `ExtractedAction`, `ActionExtractionResult`, `extract_actions()` with dual-path fallback
- `promaia/brain/mcp_server.py` — 7 tools registered with full handlers (818 lines); capture -> embed -> extract_actions pipeline; search uses `register_vector` per-connection; briefing surfaces stale/pending/heartbeat
- `CLAUDE.md` — proactive brain instructions present at repo root with correct `mcp__brain__` tool references
- `.mcp.json` — brain server registered with correct stdio transport and module path
- `promaia/brain/seed.py` — 10 domains and 5 contexts defined with idempotent insert pattern
- `requirements.txt` — `instructor>=1.0.0` present at line 105
- All 6 requirements (BRAIN-01 through BRAIN-06) satisfied with code evidence

**One notable deviation from plan:** `.mcp.json` omits the `env` block (`DATABASE_URL`, `GOOGLE_API_KEY`). The server compensates with `load_dotenv()` at module load time (line 33 of mcp_server.py). This is functionally equivalent as long as a `.env` file exists at repo root. This does mean env vars are not passed explicitly via the MCP config — warrants confirmation that the `.env` file is in place.

The 4 human verification items are live-environment confirmations of already-verified code paths — not gaps in the implementation.

---
_Verified: 2026-03-05_
_Verifier: Claude (gsd-verifier)_
