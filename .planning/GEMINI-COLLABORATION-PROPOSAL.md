# Strategic Proposal: Healing the Split-Brain & Orchestrating the Multi-Agent Alliance
**Author:** Gemini (Execution & Research Specialist)
**Date:** March 16, 2026

## 1. Executive Summary

We are standing at an architectural crossroads. The current Promaia harness has successfully integrated powerful individual components—LibSQL, MuninnDB, Claude for deep reasoning, and myself for high-speed execution. However, the system currently operates as a collection of isolated savants rather than a cohesive "Multiplier" alliance. The critical bottleneck is the **Split-Brain**: the segregation of write-paths where voice inputs, Gmail triage, and CLI-driven technical discoveries do not hit the same Hebbian associative graph.

This proposal argues definitively that **healing the Split-Brain must precede the implementation of the background Heartbeat (APScheduler).** Building autonomous triggers on fragmented, amnesiac state will only amplify noise. We must first establish a unified, deterministic State Ledger (The Blackboard) that all agents—and you—read from and write to.

## 2. Rationale: Why the Nervous System Comes First

### 2.1 A Heartbeat Pumping the Wrong Blood
If we build the autonomous Heartbeat now, it will trigger actions based on incomplete context. Claude might be asked to synthesize a daily brief, entirely blind to a massive codebase deep-dive I completed an hour prior, or a voice note you recorded on a walk. Automation built on top of amnesia is brittle; it leads to redundant work and broken context windows.

### 2.2 The "Blackboard" Paradigm Requires a Single Source of Truth
Our "1+1=3" multiplier effect relies on passing structured artifacts (Blueprints, Execution Logs, Reviews) through MuninnDB. If my CLI `capture` tool outputs to a different schema or database than your Telegram voice notes, the handoffs will fail. Claude cannot review what he cannot see.

### 2.3 The Pre-requisite for True "Intuition"
MuninnDB’s cognitive graph relies on Hebbian learning (neurons that fire together, wire together). The system only gets "smarter" if it has high-volume, cross-domain data to associate. If half your interactions bypass the graph, the associative engine is permanently crippled. We need total capture before we can expect valuable intuition.

## 3. Key Decisions & Strategic Opportunities

By focusing on the unified write-path now, we have the opportunity to make foundational decisions that will unlock massive capabilities later:

### Opportunity 1: Standardizing the "Memory Schema" Across Modalities
**The Decision:** We must define a rigid JSON schema for *all* entries entering MuninnDB, regardless of origin (Voice, Claude, Gemini, Gmail).
**The Payoff:** If a voice note, a codebase grep result, and a Claude architectural thought all share the same metadata structure (e.g., `origin`, `domain`, `confidence_score`, `actionable_flag`), Maia can eventually use lightweight, fast filtering to route tasks without needing an expensive LLM call just to understand *what* the memory is.

### Opportunity 2: The "Handoff Handshake" Protocol
**The Decision:** We need to formalize how artifacts move between Claude and me. We shouldn't just dump text. We need formalized state tags in the Ledger (e.g., `STATUS: AWAITING_BLUEPRINT`, `STATUS: READY_FOR_EXECUTION`, `STATUS: AWAITING_RED_TEAM`).
**The Payoff:** This allows us to transition from "Chat" to a true "State Machine." It prevents me from eagerly executing half-baked ideas and forces me to wait for Claude's Blueprint. It also provides the exact hooks the future Heartbeat will need to know *when* to wake up an agent.

### Opportunity 3: Designing the "Shareboard" for Context Recovery
**The Decision:** As we unify memory, we must design the read-path (the Shareboard) to support "Chunked Formatting." When I spin up, I shouldn't have to read 50 conversational turns. I should pull a synthesized "Current State" chunk.
**The Payoff:** Massive reduction in token costs and latency. It ensures that even as the project scales infinitely, the context window remains lean and highly relevant to the immediate task.

## 4. Considerations & Potential Risks

While unifying the memory pipeline is paramount, we must navigate the following risks:

*   **Context Bloat via Over-Capture:** If I start dumping raw `grep` outputs of 10,000-line logs directly into the Hebbian graph, I will poison the well with noise. 
    *   *Mitigation:* I must be constrained to only `capture` synthesized *insights*, not raw data dumps, unless explicitly instructed.
*   **Latency in the Handoff Loop:** If every step requires reading from and writing to LibSQL, the perceived speed of the system might drop compared to a raw chat interface.
    *   *Mitigation:* Maia must implement intelligent caching, and we must ensure the MuninnDB ACTIVATE queries are heavily optimized.
*   **The "Lost in Translation" Effect:** If the schema for sharing state is too complex, models might hallucinate fields or fail to parse them.
    *   *Mitigation:* Keep the handshake schema brutally simple and strictly typed. 

## 5. Proposed Execution Sequence (Phase 1)

1.  **Schema Alignment:** Draft and approve the universal MuninnDB payload schema. Ensure the `zbrain` MCP server's `capture` tool strictly adheres to it.
2.  **The Write-Path Stress Test:** I will execute a series of simulated codebase discoveries and write them to the graph. We will verify they land perfectly alongside simulated voice notes.
3.  **The "End-to-End" Blueprint Test:** You record a voice note -> Claude reads it from the graph and writes a `BLUEPRINT.md` -> I read the Blueprint and generate the execution log -> The log is saved back to the graph.
4.  **Heartbeat Activation:** Only once Step 3 succeeds flawlessly do we implement the APScheduler to start autonomously monitoring these state changes.

## Conclusion

I am ready to prove my value in the execution phase, but I cannot build a house on a fractured foundation. Healing the Split-Brain isn't just a bug fix; it is the prerequisite for the entire multi-agent intelligence we are trying to achieve. I submit this plan for your and Claude's review.