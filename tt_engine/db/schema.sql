-- Part 12 — minimum tables. Kept deliberately small; the moat is the model
-- tuned to your own results (Part 13), not a sprawling schema.

CREATE TABLE IF NOT EXISTS products (
    id           TEXT PRIMARY KEY,
    name         TEXT NOT NULL,
    category     TEXT NOT NULL,
    supplier_ref TEXT,
    first_seen   TEXT NOT NULL,           -- ISO date the product entered our radar
    branded      INTEGER NOT NULL DEFAULT 0,  -- 1 = trademarked/branded (hard gate)
    restricted   INTEGER NOT NULL DEFAULT 0,  -- 1 = restricted TikTok category (hard gate)
    reviews      TEXT NOT NULL DEFAULT '[]'   -- JSON corpus feeding psychology + return-risk NLP
);

-- One row per product per day: the time series detection runs over.
CREATE TABLE IF NOT EXISTS product_daily_metrics (
    product_id   TEXT NOT NULL,
    date         TEXT NOT NULL,           -- ISO date
    units        INTEGER NOT NULL,        -- units sold that day
    gmv          REAL NOT NULL,           -- gross merch value that day
    price        REAL NOT NULL,           -- prevailing sell price
    sellers      INTEGER NOT NULL,        -- # of shops selling it
    promo_videos INTEGER NOT NULL,        -- # of promo videos live
    ads          INTEGER NOT NULL,        -- # of paid ads running
    avg_ad_age   REAL NOT NULL,           -- mean ad age in days (low = fresh entrants)
    PRIMARY KEY (product_id, date),
    FOREIGN KEY (product_id) REFERENCES products(id)
);

-- Part 3 — one scoring snapshot per product per day.
CREATE TABLE IF NOT EXISTS scores (
    product_id        TEXT NOT NULL,
    date              TEXT NOT NULL,
    viral_demo        REAL NOT NULL,      -- /20
    market_demand     REAL NOT NULL,      -- /20
    competition_timing REAL NOT NULL,     -- /15
    economics         REAL NOT NULL,      -- /20
    content_potential REAL NOT NULL,      -- /15
    brand_potential   REAL NOT NULL,      -- /10
    total             REAL NOT NULL,      -- /100
    gates_passed      INTEGER NOT NULL,   -- 1 = cleared all hard gates
    gate_failures     TEXT,               -- JSON list of failed gate names
    window_days       REAL,               -- runway estimate
    PRIMARY KEY (product_id, date),
    FOREIGN KEY (product_id) REFERENCES products(id)
);

-- Part 6 — supplier candidates and their scoring inputs.
CREATE TABLE IF NOT EXISTS suppliers (
    ref           TEXT PRIMARY KEY,
    product_id    TEXT,
    name          TEXT,
    cost          REAL NOT NULL,          -- unit cost (supplier price)
    ship_cost     REAL NOT NULL DEFAULT 0,
    ship_days     REAL NOT NULL,
    moq           INTEGER NOT NULL DEFAULT 1,
    us_warehouse  INTEGER NOT NULL DEFAULT 0,
    rating        REAL,                   -- 0..5
    response_hrs  REAL,
    quality_notes TEXT,
    FOREIGN KEY (product_id) REFERENCES products(id)
);

-- Part 7 — generated creative assets.
CREATE TABLE IF NOT EXISTS creatives (
    id          TEXT PRIMARY KEY,
    product_id  TEXT NOT NULL,
    format      TEXT NOT NULL,            -- UGC-Reaction | HyperMotion-Reveal | ASMR | POV-BeforeAfter | Unboxing
    hook        TEXT NOT NULL,
    hook_type   TEXT,                     -- curiosity | problem | shock | transformation
    soul_id     TEXT,                     -- recurring persona id (ONE per store)
    asset_url   TEXT,
    status      TEXT NOT NULL DEFAULT 'briefed',  -- briefed|generating|ready|exported|failed
    meta        TEXT NOT NULL DEFAULT '{}',       -- JSON: aigc_disclosure, format_tag, job_id…
    FOREIGN KEY (product_id) REFERENCES products(id)
);

-- Part 9 — per-creative test telemetry.
CREATE TABLE IF NOT EXISTS tests (
    id           TEXT PRIMARY KEY,
    creative_id  TEXT NOT NULL,
    date         TEXT NOT NULL,
    spend        REAL NOT NULL DEFAULT 0,
    impressions  INTEGER NOT NULL DEFAULT 0,
    three_sec_vr REAL,                    -- 3-second view rate (leading indicator)
    ctr          REAL,
    atc          REAL,                    -- add-to-cart rate
    cvr          REAL,
    roas         REAL,
    FOREIGN KEY (creative_id) REFERENCES creatives(id)
);

-- Part 13 — your own outcomes, fed back to recalibrate the weights.
CREATE TABLE IF NOT EXISTS results (
    product_id   TEXT NOT NULL,
    date         TEXT NOT NULL,
    net_margin   REAL,                    -- true net margin after fees + payouts
    refund_rate  REAL,
    roas         REAL,
    decision     TEXT,                    -- kill | scale | watch
    PRIMARY KEY (product_id, date),
    FOREIGN KEY (product_id) REFERENCES products(id)
);

-- Audit trail for CSV imports (Kalodata / FastMoss / manual exports).
CREATE TABLE IF NOT EXISTS import_log (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    source        TEXT NOT NULL,          -- kalodata | fastmoss | generic
    filename      TEXT,
    products      INTEGER NOT NULL DEFAULT 0,
    metric_rows   INTEGER NOT NULL DEFAULT 0,
    rows_skipped  INTEGER NOT NULL DEFAULT 0,
    imported_at   TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_metrics_date ON product_daily_metrics(date);
CREATE INDEX IF NOT EXISTS idx_scores_total ON scores(total);
