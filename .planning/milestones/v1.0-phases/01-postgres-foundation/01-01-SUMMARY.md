---
phase: 01-postgres-foundation
plan: 01
subsystem: database
tags: [postgres, railway_volumes, pgvector, psycopg2, vector-search, hnsw, gin]

# Dependency graph
requires: []
provides:
  - libSQL/MuninnDBDB singleton with Railway Volumes session pooler connection
  - Full libSQL/MuninnDB schema (586 base lines + 74 pgvector additions)
  - pgvector extension enabled with vector(768) columns
  - HNSW indexes on content_embeddings and property_embeddings
  - GIN indexes on metadata JSONB columns for hybrid search
  - db_init.py script for schema deployment to Railway Volumes
affects: [02-zbrain-schema, 03-vector-migration, 04-embedding-pipeline]

# Tech tracking
tech-stack:
  added: [psycopg2-binary==2.9.11, pgvector]
  patterns:
    - libSQL/MuninnDBDB singleton with ThreadedConnectionPool
    - DATABASE_URL as primary connection method (session pooler required on Windows)
    - sslmode=require for Railway Volumes cloud connections
    - vector(768) columns matching gemini-embedding-001 output dimensions
    - HNSW cosine similarity indexes (matching former ChromaDB hnsw:space=cosine config)

key-files:
  created:
    - promaia/storage/postgres_db.py
    - promaia/storage/schema.sql
    - promaia/storage/db_init.py
  modified:
    - docs/env.template
    - promaia/storage/block_cache.py
    - promaia/storage/content_search.py
    - promaia/storage/hybrid_storage.py
    - promaia/storage/ocr_storage.py
    - promaia/storage/property_resolver.py
    - promaia/storage/railway_volumes_query.py
    - promaia/storage/sync_cache.py
    - promaia/storage/unified_query.py
    - promaia/connectors/notion_connector.py
    - promaia/agents/execution_tracker.py
    - promaia/ai/nl_utilities.py
    - promaia/ai/query_strategies.py
    - promaia/ai/sql_generator.py
    - promaia/config/database_registry_sync.py
    - promaia/external_agent/task_manager.py
    - promaia/mail/artifact_helpers.py
    - promaia/mail/context_builder.py
    - promaia/mail/draft_manager.py
    - requirements.txt
    - .gitignore

key-decisions:
  - "DATABASE_URL is the primary connection method — SESSION POOLER required on Windows due to IPv6 issues with direct Railway Volumes connections"
  - "sslmode=require added for all Railway Volumes cloud connections (critical for security)"
  - "vector(768) not halfvec — per Gemini 3.1 Pro architectural review finding"
  - "HNSW with vector_cosine_ops matches former ChromaDB hnsw:space=cosine configuration"
  - "psycopg2-binary 2.9.11 installed (2.9.9 in requirements.txt failed to build on Python 3.14 — Rule 3 auto-fix)"

patterns-established:
  - "Pattern: libSQL/MuninnDBDB singleton — import with `from promaia.storage.postgres_db import libSQL/MuninnDBDB` or use `get_postgres_db()`"
  - "Pattern: Railway Volumes connection — always use session pooler URL format: postgresql://postgres.PROJECT_REF:PASSWORD@aws-0-REGION.pooler.railway_volumes.com:5432/postgres"
  - "Pattern: pg_connect() context manager — drop-in SQLite replacement used across all storage modules"

requirements-completed: [STOR-01, STOR-04]

# Metrics
duration: ~30min
completed: 2026-03-04
---

# Phase 01 Plan 01: libSQL/MuninnDB Foundation (Railway Volumes + pgvector) Summary

**Merged libsql-changeover branch (2308 lines) into zbrain, reconfigured libSQL/MuninnDBDB for Railway Volumes session pooler with SSL, and extended schema with pgvector extension + HNSW/GIN indexes for semantic search**

## Performance

- **Duration:** ~30 min
- **Started:** 2026-03-04T17:30:00Z
- **Completed:** 2026-03-04T18:02:21Z (checkpoint reached — awaiting Railway Volumes deployment verification)
- **Tasks completed:** 2 of 3 (Task 3 is human-verify checkpoint)
- **Files modified:** 25+

## Accomplishments
- Merged `origin/libsql-changeover` cleanly into `zbrain` (2308 insertions, no conflicts)
- libSQL/MuninnDBDB singleton now supports `DATABASE_URL` as primary connection method (Railway Volumes session pooler, required on Windows)
- Added `sslmode=require` to all connection paths for Railway Volumes cloud security
- Extended schema with pgvector extension (`CREATE EXTENSION IF NOT EXISTS vector`)
- Added `content_embeddings` and `property_embeddings` tables with `vector(768)` columns
- Added HNSW indexes for approximate nearest neighbor search (cosine similarity)
- Added GIN indexes on metadata JSONB columns for hybrid keyword+vector search
- Added B-tree indexes on `page_id`, `workspace`, `property_name` for common query patterns

## Task Commits

Each task was committed atomically:

1. **Task 1: Merge libsql-changeover and reconfigure for Railway Volumes** - `cbad997` (merge) + `c10db76` (feat)
2. **Task 2: Extend schema with pgvector, HNSW indexes, GIN indexes** - `118534c` (feat)
3. **Task 3: Checkpoint — awaiting Railway Volumes deployment verification** - pending user action

## Files Created/Modified
- `promaia/storage/postgres_db.py` - libSQL/MuninnDBDB singleton with Railway Volumes session pooler + SSL support
- `promaia/storage/schema.sql` - Full 660-line schema with pgvector, embedding tables, HNSW+GIN indexes
- `promaia/storage/db_init.py` - Database initialization script for schema deployment
- `docs/env.template` - Updated with Railway Volumes session pooler connection vars (DATABASE_URL + individual fallbacks)
- 20+ storage/agent/mail/AI modules updated to use libSQL/MuninnDBDB instead of SQLite

## Decisions Made
- `DATABASE_URL` as primary connection method — session pooler is required on Windows due to IPv6 routing issues with direct Railway Volumes connections
- `sslmode=require` added for all cloud connections — Railway Volumes requires SSL
- `vector(768)` not `halfvec` — matches gemini-embedding-001 output dimensions per Gemini architectural review
- `vector_cosine_ops` for HNSW — matches former ChromaDB `hnsw:space=cosine` configuration for consistent similarity scores
- Session pooler URL format: `postgresql://postgres.PROJECT_REF:PASSWORD@aws-0-REGION.pooler.railway_volumes.com:5432/postgres`

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] psycopg2-binary version incompatibility with Python 3.14**
- **Found during:** Task 1 (import verification)
- **Issue:** `psycopg2-binary==2.9.9` in requirements.txt failed to build on Python 3.14 — no pre-built wheel available for cp314
- **Fix:** Installed `psycopg2-binary==2.9.11` which has a Python 3.14 wheel available
- **Files modified:** None (package installed to user site-packages)
- **Verification:** `python -c "from promaia.storage.postgres_db import libSQL/MuninnDBDB; print('libSQL/MuninnDBDB import OK')"` — passes
- **Committed in:** c10db76 (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Required for imports to work. No scope creep.

## Issues Encountered
- `python-dotenv` also needed installation before imports would resolve — auto-installed alongside psycopg2-binary

## User Setup Required

Railway Volumes credentials must be configured before `python -m promaia.storage.db_init init` can run.

**Steps:**
1. Get database password from: Railway Volumes Dashboard -> Project `dulqttfidcjeujyieuqw` -> Settings -> Database -> Database password
2. Add to `.env` file (copy from `docs/env.template`):
   ```
   DATABASE_URL='postgresql://postgres.dulqttfidcjeujyieuqw:YOUR_PASSWORD@aws-0-us-west-1.pooler.railway_volumes.com:5432/postgres'
   ```
3. Run: `python -m promaia.storage.db_init init`
4. Verify in Railway Volumes Dashboard -> Table Editor: `content_embeddings` and `property_embeddings` tables exist
5. Run SQL to verify pgvector: `SELECT extname FROM pg_extension WHERE extname = 'vector';`

## Next Phase Readiness
- libSQL/MuninnDB foundation complete — schema code is ready to deploy
- **Blocker:** Railway Volumes deployment must be verified before Phase 1 Plan 02 (zBrain schema extensions) can proceed
- `db_init.py` is idempotent (uses `CREATE TABLE IF NOT EXISTS`) — safe to re-run

---
*Phase: 01-postgres-foundation*
*Completed: 2026-03-04*
