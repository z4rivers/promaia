# Phase 6: Waste Elimination + Spend Visibility - Research

**Researched:** 2026-03-06
**Domain:** Model routing, cost tracking, prompt caching, budget enforcement (Google Gemini API + Python)
**Confidence:** HIGH

## Summary

Phase 6 transforms the agent pipeline from a single-model Claude SDK system ($0.132/cycle) to a multi-model Gemini-powered system with per-call cost tracking, prompt caching, and runaway-loop protection. The target is ~$0.016/cycle -- an 88% reduction.

The current executor (`promaia/agents/executor.py`) uses the Claude Agent SDK with hardcoded Claude Sonnet pricing. It tracks execution metrics in `agent_executions` table but lacks per-call granularity, model-aware pricing, and budget enforcement. The system prompt and context are assembled fresh every run with no caching. The transition requires: (1) replacing the Claude SDK execution path with direct `google.genai` API calls, (2) creating a model router that maps task types to models, (3) adding a `brain.agent_costs` table for per-call logging, (4) implementing explicit context caching via the Gemini caching API, and (5) adding budget caps and runaway detection.

**Primary recommendation:** Build a `ModelRouter` class that maps task types (classify, extract, embed, synthesize, reason, create, heartbeat) to specific Gemini models, with the `google.genai` SDK as the direct execution layer. Use explicit context caching for system prompts + stable context, and rely on implicit caching for repeated prefixes. Track every API call in `brain.agent_costs` with model, tokens, cached tokens, and computed cost.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| ROUTE-01 | Model router selects appropriate model per task type | ModelRouter class maps task types to Gemini models; see Architecture Patterns |
| ROUTE-02 | Fallback chain activates when primary model fails | Router with try/except escalation; see Fallback Chain pattern |
| ROUTE-03 | Agent prompts restructured into cacheable tiers | Gemini explicit caching API with anchor/tools/context split; see Prompt Caching |
| ROUTE-04 | Dynamic tool injection reduces prompt size | Only include MCP tool docs relevant to each agent; see Tool Injection |
| ROUTE-05 | AgentContext dataclass provides standardized awareness | Dataclass with user profile, time, goals, events, domain state; see AgentContext |
| COST-01 | brain.agent_costs table logs every API call | New Postgres table with model, tokens, cached_tokens, cost; see Cost Tracking |
| COST-02 | Per-run budget cap enforced | Budget tracker checks cumulative cost mid-run; see Budget Enforcement |
| COST-03 | Daily budget cap skips non-critical runs | Scheduler queries daily spend before launching non-critical agents; see Budget Enforcement |
| COST-04 | Each agent uses assigned model | Agent config gets `model` field mapped to Gemini model IDs; see Model Assignment |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `google-genai` | latest (1.x+) | Gemini API client -- generate_content, caching, batch | Official Google SDK, already imported in nl_orchestrator.py |
| `psycopg2` | existing | Postgres for cost tracking table | Already used throughout codebase |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `dataclasses` | stdlib | AgentContext, ModelConfig, CostRecord | All structured data |
| `enum` | stdlib | TaskType enum for model routing | Model router |
| `decimal` | stdlib | Precise cost arithmetic | Cost calculations |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Direct google-genai | LiteLLM | Adds dependency; google-genai already in codebase and sufficient |
| Postgres cost table | SQLite | Already using Postgres for everything; no reason to split |
| Manual model routing | LLM-based routing | Overkill for 3 agents with known task types |

**Installation:**
```bash
# google-genai already installed. Verify:
pip show google-genai
# No new dependencies needed
```

## Architecture Patterns

### Recommended Project Structure
```
promaia/
  agents/
    executor.py           # Modified: uses ModelRouter instead of Claude SDK
    model_router.py       # NEW: TaskType -> model mapping + fallback
    gemini_executor.py    # NEW: Replaces Claude SDK execution with google.genai
    cost_tracker.py       # NEW: Per-call logging to brain.agent_costs
    budget_guard.py       # NEW: Budget caps and runaway detection
    agent_context.py      # NEW: AgentContext dataclass
    prompt_cache.py       # NEW: Gemini explicit cache management
    agent_config.py       # Modified: add model field
  brain/
    schema.sql            # Modified: add brain.agent_costs table
```

### Pattern 1: Model Router (ROUTE-01, ROUTE-04)

**What:** A `ModelRouter` class that maps task types to specific Gemini models with pricing metadata.
**When to use:** Every API call goes through the router.

```python
from enum import Enum
from dataclasses import dataclass
from typing import Optional

class TaskType(Enum):
    CLASSIFY = "classify"       # Email classification, urgency detection
    EXTRACT = "extract"         # Data extraction, formatting
    EMBED = "embed"             # Embedding generation
    SYNTHESIZE = "synthesize"   # Briefing, digest, triage output
    REASON = "reason"           # Complex analysis, planning
    CREATE = "create"           # Content generation
    HEARTBEAT = "heartbeat"     # Health checks

@dataclass
class ModelConfig:
    model_id: str
    display_name: str
    input_price_per_m: float   # $ per 1M input tokens
    output_price_per_m: float  # $ per 1M output tokens
    cached_input_discount: float  # multiplier (0.1 = 90% off)
    min_cache_tokens: int
    max_thinking_budget: int   # 0 = no thinking support

# Model registry
MODELS = {
    "gemini-2.5-flash": ModelConfig(
        model_id="gemini-2.5-flash-preview-05-20",
        display_name="Gemini 2.5 Flash",
        input_price_per_m=0.30,
        output_price_per_m=2.50,
        cached_input_discount=0.1,
        min_cache_tokens=1024,
        max_thinking_budget=24576,
    ),
    "gemini-2.5-flash-lite": ModelConfig(
        model_id="gemini-2.5-flash-lite",  # verify exact ID
        display_name="Gemini 2.5 Flash-Lite",
        input_price_per_m=0.10,
        output_price_per_m=0.40,
        cached_input_discount=0.1,
        min_cache_tokens=1024,
        max_thinking_budget=0,
    ),
    "gemini-3.1-pro": ModelConfig(
        model_id="gemini-3.1-pro-preview",
        display_name="Gemini 3.1 Pro",
        input_price_per_m=2.00,
        output_price_per_m=12.00,
        cached_input_discount=0.1,
        min_cache_tokens=4096,
        max_thinking_budget=0,
    ),
}

# Task -> Model mapping (the routing table)
TASK_MODEL_MAP = {
    TaskType.CLASSIFY:   "gemini-2.5-flash-lite",
    TaskType.EXTRACT:    "gemini-2.5-flash-lite",
    TaskType.EMBED:      "gemini-embedding-001",
    TaskType.SYNTHESIZE: "gemini-2.5-flash",
    TaskType.REASON:     "gemini-3.1-pro",
    TaskType.CREATE:     "gemini-2.5-flash",
    TaskType.HEARTBEAT:  "gemini-2.5-flash-lite",
}

class ModelRouter:
    def get_model(self, task_type: TaskType) -> ModelConfig:
        model_key = TASK_MODEL_MAP[task_type]
        return MODELS[model_key]

    def get_agent_model(self, agent_name: str) -> ModelConfig:
        """Get the assigned model for a specific agent."""
        # Agent-level overrides (from COST-04)
        agent_models = {
            "morning-briefing": "gemini-2.5-flash",
            "email-triage": "gemini-2.5-flash",
            "evening-digest": "gemini-2.5-flash",
        }
        model_key = agent_models.get(agent_name, "gemini-2.5-flash")
        return MODELS[model_key]
```

### Pattern 2: Gemini Direct Execution (replaces Claude SDK)

**What:** Replace `_execute_with_sdk` in executor.py with direct `google.genai` calls.
**When to use:** All agent runs.

```python
from google import genai
from google.genai import types

class GeminiExecutor:
    def __init__(self, api_key: str):
        self.client = genai.Client(api_key=api_key)

    async def generate(
        self,
        model_config: ModelConfig,
        system_instruction: str,
        contents: str,
        cached_content: str = None,
        thinking_budget: int = None,
    ) -> dict:
        config = types.GenerateContentConfig(
            system_instruction=system_instruction,
        )

        if cached_content:
            config.cached_content = cached_content

        if thinking_budget and model_config.max_thinking_budget > 0:
            config.thinking_config = types.ThinkingConfig(
                thinking_budget=min(thinking_budget, model_config.max_thinking_budget)
            )

        response = self.client.models.generate_content(
            model=model_config.model_id,
            contents=contents,
            config=config,
        )

        # Extract usage for cost tracking
        usage = response.usage_metadata
        return {
            "content": response.text,
            "input_tokens": usage.prompt_token_count,
            "output_tokens": usage.candidates_token_count,
            "cached_tokens": getattr(usage, 'cached_content_token_count', 0) or 0,
            "thinking_tokens": getattr(usage, 'thoughts_token_count', 0) or 0,
            "model": model_config.model_id,
        }
```

### Pattern 3: Explicit Prompt Caching (ROUTE-03)

**What:** Cache stable prompt components (system instructions, grounding rules, tool docs) using Gemini's explicit caching API. Each agent's system prompt + grounding rules form the "anchor" tier that gets cached.
**When to use:** Agent scheduler creates/refreshes caches at startup, reuses for all runs.

```python
from google import genai
from google.genai import types

class PromptCacheManager:
    def __init__(self, client: genai.Client):
        self.client = client
        self._caches = {}  # agent_name -> cache_name

    def get_or_create_cache(
        self,
        agent_name: str,
        model_id: str,
        system_instruction: str,
        stable_context: str,
        ttl_seconds: int = 3600,  # 1 hour default
    ) -> str:
        """Get existing cache or create new one. Returns cache name."""
        # Check if cache exists and is still valid
        if agent_name in self._caches:
            try:
                cache = self.client.caches.get(name=self._caches[agent_name])
                return cache.name
            except Exception:
                del self._caches[agent_name]

        # Create new cache
        cache = self.client.caches.create(
            model=model_id,
            config=types.CreateCachedContentConfig(
                display_name=f"promaia-{agent_name}",
                system_instruction=system_instruction,
                contents=[stable_context],
                ttl=f"{ttl_seconds}s",
            )
        )
        self._caches[agent_name] = cache.name
        return cache.name
```

**Prompt tier structure for caching:**
1. **Anchor tier** (cached): System instruction + grounding rules + agent identity (~500 tokens, stable across runs)
2. **Tools tier** (cached with anchor): Tool documentation relevant to this agent (~200-500 tokens, stable)
3. **Context tier** (not cached): Live data -- emails, memories, brain state (changes every run)

### Pattern 4: Cost Tracking (COST-01)

**What:** Log every API call to `brain.agent_costs` with full metadata.
**When to use:** Wraps every `generate_content` call.

```python
@dataclass
class CostRecord:
    agent_name: str
    model_id: str
    task_type: str
    input_tokens: int
    output_tokens: int
    cached_tokens: int
    thinking_tokens: int
    cost_usd: float
    execution_id: int
    created_at: datetime

class CostTracker:
    def __init__(self):
        self._ensure_table()

    def _ensure_table(self):
        """Create brain.agent_costs if not exists."""
        # See schema in Don't Hand-Roll section

    def log_call(self, record: CostRecord):
        """Insert a cost record."""
        with pg_connect() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO brain.agent_costs
                (agent_name, model_id, task_type, input_tokens, output_tokens,
                 cached_tokens, thinking_tokens, cost_usd, execution_id, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                record.agent_name, record.model_id, record.task_type,
                record.input_tokens, record.output_tokens,
                record.cached_tokens, record.thinking_tokens,
                record.cost_usd, record.execution_id, record.created_at
            ))
            conn.commit()

    def compute_cost(self, model_config: ModelConfig, usage: dict) -> float:
        """Compute cost from usage metadata and model pricing."""
        input_tokens = usage["input_tokens"]
        output_tokens = usage["output_tokens"]
        cached_tokens = usage.get("cached_tokens", 0)
        non_cached_input = input_tokens - cached_tokens

        input_cost = (non_cached_input * model_config.input_price_per_m / 1_000_000)
        cached_cost = (cached_tokens * model_config.input_price_per_m
                       * model_config.cached_input_discount / 1_000_000)
        output_cost = (output_tokens * model_config.output_price_per_m / 1_000_000)

        return input_cost + cached_cost + output_cost
```

### Pattern 5: Budget Enforcement (COST-02, COST-03)

**What:** Check cumulative cost before/during agent runs. Kill runs that exceed budget.
**When to use:** Scheduler checks daily budget before launching; executor checks per-run budget mid-execution.

```python
class BudgetGuard:
    def __init__(self, per_run_cap: float = 0.50, daily_cap: float = 2.00):
        self.per_run_cap = per_run_cap
        self.daily_cap = daily_cap

    def can_start_run(self, agent_name: str, is_critical: bool = False) -> bool:
        """Check if daily budget allows this run."""
        if is_critical:
            return True  # Critical runs always proceed
        daily_spend = self._get_daily_spend()
        return daily_spend < self.daily_cap

    def check_run_budget(self, execution_id: int) -> bool:
        """Check if current run is within per-run budget."""
        run_spend = self._get_run_spend(execution_id)
        return run_spend < self.per_run_cap

    def _get_daily_spend(self) -> float:
        with pg_connect() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT COALESCE(SUM(cost_usd), 0)
                FROM brain.agent_costs
                WHERE created_at >= CURRENT_DATE
            """)
            return cursor.fetchone()[0]

    def _get_run_spend(self, execution_id: int) -> float:
        with pg_connect() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT COALESCE(SUM(cost_usd), 0)
                FROM brain.agent_costs
                WHERE execution_id = %s
            """, (execution_id,))
            return cursor.fetchone()[0]
```

### Pattern 6: Runaway Loop Detection (Success Criterion 4)

**What:** Detect when an agent is stuck retrying or iterating without making progress.
**When to use:** Wraps the iteration loop in executor.

```python
class RunawayDetector:
    def __init__(self, max_iterations: int = 5, max_cost: float = 0.50,
                 similarity_threshold: float = 0.9):
        self.max_iterations = max_iterations
        self.max_cost = max_cost
        self.similarity_threshold = similarity_threshold
        self.responses = []
        self.total_cost = 0.0

    def check(self, response_text: str, cost: float) -> tuple[bool, str]:
        """Returns (should_kill, reason)."""
        self.responses.append(response_text)
        self.total_cost += cost

        # Check iteration count
        if len(self.responses) > self.max_iterations:
            return True, f"Exceeded {self.max_iterations} iterations"

        # Check cost
        if self.total_cost > self.max_cost:
            return True, f"Exceeded ${self.max_cost:.2f} budget"

        # Check for repetitive output (last 3 responses similar)
        if len(self.responses) >= 3:
            recent = self.responses[-3:]
            if self._responses_similar(recent):
                return True, "Repetitive output detected"

        return False, ""

    def _responses_similar(self, responses: list) -> bool:
        """Check if responses are too similar (stuck in loop)."""
        # Simple: compare length ratios and shared words
        for i in range(len(responses) - 1):
            a, b = responses[i], responses[i + 1]
            words_a = set(a.lower().split())
            words_b = set(b.lower().split())
            if not words_a or not words_b:
                continue
            overlap = len(words_a & words_b) / max(len(words_a), len(words_b))
            if overlap < self.similarity_threshold:
                return False
        return True
```

### Pattern 7: AgentContext Dataclass (ROUTE-05)

**What:** Standardized context object injected into every agent prompt.
**When to use:** Every agent run -- replaces ad-hoc brain context loading in executor.

```python
@dataclass
class AgentContext:
    """Standardized awareness context for all agents."""
    # User identity
    user_name: str
    user_profile_summary: str  # ~200 tokens from brain.profile

    # Temporal
    current_time: datetime
    day_of_week: str
    is_office_day: bool

    # Goals & state
    pending_actions: list[dict]
    active_projects: list[dict]
    recent_memories: list[dict]

    # Domain-specific (populated per agent)
    domain_state: dict  # e.g., {"unread_emails": 5, "calendar_events_today": 2}

    def to_prompt_block(self) -> str:
        """Render as a prompt-injectable text block (~200-300 tokens)."""
        parts = [
            f"Current time: {self.current_time.strftime('%Y-%m-%d %H:%M %Z')} ({self.day_of_week})",
            f"User: {self.user_name}",
            f"Profile: {self.user_profile_summary}",
        ]
        if self.is_office_day:
            parts.append("Note: Office day today (8am-12pm)")
        if self.pending_actions:
            parts.append(f"Pending actions: {len(self.pending_actions)}")
        if self.active_projects:
            parts.append(f"Active projects: {', '.join(p['name'] for p in self.active_projects)}")
        return "\n".join(parts)
```

### Pattern 8: Cost Summary View (Success Criterion 5)

**What:** MCP tool and/or CLI command to show daily/weekly cost summary.
**When to use:** Zack asks "how much am I spending?" -- also visible on dashboard.

```sql
-- Daily summary query
SELECT
    DATE(created_at) as day,
    agent_name,
    model_id,
    COUNT(*) as calls,
    SUM(input_tokens) as total_input,
    SUM(output_tokens) as total_output,
    SUM(cached_tokens) as total_cached,
    SUM(cost_usd) as total_cost
FROM brain.agent_costs
WHERE created_at >= CURRENT_DATE - INTERVAL '7 days'
GROUP BY DATE(created_at), agent_name, model_id
ORDER BY day DESC, total_cost DESC;
```

### Anti-Patterns to Avoid
- **Re-implementing prompt caching in application code:** Use Gemini's native caching API -- it handles TTL, invalidation, and token counting. Don't build a custom prompt hash table.
- **Calling Claude SDK for Gemini tasks:** The current executor uses `ClaudeSDKClient`. The Gemini execution path must use `google.genai` directly. Do not attempt to route Gemini calls through the Claude SDK.
- **Mixing XML tags and Markdown in Gemini prompts:** Gemini supports either XML tags OR Markdown for structure, but mixing them degrades output quality. Pick one per prompt.
- **Hardcoding prices:** Use the `ModelConfig` dataclass so prices can be updated in one place when Gemini pricing changes.
- **Checking budget after the call:** Budget should be checked BEFORE making the API call. Once tokens are consumed, the cost is incurred.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Prompt caching | Custom hash-based cache | `client.caches.create()` (Gemini API) | Handles TTL, storage, token counting, 90% discount automatically |
| Implicit caching | Prefix-matching logic | Gemini implicit caching (automatic) | Just structure prompts with stable prefixes; savings are automatic |
| Token counting | Character estimation | `response.usage_metadata` | Exact counts including cached_tokens and thinking_tokens |
| Cost calculation | Rough estimates | `ModelConfig` pricing * `usage_metadata` fields | Current executor uses hardcoded Claude Sonnet prices ($3/$15) |
| Rate limiting | Sleep-based backoff | Google API built-in retry + free tier limits (250 RPD Flash) | Free tier sufficient for 3x daily agent runs |

**Key insight:** The Gemini API provides exact token counts (including cached and thinking tokens) in every response. The current codebase estimates costs with hardcoded Claude pricing -- this must be replaced with model-aware computation.

## Common Pitfalls

### Pitfall 1: Minimum Token Threshold for Caching
**What goes wrong:** Cache creation fails silently when content is below minimum.
**Why it happens:** Gemini requires minimum 1,024 tokens (Flash) or 4,096 tokens (Pro) for explicit caching.
**How to avoid:** Check token count before cache creation. Agent system prompts (~500 tokens) alone are too small -- must bundle with stable context (grounding rules, tool docs) to reach 1,024+.
**Warning signs:** `cached_content_token_count` is 0 in usage_metadata despite creating a cache.

### Pitfall 2: Gemini Temperature Default
**What goes wrong:** Output quality differs from Claude defaults.
**Why it happens:** Gemini 2.5+ models are trained to work best at temperature 1.0. Setting it lower may reduce quality rather than improve determinism.
**How to avoid:** Keep temperature at 1.0 for Gemini 2.5+ models. Only lower for pure extraction tasks on Flash-Lite.
**Warning signs:** Agent output becomes unexpectedly terse or repetitive.

### Pitfall 3: System Instruction vs Contents Placement
**What goes wrong:** Long data contexts placed in system_instruction get cached but waste cache storage cost.
**Why it happens:** Developer puts everything in system_instruction thinking it helps.
**How to avoid:** Only stable, reusable instructions go in system_instruction. Dynamic data (emails, memories) goes in contents. System instruction is automatically included in explicit caches.
**Warning signs:** Cache storage costs ($1/hr for Flash explicit caching) exceed savings.

### Pitfall 4: Claude SDK Import Failure Path
**What goes wrong:** Executor fails when Claude SDK is unavailable but Gemini path is wanted.
**Why it happens:** Current code has `SDK_AVAILABLE` flag and falls back to legacy iteration loop, both Claude-only.
**How to avoid:** Add a new `GeminiExecutor` path that doesn't depend on `claude_agent_sdk` imports. The executor should check agent's assigned model family and route to the appropriate execution path.
**Warning signs:** `ImportError` for `claude_agent_sdk` causing fallback to legacy mode.

### Pitfall 5: Free Tier Rate Limits
**What goes wrong:** Agent runs fail with 429 errors during development/testing.
**Why it happens:** Free tier allows 250 RPD for Flash, 100 RPD for Pro. Rapid testing can exhaust this.
**How to avoid:** Track daily API call counts in `brain.agent_costs`. Add rate limit awareness to `BudgetGuard`. For production 3x/day agent runs, this is a non-issue.
**Warning signs:** HTTP 429 responses from Gemini API.

### Pitfall 6: Thinking Token Costs
**What goes wrong:** Cost estimates miss thinking tokens, which are billed as output tokens.
**Why it happens:** `thoughts_token_count` is a separate field from `candidates_token_count` in usage_metadata.
**How to avoid:** Include thinking tokens in cost calculation: total output = candidates_token_count + thoughts_token_count. Or set thinking_budget=0 for tasks that don't need reasoning.
**Warning signs:** Actual bills higher than tracked costs.

### Pitfall 7: Idempotent Email Processing (Success Criterion 2)
**What goes wrong:** Same emails get re-summarized on every agent run, wasting tokens.
**Why it happens:** Context loading doesn't track which emails were already processed.
**How to avoid:** Track last-processed email timestamp/ID per agent. Only load emails newer than last processed. Store in `agent_executions` or a dedicated `agent_state` table.
**Warning signs:** Token usage doesn't decrease after initial run; same content repeated in context.

## Code Examples

### Gemini generate_content with Cost Tracking
```python
# Source: https://ai.google.dev/gemini-api/docs/tokens
from google import genai
from google.genai import types

client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))

response = client.models.generate_content(
    model="gemini-2.5-flash-preview-05-20",
    contents="Summarize these emails: ...",
    config=types.GenerateContentConfig(
        system_instruction="You are an email triage agent.",
        thinking_config=types.ThinkingConfig(thinking_budget=2048),
    )
)

# Extract usage for cost tracking
usage = response.usage_metadata
print(f"Input: {usage.prompt_token_count}")
print(f"Output: {usage.candidates_token_count}")
print(f"Cached: {usage.cached_content_token_count}")
print(f"Thinking: {usage.thoughts_token_count}")
print(f"Total: {usage.total_token_count}")
```

### Explicit Cache Creation and Usage
```python
# Source: https://ai.google.dev/gemini-api/docs/caching
from google import genai
from google.genai import types

client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))

# Create cache with system prompt + stable context
cache = client.caches.create(
    model="gemini-2.5-flash-preview-05-20",
    config=types.CreateCachedContentConfig(
        display_name="promaia-email-triage",
        system_instruction="You are Zack's email triage agent...",
        contents=[grounding_rules + tool_documentation],
        ttl="3600s",  # 1 hour
    )
)

# Use cache in subsequent requests (dynamic content only)
response = client.models.generate_content(
    model="gemini-2.5-flash-preview-05-20",
    contents="Here are today's emails: ...",
    config=types.GenerateContentConfig(
        cached_content=cache.name,
    )
)

# cached_content_token_count shows how many tokens were cached
print(f"Cached tokens: {response.usage_metadata.cached_content_token_count}")
```

### brain.agent_costs Table Schema
```sql
-- Source: Custom for promaia (modeled on existing brain schema patterns)
CREATE TABLE IF NOT EXISTS brain.agent_costs (
    id SERIAL PRIMARY KEY,
    execution_id INTEGER REFERENCES agent_executions(id),
    agent_name TEXT NOT NULL,
    model_id TEXT NOT NULL,
    task_type TEXT,  -- classify, extract, synthesize, reason, etc.
    input_tokens INTEGER DEFAULT 0,
    output_tokens INTEGER DEFAULT 0,
    cached_tokens INTEGER DEFAULT 0,
    thinking_tokens INTEGER DEFAULT 0,
    cost_usd REAL NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for cost queries
CREATE INDEX IF NOT EXISTS idx_agent_costs_agent
    ON brain.agent_costs (agent_name, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_agent_costs_date
    ON brain.agent_costs (created_at DESC);

CREATE INDEX IF NOT EXISTS idx_agent_costs_execution
    ON brain.agent_costs (execution_id);
```

### Daily Cost Summary Query
```sql
-- What Zack sees when asking "how much am I spending?"
SELECT
    DATE(created_at) as day,
    agent_name,
    COUNT(*) as api_calls,
    SUM(input_tokens) as input_tok,
    SUM(output_tokens) as output_tok,
    SUM(cached_tokens) as cached_tok,
    ROUND(SUM(cost_usd)::numeric, 4) as total_cost
FROM brain.agent_costs
WHERE created_at >= CURRENT_DATE - INTERVAL '7 days'
GROUP BY DATE(created_at), agent_name
ORDER BY day DESC, total_cost DESC;
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Claude SDK for agent execution | Direct google.genai calls for Gemini models | Phase 6 | 88% cost reduction ($0.132 -> ~$0.016/cycle) |
| Hardcoded Claude pricing ($3/$15 per 1M) | Model-aware pricing via ModelConfig | Phase 6 | Accurate cost tracking |
| No prompt caching | Gemini explicit + implicit caching | Phase 6 | 90% discount on cached input tokens |
| Single model for all tasks | Task-type model routing | Phase 6 | Right-sized models for each task |
| No budget enforcement | Per-run + daily caps | Phase 6 | Prevents cost overruns |
| Claude agent SDK (claude_agent_sdk) | google.genai generate_content | Phase 6 | Direct API control, no SDK abstraction layer |

**Deprecated/outdated:**
- `claude_agent_sdk` imports in executor.py: Keep as fallback for non-agent uses, but new agent execution path bypasses entirely
- `_estimate_cost()` method in executor.py: Hardcoded $3/$15 Claude pricing -- replaced by `CostTracker.compute_cost()`
- `text-embedding-004`: Already noted as broken in STATE.md -- replaced by `gemini-embedding-001`

## Important Technical Notes

### Gemini Prompting Differences from Claude
These must be applied when restructuring agent prompts:

1. **Constraints at TOP of system instruction** -- not bottom. Gemini processes system instructions differently.
2. **Few-shot examples > verbose instructions** -- agent prompts should include 1-2 example outputs.
3. **Temperature 1.0** for 2.5+ models -- do not lower thinking it helps determinism.
4. **Long context: instructions LAST after data** -- for user messages with lots of data, put the task instruction at the end.
5. **XML tags OR Markdown for structure** -- never mix. Current prompts use Markdown, keep it.
6. **Thinking budget controllable** -- set thinking_budget=0 for Flash-Lite extraction tasks, 2048+ for Flash synthesis tasks.

### Implicit Caching (Free Automatic Savings)
Gemini 2.5+ models automatically cache common request prefixes. To maximize implicit cache hits:
- Keep system instruction identical across requests for the same agent
- Structure user messages with stable prefix (grounding rules, tool docs) before dynamic content
- Minimum 1,024 tokens for Flash, 2,048 for Pro to trigger implicit caching
- Check `cached_content_token_count` in usage_metadata to verify hits

### Explicit vs Implicit Caching Decision
- **Explicit caching**: Use for system prompts + grounding rules that repeat across runs for the same agent. Worth the $1/hr storage if you save more on input token discounts.
- **Implicit caching**: Free, automatic. Relies on prefix matching. Good for same-agent repeated calls within a short window.
- **For 3x/day agent runs**: Explicit caching may not pay off if storage cost > token savings. Calculate: if cached content is 2,000 tokens and agent runs 3x/day, savings = 3 * 2000 * $0.27/1M = $0.0016/day. Storage at $1/hr for even 1 hour = $1.00. **Verdict: Rely on implicit caching for this workload volume. Only use explicit caching if runs increase to 10+/day or context grows significantly.**

### Smart Batching (Success Criterion 7)
For the current 3-agent setup, batching opportunities are limited but real:
- **Profile context loading**: Load once, share across all 3 agents (AgentContext pattern)
- **Email context**: Load once for email-triage, pass digest to morning-briefing and evening-digest
- **Batch API**: Not useful for real-time agent runs (24hr turnaround). Reserve for bulk reprocessing tasks.

## Open Questions

1. **Google API Key Billing Mode**
   - What we know: Free tier (250 RPD Flash, 100 RPD Pro) may be sufficient for 3x daily runs
   - What's unclear: Whether the $20/mo paid plan is needed for higher rate limits or if free tier suffices
   - Recommendation: Start with free tier, monitor RPD usage, upgrade if hitting limits

2. **Claude SDK Retention**
   - What we know: Current agents use Claude SDK. Opus 4.6 is reserved for planning/reasoning.
   - What's unclear: Should the Claude SDK execution path be kept for future use, or fully replaced?
   - Recommendation: Keep Claude SDK path but make it a secondary option via model family detection. Primary path is Gemini.

3. **MCP Tool Compatibility with Gemini**
   - What we know: Current MCP tools (gmail, calendar) are launched as subprocess servers by the Claude SDK.
   - What's unclear: Whether google.genai supports MCP tool integration or if tools must be reimplemented as function declarations.
   - Recommendation: For Phase 6, load context data directly (as currently done in `_load_initial_context`). MCP tool integration with Gemini can be deferred -- agents primarily read context, not write via tools.

4. **Gemini 2.5 Flash-Lite Exact Model ID**
   - What we know: models.py has `gemini-3.1-flash-lite-preview` but the additional_context specifies Gemini 2.5 Flash-Lite
   - What's unclear: Whether `gemini-2.5-flash-lite` is the correct model ID or if it requires a different suffix
   - Recommendation: Verify via `client.models.list()` at implementation time. Fall back to Flash if Flash-Lite is unavailable.

## Sources

### Primary (HIGH confidence)
- [Google Gemini API Context Caching docs](https://ai.google.dev/gemini-api/docs/caching) -- explicit caching API, TTL, minimum token requirements
- [Google Gemini API Token Counting docs](https://ai.google.dev/gemini-api/docs/tokens) -- usage_metadata fields: prompt_token_count, cached_content_token_count, thoughts_token_count
- [Google Gemini API Thinking docs](https://ai.google.dev/gemini-api/docs/thinking) -- thinking_budget configuration for Flash 2.5
- [Google Developers Blog: Implicit Caching](https://developers.googleblog.com/en/gemini-2-5-models-now-support-implicit-caching/) -- automatic 75-90% savings on prefix matches
- [Google Gemini Batch API docs](https://ai.google.dev/gemini-api/docs/batch-api) -- 50% discount for async processing

### Secondary (MEDIUM confidence)
- [Codebase: promaia/agents/executor.py] -- current Claude SDK execution path, cost estimation, context loading
- [Codebase: promaia/ai/models.py] -- model registry with exact model IDs
- [Codebase: promaia/ai/nl_orchestrator.py] -- existing google.genai client usage pattern
- [Codebase: promaia/brain/schema.sql] -- brain schema pattern for new agent_costs table

### Tertiary (LOW confidence)
- [WebSearch: Gemini model routing patterns] -- community patterns for task-based routing; verified with official docs
- Gemini 2.5 Flash-Lite exact model ID -- needs runtime verification

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- google-genai already in codebase, API docs verified
- Architecture: HIGH -- patterns derived from official Gemini docs and existing codebase structure
- Pitfalls: HIGH -- verified with official docs (minimum cache tokens, thinking tokens billing, temperature defaults)
- Cost calculations: MEDIUM -- pricing from additional_context (March 2026 rates), needs verification against live billing
- Model routing: HIGH -- mapping is straightforward given decided model assignments

**Research date:** 2026-03-06
**Valid until:** 2026-04-06 (Gemini API is stable; pricing may change)
