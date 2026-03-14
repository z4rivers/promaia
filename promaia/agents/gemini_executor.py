"""
Gemini Executor - Makes Gemini API calls with cost tracking and fallback chain.

Wraps the google.genai client with:
- Per-call cost computation and logging via CostTracker
- Automatic fallback to next-tier model on API errors (ROUTE-02)
- Thinking budget support for models that support it
- Usage metadata extraction (input, output, cached, thinking tokens)

Follows the same synchronous call pattern as nl_orchestrator.py.
"""

import logging
import os
from datetime import datetime, timezone
from typing import Optional

from google import genai
from google.genai import types

from promaia.agents.model_router import ModelRouter, ModelConfig, MODELS
from promaia.agents.cost_tracker import CostTracker, CostRecord

logger = logging.getLogger(__name__)

# Reverse lookup: model_id -> model_key for fallback chain navigation
_MODEL_ID_TO_KEY: dict[str, str] = {
    cfg.model_id: key for key, cfg in MODELS.items()
}


class GeminiExecutor:
    """Executes Gemini API calls with cost tracking and fallback.

    Usage:
        executor = GeminiExecutor(cost_tracker, router)
        result = await executor.generate(model_config, system_instruction, contents, ...)
        result = await executor.generate_with_fallback(model_config, ...)
    """

    def __init__(self, cost_tracker: CostTracker, router: ModelRouter):
        """Initialize with shared cost tracker and model router.

        Args:
            cost_tracker: CostTracker instance for logging API call costs.
            router: ModelRouter instance for fallback model lookup.
        """
        self.cost_tracker = cost_tracker
        self.router = router
        self.client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))

    async def generate(
        self,
        model_config: ModelConfig,
        system_instruction: str,
        contents: str,
        execution_id: int,
        agent_name: str,
        task_type: str = "synthesize",
        thinking_budget: Optional[int] = None,
    ) -> dict:
        """Make a single Gemini API call with cost tracking.

        Args:
            model_config: ModelConfig with model_id, pricing, and temperature.
            system_instruction: System-level instruction for the model.
            contents: User message / prompt contents.
            execution_id: Execution ID for cost record linkage.
            agent_name: Name of the calling agent.
            task_type: Task type label for cost records (default "synthesize").
            thinking_budget: Optional thinking token budget. Capped by
                model_config.max_thinking_budget. Ignored if model has no
                thinking support.

        Returns:
            Dict with keys: content, input_tokens, output_tokens,
            cached_tokens, thinking_tokens, cost_usd, model.
        """
        # Build generation config
        config_kwargs: dict = {
            "system_instruction": system_instruction,
            "temperature": model_config.temperature,
        }

        # Add thinking config if the model supports it and budget is requested
        if thinking_budget and model_config.max_thinking_budget > 0:
            effective_budget = min(thinking_budget, model_config.max_thinking_budget)
            config_kwargs["thinking_config"] = types.ThinkingConfig(
                thinking_budget=effective_budget,
            )

        config = types.GenerateContentConfig(**config_kwargs)

        # Call Gemini API (synchronous, matching nl_orchestrator.py pattern)
        response = self.client.models.generate_content(
            model=model_config.model_id,
            contents=contents,
            config=config,
        )

        # Extract usage metadata
        usage = response.usage_metadata
        input_tokens = usage.prompt_token_count or 0
        output_tokens = usage.candidates_token_count or 0
        cached_tokens = getattr(usage, "cached_content_token_count", 0) or 0
        thinking_tokens = getattr(usage, "thoughts_token_count", 0) or 0

        # Compute cost
        usage_dict = {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cached_tokens": cached_tokens,
            "thinking_tokens": thinking_tokens,
        }
        cost_usd = self.cost_tracker.compute_cost(model_config, usage_dict)

        # Log cost to agent_costs
        record = CostRecord(
            agent_name=agent_name,
            model_id=model_config.model_id,
            task_type=task_type,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cached_tokens=cached_tokens,
            thinking_tokens=thinking_tokens,
            cost_usd=cost_usd,
            execution_id=execution_id,
            created_at=datetime.now(timezone.utc),
        )
        self.cost_tracker.log_call(record)

        logger.info(
            f"Gemini call: {model_config.model_id} | "
            f"in={input_tokens} out={output_tokens} cached={cached_tokens} "
            f"think={thinking_tokens} | ${cost_usd:.6f}"
        )

        return {
            "content": response.text,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cached_tokens": cached_tokens,
            "thinking_tokens": thinking_tokens,
            "cost_usd": cost_usd,
            "model": model_config.model_id,
        }

    async def generate_with_fallback(
        self,
        model_config: ModelConfig,
        system_instruction: str,
        contents: str,
        execution_id: int,
        agent_name: str,
        task_type: str = "synthesize",
        thinking_budget: Optional[int] = None,
        fallback_enabled: bool = True,
    ) -> dict:
        """Make a Gemini API call with automatic fallback on failure (ROUTE-02).

        On API error (rate limit, server error, etc.), falls back to the
        next-tier model via ModelRouter.get_fallback_model(). If no fallback
        is available or fallback is disabled, the exception is re-raised.

        Args:
            model_config: Primary ModelConfig to try first.
            system_instruction: System-level instruction for the model.
            contents: User message / prompt contents.
            execution_id: Execution ID for cost record linkage.
            agent_name: Name of the calling agent.
            task_type: Task type label for cost records.
            thinking_budget: Optional thinking token budget.
            fallback_enabled: Whether to attempt fallback (default True).

        Returns:
            Dict with keys: content, input_tokens, output_tokens,
            cached_tokens, thinking_tokens, cost_usd, model.

        Raises:
            Exception: If primary call fails and no fallback is available.
        """
        try:
            return await self.generate(
                model_config=model_config,
                system_instruction=system_instruction,
                contents=contents,
                execution_id=execution_id,
                agent_name=agent_name,
                task_type=task_type,
                thinking_budget=thinking_budget,
            )
        except Exception as primary_error:
            if not fallback_enabled:
                raise

            # Resolve current model key for fallback lookup
            model_key = _MODEL_ID_TO_KEY.get(model_config.model_id)
            if model_key is None:
                logger.error(
                    f"No model key found for {model_config.model_id}, cannot fallback"
                )
                raise

            fallback_config = self.router.get_fallback_model(model_key)
            if fallback_config is None:
                logger.error(
                    f"No fallback available for {model_config.display_name} "
                    f"({model_key}), re-raising error"
                )
                raise

            logger.warning(
                f"Falling back from {model_config.display_name} to "
                f"{fallback_config.display_name}: {primary_error}"
            )

            # Retry with fallback model (no further fallback to prevent cascade)
            return await self.generate(
                model_config=fallback_config,
                system_instruction=system_instruction,
                contents=contents,
                execution_id=execution_id,
                agent_name=agent_name,
                task_type=task_type,
                thinking_budget=thinking_budget,
            )
