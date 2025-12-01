-- ============================================
-- Phase E4 Tables: Thesis Evaluation, Alerts, Daily Summary
-- ============================================

-- ===========================
-- 1. Thesis Evaluation
-- ===========================
CREATE TABLE IF NOT EXISTS thesis_evaluation (
    thesis_id TEXT PRIMARY KEY,
    evaluation JSONB NOT NULL,
    review JSONB NOT NULL,
    evaluated_at TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_thesis_evaluation_evaluated_at
    ON thesis_evaluation (evaluated_at DESC);

-- ===========================
-- 2. Alert
-- ===========================
CREATE TABLE IF NOT EXISTS alert (
    id TEXT PRIMARY KEY,
    thesis_id TEXT NOT NULL,
    thesis_title TEXT NOT NULL,
    message TEXT NOT NULL,
    observation_id TEXT,
    timestamp TIMESTAMPTZ NOT NULL,
    date DATE NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_alert_date
    ON alert (date DESC);

CREATE INDEX IF NOT EXISTS idx_alert_thesis_id
    ON alert (thesis_id);

-- ===========================
-- 3. Daily Summary
-- ===========================
CREATE TABLE IF NOT EXISTS daily_summary (
    date DATE PRIMARY KEY,
    summary JSONB NOT NULL
);

