# SQL Query Visibility & Guidance Improvements

## Summary

Improved visibility into SQL query generation and added better guidance to prevent unnecessary SQL queries for abstract questions.

## Changes Made

### 1. SQL Query Display (Visibility)

**File**: `promaia/ai/nl_processor_wrapper.py`
- Added `return_metadata` parameter to `process_natural_language_to_content()` 
- Now returns tuple with `(content, metadata)` where metadata includes the generated SQL query
- Backward compatible (defaults to returning just content)

**File**: `promaia/chat/query_tools.py`
- Updated `_execute_query_sql()` to capture generated SQL from metadata
- Added generated_sql field to execution results
- Added warning note about SQL being for exact text/keywords

**File**: `promaia/chat/interface.py`  
- Updated `request_query_permission()` to display generated SQL before user approval
- Shows truncated SQL for long queries (300 char limit)
- Now users see the actual SQL that will execute before approving

### 2. Better Query Guidance (When NOT to use SQL)

**File**: `promaia/ai/prompts.py`

#### Updated query_sql description:
- ✅ **When to use**: Specific, concrete keywords (names, products, projects)
- ❌ **When NOT to use**: 
  - Abstract questions ("who am I?", "identity", "purpose")
  - Filtering by database properties → use query_vector
  - Concepts without specific searchable keywords
  - Fuzzy/uncertain searches → use query_vector

#### Added "SQL Success Check":
Before using query_sql, ask: "What specific words/phrases will appear in the text?" 
If you can't identify concrete keywords, use query_vector instead.

#### Updated multiple query strategy guidance:
- Clarified that multiple queries should be COMPLEMENTARY, not redundant
- Added examples of when multiple queries are good vs bad:
  - ✅ Good: Different databases, different strategies, hedging uncertainty
  - ❌ Bad: Running SQL AND vector for same abstract question where SQL won't work

## Example: "who am I?" Query

### Before:
- AI ran BOTH query_vector AND query_sql
- SQL query searched for literal phrases like "who am I", "identity", "purpose"
- SQL returned 0 results (useless)
- No visibility into what SQL was generated

### After:
- AI should recognize "who am I?" as abstract → use query_vector ONLY
- If SQL is still used, user now sees generated SQL like:
  ```
  📝 Generated SQL:
     SELECT u.page_id, u.workspace, u.database_name, u.title, u.created_time
     FROM unified_content u
     WHERE (u.title LIKE '%who am I%' OR u.title LIKE '%identity%' OR u.title LIKE '%purpose%')
     AND u.database_name = 'journal'
     AND u.workspace = 'koii'
     LIMIT 1200
  ```
- User can see why it failed (searching for literal phrases in abstract question)

## Impact

1. **More transparency**: Users now see exactly what SQL is generated
2. **Fewer wasteful queries**: AI should make fewer SQL queries for abstract questions
3. **Better guidance**: Clear examples of when SQL works vs doesn't work
4. **Improved reasoning**: AI now has "SQL Success Check" criteria to validate query choice

## Testing

Test with queries like:
- "who am I?" → Should prefer query_vector only
- "emails from Federico about launch" → SQL appropriate (concrete name + keyword)
- "what are my values?" → Should prefer query_vector only (abstract)
- "stories with status blocked" → query_vector (property filter)

## Configuration

No configuration changes needed. The improvements are automatic through:
1. Enhanced system prompts
2. Metadata return from query processing
3. Display improvements in chat interface
