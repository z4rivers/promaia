"""
Gmail connector implementation for Maia.

This module provides a Gmail API connector that integrates with the existing
Maia architecture for email synchronization and storage.
"""
import os
import json
import base64
import logging
import pickle
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List, Optional, Union
from pathlib import Path
from email.mime.text import MIMEText
import re

try:
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
except ImportError:
    print("Gmail integration requires google-auth, google-auth-oauthlib, and google-api-python-client")
    print("Install with: pip install google-auth google-auth-oauthlib google-api-python-client")
    raise

from .base import BaseConnector, QueryFilter, DateRangeFilter, SyncResult

logger = logging.getLogger(__name__)

class GmailConnector(BaseConnector):
    """Gmail API connector for email synchronization."""
    
    # Gmail API scopes
    SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        
        self.email = config.get("database_id")  # Use email as database_id
        self.workspace = config.get("workspace", "koii")
        
        # OAuth2 credential paths
        self.credentials_dir = os.path.join("credentials", self.workspace)
        self.credentials_file = os.path.join(self.credentials_dir, "gmail_credentials.json")
        self.token_file = os.path.join(self.credentials_dir, "gmail_token.json")
        
        # Ensure credentials directory exists
        os.makedirs(self.credentials_dir, exist_ok=True)
        
        self.service = None
        
    async def connect(self) -> bool:
        """Establish connection to Gmail API."""
        try:
            self.service = await self._get_authenticated_service()
            return self.service is not None
        except Exception as e:
            self.logger.error(f"Failed to connect to Gmail: {e}")
            return False
    
    async def test_connection(self) -> bool:
        """Test if the Gmail connection is working."""
        if not self.service:
            if not await self.connect():
                return False
        
        try:
            # Test with a simple profile request
            profile = self.service.users().getProfile(userId='me').execute()
            self.logger.info(f"Connected to Gmail for {profile.get('emailAddress')}")
            return True
        except Exception as e:
            self.logger.error(f"Gmail connection test failed: {e}")
            return False
    
    async def _get_authenticated_service(self):
        """Get authenticated Gmail service with token refresh."""
        creds = None
        
        # Load existing token
        if os.path.exists(self.token_file):
            with open(self.token_file, 'rb') as token:
                creds = pickle.load(token)
        
        # If there are no (valid) credentials available, run OAuth flow
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                    self.logger.info("Gmail token refreshed successfully")
                except Exception as e:
                    self.logger.warning(f"Token refresh failed: {e}, need to re-authenticate")
                    creds = None
            
            if not creds:
                # Check if we have client credentials
                if not os.path.exists(self.credentials_file):
                    raise ValueError(
                        f"Gmail OAuth2 credentials not found at {self.credentials_file}. "
                        f"Please run: maia workspace gmail-setup {self.workspace} {self.email}"
                    )
                
                # Run OAuth flow
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.credentials_file, self.SCOPES
                )
                creds = flow.run_local_server(port=0)
                self.logger.info("Gmail OAuth2 authentication completed")
            
            # Save the credentials for next run
            with open(self.token_file, 'wb') as token:
                pickle.dump(creds, token)
        
        return build('gmail', 'v1', credentials=creds)
    
    async def get_database_schema(self) -> Dict[str, Any]:
        """Get the schema/properties for Gmail emails."""
        return {
            "from": {"type": "email", "description": "Sender email address"},
            "to": {"type": "email", "description": "Recipient email addresses"},
            "subject": {"type": "text", "description": "Email subject"},
            "date": {"type": "date", "description": "Email date"},
            "labels": {"type": "multi_select", "description": "Gmail labels"},
            "thread_id": {"type": "text", "description": "Gmail thread ID"},
            "message_id": {"type": "text", "description": "Gmail message ID"},
            "has_attachments": {"type": "checkbox", "description": "Has attachments"},
            "is_unread": {"type": "checkbox", "description": "Is unread"},
            "body_snippet": {"type": "text", "description": "Email body preview"},
            "snippet": latest_message.get('snippet', ''),
            "messages": messages,  # Store full message data for detailed processing
            "body_html": self._get_latest_html_body(messages)
        }
    
    async def query_pages(self, 
                         filters: Optional[List[QueryFilter]] = None,
                         date_filter: Optional[DateRangeFilter] = None,
                         sort_by: Optional[str] = None,
                         sort_direction: str = "desc",
                         limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Query emails from Gmail."""
        if not self.service:
            await self.connect()
        
        try:
            # Build Gmail search query
            query = self._build_gmail_query(filters, date_filter)
            
            self.logger.info(f"Gmail query: {query}")
            
            # Search for messages with pagination
            messages = []
            page_token = None
            
            while True:
                try:
                    result = self.service.users().messages().list(
                        userId='me',
                        q=query,
                        maxResults=100, # Max allowed by API
                        pageToken=page_token
                    ).execute()
                    
                    messages.extend(result.get('messages', []))
                    page_token = result.get('nextPageToken')
                    
                    if not page_token or (limit and len(messages) >= limit):
                        break
                        
                except HttpError as e:
                    if e.resp.status == 500:
                        # Gmail backend error - try simplified query
                        self.logger.warning(f"Gmail API 500 error with query: {query}")
                        self.logger.info("Trying simplified query without category filters...")
                        
                        # Fallback to basic query
                        simple_query = self._build_simple_gmail_query(date_filter)
                        self.logger.info(f"Simplified Gmail query: {simple_query}")
                        
                        result = self.service.users().messages().list(
                            userId='me',
                            q=simple_query,
                            maxResults=100,
                            pageToken=page_token
                        ).execute()
                        
                        messages.extend(result.get('messages', []))
                        page_token = result.get('nextPageToken')
                        
                        if not page_token or (limit and len(messages) >= limit):
                            break
                    else:
                        raise
            
            if limit:
                messages = messages[:limit]

            self.logger.info(f"Found {len(messages)} total messages.")

            # Get detailed message info - group by thread to reduce API calls
            threads = {}
            for msg in messages:
                thread_id = msg.get('threadId')
                if thread_id not in threads:
                    threads[thread_id] = []
                threads[thread_id].append(msg['id'])
            
            # Process threads (this will group emails by conversation)
            email_data = []
            for thread_id, message_ids in threads.items():
                thread_data = await self._get_thread_data(thread_id, message_ids)
                if thread_data:
                    email_data.append(thread_data)
            
            return email_data
            
        except Exception as e:
            self.logger.error(f"Failed to query Gmail messages: {e}")
            return []
    
    async def _get_thread_data(self, thread_id: str, message_ids: List[str]) -> Optional[Dict[str, Any]]:
        """Get full thread data including all messages in the conversation."""
        try:
            # Get thread details
            thread = self.service.users().threads().get(
                userId='me', 
                id=thread_id,
                format='full'
            ).execute()
            
            messages = thread.get('messages', [])
            if not messages:
                return None
            
            # Sort messages by date (oldest first for conversation flow)
            messages.sort(key=lambda m: int(m.get('internalDate', 0)))
            
            # Use the latest message for thread metadata
            latest_message = messages[-1]
            
            # Extract thread-level metadata from latest message
            headers = {h['name'].lower(): h['value'] 
                      for h in latest_message.get('payload', {}).get('headers', [])}
            
            subject = headers.get('subject', 'No Subject')
            from_addr = headers.get('from', 'Unknown')
            to_addr = headers.get('to', '')
            date_str = headers.get('date', '')
            
            # Parse date
            try:
                # Gmail provides date in various formats, try to parse
                from email.utils import parsedate_to_datetime
                date_obj = parsedate_to_datetime(date_str)
                if date_obj.tzinfo is None:
                    date_obj = date_obj.replace(tzinfo=timezone.utc)
            except Exception:
                date_obj = datetime.now(timezone.utc)
            
            # Extract labels from latest message
            labels = latest_message.get('labelIds', [])
            
            # Check for attachments across all messages in thread
            has_attachments = any(
                self._message_has_attachments(msg) for msg in messages
            )
            
            # Check if thread has unread messages
            is_unread = 'UNREAD' in labels
            
            # Generate conversation body by combining all messages
            conversation_body = self._extract_thread_conversation(messages)
            
            return {
                "id": f"thread_{thread_id}",
                "thread_id": thread_id,
                "message_ids": [msg['id'] for msg in messages],
                "subject": subject,
                "from": from_addr,
                "to": to_addr,
                "date": date_obj.isoformat(),
                "date_obj": date_obj,
                "labels": labels,
                "has_attachments": has_attachments,
                "is_unread": is_unread,
                "message_count": len(messages),
                "conversation_body": conversation_body,
                "internal_date": latest_message.get('internalDate'),
                "snippet": latest_message.get('snippet', ''),
                "messages": messages,  # Store full message data for detailed processing
                "body_html": self._get_latest_html_body(messages)
            }
            
        except Exception as e:
            self.logger.error(f"Failed to get thread data for {thread_id}: {e}")
            return None
    
    def _get_latest_html_body(self, messages: List[Dict[str, Any]]) -> Optional[str]:
        """Extracts the HTML body from the latest message."""
        if not messages:
            return None
        
        try:
            latest_message = sorted(messages, key=lambda m: int(m.get('internalDate', 0)))[-1]
            return self._extract_html_from_payload(latest_message.get('payload', {}))
        except Exception:
            return None
    
    def _extract_thread_conversation(self, messages: List[Dict[str, Any]]) -> str:
        """Extract conversation text from the latest message in a thread.
        
        Gmail threads typically contain the full conversation history in the latest message,
        so we only need to extract the content from the most recent message to avoid duplication.
        """
        if not messages:
            return ""
        
        # Sort messages by date to ensure we get the latest one
        sorted_messages = sorted(messages, key=lambda m: int(m.get('internalDate', 0)))
        latest_message = sorted_messages[-1]
        
        # Extract headers from the latest message
        headers = {h['name'].lower(): h['value'] 
                  for h in latest_message.get('payload', {}).get('headers', [])}
        
        from_addr = headers.get('from', 'Unknown')
        date_str = headers.get('date', '')
        
        # Extract the complete conversation body from the latest message
        body = self._extract_message_body(latest_message)
        
        # If the latest message is empty, try to build from individual messages
        if not body.strip():
            self.logger.debug(f"Latest message empty, building from {len(messages)} individual messages")
            return self._extract_individual_messages(sorted_messages)
        
        # Return the latest message content which should contain the full conversation
        return f"""
From: {from_addr}
Date: {date_str}

{body}
"""
    
    def _extract_individual_messages(self, messages: List[Dict[str, Any]]) -> str:
        """Fallback method to extract individual messages when latest message is empty."""
        conversation_parts = []
        
        for i, message in enumerate(messages):
            headers = {h['name'].lower(): h['value'] 
                      for h in message.get('payload', {}).get('headers', [])}
            
            from_addr = headers.get('from', 'Unknown')
            date_str = headers.get('date', '')
            
            # Use body for individual messages now for better context
            body = self._extract_message_body(message)
            
            conversation_parts.append(f"""
---
**Message {i+1}** | From: {from_addr} | Date: {date_str}

{body if body.strip() else message.get('snippet', '')}
""")
        
        return "\n".join(conversation_parts).strip()
    
    def _extract_message_body(self, message: Dict[str, Any]) -> str:
        """Extract readable text from a Gmail message."""
        payload = message.get('payload', {})
        
        # Recursively extract text from message parts
        text_content = self._extract_text_from_payload(payload)
        
        return text_content.strip()
    
    def _extract_text_from_payload(self, payload: Dict[str, Any]) -> str:
        """Recursively extract text content from a message payload."""
        mime_type = payload.get('mimeType', '')
        
        # Handle multipart content first (recursively)
        if mime_type.startswith('multipart/'):
            parts = payload.get('parts', [])
            
            # Prefer text/html over text/plain in multipart
            html_part = None
            text_part = None

            for part in parts:
                part_mime_type = part.get('mimeType', '')
                if part_mime_type == 'text/html':
                    html_part = part
                elif part_mime_type == 'text/plain':
                    text_part = part
                
                # Handle nested multipart (e.g., multipart/alternative inside multipart/mixed)
                if part_mime_type.startswith('multipart/'):
                    nested_content = self._extract_text_from_payload(part)
                    if nested_content:
                        return nested_content

            if html_part:
                return self._extract_text_from_payload(html_part)
            if text_part:
                return self._extract_text_from_payload(text_part)

            return "" # No usable text/html or text/plain part found

        # Handle direct text content
        if mime_type == 'text/plain':
            data = payload.get('body', {}).get('data', '')
            if data:
                try:
                    return base64.urlsafe_b64decode(data).decode('utf-8', errors='ignore')
                except Exception as e:
                    self.logger.warning(f"Failed to decode text/plain data: {e}")
                    return ''
        
        elif mime_type == 'text/html':
            data = payload.get('body', {}).get('data', '')
            if data:
                try:
                    html_content = base64.urlsafe_b64decode(data).decode('utf-8', errors='ignore')
                    # Simple HTML to text conversion
                    import html
                    text = re.sub('<style.*?</style>', '', html_content, flags=re.DOTALL)
                    text = re.sub('<script.*?</script>', '', text, flags=re.DOTALL)
                    text = re.sub('<[^<]+?>', ' ', text)
                    text = re.sub(r'\s+', ' ', text)
                    return html.unescape(text).strip()
                except Exception as e:
                    self.logger.warning(f"Failed to decode text/html data: {e}")
                    return ''
        
        # For other MIME types (attachments, etc.), return empty string
        return ''
    
    def _extract_html_from_payload(self, payload: Dict[str, Any]) -> Optional[str]:
        """Recursively extracts the first available HTML content from a message payload."""
        mime_type = payload.get('mimeType', '')

        if mime_type == 'text/html':
            data = payload.get('body', {}).get('data', '')
            if data:
                try:
                    return base64.urlsafe_b64decode(data).decode('utf-8', errors='ignore')
                except Exception as e:
                    self.logger.warning(f"Failed to decode text/html data for body: {e}")
                    return None
        
        if mime_type.startswith('multipart/'):
            parts = payload.get('parts', [])
            for part in parts:
                html_content = self._extract_html_from_payload(part)
                if html_content:
                    return html_content
        
        return None
    
    def _message_has_attachments(self, message: Dict[str, Any]) -> bool:
        """Check if a message has attachments."""
        payload = message.get('payload', {})
        
        # Check parts for attachments
        if 'parts' in payload:
            for part in payload['parts']:
                if part.get('filename'):
                    return True
                # Recursive check for nested parts (e.g. multipart/mixed)
                if 'parts' in part:
                    if self._message_has_attachments(part):
                        return True
        return False
    
    def _build_gmail_query(self, 
                          filters: Optional[List[QueryFilter]] = None,
                          date_filter: Optional[DateRangeFilter] = None) -> str:
        """Build Gmail search query from filters."""
        query_parts = []
        
        # Add property filters
        if filters:
            for filter_obj in filters:
                gmail_query = self._query_filter_to_gmail(filter_obj)
                if gmail_query:
                    query_parts.append(gmail_query)
        
        # Add date filter
        if date_filter:
            date_query = self._date_filter_to_gmail(date_filter)
            if date_query:
                query_parts.append(date_query)
        
        # Default filters - allow overriding from config
        # Simplified query to avoid Gmail API 500 errors
        query_parts.append('in:inbox')
        
        # Add category exclusions only if explicitly configured 
        excluded_categories = self.config.get('gmail_query_exclude_categories', ['promotions', 'social', 'forums'])
        for category in excluded_categories:
            query_parts.append(f'-category:{category}')
        
        # Basic exclusions that are generally safe
        query_parts.append('-in:spam')
        query_parts.append('-in:trash')
        
        # Get label filters from config
        label_filters = self.config.get('property_filters', {}).get('label')
        if label_filters:
            if isinstance(label_filters, list):
                for label in label_filters:
                    query_parts.append(f'label:{label}')
            else:
                query_parts.append(f'label:{label_filters}')
        
        return ' '.join(query_parts)
    
    def _build_simple_gmail_query(self, date_filter: Optional[DateRangeFilter] = None) -> str:
        """Build a simplified Gmail search query for fallback when complex queries fail."""
        query_parts = []
        
        # Add date filter
        if date_filter:
            date_query = self._date_filter_to_gmail(date_filter)
            if date_query:
                query_parts.append(date_query)
        
        # Only basic filters to avoid API errors
        query_parts.append('in:inbox')
        query_parts.append('-in:spam')
        query_parts.append('-in:trash')
        
        return ' '.join(query_parts)
    
    def _query_filter_to_gmail(self, query_filter: QueryFilter) -> Optional[str]:
        """Convert QueryFilter to Gmail search syntax."""
        prop_name = query_filter.property_name.lower()
        operator = query_filter.operator
        value = query_filter.value
        
        if prop_name == 'from' and operator == 'eq':
            return f'from:{value}'
        elif prop_name == 'to' and operator == 'eq':
            return f'to:{value}'
        elif prop_name == 'subject' and operator == 'contains':
            return f'subject:{value}'
        elif prop_name == 'label' and operator == 'eq':
            return f'label:{value}'
        elif prop_name == 'is_unread' and operator == 'eq':
            return 'is:unread' if value else 'is:read'
        elif prop_name == 'has_attachments' and operator == 'eq':
            return 'has:attachment' if value else '-has:attachment'
        
        return None
    
    def _date_filter_to_gmail(self, date_filter: DateRangeFilter) -> Optional[str]:
        """Convert DateRangeFilter to Gmail search syntax.
        
        Gmail's after:/before: syntax interprets dates in the account's local timezone,
        so we need to convert UTC dates to local timezone before formatting.
        
        For incremental syncs (start_date only), we use newer_than: which finds threads
        with any activity in the specified timeframe, not just threads that started then.
        """
        from promaia.utils.timezone_utils import to_local
        
        query_parts = []
        
        # Check if this looks like an incremental sync (start_date only, no end_date)
        is_incremental_sync = date_filter.start_date and not date_filter.end_date
        
        if date_filter.start_date:
            # Convert UTC date to local timezone before formatting for Gmail
            local_date = to_local(date_filter.start_date)
            
            if is_incremental_sync:
                # For incremental syncs, use newer_than which finds threads with ANY activity
                # in the last N days, including threads that started earlier but had new messages
                days_since = (datetime.now().date() - local_date.date()).days
                if days_since <= 0:
                    days_since = 1  # Gmail requires at least 1 day
                
                # Use newer_than for better thread activity detection
                query_parts.append(f'newer_than:{days_since}d')
                
                # Also add a more inclusive after: search to catch edge cases
                # Go back a bit further to ensure we don't miss any threads
                buffer_date = local_date - timedelta(days=2)
                date_str = buffer_date.strftime('%Y/%m/%d')
                query_parts.append(f'after:{date_str}')
                
                self.logger.debug(f"Incremental Gmail sync: using newer_than:{days_since}d and after:{date_str}")
            else:
                # For date range syncs, use standard after: syntax
                date_str = local_date.strftime('%Y/%m/%d')
                query_parts.append(f'after:{date_str}')
                self.logger.debug(f"Gmail date range sync: using after:{date_str}")
        
        if date_filter.end_date:
            # Convert UTC date to local timezone before formatting for Gmail
            local_date = to_local(date_filter.end_date)
            date_str = local_date.strftime('%Y/%m/%d')
            query_parts.append(f'before:{date_str}')
            self.logger.debug(f"Gmail date range sync: using before:{date_str}")
        
        return ' '.join(query_parts) if query_parts else None
    
    async def get_page_content(self, page_id: str, include_properties: bool = True) -> Dict[str, Any]:
        """Get full content of a specific email thread."""
        # page_id format: "thread_{thread_id}"
        thread_id = page_id.replace('thread_', '')
        
        try:
            thread_data = await self._get_thread_data(thread_id, [])
            return thread_data or {}
        except Exception as e:
            self.logger.error(f"Failed to get email thread content for {page_id}: {e}")
            return {}
    
    async def get_page_properties(self, page_id: str) -> Dict[str, Any]:
        """Get properties of a specific email thread."""
        content = await self.get_page_content(page_id, include_properties=True)
        
        return {
            "from": content.get("from"),
            "to": content.get("to"), 
            "subject": content.get("subject"),
            "date": content.get("date"),
            "labels": content.get("labels", []),
            "thread_id": content.get("thread_id"),
            "has_attachments": content.get("has_attachments", False),
            "is_unread": content.get("is_unread", False),
            "message_count": content.get("message_count", 1)
        }
    
    async def sync_to_local(self, 
                           output_directory: str,
                           filters: Optional[List[QueryFilter]] = None,
                           date_filter: Optional[DateRangeFilter] = None,
                           include_properties: bool = True,
                           force_update: bool = False,
                           excluded_properties: List[str] = None) -> SyncResult:
        """Sync Gmail threads to local storage - placeholder for backwards compatibility."""
        # This will be implemented in sync_to_local_unified
        raise NotImplementedError("Use sync_to_local_unified for Gmail connector")
    
    async def sync_to_local_unified(self, 
                                   storage,
                                   db_config,
                                   filters: Optional[List[QueryFilter]] = None,
                                   date_filter: Optional[DateRangeFilter] = None,
                                   include_properties: bool = True,
                                   force_update: bool = False,
                                   excluded_properties: List[str] = None) -> SyncResult:
        """Sync Gmail threads to local storage using unified storage system."""
        result = SyncResult()
        result.start_time = datetime.now()
        
        try:
            limit = self.config.get("sync_limit", 100)
            
            # Query Gmail for recent threads
            self.logger.info(f"Querying Gmail with date_filter: {date_filter}")
            email_threads = await self.query_pages(
                filters=filters, 
                date_filter=date_filter,
                limit=limit
            )
            
            if not email_threads:
                self.logger.info("No new email threads found from Gmail query.")
                print("📭 No email threads found to process")
                return result
            
            self.logger.info(f"Found {len(email_threads)} email threads from Gmail query.")
            
            pages_to_save = []
            for thread in email_threads:
                # Prepare page data for unified storage
                page_data = self._prepare_page_for_storage(thread, db_config, excluded_properties)
                pages_to_save.append(page_data)
            
            if not pages_to_save:
                self.logger.info("No new or updated threads to save after filtering.")
                print("📭 No email threads found to process")
                return result
            
            # Save pages to storage one by one
            saved_count = 0
            print(f"📧 Processing {len(pages_to_save)} email threads...")
            
            try:
                for page in pages_to_save:
                    try:
                        # Note: storage.save_content is a synchronous method
                        storage.save_content(
                            page_id=page['page_id'],
                            title=page['metadata']['title'],
                            content_data=page['metadata'],
                            database_config=db_config,
                            markdown_content=page['content']
                        )
                        saved_count += 1
                    except Exception as page_error:
                        self.logger.error(f"Failed to save page {page['page_id']}: {page_error}")
                        result.errors.append(f"Failed to save {page['page_id']}: {str(page_error)}")
                
                # Update sync result counters
                result.new_pages = saved_count  # We can't easily distinguish new vs updated without more complex logic
                result.updated_pages = 0
                result.success = saved_count > 0
                
                self.logger.info(f"Sync completed. {saved_count} email threads saved")
                if saved_count > 0:
                    print(f"✨ {saved_count} email threads saved")
                else:
                    print("📭 No email threads were saved")

            except Exception as e:
                self.logger.error(f"Failed during unified sync save: {e}")
                result.errors.append(f"Failed during unified sync save: {str(e)}")

            result.end_time = datetime.now()
            return result
            
        except Exception as e:
            result.end_time = datetime.now()
            result.errors.append(f"Gmail sync failed: {str(e)}")
            self.logger.error(f"Gmail sync failed: {e}")
            return result
    
    def _prepare_page_for_storage(self, thread: Dict[str, Any], db_config, excluded_properties: List[str] = None) -> Dict[str, Any]:
        """Prepare thread data for the unified storage format."""
        
        page_id = thread['id']
        markdown_content = self._thread_to_markdown(thread)
        
        # Extract properties from thread data
        properties = {
            "title": thread.get('subject', 'No Subject'),
            "from": thread.get('from', 'Unknown'),
            "to": thread.get('to', ''),
            "date": thread.get('date'),
            "labels": thread.get('labels', []),
            "has_attachments": thread.get('has_attachments', False),
            "is_unread": thread.get('is_unread', False),
            "snippet": thread.get('snippet', ''),
            "message_count": thread.get('message_count', 0)
        }
        
        # Metadata for registry
        metadata = {
            "page_id": page_id,
            "title": thread.get('subject', 'No Subject'),
            "created_time": thread.get('date'),
            "last_edited_time": thread.get('date'),
            "synced_time": datetime.now(timezone.utc).isoformat(),
            "source_id": thread.get('thread_id'),
            "data_source": "gmail",
            "content_type": "email_thread",
            "properties": properties,
            "html_available": thread.get('body_html') is not None
        }
        
        return {
            "page_id": page_id,
            "content": markdown_content,
            "html_content": thread.get('body_html'),
            "metadata": metadata
        }

    def _thread_to_markdown(self, thread: Dict[str, Any]) -> str:
        """Convert a Gmail thread dictionary to a markdown string."""
        subject = thread.get("subject", "No Subject")
        from_addr = thread.get("from", "Unknown")
        to_addr = thread.get("to", "")
        date_str = thread.get("date", "")
        labels = thread.get("labels", [])
        message_count = thread.get("message_count", 1)
        has_attachments = thread.get("has_attachments", False)
        
        # Note: Date prefix for filename is now handled by unified storage using the 'date' field
        # No need to manually add it here to avoid double prefixing
        
        # Create header
        header = f"""# Email Thread: {subject}

**From:** {from_addr}  
**To:** {to_addr}  
**Date:** {date_str}  
**Messages:** {message_count}  
**Labels:** {', '.join(labels)}  
**Has Attachments:** {'Yes' if has_attachments else 'No'}  

---

"""
        
        # Add conversation body
        conversation = thread.get("conversation_body", "")
        
        # Add attachment note if applicable
        attachment_note = ""
        if has_attachments:
            attachment_note = "\n\n---\n**Note:** This email thread contains attachments. Attachment details are stored in the JSON data but files are not downloaded.\n"
        
        return header + conversation + attachment_note 