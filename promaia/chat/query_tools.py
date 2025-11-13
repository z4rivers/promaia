"""
Query tool execution engine.

This module handles parsing query tool calls from AI responses and executing them
to load additional context into the chat session.
"""
import re
import xml.etree.ElementTree as ET
import json
import logging
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any
from promaia.ai.nl_processor_wrapper import process_natural_language_to_content, process_vector_search_to_content
from promaia.storage.files import load_database_pages_with_filters
from promaia.utils.config_utils import get_database_config

logger = logging.getLogger(__name__)


class QueryToolExecutor:
    """Executes built-in query tools called by the AI."""

    QUERY_TOOLS = {'query_sql', 'query_vector', 'query_source'}

    def __init__(self, context_state: Dict[str, Any]):
        """Initialize with context state.

        Args:
            context_state: Current chat session context state
        """
        self.context_state = context_state

    def has_query_tool_calls(self, ai_response: str) -> bool:
        """Check if AI response contains query tool calls.

        Args:
            ai_response: The AI's response text

        Returns:
            True if query tool calls are present
        """
        if '<tool_call>' not in ai_response or '</tool_call>' not in ai_response:
            return False

        # Check if it contains query tool names
        for tool_name in self.QUERY_TOOLS:
            if f'<tool_name>{tool_name}</tool_name>' in ai_response:
                return True

        return False

    def parse_query_tool_calls(self, ai_response: str) -> List[Dict[str, Any]]:
        """Parse query tool calls from AI response.

        Format:
        <tool_call>
          <tool_name>query_sql</tool_name>
          <parameters>
            <query>find emails from Federico</query>
            <workspace>default</workspace>
          </parameters>
        </tool_call>

        Args:
            ai_response: The AI's response text

        Returns:
            List of tool call dictionaries with tool name and parameters
        """
        tool_calls = []

        # Pattern: <tool_call>...</tool_call>
        tool_call_pattern = r'<tool_call>(.*?)</tool_call>'
        matches = re.findall(tool_call_pattern, ai_response, re.DOTALL)

        for match in matches:
            try:
                # Extract tool name
                tool_name_match = re.search(r'<tool_name>(.*?)</tool_name>', match, re.DOTALL)
                if not tool_name_match:
                    logger.warning("Tool call missing <tool_name> tag")
                    continue

                tool_name = tool_name_match.group(1).strip()

                # Only process query tools
                if tool_name not in self.QUERY_TOOLS:
                    logger.debug(f"Skipping non-query tool: {tool_name}")
                    continue

                # Extract parameters
                parameters = {}
                parameters_match = re.search(r'<parameters>(.*?)</parameters>', match, re.DOTALL)

                if parameters_match:
                    params_content = parameters_match.group(1)

                    # Extract individual parameter tags
                    param_pattern = r'<(\w+)>(.*?)</\1>'
                    param_matches = re.findall(param_pattern, params_content, re.DOTALL)

                    for param_name, param_value in param_matches:
                        param_value = param_value.strip()

                        # Try to parse as JSON for complex types
                        if param_value.startswith(('{', '[')):
                            try:
                                parameters[param_name] = json.loads(param_value)
                            except json.JSONDecodeError:
                                parameters[param_name] = param_value
                        # Parse numbers
                        elif param_value.replace('.', '').replace('-', '').isdigit():
                            try:
                                if '.' in param_value:
                                    parameters[param_name] = float(param_value)
                                else:
                                    parameters[param_name] = int(param_value)
                            except ValueError:
                                parameters[param_name] = param_value
                        else:
                            parameters[param_name] = param_value

                tool_calls.append({
                    'tool_name': tool_name,
                    'parameters': parameters,
                    'raw_content': match
                })

            except Exception as e:
                logger.error(f"Error parsing query tool call: {e}")
                continue

        return tool_calls

    async def execute_query_tool_calls(self, tool_calls: List[Dict[str, Any]], request_permission_callback) -> List[Dict[str, Any]]:
        """Execute a list of query tool calls with user permission.

        Args:
            tool_calls: List of parsed query tool calls
            request_permission_callback: Async function to request user permission
                                        Should return ('approved', query) or ('declined', None) or ('modified', new_query)

        Returns:
            List of execution results with loaded content
        """
        results = []

        for tool_call in tool_calls:
            result = await self.execute_single_query_tool(tool_call, request_permission_callback)
            results.append(result)

        return results

    async def execute_single_query_tool(self, tool_call: Dict[str, Any], request_permission_callback) -> Dict[str, Any]:
        """Execute a single query tool call.

        Args:
            tool_call: Tool call dictionary
            request_permission_callback: Function to request user permission

        Returns:
            Execution result with loaded content
        """
        tool_name = tool_call['tool_name']
        parameters = tool_call['parameters']

        try:
            # Request user permission
            permission_result = await request_permission_callback(tool_name, parameters)

            if permission_result[0] == 'declined':
                return {
                    'success': False,
                    'declined': True,
                    'tool_call': tool_call,
                    'message': 'User declined the query'
                }

            # Handle modified query
            if permission_result[0] == 'modified':
                parameters = permission_result[1]

            # Execute the appropriate query tool
            if tool_name == 'query_sql':
                result = await self._execute_query_sql(parameters)
            elif tool_name == 'query_vector':
                result = await self._execute_query_vector(parameters)
            elif tool_name == 'query_source':
                result = await self._execute_query_source(parameters)
            else:
                return {
                    'success': False,
                    'error': f"Unknown query tool: {tool_name}",
                    'tool_call': tool_call
                }

            # Add query to context state
            if result['success']:
                query_id = str(uuid.uuid4())
                self.context_state['ai_queries'].append({
                    'id': query_id,
                    'type': tool_name,
                    'query': parameters.get('query', parameters.get('source', '')),
                    'params': parameters,
                    'timestamp': datetime.now().isoformat()
                })
                result['query_id'] = query_id

            return result

        except Exception as e:
            logger.error(f"Error executing query tool {tool_name}: {e}")
            return {
                'success': False,
                'error': str(e),
                'tool_call': tool_call
            }

    async def _execute_query_sql(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a SQL natural language query.

        Args:
            parameters: Query parameters including 'query', optional 'workspace', 'max_results'

        Returns:
            Result with loaded content
        """
        query = parameters.get('query')
        if not query:
            return {
                'success': False,
                'error': 'Missing required parameter: query'
            }

        workspace = parameters.get('workspace', self.context_state.get('workspace'))
        max_results = parameters.get('max_results')

        try:
            # Process natural language query
            loaded_content = process_natural_language_to_content(
                nl_prompt=query,
                workspace=workspace,
                verbose=False
            )

            # Count total pages
            total_pages = sum(len(pages) for pages in loaded_content.values())

            return {
                'success': True,
                'loaded_content': loaded_content,
                'total_pages': total_pages,
                'databases': list(loaded_content.keys()),
                'query': query,
                'workspace': workspace
            }

        except Exception as e:
            return {
                'success': False,
                'error': f"SQL query failed: {str(e)}"
            }

    async def _execute_query_vector(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a vector semantic search query.

        Args:
            parameters: Query parameters including 'query', optional 'workspace', 'top_k', 'min_similarity'

        Returns:
            Result with loaded content
        """
        query = parameters.get('query')
        if not query:
            return {
                'success': False,
                'error': 'Missing required parameter: query'
            }

        workspace = parameters.get('workspace', self.context_state.get('workspace'))
        top_k = parameters.get('top_k', self.context_state.get('top_k', 20))
        min_similarity = parameters.get('min_similarity', self.context_state.get('threshold', 0.75))

        try:
            # Process vector search query
            loaded_content = process_vector_search_to_content(
                vs_prompt=query,
                workspace=workspace,
                top_k=top_k,
                threshold=min_similarity,
                verbose=False
            )

            # Count total pages
            total_pages = sum(len(pages) for pages in loaded_content.values())

            return {
                'success': True,
                'loaded_content': loaded_content,
                'total_pages': total_pages,
                'databases': list(loaded_content.keys()),
                'query': query,
                'workspace': workspace,
                'top_k': top_k,
                'min_similarity': min_similarity
            }

        except Exception as e:
            return {
                'success': False,
                'error': f"Vector search failed: {str(e)}"
            }

    async def _execute_query_source(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a direct source query.

        Args:
            parameters: Query parameters including 'source' (format: "database:days"),
                       optional 'workspace', 'filters'

        Returns:
            Result with loaded content
        """
        source = parameters.get('source')
        if not source:
            return {
                'success': False,
                'error': 'Missing required parameter: source'
            }

        workspace = parameters.get('workspace', self.context_state.get('workspace'))
        filters = parameters.get('filters', {})

        try:
            # Parse source format: "database:days" or "database"
            if ':' in source:
                database_name, days_str = source.split(':', 1)
                days = int(days_str) if days_str != 'all' else None
            else:
                database_name = source
                days = None

            # Get database config
            database_config = get_database_config(database_name, workspace)
            if not database_config:
                return {
                    'success': False,
                    'error': f"Database '{database_name}' not found in workspace '{workspace}'"
                }

            # Load pages from source
            pages = load_database_pages_with_filters(
                database_config=database_config,
                days=days,
                property_filters=filters if filters else None
            )

            # Format as multi_source_data
            loaded_content = {database_name: pages}

            return {
                'success': True,
                'loaded_content': loaded_content,
                'total_pages': len(pages),
                'databases': [database_name],
                'source': source,
                'workspace': workspace
            }

        except Exception as e:
            return {
                'success': False,
                'error': f"Source query failed: {str(e)}"
            }

    def format_query_results(self, results: List[Dict[str, Any]]) -> str:
        """Format query tool execution results for display.

        Args:
            results: List of execution results

        Returns:
            Formatted results string
        """
        formatted = "\n📊 Query Tool Results:\n\n"

        for i, result in enumerate(results, 1):
            if result.get('declined'):
                formatted += f"{i}. Query declined by user\n"
                continue

            if result.get('success'):
                tool_call = result.get('tool_call', {})
                tool_name = tool_call.get('tool_name', 'unknown')

                formatted += f"{i}. ✅ {tool_name}: "
                formatted += f"Loaded {result.get('total_pages', 0)} pages "
                formatted += f"from {', '.join(result.get('databases', []))}\n"

                if 'query' in result:
                    formatted += f"   Query: \"{result['query']}\"\n"
                elif 'source' in result:
                    formatted += f"   Source: {result['source']}\n"
            else:
                formatted += f"{i}. ❌ Query failed: {result.get('error', 'Unknown error')}\n"

        return formatted
