-- ============================================================
-- BTYT BANKING ANALYTICS
-- 10_customer_debt_monthly_materialized.sql
--
-- Purpose:
-- Customer-level monthly outstanding debt for BI.
--
-- Grain:
-- one row per year_month + customer_id
--
-- Monetary values:
-- UYU-equivalent
-- ============================================================


DROP VIEW IF EXISTS analytics.customer_debt_monthly;

DROP MATERIALIZED VIEW IF EXISTS
    analytics.customer_debt_monthly_mv;


CREATE MATERIALIZED VIEW
analytics.customer_debt_monthly_mv AS

SELECT
    ls.year_month,

    c.customer_id,
    c.customer_type,

    CASE
        WHEN c.customer_type = 'BUSINESS'
            THEN COALESCE(c.company_name, c.customer_id)

        ELSE
            COALESCE(
                NULLIF(
                    TRIM(
                        CONCAT_WS(
                            ' ',
                            c.first_name,
                            c.last_name
                        )
                    ),
                    ''
                ),
                c.customer_id
            )
    END AS customer_name,

    CASE
        WHEN c.customer_type = 'BUSINESS'
            THEN COALESCE(c.company_name, c.customer_id)
                 || ' · ' || c.customer_id

        ELSE
            COALESCE(
                NULLIF(
                    TRIM(
                        CONCAT_WS(
                            ' ',
                            c.first_name,
                            c.last_name
                        )
                    ),
                    ''
                ),
                c.customer_id
            )
            || ' · ' || c.customer_id
    END AS customer_label,

    COUNT(DISTINCT l.loan_id) AS active_loan_count,

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
    ) AS outstanding_balance_uyu,

    CAST(
        SUM(
            ls.arrears_amount
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
    ) AS arrears_amount_uyu

FROM banking.loan_monthly_snapshot AS ls

INNER JOIN banking.loans AS l
    ON l.loan_id = ls.loan_id

INNER JOIN core.customers AS c
    ON c.customer_id = l.customer_id

WHERE
    ls.outstanding_balance > 0

GROUP BY
    ls.year_month,
    c.customer_id,
    c.customer_type,
    c.company_name,
    c.first_name,
    c.last_name;


-- ------------------------------------------------------------
-- Indexes
-- ------------------------------------------------------------

CREATE UNIQUE INDEX
    ux_customer_debt_monthly_mv
ON analytics.customer_debt_monthly_mv
    (year_month, customer_id);


CREATE INDEX
    ix_customer_debt_monthly_type
ON analytics.customer_debt_monthly_mv
    (customer_type, year_month);


-- ------------------------------------------------------------
-- Stable BI-facing view
-- ------------------------------------------------------------

CREATE VIEW analytics.customer_debt_monthly AS

SELECT
    year_month,
    customer_id,
    customer_type,
    customer_name,
    customer_label,
    active_loan_count,
    outstanding_balance_uyu,
    arrears_amount_uyu

FROM analytics.customer_debt_monthly_mv;


-- ------------------------------------------------------------
-- Technical validation
-- ------------------------------------------------------------

SELECT
    COUNT(*) AS total_rows,
    COUNT(DISTINCT customer_id) AS customers,
    MIN(year_month) AS first_month,
    MAX(year_month) AS last_month

FROM analytics.customer_debt_monthly;