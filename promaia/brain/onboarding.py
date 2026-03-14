"""
Onboarding state engine for zBrain.

Manages the multi-session, multi-channel onboarding flow.
Tracks which channels (interview, pc_scan, gmail, photos) have been
completed and what profile areas still need coverage.

All functions accept an optional `db` parameter for testability
(pass a mock or real PostgresDB instance; if None, uses get_db()).

Functions:
    start_onboarding(user_id, db)        -> dict  (session + channel status)
    get_onboarding_status(user_id, db)   -> dict  (full status with coverage)
    mark_channel_progress(session_id, channel, status, ..., db) -> bool
    get_profile_coverage(db)             -> dict  (per-category gap analysis)
    complete_onboarding(session_id, db)  -> bool
"""
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Expected profile fields per category (from onboarding research schema)
# Used by get_profile_coverage() to identify gaps
# ---------------------------------------------------------------------------
EXPECTED_FIELDS = {
    # --- Tier 1: Ask directly, day one ---
    'identity': [
        'preferred_name', 'pronouns', 'timezone',
        'primary_device', 'primary_use', 'bio_blurb',
    ],
    # --- Tier 2: Ask early, slightly more personal ---
    'context': [
        'role', 'employer', 'industry',
        'active_projects', 'tech_stack', 'devices',
    ],
    'relationships': [
        'people',           # named individuals, type, notes
        'household',        # partner, kids, caregivers
        'key_collaborators',
    ],
    'communication': [
        # Tier 1/2 — declared early
        'preferred_tone', 'verbosity', 'feedback_style',
        'humor_type', 'emoji_tolerance', 'preferred_channels',
        # Tier 3 — inferred from patterns
        'message_length_pattern', 'response_to_long_answers',
    ],
    # --- Tier 3: Observe and infer, confirm when confident ---
    'cognitive_style': [
        # Asked directly (Tier 2)
        'decision_making', 'information_density', 'learning_style',
        # Inferred (Tier 3)
        'decision_speed', 'follow_through',
        # Earned over time (Tier 5)
        'need_for_closure', 'locus_of_control', 'risk_tolerance',
        'regulatory_focus', 'need_for_cognition', 'cognitive_load_threshold',
    ],
    'energy_patterns': [
        # Inferred (Tier 3)
        'chronotype', 'peak_focus_hours', 'sprint_duration_min',
        'email_send_times', 'email_activity_hours',
        # Asked (Tier 2/3)
        'energy_drains', 'energy_sources',
    ],
    'work_patterns': [
        # Asked (Tier 2/3)
        'deadline_relationship', 'deep_work_prefs', 'meeting_tolerance',
        # Inferred (Tier 3)
        'working_hours', 'inbox_relationship',
    ],
    # --- Tier 4: Earn over time, deeper and more personal ---
    'values_and_motivation': [
        'drivers', 'ambition', 'values_hierarchy',
        'purpose_statement', 'who_they_do_it_for',
        'motivational_drivers', 'self_efficacy',
    ],
    'emotional_landscape': [
        # Tier 4
        'patience_level', 'stress_response', 'known_triggers',
        'pride_points', 'humor_deployment',
        # Tier 5 (inferred only, never asked directly)
        'conflict_style', 'emotional_baseline', 'shame_sensitivity',
    ],
    'personality': [
        # Tier 4 — asked when trust exists
        'desired_ai_personality', 'pushback_tolerance', 'touchy_topics',
        # Tier 5 — inferred only
        'identity_anchors',
    ],
    # --- Neurodivergence: user-disclosed only ---
    'neurodivergence': [
        'adhd_patterns', 'sensory_preferences', 'accommodation_notes',
    ],
}

# Which fields should NEVER be asked directly — inferred from patterns only
INFERRED_ONLY_FIELDS = {
    'cognitive_style': [
        'need_for_closure', 'locus_of_control', 'risk_tolerance',
        'regulatory_focus', 'decision_speed', 'follow_through',
    ],
    'emotional_landscape': [
        'conflict_style', 'emotional_baseline', 'shame_sensitivity',
    ],
    'personality': ['identity_anchors'],
    'energy_patterns': ['email_send_times', 'email_activity_hours'],
    'communication': ['message_length_pattern', 'response_to_long_answers'],
    'work_patterns': ['inbox_relationship'],
}

# Which tier each category primarily belongs to (for sequencing)
FIELD_TIERS = {
    'identity': 1,
    'context': 2,
    'relationships': 2,
    'communication': 2,
    'energy_patterns': 3,
    'work_patterns': 3,
    'cognitive_style': 3,
    'values_and_motivation': 4,
    'emotional_landscape': 4,
    'personality': 4,
    'neurodivergence': 4,
}

# All onboarding channels
CHANNELS = ['interview', 'pc_scan', 'gmail', 'photos']


def _get_db(db=None):
    """Return db instance, creating one if not provided."""
    if db is None:
        from promaia.storage.db_factory import get_db
        return get_db()
    return db


def start_onboarding(user_id: str = 'default', db=None) -> dict:
    """Start a new onboarding session or return the existing active one.

    Creates a session row and 4 progress rows (one per channel, all 'not_started').
    If an active session already exists for this user, returns that instead.

    Returns:
        dict: {session_id, status, channels: [{channel, status}]}
    """
    db = _get_db(db)

    try:
        # Check for existing active/paused session
        existing = db.fetch_one(
            """
            SELECT id, status, started_at, last_activity
            FROM brain.onboarding_sessions
            WHERE user_id = %s AND status IN ('active', 'paused')
            ORDER BY started_at DESC
            LIMIT 1
            """,
            (user_id,),
        )

        if existing:
            session_id = existing['id']
            # Update last_activity
            db.execute(
                "UPDATE brain.onboarding_sessions SET last_activity = NOW() WHERE id = %s",
                (session_id,),
            )
            # If paused, reactivate
            if existing['status'] == 'paused':
                db.execute(
                    "UPDATE brain.onboarding_sessions SET status = 'active' WHERE id = %s",
                    (session_id,),
                )
        else:
            # Create new session
            session_id = db.insert_returning(
                """
                INSERT INTO brain.onboarding_sessions (user_id)
                VALUES (%s)
                RETURNING id
                """,
                (user_id,),
            )

            # Create progress rows for each channel
            for channel in CHANNELS:
                db.execute(
                    """
                    INSERT INTO brain.onboarding_progress (session_id, channel)
                    VALUES (%s, %s)
                    ON CONFLICT (session_id, channel) DO NOTHING
                    """,
                    (session_id, channel),
                )

        # Fetch channel statuses
        channels = db.fetch_all(
            """
            SELECT channel, status
            FROM brain.onboarding_progress
            WHERE session_id = %s
            ORDER BY channel
            """,
            (session_id,),
        )

        return {
            'session_id': session_id,
            'status': 'active',
            'channels': [{'channel': r['channel'], 'status': r['status']} for r in channels],
        }

    except Exception as e:
        logger.error(f"start_onboarding failed: {e}", exc_info=True)
        return {'session_id': None, 'status': 'error', 'channels': [], 'error': str(e)}


def get_onboarding_status(user_id: str = 'default', db=None) -> Optional[dict]:
    """Return current onboarding state with channel progress and profile coverage.

    Returns:
        dict: {session_id, status, started_at, last_activity,
               channels: [{channel, status, fields_populated}],
               profile_coverage: {category: {expected, populated, missing}}}
        None if no active/paused session exists.
    """
    db = _get_db(db)

    try:
        session = db.fetch_one(
            """
            SELECT id, status, started_at, last_activity
            FROM brain.onboarding_sessions
            WHERE user_id = %s AND status IN ('active', 'paused')
            ORDER BY started_at DESC
            LIMIT 1
            """,
            (user_id,),
        )

        if not session:
            return None

        session_id = session['id']

        # Channel progress
        channels = db.fetch_all(
            """
            SELECT channel, status, fields_populated
            FROM brain.onboarding_progress
            WHERE session_id = %s
            ORDER BY channel
            """,
            (session_id,),
        )

        # Profile coverage
        coverage = get_profile_coverage(db=db)

        # Format timestamps
        started_at = session.get('started_at')
        last_activity = session.get('last_activity')
        if hasattr(started_at, 'isoformat'):
            started_at = started_at.isoformat()
        if hasattr(last_activity, 'isoformat'):
            last_activity = last_activity.isoformat()

        return {
            'session_id': session_id,
            'status': session['status'],
            'started_at': started_at,
            'last_activity': last_activity,
            'channels': [
                {
                    'channel': r['channel'],
                    'status': r['status'],
                    'fields_populated': r['fields_populated'],
                }
                for r in channels
            ],
            'profile_coverage': coverage,
        }

    except Exception as e:
        logger.error(f"get_onboarding_status failed: {e}", exc_info=True)
        return None


def mark_channel_progress(
    session_id: int,
    channel: str,
    status: str,
    fields_populated: Optional[int] = None,
    notes: Optional[str] = None,
    db=None,
) -> bool:
    """Update a channel's progress within an onboarding session.

    When status='complete', sets completed_at=NOW().
    When status='in_progress' and started_at is null, sets started_at=NOW().
    Also updates session last_activity.

    Returns:
        True on success, False on failure.
    """
    db = _get_db(db)

    valid_statuses = ('not_started', 'in_progress', 'complete', 'skipped')
    if status not in valid_statuses:
        logger.warning(f"Invalid channel status: {status}")
        return False

    if channel not in CHANNELS:
        logger.warning(f"Invalid channel: {channel}")
        return False

    try:
        # Build dynamic update
        set_parts = ["status = %s"]
        params = [status]

        if status == 'in_progress':
            set_parts.append("started_at = COALESCE(started_at, NOW())")
        elif status in ('complete', 'skipped'):
            set_parts.append("completed_at = NOW()")

        if fields_populated is not None:
            set_parts.append("fields_populated = %s")
            params.append(fields_populated)

        if notes is not None:
            set_parts.append("notes = %s")
            params.append(notes)

        params.extend([session_id, channel])

        db.execute(
            f"""
            UPDATE brain.onboarding_progress
            SET {', '.join(set_parts)}
            WHERE session_id = %s AND channel = %s
            """,
            tuple(params),
        )

        # Update session last_activity
        db.execute(
            "UPDATE brain.onboarding_sessions SET last_activity = NOW() WHERE id = %s",
            (session_id,),
        )

        return True

    except Exception as e:
        logger.error(f"mark_channel_progress failed: {e}", exc_info=True)
        return False


def get_profile_coverage(db=None) -> dict:
    """Analyze profile coverage against EXPECTED_FIELDS.

    Queries brain.profile for populated fields by category and compares
    against expected fields to show gaps.

    Returns:
        dict: {category: {expected: N, populated: M, missing: [field_names]}}
    """
    db = _get_db(db)

    try:
        # Get all populated profile fields grouped by category
        rows = db.fetch_all(
            """
            SELECT category, field
            FROM brain.profile
            ORDER BY category, field
            """
        )

        # Build set of populated fields per category
        populated = {}
        for row in rows:
            cat = row['category']
            if cat not in populated:
                populated[cat] = set()
            populated[cat].add(row['field'])

        # Compare against expected
        coverage = {}
        for category, expected_fields in EXPECTED_FIELDS.items():
            pop_set = populated.get(category, set())
            missing = [f for f in expected_fields if f not in pop_set]
            coverage[category] = {
                'expected': len(expected_fields),
                'populated': len(expected_fields) - len(missing),
                'missing': missing,
            }

        return coverage

    except Exception as e:
        logger.error(f"get_profile_coverage failed: {e}", exc_info=True)
        # Return empty coverage on error
        return {
            cat: {'expected': len(fields), 'populated': 0, 'missing': list(fields)}
            for cat, fields in EXPECTED_FIELDS.items()
        }


def complete_onboarding(session_id: int, db=None) -> bool:
    """Finalize an onboarding session.

    Sets session status='complete' and completed_at=NOW().

    Returns:
        True on success, False on failure.
    """
    db = _get_db(db)

    try:
        db.execute(
            """
            UPDATE brain.onboarding_sessions
            SET status = 'complete', completed_at = NOW(), last_activity = NOW()
            WHERE id = %s
            """,
            (session_id,),
        )
        return True

    except Exception as e:
        logger.error(f"complete_onboarding failed: {e}", exc_info=True)
        return False
