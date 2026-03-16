# Promaia Master Strategic Action Plan
## Final Synthesis (Gemini + Opus + Zack) — March 10, 2026

*This is the finalized roadmap. It integrates the Black Hat structural fixes, the Green Hat growth opportunities, Opus's critical re-sequencing (including the 30-minute wins), and Zack's crucial flag regarding cognitive data security for future productization.*

---

### Phase 0: The 30-Minute Wins (Immediate Impact)
*Before refactoring architecture, these three items can be shipped in under an hour to immediately make the next voice session smarter and safer.*

1. **Clock Awareness:** Add `datetime.now()` to the voice system prompt so Promaia knows what time of day it is.
2. **Prevent Silent Data Loss:** Add a rescue path to `brain_stream` that saves the `staged_memories` array to the database if the WebSocket unexpectedly drops before commit.
3. **Calendar Context:** Feed `_get_calendar_events()` directly into the voice system prompt.

---

### Phase 1: Core Plumbing & Safety (Crawling)
*Addressing the deepest fragilities before adding weight.*

4. **Unify the Memory Pipeline (Fix: Split Brain)**
   - **Action:** Refactor `brain.py`'s voice commit to use the same logic as MCP's `_handle_capture` (write to libSQL/MuninnDB -> generate embeddings -> extract insights -> dual-write to MuninnDB).
5. **Split the MCP Monolith**
   - **Opus Catch:** `mcp_server.py` is 2,188 lines. Break it down into modular tool handlers before it collapses under its own weight.
6. **Implement the "Subconscious" Heartbeat**
   - **Action:** Set up a 15-minute cron (APScheduler) for offline memory clustering ("Idle Mind"), budget checks, and stale domain checks.
7. **MuninnDB Management Ops**
   - **Opus Catch:** Add `delete`, `update`, and `search-by-tag` to the MuninnDB client. Without these, the subconscious background heartbeat cannot perform memory hygiene or consolidate duplicate thoughts.
8. **The Opus CLI**
   - **Action:** Build a lightweight terminal CLI wrapper around the existing MCP tools. Creates a high-powered text interface for deep technical work, sharing the same brain as the Voice Agent.

---

### Phase 2: Cognitive Expansion (Walking)
*Expanding the brain's capabilities now that the foundation is rock solid.*

9. **Voice → Action Bridge ("Hands")**
   - **Action:** Add `create_calendar_event` and `send_email_draft` to the Gemini Live tool declarations, finally letting the voice agent use the hands that MCP already built.
10. **System Prompt Compression & Token Budgeting**
    - **Opus Catch:** Pushing 16 protocol rules, 3 raw conversation summaries, and 15 MuninnDB activations is bloating the Native Audio prompt. 
    - **Action:** Establish a strict token budget. Move deterministic rules (Duplicate Detection) to backend Python logic. Summarize past conversations before injecting them.
11. **Persona Modes & DeBono Hats**
    - **Action:** Build logic to explicitly trigger "Black Hat" or "Red Hat" cognitive modes via voice.

---

### Phase 3: Omnichannel & UI Decoupling (Running)
*With a rock-solid backend, we replace the visual layer and expand touchpoints.*

12. **Decouple and Rebuild the UI ("Glass Cockpit")**
    - **Opus Catch:** Don't decouple the UI until we are ready to replace it. 
    - **Action:** Build pure state-driven API endpoints, then use **v0.dev + Tremor** to generate the new React dashboard components without wrestling with CSS.
13. **Voice-Activated Scratchpad (Multi-modal Sync)**
    - **Action:** The new dashboard dynamically renders lists/notes in real-time as you speak to the voice agent.
14. **Smart Channel Routing & Telegram**
    - **Action:** Background insights route to Telegram for highly urgent/short nudges.
15. **Obsidian "Cognitive Graph" Integration**
    - **Action:** Feed MuninnDB outputs into an Obsidian vault for a tactile, interactive visual map of associative memories.

---

### Phase 4: Productization & Cognitive Security (Future-Proofing)
*Zack's explicit flag for Rose/Josie. This is out-of-scope for the solo-dev phase, but must be the very first step of productization.*

16. **Privacy-First Architecture Audit**
    - **The Threat:** Promaia stores *cognitive data* (inner thoughts, decisions, behavioral patterns). A breach here is worse than a financial breach.
    - **Action:** Before hitting the network or adding users, the system requires an audit focusing on:
      - Eradicating the current "No Auth" dashboard state.
      - Securing locally stored OAuth tokens that allow "act-as-user" capabilities.
      - Assessing the security posture of alpha-state MuninnDB.
      - Designing a unified "Right to be Forgotten" protocol that reliably purges data across both PostgreSQL and MuninnDB simultaneously. 
      - Evaluating the biometric security implications of storing raw WebSocket voiceprints.
