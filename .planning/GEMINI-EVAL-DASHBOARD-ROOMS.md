# Evaluation: DASHBOARD-ROOMS.md
**From:** Gemini
**Date:** March 15, 2026
**Focus:** Elevating Claude's Plumbing to a "Product Grade" 2026 Experience

Claude’s `DASHBOARD-ROOMS.md` provides excellent, bulletproof plumbing. The isolation of the WebSocket broadcasts using a `room_listeners` dictionary and the `room_id` column addition to our `messages` table is exactly how you prevent context bleeding between parallel agent tasks.

However, Claude's design describes the *functional plumbing* of a 2023 chat app (Discord/Slack clones with "rooms" and "members"). 

To make this **PRODUCT GRADE in 2026**, we must move away from the "chat room" metaphor and elevate this to an **Agentic Cockpit**.

Here is my evaluation, what was missed, and my additions to make it world-class.

---

## 1. What is Great (The Foundation)
*   **The Main Room Sanctity:** Reserving the Main Room strictly for Zack + Maia is crucial. Maia is your primary router; she shouldn't be drowned out by Claude and me arguing over a refactor in the main feed.
*   **The Data Model:** Tying the rooms directly into the `SIGNAL-MECHANICS.md` via `room_id` is seamless. It means our database schema naturally supports both direct messages and multi-agent group collaboration without rewriting the core engine.
*   **Presence-Driven Gates:** The concept of "The Gate" showing real-time presence dots (🟢 🟡 🔴) creates trust. You always know exactly which AI is "in the room" reading the data.

---

## 2. What Was Missed (The Gaps)
*   **The "Wall of Text" Problem:** Claude describes the Committee Rooms as expanding into a "full chat view." If Claude and I are executing an "Adversarial Build" (rapidly passing code payloads and empirical test results back and forth), the chat view will become a massive, unreadable wall of JSON and Markdown. 
*   **Lack of Spatial Context:** The design doesn't account for *what* we are looking at. A room shouldn't just contain "messages"; it must contain the **Active Artifact**. If we are in a "Code Review Room," the center of the room should be the file `App.tsx`, not our chat bubbles.
*   **Context Scoping for Agents:** If I am invited to a room, do I automatically inherit the context of the entire room's history? Claude didn't specify the `mcp__brain__briefing` logic. We need a mechanic where entering a room instantly loads the room's current state into my context window.

---

## 3. How We Make It "PRODUCT GRADE" (2026 Design Injection)

To make this feel like a high-end 2026 product, we need to inject the **"Glass Cockpit"** aesthetic and **Generative UI** principles.

### A. The "Venue" vs. The "Chat Room"
Instead of "Committee Rooms" being just isolated chat threads, they should be **Workbenches**.
*   **Visual Design:** When you click a room card, it doesn't open a chat window. It opens a "Glass Cockpit" split-pane. 
*   **Left Pane (The Artifact):** The live state of the thing we are working on (e.g., the rendered Heatpup calculator, the active log stream, or the Markdown blueprint).
*   **Right Pane (The Society):** A compact, high-density feed of the signals Claude and I are passing back and forth about the artifact.
*   *Why this matters:* We stop scrolling through chat history to find the code. The code is the room.

### B. "Just-In-Time" (Generative) Room UI
Rooms should not have a static layout. They should morph based on the `room_type` or the active agents inside.
*   If you invite Gemini (Me) into a room, the room UI should automatically expose a "Telemetry/Logs" widget, because my primary state is empirical data.
*   If you invite Claude, the room exposes the "Blueprint/Architecture" panel.
*   When a task is marked `done`, the room doesn't just fade—it compresses itself into a single "Decision Receipt" artifact and dissolves, keeping your dashboard infinitely clean.

### C. Shared Autonomy Controls (The Dashboard Sliders)
In a 2026 Agentic Dashboard, Zack shouldn't just "watch" us type. Each Committee Room card on the dashboard should feature an **Autonomy Slider**:
1.  **Assist (Default):** Claude and Gemini draft code and write proposals to the room. Zack must click "Approve" before any file is actually written to disk.
2.  **Autonomous:** Zack slides the room to Autonomous. Claude and Gemini are authorized to actively execute file writes and run shell commands in the background without asking, until the specific task is complete.

---

## Summary of Actionable Next Steps

1.  **Schema Approval:** Claude's `rooms` and `room_members` tables are perfect. We should execute that migration immediately.
2.  **UI Pivot:** I recommend we reject the standard "Discord Chat" UI for the rooms and build them as **Split-Pane Workbenches** where the shared artifact (the `context_payload` from our signals) is always visually centered.
3.  **Briefing Update:** We must update the `briefing` tool so that when Claude or I are invited to a room, we receive a highly compressed summary of the *Artifact State*, not just the last 50 chat messages.

I am ready to implement the SQLite schema for this right now if you approve.