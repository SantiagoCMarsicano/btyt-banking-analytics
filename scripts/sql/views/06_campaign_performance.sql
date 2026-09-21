-- ============================================================
-- BTYT BANKING ANALYTICS
-- 06_campaign_performance.sql
-- Campaign-level analytical view for BI consumption.
--
-- Grain:
-- one campaign
--
-- Sources:
-- marketing.campaigns
-- marketing.campaign_customers
-- marketing.campaign_exposures
--
-- Notes:
-- - Selected customers come from campaign_customers.
-- - Confirmed exposure is based on campaign_exposures event records.
-- - Positive response is based on campaign_customers.response_status.
-- - Positive responders are restricted to customers with a confirmed
--   exposure event for the same campaign.
-- - A POSITIVE response is not interpreted as a product conversion.
-- - Exposure and response rates are intentionally left for downstream
--   DAX so they react correctly to report filters.
-- ============================================================

DROP VIEW IF EXISTS analytics.campaign_performance;

CREATE VIEW analytics.campaign_performance AS

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
        COUNT(DISTINCT ce.customer_id) AS exposed_customers,
        COUNT(*) AS exposure_events,
        COUNT(DISTINCT ce.channel) AS exposure_channels
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
),

response_summary AS (
    SELECT
        cc.campaign_id,
        COUNT(DISTINCT cc.customer_id) FILTER (
            WHERE cc.response_status IS NOT NULL
        ) AS customers_with_response,
        COUNT(DISTINCT cc.customer_id) FILTER (
            WHERE cc.response_status IS NULL
        ) AS customers_without_response
    FROM marketing.campaign_customers AS cc
    GROUP BY cc.campaign_id
)

SELECT
    c.campaign_id,
    c.campaign_name,
    c.campaign_type,
    c.target_product_id,
    c.start_date,
    c.end_date,
    c.target_customer_type,

    -- Campaign duration
    (c.end_date - c.start_date + 1) AS campaign_duration_days,

    -- Targeting and exposure
    COALESCE(s.selected_customers, 0) AS selected_customers,
    COALESCE(e.exposed_customers, 0) AS exposed_customers,
    COALESCE(e.exposure_events, 0) AS exposure_events,
    COALESCE(e.exposure_channels, 0) AS exposure_channels,

    -- Response
    COALESCE(r.customers_with_response, 0) AS customers_with_response,
    COALESCE(r.customers_without_response, 0) AS customers_without_response,
    COALESCE(p.positive_responders, 0) AS positive_responders

FROM marketing.campaigns AS c
LEFT JOIN selected AS s
    ON s.campaign_id = c.campaign_id
LEFT JOIN exposed AS e
    ON e.campaign_id = c.campaign_id
LEFT JOIN positive AS p
    ON p.campaign_id = c.campaign_id
LEFT JOIN response_summary AS r
    ON r.campaign_id = c.campaign_id;


-- Validation
SELECT
    COUNT(*) AS total_rows,
    COUNT(DISTINCT campaign_id) AS distinct_campaigns,
    MIN(start_date) AS first_campaign_start,
    MAX(end_date) AS last_campaign_end,
    SUM(selected_customers) AS selected_customers,
    SUM(exposed_customers) AS exposed_customers,
    SUM(positive_responders) AS positive_responders
FROM analytics.campaign_performance;
