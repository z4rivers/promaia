"""
Hybrid Storage Architecture - Separate optimized tables for each content type.

This module implements a hybrid approach where different content types 
(Gmail, Notion databases, etc.) have their own optimized table schemas
while maintaining a unified query interface.
"""
import sqlite3
import os
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any, Union
from pathlib import Path

logger = logging.getLogger(__name__)

class HybridContentRegistry:
    """Hybrid storage system with separate tables for each content type."""
    
    def __init__(self, db_path: str = "data/hybrid_metadata.db"):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """Initialize the hybrid database with separate tables for each content type."""
        # Ensure directory exists
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Create Gmail-specific table with optimized schema for individual messages
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS gmail_content (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    page_id TEXT UNIQUE NOT NULL,  -- Individual message ID
                    workspace TEXT NOT NULL,
                    database_id TEXT NOT NULL,  -- Immutable database identifier
                    file_path TEXT NOT NULL,
                    
                    -- Gmail-specific fields for individual messages
                    subject TEXT,
                    sender_email TEXT,
                    sender_name TEXT,
                    recipient_emails TEXT, -- JSON array
                    gmail_labels TEXT, -- JSON array
                    thread_id TEXT NOT NULL,  -- Links messages in same conversation
                    message_id TEXT UNIQUE NOT NULL,  -- Gmail's unique message identifier
                    has_attachments BOOLEAN DEFAULT FALSE,
                    is_unread BOOLEAN DEFAULT FALSE,
                    body_snippet TEXT,
                    message_content TEXT,  -- Full message content (extracted, not quoted)
                    
                    -- Message position in thread
                    thread_position INTEGER DEFAULT 0,  -- 0 = first message, 1 = second, etc.
                    is_latest_in_thread BOOLEAN DEFAULT FALSE,  -- TRUE for the most recent message in thread
                    
                    -- Common timestamp fields (properly typed)
                    email_date TEXT, -- Gmail's original message date
                    created_time TEXT,
                    last_edited_time TEXT,  -- For threads, this is the latest message date
                    synced_time TEXT NOT NULL,
                    
                    -- File metadata
                    file_size INTEGER,
                    checksum TEXT,
                    
                    UNIQUE(page_id),
                    UNIQUE(message_id)
                )
            """)
            
            # Create Notion Journal table with optimized schema
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS notion_journal (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    page_id TEXT UNIQUE NOT NULL,
                    workspace TEXT NOT NULL,
                    database_id TEXT NOT NULL,  -- Immutable database identifier
                    database_name TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    
                    -- Journal-specific fields
                    title TEXT,
                    status TEXT, -- Published, Draft, etc.
                    date_value TEXT, -- The "Date" property
                    tags TEXT, -- JSON array
                    featured BOOLEAN DEFAULT FALSE,
                    author_name TEXT,
                    
                    -- Common timestamp fields
                    created_time TEXT,
                    last_edited_time TEXT,
                    synced_time TEXT NOT NULL,
                    
                    -- File metadata
                    file_size INTEGER,
                    checksum TEXT,
                    
                    UNIQUE(page_id)
                )
            """)
            
            # Create Notion Stories table with optimized schema
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS notion_stories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    page_id TEXT UNIQUE NOT NULL,
                    workspace TEXT NOT NULL,
                    database_id TEXT NOT NULL,  -- Immutable database identifier
                    database_name TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    
                    -- Stories-specific fields
                    title TEXT,
                    status TEXT, -- Done, In Progress, Backlog, etc.
                    epic_relation TEXT, -- Related epic page_id
                    author_name TEXT,
                    story_points INTEGER,
                    priority TEXT,
                    labels TEXT, -- JSON array
                    
                    -- Common timestamp fields
                    created_time TEXT,
                    last_edited_time TEXT,
                    synced_time TEXT NOT NULL,
                    
                    -- File metadata
                    file_size INTEGER,
                    checksum TEXT,
                    
                    UNIQUE(page_id)
                )
            """)
            
            # Create CMS content table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS notion_cms (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    page_id TEXT UNIQUE NOT NULL,
                    workspace TEXT NOT NULL,
                    database_id TEXT NOT NULL,  -- Immutable database identifier
                    database_name TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    
                    -- CMS-specific fields
                    title TEXT,
                    status TEXT,
                    category TEXT,
                    featured BOOLEAN DEFAULT FALSE,
                    author_name TEXT,
                    slug TEXT,
                    meta_description TEXT,
                    tags TEXT, -- JSON array
                    publish_date TEXT,
                    
                    -- Common timestamp fields
                    created_time TEXT,
                    last_edited_time TEXT,
                    synced_time TEXT NOT NULL,
                    
                    -- File metadata
                    file_size INTEGER,
                    checksum TEXT,
                    
                    UNIQUE(page_id)
                )
            """)
            
            # Create generic content table for unknown/new content types
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS generic_content (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    page_id TEXT UNIQUE NOT NULL,
                    workspace TEXT NOT NULL,
                    database_id TEXT NOT NULL,  -- Immutable database identifier
                    database_name TEXT NOT NULL,
                    content_type TEXT NOT NULL, -- 'awakenings', 'cpj', etc.
                    file_path TEXT NOT NULL,
                    
                    -- Basic fields
                    title TEXT,
                    
                    -- Common timestamp fields
                    created_time TEXT,
                    last_edited_time TEXT,
                    synced_time TEXT NOT NULL,
                    
                    -- File metadata
                    file_size INTEGER,
                    checksum TEXT,
                    
                    -- Flexible metadata for unknown properties
                    metadata TEXT, -- JSON string for properties that don't fit above
                    
                    UNIQUE(page_id)
                )
            """)
            
            # Create unified view that combines all tables with direct column access
            cursor.execute("""
                CREATE VIEW IF NOT EXISTS unified_content AS
                
                SELECT 
                    page_id,
                    workspace,
                    database_id,
                    'gmail' as database_name,
                    'gmail' as content_type,
                    file_path,
                    subject as title,
                    created_time,
                    last_edited_time,
                    synced_time,
                    file_size,
                    checksum,
                    -- Direct columns for Gmail
                    NULL as status,
                    sender_email,
                    sender_name,
                    has_attachments,
                    is_unread,
                    NULL as featured,
                    NULL as priority,
                    NULL as category,
                    email_date,  -- Add email_date as direct column for Gmail queries
                    -- Metadata for complex fields
                    json_object(
                        'subject', subject,
                        'sender_email', sender_email,
                        'sender_name', sender_name,
                        'recipient_emails', recipient_emails,
                        'labels', gmail_labels,
                        'has_attachments', has_attachments,
                        'is_unread', is_unread,
                        'email_date', email_date
                    ) as metadata
                FROM gmail_content
                
                UNION ALL
                
                SELECT 
                    page_id,
                    workspace,
                    database_id,
                    database_name,
                    'notion_journal' as content_type,
                    file_path,
                    title,
                    created_time,
                    last_edited_time,
                    synced_time,
                    file_size,
                    checksum,
                    -- Direct columns for Journal
                    status,
                    NULL as sender_email,
                    NULL as sender_name,
                    NULL as has_attachments,
                    NULL as is_unread,
                    featured,
                    NULL as priority,
                    NULL as category,
                    NULL as email_date,  -- Add NULL email_date for non-Gmail content
                    -- Metadata for complex fields
                    json_object(
                        'status', status,
                        'date_value', date_value,
                        'tags', tags,
                        'featured', featured,
                        'author_name', author_name
                    ) as metadata
                FROM notion_journal
                
                UNION ALL
                
                SELECT 
                    page_id,
                    workspace,
                    database_id,
                    database_name,
                    'notion_stories' as content_type,
                    file_path,
                    title,
                    created_time,
                    last_edited_time,
                    synced_time,
                    file_size,
                    checksum,
                    -- Direct columns for Stories
                    status,
                    NULL as sender_email,
                    NULL as sender_name,
                    NULL as has_attachments,
                    NULL as is_unread,
                    NULL as featured,
                    priority,
                    NULL as category,
                    NULL as email_date,  -- Add NULL email_date for non-Gmail content
                    -- Metadata for complex fields
                    json_object(
                        'status', status,
                        'epic_relation', epic_relation,
                        'author_name', author_name,
                        'story_points', story_points,
                        'priority', priority,
                        'labels', labels
                    ) as metadata
                FROM notion_stories
                
                UNION ALL
                
                SELECT 
                    page_id,
                    workspace,
                    database_id,
                    database_name,
                    'notion_cms' as content_type,
                    file_path,
                    title,
                    created_time,
                    last_edited_time,
                    synced_time,
                    file_size,
                    checksum,
                    -- Direct columns for CMS
                    status,
                    NULL as sender_email,
                    NULL as sender_name,
                    NULL as has_attachments,
                    NULL as is_unread,
                    featured,
                    NULL as priority,
                    category,
                    NULL as email_date,  -- Add NULL email_date for non-Gmail content
                    -- Metadata for complex fields
                    json_object(
                        'status', status,
                        'category', category,
                        'featured', featured,
                        'author_name', author_name,
                        'slug', slug,
                        'publish_date', publish_date,
                        'tags', tags
                    ) as metadata
                FROM notion_cms
                
                UNION ALL
                
                SELECT 
                    page_id,
                    workspace,
                    database_id,
                    database_name,
                    content_type,
                    file_path,
                    title,
                    created_time,
                    last_edited_time,
                    synced_time,
                    file_size,
                    checksum,
                    -- Direct columns for Generic (use JSON extraction as needed)
                    json_extract(metadata, '$.status') as status,
                    NULL as sender_email,
                    NULL as sender_name,
                    NULL as has_attachments,
                    NULL as is_unread,
                    CAST(json_extract(metadata, '$.featured') AS INTEGER) as featured,
                    json_extract(metadata, '$.priority') as priority,
                    json_extract(metadata, '$.category') as category,
                    NULL as email_date,  -- Add NULL email_date for non-Gmail content
                    metadata
                FROM generic_content
            """)
            
            # Create indexes for better performance
            self._create_indexes(cursor)
            
            conn.commit()
            logger.info(f"Initialized hybrid content registry at {self.db_path}")
    
    def _create_indexes(self, cursor):
        """Create indexes for better query performance."""
        # Gmail indexes for message-level storage
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_gmail_workspace ON gmail_content (workspace)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_gmail_sender ON gmail_content (sender_email)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_gmail_date ON gmail_content (email_date)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_gmail_labels ON gmail_content (gmail_labels)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_gmail_thread_id ON gmail_content (thread_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_gmail_message_id ON gmail_content (message_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_gmail_thread_position ON gmail_content (thread_id, thread_position)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_gmail_latest_in_thread ON gmail_content (thread_id, is_latest_in_thread)")
        
        # Journal indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_journal_workspace ON notion_journal (workspace, database_name)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_journal_status ON notion_journal (status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_journal_date ON notion_journal (date_value)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_journal_featured ON notion_journal (featured)")
        
        # Stories indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_stories_workspace ON notion_stories (workspace, database_name)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_stories_status ON notion_stories (status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_stories_epic ON notion_stories (epic_relation)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_stories_priority ON notion_stories (priority)")
        
        # CMS indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_cms_workspace ON notion_cms (workspace, database_name)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_cms_status ON notion_cms (status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_cms_category ON notion_cms (category)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_cms_featured ON notion_cms (featured)")
        
        # Generic indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_generic_workspace ON generic_content (workspace, database_name)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_generic_type ON generic_content (content_type)")
    
    def add_gmail_content(self, content_data: Dict[str, Any]) -> bool:
        """Add Gmail content with optimized schema."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Extract Gmail-specific fields from metadata
                metadata = content_data.get('metadata', {})
                
                cursor.execute("""
                    INSERT OR REPLACE INTO gmail_content (
                        page_id, workspace, database_id, file_path, subject, sender_email, sender_name,
                        recipient_emails, gmail_labels, thread_id, message_id, 
                        has_attachments, is_unread, body_snippet, message_content,
                        thread_position, is_latest_in_thread, email_date,
                        created_time, last_edited_time, synced_time, file_size, checksum
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    content_data['page_id'],
                    content_data['workspace'],
                    content_data.get('database_id'),
                    content_data['file_path'],
                    metadata.get('subject', content_data.get('title')),
                    metadata.get('sender_email'),
                    metadata.get('sender_name'),
                    json.dumps(metadata.get('recipient_emails', [])),
                    json.dumps(metadata.get('labels', [])),
                    metadata.get('thread_id'),
                    metadata.get('message_id'),
                    metadata.get('has_attachments', False),
                    metadata.get('is_unread', False),
                    metadata.get('body_snippet'),
                    metadata.get('message_content', ''),
                    metadata.get('thread_position', 0),
                    metadata.get('is_latest_in_thread', False),
                    metadata.get('email_date'),
                    content_data.get('created_time'),
                    content_data.get('last_edited_time'),
                    content_data['synced_time'],
                    content_data.get('file_size'),
                    content_data.get('checksum')
                ))
                
                conn.commit()
                return True
                
        except Exception as e:
            logger.error(f"Error adding Gmail content: {e}")
            return False
    
    def get_existing_message_ids_for_thread(self, thread_id: str, workspace: str = None) -> set:
        """Get existing message IDs for a thread to avoid duplicates."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                query = "SELECT message_id FROM gmail_content WHERE thread_id = ?"
                params = [thread_id]
                
                if workspace:
                    query += " AND workspace = ?"
                    params.append(workspace)
                
                cursor.execute(query, params)
                results = cursor.fetchall()
                
                return {row[0] for row in results if row[0]}
                
        except Exception as e:
            logger.error(f"Error getting existing message IDs for thread {thread_id}: {e}")
            return set()
    
    def update_latest_message_flags(self, thread_id: str, latest_message_id: str, workspace: str = None):
        """Update is_latest_in_thread flags for a thread."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # First, set all messages in thread to not latest
                query = "UPDATE gmail_content SET is_latest_in_thread = FALSE WHERE thread_id = ?"
                params = [thread_id]
                
                if workspace:
                    query += " AND workspace = ?"
                    params.append(workspace)
                
                cursor.execute(query, params)
                
                # Then set the latest message to TRUE
                query = "UPDATE gmail_content SET is_latest_in_thread = TRUE WHERE message_id = ?"
                params = [latest_message_id]
                
                if workspace:
                    query += " AND workspace = ?"
                    params.append(workspace)
                
                cursor.execute(query, params)
                conn.commit()
                
        except Exception as e:
            logger.error(f"Error updating latest message flags for thread {thread_id}: {e}")
    
    def add_notion_journal(self, content_data: Dict[str, Any]) -> bool:
        """Add Notion journal content with optimized schema."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Extract journal-specific fields from metadata
                metadata = content_data.get('metadata', {})
                properties = metadata.get('properties', {})
                
                # Extract common Notion property patterns
                status = self._extract_notion_property(properties, 'Status', 'status', 'name')
                date_value = self._extract_notion_property(properties, 'Date', 'date', 'start')
                featured = self._extract_notion_property(properties, 'Featured', 'checkbox')
                author_name = self._extract_notion_property(properties, 'Author Name', 'rich_text', 0, 'plain_text')
                
                # Extract tags
                tags = []
                if 'Tags' in properties or 'tags' in properties:
                    tag_prop = properties.get('Tags') or properties.get('tags')
                    if tag_prop and tag_prop.get('multi_select'):
                        tags = [tag['name'] for tag in tag_prop['multi_select']]
                
                cursor.execute("""
                    INSERT OR REPLACE INTO notion_journal (
                        page_id, workspace, database_id, database_name, file_path, title,
                        status, date_value, tags, featured, author_name,
                        created_time, last_edited_time, synced_time, file_size, checksum
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    content_data['page_id'],
                    content_data['workspace'],
                    content_data.get('database_id'),
                    content_data['database_name'],
                    content_data['file_path'],
                    content_data.get('title'),
                    status,
                    date_value,
                    json.dumps(tags),
                    featured,
                    author_name,
                    content_data.get('created_time'),
                    content_data.get('last_edited_time'),
                    content_data['synced_time'],
                    content_data.get('file_size'),
                    content_data.get('checksum')
                ))
                
                conn.commit()
                return True
                
        except Exception as e:
            logger.error(f"Error adding Notion journal content: {e}")
            return False
    
    def add_notion_stories(self, content_data: Dict[str, Any]) -> bool:
        """Add Notion stories content with optimized schema."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Extract stories-specific fields from metadata
                metadata = content_data.get('metadata', {})
                properties = metadata.get('properties', {})
                
                # Extract common story properties
                status = self._extract_notion_property(properties, 'Status', 'status', 'name')
                author_name = self._extract_notion_property(properties, 'Author Name', 'rich_text', 0, 'plain_text')
                story_points = self._extract_notion_property(properties, 'Story Points', 'number')
                priority = self._extract_notion_property(properties, 'Priority', 'select', 'name')
                
                # Extract epic relation
                epic_relation = None
                if 'Epic' in properties and properties['Epic'].get('relation'):
                    relations = properties['Epic']['relation']
                    if relations:
                        epic_relation = relations[0]['id']
                
                # Extract labels
                labels = []
                if 'Labels' in properties:
                    label_prop = properties['Labels']
                    if label_prop and label_prop.get('multi_select'):
                        labels = [label['name'] for label in label_prop['multi_select']]
                
                cursor.execute("""
                    INSERT OR REPLACE INTO notion_stories (
                        page_id, workspace, database_id, database_name, file_path, title,
                        status, epic_relation, author_name, story_points, priority, labels,
                        created_time, last_edited_time, synced_time, file_size, checksum
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    content_data['page_id'],
                    content_data['workspace'],
                    content_data.get('database_id'),
                    content_data['database_name'],
                    content_data['file_path'],
                    content_data.get('title'),
                    status,
                    epic_relation,
                    author_name,
                    story_points,
                    priority,
                    json.dumps(labels),
                    content_data.get('created_time'),
                    content_data.get('last_edited_time'),
                    content_data['synced_time'],
                    content_data.get('file_size'),
                    content_data.get('checksum')
                ))
                
                conn.commit()
                return True
                
        except Exception as e:
            logger.error(f"Error adding Notion stories content: {e}")
            return False
    
    def add_notion_cms(self, content_data: Dict[str, Any]) -> bool:
        """Add Notion CMS content with optimized schema."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Extract CMS-specific fields from metadata
                metadata = content_data.get('metadata', {})
                properties = metadata.get('properties', {})
                
                # Extract CMS properties
                status = self._extract_notion_property(properties, 'Status', 'status', 'name')
                category = self._extract_notion_property(properties, 'Category', 'select', 'name')
                featured = self._extract_notion_property(properties, 'Featured', 'checkbox')
                author_name = self._extract_notion_property(properties, 'Author', 'rich_text', 0, 'plain_text')
                slug = self._extract_notion_property(properties, 'Slug', 'rich_text', 0, 'plain_text')
                meta_description = self._extract_notion_property(properties, 'Meta Description', 'rich_text', 0, 'plain_text')
                publish_date = self._extract_notion_property(properties, 'Publish Date', 'date', 'start')
                
                # Extract tags
                tags = []
                if 'Tags' in properties:
                    tag_prop = properties['Tags']
                    if tag_prop and tag_prop.get('multi_select'):
                        tags = [tag['name'] for tag in tag_prop['multi_select']]
                
                cursor.execute("""
                    INSERT OR REPLACE INTO notion_cms (
                        page_id, workspace, database_id, database_name, file_path, title,
                        status, category, featured, author_name, slug, meta_description,
                        tags, publish_date, created_time, last_edited_time, synced_time, 
                        file_size, checksum
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    content_data['page_id'],
                    content_data['workspace'],
                    content_data.get('database_id'),
                    content_data['database_name'],
                    content_data['file_path'],
                    content_data.get('title'),
                    status,
                    category,
                    featured,
                    author_name,
                    slug,
                    meta_description,
                    json.dumps(tags),
                    publish_date,
                    content_data.get('created_time'),
                    content_data.get('last_edited_time'),
                    content_data['synced_time'],
                    content_data.get('file_size'),
                    content_data.get('checksum')
                ))
                
                conn.commit()
                return True
                
        except Exception as e:
            logger.error(f"Error adding Notion CMS content: {e}")
            return False
    
    def add_generic_content(self, content_data: Dict[str, Any]) -> bool:
        """Add generic content for unknown/new content types."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    INSERT OR REPLACE INTO generic_content (
                        page_id, workspace, database_id, database_name, content_type, file_path, title,
                        created_time, last_edited_time, synced_time, file_size, checksum, metadata
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    content_data['page_id'],
                    content_data['workspace'],
                    content_data.get('database_id'),
                    content_data['database_name'],
                    content_data.get('content_type', content_data['database_name']),
                    content_data['file_path'],
                    content_data.get('title'),
                    content_data.get('created_time'),
                    content_data.get('last_edited_time'),
                    content_data['synced_time'],
                    content_data.get('file_size'),
                    content_data.get('checksum'),
                    json.dumps(content_data.get('metadata', {}))
                ))
                
                conn.commit()
                return True
                
        except Exception as e:
            logger.error(f"Error adding generic content: {e}")
            return False
    
    def add_content(self, content_data: Dict[str, Any]) -> bool:
        """Add content using the appropriate table based on content type."""
        database_name = content_data.get('database_name', '')
        workspace = content_data.get('workspace', '')
        
        # Route to appropriate table based on content type
        if database_name == 'gmail' or 'gmail' in database_name:
            return self.add_gmail_content(content_data)
        elif database_name == 'journal':
            return self.add_notion_journal(content_data)
        elif database_name == 'stories':
            return self.add_notion_stories(content_data)
        elif database_name == 'cms':
            return self.add_notion_cms(content_data)
        else:
            # Use generic table for unknown types
            return self.add_generic_content(content_data)
    
    def query_content(self, workspace: str = None, database_name: str = None, 
                     content_type: str = None, filters: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """Query content using the unified view."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Build WHERE clause
                where_conditions = []
                params = []
                
                if workspace:
                    where_conditions.append("workspace = ?")
                    params.append(workspace)
                
                if database_name:
                    where_conditions.append("database_name = ?")
                    params.append(database_name)
                
                if content_type:
                    where_conditions.append("content_type = ?")
                    params.append(content_type)
                
                # Add custom filters
                if filters:
                    for key, value in filters.items():
                        if key in ['status', 'featured', 'priority', 'category']:
                            # These can be searched in metadata JSON
                            where_conditions.append(f"json_extract(metadata, '$.{key}') = ?")
                            params.append(value)
                        elif key.endswith('_date') or key.endswith('_time'):
                            where_conditions.append(f"{key} >= ?")
                            params.append(value)
                
                where_clause = " AND ".join(where_conditions) if where_conditions else "1=1"
                
                query = f"""
                    SELECT page_id, workspace, database_name, content_type, file_path, title,
                           created_time, last_edited_time, synced_time, metadata
                    FROM unified_content 
                    WHERE {where_clause}
                    ORDER BY last_edited_time DESC
                """
                
                cursor.execute(query, params)
                results = cursor.fetchall()
                
                # Convert to list of dictionaries
                columns = ['page_id', 'workspace', 'database_name', 'content_type', 'file_path', 
                          'title', 'created_time', 'last_edited_time', 'synced_time', 'metadata']
                
                content_list = []
                for row in results:
                    content_dict = dict(zip(columns, row))
                    # Parse metadata JSON
                    if content_dict['metadata']:
                        content_dict['metadata'] = json.loads(content_dict['metadata'])
                    content_list.append(content_dict)
                
                return content_list
                
        except Exception as e:
            logger.error(f"Error querying content: {e}")
            return []
    
    def get_content_statistics(self) -> Dict[str, Any]:
        """Get statistics about content in each table."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                stats = {}
                
                # Gmail stats
                cursor.execute("SELECT COUNT(*) FROM gmail_content")
                stats['gmail'] = cursor.fetchone()[0]
                
                # Journal stats
                cursor.execute("SELECT COUNT(*) FROM notion_journal")
                stats['journal'] = cursor.fetchone()[0]
                
                # Stories stats
                cursor.execute("SELECT COUNT(*) FROM notion_stories")
                stats['stories'] = cursor.fetchone()[0]
                
                # CMS stats
                cursor.execute("SELECT COUNT(*) FROM notion_cms")
                stats['cms'] = cursor.fetchone()[0]
                
                # Generic stats
                cursor.execute("SELECT COUNT(*) FROM generic_content")
                stats['generic'] = cursor.fetchone()[0]
                
                # Total stats
                cursor.execute("SELECT COUNT(*) FROM unified_content")
                stats['total'] = cursor.fetchone()[0]
                
                return stats
                
        except Exception as e:
            logger.error(f"Error getting statistics: {e}")
            return {}
    
    def migrate_from_legacy(self, legacy_db_path: str = "data/metadata.db") -> bool:
        """Migrate data from legacy single-table structure to hybrid architecture.
        
        DEPRECATED: Legacy migration is no longer supported.
        The system now uses hybrid architecture exclusively.
        """
        logger.warning("Legacy migration is deprecated. System uses hybrid architecture exclusively.")
        logger.info("If you need to import data, use the database sync commands instead.")
        return False
    
    def _extract_notion_property(self, properties: Dict[str, Any], 
                                prop_name: str, prop_type: str, 
                                *path_elements) -> Any:
        """Extract a property value from Notion property structure."""
        try:
            if prop_name not in properties:
                return None
            
            prop = properties[prop_name]
            if prop_type not in prop:
                return None
            
            value = prop[prop_type]
            
            # Navigate through path elements
            for element in path_elements:
                if isinstance(element, int) and isinstance(value, list):
                    if element < len(value):
                        value = value[element]
                    else:
                        return None
                elif isinstance(element, str) and isinstance(value, dict):
                    if element in value:
                        value = value[element]
                    else:
                        return None
                else:
                    return None
            
            return value
            
        except Exception:
            return None

    def get_content_by_file_path(self, file_path: str) -> Optional[Dict[str, Any]]:
        """Retrieve a single content entry by its file path."""
        query = "SELECT * FROM unified_content WHERE file_path = ?"
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute(query, (file_path,))
                row = cursor.fetchone()
                return dict(row) if row else None
        except sqlite3.Error as e:
            print(f"Database error in get_content_by_file_path: {e}")
            return None

    def clear_generic_content_for_database(self, database_name: str) -> int:
        """Deletes all entries from the generic_content table for a specific database."""
        query = "DELETE FROM generic_content WHERE database_name = ?"
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(query, (database_name,))
                conn.commit()
                # Return the number of deleted rows
                return cursor.rowcount
        except sqlite3.Error as e:
            print(f"Database error while clearing generic_content for {database_name}: {e}")
            return 0
            
    def close(self):
        """Close the database connection."""
        # The connection is now managed with 'with' statements, so this is less critical
        # but can be kept for explicit closure if needed elsewhere.


# Global instance
_hybrid_registry = None

def get_hybrid_registry(db_path: str = "data/hybrid_metadata.db") -> HybridContentRegistry:
    """Get the global hybrid content registry instance."""
    global _hybrid_registry
    if _hybrid_registry is None:
        _hybrid_registry = HybridContentRegistry(db_path)
    return _hybrid_registry 