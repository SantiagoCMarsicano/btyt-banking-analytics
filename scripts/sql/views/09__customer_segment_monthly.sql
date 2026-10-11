-- ============================================================
-- BTYT BANKING ANALYTICS
-- 08_customer_segment_monthly.sql
--
-- Grain:
-- one observation per year_month + customer_type
--
-- Monetary values:
-- UYU-equivalent
-- ============================================================

DROP VIEW IF EXISTS analytics.customer_segment_monthly;

CREATE VIEW analytics.customer_segment_monthly AS

WITH deposit_metrics AS (

    SELECT
        ab.year_month,
        c.customer_type,

        COUNT(DISTINCT a.customer_id) AS active_customers,
        COUNT(DISTINCT a.account_id) AS active_accounts,

        CAST(
            SUM(
                (
                    (ab.opening_balance + ab.closing_balance) / 2.0
                )
                *
                CASE
                    WHEN UPPER(p.currency) = 'USD' THEN
                        CASE EXTRACT(YEAR FROM ab.year_month)::integer
                            WHEN 2021 THEN 43.6
                            WHEN 2022 THEN 41.2
                            WHEN 2023 THEN 38.8
                            WHEN 2024 THEN 40.3
                            WHEN 2025 THEN 42.0
                            WHEN 2026 THEN 43.5
                        END
                    ELSE 1.0
                END
            )
            AS numeric(20,2)
        ) AS average_deposits

    FROM banking.account_balances AS ab

    INNER JOIN core.accounts AS a
        ON a.account_id = ab.account_id

    INNER JOIN core.customers AS c
        ON c.customer_id = a.customer_id

    INNER JOIN core.products AS p
        ON p.product_id = a.product_id

    GROUP BY
        ab.year_month,
        c.customer_type
),

loan_metrics AS (

    SELECT
        ls.year_month,
        c.customer_type,

        COUNT(DISTINCT l.loan_id) AS active_loans,

        CAST(
            SUM(
                ls.outstanding_balance
                *
                CASE
                    WHEN UPPER(l.currency) = 'USD' THEN
                        CASE EXTRACT(YEAR FROM ls.year_month)::integer
                            WHEN 2021 THEN 43.6
                            WHEN 2022 THEN 41.2
                            WHEN 2023 THEN 38.8
                            WHEN 2024 THEN 40.3
                            WHEN 2025 THEN 42.0
                            WHEN 2026 THEN 43.5
                        END
                    ELSE 1.0
                END
            )
            AS numeric(20,2)
        ) AS average_loan_balance

    FROM banking.loan_monthly_snapshot AS ls

    INNER JOIN banking.loans AS l
        ON l.loan_id = ls.loan_id

    INNER JOIN core.customers AS c
        ON c.customer_id = l.customer_id

    GROUP BY
        ls.year_month,
        c.customer_type
)

SELECT
    COALESCE(d.year_month, l.year_month) AS year_month,
    COALESCE(d.customer_type, l.customer_type) AS customer_type,

    COALESCE(d.active_customers, 0) AS active_customers,
    COALESCE(d.active_accounts, 0) AS active_accounts,
    COALESCE(l.active_loans, 0) AS active_loans,

    CAST(
        COALESCE(d.average_deposits, 0)
        AS numeric(20,2)
    ) AS average_deposits,

    CAST(
        COALESCE(l.average_loan_balance, 0)
        AS numeric(20,2)
    ) AS average_loan_balance

FROM deposit_metrics AS d

FULL OUTER JOIN loan_metrics AS l
    ON d.year_month = l.year_month
   AND d.customer_type = l.customer_type;