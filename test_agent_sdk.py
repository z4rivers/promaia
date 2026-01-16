"""
Test script for Claude Agent SDK integration with Promaia.
"""

import asyncio
import logging
from promaia.agent import PromaiaAgentClient

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

async def test_basic_query():
    """Test basic query functionality with the Agent SDK."""
    print("=" * 60)
    print("Testing Promaia Agent SDK Integration")
    print("=" * 60)

    # Create client
    client = PromaiaAgentClient(workspace="koii")

    # Initialize (loads MCP servers, creates system prompt)
    print("\n[1] Initializing client...")
    await client.initialize()
    print("✓ Client initialized")

    # Test a simple query
    print("\n[2] Sending test query...")
    query = "What did I work on yesterday in my journal?"
    print(f"Query: {query}")

    response = await client.send_message(query)

    print("\n[3] Response:")
    print("-" * 60)
    print(response)
    print("-" * 60)

    # Check context state
    context = client.get_context_state()
    print("\n[4] Context State:")
    print(f"  - Total pages loaded: {context['total_pages_loaded']}")
    print(f"  - Databases accessed: {list(context['loaded_content'].keys())}")
    print(f"  - AI queries made: {len(context['ai_queries'])}")

    for i, query_info in enumerate(context['ai_queries'], 1):
        print(f"\n  Query {i}:")
        print(f"    Tool: {query_info['tool']}")
        print(f"    Query: {query_info['query']}")
        print(f"    Pages: {query_info['pages_loaded']}")

async def test_streaming():
    """Test streaming responses."""
    print("\n" + "=" * 60)
    print("Testing Streaming Responses")
    print("=" * 60)

    client = PromaiaAgentClient(workspace="koii")
    await client.initialize()

    query = "List my recent journal entries"
    print(f"\nQuery: {query}")
    print("\nStreaming response:")
    print("-" * 60)

    async for message in client.send_message_streaming(query):
        if message.type == "content":
            print(message.content, end="", flush=True)
        elif message.type == "tool_use":
            print(f"\n[Using tool: {message.tool_name}]", flush=True)

    print("\n" + "-" * 60)

async def main():
    """Run all tests."""
    try:
        # Test 1: Basic query
        await test_basic_query()

        # Test 2: Streaming
        # await test_streaming()  # Uncomment to test streaming

        print("\n" + "=" * 60)
        print("All tests completed!")
        print("=" * 60)

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
