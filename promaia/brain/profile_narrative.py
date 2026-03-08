"""
Profile narrative synthesis — Gemini generates a natural-language
portrait from structured profile rows.

The narrative is cached in brain.profile_narrative with a hash of
the current profile state. Regenerated only when the profile changes.
"""
import hashlib
import json
import logging
import os

from google import genai
from google.genai import types

from promaia.ai.models import GOOGLE_MODELS
from promaia.storage.postgres_db import get_postgres_db

logger = logging.getLogger(__name__)

SYNTHESIS_PROMPT = """You are writing a concise personal profile portrait for an AI assistant that will use it to calibrate tone, context, and personalization in every conversation.

Here is the structured profile data:

{profile_data}

Write a natural-language portrait in the SECOND PERSON ("you are...", "you prefer..."). Cover:
- Identity essentials (name, age, location, household, work)
- Communication preferences (tone, verbosity, humor, how to handle decisions)
- Energy and rhythm (schedule, peak hours, work style)
- Key relationships (wife, daughter, stepdaughter — names and relevance)
- Cognitive style (learning, focus patterns, neurodivergence)
- Values and motivations (what drives him, what he's building toward)
- System principles (privacy, openness, health/finance mandates)
- Current projects and their status

Rules:
- ~1500 tokens maximum. Dense, no filler.
- Every sentence should carry information the AI needs to show up well.
- Do NOT include raw data like email addresses, phone numbers, or encoded strings.
- DO include names, relationships, preferences, and behavioral patterns.
- Write as if briefing a trusted colleague who will be talking with this person daily.
"""


def _compute_profile_hash(rows: list[dict]) -> str:
    """Hash all profile field values to detect changes."""
    content = json.dumps(
        [(r["category"], r["field"], r["value"]) for r in rows],
        sort_keys=True,
        default=str,
    )
    return hashlib.sha256(content.encode()).hexdigest()[:16]


def _format_rows_for_prompt(rows: list[dict]) -> str:
    """Format profile rows into readable text for the synthesis prompt."""
    lines = []
    current_cat = None
    for row in rows:
        if row["category"] != current_cat:
            current_cat = row["category"]
            lines.append(f"\n## {current_cat.replace('_', ' ').title()}")
        # Skip massive encoded values (email_topics etc.)
        value_str = json.dumps(row["value"], default=str)
        if len(value_str) > 1000:
            value_str = value_str[:200] + "... [truncated]"
        lines.append(f"- {row['field']}: {value_str}")
    return "\n".join(lines)


def get_cached_narrative(db=None) -> dict | None:
    """Return cached narrative if it exists and is current, else None."""
    if db is None:
        db = get_postgres_db()

    rows = db.fetch_all(
        "SELECT narrative, profile_hash, field_count, generated_at "
        "FROM brain.profile_narrative ORDER BY generated_at DESC LIMIT 1"
    )
    if not rows:
        return None
    return rows[0]


def get_current_profile_hash(db=None) -> tuple[str, int, list[dict]]:
    """Compute hash of current profile state. Returns (hash, count, rows)."""
    if db is None:
        db = get_postgres_db()

    rows = db.fetch_all(
        "SELECT category, field, value FROM brain.profile ORDER BY category, field"
    )
    return _compute_profile_hash(rows), len(rows), rows


async def generate_narrative(db=None) -> str:
    """Generate a fresh narrative from current profile via Gemini Flash."""
    if db is None:
        db = get_postgres_db()

    profile_hash, field_count, rows = get_current_profile_hash(db)

    if not rows:
        return "Profile is empty. Start the onboarding interview to populate it."

    profile_text = _format_rows_for_prompt(rows)
    prompt = SYNTHESIS_PROMPT.format(profile_data=profile_text)

    try:
        client = genai.Client(api_key=os.environ.get("GOOGLE_API_KEY"))
        response = await client.aio.models.generate_content(
            model=GOOGLE_MODELS["flash"],
            contents=[types.Content(parts=[types.Part(text=prompt)])],
            config=types.GenerateContentConfig(temperature=0.3, max_output_tokens=2000),
        )
        narrative = response.text.strip()
    except Exception as e:
        logger.error(f"Narrative generation failed: {e}", exc_info=True)
        return f"Narrative generation failed: {e}"

    # Cache it
    try:
        db.execute(
            """
            INSERT INTO brain.profile_narrative (narrative, field_count, profile_hash)
            VALUES (%s, %s, %s)
            """,
            (narrative, field_count, profile_hash),
        )
    except Exception as e:
        logger.warning(f"Could not cache narrative: {e}")

    # Clean up old cached narratives (keep only the latest)
    try:
        db.execute(
            """
            DELETE FROM brain.profile_narrative
            WHERE id NOT IN (
                SELECT id FROM brain.profile_narrative
                ORDER BY generated_at DESC LIMIT 1
            )
            """
        )
    except Exception as e:
        logger.warning(f"Could not clean old narratives: {e}")

    return narrative


async def get_or_generate_narrative(db=None) -> str:
    """Return cached narrative if current, otherwise regenerate."""
    if db is None:
        db = get_postgres_db()

    cached = get_cached_narrative(db)
    current_hash, field_count, _ = get_current_profile_hash(db)

    if cached and cached["profile_hash"] == current_hash:
        return cached["narrative"]

    return await generate_narrative(db)
