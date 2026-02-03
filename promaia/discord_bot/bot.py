"""
Discord bot for Promaia - Interactive AI assistant in Discord servers.

This module implements a Discord bot that can:
- Listen for mentions and commands
- Process messages with Promaia's AI
- Respond in Discord channels
- Maintain conversation context
"""
import os
import json
import logging
import asyncio
from datetime import datetime
from typing import Dict, Any, List, Optional
from pathlib import Path

try:
    import discord
    from discord.ext import commands
except ImportError:
    print("Discord bot requires discord.py")
    print("Install with: pip install discord.py")
    raise

logger = logging.getLogger(__name__)


class PromaiaBot(commands.Bot):
    """Discord bot for Promaia AI assistant."""

    def __init__(self, workspace: str = "koii", **kwargs):
        """
        Initialize Promaia Discord bot.

        Args:
            workspace: Workspace to use for credentials and context
            **kwargs: Additional arguments passed to commands.Bot
        """
        # Set up intents
        intents = discord.Intents.default()
        intents.message_content = True
        intents.guilds = True
        intents.guild_messages = True
        intents.members = True

        # Initialize bot with command prefix
        super().__init__(
            command_prefix=self._get_prefix,
            intents=intents,
            **kwargs
        )

        self.workspace = workspace
        self.config = self._load_config()

        # Track conversation context per channel (legacy)
        self.conversation_context: Dict[int, List[Dict]] = {}

        # Load AI interface
        from promaia.chat.interface import ChatInterface
        self.ai = ChatInterface()
        
        # Initialize unified conversation manager
        from promaia.agents.conversation_manager import ConversationManager
        from promaia.agents.messaging.discord_platform import DiscordPlatform
        
        self.conv_manager = ConversationManager()
        
        # Register Discord platform (will be initialized with actual token when bot starts)
        self.discord_platform = None  # Lazy init after bot login

    def _load_config(self) -> Dict[str, Any]:
        """Load bot configuration from credentials file."""
        config_path = Path("credentials") / self.workspace / "discord_credentials.json"

        if not config_path.exists():
            raise FileNotFoundError(
                f"Discord credentials not found at {config_path}\n"
                f"Run: maia workspace discord-setup {self.workspace}"
            )

        with open(config_path) as f:
            return json.load(f)

    async def _get_prefix(self, bot, message):
        """
        Determine command prefix dynamically.
        Supports: !maia, @mention, or 'maia' keyword
        """
        prefixes = ['!maia ', '!promaia ', 'maia ', 'promaia ']
        return prefixes

    async def on_ready(self):
        """Called when bot successfully connects to Discord."""
        logger.info(f"Promaia bot logged in as {self.user} (ID: {self.user.id})")
        logger.info(f"Connected to {len(self.guilds)} servers")

        # Initialize Discord platform for conversation manager
        from promaia.agents.messaging.discord_platform import DiscordPlatform
        
        if not self.discord_platform:
            bot_token = os.environ.get('DISCORD_BOT_TOKEN') or self.config.get('bot_token')
            if bot_token:
                self.discord_platform = DiscordPlatform(bot_token=bot_token)
                self.conv_manager.register_platform('discord', self.discord_platform)
                logger.info("Discord platform registered with conversation manager")

        # Set bot status
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.listening,
                name="@mentions and !maia commands"
            )
        )

    async def on_message(self, message: discord.Message):
        """
        Handle incoming messages.

        Responds to:
        - Direct mentions: @Promaia how are you?
        - Commands: !maia summarize this channel
        - Keywords in configured channels
        """
        # Ignore messages from the bot itself
        if message.author == self.user:
            return

        # Ignore messages from other bots (optional)
        if message.author.bot:
            return

        # Check if bot was mentioned or command was used
        is_mention = self.user.mentioned_in(message)
        is_command = message.content.lower().startswith(('!maia', '!promaia', 'maia ', 'promaia '))

        if is_mention or is_command:
            await self._handle_ai_request(message)

        # Process commands
        await self.process_commands(message)

    async def _handle_ai_request(self, message: discord.Message):
        """
        Process a message that requests AI assistance.
        
        First checks for active conversation managed by unified conversation manager.
        Falls back to legacy behavior if no active conversation.

        Args:
            message: Discord message to process
        """
        try:
            # Extract the actual query (remove mention/command prefix)
            query = message.content

            # Remove bot mentions
            query = query.replace(f'<@{self.user.id}>', '').strip()
            query = query.replace(f'<@!{self.user.id}>', '').strip()

            # Remove command prefixes
            for prefix in ['!maia', '!promaia', 'maia', 'promaia']:
                if query.lower().startswith(prefix):
                    query = query[len(prefix):].strip()
                    break

            if not query:
                await message.reply("How can I help you?")
                return
            
            # Check if this is part of an active conversation (unified manager)
            conversation = await self.conv_manager.get_active_conversation(
                platform='discord',
                channel_id=str(message.channel.id),
                user_id=str(message.author.id)
            )
            
            if conversation:
                # Process through unified conversation manager
                logger.info(f"Processing message in managed conversation {conversation.conversation_id}")
                
                async with message.channel.typing():
                    response = await self.conv_manager.handle_user_message(
                        conversation_id=conversation.conversation_id,
                        user_message=query,
                        user_id=str(message.author.id)
                    )
                
                # Send response
                if len(response) > 2000:
                    chunks = self._split_message(response)
                    for chunk in chunks:
                        await message.reply(chunk)
                else:
                    await message.reply(response)
                
                return
            
            # No active conversation - use legacy behavior
            logger.debug("No active conversation, using legacy AI request handling")
            
            # Show typing indicator
            async with message.channel.typing():
                # Get conversation context for this channel (legacy)
                channel_id = message.channel.id
                if channel_id not in self.conversation_context:
                    self.conversation_context[channel_id] = []

                # Add user message to context
                self.conversation_context[channel_id].append({
                    "role": "user",
                    "content": query,
                    "author": str(message.author),
                    "timestamp": message.created_at.isoformat()
                })

                # Keep only last 10 messages for context
                self.conversation_context[channel_id] = self.conversation_context[channel_id][-10:]

                # Get AI response
                response = await self._get_ai_response(query, channel_id, message)

                # Split long responses (Discord has 2000 char limit)
                if len(response) > 2000:
                    chunks = self._split_message(response)
                    for chunk in chunks:
                        await message.reply(chunk)
                else:
                    await message.reply(response)

                # Add bot response to context
                self.conversation_context[channel_id].append({
                    "role": "assistant",
                    "content": response,
                    "timestamp": datetime.now().isoformat()
                })

        except Exception as e:
            logger.error(f"Error handling AI request: {e}", exc_info=True)
            await message.reply(f"Sorry, I encountered an error: {str(e)}")

    async def _get_ai_response(self, query: str, channel_id: int, message: discord.Message) -> str:
        """
        Get AI response for a query with channel context.

        Args:
            query: User's question/request
            channel_id: Discord channel ID for context
            message: Original Discord message

        Returns:
            AI generated response
        """
        try:
            # Build context from conversation history
            context_messages = self.conversation_context.get(channel_id, [])

            # Add channel/server context
            context_info = f"Discord Server: {message.guild.name if message.guild else 'DM'}\n"
            context_info += f"Channel: {message.channel.name if hasattr(message.channel, 'name') else 'DM'}\n"
            context_info += f"User: {message.author.name}\n\n"

            # Format conversation history
            history_context = ""
            for msg in context_messages[-5:]:  # Last 5 messages
                role = "User" if msg["role"] == "user" else "Assistant"
                history_context += f"{role}: {msg['content']}\n"

            # Combine contexts
            full_prompt = f"{context_info}\nRecent conversation:\n{history_context}\n\nCurrent query: {query}"

            # Get response from AI interface
            # TODO: Integrate with actual ChatInterface
            # For now, use a simple response
            response = await self._simple_ai_response(query, full_prompt)

            return response

        except Exception as e:
            logger.error(f"Error getting AI response: {e}", exc_info=True)
            return f"I encountered an error processing your request: {str(e)}"

    async def _simple_ai_response(self, query: str, context: str) -> str:
        """
        Generate a simple AI response.
        TODO: Replace with actual ChatInterface integration.

        Args:
            query: User query
            context: Full context including conversation history

        Returns:
            Response string
        """
        # Placeholder implementation
        # In production, this should use promaia.chat.interface.ChatInterface

        if "hello" in query.lower() or "hi" in query.lower():
            return "Hello! I'm Promaia, your AI assistant. How can I help you today?"
        elif "help" in query.lower():
            return (
                "I can help you with:\n"
                "• Answering questions about your data\n"
                "• Summarizing Discord conversations\n"
                "• Searching through your knowledge base\n"
                "• General assistance\n\n"
                "Just mention me or use `!maia <your question>`"
            )
        else:
            return (
                f"I received your query: '{query}'\n\n"
                "Note: Full AI integration is in progress. "
                "I'll soon be able to provide detailed responses!"
            )

    def _split_message(self, text: str, max_length: int = 2000) -> List[str]:
        """
        Split a long message into chunks that fit Discord's character limit.

        Args:
            text: Text to split
            max_length: Maximum length per chunk (default: 2000)

        Returns:
            List of message chunks
        """
        if len(text) <= max_length:
            return [text]

        chunks = []
        current_chunk = ""

        # Split by paragraphs first
        paragraphs = text.split('\n\n')

        for para in paragraphs:
            if len(current_chunk) + len(para) + 2 <= max_length:
                current_chunk += para + '\n\n'
            else:
                if current_chunk:
                    chunks.append(current_chunk.strip())

                # If paragraph itself is too long, split by sentences
                if len(para) > max_length:
                    sentences = para.split('. ')
                    for sentence in sentences:
                        if len(current_chunk) + len(sentence) + 2 <= max_length:
                            current_chunk += sentence + '. '
                        else:
                            if current_chunk:
                                chunks.append(current_chunk.strip())
                            current_chunk = sentence + '. '
                else:
                    current_chunk = para + '\n\n'

        if current_chunk:
            chunks.append(current_chunk.strip())

        return chunks

    @commands.command(name='ping')
    async def ping(self, ctx):
        """Check if bot is responsive."""
        latency = round(self.latency * 1000)
        await ctx.reply(f"Pong! Latency: {latency}ms")

    @commands.command(name='status')
    async def status(self, ctx):
        """Get bot status and information."""
        embed = discord.Embed(
            title="Promaia Bot Status",
            color=discord.Color.blue(),
            timestamp=datetime.now()
        )

        embed.add_field(name="Servers", value=len(self.guilds), inline=True)
        embed.add_field(name="Latency", value=f"{round(self.latency * 1000)}ms", inline=True)
        embed.add_field(name="Workspace", value=self.workspace, inline=True)

        await ctx.reply(embed=embed)

    @commands.command(name='clear')
    async def clear_context(self, ctx):
        """Clear conversation context for this channel."""
        channel_id = ctx.channel.id
        if channel_id in self.conversation_context:
            del self.conversation_context[channel_id]
            await ctx.reply("Conversation context cleared for this channel.")
        else:
            await ctx.reply("No conversation context to clear.")


async def run_bot(workspace: str = "koii", token: Optional[str] = None):
    """
    Start the Promaia Discord bot.

    Args:
        workspace: Workspace to use for configuration
        token: Optional bot token (if not in credentials file)
    """
    bot = PromaiaBot(workspace=workspace)

    # Get token from parameter or config
    if not token:
        token = bot.config.get("bot_token")

    if not token:
        raise ValueError("No Discord bot token provided")

    try:
        await bot.start(token)
    except KeyboardInterrupt:
        logger.info("Bot shutdown requested")
        await bot.close()
    except Exception as e:
        logger.error(f"Bot error: {e}", exc_info=True)
        await bot.close()
        raise


if __name__ == "__main__":
    # For testing: python -m promaia.discord.bot
    import sys

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    workspace = sys.argv[1] if len(sys.argv) > 1 else "koii"

    print(f"Starting Promaia Discord bot for workspace: {workspace}")
    asyncio.run(run_bot(workspace=workspace))
