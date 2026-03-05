# State: zBrain

## Current Position

Phase: Phase 2 — Brain Schema and MCP Tools (in progress)
Plan: 02-01 COMPLETE (brain schema + engine.py)
Status: Plan 02-01 executed — 2/2 tasks, 7/7 verifications passed
Last activity: 2026-03-05 — Brain schema SQL and deterministic engine functions complete

## Next Session: What to Do

1. Execute Plan 02-02 (MCP Tools: briefing, capture, search, recall, context, actions)
2. Apply brain schema to Supabase: `python -m promaia.storage.db_init init-brain`
3. All 8 engine functions ready for MCP tool imports

## Phase 1 Completion Summary

**3 plans, 3 waves, all sequential. Verified 8/8.**

| Plan | What it did |
|------|------------|
| 01-01 | Merged postgres-sql-changeover, configured Supabase session pooler (us-east-1), deployed pgvector schema with HNSW+GIN indexes |
| 01-02 | Rewrote vector_db.py from ChromaDB to pgvector, migrated google-generativeai → google-genai across 6 files, updated requirements.txt |
| 01-03 | Created re-embedding migration script (303 lines), ZBRAIN.md changelog (110 lines) |

## Key Execution Decisions (2026-03-04)

- **New Supabase project** (jbcspnoqvtvvddifuhth) — dedicated to Promaia, separate from Heatpup
- **Project in us-east-1** (Supabase default), pooler at aws-1-us-east-1.pooler.supabase.com:5432
- **DATABASE_URL is primary connection** — session pooler required on Windows (IPv6 issues)
- **sslmode=require** for Supabase cloud security
- **vector(768) not halfvec** — HNSW with vector_cosine_ops
- **GeminiModelAdapter pattern** — wraps google-genai Client for backward compat in chat/interface.py
- **Tables currently empty** — no content synced to new project yet (expected)
- **Added MAINT-01 through MAINT-04** — self-updating dependency intelligence requirements

## Key Design Decisions (Session: 2026-03-04 Design)

- **Architecture:** Hybrid (Approach C) — thin deterministic engine + smart instructions + persistent schema
- **Mode detection:** Infer + confirm
- **Heartbeat autonomy:** Safe actions allowed (feature branch commits, no external comms)
- **DeBono:** Invisible by default
- **Embedding type:** vector(768) not halfvec (Gemini review)
- **Heartbeat execution:** Python AgentExecutor directly, not CLI subprocess (Gemini review)
- **Indexes:** HNSW on embeddings + GIN on tags/entities (Gemini review)
- **Heartbeat guardrails:** Active user check, max 2 commits per cycle (Gemini review)

## Design Documents

- `docs/plans/2026-03-04-zbrain-promaia-merge-design.md` — Infrastructure
- `docs/plans/2026-03-04-zbrain-workflow-design.md` — Workflow & UX (ADHD-aware)
- `.planning/REQUIREMENTS.md` — 24 requirements across 7 categories

## Project Reference

See: .planning/PROJECT.md
**Core value:** Claude has persistent, cross-session memory across all of Zack's projects — eliminating the amnesia problem.

## Blockers

None.

## Upcoming Events

- **Promaia re-init (within ~1 week):** Daughter re-initializing repo. Export patches before: `git format-patch feature/agent-scheduler..zbrain -o zbrain-patches/`

## Phase 2 Progress (2026-03-05)

| Plan | What it did |
|------|------------|
| 02-01 | Created brain schema (7 tables, HNSW+GIN), engine.py (8 deterministic functions), extended db_init.py with apply_brain_schema() |

## Key Execution Decisions (2026-03-05)

- **brain.* schema:** All 7 tables in dedicated Postgres schema (not public) — prevents naming collisions
- **Guardrail pattern fix:** Separated 'main' and 'master' into individual single-term patterns — required for correct blocking of "push to main"
- **suggest_next staleness cap:** 2.0 ceiling prevents severely stale domains from dominating energy-adjusted scoring
- **apply_brain_schema() autocommit:** Matches existing init_database() pattern, executes each DDL statement independently

## Git State

- Branch: `zbrain` (off `feature/agent-scheduler`)
- Phase 1 commits: cbad997 through e5fd713 (10 commits)
- Phase 2 commits: b0031df (02-01 schema), a2d1c65 (02-01 engine)
