# State: zBrain

## Current Position

Phase: Ready for Phase 1 planning via GSD
Plan: —
Status: Design complete, Gemini-reviewed, ready for `/gsd:plan-phase` on Phase 1
Last activity: 2026-03-04 — Design docs finalized, Gemini 3.1 Pro review incorporated

## Next Session: What to Do

1. Run `/gsd:plan-phase` for Phase 1 (Postgres Foundation)
2. Feed the existing design docs as context — don't re-research
3. Use `--skip-research` flag since research is already done
4. Key Phase 1 tasks from design doc:
   - Merge postgres-sql-changeover branch into zbrain
   - Configure Supabase connection
   - Add pgvector extension + vector(768) columns with HNSW indexes
   - Migrate vector_db.py from ChromaDB to pgvector
   - Re-embed all existing content with gemini-embedding-001 (migration script)
   - Add GIN indexes on tags/entities for hybrid search
   - Verify all existing Promaia features still work

## Design Documents (COMPLETE)

- `docs/plans/2026-03-04-zbrain-promaia-merge-design.md` — Infrastructure (4 features, 5 phases)
- `docs/plans/2026-03-04-zbrain-workflow-design.md` — Workflow & UX (ADHD-aware, DeBono, guardrails)
- `.planning/REQUIREMENTS.md` — 20 requirements across 6 categories
- `.planning/research/` — Stack, features, architecture, pitfalls research

## Key Design Decisions (This Session)

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

None currently.

## Upcoming Events

- **Promaia re-init (within ~1 week):** Daughter re-initializing repo. Export patches before: `git format-patch feature/agent-scheduler..zbrain -o zbrain-patches/`

## Git State

- Branch: `zbrain` (off `feature/agent-scheduler`)
- Latest commits:
  - d38967e docs: incorporate Gemini 3.1 Pro architectural review findings
  - 2889f26 docs: add zBrain workflow & UX design
  - ffcfa81 docs: update state — requirements complete, ready for roadmap
