import asyncio
import logging
from promaia.web.brain_chat import chat

logging.basicConfig(level=logging.INFO)

async def test_chat():
    print("Sending message...")
    response = await chat("What are my current active projects? Could you summarize them based on what you just retrieved from MuninnDB?")
    print("-" * 50)
    print(f"PROMAIA: {response}")
    print("-" * 50)

if __name__ == "__main__":
    asyncio.run(test_chat())
