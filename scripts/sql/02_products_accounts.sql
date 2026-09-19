-- ============================================================
-- BTYT — PRODUCTS & ACCOUNTS ANALYTICS
-- File: 02_products_accounts.sql
-- Architecture-aligned revision
--
-- Purpose:
-- Prepare reusable product/account analytical structure while
-- keeping dynamic BI calculations out of the SQL data layer.
--
-- PostgreSQL | Read-only analytical queries
-- ============================================================
--
-- MAIN QUESTION
-- What products does BTYT offer, how are account relationships
-- created and closed, and what reusable account-level structure
-- should downstream analytics consume?
--
-- TOOL OWNERSHIP
--
-- SQL:
-- - product catalog structure
-- - account lifecycle / cohorts
-- - one-row-per-account analytical base
-- - account × month analytical base
-- - card analytical base
--
-- DAX / Power BI:
-- - account shares
-- - currency mix %
-- - channel mix %
-- - balances by selected filters
-- - inflows, outflows and net flow
-- - portfolio concentration
-- - account growth measures
--
-- Python:
-- - balance distributions
-- - outliers
-- - concentration curves
-- - statistical comparisons
--
-- IMPORTANT MONETARY RULE
-- UYU and USD balances must not be summed as one monetary total
-- unless an explicit FX conversion is introduced.
--
-- ============================================================
-- 01. PRODUCT CATALOG — SQL EXPLORATION
-- ============================================================

-- 1.1 Complete product catalog and launch chronology.

SELECT
    p.product_id,
    p.product_name,
    p.product_family,
    p.currency,
    p.target_customer_type,
    p.launch_year
FROM core.products AS p
ORDER BY
    p.launch_year,
    p.product_family,
    p.product_id;


-- 1.2 Product-family structure.

SELECT
    p.product_family,
    COUNT(*) AS product_count
FROM core.products AS p
GROUP BY p.product_family
ORDER BY product_count DESC;


-- ============================================================
-- 02. ACCOUNT LIFECYCLE OVER TIME — SQL
-- ============================================================

-- 2.1 Annual account lifecycle.
-- Reusable reference for openings, closures, net change and stock.

WITH years AS (
    SELECT generate_series(
        MIN(a.opening_year),
        2026
    ) AS year
    FROM core.accounts AS a
),

openings AS (
    SELECT
        a.opening_year AS year,
        COUNT(*) AS accounts_opened
    FROM core.accounts AS a
    GROUP BY a.opening_year
),

closures AS (
    SELECT
        a.closing_year AS year,
        COUNT(*) AS accounts_closed
    FROM core.accounts AS a
    WHERE a.closing_year IS NOT NULL
    GROUP BY a.closing_year
),

active_stock AS (
    SELECT
        y.year,
        COUNT(a.account_id) AS active_account_stock
    FROM years AS y
    LEFT JOIN core.accounts AS a
        ON a.opening_year <= y.year
       AND (
            a.closing_year IS NULL
            OR a.closing_year > y.year
       )
    GROUP BY y.year
)

SELECT
    y.year,
    COALESCE(o.accounts_opened, 0) AS accounts_opened,
    COALESCE(c.accounts_closed, 0) AS accounts_closed,
    COALESCE(o.accounts_opened, 0)
        - COALESCE(c.accounts_closed, 0) AS net_account_change,
    ast.active_account_stock
FROM years AS y
LEFT JOIN openings AS o
    ON o.year = y.year
LEFT JOIN closures AS c
    ON c.year = y.year
LEFT JOIN active_stock AS ast
    ON ast.year = y.year
ORDER BY y.year;


-- ============================================================
-- 03. ACCOUNT COHORTS — SQL
-- ============================================================

-- 3.1 Opening cohort × product × opening channel.
-- Keeps stable cohort logic in SQL.
--
-- Dynamic visual comparisons can later be handled in Power BI.

SELECT
    a.opening_year AS cohort_year,
    p.product_id,
    p.product_name,
    p.currency,
    a.opening_channel,
    COUNT(*) AS cohort_accounts,

    COUNT(*) FILTER (
        WHERE a.account_status = 'ACTIVE'
    ) AS currently_active,

    COUNT(*) FILTER (
        WHERE a.account_status = 'CLOSED'
    ) AS currently_closed,

    ROUND(
        100.0
        * COUNT(*) FILTER (
            WHERE a.account_status = 'ACTIVE'
        )
        / NULLIF(COUNT(*), 0),
        2
    ) AS current_active_rate_pct

FROM core.accounts AS a

JOIN core.products AS p
    ON p.product_id = a.product_id

GROUP BY
    a.opening_year,
    p.product_id,
    p.product_name,
    p.currency,
    a.opening_channel

ORDER BY
    cohort_year,
    p.product_name,
    a.opening_channel;


-- ============================================================
-- 04. ACCOUNT ANALYTICAL BASE — SQL PREPARATION
-- ============================================================

-- 4.1 One row per account.
--
-- This is the main reusable account dataset for Power BI / DAX.
--
-- Grain:
-- 1 row = 1 account
--
-- Dimensions included:
-- - product
-- - currency
-- - customer type / segment
-- - branch / region
-- - opening channel
-- - lifecycle years

SELECT
    a.account_id,
    a.customer_id,
    a.product_id,
    a.branch_id,

    a.opening_year,
    a.account_status,
    a.closing_year,
    a.opening_channel,

    CASE
        WHEN a.closing_year IS NOT NULL
            THEN a.closing_year - a.opening_year
        ELSE 2026 - a.opening_year
    END AS account_tenure_years,

    p.product_name,
    p.product_family,
    p.currency,
    p.target_customer_type,
    p.launch_year AS product_launch_year,

    c.customer_type,

    CASE
        WHEN c.customer_type = 'INDIVIDUAL'
            THEN COALESCE(c.employment_status, 'UNKNOWN')
        WHEN c.customer_type = 'BUSINESS'
            THEN COALESCE(c.company_size, 'UNKNOWN')
        ELSE 'UNKNOWN'
    END AS customer_segment,

    b.branch_name,
    b.branch_type,
    b.branch_size,
    b.department,
    b.region

FROM core.accounts AS a

JOIN core.products AS p
    ON p.product_id = a.product_id

JOIN core.customers AS c
    ON c.customer_id = a.customer_id

JOIN core.branches AS b
    ON b.branch_id = a.branch_id;


-- ============================================================
-- 05. ACCOUNT MONTHLY ANALYTICAL BASE — SQL PREPARATION
-- ============================================================

-- 5.1 One row per account × month.
--
-- This is the preferred reusable source for monthly account
-- balance and flow analysis.
--
-- Grain:
-- 1 row = 1 account × 1 year_month
--
-- IMPORTANT:
-- closing_balance is a STOCK.
-- total_inflows and total_outflows are FLOWS.
--
-- Therefore:
-- - closing balances should be analyzed at a snapshot month;
-- - inflows/outflows may be summed across periods;
-- - UYU and USD should remain separated unless converted.
-- - account_status is a master/cutoff attribute, not a historical monthly status.
--
-- Reconciliation caution:
-- performance.average_deposits is NOT simply SUM(closing_balance). The
-- performance engine uses (opening_balance + closing_balance) / 2 and converts
-- USD balances to UYU-equivalent. Do not expect native-currency closing-balance
-- totals here to equal the consolidated performance field directly.
--   The presence of an account-month row is the monthly observation itself.

SELECT
    ab.account_id,
    ab.year_month,

    ab.opening_balance,
    ab.total_inflows,
    ab.total_outflows,
    ab.closing_balance,

    ab.total_inflows
        - ab.total_outflows AS net_flow,

    a.customer_id,
    a.product_id,
    a.branch_id,
    a.account_status AS account_status_at_cutoff,
    a.opening_year,
    a.closing_year,
    a.opening_channel,

    p.product_name,
    p.product_family,
    p.currency,
    p.target_customer_type,

    c.customer_type,

    CASE
        WHEN c.customer_type = 'INDIVIDUAL'
            THEN COALESCE(c.employment_status, 'UNKNOWN')
        WHEN c.customer_type = 'BUSINESS'
            THEN COALESCE(c.company_size, 'UNKNOWN')
        ELSE 'UNKNOWN'
    END AS customer_segment,

    b.branch_name,
    b.department,
    b.region

FROM banking.account_balances AS ab

JOIN core.accounts AS a
    ON a.account_id = ab.account_id

JOIN core.products AS p
    ON p.product_id = a.product_id

JOIN core.customers AS c
    ON c.customer_id = a.customer_id

JOIN core.branches AS b
    ON b.branch_id = a.branch_id;


-- ============================================================
-- 06. PRODUCT TARGET ALIGNMENT — SQL DIAGNOSTIC
-- ============================================================

-- 6.1 Actual customer type versus intended product target.
-- This is a useful structural diagnostic rather than a dashboard KPI.

SELECT
    p.product_name,
    p.target_customer_type,
    c.customer_type AS actual_customer_type,
    COUNT(*) AS account_count
FROM core.accounts AS a
JOIN core.products AS p
    ON p.product_id = a.product_id
JOIN core.customers AS c
    ON c.customer_id = a.customer_id
GROUP BY
    p.product_name,
    p.target_customer_type,
    c.customer_type
ORDER BY
    p.product_name,
    account_count DESC;


-- ============================================================
-- 07. CARD ANALYTICAL BASE — SQL PREPARATION
-- ============================================================

-- 7.1 One row per card.
--
-- Card issuance/channel analysis can then be performed dynamically
-- in Power BI rather than pre-aggregating every combination in SQL.
--
-- Branch attribution:
-- - debit cards use the linked account branch;
-- - credit cards have no linked_account_id by design, so the customer
--   primary branch is used as the relationship branch.
-- This mirrors the branch-performance attribution logic for card fees.
--
-- Grain:
-- 1 row = 1 card

SELECT
    ca.card_id,
    ca.customer_id,
    ca.product_id,
    ca.linked_account_id,

    ca.issue_year,
    ca.card_status,
    ca.closing_year,
    ca.issue_channel,

    p.product_name,
    p.product_family,
    p.currency,
    p.target_customer_type,

    c.customer_type,

    CASE
        WHEN c.customer_type = 'INDIVIDUAL'
            THEN COALESCE(c.employment_status, 'UNKNOWN')
        WHEN c.customer_type = 'BUSINESS'
            THEN COALESCE(c.company_size, 'UNKNOWN')
        ELSE 'UNKNOWN'
    END AS customer_segment,

    a.branch_id AS linked_account_branch_id,

    COALESCE(
        a.branch_id,
        c.primary_branch_id
    ) AS relationship_branch_id,

    b.branch_name AS relationship_branch_name,
    b.region AS relationship_branch_region

FROM banking.cards AS ca

JOIN core.products AS p
    ON p.product_id = ca.product_id

JOIN core.customers AS c
    ON c.customer_id = ca.customer_id

LEFT JOIN core.accounts AS a
    ON a.account_id = ca.linked_account_id

LEFT JOIN core.branches AS b
    ON b.branch_id = COALESCE(
        a.branch_id,
        c.primary_branch_id
    );


-- ============================================================
-- 08. ACCOUNT-BALANCE COVERAGE & CONSISTENCY
-- ============================================================

-- 8.1 Confirm account-balance coverage before BI modeling.

SELECT
    MIN(ab.year_month) AS first_balance_month,
    MAX(ab.year_month) AS last_balance_month,
    COUNT(DISTINCT ab.year_month) AS month_count,
    COUNT(*) AS account_month_rows,
    COUNT(DISTINCT ab.account_id) AS accounts_with_balance_history
FROM banking.account_balances AS ab;


-- 8.2 Duplicate account-month check.
-- The relational PK should make this return zero rows.

SELECT
    ab.account_id,
    ab.year_month,
    COUNT(*) AS row_count
FROM banking.account_balances AS ab
GROUP BY
    ab.account_id,
    ab.year_month
HAVING COUNT(*) > 1
ORDER BY row_count DESC;


-- 8.3 Balance accounting identity.
-- Expected maximum residual: 0.00 (or negligible rounding residual).
--
-- closing_balance = opening_balance + inflows - outflows

SELECT
    ROUND(
        MAX(
            ABS(
                ab.closing_balance
                - (
                    ab.opening_balance
                    + ab.total_inflows
                    - ab.total_outflows
                )
            )
        )::NUMERIC,
        2
    ) AS max_balance_identity_residual
FROM banking.account_balances AS ab;


-- 8.4 Negative balance / flow diagnostic.
-- The canonical transaction engine should not produce negative
-- stored flow amounts. Review any rows returned here.

SELECT
    ab.account_id,
    ab.year_month,
    ab.opening_balance,
    ab.total_inflows,
    ab.total_outflows,
    ab.closing_balance
FROM banking.account_balances AS ab
WHERE
       ab.opening_balance < 0
    OR ab.total_inflows < 0
    OR ab.total_outflows < 0
    OR ab.closing_balance < 0
ORDER BY
    ab.year_month,
    ab.account_id;


-- 8.5 Account master lifecycle consistency.
-- Expected result: zero rows.

SELECT
    a.account_id,
    a.opening_year,
    a.account_status,
    a.closing_year
FROM core.accounts AS a
WHERE
       (a.account_status = 'ACTIVE' AND a.closing_year IS NOT NULL)
    OR (a.account_status = 'CLOSED' AND a.closing_year IS NULL)
    OR (a.closing_year IS NOT NULL AND a.closing_year < a.opening_year)
    OR (a.closing_year IS NOT NULL AND a.closing_year > 2026)
ORDER BY a.account_id;


-- 8.6 Card master lifecycle consistency.
-- Expected result: zero rows.

SELECT
    ca.card_id,
    ca.issue_year,
    ca.card_status,
    ca.closing_year
FROM banking.cards AS ca
WHERE
       (ca.card_status = 'ACTIVE' AND ca.closing_year IS NOT NULL)
    OR (ca.card_status = 'CLOSED' AND ca.closing_year IS NULL)
    OR (ca.closing_year IS NOT NULL AND ca.closing_year < ca.issue_year)
    OR (ca.closing_year IS NOT NULL AND ca.closing_year > 2026)
ORDER BY ca.card_id;


-- ============================================================
-- 09. DOWNSTREAM ANALYTICAL HANDOFF
-- ============================================================
--
-- DAX / POWER BI
--
-- Build dynamic measures over the account and account-month bases:
--
-- - Total Accounts
-- - Active Accounts
-- - Accounts Opened
-- - Accounts Closed
-- - Account Share %
-- - YoY Account Growth
-- - Average Closing Balance
-- - Total Closing Balance at selected month
-- - Total Inflows
-- - Total Outflows
-- - Net Flow
-- - Currency Mix %
-- - Opening Channel Mix %
-- - Product Mix %
-- - Account Share by Region
-- - Card Penetration / Card Count
--
-- These measures should react to filters such as:
--
-- - year / month
-- - product
-- - product family
-- - currency
-- - customer type
-- - customer segment
-- - branch
-- - region
-- - opening / issue channel
--
-- PYTHON / PANDAS
--
-- Use the account-month base only when the question becomes:
--
-- - distribution of balances
-- - balance outliers
-- - concentration curves
-- - statistical comparisons
-- - account-level trajectory analysis
--
-- POWER QUERY
--
-- Keep Power Query light:
--
-- - connect to PostgreSQL
-- - select required analytical datasets
-- - enforce types
-- - remove presentation-irrelevant columns
-- - avoid rebuilding business logic already defined in SQL
--
-- ============================================================
-- END
-- ============================================================

