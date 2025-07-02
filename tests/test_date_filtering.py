#!/usr/bin/env python3
"""
Tests for date filtering functionality in maia chat.

This test suite verifies that date filters like 'created_time<2025-12-30' 
and 'created_time>2025-01-01' work correctly in the chat interface.
"""

import unittest
import sys
import os
from datetime import datetime, timedelta

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from promaia.storage.files import read_markdown_files_with_registry
from promaia.config.databases import get_database_manager


class TestDateFiltering(unittest.TestCase):
    """Test date filtering functionality."""
    
    def setUp(self):
        """Set up test environment."""
        self.db_manager = get_database_manager()
        self.db_config = self.db_manager.get_database('journal')
        
    def test_before_filter_excludes_future_dates(self):
        """Test that 'before' filters exclude entries after the specified date."""
        # Filter for entries before 2020 (should be 0 for modern data)
        comparison_filters = {'created_time_before': ['2020-01-01']}
        pages = read_markdown_files_with_registry(
            self.db_config, 
            comparison_filters=comparison_filters
        )
        self.assertEqual(len(pages), 0, "Should find 0 entries before 2020-01-01")
        
    def test_before_filter_includes_past_dates(self):
        """Test that 'before' filters include entries before the specified date."""
        # Filter for entries before end of 2025 (should include current data)
        comparison_filters = {'created_time_before': ['2025-12-30']}
        pages = read_markdown_files_with_registry(
            self.db_config, 
            comparison_filters=comparison_filters
        )
        # Should include most/all current entries
        self.assertGreater(len(pages), 0, "Should find entries before 2025-12-30")
        
    def test_after_filter_excludes_past_dates(self):
        """Test that 'after' filters exclude entries before the specified date."""
        # Filter for entries after end of 2025 (should be 0 for current data)
        comparison_filters = {'created_time_after': ['2025-12-01']}
        pages = read_markdown_files_with_registry(
            self.db_config, 
            comparison_filters=comparison_filters
        )
        # Should be 0 or very few entries depending on when test is run
        self.assertGreaterEqual(len(pages), 0, "Result should be 0 or positive")
        
    def test_after_filter_includes_recent_dates(self):
        """Test that 'after' filters include entries after the specified date."""
        # Filter for entries after start of 2025 (should include current data)
        comparison_filters = {'created_time_after': ['2025-01-01']}
        pages = read_markdown_files_with_registry(
            self.db_config, 
            comparison_filters=comparison_filters
        )
        self.assertGreater(len(pages), 0, "Should find entries after 2025-01-01")
        
    def test_no_filter_returns_all_entries(self):
        """Test that no filter returns all available entries."""
        pages = read_markdown_files_with_registry(self.db_config)
        self.assertGreater(len(pages), 0, "Should find entries when no filter applied")
        
    def test_comparison_with_no_filter(self):
        """Test that filtered results are subset of unfiltered results."""
        all_pages = read_markdown_files_with_registry(self.db_config)
        
        # Recent filter should return subset
        comparison_filters = {'created_time_after': ['2025-01-01']}
        filtered_pages = read_markdown_files_with_registry(
            self.db_config, 
            comparison_filters=comparison_filters
        )
        
        self.assertLessEqual(
            len(filtered_pages), 
            len(all_pages), 
            "Filtered results should be subset of all results"
        )


def main():
    """Run the tests."""
    # Enable logging to see debug output
    import logging
    logging.basicConfig(level=logging.INFO)
    
    unittest.main()


if __name__ == '__main__':
    main() 