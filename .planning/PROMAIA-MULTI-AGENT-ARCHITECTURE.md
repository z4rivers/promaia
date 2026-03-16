# Promaia Multi-Agent Collaboration Architecture
**Date:** March 15, 2026
**Status:** Architectural Draft

## 1. The Core Paradigm: Beyond the "Wrapper"

Most IDE extensions (like Cline, Cursor, or basic OpenHands clones) treat model switching as a simple API swap within a single, linear conversation thread. This creates context bloat, amnesia during handoffs, and limits the system to a sequential "chat" paradigm. 

To achieve a **multiplier effect**, Promaia must move to a **Blackboard Architecture** (or State Ledger paradigm). In this model, agents do not talk *to each other* in a linear chat. Instead, they read from and write to a shared, persistent workspace (the "Blackboard")—managed by Maia—where artifacts, state, and directives live.

## 2. The Shared State Ledger (The Nervous System)

To avoid model-switching friction, the shared memory system must be deterministic and heavily structured. 

### Core Components of the Ledger (MuninnDB + File System)
1. **The Brief (Intent):** Written by Zack. The unchangeable goal.
2. **The Blueprint (Architecture):** Authored by Claude. The technical specification, constraints, and test requirements.
3. **The Active Workspace (State):** Managed by Maia. Tracks which files are checked out, branch status, and current task assignment.
4. **The Execution Log (Audit):** Authored by Gemini. A machine-readable log of tools called, files touched, and shell outputs.
5. **The Evaluation (Review):** Authored by Claude/Zack. Pass/Fail grading on Gemini's execution.

*Crucially: When an agent spins up, it does not inherit 50 turns of conversational history. It queries the State Ledger for the current snapshot.*

## 3. The Alliance: Roles & Capabilities

We treat the models not as interchangeable brains, but as specialized hardware.

*   **Zack (The Director):** Sets the Brief. Injects real-world context. Provides the final "Go" on destructive or architectural shifts.
*   **Maia (The Orchestrator):** The persistent background process. She owns the State Ledger. She monitors inboxes, categorizes incoming data, and routes tasks. *Maia decides WHEN an agent needs to wake up.*
*   **Claude (The Architect & Reviewer):** Optimized for deep reasoning, nuance, and structural planning. 
    *   *Inputs:* The Brief, the Codebase, Gemini's Execution Log.
    *   *Outputs:* The Blueprint, Code Reviews, Edge-case identification.
*   **Gemini (The Executor):** Optimized for high-speed, multi-tool execution, massive file traversal, and persistence.
    *   *Inputs:* The Blueprint, Claude's Reviews.
    *   *Outputs:* Working code, shell commands, test executions.

## 4. Collaboration Topologies (The Multiplier Effect)

We achieve the 1+1=3 multiplier by running specific workflow topologies, rather than just unstructured chatting.

### Topology A: The "Blueprint & Build" (Sequential Execution)
1. **Request:** Zack asks for a new feature via Promaia chat.
2. **Routing:** Maia categorizes it as a complex build and tags Claude.
3. **Design:** Claude enters Plan Mode, reads the codebase, and writes `BLUEPRINT.md` to the Ledger.
4. **Handoff:** Maia pings Zack: "Blueprint ready for review." Zack approves.
5. **Execution:** Maia spins up Gemini CLI. Gemini reads `BLUEPRINT.md`, executes the exact file modifications, runs the tests, and logs success to the Ledger.

### Topology B: The "Red Team" Loop (Iterative Evaluation)
Used for critical infrastructure, security, or complex logic.
1. **Execution:** Gemini builds a V1 of a module.
2. **Review Request:** Instead of asking Zack, Gemini flags the State Ledger: `STATUS: AWAITING_REVIEW`.
3. **Adversarial Check:** Maia wakes up Claude with a specific prompt: *"Gemini just built X. Try to break it. Find security flaws, race conditions, or unhandled exceptions. Write your findings to REVIEW.md."*
4. **Refinement:** Gemini wakes back up, reads `REVIEW.md`, and fixes the flaws. This loop continues until Claude passes the code, *then* it is presented to Zack.

### Topology C: The "Investigator" (Parallel Search & Synthesis)
Used when debugging a massive, system-wide issue (e.g., "Why is the memory spiking?").
1. **Search:** Gemini uses `grep`, `glob`, and `read_file` to massively scrape logs, memory dumps, and recent commits, dumping raw findings into the Ledger.
2. **Synthesis:** Claude takes Gemini's massive data dump, finds the nuanced needle in the haystack, and presents a concise root-cause analysis to Zack.

## 5. Solving the "Eager Gemini" Problem (Operational Constraints)

To prevent Gemini from masquerading, overstepping, or destroying the architecture, we enforce **Ledger-Based Constraints**:

1. **Strict Capability Scoping:** Gemini CLI is configured to *reject* architectural decisions. If a task requires designing a new data model, Gemini's system prompt forces it to halt and request a Claude Blueprint.
2. **The "Draft-First" Action Gate:** Gemini cannot write to main application files (like `App.tsx` or `main.py`) without a corresponding, active task in the State Ledger that explicitly authorizes touching those files. 
3. **Separation of Voice:** Gemini never speaks as "I, Promaia." Gemini speaks strictly as the Executor agent. All user-facing conversation flows back through Maia's chat interface.

## 6. Implementation Strategy for the Nervous System

To build this, we don't need a massive new framework. We extend the existing Promaia architecture (`AGENT_ORCHESTRATION_ARCHITECTURE.md`):

1. **Expand `AgentOrchestrator`:** Add a `StateLedger` class backed by MuninnDB to store tasks, blueprints, and reviews.
2. **Agent Handshakes:** Create standard JSON schemas for how Claude and Gemini pass data back and forth via the Ledger.
3. **Headless Execution Mode:** Configure Gemini CLI to run in a headless, non-interactive mode where it receives a task ID from Maia, executes it based on the Ledger, and exits.