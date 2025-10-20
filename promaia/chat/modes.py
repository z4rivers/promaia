"""
Chat modes for specialized behaviors in maia chat.

Modes allow maia chat to support specialized workflows while maintaining
a unified architecture. Examples: email drafting, blog writing, code generation.
"""
import logging
import os
from typing import Dict, Optional, Callable
from datetime import datetime

logger = logging.getLogger(__name__)


class ChatMode:
    """Base class for chat modes."""
    
    def __init__(self, workspace: str):
        """
        Initialize chat mode.
        
        Args:
            workspace: Workspace name
        """
        self.workspace = workspace
    
    def get_system_prompt(self) -> Optional[str]:
        """
        Get system prompt for this mode.
        
        Override in subclass to provide custom system prompt.
        Return None to use default chat system prompt.
        
        Returns:
            System prompt string or None
        """
        return None
    
    def get_additional_commands(self) -> Dict[str, Callable]:
        """
        Get mode-specific commands.
        
        Override in subclass to add custom commands.
        
        Returns:
            Dict of command_name -> handler_function
        """
        return {}
    
    def get_welcome_message(self, context_breakdown: dict, **kwargs) -> Optional[str]:
        """
        Get custom welcome message for this mode.
        
        Override in subclass to customize welcome message.
        Return None to use default welcome.
        
        Args:
            context_breakdown: Dict of database_name -> count
            **kwargs: Additional mode-specific data
            
        Returns:
            Welcome message string or None
        """
        return None
    
    def should_enable_artifacts(self) -> bool:
        """
        Whether artifacts should be enabled for this mode.
        
        Returns:
            True to enable artifacts
        """
        return True


class DraftMode(ChatMode):
    """
    Email draft mode - specialized for email composition.
    
    Uses artifacts for email drafts and adds /send and /archive commands.
    """
    
    def __init__(
        self, 
        workspace: str, 
        draft_id: str,
        draft_data: dict,
        draft_manager,
        user_email: str
    ):
        """
        Initialize draft mode.
        
        Args:
            workspace: Workspace name
            draft_id: Draft ID
            draft_data: Draft data dict
            draft_manager: DraftManager instance
            user_email: User's email address
        """
        super().__init__(workspace)
        self.draft_id = draft_id
        self.draft_data = draft_data
        self.draft_manager = draft_manager
        self.user_email = user_email
    
    def get_system_prompt(self) -> Optional[str]:
        """
        Load maia_mail_prompt.md as system prompt.
        
        Returns:
            System prompt for email drafting
        """
        prompt_path = "prompts/maia_mail_prompt.md"
        
        if not os.path.exists(prompt_path):
            logger.warning(f"Draft mode prompt not found: {prompt_path}")
            return None
        
        try:
            with open(prompt_path, 'r', encoding='utf-8') as f:
                persona = f.read()
                
                # Fill in date/time variables
                from promaia.utils.timezone_utils import now_utc
                now = now_utc()
                persona = persona.format(
                    today_date=now.strftime("%B %d, %Y"),
                    current_time=now.strftime("%I:%M %p %Z")
                )
                
                logger.info(f"Loaded draft mode persona from '{prompt_path}'")
                return persona
        except Exception as e:
            logger.error(f"Failed to load draft mode persona: {e}")
            return None
    
    def get_additional_commands(self) -> Dict[str, Callable]:
        """
        Add /send and /archive commands for draft mode.
        
        Returns:
            Dict of draft-specific commands
        """
        return {
            '/send': self.handle_send,
            '/archive': self.handle_archive,
        }
    
    def get_welcome_message(self, context_breakdown: dict, **kwargs) -> Optional[str]:
        """
        Custom welcome for draft chat.
        
        Args:
            context_breakdown: Dict of database_name -> count
            **kwargs: Additional data (model_name, etc.)
            
        Returns:
            Welcome message for draft mode
        """
        from promaia.utils.display import print_text
        
        # Build command string
        cmd_parts = ["maia mail --draft", self.draft_id]
        if kwargs.get('message_context_enabled', True):
            cmd_parts.append("-mc")
        
        # Build the message components
        lines = []
        lines.append(("🐙 maia mail draft chat", "bold magenta"))
        lines.append((f"Query: {' '.join(cmd_parts)}", "dim"))
        lines.append(("", None))
        lines.append(("Context loaded:", "dim"))
        
        if kwargs.get('message_context_enabled', True) and context_breakdown:
            lines.append(("\tmessage-context", "dim"))
        
        for db_name, count in sorted(context_breakdown.items()):
            lines.append((f"\t{db_name}: {count}", "dim"))
        
        model_name = kwargs.get('model_name', 'Unknown')
        lines.append((f"Model: {model_name}", "dim"))
        lines.append(("", None))
        
        lines.append(("Available commands:", "dim"))
        lines.append(("  /send [#] - Send draft (default: latest)", "dim"))
        lines.append(("  /d - Toggle draft list view", "dim"))
        lines.append(("  /e - Edit context (sources, filters, message context)", "dim"))
        lines.append(("  /s - Sync databases in current context", "dim"))
        lines.append(("  /mcp [name] - Include MCP server context (e.g., /mcp search)", "dim"))
        lines.append(("  /archive or /a - Archive this email", "dim"))
        lines.append(("  /q - Return to draft list", "dim"))
        lines.append(("  /model - Switch model", "dim"))
        lines.append(("  /help - Show detailed help", "dim"))
        lines.append(("", None))
        
        # Return as text (will be printed by caller)
        message_parts = []
        for text, style in lines:
            message_parts.append(text)
        
        return "\n".join(message_parts)
    
    async def handle_send(self, artifact_manager, messages, context_state):
        """
        Handle /send command for drafts.
        
        Ports logic from draft_chat.py _handle_send_command
        
        Args:
            artifact_manager: ArtifactManager instance
            messages: Chat messages
            context_state: Chat context state
            
        Returns:
            True if should exit chat, False to continue
        """
        from promaia.utils.display import print_text
        from promaia.mail.recipient_selector import RecipientSelector
        from promaia.mail.gmail_sender import GmailSender
        from promaia.utils.timezone_utils import now_utc
        
        # Get the latest artifact (draft)
        if not artifact_manager or not artifact_manager.artifacts:
            print_text("❌ No draft to send", style="red")
            return False
        
        latest_artifact_id = max(artifact_manager.artifacts.keys())
        draft_to_send = artifact_manager.artifacts[latest_artifact_id]['content']
        
        # Show recipient selector
        selector = RecipientSelector(
            from_addr=self.draft_data.get('inbound_from', ''),
            to_addr=self.draft_data.get('inbound_to', ''),
            cc_addr=self.draft_data.get('inbound_cc', ''),
            thread_context=self.draft_data.get('thread_context', ''),
            user_email=self.user_email
        )
        
        print_text("\n📧 Select recipients for this email...", style="cyan")
        confirmed, recipients = await selector.run()
        
        if not confirmed:
            print_text("\n↩️  Send cancelled\n", style="cyan")
            return False
        
        if not recipients:
            print_text("\n❌ No recipients selected\n", style="red")
            return False
        
        print_text(f"\n✅ Sending to: {', '.join(recipients)}", style="green")
        
        # Format the draft
        from promaia.mail.response_generator import ResponseGenerator
        generator = ResponseGenerator()
        draft_to_send = generator._format_email_body(draft_to_send)
        
        # Safety confirmation
        print()
        print_text(f"⚠️  Ready to send Draft #{latest_artifact_id}", style="bold yellow")
        print_text(f"Subject: {self.draft_data['inbound_subject']}", style="yellow")
        print_text(f"\nType the first 5 characters of the subject to confirm: '{self.draft_data['safety_string']}'", style="yellow")
        print_text(f"Or type 'cancel' (or press Enter) to abort", style="dim")
        
        confirmation = input("\nConfirm: ").strip()
        
        if not confirmation or confirmation.lower() == 'cancel':
            print_text("\n↩️  Send cancelled\n", style="cyan")
            return False
        
        if confirmation != self.draft_data['safety_string']:
            print_text("\n❌ Confirmation failed\n", style="red")
            return False
        
        print_text("\n📤 Sending email...", style="cyan")
        
        # Send email
        sender = GmailSender(self.workspace, self.user_email)
        success = await sender.send_reply(
            thread_id=self.draft_data['thread_id'],
            message_id=self.draft_data['message_id'],
            subject=self.draft_data['draft_subject'],
            body_text=draft_to_send,
            recipients=recipients
        )
        
        if success:
            print_text("✅ Email sent!", style="green")
            self.draft_manager.mark_sent(self.draft_id)
            
            # Save to learning system
            from promaia.mail.learning_system import EmailResponseLearningSystem
            learning = EmailResponseLearningSystem(workspace=self.workspace)
            
            pattern = {
                "inbound": {
                    "from": self.draft_data['inbound_from'],
                    "subject": self.draft_data['inbound_subject'],
                    "body_snippet": self.draft_data['inbound_snippet'],
                },
                "response": {
                    "subject": self.draft_data['draft_subject'],
                    "body": draft_to_send,
                    "tone": "professional",
                    "length": len(draft_to_send.split())
                },
                "metadata": {
                    "workspace": self.workspace,
                    "ai_model": context_state.get('current_api', 'unknown'),
                    "timestamp": now_utc().isoformat()
                }
            }
            learning.save_successful_response(pattern)
            
            print()
            print_text("↩️  Returning to draft list...", style="cyan")
            print()
            return True
        else:
            print_text("❌ Failed to send\n", style="red")
            return False
    
    async def handle_archive(self):
        """
        Handle /archive command.
        
        Args:
            None
            
        Returns:
            True if should exit chat, False to continue
        """
        from promaia.utils.display import print_text
        
        self.draft_manager.update_draft_status(self.draft_id, 'archived')
        print_text("\n🗄️  Archived - cleared from your queue\n", style="green")
        return True

