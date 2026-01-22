#!/usr/bin/env python3
"""
Quick test script for the notification system.
Run this to verify notifications work on your system.
"""

from promaia.utils.notifications import send_notification, send_sync_complete_notification

def test_basic_notification():
    """Test basic notification."""
    print("🧪 Testing basic notification...")
    result = send_notification(
        title="Test Notification",
        message="This is a test from Maia",
        sound="Glass"
    )
    if result:
        print("✅ Basic notification sent successfully")
    else:
        print("❌ Failed to send basic notification")
    return result

def test_sync_notification():
    """Test sync completion notification."""
    print("\n🧪 Testing sync completion notification...")
    
    # Test successful sync
    print("  Testing success notification...")
    result1 = send_sync_complete_notification(
        success_count=5,
        failed_count=0,
        duration=10.5
    )
    
    import time
    time.sleep(2)  # Wait a bit between notifications
    
    # Test partial failure notification
    print("  Testing failure notification...")
    result2 = send_sync_complete_notification(
        success_count=3,
        failed_count=2,
        duration=8.2
    )
    
    if result1 and result2:
        print("✅ Sync notifications sent successfully")
    else:
        print("❌ Some notifications failed")
    
    return result1 and result2

def main():
    print("=" * 60)
    print("MAIA NOTIFICATION SYSTEM TEST")
    print("=" * 60)
    
    # Run tests
    basic_ok = test_basic_notification()
    sync_ok = test_sync_notification()
    
    print("\n" + "=" * 60)
    if basic_ok and sync_ok:
        print("✅ ALL TESTS PASSED - Notification system is working!")
    else:
        print("⚠️  SOME TESTS FAILED - Check system notification settings")
    print("=" * 60)

if __name__ == "__main__":
    main()
