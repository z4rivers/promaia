# First User Impressions: Promaia/zBrain
**Date:** 2026-03-07
**Tester:** Zack Turner (builder, first real user)
**Documented by:** Claude (session partner)

## Context

Zack sat down with Promaia for the first time as a USER, not a developer. Computer was off at 6am (scheduled briefing time), turned on later, manually started all services, and walked through the experience end to end. This document captures raw feedback for Josie, Rose, and future development.

---

## What Works

### The Brain (Core Memory Layer)
- **Profile:** 98 traits loaded at session start — identity, cognitive style, relationships, work patterns, values. Rich and accurate.
- **Semantic memory:** Thoughts captured with embeddings, searchable by meaning, actions auto-extracted.
- **Session continuity:** Every Claude Code session starts with full profile + briefing. No re-explaining yourself.
- **The "thought jar":** Toss something in, it sticks. Zack said: "I LOVE this — am not discounting it."

### What This Means
The deep persistent memory layer IS the product's core value. It works. The problem is that this magic only lives inside Claude Code terminal sessions. It doesn't reach the user where they actually are.

---

## What's Broken

### 1. Morning Briefing Never Arrived
- Computer was off at 6am. Scheduler runs time-of-day scheduling.
- When Zack turned on the PC and started the scheduler later, it calculated "next run: tomorrow 6am" and went to sleep.
- **No catch-up logic.** Missed runs are simply lost.

### 2. Telegram Bot is a Filing Cabinet
- Zack texted "are you there" — bot responded: "Captured."
- Every single message gets the same response: "Captured." or "Captured. Extracted N action(s)."
- No conversational awareness. No personality. No use of the rich profile data.
- Treats greetings, questions, and thoughts identically — everything is filed, nothing is answered.
- **Zack's words:** "I want it to be your voice saying 'got it' and saying good morning, ready to chat."

### 3. Web Dashboard is a Skeleton
- **No navigation:** Projects page has no links back. No nav bar between pages.
- **Calendar widget:** Says "Calendar not connected" — hardcoded placeholder, never wired up.
- **Email page:** Shows "Email Intelligence" header with zero content beneath it.
- **Not interactive:** Read-only display, no input fields, no ability to act from the dashboard.
- **Localhost only:** Dies when PC sleeps. Not accessible from phone.

### 4. Notion Pages Also Empty
- Not just a web display issue — the underlying data store has gaps.
- Agents may be running but not writing meaningful output to Notion or Postgres.
- The whole pipeline from agent execution to data storage to display is hollow.

### 5. Startup is 3-4 Separate Processes
- Brain MCP (auto-starts with Claude Code)
- Scheduler (separate terminal)
- Telegram bot (separate terminal)
- Web dashboard (separate terminal)
- **Should be ONE command.** "Start Promaia" and everything comes alive.

---

## New Requirements (Not on Current Roadmap)

### Startup & Lifecycle
1. **Single-command startup** — one process boots scheduler, Telegram bot, and web dashboard together.
2. **Catch-up on missed runs** — if the 6am briefing was missed, fire it immediately on startup.
3. **Shutdown notification** — send Telegram message "Promaia is offline" when shutting down.
4. **Startup notification** — send "Promaia is online" when booting up.

### Telegram Bot Personality
5. **Conversational responses** — not "Captured." but "Got it" / "Good morning, what's on your mind?" / personality.
6. **Distinguish conversation from capture** — "are you there" is a greeting, not a memory to file.
7. **Use the profile** — the bot knows who Zack is. It should sound like it.

### Dashboard as Life Central
8. **Category tabs across the top** — All, Projects, Health, Finance. This is a LIFE management dashboard.
9. **Kanban boards** for project tracking or high-level priority indicators.
10. **Focus dashboards** — drill into any project for its own dedicated view.
11. **Interactive input fields** — act from the dashboard, not just read it.
12. **Persistent navigation** across all pages.
13. **Google Calendar integration** on the dashboard (not a placeholder).
14. **Hosted on the real web** — accessible from phone, always on.

### Proactive Intelligence (Redefining "Proactive")
15. **Project intent + success criteria** — each project needs a captured definition of what "done" looks like.
16. **Active drive toward goals** — the brain should monitor gap between intent and reality and push when things drift. Not just scheduled broadcasts.
17. **Proactive means initiative** — not cron jobs. The system should think about what needs attention and surface it.

---

## Vision Reframe

The current roadmap was written from an engineering perspective: "get agents running, get data flowing, get push working." Zack's feedback is from the USER perspective: "what does this feel like?"

**What was built:** A brain with plumbing. Schedulers, event buses, model routers, cost trackers.

**What's needed:** A life operating system. The brain already holds health data, financial data, relationship data, career data. It needs surfaces to show through and intelligence to act on it.

The "Dashboard redesign" is currently listed as OUT OF SCOPE in requirements. That needs to change. The dashboard isn't cosmetic — it's the primary visual interface to the brain.

**Zack's core insight:** "Right now I see a thought container I can toss things into. What I want is a partner that knows me, drives my projects forward, and manages my life."

---

## Suggested Priority for Immediate Fixes

### Quick Wins (high feel, low effort)
1. Fix Telegram responses — swap "Captured." for conversational language
2. Add catch-up logic to scheduler — check for missed runs on startup
3. Add startup/shutdown Telegram notifications
4. Add nav bar to dashboard pages

### Medium Effort
5. Single-command startup (unified process manager)
6. Wire up email data on dashboard
7. Calendar integration on dashboard

### Larger Work
8. Conversational Telegram (actually use brain context in responses)
9. Dashboard category tabs and interactive features
10. Project intent tracking and proactive gap monitoring
11. Web hosting

---

*This document is a living reference. Update as impressions evolve and fixes land.*
