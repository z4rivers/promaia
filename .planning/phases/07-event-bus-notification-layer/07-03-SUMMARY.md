---
phase: 07-event-bus-notification-layer
plan: 03
subsystem: ui
tags: [notifications, polling, fastapi, jinja2, javascript, dashboard]

# Dependency graph
requires:
  - phase: 07-01
    provides: "brain.events schema with urgency, routed_at, held_until, channel columns"
provides:
  - "GET /api/notifications/unread endpoint returning unrouted event count"
  - "POST /api/notifications/read endpoint marking events as dashboard-delivered"
  - "Fixed-position notification badge in base template visible on all pages"
  - "60-second JS polling for badge updates"
  - "Auto mark-read on dashboard page visit"
affects: [08-telegram-channel, 09-calendar-integration]

# Tech tracking
tech-stack:
  added: []
  patterns: [polling-badge, mark-read-on-visit, graceful-db-fallback]

key-files:
  created: []
  modified:
    - promaia/web/routers/dashboard.py
    - promaia/web/templates/base.html
    - promaia/web/templates/dashboard.html

key-decisions:
  - "Badge uses CSS custom properties for skin compatibility"
  - "60-second polling interval to avoid DB connection pressure"
  - "Events marked with channel='dashboard' on read for routing audit trail"

patterns-established:
  - "Notification polling: vanilla JS fetch with graceful error swallowing"
  - "Mark-read-on-visit: POST on page load to clear notification state"

requirements-completed: [EVENT-06]

# Metrics
duration: 2min
completed: 2026-03-07
---

# Phase 7 Plan 3: Notification Badge Summary

**Dashboard notification badge with polling unread count, API endpoints for event counting and mark-read, auto-clear on dashboard visit**

## Performance

- **Duration:** 2 min
- **Started:** 2026-03-07T08:15:07Z
- **Completed:** 2026-03-07T08:17:19Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- Two REST endpoints: GET /api/notifications/unread and POST /api/notifications/read
- Fixed-position notification badge in base template header, visible on all pages
- 60-second JS polling updates badge without page reload
- Dashboard page auto-marks all unrouted events as read on visit, clearing the badge

## Task Commits

Each task was committed atomically:

1. **Task 1: Add notification API endpoints** - `6e34e67` (feat)
2. **Task 2: Add notification badge to dashboard UI** - `f06d376` (feat)

## Files Created/Modified
- `promaia/web/routers/dashboard.py` - Added GET /api/notifications/unread and POST /api/notifications/read endpoints
- `promaia/web/templates/base.html` - Added notification badge element, CSS styles, and 60s polling script
- `promaia/web/templates/dashboard.html` - Added mark-read POST call on page load with badge clear

## Decisions Made
- Badge uses CSS custom properties (var(--accent-primary)) so the Superflat skin can override badge colors
- 60-second polling interval per research recommendation to avoid DB connection pressure
- Events marked with channel='dashboard' when read, creating an audit trail for notification routing
- Graceful error handling on both endpoints -- notification failures never crash the dashboard

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Notification badge is the first visible output of the event pipeline
- All three plans in Phase 7 now complete: event schema (07-01), notification router (07-02), and dashboard badge (07-03)
- Ready for Phase 8: Telegram channel integration can use the same event routing pattern

## Self-Check: PASSED

All files exist. All commits verified (6e34e67, f06d376).

---
*Phase: 07-event-bus-notification-layer*
*Completed: 2026-03-07*
