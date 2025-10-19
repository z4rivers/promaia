"""
Mail CLI Commands - Command handlers for maia mail feature.

Commands:
- maia mail [-ws workspace] - Review drafts (default)
- maia mail -p [-ws workspace] - Process new emails then review
"""
import asyncio
import logging
import traceback
from typing import List

from promaia.utils.display import print_text, print_separator

logger = logging.getLogger(__name__)


async def handle_mail(args):
    """
    Handle 'maia mail' command.
    
    Args:
        args: Parsed command-line arguments
    """
    from promaia.config.workspaces import get_workspace_manager
    from promaia.mail.processor import EmailProcessor
    from promaia.mail.review_ui import EmailReviewUI
    
    # Set logging level based on verbose flag
    if hasattr(args, 'verbose') and args.verbose:
        logging.basicConfig(level=logging.DEBUG, force=True)
        logger.setLevel(logging.DEBUG)
        # Also set for all promaia loggers
        logging.getLogger('promaia').setLevel(logging.DEBUG)
    
    try:
        # Determine workspaces
        workspace_manager = get_workspace_manager()
        
        # Check if user explicitly specified workspace(s)
        explicit_workspaces = hasattr(args, 'workspaces') and args.workspaces
        
        if explicit_workspaces:
            workspaces = args.workspaces
        else:
            # Default to default workspace
            default_workspace = workspace_manager.get_default_workspace()
            if not default_workspace:
                print_text("❌ No default workspace configured", style="red")
                print_text("Use -ws to specify a workspace", style="dim")
                return
            workspaces = [default_workspace]
        
        # Validate workspaces
        for workspace in workspaces:
            if not workspace_manager.validate_workspace(workspace):
                print_text(f"❌ Invalid workspace: {workspace}", style="red")
                return
        
        print_separator()
        print_text("📬 Maia Mail - Intelligent Email Response System", style="bold cyan")
        print_text(f"Workspace(s): {', '.join(workspaces)}", style="dim")
        print()
        
        # Process if requested
        if hasattr(args, 'process') and args.process:
            print_text("🔄 Processing new emails from last 72 hours...", style="cyan")
            print()
            
            processor = EmailProcessor()
            count = await processor.process_new_emails(workspaces, hours_back=72)
            
            print()
            if count > 0:
                print_text(f"✅ Generated {count} draft(s)", style="green")
            else:
                print_text("✅ No new emails requiring response", style="green")
            print()
            
            # If only processing (no workspace specified), exit here to preserve logs
            if not explicit_workspaces:
                print_text("💡 Use 'maia mail -ws [workspace]' to review drafts", style="dim")
                print_separator()
                return
        
        # Launch review UI (only if workspace was specified or not in process-only mode)
        print_text("📋 Launching review interface...", style="cyan")
        print()
        
        review_ui = EmailReviewUI()
        await review_ui.launch_review(workspaces)
        
        print()
        print_separator()
        print_text("👋 Thanks for using Maia Mail!", style="cyan")
        
    except KeyboardInterrupt:
        print()
        print_text("\n\n↩️  Cancelled by user\n", style="yellow")
    
    except Exception as e:
        logger.error(f"❌ Error in mail command: {e}")
        print_text(f"\n❌ Error: {e}\n", style="red")
        import traceback
        if logger.level <= logging.DEBUG:
            traceback.print_exc()


def add_mail_commands(subparsers):
    """
    Add mail commands to CLI.
    
    Args:
        subparsers: The subparsers object from argparse
    """
    mail_parser = subparsers.add_parser(
        'mail',
        help='Intelligent email response system',
        description='Process and review email drafts. Examples: "maia mail -ws trass", "maia mail -p -ws trass"'
    )
    
    mail_parser.add_argument(
        '-ws', '--workspace',
        action='append',
        dest='workspaces',
        help='Workspace(s) to process (default: default workspace). Can be specified multiple times. Usage: -ws workspace_name'
    )
    
    mail_parser.add_argument(
        '-p', '--process',
        action='store_true',
        help='Process new emails from last 72 hours before reviewing (generates drafts for new threads)'
    )
    
    mail_parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Enable verbose debug logging'
    )
    
    mail_parser.set_defaults(func=handle_mail)

