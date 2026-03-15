import logging
import uuid
import json
from datetime import datetime, timezone

from apscheduler.schedulers.background import BackgroundScheduler
from promaia.storage.db_factory import get_db
from promaia.brain import engine

logger = logging.getLogger(__name__)

# Global scheduler instance
_scheduler = None


def _write_scheduler_heartbeat():
    """Write a scheduler_heartbeat event so the dashboard shows 'online'."""
    try:
        db = get_db()
        db.execute(
            """
            INSERT INTO events (type, payload, source, created_at)
            VALUES ('scheduler_heartbeat', ?, 'heartbeat', datetime('now'))
            """,
            (json.dumps({"source": "web_server"}),),
        )
    except Exception as e:
        logger.warning(f"Failed to write scheduler heartbeat: {e}")


def _run_subconscious_cycle():
    """Execute the background heartbeat tasks."""
    logger.info("Running Subconscious heartbeat cycle...")
    db = get_db()
    cycle_id = str(uuid.uuid4())

    # Write scheduler_heartbeat so dashboard indicator stays green
    _write_scheduler_heartbeat()

    try:
        # 1. Budget check
        # We'll use the CostTracker since it tracks actual agent costs
        from promaia.agents.cost_tracker import CostTracker
        tracker = CostTracker()
        today_spend = tracker.get_daily_spend()

        # Log the budget check
        db.execute(
            """
            INSERT INTO events (type, payload, source, session_id, created_at)
            VALUES ('daily_budget_check', ?, 'heartbeat', ?, datetime('now'))
            """,
            (json.dumps({"today_spend": today_spend}), cycle_id),
        )

        # 2. Check for stale domains
        stale_domains = []
        rows = db.fetch_all(
            """
            SELECT d.name, c.last_updated, c.stale_threshold_days
            FROM contexts c
            JOIN domains d ON d.id = c.domain_id
            WHERE julianday('now') - julianday(c.last_updated) > c.stale_threshold_days
            """
        )
        if rows:
            stale_domains = [r["name"] for r in rows]

        db.execute(
            """
            INSERT INTO events (type, payload, source, session_id, created_at)
            VALUES ('domain_staleness_check', ?, 'heartbeat', ?, datetime('now'))
            """,
            (json.dumps({
                "status": "stale_found" if stale_domains else "ok",
                "stale_domains": stale_domains
            }), cycle_id)
        )

        # 3. Suggest next (mostly to exercise the logic and log it)
        domain_rows = db.fetch_all(
            """
            SELECT d.name, c.directive, c.current_state, c.last_updated,
                   c.priority, c.stale_threshold_days
            FROM contexts c
            JOIN domains d ON d.id = c.domain_id
            """
        )
        if domain_rows:
            suggestion = engine.suggest_next(domain_rows, energy=None, db=db)
            if suggestion:
                db.execute(
                    """
                    INSERT INTO events (type, payload, source, session_id, created_at)
                    VALUES ('suggest_next_eval', ?, 'heartbeat', ?, datetime('now'))
                    """,
                    (json.dumps({
                        "domain": suggestion.get("domain"),
                        "action": suggestion.get("action"),
                        "score": suggestion.get("score"),
                        "reason": suggestion.get("reason"),
                    }), cycle_id)
                )

    except Exception as e:
        logger.error(f"Error in Subconscious heartbeat cycle: {e}", exc_info=True)


def start_heartbeat(interval_minutes: int = 15):
    """Initialize and start the background scheduler."""
    global _scheduler
    if _scheduler is not None:
        logger.warning("Scheduler already running.")
        return

    _scheduler = BackgroundScheduler()
    _scheduler.add_job(
        _run_subconscious_cycle,
        'interval',
        minutes=interval_minutes,
        id='subconscious_heartbeat',
        replace_existing=True
    )
    _scheduler.start()
    logger.info(f"Subconscious heartbeat scheduler started. Interval: {interval_minutes} minutes.")

    # Write scheduler_heartbeat immediately so dashboard shows 'online' on first poll
    _write_scheduler_heartbeat()

    # Run full subconscious cycle in background
    _scheduler.add_job(_run_subconscious_cycle, 'date', run_date=datetime.now())


def stop_heartbeat():
    """Stop the background scheduler if it's running."""
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown()
        _scheduler = None
        logger.info("Subconscious heartbeat scheduler stopped.")


def is_heartbeat_running() -> bool:
    """Return True if the background scheduler is currently alive."""
    global _scheduler
    return _scheduler is not None and getattr(_scheduler, 'running', False)
