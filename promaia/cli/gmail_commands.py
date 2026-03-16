"""
Gmail integration commands for the Maia CLI.
"""
import os
import json
import asyncio
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

async def handle_gmail_setup(args):
    """Handle 'maia workspace gmail-setup' command."""
    workspace = args.workspace
    email = args.email
    
    print(f"🔧 Setting up Gmail OAuth2 for workspace '{workspace}' and email '{email}'")
    print()
    
    # Create workspace credentials directory
    config_dir = os.path.join("credentials", workspace)
    os.makedirs(config_dir, exist_ok=True)
    
    credentials_file = os.path.join(config_dir, "gmail_credentials.json")
    
    # Check if credentials already exist
    if os.path.exists(credentials_file):
        overwrite = input(f"Gmail credentials already exist for workspace '{workspace}'. Overwrite? (y/n): ").strip().lower()
        if overwrite != 'y':
            print("Setup cancelled.")
            return
    
    print("📋 Gmail OAuth2 Setup Instructions:")
    print()
    print("1. Go to the Google Cloud Console: https://console.cloud.google.com/")
    print("2. Create a new project or select an existing one")
    print("3. Enable the Gmail API:")
    print("   - Go to 'APIs & Services' > 'Library'")
    print("   - Search for 'Gmail API' and enable it")
    print("4. Create OAuth2 credentials:")
    print("   - Go to 'APIs & Services' > 'Credentials'")
    print("   - Click 'Create Credentials' > 'OAuth client ID'")
    print("   - Choose 'Desktop application'")
    print("   - Download the JSON file")
    print("5. Save the downloaded JSON file as:")
    print(f"   {os.path.abspath(credentials_file)}")
    print()
    
    input("Press Enter when you've completed the setup and saved the credentials file...")
    
    # Verify credentials file exists
    if not os.path.exists(credentials_file):
        print(f"❌ Credentials file not found at {credentials_file}")
        print("Please complete the setup and try again.")
        return
    
    # Verify credentials file is valid JSON
    try:
        with open(credentials_file, 'r', encoding='utf-8') as f:
            creds_data = json.load(f)
        
        # Basic validation
        if 'installed' not in creds_data and 'web' not in creds_data:
            print("❌ Invalid credentials file format.")
            print("Please ensure you downloaded the OAuth2 client credentials JSON file.")
            return
        
        print("✅ Credentials file validated successfully!")
        
    except json.JSONDecodeError:
        print("❌ Invalid JSON in credentials file.")
        print("Please ensure the file is a valid JSON file from Google Cloud Console.")
        return
    except Exception as e:
        print(f"❌ Error validating credentials file: {e}")
        return
    
    # Test the OAuth2 flow
    print()
    print("🔑 Testing OAuth2 authentication...")
    
    try:
        # Import here to handle optional dependencies
        from promaia.connectors.gmail_connector import GmailConnector
        
        # Create a test connector to verify OAuth flow
        test_config = {
            "database_id": email,
            "workspace": workspace
        }
        
        connector = GmailConnector(test_config)
        
        if await connector.test_connection():
            print("✅ Gmail OAuth2 setup completed successfully!")
            print(f"📧 Connected to Gmail account: {email}")
            print()
            print("You can now add Gmail as a database source:")
            print(f"  maia database add gmail_personal \\")
            print(f"    --source-type gmail \\")
            print(f"    --database-id {email} \\")
            print(f"    --workspace {workspace} \\")
            print(f"    --nickname gmail")
        else:
            print("❌ OAuth2 test failed. Please check your setup and try again.")
            
    except ImportError:
        print("❌ Gmail dependencies not installed.")
        print("Please install: pip install google-auth google-auth-oauthlib google-api-python-client")
    except Exception as e:
        print(f"❌ OAuth2 setup failed: {e}")
        print("Please check your credentials and try again.")

async def handle_gmail_test(args):
    """Handle 'maia gmail test' command."""
    workspace = getattr(args, 'workspace', None)
    email = getattr(args, 'email', None)
    
    if not workspace or not email:
        print("❌ Please specify --workspace and --email")
        return
    
    print(f"🧪 Testing Gmail connection for {email} in workspace '{workspace}'...")
    
    try:
        from promaia.connectors.gmail_connector import GmailConnector
        
        config = {
            "database_id": email,
            "workspace": workspace
        }
        
        connector = GmailConnector(config)
        
        if await connector.test_connection():
            print("✅ Gmail connection successful!")
            
            # Test a simple query
            print("📬 Testing email query...")
            threads = await connector.query_pages(limit=5)
            print(f"✅ Found {len(threads)} recent email threads")
            
            if threads:
                print("📨 Recent threads:")
                for i, thread in enumerate(threads[:3]):
                    subject = thread.get('subject', 'No Subject')[:50]
                    from_addr = thread.get('from', 'Unknown')
                    message_count = thread.get('message_count', 1)
                    print(f"  {i+1}. {subject}... (from: {from_addr}, messages: {message_count})")
        else:
            print("❌ Gmail connection failed")
            
    except ImportError:
        print("❌ Gmail dependencies not installed.")
        print("Install with: pip install google-auth google-auth-oauthlib google-api-python-client")
    except Exception as e:
        print(f"❌ Gmail test failed: {e}")

async def handle_gmail_labels(args):
    """Handle 'maia gmail labels' command."""
    workspace = getattr(args, 'workspace', None)
    email = getattr(args, 'email', None)
    
    if not workspace or not email:
        print("❌ Please specify --workspace and --email")
        return
    
    print(f"🏷️  Fetching Gmail labels for {email}...")
    
    try:
        from promaia.connectors.gmail_connector import GmailConnector
        
        config = {
            "database_id": email,
            "workspace": workspace
        }
        
        connector = GmailConnector(config)
        await connector.connect()
        
        # Get labels using Gmail API
        labels_result = connector.service.users().labels().list(userId='me').execute()
        labels = labels_result.get('labels', [])
        
        print(f"📋 Found {len(labels)} labels:")
        print()
        
        # Categorize labels
        system_labels = []
        user_labels = []
        
        for label in labels:
            label_name = label.get('name', '')
            label_type = label.get('type', 'user')
            
            if label_type == 'system':
                system_labels.append(label_name)
            else:
                user_labels.append(label_name)
        
        if system_labels:
            print("🔧 System Labels:")
            for label in sorted(system_labels):
                print(f"  - {label}")
            print()
        
        if user_labels:
            print("👤 User Labels:")
            for label in sorted(user_labels):
                print(f"  - {label}")
            print()
        
        if user_labels:
            print("💡 To sync only emails with a specific label, add this to your database config:")
            print('  "property_filters": {')
            print('    "label": "your-label-name"')
            print('  }')
        
    except ImportError:
        print("❌ Gmail dependencies not installed.")
        print("Install with: pip install google-auth google-auth-oauthlib google-api-python-client")
    except Exception as e:
        print(f"❌ Failed to fetch labels: {e}")

def add_gmail_commands(subparsers):
    """Add Gmail management commands to CLI."""
    gmail_parser = subparsers.add_parser('gmail', help='Gmail integration commands')
    gmail_subparsers = gmail_parser.add_subparsers(dest='gmail_command', required=True)
    
    # Gmail setup
    setup_parser = gmail_subparsers.add_parser('setup', help='Set up Gmail OAuth2 authentication')
    setup_parser.add_argument('workspace', help='Workspace name')
    setup_parser.add_argument('email', help='Gmail email address')
    setup_parser.set_defaults(func=handle_gmail_setup)
    
    # Gmail test
    test_parser = gmail_subparsers.add_parser('test', help='Test Gmail connection')
    test_parser.add_argument('--workspace', required=True, help='Workspace name')
    test_parser.add_argument('--email', required=True, help='Gmail email address')
    test_parser.set_defaults(func=handle_gmail_test)
    
    # Gmail labels
    labels_parser = gmail_subparsers.add_parser('labels', help='List Gmail labels')
    labels_parser.add_argument('--workspace', required=True, help='Workspace name')
    labels_parser.add_argument('--email', required=True, help='Gmail email address')
    labels_parser.set_defaults(func=handle_gmail_labels)

# Also add to workspace commands for backwards compatibility
def add_workspace_gmail_commands(workspace_subparsers):
    """Add Gmail setup to workspace commands."""
    gmail_setup_parser = workspace_subparsers.add_parser('gmail-setup', help='Set up Gmail OAuth2 for workspace')
    gmail_setup_parser.add_argument('workspace', help='Workspace name')
    gmail_setup_parser.add_argument('email', help='Gmail email address')
    gmail_setup_parser.set_defaults(func=handle_gmail_setup) 