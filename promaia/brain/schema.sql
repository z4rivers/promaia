-- Brain Schema for zBrain
-- All tables live under a dedicated 'brain' Postgres schema.
-- Apply idempotently via apply_brain_schema() in promaia/storage/db_init.py.

-- Requires pgvector extension (already enabled in public schema)
CREATE EXTENSION IF NOT EXISTS vector;

-- Create the brain schema
CREATE SCHEMA IF NOT EXISTS brain;

-- ============================================================
-- brain.memories
-- Core persistent memory store. Stores facts, notes, and
-- observations with semantic embeddings for similarity search.
-- vector(768) matches gemini-embedding-001 with output_dimensionality=768.
-- ============================================================
CREATE TABLE IF NOT EXISTS brain.memories (
    id SERIAL PRIMARY KEY,
    content TEXT NOT NULL,
    summary TEXT,
    domain TEXT,
    tags TEXT[] DEFAULT '{}',
    entities JSONB DEFAULT '{}',
    embedding vector(768),
    source TEXT,
    source_id TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- HNSW index for fast approximate nearest neighbor search (cosine similarity)
-- Same pattern as content_embeddings in public schema
CREATE INDEX IF NOT EXISTS idx_brain_memories_embedding
    ON brain.memories USING hnsw (embedding vector_cosine_ops);

-- GIN index on tags array for fast tag lookups
CREATE INDEX IF NOT EXISTS idx_brain_memories_tags
    ON brain.memories USING gin (tags);


-- ============================================================
-- brain.domains
-- Life categories and projects. Hierarchical via parent_domain.
-- Examples: "promaia", "heatpup", "hvac-brand", "personal"
-- ============================================================
CREATE TABLE IF NOT EXISTS brain.domains (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    description TEXT,
    is_project BOOLEAN DEFAULT TRUE,
    parent_domain INTEGER REFERENCES brain.domains(id),
    created_at TIMESTAMPTZ DEFAULT NOW()
);


-- ============================================================
-- brain.contexts
-- Standing directives and current state per domain.
-- Tracks what Claude should know about each project/life area.
-- stale_threshold_days: how many days before context is considered stale.
-- ============================================================
CREATE TABLE IF NOT EXISTS brain.contexts (
    id SERIAL PRIMARY KEY,
    domain_id INTEGER REFERENCES brain.domains(id) NOT NULL,
    directive TEXT,
    current_state TEXT,
    last_updated TIMESTAMPTZ DEFAULT NOW(),
    priority INTEGER DEFAULT 5,
    stale_threshold_days INTEGER DEFAULT 7
);


-- ============================================================
-- brain.actions
-- Actionable items extracted from memories.
-- status: pending (open), done (completed), stale (expired/irrelevant)
-- ============================================================
CREATE TABLE IF NOT EXISTS brain.actions (
    id SERIAL PRIMARY KEY,
    memory_id INTEGER REFERENCES brain.memories(id),
    domain_id INTEGER REFERENCES brain.domains(id),
    description TEXT NOT NULL,
    status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'done', 'stale')),
    extracted_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);


-- ============================================================
-- brain.reviews
-- Periodic review records (weekly/monthly summaries).
-- Tracks what was accomplished and which projects were touched.
-- ============================================================
CREATE TABLE IF NOT EXISTS brain.reviews (
    id SERIAL PRIMARY KEY,
    period_start TIMESTAMPTZ,
    period_end TIMESTAMPTZ,
    summary TEXT,
    projects_touched JSONB DEFAULT '[]',
    actions_completed INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW()
);


-- ============================================================
-- brain.events
-- Event log for all brain activity: captures, mode switches,
-- heartbeat cycles, API calls, context saves.
-- Used by engine.py for time tracking and budget checks.
-- ============================================================
CREATE TABLE IF NOT EXISTS brain.events (
    id SERIAL PRIMARY KEY,
    type TEXT NOT NULL,
    payload JSONB DEFAULT '{}',
    source TEXT,
    session_id TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- B-tree indexes for common event query patterns
CREATE INDEX IF NOT EXISTS idx_brain_events_type
    ON brain.events (type);

CREATE INDEX IF NOT EXISTS idx_brain_events_source
    ON brain.events (source);

CREATE INDEX IF NOT EXISTS idx_brain_events_created_at
    ON brain.events (created_at DESC);

CREATE INDEX IF NOT EXISTS idx_brain_events_session_id
    ON brain.events (session_id);


-- ============================================================
-- brain.profile
-- Personal profile for the user. Key-value rows per dimension
-- so new dimensions can be added without schema changes.
-- Each field carries confidence (0.0-1.0), source tracking
-- (declared/inferred/confirmed), and timestamps for decay.
-- Embedding column enables semantic search ("what motivates me?").
-- ============================================================
CREATE TABLE IF NOT EXISTS brain.profile (
    id SERIAL PRIMARY KEY,
    category TEXT NOT NULL,
    field TEXT NOT NULL,
    value JSONB NOT NULL,
    confidence FLOAT DEFAULT 0.5,
    source TEXT DEFAULT 'declared' CHECK (source IN ('declared', 'inferred', 'confirmed')),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    embedding vector(768),
    UNIQUE(category, field)
);

-- HNSW index for semantic search over profile dimensions
CREATE INDEX IF NOT EXISTS idx_brain_profile_embedding
    ON brain.profile USING hnsw (embedding vector_cosine_ops);

-- B-tree on category for fast filtered lookups
CREATE INDEX IF NOT EXISTS idx_brain_profile_category
    ON brain.profile (category);


-- ============================================================
-- brain.modes
-- Session mode tracking: working, planning, capturing, reviewing.
-- One row per mode entry. Most recent row = current mode.
-- context_snapshot captures domain context at mode entry time.
-- ============================================================
CREATE TABLE IF NOT EXISTS brain.modes (
    id SERIAL PRIMARY KEY,
    session_id TEXT NOT NULL,
    mode TEXT NOT NULL CHECK (mode IN ('working', 'planning', 'capturing', 'reviewing')),
    entered_at TIMESTAMPTZ DEFAULT NOW(),
    context_snapshot JSONB DEFAULT '{}',
    triggered_by TEXT
);
