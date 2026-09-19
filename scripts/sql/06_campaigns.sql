-- ============================================================
-- BTYT — CAMPAIGNS & MARKETING EFFECTIVENESS ANALYTICS
-- File: 06_campaigns.sql
-- Architecture-aligned design
--
-- Purpose:
-- Prepare reusable campaign, campaign-customer and exposure-event
-- analytical datasets while keeping funnel definitions explicit.
--
-- PostgreSQL | Read-only analytical queries
-- ============================================================
--
-- MAIN QUESTION
-- Who is targeted, who is actually contacted, who responds, and
-- how should campaign effectiveness be measured?
--
-- TOOL OWNERSHIP
--
-- SQL:
-- - campaign dimension
-- - campaign-customer base
-- - exposure-event aggregation
-- - funnel flags
-- - response/exposure lags
-- - campaign overlap diagnostics
-- - channel/geography consistency checks
--
-- DAX / POWER BI:
-- - selected customers
-- - exposed customers
-- - response rates
-- - exposure rates
-- - campaign/channel/geography shares
--
-- PYTHON:
-- - exposure-frequency distributions
-- - response-lag distributions
-- - campaign saturation
-- - multi-touch exploratory analysis
--
-- TABLEAU:
-- - campaign geography
-- - spatial response storytelling
--
-- CRITICAL SEMANTIC RULES
--
-- 1. Selected customers != exposed customers.
-- 2. Exposed customers != exposure events.
-- 3. exposure_status is the canonical customer-level exposure flag.
-- 4. response_status is the canonical customer-level response outcome.
-- 5. response_date is timing metadata, not the response definition itself.
-- 6. Response rate among selected != response rate among exposed.
-- 7. POSITIVE response != product conversion.
-- 8. Exposure channel association != causal attribution.
--
-- ============================================================
-- 01. DOMAIN INVENTORY — RUN FIRST
-- ============================================================
--
-- Before freezing KPI definitions, inspect actual generated values.


-- 1.1 Campaign types.

SELECT
    c.campaign_type,
    COUNT(*) AS campaign_count
FROM marketing.campaigns AS c
GROUP BY c.campaign_type
ORDER BY campaign_count DESC;


-- 1.2 Target customer types.

SELECT
    c.target_customer_type,
    COUNT(*) AS campaign_count
FROM marketing.campaigns AS c
GROUP BY c.target_customer_type
ORDER BY campaign_count DESC;


-- 1.3 Exposure status values.

SELECT
    cc.exposure_status,
    COUNT(*) AS campaign_customer_count
FROM marketing.campaign_customers AS cc
GROUP BY cc.exposure_status
ORDER BY campaign_customer_count DESC;


-- 1.4 Response status values.

SELECT
    cc.response_status,
    COUNT(*) AS campaign_customer_count
FROM marketing.campaign_customers AS cc
GROUP BY cc.response_status
ORDER BY campaign_customer_count DESC;


-- 1.5 Actual exposure-event channels.

SELECT
    ce.channel,
    COUNT(*) AS exposure_event_count
FROM marketing.campaign_exposures AS ce
GROUP BY ce.channel
ORDER BY exposure_event_count DESC;


-- 1.6 Configured campaign channels.

SELECT
    rc.channel,
    COUNT(*) AS campaign_channel_count
FROM reference.campaign_channels AS rc
GROUP BY rc.channel
ORDER BY campaign_channel_count DESC;


-- 1.7 Configured geography levels.

SELECT
    cg.geography_level,
    COUNT(*) AS campaign_geography_count
FROM reference.campaign_geography AS cg
GROUP BY cg.geography_level
ORDER BY campaign_geography_count DESC;


-- ============================================================
-- 02. CAMPAIGN INVENTORY
-- ============================================================

-- 2.1 Complete campaign inventory.

SELECT
    c.campaign_id,
    c.campaign_name,
    c.campaign_type,
    c.target_product_id,
    p.product_name AS target_product_name,
    p.product_family AS target_product_family,
    c.start_date,
    c.end_date,
    c.target_customer_type,

    c.end_date - c.start_date + 1
        AS campaign_duration_days

FROM marketing.campaigns AS c

LEFT JOIN core.products AS p
    ON p.product_id = c.target_product_id

ORDER BY
    c.start_date,
    c.campaign_id;


-- ============================================================
-- 03. CAMPAIGN DIMENSION — SQL PREPARATION
-- ============================================================
--
-- Grain:
-- 1 row = 1 campaign
--
-- Configured channels and geographies are pre-aggregated before
-- joining to avoid multiplying campaign rows.

WITH configured_channels AS (
    SELECT
        cc.campaign_id,
        COUNT(*) AS configured_channel_count,
        STRING_AGG(
            cc.channel,
            ', '
            ORDER BY cc.channel
        ) AS configured_channels
    FROM reference.campaign_channels AS cc
    GROUP BY cc.campaign_id
),

configured_geography AS (
    SELECT
        cg.campaign_id,
        COUNT(*) AS configured_geography_count,
        COUNT(DISTINCT cg.geography_level)
            AS configured_geography_levels,
        STRING_AGG(
            cg.geography_level
            || ':'
            || cg.geography_value,
            ', '
            ORDER BY
                cg.geography_level,
                cg.geography_value
        ) AS configured_geographies
    FROM reference.campaign_geography AS cg
    GROUP BY cg.campaign_id
)

SELECT
    c.campaign_id,
    c.campaign_name,
    c.campaign_type,

    c.target_product_id,
    p.product_name AS target_product_name,
    p.product_family AS target_product_family,

    c.target_customer_type,

    c.start_date,
    c.end_date,

    c.end_date - c.start_date + 1
        AS campaign_duration_days,

    COALESCE(ch.configured_channel_count, 0)
        AS configured_channel_count,

    ch.configured_channels,

    COALESCE(cg.configured_geography_count, 0)
        AS configured_geography_count,

    COALESCE(cg.configured_geography_levels, 0)
        AS configured_geography_levels,

    cg.configured_geographies

FROM marketing.campaigns AS c

LEFT JOIN core.products AS p
    ON p.product_id = c.target_product_id

LEFT JOIN configured_channels AS ch
    ON ch.campaign_id = c.campaign_id

LEFT JOIN configured_geography AS cg
    ON cg.campaign_id = c.campaign_id;


-- ============================================================
-- 04. EXPOSURE-EVENT AGGREGATION
-- ============================================================
--
-- Aggregate exposure events BEFORE joining to campaign_customers.
--
-- Grain:
-- 1 row = 1 campaign × 1 customer
--
-- This avoids multiplying campaign-customer rows when a customer
-- receives several exposure events.

WITH exposure_summary AS (
    SELECT
        ce.campaign_id,
        ce.customer_id,

        COUNT(*) AS exposure_event_count,

        COUNT(DISTINCT ce.channel)
            AS distinct_exposure_channels,

        MIN(ce.exposure_datetime)
            AS first_exposure_datetime,

        MAX(ce.exposure_datetime)
            AS last_exposure_datetime,

        STRING_AGG(
            DISTINCT ce.channel,
            ', '
        ) AS exposure_channels

    FROM marketing.campaign_exposures AS ce

    GROUP BY
        ce.campaign_id,
        ce.customer_id
)

SELECT
    es.campaign_id,
    es.customer_id,
    es.exposure_event_count,
    es.distinct_exposure_channels,
    es.first_exposure_datetime,
    es.last_exposure_datetime,
    es.exposure_channels
FROM exposure_summary AS es
ORDER BY
    es.campaign_id,
    es.customer_id;


-- ============================================================
-- 05. CAMPAIGN-CUSTOMER ANALYTICAL BASE — SQL PREPARATION
-- ============================================================
--
-- This is the principal reusable source for Power BI.
--
-- Grain:
-- 1 row = 1 campaign × 1 customer
--
-- Canonical customer-level semantics:
-- - exposure_status = 'EXPOSED' defines an exposed customer;
-- - response_status in POSITIVE / NEGATIVE / NEUTRAL defines an
--   observed response;
-- - NO_RESPONSE means exposed but no observable response;
-- - NULL response_status is valid for NOT_EXPOSED customers.
--
-- Exposure events are aggregated as contact-intensity detail and are
-- not used to redefine the canonical customer-level status.

WITH exposure_summary AS (
    SELECT
        ce.campaign_id,
        ce.customer_id,
        COUNT(*) AS exposure_event_count,
        COUNT(DISTINCT ce.channel) AS distinct_exposure_channels,
        MIN(ce.exposure_datetime) AS first_exposure_datetime,
        MAX(ce.exposure_datetime) AS last_exposure_datetime,
        STRING_AGG(
            DISTINCT ce.channel,
            ', '
        ) AS exposure_channels
    FROM marketing.campaign_exposures AS ce
    GROUP BY
        ce.campaign_id,
        ce.customer_id
)

SELECT
    cc.campaign_id,
    cc.customer_id,

    c.campaign_name,
    c.campaign_type,
    c.target_product_id,
    p.product_name AS target_product_name,
    p.product_family AS target_product_family,
    c.target_customer_type,
    c.start_date,
    c.end_date,

    cc.selection_date,
    cc.exposure_status,
    cc.exposure_date,
    cc.response_status,
    cc.response_date,

    COALESCE(es.exposure_event_count, 0) AS exposure_event_count,
    COALESCE(es.distinct_exposure_channels, 0) AS distinct_exposure_channels,
    es.first_exposure_datetime,
    es.last_exposure_datetime,
    es.exposure_channels,

    CASE
        WHEN cc.exposure_status = 'EXPOSED' THEN 1
        ELSE 0
    END AS was_exposed,

    CASE
        WHEN cc.response_status IN ('POSITIVE', 'NEGATIVE', 'NEUTRAL')
            THEN 1
        ELSE 0
    END AS responded,

    CASE
        WHEN cc.response_status = 'POSITIVE' THEN 1
        ELSE 0
    END AS positive_response,

    CASE
        WHEN cc.response_status = 'NEGATIVE' THEN 1
        ELSE 0
    END AS negative_response,

    CASE
        WHEN cc.response_status = 'NEUTRAL' THEN 1
        ELSE 0
    END AS neutral_response,

    CASE
        WHEN cc.response_status = 'NO_RESPONSE' THEN 1
        ELSE 0
    END AS no_response,

    CASE
        WHEN cc.exposure_status = 'EXPOSED'
         AND cc.selection_date IS NOT NULL
         AND cc.exposure_date IS NOT NULL
            THEN cc.exposure_date - cc.selection_date
        ELSE NULL
    END AS days_selection_to_exposure,

    CASE
        WHEN cc.response_status IN ('POSITIVE', 'NEGATIVE', 'NEUTRAL')
         AND cc.response_date IS NOT NULL
         AND cc.exposure_date IS NOT NULL
            THEN cc.response_date - cc.exposure_date
        ELSE NULL
    END AS days_exposure_to_response,

    cust.customer_type,

    CASE
        WHEN cust.customer_type = 'INDIVIDUAL'
            THEN COALESCE(cust.employment_status, 'UNKNOWN')
        WHEN cust.customer_type = 'BUSINESS'
            THEN COALESCE(cust.company_size, 'UNKNOWN')
        ELSE 'UNKNOWN'
    END AS customer_segment,

    cust.residence_country,
    cust.residence_department,
    cust.residence_locality,
    cust.primary_branch_id,
    b.branch_name AS primary_branch_name,
    b.region AS primary_branch_region

FROM marketing.campaign_customers AS cc

JOIN marketing.campaigns AS c
    ON c.campaign_id = cc.campaign_id

LEFT JOIN core.products AS p
    ON p.product_id = c.target_product_id

JOIN core.customers AS cust
    ON cust.customer_id = cc.customer_id

LEFT JOIN core.branches AS b
    ON b.branch_id = cust.primary_branch_id

LEFT JOIN exposure_summary AS es
    ON es.campaign_id = cc.campaign_id
   AND es.customer_id = cc.customer_id;


-- ============================================================
-- 06. CAMPAIGN FUNNEL BASELINE — SQL VALIDATION
-- ============================================================
--
-- Funnel population:
-- Selected → Exposed → Observed Response
--
-- POSITIVE is also shown separately because it is commercially more
-- specific than the broader observed-response concept, but POSITIVE
-- still does NOT imply product conversion.

WITH campaign_customer_flags AS (
    SELECT
        cc.campaign_id,
        cc.customer_id,

        CASE
            WHEN cc.exposure_status = 'EXPOSED' THEN 1
            ELSE 0
        END AS was_exposed,

        CASE
            WHEN cc.response_status IN ('POSITIVE', 'NEGATIVE', 'NEUTRAL')
                THEN 1
            ELSE 0
        END AS responded,

        CASE
            WHEN cc.response_status = 'POSITIVE' THEN 1
            ELSE 0
        END AS positive_response,

        CASE
            WHEN cc.response_status = 'NEGATIVE' THEN 1
            ELSE 0
        END AS negative_response,

        CASE
            WHEN cc.response_status = 'NEUTRAL' THEN 1
            ELSE 0
        END AS neutral_response,

        CASE
            WHEN cc.response_status = 'NO_RESPONSE' THEN 1
            ELSE 0
        END AS no_response

    FROM marketing.campaign_customers AS cc
)

SELECT
    c.campaign_id,
    c.campaign_name,
    c.campaign_type,

    COUNT(*) AS selected_customers,
    SUM(ccf.was_exposed) AS exposed_customers,
    SUM(ccf.responded) AS responding_customers,
    SUM(ccf.positive_response) AS positive_responses,
    SUM(ccf.neutral_response) AS neutral_responses,
    SUM(ccf.negative_response) AS negative_responses,
    SUM(ccf.no_response) AS no_response_customers,

    ROUND(
        (
            100.0 * SUM(ccf.was_exposed)
            / NULLIF(COUNT(*), 0)
        )::NUMERIC,
        2
    ) AS exposure_rate_selected_pct,

    ROUND(
        (
            100.0 * SUM(ccf.responded)
            / NULLIF(COUNT(*), 0)
        )::NUMERIC,
        2
    ) AS response_rate_selected_pct,

    ROUND(
        (
            100.0 * SUM(ccf.responded)
            / NULLIF(SUM(ccf.was_exposed), 0)
        )::NUMERIC,
        2
    ) AS response_rate_exposed_pct,

    ROUND(
        (
            100.0 * SUM(ccf.positive_response)
            / NULLIF(SUM(ccf.was_exposed), 0)
        )::NUMERIC,
        2
    ) AS positive_response_rate_exposed_pct

FROM campaign_customer_flags AS ccf

JOIN marketing.campaigns AS c
    ON c.campaign_id = ccf.campaign_id

GROUP BY
    c.campaign_id,
    c.campaign_name,
    c.campaign_type

ORDER BY selected_customers DESC;


-- ============================================================
-- 07. EXPOSURE INTENSITY BASELINE — SQL VALIDATION
-- ============================================================
--
-- Distinguishes exposed customers from exposure events.

WITH exposure_summary AS (
    SELECT
        ce.campaign_id,
        ce.customer_id,
        COUNT(*) AS exposure_event_count,
        COUNT(DISTINCT ce.channel)
            AS distinct_exposure_channels
    FROM marketing.campaign_exposures AS ce
    GROUP BY
        ce.campaign_id,
        ce.customer_id
)

SELECT
    c.campaign_id,
    c.campaign_name,

    COUNT(*) AS exposed_customers,

    SUM(COALESCE(es.exposure_event_count, 0))
        AS exposure_events,

    ROUND(
        AVG(COALESCE(es.exposure_event_count, 0))::NUMERIC,
        2
    ) AS avg_exposure_events_per_exposed_customer,

    ROUND(
        AVG(COALESCE(es.distinct_exposure_channels, 0))::NUMERIC,
        2
    ) AS avg_distinct_channels_per_exposed_customer

FROM marketing.campaign_customers AS cc

JOIN marketing.campaigns AS c
    ON c.campaign_id = cc.campaign_id

LEFT JOIN exposure_summary AS es
    ON es.campaign_id = cc.campaign_id
   AND es.customer_id = cc.customer_id

WHERE cc.exposure_status = 'EXPOSED'

GROUP BY
    c.campaign_id,
    c.campaign_name

ORDER BY
    exposure_events DESC;


-- ============================================================
-- 08. EXPOSURE-EVENT BASE — SQL PREPARATION
-- ============================================================
--
-- Grain:
-- 1 row = 1 exposure event
--
-- Use this only when event-level channel sequencing is required.
-- Do not use it as the default Power BI campaign grain.

SELECT
    ce.exposure_id,
    ce.campaign_id,
    ce.customer_id,
    ce.exposure_datetime,
    ce.channel,

    c.campaign_name,
    c.campaign_type,
    c.target_product_id,

    p.product_name AS target_product_name,
    p.product_family AS target_product_family,

    cust.customer_type,

    CASE
        WHEN cust.customer_type = 'INDIVIDUAL'
            THEN COALESCE(
                cust.employment_status,
                'UNKNOWN'
            )
        WHEN cust.customer_type = 'BUSINESS'
            THEN COALESCE(
                cust.company_size,
                'UNKNOWN'
            )
        ELSE 'UNKNOWN'
    END AS customer_segment,

    cust.residence_department,
    cust.residence_locality

FROM marketing.campaign_exposures AS ce

JOIN marketing.campaigns AS c
    ON c.campaign_id = ce.campaign_id

LEFT JOIN core.products AS p
    ON p.product_id = c.target_product_id

JOIN core.customers AS cust
    ON cust.customer_id = ce.customer_id;


-- ============================================================
-- 09. CHANNEL EXECUTION VALIDATION
-- ============================================================
--
-- 9.1 Actual exposure channel versus configured channel.
--
-- Rows returned here indicate exposure events using channels that
-- were not configured for that campaign.

SELECT
    ce.exposure_id,
    ce.campaign_id,
    c.campaign_name,
    ce.customer_id,
    ce.channel AS actual_exposure_channel
FROM marketing.campaign_exposures AS ce
JOIN marketing.campaigns AS c
    ON c.campaign_id = ce.campaign_id
LEFT JOIN reference.campaign_channels AS rc
    ON rc.campaign_id = ce.campaign_id
   AND rc.channel = ce.channel
WHERE rc.campaign_id IS NULL
ORDER BY
    ce.campaign_id,
    ce.exposure_id;


-- 9.2 Configured versus actual channel counts by campaign.

WITH configured AS (
    SELECT
        cc.campaign_id,
        COUNT(DISTINCT cc.channel)
            AS configured_channel_count
    FROM reference.campaign_channels AS cc
    GROUP BY cc.campaign_id
),

actual AS (
    SELECT
        ce.campaign_id,
        COUNT(DISTINCT ce.channel)
            AS actual_channel_count
    FROM marketing.campaign_exposures AS ce
    GROUP BY ce.campaign_id
)

SELECT
    c.campaign_id,
    c.campaign_name,

    COALESCE(cfg.configured_channel_count, 0)
        AS configured_channel_count,

    COALESCE(act.actual_channel_count, 0)
        AS actual_channel_count

FROM marketing.campaigns AS c

LEFT JOIN configured AS cfg
    ON cfg.campaign_id = c.campaign_id

LEFT JOIN actual AS act
    ON act.campaign_id = c.campaign_id

ORDER BY c.campaign_id;


-- ============================================================
-- 10. GEOGRAPHY BASELINE
-- ============================================================
--
-- Preserve geography_level and geography_value.
-- Do not flatten different geographic levels into one meaning.

SELECT
    c.campaign_id,
    c.campaign_name,
    c.campaign_type,

    cg.geography_level,
    cg.geography_value

FROM reference.campaign_geography AS cg

JOIN marketing.campaigns AS c
    ON c.campaign_id = cg.campaign_id

ORDER BY
    c.campaign_id,
    cg.geography_level,
    cg.geography_value;


-- ============================================================
-- 11. TARGET CUSTOMER-TYPE ALIGNMENT
-- ============================================================
--
-- Structural diagnostic:
-- Does the selected population match the campaign target type?

SELECT
    c.campaign_id,
    c.campaign_name,
    c.target_customer_type,

    cust.customer_type
        AS actual_customer_type,

    COUNT(*) AS selected_customers

FROM marketing.campaign_customers AS cc

JOIN marketing.campaigns AS c
    ON c.campaign_id = cc.campaign_id

JOIN core.customers AS cust
    ON cust.customer_id = cc.customer_id

GROUP BY
    c.campaign_id,
    c.campaign_name,
    c.target_customer_type,
    cust.customer_type

ORDER BY
    c.campaign_id,
    selected_customers DESC;


-- ============================================================
-- 12. CAMPAIGN OVERLAP DIAGNOSTICS
-- ============================================================

-- 12.1 Calendar overlap between campaigns.
--
-- One row per overlapping campaign pair.

SELECT
    c1.campaign_id AS campaign_1_id,
    c1.campaign_name AS campaign_1_name,

    c2.campaign_id AS campaign_2_id,
    c2.campaign_name AS campaign_2_name,

    GREATEST(
        c1.start_date,
        c2.start_date
    ) AS overlap_start_date,

    LEAST(
        c1.end_date,
        c2.end_date
    ) AS overlap_end_date,

    LEAST(
        c1.end_date,
        c2.end_date
    )
    - GREATEST(
        c1.start_date,
        c2.start_date
    )
    + 1 AS overlap_days

FROM marketing.campaigns AS c1

JOIN marketing.campaigns AS c2
    ON c1.campaign_id < c2.campaign_id
   AND c1.start_date <= c2.end_date
   AND c2.start_date <= c1.end_date

ORDER BY
    overlap_start_date,
    campaign_1_id,
    campaign_2_id;


-- 12.2 Customer campaign saturation.
--
-- Grain:
-- 1 row = 1 customer
--
-- Useful later for Python distributional analysis.

SELECT
    cc.customer_id,

    COUNT(DISTINCT cc.campaign_id)
        AS campaigns_selected,

    COUNT(DISTINCT cc.campaign_id) FILTER (
        WHERE cc.exposure_status = 'EXPOSED'
    ) AS campaigns_exposed,

    COUNT(DISTINCT cc.campaign_id) FILTER (
        WHERE cc.response_status IN ('POSITIVE', 'NEGATIVE', 'NEUTRAL')
    ) AS campaigns_responded,

    COUNT(DISTINCT cc.campaign_id) FILTER (
        WHERE cc.response_status = 'POSITIVE'
    ) AS campaigns_positive_response

FROM marketing.campaign_customers AS cc

GROUP BY cc.customer_id

ORDER BY
    campaigns_selected DESC,
    cc.customer_id;


-- ============================================================
-- 13. DATA-QUALITY DIAGNOSTICS
-- ============================================================

-- 13.1 Duplicate campaign-customer rows.
-- The relational PK should make this return zero rows.

SELECT
    cc.campaign_id,
    cc.customer_id,
    COUNT(*) AS row_count
FROM marketing.campaign_customers AS cc
GROUP BY
    cc.campaign_id,
    cc.customer_id
HAVING COUNT(*) > 1
ORDER BY row_count DESC;


-- 13.2 Duplicate exposure IDs.
-- The relational PK should make this return zero rows.

SELECT
    ce.exposure_id,
    COUNT(*) AS row_count
FROM marketing.campaign_exposures AS ce
GROUP BY ce.exposure_id
HAVING COUNT(*) > 1
ORDER BY row_count DESC;


-- 13.3 Campaign dates in invalid order.

SELECT
    c.campaign_id,
    c.campaign_name,
    c.start_date,
    c.end_date
FROM marketing.campaigns AS c
WHERE c.end_date < c.start_date
ORDER BY c.campaign_id;


-- 13.4 Selection outside campaign window.

SELECT
    cc.campaign_id,
    cc.customer_id,
    cc.selection_date,
    c.start_date,
    c.end_date
FROM marketing.campaign_customers AS cc
JOIN marketing.campaigns AS c
    ON c.campaign_id = cc.campaign_id
WHERE cc.selection_date IS NOT NULL
  AND (
        cc.selection_date < c.start_date
        OR cc.selection_date > c.end_date
      )
ORDER BY
    cc.campaign_id,
    cc.customer_id;


-- 13.5 Response before selection.

SELECT
    cc.campaign_id,
    cc.customer_id,
    cc.selection_date,
    cc.response_date
FROM marketing.campaign_customers AS cc
WHERE cc.response_date IS NOT NULL
  AND cc.selection_date IS NOT NULL
  AND cc.response_date < cc.selection_date
ORDER BY
    cc.campaign_id,
    cc.customer_id;


-- 13.6 Response before recorded exposure.
-- Canonical exposed campaign-customer rows carry exposure_date, and
-- observed responses must occur on or after that first exposure date.
-- Expected result: zero rows.

SELECT
    cc.campaign_id,
    cc.customer_id,
    cc.exposure_date,
    cc.response_date
FROM marketing.campaign_customers AS cc
WHERE cc.response_date IS NOT NULL
  AND cc.exposure_date IS NOT NULL
  AND cc.response_date < cc.exposure_date
ORDER BY
    cc.campaign_id,
    cc.customer_id;


-- 13.7 Exposure events outside campaign window.

SELECT
    ce.exposure_id,
    ce.campaign_id,
    ce.customer_id,
    ce.exposure_datetime,
    c.start_date,
    c.end_date
FROM marketing.campaign_exposures AS ce
JOIN marketing.campaigns AS c
    ON c.campaign_id = ce.campaign_id
WHERE ce.exposure_datetime::DATE < c.start_date
   OR ce.exposure_datetime::DATE > c.end_date
ORDER BY ce.exposure_id;


-- 13.8 Canonical status / date consistency.
-- Expected result: zero rows.

SELECT
    cc.campaign_id,
    cc.customer_id,
    cc.exposure_status,
    cc.exposure_date,
    cc.response_status,
    cc.response_date
FROM marketing.campaign_customers AS cc
WHERE
       (cc.exposure_status = 'EXPOSED' AND cc.exposure_date IS NULL)
    OR (cc.exposure_status = 'NOT_EXPOSED' AND cc.exposure_date IS NOT NULL)
    OR (cc.exposure_status = 'NOT_EXPOSED' AND cc.response_status IS NOT NULL)
    OR (cc.exposure_status = 'NOT_EXPOSED' AND cc.response_date IS NOT NULL)
    OR (cc.exposure_status = 'EXPOSED' AND cc.response_status IS NULL)
    OR (cc.response_status = 'NO_RESPONSE' AND cc.response_date IS NOT NULL)
    OR (
        cc.response_status IN ('POSITIVE', 'NEGATIVE', 'NEUTRAL')
        AND cc.response_date IS NULL
    )
ORDER BY
    cc.campaign_id,
    cc.customer_id;


-- 13.9 Campaign-customer exposure-date versus exposure-event presence.

--
-- Expected result: zero rows. Shows inconsistent exposure recording.

WITH exposure_summary AS (
    SELECT
        ce.campaign_id,
        ce.customer_id,
        COUNT(*) AS exposure_event_count
    FROM marketing.campaign_exposures AS ce
    GROUP BY
        ce.campaign_id,
        ce.customer_id
)

SELECT
    cc.campaign_id,
    cc.customer_id,
    cc.exposure_status,
    cc.exposure_date,
    COALESCE(es.exposure_event_count, 0)
        AS exposure_event_count
FROM marketing.campaign_customers AS cc
LEFT JOIN exposure_summary AS es
    ON es.campaign_id = cc.campaign_id
   AND es.customer_id = cc.customer_id
WHERE
    (
        cc.exposure_date IS NOT NULL
        AND COALESCE(es.exposure_event_count, 0) = 0
    )
    OR
    (
        cc.exposure_date IS NULL
        AND COALESCE(es.exposure_event_count, 0) > 0
    )
ORDER BY
    cc.campaign_id,
    cc.customer_id;




-- 13.10 Recorded exposure date versus first exposure event.
-- Expected result: zero rows.

WITH first_exposure AS (
    SELECT
        ce.campaign_id,
        ce.customer_id,
        MIN(ce.exposure_datetime)::DATE AS first_exposure_date
    FROM marketing.campaign_exposures AS ce
    GROUP BY
        ce.campaign_id,
        ce.customer_id
)

SELECT
    cc.campaign_id,
    cc.customer_id,
    cc.exposure_date,
    fe.first_exposure_date
FROM marketing.campaign_customers AS cc
JOIN first_exposure AS fe
    ON fe.campaign_id = cc.campaign_id
   AND fe.customer_id = cc.customer_id
WHERE cc.exposure_date <> fe.first_exposure_date
ORDER BY
    cc.campaign_id,
    cc.customer_id;


-- ============================================================
-- 14. DOWNSTREAM ANALYTICAL HANDOFF
-- ============================================================
--
-- POWER BI / DAX
--
-- Preferred source:
-- campaign-customer analytical base
--
-- Dynamic measures:
--
-- - Campaign Count
-- - Selected Customers
-- - Exposed Customers
-- - Exposure Rate %
-- - Responding Customers
-- - Positive Responses
-- - Response Rate — Selected %
-- - Response Rate — Exposed %
-- - Positive Response Rate — Exposed %
-- - Exposure Events
-- - Exposures per Exposed Customer
-- - Average Response Lag
-- - Multi-Channel Customer %
-- - Campaign Share by Product
-- - Campaign Share by Geography
--
-- IMPORTANT:
-- Never create a generic Response Rate measure without documenting
-- its denominator.
--
--
-- PYTHON / PANDAS / JUPYTER
--
-- Strong candidates:
--
-- - exposure-frequency distributions
-- - response-lag distributions
-- - campaign saturation
-- - repeated-contact behavior
-- - responding vs non-responding profile comparisons
-- - campaign clustering
-- - exploratory multi-touch analysis
--
-- Do not imply causal uplift without a valid causal design.
--
--
-- TABLEAU
--
-- Strong candidates:
--
-- - campaign geography maps
-- - target geography versus customer residence
-- - response geography
-- - repeated campaign coverage by region
--
--
-- POWER QUERY
--
-- Keep it light:
--
-- - connect to PostgreSQL
-- - load reusable analytical objects
-- - enforce types
-- - avoid recreating funnel logic outside SQL
--
-- ============================================================
-- 15. PERSISTENCE DECISION
-- ============================================================
--
-- Candidate reusable objects:
--
-- - campaign dimension
-- - campaign-customer analytical base
-- - exposure-event base
--
-- Persist as views/materialized views only when:
--
-- 1. grain is stable;
-- 2. logic is reused;
-- 3. downstream tools benefit;
-- 4. refresh semantics are clear.
--
-- ============================================================
-- END
-- ============================================================
