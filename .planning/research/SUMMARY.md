# Project Research Summary

**Project:** zBrain v1.0
**Domain:** Personal AI memory layer and proactive agent system (Promaia fork)
**Researched:** 2026-03-04
**Confidence:** HIGH (stack and architecture based on direct code inspection; pitfalls verified against official docs)

## Executive Summary

zBrain is a personal AI brain built as a focused fork of the Promaia platform. Its core value proposition is eliminating AI amnesia: the system remembers across sessions, proactively surfaces what matters, extracts action commitments from conversations, and runs autonomous overnight work. The recommended approach is additive — build new `brain/` and `heartbeat/` modules on top of Promaia's existing agent orchestration, connector, and multi-model adapter infrastructure, while replacing the local SQLite/ChromaDB storage with Railway Volumes libSQL/MuninnDB and pgvector. Nothing in the existing connector or CLI layer needs to change; the work is primarily in storage migration, a new model router, and the brain behavioral layer.

The most important sequencing decision is infrastructure first. Every zBrain feature — session briefings, action extraction, standing directives, stale project alerts, heartbeat agent — depends on the brain schema being live in Railway Volumes with pgvector enabled. Daughter's `libsql-changeover` branch is 70% complete and is the critical path blocker. Until Railway Volumes is the storage target and the `brain.*` schema exists, no other work can proceed meaningfully. The model routing layer (new `ai/router.py`) should be built second, before the brain module, so brain features use Gemini Flash from day one rather than making direct API calls that need refactoring later.

The principal risks are technical and operational. On the technical side: asyncpg prepared statement failures on Railway Volumes's pooler (use port 5432 direct connection), chromadb-to-pgvector API mismatch (no drop-in replacement — requires a full abstraction layer), and embedding model deprecation (text-embedding-004 is past EOL; use `gemini-embedding-001` via the new `google-genai` SDK). On the operational side: the heartbeat agent must invoke Claude via the official Claude Code CLI subprocess pattern — not via Agent SDK or OAuth extraction — to comply with Anthropic's ToS. Upstream codebase drift is also a real risk given that daughter's Promaia is under active development; weekly rebases on `zbrain` are non-negotiable.

---

## Key Findings

### Recommended Stack

The new additions are minimal and deliberate. Three new packages cover all zBrain requirements: `pgvector==0.4.2` (vector type binding for the existing psycopg2 connection), `google-genai==1.65.0` (replaces deprecated `google-generativeai`, provides `gemini-embedding-001` embeddings and Gemini 2.5 Flash for cheap tasks), and `mcp[cli]==1.26.0` (bundles FastMCP for the Brain MCP server, already used in Promaia for external servers). The heartbeat agent requires no new Python scheduler library — Windows Task Scheduler plus a `.bat` wrapper is sufficient and simpler than running a daemon.

Two migration steps are mandatory before writing new code: (1) uninstall `google-generativeai` and update all imports to `google-genai`, since the old SDK is deprecated and past EOL as of August 2025; (2) swap the libSQL/MuninnDB connection string from the local `192.168.0.69` host to the Railway Volumes session pooler URL. The Brain MCP server must run in a separate Python 3.10+ venv since `mcp[cli]` requires Python >=3.10 while Promaia targets 3.8+.

**Core technologies:**
- `pgvector==0.4.2`: Vector type for psycopg2 — one `register_vector(conn)` call, no separate DB process
- `google-genai==1.65.0`: Required replacement for deprecated SDK; provides `gemini-embedding-001` (768 dims) and Gemini 2.5 Flash
- `mcp[cli]==1.26.0`: FastMCP bundled; builds Brain MCP server; Python 3.10+ venv required
- Railway Volumes session pooler (port 5432): IPv4+IPv6 compatible; psycopg2 direct connection avoids asyncpg prepared statement issues
- Windows Task Scheduler + `.bat` wrapper: Heartbeat trigger; no daemon, no Redis, no APScheduler

**Critical version constraints:**
- `gemini-embedding-001` at 768 dimensions (NOT `text-embedding-004`, deprecated Nov 2025; NOT `text-embedding-005` without dimension verification)
- `google-genai` NOT `google-generativeai` (deprecated August 2025, past EOL)
- Python 3.10+ for the Brain MCP server venv only

### Expected Features

The libSQL/MuninnDB migration is the only pre-condition. Once the `brain.*` schema exists in Railway Volumes, all features become buildable independently.

**Must have (table stakes — v1.0):**
- Persistent cross-session memory — core value proposition; without this the system is just a chatbot
- Session startup briefing — surfaces open actions, stale projects, directives, overnight report; must complete in <5 seconds
- Action extraction — async post-session LLM pass over transcript; writes to `brain.actions`
- Standing directives — per-domain config injected into system prompt context; edit via `maia directive set`
- Stale project alerts — timestamp query against `brain.domains`; addresses Zack's project-bouncing pattern
- Gemini model routing — deterministic task-type table (not a fallback chain); Gemini Flash for cheap tasks, Claude for reasoning
- Brain ingestion: YouTube — primary research format; `youtube-transcript-api` → chunk → embed → store
- Heartbeat agent — Windows Task Scheduler, 2–6 AM window, single-run script, HEARTBEAT.md checklist pattern
- iPhone access verification — Railway Volumes cloud already provides this; verify claude.ai + MCP works day-1

**Should have (competitive — v1.1):**
- Google Calendar integration — briefing includes today's schedule; heartbeat pre-researches meetings
- Email/message triage — Gmail scanning in heartbeat; draft replies
- Brain ingestion: documents — PDF/text for HVAC sales materials and research docs
- Overnight work reporting — structured `brain.reports` record surfaced in next briefing
- Heartbeat work queue — priority-ranked backlog for systematic overnight work

**Defer (v2+):**
- Kanban board UI — defer until schema is stable; rework risk if built before data model matures
- React web chat / Electron app — daughter's domain, out of zBrain scope
- Cross-user / shared brain — Promaia handles multi-user; zBrain stays personal
- Automatic memory forgetting / decay — adds complexity; v1 keeps everything

**Anti-features to consciously avoid:**
- Real-time conversation monitoring (always-on process, privacy surface, no clear session boundary)
- Automatic memory deletion (creates unreliable system behavior; use manual archive instead)
- Email triage in heartbeat v1 (needs stable brain foundation first)

### Architecture Approach

The architecture is strictly additive. Two new top-level modules (`brain/` and `heartbeat/`) contain all new behavioral logic. Two existing modules are modified (`storage/vector_db.py` replaces ChromaDB internals while preserving the public interface; `storage/postgres_db.py` changes its connection target). One new module is added to the AI layer (`ai/router.py`). The connector layer and CLI layer are untouched except for new hook points (briefing on chat startup, new `maia brain` and `maia heartbeat` commands).

The `brain/` module is explicitly NOT in `storage/` — this separation matters for the daughter's fork. Storage is raw connector output; brain is derived intelligence (reasoning, extraction, directives). Keeping them in separate modules means she can cherry-pick storage changes without picking up brain logic. The `brain.*` libSQL/MuninnDB schema is separate from `public.*` for the same reason.

**Major components:**
1. `brain/` module — `briefing.py`, `actions.py`, `directives.py`, `stale.py`; the behavioral intelligence layer that reads from storage and reasons about state
2. `ai/router.py` — deterministic task-type routing; `TaskType` enum maps each task category to a specific model client (Gemini Flash for cheap tasks, Claude Sonnet for reasoning/chat)
3. `storage/vector_db.py` (modified) — same public interface, ChromaDB internals replaced with pgvector SQL; callers unchanged
4. `heartbeat/` module — `runner.py` (single-run entry point), `tasks.py` (stale check, action review, brain ingest); wraps existing `agents/executor.py`
5. `storage/brain_schema.sql` — `brain.memories`, `brain.domains`, `brain.actions`, `brain.reviews`, `brain.directives`; HNSW index on embedding column from creation

**Key patterns to follow:**
- Preserve `VectorDBManager`'s public interface (`search`, `add_content`, `add_content_with_chunking`, `check_exists`) — four callers depend on these signatures
- Use HNSW index (not IVFFlat) — HNSW builds incrementally, works on empty tables, Railway Volumes recommends it
- Build router before brain module so brain uses it from day one
- Heartbeat is a single-run script, not a daemon — Task Scheduler handles scheduling

### Critical Pitfalls

1. **asyncpg + Railway Volumes pooler incompatibility** — Railway Volumes's pooler (port 6543, PgBouncer in transaction mode) does not persist prepared statements; asyncpg uses them automatically; queries that work locally fail against Railway Volumes. Prevention: use port 5432 (direct connection) for all Python processes; never use the pooler for persistent Python services.

2. **Anthropic ToS — heartbeat agent invocation method** — Claude Max OAuth tokens are valid only inside the official Claude Code CLI. Using Agent SDK or any library that extracts OAuth tokens programmatically is a ToS violation Anthropic actively enforces (blocks deployed January 2026). Prevention: heartbeat invokes Claude via `claude` CLI subprocess only. Never use Agent SDK with Max subscription credentials.

3. **ChromaDB is not a drop-in replacement for pgvector** — ChromaDB has a Python client API (`collection.add()`, `collection.query()`); pgvector is a SQL extension with no Python SDK. All vector operations must be rewritten as SQL. Four existing Promaia callers reference `vector_db.py`. Prevention: audit all `chromadb` imports first; build a `VectorDBManager` abstraction that preserves the existing public interface; swap internals, not the interface.

4. **Embedding dimension lock-in** — `text-embedding-004` is deprecated (November 2025); `gemini-embedding-001` is the replacement. pgvector columns are typed with fixed dimensions at creation. Switching models mid-project requires `ALTER TABLE` plus full re-embedding. Prevention: verify current model dimensions before writing schema; store model name in `brain.embedding_config`; use config constant not hardcoded string; use HNSW index which handles schema changes better.

5. **Heartbeat token runaway** — autonomous agents with no budget ceiling can exhaust rate limits overnight or pollute the brain schema with a retry loop. Prevention: hard per-run limits (max tokens, max API calls, max wall-clock seconds); risk-tier model (low-risk ops run automatically, high-risk ops never run autonomously in v1); log every API call to `brain.heartbeat_log`.

6. **Upstream codebase drift** — daughter's Promaia is under active development; every week of divergence adds merge conflict accumulation. Prevention: weekly rebase of `zbrain` on `feature/agent-scheduler`; prefer additive changes to existing files; keep `brain.*` schema separate from `public.*` to protect the boundary.

7. **IVFFlat index on empty table** — IVFFlat builds cluster centers from data present at index creation; an empty table means broken recall with no error thrown. Prevention: use HNSW exclusively; never IVFFlat.

8. **Custom schema not exposed in Railway Volumes Data API** — `brain.*` schema is invisible to PostgREST by default; RLS defaults to DENY ALL. Prevention: add `brain` to exposed schemas in Railway Volumes dashboard; use direct psycopg2 connection for all Python brain operations; set RLS policy for service-role access.

---

## Implications for Roadmap

The dependency chain is clear: storage foundation unlocks everything. Model router enables brain features. Brain module enables heartbeat. This dictates a strict four-phase sequence.

### Phase 1: Storage Foundation
**Rationale:** Absolute critical path. Every zBrain feature depends on Railway Volumes being the storage target and `brain.*` schema existing. This completes daughter's 70%-done `libsql-changeover` branch, adds pgvector, creates the brain schema, and validates the connection. Nothing else can be built on an unvalidated foundation.
**Delivers:** Railway Volumes as active storage target; `brain.*` schema live with HNSW indexes; ChromaDB internals replaced in `VectorDBManager` while preserving public interface; `maia sync` writing embeddings to Railway Volumes pgvector; verified connection from Windows 11 machine
**Addresses:** libSQL/MuninnDB/pgvector migration, brain schema creation, iPhone access (Railway Volumes cloud)
**Avoids:** asyncpg pooler incompatibility (port 5432 direct); IVFFlat on empty table (HNSW from creation); embedding dimension lock-in (gemini-embedding-001 at 768 dims via config constant); ChromaDB API mismatch (abstraction layer); SQLite parameter style bugs (audit before building); Railway Volumes schema exposure (configure during setup)
**Research flag:** STANDARD PATTERNS — Railway Volumes libSQL/MuninnDB migration is well-documented; pgvector HNSW setup is documented by Railway Volumes; connection pooler behavior is documented in official Railway Volumes docs. No phase research needed.

### Phase 2: Model Router
**Rationale:** Brain features need Gemini Flash for cheap tasks. Building the router before the brain module means brain code uses the router from day one and never makes direct API calls that need refactoring. This is infrastructure, not a user feature, so it should be invisible to end users.
**Delivers:** `ai/router.py` with `TaskType` enum and `ModelRouter` class; Gemini Flash as first-class specialist (not fallback); `google-generativeai` → `google-genai` migration complete; model names as config constants
**Uses:** `google-genai==1.65.0`, existing `ai/models.py` (data only, unchanged), existing `anthropic` SDK
**Implements:** `TaskType.BRIEFING/EMBEDDING/EXTRACTION/REASONING/CHAT/HEARTBEAT` routing table
**Avoids:** Using deprecated `google-generativeai`; hardcoding model names; routing all tasks through Claude (cost/quota risk)
**Research flag:** STANDARD PATTERNS — task-based LLM routing is well-documented; `google-genai` migration path is official; no phase research needed.

### Phase 3: Brain Module
**Rationale:** Core value proposition. Once storage and routing exist, the brain behavioral layer can be built. Session briefing validates the schema before heartbeat adds autonomous execution on top — this is the correct verification order. Every brain component reads from validated storage and uses the validated router.
**Delivers:** `brain/briefing.py` (session startup briefing hooked into `maia chat`); `brain/actions.py` (action extraction from conversation transcripts); `brain/directives.py` (per-project standing instructions); `brain/stale.py` (dormant project detection); `cli/brain_commands.py` (`maia brain status`, `maia brain briefing`, `maia directive set`)
**Addresses:** Session startup briefing, action extraction, standing directives, stale project alerts
**Avoids:** Putting brain logic in the storage layer (keep `brain/` separate from `storage/`); routing extraction tasks through Claude (use Gemini Flash via router); briefing exceeding 500 words (hard cap to 3-5 bullets per domain)
**Research flag:** STANDARD PATTERNS for action extraction (well-documented LLM extraction pattern) and briefing composition. WATCH: prompt engineering for extraction quality — may need iteration. No dedicated phase research needed, but budget time for prompt tuning.

### Phase 4: Heartbeat Agent
**Rationale:** Last because it depends on all three prior phases. Brain provides context; storage provides read/write; router provides cheap model calls. The heartbeat is autonomous execution on top of validated infrastructure, not the other way around.
**Delivers:** `heartbeat/runner.py` (single-run entry point, exits cleanly); `heartbeat/tasks.py` (stale check, action review, initial brain ingest); `cli/heartbeat_commands.py` (`maia heartbeat --run`, `--dry-run`, `--status`); Windows Task Scheduler setup (documented, configured once); budget ceiling and kill switch; heartbeat log to `brain.heartbeat_log`
**Addresses:** Heartbeat agent, overnight work reporting
**Avoids:** Daemon pattern (single-run script only); ToS violation (Claude Code CLI subprocess, not Agent SDK); token runaway (hard per-run limits from the start); Windows Task Scheduler path issues (absolute paths, first-action log entry); scope creep (no Gmail triage in v1)
**Research flag:** NEEDS ATTENTION — Anthropic ToS compliance for CLI subprocess invocation pattern should be verified against current ToS before implementation. Task Scheduler path behavior on Windows 11 should be smoke-tested early. These are not blockers for phase planning but must be resolved before heartbeat is built.

### Phase 5: Brain Ingestion Pipeline
**Rationale:** YouTube ingestion is the highest-value ingestion source for Zack's research workflow and can be built independently of heartbeat. Web ingestion follows the same pipeline pattern. Both feed the brain schema established in Phase 1 and use the router from Phase 2.
**Delivers:** `maia ingest youtube [url]` (transcript → chunk → embed → store with source metadata); `maia ingest web [url]` (fetch → extract → chunk → embed → store); ingestion as BaseConnector subclasses following existing connector plugin architecture
**Addresses:** Brain ingestion: YouTube, Brain ingestion: web
**Avoids:** Running continuous background sync (scheduled/on-demand only, not real-time); ingesting into `public.*` tables (ingestion goes to `brain.memories`)
**Research flag:** STANDARD PATTERNS — `youtube-transcript-api` is well-documented; chunking and embedding pipelines are established patterns. No phase research needed.

### Phase Ordering Rationale

- Phase 1 is forced by dependency: all features require the storage layer. No alternatives.
- Phase 2 before Phase 3 is forced by design: brain code should use the router from its first line, not make direct API calls and refactor later.
- Phase 3 before Phase 4 is forced by dependency: heartbeat uses brain for context and writes to brain tables.
- Phase 5 is independent of Phase 4 and can overlap with late Phase 3 if capacity allows. It is ordered after heartbeat because heartbeat's overnight operation benefits from having ingested content to work with.
- v1.1 additions (Calendar, Gmail, document ingestion, Obsidian sync) are deferred until Phase 1–5 proves stable.

### Research Flags

Phases needing deeper research during planning:
- **Phase 4 (Heartbeat Agent):** Verify current Anthropic ToS on CLI subprocess invocation pattern before implementation. The compliant path (calling `claude` CLI subprocess) is documented but ToS evolves rapidly. Also smoke-test Windows Task Scheduler absolute path behavior on Windows 11 before committing to the bat wrapper architecture.

Phases with standard patterns (skip research-phase):
- **Phase 1:** Railway Volumes libSQL/MuninnDB/pgvector migration is extensively documented. HNSW index setup is Railway Volumes-official. psycopg2 direct connection is standard.
- **Phase 2:** Task-based LLM routing is a well-established pattern. `google-genai` SDK migration is official and documented.
- **Phase 3:** LLM-based action extraction and session briefing composition are established patterns. Prompt iteration may be needed but doesn't require research.
- **Phase 5:** `youtube-transcript-api` and chunking pipelines are documented and stable.

---

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | Versions verified against official PyPI and Google/Anthropic docs. One MEDIUM exception: Gemini model naming changes frequently — verify `gemini-2.5-flash-lite` string at runtime startup; SDK returns clear error if wrong. |
| Features | MEDIUM-HIGH | Core patterns (session briefing, action extraction, heartbeat) are well-documented in analogous systems (OpenClaw, Nate Jones Open Brain). Specific Promaia integration points inferred from codebase context rather than tested. |
| Architecture | HIGH | Based on direct code inspection of 400+ lines across 10 source files in the `zbrain` and `libsql-changeover` branches. Component boundaries and integration points are verified, not inferred. |
| Pitfalls | HIGH | Most pitfalls verified via official docs and multiple sources. asyncpg/pooler incompatibility confirmed via Railway Volumes GitHub issues. Anthropic ToS constraint confirmed via official support article. ChromaDB migration pitfalls confirmed via multiple migration post-mortems. |

**Overall confidence:** HIGH

### Gaps to Address

- **Gemini model name verification at runtime:** `gemini-2.5-flash-lite` is the recommended model as of March 2026 but Google model naming changes frequently. Add a startup check that validates the model string against the API before the first production run.
- **`text-embedding-004` vs `gemini-embedding-001` availability:** STACK.md directs use of `gemini-embedding-001` (via `google-genai` SDK). ARCHITECTURE.md references `text-embedding-004` in some patterns (written slightly earlier). PITFALLS.md confirms `text-embedding-004` is deprecated. Treat `gemini-embedding-001` via `google-genai` as the definitive choice. Verify availability with a test API call before writing the schema.
- **Python 3.10+ venv for Brain MCP server:** Promaia targets Python 3.8+. The Brain MCP server requires a separate 3.10+ venv. This venv setup is not yet documented in the project. Address in Phase 1 setup.
- **Railway Volumes Pro connection limit:** Pro plan allows 60 direct connections. With heartbeat + CLI + any concurrent processes, this could be a constraint. Document and revisit at v1.1 if needed. Not a day-1 blocker.
- **Upstream sync cadence:** Daughter's `feature/agent-scheduler` branch is the sync target. Weekly rebases must begin in Phase 1 and never slip. This is a process requirement, not a technical gap.

---

## Sources

### Primary (HIGH confidence)
- Direct code inspection: `storage/vector_db.py`, `ai/models.py`, `storage/hybrid_storage.py`, `agent/agent_manager.py`, `agents/scheduler.py`, `agents/executor.py`, `mcp/client.py`, `connectors/base.py`, `storage/postgres_db.py`, `storage/schema.sql` — architecture and integration points
- [Railway Volumes Connecting to libSQL/MuninnDB Docs](https://railway_volumes.com/docs/guides/database/connecting-to-postgres) — session pooler format, IPv6 direct-only warning, port guidance
- [Railway Volumes pgvector Docs](https://railway_volumes.com/docs/guides/database/extensions/pgvector) — HNSW index recommendation
- [Google Gemini Embeddings Docs](https://ai.google.dev/gemini-api/docs/embeddings) — `gemini-embedding-001`, 128-3072 dims, `text-embedding-004` deprecated
- [google-genai PyPI 1.65.0](https://pypi.org/project/google-genai/) — version confirmed 2026-02-26
- [MCP Python SDK PyPI 1.26.0](https://pypi.org/project/mcp/) — Python >=3.10 requirement confirmed
- [pgvector Python PyPI 0.4.2](https://pypi.org/project/pgvector/) — psycopg2 integration, Python >=3.9
- [Anthropic: Using Claude Code with Pro/Max plan](https://support.claude.com/en/articles/11145838-using-claude-code-with-your-pro-or-max-plan) — ToS constraint on heartbeat invocation

### Secondary (MEDIUM confidence)
- [pgvector/pgvector-python GitHub](https://github.com/pgvector/pgvector-python) — `register_vector()` pattern
- [Google deprecated-generativeai-python GitHub](https://github.com/google-gemini/deprecated-generativeai-python) — confirms `google-generativeai` is deprecated
- [Railway Volumes GitHub Issue: asyncpg prepared statement errors](https://github.com/railway_volumes/railway_volumes/issues/39227) — pooler incompatibility verified
- [ChromaDB migration post-mortem](https://wwakabobik.github.io/2025/11/migrating_chroma_db/) — API mismatch pitfall confirmed
- [pgvector vs ChromaDB comparison (Elestio)](https://blog.elest.io/pgvector-vs-chromadb-when-to-extend-postgresql-and-when-to-go-dedicated/) — no Python SDK for pgvector confirmed
- [OpenClaw HEARTBEAT.md Guide](https://openclawconsult.com/lab/openclaw-heartbeat-md) — heartbeat pattern and checklist approach
- [Gemini 2.5 Flash-Lite Docs](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/models/gemini/2-5-flash) — fastest/cheapest 2.5 family model confirmed

### Tertiary (LOW confidence — verify before use)
- [n8n Community: text-embedding-004 deprecation](https://community.n8n.io/t/google-deprecating-text-embedding-004-but-gemini-embedding-001-doesnt-work/262008) — community report; deprecation confirmed by Google docs but endpoint availability should be verified directly
- [Agentic cost control: token runaway prevention](https://www.alpsagility.com/cost-control-agentic-systems) — budget ceiling pattern; implement based on principles, not this specific source

---
*Research completed: 2026-03-04*
*Ready for roadmap: yes*
