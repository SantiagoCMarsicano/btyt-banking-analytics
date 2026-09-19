-- ============================================================
-- BTYT SQL CHEATSHEET — COMPLETE STUDY GUIDE
-- PostgreSQL | Personal practice file
-- ============================================================
--
-- PURPOSE
-- A practical reference for learning SQL while analyzing BTYT.
-- The goal is not to memorize the file: understand the logic, then reuse it.
--
-- EXECUTION RULES
-- 1. Keep the active connection on the BTYT PostgreSQL database.
-- 2. Most examples are standalone: place the cursor in the statement and run it.
-- 3. In DBeaver, the small Run arrow above a detected SQL statement is fine.
-- 4. In VS Code / DBCode, use the extension's Run/Execute action if Ctrl+Enter
--    is not mapped correctly.
-- 5. Sections marked "RUN AS A BLOCK" contain setup + dependent statements.
--    Select the complete block and run it together, especially after reconnecting.
-- 6. Do NOT run the entire file blindly. Some examples scan large BTYT tables.
-- 7. All write practice uses TEMP tables. Canonical BTYT tables are not modified.
-- 8. Prefer schema-qualified names: core.customers, banking.loans, etc.
--
-- CORE MENTAL ORDER
-- SELECT
-- FROM
-- JOIN ... ON
-- WHERE
-- GROUP BY
-- HAVING
-- ORDER BY
-- LIMIT
--
-- IMPORTANT
-- NULL is not 0 and not an empty string.
-- JOIN means INNER JOIN.
-- WHERE filters rows before aggregation.
-- HAVING filters groups after aggregation.
-- A normal VIEW stores a query definition.
-- A MATERIALIZED VIEW stores query results physically.
-- Indexes should be created only after measuring a real workload.
--
-- ============================================================
-- 00. CONNECTION / DATABASE ORIENTATION
-- ============================================================

-- 00.1 Confirm the active database and user.
SELECT
    current_database() AS database_name,
    current_user AS database_user,
    current_schema() AS current_schema;

-- 00.2 List BTYT application schemas visible to the current user.
SELECT
    nspname AS schema_name
FROM pg_catalog.pg_namespace
WHERE nspname IN (
    'core',
    'banking',
    'marketing',
    'reference',
    'market',
    'macro',
    'performance'
)
ORDER BY nspname;

-- 00.3 Inspect every column of a table without relying on the ERD.
-- Change table_schema / table_name as needed.
SELECT
    c.ordinal_position,
    c.column_name,
    c.data_type,
    c.is_nullable
FROM information_schema.columns AS c
WHERE c.table_schema = 'core'
  AND c.table_name = 'customers'
ORDER BY c.ordinal_position;

-- ============================================================
-- INDEX
-- ============================================================
-- 01. SELECT / FROM / WHERE / ORDER BY / LIMIT
-- 02. DISTINCT
-- 03. NULL / IS NULL / IS NOT NULL / COALESCE / NULLIF
-- 04. STRING / NUMERIC / DATE FUNCTIONS
-- 05. CASE WHEN
-- 06. AGGREGATIONS
-- 07. GROUP BY / HAVING
-- 08. INNER JOIN
-- 09. LEFT JOIN / RIGHT JOIN / FULL JOIN
-- 10. MULTIPLE JOINS
-- 11. SELF JOIN
-- 12. SUBQUERIES
-- 13. CORRELATED SUBQUERIES
-- 14. EXISTS / NOT EXISTS
-- 15. CTEs
-- 16. WINDOW FUNCTIONS
-- 17. SET OPERATIONS
-- 18. VIEWS / MATERIALIZED VIEWS
-- 19. CAST / TYPE CONVERSION
-- 20. INSERT / UPDATE / DELETE              [TEMP TABLE LAB]
-- 21. CONSTRAINTS                           [TEMP TABLE LAB]
-- 22. INDEXES                               [TEMP TABLE LAB]
-- 23. EXPLAIN / EXPLAIN ANALYZE
-- 24. TRANSACTIONS                          [TEMP TABLE LAB]
-- APPENDIX. KPI BRIDGE: COST-TO-INCOME
--
-- ============================================================
-- 01. SELECT / FROM / WHERE / ORDER BY / LIMIT
-- ============================================================

-- 1.1 Products for individual customers.
SELECT
    p.product_name,
    p.product_id,
    p.target_customer_type
FROM core.products AS p
WHERE p.target_customer_type = 'INDIVIDUAL'
ORDER BY p.product_name DESC;

-- 1.2 Accounts opened in 2022.
SELECT
    a.account_id,
    a.opening_year,
    a.customer_id
FROM core.accounts AS a
WHERE a.opening_year = 2022
ORDER BY a.account_id
LIMIT 20;

-- 1.3 Oldest accounts with no closing year.
SELECT
    a.account_id,
    a.opening_year,
    a.branch_id
FROM core.accounts AS a
WHERE a.closing_year IS NULL
ORDER BY a.opening_year
LIMIT 20;

-- 1.4 Multiple conditions.
SELECT
    c.customer_id,
    c.customer_type,
    c.nationality,
    c.monthly_income
FROM core.customers AS c
WHERE c.customer_type = 'INDIVIDUAL'
  AND c.nationality = 'VENEZUELA'
ORDER BY c.customer_id
LIMIT 20;


-- ============================================================
-- 02. DISTINCT
-- ============================================================

-- 2.1 Unique account opening years.
SELECT DISTINCT
    a.opening_year
FROM core.accounts AS a
ORDER BY a.opening_year;

-- 2.2 Unique nationalities.
SELECT DISTINCT
    c.nationality
FROM core.customers AS c
ORDER BY c.nationality;

-- 2.3 Unique transaction types.
-- NOTE: transactions is a very large table; this may take longer than small-table examples.
SELECT DISTINCT
    t.transaction_type
FROM banking.transactions AS t
ORDER BY t.transaction_type;

-- 2.4 Unique transaction channels.
-- NOTE: transactions is a very large table; this may take longer than small-table examples.
SELECT DISTINCT
    t.channel
FROM banking.transactions AS t
ORDER BY t.channel;


-- ============================================================
-- 03. NULL / IS NULL / IS NOT NULL / COALESCE / NULLIF
-- ============================================================

-- 3.1 Find missing values.
SELECT
    c.customer_id,
    c.customer_type,
    c.nationality
FROM core.customers AS c
WHERE c.nationality IS NULL
LIMIT 50;

-- 3.2 Find non-missing values.
SELECT
    a.account_id,
    a.opening_year,
    a.closing_year
FROM core.accounts AS a
WHERE a.closing_year IS NOT NULL
ORDER BY a.closing_year DESC
LIMIT 20;

-- 3.3 Replace NULL in the result.
SELECT
    c.customer_id,
    c.customer_type,
    COALESCE(c.nationality, 'UNKNOWN') AS nationality
FROM core.customers AS c
LIMIT 50;

-- 3.4 First non-NULL value.
SELECT
    c.customer_id,
    c.customer_type,
    COALESCE(
        c.company_name,
        CONCAT(c.first_name, ' ', c.last_name),
        'NO NAME'
    ) AS customer_name
FROM core.customers AS c
LIMIT 50;

-- 3.5 NULLIF turns equal values into NULL.
SELECT
    NULLIF(100, 100) AS becomes_null,
    NULLIF(100, 0) AS keeps_100;

-- 3.6 Typical use: avoid division by zero.
SELECT
    bmp.branch_id,
    bmp.year_month,
    bmp.total_operating_cost,
    bmp.total_revenue,
    bmp.total_operating_cost / NULLIF(bmp.total_revenue, 0)
        AS cost_to_income_ratio
FROM performance.branch_monthly_performance AS bmp
LIMIT 20;


-- ============================================================
-- 04. STRING / NUMERIC / DATE FUNCTIONS
-- ============================================================

-- 4.1 String functions.
SELECT
    c.customer_id,
    UPPER(c.nationality) AS nationality_upper,
    LOWER(c.nationality) AS nationality_lower,
    TRIM(c.residence_department) AS department_clean
FROM core.customers AS c
WHERE c.nationality IS NOT NULL
LIMIT 20;

-- 4.2 Build a display name.
SELECT
    c.customer_id,
    CONCAT(c.first_name, ' ', c.last_name) AS full_name
FROM core.customers AS c
WHERE c.customer_type = 'INDIVIDUAL'
LIMIT 20;

-- 4.3 Numeric functions.
SELECT
    l.loan_id,
    l.original_amount,
    ROUND(l.original_amount::NUMERIC, 0) AS amount_rounded,
    ABS(l.original_amount) AS absolute_amount
FROM banking.loans AS l
LIMIT 20;

-- 4.4 Extract year and month.
SELECT
    bmp.year_month,
    EXTRACT(YEAR FROM bmp.year_month) AS year,
    EXTRACT(MONTH FROM bmp.year_month) AS month
FROM performance.bank_monthly_performance AS bmp
ORDER BY bmp.year_month;


-- ============================================================
-- 05. CASE WHEN
-- ============================================================

-- 5.1 Income segmentation.
SELECT
    c.customer_id,
    c.monthly_income,
    CASE
        WHEN c.monthly_income IS NULL THEN 'UNKNOWN'
        WHEN c.monthly_income < 30000 THEN 'LOW'
        WHEN c.monthly_income < 80000 THEN 'MEDIUM'
        ELSE 'HIGH'
    END AS income_segment
FROM core.customers AS c
WHERE c.customer_type = 'INDIVIDUAL'
LIMIT 50;

-- 5.2 Approximate age bands at the 2026 dataset endpoint.
SELECT
    c.customer_id,
    c.birth_year,
    2026 - c.birth_year AS approx_age,
    CASE
        WHEN c.birth_year IS NULL THEN 'UNKNOWN'
        WHEN 2026 - c.birth_year BETWEEN 18 AND 24 THEN '18-24'
        WHEN 2026 - c.birth_year BETWEEN 25 AND 34 THEN '25-34'
        WHEN 2026 - c.birth_year BETWEEN 35 AND 44 THEN '35-44'
        WHEN 2026 - c.birth_year BETWEEN 45 AND 54 THEN '45-54'
        WHEN 2026 - c.birth_year BETWEEN 55 AND 64 THEN '55-64'
        ELSE '65+'
    END AS age_group
FROM core.customers AS c
WHERE c.customer_type = 'INDIVIDUAL'
LIMIT 50;


-- ============================================================
-- 06. AGGREGATIONS
-- COUNT / SUM / AVG / MIN / MAX
-- ============================================================

SELECT COUNT(*) AS total_customers
FROM core.customers;

SELECT
    COUNT(*) AS loan_count,
    SUM(l.original_amount) AS total_original_amount,
    AVG(l.original_amount) AS average_original_amount,
    MIN(l.original_amount) AS minimum_original_amount,
    MAX(l.original_amount) AS maximum_original_amount
FROM banking.loans AS l;

SELECT
    SUM(bmp.total_revenue) AS total_revenue,
    SUM(bmp.total_operating_cost) AS total_operating_cost,
    SUM(bmp.net_income) AS total_net_income
FROM performance.bank_monthly_performance AS bmp;


-- ============================================================
-- 07. GROUP BY / HAVING
-- ============================================================

-- WHERE filters rows. HAVING filters aggregated groups.

SELECT
    c.customer_status,
    COUNT(*) AS customer_count
FROM core.customers AS c
GROUP BY c.customer_status
ORDER BY customer_count DESC;

SELECT
    l.loan_status,
    COUNT(*) AS loan_count
FROM banking.loans AS l
GROUP BY l.loan_status
ORDER BY loan_count DESC;

SELECT
    COALESCE(c.nationality, 'UNKNOWN') AS nationality,
    COUNT(*) AS customer_count
FROM core.customers AS c
GROUP BY COALESCE(c.nationality, 'UNKNOWN')
ORDER BY customer_count DESC;

SELECT
    c.primary_branch_id,
    COUNT(*) AS customer_count
FROM core.customers AS c
GROUP BY c.primary_branch_id
HAVING COUNT(*) > 3000
ORDER BY customer_count DESC;

SELECT
    EXTRACT(YEAR FROM bmp.year_month)::INT AS year,
    SUM(bmp.total_revenue) AS annual_revenue,
    SUM(bmp.net_income) AS annual_net_income
FROM performance.bank_monthly_performance AS bmp
GROUP BY EXTRACT(YEAR FROM bmp.year_month)
ORDER BY year;


-- ============================================================
-- 08. INNER JOIN
-- ============================================================

-- JOIN = INNER JOIN. Only matching rows survive.

SELECT
    c.customer_id,
    c.customer_type,
    a.account_id,
    a.account_status
FROM core.customers AS c
JOIN core.accounts AS a
    ON c.customer_id = a.customer_id
LIMIT 50;

SELECT
    a.account_id,
    a.customer_id,
    p.product_name,
    p.product_family
FROM core.accounts AS a
JOIN core.products AS p
    ON a.product_id = p.product_id
LIMIT 50;

SELECT
    l.loan_id,
    l.loan_status,
    l.original_amount,
    b.branch_name,
    b.region
FROM banking.loans AS l
JOIN core.branches AS b
    ON l.branch_id = b.branch_id
LIMIT 50;


-- ============================================================
-- 09. LEFT JOIN / RIGHT JOIN / FULL JOIN
-- ============================================================

-- LEFT JOIN keeps every row from the left table.

SELECT
    c.customer_id,
    c.customer_type,
    ca.card_id,
    ca.product_id
FROM core.customers AS c
LEFT JOIN banking.cards AS ca
    ON c.customer_id = ca.customer_id
   AND ca.product_id IN ('P010', 'P011')
LIMIT 100;

-- Turn the result into a YES / NO indicator.
SELECT
    c.customer_id,
    CASE
        WHEN COUNT(ca.card_id) > 0 THEN 'YES'
        ELSE 'NO'
    END AS has_credit_card
FROM core.customers AS c
LEFT JOIN banking.cards AS ca
    ON c.customer_id = ca.customer_id
   AND ca.product_id IN ('P010', 'P011')
GROUP BY c.customer_id
LIMIT 100;

-- RIGHT JOIN keeps every row from the right table.
SELECT
    a.account_id,
    p.product_id,
    p.product_name
FROM core.accounts AS a
RIGHT JOIN core.products AS p
    ON a.product_id = p.product_id
LIMIT 100;

-- FULL JOIN keeps all rows from both sides.
SELECT
    a.account_id,
    a.product_id AS account_product_id,
    p.product_id AS product_product_id,
    p.product_name
FROM core.accounts AS a
FULL JOIN core.products AS p
    ON a.product_id = p.product_id
LIMIT 100;


-- ============================================================
-- 10. MULTIPLE JOINS
-- ============================================================

SELECT
    c.customer_id,
    c.customer_type,
    a.account_id,
    p.product_name,
    b.branch_name,
    b.region
FROM core.customers AS c
JOIN core.accounts AS a
    ON c.customer_id = a.customer_id
JOIN core.products AS p
    ON a.product_id = p.product_id
JOIN core.branches AS b
    ON a.branch_id = b.branch_id
LIMIT 100;

SELECT
    c.customer_id,
    c.customer_type,
    l.loan_id,
    l.loan_status,
    l.original_amount,
    p.product_name,
    b.branch_name
FROM core.customers AS c
JOIN banking.loans AS l
    ON c.customer_id = l.customer_id
JOIN core.products AS p
    ON l.product_id = p.product_id
JOIN core.branches AS b
    ON l.branch_id = b.branch_id
LIMIT 100;


-- ============================================================
-- 11. SELF JOIN
-- ============================================================

-- A table joins to itself.
-- Natural BTYT example: branch -> parent branch.

SELECT
    child.branch_id AS child_branch_id,
    child.branch_name AS child_branch_name,
    parent.branch_id AS parent_branch_id,
    parent.branch_name AS parent_branch_name
FROM core.branches AS child
LEFT JOIN core.branches AS parent
    ON child.parent_branch_id = parent.branch_id
ORDER BY child.branch_id;


-- ============================================================
-- 12. SUBQUERIES
-- ============================================================

SELECT
    c.customer_id,
    c.monthly_income
FROM core.customers AS c
WHERE c.customer_type = 'INDIVIDUAL'
  AND c.monthly_income > (
        SELECT AVG(c2.monthly_income)
        FROM core.customers AS c2
        WHERE c2.customer_type = 'INDIVIDUAL'
          AND c2.monthly_income IS NOT NULL
    )
ORDER BY c.monthly_income DESC
LIMIT 50;

SELECT
    l.loan_id,
    l.product_id,
    l.original_amount
FROM banking.loans AS l
WHERE l.original_amount > (
    SELECT AVG(l2.original_amount)
    FROM banking.loans AS l2
)
ORDER BY l.original_amount DESC
LIMIT 50;


-- ============================================================
-- 13. CORRELATED SUBQUERIES
-- ============================================================

-- The inner query depends on the current outer row.

SELECT
    ab.account_id,
    ab.year_month,
    ab.closing_balance
FROM banking.account_balances AS ab
WHERE ab.year_month = (
    SELECT MAX(ab2.year_month)
    FROM banking.account_balances AS ab2
    WHERE ab2.account_id = ab.account_id
)
LIMIT 100;

SELECT
    c.customer_id,
    c.customer_type
FROM core.customers AS c
WHERE (
    SELECT COUNT(*)
    FROM core.accounts AS a
    WHERE a.customer_id = c.customer_id
) > 2
LIMIT 100;


-- ============================================================
-- 14. EXISTS / NOT EXISTS
-- ============================================================

SELECT
    c.customer_id,
    c.customer_type
FROM core.customers AS c
WHERE EXISTS (
    SELECT 1
    FROM banking.loans AS l
    WHERE l.customer_id = c.customer_id
)
LIMIT 100;

SELECT
    c.customer_id,
    c.customer_type
FROM core.customers AS c
WHERE NOT EXISTS (
    SELECT 1
    FROM banking.cards AS ca
    WHERE ca.customer_id = c.customer_id
      AND ca.product_id IN ('P010', 'P011')
)
LIMIT 100;


-- ============================================================
-- 15. CTEs
-- WITH
-- ============================================================

WITH annual_branch_performance AS (
    SELECT
        bmp.branch_id,
        EXTRACT(YEAR FROM bmp.year_month)::INT AS year,
        SUM(bmp.total_revenue) AS annual_revenue,
        SUM(bmp.total_operating_cost) AS annual_operating_cost,
        SUM(bmp.net_income) AS annual_net_income
    FROM performance.branch_monthly_performance AS bmp
    GROUP BY
        bmp.branch_id,
        EXTRACT(YEAR FROM bmp.year_month)
)
SELECT
    abp.branch_id,
    abp.year,
    abp.annual_revenue,
    abp.annual_operating_cost,
    abp.annual_net_income
FROM annual_branch_performance AS abp
ORDER BY
    abp.year,
    abp.annual_net_income DESC;


-- ============================================================
-- 16. WINDOW FUNCTIONS
-- ============================================================

-- Window functions do calculations across related rows
-- without collapsing the detail rows.

-- 16.1 Rank branches by annual net income.
WITH annual_branch_income AS (
    SELECT
        bmp.branch_id,
        EXTRACT(YEAR FROM bmp.year_month)::INT AS year,
        SUM(bmp.net_income) AS annual_net_income
    FROM performance.branch_monthly_performance AS bmp
    GROUP BY
        bmp.branch_id,
        EXTRACT(YEAR FROM bmp.year_month)
)
SELECT
    abi.branch_id,
    abi.year,
    abi.annual_net_income,
    RANK() OVER (
        PARTITION BY abi.year
        ORDER BY abi.annual_net_income DESC
    ) AS income_rank
FROM annual_branch_income AS abi
ORDER BY
    abi.year,
    income_rank;

-- 16.2 Previous month with LAG.
SELECT
    bmp.year_month,
    bmp.net_income,
    LAG(bmp.net_income) OVER (
        ORDER BY bmp.year_month
    ) AS previous_month_net_income,
    bmp.net_income
        - LAG(bmp.net_income) OVER (ORDER BY bmp.year_month)
        AS monthly_change
FROM performance.bank_monthly_performance AS bmp
ORDER BY bmp.year_month;

-- 16.3 Next month with LEAD.
SELECT
    bmp.year_month,
    bmp.net_income,
    LEAD(bmp.net_income) OVER (
        ORDER BY bmp.year_month
    ) AS next_month_net_income
FROM performance.bank_monthly_performance AS bmp
ORDER BY bmp.year_month;

-- 16.4 Running total.
SELECT
    bmp.year_month,
    bmp.net_income,
    SUM(bmp.net_income) OVER (
        ORDER BY bmp.year_month
        ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
    ) AS cumulative_net_income
FROM performance.bank_monthly_performance AS bmp
ORDER BY bmp.year_month;

-- 16.5 Three-month moving average.
SELECT
    bmp.year_month,
    bmp.net_income,
    AVG(bmp.net_income) OVER (
        ORDER BY bmp.year_month
        ROWS BETWEEN 2 PRECEDING AND CURRENT ROW
    ) AS moving_avg_3m
FROM performance.bank_monthly_performance AS bmp
ORDER BY bmp.year_month;


-- ============================================================
-- 17. SET OPERATIONS
-- UNION / UNION ALL / INTERSECT / EXCEPT
-- ============================================================

-- UNION removes duplicates.
SELECT l.customer_id
FROM banking.loans AS l
UNION
SELECT ca.customer_id
FROM banking.cards AS ca;

-- UNION ALL keeps duplicates.
SELECT l.customer_id
FROM banking.loans AS l
UNION ALL
SELECT ca.customer_id
FROM banking.cards AS ca;

-- Customers appearing in both sets.
SELECT l.customer_id
FROM banking.loans AS l
INTERSECT
SELECT ca.customer_id
FROM banking.cards AS ca;

-- Loan customers who do not appear in cards.
SELECT l.customer_id
FROM banking.loans AS l
EXCEPT
SELECT ca.customer_id
FROM banking.cards AS ca;


-- ============================================================
-- 18. VIEWS / MATERIALIZED VIEWS
-- ============================================================

-- VIEW: stores the query definition.
-- TEMPLATE ONLY — run intentionally.
--
-- CREATE OR REPLACE VIEW performance.vw_branch_annual_performance AS
-- SELECT
--     bmp.branch_id,
--     EXTRACT(YEAR FROM bmp.year_month)::INT AS year,
--     SUM(bmp.total_revenue) AS annual_revenue,
--     SUM(bmp.total_operating_cost) AS annual_operating_cost,
--     SUM(bmp.net_income) AS annual_net_income
-- FROM performance.branch_monthly_performance AS bmp
-- GROUP BY
--     bmp.branch_id,
--     EXTRACT(YEAR FROM bmp.year_month);

-- MATERIALIZED VIEW: stores the result physically.
-- TEMPLATE ONLY — run intentionally.
--
-- CREATE MATERIALIZED VIEW performance.mv_branch_annual_performance AS
-- SELECT
--     bmp.branch_id,
--     EXTRACT(YEAR FROM bmp.year_month)::INT AS year,
--     SUM(bmp.total_revenue) AS annual_revenue,
--     SUM(bmp.net_income) AS annual_net_income
-- FROM performance.branch_monthly_performance AS bmp
-- GROUP BY
--     bmp.branch_id,
--     EXTRACT(YEAR FROM bmp.year_month);
--
-- REFRESH MATERIALIZED VIEW performance.mv_branch_annual_performance;


-- ============================================================
-- 19. CAST / TYPE CONVERSION
-- ============================================================

SELECT CAST(123.45 AS INTEGER) AS integer_value;

SELECT 123.45::INTEGER AS integer_value;

SELECT
    bmp.year_month,
    EXTRACT(YEAR FROM bmp.year_month)::INT AS year
FROM performance.bank_monthly_performance AS bmp
LIMIT 20;

SELECT
    l.loan_id,
    l.original_amount,
    l.original_amount::TEXT AS amount_as_text
FROM banking.loans AS l
LIMIT 20;


-- ============================================================
-- 20. INSERT / UPDATE / DELETE
-- RUN AS A BLOCK
-- ============================================================

-- This lab is completely isolated from canonical BTYT data.
-- If you reconnect to PostgreSQL, run the complete setup block again.

DROP TABLE IF EXISTS temp_sql_practice;

CREATE TEMP TABLE temp_sql_practice (
    id INTEGER,
    label TEXT,
    amount NUMERIC
) ON COMMIT PRESERVE ROWS;

INSERT INTO temp_sql_practice (id, label, amount)
VALUES
    (1, 'A', 100),
    (2, 'B', 200),
    (3, 'C', 300);

-- Check the initial rows.
SELECT *
FROM temp_sql_practice
ORDER BY id;

-- UPDATE changes existing rows.
UPDATE temp_sql_practice
SET amount = 250
WHERE id = 2;

-- DELETE removes rows.
DELETE FROM temp_sql_practice
WHERE id = 3;

-- Check the final rows.
SELECT *
FROM temp_sql_practice
ORDER BY id;


-- ============================================================
-- 21. CONSTRAINTS
-- PRIMARY KEY / FOREIGN KEY / CHECK / UNIQUE / NOT NULL
-- RUN AS A BLOCK
-- ============================================================

DROP TABLE IF EXISTS temp_constraint_practice;

CREATE TEMP TABLE temp_constraint_practice (
    id INTEGER PRIMARY KEY,
    code TEXT UNIQUE NOT NULL,
    amount NUMERIC CHECK (amount >= 0),
    status TEXT NOT NULL
) ON COMMIT PRESERVE ROWS;

-- Valid row: should work.
INSERT INTO temp_constraint_practice (id, code, amount, status)
VALUES (1, 'A001', 100, 'ACTIVE');

SELECT *
FROM temp_constraint_practice;

-- Examples below are intentionally COMMENTED OUT because they should fail:
--
-- Duplicate PRIMARY KEY:
-- INSERT INTO temp_constraint_practice VALUES (1, 'A002', 50, 'ACTIVE');
--
-- Duplicate UNIQUE code:
-- INSERT INTO temp_constraint_practice VALUES (2, 'A001', 50, 'ACTIVE');
--
-- Negative amount violates CHECK:
-- INSERT INTO temp_constraint_practice VALUES (3, 'A003', -10, 'ACTIVE');
--
-- NULL status violates NOT NULL:
-- INSERT INTO temp_constraint_practice VALUES (4, 'A004', 10, NULL);

-- BTYT foreign-key example:
-- core.accounts.customer_id -> core.customers.customer_id
--
-- Generic syntax:
-- ALTER TABLE child_table
-- ADD CONSTRAINT fk_example
-- FOREIGN KEY (customer_id)
-- REFERENCES parent_table(customer_id);


-- ============================================================
-- 22. INDEXES
-- RUN AS A BLOCK
-- ============================================================

-- Indexes can speed up searches and joins.
-- They consume storage and add write overhead.
-- The professional workflow is:
-- query -> EXPLAIN ANALYZE -> index if justified -> ANALYZE -> remeasure.

DROP TABLE IF EXISTS temp_customer_index_test;

CREATE TEMP TABLE temp_customer_index_test AS
SELECT
    c.customer_id,
    c.nationality,
    c.monthly_income
FROM core.customers AS c;

-- Give PostgreSQL fresh statistics for the temporary table.
ANALYZE temp_customer_index_test;

-- BEFORE INDEX.
EXPLAIN ANALYZE
SELECT *
FROM temp_customer_index_test
WHERE nationality = 'VENEZUELA';

-- Create the test index.
CREATE INDEX idx_temp_customer_nationality
ON temp_customer_index_test (nationality);

ANALYZE temp_customer_index_test;

-- AFTER INDEX.
EXPLAIN ANALYZE
SELECT *
FROM temp_customer_index_test
WHERE nationality = 'VENEZUELA';

-- Real BTYT syntax example — intentionally commented out:
-- CREATE INDEX idx_transactions_account_id
-- ON banking.transactions (account_id);
--
-- Do not create production indexes just because they appear in a cheatsheet.


-- ============================================================
-- 23. EXPLAIN / EXPLAIN ANALYZE
-- ============================================================

-- EXPLAIN shows the planned execution strategy.
EXPLAIN
SELECT
    a.account_id,
    a.customer_id
FROM core.accounts AS a
WHERE a.opening_year = 2022;

-- EXPLAIN ANALYZE actually runs the query and measures it.
EXPLAIN ANALYZE
SELECT
    a.account_id,
    a.customer_id
FROM core.accounts AS a
WHERE a.opening_year = 2022;

-- Concepts to learn:
-- Seq Scan / Index Scan / Hash Join / Nested Loop / Sort / Aggregate
-- estimated rows / actual rows / actual time


-- ============================================================
-- 24. TRANSACTIONS
-- BEGIN / COMMIT / ROLLBACK
-- RUN AS A BLOCK
-- ============================================================

-- This lab demonstrates that ROLLBACK undoes changes.
-- Run the complete block together in the same connection.

DROP TABLE IF EXISTS temp_transaction_practice;

CREATE TEMP TABLE temp_transaction_practice (
    id INTEGER PRIMARY KEY,
    amount NUMERIC
) ON COMMIT PRESERVE ROWS;

INSERT INTO temp_transaction_practice
VALUES
    (1, 100),
    (2, 200);

-- Initial state.
SELECT *
FROM temp_transaction_practice
ORDER BY id;

BEGIN;

UPDATE temp_transaction_practice
SET amount = 999
WHERE id = 1;

-- Inside the transaction, id=1 temporarily shows 999.
SELECT *
FROM temp_transaction_practice
ORDER BY id;

ROLLBACK;

-- After ROLLBACK, id=1 is back to 100.
SELECT *
FROM temp_transaction_practice
ORDER BY id;

-- COMMIT would keep the change instead:
--
-- BEGIN;
-- UPDATE temp_transaction_practice
-- SET amount = 999
-- WHERE id = 1;
-- COMMIT;


-- ============================================================
-- APPENDIX — KPI BRIDGE: COST-TO-INCOME RATIO
-- This is intentionally more advanced: use it as a bridge, not as a memorization exercise.
-- ============================================================

-- Business question:
-- How much of a branch's revenue is consumed by operating costs?
--
-- Formula:
-- Cost-to-Income (%) = Total Operating Cost / Total Revenue * 100
--
-- For an annual ratio:
-- sum annual costs and annual revenue FIRST,
-- then divide. Do not average the 12 monthly ratios.

SELECT
    bmp.branch_id,
    b.branch_name,
    EXTRACT(YEAR FROM bmp.year_month)::INT AS year,
    SUM(bmp.total_revenue) AS annual_revenue,
    SUM(bmp.total_operating_cost) AS annual_operating_cost,
    (
        SUM(bmp.total_operating_cost)
        / NULLIF(SUM(bmp.total_revenue), 0)
    ) * 100 AS cost_to_income_pct
FROM performance.branch_monthly_performance AS bmp
LEFT JOIN core.branches AS b
    ON bmp.branch_id = b.branch_id
GROUP BY
    bmp.branch_id,
    b.branch_name,
    EXTRACT(YEAR FROM bmp.year_month)
ORDER BY
    year,
    cost_to_income_pct ASC;


-- ============================================================
-- OPTIONAL TEMP-LAB CLEANUP
-- ============================================================

DROP TABLE IF EXISTS temp_sql_practice;
DROP TABLE IF EXISTS temp_constraint_practice;
DROP TABLE IF EXISTS temp_customer_index_test;
DROP TABLE IF EXISTS temp_transaction_practice;


-- ============================================================
-- STUDY ORDER
-- ============================================================
-- 01–03: basic querying and NULL handling
-- 04–07: transformations and aggregations
-- 08–11: joins
-- 12–15: subqueries, EXISTS, CTEs
-- 16–17: analytical SQL
-- 18–19: reusable structures and types
-- 20–24: writes, integrity, performance, transactions
--
-- Goal: understand the logic first.
-- Syntax becomes automatic with repetition.
-- ============================================================