# Requirements: zBrain (Promaia Fork)

**Defined:** 2026-03-04
**Core Value:** Claude has persistent, cross-session memory across all of Zack's projects — eliminating the amnesia problem.

## v1.0 Requirements

### Storage

- [x] **STOR-01**: System connects to Supabase Postgres via session pooler
- [x] **STOR-02**: pgvector replaces ChromaDB for all vector operations (HNSW indexes)
- [x] **STOR-03**: Google gemini-embedding-001 generates embeddings (768 dims)
- [x] **STOR-04**: Existing Promaia features (sync, chat, query) work against Postgres
- [x] **STOR-05**: google-generativeai migrated to google-genai SDK

### Brain

- [x] **BRAIN-01**: Brain schema stores memories with embeddings (semantic search) — brain.memories with vector(768) + HNSW (02-01)
- [x] **BRAIN-02**: Domains represent life categories and projects — brain.domains with hierarchical parent_domain FK (02-01)
- [x] **BRAIN-03**: Standing directives per project define direction, not task lists — brain.contexts with directive + stale_threshold_days (02-01)
- [x] **BRAIN-04**: Actions auto-extracted from conversations with status tracking
- [x] **BRAIN-05**: Session briefing runs automatically on startup (stalled projects, pending actions, recent activity)
- [x] **BRAIN-06**: Stale alerts flag projects with no activity past threshold — suggest_next() in engine.py scores by staleness ratio (02-01)

### Onboarding (INSERTED — Phase 03.1)

- [x] **ONBOARD-01**: Onboarding session state persists across sessions (start, pause, resume, complete)
- [x] **ONBOARD-02**: Profile coverage report shows per-category gap analysis against expected schema
- [x] **ONBOARD-03**: Onboard MCP tool manages onboarding flow (start/status/channel_update/complete)
- [x] **ONBOARD-04**: PC scan channel extracts profile data from local git repos, file structure, installed apps
- [x] **ONBOARD-05**: Gmail read channel extracts contacts, communication patterns, topics from inbox
- [x] **ONBOARD-06**: Channel tools (pc_scan, gmail_scan) registered as MCP tools in brain server
- [x] **ONBOARD-07**: Interview question bank covers all profile categories with OARS-informed questions
- [x] **ONBOARD-08**: Interview orchestration selects next question based on profile coverage gaps
- [x] **ONBOARD-09**: CLAUDE.md contains onboarding instructions: reciprocal disclosure, progressive profiling, design principles
- [x] **ONBOARD-10**: Onboarding follows design principles: short bursts, instant value, resumable, no shame

### Routing

- [ ] **ROUTE-01**: Task-based model router (ai/router.py) assigns models by task type
- [ ] **ROUTE-02**: Gemini Flash handles cheap tasks (classification, summarization, embeddings)
- [ ] **ROUTE-03**: Claude Sonnet/Opus handles reasoning and interactive work
- [ ] **ROUTE-04**: Gemini MCP tools feed research results into brain automatically

### Heartbeat

- [ ] **BEAT-01**: Windows Task Scheduler runs heartbeat script on configurable interval
- [ ] **BEAT-02**: Heartbeat scans all projects, deep-works on most stalled
- [ ] **BEAT-03**: Heartbeat uses claude CLI subprocess (Anthropic ToS compliant)
- [ ] **BEAT-04**: Safety guardrails — branch-only commits, logging, budget cap, max runtime
- [ ] **BEAT-05**: Morning summary available in next session briefing

### Access

- [ ] **ACCESS-01**: Brain accessible from iPhone via cloud endpoint (Supabase is cloud-native)

### Documentation

- [x] **DOCS-01**: ZBRAIN.md in repo root — running changelog of all changes for daughter's visibility
- [x] **DOCS-02**: Every commit has clear message explaining what changed and why
- [x] **DOCS-03**: Modified upstream files documented in ZBRAIN.md with reasoning

### Self-Maintenance

- [ ] **MAINT-01**: Dependency intelligence monitors stack for updates (PyPI, GitHub releases)
- [ ] **MAINT-02**: Evaluates update relevance — flags new capabilities that enable features, not just version bumps (Green Hat thinking)
- [ ] **MAINT-03**: Catches deprecations early — alerts before EOL dates hit (prevents google-generativeai situation)
- [ ] **MAINT-04**: Logs findings to brain.events with actionable recommendations

## v1.1 Requirements (Deferred)

- **CAL-01**: Google Calendar integration for time management
- **TRIAGE-01**: Email/message triage automation
- **VIZ-01**: Kanban board visualization per project
- **SYNC-01**: Obsidian sync layer for human review

## Out of Scope

| Feature | Reason |
|---------|--------|
| Desktop Electron app | Daughter's domain |
| React web chat app | Daughter's domain |
| OpenAI API dependency | Replacing with Gemini everywhere |
| Real-time conversation monitoring | Cost/complexity anti-pattern (research) |
| Continuous background embedding | Token burn anti-pattern (research) |
| Email triage in v1 heartbeat | Needs stable brain foundation first |

## Traceability

<!-- Updated during roadmap creation -->

| Requirement | Phase | Status |
|-------------|-------|--------|
| BRAIN-01 | 02-01 | Complete |
| BRAIN-02 | 02-01 | Complete |
| BRAIN-03 | 02-01 | Complete |
| BRAIN-06 | 02-01 | Complete |
| BRAIN-04 | 02-02 | Complete |
| BRAIN-05 | 02-02 | Complete |
| ONBOARD-01 | 03.1-01 | Complete |
| ONBOARD-02 | 03.1-01 | Complete |
| ONBOARD-03 | 03.1-01 | Complete |
| ONBOARD-04 | 03.1-02 | Complete |
| ONBOARD-05 | 03.1-02 | Complete |
| ONBOARD-06 | 03.1-02 | Complete |
| ONBOARD-07 | 03.1-03 | Complete |
| ONBOARD-08 | 03.1-03 | Complete |
| ONBOARD-09 | 03.1-03 | Complete |
| ONBOARD-10 | 03.1-03 | Complete |

**Coverage:**
- v1.0 requirements: 34 total (24 original + 10 onboarding)
- Mapped to phases: 26 (6 BRAIN, 10 ONBOARD, 5 STOR, 3 DOCS, 2 mapped)
- Complete: 21 (5 STOR, 6 BRAIN, 10 ONBOARD)

---
*Requirements defined: 2026-03-04*
*Last updated: 2026-03-05 after 03.1-03 complete (all ONBOARD requirements satisfied)*
