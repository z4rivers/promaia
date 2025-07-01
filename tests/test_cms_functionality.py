"""
Test suite for CMS sync functionality.

This test file ensures that the CMS sync features work correctly
and do not regress after code changes.
"""
import unittest
import asyncio
import tempfile
import shutil
import os
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from promaia.notion.pages import (
    query_database, 
    get_page_property, 
    get_block_content,
    get_pages_by_blog_status
)
from promaia.webflow.sync import notion_to_webflow_item
from promaia.notion.client import ensure_default_client


class TestCMSFunctionality(unittest.TestCase):
    """Test CMS sync functionality."""
    
    @classmethod
    def setUpClass(cls):
        """Set up test environment."""
        cls.data_path = Path("data")
        cls.backup_dir = Path(f"test_backup_{uuid.uuid4().hex[:8]}")
        
        # Backup existing data if it exists
        if cls.data_path.exists():
            shutil.copytree(cls.data_path, cls.backup_dir / "data_bak")
            print(f"Backed up existing data to {cls.backup_dir}")
        
        print("CMS test environment set up.")
    
    @classmethod
    def tearDownClass(cls):
        """Clean up test environment."""
        import time
        
        # Clean up test-generated files with retry logic
        for attempt in range(3):
            try:
                if cls.data_path.exists():
                    shutil.rmtree(cls.data_path)
                break
            except PermissionError:
                if attempt < 2:
                    time.sleep(0.5)
                    continue
                print(f"Warning: Could not clean up {cls.data_path}")
        
        # Restore backup with retry logic
        if (cls.backup_dir / "data_bak").exists():
            for attempt in range(3):
                try:
                    if cls.data_path.exists():
                        shutil.rmtree(cls.data_path)
                    shutil.move(str(cls.backup_dir / "data_bak"), str(cls.data_path))
                    break
                except (PermissionError, OSError):
                    if attempt < 2:
                        time.sleep(0.5)
                        continue
                    print(f"Warning: Could not restore backup from {cls.backup_dir}")
        
        # Clean up backup directory
        if cls.backup_dir.exists():
            try:
                shutil.rmtree(cls.backup_dir)
            except:
                print(f"Warning: Could not clean up backup directory {cls.backup_dir}")
        
        print("CMS test environment torn down.")
    
    def test_notion_client_initialization(self):
        """Test that the Notion client can be initialized correctly."""
        try:
            client = ensure_default_client()
            self.assertIsNotNone(client)
            # Check that the client has the expected attributes
            self.assertTrue(hasattr(client, 'databases'))
            self.assertTrue(hasattr(client, 'pages'))
            self.assertTrue(hasattr(client, 'blocks'))
        except Exception as e:
            self.fail(f"Failed to initialize Notion client: {e}")
    
    @patch('promaia.notion.pages.ensure_default_client')
    def test_query_database_with_mock(self, mock_client):
        """Test database querying with mocked responses."""
        # Mock the client
        mock_client_instance = AsyncMock()
        mock_client.return_value = mock_client_instance
        
        # Mock database response
        mock_response = {
            "results": [
                {
                    "id": "test-page-1",
                    "properties": {
                        "Blog Status": {
                            "type": "status",
                            "status": {"name": "To push"}
                        }
                    }
                }
            ],
            "has_more": False
        }
        
        mock_client_instance.databases.query = AsyncMock(return_value=mock_response)
        
        async def run_test():
            result = await query_database("test-db-id")
            self.assertEqual(len(result), 1)
            self.assertEqual(result[0]["id"], "test-page-1")
        
        asyncio.run(run_test())
    
    @patch('promaia.notion.pages.ensure_default_client')
    def test_get_page_property_with_mock(self, mock_client):
        """Test page property retrieval with mocked responses."""
        # Mock the client
        mock_client_instance = AsyncMock()
        mock_client.return_value = mock_client_instance
        
        # Mock page response
        mock_page = {
            "properties": {
                "Blog Status": {
                    "type": "status",
                    "status": {"name": "Live"}
                }
            }
        }
        
        mock_client_instance.pages.retrieve = AsyncMock(return_value=mock_page)
        
        async def run_test():
            result = await get_page_property("test-page-id", "Blog Status")
            self.assertEqual(result, "Live")
        
        asyncio.run(run_test())
    
    @patch('promaia.notion.pages.ensure_default_client')
    def test_get_block_content_with_mock(self, mock_client):
        """Test block content retrieval with mocked responses."""
        # Mock the client
        mock_client_instance = AsyncMock()
        mock_client.return_value = mock_client_instance
        
        # Mock blocks response
        mock_response = {
            "results": [
                {
                    "id": "block-1",
                    "type": "paragraph",
                    "paragraph": {
                        "rich_text": [
                            {
                                "text": {"content": "Test content"},
                                "plain_text": "Test content"
                            }
                        ]
                    },
                    "has_children": False
                }
            ],
            "has_more": False
        }
        
        mock_client_instance.blocks.children.list = AsyncMock(return_value=mock_response)
        
        async def run_test():
            result = await get_block_content("test-page-id")
            self.assertEqual(len(result), 1)
            self.assertEqual(result[0]["type"], "paragraph")
        
        asyncio.run(run_test())
    
    @patch('promaia.notion.pages.ensure_default_client')
    def test_get_pages_by_blog_status_with_mock(self, mock_client):
        """Test filtering pages by blog status with mocked responses."""
        # Mock the client
        mock_client_instance = AsyncMock()
        mock_client.return_value = mock_client_instance
        
        # Mock database response with filtered pages
        mock_response = {
            "results": [
                {
                    "id": "page-to-push",
                    "properties": {
                        "Blog Status": {
                            "type": "status", 
                            "status": {"name": "To push"}
                        }
                    }
                },
                {
                    "id": "page-live",
                    "properties": {
                        "Blog Status": {
                            "type": "status",
                            "status": {"name": "Live"}
                        }
                    }
                }
            ],
            "has_more": False
        }
        
        mock_client_instance.databases.query = AsyncMock(return_value=mock_response)
        
        async def run_test():
            result = await get_pages_by_blog_status(
                "test-db-id", 
                "Blog Status", 
                ["To push", "Live"]
            )
            self.assertEqual(len(result), 2)
            self.assertIn("page-to-push", [p["id"] for p in result])
            self.assertIn("page-live", [p["id"] for p in result])
        
        asyncio.run(run_test())
    
    def test_notion_to_webflow_item_conversion(self):
        """Test converting Notion page data to Webflow item format."""
        # Mock Notion page data
        mock_page = {
            "id": "test-page-id",
            "properties": {
                "Name": {
                    "type": "title",
                    "title": [{"plain_text": "Test Blog Post"}]
                },
                "Blog Status": {
                    "type": "status",
                    "status": {"name": "To push"}
                },
                "Webflow ID": {
                    "type": "rich_text",
                    "rich_text": [{"plain_text": "webflow-123"}]
                }
            }
        }
        
        async def run_test():
            webflow_data, stored_id = await notion_to_webflow_item(mock_page)
            
            # Check that basic conversion works
            self.assertIsInstance(webflow_data, dict)
            self.assertIn("name", webflow_data)
            self.assertEqual(stored_id, "webflow-123")
        
        with patch('promaia.webflow.sync.get_block_content') as mock_get_blocks:
            mock_get_blocks.return_value = []
            asyncio.run(run_test())
    
    def test_cms_help_command(self):
        """Test that CMS help command works without errors."""
        import subprocess
        
        try:
            result = subprocess.run(
                ["maia", "cms", "pull", "--help"],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            self.assertEqual(result.returncode, 0)
            self.assertIn("usage:", result.stdout)
            self.assertIn("cms pull", result.stdout)
            
        except subprocess.TimeoutExpired:
            self.fail("CMS help command timed out")
        except Exception as e:
            self.fail(f"CMS help command failed: {e}")
    
    def test_database_config_cms_entry(self):
        """Test that CMS database configuration exists and is valid."""
        from promaia.config.databases import get_database_manager
        
        try:
            db_manager = get_database_manager()
            cms_db = db_manager.get_database("cms")
            
            self.assertIsNotNone(cms_db, "CMS database configuration not found")
            self.assertEqual(cms_db.source_type, "notion")
            self.assertTrue(cms_db.sync_enabled)
            self.assertIsNotNone(cms_db.database_id)
            
        except Exception as e:
            self.fail(f"Failed to load CMS database configuration: {e}")
    
    def test_webflow_field_mapping(self):
        """Test that Webflow field mapping works correctly."""
        from promaia.webflow.sync import DEFAULT_FIELD_MAPPING
        
        # Check that required mappings exist
        self.assertIsInstance(DEFAULT_FIELD_MAPPING, dict)
        self.assertIn("Name", DEFAULT_FIELD_MAPPING)
        self.assertIn("Slug", DEFAULT_FIELD_MAPPING)
        
        # Check that mapping produces valid Webflow field names
        for notion_field, webflow_field in DEFAULT_FIELD_MAPPING.items():
            self.assertIsInstance(notion_field, str)
            self.assertIsInstance(webflow_field, str)
            self.assertGreater(len(webflow_field), 0)


if __name__ == "__main__":
    unittest.main() 