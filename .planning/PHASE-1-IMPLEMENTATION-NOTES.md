# Technical Implementation Notes: Phase 1
**Status:** Pre-Validated for Execution

## 1. Phase 1A: `capture_memory()` Integration
*   **File:** `promaia/brain/core/memory_pipeline.py`
*   **Verified Signature:** 
    ```python
    async def capture_memory(
        db,
        vector_mgr: VectorDBManager,
        content: str,
        session_id: str,
        domain_name: Optional[str] = None,
        confidence: float = 0.9,
        source: str = "capture",
        ... (optional assets)
    ) -> Dict[str, Any]
    ```
*   **Verified Return:** Returns `Dict` with `memory_id`.
*   **Action:** In `promaia/telegram/brain_ops.py`, replace the internal `_sync()` logic in `promote_message_to_memory` with this async call. Note: `_get_db()` and `_get_vector_mgr()` are already available in that file.

## 2. Phase 1B: Voice Staging Persistence
*   **File:** `promaia/brain/voice_handlers/memory_ops.py`
*   **Current State:** `staged_memories` is a list passed to `handle(ft, staged_memories)`. 
*   **Target State:** Replace list mutations (`staged_memories.append`, `staged_memories.clear`) with DB operations on the new `staged_memories` table.
*   **Schema Change:** Add `user_id` column (default 'zack') to the migration.

## 3. Phase 1C: Domain Fuzzy Matching
*   **File:** `promaia/brain/core/memory_pipeline.py`
*   **Function:** `_get_or_create_domain_id(db, domain_name: str)`
*   **Verified Logic:** Currently does a strict match. Change to:
    ```python
    fuzzy = db.fetch_one("SELECT id, name FROM domains WHERE LOWER(name) = LOWER(%s)", (domain_name,))
    ```

## 4. Phase 1D: WAL Mode
*   **File:** `promaia/storage/libsql_db.py`
*   **Verified State:** `PRAGMA journal_mode=WAL;` is already hardcoded in `LibSQLDB._init_connection()`. 
*   **Action:** No code change needed. Only a confirmation log during startup.
