# Promaia Discord Bot

Promaia can now interact with people in Discord! The bot responds to mentions and commands, allowing users to ask questions and get AI-powered responses directly in Discord channels.

## Features

### 🎯 Core Capabilities
- **@Mention Responses**: Tag @Promaia anywhere to get an AI response
- **Command Support**: Use `!maia` or `!promaia` prefix for commands
- **Conversation Context**: Maintains context within each channel (last 10 messages)
- **Long Message Handling**: Automatically splits responses over 2000 characters
- **Multi-Server Support**: Works across multiple Discord servers simultaneously

### 📝 Supported Interactions

1. **Direct Mentions**
   ```
   @Promaia what's the weather like?
   @Promaia can you summarize this conversation?
   ```

2. **Commands**
   ```
   !maia help
   !maia status
   !maia ping
   !maia clear (clears conversation context)
   ```

3. **Natural Language**
   ```
   maia hello
   maia what can you do?
   ```

## Setup

### Prerequisites
- Discord bot token (from Discord Developer Portal)
- Bot must have the following permissions:
  - Read Messages/View Channels
  - Send Messages
  - Read Message History
  - Add Reactions (optional)

### Configuration

1. **Create Discord Bot** (if not already done):
   ```bash
   # Visit https://discord.com/developers/applications
   # Create a new application
   # Go to Bot section and create a bot
   # Enable "Message Content Intent" under Privileged Gateway Intents
   # Copy the bot token
   ```

2. **Set up credentials**:
   ```bash
   # Credentials should already exist at:
   # credentials/koii/discord_credentials.json

   # Format:
   {
     "bot_token": "YOUR_BOT_TOKEN_HERE",
     "server_id": "YOUR_SERVER_ID",
     "workspace": "koii"
   }
   ```

3. **Invite bot to server**:
   ```bash
   # Use OAuth2 URL Generator in Discord Developer Portal
   # Required scopes: bot
   # Required bot permissions:
   #   - Read Messages/View Channels
   #   - Send Messages
   #   - Read Message History
   ```

## Usage

### Starting the Bot

```bash
# Start bot for default workspace (koii)
maia discord-bot

# Start bot for specific workspace
maia discord-bot --workspace koii

# Start with custom token (overrides credentials file)
maia discord-bot --token YOUR_BOT_TOKEN
```

### In Discord

Once the bot is running:

1. **Get Help**:
   ```
   @Promaia help
   !maia help
   ```

2. **Check Status**:
   ```
   !maia status
   !maia ping
   ```

3. **Ask Questions**:
   ```
   @Promaia what's the latest from my emails?
   @Promaia can you summarize this channel?
   ```

4. **Clear Context** (useful for starting fresh):
   ```
   !maia clear
   ```

## Architecture

### Components

1. **PromaiaBot** (`promaia/discord/bot.py`):
   - Main bot class extending `discord.ext.commands.Bot`
   - Handles message events and command processing
   - Manages conversation context per channel
   - Integrates with Promaia AI interface

2. **CLI Integration** (`promaia/cli.py`):
   - `maia discord-bot` command
   - Workspace and token configuration
   - Async command handling

### How It Works

1. **Message Reception**:
   - Bot listens for all messages in channels it has access to
   - Filters for mentions (`@Promaia`) or command prefixes (`!maia`)
   - Ignores messages from bots (including itself)

2. **Context Management**:
   - Maintains separate conversation history per channel
   - Stores last 10 messages for context
   - Includes user info and timestamps

3. **AI Processing** (TODO):
   - Currently uses placeholder responses
   - Will integrate with `promaia.chat.interface.ChatInterface`
   - Will support querying user's knowledge base

4. **Response Delivery**:
   - Replies to the original message
   - Splits long responses (>2000 chars)
   - Shows typing indicator while processing

## Current Limitations

### 🚧 In Development

1. **AI Integration**: Bot currently uses placeholder responses. Full ChatInterface integration is coming soon.

2. **Knowledge Base Access**: Bot doesn't yet query user's databases (Gmail, Notion, etc.)

3. **Advanced Commands**: Limited command set (help, status, ping, clear)

### Future Enhancements

- [ ] Full ChatInterface integration
- [ ] Database/knowledge base querying
- [ ] Voice channel support
- [ ] Reaction-based interactions
- [ ] Role-based permissions
- [ ] Custom command registration
- [ ] Webhook support for async updates
- [ ] Rich embeds for formatted responses
- [ ] Image/file handling

## Troubleshooting

### Bot doesn't respond
1. Check bot is running: Look for "Promaia bot logged in" message
2. Verify bot has proper permissions in the channel
3. Ensure "Message Content Intent" is enabled in Discord Developer Portal
4. Check bot credentials in `credentials/[workspace]/discord_credentials.json`

### "Module not found" error
```bash
# Install discord.py if not already installed
pip install discord.py
```

### Bot responds but times out
- Check network connectivity
- Verify bot token is valid
- Check Discord API status: https://discordstatus.com

### Context issues
```
# Clear context for a channel
!maia clear
```

## Development

### Testing Locally

```bash
# Run with debug logging
PYTHONPATH=/Users/kb20250422/Documents/dev/promaia python3 -m promaia.discord.bot koii

# Or via CLI
maia discord-bot --workspace koii
```

### Adding New Commands

```python
# In promaia/discord/bot.py

@commands.command(name='mycommand')
async def my_command(self, ctx):
    """My custom command."""
    await ctx.reply("This is my custom response!")
```

### Extending AI Integration

```python
# Replace _simple_ai_response() with actual ChatInterface
from promaia.chat.interface import ChatInterface

async def _get_ai_response(self, query, channel_id, message):
    # Use ChatInterface to process query
    chat = ChatInterface()
    response = await chat.process_query(query, context=...)
    return response
```

## Production Deployment

### Running as a Service

Consider using systemd, docker, or a process manager:

```bash
# Example systemd service
[Unit]
Description=Promaia Discord Bot
After=network.target

[Service]
Type=simple
User=promaia
WorkingDirectory=/path/to/promaia
ExecStart=/path/to/promaia/venv/bin/maia discord-bot --workspace koii
Restart=always

[Install]
WantedBy=multi-user.target
```

### Monitoring

- Bot logs connection status and errors
- Use `!maia status` to check bot health
- Monitor Discord API rate limits

## Security Considerations

1. **Token Security**: Never commit bot tokens to git
2. **Permissions**: Grant minimum required permissions
3. **Rate Limiting**: Bot respects Discord API rate limits
4. **Content Filtering**: Consider implementing content moderation
5. **User Privacy**: Conversation context is ephemeral (in-memory only)

## Support

For issues or questions:
1. Check logs for error messages
2. Review Discord Developer Portal for bot status
3. Verify credentials file is properly configured
4. Ensure bot has proper server permissions

## License

Part of the Promaia project.
