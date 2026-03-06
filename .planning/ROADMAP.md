# Roadmap: zBrain v1.0 Foundation

## Phases

- [x] **Phase 1: Postgres Foundation** - Supabase/pgvector backend replacing SQLite+ChromaDB (2026-03-04)
- [x] **Phase 2: Brain Schema and MCP Tools** - Proactive brain layer with memories, domains, actions, briefings (completed 2026-03-05)
- [ ] **Phase 3: Gemini Routing** - Intelligent model router and brain ingestion pipeline
- [x] **Phase 03.1: Onboarding Module** - Guided personal profile interview with reciprocal AI disclosure (2026-03-05)
- [ ] **Phase 4: Full Platform Activation** - Activate ALL Promaia modules + MuninnDB cognitive memory
  - [x] 4.1: MuninnDB Install + Seed (cognitive memory sidecar) (2026-03-05)
  - [ ] 4.2: Google Calendar Setup (schedule awareness)
  - [ ] 4.3: Notion Dashboard Setup (visibility layer)
  - [ ] 4.4: Agent Scheduler Activation (the heartbeat)
  - [ ] 4.5: Full Email Pipeline (mail/ module + gmail_read.py)
  - [ ] 4.6: Web/Chat Interface (iPhone access)
  - [ ] 4.7: Information Funneling (intelligence briefs)
  - [ ] 4.8: Webflow CMS (when needed)
- [ ] **Phase 5: iPhone Access** - Mobile brain access via cloud endpoint (merged into 4.6)

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
**Requirements:** [ONBOARD-01 through ONBOARD-10]
**Plans:** 3/3 plans complete

Plans:
- [x] 03.1-01-PLAN.md -- Onboarding state schema + engine + onboard MCP tool (2026-03-05)
- [x] 03.1-02-PLAN.md -- PC scan and Gmail read channel modules + MCP tools (2026-03-05)
- [x] 03.1-03-PLAN.md -- Interview question bank + CLAUDE.md onboarding instructions + human-verified (2026-03-05)

### Phase 4: Full Platform Activation

**Goal:** Activate ALL major Promaia modules for Zack's use case, integrate MuninnDB cognitive memory, establish the complete autonomous AI assistant stack.
**Depends on:** Phase 2
**Full plan:** `.planning/phases/04-full-platform-activation/ACTIVATION-PLAN.md`

**Sub-phases:**

#### 4.1: MuninnDB Cognitive Memory
**Goal:** Integrate MuninnDB as cognitive memory sidecar with dual-write capture, parallel search retrieval, and dedicated ACTIVATE tool for associative recall
**Depends on:** Phase 2
**Requirements:** [MUNINN-01, MUNINN-02, MUNINN-03, MUNINN-04, MUNINN-05, MUNINN-06]
**Success Criteria** (what must be TRUE):
  1. MuninnDB REST client wrapper exists (promaia/brain/muninn.py)
  2. Capture dual-writes to both Postgres and MuninnDB (MuninnDB best-effort)
  3. Search returns labeled results from both pgvector and MuninnDB ACTIVATE
  4. Dedicated activate MCP tool provides cognitive retrieval with score components
  5. All existing brain.memories seeded into MuninnDB zbrain-vault
  6. MuninnDB failures never block Postgres operations (graceful degradation)
**Plans:** 1/1 plans complete

Plans:
- [x] 4.1-01-PLAN.md -- MuninnDB REST client, dual-write capture, parallel search, activate tool, seed memories, end-to-end verification (2026-03-05)

#### 4.2: Google Calendar
Enable Calendar API, OAuth scope, wire to agents. Brain knows the schedule.

#### 4.3: Notion Dashboard
Set up Notion as visibility layer. Agent output pages, brain dashboard, profile view. Notion displays, MuninnDB thinks.

#### 4.4: Agent Scheduler
Activate the heartbeat. Morning Briefing, Email Triage, Evening Digest agents. Autonomous operation via scheduler daemon.

#### 4.5: Full Email Pipeline
Wire gmail_read.py into existing mail/ module (classifier, intent detector, response generator, draft manager). All 4 Gmail layers operational.

#### 4.6: Web/Chat Interface (iPhone Access)
Deploy FastAPI chat server to cloud. Brain accessible from phone. Voice capture while driving.

#### 4.7: Information Funneling
Curate information sources, filter by brain profile, form into regular intelligence briefs. Not newsletters — intelligence delivery.

#### 4.8: Webflow CMS
Activate when needed for Heatpup or other web publishing.

## Progress

| Phase | Plans Complete | Status | Completed |
|-------|---|---|---|
| 1. Postgres Foundation | 3/3 | Complete | 2026-03-04 |
| 2. Brain Schema and MCP Tools | 3/3 | Complete    | 2026-03-05 |
| 3. Gemini Routing | 0/0 | Not started | - |
| 3.1 Onboarding Module | 3/3 | Complete | 2026-03-05 |
| 4. Full Platform Activation | 1/8 | In Progress | - |
| 4.1 MuninnDB | 1/1 | Complete | 2026-03-05 |
| 4.2 Google Calendar | - | Ready | - |
| 4.3 Notion Dashboard | - | Ready | - |
| 4.4 Agent Scheduler | - | Depends on 4.2+4.3 | - |
| 4.5 Email Pipeline | - | Ready | - |
| 4.6 Web/Chat (iPhone) | - | Ready | - |
| 4.7 Info Funneling | - | Depends on 4.4 | - |
| 4.8 Webflow CMS | - | When needed | - |

---
*Created: 2026-03-04 from design docs*
*Updated: 2026-03-05 — Phase 4 added after full module audit*
*Updated: 2026-03-05 — Phase 4.1 MuninnDB planned (1 plan)*
*Updated: 2026-03-05 — Phase 4.1 MuninnDB complete (1/1 plans, 6 MUNINN requirements satisfied)*
