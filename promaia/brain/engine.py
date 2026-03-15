"""
Brain engine — 8 deterministic functions for zBrain.

CRITICAL: No LLM calls inside any function. Pure Python + SQL via PostgresDB.
All DB-touching functions accept an optional `db` parameter for testability
(pass a mock or real PostgresDB instance; if None, uses get_db()).

Functions:
    detect_mode(message)           -> {mode, confidence}
    confirm_mode(detected, current) -> str
    enforce_guardrails(action, source) -> bool
    track_time(session_id, domain_id, db) -> float
    budget_check(cycle_id, max_budget, db) -> {remaining, exceeded, calls}
    save_context(session_id, domain_id, db) -> dict
    restore_context(session_id, db) -> dict
    suggest_next(domains, energy, db) -> {domain, action, score, reason}
"""
import json
import logging
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Mode detection keyword sets
# ---------------------------------------------------------------------------
_MODE_KEYWORDS = {
    'working': [
        'build', 'implement', 'code', 'fix', 'create', 'deploy',
        'commit', 'run', 'write', 'develop', 'test', 'debug', 'push',
        'ship', 'release',
    ],
    'planning': [
        'plan', 'think about', 'consider', 'design', 'architect',
        'should we', 'what if', 'approach', 'strategy', 'roadmap',
        'decide', 'evaluate', 'compare', 'options', 'tradeoff',
    ],
    'capturing': [
        'remember', 'note', 'capture', 'save', "don't forget",
        'i need to', 'jot', 'log', 'record', 'store', 'remind',
    ],
    'reviewing': [
        'review', 'check', 'look at', 'status', "how's", 'briefing',
        'summary', 'report', 'overview', 'progress', 'update', 'audit',
    ],
}

# Confirmation phrases per mode transition (from detected -> something else)
_CONFIRM_PHRASES = {
    'working': "Sounds like we're building something — I'll focus on making changes. Sound right?",
    'planning': "Sounds like we're planning — I'll explore options before making changes. Right?",
    'capturing': "Sounds like you want to capture something — I'll save this for later. Right?",
    'reviewing': "Sounds like a review session — I'll give you a status overview. Right?",
}

# ---------------------------------------------------------------------------
# Guardrail patterns (action, source) -> blocked
# Format: list of (required_terms, blocked_sources_or_None)
# required_terms: ALL terms must appear in the action for this rule to fire.
# A single-term entry blocks if that term appears anywhere.
# None means blocked regardless of source.
# ---------------------------------------------------------------------------
_BLOCK_PATTERNS = [
    # Branch safety: block 'main' OR 'master' branch operations always
    # Using separate single-term entries so either word alone triggers the block
    (['main'], None),
    (['master'], None),
    # Communication safety: block send + messaging platforms
    (['send', 'email'], None),
    (['send', 'message'], None),
    (['send', 'slack'], None),
    # Destructive operations
    (['delete'], None),
    # PR merges
    (['merge', 'pr'], None),
    (['merge', 'pull request'], None),
]


def detect_mode(message: str) -> dict:
    """Classify user intent from message text using keyword heuristics.

    Returns:
        dict with keys:
            mode (str): one of 'working', 'planning', 'capturing', 'reviewing'
            confidence (float): 0.0–1.0
    """
    lower = message.lower()
    scores = {}

    for mode, keywords in _MODE_KEYWORDS.items():
        hits = sum(1 for kw in keywords if kw in lower)
        if hits > 0:
            # Confidence scales with number of keyword hits, capped at 0.95
            scores[mode] = min(0.4 + (hits * 0.15), 0.95)

    if not scores:
        return {'mode': 'working', 'confidence': 0.3}

    best_mode = max(scores, key=scores.__getitem__)
    return {'mode': best_mode, 'confidence': scores[best_mode]}


def confirm_mode(detected: str, current: str) -> str:
    """Return a confirmation phrase if mode is changing, empty string if same.

    Args:
        detected: mode just detected from user message
        current:  mode currently active in the session

    Returns:
        Confirmation string to surface to user, or '' if no change.
    """
    if detected == current:
        return ''
    return _CONFIRM_PHRASES.get(detected, f"Switching to {detected} mode — OK?")


def enforce_guardrails(action: str, source: str) -> bool:
    """Check whether an action is allowed.

    Blocks operations that could cause irreversible damage:
    - main/master branch operations
    - send + email/message/slack
    - delete + critical patterns
    - merge + pr/pull request

    Args:
        action: description of the action being attempted
        source: 'heartbeat' (strict) or 'session' (lenient)

    Returns:
        True  if the action is allowed
        False if the action is blocked
    """
    lower = action.lower()

    for patterns, blocked_sources in _BLOCK_PATTERNS:
        # Check if all patterns match within the action string
        if all(p in lower for p in patterns):
            # If blocked_sources is None, block regardless of source
            if blocked_sources is None:
                return False
            # Otherwise block only for the specified source(s)
            if isinstance(blocked_sources, str):
                if source == blocked_sources:
                    return False
            elif source in blocked_sources:
                return False

    return True


def track_time(session_id: str, domain_id: int, db=None) -> float:
    """Return elapsed seconds since earliest brain event for this session+domain.

    Args:
        session_id: current session identifier
        domain_id:  domain to scope the lookup
        db:         PostgresDB instance (uses get_db() if None)

    Returns:
        Elapsed seconds as float. 0.0 if no events found.
    """
    if db is None:
        from promaia.storage.db_factory import get_db
        db = get_db()

    try:
        row = db.fetch_one(
            """
            SELECT MIN(created_at) AS earliest
            FROM events
            WHERE session_id = %s
              AND CAST(json_extract(payload, '$.domain_id') AS INTEGER) = %s
            """,
            (session_id, domain_id),
        )
        if row and row.get('earliest'):
            earliest = row['earliest']
            if isinstance(earliest, str):
                earliest = datetime.fromisoformat(earliest)
            # Ensure tz-aware comparison
            now = datetime.now(timezone.utc)
            if earliest.tzinfo is None:
                earliest = earliest.replace(tzinfo=timezone.utc)
            return (now - earliest).total_seconds()
    except Exception as e:
        logger.warning(f"track_time query failed: {e}")

    return 0.0


def budget_check(cycle_id: str, max_budget: float = 1.0, db=None) -> dict:
    """Check API call budget for a heartbeat cycle.

    Queries events where source='heartbeat' and session_id=cycle_id,
    counts rows with type='api_call', sums payload->>'cost'.

    Args:
        cycle_id:   heartbeat cycle identifier (maps to session_id)
        max_budget: maximum allowed spend (default $1.00)
        db:         PostgresDB instance (uses get_db() if None)

    Returns:
        dict: {remaining: float, exceeded: bool, calls: int}
    """
    if db is None:
        from promaia.storage.db_factory import get_db
        db = get_db()

    try:
        row = db.fetch_one(
            """
            SELECT
                COUNT(*) AS calls,
                COALESCE(SUM(CAST(json_extract(payload, '$.cost') AS REAL)), 0.0) AS total_cost
            FROM events
            WHERE source = 'heartbeat'
              AND session_id = %s
              AND type = 'api_call'
            """,
            (cycle_id,),
        )
        calls = int(row['calls']) if row and row.get('calls') else 0
        total_cost = float(row['total_cost']) if row and row.get('total_cost') else 0.0
        remaining = max(0.0, max_budget - total_cost)
        return {
            'remaining': remaining,
            'exceeded': total_cost >= max_budget,
            'calls': calls,
        }
    except Exception as e:
        logger.warning(f"budget_check query failed: {e}")
        return {'remaining': max_budget, 'exceeded': False, 'calls': 0}


def save_context(session_id: str, domain_id: int, db=None) -> dict:
    """Snapshot the current contexts row for this domain into events.

    Inserts an event with type='context_save'. Returns the snapshot dict.

    Args:
        session_id: current session identifier
        domain_id:  domain to snapshot
        db:         PostgresDB instance (uses get_db() if None)

    Returns:
        Snapshot dict with domain_id, timestamp, and context fields.
        Empty dict on failure.
    """
    if db is None:
        from promaia.storage.db_factory import get_db
        db = get_db()

    try:
        context_row = db.fetch_one(
            """
            SELECT id, domain_id, directive, current_state,
                   last_updated, priority, stale_threshold_days
            FROM contexts
            WHERE domain_id = %s
            ORDER BY last_updated DESC
            LIMIT 1
            """,
            (domain_id,),
        )

        snapshot = {
            'domain_id': domain_id,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'context': context_row if context_row else {},
        }

        # Serialize datetimes in context_row
        if context_row:
            for key, val in snapshot['context'].items():
                if isinstance(val, datetime):
                    snapshot['context'][key] = val.isoformat()

        db.execute(
            """
            INSERT INTO events (type, payload, source, session_id)
            VALUES ('context_save', %s, 'session', %s)
            """,
            (json.dumps(snapshot), session_id),
        )

        return snapshot

    except Exception as e:
        logger.warning(f"save_context failed: {e}")
        return {}


def restore_context(session_id: str, db=None) -> dict:
    """Retrieve the most recent context_save snapshot for this session.

    Args:
        session_id: session to restore context for
        db:         PostgresDB instance (uses get_db() if None)

    Returns:
        Snapshot dict from the most recent context_save event.
        Empty dict if none found.
    """
    if db is None:
        from promaia.storage.db_factory import get_db
        db = get_db()

    try:
        row = db.fetch_one(
            """
            SELECT payload
            FROM events
            WHERE type = 'context_save'
              AND session_id = %s
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (session_id,),
        )
        if row and row.get('payload'):
            payload = row['payload']
            if isinstance(payload, str):
                return json.loads(payload)
            return payload  # psycopg2 may already parse JSONB as dict
    except Exception as e:
        logger.warning(f"restore_context query failed: {e}")

    return {}


def suggest_next(domains: list, energy: str = None, db=None) -> dict:
    """Suggest the highest-priority domain to work on next.

    Scoring algorithm:
    - staleness_score = days_since_update / stale_threshold_days, capped at 2.0
    - priority_score  = (11 - priority) / 10  (priority 1 = 1.0, priority 10 = 0.1)
    - combined_score  = staleness_score + priority_score
    - energy='low' halves the score for high-effort items (priority <= 3)

    Args:
        domains: list of domain dicts, each expected to contain:
                 name, directive, current_state, last_updated,
                 priority, stale_threshold_days
        energy:  'low' | 'high' | None — adjusts scoring for user energy level
        db:      PostgresDB instance (unused here; accepted for API consistency)

    Returns:
        dict: {domain: str, action: str, score: float, reason: str}
        Empty dict if domains is empty.
    """
    if not domains:
        return {}

    now = datetime.now(timezone.utc)
    scored = []

    for d in domains:
        name = d.get('name', 'unknown')
        priority = int(d.get('priority', 5))
        stale_days = int(d.get('stale_threshold_days', 7))
        directive = d.get('directive', '')
        current_state = d.get('current_state', '')

        # Staleness score
        last_updated = d.get('last_updated')
        if last_updated:
            if isinstance(last_updated, str):
                try:
                    last_updated = datetime.fromisoformat(last_updated)
                except ValueError:
                    last_updated = None
            if last_updated and last_updated.tzinfo is None:
                last_updated = last_updated.replace(tzinfo=timezone.utc)

        if last_updated:
            days_stale = (now - last_updated).total_seconds() / 86400
        else:
            days_stale = stale_days  # treat unknown as fully stale

        staleness_score = min(days_stale / max(stale_days, 1), 2.0)

        # Priority score: priority 1 (most urgent) -> 1.0, priority 10 -> 0.1
        priority_score = (11 - priority) / 10.0

        combined = staleness_score + priority_score

        # Energy adjustment: low energy -> halve score for high-effort items
        if energy == 'low' and priority <= 3:
            combined *= 0.5

        reason_parts = []
        if staleness_score > 1.0:
            reason_parts.append(f"overdue by {days_stale:.1f} days")
        elif staleness_score > 0.5:
            reason_parts.append(f"getting stale ({days_stale:.1f} days)")
        if priority <= 3:
            reason_parts.append(f"high priority ({priority})")
        if not reason_parts:
            reason_parts.append(f"priority {priority}")

        reason = '; '.join(reason_parts)
        action = directive or current_state or f"Review {name}"

        scored.append({
            'domain': name,
            'action': action,
            'score': combined,
            'reason': reason,
        })

    if not scored:
        return {}

    top = max(scored, key=lambda x: x['score'])
    return top
