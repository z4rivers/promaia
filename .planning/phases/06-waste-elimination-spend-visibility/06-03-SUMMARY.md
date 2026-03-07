---
phase: 06-waste-elimination-spend-visibility
plan: 03
subsystem: agents
tags: [gemini, executor, budget, fallback, runaway-detection, cost-tracking]

# Dependency graph
requires:
  - phase: 06-01
    provides: "ModelRouter, CostTracker, brain.agent_costs table, model field on AgentConfig"
  - phase: 06-02
    provides: "AgentContext dataclass, get_agent_tools_docs(), AGENT_TOOL_REGISTRY"
provides:
  - "GeminiExecutor class with generate() and generate_with_fallback() methods"
  - "BudgetGuard class with per-run ($0.50) and daily ($2.00) budget enforcement"
  - "RunawayDetector class for stuck agent detection"
  - "Gemini execution path in AgentExecutor (routes by model_id prefix)"
  - "Daily budget check in AgentScheduler before each agent run"
affects: [06-04-validation, executor, scheduler, dashboard]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "GeminiExecutor: single-call API wrapper with cost tracking and fallback"
    - "BudgetGuard: pre-run daily check + mid-run per-run check pattern"
    - "RunawayDetector: iteration + cost + similarity triple-check for stuck agents"
    - "Model routing in executor: model_id.startswith('gemini') selects Gemini path"

key-files:
  created:
    - "promaia/agents/gemini_executor.py"
    - "promaia/agents/budget_guard.py"
  modified:
    - "promaia/agents/executor.py"
    - "promaia/agents/scheduler.py"

key-decisions:
  - "Synchronous genai.generate_content call (matching nl_orchestrator.py pattern, not asyncio.to_thread)"
  - "Reverse model_id-to-key lookup dict for fallback chain navigation"
  - "Single-level fallback only (no cascade) to prevent cost explosion"
  - "RunawayDetector uses word-set Jaccard overlap for similarity (no external deps)"
  - "Budget-blocked agents still sleep for their full interval before retry"

patterns-established:
  - "GeminiExecutor.generate(): builds GenerateContentConfig, extracts usage_metadata, logs CostRecord"
  - "_execute_with_gemini(): AgentContext + tool docs + prompt file -> system_instruction; initial_context -> contents"
  - "Model routing: model_config.model_id.startswith('gemini') routes to Gemini, else SDK/legacy"
  - "Budget guard pattern: can_start_run() before, check_run_budget() after each API call"

requirements-completed: [ROUTE-02, COST-02, COST-03]

# Metrics
duration: 9min
completed: 2026-03-07
---

# Phase 6 Plan 03: Gemini Execution Path + Budget Enforcement Summary

**GeminiExecutor with fallback chain routes all 3 agents to Gemini API, BudgetGuard enforces per-run and daily caps, RunawayDetector catches stuck agents via iteration/cost/similarity checks**

## Performance

- **Duration:** 9 min
- **Started:** 2026-03-07T06:12:09Z
- **Completed:** 2026-03-07T06:21:44Z
- **Tasks:** 2
- **Files modified:** 4 (2 created, 2 modified)

## Accomplishments
- GeminiExecutor wraps google.genai with per-call cost logging to brain.agent_costs and automatic fallback to next-tier model on API errors (ROUTE-02)
- BudgetGuard enforces $0.50 per-run cap during execution and $2.00 daily cap before agent runs in scheduler (COST-02, COST-03)
- RunawayDetector provides triple-check safety: iteration count, cumulative cost, and repetitive output detection (word-set Jaccard overlap)
- executor.py routes to Gemini when model starts with "gemini", preserving Claude SDK and legacy iteration paths as fallback
- scheduler.py checks daily budget before every agent run, skipping non-critical agents when budget is exceeded

## Task Commits

Each task was committed atomically:

1. **Task 1: Create GeminiExecutor and BudgetGuard** - `4d6d34b` (feat)
2. **Task 2: Wire GeminiExecutor into executor.py and add budget check to scheduler.py** - `41a9c70` (feat)

## Files Created/Modified
- `promaia/agents/gemini_executor.py` - GeminiExecutor class with generate(), generate_with_fallback(), reverse model_id-to-key lookup
- `promaia/agents/budget_guard.py` - BudgetGuard (per-run + daily caps) and RunawayDetector (iteration + cost + similarity)
- `promaia/agents/executor.py` - Added Gemini imports, router/cost_tracker/gemini_executor/budget_guard to __init__, model routing in execute(), _execute_with_gemini() method
- `promaia/agents/scheduler.py` - Added BudgetGuard/CostTracker imports, budget_guard to __init__, daily budget check before executor.execute()

## Decisions Made
- Used synchronous generate_content (matching nl_orchestrator.py pattern) rather than asyncio.to_thread -- existing agents already block during API calls
- Created _MODEL_ID_TO_KEY reverse lookup dict for fallback chain navigation (model_id -> key -> fallback)
- Single-level fallback only (flash -> pro, no cascade) to prevent cost explosion from repeated retries
- RunawayDetector uses word-set Jaccard overlap (intersection/union) for similarity -- simple, no external dependencies, works for agent output
- Budget-blocked agents sleep for their full interval before retry, rather than immediately re-checking

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - GOOGLE_API_KEY environment variable is already configured (used by nl_orchestrator.py).

## Next Phase Readiness
- Gemini execution path is ready for end-to-end validation in 06-04
- All 3 agents will route to Gemini 3 Flash on next scheduler run
- Budget enforcement is active -- non-critical agents will be skipped if daily spend exceeds $2.00
- Cost logging is live -- brain_costs MCP tool will show actual Gemini spend data

## Self-Check: PASSED

- All 4 key files verified on disk (2 created, 2 modified)
- Task 1 commit 4d6d34b found in git log
- Task 2 commit 41a9c70 found in git log
- All 6 verification checks pass (executor construction, scheduler construction, imports, SDK path, budget check, GeminiExecutor methods)

---
*Phase: 06-waste-elimination-spend-visibility*
*Completed: 2026-03-07*
