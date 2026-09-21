-- ============================================================
-- BTYT BANKING ANALYTICS
-- 07_market_performance_yearly.sql
-- Annual bank-level competitive and financial analytical view.
--
-- Grain:
-- one bank per year
--
-- Sources:
-- market.bank_market_weights
-- market.banks
-- market.bank_financials
--
-- Notes:
-- - Market weights are synthetic competitive-position measures.
-- - They must not be interpreted as real-world market shares.
-- - Financial values are synthetic bank-level annual figures.
-- - Ratios such as ROA, ROE, Cost-to-Income and YoY market-weight
--   change are intentionally left for downstream DAX.
-- - Simulation-internal latent-state fields are excluded from this
--   BI-facing view because they are generator mechanics rather than
--   management-facing analytical attributes.
-- ============================================================

DROP VIEW IF EXISTS analytics.market_performance_yearly;

CREATE VIEW analytics.market_performance_yearly AS
SELECT
    bmw.year,
    bmw.bank_id,

    -- Bank dimensions
    b.bank_name,
    b.bank_scope,
    b.bank_type,
    b.operating_country,
    b.bank_profile,
    b.bank_status,

    -- Synthetic market position
    bmw.market_weight,

    -- Annual financial performance
    bf.revenue,
    bf.operating_costs,
    bf.net_income,
    bf.total_assets,
    bf.total_deposits,
    bf.total_loans,
    bf.equity,
    bf.reporting_currency,

    -- Reusable BTYT flag
    CASE
        WHEN bmw.bank_id = 'B000' THEN 1
        ELSE 0
    END AS is_btyt

FROM market.bank_market_weights AS bmw
INNER JOIN market.banks AS b
    ON b.bank_id = bmw.bank_id
LEFT JOIN market.bank_financials AS bf
    ON bf.bank_id = bmw.bank_id
   AND bf.year = bmw.year;


-- Validation
SELECT
    COUNT(*) AS total_rows,
    COUNT(DISTINCT bank_id) AS distinct_banks,
    MIN(year) AS first_year,
    MAX(year) AS last_year,
    COUNT(*) FILTER (
        WHERE revenue IS NULL
           OR operating_costs IS NULL
           OR net_income IS NULL
           OR total_assets IS NULL
           OR total_deposits IS NULL
           OR total_loans IS NULL
           OR equity IS NULL
    ) AS incomplete_financial_rows
FROM analytics.market_performance_yearly;
