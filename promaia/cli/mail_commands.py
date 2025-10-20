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
        # Check if user wants to open a specific draft directly
        if hasattr(args, 'draft') and args.draft:
            from promaia.mail.draft_chat import DraftChatInterface
            from promaia.mail.draft_manager import DraftManager
            
            # Get draft to determine workspace
            draft_manager = DraftManager()
            draft = draft_manager.get_draft(args.draft)
            
            if not draft:
                print_text(f"❌ Draft {args.draft} not found", style="red")
                return
            
            workspace = draft.get('workspace')
            if not workspace:
                print_text("❌ Draft has no workspace", style="red")
                return
            
            # Launch draft chat directly
            chat = DraftChatInterface(draft_id=args.draft, workspace=workspace)
            
            # Note: message_context is True by default in DraftChatInterface
            # The -mc flag is just to explicitly enable it in the command string
            # It's always enabled unless explicitly disabled via /e in the chat
            
            await chat.run_chat_loop()
            return
        
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
        
        # Refresh existing drafts if requested
        if hasattr(args, 'refresh') and args.refresh:
            days = args.days if hasattr(args, 'days') else 7
            print_text(f"🔄 Refreshing drafts from last {days} days...", style="cyan")
            print_text("   (Rebuilding context, thread, and replies for pending/unsure/skipped)", style="dim")
            print()
            
            processor = EmailProcessor()
            count = await processor.refresh_drafts(workspaces, days_back=days)
            
            print()
            if count > 0:
                print_text(f"✅ Refreshed {count} draft(s)", style="green")
            else:
                print_text("✅ No drafts to refresh", style="green")
            print()
            
            # If only refreshing (no workspace specified), exit here to preserve logs
            if not explicit_workspaces:
                print_text("💡 Use 'maia mail -ws [workspace]' to review drafts", style="dim")
                print_separator()
                return
        
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
        if hasattr(args, 'history') and args.history:
            print_text("📋 Launching history view...", style="cyan")
        else:
            print_text("📋 Launching review interface...", style="cyan")
        print()
        
        review_ui = EmailReviewUI()
        start_in_history = hasattr(args, 'history') and args.history
        await review_ui.launch_review(workspaces, start_in_history=start_in_history)
        
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
        '--draft',
        type=str,
        help='Open a specific draft directly by ID (e.g., --draft abc123)'
    )
    
    mail_parser.add_argument(
        '-mc', '--message-context',
        action='store_true',
        dest='message_context',
        help='Enable message context in draft chat (includes email thread and related context)'
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
    
    mail_parser.add_argument(
        '--history',
        action='store_true',
        dest='history',
        help='Start in history view (completed messages) instead of queue'
    )
    
    mail_parser.add_argument(
        '-r', '--refresh',
        action='store_true',
        help='Refresh existing drafts (rebuilds context, thread, and replies for pending/unsure/skipped)'
    )
    
    mail_parser.add_argument(
        '--days',
        type=int,
        default=7,
        help='Number of days to look back for refresh (default: 7). Only used with --refresh'
    )
    
    mail_parser.set_defaults(func=handle_mail)

