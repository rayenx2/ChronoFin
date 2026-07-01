-- Stock AI Pipeline — PostgreSQL schema
-- Run once on first startup via docker-entrypoint-initdb.d

CREATE DATABASE stockai;
\c stockai;

-- Raw prices (star schema fact table)
CREATE TABLE IF NOT EXISTS stock_prices (
    id              BIGSERIAL PRIMARY KEY,
    symbol          VARCHAR(10)     NOT NULL,
    date            DATE            NOT NULL,
    open            NUMERIC(12, 4),
    high            NUMERIC(12, 4),
    low             NUMERIC(12, 4),
    close           NUMERIC(12, 4),
    adjusted_close  NUMERIC(12, 4),
    volume          BIGINT,
    daily_return    NUMERIC(10, 6),
    vwap            NUMERIC(12, 4),
    price_range     NUMERIC(12, 4),
    ingested_at     TIMESTAMPTZ     DEFAULT NOW(),
    processed_at    TIMESTAMPTZ,
    UNIQUE (symbol, date)
);

-- Technical indicators
CREATE TABLE IF NOT EXISTS technical_indicators (
    id          BIGSERIAL PRIMARY KEY,
    symbol      VARCHAR(10)     NOT NULL,
    date        DATE            NOT NULL,
    rsi_14      NUMERIC(8, 4),
    macd        NUMERIC(12, 6),
    macd_signal NUMERIC(12, 6),
    macd_hist   NUMERIC(12, 6),
    bb_upper    NUMERIC(12, 4),
    bb_lower    NUMERIC(12, 4),
    bb_width    NUMERIC(10, 6),
    atr_14      NUMERIC(12, 4),
    return_1d   NUMERIC(10, 6),
    return_5d   NUMERIC(10, 6),
    UNIQUE (symbol, date)
);

-- ML predictions
CREATE TABLE IF NOT EXISTS predictions (
    id                  BIGSERIAL PRIMARY KEY,
    symbol              VARCHAR(10)     NOT NULL,
    prediction_date     DATE            NOT NULL,
    predicted_price     NUMERIC(12, 4)  NOT NULL,
    confidence_lower    NUMERIC(12, 4),
    confidence_upper    NUMERIC(12, 4),
    confidence_score    NUMERIC(5, 4),
    model_version       VARCHAR(50),
    sentiment_score     NUMERIC(6, 4),
    sentiment_label     VARCHAR(20),
    created_at          TIMESTAMPTZ     DEFAULT NOW(),
    UNIQUE (symbol, prediction_date, model_version)
);

-- Sentiment signals
CREATE TABLE IF NOT EXISTS sentiment (
    id                      BIGSERIAL PRIMARY KEY,
    symbol                  VARCHAR(10)     NOT NULL,
    date                    DATE            NOT NULL,
    sentiment_compound      NUMERIC(6, 4),
    sentiment_positive      NUMERIC(6, 4),
    sentiment_negative      NUMERIC(6, 4),
    article_count           INTEGER,
    created_at              TIMESTAMPTZ     DEFAULT NOW(),
    UNIQUE (symbol, date)
);

-- Pipeline run log
CREATE TABLE IF NOT EXISTS pipeline_runs (
    id              BIGSERIAL PRIMARY KEY,
    dag_id          VARCHAR(100)    NOT NULL,
    run_id          VARCHAR(200)    NOT NULL,
    status          VARCHAR(20)     NOT NULL,
    rows_processed  INTEGER,
    started_at      TIMESTAMPTZ,
    completed_at    TIMESTAMPTZ,
    error_message   TEXT
);

-- Indexes
CREATE INDEX idx_stock_prices_symbol_date ON stock_prices (symbol, date DESC);
CREATE INDEX idx_predictions_symbol_date  ON predictions  (symbol, prediction_date DESC);
CREATE INDEX idx_sentiment_symbol_date    ON sentiment    (symbol, date DESC);
