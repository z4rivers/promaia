#!/usr/bin/env python3
"""
Test script to process a single email thread for debugging.
Much faster than running full refresh on all drafts.

Usage:
    python test_single_email.py
    
This will process the most recent email in your inbox.
"""
import asyncio
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from promaia.mail.processor import EmailProcessor
from promaia.mail.classifier import EmailClassifier
from promaia.mail.context_builder import ResponseContextBuilder
from promaia.mail.response_generator import ResponseGenerator
from promaia.connectors.gmail_connector import GmailConnector
from promaia.config.databases import get_database_manager


async def test_single_email(workspace: str = "trass", subject_filter: str = None):
    """
    Test processing a single email.
    
    Args:
        workspace: Workspace to use (default: trass)
        subject_filter: Optional subject keyword to filter by
    """
    print(f"\n{'='*60}")
    print(f"Testing Single Email Processing")
    print(f"Workspace: {workspace}")
    print(f"{'='*60}\n")
    
    # Get Gmail database for workspace
    db_manager = get_database_manager()
    gmail_dbs = [
        db for db in db_manager.get_workspace_databases(workspace)
        if db.source_type == "gmail"
    ]
    
    if not gmail_dbs:
        print(f"❌ No Gmail database found for workspace '{workspace}'")
        return
    
    gmail_db = gmail_dbs[0]
    user_email = gmail_db.database_id
    print(f"📧 User email: {user_email}\n")
    
    # Connect to Gmail
    print("🔌 Connecting to Gmail...")
    connector = GmailConnector({
        "database_id": user_email,
        "workspace": workspace,
        "gmail_content_mode": "full_thread"
    })
    
    await connector.connect()
    print("✅ Connected\n")
    
    # Fetch recent threads
    print("📬 Fetching recent threads...")
    service = connector.service
    
    # Get threads from inbox
    results = service.users().threads().list(
        userId='me',
        maxResults=10,
        labelIds=['INBOX']
    ).execute()
    
    threads = results.get('threads', [])
    if not threads:
        print("❌ No threads found")
        return
    
    print(f"Found {len(threads)} recent threads\n")
    
    # If subject filter provided, find matching thread
    selected_thread = None
    if subject_filter:
        print(f"🔍 Searching for subject containing: '{subject_filter}'")
        for thread_info in threads:
            thread_data = service.users().threads().get(
                userId='me',
                id=thread_info['id'],
                format='full'
            ).execute()
            
            thread = connector._process_thread_data(thread_data)
            if thread and subject_filter.lower() in thread.get('subject', '').lower():
                selected_thread = thread
                print(f"✅ Found: {thread['subject']}\n")
                break
        
        if not selected_thread:
            print(f"❌ No thread found with subject containing '{subject_filter}'")
            return
    else:
        # Use most recent thread
        thread_data = service.users().threads().get(
            userId='me',
            id=threads[0]['id'],
            format='full'
        ).execute()
        selected_thread = connector._process_thread_data(thread_data)
        print(f"📨 Using most recent thread: {selected_thread['subject']}\n")
    
    # Initialize components
    classifier = EmailClassifier()
    context_builder = ResponseContextBuilder()
    response_generator = ResponseGenerator()
    
    print(f"📚 Learning patterns: data/mail_response_patterns/{workspace}/successful_responses.json")
    
    # Step 1: Classify
    print(f"{'='*60}")
    print("STEP 1: CLASSIFICATION")
    print(f"{'='*60}\n")
    
    print("🤖 Classifying email...")
    classification = await classifier.classify(selected_thread, user_email=user_email, workspace=workspace)
    
    print(f"📊 Classification Results:")
    print(f"   Pertains to me: {classification['pertains_to_me']}")
    print(f"   Is spam: {classification['is_spam']}")
    print(f"   Addressed to user: {classification['addressed_to_user']}")
    print(f"   Requires response: {classification['requires_response']}")
    print(f"   Reasoning: {classification['reasoning']}\n")
    
    if not classifier.should_generate_draft(classification):
        print("⏭️  Email classified as SKIP - no draft will be generated")
        print(f"   Status: {classifier.get_draft_status(classification)}")
        return
    
    # Step 2: Build Context
    print(f"{'='*60}")
    print("STEP 2: CONTEXT BUILDING")
    print(f"{'='*60}\n")
    
    print("🔍 Building context via vector search...")
    context = await context_builder.build_context(selected_thread, workspace)
    print(f"✅ Found {context.total_sources} relevant documents\n")
    
    # Step 3: Generate Response
    print(f"{'='*60}")
    print("STEP 3: RESPONSE GENERATION")
    print(f"{'='*60}\n")
    
    print("✍️  Generating response...")
    response = await response_generator.generate_response(selected_thread, context)
    
    print(f"✅ Generated response:")
    print(f"   Subject: {response['subject']}")
    print(f"   Body length: {len(response['body'])} chars")
    print(f"   Model: {response['model']}\n")
    
    print(f"{'='*60}")
    print("DRAFT PREVIEW")
    print(f"{'='*60}\n")
    print(response['body'])
    print(f"\n{'='*60}\n")
    
    # Check for logs
    import glob
    log_files = sorted(glob.glob("context_logs/mail_draft_logs/*.txt"), reverse=True)
    if log_files:
        latest_log = log_files[0]
        print(f"📝 Log saved to: {latest_log}")
        
        # Show grep test
        print(f"\n🔍 Testing greppable headers:")
        with open(latest_log, 'r') as f:
            content = f.read()
            headers = [line for line in content.split('\n') if line.startswith('===')]
            for header in headers[:10]:  # Show first 10
                print(f"   {header}")
    
    print(f"\n✅ Test complete!")


if __name__ == "__main__":
    # Parse command line arguments
    workspace = "trass"
    subject_filter = None
    
    if len(sys.argv) > 1:
        workspace = sys.argv[1]
    if len(sys.argv) > 2:
        subject_filter = sys.argv[2]
    
    print("\n" + "="*60)
    print("SINGLE EMAIL TEST SCRIPT")
    print("="*60)
    print(f"\nUsage: python {sys.argv[0]} [workspace] [subject_filter]")
    print(f"\nCurrent settings:")
    print(f"  Workspace: {workspace}")
    print(f"  Subject filter: {subject_filter or '(most recent)'}")
    print()
    
    asyncio.run(test_single_email(workspace, subject_filter))

