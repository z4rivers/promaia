# Roadmap: zBrain

## Milestones

- **v1.0 Foundation** -- Phases 01-04 (shipped 2026-03-06) [archive](milestones/v1.0-ROADMAP.md)
- **v2.0 Proactive Agent** -- Phases 5-10 (in progress)

## Phases

<details>
<summary>v1.0 Foundation (Phases 01-04) -- SHIPPED 2026-03-06</summary>

- [x] Phase 01: Postgres Foundation (3/3 plans) -- 2026-03-04
- [x] Phase 02: Brain Schema and MCP Tools (3/3 plans) -- 2026-03-05
- [x] Phase 03.1: Onboarding Module (3/3 plans) -- 2026-03-05
- [x] Phase 04: Full Platform Activation (1/1 formal plan + 5 informal) -- 2026-03-06

</details>

### v2.0 Proactive Agent

- [x] **Phase 5: Validate & Activate** - Fix agent data pipeline, kill SQL bugs, get real coherent agent runs
- [x] **Phase 6: Waste Elimination + Spend Visibility** - Cache what repeats, track what you spend, kill runaway loops (completed 2026-03-07)
- [x] **Phase 7: Event Bus + Notification Layer** - Urgency-routed events, quiet hours, dashboard badge (completed 2026-03-07)
- [x] **Phase 8: Telegram Bot** - Mobile brain access via text, voice, and commands (completed 2026-03-07)
- [x] **Phase 9: Proactive Push** - Agents initiate contact: morning briefing, urgent alerts, evening digest (completed 2026-03-07)
- [ ] **Phase 10: Memory Deepening + Polish** - Decay tiers, association strengthening, profile-driven prompts, session handoff
- [ ] **Phase 11: Conversational Telegram Bot** - Gemini-powered conversation with brain context, personality manifest, session synthesis

## Phase Details

### Phase 5: Validate & Activate
**Goal**: Agents produce real, useful output from live data -- no hallucinated facts, no broken queries, no missing context
**Depends on**: v1.0 (complete)
**Requirements**: VALID-01, VALID-02, VALID-03, VALID-04
**Success Criteria** (what must be TRUE):
  1. All three agents (morning-briefing, email-triage, evening-digest) complete a full SDK run without errors
  2. Agent output references actual emails, calendar events, and brain memories -- not fabricated content
  3. Gmail context appears in agent output (loaded from Postgres, not disk files)
  4. No SQL errors in agent logs related to jsonb, timestamp, or table references
**Plans:** 3/3 plans complete

Plans:
- [x] 05-01-PLAN.md -- Fix Gmail content pipeline (Postgres fallback + message body population)
- [x] 05-02-PLAN.md -- Agent config + prompt hardening (schedule change + anti-hallucination)
- [x] 05-03-PLAN.md -- Full validation run + human verification of agent output

### Phase 6: Waste Elimination + Spend Visibility
**Goal**: Best possible results at minimum cost — never pay twice for the same work, never burn time on garbage output, never let a bug drain the wallet silently
**Depends on**: Phase 5
**Requirements**: ROUTE-01, ROUTE-02, ROUTE-03, ROUTE-04, ROUTE-05, COST-01, COST-02, COST-03, COST-04
**Success Criteria** (what must be TRUE):
  1. Repeated system prompts and stable context blocks are cached — not re-sent and re-billed on every call
  2. Already-processed emails/memories are not re-summarized or re-embedded on subsequent agent runs
  3. Every agent run logs its model, token count, and dollar cost to a tracking table — visible on demand
  4. A runaway loop (agent stuck retrying or iterating with no progress) is detected and killed automatically
  5. Zack can see a daily/weekly cost summary without digging through logs
  6. Model selection is intentional: best model for reasoning tasks, lightweight model only where output quality is genuinely identical (pure extraction, formatting)
  7. Smart batching: combine related queries into fewer, better-structured calls instead of many small ones
**Plans:** 4/4 plans complete

Plans:
- [x] 06-01-PLAN.md -- Model routing infrastructure + cost tracking table + pricing computation
- [x] 06-02-PLAN.md -- AgentContext dataclass + prompt restructuring for Gemini optimization
- [x] 06-03-PLAN.md -- Gemini execution path + budget enforcement + fallback chain
- [x] 06-04-PLAN.md -- End-to-end validation run + human verification of output quality and cost

### Phase 7: Event Bus + Notification Layer
**Goal**: Agents produce routable events with urgency tiers, and a polling loop delivers them to the right channel at the right time
**Depends on**: Phase 6
**Requirements**: EVENT-01, EVENT-02, EVENT-03, EVENT-04, EVENT-05, EVENT-06, EVENT-07
**Success Criteria** (what must be TRUE):
  1. After an agent run completes, events appear in brain.events with correct urgency (interrupt/digest/archive)
  2. The event router delivers interrupt events within 30 seconds of creation
  3. Events generated between 9pm and 6am are held until morning (quiet hours)
  4. Dashboard shows an unread notification count badge that clears when viewed
  5. No more than 10 push notifications are sent in any one-hour window
**Plans:** 3/3 plans complete

Plans:
- [ ] 07-01-PLAN.md -- Schema extension + event models + emitter + executor integration
- [ ] 07-02-PLAN.md -- Event router + channels + rate limiter + scheduler integration
- [ ] 07-03-PLAN.md -- Dashboard notification badge + API endpoints

### Phase 8: Telegram Bot
**Goal**: Zack can talk to the brain from his phone -- text, voice, commands -- and the brain talks back
**Depends on**: Phase 7
**Requirements**: TELE-01, TELE-02, TELE-03, TELE-04, TELE-05, TELE-06, TELE-07, TELE-08
**Success Criteria** (what must be TRUE):
  1. Sending a text message to the bot from a whitelisted Telegram account gets a brain-powered response
  2. Messages from unknown users are silently dropped (no error, no response)
  3. /briefing returns the current morning briefing; /search, /capture, /projects, /actions work against live brain data
  4. Sending a voice note produces a text transcription and a brain response based on that transcription
  5. The bot stays running as a daemon and reconnects automatically after network interruptions
**Plans:** 2/2 plans complete

Plans:
- [x] 08-01-PLAN.md -- Core bot infrastructure + text commands + brain operations + daemon CLI
- [x] 08-02-PLAN.md -- Voice transcription (Deepgram Nova-3) + event channel integration + human verification

### Phase 9: Proactive Push
**Goal**: The brain reaches Zack without being asked -- morning briefing on the phone at wake-up, urgent emails within a minute, evening digest at end of day
**Depends on**: Phase 8
**Requirements**: PUSH-01, PUSH-02, PUSH-03, PUSH-04, PUSH-05, PUSH-06
**Success Criteria** (what must be TRUE):
  1. Morning briefing arrives on Telegram at 6:00 AM (or configured wake time) without any user action
  2. An urgent email classified as "interrupt" by email-triage reaches Telegram within 1 minute
  3. Evening digest arrives as a single batched Telegram message at 4:30 PM
  4. Zack can reply inline to a pushed Telegram message and the brain processes the response
  5. Notification fatigue controls are active: 30-min cooldown between non-urgent pushes, daily cap of 10, cross-channel dedup
**Plans:** 2 plans

Plans:
- [x] 09-01-PLAN.md -- Time-of-day scheduling + direct Telegram push + emitter pre-routing + config
- [x] 09-02-PLAN.md -- Fatigue controls + reply handler + email-triage interval + human verification

### Phase 10: Memory Deepening + Polish
**Goal**: The brain gets smarter over time -- memories decay or strengthen based on use, the profile shapes every agent call, and sessions resume seamlessly
**Depends on**: Phase 9
**Requirements**: MEM-01, MEM-02, MEM-03, MEM-04, MEM-05
**Success Criteria** (what must be TRUE):
  1. MuninnDB health is checked every 5 minutes; if it goes down, brain operations continue on Postgres without interruption
  2. A nightly job recalculates memory tiers (core/active/warm/cold/archive) and stale memories rank lower in search results
  3. Memories that are frequently retrieved together score higher when either one is searched (association strengthening)
  4. Every agent call includes a ~200-token cached profile prefix describing who Zack is, his schedule, and his preferences
  5. Ending a session auto-captures a summary; the next session's briefing surfaces yesterday's context
**Plans**: TBD

### Phase 11: Conversational Telegram Bot
**Goal**: Telegram becomes a real conversational surface -- Gemini-powered responses using brain context, personality manifest, and conversation history
**Depends on**: Phase 9
**Requirements**: CONV-01, CONV-02, CONV-03, CONV-04, CONV-05
**Success Criteria** (what must be TRUE):
  1. Text "how are my projects looking?" on Telegram and get a real answer using brain context
  2. Voice note about a project idea gets intelligent acknowledgment, not "Captured."
  3. Conversation history (last 5 messages) provides continuity within a session
  4. Personality manifest loaded as system prompt -- Promaia sounds like Promaia, not a generic bot
  5. After 5+ min silence with 3+ messages, a synthesized session summary is stored as a single memory
**Plans**: TBD

## Progress

**Execution Order:** Phases execute in numeric order: 5 -> 6 -> 7 -> 8 -> 9 -> 10

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 01. Postgres Foundation | v1.0 | 3/3 | Complete | 2026-03-04 |
| 02. Brain Schema + MCP | v1.0 | 3/3 | Complete | 2026-03-05 |
| 03.1 Onboarding Module | v1.0 | 3/3 | Complete | 2026-03-05 |
| 04. Platform Activation | v1.0 | 1/1 | Complete | 2026-03-06 |
| 5. Validate & Activate | v2.0 | Complete    | 2026-03-06 | 2026-03-06 |
| 6. Waste Elimination + Spend Visibility | v2.0 | 4/4 | Complete | 2026-03-07 |
| 7. Event Bus + Notification Layer | v2.0 | Complete    | 2026-03-07 | - |
| 8. Telegram Bot | v2.0 | Complete    | 2026-03-07 | 2026-03-07 |
| 9. Proactive Push | v2.0 | 2/2 | Complete | 2026-03-07 |
| 10. Memory Deepening + Polish | v2.0 | 0/? | Not started | - |
| 11. Conversational Telegram Bot | v2.0 | 0/? | Discussion | - |

---
*Created: 2026-03-04*
*v1.0 archived: 2026-03-06*
*v2.0 roadmap added: 2026-03-06*
