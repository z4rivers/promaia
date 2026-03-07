"""
Model Router - Maps task types and agent names to specific Gemini models.

Provides model selection, pricing metadata, and fallback chains for all
agent API calls. Replaces hardcoded Claude Sonnet pricing with accurate
Gemini model-specific pricing.

Model IDs sourced from promaia/ai/models.py GOOGLE_MODELS registry.
"""

from enum import Enum
from dataclasses import dataclass
from typing import Optional


class TaskType(Enum):
    """Types of tasks that agents perform, each routed to an optimal model."""
    CLASSIFY = "classify"       # Email classification, urgency detection
    EXTRACT = "extract"         # Data extraction, formatting
    EMBED = "embed"             # Embedding generation
    SYNTHESIZE = "synthesize"   # Briefing, digest, triage output
    REASON = "reason"           # Complex analysis, planning
    CREATE = "create"           # Content generation
    HEARTBEAT = "heartbeat"     # Health checks, status pings


@dataclass(frozen=True)
class ModelConfig:
    """Configuration and pricing metadata for a specific model.

    Pricing figures are approximate and should be verified against the
    current Google AI pricing page (https://ai.google.dev/pricing).
    """
    model_id: str
    display_name: str
    input_price_per_m: float       # $ per 1M input tokens
    output_price_per_m: float      # $ per 1M output tokens
    thinking_price_per_m: float    # $ per 1M thinking tokens (billed separately)
    cached_input_discount: float   # Multiplier, e.g. 0.1 = 90% off cached input
    min_cache_tokens: int          # Minimum tokens for explicit caching
    max_thinking_budget: int       # 0 = disable thinking for this model
    temperature: float = 1.0       # Default 1.0 per user decision (Gemini 3 best at 1.0)


# ---------------------------------------------------------------------------
# Model registry
# Pricing approximate as of March 2026. Verify against Google AI pricing page.
# Model IDs match promaia/ai/models.py GOOGLE_MODELS.
# ---------------------------------------------------------------------------
MODELS: dict[str, ModelConfig] = {
    "flash": ModelConfig(
        model_id="gemini-3-flash-preview",
        display_name="Gemini 3 Flash",
        input_price_per_m=0.15,
        output_price_per_m=0.60,
        thinking_price_per_m=0.60,     # Thinking billed as output
        cached_input_discount=0.1,     # 90% off
        min_cache_tokens=1024,
        max_thinking_budget=8192,
        temperature=1.0,
    ),
    "flash-lite": ModelConfig(
        model_id="gemini-3.1-flash-lite-preview",
        display_name="Gemini 3.1 Flash-Lite",
        input_price_per_m=0.04,
        output_price_per_m=0.15,
        thinking_price_per_m=0.00,     # No thinking support
        cached_input_discount=0.1,
        min_cache_tokens=1024,
        max_thinking_budget=0,         # Per user decision: no thinking for Flash-Lite
        temperature=1.0,
    ),
    "pro": ModelConfig(
        model_id="gemini-3.1-pro-preview",
        display_name="Gemini 3.1 Pro",
        input_price_per_m=1.25,
        output_price_per_m=10.00,
        thinking_price_per_m=10.00,    # Thinking billed as output
        cached_input_discount=0.1,
        min_cache_tokens=4096,
        max_thinking_budget=0,         # Disabled by default; enable per-task if needed
        temperature=1.0,
    ),
    "embedding": ModelConfig(
        model_id="gemini-embedding-001",
        display_name="Gemini Embedding",
        input_price_per_m=0.00,
        output_price_per_m=0.00,
        thinking_price_per_m=0.00,
        cached_input_discount=0.0,     # No caching for embeddings
        min_cache_tokens=0,
        max_thinking_budget=0,
        temperature=0.0,
    ),
}


# ---------------------------------------------------------------------------
# Task type -> model key mapping
# ---------------------------------------------------------------------------
TASK_MODEL_MAP: dict[TaskType, str] = {
    TaskType.CLASSIFY:   "flash-lite",
    TaskType.EXTRACT:    "flash-lite",
    TaskType.EMBED:      "embedding",
    TaskType.SYNTHESIZE: "flash",
    TaskType.REASON:     "pro",
    TaskType.CREATE:     "flash",
    TaskType.HEARTBEAT:  "flash-lite",
}


# ---------------------------------------------------------------------------
# Agent name -> model key mapping (per user decision COST-04)
# All agents use Gemini 3 Flash for agent tasks.
# ---------------------------------------------------------------------------
AGENT_MODEL_MAP: dict[str, str] = {
    "morning-briefing": "flash",   # Gemini 3 Flash for synthesis
    "email-triage":     "flash",   # Gemini 3 Flash for agent tasks
    "evening-digest":   "flash",   # Gemini 3 Flash for agent tasks
}


# ---------------------------------------------------------------------------
# Fallback chain: model key -> next tier up
# ---------------------------------------------------------------------------
_FALLBACK_CHAIN: dict[str, str] = {
    "flash-lite": "flash",
    "flash":      "pro",
    # "pro" has no fallback -- it's the top tier
    # "embedding" has no fallback -- it's a separate model type
}


class ModelRouter:
    """Routes task types and agent names to appropriate Gemini models.

    Usage:
        router = ModelRouter()
        config = router.get_model(TaskType.SYNTHESIZE)
        agent_config = router.get_agent_model("morning-briefing")
        fallback = router.get_fallback_model("flash-lite")
    """

    def get_model(self, task_type: TaskType) -> ModelConfig:
        """Get the model configuration for a given task type.

        Args:
            task_type: The type of task to route.

        Returns:
            ModelConfig for the optimal model for this task type.

        Raises:
            KeyError: If task_type is not in TASK_MODEL_MAP.
        """
        model_key = TASK_MODEL_MAP[task_type]
        return MODELS[model_key]

    def get_agent_model(self, agent_name: str) -> ModelConfig:
        """Get the assigned model for a specific agent.

        Falls back to 'flash' if the agent name is not in the map.

        Args:
            agent_name: Name of the agent (e.g., 'morning-briefing').

        Returns:
            ModelConfig for the agent's assigned model.
        """
        model_key = AGENT_MODEL_MAP.get(agent_name, "flash")
        return MODELS[model_key]

    def get_fallback_model(self, model_key: str) -> Optional[ModelConfig]:
        """Get the next-tier-up model for fallback when primary fails.

        Fallback chain: flash-lite -> flash -> pro -> None

        Args:
            model_key: Current model key (e.g., 'flash-lite').

        Returns:
            ModelConfig for the fallback model, or None if no fallback exists.
        """
        fallback_key = _FALLBACK_CHAIN.get(model_key)
        if fallback_key is None:
            return None
        return MODELS[fallback_key]
