"""
Integration tests for core Maia functionality.
"""
import unittest
import tempfile
import os
import json
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add project root to sys.path 
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from promaia.config.databases import DatabaseManager, DatabaseConfig
from promaia.utils.config import get_config, update_config
from promaia.notion.client import get_client

class TestIntegration(unittest.TestCase):
    
    def setUp(self):
        """Set up test environment for each test."""
        self.test_dir = tempfile.mkdtemp()
        self.config_file = os.path.join(self.test_dir, "test_config.json")
        
    def tearDown(self):
        """Clean up after each test."""
        import shutil
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
            
    def test_database_manager_initialization(self):
        """Test that DatabaseManager can be initialized properly."""
        db_manager = DatabaseManager(self.config_file)
        self.assertIsInstance(db_manager, DatabaseManager)
        self.assertEqual(len(db_manager.databases), 0)  # Should start empty
        print("✓ DatabaseManager initialization works")
        
    def test_database_config_creation(self):
        """Test creating and managing database configurations."""
        config_data = {
            "source_type": "notion",
            "database_id": "test_db_id",
            "nickname": "test_db",
            "description": "Test database",
            "workspace": "test_workspace"
        }
        
        db_config = DatabaseConfig("test_db", config_data)
        self.assertEqual(db_config.name, "test_db")
        self.assertEqual(db_config.database_id, "test_db_id")
        self.assertEqual(db_config.workspace, "test_workspace")
        print("✓ DatabaseConfig creation works")
        
    def test_config_serialization(self):
        """Test that database configs can be serialized and deserialized."""
        config_data = {
            "source_type": "notion",
            "database_id": "test_db_id",
            "nickname": "test_db",
            "description": "Test database",
            "workspace": "test_workspace"
        }
        
        db_config = DatabaseConfig("test_db", config_data)
        serialized = db_config.to_dict()
        
        # Create new config from serialized data
        new_config = DatabaseConfig("test_db", serialized)
        
        self.assertEqual(db_config.database_id, new_config.database_id)
        self.assertEqual(db_config.workspace, new_config.workspace)
        print("✓ Config serialization/deserialization works")
        
    def test_config_management(self):
        """Test basic configuration management functions."""
        # Test default config
        config = get_config()
        self.assertIsInstance(config, dict)
        
        # Test config updates
        test_updates = {"test_key": "test_value"}
        updated_config = update_config(test_updates)
        self.assertEqual(updated_config["test_key"], "test_value")
        print("✓ Config management works")
        
    @patch('promaia.notion.client.AsyncClient')
    @patch('promaia.config.workspaces.get_workspace_api_key')
    @patch('promaia.config.workspaces.get_default_workspace')
    def test_notion_client_creation(self, mock_default_workspace, mock_api_key, mock_client):
        """Test Notion client creation (mocked)."""
        mock_client.return_value = MagicMock()
        mock_default_workspace.return_value = None  # No default workspace
        mock_api_key.return_value = None  # No workspace API key
        
        with patch.dict(os.environ, {'NOTION_TOKEN': 'test_token'}):
            client = get_client()
            self.assertIsNotNone(client)
            mock_client.assert_called_with(auth='test_token')
            
        print("✓ Notion client creation works")
        
    def test_qualified_database_names(self):
        """Test workspace-qualified database naming."""
        # Test koii workspace (default)
        koii_config = DatabaseConfig("journal", {
            "workspace": "koii",
            "nickname": "journal"
        })
        self.assertEqual(koii_config.get_qualified_name(), "journal")
        
        # Test other workspace
        trass_config = DatabaseConfig("journal", {
            "workspace": "trass", 
            "nickname": "journal"
        })
        self.assertEqual(trass_config.get_qualified_name(), "trass.journal")
        print("✓ Qualified database naming works")
        
    def test_output_directory_paths(self):
        """Test that output directory paths are correctly configured."""
        # Test koii workspace path - new markdown directory structure
        koii_config = DatabaseConfig("journal", {
            "workspace": "koii",
            "nickname": "journal"
        })
        self.assertEqual(koii_config.markdown_directory, "data/md/notion/koii/journal")
        self.assertEqual(koii_config.json_directory, "data/json")
        
        # Test trass workspace path
        trass_config = DatabaseConfig("journal", {
            "workspace": "trass",
            "nickname": "journal"
        })
        self.assertEqual(trass_config.markdown_directory, "data/md/notion/trass/journal")
        self.assertEqual(trass_config.json_directory, "data/json")
        
        # Test explicit directory override
        custom_config = DatabaseConfig("journal", {
            "workspace": "koii",
            "nickname": "journal",
            "markdown_directory": "custom/path",
            "json_directory": "custom/json"
        })
        self.assertEqual(custom_config.markdown_directory, "custom/path")
        self.assertEqual(custom_config.json_directory, "custom/json")
        
        print("✓ Output directory paths work correctly")

if __name__ == '__main__':
    unittest.main() 