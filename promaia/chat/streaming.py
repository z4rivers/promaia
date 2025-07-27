"""
Streaming chat interface with multi-turn feedback loops for MCP tool execution.

This module provides real-time text streaming like Cursor/Claude and implements
chain-of-thought functionality where tool results are fed back to the AI.
"""
import sys
import time
import asyncio
import logging
from typing import Dict, List, Optional, Any, Iterator, Tuple
from promaia.utils.display import print_text

logger = logging.getLogger(__name__)

class StreamingResponseHandler:
    """Handles streaming responses from AI APIs with MCP tool integration."""
    
    def __init__(self, mcp_executor=None):
        """Initialize the streaming handler.
        
        Args:
            mcp_executor: MCP tool executor for handling tool calls
        """
        self.mcp_executor = mcp_executor
        self.accumulated_text = ""
        self.tool_calls_found = []
        
    async def stream_response_with_tools(self, api_client, api_type: str, system_prompt: str, 
                                       messages: List[Dict], max_turns: int = 3) -> Tuple[str, List[Dict]]:
        """Stream AI response and handle multi-turn tool execution.
        
        Args:
            api_client: The AI API client (anthropic, openai, etc.)
            api_type: Type of API ('anthropic', 'openai', 'gemini')
            system_prompt: System prompt for the AI
            messages: Conversation messages
            max_turns: Maximum number of feedback turns
            
        Returns:
            Tuple of (final_response_text, updated_messages)
        """
        all_responses = []
        current_messages = messages.copy()
        
        for turn in range(max_turns):
            print_text(f"\n🤖 AI Turn {turn + 1}:", style="dim cyan")
            
            # Stream the AI response
            response_text, tool_calls = await self._stream_single_response(
                api_client, api_type, system_prompt, current_messages
            )
            
            all_responses.append(response_text)
            current_messages.append({"role": "assistant", "content": response_text})
            
            # If no tool calls found, we're done
            if not tool_calls:
                break
                
            # Execute tools and get results
            print_text(f"\n🔧 Executing {len(tool_calls)} tool call(s)...", style="bold cyan")
            
            tool_results = await self.mcp_executor.execute_tool_calls(tool_calls)
            results_text = self.mcp_executor.format_tool_results(tool_results)
            
            print_text(results_text, style="dim green")
            
            # Feed tool results back to AI for next turn
            tool_feedback = f"Tool execution results:\n{results_text}\n\nBased on these results, please continue or complete the task."
            current_messages.append({"role": "user", "content": tool_feedback})
            
            # Check if we should continue (simple heuristic)
            if self._should_stop_execution(tool_results):
                print_text("🎯 Task completed successfully.", style="bold green")
                break
        
        # Combine all responses
        final_response = "\n".join(all_responses)
        return final_response, current_messages
    
    async def _stream_single_response(self, api_client, api_type: str, system_prompt: str, 
                                    messages: List[Dict]) -> Tuple[str, List[Dict]]:
        """Stream a single AI response and parse for tool calls.
        
        Returns:
            Tuple of (response_text, parsed_tool_calls)
        """
        self.accumulated_text = ""
        self.tool_calls_found = []
        
        if api_type == "anthropic":
            await self._stream_anthropic(api_client, system_prompt, messages)
        elif api_type == "openai":
            await self._stream_openai(api_client, system_prompt, messages)
        elif api_type == "gemini":
            await self._stream_gemini(api_client, system_prompt, messages)
        else:
            # Fallback to non-streaming
            self.accumulated_text = "Streaming not supported for this API."
        
        # Parse tool calls from accumulated text
        if self.mcp_executor:
            tool_calls = self.mcp_executor.parse_tool_calls(self.accumulated_text)
        else:
            tool_calls = []
            
        return self.accumulated_text, tool_calls
    
    async def _stream_anthropic(self, client, system_prompt: str, messages: List[Dict]):
        """Stream Anthropic response."""
        try:
            stream = client.messages.stream(
                model="claude-3-sonnet-20240229",
                system=system_prompt,
                messages=messages,
                max_tokens=4000,
                temperature=0.7,
            )
            
            with stream as stream_context:
                for text in stream_context.text_stream:
                    self.accumulated_text += text
                    # Stream to terminal character by character for effect
                    sys.stdout.write(text)
                    sys.stdout.flush()
                    await asyncio.sleep(0.01)  # Small delay for smooth streaming
                    
        except Exception as e:
            error_text = f"Error streaming from Anthropic: {e}"
            self.accumulated_text = error_text
            print_text(error_text, style="bold red")
    
    async def _stream_openai(self, client, system_prompt: str, messages: List[Dict]):
        """Stream OpenAI response."""
        try:
            # Prepare messages with system prompt
            api_messages = [{"role": "system", "content": system_prompt}] + messages
            
            stream = client.chat.completions.create(
                model="gpt-4",
                messages=api_messages,
                stream=True,
                temperature=0.7,
                max_tokens=4000
            )
            
            for chunk in stream:
                if chunk.choices[0].delta.content is not None:
                    text = chunk.choices[0].delta.content
                    self.accumulated_text += text
                    # Stream to terminal
                    sys.stdout.write(text)
                    sys.stdout.flush()
                    await asyncio.sleep(0.01)
                    
        except Exception as e:
            error_text = f"Error streaming from OpenAI: {e}"
            self.accumulated_text = error_text
            print_text(error_text, style="bold red")
    
    async def _stream_gemini(self, client, system_prompt: str, messages: List[Dict]):
        """Stream Gemini response (fallback to non-streaming since Gemini streaming is complex)."""
        try:
            formatted_prompt = f"System: {system_prompt}\n\nConversation:\n"
            for msg in messages:
                formatted_prompt += f"{msg['role'].title()}: {msg['content']}\n"
            
            response = client.generate_content(formatted_prompt)
            if response.text:
                # Simulate streaming for consistent UX
                for char in response.text:
                    self.accumulated_text += char
                    sys.stdout.write(char)
                    sys.stdout.flush()
                    await asyncio.sleep(0.005)  # Faster for simulated streaming
            else:
                self.accumulated_text = "No response generated from Gemini."
                
        except Exception as e:
            error_text = f"Error with Gemini: {e}"
            self.accumulated_text = error_text
            print_text(error_text, style="bold red")
    
    def _should_stop_execution(self, tool_results: List[Dict]) -> bool:
        """Determine if tool execution chain should stop.
        
        Args:
            tool_results: Results from tool execution
            
        Returns:
            True if execution should stop
        """
        # Simple heuristics for stopping:
        
        # 1. All tools succeeded and no complex operations
        all_success = all(result.get('success', False) for result in tool_results)
        
        # 2. Check for completion indicators in results
        completion_indicators = ['successfully', 'completed', 'created', 'saved', 'sent']
        has_completion = any(
            any(indicator in str(result.get('result', '')).lower() 
                for indicator in completion_indicators)
            for result in tool_results
        )
        
        # 3. No errors occurred
        no_errors = not any('error' in str(result).lower() for result in tool_results)
        
        return all_success and has_completion and no_errors


def create_streaming_handler(mcp_executor=None) -> StreamingResponseHandler:
    """Create a streaming response handler.
    
    Args:
        mcp_executor: Optional MCP executor for tool handling
        
    Returns:
        Configured streaming handler
    """
    return StreamingResponseHandler(mcp_executor) 