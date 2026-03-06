---
phase: 05-validate-and-activate
plan: 01
subsystem: database
tags: [postgres, gmail, jsonb, content-pipeline, agent-context]

# Dependency graph
requires:
  - phase: 04-platform-activation
    provides: Gmail OAuth pipeline and gmail_content table
provides:
  - Postgres fallback for Gmail content in load_content_by_page_ids
  - resync_missing_bodies() function for backfilling NULL message_content
  - GIN index on gmail_labels for JSONB operator support
  - Correct SQL type documentation for gmail_content columns
affects: [05-02, 05-03, agent-executor, email-triage-agent]

# Tech tracking
tech-stack:
  added: []
  patterns: [postgres-fallback-for-disk-content, gin-index-for-jsonb, resync-pattern]

key-files:
  created: []
  modified:
    - promaia/storage/files.py
    - promaia/brain/gmail_ingest.py
    - promaia/storage/hybrid_storage.py

key-decisions:
  - "Gmail Postgres fallback activates only when md_file is None AND entry is Gmail -- non-Gmail paths unchanged"
  - "GIN index replaces B-tree on gmail_labels for proper JSONB operator support"
  - "resync_missing_bodies uses snippet as fallback when full body extraction returns empty"

patterns-established:
  - "Postgres fallback pattern: check content_type/database_name for gmail before skip logic"
  - "Column type awareness: gmail_labels=JSONB, email_date=TEXT, synced_time=TEXT"

requirements-completed: [VALID-02, VALID-03]

# Metrics
duration: 4min
completed: 2026-03-06
---

# Phase 5 Plan 1: Gmail Content Pipeline Summary

**Postgres fallback for Gmail content loading with resync capability and JSONB GIN indexing**

## Performance

- **Duration:** 4 min
- **Started:** 2026-03-06T19:50:27Z
- **Completed:** 2026-03-06T19:55:09Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- Gmail pages now load from Postgres when .md files are absent on disk (was: silently skipped, agents got 0 email context)
- Added resync_missing_bodies() function with CLI flag to backfill NULL message_content rows via Gmail API
- Replaced B-tree index on gmail_labels (JSONB) with GIN index for proper @> operator support
- Documented gmail_content column types to prevent future SQL type mismatch errors

## Task Commits

Each task was committed atomically:

1. **Task 1: Add Postgres fallback for Gmail content in load_content_by_page_ids** - `e31054c` (feat)
2. **Task 2: Fix message_content population and re-sync existing emails** - `a66151a` (feat)

## Files Created/Modified
- `promaia/storage/files.py` - Added Postgres fallback in load_content_by_page_ids for Gmail entries without .md files; fixed Unicode emoji prints for Windows compatibility
- `promaia/brain/gmail_ingest.py` - Added resync_missing_bodies() function and --resync-bodies CLI flag
- `promaia/storage/hybrid_storage.py` - Replaced B-tree index with GIN on gmail_labels; added column type documentation

## Decisions Made
- Gmail Postgres fallback activates only when md_file is None AND entry is Gmail -- non-Gmail paths remain unchanged
- GIN index replaces B-tree for proper JSONB operator support (@>, ?, etc.)
- resync_missing_bodies stores "[snippet only]" prefix when full body extraction returns empty, so consumers can distinguish

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Fixed Unicode emoji prints crashing on Windows cp1252**
- **Found during:** Task 1 (Postgres fallback implementation)
- **Issue:** Existing print statements in load_content_by_page_ids used emoji characters that fail on Windows cp1252 encoding, causing UnicodeEncodeError and aborting the entire function
- **Fix:** Replaced emoji-prefixed prints with ASCII-safe equivalents ([Gmail], [WARN])
- **Files modified:** promaia/storage/files.py
- **Verification:** Function executes without encoding errors on Windows
- **Committed in:** e31054c (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Essential fix -- the function could not execute at all on Windows without this. No scope creep.

## Issues Encountered
- 17 of 34 gmail_content rows still have NULL message_content. The resync_missing_bodies() function is ready but requires running `python -m promaia.brain.gmail_ingest --resync-bodies` with live Gmail API access (OAuth tokens). This is a runtime operation, not a code gap.

## User Setup Required
None - no external service configuration required. To backfill message bodies, run:
```
python -m promaia.brain.gmail_ingest --resync-bodies --workspace zbrain
```

## Next Phase Readiness
- Gmail content pipeline is code-complete
- Agent executor can now load Gmail pages in context (verified: 3/3 pages loaded from Postgres)
- Ready for Plan 02 (agent data pipeline fixes) and Plan 03 (end-to-end validation)

## Self-Check: PASSED

All files exist. All commits verified (e31054c, a66151a).

---
*Phase: 05-validate-and-activate*
*Completed: 2026-03-06*
