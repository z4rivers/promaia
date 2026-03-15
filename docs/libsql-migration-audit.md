# libSQL Migration Audit — 2026-03-15

Full codebase audit of the Postgres-to-libSQL migration. Found **30+ issues** across 20 files.
The brain MCP server was running against broken schemas for ~9 days, causing silent failures
and data written to ghost tables.

---

## CRITICAL — Runtime Crashes / Wrong Data

### 1. `brain_agent_costs` ghost table
**File:** `promaia/agents/cost_tracker.py` (lines 58-224)
- All cost queries use `brain_agent_costs` but the real table is `agent_costs`
- `CREATE TABLE IF NOT EXISTS brain_agent_costs` created a SECOND table
- All agent cost data for the last 9 days went to the ghost table, not the real one
- **Fix:** Replace `brain_agent_costs` with `agent_costs` throughout file

### 2. Postgres `::type` casts in engine.py
**File:** `promaia/brain/engine.py` (lines 176, 218)
- `(payload->>'domain_id')::int` — `::int` is Postgres, SQLite errors
- `(payload->>'cost')::float` — `::float` is Postgres
- **Fix:** Use `CAST(json_extract(payload, '$.domain_id') AS INTEGER)` etc.

### 3. pgvector operator in telegram/brain_ops.py
**File:** `promaia/telegram/brain_ops.py` (line 278)
- `embedding <=> %s::vector AS distance` — pgvector operator, crashes on every call
- Also passes numpy array instead of sqlite-vec blob
- **Fix:** Use `vec_distance_cosine(embedding, ?)` with `struct.pack()` serialized blob

### 4. `memories.asset_paths` column doesn't exist
**Files:** `promaia/brain/core/memory_pipeline.py` (line 73), `promaia/brain/mcp/handlers/capture_ops.py` (line 162)
- INSERT and SELECT reference `asset_paths` — column doesn't exist
- Capture and recall silently fail
- **Fix:** Add column to DB or remove from queries

### 5. `memories.embedding` column doesn't exist
**Files:** `memory_pipeline.py` (lines 96, 176), `capture_ops.py` (line 89), `profile_ops.py` (line 53), `brain_ops.py` (line 278)
- Vector search on `memories` and `profile` references `embedding` column
- Actual embeddings are in `content_embeddings` table
- **Fix:** Join with `content_embeddings` or add `embedding` column

### 6. `profile.embedding` column doesn't exist
**File:** `promaia/brain/mcp/handlers/profile_ops.py` (lines 53, 168)
- SELECT with `vector_distance_cos(embedding, ?)` and UPDATE `embedding` both fail
- **Fix:** Same as above

### 7. Wrong column names in `actions` INSERT
**File:** `promaia/brain/voice_handlers/system_ops.py` (line 83)
- Uses `due_date`, `domain`, `created_at` — none exist on `actions` table
- Actual: `memory_id, domain_id, description, status, extracted_at, completed_at`
- **Fix:** Rewrite INSERT with correct columns, resolve domain name to domain_id

### 8. `conversations.messages` doesn't exist
**File:** `promaia/web/routers/dashboard.py` (line 265)
- `SELECT messages FROM conversations` — column doesn't exist
- Actual schema: per-row messages with `role` and `content` columns
- **Fix:** Query `content` from `conversations WHERE role = 'assistant'`

### 9. `gmail_query` handler queries nonexistent event type
**File:** `promaia/brain/mcp/handlers/gmail_ops.py` (lines 171-191)
- Queries `events WHERE type = 'gmail_email_processed'` — nothing writes this type
- Should query `gmail_content` table directly
- **Fix:** Rewrite to query `gmail_content` columns

### 10. `supabase_query.py` imports nonexistent classes
**File:** `promaia/storage/supabase_query.py` (line 11)
- Imports `PostgresQueryInterface`, `get_postgres_query_interface` from `db_factory`
- These don't exist — crashes on import
- **Fix:** Remove or rewrite module

### 11. Wrong vector function name
**File:** `promaia/brain/mcp/handlers/capture_ops.py` (line 89)
- Uses `vector_distance_cos()` — correct sqlite-vec function is `vec_distance_cosine()`
- **Fix:** Rename to `vec_distance_cosine`

---

## HIGH — Postgres DDL That Fails on Table Creation

### 12. `SERIAL PRIMARY KEY` in block_cache.py and sync_cache.py
**Files:** `promaia/storage/block_cache.py` (line 41), `promaia/storage/sync_cache.py` (line 43)
- `SERIAL` is Postgres-only
- **Fix:** Change to `INTEGER PRIMARY KEY AUTOINCREMENT`

### 13. `JSONB` column type in block_cache.py
**File:** `promaia/storage/block_cache.py` (line 44)
- `JSONB` is Postgres type
- **Fix:** Change to `TEXT`

### 14. `DOUBLE PRECISION` in sync_cache.py and block_cache.py
**Files:** `sync_cache.py` (line 46), `block_cache.py` (line 45)
- Postgres type, SQLite uses `REAL`
- **Fix:** Change to `REAL`

### 15. Incomplete GIN index in hybrid_storage.py
**File:** `promaia/storage/hybrid_storage.py` (line 111)
- `CREATE INDEX ... ON gmail_content` — no column specified
- **Fix:** Add column, e.g., `ON gmail_content(gmail_labels)`

### 16. `NULLS LAST` in hybrid_query.py
**File:** `promaia/storage/hybrid_query.py` (lines 156, 175)
- Postgres-only syntax
- **Fix:** Use `ORDER BY COALESCE(col, '') DESC`

### 17. `to_char()` + `::timestamp` in sql_generator.py
**File:** `promaia/ai/sql_generator.py` (line 400)
- Postgres function and cast
- **Fix:** Use `strftime('%Y-%W', created_time)`

### 18. `schema.sql` is entirely Postgres
**File:** `promaia/brain/schema.sql`
- Full Postgres DDL: `CREATE SCHEMA`, `SERIAL`, `TIMESTAMPTZ`, `JSONB`, `vector(768)`, `TEXT[]`, `USING hnsw`, `USING gin`
- If `db_init.py` runs `apply_brain_schema()`, everything breaks
- **Fix:** Create libSQL-compatible schema or mark as deprecated

---

## MEDIUM — Data Integrity / Logic Issues

### 19. `create_brain_tables_windows.py` is wrong
**File:** `scripts/create_brain_tables_windows.py`
- 12+ column/table mismatches vs actual DB
- `domains` has wrong columns (adds `priority`, misses `description`, `is_project`, `parent_domain`)
- `memories` has `memory_type`, `importance`, `embedding` (none exist)
- `actions` has `domain TEXT`, `content TEXT`, `priority TEXT` (all wrong)
- `conversations` has `messages TEXT` (wrong schema entirely)
- `agent_costs` missing 5 columns
- **Fix:** Complete rewrite from actual `PRAGMA table_info` output

### 20. `ON CONFLICT DO NOTHING` without matching constraint
**File:** `promaia/brain/channels/pc_scan.py` (line 340)
- `ON CONFLICT DO NOTHING` on `memories` — no unique constraint matches
- Creates duplicates every run
- **Fix:** Add existence check or unique constraint

### 21. f-string SQL interpolation
**File:** `promaia/agents/cost_tracker.py` (line 221)
- `f"date('now', '-{days} days')"` — bypasses parameterization
- **Fix:** Use parameterized query

### 22. Brain contexts are stale and scrambled
- All 9 contexts last updated March 6 (9 days ago)
- Domain-description assignments are wrong (zBrain has Promaia's description, etc.)
- **Fix:** Update contexts via `mcp__brain__update_context`

### 23. 10 pending migration actions never completed
- Actions 927-936 in brain are migration tasks, some done but never marked complete
- **Fix:** Audit each, mark completed or delete

---

## LOW — Stale Comments / Cosmetic

### 24. ~8 `PostgresDB` references in docstrings
engine.py, onboarding.py, gmail_read.py, pc_scan.py, memory_pipeline.py

### 25. ~15 `pgvector` references in comments
vector_db.py, brain_ops.py, capture_ops.py, muninn_ops.py

### 26. ~6 `psycopg2` references in comments
block_cache.py, engine.py, libsql_db.py

### 27. ~10 `PostgreSQL` backend name references
block_cache.py, sync_cache.py, hybrid_storage.py, execution_tracker.py, agent_context.py, main.py

### 28. ~6 `JSONB` references in comments
vector_db.py, agent_context.py, channel.py, block_cache.py

### 29. 6 `# psycopg2 removed` cleanup markers
task_manager.py, content_search.py, files.py, conversation.py, brain_ops.py, ocr_storage.py

---

## Files That Passed Clean

These were audited and have correct SQL:
- `promaia/web/routers/dashboard.py` — main queries all correct (actions, contexts, memories, email, profile)
- `promaia/agents/executor.py` — correct columns, correct SQLite syntax
- `promaia/agents/agent_context.py` — correct profile/actions/contexts queries
- `promaia/brain/mcp/handlers/context_ops.py` — correct joins and columns
- `promaia/brain/onboarding.py` — correct (minus docstring)
- `promaia/brain/seed.py` — correct ON CONFLICT usage
- Entry points (`__main__.py`, `cli/`) — clean, no broken imports

---

## Recommended Fix Order

1. **Ghost table** — `brain_agent_costs` → `agent_costs` (data recovery needed)
2. **engine.py** casts — breaks budget checks and cost queries
3. **brain_ops.py** pgvector — breaks Telegram semantic search
4. **system_ops.py** actions INSERT — breaks voice action creation
5. **capture_ops/memory_pipeline** asset_paths + embedding — breaks memory capture
6. **profile_ops** embedding — breaks profile semantic search
7. **dashboard.py** conversations query — breaks Talk page
8. **gmail_ops.py** query — breaks gmail_query MCP tool
9. **DDL files** (block_cache, sync_cache, schema.sql) — breaks fresh table creation
10. **create_brain_tables_windows.py** — complete rewrite from actual schema
11. **Stale comments** — bulk find-replace pass
