-- ============================================================
-- BTYT — TRANSACTIONS & CHANNELS ANALYTICS
-- File: 04_transactions.sql
-- Audited architecture-aligned revision
--
-- Purpose:
-- Prepare scalable reusable transaction aggregates from BTYT's
-- largest Part I fact table while separating attempted activity
-- from economically completed money movement.
--
-- PostgreSQL | Read-only analytical queries
-- ============================================================
--
-- MAIN QUESTION
-- How does money move through BTYT, through which channels and
-- transaction types, and what efficient analytical grains should
-- downstream tools use?
--
-- IMPORTANT SCALE NOTE
-- banking.transactions contains tens of millions of rows.
--
-- Do NOT run this entire file blindly every time.
-- Run sections selectively and benchmark recurring heavy queries
-- before deciding whether to persist/materialize them.
--
-- ============================================================
-- 00. CORE TRANSACTION SEMANTICS — READ BEFORE USING
-- ============================================================
--
-- STATUS SEMANTICS
--
-- COMPLETED
--   The transaction actually executed and therefore represents
--   realized account activity / money movement.
--
-- FAILED
--   The transaction was attempted but did not execute.
--   Its amount is an attempted amount, not realized money movement.
--
-- Therefore:
--
-- - operational activity may use attempted + failed counts;
-- - financial transaction volume should normally use COMPLETED only;
-- - Failure Rate = failed attempts / all attempts;
-- - failed amounts must not be mixed into completed transaction value.
--
-- MONETARY RULE
-- banking.transactions does not store currency directly.
-- Currency is inherited from the account's product.
--
-- Never combine UYU and USD transaction amounts as one monetary total
-- unless an explicit FX conversion is introduced.
--
-- CHANNEL GROUPING USED IN THIS FILE
--
-- DIGITAL    = MOBILE + WEB
-- PHYSICAL   = BRANCH + ATM
-- AUTOMATED  = AUTOMATIC
-- MERCHANT   = POS
-- OTHER      = any future/unmapped value
--
-- This grouping is reusable analytical semantics. Detailed channel
-- values remain available and should not be discarded.
--
-- PHYSICAL BRANCH ACTIVITY RULE
-- The performance engine's branch_transaction_count corresponds to
-- COMPLETED transactions with channel = 'BRANCH' and a non-NULL
-- transaction_branch_id.
--
-- COUNTERPARTY RULE
--
-- banking.transactions.counterparty_institution_id
--      ↓
-- market.financial_institutions.institution_id
--      ↓
-- market.banks.bank_id
--
-- Do not replace this with a direct transaction-to-bank join because
-- counterparties can include non-bank institutions.
--
-- MERCHANT CATEGORY
-- merchant_category is applicable to merchant-related account activity,
-- especially DEBIT_PURCHASE. Analyze it only where populated and keep
-- NULL as structurally meaningful for non-merchant transactions.
--
-- ============================================================
-- 01. DOMAIN INVENTORY — SELECTIVE / ONE-TIME EXPLORATION
-- ============================================================
--
-- Each query below scans the large fact table. Run only the domain you
-- actually need to inspect; these are discovery queries, not dashboard
-- sources.


-- 1.1 Transaction types.

SELECT
    t.transaction_type,
    COUNT(*) AS attempted_transaction_count,
    COUNT(*) FILTER (
        WHERE t.transaction_status = 'COMPLETED'
    ) AS completed_transaction_count,
    COUNT(*) FILTER (
        WHERE t.transaction_status = 'FAILED'
    ) AS failed_transaction_count
FROM banking.transactions AS t
GROUP BY t.transaction_type
ORDER BY attempted_transaction_count DESC;


-- 1.2 Directions.

SELECT
    t.direction,
    COUNT(*) AS attempted_transaction_count,
    COUNT(*) FILTER (
        WHERE t.transaction_status = 'COMPLETED'
    ) AS completed_transaction_count
FROM banking.transactions AS t
GROUP BY t.direction
ORDER BY attempted_transaction_count DESC;


-- 1.3 Channels.

SELECT
    t.channel,
    CASE
        WHEN t.channel IN ('MOBILE', 'WEB') THEN 'DIGITAL'
        WHEN t.channel IN ('BRANCH', 'ATM') THEN 'PHYSICAL'
        WHEN t.channel = 'AUTOMATIC' THEN 'AUTOMATED'
        WHEN t.channel = 'POS' THEN 'MERCHANT'
        ELSE 'OTHER'
    END AS channel_group,
    COUNT(*) AS attempted_transaction_count,
    COUNT(*) FILTER (
        WHERE t.transaction_status = 'COMPLETED'
    ) AS completed_transaction_count,
    COUNT(*) FILTER (
        WHERE t.transaction_status = 'FAILED'
    ) AS failed_transaction_count
FROM banking.transactions AS t
GROUP BY
    t.channel,
    CASE
        WHEN t.channel IN ('MOBILE', 'WEB') THEN 'DIGITAL'
        WHEN t.channel IN ('BRANCH', 'ATM') THEN 'PHYSICAL'
        WHEN t.channel = 'AUTOMATIC' THEN 'AUTOMATED'
        WHEN t.channel = 'POS' THEN 'MERCHANT'
        ELSE 'OTHER'
    END
ORDER BY attempted_transaction_count DESC;


-- 1.4 Transaction status / failure reason combinations.

SELECT
    t.transaction_status,
    COALESCE(t.failure_reason, 'NO_FAILURE_REASON') AS failure_reason,
    COUNT(*) AS transaction_count
FROM banking.transactions AS t
GROUP BY
    t.transaction_status,
    COALESCE(t.failure_reason, 'NO_FAILURE_REASON')
ORDER BY
    t.transaction_status,
    transaction_count DESC;


-- 1.5 Transfer scopes.
-- NULL is structurally valid for transactions where transfer scope
-- does not apply.

SELECT
    COALESCE(t.transfer_scope, 'NOT_APPLICABLE') AS transfer_scope,
    COUNT(*) AS attempted_transaction_count,
    COUNT(*) FILTER (
        WHERE t.transaction_status = 'COMPLETED'
    ) AS completed_transaction_count
FROM banking.transactions AS t
GROUP BY COALESCE(t.transfer_scope, 'NOT_APPLICABLE')
ORDER BY attempted_transaction_count DESC;


-- 1.6 Counterparty types.

SELECT
    COALESCE(t.counterparty_type, 'NOT_APPLICABLE') AS counterparty_type,
    COUNT(*) AS attempted_transaction_count,
    COUNT(*) FILTER (
        WHERE t.transaction_status = 'COMPLETED'
    ) AS completed_transaction_count
FROM banking.transactions AS t
GROUP BY COALESCE(t.counterparty_type, 'NOT_APPLICABLE')
ORDER BY attempted_transaction_count DESC;


-- ============================================================
-- 02. TEMPORAL COVERAGE — SQL DIAGNOSTIC
-- ============================================================

-- 2.1 Event-table coverage.
-- COUNT(*) and COUNT(DISTINCT) require substantial work on this table.

SELECT
    MIN(t.transaction_datetime) AS first_transaction_datetime,
    MAX(t.transaction_datetime) AS last_transaction_datetime,
    COUNT(*) AS attempted_transaction_rows,
    COUNT(*) FILTER (
        WHERE t.transaction_status = 'COMPLETED'
    ) AS completed_transaction_rows,
    COUNT(*) FILTER (
        WHERE t.transaction_status = 'FAILED'
    ) AS failed_transaction_rows,
    COUNT(DISTINCT t.account_id) AS accounts_with_attempts
FROM banking.transactions AS t;


-- 2.2 Monthly event coverage.

SELECT
    DATE_TRUNC('month', t.transaction_datetime)::DATE AS year_month,
    COUNT(*) AS attempted_transaction_count,
    COUNT(*) FILTER (
        WHERE t.transaction_status = 'COMPLETED'
    ) AS completed_transaction_count,
    COUNT(*) FILTER (
        WHERE t.transaction_status = 'FAILED'
    ) AS failed_transaction_count
FROM banking.transactions AS t
GROUP BY DATE_TRUNC('month', t.transaction_datetime)::DATE
ORDER BY year_month;


-- ============================================================
-- 03. ACCOUNT-MONTH TRANSACTION BASE — SQL PREPARATION
-- ============================================================
--
-- Principal reusable transaction layer for Power BI.
--
-- Grain:
-- 1 row =
-- account
-- × month
-- × transaction_type
-- × direction
-- × channel
-- × transfer_scope
--
-- transaction_status is intentionally NOT part of the grain.
-- Instead, attempted/completed/failed metrics coexist in the same row.
-- This prevents users from accidentally summing failed amounts as
-- realized transaction value.
--
-- Strategy:
-- 1. Aggregate the large fact table first.
-- 2. Join smaller dimensions afterward.

WITH transaction_aggregate AS (
    SELECT
        t.account_id,
        DATE_TRUNC('month', t.transaction_datetime)::DATE AS year_month,
        t.transaction_type,
        t.direction,
        t.channel,
        t.transfer_scope,

        COUNT(*) AS attempted_transaction_count,

        COUNT(*) FILTER (
            WHERE t.transaction_status = 'COMPLETED'
        ) AS completed_transaction_count,

        COUNT(*) FILTER (
            WHERE t.transaction_status = 'FAILED'
        ) AS failed_transaction_count,

        SUM(t.amount) AS attempted_transaction_amount,

        SUM(t.amount) FILTER (
            WHERE t.transaction_status = 'COMPLETED'
        ) AS completed_transaction_amount,

        SUM(t.amount) FILTER (
            WHERE t.transaction_status = 'FAILED'
        ) AS failed_transaction_amount,

        AVG(t.amount) FILTER (
            WHERE t.transaction_status = 'COMPLETED'
        ) AS avg_completed_transaction_amount,

        COUNT(*) FILTER (
            WHERE t.transaction_status = 'COMPLETED'
              AND t.channel = 'BRANCH'
              AND t.transaction_branch_id IS NOT NULL
        ) AS completed_branch_transaction_count

    FROM banking.transactions AS t

    GROUP BY
        t.account_id,
        DATE_TRUNC('month', t.transaction_datetime)::DATE,
        t.transaction_type,
        t.direction,
        t.channel,
        t.transfer_scope
)

SELECT
    ta.account_id,
    ta.year_month,
    ta.transaction_type,
    ta.direction,
    ta.channel,

    CASE
        WHEN ta.channel IN ('MOBILE', 'WEB') THEN 'DIGITAL'
        WHEN ta.channel IN ('BRANCH', 'ATM') THEN 'PHYSICAL'
        WHEN ta.channel = 'AUTOMATIC' THEN 'AUTOMATED'
        WHEN ta.channel = 'POS' THEN 'MERCHANT'
        ELSE 'OTHER'
    END AS channel_group,

    ta.transfer_scope,

    ta.attempted_transaction_count,
    ta.completed_transaction_count,
    ta.failed_transaction_count,

    ROUND(
        COALESCE(ta.attempted_transaction_amount, 0)::NUMERIC,
        2
    ) AS attempted_transaction_amount,

    ROUND(
        COALESCE(ta.completed_transaction_amount, 0)::NUMERIC,
        2
    ) AS completed_transaction_amount,

    ROUND(
        COALESCE(ta.failed_transaction_amount, 0)::NUMERIC,
        2
    ) AS failed_transaction_amount,

    ROUND(
        ta.avg_completed_transaction_amount::NUMERIC,
        2
    ) AS avg_completed_transaction_amount,

    ROUND(
        (
            100.0 * ta.failed_transaction_count
            / NULLIF(ta.attempted_transaction_count, 0)
        )::NUMERIC,
        2
    ) AS failure_rate_pct,

    ta.completed_branch_transaction_count,

    a.customer_id,
    a.product_id,
    a.branch_id AS account_branch_id,
    a.account_status AS account_status_at_cutoff,
    a.opening_year,
    a.closing_year,
    a.opening_channel,

    p.product_name,
    p.product_family,
    p.currency,

    c.customer_type,

    CASE
        WHEN c.customer_type = 'INDIVIDUAL'
            THEN COALESCE(c.employment_status, 'UNKNOWN')
        WHEN c.customer_type = 'BUSINESS'
            THEN COALESCE(c.company_size, 'UNKNOWN')
        ELSE 'UNKNOWN'
    END AS customer_segment,

    b.branch_name AS account_branch_name,
    b.department AS account_branch_department,
    b.region AS account_branch_region

FROM transaction_aggregate AS ta

JOIN core.accounts AS a
    ON a.account_id = ta.account_id

JOIN core.products AS p
    ON p.product_id = a.product_id

JOIN core.customers AS c
    ON c.customer_id = a.customer_id

JOIN core.branches AS b
    ON b.branch_id = a.branch_id;


-- ============================================================
-- 04. PHYSICAL BRANCH-MONTH TRANSACTION BASE — SQL PREPARATION
-- ============================================================
--
-- This definition intentionally matches the performance engine:
-- COMPLETED + channel = BRANCH + transaction_branch_id present.
--
-- Grain:
-- 1 row = physical transaction branch × month × currency
--
-- Currency remains explicit; UYU and USD are not added together here.
-- Counts can be compared with performance.branch_transaction_count; monetary
-- amounts cannot reconcile directly to performance.transaction_volume until
-- converted to the performance engine's UYU-equivalent reporting currency.

WITH branch_transactions AS (
    SELECT
        t.transaction_branch_id AS branch_id,
        DATE_TRUNC('month', t.transaction_datetime)::DATE AS year_month,
        p.currency,

        COUNT(*) AS completed_branch_transaction_count,
        SUM(t.amount) AS completed_branch_transaction_amount,
        AVG(t.amount) AS avg_completed_branch_transaction_amount,
        COUNT(DISTINCT t.account_id) AS transacting_accounts

    FROM banking.transactions AS t

    JOIN core.accounts AS a
        ON a.account_id = t.account_id

    JOIN core.products AS p
        ON p.product_id = a.product_id

    WHERE t.transaction_status = 'COMPLETED'
      AND t.channel = 'BRANCH'
      AND t.transaction_branch_id IS NOT NULL

    GROUP BY
        t.transaction_branch_id,
        DATE_TRUNC('month', t.transaction_datetime)::DATE,
        p.currency
)

SELECT
    bt.branch_id,
    b.branch_name,
    b.branch_type,
    b.branch_size,
    b.department,
    b.region,
    bt.year_month,
    bt.currency,
    bt.completed_branch_transaction_count,

    ROUND(
        bt.completed_branch_transaction_amount::NUMERIC,
        2
    ) AS completed_branch_transaction_amount,

    ROUND(
        bt.avg_completed_branch_transaction_amount::NUMERIC,
        2
    ) AS avg_completed_branch_transaction_amount,

    bt.transacting_accounts

FROM branch_transactions AS bt

JOIN core.branches AS b
    ON b.branch_id = bt.branch_id

ORDER BY
    bt.year_month,
    bt.currency,
    bt.completed_branch_transaction_count DESC;


-- ============================================================
-- 05. COUNTERPARTY-MONTH TRANSFER BASE — SQL PREPARATION
-- ============================================================
--
-- Only rows with a counterparty institution are included.
--
-- Grain:
-- 1 row =
-- counterparty institution
-- × month
-- × direction
-- × transfer scope
-- × currency
--
-- Completed transfer amount is the financial flow measure.
-- Failed attempts remain available as an operational measure.

WITH counterparty_transfers AS (
    SELECT
        t.counterparty_institution_id,
        DATE_TRUNC('month', t.transaction_datetime)::DATE AS year_month,
        t.direction,
        t.transfer_scope,
        p.currency,

        COUNT(*) AS attempted_transfer_count,

        COUNT(*) FILTER (
            WHERE t.transaction_status = 'COMPLETED'
        ) AS completed_transfer_count,

        COUNT(*) FILTER (
            WHERE t.transaction_status = 'FAILED'
        ) AS failed_transfer_count,

        SUM(t.amount) FILTER (
            WHERE t.transaction_status = 'COMPLETED'
        ) AS completed_transfer_amount,

        AVG(t.amount) FILTER (
            WHERE t.transaction_status = 'COMPLETED'
        ) AS avg_completed_transfer_amount,

        COUNT(DISTINCT t.account_id) FILTER (
            WHERE t.transaction_status = 'COMPLETED'
        ) AS completed_transacting_accounts

    FROM banking.transactions AS t

    JOIN core.accounts AS a
        ON a.account_id = t.account_id

    JOIN core.products AS p
        ON p.product_id = a.product_id

    WHERE t.transaction_type IN ('TRANSFER_IN', 'TRANSFER_OUT')
      AND t.counterparty_institution_id IS NOT NULL

    GROUP BY
        t.counterparty_institution_id,
        DATE_TRUNC('month', t.transaction_datetime)::DATE,
        t.direction,
        t.transfer_scope,
        p.currency
)

SELECT
    ct.counterparty_institution_id,
    fi.institution_name,
    fi.institution_type,
    fi.country,
    fi.domestic_flag,
    fi.bank_id,
    bk.bank_name,
    bk.bank_scope,
    bk.bank_type,
    ct.year_month,
    ct.direction,
    ct.transfer_scope,
    ct.currency,
    ct.attempted_transfer_count,
    ct.completed_transfer_count,
    ct.failed_transfer_count,

    ROUND(
        COALESCE(ct.completed_transfer_amount, 0)::NUMERIC,
        2
    ) AS completed_transfer_amount,

    ROUND(
        ct.avg_completed_transfer_amount::NUMERIC,
        2
    ) AS avg_completed_transfer_amount,

    ct.completed_transacting_accounts

FROM counterparty_transfers AS ct

JOIN market.financial_institutions AS fi
    ON fi.institution_id = ct.counterparty_institution_id

LEFT JOIN market.banks AS bk
    ON bk.bank_id = fi.bank_id

ORDER BY
    ct.year_month,
    ct.currency,
    completed_transfer_amount DESC;


-- ============================================================
-- 06. MONTHLY TRANSACTION BASELINE — SQL VALIDATION
-- ============================================================
--
-- Compact month × currency series for future DAX validation.
--
-- Financial volume = COMPLETED only.
-- Attempted count includes both COMPLETED and FAILED.

SELECT
    DATE_TRUNC('month', t.transaction_datetime)::DATE AS year_month,
    p.currency,

    COUNT(*) AS attempted_transaction_count,

    COUNT(*) FILTER (
        WHERE t.transaction_status = 'COMPLETED'
    ) AS completed_transaction_count,

    COUNT(*) FILTER (
        WHERE t.transaction_status = 'FAILED'
    ) AS failed_transaction_count,

    ROUND(
        COALESCE(
            SUM(t.amount) FILTER (
                WHERE t.transaction_status = 'COMPLETED'
            ),
            0
        )::NUMERIC,
        2
    ) AS completed_transaction_amount,

    ROUND(
        (
            AVG(t.amount) FILTER (
                WHERE t.transaction_status = 'COMPLETED'
            )
        )::NUMERIC,
        2
    ) AS avg_completed_transaction_amount,

    COUNT(DISTINCT t.account_id) FILTER (
        WHERE t.transaction_status = 'COMPLETED'
    ) AS completed_transacting_accounts,

    ROUND(
        (
            100.0
            * COUNT(*) FILTER (
                WHERE t.transaction_status = 'FAILED'
            )
            / NULLIF(COUNT(*), 0)
        )::NUMERIC,
        2
    ) AS failure_rate_pct

FROM banking.transactions AS t

JOIN core.accounts AS a
    ON a.account_id = t.account_id

JOIN core.products AS p
    ON p.product_id = a.product_id

GROUP BY
    DATE_TRUNC('month', t.transaction_datetime)::DATE,
    p.currency

ORDER BY
    year_month,
    p.currency;


-- ============================================================
-- 07. CHANNEL BASELINE — SQL VALIDATION
-- ============================================================
--
-- Channel × month × currency with both operational attempts and
-- completed financial activity.

SELECT
    DATE_TRUNC('month', t.transaction_datetime)::DATE AS year_month,
    t.channel,

    CASE
        WHEN t.channel IN ('MOBILE', 'WEB') THEN 'DIGITAL'
        WHEN t.channel IN ('BRANCH', 'ATM') THEN 'PHYSICAL'
        WHEN t.channel = 'AUTOMATIC' THEN 'AUTOMATED'
        WHEN t.channel = 'POS' THEN 'MERCHANT'
        ELSE 'OTHER'
    END AS channel_group,

    p.currency,

    COUNT(*) AS attempted_transaction_count,

    COUNT(*) FILTER (
        WHERE t.transaction_status = 'COMPLETED'
    ) AS completed_transaction_count,

    COUNT(*) FILTER (
        WHERE t.transaction_status = 'FAILED'
    ) AS failed_transaction_count,

    ROUND(
        COALESCE(
            SUM(t.amount) FILTER (
                WHERE t.transaction_status = 'COMPLETED'
            ),
            0
        )::NUMERIC,
        2
    ) AS completed_transaction_amount,

    ROUND(
        (
            AVG(t.amount) FILTER (
                WHERE t.transaction_status = 'COMPLETED'
            )
        )::NUMERIC,
        2
    ) AS avg_completed_transaction_amount,

    ROUND(
        (
            100.0
            * COUNT(*) FILTER (
                WHERE t.transaction_status = 'FAILED'
            )
            / NULLIF(COUNT(*), 0)
        )::NUMERIC,
        2
    ) AS failure_rate_pct

FROM banking.transactions AS t

JOIN core.accounts AS a
    ON a.account_id = t.account_id

JOIN core.products AS p
    ON p.product_id = a.product_id

GROUP BY
    DATE_TRUNC('month', t.transaction_datetime)::DATE,
    t.channel,
    CASE
        WHEN t.channel IN ('MOBILE', 'WEB') THEN 'DIGITAL'
        WHEN t.channel IN ('BRANCH', 'ATM') THEN 'PHYSICAL'
        WHEN t.channel = 'AUTOMATIC' THEN 'AUTOMATED'
        WHEN t.channel = 'POS' THEN 'MERCHANT'
        ELSE 'OTHER'
    END,
    p.currency

ORDER BY
    year_month,
    p.currency,
    attempted_transaction_count DESC;


-- ============================================================
-- 08. FAILURE BASELINE — SQL VALIDATION
-- ============================================================
--
-- Failed attempts are an operational-quality question, not realized
-- transaction volume. Currency is retained because failed attempted
-- amounts are still expressed in the account's native currency.

SELECT
    DATE_TRUNC('month', t.transaction_datetime)::DATE AS year_month,
    t.transaction_type,
    t.channel,
    p.currency,
    COALESCE(t.failure_reason, 'NO_FAILURE_REASON') AS failure_reason,
    COUNT(*) AS failed_transaction_count,

    ROUND(
        COALESCE(SUM(t.amount), 0)::NUMERIC,
        2
    ) AS failed_attempt_amount

FROM banking.transactions AS t

JOIN core.accounts AS a
    ON a.account_id = t.account_id

JOIN core.products AS p
    ON p.product_id = a.product_id

WHERE t.transaction_status = 'FAILED'

GROUP BY
    DATE_TRUNC('month', t.transaction_datetime)::DATE,
    t.transaction_type,
    t.channel,
    p.currency,
    COALESCE(t.failure_reason, 'NO_FAILURE_REASON')

ORDER BY
    year_month,
    p.currency,
    failed_transaction_count DESC;


-- ============================================================
-- 09. TRANSFER-SCOPE BASELINE — SQL VALIDATION
-- ============================================================
--
-- Restricts analysis to rows where transfer_scope is populated.
-- Completed amount is the realized transfer-flow measure.

SELECT
    DATE_TRUNC('month', t.transaction_datetime)::DATE AS year_month,
    t.transfer_scope,
    t.direction,
    p.currency,

    COUNT(*) AS attempted_transfer_count,

    COUNT(*) FILTER (
        WHERE t.transaction_status = 'COMPLETED'
    ) AS completed_transfer_count,

    COUNT(*) FILTER (
        WHERE t.transaction_status = 'FAILED'
    ) AS failed_transfer_count,

    ROUND(
        COALESCE(
            SUM(t.amount) FILTER (
                WHERE t.transaction_status = 'COMPLETED'
            ),
            0
        )::NUMERIC,
        2
    ) AS completed_transfer_amount,

    ROUND(
        (
            AVG(t.amount) FILTER (
                WHERE t.transaction_status = 'COMPLETED'
            )
        )::NUMERIC,
        2
    ) AS avg_completed_transfer_amount

FROM banking.transactions AS t

JOIN core.accounts AS a
    ON a.account_id = t.account_id

JOIN core.products AS p
    ON p.product_id = a.product_id

WHERE t.transaction_type IN ('TRANSFER_IN', 'TRANSFER_OUT')
  AND t.transfer_scope IS NOT NULL

GROUP BY
    DATE_TRUNC('month', t.transaction_datetime)::DATE,
    t.transfer_scope,
    t.direction,
    p.currency

ORDER BY
    year_month,
    p.currency,
    completed_transfer_count DESC;


-- ============================================================
-- 09.5 MERCHANT-CATEGORY BASELINE — SQL VALIDATION
-- ============================================================
--
-- Merchant category is meaningful for merchant-related activity.
-- This baseline is restricted to DEBIT_PURCHASE and keeps currency
-- separate. Completed amount is realized money movement; failed rows
-- remain useful only as operational attempts.

SELECT
    DATE_TRUNC('month', t.transaction_datetime)::DATE AS year_month,
    COALESCE(t.merchant_category, 'UNCLASSIFIED') AS merchant_category,
    t.channel,
    p.currency,

    COUNT(*) AS attempted_purchase_count,

    COUNT(*) FILTER (
        WHERE t.transaction_status = 'COMPLETED'
    ) AS completed_purchase_count,

    COUNT(*) FILTER (
        WHERE t.transaction_status = 'FAILED'
    ) AS failed_purchase_count,

    ROUND(
        COALESCE(
            SUM(t.amount) FILTER (
                WHERE t.transaction_status = 'COMPLETED'
            ),
            0
        )::NUMERIC,
        2
    ) AS completed_purchase_amount

FROM banking.transactions AS t

JOIN core.accounts AS a
    ON a.account_id = t.account_id

JOIN core.products AS p
    ON p.product_id = a.product_id

WHERE t.transaction_type = 'DEBIT_PURCHASE'

GROUP BY
    DATE_TRUNC('month', t.transaction_datetime)::DATE,
    COALESCE(t.merchant_category, 'UNCLASSIFIED'),
    t.channel,
    p.currency

ORDER BY
    year_month,
    p.currency,
    completed_purchase_count DESC;


-- ============================================================
-- 10. DATA-QUALITY / SEMANTIC DIAGNOSTICS
-- ============================================================
--
-- PK/FK uniqueness is already enforced and audited in the relational
-- model. The checks here focus on transaction-domain semantics.


-- 10.1 Status / failure-reason consistency.
-- Expected result: zero rows.
-- COMPLETED should have no failure reason; FAILED should have one.

SELECT
    t.transaction_status,
    t.failure_reason,
    COUNT(*) AS transaction_count
FROM banking.transactions AS t
WHERE
       (t.transaction_status = 'COMPLETED'
        AND t.failure_reason IS NOT NULL)
    OR (t.transaction_status = 'FAILED'
        AND t.failure_reason IS NULL)
GROUP BY
    t.transaction_status,
    t.failure_reason
ORDER BY transaction_count DESC;


-- 10.2 Transaction-type / direction consistency.
-- Expected result: zero rows.
-- Unknown transaction types are also surfaced for review.

WITH direction_check AS (
    SELECT
        t.transaction_type,
        t.direction,

        CASE
            WHEN t.transaction_type IN (
                'TRANSFER_IN',
                'CASH_DEPOSIT',
                'LOAN_DISBURSEMENT',
                'INTEREST_CREDIT'
            ) THEN 'CREDIT'
            WHEN t.transaction_type IN (
                'TRANSFER_OUT',
                'CASH_WITHDRAWAL',
                'DEBIT_PURCHASE',
                'SERVICE_PAYMENT',
                'CREDIT_CARD_PAYMENT',
                'LOAN_PAYMENT'
            ) THEN 'DEBIT'
            ELSE NULL
        END AS expected_direction

    FROM banking.transactions AS t
)

SELECT
    dc.transaction_type,
    dc.direction,
    dc.expected_direction,
    COUNT(*) AS transaction_count
FROM direction_check AS dc
WHERE dc.expected_direction IS NULL
   OR dc.direction IS DISTINCT FROM dc.expected_direction
GROUP BY
    dc.transaction_type,
    dc.direction,
    dc.expected_direction
ORDER BY transaction_count DESC;


-- 10.3 Non-positive transaction amounts.
-- The business definition requires strictly positive absolute amounts.
-- Expected result: zero rows.

SELECT
    t.transaction_id,
    t.amount,
    t.transaction_type,
    t.transaction_status
FROM banking.transactions AS t
WHERE t.amount <= 0
ORDER BY t.transaction_id;


-- 10.4 Physical branch transaction consistency.
-- BRANCH-channel transactions should identify the physical branch.
-- Expected result: zero rows in the canonical world.

SELECT
    t.transaction_id,
    t.transaction_datetime,
    t.channel,
    t.transaction_branch_id,
    t.transaction_status
FROM banking.transactions AS t
WHERE
       (t.channel = 'BRANCH' AND t.transaction_branch_id IS NULL)
    OR (t.channel <> 'BRANCH' AND t.transaction_branch_id IS NOT NULL)
ORDER BY t.transaction_datetime;


-- 10.5 Counterparty-institution usage by transaction type.
-- Diagnostic only; this does not assume every transfer has a mapped
-- financial institution.

SELECT
    t.transaction_type,
    COUNT(*) AS transaction_count,

    COUNT(*) FILTER (
        WHERE t.counterparty_institution_id IS NOT NULL
    ) AS transactions_with_counterparty_institution,

    ROUND(
        (
            100.0
            * COUNT(*) FILTER (
                WHERE t.counterparty_institution_id IS NOT NULL
            )
            / NULLIF(COUNT(*), 0)
        )::NUMERIC,
        2
    ) AS pct_with_counterparty_institution

FROM banking.transactions AS t
GROUP BY t.transaction_type
ORDER BY transaction_count DESC;


-- 10.6 Non-transfer rows carrying transfer scope.
-- Expected result: zero rows.

SELECT
    t.transaction_type,
    t.transfer_scope,
    COUNT(*) AS transaction_count
FROM banking.transactions AS t
WHERE t.transaction_type NOT IN ('TRANSFER_IN', 'TRANSFER_OUT')
  AND t.transfer_scope IS NOT NULL
GROUP BY
    t.transaction_type,
    t.transfer_scope
ORDER BY transaction_count DESC;


-- 10.7 Merchant-category applicability.
-- Non-purchase rows should not carry a merchant category.
-- Missing categories on DEBIT_PURCHASE are reported separately as a
-- completeness metric because optional-classification degradation may
-- exist in some generated worlds.

SELECT
    t.transaction_type,
    t.merchant_category,
    COUNT(*) AS transaction_count
FROM banking.transactions AS t
WHERE t.transaction_type <> 'DEBIT_PURCHASE'
  AND t.merchant_category IS NOT NULL
GROUP BY
    t.transaction_type,
    t.merchant_category
ORDER BY transaction_count DESC;


SELECT
    COUNT(*) AS debit_purchase_attempts,
    COUNT(*) FILTER (
        WHERE t.merchant_category IS NOT NULL
    ) AS classified_debit_purchase_attempts,
    ROUND(
        (
            100.0 * COUNT(*) FILTER (
                WHERE t.merchant_category IS NOT NULL
            )
            / NULLIF(COUNT(*), 0)
        )::NUMERIC,
        2
    ) AS merchant_category_completeness_pct
FROM banking.transactions AS t
WHERE t.transaction_type = 'DEBIT_PURCHASE';


-- ============================================================
-- 11. PERFORMANCE WORKFLOW — DO NOT RUN AUTOMATICALLY
-- ============================================================
--
-- Use EXPLAIN first when designing a new heavy query.
-- EXPLAIN does not execute the query.
--
-- Example:
--
-- EXPLAIN
-- SELECT
--     t.account_id,
--     DATE_TRUNC('month', t.transaction_datetime)::DATE AS year_month,
--     t.channel,
--     COUNT(*) FILTER (
--         WHERE t.transaction_status = 'COMPLETED'
--     ) AS completed_transaction_count
-- FROM banking.transactions AS t
-- GROUP BY
--     t.account_id,
--     DATE_TRUNC('month', t.transaction_datetime)::DATE,
--     t.channel;
--
-- Once the logic is safe and reusable:
--
-- EXPLAIN (ANALYZE, BUFFERS)
-- SELECT ...
--
-- EXPLAIN ANALYZE DOES execute the query.
--
-- Do not add indexes speculatively. Index design belongs to the later
-- performance phase and should follow measured query plans/workloads.
--
-- Likely fields to inspect there include:
-- - transaction_datetime
-- - account_id
-- - transaction_branch_id
-- - counterparty_institution_id
-- - transaction_type
-- - channel
-- - transaction_status
--
-- ============================================================
-- 12. DOWNSTREAM ANALYTICAL HANDOFF
-- ============================================================
--
-- POWER BI / DAX
--
-- Preferred source:
-- account-month transaction aggregate
--
-- Default financial-activity measures should use COMPLETED metrics:
--
-- - Completed Transaction Count
-- - Completed Transaction Value
-- - Average Completed Transaction Value
-- - Incoming Completed Value
-- - Outgoing Completed Value
-- - Channel Share %
-- - Digital Transaction %
-- - Digital Value %
-- - Branch Transaction Share %
-- - International Transfer Share %
-- - YoY Completed Transaction Growth
--
-- Operational-quality measures should use attempted/failed metrics:
--
-- - Attempted Transaction Count
-- - Failed Transaction Count
-- - Failure Rate %
-- - Failed Attempt Amount
--
-- Do not use attempted amount as realized transaction volume.
--
-- PYTHON / PANDAS / JUPYTER
--
-- Prefer targeted extracts or reduced aggregates for:
-- - completed amount distributions
-- - percentiles / heavy tails
-- - account-month intensity distributions
-- - high-value outliers
-- - intraday / day-of-week behavior
-- - failure-pattern analysis
-- - concentration curves
--
-- Avoid loading all raw transactions into pandas without a clear reason.
--
-- SUPERSET
--
-- Strong operational candidates:
-- - recent completed transaction activity
-- - failure monitoring
-- - channel activity
-- - physical branch activity
-- - transfer-scope monitoring
-- - counterparty flows
--
-- POWER QUERY
--
-- Keep it light:
-- - connect to PostgreSQL
-- - select reusable analytical objects
-- - enforce types
-- - remove presentation-irrelevant columns
-- - do not rebuild transaction business logic
--
-- ============================================================
-- 13. PERSISTENCE DECISION
-- ============================================================
--
-- Candidate reusable objects:
-- - account-month transaction summary
-- - physical branch-month transaction summary
-- - counterparty-month transfer summary
--
-- Persist/materialize only after confirming:
-- 1. grain is analytically useful;
-- 2. logic is reused repeatedly;
-- 3. runtime justifies persistence;
-- 4. refresh strategy is clear;
-- 5. downstream BI benefits materially.
--
-- ============================================================
-- END
-- ============================================================
