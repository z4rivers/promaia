"""
Budget Guard - Per-run and daily budget enforcement for agent execution.

BudgetGuard checks spending limits before and during agent runs:
- Per-run cap ($0.50 default): kills a run that spends too much (COST-02)
- Daily cap ($2.00 default): skips non-critical runs when daily spend is high (COST-03)

RunawayDetector catches stuck agents via:
- Iteration count limits
- Cumulative cost limits
- Repetitive output detection (word-set overlap)
"""

import logging
from typing import Optional

from promaia.agents.cost_tracker import CostTracker

logger = logging.getLogger(__name__)


class BudgetGuard:
    """Enforces per-run and daily budget caps for agent execution.

    Usage:
        guard = BudgetGuard(cost_tracker, per_run_cap=0.50, daily_cap=2.00)
        allowed, reason = guard.can_start_run("morning-briefing")
        ok, reason = guard.check_run_budget(execution_id)
    """

    def __init__(
        self,
        cost_tracker: CostTracker,
        per_run_cap: float = 0.50,
        daily_cap: float = 2.00,
    ):
        """Initialize with cost tracker and budget caps.

        Args:
            cost_tracker: CostTracker instance for spend queries.
            per_run_cap: Maximum spend per single agent run in USD.
            daily_cap: Maximum daily spend across all agents in USD.
        """
        self.cost_tracker = cost_tracker
        self.per_run_cap = per_run_cap
        self.daily_cap = daily_cap

    def can_start_run(
        self, agent_name: str, is_critical: bool = False
    ) -> tuple[bool, str]:
        """Check whether an agent run should be allowed to start.

        Critical agents always pass. Non-critical agents are blocked when
        daily spend exceeds the daily cap (COST-03).

        Args:
            agent_name: Name of the agent requesting to run.
            is_critical: If True, always allow regardless of budget.

        Returns:
            Tuple of (allowed, reason). reason is empty string when allowed.
        """
        if is_critical:
            return True, ""

        daily_spend = self.cost_tracker.get_daily_spend()
        if daily_spend >= self.daily_cap:
            reason = (
                f"Daily budget exceeded: ${daily_spend:.2f}/${self.daily_cap:.2f}"
            )
            logger.warning(f"Budget guard blocking '{agent_name}': {reason}")
            return False, reason

        return True, ""

    def check_run_budget(self, execution_id: int) -> tuple[bool, str]:
        """Check whether a running execution has exceeded its per-run cap.

        Call this after each API call within a run to enforce COST-02.

        Args:
            execution_id: The execution ID to check spend for.

        Returns:
            Tuple of (within_budget, reason). reason is empty when within budget.
        """
        run_spend = self.cost_tracker.get_run_spend(execution_id)
        if run_spend >= self.per_run_cap:
            reason = (
                f"Run budget exceeded: ${run_spend:.2f}/${self.per_run_cap:.2f}"
            )
            logger.warning(f"Budget guard killing execution {execution_id}: {reason}")
            return False, reason

        return True, ""


class RunawayDetector:
    """Detects stuck agents producing repetitive or excessive output.

    Tracks iteration count, cumulative cost, and output similarity across
    responses within a single run. Any trigger causes a kill recommendation.

    Usage:
        detector = RunawayDetector(max_iterations=5, max_cost=0.50)
        should_kill, reason = detector.check(response_text, cost)
    """

    def __init__(
        self,
        max_iterations: int = 5,
        max_cost: float = 0.50,
        similarity_threshold: float = 0.85,
    ):
        """Initialize with kill thresholds.

        Args:
            max_iterations: Max number of iterations before kill.
            max_cost: Max cumulative cost (USD) before kill.
            similarity_threshold: Word-set overlap ratio (0-1) above which
                last 3 responses are considered repetitive.
        """
        self.max_iterations = max_iterations
        self.max_cost = max_cost
        self.similarity_threshold = similarity_threshold
        self._responses: list[str] = []
        self._total_cost: float = 0.0
        self._iterations: int = 0

    def check(self, response_text: str, cost: float) -> tuple[bool, str]:
        """Check whether the agent should be killed.

        Call after each response within a run.

        Args:
            response_text: The agent's latest response text.
            cost: Cost of the latest API call in USD.

        Returns:
            Tuple of (should_kill, reason). reason is empty when safe.
        """
        self._iterations += 1
        self._total_cost += cost
        self._responses.append(response_text)

        # Check iteration limit
        if self._iterations > self.max_iterations:
            return True, (
                f"Iteration limit exceeded: {self._iterations}/{self.max_iterations}"
            )

        # Check cost limit
        if self._total_cost > self.max_cost:
            return True, (
                f"Cost limit exceeded: ${self._total_cost:.4f}/${self.max_cost:.2f}"
            )

        # Check repetitive output (need at least 3 responses)
        if len(self._responses) >= 3 and self._responses_similar(self._responses[-3:]):
            return True, (
                f"Repetitive output detected "
                f"(last 3 responses similarity > {self.similarity_threshold})"
            )

        return False, ""

    def _responses_similar(self, responses: list[str]) -> bool:
        """Check if responses are too similar via word-set overlap.

        Compares each pair among the given responses. All pairs must exceed
        the similarity threshold to trigger a kill.

        Args:
            responses: List of response texts to compare.

        Returns:
            True if all response pairs exceed the similarity threshold.
        """
        word_sets = [set(r.lower().split()) for r in responses]

        for i in range(len(word_sets)):
            for j in range(i + 1, len(word_sets)):
                set_a, set_b = word_sets[i], word_sets[j]
                if not set_a or not set_b:
                    return False
                union = set_a | set_b
                intersection = set_a & set_b
                overlap = len(intersection) / len(union) if union else 0.0
                if overlap < self.similarity_threshold:
                    return False

        return True

    def reset(self) -> None:
        """Clear state for a new run."""
        self._responses.clear()
        self._total_cost = 0.0
        self._iterations = 0
