-- ============================================
-- Phase 4 Tables: Thesis, Observation, Trade, Scenario
-- Postgres + pgvector (extension must be installed)
-- ============================================

CREATE EXTENSION IF NOT EXISTS vector;

-- ===========================
-- 1. Thesis
-- ===========================
CREATE TABLE IF NOT EXISTS thesis (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    hypothesis TEXT NOT NULL,
    drivers JSONB NOT NULL,
    disconfirmers JSONB NOT NULL,
    expression JSONB NOT NULL,
    start_date DATE NOT NULL,
    review_date DATE,
    status TEXT NOT NULL,
    tags JSONB NOT NULL,
    monitor_indices JSONB NOT NULL,
    notes TEXT
);

-- ===========================
-- 2. Observation
-- ===========================
CREATE TABLE IF NOT EXISTS observation (
    id TEXT PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL,
    text TEXT NOT NULL,
    thesis_ref TEXT[],
    sentiment TEXT NOT NULL,
    categories TEXT[] NOT NULL,
    actionable TEXT NOT NULL,
    embedding VECTOR(1536)  -- pgvector
);

-- Vector index for semantic search
CREATE INDEX IF NOT EXISTS observation_embedding_idx
    ON observation USING ivfflat (embedding vector_l2_ops)
    WITH (lists = 100);

-- ===========================
-- 3. Trade
-- ===========================
CREATE TABLE IF NOT EXISTS trade (
    trade_id TEXT PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL,
    asset TEXT NOT NULL,
    action TEXT NOT NULL,
    quantity DOUBLE PRECISION NOT NULL,
    price DOUBLE PRECISION NOT NULL,
    type TEXT NOT NULL,
    thesis_ref TEXT,
    notes TEXT
);

-- ===========================
-- 4. Scenario
-- ===========================
CREATE TABLE IF NOT EXISTS scenario (
    scenario_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    assumptions JSONB NOT NULL,
    expected_impact JSONB NOT NULL,
    description TEXT NOT NULL
);