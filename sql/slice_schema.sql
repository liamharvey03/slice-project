
-- Slice Phase 2 Database Schema
-- Executable SQL only (no markdown or spec text)

-- CREATE EXTENSION IF NOT EXISTS vector;

-- ------------------------------------------------------------
-- 1. Market Price Data
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS market_data (
    ticker          VARCHAR(32) NOT NULL,
    date            DATE        NOT NULL,
    open            DOUBLE PRECISION,
    high            DOUBLE PRECISION,
    low             DOUBLE PRECISION,
    close           DOUBLE PRECISION,
    volume          DOUBLE PRECISION,
    PRIMARY KEY (ticker, date)
);

CREATE INDEX IF NOT EXISTS idx_market_data_ticker_date
    ON market_data (ticker, date);

-- ------------------------------------------------------------
-- 2. Economic Data (FRED, macro indicators)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS econ_data (
    series_id       VARCHAR(64) NOT NULL,
    date            DATE        NOT NULL,
    value           DOUBLE PRECISION,
    PRIMARY KEY (series_id, date)
);

CREATE INDEX IF NOT EXISTS idx_econ_data_series_date
    ON econ_data (series_id, date);
