# Session Handoff: 2026-03-07

## Morning Session

### First Real User Test
Zack used Promaia as a USER for the first time. Documented in `.planning/FIRST-USER-IMPRESSIONS.md`. Key finding: the brain layer works and is valuable, but every surface (Telegram, web, agents) is disconnected and feels lifeless.

### Three Fixes Shipped (morning)
1. **Telegram bot personality** — greetings get warm responses, questions get honest acknowledgment, captures get varied confirmations. VERIFIED WORKING.
2. **Scheduler catch-up** — `_missed_runs()` detects missed scheduled runs on startup and fires them immediately.
3. **Startup/shutdown notifications** — sends "Promaia is online/offline" to Telegram.

### Plans Written
- `.planning/v3.0-VISION.md` — North star: one brain, every surface, Gemini for conversation
- `.planning/v3.0-PLANS.md` — 9 plans (0.5a through 7), ordered for early wins
- `.planning/FIRST-USER-IMPRESSIONS.md` — Raw user feedback for Josie/Rose

---

## Afternoon Session — Plans Executed

### Plan 0.5a: Gmail Pipeline (DONE)
- Fresh Gmail sync: 17 new messages inserted (78 total across both accounts)
- Recovered 21 missing email bodies via resync
- Fixed email_date bug: dashboard was casting RFC 2822 text to date, now uses synced_time
- Email page renders 59 rows with sender, subject, snippet, unread indicators

### Plan 0.5b: Google Calendar (DONE)
- Calendar was already authenticated (token existed at ~/.promaia/)
- 7 calendars found: Family, Holidays, Polar training targets/results, etc.
- Sharon's birthday (March 4) confirmed visible on Family calendar
- Dashboard now pulls events from ALL calendars, replaces "Calendar not connected" placeholder
- Zack wants calendar to keep track of daily summaries as a personal record

### Plan 1: Unified Startup (DONE)
- Created `promaia/runner.py` — asyncio.gather runs scheduler + telegram + web dashboard
- `python -m promaia dev` boots everything in one command
- Bypasses heavy CLI imports via __main__.py fast path (team_commands module missing)
- Startup notification fires to Telegram
- Catch-up logic confirmed: detected and fired missed morning briefing on boot

### Plan 2: Scheduler Reliability (DONE)
- Heartbeat loop: writes to brain.events every 5 minutes
- `/api/scheduler/health` endpoint returns online/stale/unknown
- Exception resilience already existed in agent loops

### Plan 4: Dashboard Navigation (DONE)
- Top nav bar on every page: Promaia | Dashboard | Projects | Email | Profile
- Active page highlighting
- System health indicator: green/yellow/gray dot with live status
- Old bottom nav and back-links removed
- Notification badge + health poll every 60s

### Plan 3: Conversational Telegram Bot (NOT STARTED)
This is the product-defining change. The whole point.

## Files Changed (afternoon)
- `promaia/runner.py` — NEW: unified dev runner
- `promaia/__main__.py` — rewritten: fast-path for `dev` command
- `promaia/cli.py` — added `dev` subcommand (also still has team_commands import issue)
- `promaia/agents/scheduler.py` — added heartbeat loop
- `promaia/web/routers/dashboard.py` — calendar events, health API, email_date fix, active_page
- `promaia/web/templates/base.html` — top nav bar, health indicator
- `promaia/web/templates/dashboard.html` — calendar widget, removed old nav
- `promaia/web/templates/email.html` — removed old back-link and unused styles

## Not Committed Yet
All changes are unstaged. Next session should review and commit in logical groups.

## What's Next

### Priority 1: Plan 3 — Conversational Telegram Bot
1. Create `brain.conversations` table (chat_id, role, content, created_at)
2. Create `promaia/telegram/conversation.py`:
   - Load profile prefix (~200 tokens) + last 10 messages
   - Call Gemini Flash with personality system prompt + context + message
   - Return conversational response
3. Personality system prompt (currently hardcoded in conversation.py — TODO: move to brain)
4. Update handlers/messages.py and voice.py for conversational replies
5. Session synthesis: after 4 min silence with 3+ messages, Gemini summarizes

### Priority 2: Remaining plans
- Plan 5: Deploy to web (phone access)
- Plan 6: Life dashboard categories
- Plan 7: Prepare for sharing with Josie/Rose

### Roadmap addition Zack wanted to discuss
(Zack — you said there was a roadmap section to add. Tell next session what it is.)

## Decisions Made
- **PAUL:** Not installing the tool. Adopting the philosophy: Plan → Apply → Unify. Each plan closes with reconciliation of planned vs actual.
- **GSD replaced** by PAUL-inspired workflow for this stage (shipping product, not greenfield)
- **Calendar:** Connected, lightly used. Future use: daily summary logging, becoming useful once naturally incorporated
- **Approval prefs:** Don't surface routine verification for approval. Only UX-affecting decisions. One sentence on WHY, no jargon. (Saved to profile.)

## Known Issues
- `DEEPGRAM_API_KEY` not in .env — voice notes will crash
- `promaia.cli.team_commands` module missing — full `maia` CLI won't boot, `python -m promaia dev` works fine
- Calendar `%#d` strftime is Windows-specific — needs `%-d` fallback for Linux
- email_date stored as RFC 2822 text — proper date ordering needs parsing or new column
