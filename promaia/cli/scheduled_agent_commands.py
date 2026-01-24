"""
CLI commands for scheduled agent management.

These commands allow users to create, manage, and monitor interval-based agents
that automatically run queries and write results to Notion.
"""
import asyncio
import json
import logging
import random
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


def _generate_placeholder_name() -> str:
    """Generate a random placeholder name in format: noun-####"""
    nouns = [
        "phoenix", "falcon", "eagle", "hawk", "raven", "sparrow",
        "tiger", "wolf", "lion", "bear", "fox", "lynx",
        "comet", "nova", "star", "nebula", "pulsar", "quasar",
        "river", "mountain", "forest", "ocean", "canyon", "valley",
        "storm", "thunder", "lightning", "cloud", "wind", "rain",
        "sage", "mentor", "guide", "scout", "guardian", "watcher",
        "crystal", "diamond", "ruby", "amber", "jade", "opal",
        "compass", "beacon", "anchor", "horizon", "zenith", "atlas"
    ]
    noun = random.choice(nouns)
    number = random.randint(1000, 9999)
    return f"{noun}-{number}"


async def _add_agent_to_calendar(agent_config: AgentConfig) -> bool:
    """Add an agent to Google Calendar."""
    try:
        from promaia.gcal import get_calendar_manager

        calendar_mgr = get_calendar_manager()

        if not agent_config.schedule:
            logger.warning(f"Agent {agent_config.name} has no schedule, cannot add to calendar")
            return False

        event_ids = calendar_mgr.create_agent_event(
            agent_name=agent_config.name,
            schedule=agent_config.schedule,
            agent_config=agent_config.to_dict()
        )

        if event_ids:
            # Store event IDs in agent config
            agent_config.calendar_event_ids = event_ids
            save_agent(agent_config)
            return True

        return False

    except Exception as e:
        logger.error(f"Error adding agent to calendar: {e}")
        return False


def _show_agent_summary(agent: AgentConfig, console):
    """Display agent configuration summary before creation."""
    from promaia.utils.display import print_separator
    from promaia.cli.schedule_grid_selector import schedule_to_string

    print()
    print_separator("Agent Configuration Summary")
    console.print(f"Name: [bold white]{agent.name}[/bold white]")
    console.print(f"Workspace: [cyan]{agent.workspace}[/cyan]")
    console.print(f"Databases: [cyan]{', '.join(agent.databases)}[/cyan]")

    # Show schedule or interval
    if agent.schedule:
        schedule_display = schedule_to_string(agent.schedule)
        console.print(f"Schedule: [cyan]{len(agent.schedule)} runs/week[/cyan]")
        console.print(f"  [dim]{schedule_display}[/dim]")
    elif agent.interval_minutes:
        console.print(f"Interval: [cyan]Every {agent.interval_minutes} minutes[/cyan]")

    console.print(f"Max Iterations: [cyan]{agent.max_iterations}[/cyan]")
    console.print(f"Output Page: [cyan]{agent.output_notion_page_id}[/cyan]")

    if agent.description:
        console.print(f"Description: [dim]{agent.description}[/dim]")

    if agent.mcp_tools:
        console.print(f"MCP Tools: [cyan]{', '.join(agent.mcp_tools)}[/cyan]")

    # Show prompt preview
    prompt_preview = agent.prompt_file[:150] if len(agent.prompt_file) > 150 else agent.prompt_file
    if len(agent.prompt_file) > 150:
        prompt_preview += "..."
    console.print(f"Prompt: [dim]{prompt_preview}[/dim]")

    print_separator()


async def handle_agent_add(args):
    """
    Interactively add a new scheduled agent with modern UI.

    Usage:
        maia agent add
    """
    from promaia.utils.display import print_text, print_separator
    from promaia.cli.agent_creation_selector import (
        select_workspace,
        select_databases,
        input_prompt,
        select_interval,
        select_notion_page,
        select_mcp_tools,
    )
    from promaia.config.databases import get_database_manager
    from rich.console import Console

    console = Console()

    print_text("\n🤖 Create New Scheduled Agent\n", style="bold cyan")

    # Step 1: Agent name (simple text input with placeholder)
    placeholder_name = _generate_placeholder_name()
    console.print(f"Agent name (press ENTER for '[cyan]{placeholder_name}[/cyan]'):")
    name = input("› ").strip()

    # Use placeholder if user pressed ENTER without typing
    if not name:
        name = placeholder_name
        console.print(f"✓ Using name: [cyan]{name}[/cyan]", style="dim")

    # Check if already exists
    if get_agent(name):
        console.print(f"❌ Agent '{name}' already exists", style="red")
        return

    # Step 2: Workspace selection (interactive)
    workspace_mgr = get_workspace_manager()
    workspaces = workspace_mgr.list_workspaces()

    if not workspaces:
        console.print("❌ No workspaces configured. Please create a workspace first.", style="red")
        return

    console.print()  # Spacing
    workspace = await select_workspace(workspaces)
    if not workspace:
        console.print("❌ Cancelled", style="red")
        return

    console.print(f"✓ Workspace: [cyan]{workspace}[/cyan]", style="dim")

    # Step 3: Database selection (interactive checkbox with inline days)
    db_manager = get_database_manager()
    workspace_databases = db_manager.get_workspace_databases(workspace)

    # Format databases for selector
    available_databases = []
    for db in workspace_databases:
        if db.browser_include:  # Only show databases marked for browser
            available_databases.append({
                'name': db.get_qualified_name(),
                'default_days': db.default_days,
                'default_include': db.default_include,
            })

    if not available_databases:
        console.print(f"❌ No databases available in workspace '{workspace}'", style="red")
        return

    console.print()  # Spacing
    selected_dbs = await select_databases(workspace, available_databases)
    if not selected_dbs:
        console.print("❌ Cancelled", style="red")
        return

    # Format databases with days for agent config
    databases = [f"{db_name}:{days}" for db_name, days in selected_dbs]
    console.print(f"✓ Databases: {len(selected_dbs)} selected", style="dim")

    # Step 4: Prompt input (interactive file browser)
    console.print()  # Spacing
    prompt_content = await input_prompt()
    if not prompt_content:
        console.print("❌ Cancelled", style="red")
        return

    console.print(f"✓ Prompt: {len(prompt_content)} characters", style="dim")

    # Step 5: Schedule selection (interactive grid)
    console.print()  # Spacing
    console.print("📅 Schedule agent runs (MIDI-style grid):", style="cyan")
    console.print("   Use arrow keys to navigate, SPACE to toggle slots", style="dim")

    from promaia.cli.schedule_grid_selector import select_schedule, schedule_to_string

    schedule = await select_schedule()
    if not schedule:
        console.print("❌ Cancelled", style="red")
        return

    schedule_str = schedule_to_string(schedule)
    console.print(f"✓ Schedule: {len(schedule)} runs/week", style="dim")

    # Step 6: Max iterations (simple with default)
    console.print()  # Spacing
    max_iterations_input = input("Max query iterations (default: 3): ").strip()
    max_iterations = int(max_iterations_input) if max_iterations_input else 3

    if max_iterations <= 0:
        console.print("❌ Max iterations must be positive", style="red")
        return

    console.print(f"✓ Max iterations: {max_iterations}", style="dim")

    # Step 7: Output page selection (interactive browser)
    console.print()  # Spacing
    output_page_id = await select_notion_page(workspace)
    if not output_page_id:
        console.print("❌ Cancelled", style="red")
        return

    console.print(f"✓ Output page: {output_page_id}", style="dim")

    # Step 8: MCP tools (optional, interactive)
    mcp_tools = []
    console.print()  # Spacing
    configure_mcp = input("Configure MCP tools? (y/N): ").strip().lower()
    if configure_mcp == 'y':
        # For now, we'll get available tools from a simple list
        # In the future, this could query actual available MCP tools
        available_tools = []  # Placeholder - would be populated from MCP server
        if available_tools:
            mcp_tools = await select_mcp_tools(available_tools)
            if mcp_tools:
                console.print(f"✓ MCP Tools: {len(mcp_tools)} selected", style="dim")
        else:
            console.print("No MCP tools available", style="yellow")

    # Step 9: Description (optional, simple text)
    console.print()  # Spacing
    description = input("Description (optional, press ENTER to skip): ").strip()

    # Generate agent ID
    from promaia.agents.notion_setup import generate_agent_id
    existing_agents = load_agents()
    agent_id = generate_agent_id(name, existing_agents)
    console.print(f"✓ Agent ID: [cyan]{agent_id}[/cyan]", style="dim")

    # Create agent config
    agent_config = AgentConfig(
        name=name,
        agent_id=agent_id,
        workspace=workspace,
        databases=databases,
        prompt_file=prompt_content,
        schedule=schedule,  # New schedule format
        interval_minutes=None,  # No longer using interval
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
        console.print("\n❌ Validation errors:", style="red")
        for error in errors:
            console.print(f"  - {error}", style="red")
        return

    # Show configuration summary
    _show_agent_summary(agent_config, console)

    # Confirm creation
    confirm = input("\nCreate this agent? (Y/n): ").strip().lower()
    if confirm and confirm != 'y':
        console.print("❌ Cancelled", style="yellow")
        return

    # Create agent structure in Notion
    try:
        from promaia.agents.notion_setup import create_agent_in_notion

        notion_page_id = await create_agent_in_notion(agent_config, workspace)
        agent_config.notion_page_id = notion_page_id

    except Exception as e:
        console.print(f"\n⚠️  Could not create Notion structure: {e}", style="yellow")
        console.print("   Agent will be created without Notion integration", style="dim")
        # Continue anyway - agent can still work from JSON

    # Save
    save_agent(agent_config)

    console.print(f"\n✅ Agent '{name}' created successfully!", style="green")
    console.print(f"   Agent ID: [cyan]{agent_id}[/cyan]", style="dim")

    if agent_config.notion_page_id:
        console.print(f"   View in Notion: https://notion.so/{agent_config.notion_page_id}", style="dim")
        console.print(f"   Mention with @{agent_id} in calendar events", style="dim")

    console.print(f"   Use 'maia agent run-scheduled {name}' to test it", style="dim")

    # Ask if user wants to add to Google Calendar
    console.print()
    add_to_calendar = input("Add this agent to Google Calendar? (Y/n): ").strip().lower()

    if add_to_calendar != 'n':
        console.print("\n📅 Adding agent to Google Calendar...", style="cyan")
        success = await _add_agent_to_calendar(agent_config)

        if success:
            console.print("✅ Agent added to your Google Calendar!", style="green")
            console.print("   You can now manage it like any calendar event", style="dim")
        else:
            console.print("⚠️  Could not add to calendar. You can add it later with:", style="yellow")
            console.print(f"   maia agent calendar-sync {name}", style="dim")


async def handle_agent_list_scheduled(args):
    """
    List all scheduled agents.

    Usage:
        maia agent list-scheduled
    """
    from promaia.cli.schedule_grid_selector import schedule_to_string

    agents = load_agents()

    if not agents:
        print("No scheduled agents configured")
        return

    print(f"\n🤖 Scheduled Agents ({len(agents)}):\n")

    tracker = ExecutionTracker()

    for agent in agents:
        status_emoji = "✅" if agent.enabled else "⏸️"
        calendar_emoji = " 📅" if agent.calendar_event_ids else ""
        print(f"{status_emoji}{calendar_emoji} {agent.name}")
        print(f"   Workspace: {agent.workspace}")

        # Show schedule or interval
        if agent.schedule:
            print(f"   Schedule: {len(agent.schedule)} runs/week")
        elif agent.interval_minutes:
            print(f"   Interval: every {agent.interval_minutes} minutes")

        if agent.calendar_event_ids:
            print(f"   Calendar: On Google Calendar")

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
    from promaia.cli.schedule_grid_selector import schedule_to_string

    agent = get_agent(args.name)

    if not agent:
        print(f"❌ Agent '{args.name}' not found")
        return

    tracker = ExecutionTracker()
    stats = tracker.get_agent_stats(agent.name)

    print(f"\n🤖 Agent: {agent.name}\n")

    print(f"Status: {'✅ Enabled' if agent.enabled else '⏸️  Disabled'}")
    print(f"Workspace: {agent.workspace}")

    # Show schedule or interval
    if agent.schedule:
        schedule_display = schedule_to_string(agent.schedule)
        print(f"Schedule: {len(agent.schedule)} runs/week")
        print(f"  {schedule_display}")
    elif agent.interval_minutes:
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


async def handle_calendar_sync(args):
    """
    Sync an agent to Google Calendar.

    Usage:
        maia agent calendar-sync <name>
    """
    from promaia.utils.display import print_text
    from promaia.gcal import get_calendar_manager
    from rich.console import Console

    console = Console()

    agent = get_agent(args.name)
    if not agent:
        console.print(f"❌ Agent '{args.name}' not found", style="red")
        return

    if not agent.schedule:
        console.print(f"❌ Agent '{args.name}' has no schedule", style="red")
        console.print("   Only schedule-based agents can be synced to calendar", style="dim")
        return

    print_text(f"\n📅 Syncing agent '{args.name}' to Google Calendar...\n", style="bold cyan")

    try:
        calendar_mgr = get_calendar_manager()

        # Remove existing events if any
        if agent.calendar_event_ids:
            console.print("Removing existing calendar events...", style="dim")
            calendar_mgr.delete_agent_events(args.name)

        # Create new events
        event_ids = calendar_mgr.create_agent_event(
            agent_name=agent.name,
            schedule=agent.schedule,
            agent_config=agent.to_dict()
        )

        if event_ids:
            # Update agent config with event IDs
            agent.calendar_event_ids = event_ids
            save_agent(agent)

            console.print(f"\n✅ Agent '{args.name}' synced to Google Calendar!", style="green")
            console.print(f"   Created {len(agent.schedule)} recurring event(s)", style="dim")
            console.print(f"   View in your calendar: https://calendar.google.com", style="dim")
        else:
            console.print(f"\n❌ Failed to sync agent to calendar", style="red")

    except Exception as e:
        console.print(f"\n❌ Error: {e}", style="red")
        import traceback
        traceback.print_exc()


async def handle_calendar_remove(args):
    """
    Remove an agent from Google Calendar.

    Usage:
        maia agent calendar-remove <name>
    """
    from promaia.utils.display import print_text
    from promaia.gcal import get_calendar_manager
    from rich.console import Console

    console = Console()

    agent = get_agent(args.name)
    if not agent:
        console.print(f"❌ Agent '{args.name}' not found", style="red")
        return

    if not agent.calendar_event_ids:
        console.print(f"⚠️  Agent '{args.name}' is not on Google Calendar", style="yellow")
        return

    print_text(f"\n📅 Removing agent '{args.name}' from Google Calendar...\n", style="bold cyan")

    try:
        calendar_mgr = get_calendar_manager()
        success = calendar_mgr.delete_agent_events(args.name)

        if success:
            # Clear event IDs from agent config
            agent.calendar_event_ids = None
            save_agent(agent)

            console.print(f"\n✅ Agent '{args.name}' removed from calendar", style="green")
        else:
            console.print(f"\n❌ Failed to remove agent from calendar", style="red")

    except Exception as e:
        console.print(f"\n❌ Error: {e}", style="red")


async def handle_calendar_list(args):
    """
    List all agents on Google Calendar.

    Usage:
        maia agent calendar-list
    """
    from promaia.utils.display import print_text
    from promaia.gcal import get_calendar_manager
    from rich.console import Console
    from rich.table import Table

    console = Console()

    print_text("\n📅 Agents on Google Calendar\n", style="bold cyan")

    try:
        calendar_mgr = get_calendar_manager()
        events = calendar_mgr.list_agent_events()

        if not events:
            console.print("No agents found on Google Calendar", style="yellow")
            console.print("\nUse 'maia agent calendar-sync <name>' to add an agent", style="dim")
            return

        # Create table
        table = Table(title=f"Found {len(events)} agent event(s)")
        table.add_column("Agent", style="cyan")
        table.add_column("Recurrence", style="white")
        table.add_column("Event ID", style="dim")

        for event in events:
            props = event.get('extendedProperties', {}).get('private', {})
            agent_name = props.get('agent_name', 'Unknown')
            recurrence = event.get('recurrence', ['One-time'])[0]
            event_id = event['id'][:12] + "..."

            table.add_row(agent_name, recurrence, event_id)

        console.print(table)
        console.print("\n💡 View full calendar: https://calendar.google.com", style="dim")

    except Exception as e:
        console.print(f"❌ Error: {e}", style="red")


async def handle_sync_prompts(args):
    """
    Sync all Notion-backed prompts with their source pages.

    Usage:
        maia agent sync-prompts
        maia agent sync-prompts --workspace <workspace>
    """
    from promaia.utils.display import print_text
    from promaia.cli.notion_prompt_manager import sync_all_notion_prompts
    from rich.console import Console

    console = Console()

    workspace = getattr(args, 'workspace', None)

    print_text("\n🔄 Syncing Notion-backed prompts...\n", style="bold cyan")

    try:
        results = await sync_all_notion_prompts(workspace=workspace)

        # Display results
        if results['synced']:
            console.print(f"\n✅ Synced {len(results['synced'])} prompt(s):", style="green")
            for filename in results['synced']:
                console.print(f"  ✓ {filename}", style="dim")

        if results['failed']:
            console.print(f"\n❌ Failed to sync {len(results['failed'])} prompt(s):", style="red")
            for filename in results['failed']:
                console.print(f"  ✗ {filename}", style="dim")

        if results['skipped']:
            console.print(f"\n⏭️  Skipped {len(results['skipped'])} file(s) (not Notion-backed or sync disabled)", style="yellow")

        if not results['synced'] and not results['failed']:
            console.print("No Notion-backed prompts found to sync", style="yellow")

    except Exception as e:
        console.print(f"\n❌ Error syncing prompts: {e}", style="red")
        import traceback
        traceback.print_exc()


def add_scheduled_agent_commands(agent_subparsers):
    """Add scheduled agent commands to the agent subparser.

    Args:
        agent_subparsers: The subparsers object from the 'agent' command
    """
    # Add command
    add_parser = agent_subparsers.add_parser('add', help='Create a new scheduled agent')
    add_parser.set_defaults(func=handle_agent_add)

    # List command (for scheduled agents)
    list_scheduled_parser = agent_subparsers.add_parser('list-scheduled', help='List all scheduled agents')
    list_scheduled_parser.set_defaults(func=handle_agent_list_scheduled)

    # Run command (for scheduled agents)
    run_scheduled_parser = agent_subparsers.add_parser('run-scheduled', help='Manually run a scheduled agent')
    run_scheduled_parser.add_argument('name', help='Agent name')
    run_scheduled_parser.set_defaults(func=handle_agent_run_scheduled)

    # Logs command (for scheduled agents)
    logs_scheduled_parser = agent_subparsers.add_parser('logs-scheduled', help='View execution logs for scheduled agent')
    logs_scheduled_parser.add_argument('name', help='Agent name')
    logs_scheduled_parser.add_argument('--limit', '-l', type=int, default=20, help='Number of logs to show')
    logs_scheduled_parser.set_defaults(func=handle_agent_logs_scheduled)

    # Remove command (for scheduled agents)
    remove_scheduled_parser = agent_subparsers.add_parser('remove-scheduled', help='Remove a scheduled agent')
    remove_scheduled_parser.add_argument('name', help='Agent name')
    remove_scheduled_parser.add_argument('--yes', '-y', action='store_true', help='Skip confirmation')
    remove_scheduled_parser.set_defaults(func=handle_agent_remove_scheduled)

    # Enable command
    enable_parser = agent_subparsers.add_parser('enable', help='Enable a scheduled agent')
    enable_parser.add_argument('name', help='Agent name')
    enable_parser.set_defaults(func=handle_agent_enable)

    # Disable command
    disable_parser = agent_subparsers.add_parser('disable', help='Disable a scheduled agent')
    disable_parser.add_argument('name', help='Agent name')
    disable_parser.set_defaults(func=handle_agent_disable)

    # Info command (for scheduled agents)
    info_scheduled_parser = agent_subparsers.add_parser('info-scheduled', help='Show scheduled agent details')
    info_scheduled_parser.add_argument('name', help='Agent name')
    info_scheduled_parser.set_defaults(func=handle_agent_info_scheduled)

    # Scheduler commands
    scheduler_start_parser = agent_subparsers.add_parser('scheduler-start', help='Start the agent scheduler daemon')
    scheduler_start_parser.set_defaults(func=handle_scheduler_start)

    scheduler_stop_parser = agent_subparsers.add_parser('scheduler-stop', help='Stop the agent scheduler daemon')
    scheduler_stop_parser.set_defaults(func=handle_scheduler_stop)

    scheduler_status_parser = agent_subparsers.add_parser('scheduler-status', help='Check scheduler status')
    scheduler_status_parser.set_defaults(func=handle_scheduler_status)

    # Sync prompts command
    sync_prompts_parser = agent_subparsers.add_parser('sync-prompts', help='Sync Notion-backed prompts')
    sync_prompts_parser.add_argument('--workspace', '-w', help='Workspace for auth context')
    sync_prompts_parser.set_defaults(func=handle_sync_prompts)

    # Calendar commands
    calendar_sync_parser = agent_subparsers.add_parser('calendar-sync', help='Sync agent to Google Calendar')
    calendar_sync_parser.add_argument('name', help='Agent name')
    calendar_sync_parser.set_defaults(func=handle_calendar_sync)

    calendar_remove_parser = agent_subparsers.add_parser('calendar-remove', help='Remove agent from Google Calendar')
    calendar_remove_parser.add_argument('name', help='Agent name')
    calendar_remove_parser.set_defaults(func=handle_calendar_remove)

    calendar_list_parser = agent_subparsers.add_parser('calendar-list', help='List agents on Google Calendar')
    calendar_list_parser.set_defaults(func=handle_calendar_list)
