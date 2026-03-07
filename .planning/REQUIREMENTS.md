# Requirements: zBrain v2.0 Proactive Agent

**Defined:** 2026-03-06
**Core Value:** A proactive AI assistant that reaches YOU -- not a dashboard you check, but a system that initiates, remembers, and acts autonomously.

## v2 Requirements

Requirements for v2.0 milestone. Each maps to roadmap phases.

### Validation & Data Pipeline

- [x] **VALID-01**: Agent scheduler runs all 3 agents (morning-briefing, email-triage, evening-digest) successfully via SDK
- [x] **VALID-02**: Gmail context loads from Postgres (not .md files on disk) in agent executor
- [x] **VALID-03**: SQL dialect bugs fixed (jsonb operators, timestamp casting, unified_content table reference). Note: files.py row['thread_id'] fix already applied.
- [x] **VALID-04**: Agent output is coherent and surfaces real data (not hallucinated)

### Model Routing & Cost

- [x] **ROUTE-01**: Model router selects appropriate model per task type (classify, extract, embed, synthesize, reason, create, heartbeat)
- [ ] **ROUTE-02**: Fallback chain activates when primary model fails (next tier up)
- [ ] **ROUTE-03**: Agent prompts restructured into implicit-cacheable tiers: stable system instruction prefix (anchor tier), tool declarations (tools tier), per-run dynamic context (context tier). Prompt ordering maximizes Gemini implicit cache hits on the stable prefix. Explicit cache_control markers are not used -- implicit caching is preferred for 3x/day run volume per research findings.
- [ ] **ROUTE-04**: Dynamic tool injection reduces prompt size by only including tools each agent needs
- [ ] **ROUTE-05**: AgentContext dataclass provides standardized awareness (user profile, time, goals, events, domain state) to all agents
- [x] **COST-01**: brain.agent_costs table logs every API call with model, tokens, and cost
- [ ] **COST-02**: Per-run budget cap enforced (configurable, default $0.50)
- [ ] **COST-03**: Daily budget cap skips non-critical runs when exceeded
- [x] **COST-04**: Each agent uses assigned model per ModelRouter configuration (default: gemini-3-flash-preview for all three agents)

### Event Bus & Notifications

- [ ] **EVENT-01**: brain.events has urgency column (interrupt/digest/archive) with routing metadata
- [ ] **EVENT-02**: Event router polls unrouted events every 30 seconds and routes by urgency
- [ ] **EVENT-03**: Quiet hours (9pm-6am) respected -- non-critical interrupts queued for morning
- [ ] **EVENT-04**: Rate limiting prevents notification spam (max 10 pushes/hour, 30-min cooldown between non-urgent)
- [ ] **EVENT-05**: Channel registry supports abstract channel interface with dashboard fallback
- [ ] **EVENT-06**: Dashboard shows unread notification badge from unrouted events
- [ ] **EVENT-07**: Agents emit routable events with correct urgency after each run

### Telegram Bot

- [ ] **TELE-01**: Telegram bot responds to text messages from whitelisted chat IDs
- [ ] **TELE-02**: Bot silently ignores messages from non-whitelisted users
- [ ] **TELE-03**: /briefing command triggers and returns morning briefing content
- [ ] **TELE-04**: /search, /capture, /projects, /actions commands work against brain
- [ ] **TELE-05**: Free-text messages auto-captured to brain with domain detection
- [ ] **TELE-06**: Voice notes transcribed via Deepgram Nova-3 and processed as text
- [ ] **TELE-07**: Bot registered as event router channel -- interrupt events pushed within 30 seconds
- [ ] **TELE-08**: Bot runs as persistent daemon with auto-reconnect

### Proactive Push

- [ ] **PUSH-01**: Email-triage classifies each finding as interrupt/digest/archive
- [ ] **PUSH-02**: Morning briefing auto-pushes to Telegram at scheduled time (6:00 AM or wake signal)
- [ ] **PUSH-03**: Evening digest batches day's events into single Telegram message at 4:30 PM
- [ ] **PUSH-04**: Notification fatigue prevention: 30-min cooldown, daily cap (10), cross-channel dedup, batching
- [ ] **PUSH-05**: User can reply inline to Telegram pushes and brain processes the response
- [ ] **PUSH-06**: Urgent emails reach Zack within 1 minute via interrupt push

### Memory & Polish

- [ ] **MEM-01**: MuninnDB health monitored every 5 minutes with graceful fallback to Postgres-only
- [ ] **MEM-02**: Memory decay tiers (core/active/warm/cold/archive) recalculated nightly based on access
- [ ] **MEM-03**: Association strengthening tracks co-retrieved memories and boosts linked results
- [ ] **MEM-04**: Profile-driven prompt (~200 tokens of "who Zack is") injected as cached prefix in every agent call
- [ ] **MEM-05**: Session handoff: end-of-session summary auto-captured, next session briefing surfaces yesterday's work

## Future Requirements

Deferred beyond v2.0.

### Idea Pipeline

- **IDEA-01**: Voice capture spawns Idea-to-Spec agent that produces structured spec
- **IDEA-02**: Spec can spawn Claude Code worktree for scaffolding

### Voice Interface

- **VOICE-01**: Twilio voice calls for hands-free interaction while driving
- **VOICE-02**: Wake-word activation for ambient listening

### Advanced Memory

- **AMEM-01**: Hebbian learning natively in Postgres (replace MuninnDB dependency)
- **AMEM-02**: Temporal narrative construction from memory graph

## Out of Scope

| Feature | Reason |
|---------|--------|
| Desktop Electron app | Josie's domain |
| React web chat app | Josie's domain |
| OpenAI API dependency | Using Gemini instead |
| Twilio voice calls | $12-31/month, higher complexity -- defer to post-v2 |
| Dashboard redesign | Works well enough, agents first |
| Multi-user support | Single-user system by design |
| Idea-to-Repo pipeline | Security risk, scope creep -- replaced by lighter Idea-to-Spec |

## Traceability

Updated during v2.0 roadmap creation (2026-03-06).

| Requirement | Phase | Status |
|-------------|-------|--------|
| VALID-01 | Phase 5 | Complete |
| VALID-02 | Phase 5 | Complete |
| VALID-03 | Phase 5 | Complete |
| VALID-04 | Phase 5 | Complete |
| ROUTE-01 | Phase 6 | Complete |
| ROUTE-02 | Phase 6 | Pending |
| ROUTE-03 | Phase 6 | Pending |
| ROUTE-04 | Phase 6 | Pending |
| ROUTE-05 | Phase 6 | Pending |
| COST-01 | Phase 6 | Complete |
| COST-02 | Phase 6 | Pending |
| COST-03 | Phase 6 | Pending |
| COST-04 | Phase 6 | Complete |
| EVENT-01 | Phase 7 | Pending |
| EVENT-02 | Phase 7 | Pending |
| EVENT-03 | Phase 7 | Pending |
| EVENT-04 | Phase 7 | Pending |
| EVENT-05 | Phase 7 | Pending |
| EVENT-06 | Phase 7 | Pending |
| EVENT-07 | Phase 7 | Pending |
| TELE-01 | Phase 8 | Pending |
| TELE-02 | Phase 8 | Pending |
| TELE-03 | Phase 8 | Pending |
| TELE-04 | Phase 8 | Pending |
| TELE-05 | Phase 8 | Pending |
| TELE-06 | Phase 8 | Pending |
| TELE-07 | Phase 8 | Pending |
| TELE-08 | Phase 8 | Pending |
| PUSH-01 | Phase 9 | Pending |
| PUSH-02 | Phase 9 | Pending |
| PUSH-03 | Phase 9 | Pending |
| PUSH-04 | Phase 9 | Pending |
| PUSH-05 | Phase 9 | Pending |
| PUSH-06 | Phase 9 | Pending |
| MEM-01 | Phase 10 | Pending |
| MEM-02 | Phase 10 | Pending |
| MEM-03 | Phase 10 | Pending |
| MEM-04 | Phase 10 | Pending |
| MEM-05 | Phase 10 | Pending |

**Coverage:**
- v2 requirements: 39 total
- Mapped to phases: 39
- Unmapped: 0

---
*Requirements defined: 2026-03-06*
*Last updated: 2026-03-07 after Phase 6 checker revision (ROUTE-03 implicit caching, COST-04 model assignment)*
