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

### Multi-Source Chat
```bash
# Start chat with default settings
maia chat

# Chat with specific data sources
maia chat --source journal:7 --source awakenings:all
maia chat --source journal:30 --source cms:14

# Advanced filtering (see docs/ENHANCED_FILTERING.md for complete guide)
maia chat -s journal -f 'journal:created_time>2025-01-01'
maia chat -s journal -f 'journal:created_time>2024-12-01 and created_time<2024-12-08 or created_time>2025-07-01 and created_time<2025-07-08'

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
--source journal:7              # Last 7 days from journal
--source awakenings:all         # All entries from awakenings
--source cms:30                 # Last 30 days from CMS
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

### Daily Journal Sync
```bash
maia database sync journal                           # Sync journal database
maia chat --source journal:7                        # Chat with recent entries
```

### Content Creation
```bash
maia database sync                                   # Sync all databases
maia write --days 14                                # Generate content from context
maia cms push                                       # Push to CMS
```

### Multi-Source Analysis
```bash
maia chat --source journal:30 --source awakenings:all --source projects:14
```

### Blog Publishing
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