#!/usr/bin/env python3
"""Test script for image path detection improvements."""

import sys
from pathlib import Path

# Add the promaia module to the path
sys.path.insert(0, str(Path(__file__).parent))

from promaia.chat.interface import _is_likely_image_path


def test_image_path_detection():
    """Test the _is_likely_image_path function with various inputs."""

    test_cases = [
        # URLs that should NOT be detected as image paths
        ("Google Sheets URL", "https://docs.google.com/spreadsheets/d/1khgKRhUuTY4TDMWYdzRkwkeVHMjsa0oB-z8Ljq2dvyo/edit?gid=592614362#gid=592614362", False),
        ("Google Docs URL", "https://docs.google.com/document/d/abc123/edit", False),
        ("GitHub URL", "https://github.com/user/repo/blob/main/file.py", False),
        ("HTTP URL", "http://example.com/path/to/something", False),
        ("FTP URL", "ftp://ftp.example.com/files/data.txt", False),
        ("www URL", "www.example.com/page", False),
        ("Custom protocol", "myprotocol://path/to/resource", False),
        ("Email address", "user@example.com", False),

        # Valid image paths that SHOULD be detected
        ("Image with extension", "/path/to/image.jpg", True),
        ("PNG file", "photo.png", True),
        ("Relative path with extension", "./images/photo.jpg", True),
        ("Nested path", "dir/subdir/image.png", True),
        ("Path with escaped spaces", "/path/to/my\\ image.jpg", True),
        ("Home directory path", "~/Pictures/photo.png", True),
        ("Deep nested path", "a/b/c/d/file.txt", True),

        # Edge cases
        ("URL with image extension", "https://example.com/image.jpg", False),  # Still a URL
        ("Path-like acronym", "VAT/EORI", False),  # Should not be detected
        ("Simple dir/file", "images/photo", False),  # Only 2 components, no extension
        ("Single word", "image", False),  # Not a path
        ("Sentence with slash", "This is text/sentence", False),  # Multiple words
    ]

    print("Testing image path detection...\n")
    print(f"{'Test Case':<30} {'Input':<80} {'Expected':<10} {'Result':<10} {'Status':<10}")
    print("=" * 140)

    passed = 0
    failed = 0

    for test_name, test_input, expected in test_cases:
        result = _is_likely_image_path(test_input)
        status = "✅ PASS" if result == expected else "❌ FAIL"

        if result == expected:
            passed += 1
        else:
            failed += 1

        # Truncate long inputs for display
        display_input = test_input if len(test_input) < 77 else test_input[:74] + "..."

        print(f"{test_name:<30} {display_input:<80} {str(expected):<10} {str(result):<10} {status:<10}")

    print("=" * 140)
    print(f"\nResults: {passed} passed, {failed} failed out of {len(test_cases)} tests")

    if failed == 0:
        print("✅ All tests passed!")
        return 0
    else:
        print(f"❌ {failed} test(s) failed")
        return 1


if __name__ == "__main__":
    sys.exit(test_image_path_detection())
