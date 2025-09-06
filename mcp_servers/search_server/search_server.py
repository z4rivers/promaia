#!/usr/bin/env python3
"""
Internet Search MCP Server

A simple MCP server that provides internet search capabilities using DuckDuckGo.
"""

import asyncio
import json
import logging
import sys
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SearchServer:
    """MCP server for internet search functionality."""

    def __init__(self):
        self.tools = [
            {
                "name": "web_search",
                "description": "Search the internet for information using DuckDuckGo",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "The search query to perform"
                        },
                        "max_results": {
                            "type": "integer",
                            "description": "Maximum number of results to return (default: 5)",
                            "default": 5
                        }
                    },
                    "required": ["query"]
                }
            }
        ]

    def search_duckduckgo(self, query: str, max_results: int = 5) -> Dict[str, Any]:
        """Perform a search using DuckDuckGo's instant answer API."""
        try:
            # Encode the query
            encoded_query = urllib.parse.quote(query)

            # DuckDuckGo instant answer API
            url = f"https://api.duckduckgo.com/?q={encoded_query}&format=json&no_html=1"

            # Make the request
            with urllib.request.urlopen(url, timeout=10) as response:
                data = json.loads(response.read().decode('utf-8'))

            results = []

            # Extract instant answer if available
            if data.get('Answer'):
                results.append({
                    "title": "Instant Answer",
                    "description": data['Answer'],
                    "url": f"https://duckduckgo.com/?q={encoded_query}",
                    "source": "DuckDuckGo Instant Answer"
                })

            # Extract abstract if available
            if data.get('AbstractText'):
                results.append({
                    "title": data.get('Heading', 'Abstract'),
                    "description": data['AbstractText'],
                    "url": data.get('AbstractURL', f"https://duckduckgo.com/?q={encoded_query}"),
                    "source": data.get('AbstractSource', 'DuckDuckGo')
                })

            # Extract related topics
            if data.get('RelatedTopics'):
                for topic in data['RelatedTopics'][:max_results - len(results)]:
                    if isinstance(topic, dict) and 'Text' in topic:
                        results.append({
                            "title": topic.get('FirstURL', topic.get('Text', ''))[:50],
                            "description": topic['Text'],
                            "url": f"https://duckduckgo.com/?q={encoded_query}",
                            "source": "DuckDuckGo Related Topics"
                        })

            # If no results, provide a fallback
            if not results:
                results.append({
                    "title": f"Search Results for: {query}",
                    "description": f"No specific results found. Try refining your search query or visit: https://duckduckgo.com/?q={encoded_query}",
                    "url": f"https://duckduckgo.com/?q={encoded_query}",
                    "source": "DuckDuckGo"
                })

            return {
                "query": query,
                "results": results[:max_results],
                "total_found": len(results)
            }

        except Exception as e:
            logger.error(f"Search error: {e}")
            return {
                "query": query,
                "error": f"Search failed: {str(e)}",
                "results": [{
                    "title": "Search Error",
                    "description": f"Unable to perform search: {str(e)}. Try a different search query.",
                    "url": f"https://duckduckgo.com/?q={urllib.parse.quote(query)}",
                    "source": "Error"
                }]
            }

    def handle_initialize(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle initialization request."""
        return {
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {
                        "listChanged": False
                    }
                },
                "serverInfo": {
                    "name": "internet-search",
                    "version": "1.0.0"
                }
            }
        }

    def handle_tools_list(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle tools list request."""
        return {
            "result": {
                "tools": self.tools
            }
        }

    def handle_tools_call(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle tool call request."""
        tool_name = params.get("name")
        tool_args = params.get("arguments", {})

        if tool_name == "web_search":
            query = tool_args.get("query", "")
            max_results = tool_args.get("max_results", 5)

            search_results = self.search_duckduckgo(query, max_results)

            # Format results for MCP response
            content = []

            if "error" in search_results:
                content.append({
                    "type": "text",
                    "text": f"❌ Search Error: {search_results['error']}"
                })
            else:
                content.append({
                    "type": "text",
                    "text": f"🔍 Search Results for: '{query}'\n"
                })

                for i, result in enumerate(search_results.get("results", []), 1):
                    content.append({
                        "type": "text",
                        "text": f"\n{i}. **{result['title']}**\n"
                               f"   {result['description']}\n"
                               f"   Source: {result['source']}\n"
                               f"   URL: {result['url']}\n"
                    })

                content.append({
                    "type": "text",
                    "text": f"\n📊 Total results shown: {len(search_results.get('results', []))}"
                })

                return {
                    "result": {
                        "content": content
                    }
                }

        return {
            "result": {
                "content": [{
                    "type": "text",
                    "text": f"Unknown tool: {tool_name}"
                }],
                "isError": True
            }
        }

    async def run(self):
        """Run the MCP server."""
        logger.info("Internet Search MCP Server starting...")

        try:
            # Read messages from stdin
            for line in sys.stdin:
                try:
                    message = json.loads(line.strip())
                    logger.info(f"Received message: {message.get('method', 'unknown')}")

                    # Handle different message types
                    if message.get("method") == "initialize":
                        response = self.handle_initialize(message.get("params", {}))
                        response["jsonrpc"] = "2.0"
                        response["id"] = message.get("id")

                    elif message.get("method") == "tools/list":
                        response = self.handle_tools_list(message.get("params", {}))
                        response["jsonrpc"] = "2.0"
                        response["id"] = message.get("id")

                    elif message.get("method") == "tools/call":
                        response = self.handle_tools_call(message.get("params", {}))
                        response["jsonrpc"] = "2.0"
                        response["id"] = message.get("id")

                    else:
                        response = {
                            "jsonrpc": "2.0",
                            "id": message.get("id"),
                            "error": {
                                "code": -32601,
                                "message": f"Method not found: {message.get('method')}"
                            }
                        }

                    # Send response
                    print(json.dumps(response), flush=True)

                except json.JSONDecodeError as e:
                    logger.error(f"Invalid JSON received: {e}")
                    continue

        except KeyboardInterrupt:
            logger.info("Server shutting down...")
        except Exception as e:
            logger.error(f"Server error: {e}")

def main():
    """Main entry point."""
    server = SearchServer()
    asyncio.run(server.run())

if __name__ == "__main__":
    main()
