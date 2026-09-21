-- ============================================================
-- BTYT BANKING ANALYTICS
-- 07_transactions_campaigns_and_market.sql
-- Digital activity, campaign response and synthetic market position
-- ============================================================
--
-- Measurement rules:
-- - Attempted transactions include COMPLETED and FAILED.
-- - Realized count and value include only COMPLETED transactions.
-- - Digital means MOBILE + WEB, exactly as defined in the KPI catalog.
-- - Transaction value is kept separate by account/product currency.
-- - External transfers are DOMESTIC_EXTERNAL or INTERNATIONAL.
-- - Campaign POSITIVE response is receptivity, not product conversion.
-- - Market weight is a synthetic competitive measure, not profitability.
-- - BTYT bank_id is B000.
-- ============================================================


-- ============================================================
-- 00. VALIDATE TRANSACTION DOMAINS
-- ============================================================

SELECT
    transaction_status,
    channel,
    transfer_scope,
    COUNT(*) AS transactions
FROM banking.transactions
GROUP BY transaction_status, channel, transfer_scope
ORDER BY transaction_status, channel, transfer_scope;


-- ============================================================
-- 01. MONTHLY TRANSACTION COUNTS AND DIGITAL SHARE
-- ============================================================
-- Counts can be aggregated across currencies because the unit is an
-- operation rather than a monetary amount.

SELECT
    DATE_TRUNC('month', transaction_datetime)::DATE AS report_month,

    COUNT(*) AS attempted_transactions,

    -- KPI-33 | Completed Transaction Count | Tier B | Tool: Superset
    COUNT(*) FILTER (
        WHERE transaction_status = 'COMPLETED'
    ) AS completed_transaction_count,

    COUNT(*) FILTER (
        WHERE transaction_status = 'FAILED'
    ) AS failed_transaction_count,

    -- KPI-14 | Transaction Failure Rate | Tier B | Tool: Superset
    ROUND(
        100.0 * COUNT(*) FILTER (
            WHERE transaction_status = 'FAILED'
        )
        / NULLIF(COUNT(*), 0),
        2
    ) AS transaction_failure_rate_pct,

    COUNT(*) FILTER (
        WHERE transaction_status = 'COMPLETED'
          AND channel IN ('MOBILE', 'WEB')
    ) AS completed_digital_transactions,

    -- KPI-13 | Digital Transaction Share - Count | Tier B | Tool: Superset
    ROUND(
        100.0 * COUNT(*) FILTER (
            WHERE transaction_status = 'COMPLETED'
              AND channel IN ('MOBILE', 'WEB')
        )
        / NULLIF(
            COUNT(*) FILTER (
                WHERE transaction_status = 'COMPLETED'
            ),
            0
        ),
        2
    ) AS digital_transaction_share_count_pct

FROM banking.transactions
GROUP BY DATE_TRUNC('month', transaction_datetime)
ORDER BY report_month;


-- ============================================================
-- 02. MONTHLY COMPLETED VOLUME AND DIGITAL VALUE SHARE
-- ============================================================
-- Monetary amounts remain separated by currency.
-- Currency is recovered through transaction account -> product.

SELECT
    DATE_TRUNC('month', t.transaction_datetime)::DATE AS report_month,
    p.currency,

    -- KPI-34 | Completed Transaction Volume | Tier B | Tool: Superset
    ROUND(
        SUM(t.amount) FILTER (
            WHERE t.transaction_status = 'COMPLETED'
        )::NUMERIC,
        2
    ) AS completed_transaction_volume,

    ROUND(
        SUM(t.amount) FILTER (
            WHERE t.transaction_status = 'COMPLETED'
              AND t.channel IN ('MOBILE', 'WEB')
        )::NUMERIC,
        2
    ) AS completed_digital_transaction_volume,

    -- KPI-35 | Digital Transaction Share - Value | Tier C | Tool: Superset
    ROUND(
        100.0
        * SUM(t.amount) FILTER (
            WHERE t.transaction_status = 'COMPLETED'
              AND t.channel IN ('MOBILE', 'WEB')
        )
        / NULLIF(
            SUM(t.amount) FILTER (
                WHERE t.transaction_status = 'COMPLETED'
            ),
            0
        ),
        2
    ) AS digital_transaction_share_value_pct

FROM banking.transactions AS t
INNER JOIN core.accounts AS a
    ON a.account_id = t.account_id
INNER JOIN core.products AS p
    ON p.product_id = a.product_id
GROUP BY DATE_TRUNC('month', t.transaction_datetime), p.currency
ORDER BY report_month, p.currency;


-- ============================================================
-- 03. EXTERNAL TRANSFER SHARE
-- ============================================================
-- Denominator: completed transfers with any valid transfer scope.
-- Numerator: completed DOMESTIC_EXTERNAL + INTERNATIONAL transfers.

SELECT
    DATE_TRUNC('month', transaction_datetime)::DATE AS report_month,

    COUNT(*) FILTER (
        WHERE transaction_status = 'COMPLETED'
          AND transaction_type IN ('TRANSFER_IN', 'TRANSFER_OUT')
          AND transfer_scope IN (
              'INTERNAL',
              'DOMESTIC_EXTERNAL',
              'INTERNATIONAL'
          )
    ) AS completed_transfers,

    COUNT(*) FILTER (
        WHERE transaction_status = 'COMPLETED'
          AND transaction_type IN ('TRANSFER_IN', 'TRANSFER_OUT')
          AND transfer_scope IN (
              'DOMESTIC_EXTERNAL',
              'INTERNATIONAL'
          )
    ) AS completed_external_transfers,

    -- KPI-36 | External Transfer Share | Tier C | Tool: Superset
    ROUND(
        100.0 * COUNT(*) FILTER (
            WHERE transaction_status = 'COMPLETED'
              AND transaction_type IN ('TRANSFER_IN', 'TRANSFER_OUT')
              AND transfer_scope IN (
                  'DOMESTIC_EXTERNAL',
                  'INTERNATIONAL'
              )
        )
        / NULLIF(
            COUNT(*) FILTER (
                WHERE transaction_status = 'COMPLETED'
                  AND transaction_type IN ('TRANSFER_IN', 'TRANSFER_OUT')
                  AND transfer_scope IN (
                      'INTERNAL',
                      'DOMESTIC_EXTERNAL',
                      'INTERNATIONAL'
                  )
            ),
            0
        ),
        2
    ) AS external_transfer_share_pct

FROM banking.transactions
GROUP BY DATE_TRUNC('month', transaction_datetime)
ORDER BY report_month;


-- ============================================================
-- 04. CAMPAIGN EXPOSURE AND POSITIVE RESPONSE
-- ============================================================
-- Selected customers come from campaign_customers.
-- Exposure is confirmed by an event in campaign_exposures.
-- Positive response is read from campaign_customers.response_status.

WITH selected AS (
    SELECT
        cc.campaign_id,
        COUNT(DISTINCT cc.customer_id) AS selected_customers
    FROM marketing.campaign_customers AS cc
    GROUP BY cc.campaign_id
),
exposed AS (
    SELECT
        ce.campaign_id,
        COUNT(DISTINCT ce.customer_id) AS exposed_customers
    FROM marketing.campaign_exposures AS ce
    GROUP BY ce.campaign_id
),
positive AS (
    SELECT
        cc.campaign_id,
        COUNT(DISTINCT cc.customer_id) AS positive_responders
    FROM marketing.campaign_customers AS cc
    WHERE cc.response_status = 'POSITIVE'
      AND EXISTS (
          SELECT 1
          FROM marketing.campaign_exposures AS ce
          WHERE ce.campaign_id = cc.campaign_id
            AND ce.customer_id = cc.customer_id
      )
    GROUP BY cc.campaign_id
)
SELECT
    c.campaign_id,
    c.campaign_name,
    c.campaign_type,
    c.start_date,
    c.end_date,

    COALESCE(s.selected_customers, 0) AS selected_customers,
    COALESCE(e.exposed_customers, 0) AS exposed_customers,
    COALESCE(p.positive_responders, 0) AS positive_responders,

    -- KPI-43 | Campaign Exposure Rate | Tier C | Tool: Tableau
    ROUND(
        100.0 * COALESCE(e.exposed_customers, 0)
        / NULLIF(s.selected_customers, 0),
        2
    ) AS campaign_exposure_rate_pct,

    -- KPI-44 | Positive Response Rate | Tier B | Tool: Tableau
    ROUND(
        100.0 * COALESCE(p.positive_responders, 0)
        / NULLIF(e.exposed_customers, 0),
        2
    ) AS positive_response_rate_pct

FROM marketing.campaigns AS c
LEFT JOIN selected AS s
    ON s.campaign_id = c.campaign_id
LEFT JOIN exposed AS e
    ON e.campaign_id = c.campaign_id
LEFT JOIN positive AS p
    ON p.campaign_id = c.campaign_id
ORDER BY c.start_date, c.campaign_id;


-- ============================================================
-- 05. SYNTHETIC MARKET WEIGHT — ALL BANKS
-- ============================================================
-- This is the competitive-market measure modeled by the generator.
-- It must not be interpreted as a profitability ranking.

SELECT
    bmw.year,
    bmw.bank_id,
    b.bank_name,
    b.bank_scope,
    b.bank_type,
    ROUND((100.0 * bmw.market_weight)::NUMERIC, 4)
        AS market_weight_pct,
    CASE WHEN bmw.bank_id = 'B000' THEN TRUE ELSE FALSE END AS is_btyt
FROM market.bank_market_weights AS bmw
LEFT JOIN market.banks AS b
    ON b.bank_id = bmw.bank_id
ORDER BY bmw.year, bmw.market_weight DESC, bmw.bank_id;


-- ============================================================
-- 06. BTYT MARKET WEIGHT AND YOY CHANGE
-- ============================================================

WITH btyt AS (
    SELECT
        year::INT AS calendar_year,
        market_weight::NUMERIC AS market_weight
    FROM market.bank_market_weights
    WHERE bank_id = 'B000'
)
SELECT
    cur.calendar_year,

    -- KPI-45 | BTYT Market Weight | Tier B | Tool: Power BI
    ROUND(100.0 * cur.market_weight, 4) AS btyt_market_weight_pct,

    ROUND(100.0 * prev.market_weight, 4)
        AS prior_year_btyt_market_weight_pct,

    -- KPI-46 | Market Weight Change YoY | Tier B | Tool: Power BI
    -- Difference is expressed in percentage points, not percent growth.
    ROUND(
        100.0 * (cur.market_weight - prev.market_weight),
        4
    ) AS market_weight_change_yoy_pp

FROM btyt AS cur
LEFT JOIN btyt AS prev
    ON prev.calendar_year = cur.calendar_year - 1
ORDER BY cur.calendar_year;


-- ============================================================
-- 07. MARKET-WEIGHT RECONCILIATION
-- ============================================================
-- If market weights represent a full annual distribution, the annual
-- sum should be approximately 1.0 before percentage conversion.

SELECT
    year,
    COUNT(*) AS banks_observed,
    ROUND(SUM(market_weight)::NUMERIC, 8) AS market_weight_sum,
    ROUND((100.0 * SUM(market_weight))::NUMERIC, 4)
        AS market_weight_sum_pct
FROM market.bank_market_weights
GROUP BY year
ORDER BY year;


-- ============================================================
-- INTERPRETATION
-- ============================================================
-- Transaction Failure Rate uses attempts as denominator; completed
-- transaction KPIs use realized operations only.
--
-- Digital count share and digital value share answer different
-- questions. A channel can dominate transaction counts without
-- dominating monetary value.
--
-- External Transfer Share is a count-based share of completed
-- transfers. INTERNAL transfers remain inside BTYT; DOMESTIC_EXTERNAL
-- and INTERNATIONAL are external.
--
-- Campaign exposure measures delivery to the selected cohort.
-- Positive response measures observed receptivity among exposed
-- customers; it is not a purchase or product-conversion rate.
--
-- BTYT Market Weight is a synthetic market-position metric. It can be
-- compared across modeled banks and over time, but it does not by
-- itself establish peer profitability or financial performance.
-- ============================================================

-- ============================================================
-- KPI OWNERSHIP MAP — FREEZE VERSION
-- ============================================================
-- Tier = portfolio / decision priority; Tool = primary delivery home.
-- PostgreSQL remains the calculation layer for every KPI in this file.
--
-- TIER B
--   Power BI: KPI-45 BTYT Market Weight, KPI-46 Market Weight Change YoY
--   Superset: KPI-13 Digital Transaction Share - Count, KPI-14 Transaction Failure Rate, KPI-33 Completed Transaction Count, KPI-34 Completed Transaction Volume
--   Tableau: KPI-44 Positive Response Rate
--
-- TIER C
--   Superset: KPI-35 Digital Transaction Share - Value, KPI-36 External Transfer Share
--   Tableau: KPI-43 Campaign Exposure Rate
-- ============================================================
