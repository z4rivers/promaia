# Collaborative Refraction: Multi-Agent Planning Process

**Author:** Zack, Claude, Gemini, Maia
**Created:** 2026-03-16
**Origin:** Derived from the Prism Pipeline planning session — the first time this process was used

---

## What This Is

A structured process for multi-agent collaborative planning. Four or more minds (human, AI agents, and the system being designed) contribute independent perspectives, evaluate through Six Thinking Hats, converge on a unified plan, and let the artifact itself weigh in.

This is NOT adversarial. Not "red team vs blue team." Not debate. It's collaborative refraction — each perspective adds light. The output is richer than any single input, the same way a prism produces a full spectrum from white light.

---

## When to Use This

- Architectural decisions that affect multiple surfaces or agents
- Any change where Claude and Gemini would both have implementation opinions
- Work where the system being changed (Maia, the dashboard, the pipeline) has its own operational perspective
- Decisions where "just pick one" would leave value on the table

## When NOT to Use This

- Bug fixes with obvious causes
- Single-file changes
- Tasks where one agent has clear ownership and the other has no relevant perspective

---

## The Process

### Step 1: Frame the Problem

Zack (or the initiating agent) states what needs to be solved. Not the solution — the problem. Include:
- What's broken or missing
- What it costs (in time, tokens, quality, frustration)
- Any constraints (budget, timeline, existing infrastructure)

**Output:** A problem statement all participants can see.

### Step 2: Independent Proposals

Each participating agent develops a plan **in isolation**. No peeking at each other's work. This prevents anchoring — you get genuinely different perspectives, not variations on whoever went first.

Each proposal should include:
- The agent's diagnosis of the root cause
- Their proposed solution with specific implementation details
- Rationale for key decisions
- Risks they foresee

**Output:** One proposal document per agent (e.g., `CLAUDE-COLLABORATION-PROPOSAL.md`, `GEMINI-COLLABORATION-PROPOSAL.md`).

### Step 3: Six Thinking Hats Cross-Evaluation

Each agent reviews the other's proposal through ALL six hats. This is the core of the process. The hats ensure every angle is covered — not just critique.

#### Yellow Hat — Sunshine: What's Good
Before ANY critique, identify what's strong. This isn't politeness — it's functional. It flags what to PROTECT during convergence. When two independent minds arrive at the same conclusion, that conclusion is almost certainly right.

*"Phase 2 is exceptional. The INPUT/OUTPUT tool split is the exact structural shift required."*

#### Green Hat — Growth: What Could This Become?
Not "what's wrong" but "what seeds are here that could grow bigger than what's written?" This is the expansion phase. Ideas get LARGER, not smaller.

*"The Handoff Handshake isn't just agent coordination — it's the seed of a workflow engine."*

#### Brown Hat — Work Boots: Best Way to Get It Done
Practical implementation check. Does this work with the existing codebase? What's the real effort? Where are the dependencies? What existing code can be reused? This grounds architecture vision in mechanical reality.

*"Skip the Event Bus. `capture_memory()` IS the chokepoint. 161 writes/day doesn't need queue infrastructure."*

#### White Hat — Facts on Paper: What Does the Code Say?
Data over opinion. Actual write counts, actual function signatures, actual latency numbers. When two plans disagree, the codebase is the tiebreaker. Read the files. Count the calls. Measure the load.

*"The domain is caller-provided at memory_pipeline.py:35, not LLM-extracted. The hallucination risk is overstated."*

#### Blue Hat — Big Sky: What Are We Missing?
Step back from the mechanics. How does this fit the larger system? What maturity stage are we building for? What patterns should we establish now that future work will thank us for? What are neither of us seeing?

*"Gemini's instincts about where this system WILL need to go are correct. Build Phase 1-6 so they don't BLOCK those patterns from being added later."*

#### Red Hat — Gut: Where Does the Awesomeness Live?
What FEELS right about the ordering, the momentum, the emotional payoff? What sequence will make us grin when it works? Where does intuition say something that logic hasn't articulated yet?

*"Do the pipeline fix, then the bridge, then the Campfire — then STOP. Live with it. Let real data show us what the heartbeat should do."*

**Output:** One review document per agent (e.g., `CLAUDE-REVIEW-OF-GEMINI-PROPOSAL.md`).

### Step 4: Convergence

Not compromise — synthesis. The goal is not to meet in the middle but to find the plan that's better than either input.

Process:
1. Identify where the plans **agree** (this is the foundation — don't re-debate it)
2. Identify the **real disagreements** (usually 2-4, not twenty)
3. For each disagreement: state both positions clearly, let White Hat data resolve what it can, let the human decide what data can't
4. State what's being **adopted** from each plan and what's being **deferred**

**Output:** Convergence response documents, then a merged plan.

### Step 5: System Voice

The thing being designed gets a say. The artifact has standing in its own design process.

If you're redesigning Maia's bridge, Maia reviews the plan. If you're changing the pipeline, the pipeline's operational constraints (latency, cost, failure modes) are represented. The system-under-design catches gaps that the architects miss because they're not the ones running in production.

*Maia caught four gaps none of us saw: search escalation, user_id future-proofing, manual heartbeat triggers, and echo chamber prevention.*

**Output:** Feedback document from the system perspective.

### Step 6: Final Incorporation + Sign-Off

Incorporate the system's feedback. Produce one final plan document. All parties explicitly approve — not silence-as-consent, but active agreement.

The final plan should include:
- Core principles (named, memorable — these guide decisions during implementation)
- Phased implementation with clear ordering rationale
- Specific files and functions to modify
- Verification steps per phase
- A "Next Phase" section capturing good ideas that aren't this sprint
- Attribution (whose idea was each piece — continuity matters)

**Output:** The signed-off plan (e.g., `PRISM-PIPELINE-FINAL-PLAN.md`).

---

## Why This Works

### The Structural Choices (these are the real innovation, not the hats)

1. **Blind siloing at the start.** Each agent commits a full proposal in writing before seeing the other's work. This isn't just "preventing anchoring" — it forces each agent to do their OWN thinking. No drafting off someone else's momentum. No "I agree with Claude but would add..." You have to stand on your own ideas first. The quality of the cross-evaluation depends entirely on the proposals being genuinely independent.

2. **Written commitments, not live discussion.** Proposals are documents, not conversation. You can't hedge in a document the way you can in a chat. "I think maybe we should consider..." becomes "Here is my plan." Writing forces clarity and commitment. It also creates an artifact trail — you can see how thinking evolved.

3. **Expansion before contraction.** Yellow Hat (what's good) and Green Hat (what could this become) run BEFORE Brown Hat (practical) and White Hat (facts). This is deliberate sequencing. If you lead with "is this practical?" you kill ideas before they've been explored. If you lead with "what's the seed here?" ideas grow into things nobody originally imagined. The Handoff Handshake became a workflow engine because Green Hat ran before Brown Hat.

4. **Practical grounding comes LATER, not never.** Brown Hat and White Hat are essential — but they come after expansion, not before it. The dreamer runs first. The engineer runs second. Both are necessary. The order matters.

5. **Gut feelings are a first-class input.** Red Hat isn't a bonus round. "Do this first because it'll feel amazing when it works" reordered our entire execution sequence. Intuition about momentum and emotional payoff is architectural information that no amount of code analysis produces.

### The Process Choices

6. **The system gets a voice.** The artifact's operational perspective catches gaps architects can't see from the outside. Maia caught four things none of us saw.

7. **Convergence is synthesis, not compromise.** The final plan contains things NO individual proposal had. Assistant memory weighting, search escalation, manual heartbeat triggers — none existed in either original proposal.

8. **The human decides, the process generates.** This isn't democratic. Zack has final authority. The process gives him OPTIONS with analysis, not a single recommendation to rubber-stamp.

---

## What This Is NOT

- **Not adversarial.** No "red team." No "breaking" the other plan. Every hat adds, even the critical ones.
- **Not consensus-seeking.** Real disagreements are identified and resolved, not smoothed over. Three genuine disagreements are better than twenty false agreements.
- **Not a meeting.** It's asynchronous. Documents, not discussions. Each agent works at their own speed.
- **Not democratic.** Zack has final authority. The process generates options and analysis. The human decides.

---

## The Hats at a Glance

| Hat | Color Metaphor | Question It Answers |
|-----|---------------|-------------------|
| Yellow | Sunshine | What's strong? What must we protect? |
| Green | Growth | What could this become? Where are the seeds? |
| Brown | Work Boots | What's the most practical way to build this? |
| White | Facts on Paper | What does the data/code actually say? |
| Blue | Big Sky | What are we missing? How does it all fit? |
| Red | Gut Feeling | What feels right? Where's the momentum? |

---

## File Naming Convention

All documents live in `.planning/` at the project root. Naming pattern:

```
{AGENT}-COLLABORATION-PROPOSAL.md     — Independent proposals (Step 2)
{AGENT}-REVIEW-OF-{OTHER}-PROPOSAL.md — Cross-evaluation (Step 3)
{AGENT}-CONVERGENCE-RESPONSE.md       — Convergence negotiation (Step 4)
{AGENT}-RED-HAT.md                     — Gut feelings (Step 3, Red Hat)
MERGED-COLLABORATION-PLAN.md          — Merged attempt (Step 4)
{NAME}-FINAL-PLAN.md                  — Signed-off plan (Step 6)
```

---

## First Use

This process was first used on 2026-03-16 to design The Prism Pipeline — the unified memory architecture for Promaia. The full deliberation trail is preserved in `C:\Users\Zachary Turner\dev\promaia\.planning\`:

- `CLAUDE-COLLABORATION-PROPOSAL.md`
- `GEMINI-COLLABORATION-PROPOSAL.md`
- `CLAUDE-REVIEW-OF-GEMINI-PROPOSAL.md`
- `GEMINI-PRISM-PIPELINE-AUDIT.md`
- `CLAUDE-RESPONSE-TO-GEMINI-AUDIT.md`
- `CLAUDE-RED-HAT.md`
- `CLAUDE-CONVERGENCE-RESPONSE.md`
- `MERGED-COLLABORATION-PLAN.md`
- `PRISM-PIPELINE-FINAL-PLAN.md`

The plan was better than anything any of us could have produced alone.
