---
phase: 07-event-bus-notification-layer
verified: 2026-03-07T09:30:00Z
status: passed
score: 5/5 must-haves verified
---

# Phase 7: Event Bus + Notification Layer Verification Report

**Phase Goal:** Agents produce routable events with urgency tiers, and a polling loop delivers them to the right channel at the right time
**Verified:** 2026-03-07T09:30:00Z
**Status:** passed
**Re-verification:** No -- initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | After an agent run completes, events appear in brain.events with correct urgency (interrupt/digest/archive) | VERIFIED | schema.sql adds urgency CHECK column; emitter.py has deterministic agent-to-urgency mapping; executor.py calls emit_agent_events after success path (line 258); non-fatal try/except wrapping at both layers |
| 2 | The event router delivers interrupt events within 30 seconds of creation | VERIFIED | router.py poll_interval=30 default; interrupt bypasses quiet hours (line 92) and rate limiting (rate_limiter.py line 39); router registered as asyncio task in scheduler.py (line 66) |
| 3 | Events generated between 9pm and 6am are held until morning (quiet hours) | VERIFIED | router.py _is_quiet_hours checks hour >= 21 or hour < 6 (line 126); _hold_for_morning calculates next 6am and sets held_until (lines 128-150); interrupt events bypass quiet hours (line 92) |
| 4 | Dashboard shows an unread notification count badge that clears when viewed | VERIFIED | base.html has notification-badge element (line 81) with 60s polling script (lines 89-108); dashboard.py has GET /api/notifications/unread (line 364) and POST /api/notifications/read (line 385); dashboard.html calls POST on load (line 414) and clears badge (line 417) |
| 5 | No more than 10 push notifications are sent in any one-hour window | VERIFIED | rate_limiter.py max_per_hour=10 (line 24); SQL COUNT check for hourly cap (lines 46-58); 30-min cooldown for non-urgent (lines 61-82); DB-backed state survives restarts; interrupt bypasses limits (line 39) |

**Score:** 5/5 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `promaia/brain/schema.sql` | Extended brain.events with urgency, routed_at, channel, held_until columns + partial index | VERIFIED | Lines 133-150: ALTER TABLE ADD COLUMN IF NOT EXISTS for all 4 columns; CHECK constraint on urgency; idx_brain_events_unrouted partial index |
| `promaia/events/__init__.py` | Package init | VERIFIED | Exists (empty, as expected) |
| `promaia/events/models.py` | Urgency enum and Event dataclass | VERIFIED | 34 lines; Urgency(str, Enum) with INTERRUPT/DIGEST/ARCHIVE; frozen Event dataclass with all required fields |
| `promaia/events/emitter.py` | emit_agent_events function with agent-to-urgency mapping | VERIFIED | 165 lines; deterministic mapping for morning-briefing, evening-digest, email-triage; Action Needed parser; INSERT INTO brain.events with urgency; non-fatal exception handling |
| `promaia/events/channels.py` | NotificationChannel ABC and DashboardChannel | VERIFIED | 79 lines; ABC with name, deliver, supports_urgency; DashboardChannel returns "dashboard", supports interrupt/digest (not archive), marks events routed with channel='dashboard' |
| `promaia/events/rate_limiter.py` | RateLimiter with SQL-backed sliding window | VERIFIED | 90 lines; 10/hour cap, 30-min cooldown, interrupt bypass, DB-backed queries, fail-open on errors |
| `promaia/events/router.py` | EventRouter polling loop with quiet hours, rate limiting, channel dispatch | VERIFIED | 160 lines; 30s poll interval; fetches WHERE urgency IS NOT NULL AND routed_at IS NULL; quiet hours 9pm-6am; archive auto-routed; priority ordering interrupt > digest > archive |
| `promaia/agents/executor.py` | Post-execution hook calling emit_agent_events | VERIFIED | Import at line 28; call at lines 258-264 after "Agent completed successfully"; wrapped in try/except |
| `promaia/agents/scheduler.py` | EventRouter registered as asyncio task | VERIFIED | Import at line 15; self.event_router = EventRouter() in __init__ (line 34); asyncio.create_task in start() (line 66); cancelled on shutdown via self.tasks |
| `promaia/web/routers/dashboard.py` | REST endpoints /api/notifications/unread and /api/notifications/read | VERIFIED | GET /api/notifications/unread (lines 364-382) returns {"unread": N}; POST /api/notifications/read (lines 385-403) marks events with channel='dashboard' |
| `promaia/web/templates/base.html` | Notification badge element and JS polling script | VERIFIED | Badge div at line 81 with CSS (lines 54-76); polling script at lines 89-108 fetches every 60s; uses CSS custom properties for skin compatibility |
| `promaia/web/templates/dashboard.html` | Dashboard page triggers mark-read on load | VERIFIED | Lines 410-421: block scripts with super(), POST to /api/notifications/read, clears badge on success |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `executor.py` | `emitter.py` | import and call after successful execution | WIRED | Line 28: `from promaia.events.emitter import emit_agent_events`; Lines 258-264: called with agent_name, output, execution_id |
| `emitter.py` | brain.events | INSERT with urgency column | WIRED | Lines 159-163: `INSERT INTO brain.events (type, payload, source, urgency)` via insert_returning |
| `router.py` | brain.events | SQL poll for unrouted events | WIRED | Lines 64-79: `WHERE urgency IS NOT NULL AND routed_at IS NULL AND (held_until IS NULL OR held_until <= NOW())` |
| `router.py` | `channels.py` | channel.deliver(event) dispatch | WIRED | Line 108: `await channel.deliver(event)` with supports_urgency check at line 98 |
| `router.py` | `rate_limiter.py` | rate_limiter.allow() check | WIRED | Line 101: `self.rate_limiter.allow(channel.name, urgency)` |
| `scheduler.py` | `router.py` | asyncio.create_task(event_router.run()) | WIRED | Line 15: import; Line 34: instantiation; Line 66: task creation |
| `base.html` | `/api/notifications/unread` | fetch() polling every 60 seconds | WIRED | Lines 93-104: fetch('/api/notifications/unread') with setInterval(poll, 60000) |
| `dashboard.html` | `/api/notifications/read` | fetch() POST on page load | WIRED | Line 414: `fetch('/api/notifications/read', { method: 'POST' })` |
| `dashboard.py` | brain.events | SQL COUNT query for unrouted events | WIRED | Lines 370-377: `SELECT COUNT(*) ... WHERE urgency IS NOT NULL AND routed_at IS NULL` |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| EVENT-01 | 07-01 | brain.events has urgency column (interrupt/digest/archive) with routing metadata | SATISFIED | schema.sql: ALTER TABLE adds urgency with CHECK constraint, plus routed_at/channel/held_until columns |
| EVENT-02 | 07-02 | Event router polls unrouted events every 30 seconds and routes by urgency | SATISFIED | router.py: EventRouter with poll_interval=30, polls WHERE routed_at IS NULL, priority ordering by urgency |
| EVENT-03 | 07-02 | Quiet hours (9pm-6am) respected -- non-critical interrupts queued for morning | SATISFIED | router.py: _is_quiet_hours (hour >= 21 or < 6), _hold_for_morning sets held_until to next 6am, interrupt bypasses |
| EVENT-04 | 07-02 | Rate limiting prevents notification spam (max 10 pushes/hour, 30-min cooldown between non-urgent) | SATISFIED | rate_limiter.py: max_per_hour=10, cooldown_minutes=30, SQL-backed sliding window, interrupt bypass |
| EVENT-05 | 07-02 | Channel registry supports abstract channel interface with dashboard fallback | SATISFIED | channels.py: NotificationChannel ABC with name/deliver/supports_urgency; DashboardChannel concrete implementation |
| EVENT-06 | 07-03 | Dashboard shows unread notification badge from unrouted events | SATISFIED | base.html badge element + 60s polling; dashboard.py API endpoints; dashboard.html mark-read on visit |
| EVENT-07 | 07-01 | Agents emit routable events with correct urgency after each run | SATISFIED | emitter.py: deterministic agent-to-urgency mapping; executor.py: post-run hook calling emit_agent_events |

All 7 requirements (EVENT-01 through EVENT-07) are accounted for across the three plans. No orphaned requirements.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `promaia/web/templates/dashboard.html` | 368 | `calendar-placeholder` class with "Calendar not connected" text | Info | Pre-existing UI placeholder for future calendar integration (Phase 9). Not a Phase 7 concern. |

No blocker or warning-level anti-patterns found. All event module files are clean -- no TODOs, FIXMEs, stub returns, or empty implementations.

### Human Verification Required

### 1. Visual Badge Appearance

**Test:** Start the web server, insert a test event with urgency='interrupt' in brain.events, then visit any page (e.g., /projects).
**Expected:** A red badge appears in the top-right corner showing "1". Clicking it navigates to /dashboard. After the dashboard loads, the badge disappears.
**Why human:** Visual rendering, CSS custom property resolution with Superflat skin, and click behavior cannot be verified programmatically.

### 2. Quiet Hours Hold Behavior

**Test:** Change system clock to 10pm ET (or temporarily modify _is_quiet_hours to return True). Trigger an agent run or manually insert an unrouted digest event. Wait 30 seconds for the router poll.
**Expected:** The event gains a held_until value (next 6am) instead of being routed. Interrupt events should still be delivered immediately.
**Why human:** Requires real-time clock manipulation and observing DB state changes over time.

### 3. End-to-End Agent-to-Badge Flow

**Test:** Run a real agent (e.g., morning-briefing via CLI). Check brain.events for the new event row. Wait up to 30 seconds for the router to route it. Reload the dashboard.
**Expected:** Event appears in brain.events with urgency='digest'. Router marks it routed with channel='dashboard'. Badge shows count, then clears on dashboard visit.
**Why human:** Full pipeline timing, real database writes, and async coordination between executor, emitter, router, and dashboard.

### Gaps Summary

No gaps found. All 5 success criteria are verified against the actual codebase. All 7 requirement IDs (EVENT-01 through EVENT-07) are satisfied by substantive, wired implementations. All 12 artifacts exist, are non-trivial, and are properly connected. All 9 key links are wired with real function calls and SQL queries. No anti-patterns blocking goal achievement.

The implementation follows the research recommendations closely: deterministic agent-to-urgency mapping (no LLM classification), DB-backed rate limiting (survives restarts), fail-open on rate limiter errors, non-fatal event emission, and poll-for-NULL pattern (catches missed events). The channel abstraction is ready for Phase 8 Telegram integration.

---

_Verified: 2026-03-07T09:30:00Z_
_Verifier: Claude (gsd-verifier)_
