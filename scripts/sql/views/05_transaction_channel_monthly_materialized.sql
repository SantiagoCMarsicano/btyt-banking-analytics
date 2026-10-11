-- ============================================================
-- BTYT BANKING ANALYTICS
-- 05_transaction_channel_monthly_materialized.sql
-- Materialized monthly transaction/channel analytical layer.
--
-- Grain:
-- one month × channel × transaction type × direction × transfer scope × currency
--
-- Sources:
-- banking.transactions
-- core.accounts
-- core.products
--
-- Why materialized:
-- - The source transaction table contains ~76.8M rows.
-- - A normal view recomputes the full aggregation every time it is queried.
-- - The materialized view stores the aggregated result for fast BI consumption.
--
-- Refresh:
-- REFRESH MATERIALIZED VIEW analytics.transaction_channel_monthly;
-- ============================================================

DROP VIEW IF EXISTS analytics.transaction_channel_monthly;
DROP MATERIALIZED VIEW IF EXISTS analytics.transaction_channel_monthly;

CREATE MATERIALIZED VIEW analytics.transaction_channel_monthly AS
SELECT
    DATE_TRUNC('month', t.transaction_datetime)::DATE AS year_month,
    t.channel,
    t.transaction_type,
    t.direction,
    t.transfer_scope,
    p.currency,

    COUNT(DISTINCT t.account_id) AS distinct_accounts,
    COUNT(DISTINCT a.customer_id) AS distinct_customers,

    COUNT(*) AS attempted_transaction_count,

    COUNT(*) FILTER (
        WHERE t.transaction_status = 'COMPLETED'
    ) AS completed_transaction_count,

    COUNT(*) FILTER (
        WHERE t.transaction_status = 'FAILED'
    ) AS failed_transaction_count,

    SUM(t.amount) FILTER (
        WHERE t.transaction_status = 'COMPLETED'
    ) AS completed_transaction_volume,

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
INNER JOIN core.products AS p
    ON p.product_id = a.product_id

GROUP BY
    DATE_TRUNC('month', t.transaction_datetime)::DATE,
    t.channel,
    t.transaction_type,
    t.direction,
    t.transfer_scope,
    p.currency

WITH DATA;

CREATE INDEX IF NOT EXISTS idx_transaction_channel_monthly_year
    ON analytics.transaction_channel_monthly (year_month);

CREATE INDEX IF NOT EXISTS idx_transaction_channel_monthly_channel
    ON analytics.transaction_channel_monthly (channel);

SELECT
    COUNT(*) AS total_rows,
    MIN(year_month) AS first_month,
    MAX(year_month) AS last_month,
    SUM(attempted_transaction_count) AS attempted_transactions,
    SUM(completed_transaction_count) AS completed_transactions,
    SUM(failed_transaction_count) AS failed_transactions
FROM analytics.transaction_channel_monthly;

CREATE VIEW analytics.transaction_channel_monthly_bi AS
SELECT *
FROM analytics.transaction_channel_monthly;
