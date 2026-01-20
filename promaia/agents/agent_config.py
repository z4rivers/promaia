"""
Agent configuration management with JSON persistence.
"""

import json
import os
from dataclasses import dataclass, asdict
from typing import List, Optional, Dict, Any
from pathlib import Path


@dataclass
class AgentConfig:
    """Configuration for a scheduled agent."""

    name: str
    workspace: str
    databases: List[str]  # e.g., ["journal:7", "gmail:7", "stories:all"]
    prompt_file: str  # Path to .md file or inline content
    interval_minutes: int  # 5, 15, 30, 60, etc.
    mcp_tools: List[str]  # List of MCP tool names to enable
    max_iterations: int  # Maximum query iterations (default: 3)
    output_notion_page_id: str  # Where to write results
    enabled: bool = True

    # Optional fields
    description: Optional[str] = None
    created_at: Optional[str] = None
    last_run_at: Optional[str] = None

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

        if not self.prompt_file:
            errors.append("Prompt file is required")

        if self.interval_minutes <= 0:
            errors.append("Interval must be positive")

        if self.max_iterations <= 0:
            errors.append("Max iterations must be positive")

        if not self.output_notion_page_id:
            errors.append("Output Notion page ID is required")

        return errors


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
