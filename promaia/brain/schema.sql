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

-- Notification routing columns (07-01: Event Bus)
-- Nullable so existing events are unaffected
ALTER TABLE brain.events ADD COLUMN IF NOT EXISTS
    urgency TEXT CHECK (urgency IN ('interrupt', 'digest', 'archive'));

ALTER TABLE brain.events ADD COLUMN IF NOT EXISTS
    routed_at TIMESTAMPTZ;

ALTER TABLE brain.events ADD COLUMN IF NOT EXISTS
    channel TEXT;

ALTER TABLE brain.events ADD COLUMN IF NOT EXISTS
    held_until TIMESTAMPTZ;

-- Partial index for the router's polling query: find unrouted events with urgency
CREATE INDEX IF NOT EXISTS idx_brain_events_unrouted
    ON brain.events (created_at ASC)
    WHERE urgency IS NOT NULL AND routed_at IS NULL;


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


-- ============================================================
-- brain.onboarding_sessions
-- Tracks onboarding session lifecycle: active, paused, complete.
-- Supports multi-session, pausable onboarding experiences.
-- metadata JSONB stores arc phase, preferences, etc.
-- ============================================================
CREATE TABLE IF NOT EXISTS brain.onboarding_sessions (
    id SERIAL PRIMARY KEY,
    user_id TEXT DEFAULT 'default',
    status TEXT DEFAULT 'active' CHECK (status IN ('active', 'paused', 'complete')),
    started_at TIMESTAMPTZ DEFAULT NOW(),
    last_activity TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    metadata JSONB DEFAULT '{}'
);

-- B-tree index for user lookup
CREATE INDEX IF NOT EXISTS idx_brain_onboarding_sessions_user_id
    ON brain.onboarding_sessions (user_id);


-- ============================================================
-- brain.onboarding_progress
-- Per-channel progress within an onboarding session.
-- Channels: interview, pc_scan, gmail, photos.
-- Tracks status, timing, and how many profile fields each channel contributed.
-- ============================================================
CREATE TABLE IF NOT EXISTS brain.onboarding_progress (
    id SERIAL PRIMARY KEY,
    session_id INTEGER REFERENCES brain.onboarding_sessions(id) NOT NULL,
    channel TEXT NOT NULL,
    status TEXT DEFAULT 'not_started' CHECK (status IN ('not_started', 'in_progress', 'complete', 'skipped')),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    fields_populated INTEGER DEFAULT 0,
    notes TEXT,
    UNIQUE(session_id, channel)
);

-- B-tree index for session lookup
CREATE INDEX IF NOT EXISTS idx_brain_onboarding_progress_session_id
    ON brain.onboarding_progress (session_id);


-- ============================================================
-- brain.timeline
-- Reference timeline of life events — biographical anchors for
-- contextual memory. Stores major milestones, moves, relationships,
-- career changes, etc. with optional fuzzy dating (month/year).
-- Used by briefings ("3 years ago today...") and for understanding
-- what shaped the user's current situation.
-- ============================================================
CREATE TABLE IF NOT EXISTS brain.timeline (
    id SERIAL PRIMARY KEY,
    event_date DATE NOT NULL,
    date_precision TEXT DEFAULT 'day' CHECK (date_precision IN ('day', 'month', 'year')),
    title TEXT NOT NULL,
    description TEXT,
    category TEXT DEFAULT 'life' CHECK (category IN (
        'life', 'career', 'relationship', 'education',
        'health', 'location', 'project', 'milestone'
    )),
    significance INTEGER DEFAULT 5 CHECK (significance BETWEEN 1 AND 10),
    domain TEXT,
    tags TEXT[] DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- B-tree on event_date for chronological queries and anniversary detection
CREATE INDEX IF NOT EXISTS idx_brain_timeline_event_date
    ON brain.timeline (event_date);

-- B-tree on category for filtered lookups
CREATE INDEX IF NOT EXISTS idx_brain_timeline_category
    ON brain.timeline (category);


-- ============================================================
-- brain.agent_costs
-- Per-API-call cost tracking for agent executions.
-- Every generate_content call logs model, token counts,
-- cached/thinking tokens, and computed USD cost.
-- Used by CostTracker (promaia/agents/cost_tracker.py)
-- and brain_costs MCP tool for user-facing spend visibility.
-- ============================================================
CREATE TABLE IF NOT EXISTS brain.agent_costs (
    id SERIAL PRIMARY KEY,
    execution_id INTEGER REFERENCES agent_executions(id),
    agent_name TEXT NOT NULL,
    model_id TEXT NOT NULL,
    task_type TEXT,
    input_tokens INTEGER DEFAULT 0,
    output_tokens INTEGER DEFAULT 0,
    cached_tokens INTEGER DEFAULT 0,
    thinking_tokens INTEGER DEFAULT 0,
    cost_usd REAL NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index for per-agent cost queries (e.g., "how much did morning-briefing cost?")
CREATE INDEX IF NOT EXISTS idx_agent_costs_agent
    ON brain.agent_costs (agent_name, created_at DESC);

-- Index for daily/weekly cost summaries
CREATE INDEX IF NOT EXISTS idx_agent_costs_date
    ON brain.agent_costs (created_at DESC);

-- Index for per-run cost queries
CREATE INDEX IF NOT EXISTS idx_agent_costs_execution
    ON brain.agent_costs (execution_id);


-- ============================================================
-- brain.conversations
-- Ephemeral session history for continuity. Every user and
-- assistant message is stored here. High-impact messages
-- graduate to brain.memories via promote_message_to_memory().
-- ============================================================
CREATE TABLE IF NOT EXISTS brain.conversations (
    id SERIAL PRIMARY KEY,
    chat_id BIGINT NOT NULL,
    session_id TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content TEXT NOT NULL,
    impact_score REAL DEFAULT 0.0,
    promoted BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_conversations_chat_session
    ON brain.conversations (chat_id, session_id, created_at ASC);

CREATE INDEX IF NOT EXISTS idx_conversations_chat_recent
    ON brain.conversations (chat_id, created_at DESC);


-- ============================================================
-- brain.conversation_sessions
-- Tracks session lifecycle and synthesis state. A session groups
-- messages by time proximity (gap_minutes threshold). Synthesis
-- produces a summary memory when a session goes quiet.
-- ============================================================
CREATE TABLE IF NOT EXISTS brain.conversation_sessions (
    id SERIAL PRIMARY KEY,
    chat_id BIGINT NOT NULL,
    session_id TEXT NOT NULL UNIQUE,
    started_at TIMESTAMPTZ DEFAULT NOW(),
    last_message_at TIMESTAMPTZ DEFAULT NOW(),
    message_count INTEGER DEFAULT 0,
    synthesized BOOLEAN DEFAULT FALSE,
    synthesized_at TIMESTAMPTZ,
    synthesis_memory_id INTEGER REFERENCES brain.memories(id)
);

CREATE INDEX IF NOT EXISTS idx_conv_sessions_chat
    ON brain.conversation_sessions (chat_id, started_at DESC);
