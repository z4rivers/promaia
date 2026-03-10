# Opus Critical Analysis: zBrain/Promaia
## Independent Assessment — March 9, 2026

I went through the actual codebase — not just the architecture docs. Here's what I see.

---

## Where Gemini Was Right

Gemini's evaluation identified real structural issues. I agree with points 1, 2, 3, and 6. But I want to add nuance and correct one significant factual gap.

---

## The Big Surprise: You Already Have Hands

Gemini said zBrain "cannot *do* anything yet" and "lacks hands." **This is wrong.**

Your codebase already contains:

| Module | Size | What It Does |
|---|---|---|
| `promaia/gcal/google_calendar.py` | 19K | Full Google Calendar integration |
| `promaia/mail/` | 16 files, ~200K+ | Complete Gmail system: classify, draft, send, review |
| `promaia/mcp/calendar_tools_server.py` | 10K | MCP tool server for calendar |
| `promaia/mcp/gmail_tools_server.py` | 8K | MCP tool server for Gmail |
| `promaia/mcp/execution.py` | 13K | Action execution layer |
| `promaia/mcp/protocol.py` | 9K | Tool protocol definitions |

The hands exist. They work via the MCP layer (Claude can use them). **But they are completely disconnected from the voice agent.** The Gemini Live API session in `brain.py` only has two tools: `save_conversation_memory` and `commit_staged_memories`. It cannot schedule, email, or act.

> **Fix:** This is actually low-hanging fruit. Adding a `create_calendar_event` function declaration to the `memory_tools` dict in `brain.py` and wiring the tool response to `google_calendar.py` would take hours, not weeks.

---

## The Real Fragility: Two Memory Worlds That Don't Talk

This is the sharpest architectural pain point:

**MCP World** (Claude via mcp_server.py):
- Writes to `brain.memories` (PostgreSQL) with embeddings
- Dual-writes to MuninnDB
- Full intelligence extraction (decisions, insights, preferences, asides)
- Has 16 sophisticated tools

**Voice World** (Gemini Live via brain.py):
- Stages memories in a **Python list** (`staged_memories = []`)
- On commit, writes to MuninnDB only
- On disconnect, runs `generate_session_review` which writes to `brain.audio_session_reviews`
- **Does NOT write to `brain.memories`**
- **Does NOT run extraction pipeline**
- **Does NOT generate embeddings**

This means:
- A memory captured via voice **cannot be found by MCP's semantic search**
- A memory captured via MCP **does appear in voice context** (because voice reads from MuninnDB)
- The intelligence extraction that finds decisions, insights, and preferences **never runs on voice data**

> **Fix:** When `commit_staged_memories` fires, it should follow the same path as `_handle_capture` in `mcp_server.py`: write to `brain.memories`, generate embeddings, run `extract_insights()`, AND write to MuninnDB. One path, one truth.

---

## MuninnDB: Ready But Not Proven Under Load

You asked whether MuninnDB has earned the primary role. My assessment:

**What's working:**
- Clean REST client with graceful degradation (if MuninnDB is down, system continues)
- ACTIVATE retrieval is being used for Live API context injection (15 results)
- Dual-write from MCP captures guarantees data reaches both stores
- Google embedding retirement was survived by switching to OpenAI

**What's concerning:**
- The client only exposes `write`, `write_batch`, `activate`, and `stats`. No `delete`, `update`, or `search-by-tag`. You can put memories in but you can't manage them
- No TTL or expiration mechanism visible in the client — decay happens inside MuninnDB but you have no way to observe or control it
- The `write_batch` method works around a **known MuninnDB bug** (v0.3.6-alpha batch endpoint ignores vault field). You're building on alpha software
- No integration tests. If MuninnDB behavior changes on update, you'd find out in production

> **Verdict:** MuninnDB is earning its spot, but it should remain a *supplementary cognitive layer* alongside PostgreSQL, not replace it. The dual-write philosophy is correct. PostgreSQL is your source of truth; MuninnDB is your associative retrieval engine.

---

## The Missing Subconscious (Background Heartbeat)

Gemini was exactly right here. Your system only thinks when poked.

**What a background worker would enable:**
- Memory consolidation (merge similar memories, increase confidence on corroborated facts)
- Stale task alerts ("You haven't touched HeatPup in 5 days")
- Proactive synthesis ("Your calendar shows a meeting about X, and you captured a note about X yesterday")
- MuninnDB maintenance (audit decay, clean orphaned engrams)

**What it would take:**

| Option | Complexity | Cost | Best For |
|---|---|---|---|
| **APScheduler** (in-process) | Low | Free | Quick win, runs inside FastAPI |
| **Celery + Redis** | Medium | Redis hosting | Heavy processing, retries |
| **Simple cron + management command** | Low | Free | Railway scheduled tasks |
| **AsyncIO background tasks** | Low | Free | Already available in FastAPI |

> **My recommendation:** Start with **APScheduler** or **FastAPI's built-in background tasks** running on a 15-minute interval. Don't introduce Celery until you have workloads that need queuing. Your `engine.py` already has `suggest_next()` and `budget_check()` — those are subconscious functions waiting for a heartbeat to call them.

---

## What Gemini Missed

### The 90K MCP Server Monolith

`mcp_server.py` is **2,188 lines** in a single file. It contains all 16 tool handlers, database queries, embedding generation, Gmail scanning, profile management, and onboarding logic. This is the real monolith in the system — not the dashboard.

If this file breaks, everything breaks. It needs to be split into handler modules.

### The System Prompt Is Already Too Long

With 16 protocol rules, memory instructions, recent conversation context, and MuninnDB activations, the system prompt for the Live API is approaching **2,000+ tokens** before any conversation begins. Gemini's native audio model has limited system instruction capacity compared to text models. You're approaching a ceiling where adding more rules will cause earlier rules to be deprioritized.

### No Error Recovery on Disconnect

When the WebSocket disconnects (line 402-405), staged but uncommitted memories are **silently lost**. The `finally` block only triggers `generate_session_review` for the transcript — it doesn't persist the `staged_memories` list. If you stage 5 memories via tool calls but lose connection before committing, they're gone.

---

## Prioritized Action List

Based on severity and effort:

| # | Action | Effort | Impact |
|---|---|---|---|
| 1 | **Unify memory write path** — voice commit should mirror MCP capture | 1-2 days | Critical |
| 2 | **Persist staged memories on disconnect** — write to DB before cleanup | Hours | High |
| 3 | **Wire calendar tool to voice** — add `create_calendar_event` to Live API | Hours | High |
| 4 | **Add background scheduler** — APScheduler with 15-min heartbeat | 1 day | High |
| 5 | **Split mcp_server.py** — extract handlers into modules | 1-2 days | Medium |
| 6 | **Add MuninnDB management ops** — delete, update, search-by-tag | Days | Medium |
| 7 | **System prompt compression** — move rules to deterministic code where possible | Ongoing | Medium |

---

## The Verdict

Gemini called this "a highly advanced chatbot strapped to a complex notebook." I disagree.

What I see is **a cognitive OS that's 70% wired but has its neurons disconnected from each other.** The pieces are genuinely sophisticated — the extraction pipeline, the MuninnDB integration, the MCP tool server, the Gmail system, the calendar, the guardrails engine. They just don't share a common pathway yet.

The voice agent talks to MuninnDB but not PostgreSQL. The MCP server talks to PostgreSQL but treats MuninnDB as supplementary. The Gmail and calendar modules exist but voice can't reach them. The intelligence extraction runs on MCP captures but not voice captures.

**One unified memory-and-action pipeline would turn this from a collection of impressive parts into an actual operating system.** And that pipeline isn't a months-long project — it's within reach.
