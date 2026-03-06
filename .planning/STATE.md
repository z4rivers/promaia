# State: zBrain

## Current Position

Phase: Not started (defining requirements)
Plan: --
Status: Defining requirements for v2.0 Proactive Agent
Last activity: 2026-03-06 -- Milestone v2.0 started

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-06)

**Core value:** Proactive AI assistant that reaches YOU
**Current focus:** v2.0 Proactive Agent — defining requirements

## What's Live

- Brain MCP server: 15 tools, 56+ memories, 10 domains, 98 profile traits
- Agent scheduler: PID running, 3 agents (morning-briefing, email-triage, evening-digest)
- Agent cost: ~$0.011/run via Claude SDK
- Web dashboard: localhost:8000, 5 pages, Superflat skin
- Gmail pipeline: OAuth working, emails ingested

## Known Issues (carry to v2)

- MuninnDB embeddings broken (text-embedding-004 deprecated)
- Gmail context loading in agents (needs Postgres fallback)
- SQL dialect bugs (jsonb operators, timestamp casting)
- unified_content SQLite table reference leaking into Postgres
- Agent token tracking shows $0.00 in legacy mode

## Git State

- Branch: `zbrain` (off `feature/agent-scheduler`)
- Tag: v1.0 (pending)
- Patches: 68 exported to `zbrain-patches/`

## Decisions

(Cleared for v2 -- full log in milestones/v1.0-ROADMAP.md)

## Blockers

(None -- ready for v2 planning)
