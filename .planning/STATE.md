# State: zBrain

## Current Position

Phase: Phase 4.1 — MuninnDB Cognitive Memory COMPLETE
Plan: 4.1-01 of 4.1-01 complete (1/1)
Status: 4.1-01 COMPLETE — MuninnDB REST client, dual-write capture, parallel search, activate tool, 32 memories seeded, human-verified (2026-03-05)
Last activity: 2026-03-05 — Phase 4.1 MuninnDB integration complete, all 6 MUNINN requirements satisfied

## Next Session: What to Do

1. Continue Phase 4 — next sub-phase 4.2 (Google Calendar) — run `/gsd:plan-phase`
2. Export patches before daughter re-initializes repo: `git format-patch feature/agent-scheduler..zbrain -o zbrain-patches/`
3. Continue onboarding conversations -- profile is growing, keep feeding it
4. Monitor MuninnDB embedder fix -- semantic_similarity currently 0 (v1beta API issue)

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

## Accumulated Context

### Roadmap Evolution

- Phase 03.1 inserted after Phase 3: Onboarding Module (URGENT)

## Blockers

None.

## Upcoming Events

- **Promaia re-init (within ~1 week):** Daughter re-initializing repo. Export patches before: `git format-patch feature/agent-scheduler..zbrain -o zbrain-patches/`

## Phase 2 Progress (2026-03-05)

| Plan | What it did |
|------|------------|
| 02-01 | Created brain schema (7 tables, HNSW+GIN), engine.py (8 deterministic functions), extended db_init.py with apply_brain_schema() |
| 02-02 | Brain MCP server (7 tools), extraction.py (instructor + Gemini Flash), requirements.txt updated |
| 02-03 | CLAUDE.md (proactive brain instructions), .mcp.json (stdio MCP registration), seed.py (10 domains, 5 contexts), end-to-end verified — COMPLETE |

## Key Execution Decisions (2026-03-05)

- **brain.* schema:** All 7 tables in dedicated Postgres schema (not public) — prevents naming collisions
- **Guardrail pattern fix:** Separated 'main' and 'master' into individual single-term patterns — required for correct blocking of "push to main"
- **suggest_next staleness cap:** 2.0 ceiling prevents severely stale domains from dominating energy-adjusted scoring
- **apply_brain_schema() autocommit:** Matches existing init_database() pattern, executes each DDL statement independently
- **instructor fallback:** instructor.from_genai() primary; falls back to raw Gemini JSON mode + Pydantic model_validate_json() if fails
- **Lazy DB singletons in MCP:** get_db()/get_vector_mgr() deferred to first tool call — avoids connection startup at import time
- **Embedding failure non-fatal in capture:** Memory row persisted even if embedding generation fails (embedding=NULL)
- **Briefing event idempotency:** Checks brain.events for same session_id + date before inserting briefing event
- **CLAUDE.md at repo root:** Claude Code picks up CLAUDE.md from project root automatically — applies to all sessions in this repo
- **seed.py fetch-after-upsert:** INSERT ON CONFLICT DO NOTHING, then SELECT for domain_id — cleaner than ON CONFLICT DO UPDATE RETURNING
- **Context existence check:** brain.contexts uses explicit SELECT before INSERT (no unique constraint on domain_id to leverage ON CONFLICT)

## Phase 03.1 Progress (2026-03-05)

| Plan | What it did |
|------|------------|
| 03.1-01 | Onboarding state engine: 2 new tables (onboarding_sessions, onboarding_progress), onboarding.py (5 functions), onboard MCP tool (10th tool), deployed to Supabase |
| 03.1-02 | PC scan channel (git analysis, file structure, Windows apps), Gmail read channel (contacts, patterns, topics), pc_scan + gmail_scan MCP tools (12 total) |
| 03.1-03 | Interview question bank (16 questions, 9 categories, OARS technique), interview orchestration, CLAUDE.md onboarding instructions, human-verified APPROVED |

## Key Execution Decisions (Phase 03.1, 2026-03-05)

- **EXPECTED_FIELDS constant:** 10 categories, 48 fields total for profile gap analysis
- **Session reuse:** start_onboarding returns existing active session instead of creating duplicates
- **Paused auto-reactivate:** Paused sessions set back to 'active' on start
- **Single MCP tool pattern:** One 'onboard' tool with action parameter, not 4 separate tools
- **No db_init.py changes:** apply_brain_schema() reads full schema.sql dynamically, new DDL picked up automatically
- **Registry query for Windows apps:** reg query instead of deprecated wmic for installed app detection
- **Gmail metadata-only format:** thread fetch with format="metadata" + metadataHeaders for privacy-first scanning
- **Differentiated confidence:** PC scan 0.6, Gmail scan 0.5 — email patterns less direct than git timestamps
- **Channel module pattern:** standalone run_*() functions that accept db param and return result dicts
- **Question bank 4-phase arc:** warm_up, current_state, gap_identification, commitment -- matches motivational interviewing structure
- **Interview module is a selector:** Provides next question, does NOT drive conversation -- Claude uses CLAUDE.md instructions for that
- **Design Principles (not ADHD-Friendly):** Short bursts, auto-save, no shame framing are the default style, not a special accommodation
- **User verification positive:** Onboarding captures both stated and implied information effectively

## Phase 4.1 Progress (2026-03-05)

| Plan | What it did |
|------|------------|
| 4.1-01 | MuninnDB REST client (muninn.py, 170 lines), dual-write capture, parallel pgvector+ACTIVATE search, activate MCP tool (#13), 32 memories seeded, human-verified APPROVED |

## Key Execution Decisions (Phase 4.1, 2026-03-05)

- **httpx REST client over SDK:** muninndb Python SDK broken on 3.14 (zero code files installed). Direct REST via httpx is reliable.
- **write_batch vault workaround:** Batch endpoint ignores vault field (MuninnDB v0.3.6-alpha bug). Sequential individual POST calls used instead.
- **Best-effort dual-write:** MuninnDB failure in capture never blocks Postgres or changes return value. try/except after all Postgres ops.
- **Async lazy singleton (get_muninn):** One-time health check on first call, cached result. Prevents repeated connection attempts when MuninnDB is down.
- **Embedder limitation accepted:** semantic_similarity=0 due to text-embedding-004 not available on v1beta API. MuninnDB config issue, not code issue. User approved.

## Git State

- Branch: `zbrain` (off `feature/agent-scheduler`)
- Phase 1 commits: cbad997 through e5fd713 (10 commits)
- Phase 2 commits: b0031df (02-01 schema), a2d1c65 (02-01 engine), 15eb7c5 (02-02 extraction), d3517b1 (02-02 mcp_server), 0fae709 (02-03 CLAUDE.md+.mcp.json+seed)
- Phase 03.1 commits: e329a33 (03.1-01 schema+engine), 456adfe (03.1-01 mcp_server), 551c08c (03.1-02 pc_scan), 613bcc7 (03.1-02 gmail_read), 0e6fa6d (03.1-02 mcp tools), e00e58b (03.1-03 question bank+interview), a8613e9 (03.1-03 CLAUDE.md instructions), fc9605e (03.1-03 rename Design Principles)
- Phase 4.1 commits: 180e04e (4.1-01 muninn.py), 9071754 (4.1-01 mcp_server 13 tools), d5ea814 (4.1-01 write_batch fix)
