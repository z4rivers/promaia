# Promaia - Notion Integration & Automation Framework

> A Python framework for Notion automation, content management, and AI-powered workflows

Promaia provides a comprehensive CLI interface and Python API for syncing Notion content, managing multiple workspaces, and processing data through various formats including Markdown, JSON, and vector databases.

## ✨ Features

- **Multi-Workspace Management**: Handle multiple Notion workspaces and databases
- **Hybrid Storage Architecture**: Optimized separate tables for each content type (Gmail, Notion databases, etc.)
- **Intelligent Syncing**: Smart synchronization with timestamp tracking and conflict resolution
- **Content Processing**: Convert between Markdown, JSON, and structured formats
- **AI Integration**: Chat interface with context from your Notion content
- **Newsletter Automation**: Sync and distribute content via email
- **CMS Integration**: Manage content workflows between Notion and other platforms
- **Natural Language Queries**: Advanced AI-powered content filtering and search

## 🚀 Quick Start

### Installation

```bash
# Clone the repository
git clone <repository-url>
cd promaia

# Install dependencies
pip install -e .

# Set up configuration
cp docs/env.template .env
```

### Basic Usage

```bash
# Add a workspace
maia workspace add myworkspace --api-key your_notion_token

# Add a database
maia database add journal --id your_database_id --workspace myworkspace

# Test your setup
maia database list

# Test connectivity
maia database test journal

# Sync content
maia database sync --source journal --days 7

# Check sync status  
maia database status

# Start AI chat with your content
maia chat

# Generate content with AI
maia write --prompt "Write a blog post about productivity"
```

## 📚 Core Commands

### Database Management
- `maia database list` - List all configured databases
- `maia database add` - Add a new database configuration
- `maia database sync` - Sync databases with Notion
- `maia database test` - Test database connections
- `maia database status` - Show what needs syncing

### Workspace Management
- `maia workspace list` - List configured workspaces
- `maia workspace add` - Add a new workspace
- `maia workspace set-default` - Set default workspace

### Content Management
- `maia cms pull` - Pull CMS content from Notion
- `maia cms push` - Push local changes to Notion
- `maia newsletter sync` - Sync newsletter content
- `maia convert` - Convert between storage formats

### AI & Chat Features
- `maia chat` - Interactive AI chat with context from synced content
- `maia write` - AI-powered content generation
- `maia model` - Configure AI model preferences

### Hybrid Architecture
- `maia hybrid status` - Show hybrid storage architecture status
- `maia hybrid migrate` - One-time migration from legacy to hybrid (if needed)
- `maia hybrid analyze` - Analyze content structure and optimization tips

### Advanced Filtering
- **Complex date filtering** for journaling analysis (first week of every month, seasonal patterns, etc.)
- **Multi-source filtering** with different criteria per database
- **Property-based filtering** for content management workflows
- See `docs/ENHANCED_FILTERING.md` for complete guide

## 📁 Project Structure

```
promaia/
├── promaia/               # Main package
│   ├── cli/              # Command-line interface
│   ├── config/           # Configuration management
│   ├── connectors/       # Data source connectors
│   ├── storage/          # File and data storage
│   ├── ai/               # AI integration
│   └── notion/           # Notion API client
├── data/                 # Content storage
│   ├── md/              # Markdown files
│   └── json/            # JSON metadata
├── docs/                # Documentation
└── tests/               # Test suite
```

## Development

```bash
# Install development dependencies
pip install -r requirements.txt

# Run tests
python -m pytest tests/ -v

# Run with coverage
python -m pytest tests/ --cov=maia

# Format code
black maia/ tests/
isort maia/ tests/

# Lint code
flake8 maia/ tests/
```

## Testing

The project includes comprehensive tests for:
- Configuration management
- CLI interface functionality  
- Database synchronization
- API connectivity

Run the test suite:
```bash
python -m pytest tests/ -v
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes with tests
4. Ensure all tests pass
5. Submit a pull request

## License

MIT License - see LICENSE file for details.

---

*Built for seamless Notion integration and AI-powered content workflows.*
