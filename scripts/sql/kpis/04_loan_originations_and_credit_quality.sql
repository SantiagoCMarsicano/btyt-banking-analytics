-- ============================================================
-- BTYT — LOAN ORIGINATIONS AND CREDIT QUALITY
-- File: 04_loan_originations_and_credit_quality.sql
-- PostgreSQL | Read-only | Run one statement at a time
-- ============================================================
-- SEQUENCE
-- 01: bank performance; 02: growth and income mix;
-- 03: funding and credit loss; 04: originations and loan-level risk.
-- Catalog IDs are stable identifiers, not SQL file numbers.
--
-- KPI-07 | 30+ DPD Exposure Rate | Tier S | Tool: Power BI
-- KPI-28 | Loan Origination Amount | Tier A | Tool: Power BI
-- KPI-29 | 90+ DPD Exposure Rate | Tier A | Tool: Power BI
-- KPI-30 | Payment Shortfall Rate | Tier B | Tool: Python
-- KPI-31 | Cure Rate | Tier B | Tool: Python
-- KPI-32 | Roll-to-30+ Rate | Tier A | Tool: Python
-- PW = Power BI; E = Excel; T = Tableau; S = Superset; P = Python.
-- Assignments follow kpi_catalog_v2_expanded.md, superseding older
-- tool suggestions in the exploratory loan SQL.
--
-- SOURCES (columns grounded in the existing 03_loans_fixed.sql)
-- banking.loans: one row per loan; origination_year provides annual
-- origination precision. Do not invent a monthly origination date.
-- banking.loan_monthly_snapshot: one row per loan and calendar month.
-- UYU and USD remain separate. No implicit FX conversion is applied.
-- Snapshot exposure is not the average balance from performance.*.
-- Do not reconcile those different measures by assuming equal scope.
-- No current loan_status filter is applied to historical snapshots.
--
-- DEFINITIONS
-- 30+ means days_past_due >= 30; 90+ means >= 90 (inclusive).
-- Exposure rates are balance-weighted; transition rates are loan counts.
-- Payment shortfall = max(scheduled - actual, 0) PER LOAN-MONTH;
-- overpayments on one loan must not cancel another loan's shortfall.
-- Cure: prior DPD > 0 becomes DPD = 0 in the next calendar month.
-- Roll-to-30+: prior DPD < 30 becomes DPD >= 30 in the next month.
-- Transition cohort: positive prior balance and valid DPD, followed
-- by an observed next-month row with valid DPD and nonnegative balance.
-- Zero current balance is allowed if the snapshot is observed.
-- Missing next snapshots are excluded, counted, and never called cured.
-- These are conditional observed-cohort rates, not default probabilities.
-- Do not sum exposure snapshots or average monthly rates over time.
-- Round only final results.

-- ============================================================
-- 00. SOURCE QUALITY CHECKS
-- ============================================================
-- Expect zero issues. Fix duplicate keys or orphan snapshots before
-- subsequent queries: joins would otherwise multiply or omit loans.
-- Invalid financial inputs suppress the relevant monthly KPI below.
SELECT 'duplicate_loan_ids' AS check_name, COUNT(*) AS issue_count
FROM (
    SELECT loan_id FROM banking.loans GROUP BY loan_id HAVING COUNT(*) > 1
) AS duplicates
UNION ALL
SELECT 'duplicate_loan_months', COUNT(*)
FROM (
    SELECT loan_id, DATE_TRUNC('month', year_month)
    FROM banking.loan_monthly_snapshot
    GROUP BY loan_id, DATE_TRUNC('month', year_month)
    HAVING COUNT(*) > 1
) AS duplicates
UNION ALL
SELECT 'invalid_loan_master_rows', COUNT(*)
FROM banking.loans
WHERE loan_id IS NULL OR currency IS NULL OR origination_year IS NULL
   OR original_amount IS NULL OR original_amount < 0
UNION ALL
SELECT 'orphan_snapshot_rows', COUNT(*)
FROM banking.loan_monthly_snapshot AS s
WHERE NOT EXISTS (SELECT 1 FROM banking.loans AS l WHERE l.loan_id = s.loan_id)
UNION ALL
SELECT 'invalid_snapshot_keys', COUNT(*)
FROM banking.loan_monthly_snapshot
WHERE loan_id IS NULL OR year_month IS NULL
UNION ALL
SELECT 'invalid_exposure_or_dpd_rows', COUNT(*)
FROM banking.loan_monthly_snapshot
WHERE outstanding_balance IS NULL OR outstanding_balance < 0
   OR days_past_due IS NULL OR days_past_due < 0
UNION ALL
SELECT 'invalid_payment_rows', COUNT(*)
FROM banking.loan_monthly_snapshot
WHERE scheduled_payment IS NULL OR actual_payment IS NULL
   OR scheduled_payment < 0 OR actual_payment < 0;

-- ============================================================
-- 01. ANNUAL ORIGINATIONS BY CURRENCY
-- ============================================================
-- Question: How much principal was originated in each year?
-- Use the loan table directly: joining monthly snapshots would repeat
-- original principal. Retain closed loans in their origination cohort.
SELECT
    origination_year,
    currency,
    COUNT(*) AS originated_loans,
    -- KPI-28 | Loan Origination Amount | Tier A | Tool: Power BI
    CASE WHEN COUNT(*) FILTER (
        WHERE original_amount IS NULL OR original_amount < 0
    ) = 0 THEN ROUND(SUM(original_amount::NUMERIC), 2)
    END AS loan_origination_amount
FROM banking.loans
GROUP BY origination_year, currency
ORDER BY origination_year, currency;

-- ============================================================
-- 02. MONTHLY EXPOSURE AND PAYMENT SHORTFALL BY CURRENCY
-- ============================================================
-- Question: What share of exposure is 30+/90+ DPD, and how much of
-- scheduled payments was not covered by actual payments?
-- NULL is not treated as zero. An invalid row suppresses only its
-- corresponding KPI family for that month/currency.
WITH monthly AS (
    SELECT
        DATE_TRUNC('month', s.year_month)::DATE AS report_month,
        l.currency,
        COUNT(*) AS loan_rows,
        COUNT(*) FILTER (
            WHERE s.outstanding_balance IS NULL OR s.outstanding_balance < 0
               OR s.days_past_due IS NULL OR s.days_past_due < 0
        ) AS invalid_exposure_rows,
        COUNT(*) FILTER (
            WHERE s.scheduled_payment IS NULL OR s.actual_payment IS NULL
               OR s.scheduled_payment < 0 OR s.actual_payment < 0
        ) AS invalid_payment_rows,
        SUM(s.outstanding_balance::NUMERIC) AS total_exposure,
        SUM(CASE WHEN s.days_past_due >= 30
            THEN s.outstanding_balance::NUMERIC ELSE 0 END) AS exposure_30_plus,
        SUM(CASE WHEN s.days_past_due >= 90
            THEN s.outstanding_balance::NUMERIC ELSE 0 END) AS exposure_90_plus,
        SUM(s.scheduled_payment::NUMERIC) AS scheduled_payment,
        SUM(CASE WHEN s.scheduled_payment >= 0 AND s.actual_payment >= 0
            THEN GREATEST(s.scheduled_payment::NUMERIC - s.actual_payment::NUMERIC, 0)
        END) AS payment_shortfall
    FROM banking.loan_monthly_snapshot AS s
    JOIN banking.loans AS l ON l.loan_id = s.loan_id
    GROUP BY DATE_TRUNC('month', s.year_month)::DATE, l.currency
)
SELECT
    report_month, currency, loan_rows,
    invalid_exposure_rows, invalid_payment_rows,
    -- Supporting amounts are NULL when the group contains invalid inputs.
    CASE WHEN invalid_exposure_rows = 0 THEN ROUND(total_exposure, 2) END
        AS total_outstanding_exposure,
    CASE WHEN invalid_exposure_rows = 0 THEN ROUND(exposure_30_plus, 2) END
        AS outstanding_exposure_30_plus,
    CASE WHEN invalid_exposure_rows = 0 THEN ROUND(exposure_90_plus, 2) END
        AS outstanding_exposure_90_plus,
    -- KPI-07 | 30+ DPD Exposure Rate | Tier S | Tool: Power BI
    CASE WHEN invalid_exposure_rows = 0 AND total_exposure > 0 THEN
        ROUND(100.0 * exposure_30_plus / total_exposure, 2)
    END AS dpd_30_plus_exposure_rate_pct,
    -- KPI-29 | 90+ DPD Exposure Rate | Tier A | Tool: Power BI
    CASE WHEN invalid_exposure_rows = 0 AND total_exposure > 0 THEN
        ROUND(100.0 * exposure_90_plus / total_exposure, 2)
    END AS dpd_90_plus_exposure_rate_pct,
    CASE WHEN invalid_payment_rows = 0 THEN ROUND(scheduled_payment, 2) END
        AS total_scheduled_payment,
    CASE WHEN invalid_payment_rows = 0 THEN ROUND(payment_shortfall, 2) END
        AS total_payment_shortfall,
    -- KPI-30 | Payment Shortfall Rate | Tier B | Tool: Python
    CASE WHEN invalid_payment_rows = 0 AND scheduled_payment > 0 THEN
        ROUND(100.0 * payment_shortfall / scheduled_payment, 2)
    END AS payment_shortfall_rate_pct
FROM monthly
ORDER BY report_month, currency;

-- ============================================================
-- 03. CONSECUTIVE-MONTH CURE AND ROLL RATES BY CURRENCY
-- ============================================================
-- Question: Among observable next-month transitions, how many loans
-- recover to current or cross the 30-day threshold?
-- Exact month joins prevent gaps from becoming false transitions.
-- Review excluded counts: exits can cause selection bias.
-- The final source month has no follow-up and normally has NULL rates.
WITH snapshots AS (
    SELECT
        loan_id, DATE_TRUNC('month', year_month)::DATE AS report_month,
        outstanding_balance, days_past_due
    FROM banking.loan_monthly_snapshot
),
pairs AS (
    SELECT
        prev.report_month AS cohort_month,
        (prev.report_month + INTERVAL '1 month')::DATE AS outcome_month,
        l.currency,
        prev.days_past_due AS prior_dpd,
        nxt.days_past_due AS next_dpd,
        (nxt.loan_id IS NOT NULL AND nxt.days_past_due >= 0
            AND nxt.outstanding_balance >= 0) IS TRUE AS observed_valid_next
    FROM snapshots AS prev
    JOIN banking.loans AS l ON l.loan_id = prev.loan_id
    LEFT JOIN snapshots AS nxt
        ON nxt.loan_id = prev.loan_id
       AND nxt.report_month = (prev.report_month + INTERVAL '1 month')::DATE
    WHERE prev.outstanding_balance > 0 AND prev.days_past_due >= 0
),
cohorts AS (
    SELECT
        cohort_month, outcome_month, currency,
        COUNT(*) FILTER (WHERE prior_dpd > 0) AS cure_candidate_loans,
        COUNT(*) FILTER (WHERE prior_dpd > 0 AND NOT observed_valid_next)
            AS cure_excluded_missing_or_invalid_next,
        COUNT(*) FILTER (WHERE prior_dpd > 0 AND observed_valid_next)
            AS cure_eligible_loans,
        COUNT(*) FILTER (
            WHERE prior_dpd > 0 AND observed_valid_next AND next_dpd = 0
        ) AS cured_loans,
        COUNT(*) FILTER (WHERE prior_dpd < 30) AS roll_candidate_loans,
        COUNT(*) FILTER (WHERE prior_dpd < 30 AND NOT observed_valid_next)
            AS roll_excluded_missing_or_invalid_next,
        COUNT(*) FILTER (WHERE prior_dpd < 30 AND observed_valid_next)
            AS roll_eligible_loans,
        COUNT(*) FILTER (
            WHERE prior_dpd < 30 AND observed_valid_next AND next_dpd >= 30
        ) AS rolled_to_30_plus_loans
    FROM pairs
    GROUP BY cohort_month, outcome_month, currency
)
SELECT
    cohort_month, outcome_month, currency,
    cure_candidate_loans, cure_excluded_missing_or_invalid_next,
    cure_eligible_loans, cured_loans,
    -- KPI-31 | Cure Rate | Tier B | Tool: Python
    ROUND(100.0 * cured_loans / NULLIF(cure_eligible_loans, 0), 2)
        AS cure_rate_pct,
    roll_candidate_loans, roll_excluded_missing_or_invalid_next,
    roll_eligible_loans, rolled_to_30_plus_loans,
    -- KPI-32 | Roll-to-30+ Rate | Tier A | Tool: Python
    ROUND(100.0 * rolled_to_30_plus_loans / NULLIF(roll_eligible_loans, 0), 2)
        AS roll_to_30_plus_rate_pct
FROM cohorts
ORDER BY cohort_month, currency;

-- ============================================================
-- KPI OWNERSHIP MAP — FREEZE VERSION
-- ============================================================
-- Tier = portfolio / decision priority; Tool = primary delivery home.
-- PostgreSQL remains the calculation layer for every KPI in this file.
--
-- TIER S
--   Power BI: KPI-07 30+ DPD Exposure Rate
--
-- TIER A
--   Power BI: KPI-28 Loan Origination Amount, KPI-29 90+ DPD Exposure Rate
--   Python: KPI-32 Roll-to-30+ Rate
--
-- TIER B
--   Python: KPI-30 Payment Shortfall Rate, KPI-31 Cure Rate
-- ============================================================
