# 00 — Structural Context

## Objective

Build a reusable structural census of the BTYT banking universe before moving into thematic analysis, KPIs, profitability, credit risk, customer behavior, campaigns or macroeconomic interpretation.

The purpose of this stage is to answer a simple question:

> **What bank do we have?**

This file establishes the baseline composition, scope and temporal coverage of the database so that later analytical work starts from a clear understanding of the underlying banking universe.

---


## Final-model context

This document refers to the frozen seven-schema PostgreSQL model:

```text
core
banking
marketing
reference
market
macro
performance
```

The structural layer contains 23 tables. `00_structural_context.sql` is intentionally descriptive: its job is to establish what exists in the realized BTYT world before deeper analytical interpretation begins.

Important rule: status fields shown here are generally **master / cutoff attributes**. Historical monthly behavior belongs to the appropriate snapshot or performance table rather than being reconstructed from the current master status.

---

## Scope

The structural analysis focuses on:

- branch network composition
- customer base composition
- product catalog
- accounts, cards and loans
- transaction categories and coverage
- monthly balances and loan snapshots
- campaign structure
- market and external financial institutions
- macroeconomic coverage
- external shocks
- bank and branch performance coverage
- structural consistency checks

This file is intentionally descriptive.

It includes:

- counts
- shares
- category distributions
- broad cross-tabulations
- temporal coverage
- first-level consistency checks

It does **not** attempt to explain why performance differs across segments, branches or products.

---

## Out of Scope

The following topics are intentionally deferred to thematic SQL files:

- branch profitability and efficiency
- customer segmentation and relationship depth
- detailed product behavior
- credit quality and delinquency
- transaction behavior and digital adoption
- campaign effectiveness
- macroeconomic relationships
- advanced customer-level behavioral analysis
- KPI construction
- performance optimization and indexing

The structural file should remain a census and analytical map, not become the full analytical project.

---

## Main Business Questions

### Branch network

1. How many branches exist?
2. How are branches distributed by status, region, department, type and size?
3. Which branches have parent branches?
4. How did the network expand over time?
5. Which branches closed, when and why?
6. Are branch status and closing-year fields structurally consistent?

### Customers

7. How many customers exist?
8. What share are individuals versus businesses?
9. How are customers distributed by status?
10. How do customer status patterns differ between individuals and businesses?
11. How are customers distributed geographically?
12. What is the demographic profile of individual customers?
13. How are individual customers distributed by age, gender, employment and income?
14. How are business customers distributed by company size and sector?
15. How has customer registration evolved over time?
16. Are customer status and closing-year fields structurally consistent?

### Products and accounts

17. What product families exist?
18. Which customer types and currencies are targeted by the product catalog?
19. How many accounts exist?
20. How are accounts distributed by status, product, branch and opening channel?
21. How have account openings and closures evolved over time?
22. Are account status and closing-year fields structurally consistent?

### Cards

23. How many cards exist?
24. How are cards distributed by product and status?
25. Through which channels are cards issued?
26. How has card issuance evolved over time?

### Loans

27. How many loans exist?
28. How are loans distributed by status?
29. Which lending products concentrate the largest number of loans?
30. Which lending products concentrate the largest originated amounts?
31. What is the average ticket by lending product?
32. How are loans distributed across branches, currencies and origination years?

### Transactions and time coverage

33. How many transactions exist?
34. What is the transaction date coverage?
35. Which transaction types, channels and statuses exist?
36. What broad transaction-type × channel combinations exist?

### Monthly banking snapshots

37. What period is covered by account balances?
38. What period is covered by loan monthly snapshots?
39. How many monthly observations exist?

### Marketing

40. How many campaigns exist?
41. What campaign types are represented?
42. Which customer types are targeted?
43. Which channels and geography levels are available?
44. What period is covered by campaign activity?

### Market and institutions

45. How many banks exist in the simulated market?
46. How are banks distributed by type, scope, status and operating country?
47. What types of external financial institutions exist?
48. What is the domestic versus foreign institution mix?

### Macro and performance coverage

49. What years are covered by the macro environment?
50. What external shocks exist, what scope do they have and when do they occur?
51. What period is covered by bank monthly performance?
52. What period and branch coverage exist in branch monthly performance?

---

## Main Tables

### Core

- `core.branches`
- `core.customers`
- `core.products`
- `core.accounts`

### Banking

- `banking.cards`
- `banking.loans`
- `banking.transactions`
- `banking.account_balances`
- `banking.loan_monthly_snapshot`

### Marketing

- `marketing.campaigns`
- `reference.campaign_channels`
- `reference.campaign_geography`

### Market

- `market.banks`
- `market.financial_institutions`

### Macro

- `macro.macro_environment`
- `macro.external_shocks`

### Performance

- `performance.bank_monthly_performance`
- `performance.branch_monthly_performance`

---

## Analytical Sequence

The structural SQL file follows this order:

1. Connection check
2. Branch network
3. Customer base
4. Product catalog
5. Accounts
6. Cards
7. Loans
8. Transactions and time coverage
9. Monthly balance and loan snapshot coverage
10. Marketing structure
11. Market and external institutions
12. Macro and performance coverage
13. Compact structural summary
14. Structural interpretation checklist

This order moves from the bank's physical and customer structure toward operational, market and performance coverage.

---

## SQL Concepts Used

The structural file also serves as a practical SQL learning exercise.

Main concepts used include:

- `SELECT`
- `FROM`
- `WHERE`
- `GROUP BY`
- `ORDER BY`
- `COUNT`
- `SUM`
- `AVG`
- `MIN`
- `MAX`
- `ROUND`
- `DISTINCT`
- `COUNT(DISTINCT ...)`
- `CASE WHEN`
- `COALESCE`
- `NULLIF`
- `IS NULL`
- `IS NOT NULL`
- `IN`
- `BETWEEN`
- `FILTER`
- `JOIN`
- `LEFT JOIN`
- self joins
- CTEs with `WITH`
- window functions with `OVER()`
- `PARTITION BY`
- percentiles with `PERCENTILE_CONT`
- scalar subqueries
- type casting with `::TEXT`

The file is intended to be run one statement at a time so that each construction can be inspected and understood independently.

---

## Structural Interpretation Rules

### Structural NULLs

A NULL value is not automatically a data-quality problem.

Before labeling a NULL as incorrect, check whether it is structurally explained by the business model.

Examples include:

- nationality for business customers
- closing year for active entities
- closure reason for entities that were never closed

### Consistency checks

Structural consistency queries are used to identify combinations that may contradict the model.

Examples:

- branch marked `OPEN` with a non-null closing year
- branch marked `CLOSED` with a null closing year
- active customer with a closing year
- closed account without a closing year

These checks are diagnostic and should not modify canonical data.

### Large tables

`banking.transactions` is the largest table in BTYT.

Queries over the full transaction table should be treated carefully because they may require large scans.

Performance optimization, indexes and `EXPLAIN ANALYZE` belong to a later phase.

---

## Analytical Boundary

This file intentionally stops at:

- census
- composition
- broad shares
- category distributions
- temporal coverage
- first-level cross-tabs
- structural consistency

If a question starts asking:

- why a segment performs better
- which branch is more profitable
- where risk is concentrated
- which channel behaves better
- which segment has higher relationship depth
- what explains customer behavior

then the question belongs in a thematic SQL file.

---

## Expected Output

By the end of the structural stage, the analyst should be able to explain:

- how the branch network is composed
- how the customer base is structured
- what products exist
- how accounts, cards and loans are distributed
- what period the operational data covers
- what campaign, market and macro dimensions are available
- what performance coverage exists
- which structural fields require special interpretation

The file should also provide a reusable baseline that can be rerun whenever the database is regenerated.

---

## Next Analytical Files

After the structural census, the project moves into thematic analysis:

1. `01_customers.sql`
2. `02_products_accounts.sql`
3. `03_loans.sql`
4. `04_transactions.sql`
5. `05_branches.sql`
6. `06_campaigns.sql`
7. `07_performance.sql`

The transition is:

> **00 — What bank do we have?**

to:

> **01–07 — How does that bank behave and perform?**
