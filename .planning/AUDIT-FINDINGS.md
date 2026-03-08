# Memory Audit Findings

*Generated: 2026-03-07T19:36:58.091403*

Here is the audit of the planning/memory docs against the codebase source files:

### Category 1: WRONG — Claims that contradict the source code

- **File**: `v3.0-PLANS.md` (Plan 3) and `ROADMAP.md` (Phase 11)
  - **Issue**: Docs claim the personality system prompt is "Stored in brain (not hardcoded) as a profile trait or config".
  - **Evidence**: In `promaia/telegram/conversation.py`, `PERSONALITY_SYSTEM_PROMPT` is hardcoded as a string constant at the top of the file.
  - **Severity**: HIGH

- **File**: `v3.0-PLANS.md` (Plan 3) and `ROADMAP.md` (Phase 11)
  - **Issue**: Docs claim the conversation engine loads the "last 5 messages" from conversation history for continuity.
  - **Evidence**: In `promaia/telegram/conversation.py` (`_assemble_context`), the code actually loads 10 messages: `history = await get_conversation_history(chat_id, limit=10)`.
  - **Severity**: MEDIUM

- **File**: `v3.0-PLANS.md` (Plan 3) and `ROADMAP.md` (Phase 11)
  - **Issue**: Docs claim session synthesis triggers "After 5+ minutes of no messages".
  - **Evidence**: In `promaia/telegram/conversation.py`, the silence timer is set to 4 minutes (`SYNTHESIS_SILENCE_SECONDS = 240`).
  - **Severity**: LOW

- **File**: `promaia/brain/mcp_server.py` (Source Code Docstring)
  - **Issue**: The docstring for `list_tools()` says `"""Enumerate all 13 brain tools."""`
  - **Evidence**: The function actually returns 16 tools (and the module docstring correctly states 16 tools).
  - **Severity**: LOW

### Category 2: STALE — Information that was once true but has been superseded

- **File**: `ROADMAP.md`
  - **Line/Section**: Phase 7: Event Bus + Notification Layer
  - **Issue**: The plan checkboxes for Phase 7 are unchecked (`[ ] 07-01-PLAN.md`, `[ ] 07-02-PLAN.md`, `[ ] 07-03-PLAN.md`).
  - **Evidence**: The phase itself is marked as `[x]` complete, the text says "3/3 plans complete", and `STATE.md` confirms Phase 7 is fully shipped. The checkboxes were forgotten.
  - **Severity**: LOW

### Category 3: CONTRADICTIONS — Places where planning docs disagree with each other

- *No major contradictions found between the planning docs themselves outside of the stale checkboxes mentioned above.*

### Category 4: MISSING — Important things in the codebase not reflected in docs

- *No major undocumented capabilities found. The docs are highly detailed and accurately reflect the schema, tools, and agent configurations present in the code.*
