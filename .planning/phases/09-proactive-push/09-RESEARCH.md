# Phase 9: Proactive Push - Research

**Researched:** 2026-03-07
**Domain:** Time-of-day agent scheduling, proactive Telegram delivery, email urgency classification, inline reply processing, notification fatigue controls
**Confidence:** HIGH

## Summary

Phase 9 is the culmination of the proactive pipeline: the brain reaches Zack without being asked. All the infrastructure is in place -- the event bus with urgency routing (Phase 7), Telegram bot with commands and event delivery (Phase 8), and three working agents (Phases 5-6). What's missing is the *timing glue* that triggers agents at specific wall-clock times and *pushes* their output to Telegram, plus the ability for Zack to reply inline and have those replies processed.

The current scheduler runs agents on fixed intervals (`interval_minutes`), which means the morning briefing runs every 1440 minutes from whenever the scheduler started -- NOT at 6:00 AM. The `AgentConfig` already has a `schedule` field (`List[Tuple[str, str]]`) that was designed for time-of-day scheduling but is completely unused. Phase 9 needs to implement time-of-day scheduling in the scheduler, configure the three agents to run at their target times, enhance the email-triage emitter to classify urgency properly, and wire inline reply handling in the Telegram bot.

The event bus (Phase 7) already routes events to TelegramChannel (Phase 8). The email-triage emitter already parses "Action Needed" sections and creates `interrupt` events. The gap is narrower than it appears: (1) the scheduler needs to support time-of-day runs instead of just intervals, (2) morning briefing and evening digest agents need to auto-push their output directly to Telegram rather than just emitting events, (3) email-triage needs to re-emit events as interrupts faster than the current 480-minute interval, (4) the bot needs to handle replies to pushed messages, and (5) the existing rate limiting and dedup need fine-tuning for the proactive use case.

**Primary recommendation:** Implement time-of-day scheduling in the existing scheduler by using the dormant `schedule` field in `AgentConfig`, push agent output directly to Telegram via `TelegramChannel.deliver()` after execution (not just through the event router), reduce email-triage interval to enable sub-minute email-to-push latency, and add a reply handler in the Telegram bot that links reply context to the original pushed event.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| PUSH-01 | Email-triage classifies each finding as interrupt/digest/archive | Emitter already does this via `_parse_action_needed()` -- Action Needed items become `interrupt`, rest becomes `archive`. Gap: email-triage runs every 480 minutes, far too slow for "within 1 minute" requirement. Need faster polling or a separate email-check loop. |
| PUSH-02 | Morning briefing auto-pushes to Telegram at scheduled time (6:00 AM or wake signal) | Scheduler needs time-of-day support using `AgentConfig.schedule` field. After agent execution, push output directly to Telegram. Current `interval_minutes=1440` must become `schedule=[("daily", "06:00")]`. |
| PUSH-03 | Evening digest batches day's events into single Telegram message at 4:30 PM | Same time-of-day scheduler support. Evening digest runs at 4:30 PM, pushes single batched message to Telegram. Current prompt runs at 9pm -- needs time change and event batching logic. |
| PUSH-04 | Notification fatigue prevention: 30-min cooldown, daily cap (10), cross-channel dedup, batching | Rate limiter (Phase 7) already enforces 10/hour cap and 30-min cooldown. Gap: need daily cap (not just hourly), cross-channel dedup (prevent same event routing to both dashboard and telegram as separate counts), and digest batching. |
| PUSH-05 | User can reply inline to Telegram pushes and brain processes the response | Telegram reply-to message tracking. When Zack replies to a pushed notification, extract the original event context and process the reply intelligently (e.g., reply to urgent email notification -> capture as action item or mark as handled). |
| PUSH-06 | Urgent emails reach Zack within 1 minute via interrupt push | Email-triage must run frequently enough (~every 60s) or a lightweight email-check loop must poll for new mail and classify urgency. Current 480-min interval makes this impossible. The event router polls every 30s, so once an interrupt event exists, Telegram delivery is fast. The bottleneck is email detection. |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| psycopg2 | 2.9.x (installed) | Postgres queries for events, scheduling state | Already used throughout |
| aiogram | 3.26.0 (installed) | Telegram message delivery and reply handling | Already powers the bot |
| asyncio | stdlib | Scheduler timing, sleep-until logic | Already used by scheduler |
| zoneinfo | stdlib | Timezone-aware scheduling (6:00 AM ET, not UTC) | Already used by event router |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| dataclasses | stdlib | Schedule models | Same pattern as Event, AgentContext |
| json | stdlib | Config parsing, event payloads | Already used throughout |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Custom sleep-until scheduler | APScheduler | Adds a dependency; project policy is zero new deps. The custom implementation is ~50 lines. |
| Frequent email-triage agent runs | Gmail push notifications (pub/sub) | Gmail push requires Google Cloud Pub/Sub, a webhook endpoint, and domain verification. Far too heavy for a single-user system. |
| Frequent full email-triage runs | Lightweight email-check loop | A dedicated loop that just checks for new unread emails (SQL query, not LLM) and only triggers the full agent when new mail is found. Much cheaper than running the full agent every 60 seconds. |

**Installation:**
```bash
# No new packages needed -- all libraries already installed
```

## Architecture Patterns

### Recommended Project Structure
```
promaia/
  agents/
    scheduler.py          # MODIFY: add time-of-day scheduling support
    executor.py           # MODIFY: add post-execution push hook
  events/
    emitter.py            # MODIFY: enhance email urgency classification
    router.py             # MODIFY: add daily cap, cross-channel dedup
    rate_limiter.py        # MODIFY: add daily cap tracking
    push_manager.py        # NEW: coordinates push delivery after agent runs
  telegram/
    handlers/
      replies.py           # NEW: inline reply handler
    channel.py            # EXISTING: used for push delivery
```

### Pattern 1: Time-of-Day Scheduling (sleep-until)
**What:** Replace `interval_minutes` with `schedule` field-based time-of-day execution. The agent loop calculates the next scheduled run time and sleeps until then, rather than sleeping for a fixed interval.
**When to use:** When agents need to run at specific wall-clock times.

```python
# In scheduler.py -- replace _run_agent_loop for schedule-based agents

from datetime import datetime, time
from zoneinfo import ZoneInfo

USER_TZ = ZoneInfo("America/New_York")

def _next_run_time(schedule: list[tuple[str, str]]) -> datetime:
    """Calculate the next scheduled run time from a list of (day, time) tuples.

    day: "daily", "Mon", "Tue", etc.
    time: "HH:MM" in user's timezone
    """
    now = datetime.now(USER_TZ)
    candidates = []

    for day_spec, time_str in schedule:
        hour, minute = map(int, time_str.split(":"))
        target_time = time(hour, minute)

        if day_spec == "daily":
            # Today at target_time if not past, else tomorrow
            candidate = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            if candidate <= now:
                candidate += timedelta(days=1)
            candidates.append(candidate)
        else:
            # Specific day of week
            day_map = {"Mon": 0, "Tue": 1, "Wed": 2, "Thu": 3, "Fri": 4, "Sat": 5, "Sun": 6}
            target_weekday = day_map.get(day_spec, 0)
            days_ahead = (target_weekday - now.weekday()) % 7
            if days_ahead == 0 and now.time() >= target_time:
                days_ahead = 7
            candidate = (now + timedelta(days=days_ahead)).replace(
                hour=hour, minute=minute, second=0, microsecond=0
            )
            candidates.append(candidate)

    return min(candidates)

async def _run_scheduled_agent(self, agent: AgentConfig):
    """Run agent at scheduled times instead of fixed intervals."""
    while self.running:
        next_run = _next_run_time(agent.schedule)
        sleep_seconds = (next_run - datetime.now(USER_TZ)).total_seconds()

        logger.info(f"'{agent.name}' next run at {next_run.strftime('%H:%M %Z')} (in {sleep_seconds/60:.0f}min)")

        try:
            await asyncio.sleep(max(0, sleep_seconds))
        except asyncio.CancelledError:
            break

        # Execute agent + push
        await self._execute_and_push(agent)
```

### Pattern 2: Post-Execution Push to Telegram
**What:** After an agent executes, push its output directly to Telegram via `TelegramChannel`, independent of the event router's 30-second poll cycle.
**When to use:** For morning briefing and evening digest -- the user expects the message immediately when the agent runs, not 30 seconds later.

```python
# In a new push_manager.py or integrated into executor post-hook

from promaia.telegram.channel import TelegramChannel

async def push_agent_output(agent_name: str, output: str):
    """Push agent output directly to Telegram as a formatted message."""
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    whitelist = os.getenv("TELEGRAM_WHITELIST", "")
    if not token or not whitelist:
        return

    chat_id = int(whitelist.split(",")[0].strip())
    bot = Bot(token=token)

    # Format based on agent type
    if agent_name == "morning-briefing":
        header = "Good morning. Here's your briefing:\n\n"
    elif agent_name == "evening-digest":
        header = "Evening digest:\n\n"
    else:
        header = ""

    text = header + output
    await send_long_message_raw(bot, chat_id, text)
    await bot.session.close()
```

**Key insight:** This push is separate from the event router. The event router handles interrupt events (urgent emails). The direct push handles scheduled agent output. They're different delivery mechanisms for different purposes.

### Pattern 3: Lightweight Email Check Loop
**What:** A fast, cheap loop that polls Gmail for new unread emails every 60 seconds. When new mail is detected, it triggers the full email-triage agent immediately.
**When to use:** To achieve PUSH-06's "within 1 minute" requirement without running the full LLM-based triage agent every minute.

```python
# Approach: Check Gmail for new unread count via Postgres
# The Gmail pipeline syncs email metadata to Postgres. We can detect
# new unread emails by comparing counts.

async def _email_check_loop(self):
    """Fast polling loop that detects new emails and triggers triage."""
    last_known_count = self._get_unread_count()

    while self.running:
        await asyncio.sleep(60)  # Check every 60 seconds

        current_count = self._get_unread_count()
        if current_count > last_known_count:
            logger.info(f"New email detected ({current_count} vs {last_known_count})")
            # Trigger email-triage agent immediately
            agent = get_agent("email-triage")
            if agent:
                executor = AgentExecutor(agent)
                result = await executor.execute()
                # Events are emitted by executor, router picks up interrupts
            last_known_count = current_count
        else:
            last_known_count = current_count

def _get_unread_count(self) -> int:
    """Count unread emails from Gmail data in Postgres."""
    db = get_postgres_db()
    row = db.fetch_one(
        """SELECT COUNT(*) as cnt FROM unified_content
           WHERE source_type = 'gmail'
           AND metadata->>'is_read' = 'false'
           AND created_at > NOW() - INTERVAL '24 hours'"""
    )
    return row["cnt"] if row else 0
```

**Alternative approach (simpler):** Just reduce `interval_minutes` for email-triage to 5 or 10 minutes. At ~$0.004/run, that's $0.58-$1.15/day. This is simpler but costs more. The lightweight check loop is free (just a SQL COUNT) and only triggers the LLM when needed.

**Third option (recommended):** Use the Gmail API directly for a lightweight "any new mail?" check. The Gmail API `users.messages.list` with `q=is:unread after:{timestamp}` is one free API call. This avoids depending on the sync pipeline's timing.

### Pattern 4: Inline Reply Processing
**What:** When Zack replies to a pushed Telegram message, the bot detects the reply-to context and processes it intelligently.
**When to use:** PUSH-05 -- reply inline to a pushed message and have the brain process it.

```python
# In telegram/handlers/replies.py

from aiogram import Router
from aiogram.types import Message

router = Router()

@router.message(lambda msg: msg.reply_to_message is not None)
async def handle_reply(message: Message) -> None:
    """Process replies to pushed notifications."""
    original = message.reply_to_message
    reply_text = message.text

    if not reply_text:
        return

    # Check if the original message was from the bot (a push notification)
    if original.from_user and original.from_user.is_bot:
        # Extract context from the original pushed message
        original_text = original.text or ""

        # Determine what kind of push this was a reply to
        if original_text.startswith("URGENT:"):
            # Reply to urgent email -- capture as action/response
            context = f"Reply to urgent notification: {original_text[:200]}"
            combined = f"{context}\n\nZack's response: {reply_text}"
            result = await capture_memory(combined, domain="email")
            await message.answer(f"Got it. {result}")
        elif "briefing" in original_text.lower()[:50]:
            # Reply to morning briefing
            result = await capture_memory(reply_text)
            await message.answer(result)
        else:
            # Generic reply to a push
            result = await capture_memory(reply_text)
            await message.answer(result)
    else:
        # Not a reply to the bot -- treat as free text
        from promaia.brain.engine import detect_mode
        mode_result = detect_mode(reply_text)
        domain = mode_result.get("mode", "working")
        result = await capture_memory(reply_text, domain=domain)
        await message.answer(result)
```

**Key insight:** Telegram's `reply_to_message` gives us the full original message. We don't need to store push metadata in a database -- the original message text itself provides context. The handler must be registered BEFORE the catch-all free-text handler but AFTER commands and voice.

### Pattern 5: Event Batching for Evening Digest
**What:** The evening digest should collect the day's events and present them as a single coherent message, not individual notifications.
**When to use:** PUSH-03 -- evening digest arrives as a single batched Telegram message.

The evening digest agent already produces a single output. The key is that when it runs at 4:30 PM, it should:
1. Query the day's events from brain.events
2. Include them in its context
3. Produce a single summary
4. Push that summary as one Telegram message

This is mostly handled by the agent's prompt and context loading. The only gap is timing (needs to run at 4:30 PM, not on a fixed interval) and the direct push mechanism.

### Anti-Patterns to Avoid
- **Running email-triage every 60 seconds with full LLM:** At $0.004/run, this costs $5.76/day. Use a lightweight SQL or API check to detect new mail, only trigger the LLM when needed.
- **Duplicating push logic in multiple places:** Centralize push delivery in one module (push_manager or post-execution hook). Don't add push code to both the executor and the event router.
- **Treating push and event routing as the same thing:** The event router handles async event delivery (interrupt emails). Direct push handles scheduled agent output (briefing, digest). They are complementary, not redundant.
- **Using the event router for time-of-day delivery:** Don't emit events with `held_until=6:00AM` and wait for the router to deliver them. Run the agent at the target time and push immediately.
- **Modifying the Telegram bot process for scheduling:** The scheduler process handles all timing. The bot process handles user input. Keep them separate. They share the token for sending.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Time-of-day scheduling | Cron-like parser | Simple sleep-until with datetime math | Only 3 agents, all daily. Don't need a full cron engine. |
| Cross-timezone time calculation | Manual UTC offset | `zoneinfo.ZoneInfo` + `datetime.now(tz)` | DST transitions handled correctly by stdlib |
| Gmail new-mail detection | Full Gmail API polling | SQL COUNT on existing Postgres gmail data | The Gmail pipeline already syncs. Just check the counts. |
| Message batching | Custom accumulator | Agent prompt + single push | The evening digest agent already produces batched output. |

**Key insight:** The infrastructure is already built. Phase 9 is mostly wiring and configuration, not new infrastructure. The scheduler, event router, Telegram channel, and agents all exist. The gaps are: timing, direct push, reply handling, and faster email detection.

## Common Pitfalls

### Pitfall 1: Scheduler Drift with sleep()
**What goes wrong:** Using `asyncio.sleep(seconds_until_target)` can drift because the sleep doesn't account for execution time of the previous run.
**Why it happens:** If a morning briefing agent takes 30 seconds to run, the next run starts at 6:00:30 AM instead of 6:00:00 AM. Over many days, this drifts.
**How to avoid:** Always recalculate the target time after each run. Don't use fixed intervals. Calculate `next_run = _next_run_time(schedule)` fresh each iteration.
**Warning signs:** Agent runs drifting later each day in the logs.

### Pitfall 2: Timezone-Naive Scheduling
**What goes wrong:** Agent scheduled for 6:00 AM ET runs at 6:00 AM UTC (1:00 AM ET in winter, 2:00 AM ET in summer).
**Why it happens:** Using `datetime.now()` without timezone, or storing schedule times as UTC.
**How to avoid:** All schedule times are in the user's timezone. The scheduler converts to UTC only for the `asyncio.sleep()` duration calculation. Use `datetime.now(ZoneInfo("America/New_York"))` consistently. The user_timezone is already set in `EventRouter.user_timezone = "America/New_York"` -- share this config.
**Warning signs:** Briefing arrives at wrong time. Especially breaks during DST transitions.

### Pitfall 3: Double-Pushing Scheduled Agent Output
**What goes wrong:** Morning briefing output gets pushed directly to Telegram AND also emitted as a `digest` event, which the event router routes to TelegramChannel, sending the same briefing twice.
**Why it happens:** The executor already calls `emit_agent_events()` after every run (Phase 7). The event router routes `digest` events to TelegramChannel (Phase 8).
**How to avoid:** Two options:
  - **Option A (recommended):** When an agent's output is directly pushed to Telegram, skip event emission for that agent run, OR emit the event but mark it pre-routed (set `routed_at` and `channel='telegram'` at emission time).
  - **Option B:** Change the emitter to not emit events for agents that have direct push configured.
**Warning signs:** Zack receiving the same briefing twice on Telegram.

### Pitfall 4: Email-Check Loop Missing New Mail
**What goes wrong:** The lightweight email check polls Postgres, but the Gmail sync pipeline hasn't ingested the new email yet.
**Why it happens:** There's a lag between Gmail receiving an email and the sync pipeline writing it to Postgres. If the sync runs every 480 minutes, the email-check loop waiting on Postgres sees nothing for 8 hours.
**How to avoid:** The email-check loop should either: (a) call the Gmail API directly for a lightweight `is:unread` check, or (b) ensure the Gmail sync pipeline runs frequently enough. Option (a) is simpler and has no dependency on sync timing.
**Warning signs:** "Urgent" emails arriving hours late despite the check loop running every 60 seconds.

### Pitfall 5: Rate Limiter Blocking Scheduled Pushes
**What goes wrong:** The morning briefing direct push is blocked by the 30-minute cooldown because a digest event was routed 10 minutes earlier.
**Why it happens:** The rate limiter in Phase 7 enforces 30-minute cooldown for all non-interrupt pushes. If the event router delivered a digest event shortly before the scheduled briefing, the cooldown blocks the briefing.
**How to avoid:** Direct pushes from scheduled agents should bypass the rate limiter. Rate limiting applies to the event router's async delivery, not to explicitly scheduled agent output. The rate limiter should distinguish between "router-initiated" and "scheduler-initiated" pushes.
**Warning signs:** Morning briefing not arriving because it was rate-limited.

### Pitfall 6: Bot Reply Handler Stealing Free-Text Messages
**What goes wrong:** The reply handler intercepts all messages that happen to be replies to any message (including the bot's own responses to commands).
**Why it happens:** `msg.reply_to_message is not None` matches replies to ANY bot message, not just push notifications.
**How to avoid:** Check that the replied-to message is a push notification, not a command response. Options: (a) prefix push messages with a unique marker (e.g., a zero-width character or a specific format), (b) store push message IDs in the DB and check against them, or (c) check the message text pattern (starts with "URGENT:", "Good morning", "Evening digest").
**Warning signs:** Replies to /briefing command responses being double-captured.

## Code Examples

### Agent Schedule Configuration
```json
// In promaia.config.json -- updated agent configs
{
  "name": "morning-briefing",
  "schedule": [["daily", "06:00"]],
  "interval_minutes": null,
  "push_to_telegram": true,
  // ... rest unchanged
}
```

### Dedup Check for Event Emission
```python
# Prevent double-push: when agent output is pushed directly,
# mark the emitted event as already routed to telegram

def emit_agent_events_with_push(
    agent_name: str,
    output: str,
    execution_id: int,
    pushed_to_channel: str | None = None,
) -> int:
    """Emit events, optionally pre-marking as routed if already pushed."""
    count = emit_agent_events(agent_name, output, execution_id)

    if pushed_to_channel and count > 0:
        db = get_postgres_db()
        db.execute(
            """UPDATE brain.events
               SET routed_at = NOW(), channel = %s
               WHERE urgency IS NOT NULL
                 AND routed_at IS NULL
                 AND source = %s
                 AND payload->>'execution_id' = %s::text""",
            (pushed_to_channel, agent_name, str(execution_id)),
        )
    return count
```

### Daily Cap for Rate Limiter
```python
# Extension to rate_limiter.py

def _check_daily_cap(self, channel_name: str) -> bool:
    """Check if daily notification cap (10) has been reached."""
    db = get_postgres_db()
    row = db.fetch_one(
        """SELECT COUNT(*) AS cnt FROM brain.events
           WHERE routed_at IS NOT NULL AND channel = %s
           AND routed_at > CURRENT_DATE""",
        (channel_name,),
    )
    daily_count = row["cnt"] if row else 0
    return daily_count < 10  # PUSH-04: daily cap of 10
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Fixed interval scheduling (1440min) | Time-of-day scheduling via `schedule` field | This phase | Briefings arrive at the right time |
| Agents passive (user checks dashboard) | Agents push output to Telegram proactively | This phase | Brain initiates contact |
| Email-triage every 8 hours | Lightweight email check every 60s + on-demand triage | This phase | Urgent emails within 1 minute |
| Event router only delivery mechanism | Direct push + event router for different use cases | This phase | Scheduled output is immediate, async events are routed |

**Deprecated/outdated:**
- `interval_minutes` field: Still works for backward compatibility, but `schedule` is now the primary scheduling mechanism. Agents with `schedule` set ignore `interval_minutes`.
- Evening digest prompt says "runs at 9pm" -- needs updating to 4:30 PM per PUSH-03.

## Key Integration Points

### 1. Scheduler: Time-of-Day Support
**File:** `promaia/agents/scheduler.py`, `_run_agent_loop()` method
**What:** When `agent.schedule` is set, use `_next_run_time()` sleep-until logic instead of fixed `interval_minutes`. Keep the existing interval logic as fallback for agents without schedules.
**Why here:** This is the single place where agent execution timing is controlled.

### 2. Executor/Scheduler: Post-Execution Push
**File:** `promaia/agents/scheduler.py`, after `executor.execute()` returns
**What:** If agent has `push_to_telegram=True` and execution succeeded, push output directly via TelegramChannel. Then emit events with pre-routed flag to prevent double delivery.
**Why here:** The push must happen right after execution, before the next sleep cycle.

### 3. Emitter: Pre-Routed Event Emission
**File:** `promaia/events/emitter.py`
**What:** Accept optional `pushed_to_channel` parameter. When set, mark emitted events as already routed to that channel.
**Why here:** Prevents the event router from re-delivering events that were already pushed directly.

### 4. Rate Limiter: Daily Cap
**File:** `promaia/events/rate_limiter.py`
**What:** Add daily cap check (10 per day) alongside existing hourly cap (10 per hour).
**Why here:** PUSH-04 explicitly requires a daily cap.

### 5. Telegram Bot: Reply Handler
**File:** `promaia/telegram/handlers/replies.py` (new)
**What:** Handler for `message.reply_to_message is not None` that processes inline replies to pushed notifications.
**Registration:** Must be registered after commands and voice, but BEFORE the catch-all free-text handler.
**Bot.py change:** Add `dp.include_router(replies.router)` between voice and messages routers.

### 6. Email Check Loop
**File:** `promaia/agents/scheduler.py` (new task in `start()`)
**What:** Lightweight loop that checks for new unread emails every 60 seconds and triggers email-triage agent when new mail is detected.
**Why here:** Runs as another asyncio task in the scheduler, alongside agent loops and the event router.

### 7. Agent Config Updates
**File:** `promaia.config.json`
**What:** Update the three agents' `schedule` fields and add `push_to_telegram` flag:
- morning-briefing: `schedule=[["daily", "06:00"]], push_to_telegram=true`
- evening-digest: `schedule=[["daily", "16:30"]], push_to_telegram=true`
- email-triage: `schedule=null, interval_minutes=480` (keep interval, but email-check loop triggers on-demand)

### 8. Evening Digest Prompt Update
**File:** `prompts/agent_evening_digest.md`
**What:** Change "runs at 9pm" to "runs at 4:30 PM" in the identity section. Adjust suggestions from "tonight's work" to "rest of the day" framing.

## Design Decisions for Planner

### Scheduling Strategy
The `AgentConfig.schedule` field already exists as `Optional[List[Tuple[str, str]]]`. It's unused because the scheduler only checks `interval_minutes`. The implementation plan is:

1. In `_run_agent_loop()`, check `agent.schedule` first. If set, use sleep-until logic.
2. If `agent.schedule` is None, fall back to `interval_minutes` (existing behavior).
3. This is backward compatible -- no existing behavior changes.

### Push vs Event Router
Two delivery mechanisms serve different purposes:

| Mechanism | Used For | Timing | Bypass Rate Limiter? |
|-----------|----------|--------|---------------------|
| Direct push | Scheduled agent output (briefing, digest) | Immediate after agent run | Yes |
| Event router | Async events (urgent emails, general notifications) | Within 30s of event creation | No (except interrupts) |

### Email Detection Strategy
Three options were evaluated:

| Option | How | Cost | Latency | Complexity |
|--------|-----|------|---------|------------|
| A: Reduce email-triage interval to 1min | Run full LLM triage every 60s | ~$5.76/day | ~60s | Low |
| B: SQL poll for new emails in Postgres | COUNT unread from synced gmail data | $0/day | Depends on sync frequency | Medium |
| C: Gmail API lightweight check | `users.messages.list(q=is:unread)` | $0/day (free API) | ~60s | Medium |

**Recommendation:** Option C (Gmail API check) or a hybrid: run a cheap SQL check first, and if the gmail sync pipeline runs frequently, that's sufficient. If the pipeline only runs every 480 minutes, Option C is needed.

**Practical note:** Looking at the codebase, gmail sync is tied to the email-triage agent's interval. So if email-triage runs every 480 minutes, new emails are only available in Postgres every 480 minutes. This means Option B won't work for sub-minute detection. Option C (direct Gmail API check) or Option A (cheaper interval) is needed.

**Simplest viable approach:** Reduce email-triage `interval_minutes` to 10 minutes ($0.58/day). This gives ~10-minute email detection latency, not 1-minute. For true 1-minute latency, need Option C (lightweight Gmail API check that triggers the full triage on demand). Given the cost constraints (~$20/month budget), 10-minute intervals at $17.40/month might be acceptable. Or use the lightweight Gmail check for $0 API cost.

### Cross-Channel Dedup (PUSH-04)
Currently, the event router delivers to ALL channels that `supports_urgency()` returns True for. Both DashboardChannel and TelegramChannel support `interrupt` and `digest`. This means every event gets delivered to both channels -- which is intentional (dashboard + mobile).

Cross-channel dedup means: don't count a single event delivered to both channels as two notifications against the daily cap. The rate limiter should count unique events, not unique deliveries.

Implementation: Track `event_id` in the rate limiter, not just channel+timestamp.

## Open Questions

1. **Gmail Sync Pipeline Frequency**
   - What we know: The gmail sync runs as part of the email-triage agent execution. When email-triage runs, it loads gmail data from Postgres (already synced) and classifies it.
   - What's unclear: Does the gmail data in Postgres update independently of agent runs, or only when the agent runs? If only when the agent runs, then a lightweight SQL check won't detect new emails between runs.
   - Recommendation: Investigate whether gmail sync is continuous or agent-triggered. If agent-triggered, use Gmail API `users.messages.list` for the check loop.

2. **Wake Signal vs Fixed Time**
   - What we know: PUSH-02 says "6:00 AM or wake signal." The requirement mentions an alternative trigger.
   - What's unclear: What "wake signal" means concretely. A Telegram message saying "I'm up"? First phone unlock?
   - Recommendation: Implement fixed time (6:00 AM) as the primary mechanism. Add a `/wakeup` Telegram command as a manual trigger. The scheduler checks if the briefing was already pushed today before sending.

3. **4:30 PM Evening Digest Timing**
   - What we know: The evening digest prompt says "runs at 9pm when Zack sits down to code." PUSH-03 says 4:30 PM.
   - What's unclear: Whether 4:30 PM is the final decision or if it should remain 9 PM.
   - Recommendation: Use 4:30 PM as specified in the requirement. The prompt will need updating ("end of afternoon" not "evening coding session"). The timing is configurable via `schedule` field so it's easy to adjust.

4. **Reply Processing Depth**
   - What we know: PUSH-05 says "brain processes the response." But what does processing mean?
   - What's unclear: Should a reply to an urgent email notification trigger an email draft? Just capture to memory? Mark the original event as handled?
   - Recommendation: Start simple -- capture the reply as a memory with context linking back to the original notification text. If the reply says "done" or "handled," mark any related action as complete. Don't attempt email drafting in Phase 9.

## Sources

### Primary (HIGH confidence)
- Codebase analysis: `promaia/agents/scheduler.py` -- current interval-based scheduling, asyncio task management
- Codebase analysis: `promaia/agents/agent_config.py` -- dormant `schedule` field, line 43
- Codebase analysis: `promaia/events/emitter.py` -- current urgency classification logic
- Codebase analysis: `promaia/events/router.py` -- event routing, quiet hours, TelegramChannel registration
- Codebase analysis: `promaia/events/rate_limiter.py` -- hourly cap, cooldown, interrupt bypass
- Codebase analysis: `promaia/telegram/channel.py` -- TelegramChannel.deliver() API
- Codebase analysis: `promaia/telegram/handlers/messages.py` -- catch-all handler pattern
- Codebase analysis: `promaia/telegram/bot.py` -- router registration order
- Codebase analysis: `promaia.config.json` -- current agent scheduling configuration
- Codebase analysis: `prompts/agent_email_triage.md` -- "Action Needed" section format
- Codebase analysis: `prompts/agent_evening_digest.md` -- current 9pm timing

### Secondary (MEDIUM confidence)
- Phase 7 research and verification: event bus architecture decisions
- Phase 8 research and verification: Telegram bot architecture, TelegramChannel decoupling decision
- `.planning/REQUIREMENTS.md`: PUSH-01 through PUSH-06 specifications

### Tertiary (LOW confidence)
- Gmail API rate limits: Training data suggests 250 quota units per user per second for `messages.list`. Need to verify current limits for the lightweight check approach.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - all libraries already installed, no new dependencies
- Architecture: HIGH - extends existing patterns (scheduler tasks, event router, Telegram channel), minimal new modules
- Pitfalls: HIGH - identified from direct analysis of existing code interactions (double-push, rate limiter conflicts, timezone handling)
- Email detection strategy: MEDIUM - depends on gmail sync pipeline frequency which needs investigation
- Reply processing: MEDIUM - requirement is vague ("brain processes the response"), simple approach recommended

**Research date:** 2026-03-07
**Valid until:** 2026-04-07 (stable -- internal architecture, no external dependency changes)
