# Feature Research

**Domain:** Personal AI Brain / Proactive Agent System
**Researched:** 2026-03-04
**Confidence:** MEDIUM-HIGH (core patterns well-documented; specific Promaia integration points inferred from codebase context)

---

## Feature Landscape

### Table Stakes (Users Expect These)

These are the baseline behaviors that make the system feel like an AI brain rather than just a chatbot with memory. Missing any of these produces the "amnesia problem" zBrain explicitly exists to solve.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Persistent cross-session memory | Core value prop — without this the system is just another chatbot | MEDIUM | Brain schema in Railway Volumes. Memories, domains, contexts tables. Depends on libSQL/MuninnDB migration completing first. |
| Session startup briefing | Users expect an "AI assistant" to orient them, not require them to re-explain everything | MEDIUM | On `maia chat` start: query brain for open actions, recent domains, stale projects. Format as brief summary. Time-boxed to <5 seconds. |
| Action extraction from conversations | Users assume the AI will notice when they say "I need to do X" and remember it | MEDIUM | Post-conversation pass (async, not blocking). LLM prompt over transcript to extract commitments. Store to `brain.actions`. |
| Cloud access from any device | Any "personal brain" tool must work from phone — desktop-only feels broken | MEDIUM | Railway Volumes REST API. No bespoke mobile app needed for v1 — claude.ai on iPhone hits brain via MCP or REST. |
| Stale project / dormant alert | Users expect the brain to proactively notice what's been neglected | LOW-MEDIUM | Simple: query `brain.domains` for last-touched timestamp > threshold. Alert on startup briefing or heartbeat. |
| Standing directives per project | Users want to tell the AI once "always do X for project Y" and not repeat it | LOW | Static config per domain/project. Read at session start. Injected into system prompt for relevant context. |

### Differentiators (Competitive Advantage)

These are what make zBrain meaningfully different from generic AI memory tools like MemSync, AI Context Flow, or a plain libSQL/MuninnDB + Claude setup.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Heartbeat agent (autonomous overnight work) | The brain actively works between sessions — most AI tools are purely reactive | HIGH | Windows Task Scheduler + Python script. Scan → pick work → execute → report. HEARTBEAT.md checklist pattern (OpenClaw-inspired). Needs active-hours guard to avoid 3 AM noise. |
| Intelligent model routing (task-based, not fallback) | Right model for each task — Gemini Flash for cheap/fast, Claude for nuance/reasoning | MEDIUM | Router reads task_type tag. Gemini 2.5 Flash: embeddings, classification, summarization. Claude Sonnet: reasoning, directives, session briefing. Not a fallback chain — deterministic by task. |
| Brain ingestion pipeline (YouTube, web, docs) | Zack captures via voice and video — the brain must absorb these formats | MEDIUM-HIGH | YouTube: `youtube-transcript-api` → chunk → embed → store. Web: fetch + extract → chunk → embed. Docs: parse → chunk → embed. Google `text-embedding-004` for all. |
| Gemini as first-class specialist (not fallback) | Covers all cheap tasks under existing Google AI Premium — no new API costs | LOW-MEDIUM | Model adapter already exists in Promaia. Add `task_type` routing table mapping task categories to model IDs. Remove OpenAI dependency for cheap tasks. |
| Domain-aware context injection | Briefings and heartbeat results are scoped per project domain, not a global blob | MEDIUM | `brain.domains` table. Each domain has directives, last activity, open actions. Context serializer pulls domain-specific slice. |
| Overnight work reporting | Heartbeat produces a written report Zack reads on iPhone next morning | LOW | Heartbeat loop writes `brain.reports` record. Session briefing includes "overnight summary" section if report exists from last N hours. |

### Anti-Features (Commonly Requested, Often Problematic)

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Real-time conversation monitoring | Seems powerful — AI watches everything you type | Requires always-on process, privacy surface, API cost per keystroke. No clear trigger for "when is a session over?" | Post-session extraction: user runs `maia reflect` or heartbeat scans recent chat exports. Async is fine. |
| Automatic memory deletion / forgetting | Feels important for privacy, sounds smart | Creates unreliable behavior. Users forget what they told it, then wonder why it "forgot" something important. | Manual archive: `maia forget [domain]`. Keep raw data, just lower relevance weight in retrieval. |
| Kanban / task board UI | Natural request once actions are being captured | Build the brain first. A UI before the data model is stable means rework. Daughter's Promaia already has desktop UI work in progress. | v1: actions live in DB, surface in briefing. v1.1: Kanban on top of stable schema. |
| Continuous background sync + embedding | "Keep everything up to date" feels right | Embeddings cost tokens. Running continuously burns Google AI quota and adds latency to system. Most content doesn't change. | Scheduled sync: `maia sync` on demand or via heartbeat once daily. On-change triggers only for high-priority domains. |
| Cross-user / shared brain | Collaboration feels like a natural extension | zBrain is a personal system. Shared memory = shared context = confusion about whose actions are whose. Promaia's multi-workspace handles teams separately. | Keep brain schema user-scoped. Multi-user is Promaia's problem, not zBrain's. |
| Email triage built into heartbeat | Zack doesn't use task managers — Gmail integration seems obvious | Needs brain foundation first. Adding Gmail to heartbeat v1 creates a complex first milestone. Email triage is a separate behavioral domain. | v1.1 feature. Brain schema must be stable before adding new ingestion sources to heartbeat. |

---

## Feature Dependencies

```
[libSQL/MuninnDB + pgvector migration]
    └──required by──> [Brain schema creation]
                          └──required by──> [Session briefing]
                          └──required by──> [Action extraction]
                          └──required by──> [Standing directives]
                          └──required by──> [Stale project alerts]
                          └──required by──> [Heartbeat agent]
                          └──required by──> [Brain ingestion pipeline]

[Brain schema creation]
    └──required by──> [Intelligent model routing table]
                          └──enhances──> [Heartbeat agent]
                          └──enhances──> [Brain ingestion pipeline]

[Session briefing]
    └──required by (validates)──> [Overnight work reporting]

[Gemini model routing]
    └──required by──> [Brain ingestion pipeline (embeddings via text-embedding-004)]

[Promaia: Agent orchestration architecture] (already built)
    └──reused by──> [Heartbeat agent]
    └──reused by──> [Action extraction]

[Promaia: Multi-model LLM adapter] (already built)
    └──extended by──> [Intelligent model routing]

[Promaia: Scheduled agent system] (partially built)
    └──extended by──> [Heartbeat agent]
```

### Dependency Notes

- **libSQL/MuninnDB migration is the critical path blocker:** Every single new feature depends on the brain schema, which depends on Railway Volumes being the target. Daughter's `libsql-changeover` branch is 70% done — completing this unlocks everything else.
- **Session briefing validates the schema before heartbeat:** Build and use session briefing first. It exercises the same queries heartbeat will use (open actions, stale domains, directives) but in a synchronous, inspectable way. Heartbeat adds autonomous execution on top of validated reads.
- **Model routing is infrastructure, not a user feature:** It should be built alongside or just before brain ingestion, since ingestion has the most varied task types (embedding, summarization, classification). Routing can be a simple lookup table — don't over-engineer a classifier.
- **Brain ingestion is independent of heartbeat timing:** Ingestion can be triggered manually (`maia ingest youtube [url]`) before the heartbeat loop is automated. This lets Zack build up memory content without waiting for full automation.

---

## MVP Definition

### Launch With (v1.0 — zBrain Foundation)

The goal is to eliminate the amnesia problem and have the brain actively working overnight. Every item below is blocking that.

- [ ] **libSQL/MuninnDB + pgvector on Railway Volumes** — all other features are blocked without this. Complete daughter's migration branch, retarget to Railway Volumes `brain` schema.
- [ ] **Brain schema** — `memories`, `domains`, `contexts`, `actions`, `reviews`, `reports` tables. Schema is the data contract everything else reads/writes.
- [ ] **Session startup briefing** — fires automatically on `maia chat`. Shows: open actions, stale domains, overnight report if present, active directives. Under 5 seconds.
- [ ] **Action extraction** — post-session async pass. LLM reads transcript, extracts commitments, writes to `brain.actions`. Manual trigger: `maia reflect`.
- [ ] **Standing directives** — per-domain config. Injected into system prompt context when that domain is active. Edit via `maia directive set [domain] "always..."`.
- [ ] **Stale project alerts** — query last-activity timestamp. Surface in session briefing. Threshold configurable (default 7 days).
- [ ] **Gemini model routing** — task-type routing table. Gemini 2.5 Flash for embeddings/summarization/classification. Claude Sonnet for reasoning/briefing/directives. Deterministic, not fallback.
- [ ] **Brain ingestion: YouTube** — `maia ingest youtube [url]`. Transcript → chunk → embed → store with source metadata.
- [ ] **Brain ingestion: web** — `maia ingest web [url]`. Fetch → extract text → chunk → embed → store.
- [ ] **Heartbeat agent** — Windows Task Scheduler + Python script. Scan open actions → pick one task → execute → write report. Runs 2 AM–6 AM window only. HEARTBEAT.md checklist for directives.
- [ ] **iPhone access** — Railway Volumes cloud means the brain is already accessible. Verify claude.ai + MCP or REST endpoint works from iPhone for day-1.

### Add After Validation (v1.1)

Add these once v1.0 is stable and the schema has proven reliable.

- [ ] **Google Calendar integration** — already flagged as v1.1 priority in PROJECT.md. Briefing includes today's schedule. Heartbeat can pre-research meeting topics.
- [ ] **Email/message triage** — Gmail scanning in heartbeat. Flag urgent emails, draft replies. Needs brain foundation to be stable first.
- [ ] **Brain ingestion: documents** — `maia ingest doc [path]`. PDF/text → chunk → embed. Needed for Zack's HVAC sales materials and research docs.
- [ ] **Obsidian sync** — brain as Obsidian vault. Review layer on top of libSQL/MuninnDB brain. Nice-to-have, not blocking.
- [ ] **Heartbeat work queue** — priority-ranked backlog of things for the overnight agent to tackle. Currently heartbeat picks ad-hoc; queue makes it systematic.

### Future Consideration (v2+)

Defer until zBrain v1.0 is stable and the collaboration model with daughter's Promaia is established.

- [ ] **Kanban board UI** — visualization of `brain.actions`. Defer until schema is stable.
- [ ] **React web chat app** — daughter's domain. zBrain's CLI + iPhone access is sufficient.
- [ ] **Desktop Electron app** — daughter's domain. Out of zBrain scope.
- [ ] **Cross-project / team brain** — multi-user memory. Promaia handles this; zBrain stays personal.
- [ ] **Automatic memory forgetting / decay** — weighted relevance over time. Interesting but adds complexity. v1 just keeps everything.

---

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| libSQL/MuninnDB + pgvector migration | HIGH (unblocks everything) | MEDIUM (70% done, retarget Railway Volumes) | P1 |
| Brain schema | HIGH (data contract) | LOW (design + SQL) | P1 |
| Session startup briefing | HIGH (core value: no amnesia) | MEDIUM (query + format + inject) | P1 |
| Action extraction | HIGH (captures commitments automatically) | MEDIUM (async LLM pass over transcript) | P1 |
| Standing directives | MEDIUM (reduces repetition) | LOW (config + prompt injection) | P1 |
| Stale project alerts | MEDIUM (addresses Zack's bounce pattern) | LOW (timestamp query) | P1 |
| Gemini model routing | MEDIUM (cost control, Gemini as specialist) | LOW (routing table in model adapter) | P1 |
| Brain ingestion: YouTube | HIGH (Zack's primary research format) | MEDIUM (transcript API + chunking pipeline) | P1 |
| Heartbeat agent | HIGH (works while sleeping) | HIGH (scheduler + loop + safety guards) | P1 |
| iPhone access verification | HIGH (day-1 requirement) | LOW (Railway Volumes cloud already provides this) | P1 |
| Brain ingestion: web | MEDIUM | MEDIUM | P2 |
| Brain ingestion: documents | MEDIUM (HVAC research) | MEDIUM | P2 |
| Google Calendar integration | MEDIUM | MEDIUM | P2 |
| Overnight work reporting | MEDIUM | LOW | P2 |
| Email/message triage | HIGH (eventually) | HIGH | P2 |
| Heartbeat work queue | MEDIUM | MEDIUM | P2 |
| Obsidian sync | LOW-MEDIUM | MEDIUM | P3 |
| Kanban board UI | MEDIUM | HIGH | P3 |

**Priority key:**
- P1: Must have for v1.0 launch
- P2: v1.1 after validation
- P3: v2+ or daughter's platform

---

## Competitor / Inspiration Feature Analysis

| Feature | OpenClaw Heartbeat | Nate Jones Open Brain | zBrain Approach |
|---------|--------------------|-----------------------|-----------------|
| Proactive agent loop | HEARTBEAT.md checklist, every 30min | Not documented | Windows Task Scheduler + Python, HEARTBEAT.md pattern, overnight-only window |
| Memory storage | File-based MEMORY.md | libSQL/MuninnDB + pgvector | Railway Volumes `brain` schema, pgvector, structured tables |
| Session briefing | Not native (external integration) | Not documented | Built-in: fires on `maia chat` start, pulls from brain schema |
| Model routing | Single model (Claude) | Single model (Claude) | Task-based routing table: Gemini Flash for cheap tasks, Claude for reasoning |
| Ingestion sources | Files, web via skills | Manual capture | YouTube transcript, web fetch, docs, existing Notion/Gmail/Discord (Promaia) |
| Standing directives | HEARTBEAT.md global directives | Not documented | Per-domain directives in `brain.domains`, injected at session start |
| Action extraction | Not automatic | Not documented | Async post-session LLM pass over transcript |
| iPhone access | Via Telegram bot | Via claude.ai | Railway Volumes cloud + claude.ai MCP on iPhone |
| Work reporting | Alert on condition | Not documented | Structured report written to `brain.reports`, surfaced in next briefing |

---

## Promaia Integration Dependencies

These existing Promaia features are directly reused or extended — no rebuild needed.

| zBrain Feature | Promaia Feature Reused | What Changes |
|----------------|------------------------|--------------|
| Gemini model routing | Multi-model LLM adapter (`claude primary, openai/gemini fallback`) | Add `task_type` routing logic. Gemini becomes primary for cheap tasks, not just fallback. |
| Heartbeat agent | Scheduled agent system (early, in `feature/agent-scheduler` branch) | Extend with HEARTBEAT.md loop pattern, work queue, active-hours guard, report writing. |
| Action extraction | Agent orchestration (intent classifier, context serializer) | Reuse context serializer for transcript post-processing. Add extraction prompt. |
| Brain ingestion | Connector plugin architecture (BaseConnector) | YouTube/web/doc ingestion as new BaseConnector subclasses. |
| Session briefing | CLI interface (`maia chat`) | Add briefing hook on chat session start. Pull from brain schema. |
| Stale alerts | Natural language query orchestrator (NL → SQL/vector) | Stale query is straightforward SQL against `brain.domains`. NL orchestrator handles it. |

---

## Sources

- [Task-Based LLM Routing — Portkey.ai](https://portkey.ai/blog/task-based-llm-routing/)
- [OpenClaw HEARTBEAT.md Guide](https://openclawconsult.com/lab/openclaw-heartbeat-md)
- [OpenClaw Heartbeat Official Docs](https://docs.openclaw.ai/gateway/heartbeat)
- [Autonomous AI Dev Teams: Heartbeats, Work Queues — Medium](https://medium.com/@chen.yang_50796/autonomous-ai-dev-teams-heartbeats-work-queues-and-self-managing-agents-0fad942580e9)
- [Self-Evolving AI Agent 59 Overnight Rounds — DEV Community](https://dev.to/terryfyl/i-built-a-self-evolving-ai-agent-that-ran-59-exploration-rounds-overnight-4jcj)
- [Railway Volumes pgvector Docs](https://railway_volumes.com/docs/guides/database/extensions/pgvector)
- [YouTube Transcripts to Knowledge Base — CustomGPT](https://customgpt.ai/ingest-youtube-video-data-ai-knowledge-base/)
- [Gemini 2.5 Flash vs Claude 4.5 Haiku — Appaca](https://www.appaca.ai/resources/llm-comparison/gemini-2.5-flash-vs-claude-4.5-haiku)
- [Proactive AI in 2026 — Alpha Sense](https://www.alpha-sense.com/resources/research-articles/proactive-ai/)
- [AI Action Item Extraction — MyMobileLyfe](https://www.mymobilelyfe.com/artificial-intelligence/turn-meetings-into-action-automating-action-item-extraction-and-task-assignment-with-ai/)
- [Building Smarter AI Agents: AgentCore Long-Term Memory — AWS](https://aws.amazon.com/blogs/machine-learning/building-smarter-ai-agents-agentcore-long-term-memory-deep-dive/)

---

*Feature research for: zBrain — Personal AI Brain / Proactive Agent System (Promaia milestone)*
*Researched: 2026-03-04*
