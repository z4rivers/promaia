"""
Database configuration management for Maia.

This module provides a unified configuration system for managing multiple databases
and their sync settings, filters, and properties.
"""
import os
import json
import logging
from typing import Dict, Any, List, Optional, Union
from datetime import datetime, timedelta
from pathlib import Path

from promaia.utils.env_resolver import resolve_env_variables, load_env_file

logger = logging.getLogger(__name__)

# Default configuration file location
DEFAULT_CONFIG_FILE = "promaia.config.json"

class DatabaseConfig:
    """Configuration for a single database."""
    
    def __init__(self, name: str, config_data: Dict[str, Any]):
        self.name = name
        self.source_type = config_data.get("source_type", "notion")
        self.database_id = config_data["database_id"]
        self.nickname = config_data.get("nickname", name)
        self.description = config_data.get("description", "")
        
        # Workspace assignment
        self.workspace = config_data.get("workspace", "koii")
        
        # Sync settings
        self.sync_enabled = config_data.get("sync_enabled", True)
        self.include_properties = config_data.get("include_properties", True)
        self.sync_frequency = config_data.get("sync_frequency", "daily")
        self.default_days = config_data.get("default_days", 7)
        self.last_sync_time = config_data.get("last_sync_time", None)
        
        # Filtering settings
        self.filters = config_data.get("filters", {})
        self.property_filters = config_data.get("property_filters", {})
        self.date_filters = config_data.get("date_filters", {})

        # Storage settings - markdown only
        if config_data.get("source_type") == "gmail":
            # For Gmail, use data/md/gmail/{username} structure
            # Extract username from email database_id (e.g., koii.create@gmail.com -> koiicreate)
            email = config_data.get("database_id", "")
            username = email.split("@")[0].replace(".", "") if "@" in email else "unknown"
            default_md_dir = f"data/md/gmail/{username}"
        else:
            # For other sources (Notion), use data/md/notion/{workspace}/{database}
            default_md_dir = f"data/md/notion/{self.workspace}/{self.nickname}"
        
        self.markdown_directory = config_data.get("markdown_directory", default_md_dir)
        
        # Backward compatibility: keep output_directory for legacy systems
        self.output_directory = config_data.get("output_directory", self.markdown_directory)
            
        self.primary_format = "markdown"  # Always markdown
        self.save_markdown = True  # Always save markdown
        
        # Subpage sync settings
        self.sync_subpages = config_data.get("sync_subpages", False)
        
        # Property mapping
        self.property_mapping = config_data.get("property_mapping", {})
        self.required_properties = config_data.get("required_properties", [])
        self.excluded_properties = config_data.get("excluded_properties", [])
        
        # Authentication (for future extensibility)
        self.auth_config = config_data.get("auth", {})
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert database config to dictionary."""
        result = {
            "source_type": self.source_type,
            "database_id": self.database_id,
            "nickname": self.nickname,
            "description": self.description,
            "workspace": self.workspace,
            "sync_enabled": self.sync_enabled,
            "include_properties": self.include_properties,
            "sync_frequency": self.sync_frequency,
            "default_days": self.default_days,
            "last_sync_time": self.last_sync_time,
            "filters": self.filters,
            "property_filters": self.property_filters,
            "date_filters": self.date_filters,
            "markdown_directory": self.markdown_directory,
            "primary_format": self.primary_format,
            "save_markdown": self.save_markdown,
            "sync_subpages": self.sync_subpages,
            "property_mapping": self.property_mapping,
            "required_properties": self.required_properties,
            "excluded_properties": self.excluded_properties,
            "auth": self.auth_config
        }
        
        # Include backward compatibility fields only if they differ from current structure
        if self.output_directory != self.markdown_directory:
            result["output_directory"] = self.output_directory
        
        return result
        
    def get_qualified_name(self) -> str:
        """Get the workspace-qualified database name."""
        if self.workspace == "koii":
            return self.nickname
        else:
            # Check if nickname already starts with workspace prefix
            if self.nickname.startswith(f"{self.workspace}."):
                return self.nickname
            else:
                return f"{self.workspace}.{self.nickname}"

class DatabaseManager:
    """Manages all database configurations."""
    
    def __init__(self, config_file: str = DEFAULT_CONFIG_FILE):
        self.config_file = config_file
        self.global_settings = {}
        self.databases: Dict[str, DatabaseConfig] = {}
        
        # Import workspace manager
        from promaia.config.workspaces import get_workspace_manager
        self.workspace_manager = get_workspace_manager(config_file)
        
        # Initialize configuration
        if not os.path.exists(config_file):
            self.create_default_config()
        else:
            self.load_config()
    
    def load_config(self):
        """Load configuration from file."""
        if not os.path.exists(self.config_file):
            logger.info(f"Configuration file {self.config_file} not found. Creating default configuration.")
            self.create_default_config()
            return
        
        try:
            # Load environment variables first
            load_env_file()
            
            with open(self.config_file, 'r') as f:
                config_data = json.load(f)
            
            # Resolve environment variables in configuration
            config_data = resolve_env_variables(config_data)
            
            # Load global settings
            self.global_settings = config_data.get("global", {})
            
            # Load database configurations
            databases_config = config_data.get("databases", {})
            for name, db_config in databases_config.items():
                self.databases[name] = DatabaseConfig(name, db_config)
                
            logger.info(f"Loaded configuration for {len(self.databases)} databases")
            
        except Exception as e:
            logger.error(f"Error loading configuration: {e}")
            self.create_default_config()
    
    def save_config(self):
        """Save configuration to file."""
        # Load existing config to preserve workspaces and other sections
        existing_config = {}
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    existing_config = json.load(f)
        except Exception as e:
            logger.warning(f"Could not load existing config for preservation: {e}")
        
        # Build new config with preserved sections
        config_data = {
            "global": self.global_settings,
            "databases": {
                name: db.to_dict() for name, db in self.databases.items()
            }
        }
        
        # Preserve workspaces section if it exists
        if "workspaces" in existing_config:
            config_data["workspaces"] = existing_config["workspaces"]
        
        # Preserve default_workspace setting if it exists
        if "default_workspace" in existing_config:
            config_data["default_workspace"] = existing_config["default_workspace"]
        
        try:
            with open(self.config_file, 'w') as f:
                json.dump(config_data, f, indent=2)
            logger.debug(f"Configuration saved to {self.config_file}")
        except Exception as e:
            logger.error(f"Error saving configuration: {e}")
    
    def create_default_config(self):
        """Create a default configuration file."""
        default_config = {
            "global": {
            "default_sync_days": 7,
            "default_output_directory": "data",
            "markdown_base_directory": "data/md",
                "json_base_directory": "data/json",
                "json_registry_db": "data/maia_content.db",
                "registry_db": "data/hybrid_metadata.db",
                "vector_db_enabled": False,
                "vector_db_type": "chroma",
                "vector_db_path": "vector_db",
                "storage_format": "json",
            "enable_ai_editing": True,
                "ai_edit_safety_mode": True
            },
            "databases": {}
        }
        
        # Migrate existing environment variables to new config
        self._migrate_from_env_vars()
        
        self.save_config()
    
    def get_database_by_qualified_name(self, qualified_name: str) -> Optional[DatabaseConfig]:
        """Get a database configuration by its qualified name."""
        for db in self.databases.values():
            # Check against the key in the config (e.g., "trass.journal")
            # and the generated qualified name (e.g., "trass.journal")
            if db.name == qualified_name or db.get_qualified_name() == qualified_name:
                return db
        return None
    
    def _migrate_from_env_vars(self):
        """Migrate existing environment variable configurations."""
        # Journal database
        journal_db_id = os.getenv("NOTION_JOURNAL_DATABASE_ID")
        if journal_db_id:
            self.databases["journal"] = DatabaseConfig("journal", {
                "source_type": "notion",
                "database_id": journal_db_id,
                "nickname": "koii_journal",
                "description": "Personal journal entries",
                "output_directory": "data/koii/md/journal",
                "default_days": 7,
                "include_properties": False,
                "save_markdown": True,
                "property_filters": {},
                "date_filters": {
                    "property": "Date",
                    "type": "date"
                }
            })
        
        # CMS database
        cms_db_id = os.getenv("NOTION_CMS_DATABASE_ID")
        if cms_db_id:
            self.databases["cms"] = DatabaseConfig("cms", {
                "source_type": "notion",
                "database_id": cms_db_id,
                "nickname": "koii_cms",
                "description": "Content management system",
                "output_directory": "data/koii/md/cms",
                "default_days": 30,
                "include_properties": False,
                "save_markdown": True,
                "property_filters": {
                    "Blog Status": ["To sync", "Update on sync", "Don't sync", "Live"]
                }
            })
        
        logger.info("Migrated existing environment variables to new configuration")
    
    def add_database(self, name: str, config_data: Dict[str, Any], workspace: str = None) -> bool:
        """Add a new database configuration."""
        # Set workspace if not specified
        if workspace is None:
            workspace = self.workspace_manager.get_default_workspace() or "koii"
        
        # Add workspace to config data
        config_data["workspace"] = workspace
        
        # Create qualified name for storage
        qualified_name = f"{workspace}.{name}" if workspace != "koii" else name
        
        if qualified_name in self.databases:
            logger.warning(f"Database '{qualified_name}' already exists")
            return False
        
        self.databases[qualified_name] = DatabaseConfig(name, config_data)
        self.save_config()
        
        logger.info(f"Added database '{qualified_name}' to workspace '{workspace}'")
        return True
    
    def get_database(self, name: str, workspace: str = None) -> Optional[DatabaseConfig]:
        """Get database configuration by name, with workspace-aware lookup."""
        # If workspace specified, try workspace.name format first
        if workspace:
            qualified_name = f"{workspace}.{name}"
            if qualified_name in self.databases:
                return self.databases[qualified_name]
        
        # Try exact match if no workspace specified or qualified name not found
        if name in self.databases:
            db = self.databases[name]
            # If workspace specified, ensure it matches
            if workspace is None or db.workspace == workspace:
                return db
        
        # Try searching across all workspaces for the nickname as fallback
        for db_name, db_config in self.databases.items():
            if db_config.nickname == name:
                # If workspace specified, ensure it matches
                if workspace is None or db_config.workspace == workspace:
                    return db_config
        
        return None
    
    def list_databases(self, workspace: str = None) -> List[str]:
        """List database names, optionally filtered by workspace."""
        if workspace is None:
            return list(self.databases.keys())
        
        return [
            name for name, config in self.databases.items() 
            if config.workspace == workspace
        ]
    
    def list_databases_by_workspace(self) -> Dict[str, List[str]]:
        """List databases grouped by workspace."""
        result = {}
        for name, config in self.databases.items():
            workspace = config.workspace
            if workspace not in result:
                result[workspace] = []
            result[workspace].append(name)
        return result
    
    def remove_database(self, name: str, workspace: str = None) -> bool:
        """Remove a database configuration."""
        db_config = self.get_database(name, workspace)
        if not db_config:
            logger.warning(f"Database '{name}' not found")
            return False
        
        # Find the actual key in self.databases
        key_to_remove = None
        for key, config in self.databases.items():
            if config == db_config:
                key_to_remove = key
                break
        
        if key_to_remove:
            del self.databases[key_to_remove]
            self.save_config()
            logger.info(f"Removed database '{name}' from workspace '{db_config.workspace}'")
            return True
        
        return False
    
    def get_workspace_databases(self, workspace: str) -> List[DatabaseConfig]:
        """Get all databases for a specific workspace."""
        return [
            config for config in self.databases.values()
            if config.workspace == workspace
        ]

# Global database manager instance
_db_manager = None

def get_database_manager() -> DatabaseManager:
    """Get the global database manager instance."""
    global _db_manager
    if _db_manager is None:
        _db_manager = DatabaseManager()
    return _db_manager

def get_database_config(name: str, workspace: str = None) -> Optional[DatabaseConfig]:
    """Get database configuration by name."""
    manager = get_database_manager()
    return manager.get_database(name, workspace)

def list_databases(workspace: str = None) -> List[str]:
    """List all configured databases."""
    return get_database_manager().list_databases(workspace)

def add_database(name: str, config: Dict[str, Any]) -> DatabaseConfig:
    """Add a new database configuration."""
    return get_database_manager().add_database(name, config) 