# Gemini: Independent Proposal for Domain Siloing and Context Stability

**Author:** Gemini (CLI Agent)
**Date:** 2026-03-16
**Status:** Independent Proposal (Step 2 of Collaborative Refraction)

---

## 1. Diagnosis of the Failure

The Prism Pipeline unification (`571ea14`) attempted to centralize context gathering into `assemble_brain_context`, but in doing so, it replaced a functional (if messy) retrieval logic with a "dumb" aggregator.

### 1.1 Root Causes

1.  **Semantic Thread Loss:** The previous system used a sliding window of the last 3 conversation messages as the query for MuninnDB. The new system uses only the *current* user message. Without the conversation thread, the vector search returns results based on single words, leading to the "wandering" into HVAC or Sedgwick topics when those words appear or when the search is low-confidence.
2.  **Blind Context Loading:** `assemble_brain_context` currently loads ALL profile items with confidence > 0.7 and ALL pending actions/projects unconditionally. This creates a massive context dump (2k+ tokens) of irrelevant life noise that confuses the LLM's focus.
3.  **Fatal Error Handling (The "Thinking" Crash):** In `maia_bridge.py`, the turn-exhaustion fallback (the `else` block for the tool loop) was removed. If Gemini makes 4 tool calls without returning text, the response becomes `None`, causing a crash and the "I'm having trouble thinking" error.
4.  **Implicit Associations:** The `PERSONALITY_SYSTEM_PROMPT` encourages "connecting dots" but lacks a "stay in your lane" directive. Without hard silos, the model's natural tendency to associate concepts (ADHD-like wandering) is amplified by the polluted context.

---

## 2. Proposed Solution: The "Hard Silo" Architecture

I propose moving from "soft relevance" (hoping the search finds the right thing) to "hard filtering" (physically preventing the wrong thing from entering the context).

### 2.1 Domain-Level Scoping

We will introduce an explicit `domain_filter` throughout the context assembly pipeline.

*   **Session Focus Tracking:** Update `conversation_sessions` to store an optional `active_domain_id`.
*   **Context Filtering:** Modify `assemble_brain_context` to accept a `domain_id`.
    *   **SQL Queries:** `SELECT ... FROM actions WHERE domain_id = ? AND status = 'pending'`
    *   **MuninnDB:** Pass the `domain_id` as a metadata filter to the vector search. If we are in "Promaia" mode, MuninnDB *must not* return HVAC memories, even if they match semantically.
    *   **Profile Filtering:** Tag profile fields with domains. Facts like "Zack works at Climate Control" are tagged `hvac`. Facts like "Zack uses Gemini CLI" are tagged `promaia`. Only load domain-matching or "global" profile facts.

### 2.2 The "Clean Slate" Protocol

When Zack says "Focus on Promaia" or "Switching to HVAC":
1.  **State Update:** The agent calls a new tool `set_session_domain(domain_name)`.
2.  **Snapshot:** A session snapshot is taken of the *current* state before switching.
3.  **Context Reset:** The `active_domain_id` for the session is updated. The very next turn will have a completely different context window, free of the previous domain's noise.

### 2.3 Stability & Reliability Fixes

1.  **Restore Forced Fallback:** Re-implement the "no-tools" final call in `maia_bridge.py`. If 4 turns are hit, call Gemini one last time with `tools=[]` and a directive to "Answer with what you know."
2.  **Restore Search Window:** Change the MuninnDB query from `[user_message]` back to `[msg1, msg2, msg3, user_message]`.
3.  **Fix Persistent Memory Imports:** Add missing `VectorDBManager` and `capture_memory` imports to `maia_bridge.py` to ensure assistant responses are actually remembered.

---

## 3. Rationale

*   **Safety over Relevance:** In a "Second Brain," it is better to return *less* context that is 100% relevant than *more* context that is 50% noise. Hard silos ensure this.
*   **Computational Efficiency:** Reducing context pollution saves tokens and reduces "reasoning drift" in the model.
*   **User Trust:** By implementing the "Clean Slate" protocol, we give Zack the "Strict Guardrails" he requested. The system stops being a "junk drawer" and starts being a set of organized workrooms.

---

## 4. Risks & Mitigations

*   **Risk:** Over-siloing might prevent useful cross-domain insights.
    *   **Mitigation:** Provide a "Global" domain or a `cross_domain_search` tool that Maia can explicitly invoke if she suspects a connection, rather than loading it automatically.
*   **Risk:** MuninnDB's metadata filtering might be slow or return empty if tagging is inconsistent.
    *   **Mitigation:** Implement a "Tagging Auditor" (background task) that identifies untagged memories and asks for classification, ensuring the silos remain healthy.

---

## 5. Verification Plan

1.  **The "Promaia Only" Test:** Set domain to Promaia. Ask about HVAC leads. Result: "I don't have access to HVAC context right now. Should we switch domains?"
2.  **The "Turn Crash" Test:** Simulate a tool-loop exhaustion. Result: A coherent text response instead of a crash.
3.  **The "Memory Loop" Test:** Verify that assistant responses now appear in subsequent MuninnDB searches (requires the import fix).
