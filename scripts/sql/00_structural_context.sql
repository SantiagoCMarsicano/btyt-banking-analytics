-- ============================================================
-- BTYT — STRUCTURAL CONTEXT
-- File: 00_structural_context.sql
-- Purpose: Build a reusable "census" of the BTYT banking universe
-- PostgreSQL | Read-only analytical queries
-- ============================================================
--
-- HOW TO USE
-- - Run one statement at a time.
-- - These queries describe the structure of the bank before KPI analysis.
-- - They are intentionally descriptive: counts, shares, categories, coverage.
-- - Use this file to establish the bank's structural baseline before KPI analysis.
-- - Structural NULLs are described first; do not label them as data-quality errors
--   until their relationship with customer type / business logic is checked.
-- - No query modifies canonical BTYT data.
-- - Prefer saving the interesting outputs/notes separately rather than editing
--   the database itself.
--
-- Suggested repo path:
-- scripts/sql/00_structural_context.sql
--
-- ============================================================
-- 00. CONNECTION CHECK
-- ============================================================

SELECT
    current_database() AS database_name,
    current_user AS database_user,
    current_schema() AS current_schema;


-- ============================================================
-- 01. BRANCH NETWORK
-- ============================================================

-- 1.1 Total number of branches.
SELECT
    COUNT(*) AS total_branches
FROM core.branches;


-- 1.2 Branches by status.
SELECT
    b.status,
    COUNT(*) AS branch_count,
    ROUND(
        100.0 * COUNT(*) / SUM(COUNT(*)) OVER (),
        2
    ) AS pct_of_branches
FROM core.branches AS b
GROUP BY b.status
ORDER BY branch_count DESC;


-- 1.3 Which branches are closed?
SELECT
    b.branch_id,
    b.branch_name,
    b.branch_type,
    b.branch_size,
    b.department,
    b.locality,
    b.region,
    b.opening_year,
    b.closing_year,
    b.closure_reason
FROM core.branches AS b
WHERE b.status = 'CLOSED'
   OR b.closing_year IS NOT NULL
ORDER BY
    b.closing_year,
    b.branch_id;

-- 1.3.1 Check for closed branches
SELECT
    COUNT(*) FILTER (WHERE closing_year IS NOT NULL) AS with_closing_year,
    COUNT(*) FILTER (WHERE closure_reason IS NOT NULL) AS with_closure_reason
FROM core.branches;

-- 1.4 Branches by region.
SELECT
    b.region,
    COUNT(*) AS branch_count,
    ROUND(
        100.0 * COUNT(*) / SUM(COUNT(*)) OVER (),
        2
    ) AS branch_percentage
FROM core.branches AS b
GROUP BY b.region
ORDER BY branch_count DESC;


-- 1.5 Branches by department.
SELECT
    b.department,
    COUNT(*) AS branch_count
FROM core.branches AS b
GROUP BY b.department
ORDER BY
    branch_count DESC,
    b.department;


-- 1.6 Branches by type.
SELECT
    b.branch_type,
    COUNT(*) AS branch_count,
    ROUND(
        100.0 * COUNT(*) / SUM(COUNT(*)) OVER (),
        2
    ) AS pct_of_branches
FROM core.branches AS b
GROUP BY b.branch_type
ORDER BY branch_count DESC;


-- 1.7 Branches by size.
SELECT
    b.branch_size,
    COUNT(*) AS branch_count,
    ROUND(
        100.0 * COUNT(*) / SUM(COUNT(*)) OVER (),
        2
    ) AS branch_percentage
FROM core.branches AS b
GROUP BY b.branch_size
ORDER BY branch_count DESC;


-- 1.8 Branch type × branch size.
SELECT
    b.branch_type,
    b.branch_size,
    COUNT(*) AS branch_count
FROM core.branches AS b
GROUP BY
    b.branch_type,
    b.branch_size
ORDER BY
    b.branch_type,
    b.branch_size;


-- 1.9 Branches with a parent branch.
SELECT
    child.branch_id,
    child.branch_name,
    child.branch_type,
    parent.branch_id AS parent_branch_id,
    parent.branch_name AS parent_branch_name
FROM core.branches AS child
LEFT JOIN core.branches AS parent
    ON child.parent_branch_id = parent.branch_id
WHERE child.parent_branch_id IS NOT NULL
ORDER BY
    parent.branch_name,
    child.branch_name;


-- 1.10 Network expansion by opening year.
SELECT
    b.opening_year,
    COUNT(*) AS branches_opened
FROM core.branches AS b
GROUP BY b.opening_year
ORDER BY b.opening_year;



-- 1.11 Branches by opening reason.
SELECT
    COALESCE(b.opening_reason, 'UNKNOWN') AS opening_reason,
    COUNT(*) AS branch_count
FROM core.branches AS b
GROUP BY COALESCE(b.opening_reason, 'UNKNOWN')
ORDER BY branch_count DESC;


-- 1.12 Closure reasons among closed branches.
SELECT
    COALESCE(b.closure_reason, 'UNKNOWN') AS closure_reason,
    COUNT(*) AS branch_count
FROM core.branches AS b
WHERE b.closing_year IS NOT NULL
GROUP BY COALESCE(b.closure_reason, 'UNKNOWN')
ORDER BY branch_count DESC;


-- 1.13 Structural consistency check: branch status vs closing year.
-- Ideally this returns zero rows or only cases justified by the model rules.
SELECT
    b.branch_id,
    b.branch_name,
    b.status,
    b.closing_year,
    b.closure_reason
FROM core.branches AS b
WHERE
    (b.status = 'OPEN' AND b.closing_year IS NOT NULL)
    OR
    (b.status = 'CLOSED' AND b.closing_year IS NULL);


-- ============================================================
-- 02. CUSTOMER BASE
-- ============================================================

-- 2.1 Total customers.
SELECT
    COUNT(*) AS total_customers
FROM core.customers;


-- 2.2 Customers by status.
SELECT
    c.customer_status,
    COUNT(*) AS customer_count,
    ROUND(
        100.0 * COUNT(*) / SUM(COUNT(*)) OVER (),
        2
    ) AS pct_of_customers
FROM core.customers AS c
GROUP BY c.customer_status
ORDER BY customer_count DESC;


-- 2.3 Customers by type: individuals vs businesses.
SELECT
    c.customer_type,
    COUNT(*) AS customer_count,
    ROUND(
        100.0 * COUNT(*) / SUM(COUNT(*)) OVER (),
        2
    ) AS pct_of_customers
FROM core.customers AS c
GROUP BY c.customer_type
ORDER BY customer_count DESC;


-- 2.4 Customer status × customer type.
SELECT
    c.customer_type,
    c.customer_status,
    COUNT(*) AS customer_count
FROM core.customers AS c
GROUP BY
    c.customer_type,
    c.customer_status
ORDER BY
    c.customer_type,
    customer_count DESC;


-- 2.5 Nationality distribution, keeping NULL visible.
SELECT
    COALESCE(c.nationality, 'NULL / NOT RECORDED') AS nationality,
    COUNT(*) AS customer_count,
    ROUND(
        100.0 * COUNT(*) / SUM(COUNT(*)) OVER (),
        2
    ) AS pct_of_customers
FROM core.customers AS c
GROUP BY COALESCE(c.nationality, 'NULL / NOT RECORDED')
ORDER BY customer_count DESC;


-- 2.6 Check whether nationality NULLs are structural by customer type.
SELECT
    c.customer_type,
    COUNT(*) AS total_customers,
    COUNT(*) FILTER (WHERE c.nationality IS NULL) AS nationality_null_count,
    ROUND(
        100.0
        * COUNT(*) FILTER (WHERE c.nationality IS NULL)
        / NULLIF(COUNT(*), 0),
        2
    ) AS nationality_null_pct
FROM core.customers AS c
GROUP BY c.customer_type
ORDER BY c.customer_type;


-- 2.7 Customers by residence department.
SELECT
    COALESCE(c.residence_department, 'UNKNOWN') AS residence_department,
    COUNT(*) AS customer_count
FROM core.customers AS c
GROUP BY COALESCE(c.residence_department, 'UNKNOWN')
ORDER BY customer_count DESC;


-- 2.8 Customers by region through their primary branch.
SELECT
    b.region,
    COUNT(*) AS customer_count,
    ROUND(
        100.0 * COUNT(*) / SUM(COUNT(*)) OVER (),
        2
    ) AS pct_of_customers
FROM core.customers AS c
LEFT JOIN core.branches AS b
    ON c.primary_branch_id = b.branch_id
GROUP BY b.region
ORDER BY customer_count DESC;


-- 2.9 Customers by primary branch.
SELECT
    b.branch_id,
    b.branch_name,
    b.region,
    COUNT(c.customer_id) AS customer_count
FROM core.branches AS b
LEFT JOIN core.customers AS c
    ON c.primary_branch_id = b.branch_id
GROUP BY
    b.branch_id,
    b.branch_name,
    b.region
ORDER BY customer_count DESC;


-- 2.10 Gender distribution among individual customers.
SELECT
    COALESCE(c.gender, 'UNKNOWN') AS gender,
    COUNT(*) AS customer_count,
    ROUND(
        100.0 * COUNT(*) / SUM(COUNT(*)) OVER (),
        2
    ) AS pct_of_individual_customers
FROM core.customers AS c
WHERE c.customer_type = 'INDIVIDUAL'
GROUP BY COALESCE(c.gender, 'UNKNOWN')
ORDER BY customer_count DESC;


-- 2.11 Approximate age distribution among individuals at the 2026 endpoint.
-- The explicit out-of-range bucket avoids silently classifying impossible ages as 65+.
WITH individual_ages AS (
    SELECT
        c.customer_id,
        CASE
            WHEN c.birth_year IS NULL THEN NULL
            ELSE 2026 - c.birth_year
        END AS approx_age
    FROM core.customers AS c
    WHERE c.customer_type = 'INDIVIDUAL'
)
SELECT
    CASE
        WHEN ia.approx_age IS NULL THEN 'UNKNOWN'
        WHEN ia.approx_age < 18 OR ia.approx_age > 110 THEN 'OUT_OF_RANGE'
        WHEN ia.approx_age BETWEEN 18 AND 24 THEN '18-24'
        WHEN ia.approx_age BETWEEN 25 AND 34 THEN '25-34'
        WHEN ia.approx_age BETWEEN 35 AND 44 THEN '35-44'
        WHEN ia.approx_age BETWEEN 45 AND 54 THEN '45-54'
        WHEN ia.approx_age BETWEEN 55 AND 64 THEN '55-64'
        ELSE '65+'
    END AS age_group,
    COUNT(*) AS customer_count
FROM individual_ages AS ia
GROUP BY 1
ORDER BY
    CASE
        WHEN CASE
            WHEN ia.approx_age IS NULL THEN 'UNKNOWN'
            WHEN ia.approx_age < 18 OR ia.approx_age > 110 THEN 'OUT_OF_RANGE'
            WHEN ia.approx_age BETWEEN 18 AND 24 THEN '18-24'
            WHEN ia.approx_age BETWEEN 25 AND 34 THEN '25-34'
            WHEN ia.approx_age BETWEEN 35 AND 44 THEN '35-44'
            WHEN ia.approx_age BETWEEN 45 AND 54 THEN '45-54'
            WHEN ia.approx_age BETWEEN 55 AND 64 THEN '55-64'
            ELSE '65+'
        END
            WHEN '18-24' THEN 1
            WHEN '25-34' THEN 2
            WHEN '35-44' THEN 3
            WHEN '45-54' THEN 4
            WHEN '55-64' THEN 5
            WHEN '65+' THEN 6
            WHEN 'OUT_OF_RANGE' THEN 7
            ELSE 8
        END;


-- 2.12 Individual income summary.
-- Median and quartiles are more informative than the mean alone for skewed income data.
SELECT
    COUNT(*) AS individual_customers,
    COUNT(c.monthly_income) AS customers_with_income,
    COUNT(*) - COUNT(c.monthly_income) AS customers_without_income,
    ROUND(AVG(c.monthly_income), 2) AS avg_monthly_income,
    ROUND(
        PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY c.monthly_income)::NUMERIC,
        2
    ) AS p25_monthly_income,
    ROUND(
        PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY c.monthly_income)::NUMERIC,
        2
    ) AS median_monthly_income,
    ROUND(
        PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY c.monthly_income)::NUMERIC,
        2
    ) AS p75_monthly_income,
    ROUND(MIN(c.monthly_income), 2) AS min_monthly_income,
    ROUND(MAX(c.monthly_income), 2) AS max_monthly_income
FROM core.customers AS c
WHERE c.customer_type = 'INDIVIDUAL';


-- 2.13 Business customers by company size.
SELECT
    COALESCE(c.company_size, 'UNKNOWN') AS company_size,
    COUNT(*) AS business_count
FROM core.customers AS c
WHERE c.customer_type = 'BUSINESS'
GROUP BY COALESCE(c.company_size, 'UNKNOWN')
ORDER BY business_count DESC;


-- 2.14 Business customers by sector.
SELECT
    COALESCE(c.business_sector, 'UNKNOWN') AS business_sector,
    COUNT(*) AS business_count
FROM core.customers AS c
WHERE c.customer_type = 'BUSINESS'
GROUP BY COALESCE(c.business_sector, 'UNKNOWN')
ORDER BY business_count DESC;



-- 2.15 Customer registrations by year.
SELECT
    c.registration_year,
    COUNT(*) AS customers_registered
FROM core.customers AS c
GROUP BY c.registration_year
ORDER BY c.registration_year;


-- 2.16 Structural consistency check: customer status vs closing year.
-- Ideally this returns zero rows or only cases justified by the model rules.
SELECT
    c.customer_id,
    c.customer_status,
    c.closing_year
FROM core.customers AS c
WHERE
    (c.customer_status = 'ACTIVE' AND c.closing_year IS NOT NULL)
    OR
    (c.customer_status <> 'ACTIVE' AND c.closing_year IS NULL)
LIMIT 100;


-- ============================================================
-- 03. PRODUCTS
-- ============================================================

-- 3.1 Total products.
SELECT
    COUNT(*) AS total_products
FROM core.products;


-- 3.2 Product catalog.
SELECT
    p.product_id,
    p.product_name,
    p.product_family,
    p.currency,
    p.target_customer_type,
    p.launch_year
FROM core.products AS p
ORDER BY
    p.product_family,
    p.product_id;


-- 3.3 Products by family.
SELECT
    p.product_family,
    COUNT(*) AS product_count
FROM core.products AS p
GROUP BY p.product_family
ORDER BY product_count DESC;


-- 3.4 Products by target customer type.
SELECT
    p.target_customer_type,
    COUNT(*) AS product_count
FROM core.products AS p
GROUP BY p.target_customer_type
ORDER BY product_count DESC;


-- 3.5 Products by currency.
SELECT
    p.currency,
    COUNT(*) AS product_count
FROM core.products AS p
GROUP BY p.currency
ORDER BY product_count DESC;


-- ============================================================
-- 04. ACCOUNTS
-- ============================================================

-- 4.1 Total accounts.
SELECT
    COUNT(*) AS total_accounts
FROM core.accounts;


-- 4.2 Accounts by status.
SELECT
    a.account_status,
    COUNT(*) AS account_count,
    ROUND(
        100.0 * COUNT(*) / SUM(COUNT(*)) OVER (),
        2
    ) AS pct_of_accounts
FROM core.accounts AS a
GROUP BY a.account_status
ORDER BY account_count DESC;


-- 4.3 Accounts by product.
SELECT
    p.product_id,
    p.product_name,
    p.product_family,
    COUNT(a.account_id) AS account_count
FROM core.products AS p
LEFT JOIN core.accounts AS a
    ON a.product_id = p.product_id
GROUP BY
    p.product_id,
    p.product_name,
    p.product_family
ORDER BY account_count DESC;


-- 4.4 Accounts by branch.
SELECT
    b.branch_id,
    b.branch_name,
    b.region,
    COUNT(a.account_id) AS account_count
FROM core.branches AS b
LEFT JOIN core.accounts AS a
    ON a.branch_id = b.branch_id
GROUP BY
    b.branch_id,
    b.branch_name,
    b.region
ORDER BY account_count DESC;


-- 4.5 Accounts by opening channel.
SELECT
    a.opening_channel,
    COUNT(*) AS account_count
FROM core.accounts AS a
GROUP BY a.opening_channel
ORDER BY account_count DESC;


-- 4.6 Account openings by year.
SELECT
    a.opening_year,
    COUNT(*) AS accounts_opened
FROM core.accounts AS a
GROUP BY a.opening_year
ORDER BY a.opening_year;


-- 4.7 Account closures by year.
SELECT
    a.closing_year,
    COUNT(*) AS accounts_closed
FROM core.accounts AS a
WHERE a.closing_year IS NOT NULL
GROUP BY a.closing_year
ORDER BY a.closing_year;



-- 4.8 Structural consistency check: account status vs closing year.
SELECT
    a.account_id,
    a.account_status,
    a.closing_year
FROM core.accounts AS a
WHERE
    (a.account_status = 'ACTIVE' AND a.closing_year IS NOT NULL)
    OR
    (a.account_status <> 'ACTIVE' AND a.closing_year IS NULL)
LIMIT 100;


-- ============================================================
-- 05. CARDS
-- ============================================================

-- 5.1 Total cards.
SELECT
    COUNT(*) AS total_cards
FROM banking.cards;


-- 5.2 Cards by product.
-- LEFT JOIN keeps card products visible even if one has zero issued cards.
SELECT
    p.product_id,
    p.product_name,
    COUNT(ca.card_id) AS card_count
FROM core.products AS p
LEFT JOIN banking.cards AS ca
    ON ca.product_id = p.product_id
WHERE p.product_family = 'CARD'
GROUP BY
    p.product_id,
    p.product_name
ORDER BY card_count DESC;


-- 5.3 Cards by status.
SELECT
    ca.card_status,
    COUNT(*) AS card_count,
    ROUND(
        100.0 * COUNT(*) / SUM(COUNT(*)) OVER (),
        2
    ) AS pct_of_cards
FROM banking.cards AS ca
GROUP BY ca.card_status
ORDER BY card_count DESC;



-- 5.4 Cards issued by year.
SELECT
    ca.issue_year,
    COUNT(*) AS cards_issued
FROM banking.cards AS ca
GROUP BY ca.issue_year
ORDER BY ca.issue_year;


-- 5.5 Cards by issue channel.
SELECT
    ca.issue_channel,
    COUNT(*) AS card_count
FROM banking.cards AS ca
GROUP BY ca.issue_channel
ORDER BY card_count DESC;


-- ============================================================
-- 06. LOANS
-- ============================================================

-- 6.1 Total loans.
SELECT
    COUNT(*) AS total_loans
FROM banking.loans;


-- 6.2 Loans by status.
SELECT
    l.loan_status,
    COUNT(*) AS loan_count,
    ROUND(
        100.0 * COUNT(*) / SUM(COUNT(*)) OVER (),
        2
    ) AS pct_of_loans
FROM banking.loans AS l
GROUP BY l.loan_status
ORDER BY loan_count DESC;


-- 6.3 Loans by product.
-- LEFT JOIN keeps lending products visible even if one has zero originated loans.
SELECT
    p.product_id,
    p.product_name,
    p.product_family,
    COUNT(l.loan_id) AS loan_count,
    ROUND(COALESCE(SUM(l.original_amount), 0), 2) AS total_original_amount
FROM core.products AS p
LEFT JOIN banking.loans AS l
    ON l.product_id = p.product_id
WHERE p.product_family IN ('RETAIL_LENDING', 'BUSINESS_LENDING')
GROUP BY
    p.product_id,
    p.product_name,
    p.product_family
ORDER BY loan_count DESC;


-- 6.4 Loans by branch.
SELECT
    b.branch_id,
    b.branch_name,
    b.region,
    COUNT(l.loan_id) AS loan_count,
    ROUND(SUM(l.original_amount), 2) AS total_original_amount
FROM core.branches AS b
LEFT JOIN banking.loans AS l
    ON l.branch_id = b.branch_id
GROUP BY
    b.branch_id,
    b.branch_name,
    b.region
ORDER BY loan_count DESC;



-- 6.5 Loan originations by year.
SELECT
    l.origination_year,
    COUNT(*) AS loans_originated,
    ROUND(SUM(l.original_amount), 2) AS original_amount
FROM banking.loans AS l
GROUP BY l.origination_year
ORDER BY l.origination_year;


-- 6.6 Loans by currency.
SELECT
    l.currency,
    COUNT(*) AS loan_count,
    ROUND(SUM(l.original_amount), 2) AS total_original_amount
FROM banking.loans AS l
GROUP BY l.currency
ORDER BY loan_count DESC;


-- ============================================================
-- 07. TRANSACTIONS AND TIME COVERAGE
-- ============================================================

-- NOTE:
-- banking.transactions is the largest table in BTYT.
-- Queries in this section may take noticeably longer.

-- 7.1 Exact transaction count.
-- HEAVY QUERY: COUNT(*) may scan the full transactions table.
SELECT
    COUNT(*) AS total_transactions
FROM banking.transactions;


-- 7.2 Transaction date coverage.
-- HEAVY QUERY unless an appropriate transaction_datetime index is available.
SELECT
    MIN(t.transaction_datetime) AS first_transaction,
    MAX(t.transaction_datetime) AS last_transaction
FROM banking.transactions AS t;


-- 7.3 Transaction types.
SELECT
    t.transaction_type,
    COUNT(*) AS transaction_count
FROM banking.transactions AS t
GROUP BY t.transaction_type
ORDER BY transaction_count DESC;


-- 7.4 Transaction channels.
SELECT
    t.channel,
    COUNT(*) AS transaction_count
FROM banking.transactions AS t
GROUP BY t.channel
ORDER BY transaction_count DESC;


-- 7.5 Transaction statuses.
SELECT
    t.transaction_status,
    COUNT(*) AS transaction_count
FROM banking.transactions AS t
GROUP BY t.transaction_status
ORDER BY transaction_count DESC;


-- ============================================================
-- 08. MONTHLY BALANCE / LOAN SNAPSHOT COVERAGE
-- ============================================================

-- 8.1 Account balance monthly coverage.
SELECT
    MIN(ab.year_month) AS first_balance_month,
    MAX(ab.year_month) AS last_balance_month,
    COUNT(DISTINCT ab.year_month) AS month_count,
    COUNT(*) AS balance_rows
FROM banking.account_balances AS ab;


-- 8.2 Loan snapshot monthly coverage.
SELECT
    MIN(lms.year_month) AS first_snapshot_month,
    MAX(lms.year_month) AS last_snapshot_month,
    COUNT(DISTINCT lms.year_month) AS month_count,
    COUNT(*) AS snapshot_rows
FROM banking.loan_monthly_snapshot AS lms;


-- ============================================================
-- 09. MARKETING STRUCTURE
-- ============================================================

-- 9.1 Total campaigns.
SELECT
    COUNT(*) AS total_campaigns
FROM marketing.campaigns;


-- 9.2 Campaigns by type.
SELECT
    c.campaign_type,
    COUNT(*) AS campaign_count
FROM marketing.campaigns AS c
GROUP BY c.campaign_type
ORDER BY campaign_count DESC;


-- 9.3 Campaigns by target customer type.
SELECT
    c.target_customer_type,
    COUNT(*) AS campaign_count
FROM marketing.campaigns AS c
GROUP BY c.target_customer_type
ORDER BY campaign_count DESC;


-- 9.4 Campaign date coverage.
SELECT
    MIN(c.start_date) AS first_campaign_start,
    MAX(c.end_date) AS last_campaign_end
FROM marketing.campaigns AS c;


-- 9.5 Campaign channels available.
SELECT
    cc.channel,
    COUNT(DISTINCT cc.campaign_id) AS campaign_count
FROM reference.campaign_channels AS cc
GROUP BY cc.channel
ORDER BY campaign_count DESC;


-- 9.6 Campaign geography levels.
SELECT
    cg.geography_level,
    COUNT(*) AS geography_rule_count,
    COUNT(DISTINCT cg.campaign_id) AS campaign_count
FROM reference.campaign_geography AS cg
GROUP BY cg.geography_level
ORDER BY geography_rule_count DESC;


-- ============================================================
-- 10. MARKET / EXTERNAL INSTITUTIONS
-- ============================================================

-- 10.1 Banks in the simulated market.
SELECT
    COUNT(*) AS total_banks
FROM market.banks;


-- 10.2 Banks by type and scope.
SELECT
    b.bank_type,
    b.bank_scope,
    COUNT(*) AS bank_count
FROM market.banks AS b
GROUP BY
    b.bank_type,
    b.bank_scope
ORDER BY
    b.bank_type,
    b.bank_scope;


-- 10.3 Banks by status.
SELECT
    b.bank_status,
    COUNT(*) AS bank_count
FROM market.banks AS b
GROUP BY b.bank_status
ORDER BY bank_count DESC;


-- 10.4 Banks by operating country.
SELECT
    b.operating_country,
    COUNT(*) AS bank_count
FROM market.banks AS b
GROUP BY b.operating_country
ORDER BY bank_count DESC;


-- 10.5 External financial institutions by type.
SELECT
    fi.institution_type,
    COUNT(*) AS institution_count
FROM market.financial_institutions AS fi
GROUP BY fi.institution_type
ORDER BY institution_count DESC;


-- 10.6 Domestic vs foreign institutions.
SELECT
    fi.domestic_flag,
    COUNT(*) AS institution_count
FROM market.financial_institutions AS fi
GROUP BY fi.domestic_flag
ORDER BY institution_count DESC;


-- ============================================================
-- 11. MACRO / PERFORMANCE COVERAGE
-- ============================================================

-- 11.1 Macro environment coverage.
SELECT
    MIN(me.year) AS first_macro_year,
    MAX(me.year) AS last_macro_year,
    COUNT(*) AS macro_year_rows
FROM macro.macro_environment AS me;


-- 11.2 External shock inventory.
SELECT
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
    es.recovery_end_month
FROM macro.external_shocks AS es
ORDER BY es.start_month;


-- 11.3 Bank monthly performance coverage.
SELECT
    MIN(bmp.year_month) AS first_performance_month,
    MAX(bmp.year_month) AS last_performance_month,
    COUNT(*) AS performance_months
FROM performance.bank_monthly_performance AS bmp;


-- 11.4 Branch monthly performance coverage.
SELECT
    MIN(bmp.year_month) AS first_performance_month,
    MAX(bmp.year_month) AS last_performance_month,
    COUNT(DISTINCT bmp.year_month) AS month_count,
    COUNT(DISTINCT bmp.branch_id) AS branch_count,
    COUNT(*) AS performance_rows
FROM performance.branch_monthly_performance AS bmp;


-- ============================================================
-- 12. COMPACT STRUCTURAL SUMMARY
-- ============================================================

-- A compact summary that can be rerun whenever you want a quick census.
-- Transaction count is deliberately excluded here to avoid repeating a full-table scan.
-- Use section 7.1 when you need the exact transaction count.

SELECT
    (SELECT COUNT(*) FROM core.branches) AS branches,
    (SELECT COUNT(*) FROM core.customers) AS customers,
    (SELECT COUNT(*) FROM core.accounts) AS accounts,
    (SELECT COUNT(*) FROM core.products) AS products,
    (SELECT COUNT(*) FROM banking.cards) AS cards,
    (SELECT COUNT(*) FROM banking.loans) AS loans,
    (SELECT COUNT(*) FROM marketing.campaigns) AS campaigns,
    (SELECT COUNT(*) FROM market.banks) AS banks,
    (SELECT COUNT(*) FROM market.financial_institutions) AS financial_institutions;



-- ============================================================
-- 13. STRUCTURAL INTERPRETATION CHECKLIST
-- ============================================================
--
-- Before moving to KPI analysis, be able to answer:
--
-- Branch network
-- - How many branches exist, and how are they distributed by status, region,
--   type and size?
-- - Which branches closed, when, and why?
--
-- Customers
-- - How many customers exist, and what share are individuals vs businesses?
-- - How are customers distributed by status, geography and primary branch?
-- - Are NULLs structural or unexpected?
--
-- Products / accounts / cards / loans
-- - What product families exist?
-- - How many accounts, cards and loans exist, and what are their main states?
-- - What is the temporal coverage of openings / issuances / originations?
--
-- Time / operations
-- - What period do transactions, balances, loan snapshots and performance cover?
--
-- Marketing / market / macro
-- - How many campaigns, channels, geography rules, banks, institutions and
--   external shocks exist?
--
-- Once these answers are clear, move from "what bank do we have?" to
-- "how is the bank performing, and why?"
--
-- ============================================================
-- END
-- ============================================================
--
-- NEXT STEP AFTER THIS FILE
--
-- Once this structural census is understood, move to business analysis:
--
-- 01. Branch profitability and efficiency
-- 02. Customer and product relationships
-- 03. Loan portfolio and credit quality
-- 04. Transactions and channels
-- 05. Campaign effectiveness
-- 06. Macro context and shocks
--
-- The structural file answers:
-- "What bank do we have?"
--
-- The next files answer:
-- "How is that bank performing, and why?"
-- ============================================================
