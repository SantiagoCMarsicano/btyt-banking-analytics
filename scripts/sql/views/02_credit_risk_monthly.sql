-- ============================================================
-- BTYT BANKING ANALYTICS
-- 02_credit_risk_monthly.sql
-- Loan-level monthly credit-risk analytical view.
--
-- Grain:
-- one loan per month
--
-- Sources:
-- banking.loan_monthly_snapshot
-- banking.loans
--
-- Notes:
-- - Contract/master attributes come from banking.loans.
-- - Historical monthly risk state comes from loan_monthly_snapshot.
-- - Master loan_status is a cutoff attribute and must not be read as
--   the historical status of the loan in each month.
-- - Roll-rate and cure-rate transitions are not calculated here.
-- ============================================================

DROP VIEW IF EXISTS analytics.credit_risk_monthly;

CREATE VIEW analytics.credit_risk_monthly AS
SELECT
    lms.year_month,
    lms.loan_id,

    -- Loan dimensions
    l.customer_id,
    l.product_id,
    l.branch_id,
    l.origination_year,
    l.currency,
    l.original_amount,
    l.term_months,
    l.rate_type,
    l.initial_interest_rate,
    l.loan_status,
    l.closing_year,

    -- Monthly credit state
    lms.outstanding_balance,
    lms.current_interest_rate,
    lms.scheduled_payment,
    lms.actual_payment,
    lms.days_past_due,
    lms.delinquency_status,
    lms.arrears_amount,

    -- Analytical flags
    CASE
        WHEN lms.days_past_due >= 30 THEN 1
        ELSE 0
    END AS is_30_plus_dpd,

    CASE
        WHEN lms.days_past_due >= 90 THEN 1
        ELSE 0
    END AS is_90_plus_dpd,

    GREATEST(
        lms.scheduled_payment - lms.actual_payment,
        0
    ) AS payment_shortfall

FROM banking.loan_monthly_snapshot AS lms
INNER JOIN banking.loans AS l
    ON l.loan_id = lms.loan_id;


-- Validation
SELECT
    COUNT(*) AS total_rows,
    MIN(year_month) AS first_month,
    MAX(year_month) AS last_month,
    COUNT(DISTINCT loan_id) AS distinct_loans
FROM analytics.credit_risk_monthly;
