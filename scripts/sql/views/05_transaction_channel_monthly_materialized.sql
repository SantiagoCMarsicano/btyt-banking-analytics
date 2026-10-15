-- ============================================================
-- BTYT BANKING ANALYTICS
-- 05_transaction_channel_monthly_materialized.sql
-- Materialized monthly transaction/channel analytical layer for BI.
--
-- IMPORTANT:
-- - This is the canonical BI object.
-- - Power BI should consume analytics.transaction_channel_monthly_bi.
-- - analytics.transaction_channel_monthly MUST remain a MATERIALIZED VIEW.
--
-- Grain:
-- one month × customer type × channel × transaction type × direction
-- × transfer scope × currency
--
-- Sources:
-- banking.transactions
-- core.accounts
-- core.customers
-- core.products
--
-- Why materialized:
-- - The source transaction table contains ~76.8M rows.
-- - A normal view recomputes the full aggregation every time it is queried.
-- - The materialized view stores the aggregated result for fast BI consumption.
--
-- Refresh after source-data reload:
-- REFRESH MATERIALIZED VIEW analytics.transaction_channel_monthly;
-- ANALYZE analytics.transaction_channel_monthly;
-- ============================================================

-- The BI wrapper depends on the canonical object, so remove it first.
DROP VIEW IF EXISTS analytics.transaction_channel_monthly_bi;

-- Safely remove the canonical object whether an older execution left it
-- as a MATERIALIZED VIEW or accidentally as a normal VIEW.
DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM pg_matviews
        WHERE schemaname = 'analytics'
          AND matviewname = 'transaction_channel_monthly'
    ) THEN
        EXECUTE 'DROP MATERIALIZED VIEW analytics.transaction_channel_monthly';
    ELSIF EXISTS (
        SELECT 1
        FROM pg_views
        WHERE schemaname = 'analytics'
          AND viewname = 'transaction_channel_monthly'
    ) THEN
        EXECUTE 'DROP VIEW analytics.transaction_channel_monthly';
    END IF;
END $$;

CREATE MATERIALIZED VIEW analytics.transaction_channel_monthly AS
SELECT
    DATE_TRUNC('month', t.transaction_datetime)::DATE AS year_month,
    c.customer_type,
    t.channel,
    t.transaction_type,
    t.direction,
    t.transfer_scope,
    p.currency,

    -- Relationship coverage
    COUNT(DISTINCT t.account_id) AS distinct_accounts,
    COUNT(DISTINCT a.customer_id) AS distinct_customers,

    -- Operational activity
    COUNT(*) AS attempted_transaction_count,

    COUNT(*) FILTER (
        WHERE t.transaction_status = 'COMPLETED'
    ) AS completed_transaction_count,

    COUNT(*) FILTER (
        WHERE t.transaction_status = 'FAILED'
    ) AS failed_transaction_count,

    -- Realized economic volume
    SUM(t.amount) FILTER (
        WHERE t.transaction_status = 'COMPLETED'
    ) AS completed_transaction_volume,

    -- External transfer support
    COUNT(*) FILTER (
        WHERE t.transaction_status = 'COMPLETED'
          AND t.transaction_type IN ('TRANSFER_IN', 'TRANSFER_OUT')
          AND t.transfer_scope IN ('DOMESTIC_EXTERNAL', 'INTERNATIONAL')
    ) AS completed_external_transfer_count,

    COUNT(*) FILTER (
        WHERE t.transaction_status = 'COMPLETED'
          AND t.transaction_type IN ('TRANSFER_IN', 'TRANSFER_OUT')
          AND t.transfer_scope IN ('INTERNAL', 'DOMESTIC_EXTERNAL', 'INTERNATIONAL')
    ) AS completed_transfer_count

FROM banking.transactions AS t
INNER JOIN core.accounts AS a
    ON a.account_id = t.account_id
INNER JOIN core.customers AS c
    ON c.customer_id = a.customer_id
INNER JOIN core.products AS p
    ON p.product_id = a.product_id

GROUP BY
    DATE_TRUNC('month', t.transaction_datetime)::DATE,
    c.customer_type,
    t.channel,
    t.transaction_type,
    t.direction,
    t.transfer_scope,
    p.currency

WITH DATA;


-- BI-oriented indexes
CREATE INDEX IF NOT EXISTS idx_transaction_channel_monthly_year
    ON analytics.transaction_channel_monthly (year_month);

CREATE INDEX IF NOT EXISTS idx_transaction_channel_monthly_customer_type
    ON analytics.transaction_channel_monthly (customer_type);

CREATE INDEX IF NOT EXISTS idx_transaction_channel_monthly_channel
    ON analytics.transaction_channel_monthly (channel);

ANALYZE analytics.transaction_channel_monthly;


-- Stable Power BI wrapper.
CREATE VIEW analytics.transaction_channel_monthly_bi AS
SELECT *
FROM analytics.transaction_channel_monthly;


-- Data validation
SELECT
    COUNT(*) AS total_rows,
    MIN(year_month) AS first_month,
    MAX(year_month) AS last_month,
    COUNT(DISTINCT customer_type) AS customer_types,
    SUM(attempted_transaction_count) AS attempted_transactions,
    SUM(completed_transaction_count) AS completed_transactions,
    SUM(failed_transaction_count) AS failed_transactions
FROM analytics.transaction_channel_monthly;


-- Object-type validation: must return m / MATERIALIZED VIEW.
SELECT
    c.relkind,
    CASE c.relkind
        WHEN 'm' THEN 'MATERIALIZED VIEW'
        WHEN 'v' THEN 'VIEW'
        WHEN 'r' THEN 'TABLE'
        ELSE c.relkind::TEXT
    END AS object_type,
    pg_size_pretty(pg_relation_size(c.oid)) AS size
FROM pg_class AS c
INNER JOIN pg_namespace AS n
    ON n.oid = c.relnamespace
WHERE n.nspname = 'analytics'
  AND c.relname = 'transaction_channel_monthly';
