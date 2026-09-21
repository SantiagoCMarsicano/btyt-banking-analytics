-- ============================================================
-- BTYT — PERFORMANCE AND PROFITABILITY KPI CASE
-- File: 01_bank_performance.sql
-- PostgreSQL | Read-only queries | Run one statement at a time
-- ============================================================
--
-- PURPOSE
-- Turn the approved KPI catalog into a defensible step-by-step
-- performance case. Each query answers a business question and
-- exposes the components behind its ratios.
--
-- CANONICAL BTYT SOURCE
-- performance.bank_monthly_performance
-- Grain: one BTYT row per year_month.
--
-- PEER SOURCE
-- market.bank_financials
-- Grain: one synthetic bank per year. Validate currency, bank
-- coverage and comparability before combining it with BTYT.
--
-- Monetary values from the BTYT performance layer are reporting
-- values. Do not join lower-level mixed-currency balances here.
--


-- ============================================================
-- 00. GRAIN AND COVERAGE CHECK
-- ============================================================
-- Question: Which months are present, and is the bank-month key unique?
-- Expected: one row per month, with duplicate_months = 0.

SELECT
    MIN(bmp.year_month) AS first_month,
    MAX(bmp.year_month) AS last_month,
    COUNT(*) AS rows_observed,
    COUNT(DISTINCT bmp.year_month) AS distinct_months,
    COUNT(*) - COUNT(DISTINCT bmp.year_month) AS duplicate_months
FROM performance.bank_monthly_performance AS bmp;


-- ============================================================
-- 01. MONTHLY SCALE AND PROFIT BRIDGE
-- ============================================================
-- Question: How does the bank move from customers and balances
-- to revenue, operating profit and final synthetic net income?
--
-- active_customers, average_deposits and average_loan_balance
-- are stock-style monthly observations. Do not sum them over time.
-- Revenue, costs and credit loss are monthly flows.

SELECT
    bmp.year_month,
    -- KPI-01 | Active Customers | Tier S | Tool: Power BI
    bmp.active_customers,
    -- KPI-02 | Average Deposits | Tier S | Tool: Power BI
    ROUND(bmp.average_deposits::NUMERIC, 2) AS average_deposits,
    -- KPI-03 | Average Loan Balance | Tier S | Tool: Power BI
    ROUND(bmp.average_loan_balance::NUMERIC, 2) AS average_loan_balance,
    ROUND(bmp.net_interest_income::NUMERIC, 2) AS net_interest_income,
    ROUND(bmp.fee_income::NUMERIC, 2) AS fee_income,
    -- KPI-04 | Total Revenue | Tier S | Tool: Power BI
    ROUND(bmp.total_revenue::NUMERIC, 2) AS total_revenue,
    ROUND(bmp.total_operating_cost::NUMERIC, 2) AS operating_cost,
    -- KPI-48 | Pre-Provision Margin component | Tier A | Tool: Power BI
    ROUND(bmp.pre_provision_profit::NUMERIC, 2) AS pre_provision_profit,
    ROUND(bmp.credit_loss::NUMERIC, 2) AS credit_loss,
    -- KPI-08 | Net Income | Tier S | Tool: Power BI
    ROUND(bmp.net_income::NUMERIC, 2) AS net_income
FROM performance.bank_monthly_performance AS bmp
ORDER BY bmp.year_month;


-- ============================================================
-- 02. RECONCILE THE FIVE PERFORMANCE IDENTITIES
-- ============================================================
-- Question: Can the reported results be rebuilt from components?
-- Expected: every maximum absolute difference is zero or within
-- the rounding tolerance of the source values.
-- Avoid rounding each component before calculating differences.

SELECT
    COUNT(*) AS months_checked,
    MAX(ABS(bmp.net_interest_income
        - (bmp.interest_income - bmp.interest_expense)))
        AS max_net_interest_income_gap,
    MAX(ABS(bmp.total_revenue
        - (bmp.net_interest_income + bmp.fee_income)))
        AS max_revenue_gap,
    MAX(ABS(bmp.total_operating_cost
        - (bmp.personnel_cost + bmp.fixed_cost
           + bmp.variable_cost + bmp.operational_cost)))
        AS max_operating_cost_gap,
    MAX(ABS(bmp.pre_provision_profit
        - (bmp.total_revenue - bmp.total_operating_cost)))
        AS max_pre_provision_gap,
    MAX(ABS(bmp.net_income
        - (bmp.pre_provision_profit - bmp.credit_loss)))
        AS max_net_income_gap
FROM performance.bank_monthly_performance AS bmp;


-- ============================================================
-- 03. MONTHLY PROFITABILITY RATIOS
-- ============================================================
-- Question: How much revenue survives operating costs and losses?
-- Ratios remain NULL when the relevant denominator is zero.
-- The ratio definitions are synthetic management measures, not
-- audited statutory or regulatory profitability measures.

SELECT
    bmp.year_month,
    ROUND(bmp.total_revenue::NUMERIC, 2) AS total_revenue,
    ROUND(bmp.total_operating_cost::NUMERIC, 2) AS operating_cost,
    ROUND(bmp.credit_loss::NUMERIC, 2) AS credit_loss,
    ROUND(bmp.net_income::NUMERIC, 2) AS net_income,
    -- KPI-05 | Cost-to-Income | Tier S | Tool: Power BI
    ROUND((100.0 * bmp.total_operating_cost
        / NULLIF(bmp.total_revenue, 0))::NUMERIC, 2) AS cost_to_income_pct,
    -- KPI-48 | Pre-Provision Margin | Tier A | Tool: Power BI
    ROUND((100.0 * bmp.pre_provision_profit
        / NULLIF(bmp.total_revenue, 0))::NUMERIC, 2) AS pre_provision_margin_pct,
    -- KPI-09 | Net Margin | Tier S | Tool: Power BI
    ROUND((100.0 * bmp.net_income
        / NULLIF(bmp.total_revenue, 0))::NUMERIC, 2) AS net_margin_pct,
    -- KPI-49 | Credit Loss Absorption | Tier B | Tool: Power BI
    ROUND((100.0 * bmp.credit_loss
        / NULLIF(bmp.pre_provision_profit, 0))::NUMERIC, 2)
        AS credit_loss_absorption_pct
FROM performance.bank_monthly_performance AS bmp
ORDER BY bmp.year_month;


-- ============================================================
-- 04. ANNUAL PERFORMANCE WITH CORRECT STOCK / FLOW HANDLING
-- ============================================================
-- Question: Did BTYT grow, and did revenue turn into profit?
-- Annual revenue, cost, loss and net income sum monthly flows.
-- Average balances average monthly stock values. The year-end
-- customer count takes the latest observed month of each year.
-- months_observed reveals partial years before interpretation.

WITH annual_flows AS (
    SELECT
        EXTRACT(YEAR FROM bmp.year_month)::INT AS calendar_year,
        COUNT(*) AS months_observed,
        AVG(bmp.average_deposits) AS monthly_average_deposits,
        AVG(bmp.average_loan_balance) AS monthly_average_loan_balance,
        SUM(bmp.net_interest_income) AS net_interest_income,
        SUM(bmp.fee_income) AS fee_income,
        SUM(bmp.total_revenue) AS total_revenue,
        SUM(bmp.total_operating_cost) AS operating_cost,
        SUM(bmp.pre_provision_profit) AS pre_provision_profit,
        SUM(bmp.credit_loss) AS credit_loss,
        SUM(bmp.net_income) AS net_income
    FROM performance.bank_monthly_performance AS bmp
    GROUP BY EXTRACT(YEAR FROM bmp.year_month)::INT
),
year_end_customers AS (
    SELECT DISTINCT ON (EXTRACT(YEAR FROM bmp.year_month)::INT)
        EXTRACT(YEAR FROM bmp.year_month)::INT AS calendar_year,
        bmp.year_month AS latest_observed_month,
        bmp.active_customers AS latest_active_customers
    FROM performance.bank_monthly_performance AS bmp
    ORDER BY EXTRACT(YEAR FROM bmp.year_month)::INT,
             bmp.year_month DESC
)
SELECT
    af.calendar_year,
    af.months_observed,
    yec.latest_observed_month,
    yec.latest_active_customers,
    ROUND(af.monthly_average_deposits::NUMERIC, 2)
        AS monthly_average_deposits,
    ROUND(af.monthly_average_loan_balance::NUMERIC, 2)
        AS monthly_average_loan_balance,
    ROUND(af.net_interest_income::NUMERIC, 2) AS net_interest_income,
    ROUND(af.fee_income::NUMERIC, 2) AS fee_income,
    ROUND(af.total_revenue::NUMERIC, 2) AS total_revenue,
    ROUND(af.operating_cost::NUMERIC, 2) AS operating_cost,
    ROUND(af.credit_loss::NUMERIC, 2) AS credit_loss,
    ROUND(af.net_income::NUMERIC, 2) AS net_income,
    ROUND((100.0 * af.operating_cost
        / NULLIF(af.total_revenue, 0))::NUMERIC, 2) AS cost_to_income_pct,
    ROUND((100.0 * af.net_income
        / NULLIF(af.total_revenue, 0))::NUMERIC, 2) AS net_margin_pct
FROM annual_flows AS af
JOIN year_end_customers AS yec
    ON yec.calendar_year = af.calendar_year
ORDER BY af.calendar_year;


-- ============================================================
-- 05. PEER COVERAGE AND CURRENCY CHECK
-- ============================================================
-- Question: Which peer bank-years are available for comparison?
-- Inspect this output before attempting a cross-bank ranking.
-- The peer financial table is annual; BTYT's own source is monthly.

SELECT
    bf.year AS calendar_year,
    bf.reporting_currency,
    COUNT(*) AS bank_rows,
    COUNT(DISTINCT bf.bank_id) AS distinct_banks,
    COUNT(*) FILTER (WHERE bf.revenue IS NULL) AS missing_revenue,
    COUNT(*) FILTER (WHERE bf.operating_costs IS NULL)
        AS missing_operating_costs,
    COUNT(*) FILTER (WHERE bf.net_income IS NULL) AS missing_net_income
FROM market.bank_financials AS bf
GROUP BY bf.year, bf.reporting_currency
ORDER BY bf.year, bf.reporting_currency;


-- ============================================================
-- 06. PEER PROFITABILITY, GROUPED BY REPORTING CURRENCY
-- ============================================================
-- Question: Which banks have stronger margins and cost efficiency?
-- This comparison uses the peer table's own financial concepts.
-- Ratios are comparable within a consistent reporting definition;
-- absolute amounts should only be ranked within the same currency.
-- BTYT is not assigned a peer rank until its row, period and
-- accounting definitions are reconciled with the peer table.

SELECT
    bf.year AS calendar_year,
    bf.reporting_currency,
    bf.bank_id,
    bf.bank_name,
    ROUND(bf.revenue::NUMERIC, 2) AS revenue,
    ROUND(bf.operating_costs::NUMERIC, 2) AS operating_costs,
    ROUND(bf.net_income::NUMERIC, 2) AS net_income,
    ROUND((100.0 * bf.operating_costs
        / NULLIF(bf.revenue, 0))::NUMERIC, 2) AS cost_to_income_pct,
    ROUND((100.0 * bf.net_income
        / NULLIF(bf.revenue, 0))::NUMERIC, 2) AS net_margin_pct,
    RANK() OVER (
        PARTITION BY bf.year, bf.reporting_currency
        ORDER BY bf.net_income / NULLIF(bf.revenue, 0) DESC NULLS LAST
    ) AS net_margin_rank_within_currency
FROM market.bank_financials AS bf
ORDER BY bf.year,
         bf.reporting_currency,
         net_margin_rank_within_currency,
         bf.bank_id;


-- ============================================================
-- 07. FIND THE BTYT PEER RECORD BEFORE A DIRECT BENCHMARK
-- ============================================================
-- Question: Is BTYT represented among the external bank-year rows?
-- A matching name alone does not prove accounting comparability.

SELECT
    b.bank_id,
    b.bank_name,
    b.bank_scope,
    bf.year AS calendar_year,
    bf.reporting_currency,
    bf.revenue,
    bf.operating_costs,
    bf.net_income
FROM market.banks AS b
LEFT JOIN market.bank_financials AS bf
    ON bf.bank_id = b.bank_id
WHERE b.bank_name ILIKE '%BTYT%'
ORDER BY b.bank_id, bf.year;


-- ============================================================
-- 08. BTYT INTERNAL SERIES VS B000 PEER SERIES
-- ============================================================
-- Question: Do dimensionless profitability ratios match across
-- the two modeled sources for the same bank and year?
-- Revenue amounts are intentionally not divided or subtracted:
-- the internal reporting amounts and peer USD amounts have
-- different currency and possibly different generation logic.
-- A currency conversion alone cannot change cost-to-income or
-- net margin. Substantial ratio gaps indicate a definition/model
-- mismatch and prohibit a direct cross-source profit ranking.

WITH btyt_annual AS (
    SELECT
        EXTRACT(YEAR FROM bmp.year_month)::INT AS calendar_year,
        COUNT(*) AS months_observed,
        SUM(bmp.total_revenue) AS revenue,
        SUM(bmp.total_operating_cost) AS operating_costs,
        SUM(bmp.net_income) AS net_income
    FROM performance.bank_monthly_performance AS bmp
    GROUP BY EXTRACT(YEAR FROM bmp.year_month)::INT
)
SELECT
    ba.calendar_year,
    ba.months_observed,
    bf.reporting_currency AS peer_currency,
    ROUND((100.0 * ba.operating_costs
        / NULLIF(ba.revenue, 0))::NUMERIC, 2)
        AS internal_cost_to_income_pct,
    ROUND((100.0 * bf.operating_costs
        / NULLIF(bf.revenue, 0))::NUMERIC, 2)
        AS peer_cost_to_income_pct,
    ROUND((100.0 * ba.net_income
        / NULLIF(ba.revenue, 0))::NUMERIC, 2)
        AS internal_net_margin_pct,
    ROUND((100.0 * bf.net_income
        / NULLIF(bf.revenue, 0))::NUMERIC, 2)
        AS peer_net_margin_pct,
    ROUND((100.0 * ba.net_income
        / NULLIF(ba.revenue, 0)
        - 100.0 * bf.net_income
        / NULLIF(bf.revenue, 0))::NUMERIC, 2)
        AS net_margin_gap_pp
FROM btyt_annual AS ba
JOIN market.bank_financials AS bf
    ON bf.year = ba.calendar_year
   AND bf.bank_id = 'B000'
ORDER BY ba.calendar_year;


-- NEXT: Interpret query 08 before creating a cross-source BTYT
-- profitability rank. A peer-only ranking within the market source
-- remains valid as a distinct synthetic comparison.

-- ============================================================
-- KPI OWNERSHIP MAP — FREEZE VERSION
-- ============================================================
-- Tier = portfolio / decision priority; Tool = primary delivery home.
-- PostgreSQL remains the calculation layer for every KPI in this file.
--
-- TIER S
--   Power BI: KPI-01 Active Customers, KPI-02 Average Deposits, KPI-03 Average Loan Balance, KPI-04 Total Revenue, KPI-05 Cost-to-Income, KPI-08 Net Income, KPI-09 Net Margin
--
-- TIER A
--   Power BI: KPI-48 Pre-Provision Margin
--
-- TIER B
--   Power BI: KPI-49 Credit Loss Absorption
-- ============================================================
