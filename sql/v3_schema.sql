-- ===========================================
-- V3 Schema Migration
-- ===========================================

-- 1. Extend thesis table
ALTER TABLE thesis ADD COLUMN IF NOT EXISTS status VARCHAR(20) DEFAULT 'DRAFT';
ALTER TABLE thesis ADD COLUMN IF NOT EXISTS risk_rails JSONB;
ALTER TABLE thesis ADD COLUMN IF NOT EXISTS final_size FLOAT;

-- 2. Create thesis_snapshot table
CREATE TABLE IF NOT EXISTS thesis_snapshot (
    id TEXT PRIMARY KEY,
    thesis_id TEXT NOT NULL REFERENCES thesis(id),
    snapshot_type VARCHAR(20) NOT NULL,  -- pre_critique | post_critique | activation
    content JSONB NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_thesis_snapshot_thesis ON thesis_snapshot(thesis_id);
CREATE INDEX IF NOT EXISTS idx_thesis_snapshot_type ON thesis_snapshot(thesis_id, snapshot_type);

-- 3. Create logic_validation table
CREATE TABLE IF NOT EXISTS logic_validation (
    id TEXT PRIMARY KEY,
    thesis_id TEXT NOT NULL REFERENCES thesis(id),
    links JSONB NOT NULL,  -- Array of LogicLink objects
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_logic_validation_thesis ON logic_validation(thesis_id);

-- 4. Create backtest_result table
CREATE TABLE IF NOT EXISTS backtest_result (
    id TEXT PRIMARY KEY,
    thesis_id TEXT NOT NULL REFERENCES thesis(id),
    expression JSONB NOT NULL,
    period_start DATE NOT NULL,
    period_end DATE NOT NULL,
    metrics JSONB NOT NULL,
    equity_curve JSONB NOT NULL,
    factor_exposure JSONB,
    iteration_count INT DEFAULT 1,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_backtest_result_thesis ON backtest_result(thesis_id);
CREATE INDEX IF NOT EXISTS idx_backtest_result_created ON backtest_result(thesis_id, created_at DESC);

-- 5. Create critique_session table (for conversation history)
CREATE TABLE IF NOT EXISTS critique_session (
    id TEXT PRIMARY KEY,
    thesis_id TEXT NOT NULL REFERENCES thesis(id),
    conversation JSONB NOT NULL,  -- Array of {role, content, timestamp}
    status VARCHAR(20) DEFAULT 'active',  -- active | completed
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_critique_session_thesis ON critique_session(thesis_id);
