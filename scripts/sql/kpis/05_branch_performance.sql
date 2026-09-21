-- ============================================================
-- BTYT BANKING ANALYTICS
-- 05_branch_performance.sql
-- Branch profitability, efficiency and growth
-- ============================================================
--
-- Measurement rules:
-- - Revenue, cost and net income are synthetic operating measures.
-- - Ratios are recomputed from their numerator and denominator.
-- - A zero revenue or active-customer denominator returns NULL.
-- - Monthly YoY growth compares the same calendar month one year earlier.
-- - Annual branch ratios use annual flows and mean monthly active customers.
-- - No arbitrary profitability threshold is imposed: profitable means net_income > 0.
-- ============================================================


-- ============================================================
-- 00. VALIDATE MONTHLY BRANCH GRAIN AND COVERAGE
-- ============================================================
-- Expected grain: one row per branch per month.

WITH coverage AS (
    SELECT
        COUNT(*) AS rows_observed,
        COUNT(DISTINCT (branch_id, DATE_TRUNC('month', year_month)))
            AS distinct_branch_months,
        COUNT(DISTINCT branch_id) AS branches_observed,
        MIN(year_month)::DATE AS first_month,
        MAX(year_month)::DATE AS last_month,
        COUNT(*) FILTER (WHERE branch_id IS NULL OR year_month IS NULL)
            AS null_key_rows,
        COUNT(*) FILTER (
            WHERE total_revenue IS NULL
               OR total_operating_cost IS NULL
               OR net_income IS NULL
               OR active_customers IS NULL
        ) AS incomplete_kpi_rows
    FROM performance.branch_monthly_performance
)
SELECT
    *,
    rows_observed - distinct_branch_months AS duplicate_branch_month_rows
FROM coverage;


-- ============================================================
-- 01. MONTHLY BRANCH PERFORMANCE
-- ============================================================
-- Question:
-- Which branches generate income efficiently and how much value is
-- produced per active customer?

SELECT
    bmp.year_month,
    bmp.branch_id,
    b.branch_name,
    b.department,
    b.region,

    ROUND(bmp.total_revenue::NUMERIC, 2) AS total_revenue,
    ROUND(bmp.total_operating_cost::NUMERIC, 2) AS total_operating_cost,
    bmp.active_customers,

    -- KPI-37 | Branch Net Income | Tier A | Tool: Power BI
    ROUND(bmp.net_income::NUMERIC, 2) AS branch_net_income,

    -- KPI-38 | Branch Cost-to-Income | Tier A | Tool: Power BI
    ROUND(
        (100.0 * bmp.total_operating_cost
        / NULLIF(bmp.total_revenue, 0))::NUMERIC,
        2
    ) AS branch_cost_to_income_pct,

    -- KPI-39 | Revenue per Active Customer | Tier B | Tool: Excel
    ROUND(
        (bmp.total_revenue
        / NULLIF(bmp.active_customers, 0))::NUMERIC,
        2
    ) AS revenue_per_active_customer,

    -- KPI-40 | Net Income per Active Customer | Tier B | Tool: Excel
    ROUND(
        (bmp.net_income
        / NULLIF(bmp.active_customers, 0))::NUMERIC,
        2
    ) AS net_income_per_active_customer

FROM performance.branch_monthly_performance AS bmp
LEFT JOIN core.branches AS b
    ON b.branch_id = bmp.branch_id
ORDER BY bmp.year_month, bmp.net_income DESC, bmp.branch_id;


-- ============================================================
-- 02. MONTHLY PROFITABLE BRANCH SHARE
-- ============================================================
-- Question:
-- What share of reporting branches produced positive net income
-- in each month?

SELECT
    year_month,
    COUNT(*) AS eligible_branches,
    COUNT(*) FILTER (WHERE net_income > 0) AS profitable_branches,

    -- KPI-41 | Profitable Branch Share | Tier B | Tool: Tableau
    ROUND(
        100.0 * COUNT(*) FILTER (WHERE net_income > 0)
        / NULLIF(COUNT(*), 0),
        2
    ) AS profitable_branch_share_pct

FROM performance.branch_monthly_performance
WHERE net_income IS NOT NULL
GROUP BY year_month
ORDER BY year_month;


-- ============================================================
-- 03. MONTHLY BRANCH REVENUE GROWTH YOY
-- ============================================================
-- Question:
-- How did each branch's revenue change versus the same month one
-- year earlier?

WITH monthly AS (
    SELECT
        branch_id,
        DATE_TRUNC('month', year_month)::DATE AS report_month,
        total_revenue::NUMERIC AS total_revenue
    FROM performance.branch_monthly_performance
)
SELECT
    cur.branch_id,
    b.branch_name,
    cur.report_month,
    prev.report_month AS prior_year_month,
    ROUND(cur.total_revenue, 2) AS current_revenue,
    ROUND(prev.total_revenue, 2) AS prior_year_revenue,

    -- KPI-42 | Branch Revenue Growth YoY | Tier B | Tool: Tableau
    CASE
        WHEN prev.total_revenue > 0 THEN
            ROUND(
                100.0 * (cur.total_revenue / prev.total_revenue - 1),
                2
            )
    END AS branch_revenue_growth_yoy_pct

FROM monthly AS cur
LEFT JOIN monthly AS prev
    ON prev.branch_id = cur.branch_id
   AND prev.report_month = (cur.report_month - INTERVAL '1 year')::DATE
LEFT JOIN core.branches AS b
    ON b.branch_id = cur.branch_id
ORDER BY cur.report_month, cur.branch_id;


-- ============================================================
-- 04. ANNUAL BRANCH COMPARISON
-- ============================================================
-- Annual flows are summed.
-- Active customers are treated as a stock and averaged across the
-- months available in the year.

WITH annual AS (
    SELECT
        branch_id,
        EXTRACT(YEAR FROM year_month)::INT AS calendar_year,
        COUNT(*) AS months_observed,
        SUM(total_revenue::NUMERIC) AS annual_revenue,
        SUM(total_operating_cost::NUMERIC) AS annual_operating_cost,
        SUM(net_income::NUMERIC) AS annual_net_income,
        AVG(active_customers::NUMERIC) AS mean_monthly_active_customers
    FROM performance.branch_monthly_performance
    GROUP BY branch_id, EXTRACT(YEAR FROM year_month)
),
annual_with_prior AS (
    SELECT
        cur.*,
        prev.annual_revenue AS prior_year_revenue
    FROM annual AS cur
    LEFT JOIN annual AS prev
        ON prev.branch_id = cur.branch_id
       AND prev.calendar_year = cur.calendar_year - 1
)
SELECT
    a.calendar_year,
    a.branch_id,
    b.branch_name,
    b.department,
    b.region,
    a.months_observed,

    ROUND(a.annual_revenue, 2) AS annual_revenue,
    ROUND(a.annual_operating_cost, 2) AS annual_operating_cost,

    -- KPI-37 | Branch Net Income | Tier A | Tool: Power BI
    ROUND(a.annual_net_income, 2) AS branch_net_income,

    -- KPI-38 | Branch Cost-to-Income | Tier A | Tool: Power BI
    CASE
        WHEN a.annual_revenue <> 0 THEN
            ROUND(
                100.0 * a.annual_operating_cost / a.annual_revenue,
                2
            )
    END AS branch_cost_to_income_pct,

    ROUND(a.mean_monthly_active_customers, 2)
        AS mean_monthly_active_customers,

    -- KPI-39 | Revenue per Active Customer | Tier B | Tool: Excel
    CASE
        WHEN a.mean_monthly_active_customers > 0 THEN
            ROUND(
                a.annual_revenue / a.mean_monthly_active_customers,
                2
            )
    END AS annual_revenue_per_mean_active_customer,

    -- KPI-40 | Net Income per Active Customer | Tier B | Tool: Excel
    CASE
        WHEN a.mean_monthly_active_customers > 0 THEN
            ROUND(
                a.annual_net_income / a.mean_monthly_active_customers,
                2
            )
    END AS annual_net_income_per_mean_active_customer,

    ROUND(a.prior_year_revenue, 2) AS prior_year_revenue,

    -- KPI-42 | Branch Revenue Growth YoY | Tier B | Tool: Tableau
    CASE
        WHEN a.prior_year_revenue > 0 THEN
            ROUND(
                100.0 * (a.annual_revenue / a.prior_year_revenue - 1),
                2
            )
    END AS branch_revenue_growth_yoy_pct

FROM annual_with_prior AS a
LEFT JOIN core.branches AS b
    ON b.branch_id = a.branch_id
ORDER BY a.calendar_year, a.annual_net_income DESC, a.branch_id;


-- ============================================================
-- 05. ANNUAL PROFITABLE BRANCH SHARE
-- ============================================================
-- A branch is profitable for the year when its aggregated annual
-- net income is positive.

WITH branch_year AS (
    SELECT
        branch_id,
        EXTRACT(YEAR FROM year_month)::INT AS calendar_year,
        SUM(net_income::NUMERIC) AS annual_net_income
    FROM performance.branch_monthly_performance
    GROUP BY branch_id, EXTRACT(YEAR FROM year_month)
)
SELECT
    calendar_year,
    COUNT(*) AS eligible_branches,
    COUNT(*) FILTER (WHERE annual_net_income > 0) AS profitable_branches,

    -- KPI-41 | Profitable Branch Share | Tier B | Tool: Tableau
    ROUND(
        100.0 * COUNT(*) FILTER (WHERE annual_net_income > 0)
        / NULLIF(COUNT(*), 0),
        2
    ) AS profitable_branch_share_pct

FROM branch_year
GROUP BY calendar_year
ORDER BY calendar_year;


-- ============================================================
-- INTERPRETATION
-- ============================================================
-- A branch can have high revenue and weak profitability if its cost
-- base is also high.
--
-- Revenue per active customer and net income per active customer are
-- productivity measures, not customer-level profitability models.
--
-- Profitable Branch Share should be read together with the distribution
-- of branch net income; a high share can coexist with a small number of
-- heavily loss-making branches.
--
-- Branch Revenue Growth YoY is undefined when the prior-year revenue
-- denominator is zero or unavailable.
-- ============================================================

-- ============================================================
-- KPI OWNERSHIP MAP — FREEZE VERSION
-- ============================================================
-- Tier = portfolio / decision priority; Tool = primary delivery home.
-- PostgreSQL remains the calculation layer for every KPI in this file.
--
-- TIER A
--   Power BI: KPI-37 Branch Net Income, KPI-38 Branch Cost-to-Income
--
-- TIER B
--   Excel: KPI-39 Revenue per Active Customer, KPI-40 Net Income per Active Customer
--   Tableau: KPI-41 Profitable Branch Share, KPI-42 Branch Revenue Growth YoY
-- ============================================================
