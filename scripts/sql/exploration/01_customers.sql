-- ============================================================
-- BTYT — CUSTOMER ANALYTICS
-- File: 01_customers.sql
-- Architecture-aligned revision
--
-- Purpose:
-- Prepare reusable customer-level analytical structure and keep
-- only SQL analyses that are naturally owned by the data layer.
--
-- PostgreSQL | Read-only analytical queries
-- ============================================================
--
-- MAIN QUESTION
-- Who are BTYT customers, how has the customer base evolved,
-- and what reusable customer-level structure should downstream
-- analytics consume?
--
-- TOOL OWNERSHIP
--
-- SQL:
-- - customer composition checks
-- - lifecycle / cohorts
-- - one-row-per-customer analytical base
-- - reusable relationship counts and flags
--
-- Python:
-- - distributions, percentiles, outliers
-- - age / income / tenure comparisons
-- - statistical segment analysis
--
-- DAX / Power BI:
-- - dynamic percentages and averages
-- - filter-context segment comparisons
-- - interactive cross-sell and product-depth measures
--
-- IMPORTANT SEMANTIC DISTINCTION
-- Relationship history is not the same as a current relationship.
-- Historical accounts/cards/loans are therefore kept separate from
-- currently active account/card counts.
--
-- Loan "current relationship" logic is intentionally deferred to
-- 03_loans.sql, where loan-status semantics are defined explicitly.
--
-- ============================================================
-- 01. CUSTOMER COMPOSITION — SQL EXPLORATION
-- ============================================================

-- 1.1 Customer type × status.
-- A compact baseline check before building downstream analysis.

SELECT
    c.customer_type,
    c.customer_status,
    COUNT(*) AS customer_count,
    ROUND(
        100.0 * COUNT(*)
        / SUM(COUNT(*)) OVER (
            PARTITION BY c.customer_type
        ),
        2
    ) AS status_pct_within_type
FROM core.customers AS c
GROUP BY
    c.customer_type,
    c.customer_status
ORDER BY
    c.customer_type,
    customer_count DESC;


-- ============================================================
-- 02. CUSTOMER LIFECYCLE OVER TIME — SQL
-- ============================================================

-- 2.1 Registrations, closures, net change and active stock by year.
-- This is a reusable annual lifecycle reference.

WITH years AS (
    SELECT generate_series(
        MIN(c.registration_year),
        2026
    ) AS year
    FROM core.customers AS c
),

registrations AS (
    SELECT
        c.registration_year AS year,
        COUNT(*) AS registrations
    FROM core.customers AS c
    GROUP BY c.registration_year
),

closures AS (
    SELECT
        c.closing_year AS year,
        COUNT(*) AS closures
    FROM core.customers AS c
    WHERE c.closing_year IS NOT NULL
    GROUP BY c.closing_year
),

active_stock AS (
    SELECT
        y.year,
        COUNT(c.customer_id) AS active_customer_stock
    FROM years AS y
    LEFT JOIN core.customers AS c
        ON c.registration_year <= y.year
       AND (
            c.closing_year IS NULL
            OR c.closing_year > y.year
       )
    GROUP BY y.year
)

SELECT
    y.year,
    COALESCE(r.registrations, 0) AS registrations,
    COALESCE(cl.closures, 0) AS closures,
    COALESCE(r.registrations, 0)
        - COALESCE(cl.closures, 0) AS net_customer_change,
    ast.active_customer_stock
FROM years AS y
LEFT JOIN registrations AS r
    ON r.year = y.year
LEFT JOIN closures AS cl
    ON cl.year = y.year
LEFT JOIN active_stock AS ast
    ON ast.year = y.year
ORDER BY y.year;


-- ============================================================
-- 03. REGISTRATION COHORTS — SQL
-- ============================================================

-- 3.1 Registration cohort × customer type.
-- Keeps the cohort logic at the data layer while avoiding
-- unnecessary downstream-style descriptive statistics.

SELECT
    c.registration_year AS cohort_year,
    c.customer_type,
    COUNT(*) AS cohort_customers,

    COUNT(*) FILTER (
        WHERE c.customer_status = 'ACTIVE'
    ) AS currently_active,

    COUNT(*) FILTER (
        WHERE c.customer_status = 'CLOSED'
    ) AS currently_closed,

    ROUND(
        100.0
        * COUNT(*) FILTER (
            WHERE c.customer_status = 'ACTIVE'
        )
        / NULLIF(COUNT(*), 0),
        2
    ) AS current_active_rate_pct

FROM core.customers AS c

GROUP BY
    c.registration_year,
    c.customer_type

ORDER BY
    cohort_year,
    c.customer_type;


-- ============================================================
-- 04. CUSTOMER DIMENSIONAL BASE — SQL PREPARATION
-- ============================================================

-- 4.1 One row per customer.
--
-- This is a candidate reusable analytical dataset.
-- It does NOT aggregate customers into final dashboard segments.
-- Power BI / DAX and Python can group this base dynamically.
--
-- Grain:
-- 1 row = 1 customer

SELECT
    c.customer_id,
    c.customer_type,
    c.customer_status,
    c.registration_year,
    c.closing_year,

    CASE
        WHEN c.closing_year IS NOT NULL
            THEN c.closing_year - c.registration_year
        ELSE 2026 - c.registration_year
    END AS tenure_years,

    CASE
        WHEN c.customer_type = 'INDIVIDUAL'
            THEN 2026 - c.birth_year
        ELSE NULL
    END AS approx_age_2026,

    c.gender,
    c.employment_status,
    c.monthly_income,

    c.company_size,
    c.business_sector,
    c.foundation_year,
    c.annual_revenue,

    CASE
        WHEN c.customer_type = 'BUSINESS'
             AND c.foundation_year IS NOT NULL
            THEN 2026 - c.foundation_year
        ELSE NULL
    END AS business_age_2026,

    CASE
        WHEN c.customer_type = 'INDIVIDUAL'
            THEN COALESCE(c.employment_status, 'UNKNOWN')
        WHEN c.customer_type = 'BUSINESS'
            THEN COALESCE(c.company_size, 'UNKNOWN')
        ELSE 'UNKNOWN'
    END AS customer_segment,

    c.residence_country,
    c.residence_department,
    c.residence_locality,

    c.primary_branch_id,
    b.branch_name AS primary_branch_name,
    b.region AS primary_branch_region

FROM core.customers AS c

LEFT JOIN core.branches AS b
    ON b.branch_id = c.primary_branch_id;


-- ============================================================
-- 05. CUSTOMER RELATIONSHIP BASE — SQL PREPARATION
-- ============================================================

-- 5.1 One row per customer with relationship history.
--
-- Instead of joining accounts + cards + loans directly and risking
-- row multiplication, the three relationship sources are stacked
-- vertically and aggregated once.
--
-- Grain:
-- 1 row = 1 customer
--
-- NOTE:
-- total_* columns describe historical relationships.
-- active_account_count and active_card_count describe current
-- status according to their own tables.
-- Loan current-status logic is deferred to 03_loans.sql.

WITH relationships AS (

    SELECT
        a.customer_id,
        a.product_id,
        'ACCOUNT' AS relationship_type,
        a.account_status AS relationship_status
    FROM core.accounts AS a

    UNION ALL

    SELECT
        ca.customer_id,
        ca.product_id,
        'CARD' AS relationship_type,
        ca.card_status AS relationship_status
    FROM banking.cards AS ca

    UNION ALL

    SELECT
        l.customer_id,
        l.product_id,
        'LOAN' AS relationship_type,
        l.loan_status AS relationship_status
    FROM banking.loans AS l
),

relationship_counts AS (
    SELECT
        r.customer_id,

        COUNT(*) FILTER (
            WHERE r.relationship_type = 'ACCOUNT'
        ) AS total_account_count,

        COUNT(*) FILTER (
            WHERE r.relationship_type = 'CARD'
        ) AS total_card_count,

        COUNT(*) FILTER (
            WHERE r.relationship_type = 'LOAN'
        ) AS loan_history_count,

        COUNT(*) FILTER (
            WHERE r.relationship_type = 'ACCOUNT'
              AND r.relationship_status = 'ACTIVE'
        ) AS active_account_count,

        COUNT(*) FILTER (
            WHERE r.relationship_type = 'CARD'
              AND r.relationship_status = 'ACTIVE'
        ) AS active_card_count,

        COUNT(DISTINCT r.product_id)
            AS lifetime_distinct_product_count

    FROM relationships AS r

    GROUP BY r.customer_id
)

SELECT
    c.customer_id,
    c.customer_type,
    c.customer_status,

    CASE
        WHEN c.customer_type = 'INDIVIDUAL'
            THEN COALESCE(c.employment_status, 'UNKNOWN')
        WHEN c.customer_type = 'BUSINESS'
            THEN COALESCE(c.company_size, 'UNKNOWN')
        ELSE 'UNKNOWN'
    END AS customer_segment,

    c.registration_year,

    CASE
        WHEN c.closing_year IS NOT NULL
            THEN c.closing_year - c.registration_year
        ELSE 2026 - c.registration_year
    END AS tenure_years,

    b.region AS primary_branch_region,

    COALESCE(rc.total_account_count, 0)
        AS total_account_count,

    COALESCE(rc.total_card_count, 0)
        AS total_card_count,

    COALESCE(rc.loan_history_count, 0)
        AS loan_history_count,

    COALESCE(rc.active_account_count, 0)
        AS active_account_count,

    COALESCE(rc.active_card_count, 0)
        AS active_card_count,

    COALESCE(rc.lifetime_distinct_product_count, 0)
        AS lifetime_distinct_product_count,

    CASE
        WHEN COALESCE(rc.active_account_count, 0) > 0
            THEN 1
        ELSE 0
    END AS has_active_account,

    CASE
        WHEN COALESCE(rc.active_card_count, 0) > 0
            THEN 1
        ELSE 0
    END AS has_active_card,

    CASE
        WHEN COALESCE(rc.loan_history_count, 0) > 0
            THEN 1
        ELSE 0
    END AS has_loan_history

FROM core.customers AS c

LEFT JOIN relationship_counts AS rc
    ON rc.customer_id = c.customer_id

LEFT JOIN core.branches AS b
    ON b.branch_id = c.primary_branch_id;


-- ============================================================
-- 06. CROSS-SELL BASE FLAGS — SQL PREPARATION
-- ============================================================

-- 6.1 Active customers with reusable account/card opportunity flags.
--
-- These flags are intentionally kept at customer grain.
-- Final percentages and segment comparisons belong in DAX.
--
-- Loan cross-sell logic is not finalized here because a historical
-- loan is not automatically a current loan relationship.

WITH account_status AS (
    SELECT
        a.customer_id,
        COUNT(*) FILTER (
            WHERE a.account_status = 'ACTIVE'
        ) AS active_account_count
    FROM core.accounts AS a
    GROUP BY a.customer_id
),

card_status AS (
    SELECT
        ca.customer_id,
        COUNT(*) FILTER (
            WHERE ca.card_status = 'ACTIVE'
        ) AS active_card_count
    FROM banking.cards AS ca
    GROUP BY ca.customer_id
)

SELECT
    c.customer_id,
    c.customer_type,

    CASE
        WHEN c.customer_type = 'INDIVIDUAL'
            THEN COALESCE(c.employment_status, 'UNKNOWN')
        WHEN c.customer_type = 'BUSINESS'
            THEN COALESCE(c.company_size, 'UNKNOWN')
        ELSE 'UNKNOWN'
    END AS customer_segment,

    COALESCE(a.active_account_count, 0)
        AS active_account_count,

    COALESCE(ca.active_card_count, 0)
        AS active_card_count,

    CASE
        WHEN COALESCE(a.active_account_count, 0) > 0
         AND COALESCE(ca.active_card_count, 0) = 0
            THEN 1
        ELSE 0
    END AS account_without_active_card_flag

FROM core.customers AS c

LEFT JOIN account_status AS a
    ON a.customer_id = c.customer_id

LEFT JOIN card_status AS ca
    ON ca.customer_id = c.customer_id

WHERE c.customer_status = 'ACTIVE';


-- ============================================================
-- 07. DOWNSTREAM ANALYTICAL HANDOFF
-- ============================================================
--
-- PYTHON / PANDAS
-- Use the customer-level bases above for:
--
-- - income distributions
-- - age distributions
-- - median / percentile analysis
-- - outliers
-- - tenure × product-depth exploration
-- - age / income / product-depth comparisons
-- - statistical comparisons between segments
--
-- DAX / POWER BI
-- Use the same customer grain for dynamic measures such as:
--
-- - Active Customers
-- - Customer Share %
-- - Average Tenure
-- - Average Active Accounts
-- - Average Active Cards
-- - Card Penetration %
-- - Account-without-card %
-- - Average Lifetime Distinct Products
--
-- Filters can then change dynamically by:
--
-- - year / cohort
-- - customer type
-- - employment status
-- - company size
-- - region
-- - branch
--
-- ============================================================
-- END
-- ============================================================
