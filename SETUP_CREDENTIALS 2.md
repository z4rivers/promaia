# Credentials Setup Guide

This guide explains how to set up your API keys and credentials for Promaia.

## Quick Setup

### 1. Create Local Config Files

Copy the template files and add your actual API keys:

```bash
# Copy MCP servers config
cp mcp_servers.json.template mcp_servers.json

# Copy main config (if you don't have it already)
cp promaia.config.template.json promaia.config.json
```

### 2. Set Environment Variables

Create a `.env` file in the project root (it's already gitignored):

```bash
# Notion API Keys
export NOTION_KOII_API_KEY="your-notion-koii-api-key-here"
export NOTION_TRASS_API_KEY="your-notion-trass-api-key-here"

# AI Provider API Keys
export ANTHROPIC_API_KEY="your-anthropic-api-key"
export OPENAI_API_KEY="your-openai-api-key"
export GOOGLE_API_KEY="your-google-api-key"
export LLAMA_API_KEY="your-llama-api-key"  # Optional for local Llama

# Search API
export PERPLEXITY_API_KEY="your-perplexity-api-key"

# Discord (if using Discord integration)
export DISCORD_BOT_TOKEN="your-discord-bot-token"
```

### 3. Gmail OAuth Credentials

For Gmail integration, you need to set up OAuth credentials:

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. Enable the Gmail API
4. Create OAuth 2.0 credentials
5. Download the credentials JSON file
6. Save it to the appropriate workspace folder:
   - Koii workspace: `credentials/koii/gmail_credentials.json`
   - Trass workspace: `credentials/trass/gmail_credentials.json`

The first time you run the mail sync, it will open a browser for OAuth authorization and save the token automatically.

### 4. Discord Credentials (Optional)

If using Discord integration:

1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Create a new application
3. Go to the "Bot" section and create a bot
4. Copy the bot token
5. Save credentials to:
   - Koii workspace: `credentials/koii/discord_credentials.json`
   - Trass workspace: `credentials/trass/discord_credentials.json`

Format:
```json
{
  "token": "your-discord-bot-token",
  "guild_id": "your-discord-server-id"
}
```

## Security Notes

### Protected Files (Never Commit These)

The following files are automatically ignored by git:

- ✅ `mcp_servers.json` - Contains MCP server configurations with API keys
- ✅ `promaia.config.json` - Main config with workspace API keys
- ✅ `.env` and `.env.*` - Environment variables
- ✅ `credentials/**/*credentials*.json` - OAuth and API credentials
- ✅ `credentials/**/*token*.json` - OAuth tokens
- ✅ All `*.db` and `*.sqlite*` files - Databases may contain sensitive data

### Template Files (Safe to Commit)

These files are safe templates without real credentials:

- ✅ `mcp_servers.json.template`
- ✅ `promaia.config.template.json`
- ✅ `.env.template` or `.env.example`

## Verification

Check that your sensitive files are properly ignored:

```bash
# Should show which .gitignore rule is ignoring each file
git check-ignore -v mcp_servers.json promaia.config.json credentials/koii/gmail_credentials.json

# Should return empty (no tracked sensitive files)
git ls-files | grep -E "(credentials|token|secret)"
```

## Getting API Keys

### Notion
1. Go to https://www.notion.so/my-integrations
2. Create a new integration
3. Copy the "Internal Integration Token"
4. Share your Notion databases with the integration

### Anthropic (Claude)
1. Go to https://console.anthropic.com/
2. Navigate to API Keys
3. Create a new API key

### OpenAI (GPT)
1. Go to https://platform.openai.com/api-keys
2. Create a new API key

### Google (Gemini)
1. Go to https://makersuite.google.com/app/apikey
2. Create a new API key

### Perplexity
1. Go to https://www.perplexity.ai/settings/api
2. Generate an API key

## Troubleshooting

### "API key not found" errors

Make sure your environment variables are loaded:

```bash
# Check if variables are set
echo $NOTION_KOII_API_KEY
echo $ANTHROPIC_API_KEY

# Load from .env file
source .env

# Or use direnv (recommended)
direnv allow
```

### Gmail authentication issues

1. Delete the token file: `rm credentials/koii/gmail_token.json`
2. Run the mail sync again to re-authenticate
3. Make sure your OAuth credentials are valid

### Config file not found

If you get "config file not found" errors:

```bash
# Make sure you copied the templates
ls -la mcp_servers.json promaia.config.json

# If missing, copy from templates
cp mcp_servers.json.template mcp_servers.json
cp promaia.config.template.json promaia.config.json
```

## Need Help?

Check the main README.md or create an issue if you encounter problems.
