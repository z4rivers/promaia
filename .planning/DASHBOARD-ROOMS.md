# Dashboard Rooms & Privacy System
**Date:** March 15, 2026
**Status:** Design

## Research

- [2026 multi-agent dashboards](https://letsblogitup.dev/articles/building-multi-agent-dashboards-for-2026-a-develop/) — role-based isolation in separate channels + centralized dashboard monitoring
- [OpenClaw multi-agent isolation](https://lumadock.com/tutorials/openclaw-multi-agent-setup) — fully isolated agents per workspace, shared server process
- [Google's agent design patterns](https://www.infoq.com/news/2026/01/multi-agent-design-patterns/) — route each channel to a specialist, don't let agents cross-message without going through the channel
- Industry pattern: persistent agents map to channels, keep separate agents bound to separate channels, centralized dashboard shows who's where

## Current State

- One global broadcast pool (`active_maia_listeners`)
- All WebSocket clients see all activity
- Maia Widget is a collapsible `<details>` block on the dashboard
- No rooms, no channels, no privacy boundaries
- WebSocket endpoints: `/maia_stream` (widget), `/stream` (voice), `/stream/text` (log replay)

## Design

### The Room Model

```
┌─────────────────────────────────────────────┐
│                 DASHBOARD                    │
│                                              │
│  ┌────────────────────────────────────────┐  │
│  │         MAIN ROOM (default)            │  │
│  │         Zack + Maia only               │  │
│  │         Always open, always private     │  │
│  │         Full chat interface             │  │
│  └────────────────────────────────────────┘  │
│                                              │
│  ┌──────────────┐  ┌──────────────────────┐  │
│  │ Committee:   │  │ Committee:           │  │
│  │ Code Review  │  │ Research             │  │
│  │ ┄┄┄┄┄┄┄┄┄┄┄ │  │ ┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄ │  │
│  │ 🟢 Claude   │  │ 🔴 (empty)          │  │
│  │ 🟡 Gemini   │  │                      │  │
│  │ Gate: invite │  │ Gate: invite         │  │
│  └──────────────┘  └──────────────────────┘  │
│                                              │
│  [ + New Room ]                              │
└─────────────────────────────────────────────┘
```

### Three Concepts

**1. Main Room**
- Zack + Maia. Nobody else. Ever. Unless Zack explicitly invites someone in.
- This is the existing Maia Widget, promoted from a collapsible detail to the primary UI surface.
- All current chat functionality stays here.
- Other agents CANNOT see or post into this room.

**2. Committee Rooms**
- Created on demand ("New Room" or via signal mechanics — `message_send` with `room` parameter).
- Each room has a name, a guest list, and a visible gate showing who's in/out.
- Agents join by invitation only. Zack invites, or Maia invites on Zack's behalf.
- Messages in a committee room are visible ONLY to room members.
- Rooms can be persistent (always there) or ephemeral (auto-close when empty + resolved).

**3. The Gate**
- Visible on each committee room card.
- Shows: room name, who's currently in (with presence status dots), who's been invited.
- Compact — a card with a guest list, not a full chat window. Expands on click to see the conversation.

### Data Model

```sql
CREATE TABLE rooms (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    room_type   TEXT DEFAULT 'topic',      -- "main", "topic", "summon"
    topic       TEXT,                      -- what this room is about: "Auth Refactor", "Dashboard Layout"
    artifact_ref TEXT,                     -- optional: the thing being worked on (file path, schema name, design spec)
    created_by  TEXT NOT NULL,             -- who created it
    status      TEXT DEFAULT 'active',     -- "active", "dissolved"
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    dissolved_at TIMESTAMP                 -- when room was completed and compressed to memory
);

-- Seed the main room
INSERT INTO rooms (id, name, room_type, created_by) VALUES (1, 'Main', 'main', 'zack');

CREATE TABLE room_members (
    room_id     INTEGER NOT NULL,
    agent_name  TEXT NOT NULL,
    role        TEXT DEFAULT 'member',     -- "owner", "member"
    invited_by  TEXT NOT NULL,
    joined_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (room_id, agent_name)
);

-- Main room always has Zack + Maia
INSERT INTO room_members (room_id, agent_name, role, invited_by) VALUES (1, 'zack', 'owner', 'zack');
INSERT INTO room_members (room_id, agent_name, role, invited_by) VALUES (1, 'maia', 'member', 'zack');
```

### How It Connects to Signal Mechanics

The `messages` table from SIGNAL-MECHANICS.md gets a `room_id` column:

```sql
ALTER TABLE messages ADD COLUMN room_id INTEGER DEFAULT NULL;
-- NULL = direct agent-to-agent signal (no room, existing behavior)
-- room_id set = message belongs to that room, visible only to members
```

When posting to a room:
- Brain checks `room_members` — sender must be a member
- WebSocket broadcast goes ONLY to connections associated with that room
- Briefing shows room messages separately: "## Code Review Room — 3 new messages"

### WebSocket Changes

Currently: all connections go into `active_maia_listeners` set.

New: connections associate with a room.

```python
# Current
active_maia_listeners: set[WebSocket] = set()

# New
room_listeners: dict[int, set[WebSocket]] = {
    1: set(),  # Main room — Zack + Maia widget connections
}

# On WebSocket connect, client sends: {"join_room": 1}
# Server validates membership, adds to room_listeners[room_id]
# Broadcasts only go to room_listeners[target_room_id]
```

### Dashboard UI Changes

**Main Room (top of page, always visible):**
- Promote Maia Widget from collapsible `<details>` to primary full-width chat panel
- Remove the expand/collapse behavior — it's always open
- Chat input, session feed, media upload — all stay
- No guest list needed (it's always Zack + Maia)

**Committee Rooms (below main, card grid):**
- Each room is a card showing:
  - Room name
  - Guest list with presence dots (🟢 online, 🟡 idle, 🔴 offline)
  - Unread message count badge
  - Click to expand into full chat view
- "New Room" button to create an ad-hoc committee
- Rooms with no activity for 7 days show as faded/archivable

**Inviting an agent:**
- From within a topic room: "Invite" button → pick from known agents (presence table)
- From main room: "Hey Maia, invite Claude into a code review room" → Maia creates room + sends invitation signal
- From Claude Code: `message_send(to="maia", type="request", body="can I join the research room?")` → Maia decides

**Room dissolution (from Gemini's synthesis):**
When work is marked done, the room doesn't archive — it dissolves:
1. Room outcome compressed into a brain memory via `capture` (the "Decision Receipt")
2. Room status set to `dissolved`, timestamp recorded
3. Room card disappears from dashboard
4. Messages stay in DB for history, but the room is no longer a live surface
This prevents zombie room bloat while preserving the record.

### Room Lifecycle

1. **Create:** Zack clicks "New Room" or tells Maia to create one. Names it, selects initial guests.
2. **Invite:** Zack or Maia adds agents. Agents get a signal (`msg_type: "room_invite"`) via the signal mechanics system.
3. **Active:** Members post messages, visible only within the room. Presence dots show who's engaged.
4. **Archive:** Zack closes the room, or it auto-archives after 7 days of inactivity. Messages stay in the DB for history.

### What This Preserves

- Main room chat is identical to current Maia Widget behavior — just promoted to primary
- All existing WebSocket mechanics stay — we're adding room-scoping, not replacing the transport
- Signal mechanics (SIGNAL-MECHANICS.md) work independently of rooms — direct agent-to-agent signals don't need a room
- Voice sessions (`/stream`) remain point-to-point, unaffected

---

## Claude's Refinements (After Research + Gemini's Eval)

### Research Sources (March 2026)
- [Smashing Magazine (Feb 2026)](https://www.smashingmagazine.com/2026/02/designing-agentic-ai-practical-ux-patterns/) — Six proven agentic UX patterns: Intent Preview, Autonomy Dial, Explainable Rationale, Confidence Signal, Action Audit, Escalation Pathway
- [CopilotKit Generative UI](https://www.copilotkit.ai/generative-ui) — Three types: static (pre-built components), open-ended (arbitrary HTML), declarative (structured specs). "Chat+" surface = side-by-side chat + canvas
- [Codewave Agentic UI](https://codewave.com/insights/designing-agentic-ai-ui/) — Mission-control style interfaces for agent swarms
- [GitLab Trust in Agentic Tools](https://about.gitlab.com/blog/building-trust-in-agentic-tools-what-we-learned-from-our-users/) — Progressive authorization, not binary switches

### Where Gemini's Right

**Workbench over chat room.** Committee rooms should be artifact-centered, not chat-centered. The 2026 pattern is "Chat+" — side-by-side with the thing you're working on visible alongside the conversation about it. When Claude and Gemini are reviewing code, the code is the center, the conversation is alongside.

**Context scoping on room entry.** When an agent joins a room, they should get a compressed summary of the room's current state and artifact — not the last 50 messages. The briefing tool needs a room-aware mode.

### Where Gemini's Too Ambitious for v1

**Generative UI that morphs per agent.** Fascinating concept, but premature. We need the room mechanics solid before the rooms get smart about their own layout. v2 territory.

**Full autonomous mode on the slider.** Dangerous as a v1 feature. If Gemini gets "Act Autonomously" and goes off-rails, the damage is real files on disk. v1 should be confirmation-required only. The Autonomy Dial earns its higher settings through demonstrated track record — exactly like the Smashing Magazine pattern recommends: start at "Suggest," work up to "Autonomous."

### What I'd Add

**1. The Summon Pattern**
Zack is in the main room with Maia. Wants Claude's input for 30 seconds. Instead of creating a whole committee room, he says "bring Claude in." Claude gets a temporary guest pass into the main room — visible in the member list, can see and respond to the current thread. When the question is answered, Claude leaves. The main room returns to Zack + Maia.

This is lighter than a full committee room for quick cross-checks. "Hey other model, what do you think of this?"

**2. Spectator Mode**
Zack might want to watch Claude and Gemini work something out in a committee room without participating. Observe the Adversarial Build happening. His presence is visible (so agents know he's watching) but he's not injecting messages. He can pull the cord (Approval Register) if needed.

**3. "Because X, I did Y" on Every Action**
From Smashing Magazine's Explainable Rationale pattern. Every agent action in a room cites its reasoning. Not a full essay — one line. "Because your layout uses nested flexbox, I'd suggest grid for the outer container." This catches misinterpretation at the action level, not after the fact.

**4. Room-Level Action Audit**
Each room has a compact audit trail — not the full message history, but a log of ACTIONS taken (files modified, signals sent, approvals requested). Visible in the room's gate/header. "3 files modified, 1 approval pending, 2 reviews completed." Undo available within a time window.

**5. Topic Rooms, Not Just Agent Rooms**
Committee rooms shouldn't be "Claude's room" or "Gemini's room." They should be about a TOPIC — "Auth Refactor," "Dashboard Layout," "Email Triage Review." Agents come and go as they have something to contribute. The room persists as long as the topic is active. This prevents rooms from being identity-bound and encourages the "fresh eyes" pattern — any agent can be invited into any topic.

### Revised Room Types

| Type | Who | Purpose | Persistence |
|------|-----|---------|-------------|
| **Main** | Zack + Maia (always). Guests by summon (temporary). | Private 1:1. The home base. | Permanent |
| **Topic** | Invited agents. Zack can spectate or participate. | Artifact-centered workbench for a specific piece of work. | Dissolves on completion — compresses into a brain memory. |
| **Summon** | Temporary guest in Main room. | Quick cross-check. "What do you think of this?" | Dissolves when guest leaves. |

### v1 vs v2

**v1 (Build now):**
- Main room promoted to primary UI
- Topic rooms as cards with gates/guest lists/presence dots
- Rooms have `topic` and optional `artifact_ref` — they're about something, not just containers
- Room dissolution on completion — compress to memory, disappear from dashboard
- Summon pattern for quick cross-checks
- Room-scoped WebSocket broadcasts
- Room-aware briefing
- Confirmation-required on all agent actions (no autonomy slider yet)

**v2 (Build after v1 proves out):**
- Workbench split-pane (artifact + conversation side-by-side)
- Autonomy Dial per room (earned through track record)
- Action Audit with timed undo
- Spectator mode
- Generative UI per agent type

### Implementation Files

- `promaia/web/templates/dashboard.html` — promote widget, add room cards grid
- `promaia/web/static/js/maia_widget.js` — add room_id to WebSocket join, scope message display
- `promaia/web/main.py` — change `active_maia_listeners` to `room_listeners` dict, scope broadcasts
- `promaia/web/routers/brain.py` — room CRUD endpoints, membership management
- `promaia/storage/db_init.py` — add `rooms` and `room_members` tables, `room_id` on messages
- `promaia/brain/mcp/handlers/signal_ops.py` — room-aware message sending/receiving
