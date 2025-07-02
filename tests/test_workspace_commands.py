"""
Tests for workspace management commands.
"""
import unittest
import subprocess
import sys
import tempfile
import os
from pathlib import Path

class TestWorkspaceCommands(unittest.TestCase):
    
    @classmethod
    def setUpClass(cls):
        """Set up test environment."""
        cls.project_root = Path(__file__).parent.parent
        
    def test_workspace_list_command(self):
        """Test that workspace list command works."""
        result = subprocess.run([
            sys.executable, "-m", "promaia", "workspace", "list"
        ], cwd=self.project_root, capture_output=True, text=True)
        
        self.assertEqual(result.returncode, 0, f"Workspace list failed: {result.stderr}")
        # Should show configured workspaces
        self.assertIn("koii", result.stdout.lower())
        print("✓ Workspace list command works")
        
    def test_workspace_help_command(self):
        """Test that workspace help command works."""
        result = subprocess.run([
            sys.executable, "-m", "promaia", "workspace", "--help"
        ], cwd=self.project_root, capture_output=True, text=True)
        
        self.assertEqual(result.returncode, 0, f"Workspace help failed: {result.stderr}")
        self.assertIn("workspace", result.stdout.lower())
        print("✓ Workspace help command works")

if __name__ == '__main__':
    unittest.main() 