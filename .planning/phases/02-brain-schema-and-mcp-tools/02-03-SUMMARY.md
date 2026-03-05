---
phase: 02-brain-schema-and-mcp-tools
plan: 03
subsystem: infra
tags: [mcp, claude, brain, zBrain, postgres, seed-data, system-instructions]

# Dependency graph
requires:
  - phase: 02-02
    provides: brain MCP server (7 tools), extraction.py (instructor + Gemini Flash)
  - phase: 02-01
    provides: brain schema (7 tables), engine.py (8 deterministic functions)
provides:
  - CLAUDE.md with proactive brain system instructions (briefing/capture/context/ambient/energy)
  - .mcp.json registering brain MCP server for project-scoped stdio transport
  - promaia/brain/seed.py with 10 domains and 5 contexts (idempotent)
  - Brain layer verified end-to-end: schema deployed, seed data populated, MCP server connected in Claude Code
affects: [03-heartbeat, all-future-sessions]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - System instructions pattern: CLAUDE.md at repo root triggers proactive MCP tool calls
    - .mcp.json stdio registration pattern: project-scoped MCP server with env var passthrough
    - Idempotent seed pattern: INSERT ... ON CONFLICT (name) DO NOTHING + fetch for domain_ids

key-files:
  created:
    - CLAUDE.md
    - .mcp.json
    - promaia/brain/seed.py
  modified: []

key-decisions:
  - "CLAUDE.md at repo root: project-scoped system instructions that Claude Code picks up automatically for all sessions in this repo"
  - "seed.py uses fetch-after-upsert pattern for domain IDs: INSERT ON CONFLICT DO NOTHING then SELECT — avoids needing RETURNING with ON CONFLICT"
  - "Context seeding uses explicit existence check rather than ON CONFLICT: brain.contexts has no unique constraint other than domain_id, so manual check is cleaner"

patterns-established:
  - "Seed script pattern: runnable as python -m promaia.brain.seed, uses get_postgres_db() singleton, idempotent via ON CONFLICT"
  - "MCP registration pattern: .mcp.json at repo root, stdio transport, env vars as ${VAR} references"

requirements-completed: [BRAIN-02, BRAIN-03, BRAIN-05]

# Metrics
duration: 3min
completed: 2026-03-05
---

# Phase 2 Plan 03: System Instructions, MCP Registration, and Seed Data Summary

**CLAUDE.md proactive brain instructions + .mcp.json stdio registration + idempotent seed.py for 10 domains and 5 contexts — brain layer fully wired and verified end-to-end**

## Performance

- **Duration:** 3 min
- **Started:** 2026-03-05T02:22:31Z
- **Completed:** 2026-03-05T02:25:00Z
- **Tasks:** 2/2
- **Files modified:** 3

## Accomplishments

- CLAUDE.md with 5 behavior sections: session start briefing, capture on thoughts, project context loading, ambient awareness, energy adaptation — all using mcp__brain__ tool names
- .mcp.json registering brain server as stdio transport with DATABASE_URL and GOOGLE_API_KEY env passthrough
- seed.py that populates 10 domains (7 projects, 3 non-projects) and 5 project contexts with directives, stale thresholds, and priorities — fully idempotent
- End-to-end verified: brain schema deployed to Supabase, seed data populated, MCP server starts and registers in Claude Code, briefing fires on session start

## Task Commits

Each task was committed atomically:

1. **Task 1: CLAUDE.md, .mcp.json, and seed data script** - `0fae709` (feat)
2. **Task 2: Verify brain MCP server starts and tools respond** - checkpoint:human-verify, approved by user

**Plan metadata:** (final docs commit — see below)

## Files Created/Modified

- `CLAUDE.md` - Proactive brain instructions: briefing on session start, capture on thoughts, context before project work, ambient awareness, energy adaptation
- `.mcp.json` - MCP server registration: stdio transport, python -m promaia.brain.mcp_server, DATABASE_URL + GOOGLE_API_KEY env
- `promaia/brain/seed.py` - Seed script: 10 domains (Heatpup, HVAC Brand, PURRfoot, Promaia, zBrain, Catpool, Hopecookie, Maybecat, HVAC Work, Personal) + 5 contexts with directives

## Decisions Made

- **CLAUDE.md at repo root:** Claude Code picks up CLAUDE.md from the project root automatically. Placing it here (not in promaia/) ensures it applies to all Claude Code sessions in this repo.
- **seed.py fetch-after-upsert pattern:** `INSERT ... ON CONFLICT (name) DO NOTHING` followed by `SELECT id` to get domain IDs. Cleaner than `INSERT ... ON CONFLICT DO UPDATE ... RETURNING id` which requires a dummy update.
- **Context existence check:** brain.contexts has no unique constraint other than foreign key on domain_id, so a manual `SELECT` before `INSERT` is used rather than ON CONFLICT — avoids schema assumption.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

User completed end-to-end verification:

1. Applied brain schema: `python -c "from promaia.storage.db_init import apply_brain_schema; apply_brain_schema()"` — 7 brain.* tables deployed to Supabase
2. Ran seed data: `python -m promaia.brain.seed` — 10 domains and 5 contexts populated
3. Tested MCP server starts: `python -m promaia.brain.mcp_server` — hangs on stdio as expected
4. Registered with Claude Code: `claude mcp add --scope project --transport stdio brain -- python -m promaia.brain.mcp_server`
5. Verified in new Claude Code session: /mcp shows brain connected, briefing fires on startup, capture extracts actions

All steps approved by user.

## Next Phase Readiness

- Complete brain layer: schema (7 tables) + engine (8 functions) + MCP server (7 tools) + action extraction + system instructions + seed data
- Ready for Phase 3: heartbeat autonomy (Windows Task Scheduler, AgentExecutor, active-user check, max 2 commits/cycle)
- Phase 2 is fully complete — all 3 plans delivered and verified

---

## Self-Check: PASSED

- `CLAUDE.md` exists at repo root — confirmed (contains mcp__brain__briefing, mcp__brain__capture)
- `.mcp.json` exists at repo root — confirmed (contains promaia.brain.mcp_server)
- `promaia/brain/seed.py` exists — confirmed
- Commit `0fae709` exists — confirmed (feat(02-03) — CLAUDE.md, .mcp.json, seed.py)
- Commit `3d026b8` exists — confirmed (docs(02-03) — partial checkpoint summary)

---
*Phase: 02-brain-schema-and-mcp-tools*
*Completed: 2026-03-05*
