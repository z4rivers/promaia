# Maia CLI Quick Reference

Maia is your personal AI assistant manager with powerful database synchronization, multi-source chat, and content generation capabilities.

**Note**: Maia now uses a hybrid storage architecture with optimized separate tables for each content type, providing faster queries and better natural language processing.

## Core Commands

### Database Management (Primary Interface)
```bash
# List all configured databases
maia database list

# Add a new database
maia database add --name stories --source-type notion --database-id abc123

# Test database connections
maia database test

# Sync databases with optional filters
maia database sync                                    # Sync all enabled databases
maia database sync --sources journal awakenings      # Sync specific databases
maia database sync --sources journal[date>-30d]      # Sync with filters

# Get database information
maia database info journal
maia database info journal --schema                  # Include schema details

# Remove a database
maia database remove old-database
```

### 🎮 Discord Integration

#### Setup & Configuration
```bash
# Configure Discord for a workspace
maia workspace discord-setup myworkspace --server-id YOUR_DISCORD_SERVER_ID

# Add Discord database
maia database add discord --type discord --id YOUR_SERVER_ID --workspace myworkspace

# Test Discord connectivity
maia discord debug-channels --workspace myworkspace
maia discord list-channels myworkspace

# Test sync with specific channel
maia database sync -s myworkspace.discord:1.channel_name=general
```

#### Interactive Browse Mode
```bash
# Browse Discord channels with visual TUI
maia sync -b workspace.discord                      # Interactive sync
maia chat -b workspace.discord                      # Interactive chat

# Browse multiple Discord databases
maia sync -b workspace.discord workspace.community_discord
maia chat -b workspace.discord workspace.yeeps_discord

# Browse with day specifications
maia sync -b workspace.discord:30                   # 30-day default filter
maia chat -b workspace.discord:7 workspace.yeeps_discord:14
```

#### Browser Controls
```
🎮 Discord Channel Browser

📂 My Team Server (workspace.discord)
    ☑ #📢・announcements (30 days)    # ← Selected with ☑
>>> ☐ #💬・general (7 days)          # ← Highlighted with >>>
    ☐ #🗞️・release-notes (14 days)

↑↓ Navigate  SPACE Toggle  D Cycle Days  ENTER Confirm  ESC Cancel
```

#### Direct Discord Sync
```bash
# Sync specific Discord channels
maia sync -s workspace.discord:7.channel_name=announcements
maia sync -s workspace.discord:30.author_name=admin

# Combined Discord and Notion sync
maia sync -s journal:5 -s workspace.discord:14.channel_name=general
```

### Multi-Source Chat & Sync
```bash
# Start chat with default settings
maia chat

# Chat with specific data sources
maia chat -s journal:7 -s awakenings:all
maia chat -s journal:30 -s cms:14

# Interactive Discord browse mode (NEW)
maia chat -b workspace.discord                      # Browse Discord channels
maia chat -b workspace.discord workspace.yeeps_discord # Multiple Discord databases
maia sync -b workspace.discord:30                   # Browse for sync with day filter

# Combined sources with Discord browse
maia chat -s journal:7 -b workspace.discord:14     # Mix Notion with Discord
maia sync -s journal:5 -b workspace.discord:30     # Combined sync

# Direct Discord specifications
maia chat -s workspace.discord:7.channel_name=announcements
maia sync -s workspace.discord:14.channel_name=general

# Advanced filtering (see docs/ENHANCED_FILTERING.md for complete guide)
maia chat -s journal -f 'journal:created_time>2025-01-01'
maia chat -s workspace.discord:7 -f 'workspace.discord:author_name=admin'

# Available in chat:
# /pull        - Sync all databases and reload context
# /days        - Change context days 
# /switch      - Change AI model (anthropic/openai/gemini)
# /clear       - Clear chat history
# /push        - Push conversation to Notion
# /quit        - Exit
```

### Content Generation
```bash
# Generate blog content
maia write
maia write --days 14 --prompt "Write about productivity"
maia write --no-push                                 # Save to drafts/ instead of Notion

# Set default AI model
maia model
```

## Legacy Commands (Preserved for Workflows)

### CMS Operations
```bash
# Pull CMS entries from Notion
maia cms pull
maia cms pull --days 30
maia cms pull --force

# Push draft to CMS
maia cms push
maia cms push --title "My Post" --draft path/to/file.md

# Sync with Webflow
maia cms sync --collection abc123
maia cms sync --force-update
```

### Newsletter
```bash
# Send eligible CMS pages to newsletter via Resend
# Automatically includes Notion cover photos (uses Webflow-hosted images when available)
maia newsletter send

# Alternative command alias
maia news send
```

### Subscriber Migration
```bash
# Migrate subscribers from MailerLite to Resend
maia migrate                                    # Migrate only active subscribers
maia migrate --include-unsubscribed             # Include unsubscribed subscribers
maia migrate --audience-name "My Newsletter"    # Specify custom audience name
maia migrate --batch-size 100                   # Adjust batch size for import
```

## Configuration

### Database Configuration
Configuration is stored in `promaia.config.json`:

```json
{
  "global": {
    "default_sync_days": 7,
    "default_output_directory": "data"
  },
  "databases": {
    "journal": {
      "source_type": "notion",
      "database_id": "your_database_id",
      "nickname": "journal",
      "description": "Personal journal entries",
      "sync_enabled": true,
      "include_properties": false,
      "default_days": 7,
      "output_directory": "data/journal"
    }
  }
}
```

### Environment Variables
```bash
# AI Model API Keys
export ANTHROPIC_API_KEY="your_key"
export OPENAI_API_KEY="your_key" 
export GOOGLE_API_KEY="your_key"

# Legacy database IDs (auto-migrated to config)
export NOTION_JOURNAL_DATABASE_ID="your_id"
export NOTION_CMS_DATABASE_ID="your_id"

# Newsletter settings (for email sending)
export RESEND_API_KEY="your_resend_api_key"
export RESEND_FROM_EMAIL="newsletter@yourdomain.com"
export RESEND_FROM_NAME="Your Name"
export RESEND_TEST_EMAIL="your_test_email@domain.com"

# Optional settings
export WEBFLOW_COLLECTION_ID="your_id"
export MAIA_DEBUG="1"                               # Enable debug mode
```

## Multi-Source Query Syntax

### Basic Source Specifications
```bash
# Format: database_name:days
-s journal:7                    # Last 7 days from journal
-s awakenings:all              # All entries from awakenings
-s cms:30                      # Last 30 days from CMS

# Discord sources
-s workspace.discord:7         # Last 7 days from Discord
-s workspace.discord:30.channel_name=announcements # Specific channel
-s workspace.yeeps_discord:14.author_name=admin    # Author filter

# Browse mode (interactive TUI)
-b workspace.discord           # Browse Discord channels
-b workspace.discord:30        # Browse with 30-day default
-b discord yeeps_discord       # Browse multiple databases
```

### Advanced Filtering (Database Sync)
```bash
# Date filters
maia database sync --sources journal[date>-30d]     # Last 30 days
maia database sync --sources cms[date>2024-01-01]   # After specific date

# Property filters
maia database sync --sources cms[status=published]   # Filter by property
maia database sync --sources stories[team=plush]     # Multiple filters supported
```

## Common Workflows

### Daily Journal & Team Sync
```bash
maia database sync journal                           # Sync journal database
maia chat -s journal:7                             # Chat with recent entries

# Discord team updates
maia sync -b team.discord:1                        # Sync yesterday's Discord
maia chat -b team.discord:1                        # Chat with recent team updates
```

### Team Communication Analysis
```bash
# Browse and sync team Discord channels
maia sync -b team.discord team.dev_discord
maia chat -s project_notes:14 -b team.discord:7    # Combine project notes with Discord

# Analyze specific channels
maia chat -s team.discord:7.channel_name=announcements
```

### Content Creation with Team Context
```bash
maia sync -s cms:7 -b team.discord:14              # Sync content and team discussions
maia write --prompt "Blog post based on recent team discussions"
maia cms push                                       # Push to CMS
```

### Multi-Source Analysis
```bash
# Traditional multi-source
maia chat -s journal:30 -s awakenings:all -s projects:14

# With Discord integration
maia chat -s journal:7 -s projects:14 -b team.discord:7 team.community_discord:14
```

### Weekly Team Retrospective
```bash
# Comprehensive team analysis
maia chat -s team_notes:7 -b team.discord:7 team.dev_discord:7
# Ask: "What were the key discussions and decisions this week?"
```

### Blog Publishing Pipeline
```bash
maia cms pull                                       # Pull latest CMS entries
maia cms sync                                       # Sync to Webflow
maia newsletter send                                # Send to email campaign with cover photos
```

## Debug and Help

```bash
# Enable debug mode
maia --debug <command>

# Get help for any command
maia --help
maia database --help
maia chat --help

# See detailed multi-source documentation
# docs/guides/MULTI_SOURCE_CHAT_GUIDE.md
```

## Performance Tips

- Use specific day filters rather than `:all` for faster loading
- Configure `sync_enabled: false` for databases you don't need regularly
- Use `maia database test` to verify connections before syncing
- Check `data/` directories for locally cached content

## Migration from Legacy Commands

The journal commands have been removed. Use the database system instead:

```bash
# Old (removed)
maia journal pull --days 7

# New (recommended)  
maia database sync journal --days 7

# Or configure and use
maia database sync                                   # Syncs all enabled databases
``` 