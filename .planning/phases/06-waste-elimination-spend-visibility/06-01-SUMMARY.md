---
phase: 06-waste-elimination-spend-visibility
plan: 01
subsystem: agents
tags: [gemini, model-routing, cost-tracking, mcp, postgres]

# Dependency graph
requires:
  - phase: 05-validate-activate
    provides: Agent pipeline, execution tracker, brain schema
provides:
  - ModelRouter class with TaskType enum, ModelConfig dataclass, model registry
  - CostTracker class with compute_cost, log_call, daily/run spend queries
  - brain.agent_costs table with indexes for cost logging
  - model field on AgentConfig for per-agent model override
  - brain_costs MCP tool for user-facing cost visibility
affects: [06-02, 06-03, 06-04, executor, scheduler, dashboard]

# Tech tracking
tech-stack:
  added: []
  patterns: [ModelConfig dataclass for pricing metadata, CostTracker pattern for per-call logging]

key-files:
  created:
    - promaia/agents/model_router.py
    - promaia/agents/cost_tracker.py
  modified:
    - promaia/brain/schema.sql
    - promaia/agents/agent_config.py
    - promaia/brain/mcp_server.py

key-decisions:
  - "All 3 agents (morning-briefing, email-triage, evening-digest) use Gemini 3 Flash per user decision COST-04"
  - "thinking_budget=0 for Flash-Lite per user decision"
  - "Thinking tokens billed separately via thinking_price_per_m field (not lumped with output)"
  - "ModelConfig is frozen dataclass for immutability"
  - "CostTracker.compute_cost is a static method for use without DB connection"

patterns-established:
  - "ModelConfig dataclass: frozen, with pricing metadata per model"
  - "TASK_MODEL_MAP/AGENT_MODEL_MAP: dict-based routing tables"
  - "Fallback chain via _FALLBACK_CHAIN dict (flash-lite -> flash -> pro -> None)"
  - "CostTracker auto-creates brain.agent_costs on init (same pattern as ExecutionTracker)"

requirements-completed: [ROUTE-01, COST-01, COST-04]

# Metrics
duration: 11min
completed: 2026-03-07
---

# Phase 6 Plan 01: Model Routing Infrastructure Summary

**ModelRouter maps 7 task types and 3 agents to Gemini models with pricing metadata; CostTracker computes model-aware costs; brain_costs MCP tool surfaces spend via Claude Code**

## Performance

- **Duration:** 11 min
- **Started:** 2026-03-07T05:52:53Z
- **Completed:** 2026-03-07T06:04:34Z
- **Tasks:** 3
- **Files modified:** 5

## Accomplishments
- ModelRouter correctly maps all 7 task types (classify, extract, embed, synthesize, reason, create, heartbeat) and all 3 agents to specific Gemini models
- CostTracker computes accurate model-aware costs with cached token discounts, thinking token billing, and zero-usage edge case handling
- brain.agent_costs table auto-creates with schema and 3 indexes on CostTracker init
- brain_costs MCP tool returns formatted daily/weekly cost breakdown when Zack asks "what am I spending?"
- AgentConfig has optional model field for per-agent model override via promaia.config.json

## Task Commits

Each task was committed atomically:

1. **Task 1: Create ModelRouter** - `14e820a` (feat)
2. **Task 2: Create CostTracker + schema + AgentConfig** - `c0a8259` (feat)
3. **Task 3: Add brain_costs MCP tool** - `78e7b50` (feat)

## Files Created/Modified
- `promaia/agents/model_router.py` - TaskType enum, ModelConfig dataclass, MODELS registry, TASK_MODEL_MAP, AGENT_MODEL_MAP, ModelRouter class with get_model/get_agent_model/get_fallback_model
- `promaia/agents/cost_tracker.py` - CostRecord dataclass, CostTracker class with log_call, compute_cost, get_daily_spend, get_run_spend, get_daily_summary
- `promaia/brain/schema.sql` - Added brain.agent_costs table definition with 3 indexes
- `promaia/agents/agent_config.py` - Added optional model field to AgentConfig dataclass
- `promaia/brain/mcp_server.py` - Added brain_costs tool registration, dispatcher entry, and _handle_brain_costs handler (tool count 15 -> 16)

## Decisions Made
- All 3 agents use Gemini 3 Flash per user decision COST-04 (research originally suggested Pro for morning-briefing)
- thinking_budget=0 for Flash-Lite per user decision (no thinking support)
- ModelConfig is a frozen dataclass for immutability and safety
- Thinking tokens billed via separate thinking_price_per_m field rather than lumping with output_price_per_m
- CostTracker.compute_cost is a static method so it can be used without a DB connection for pure computation

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- ModelRouter and CostTracker are ready for 06-02 (Gemini executor) to use for model selection and cost logging
- brain.agent_costs table is created; 06-02 will begin populating it with actual API call costs
- brain_costs MCP tool is wired up; will show data once agents start logging costs

## Self-Check: PASSED

All 5 created/modified files verified on disk. All 3 task commits verified in git log.

---
*Phase: 06-waste-elimination-spend-visibility*
*Completed: 2026-03-07*
