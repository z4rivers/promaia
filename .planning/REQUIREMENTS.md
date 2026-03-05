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

- [ ] **DOCS-01**: ZBRAIN.md in repo root — running changelog of all changes for daughter's visibility
- [ ] **DOCS-02**: Every commit has clear message explaining what changed and why
- [ ] **DOCS-03**: Modified upstream files documented in ZBRAIN.md with reasoning

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

**Coverage:**
- v1.0 requirements: 24 total
- Mapped to phases: 6 (Phase 2, Plans 01-02)
- Complete: 11 (5 STOR, 6 BRAIN)

---
*Requirements defined: 2026-03-04*
*Last updated: 2026-03-05 after 02-02 execution*
