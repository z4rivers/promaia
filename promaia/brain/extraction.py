"""
Conversation intelligence extraction module for zBrain.

Two extraction tiers:
  1. extract_actions()  — Original action-only extractor (unchanged API).
  2. extract_insights()  — Full conversation intelligence: decisions, insights,
                           preferences, and secondary elements/asides.

Both use instructor + Gemini Flash with a raw-Gemini JSON fallback.
The capture handler calls both: actions go to actions,
insights go to memories as tagged sub-captures.

Philosophy: MuninnDB's cognitive engine (Hebbian learning, temporal decay,
graph traversal) is designed to sort for patterns and relevance. The input
stream should be RICH, not filtered. Under-capturing is the real failure mode.
"""
import json
import logging
import os
from typing import List, Optional

from pydantic import BaseModel

from promaia.ai.models import GOOGLE_MODELS

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Pydantic models — Actions (original, unchanged)
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
# Pydantic models — Conversation Intelligence (new)
# ---------------------------------------------------------------------------

class ExtractedDecision(BaseModel):
    """A decision or commitment made during conversation."""
    description: str
    domain: Optional[str] = None
    confidence: str = "firm"  # "firm", "tentative", "exploring"


class ExtractedInsight(BaseModel):
    """A technical discovery, architecture revelation, or breakthrough."""
    description: str
    domain: Optional[str] = None
    category: str = "technical"  # "technical", "strategic", "personal", "process"


class ExtractedPreference(BaseModel):
    """A revealed preference about how the user thinks, works, or values things."""
    description: str
    profile_category: Optional[str] = None  # maps to profile categories
    profile_field: Optional[str] = None     # suggested field name


class ExtractedAside(BaseModel):
    """A secondary element or tangent that is independently valuable."""
    description: str
    domain: Optional[str] = None


class ConversationIntelligence(BaseModel):
    """Full intelligence extraction from a block of conversation text."""
    decisions: List[ExtractedDecision]
    insights: List[ExtractedInsight]
    preferences: List[ExtractedPreference]
    asides: List[ExtractedAside]
    has_intelligence: bool


# ---------------------------------------------------------------------------
# Extraction prompts
# ---------------------------------------------------------------------------

_ACTION_PROMPT = """Extract any actionable items from this text. Look for:
- "I need to..."
- "don't forget..."
- "we should..."
- "make sure to..."
- explicit commitments or tasks

For each action found, set urgency to one of: "urgent", "normal", "someday".
If no actions found, return has_actions=False with empty list.

Text to analyze:
{text}"""


_INTELLIGENCE_PROMPT = """You are a conversation intelligence engine for a personal AI memory system.
Analyze this text and extract ONLY elements that are genuinely present. Do NOT fabricate or infer
things that aren't clearly stated. If a category has no matches, return an empty list for it.

Extract these types of intelligence:

1. DECISIONS — Choices made or commitments stated.
   Look for: "we decided...", "let's go with...", "I'm going to...", "the plan is..."
   Set confidence: "firm" (definite), "tentative" (leaning), "exploring" (considering)

2. INSIGHTS — Technical discoveries, architecture revelations, breakthroughs, or important
   realizations. These are "aha" moments or key understanding shifts.
   Set category: "technical", "strategic", "personal", "process"

3. PREFERENCES — Revealed preferences about how the user thinks, works, communicates, or
   what they value. Things that help an AI understand and adapt to this person.
   If possible, suggest a profile_category (e.g. "cognitive_style", "communication",
   "work_patterns", "values_and_motivation", "energy_patterns") and a profile_field name.
   Only extract clear, genuine preferences — not every opinion on every topic.

4. ASIDES — Secondary elements, tangents, or off-topic mentions that are independently
   valuable as memories. Things the user mentioned in passing that shouldn't be lost.
   Include the relevant domain if identifiable.

Return has_intelligence=False ONLY if ALL four lists are empty.

Text to analyze:
{text}"""


# ---------------------------------------------------------------------------
# Main extraction functions
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

    api_key = os.environ.get('GEMINI_API_KEY') or os.environ.get('GOOGLE_API_KEY')
    if not api_key:
        logger.warning("Neither GEMINI_API_KEY nor GOOGLE_API_KEY set — skipping action extraction")
        return ActionExtractionResult(actions=[], has_actions=False)

    # Try instructor path first
    try:
        return _extract_actions_via_instructor(text, api_key)
    except Exception as e:
        logger.warning(f"instructor extraction failed ({e}), trying raw Gemini fallback")

    # Fallback: raw Gemini Flash with JSON mode
    try:
        return _extract_actions_via_raw_gemini(text, api_key)
    except Exception as e:
        logger.error(f"Action extraction failed (both paths): {e}")
        return ActionExtractionResult(actions=[], has_actions=False)


def extract_insights(text: str) -> ConversationIntelligence:
    """Extract conversation intelligence: decisions, insights, preferences, asides.

    Uses Gemini Flash to identify substantive elements in conversation text
    that should be captured as independent memories for MuninnDB's cognitive
    graph to work with.

    Args:
        text: Free-form conversation text to analyze.

    Returns:
        ConversationIntelligence with lists of decisions, insights, preferences,
        and asides. Returns empty result on any failure (never raises).
    """
    empty = ConversationIntelligence(
        decisions=[], insights=[], preferences=[], asides=[],
        has_intelligence=False,
    )

    if not text or not text.strip():
        return empty

    # Skip intelligence extraction for very short texts (< 80 chars)
    # These are simple notes, not conversation fragments worth decomposing
    if len(text.strip()) < 80:
        return empty

    api_key = os.environ.get('GEMINI_API_KEY') or os.environ.get('GOOGLE_API_KEY')
    if not api_key:
        logger.warning("Neither GEMINI_API_KEY nor GOOGLE_API_KEY set — skipping intelligence extraction")
        return empty

    # Try instructor path first
    try:
        return _extract_insights_via_instructor(text, api_key)
    except Exception as e:
        logger.warning(f"instructor intelligence extraction failed ({e}), trying raw fallback")

    # Fallback: raw Gemini Flash with JSON mode
    try:
        return _extract_insights_via_raw_gemini(text, api_key)
    except Exception as e:
        logger.error(f"Intelligence extraction failed (both paths): {e}")
        return empty


# ---------------------------------------------------------------------------
# Action extraction implementations (original, renamed for clarity)
# ---------------------------------------------------------------------------

def _extract_actions_via_instructor(text: str, api_key: str) -> ActionExtractionResult:
    """Attempt action extraction using instructor + google-genai client."""
    import instructor
    from google import genai

    client = genai.Client(api_key=api_key)
    instructor_client = instructor.from_genai(client)

    prompt = _ACTION_PROMPT.format(text=text)

    result = instructor_client.chat.completions.create(
        model=GOOGLE_MODELS["flash-lite"],
        messages=[{"role": "user", "content": prompt}],
        response_model=ActionExtractionResult,
    )

    return result


def _extract_actions_via_raw_gemini(text: str, api_key: str) -> ActionExtractionResult:
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

    prompt = _ACTION_PROMPT.format(text=text)

    response = client.models.generate_content(
        model=GOOGLE_MODELS["flash-lite"],
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=schema,
        ),
    )

    raw_json = response.text
    result = ActionExtractionResult.model_validate_json(raw_json)
    return result


# ---------------------------------------------------------------------------
# Intelligence extraction implementations (new)
# ---------------------------------------------------------------------------

def _extract_insights_via_instructor(text: str, api_key: str) -> ConversationIntelligence:
    """Extract conversation intelligence using instructor + google-genai client."""
    import instructor
    from google import genai

    client = genai.Client(api_key=api_key)
    instructor_client = instructor.from_genai(client)

    prompt = _INTELLIGENCE_PROMPT.format(text=text)

    result = instructor_client.chat.completions.create(
        model=GOOGLE_MODELS["flash-lite"],
        messages=[{"role": "user", "content": prompt}],
        response_model=ConversationIntelligence,
    )

    return result


def _extract_insights_via_raw_gemini(text: str, api_key: str) -> ConversationIntelligence:
    """Fallback: call Gemini Flash directly in JSON mode for intelligence extraction."""
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=api_key)

    schema = {
        "type": "object",
        "properties": {
            "decisions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "description": {"type": "string"},
                        "domain": {"type": "string", "nullable": True},
                        "confidence": {
                            "type": "string",
                            "enum": ["firm", "tentative", "exploring"]
                        }
                    },
                    "required": ["description", "confidence"]
                }
            },
            "insights": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "description": {"type": "string"},
                        "domain": {"type": "string", "nullable": True},
                        "category": {
                            "type": "string",
                            "enum": ["technical", "strategic", "personal", "process"]
                        }
                    },
                    "required": ["description", "category"]
                }
            },
            "preferences": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "description": {"type": "string"},
                        "profile_category": {"type": "string", "nullable": True},
                        "profile_field": {"type": "string", "nullable": True}
                    },
                    "required": ["description"]
                }
            },
            "asides": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "description": {"type": "string"},
                        "domain": {"type": "string", "nullable": True}
                    },
                    "required": ["description"]
                }
            },
            "has_intelligence": {"type": "boolean"}
        },
        "required": ["decisions", "insights", "preferences", "asides", "has_intelligence"]
    }

    prompt = _INTELLIGENCE_PROMPT.format(text=text)

    response = client.models.generate_content(
        model=GOOGLE_MODELS["flash-lite"],
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=schema,
        ),
    )

    raw_json = response.text
    result = ConversationIntelligence.model_validate_json(raw_json)
    return result
