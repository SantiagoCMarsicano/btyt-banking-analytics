-- ============================================================
-- BTYT BANKING ANALYTICS
-- 04_customer_account_summary.sql
-- Customer-level relationship summary for BI consumption.
--
-- Grain:
-- one customer
--
-- Sources:
-- core.customers
-- core.accounts
-- core.products
-- banking.cards
--
-- Notes:
-- - The view summarizes customer relationship depth without exposing
--   document identifiers.
-- - Customer master attributes are cutoff attributes unless explicitly
--   documented otherwise.
-- - Account and card counts are based on current master status.
-- - Product counts are derived from account relationships.
-- - Dynamic ratios and time intelligence are intentionally left for
--   downstream BI / DAX where appropriate.
-- ============================================================

DROP VIEW IF EXISTS analytics.customer_account_summary;

CREATE VIEW analytics.customer_account_summary AS

WITH account_summary AS (
    SELECT
        a.customer_id,

        COUNT(*) AS total_accounts,

        COUNT(*) FILTER (
            WHERE a.account_status = 'ACTIVE'
        ) AS active_accounts,

        COUNT(*) FILTER (
            WHERE a.account_status <> 'ACTIVE'
        ) AS non_active_accounts,

        COUNT(DISTINCT a.product_id) AS distinct_account_products,

        COUNT(DISTINCT p.product_family) AS distinct_product_families,

        COUNT(DISTINCT p.currency) AS account_currencies,

        MIN(a.opening_year) AS first_account_opening_year,
        MAX(a.opening_year) AS latest_account_opening_year,

        COUNT(*) FILTER (
            WHERE p.target_customer_type IS NOT NULL
              AND p.target_customer_type = c.customer_type
        ) AS target_aligned_accounts,

        COUNT(*) FILTER (
            WHERE p.target_customer_type IS NOT NULL
        ) AS target_eligible_accounts

    FROM core.accounts AS a
    INNER JOIN core.customers AS c
        ON c.customer_id = a.customer_id
    LEFT JOIN core.products AS p
        ON p.product_id = a.product_id

    GROUP BY a.customer_id
),

card_summary AS (
    SELECT
        customer_id,

        COUNT(*) AS total_cards,

        COUNT(*) FILTER (
            WHERE card_status = 'ACTIVE'
        ) AS active_cards,

        COUNT(*) FILTER (
            WHERE card_status <> 'ACTIVE'
        ) AS non_active_cards,

        MIN(issue_year) AS first_card_issue_year,
        MAX(issue_year) AS latest_card_issue_year

    FROM banking.cards
    GROUP BY customer_id
)

SELECT
    c.customer_id,

    -- Customer dimensions
    c.customer_type,
    c.nationality,
    c.birth_year,
    c.gender,
    c.residence_country,
    c.residence_department,
    c.residence_locality,
    c.primary_branch_id,
    c.registration_year,
    c.customer_status,
    c.closing_year,
    c.employment_status,
    c.monthly_income,
    c.business_sector,
    c.company_size,
    c.foundation_year,
    c.annual_revenue,

    -- Account relationship summary
    COALESCE(a.total_accounts, 0) AS total_accounts,
    COALESCE(a.active_accounts, 0) AS active_accounts,
    COALESCE(a.non_active_accounts, 0) AS non_active_accounts,
    COALESCE(a.distinct_account_products, 0) AS distinct_account_products,
    COALESCE(a.distinct_product_families, 0) AS distinct_product_families,
    COALESCE(a.account_currencies, 0) AS account_currencies,
    a.first_account_opening_year,
    a.latest_account_opening_year,

    -- Product-target alignment support
    COALESCE(a.target_aligned_accounts, 0) AS target_aligned_accounts,
    COALESCE(a.target_eligible_accounts, 0) AS target_eligible_accounts,

    -- Card relationship summary
    COALESCE(cd.total_cards, 0) AS total_cards,
    COALESCE(cd.active_cards, 0) AS active_cards,
    COALESCE(cd.non_active_cards, 0) AS non_active_cards,
    cd.first_card_issue_year,
    cd.latest_card_issue_year,

    -- Reusable analytical flags
    CASE
        WHEN COALESCE(a.active_accounts, 0) > 0 THEN 1
        ELSE 0
    END AS has_active_account,

    CASE
        WHEN COALESCE(cd.active_cards, 0) > 0 THEN 1
        ELSE 0
    END AS has_active_card

FROM core.customers AS c
LEFT JOIN account_summary AS a
    ON a.customer_id = c.customer_id
LEFT JOIN card_summary AS cd
    ON cd.customer_id = c.customer_id;


-- Validation
SELECT
    COUNT(*) AS total_rows,
    COUNT(DISTINCT customer_id) AS distinct_customers,
    COUNT(*) FILTER (
        WHERE has_active_account = 1
    ) AS customers_with_active_account,
    COUNT(*) FILTER (
        WHERE has_active_card = 1
    ) AS customers_with_active_card
FROM analytics.customer_account_summary;
