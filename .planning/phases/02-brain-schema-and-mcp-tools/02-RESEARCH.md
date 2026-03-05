# Phase 2: Brain Schema and MCP Tools - Research

**Researched:** 2026-03-04
**Domain:** PostgreSQL brain schema + MCP server (Python/FastMCP) + deterministic engine
**Confidence:** HIGH

---

## Summary

Phase 2 builds the proactive brain layer on top of the Postgres foundation from Phase 1. The work breaks into three tightly-coupled areas: (1) brain schema tables in Postgres, (2) an MCP server that exposes brain tools to Claude, and (3) a deterministic engine (`brain/engine.py`) with ~8 pure functions for mode detection, guardrails, and context management.

The MCP server pattern is already established in this codebase. The `promaia/mcp/` module has two working stdio servers (gmail_tools_server.py, calendar_tools_server.py) that use the official `mcp` Python SDK with `from mcp.server import Server` and `from mcp.server.stdio import stdio_server`. However, **FastMCP** has emerged as the de-facto standard for new MCP servers in 2025-2026 (70% of all MCP servers, incorporated into official SDK). Either approach works — the codebase already uses the low-level SDK pattern so either can be used. FastMCP is simpler for new code.

The `brain/engine.py` functions must be deterministic (no LLM calls inside them). Action extraction — detecting "I need to..." patterns — should use Gemini Flash via the `instructor` library for structured Pydantic output, keeping it cheap and typed. The existing `VectorDBManager` embedding pattern (google-genai SDK, `gemini-embedding-001`, 768 dims) is the model for all embedding generation in `brain.memories`.

The MCP server registers with Claude Code via `claude mcp add --transport stdio brain-server -- python -m promaia.brain.mcp_server` and lives in `.mcp.json` (project scope) for sharing.

**Primary recommendation:** New brain MCP server using low-level `mcp` SDK (matches existing codebase pattern). Brain schema as a separate SQL migration file applied via `db_init.py`. Action extraction via `instructor` + Gemini Flash. CLAUDE.md updated with briefing/capture/context system instructions.

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| BRAIN-01 | Brain schema stores memories with embeddings (semantic search) | `brain.memories` table with `vector(768)` + HNSW index; same pattern as `content_embeddings` in schema.sql; `VectorDBManager` pattern for embed generation |
| BRAIN-02 | Domains represent life categories and projects | `brain.domains` table (simple, no embeddings needed); seed with Zack's known projects during plan |
| BRAIN-03 | Standing directives per project define direction, not task lists | `brain.contexts` table with `directive TEXT`, `current_state TEXT`, `stale_threshold_days INT`; queryable by `domain_id` |
| BRAIN-04 | Actions auto-extracted from conversations with status tracking | `brain.actions` table; extraction via `instructor` + Gemini Flash; status enum `('pending','done','stale')` |
| BRAIN-05 | Session briefing runs automatically on startup | `briefing` MCP tool called by system instructions in CLAUDE.md; queries `brain.contexts`, `brain.actions`, `brain.events` |
| BRAIN-06 | Stale alerts flag projects with no activity past threshold | Staleness = `NOW() - brain.contexts.last_updated > stale_threshold_days`; surfaced in `briefing` tool output |
</phase_requirements>

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `mcp` | `>=1.26.0` (already in requirements.txt) | MCP server protocol (Server, stdio_server, Tool, TextContent) | Official SDK, already used in this codebase |
| `psycopg2-binary` | `>=2.9.9` (already in requirements.txt) | Postgres queries for brain schema | Phase 1 established this as DB driver |
| `pgvector` | `>=0.4.2` (already in requirements.txt) | `register_vector()` for brain.memories embedding queries | Phase 1 established; same HNSW pattern |
| `google-genai` | `>=1.65.0` (already in requirements.txt) | Embeddings for brain.memories via `gemini-embedding-001` | Phase 1 established |
| `instructor` | latest | Structured Pydantic output from LLM for action extraction | Standard library for typed LLM output; Gemini Flash support confirmed |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `pydantic` | `>=2.11.3` (already in requirements.txt) | Define `ActionExtraction` model for `instructor` | Action extraction schema definition |
| `anthropic` | `>=0.64.0` (already in requirements.txt) | Optional: use Claude Haiku for action extraction if Gemini latency is an issue | Fallback for extraction if needed |
| `fastmcp` | latest | Alternative MCP server framework (simpler decorator pattern) | If the team wants to start fresh; NOT needed since existing pattern works |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Low-level `mcp` SDK | `fastmcp` | FastMCP is cleaner (`@mcp.tool` decorator), but low-level SDK matches existing codebase style and is already installed |
| `instructor` for action extraction | Raw Gemini Flash with JSON schema | `instructor` adds automatic retry + Pydantic validation; worth the extra dep |
| Gemini Flash for action extraction | Regex/NLP heuristics | LLM approach is far more accurate for "I need to...", "don't forget", "we should..." patterns |

**Installation (new deps only):**
```bash
pip install instructor
```

---

## Architecture Patterns

### Recommended Project Structure

```
promaia/
├── brain/
│   ├── __init__.py
│   ├── engine.py          # 8 deterministic functions (mode detect, guardrails, etc.)
│   ├── mcp_server.py      # MCP server exposing briefing, capture, search, etc.
│   └── schema.sql         # Brain schema SQL (CREATE TABLE IF NOT EXISTS brain.*)
└── storage/
    └── schema.sql         # Existing public schema (unchanged)

.planning/phases/02-brain-schema-and-mcp-tools/
CLAUDE.md                  # System instructions added here (briefing on startup, capture behavior)
.mcp.json                  # Project-scoped MCP server registration for brain-server
```

### Pattern 1: Brain Schema in Separate SQL File

**What:** Create `promaia/brain/schema.sql` with all `CREATE TABLE IF NOT EXISTS brain.*` DDL. Apply it via a new function in `db_init.py`.

**When to use:** Keeps brain schema isolated from the public Promaia schema. Easy for daughter to review and cherry-pick.

**Example:**
```sql
-- promaia/brain/schema.sql
CREATE SCHEMA IF NOT EXISTS brain;

CREATE TABLE IF NOT EXISTS brain.memories (
    id SERIAL PRIMARY KEY,
    content TEXT NOT NULL,
    summary TEXT,
    domain TEXT,
    tags TEXT[] DEFAULT '{}',
    entities JSONB DEFAULT '{}',
    embedding vector(768),
    source TEXT,
    source_id TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- HNSW index (same pattern as content_embeddings in public schema)
CREATE INDEX IF NOT EXISTS idx_brain_memories_vector
    ON brain.memories USING hnsw (embedding vector_cosine_ops);

-- GIN index for hybrid search (same pattern as Phase 1)
CREATE INDEX IF NOT EXISTS idx_brain_memories_tags
    ON brain.memories USING gin (tags);

CREATE TABLE IF NOT EXISTS brain.domains (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    description TEXT,
    is_project BOOLEAN DEFAULT TRUE,
    parent_domain INTEGER REFERENCES brain.domains(id),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS brain.contexts (
    id SERIAL PRIMARY KEY,
    domain_id INTEGER REFERENCES brain.domains(id) NOT NULL,
    directive TEXT,
    current_state TEXT,
    last_updated TIMESTAMPTZ DEFAULT NOW(),
    priority INTEGER DEFAULT 5,
    stale_threshold_days INTEGER DEFAULT 7
);

CREATE TABLE IF NOT EXISTS brain.actions (
    id SERIAL PRIMARY KEY,
    memory_id INTEGER REFERENCES brain.memories(id),
    domain_id INTEGER REFERENCES brain.domains(id),
    description TEXT NOT NULL,
    status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'done', 'stale')),
    extracted_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS brain.reviews (
    id SERIAL PRIMARY KEY,
    period_start TIMESTAMPTZ,
    period_end TIMESTAMPTZ,
    summary TEXT,
    projects_touched JSONB DEFAULT '[]',
    actions_completed INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS brain.events (
    id SERIAL PRIMARY KEY,
    type TEXT NOT NULL,
    payload JSONB DEFAULT '{}',
    source TEXT,
    session_id TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_brain_events_type ON brain.events(type);
CREATE INDEX IF NOT EXISTS idx_brain_events_source ON brain.events(source);
CREATE INDEX IF NOT EXISTS idx_brain_events_created ON brain.events(created_at DESC);

CREATE TABLE IF NOT EXISTS brain.modes (
    id SERIAL PRIMARY KEY,
    session_id TEXT NOT NULL,
    mode TEXT NOT NULL CHECK (mode IN ('working', 'planning', 'capturing', 'reviewing')),
    entered_at TIMESTAMPTZ DEFAULT NOW(),
    context_snapshot JSONB DEFAULT '{}',
    triggered_by TEXT
);
```

### Pattern 2: MCP Server Using Existing Low-Level SDK

**What:** Mirror the pattern from `promaia/mcp/gmail_tools_server.py`. Use `Server`, `@server.list_tools()`, `@server.call_tool()`, `stdio_server`.

**When to use:** Consistent with existing codebase. No new framework to install.

**Example (brain MCP server skeleton):**
```python
# promaia/brain/mcp_server.py
import asyncio
import logging
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent
from promaia.storage.postgres_db import get_postgres_db

logger = logging.getLogger(__name__)
server = Server("promaia-brain")

@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="briefing",
            description="Get session briefing: stalled projects, pending actions, recent activity. Call this at session start.",
            inputSchema={"type": "object", "properties": {}, "required": []}
        ),
        Tool(
            name="capture",
            description="Store a thought, auto-classify domain, extract actions. Call when user shares something worth remembering.",
            inputSchema={
                "type": "object",
                "properties": {
                    "content": {"type": "string", "description": "The thought or information to capture"},
                    "domain": {"type": "string", "description": "Project/domain name (optional, auto-detected if omitted)"}
                },
                "required": ["content"]
            }
        ),
        Tool(
            name="search",
            description="Semantic search across all brain memories.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "limit": {"type": "integer", "default": 10}
                },
                "required": ["query"]
            }
        ),
        # ... recall, context, update_context, actions tools
    ]

@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    if name == "briefing":
        return await _handle_briefing()
    elif name == "capture":
        return await _handle_capture(arguments)
    elif name == "search":
        return await _handle_search(arguments)
    # ... etc.

async def main():
    logging.basicConfig(level=logging.INFO, stream=__import__('sys').stderr)
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())

if __name__ == "__main__":
    asyncio.run(main())
```

### Pattern 3: Action Extraction with `instructor` + Gemini Flash

**What:** Use `instructor` to get structured Pydantic output from Gemini Flash for extracting actionable items from captured text.

**Why not regex:** Patterns like "I need to...", "don't forget", "we should...", "make sure to..." are highly variable. LLM extraction is far more accurate.

**Example:**
```python
# In brain/engine.py or brain/mcp_server.py capture handler
import instructor
from google import genai
from pydantic import BaseModel
from typing import List, Optional

class ExtractedAction(BaseModel):
    description: str
    domain: Optional[str] = None
    urgency: str = "normal"  # urgent | normal | someday

class ActionExtractionResult(BaseModel):
    actions: List[ExtractedAction]
    has_actions: bool

def extract_actions(text: str) -> ActionExtractionResult:
    """Extract actions from text using Gemini Flash via instructor."""
    client = instructor.from_provider("google/gemini-flash")  # or wrap genai client

    result = client.chat.completions.create(
        response_model=ActionExtractionResult,
        messages=[{
            "role": "user",
            "content": f"""Extract any actionable items from this text.
Look for: "I need to...", "don't forget...", "we should...", "make sure to...", explicit commitments.
If no actions found, return has_actions=False with empty list.

Text: {text}"""
        }]
    )
    return result
```

### Pattern 4: CLAUDE.md System Instructions

**What:** The proactive behaviors (briefing on startup, capture on thought-sharing, context before project work) live in CLAUDE.md as system instructions, not in code.

**Why:** Design decision from the workflow doc — Claude's personality layer is instructions, not hard-wired logic. Changing behavior doesn't require code deploys.

**Example CLAUDE.md additions:**
```markdown
## zBrain: Proactive Brain Instructions

At the start of every session, call `mcp__brain__briefing` automatically before responding.
Present the briefing concisely — what changed, what's pending, suggested flow.

When the user shares a thought, observation, or decision worth remembering,
call `mcp__brain__capture` with the content and inferred domain.

When starting work on a project, call `mcp__brain__context` first to get
the current state and standing directive.

When the user says "I need to...", "don't forget...", or makes a commitment,
call `mcp__brain__capture` — the system will auto-extract the action.

Keep confirmations brief: "Captured." or "Captured. Updated Heatpup context." — not a paragraph.
```

### Pattern 5: MCP Server Registration in .mcp.json

**What:** Project-scoped `.mcp.json` at repo root so the brain server is available to anyone using the zbrain branch.

```json
{
  "mcpServers": {
    "brain": {
      "type": "stdio",
      "command": "python",
      "args": ["-m", "promaia.brain.mcp_server"],
      "env": {
        "DATABASE_URL": "${DATABASE_URL}",
        "GOOGLE_API_KEY": "${GOOGLE_API_KEY}"
      }
    }
  }
}
```

Registration command for Zack's machine:
```bash
# Project-scoped (committed to repo, available to everyone on zbrain)
claude mcp add --scope project --transport stdio brain -- python -m promaia.brain.mcp_server
```

### Pattern 6: engine.py Pure Functions

**What:** `brain/engine.py` contains ~8 deterministic functions. No LLM calls inside these functions. Pure Python + SQL.

**Key function signatures (from workflow design doc):**
```python
def detect_mode(message: str) -> dict:
    """Returns {mode: str, confidence: float}. Uses keyword heuristics, not LLM."""
    # working | planning | capturing | reviewing

def confirm_mode(detected: str, current: str) -> str:
    """Returns a confirmation string to show user on mode change."""

def enforce_guardrails(action: str, source: str) -> bool:
    """Blocks: main branch commits, external comms, deletes. Returns True if allowed."""

def track_time(session_id: str, domain_id: int) -> float:
    """Returns duration in seconds for current task (reads brain.events)."""

def budget_check(cycle_id: str) -> dict:
    """Returns {remaining: float, exceeded: bool} for heartbeat API budget."""

def save_context(session_id: str, domain_id: int) -> dict:
    """Writes snapshot to brain.contexts. Returns snapshot."""

def restore_context(session_id: str) -> dict:
    """Reads most recent context from brain.contexts."""

def suggest_next(domains: list, energy: str = None) -> dict:
    """Returns best next domain/action based on staleness, priority, time estimates."""
```

**Key insight:** `detect_mode()` uses keyword/phrase heuristics, NOT a LLM call. The design doc says "Gemini review noted: start with Haiku/Flash classifier — revisit if latency is issue." For Phase 2, simple heuristics are fine. Mode classification accuracy is not critical — "infer + confirm" pattern means Claude checks with the user.

### Anti-Patterns to Avoid

- **LLM calls inside engine.py:** These functions must be deterministic. No `genai.Client` in engine.py.
- **Embedding every capture inline:** Generate embedding async or queue it. Blocking the capture tool on an embedding API call adds 200-500ms latency.
- **Storing embeddings for non-memory tables:** Only `brain.memories` needs embeddings. `domains`, `contexts`, `actions`, `events`, `modes` are SQL-only.
- **Single monolithic MCP server with 15 tools:** Keep tools focused. 7 tools maximum. If a tool needs >5 parameters, split it.
- **psycopg2 not registered for pgvector:** Must call `register_vector(conn)` before any `vector(768)` column operations. Pattern established in `VectorDBManager._register_vector_on_connection()`.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Typed LLM output for action extraction | Custom JSON parsing + retry logic | `instructor` library | Handles retries, validation, schema generation automatically |
| MCP protocol implementation | Custom JSON-RPC handler | `mcp` SDK | Protocol already handles message framing, capability negotiation |
| Embedding generation | New embedding wrapper | Reuse `VectorDBManager.generate_embedding()` or its pattern directly | Same google-genai Client pattern, same model |
| Staleness calculation | Custom timer | SQL: `NOW() - last_updated > stale_threshold_days * INTERVAL '1 day'` | Postgres handles it; no application-level timer needed |
| Mode detection ML | Train a classifier | Keyword heuristics in engine.py | "infer + confirm" UX pattern — accuracy is good enough; user corrects wrong guesses |

**Key insight:** The existing `PostgresDB.fetch_all()`, `execute()`, and `insert_returning()` methods cover all query needs. No ORM, no new query builder.

---

## Common Pitfalls

### Pitfall 1: `mcp` Package Not Installed in Runtime Python
**What goes wrong:** `ModuleNotFoundError: No module named 'mcp'` when Claude Code tries to start the brain server. (This happened in testing — the system Python 3.14 doesn't have `mcp` installed.)
**Why it happens:** `mcp>=1.26.0` is in `requirements.txt` but may not be installed in the active Python environment.
**How to avoid:** Verify with `python -m promaia.brain.mcp_server --help` before registering. Use `pip install -r requirements.txt` to ensure deps.
**Warning signs:** MCP server shows "Connection closed" in Claude Code's `/mcp` output.

### Pitfall 2: pgvector Not Registered Before Brain Query
**What goes wrong:** `psycopg2.ProgrammingError: can't adapt type 'numpy.ndarray'` or adapter errors when inserting/querying `brain.memories.embedding`.
**Why it happens:** pgvector type must be registered on each connection via `register_vector(conn)` before use.
**How to avoid:** Call `register_vector(conn)` inside every connection context manager that touches embedding columns. Copy the pattern from `VectorDBManager._register_vector_on_connection()`.
**Warning signs:** Errors appear specifically on `brain.memories` queries, not on other tables.

### Pitfall 3: Brain Schema Not in `brain` Postgres Schema
**What goes wrong:** Tables created in `public` schema, conflicting with Promaia's existing tables.
**Why it happens:** Default schema is `public` unless explicitly specified.
**How to avoid:** All brain DDL uses `CREATE TABLE IF NOT EXISTS brain.*`. Include `CREATE SCHEMA IF NOT EXISTS brain;` as first statement in brain/schema.sql. Apply with `SET search_path TO brain, public;` or explicit schema qualification in all queries.

### Pitfall 4: CLAUDE.md Briefing Called Twice
**What goes wrong:** Session briefing fires on every message, not just session start.
**Why it happens:** System instructions that say "call briefing" without a qualifier get re-evaluated on every turn.
**How to avoid:** System instruction must be explicit: "At the START of every session (first message only)." The MCP tool itself can check `brain.events` for an existing briefing in the current session and return early if already called.

### Pitfall 5: Capture Tool Blocking on Embedding
**What goes wrong:** Every capture call takes 500ms+ because embedding generation blocks the response.
**Why it happens:** Inline synchronous embedding in the capture handler.
**How to avoid:** Two options: (a) generate embedding asynchronously after returning acknowledgment, or (b) insert the memory without embedding first, then update embedding in a background task. For Phase 2 simplicity, option (b) (insert then update) is sufficient.

### Pitfall 6: instructor Library `from_provider` API
**What goes wrong:** `instructor.from_provider("google/gemini-flash")` may fail if the provider string format is wrong.
**Why it happens:** `instructor` wraps different SDKs with different initialization patterns.
**How to avoid:** For google-genai SDK specifically, use `instructor.from_genai(genai.Client(...))` rather than the `from_provider` string API. Verify against official instructor docs.
**Warning signs:** `ValueError: unknown provider` or import errors.

---

## Code Examples

### Briefing Tool Handler (core logic)

```python
# Source: design from 2026-03-04-zbrain-workflow-design.md + postgres_db.py patterns
async def _handle_briefing() -> list[TextContent]:
    db = get_postgres_db()

    # Stale projects (last_updated > threshold)
    stale = db.fetch_all("""
        SELECT d.name, c.last_updated, c.stale_threshold_days,
               EXTRACT(EPOCH FROM (NOW() - c.last_updated))/86400 AS days_stale
        FROM brain.contexts c
        JOIN brain.domains d ON d.id = c.domain_id
        WHERE NOW() - c.last_updated > c.stale_threshold_days * INTERVAL '1 day'
        ORDER BY days_stale DESC
    """)

    # Pending actions
    pending_actions = db.fetch_all("""
        SELECT a.description, d.name as domain
        FROM brain.actions a
        LEFT JOIN brain.domains d ON d.id = a.domain_id
        WHERE a.status = 'pending'
        ORDER BY a.extracted_at DESC
        LIMIT 10
    """)

    # Recent heartbeat activity
    recent_heartbeat = db.fetch_all("""
        SELECT payload->>'summary' as summary, created_at
        FROM brain.events
        WHERE source = 'heartbeat' AND created_at > NOW() - INTERVAL '24 hours'
        ORDER BY created_at DESC
        LIMIT 5
    """)

    # Assemble briefing text
    parts = []
    if stale:
        parts.append(f"Stale projects: {', '.join(p['name'] for p in stale)}")
    if pending_actions:
        parts.append(f"Pending actions: {len(pending_actions)} items")
    if recent_heartbeat:
        parts.append("Heartbeat ran overnight")

    briefing_text = "\n".join(parts) if parts else "All clear — nothing stale, no pending actions."

    # Log event
    db.execute(
        "INSERT INTO brain.events (type, payload, source) VALUES (%s, %s, %s)",
        ('briefing', '{}', 'session')
    )

    return [TextContent(type="text", text=briefing_text)]
```

### Semantic Search in brain.memories

```python
# Source: vector_db.py pattern adapted for brain schema
async def _handle_search(arguments: dict) -> list[TextContent]:
    from pgvector.psycopg2 import register_vector
    import numpy as np

    query = arguments["query"]
    limit = arguments.get("limit", 10)

    # Generate query embedding (reuse VectorDBManager pattern)
    from promaia.storage.vector_db import VectorDBManager
    vdb = VectorDBManager()
    query_embedding = vdb.generate_embedding(query)

    db = get_postgres_db()
    with db.get_connection() as conn:
        register_vector(conn)
        with conn.cursor(cursor_factory=__import__('psycopg2').extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT content, summary, domain, source, created_at,
                       embedding <=> %s::vector AS distance
                FROM brain.memories
                WHERE embedding IS NOT NULL
                ORDER BY distance
                LIMIT %s
            """, (query_embedding, limit))
            results = [dict(r) for r in cur.fetchall()]

    text = "\n\n".join(
        f"[{r['domain'] or 'unknown'}] {r['summary'] or r['content'][:200]}"
        for r in results
    )
    return [TextContent(type="text", text=text or "No memories found.")]
```

### Applying Brain Schema (db_init.py extension)

```python
# Source: pattern from promaia/storage/db_init.py (existing)
import os

def apply_brain_schema():
    """Apply brain schema tables. Idempotent (CREATE TABLE IF NOT EXISTS)."""
    brain_schema_path = os.path.join(os.path.dirname(__file__), '..', 'brain', 'schema.sql')
    with open(brain_schema_path, 'r') as f:
        sql = f.read()

    db = get_postgres_db()
    db.execute(sql)
    logger.info("Brain schema applied successfully")
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| ChromaDB for vectors | pgvector in Postgres | Phase 1 (2026-03-04) | All vectors now cloud-native in Supabase |
| google-generativeai | google-genai SDK | Phase 1 (2026-03-04) | `genai.Client`, `gemini-embedding-001` |
| Low-level MCP SDK only | FastMCP available as alternative | 2025 | Either works; low-level already in codebase |
| Manual JSON parsing for structured LLM output | `instructor` library | 2024-2025 | Typed, validated, retried automatically |
| `halfvec` for embeddings | `vector(768)` | Phase 1 design review | More stable, better Supabase support |

**Deprecated/outdated:**
- `halfvec`: Considered but rejected (Gemini review 2026-03-04). Use `vector(768)`.
- IVFFlat index: Open Brain project uses it, but HNSW is the correct choice here (research from Phase 1). Use HNSW.
- `google-generativeai`: EOL August 2025, already migrated in Phase 1.

---

## Open Questions

1. **instructor integration with google-genai SDK**
   - What we know: `instructor` supports Gemini via tool calling; has `from_genai()` method
   - What's unclear: Exact initialization with the `genai.Client` pattern used in this codebase vs. `from_provider()` string
   - Recommendation: Test `instructor.from_genai(genai.Client(api_key=...))` in Wave 0; if it fails, use raw Gemini Flash with `response_mime_type="application/json"` and Pydantic parsing manually

2. **Session ID tracking for mode logging**
   - What we know: `brain.modes` stores session_id; `brain.events` stores session_id
   - What's unclear: How to get a stable session identifier from Claude Code (process ID? timestamp? env var?)
   - Recommendation: Generate UUID on MCP server startup and use as session_id for that server's lifecycle. Store in module-level variable.

3. **Seed data: initial domains and directives**
   - What we know: Design doc lists example directives for Heatpup, HVAC Brand, PURRfoot
   - What's unclear: Exact domains and priorities Zack wants at launch
   - Recommendation: Include a seed script in the plan that inserts known domains with placeholder directives. Zack updates directives during Phase 2 testing.

4. **Embedding async vs sync in capture**
   - What we know: Embedding generation takes ~200-500ms; capture should feel instant
   - What's unclear: Whether psycopg2 connections can be used truly async in this context
   - Recommendation: Insert memory row without embedding first, return acknowledgment, then update embedding in same async handler after response. Use `asyncio.create_task()` if response must return before embedding completes.

---

## Validation Architecture

Note: `workflow.nyquist_validation` is not set in `.planning/config.json` (only `workflow.research: true` is set). The key `nyquist_validation` is absent, which is interpreted as `false`. The Validation Architecture section is included here as guidance regardless, since test infrastructure exists.

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 8.3.5 + pytest-asyncio 0.26.0 |
| Config file | `pyproject.toml` (`[tool.pytest.ini_options]`) |
| Quick run command | `pytest tests/ -x -q` |
| Full suite command | `pytest tests/ --cov=promaia` |
| Estimated runtime | ~10-30 seconds (no live DB in unit tests) |

### Phase Requirements to Test Map

| Req ID | Behavior | Test Type | Automated Command |
|--------|----------|-----------|-------------------|
| BRAIN-01 | brain.memories table exists with vector(768) column | integration | `pytest tests/test_brain_schema.py::test_memories_table -x` |
| BRAIN-02 | brain.domains table exists; domains queryable | integration | `pytest tests/test_brain_schema.py::test_domains_table -x` |
| BRAIN-03 | Standing directive stored and queryable by domain | integration | `pytest tests/test_brain_schema.py::test_contexts_directive -x` |
| BRAIN-04 | capture tool extracts action from "I need to..." text | unit (mocked) | `pytest tests/test_brain_engine.py::test_action_extraction -x` |
| BRAIN-05 | briefing tool returns stale project data | unit (mocked DB) | `pytest tests/test_brain_mcp.py::test_briefing_tool -x` |
| BRAIN-06 | Stale alert fires when last_updated > threshold | unit (mocked DB) | `pytest tests/test_brain_mcp.py::test_stale_alert -x` |

### Wave 0 Gaps (must be created before implementation)

- [ ] `tests/test_brain_schema.py` — covers BRAIN-01, BRAIN-02, BRAIN-03 (requires live DB or mock)
- [ ] `tests/test_brain_engine.py` — covers BRAIN-04 (mock instructor/Gemini; test extraction logic)
- [ ] `tests/test_brain_mcp.py` — covers BRAIN-05, BRAIN-06 (mock PostgresDB; test tool handlers)

---

## Sources

### Primary (HIGH confidence)

- Codebase: `promaia/mcp/gmail_tools_server.py` — existing MCP server pattern (low-level SDK, stdio, `@server.list_tools`, `@server.call_tool`)
- Codebase: `promaia/storage/postgres_db.py` — `PostgresDB.fetch_all()`, `execute()`, `insert_returning()`, `get_connection()` patterns
- Codebase: `promaia/storage/vector_db.py` — `register_vector(conn)` pattern, `gemini-embedding-001` embedding generation
- Codebase: `promaia/storage/schema.sql` — HNSW + GIN index DDL patterns to mirror for brain schema
- Codebase: `requirements.txt` — confirms `mcp>=1.26.0`, `psycopg2-binary>=2.9.9`, `pgvector>=0.4.2`, `google-genai>=1.65.0` already installed
- Official docs: https://code.claude.com/docs/en/mcp — Claude Code MCP registration (`claude mcp add --scope project --transport stdio`), `.mcp.json` format, `CLAUDE_PLUGIN_ROOT` env var patterns
- Design docs: `docs/plans/2026-03-04-zbrain-promaia-merge-design.md` and `docs/plans/2026-03-04-zbrain-workflow-design.md` — full schema spec, engine.py function signatures, system instruction text

### Secondary (MEDIUM confidence)

- WebSearch + official PyPI: FastMCP vs mcp SDK comparison — FastMCP is standard in 2025-2026 but low-level SDK sufficient for this project since already in use
- WebSearch + instructor.com docs: `instructor` library confirmed to support Gemini via `from_genai()` wrapper
- GitHub (open-brain project): Confirms FastMCP + pgvector pattern is viable for brain-style memory servers; uses IVFFlat (we use HNSW, which is correct)

### Tertiary (LOW confidence)

- WebSearch: Specific `instructor.from_genai()` initialization syntax — needs verification in Wave 0 test

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all core deps already in requirements.txt; MCP pattern already in codebase
- Architecture: HIGH — design docs are the spec; patterns directly visible in codebase
- Pitfalls: HIGH for schema/pgvector (same issues as Phase 1); MEDIUM for instructor integration (new dep)
- Seed data: LOW — domains/directives need Zack input

**Research date:** 2026-03-04
**Valid until:** 2026-04-04 (30 days; mcp and instructor packages move fast but core patterns stable)
