"""
Tests for Gmail integration functionality.
"""
import unittest
from unittest.mock import Mock, patch, MagicMock
import json
import os
import tempfile
import shutil
from datetime import datetime, timezone

from promaia.connectors.gmail_connector import GmailConnector


class TestGmailIntegration(unittest.TestCase):
    """Test Gmail connector functionality."""
    
    def setUp(self):
        """Set up test environment."""
        self.test_dir = tempfile.mkdtemp()
        self.test_config = {
            'source_type': 'gmail',
            'database_id': 'test@example.com',
            'nickname': 'test_gmail',
            'workspace': 'test_workspace',
            'default_days': 7,
            'save_markdown': True,
            'save_json': True,
            'markdown_directory': os.path.join(self.test_dir, 'md'),
            'json_directory': os.path.join(self.test_dir, 'json'),
            'property_filters': {'label': 'important'}
        }
        
        # Create directories
        os.makedirs(self.test_config['markdown_directory'], exist_ok=True)
        os.makedirs(self.test_config['json_directory'], exist_ok=True)
        
        # Mock credentials path
        self.credentials_path = os.path.join(self.test_dir, 'credentials.json')
        self.token_path = os.path.join(self.test_dir, 'token.json')
    
    def tearDown(self):
        """Clean up test environment."""
        shutil.rmtree(self.test_dir)
    
    @patch('promaia.connectors.gmail_connector.build')
    @patch('promaia.connectors.gmail_connector.Credentials')
    def test_gmail_connector_initialization(self, mock_credentials, mock_build):
        """Test GmailConnector initialization."""
        # Mock credentials
        mock_creds = Mock()
        mock_credentials.from_authorized_user_file.return_value = mock_creds
        mock_creds.valid = True
        
        # Mock Gmail service
        mock_service = Mock()
        mock_build.return_value = mock_service
        
        connector = GmailConnector(self.test_config)
        
        self.assertEqual(connector.database_id, 'test@example.com')
        self.assertEqual(connector.nickname, 'test_gmail')
        self.assertEqual(connector.workspace, 'test_workspace')
    
    def test_build_gmail_query(self):
        """Test Gmail query building from Maia filters."""
        connector = GmailConnector(self.test_config)
        
        # Test with label filter
        config_with_label = self.test_config.copy()
        config_with_label['property_filters'] = {'label': 'important'}
        query = connector._build_gmail_query(config_with_label, 7)
        
        self.assertIn('label:important', query)
        self.assertIn('newer_than:7d', query)
    
    def test_build_gmail_query_multiple_labels(self):
        """Test Gmail query with multiple labels."""
        connector = GmailConnector(self.test_config)
        
        config_with_labels = self.test_config.copy()
        config_with_labels['property_filters'] = {'label': ['work', 'project']}
        query = connector._build_gmail_query(config_with_labels, 14)
        
        # Should create OR query for multiple labels
        self.assertIn('(label:work OR label:project)', query)
        self.assertIn('newer_than:14d', query)
    
    @patch('promaia.connectors.gmail_connector.build')
    @patch('promaia.connectors.gmail_connector.Credentials')
    def test_email_processing(self, mock_credentials, mock_build):
        """Test email processing and thread grouping."""
        # Mock credentials
        mock_creds = Mock()
        mock_credentials.from_authorized_user_file.return_value = mock_creds
        mock_creds.valid = True
        
        # Mock Gmail service with sample data
        mock_service = Mock()
        mock_build.return_value = mock_service
        
        # Mock thread list response
        mock_service.users().threads().list().execute.return_value = {
            'threads': [
                {'id': 'thread_123', 'snippet': 'Test thread'},
                {'id': 'thread_456', 'snippet': 'Another thread'}
            ]
        }
        
        # Mock thread get response
        sample_thread = {
            'id': 'thread_123',
            'messages': [
                {
                    'id': 'msg_1',
                    'threadId': 'thread_123',
                    'payload': {
                        'headers': [
                            {'name': 'Subject', 'value': 'Test Email'},
                            {'name': 'From', 'value': 'sender@example.com'},
                            {'name': 'To', 'value': 'test@example.com'},
                            {'name': 'Date', 'value': 'Mon, 15 Jan 2025 10:30:00 +0000'}
                        ],
                        'body': {'data': 'VGVzdCBlbWFpbCBjb250ZW50'} # Base64 for "Test email content"
                    },
                    'labelIds': ['INBOX', 'IMPORTANT']
                }
            ]
        }
        
        mock_service.users().threads().get().execute.return_value = sample_thread
        
        connector = GmailConnector(self.test_config)
        
        # Test sync
        with patch.object(connector, '_get_credentials') as mock_get_creds:
            mock_get_creds.return_value = mock_creds
            results = connector.sync(days=7)
        
        # Should have processed the thread
        self.assertGreater(len(results), 0)
    
    def test_markdown_generation(self):
        """Test markdown content generation."""
        connector = GmailConnector(self.test_config)
        
        # Sample thread data
        thread_data = {
            'id': 'thread_123',
            'subject': 'Test Email',
            'from': 'sender@example.com',
            'to': 'test@example.com',
            'date': '2025-01-15T10:30:00Z',
            'labels': ['inbox', 'important'],
            'has_attachments': False,
            'is_unread': False,
            'message_count': 1,
            'messages': [
                {
                    'from': 'sender@example.com',
                    'date': 'Mon, 15 Jan 2025 10:30:00',
                    'body': 'Test email content'
                }
            ]
        }
        
        markdown = connector._generate_markdown_content(thread_data)
        
        # Check key elements are present
        self.assertIn('# Email Thread: Test Email', markdown)
        self.assertIn('**From:** sender@example.com', markdown)
        self.assertIn('**To:** test@example.com', markdown)
        self.assertIn('**Labels:** inbox, important', markdown)
        self.assertIn('Test email content', markdown)
    
    def test_conversation_formatting(self):
        """Test multi-message conversation formatting."""
        connector = GmailConnector(self.test_config)
        
        # Sample conversation with multiple messages
        messages = [
            {
                'from': 'alice@example.com',
                'date': 'Mon, 15 Jan 2025 10:30:00',
                'body': 'Hi Bob, how are you?'
            },
            {
                'from': 'bob@example.com', 
                'date': 'Mon, 15 Jan 2025 11:15:00',
                'body': 'Hi Alice! I\'m doing well, thanks for asking.'
            },
            {
                'from': 'alice@example.com',
                'date': 'Mon, 15 Jan 2025 14:20:00', 
                'body': 'Great to hear! Let\'s catch up soon.'
            }
        ]
        
        conversation = connector._format_conversation(messages)
        
        # Check conversation structure
        self.assertIn('**Message 1**', conversation)
        self.assertIn('**Message 2**', conversation)
        self.assertIn('**Message 3**', conversation)
        self.assertIn('Hi Bob, how are you?', conversation)
        self.assertIn('Hi Alice! I\'m doing well', conversation)
        self.assertIn('Great to hear!', conversation)
    
    def test_filter_application(self):
        """Test property filter application."""
        connector = GmailConnector(self.test_config)
        
        # Test single label filter
        config_single = {'property_filters': {'label': 'work'}}
        query = connector._build_gmail_query(config_single, 7)
        self.assertIn('label:work', query)
        
        # Test multiple label filter
        config_multiple = {'property_filters': {'label': ['work', 'urgent']}}
        query = connector._build_gmail_query(config_multiple, 7)
        self.assertIn('(label:work OR label:urgent)', query)
        
        # Test no filter
        config_none = {'property_filters': {}}
        query = connector._build_gmail_query(config_none, 7)
        self.assertNotIn('label:', query)
    
    def test_date_filtering(self):
        """Test date-based filtering."""
        connector = GmailConnector(self.test_config)
        
        # Test various day ranges
        query_7 = connector._build_gmail_query({}, 7)
        self.assertIn('newer_than:7d', query_7)
        
        query_30 = connector._build_gmail_query({}, 30)
        self.assertIn('newer_than:30d', query_30)
        
        # Test no date filter (None)
        query_all = connector._build_gmail_query({}, None)
        self.assertNotIn('newer_than:', query_all)
    
    def test_error_handling(self):
        """Test error handling in Gmail connector."""
        connector = GmailConnector(self.test_config)
        
        # Test with invalid credentials path
        with patch.object(connector, '_get_credentials', side_effect=Exception("Credentials error")):
            with self.assertRaises(Exception):
                connector.sync(days=7)
    
    def test_incremental_sync(self):
        """Test incremental sync functionality."""
        # This would test last_sync_time based filtering
        # Implementation depends on how sync state is tracked
        connector = GmailConnector(self.test_config)
        
        # Mock a previous sync time
        config_with_sync = self.test_config.copy()
        config_with_sync['last_sync_time'] = '2025-01-14T00:00:00Z'
        
        # Should build query considering last sync time
        # (Implementation detail - would need to check specific logic)
        pass
    
    def test_workspace_isolation(self):
        """Test that workspace isolation works correctly."""
        # Test that credentials are stored per workspace
        workspace1_config = self.test_config.copy()
        workspace1_config['workspace'] = 'workspace1'
        
        workspace2_config = self.test_config.copy()  
        workspace2_config['workspace'] = 'workspace2'
        
        connector1 = GmailConnector(workspace1_config)
        connector2 = GmailConnector(workspace2_config)
        
        # Should have different credential paths
        self.assertNotEqual(
            connector1._get_credentials_path(),
            connector2._get_credentials_path()
        )


class TestGmailCLIIntegration(unittest.TestCase):
    """Test Gmail CLI command integration."""
    
    def test_cli_registration(self):
        """Test that Gmail commands are properly registered."""
        # Import to trigger registration
        from promaia.cli.gmail_commands import gmail_group
        
        # Check that command group exists and has expected commands
        self.assertIsNotNone(gmail_group)
        
        # Check for expected subcommands
        command_names = [cmd.name for cmd in gmail_group.commands.values()]
        expected_commands = ['setup', 'test', 'labels']
        
        for expected in expected_commands:
            self.assertIn(expected, command_names)


if __name__ == '__main__':
    unittest.main() 