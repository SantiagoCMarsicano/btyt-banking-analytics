-- ============================================================
-- BTYT — LOANS & CREDIT QUALITY ANALYTICS
-- File: 03_loans.sql
-- Architecture-aligned design
--
-- Purpose:
-- Prepare reusable loan and loan-month analytical structure for
-- credit-quality analysis without precomputing every BI question.
--
-- PostgreSQL | Read-only analytical queries
-- ============================================================
--
-- MAIN QUESTION
-- What is in BTYT's loan portfolio, how does credit quality evolve,
-- and what analytical grains should downstream tools consume?
--
-- TOOL OWNERSHIP
--
-- SQL:
-- - portfolio diagnostics
-- - origination cohorts
-- - one-row-per-loan analytical base
-- - one-row-per-loan-month analytical base
-- - latest-snapshot analytical base
-- - DPD buckets and stable payment fields
--
-- DAX / Power BI:
-- - dynamic delinquency ratios
-- - outstanding-balance shares
-- - arrears ratios
-- - current portfolio KPIs
-- - filter-context comparisons
--
-- Python:
-- - DPD distributions
-- - roll rates / transitions
-- - pre-default trajectories
-- - vintage curves
-- - outliers and statistical comparisons
--
-- IMPORTANT:
-- UYU and USD monetary values must remain separated unless an
-- explicit FX conversion is introduced.
--
-- TEMPORAL STATUS RULE
-- loans.loan_status is the current/final contractual status at the
-- 2026-12-31 analytical cutoff. It is NOT a month-specific status.
-- loan_monthly_snapshot.delinquency_status is the monthly credit-quality
-- state and should be used for historical month-by-month risk analysis.
--
-- ============================================================
-- 01. PORTFOLIO STRUCTURE — SQL EXPLORATION
-- ============================================================

-- 1.1 Loan portfolio by product, currency and status.
-- Compact structural diagnostic before building reusable bases.

SELECT
    p.product_name,
    p.product_family,
    l.currency,
    l.loan_status,

    COUNT(*) AS loan_count,

    ROUND(
        SUM(l.original_amount)::NUMERIC,
        2
    ) AS total_original_amount,

    ROUND(
        AVG(l.original_amount)::NUMERIC,
        2
    ) AS avg_original_amount,

    ROUND(
        AVG(l.term_months)::NUMERIC,
        2
    ) AS avg_term_months,

    ROUND(
        AVG(l.initial_interest_rate)::NUMERIC,
        4
    ) AS avg_initial_interest_rate

FROM banking.loans AS l

JOIN core.products AS p
    ON p.product_id = l.product_id

GROUP BY
    p.product_name,
    p.product_family,
    l.currency,
    l.loan_status

ORDER BY
    l.currency,
    p.product_name,
    loan_count DESC;


-- ============================================================
-- 02. ORIGINATION OVER TIME — SQL
-- ============================================================

-- 2.1 Origination year × product × currency.
-- Monetary values remain separated by currency.

SELECT
    l.origination_year,
    p.product_name,
    l.currency,

    COUNT(*) AS loans_originated,

    COUNT(DISTINCT l.customer_id)
        AS borrowing_customers,

    ROUND(
        SUM(l.original_amount)::NUMERIC,
        2
    ) AS total_original_amount,

    ROUND(
        AVG(l.original_amount)::NUMERIC,
        2
    ) AS avg_original_amount,

    ROUND(
        AVG(l.initial_interest_rate)::NUMERIC,
        4
    ) AS avg_initial_interest_rate

FROM banking.loans AS l

JOIN core.products AS p
    ON p.product_id = l.product_id

GROUP BY
    l.origination_year,
    p.product_name,
    l.currency

ORDER BY
    l.origination_year,
    l.currency,
    loans_originated DESC;


-- ============================================================
-- 03. ORIGINATION COHORTS — SQL
-- ============================================================

-- 3.1 Cohort × product with current loan-status composition.
--
-- Interpretation caution:
-- older cohorts have had more time to reach terminal states.

SELECT
    l.origination_year AS cohort_year,
    p.product_name,
    l.currency,

    COUNT(*) AS cohort_loans,

    COUNT(*) FILTER (
        WHERE l.loan_status = 'ACTIVE'
    ) AS active_loans,

    COUNT(*) FILTER (
        WHERE l.loan_status = 'PAID_OFF'
    ) AS paid_off_loans,

    COUNT(*) FILTER (
        WHERE l.loan_status = 'DEFAULTED'
    ) AS defaulted_loans,

    COUNT(*) FILTER (
        WHERE l.loan_status = 'RESTRUCTURED'
    ) AS restructured_loans,

    COUNT(*) FILTER (
        WHERE l.loan_status = 'WRITTEN_OFF'
    ) AS written_off_loans

FROM banking.loans AS l

JOIN core.products AS p
    ON p.product_id = l.product_id

GROUP BY
    l.origination_year,
    p.product_name,
    l.currency

ORDER BY
    cohort_year,
    l.currency,
    cohort_loans DESC;


-- ============================================================
-- 04. LOAN ANALYTICAL BASE — SQL PREPARATION
-- ============================================================

-- 4.1 One row per loan.
--
-- Candidate reusable dataset for BI and downstream analysis.
--
-- Grain:
-- 1 row = 1 loan

SELECT
    l.loan_id,
    l.customer_id,
    l.product_id,
    l.branch_id,

    l.origination_year,
    l.currency,
    l.original_amount,
    l.term_months,
    l.rate_type,
    l.initial_interest_rate,
    l.loan_status,
    l.closing_year,

    CASE
        WHEN l.closing_year IS NULL THEN 1
        ELSE 0
    END AS is_open_at_cutoff,

    CASE
        WHEN l.closing_year IS NOT NULL
            THEN l.closing_year - l.origination_year
        ELSE 2026 - l.origination_year
    END AS loan_age_years,

    p.product_name,
    p.product_family,
    p.target_customer_type,

    c.customer_type,

    CASE
        WHEN c.customer_type = 'INDIVIDUAL'
            THEN COALESCE(c.employment_status, 'UNKNOWN')
        WHEN c.customer_type = 'BUSINESS'
            THEN COALESCE(c.company_size, 'UNKNOWN')
        ELSE 'UNKNOWN'
    END AS customer_segment,

    c.registration_year AS customer_registration_year,

    b.branch_name,
    b.branch_type,
    b.branch_size,
    b.department,
    b.region

FROM banking.loans AS l

JOIN core.products AS p
    ON p.product_id = l.product_id

JOIN core.customers AS c
    ON c.customer_id = l.customer_id

JOIN core.branches AS b
    ON b.branch_id = l.branch_id;


-- ============================================================
-- 05. LOAN-MONTH ANALYTICAL BASE — SQL PREPARATION
-- ============================================================

-- 5.1 One row per loan × month.
--
-- This is the principal reusable credit-quality dataset.
--
-- Grain:
-- 1 row = 1 loan × 1 year_month
--
-- Stable derived fields:
-- - payment_shortfall
-- - payment_ratio
-- - has_arrears
-- - is_delinquent
-- - dpd_bucket
--
-- These fields are descriptive and reusable.
-- Final portfolio ratios should remain dynamic in DAX.
-- loan_status_at_cutoff is repeated only as a master attribute; it must
-- not be interpreted as the status that applied in each historical month.

SELECT
    lms.loan_id,
    lms.year_month,

    lms.outstanding_balance,
    lms.current_interest_rate,
    lms.scheduled_payment,
    lms.actual_payment,
    lms.days_past_due,
    lms.delinquency_status,
    lms.arrears_amount,

    GREATEST(
        COALESCE(lms.scheduled_payment, 0)
        - COALESCE(lms.actual_payment, 0),
        0
    ) AS payment_shortfall,

    CASE
        WHEN lms.scheduled_payment IS NULL
          OR lms.scheduled_payment = 0
            THEN NULL
        ELSE
            lms.actual_payment
            / NULLIF(lms.scheduled_payment, 0)
    END AS payment_ratio,

    CASE
        WHEN COALESCE(lms.arrears_amount, 0) > 0
            THEN 1
        ELSE 0
    END AS has_arrears,

    CASE
        WHEN COALESCE(lms.days_past_due, 0) > 0
            THEN 1
        ELSE 0
    END AS is_delinquent,

    CASE
        WHEN lms.days_past_due IS NULL
            THEN 'UNKNOWN'
        WHEN lms.days_past_due = 0
            THEN 'CURRENT'
        WHEN lms.days_past_due BETWEEN 1 AND 30
            THEN 'DPD_1_30'
        WHEN lms.days_past_due BETWEEN 31 AND 60
            THEN 'DPD_31_60'
        WHEN lms.days_past_due BETWEEN 61 AND 90
            THEN 'DPD_61_90'
        ELSE 'DPD_90_PLUS'
    END AS dpd_bucket,

    l.origination_year,
    l.currency,
    l.original_amount,
    l.term_months,
    l.rate_type,
    l.initial_interest_rate,
    l.loan_status AS loan_status_at_cutoff,
    l.closing_year,

    CASE
        WHEN l.closing_year IS NULL THEN 1
        ELSE 0
    END AS is_open_at_cutoff,

    p.product_name,
    p.product_family,

    c.customer_type,

    CASE
        WHEN c.customer_type = 'INDIVIDUAL'
            THEN COALESCE(c.employment_status, 'UNKNOWN')
        WHEN c.customer_type = 'BUSINESS'
            THEN COALESCE(c.company_size, 'UNKNOWN')
        ELSE 'UNKNOWN'
    END AS customer_segment,

    b.branch_id,
    b.branch_name,
    b.department,
    b.region

FROM banking.loan_monthly_snapshot AS lms

JOIN banking.loans AS l
    ON l.loan_id = lms.loan_id

JOIN core.products AS p
    ON p.product_id = l.product_id

JOIN core.customers AS c
    ON c.customer_id = l.customer_id

JOIN core.branches AS b
    ON b.branch_id = l.branch_id;


-- ============================================================
-- 06. LATEST PORTFOLIO SNAPSHOT — SQL PREPARATION
-- ============================================================

-- 6.1 One row per loan present in the latest available snapshot.
--
-- This base intentionally keeps every loan represented in the latest snapshot,
-- including contracts that may resolve in that same month. Use
-- is_open_at_cutoff = 1 when the business question is strictly the open portfolio.
--
-- Grain:
-- 1 row = 1 loan at latest year_month

WITH latest_month AS (
    SELECT
        MAX(lms.year_month) AS year_month
    FROM banking.loan_monthly_snapshot AS lms
)

SELECT
    lms.year_month,
    lms.loan_id,

    lms.outstanding_balance,
    lms.current_interest_rate,
    lms.scheduled_payment,
    lms.actual_payment,
    lms.days_past_due,
    lms.delinquency_status,
    lms.arrears_amount,

    GREATEST(
        COALESCE(lms.scheduled_payment, 0)
        - COALESCE(lms.actual_payment, 0),
        0
    ) AS payment_shortfall,

    CASE
        WHEN COALESCE(lms.days_past_due, 0) > 0
            THEN 1
        ELSE 0
    END AS is_delinquent,

    CASE
        WHEN lms.days_past_due IS NULL
            THEN 'UNKNOWN'
        WHEN lms.days_past_due = 0
            THEN 'CURRENT'
        WHEN lms.days_past_due BETWEEN 1 AND 30
            THEN 'DPD_1_30'
        WHEN lms.days_past_due BETWEEN 31 AND 60
            THEN 'DPD_31_60'
        WHEN lms.days_past_due BETWEEN 61 AND 90
            THEN 'DPD_61_90'
        ELSE 'DPD_90_PLUS'
    END AS dpd_bucket,

    l.customer_id,
    l.product_id,
    l.branch_id,
    l.origination_year,
    l.currency,
    l.original_amount,
    l.term_months,
    l.rate_type,
    l.initial_interest_rate,
    l.loan_status AS loan_status_at_cutoff,
    l.closing_year,

    CASE
        WHEN l.closing_year IS NULL THEN 1
        ELSE 0
    END AS is_open_at_cutoff,

    p.product_name,
    p.product_family,

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

FROM banking.loan_monthly_snapshot AS lms

JOIN latest_month AS lm
    ON lm.year_month = lms.year_month

JOIN banking.loans AS l
    ON l.loan_id = lms.loan_id

JOIN core.products AS p
    ON p.product_id = l.product_id

JOIN core.customers AS c
    ON c.customer_id = l.customer_id

JOIN core.branches AS b
    ON b.branch_id = l.branch_id;


-- ============================================================
-- 07. CURRENT CREDIT-QUALITY DIAGNOSTIC — SQL EXPLORATION
-- ============================================================

-- 7.1 Latest snapshot by product, currency and DPD bucket.
--
-- This remains useful as a SQL validation query.
-- The equivalent dashboard ratios should later be implemented in DAX.

WITH latest_month AS (
    SELECT
        MAX(lms.year_month) AS year_month
    FROM banking.loan_monthly_snapshot AS lms
),

latest_portfolio AS (
    SELECT
        lms.loan_id,
        lms.outstanding_balance,
        lms.arrears_amount,
        lms.days_past_due,

        CASE
            WHEN lms.days_past_due IS NULL
                THEN 'UNKNOWN'
            WHEN lms.days_past_due = 0
                THEN 'CURRENT'
            WHEN lms.days_past_due BETWEEN 1 AND 30
                THEN 'DPD_1_30'
            WHEN lms.days_past_due BETWEEN 31 AND 60
                THEN 'DPD_31_60'
            WHEN lms.days_past_due BETWEEN 61 AND 90
                THEN 'DPD_61_90'
            ELSE 'DPD_90_PLUS'
        END AS dpd_bucket

    FROM banking.loan_monthly_snapshot AS lms

    JOIN latest_month AS lm
        ON lm.year_month = lms.year_month
)

SELECT
    p.product_name,
    l.currency,
    lp.dpd_bucket,

    COUNT(*) AS loan_count,

    ROUND(
        SUM(lp.outstanding_balance)::NUMERIC,
        2
    ) AS outstanding_balance,

    ROUND(
        SUM(lp.arrears_amount)::NUMERIC,
        2
    ) AS arrears_amount

FROM latest_portfolio AS lp

JOIN banking.loans AS l
    ON l.loan_id = lp.loan_id

JOIN core.products AS p
    ON p.product_id = l.product_id

WHERE l.closing_year IS NULL

GROUP BY
    p.product_name,
    l.currency,
    lp.dpd_bucket

ORDER BY
    l.currency,
    p.product_name,
    CASE lp.dpd_bucket
        WHEN 'CURRENT' THEN 1
        WHEN 'DPD_1_30' THEN 2
        WHEN 'DPD_31_60' THEN 3
        WHEN 'DPD_61_90' THEN 4
        WHEN 'DPD_90_PLUS' THEN 5
        ELSE 6
    END;


-- ============================================================
-- 08. TEMPORAL CREDIT-QUALITY BASELINE — SQL
-- ============================================================

-- 8.1 Monthly portfolio totals by currency.
--
-- This is a compact SQL validation series in contractual currency.
-- Product, branch, segment and other dimensions should normally
-- remain filterable in the reusable loan-month dataset.
--
-- performance.average_loan_balance is UYU-equivalent, so native UYU/USD
-- balances in this section do not reconcile directly until FX conversion.

SELECT
    lms.year_month,
    l.currency,

    COUNT(*) AS loan_month_rows,

    ROUND(
        SUM(lms.outstanding_balance)::NUMERIC,
        2
    ) AS outstanding_balance,

    ROUND(
        SUM(lms.arrears_amount)::NUMERIC,
        2
    ) AS arrears_amount,

    ROUND(
        AVG(lms.days_past_due)::NUMERIC,
        2
    ) AS avg_days_past_due,

    COUNT(*) FILTER (
        WHERE COALESCE(lms.days_past_due, 0) > 0
    ) AS delinquent_loan_rows

FROM banking.loan_monthly_snapshot AS lms

JOIN banking.loans AS l
    ON l.loan_id = lms.loan_id

GROUP BY
    lms.year_month,
    l.currency

ORDER BY
    lms.year_month,
    l.currency;


-- ============================================================
-- 09. COVERAGE & CONSISTENCY CHECKS — SQL DIAGNOSTICS
-- ============================================================

-- 9.1 Snapshot coverage.

SELECT
    MIN(lms.year_month) AS first_snapshot_month,
    MAX(lms.year_month) AS last_snapshot_month,
    COUNT(DISTINCT lms.year_month) AS month_count,
    COUNT(*) AS snapshot_rows,
    COUNT(DISTINCT lms.loan_id) AS loans_with_snapshots
FROM banking.loan_monthly_snapshot AS lms;


-- 9.2 Loan-status / closing-year consistency.
-- Diagnostic only.
--
-- Master loan_status is the contractual status at the 2026-12-31 cutoff.
-- ACTIVE must remain open. PAID_OFF and WRITTEN_OFF are terminal.
-- DEFAULTED and RESTRUCTURED may be either open at cutoff or closed /
-- materially resolved, so NULL closing_year is valid for those states.

SELECT
    l.loan_id,
    l.loan_status,
    l.origination_year,
    l.closing_year
FROM banking.loans AS l
WHERE
       (l.loan_status = 'ACTIVE' AND l.closing_year IS NOT NULL)
    OR (
        l.loan_status IN ('PAID_OFF', 'WRITTEN_OFF')
        AND l.closing_year IS NULL
    )
    OR (
        l.closing_year IS NOT NULL
        AND l.closing_year < l.origination_year
    )
    OR (
        l.closing_year IS NOT NULL
        AND l.closing_year > 2026
    )
ORDER BY l.loan_id;


-- 9.2.1 Monthly delinquency-status / DPD consistency.
-- Expected result: zero rows.

SELECT
    lms.loan_id,
    lms.year_month,
    lms.days_past_due,
    lms.delinquency_status
FROM banking.loan_monthly_snapshot AS lms
WHERE
       lms.days_past_due IS NULL
    OR lms.delinquency_status IS NULL
    OR lms.delinquency_status NOT IN (
        'CURRENT',
        'DPD_1_30',
        'DPD_31_60',
        'DPD_61_90',
        'DPD_90_PLUS'
    )
    OR (lms.days_past_due = 0
        AND lms.delinquency_status <> 'CURRENT')
    OR (lms.days_past_due BETWEEN 1 AND 30
        AND lms.delinquency_status <> 'DPD_1_30')
    OR (lms.days_past_due BETWEEN 31 AND 60
        AND lms.delinquency_status <> 'DPD_31_60')
    OR (lms.days_past_due BETWEEN 61 AND 90
        AND lms.delinquency_status <> 'DPD_61_90')
    OR (lms.days_past_due > 90
        AND lms.delinquency_status <> 'DPD_90_PLUS')
ORDER BY
    lms.year_month,
    lms.loan_id;


-- 9.3 Duplicate loan-month check.
-- The relational model PK should make this return zero rows.

SELECT
    lms.loan_id,
    lms.year_month,
    COUNT(*) AS row_count
FROM banking.loan_monthly_snapshot AS lms
GROUP BY
    lms.loan_id,
    lms.year_month
HAVING COUNT(*) > 1
ORDER BY row_count DESC;


-- ============================================================
-- 10. DOWNSTREAM ANALYTICAL HANDOFF
-- ============================================================
--
-- DAX / POWER BI
--
-- Build dynamic measures over the reusable loan / loan-month bases:
--
-- - Loan Count
-- - Outstanding Balance
-- - Average Outstanding Balance
-- - Portfolio Share %
-- - Delinquent Loan Count
-- - Delinquent Loan %
-- - Delinquent Balance
-- - Delinquent Balance %
-- - 30+ DPD Balance
-- - DPD_90_PLUS Balance
-- - Arrears Balance
-- - Arrears / Outstanding %
-- - Average DPD
-- - Average Current Interest Rate
-- - Payment Shortfall
-- - Origination Growth
--
-- These measures should react to:
--
-- - month / year
-- - product
-- - currency
-- - customer type
-- - customer segment
-- - branch
-- - region
-- - loan status at cutoff
-- - monthly delinquency status / DPD bucket
--
-- PYTHON / PANDAS / JUPYTER
--
-- Use the loan-month base when questions become longitudinal or
-- statistical:
--
-- - DPD distributions
-- - transition matrices / roll rates
-- - pre-default trajectories
-- - recovery trajectories
-- - vintage curves
-- - payment-shortfall persistence
-- - rate / delinquency comparisons
-- - outliers
-- - exploratory regressions
--
-- PART II
--
-- Reuse this history only after defining:
--
-- - target
-- - observation window
-- - performance window
-- - temporal split
-- - leakage rules
--
-- ============================================================
-- END
-- ============================================================