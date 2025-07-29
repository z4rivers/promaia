"""
MCP tool execution engine.

This module handles parsing tool calls from AI responses and executing them
via connected MCP servers, then formatting the results.
"""
import re
import json
import logging
from typing import Dict, List, Optional, Any, Tuple
from .client import McpClient

logger = logging.getLogger(__name__)

class McpToolExecutor:
    """Executes MCP tools called by the AI."""
    
    def __init__(self, mcp_client: McpClient):
        """Initialize with an MCP client.
        
        Args:
            mcp_client: Connected MCP client with available servers
        """
        self.mcp_client = mcp_client
    
    def parse_tool_calls(self, ai_response: str) -> List[Dict[str, Any]]:
        """Parse tool calls from AI response.
        
        Args:
            ai_response: The AI's response text
            
        Returns:
            List of tool call dictionaries with server, tool, and arguments
        """
        tool_calls = []
        
        # Pattern 1: <execute_tool>server.tool(args)</execute_tool>
        pattern1 = r'<execute_tool>\s*(\w+)\.([\w-]+)\s*\((.*?)\)\s*</execute_tool>'
        
        # Pattern 2: <tool_code>print(server.tool(args))</tool_code>
        pattern2 = r'<tool_code>\s*print\((\w+)\.([\w-]+)\s*\((.*?)\)\)\s*</tool_code>'
        
        # Pattern 3: <tool_code>server.tool(args)</tool_code>
        pattern3 = r'<tool_code>\s*(\w+)\.([\w-]+)\s*\((.*?)\)\s*</tool_code>'
        
        # Try all patterns
        for pattern in [pattern1, pattern2, pattern3]:
            matches = re.findall(pattern, ai_response, re.DOTALL)
            
            for match in matches:
                server_name, tool_name, args_str = match
                
                try:
                    # Parse arguments - handle both JSON and simple formats
                    arguments = self._parse_arguments(args_str)
                    
                    tool_calls.append({
                        'server': server_name,
                        'tool': tool_name,
                        'arguments': arguments,
                        'raw_args': args_str
                    })
                    
                except Exception as e:
                    logger.error(f"Error parsing tool call arguments: {e}")
                    logger.error(f"Raw arguments: {args_str}")
        
        return tool_calls
    
    def _parse_arguments(self, args_str: str) -> Dict[str, Any]:
        """Parse tool arguments from string.
        
        Args:
            args_str: Arguments string from the tool call
            
        Returns:
            Dictionary of parsed arguments
        """
        args_str = args_str.strip()
        
        if not args_str:
            return {}
        
        # Try JSON format first
        try:
            return json.loads(f"{{{args_str}}}")
        except:
            pass
        
        # Try Python-style arguments: key=value, key="value"
        arguments = {}
        
        # Split by commas, but respect quotes
        parts = self._split_arguments(args_str)
        
        for part in parts:
            part = part.strip()
            if '=' in part:
                key, value = part.split('=', 1)
                key = key.strip()
                value = value.strip()
                
                # Remove quotes if present
                if (value.startswith('"') and value.endswith('"')) or \
                   (value.startswith("'") and value.endswith("'")):
                    value = value[1:-1]
                
                arguments[key] = value
        
        return arguments
    
    def _split_arguments(self, args_str: str) -> List[str]:
        """Split arguments by comma, respecting quotes."""
        parts = []
        current_part = ""
        in_quotes = False
        quote_char = None
        
        for char in args_str:
            if char in ['"', "'"] and not in_quotes:
                in_quotes = True
                quote_char = char
                current_part += char
            elif char == quote_char and in_quotes:
                in_quotes = False
                quote_char = None
                current_part += char
            elif char == ',' and not in_quotes:
                if current_part.strip():
                    parts.append(current_part.strip())
                current_part = ""
            else:
                current_part += char
        
        if current_part.strip():
            parts.append(current_part.strip())
        
        return parts
    
    async def execute_tool_calls(self, tool_calls: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Execute a list of tool calls.
        
        Args:
            tool_calls: List of parsed tool calls
            
        Returns:
            List of execution results
        """
        results = []
        
        for tool_call in tool_calls:
            result = await self.execute_single_tool(tool_call)
            results.append(result)
        
        return results
    
    async def execute_single_tool(self, tool_call: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a single tool call.
        
        Args:
            tool_call: Tool call dictionary
            
        Returns:
            Execution result
        """
        server_name = tool_call['server']
        tool_name = tool_call['tool']
        arguments = tool_call['arguments']
        
        # Check if server is connected
        if not self.mcp_client.is_server_connected(server_name):
            return {
                'success': False,
                'error': f"Server '{server_name}' is not connected",
                'tool_call': tool_call
            }
        
        # Get the protocol client for this server
        protocol_client = self.mcp_client.connected_servers.get(server_name)
        
        if not protocol_client:
            return {
                'success': False,
                'error': f"No protocol client for server '{server_name}'",
                'tool_call': tool_call
            }
        
        try:
            logger.info(f"Executing {server_name}.{tool_name} with args: {arguments}")
            print(f"🔧 Executing {server_name}.{tool_name}...")
            
            # Execute the tool
            result = await protocol_client.call_tool(tool_name, arguments)
            
            if result:
                print(f"✅ Tool execution successful: {result}")
                return {
                    'success': True,
                    'result': result,
                    'tool_call': tool_call
                }
            else:
                print(f"❌ Tool execution returned no result")
                return {
                    'success': False,
                    'error': f"Tool execution returned no result",
                    'tool_call': tool_call
                }
        
        except Exception as e:
            logger.error(f"Error executing tool {server_name}.{tool_name}: {e}")
            return {
                'success': False,
                'error': str(e),
                'tool_call': tool_call
            }
    
    def format_tool_results(self, results: List[Dict[str, Any]]) -> str:
        """Format tool execution results for display.
        
        Args:
            results: List of execution results
            
        Returns:
            Formatted results string
        """
        if not results:
            print("🔍 No results to format")
            return ""
        
        print(f"🔍 Formatting {len(results)} results: {results}")
        formatted = "\n🔧 Tool Execution Results:\n"
        
        for i, result in enumerate(results, 1):
            tool_call = result['tool_call']
            server = tool_call['server']
            tool = tool_call['tool']
            
            if result['success']:
                formatted += f"\n✅ {server}.{tool}:\n"
                
                # Extract and format the actual result content
                result_data = result['result']
                if 'content' in result_data:
                    content = result_data['content']
                    if isinstance(content, list) and content:
                        # Take the first content item
                        first_content = content[0]
                        if isinstance(first_content, dict) and 'text' in first_content:
                            formatted += f"{first_content['text']}\n"
                        else:
                            formatted += f"{first_content}\n"
                    else:
                        formatted += f"{content}\n"
                else:
                    formatted += f"{result_data}\n"
            else:
                formatted += f"\n❌ {server}.{tool} failed:\n"
                formatted += f"Error: {result['error']}\n"
        
        return formatted
    
    def has_tool_calls(self, ai_response: str) -> bool:
        """Check if AI response contains tool calls.
        
        Args:
            ai_response: The AI's response text
            
        Returns:
            True if tool calls are present
        """
        return (('<execute_tool>' in ai_response and '</execute_tool>' in ai_response) or 
                ('<tool_code>' in ai_response and '</tool_code>' in ai_response)) 