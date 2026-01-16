#!/usr/bin/env python3
"""
Test script to verify PDF and document detection works correctly.
"""

import sys
sys.path.insert(0, '/Users/kb20250422/Documents/dev/promaia')

from promaia.chat.interface import _is_likely_file_path, _detect_file_paths_in_message

def test_file_detection():
    """Test that various file paths are detected correctly."""

    test_cases = [
        # (input_string, expected_result, expected_type)
        ('/Users/kb20250422/Downloads/Appointment\\ details\\ -\\ Opendock\\ Scheduling\\ Portal.pdf', True, 'document'),
        ('/path/to/document.pdf', True, 'document'),
        ('/path/to/image.png', True, 'image'),
        ('/path/to/spreadsheet.xlsx', True, 'document'),
        ('regular text', False, ''),
        ('VAT/EORI', False, ''),
        ('/Users/kb20250422/file.doc', True, 'document'),
    ]

    print("Testing _is_likely_file_path():")
    print("-" * 60)

    for test_input, expected_is_file, expected_type in test_cases:
        is_file, file_type = _is_likely_file_path(test_input)
        status = "✅" if (is_file == expected_is_file and file_type == expected_type) else "❌"
        print(f"{status} Input: {test_input}")
        print(f"   Expected: is_file={expected_is_file}, type='{expected_type}'")
        print(f"   Got:      is_file={is_file}, type='{file_type}'")
        print()

def test_message_detection():
    """Test that files are detected in user messages."""

    test_messages = [
        "Would you please send this scheduling appt thread /Users/kb20250422/Downloads/Appointment\\ details\\ -\\ Opendock\\ Scheduling\\ Portal.pdf to Fionn in the correct thread",
        "Here are the documents: /path/to/report.pdf and /path/to/data.xlsx",
        "Check out this image /path/to/photo.png",
        "Regular message with no files",
    ]

    print("\nTesting _detect_file_paths_in_message():")
    print("-" * 60)

    for message in test_messages:
        cleaned_msg, file_paths = _detect_file_paths_in_message(message)
        print(f"Input: {message}")
        print(f"Cleaned: {cleaned_msg}")
        print(f"Files detected: {len(file_paths)}")
        for path, ftype in file_paths:
            print(f"  - {path} ({ftype})")
        print()

if __name__ == "__main__":
    test_file_detection()
    test_message_detection()
    print("✅ All tests completed!")
