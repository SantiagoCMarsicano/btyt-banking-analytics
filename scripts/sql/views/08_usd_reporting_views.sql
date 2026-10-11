-- ============================================================
-- BTYT ANALYTICS — USD REPORTING LAYER
-- ============================================================

-- 1. Reusable FX assumptions
CREATE OR REPLACE VIEW analytics.fx_rates AS
SELECT *
FROM (
    VALUES
        (2021, 43.6::numeric),
        (2022, 41.2::numeric),
        (2023, 38.8::numeric),
        (2024, 40.3::numeric),
        (2025, 42.0::numeric),
        (2026, 43.5::numeric)
) AS fx(year, uyu_per_usd);


-- ============================================================
-- 2. BANK PERFORMANCE — USD
-- ============================================================

CREATE OR REPLACE VIEW analytics.bank_performance_monthly_usd AS
SELECT
    bpm.year_month,

    -- Counts
    bpm.active_customers,
    bpm.active_accounts,

    -- Monetary values converted from UYU-equivalent to USD
    bpm.average_deposits       / fx.uyu_per_usd AS average_deposits,
    bpm.average_loan_balance   / fx.uyu_per_usd AS average_loan_balance,

    -- Activity
    bpm.transaction_count,
    bpm.transaction_volume     / fx.uyu_per_usd AS transaction_volume,
    bpm.branch_transaction_count,

    -- Income statement
    bpm.interest_income        / fx.uyu_per_usd AS interest_income,
    bpm.interest_expense       / fx.uyu_per_usd AS interest_expense,
    bpm.net_interest_income    / fx.uyu_per_usd AS net_interest_income,
    bpm.fee_income             / fx.uyu_per_usd AS fee_income,
    bpm.total_revenue          / fx.uyu_per_usd AS total_revenue,

    -- Operating costs
    bpm.personnel_cost         / fx.uyu_per_usd AS personnel_cost,
    bpm.fixed_cost             / fx.uyu_per_usd AS fixed_cost,
    bpm.variable_cost          / fx.uyu_per_usd AS variable_cost,
    bpm.operational_cost       / fx.uyu_per_usd AS operational_cost,
    bpm.total_operating_cost   / fx.uyu_per_usd AS total_operating_cost,

    -- Risk / profitability
    bpm.credit_loss            / fx.uyu_per_usd AS credit_loss,
    bpm.pre_provision_profit   / fx.uyu_per_usd AS pre_provision_profit,
    bpm.net_income             / fx.uyu_per_usd AS net_income,
    bpm.pre_tax_income         / fx.uyu_per_usd AS pre_tax_income,
    bpm.income_tax_expense     / fx.uyu_per_usd AS income_tax_expense

FROM performance.bank_monthly_performance bpm
JOIN analytics.fx_rates fx
    ON fx.year = EXTRACT(YEAR FROM bpm.year_month)::integer;


-- ============================================================
-- 3. BRANCH PERFORMANCE — USD
-- ============================================================

CREATE OR REPLACE VIEW analytics.branch_performance_monthly_usd AS
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

    -- Counts
    bpm.active_customers,
    bpm.active_accounts,

    -- Monetary values converted from UYU-equivalent to USD
    bpm.average_deposits       / fx.uyu_per_usd AS average_deposits,
    bpm.average_loan_balance   / fx.uyu_per_usd AS average_loan_balance,

    -- Activity
    bpm.transaction_count,
    bpm.transaction_volume     / fx.uyu_per_usd AS transaction_volume,
    bpm.branch_transaction_count,

    -- Income statement
    bpm.interest_income        / fx.uyu_per_usd AS interest_income,
    bpm.interest_expense       / fx.uyu_per_usd AS interest_expense,
    bpm.net_interest_income    / fx.uyu_per_usd AS net_interest_income,
    bpm.fee_income             / fx.uyu_per_usd AS fee_income,
    bpm.total_revenue          / fx.uyu_per_usd AS total_revenue,

    -- Operating costs
    bpm.personnel_cost         / fx.uyu_per_usd AS personnel_cost,
    bpm.fixed_cost             / fx.uyu_per_usd AS fixed_cost,
    bpm.variable_cost          / fx.uyu_per_usd AS variable_cost,
    bpm.operational_cost       / fx.uyu_per_usd AS operational_cost,
    bpm.total_operating_cost   / fx.uyu_per_usd AS total_operating_cost,

    -- Risk / profitability
    bpm.credit_loss            / fx.uyu_per_usd AS credit_loss,
    bpm.pre_provision_profit   / fx.uyu_per_usd AS pre_provision_profit,
    bpm.net_income             / fx.uyu_per_usd AS net_income,
    bpm.pre_tax_income         / fx.uyu_per_usd AS pre_tax_income,
    bpm.income_tax_expense     / fx.uyu_per_usd AS income_tax_expense

FROM performance.branch_monthly_performance bpm
JOIN core.branches b
    ON b.branch_id = bpm.branch_id
JOIN analytics.fx_rates fx
    ON fx.year = EXTRACT(YEAR FROM bpm.year_month)::integer;