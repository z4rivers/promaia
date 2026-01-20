"""
CLI commands for scheduled agent management.

These commands allow users to create, manage, and monitor interval-based agents
that automatically run queries and write results to Notion.
"""
import asyncio
import json
import logging
from datetime import datetime
from typing import Optional
from pathlib import Path

from promaia.agents import (
    AgentConfig, load_agents, save_agent, delete_agent, get_agent,
    execute_agent_sync, ExecutionTracker,
    run_scheduler_daemon_sync, is_scheduler_running, stop_scheduler
)
from promaia.config.workspaces import get_workspace_manager

logger = logging.getLogger(__name__)


async def handle_agent_add(args):
    """
    Interactively add a new scheduled agent.

    Usage:
        maia agent add
    """
    from promaia.utils.display import print_text

    print_text("\n🤖 Create New Scheduled Agent\n", style="bold cyan")

    # Step 1: Agent name
    name = input("Agent name: ").strip()
    if not name:
        print("❌ Name is required")
        return

    # Check if already exists
    if get_agent(name):
        print(f"❌ Agent '{name}' already exists")
        return

    # Step 2: Workspace
    workspace_mgr = get_workspace_manager()
    workspaces = workspace_mgr.list_workspaces()

    if not workspaces:
        print("❌ No workspaces configured. Please create a workspace first.")
        return

    print("\nAvailable workspaces:")
    for i, ws in enumerate(workspaces, 1):
        print(f"  {i}. {ws}")

    ws_choice = input(f"Select workspace (1-{len(workspaces)}): ").strip()
    try:
        workspace = workspaces[int(ws_choice) - 1]
    except (ValueError, IndexError):
        print("❌ Invalid workspace selection")
        return

    # Step 3: Select databases (with browser if available, otherwise manual input)
    print("\nSelect databases (comma-separated with optional days)")
    print("Examples: journal:7, stories:all, gmail:30")
    databases_input = input("Databases: ").strip()

    if not databases_input:
        print("❌ At least one database is required")
        return

    databases = [db.strip() for db in databases_input.split(',')]

    # Step 4: Prompt
    print("\nCustom prompt:")
    print("  1. Enter file path to .md file")
    print("  2. Paste markdown directly (end with empty line)")

    prompt_choice = input("Choose (1 or 2): ").strip()

    if prompt_choice == '1':
        prompt_file = input("Prompt file path: ").strip()
        if not Path(prompt_file).exists():
            print(f"❌ File not found: {prompt_file}")
            return
    else:
        print("Paste your prompt (press Enter twice to finish):")
        lines = []
        while True:
            line = input()
            if not line and lines:  # Empty line after some content
                break
            lines.append(line)
        prompt_file = "\n".join(lines)

    # Step 5: Interval
    print("\nRun interval (minutes):")
    print("  Common: 5, 15, 30, 60")
    interval_input = input("Interval: ").strip()

    try:
        interval_minutes = int(interval_input)
        if interval_minutes <= 0:
            raise ValueError("Must be positive")
    except ValueError:
        print("❌ Invalid interval")
        return

    # Step 6: Max iterations
    max_iterations_input = input("Max query iterations (default: 3): ").strip()
    max_iterations = int(max_iterations_input) if max_iterations_input else 3

    # Step 7: Output Notion page
    print("\nOutput Notion page ID:")
    print("  (This is where agent results will be written)")
    output_page_id = input("Page ID: ").strip()

    if not output_page_id:
        print("❌ Output page ID is required")
        return

    # Step 8: MCP tools (optional for now)
    mcp_tools_input = input("\nMCP tools (comma-separated, optional): ").strip()
    mcp_tools = [t.strip() for t in mcp_tools_input.split(',')] if mcp_tools_input else []

    # Step 9: Description (optional)
    description = input("\nDescription (optional): ").strip()

    # Create agent config
    agent_config = AgentConfig(
        name=name,
        workspace=workspace,
        databases=databases,
        prompt_file=prompt_file,
        interval_minutes=interval_minutes,
        mcp_tools=mcp_tools,
        max_iterations=max_iterations,
        output_notion_page_id=output_page_id,
        enabled=True,
        description=description,
        created_at=datetime.now().isoformat()
    )

    # Validate
    errors = agent_config.validate()
    if errors:
        print("\n❌ Validation errors:")
        for error in errors:
            print(f"  - {error}")
        return

    # Save
    save_agent(agent_config)

    print(f"\n✅ Agent '{name}' created successfully!")
    print(f"   Workspace: {workspace}")
    print(f"   Databases: {', '.join(databases)}")
    print(f"   Interval: every {interval_minutes} minutes")
    print(f"   Output: {output_page_id}")
    print(f"\nUse 'maia agent run {name}' to test it manually")


async def handle_agent_list_scheduled(args):
    """
    List all scheduled agents.

    Usage:
        maia agent list-scheduled
    """
    agents = load_agents()

    if not agents:
        print("No scheduled agents configured")
        return

    print(f"\n🤖 Scheduled Agents ({len(agents)}):\n")

    tracker = ExecutionTracker()

    for agent in agents:
        status_emoji = "✅" if agent.enabled else "⏸️"
        print(f"{status_emoji} {agent.name}")
        print(f"   Workspace: {agent.workspace}")
        print(f"   Interval: every {agent.interval_minutes} minutes")
        print(f"   Databases: {', '.join(agent.databases)}")

        if agent.description:
            print(f"   Description: {agent.description}")

        # Show last run
        if agent.last_run_at:
            print(f"   Last run: {agent.last_run_at}")

        # Show stats
        stats = tracker.get_agent_stats(agent.name)
        if stats.get('total_runs', 0) > 0:
            print(f"   Runs: {stats['total_runs']} (success rate: {stats['success_rate']:.1f}%)")
            print(f"   Total cost: ${stats['total_cost']:.4f}")

        print()


async def handle_agent_run_scheduled(args):
    """
    Manually run a scheduled agent.

    Usage:
        maia agent run-scheduled <name>
    """
    from promaia.utils.display import print_text

    agent = get_agent(args.name)

    if not agent:
        print(f"❌ Agent '{args.name}' not found")
        return

    print_text(f"\n🤖 Running agent '{args.name}'...\n", style="bold cyan")

    # Execute agent
    result = execute_agent_sync(agent)

    if result['success']:
        print_text(f"\n✅ Agent completed successfully!", style="green")

        metrics = result.get('metrics', {})
        print(f"\nMetrics:")
        print(f"  Iterations: {metrics.get('iterations_used', 0)}")
        print(f"  Tokens: {metrics.get('tokens_used', 0):,}")
        print(f"  Cost: ${metrics.get('cost_estimate', 0):.4f}")
        print(f"  Duration: {metrics.get('duration_seconds', 0):.1f}s")

        print(f"\n📝 Output written to Notion page: {agent.output_notion_page_id}")

        # Show preview of output
        if result.get('output'):
            print("\nOutput preview:")
            output_preview = result['output'][:200]
            print(f"  {output_preview}...")

    else:
        print_text(f"\n❌ Agent failed: {result.get('error')}", style="red")


async def handle_agent_logs_scheduled(args):
    """
    View execution logs for a scheduled agent.

    Usage:
        maia agent logs-scheduled <name>
        maia agent logs-scheduled <name> --limit 10
    """
    tracker = ExecutionTracker()

    executions = tracker.list_executions(
        agent_name=args.name,
        limit=args.limit
    )

    if not executions:
        print(f"No execution logs for agent '{args.name}'")
        return

    print(f"\n📜 Execution Logs for '{args.name}' ({len(executions)} recent):\n")

    for exec_record in executions:
        status = exec_record['status']
        status_emoji = {
            'completed': '✅',
            'failed': '❌',
            'running': '⏳',
            'pending': '⏸️'
        }.get(status, '❓')

        print(f"{status_emoji} Execution #{exec_record['id']}")
        print(f"   Started: {exec_record['started_at']}")

        if exec_record['completed_at']:
            print(f"   Completed: {exec_record['completed_at']}")

        print(f"   Status: {status}")

        if exec_record['iterations_used']:
            print(f"   Iterations: {exec_record['iterations_used']}")

        if exec_record['tokens_used']:
            print(f"   Tokens: {exec_record['tokens_used']:,}")

        if exec_record['cost_estimate']:
            print(f"   Cost: ${exec_record['cost_estimate']:.4f}")

        if exec_record['error_message']:
            print(f"   Error: {exec_record['error_message']}")

        if exec_record['context_summary']:
            print(f"   Context: {exec_record['context_summary']}")

        print()


async def handle_agent_remove_scheduled(args):
    """
    Remove a scheduled agent.

    Usage:
        maia agent remove-scheduled <name>
    """
    agent = get_agent(args.name)

    if not agent:
        print(f"❌ Agent '{args.name}' not found")
        return

    # Confirm deletion
    if not args.yes:
        confirm = input(f"⚠️  Remove agent '{args.name}'? (y/N): ").strip().lower()
        if confirm != 'y':
            print("Cancelled")
            return

    deleted = delete_agent(args.name)

    if deleted:
        print(f"✅ Agent '{args.name}' removed")
    else:
        print(f"❌ Failed to remove agent '{args.name}'")


async def handle_agent_enable(args):
    """
    Enable a scheduled agent.

    Usage:
        maia agent enable <name>
    """
    agent = get_agent(args.name)

    if not agent:
        print(f"❌ Agent '{args.name}' not found")
        return

    agent.enabled = True
    save_agent(agent)

    print(f"✅ Agent '{args.name}' enabled")


async def handle_agent_disable(args):
    """
    Disable a scheduled agent.

    Usage:
        maia agent disable <name>
    """
    agent = get_agent(args.name)

    if not agent:
        print(f"❌ Agent '{args.name}' not found")
        return

    agent.enabled = False
    save_agent(agent)

    print(f"⏸️  Agent '{args.name}' disabled")


async def handle_agent_info_scheduled(args):
    """
    Show detailed information about a scheduled agent.

    Usage:
        maia agent info-scheduled <name>
    """
    agent = get_agent(args.name)

    if not agent:
        print(f"❌ Agent '{args.name}' not found")
        return

    tracker = ExecutionTracker()
    stats = tracker.get_agent_stats(agent.name)

    print(f"\n🤖 Agent: {agent.name}\n")

    print(f"Status: {'✅ Enabled' if agent.enabled else '⏸️  Disabled'}")
    print(f"Workspace: {agent.workspace}")
    print(f"Interval: every {agent.interval_minutes} minutes")
    print(f"Max Iterations: {agent.max_iterations}")

    print(f"\nDatabases ({len(agent.databases)}):")
    for db in agent.databases:
        print(f"  - {db}")

    if agent.mcp_tools:
        print(f"\nMCP Tools ({len(agent.mcp_tools)}):")
        for tool in agent.mcp_tools:
            print(f"  - {tool}")

    print(f"\nOutput Page: {agent.output_notion_page_id}")

    if agent.description:
        print(f"\nDescription: {agent.description}")

    print(f"\nPrompt:")
    prompt_preview = agent.prompt_file[:200] if len(agent.prompt_file) < 500 else agent.prompt_file[:200] + "..."
    print(f"  {prompt_preview}")

    print(f"\nCreated: {agent.created_at}")

    if agent.last_run_at:
        print(f"Last Run: {agent.last_run_at}")

    if stats.get('total_runs', 0) > 0:
        print(f"\n📊 Statistics:")
        print(f"  Total Runs: {stats['total_runs']}")
        print(f"  Successful: {stats['successful_runs']}")
        print(f"  Failed: {stats['failed_runs']}")
        print(f"  Success Rate: {stats['success_rate']:.1f}%")
        print(f"  Avg Cost: ${stats['avg_cost']:.4f}")
        print(f"  Total Cost: ${stats['total_cost']:.4f}")
        print(f"  Last Status: {stats['last_run_status']}")


async def handle_scheduler_start(args):
    """
    Start the agent scheduler daemon.

    Usage:
        maia agent-scheduler-start
    """
    from promaia.utils.display import print_text

    # Check if already running
    if is_scheduler_running():
        print_text("❌ Scheduler is already running", style="red")
        return

    # Check if there are enabled agents
    agents = load_agents()
    enabled_agents = [a for a in agents if a.enabled]

    if not enabled_agents:
        print_text("⚠️  No enabled agents found. Create and enable agents first.", style="yellow")
        return

    print_text(f"\n🚀 Starting scheduler with {len(enabled_agents)} enabled agents...\n", style="bold cyan")

    for agent in enabled_agents:
        print(f"  ✓ {agent.name} (every {agent.interval_minutes} min)")

    print()

    # Start the scheduler
    try:
        run_scheduler_daemon_sync()
    except KeyboardInterrupt:
        print_text("\n⚠️  Scheduler stopped by user", style="yellow")


async def handle_scheduler_stop(args):
    """
    Stop the agent scheduler daemon.

    Usage:
        maia agent-scheduler-stop
    """
    from promaia.utils.display import print_text

    if not is_scheduler_running():
        print_text("⚠️  Scheduler is not running", style="yellow")
        return

    print_text("🛑 Stopping scheduler...", style="cyan")

    if stop_scheduler():
        print_text("✅ Scheduler stopped", style="green")
    else:
        print_text("❌ Failed to stop scheduler", style="red")


async def handle_scheduler_status(args):
    """
    Check scheduler status.

    Usage:
        maia agent-scheduler-status
    """
    from promaia.utils.display import print_text

    if is_scheduler_running():
        print_text("✅ Scheduler is running", style="green")

        # Show enabled agents
        agents = load_agents()
        enabled_agents = [a for a in agents if a.enabled]

        if enabled_agents:
            print(f"\nEnabled agents ({len(enabled_agents)}):")
            for agent in enabled_agents:
                print(f"  ✓ {agent.name} (every {agent.interval_minutes} min)")
    else:
        print_text("⏸️  Scheduler is not running", style="yellow")

        # Show enabled agents that would run
        agents = load_agents()
        enabled_agents = [a for a in agents if a.enabled]

        if enabled_agents:
            print(f"\nEnabled agents ({len(enabled_agents)}) waiting to run:")
            for agent in enabled_agents:
                print(f"  ⏸️  {agent.name} (every {agent.interval_minutes} min)")
            print("\nUse 'maia agent-scheduler-start' to start the scheduler")
        else:
            print("\nNo enabled agents configured.")


def add_scheduled_agent_commands(subparsers):
    """Add scheduled agent commands to the parser."""
    # Note: This is a separate set of commands from external agents
    # Main 'agent' command is already taken by external agents, so we'll add these as subcommands

    # Add command
    add_parser = subparsers.add_parser('agent-add', help='Create a new scheduled agent')
    add_parser.set_defaults(func=handle_agent_add)

    # List command
    list_parser = subparsers.add_parser('agent-list', help='List all scheduled agents')
    list_parser.set_defaults(func=handle_agent_list_scheduled)

    # Run command
    run_parser = subparsers.add_parser('agent-run', help='Manually run a scheduled agent')
    run_parser.add_argument('name', help='Agent name')
    run_parser.set_defaults(func=handle_agent_run_scheduled)

    # Logs command
    logs_parser = subparsers.add_parser('agent-logs', help='View execution logs')
    logs_parser.add_argument('name', help='Agent name')
    logs_parser.add_argument('--limit', '-l', type=int, default=20, help='Number of logs to show')
    logs_parser.set_defaults(func=handle_agent_logs_scheduled)

    # Remove command
    remove_parser = subparsers.add_parser('agent-remove', help='Remove a scheduled agent')
    remove_parser.add_argument('name', help='Agent name')
    remove_parser.add_argument('--yes', '-y', action='store_true', help='Skip confirmation')
    remove_parser.set_defaults(func=handle_agent_remove_scheduled)

    # Enable command
    enable_parser = subparsers.add_parser('agent-enable', help='Enable a scheduled agent')
    enable_parser.add_argument('name', help='Agent name')
    enable_parser.set_defaults(func=handle_agent_enable)

    # Disable command
    disable_parser = subparsers.add_parser('agent-disable', help='Disable a scheduled agent')
    disable_parser.add_argument('name', help='Agent name')
    disable_parser.set_defaults(func=handle_agent_disable)

    # Info command
    info_parser = subparsers.add_parser('agent-info', help='Show agent details')
    info_parser.add_argument('name', help='Agent name')
    info_parser.set_defaults(func=handle_agent_info_scheduled)

    # Scheduler commands
    scheduler_start_parser = subparsers.add_parser('agent-scheduler-start', help='Start the agent scheduler daemon')
    scheduler_start_parser.set_defaults(func=handle_scheduler_start)

    scheduler_stop_parser = subparsers.add_parser('agent-scheduler-stop', help='Stop the agent scheduler daemon')
    scheduler_stop_parser.set_defaults(func=handle_scheduler_stop)

    scheduler_status_parser = subparsers.add_parser('agent-scheduler-status', help='Check scheduler status')
    scheduler_status_parser.set_defaults(func=handle_scheduler_status)
