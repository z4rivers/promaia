"""
Interview orchestration for onboarding.

Determines WHAT to ask next based on current profile state. Does NOT
conduct the conversation -- that's Claude's job using CLAUDE.md instructions.
This module provides the NEXT question and tracks interview progress.

The interview module queries brain.profile to find coverage gaps, then
cross-references with the question bank to find unanswered questions,
respecting the phase ordering (warm_up -> current_state ->
gap_identification -> commitment).

Usage:
    from promaia.brain.channels.interview import (
        get_interview_state,
        get_next_question,
        mark_question_answered,
    )
"""
import logging
from typing import Dict, List, Optional

from promaia.brain.channels.question_bank import (
    PHASE_ORDER,
    QUESTION_BANK,
    get_questions_for_category,
)
from promaia.brain.onboarding import EXPECTED_FIELDS

logger = logging.getLogger(__name__)


def _get_db(db=None):
    """Return db instance, creating one if not provided."""
    if db is None:
        from promaia.storage.postgres_db import get_postgres_db
        return get_postgres_db()
    return db


def _get_populated_fields(db) -> Dict[str, set]:
    """Query brain.profile for all populated fields, grouped by category.

    Returns:
        Dict mapping category -> set of field names.
    """
    try:
        rows = db.fetch_all(
            "SELECT category, field FROM brain.profile ORDER BY category, field"
        )
        populated: Dict[str, set] = {}
        for row in rows:
            cat = row["category"]
            if cat not in populated:
                populated[cat] = set()
            populated[cat].add(row["field"])
        return populated
    except Exception as e:
        logger.error(f"Failed to query profile fields: {e}")
        return {}


def _category_fill_pct(category: str, populated: Dict[str, set]) -> float:
    """Calculate fill percentage for a category.

    Returns:
        Float between 0.0 and 1.0 representing how much of the category
        is populated relative to EXPECTED_FIELDS.
    """
    expected = EXPECTED_FIELDS.get(category, [])
    if not expected:
        return 1.0  # Unknown category considered complete
    pop_set = populated.get(category, set())
    filled = sum(1 for f in expected if f in pop_set)
    return filled / len(expected)


def _question_fields_populated(question: dict, populated: Dict[str, set]) -> bool:
    """Check whether a question's target fields are already populated.

    A question is considered answered if ALL of its target fields exist
    in brain.profile.
    """
    for field_spec in question.get("fields", []):
        parts = field_spec.split(".", 1)
        if len(parts) != 2:
            continue
        cat, field = parts
        cat_fields = populated.get(cat, set())
        if field not in cat_fields:
            return False
    return True


def get_interview_state(db=None) -> dict:
    """Return the current interview state based on profile coverage.

    Queries brain.profile to see which categories have fields populated,
    then cross-references with QUESTION_BANK to find unanswered questions.

    Args:
        db: Optional database instance (for testability).

    Returns:
        dict: {
            current_phase: str,
            categories_covered: [str],
            categories_remaining: [str],
            total_questions_asked: int,
            next_category: str | None,
            completion_pct: float,
        }
    """
    db = _get_db(db)
    populated = _get_populated_fields(db)

    total_questions = sum(len(qs) for qs in QUESTION_BANK.values())
    answered = 0
    categories_covered = []
    categories_remaining = []

    for category, questions in QUESTION_BANK.items():
        cat_answered = 0
        for q in questions:
            if _question_fields_populated(q, populated):
                cat_answered += 1
                answered += 1

        fill_pct = _category_fill_pct(category, populated)
        # A category is "covered" if >60% filled OR all its questions answered
        if fill_pct > 0.6 or cat_answered == len(questions):
            categories_covered.append(category)
        else:
            categories_remaining.append(category)

    # Determine current phase from remaining categories
    current_phase = "complete"
    for phase in PHASE_ORDER:
        phase_has_remaining = False
        for category in categories_remaining:
            for q in QUESTION_BANK.get(category, []):
                if q["phase"] == phase and not _question_fields_populated(q, populated):
                    phase_has_remaining = True
                    break
            if phase_has_remaining:
                break
        if phase_has_remaining:
            current_phase = phase
            break

    # Pick next category (lowest fill percentage among remaining)
    next_category = None
    if categories_remaining:
        # Filter to categories that have questions in the current phase
        phase_categories = []
        for cat in categories_remaining:
            for q in QUESTION_BANK.get(cat, []):
                if q["phase"] == current_phase and not _question_fields_populated(q, populated):
                    phase_categories.append(cat)
                    break

        if phase_categories:
            next_category = min(
                phase_categories,
                key=lambda c: _category_fill_pct(c, populated),
            )
        else:
            # Fall back to lowest fill from remaining
            next_category = min(
                categories_remaining,
                key=lambda c: _category_fill_pct(c, populated),
            )

    completion_pct = (answered / total_questions * 100) if total_questions > 0 else 100.0

    return {
        "current_phase": current_phase,
        "categories_covered": sorted(categories_covered),
        "categories_remaining": sorted(categories_remaining),
        "total_questions_asked": answered,
        "next_category": next_category,
        "completion_pct": round(completion_pct, 1),
    }


def get_next_question(current_category: Optional[str] = None, db=None) -> Optional[dict]:
    """Get the next unanswered question to ask.

    Respects phase ordering: warm_up questions before current_state before
    gap_identification before commitment. Within a phase, picks the category
    with the lowest fill percentage.

    Args:
        current_category: If provided, get next unanswered question in
                         this specific category. If not, pick automatically.
        db: Optional database instance.

    Returns:
        Question dict from QUESTION_BANK (with text, fields, ai_disclosure, etc.)
        plus an added 'category' key. Returns None if all questions answered
        or all categories sufficiently populated (>60% fill).
    """
    db = _get_db(db)
    populated = _get_populated_fields(db)

    if current_category:
        # Get next unanswered question in this specific category
        questions = get_questions_for_category(current_category)
        for q in questions:
            if not _question_fields_populated(q, populated):
                # Skip conditional questions if condition not met
                if q.get("condition") == "only_if_adhd_mentioned":
                    adhd_fields = populated.get("neurodivergence", set())
                    if "adhd_patterns" not in adhd_fields:
                        continue
                return {**q, "category": current_category}
        return None  # All questions in this category answered

    # Auto-select: iterate through phases in order
    for phase in PHASE_ORDER:
        # Find all unanswered questions in this phase
        candidates = []
        for category, questions in QUESTION_BANK.items():
            fill_pct = _category_fill_pct(category, populated)
            if fill_pct > 0.6:
                continue  # Category sufficiently populated, skip

            for q in questions:
                if q["phase"] != phase:
                    continue
                if _question_fields_populated(q, populated):
                    continue
                # Skip conditional questions
                if q.get("condition") == "only_if_adhd_mentioned":
                    adhd_fields = populated.get("neurodivergence", set())
                    if "adhd_patterns" not in adhd_fields:
                        continue
                candidates.append((category, q, fill_pct))

        if candidates:
            # Pick from category with lowest fill percentage
            candidates.sort(key=lambda x: x[2])
            category, question, _ = candidates[0]
            return {**question, "category": category}

    return None  # All done


def mark_question_answered(
    category: str,
    fields_populated: List[str],
    db=None,
) -> None:
    """Record that a question was asked and answered.

    The actual profile update happens via the update_profile MCP tool.
    This function:
    1. Logs a brain.events entry for the question
    2. Updates onboarding_progress for the 'interview' channel

    Args:
        category: The profile category the question was in.
        fields_populated: List of "category.field" strings that were populated.
        db: Optional database instance.
    """
    db = _get_db(db)

    try:
        # Log event
        db.execute(
            """
            INSERT INTO brain.events (event_type, detail)
            VALUES ('interview_question', %s)
            """,
            (
                f"category={category}, fields={','.join(fields_populated)}",
            ),
        )

        # Update interview channel progress (increment fields_populated count)
        # Find active session first
        session = db.fetch_one(
            """
            SELECT s.id
            FROM brain.onboarding_sessions s
            WHERE s.status = 'active'
            ORDER BY s.started_at DESC
            LIMIT 1
            """
        )

        if session:
            db.execute(
                """
                UPDATE brain.onboarding_progress
                SET fields_populated = fields_populated + %s,
                    status = 'in_progress',
                    started_at = COALESCE(started_at, NOW())
                WHERE session_id = %s AND channel = 'interview'
                """,
                (len(fields_populated), session["id"]),
            )

    except Exception as e:
        logger.error(f"mark_question_answered failed: {e}", exc_info=True)
