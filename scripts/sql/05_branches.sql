-- ============================================================
-- BTYT — BRANCH NETWORK & BRANCH PERFORMANCE ANALYTICS
-- File: 05_branches.sql
-- Architecture-aligned design
--
-- Purpose:
-- Prepare reusable branch-level structural and monthly performance
-- datasets without duplicating transaction or bank-wide analysis.
--
-- PostgreSQL | Read-only analytical queries
-- ============================================================
--
-- MAIN QUESTION
-- How is BTYT's physical network structured, how much business does
-- each branch serve, and how does branch-level performance evolve?
--
-- TOOL OWNERSHIP
--
-- SQL:
-- - branch dimension
-- - branch hierarchy
-- - current commercial footprint
-- - branch-month performance base
-- - structural consistency checks
--
-- DAX / POWER BI:
-- - profitability ratios
-- - efficiency measures
-- - growth measures
-- - shares / rankings under filters
--
-- TABLEAU:
-- - maps
-- - geographic branch storytelling
--
-- PYTHON:
-- - outlier branches
-- - clustering / trajectory analysis
-- - exploratory benchmarking
--
-- IMPORTANT
-- Detailed transaction-channel analysis belongs to 04_transactions.sql.
-- Consolidated bank performance belongs to 07_performance.sql.
--
-- MEASURE SEMANTICS
--
-- performance.branch_monthly_performance is additive across branches
-- for a GIVEN MONTH and reconciles to bank_monthly_performance.
--
-- active_customers is a monthly relationship assignment from the account-
-- balance layer: each represented customer is assigned to one branch in the
-- month (the branch carrying the customer's largest average deposits). It is
-- NOT the same concept as customers.primary_branch_id or the cutoff master
-- customer_status.
--
-- active_accounts means accounts represented in that month's balance layer,
-- not simply accounts whose master account_status is ACTIVE at 2026-12-31.
--
-- transaction_count / transaction_volume contain COMPLETED transaction
-- activity attributed to the account relationship branch.
-- branch_transaction_count counts COMPLETED physical BRANCH-channel events.
--
-- Across TIME, not every column is additive:
--
-- Semi-additive / snapshot-style:
-- - active_customers
-- - active_accounts
-- - average_deposits
-- - average_loan_balance
--
-- These may be summed across branches for the same month, but should
-- not simply be summed across months. Annual stock KPIs require an
-- explicit rule (for example monthly average or end-of-period).
--
-- Additive flows:
-- - transaction_count
-- - transaction_volume
-- - interest_income / expense
-- - fee_income / total_revenue
-- - operating costs
-- - credit_loss
-- - pre_provision_profit
-- - net_income
--
-- Performance monetary fields are reporting-currency equivalent and
-- therefore may be aggregated across branches within the same period.
--
-- ============================================================
-- 01. BRANCH NETWORK INVENTORY
-- ============================================================

-- 1.1 Complete branch inventory.

SELECT
    b.branch_id,
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
    b.longitude
FROM core.branches AS b
ORDER BY
    b.region,
    b.department,
    b.branch_name;


-- 1.2 Network composition by region, type and size.

SELECT
    b.region,
    b.branch_type,
    b.branch_size,
    COUNT(*) AS branch_count
FROM core.branches AS b
GROUP BY
    b.region,
    b.branch_type,
    b.branch_size
ORDER BY
    b.region,
    branch_count DESC;


-- 1.3 Network lifecycle by year.
-- Shows openings, closures, net change and operating network at year-end.

WITH years AS (
    SELECT generate_series(
        MIN(b.opening_year),
        2026
    ) AS year
    FROM core.branches AS b
),

openings AS (
    SELECT
        b.opening_year AS year,
        COUNT(*) AS branches_opened
    FROM core.branches AS b
    GROUP BY b.opening_year
),

closures AS (
    SELECT
        b.closing_year AS year,
        COUNT(*) AS branches_closed
    FROM core.branches AS b
    WHERE b.closing_year IS NOT NULL
    GROUP BY b.closing_year
),

operating_stock AS (
    SELECT
        y.year,
        COUNT(b.branch_id) AS operating_branches_year_end
    FROM years AS y
    LEFT JOIN core.branches AS b
        ON b.opening_year <= y.year
       AND (
            b.closing_year IS NULL
            OR b.closing_year > y.year
       )
    GROUP BY y.year
)

SELECT
    y.year,
    COALESCE(o.branches_opened, 0) AS branches_opened,
    COALESCE(c.branches_closed, 0) AS branches_closed,
    COALESCE(o.branches_opened, 0)
        - COALESCE(c.branches_closed, 0) AS net_network_change,
    os.operating_branches_year_end
FROM years AS y
LEFT JOIN openings AS o
    ON o.year = y.year
LEFT JOIN closures AS c
    ON c.year = y.year
LEFT JOIN operating_stock AS os
    ON os.year = y.year
ORDER BY y.year;


-- ============================================================
-- 02. BRANCH DIMENSION — SQL PREPARATION
-- ============================================================
--
-- Grain:
-- 1 row = 1 branch
--
-- Candidate reusable dimension for Power BI / Tableau.

WITH child_counts AS (
    SELECT
        b.parent_branch_id,
        COUNT(*) AS child_branch_count
    FROM core.branches AS b
    WHERE b.parent_branch_id IS NOT NULL
    GROUP BY b.parent_branch_id
)

SELECT
    b.branch_id,
    b.branch_name,
    b.branch_type,
    b.branch_size,
    b.status AS branch_status_at_cutoff,

    b.opening_year,
    b.closing_year,

    CASE
        WHEN b.closing_year IS NOT NULL
            THEN b.closing_year - b.opening_year
        ELSE 2026 - b.opening_year
    END AS branch_age_years,

    b.opening_reason,
    b.closure_reason,

    b.parent_branch_id,
    pb.branch_name AS parent_branch_name,

    COALESCE(cc.child_branch_count, 0)
        AS child_branch_count,

    CASE
        WHEN COALESCE(cc.child_branch_count, 0) > 0
            THEN 1
        ELSE 0
    END AS is_parent_branch,

    b.department,
    b.locality,
    b.region,
    b.latitude,
    b.longitude

FROM core.branches AS b

LEFT JOIN core.branches AS pb
    ON pb.branch_id = b.parent_branch_id

LEFT JOIN child_counts AS cc
    ON cc.parent_branch_id = b.branch_id;


-- ============================================================
-- 03. CURRENT COMMERCIAL FOOTPRINT — SQL PREPARATION
-- ============================================================
--
-- Grain:
-- 1 row = 1 branch
--
-- This is a current structural snapshot.
--
-- Customer attribution:
-- primary branch = customers.primary_branch_id
--
-- Account attribution:
-- servicing branch = accounts.branch_id
--
-- Loan attribution:
-- origination / loan branch = loans.branch_id
--
-- Current loan relationship:
-- closing_year IS NULL is used instead of loan_status = 'ACTIVE'.
-- This preserves open DEFAULTED / RESTRUCTURED exposures at cutoff.
--
-- Loan monetary amounts are deliberately omitted here because the
-- loan master stores native currencies. Current monetary lending scale
-- is available in the UYU-equivalent branch performance layer.
--
-- These are distinct business relationships and should not be
-- interpreted as exactly the same concept.


WITH customer_counts AS (
    SELECT
        c.primary_branch_id AS branch_id,

        COUNT(*) FILTER (
            WHERE c.customer_status = 'ACTIVE'
        ) AS active_primary_customers,

        COUNT(*) FILTER (
            WHERE c.customer_status = 'ACTIVE'
              AND c.customer_type = 'INDIVIDUAL'
        ) AS active_individual_customers,

        COUNT(*) FILTER (
            WHERE c.customer_status = 'ACTIVE'
              AND c.customer_type = 'BUSINESS'
        ) AS active_business_customers

    FROM core.customers AS c

    WHERE c.primary_branch_id IS NOT NULL

    GROUP BY c.primary_branch_id
),

account_counts AS (
    SELECT
        a.branch_id,

        COUNT(*) AS total_accounts,

        COUNT(*) FILTER (
            WHERE a.account_status = 'ACTIVE'
        ) AS active_accounts

    FROM core.accounts AS a

    GROUP BY a.branch_id
),

loan_counts AS (
    SELECT
        l.branch_id,

        COUNT(*) AS total_loans,

        COUNT(*) FILTER (
            WHERE l.closing_year IS NULL
        ) AS open_loans_at_cutoff

    FROM banking.loans AS l

    GROUP BY l.branch_id
)

SELECT
    b.branch_id,
    b.branch_name,
    b.branch_type,
    b.branch_size,
    b.status AS branch_status_at_cutoff,
    b.department,
    b.region,

    COALESCE(cc.active_primary_customers, 0)
        AS active_primary_customers,

    COALESCE(cc.active_individual_customers, 0)
        AS active_individual_customers,

    COALESCE(cc.active_business_customers, 0)
        AS active_business_customers,

    COALESCE(ac.total_accounts, 0)
        AS total_accounts,

    COALESCE(ac.active_accounts, 0)
        AS active_accounts,

    COALESCE(lc.total_loans, 0)
        AS total_loans,

    COALESCE(lc.open_loans_at_cutoff, 0)
        AS open_loans_at_cutoff

FROM core.branches AS b

LEFT JOIN customer_counts AS cc
    ON cc.branch_id = b.branch_id

LEFT JOIN account_counts AS ac
    ON ac.branch_id = b.branch_id

LEFT JOIN loan_counts AS lc
    ON lc.branch_id = b.branch_id

ORDER BY
    active_primary_customers DESC,
    active_accounts DESC;


-- ============================================================
-- 04. BRANCH-MONTH PERFORMANCE BASE — SQL PREPARATION
-- ============================================================
--
-- Grain:
-- 1 row = 1 branch × 1 month
--
-- This is the principal reusable branch-performance source for
-- Power BI.
--
-- branch_status_at_cutoff is a master/cutoff attribute from core.branches;
-- it must not be interpreted as the branch's historical status in each month.
--
-- Most derived ratios should be created as DAX measures rather
-- than permanently precomputed here.

SELECT
    bmp.branch_id,
    bmp.year_month,

    b.branch_name,
    b.branch_type,
    b.branch_size,
    b.status AS branch_status_at_cutoff,
    b.opening_year,
    b.department,
    b.locality,
    b.region,

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
    bmp.net_income

FROM performance.branch_monthly_performance AS bmp

JOIN core.branches AS b
    ON b.branch_id = bmp.branch_id;


-- ============================================================
-- 05. MONTHLY NETWORK BASELINE — SQL VALIDATION
-- ============================================================
--
-- Compact bank-network time series.
--
-- Useful for validating later DAX totals.
-- These are already management-performance metrics from the
-- performance schema; do not combine them casually with raw
-- account-balance currencies unless semantics are explicitly aligned.

SELECT
    bmp.year_month,

    SUM(bmp.active_customers)
        AS branch_reported_active_customers,

    SUM(bmp.active_accounts)
        AS branch_reported_active_accounts,

    ROUND(
        SUM(bmp.average_deposits)::NUMERIC,
        2
    ) AS bank_average_deposits_reconstructed,

    ROUND(
        SUM(bmp.average_loan_balance)::NUMERIC,
        2
    ) AS bank_average_loan_balance_reconstructed,

    SUM(bmp.transaction_count)
        AS transaction_count,

    ROUND(
        SUM(bmp.transaction_volume)::NUMERIC,
        2
    ) AS transaction_volume,

    ROUND(
        SUM(bmp.total_revenue)::NUMERIC,
        2
    ) AS total_revenue,

    ROUND(
        SUM(bmp.total_operating_cost)::NUMERIC,
        2
    ) AS total_operating_cost,

    ROUND(
        SUM(bmp.credit_loss)::NUMERIC,
        2
    ) AS credit_loss,

    ROUND(
        SUM(bmp.net_income)::NUMERIC,
        2
    ) AS net_income

FROM performance.branch_monthly_performance AS bmp

GROUP BY bmp.year_month

ORDER BY bmp.year_month;


-- 5.2 Cross-file reconciliation ownership.
-- The canonical full branch-to-bank reconciliation is kept in
-- 07_performance.sql so the same integrity logic is not duplicated here.


-- ============================================================
-- 06. BRANCH PERFORMANCE SNAPSHOT — SQL VALIDATION
-- ============================================================
--
-- Latest available month by branch.
--
-- This query is useful for quick validation / exploration.
-- Rankings and comparative ratios should remain dynamic in DAX.

WITH latest_month AS (
    SELECT
        MAX(bmp.year_month) AS year_month
    FROM performance.branch_monthly_performance AS bmp
)

SELECT
    bmp.year_month,
    bmp.branch_id,
    b.branch_name,
    b.branch_type,
    b.branch_size,
    b.region,

    bmp.active_customers,
    bmp.active_accounts,

    ROUND(
        bmp.average_deposits::NUMERIC,
        2
    ) AS average_deposits,

    ROUND(
        bmp.average_loan_balance::NUMERIC,
        2
    ) AS average_loan_balance,

    bmp.transaction_count,
    bmp.branch_transaction_count,

    ROUND(
        bmp.total_revenue::NUMERIC,
        2
    ) AS total_revenue,

    ROUND(
        bmp.total_operating_cost::NUMERIC,
        2
    ) AS total_operating_cost,

    ROUND(
        bmp.credit_loss::NUMERIC,
        2
    ) AS credit_loss,

    ROUND(
        bmp.pre_provision_profit::NUMERIC,
        2
    ) AS pre_provision_profit,

    ROUND(
        bmp.net_income::NUMERIC,
        2
    ) AS net_income

FROM performance.branch_monthly_performance AS bmp

JOIN latest_month AS lm
    ON lm.year_month = bmp.year_month

JOIN core.branches AS b
    ON b.branch_id = bmp.branch_id

ORDER BY
    bmp.net_income DESC;


-- ============================================================
-- 07. BRANCH TYPE / SIZE BASELINE — SQL VALIDATION
-- ============================================================
--
-- Latest-month structural comparison.
--
-- Final efficiency ratios belong in DAX.

WITH latest_month AS (
    SELECT
        MAX(bmp.year_month) AS year_month
    FROM performance.branch_monthly_performance AS bmp
)

SELECT
    b.branch_type,
    b.branch_size,

    COUNT(DISTINCT bmp.branch_id) AS branch_count,

    SUM(bmp.active_customers)
        AS active_customers,

    SUM(bmp.active_accounts)
        AS active_accounts,

    ROUND(
        SUM(bmp.total_revenue)::NUMERIC,
        2
    ) AS total_revenue,

    ROUND(
        SUM(bmp.total_operating_cost)::NUMERIC,
        2
    ) AS total_operating_cost,

    ROUND(
        SUM(bmp.net_income)::NUMERIC,
        2
    ) AS net_income

FROM performance.branch_monthly_performance AS bmp

JOIN latest_month AS lm
    ON lm.year_month = bmp.year_month

JOIN core.branches AS b
    ON b.branch_id = bmp.branch_id

GROUP BY
    b.branch_type,
    b.branch_size

ORDER BY
    b.branch_type,
    b.branch_size;


-- ============================================================
-- 08. REGIONAL PERFORMANCE BASELINE — SQL VALIDATION
-- ============================================================
--
-- Latest-month regional comparison.
--
-- Region shares and per-customer measures belong in DAX.

WITH latest_month AS (
    SELECT
        MAX(bmp.year_month) AS year_month
    FROM performance.branch_monthly_performance AS bmp
)

SELECT
    b.region,

    COUNT(DISTINCT bmp.branch_id) AS branch_count,

    SUM(bmp.active_customers)
        AS active_customers,

    SUM(bmp.active_accounts)
        AS active_accounts,

    ROUND(
        SUM(bmp.average_deposits)::NUMERIC,
        2
    ) AS regional_average_deposits,

    ROUND(
        SUM(bmp.average_loan_balance)::NUMERIC,
        2
    ) AS regional_average_loan_balance,

    ROUND(
        SUM(bmp.total_revenue)::NUMERIC,
        2
    ) AS total_revenue,

    ROUND(
        SUM(bmp.total_operating_cost)::NUMERIC,
        2
    ) AS total_operating_cost,

    ROUND(
        SUM(bmp.credit_loss)::NUMERIC,
        2
    ) AS credit_loss,

    ROUND(
        SUM(bmp.net_income)::NUMERIC,
        2
    ) AS net_income

FROM performance.branch_monthly_performance AS bmp

JOIN latest_month AS lm
    ON lm.year_month = bmp.year_month

JOIN core.branches AS b
    ON b.branch_id = bmp.branch_id

GROUP BY b.region

ORDER BY net_income DESC;


-- ============================================================
-- 09. BRANCH LIFECYCLE SUPPORT — SQL PREPARATION
-- ============================================================
--
-- Adds branch age at each performance month.
--
-- Useful later for comparing young versus mature branches.
--
-- In the PostgreSQL relational model, year_month is stored as DATE,
-- so EXTRACT(YEAR FROM year_month) is valid here.

SELECT
    bmp.branch_id,
    bmp.year_month,

    b.branch_name,
    b.branch_type,
    b.branch_size,
    b.region,
    b.opening_year,

    EXTRACT(
        YEAR FROM bmp.year_month
    )::INT - b.opening_year AS branch_age_at_month,

    bmp.active_customers,
    bmp.active_accounts,
    bmp.total_revenue,
    bmp.total_operating_cost,
    bmp.credit_loss,
    bmp.net_income

FROM performance.branch_monthly_performance AS bmp

JOIN core.branches AS b
    ON b.branch_id = bmp.branch_id

WHERE EXTRACT(YEAR FROM bmp.year_month)::INT >= b.opening_year
  AND (
        b.closing_year IS NULL
        OR EXTRACT(YEAR FROM bmp.year_month)::INT <= b.closing_year
      )

ORDER BY
    bmp.branch_id,
    bmp.year_month;


-- ============================================================
-- 10. BRANCH HIERARCHY
-- ============================================================

-- 10.1 Parent / child branch relationships.

SELECT
    parent.branch_id AS parent_branch_id,
    parent.branch_name AS parent_branch_name,

    child.branch_id AS child_branch_id,
    child.branch_name AS child_branch_name,
    child.branch_type AS child_branch_type,
    child.branch_size AS child_branch_size,
    child.status AS child_branch_status_at_cutoff,
    child.region AS child_region

FROM core.branches AS child

JOIN core.branches AS parent
    ON parent.branch_id = child.parent_branch_id

ORDER BY
    parent.branch_name,
    child.branch_name;


-- ============================================================
-- 11. DATA-QUALITY DIAGNOSTICS
-- ============================================================

-- 11.1 Contradictory branch status / closing-year combinations.

SELECT
    b.branch_id,
    b.branch_name,
    b.status,
    b.opening_year,
    b.closing_year,
    b.closure_reason
FROM core.branches AS b
WHERE
    (b.status = 'OPEN' AND b.closing_year IS NOT NULL)
    OR
    (b.status = 'CLOSED' AND b.closing_year IS NULL)
ORDER BY b.branch_id;


-- 11.2 Closing year before opening year.

SELECT
    b.branch_id,
    b.branch_name,
    b.opening_year,
    b.closing_year
FROM core.branches AS b
WHERE b.closing_year IS NOT NULL
  AND b.closing_year < b.opening_year
ORDER BY b.branch_id;


-- 11.3 Self-parenting branch.

SELECT
    b.branch_id,
    b.branch_name,
    b.parent_branch_id
FROM core.branches AS b
WHERE b.parent_branch_id = b.branch_id;


-- 11.4 Duplicate branch-month rows.
-- The relational PK should make this return zero rows.

SELECT
    bmp.branch_id,
    bmp.year_month,
    COUNT(*) AS row_count
FROM performance.branch_monthly_performance AS bmp
GROUP BY
    bmp.branch_id,
    bmp.year_month
HAVING COUNT(*) > 1
ORDER BY row_count DESC;


-- 11.5 Branch-performance temporal coverage.

SELECT
    MIN(bmp.year_month) AS first_performance_month,
    MAX(bmp.year_month) AS last_performance_month,
    COUNT(DISTINCT bmp.year_month) AS month_count,
    COUNT(*) AS branch_month_rows,
    COUNT(DISTINCT bmp.branch_id) AS branches_with_performance
FROM performance.branch_monthly_performance AS bmp;


-- 11.6 Missing branch-month coverage.
-- Expected result: zero rows when every branch is represented
-- in every performance month.

SELECT
    bmp.year_month,
    COUNT(DISTINCT bmp.branch_id) AS branches_present,
    (
        SELECT COUNT(*)
        FROM core.branches
    ) AS expected_branches
FROM performance.branch_monthly_performance AS bmp
GROUP BY bmp.year_month
HAVING COUNT(DISTINCT bmp.branch_id) <> (
    SELECT COUNT(*)
    FROM core.branches
)
ORDER BY bmp.year_month;


-- 11.7 Accounting-identity residuals.
-- Expected result: residuals approximately zero.

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
    ) AS max_net_interest_residual,

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
    ) AS max_revenue_residual,

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
    ) AS max_operating_cost_residual,

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
    ) AS max_pre_provision_residual,

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

FROM performance.branch_monthly_performance AS bmp;


-- ============================================================
-- 12. DOWNSTREAM ANALYTICAL HANDOFF
-- ============================================================
--
-- POWER BI / DAX
--
-- Preferred source:
-- branch-month performance base
--
-- Dynamic measures:
--
-- SEMI-ADDITIVE / SNAPSHOT MEASURES
-- (sum across branches at one month; define explicit time logic)
--
-- - Active Customers
-- - Active Accounts
-- - Average Deposits
-- - Average Loan Balance
--
-- ADDITIVE FLOW MEASURES
-- - Transaction Count
-- - Transaction Volume
-- - Total Revenue
-- - Total Operating Cost
-- - Credit Loss
-- - Pre-Provision Profit
-- - Net Income
-- - Revenue per Customer
-- - Revenue per Account
-- - Net Income per Customer
-- - Cost-to-Income
-- - Deposit per Customer
-- - Loan Balance per Customer
-- - Branch Share of Revenue
-- - Branch Share of Customers
-- - YoY Revenue Growth
-- - YoY Net Income Growth
--
-- IMPORTANT FOR DAX:
-- Do not SUM snapshot/stock measures across months.
-- Example annual rules:
-- - deposits / loan balance: average of monthly portfolio stocks
-- - active customers / accounts: end-of-period or monthly average,
--   depending on the KPI definition
-- - revenue / costs / credit loss / net income: SUM across months
--
-- Filters:
--
-- - year / month
-- - branch
-- - branch type
-- - branch size
-- - status
-- - region
-- - department
--
--
-- TABLEAU
--
-- Strong candidates:
--
-- - branch map
-- - geographic network coverage
-- - regional business volume
-- - branch size/type overlays
-- - spatial profitability storytelling
--
--
-- PYTHON
--
-- Potential branch analysis:
--
-- - outlier branches
-- - branch-performance distributions
-- - scale vs profitability
-- - clustering by business profile
-- - branch trajectories
-- - lifecycle analysis
--
--
-- TRANSACTION DETAIL
--
-- Reuse the branch-month aggregate from 04_transactions.sql.
-- Do not repeatedly scan banking.transactions here.
--
-- ============================================================
-- 13. PERSISTENCE DECISION
-- ============================================================
--
-- Candidate reusable objects:
--
-- - branch dimension
-- - current branch commercial snapshot
-- - branch-month performance base
--
-- Persist as views/materialized views only when:
--
-- 1. the grain is stable;
-- 2. the logic is reused;
-- 3. downstream tools benefit;
-- 4. refresh semantics are clear.
--
-- ============================================================
-- END
-- ============================================================
