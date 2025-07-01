# Maia Database Sync Functionality PRD

## 1. Overview

This document outlines the product requirements for the `maia database sync` command. The primary goal of this command is to synchronize data from a remote source (e.g., Notion database) to local storage, providing options for full and incremental updates, and ensuring that local data accurately reflects the source based on specified criteria.

## 2. Core Functionality

The `maia database sync` command fetches data from a configured database source and saves it locally. The sync process is governed by several factors including the last synchronization time, command-line arguments (`--force`, `--days`), and the existence of pages locally.

### 2.1. Key Principles

*   **Incremental Sync by Default:** When no specific flags (`--force`, `--days`) are provided, the system should perform an incremental sync. It should fetch only those pages from the source that have been modified *after* the `last_sync_time` recorded for that database.
*   **Local Existence Check:** A crucial aspect of the sync is to ensure that pages fetched from the remote source are downloaded if they do not already exist locally, regardless of their `last_edited_time` relative to `last_sync_time` (unless `--force` changes this behavior, or the date filters specifically exclude them).
*   **Force Update:** The `--force` flag overrides incremental logic and attempts to re-sync all relevant pages based on other active filters (like `--days` or source-specific filters).
*   **Date Range Sync (`--days`):** The `--days` flag allows syncing pages based on a date property (configurable, defaults to `created_time` if `--force` is also used, otherwise `last_edited_time` or a configured date property) within the specified number of past days.
*   **Timezone Consistency:** All date and time comparisons must be timezone-aware, with UTC being the standard. `last_sync_time` is stored in UTC. Timestamps from the source (e.g., Notion's `last_edited_time`) are converted to UTC before comparison.

## 3. Detailed Sync Logic

The connector responsible for a specific source type (e.g., `NotionConnector`) implements the `sync_to_local` method.

### 3.1. Page Fetching

1.  **Filter Construction:**
    *   Based on command-line arguments (`--days`, `--force`), database configuration (`last_sync_time`, `default_days`, configured date property), and source specifications (e.g., `journal[status=published]`), appropriate filters are constructed for the remote API query.
    *   **Default Incremental:** If no `--days`, `--force`, or specific date filters are given, and a valid `last_sync_time` exists, the query requests pages edited after `last_sync_time`.
    *   **`--days` argument:**
        *   If `--days N` is specified:
            *   If `--force` is also present: The query targets pages *created* within the last N days.
            *   If `--force` is NOT present: The query targets pages *edited* (or matching a configured date property) within the last N days.
        *   The `date_prop` used (e.g., `created_time`, `last_edited_time`, or a custom "Date" field) is determined by `build_date_filter` in `maia/cli/database_commands.py`.
    *   **`--force` without `--days`:** The query fetches all pages matching other non-date filters. No specific date range is applied by default from the CLI, but the connector might query based on a configured date property.
    *   **Initial Sync / No `last_sync_time`:** If `last_sync_time` is not available (or invalid) and no other overriding flags are present, the system syncs pages from the last `default_days` (e.g., 7 days), typically based on `created_time` or a configured date property for the initial pull.

2.  **API Query:** The connector queries the remote source API (e.g., Notion) with the constructed filters.

### 3.2. Page Processing and Skipping Logic

For each page returned by the remote API query:

1.  **Identify Page:** Extract `page_id` and `page_last_edited_time_str`.
2.  **Determine Local File Path:**
    *   Attempt to derive a title from the page data already available from the query (e.g., "Name" property).
    *   Construct a prospective local filename (e.g., `My Page PageID123.md`).
    *   Check if this `local_file_path` exists.
3.  **Decision to Sync/Skip:**
    *   **Scenario A: `--force` is TRUE:**
        *   The page is **ALWAYS PROCESSED** (downloaded/updated).
        *   Log: "Page X: force_update is True. Will sync."
    *   **Scenario B: `--force` is FALSE AND local file DOES NOT exist:**
        *   The page is **ALWAYS PROCESSED**.
        *   Log: "Page X does not exist locally. Will sync."
    *   **Scenario C: `--force` is FALSE AND local file DOES exist:**
        *   Compare `page_last_edited_time` (from Notion, UTC) with `db_last_sync_time` (from local config, UTC).
        *   A small tolerance (e.g., 1 second added to `db_last_sync_time`) is used in the comparison to account for minor clock skews or precision differences.
        *   If `page_last_edited_time <= (db_last_sync_time + tolerance)`:
            *   The page is **SKIPPED**.
            *   Log: "Skipping page X. Exists locally and up-to-date (last edit: Y, last sync: Z)."
        *   Else (page is newer):
            *   The page is **PROCESSED**.
            *   Log: "Page X exists locally but is outdated. Will re-sync."
        *   If date comparison fails (e.g., invalid date strings) or if `page_last_edited_time_str` or `db_last_sync_time_str` is missing, the page is **PROCESSED** as a fallback, with a warning.

4.  **Processing (If Not Skipped):**
    *   Fetch full page content from the remote source.
    *   Convert content to local format (e.g., Markdown).
    *   Determine the final filename, prioritizing a title derived from the full page content. If a good title isn't available, use a default like "untitled\_pageid.md".
    *   Save the file locally.
    *   Log: "Saved page to /path/to/file.md"

### 3.3. Updating `last_sync_time`

*   After a sync operation for a database completes (and if at least one page was saved or skipped, indicating a successful interaction), the `last_sync_time` for that database in the local configuration (`promaia.config.json`) is updated to the current UTC timestamp (`datetime.now(timezone.utc)`).

## 4. Logging Requirements

To provide visibility into the sync process:

*   **INFO Level:**
    *   Start of sync for a database: `Initiating sync for database: '{db_name}'. Force: {force_status}. Days: {days_arg}. Filters from spec/config...`
    *   Number of pages found by the query: `Found {N} pages to sync.`
    *   Processing individual page: `Processing page {i+1} of {N}: '{title_for_log}' ({page_id})`
    *   Skipping a page (and why):
        *   `Skipping page X. Exists locally and up-to-date (last edit: Y, last sync: Z).`
    *   Saving a page: `Saved page to {file_path}`
    *   Sync completion summary: `✓ {db_name}: {saved_count} saved, {skipped_count} skipped.`
    *   Errors encountered during sync.
*   **DEBUG Level:**
    *   Detailed filter construction logic in `maia/cli/database_commands.py`.
    *   Details of Notion API filter construction in the connector.
    *   `force_update` status for a page.
    *   Retrieved `page_last_edited_time` and `db_last_sync_time` values.
    *   Timezone conversion details (e.g., "Made naive sync_dt timezone-aware (UTC): ...").
    *   Result of date comparisons.
    *   Local file existence check details.

## 5. Key Files Involved

*   `maia/cli/database_commands.py`: Handles CLI arguments, orchestrates sync, builds date filters.
*   `maia/connectors/notion_connector.py` (and other connectors): Implements source-specific query and page processing logic.
*   `maia/config/databases.py`: Manages database configurations, including `last_sync_time`.
*   `maia/connectors/base.py`: Defines `DateRangeFilter` and other base classes.

## 6. Edge Cases and Considerations

*   **Invalid `last_sync_time`:** If `last_sync_time` in the config is corrupted or unparsable, the system should gracefully fall back to syncing based on `default_days` (as if it's an initial sync for that period).
*   **API Rate Limiting:** Connectors should implement small delays (e.g., `asyncio.sleep(0.1)`) between fetching/processing pages to avoid hitting API rate limits. Pagination in Notion queries should also be mindful of limits.
*   **Title Extraction for Filenames:** The system should attempt to get a meaningful title for filenames, first from queried page properties, then from full page content, and as a last resort, using a default. This should be done efficiently to minimize extra API calls.
*   **Error Handling:** Individual page processing errors should be logged and counted but should not stop the entire sync process for other pages. Overall sync operation errors should also be caught and reported. 