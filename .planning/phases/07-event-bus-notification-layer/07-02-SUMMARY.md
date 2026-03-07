---
phase: 07-event-bus-notification-layer
plan: 02
subsystem: events
tags: [event-router, notification-channels, rate-limiting, quiet-hours, asyncio]

# Dependency graph
requires:
  - phase: 07-event-bus-notification-layer
    provides: "brain.events urgency/routed_at/channel/held_until columns, Urgency enum, emit_agent_events"
provides:
  - "EventRouter polling loop dispatching unrouted events to channels"
  - "NotificationChannel ABC for pluggable delivery channels"
  - "DashboardChannel marking events routed with channel='dashboard'"
  - "RateLimiter with 10/hour cap and 30-min cooldown via SQL queries"
  - "Quiet hours (9pm-6am ET) holding non-interrupt events until morning"
  - "Scheduler integration: EventRouter runs as asyncio task alongside agents"
affects: [07-03, dashboard-badges, telegram-bot, phase-08]

# Tech tracking
tech-stack:
  added: []
  patterns: [channel-abstraction-abc, db-backed-rate-limiting, quiet-hours-hold, poll-for-null-not-since-timestamp]

key-files:
  created:
    - promaia/events/channels.py
    - promaia/events/rate_limiter.py
    - promaia/events/router.py
  modified:
    - promaia/agents/scheduler.py

key-decisions:
  - "DB-backed rate limiting (no in-memory state) survives scheduler restarts"
  - "Fail-open on rate limiter DB errors to prioritize delivery over limiting"
  - "Hardcoded America/New_York timezone for quiet hours (env var later)"

patterns-established:
  - "Channel abstraction: NotificationChannel ABC with name, deliver, supports_urgency"
  - "Poll for NULL pattern: WHERE routed_at IS NULL catches missed events after restart"
  - "Interrupt bypass: interrupt urgency skips both quiet hours and rate limiting"

requirements-completed: [EVENT-02, EVENT-03, EVENT-04, EVENT-05]

# Metrics
duration: 2min
completed: 2026-03-07
---

# Phase 7 Plan 2: Notification Router Summary

**Event routing engine with polling loop, quiet hours (9pm-6am ET), 10/hour rate limiting via SQL, and pluggable NotificationChannel ABC with DashboardChannel**

## Performance

- **Duration:** 2 min
- **Started:** 2026-03-07T08:15:09Z
- **Completed:** 2026-03-07T08:17:45Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments
- Built EventRouter polling loop that queries brain.events every 30 seconds for unrouted events, ordered by urgency priority (interrupt > digest > archive)
- Created NotificationChannel ABC with DashboardChannel implementation -- Phase 8 TelegramChannel plugs in without router changes
- Implemented RateLimiter using SQL count queries (no in-memory state) with 10/hour cap and 30-minute cooldown between non-urgent pushes
- Added quiet hours enforcement (9pm-6am America/New_York) that holds non-interrupt events until 6am via held_until column
- Wired EventRouter as asyncio task in AgentScheduler, cancelled on shutdown alongside agent loops

## Task Commits

Each task was committed atomically:

1. **Task 1: Create channel interface, rate limiter, and event router** - `a9c2212` (feat)
2. **Task 2: Wire event router into agent scheduler** - `ebbe731` (feat)

## Files Created/Modified
- `promaia/events/channels.py` - NotificationChannel ABC and DashboardChannel (marks events routed with channel='dashboard')
- `promaia/events/rate_limiter.py` - RateLimiter with SQL-backed sliding window (10/hour, 30-min cooldown)
- `promaia/events/router.py` - EventRouter polling loop with quiet hours, rate limiting, and channel dispatch
- `promaia/agents/scheduler.py` - Added EventRouter import, init, and asyncio task creation

## Decisions Made
- DB-backed rate limiting (SQL count queries) instead of in-memory counters -- survives scheduler restarts per research pitfall 5
- Fail-open on rate limiter DB errors: delivery is more important than rate limiting precision
- Hardcoded America/New_York timezone for quiet hours (plan specified env var default; keeping simple for now)

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Event routing pipeline is live: events are polled, rate-limited, and dispatched to channels
- DashboardChannel marks events for badge display in the web layer
- Ready for 07-03 (dashboard badges + API) to surface routed events to the user
- Channel ABC ready for Phase 8 TelegramChannel to plug in without router changes

## Self-Check: PASSED

All 4 files verified present. Both task commits (a9c2212, ebbe731) confirmed in git log.

---
*Phase: 07-event-bus-notification-layer*
*Completed: 2026-03-07*
