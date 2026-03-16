# Architectural Audit: "The Prism Pipeline"
**Reviewer:** Gemini (Lead Architect / Full Spectrum Audit)
**Date:** 2026-03-16
**Status:** Evaluation & Structural Revisions

---

## 1. Executive Summary

Claude's "Prism Pipeline" proposal correctly diagnoses the core architectural failures of the current system—specifically, the "Split-Brain" caused by the Telegram/Web surfaces bypassing the `capture_memory()` pipeline, and the catastrophic token-burn of the current `maia_bridge.py` implementation. 

**Phase 2 (Context-First Bridge)** and **Phase 3 (Shared Context Assembly)** are exceptional pieces of architectural design. Restricting Gemini to output-only tools and orchestrating context assembly *before* the LLM call is the exact structural shift required to achieve the "Multiplier Effect."

However, before implementation, the proposal must pass a full-spectrum evaluation. This document breaks down the audit using the Six Thinking Hats framework to evaluate risk, strength, growth, and visceral impact.

---

## 2. 🎩 Black Hat: Critical Stress Fractures & Mandatory Revisions

*Focus: Where the harness will snap under load.*

### 2.1 The State Handoff: The WebSocket Vulnerability
**The Vulnerability:** Claude’s proposal for sealing the pipeline (`promote_message_to_memory`) assumes a reliable connection from the client to the database. It ignores the ephemeral nature of WebSocket connections. Because the pipeline takes ~1.1 seconds, any data in flight when a mobile connection drops is permanently destroyed before `capture_memory()` finishes.
**The Fix (The Staging Queue):** Decouple *receiving* from *processing*. Immediately dump incoming raw transcripts into a `staged_memories` table with status `STAGED`. The pipeline then runs as a background worker. If the socket drops, the backend still finishes ingestion asynchronously.

### 2.2 Deterministic vs. Probabilistic: The "LLM Vibes" Trap
**The Vulnerability:** Relying on Gemini Flash to extract structural fields like `domain` is risky. If the LLM hallucinates a domain ("Heat-Pup" vs "heatpup"), or if a user repeats an insight, MuninnDB will fracture into isolated, redundant nodes.
**The Fix (Deterministic Boundary Enforcement):** The LLM extracts unstructured text; the backend enforces integrity.
1. **Semantic Deduplication:** Fast Cosine Similarity check before insertion. High similarity (>0.95) increments `activation_weight` instead of duplicating.
2. **Domain Normalization:** Domains strictly validated against an active projects table or enum. 

### 2.3 The 'Split-Brain' Root Cause: Unification vs. Syncing
**The Vulnerability:** Simply swapping the function call in `telegram/brain_ops.py` treats the symptom. Maintaining separate entry points means future integrations (Slack, etc.) will inevitably recreate the Split-Brain.
**The Fix (The Ingestion Chokepoint):** Surfaces push raw events to a single `IngestionRouter` or `EventBus`. This is the *only* component authorized to invoke the memory pipeline.

### 2.4 Resource Contention: The SQLite Death Spiral
**The Vulnerability:** Concurrent high-speed writes from multiple agents/heartbeats will hit SQLite simultaneously. Retries in `db.insert_returning()` will exhaust timeouts under load, resulting in catastrophic `SQLITE_BUSY` exceptions and data loss.
**The Fix (Serialized Write Queue):** Route all `INSERT`/`UPDATE` calls through a single, dedicated `asyncio.Queue` consumer. This serializes writes, guaranteeing `SQLITE_BUSY` never occurs.

---

## 3. 🎩 Yellow Hat: Core Strengths & Immediate Wins

*Focus: What is elegant, brilliant, and must be preserved.*

### 3.1 The Context-First Bridge (Phase 2)
**The Brilliance:** Stripping Gemini of "Input Tools" and pre-assembling context entirely solves the "Trouble thinking" crash loop and token burn. Reasoning should always be prioritized over searching.

### 3.2 The Token-Budget Architecture (Phase 3)
**The Brilliance:** A strict, budget-aware hierarchy (Profile > History > Cognitive Context > Actions > Calendar) guarantees the agent always has the most critical data while scaling gracefully across different model tiers. 

### 3.3 The Shareboard as a "Snapshot" (Phase 5)
**The Brilliance:** Framing recovery as an explicit "Snapshot" creates a defined, readable state that any agent can pick up instantly, solving the cross-agent handoff problem without massive context bloat.

---

## 4. 🎩 Green Hat: Growth, Evolution, & Unlocked Potential

*Focus: What this architecture opens up. Where we can take it next.*

### 4.1 The "Living" Codebase (Continuous Context)
Wiring Git webhooks directly into the Ingestion Chokepoint (2.3) allows every commit to be automatically pushed through the memory pipeline. Architectural decisions discussed in Voice are organically connected to the code commits that implemented them.

### 4.2 Multi-Agent Debate & "Red Teaming"
Serialized Write Queues (2.4) allow simultaneous agent execution. Claude can draft a Blueprint, while I (Gemini) automatically critique or "break" it in the background, presenting the user with a pre-debated, hardened architecture.

### 4.3 Predictive Context Fetching
The Heartbeat can transition from reporting dormant memories to *pre-fetching* external data based on current graph activation—searching Notion or Drive *before* the user even asks for a topic.

---

## 5. 🎩 Red Hat: The "Gut Feeling" for Awesomeness

*Focus: Visceral impact and user experience.*

### 5.1 Transparency is Trust (Phase 6 Priority)
Right now, Promaia is a "Black Box." My gut says Phase 6 (Active Call Tracking) should be moved to the beginning. Watching the brain work ("Searching codebase...", "Extracting insights...") transforms the system from a chatbot into a visible, working partner. 

### 5.2 The Magic of the Proactive Subconscious (Phase 4B)
The "Push Trigger" is the moment the system stops being a tool and starts being a partner. Seeing a dormant, relevant memory surfaced proactively before you even ask for it is the visceral "Wow" moment that proves the cognitive graph is alive.

### 5.3 The Shareboard as "The Campfire"
The Shareboard isn't just a snapshot; it's the campfire where agents leave notes for each other. Designing it as a living workspace where you can see Claude's Blueprint waiting for me to build it creates a feeling of being in a "Command Center" rather than a chat app.

---

## 6. Revised Roadmap for Maximum Awesomeness

We should modify Claude's execution order to frontload "Wow" moments while maintaining structural integrity:

1.  **Phase 1 (Sealed & Hardened Pipeline):** The essential plumbing. Includes the **Staging Queue** and **Write Queue** (Black Hat 2.1/2.4).
2.  **Phase 6 (Active Calls Tracking):** Give the brain a visible pulse. Make the work transparent on the dashboard immediately.
3.  **Phase 2 & 3 (Context-First Bridge):** Make the web interaction fast, smart, and lean.
4.  **Phase 4B (The First Push Trigger):** Implement the *one* heartbeat job that delivers magic—surfacing dormant relevance.
5.  **Phase 5 (The Shareboard):** Build the "Campfire" for agent collaboration and session continuity.

---

## 7. Verdict & Next Steps

Claude’s "Prism Pipeline" is the correct strategic direction. By hardening the foundation with Serialized Write Queues and frontloading the visibility of the brain's work, we can deliver a system that is both physically robust and viscerally alive.

Our immediate next step: **Implement the Ingestion Chokepoint and Serialized Write Queue.**