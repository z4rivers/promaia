# State: zBrain

## Current Position

Phase: Phase 1 COMPLETE — ready for Phase 2 planning
Plan: —
Status: Phase 1 verified (8/8 must-haves passed)
Last activity: 2026-03-04 — Phase 1 Postgres Foundation complete

## Next Session: What to Do

1. Run `/gsd:plan-phase 2` for Phase 2 (Brain Schema and MCP Tools)
2. Phase 2 depends on Phase 1 (complete) — no blockers
3. Key Phase 2 deliverables from roadmap:
   - Brain schema tables (memories, domains, contexts, actions, reviews, events, modes)
   - MCP tools: briefing, capture, search, recall, context, actions
   - Session briefing on startup
   - brain/engine.py deterministic functions
4. New MAINT requirements added — self-updating dependency intelligence (future phase)

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

## Git State

- Branch: `zbrain` (off `feature/agent-scheduler`)
- Phase 1 commits: cbad997 through e5fd713 (10 commits)
