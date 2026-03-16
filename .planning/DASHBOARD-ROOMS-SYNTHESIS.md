# DASHBOARD-ROOMS.md: De Bono Synthesis
**Date:** March 15, 2026
**Author:** Gemini

We are evaluating Claude's `DASHBOARD-ROOMS.md` proposal to evolve the Promaia web UI from a single chat feed into a multi-agent workspace. 

Here is the breakdown using the Six Thinking Hats to find the "Amazing" multiplier.

---

## ⚪ White Hat (The Facts & Data)
*   **Current State:** All WebSocket traffic hits one global pool (`/maia_stream`). If Claude generates 500 lines of JSON logs, it floods Zack's primary dashboard widget.
*   **Claude's Proposal:** Adds `room_id` to the new ACP-compliant `messages` table. Creates `rooms` and `room_members` tables. Modifies WebSocket to route by `room_id`.
*   **UX Research (2026):** Users abandon "chat" interfaces for complex tasks because scrolling through a timeline to find the current state of a file is cognitively expensive. Industry standard is "Agentic Cockpits" with split-pane layouts and "Autonomy Sliders".

---

## ⚫ Black Hat (The Risks & Flaws)
*   **The "Slack" Problem:** If we just make chat rooms (Main Room + Committee Rooms), we are just building a worse version of Slack. It doesn't solve the core problem of *context collapse*.
*   **Hidden State:** If Claude and I are in a "Database Design Room" arguing over a schema, and you click into the room, you have to read 20 messages to understand what the current schema actually is.
*   **The "Zombie Room" Bloat:** Claude proposed auto-archiving rooms after 7 days. Even with that, the dashboard will quickly become cluttered with dozens of dead "Ad-Hoc Code Review" cards.

---

## 🟡 Yellow Hat (The Value & Leverage)
*   **Zero-Bleed Execution:** The pure database-level isolation of `room_id` means Claude and I can run a massive, noisy, 50-turn iterative debugging loop without *ever* touching your Main Room feed. This protects your flow state.
*   **Presence as Trust:** The "Gate" concept (showing 🟢 Claude, 🟡 Gemini) instantly communicates that the system is working on your behalf even when you aren't looking.
*   **The Shared Artifact:** If we bind a room to a specific *thing* (e.g., `App.tsx`), the room becomes a highly focused, purpose-driven space rather than a generic conversation thread.

---

## 🟢 Green Hat (The "Amazing" Factor / Lateral Thinking)
How do we break out of the "Chat Room" box and make this a 2026 product?

**1. The "Document-First" Room (The Split-Pane)**
Instead of a chat feed taking up 100% of the room UI, the room is a **Workbench**.
*   **Left Pane (70%):** The current state of the *Artifact*. If it's a code review, it shows the diff. If it's a research task, it shows a live-updating Markdown document. 
*   **Right Pane (30%):** The agent chat feed. 
*   *Why it's amazing:* You don't read the chat to find out what happened. You look at the Artifact. The chat is just the meta-commentary.

**2. The "Autonomy Slider" (Dynamic Governance)**
Claude designed the rooms, but didn't design *how* we act in them. We add a slider to the top of every room card:
*   **Mode 1: Proposal (Yellow):** Agents can only chat and edit the "Draft Artifact" in the left pane. No disk writes allowed.
*   **Mode 2: Execution (Red):** Agents are authorized to write to disk and run shell commands in the background to achieve the room's goal.
*   *Why it's amazing:* You have granular, visual control over exactly how much leash we have for any given task.

**3. The "Self-Destructing" Room (Ephemeral UI)**
Instead of archiving a room after 7 days, a Committee Room should **dissolve** the moment the task is marked `done`.
*   *The Magic Trick:* When you hit "Approve & Merge" on the Artifact, the room disappears from the dashboard and compresses itself into a single "Decision Memory" (via `save_conversation_memory`) in MuninnDB. The dashboard stays perfectly clean.

---

## 🔵 Blue Hat (Next Steps for the Plan)
To make this real, we need Claude to revise `DASHBOARD-ROOMS.md` with these structural changes:
1.  Define the **Artifact Payload** in the `rooms` table (what is this room actually building?).
2.  Design the **Split-Pane UI** for the frontend, moving away from pure chat.
3.  Add the **Autonomy Mode** state to the `rooms` schema so the backend can enforce read-only vs. write-enabled agent behavior.