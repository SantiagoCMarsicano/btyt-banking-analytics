DROP VIEW IF EXISTS analytics.customer_transaction_yearly;

DROP MATERIALIZED VIEW IF EXISTS
    analytics.customer_transaction_yearly_mv;


CREATE MATERIALIZED VIEW
analytics.customer_transaction_yearly_mv AS

SELECT
    EXTRACT(YEAR FROM t.transaction_datetime)::integer AS year,

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

    COUNT(*) AS transaction_count,

    CAST(
        SUM(
            t.amount
            *
            CASE
                WHEN UPPER(p.currency) = 'USD' THEN
                    CASE EXTRACT(YEAR FROM t.transaction_datetime)::integer
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
    ) AS transaction_volume_uyu

FROM banking.transactions AS t

INNER JOIN core.accounts AS a
    ON a.account_id = t.account_id

INNER JOIN core.customers AS c
    ON c.customer_id = a.customer_id

INNER JOIN core.products AS p
    ON p.product_id = a.product_id

WHERE
    UPPER(t.transaction_status) = 'COMPLETED'

    AND t.transaction_datetime >= TIMESTAMP '2021-01-01'
    AND t.transaction_datetime < TIMESTAMP '2027-01-01'

GROUP BY
    EXTRACT(YEAR FROM t.transaction_datetime)::integer,
    c.customer_id,
    c.customer_type,
    c.company_name,
    c.first_name,
    c.last_name;


CREATE UNIQUE INDEX
    ux_customer_transaction_yearly_mv
ON analytics.customer_transaction_yearly_mv
    (year, customer_id);


CREATE INDEX
    ix_customer_transaction_yearly_type
ON analytics.customer_transaction_yearly_mv
    (customer_type, year);


CREATE VIEW analytics.customer_transaction_yearly AS

SELECT
    year,
    customer_id,
    customer_type,
    customer_name,
    customer_label,
    transaction_count,
    transaction_volume_uyu

FROM analytics.customer_transaction_yearly_mv;