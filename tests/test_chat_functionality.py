"""
Test chat functionality to ensure markdown files are loaded correctly.
"""
import unittest
import os
import sys
import shutil
import tempfile
import uuid
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from promaia.storage.files import read_markdown_files_from_directory
from promaia.storage.markdown_files import get_md_output_dir_for_database
from promaia.chat.interface import create_system_prompt
from promaia.config.databases import get_database_config

class TestChatFunctionality(unittest.TestCase):
    """Test chat system can correctly load and process markdown files."""
    
    @classmethod
    def setUpClass(cls):
        """Set up test environment."""
        cls.project_root = PROJECT_ROOT
        cls.data_path = cls.project_root / "data"
        
        # Create unique backup directory for this test
        cls.backup_dir = cls.project_root / f"test_backup_chat_{uuid.uuid4().hex[:8]}"
        cls.backup_dir.mkdir(exist_ok=True)
        
        # Backup existing data if it exists
        if cls.data_path.exists():
            if (cls.backup_dir / "data_bak").exists():
                shutil.rmtree(cls.backup_dir / "data_bak")
            shutil.move(str(cls.data_path), str(cls.backup_dir / "data_bak"))
        
        print("Chat test environment set up. Existing data backed up.")
    
    def test_markdown_directory_path_resolution(self):
        """Test that the chat system resolves markdown directory paths correctly."""
        print("\n🧪 Testing markdown directory path resolution...")
        
        # Test journal database path resolution
        journal_md_dir = get_md_output_dir_for_database('journal')
        expected_path = os.path.join(str(self.project_root), "data/md/notion/koii/journal")
        
        self.assertEqual(journal_md_dir, expected_path)
        print(f"✓ Journal markdown directory resolved correctly: {journal_md_dir}")
        
        # Test with workspace-qualified name
        qualified_journal_md_dir = get_md_output_dir_for_database('koii.journal')
        self.assertEqual(qualified_journal_md_dir, expected_path)
        print(f"✓ Qualified journal markdown directory resolved correctly")
        
        # Test trass workspace
        trass_md_dir = get_md_output_dir_for_database('trass.journal')
        expected_trass_path = os.path.join(str(self.project_root), "data/md/notion/trass/journal")
        self.assertEqual(trass_md_dir, expected_trass_path)
        print(f"✓ Trass journal markdown directory resolved correctly: {trass_md_dir}")
    
    def test_chat_loads_existing_markdown_files(self):
        """Test that chat can load existing markdown files from sync."""
        print("\n🧪 Testing chat loading of existing markdown files...")
        
        # First, ensure we have some synced data
        import subprocess
        result = subprocess.run([
            "maia", "database", "sync", 
            "--source", "journal", "--days", "3", "--force"
        ], cwd=self.project_root, capture_output=True, text=True)
        
        self.assertEqual(result.returncode, 0, f"Sync failed: {result.stderr}")
        print("✓ Synced journal data successfully")
        
        # Test markdown directory loading
        journal_md_dir = get_md_output_dir_for_database('journal')
        self.assertTrue(os.path.exists(journal_md_dir), f"Markdown directory doesn't exist: {journal_md_dir}")
        
        # Load markdown files
        pages = read_markdown_files_from_directory(journal_md_dir, days=7)
        self.assertGreater(len(pages), 0, "No markdown files were loaded")
        print(f"✓ Loaded {len(pages)} markdown files from {journal_md_dir}")
        
        # Verify page structure
        if pages:
            sample_page = pages[0]
            required_keys = ['date', 'date_obj', 'content', 'file_path', 'filename']
            for key in required_keys:
                self.assertIn(key, sample_page, f"Missing key '{key}' in page structure")
            
            # Verify content is not empty
            self.assertGreater(len(sample_page['content'].strip()), 0, "Page content is empty")
            print(f"✓ Page structure is correct, sample date: {sample_page['date']}")
    
    def test_multi_source_data_structure(self):
        """Test that multi-source data structure is created correctly for chat."""
        print("\n🧪 Testing multi-source data structure creation...")
        
        # Create sample multi-source data
        journal_md_dir = get_md_output_dir_for_database('journal')
        journal_pages = read_markdown_files_from_directory(journal_md_dir, days=7)
        
        # Test multi-source data structure
        multi_source_data = {
            'journal': journal_pages
        }
        
        total_entries = sum(len(pages) for pages in multi_source_data.values())
        self.assertGreater(total_entries, 0, "Multi-source data is empty")
        print(f"✓ Multi-source data contains {total_entries} entries from {len(multi_source_data)} sources")
        
        # Test system prompt generation
        system_prompt = create_system_prompt([], [], "openai", multi_source_data=multi_source_data)
        self.assertGreater(len(system_prompt), 100, "System prompt is too short")
        self.assertIn("journal", system_prompt.lower(), "System prompt doesn't mention journal data")
        print(f"✓ System prompt generated successfully ({len(system_prompt)} characters)")
    
    def test_chat_handles_multiple_databases(self):
        """Test that chat can handle multiple databases if available."""
        print("\n🧪 Testing multi-database chat functionality...")
        
        # Try to sync trass journal as well
        import subprocess
        result = subprocess.run([
            "maia", "database", "sync", 
            "--source", "trass.journal", "--days", "1", "--force"
        ], cwd=self.project_root, capture_output=True, text=True)
        
        # Don't fail the test if trass sync fails (might not have data)
        if result.returncode == 0:
            print("✓ Synced trass journal data successfully")
            
            # Test loading from multiple sources
            journal_md_dir = get_md_output_dir_for_database('journal')
            trass_md_dir = get_md_output_dir_for_database('trass.journal')
            
            journal_pages = read_markdown_files_from_directory(journal_md_dir, days=7)
            trass_pages = read_markdown_files_from_directory(trass_md_dir, days=7)
            
            multi_source_data = {
                'journal': journal_pages,
                'trass.journal': trass_pages
            }
            
            total_entries = sum(len(pages) for pages in multi_source_data.values())
            print(f"✓ Multi-database data contains {total_entries} entries from {len(multi_source_data)} sources")
            
            # Test system prompt with multiple sources
            system_prompt = create_system_prompt([], [], "openai", multi_source_data=multi_source_data)
            self.assertGreater(len(system_prompt), 100, "Multi-source system prompt is too short")
            print(f"✓ Multi-database system prompt generated successfully")
        else:
            print("⚠ Trass sync failed (expected if no trass data), testing single source only")
    
    def test_chat_empty_directory_handling(self):
        """Test that chat handles empty or non-existent directories gracefully."""
        print("\n🧪 Testing empty directory handling...")
        
        # Test with non-existent directory
        fake_dir = "/path/that/does/not/exist"
        pages = read_markdown_files_from_directory(fake_dir, days=7)
        self.assertEqual(len(pages), 0, "Should return empty list for non-existent directory")
        print("✓ Non-existent directory handled gracefully")
        
        # Test with empty directory
        with tempfile.TemporaryDirectory() as temp_dir:
            pages = read_markdown_files_from_directory(temp_dir, days=7)
            self.assertEqual(len(pages), 0, "Should return empty list for empty directory")
            print("✓ Empty directory handled gracefully")
    
    def test_database_config_integration(self):
        """Test that chat integrates properly with database configuration."""
        print("\n🧪 Testing database configuration integration...")
        
        # Test that database config exists and has correct paths
        db_config = get_database_config('journal')
        self.assertIsNotNone(db_config, "Journal database config not found")
        
        # Verify the markdown directory is in the config
        self.assertTrue(hasattr(db_config, 'markdown_directory'), "Database config missing markdown_directory")
        expected_structure = "data/md/notion"
        self.assertIn(expected_structure, db_config.markdown_directory, 
                     f"Markdown directory doesn't use unified structure: {db_config.markdown_directory}")
        print(f"✓ Database config has correct markdown directory: {db_config.markdown_directory}")
        
        # Test that the path resolution works
        resolved_path = get_md_output_dir_for_database('journal')
        self.assertIn(db_config.markdown_directory, resolved_path, 
                     "Resolved path doesn't match config directory")
        print("✓ Path resolution matches database configuration")
    
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
            except OSError as e:
                if attempt < 2:
                    print(f"Retry {attempt + 1}: Failed to remove data directory: {e}")
                    time.sleep(0.5)
                else:
                    print(f"Warning: Could not remove data directory after 3 attempts: {e}")
        
        # Restore backup with retry and better conflict handling
        if (cls.backup_dir / "data_bak").exists():
            for attempt in range(3):
                try:
                    # Ensure target doesn't exist
                    if cls.data_path.exists():
                        shutil.rmtree(cls.data_path)
                    
                    # Use copy2 + remove instead of move to avoid filesystem conflicts
                    shutil.copytree(str(cls.backup_dir / "data_bak"), str(cls.data_path))
                    shutil.rmtree(cls.backup_dir / "data_bak")
                    break
                except OSError as e:
                    if attempt < 2:
                        print(f"Retry {attempt + 1}: Failed to restore backup: {e}")
                        time.sleep(0.5)
                    else:
                        print(f"Warning: Could not restore backup after 3 attempts: {e}")
        
        # Clean up backup directory
        if cls.backup_dir.exists():
            try:
                shutil.rmtree(cls.backup_dir)
            except OSError as e:
                print(f"Warning: Could not remove backup directory: {e}")
        
        print("\nChat test environment torn down. Original data restored.")

if __name__ == '__main__':
    unittest.main() 