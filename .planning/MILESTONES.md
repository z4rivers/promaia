# Milestones

## v1.0 zBrain Foundation (2026-03-06)

**Phases:** 4 | **Plans:** 11 | **Commits:** 63 | **Lines:** +20,643

Built persistent brain layer on Promaia: libSQL/MuninnDB+pgvector on Railway Volumes, 15-tool MCP brain server, ambient onboarding with 98 profile traits, MuninnDB cognitive memory sidecar, 3-agent scheduler via Claude SDK, web dashboard with live data.

**Key accomplishments:**
1. Cloud-native libSQL/MuninnDB+pgvector replacing SQLite+ChromaDB
2. Brain MCP server (15 tools: briefing, capture, search, recall, profile, onboard)
3. Ambient onboarding interview capturing 98 profile traits
4. MuninnDB cognitive memory with dual-write pattern
5. Agent scheduler: morning-briefing, email-triage, evening-digest running via SDK
6. Web dashboard (5 pages, Superflat skin, live libSQL/MuninnDB data)

**Known gaps carried to v2:**
- Model routing (all agents use Opus, no cost optimization)
- Mobile access (no Telegram, no phone interface)
- Self-maintenance (no dependency monitoring)
- MuninnDB embeddings broken (deprecated model)

**Archive:** `milestones/v1.0-ROADMAP.md`, `milestones/v1.0-REQUIREMENTS.md`

## v2.0 Proactive Agent (2026-03-07)

**Phases:** 7 (5-11) | **Plans:** 17

The brain reaches you. Agents push to Telegram, conversation is Gemini-powered with full brain context, costs tracked and optimized.

**Key accomplishments:**
1. Agent data pipeline validated — real data, no hallucinations (Phase 5)
2. Gemini model routing with 91% cost reduction vs Claude (Phase 6)
3. Event bus with urgency tiers, quiet hours, dashboard badges (Phase 7)
4. Telegram bot — text, voice, commands, daemon with auto-reconnect (Phase 8)
5. Proactive push — morning briefing, urgent alerts, evening digest arrive automatically (Phase 9)
6. Conversational Telegram — Gemini-powered responses with personality, context assembly, session synthesis (Phase 11)

**Deferred:**
- Phase 10 (Memory Deepening) — blocked on MuninnDB embedding fix, deferred to v3.1+

**Archive:** `ROADMAP.md` (v2.0 section), `REQUIREMENTS.md`, `phases/05-11`
