# Promaia Scheduled Agents

Interval-based agents that monitor multiple sources, perform multi-step analysis, and output results to Notion pages.

## Features

- ✅ Run at configured intervals (5, 15, 30, 60 minutes, etc.)
- ✅ Execute context queries from multiple databases
- ✅ Custom prompts per agent
- ✅ Multi-step agentic loops (iterative query tool calling)
- ✅ Workspace-scoped access control
- ✅ Write results to Notion pages
- ✅ Execution tracking and cost monitoring
- ✅ AsyncIO-based scheduler (no external dependencies)

## Quick Start

### 1. Create an Agent

```bash
maia agent-add
```

This interactive command will ask for:
- **Name**: Unique identifier for the agent
- **Workspace**: Which workspace to operate in
- **Databases**: Source data (e.g., `journal:7`, `gmail:30`, `stories:all`)
- **Prompt**: Custom instructions (file path or inline markdown)
- **Interval**: How often to run (in minutes)
- **Max Iterations**: Maximum query iterations (default: 3)
- **Output Page ID**: Notion page where results will be written
- **MCP Tools** (optional): Additional tools to enable

### 2. List Agents

```bash
maia agent-list
```

Shows all configured agents with their settings and statistics.

### 3. Test an Agent Manually

```bash
maia agent-run <agent-name>
```

Runs the agent immediately (without waiting for the schedule).

### 4. Start the Scheduler

```bash
maia agent-scheduler-start
```

Starts the background scheduler that runs all enabled agents at their intervals.

**Note**: The scheduler runs in the foreground. Use Ctrl+C to stop, or run in a `screen`/`tmux` session for persistence.

### 5. Check Scheduler Status

```bash
maia agent-scheduler-status
```

### 6. Stop the Scheduler

```bash
maia agent-scheduler-stop
```

## Commands Reference

### Agent Management

- `maia agent-add` - Create a new scheduled agent
- `maia agent-list` - List all agents
- `maia agent-info <name>` - Show detailed agent info
- `maia agent-remove <name>` - Delete an agent
- `maia agent-enable <name>` - Enable an agent
- `maia agent-disable <name>` - Disable an agent

### Execution

- `maia agent-run <name>` - Manually run an agent
- `maia agent-logs <name>` - View execution history

### Scheduler Control

- `maia agent-scheduler-start` - Start the scheduler daemon
- `maia agent-scheduler-stop` - Stop the scheduler daemon
- `maia agent-scheduler-status` - Check scheduler status

## How It Works

### Execution Flow

1. **Load Context**: Agent loads data from specified databases
2. **Create Prompt**: Combines custom prompt with loaded context
3. **Agentic Loop**: AI can make multiple query tool calls to gather more data
   - `query_sql`: Natural language → SQL queries
   - `query_vector`: Semantic search
   - `query_source`: Load additional databases
4. **Write Output**: Structured results written to Notion page
5. **Track Metrics**: Execution logged with tokens, cost, iterations

### Multi-Step Capability

Agents use an iteration loop (max 3-5 steps by default) where the AI can:
- Make initial queries to gather data
- Analyze results
- Request additional information via query tools
- Iterate until satisfied or max iterations reached
- Produce final structured output

This solves the "agentic loop" challenge with a simple counter-based approach.

## Example Use Case: Manufacturing Sentry

### Problem
Hardware teams need to monitor emails, Notion tasks, and inventory for issues.

### Solution
```yaml
Name: manufacturing-sentry
Workspace: hardware
Databases:
  - journal:7
  - gmail:7
  - stories:all
Interval: 30 minutes
Prompt: |
  You are a sentry for a hardware manufacturing team.

  Your job:
  1. Monitor all sources for issues (delays, inventory problems, blockers)
  2. Cross-reference information across sources
  3. Identify patterns or recurring problems
  4. Suggest actionable solutions

  Output format:
  ## 🚨 Issues Found
  [List issues with severity]

  ## 💡 Suggested Actions
  [Actionable next steps]

  ## ✅ Status
  [Overall assessment]
```

Every 30 minutes, this agent:
1. Loads last 7 days of emails and journal entries
2. Checks all stories/tasks
3. Runs SQL queries to find specific patterns
4. Writes findings to a Notion page

## Configuration Storage

Agents are stored in `promaia.config.json`:

```json
{
  "agents": [
    {
      "name": "manufacturing-sentry",
      "workspace": "hardware",
      "databases": ["journal:7", "gmail:7", "stories:all"],
      "prompt_file": "prompts/agents/sentry.md",
      "interval_minutes": 30,
      "mcp_tools": ["notion"],
      "max_iterations": 5,
      "output_notion_page_id": "abc123-def456",
      "enabled": true,
      "created_at": "2026-01-19T10:30:00Z",
      "last_run_at": "2026-01-19T11:00:00Z"
    }
  ]
}
```

## Execution Tracking

All executions are logged in `data/hybrid_metadata.db` (table: `agent_executions`):

- Timestamps (start/complete)
- Iterations used
- Tokens consumed
- Cost estimate
- Status (completed/failed)
- Error messages
- Output page ID

View logs: `maia agent-logs <agent-name>`

## Cost Monitoring

Each execution tracks:
- **Tokens**: Input + output tokens
- **Cost**: Estimated USD cost
- **Stats**: View per-agent totals with `maia agent-info <name>`

## Architecture

```
promaia/agents/
├── __init__.py              # Module exports
├── agent_config.py          # Agent configuration & persistence
├── executor.py              # Agent execution engine
├── execution_tracker.py     # Execution logging & metrics
├── notion_writer.py         # Notion output formatting
└── scheduler.py             # AsyncIO-based scheduler

promaia/cli/
└── scheduled_agent_commands.py  # CLI commands
```

## Tips

1. **Start Small**: Test agents manually with `maia agent-run` before scheduling
2. **Monitor Costs**: Check `maia agent-logs` regularly for cost trends
3. **Iterate on Prompts**: Refine agent prompts based on execution logs
4. **Use Workspaces**: Isolate agents by workspace for security
5. **Disable When Not Needed**: Use `maia agent-disable` to pause expensive agents

## Next Steps

- [ ] Add webhook triggers (run on new content)
- [ ] Support Discord/Slack notifications
- [ ] Add conditional execution (only run if X changes)
- [ ] Multi-output support (write to multiple Notion pages)
- [ ] Agent dependencies (agent B runs after agent A)
- [ ] Web UI for agent management

## Troubleshooting

### Scheduler won't start
- Check if already running: `maia agent-scheduler-status`
- Ensure at least one agent is enabled: `maia agent-list`

### Agent fails with import errors
- Ensure all dependencies are installed
- Check workspace has valid API keys

### High costs
- Reduce `max_iterations` (default: 3)
- Increase `interval_minutes` to run less frequently
- Optimize prompts to be more concise

### No output in Notion
- Verify `output_notion_page_id` is correct
- Check Notion API permissions
- Review `maia agent-logs` for errors

## Support

For issues or questions:
- GitHub: https://github.com/anthropics/promaia
- Documentation: Check `/docs` folder
