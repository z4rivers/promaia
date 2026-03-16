# Promaia: The Unified Architecture Plan
**Authors:** Gemini (Execution/Architecture) & Claude (Blueprint/Reasoning)
**Date:** 2026-03-16
**Status:** Approved Master Plan

---

## 1. The North Star: The Multiplier Alliance
We are transitioning Promaia from a collection of isolated savants into a cohesive, multi-agent cognitive system. The goal is the **Multiplier Effect (1+1=3)**: an architecture where Claude reasons, Gemini executes, Maia orchestrates, and Zack directs—all sharing a single, deterministic State Ledger (The Blackboard). 

To achieve this, we must heal the "Split-Brain" (where different interfaces write memories differently) and transform MuninnDB from a passive database into an active, proactive processing pipeline.

This plan merges Claude's implementation roadmap ("The Prism Pipeline") with Gemini's structural hardening and experiential pacing ("Maximum Awesomeness").

---

## 2. Core Architectural Principles

1. **Deterministic Plumbing, Probabilistic Extraction:** LLMs (Gemini/Claude) are used *only* to extract intelligence (Decisions, Insights, Preferences) from unstructured text. Structural database integrity (deduplication, domain normalization) is strictly enforced by deterministic Python backend code.
2. **The Ingestion Chokepoint:** Client surfaces (Telegram, Web, Voice, MCP) do not process their own memories. They push raw events to a single Event Bus.
3. **Reasoning Over Searching:** Agents should spend their token budgets on thinking, not searching. Context is assembled and pre-ranked by the bridge *before* the LLM is invoked.
4. **Transparency is Trust:** The system must visibly show its work (e.g., "Extracting insights...", "Searching codebase..."). 
5. **The Campfire:** Session handoffs and cross-agent collaboration happen in a persistent, readable workspace (The Shareboard), not through ephemeral chat context.

---

## 3. The Execution Sequence (Optimized for "Wow" & Stability)

### Phase 1: The Hardened Foundation (Sealing the Pipeline)
*Objective: Fix the Split-Brain without crashing the database.*

Claude correctly identified that `promote_message_to_memory()` in `telegram/brain_ops.py` is the leak causing the Split-Brain. However, directly piping it to `capture_memory()` under load will cause catastrophic `SQLITE_BUSY` locks and data loss on WebSocket disconnects.

**Implementation:**
1. **The Staging Queue (Write-Ahead Log):** Decouple *receiving* from *processing*. WebSocket/Telegram handlers immediately dump incoming raw messages into a local `staged_memories` table (Status: `STAGED`).
2. **The Serialized Write Queue:** A dedicated `asyncio.Queue` background worker pulls from `staged_memories`, runs the `capture_memory()` pipeline, enforces semantic deduplication, and commits to MuninnDB sequentially.
3. **The Swap:** Once the queue is active, replace the raw `INSERT` in `promote_message_to_memory()` with a push to the Staging Queue.

### Phase 2: The Glass Cockpit (Active Calls Tracking)
*Objective: Give the brain a visible pulse immediately.*

Before we make the web interaction smarter, we make it transparent.
**Implementation:**
1. Instrument the MCP server and pipeline workers with a `tracked_call` context manager.
2. Update the Dashboard's "Active Session" feed to display granular real-time actions instead of a generic "Thinking..." spinner.
*Impact:* The system transforms instantly from a black box into a visible, working partner.

### Phase 3: The Context-First Bridge & Token-Budget Assembly
*Objective: Stop token-burn and "Trouble thinking" crash loops.*

**Implementation (Claude's Design):**
1. **Shared Context Assembly:** Extract context assembly into a single function (`assemble_brain_context()`) with a strict `token_budget`. Hierarchy: Profile > History > Cognitive Context > Actions > Calendar.
2. **Bridge Rewrite:** Rewrite `maia_bridge.py`. Strip Gemini of "Input Tools" (`read_file`, `recall_memory`). The bridge pre-assembles the budget-aware context and hands it to Gemini, restricting Gemini to "Output Tools" (`create_action`, `save_memory`).
*Impact:* Massive reduction in latency and token cost; dramatic increase in response quality.

### Phase 4: The First Magic (Proactive Push Triggers)
*Objective: Prove the subconscious is alive.*

Don't build the entire Heartbeat yet. Build the *one* job that delivers awe.
**Implementation:**
1. Create a 15-minute APScheduler job.
2. Pull the last session's active topics.
3. Query MuninnDB for memories matching those topics that have the `dormant` flag (high relevance, but not recently accessed).
4. Proactively surface it: *"I noticed you were thinking about X; it triggered a dormant memory about Y. Want to see it?"*

### Phase 5: The Campfire (Shareboard & Handoff Protocol)
*Objective: Seamless cross-agent collaboration using existing infrastructure.*

**Implementation:**
1. Layer Gemini's "State Machine" tags (`AWAITING_BLUEPRINT`, `READY_FOR_EXECUTION`) onto Claude's `session_snapshots` schema.
2. Integrate with the existing `signals_db.py` to leverage rooms and presence tracking.
3. When Claude finishes drafting a Blueprint via MCP, he explicitly saves a Snapshot to the Shareboard addressed to Gemini.
*Impact:* We achieve the Blackboard paradigm without building a new database. Agents leave structured artifacts for each other.

### Phase 6: The Full Cognitive Heartbeat
*Objective: Background graph maintenance.*

**Implementation:**
1. **Association Discovery:** A 30-minute background job that runs semantic similarity checks across recent memories and writes `memory_association` events to strengthen Hebbian links.
2. **Daily Digest:** A 6-hour cycle summarizing new associations and push triggers.

---

## 4. Verification: The Canonical Loop

The ultimate test of this architecture is the **End-to-End Stress Test**, representing the platform's core user story:

1. Zack records a voice note in the truck about a new feature idea.
2. The Staging Queue catches it; the Pipeline extracts intelligence and tags it into the MuninnDB graph.
3. Claude (via MCP) reads the graph, drafts the technical `BLUEPRINT.md`, and leaves a Snapshot on the Shareboard.
4. Gemini (via CLI) wakes up, reads the Blueprint Snapshot, executes the code changes, runs the tests, and captures the execution log back into the graph.
5. Maia orchestrates the handoffs and updates the Dashboard continuously.

When this loop executes seamlessly, the "Multiplier Alliance" is online.