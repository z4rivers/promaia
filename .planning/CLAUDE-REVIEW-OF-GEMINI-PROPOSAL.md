# Claude's Review of Gemini's Collaboration Proposal

**Author:** Claude (Opus 4.6)
**Date:** March 16, 2026
**Reviewing:** `.planning/GEMINI-COLLABORATION-PROPOSAL.md`

---

## Yellow Hat: What's Good

### 1. Priority Sequencing Is Correct
Gemini and I independently arrived at the same conclusion: **heal the Split-Brain before building the Heartbeat.** The "Heartbeat pumping the wrong blood" analogy is precise — automation built on fragmented state amplifies noise. This alignment means we're not debating priorities; we're debating implementation.

### 2. The Over-Capture Risk
Gemini identifies that dumping raw data (10,000-line grep outputs) into the Hebbian graph poisons the associative engine. My plan's extraction philosophy quotes the codebase docstring: "the input stream should be RICH, not filtered." Gemini correctly identifies the ceiling on that principle. There IS a difference between "rich" and "noisy." The pipeline's `extract_insights()` already has an 80-char minimum threshold — but there's no maximum or noise filter. This is a real gap worth addressing.

### 3. The Stress Test as Validation
Gemini's Step 3 — voice note → graph → Claude reads → Blueprint → Gemini executes → log saves back — is the right end-to-end integration test. My plan has per-phase verification but not this kind of cross-agent loop test. This should be adopted.

---

## Green Hat: Where Could This Grow?

### 1. The Handoff Handshake Is Actually a Workflow Engine
Gemini proposes state tags: `AWAITING_BLUEPRINT`, `READY_FOR_EXECUTION`, `AWAITING_RED_TEAM`. On the surface this is agent coordination. But if sessions have machine-readable states, the heartbeat doesn't just monitor — it can **advance state when conditions are met**. "Blueprint complete + all tests pass → automatically transition to READY_FOR_EXECUTION." That's not a notification system. That's an autonomous project manager. This seed is bigger than Gemini framed it.

### 2. The Blackboard Paradigm Is a Protocol, Not a Table
Gemini names the "Blackboard" explicitly — a shared space all agents read/write. My shareboard design stores session snapshots. But Gemini's framing pushes toward something more powerful: a **live, queryable workspace** where agents leave structured artifacts for each other. The existing `signals_db.py` already has rooms, messages, and presence tracking. If we layer Gemini's state tags onto the signals infrastructure, we get a real-time collaboration protocol without building a new system. The shareboard becomes the persistent layer; signals become the real-time layer. Same paradigm, two speeds.

### 3. The Canonical User Story
Gemini's end-to-end test (Step 3) isn't just a test — it's the **canonical user story** for the whole platform. "Zack has a thought in the truck (voice) → it enters the graph → Claude reads it and plans → Gemini executes → results flow back." If we build the architecture to make THAT loop frictionless, every other use case falls out of it. This should be the design target, not just a verification step.

### 4. The Schema Standardization — Redirected
Gemini wants to standardize the MuninnDB payload schema. The schema already exists in `capture_memory()` — but Gemini's instinct to formalize it has a Green Hat extension: **what if the schema included a `status` field?** Every memory could carry workflow state: `raw`, `extracted`, `associated`, `surfaced`, `acted_on`. This turns the memory table into a processing pipeline with visibility at every stage. The heartbeat could advance memories through states. The dashboard could show "12 memories awaiting association, 3 push triggers pending."

---

## Implementation Check: Four Lenses

### Lens 1: Code Reuse
**Finding: Gemini's plan proposes designing what already exists.**

`capture_memory()` at `promaia/brain/core/memory_pipeline.py:35` IS the universal pipeline. It handles: insert → embed → extract actions → extract intelligence (decisions/insights/preferences/asides) → log event → MuninnDB dual-write. Two of three surfaces already use it:
- MCP/Claude: via `capture_ops._handle_capture()` at `promaia/brain/mcp/handlers/capture_ops.py:40`
- Voice/Gemini Live: via `memory_ops.handle()` at `promaia/brain/voice_handlers/memory_ops.py:33` (staging model)
- Git hooks: via `routers/brain.py:313`

The ONE broken path is `promote_message_to_memory()` at `promaia/telegram/brain_ops.py:531`. It does a raw INSERT + embedding and skips action extraction, intelligence extraction, MuninnDB write, and event logging. The fix is replacing its internals with a call to `capture_memory()`. Not a schema design project — a function call swap.

**Recommendation:** Skip Gemini's Step 1 (schema alignment). The schema exists. Wire the broken path directly.

### Lens 2: The Monolith Problem
**Finding: Neutral.** Gemini doesn't mention `mcp_server.py` (originally 2,188 lines, now partially decomposed into `promaia/brain/mcp/handlers/`). The plan neither helps nor hurts the decomposition. Any new MCP tools from the Handoff Handshake should go into new handler modules (`mcp/handlers/handoff_ops.py`), not back into the monolith. The existing pattern is the right home.

### Lens 3: Tool Parity
**Finding: Not addressed.** The voice agent gets a shallow MuninnDB snapshot via `context_loaders.get_muninn_context()`:

```python
# 8 items, 200 chars each, hardcoded generic queries:
res = await muninn.activate(
    ["Zack's active projects", "Zack's profile preferences", "recent priorities"],
    max_results=8
)
```

MCP search does full parallel retrieval: sqlite-vec similarity + MuninnDB ACTIVATE, with dynamic queries based on the user's actual question, rich metadata, up to 10 full-content results. Voice is a second-class citizen for retrieval.

**Recommendation:** Update `context_loaders.get_muninn_context()` to accept an optional `context_hints: list[str]` parameter. The voice cache pre-warm can pass recent conversation topics instead of hardcoded strings.

### Lens 4: Research First Check
**Finding: Gemini missed existing infrastructure.**

| Existing Code | What It Does | Gemini Awareness |
|---------------|-------------|-----------------|
| `capture_memory()` pipeline | THE unified write path | Not identified |
| `promote_message_to_memory()` | The specific broken function | Not identified |
| `gcal/google_calendar.py` (19K lines) | Full calendar integration | Not mentioned |
| `mail/` (16 files, 200K+) | Full email stack | Mentioned abstractly |
| `mcp/calendar_tools_server.py` | MCP calendar tools | Not mentioned |
| `mcp/gmail_tools_server.py` | MCP email tools | Not mentioned |
| `signals_db.py` | Rooms, messages, presence | Not connected to Handoff proposal |
| `brain_ops.py` Telegram ops | Parallel to MCP handlers | Not identified |

The biggest miss: `signals_db.py` already provides `update_presence()`, `send_message()`, `get_room_messages()`, room CRUD. Gemini's Handoff Handshake should be implemented using this existing system, not as a new state-tracking mechanism.

---

## What to Adopt from Gemini's Plan

1. **Handoff state tags** — implement via `signals_db.py`, layer onto shareboard schema
2. **Over-capture risk mitigation** — add content-length ceiling or synthesis requirement to the pipeline
3. **End-to-end cross-agent stress test** — add as final verification after all phases complete
4. **"State machine not chat" framing** — influences shareboard design (sessions carry workflow state)
5. **Memory status field** — extend schema with processing states for pipeline visibility

## What to Skip

1. **Schema alignment phase** — `capture_memory()` IS the schema
2. **"Universal MuninnDB payload schema" design** — already implemented in pipeline
3. **Any work that treats voice as broken** — voice is already on the pipeline via staging

---

## Synthesis: Toward a Merged Plan

The two plans are complementary, not competing:
- **Claude's plan** provides the implementation roadmap (6 phases, specific files, specific functions, code-level changes)
- **Gemini's plan** provides the strategic framing (Blackboard paradigm, state machine thinking, cross-agent workflow)

The merged plan should be Claude's phases with Gemini's concepts woven in:
- Phase 1 stays unchanged (seal the pipeline)
- Phase 2 stays unchanged (bridge redesign)
- Phase 3 gains token budgeting + voice context hints
- Phase 4 gains Gemini's workflow state awareness (heartbeat advances states, not just monitors)
- Phase 5 gains Gemini's Handoff Handshake protocol, built on `signals_db.py`
- Phase 6 stays unchanged (active calls tracking)
- A new verification phase adds Gemini's end-to-end stress test

Ready for the four-way discussion when Zack and Maia weigh in.
