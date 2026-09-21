-- ============================================================
-- BTYT — FUNDING AND CREDIT LOSS
-- File: 03_funding_and_credit_loss.sql
-- PostgreSQL | Read-only | Run one statement at a time
-- ============================================================
-- Source: performance.bank_monthly_performance
-- Grain: one BTYT row per calendar month.
-- Monetary amounts: UYU-equivalent reporting values.
-- Assignments follow kpi_catalog_v2_expanded.md.
--
-- NEW KPI CALCULATIONS
-- KPI-06 | Credit Loss Ratio | Tier S | Tool: Power BI
-- KPI-12 | Loan-to-Deposit Operating Ratio | Tier S | Tool: Power BI
-- KPI-25 | Deposit Growth YoY | Tier A | Tool: Power BI
--
-- SUPPORTING KPIs ALREADY INTRODUCED IN FILE 01
-- KPI-02 | Average Deposits | Tier S | Tool: Power BI
-- KPI-03 | Average Loan Balance | Tier S | Tool: Power BI
--
-- PW = Power BI; E = Excel; T = Tableau; S = Superset; P = Python.
-- Tiers express priority; tools identify the intended main output.
--
-- MEASUREMENT RULES
-- Deposits and loan balances are monthly averages, not additive flows.
-- Annual balances are the unweighted mean of 12 monthly averages;
-- they are not daily-weighted annual average balances.
-- Credit loss is a flow: sum it for annual reporting.
-- Monthly credit loss ratio = monthly loss / monthly average loans.
-- Annual credit loss ratio = annual loss / mean monthly average loans.
-- Monthly ratios are NOT annualized and must not be summed or averaged
-- to obtain the annual ratio. Compare like periods.
-- Loan-to-deposit is an operating measure, not a regulatory liquidity
-- ratio. No undocumented target or risk threshold is applied.
-- Ratios and growth require a strictly positive denominator.
-- A missing prior-year observation produces NULL growth, not zero.

-- ============================================================
-- 00. CHECK MONTHLY GRAIN, COMPLETENESS AND DENOMINATORS
-- ============================================================
-- Resolve duplicate months, NULL months, missing months and incomplete
-- rows before interpreting results. Nonpositive balances make the
-- relevant ratios undefined; they are reported as NULL below.
WITH coverage AS (
    SELECT
        COUNT(*) AS rows_observed,
        COUNT(DISTINCT DATE_TRUNC('month', year_month)) AS distinct_months,
        MIN(year_month)::DATE AS first_month,
        MAX(year_month)::DATE AS last_month,
        COUNT(*) FILTER (WHERE year_month IS NULL) AS null_month_rows,
        COUNT(*) FILTER (
            WHERE average_deposits IS NULL
               OR average_loan_balance IS NULL OR credit_loss IS NULL
        ) AS incomplete_financial_rows,
        COUNT(*) FILTER (WHERE average_deposits <= 0)
            AS nonpositive_deposit_rows,
        COUNT(*) FILTER (WHERE average_loan_balance <= 0)
            AS nonpositive_loan_rows
    FROM performance.bank_monthly_performance
)
SELECT
    c.*,
    rows_observed - null_month_rows - distinct_months AS duplicate_months,
    (SELECT COUNT(*) FROM GENERATE_SERIES(
        DATE_TRUNC('month', c.first_month),
        DATE_TRUNC('month', c.last_month), INTERVAL '1 month'
    )) - distinct_months AS missing_months
FROM coverage AS c;

-- ============================================================
-- 01. MONTHLY FUNDING AND CREDIT LOSS
-- ============================================================
-- Question: How do deposit growth, lending relative to deposits and
-- credit losses relative to lending evolve together?
-- Match the same calendar month one year earlier, even if gaps exist.
WITH monthly AS (
    SELECT
        DATE_TRUNC('month', year_month)::DATE AS report_month,
        average_deposits::NUMERIC AS average_deposits,
        average_loan_balance::NUMERIC AS average_loan_balance,
        credit_loss::NUMERIC AS credit_loss
    FROM performance.bank_monthly_performance
)
SELECT
    cur.report_month,
    prev.report_month AS prior_year_month,
    -- KPI-02 | Average Deposits | Tier S | Tool: Power BI
    ROUND(cur.average_deposits, 2) AS average_deposits,
    -- KPI-03 | Average Loan Balance | Tier S | Tool: Power BI
    ROUND(cur.average_loan_balance, 2) AS average_loan_balance,
    -- Supporting components: monthly loss and prior-year deposits.
    ROUND(cur.credit_loss, 2) AS monthly_credit_loss,
    ROUND(prev.average_deposits, 2) AS prior_year_average_deposits,
    -- KPI-06 | Credit Loss Ratio | Tier S | Tool: Power BI
    CASE WHEN cur.average_loan_balance > 0 THEN
        ROUND(100.0 * cur.credit_loss / cur.average_loan_balance, 4)
    END AS monthly_credit_loss_ratio_pct,
    -- KPI-12 | Loan-to-Deposit Operating Ratio | Tier S | Tool: Power BI
    CASE WHEN cur.average_deposits > 0 THEN
        ROUND(100.0 * cur.average_loan_balance / cur.average_deposits, 2)
    END AS loan_to_deposit_operating_ratio_pct,
    -- KPI-25 | Deposit Growth YoY | Tier A | Tool: Power BI
    CASE WHEN prev.average_deposits > 0 THEN
        ROUND(100.0 * (cur.average_deposits / prev.average_deposits - 1), 2)
    END AS deposit_growth_yoy_pct
FROM monthly AS cur
LEFT JOIN monthly AS prev
    ON prev.report_month = (cur.report_month - INTERVAL '1 year')::DATE
ORDER BY cur.report_month;

-- ============================================================
-- 02. ANNUAL FUNDING AND CREDIT LOSS
-- ============================================================
-- Question: Did annual funding expand, and how much lending exposure
-- was absorbed by the year's modeled credit losses?
-- Only complete calendar years enter: exactly 12 rows, 12 unique
-- months and no missing components. Resolve query 00 failures first.
-- Annual deposit growth compares mean monthly balances between years;
-- it is distinct from December-over-December growth in query 01.
WITH annual AS (
    SELECT
        EXTRACT(YEAR FROM year_month)::INT AS calendar_year,
        AVG(average_deposits::NUMERIC) AS mean_monthly_deposits,
        AVG(average_loan_balance::NUMERIC) AS mean_monthly_loan_balance,
        SUM(credit_loss::NUMERIC) AS annual_credit_loss
    FROM performance.bank_monthly_performance
    GROUP BY EXTRACT(YEAR FROM year_month)::INT
    HAVING COUNT(*) = 12
       AND COUNT(DISTINCT DATE_TRUNC('month', year_month)) = 12
       AND COUNT(average_deposits) = 12
       AND COUNT(average_loan_balance) = 12
       AND COUNT(credit_loss) = 12
)
SELECT
    cur.calendar_year,
    prev.calendar_year AS prior_calendar_year,
    -- KPI-02 | Average Deposits | Tier S | Tool: Power BI
    ROUND(cur.mean_monthly_deposits, 2) AS mean_monthly_deposits,
    -- KPI-03 | Average Loan Balance | Tier S | Tool: Power BI
    ROUND(cur.mean_monthly_loan_balance, 2) AS mean_monthly_loan_balance,
    -- Supporting components for annual loss and deposit growth.
    ROUND(cur.annual_credit_loss, 2) AS annual_credit_loss,
    ROUND(prev.mean_monthly_deposits, 2) AS prior_year_mean_monthly_deposits,
    -- KPI-06 | Credit Loss Ratio | Tier S | Tool: Power BI
    CASE WHEN cur.mean_monthly_loan_balance > 0 THEN
        ROUND(100.0 * cur.annual_credit_loss / cur.mean_monthly_loan_balance, 4)
    END AS annual_credit_loss_ratio_pct,
    -- KPI-12 | Loan-to-Deposit Operating Ratio | Tier S | Tool: Power BI
    CASE WHEN cur.mean_monthly_deposits > 0 THEN
        ROUND(100.0 * cur.mean_monthly_loan_balance / cur.mean_monthly_deposits, 2)
    END AS loan_to_deposit_operating_ratio_pct,
    -- KPI-25 | Deposit Growth YoY | Tier A | Tool: Power BI
    CASE WHEN prev.mean_monthly_deposits > 0 THEN
        ROUND(100.0 * (cur.mean_monthly_deposits / prev.mean_monthly_deposits - 1), 2)
    END AS deposit_growth_yoy_pct
FROM annual AS cur
LEFT JOIN annual AS prev
    ON prev.calendar_year = cur.calendar_year - 1
ORDER BY cur.calendar_year;

-- INTERPRETATION
-- A rising credit loss ratio can reflect higher losses, a smaller
-- loan balance, or both. Inspect the exposed numerator and denominator.
-- The loss ratio does not measure delinquency: 30+/90+ DPD exposure,
-- cure and roll rates require a separate loan-month source.

-- ============================================================
-- KPI OWNERSHIP MAP — FREEZE VERSION
-- ============================================================
-- Tier = portfolio / decision priority; Tool = primary delivery home.
-- PostgreSQL remains the calculation layer for every KPI in this file.
--
-- TIER S
--   Power BI: KPI-02 Average Deposits, KPI-03 Average Loan Balance, KPI-06 Credit Loss Ratio, KPI-12 Loan-to-Deposit Operating Ratio
--
-- TIER A
--   Power BI: KPI-25 Deposit Growth YoY
-- ============================================================
