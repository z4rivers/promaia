# Milestones

## v1.0 zBrain Foundation (2026-03-06)

**Phases:** 4 | **Plans:** 11 | **Commits:** 63 | **Lines:** +20,643

Built persistent brain layer on Promaia: Postgres+pgvector on Supabase, 15-tool MCP brain server, ambient onboarding with 98 profile traits, MuninnDB cognitive memory sidecar, 3-agent scheduler via Claude SDK, web dashboard with live data.

**Key accomplishments:**
1. Cloud-native Postgres+pgvector replacing SQLite+ChromaDB
2. Brain MCP server (15 tools: briefing, capture, search, recall, profile, onboard)
3. Ambient onboarding interview capturing 98 profile traits
4. MuninnDB cognitive memory with dual-write pattern
5. Agent scheduler: morning-briefing, email-triage, evening-digest running via SDK
6. Web dashboard (5 pages, Superflat skin, live Postgres data)

**Known gaps carried to v2:**
- Model routing (all agents use Opus, no cost optimization)
- Mobile access (no Telegram, no phone interface)
- Self-maintenance (no dependency monitoring)
- MuninnDB embeddings broken (deprecated model)

**Archive:** `milestones/v1.0-ROADMAP.md`, `milestones/v1.0-REQUIREMENTS.md`
