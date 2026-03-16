---
phase: 02-brain-schema-and-mcp-tools
plan: 01
subsystem: database
tags: [postgres, pgvector, hnsw, gin, brain-schema, python, sql]

requires:
  - phase: 01-postgres-foundation
    provides: libSQL/MuninnDBDB singleton, get_postgres_db(), vector(768)/HNSW pattern in public schema, db_init.py scaffold

provides:
  - brain libSQL/MuninnDB schema with 7 tables (memories, domains, contexts, actions, reviews, events, modes)
  - brain/schema.sql DDL — idempotent, all CREATE IF NOT EXISTS
  - brain/engine.py with 8 deterministic functions for mode/context/budget management
  - apply_brain_schema() in db_init.py with init-brain subcommand

affects:
  - 02-02 (MCP tools — all tools query brain.* tables)
  - 02-03 (session briefing — reads brain.contexts, brain.events)
  - heartbeat agent (uses engine.py guardrails, budget_check, track_time)

tech-stack:
  added: []
  patterns:
    - "brain schema in dedicated libSQL/MuninnDB schema (not public) — prevents naming collisions"
    - "vector(768) + HNSW cosine ops — same as public.content_embeddings"
    - "GIN index on text[] arrays — fast tag lookup"
    - "B-tree indexes on brain.events (type, source, created_at DESC) — event log query patterns"
    - "All engine functions accept optional db= for mockable testing"
    - "enforce_guardrails: single-term patterns block main/master independently"

key-files:
  created:
    - promaia/brain/__init__.py
    - promaia/brain/schema.sql
    - promaia/brain/engine.py
  modified:
    - promaia/storage/db_init.py

key-decisions:
  - "brain schema lives in a dedicated 'brain' libSQL/MuninnDB schema — all 7 tables under brain.* to avoid collision with public schema"
  - "guardrails use separate single-term entries for 'main' and 'master' so either word alone triggers block without requiring both"
  - "suggest_next scores: staleness_score + priority_score; energy='low' halves scores for priority<=3 items"
  - "apply_brain_schema() uses autocommit=True per statement to match existing init_database() pattern"

patterns-established:
  - "Engine functions: pure Python + SQL, no LLM calls, optional db param for testability"
  - "Mode detection: keyword hit count -> confidence (0.4 base + 0.15 per hit, capped at 0.95)"
  - "Guardrail rule format: list of required_terms; all must match in action string"

requirements-completed: [BRAIN-01, BRAIN-02, BRAIN-03, BRAIN-06]

duration: 6min
completed: 2026-03-05
---

# Phase 02 Plan 01: Brain Schema and Engine Summary

**Brain libSQL/MuninnDB schema (7 tables with HNSW/GIN indexes) and 8 deterministic engine functions for mode detection, guardrails, time tracking, budget management, and context save/restore**

## Performance

- **Duration:** 6 min
- **Started:** 2026-03-05T02:04:48Z
- **Completed:** 2026-03-05T02:10:14Z
- **Tasks:** 2/2
- **Files modified:** 4

## Accomplishments

- Created `promaia/brain/schema.sql` with all 7 brain tables: memories (vector(768) + HNSW + GIN on tags), domains, contexts, actions, reviews, events (B-tree on type/source/created_at), modes
- Created `promaia/brain/engine.py` with 8 pure-Python deterministic functions — no LLM imports, all testable via optional db parameter
- Extended `promaia/storage/db_init.py` with `apply_brain_schema()` function and `init-brain` CLI subcommand

## Task Commits

Each task was committed atomically:

1. **Task 1: Create brain schema SQL and extend db_init.py** - `b0031df` (feat)
2. **Task 2: Create brain/engine.py with 8 deterministic functions** - `a2d1c65` (feat)

**Plan metadata:** (docs commit — next)

## Files Created/Modified

- `promaia/brain/__init__.py` — Brain package init with docstring describing module contents
- `promaia/brain/schema.sql` — DDL for all 7 brain tables, HNSW index on memories.embedding, GIN on memories.tags, B-tree indexes on brain.events
- `promaia/brain/engine.py` — 8 deterministic functions: detect_mode, confirm_mode, enforce_guardrails, track_time, budget_check, save_context, restore_context, suggest_next
- `promaia/storage/db_init.py` — Added get_brain_schema_path(), apply_brain_schema(), init-brain subcommand

## Decisions Made

- **brain schema in dedicated libSQL/MuninnDB schema:** All 7 tables live under `brain.*` to keep them separate from `public.*` tables. This avoids naming collisions (e.g., public already has no 'memories' table but future additions won't conflict).
- **Guardrail pattern design:** Separated 'main' and 'master' into individual single-term block patterns. Original design had them combined (`['main', 'master']`) which required BOTH words to appear — incorrect. Each word independently signals a main branch operation.
- **apply_brain_schema() uses autocommit=True:** Matches the existing `init_database()` pattern — executes each DDL statement individually. CREATE INDEX/TABLE IF NOT EXISTS are idempotent so this is safe.
- **suggest_next staleness cap at 2.0:** Domains severely overdue don't get unbounded scores — prevents any single stale domain from completely dominating even with energy adjustments.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed guardrails pattern for main/master branch detection**
- **Found during:** Task 2 verification
- **Issue:** `_BLOCK_PATTERNS` had `(['main', 'master'], None)` which requires both words in the action string. "push to main" only contains 'main', so it was incorrectly allowed.
- **Fix:** Split into two separate entries: `(['main'], None)` and `(['master'], None)` so either word alone triggers the block.
- **Files modified:** promaia/brain/engine.py
- **Verification:** `enforce_guardrails('push to main', 'heartbeat') == False` now passes
- **Committed in:** a2d1c65 (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 - bug in guardrail pattern logic)
**Impact on plan:** Essential correctness fix — the guardrails are a safety system and must block main branch operations reliably. No scope creep.

## Issues Encountered

None beyond the guardrails pattern fix above.

## User Setup Required

None — no external service configuration required. Brain schema is applied via `python -m promaia.storage.db_init init-brain` once Railway Volumes connection is live (existing DATABASE_URL env var).

## Next Phase Readiness

- Brain schema SQL is ready to apply against Railway Volumes (run `init-brain` subcommand)
- All 8 engine functions importable and passing tests
- Plan 02-02 (MCP tools) can build on brain.* tables and import from engine.py immediately
- No blockers

---
*Phase: 02-brain-schema-and-mcp-tools*
*Completed: 2026-03-05*
