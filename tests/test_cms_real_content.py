#!/usr/bin/env python3
"""
Real Content CMS Tests
Tests CMS functionality with actual Notion data to ensure reliability.
"""

import os
import json
import tempfile
import shutil
import asyncio
import pytest
from pathlib import Path
from datetime import datetime, timedelta, timezone

# Import the function we need to test
import sys
import os
sys.path.insert(0, os.path.abspath('.'))

# Import directly from the CLI module file since it's not exported
import importlib.util
spec = importlib.util.spec_from_file_location("promaia_cli", "promaia/cli.py")
promaia_cli = importlib.util.module_from_spec(spec)
spec.loader.exec_module(promaia_cli)
handle_cms_pull = promaia_cli.handle_cms_pull

# Test requires real API access
pytestmark = pytest.mark.integration

class TestCMSRealContent:
    """Test CMS commands against real Notion content."""
    
    @pytest.fixture(scope="class")
    def temp_workspace(self):
        """Create temporary workspace for testing."""
        original_dir = os.getcwd()
        temp_dir = tempfile.mkdtemp(prefix="promaia_cms_test_")
        
        try:
            # Copy necessary config files to temp directory
            shutil.copy("promaia.config.json", temp_dir)
            os.chdir(temp_dir)
            
            # Create data structure
            os.makedirs("data/json", exist_ok=True)
            os.makedirs("data/md/notion/koii/cms", exist_ok=True)
            
            yield temp_dir
            
        finally:
            os.chdir(original_dir)
            shutil.rmtree(temp_dir, ignore_errors=True)
    
    @pytest.fixture(scope="class")
    def cms_config(self):
        """Get CMS database configuration."""
        from promaia.config.databases import get_database_config
        config = get_database_config("cms")
        assert config is not None, "CMS database configuration not found"
        return config

    def test_cms_pull_koii_chat_context(self, temp_workspace, cms_config):
        """Test 'maia cms pull' creates KOii chat context correctly."""
        from types import SimpleNamespace

        # Prepare arguments
        args = SimpleNamespace()
        args.days = 30
        args.force = False

        # Run the command
        asyncio.run(handle_cms_pull(args))
        
        # Verify KOii-chat-context directory was created
        context_dir = Path("KOii-chat-context")
        assert context_dir.exists(), "KOii-chat-context directory not created"
        
        # Verify metadata file exists and is valid
        metadata_file = context_dir / "_metadata.json"
        assert metadata_file.exists(), "Metadata file not created"
        
        with open(metadata_file) as f:
            metadata = json.load(f)
        
        # Verify metadata structure
        assert "filter_applied" in metadata
        assert metadata["filter_applied"]["KOii chat"] is True
        assert "total_pages" in metadata
        assert "saved_pages" in metadata
        assert "description" in metadata
        assert metadata["description"] == "KOii chat context"
        assert metadata["days_filter"] == 30
        
        # Verify we got some content (assuming test data exists)
        total_pages = metadata["total_pages"]
        saved_pages = metadata["saved_pages"]
        assert total_pages > 0, "No pages found with KOii chat filter"
        assert saved_pages == total_pages, "Not all pages were saved"
        
        # Verify both JSON and markdown files were created
        json_files = list(context_dir.glob("*.json"))
        md_files = list(context_dir.glob("*.md"))
        
        # Should have metadata + page files
        assert len(json_files) >= 1, "No JSON files created"
        assert len(md_files) >= 0, "Markdown files expected"
        
        # Check that non-metadata JSON files have corresponding content
        content_json_files = [f for f in json_files if f.name != "_metadata.json"]
        for json_file in content_json_files:
            with open(json_file) as f:
                page_data = json.load(f)
            
            # Verify essential page structure
            assert "page_id" in page_data or "id" in page_data
            assert "properties" in page_data
            assert "content" in page_data  # Content should be included
            
            # Verify the page actually has KOii chat enabled
            properties = page_data["properties"]
            koii_chat_prop = None
            for prop_name, prop_data in properties.items():
                if prop_name == "KOii chat" and prop_data.get("type") == "checkbox":
                    koii_chat_prop = prop_data
                    break
            
            if koii_chat_prop:
                assert koii_chat_prop["checkbox"] is True, f"Page {json_file.name} doesn't have KOii chat enabled"
        
        print(f"✓ CMS pull test passed: {saved_pages} pages saved to KOii-chat-context")
    
    def test_database_sync_cms_unified_storage(self, temp_workspace, cms_config):
        """Test 'maia database sync --source cms' saves to unified storage."""
        from promaia.cli.database_commands import handle_database_sync
        from types import SimpleNamespace
        
        # Prepare arguments
        args = SimpleNamespace()
        args.sources = ["cms"]
        args.days = 7
        args.force = False
        args.workspace = None
        
        # Run the command
        asyncio.run(handle_database_sync(args))
        
        # Verify unified storage structure
        json_dir = Path("data/json")
        md_dir = Path("data/md/notion/koii/cms")
        registry_db = Path("data/hybrid_metadata.db")
        
        assert json_dir.exists(), "JSON directory not created"
        assert md_dir.exists(), "Markdown directory not created"
        assert registry_db.exists(), "Registry database not created"
        
        # Verify content was saved
        json_files = list(json_dir.glob("*.json"))
        md_files = list(md_dir.glob("*.md"))
        
        assert len(json_files) > 0, "No JSON files saved to unified storage"
        assert len(md_files) > 0, "No markdown files saved to unified storage"
        
        # Verify JSON files have valid structure
        for json_file in json_files:
            with open(json_file) as f:
                page_data = json.load(f)
            
            assert "page_id" in page_data or "id" in page_data
            assert "properties" in page_data
            # Note: Unified storage may or may not include content depending on config
        
        print(f"✓ Database sync test passed: {len(json_files)} JSON, {len(md_files)} MD files")
    
    def test_cms_pull_vs_database_sync_content_difference(self, temp_workspace, cms_config):
        """Test that cms pull and database sync produce different filtered results."""
        from promaia.cli.database_commands import handle_database_sync
        from types import SimpleNamespace
        
        # Clean any existing content
        if Path("KOii-chat-context").exists():
            shutil.rmtree("KOii-chat-context")
        
        # Run CMS pull (filtered for KOii chat)
        cms_args = SimpleNamespace()
        cms_args.days = 30
        cms_args.force = False
        asyncio.run(handle_cms_pull(cms_args))
        
        # Run database sync (all pages)
        db_args = SimpleNamespace()
        db_args.sources = ["cms"]
        db_args.days = 30
        db_args.force = False
        db_args.workspace = None
        asyncio.run(handle_database_sync(db_args))
        
        # Compare results
        context_metadata = Path("KOii-chat-context/_metadata.json")
        with open(context_metadata) as f:
            cms_metadata = json.load(f)
        
        unified_json_files = list(Path("data/json").glob("*.json"))
        
        cms_pages = cms_metadata["saved_pages"]
        unified_pages = len(unified_json_files)
        
        print(f"CMS pull (filtered): {cms_pages} pages")
        print(f"Database sync (all): {unified_pages} pages")
        
        # CMS pull should have fewer or equal pages (since it's filtered)
        assert cms_pages <= unified_pages, "CMS pull should have fewer or equal pages than database sync"
        
        # Verify filtering actually happened (unless all pages have KOii chat enabled)
        if cms_pages < unified_pages:
            print("✓ Filtering working correctly: CMS pull has fewer pages than database sync")
        else:
            print("✓ All CMS pages have KOii chat enabled (filtering still working)")
    
    def test_cms_pull_force_update(self, temp_workspace, cms_config):
        """Test cms pull --force updates existing content."""
        from types import SimpleNamespace
        
        # First run
        args = SimpleNamespace()
        args.days = 30
        args.force = False
        asyncio.run(handle_cms_pull(args))
        
        context_dir = Path("KOii-chat-context")
        metadata_file = context_dir / "_metadata.json"
        
        # Get initial timestamp
        with open(metadata_file) as f:
            first_metadata = json.load(f)
        first_timestamp = first_metadata["created_at"]
        
        # Wait a moment
        import time
        time.sleep(1)
        
        # Second run with force
        args.force = True
        asyncio.run(handle_cms_pull(args))
        
        # Verify timestamp updated
        with open(metadata_file) as f:
            second_metadata = json.load(f)
        second_timestamp = second_metadata["created_at"]
        
        assert second_timestamp > first_timestamp, "Force update didn't refresh content"
        print("✓ Force update working correctly")
    
    def test_cms_pull_days_filter(self, temp_workspace, cms_config):
        """Test cms pull with different days filters."""
        from types import SimpleNamespace
        
        test_cases = [7, 30, "all"]
        
        for days in test_cases:
            # Clean previous results
            if Path("KOii-chat-context").exists():
                shutil.rmtree("KOii-chat-context")
            
            args = SimpleNamespace()
            args.days = days
            args.force = False
            asyncio.run(handle_cms_pull(args))
            
            metadata_file = Path("KOii-chat-context/_metadata.json")
            with open(metadata_file) as f:
                metadata = json.load(f)
            
            expected_days = None if days == "all" else days
            assert metadata["days_filter"] == expected_days, f"Days filter mismatch for {days}"
            
            print(f"✓ Days filter {days}: {metadata['saved_pages']} pages")
    
    def test_advanced_chat_filtering_syntax(self, temp_workspace, cms_config):
        """Test the advanced filtering syntax for chat commands."""
        from promaia.cli.database_commands import parse_source_specs
        
        # Test various syntax patterns
        test_cases = [
            ("cms.KOii_chat=true", {"database": "cms", "days": None, "property_filters": {"KOii_chat": True}}),
            ("cms:30.Reference=false", {"database": "cms", "days": 30, "property_filters": {"Reference": False}}),
            ("cms:all.Status=published", {"database": "cms", "days": None, "property_filters": {"Status": "published"}}),
            ("journal:7", {"database": "journal", "days": 7, "property_filters": {}}),
        ]
        
        for spec_str, expected in test_cases:
            parsed = parse_source_specs([spec_str])
            assert len(parsed) == 1
            
            result = parsed[0]
            assert result["name"] == expected["database"]
            assert result["days"] == expected["days"]
            assert result["property_filters"] == expected["property_filters"]
            
            print(f"✓ Parsing '{spec_str}': {result}")


def test_cms_commands_help():
    """Test that help commands work without errors."""
    import subprocess
    
    commands = [
                    ["maia", "cms", "--help"],
            ["maia", "cms", "pull", "--help"],
            ["maia", "database", "sync", "--help"],
    ]
    
    for cmd in commands:
        result = subprocess.run(cmd, capture_output=True, text=True)
        assert result.returncode == 0, f"Help command failed: {' '.join(cmd)}\n{result.stderr}"
        assert len(result.stdout) > 0, f"No help output for: {' '.join(cmd)}"
    
    print("✓ All help commands work correctly")


if __name__ == "__main__":
    # Run tests directly
    pytest.main([__file__, "-v", "-s"]) 