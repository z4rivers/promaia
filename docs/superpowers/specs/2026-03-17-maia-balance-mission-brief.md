# MAIA Balance: Mission Brief

**Date:** 2026-03-17 | **Branch:** `maia_balance`

## Goal
Maia adapts to what's happening in each conversation — right instructions, right tools, right context. Not one-size-fits-all.

## The Problem
Maia had an ~800-token static personality prompt telling her WHO to be, leaving no room to DO. Every turn got the same instructions whether Zack said "I'm overwhelmed" or "look at the deployment logs." Result: she fought the user, hallucinated emails, quoted her own stale complaints as truth, and didn't know what time it was.

## Phase 0 Done (Cleanup)
Core prompt trimmed ~800→~300 tokens. 3 duplicate personality constants removed. Temperature fixed (0.7→1.0 per Google). Dead tools cut, `recall_memory` + `read_file` added. Memory relevance floor (0.25). Time injection. MuninnDB updated to v0.4.4. Maia is functional but still one-mode.

## Open Issues
- **Echo chamber**: assistant responses feed back into MuninnDB at high scores — Maia quotes herself
- **Email hallucination**: fabricates plausible emails when data is thin
- **Profile noise**: 40 fields loaded, ~10 useful per turn, rest is noise + duplicates
- **Stale memory bleed**: old debugging sessions activate on loosely related queries
- **One-mode operation**: same prompt, same 11 tools, same context shape every turn

## Research (Key Takeaways)
- Every production system converges on: **Classify → Select → Assemble → Call** (fresh per turn)
- Context rot: irrelevant content actively misleads the model ([Chroma](https://research.trychroma.com/context-rot))
- U-shaped attention: start and end get attention, middle gets lost — cannot be trained away ([Stanford/MIT](https://direct.mit.edu/tacl/article/doi/10.1162/tacl_a_00638/119630/))
- Gemini is most susceptible to contextual drift; needs explicit priority declarations
- Embedding-based routing works in sub-millisecond ([semantic-router](https://github.com/aurelio-labs/semantic-router))
- Anthropic's Agent Skills: progressive disclosure adopted cross-vendor
- Don't load all instructions/tools and say "use what's relevant" — behaviors bleed

## Existing Infrastructure
Silo/open mode (changes context), cognitive mode tool (changes "hat" but not instructions/tools), MuninnDB embeddings, per-call Gemini API (system_instruction + tools can change every turn), email keyword detection, domain aliases.

## Josie's Spirit
This project carries Josie's original vision: an AI that actively learns about its user rather than being told what to be. Personality emerges from relationship, not from scripts. Any design work should honor that.
