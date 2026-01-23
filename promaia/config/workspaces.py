"""
Workspace configuration management for Maia.

This module provides support for managing multiple Notion workspaces,
allowing users to connect and segregate data from different workspaces.
"""
import os
import json
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
from pathlib import Path

from promaia.utils.env_resolver import resolve_env_variables, load_env_file

logger = logging.getLogger(__name__)

class WorkspaceConfig:
    """Configuration for a single workspace."""

    def __init__(self, name: str, config_data: Dict[str, Any]):
        self.name = name
        self.api_key = config_data.get("api_key")
        self.description = config_data.get("description", "")
        self.enabled = config_data.get("enabled", True)
        self.created_at = config_data.get("created_at", datetime.now().isoformat())
        self.archived = config_data.get("archived", False)
        self.archived_at = config_data.get("archived_at")
        self.archived_reason = config_data.get("archived_reason", "")

    def to_dict(self) -> Dict[str, Any]:
        """Convert workspace config to dictionary."""
        result = {
            "api_key": self.api_key,
            "description": self.description,
            "enabled": self.enabled,
            "created_at": self.created_at,
            "archived": self.archived
        }

        # Only include archive metadata if archived
        if self.archived:
            if self.archived_at:
                result["archived_at"] = self.archived_at
            if self.archived_reason:
                result["archived_reason"] = self.archived_reason

        return result

class WorkspaceManager:
    """Manages workspace configurations and operations."""
    
    def __init__(self, config_file: str = "promaia.config.json"):
        self.config_file = config_file
        self.workspaces: Dict[str, WorkspaceConfig] = {}
        self.default_workspace = None
        self.load_config()
    
    def load_config(self):
        """Load workspace configuration from file."""
        if os.path.exists(self.config_file):
            try:
                # Load environment variables first
                load_env_file()
                
                with open(self.config_file, 'r') as f:
                    config = json.load(f)
                
                # Resolve environment variables in configuration
                config = resolve_env_variables(config)
                
                # Load workspaces from config
                workspaces_data = config.get("workspaces", {})
                for name, workspace_data in workspaces_data.items():
                    self.workspaces[name] = WorkspaceConfig(name, workspace_data)
                
                # Set default workspace
                self.default_workspace = config.get("default_workspace")
                
                # If no workspaces exist but we have legacy NOTION_TOKEN, create default
                if not self.workspaces and os.getenv("NOTION_TOKEN"):
                    self._create_default_workspace_from_env()
                    
            except Exception as e:
                logger.error(f"Error loading workspace config: {e}")
                self._create_default_workspace_from_env()
        else:
            self._create_default_workspace_from_env()
    
    def _create_default_workspace_from_env(self):
        """Create a default workspace from environment variables."""
        notion_token = os.getenv("NOTION_TOKEN")
        if notion_token:
            self.workspaces["default"] = WorkspaceConfig("default", {
                "api_key": notion_token,
                "description": "Default workspace (migrated from NOTION_TOKEN)",
                "enabled": True
            })
            self.default_workspace = "default"
            self.save_config()
            logger.info("Created default workspace from NOTION_TOKEN environment variable")
    
    def save_config(self):
        """Save workspace configuration to file."""
        config = {}
        
        # Load existing config to preserve other sections
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r') as f:
                    config = json.load(f)
            except Exception as e:
                logger.warning(f"Could not load existing config for merging: {e}")
        
        # Update workspaces section
        config["workspaces"] = {
            name: workspace.to_dict() 
            for name, workspace in self.workspaces.items()
        }
        
        # Set default workspace
        if self.default_workspace:
            config["default_workspace"] = self.default_workspace
        
        # Write config file
        try:
            with open(self.config_file, 'w') as f:
                json.dump(config, f, indent=2)
            logger.debug(f"Saved workspace configuration to {self.config_file}")
        except Exception as e:
            logger.error(f"Error saving workspace config: {e}")
    
    def add_workspace(self, name: str, api_key: str, description: str = "") -> bool:
        """Add a new workspace."""
        if name in self.workspaces:
            logger.warning(f"Workspace '{name}' already exists")
            return False
        
        self.workspaces[name] = WorkspaceConfig(name, {
            "api_key": api_key,
            "description": description,
            "enabled": True
        })
        
        # Set as default if it's the first workspace
        if not self.default_workspace:
            self.default_workspace = name
        
        self.save_config()
        logger.info(f"Added workspace '{name}'")
        return True
    
    def remove_workspace(self, name: str) -> bool:
        """Remove a workspace."""
        if name not in self.workspaces:
            logger.warning(f"Workspace '{name}' not found")
            return False

        del self.workspaces[name]

        # Update default workspace if needed
        if self.default_workspace == name:
            self.default_workspace = next(iter(self.workspaces.keys())) if self.workspaces else None

        self.save_config()
        logger.info(f"Removed workspace '{name}'")
        return True

    def archive_workspace(self, name: str, reason: str = "") -> bool:
        """
        Archive a workspace.

        Args:
            name: Workspace name
            reason: Optional reason for archiving

        Returns:
            True if successful
        """
        if name not in self.workspaces:
            logger.warning(f"Workspace '{name}' not found")
            return False

        workspace = self.workspaces[name]
        if workspace.archived:
            logger.warning(f"Workspace '{name}' is already archived")
            return False

        workspace.archived = True
        workspace.archived_at = datetime.now().isoformat()
        workspace.archived_reason = reason

        # Update default workspace if this was the default
        if self.default_workspace == name:
            # Find first non-archived workspace
            active_workspaces = [
                ws_name for ws_name, ws in self.workspaces.items()
                if not ws.archived and ws_name != name
            ]
            self.default_workspace = active_workspaces[0] if active_workspaces else None

        self.save_config()
        logger.info(f"Archived workspace '{name}'")
        return True

    def unarchive_workspace(self, name: str) -> bool:
        """
        Unarchive a workspace.

        Args:
            name: Workspace name

        Returns:
            True if successful
        """
        if name not in self.workspaces:
            logger.warning(f"Workspace '{name}' not found")
            return False

        workspace = self.workspaces[name]
        if not workspace.archived:
            logger.warning(f"Workspace '{name}' is not archived")
            return False

        workspace.archived = False
        workspace.archived_at = None
        workspace.archived_reason = ""

        # Set as default if no default exists
        if not self.default_workspace:
            self.default_workspace = name

        self.save_config()
        logger.info(f"Unarchived workspace '{name}'")
        return True

    def get_workspace(self, name: str) -> Optional[WorkspaceConfig]:
        """Get workspace configuration by name."""
        return self.workspaces.get(name)
    
    def list_workspaces(self, include_archived: bool = False) -> List[str]:
        """
        List all workspace names.

        Args:
            include_archived: If True, include archived workspaces. Default False.

        Returns:
            List of workspace names
        """
        if include_archived:
            return list(self.workspaces.keys())

        # Filter out archived workspaces by default
        return [
            name for name, workspace in self.workspaces.items()
            if not workspace.archived
        ]
    
    def get_default_workspace(self) -> Optional[str]:
        """Get the default workspace name."""
        return self.default_workspace
    
    def set_default_workspace(self, name: str) -> bool:
        """Set the default workspace."""
        if name not in self.workspaces:
            logger.warning(f"Workspace '{name}' not found")
            return False
        
        self.default_workspace = name
        self.save_config()
        logger.info(f"Set default workspace to '{name}'")
        return True
    
    def get_api_key(self, workspace_name: str = None) -> Optional[str]:
        """Get API key for a workspace (defaults to default workspace)."""
        if workspace_name is None:
            workspace_name = self.default_workspace
        
        if workspace_name is None:
            logger.warning("No workspace specified and no default workspace set")
            return None
        
        workspace = self.get_workspace(workspace_name)
        return workspace.api_key if workspace else None
    
    def validate_workspace(self, name: str, allow_archived: bool = False) -> bool:
        """
        Validate that a workspace is properly configured.

        Args:
            name: Workspace name
            allow_archived: If True, archived workspaces are valid. Default False.

        Returns:
            True if workspace is valid
        """
        workspace = self.get_workspace(name)
        if not workspace:
            return False

        if not workspace.api_key:
            logger.error(f"Workspace '{name}' is missing API key")
            return False

        if not workspace.enabled:
            logger.warning(f"Workspace '{name}' is disabled")
            return False

        if workspace.archived and not allow_archived:
            logger.warning(f"Workspace '{name}' is archived")
            return False

        return True

# Global workspace manager instance
_workspace_manager = None

def get_workspace_manager(config_file: str = "promaia.config.json") -> WorkspaceManager:
    """Get the global workspace manager instance."""
    global _workspace_manager
    if _workspace_manager is None:
        _workspace_manager = WorkspaceManager(config_file)
    return _workspace_manager

def get_workspace_config(name: str) -> Optional[WorkspaceConfig]:
    """Get workspace configuration by name."""
    manager = get_workspace_manager()
    return manager.get_workspace(name)

def get_workspace_api_key(workspace_name: str = None) -> Optional[str]:
    """Get API key for a workspace."""
    manager = get_workspace_manager()
    return manager.get_api_key(workspace_name) 

def get_default_workspace() -> Optional[str]:
    """Get the default workspace name."""
    manager = get_workspace_manager()
    return manager.get_default_workspace() 