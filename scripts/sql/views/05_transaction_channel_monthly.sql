-- ============================================================
-- BTYT BANKING ANALYTICS
-- 05_transaction_channel_monthly.sql
-- Live (non-materialized) monthly transaction/channel analytical view.
--
-- PURPOSE:
-- - Reference / validation version of the transaction-channel aggregation.
-- - NOT intended as the Power BI source because it recomputes the aggregation
--   over banking.transactions on every query.
-- - Power BI should use analytics.transaction_channel_monthly_bi, which points
--   to the materialized object created by
--   05_transaction_channel_monthly_materialized.sql.
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
-- Notes:
-- - Transaction amounts are kept separated by product/account currency.
-- - FAILED transactions are operational attempts, not realized economic flows.
-- - Completed transaction volume therefore uses COMPLETED transactions only.
-- - Digital shares, failure rates and external-transfer shares are left for
--   downstream DAX so they react correctly to report filters.
-- - NULL transfer_scope is preserved for non-transfer transactions.
-- ============================================================

DROP VIEW IF EXISTS analytics.transaction_channel_monthly_live;

CREATE VIEW analytics.transaction_channel_monthly_live AS
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
    p.currency;


-- Validation
-- NOTE: this validation executes the live aggregation and can be slow
-- because the source contains ~76.8M transaction rows.
SELECT
    COUNT(*) AS total_rows,
    MIN(year_month) AS first_month,
    MAX(year_month) AS last_month,
    COUNT(DISTINCT customer_type) AS customer_types,
    SUM(attempted_transaction_count) AS attempted_transactions,
    SUM(completed_transaction_count) AS completed_transactions,
    SUM(failed_transaction_count) AS failed_transactions
FROM analytics.transaction_channel_monthly_live;


-- Object-type validation: must return v / VIEW.
SELECT
    c.relkind,
    CASE c.relkind
        WHEN 'v' THEN 'VIEW'
        WHEN 'm' THEN 'MATERIALIZED VIEW'
        WHEN 'r' THEN 'TABLE'
        ELSE c.relkind::TEXT
    END AS object_type
FROM pg_class AS c
INNER JOIN pg_namespace AS n
    ON n.oid = c.relnamespace
WHERE n.nspname = 'analytics'
  AND c.relname = 'transaction_channel_monthly_live';
