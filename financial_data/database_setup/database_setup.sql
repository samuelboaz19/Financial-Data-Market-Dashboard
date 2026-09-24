-- ============================================================
-- Financial Data / Market Dashboard
-- TimescaleDB Database Setup
-- ============================================================

-- Verify the database
SELECT current_database();

-- ============================================================
-- 1. Crypto / market tick data
-- ============================================================

CREATE TABLE crypto_ticks (
"time" TIMESTAMPTZ,
symbol TEXT,
price DOUBLE PRECISION,
day_volume NUMERIC
)
WITH (
tsdb.hypertable,
tsdb.segmentby = 'symbol',
tsdb.orderby = 'time DESC'
);

-- Verify the database
SELECT current_database();

-- ============================================================
-- 2. Asset reference table
-- ============================================================

CREATE TABLE crypto_assets (
symbol TEXT UNIQUE,
"name" TEXT
);

INSERT INTO crypto_assets (symbol, name)
VALUES
('BTC/USD', 'Bitcoin'),
('ETH/USD', 'Ethereum'),
('AAPL', 'Apple Inc.'),
('MSFT', 'Microsoft Corporation');

-- Verify assets
SELECT * FROM crypto_assets;

-- ============================================================
-- 3. Daily OHLC continuous aggregate
-- ============================================================

CREATE MATERIALIZED VIEW one_day_candle
WITH (timescaledb.continuous) AS
SELECT
time_bucket('1 day', "time") AS bucket,
symbol,
FIRST(price, "time") AS "open",
MAX(price) AS high,
MIN(price) AS low,
LAST(price, "time") AS "close",
LAST(day_volume, "time") AS day_volume
FROM crypto_ticks
GROUP BY bucket, symbol;

-- ============================================================
-- 4. Continuous aggregate refresh policy
-- ============================================================

SELECT add_continuous_aggregate_policy(
'one_day_candle',
start_offset => INTERVAL '3 days',
end_offset => INTERVAL '1 day',
schedule_interval => INTERVAL '1 day'
);
