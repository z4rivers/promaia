"""
Tests for general CLI functionality.
"""
import unittest
import subprocess
import sys
from pathlib import Path

class TestCLICommands(unittest.TestCase):
    
    @classmethod
    def setUpClass(cls):
        """Set up test environment."""
        cls.project_root = Path(__file__).parent.parent
        
    def test_main_help_command(self):
        """Test that main help command works."""
        result = subprocess.run([
            "maia", "--help"
        ], cwd=self.project_root, capture_output=True, text=True)
        
        self.assertEqual(result.returncode, 0, f"Main help failed: {result.stderr}")
        self.assertIn("Promaia CLI", result.stdout)
        self.assertIn("database", result.stdout)
        self.assertIn("workspace", result.stdout)
        print("✓ Main help command works")
        
    def test_model_help_command(self):
        """Test that model help command works."""
        result = subprocess.run([
            "maia", "model", "--help"
        ], cwd=self.project_root, capture_output=True, text=True)
        
        self.assertEqual(result.returncode, 0, f"Model help failed: {result.stderr}")
        self.assertIn("model", result.stdout.lower())
        print("✓ Model help command works")
        
    def test_convert_help_command(self):
        """Test that convert help command works."""
        result = subprocess.run([
            "maia", "convert", "--help"
        ], cwd=self.project_root, capture_output=True, text=True)
        
        self.assertEqual(result.returncode, 0, f"Convert help failed: {result.stderr}")
        self.assertIn("convert", result.stdout.lower())
        print("✓ Convert help command works")
        
    def test_list_formats_command(self):
        """Test that list-formats command works."""
        result = subprocess.run([
            "maia", "list-formats", "journal"
        ], cwd=self.project_root, capture_output=True, text=True)
        
        self.assertEqual(result.returncode, 0, f"List formats failed: {result.stderr}")
        # Should show available formats
        print("✓ List formats command works")
        
    def test_cleanup_help_command(self):
        """Test that cleanup help command works."""
        result = subprocess.run([
            "maia", "cleanup", "--help"
        ], cwd=self.project_root, capture_output=True, text=True)
        
        self.assertEqual(result.returncode, 0, f"Cleanup help failed: {result.stderr}")
        self.assertIn("cleanup", result.stdout.lower())
        print("✓ Cleanup help command works")

if __name__ == '__main__':
    unittest.main() 