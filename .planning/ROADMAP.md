# Roadmap: zBrain v1.0 Foundation

## Phases

- [x] **Phase 1: Postgres Foundation** - Supabase/pgvector backend replacing SQLite+ChromaDB (2026-03-04)
- [x] **Phase 2: Brain Schema and MCP Tools** - Proactive brain layer with memories, domains, actions, briefings (completed 2026-03-05)
- [ ] **Phase 3: Gemini Routing** - Intelligent model router and brain ingestion pipeline
- [ ] **Phase 03.1: Onboarding Module** - Guided personal profile interview with reciprocal AI disclosure (INSERTED)
- [ ] **Phase 4: Heartbeat Agent** - Autonomous overnight work loop with guardrails
- [ ] **Phase 5: iPhone Access** - Mobile brain access via cloud endpoint

## Phase Details

### Phase 1: Postgres Foundation
**Goal:** Replace SQLite+ChromaDB with Supabase Postgres+pgvector so all data is cloud-native and accessible from any device
**Depends on:** Nothing
**Requirements:** [STOR-01, STOR-02, STOR-03, STOR-04, STOR-05, DOCS-01, DOCS-02, DOCS-03]
**Success Criteria** (what must be TRUE):
  1. Promaia connects to Supabase Postgres via session pooler
  2. pgvector extension enabled with vector(768) columns and HNSW indexes
  3. All existing Promaia features (sync, chat, query) work against Postgres
  4. ChromaDB dependency removed; vector_db.py uses pgvector adapter
  5. Existing content re-embedded with gemini-embedding-001
  6. GIN indexes on tags/entities for hybrid search
  7. google-generativeai replaced with google-genai SDK
  8. ZBRAIN.md created documenting all changes
**Plans:** 3 plans

Plans:
- [x] 01-01-PLAN.md -- Merge postgres branch, configure Supabase, extend schema with pgvector + indexes (CHECKPOINT: awaiting Supabase deployment verification)
- [x] 01-02-PLAN.md -- Replace ChromaDB with pgvector in vector_db.py, migrate google-genai SDK, update requirements
- [x] 01-03-PLAN.md -- Re-embed migration script, end-to-end verification, ZBRAIN.md changelog

### Phase 2: Brain Schema and MCP Tools
**Goal:** Add proactive brain layer — memories, domains, contexts, actions, reviews, events tables plus MCP tools for briefing, capture, search, and system instructions
**Depends on:** Phase 1
**Requirements:** [BRAIN-01, BRAIN-02, BRAIN-03, BRAIN-04, BRAIN-05, BRAIN-06]
**Success Criteria** (what must be TRUE):
  1. Brain schema tables created (memories, domains, contexts, actions, reviews, events, modes)
  2. MCP tools working: briefing, capture, search, recall, context, update_context, actions
  3. Session briefing runs automatically on startup
  4. Action extraction detects actionable items from conversation
  5. Standing directives per project stored and queryable
  6. Stale project alerts surface in briefings
  7. brain/engine.py deterministic functions operational (mode detection, guardrails, time tracking, budget, context save/restore)
**Plans:** 3/3 plans complete

Plans:
- [x] 02-01-PLAN.md -- Brain schema SQL (7 tables) + engine.py (8 deterministic functions) + db_init extension (2026-03-05)
- [x] 02-02-PLAN.md -- MCP server (7 tools: briefing, capture, search, recall, context, update_context, actions) + action extraction with instructor (2026-03-05)
- [x] 02-03-PLAN.md -- CLAUDE.md system instructions + .mcp.json registration + seed data + end-to-end verification (2026-03-05)

### Phase 3: Gemini Routing
**Goal:** Intelligent model routing so each model handles what it's best at, plus brain ingestion from Gemini research tools
**Depends on:** Phase 2
**Requirements:** [ROUTE-01, ROUTE-02, ROUTE-03, ROUTE-04]
**Success Criteria** (what must be TRUE):
  1. ai/router.py routes tasks to appropriate model by type
  2. Gemini Flash handles classification, summarization, embeddings
  3. Claude Sonnet/Opus handles reasoning and interactive work
  4. Gemini MCP research results automatically captured into brain.memories
  5. YouTube analysis and deep research feed brain automatically
**Plans:** TBD

### Phase 03.1: Onboarding Module (INSERTED)

**Goal:** Guided "getting to know you" interview with reciprocal AI disclosure, progressive profiling, and multi-channel onboarding (interview, PC scan, Gmail, photos)
**Depends on:** Phase 2
**Requirements:** [ONBOARD-01, ONBOARD-02, ONBOARD-03, ONBOARD-04, ONBOARD-05, ONBOARD-06, ONBOARD-07, ONBOARD-08, ONBOARD-09, ONBOARD-10]
**Success Criteria** (what must be TRUE):
  1. Onboarding session can be started, paused, and resumed across sessions
  2. Profile coverage report shows per-category gap analysis
  3. PC scan channel automatically extracts profile data from local files and git history
  4. Gmail read channel extracts contacts and communication patterns (when OAuth configured)
  5. Interview question bank covers all profile categories with OARS-informed questions
  6. Claude follows onboarding instructions: one question at a time, reciprocal disclosure, ADHD-friendly
  7. Progressive profiling continues after initial interview via observation
**Plans:** 1/3 plans executed

Plans:
- [ ] 03.1-01-PLAN.md -- Onboarding state schema + engine + onboard MCP tool
- [ ] 03.1-02-PLAN.md -- PC scan and Gmail read channel modules + MCP tools
- [ ] 03.1-03-PLAN.md -- Interview question bank + CLAUDE.md onboarding instructions + verification

### Phase 4: Heartbeat Agent
**Goal:** Autonomous overnight agent that scans all projects, deep-works on the most stalled, and reports in morning briefing
**Depends on:** Phase 2
**Requirements:** [BEAT-01, BEAT-02, BEAT-03, BEAT-04, BEAT-05]
**Success Criteria** (what must be TRUE):
  1. Windows Task Scheduler runs heartbeat on configurable interval
  2. Heartbeat scans all projects and picks most stalled for deep work
  3. Active user check: scan-only mode if user active within 15 min
  4. Safety guardrails enforced: branch-only commits, no external comms, max 2 commits, budget cap, 30-min runtime
  5. Morning summary available in next session briefing
  6. All activity logged to brain.events with source="heartbeat"
**Plans:** TBD

### Phase 5: iPhone Access
**Goal:** Brain accessible from iPhone so mobile captures flow into the shared brain and briefings work on any device
**Depends on:** Phase 2
**Requirements:** [ACCESS-01]
**Success Criteria** (what must be TRUE):
  1. Brain MCP endpoint accessible from iPhone via cloud
  2. Mobile capture stores thoughts in brain.memories
  3. PC session briefing picks up mobile captures automatically
**Plans:** TBD

## Progress

| Phase | Plans Complete | Status | Completed |
|-------|---|---|---|
| 1. Postgres Foundation | 3/3 | Complete | 2026-03-04 |
| 2. Brain Schema and MCP Tools | 3/3 | Complete    | 2026-03-05 |
| 3. Gemini Routing | 0/0 | Not started | - |
| 3.1 Onboarding Module | 0/3 | Planned | - |
| 4. Heartbeat Agent | 0/0 | Not started | - |
| 5. iPhone Access | 0/0 | Not started | - |

---
*Created: 2026-03-04 from design docs*
*Design docs: docs/plans/2026-03-04-zbrain-promaia-merge-design.md, docs/plans/2026-03-04-zbrain-workflow-design.md*
