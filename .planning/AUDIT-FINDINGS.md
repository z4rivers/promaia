# Memory Audit Findings

*Generated: 2026-03-07T19:36:58.091403*
*Updated: 2026-03-08 — all findings resolved*

### Category 1: WRONG — Claims that contradict the source code

- **File**: `v3.0-PLANS.md` (Plan 3) and `ROADMAP.md` (Phase 11)
  - **Issue**: Docs claimed the personality system prompt is "Stored in brain (not hardcoded)".
  - **Evidence**: In `promaia/telegram/conversation.py`, `PERSONALITY_SYSTEM_PROMPT` is hardcoded as a string constant.
  - **Status**: RESOLVED — docs updated to reflect current state (hardcoded, TODO to move to brain)

- **File**: `v3.0-PLANS.md` (Plan 3) and `ROADMAP.md` (Phase 11)
  - **Issue**: Docs claimed the conversation engine loads "last 5 messages".
  - **Evidence**: Code loads 10 messages: `history = await get_conversation_history(chat_id, limit=10)`.
  - **Status**: RESOLVED — docs updated to say "last 10 messages"

- **File**: `v3.0-PLANS.md` (Plan 3) and `ROADMAP.md` (Phase 11)
  - **Issue**: Docs claimed session synthesis triggers "After 5+ minutes of no messages".
  - **Evidence**: Silence timer is 4 minutes (`SYNTHESIS_SILENCE_SECONDS = 240`).
  - **Status**: RESOLVED — docs updated to say "4 minutes"

- **File**: `promaia/brain/mcp_server.py` (Source Code Docstring)
  - **Issue**: The docstring for `list_tools()` said "13 brain tools".
  - **Evidence**: 16 tools registered (module docstring was already correct).
  - **Status**: RESOLVED — docstring updated to "16 brain tools"

### Category 2: STALE — Information that was once true but has been superseded

- **File**: `ROADMAP.md`
  - **Issue**: Phase 7 checkboxes unchecked despite being complete.
  - **Status**: Known, cosmetic only — not blocking.

### Category 3: CONTRADICTIONS
- *No contradictions found.*

### Category 4: MISSING
- *No undocumented capabilities found.*
