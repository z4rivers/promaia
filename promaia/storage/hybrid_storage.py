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
            
            # Create notion page chunks table for large page handling
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS notion_page_chunks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    page_id TEXT NOT NULL,
                    chunk_id TEXT UNIQUE NOT NULL,
                    chunk_index INTEGER NOT NULL,
                    total_chunks INTEGER NOT NULL,
                    workspace TEXT NOT NULL,
                    database_name TEXT NOT NULL,

                    -- Chunk boundaries
                    char_start INTEGER,
                    char_end INTEGER,
                    estimated_tokens INTEGER,

                    -- Date-based chunking metadata
                    date_boundary TEXT,  -- YYYY-MM-DD if split by date

                    -- References
                    parent_file_path TEXT NOT NULL,

                    -- Timestamps
                    created_time TEXT,
                    synced_time TEXT NOT NULL,

                    UNIQUE(chunk_id)
                )
            """)

            # Create notion property schema table to track property definitions
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS notion_property_schema (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    database_id TEXT NOT NULL,
                    database_name TEXT NOT NULL,
                    table_name TEXT NOT NULL,
                    property_name TEXT NOT NULL,
                    column_name TEXT NOT NULL,
                    property_type TEXT NOT NULL,
                    notion_type TEXT NOT NULL,
                    added_time TEXT NOT NULL,
                    last_seen TEXT NOT NULL,
                    is_active BOOLEAN DEFAULT TRUE,

                    UNIQUE(database_id, property_name),
                    UNIQUE(table_name, column_name)
                )
            """)
            
            # Create unified view that combines all tables with direct column access
            # Drop and recreate to ensure latest schema (CREATE VIEW IF NOT EXISTS doesn't update)
            cursor.execute("DROP VIEW IF EXISTS unified_content")
            cursor.execute("""
                CREATE VIEW unified_content AS
                
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
        
        # Chunks indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_chunks_page_id ON notion_page_chunks (page_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_chunks_workspace ON notion_page_chunks (workspace, database_name)")

        # Property schema indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_property_schema_db ON notion_property_schema (database_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_property_schema_table ON notion_property_schema (table_name)")
    
    def add_gmail_content(self, content_data: Dict[str, Any]) -> bool:
        """Add Gmail content with optimized schema."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Extract Gmail-specific fields from metadata
                metadata = content_data.get('metadata', {})
                
                # Ensure last_edited_time is initialized to created_time if missing
                created_time = content_data.get('created_time')
                last_edited_time = content_data.get('last_edited_time') or created_time
                
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
                    created_time,
                    last_edited_time,
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
        return self._add_notion_with_properties('notion_journal', content_data)
    
    def add_notion_stories(self, content_data: Dict[str, Any]) -> bool:
        """Add Notion stories content with optimized schema."""
        return self._add_notion_with_properties('notion_stories', content_data)
    
    def add_notion_cms(self, content_data: Dict[str, Any]) -> bool:
        """Add Notion CMS content with optimized schema."""
        return self._add_notion_with_properties('notion_cms', content_data)

    def _add_notion_with_properties(self, table_name: str, content_data: Dict[str, Any]) -> bool:
        """
        Add Notion content with dynamic property extraction.

        This method dynamically extracts and stores ALL properties based on the schema.

        Args:
            table_name: Name of the table (notion_journal, notion_stories, notion_cms)
            content_data: Content data dictionary

        Returns:
            True if successful, False otherwise
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                # Extract metadata and properties
                metadata = content_data.get('metadata', {})
                properties = metadata.get('properties', {})
                database_id = content_data.get('database_id')

                # Base columns that are always present
                columns = ['page_id', 'workspace', 'database_id', 'database_name', 'file_path',
                          'title', 'created_time', 'last_edited_time', 'synced_time',
                          'file_size', 'checksum']
                values = [
                    content_data['page_id'],
                    content_data['workspace'],
                    database_id,
                    content_data['database_name'],
                    content_data['file_path'],
                    content_data.get('title'),
                    content_data.get('created_time'),
                    content_data.get('last_edited_time') or content_data.get('created_time'),
                    content_data['synced_time'],
                    content_data.get('file_size'),
                    content_data.get('checksum')
                ]

                # Get property schema for this database
                if database_id:
                    property_schema = self.get_property_schema(database_id)

                    # Extract and add dynamic properties
                    for prop_schema in property_schema:
                        prop_name = prop_schema['property_name']
                        column_name = prop_schema['column_name']

                        # Check if property exists in page properties
                        if prop_name in properties:
                            # Extract value using flexible extraction
                            value = self.extract_property_value_flexible(properties[prop_name])
                            columns.append(column_name)
                            values.append(value)

                # Build dynamic INSERT query
                placeholders = ', '.join(['?' for _ in columns])
                column_str = ', '.join(columns)

                query = f"""
                    INSERT OR REPLACE INTO {table_name} ({column_str})
                    VALUES ({placeholders})
                """

                cursor.execute(query, values)
                conn.commit()
                return True

        except Exception as e:
            logger.error(f"Error adding Notion content to {table_name}: {e}")
            logger.debug(f"Content data: {content_data.get('page_id', 'unknown')}")
            return False

    def add_generic_content(self, content_data: Dict[str, Any]) -> bool:
        """Add generic content for unknown/new content types."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Ensure last_edited_time is initialized to created_time if missing
                created_time = content_data.get('created_time')
                last_edited_time = content_data.get('last_edited_time') or created_time
                
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
                    created_time,
                    last_edited_time,
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
            sql_success = self.add_gmail_content(content_data)
        elif database_name == 'journal':
            sql_success = self.add_notion_journal(content_data)
        elif database_name == 'stories':
            sql_success = self.add_notion_stories(content_data)
        elif database_name == 'cms':
            sql_success = self.add_notion_cms(content_data)
        else:
            # Use generic table for unknown types
            sql_success = self.add_generic_content(content_data)
        
        # If SQL insertion succeeded, also embed to ChromaDB (if enabled)
        if sql_success:
            self._embed_to_vector_db(content_data)
        
        return sql_success
    
    def _embed_to_vector_db(self, content_data: Dict[str, Any]) -> bool:
        """
        Embed content to ChromaDB for vector search.
        
        This is called after successful SQL insertion and runs silently
        to avoid disrupting the sync flow if vector DB is unavailable.
        """
        try:
            # Check if vector search is enabled - load from main config file
            import json
            config_path = "promaia.config.json"
            with open(config_path, 'r') as f:
                config = json.load(f)
            vector_config = config.get('global', {}).get('vector_search', {})
            
            if not vector_config.get('enabled', False):
                return False  # Vector search disabled, skip silently
            
            # Get required fields
            page_id = content_data.get('page_id')
            file_path = content_data.get('file_path')
            
            if not page_id or not file_path:
                return False  # Missing required fields
            
            # Read markdown content
            if not os.path.exists(file_path):
                return False  # File doesn't exist
            
            with open(file_path, 'r', encoding='utf-8') as f:
                content_text = f.read()
            
            if not content_text or len(content_text.strip()) < 10:
                return False  # Content too short or empty
            
            # Initialize vector DB
            from promaia.storage.vector_db import VectorDBManager
            vector_db = VectorDBManager(chroma_path=vector_config.get('chroma_path', 'chroma_db'))
            
            # Prepare metadata
            metadata = {
                'database_name': content_data.get('database_name', ''),
                'workspace': content_data.get('workspace', ''),
                'created_time': content_data.get('created_time', ''),
                'content_type': content_data.get('content_type', ''),
            }

            # Add properties to metadata (except title, which is in content)
            try:
                database_id = content_data.get('database_id')
                database_name = content_data.get('database_name', '')

                # Determine table name to query properties from
                table_mapping = {
                    'journal': 'notion_journal',
                    'stories': 'notion_stories',
                    'cms': 'notion_cms',
                }
                table_name = table_mapping.get(database_name, None)

                # Query properties if we have a known table
                if table_name and database_id:
                    with sqlite3.connect(self.db_path) as conn:
                        conn.row_factory = sqlite3.Row
                        cursor = conn.cursor()

                        # Get property schema
                        property_schema = self.get_property_schema(database_id)

                        if property_schema:
                            # Build query to fetch page with properties
                            column_names = [prop['column_name'] for prop in property_schema]
                            if column_names:
                                columns_str = ', '.join(column_names)
                                query = f"SELECT {columns_str} FROM {table_name} WHERE page_id = ?"

                                cursor.execute(query, (page_id,))
                                row = cursor.fetchone()

                                if row:
                                    # Add each property to metadata
                                    for col_name in column_names:
                                        value = row[col_name]
                                        if value is not None:  # Only include non-null properties
                                            metadata[col_name] = value

                logger.debug(f"Added {len(metadata) - 4} properties to vector metadata for {page_id}")

            except Exception as e:
                logger.warning(f"Could not add properties to vector metadata for {page_id}: {e}")
            
            # Check chunking configuration
            chunking_config = vector_config.get('chunking', {})
            chunking_enabled = chunking_config.get('enabled', True)
            max_tokens = chunking_config.get('max_tokens_per_chunk', 6000)
            
            # Estimate tokens in content
            estimated_tokens = vector_db.estimate_tokens(content_text)
            
            # Determine if chunking is needed
            if chunking_enabled and estimated_tokens > max_tokens:
                # Content exceeds token limit, use chunking
                logger.info(f"Page {page_id} has {estimated_tokens} tokens (> {max_tokens}), using chunking")
                
                from promaia.storage.page_chunker import chunk_page_content
                from datetime import datetime
                
                # Generate chunks
                chunks = chunk_page_content(
                    markdown_content=content_text,
                    page_id=page_id,
                    block_metadata=None,  # Could be enhanced with block timestamps
                    max_tokens=max_tokens,
                    provider=vector_db.embedding_provider
                )
                
                if not chunks:
                    logger.warning(f"Failed to chunk page {page_id}")
                    return False
                
                # Store chunks in database
                synced_time = datetime.utcnow().isoformat()
                for chunk in chunks:
                    chunk_data = {
                        'chunk_id': chunk['chunk_id'],
                        'page_id': page_id,
                        'chunk_index': chunk['chunk_index'],
                        'total_chunks': chunk['total_chunks'],
                        'workspace': content_data.get('workspace', ''),
                        'database_name': content_data.get('database_name', ''),
                        'char_start': chunk['char_start'],
                        'char_end': chunk['char_end'],
                        'estimated_tokens': chunk['estimated_tokens'],
                        'date_boundary': chunk.get('date_boundary'),
                        'parent_file_path': file_path,
                        'created_time': content_data.get('created_time'),
                        'synced_time': synced_time
                    }
                    self.add_page_chunk(chunk_data)
                
                # Embed chunks to vector DB
                success = vector_db.add_content_with_chunking(
                    page_id=page_id,
                    content_text=content_text,
                    metadata=metadata,
                    chunks=chunks
                )
                
                if success:
                    logger.info(f"✅ Embedded {len(chunks)} chunks to vector DB for page: {page_id}")
                
                return success
            else:
                # Content fits in single embedding, use standard flow
                success = vector_db.add_content(
                    page_id=page_id,
                    content_text=content_text,
                    metadata=metadata
                )
                
                if success:
                    logger.debug(f"✅ Embedded to vector DB: {page_id} ({estimated_tokens} tokens)")
                
                return success
        
        except Exception as e:
            # Silently log errors - don't disrupt sync if vector DB has issues
            logger.debug(f"Could not embed to vector DB for {content_data.get('page_id', 'unknown')}: {e}")
            return False
    
    def add_content_batch(self, content_list: List[Dict[str, Any]]) -> List[bool]:
        """Add multiple content items efficiently - significant performance improvement."""
        if not content_list:
            return []
        
        results = []
        success_count = 0
        
        for content_data in content_list:
            try:
                # Use existing add_content method (already optimized with proper routing)
                success = self.add_content(content_data)
                results.append(success)
                if success:
                    success_count += 1
            except Exception as e:
                logger.error(f"Error in batch add for content {content_data.get('page_id', 'unknown')}: {e}")
                results.append(False)
        
        logger.info(f"Batch processed {len(content_list)} content items with {success_count} successes")
        return results
    
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

    def extract_property_value_flexible(self, property_data: Dict[str, Any]) -> Any:
        """
        Extract value from a Notion property in a flexible way.

        Handles all Notion property types and returns appropriately formatted values.

        Args:
            property_data: Single property dict from Notion API

        Returns:
            Extracted value (str, int, float, list, or None)
        """
        try:
            prop_type = property_data.get('type')

            if not prop_type:
                return None

            # Extract based on type
            if prop_type == 'title':
                title_arr = property_data.get('title', [])
                return title_arr[0]['plain_text'] if title_arr else None

            elif prop_type == 'rich_text':
                text_arr = property_data.get('rich_text', [])
                return ' '.join([t['plain_text'] for t in text_arr]) if text_arr else None

            elif prop_type == 'number':
                return property_data.get('number')

            elif prop_type == 'select':
                select_data = property_data.get('select')
                return select_data['name'] if select_data else None

            elif prop_type == 'multi_select':
                multi_arr = property_data.get('multi_select', [])
                return json.dumps([item['name'] for item in multi_arr]) if multi_arr else None

            elif prop_type == 'status':
                status_data = property_data.get('status')
                return status_data['name'] if status_data else None

            elif prop_type == 'date':
                date_data = property_data.get('date')
                return date_data['start'] if date_data else None

            elif prop_type == 'checkbox':
                return 1 if property_data.get('checkbox') else 0

            elif prop_type == 'url':
                return property_data.get('url')

            elif prop_type == 'email':
                return property_data.get('email')

            elif prop_type == 'phone_number':
                return property_data.get('phone_number')

            elif prop_type == 'relation':
                relation_arr = property_data.get('relation', [])
                return json.dumps([r['id'] for r in relation_arr]) if relation_arr else None

            elif prop_type == 'people':
                people_arr = property_data.get('people', [])
                return json.dumps([p['id'] for p in people_arr]) if people_arr else None

            elif prop_type == 'files':
                files_arr = property_data.get('files', [])
                return json.dumps([f.get('name', f.get('file', {}).get('url', ''))
                                  for f in files_arr]) if files_arr else None

            elif prop_type == 'formula':
                formula_data = property_data.get('formula', {})
                formula_type = formula_data.get('type')
                if formula_type:
                    return formula_data.get(formula_type)
                return None

            elif prop_type == 'rollup':
                rollup_data = property_data.get('rollup', {})
                rollup_type = rollup_data.get('type')
                if rollup_type == 'number':
                    return rollup_data.get('number')
                elif rollup_type == 'array':
                    return json.dumps(rollup_data.get('array', []))
                return None

            elif prop_type in ['created_time', 'last_edited_time']:
                return property_data.get(prop_type)

            elif prop_type in ['created_by', 'last_edited_by']:
                user_data = property_data.get(prop_type)
                return user_data.get('id') if user_data else None

            else:
                # Unknown type, try to serialize as JSON
                logger.warning(f"Unknown property type: {prop_type}")
                return json.dumps(property_data)

        except Exception as e:
            logger.error(f"Error extracting property value: {e}")
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
    
    def add_page_chunk(self, chunk_data: Dict[str, Any]) -> bool:
        """
        Add a page chunk to the database.
        
        Args:
            chunk_data: Dict containing chunk metadata
                Required: chunk_id, page_id, chunk_index, total_chunks, 
                         workspace, database_name, parent_file_path, synced_time
                Optional: char_start, char_end, estimated_tokens, date_boundary, created_time
        
        Returns:
            True if successful, False otherwise
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO notion_page_chunks (
                        chunk_id, page_id, chunk_index, total_chunks,
                        workspace, database_name, char_start, char_end,
                        estimated_tokens, date_boundary, parent_file_path,
                        created_time, synced_time
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    chunk_data['chunk_id'],
                    chunk_data['page_id'],
                    chunk_data['chunk_index'],
                    chunk_data['total_chunks'],
                    chunk_data['workspace'],
                    chunk_data['database_name'],
                    chunk_data.get('char_start'),
                    chunk_data.get('char_end'),
                    chunk_data.get('estimated_tokens'),
                    chunk_data.get('date_boundary'),
                    chunk_data['parent_file_path'],
                    chunk_data.get('created_time'),
                    chunk_data['synced_time']
                ))
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Error adding page chunk {chunk_data.get('chunk_id')}: {e}")
            return False
    
    def get_chunks_for_page(self, page_id: str) -> List[Dict[str, Any]]:
        """
        Retrieve all chunks for a given page.
        
        Args:
            page_id: Page identifier
        
        Returns:
            List of chunk metadata dicts, ordered by chunk_index
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT * FROM notion_page_chunks 
                    WHERE page_id = ?
                    ORDER BY chunk_index
                """, (page_id,))
                rows = cursor.fetchall()
                return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Error retrieving chunks for page {page_id}: {e}")
            return []
    
    def remove_chunks_for_page(self, page_id: str) -> bool:
        """
        Remove all chunks for a given page.

        Args:
            page_id: Page identifier

        Returns:
            True if successful, False otherwise
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM notion_page_chunks WHERE page_id = ?", (page_id,))
                conn.commit()
                deleted_count = cursor.rowcount
                if deleted_count > 0:
                    logger.debug(f"Removed {deleted_count} chunks for page {page_id}")
                return True
        except Exception as e:
            logger.error(f"Error removing chunks for page {page_id}: {e}")
            return False

    @staticmethod
    def sanitize_property_name(property_name: str) -> str:
        """
        Sanitize a Notion property name to create a valid SQLite column name.

        Rules:
        - Convert to lowercase
        - Replace spaces with underscores
        - Remove special characters except underscores
        - Ensure it starts with a letter or underscore
        - Truncate to 64 characters

        Args:
            property_name: Original Notion property name

        Returns:
            Sanitized column name safe for SQLite
        """
        import re

        # Convert to lowercase
        sanitized = property_name.lower()

        # Replace spaces and hyphens with underscores
        sanitized = sanitized.replace(' ', '_').replace('-', '_')

        # Remove all characters except alphanumeric and underscores
        sanitized = re.sub(r'[^a-z0-9_]', '', sanitized)

        # Ensure it starts with a letter or underscore
        if sanitized and not sanitized[0].isalpha() and sanitized[0] != '_':
            sanitized = 'prop_' + sanitized

        # If empty after sanitization, use a default
        if not sanitized:
            sanitized = 'property_value'

        # Truncate to 64 characters
        sanitized = sanitized[:64]

        # Avoid SQL keywords
        sql_keywords = {'select', 'from', 'where', 'table', 'index', 'order', 'group', 'by', 'having', 'join', 'union'}
        if sanitized in sql_keywords:
            sanitized = sanitized + '_prop'

        return sanitized

    @staticmethod
    def get_sqlite_type_for_notion_property(notion_type: str) -> str:
        """
        Map Notion property type to SQLite column type.

        Args:
            notion_type: Notion property type (e.g., 'select', 'number', 'checkbox')

        Returns:
            SQLite column type (TEXT, INTEGER, REAL, BOOLEAN)
        """
        type_mapping = {
            'title': 'TEXT',
            'rich_text': 'TEXT',
            'number': 'REAL',
            'select': 'TEXT',
            'multi_select': 'TEXT',  # Will store as JSON array
            'status': 'TEXT',
            'date': 'TEXT',  # Store as ISO format string
            'checkbox': 'INTEGER',  # SQLite boolean (0/1)
            'url': 'TEXT',
            'email': 'TEXT',
            'phone_number': 'TEXT',
            'formula': 'TEXT',  # Complex, store as text
            'relation': 'TEXT',  # Store as JSON array of IDs
            'rollup': 'TEXT',  # Complex, store as JSON
            'people': 'TEXT',  # Store as JSON array
            'files': 'TEXT',  # Store as JSON array
            'created_time': 'TEXT',
            'last_edited_time': 'TEXT',
            'created_by': 'TEXT',
            'last_edited_by': 'TEXT',
        }

        return type_mapping.get(notion_type, 'TEXT')

    def get_property_schema(self, database_id: str) -> List[Dict[str, Any]]:
        """
        Get the property schema for a specific Notion database.

        Args:
            database_id: Notion database ID

        Returns:
            List of property definitions
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT * FROM notion_property_schema
                    WHERE database_id = ? AND is_active = TRUE
                    ORDER BY added_time
                """, (database_id,))
                rows = cursor.fetchall()
                return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Error getting property schema for database {database_id}: {e}")
            return []

    def update_property_schema(self, database_id: str, database_name: str,
                              table_name: str, properties: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update the property schema for a Notion database.

        Compares current properties against stored schema and returns
        changes (added/removed/unchanged properties).

        Args:
            database_id: Notion database ID
            database_name: Notion database name
            table_name: SQL table name (e.g., 'notion_journal')
            properties: Dict of Notion properties from API

        Returns:
            Dict with keys: 'added', 'removed', 'unchanged'
        """
        try:
            now = datetime.utcnow().isoformat()

            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                # Get current schema from database
                cursor.execute("""
                    SELECT property_name, column_name, notion_type
                    FROM notion_property_schema
                    WHERE database_id = ? AND is_active = TRUE
                """, (database_id,))

                current_schema = {row[0]: {'column_name': row[1], 'notion_type': row[2]}
                                 for row in cursor.fetchall()}

                # Analyze changes
                current_props = set(current_schema.keys())
                new_props = set(properties.keys())

                added_props = new_props - current_props
                removed_props = current_props - new_props
                unchanged_props = current_props & new_props

                result = {
                    'added': [],
                    'removed': [],
                    'unchanged': list(unchanged_props)
                }

                # Add new properties to schema
                for prop_name in added_props:
                    prop_data = properties[prop_name]
                    notion_type = prop_data.get('type', 'rich_text')
                    column_name = self.sanitize_property_name(prop_name)
                    sqlite_type = self.get_sqlite_type_for_notion_property(notion_type)

                    # Check if column name already exists (collision)
                    cursor.execute("""
                        SELECT property_name FROM notion_property_schema
                        WHERE table_name = ? AND column_name = ? AND is_active = TRUE
                    """, (table_name, column_name))

                    existing = cursor.fetchone()
                    if existing:
                        # Column name collision - append a suffix
                        suffix = 1
                        original_column = column_name
                        while existing:
                            column_name = f"{original_column}_{suffix}"
                            cursor.execute("""
                                SELECT property_name FROM notion_property_schema
                                WHERE table_name = ? AND column_name = ? AND is_active = TRUE
                            """, (table_name, column_name))
                            existing = cursor.fetchone()
                            suffix += 1

                        logger.warning(f"Column name collision for '{prop_name}', using '{column_name}'")

                    cursor.execute("""
                        INSERT INTO notion_property_schema (
                            database_id, database_name, table_name, property_name,
                            column_name, property_type, notion_type, added_time, last_seen
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (database_id, database_name, table_name, prop_name,
                          column_name, sqlite_type, notion_type, now, now))

                    result['added'].append({
                        'property_name': prop_name,
                        'column_name': column_name,
                        'sqlite_type': sqlite_type,
                        'notion_type': notion_type
                    })

                # Mark removed properties as inactive
                for prop_name in removed_props:
                    cursor.execute("""
                        UPDATE notion_property_schema
                        SET is_active = FALSE
                        WHERE database_id = ? AND property_name = ?
                    """, (database_id, prop_name))

                    result['removed'].append({
                        'property_name': prop_name,
                        'column_name': current_schema[prop_name]['column_name']
                    })

                # Update last_seen for unchanged properties
                for prop_name in unchanged_props:
                    cursor.execute("""
                        UPDATE notion_property_schema
                        SET last_seen = ?
                        WHERE database_id = ? AND property_name = ?
                    """, (now, database_id, prop_name))

                conn.commit()

                if result['added']:
                    logger.info(f"Added {len(result['added'])} properties to schema for {database_name}")
                if result['removed']:
                    logger.info(f"Removed {len(result['removed'])} properties from schema for {database_name}")

                return result

        except Exception as e:
            logger.error(f"Error updating property schema: {e}")
            return {'added': [], 'removed': [], 'unchanged': []}

    def apply_schema_changes(self, table_name: str, schema_changes: Dict[str, Any],
                            remove_columns: bool = False) -> bool:
        """
        Apply schema changes to a table (add/remove columns).

        Args:
            table_name: Name of the table to modify
            schema_changes: Dict from update_property_schema with 'added' and 'removed' lists
            remove_columns: If True, remove columns for removed properties (dangerous!)

        Returns:
            True if successful, False otherwise
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                # Add new columns
                for prop in schema_changes.get('added', []):
                    column_name = prop['column_name']
                    sqlite_type = prop['sqlite_type']

                    # Check if column already exists
                    cursor.execute(f"PRAGMA table_info({table_name})")
                    columns = {row[1] for row in cursor.fetchall()}

                    if column_name in columns:
                        logger.warning(f"Column '{column_name}' already exists in {table_name}, skipping")
                        continue

                    # Add the column
                    alter_query = f"ALTER TABLE {table_name} ADD COLUMN {column_name} {sqlite_type}"
                    logger.info(f"Adding column: {alter_query}")

                    try:
                        cursor.execute(alter_query)
                    except sqlite3.OperationalError as e:
                        logger.error(f"Failed to add column '{column_name}' to {table_name}: {e}")
                        continue

                # Remove columns (if requested and supported)
                # Note: SQLite doesn't support DROP COLUMN directly in older versions
                # This is a destructive operation and should be used carefully
                if remove_columns and schema_changes.get('removed'):
                    logger.warning(f"Column removal requested for {table_name}")

                    # Check SQLite version
                    cursor.execute("SELECT sqlite_version()")
                    version = cursor.fetchone()[0]
                    major_version = int(version.split('.')[0])
                    minor_version = int(version.split('.')[1])

                    # DROP COLUMN supported in SQLite 3.35.0+
                    if major_version > 3 or (major_version == 3 and minor_version >= 35):
                        for prop in schema_changes['removed']:
                            column_name = prop['column_name']
                            drop_query = f"ALTER TABLE {table_name} DROP COLUMN {column_name}"
                            logger.warning(f"Removing column: {drop_query}")

                            try:
                                cursor.execute(drop_query)
                            except sqlite3.OperationalError as e:
                                logger.error(f"Failed to drop column '{column_name}' from {table_name}: {e}")
                    else:
                        logger.warning(f"SQLite version {version} does not support DROP COLUMN. "
                                     f"Columns marked inactive in schema but not removed from table.")

                conn.commit()
                return True

        except Exception as e:
            logger.error(f"Error applying schema changes to {table_name}: {e}")
            return False

    def sync_table_schema_with_properties(self, database_id: str, database_name: str,
                                         properties: Dict[str, Any],
                                         remove_columns: bool = False) -> bool:
        """
        Synchronize a table's schema with Notion properties.

        This is the main entry point for schema synchronization. It:
        1. Determines the correct table for the database
        2. Updates the property schema tracking
        3. Applies changes to the actual database table

        Args:
            database_id: Notion database ID
            database_name: Notion database name
            properties: Dict of Notion properties
            remove_columns: If True, remove columns for deleted properties (default: False)

        Returns:
            True if successful, False otherwise
        """
        try:
            # Determine table name
            table_mapping = {
                'journal': 'notion_journal',
                'stories': 'notion_stories',
                'cms': 'notion_cms',
            }

            table_name = table_mapping.get(database_name, 'generic_content')

            # Skip universal properties that are handled separately
            excluded_props = {
                'Title', 'title',
                'Created time', 'created_time',
                'Last edited time', 'last_edited_time',
                'Created by', 'created_by',
                'Last edited by', 'last_edited_by'
            }

            filtered_properties = {k: v for k, v in properties.items()
                                  if k not in excluded_props}

            # Update schema tracking
            schema_changes = self.update_property_schema(
                database_id, database_name, table_name, filtered_properties
            )

            # Apply changes to table (only if not generic_content)
            if table_name != 'generic_content':
                success = self.apply_schema_changes(table_name, schema_changes, remove_columns)
                if not success:
                    logger.error(f"Failed to apply schema changes to {table_name}")
                    return False

            logger.info(f"Schema synchronized for {database_name} ({table_name})")
            return True

        except Exception as e:
            logger.error(f"Error synchronizing table schema: {e}")
            return False

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