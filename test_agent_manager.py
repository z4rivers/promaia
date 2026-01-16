"""
Test script for agent manager.
"""

import asyncio
import logging
from promaia.agent.agent_manager import AgentSession

logging.basicConfig(level=logging.INFO)

async def test_agent_spawn():
    """Test spawning an agent with sample context."""
    print("Testing Agent Manager")
    print("=" * 60)

    # Sample context
    test_context = {
        "koii.journal": [
            {
                "title": "2024-01-15 - Monday",
                "content": "Worked on API endpoints today.",
                "created_time": "2024-01-15T09:00:00Z"
            }
        ]
    }

    # Create session
    session = AgentSession(
        task="Tell me what you can see in the context",
        context=test_context,
        workspace="koii"
    )

    # Spawn agent
    print("\nSpawning agent...")
    success = await session.spawn()

    if success:
        print("✓ Agent spawned successfully")

        # Try to receive first message
        print("\nWaiting for agent response...")
        try:
            count = 0
            async for message in session.receive_messages():
                print(f"\n[{message.role}]: {message.content[:200]}")
                count += 1
                if count >= 3:  # Just get first few messages
                    break
        except Exception as e:
            print(f"Error: {e}")
            import traceback
            traceback.print_exc()

        # Cleanup
        await session.terminate()
        print("\n✓ Session terminated")
    else:
        print("✗ Failed to spawn agent")

if __name__ == "__main__":
    asyncio.run(test_agent_spawn())
