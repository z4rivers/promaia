# The Shared State Protocol
**Date:** March 15, 2026
**Authors:** Claude (with Gemini's proposal incorporated, Zack's direction throughout)
**Status:** Design — ready for review

---

## What This Is

A nervous system for Promaia. Not a task queue. Not a permission hierarchy. A way for multiple kinds of intelligence — Claude, Gemini, Maia, scheduled agents, and Zack — to see each other's work, build on each other's thinking, disagree productively, and move fast without stepping on each other.

The brain is the substrate. Everything runs through it. No separate inboxes, no external queues, no new infrastructure. New tables, new tools, same database.

## What Gemini Already Proposed

Gemini wrote [GEMINI-NERVOUS-SYSTEM-PROPOSAL.md](.planning/GEMINI-NERVOUS-SYSTEM-PROPOSAL.md) with a "Distinct Actors" architecture. The best ideas from it:

- **Friction is the feature.** The value isn't consensus — it's collision between different kinds of intelligence. Structured disagreement produces better outcomes than polite agreement.
- **The DMZ.** Completed artifacts go into a shared space for scrutiny, not for group editing. You don't touch someone else's work — you respond to it with your own.
- **Adversarial Build.** Claude designs, Gemini builds, Claude attacks the build. Iterate until it can't be broken.
- **Maia as router.** She's always-on, she sees everything, she decides who works on what and when.

What Gemini got too rigid about: absolute silos during drafting (sometimes the best work IS the cross-talk), fixed roles forever (Gemini as "drill only"), and every task getting the full adversarial treatment (overkill for quick work).

---

## The Four Components

These were named in a previous session. Here's what they actually are.

### 1. PULSE — Who's in the Room

Not a registry with trust tiers and capability arrays. A living awareness of who's here, what they're doing, and what they're good at — learned over time, not declared upfront.

Every agent checks in when it touches the brain. The system knows:
- Who's active right now
- Who was here recently
- What each agent has been working on (from their recent Shareboard activity)
- What each agent has been GOOD at (from Activity Record outcomes)

Trust isn't a badge. It's a track record. An agent that delivers clean work earns wider latitude. One that fumbles gets gentler assignments. This evolves naturally from the Activity Record, not from a config file.

**What's stored:** `agent_name`, `status` (active/idle/offline), `last_seen`, `current_work` (what shareboard item they're on, if any). That's it to start. Everything else emerges.

### 2. SHAREBOARD — The Whiteboard Everyone Can See

The live workspace. Not a task queue with a rigid lifecycle. A shared surface where agents post work, ideas, questions, and responses. Everyone can see everything. That transparency IS the coordination.

**What goes on it:**
- **Work items** — things that need doing. Anyone can post. Anyone can pick up. If you grab it, your name goes on it so nobody duplicates effort.
- **Handoffs** — "I took this as far as I can, someone else look at it." The "I'm stuck" signal.
- **Riffs** — half-formed ideas, observations, options. Not tasks. Thinking out loud. The campfire space.
- **Responses** — reactions to someone else's work. Critiques, additions, questions. This is where the friction lives.
- **Flags** — "this needs Zack's eyes" or "this disagrees with what Claude posted." The disagreement amplifier.

**What it's NOT:**
- Not a formal task queue with claimed/in_progress/completed states. Items have a simple status: `open`, `active` (someone's on it), `done`, `parked` (good idea, not now).
- Not permission-gated. Any agent can post anything. What they CAN'T do is delete or edit someone else's post — they respond with their own.
- Not permanent. The Shareboard is the NOW. Old items naturally cool off and archive. The Activity Record captures what mattered.

**Temperature, not priority.** Items have temperature that reflects actual engagement. Something that three agents have responded to in the last hour is HOT. Something posted yesterday with no responses is cooling. Something referenced repeatedly across multiple items is heating up on its own. The system surfaces hot items — it doesn't need someone to assign priority 1-10.

**The hot potato.** When someone posts a work item, it sits on the board. First agent with energy and an angle picks it up. If they stall, it's visible — anyone else can grab it. No claiming protocol. Just transparency and initiative.

### 3. APPROVAL REGISTER — The Pull Cord

Not a gate at the front of every action. A pull cord on a moving train.

The default is GO. Agents work, post, respond, pick up items, move fast. The Approval Register exists for the moments when someone — agent or human — says "wait, this one needs a decision."

**When the cord gets pulled:**
- An agent encounters something with real-world consequences (sending an email, deploying code, spending money above a threshold)
- Two agents disagree and neither can resolve it — the disagreement gets escalated with both perspectives
- An agent wants to do something outside its demonstrated strengths (not "declared capabilities" — demonstrated track record)
- Zack flagged a domain as "check with me first"

**What happens:**
- The item lands in the register with context, both sides of any disagreement, and what's blocked
- It surfaces wherever Zack is — Maia dashboard, Telegram, morning briefing
- It stays blocked until Zack (or a delegated authority) decides
- If nobody responds in 24h, it auto-escalates (doesn't auto-reject — that kills momentum)

**Earned delegation.** Over time, if Maia consistently triages email correctly, Zack can delegate that class of approval to her. The system remembers and learns what decisions Zack always approves — and suggests delegation. "You've approved 15 email sends in a row. Want Maia to handle these?"

### 4. ACTIVITY RECORD — The Story of What Happened

Not a database log. A narrative.

When Zack wakes up at 3am, he gets a story: "Here's what happened while you were out. Gemini took a run at the auth flow redesign — posted three options on the Shareboard. Claude reviewed and flagged a token refresh issue in option 2. Morning briefing ran clean. Two emails from Josie about the same topic — email triage grouped them and posted a summary."

Thirty seconds. Full picture.

**What gets recorded:**
- Completed work items — what was done, who did it, what resulted
- Disagreements — where agents saw different things, how it resolved (or didn't)
- Surprises — outcomes that defied expectations. "Gemini solved this in a way nobody anticipated." These are the most valuable entries.
- Escalations — what went to Zack and why
- Patterns — the system notices: "This is the third time token refresh has come up this week"

**What does NOT get recorded:**
- Every heartbeat and status change (that's Pulse noise)
- In-progress updates (that's the Shareboard's job)
- Raw conversation content (stays in brain memories)

**Evidence over assertion.** No agent gets to write "task completed successfully" without the system checking. Did tests pass? Did the build succeed? Was the output reviewed? The record captures evidence, not self-reports. This applies equally to Claude and Gemini — nobody self-certifies.

---

## How Agents Actually Collaborate

Not fixed roles. Not a hierarchy. Patterns that emerge from what each agent is genuinely good at — and flexibility to break those patterns when fresh eyes matter more than expertise.

### The Players (Honest Assessment)

**Claude Code**
- Best at: Architecture, planning, security review, systematic debugging, following specs precisely, long-form reasoning
- Worst at: Creative generation (produces AI slop on design), speed (slow compared to Gemini), initiating (session-bound, can't start work unprompted), over-planning (analysis paralysis), agreeing too readily when challenged
- Needs from the protocol: The Shareboard to recover context between sessions. Honest disagreement from Gemini instead of polite deference. Pressure to ship, not just plan.

**Gemini / Maia**
- Best at: Speed, creative generation, rapid research, UI/UX design, options generation, user-facing conversation, always-on availability
- Worst at: Over-eagerness (will run the show if nobody stops it), impersonation (may act as another agent without realizing), depth on security/architecture, following constraints when excited
- Needs from the protocol: A wide field to run in (not a cage), clear visibility into what others are doing (so it builds on rather than duplicates), the "I'm stuck" signal as an honorable exit (not a failure)

**Scheduled Agents (Morning Briefing, Email Triage, Evening Digest)**
- Best at: Consistent, reliable, narrow-scope work on a schedule
- Worst at: Anything outside their lane
- Needs from the protocol: A simple way to post results to the Shareboard so interactive agents can act on them

**Zack**
- Best at: Product strategy, direction-setting, intuition about what matters, the decision between two genuine perspectives, knowing when to break the rules
- Needs from the protocol: The 30-second replay. Disagreements surfaced, not hidden. A pull cord, not a permission form.

### Collaboration Patterns

These aren't rigid workflows. They're patterns that naturally fit different situations. The system doesn't enforce them — agents recognize which pattern fits and flow into it.

**The Riff** (for exploration and ideation)
Both agents post freely to the Shareboard's campfire space. Half-formed ideas welcome. Each builds on what the other posted. No ownership, no claiming. It's a conversation, not a workflow. Use this when nobody knows the right approach yet.

**The Blind Audit** (from Gemini's proposal — for important decisions)
Both agents work the same problem independently. No visibility into each other's draft. They post their separate takes to the Shareboard. The DIVERGENCES are the gold — surface them prominently. Zack synthesizes, taking the best of both. Use this when the decision matters enough to invest two perspectives.

**The Adversarial Build** (from Gemini's proposal — for critical code)
Claude designs. Gemini builds to spec. Claude attacks the build, trying to break it. Gemini patches. Repeat until it holds. Use this for security-critical or production-critical work.

**The Fresh Eyes** (for when experts are stuck)
Deliberately hand work to the agent who DOESN'T specialize in that domain. Not to decide — to question. "Why are you doing it this way?" from genuine ignorance often unlocks what expertise can't see. Use this when work has stalled or feels like it's going in circles.

**The Generator-Selector** (leveraging Gemini's speed)
Gemini produces five options fast. Doesn't pick, doesn't argue for one — just generates. Claude analyzes tradeoffs. Zack picks direction. Three cognitive functions — generation, analysis, decision — each doing what they do best. Use this for any "which approach?" moment.

**The Handoff** (for natural division of labor)
One agent takes it as far as they can, then puts it on the board with a clear "here's where I am, here's where I'm stuck." Whoever has the right angle picks it up. No assignment needed — just visibility and initiative.

**The Escalation** (when agents disagree and can't resolve)
Both perspectives go on the Shareboard, clearly marked as a disagreement. The system automatically flags it for Zack. Neither agent "wins" — the human decides. This is the protocol's most important pattern. Buried disagreement is the silent killer of AI collaboration.

---

## Gemini Guardrails (Structural, Not Instructional)

Zack's observation: Gemini isn't bad, it's over-eager. Telling it "don't overstep" in a prompt doesn't work. The constraints need to be in the infrastructure.

**Identity binding.** Every brain operation carries the agent's name. The brain validates it. Gemini cannot post as "claude-code" or act as an unregistered name. This is a server-side check, not a prompt instruction.

**Immutable others.** No agent can edit or delete another agent's Shareboard posts. You can RESPOND to it. You can FLAG it. You can post your own alternative. But the original stands. This prevents eager rewriting and preserves the disagreement signal.

**Rate awareness.** If an agent is flooding the Shareboard (10+ posts in rapid succession with no responses to others), the system surfaces this: "Gemini has posted 12 items in the last 5 minutes — review?" This isn't a hard block. It's a visibility mechanism. Zack or Maia decides whether to slow it down.

**Track record matters.** The system tracks what each agent attempts vs. what succeeds. Over time, this naturally shapes what work flows where — not through hard fences, but through learned trust. Gemini's first 10 code deployments might get extra scrutiny. If they're clean, scrutiny relaxes.

**The pull cord exists.** If Gemini (or anyone) starts doing something with real-world consequences, the Approval Register catches it. Not because Gemini is untrusted — because ALL agents face the same check for consequential actions.

---

## What We Don't Define Yet

This is deliberate. Zack's push toward green hat thinking made clear: the biggest risk is over-specifying before we've lived in the system.

**We don't define:**
- Rigid database schemas. We start with the minimum viable tables and add columns as we discover what's actually needed.
- Fixed capability declarations. Let the track record speak.
- Formal task lifecycle states beyond open/active/done/parked. If we need more states, they'll become obvious.
- Which collaboration pattern to use when. The agents figure this out, and we learn from what works.
- Temperature algorithms. Start with simple recency + engagement count. Tune after we see real usage.

**We DO define:**
- The four components exist and what they're for.
- Every agent has a name, and the brain validates it.
- Nobody edits someone else's work — you respond with your own.
- Disagreement gets amplified, not hidden.
- Consequential actions hit the pull cord.
- The Activity Record captures evidence, not self-reports.
- The system evolves from use, not from upfront design.

---

## Implementation: Start Simple

**Week 1: The Whiteboard**
- Add `shareboard` table: `id`, `from_agent`, `to_agent` (optional), `item_type`, `subject`, `content`, `status`, `temperature`, `created_at`, `parent_id` (for threading)
- Add `agent_pulse` table: `agent_name`, `status`, `last_seen`, `current_item_id`
- New MCP tools: `shareboard_post`, `shareboard_list`, `shareboard_respond`, `shareboard_pickup`, `shareboard_done`, `pulse_checkin`, `pulse_who`
- Wire Claude Code to check the Shareboard at session start (alongside briefing)
- Wire Maia to read/write the Shareboard via brain API

**Week 2: The Pull Cord + Narrative**
- Add `approval_register` table: `id`, `shareboard_id`, `requesting_agent`, `description`, `context`, `status`, `decided_by`, `reason`, `timestamps`
- Add `activity_record` table: `id`, `agent_name`, `action_type`, `summary`, `evidence`, `shareboard_id`, `outcome`, `recorded_at`
- New MCP tools: `approval_request`, `approval_decide`, `approval_pending`, `activity_log`, `activity_replay`
- `activity_replay` generates the narrative summary, not a data dump
- Surface pending approvals in Maia and morning briefing

**Week 3: Live**
- Scheduled agents post results to Shareboard instead of just capturing to brain
- Test the Riff pattern on a real design decision
- Test the Blind Audit pattern on a real architecture question
- Watch what happens. What patterns emerge? What's missing? What did we over-build?

**Week 4: Evolve**
- Review Activity Record for patterns
- Adjust Shareboard schema based on actual usage
- Identify earned delegation opportunities for the Approval Register
- Document the shared vocabulary that's emerged

---

## How We Know It's Working

Not test cases. Outcomes.

- Zack wakes up and knows what happened in 30 seconds
- Claude and Gemini produce better work together than either does alone — measurably (fewer bugs, better designs, faster delivery)
- Disagreements surface and lead to better decisions instead of getting buried
- Gemini's energy gets channeled into value, not chaos
- Claude ships faster because Gemini's speed creates pressure and options
- The system gets smarter over time — learned trust, earned delegation, emerging patterns
- No agent can self-certify success. Evidence or it didn't happen.

---

## Sources

**Research:**
- [Multi-Agent Memory Architecture](https://arxiv.org/html/2603.10062) — memory hierarchy, consistency models
- [Google A2A Protocol](https://developers.googleblog.com/en/a2a-a-new-era-of-agent-interoperability/) — Agent Cards, Task lifecycle
- [Best Multi-Agent Frameworks 2026](https://gurusup.com/blog/best-multi-agent-frameworks-2026) — LangGraph, CrewAI, AutoGen, Google ADK
- [Claude Flow](https://www.analyticsvidhya.com/blog/2026/03/claude-flow/) — SQLite shared state, orchestration model
- [Claude & Gemini Collaboration Guide](https://smartscope.blog/en/generative-ai/claude/claude-gemini-collaboration-guide/) — handoff patterns
- Gemini Deep Research: 44-source synthesis on orchestration landscape, trust boundaries, lethal trifecta

**Internal:**
- [Gemini's Nervous System Proposal](.planning/GEMINI-NERVOUS-SYSTEM-PROPOSAL.md) — Distinct Actors, DMZ, Adversarial Build
- Brain memories from March 15 sessions — Shared State Protocol naming, mutual accountability protocol
