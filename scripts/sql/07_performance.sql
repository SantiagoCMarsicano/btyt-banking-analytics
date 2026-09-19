-- ============================================================
-- BTYT — BANK PERFORMANCE & EXECUTIVE MANAGEMENT ANALYTICS
-- File: 07_performance.sql
-- Architecture-aligned executive synthesis
--
-- Purpose:
-- Build the consolidated Part I performance layer for executive
-- management analysis while preserving correct stock/flow semantics.
--
-- PostgreSQL | Read-only analytical queries
-- ============================================================
--
-- MAIN QUESTION
-- How is BTYT performing as a bank, what is driving changes in
-- revenue, costs, credit losses and net income, and how does that
-- performance evolve over time?
--
-- PRIMARY GRAIN
-- 1 row = 1 month of consolidated BTYT performance
--
-- REPORTING CURRENCY
-- Monetary fields in performance.bank_monthly_performance and
-- performance.branch_monthly_performance are UYU-equivalent reporting
-- values produced by the performance engine. They are designed to be
-- aggregated within this performance layer.
--
-- TOOL OWNERSHIP
--
-- SQL:
-- - monthly performance base
-- - annual stock/flow rollups
-- - macro / shock context
-- - P&L bridge
-- - accounting integrity
-- - branch reconciliation
--
-- DAX / POWER BI:
-- - dynamic KPIs
-- - ratios
-- - growth
-- - YTD / rolling periods
-- - executive interaction
--
-- PYTHON:
-- - decomposition
-- - anomaly analysis
-- - macro / shock association
-- - forecasting / scenarios
--
-- EXCEL:
-- - management reporting
-- - pivots / variance tables
-- - waterfall / scenario work
--
-- ============================================================
-- 00. MEASURE SEMANTICS — READ BEFORE USING
-- ============================================================
--
-- SEMI-ADDITIVE / SNAPSHOT-STYLE
--
-- - active_customers
-- - active_accounts
-- - average_deposits
-- - average_loan_balance
--
-- PERFORMANCE-ENGINE DEFINITIONS
-- active_customers = customers represented in the monthly account-balance
-- layer, uniquely assigned to one relationship branch for that month. This
-- is a monthly relationship/activity concept, not the same field as the
-- cutoff master flag core.customers.customer_status.
--
-- active_accounts = accounts represented in that month's account-balance
-- layer; it is not simply core.accounts.account_status at the 2026 cutoff.
--
-- average_deposits = sum of account average monthly balances
-- ((opening_balance + closing_balance) / 2), converted to UYU-equivalent.
--
-- average_loan_balance = monthly outstanding loan exposure converted to
-- UYU-equivalent.
--
-- These can represent the bank at a selected month.
-- Do NOT SUM them across months for annual reporting.
--
-- Annual examples:
-- - year-end active customers
-- - average monthly active customers
-- - year-end active accounts
-- - average monthly deposits
-- - average monthly loan balance
--
--
-- ADDITIVE FLOWS
--
-- Transaction performance fields use COMPLETED transactions only.
-- transaction_volume is converted to UYU-equivalent by the performance
-- engine. branch_transaction_count is the completed BRANCH-channel count.
--
-- - transaction_count
-- - transaction_volume
-- - branch_transaction_count
-- - interest_income
-- - interest_expense
-- - net_interest_income
-- - fee_income
-- - total_revenue
-- - personnel_cost
-- - fixed_cost
-- - variable_cost
-- - operational_cost
-- - total_operating_cost
-- - credit_loss
-- - pre_provision_profit
-- - net_income
--
-- These may be SUMMED across months.
--
--
-- ACCOUNTING IDENTITIES
--
-- net_interest_income
-- = interest_income - interest_expense
--
-- total_revenue
-- = net_interest_income + fee_income
--
-- total_operating_cost
-- = personnel_cost + fixed_cost + variable_cost + operational_cost
--
-- pre_provision_profit
-- = total_revenue - total_operating_cost
--
-- net_income
-- = pre_provision_profit - credit_loss
--
-- ============================================================
-- 01. PERFORMANCE COVERAGE
-- ============================================================

-- 1.1 Consolidated monthly coverage.

SELECT
    MIN(bmp.year_month) AS first_performance_month,
    MAX(bmp.year_month) AS last_performance_month,
    COUNT(*) AS month_rows,
    COUNT(DISTINCT bmp.year_month) AS distinct_months
FROM performance.bank_monthly_performance AS bmp;


-- 1.2 Full monthly series.
-- This is intentionally direct and useful for first inspection.

SELECT
    bmp.*
FROM performance.bank_monthly_performance AS bmp
ORDER BY bmp.year_month;


-- ============================================================
-- 02. BANK-MONTH PERFORMANCE BASE — SQL PREPARATION
-- ============================================================
--
-- Grain:
-- 1 row = 1 month
--
-- Adds:
-- - calendar fields
-- - annual macro context
-- - monthly external-shock context
--
-- NOTE:
-- macro_environment is annual.
-- Its values repeat across all months of the same year.
--
-- Shock context is descriptive only and does not imply causality.

WITH shock_month AS (
    SELECT
        gs.year_month,
        es.shock_id,
        es.shock_name,
        es.shock_type,
        es.signed_peak_intensity,

        CASE
            WHEN gs.year_month = DATE_TRUNC(
                'month',
                es.peak_month
            )::DATE
                THEN 'PEAK'
            WHEN gs.year_month <= DATE_TRUNC(
                'month',
                es.end_month
            )::DATE
                THEN 'ACTIVE_SHOCK'
            ELSE 'RECOVERY'
        END AS shock_phase

    FROM macro.external_shocks AS es

    CROSS JOIN LATERAL (
        SELECT
            generate_series(
                DATE_TRUNC('month', es.start_month)::DATE,
                DATE_TRUNC('month', es.recovery_end_month)::DATE,
                INTERVAL '1 month'
            )::DATE AS year_month
    ) AS gs
),

shock_calendar AS (
    SELECT
        sm.year_month,

        COUNT(*) AS shock_window_count,

        COUNT(*) FILTER (
            WHERE sm.shock_phase IN ('ACTIVE_SHOCK', 'PEAK')
        ) AS active_shock_count,

        COUNT(*) FILTER (
            WHERE sm.shock_phase = 'RECOVERY'
        ) AS recovery_shock_count,

        STRING_AGG(
            sm.shock_name,
            ', ' ORDER BY sm.shock_name
        ) AS shock_window_names,

        STRING_AGG(
            sm.shock_name,
            ', ' ORDER BY sm.shock_name
        ) FILTER (
            WHERE sm.shock_phase IN ('ACTIVE_SHOCK', 'PEAK')
        ) AS active_shocks,

        STRING_AGG(
            DISTINCT sm.shock_type,
            ', '
        ) FILTER (
            WHERE sm.shock_phase IN ('ACTIVE_SHOCK', 'PEAK')
        ) AS active_shock_types,

        MAX(ABS(sm.signed_peak_intensity))
            AS max_abs_shock_peak_intensity

    FROM shock_month AS sm

    GROUP BY sm.year_month
)

SELECT
    bmp.year_month,

    EXTRACT(
        YEAR FROM bmp.year_month
    )::INT AS calendar_year,

    EXTRACT(
        MONTH FROM bmp.year_month
    )::INT AS calendar_month,

    EXTRACT(
        QUARTER FROM bmp.year_month
    )::INT AS calendar_quarter,

    bmp.active_customers,
    bmp.active_accounts,
    bmp.average_deposits,
    bmp.average_loan_balance,

    bmp.transaction_count,
    bmp.transaction_volume,
    bmp.branch_transaction_count,

    bmp.interest_income,
    bmp.interest_expense,
    bmp.net_interest_income,
    bmp.fee_income,
    bmp.total_revenue,

    bmp.personnel_cost,
    bmp.fixed_cost,
    bmp.variable_cost,
    bmp.operational_cost,
    bmp.total_operating_cost,

    bmp.credit_loss,
    bmp.pre_provision_profit,
    bmp.net_income,

    me.macro_growth_factor,
    me.credit_cycle_factor,
    me.usd_pressure_factor,
    me.financial_stress_factor,
    me.digitalization_factor,
    me.cross_border_factor,
    me.systemic_shock,
    me.systemic_shock_flag,

    COALESCE(sc.shock_window_count, 0)
        AS external_shock_window_count,

    COALESCE(sc.active_shock_count, 0)
        AS active_external_shock_count,

    COALESCE(sc.recovery_shock_count, 0)
        AS recovery_external_shock_count,

    sc.shock_window_names,
    sc.active_shocks,
    sc.active_shock_types,
    sc.max_abs_shock_peak_intensity

FROM performance.bank_monthly_performance AS bmp

LEFT JOIN macro.macro_environment AS me
    ON me.year = EXTRACT(
        YEAR FROM bmp.year_month
    )::INT

LEFT JOIN shock_calendar AS sc
    ON sc.year_month = bmp.year_month

ORDER BY bmp.year_month;


-- ============================================================
-- 03. EXECUTIVE KPI BASELINE — SQL VALIDATION
-- ============================================================
--
-- These ratios are useful for:
-- - learning
-- - SQL validation
-- - cross-checking future DAX measures
--
-- Production dashboard versions should generally be implemented
-- as DAX measures so they respond to filter context.
--
-- All performance monetary fields are in the management reporting
-- currency of the performance engine.

SELECT
    bmp.year_month,

    bmp.active_customers,
    bmp.active_accounts,
    bmp.average_deposits,
    bmp.average_loan_balance,

    bmp.total_revenue,
    bmp.total_operating_cost,
    bmp.credit_loss,
    bmp.pre_provision_profit,
    bmp.net_income,

    ROUND(
        (
            bmp.active_accounts::NUMERIC
            / NULLIF(
                bmp.active_customers,
                0
            )
        ),
        2
    ) AS accounts_per_customer,

    ROUND(
        (
            bmp.average_deposits
            / NULLIF(
                bmp.active_customers,
                0
            )
        )::NUMERIC,
        2
    ) AS deposits_per_customer,

    ROUND(
        (
            bmp.average_loan_balance
            / NULLIF(
                bmp.active_customers,
                0
            )
        )::NUMERIC,
        2
    ) AS loan_balance_per_customer,

    ROUND(
        (
            bmp.total_revenue
            / NULLIF(
                bmp.active_customers,
                0
            )
        )::NUMERIC,
        2
    ) AS revenue_per_customer,

    ROUND(
        (
            bmp.net_income
            / NULLIF(
                bmp.active_customers,
                0
            )
        )::NUMERIC,
        2
    ) AS net_income_per_customer,

    ROUND(
        (
            bmp.total_revenue
            / NULLIF(
                bmp.active_accounts,
                0
            )
        )::NUMERIC,
        2
    ) AS revenue_per_account,

    ROUND(
        (
            100.0
            * bmp.total_operating_cost
            / NULLIF(
                bmp.total_revenue,
                0
            )
        )::NUMERIC,
        2
    ) AS cost_to_income_pct,

    ROUND(
        (
            100.0
            * bmp.pre_provision_profit
            / NULLIF(
                bmp.total_revenue,
                0
            )
        )::NUMERIC,
        2
    ) AS pre_provision_margin_pct,

    ROUND(
        (
            100.0
            * bmp.net_income
            / NULLIF(
                bmp.total_revenue,
                0
            )
        )::NUMERIC,
        2
    ) AS net_margin_pct,

    ROUND(
        (
            100.0
            * bmp.fee_income
            / NULLIF(
                bmp.total_revenue,
                0
            )
        )::NUMERIC,
        2
    ) AS fee_income_share_pct,

    ROUND(
        (
            100.0
            * bmp.credit_loss
            / NULLIF(
                bmp.average_loan_balance,
                0
            )
        )::NUMERIC,
        2
    ) AS credit_loss_to_loan_balance_pct,

    CASE
        WHEN bmp.pre_provision_profit > 0 THEN
            ROUND(
                (
                    100.0
                    * bmp.credit_loss
                    / bmp.pre_provision_profit
                )::NUMERIC,
                2
            )
        ELSE NULL
    END AS credit_loss_absorption_pct,

    ROUND(
        (
            100.0
            * bmp.average_loan_balance
            / NULLIF(
                bmp.average_deposits,
                0
            )
        )::NUMERIC,
        2
    ) AS loan_to_deposit_operating_pct,

    ROUND(
        (
            100.0
            * bmp.branch_transaction_count
            / NULLIF(
                bmp.transaction_count,
                0
            )
        )::NUMERIC,
        2
    ) AS branch_transaction_share_pct

FROM performance.bank_monthly_performance AS bmp

ORDER BY bmp.year_month;


-- ============================================================
-- 04. ANNUAL MANAGEMENT SUMMARY — SQL PREPARATION
-- ============================================================
--
-- Correct stock/flow handling:
--
-- FLOWS:
-- SUM across months
--
-- STOCKS:
-- monthly AVG and year-end value
--
-- Grain:
-- 1 row = 1 year

WITH monthly AS (
    SELECT
        bmp.*,

        EXTRACT(
            YEAR FROM bmp.year_month
        )::INT AS calendar_year,

        ROW_NUMBER() OVER (
            PARTITION BY EXTRACT(
                YEAR FROM bmp.year_month
            )::INT
            ORDER BY bmp.year_month DESC
        ) AS month_desc_rank

    FROM performance.bank_monthly_performance AS bmp
),

annual_flows_and_averages AS (
    SELECT
        m.calendar_year,

        COUNT(*) AS months_observed,

        ROUND(
            AVG(m.active_customers)::NUMERIC,
            2
        ) AS avg_monthly_active_customers,

        ROUND(
            AVG(m.active_accounts)::NUMERIC,
            2
        ) AS avg_monthly_active_accounts,

        ROUND(
            AVG(m.average_deposits)::NUMERIC,
            2
        ) AS avg_monthly_deposits,

        ROUND(
            AVG(m.average_loan_balance)::NUMERIC,
            2
        ) AS avg_monthly_loan_balance,

        SUM(m.transaction_count)
            AS annual_transaction_count,

        ROUND(
            SUM(m.transaction_volume)::NUMERIC,
            2
        ) AS annual_transaction_volume,

        SUM(m.branch_transaction_count)
            AS annual_branch_transaction_count,

        ROUND(
            SUM(m.interest_income)::NUMERIC,
            2
        ) AS annual_interest_income,

        ROUND(
            SUM(m.interest_expense)::NUMERIC,
            2
        ) AS annual_interest_expense,

        ROUND(
            SUM(m.net_interest_income)::NUMERIC,
            2
        ) AS annual_net_interest_income,

        ROUND(
            SUM(m.fee_income)::NUMERIC,
            2
        ) AS annual_fee_income,

        ROUND(
            SUM(m.total_revenue)::NUMERIC,
            2
        ) AS annual_total_revenue,

        ROUND(
            SUM(m.total_operating_cost)::NUMERIC,
            2
        ) AS annual_total_operating_cost,

        ROUND(
            SUM(m.credit_loss)::NUMERIC,
            2
        ) AS annual_credit_loss,

        ROUND(
            SUM(m.pre_provision_profit)::NUMERIC,
            2
        ) AS annual_pre_provision_profit,

        ROUND(
            SUM(m.net_income)::NUMERIC,
            2
        ) AS annual_net_income

    FROM monthly AS m

    GROUP BY m.calendar_year
),

year_end AS (
    SELECT
        m.calendar_year,
        m.year_month AS year_end_month,
        m.active_customers
            AS year_end_active_customers,
        m.active_accounts
            AS year_end_active_accounts,
        m.average_deposits
            AS year_end_average_deposits,
        m.average_loan_balance
            AS year_end_average_loan_balance

    FROM monthly AS m

    WHERE m.month_desc_rank = 1
)

SELECT
    afa.calendar_year,
    afa.months_observed,

    afa.avg_monthly_active_customers,
    ye.year_end_active_customers,

    afa.avg_monthly_active_accounts,
    ye.year_end_active_accounts,

    afa.avg_monthly_deposits,
    ROUND(
        ye.year_end_average_deposits::NUMERIC,
        2
    ) AS year_end_average_deposits,

    afa.avg_monthly_loan_balance,
    ROUND(
        ye.year_end_average_loan_balance::NUMERIC,
        2
    ) AS year_end_average_loan_balance,

    afa.annual_transaction_count,
    afa.annual_transaction_volume,
    afa.annual_branch_transaction_count,

    afa.annual_interest_income,
    afa.annual_interest_expense,
    afa.annual_net_interest_income,
    afa.annual_fee_income,
    afa.annual_total_revenue,

    afa.annual_total_operating_cost,
    afa.annual_credit_loss,
    afa.annual_pre_provision_profit,
    afa.annual_net_income,

    ye.year_end_month

FROM annual_flows_and_averages AS afa

JOIN year_end AS ye
    ON ye.calendar_year = afa.calendar_year

ORDER BY afa.calendar_year;


-- ============================================================
-- 05. P&L COMPONENT BRIDGE — SQL PREPARATION
-- ============================================================
--
-- Grain:
-- 1 row = 1 month × 1 P&L component
--
-- This long-format base is especially useful for:
-- - waterfall charts
-- - management decomposition
-- - Power BI / Excel storytelling
--
-- Positive values contribute upward.
-- Cost / credit-loss components are signed negatively.
--
-- IMPORTANT:
-- amount_type = 'TOTAL' rows are presentation anchors, not additional
-- additive components. Do not SUM TOTAL + COMPONENT rows together.
-- For a component-only bridge, filter amount_type = 'COMPONENT'.

SELECT
    bmp.year_month,

    pnl.sort_order,
    pnl.component_group,
    pnl.component_name,
    pnl.amount_type,

    ROUND(
        pnl.signed_amount::NUMERIC,
        2
    ) AS signed_amount

FROM performance.bank_monthly_performance AS bmp

CROSS JOIN LATERAL (
    VALUES
        (
            1,
            'REVENUE',
            'Net Interest Income',
            'COMPONENT',
            bmp.net_interest_income
        ),
        (
            2,
            'REVENUE',
            'Fee Income',
            'COMPONENT',
            bmp.fee_income
        ),
        (
            3,
            'REVENUE',
            'Total Revenue',
            'TOTAL',
            bmp.total_revenue
        ),
        (
            4,
            'OPERATING_COST',
            'Personnel Cost',
            'COMPONENT',
            -bmp.personnel_cost
        ),
        (
            5,
            'OPERATING_COST',
            'Fixed Cost',
            'COMPONENT',
            -bmp.fixed_cost
        ),
        (
            6,
            'OPERATING_COST',
            'Variable Cost',
            'COMPONENT',
            -bmp.variable_cost
        ),
        (
            7,
            'OPERATING_COST',
            'Operational Cost',
            'COMPONENT',
            -bmp.operational_cost
        ),
        (
            8,
            'PROFIT',
            'Pre-Provision Profit',
            'TOTAL',
            bmp.pre_provision_profit
        ),
        (
            9,
            'CREDIT_RISK',
            'Credit Loss',
            'COMPONENT',
            -bmp.credit_loss
        ),
        (
            10,
            'PROFIT',
            'Net Income',
            'TOTAL',
            bmp.net_income
        )
) AS pnl(
    sort_order,
    component_group,
    component_name,
    amount_type,
    signed_amount
)

ORDER BY
    bmp.year_month,
    pnl.sort_order;


-- ============================================================
-- 06. REVENUE / COST MIX BASELINE — SQL VALIDATION
-- ============================================================
--
-- Compact mix diagnostics for future DAX validation.

SELECT
    bmp.year_month,

    ROUND(
        (
            100.0
            * bmp.net_interest_income
            / NULLIF(
                bmp.total_revenue,
                0
            )
        )::NUMERIC,
        2
    ) AS net_interest_income_share_pct,

    ROUND(
        (
            100.0
            * bmp.fee_income
            / NULLIF(
                bmp.total_revenue,
                0
            )
        )::NUMERIC,
        2
    ) AS fee_income_share_pct,

    ROUND(
        (
            100.0
            * bmp.personnel_cost
            / NULLIF(
                bmp.total_operating_cost,
                0
            )
        )::NUMERIC,
        2
    ) AS personnel_cost_share_pct,

    ROUND(
        (
            100.0
            * bmp.fixed_cost
            / NULLIF(
                bmp.total_operating_cost,
                0
            )
        )::NUMERIC,
        2
    ) AS fixed_cost_share_pct,

    ROUND(
        (
            100.0
            * bmp.variable_cost
            / NULLIF(
                bmp.total_operating_cost,
                0
            )
        )::NUMERIC,
        2
    ) AS variable_cost_share_pct,

    ROUND(
        (
            100.0
            * bmp.operational_cost
            / NULLIF(
                bmp.total_operating_cost,
                0
            )
        )::NUMERIC,
        2
    ) AS operational_cost_share_pct

FROM performance.bank_monthly_performance AS bmp

ORDER BY bmp.year_month;


-- ============================================================
-- 07. MACRO CONTEXT BASELINE
-- ============================================================
--
-- Monthly performance joined to annual macro state.
--
-- This is descriptive context only.

SELECT
    bmp.year_month,

    bmp.active_customers,
    bmp.average_deposits,
    bmp.average_loan_balance,
    bmp.total_revenue,
    bmp.total_operating_cost,
    bmp.credit_loss,
    bmp.net_income,

    me.macro_growth_factor,
    me.credit_cycle_factor,
    me.usd_pressure_factor,
    me.financial_stress_factor,
    me.digitalization_factor,
    me.cross_border_factor,
    me.systemic_shock,
    me.systemic_shock_flag

FROM performance.bank_monthly_performance AS bmp

LEFT JOIN macro.macro_environment AS me
    ON me.year = EXTRACT(
        YEAR FROM bmp.year_month
    )::INT

ORDER BY bmp.year_month;


-- ============================================================
-- 08. EXTERNAL SHOCK CALENDAR — SQL PREPARATION
-- ============================================================
--
-- Grain:
-- 1 row = 1 month × 1 shock
--
-- Expands each shock from start_month through recovery_end_month.
--
-- Useful for:
-- - shock-window filters
-- - performance overlays
-- - Python event-window analysis
--
-- No causal claim is implied.

SELECT
    gs.year_month,

    es.shock_id,
    es.shock_name,
    es.shock_type,
    es.shock_scale,
    es.direction,
    es.region_scope,
    es.sector_scope,

    es.start_month,
    es.peak_month,
    es.end_month,
    es.recovery_end_month,

    es.duration_months,
    es.recovery_months,
    es.peak_magnitude,
    es.signed_peak_intensity,
    es.persistence,
    es.recovery_shape,

    CASE
        WHEN gs.year_month
             = DATE_TRUNC(
                 'month',
                 es.peak_month
               )::DATE
            THEN 'PEAK'
        WHEN gs.year_month
             <= DATE_TRUNC(
                 'month',
                 es.end_month
               )::DATE
            THEN 'ACTIVE_SHOCK'
        ELSE 'RECOVERY'
    END AS shock_phase

FROM macro.external_shocks AS es

CROSS JOIN LATERAL (
    SELECT
        generate_series(
            DATE_TRUNC(
                'month',
                es.start_month
            )::DATE,
            DATE_TRUNC(
                'month',
                es.recovery_end_month
            )::DATE,
            INTERVAL '1 month'
        )::DATE AS year_month
) AS gs

ORDER BY
    gs.year_month,
    es.shock_id;


-- ============================================================
-- 09. MARKET CONTEXT — OPTIONAL EXECUTIVE CONTEXT
-- ============================================================
--
-- This section does NOT reconcile to bank_monthly_performance.
--
-- It provides annual market / competitor context only.
-- bank_financials contains its own reporting_currency field; do not
-- aggregate competitor monetary values across reporting currencies
-- unless they are explicitly converted to a common currency.
--
-- Grain:
-- 1 row = 1 bank × 1 year

SELECT
    b.bank_id,
    b.bank_name,
    b.bank_scope,
    b.bank_type,
    b.bank_status,

    bmw.year,
    bmw.market_weight,

    bf.revenue,
    bf.operating_costs,
    bf.net_income,
    bf.total_assets,
    bf.total_deposits,
    bf.total_loans,
    bf.equity,
    bf.reporting_currency

FROM market.bank_market_weights AS bmw

JOIN market.banks AS b
    ON b.bank_id = bmw.bank_id

LEFT JOIN market.bank_financials AS bf
    ON bf.bank_id = bmw.bank_id
   AND bf.year = bmw.year

ORDER BY
    bmw.year,
    bmw.market_weight DESC;


-- ============================================================
-- 10. BRANCH-TO-BANK RECONCILIATION
-- ============================================================
--
-- Canonical full reconciliation for the performance layer.
-- The bank table is generated by aggregating the branch table, so every
-- published performance measure should reconcile by month.
--
-- Expected:
-- - count differences = 0
-- - monetary differences = 0.00 (or <= 0.01 rounding tolerance)
-- - reconciliation_status = PASS
--
-- A smaller branch-focused check may remain in 05_branches.sql, but
-- this is the canonical complete audit copy.

WITH branch_rollup AS (
    SELECT
        bmp.year_month,

        SUM(bmp.active_customers) AS active_customers,

        SUM(bmp.active_accounts) AS active_accounts,

        SUM(bmp.transaction_count) AS transaction_count,

        SUM(bmp.branch_transaction_count) AS branch_transaction_count,

        SUM(bmp.average_deposits) AS average_deposits,

        SUM(bmp.average_loan_balance) AS average_loan_balance,

        SUM(bmp.transaction_volume) AS transaction_volume,

        SUM(bmp.interest_income) AS interest_income,

        SUM(bmp.interest_expense) AS interest_expense,

        SUM(bmp.net_interest_income) AS net_interest_income,

        SUM(bmp.fee_income) AS fee_income,

        SUM(bmp.total_revenue) AS total_revenue,

        SUM(bmp.personnel_cost) AS personnel_cost,

        SUM(bmp.fixed_cost) AS fixed_cost,

        SUM(bmp.variable_cost) AS variable_cost,

        SUM(bmp.operational_cost) AS operational_cost,

        SUM(bmp.total_operating_cost) AS total_operating_cost,

        SUM(bmp.credit_loss) AS credit_loss,

        SUM(bmp.pre_provision_profit) AS pre_provision_profit,

        SUM(bmp.net_income) AS net_income

    FROM performance.branch_monthly_performance AS bmp

    GROUP BY bmp.year_month
)

SELECT
    br.year_month,

    br.active_customers - bank.active_customers
        AS active_customers_diff,

    br.active_accounts - bank.active_accounts
        AS active_accounts_diff,

    br.transaction_count - bank.transaction_count
        AS transaction_count_diff,

    br.branch_transaction_count - bank.branch_transaction_count
        AS branch_transaction_count_diff,

    ROUND(
        (br.average_deposits - bank.average_deposits)::NUMERIC,
        2
    ) AS average_deposits_diff,

    ROUND(
        (br.average_loan_balance - bank.average_loan_balance)::NUMERIC,
        2
    ) AS average_loan_balance_diff,

    ROUND(
        (br.transaction_volume - bank.transaction_volume)::NUMERIC,
        2
    ) AS transaction_volume_diff,

    ROUND(
        (br.interest_income - bank.interest_income)::NUMERIC,
        2
    ) AS interest_income_diff,

    ROUND(
        (br.interest_expense - bank.interest_expense)::NUMERIC,
        2
    ) AS interest_expense_diff,

    ROUND(
        (br.net_interest_income - bank.net_interest_income)::NUMERIC,
        2
    ) AS net_interest_income_diff,

    ROUND(
        (br.fee_income - bank.fee_income)::NUMERIC,
        2
    ) AS fee_income_diff,

    ROUND(
        (br.total_revenue - bank.total_revenue)::NUMERIC,
        2
    ) AS total_revenue_diff,

    ROUND(
        (br.personnel_cost - bank.personnel_cost)::NUMERIC,
        2
    ) AS personnel_cost_diff,

    ROUND(
        (br.fixed_cost - bank.fixed_cost)::NUMERIC,
        2
    ) AS fixed_cost_diff,

    ROUND(
        (br.variable_cost - bank.variable_cost)::NUMERIC,
        2
    ) AS variable_cost_diff,

    ROUND(
        (br.operational_cost - bank.operational_cost)::NUMERIC,
        2
    ) AS operational_cost_diff,

    ROUND(
        (br.total_operating_cost - bank.total_operating_cost)::NUMERIC,
        2
    ) AS total_operating_cost_diff,

    ROUND(
        (br.credit_loss - bank.credit_loss)::NUMERIC,
        2
    ) AS credit_loss_diff,

    ROUND(
        (br.pre_provision_profit - bank.pre_provision_profit)::NUMERIC,
        2
    ) AS pre_provision_profit_diff,

    ROUND(
        (br.net_income - bank.net_income)::NUMERIC,
        2
    ) AS net_income_diff,

    CASE
        WHEN br.active_customers = bank.active_customers
         AND br.active_accounts = bank.active_accounts
         AND br.transaction_count = bank.transaction_count
         AND br.branch_transaction_count = bank.branch_transaction_count
         AND ABS(br.average_deposits - bank.average_deposits) <= 0.01
         AND ABS(br.average_loan_balance - bank.average_loan_balance) <= 0.01
         AND ABS(br.transaction_volume - bank.transaction_volume) <= 0.01
         AND ABS(br.interest_income - bank.interest_income) <= 0.01
         AND ABS(br.interest_expense - bank.interest_expense) <= 0.01
         AND ABS(br.net_interest_income - bank.net_interest_income) <= 0.01
         AND ABS(br.fee_income - bank.fee_income) <= 0.01
         AND ABS(br.total_revenue - bank.total_revenue) <= 0.01
         AND ABS(br.personnel_cost - bank.personnel_cost) <= 0.01
         AND ABS(br.fixed_cost - bank.fixed_cost) <= 0.01
         AND ABS(br.variable_cost - bank.variable_cost) <= 0.01
         AND ABS(br.operational_cost - bank.operational_cost) <= 0.01
         AND ABS(br.total_operating_cost - bank.total_operating_cost) <= 0.01
         AND ABS(br.credit_loss - bank.credit_loss) <= 0.01
         AND ABS(br.pre_provision_profit - bank.pre_provision_profit) <= 0.01
         AND ABS(br.net_income - bank.net_income) <= 0.01
            THEN 'PASS'
        ELSE 'REVIEW'
    END AS reconciliation_status

FROM branch_rollup AS br

JOIN performance.bank_monthly_performance AS bank
    ON bank.year_month = br.year_month

ORDER BY br.year_month;


-- ============================================================
-- 11. ACCOUNTING IDENTITY AUDIT
-- ============================================================
--
-- Expected:
-- all maximum residuals = 0 or negligible rounding residual.

SELECT
    ROUND(
        MAX(
            ABS(
                bmp.net_interest_income
                - (
                    bmp.interest_income
                    - bmp.interest_expense
                )
            )
        )::NUMERIC,
        2
    ) AS max_net_interest_income_residual,

    ROUND(
        MAX(
            ABS(
                bmp.total_revenue
                - (
                    bmp.net_interest_income
                    + bmp.fee_income
                )
            )
        )::NUMERIC,
        2
    ) AS max_total_revenue_residual,

    ROUND(
        MAX(
            ABS(
                bmp.total_operating_cost
                - (
                    bmp.personnel_cost
                    + bmp.fixed_cost
                    + bmp.variable_cost
                    + bmp.operational_cost
                )
            )
        )::NUMERIC,
        2
    ) AS max_total_operating_cost_residual,

    ROUND(
        MAX(
            ABS(
                bmp.pre_provision_profit
                - (
                    bmp.total_revenue
                    - bmp.total_operating_cost
                )
            )
        )::NUMERIC,
        2
    ) AS max_pre_provision_profit_residual,

    ROUND(
        MAX(
            ABS(
                bmp.net_income
                - (
                    bmp.pre_provision_profit
                    - bmp.credit_loss
                )
            )
        )::NUMERIC,
        2
    ) AS max_net_income_residual

FROM performance.bank_monthly_performance AS bmp;


-- ============================================================
-- 12. STRUCTURAL SANITY CHECKS
-- ============================================================

-- 12.1 Duplicate bank-month rows.
-- PK should make this return zero rows.

SELECT
    bmp.year_month,
    COUNT(*) AS row_count
FROM performance.bank_monthly_performance AS bmp
GROUP BY bmp.year_month
HAVING COUNT(*) > 1;


-- 12.2 Impossible negative fields.
--
-- Net interest income, total revenue, pre-provision profit and net income
-- are not constrained here because negative values can be economically valid.
-- Counts, balance stocks, transaction volume, operating-cost components and
-- credit-loss expense are expected to be nonnegative in the performance engine.

SELECT
    bmp.year_month,
    bmp.active_customers,
    bmp.active_accounts,
    bmp.average_deposits,
    bmp.average_loan_balance,
    bmp.transaction_count,
    bmp.transaction_volume,
    bmp.branch_transaction_count,
    bmp.personnel_cost,
    bmp.fixed_cost,
    bmp.variable_cost,
    bmp.operational_cost,
    bmp.total_operating_cost,
    bmp.credit_loss
FROM performance.bank_monthly_performance AS bmp
WHERE
       bmp.active_customers < 0
    OR bmp.active_accounts < 0
    OR bmp.average_deposits < 0
    OR bmp.average_loan_balance < 0
    OR bmp.transaction_count < 0
    OR bmp.transaction_volume < 0
    OR bmp.branch_transaction_count < 0
    OR bmp.personnel_cost < 0
    OR bmp.fixed_cost < 0
    OR bmp.variable_cost < 0
    OR bmp.operational_cost < 0
    OR bmp.total_operating_cost < 0
    OR bmp.credit_loss < 0
ORDER BY bmp.year_month;


-- 12.3 Branch transaction count cannot exceed total transaction count.

SELECT
    bmp.year_month,
    bmp.transaction_count,
    bmp.branch_transaction_count
FROM performance.bank_monthly_performance AS bmp
WHERE bmp.branch_transaction_count > bmp.transaction_count
ORDER BY bmp.year_month;


-- 12.4 Macro-context coverage.
-- Expected: every performance month finds one macro year.

SELECT
    bmp.year_month,
    EXTRACT(
        YEAR FROM bmp.year_month
    )::INT AS performance_year
FROM performance.bank_monthly_performance AS bmp
LEFT JOIN macro.macro_environment AS me
    ON me.year = EXTRACT(
        YEAR FROM bmp.year_month
    )::INT
WHERE me.year IS NULL
ORDER BY bmp.year_month;


-- ============================================================
-- 13. DOWNSTREAM POWER BI / DAX HANDOFF
-- ============================================================
--
-- PRIMARY SOURCE
--
-- Bank-month performance base
--
--
-- SCALE MEASURES
--
-- - Active Customers
-- - Active Accounts
-- - Average Deposits
-- - Average Loan Balance
-- - Transaction Count
-- - Transaction Volume
--
--
-- REVENUE MEASURES
--
-- - Interest Income
-- - Interest Expense
-- - Net Interest Income
-- - Fee Income
-- - Total Revenue
--
--
-- COST MEASURES
--
-- - Personnel Cost
-- - Fixed Cost
-- - Variable Cost
-- - Operational Cost
-- - Total Operating Cost
--
--
-- RISK / PROFIT MEASURES
--
-- - Credit Loss
-- - Pre-Provision Profit
-- - Net Income
--
--
-- DYNAMIC RATIOS
--
-- - Accounts per Customer
-- - Deposits per Customer
-- - Loan Balance per Customer
-- - Revenue per Customer
-- - Net Income per Customer
-- - Revenue per Account
-- - Cost-to-Income
-- - Pre-Provision Margin
-- - Net Margin
-- - Fee Income Share
-- - Credit Loss / Loan Balance
-- - Credit Loss / Pre-Provision Profit
-- - Loan-to-Deposit Operating Ratio
-- - Branch Transaction Share
--
--
-- TIME INTELLIGENCE
--
-- - MoM Growth
-- - YoY Growth
-- - YTD Revenue
-- - YTD Net Income
-- - Rolling 3M Revenue
-- - Rolling 12M Net Income
-- - Current vs Prior Period
--
--
-- CRITICAL DAX RULE
--
-- Do NOT SUM the following across months:
--
-- - Active Customers
-- - Active Accounts
-- - Average Deposits
-- - Average Loan Balance
--
-- Use:
-- - end-of-period
-- - monthly average
-- - or another explicitly documented stock rule
--
-- depending on the KPI.
--
-- ============================================================
-- 14. EXECUTIVE DASHBOARD CONCEPT
-- ============================================================
--
-- Suggested Power BI pages:
--
-- PAGE 1 — EXECUTIVE OVERVIEW
-- - Active Customers
-- - Deposits
-- - Loans
-- - Revenue
-- - Cost-to-Income
-- - Credit Loss
-- - Net Income
-- - trend cards
--
-- PAGE 2 — REVENUE & MARGIN
-- - NII
-- - Fee Income
-- - Revenue Mix
-- - Pre-Provision Profit
-- - P&L waterfall
--
-- PAGE 3 — COST & EFFICIENCY
-- - cost structure
-- - Cost-to-Income
-- - productivity ratios
-- - operating leverage
--
-- PAGE 4 — RISK & CREDIT LOSS
-- - credit-loss trend
-- - credit-loss ratios
-- - links / drill-through to 03_loans
--
-- PAGE 5 — BRANCH CONTRIBUTION
-- - branch / region contribution
-- - links to 05_branches
--
-- PAGE 6 — MACRO / SHOCK CONTEXT
-- - macro factors
-- - shock overlays
-- - performance around shock windows
--
-- This file provides the executive semantic foundation.
--
-- ============================================================
-- 15. PYTHON / EXCEL HANDOFF
-- ============================================================
--
-- PYTHON
--
-- Strong candidates:
--
-- - decomposition of net-income changes
-- - trend-break detection
-- - shock-window comparisons
-- - macro correlations
-- - scenario analysis
-- - forecasting
--
-- Do not treat correlations as causal effects.
--
--
-- EXCEL
--
-- Strong candidates:
--
-- - management P&L
-- - annual summary
-- - monthly variance analysis
-- - KPI scorecards
-- - PivotTables
-- - P&L waterfall
-- - scenario / sensitivity analysis
--
-- ============================================================
-- 16. FINAL PART I ROLE
-- ============================================================
--
-- 07_performance.sql is the executive synthesis layer.
--
-- It should consume and reconcile the bank already built by the
-- previous files rather than recreate their detailed analyses.
--
-- 00 → What bank exists?
-- 01 → Who are the customers?
-- 02 → What products/accounts do they hold?
-- 03 → How does lending and credit quality behave?
-- 04 → How does money move through the bank?
-- 05 → How does the branch network perform?
-- 06 → How do campaigns reach and engage customers?
-- 07 → How is the bank performing as a whole?
--
-- ============================================================
-- END
-- ============================================================
