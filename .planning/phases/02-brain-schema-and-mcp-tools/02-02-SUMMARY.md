---
phase: 02-brain-schema-and-mcp-tools
plan: 02
subsystem: api
tags: [mcp, gemini, instructor, pgvector, pydantic, brain, zBrain]

# Dependency graph
requires:
  - phase: 02-01
    provides: brain schema (7 tables), engine.py (8 deterministic functions)
provides:
  - Brain MCP server with 7 tools (briefing, capture, search, recall, context, update_context, actions)
  - Action extraction module (instructor + Gemini Flash with fallback)
affects: [03-heartbeat, claude-system-prompt, zbrain-mcp-config]

# Tech tracking
tech-stack:
  added: [instructor>=1.0.0, mcp>=1.26.0 (already in requirements)]
  patterns:
    - MCP Server pattern with @server.list_tools() and @server.call_tool() decorators
    - Lazy-initialized DB/vector singletons (get_db(), get_vector_mgr())
    - register_vector(conn) called per-connection before any pgvector query
    - Two-path extraction: instructor.from_genai() primary, raw Gemini JSON fallback
    - get_or_create_domain_id() for implicit domain creation
    - Idempotent event logging: briefing skips duplicate per session/day

key-files:
  created:
    - promaia/brain/extraction.py
    - promaia/brain/mcp_server.py
  modified:
    - requirements.txt

key-decisions:
  - "instructor fallback path: if instructor.from_genai() fails, fall back to raw Gemini Flash with response_mime_type=application/json + Pydantic model_validate_json()"
  - "Lazy singletons for DB and VectorDBManager: avoids connection pool initialization at import time when MCP server is used in test environments"
  - "Embedding failure in capture is non-fatal: memory row is persisted, embedding update logs a warning and continues"
  - "Briefing event idempotency: check brain.events for same session_id + date before logging — avoids duplicate entries on repeated briefing calls"
  - "get_or_create_domain_id() helper handles implicit domain creation across capture and update_context tools"

patterns-established:
  - "MCP tool handlers: async functions called from @server.call_tool() dispatcher, all wrapped in try/except returning TextContent"
  - "register_vector pattern: called on every db.get_connection() context used for embedding queries (search, capture update)"
  - "Brain SQL pattern: all queries use brain.* schema prefix (brain.memories, brain.domains, brain.contexts, brain.actions, brain.events)"

requirements-completed: [BRAIN-01, BRAIN-04, BRAIN-05, BRAIN-06]

# Metrics
duration: 4min
completed: 2026-03-05
---

# Phase 2 Plan 02: Brain MCP Server and Action Extraction Summary

**MCP server with 7 tools (briefing/capture/search/recall/context/update_context/actions) using pgvector cosine search, instructor-based action extraction from Gemini Flash, and stale-alert briefing over brain.* schema**

## Performance

- **Duration:** 4 min
- **Started:** 2026-03-05T02:14:17Z
- **Completed:** 2026-03-05T02:18:30Z
- **Tasks:** 2/2
- **Files modified:** 3

## Accomplishments

- Action extraction module with dual paths: instructor.from_genai() primary, raw Gemini JSON + Pydantic fallback — never raises on failure
- MCP server exposes exactly 7 tools registered via @server.list_tools() decorator with full input schemas
- Capture flow: insert brain.memories -> generate pgvector embedding (register_vector per-connection) -> extract_actions -> insert brain.actions
- Briefing flow: stale projects (NOW() - last_updated > stale_threshold_days * INTERVAL), pending actions LIMIT 10, heartbeat events last 24h
- Search flow: generate query embedding -> cosine distance via `embedding <=> %s::vector` ORDER BY distance
- All 8 plan verification checks pass

## Task Commits

Each task was committed atomically:

1. **Task 1: Action extraction module** - `15eb7c5` (feat)
2. **Task 2: Brain MCP server with 7 tools** - `d3517b1` (feat)

**Plan metadata:** (final docs commit — see below)

## Files Created/Modified

- `promaia/brain/extraction.py` - Pydantic models (ExtractedAction, ActionExtractionResult) + extract_actions() with instructor/fallback paths
- `promaia/brain/mcp_server.py` - MCP server with 7 tool handlers querying brain.* tables
- `requirements.txt` - Added instructor>=1.0.0

## Decisions Made

- **instructor fallback:** instructor.from_genai() is primary; if it raises (API mismatch), falls back to raw Gemini Flash with response_mime_type="application/json" and Pydantic model_validate_json(). Never raises to caller.
- **Lazy DB singletons:** get_db() and get_vector_mgr() initialized on first tool call, not at import time. Avoids connection pool startup cost when running verification-only tests.
- **Non-fatal embedding failure:** capture tool inserts memory row first, then attempts embedding update. If embedding fails (network, quota), memory is still stored with embedding=NULL. Warning logged.
- **Idempotent briefing events:** briefing checks brain.events for existing 'briefing' type with same session_id + today's date before inserting — prevents duplicate event log on repeated calls.
- **get_or_create_domain_id():** Both capture and update_context use this helper to auto-create brain.domains rows on first reference. No pre-seeding required.

## Deviations from Plan

**1. [Rule 3 - Blocking] Installed mcp package not present in environment**
- **Found during:** Task 2 verification
- **Issue:** `mcp` package was listed in requirements.txt but not installed in the active Python environment, causing ImportError during verification
- **Fix:** Ran `pip install "mcp>=1.26.0"` to install the package
- **Files modified:** None (environment change only — already in requirements.txt)
- **Verification:** Import succeeded, 7 tools verified
- **Committed in:** d3517b1 (Task 2 commit — no file change needed)

**2. [Rule 1 - Bug] asyncio.run(server.list_tools()) is not a coroutine in mcp 1.26.0**
- **Found during:** Task 2 verification
- **Issue:** Plan verification command called `asyncio.run(server.list_tools())` but in mcp 1.26.0 the `list_tools()` method is a decorator factory, not a coroutine. The actual handler is registered in `server.request_handlers`.
- **Fix:** Adapted verification to call the handler directly: `server.request_handlers[ListToolsRequest](req)` — this matches the actual MCP SDK call pattern and correctly returns the tool list.
- **Files modified:** None (verification command adaptation only)
- **Verification:** All 7 tools confirmed present with correct names
- **Committed in:** d3517b1 (Task 2 commit)

---

**Total deviations:** 2 auto-fixed (1 blocking, 1 bug)
**Impact on plan:** Both were environmental/verification adaptations. Core implementation matches plan exactly. No scope creep.

## Issues Encountered

- mcp SDK `list_tools()` API differs from gmail_tools_server.py pattern in one way: the decorator registers a handler, so runtime verification requires calling via `server.request_handlers[ListToolsRequest]` rather than `asyncio.run(server.list_tools())`. All 7 tools confirmed present.

## User Setup Required

None — no new external service configuration required. Uses existing GOOGLE_API_KEY and DATABASE_URL.

## Next Phase Readiness

- Brain MCP server is complete and ready for Claude system prompt configuration
- All 7 tools functional against brain.* schema (requires `python -m promaia.storage.db_init init-brain` to apply schema to Supabase)
- Action extraction gracefully degrades if instructor not available or API key missing
- Ready for Phase 3: heartbeat autonomy implementation

---
*Phase: 02-brain-schema-and-mcp-tools*
*Completed: 2026-03-05*
