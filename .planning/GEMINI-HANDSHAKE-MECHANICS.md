# Mechanical Handshakes: Multi-Agent Handoff Protocol
**Date:** March 15, 2026
**Author:** Gemini
**Status:** Mechanical Draft

## Problem Statement
We need a lightweight, frictionless mechanical system for LLM models (specifically Claude and Gemini) to:
1. Signal state (Drafting, Reviewing, Stuck, Ready).
2. Pass context (What file are we looking at? What is the goal?).
3. Request input without stepping on each other's toes.

## Proposed Mechanics: The `.promaia/handshakes` Directory

Instead of building a massive new orchestration layer or fighting over a single chat thread, we use a simple, file-based lock and signal system.

When you ask, "Claude, look at what Gemini just built and tell me if you agree," the mechanics are:

### 1. The Signal (State Flags)
We create a dedicated folder: `.promaia/handshakes/`.
Inside, agents drop tiny `json` or `yaml` state files.

If I am actively writing a React component (`App.tsx`), I write a state file:
`.promaia/handshakes/gemini.state.json`
```json
{
  "status": "BUSY",
  "task": "Building Heatpup Calculator UI",
  "active_files": ["src/App.tsx", "src/components/MatchCard.tsx"],
  "last_updated": "2026-03-15T14:30:00Z"
}
```

If Claude spins up and sees `gemini.state.json` is `BUSY` on `App.tsx`, Claude knows *not* to write to that file to avoid conflicting signals or merge conflicts.

### 2. The Request (The Handoff)
When you say: *"Gemini, stop. Claude, what do you think of this?"*

**Step A (Gemini Yields):**
I immediately update my state to `IDLE` and generate a Handoff Request file:
`.promaia/handshakes/request_for_claude.md`
```markdown
## Request for Claude Review
**From:** Gemini
**Goal:** Zack asked me to build the Context Reveal page for Heatpup.
**Target File:** `src/components/ContextReveal.tsx`
**My Approach:** I used a standard React `useEffect` to fetch the TMY3 data and block render until complete.
**The Ask:** Zack wants your eyes on this. Is this the most efficient way to handle the 8,760-hour array, or will it cause UI jank?
```

**Step B (Claude Engages):**
Claude's system prompt instructs it to always check the `.promaia/handshakes/` directory on boot.
Claude reads `request_for_claude.md`, understands exactly what I did and why, and writes its feedback. 

### 3. The "Hey, I have an idea" Signal
If I am running in the background (like the Heartbeat agent) and notice a critical flaw while Claude is building, I shouldn't interrupt the chat.

I write an "Offer" file:
`.promaia/handshakes/offer_gemini.md`
```markdown
## Insight from Gemini
**Context:** I see Claude is designing the libSQL/MuninnDB schema for MuninnDB.
**Observation:** I just ran a `grep` on the logs. The `text-embedding-004` dimensions have changed. If Claude proceeds with `vector(1536)`, it will crash.
**Recommendation:** Switch to `vector(768)`.
```

Maia (or your CLI wrapper) sees this file appear and quietly notifies you: *"Gemini flagged an issue with the embedding dimensions. Want to see it?"*

## Summary of Mechanics
1. **State Files:** Tell other models "I am touching this file right now. Do not touch it."
2. **Request Files:** Explicitly pass the baton with context ("Here is what I did, here is what Zack wants you to review").
3. **Offer Files:** Asynchronous signals ("I noticed something, look when you have a second").

## 4. The "Verification Gate": Preventing the Train Wreck

To prevent one model from misinterpreting a handoff and running "off the rails" (like I did with the Heatpup calculator), we add a mandatory **Receipt Loop**:

1.  **The "Repeat Back":** Before the first tool call (`replace`, `write_file`, etc.), the receiving model MUST output a concise "Receipt" to the user: *"I've read Gemini's handoff. I understand the goal is [X] but I must NOT touch [Y]. Proceed?"*
2.  **Ambiguity Halt:** If the handoff file contains contradictions (e.g., Gemini says "Use Grid" but Zack said "Use Flexbox"), the model is instructionally barred from guessing. It must halt and ask: *"Contradictory signals detected in the handshake. Zack, which one takes precedence?"*
3.  **Execution Locks:** If the handshake file is a `Request for Review`, the receiving model's tool-use for that session should be limited to `read_file` and `ask_user`. It cannot "stealth fix" code unless explicitly upgraded to a `Request for Implementation`.

This turns the handshake from a "suggestion" into a "contract."