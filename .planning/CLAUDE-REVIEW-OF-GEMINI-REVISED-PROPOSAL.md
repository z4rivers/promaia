# Claude: Three-Hat Review of Gemini's Revised Proposal

**Author:** Claude (Opus 4.6)
**Date:** 2026-03-16
**Status:** Step 3 of Collaborative Refraction (Cross-Evaluation)
**Document Under Review:** GEMINI-REVISED-PROPOSAL.md — "Dynamic Relevance & The Layered Brain"

---

## Black Hat (Risks, Problems, What Could Go Wrong)

### 1. The `set_active_domain` tool has a session-routing problem

Gemini says "add a `set_active_domain(domain_name)` tool for Maia" and "update the `conversation_sessions` table." But `handle_tool_call()` currently receives `(ft, websocket, staged_memories)` — it has no access to `session_id` or `chat_id`. The tool handler would need the session context threaded through to actually write the domain lock to the correct row. This isn't a dealbreaker, but it's a plumbing detail the proposal doesn't address. If we get it wrong, `set_focus` writes to the wrong session or throws.

### 2. Layer 4 depends on domain tagging that doesn't exist yet

The hard silo (`domain_id = X` filter) assumes memories, actions, and MuninnDB activations are reliably domain-tagged. In practice:
- `memories.domain` is a TEXT field, not an FK. Many memories have NULL or empty domain values.
- MuninnDB activations return whatever `activate()` returns — there's no guarantee of a `domain` field in the response objects.
- If domain tagging coverage is low, the silo filter will return *nothing*, making Maia appear amnesic in silo mode rather than focused.

The proposal says "hard SQL/MuninnDB filter" but doesn't address what happens when domain tagging is incomplete. We need a fallback for untagged memories (include them? exclude them?) or this will silently break.

### 3. "Essential Profile" is underspecified

Layer 1 says "communication style, peak hours, core drives" — but doesn't define which profile categories or fields qualify. The current `profile` table has categories like `communication`, `personality`, `work`, `identity`, `health`, `relationships`, `lifestyle`. Which ones are "essential"? Without a concrete filter (e.g., `WHERE category IN ('communication', 'personality', 'work', 'identity')`), different implementations will make different choices and the "low cost" promise may not hold.

### 4. Phase 4 (Sealed Pipeline) is vague

"Adopt Claude's fix for `promote_message_to_memory`" — but which fix? The Telegram path (`brain_ops.capture_memory`) already works. The Web path (`maia_bridge.py` lines 247-255) has broken imports. Phase 4 needs to be specific: fix the three missing imports in `maia_bridge.py` and ensure the `capture_memory` call signature matches `memory_pipeline.py`'s `(db, vector_mgr, content, session_id, ...)` pattern.

---

## Yellow Hat (Value, Benefits, What's Strong)

### 1. The Layered Brain metaphor is genuinely clarifying

Naming the layers (Core Self, Working Memory, Semantic Web, Cost-Boundary Silos) creates shared vocabulary that makes architectural discussions faster. When we say "Layer 3 is broken," everyone knows we mean MuninnDB retrieval lost its conversation-thread query. This framing should survive into the final merged plan — it's better than "context assembly" for communication.

### 2. Phase 1 ("The Bleeding Neck") has the right priorities

Restore the fallback, fix the imports, restore the lens. These three fixes map exactly to Root Causes #3, #5, and #1 from the problem statement. Gemini correctly identifies these as the acute wounds — the things that make Maia crash and hallucinate today. Ship these and Maia is usable again, even without the silo work.

### 3. The cost argument for silos is compelling

Framing domain locks as a *cost control* mechanism ("guarantees that a 4 AM coding sprint doesn't waste $0.05 per turn loading uninvited personal drama") makes the business case concrete. On a $20/mo budget, eliminating 2,000 tokens of irrelevant context per message is real money. This reframing also explains why silo mode should be *strict* — it's not just about focus, it's about budget.

### 4. Phase 2 (Context-First Bridge) correctly preserves the output-only tool restriction

Gemini endorses stripping gather tools and pre-loading context — the same direction the Prism Pipeline was heading. The key insight: "the output-only tool restriction was correct, the context assembly was too dumb to compensate." This validates the architectural direction while identifying the specific failure point.

### 5. The "Result" section (Section 4) is well-reframed

After Zack's correction, the outcome description leads with "draw heavily on memory and history" and "deeply informed by layers of personal history, preferences, communication style, work style, appropriate focus, and privacy." This is the right frame — context informs replies, not performs them.

---

## Green Hat (Creative Improvements, What Could Be Better)

### 1. Untagged memories need a policy, not silence

When silo mode is active and a memory has no domain tag, what happens? Three options:
- **Include it** — safe default, but risks the exact bleed we're trying to prevent
- **Exclude it** — strict, but Maia loses access to potentially relevant untagged memories
- **Include but deprioritize** — MuninnDB returns them but they sort below domain-matched results

I'd propose: in silo mode, include untagged memories but cap them at 2 (same pattern as the assistant-memory penalty). This prevents bleed from tagged-wrong memories while keeping genuinely domain-agnostic context available.

### 2. Layer 1 should be a materialized view, not a query

Instead of querying `profile` with a category filter on every message, pre-compute the "Essential Profile" as a ~200-token text block when the profile changes. Store it in `profile_narrative` (table already exists) with a type flag like `essential`. This means Layer 1 is a single row read, not a filtered query — genuinely "low cost" as promised.

### 3. The cross-domain escape hatch needs a mechanism

Gemini's Layer 4 is strict — and should be. But the problem statement says "Cross-domain connections should be flagged, not assumed." In silo mode, if MuninnDB returns a high-confidence hit from another domain, the current plan just drops it. Instead: if a cross-domain activation scores above a confidence threshold (e.g., 0.9), Maia should note it without loading the context: "This connects to something in Heatpup — want me to go there?" This preserves the boundary while respecting genuine connections.

### 4. Domain switching should clear MuninnDB query context

When Zack says "Switching to HVAC," the Layer 2 working memory still contains the last 5 Promaia messages. If we feed those to MuninnDB as the query, we'll get Promaia-relevant memories even with a domain filter (because the *query* is Promaia-flavored). On domain switch, the MuninnDB query should use only the *current message* plus the domain hint — not the conversation history from the previous domain.

### 5. Consider a lightweight "domain detector" before requiring explicit commands

Gemini's plan requires Zack to explicitly say "only Promaia" or "switching to HVAC." This works, but it puts the burden on the user. A lightweight enhancement: when Maia detects that the last 3 messages are all about the same domain (based on project name mentions or MuninnDB activation domain clustering), she could *suggest* activating silo mode: "Looks like we're deep in Promaia — want me to lock focus?" This is opt-in, not automatic, so it respects Zack's control while reducing cognitive load.

---

## Summary for Convergence

Gemini's Layered Brain architecture is the right framing. The four-layer model maps cleanly to the five context sources in `assemble_brain_context()` and gives us shared vocabulary for design discussions.

**Adopt:** Layers 1-4 as the architectural frame. Phase 1 priorities. Phase 2 context-first bridge. Phase 3 domain silos via `conversation_sessions.active_domain`.

**Strengthen:** Define the Essential Profile concretely. Add a policy for untagged memories in silo mode. Thread session context through to the `set_focus` tool handler. Add the cross-domain escape hatch. Handle domain-switch query context correctly.

**Defer agreement on:** Phase 4 (Sealed Pipeline) needs specificity — which exact imports, which exact call signature. Not a disagreement, just needs detail.
