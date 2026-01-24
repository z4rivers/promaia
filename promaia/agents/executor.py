"""
Agent Executor - Runs scheduled agents with multi-step query capability.
"""
import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from pathlib import Path

from promaia.agents.agent_config import AgentConfig, update_agent_last_run
from promaia.agents.execution_tracker import ExecutionTracker
from promaia.agents.notion_writer import NotionOutputWriter
from promaia.storage.files import load_database_pages_with_filters
from promaia.chat.query_tools import QueryToolExecutor
from promaia.ai.prompts import format_context_data
from promaia.ai.nl_orchestrator import PromaiLLMAdapter
from promaia.config.databases import get_database_config

logger = logging.getLogger(__name__)


class AgentExecutor:
    """
    Executes scheduled agents with multi-step query capability.

    This executor:
    1. Loads context from specified databases
    2. Creates a prompt with custom agent instructions
    3. Allows AI to make multiple query tool calls iteratively
    4. Writes results to Notion
    5. Tracks execution metrics
    """

    def __init__(self, agent_config: AgentConfig):
        """
        Initialize the executor.

        Args:
            agent_config: The agent configuration
        """
        self.config = agent_config
        self.tracker = ExecutionTracker()
        self.notion_writer = NotionOutputWriter(workspace=agent_config.workspace)

    async def execute(self) -> Dict[str, Any]:
        """
        Execute the agent.

        Returns:
            Execution result with status, metrics, and output
        """
        execution_id = None
        start_time = datetime.now(timezone.utc)

        try:
            # Load fresh config from Notion if available
            if self.config.notion_page_id and self.config.agent_id:
                from promaia.agents.notion_config import load_agent_by_id
                notion_agent = await load_agent_by_id(self.config.agent_id, self.config.workspace)
                if notion_agent:
                    self.config = notion_agent
                    logger.info(f"Loaded System Prompt from Notion for '{self.config.name}'")

            # Start tracking execution
            execution_id = self.tracker.start_execution(self.config.name)
            logger.info(f"🤖 Starting agent '{self.config.name}' (execution {execution_id})")

            # Step 1: Load initial context
            logger.info(f"📚 Loading context from {len(self.config.databases)} source(s)...")
            initial_context = await self._load_initial_context()

            if not initial_context:
                logger.warning("No context data loaded")

            # Step 2: Load custom prompt
            custom_prompt = self._load_custom_prompt()

            # Step 3: Create full prompt with context
            full_prompt = self._create_agent_prompt(custom_prompt, initial_context)

            # Step 4: Execute agent with iteration loop
            result = await self._execute_with_iterations(full_prompt, initial_context)

            # Step 5: Write results to Notion
            if result.get('output'):
                success = await self._write_to_notion(result['output'])
                result['notion_written'] = success
            else:
                result['notion_written'] = False

            # Step 6: Calculate metrics
            end_time = datetime.now(timezone.utc)
            duration = (end_time - start_time).total_seconds()

            metrics = {
                'iterations_used': result.get('iterations_used', 0),
                'tokens_used': result.get('tokens_used', 0),
                'cost_estimate': result.get('cost_estimate', 0.0),
                'duration_seconds': duration
            }

            # Complete execution tracking
            self.tracker.complete_execution(
                execution_id=execution_id,
                status='completed',
                iterations_used=metrics['iterations_used'],
                tokens_used=metrics['tokens_used'],
                cost_estimate=metrics['cost_estimate'],
                output_notion_page_id=self.config.output_notion_page_id,
                context_summary=f"Processed {len(initial_context)} context items"
            )

            # Update agent's last run time
            timestamp = datetime.now(timezone.utc).isoformat()
            update_agent_last_run(self.config.name, timestamp)

            # Write to Notion journal and update Last Run
            if self.config.notion_page_id and self.config.agent_id:
                try:
                    from promaia.agents.notion_journal import write_journal_entry
                    from promaia.agents.notion_config import update_last_run

                    # Write journal entry
                    journal_content = (
                        f"Executed successfully\n"
                        f"Duration: {metrics['duration_seconds']:.1f}s\n"
                        f"Iterations: {metrics['iterations_used']}\n"
                        f"Tokens: {metrics['tokens_used']}\n"
                        f"Cost: ${metrics['cost_estimate']:.4f}"
                    )

                    await write_journal_entry(
                        agent_id=self.config.agent_id,
                        workspace=self.config.workspace,
                        entry_type="Execution",
                        content=journal_content,
                        execution_id=execution_id
                    )

                    # Update Last Run in Notion
                    await update_last_run(
                        agent_id=self.config.agent_id,
                        workspace=self.config.workspace,
                        timestamp=timestamp
                    )

                except Exception as e:
                    logger.warning(f"Could not write to Notion journal: {e}")

            logger.info(f"✅ Agent '{self.config.name}' completed successfully")
            return {
                'success': True,
                'execution_id': execution_id,
                'metrics': metrics,
                'output': result.get('output')
            }

        except Exception as e:
            logger.error(f"❌ Agent '{self.config.name}' failed: {e}")

            if execution_id:
                self.tracker.complete_execution(
                    execution_id=execution_id,
                    status='failed',
                    error_message=str(e)
                )

            # Write error to journal
            if self.config.notion_page_id and self.config.agent_id:
                try:
                    from promaia.agents.notion_journal import write_journal_entry

                    await write_journal_entry(
                        agent_id=self.config.agent_id,
                        workspace=self.config.workspace,
                        entry_type="Error",
                        content=f"Execution failed: {str(e)}",
                        execution_id=execution_id
                    )
                except Exception as journal_error:
                    logger.warning(f"Could not write error to journal: {journal_error}")

            return {
                'success': False,
                'execution_id': execution_id,
                'error': str(e)
            }

    async def _load_initial_context(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        Load initial context from configured databases.

        Returns:
            Dictionary mapping database names to lists of pages
        """
        context = {}

        for source_spec in self.config.databases:
            try:
                # Parse source spec (e.g., "journal:7", "stories:all")
                if ':' in source_spec:
                    database_name, days_str = source_spec.split(':', 1)
                    days = None if days_str == 'all' else int(days_str)
                else:
                    database_name = source_spec
                    days = None

                # Load pages for this database
                pages = load_database_pages_with_filters(
                    database_name=database_name,
                    workspace=self.config.workspace,
                    days=days
                )

                if pages:
                    context[database_name] = pages
                    logger.info(f"  ✓ Loaded {len(pages)} pages from '{database_name}'")
                else:
                    logger.info(f"  ⚠ No pages found in '{database_name}'")

            except Exception as e:
                logger.error(f"  ✗ Failed to load '{source_spec}': {e}")

        return context

    def _load_custom_prompt(self) -> str:
        """
        Load the custom prompt for the agent.

        Returns:
            Prompt text
        """
        prompt_path = Path(self.config.prompt_file)

        # If it's a file path, read it
        if prompt_path.exists():
            with open(prompt_path, 'r') as f:
                return f.read()

        # Otherwise, treat it as inline content
        return self.config.prompt_file

    def _create_agent_prompt(
        self,
        custom_prompt: str,
        context_data: Dict[str, List[Dict[str, Any]]]
    ) -> str:
        """
        Create the full agent prompt with context and tools.

        Args:
            custom_prompt: The agent's custom instructions
            context_data: Loaded context from databases

        Returns:
            Full prompt string
        """
        # Start with custom instructions
        prompt = f"""# Agent: {self.config.name}

{custom_prompt}

# Available Tools

You have access to the following query tools to gather additional information:

1. **query_sql**: Execute natural language queries against structured data
   - Example: <tool_call><tool_name>query_sql</tool_name><parameters><query>find emails from our manufacturer</query></parameters></tool_call>

2. **query_vector**: Semantic search across all content
   - Example: <tool_call><tool_name>query_vector</tool_name><parameters><query>discussions about inventory</query></parameters></tool_call>

3. **query_source**: Load additional source data
   - Example: <tool_call><tool_name>query_source</tool_name><parameters><source>gmail:7</source></parameters></tool_call>

You can make multiple tool calls to gather all needed information. After gathering sufficient data, provide your final analysis and recommendations.

# Current Context

"""

        # Add formatted context
        if context_data:
            prompt += format_context_data(context_data)
        else:
            prompt += "No initial context loaded.\n"

        prompt += f"""

# Instructions

1. Analyze the context provided above
2. Use query tools if you need additional information
3. Identify any issues, patterns, or insights
4. Provide clear, actionable recommendations
5. Format your final response as a structured report

Current time: {datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")}
"""

        return prompt

    async def _execute_with_iterations(
        self,
        initial_prompt: str,
        context_data: Dict[str, List[Dict[str, Any]]]
    ) -> Dict[str, Any]:
        """
        Execute agent with iteration loop for multi-step queries.

        Args:
            initial_prompt: The initial prompt with instructions
            context_data: Initial context data

        Returns:
            Result dictionary with output and metrics
        """
        # Initialize context state for query tools
        context_state = {
            'ai_queries': [],
            'context_data': context_data
        }

        query_executor = QueryToolExecutor(context_state)

        # Get AI model
        model = PromaiLLMAdapter(client_type="auto")

        # Conversation history
        messages = []
        total_tokens = 0
        total_cost = 0.0

        # Initial message
        messages.append({
            'role': 'user',
            'content': initial_prompt
        })

        # Iteration loop
        for iteration in range(self.config.max_iterations):
            logger.info(f"🔄 Iteration {iteration + 1}/{self.config.max_iterations}")

            try:
                # Call AI
                response = await self._call_ai(model, messages)
                response_text = response.get('content', '')

                # Track tokens/cost (if available)
                if response.get('usage'):
                    total_tokens += response['usage'].get('total_tokens', 0)
                    # Rough cost estimate (adjust based on model pricing)
                    total_cost += self._estimate_cost(response['usage'])

                # Check for query tool calls
                if query_executor.has_query_tool_calls(response_text):
                    logger.info("🔍 Found query tool calls, executing...")

                    # Parse tool calls
                    tool_calls = query_executor.parse_query_tool_calls(response_text)

                    # Execute queries (without permission callbacks - agents run autonomously)
                    query_results = []
                    for tool_call in tool_calls:
                        result = await query_executor._execute_query_only(tool_call)
                        query_results.append(result)

                    # Add results to conversation
                    results_text = "\n\n".join([
                        f"Query Result:\n{r.get('content', r.get('error', 'No result'))}"
                        for r in query_results
                    ])

                    messages.append({'role': 'assistant', 'content': response_text})
                    messages.append({'role': 'user', 'content': f"Tool Results:\n{results_text}\n\nPlease continue your analysis."})

                else:
                    # No more tool calls, this is the final response
                    logger.info("✅ Agent produced final output")
                    return {
                        'output': response_text,
                        'iterations_used': iteration + 1,
                        'tokens_used': total_tokens,
                        'cost_estimate': total_cost
                    }

            except Exception as e:
                logger.error(f"Error in iteration {iteration + 1}: {e}")
                break

        # Max iterations reached
        logger.warning(f"⚠️ Max iterations ({self.config.max_iterations}) reached")

        # Return last response if available
        if messages:
            last_message = messages[-1]
            if last_message.get('role') == 'assistant':
                return {
                    'output': last_message.get('content', 'No output generated'),
                    'iterations_used': self.config.max_iterations,
                    'tokens_used': total_tokens,
                    'cost_estimate': total_cost
                }

        return {
            'output': 'No output generated (max iterations reached)',
            'iterations_used': self.config.max_iterations,
            'tokens_used': total_tokens,
            'cost_estimate': total_cost
        }

    async def _call_ai(self, model, messages: List[Dict[str, str]]) -> Dict[str, Any]:
        """
        Call the AI model.

        Args:
            model: The AI model instance (PromaiLLMAdapter)
            messages: Conversation messages

        Returns:
            Response dictionary with content and usage
        """
        # Use PromaiLLMAdapter's invoke method
        response = model.invoke(messages)

        # PromaiLLMAdapter returns a MockResponse with .content attribute
        if hasattr(response, 'content'):
            return {'content': response.content}
        elif isinstance(response, str):
            return {'content': response}
        else:
            return {'content': str(response)}

    def _estimate_cost(self, usage: Dict[str, int]) -> float:
        """
        Estimate cost based on token usage.

        Args:
            usage: Usage dict with token counts

        Returns:
            Estimated cost in USD
        """
        # Rough estimates (adjust based on actual model pricing)
        # Claude Sonnet: ~$3/$15 per 1M tokens (input/output)
        # GPT-4: ~$10/$30 per 1M tokens
        input_tokens = usage.get('prompt_tokens', 0)
        output_tokens = usage.get('completion_tokens', 0)

        # Conservative estimate
        cost = (input_tokens * 3 / 1_000_000) + (output_tokens * 15 / 1_000_000)
        return cost

    async def _write_to_notion(self, output: str) -> bool:
        """
        Write agent output to Notion page.

        Args:
            output: The agent's output text

        Returns:
            True if successful
        """
        try:
            success = await self.notion_writer.append_to_page(
                page_id=self.config.output_notion_page_id,
                content=output,
                agent_name=self.config.name,
                add_timestamp=True,
                add_divider=True
            )

            if success:
                logger.info(f"📝 Wrote output to Notion page {self.config.output_notion_page_id}")
            else:
                logger.error("Failed to write to Notion")

            return success

        except Exception as e:
            logger.error(f"Error writing to Notion: {e}")
            return False


# Synchronous wrapper
def execute_agent_sync(agent_config: AgentConfig) -> Dict[str, Any]:
    """
    Synchronous wrapper for agent execution.

    Args:
        agent_config: The agent configuration

    Returns:
        Execution result
    """
    executor = AgentExecutor(agent_config)
    return asyncio.run(executor.execute())
