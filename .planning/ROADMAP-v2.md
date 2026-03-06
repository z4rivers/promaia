# Roadmap v2: Promaia Activation — OpenClaw Parity + Beyond

## Context

v1 roadmap (Phases 1-4) built the foundation: Postgres+pgvector, brain schema, MCP tools, onboarding, agents, dashboard, Gmail pipeline. All infrastructure is LIVE as of 2026-03-06.

v2 focuses on making the system feel like a proactive personal agent — not a dashboard you check, but an assistant that reaches you, takes initiative, and turns ideas into action while you're walking the dog.

Inspired by OpenClaw's popularity but built on Promaia's stronger foundation (Postgres vs flat files, pgvector vs SQLite, brain context injection vs raw cron).

## Current State (2026-03-06)

### Working
- Brain MCP server: 15 tools, 56 memories, 10 domains, 98 profile traits
- Agent scheduler: 3 agents (morning-briefing, email-triage, evening-digest), $0.07/cycle
- Web dashboard: FastAPI, 5 pages, 6 CSS skins, live Postgres data
- Gmail pipeline: OAuth working, 34 emails ingested
- Action extraction: Gemini Flash via GOOGLE_API_KEY (working)
- Claude Agent SDK: available, agents run successfully outside Claude Code

### Broken/Blocked
- MuninnDB: embeddings dead (text-embedding-004 deprecated, index_size=0)
- Onboarding: exists but tacked on as CLAUDE.md instructions, not auto-triggered
- Dashboard skins: palette swaps, not the distinct designs specified in briefs
- No mobile access — no way to reach brain from phone

### Key Gaps vs OpenClaw
1. No messaging channel (can't talk to brain from phone)
2. No proactive push (agents write to Notion nobody checks)
3. No idea-to-repo pipeline (voice memo -> working project)
4. Onboarding not deeply integrated
5. No token budget discipline for sustained autonomous work

---

## Phase 5: Messaging Channel (THE critical path)

**Goal:** Talk to the brain from anywhere — phone, watch, car. Text or voice.

**Why first:** This unblocks everything else. Push notifications need a channel. Voice memos need an endpoint. The "idea on a dog walk" use case requires this.

### Research needed:
- Best Python Telegram bot library (python-telegram-bot vs aiogram vs telethon) — March 2026 state
- OpenClaw's messaging adapter pattern — how they handle multi-channel routing
- Whisper vs Google Speech-to-Text vs Deepgram for voice transcription — cost, latency, accuracy
- How to route incoming messages to brain.capture + trigger agent responses
- Signal bot feasibility (signal-cli?) vs Telegram vs WhatsApp Business API
- Security: authentication, rate limiting, abuse prevention for self-hosted bot

### Deliverables:
- [ ] Telegram bot that receives text messages and routes to brain.capture
- [ ] Voice note handling: receive audio -> transcribe -> capture -> respond
- [ ] Bot responds with brain search results, briefing summaries
- [ ] Bot can trigger agent runs on demand ("run email triage")
- [ ] Persistent session context across messages (not stateless)

### Architecture:
```
Phone (Telegram) -> Bot process -> Brain MCP tools -> Response -> Phone
                                -> Agent spawn (if needed)
                                -> brain.capture (always)
```

### Promaia assets to leverage:
- `promaia/chat/` (10,899L) — existing chat interface, may have reusable patterns
- `promaia/agents/executor.py` — agent spawning already works
- `promaia/brain/mcp_server.py` — all 15 brain tools available
- Agent configs already have `messaging_platform`, `messaging_channel_id`, `messaging_enabled` fields (unused)

---

## Phase 6: Proactive Push

**Goal:** Agents reach out to YOU. Morning briefing texts you at 5am. Email triage pings when something needs attention. Evening digest arrives at 8pm.

**Why:** Without push, the brain is passive — you have to check it. OpenClaw's #1 loved feature is that it initiates conversations.

### Research needed:
- Best patterns for agent -> user notification (Telegram inline, SMS via Twilio, push notifications)
- How OpenClaw handles proactive heartbeat messaging (their 30-min wake cycle)
- Priority/urgency filtering — what warrants an interrupt vs a batch digest
- Notification fatigue prevention — how to avoid becoming spam
- Cost comparison: Telegram (free) vs Twilio SMS ($0.0079/msg) vs push notification services

### Deliverables:
- [ ] Agent output routes to Telegram (not just Notion)
- [ ] Morning briefing delivered to phone at configured time
- [ ] Email triage sends alert for urgent items only
- [ ] Evening digest delivered at configured time
- [ ] User can respond inline to agent messages (two-way)
- [ ] Configurable urgency thresholds per agent

### Architecture:
```
Agent scheduler -> Agent executor -> Result
                                      |-> Notion (existing, keep)
                                      |-> Telegram push (NEW)
                                      |-> SMS fallback (optional)
```

---

## Phase 7: Idea-to-Repo Pipeline

**Goal:** Voice memo on a walk -> brain captures the idea -> spawns a Claude Code session -> scaffolds a project in a git worktree -> pushes notification "PetalPolicy repo ready, 3 files, branch created."

**Why:** This is the dream use case. The compound of messaging (Phase 5) + push (Phase 6) + autonomous code execution.

### Research needed:
- Claude Agent SDK headless mode — spawning long-running sessions programmatically
- Git worktree management for isolated project scaffolding
- Project template system — what boilerplate per project type (landing page, Python package, API)
- How to scope autonomous coding safely (sandbox, cost caps, approval gates)
- OpenClaw's self-extensible skills pattern — how they write their own plugins
- Best voice-to-structured-intent pipeline (transcribe -> extract project spec -> plan -> execute)

### Deliverables:
- [ ] "New project" intent detection from voice/text input
- [ ] Project type classification (landing page, API, Python tool, etc.)
- [ ] Git worktree creation + branch naming
- [ ] Claude Code spawned with project spec as prompt
- [ ] Progress updates pushed to Telegram
- [ ] Completion notification with branch name + file summary
- [ ] Cost cap per spawned session (configurable, default $2)

### Depends on: Phase 5 (messaging), Phase 6 (push)

---

## Phase 8: Onboarding Deep Integration

**Goal:** Onboarding is a first-class system flow, not CLAUDE.md instructions that the model may or may not follow.

**Why:** Zack's feedback: "having to tell the model to interview me is counter to the nature of what it should be." The profile (98 traits) should actively shape every interaction.

### Research needed:
- How OpenClaw handles personality calibration and user preference learning
- Progressive profiling best practices — when to ask vs when to infer
- Profile-driven prompt engineering — how traits modify system prompts dynamically
- Onboarding state machine patterns — auto-trigger, resume, completion detection

### Deliverables:
- [ ] Auto-detect incomplete profile at session start -> trigger interview
- [ ] Resume from last question (already partially built)
- [ ] Profile traits dynamically injected into agent system prompts
- [ ] Observable behavior changes: "I noticed you work mornings, scheduling deep work for AM"
- [ ] One contextual question per session max (not a survey)
- [ ] Profile completeness score visible on dashboard

---

## Phase 9: Activate MuninnDB Cognitive Memory

**Goal:** Fix MuninnDB's broken embedding layer and make Hebbian associative memory the core differentiator of zBrain.

**Why:** MuninnDB is the RIGHT architecture — associative recall, Hebbian strengthening, temporal decay, graph traversal. This is what makes a brain act like a brain, not a search engine. pgvector does similarity; MuninnDB does association. Both are needed. The only problem is a deprecated embedding model in v0.3.6-alpha.

### Research needed:
- MuninnDB v0.3.7+ release status — when Windows binary ships, or how to build from source
- Alternative embedding providers MuninnDB supports (Cohere, local ONNX, Voyage AI)
- Whether MuninnDB accepts a custom OpenAI-compatible base URL (route to Google via proxy)
- MuninnDB contributor community — can we submit a PR to update the Google model name?
- How to seed MuninnDB from existing pgvector memories (bulk sync)
- Optimal activation patterns — how agents should call activate to build Hebbian connections

### Deliverables:
- [ ] Embeddings working in MuninnDB (fix model or provider)
- [ ] All 56 pgvector memories synced to MuninnDB
- [ ] Agents use `activate` (not just `search`) in their execution loop
- [ ] Hebbian weights building from real usage (hebbian > 0.00)
- [ ] Temporal decay active — stale memories fade, reinforced ones persist
- [ ] Dashboard widget showing MuninnDB coherence score and association graph

---

## Phase 10: Token Budget + Autonomous Work Discipline

**Goal:** Sustained autonomous work without cost blowups. Agents that can work for hours safely.

### Research needed:
- Prompt caching strategies for Anthropic API (static system context prefix)
- Checkpoint/resume patterns for long-running agent tasks
- Model routing: when to use Haiku vs Sonnet vs Opus (cost/capability matrix March 2026)
- Budget guardrails: hard caps, iteration limits, cost alerting
- OpenClaw's lane queue pattern for serial execution safety

### Deliverables:
- [ ] Per-agent cost caps (configurable, default varies by agent type)
- [ ] Checkpoint files: agent writes status.md between steps, context resets, resumes
- [ ] Model routing in agent config: task_type -> model selection
- [ ] Cost tracking dashboard widget (daily/weekly/monthly spend)
- [ ] Alert when agent approaches budget cap (push to Telegram)
- [ ] Prompt caching: static context (profile, project states) cached, dynamic context fresh

---

## Phase Priority + Dependencies

```
Phase 5: Messaging Channel -----> Phase 6: Proactive Push -----> Phase 7: Idea-to-Repo
                                                                        |
Phase 8: Onboarding Integration (independent)                          |
Phase 9: Hebbian Memory (independent)                                  |
Phase 10: Token Budget (independent, but needed before Phase 7 goes heavy)
```

**Recommended order:** 5 -> 6 -> 8 -> 9 -> 10 -> 7

Phase 7 is the most ambitious and depends on everything else being solid first.

---

## Research Agent Tasks

For each phase, spawn a research agent to find:
1. Best current (March 2026) libraries/repos for the core technology
2. OpenClaw's implementation of the equivalent feature (it's open source)
3. Other popular personal agent projects doing the same thing
4. Cost/performance trade-offs
5. Security considerations for self-hosted personal agents

Store all research results in brain.memories with domain="zbrain" for cross-session recall.

---

## Success Criteria for v2

The system is "done" when:
1. Zack can voice-memo an idea while walking the dog
2. The idea is captured, acknowledged, and (if requested) acted on before he gets home
3. Morning briefing arrives on his phone at 3am when he wakes up
4. He never has to open Notion or a dashboard to know what's happening
5. The system knows him well enough to adjust tone, timing, and urgency without being told
6. Monthly cost stays under $50 for all agent activity

---

*Created: 2026-03-06 from OpenClaw gap analysis session*
*Base: v1 roadmap (Phases 1-4 complete)*
