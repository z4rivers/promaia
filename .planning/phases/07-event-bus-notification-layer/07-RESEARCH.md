# Phase 7: Event Bus + Notification Layer - Research

**Researched:** 2026-03-06
**Domain:** Postgres-based event bus, urgency routing, notification delivery, dashboard integration
**Confidence:** HIGH

## Summary

Phase 7 wires together existing pieces to create a notification pipeline: agents emit events into `brain.events` with urgency metadata, a polling loop routes them to delivery channels, and the dashboard displays an unread count. The key insight from the codebase is that `brain.events` already exists and is actively used (briefing, capture, context_save, profile_update events), but lacks urgency classification and routing status. The schema needs extending -- not replacing.

The architecture splits into three clean layers: (1) event emission at the end of agent execution in `executor.py`, (2) a standalone event router that polls `brain.events` for unrouted items every 30 seconds, and (3) a channel abstraction where "dashboard" is the first concrete channel. Telegram becomes a second channel in Phase 8 without changing the router.

**Primary recommendation:** Extend `brain.events` with `urgency` and `routed_at` columns (zero new tables), build the event router as a standalone asyncio loop inside the existing scheduler process, and add a `/api/notifications` REST endpoint for the dashboard badge.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| EVENT-01 | brain.events has urgency column (interrupt/digest/archive) with routing metadata | Schema migration adds `urgency`, `routed_at`, `channel`, `held_until` columns to existing `brain.events` table |
| EVENT-02 | Event router polls unrouted events every 30 seconds and routes by urgency | EventRouter class with asyncio polling loop, runs as a task inside AgentScheduler |
| EVENT-03 | Quiet hours (9pm-6am) respected -- non-critical interrupts queued for morning | `held_until` column on events; router checks current time in user's timezone and defers delivery |
| EVENT-04 | Rate limiting prevents notification spam (max 10 pushes/hour, 30-min cooldown between non-urgent) | In-memory rate limiter in EventRouter with sliding window counter, backed by SQL count query |
| EVENT-05 | Channel registry supports abstract channel interface with dashboard fallback | Abstract `NotificationChannel` base class; `DashboardChannel` writes routed status; Telegram channel plugs in later |
| EVENT-06 | Dashboard shows unread notification badge from unrouted events | New `/api/notifications/unread` endpoint queried by dashboard JS; `/api/notifications/read` marks viewed |
| EVENT-07 | Agents emit routable events with correct urgency after each run | Post-execution hook in `executor.py` that parses agent output and inserts typed events |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| psycopg2 | 2.9.x (already installed) | Postgres queries for event bus | Already used throughout -- `brain.events` table exists |
| FastAPI | 0.115.x (already installed) | Dashboard notification API endpoints | Already powers localhost:8000 dashboard |
| asyncio | stdlib | Event router polling loop | Already used by AgentScheduler |
| Jinja2 | 3.x (already installed) | Dashboard template updates | Already used for all dashboard pages |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| zoneinfo | stdlib (Python 3.9+) | User timezone for quiet hours | Quiet hours need timezone-aware time checks |
| dataclasses | stdlib | Event models, channel config | Same pattern as AgentContext, CostRecord |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Postgres polling | Redis pub/sub | Adds dependency; project decision is zero new deps |
| Postgres polling | pg_notify/LISTEN | Better latency, but psycopg2 pool pattern doesn't hold connections; 30s poll is adequate for requirements |
| Separate router process | In-scheduler task | Separate process = restart coordination headache; scheduler already has asyncio loop |

**Installation:**
```bash
# No new packages needed -- all libraries already installed
```

## Architecture Patterns

### Recommended Project Structure
```
promaia/
  events/
    __init__.py
    models.py           # Event dataclass, urgency enum
    emitter.py          # emit_agent_events() called from executor.py
    router.py           # EventRouter polling loop
    channels.py         # NotificationChannel ABC + DashboardChannel
    rate_limiter.py     # Sliding window rate limiter
```

### Pattern 1: Schema Extension (Not New Table)
**What:** Add columns to existing `brain.events` rather than creating a new table
**When to use:** When the existing table already captures the same entity (events) and just needs richer metadata
**Why:** `brain.events` already has 8+ INSERT sites across the codebase. A new table would mean maintaining two event systems. Extending is cleaner.

```sql
-- Migration: extend brain.events for notification routing
ALTER TABLE brain.events ADD COLUMN IF NOT EXISTS urgency TEXT
    CHECK (urgency IN ('interrupt', 'digest', 'archive'));

ALTER TABLE brain.events ADD COLUMN IF NOT EXISTS routed_at TIMESTAMPTZ;

ALTER TABLE brain.events ADD COLUMN IF NOT EXISTS channel TEXT;

ALTER TABLE brain.events ADD COLUMN IF NOT EXISTS held_until TIMESTAMPTZ;

-- Index for the router's polling query (unrouted events)
CREATE INDEX IF NOT EXISTS idx_brain_events_unrouted
    ON brain.events (created_at ASC)
    WHERE urgency IS NOT NULL AND routed_at IS NULL;
```

**Key insight:** Existing events (briefing, capture, etc.) will have `urgency = NULL`, which naturally excludes them from the routing loop. Only new agent-emitted events will have urgency set. This is backward-compatible.

### Pattern 2: Event Router as Scheduler Co-Task
**What:** Run the event router as an asyncio task alongside agent loops in the existing scheduler
**When to use:** When you need a persistent polling loop and already have a daemon process

```python
# In scheduler.py, add router as another task in start()
class AgentScheduler:
    async def start(self):
        # ... existing agent tasks ...

        # Add event router task
        from promaia.events.router import EventRouter
        self.event_router = EventRouter()
        router_task = asyncio.create_task(self.event_router.run())
        self.tasks["__event_router__"] = router_task
```

### Pattern 3: Abstract Channel Interface
**What:** Define a simple ABC that any notification channel implements
**When to use:** When Phase 8 (Telegram) and future channels need to plug in without changing the router

```python
from abc import ABC, abstractmethod
from typing import Optional

class NotificationChannel(ABC):
    """Base class for notification delivery channels."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Channel identifier (e.g., 'dashboard', 'telegram')."""
        ...

    @abstractmethod
    async def deliver(self, event: Event) -> bool:
        """Deliver an event to this channel. Returns True on success."""
        ...

    @abstractmethod
    def supports_urgency(self, urgency: str) -> bool:
        """Whether this channel handles events of the given urgency."""
        ...
```

### Pattern 4: Agent Output Parsing for Event Emission
**What:** After an agent run completes, parse structured output to emit typed events
**When to use:** At the integration point in `executor.py` after Step 6 (metrics)

The current agent output is markdown text (from Gemini). There are two approaches:

**Option A (Recommended): Post-hoc classification by agent name**
Each agent has a known purpose, so urgency can be determined by agent name + output characteristics:
- `morning-briefing` -> always `digest` urgency (it's a daily summary)
- `evening-digest` -> always `digest` urgency
- `email-triage` -> parse "Action Needed" vs "FYI" sections; "Action Needed" items become `interrupt`, everything else is `archive`

**Option B: Instruct agents to emit structured events in output**
Add a `## Events` section to agent prompts with JSON blocks. More flexible but requires prompt changes and adds parsing complexity.

Option A is simpler and aligns with "wire existing pieces together." Option B becomes valuable in Phase 9 when agents need more granular event classification.

### Anti-Patterns to Avoid
- **Separate events table:** Don't create `brain.notifications` alongside `brain.events` -- it splits the event system and creates sync problems
- **Real-time WebSocket for dashboard:** Overkill for a single-user dashboard polled every 30 seconds. A simple AJAX poll on the dashboard page is sufficient.
- **Router modifying agent output:** The router should only read events and route them. It should never modify the agent's output text.
- **Timezone hardcoding:** Don't hardcode EST/ET -- use a configurable timezone from brain.profile or environment variable

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Rate limiting | Custom token bucket | Sliding window counter with SQL | Simple count query (`WHERE created_at > NOW() - INTERVAL '1 hour'`) is sufficient at 10/hour scale |
| Timezone handling | Manual UTC offset math | `zoneinfo.ZoneInfo` from stdlib | Handles DST transitions correctly |
| Event schema migration | Raw ALTER TABLE in code | Idempotent migration in `db_init.py` pattern | Project already uses `CREATE TABLE IF NOT EXISTS` pattern; `ALTER TABLE ADD COLUMN IF NOT EXISTS` follows the same convention |

**Key insight:** At the scale of this system (3 agents, single user, ~10 events/day max), simple SQL queries outperform anything requiring external dependencies. The rate limiter is a COUNT query, not a Redis token bucket.

## Common Pitfalls

### Pitfall 1: Timezone Confusion in Quiet Hours
**What goes wrong:** Quiet hours check uses UTC instead of user's local time, causing events to be held at wrong times
**Why it happens:** Server runs in UTC; `datetime.now()` returns UTC on Supabase
**How to avoid:** Store user timezone in config (or read from brain.profile). Always convert to user timezone before quiet hours check. Use `zoneinfo.ZoneInfo("America/New_York")` (or whatever Zack's timezone is).
**Warning signs:** Events being held during daytime, or interrupts arriving at 2 AM

### Pitfall 2: Router Missing Events During Scheduler Restart
**What goes wrong:** Events inserted while the scheduler (and router) is down are never routed
**Why it happens:** If the router only processes events created "since last poll," a restart gap means missed events
**How to avoid:** The router query should always look for `WHERE urgency IS NOT NULL AND routed_at IS NULL` regardless of when they were created. On startup, it will catch any unrouted events from the gap.
**Warning signs:** Dashboard badge shows unread events that were never delivered

### Pitfall 3: Agent Output Parsing Fragility
**What goes wrong:** Regex-based parsing of agent output breaks when the agent changes its format slightly
**Why it happens:** LLM output is inherently variable in formatting
**How to avoid:** Use agent-name-based urgency mapping (Option A above) for now. Email-triage output structure is well-defined (Action Needed / FYI / Skipped sections). Parse section headers, not specific line formats.
**Warning signs:** Events created with wrong urgency or not created at all

### Pitfall 4: Dashboard Polling Creating DB Connection Pressure
**What goes wrong:** Dashboard AJAX polling every few seconds from the browser creates excessive DB connections
**Why it happens:** Each AJAX call is a new request hitting the DB
**How to avoid:** Dashboard polls at 60-second intervals (not 5 seconds). The badge count query is a trivial `SELECT COUNT(*)` on an indexed column. The connection pool (`ThreadedConnectionPool` with max 10) handles this fine.
**Warning signs:** Connection pool exhaustion errors in logs

### Pitfall 5: Rate Limiter State Loss
**What goes wrong:** In-memory rate limiter resets on scheduler restart, allowing burst after restart
**Why it happens:** Rate state stored only in Python process memory
**How to avoid:** Always verify rate against the DB: `SELECT COUNT(*) FROM brain.events WHERE routed_at IS NOT NULL AND channel = %s AND routed_at > NOW() - INTERVAL '1 hour'`. Memory-only tracking is a cache, DB is source of truth.
**Warning signs:** Burst of notifications after scheduler restart

## Code Examples

### Event Emission from Executor
```python
# In executor.py, after successful execution (around line 253)
# Source: codebase analysis of executor.py execute() method

async def _emit_events(self, agent_name: str, output: str, execution_id: int):
    """Parse agent output and emit routable events to brain.events."""
    from promaia.events.emitter import emit_agent_events

    try:
        event_count = emit_agent_events(
            agent_name=agent_name,
            output=output,
            execution_id=execution_id,
        )
        if event_count > 0:
            logger.info(f"Emitted {event_count} routable events for '{agent_name}'")
    except Exception as e:
        logger.warning(f"Event emission failed (non-fatal): {e}")
```

### Event Router Polling Loop
```python
# Source: pattern from scheduler.py _run_agent_loop

class EventRouter:
    POLL_INTERVAL = 30  # seconds (EVENT-02 requirement)

    async def run(self):
        """Main polling loop -- runs inside scheduler's asyncio event loop."""
        logger.info("Event router started (polling every 30s)")
        while True:
            try:
                unrouted = self._fetch_unrouted_events()
                for event in unrouted:
                    await self._route_event(event)
            except Exception as e:
                logger.error(f"Event router error: {e}")
            await asyncio.sleep(self.POLL_INTERVAL)

    def _fetch_unrouted_events(self) -> list[dict]:
        db = get_postgres_db()
        return db.fetch_all(
            """
            SELECT id, type, payload, source, urgency, created_at, held_until
            FROM brain.events
            WHERE urgency IS NOT NULL
              AND routed_at IS NULL
              AND (held_until IS NULL OR held_until <= NOW())
            ORDER BY
              CASE urgency
                WHEN 'interrupt' THEN 1
                WHEN 'digest' THEN 2
                WHEN 'archive' THEN 3
              END,
              created_at ASC
            """
        )
```

### Quiet Hours Check
```python
# Source: requirements EVENT-03

from zoneinfo import ZoneInfo

def _apply_quiet_hours(self, event: dict) -> bool:
    """Check if event should be held for quiet hours. Returns True if held."""
    if event["urgency"] == "archive":
        return False  # archive events don't get pushed, no hold needed

    user_tz = ZoneInfo("America/New_York")  # from config/profile
    now_local = datetime.now(user_tz)
    hour = now_local.hour

    # Quiet hours: 9 PM to 6 AM
    if hour >= 21 or hour < 6:
        # Calculate next 6 AM
        if hour >= 21:
            next_morning = now_local.replace(hour=6, minute=0, second=0, microsecond=0) + timedelta(days=1)
        else:
            next_morning = now_local.replace(hour=6, minute=0, second=0, microsecond=0)

        db = get_postgres_db()
        db.execute(
            "UPDATE brain.events SET held_until = %s WHERE id = %s",
            (next_morning, event["id"]),
        )
        return True
    return False
```

### Dashboard Notification Badge
```python
# Source: pattern from dashboard.py _get_brain_data

@router.get("/api/notifications/unread")
async def unread_count():
    """Return count of unrouted events for dashboard badge."""
    db = get_postgres_db()
    row = db.fetch_one(
        """
        SELECT COUNT(*) as count
        FROM brain.events
        WHERE urgency IS NOT NULL
          AND routed_at IS NULL
          AND (held_until IS NULL OR held_until <= NOW())
        """
    )
    return {"unread": row["count"] if row else 0}

@router.post("/api/notifications/read")
async def mark_read():
    """Mark all dashboard-channel events as read."""
    db = get_postgres_db()
    db.execute(
        """
        UPDATE brain.events
        SET routed_at = NOW(), channel = 'dashboard'
        WHERE urgency IS NOT NULL
          AND routed_at IS NULL
          AND (held_until IS NULL OR held_until <= NOW())
        """
    )
    return {"status": "ok"}
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Agent output goes to Notion only | Agent output stored in execution tracker + Notion | Phase 5 | Output is already accessible from Postgres |
| No urgency classification | Agents classify urgency at emission time | This phase | Enables routing by priority |
| No notification delivery | Dashboard is passive (must visit) | Before this phase | User must check dashboard manually |
| Events are activity logs only | Events carry routing metadata | This phase | Events become actionable notifications |

**Deprecated/outdated:**
- Legacy Claude SDK execution path: Still exists but unused (all agents on Gemini now). Event emission should only hook into the Gemini path and the successful completion path in `execute()`.

## Key Integration Points

### 1. Executor Integration (EVENT-07)
**File:** `promaia/agents/executor.py`, lines 253-260 (after `logger.info("Agent completed successfully")`)
**What:** Add `_emit_events()` call after successful execution, before returning result dict
**Why here:** This is the single exit point for successful agent runs in both Gemini and legacy paths

### 2. Scheduler Integration (EVENT-02)
**File:** `promaia/agents/scheduler.py`, lines 56-62 (in `start()` method)
**What:** Create and register EventRouter as an additional asyncio task
**Why here:** The scheduler already manages asyncio tasks per agent; the router is just another task

### 3. Dashboard Integration (EVENT-06)
**Files:** `promaia/web/routers/dashboard.py`, `promaia/web/templates/dashboard.html`, `promaia/web/templates/base.html`
**What:** Add `/api/notifications/unread` endpoint; add badge element to nav/header; add JS polling
**Why here:** Dashboard is the only delivery channel in this phase

### 4. Schema Migration
**File:** `promaia/brain/schema.sql` (extend existing table definition)
**Also:** `promaia/storage/db_init.py` or equivalent (apply migration idempotently)
**What:** Add 4 columns to `brain.events` + 1 partial index

## Design Decisions for Planner

### Agent-to-Urgency Mapping (EVENT-07)
The simplest reliable approach for the three current agents:

| Agent | Default Urgency | Override Logic |
|-------|----------------|----------------|
| morning-briefing | digest | Always digest (daily summary) |
| evening-digest | digest | Always digest (daily summary) |
| email-triage | archive (default) | Items under "Action Needed" header become `interrupt` |

This mapping lives in `emitter.py` and is the single place to modify when Phase 9 adds more granular classification.

### Channel Selection Logic
For Phase 7 (dashboard only):
- All urgency levels route to `dashboard` channel
- `archive` events are marked routed immediately (no delivery needed, just logged)
- `interrupt` and `digest` events show up in dashboard badge count

For Phase 8+ (Telegram added):
- `interrupt` -> Telegram (immediate push) + dashboard
- `digest` -> Telegram (batched at scheduled time) + dashboard
- `archive` -> dashboard only

The channel interface must support this expansion without changing the router logic.

### Rate Limiter Scope (EVENT-04)
Rate limiting applies per-channel (not global):
- Max 10 pushes per hour per channel
- 30-min cooldown between non-urgent pushes per channel
- Dashboard is exempt from rate limiting (it's pull-based, not push-based)
- Rate limiting primarily matters for Phase 8 (Telegram) but the infrastructure is built now

## Open Questions

1. **User timezone source**
   - What we know: Zack is in a US Eastern timezone (morning briefing mentions office)
   - What's unclear: Should timezone come from brain.profile, environment variable, or promaia.config.json?
   - Recommendation: Use environment variable `PROMAIA_TIMEZONE=America/New_York` with fallback to brain.profile lookup. Simple and overridable.

2. **Event retention/cleanup**
   - What we know: `brain.events` has no cleanup mechanism currently. Old events accumulate forever.
   - What's unclear: Should routed events be cleaned up? Archived?
   - Recommendation: Out of scope for Phase 7. Add a cleanup job in Phase 10 (Memory Deepening). The table will grow slowly (~10 events/day).

3. **Dashboard notification detail view**
   - What we know: The badge shows a count. Requirement says "clears when viewed."
   - What's unclear: Does "viewed" mean visiting the dashboard page, or clicking the badge, or viewing a dedicated notifications page?
   - Recommendation: "Viewed" = visiting the dashboard page. On dashboard load, fire a POST to `/api/notifications/read`. No separate notifications page needed for Phase 7.

## Sources

### Primary (HIGH confidence)
- Codebase analysis: `promaia/brain/schema.sql` -- existing `brain.events` table definition
- Codebase analysis: `promaia/agents/executor.py` -- agent execution flow and output handling
- Codebase analysis: `promaia/agents/scheduler.py` -- asyncio task management pattern
- Codebase analysis: `promaia/web/routers/dashboard.py` -- dashboard data loading pattern
- Codebase analysis: `promaia/web/templates/dashboard.html` -- current dashboard UI structure
- Codebase analysis: `promaia/agents/budget_guard.py` -- rate limiting pattern reference
- Codebase analysis: `promaia/storage/postgres_db.py` -- DB helper API (fetch_one, fetch_all, execute, insert_returning)

### Secondary (MEDIUM confidence)
- `prompts/agent_email_triage.md` -- output structure for urgency classification
- `.planning/ROADMAP.md` -- Phase 8/9 forward compatibility requirements
- `.planning/REQUIREMENTS.md` -- EVENT-01 through EVENT-07 specifications

### Tertiary (LOW confidence)
- None -- all findings are from direct codebase analysis

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - all libraries already installed and used in the codebase
- Architecture: HIGH - follows existing patterns (scheduler tasks, dashboard routes, brain.events inserts)
- Pitfalls: HIGH - identified from direct analysis of existing code and schema
- Forward compatibility: MEDIUM - Phase 8/9 requirements are defined but implementation details TBD

**Research date:** 2026-03-06
**Valid until:** 2026-04-06 (stable -- no external dependency changes expected)
