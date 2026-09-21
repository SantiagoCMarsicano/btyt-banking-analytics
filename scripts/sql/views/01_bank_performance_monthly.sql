-- ============================================================
-- BTYT BANKING ANALYTICS
-- 01_bank_performance_monthly.sql
-- Monthly bank-level analytical view for BI consumption.
--
-- Grain:
-- one consolidated BTYT observation per month
--
-- Source:
-- performance.bank_monthly_performance
--
-- Notes:
-- - The view exposes base measures rather than precomputed dynamic ratios.
-- - Ratios, shares and time intelligence can be handled downstream in DAX.
-- - Monetary values in the performance schema are UYU-equivalent.
-- ============================================================

DROP VIEW IF EXISTS analytics.bank_performance_monthly;

CREATE VIEW analytics.bank_performance_monthly AS
SELECT
    year_month,

    -- Scale
    active_customers,
    active_accounts,
    average_deposits,
    average_loan_balance,

    -- Transaction activity
    transaction_count,
    transaction_volume,
    branch_transaction_count,

    -- Revenue
    interest_income,
    interest_expense,
    net_interest_income,
    fee_income,
    total_revenue,

    -- Operating costs
    personnel_cost,
    fixed_cost,
    variable_cost,
    operational_cost,
    total_operating_cost,

    -- Credit risk and profitability
    credit_loss,
    pre_provision_profit,
    net_income

FROM performance.bank_monthly_performance;


-- Validation
SELECT
    COUNT(*) AS total_rows,
    MIN(year_month) AS first_month,
    MAX(year_month) AS last_month
FROM analytics.bank_performance_monthly;
