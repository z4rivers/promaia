"""
Event emitter -- converts agent output into routable events.

Maps each agent's output to one or more brain.events rows with
the appropriate urgency level. Called by the executor after every
successful agent run (07-01).

Agent-to-urgency mapping (deterministic by agent name):
  morning-briefing -> digest (single event)
  evening-digest   -> digest (single event)
  email-triage     -> interrupt per "Action Needed" item + archive for rest
"""
import json
import logging
from typing import Optional

from promaia.storage.postgres_db import get_postgres_db

logger = logging.getLogger(__name__)

# Maximum summary length stored in payload
_MAX_SUMMARY_LEN = 500


def _parse_action_needed(output: str) -> list[str]:
    """Extract individual items from the **Action Needed** section.

    Looks for lines starting with ``- `` after the ``**Action Needed**``
    header and before the next ``**`` header (or end of string).
    """
    items: list[str] = []
    in_section = False

    for line in output.splitlines():
        stripped = line.strip()

        if "**Action Needed**" in stripped:
            in_section = True
            continue

        if in_section:
            # Another section header ends the Action Needed block
            if stripped.startswith("**") and stripped.endswith("**"):
                break
            # Capture bullet items
            if stripped.startswith("- "):
                items.append(stripped[2:].strip())

    return items


def emit_agent_events(
    agent_name: str,
    output: str,
    execution_id: int,
) -> int:
    """Convert agent output into routable brain.events rows.

    Args:
        agent_name: Name of the agent (e.g. ``morning-briefing``).
        output: Raw text output from the agent run.
        execution_id: Execution ID for traceability.

    Returns:
        Number of events inserted.
    """
    try:
        db = get_postgres_db()
        count = 0

        if agent_name == "morning-briefing":
            _insert_event(
                db,
                event_type="agent_briefing",
                source=agent_name,
                urgency="digest",
                agent_name=agent_name,
                execution_id=execution_id,
                summary=output[:_MAX_SUMMARY_LEN],
            )
            count = 1

        elif agent_name == "evening-digest":
            _insert_event(
                db,
                event_type="agent_digest",
                source=agent_name,
                urgency="digest",
                agent_name=agent_name,
                execution_id=execution_id,
                summary=output[:_MAX_SUMMARY_LEN],
            )
            count = 1

        elif agent_name == "email-triage":
            action_items = _parse_action_needed(output)

            # Each action-needed item becomes an interrupt event
            for item_text in action_items:
                _insert_event(
                    db,
                    event_type="email_action_needed",
                    source=agent_name,
                    urgency="interrupt",
                    agent_name=agent_name,
                    execution_id=execution_id,
                    summary=item_text[:_MAX_SUMMARY_LEN],
                )
                count += 1

            # Everything else becomes a single archive event
            _insert_event(
                db,
                event_type="email_triage_summary",
                source=agent_name,
                urgency="archive",
                agent_name=agent_name,
                execution_id=execution_id,
                summary=output[:_MAX_SUMMARY_LEN],
            )
            count += 1

        else:
            # Unknown agent -- emit a single digest event as safe default
            _insert_event(
                db,
                event_type="agent_output",
                source=agent_name,
                urgency="digest",
                agent_name=agent_name,
                execution_id=execution_id,
                summary=output[:_MAX_SUMMARY_LEN],
            )
            count = 1

        return count

    except Exception as e:
        logger.warning(f"Event emission failed (non-fatal): {e}")
        return 0


def _insert_event(
    db,
    *,
    event_type: str,
    source: str,
    urgency: str,
    agent_name: str,
    execution_id: int,
    summary: str,
) -> Optional[int]:
    """Insert a single event row into brain.events."""
    payload = json.dumps({
        "agent_name": agent_name,
        "execution_id": execution_id,
        "summary": summary,
    })
    return db.insert_returning(
        """INSERT INTO brain.events (type, payload, source, urgency)
           VALUES (%s, %s::jsonb, %s, %s)
           RETURNING id""",
        (event_type, payload, source, urgency),
    )
