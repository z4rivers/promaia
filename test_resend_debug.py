#!/usr/bin/env python3
"""Debug script to test Resend email sending."""
import os
import resend

# Set up the API key
resend.api_key = 're_2i8No6Qw_MCUrVqEcvsQMfTbkXidhwkpf'

print("🧪 Testing Resend API directly...\n")

try:
    # Send a test email
    response = resend.Emails.send({
        "from": "Koii Benvenutto <hello@koiib.com>",
        "to": ["koii.create@gmail.com"],
        "subject": "[DEBUG TEST] Testing Resend API",
        "text": "This is a debug test to check Resend API response.",
        "html": "<p>This is a <strong>debug test</strong> to check Resend API response.</p>",
        "reply_to": "me@koiib.com"
    })

    print(f"✅ Response received!")
    print(f"Response type: {type(response)}")
    print(f"Response value: {response}")
    print(f"Response repr: {repr(response)}")

    # Try different ways to access the ID
    print(f"\nTrying to extract ID:")
    print(f"  response.get('id'): {response.get('id') if hasattr(response, 'get') else 'N/A'}")
    print(f"  response['id']: {response['id'] if isinstance(response, dict) else 'N/A'}")
    print(f"  response.id: {response.id if hasattr(response, 'id') else 'N/A'}")

    # Check if it's a dict-like object
    if hasattr(response, '__dict__'):
        print(f"\nResponse __dict__: {response.__dict__}")

    if hasattr(response, 'keys'):
        print(f"\nResponse keys: {list(response.keys())}")

except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
