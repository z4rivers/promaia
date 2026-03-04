# State: zBrain

## Current Position

Phase: 01-postgres-foundation
Plan: 01 of 3 (at checkpoint — awaiting human verification)
Status: Tasks 1-2 complete. Paused at checkpoint:human-verify. User must run `python -m promaia.storage.db_init init` and verify Supabase tables before Plan 02 can start.
Last activity: 2026-03-04 — Phase 01 Plan 01 tasks 1+2 executed (postgres merge + pgvector schema)
Last session: 2026-03-04T18:02:21Z
Stopped at: 01-01-PLAN.md (Task 3: checkpoint:human-verify)

## Next Session: What to Do

1. Verify Supabase deployment:
   - Ensure `.env` has `DATABASE_URL` with session pooler URL (see `docs/env.template`)
   - Run: `python -m promaia.storage.db_init init`
   - Confirm tables in Supabase Dashboard -> Table Editor
   - Run SQL: `SELECT extname FROM pg_extension WHERE extname = 'vector';`
2. After verification, continue with Plan 02 (zBrain Schema Extensions):
   - Run `/gsd:execute-phase` for Phase 1 Plan 02
3. Then Plan 03 (Vector DB Migration)

## Design Documents (COMPLETE)

- `docs/plans/2026-03-04-zbrain-promaia-merge-design.md` — Infrastructure (4 features, 5 phases)
- `docs/plans/2026-03-04-zbrain-workflow-design.md` — Workflow & UX (ADHD-aware, DeBono, guardrails)
- `.planning/REQUIREMENTS.md` — 20 requirements across 6 categories
- `.planning/research/` — Stack, features, architecture, pitfalls research

## Key Execution Decisions (2026-03-04)

- **DATABASE_URL is the primary connection method** — session pooler required on Windows due to IPv6 issues with direct Supabase connections
- **sslmode=require** — added to all connection paths for Supabase cloud security
- **vector(768) not halfvec** — confirmed in HNSW index implementation (gemini-embedding-001)
- **HNSW cosine ops** — `vector_cosine_ops` matches former ChromaDB `hnsw:space=cosine` config
- **psycopg2-binary 2.9.11** — requirements.txt has 2.9.9 but that fails on Python 3.14; updated to 2.9.11

## Key Design Decisions (Session: 2026-03-04 Design)

- **Architecture:** Hybrid (Approach C) — thin deterministic engine + smart instructions + persistent schema
- **Mode detection:** Infer + confirm
- **Phone→PC handoff:** Adjusted plan on login
- **Heartbeat autonomy:** Safe actions allowed (feature branch commits, no external comms)
- **DeBono:** Invisible by default
- **Check-in cadence:** Ambient awareness, no formal check-ins
- **Embedding type:** vector(768) not halfvec (Gemini review)
- **Heartbeat execution:** Python AgentExecutor directly, not CLI subprocess (Gemini review)
- **New table:** brain.events audit trail (Gemini review)
- **Indexes:** HNSW on embeddings + GIN on tags/entities (Gemini review)
- **Heartbeat guardrails:** Active user check, max 2 commits per cycle (Gemini review)

## Execution Strategy

- GSD for phase-by-phase execution (plan each phase when ready to build)
- Skip GSD roadmap/research stages — design docs serve as the spec
- No roadmap file needed — phases defined in design doc

## Project Reference

See: .planning/PROJECT.md
**Core value:** Claude has persistent, cross-session memory across all of Zack's projects — eliminating the amnesia problem.

## Blockers

- **Supabase deployment pending** — User must run `python -m promaia.storage.db_init init` with valid `.env` credentials before Plan 02 can start. Schema is ready; deployment is a human-action step.

## Upcoming Events

- **Promaia re-init (within ~1 week):** Daughter re-initializing repo. Export patches before: `git format-patch feature/agent-scheduler..zbrain -o zbrain-patches/`

## Git State

- Branch: `zbrain` (off `feature/agent-scheduler`)
- Latest commits:
  - 118534c feat(01-01): extend schema with pgvector extension and embedding tables
  - c10db76 feat(01-01): merge postgres-sql-changeover and reconfigure for Supabase
  - cbad997 Merge remote-tracking branch 'origin/postgres-sql-changeover' into zbrain
  - 0bbb99d docs(01-postgres-foundation): create phase plan - 3 plans, 3 waves
  - 4e64912 docs: update state — design complete, ready for Phase 1 GSD execution
