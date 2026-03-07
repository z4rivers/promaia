"""
Agent Scheduler - Runs scheduled agents at specified intervals using asyncio.

Supports two scheduling modes:
  - Time-of-day via agent.schedule (e.g., daily at 06:00 ET)
  - Fixed interval via agent.interval_minutes (legacy, e.g., every 480 min)
"""
import asyncio
import logging
import os
import signal
from datetime import datetime, timezone, timedelta, time
from typing import Dict, List, Optional, Set, Tuple
from pathlib import Path
from zoneinfo import ZoneInfo

from promaia.agents.agent_config import load_agents, AgentConfig
from promaia.agents.executor import AgentExecutor
from promaia.agents.budget_guard import BudgetGuard
from promaia.agents.cost_tracker import CostTracker
from promaia.events.emitter import emit_agent_events
from promaia.events.router import EventRouter

logger = logging.getLogger(__name__)

# User timezone for schedule calculations
_USER_TZ = ZoneInfo("America/New_York")

# Weekday name to weekday number (Monday=0 .. Sunday=6)
_WEEKDAY_MAP = {
    "Mon": 0, "Tue": 1, "Wed": 2, "Thu": 3,
    "Fri": 4, "Sat": 5, "Sun": 6,
}

# Agent-specific message prefixes for Telegram push
_PUSH_PREFIXES = {
    "morning-briefing": "Good morning. Here's your briefing:\n\n",
    "evening-digest": "Evening digest:\n\n",
}


def _next_run_time(schedule: List[Tuple[str, str]]) -> datetime:
    """Calculate the next scheduled run time from a schedule list.

    Each entry is (day_spec, time_str) where:
      - day_spec is "daily" or a weekday abbreviation ("Mon", "Tue", etc.)
      - time_str is "HH:MM" in user timezone (America/New_York)

    Returns the earliest upcoming datetime (timezone-aware in user TZ).
    """
    now = datetime.now(_USER_TZ)
    candidates: List[datetime] = []

    for day_spec, time_str in schedule:
        hour, minute = int(time_str.split(":")[0]), int(time_str.split(":")[1])
        target_time = time(hour, minute)

        if day_spec.lower() == "daily":
            # Today if not yet past, otherwise tomorrow
            candidate = now.replace(
                hour=hour, minute=minute, second=0, microsecond=0
            )
            if candidate <= now:
                candidate += timedelta(days=1)
            candidates.append(candidate)
        else:
            # Specific weekday
            target_weekday = _WEEKDAY_MAP.get(day_spec)
            if target_weekday is None:
                logger.warning(f"Unknown day_spec '{day_spec}', skipping")
                continue

            # Days until next occurrence of target weekday
            days_ahead = target_weekday - now.weekday()
            if days_ahead < 0:
                days_ahead += 7
            elif days_ahead == 0:
                # Same weekday -- check if time already passed
                candidate = now.replace(
                    hour=hour, minute=minute, second=0, microsecond=0
                )
                if candidate <= now:
                    days_ahead = 7

            candidate = now.replace(
                hour=hour, minute=minute, second=0, microsecond=0
            ) + timedelta(days=days_ahead)
            candidates.append(candidate)

    if not candidates:
        # Fallback: 24 hours from now (should not happen with valid config)
        logger.error("No valid schedule entries, falling back to 24h")
        return now + timedelta(hours=24)

    return min(candidates)


class AgentScheduler:
    """
    Schedules and runs agents at their configured intervals.

    Uses asyncio for lightweight concurrent execution without additional dependencies.
    """

    def __init__(self):
        """Initialize the scheduler."""
        self.running = False
        self.tasks: Dict[str, asyncio.Task] = {}
        self.shutdown_event = asyncio.Event()
        self.cost_tracker = CostTracker()
        self.budget_guard = BudgetGuard(self.cost_tracker)
        self.event_router = EventRouter()

    async def start(self):
        """
        Start the scheduler and run all enabled agents.

        This is the main entry point that:
        1. Loads all agent configurations
        2. Creates interval tasks for each enabled agent
        3. Runs until shutdown is requested
        """
        logger.info("🚀 Starting Agent Scheduler...")

        self.running = True

        # Load agents
        agents = load_agents()
        enabled_agents = [a for a in agents if a.enabled]

        if not enabled_agents:
            logger.warning("⚠️  No enabled agents found")
            return

        logger.info(f"📋 Found {len(enabled_agents)} enabled agents")

        # Create tasks for each agent
        for agent in enabled_agents:
            if agent.schedule:
                # Time-of-day scheduling (sleep-until)
                task = asyncio.create_task(self._run_scheduled_agent(agent))
                self.tasks[agent.name] = task
                schedule_desc = ", ".join(
                    f"{day} {t}" for day, t in agent.schedule
                )
                logger.info(
                    f"   ✓ Scheduled '{agent.name}' (time-of-day: {schedule_desc})"
                )
            else:
                # Legacy interval-based scheduling
                task = asyncio.create_task(self._run_agent_loop(agent))
                self.tasks[agent.name] = task
                logger.info(
                    f"   ✓ Scheduled '{agent.name}' (every {agent.interval_minutes} min)"
                )

        # Start lightweight email check loop (PUSH-06: sub-minute email detection)
        email_check_task = asyncio.create_task(self._email_check_loop())
        self.tasks["__email_check__"] = email_check_task
        logger.info("   Email check loop started (polling Gmail every 60s)")

        # Start event router (EVENT-02)
        router_task = asyncio.create_task(self.event_router.run())
        self.tasks["__event_router__"] = router_task
        logger.info("   Event router started (polling every 30s)")

        logger.info("✅ Scheduler started. Press Ctrl+C to stop.\n")

        # Wait for shutdown signal
        await self.shutdown_event.wait()

        # Cleanup
        await self._shutdown()

    async def _run_agent_loop(self, agent: AgentConfig):
        """
        Run an agent in a loop at its configured interval.

        Args:
            agent: The agent configuration
        """
        interval_seconds = agent.interval_minutes * 60

        logger.info(f"🔄 Starting loop for '{agent.name}'")

        while self.running:
            try:
                # Check daily budget before running (COST-03)
                allowed, reason = self.budget_guard.can_start_run(agent.name, is_critical=False)
                if not allowed:
                    logger.warning(f"Skipping '{agent.name}': {reason}")
                    # Wait for next interval instead of running
                    if self.running:
                        logger.info(f"⏳ '{agent.name}' sleeping for {agent.interval_minutes} minutes...")
                        try:
                            await asyncio.sleep(interval_seconds)
                        except asyncio.CancelledError:
                            break
                    continue

                # Run the agent
                logger.info(f"\n⏰ Triggering '{agent.name}' (interval: {agent.interval_minutes}m)")

                executor = AgentExecutor(agent)
                result = await executor.execute()

                if result['success']:
                    logger.info(f"✅ '{agent.name}' completed successfully")

                    if result.get('metrics'):
                        metrics = result['metrics']
                        logger.info(
                            f"   Metrics: {metrics.get('iterations_used', 0)} iterations, "
                            f"{metrics.get('tokens_used', 0):,} tokens, "
                            f"${metrics.get('cost_estimate', 0):.4f}"
                        )
                else:
                    logger.error(f"❌ '{agent.name}' failed: {result.get('error')}")

            except Exception as e:
                logger.error(f"❌ Error running '{agent.name}': {e}")

            # Wait for next interval
            if self.running:
                logger.info(f"⏳ '{agent.name}' sleeping for {agent.interval_minutes} minutes...")
                try:
                    await asyncio.sleep(interval_seconds)
                except asyncio.CancelledError:
                    logger.info(f"🛑 '{agent.name}' loop cancelled")
                    break

    async def _run_scheduled_agent(self, agent: AgentConfig):
        """Run an agent using time-of-day scheduling (sleep-until).

        Calculates the next run time from the agent's schedule, sleeps until
        then, executes, pushes output to Telegram, emits events, and loops.

        Args:
            agent: The agent configuration (must have schedule set).
        """
        logger.info(f"🕐 Starting scheduled loop for '{agent.name}'")

        while self.running:
            try:
                # Calculate next run time (recalculated each loop to prevent drift)
                next_run = _next_run_time(agent.schedule)
                now = datetime.now(_USER_TZ)
                sleep_seconds = (next_run - now).total_seconds()

                if sleep_seconds < 0:
                    sleep_seconds = 0

                logger.info(
                    f"⏳ '{agent.name}' next run at {next_run.strftime('%Y-%m-%d %H:%M %Z')} "
                    f"(sleeping {sleep_seconds / 3600:.1f}h)"
                )

                # Sleep until scheduled time
                try:
                    await asyncio.sleep(sleep_seconds)
                except asyncio.CancelledError:
                    logger.info(f"🛑 '{agent.name}' scheduled loop cancelled")
                    break

                if not self.running:
                    break

                # Check daily budget before running (COST-03)
                allowed, reason = self.budget_guard.can_start_run(
                    agent.name, is_critical=False
                )
                if not allowed:
                    logger.warning(f"Skipping '{agent.name}': {reason}")
                    # Sleep a short period before recalculating
                    try:
                        await asyncio.sleep(60)
                    except asyncio.CancelledError:
                        break
                    continue

                # Execute the agent
                logger.info(
                    f"\n⏰ Triggering '{agent.name}' "
                    f"(scheduled: {next_run.strftime('%H:%M %Z')})"
                )

                executor = AgentExecutor(agent)
                result = await executor.execute()

                if result["success"]:
                    logger.info(f"✅ '{agent.name}' completed successfully")

                    if result.get("metrics"):
                        metrics = result["metrics"]
                        logger.info(
                            f"   Metrics: {metrics.get('iterations_used', 0)} iterations, "
                            f"{metrics.get('tokens_used', 0):,} tokens, "
                            f"${metrics.get('cost_estimate', 0):.4f}"
                        )

                    # Push output directly to Telegram
                    output = result.get("output", "")
                    pushed = False
                    if output:
                        pushed = await self._push_agent_output(agent, output)

                    # Emit events with pre-routing if push succeeded
                    try:
                        execution_id = result.get("execution_id", 0)
                        event_count = emit_agent_events(
                            agent_name=agent.name,
                            output=output,
                            execution_id=execution_id,
                            pushed_to_channel="telegram" if pushed else None,
                        )
                        if event_count > 0:
                            logger.info(
                                f"Emitted {event_count} events for '{agent.name}'"
                                + (" (pre-routed)" if pushed else "")
                            )
                    except Exception as e:
                        logger.warning(f"Event emission failed (non-fatal): {e}")
                else:
                    logger.error(
                        f"❌ '{agent.name}' failed: {result.get('error')}"
                    )

            except asyncio.CancelledError:
                logger.info(f"🛑 '{agent.name}' scheduled loop cancelled")
                break
            except Exception as e:
                logger.error(f"❌ Error running '{agent.name}': {e}")
                # Brief pause before retrying the loop
                try:
                    await asyncio.sleep(60)
                except asyncio.CancelledError:
                    break

    async def _push_agent_output(self, agent: AgentConfig, output: str) -> bool:
        """Push agent output directly to Telegram.

        Bypasses the event router and rate limiter for immediate delivery
        of scheduled agent output. Uses send_long_message for proper
        splitting at the 4096-char Telegram limit.

        Args:
            agent: The agent configuration.
            output: Raw text output from the agent run.

        Returns:
            True on success, False on failure.
        """
        bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
        whitelist = os.environ.get("TELEGRAM_WHITELIST")

        if not bot_token or not whitelist:
            logger.warning(
                f"Telegram push skipped for '{agent.name}': "
                "TELEGRAM_BOT_TOKEN or TELEGRAM_WHITELIST not set"
            )
            return False

        try:
            chat_id = int(whitelist.split(",")[0].strip())
        except (ValueError, IndexError):
            logger.error(f"Invalid TELEGRAM_WHITELIST format: {whitelist}")
            return False

        # Add agent-specific prefix
        prefix = _PUSH_PREFIXES.get(agent.name, "")
        message_text = prefix + output

        try:
            from aiogram import Bot
            from promaia.telegram.formatting import _split_message

            bot = Bot(token=bot_token)
            try:
                chunks = _split_message(message_text)
                for chunk in chunks:
                    await bot.send_message(chat_id, chunk)

                logger.info(
                    f"📱 Pushed '{agent.name}' output to Telegram "
                    f"({len(chunks)} message(s), chat {chat_id})"
                )
                return True
            finally:
                await bot.session.close()

        except Exception as e:
            logger.error(
                f"Telegram push failed for '{agent.name}': {e}",
                exc_info=True,
            )
            return False

    async def _email_check_loop(self):
        """Lightweight Gmail API poll for new unread emails (PUSH-06).

        Checks every 60 seconds for new unread mail. When detected, triggers
        the email-triage agent on-demand. This achieves sub-2-minute email
        detection at $0/day API cost (Gmail API calls are free within quota).

        The full email-triage agent only runs when new mail exists, so LLM
        cost is proportional to actual email volume, not polling frequency.
        """
        from promaia.brain.channels.gmail_read import _get_gmail_service, discover_accounts
        import time as _time

        # Discover Gmail accounts
        accounts = discover_accounts()
        if not accounts:
            logger.warning("No Gmail accounts found -- email check loop disabled")
            return

        # Use first account (primary)
        account_label, token_path = next(iter(accounts.items()))
        logger.info(f"Email check loop using account: {account_label}")

        # Track last check timestamp (epoch seconds)
        # Capture timestamp BEFORE the API call to prevent coverage gaps
        last_check_epoch = int(_time.time())

        while self.running:
            try:
                await asyncio.sleep(60)
            except asyncio.CancelledError:
                break

            try:
                # Capture timestamp at START of iteration (before API call)
                check_start_epoch = int(_time.time())

                # Build Gmail service (handles token refresh)
                service = _get_gmail_service(token_path)

                # Lightweight check: list unread messages since last check
                # Gmail query uses epoch seconds for after: filter
                query = f"is:unread after:{last_check_epoch}"
                response = service.users().messages().list(
                    userId="me", q=query, maxResults=1
                ).execute()

                new_count = response.get("resultSizeEstimate", 0)

                if new_count > 0:
                    logger.info(f"New unread email detected ({new_count} new) -- syncing and triggering email-triage")

                    # Sync new emails into database before triage
                    try:
                        from promaia.brain.gmail_ingest import run_gmail_ingest
                        sync_result = run_gmail_ingest(account=account_label, days_back=1, max_emails=50)
                        logger.info(f"Gmail sync: {sync_result.get('total_synced', 0)} new messages ingested")
                    except Exception as e:
                        logger.warning(f"Gmail sync failed (non-fatal): {e}")

                    # Find the email-triage agent config
                    agents = load_agents()
                    triage_agent = next((a for a in agents if a.name == "email-triage"), None)

                    if triage_agent:
                        # Check budget before running
                        allowed, reason = self.budget_guard.can_start_run("email-triage", is_critical=False)
                        if allowed:
                            executor = AgentExecutor(triage_agent)
                            result = await executor.execute()
                            if result.get("success"):
                                logger.info("Email-triage completed (triggered by new mail)")
                                # Push triage results to Telegram so Zack sees them
                                output = result.get("output", "")
                                if output:
                                    await self._push_agent_output(triage_agent, output)
                            else:
                                logger.warning(f"Email-triage failed: {result.get('error')}")
                        else:
                            logger.warning(f"Skipping on-demand email-triage: {reason}")

                # Update last check time (captured at start of iteration)
                last_check_epoch = check_start_epoch

            except Exception as e:
                logger.warning(f"Email check loop error (non-fatal): {e}")
                # Continue polling -- transient errors should not kill the loop

    async def _shutdown(self):
        """Gracefully shutdown all running tasks."""
        logger.info("\n🛑 Shutting down scheduler...")

        self.running = False

        # Cancel all tasks
        for name, task in self.tasks.items():
            logger.info(f"   Cancelling '{name}'...")
            task.cancel()

        # Wait for all tasks to complete
        if self.tasks:
            await asyncio.gather(*self.tasks.values(), return_exceptions=True)

        logger.info("✅ Scheduler stopped")

    def stop(self):
        """Signal the scheduler to stop."""
        logger.info("📢 Stop signal received")
        self.shutdown_event.set()


# Global scheduler instance for signal handling
_scheduler: Optional[AgentScheduler] = None


def _handle_shutdown_signal(signum, frame):
    """Handle shutdown signals (SIGINT, SIGTERM)."""
    if _scheduler:
        _scheduler.stop()


async def run_scheduler():
    """
    Run the agent scheduler.

    This is the main entry point for the scheduler daemon.
    """
    global _scheduler

    # Setup signal handlers
    signal.signal(signal.SIGINT, _handle_shutdown_signal)
    signal.signal(signal.SIGTERM, _handle_shutdown_signal)

    _scheduler = AgentScheduler()

    try:
        await _scheduler.start()
    except KeyboardInterrupt:
        logger.info("\n⚠️  Keyboard interrupt received")
        _scheduler.stop()
        await _scheduler._shutdown()


def run_scheduler_sync():
    """
    Synchronous entry point for the scheduler.

    Use this from CLI commands.
    """
    asyncio.run(run_scheduler())


# PID file management for daemon control
PID_FILE = Path.home() / ".promaia" / "scheduler.pid"


def write_pid_file():
    """Write the current process ID to the PID file."""
    import os

    PID_FILE.parent.mkdir(parents=True, exist_ok=True)

    with open(PID_FILE, 'w') as f:
        f.write(str(os.getpid()))

    logger.info(f"📝 PID file written: {PID_FILE}")


def read_pid_file() -> Optional[int]:
    """Read the process ID from the PID file."""
    if not PID_FILE.exists():
        return None

    try:
        with open(PID_FILE, 'r') as f:
            return int(f.read().strip())
    except Exception as e:
        logger.error(f"Error reading PID file: {e}")
        return None


def remove_pid_file():
    """Remove the PID file."""
    if PID_FILE.exists():
        PID_FILE.unlink()
        logger.info(f"🗑️  PID file removed: {PID_FILE}")


def is_scheduler_running() -> bool:
    """Check if the scheduler is currently running."""
    import os

    pid = read_pid_file()

    if not pid:
        return False

    # Check if process exists
    try:
        os.kill(pid, 0)  # Doesn't actually kill, just checks if process exists
        return True
    except OSError:
        # Process doesn't exist, clean up stale PID file
        remove_pid_file()
        return False


def stop_scheduler():
    """Stop the running scheduler daemon."""
    import os

    pid = read_pid_file()

    if not pid:
        logger.info("No scheduler is running")
        return False

    try:
        # Send SIGTERM to gracefully stop
        os.kill(pid, signal.SIGTERM)
        logger.info(f"✅ Sent stop signal to scheduler (PID: {pid})")

        # Wait a bit for graceful shutdown
        import time
        time.sleep(2)

        # Check if still running
        try:
            os.kill(pid, 0)
            logger.warning(f"⚠️  Scheduler still running, sending SIGKILL...")
            os.kill(pid, signal.SIGKILL)
        except OSError:
            # Process stopped
            pass

        remove_pid_file()
        return True

    except ProcessLookupError:
        logger.info("Scheduler process not found (already stopped)")
        remove_pid_file()
        return False
    except Exception as e:
        logger.error(f"Error stopping scheduler: {e}")
        return False


async def run_scheduler_daemon():
    """
    Run the scheduler as a background daemon.

    This handles PID file management and proper cleanup.
    """
    # Check if already running
    if is_scheduler_running():
        logger.error("❌ Scheduler is already running")
        return

    # Write PID file
    write_pid_file()

    try:
        await run_scheduler()
    finally:
        # Cleanup PID file on exit
        remove_pid_file()


def run_scheduler_daemon_sync():
    """
    Synchronous entry point for the scheduler daemon.

    Use this from CLI commands.
    """
    asyncio.run(run_scheduler_daemon())


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    logging.getLogger("googleapiclient.discovery_cache").setLevel(logging.ERROR)
    run_scheduler_daemon_sync()
