---
phase: 07-event-bus-notification-layer
plan: 01
subsystem: events
tags: [event-bus, postgres, notification-routing, urgency]

# Dependency graph
requires:
  - phase: 06-waste-elimination-spend-visibility
    provides: "Agent executor with Gemini execution path and cost tracking"
provides:
  - "brain.events urgency/routed_at/channel/held_until columns"
  - "Partial index idx_brain_events_unrouted for router polling"
  - "Urgency enum and Event dataclass in promaia/events/models.py"
  - "emit_agent_events function mapping agent output to routable events"
  - "Executor post-run event emission hook"
affects: [07-02, 07-03, notification-router, dashboard-badges, telegram-bot]

# Tech tracking
tech-stack:
  added: []
  patterns: [deterministic-agent-urgency-mapping, non-fatal-event-emission, action-needed-parsing]

key-files:
  created:
    - promaia/events/__init__.py
    - promaia/events/models.py
    - promaia/events/emitter.py
  modified:
    - promaia/brain/schema.sql
    - promaia/agents/executor.py

key-decisions:
  - "Deterministic agent-to-urgency mapping (no LLM classification) for zero-cost, predictable routing"
  - "Unknown agents default to digest urgency as safe fallback"
  - "Event emission wrapped in try/except -- never crashes agent pipeline"

patterns-established:
  - "Non-fatal event emission: event failures logged as warnings, never block agent execution"
  - "Action Needed parsing: line-by-line bullet extraction between section headers"
  - "Urgency enum (interrupt/digest/archive) as the routing primitive for the notification pipeline"

requirements-completed: [EVENT-01, EVENT-07]

# Metrics
duration: 3min
completed: 2026-03-07
---

# Phase 7 Plan 1: Event Schema + Emitter Summary

**Extended brain.events with urgency routing columns and wired deterministic event emission into the agent executor for morning-briefing, evening-digest, and email-triage**

## Performance

- **Duration:** 3 min
- **Started:** 2026-03-07T08:08:19Z
- **Completed:** 2026-03-07T08:11:45Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments
- Extended brain.events schema with 4 notification routing columns (urgency, routed_at, channel, held_until) plus a partial index for unrouted event polling
- Created promaia/events/ package with Urgency enum (interrupt/digest/archive) and frozen Event dataclass
- Built emit_agent_events with deterministic agent-to-urgency mapping: morning-briefing and evening-digest produce digest events, email-triage produces interrupt events per Action Needed item plus an archive summary
- Wired event emission into executor.py success path with non-fatal error handling

## Task Commits

Each task was committed atomically:

1. **Task 1: Extend brain.events schema and create event models** - `cb2bf07` (feat)
2. **Task 2: Create event emitter and wire into executor** - `34ec039` (feat)

## Files Created/Modified
- `promaia/brain/schema.sql` - Added ALTER TABLE for urgency/routed_at/channel/held_until columns and partial index
- `promaia/events/__init__.py` - Package init (empty)
- `promaia/events/models.py` - Urgency enum and Event frozen dataclass
- `promaia/events/emitter.py` - emit_agent_events with agent-to-urgency mapping and Action Needed parser
- `promaia/agents/executor.py` - Added import and post-execution event emission hook

## Decisions Made
- Deterministic agent-to-urgency mapping (no LLM classification) -- zero additional cost, predictable behavior
- Unknown agents default to digest urgency as a safe fallback rather than skipping event emission
- Event emission is fully non-fatal: wrapped in try/except at both the emitter and executor level

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Event data foundation is live: every agent run now produces routable events in brain.events
- Ready for 07-02 (notification router) to poll idx_brain_events_unrouted and route events to channels
- Ready for 07-03 (dashboard/Telegram) to consume routed events

## Self-Check: PASSED

All 6 files verified present. Both task commits (cb2bf07, 34ec039) confirmed in git log.

---
*Phase: 07-event-bus-notification-layer*
*Completed: 2026-03-07*
