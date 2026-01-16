"""
Simple test for Claude Agent SDK integration.
"""

import asyncio
import logging
from promaia.agent.sdk_adapter_simple import PromaiaAgentClient

logging.basicConfig(level=logging.INFO)

async def main():
    print("Testing Agent SDK Integration...")
    print("-" * 60)

    # Create client
    client = PromaiaAgentClient(workspace="koii")

    # Initialize
    print("\nInitializing...")
    await client.initialize()
    print("✓ Initialized")

    # Send a simple message
    print("\nSending message...")
    response = await client.send_message("Hello! Can you tell me what tools you have access to?")

    print("\nResponse:")
    print(response)
    print("-" * 60)

if __name__ == "__main__":
    asyncio.run(main())
