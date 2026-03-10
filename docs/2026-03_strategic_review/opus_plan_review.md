# Opus Review: Strategic Action Plan
## What's Right, What's Missing, What's Misordered — March 10, 2026

I read through the plan. Gemini did a good job structuring it, and the Black Hat / Green Hat merge was the right call. But there are real gaps and one significant sequencing error. Here's my critique:

---

## What's Right

- **Phase 1 priorities are correct.** Unified memory pipeline first, then disconnect safety, then hands. That's the right dependency order.
- **The "don't build the dashboard until Step 5" warning** is smart. Rebuilding UI on tangled logic is throwing good money after bad.
- **The subconscious heartbeat** is correctly positioned as foundational.

---

## What's Missing

### 1. The MCP Server Split Disappeared
My Black Hat analysis flagged `mcp_server.py` at **2,188 lines** as the real monolith — not the dashboard. It's the single point of failure for *all* of Claude's brain tools. This isn't in the action plan at all.

> **Recommendation:** Add to Phase 1 or early Phase 2. This is a refactor, not a feature — it doesn't change behavior, just improves resilience.

### 2. No MuninnDB Management Operations
The MuninnDB client can `write` and `activate` but cannot `delete`, `update`, or `search-by-tag`. Without these, you can't:
- Clean up bad memories
- Correct misinformation
- Do any kind of memory hygiene

The background heartbeat (Phase 1, Item 4) will need these operations to do memory consolidation.

> **Recommendation:** Add MuninnDB management ops to Phase 1, bundled with the heartbeat work.

### 3. The Opus CLI
You asked about this directly and Gemini mentioned it once in passing. It deserves its own line item. The MCP tool servers already exist — an Opus CLI is literally a thin wrapper. It gives you a third surface (Voice, Dashboard, Terminal) with almost zero effort.

> **Recommendation:** Phase 1 or Phase 2. It's hours of work, not days.

### 4. System Prompt Compression Strategy
Gemini's plan says "Move Protocol Rules to Backend" (Phase 2, Item 6). That's correct but incomplete. The system prompt is also bloated by:
- Recent conversation summaries (3 sessions injected raw)
- MuninnDB activations (15 results injected raw)
- Verbose instructions for the confirmation loop

We need a *compression strategy*, not just rule extraction. The prompt needs a token budget.

---

## What's Misordered

### UI Decoupling Is Too Early
Phase 2, Item 5 says "Decouple the UI Monolith" before building any new features on the dashboard. But here's the thing: **the dashboard barely exists yet.** You said yourself it's "the MASSIVE to-do item I haven't even started to wrap my head around."

Decoupling logic from UI makes sense when you have a mature, tangled UI. Right now, `dashboard.py` is mostly data queries feeding Jinja2 templates. It's not deeply entangled — it's just *unfinished.*

> **Recommendation:** Move UI decoupling to Phase 3, *alongside* the dashboard rebuild. When you're ready to build the v0/Tremor glass cockpit, that's when you design the clean API contracts. Don't spend time decoupling something that's about to be replaced anyway.

### Temporal Context Should Be Phase 1
Calendar/clock awareness (currently Phase 2, Item 7) is trivially easy to implement — `_get_calendar_events()` already exists — and it dramatically improves voice session quality. It should be bundled with the Voice → Action Bridge work since they both touch the same system prompt setup code.

---

## What I'd Add: Phase 0 (The 30-Minute Wins)

Before Phase 1's multi-day refactors, there are things we could ship *tonight* that have outsized impact:

| Win | Effort | Impact |
|---|---|---|
| Add `datetime.now()` to voice system prompt | 5 min | Agent knows what time of day it is |
| Persist `staged_memories` to DB on disconnect | 30 min | Zero data loss risk |
| Add `_get_calendar_events()` to voice context | 15 min | Agent knows your schedule |

These three changes would make the next voice session noticeably smarter with under an hour of work.

---

## Summary

The bones are right. The gaps are:
1. MCP server split (missing entirely)
2. MuninnDB management ops (missing entirely)
3. Opus CLI (mentioned but not itemized)
4. System prompt compression (incomplete — needs token budget, not just rule extraction)
5. UI decoupling timing (too early — move to Phase 3)
6. Temporal context timing (too late — move to Phase 1 or Phase 0)

My recommendation: **Add a Phase 0 for the 30-minute wins**, resequence temporal context into Phase 1, push UI decoupling to Phase 3, and add the three missing items. Then let Gemini revise the plan with these inputs.
