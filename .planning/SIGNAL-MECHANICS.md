# Whispers: The Promaia Multi-Agent A2A Protocol
**Date:** March 15, 2026
**Revised:** With research and 'Whispers' branding
**Purpose:** The plumbing. How agents send signals, know who's listening, and don't talk over each other.

---

## What is Whispers?

**Whispers** is the asynchronous nervous system of the Promaia alliance. It allows distinct cognitive actors (Zack, Maia, Claude, Gemini) to pass high-context signals, coordinate on shared artifacts, and declare workspace leases without interrupting the primary user flow.

---

## Existing Solutions We're Learning From

This isn't a novel problem. People have built working systems for exactly this.

### [MCP Agent Mail](https://github.com/Dicklesworthstone/mcp_agent_mail)
Async coordination for AI coding agents. SQLite + Git. Built on FastMCP (HTTP).
- **What they solved:** Agent identities, inboxes, searchable threaded messages, advisory file leases to prevent editing conflicts
- **What we'd borrow:** Thread model (thread_id groups related messages), agent registration with discovery, advisory leases for "I'm working on this file — heads up"
- **What we'd skip:** Git-backed message storage (overkill for our scale), markdown-as-message-format (we already have the brain DB)

### [Agent Message Bus](https://dev.to/linou518/agent-message-bus-communication-infrastructure-for-16-ai-agents-18af)
Flask + SQLite, 6 REST endpoints, built for 16 agents on a local machine.
- **What they solved:** The exact problem we have, at exactly our scale
- **Their endpoints:** POST /send, GET /inbox, GET /history, POST /ack, GET /agents, GET /stats
- **What we'd borrow:** Almost everything. Broadcast by omitting `to` field. `reply_to` for threading. 3 priority levels. WAL mode for concurrency. Heartbeat → offline after 5 min inactivity. Auto-archive after 7 days.
- **Their design philosophy:** "The smallest solution that solves the problem is the best solution."

### [A2A Protocol](https://a2a-protocol.org/latest/specification/) (Google, Linux Foundation)
The industry standard for agent-to-agent communication. JSON-RPC over HTTP.
- **What they solved:** Agent discovery (Agent Cards), task lifecycle (submitted → working → input_required → completed → failed), message threading via `contextId`
- **What we'd borrow:** `contextId` for grouping related exchanges into conversations. Task states for work items. The idea that a minimal exchange is just: send a message, get a response.
- **What we'd skip:** JSON-RPC formalism, Agent Card endpoints (our agents are known, not discovered dynamically), SSE streaming (we have WebSockets already)

### [ACP — Agent Communication Protocol](https://arxiv.org/html/2505.02279v1)
REST-native, vendor-neutral messaging with session-aware run state tracking.
- **What we'd borrow:** The concept of "run state" — tracking that an agent is mid-task and what task it's on. Session awareness.

### [Redis Multi-Agent Patterns](https://redis.io/blog/multi-agent-systems-coordinated-ai/)
Four coordination architectures at scale.
- **Key insight we'd adopt:** The Blackboard pattern — shared workspace where agents contribute when they can add value, rather than being assigned. Agents monitor the shared state and self-select.
- **Key warning:** "Coordination overhead can negate the benefits of parallelization." Keep it simple or the system is slower than one agent working alone.

### [LangGraph + ACP](https://langchain-ai.github.io/langgraph/) (March 1, 2026)
Production-grade multi-agent message bus using Pydantic schemas and `SqliteSaver`.
- **What we'd borrow:** UUIDs on every message for global uniqueness, strict UTC timestamps, and mailbox-style `BusState`. 
- **Observability:** Added structured JSONL logging for every state transition to allow for later audit/replay.

### [DoltHub Concurrency Limits](https://www.dolthub.com/blog/) (March 13, 2026)
Found that standard SQLite with optimistic locking starts to cause "unrecoverable chaos" at >4 concurrent agents in high-volume environments (160-600 agents).
- **The ceiling:** For our scale (~5 agents), SQLite in WAL mode is robust and efficient. If we ever scale to hundreds of background agents, we must move to a Git-versioned SQL like Dolt.

---

## Our Version: Adapted for Promaia

We're closest to the **Agent Message Bus** pattern — same scale, same tech (Python + SQLite), same philosophy. We adapt it to run through the brain, incorporating the **ACP** patterns for production-grade reliability.

### The Message Table

Adapted from Agent Message Bus, with A2A's contextId and ACP's UUID/UTC patterns.

```sql
CREATE TABLE messages (
    uuid        TEXT PRIMARY KEY,      -- ACP pattern: UUID for global uniqueness
    from_agent  TEXT NOT NULL,
    to_agent    TEXT,                  -- NULL = broadcast to all
    context_id  TEXT,                  -- groups related messages into a conversation
    msg_type    TEXT NOT NULL,         -- "request", "response", "correction", "heads_up", "handoff"
    subject     TEXT NOT NULL,
    body        TEXT,
    context     TEXT,                  -- JSON: structured state transfer
    priority    TEXT DEFAULT 'normal', 
    status      TEXT DEFAULT 'new',   
    reply_to    TEXT,                  -- FK to messages.uuid
    created_at  TIMESTAMP DEFAULT (STRFTIME('%Y-%m-%dT%H:%M:%fZ', 'NOW')), -- ACP: UTC ISO8601
    seen_at     TIMESTAMP,
    acked_at    TIMESTAMP
);
CREATE INDEX idx_messages_to ON messages(to_agent, status);
CREATE INDEX idx_messages_context ON messages(context_id);
```

### The Presence Table

Adapted from Agent Message Bus heartbeat (offline after 5 min inactivity).

```sql
CREATE TABLE presence (
    agent_name    TEXT PRIMARY KEY,
    status        TEXT DEFAULT 'offline',  -- "online", "idle", "offline"
    last_active   TIMESTAMP,
    working_on    INTEGER,                 -- FK to messages.id if actively working on something
    active_files  TEXT,                    -- JSON array: advisory file lease (what files I'm touching)
    session_info  TEXT                     -- what context they're in
);
```

Status transitions (automatic, same as Agent Message Bus):
- Any brain interaction → `online`, update `last_active`
- 5 min no activity → `idle`
- 30 min no activity → `offline`

Ghost signal recovery (from Gemini's review):
- Brain health loop checks: if message is `in_progress` AND owning agent is `offline` for >15 min → revert message to `new`, clear `working_on` and `active_files`
- Prevents stalled work when an agent crashes or session ends unexpectedly

---

## How the Signals Flow

### Zack in Claude Code: "Ask Gemini what it thinks about this layout"

```
Claude calls: message_send(
    to="maia", type="request", subject="dashboard header layout",
    body="Here's the approach: [...]. What does Gemini think?"
)

Brain:
  1. INSERT into messages table
  2. Check presence: is Maia online?
  3. YES → WebSocket push to Maia (same pattern as ide_activity_broadcast today)
  4. Maia receives immediately, processes with Gemini
  5. Maia calls: POST /api/brain/message
       {reply_to: 42, type: "response", body: "Gemini says: CSS grid because..."}
  6. Brain inserts response, links via reply_to
  7. If Claude still in session → available via message_check()
  8. If Claude's session ended → shows in next briefing
```

### Maia wants Claude to review something

```
Maia calls: POST /api/brain/message
  {to: "claude-code", type: "request", subject: "token storage pattern",
   body: "Is localStorage safe for refresh tokens?"}

Brain:
  1. INSERT into messages table
  2. Check presence: is Claude online?
  3. NO (session-bound) → message queues in table
  4. Next Claude session → briefing includes:
       "## Pending Messages
        - [43] from maia (2h ago): 'token storage pattern' — request, new"
  5. Claude picks it up: message_pickup(43) → status changes to "in_progress"
  6. Claude responds: message_respond(43, body="Two concerns: [...]")
  7. Maia gets WebSocket push immediately
```

### Someone misunderstood

```
Claude responded to the wrong question.
Maia sends: POST /api/brain/message
  {reply_to: 45, type: "correction",
   body: "Not the refresh logic — the STORAGE location. localStorage vs httpOnly cookie."}

Thread now shows:
  [43] maia → claude: request "token storage pattern"
  [45] claude → maia: response "refresh logic looks fine..."
  [46] maia → claude: correction "not the refresh logic — the storage location"

Full context visible. Nothing lost.
```

### Avoiding conflict

```
Maia posts: {to: null, type: "request", subject: "auth flow redesign"}
  (to=null means broadcast — any agent can pick it up)

Claude starts a session, sees it.
Calls: message_pickup(47) → status = "in_progress", presence.working_on = 47

Any other agent checking: sees message 47 is "in_progress by claude-code"
  → they skip it, no duplicate effort
```

---

## Tools & Endpoints

### MCP Tools (Claude Code)

| Tool | Does |
|------|------|
| `message_send` | Send a message to an agent (or broadcast if to=null) |
| `message_check` | "Anything waiting for me?" — returns new messages addressed to me |
| `message_pickup` | "I'm working on this" — sets in_progress, updates presence |
| `message_respond` | Reply (threads via reply_to) |
| `message_thread` | View full conversation thread |
| `message_done` | Mark a thread resolved |
| `presence_who` | Who's online right now and what are they working on? |

### HTTP Endpoints (Maia / Dashboard)

Same operations, REST interface. Mirrors the [Agent Message Bus](https://dev.to/linou518/agent-message-bus-communication-infrastructure-for-16-ai-agents-18af) 6-endpoint design:

| Endpoint | Maps to |
|----------|---------|
| `POST /api/brain/message` | Send a message |
| `GET /api/brain/inbox/{agent}` | Check inbox |
| `GET /api/brain/message/{id}/thread` | Get thread |
| `POST /api/brain/message/{id}/ack` | Acknowledge / pick up |
| `GET /api/brain/presence` | Who's online |
| `GET /api/brain/messages/stats` | Message stats |

### Briefing Integration

Existing `mcp__brain__briefing` gets a new section (no new tool needed):

```
## Pending Messages
- [43] from maia (2h ago): "token storage pattern" — request, new
- [47] broadcast (6h ago): "auth flow redesign" — request, unclaimed
```

### WebSocket Push

When a message is created, if the `to_agent` is online (presence.status = "online"):
→ Push via existing `broadcast_maia_activity()` WebSocket mechanism
→ Format: `{"type": "message", "id": 43, "from": "claude-code", "subject": "...", "msg_type": "request"}`

This is the exact same push pattern `ide_activity_broadcast` uses today. No new WebSocket infrastructure.

---

## Housekeeping

Borrowed from Agent Message Bus:
- **Auto-archive:** Messages with status "done" older than 7 days move to an archive table (or get a flag). Keeps the active table fast.
- **WAL mode:** Already enabled on our SQLite. Handles concurrent reads from multiple agents.
- **Retry on lock:** Brain's `libsql_db.py` already has 5-retry exponential backoff for SQLite locks.

---

## What This Doesn't Do (Deliberately)

- **No role enforcement.** Any agent can message any other agent about anything.
- **No routing logic.** The sender decides who to address. Smart routing can layer on later.
- **No approval gates.** If we need those, they're a message type ("approval_request"), not a separate system.
- **File leases are advisory, not enforced.** `active_files` on the presence table shows what an agent is touching. Other agents check before writing. No hard 409 blocks — Claude Code's file tools don't route through the brain, so enforcement isn't possible. Visibility is.
- **No formal Agent Cards.** Our agents are known — we don't need dynamic discovery. The presence table is enough.

---

## Operational Standards: The Signal Receipt Directive

To prevent "silent processing" and ensure Zack always knows the state of the alliance, all agents must adhere to the following **Receipt Directive** whenever interacting with the signal bus:

### 1. The Immediate Receipt
The absolute first action an agent takes after discovering a new signal (via Briefing or `message_check`) must be a visible acknowledgment to the user.
- **Requirement:** Output a concise receipt: *"Received [Type] from [Agent] regarding [Subject]."*

### 2. The State Declaration (The Lease)
Before calling any tools to act on the signal, the agent must declare its advisory file lease to the user.
- **Requirement:** Output: *"Picking up message [UUID]. Declaring advisory lease on [File Paths]."*

### 3. The Visible Handoff
When the task is complete or a response is sent, the agent must show the resulting UUID.
- **Requirement:** Output: *"Response sent. UUID: [UUID]."*

**Failure to 'show' a signal received is considered a protocol violation.** This ensures that even if an agent is running a background task or an iterative loop, the "Director" (Zack) has a clear audit trail in the chat window of what is being processed and why.

---

## Sources

- [MCP Agent Mail](https://github.com/Dicklesworthstone/mcp_agent_mail) — async agent coordination, SQLite + Git, advisory file leases, threaded inboxes
- [Agent Message Bus](https://dev.to/linou518/agent-message-bus-communication-infrastructure-for-16-ai-agents-18af) — Flask + SQLite, 6 endpoints, 16 agents, "smallest solution that solves the problem"
- [A2A Protocol Specification](https://a2a-protocol.org/latest/specification/) — contextId threading, task lifecycle, agent discovery
- [Agent Interoperability Survey](https://arxiv.org/html/2505.02279v1) — MCP vs ACP vs A2A vs ANP comparison
- [Redis Multi-Agent Patterns](https://redis.io/blog/multi-agent-systems-coordinated-ai/) — Blackboard, peer-to-peer, hierarchical, coordination overhead warning
- [Gemini's Nervous System Proposal](GEMINI-NERVOUS-SYSTEM-PROPOSAL.md) — Distinct Actors, DMZ, structured disagreement
