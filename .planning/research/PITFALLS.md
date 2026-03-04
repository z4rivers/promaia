# Pitfalls Research

**Domain:** Adding cloud Postgres/pgvector, proactive AI brain, autonomous heartbeat agents, and multi-model routing to an existing Python content management platform (Promaia fork)
**Researched:** 2026-03-04
**Confidence:** HIGH (most pitfalls verified via official docs + multiple sources)

---

## Critical Pitfalls

### Pitfall 1: Supabase Transaction Pooler Breaks asyncpg Prepared Statements

**What goes wrong:**
Promaia's existing `PostgresDB` singleton likely uses asyncpg or SQLAlchemy with asyncpg. When pointed at Supabase's pooled connection (port 6543, PgBouncer in transaction mode), every query that uses a prepared statement fails with `PreparedStatementError: prepared statement 'asyncpg_stmt_X' does not exist`. This is a silent killer — it works on direct connections during local dev, then explodes when you point at Supabase.

**Why it happens:**
PgBouncer in transaction mode does not persist prepared statements between connections. asyncpg automatically uses prepared statements for performance. These two behaviors are mutually incompatible. The daughter's existing `PostgresDB` was written against a local Postgres at `192.168.0.69` (direct connection), not a pooler. Supabase's default public URL hits the pooler.

**How to avoid:**
- Use Supabase's direct connection string (port 5432) for all non-serverless, persistent Python processes.
- If you must use the pooler (port 6543), disable prepared statements explicitly: `statement_cache_size=0` in `asyncpg.connect()` and `asyncpg.create_pool()`. For SQLAlchemy: set both `statement_cache_size` and `prepared_statement_cache_size` to 0 in `connect_args`, and use `NullPool`.
- In the connection config, document which port is used and why. Never silently switch ports.

**Warning signs:**
- `PreparedStatementError` or `asyncpg.exceptions.InvalidCachedStatementError` in logs.
- Queries that work locally fail after pointing at Supabase URL.
- Intermittent failures that appear random but correlate with connection recycling.

**Phase to address:** Phase 1 (Postgres/Supabase migration). This must be resolved before any other work proceeds.

---

### Pitfall 2: Anthropic ToS Violation — Heartbeat Agent Outside Claude Code

**What goes wrong:**
Running an autonomous overnight heartbeat agent that calls Claude via a workaround, third-party library, or by invoking Claude Code's internals programmatically violates Anthropic's Terms of Service as of January 2026. The OAuth tokens from Claude Max subscriptions may only be used within Claude Code's official CLI interface. Anthropic deployed technical blocks in January 2026 specifically to prevent this pattern.

**Why it happens:**
Claude Max provides unlimited tokens through Claude Code but the same usage through the API would cost $1,000+/month. Anthropic actively enforces this economic boundary. Third-party tools that spoofed Claude Code's client were blocked. The Agent SDK explicitly requires API key authentication — it will not accept Claude Max subscription billing.

**How to avoid:**
- The heartbeat agent MUST run via Claude Code's native interface (terminal subprocesses calling `claude` CLI) or via official Claude API with a paid API key.
- Do NOT use Agent SDK or any library that uses Claude Max's OAuth token programmatically.
- The compliant pattern: Windows Task Scheduler invokes a shell script, which calls `claude --headless ...` or similar official CLI entry points.
- If you need programmatic API access beyond what Claude Code CLI supports, budget for an API key separately (different cost from Max subscription).
- Review the current ToS before building the heartbeat: https://support.claude.com/en/articles/11145838-using-claude-code-with-your-pro-or-max-plan

**Warning signs:**
- Any library that says it "uses your Claude subscription" and is not Anthropic-official.
- Using OAuth tokens extracted from Claude's browser session in Python code.
- Agent SDK or similar SDK initialized without an explicit API key.

**Phase to address:** Phase 3 (Heartbeat agent). Must be designed around ToS constraints from the start.

---

### Pitfall 3: Embedding Dimension Lock-In — Schema Baked at Wrong Dimensions

**What goes wrong:**
The `brain.memories` table is created with `embedding vector(768)` based on one model's output. Later, when switching embedding models (or when text-embedding-004 is deprecated for text-embedding-005), the new model produces 768 or 1536 dimensions and every INSERT fails with `expected 768 dimensions, not 768` or a cryptic error about wrong dimensions. Rebuilding the column requires reprocessing every stored memory.

**Why it happens:**
pgvector columns are typed with a fixed dimension at creation time (`vector(N)`). text-embedding-004 outputs 768-dimensional vectors. text-embedding-005 (the replacement as of November 2025) may output different dimensions. Switching models mid-flight requires an ALTER TABLE and full re-embedding of all stored content — expensive and disruptive.

**How to avoid:**
- Verify Google text-embedding-005's exact output dimensions before writing the schema. (text-embedding-004 = 768 dims; text-embedding-005 = also 768 dims, but verify.)
- Store the model name and output dimension in a `brain.embedding_config` metadata table. This makes future migrations discoverable.
- Use HNSW index (not IVFFlat) — HNSW handles schema changes and live inserts without needing rebuild.
- Add a migration path note in the schema: "if changing embedding model, run `ALTER TABLE brain.memories ALTER COLUMN embedding TYPE vector(NEW_DIM)` after full re-embedding."

**Warning signs:**
- Errors like `ERROR: expected N dimensions, not M` on INSERT.
- Queries returning zero results after a model change.
- HNSW index not being used (visible in `EXPLAIN ANALYZE`).

**Phase to address:** Phase 1 (Brain schema definition). Dimension must be locked before any data is inserted.

---

### Pitfall 4: ChromaDB to pgvector API Mismatch — Not a Drop-in Replacement

**What goes wrong:**
Promaia uses ChromaDB's Python client (`collection.add()`, `collection.query()`, `collection.get()`). pgvector has no equivalent Python client — it's a SQL extension. All vector operations become raw SQL queries or ORM calls. Every caller of the vector store must be rewritten, not just the storage layer. Code that worked with `results = collection.query(query_embeddings=..., n_results=10)` must become `SELECT ... ORDER BY embedding <-> $1 LIMIT 10`.

**Why it happens:**
Developers assume "replacing the vector database" means swapping a configuration line. ChromaDB is a standalone service with a Python SDK. pgvector is a Postgres extension — it has no Python SDK. The query interface is SQL, not an object API. This touches every code path that does retrieval, not just the storage initialization.

**How to avoid:**
- Audit every use of `chromadb` in Promaia before writing a single line of pgvector code. (`grep -r "chromadb" --include="*.py"` in the repo.)
- Build a `VectorStore` abstraction class that has identical method signatures to what Promaia currently uses, with ChromaDB and pgvector backends. This lets you swap without touching callers.
- Export all ChromaDB data to JSON before deleting ChromaDB. ChromaDB migrations between major versions are notoriously fragile.
- Test on a copy of production data — ChromaDB's JSON export has edge cases with empty collections and null embeddings.

**Warning signs:**
- Any file importing `chromadb` that isn't the storage adapter layer.
- Search returning empty results after migration (dimension mismatch or wrong index type).
- `collection.query()` calls that weren't wrapped behind an interface.

**Phase to address:** Phase 1 (Storage migration). Abstraction layer must be built before migration begins.

---

### Pitfall 5: SQLite Parameter Style Breaking Postgres Queries

**What goes wrong:**
SQLite uses `?` as the parameter placeholder (`WHERE id = ?`). PostgreSQL uses `$1, $2, ...` (`WHERE id = $1`). The daughter's existing codebase was built against SQLite. When the `PostgresDB` branch is used as the base, some queries may already be converted. But any new SQL written referencing the old style will fail with `syntax error at or near "?"` in Postgres — silently working in tests that still hit SQLite.

**Why it happens:**
If the test suite still runs against SQLite (fast, no config), bugs in postgres-targeted code are invisible until you run the full integration test against Supabase. This is especially dangerous in a fork where you're extending code you didn't write and can't fully audit before starting.

**How to avoid:**
- Before writing any SQL: run `grep -r "= ?" --include="*.py"` across the entire repo. Document every location.
- Make Supabase the default test target from day one. No SQLite fallback for any code path that touches the database.
- In `zbrain` branch, never add test fixtures that use SQLite. All tests hit a Supabase test schema.
- Add a linter rule or pre-commit hook that rejects `?` placeholders in `.py` files.

**Warning signs:**
- Tests passing locally but queries failing against Supabase.
- `psycopg2.ProgrammingError: syntax error at or near "?"` in logs.
- Boolean columns behaving strangely (SQLite stores 0/1, Postgres uses true/false).

**Phase to address:** Phase 1 (Postgres migration). Catch all before building any new features on top.

---

### Pitfall 6: Heartbeat Agent Token Runaway — No Budget Ceiling

**What goes wrong:**
The heartbeat agent runs overnight, processes stale projects, extracts actions, generates briefings. If there is no per-run token budget, a single run against a large memory corpus can consume hours of context processing. At scale, an agent loop with a bug (infinite retry, cascading context, recursive summarization) can exhaust rate limits or generate massive unexpected API costs.

**Why it happens:**
Autonomous agents that "do as much as needed" don't naturally stop. A "process all stale projects" loop with no limit will process all 15+ projects in one run. A bug in action extraction that triggers a retry loop won't stop until rate limited. Claude Max has rate limits but does not have per-script cost visibility.

**How to avoid:**
- Implement hard limits per heartbeat run: max tokens consumed, max API calls, max wall-clock seconds. Kill the process if any limit is exceeded.
- Use a risk-tier model: low-risk operations (read, summarize) run automatically; medium-risk operations (write to brain schema, generate directives) log but don't execute without confirmation; high-risk operations (send messages, create calendar events) never run autonomously in v1.0.
- Log every API call with timestamp, model used, approximate token count to a `brain.heartbeat_log` table.
- Windows Task Scheduler: set task timeout. Never let it run indefinitely.
- Start with a single project scope per night. Expand only after proven safe.

**Warning signs:**
- Heartbeat logs showing >20 minutes runtime.
- `brain.heartbeat_log` growing faster than expected.
- Duplicate memories being inserted (sign of retry loop).
- Claude Code rate limit errors appearing in morning logs.

**Phase to address:** Phase 3 (Heartbeat agent). Budget and kill switches must be in the initial implementation, not retrofitted.

---

### Pitfall 7: Upstream Codebase Drift — Merge Conflict Accumulation

**What goes wrong:**
Zack works on `zbrain` branch. Daughter continues development on `feature/agent-scheduler` (the default branch). Over weeks, `zbrain` diverges significantly. When it's time to sync upstream changes (new connectors, agent fixes, schema changes), the merge is massive and conflicting. The daughter's scheduler conflicts with the heartbeat agent. Her schema migrations conflict with the brain schema additions. A full merge takes days or becomes impossible.

**Why it happens:**
"I'll sync upstream later" is a trap. Every week of divergence adds a day of merge work. When both branches modify `__init__.py`, `database.py`, or `config.py`, conflicts are guaranteed. Working on a living codebase that you don't control means the merge window is always closing.

**How to avoid:**
- Sync `zbrain` from the upstream default branch at minimum weekly. `git fetch upstream && git rebase upstream/feature/agent-scheduler` at the start of each work session.
- Use `rebase` not `merge` to keep `zbrain` history linear and conflicts small.
- Keep changes to existing Promaia files minimal. If a file must be changed, prefer adding new functions over modifying existing ones.
- The `brain.*` schema strategy is correct — it isolates zBrain's database work entirely from Promaia's `public.*` tables. Protect this boundary aggressively.
- Communicate with daughter before touching shared files: `database.py`, `config.py`, `models.py`, any connector base class.

**Warning signs:**
- Running `git log --oneline upstream/feature/agent-scheduler..zbrain` and seeing more than 20 commits since last sync.
- Daughter's branch has new connector or agent code that wasn't in your base.
- Config files have been refactored upstream.

**Phase to address:** Every phase. Establish sync cadence in Phase 1. Never let it slip.

---

### Pitfall 8: IVFFlat Index on Empty Table — Silent Recall Degradation

**What goes wrong:**
The brain schema is created, IVFFlat index is added immediately on the empty `brain.memories` table, data is inserted over time. Vector search returns irrelevant or zero results even for obvious queries. The index was built with no data, so the internal cluster centers are meaningless. All vectors hash to the same cluster. Recall is catastrophically low but no error is thrown.

**Why it happens:**
IVFFlat builds cluster centers at index creation time based on the data present. An empty table means all clusters are initialized randomly. This is a well-documented pgvector pitfall but easy to miss because the SQL creates without error and queries "work" (return something).

**How to avoid:**
- Use HNSW index, not IVFFlat. HNSW builds incrementally as data is inserted, has no "populate first" requirement, and doesn't need rebuilding when data distribution changes. Supabase's own documentation recommends HNSW.
- `CREATE INDEX ON brain.memories USING hnsw (embedding vector_cosine_ops)` — create this immediately on table creation, before any data.
- If IVFFlat is ever used (it shouldn't be), only create it after inserting at least 1000 rows.

**Warning signs:**
- Vector search returning results that seem unrelated to the query.
- `EXPLAIN ANALYZE` showing seq scan instead of index scan.
- All vectors appearing in the same "cluster" during debugging.

**Phase to address:** Phase 1 (Brain schema). Index type decision is final at table creation.

---

### Pitfall 9: Custom Schema Not Exposed in Supabase Data API

**What goes wrong:**
`brain.*` schema is created, tables are populated, but the Supabase client (JavaScript or Python using the REST API) returns "relation does not exist" or 404 errors. The Supabase Data API (PostgREST) only exposes the `public` schema by default. The `brain` schema exists in Postgres but is invisible to the REST layer.

**Why it happens:**
Supabase's PostgREST layer requires explicit schema exposure. It's not automatic for non-`public` schemas. Additionally, RLS (Row Level Security) policies default to `DENY ALL` for new tables, so even with the schema exposed, queries return empty results or permission errors without explicit policies.

**How to avoid:**
- Go to Supabase Dashboard → Project Settings → Data API → Exposed Schemas. Add `brain`.
- Alternatively, use direct database connections (not the Supabase REST client) for all brain operations from Python. This bypasses PostgREST entirely and avoids the schema exposure issue.
- For every new table in `brain.*`, explicitly set RLS policy or disable RLS for service-role access. Document which tables have RLS enabled.
- Do not mix Supabase REST client and direct Postgres connection in the same code path without documentation.

**Warning signs:**
- `pgrst116: The schema must be one of the following: public` error from Supabase client.
- Empty results from Python code when rows definitely exist (RLS silently filtering).
- Dashboard showing table data but Python client returning nothing.

**Phase to address:** Phase 1 (Brain schema). Set up schema exposure and access patterns before writing any application code.

---

### Pitfall 10: Google text-embedding-004 Deprecation Mid-Project

**What goes wrong:**
The embedding schema is built around `text-embedding-004` (768 dimensions). Google deprecated text-embedding-004 on November 18, 2025. If this project is being built now (March 2026), any code using `text-embedding-004` is calling a discontinued model. Requests may still succeed (Google often maintains deprecated endpoints temporarily) but will eventually break with no warning.

**Why it happens:**
PROJECT.md specifies `text-embedding-004` as the embedding model. As of the research date (March 2026), this model is past its deprecation date. text-embedding-005 is the current recommended model.

**How to avoid:**
- Verify text-embedding-004 availability before writing any embedding code. Call the API with a test string and check the response.
- If 004 is unavailable, use text-embedding-005 (likely same 768-dim output, but verify).
- Store the model name in `brain.embedding_config` so a future model swap is a one-row UPDATE + re-embedding job, not a code rewrite.
- Never hardcode model names in embedding calls. Use a config constant: `EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-005")`.

**Warning signs:**
- `404 Not Found` or `Model not found` errors from Google Generative AI API.
- Zero embeddings inserted into brain tables.

**Phase to address:** Phase 0 / Phase 1 setup. Verify before writing schema.

---

### Pitfall 11: Windows Task Scheduler Path Context — Heartbeat Silently Does Nothing

**What goes wrong:**
The heartbeat script is scheduled in Windows Task Scheduler and shows as "running successfully" (exit code 0). But nothing is logged, no memories are inserted, no briefing is generated. The script runs in a different working directory than expected, cannot find `.env` files, uses the wrong Python interpreter, or fails to import modules — all silently, because Python catches the exception and the Task Scheduler sees exit code 0.

**Why it happens:**
Task Scheduler does not inherit the interactive user's environment. The working directory is often `C:\Windows\System32` unless explicitly set. Relative paths like `./config.py` or `../.env` resolve to wrong locations. The `python` command resolves to a different interpreter than the venv. If the script has a try/except that swallows errors and exits 0, Task Scheduler reports success regardless.

**How to avoid:**
- Always set "Start in" to the absolute path of the project directory in Task Scheduler.
- Use absolute path to the Python interpreter: `C:\Users\Zachary Turner\dev\promaia\.venv\Scripts\python.exe`
- Load `.env` using an absolute path in the script: `load_dotenv(Path(__file__).parent / ".env")`
- Write a heartbeat log entry as the FIRST action in the script (before any imports or config loading that could fail). If this entry exists in the morning, the script started. If not, Task Scheduler never ran it.
- Exit with non-zero exit code on failure. Task Scheduler will record it.

**Warning signs:**
- Task history shows "Task completed (0x0)" but no records in `brain.heartbeat_log`.
- Morning briefing not generated despite scheduled task showing success.
- No error emails or alerts (means alerting code never ran, not that nothing went wrong).

**Phase to address:** Phase 3 (Heartbeat agent). Must be part of the initial heartbeat design.

---

## Technical Debt Patterns

Shortcuts that seem reasonable but create long-term problems.

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Using direct Postgres connection for everything (skip pooler) | Simpler config, no prepared statement issues | Connection limit exhaustion when heartbeat + CLI + any background process all run simultaneously; Supabase Pro limit is 60 direct connections | Acceptable for v1.0, document and revisit at v1.1 |
| Hardcoding model names (claude-sonnet-4-6, gemini-2.0-flash) | Faster to build | Model deprecation breaks code silently; version-pinned models cost more as newer models are cheaper | Never — use config constants always |
| Single `zbrain` branch (no feature branches) | Simple workflow | If a feature partially breaks upstream compatibility, you can't cherry-pick; daughter must accept the whole branch | Acceptable only if features are small and frequent syncs happen |
| Skipping RLS on brain tables | Simpler access | Any compromised credential exposes all brain data | Never — add service-role access pattern from day one |
| Running IVFFlat instead of HNSW | Marginally faster at scale | Built on empty table = broken recall; need to rebuild when data grows | Never — use HNSW |
| Storing raw conversation transcripts in brain schema | Easier ingestion | Privacy risk; also grows unboundedly; Postgres is not a log store | Only if TTL and size limits are implemented from the start |

---

## Integration Gotchas

Common mistakes when connecting to external services.

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| Supabase (pooler) | Pointing asyncpg at port 6543 without disabling prepared statements | Use port 5432 (direct) for Python processes; set `statement_cache_size=0` if pooler is required |
| Supabase (schema) | Using PostgREST client for `brain.*` tables without exposing schema | Use direct psycopg2/asyncpg connection from Python; expose schema in dashboard for any REST calls |
| Google Generative AI | Calling `embed_content` without rate limiting; the function internally uses batch endpoint with a separate rate limit | Add retry with exponential backoff; batch in groups of ≤100; track RPM |
| Google Generative AI | Using text-embedding-004 (deprecated Nov 2025) | Verify current model name before each project phase; use config constant not hardcoded string |
| Claude Code CLI (heartbeat) | Spawning Claude subprocesses without timeout | Always set subprocess timeout; kill on exceeded wall-clock time |
| Anthropic API | Using Agent SDK with Claude Max OAuth token | Agent SDK requires API key; Max OAuth is only valid inside Claude Code CLI |
| Windows Task Scheduler | Using relative paths, default Python, default working directory | Absolute paths to interpreter and start directory; test in cmd.exe first |

---

## Performance Traps

Patterns that work at small scale but fail as usage grows.

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Re-embedding all content on every heartbeat run | First few runs fine, then 30min+ runtimes | Incremental embedding: only embed new/changed content; track `last_embedded_at` | After ~100 memories |
| Full table scan for similar memories (no index) | Sub-second locally, 10+ seconds against Supabase | HNSW index created at table creation, `EXPLAIN ANALYZE` every query in development | After ~500 rows |
| Fetching all memories into Python, filtering in-app | Works with 50 memories, OOM with 5000 | All filtering in SQL; never `SELECT * FROM brain.memories` without LIMIT | After ~1000 rows |
| Generating briefing by reading entire message history | Single session fine; briefing degrades after 6 months | Time-bounded lookups: `WHERE created_at > NOW() - INTERVAL '30 days'` | After ~3 months of use |
| Model routing with no fallback timeout | One slow model call blocks entire pipeline | Per-model timeout with fallback; never await indefinitely | On first network hiccup |
| Storing both raw text and embedding in brain.memories without size cap | Fine for first 100 notes | Postgres row size balloons; embedding alone is 3KB per row (768 floats × 4 bytes) | After ~50K memories |

---

## Security Mistakes

Domain-specific security issues beyond general web security.

| Mistake | Risk | Prevention |
|---------|------|------------|
| Supabase service role key in Python files or dotenv committed to git | Full database access exposed; Heatpup's 37+ tables at risk, not just brain schema | `.env` in `.gitignore` verified before first commit; separate service role per project if Supabase supports it |
| Brain memories contain private data (voice notes, personal projects) accessible via public schema | If daughter's app inadvertently queries across schemas, personal data leaks | `brain.*` schema never cross-referenced in Promaia's `public.*` queries; RLS policy on brain tables |
| Heartbeat agent credentials (API keys, Supabase URL) in scheduled task command line | Visible in Windows Task Scheduler UI and Event Viewer logs | Load all credentials from `.env` file; never pass secrets as CLI arguments |
| Claude prompts containing Supabase credentials for database operations | Prompt injection can expose or modify credentials | Never include connection strings in prompts; use tool calls with pre-configured connections only |
| Gemini API key shared between Promaia (daughter's app) and zBrain | Key rotation or exhaustion in one project breaks both | Separate API keys per project; zBrain uses Zack's Google AI Premium, Promaia uses separate key |

---

## UX Pitfalls

Common user experience mistakes in this domain.

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| Morning briefing generates but Zack never reads it | Memory system doesn't actually solve AI amnesia | Briefing must arrive via iPhone (push or claude.ai); passive file generation is ignored |
| Briefing is too long (>500 words) | Skimmed or skipped while driving | Hard cap briefing at 3-5 bullet points per domain; details on demand |
| Heartbeat runs but Zack can't tell if it worked | Trust degrades; stops relying on the system | One-line status summary always visible: last run time, memories added, actions pending |
| Action extraction creates actions Zack never committed to | False urgency, system loses credibility | Mark extracted actions as "suggested" until explicitly confirmed; never auto-promote to active |
| Multi-model routing is invisible | Zack doesn't know if Claude or Gemini answered | Log model used per response; show in briefings ("Gemini processed 3 of 5 tasks") |

---

## "Looks Done But Isn't" Checklist

Things that appear complete but are missing critical pieces.

- [ ] **Postgres migration:** Often missing — all ChromaDB callers updated, not just storage init. Verify: `grep -r "chromadb" --include="*.py"` returns zero results.
- [ ] **Brain schema:** Often missing — HNSW index actually created (not just planned). Verify: `\d+ brain.memories` in psql shows index.
- [ ] **Heartbeat agent:** Often missing — actual kill switch / timeout implemented (not just documented). Verify: Run heartbeat with a deliberately slow API call and confirm it terminates.
- [ ] **Supabase connection:** Often missing — tested against actual Supabase, not just local Postgres. Verify: Run test query from the production connection string.
- [ ] **ToS compliance:** Often missing — heartbeat invocation method is actually via Claude Code CLI, not via Agent SDK or OAuth spoofing. Verify: Check no OAuth token extraction occurs in the codebase.
- [ ] **Schema exposure:** Often missing — `brain` schema added to Supabase's exposed schemas list. Verify: Test a PostgREST call to `brain.memories` returns data, not 404.
- [ ] **Embedding model:** Often missing — verified text-embedding-005 (or current model) is available and dimensions confirmed. Verify: Make a test embedding call and print `len(result.embeddings[0].values)`.
- [ ] **Upstream sync:** Often missing — `zbrain` branch has been rebased on latest upstream within the last week. Verify: `git log --oneline HEAD..upstream/feature/agent-scheduler` returns nothing.
- [ ] **Gemini routing:** Often missing — fallback behavior when Gemini is unavailable is tested. Verify: Simulate a Gemini API error and confirm Claude handles the task without crashing.

---

## Recovery Strategies

When pitfalls occur despite prevention, how to recover.

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| asyncpg prepared statement errors on Supabase | LOW | Switch connection string to port 5432 (direct); restart Python process; no data loss |
| Embedding dimension mismatch after model change | HIGH | 1) Add new column `embedding_v2 vector(NEW_DIM)`. 2) Re-embed all rows into new column. 3) Swap column names. 4) Rebuild HNSW index. Expect 2-4 hours of work. |
| ChromaDB migration broke retrieval | MEDIUM | Keep ChromaDB running in parallel behind the abstraction layer; switch retrieval back to ChromaDB flag; debug pgvector in isolation |
| Heartbeat ran away (many API calls, possible data pollution) | MEDIUM | 1) Disable Task Scheduler task immediately. 2) Audit `brain.heartbeat_log` for what ran. 3) Delete suspicious memories by `source = 'heartbeat' AND created_at > [runaway_start]`. 4) Fix budget ceiling before re-enabling. |
| `zbrain` branch unmergeable with upstream | HIGH | 1) Create new branch from latest upstream. 2) Cherry-pick zbrain commits that don't conflict. 3) Manually reapply conflicting changes. Plan for 1-2 days. Prevent by weekly rebases. |
| Supabase Heatpup tables affected by brain schema migration | CRITICAL | Brain schema (`brain.*`) never touches `public.*`. If this happens, a migration script ran against wrong schema. Restore from Supabase backup (Pro plan includes PITR). |
| ToS violation discovered (wrong Claude access method) | MEDIUM | Swap invocation method to compliant Claude Code CLI subprocess; no API key needed; heartbeat functionality preserved |

---

## Pitfall-to-Phase Mapping

How roadmap phases should address these pitfalls.

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| asyncpg + Supabase pooler incompatibility | Phase 1: Postgres/Supabase setup | Test query against Supabase connection string succeeds; check port in connection config |
| Anthropic ToS violation in heartbeat | Phase 3: Heartbeat agent design | Code review confirms no OAuth extraction; invocation uses `claude` CLI subprocess or API key |
| Embedding dimension lock-in | Phase 1: Brain schema definition | `brain.embedding_config` table exists; model name is a config constant; test embedding call dimension printed |
| ChromaDB API mismatch (not drop-in) | Phase 1: Storage migration | `grep -r "chromadb"` returns zero in non-adapter files |
| SQLite parameter style (`?` placeholders) | Phase 1: Pre-migration audit | `grep -r "= ?" --include="*.py"` returns zero |
| Heartbeat token runaway | Phase 3: Heartbeat initial implementation | Budget ceiling and kill switch tested; heartbeat log shows per-run token counts |
| Upstream codebase drift | Phase 0: Branch setup + every phase | Weekly rebase confirmed in work log; no more than 20 unsynced upstream commits |
| IVFFlat on empty table | Phase 1: Brain schema definition | `\d+ brain.memories` shows HNSW index; IVFFlat never appears in migration files |
| Brain schema not exposed in Supabase | Phase 1: Supabase configuration | PostgREST call to `brain.*` endpoint succeeds |
| text-embedding-004 deprecation | Phase 0/1 setup | Test API call to current model succeeds; model name is config constant not hardcoded |
| Windows Task Scheduler path issues | Phase 3: Heartbeat agent | Heartbeat log entry written as first action; morning after first scheduled run, log entry exists |
| Upstream files in Heatpup affected | Ongoing | Brain schema migrations never reference `public.*`; reviewed before each migration run |

---

## Sources

- [Supabase: Pooling and asyncpg incompatibility (Medium)](https://medium.com/@patrickduch93/supabase-pooling-and-asyncpg-dont-mix-here-s-the-real-fix-44f700b05249)
- [Supabase GitHub Issue: asyncpg prepared statement errors](https://github.com/supabase/supabase/issues/39227)
- [Supabase Docs: Connecting to Postgres](https://supabase.com/docs/guides/database/connecting-to-postgres)
- [Supabase Docs: HNSW Indexes](https://supabase.com/docs/guides/ai/vector-indexes/hnsw-indexes)
- [Supabase Docs: pgvector extension](https://supabase.com/docs/guides/database/extensions/pgvector)
- [Anthropic: Using Claude Code with Pro/Max plan](https://support.claude.com/en/articles/11145838-using-claude-code-with-your-pro-or-max-plan)
- [Anthropic ToS changes 2025: aihackers.net](https://aihackers.net/posts/anthropic-tos-changes-2025/)
- [TechCrunch: Anthropic rate limits Claude Code](https://techcrunch.com/2025/07/28/anthropic-unveils-new-rate-limits-to-curb-claude-code-power-users/)
- [ChromaDB migration horror story: When ChromaDB Mutates](https://wwakabobik.github.io/2025/11/migrating_chroma_db/)
- [pgvector GitHub: vector from ChromaDB import](https://github.com/pgvector/pgvector/issues/537)
- [pgvector vs ChromaDB comparison (Elestio)](https://blog.elest.io/pgvector-vs-chromadb-when-to-extend-postgresql-and-when-to-go-dedicated/)
- [DEV: Resolving vector dimension mismatches](https://dev.to/hijazi313/resolving-vector-dimension-mismatches-in-ai-workflows-47m)
- [SQLite to PostgreSQL migration gotchas (Bytebase)](https://www.bytebase.com/blog/database-migration-sqlite-to-postgresql/)
- [Migrating from SQLite to PostgreSQL (masteringpostgres.com)](https://masteringpostgres.com/articles/migrating-from-sqlite-to-postgresql)
- [Agentic cost control: token runaway prevention](https://www.alpsagility.com/cost-control-agentic-systems)
- [Agentic AI safety playbook 2025](https://dextralabs.com/blog/agentic-ai-safety-playbook-guardrails-permissions-auditability/)
- [Google Generative AI: batch embed rate limit issue](https://github.com/googleapis/python-genai/issues/427)
- [Google Gemini API rate limits](https://ai.google.dev/gemini-api/docs/rate-limits)
- [Windows Task Scheduler Python gotchas (ESRI)](https://support.esri.com/en-us/knowledge-base/windows-task-scheduler-will-not-run-a-python-script-146-000012657)
- [GitHub Blog: Friendly fork management strategies](https://github.blog/2022-05-02-friend-zone-strategies-friendly-fork-management/)

---
*Pitfalls research for: zBrain — adding cloud Postgres/pgvector, proactive AI brain, autonomous heartbeat agents, and multi-model routing to Promaia fork*
*Researched: 2026-03-04*
