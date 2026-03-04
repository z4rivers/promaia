# zBrain + Promaia Merge Design

**Date:** 2026-03-04
**Author:** Zack Turner (z4rivers)
**Branch:** `zbrain` (off `feature/agent-scheduler`)
**Status:** DESIGN — awaiting approval

---

## What This Is

zBrain is Zack's personal AI operating system — proactive agents that manage his projects, remember everything, and work autonomously overnight. Instead of building from scratch, zBrain builds on top of Promaia (his daughter's content management + agent platform), contributing features back upstream.

**Collaboration model:** Branch & contribute back. Zack builds on a `zbrain` branch. His daughter cherry-picks features she wants for the main platform.

---

## Four Features to Add

### Feature 1: Supabase/Postgres Backend

**What exists:** Promaia's `postgres-sql-changeover` branch has a 586-line schema, `PostgresDB` singleton with connection pooling, and migrations for all existing tables (gmail_content, notion_journal, etc.). Currently targets a local Postgres at `192.168.0.69`.

**What zBrain adds:**
- Merge the postgres branch into `zbrain` as the foundation
- Swap connection config from local Postgres to Supabase (dulqttfidcjeujyieuqw)
- Add pgvector extension + `halfvec(768)` columns with HNSW indexes (replacing ChromaDB)
- Add `brain` schema tables (see Feature 2) alongside existing Promaia tables
- Google `text-embedding-004` for embeddings (covered by existing Google AI Premium)

**Connection strategy:**
```
# .env (zBrain)
POSTGRES_HOST=db.dulqttfidcjeujyieuqw.supabase.co
POSTGRES_PORT=5432
POSTGRES_DATABASE=postgres
POSTGRES_USER=postgres
POSTGRES_PASSWORD=<supabase-db-password>
POSTGRES_SCHEMA=brain    # zBrain tables live here
```

Promaia's existing tables (`content_items`, `gmail_content`, `notion_journal`, etc.) go in the `public` schema. zBrain's new tables go in a `brain` schema. Same database, separate concerns.

**pgvector replaces ChromaDB:**
- `vector_db.py` gets a Postgres adapter: `INSERT INTO brain.memories ... RETURNING id` with embedding column
- Semantic search becomes a SQL query: `ORDER BY embedding <=> $1 LIMIT 10`
- No more local ChromaDB folder — everything cloud-native, accessible from iPhone

**Contribute-back value:** HIGH. She wants Postgres too. The pgvector integration and Supabase connection pattern benefit the main platform.

---

### Feature 2: Proactive Brain Layer

**What exists:** Promaia is reactive — user initiates sync, chat, queries. Nothing happens without a command.

**What zBrain adds:** A new layer that makes the system proactive.

**New tables (brain schema):**

```sql
-- What Zack has been thinking about, from all sources
brain.memories (
  id, content, summary, domain, tags, entities,
  embedding halfvec(768), source, source_id,
  created_at, updated_at
)

-- Life categories and projects
brain.domains (
  id, name, description, is_project, parent_domain,
  created_at
)

-- Current state + standing directive per project
brain.contexts (
  id, domain_id, directive, current_state, last_updated,
  priority, stale_threshold_days
)

-- Extracted next actions with status
brain.actions (
  id, memory_id, domain_id, description,
  status (pending/done/stale), extracted_at, completed_at
)

-- Weekly synthesis records
brain.reviews (
  id, period_start, period_end, summary,
  projects_touched, actions_completed, created_at
)
```

**New MCP tools (exposed via system instructions):**

| Tool | Behavior | Proactive? |
|------|----------|-----------|
| `briefing` | Returns stalled projects, pending actions, recent activity | YES — called at session start |
| `capture` | Store thought, auto-classify domain, auto-extract actions | YES — detects actionable items |
| `search` | Semantic search across all memories | On demand |
| `recall` | Get memories by domain or time range | On demand |
| `context` | Get current state + directive for a project | On demand |
| `update_context` | Update project state or directive | On demand |
| `actions` | List pending actions, mark done, flag stale | YES — feeds briefings |

**How it works with Promaia's existing system:**

Promaia already syncs Notion, Gmail, Discord into its storage. The brain layer sits on top:
1. When Promaia syncs content, key items also get `capture`d into `brain.memories`
2. When Zack chats, action extraction runs on his messages
3. Session briefings call Promaia's existing query system PLUS brain tables
4. Standing directives inform how Promaia's agents work on each project

**System instructions (added to CLAUDE.md):**
```
At session start, call `briefing` automatically.
When user shares a thought, call `capture`.
When working on a project, call `context` first.
When user says "I need to..." — extract the action.
```

**Contribute-back value:** HIGH. This is opt-in — if you don't set up brain tables, nothing changes. But anyone who wants proactive AI gets it.

---

### Feature 3: Heartbeat Agent

**What exists:** Promaia has `agents/scheduler.py` and `cli/scheduled_agent_commands.py` — agent definitions stored in Notion, multi-step execution. Early but foundational.

**What zBrain adds:** An autonomous overnight loop.

**Architecture:**
```
Windows Task Scheduler
  → runs every 4 hours (configurable)
  → launches: claude-code --non-interactive --script heartbeat.py

heartbeat.py:
  1. Call `briefing` to get system state
  2. Identify most stalled project (longest since last activity)
  3. Read that project's directive from `brain.contexts`
  4. Do autonomous work:
     - Research (web search, YouTube analysis via Gemini)
     - Drafting (documents, emails, code)
     - Code commits (on feature branches only)
  5. Log results to `brain.memories` with source="heartbeat"
  6. Update `brain.contexts` with new state
  7. Generate summary for morning briefing
```

**Safety guardrails:**
- Heartbeat only works on feature branches, never main
- No sending emails/messages without explicit directive
- Logs everything — Zack reviews in morning briefing
- Max runtime per session (30 min default)
- Budget cap on API calls per heartbeat cycle

**Quick scan + deep work pattern:**
- Quick scan: Check all projects (2 min) — any blockers, any stale items, any pending actions past due
- Deep work: Pick the most stalled project, spend remaining time on it
- Report: Summary of scan + deep work results

**Contribute-back value:** MEDIUM. The pattern is useful, but Task Scheduler is Windows-specific. The heartbeat logic itself (scan → pick → work → report) is platform-agnostic and valuable upstream.

---

### Feature 4: Gemini as First-Class Model

**What exists:** Promaia's `ai/models.py` has a multi-model LLM adapter with Claude primary, OpenAI and Gemini as fallbacks. Gemini is only used when Claude and OpenAI fail.

**What zBrain adds:** Intelligent model routing — each model handles what it's best at.

**Routing table:**

| Task | Model | Why |
|------|-------|-----|
| Complex reasoning, architecture | Claude Opus | Best at judgment calls |
| Code generation, drafting | Claude Sonnet | Good balance of speed/quality |
| Classification, action extraction | Claude Haiku or Gemini Flash | Cheap, fast, good enough |
| Deep research with citations | Gemini (via `gemini-deep-research` MCP) | Google Search grounding |
| YouTube video analysis | Gemini (via `gemini-youtube` MCP) | Native video understanding |
| Image generation | Gemini (via `gemini-generate-image` MCP) | Nano banana |
| Document/URL analysis | Gemini (via `gemini-analyze-document` MCP) | Multimodal input |
| Web search | Gemini (via `gemini-search` MCP) | Google Search integration |

**Implementation:**

Zack already has Gemini connected as MCP tools in his Claude Code setup. The integration is:

1. **Brain ingestion pipeline**: When Gemini analyzes a YouTube video or document, the results get `capture`d into `brain.memories` automatically. Every research session makes the brain smarter.

2. **Model router in `ai/models.py`**: Add a `route_to_model(task_type)` function that picks the right model based on task classification. Not a fallback chain — an intentional routing decision.

3. **Cost optimization**: Classification and action extraction (high volume, low complexity) go through Haiku/Flash. Complex reasoning (low volume, high value) goes through Opus. Middle-ground work goes through Sonnet.

**Contribute-back value:** HIGH. Reduces API costs for everyone. The routing pattern is model-agnostic — she could route differently for her setup.

---

## Build Order

```
Phase 1: Postgres Foundation (Week 1)
├── Merge postgres-sql-changeover branch into zbrain
├── Configure Supabase connection
├── Add pgvector extension + embedding columns
├── Migrate vector_db.py from ChromaDB to pgvector
├── Verify all existing Promaia features still work
│
Phase 2: Brain Schema + MCP Tools (Week 1-2)
├── Create brain schema tables (memories, domains, contexts, actions, reviews)
├── Build brain MCP tools (briefing, capture, search, recall, context, actions)
├── Add system instructions for proactive behavior
├── Seed initial domains and directives for each project
├── Test: start session → auto-briefing works
│
Phase 3: Gemini Routing (Week 2)
├── Add model router to ai/models.py
├── Wire Gemini MCP tools into brain ingestion pipeline
├── YouTube analysis → brain.memories
├── Deep research → brain.memories
├── Test: research a topic → brain captures findings automatically
│
Phase 4: Heartbeat Agent (Week 3)
├── Build heartbeat.py script
├── Windows Task Scheduler setup
├── Safety guardrails (branch-only, logging, budget cap)
├── Morning summary generation
├── Test: run heartbeat manually → see results in next briefing
│
Phase 5: iPhone Access (Week 3)
├── ngrok or VPS setup for brain MCP endpoint
├── Add brain MCP to claude.ai custom connectors
├── Test: capture a thought from iPhone → shows in PC session
```

**Dependencies:** Phase 1 → Phase 2 → Phase 3 (can parallel with 2) → Phase 4 (needs 2) → Phase 5 (needs 2)

---

## What Zack Experiences After This

**Morning (iPhone, driving to work):**
> "Good morning Zack. Here's your briefing:
> - Heatpup: stalled 9 days. Directive says 'working public calculator.' The heartbeat agent researched Portland energy rates overnight — findings saved.
> - HVAC Brand: 2 pending actions from yesterday — follow up with customer on 35th, draft Google Business post.
> - PURRfoot: last touched 3 weeks ago. No blockers, just needs attention.
> - Overnight work: researched competitor heat pump calculators, drafted comparison notes."

**During the day (voice on iPhone):**
> Zack: "I just realized the calculator should show monthly savings not just annual"
> Claude: *captures to brain, extracts action, classifies under heatpup, updates context*

**Evening (PC, Claude Code):**
> Claude: "You mentioned monthly savings this morning. I can update the calculator component now. The heartbeat research from last night found that Bonneville Power offers a rate API we could use. Want me to start?"

---

## Costs

| Item | Cost | Notes |
|------|------|-------|
| Supabase Pro | $27.49/mo (existing) | Brain schema adds ~$0.10-0.30/mo |
| Claude Max | $199/mo (existing) | Heartbeat + all model routing included |
| Google AI Premium | $125/mo (existing) | Gemini API + embeddings included |
| Obsidian Sync | $4/mo (new) | Human review layer |
| ngrok (free tier) | $0 | Or $5/mo VPS if always-on needed |
| **New cost** | **$4/mo** | Everything else on existing subscriptions |

---

## Git Strategy

1. Create `zbrain` branch off current `feature/agent-scheduler`
2. Merge `postgres-sql-changeover` into `zbrain` early (Phase 1)
3. Clean commits per feature — easy for daughter to review
4. PR individual features back when stable
5. Rebase/merge from her main periodically to stay in sync

---

## Open Questions (Resolved from Previous Session)

| Question | Answer |
|----------|--------|
| iPhone capture day-1? | Yes |
| Heartbeat behavior? | Quick scan all projects, deep work on most stalled |
| Local vs VPS? | Start local (PC + ngrok), upgrade to VPS if needed |
| Which memory MCP? | Build on Promaia (not Open Brain or mcp-mem0) |
| Proactive how aggressive? | TBD — start moderate, tune based on experience |
| Standing directives per project? | TBD — draft with Zack during Phase 2 seeding |
