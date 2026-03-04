# Architecture Research

**Domain:** zBrain — proactive AI memory layer on top of Promaia
**Researched:** 2026-03-04
**Confidence:** HIGH (based on direct code inspection of existing codebase)

## Existing System Overview

Before mapping integration points, this is what Promaia already has on the `zbrain` branch:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           CLI Layer (promaia/cli.py)                     │
│  maia sync | maia chat | maia workspace | maia agent | maia schedule    │
├─────────────────────────────────────────────────────────────────────────┤
│                      Agent Orchestration Layer                           │
│  ┌──────────────────┐  ┌───────────────────┐  ┌─────────────────────┐  │
│  │ agents/scheduler │  │ agent/agent_manager│  │ agent/intent_       │  │
│  │  (interval loop) │  │  (Claude SDK      │  │  classifier.py      │  │
│  │                  │  │   subprocesses)   │  │                     │  │
│  └──────────────────┘  └───────────────────┘  └─────────────────────┘  │
├─────────────────────────────────────────────────────────────────────────┤
│                         AI Layer                                         │
│  ┌─────────────────┐  ┌──────────────────┐  ┌────────────────────────┐ │
│  │ ai/models.py    │  │ ai/nl_orchestrator│  │ ai/prompts.py          │ │
│  │ (model registry)│  │ (NL→SQL/vector)  │  │ (context formatting)   │ │
│  │ Claude primary  │  │ PromaiLLMAdapter  │  │                        │ │
│  │ Gemini fallback │  │                  │  │                        │ │
│  └─────────────────┘  └──────────────────┘  └────────────────────────┘ │
├─────────────────────────────────────────────────────────────────────────┤
│                     Connector Layer                                      │
│  ┌────────────────┐  ┌─────────────────┐  ┌────────────────────────┐   │
│  │ connectors/    │  │ connectors/      │  │ connectors/            │   │
│  │ notion_        │  │ gmail_connector  │  │ discord_connector      │   │
│  │ connector      │  │                  │  │                        │   │
│  └───────┬────────┘  └────────┬─────────┘  └──────────┬─────────── ┘   │
├──────────┴─────────────────────┴─────────────────────────┴──────────────┤
│                     Storage Layer                                        │
│  ┌──────────────────────┐  ┌─────────────────┐  ┌──────────────────┐   │
│  │ storage/hybrid_      │  │ storage/vector_ │  │ storage/supabase_│   │
│  │ storage.py (SQLite)  │  │ db.py (ChromaDB)│  │ query.py (cloud) │   │
│  │ HybridContentRegistry│  │ VectorDBManager │  │                  │   │
│  └──────────────────────┘  └─────────────────┘  └──────────────────┘   │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │ storage/unified_query.py (HybridQueryInterface — SQL view)       │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │  [postgres-sql-changeover branch] storage/postgres_db.py        │    │
│  │  PostgresDB singleton + schema.sql (586 lines, no pgvector yet) │    │
│  └─────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────┘
```

## Target Architecture (zBrain v1.0)

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     CLI Layer (extended)                                 │
│  maia sync | maia chat | maia workspace | maia agent | maia heartbeat   │
│                                          [NEW] maia brain               │
├─────────────────────────────────────────────────────────────────────────┤
│                  Brain Layer [NEW MODULE: brain/]                        │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────────┐  ┌───────────┐  │
│  │ brain/       │  │ brain/       │  │ brain/        │  │ brain/    │  │
│  │ briefing.py  │  │ actions.py   │  │ directives.py │  │ stale.py  │  │
│  │ (startup     │  │ (extract &   │  │ (per-project  │  │ (project  │  │
│  │  briefing)   │  │  store)      │  │  directives)  │  │ alerts)   │  │
│  └──────────────┘  └──────────────┘  └───────────────┘  └───────────┘  │
├─────────────────────────────────────────────────────────────────────────┤
│                     AI Layer (modified)                                  │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │ ai/router.py [NEW] — task-based model selection                  │    │
│  │  "briefing" → Gemini Flash   "complex" → Claude Sonnet           │    │
│  │  "embedding" → text-embed-004  "bulk" → Gemini Flash             │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│  ┌─────────────────┐  ┌──────────────────┐  ┌───────────────────────┐  │
│  │ ai/models.py    │  │ ai/nl_orchestrator│  │ ai/prompts.py         │  │
│  │ [MODIFIED:      │  │ (unchanged)       │  │ [EXTENDED: brain      │  │
│  │  add Google     │  │                   │  │  prompt templates]    │  │
│  │  embed client]  │  │                   │  │                       │  │
│  └─────────────────┘  └───────────────────┘  └───────────────────────┘  │
├─────────────────────────────────────────────────────────────────────────┤
│                     Connector Layer (unchanged)                          │
│  [same as above — connectors/ not modified by zBrain]                   │
├─────────────────────────────────────────────────────────────────────────┤
│                     Storage Layer (replaced + extended)                  │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │  storage/postgres_db.py [MODIFIED: point to Supabase, not local] │   │
│  │  PostgresDB singleton — connection string → Supabase cloud       │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │  storage/vector_db.py [REPLACED: pgvector backend]               │   │
│  │  VectorDBManager — drop ChromaDB, write to Supabase pgvector     │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │  storage/brain_schema.sql [NEW] — brain.* schema                 │   │
│  │  brain.memories | brain.domains | brain.actions | brain.reviews   │   │
│  └──────────────────────────────────────────────────────────────────┘   │
├─────────────────────────────────────────────────────────────────────────┤
│                     Autonomous Layer [NEW: heartbeat/]                   │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │  heartbeat/runner.py — Windows Task Scheduler entry point        │   │
│  │  heartbeat/tasks.py — stale check, action review, brain ingest   │   │
│  └──────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
```

## Integration Analysis: New vs Modified Components

### Feature 1: pgvector Replacing ChromaDB

**Status:** storage/vector_db.py exists and is fully ChromaDB-based. postgres-sql-changeover branch has PostgresDB singleton (psycopg2 + connection pooling) but NO vector extension or embedding columns in schema.sql (confirmed: grep found zero matches for "vector", "embed", "pgvector" in schema.sql).

**What changes:**

| Component | Action | Details |
|-----------|--------|---------|
| `storage/vector_db.py` | REPLACE internals | Keep `VectorDBManager` class interface, swap ChromaDB calls for pgvector SQL. Callers use same `.search()`, `.add_content()`, `.generate_embedding()` API. |
| `storage/schema.sql` (from postgres branch) | EXTEND | Add `CREATE EXTENSION vector` and `embedding vector(768)` columns to content tables. 768 dims = Google text-embedding-004. |
| `ai/models.py` | MODIFY | Add `get_google_embedding_client()` function. Change `_init_embedding_function()` in VectorDBManager to use `google.generativeai` instead of OpenAI. |
| `storage/unified_query.py` | MINOR MODIFY | Replace ChromaDB filter syntax with pgvector SQL operator (`<=>` cosine distance). |
| `storage/hybrid_storage.py` | UNCHANGED | SQLite wrapper stays until Postgres migration completes. |

**Key interface to preserve** (callers expect this contract from `vector_db.py`):
```python
# These signatures must not change — they're called from:
#   storage/unified_query.py, storage/content_search.py
vector_db.search(query_text, filters, n_results, min_similarity) -> List[Dict]
vector_db.add_content(page_id, content_text, metadata) -> bool
vector_db.add_content_with_chunking(page_id, content_text, metadata, chunks) -> bool
vector_db.check_exists(page_id) -> bool
```

**pgvector SQL pattern** (replaces ChromaDB calls):
```python
# In VectorDBManager.search():
embedding = self.generate_embedding(query_text)
rows = db.execute("""
    SELECT page_id, metadata,
           1 - (embedding <=> %s::vector) AS similarity
    FROM public.content_embeddings
    WHERE workspace = %s
    ORDER BY embedding <=> %s::vector
    LIMIT %s
""", [embedding, workspace_filter, embedding, n_results])
```

---

### Feature 2: Brain Schema — New `brain/` Module

**Status:** No brain module exists in Promaia. The postgres branch schema has NO brain tables. This is entirely new work in the `brain.*` Postgres schema (separate from `public.*`).

**Why `brain/` not `storage/`:**
- Brain is a behavioral layer (reasoning, extraction, directives), not a raw storage layer.
- `storage/` is connector output — what was synced from Notion/Gmail/Discord.
- `brain/` is derived intelligence — what zBrain has learned, decided, and remembered.
- Keeping them separate makes the daughter's cherry-pick clean: she can take storage changes without picking up brain logic.

**New module structure:**
```
promaia/brain/
├── __init__.py
├── schema.sql          # brain.* schema DDL (CREATE SCHEMA brain; CREATE TABLE brain.memories ...)
├── briefing.py         # generate_session_briefing(workspace) -> str
├── actions.py          # extract_actions_from_conversation(messages) -> List[Action]
│                       # store_action(action), get_pending_actions(workspace)
├── directives.py       # get_directives(project) -> List[Directive]
│                       # upsert_directive(project, text)
└── stale.py            # get_stale_projects(days_threshold) -> List[Project]
```

**Brain schema tables** (new `brain.*` Postgres schema, separate from `public.*`):
```sql
-- brain.memories: cross-session persistent facts
-- brain.actions: extracted next-steps from conversations
-- brain.directives: standing per-project instructions
-- brain.reviews: heartbeat audit log
-- brain.domains: project/topic taxonomy for routing context
```

**Integration points:**
- `brain/briefing.py` calls `storage/unified_query.py` to fetch recent content
- `brain/briefing.py` calls `brain/actions.py` for pending actions
- `brain/briefing.py` calls `brain/stale.py` for project alerts
- `brain/briefing.py` calls `ai/router.py` (new) to invoke Gemini Flash for synthesis
- `cli.py` startup hook: `maia chat` calls `briefing.generate_session_briefing()` before prompt

---

### Feature 3: Model Routing — New `ai/router.py`

**Status:** `ai/models.py` is currently a model registry (static dicts + helper functions). `ai/nl_orchestrator.py` has its own `PromaiLLMAdapter` that manually tries API keys in order (Anthropic → OpenAI → Gemini). No routing logic exists in any shared location.

**Why `ai/router.py` not modifying `ai/models.py`:**
- `ai/models.py` is data — model ID strings and display names. Keep it pure data.
- Routing is logic — decisions about WHICH model to use for WHICH task.
- `nl_orchestrator.py`'s `PromaiLLMAdapter` is query-specific; don't generalize it.
- A new `router.py` is a clean extension point and easier for the daughter to adopt or ignore.

**New component:**
```python
# ai/router.py
class TaskType(Enum):
    BRIEFING = "briefing"       # Gemini Flash — daily summary, cheap
    EMBEDDING = "embedding"     # Google text-embedding-004 — via google.generativeai
    EXTRACTION = "extraction"   # Gemini Flash — action/directive extraction, high volume
    REASONING = "reasoning"     # Claude Sonnet — complex multi-step analysis
    CHAT = "chat"               # Claude Sonnet — interactive conversation
    HEARTBEAT = "heartbeat"     # Gemini Flash — overnight autonomous work

class ModelRouter:
    def get_client(self, task: TaskType) -> LLMClient: ...
    def route(self, task: TaskType, prompt: str, **kwargs) -> str: ...
```

**Integration points:**
- `brain/briefing.py` uses `router.route(TaskType.BRIEFING, ...)`
- `brain/actions.py` uses `router.route(TaskType.EXTRACTION, ...)`
- `heartbeat/tasks.py` uses `router.route(TaskType.HEARTBEAT, ...)`
- `ai/nl_orchestrator.py` unchanged — it has its own adapter, which is fine
- `agents/executor.py` — optionally extended later to use router; not required for v1.0

**Gemini as first-class client** — add to `ai/router.py`:
```python
import google.generativeai as genai

class GeminiClient:
    def __init__(self):
        genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
        self.flash = genai.GenerativeModel("gemini-2.0-flash-exp")

    def complete(self, prompt: str) -> str:
        response = self.flash.generate_content(prompt)
        return response.text

    def embed(self, text: str) -> List[float]:
        result = genai.embed_content(
            model="models/text-embedding-004",
            content=text,
            task_type="retrieval_document"
        )
        return result["embedding"]  # 768 dims
```

---

### Feature 4: Heartbeat Agent — New `heartbeat/` Module

**Status:** `agents/scheduler.py` exists and runs agents on intervals via asyncio. `agents/executor.py` runs agents with Claude SDK. The heartbeat is a specialized scheduled agent that runs autonomously overnight — it IS the existing agent system, not separate from it.

**Recommended approach:** New `heartbeat/` module that wraps the existing scheduler/executor pattern, plus a Windows Task Scheduler trigger script.

**Why `heartbeat/` not reusing `agents/scheduler.py` directly:**
- `agents/scheduler.py` is a continuous loop daemon (runs forever, Ctrl+C to stop).
- Heartbeat is a single-run triggered job (Windows Task Scheduler fires it, it runs, it exits).
- The trigger mechanism is different enough to warrant a thin wrapper.
- `heartbeat/` can still import from `agents/executor.py` for the actual work.

**New structure:**
```
promaia/heartbeat/
├── __init__.py
├── runner.py     # Entry point: python -m promaia.heartbeat — runs once and exits
└── tasks.py      # Heartbeat-specific tasks: stale_check(), action_review(), brain_ingest()
```

**runner.py pattern:**
```python
# python -m promaia.heartbeat
# Also: python -m promaia.heartbeat --dry-run
async def main():
    brain_context = briefing.get_brain_context()     # Load current state
    tasks = tasks.get_pending_tasks(brain_context)    # What needs doing
    for task in tasks:
        await executor.run_task(task)                 # Reuse existing executor
    await brain.store_review(results)                 # Log what happened
```

**Windows Task Scheduler integration:**
```
Action: python -m promaia.heartbeat
Trigger: Daily 2:00 AM
Condition: Run whether logged on or not
Working Directory: C:\Users\Zachary Turner\dev\promaia
```

**Also add as CLI command** (for `maia heartbeat --run` manual trigger):
```python
# cli/heartbeat_commands.py
# Plugs into existing cli.py pattern (like agent_commands.py, gmail_commands.py)
```

---

## Recommended Project Structure (zbrain additions only)

```
promaia/
├── brain/                      [NEW]
│   ├── __init__.py
│   ├── schema.sql              # brain.* DDL (separate from storage/schema.sql)
│   ├── briefing.py             # Session briefing generator
│   ├── actions.py              # Action extraction + storage
│   ├── directives.py           # Per-project standing instructions
│   └── stale.py                # Project staleness detection
├── heartbeat/                  [NEW]
│   ├── __init__.py             # python -m promaia.heartbeat entry point
│   ├── runner.py               # Single-run orchestrator
│   └── tasks.py                # Heartbeat task definitions
├── ai/
│   ├── models.py               [UNCHANGED — data only]
│   ├── router.py               [NEW — task-based model selection]
│   ├── nl_orchestrator.py      [UNCHANGED]
│   └── prompts.py              [EXTENDED — add brain prompt templates]
├── storage/
│   ├── postgres_db.py          [MODIFIED — change host to Supabase URL]
│   ├── schema.sql              [EXTENDED — add pgvector extension + embedding columns]
│   ├── vector_db.py            [MODIFIED — replace ChromaDB with pgvector SQL]
│   ├── unified_query.py        [MINOR MOD — update vector search filter syntax]
│   ├── hybrid_storage.py       [UNCHANGED — SQLite, deprecated but not removed in v1.0]
│   └── supabase_query.py       [UNCHANGED — existing Supabase client interface]
└── cli/
    ├── heartbeat_commands.py   [NEW — maia heartbeat commands]
    └── brain_commands.py       [NEW — maia brain commands]
```

---

## Recommended Build Order

The four features have dependencies. Build in this order:

### Phase 1: Storage Foundation (pgvector)
**Rationale:** Everything else depends on the database layer. Brain, heartbeat, and embeddings all write to Postgres. Do this first so subsequent phases can test against real storage.

**Steps:**
1. Point `postgres_db.py` to Supabase (env var swap: `POSTGRES_HOST` → `DATABASE_URL`)
2. Run existing `storage/db_init.py` against Supabase — verify all 586-line schema migrates clean
3. Add `CREATE EXTENSION vector` and embedding columns to `storage/schema.sql`
4. Create `storage/brain_schema.sql` with `brain.*` tables
5. Modify `storage/vector_db.py` internals — keep class interface, replace ChromaDB calls
6. Update embedding provider in `ai/models.py` or new `ai/router.py` to use Google embed-004
7. Smoke test: `maia sync` followed by vector search — verify embeddings write to Supabase

**Dependencies this unblocks:** Everything. No other phase can proceed without storage.

---

### Phase 2: Model Router
**Rationale:** Brain features need Gemini Flash. Build the router before brain so brain can use it from day one rather than making direct API calls that later need refactoring.

**Steps:**
1. Create `ai/router.py` with `TaskType` enum and `ModelRouter` class
2. Implement `GeminiClient` wrapper (Flash for generation, text-embedding-004)
3. Implement `ClaudeClient` wrapper (Sonnet for reasoning/chat)
4. Route table: map each `TaskType` to a client
5. Add `GOOGLE_API_KEY` env var check to startup

**Dependencies this unblocks:** Brain features (Phase 3) and Heartbeat (Phase 4).

---

### Phase 3: Brain Module
**Rationale:** Brain is the core value proposition. Once storage and routing exist, build the brain. Heartbeat uses the brain, so brain must exist first.

**Steps:**
1. `brain/actions.py` — extract actions from text, write to `brain.actions` table
2. `brain/directives.py` — read/write per-project directives to `brain.directives`
3. `brain/stale.py` — query `public.unified_content` for project activity gaps
4. `brain/briefing.py` — compose and return briefing string, hook into `maia chat` startup
5. Extend `ai/prompts.py` with brain-specific templates (briefing format, action extraction prompt)
6. Add `cli/brain_commands.py` — `maia brain status`, `maia brain briefing`

**Dependencies this unblocks:** Heartbeat (Phase 4).

---

### Phase 4: Heartbeat Agent
**Rationale:** Last because it depends on brain (for context), storage (for writes), and router (for cheap model calls). Once built, it runs autonomously.

**Steps:**
1. `heartbeat/tasks.py` — define stale project check, action review, brain ingest tasks
2. `heartbeat/runner.py` — single-run entry point that iterates tasks and exits cleanly
3. `cli/heartbeat_commands.py` — `maia heartbeat --run`, `maia heartbeat --status`, `maia heartbeat --dry-run`
4. Windows Task Scheduler setup (documented, not scripted — user configures once)
5. Test: `python -m promaia.heartbeat --dry-run` → verify it runs without writing

---

## Data Flow Changes

### Before (current): Sync → Vector flow
```
maia sync
    → connectors/notion_connector.py → fetch pages
    → storage/hybrid_storage.py → write SQLite
    → storage/vector_db.py → VectorDBManager
        → OpenAI embeddings API (text-embedding-3-small)
        → ChromaDB (local file chroma_db/)
```

### After (zBrain): Sync → Vector flow
```
maia sync
    → connectors/notion_connector.py → fetch pages (UNCHANGED)
    → storage/postgres_db.py → write Supabase public.* tables (REPLACES SQLite)
    → storage/vector_db.py → VectorDBManager (SAME INTERFACE)
        → ai/router.py → GeminiClient.embed()
        → Google text-embedding-004 (768 dims)
        → Supabase pgvector (public.content_embeddings)
```

### New: Chat startup → Brain briefing flow
```
maia chat
    → brain/briefing.py → generate_session_briefing()
        → storage/unified_query.py → recent content (last 48h)
        → brain/actions.py → get_pending_actions()
        → brain/stale.py → get_stale_projects()
        → ai/router.py → Gemini Flash → synthesize briefing text
    → print briefing to terminal
    → enter normal chat loop (UNCHANGED)
```

### New: Conversation → Action extraction flow
```
maia chat (during/after session)
    → brain/actions.py → extract_actions_from_conversation(messages)
        → ai/router.py → Gemini Flash → structured extraction prompt
        → parse JSON response → List[Action]
        → store_action() → INSERT INTO brain.actions
```

### New: Heartbeat overnight flow
```
Windows Task Scheduler → 2:00 AM
    → python -m promaia.heartbeat
        → heartbeat/runner.py → main()
            → brain/briefing.py → get_brain_context()
            → heartbeat/tasks.py → stale_check()
                → brain/stale.py → identify stale projects
                → ai/router.py → Gemini Flash → draft nudge message
                → brain.reviews → log result
            → heartbeat/tasks.py → action_review()
                → brain/actions.py → get_overdue_actions()
                → ai/router.py → Gemini Flash → priority assessment
            → exit(0)
```

---

## Component Boundaries

| Component | Responsibility | Communicates With | Does NOT Touch |
|-----------|---------------|-------------------|----------------|
| `brain/briefing.py` | Compose session context summary | `storage/unified_query`, `brain/actions`, `brain/stale`, `ai/router` | Connectors, ChromaDB, SQLite |
| `brain/actions.py` | Extract and persist action items | `ai/router`, `storage/postgres_db` | Connector layer, chat session |
| `brain/directives.py` | Read/write standing instructions | `storage/postgres_db` | AI layer, connectors |
| `brain/stale.py` | Identify inactive projects | `storage/unified_query` | AI layer directly |
| `ai/router.py` | Route tasks to correct model | `ai/models.py` (for model IDs) | Storage, brain, connectors |
| `storage/vector_db.py` | Embed and search content vectors | `storage/postgres_db`, `ai/router` (embedding) | Brain tables, connectors |
| `heartbeat/runner.py` | Single-run autonomous orchestration | `brain/*`, `ai/router`, `agents/executor` | CLI layer, chat session |
| `storage/postgres_db.py` | Connection pool to Supabase | Environment vars | Business logic |

---

## Integration Points: What Callers Already Exist

These are files that call into the modules being modified. They must not break.

### Callers of `storage/vector_db.py`

| File | Call | Impact of pgvector change |
|------|------|--------------------------|
| `storage/unified_query.py` | `vector_db.search()` | Minor: filter syntax changes (no impact on return type) |
| `storage/content_search.py` | `vector_db.search()` | Same as above |
| `storage/notion_sync.py` | `vector_db.add_content()`, `add_content_with_chunking()` | None if interface preserved |
| `storage/unified_storage.py` | `vector_db.add_content()` | None if interface preserved |

### Callers of `ai/models.py`

| File | Call | Impact of adding router.py |
|------|------|---------------------------|
| `ai/nl_orchestrator.py` | `ANTHROPIC_MODELS`, `GOOGLE_MODELS` dicts | None — router.py adds, doesn't change models.py |
| `agents/executor.py` | `get_current_anthropic_model()` | None |
| Various chat files | `get_model_display_name()` | None |

### Where `maia chat` startup hooks

`promaia/cli.py` imports from `promaia/cli/` submodules. The brain briefing hook goes in `cli/chat_commands.py` or directly in `cli.py` before the chat loop begins. This is an additive change — no existing functionality removed.

---

## Anti-Patterns to Avoid

### Anti-Pattern 1: Putting Brain Logic in Storage

**What people do:** Add `get_briefing()` to `unified_query.py` or a new `BrainStorage` class in `storage/`.
**Why it's wrong:** Storage layer should be dumb data retrieval. Brain is reasoning and synthesis. Mixing them makes the daughter's codebase harder to fork — she gets brain logic when she only wanted the storage migration.
**Do this instead:** `brain/` module calls `storage/` for raw data, does reasoning itself.

### Anti-Pattern 2: Modifying VectorDBManager's Public Interface

**What people do:** Change method signatures in `vector_db.py` because pgvector needs different params.
**Why it's wrong:** Four existing callers depend on `search(query_text, filters, n_results, min_similarity)`. Breaking this signature breaks sync and chat immediately.
**Do this instead:** Keep the same public interface. Translate ChromaDB-style filters to pgvector SQL internally. Add new methods for brain-specific vector operations rather than changing existing ones.

### Anti-Pattern 3: Using Claude for Cheap Brain Tasks

**What people do:** Route all brain processing through Claude Sonnet because "it's better."
**Why it's wrong:** Action extraction, briefing generation, and stale checks run frequently. At Claude API pricing this adds up fast. These tasks don't need Claude's reasoning depth.
**Do this instead:** Use Gemini Flash (already paid for via Google AI Premium) for extraction and synthesis tasks. Reserve Claude for interactive chat and complex multi-step reasoning where the quality difference matters.

### Anti-Pattern 4: Making Heartbeat a Daemon

**What people do:** Build heartbeat as a long-running asyncio service like `agents/scheduler.py`.
**Why it's wrong:** A daemon needs to stay running, handle failures, and restart. On Windows this requires a service wrapper or always-on process. Unnecessary complexity for a personal tool.
**Do this instead:** Single-run script triggered by Windows Task Scheduler. It runs, does its work, writes results to `brain.reviews`, exits. Task Scheduler handles the scheduling. Simpler, more reliable on Windows 11.

### Anti-Pattern 5: Migrating SQLite Before Postgres is Validated

**What people do:** Delete `hybrid_storage.py` and `vector_db.py` (ChromaDB) as soon as postgres_db.py works.
**Why it's wrong:** The postgres branch has never been tested against Supabase. Schema may need adjustments. ChromaDB data migration takes time. Deleting the working fallback too early risks breaking `maia chat` and `maia sync` during development.
**Do this instead:** Keep SQLite + ChromaDB operational until pgvector path proves stable in production. Use an env var toggle (`STORAGE_BACKEND=postgres|sqlite`) during transition. Remove old path only after Supabase has been running reliably for at least one week of normal use.

---

## Scaling Considerations

This is a single-user personal tool. Scaling is not the concern. The concerns are:

| Concern | Mitigation |
|---------|------------|
| Supabase free tier limits (500MB DB, 2GB bandwidth) | Already on Pro ($27.49/mo). 8GB DB, unlimited API calls. Fine. |
| pgvector query performance at thousands of embeddings | Add HNSW index on embedding column. Supabase supports this. |
| Heartbeat job running over its window | Add per-task timeout (30s default). Exit cleanly after total budget. |
| Brain tables growing unbounded | Add `created_at` + periodic archive job. Not day-1 concern. |
| Google embedding API rate limits | text-embedding-004 allows 1500 RPM on free, more on paid. Fine for personal use. |

---

## Sources

- Direct code inspection: `promaia/storage/vector_db.py`, `promaia/ai/models.py`, `promaia/storage/hybrid_storage.py`, `promaia/agent/agent_manager.py`, `promaia/agents/scheduler.py`, `promaia/agents/executor.py`, `promaia/mcp/client.py`, `promaia/connectors/base.py`
- postgres-sql-changeover branch: `promaia/storage/postgres_db.py`, `promaia/storage/schema.sql` (586 lines inspected, confirmed no pgvector or brain tables)
- PROJECT.md milestone context (zbrain constraints, features, decisions)
- Supabase pgvector documentation (HIGH confidence — standard extension, well-documented)
- Google generativeai Python SDK — `genai.embed_content()` with `text-embedding-004` (HIGH confidence)

---
*Architecture research for: zBrain v1.0 integration into Promaia*
*Researched: 2026-03-04*
*Confidence: HIGH — based on direct code inspection of 400+ lines across 10 source files*
