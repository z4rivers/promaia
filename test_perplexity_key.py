#!/usr/bin/env python3
"""
Simple script to test Perplexity API key
Run with: python3 test_perplexity_key.py
"""

import os
import json
import urllib.request
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def test_perplexity_key():
    """Test if the Perplexity API key works"""
    api_key = os.getenv('PERPLEXITY_API_KEY')
    
    if not api_key:
        print("❌ PERPLEXITY_API_KEY not found in environment variables")
        return False
    
    print(f"✅ Found API key: {api_key[:15]}...")
    
    try:
        url = "https://api.perplexity.ai/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": "sonar-pro",
            "messages": [{"role": "user", "content": "Test: What is 2+2?"}]
        }
        
        request = urllib.request.Request(
            url, 
            data=json.dumps(data).encode('utf-8'),
            headers=headers
        )
        
        print("🔄 Testing API call...")
        with urllib.request.urlopen(request, timeout=30) as response:
            result = json.loads(response.read().decode('utf-8'))
        
        if 'choices' in result and len(result['choices']) > 0:
            content = result['choices'][0]['message']['content']
            print("✅ API key works! Response:")
            print(f"   {content[:100]}...")
            return True
        else:
            print("⚠️ Unexpected response format")
            return False
            
    except urllib.error.HTTPError as e:
        if e.code == 401:
            print("❌ API key is invalid or expired")
        elif e.code == 429:
            print("⚠️ Rate limit exceeded")
        else:
            print(f"❌ HTTP Error {e.code}: {e.reason}")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    print("🧪 Testing Perplexity API Key")
    print("=" * 40)
    success = test_perplexity_key()
    print("=" * 40)
    if success:
        print("🎉 Your Perplexity API key is working!")
    else:
        print("💡 Get a new key at: https://www.perplexity.ai/settings/api")
