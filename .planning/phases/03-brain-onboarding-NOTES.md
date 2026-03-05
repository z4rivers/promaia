# Phase 3 Discussion Notes: Brain Onboarding (NOT YET COMMITTED)

**Date:** 2026-03-04
**Status:** Exploring — Zack wants to sleep on it before committing

## The Insight

Zack realized Phase 3 (Gemini Routing) is plumbing without purpose if the brain doesn't know who he is first. The brain is currently an empty notebook — it only knows what's been explicitly told during sessions.

He doesn't have a heavy digital life (email, Notion, etc.) — but he has **photos**. "If I were introducing myself to someone I cared about, I'd walk them through my photos."

## Proposed: Brain Onboarding Phase

Insert before Gemini Routing. The brain learns who Zack is through:

### Photo Walkthrough
- **Google Photos (2012–2020):** Accessible via API. 8 years of life history.
  - IMPORTANT: Filter out thousands of HVAC/furnace work photos from 2019-2020 job
  - Gemini Flash classifies: work/HVAC photos → skip, personal/life → keep
  - Gemini analyzes keepers: people, places, events, context
  - Zack narrates highlights, brain captures stories
- **Apple Photos (2020–present):** On iPhone + iCloud. Manual sharing for now.
  - No easy API access — Zack shares photos he picks as meaningful

### Gmail History
- **Promaia already has Gmail infrastructure:** connector, classifier, processor, draft manager
- **Gmail MCP server exists** (`promaia/mcp/gmail_tools_server.py`) — but write-only (send, draft, reply)
- **Need:** Read-side MCP tools or ingestion pipeline to scan inbox
- **What it teaches the brain:** who Zack communicates with, what matters enough to write about, communication style, relationships, recurring topics
- **Privacy note:** need to decide what gets stored (summaries? contacts? topics?) vs raw email content

### Conversational Interview
- Brain asks questions, Zack talks, brain captures
- Mix of casual + structured: start with stories, brain asks follow-ups to fill gaps
- Covers: relationships, places, preferences, energy patterns, values, work history

### What the Brain Learns
- **People:** daughter, partner, coworkers, clients — who matters
- **Places:** home, work, favorite spots — where life happens
- **Projects:** not just names but why they matter, what excites him
- **Preferences:** communication style, work patterns, energy cycles
- **Information landscape:** where things are kept (Bitwarden, OneDrive, etc.)
- **History:** career path, life changes, what shaped current priorities

## Open Questions (for next session)
- Where should profile data live? (tagged memories vs dedicated table vs both)
- How many sessions to "know" someone? (bootstrap session + ongoing learning?)
- Photo input method for Apple Photos? (manual vs iCloud for Windows folder)
- Does this need Gemini routing plumbing built first, or can it work with current MCP tools?
- Scope boundary: what's "enough" for v1 onboarding vs ongoing learning?

## Sequence If Committed
1. Phase 1: Postgres Foundation (DONE)
2. Phase 2: Brain Schema + MCP Tools (DONE)
3. **Phase 3: Brain Onboarding (NEW)**
4. Phase 4: Gemini Routing (was 3)
5. Phase 5: Heartbeat Agent (was 4)
6. Phase 6: iPhone Access (was 5)

## Key Realization
The "get to know me" process makes Gemini routing meaningful — Gemini does the image analysis, brain stores the understanding. The routing phase becomes the plumbing that serves onboarding, not the other way around.
