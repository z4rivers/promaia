---
phase: 06-waste-elimination-spend-visibility
plan: 02
subsystem: agents
tags: [dataclass, gemini, prompt-engineering, caching, context-injection]

# Dependency graph
requires:
  - phase: 05-validate-activate
    provides: "Grounding rules in agent prompts, validated agent pipeline"
  - phase: 06-01
    provides: "ModelRouter, CostTracker, brain.agent_costs table, model field on AgentConfig"
provides:
  - "AgentContext dataclass with to_prompt_block() and load_from_brain()"
  - "get_agent_tools_docs() for per-agent tool injection (ROUTE-04)"
  - "AGENT_TOOL_REGISTRY mapping agents to their MCP tools"
  - "Three restructured agent prompts with implicit-cacheable tier structure"
affects: [06-03-gemini-execution, 06-04-validation]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Implicit-cacheable prompt tiers: anchor (grounding+identity) / tools (runtime injection) / context (few-shot+data)"
    - "AgentContext smart batching: load once per scheduler cycle, share across all agents"
    - "Per-agent tool documentation injection via AGENT_TOOL_REGISTRY"

key-files:
  created:
    - "promaia/agents/agent_context.py"
  modified:
    - "prompts/agent_morning_briefing.md"
    - "prompts/agent_email_triage.md"
    - "prompts/agent_evening_digest.md"

key-decisions:
  - "Office day detection uses day_of_week == Thursday (hardcoded from Zack's schedule)"
  - "AGENT_TOOL_REGISTRY uses static mapping rather than dynamic discovery -- sufficient for 3 known agents"
  - "Profile summary built from top 8 traits by confidence, truncated to 500 chars"
  - "Prompt restructuring confirmed identical to 06-01 output -- no redundant changes needed"

patterns-established:
  - "AgentContext.load_from_brain() as single batched context loader for all agents"
  - "get_agent_tools_docs(agent_name) for ROUTE-04 dynamic tool injection"
  - "Three-tier prompt structure: anchor/tools/context for implicit caching"

requirements-completed: [ROUTE-03, ROUTE-04, ROUTE-05]

# Metrics
duration: 14min
completed: 2026-03-07
---

# Phase 6 Plan 02: AgentContext + Prompt Restructuring Summary

**AgentContext dataclass with batched brain loading and per-agent tool injection, plus three-tier prompt structure optimized for Gemini implicit caching**

## Performance

- **Duration:** 14 min
- **Started:** 2026-03-07T05:52:15Z
- **Completed:** 2026-03-07T06:05:56Z
- **Tasks:** 2
- **Files modified:** 4 (1 created, 3 confirmed-in-place)

## Accomplishments
- AgentContext dataclass with to_prompt_block() rendering ~200-300 token user awareness blocks
- load_from_brain() classmethod serves as batched context loader (smart batching for 3 agents)
- get_agent_tools_docs() returns per-agent MCP tool documentation (ROUTE-04)
- All three agent prompts confirmed in correct three-tier structure for implicit caching (ROUTE-03)

## Task Commits

Each task was committed atomically:

1. **Task 1: Create AgentContext dataclass** - `d160547` (feat)
2. **Task 2: Restructure agent prompts** - No new commit needed (prompts already restructured by 06-01 execution)

## Files Created/Modified
- `promaia/agents/agent_context.py` - AgentContext dataclass, load_from_brain(), get_agent_tools_docs(), AGENT_TOOL_REGISTRY
- `prompts/agent_morning_briefing.md` - Confirmed in three-tier structure (anchor/tools/context)
- `prompts/agent_email_triage.md` - Confirmed in three-tier structure (anchor/tools/context)
- `prompts/agent_evening_digest.md` - Confirmed in three-tier structure (anchor/tools/context)

## Decisions Made
- Office day detection uses hardcoded Thursday check (matches Zack's real schedule)
- AGENT_TOOL_REGISTRY is a static dict mapping -- dynamic discovery would be overengineering for 3 known agents
- Profile summary loads top 8 traits by confidence and concatenates them (keeps it under 200 tokens)
- Prompt restructuring was already applied by 06-01 executor -- verified structure rather than duplicating changes

## Deviations from Plan

### Task 2: Prompt files already restructured

**Found during:** Task 2 (Restructure agent prompts)
**Issue:** The 06-01 plan executor had already restructured all three agent prompts into the exact three-tier format specified in this plan (anchor/tools/context with grounding rules first, tool injection placeholder, few-shot examples, and data instructions last).
**Resolution:** Verified the existing structure passes all verification checks. No redundant changes committed. This is a coordination overlap between 06-01 and 06-02 plans, not a bug.
**Impact:** Zero -- the prompts are in the correct state. One fewer commit is the only difference.

---

**Total deviations:** 1 (plan overlap, no impact)
**Impact on plan:** None. All verification criteria pass. All success criteria met.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- AgentContext is ready for use by GeminiExecutor (06-03)
- get_agent_tools_docs() is ready for prompt assembly in executor
- Three-tier prompt structure is ready for implicit caching at runtime
- load_from_brain() is ready for scheduler-level batched context loading

## Self-Check: PASSED

- All 4 key files exist on disk
- Task 1 commit d160547 found in git log
- All verification scripts pass (AgentContext, prompt structure, tool docs)

---
*Phase: 06-waste-elimination-spend-visibility*
*Completed: 2026-03-07*
