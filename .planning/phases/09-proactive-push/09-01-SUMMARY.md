---
phase: 09-proactive-push
plan: 01
subsystem: agents
tags: [scheduling, telegram, asyncio, zoneinfo, aiogram, push-notifications]

# Dependency graph
requires:
  - phase: 08-telegram-bot
    provides: "TelegramChannel, aiogram Bot, send_long_message formatting"
  - phase: 07-event-bus
    provides: "Event emitter, event router, notification channels"
provides:
  - "Time-of-day scheduling via _next_run_time() with timezone-aware datetime math"
  - "Direct Telegram push via _push_agent_output() bypassing event router"
  - "Pre-routing flag in emit_agent_events() preventing double delivery"
  - "Morning briefing at 06:00 ET, evening digest at 16:30 ET"
affects: [09-02-PLAN, email-triage-scheduling]

# Tech tracking
tech-stack:
  added: [tzdata]
  patterns: [sleep-until-scheduling, pre-routed-events, direct-push-bypass]

key-files:
  created: []
  modified:
    - promaia/agents/scheduler.py
    - promaia/events/emitter.py
    - promaia.config.json
    - prompts/agent_evening_digest.md

key-decisions:
  - "Sleep-until scheduling recalculates next_run after each execution to prevent drift"
  - "Direct Telegram push bypasses rate limiter for scheduled agents"
  - "Pre-routing uses atomic INSERT with routed_at+channel to prevent race condition"
  - "Evening digest renamed Tonight to What's Next for 4:30 PM timing"
  - "Bot session closed in finally block to prevent connection leaks"

patterns-established:
  - "Sleep-until scheduling: _next_run_time() calculates next occurrence, agent sleeps until then"
  - "Pre-routed events: pushed_to_channel param sets routed_at at INSERT time"
  - "Agent prefixes: _PUSH_PREFIXES dict maps agent names to Telegram message prefixes"

requirements-completed: [PUSH-02, PUSH-03]

# Metrics
duration: 4min
completed: 2026-03-07
---

# Phase 9 Plan 1: Time-of-Day Scheduling + Telegram Push Summary

**Time-of-day scheduling with sleep-until logic for morning briefing (6:00 AM) and evening digest (4:30 PM), with direct Telegram push and atomic pre-routing to prevent double delivery**

## Performance

- **Duration:** 4 min
- **Started:** 2026-03-07T10:48:30Z
- **Completed:** 2026-03-07T10:53:23Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments
- Scheduler supports time-of-day scheduling via agent.schedule field with timezone-aware (America/New_York) sleep-until logic
- Agent output pushed directly to Telegram after scheduled execution, bypassing event router for immediate delivery
- Emitted events marked pre-routed atomically at INSERT time when direct push succeeds, preventing double Telegram messages
- Config updated: morning briefing at 06:00, evening digest at 16:30, email-triage unchanged at 480-min interval
- Evening digest prompt updated from 9pm/tonight framing to 4:30 PM/what's next

## Task Commits

Each task was committed atomically:

1. **Task 1: Time-of-day scheduling and direct Telegram push in scheduler** - `bf30b08` (feat)
2. **Task 2: Emitter pre-routing, config update, and prompt timing fix** - `f78749a` (feat)

## Files Created/Modified
- `promaia/agents/scheduler.py` - Added _next_run_time(), _run_scheduled_agent(), _push_agent_output(), modified start() branching
- `promaia/events/emitter.py` - Added pushed_to_channel param to emit_agent_events and _insert_event with atomic pre-routing
- `promaia.config.json` - Morning briefing schedule daily 06:00, evening digest schedule daily 16:30
- `prompts/agent_evening_digest.md` - Updated timing from 9pm to 4:30 PM, Tonight to What's Next

## Decisions Made
- Sleep-until scheduling recalculates next_run_time after each execution to prevent drift (Research Pitfall 1)
- Direct Telegram push bypasses rate limiter -- scheduled pushes should not be rate-limited (Research Pitfall 5)
- Pre-routing uses atomic INSERT with routed_at+channel columns to prevent race condition where event router picks up unrouted events between INSERT and UPDATE (Gemini review finding)
- _split_message used directly instead of send_long_message since Bot.send_message requires chat_id not Message object
- Bot session explicitly closed in finally block to prevent connection leaks

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Installed tzdata package for zoneinfo on Windows**
- **Found during:** Task 1 (scheduler import)
- **Issue:** Python 3.14 on Windows requires tzdata package for zoneinfo.ZoneInfo to resolve timezone keys
- **Fix:** Installed tzdata via pip
- **Files modified:** None (runtime dependency only)
- **Verification:** Import succeeds, _next_run_time() returns correct future datetimes
- **Committed in:** bf30b08 (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Essential for Windows Python 3.14 compatibility. No scope creep.

## Issues Encountered
None beyond the tzdata dependency.

## User Setup Required
None - no external service configuration required. Existing TELEGRAM_BOT_TOKEN and TELEGRAM_WHITELIST env vars are reused.

## Next Phase Readiness
- Time-of-day scheduling foundation ready for Plan 02 (email-triage time-of-day migration and notification preferences)
- Interval-based scheduling preserved for backward compatibility
- Direct push + pre-routing pattern established for reuse by future agents

## Self-Check: PASSED

All files exist. All commits verified (bf30b08, f78749a).

---
*Phase: 09-proactive-push*
*Completed: 2026-03-07*
