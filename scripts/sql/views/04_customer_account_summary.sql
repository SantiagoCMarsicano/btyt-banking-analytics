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

CREATE OR REPLACE VIEW analytics.customer_account_summary AS

WITH account_summary AS (
    SELECT
        a_1.customer_id,
        COUNT(*) AS total_accounts,
        COUNT(*) FILTER (
            WHERE a_1.account_status = 'ACTIVE'
        ) AS active_accounts,
        COUNT(*) FILTER (
            WHERE a_1.account_status <> 'ACTIVE'
        ) AS non_active_accounts,
        COUNT(DISTINCT a_1.product_id) AS distinct_account_products,
        COUNT(DISTINCT p.product_family) AS distinct_product_families,
        COUNT(DISTINCT p.currency) AS account_currencies,
        MIN(a_1.opening_year) AS first_account_opening_year,
        MAX(a_1.opening_year) AS latest_account_opening_year,
        COUNT(*) FILTER (
            WHERE p.target_customer_type IS NOT NULL
              AND p.target_customer_type = c_1.customer_type
        ) AS target_aligned_accounts,
        COUNT(*) FILTER (
            WHERE p.target_customer_type IS NOT NULL
        ) AS target_eligible_accounts

    FROM core.accounts a_1

    JOIN core.customers c_1
        ON c_1.customer_id = a_1.customer_id

    LEFT JOIN core.products p
        ON p.product_id = a_1.product_id

    GROUP BY
        a_1.customer_id
),

card_summary AS (
    SELECT
        cards.customer_id,
        COUNT(*) AS total_cards,
        COUNT(*) FILTER (
            WHERE cards.card_status = 'ACTIVE'
        ) AS active_cards,
        COUNT(*) FILTER (
            WHERE cards.card_status <> 'ACTIVE'
        ) AS non_active_cards,
        MIN(cards.issue_year) AS first_card_issue_year,
        MAX(cards.issue_year) AS latest_card_issue_year

    FROM banking.cards

    GROUP BY
        cards.customer_id
),

account_activity_span AS (
    SELECT
        a.customer_id,
        ab.account_id,
        MIN(ab.year_month) AS first_month,
        MAX(ab.year_month) AS last_month

    FROM banking.account_balances ab

    JOIN core.accounts a
        ON a.account_id = ab.account_id

    GROUP BY
        a.customer_id,
        ab.account_id
),

activity_bounds AS (
    SELECT
        MAX(year_month) AS end_month

    FROM banking.account_balances
),

account_window_summary AS (
    SELECT
        s.customer_id,

        COUNT(*) FILTER (
            WHERE s.first_month <= b.end_month
              AND s.last_month >= b.end_month
        ) AS active_accounts_1m,

        COUNT(*) FILTER (
            WHERE s.first_month <= b.end_month
              AND s.last_month >= b.end_month - INTERVAL '2 months'
        ) AS active_accounts_3m,

        COUNT(*) FILTER (
            WHERE s.first_month <= b.end_month
              AND s.last_month >= b.end_month - INTERVAL '5 months'
        ) AS active_accounts_6m,

        COUNT(*) FILTER (
            WHERE s.first_month <= b.end_month
              AND s.last_month >= b.end_month - INTERVAL '11 months'
        ) AS active_accounts_12m,

        COUNT(*) AS active_accounts_all

    FROM account_activity_span s

    CROSS JOIN activity_bounds b

    GROUP BY
        s.customer_id
)

SELECT
    c.customer_id,
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

    COALESCE(a.total_accounts, 0) AS total_accounts,
    COALESCE(a.active_accounts, 0) AS active_accounts,
    COALESCE(a.non_active_accounts, 0) AS non_active_accounts,
    COALESCE(a.distinct_account_products, 0) AS distinct_account_products,
    COALESCE(a.distinct_product_families, 0) AS distinct_product_families,
    COALESCE(a.account_currencies, 0) AS account_currencies,

    a.first_account_opening_year,
    a.latest_account_opening_year,

    COALESCE(a.target_aligned_accounts, 0) AS target_aligned_accounts,
    COALESCE(a.target_eligible_accounts, 0) AS target_eligible_accounts,

    COALESCE(cd.total_cards, 0) AS total_cards,
    COALESCE(cd.active_cards, 0) AS active_cards,
    COALESCE(cd.non_active_cards, 0) AS non_active_cards,

    cd.first_card_issue_year,
    cd.latest_card_issue_year,

    CASE
        WHEN COALESCE(a.active_accounts, 0) > 0 THEN 1
        ELSE 0
    END AS has_active_account,

    CASE
        WHEN COALESCE(cd.active_cards, 0) > 0 THEN 1
        ELSE 0
    END AS has_active_card,

    CASE
        WHEN c.customer_type = 'BUSINESS'
            THEN COALESCE(
                NULLIF(TRIM(c.company_name), ''),
                c.customer_id
            )
        ELSE COALESCE(
            NULLIF(
                TRIM(CONCAT_WS(' ', c.first_name, c.last_name)),
                ''
            ),
            c.customer_id
        )
    END AS customer_name,

    (
        CASE
            WHEN c.customer_type = 'BUSINESS'
                THEN COALESCE(
                    NULLIF(TRIM(c.company_name), ''),
                    c.customer_id
                )
            ELSE COALESCE(
                NULLIF(
                    TRIM(CONCAT_WS(' ', c.first_name, c.last_name)),
                    ''
                ),
                c.customer_id
            )
        END
        || ' · '
        || c.customer_id
    ) AS customer_label,

    COALESCE(aws.active_accounts_1m, 0) AS active_accounts_1m,
    COALESCE(aws.active_accounts_3m, 0) AS active_accounts_3m,
    COALESCE(aws.active_accounts_6m, 0) AS active_accounts_6m,
    COALESCE(aws.active_accounts_12m, 0) AS active_accounts_12m,
    COALESCE(aws.active_accounts_all, 0) AS active_accounts_all

FROM core.customers c

LEFT JOIN account_summary a
    ON a.customer_id = c.customer_id

LEFT JOIN card_summary cd
    ON cd.customer_id = c.customer_id

LEFT JOIN account_window_summary aws
    ON aws.customer_id = c.customer_id;