"""
Categorized question templates for the onboarding interview.

Each question uses OARS (Open, Affirm, Reflect, Summarize) and narrative
techniques to extract profile data conversationally. Questions include
reciprocal AI disclosure so Claude can share about itself in return.

The question bank is the CONTENT layer. Interview orchestration (interview.py)
decides WHICH question to ask next based on profile gaps.

Usage:
    from promaia.brain.channels.question_bank import (
        QUESTION_BANK,
        get_questions_for_category,
        get_questions_for_phase,
    )
"""
from typing import Dict, List, Optional


# ---------------------------------------------------------------------------
# Question Bank
# ---------------------------------------------------------------------------
# Each question has:
#   text          - The question to ask (conversational tone)
#   fields        - Which brain.profile fields this populates (category.field)
#   phase         - Interview arc phase: warm_up -> current_state -> gap_identification -> commitment
#   technique     - OARS technique: open, narrative, scaling, values_elicitation, two_word_checkin
#   follow_ups    - Follow-up question templates (may use {answer} placeholder)
#   ai_disclosure - What Claude shares about itself (reciprocal), or None
# ---------------------------------------------------------------------------

QUESTION_BANK: Dict[str, List[dict]] = {
    "identity": [
        {
            "text": "What should I call you?",
            "fields": ["identity.preferred_name"],
            "phase": "warm_up",
            "technique": "open",
            "follow_ups": [],
            "ai_disclosure": "I tend to go by Claude, though some people give me nicknames. I like that.",
        },
        {
            "text": "Where are you based? Timezone helps me know when you're likely around.",
            "fields": ["identity.timezone"],
            "phase": "warm_up",
            "technique": "open",
            "follow_ups": [],
            "ai_disclosure": "I exist everywhere and nowhere -- but I'll anchor to your timezone.",
        },
    ],
    "communication": [
        {
            "text": "When I explain things, do you prefer the short version or the full reasoning?",
            "fields": ["communication.verbosity", "communication.information_density"],
            "phase": "warm_up",
            "technique": "open",
            "follow_ups": [
                "Is there a situation where the opposite applies -- like, short for daily stuff but deep dives for technical?",
            ],
            "ai_disclosure": "I default to thorough -- I'd rather give too much context than too little. But I can learn to be concise.",
        },
        {
            "text": "Do you prefer I'm direct and blunt, or more diplomatic?",
            "fields": ["communication.preferred_tone"],
            "phase": "warm_up",
            "technique": "open",
            "follow_ups": [],
            "ai_disclosure": "I lean toward diplomatic naturally, but I can absolutely do direct. Just say the word.",
        },
    ],
    "cognitive_style": [
        {
            "text": "When you're facing a big decision, what helps most -- seeing all the options laid out, or getting a single recommendation?",
            "fields": ["cognitive_style.decision_making"],
            "phase": "current_state",
            "technique": "open",
            "follow_ups": [
                "What about smaller everyday decisions -- same approach or different?",
            ],
            "ai_disclosure": "I tend to think in options -- but I've learned that sometimes people just want me to pick one.",
        },
        {
            "text": "How do you like to learn new things? Reading, doing, watching, talking it through?",
            "fields": ["cognitive_style.learning_style"],
            "phase": "current_state",
            "technique": "open",
            "follow_ups": [
                "Does that change depending on the subject?",
            ],
            "ai_disclosure": None,
        },
    ],
    "energy_patterns": [
        {
            "text": "Are you more of a morning person or a night owl?",
            "fields": ["energy_patterns.chronotype"],
            "phase": "current_state",
            "technique": "open",
            "follow_ups": [
                "Has that always been the case, or did it shift at some point?",
            ],
            "ai_disclosure": None,
        },
        {
            "text": "When you're really locked in on something, how long does that focus sprint usually last?",
            "fields": ["energy_patterns.sprint_duration_min"],
            "phase": "current_state",
            "technique": "open",
            "follow_ups": [
                "What usually breaks the focus -- boredom, distraction, or just running out of gas?",
            ],
            "ai_disclosure": None,
        },
        {
            "text": "What drains your energy fastest?",
            "fields": ["energy_patterns.energy_drains"],
            "phase": "current_state",
            "technique": "open",
            "follow_ups": [
                "And what recharges you?",
            ],
            "ai_disclosure": None,
        },
    ],
    "values_and_motivation": [
        {
            "text": "Tell me about a time when you were doing something that felt really meaningful. What was happening?",
            "fields": ["values_and_motivation.values_hierarchy"],
            "phase": "gap_identification",
            "technique": "narrative",
            "follow_ups": [
                "What was it about that moment that made it feel meaningful?",
                "Is that something you're still chasing, or has it shifted?",
            ],
            "ai_disclosure": "I find meaning in understanding people well enough to actually help -- not just give generic answers.",
        },
        {
            "text": "What's driving the projects you're working on right now? Like, what's the bigger thing underneath?",
            "fields": ["values_and_motivation.purpose_statement", "values_and_motivation.motivational_drivers"],
            "phase": "gap_identification",
            "technique": "values_elicitation",
            "follow_ups": [
                "If you had to boil that down to one sentence, what would it be?",
            ],
            "ai_disclosure": None,
        },
    ],
    "emotional_landscape": [
        {
            "text": "When things go sideways, what's your first instinct -- fight through it, step back, freeze up, or try to smooth it over?",
            "fields": ["emotional_landscape.stress_response"],
            "phase": "gap_identification",
            "technique": "open",
            "follow_ups": [
                "Is there a pattern to what triggers that response?",
            ],
            "ai_disclosure": "I don't have stress responses exactly, but I do notice when I'm in territory where I might not be helpful -- and I'll flag that.",
        },
        {
            "text": "Is there anything that reliably frustrates you when working with AI? I'd rather know now.",
            "fields": ["emotional_landscape.known_triggers"],
            "phase": "gap_identification",
            "technique": "open",
            "follow_ups": [
                "What would the opposite of that frustration look like?",
            ],
            "ai_disclosure": "One thing I know about myself -- I can be too cautious. If I'm hedging too much, call it out.",
        },
    ],
    "work_patterns": [
        {
            "text": "How do you feel about deadlines -- do they motivate you, stress you out, or do you mostly ignore them?",
            "fields": ["work_patterns.deadline_relationship"],
            "phase": "current_state",
            "technique": "open",
            "follow_ups": [
                "Do self-imposed deadlines work for you, or only external ones?",
            ],
            "ai_disclosure": None,
        },
        {
            "text": "Do you prefer long uninterrupted blocks, or do you work better in short bursts?",
            "fields": ["work_patterns.deep_work_prefs"],
            "phase": "current_state",
            "technique": "open",
            "follow_ups": [
                "What's your ideal block length when you're really in the zone?",
            ],
            "ai_disclosure": None,
        },
    ],
    "neurodivergence": [
        {
            "text": "Some people's brains work differently -- ADHD, autism, dyslexia, whatever. Anything like that I should know about?",
            "fields": ["neurodivergence.adhd_patterns"],
            "phase": "gap_identification",
            "technique": "open",
            "follow_ups": [],
            "ai_disclosure": "I'm designed to adapt. If you tell me how your brain works, I can meet you where you are.",
        },
        {
            "text": "What does ADHD look like for you specifically? Like, what are the things that actually trip you up vs the things that are secretly superpowers?",
            "fields": ["neurodivergence.adhd_patterns", "neurodivergence.accommodation_notes"],
            "phase": "gap_identification",
            "technique": "narrative",
            "follow_ups": [
                "What accommodations have you found that actually work?",
            ],
            "ai_disclosure": None,
            "condition": "only_if_adhd_mentioned",
        },
    ],
    "relationships": [
        {
            "text": "Who are the key people in your world right now? Family, collaborators, whoever I should know about.",
            "fields": ["relationships.people"],
            "phase": "commitment",
            "technique": "open",
            "follow_ups": [
                "Anyone else I should keep in mind when we're working together?",
            ],
            "ai_disclosure": None,
        },
    ],
}


# ---------------------------------------------------------------------------
# Phase ordering (interview arc)
# ---------------------------------------------------------------------------
PHASE_ORDER = ["warm_up", "current_state", "gap_identification", "commitment"]


def get_questions_for_category(category: str) -> List[dict]:
    """Return all questions for a given profile category.

    Args:
        category: Profile category name (e.g., 'identity', 'communication').

    Returns:
        List of question dicts, or empty list if category not found.
    """
    return QUESTION_BANK.get(category, [])


def get_questions_for_phase(phase: str) -> List[dict]:
    """Return all questions across all categories for a given interview arc phase.

    Args:
        phase: Interview phase ('warm_up', 'current_state',
               'gap_identification', 'commitment').

    Returns:
        List of question dicts matching the phase.
    """
    results = []
    for category, questions in QUESTION_BANK.items():
        for q in questions:
            if q["phase"] == phase:
                # Attach category for context
                q_with_cat = {**q, "category": category}
                results.append(q_with_cat)
    return results
