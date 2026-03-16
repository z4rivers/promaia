# Tool Design & Implicit Frameworks Notes

This document captures the implicit logic, failure modes, and architectural decisions embedded in the Python-based `zBrain` tool definitions (formerly a massive dictionary in `brain.py`, now extracted to `tool_definitions.py` and `tool_handlers.py`).

⚠️ **CRITICAL FOR TYPESCRIPT MIGRATION TEAM:** Do *not* refactor these mechanisms away into naive switch statements. They exist to solve very specific real-time Voice UI and memory persistence problems.

---

## 1. Hybrid Async Confirmation (The "Two-Step" Commit)

### The Problem
When a user tells the voice agent to "save that to memory," the STT transcription might be flawed, or the agent's summarization might miss nuance. If the agent writes directly to the permanent MuninnDB, the database fills with garbage or inaccuracies that the user cannot easily delete via voice.

### The Mechanism
We use a **Hybrid Async Confirmation** model.
1. The agent's `record_memory` tool *does not write permanently*. Instead, it adds the extracted memory to a temporary `proposed_memories` array within the current `AudioSession` (libSQL/MuninnDB).
2. The user is told "I've noted that for review" rather than "I saved it".
3. After the conversation ends, these proposed memories appear on the web dashboard for visual confirmation (Accept/Edit/Discard).
4. Only upon clicking "Accept" does the data officially flow into the semantic MuninnDB for long-term recall.

### Migration Rule
When porting `record_memory` to TypeScript, preserve the step that writes to the `AudioSession` draft table rather than calling the MuninnDB `capture` endpoint directly.

---

## 2. De Bono's "Six Thinking Hats" (Cognitive Routing)

### The Problem
The agent needs to dynamically switch personality sub-system instructions (e.g., from "Be an empathetic active listener" to "Act as a hardcore technical critic" or "Act as an imaginative brainstormer") without breaking the real-time WebSocket connection or requiring massive system prompt rewrites mid-turn.

### The Mechanism
We mapped De Bono's Six Thinking Hats to the `switch_cognitive_mode` tool:
*   `white_hat`: Facts, analysis, neutral logic.
*   `red_hat`: Emotion, empathy, venting.
*   `black_hat`: Critical analysis, risk spotting, "devil's advocate".
*   `yellow_hat`: Optimism, identifying value, finding the "yes".
*   `green_hat`: Creativity, brainstorming, lateral thinking.
*   `blue_hat`: Orchestration, summary, process control.

When the tool is called, the system appends a specific directive into the session context.

### Migration Rule
Ensure the TypeScript `switch_cognitive_mode` handler retains these explicit mappings and overrides the agent's underlying tone effectively across subsequent WS turns.

---

## 3. The Context Window "Tether" (Data-Loss Prevention)

### The Problem
Over a 30-minute Voice Session, vital implicit context (names, ideas discussed) risks falling out of Gemini's active context window before the user explicitly asks to save it. When the WebSocket closes, this transient context vanishes.

### The Mechanism
The prompt implicitly instructs the model to use `record_memory` constantly (as a background process) when interesting facts emerge, rather than waiting for explicitly commanded "Save this." Because of the *Hybrid Async Confirmation* (see point 1), over-capturing is perfectly safe—the user will filter the noise on the dashboard later.

### Migration Rule
Do not attempt to batch tool calls at the end of the WebSocket session. Tool calls must execute mid-stream to ensure data is safely lodged in the libSQL/MuninnDB staging tables before the connection is inevitably severed by network drops.

---

## 4. Time Awareness and "The Moving Now"

### The Problem
LLMs do not inherently know the current time, day of the week, or the passage of time within an open session.

### The Mechanism
The `datetime_stamp` injected at the start of the system prompt gives a static baseline. However, the `read_calendar` tool specifically expects relative queries from the model (e.g., "What's happening *today*?") to resolve using Python's live timezone-aware `datetime.now()` rather than relying on the LLM's static baseline.

### Migration Rule
The TS equivalent of `get_calendar_context()` MUST recalculate the actual *current local time* on every single invocation, preventing drift over long sessions.
