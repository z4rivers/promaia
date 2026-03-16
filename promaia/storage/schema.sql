-- PostgreSQL Schema for Promaia
-- Run this script to initialize the database

-- Enable UUID extension if needed
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Enable pgvector for semantic search (replaces ChromaDB)
-- Requires the pgvector extension to be installed in Supabase (it is by default)
CREATE EXTENSION IF NOT EXISTS vector;

-- ============================================================
-- CONTENT ITEMS TABLE (replaces Supabase content_items)
-- ============================================================
CREATE TABLE IF NOT EXISTS content_items (
    id SERIAL PRIMARY KEY,
    user_id UUID NOT NULL DEFAULT '00000000-0000-0000-0000-000000000001',
    title TEXT,
    content TEXT,
    source_name TEXT NOT NULL,
    content_type TEXT,
    created_date DATE,
    message_date TIMESTAMP WITH TIME ZONE,
    indexed_date TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    metadata JSONB DEFAULT '{}',
    
    UNIQUE(user_id, source_name, title)
);

CREATE INDEX IF NOT EXISTS idx_content_items_user ON content_items(user_id);
CREATE INDEX IF NOT EXISTS idx_content_items_source ON content_items(source_name);
CREATE INDEX IF NOT EXISTS idx_content_items_date ON content_items(created_date DESC);
CREATE INDEX IF NOT EXISTS idx_content_items_indexed ON content_items(indexed_date DESC);


-- ============================================================
-- GMAIL CONTENT TABLE
-- ============================================================
CREATE TABLE IF NOT EXISTS gmail_content (
    id SERIAL PRIMARY KEY,
    page_id TEXT UNIQUE NOT NULL,
    workspace TEXT NOT NULL,
    database_id TEXT NOT NULL,
    file_path TEXT NOT NULL,
    
    -- Gmail-specific fields
    subject TEXT,
    sender_email TEXT,
    sender_name TEXT,
    recipient_emails JSONB,
    cc_recipients JSONB,
    gmail_labels JSONB,
    thread_id TEXT NOT NULL,
    message_id TEXT UNIQUE NOT NULL,
    has_attachments BOOLEAN DEFAULT FALSE,
    is_unread BOOLEAN DEFAULT FALSE,
    body_snippet TEXT,
    message_content TEXT,
    attachments JSONB,
    
    -- Message position
    thread_position INTEGER DEFAULT 0,
    is_latest_in_thread BOOLEAN DEFAULT FALSE,
    
    -- Timestamps
    email_date TEXT,
    created_time TEXT,
    last_edited_time TEXT,
    synced_time TEXT NOT NULL,
    
    -- File metadata
    file_size INTEGER,
    checksum TEXT
);

CREATE INDEX IF NOT EXISTS idx_gmail_thread ON gmail_content(thread_id);
CREATE INDEX IF NOT EXISTS idx_gmail_sender ON gmail_content(sender_email);
CREATE INDEX IF NOT EXISTS idx_gmail_date ON gmail_content(email_date DESC);
CREATE INDEX IF NOT EXISTS idx_gmail_workspace ON gmail_content(workspace);


-- ============================================================
-- NOTION JOURNAL TABLE
-- ============================================================
CREATE TABLE IF NOT EXISTS notion_journal (
    id SERIAL PRIMARY KEY,
    page_id TEXT UNIQUE NOT NULL,
    workspace TEXT NOT NULL,
    database_id TEXT NOT NULL,
    database_name TEXT NOT NULL,
    file_path TEXT NOT NULL,
    
    -- Journal-specific fields
    title TEXT,
    status TEXT,
    date_value TEXT,
    tags JSONB,
    featured BOOLEAN DEFAULT FALSE,
    author_name TEXT,
    
    -- Timestamps
    created_time TEXT,
    last_edited_time TEXT,
    synced_time TEXT NOT NULL,
    
    -- File metadata
    file_size INTEGER,
    checksum TEXT
);

CREATE INDEX IF NOT EXISTS idx_journal_workspace ON notion_journal(workspace);
CREATE INDEX IF NOT EXISTS idx_journal_date ON notion_journal(date_value DESC);


-- ============================================================
-- NOTION STORIES TABLE
-- ============================================================
CREATE TABLE IF NOT EXISTS notion_stories (
    id SERIAL PRIMARY KEY,
    page_id TEXT UNIQUE NOT NULL,
    workspace TEXT NOT NULL,
    database_id TEXT NOT NULL,
    database_name TEXT NOT NULL,
    file_path TEXT NOT NULL,
    
    -- Stories-specific fields
    title TEXT,
    status TEXT,
    epic_relation TEXT,
    author_name TEXT,
    story_points INTEGER,
    priority TEXT,
    labels JSONB,
    
    -- Timestamps
    created_time TEXT,
    last_edited_time TEXT,
    synced_time TEXT NOT NULL,
    
    -- File metadata
    file_size INTEGER,
    checksum TEXT
);

CREATE INDEX IF NOT EXISTS idx_stories_workspace ON notion_stories(workspace);
CREATE INDEX IF NOT EXISTS idx_stories_status ON notion_stories(status);


-- ============================================================
-- NOTION CMS TABLE
-- ============================================================
CREATE TABLE IF NOT EXISTS notion_cms (
    id SERIAL PRIMARY KEY,
    page_id TEXT UNIQUE NOT NULL,
    workspace TEXT NOT NULL,
    database_id TEXT NOT NULL,
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
    tags JSONB,
    publish_date TEXT,
    
    -- Timestamps
    created_time TEXT,
    last_edited_time TEXT,
    synced_time TEXT NOT NULL,
    
    -- File metadata
    file_size INTEGER,
    checksum TEXT
);

CREATE INDEX IF NOT EXISTS idx_cms_workspace ON notion_cms(workspace);
CREATE INDEX IF NOT EXISTS idx_cms_status ON notion_cms(status);
CREATE INDEX IF NOT EXISTS idx_cms_slug ON notion_cms(slug);


-- ============================================================
-- CONVERSATION CONTENT TABLE
-- ============================================================
CREATE TABLE IF NOT EXISTS conversation_content (
    id SERIAL PRIMARY KEY,
    page_id TEXT UNIQUE NOT NULL,
    workspace TEXT NOT NULL,
    database_id TEXT NOT NULL,
    file_path TEXT NOT NULL,
    
    -- Conversation-specific fields
    thread_id TEXT UNIQUE NOT NULL,
    thread_name TEXT,
    message_count INTEGER DEFAULT 0,
    context_type TEXT,
    sql_query_prompt TEXT,
    
    -- Timestamps
    created_time TEXT,
    last_edited_time TEXT,
    synced_time TEXT NOT NULL,
    
    -- File metadata
    file_size INTEGER,
    checksum TEXT
);

CREATE INDEX IF NOT EXISTS idx_conversation_thread ON conversation_content(thread_id);


-- ============================================================
-- GENERIC CONTENT TABLE
-- ============================================================
CREATE TABLE IF NOT EXISTS generic_content (
    id SERIAL PRIMARY KEY,
    page_id TEXT UNIQUE NOT NULL,
    workspace TEXT NOT NULL,
    database_id TEXT NOT NULL,
    database_name TEXT NOT NULL,
    content_type TEXT NOT NULL,
    file_path TEXT NOT NULL,
    
    -- Basic fields
    title TEXT,
    
    -- Timestamps
    created_time TEXT,
    last_edited_time TEXT,
    synced_time TEXT NOT NULL,
    
    -- File metadata
    file_size INTEGER,
    checksum TEXT,
    metadata JSONB
);

CREATE INDEX IF NOT EXISTS idx_generic_workspace ON generic_content(workspace);
CREATE INDEX IF NOT EXISTS idx_generic_type ON generic_content(content_type);


-- ============================================================
-- NOTION PAGE CHUNKS TABLE
-- ============================================================
CREATE TABLE IF NOT EXISTS notion_page_chunks (
    id SERIAL PRIMARY KEY,
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
    date_boundary TEXT,
    
    -- References
    parent_file_path TEXT NOT NULL,
    
    -- Timestamps
    created_time TEXT,
    synced_time TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_chunks_page ON notion_page_chunks(page_id);


-- ============================================================
-- NOTION PROPERTY SCHEMA TABLE
-- ============================================================
CREATE TABLE IF NOT EXISTS notion_property_schema (
    id SERIAL PRIMARY KEY,
    database_id TEXT NOT NULL,
    database_name TEXT NOT NULL,
    table_name TEXT NOT NULL,
    property_name TEXT NOT NULL,
    property_id TEXT,
    column_name TEXT NOT NULL,
    property_type TEXT NOT NULL,
    notion_type TEXT NOT NULL,
    added_time TEXT NOT NULL,
    last_seen TEXT NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    
    UNIQUE(database_id, property_name),
    UNIQUE(table_name, column_name)
);


-- ============================================================
-- NOTION SELECT OPTIONS TABLE
-- ============================================================
CREATE TABLE IF NOT EXISTS notion_select_options (
    id SERIAL PRIMARY KEY,
    database_id TEXT NOT NULL,
    property_id TEXT NOT NULL,
    property_name TEXT NOT NULL,
    option_id TEXT NOT NULL,
    option_name TEXT NOT NULL,
    option_color TEXT,
    property_type TEXT NOT NULL,
    first_seen TEXT NOT NULL,
    last_seen TEXT NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    
    UNIQUE(database_id, property_id, option_id)
);

CREATE INDEX IF NOT EXISTS idx_select_options_db ON notion_select_options(database_id);


-- ============================================================
-- NOTION RELATIONS TABLE
-- ============================================================
CREATE TABLE IF NOT EXISTS notion_relations (
    id SERIAL PRIMARY KEY,
    database_id TEXT NOT NULL,
    property_id TEXT NOT NULL,
    property_name TEXT NOT NULL,
    related_database_id TEXT NOT NULL,
    relation_type TEXT NOT NULL,
    synced_property_id TEXT,
    first_seen TEXT NOT NULL,
    last_seen TEXT NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    
    UNIQUE(database_id, property_id)
);


-- ============================================================
-- BLOCK CACHE TABLE
-- ============================================================
CREATE TABLE IF NOT EXISTS block_cache (
    id SERIAL PRIMARY KEY,
    page_id TEXT NOT NULL,
    last_edited_time TEXT NOT NULL,
    blocks JSONB NOT NULL,
    cached_at DOUBLE PRECISION NOT NULL,
    
    UNIQUE(page_id, last_edited_time)
);

CREATE INDEX IF NOT EXISTS idx_block_cache_page ON block_cache(page_id);
CREATE INDEX IF NOT EXISTS idx_block_cache_time ON block_cache(cached_at);


-- ============================================================
-- SYNC CACHE TABLE (PAGE CACHE)
-- ============================================================
CREATE TABLE IF NOT EXISTS page_cache (
    id SERIAL PRIMARY KEY,
    page_id TEXT UNIQUE NOT NULL,
    content_hash TEXT NOT NULL,
    last_edited_time TEXT,
    last_synced_at DOUBLE PRECISION NOT NULL,
    webflow_id TEXT
);

CREATE INDEX IF NOT EXISTS idx_page_cache_synced ON page_cache(last_synced_at);


-- ============================================================
-- OCR UPLOADS TABLE
-- ============================================================
CREATE TABLE IF NOT EXISTS ocr_uploads (
    id SERIAL PRIMARY KEY,
    page_id TEXT UNIQUE,
    workspace TEXT NOT NULL,
    database_name TEXT NOT NULL,
    title TEXT NOT NULL,
    file_path TEXT NOT NULL,
    
    -- Image paths
    source_image_path TEXT UNIQUE NOT NULL,
    processed_image_path TEXT,
    
    -- OCR results
    ocr_confidence REAL,
    ocr_engine TEXT,
    language TEXT,
    text_length INTEGER,
    
    -- Status
    status TEXT,
    
    -- Timestamps
    upload_date TEXT,
    processing_date TEXT,
    created_time TEXT NOT NULL,
    last_edited_time TEXT,
    synced_time TEXT,
    
    -- Additional metadata
    metadata JSONB
);

CREATE INDEX IF NOT EXISTS idx_ocr_workspace_status ON ocr_uploads(workspace, status);
CREATE INDEX IF NOT EXISTS idx_ocr_processing_date ON ocr_uploads(processing_date);


-- ============================================================
-- EMAIL DRAFTS TABLE
-- ============================================================
CREATE TABLE IF NOT EXISTS email_drafts (
    id SERIAL PRIMARY KEY,
    draft_id TEXT UNIQUE NOT NULL,
    workspace TEXT NOT NULL,
    thread_id TEXT NOT NULL,
    message_id TEXT NOT NULL,
    inbound_subject TEXT,
    inbound_from TEXT,
    inbound_snippet TEXT,
    inbound_date TEXT,
    inbound_body TEXT,
    inbound_to TEXT,
    inbound_cc TEXT,
    
    -- Classification results
    pertains_to_me BOOLEAN DEFAULT TRUE,
    is_spam BOOLEAN DEFAULT FALSE,
    requires_response BOOLEAN DEFAULT TRUE,
    classification_reasoning TEXT,
    
    -- Draft response
    draft_subject TEXT,
    draft_body TEXT,
    draft_body_html TEXT,
    
    -- Context
    response_context TEXT,
    system_prompt TEXT,
    ai_model TEXT,
    
    -- Draft versioning
    draft_number INTEGER DEFAULT 1,
    chat_session_id TEXT,
    previous_draft_id TEXT,
    version INTEGER DEFAULT 1,
    draft_history JSONB,
    chat_messages JSONB,
    
    -- Status tracking
    status TEXT DEFAULT 'pending',
    created_time TEXT NOT NULL,
    reviewed_time TEXT,
    sent_time TEXT,
    completed_time TEXT,
    
    -- Safety mechanism
    safety_string TEXT,
    
    -- Thread context
    thread_context TEXT,
    message_count INTEGER DEFAULT 1
);

CREATE INDEX IF NOT EXISTS idx_drafts_workspace_status ON email_drafts(workspace, status);
CREATE INDEX IF NOT EXISTS idx_drafts_thread ON email_drafts(thread_id);


-- ============================================================
-- MAIL SYNC STATE TABLE
-- ============================================================
CREATE TABLE IF NOT EXISTS mail_sync_state (
    id SERIAL PRIMARY KEY,
    workspace TEXT UNIQUE NOT NULL,
    last_sync_time TEXT NOT NULL,
    updated_at TEXT NOT NULL
);


-- ============================================================
-- AGENT TASKS TABLE
-- ============================================================
CREATE TABLE IF NOT EXISTS agent_tasks (
    id SERIAL PRIMARY KEY,
    task_id TEXT UNIQUE NOT NULL,
    task_type TEXT NOT NULL,
    workspace TEXT NOT NULL,
    instructions TEXT NOT NULL,
    context TEXT NOT NULL,
    metadata JSONB,
    
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    expires_at TEXT,
    started_at TEXT,
    completed_at TEXT,
    
    related_draft_id TEXT,
    related_thread_id TEXT,
    progress_notes TEXT
);

CREATE INDEX IF NOT EXISTS idx_tasks_status ON agent_tasks(status);
CREATE INDEX IF NOT EXISTS idx_tasks_workspace ON agent_tasks(workspace, status);
CREATE INDEX IF NOT EXISTS idx_tasks_type ON agent_tasks(task_type, status);


-- ============================================================
-- AGENT RESULTS TABLE
-- ============================================================
CREATE TABLE IF NOT EXISTS agent_results (
    id SERIAL PRIMARY KEY,
    task_id TEXT NOT NULL REFERENCES agent_tasks(task_id),
    status TEXT NOT NULL,
    result_data TEXT NOT NULL,
    metadata JSONB,
    
    error_message TEXT,
    created_at TEXT NOT NULL,
    
    agent_name TEXT,
    agent_version TEXT,
    execution_time_seconds REAL
);

CREATE INDEX IF NOT EXISTS idx_results_task ON agent_results(task_id);


-- ============================================================
-- CHAT HISTORY TABLE
-- ============================================================
CREATE TABLE IF NOT EXISTS chat_threads (
    id SERIAL PRIMARY KEY,
    thread_id TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    messages JSONB NOT NULL DEFAULT '[]',
    context JSONB NOT NULL DEFAULT '{}',
    last_accessed TIMESTAMP WITH TIME ZONE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    user_id UUID DEFAULT '00000000-0000-0000-0000-000000000001'
);

CREATE INDEX IF NOT EXISTS idx_chat_threads_user ON chat_threads(user_id);
CREATE INDEX IF NOT EXISTS idx_chat_threads_accessed ON chat_threads(last_accessed DESC);


-- ============================================================
-- UNIFIED CONTENT VIEW
-- ============================================================
CREATE OR REPLACE VIEW unified_content AS
SELECT 
    page_id, workspace, 'gmail' as database_name, 'gmail' as content_type,
    file_path, subject as title, sender_email, sender_name, 
    created_time, last_edited_time, synced_time,
    file_size, checksum, message_content as metadata
FROM gmail_content
UNION ALL
SELECT 
    page_id, workspace, database_name, 'journal' as content_type,
    file_path, title, NULL as sender_email, author_name as sender_name,
    created_time, last_edited_time, synced_time,
    file_size, checksum, NULL as metadata
FROM notion_journal
UNION ALL
SELECT 
    page_id, workspace, database_name, 'stories' as content_type,
    file_path, title, NULL as sender_email, author_name as sender_name,
    created_time, last_edited_time, synced_time,
    file_size, checksum, NULL as metadata
FROM notion_stories
UNION ALL
SELECT 
    page_id, workspace, database_name, 'cms' as content_type,
    file_path, title, NULL as sender_email, author_name as sender_name,
    created_time, last_edited_time, synced_time,
    file_size, checksum, NULL as metadata
FROM notion_cms
UNION ALL
SELECT 
    page_id, workspace, database_name, content_type,
    file_path, title, NULL as sender_email, NULL as sender_name,
    created_time, last_edited_time, synced_time,
    file_size, checksum, metadata::TEXT
FROM generic_content;


-- ============================================================
-- CONTENT EMBEDDINGS TABLE (replaces ChromaDB content collection)
-- Uses vector(768) for gemini-embedding-001 output dimensions.
-- HNSW index with cosine similarity matches ChromaDB's hnsw:space=cosine config.
-- ============================================================
CREATE TABLE IF NOT EXISTS content_embeddings (
    id SERIAL PRIMARY KEY,
    page_id TEXT NOT NULL,
    chunk_id TEXT,
    content TEXT NOT NULL,
    embedding vector(768) NOT NULL,
    workspace TEXT,
    database_name TEXT,
    metadata JSONB DEFAULT '{}',
    is_chunk BOOLEAN DEFAULT FALSE,
    chunk_index INTEGER,
    total_chunks INTEGER,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(page_id, chunk_id)
);

-- HNSW index for fast approximate nearest neighbor search (cosine similarity)
CREATE INDEX IF NOT EXISTS idx_content_embeddings_vector
    ON content_embeddings USING hnsw (embedding vector_cosine_ops);

-- GIN index for hybrid search on metadata JSONB
CREATE INDEX IF NOT EXISTS idx_content_embeddings_metadata
    ON content_embeddings USING gin (metadata);

-- B-tree indexes for common query patterns
CREATE INDEX IF NOT EXISTS idx_content_embeddings_page_id
    ON content_embeddings(page_id);
CREATE INDEX IF NOT EXISTS idx_content_embeddings_workspace
    ON content_embeddings(workspace);


-- ============================================================
-- PROPERTY EMBEDDINGS TABLE (replaces ChromaDB property collection)
-- Stores embeddings for individual Notion property values.
-- ============================================================
CREATE TABLE IF NOT EXISTS property_embeddings (
    id SERIAL PRIMARY KEY,
    page_id TEXT NOT NULL,
    property_name TEXT NOT NULL,
    property_type TEXT,
    property_value TEXT NOT NULL,
    embedding vector(768) NOT NULL,
    workspace TEXT,
    database_name TEXT,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(page_id, property_name)
);

-- HNSW index for fast approximate nearest neighbor search (cosine similarity)
CREATE INDEX IF NOT EXISTS idx_property_embeddings_vector
    ON property_embeddings USING hnsw (embedding vector_cosine_ops);

-- GIN index for hybrid search on metadata JSONB
CREATE INDEX IF NOT EXISTS idx_property_embeddings_metadata
    ON property_embeddings USING gin (metadata);

-- B-tree indexes for common query patterns
CREATE INDEX IF NOT EXISTS idx_property_embeddings_page_id
    ON property_embeddings(page_id);
CREATE INDEX IF NOT EXISTS idx_property_embeddings_property
    ON property_embeddings(property_name);


-- ============================================================
-- GRANT PERMISSIONS (if needed)
-- ============================================================
-- GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO promaia;
-- GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO promaia;

-- ============================================================
-- AGENT SIGNALING: MESSAGES TABLE
-- ============================================================
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    from_agent TEXT NOT NULL,
    to_agent TEXT,
    context_id TEXT,
    msg_type TEXT NOT NULL,
    subject TEXT NOT NULL,
    body TEXT,
    context TEXT,
    priority TEXT DEFAULT ''normal'',
    status TEXT DEFAULT ''new'',
    reply_to INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    seen_at TIMESTAMP,
    acked_at TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_messages_to ON messages(to_agent, status);
CREATE INDEX IF NOT EXISTS idx_messages_context ON messages(context_id);

-- ============================================================
-- AGENT SIGNALING: PRESENCE TABLE
-- ============================================================
CREATE TABLE IF NOT EXISTS presence (
    agent_name TEXT PRIMARY KEY,
    status TEXT DEFAULT ''offline'',
    last_active TIMESTAMP,
    working_on INTEGER,
    active_files TEXT,
    session_info TEXT
);
