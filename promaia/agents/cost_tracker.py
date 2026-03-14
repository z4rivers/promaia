"""
Cost Tracker - Per-call cost logging and computation for agent API calls.

Logs every API call to brain.agent_costs with model, tokens, cached tokens,
thinking tokens, and dollar cost. Provides daily/run spend queries and
summary aggregation.

Uses model-aware pricing from ModelConfig (not hardcoded Claude rates).
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from promaia.storage.db_factory import get_db
from promaia.agents.model_router import ModelConfig

logger = logging.getLogger(__name__)


@dataclass
class CostRecord:
    """A single API call cost record for brain.agent_costs."""
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
    """Tracks and computes costs for agent API calls.

    On initialization, ensures the brain.agent_costs table exists.
    Follows the same connection pattern as ExecutionTracker.

    Usage:
        tracker = CostTracker()
        cost = tracker.compute_cost(model_config, usage_dict)
        tracker.log_call(cost_record)
        today = tracker.get_daily_spend()
    """

    def __init__(self):
        self._ensure_table()

    def _ensure_table(self):
        """Create brain.agent_costs table and indexes if they don't exist."""
        try:
            db = get_db()

            db.execute("""
                CREATE TABLE IF NOT EXISTS brain_agent_costs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    execution_id INTEGER,
                    agent_name TEXT NOT NULL,
                    model_id TEXT NOT NULL,
                    task_type TEXT,
                    input_tokens INTEGER DEFAULT 0,
                    output_tokens INTEGER DEFAULT 0,
                    cached_tokens INTEGER DEFAULT 0,
                    thinking_tokens INTEGER DEFAULT 0,
                    cost_usd REAL NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)

            db.execute("""
                CREATE INDEX IF NOT EXISTS idx_agent_costs_agent
                ON brain_agent_costs (agent_name, created_at DESC)
            """)

            db.execute("""
                CREATE INDEX IF NOT EXISTS idx_agent_costs_date
                ON brain_agent_costs (created_at DESC)
            """)

            db.execute("""
                CREATE INDEX IF NOT EXISTS idx_agent_costs_execution
                ON brain_agent_costs (execution_id)
            """)
            logger.info("brain.agent_costs table initialized")

        except Exception as e:
            logger.error(f"Failed to initialize brain.agent_costs table: {e}")
            raise

    def log_call(self, record: CostRecord) -> None:
        """Insert a cost record into brain_agent_costs.

        Args:
            record: CostRecord with all fields populated.
        """
        try:
            db = get_db()
            db.execute("""
                INSERT INTO brain_agent_costs
                (agent_name, model_id, task_type, input_tokens, output_tokens,
                 cached_tokens, thinking_tokens, cost_usd, execution_id, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                record.agent_name,
                record.model_id,
                record.task_type,
                record.input_tokens,
                record.output_tokens,
                record.cached_tokens,
                record.thinking_tokens,
                record.cost_usd,
                record.execution_id,
                record.created_at.isoformat() if record.created_at else None,
            ))
            logger.debug(
                f"Logged cost: {record.agent_name} / {record.model_id} "
                f"= ${record.cost_usd:.6f}"
            )
        except Exception as e:
            logger.error(f"Failed to log cost record: {e}")
            raise

    @staticmethod
    def compute_cost(model_config: ModelConfig, usage: dict) -> float:
        """Compute dollar cost from model pricing and token usage.

        Thinking tokens are billed separately at thinking_price_per_m
        (per Gemini API: usage_metadata.thoughts_token_count).

        Args:
            model_config: ModelConfig with pricing fields.
            usage: Dict with keys: input_tokens, output_tokens,
                   cached_tokens, thinking_tokens.

        Returns:
            Total cost in USD as a float.
        """
        input_tokens = usage.get("input_tokens", 0)
        output_tokens = usage.get("output_tokens", 0)
        cached_tokens = usage.get("cached_tokens", 0)
        thinking_tokens = usage.get("thinking_tokens", 0)

        non_cached_input = input_tokens - cached_tokens
        input_cost = non_cached_input * model_config.input_price_per_m / 1_000_000
        cached_cost = (
            cached_tokens
            * model_config.input_price_per_m
            * model_config.cached_input_discount
            / 1_000_000
        )
        output_cost = output_tokens * model_config.output_price_per_m / 1_000_000
        thinking_cost = thinking_tokens * model_config.thinking_price_per_m / 1_000_000

        return input_cost + cached_cost + output_cost + thinking_cost

    def get_daily_spend(self) -> float:
        """Get total spend for the current day (UTC).

        Returns:
            Total cost in USD for today.
        """
        try:
            db = get_db()
            row = db.fetch_one("""
                SELECT COALESCE(SUM(cost_usd), 0) as total
                FROM brain_agent_costs
                WHERE created_at >= date('now')
            """)
            return float(row["total"]) if row else 0.0
        except Exception as e:
            logger.error(f"Failed to get daily spend: {e}")
            return 0.0

    def get_run_spend(self, execution_id: int) -> float:
        """Get total spend for a specific execution run.

        Args:
            execution_id: The execution ID from agent_executions.

        Returns:
            Total cost in USD for the run.
        """
        try:
            db = get_db()
            row = db.fetch_one("""
                SELECT COALESCE(SUM(cost_usd), 0) as total
                FROM brain_agent_costs
                WHERE execution_id = ?
            """, (execution_id,))
            return float(row["total"]) if row else 0.0
        except Exception as e:
            logger.error(f"Failed to get run spend for execution {execution_id}: {e}")
            return 0.0

    def get_daily_summary(self, days: int = 7) -> list[dict]:
        """Get cost summary grouped by date and agent.

        Args:
            days: Number of days to look back (default 7).

        Returns:
            List of dicts with keys: date, agent_name, calls,
            input_tokens, output_tokens, cached_tokens, cost.
        """
        try:
            db = get_db()
            rows = db.fetch_all(f"""
                SELECT
                    DATE(created_at) as day,
                    agent_name,
                    COUNT(*) as calls,
                    SUM(input_tokens) as input_tokens,
                    SUM(output_tokens) as output_tokens,
                    SUM(cached_tokens) as cached_tokens,
                    SUM(cost_usd) as cost
                FROM brain_agent_costs
                WHERE created_at >= date('now', '-{days} days')
                GROUP BY DATE(created_at), agent_name
                ORDER BY day DESC, cost DESC
            """)
            return rows

        except Exception as e:
            logger.error(f"Failed to get daily summary: {e}")
            return []
