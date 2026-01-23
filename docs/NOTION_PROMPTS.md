# Notion-Backed Prompts

## Overview

Promaia now supports using Notion pages as agent prompts that stay automatically synced. This allows you to:
- **Edit prompts in Notion** using its rich editor
- **Collaborate on prompts** with your team
- **Keep prompts in sync** automatically during Promaia sync operations
- **Version control** your prompts in Notion's page history

## Creating a Notion-Backed Prompt

### Method 1: During Agent Creation

When creating a new agent with `maia agent add`, you'll see the prompt selector:

```
↑↓:Navigate N:New E:Edit P:Notion ENTER:Select ESC:Cancel
```

Press **P** to create a prompt from a Notion page:

1. Paste your Notion page URL
2. Optionally provide a filename (or press ENTER to auto-generate)
3. Promaia fetches the page content and creates a synced prompt file

### Method 2: Manual Creation

You can also create Notion-backed prompts programmatically:

```python
from promaia.cli.notion_prompt_manager import create_notion_prompt

prompt_file = await create_notion_prompt(
    notion_url="https://www.notion.so/your-page-id",
    filename="my_agent_prompt",  # Optional
    workspace="your_workspace"   # Optional
)
```

## How It Works

### Metadata Storage

Notion-backed prompts store metadata at the top of the markdown file:

```markdown
<!-- notion_prompt_metadata
{
  "notion_page_id": "abc123def456...",
  "notion_url": "https://www.notion.so/...",
  "last_synced": "2026-01-22T10:30:00Z",
  "sync_enabled": true
}
-->

# Your Prompt Content
[Rest of the Notion page content as markdown...]
```

### Automatic Syncing

Notion-backed prompts are automatically synced:

1. **During chat sync**: When you run `maia chat --sources ...`, prompts are synced first
2. **Before agent execution**: Scheduled agents sync their prompts before running
3. **Manual sync**: Use `maia agent sync-prompts` to sync all prompts

### Sync Behavior

- Prompts with `sync_enabled: true` are updated on every sync
- Prompts with `sync_enabled: false` are skipped
- Only the content is updated; metadata is preserved
- Failed syncs don't break your workflow (old content is used)

## Supported Notion URL Formats

The system recognizes various Notion URL formats:

```
https://www.notion.so/Page-Title-abc123def456
https://notion.so/abc123def456
https://www.notion.so/workspace/abc123def456
https://www.notion.so/workspace/Page-Title-abc123def456?v=...
```

## CLI Commands

### Sync All Prompts

```bash
# Sync all Notion-backed prompts
maia agent sync-prompts

# Sync with specific workspace context
maia agent sync-prompts --workspace koii
```

### Check Prompt Status

View which prompts are Notion-backed:

```bash
ls -la ~/.promaia/agent_prompts/
```

Files with Notion metadata at the top are synced prompts.

## Use Cases

### Team Collaboration

Store your agent prompts in a shared Notion workspace:

```
Team Workspace
└── Agent Prompts
    ├── Daily Summary Agent
    ├── Email Draft Assistant
    └── Code Review Agent
```

Everyone can edit prompts in Notion, and Promaia keeps them synced locally.

### Prompt Evolution

Use Notion's version history to:
- Track prompt changes over time
- Experiment with different prompt versions
- Roll back to previous versions if needed

### Rich Prompt Editing

Use Notion's features for better prompts:
- **Toggle blocks** for optional sections
- **Callouts** for important instructions
- **Tables** for structured data
- **Code blocks** with syntax highlighting
- **Embedded content** (images, videos, etc.)

## Advanced Usage

### Disable Sync for a Prompt

Edit the metadata at the top of the file:

```markdown
<!-- notion_prompt_metadata
{
  ...
  "sync_enabled": false
}
-->
```

This prompt will no longer be updated from Notion.

### Programmatic Access

Get prompt content without metadata:

```python
from promaia.cli.notion_prompt_manager import get_prompt_content
from pathlib import Path

prompt_file = Path("~/.promaia/agent_prompts/my_prompt.md").expanduser()
clean_content = get_prompt_content(prompt_file)
```

Check if a prompt is Notion-backed:

```python
from promaia.cli.notion_prompt_manager import is_notion_backed

if is_notion_backed(prompt_file):
    print("This prompt syncs with Notion!")
```

### Parse Notion URLs

```python
from promaia.cli.notion_prompt_manager import parse_notion_url

page_id = parse_notion_url("https://www.notion.so/My-Page-abc123")
# Returns: "abc123..." (32-character hex ID)
```

## Troubleshooting

### "Could not parse Notion URL"

Ensure your URL is in one of the supported formats. The page ID should be visible in the URL.

### "Failed to fetch Notion page"

Check:
- You have internet connectivity
- Your Notion API key is configured in the workspace
- The page is accessible with your API credentials
- The page isn't in the trash

### Sync Failures

If a prompt fails to sync:
- The old content remains intact (safe fallback)
- Check the sync output for specific error messages
- Use `maia agent sync-prompts` to retry

### Permission Issues

Ensure your Notion integration has:
- Read access to the pages you want to use as prompts
- Access to the specific workspace containing the pages

## Best Practices

1. **Organize prompts in Notion**: Keep all agent prompts in a dedicated Notion database or page
2. **Use descriptive titles**: Name your Notion pages clearly so you can identify them later
3. **Test after editing**: After editing a prompt in Notion, sync and test your agent
4. **Version control metadata**: Keep the Notion URL in the metadata for future reference
5. **Regular syncs**: Run `maia agent sync-prompts` periodically to stay up to date

## Examples

### Daily Summary Agent

Create a Notion page with your agent prompt:

```markdown
# Daily Summary Agent

Create a concise daily summary of my work activities.

## Sources to Review
- Journal entries from the past 24 hours
- Recent Gmail conversations
- Discord messages from work channels

## Output Format
- **Key Highlights**: Main achievements
- **Decisions Made**: Important choices
- **Action Items**: Tasks for tomorrow

## Style Guidelines
- Be concise but informative
- Focus on actionable insights
- Group related items together
```

Then create the agent:

```bash
maia agent add
# Follow prompts, press P when asked for prompt
# Paste your Notion URL
# Complete the agent setup
```

The agent will always use the latest version of your Notion prompt!

## Integration with Regular Chat

Notion prompts also work with regular chat sessions:

```bash
# Syncs prompts before starting chat
maia chat --sources journal:7,gmail:30
```

All Notion-backed prompts in `~/.promaia/agent_prompts/` are synced automatically.
