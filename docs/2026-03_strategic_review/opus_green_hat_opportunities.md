# Opus Green Hat: Top 10 Growth Opportunities
## What zBrain Could Become From Here — March 9, 2026

Ranked by **impact-to-effort ratio**. Most of these build on pieces you already have.

---

### 1. 🎯 Voice → Action Bridge
**"Hey Promaia, schedule that for tomorrow at 2"**

`google_calendar.py` and `gmail_tools_server.py` already exist. The voice agent has zero tools beyond memory staging. Adding `create_calendar_event` and `send_email_draft` as Gemini Live tool declarations would transform the system from *observer* to *actor* in a single afternoon of wiring.

**Why it's #1:** This is the moment it stops feeling like a smart notebook and starts feeling like an assistant.

---

### 2. 🌅 Morning Briefing (The Subconscious's First Gift)
**"Good morning, Zack. You have 3 meetings today, you were mulling over the MuninnDB architecture last night, and HeatPup hasn't been touched in 5 days."**

Calendar data ✅ Memory context ✅ Domain staleness tracking ✅ (`suggest_next()` in engine.py). All you need is the background heartbeat (APScheduler) to synthesize them at 7am and push to dashboard or Telegram.

**Why it matters:** This is the first time the system *initiates* instead of *responds.* That's the line between tool and partner.

---

### 3. 🔗 Unified Memory Pipeline
Not a new feature — a **multiplier** for every feature. Voice commit follows the same path as MCP capture: write to `brain.memories` → generate embedding → run `extract_insights()` → dual-write to MuninnDB. One pipeline, both surfaces.

**Why it matters:** Every other opportunity on this list works better when memories are findable regardless of where they were captured.

---

### 4. 🧭 Temporal & Calendar Awareness
The voice agent has no idea what time it is, what day it is, or what's on your calendar. Adding clock context and today's calendar to the system prompt enables:
- "You have a meeting about X in 30 minutes" → agent preps relevant context
- Late night sessions → automatically briefer, respects wind-down
- Monday morning → surfaces weekend captures for review

`_get_calendar_events()` already exists in `dashboard.py`. Just needs to feed into `brain_stream`.

---

### 5. 🔄 Conversation Continuity Threading
Start a thought in the car. Pick it up at your desk. Get a synthesis at night.

The pieces exist: transcript logs, MuninnDB context injection, dashboard reviews. What's missing is an explicit **thread ID** — a way to tag related conversations across sessions so the agent can say "Last time you were working through X, you got to this point. Want to pick it up?"

**Implementation:** Add an optional `thread_tag` to staged memories and `audio_session_reviews`. MuninnDB's associative retrieval would naturally cluster related items.

---

### 6. 🎭 Voice Session Modes
Not every voice session is the same. Instead of one-size-fits-all:

| Mode | Behavior |
|---|---|
| **Capture** | Pure dictation. Minimal responses. Stage everything. |
| **Review** | Batch confirmation (#15). Agent leads, user approves. |
| **Brainstorm** | Agent pushes back, asks "what if," plays devil's advocate |
| **Debrief** | "How did the meeting go?" → structured extraction |

User selects mode on the Talk page, or the agent detects it from context ("I just got out of a meeting" → debrief mode).

---

### 7. 🧠 Proactive Memory Synthesis
The background heartbeat doesn't just remind — it **thinks.** Every night, run `extract_insights()` across the day's accumulated memories to generate higher-order patterns:

- "You've made 5 decisions about voice protocol this week. Here's the through-line."
- "You mentioned 'timing' in 3 different project contexts. Is there a connection?"
- Weekly digest: what you decided, what you learned, what's unresolved.

This is **Value Hunting (#16)** operating autonomously.

---

### 8. 📱 Telegram as Second Surface
You already have `promaia/telegram/` and `promaia/telegram_cli.py`. Telegram is the perfect channel for:
- Push notifications from the background heartbeat
- Quick captures when you can't open the dashboard
- Morning briefing delivery
- Async confirmation of staged memories

Voice for capturing. Dashboard for reviewing. Telegram for nudges.

---

### 9. 🗺️ Knowledge Graph Visualization
MuninnDB's associative memory is invisible right now — you put things in and get them out, but you can't *see* the graph. A force-directed visualization on the dashboard showing how your concepts connect would:
- Make the "glass cockpit" genuinely meaningful
- Help you spot orphaned ideas or over-connected clusters  
- Create an intuitive way to prune or strengthen connections

Libraries like D3.js force-graph or vis-network make this achievable in days, not weeks.

---

### 10. 🔧 Adaptive Protocol Learning
Instead of hard-coding all 16 voice rules, the system could **learn new ones** from corrections:

- User: "Don't do that again"
- Agent: "Got it. New rule: [reads back what it inferred]. Should I add this to my protocol?"
- User confirms → rule persists in `brain.memories` with tag `voice_protocol`
- On session start, protocol rules are loaded dynamically from memory

This closes the loop: the product improves itself through use, and early adopters' discoveries automatically benefit the system. The 16 rules we codified today become the *seed set*, not the ceiling.

---

## The Common Thread

8 of these 10 opportunities require the **same two infrastructure pieces**:
1. **Unified memory pipeline** (#3)
2. **Background heartbeat** (#2)

Build those two, and everything else becomes wiring.
