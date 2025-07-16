#!/usr/bin/env python3
"""
Test script to analyze a specific Gmail thread
"""
import asyncio
import sys
import os
import json

# Add the current directory to Python path
sys.path.insert(0, os.getcwd())

from promaia.connectors.gmail_connector import GmailConnector
from promaia.config.databases import get_database_manager


async def test_specific_thread():
    """Test retrieving a specific Gmail thread to understand message structure"""
    print("🔍 Testing specific Gmail thread retrieval...")
    
    # Get Gmail database config
    db_manager = get_database_manager()
    gmail_config = db_manager.get_database("gmail")
    
    if not gmail_config:
        print("❌ Gmail database config not found")
        return
    
    # Create Gmail connector
    connector = GmailConnector(gmail_config.to_dict())
    
    if not await connector.connect():
        print("❌ Failed to connect to Gmail")
        return
    
    print("✅ Connected to Gmail")
    
    # Get recent emails to analyze thread structure
    print(f"🔍 Getting recent emails to analyze thread structure...")
    
    result = connector.service.users().messages().list(
        userId='me',
        maxResults=10,
        q='in:inbox'
    ).execute()
    
    found_messages = result.get('messages', [])
    print(f"📧 Found {len(found_messages)} recent messages")
    
    if not found_messages:
        print("❌ No messages found")
        return
    
    try:
        # Group by thread
        threads = {}
        for msg in found_messages:
            thread_id = msg.get('threadId')
            if thread_id not in threads:
                threads[thread_id] = []
            threads[thread_id].append(msg['id'])
        
        print(f"🧵 Found {len(threads)} unique threads")
        
        if not threads:
            print("❌ No threads found")
            return
        
        # Analyze each thread
        for i, (thread_id, message_ids) in enumerate(threads.items()):
            print(f"\n📋 Thread {i+1}: {thread_id}")
            print(f"   Messages in thread: {len(message_ids)}")
            
            # Get full thread data
            thread_data = connector.service.users().threads().get(
                userId='me', 
                id=thread_id,
                format='full'
            ).execute()
            
            messages_in_thread = thread_data.get('messages', [])
            print(f"   Full thread has {len(messages_in_thread)} messages")
            
            # Analyze each message in the thread
            for j, message in enumerate(messages_in_thread):
                headers = {h['name'].lower(): h['value'] 
                          for h in message.get('payload', {}).get('headers', [])}
                
                subject = headers.get('subject', 'No Subject')
                from_addr = headers.get('from', 'Unknown')
                to_addr = headers.get('to', '')
                date_str = headers.get('date', '')
                
                print(f"      Message {j+1}:")
                print(f"         From: {from_addr}")
                print(f"         To: {to_addr}")
                print(f"         Subject: {subject}")
                print(f"         Date: {date_str}")
                
                # Check if this is one of the forwarded emails
                if "Fwd:" in subject:
                    print(f"         🔄 FORWARDED EMAIL DETECTED")
                
                # Check if MCP sent
                if "mcp" in from_addr.lower() or "claude" in from_addr.lower():
                    print(f"         🤖 MCP-SENT EMAIL DETECTED") 
                    
        # Test our thread processing
        print(f"\n🔧 Testing our thread processing...")
        thread_id = list(threads.keys())[0]  # Use first thread
        processed_data = connector._process_thread_data(thread_data)
        
        if processed_data:
            print(f"✅ Processed thread data:")
            print(f"   Subject: {processed_data.get('subject')}")
            print(f"   Message count: {processed_data.get('message_count')}")
            print(f"   Thread ID: {processed_data.get('thread_id')}")
            
            # Show first few lines of conversation
            conversation = processed_data.get('conversation_body', '')
            lines = conversation.split('\n')[:10]
            print(f"   First 10 lines of conversation:")
            for line in lines:
                print(f"      {line}")
            
        else:
            print(f"❌ Failed to process thread data")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_specific_thread()) 