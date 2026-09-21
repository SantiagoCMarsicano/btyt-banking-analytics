-- ============================================================
-- BTYT BANKING ANALYTICS
-- 06_customer_and_account_relationships.sql
-- Customer growth, relationship depth and account behavior
-- ============================================================
--
-- Measurement rules:
-- - Customer/account lifecycle fields are annual, so lifecycle KPIs
--   are evaluated at annual grain.
-- - Current-snapshot measures use the latest year available in the
--   bank performance layer as analytical cutoff.
-- - Monetary account-balance measures remain separated by currency.
-- - Bank-performance deposits and loans are UYU-equivalent and can be
--   divided by bank-level active customers.
-- ============================================================


-- ============================================================
-- 00. INSPECT STATUS, CHANNEL AND PRODUCT DOMAINS
-- ============================================================

SELECT 'customer_status' AS field_name, customer_status AS field_value, COUNT(*) AS rows
FROM core.customers
GROUP BY customer_status

UNION ALL

SELECT 'account_status', account_status, COUNT(*)
FROM core.accounts
GROUP BY account_status

UNION ALL

SELECT 'card_status', card_status, COUNT(*)
FROM banking.cards
GROUP BY card_status

UNION ALL

SELECT 'opening_channel', opening_channel, COUNT(*)
FROM core.accounts
GROUP BY opening_channel

ORDER BY field_name, field_value;


-- ============================================================
-- 01. CUSTOMER GROWTH BY YEAR
-- ============================================================
-- Customer lifecycle is stored at year grain.

WITH years AS (
    SELECT DISTINCT registration_year::INT AS calendar_year
    FROM core.customers
    WHERE registration_year IS NOT NULL

    UNION

    SELECT DISTINCT closing_year::INT
    FROM core.customers
    WHERE closing_year IS NOT NULL
),
customer_flows AS (
    SELECT
        y.calendar_year,
        COUNT(*) FILTER (
            WHERE c.registration_year = y.calendar_year
        ) AS new_customers,
        COUNT(*) FILTER (
            WHERE c.closing_year = y.calendar_year
        ) AS closed_customers
    FROM years AS y
    CROSS JOIN core.customers AS c
    GROUP BY y.calendar_year
)
SELECT
    calendar_year,

    -- KPI-16 | New Customers | Tier A | Tool: Power BI
    new_customers,

    closed_customers,

    -- KPI-17 | Net Customer Growth | Tier A | Tool: Power BI
    new_customers - closed_customers AS net_customer_growth

FROM customer_flows
ORDER BY calendar_year;


-- ============================================================
-- 02. ACTIVE ACCOUNTS AND NET ACCOUNT GROWTH BY YEAR
-- ============================================================
-- An account is considered active at year-end when it has opened by
-- that year and has not closed before or during that year.

WITH bounds AS (
    SELECT
        MIN(opening_year)::INT AS first_year,
        MAX(
            GREATEST(
                opening_year,
                COALESCE(closing_year, opening_year)
            )
        )::INT AS last_year
    FROM core.accounts
),
years AS (
    SELECT GENERATE_SERIES(first_year, last_year) AS calendar_year
    FROM bounds
)
SELECT
    y.calendar_year,

    -- KPI-21 | Active Accounts | Tier B | Tool: Power BI
    COUNT(*) FILTER (
        WHERE a.opening_year <= y.calendar_year
          AND (a.closing_year IS NULL OR a.closing_year > y.calendar_year)
    ) AS active_accounts,

    COUNT(*) FILTER (
        WHERE a.opening_year = y.calendar_year
    ) AS accounts_opened,

    COUNT(*) FILTER (
        WHERE a.closing_year = y.calendar_year
    ) AS accounts_closed,

    -- KPI-22 | Net Account Growth | Tier B | Tool: Power BI
    COUNT(*) FILTER (
        WHERE a.opening_year = y.calendar_year
    )
    -
    COUNT(*) FILTER (
        WHERE a.closing_year = y.calendar_year
    ) AS net_account_growth

FROM years AS y
CROSS JOIN core.accounts AS a
GROUP BY y.calendar_year
ORDER BY y.calendar_year;


-- ============================================================
-- 03. ACTIVE ACCOUNTS PER ACTIVE CUSTOMER — CURRENT SNAPSHOT
-- ============================================================
-- Use explicit ACTIVE statuses for the present relationship snapshot.

WITH active_customers AS (
    SELECT customer_id
    FROM core.customers
    WHERE customer_status = 'ACTIVE'
),
active_accounts AS (
    SELECT account_id, customer_id
    FROM core.accounts
    WHERE account_status = 'ACTIVE'
),
summary AS (
    SELECT
        (SELECT COUNT(*) FROM active_customers) AS active_customers,
        (SELECT COUNT(*) FROM active_accounts) AS active_accounts
)
SELECT
    active_customers,
    active_accounts,

    -- KPI-18 | Active Accounts per Customer | Tier C | Tool: Excel
    ROUND(
        active_accounts::NUMERIC
        / NULLIF(active_customers, 0),
        4
    ) AS active_accounts_per_customer

FROM summary;


-- ============================================================
-- 04. ACTIVE CARD PENETRATION — CURRENT SNAPSHOT
-- ============================================================
-- Numerator: active customers with at least one active card.
-- Denominator: all active customers.

WITH active_customers AS (
    SELECT customer_id
    FROM core.customers
    WHERE customer_status = 'ACTIVE'
),
active_card_customers AS (
    SELECT DISTINCT c.customer_id
    FROM banking.cards AS c
    INNER JOIN active_customers AS ac
        ON ac.customer_id = c.customer_id
    WHERE c.card_status = 'ACTIVE'
)
SELECT
    (SELECT COUNT(*) FROM active_customers) AS active_customers,
    (SELECT COUNT(*) FROM active_card_customers)
        AS active_customers_with_active_card,

    -- KPI-19 | Active Card Penetration | Tier B | Tool: Power BI
    ROUND(
        100.0 * (SELECT COUNT(*) FROM active_card_customers)
        / NULLIF((SELECT COUNT(*) FROM active_customers), 0),
        2
    ) AS active_card_penetration_pct;


-- ============================================================
-- 05. AVERAGE CUSTOMER TENURE — CURRENT ANALYTICAL CUTOFF
-- ============================================================
-- The analytical cutoff is derived from the latest bank-performance
-- observation rather than the computer's current date.

WITH cutoff AS (
    SELECT MAX(EXTRACT(YEAR FROM year_month))::INT AS as_of_year
    FROM performance.bank_monthly_performance
)
SELECT
    c.customer_type,
    cutoff.as_of_year,
    COUNT(*) AS active_customers,

    -- KPI-20 | Average Customer Tenure | Tier C | Tool: Python
    ROUND(
        AVG(cutoff.as_of_year - c.registration_year)::NUMERIC,
        2
    ) AS average_customer_tenure_years

FROM core.customers AS c
CROSS JOIN cutoff
WHERE c.customer_status = 'ACTIVE'
  AND c.registration_year IS NOT NULL
GROUP BY c.customer_type, cutoff.as_of_year
ORDER BY c.customer_type;


-- ============================================================
-- 06. MONTHLY NET ACCOUNT FLOW
-- ============================================================
-- Account flows are additive within month.
-- Currency is recovered through account -> product and kept separate.

SELECT
    DATE_TRUNC('month', ab.year_month)::DATE AS report_month,
    p.currency,
    ROUND(SUM(ab.total_inflows)::NUMERIC, 2) AS total_inflows,
    ROUND(SUM(ab.total_outflows)::NUMERIC, 2) AS total_outflows,

    -- KPI-23 | Net Account Flow | Tier B | Tool: Excel
    ROUND(
        (SUM(ab.total_inflows) - SUM(ab.total_outflows))::NUMERIC,
        2
    ) AS net_account_flow

FROM banking.account_balances AS ab
INNER JOIN core.accounts AS a
    ON a.account_id = ab.account_id
INNER JOIN core.products AS p
    ON p.product_id = a.product_id
GROUP BY DATE_TRUNC('month', ab.year_month), p.currency
ORDER BY report_month, p.currency;


-- ============================================================
-- 07. AVERAGE BALANCE PER ACCOUNT
-- ============================================================
-- Closing balances are not mixed across currencies.
-- This is a drill-down account measure, not a substitute for the
-- UYU-equivalent bank-level Average Deposits KPI.

SELECT
    DATE_TRUNC('month', ab.year_month)::DATE AS report_month,
    p.currency,
    COUNT(DISTINCT ab.account_id) AS accounts_with_balance,

    -- KPI-24 | Average Balance per Account | Tier C | Tool: Excel
    ROUND(
        AVG(ab.closing_balance)::NUMERIC,
        2
    ) AS average_balance_per_account

FROM banking.account_balances AS ab
INNER JOIN core.accounts AS a
    ON a.account_id = ab.account_id
INNER JOIN core.products AS p
    ON p.product_id = a.product_id
GROUP BY DATE_TRUNC('month', ab.year_month), p.currency
ORDER BY report_month, p.currency;


-- ============================================================
-- 08. PRODUCT TARGET ALIGNMENT RATE
-- ============================================================
-- Denominator includes only relationships whose product has an
-- explicit target customer type.

WITH eligible_relationships AS (
    SELECT
        a.account_id,
        c.customer_type,
        p.product_family,
        p.product_name,
        p.target_customer_type,
        (c.customer_type = p.target_customer_type) AS is_aligned
    FROM core.accounts AS a
    INNER JOIN core.customers AS c
        ON c.customer_id = a.customer_id
    INNER JOIN core.products AS p
        ON p.product_id = a.product_id
    WHERE p.target_customer_type IS NOT NULL
)
SELECT
    product_family,
    COUNT(*) AS eligible_relationships,
    COUNT(*) FILTER (WHERE is_aligned) AS aligned_relationships,

    -- KPI-26 | Product Target Alignment Rate | Tier D | Tool: Excel
    ROUND(
        100.0 * COUNT(*) FILTER (WHERE is_aligned)
        / NULLIF(COUNT(*), 0),
        2
    ) AS product_target_alignment_rate_pct

FROM eligible_relationships
GROUP BY product_family
ORDER BY product_family;


-- ============================================================
-- 09. ACCOUNT OPENING CHANNEL SHARE
-- ============================================================
-- Shares are recomputed within each opening year.

WITH channel_counts AS (
    SELECT
        opening_year::INT AS calendar_year,
        opening_channel,
        COUNT(*) AS accounts_opened
    FROM core.accounts
    WHERE opening_year IS NOT NULL
      AND opening_channel IS NOT NULL
    GROUP BY opening_year, opening_channel
)
SELECT
    calendar_year,
    opening_channel,
    accounts_opened,

    -- KPI-27 | Opening Channel Share | Tier C | Tool: Superset
    ROUND(
        100.0 * accounts_opened
        / NULLIF(SUM(accounts_opened) OVER (
            PARTITION BY calendar_year
        ), 0),
        2
    ) AS opening_channel_share_pct

FROM channel_counts
ORDER BY calendar_year, accounts_opened DESC, opening_channel;


-- ============================================================
-- 10. BANK RELATIONSHIP VALUE PER ACTIVE CUSTOMER
-- ============================================================
-- These measures use the UYU-equivalent bank performance layer.

SELECT
    year_month,
    active_customers,
    ROUND(average_deposits::NUMERIC, 2) AS average_deposits,
    ROUND(average_loan_balance::NUMERIC, 2) AS average_loan_balance,

    -- KPI-50 | Deposits per Active Customer | Tier C | Tool: Excel
    ROUND(
        (average_deposits
        / NULLIF(active_customers, 0))::NUMERIC,
        2
    ) AS deposits_per_active_customer,

    -- KPI-51 | Loan Balance per Active Customer | Tier C | Tool: Excel
    ROUND(
        (average_loan_balance
        / NULLIF(active_customers, 0))::NUMERIC,
        2
    ) AS loan_balance_per_active_customer

FROM performance.bank_monthly_performance
ORDER BY year_month;


-- ============================================================
-- INTERPRETATION
-- ============================================================
-- New Customers and Net Customer Growth are lifecycle-flow measures.
-- Active Accounts and Active Accounts per Customer describe stock and
-- relationship depth.
--
-- Active Card Penetration is a relationship-adoption measure; it does
-- not imply card usage.
--
-- Product Target Alignment Rate is diagnostic (Tier D). It tests whether
-- account relationships match the modeled product target, not whether a
-- customer is profitable or commercially desirable.
--
-- Account flow and balance analysis must preserve currency separation.
-- Bank-level deposits and loans come from the UYU-equivalent performance
-- layer and therefore support per-customer comparison across time.
-- ============================================================

-- ============================================================
-- KPI OWNERSHIP MAP — FREEZE VERSION
-- ============================================================
-- Tier = portfolio / decision priority; Tool = primary delivery home.
-- PostgreSQL remains the calculation layer for every KPI in this file.
--
-- TIER S
--   Power BI: KPI-01 Active Customers
--
-- TIER A
--   Power BI: KPI-16 New Customers, KPI-17 Net Customer Growth
--
-- TIER B
--   Excel: KPI-23 Net Account Flow
--   Power BI: KPI-19 Active Card Penetration, KPI-21 Active Accounts, KPI-22 Net Account Growth
--
-- TIER C
--   Excel: KPI-18 Active Accounts per Customer, KPI-24 Average Balance per Account, KPI-50 Deposits per Active Customer, KPI-51 Loan Balance per Active Customer
--   Python: KPI-20 Average Customer Tenure
--   Superset: KPI-27 Opening Channel Share
--
-- TIER D
--   Excel: KPI-26 Product Target Alignment Rate
-- ============================================================
