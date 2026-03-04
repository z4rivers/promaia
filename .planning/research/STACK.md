# Stack Research

**Domain:** Personal AI memory / autonomous agent platform (Python backend, cloud Postgres, MCP server)
**Researched:** 2026-03-04
**Confidence:** HIGH for versions; MEDIUM for Gemini model naming (fast-moving); HIGH for integration patterns

---

## Context: What Already Exists (Do Not Re-Add)

These are validated in Promaia and must integrate with, not replace:
- `psycopg2` — already in daughter's `postgres-sql-changeover` branch, keep it
- `google-generativeai` — already in multi-model adapter, being **migrated** (see SDK change below)
- `anthropic` SDK — primary LLM, keep
- `mcp` Python SDK — already powering Gmail/Notion/Filesystem/Git/SQLite servers
- `FastAPI` — existing web interface
- `python-dotenv` — existing config pattern

---

## New Additions: Core Technologies

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| `pgvector` (Python) | 0.4.2 | Register vector type with psycopg2; numpy array <-> `vector` column marshaling | Official pgvector Python bindings. Works with existing psycopg2. One `register_vector(conn)` call wires it in. No separate vector DB process to run. |
| `google-genai` | 1.65.0 | Replaces deprecated `google-generativeai`; embeddings via `gemini-embedding-001`; Gemini Flash for cheap tasks | `google-generativeai` is deprecated (EOL August 31, 2025 — already past). `google-genai` is the unified SDK supporting both AI Studio and Vertex AI. Migration is required, not optional. |
| `mcp` (Python SDK) | 1.26.0 | Build the Brain MCP server with `@mcp.tool()` decorated functions | Already used in Promaia for external servers. Use the same SDK to build zBrain's own server. `FastMCP` is bundled inside `mcp[cli]` — no separate install. |

---

## New Additions: Supporting Libraries

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `pgvector[psycopg2]` | 0.4.2 | The `psycopg2` integration extra for pgvector | Use when registering vector type with existing psycopg2 connections in daughter's `PostgresDB` singleton |
| `numpy` | >=1.24 | Required by pgvector for array <-> vector conversion | Already likely present; verify in requirements. pgvector Python bindings use numpy arrays for vectors |
| `python-dotenv` | existing | Supabase connection string from env var | Already used — just add `SUPABASE_SESSION_POOLER_URL` to `.env` |

---

## Supabase Connection: Critical Decision

**Use the Session Pooler, not the Direct Connection.**

Supabase direct connections are IPv6-only. Windows 11 home networks are typically dual-stack but ISP behavior varies. The session pooler supports IPv4 + IPv6 and is the documented fallback for environments where direct IPv6 fails.

Connection string format (session pooler):
```
postgresql://postgres.dulqttfidcjeujyieuqw:[PASSWORD]@aws-0-[REGION].pooler.supabase.com:5432/postgres
```

Direct connection format (IPv6 only — avoid on Windows unless confirmed IPv6 works):
```
postgresql://postgres:[PASSWORD]@db.dulqttfidcjeujyieuqw.supabase.co:5432/postgres
```

The existing `PostgresDB` singleton in daughter's branch targets `192.168.0.69`. The only change needed is swapping the connection string to the Supabase session pooler URL. The `psycopg2` code itself does not change.

---

## Embeddings: Use gemini-embedding-001, Not text-embedding-004

**CRITICAL: text-embedding-004 is deprecated as of January 14, 2026.** Do not build against it.

The replacement is `gemini-embedding-001`:
- 128 to 3,072 output dimensions (MRL-based, recommended: 768, 1536, or 3072)
- Available via `google-genai` SDK: `client.models.embed_content(model='gemini-embedding-001', ...)`
- Covered by existing Google AI Premium subscription

**pgvector column size decision:** Use 768 dimensions. Rationale: Supabase already has 37+ tables from Heatpup; 768 is the recommended efficient size, cuts storage/index cost vs 3072 while MRL guarantees no quality loss at this tier.

```python
# pgvector column: vector(768)
CREATE TABLE brain.memories (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    embedding vector(768),
    ...
);
```

---

## Gemini Model Routing: Use gemini-2.5-flash-lite

**Purpose:** Cheap, fast tasks that should not consume Claude Max quota — action extraction, summarization, classification, briefing generation from raw content.

**Model choice:** `gemini-2.5-flash-lite` (as of March 2026, this is the fastest/cheapest in the 2.5 family). The `google-genai` SDK uses model strings directly:

```python
from google import genai
client = genai.Client()  # uses GEMINI_API_KEY env var
response = client.models.generate_content(
    model='gemini-2.5-flash-lite',
    contents=prompt
)
```

**Routing logic (not a library, a pattern):** In the existing multi-model adapter, add a routing tier:
- `claude-3-5-sonnet` → strategic reasoning, final synthesis, anything touching user trust
- `gemini-2.5-flash-lite` → extraction, classification, summarization, structured output from raw content
- Do NOT add OpenAI to this — PROJECT.md explicitly replaces OpenAI with Gemini

**MEDIUM confidence on model name:** Google model naming changes frequently. Verify `gemini-2.5-flash-lite` string at runtime startup. The SDK will return a clear error if model name is wrong.

---

## Brain MCP Server: Use mcp[cli] 1.26.0 (FastMCP)

The Brain MCP server exposes tools that Claude Code (and claude.ai on iPhone) can call to read/write the brain schema.

Pattern — this is what the server code looks like:

```python
from mcp.server.fastmcp import FastMCP
import psycopg2
from pgvector.psycopg2 import register_vector

mcp = FastMCP(name="zBrain")

@mcp.tool()
def get_session_briefing(project: str) -> str:
    """Return a briefing for the named project from brain.memories."""
    conn = get_db_connection()
    # ... query brain.memories, brain.actions, brain.directives
    return briefing_text

@mcp.tool()
def store_memory(content: str, domain: str, source: str) -> str:
    """Embed and store a memory in the brain."""
    embedding = embed(content)  # google-genai call
    # ... INSERT INTO brain.memories
    return "stored"
```

**Note on MCP Python version requirement:** `mcp` 1.26.0 requires Python >=3.10. Promaia targets Python 3.8+. The brain MCP server should be written as a **separate runnable script** (`zbrain_mcp_server.py`) that uses Python 3.10+ from a dedicated venv, not embedded in the main Promaia package. This avoids forcing a Python version bump on the upstream codebase.

---

## Heartbeat Agent: Windows Task Scheduler + Batch Wrapper

**No new Python library needed.** The heartbeat is a scheduled call to Claude Code CLI.

Architecture:
```
Windows Task Scheduler (3am daily)
  → run_heartbeat.bat
    → activates zbrain venv
    → runs: claude --model claude-opus-4-6 -p "$(cat heartbeat_prompt.txt)"
```

The `.bat` wrapper is required because Task Scheduler does not inherit PATH or venv state from interactive sessions.

```batch
@echo off
call C:\Users\Zachary Turner\dev\promaia\.venv\Scripts\activate.bat
cd /d C:\Users\Zachary Turner\dev\promaia
claude --model claude-opus-4-6 --allowedTools "mcp__zbrain__*" -p "@heartbeat_prompt.txt" >> logs\heartbeat.log 2>&1
```

**Task Scheduler setup (one-time, via schtasks):**
```batch
schtasks /Create /SC DAILY /TN "zBrainHeartbeat" /TR "C:\Users\Zachary Turner\dev\promaia\run_heartbeat.bat" /ST 03:00 /RL HIGHEST /F
```

**Important:** Log to a file (heartbeat.log) because Task Scheduler swallows stdout. Use `/RL HIGHEST` (run with highest privileges) to avoid permission issues writing logs.

---

## What NOT to Add

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| `google-generativeai` | Deprecated August 31, 2025 (past deadline). Using it means running dead code | `google-genai` 1.65.0 |
| `text-embedding-004` | Deprecated January 14, 2026. Will stop working | `gemini-embedding-001` via `google-genai` |
| `supabase` Python client (PostgREST) | Adds REST layer over Postgres; daughter's code already uses psycopg2 direct. Mixing two connection patterns creates confusion | Direct psycopg2 via session pooler |
| `vecs` (supabase/vecs) | Supabase's vector client adds abstraction that fights with custom brain schema. Designed for unstructured collections, not structured relational brain schema | pgvector Python bindings directly |
| `chromadb` | Being replaced. Local files, no cloud, blocks iPhone access | pgvector on Supabase |
| `sqlite3` / SQLite | Being replaced. Same reason — no cloud | psycopg2 + Supabase Postgres |
| `openai` SDK | PROJECT.md explicitly replaces with Gemini. No new OpenAI cost. | `google-genai` for cheap tasks, `anthropic` for primary |
| `celery` / `APScheduler` / `rq` | Over-engineered for one nightly task on a Windows PC. Adds Redis dependency or worker process | Windows Task Scheduler + batch file |
| `langchain` / `llama-index` | Heavy frameworks that fight with existing Promaia multi-model adapter. Add 50+ transitive dependencies | Direct SDK calls (anthropic, google-genai) |
| `FastMCP` standalone (PrefectHQ) | `mcp[cli]` already bundles FastMCP. Installing the standalone package creates version conflicts | `mcp[cli]` 1.26.0 |

---

## Installation

```bash
# Activate zbrain venv (Python 3.10+ required for mcp server)
# Core new additions only — everything else already in Promaia requirements

pip install pgvector==0.4.2
pip install "mcp[cli]==1.26.0"
pip install google-genai==1.65.0

# numpy is likely already present; verify
pip install numpy>=1.24
```

Migration step (required before first run):
```bash
# Remove deprecated SDK
pip uninstall google-generativeai

# Update imports in existing multi-model adapter
# from google import generativeai → from google import genai
# genai.configure(api_key=...) → client = genai.Client()
```

---

## Version Compatibility

| Package | Compatible With | Notes |
|---------|-----------------|-------|
| `pgvector==0.4.2` | `psycopg2>=2.9`, Python >=3.9 | Promaia uses 3.8+; **Brain MCP server must run on 3.10+ venv** |
| `mcp[cli]==1.26.0` | Python >=3.10 | Run as separate server process, not embedded in main Promaia package |
| `google-genai==1.65.0` | Python >=3.9 | Replaces `google-generativeai`. Not backwards-compatible — update adapter |
| `psycopg2` (existing) | `pgvector==0.4.2` | Just add `register_vector(conn)` call after connecting |
| Supabase session pooler | `psycopg2` (any version) | Port 5432, standard PostgreSQL protocol — psycopg2 needs no changes |

---

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|------------------------|
| Session pooler URL | Direct Supabase IPv6 URL | Only if you confirm Windows machine has working IPv6 (test: `ping6 google.com`) |
| `gemini-embedding-001` at 768 dims | 3072 dims | If you later find semantic search quality insufficient on short voice notes |
| `mcp[cli]` (bundled FastMCP) | FastMCP 3.x standalone | If you need FastMCP 3.x-specific features like component versioning or OAuth |
| Windows Task Scheduler + .bat | Python `schedule` library as always-on daemon | If you want sub-daily triggers without relying on the machine being on |
| Direct `psycopg2` to Supabase | `supabase` Python client | If you add non-vector features that benefit from PostgREST (auth, realtime) |

---

## Sources

- [pgvector Python PyPI](https://pypi.org/project/pgvector/) — Version 0.4.2, psycopg2 integration confirmed
- [pgvector/pgvector-python GitHub](https://github.com/pgvector/pgvector-python) — register_vector pattern, requires Python >=3.9
- [MCP Python SDK PyPI](https://pypi.org/project/mcp/) — Version 1.26.0, requires Python >=3.10
- [Supabase Connecting to Postgres Docs](https://supabase.com/docs/guides/database/connecting-to-postgres) — Session pooler format, IPv6 direct-only warning
- [Google Gemini Embeddings Docs](https://ai.google.dev/gemini-api/docs/embeddings) — gemini-embedding-001, 128-3072 dims, text-embedding-004 deprecated
- [google-genai PyPI](https://pypi.org/project/google-genai/) — Version 1.65.0, released 2026-02-26
- [Google deprecated-generative-ai-python GitHub](https://github.com/google-gemini/deprecated-generative-ai-python) — Confirms google-generativeai is deprecated
- [Google AI Migration Docs](https://ai.google.dev/gemini-api/docs/migrate) — Migration path from google-generativeai to google-genai
- [Gemini 2.5 Flash-Lite Docs](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/models/gemini/2-5-flash) — Confirmed as fastest/cheapest 2.5 family model
- [Windows Task Scheduler Python Guide](https://datatofish.com/python-script-windows-scheduler/) — .bat wrapper pattern, full path requirements
- [n8n Community: text-embedding-004 deprecation](https://community.n8n.io/t/google-deprecating-text-embedding-004-but-gemini-embedding-001-doesnt-work/262008) — Deprecation confirmed January 14, 2026

---

*Stack research for: zBrain — Promaia fork with pgvector, Supabase, Gemini routing, Brain MCP, heartbeat agent*
*Researched: 2026-03-04*
