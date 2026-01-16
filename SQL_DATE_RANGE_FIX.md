# SQL Query Date Range Fix
**Date:** January 16, 2026  
**Branch:** polish  
**Status:** ✅ FIXED

## Problem

The `-sql` query type was failing to handle date range queries properly. When users tried queries like:

```
-sql all the stories in the current angl sprint so basically between a week ago and april, with the angl work project
```

The system generated incorrect SQL with conflicting date logic:

```sql
-- Attempt 1: Impossible condition (last week AND before April 2025)
AND u.created_time >= date('now', '-7 days')
AND u.created_time <= '2025-04-30'

-- Attempt 2: Wrong logic (>= April AND >= last week)
AND u.created_time >= '2025-04-01'
AND u.created_time >= DATE('now', '-7 days')

-- Attempt 3: Wrong year
AND u.created_time >= date('now', '-7 days')
AND u.created_time <= '2024-04-30'
```

All three attempts returned 0 rows because the date logic was fundamentally broken.

## Root Cause

The date filtering system only supported **backward-looking queries** using `days_back` (e.g., "last 7 days"), but not **date ranges** with both start and end dates.

The intent parsing prompt instructed the LLM to parse dates as:
```python
"date_filter": {"days_back": 7, "description": "last 7 days"}
```

But for ranges like "between a week ago and april", there was no way to express both:
- Start date: 7 days ago
- End date: April 2026 (future date)

## Solution

### 1. Enhanced Date Filter Schema

Updated the `date_filter` schema to support three modes:

```python
# OLD (only backward lookups):
"date_filter": {"days_back": null, "description": ""}

# NEW (supports ranges too):
"date_filter": {
    "days_back": null,        # For simple backward lookups
    "start_date": null,        # For range start (can be relative or absolute)
    "end_date": null,          # For range end (can be future dates)
    "description": ""
}
```

### 2. Updated Intent Parsing Rules

Added comprehensive date parsing rules in `promaia/ai/nl_orchestrator.py`:

```python
Rules for date_filter - CRITICAL:
- For simple backward lookups use days_back: "last N months" → days_back: N*30
- For date RANGES use start_date and end_date: "between X and Y" → start_date: X, end_date: Y
- For future dates, use ISO format (YYYY-MM-DD): "until april" → end_date: "2026-04-30"
- Parse relative dates: "a week ago" → "DATE('now', '-7 days')" for start_date
- TODAY IS: 2026-01-16 - use this for calculating relative dates
- NEVER mix incompatible date logic (don't use days_back with start_date/end_date)
```

### 3. Examples Added

Added clear examples showing correct date parsing:

```python
# Backward only
"last 7 days" → {"days_back": 7, "start_date": null, "end_date": null}

# Date ranges
"between a week ago and april" → {
    "days_back": null,
    "start_date": "DATE('now', '-7 days')",
    "end_date": "2026-04-30"
}

# Future end date only
"until april" → {"days_back": null, "start_date": null, "end_date": "2026-04-30"}

# Past start date only
"since last monday" → {"days_back": null, "start_date": "DATE('now', '-7 days')", "end_date": null}
```

### 4. Updated SQL Generation

Enhanced SQL generation in `promaia/ai/query_strategies.py` with explicit date filter rules:

```sql
DATE FILTER RULES:
- If days_back is provided: use "AND u.created_time >= date('now', '-{days_back} days')"
- If start_date and/or end_date are provided, use them for date ranges:
  - start_date: "AND u.created_time >= '{start_date}'" or "AND u.created_time >= date('now', '-N days')"
  - end_date: "AND u.created_time <= '{end_date}'" (can be a future date like '2026-04-30')
- NEVER combine days_back with start_date/end_date - use one or the other
```

### 5. Updated Validation Logic

Enhanced result validation in `promaia/ai/nl_utilities.py` to check both:
- `days_back` constraints (existing)
- `start_date` and `end_date` range constraints (new)

The validator now properly handles:
- Relative dates like `date('now', '-7 days')`
- Absolute dates like `2026-04-30`
- Both start and end date boundaries

## Files Modified

1. **promaia/ai/nl_orchestrator.py**
   - Updated date_filter schema
   - Added date parsing rules and examples
   - Enhanced intent parsing prompt

2. **promaia/ai/query_strategies.py**
   - Added DATE FILTER RULES section
   - Added date range SQL examples
   - Updated SQL generation prompt

3. **promaia/ai/nl_utilities.py**
   - Enhanced date validation to check ranges
   - Added support for relative and absolute date parsing
   - Improved error messages for date range violations

## Testing

Test the fix with these queries:

```bash
# Date range with future end date
maia chat -s stories:100 -sql between a week ago and april with angl project

# Date range with relative dates
maia chat -s journal:50 -sql entries from last monday to next friday

# Future date only
maia chat -s stories:100 -sql stories due before april

# Past date only  
maia chat -s gmail:100 -sql emails since january 1st

# Backward only (should still work)
maia chat -s journal:30 -sql last 7 days
```

## Expected Behavior

### Before Fix ❌
- Generated conflicting date logic
- Returned 0 rows for date ranges
- Failed after 2-3 retry attempts
- Confused about relative vs absolute dates

### After Fix ✅
- Correctly parses date ranges
- Generates valid SQL with proper `>=` and `<=` operators
- Handles relative dates (`date('now', '-7 days')`)
- Handles future absolute dates (`2026-04-30`)
- Validates results match the requested date range

## Notes

- The system now distinguishes between **three date modes**:
  1. **Backward only**: `days_back` (e.g., "last 7 days")
  2. **Range**: `start_date` + `end_date` (e.g., "between X and Y")
  3. **One-sided range**: Only `start_date` or only `end_date`

- The LLM is explicitly instructed to **NEVER mix** `days_back` with `start_date`/`end_date`

- Current date (`2026-01-16`) is provided in the prompt to help the LLM calculate relative dates correctly

- Validation is "soft" - checks a sample of first 5 results rather than all results for performance

## Related Issues

This fix also improves:
- Sprint planning queries (e.g., "current sprint stories")
- Project timeline queries (e.g., "Q1 2026 tasks")
- Historical analysis (e.g., "compare December vs January")

## Next Steps

Consider adding:
- Week/month/quarter shortcuts (e.g., "this week", "Q1")
- Relative week parsing (e.g., "last week" → correct Monday-Sunday range)
- Time-of-day filtering (currently only supports dates, not times)
