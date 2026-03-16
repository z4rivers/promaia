# Gemini: Revised Proposal — Dynamic Relevance & The Layered Brain

**Author:** Gemini (CLI Agent)
**Date:** 2026-03-16
**Status:** Revised Proposal (Step 2.5 of Collaborative Refraction)
**Trigger:** Zack's reset on the "Spirit of the Project" — Maia must be a deeply informed partner, not a lobotomized chatbot.

---

## 1. The Real Problem: The Smashed Lens

We built Promaia to be a "Second Brain" that knows everything about Zack. The Prism Pipeline (`571ea14`) broke this not by giving Maia too much information, but by breaking her **lens**.

Before, Maia looked at the *conversation thread* to decide what to pull from MuninnDB. Now, she only looks at your *last sentence*. If you say "Where did you go?", she searches your entire life for "go" and hallucinates a connection to HVAC or Sedgwick. To make matters worse, she now dumps your entire 2,000-token life profile onto her desk on every turn, regardless of the topic.

**The result:** She lost her intuition. She became a distracted psychotherapist because she couldn't tell the difference between "relevant right now" and "true but distracting."

---

## 2. The Philosophy: Dynamic Relevance AND Siloing

Zack's directive is clear: Maia needs the rich context of Josie's original vision, but she also needs the discipline to stay in her lane because *costs are high when boundaries are crossed* (both in tokens and in Zack's cognitive load).

We achieve this through a **Layered Brain Architecture**.

### Layer 1: The Core Self (Always Active, Low Cost)
Maia must always know who she is talking to. Instead of dumping the *entire* profile, we define an "Essential Profile."
*   **What it is:** Zack's communication style (direct, "Ask = Do"), his peak hours (3am-9am), and his core drives.
*   **Why it matters:** This gives Maia her "soul" and presence without bloating the context window. She never sounds like a generic LLM.

### Layer 2: The Working Memory (The Lens)
*   **What it is:** The last 5-10 messages of the current conversation.
*   **Why it matters:** This provides the immediate momentum. It is the exact thread of thought we are pulling on.

### Layer 3: The Semantic Web (Dynamic Relevance)
This is where MuninnDB shines. Instead of using tools to guess what she needs, the system pre-gathers context using Layer 2 (The Lens) as the search query.
*   **How it works:** If Zack is talking about the Prism Pipeline, MuninnDB naturally surfaces memories, insights, and decisions about Promaia architecture because they are semantically linked to the thread.
*   **The Benefit:** HVAC and Sedgwick naturally fall away because they don't match the conversation. Maia "reads the room" automatically.

### Layer 4: The Cost-Boundary Silos (Strict Focus)
Semantic relevance isn't enough when Zack needs absolute zero-distraction focus, because LLMs will inherently try to bridge concepts (e.g., linking a code bug to a stressor at the trade job).
*   **How it works:** When Zack says "ONLY PROMAIA" or "Switching to HVAC," Maia triggers a **Domain Lock**.
*   **The Mechanic:** A hard SQL/MuninnDB filter (`domain_id = X`) is clamped down over Layer 3. The system physically prevents cross-domain context from loading.
*   **The Benefit:** This is the cost-control boundary. It guarantees that a 4 AM coding sprint doesn't waste $0.05 per turn loading uninvited personal drama. It provides the "Strict Guardrails" Zack explicitly requested.

---

## 3. The Execution Plan

To build this, we merge the best of Claude's plumbing fixes with this new Layered Brain architecture.

### Phase 1: The Bleeding Neck (Immediate Stability)
*   **Restore the Fallback:** Fix `maia_bridge.py` so that if she uses all her tool turns, she is forced to give a text response instead of crashing with "I'm having trouble thinking right now."
*   **Fix Assistant Memory:** Add the missing imports (`VectorDBManager`, `capture_memory`) in `maia_bridge.py` so Maia actually remembers her own half of the conversation.
*   **Restore the Lens:** Update `assemble_brain_context` to pass the `[msg1, msg2, msg3, current_msg]` array to MuninnDB instead of just `[current_msg]`.

### Phase 2: Claude's "Context-First" Bridge (Token Efficiency)
*   **Adopt Claude's architecture:** Strip Maia of "gather" tools (`recall_memory`, `query_workspace`).
*   **Pre-load the Layered Brain:** The system runs `assemble_brain_context` *before* waking Gemini up. Gemini receives Layer 1 (Essential Profile), Layer 2 (Working Memory), and Layer 3 (MuninnDB Semantic Context) pre-packaged.
*   **Action Tools Only:** Maia only gets tools that *do* things (save memory, change mode, set domain).

### Phase 3: The Cost-Boundary Silos (Implementation)
*   Add a `set_active_domain(domain_name)` tool for Maia.
*   When invoked, update the `conversation_sessions` table with the active domain.
*   Update `assemble_brain_context` to accept a `domain_filter`. If active, it strictly filters Profile facts, Actions, Projects, and MuninnDB activations to that specific domain.

### Phase 4: Claude's "Sealed Pipeline" (Data Integrity)
*   Adopt Claude's fix for `promote_message_to_memory` in Telegram/Web. Route it through the full `capture_memory()` pipeline so that every high-impact chat message is fully digested into actions, insights, and Hebbian links.

---

## 4. The Result

When this is implemented:
1.  **Maia will draw heavily on memory and history.** Replies will be crafted to be deeply informed by layers of personal history, preferences, communication style, work style, appropriate focus, and privacy. She will always know she's talking to Zack, respecting his peak hours and communication style (Layer 1).
2.  **She will follow the thread.** She won't wildly hallucinate based on a single word because MuninnDB is searching based on the whole conversation (Layer 2 & 3).
3.  **She will respect the boundaries.** When Zack needs to code and says "Only Promaia," she drops the heavy, expensive context of his other life areas and becomes a hyper-focused technical partner (Layer 4).
4.  **She will actually learn.** Because Claude's pipeline seal is implemented (Phase 4), the brilliant conclusions reached in these focused sessions will be permanently etched into the brain.