# zBrain (Promaia Fork)

## What This Is

A personal AI operating system built on top of Promaia — Zack's daughter's content management and agent platform. zBrain extends Promaia with proactive memory, autonomous agents, intelligent model routing, and cloud-native storage. It's the system that remembers everything, keeps projects moving, and works while Zack sleeps.

## Core Value

Claude has persistent, cross-session memory across all of Zack's projects and life domains — eliminating the "amnesia problem" where every session starts from scratch.

## Current Milestone: v1.0 zBrain Foundation

**Goal:** Extend Promaia with cloud storage, proactive brain, Gemini routing, and autonomous heartbeat agent.

**Target features:**
- Postgres/pgvector on Supabase (completing daughter's started migration)
- Proactive brain layer (briefings, action extraction, directives)
- Gemini as first-class model (not just fallback)
- Heartbeat agent (autonomous overnight work)

## Requirements

### Validated

<!-- Inherited from Promaia — these already work and we don't touch them -->

- [x] Multi-source content sync (Notion, Gmail, Discord)
- [x] Hybrid storage with SQL + vector search
- [x] AI-powered chat with synced content
- [x] Natural language query orchestrator (NL → SQL/vector)
- [x] Multi-workspace support
- [x] Agent orchestration architecture (intent classifier, context serializer, agent spawner)
- [x] Multi-model LLM adapter (Claude primary, OpenAI/Gemini fallback)
- [x] CLI interface (`maia sync`, `maia chat`, `maia workspace`)
- [x] MCP server integration (Gmail, Notion, Filesystem, Git, SQLite)
- [x] Connector plugin architecture (BaseConnector → register new sources)

### Active

<!-- Current scope — zBrain v1.0 -->

- [ ] Postgres + pgvector backend (replacing SQLite + ChromaDB)
- [ ] Brain schema (memories, domains, contexts, actions, reviews)
- [ ] Session briefing (auto on startup)
- [ ] Action extraction (auto from conversations)
- [ ] Standing directives per project
- [ ] Stale project alerts
- [ ] Gemini model routing (specialist, not fallback)
- [ ] Brain ingestion from Gemini research/YouTube/docs
- [ ] Heartbeat agent (autonomous overnight work)
- [ ] iPhone access via cloud endpoint

### Out of Scope

<!-- Explicit boundaries for v1.0 -->

- Google Calendar integration — deferred to v1.1, noted as priority
- Email/message triage — future layer, needs brain foundation first
- Kanban board UI — future, brain must exist before visualization
- Obsidian sync — nice-to-have, not blocking (brain is primary, Obsidian is review layer)
- Desktop Electron app — daughter's domain, not zBrain's focus
- React web chat app — daughter's domain
- OpenAI API dependency — replacing with Gemini where Promaia used OpenAI

## Context

**Promaia (upstream):** Python-based content management platform built by Zack's daughter. 359 files, ~15K+ lines. Has connectors for Notion/Gmail/Discord, hybrid SQLite+ChromaDB storage, agent orchestration (in development), multi-model support, CLI + desktop + web interfaces. Default branch: `feature/agent-scheduler`.

**Existing Postgres work:** Daughter started `postgres-sql-changeover` branch — 586-line schema, `PostgresDB` singleton with connection pooling, migrations for all content tables. Targets local Postgres (`192.168.0.69`). zBrain will complete this, pointing at Supabase.

**Supabase:** Existing Pro plan ($27.49/mo), project `dulqttfidcjeujyieuqw`. Already has 37+ tables for Heatpup. zBrain uses a separate `brain` schema alongside.

**Inspiration sources:** Nate Jones Open Brain (Postgres+pgvector+MCP), OpenClaw heartbeat system (autonomous agents), 5 YouTube videos analyzed in previous session.

**User work patterns:** Zack is an HVAC salesperson, captures ideas by voice on iPhone while driving, bounces between topics, doesn't use calendars/to-do apps. Wants AI with drive, not another passive tool. Frustrated by AI amnesia.

**Collaboration model:** Branch & contribute back. Zack builds on `zbrain` branch of `commodorebob/promaia`. Daughter cherry-picks features she wants for main platform.

## Constraints

- **Cost**: No new API subscriptions. Use existing Claude Max ($199/mo), Google AI Premium ($125/mo), Supabase Pro ($27.49/mo). New cost max $4/mo (Obsidian Sync).
- **Platform**: Windows 11, Claude Code CLI. Heartbeat uses Windows Task Scheduler.
- **Anthropic ToS**: All Claude usage through official channels (Claude Max, Claude Code CLI). No workarounds.
- **Upstream compatibility**: Changes should be mergeable back to Promaia. Don't break existing features.
- **Python**: Promaia is Python 3.8+. Stay in Python ecosystem for backend.
- **iPhone day-1**: Brain must be accessible from iPhone (claude.ai) from the start. Drives cloud-first architecture.
- **Embeddings**: Google text-embedding-004 (not OpenAI). Covered by existing Google AI Premium.

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Build on Promaia, not from scratch | Daughter built 70% of needed infrastructure. Collaboration opportunity. | — Pending |
| Single `zbrain` branch | Simple git workflow, easy PR back. Not per-feature branches. | — Pending |
| Supabase over local Postgres | iPhone day-1 requirement. Cloud-native. Already paying for Pro. | — Pending |
| pgvector over ChromaDB | Cloud-native, no local files, SQL-queryable, same DB as content. | — Pending |
| Gemini over OpenAI for cheap tasks | Already paying for Google AI Premium. No new API costs. | — Pending |
| Google text-embedding-004 | Covered by existing subscription. Good quality. Not OpenAI. | — Pending |
| Brain schema separate from Promaia tables | `brain.*` schema doesn't touch `public.*`. Clean separation. | — Pending |

---
*Last updated: 2026-03-04 after initial milestone definition*
