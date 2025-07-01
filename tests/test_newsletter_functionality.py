"""
Test suite for newsletter functionality.

Tests the complete newsletter workflow:
- Status filtering (only "To push" newsletters)
- Content conversion from Notion to plain text
- Email formatting and template generation
- Resend API integration
- Status updates after sending
"""
import pytest
import asyncio
import os
from unittest.mock import Mock, patch, AsyncMock
from typing import Dict, Any, List

# Import the modules we're testing
from promaia.newsletter.commands import (
    get_eligible_newsletter_pages,
    send_newsletter_via_resend,
    update_page_newsletter_status,
    update_page_last_synced,
    newsletter_sync_command,
    get_property_value,
    get_page_display_title
)
from promaia.newsletter.template import (
    create_plain_text_newsletter,
    notion_blocks_to_plain_text
)
from promaia.newsletter.resend_client import ResendClient


class TestNewsletterStatusFiltering:
    """Test that newsletter system only processes pages with 'To push' status."""
    
    @pytest.fixture
    def mock_notion_pages(self):
        """Mock Notion pages with different newsletter statuses."""
        return [
            {
                "id": "page-1",
                "properties": {
                    "Name": {"type": "title", "title": [{"text": {"content": "Newsletter 1"}}]},
                    "Newsletter Status": {"type": "status", "status": {"name": "To push"}}
                }
            },
            {
                "id": "page-2", 
                "properties": {
                    "Name": {"type": "title", "title": [{"text": {"content": "Newsletter 2"}}]},
                    "Newsletter Status": {"type": "status", "status": {"name": "Sent"}}
                }
            },
            {
                "id": "page-3",
                "properties": {
                    "Name": {"type": "title", "title": [{"text": {"content": "Newsletter 3"}}]},
                    "Newsletter Status": {"type": "status", "status": {"name": "Don't push"}}
                }
            },
            {
                "id": "page-4",
                "properties": {
                    "Name": {"type": "title", "title": [{"text": {"content": "Newsletter 4"}}]},
                    "Newsletter Status": {"type": "status", "status": {"name": "To push"}}
                }
            }
        ]
    
    @pytest.mark.asyncio
    @patch('promaia.newsletter.commands.query_pages_by_status')
    async def test_only_to_push_pages_returned(self, mock_query, mock_notion_pages):
        """Test that get_eligible_newsletter_pages only returns 'To push' pages."""
        # Mock the query to return only "To push" pages
        to_push_pages = [p for p in mock_notion_pages if 
                        get_property_value(p, "Newsletter Status") == "To push"]
        mock_query.return_value = to_push_pages
        
        # Get eligible pages
        eligible_pages = await get_eligible_newsletter_pages("test-db-id")
        
        # Verify only "To push" pages are returned
        assert len(eligible_pages) == 2
        for page in eligible_pages:
            assert get_property_value(page, "Newsletter Status") == "To push"
        
        # Verify the query was called with correct status
        mock_query.assert_called_once_with("test-db-id", "To push")
    
    @pytest.mark.asyncio
    async def test_empty_result_when_no_to_push_pages(self):
        """Test that empty list is returned when no pages have 'To push' status."""
        with patch('promaia.newsletter.commands.query_pages_by_status') as mock_query:
            mock_query.return_value = []
            
            eligible_pages = await get_eligible_newsletter_pages("test-db-id")
            
            assert eligible_pages == []
            mock_query.assert_called_once_with("test-db-id", "To push")


class TestNewsletterContentConversion:
    """Test content conversion from Notion blocks to plain text."""
    
    @pytest.fixture
    def sample_notion_blocks(self):
        """Sample Notion blocks for testing."""
        return [
            {
                "type": "heading_1",
                "heading_1": {
                    "rich_text": [{"plain_text": "Main Title"}]
                }
            },
            {
                "type": "paragraph", 
                "paragraph": {
                    "rich_text": [{"plain_text": "This is a paragraph with some content."}]
                }
            },
            {
                "type": "heading_2",
                "heading_2": {
                    "rich_text": [{"plain_text": "Subtitle"}]
                }
            },
            {
                "type": "bulleted_list_item",
                "bulleted_list_item": {
                    "rich_text": [{"plain_text": "First bullet point"}]
                }
            },
            {
                "type": "bulleted_list_item", 
                "bulleted_list_item": {
                    "rich_text": [{"plain_text": "Second bullet point"}]
                }
            }
        ]
    
    def test_notion_blocks_to_plain_text_conversion(self, sample_notion_blocks):
        """Test conversion of Notion blocks to plain text."""
        result = notion_blocks_to_plain_text(sample_notion_blocks)
        
        # Check that headings are properly formatted
        assert "Main Title" in result
        assert "=" * len("Main Title") in result  # H1 underline
        assert "Subtitle" in result
        assert "-" * len("Subtitle") in result   # H2 underline
        
        # Check paragraph content
        assert "This is a paragraph with some content." in result
        
        # Check bullet points
        assert "• First bullet point" in result
        assert "• Second bullet point" in result
    
    def test_empty_blocks_handling(self):
        """Test handling of empty or None blocks."""
        assert notion_blocks_to_plain_text([]) == ""
        assert notion_blocks_to_plain_text(None) == ""
    
    def test_create_plain_text_newsletter_format(self):
        """Test the complete newsletter formatting."""
        content = "This is test content.\n\nWith multiple paragraphs."
        newsletter = create_plain_text_newsletter(
            content_text=content,
            newsletter_title="Test Newsletter",
            post_link="https://example.com/post"
        )
        
        # Check that title is NOT included (since it's in subject)
        assert "Test Newsletter" not in newsletter
        
        # Check content is included
        assert content in newsletter
        
        # Check footer formatting
        assert "📖 Read the full post: https://example.com/post" in newsletter
        assert "💌 Forwarded this email? Subscribe: https://www.koiibenvenutto.com/" in newsletter
        assert "Thanks for reading!" in newsletter
        assert "- Koii Benvenutto" in newsletter


class TestResendClientIntegration:
    """Test Resend email client functionality."""
    
    def test_successful_email_sending(self):
        """Test successful email sending via Resend."""
        with patch.dict(os.environ, {
            'RESEND_API_KEY': 'test-api-key',
            'RESEND_FROM_EMAIL': 'test@example.com',
            'RESEND_FROM_NAME': 'Test Sender',
            'RESEND_TEST_EMAIL': 'test-recipient@example.com'
        }):
            client = ResendClient()
            
            with patch('resend.Emails.send') as mock_send:
                # Mock successful response
                mock_send.return_value = {"id": "test-email-id-123"}
                
                result = client.send_newsletter(
                    subject="Test Newsletter",
                    plain_text="Test content"
                )
                
                assert result["success"] is True
                assert result["email_id"] == "test-email-id-123"
                
                # Verify the send call
                mock_send.assert_called_once()
                call_args = mock_send.call_args[0][0]
                assert call_args["subject"] == "Test Newsletter"
                assert call_args["text"] == "Test content"
                assert call_args["from"] == "Test Sender <test@example.com>"
    
    def test_email_sending_failure(self):
        """Test handling of email sending failures."""
        with patch.dict(os.environ, {
            'RESEND_API_KEY': 'test-api-key',
            'RESEND_FROM_EMAIL': 'test@example.com',
            'RESEND_FROM_NAME': 'Test Sender',
            'RESEND_TEST_EMAIL': 'test-recipient@example.com'
        }):
            client = ResendClient()
            
            with patch('resend.Emails.send') as mock_send:
                # Mock API failure
                mock_send.side_effect = Exception("API Error")
                
                result = client.send_newsletter(
                    subject="Test Newsletter",
                    plain_text="Test content"
                )
                
                assert result["success"] is False
                assert "API Error" in result["error"]
    
    def test_html_link_conversion(self):
        """Test that plain text URLs are converted to clickable HTML links."""
        with patch.dict(os.environ, {
            'RESEND_API_KEY': 'test-api-key',
            'RESEND_FROM_EMAIL': 'test@example.com',
            'RESEND_FROM_NAME': 'Test Sender',
            'RESEND_TEST_EMAIL': 'test-recipient@example.com'
        }):
            client = ResendClient()
            
            plain_text = """
            Test content here.
            
            📖 Read the full post: https://example.com/post
            
            💌 Forwarded this email? Subscribe: https://www.koiibenvenutto.com/
            """
            
            html = client._plain_text_to_html(plain_text)
            
            # Check that URLs are converted to clickable links
            assert '<a href="https://example.com/post"' in html
            assert '<a href="https://www.koiibenvenutto.com/"' in html
            assert 'Read the full post</a>' in html
            assert 'Subscribe here</a>' in html


class TestNewsletterWorkflow:
    """Test the complete newsletter sending workflow."""
    
    @pytest.fixture
    def mock_page(self):
        """Mock Notion page for testing."""
        return {
            "id": "test-page-id",
            "properties": {
                "Name": {
                    "type": "title",
                    "title": [{"text": {"content": "Test Newsletter"}}]
                },
                "Newsletter Status": {
                    "type": "status", 
                    "status": {"name": "To push"}
                }
            }
        }
    
    @pytest.mark.asyncio
    @patch('promaia.newsletter.commands.notion_to_plain_text')
    @patch('promaia.newsletter.commands.get_resend_client')
    @patch('promaia.newsletter.commands.check_webflow_published')
    async def test_successful_newsletter_sending(self, mock_webflow, mock_get_client, mock_notion_text, mock_page):
        """Test successful newsletter sending workflow."""
        # Mock dependencies
        mock_notion_text.return_value = "Test newsletter content"
        mock_webflow.return_value = (False, None, "test-slug")
        
        mock_client = Mock()
        mock_client.send_newsletter.return_value = {
            "success": True,
            "email_id": "test-email-id"
        }
        mock_get_client.return_value = mock_client
        
        # Test the workflow
        success, message, email_id = await send_newsletter_via_resend(mock_page)
        
        assert success is True
        assert "test-email-id" in message
        assert email_id == "test-email-id"
        
        # Verify client was called correctly
        mock_client.send_newsletter.assert_called_once()
        call_args = mock_client.send_newsletter.call_args
        assert call_args[1]["subject"] == "Test Newsletter"
    
    @pytest.mark.asyncio
    @patch('promaia.newsletter.commands.notion_to_plain_text')
    async def test_newsletter_sending_failure(self, mock_notion_text, mock_page):
        """Test handling of newsletter sending failures."""
        # Mock content conversion failure
        mock_notion_text.side_effect = Exception("Content conversion failed")
        
        success, message, email_id = await send_newsletter_via_resend(mock_page)
        
        assert success is False
        assert "Content conversion failed" in message
        assert email_id is None


class TestPropertyUtilities:
    """Test utility functions for extracting page properties."""
    
    def test_get_property_value_title(self):
        """Test extracting title property."""
        page = {
            "properties": {
                "Name": {
                    "type": "title",
                    "title": [{"text": {"content": "Test Title"}}]
                }
            }
        }
        
        assert get_property_value(page, "Name") == "Test Title"
    
    def test_get_property_value_status(self):
        """Test extracting status property."""
        page = {
            "properties": {
                "Newsletter Status": {
                    "type": "status",
                    "status": {"name": "To push"}
                }
            }
        }
        
        assert get_property_value(page, "Newsletter Status") == "To push"
    
    def test_get_property_value_missing(self):
        """Test handling of missing properties."""
        page = {"properties": {}}
        
        assert get_property_value(page, "NonExistent") is None
    
    def test_get_page_display_title(self):
        """Test getting display title from page."""
        page = {
            "id": "test-id",
            "properties": {
                "Name": {
                    "type": "title", 
                    "title": [{"text": {"content": "Display Title"}}]
                }
            }
        }
        
        assert get_page_display_title(page) == "Display Title"


class TestStatusUpdates:
    """Test status update functionality."""
    
    @pytest.mark.asyncio
    @patch('promaia.newsletter.commands.ensure_default_client')
    async def test_update_newsletter_status(self, mock_client):
        """Test updating newsletter status."""
        mock_notion_client = AsyncMock()
        mock_client.return_value = mock_notion_client
        
        await update_page_newsletter_status("test-page-id", "Sent")
        
        mock_notion_client.pages.update.assert_called_once_with(
            page_id="test-page-id",
            properties={
                "Newsletter Status": {
                    "status": {"name": "Sent"}
                }
            }
        )
    
    @pytest.mark.asyncio
    @patch('promaia.newsletter.commands.ensure_default_client')
    async def test_update_last_synced(self, mock_client):
        """Test updating last synced timestamp."""
        mock_notion_client = AsyncMock()
        mock_client.return_value = mock_notion_client
        
        await update_page_last_synced("test-page-id")
        
        mock_notion_client.pages.update.assert_called_once()
        call_args = mock_notion_client.pages.update.call_args
        
        # Verify the structure of the call
        assert call_args[1]["page_id"] == "test-page-id"
        assert "Newsletter Last Synced" in call_args[1]["properties"]


class TestNewsletterIntegration:
    """Integration tests for newsletter functionality (requires API access)."""
    
    @pytest.mark.asyncio
    async def test_newsletter_command_with_no_eligible_pages(self):
        """Test newsletter command when no pages are eligible."""
        with patch('promaia.newsletter.commands.get_eligible_newsletter_pages') as mock_get_pages:
            mock_get_pages.return_value = []
            
            # Mock args object
            args = Mock()
            
            # Capture print output
            with patch('builtins.print') as mock_print:
                await newsletter_sync_command(args)
                
                # Verify appropriate message is printed
                print_calls = [call[0][0] for call in mock_print.call_args_list]
                assert any("No CMS pages eligible" in call for call in print_calls)
                assert any("Make sure pages have Newsletter Status set to 'To push'" in call for call in print_calls)


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"]) 