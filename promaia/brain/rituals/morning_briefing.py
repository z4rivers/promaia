"""
The Morning Briefing: automated ritual to summarize the previous day's Campfire snapshots.
Ensures Zack starts the day with a clear view of all agent activities.
"""
import asyncio
import logging
from datetime import datetime, timedelta
from promaia.brain.campfire import get_latest_snapshots
from promaia.telegram.conversation import _get_genai_client
from promaia.ai.models import GOOGLE_MODELS
from google.genai import types

logger = logging.getLogger(__name__)

async def generate_morning_briefing() -> str:
    """
    Gathers snapshots from the last 24 hours and synthesizes them into a briefing.
    """
    # 1. Gather snapshots from the last 24 hours
    # (In a real implementation, we'd filter by timestamp, but for now we'll take the latest 10)
    snapshots = await get_latest_snapshots(limit=10)
    
    if not snapshots:
        return "No significant agent activity recorded in the last 24 hours. A fresh start!"

    # 2. Format snapshots for the prompt
    snapshot_texts = []
    for s in snapshots:
        snapshot_texts.append(
            f"Agent: {s['agent']}\n"
            f"Summary: {s['summary']}\n"
            f"Topics: {s['topics']}\n"
            f"Decisions: {s['decisions']}\n"
            f"Next Steps: {s['next_steps']}\n"
            f"---"
        )
    
    context_text = "\n".join(snapshot_texts)
    
    # 3. Synthesize via Gemini
    try:
        client = _get_genai_client()
        prompt = (
            "You are Promaia, providing Zack's Morning Briefing. "
            "Synthesize the following session snapshots from the last 24 hours into a "
            "concise, high-impact briefing. Group by project if applicable. "
            "Focus on: What happened while he was away, key decisions made, and what needs his attention FIRST today.\n\n"
            "Keep it under 250 words. Be direct, substance-first, and maintain your signature sharp humor.\n\n"
            f"SNAPSHOTS:\n{context_text}"
        )
        
        response = await client.aio.models.generate_content(
            model=GOOGLE_MODELS["flash"],
            contents=prompt
        )
        
        briefing = response.text if response and response.text else "Briefing generation failed."
        
        # 4. Save the briefing itself to the Campfire (Phase 5 requirement)
        from promaia.brain.campfire import save_snapshot
        await save_snapshot(
            agent="morning-briefing",
            summary=briefing,
            status="complete",
            topics=["daily-briefing"]
        )
        
        return briefing
        
    except Exception as e:
        logger.error(f"Failed to generate morning briefing: {e}")
        return "The morning briefing engine encountered an error. Check the logs."

if __name__ == "__main__":
    # Test run
    logging.basicConfig(level=logging.INFO)
    loop = asyncio.get_event_loop()
    res = loop.run_until_complete(generate_morning_briefing())
    print(res)
