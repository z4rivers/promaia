"""
Tests for unified storage system.
"""
import unittest
import tempfile
import os
import json
import shutil
from pathlib import Path

# Add project root to sys.path 
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from promaia.storage.unified_storage import UnifiedStorage, get_unified_storage
from promaia.config.databases import DatabaseConfig

class TestUnifiedStorage(unittest.TestCase):
    
    def setUp(self):
        """Set up test environment for each test."""
        self.test_dir = tempfile.mkdtemp()
        self.config_file = os.path.join(self.test_dir, "test_config.json")
        
        # Use unique database path for each test to avoid interference
        import uuid
        db_name = f"test_registry_{uuid.uuid4().hex[:8]}.db"
        self.registry_db_path = os.path.join(self.test_dir, db_name)
        
        # Create test configuration
        test_config = {
            "global": {
                "markdown_base_directory": "data/md",
                "json_base_directory": "data/json", 
                "json_registry_db": self.registry_db_path
            },
            "databases": {
                "test_journal": {
                    "source_type": "notion",
                    "database_id": "test-db-id",
                    "nickname": "journal",
                    "workspace": "koii",
                    "markdown_directory": os.path.join(self.test_dir, "md/notion/koii/journal"),
                    "json_directory": os.path.join(self.test_dir, "json"),
                    "save_markdown": True,
                    "save_json": True,
                    "primary_format": "json"
                }
            },
            "workspaces": {
                "koii": {
                    "api_key": "test-key",
                    "enabled": True
                }
            }
        }
        
        with open(self.config_file, 'w') as f:
            json.dump(test_config, f)
            
        # Initialize storage with custom registry path to avoid interference
        from promaia.storage.json_registry import JSONContentRegistry
        from promaia.config.databases import DatabaseManager
        
        self.storage = UnifiedStorage(self.config_file)
        # Override with isolated registry
        self.storage.json_registry = JSONContentRegistry(self.registry_db_path)
        
    def tearDown(self):
        """Clean up after each test."""
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
            
    def test_storage_initialization(self):
        """Test that storage initializes correctly."""
        self.assertIsNotNone(self.storage.db_manager)
        self.assertIsNotNone(self.storage.json_registry)
        print("✓ Storage initialization works")
        
    def test_save_content_json_only(self):
        """Test saving content with JSON only."""
        db_config = DatabaseConfig("test_journal", {
            "workspace": "koii",
            "nickname": "journal",
            "markdown_directory": os.path.join(self.test_dir, "md/notion/koii/journal"),
            "json_directory": os.path.join(self.test_dir, "json"),
            "save_markdown": False,
            "save_json": True,
            "primary_format": "json"
        })
        
        content_data = {
            "page_id": "test-123",
            "title": "Test Page",
            "created_time": "2023-01-01T00:00:00Z",
            "properties": {"Status": "Draft"},
            "content": [{"type": "paragraph", "text": "Test content"}]
        }
        
        saved_paths = self.storage.save_content(
            page_id="test-123",
            title="Test Page",
            content_data=content_data,
            database_config=db_config
        )
        
        self.assertIn('json', saved_paths)
        self.assertTrue(os.path.exists(saved_paths['json']))
        self.assertNotIn('markdown', saved_paths)
        
        # Verify content in registry
        registry_info = self.storage.get_content_by_page_id("test-123")
        self.assertIsNotNone(registry_info)
        self.assertEqual(registry_info['workspace'], "koii")
        self.assertEqual(registry_info['database_name'], "journal")
        
        print("✓ JSON-only content saving works")
        
    def test_save_content_both_formats(self):
        """Test saving content in both markdown and JSON."""
        db_config = DatabaseConfig("test_journal", {
            "workspace": "koii",
            "nickname": "journal",
            "markdown_directory": os.path.join(self.test_dir, "md/notion/koii/journal"),
            "json_directory": os.path.join(self.test_dir, "json"),
            "save_markdown": True,
            "save_json": True,
            "primary_format": "json"
        })
        
        content_data = {
            "page_id": "test-456",
            "title": "Markdown Test",
            "properties": {"Priority": "High"}
        }
        
        markdown_content = "# Markdown Test\n\nThis is test content."
        
        saved_paths = self.storage.save_content(
            page_id="test-456",
            title="Markdown Test",
            content_data=content_data,
            database_config=db_config,
            markdown_content=markdown_content
        )
        
        self.assertIn('json', saved_paths)
        self.assertIn('markdown', saved_paths)
        self.assertTrue(os.path.exists(saved_paths['json']))
        self.assertTrue(os.path.exists(saved_paths['markdown']))
        
        # Verify markdown content
        with open(saved_paths['markdown'], 'r', encoding='utf-8') as f:
            saved_md = f.read()
        self.assertEqual(saved_md, markdown_content)
        
        print("✓ Dual-format content saving works")
        
    def test_get_existing_page_ids(self):
        """Test getting existing page IDs."""
        db_config = DatabaseConfig("test_journal", {
            "workspace": "koii",
            "nickname": "journal",
            "markdown_directory": os.path.join(self.test_dir, "md/notion/koii/journal"),
            "json_directory": os.path.join(self.test_dir, "json"),
            "save_json": True,
            "primary_format": "json"
        })
        
        # Save some content
        for i in range(3):
            content_data = {
                "page_id": f"test-{i}",
                "title": f"Test {i}"
            }
            
            self.storage.save_content(
                page_id=f"test-{i}",
                title=f"Test {i}",
                content_data=content_data,
                database_config=db_config
            )
        
        existing_ids = self.storage.get_existing_page_ids(db_config)
        self.assertEqual(len(existing_ids), 3)
        self.assertIn("test-0", existing_ids)
        self.assertIn("test-1", existing_ids)
        self.assertIn("test-2", existing_ids)
        
        print("✓ Existing page IDs retrieval works")
        
    def test_list_content_filtering(self):
        """Test listing content with filters."""
        # Create configs for different workspaces/databases
        koii_journal_config = DatabaseConfig("koii_journal", {
            "workspace": "koii",
            "nickname": "journal",
            "json_directory": os.path.join(self.test_dir, "json"),
            "save_json": True
        })
        
        koii_stories_config = DatabaseConfig("koii_stories", {
            "workspace": "koii", 
            "nickname": "stories",
            "json_directory": os.path.join(self.test_dir, "json"),
            "save_json": True
        })
        
        trass_journal_config = DatabaseConfig("trass_journal", {
            "workspace": "trass",
            "nickname": "journal",
            "json_directory": os.path.join(self.test_dir, "json"),
            "save_json": True
        })
        
        # Save content to different databases
        configs_and_data = [
            (koii_journal_config, "koii-journal-1", "Koii Journal Entry"),
            (koii_stories_config, "koii-stories-1", "Koii Story"),
            (trass_journal_config, "trass-journal-1", "Trass Journal Entry")
        ]
        
        for config, page_id, title in configs_and_data:
            content_data = {"page_id": page_id, "title": title}
            self.storage.save_content(
                page_id=page_id,
                title=title,
                content_data=content_data,
                database_config=config
            )
        
        # Test filtering by workspace
        koii_content = self.storage.list_content(workspace="koii")
        self.assertEqual(len(koii_content), 2)
        
        # Test filtering by workspace and database
        koii_journal = self.storage.list_content(workspace="koii", database_name="journal")
        self.assertEqual(len(koii_journal), 1)
        self.assertEqual(koii_journal[0]['page_id'], "koii-journal-1")
        
        print("✓ Content filtering works")
        
    def test_storage_stats(self):
        """Test getting storage statistics."""
        db_config = DatabaseConfig("test_journal", {
            "workspace": "koii",
            "nickname": "journal",
            "markdown_directory": os.path.join(self.test_dir, "md/notion/koii/journal"),
            "json_directory": os.path.join(self.test_dir, "json"),
            "save_markdown": True,
            "save_json": True
        })
        
        # Save some content
        content_data = {"page_id": "stats-test", "title": "Stats Test"}
        self.storage.save_content(
            page_id="stats-test",
            title="Stats Test", 
            content_data=content_data,
            database_config=db_config,
            markdown_content="# Stats Test"
        )
        
        stats = self.storage.get_storage_stats()
        
        self.assertIn('json_registry', stats)
        self.assertIn('markdown_directories', stats)
        self.assertGreater(stats['json_registry']['total_content'], 0)
        
        print("✓ Storage statistics work")
        
    def test_global_storage_instance(self):
        """Test the global storage instance function."""
        storage1 = get_unified_storage(self.config_file)
        storage2 = get_unified_storage(self.config_file)
        
        # Should return the same instance
        self.assertIs(storage1, storage2)
        
        print("✓ Global storage instance works")
    
    def test_files_exist_locally(self):
        """Test the files_exist_locally method for detecting missing and existing files."""
        db_config = DatabaseConfig("test_journal", {
            "workspace": "koii",
            "nickname": "journal",
            "markdown_directory": os.path.join(self.test_dir, "md/notion/koii/journal"),
            "json_directory": os.path.join(self.test_dir, "json"),
            "save_markdown": True,
            "save_json": True,
            "primary_format": "json"
        })
        
        page_id = "test-file-check-123"
        title = "Test File Check"
        
        # Initially no files should exist
        file_status = self.storage.files_exist_locally(page_id, title, db_config)
        self.assertFalse(file_status['json'])
        self.assertFalse(file_status['markdown'])
        
        # Save content to create files
        content_data = {
            "page_id": page_id,
            "title": title,
            "properties": {"Status": "Test"}
        }
        
        saved_paths = self.storage.save_content(
            page_id=page_id,
            title=title,
            content_data=content_data,
            database_config=db_config,
            markdown_content="# Test Content"
        )
        
        # Now both files should exist
        file_status = self.storage.files_exist_locally(page_id, title, db_config)
        self.assertTrue(file_status['json'])
        self.assertTrue(file_status['markdown'])
        
        # Remove JSON file and check again
        os.remove(saved_paths['json'])
        file_status = self.storage.files_exist_locally(page_id, title, db_config)
        self.assertFalse(file_status['json'])
        self.assertTrue(file_status['markdown'])
        
        # Remove markdown file and check again
        os.remove(saved_paths['markdown'])
        file_status = self.storage.files_exist_locally(page_id, title, db_config)
        self.assertFalse(file_status['json'])
        self.assertFalse(file_status['markdown'])
        
        print("✓ File existence detection works correctly")

if __name__ == '__main__':
    unittest.main() 