import unittest
import os
import shutil
import subprocess
import sys
from pathlib import Path

class TestDirectoryStructureRegression(unittest.TestCase):
    """Dedicated test to prevent regression of the sync directory structure bug."""
    
    @classmethod
    def setUpClass(cls):
        """Set up the test environment."""
        cls.project_root = Path(__file__).parent.parent
        
        # Define paths for data and backups
        cls.data_path = cls.project_root / "data"
        import uuid
        cls.backup_dir = cls.project_root / f"test_backup_regression_{uuid.uuid4().hex[:8]}"
        cls.backup_dir.mkdir(exist_ok=True)

        # Backup existing data
        if cls.data_path.exists():
            if (cls.backup_dir / "data_bak").exists():
                shutil.rmtree(cls.backup_dir / "data_bak")
            shutil.move(str(cls.data_path), str(cls.backup_dir / "data_bak"))
            
        print("Regression test environment set up.")

    def test_sync_never_creates_old_style_directories(self):
        """
        CRITICAL REGRESSION TEST: Ensure sync command never creates old-style directories.
        
        This test specifically prevents the bug where sync command would create files in 
        old directory structures like:
        - data/koii/md/journal/
        - data/trass/journal/ 
        - data/json/journal/
        
        Instead of the correct unified structure:
        - data/json/ (flat)
        - data/md/notion/{workspace}/{database}/ (hierarchical)
        """
        print("\n🔍 REGRESSION TEST: Checking for old-style directory creation...")
        
        # List of forbidden directory patterns that should NEVER be created
        FORBIDDEN_PATTERNS = [
            "data/koii",
            "data/koii/md", 
            "data/koii/md/journal",
            "data/koii/md/cms",
            "data/koii/md/stories",
            "data/koii/md/epics", 
            "data/koii/md/projects",
            "data/koii/md/awakenings",
            "data/trass",
            "data/trass/journal",
            "data/trass/stories",
            "data/json/journal",
            "data/json/cms", 
            "data/json/stories",
            "data/json/epics",
            "data/json/projects",
            "data/json/awakenings",
            "data/json/trass.journal",
            "data/json/trass.stories"
        ]
        
        # Test multiple database syncs to ensure consistency
        test_databases = ["journal", "trass.journal"]
        
        for db_name in test_databases:
            print(f"  Testing {db_name}...")
            
            # Sync with minimal data
            result = subprocess.run([
                "maia", "database", "sync", 
                "--source", db_name, "--days", "1", "--force"
            ], cwd=self.project_root, capture_output=True, text=True)
            
            # Sync should succeed
            self.assertEqual(result.returncode, 0, 
                f"Sync failed for {db_name}: {result.stderr}")
            
            # Check that no forbidden directories were created
            for forbidden_pattern in FORBIDDEN_PATTERNS:
                forbidden_path = self.project_root / forbidden_pattern
                self.assertFalse(forbidden_path.exists(), 
                    f"🚨 REGRESSION DETECTED: Forbidden old-style directory {forbidden_pattern} was created during sync of {db_name}")
        
        # Verify the correct directory structure exists
        expected_structure = [
            "data",
            "data/json",
            "data/md", 
            "data/md/notion",
            "data/md/notion/koii",
            "data/md/notion/trass"
        ]
        
        for expected_dir in expected_structure:
            expected_path = self.project_root / expected_dir
            self.assertTrue(expected_path.exists(), 
                f"Expected directory {expected_dir} was not created")
        
        # Verify JSON files are in flat structure (no subdirectories in data/json)
        json_dir = self.project_root / "data/json"
        if json_dir.exists():
            # Should only contain files, no subdirectories
            subdirs = [item for item in json_dir.iterdir() if item.is_dir()]
            self.assertEqual(len(subdirs), 0, 
                f"Found unexpected subdirectories in data/json: {[d.name for d in subdirs]}")
            
            # All files should be .json files
            json_files = list(json_dir.glob("*.json"))
            all_files = list(json_dir.glob("*"))
            non_json_files = [f for f in all_files if f not in json_files and f.name != ".DS_Store"]
            self.assertEqual(len(non_json_files), 0,
                f"Found non-JSON files in data/json: {[f.name for f in non_json_files]}")
        
        print("  ✓ No old-style directories created")
        print("  ✓ Correct directory structure maintained")
        print("  ✓ JSON files in flat structure")
        print("🎉 REGRESSION TEST PASSED: Directory structure is correct")

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
                    
                    # Use copy + remove instead of move to avoid filesystem conflicts
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
                
        print("Regression test environment cleaned up.")

if __name__ == '__main__':
    unittest.main() 