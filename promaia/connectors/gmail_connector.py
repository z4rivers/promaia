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
import asyncio
import time
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
    """Gmail API connector for email synchronization.
    
    Enhanced Features:
    - Intelligent date range chunking for large syncs
    - Batch processing with rate limit protection  
    - Exponential backoff retry logic for reliability
    - Removes artificial sync limits (was capped at 100 emails)
    - Complete email coverage for specified date ranges
    
    Configuration Options:
    - max_threads_per_batch (default: 25): Number of threads to process per batch
    - chunk_size_days (default: 15): Days per chunk for large date ranges
    - max_retry_attempts (default: 5): Maximum retry attempts for failed requests
    
    Usage Examples:
    # Sync all emails from March 1st to June 30th, 2025:
    maia database sync --source trass.gmail --start-date 2025-03-01 --end-date 2025-06-30
    
    # Sync last 30 days (no artificial limits):
    maia database sync --source trass.gmail --days 30
    
    # For very large date ranges, the system automatically:
    # 1. Breaks the range into 15-day chunks (configurable)
    # 2. Processes threads in batches of 25 (configurable)  
    # 3. Handles rate limits with exponential backoff
    # 4. Provides progress reporting
    """
    
    # Gmail API scopes
    SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']
    
    # Rate limiting and batching configuration
    MAX_THREADS_PER_BATCH = 25  # Conservative to avoid concurrent request limits
    MAX_RETRY_ATTEMPTS = 5
    BASE_RETRY_DELAY = 1.0  # seconds
    MAX_RETRY_DELAY = 32.0  # seconds
    RATE_LIMIT_RETRY_DELAY = 2.0  # seconds for 429 errors
    CHUNK_SIZE_DAYS = 15  # Break large date ranges into smaller chunks
    
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
        
        # Override default batching configuration from config if provided
        self.max_threads_per_batch = config.get("max_threads_per_batch", self.MAX_THREADS_PER_BATCH)
        self.chunk_size_days = config.get("chunk_size_days", self.CHUNK_SIZE_DAYS)
        self.max_retry_attempts = config.get("max_retry_attempts", self.MAX_RETRY_ATTEMPTS)
        
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
    
    async def _retry_with_backoff(self, func, *args, **kwargs):
        """Execute a function with exponential backoff retry logic for rate limits."""
        for attempt in range(self.max_retry_attempts):
            try:
                return func(*args, **kwargs)
            except HttpError as e:
                if e.resp.status == 429:  # Rate limit exceeded
                    if attempt < self.max_retry_attempts - 1:
                        delay = min(self.RATE_LIMIT_RETRY_DELAY * (2 ** attempt), self.MAX_RETRY_DELAY)
                        self.logger.warning(f"Rate limit hit, retrying in {delay:.1f}s (attempt {attempt + 1}/{self.max_retry_attempts})")
                        await asyncio.sleep(delay)
                        continue
                    else:
                        self.logger.error(f"Rate limit exceeded, max retries reached")
                        raise
                elif e.resp.status >= 500:  # Server errors
                    if attempt < self.max_retry_attempts - 1:
                        delay = min(self.BASE_RETRY_DELAY * (2 ** attempt), self.MAX_RETRY_DELAY)
                        self.logger.warning(f"Server error {e.resp.status}, retrying in {delay:.1f}s (attempt {attempt + 1}/{self.max_retry_attempts})")
                        await asyncio.sleep(delay)
                        continue
                    else:
                        self.logger.error(f"Server error {e.resp.status}, max retries reached")
                        raise
                else:
                    # Other HTTP errors, don't retry
                    raise
            except Exception as e:
                # Non-HTTP errors, don't retry
                raise
        
        # Should never reach here, but just in case
        raise Exception("Unexpected retry loop exit")
    
    async def _get_thread_data_batch(self, thread_ids: List[str]) -> List[Optional[Dict[str, Any]]]:
        """Get thread data in batches with rate limiting."""
        results = []
        
        for thread_id in thread_ids:
            try:
                thread_data = await self._retry_with_backoff(
                    lambda: self.service.users().threads().get(
                        userId='me', 
                        id=thread_id,
                        format='full'
                    ).execute()
                )
                
                if thread_data:
                    processed_data = self._process_thread_data(thread_data)
                    if processed_data:
                        results.append(processed_data)
                
                # Small delay between individual thread requests to be respectful
                await asyncio.sleep(0.1)
                
            except Exception as e:
                self.logger.error(f"Failed to get thread data for {thread_id}: {e}")
                results.append(None)
        
        return [r for r in results if r is not None]
    
    def _process_thread_data(self, thread: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Process raw thread data from Gmail API into standardized format."""
        try:
            messages = thread.get('messages', [])
            if not messages:
                return None
            
            thread_id = thread.get('id')
            
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
            self.logger.error(f"Failed to process thread data: {e}")
            return None
    
    def _chunk_date_range(self, date_filter: DateRangeFilter) -> List[DateRangeFilter]:
        """Break large date ranges into smaller chunks to avoid API timeouts."""
        if not date_filter or not date_filter.start_date:
            return [date_filter] if date_filter else []
        
        chunks = []
        current_start = date_filter.start_date
        end_date = date_filter.end_date or datetime.now(timezone.utc)
        
        while current_start < end_date:
            chunk_end = min(current_start + timedelta(days=self.chunk_size_days), end_date)
            
            chunk_filter = DateRangeFilter(
                property_name=date_filter.property_name,
                start_date=current_start,
                end_date=chunk_end
            )
            chunks.append(chunk_filter)
            
            current_start = chunk_end
        
        return chunks
    
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
        """Query emails from Gmail with intelligent chunking and batching."""
        if not self.service:
            await self.connect()
        
        try:
            all_email_data = []
            
            # Break large date ranges into smaller chunks
            date_chunks = self._chunk_date_range(date_filter) if date_filter else [None]
            
            total_chunks = len(date_chunks)
            if total_chunks > 1:
                self.logger.info(f"Breaking sync into {total_chunks} date chunks for better reliability")
            
            for chunk_idx, chunk_filter in enumerate(date_chunks):
                if total_chunks > 1:
                    if chunk_filter and chunk_filter.start_date and chunk_filter.end_date:
                        start_str = chunk_filter.start_date.strftime('%Y-%m-%d')
                        end_str = chunk_filter.end_date.strftime('%Y-%m-%d')
                        self.logger.info(f"Processing chunk {chunk_idx + 1}/{total_chunks}: {start_str} to {end_str}")
                
                # Build Gmail search query for this chunk
                query = self._build_gmail_query(filters, chunk_filter)
                self.logger.info(f"Gmail query: {query}")
                
                # Search for messages with pagination and retry logic
                messages = []
                page_token = None
                
                while True:
                    try:
                        result = await self._retry_with_backoff(
                            lambda: self.service.users().messages().list(
                                userId='me',
                                q=query,
                                maxResults=100,  # Max allowed by API
                                pageToken=page_token
                            ).execute()
                        )
                        
                        batch_messages = result.get('messages', [])
                        messages.extend(batch_messages)
                        page_token = result.get('nextPageToken')
                        
                        if not page_token:
                            break
                            
                        # Respect limit across all chunks
                        if limit and len(all_email_data) + len(messages) >= limit:
                            messages = messages[:limit - len(all_email_data)]
                            break
                            
                    except HttpError as e:
                        if e.resp.status == 500:
                            # Gmail backend error - try simplified query
                            self.logger.warning(f"Gmail API 500 error with query: {query}")
                            self.logger.info("Trying simplified query without category filters...")
                            
                            # Fallback to basic query
                            simple_query = self._build_simple_gmail_query(chunk_filter)
                            self.logger.info(f"Simplified Gmail query: {simple_query}")
                            
                            result = await self._retry_with_backoff(
                                lambda: self.service.users().messages().list(
                                userId='me',
                                q=simple_query,
                                maxResults=100,
                                pageToken=page_token
                            ).execute()
                            )
                            
                            batch_messages = result.get('messages', [])
                            messages.extend(batch_messages)
                            page_token = result.get('nextPageToken')
                            
                            if not page_token:
                                break
                        else:
                            raise
                
                if not messages:
                    if total_chunks > 1:
                        self.logger.info(f"No messages found in chunk {chunk_idx + 1}/{total_chunks}")
                    continue
                
                chunk_message_count = len(messages)
                self.logger.info(f"Found {chunk_message_count} messages in this chunk")

                # Group messages by thread to reduce API calls
            threads = {}
            for msg in messages:
                thread_id = msg.get('threadId')
                if thread_id not in threads:
                    threads[thread_id] = []
                threads[thread_id].append(msg['id'])
            
                thread_ids = list(threads.keys())
                thread_count = len(thread_ids)
                self.logger.info(f"Processing {thread_count} unique threads from {chunk_message_count} messages")
                
                # Process threads in batches to respect rate limits
                for batch_start in range(0, thread_count, self.max_threads_per_batch):
                    batch_end = min(batch_start + self.max_threads_per_batch, thread_count)
                    batch_thread_ids = thread_ids[batch_start:batch_end]
                    
                    self.logger.debug(f"Processing thread batch {batch_start // self.max_threads_per_batch + 1} "
                                    f"({len(batch_thread_ids)} threads)")
                    
                    # Get thread data for this batch
                    batch_threads = await self._get_thread_data_batch(batch_thread_ids)
                    all_email_data.extend(batch_threads)
            
                    # Respect limit
                    if limit and len(all_email_data) >= limit:
                        all_email_data = all_email_data[:limit]
                        break
                
                # Log progress
                if total_chunks > 1:
                    self.logger.info(f"Chunk {chunk_idx + 1}/{total_chunks} complete. "
                                   f"Total emails collected: {len(all_email_data)}")
                
                # Stop if we've hit the limit
                if limit and len(all_email_data) >= limit:
                    self.logger.info(f"Reached limit of {limit} emails")
                    break
            
            self.logger.info(f"Gmail sync complete. Found {len(all_email_data)} total email threads.")
            return all_email_data
            
        except Exception as e:
            self.logger.error(f"Failed to query Gmail messages: {e}")
            return []
    
    async def _get_thread_data(self, thread_id: str, message_ids: List[str]) -> Optional[Dict[str, Any]]:
        """DEPRECATED: Use _get_thread_data_batch instead. Kept for backward compatibility."""
        self.logger.warning("_get_thread_data is deprecated, use batch processing instead")
        batch_result = await self._get_thread_data_batch([thread_id])
        return batch_result[0] if batch_result else None
    
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
        elif operator == 'contains':
            # Generic contains operator for full email content search
            # Use Gmail's quoted search syntax to search body, subject, and other content
            return f'"{value}"'
        
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
            thread_data = await self._get_thread_data_batch([thread_id])
            return thread_data[0] if thread_data else {}
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
            # Query Gmail for recent threads
            self.logger.info(f"Querying Gmail with date_filter: {date_filter}")
            email_threads = await self.query_pages(
                filters=filters, 
                date_filter=date_filter
            )
            
            if not email_threads:
                self.logger.info("No new email threads found from Gmail query.")
                return result
            
            self.logger.info(f"Found {len(email_threads)} email threads from Gmail query.")
            result.pages_fetched = len(email_threads)
            
            pages_to_save = []
            for thread in email_threads:
                # Prepare page data for unified storage
                page_data = self._prepare_page_for_storage(thread, db_config, excluded_properties)
                pages_to_save.append(page_data)
            
            if not pages_to_save:
                self.logger.info("No new or updated threads to save after filtering.")
                return result
            
            # Process pages with proper skipping logic  
            saved_count = 0
            skipped_count = 0
            
            try:
                for page in pages_to_save:
                    page_id = page['page_id']
                    title = page['metadata']['title']
                    
                    # Check if we should skip this page
                    should_skip = False
                    
                    if not force_update:
                        # Check if files exist locally
                        file_status = storage.files_exist_locally(page_id, title, db_config)
                        
                        if file_status['markdown']:
                            # File exists, check timestamps
                            page_date_str = page['metadata'].get('date')
                            db_last_sync_time_str = db_config.last_sync_time
                            
                            if page_date_str and db_last_sync_time_str:
                                try:
                                    # Parse page date (Gmail uses the email date)
                                    page_dt = datetime.fromisoformat(page_date_str.replace("Z", "+00:00"))
                                    sync_dt = datetime.fromisoformat(db_last_sync_time_str.replace("Z", "+00:00"))
                                    
                                    # Add 1 second tolerance for sync time comparison
                                    if page_dt <= (sync_dt + timedelta(seconds=1)):
                                        should_skip = True
                                        self.logger.debug(f"Skipping email thread {page_id} ('{title}'). Exists locally and up-to-date.")
                                        
                                except ValueError as ve:
                                    self.logger.warning(f"Could not parse dates for thread {page_id}: {ve}. Proceeding with sync.")
                    
                    if should_skip:
                        skipped_count += 1
                        result.pages_skipped += 1
                        continue
                    
                    # Save the page
                    try:
                        # Note: storage.save_content is a synchronous method
                        storage.save_content(
                            page_id=page_id,
                            title=title,
                            content_data=page['metadata'],
                            database_config=db_config,
                            markdown_content=page['content']
                        )
                        saved_count += 1
                        result.pages_saved += 1
                    except Exception as page_error:
                        self.logger.error(f"Failed to save page {page_id}: {page_error}")
                        result.errors.append(f"Failed to save {page_id}: {str(page_error)}")
                        result.pages_failed += 1
                
                result.success = saved_count > 0
                
                self.logger.info(f"Sync completed. {saved_count} email threads saved, {skipped_count} skipped")
                # Note: Individual processing messages removed for clean 3-line output per database

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