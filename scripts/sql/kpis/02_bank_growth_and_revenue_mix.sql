-- ============================================================
-- BTYT — BANK GROWTH AND REVENUE MIX
-- File: 02_bank_growth_and_revenue_mix.sql
-- PostgreSQL | Read-only | Run one statement at a time
-- ============================================================
-- Source: performance.bank_monthly_performance
-- Grain: one row per calendar month. Reporting currency: UYU-equivalent.
-- This file completes the profitability block started in file 01.
-- Code and KPI assignments follow kpi_catalog_v2_expanded.md.
--
--
-- RULES
-- Growth rates require a strictly positive prior-year denominator.
-- Net income change is an absolute UYU-equivalent difference, not a
-- percentage: it remains interpretable across losses and sign changes.
-- Revenue shares require strictly positive current revenue. Components
-- can be negative; do not clamp their shares to a 0–100 range.
-- Operating leverage = revenue growth minus operating-cost growth,
-- expressed in percentage points. It is not a causal estimate.
-- Round only final outputs. Recompute annual ratios from annual sums.
-- Annual YoY outputs require two complete calendar years.

-- ============================================================
-- 00. SOURCE VALIDATION
-- ============================================================
-- Expect zero duplicate months, missing months and incomplete rows.
-- Resolve any failures before running the KPI queries. NULL financial
-- values must not silently become understated annual totals.
WITH coverage AS (
    SELECT
        COUNT(*) AS rows_observed,
        COUNT(DISTINCT DATE_TRUNC('month', year_month)) AS distinct_months,
        MIN(year_month)::DATE AS first_month,
        MAX(year_month)::DATE AS last_month,
        COUNT(*) FILTER (WHERE year_month IS NULL) AS null_month_rows,
        COUNT(*) FILTER (
            WHERE total_revenue IS NULL OR total_operating_cost IS NULL
               OR net_income IS NULL OR fee_income IS NULL
               OR net_interest_income IS NULL
        ) AS incomplete_financial_rows
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
-- 01. MONTHLY YoY GROWTH AND REVENUE MIX
-- ============================================================
-- Question: Is revenue growing faster than costs, and which income
-- component contributes to it?
-- Match the exact calendar month one year earlier. LAG(..., 12)
-- would match the wrong period if intermediate months were missing.
-- The first observed year has NULL YoY outputs, not zero growth.
WITH monthly AS (
    SELECT
        DATE_TRUNC('month', year_month)::DATE AS report_month,
        total_revenue::NUMERIC AS revenue,
        total_operating_cost::NUMERIC AS operating_cost,
        net_income::NUMERIC AS net_income,
        fee_income::NUMERIC AS fee_income,
        net_interest_income::NUMERIC AS net_interest_income
    FROM performance.bank_monthly_performance
)
SELECT
    cur.report_month,
    prev.report_month AS prior_year_period,
    -- Supporting components expose the denominators and growth drivers.
    ROUND(cur.revenue, 2) AS revenue,
    ROUND(prev.revenue, 2) AS prior_year_revenue,
    ROUND(cur.operating_cost, 2) AS operating_cost,
    ROUND(prev.operating_cost, 2) AS prior_year_operating_cost,
    ROUND(cur.net_income, 2) AS net_income,
    ROUND(prev.net_income, 2) AS prior_year_net_income,
    ROUND(cur.fee_income, 2) AS fee_income,
    ROUND(cur.net_interest_income, 2) AS net_interest_income,
    -- KPI-10 | YoY Revenue Growth | Tier A | Tool: Power BI
    CASE WHEN prev.revenue > 0 THEN
        ROUND(100.0 * (cur.revenue / prev.revenue - 1), 2)
    END AS yoy_revenue_growth_pct,
    -- KPI-11 | YoY Net Income Change | Tier A | Tool: Power BI
    ROUND(cur.net_income - prev.net_income, 2) AS yoy_net_income_change,
    -- KPI-15 | Fee Income Share | Tier B | Tool: Power BI
    CASE WHEN cur.revenue > 0 THEN
        ROUND(100.0 * cur.fee_income / cur.revenue, 2)
    END AS fee_income_share_pct,
    -- KPI-47 | Net Interest Income Share | Tier B | Tool: Power BI
    CASE WHEN cur.revenue > 0 THEN
        ROUND(100.0 * cur.net_interest_income / cur.revenue, 2)
    END AS net_interest_income_share_pct,
    -- Supporting measure used in operating leverage.
    CASE WHEN prev.operating_cost > 0 THEN
        ROUND(100.0 * (cur.operating_cost / prev.operating_cost - 1), 2)
    END AS yoy_operating_cost_growth_pct,
    -- KPI-52 | Operating Leverage | Tier A | Tool: Power BI
    CASE WHEN prev.revenue > 0 AND prev.operating_cost > 0 THEN
        ROUND(100.0 * (
            (cur.revenue / prev.revenue - 1)
            - (cur.operating_cost / prev.operating_cost - 1)
        ), 2)
    END AS operating_leverage_pp
FROM monthly AS cur
LEFT JOIN monthly AS prev
    ON prev.report_month = (cur.report_month - INTERVAL '1 year')::DATE
ORDER BY cur.report_month;

-- ============================================================
-- 02. ANNUAL YoY GROWTH AND REVENUE MIX
-- ============================================================
-- Question: Do full-year results confirm the monthly trend?
-- Only complete years enter the calculation: 12 unique months,
-- exactly 12 source rows, and no missing financial components.
-- Missing years do not cause a comparison with an older available year.
WITH annual AS (
    SELECT
        EXTRACT(YEAR FROM year_month)::INT AS calendar_year,
        SUM(total_revenue::NUMERIC) AS revenue,
        SUM(total_operating_cost::NUMERIC) AS operating_cost,
        SUM(net_income::NUMERIC) AS net_income,
        SUM(fee_income::NUMERIC) AS fee_income,
        SUM(net_interest_income::NUMERIC) AS net_interest_income
    FROM performance.bank_monthly_performance
    GROUP BY EXTRACT(YEAR FROM year_month)::INT
    HAVING COUNT(*) = 12
       AND COUNT(DISTINCT DATE_TRUNC('month', year_month)) = 12
       AND COUNT(total_revenue) = 12
       AND COUNT(total_operating_cost) = 12
       AND COUNT(net_income) = 12
       AND COUNT(fee_income) = 12
       AND COUNT(net_interest_income) = 12
)
SELECT
    cur.calendar_year,
    prev.calendar_year AS prior_year_period,
    -- Supporting components expose the denominators and growth drivers.
    ROUND(cur.revenue, 2) AS revenue,
    ROUND(prev.revenue, 2) AS prior_year_revenue,
    ROUND(cur.operating_cost, 2) AS operating_cost,
    ROUND(prev.operating_cost, 2) AS prior_year_operating_cost,
    ROUND(cur.net_income, 2) AS net_income,
    ROUND(prev.net_income, 2) AS prior_year_net_income,
    ROUND(cur.fee_income, 2) AS fee_income,
    ROUND(cur.net_interest_income, 2) AS net_interest_income,
    -- KPI-10 | YoY Revenue Growth | Tier A | Tool: Power BI
    CASE WHEN prev.revenue > 0 THEN
        ROUND(100.0 * (cur.revenue / prev.revenue - 1), 2)
    END AS yoy_revenue_growth_pct,
    -- KPI-11 | YoY Net Income Change | Tier A | Tool: Power BI
    ROUND(cur.net_income - prev.net_income, 2) AS yoy_net_income_change,
    -- KPI-15 | Fee Income Share | Tier B | Tool: Power BI
    CASE WHEN cur.revenue > 0 THEN
        ROUND(100.0 * cur.fee_income / cur.revenue, 2)
    END AS fee_income_share_pct,
    -- KPI-47 | Net Interest Income Share | Tier B | Tool: Power BI
    CASE WHEN cur.revenue > 0 THEN
        ROUND(100.0 * cur.net_interest_income / cur.revenue, 2)
    END AS net_interest_income_share_pct,
    -- Supporting measure used in operating leverage.
    CASE WHEN prev.operating_cost > 0 THEN
        ROUND(100.0 * (cur.operating_cost / prev.operating_cost - 1), 2)
    END AS yoy_operating_cost_growth_pct,
    -- KPI-52 | Operating Leverage | Tier A | Tool: Power BI
    CASE WHEN prev.revenue > 0 AND prev.operating_cost > 0 THEN
        ROUND(100.0 * (
            (cur.revenue / prev.revenue - 1)
            - (cur.operating_cost / prev.operating_cost - 1)
        ), 2)
    END AS operating_leverage_pp
FROM annual AS cur
LEFT JOIN annual AS prev
    ON prev.calendar_year = cur.calendar_year - 1
ORDER BY cur.calendar_year;

-- INTERPRETATION
-- Fee share + net interest share should equal 100% before rounding
-- when the source revenue identity holds and revenue is positive.
-- Positive operating leverage means revenue grew faster than costs;
-- net income can still decline when credit losses increase.
-- Run query 00 first, then inspect query 01 before the annual summary.

-- ============================================================
-- KPI OWNERSHIP MAP — FREEZE VERSION
-- ============================================================
-- Tier = portfolio / decision priority; Tool = primary delivery home.
-- PostgreSQL remains the calculation layer for every KPI in this file.
--
-- TIER A
--   Power BI: KPI-10 YoY Revenue Growth, KPI-11 YoY Net Income Change, KPI-52 Operating Leverage
--
-- TIER B
--   Power BI: KPI-15 Fee Income Share, KPI-47 Net Interest Income Share
-- ============================================================
