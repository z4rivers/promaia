# State: zBrain

## Current Position

Phase: 01-postgres-foundation
Plan: 02 of 3 (complete)
Status: Plan 02 complete -- ChromaDB replaced with pgvector, google-genai SDK migration done. Ready for Plan 03.
Last activity: 2026-03-04 -- Phase 01 Plan 02 executed (pgvector migration + google-genai SDK)
Last session: 2026-03-04T20:02:00Z
Stopped at: Completed 01-02-PLAN.md

## Next Session: What to Do

1. Execute Plan 03 (re-embedding migration script, end-to-end verification, ZBRAIN.md changelog):
   - Run `/gsd:execute-phase` for Phase 1 Plan 03
2. Then proceed to Phase 2 planning (Brain Schema and MCP Tools)

## Design Documents (COMPLETE)

- `docs/plans/2026-03-04-zbrain-promaia-merge-design.md` -- Infrastructure (4 features, 5 phases)
- `docs/plans/2026-03-04-zbrain-workflow-design.md` -- Workflow & UX (ADHD-aware, DeBono, guardrails)
- `.planning/REQUIREMENTS.md` -- 20 requirements across 6 categories
- `.planning/research/` -- Stack, features, architecture, pitfalls research

## Key Execution Decisions (2026-03-04)

- **DATABASE_URL is the primary connection method** -- session pooler required on Windows due to IPv6 issues with direct Supabase connections
- **sslmode=require** -- added to all connection paths for Supabase cloud security
- **vector(768) not halfvec** -- confirmed in HNSW index implementation (gemini-embedding-001)
- **HNSW cosine ops** -- `vector_cosine_ops` matches former ChromaDB `hnsw:space=cosine` config
- **psycopg2-binary 2.9.11** -- requirements.txt has 2.9.9 but that fails on Python 3.14; installed 2.9.11
- **GeminiModelAdapter pattern** -- wraps google-genai Client to provide old GenerativeModel interface in chat/interface.py
- **register_vector per-connection** -- pgvector type registration is connection-scoped in psycopg2
- **chroma_path backward compat** -- VectorDBManager still accepts chroma_path parameter but ignores it

## Key Design Decisions (Session: 2026-03-04 Design)

- **Architecture:** Hybrid (Approach C) -- thin deterministic engine + smart instructions + persistent schema
- **Mode detection:** Infer + confirm
- **Phone to PC handoff:** Adjusted plan on login
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
- Skip GSD roadmap/research stages -- design docs serve as the spec
- No roadmap file needed -- phases defined in design doc

## Project Reference

See: .planning/PROJECT.md
**Core value:** Claude has persistent, cross-session memory across all of Zack's projects -- eliminating the amnesia problem.

## Blockers

None currently.

## Upcoming Events

- **Promaia re-init (within ~1 week):** Daughter re-initializing repo. Export patches before: `git format-patch feature/agent-scheduler..zbrain -o zbrain-patches/`

## Git State

- Branch: `zbrain` (off `feature/agent-scheduler`)
- Latest commits:
  - 56c5006 feat(01-02): migrate google-generativeai to google-genai SDK and update requirements
  - ee8bef3 feat(01-02): replace ChromaDB with pgvector in vector_db.py
  - 903376f fix(01-01): correct Supabase pooler region to us-east-1
  - ee5987e fix(01-01): update Supabase project ref to new 'promaia' project
  - 7b3048e docs(01-01): complete plan 01 tasks 1-2, checkpoint reached for Supabase verification

## Performance Metrics

| Phase-Plan | Duration | Tasks | Files | Date |
|---|---|---|---|---|
| 01-01 | ~30min | 2/3 | 25+ | 2026-03-04 |
| 01-02 | ~15min | 2/2 | 8 | 2026-03-04 |
