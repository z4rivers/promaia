"""
Tests for JSON Content Registry functionality.
"""
import unittest
import tempfile
import os
import json
from pathlib import Path

# Add project root to sys.path 
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from promaia.storage.json_registry import JSONContentRegistry, get_json_registry

class TestJSONContentRegistry(unittest.TestCase):
    
    def setUp(self):
        """Set up test environment for each test."""
        self.test_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.test_dir, "test_registry.db")
        self.registry = JSONContentRegistry(self.db_path)
        
    def tearDown(self):
        """Clean up after each test."""
        import shutil
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
            
    def test_registry_initialization(self):
        """Test that registry initializes correctly."""
        self.assertTrue(os.path.exists(self.db_path))
        self.assertEqual(self.registry.db_path, self.db_path)
        print("✓ Registry initialization works")
        
    def test_register_content(self):
        """Test registering content in the registry."""
        # Create a test JSON file
        test_file = os.path.join(self.test_dir, "test_content.json")
        content_data = {
            "page_id": "test-123",
            "title": "Test Page",
            "created_time": "2023-01-01T00:00:00Z",
            "last_edited_time": "2023-01-01T12:00:00Z",
            "content": [{"type": "paragraph", "text": "Test content"}],
            "properties": {"Status": "Draft"}
        }
        
        with open(test_file, 'w') as f:
            json.dump(content_data, f)
        
        # Register the content
        success = self.registry.register_content(
            page_id="test-123",
            workspace="koii",
            database_name="journal",
            file_path=test_file,
            content_data=content_data
        )
        
        self.assertTrue(success)
        print("✓ Content registration works")
        
    def test_get_content_info(self):
        """Test retrieving content information."""
        # Register content first
        test_file = os.path.join(self.test_dir, "test_content.json")
        content_data = {
            "page_id": "test-456",
            "title": "Another Test Page",
            "properties": {"Priority": "High"}
        }
        
        with open(test_file, 'w') as f:
            json.dump(content_data, f)
            
        self.registry.register_content(
            page_id="test-456",
            workspace="trass",
            database_name="stories",
            file_path=test_file,
            content_data=content_data
        )
        
        # Retrieve the content info
        info = self.registry.get_content_info("test-456")
        
        self.assertIsNotNone(info)
        self.assertEqual(info['page_id'], "test-456")
        self.assertEqual(info['workspace'], "trass")
        self.assertEqual(info['database_name'], "stories")
        self.assertEqual(info['title'], "Another Test Page")
        print("✓ Content retrieval works")
        
    def test_list_content_with_filters(self):
        """Test listing content with workspace and database filters."""
        # Register multiple pieces of content
        for i, (workspace, db_name) in enumerate([
            ("koii", "journal"), 
            ("koii", "stories"), 
            ("trass", "journal")
        ]):
            test_file = os.path.join(self.test_dir, f"content_{i}.json")
            content_data = {"page_id": f"test-{i}", "title": f"Test {i}"}
            
            with open(test_file, 'w') as f:
                json.dump(content_data, f)
                
            self.registry.register_content(
                page_id=f"test-{i}",
                workspace=workspace,
                database_name=db_name,
                file_path=test_file,
                content_data=content_data
            )
        
        # Test filtering by workspace
        koii_content = self.registry.list_content(workspace="koii")
        self.assertEqual(len(koii_content), 2)
        
        # Test filtering by workspace and database
        koii_journal = self.registry.list_content(workspace="koii", database_name="journal")
        self.assertEqual(len(koii_journal), 1)
        self.assertEqual(koii_journal[0]['page_id'], "test-0")
        
        print("✓ Content filtering works")
        
    def test_remove_content(self):
        """Test removing content from registry."""
        # Register content
        test_file = os.path.join(self.test_dir, "test_content.json")
        content_data = {"page_id": "test-remove", "title": "To Remove"}
        
        with open(test_file, 'w') as f:
            json.dump(content_data, f)
            
        self.registry.register_content(
            page_id="test-remove",
            workspace="koii",
            database_name="journal",
            file_path=test_file,
            content_data=content_data
        )
        
        # Verify it exists
        self.assertIsNotNone(self.registry.get_content_info("test-remove"))
        
        # Remove it
        removed = self.registry.remove_content("test-remove")
        self.assertTrue(removed)
        
        # Verify it's gone
        self.assertIsNone(self.registry.get_content_info("test-remove"))
        print("✓ Content removal works")
        
    def test_get_stats(self):
        """Test getting registry statistics."""
        # Register some content
        for i, (workspace, db_name) in enumerate([
            ("koii", "journal"), 
            ("koii", "stories"), 
            ("trass", "journal")
        ]):
            test_file = os.path.join(self.test_dir, f"stats_content_{i}.json")
            content_data = {"page_id": f"stats-{i}", "title": f"Stats Test {i}"}
            
            with open(test_file, 'w') as f:
                json.dump(content_data, f)
                
            self.registry.register_content(
                page_id=f"stats-{i}",
                workspace=workspace,
                database_name=db_name,
                file_path=test_file,
                content_data=content_data
            )
        
        stats = self.registry.get_stats()
        
        self.assertEqual(stats['total_content'], 3)
        self.assertEqual(stats['by_workspace']['koii'], 2)
        self.assertEqual(stats['by_workspace']['trass'], 1)
        self.assertEqual(stats['by_database']['koii']['journal'], 1)
        self.assertEqual(stats['by_database']['koii']['stories'], 1)
        
        print("✓ Statistics generation works")
        
    def test_global_registry_instance(self):
        """Test the global registry instance function."""
        registry1 = get_json_registry(self.db_path)
        registry2 = get_json_registry(self.db_path)
        
        # Should return the same instance
        self.assertIs(registry1, registry2)
        
        # But different path should create new instance
        other_path = os.path.join(self.test_dir, "other_registry.db")
        registry3 = get_json_registry(other_path)
        self.assertIsNot(registry1, registry3)
        
        print("✓ Global registry instance works")

if __name__ == '__main__':
    unittest.main() 