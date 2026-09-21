-- ============================================================
-- BTYT BANKING ANALYTICS
-- 03_branch_performance_monthly.sql
-- Monthly branch-level analytical view for BI consumption.
--
-- Grain:
-- one branch per month
--
-- Sources:
-- performance.branch_monthly_performance
-- core.branches
--
-- Notes:
-- - Branch master attributes are enriched onto the monthly
--   performance grain for BI and geographic analysis.
-- - Dynamic ratios such as Cost-to-Income, revenue growth and
--   productivity metrics are intentionally left for downstream DAX.
-- - Latitude and longitude are included for Power BI / Tableau maps.
-- - Monetary values in the performance schema are UYU-equivalent.
-- ============================================================

DROP VIEW IF EXISTS analytics.branch_performance_monthly;

CREATE VIEW analytics.branch_performance_monthly AS
SELECT
    bpm.year_month,
    bpm.branch_id,

    -- Branch dimensions
    b.branch_name,
    b.branch_type,
    b.branch_size,
    b.status,
    b.opening_year,
    b.opening_reason,
    b.closing_year,
    b.closure_reason,
    b.parent_branch_id,
    b.department,
    b.locality,
    b.region,
    b.latitude,
    b.longitude,

    -- Scale
    bpm.active_customers,
    bpm.active_accounts,
    bpm.average_deposits,
    bpm.average_loan_balance,

    -- Transaction activity
    bpm.transaction_count,
    bpm.transaction_volume,
    bpm.branch_transaction_count,

    -- Revenue
    bpm.interest_income,
    bpm.interest_expense,
    bpm.net_interest_income,
    bpm.fee_income,
    bpm.total_revenue,

    -- Operating costs
    bpm.personnel_cost,
    bpm.fixed_cost,
    bpm.variable_cost,
    bpm.operational_cost,
    bpm.total_operating_cost,

    -- Credit risk and profitability
    bpm.credit_loss,
    bpm.pre_provision_profit,
    bpm.net_income

FROM performance.branch_monthly_performance AS bpm
INNER JOIN core.branches AS b
    ON b.branch_id = bpm.branch_id;


-- Validation
SELECT
    COUNT(*) AS total_rows,
    MIN(year_month) AS first_month,
    MAX(year_month) AS last_month,
    COUNT(DISTINCT branch_id) AS distinct_branches
FROM analytics.branch_performance_monthly;
