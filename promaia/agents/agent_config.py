"""
Agent configuration management with JSON persistence.
"""

import json
import os
from dataclasses import dataclass, asdict, field
from typing import List, Optional, Dict, Any, Tuple
from pathlib import Path
from enum import Enum


class SourcePermission(Enum):
    """Permission levels for data sources"""
    READ_INITIAL = "read_initial"  # Load in initial context boundary
    QUERY = "query"                # Can query dynamically at runtime
    WRITE = "write"                # Can write/modify via MCP tools


@dataclass
class SourceAccess:
    """Access configuration for a single source"""
    source_name: str               # e.g., "journal", "gmail", "tasks"
    initial_days: Optional[int]    # Days to load initially (None = all)
    permissions: List[SourcePermission]  # What agent can do
    max_query_days: Optional[int] = None  # Max days for query_source (safety limit)


@dataclass
class AgentConfig:
    """Configuration for a scheduled agent."""

    name: str
    workspace: str
    databases: List[str]  # e.g., ["journal:7", "gmail:7", "stories:all"]
    prompt_file: str  # Path to .md file or inline content
    mcp_tools: List[str]  # List of MCP tool names to enable
    max_iterations: int  # Maximum query iterations (default: 3)
    output_notion_page_id: str  # Where to write results
    enabled: bool = True

    # Scheduling fields (new format uses schedule, old format uses interval_minutes)
    schedule: Optional[List[Tuple[str, str]]] = None  # List of (day, time) like [("Mon", "09:00"), ...]
    interval_minutes: Optional[int] = None  # Legacy: 5, 15, 30, 60, etc. (deprecated, use schedule)

    # Notion integration fields
    agent_id: str = ""                                  # "grace", "bondu", "daily-summary"
    notion_page_id: Optional[str] = None                # Agent's page in Agents database
    system_prompt_page_id: Optional[str] = None         # System Prompt subpage ID
    instructions_db_id: Optional[str] = None            # Instructions sub-database ID
    journal_db_id: Optional[str] = None                 # Journal sub-database ID

    # Optional fields
    description: Optional[str] = None
    created_at: Optional[str] = None
    last_run_at: Optional[str] = None
    calendar_event_ids: Optional[str] = None  # Comma-separated event IDs from Google Calendar
    calendar_id: Optional[str] = None  # Dedicated Google Calendar ID for this agent

    # NEW: Source-level permissions (replaces databases eventually)
    source_access: Optional[List[SourceAccess]] = None

    # NEW: SDK-related fields
    sdk_enabled: bool = True  # Use SDK for execution
    sdk_permission_mode: str = "bypassPermissions"  # or "default", "acceptEdits", "plan"
    sdk_allowed_tools: Optional[List[str]] = None  # Override default tools

    # NEW: Model routing override
    # Model key from AGENT_MODEL_MAP (e.g., "flash", "pro"). When None,
    # ModelRouter.get_agent_model() uses the default for the agent name.
    # Set in promaia.config.json to override the default model per agent.
    model: Optional[str] = None
    
    # NEW: Messaging platform configuration (platform-agnostic)
    messaging_platform: Optional[str] = None  # "slack" or "discord"
    messaging_channel_id: Optional[str] = None  # Platform-specific channel ID
    messaging_enabled: bool = False  # Enable messaging integration
    initiate_conversation: bool = False  # Start conversation vs one-way post
    conversation_timeout_minutes: int = 15  # Minutes before timeout
    conversation_max_turns: Optional[int] = None  # Max turns (None = unlimited)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AgentConfig':
        """Create AgentConfig from dictionary."""
        return cls(**data)

    def validate(self) -> List[str]:
        """Validate configuration and return list of errors."""
        errors = []

        if not self.name:
            errors.append("Agent name is required")

        if not self.workspace:
            errors.append("Workspace is required")

        if not self.databases:
            errors.append("At least one database must be selected")

        # Prompt file is optional - uses default or Notion System Prompt

        # Scheduling is optional - agents triggered by calendar events or interval
        if self.interval_minutes is not None and self.interval_minutes <= 0:
            errors.append("Interval must be positive")

        if self.schedule is not None and len(self.schedule) == 0:
            errors.append("Schedule must have at least one run")

        if self.max_iterations <= 0:
            errors.append("Max iterations must be positive")

        # Output page is optional - agents respond contextually

        return errors

    def get_initial_context_sources(self) -> Dict[str, Optional[int]]:
        """Get sources to load in initial context boundary"""
        if self.source_access:
            return {
                access.source_name: access.initial_days
                for access in self.source_access
                if SourcePermission.READ_INITIAL in access.permissions
            }
        else:
            # Fall back to old databases format
            return self._parse_legacy_databases()

    def _parse_legacy_databases(self) -> Dict[str, Optional[int]]:
        """Parse legacy databases field into dict of source -> days"""
        result = {}
        for source_spec in self.databases:
            if ':' in source_spec:
                database_name, days_str = source_spec.split(':', 1)
                days = None if days_str == 'all' else int(days_str)
            else:
                database_name = source_spec
                days = None
            result[database_name] = days
        return result

    def get_queryable_sources(self) -> List[str]:
        """Get sources agent can query dynamically"""
        if self.source_access:
            return [
                access.source_name
                for access in self.source_access
                if SourcePermission.QUERY in access.permissions
            ]
        else:
            # Legacy: all initial sources are queryable
            return [db.split(':')[0] for db in self.databases]

    def get_writable_sources(self) -> List[str]:
        """Get sources agent can write to via MCP"""
        if self.source_access:
            return [
                access.source_name
                for access in self.source_access
                if SourcePermission.WRITE in access.permissions
            ]
        else:
            return []  # Legacy mode: no write permissions

    def can_query_source(self, source_name: str, days: int) -> bool:
        """Check if agent can query this source with given time range"""
        if not self.source_access:
            return True  # Legacy mode: allow all queries

        for access in self.source_access:
            if access.source_name == source_name:
                if SourcePermission.QUERY not in access.permissions:
                    return False
                if access.max_query_days and days > access.max_query_days:
                    return False
                return True
        return False


def get_config_file_path() -> Path:
    """Get the path to promaia.config.json."""
    # Try current directory first
    config_path = Path.cwd() / "promaia.config.json"
    if config_path.exists():
        return config_path

    # Try home directory
    config_path = Path.home() / ".promaia" / "promaia.config.json"
    if config_path.exists():
        return config_path

    # Default to current directory
    return Path.cwd() / "promaia.config.json"


def load_config() -> Dict[str, Any]:
    """Load the entire config file."""
    config_path = get_config_file_path()

    if not config_path.exists():
        return {}

    try:
        with open(config_path, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading config: {e}")
        return {}


def save_config(config: Dict[str, Any]) -> None:
    """Save the entire config file."""
    config_path = get_config_file_path()

    # Ensure directory exists
    config_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        with open(config_path, 'w') as f:
            json.dump(config, f, indent=2)
    except Exception as e:
        print(f"Error saving config: {e}")
        raise


def load_agents() -> List[AgentConfig]:
    """Load all agent configurations from promaia.config.json."""
    config = load_config()
    agents_data = config.get('agents', [])

    agents = []
    for agent_data in agents_data:
        try:
            agents.append(AgentConfig.from_dict(agent_data))
        except Exception as e:
            print(f"Error loading agent {agent_data.get('name', 'unknown')}: {e}")

    return agents


def save_agent(agent: AgentConfig) -> None:
    """Save or update an agent configuration."""
    config = load_config()

    if 'agents' not in config:
        config['agents'] = []

    # Find and replace if exists, otherwise append
    found = False
    for i, existing in enumerate(config['agents']):
        if existing.get('name') == agent.name:
            config['agents'][i] = agent.to_dict()
            found = True
            break

    if not found:
        config['agents'].append(agent.to_dict())

    save_config(config)


def delete_agent(agent_name: str) -> bool:
    """Delete an agent configuration. Returns True if deleted, False if not found."""
    config = load_config()

    if 'agents' not in config:
        return False

    original_length = len(config['agents'])
    config['agents'] = [a for a in config['agents'] if a.get('name') != agent_name]

    if len(config['agents']) < original_length:
        save_config(config)
        return True

    return False


def get_agent(agent_name: str) -> Optional[AgentConfig]:
    """Get a specific agent by name."""
    agents = load_agents()
    for agent in agents:
        if agent.name == agent_name:
            return agent
    return None


def update_agent_last_run(agent_name: str, timestamp: str) -> None:
    """Update the last run timestamp for an agent."""
    agent = get_agent(agent_name)
    if agent:
        agent.last_run_at = timestamp
        save_agent(agent)
