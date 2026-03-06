"""
Action extraction module for zBrain.

Uses instructor + Gemini Flash to extract structured actionable items
from free-form text captured via the brain MCP capture tool.

If instructor.from_genai is unavailable (version mismatch), falls back to
raw Gemini Flash with response_mime_type="application/json" and manual
Pydantic validation.
"""
import json
import logging
import os
from typing import List, Optional

from pydantic import BaseModel

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class ExtractedAction(BaseModel):
    """A single actionable item extracted from text."""
    description: str
    domain: Optional[str] = None
    urgency: str = "normal"  # choices: "urgent", "normal", "someday"


class ActionExtractionResult(BaseModel):
    """Result of action extraction from a block of text."""
    actions: List[ExtractedAction]
    has_actions: bool


# ---------------------------------------------------------------------------
# Extraction prompt
# ---------------------------------------------------------------------------

_EXTRACTION_PROMPT = """Extract any actionable items from this text. Look for:
- "I need to..."
- "don't forget..."
- "we should..."
- "make sure to..."
- explicit commitments or tasks

For each action found, set urgency to one of: "urgent", "normal", "someday".
If no actions found, return has_actions=False with empty list.

Text to analyze:
{text}"""


# ---------------------------------------------------------------------------
# Main extraction function
# ---------------------------------------------------------------------------

def extract_actions(text: str) -> ActionExtractionResult:
    """Extract actionable items from text using Gemini Flash via instructor.

    Attempts instructor.from_genai() first; falls back to raw Gemini JSON
    mode + manual Pydantic validation if instructor integration is unavailable.

    Args:
        text: Free-form text to scan for actions.

    Returns:
        ActionExtractionResult with list of extracted actions and has_actions flag.
        Returns empty result on any failure (never raises).
    """
    if not text or not text.strip():
        return ActionExtractionResult(actions=[], has_actions=False)

    api_key = os.environ.get('GOOGLE_API_KEY')
    if not api_key:
        logger.warning("GOOGLE_API_KEY not set — skipping action extraction")
        return ActionExtractionResult(actions=[], has_actions=False)

    # Try instructor path first
    try:
        return _extract_via_instructor(text, api_key)
    except Exception as e:
        logger.warning(f"instructor extraction failed ({e}), trying raw Gemini fallback")

    # Fallback: raw Gemini Flash with JSON mode
    try:
        return _extract_via_raw_gemini(text, api_key)
    except Exception as e:
        logger.error(f"Action extraction failed (both paths): {e}")
        return ActionExtractionResult(actions=[], has_actions=False)


def _extract_via_instructor(text: str, api_key: str) -> ActionExtractionResult:
    """Attempt extraction using instructor + google-genai client."""
    import instructor
    from google import genai

    client = genai.Client(api_key=api_key)
    instructor_client = instructor.from_genai(client)

    prompt = _EXTRACTION_PROMPT.format(text=text)

    result = instructor_client.chat.completions.create(
        model="gemini-3.1-flash-lite-preview",
        messages=[{"role": "user", "content": prompt}],
        response_model=ActionExtractionResult,
    )

    return result


def _extract_via_raw_gemini(text: str, api_key: str) -> ActionExtractionResult:
    """Fallback: call Gemini Flash directly in JSON mode, parse with Pydantic."""
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=api_key)

    schema = {
        "type": "object",
        "properties": {
            "actions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "description": {"type": "string"},
                        "domain": {"type": "string", "nullable": True},
                        "urgency": {
                            "type": "string",
                            "enum": ["urgent", "normal", "someday"]
                        }
                    },
                    "required": ["description", "urgency"]
                }
            },
            "has_actions": {"type": "boolean"}
        },
        "required": ["actions", "has_actions"]
    }

    prompt = _EXTRACTION_PROMPT.format(text=text)

    response = client.models.generate_content(
        model="gemini-3.1-flash-lite-preview",
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=schema,
        ),
    )

    raw_json = response.text
    result = ActionExtractionResult.model_validate_json(raw_json)
    return result
