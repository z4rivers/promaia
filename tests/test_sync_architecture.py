import unittest
import os
import shutil
import sqlite3
import json
import subprocess
import sys
from pathlib import Path

# Add project root to sys.path to allow imports from maia
sys.path.insert(0, str(Path(__file__).parent.parent))

class TestSyncArchitecture(unittest.TestCase):
    
    @classmethod
    def setUpClass(cls):
        """Set up the test environment once for the entire test class."""
        cls.project_root = Path(__file__).parent.parent
        
        # Define paths for data and backups
        cls.data_path = cls.project_root / "data"
        
        import uuid
        cls.backup_dir = cls.project_root / f"test_backup_{uuid.uuid4().hex[:8]}"
        cls.backup_dir.mkdir(exist_ok=True)

        # Backup existing data
        if cls.data_path.exists():
            if (cls.backup_dir / "data_bak").exists():
                shutil.rmtree(cls.backup_dir / "data_bak")
            shutil.move(str(cls.data_path), str(cls.backup_dir / "data_bak"))
            
        print("Test environment set up. Existing data backed up.")

    def test_cli_database_list(self):
        """Test that the database list command works."""
        result = subprocess.run([
            sys.executable, "-m", "prom", "database", "list"
        ], cwd=self.project_root, capture_output=True, text=True)
        
        self.assertEqual(result.returncode, 0, f"Database list failed: {result.stderr}")
        self.assertIn("journal", result.stdout)
        print("✓ Database list command works")

    def test_cli_database_test(self):
        """Test that the database test command works."""
        result = subprocess.run([
            sys.executable, "-m", "prom", "database", "test", "journal"
        ], cwd=self.project_root, capture_output=True, text=True)
        
        self.assertEqual(result.returncode, 0, f"Database test failed: {result.stderr}")
        self.assertIn("Connection successful", result.stdout)
        print("✓ Database test command works")

    def test_cli_database_sync(self):
        """Test that the database sync command works."""
        result = subprocess.run([
            sys.executable, "-m", "prom", "database", "sync", 
            "--source", "journal", "--days", "1"
        ], cwd=self.project_root, capture_output=True, text=True)
        
        self.assertEqual(result.returncode, 0, f"Database sync failed: {result.stderr}")
        # The sync might return 0 pages if there's nothing to sync, that's OK
        print("✓ Database sync command works")

    def test_cli_database_status(self):
        """Test that the database status command works."""
        result = subprocess.run([
            sys.executable, "-m", "prom", "database", "status"
        ], cwd=self.project_root, capture_output=True, text=True)
        
        self.assertEqual(result.returncode, 0, f"Database status failed: {result.stderr}")
        self.assertIn("OVERALL STATUS", result.stdout)
        print("✓ Database status command works")

    def test_sync_respects_directory_structure(self):
        """Test that sync command maintains the correct directory structure and doesn't create old-style directories."""
        print("\n🧪 Testing sync directory structure compliance...")
        
        # Record initial directory state
        initial_dirs = set()
        if self.data_path.exists():
            for root, dirs, files in os.walk(self.data_path):
                for d in dirs:
                    initial_dirs.add(os.path.relpath(os.path.join(root, d), self.project_root))
        
        # Sync a small amount of data from journal
        result = subprocess.run([
            sys.executable, "-m", "prom", "database", "sync", 
            "--source", "journal", "--days", "3", "--force"
        ], cwd=self.project_root, capture_output=True, text=True)
        
        self.assertEqual(result.returncode, 0, f"Database sync failed: {result.stderr}")
        
        # Verify the expected directory structure exists
        expected_dirs = {
            "data",
            "data/json",
            "data/md",
            "data/md/notion", 
            "data/md/notion/koii",
            "data/md/notion/koii/journal"
        }
        
        for expected_dir in expected_dirs:
            expected_path = self.project_root / expected_dir
            self.assertTrue(expected_path.exists(), f"Expected directory {expected_dir} does not exist")
        
        # Verify old-style directories are NOT created
        forbidden_dirs = {
            "data/koii",
            "data/koii/md", 
            "data/koii/md/journal",
            "data/trass",
            "data/trass/journal",
            "data/json/journal"
        }
        
        for forbidden_dir in forbidden_dirs:
            forbidden_path = self.project_root / forbidden_dir
            self.assertFalse(forbidden_path.exists(), f"Forbidden old-style directory {forbidden_dir} was created")
        
        # Verify JSON files are in flat structure
        json_dir = self.project_root / "data/json"
        if json_dir.exists():
            json_files = list(json_dir.glob("*.json"))
            for json_file in json_files:
                # JSON files should be directly in data/json, not in subdirectories
                self.assertEqual(json_file.parent.name, "json", f"JSON file {json_file.name} is not in flat structure")
                
                # Verify JSON file naming convention: title_pageId.json
                self.assertTrue("_" in json_file.stem, f"JSON file {json_file.name} doesn't follow naming convention")
                self.assertTrue(len(json_file.stem.split("_")[-1]) >= 8, f"JSON file {json_file.name} doesn't have page ID")
        
        # Test sync with different database to ensure consistency
        result2 = subprocess.run([
            sys.executable, "-m", "prom", "database", "sync", 
            "--source", "trass.journal", "--days", "1", "--force"
        ], cwd=self.project_root, capture_output=True, text=True)
        
        self.assertEqual(result2.returncode, 0, f"Trass journal sync failed: {result2.stderr}")
        
        # Verify trass directories exist
        trass_dirs = {
            "data/md/notion/trass",
            "data/md/notion/trass/journal"
        }
        
        for trass_dir in trass_dirs:
            trass_path = self.project_root / trass_dir
            self.assertTrue(trass_path.exists(), f"Expected trass directory {trass_dir} does not exist")
        
        # Verify no old-style trass directories were created
        forbidden_trass_dirs = {
            "data/trass", 
            "data/trass/journal",
            "data/json/trass.journal"
        }
        
        for forbidden_dir in forbidden_trass_dirs:
            forbidden_path = self.project_root / forbidden_dir
            self.assertFalse(forbidden_path.exists(), f"Forbidden old-style trass directory {forbidden_dir} was created")
        
        # Verify JSON registry is working
        registry_db = self.project_root / "data/hybrid_metadata.db"
        if registry_db.exists():
            conn = sqlite3.connect(registry_db)
            cursor = conn.cursor()
            
            # Check that content was registered
            cursor.execute("SELECT COUNT(*) FROM content_registry")
            content_count = cursor.fetchone()[0]
            self.assertGreater(content_count, 0, "No content was registered in JSON registry")
            
            # Verify workspace separation
            cursor.execute("SELECT DISTINCT workspace FROM content_registry")
            workspaces = [row[0] for row in cursor.fetchall()]
            self.assertIn("koii", workspaces, "Koii workspace not found in registry")
            
            conn.close()
        
        # Check registry stats command
        result3 = subprocess.run([
            sys.executable, "-m", "prom", "migration", "registry-stats"
        ], cwd=self.project_root, capture_output=True, text=True)
        
        self.assertEqual(result3.returncode, 0, f"Registry stats failed: {result3.stderr}")
        self.assertIn("Total content entries:", result3.stdout)
        self.assertIn("koii:", result3.stdout)
        
        print("✓ Sync respects directory structure")
        print("✓ No old-style directories created") 
        print("✓ JSON files in flat structure")
        print("✓ JSON registry working")
        print("✓ Multi-workspace sync working")

    @classmethod
    def tearDownClass(cls):
        """Restore the original data after all tests are done."""
        import time
        
        # Clean up test-generated files with retry logic
        for attempt in range(3):
            try:
                if cls.data_path.exists():
                    shutil.rmtree(cls.data_path)
                break
            except OSError as e:
                if attempt < 2:
                    print(f"Retry {attempt + 1}: Failed to remove test files: {e}")
                    time.sleep(0.5)
                else:
                    print(f"Warning: Could not remove test files after 3 attempts: {e}")

        # Restore backups with retry and better conflict handling
        if (cls.backup_dir / "data_bak").exists():
            for attempt in range(3):
                try:
                    # Ensure target doesn't exist
                    if cls.data_path.exists():
                        shutil.rmtree(cls.data_path)
                    
                    # Use copy + remove instead of move to avoid filesystem conflicts
                    shutil.copytree(str(cls.backup_dir / "data_bak"), str(cls.data_path))
                    shutil.rmtree(cls.backup_dir / "data_bak")
                    break
                except OSError as e:
                    if attempt < 2:
                        print(f"Retry {attempt + 1}: Failed to restore data backup: {e}")
                        time.sleep(0.5)
                    else:
                        print(f"Warning: Could not restore data backup after 3 attempts: {e}")
        

            
        # Clean up backup directory
        if cls.backup_dir.exists():
            try:
                shutil.rmtree(cls.backup_dir)
            except OSError as e:
                print(f"Warning: Could not remove backup directory: {e}")
                
        print("\nTest environment torn down. Original data restored.")

if __name__ == '__main__':
    unittest.main() 