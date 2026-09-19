# 05 — Branch Network & Branch Performance Analytics

## Objective

Build a reusable analytical framework for BTYT's physical branch network and branch-level business performance.

The main question is:

> **How is BTYT's branch network structured, how does each branch serve customers and products, and how does branch-level activity and financial performance evolve over time?**

This file should connect three distinct perspectives:

1. **network structure** — where branches are, what type they are, and how the network evolved;
2. **commercial footprint** — customers, accounts and loans associated with each branch;
3. **branch performance** — activity, deposits, lending, revenue, costs and net income over time.

The objective is not to reproduce every possible branch KPI in SQL. PostgreSQL should provide stable branch-level analytical grains; DAX and Power BI should calculate dynamic comparative measures.

---

## Scope

This analysis focuses on:

- branch inventory;
- branch type and size;
- branch status;
- opening and closing timeline;
- parent / child branch relationships;
- department, locality and region;
- customer concentration by primary branch;
- account concentration by branch;
- loan concentration by branch;
- branch-level transaction activity;
- average deposits;
- average loan balance;
- revenue;
- operating costs;
- credit losses;
- pre-provision profit;
- net income;
- branch growth over time;
- branch efficiency and productivity;
- comparison across regions, branch types and branch sizes.

---

## Out of Scope

The following topics belong elsewhere:

- customer demographics and relationship depth → `01_customers.sql`
- product/account portfolio behavior → `02_products_accounts.sql`
- loan delinquency and DPD → `03_loans.sql`
- transaction-channel behavior → `04_transactions.sql`
- campaign effectiveness → `06_campaigns.sql`
- consolidated bank-wide management performance → `07_performance.sql`

This file may use branch-level profitability measures, but it should not replace the bank-wide performance framework in `07_performance.sql`.

---

## Main Tables

### Primary tables

- `core.branches`
- `performance.branch_monthly_performance`

### Supporting tables

- `core.customers`
- `core.accounts`
- `banking.loans`

### Transaction activity

Prefer reusing the branch-month transaction aggregate designed in `04_transactions.sql`.

Avoid repeatedly scanning the full `banking.transactions` table from this file unless a specific diagnostic requires it.

---

## Canonical Performance Semantics

`performance.branch_monthly_performance` is additive across branches for a **given month** and is designed to reconcile to `performance.bank_monthly_performance`.

### Monthly active customers

This is not `core.customers.customer_status`.

In the performance engine, a represented customer is assigned to one relationship branch for the month — the branch carrying that customer's largest average deposits.

### Monthly active accounts

This means accounts represented in the monthly balance layer.

It is not simply `core.accounts.account_status = 'ACTIVE'` at the 2026 cutoff.

### Transaction measures

```text
transaction_count / transaction_volume
→ COMPLETED activity attributed to the account relationship branch

branch_transaction_count
→ COMPLETED BRANCH-channel events
```

### Reporting currency

Performance monetary fields are **UYU-equivalent reporting values**.

This is why deposits, loans, revenue, costs and profit can be aggregated across branches inside the performance layer.

### Stocks vs flows

Semi-additive / monthly stock measures:

- active customers;
- active accounts;
- average deposits;
- average loan balance.

Additive flows:

- transaction count / volume;
- revenue;
- costs;
- credit loss;
- pre-provision profit;
- net income.

Do not sum monthly stocks across time without an explicit rule.

---

## Key Analytical Grains

### Branch grain

`core.branches.status` is a master/cutoff attribute. It must not be presented as the historical status of the branch in every performance month.

> **1 row = 1 branch**

Used for:

- network structure;
- geography;
- branch type;
- branch size;
- opening / closing history;
- current branch status;
- parent branch relationships.

---

### Branch-month grain

> **1 row = 1 branch × 1 month**

Source:

- `performance.branch_monthly_performance`

Used for:

- deposits;
- loan balances;
- customers;
- accounts;
- transaction activity;
- revenue;
- costs;
- credit losses;
- profit;
- time-series performance.

This is the principal reusable branch-performance layer for Power BI.

---

### Branch-commercial snapshot grain

> **1 row = 1 branch**

Used for:

- current customer count;
- current account count;
- open-loan count at cutoff (`closing_year IS NULL`);
- customer/account/loan mix;
- branch footprint comparison.

This is a structural snapshot, not a monthly performance table.

---

## Main Business Questions

### 1. Network Structure

1. How many branches does BTYT have?
2. How are branches distributed by region?
3. How are they distributed by department and locality?
4. How many are branches versus agencies?
5. How are branches distributed by size?
6. Which branches are open or closed?
7. How has the network expanded over time?
8. Which branches act as parent branches for smaller offices?
9. Are some regions served mainly by small branches or agencies?

---

### 2. Commercial Footprint

10. Which branches have the largest primary customer base?
11. Which branches hold the most active accounts?
12. Which branches originate or manage the most loans?
13. Does branch size correspond to customer scale?
14. Do some small branches serve unusually large customer bases?
15. Which branches are more retail-oriented?
16. Which branches are more business-oriented?
17. Does customer/product mix differ by region?

---

### 3. Branch Activity

18. Which branches process the most transactions?
19. Which branches process the highest transaction value?
20. How does branch-linked transaction activity evolve over time?
21. Which branches show declining physical activity?
22. Does branch transaction activity track customer-base growth?
23. Are some branches relatively inactive given their customer base?

Transaction-channel detail remains in `04_transactions.sql`.

---

### 4. Deposits and Lending

24. Which branches hold the largest average deposits?
25. Which branches hold the largest average loan balances?
26. How do deposits evolve over time by branch?
27. How does lending evolve over time by branch?
28. Which branches are more deposit-heavy?
29. Which branches are more lending-heavy?
30. How does the deposit/loan mix vary by region?

The exact interpretation of management-performance monetary fields should follow the generated `performance` table semantics.

---

### 5. Revenue and Costs

31. Which branches generate the most total revenue?
32. Which generate the most net interest income?
33. Which generate the most fee income?
34. Which branches have the highest personnel cost?
35. Which have the highest fixed and variable costs?
36. How do operating costs evolve over time?
37. Are high-revenue branches also high-cost branches?

---

### 6. Profitability

38. Which branches generate the highest net income?
39. Which branches generate persistent losses?
40. How does pre-provision profit differ from final net income?
41. Which branches are most affected by credit losses?
42. How does profitability evolve over time?
43. Are profitability patterns persistent or temporary?
44. Do branch types and sizes show different profitability profiles?

Dynamic profitability rankings should be handled in Power BI / DAX rather than hardcoded permanently in SQL.

---

### 7. Efficiency

45. Which branches generate more revenue per active customer?
46. Which branches generate more revenue per active account?
47. Which branches have lower cost-to-income ratios?
48. Which branches generate more net income per customer?
49. Do larger branches actually operate more efficiently?
50. Are some small branches highly productive relative to their scale?

These ratios are especially suitable for DAX because they should respond to date, region, branch type and branch size filters.

---

### 8. Growth

51. Which branches are growing their active customer base?
52. Which branches are growing deposits?
53. Which branches are growing loan balances?
54. Which branches are growing revenue?
55. Which branches are improving or deteriorating in net income?
56. Are growth patterns different across regions?
57. Are newer branches still scaling faster than mature branches?

---

### 9. Branch Type and Size Comparison

58. How do large, medium and small branches differ?
59. How do branches and agencies differ?
60. Do branch types have different cost structures?
61. Do branch sizes have different profitability patterns?
62. Are smaller units more digitally oriented or less transaction-intensive?
63. Are certain branch types concentrated in specific regions?

---

### 10. Geography

64. Which regions contribute most to customers, deposits, loans and revenue?
65. How does branch profitability vary geographically?
66. Are some regions more expensive to serve?
67. Are there regional differences in branch productivity?
68. Does network density correspond to business volume?
69. Are some departments potentially over- or under-represented in the branch network?

The file should describe evidence in the realized BTYT world; it should not infer real-world branch strategy without additional external data.

---

### 11. Branch Lifecycle

70. How do branch performance profiles change with branch age?
71. Do newer branches require time to reach stable profitability?
72. How do branches behave before closure?
73. Are closures preceded by declining customers, activity or profit?
74. Do parent branches absorb activity from closed or smaller units?

Because the canonical world may contain no closed branches, some lifecycle questions may remain analytical possibilities rather than populated results.

---

## Temporal Variables

Main temporal fields include:

- `core.branches.opening_year`
- `core.branches.closing_year`
- `performance.branch_monthly_performance.year_month`

These support two distinct views.

### Network lifecycle

Use:

- opening year;
- closing year;
- status;
- branch age;
- expansion waves.

### Monthly branch performance

Use:

- active customers;
- active accounts;
- deposits;
- loan balance;
- transaction activity;
- revenue;
- costs;
- credit loss;
- net income.

---

## SQL vs DAX vs Python Boundary

### SQL

SQL should own:

- branch dimension joins;
- branch hierarchy;
- current commercial footprint;
- branch-month performance base;
- stable branch attributes;
- branch-age fields;
- structural diagnostics;
- reusable branch-level datasets.

SQL should not precompute every profitability or efficiency ratio by every possible filter combination.

---

### DAX / Power BI

DAX should own dynamic measures such as:

- Active Customers;
- Active Accounts;
- Average Deposits;
- Average Loan Balance;
- Transaction Count;
- Transaction Volume;
- Total Revenue;
- Operating Cost;
- Credit Loss;
- Net Income;
- Revenue per Customer;
- Revenue per Account;
- Net Income per Customer;
- Cost-to-Income;
- Deposit per Customer;
- Loan Balance per Customer;
- YoY Revenue Growth;
- YoY Net Income Growth;
- Branch Share of Revenue;
- Branch Share of Customers.

These measures should react to:

- month/year;
- branch;
- branch type;
- branch size;
- region;
- department;
- branch status.

---

### Python / Pandas / Jupyter

Python may be useful for:

- branch-performance distributions;
- outlier branches;
- clustering branches by business profile;
- trajectory analysis;
- correlation between scale and profitability;
- branch lifecycle analysis;
- exploratory efficiency benchmarking.

Python is not required merely because a branch topic exists.

---

### Tableau

Tableau is especially suitable for:

- branch geography;
- maps;
- regional network storytelling;
- branch size/type overlays;
- spatial comparison of business volume and performance.

This is one of the strongest Tableau use cases in Part I.

---

## Recommended SQL Analytical Objects

### 1. Branch dimension

Recommended grain:

```text
1 row = 1 branch
```

Include:

- branch identity;
- branch type;
- branch size;
- branch status;
- opening / closing years;
- branch age;
- parent branch;
- department;
- locality;
- region;
- latitude;
- longitude.

---

### 2. Branch commercial snapshot

Recommended grain:

```text
1 row = 1 branch
```

Include:

- current primary customers;
- active accounts;
- loan count;
- customer type mix;
- basic structural scale indicators.

Do not mix this current snapshot with historical monthly metrics without making the time reference explicit.

---

### 3. Branch-month performance base

Recommended grain:

```text
1 row = 1 branch × 1 month
```

Use:

- `performance.branch_monthly_performance`;
- joined branch metadata.

This should be the main Power BI branch source.

---

## Performance Considerations

The main branch-performance table is already aggregated monthly, so it is much lighter than raw transactions.

Therefore:

- prefer `performance.branch_monthly_performance` for branch time series;
- reuse `04_transactions` branch aggregates for detailed transaction-channel analysis;
- avoid rescanning `banking.transactions` from `05` unless necessary;
- create persistent branch views only if multiple downstream tools reuse them;
- use `EXPLAIN` / `EXPLAIN ANALYZE` for heavier structural joins if needed.

---

## Data-Quality Checks

Before analytical use, verify:

- branch IDs are unique;
- parent branch IDs refer to valid branches;
- parent branch is not the branch itself;
- opening year precedes closing year where applicable;
- open branches do not have contradictory closing years;
- closed branches have coherent closure metadata;
- latitude and longitude are populated where expected;
- branch-month performance references valid branch IDs;
- monthly branch totals reconcile structurally with consolidated performance; the canonical full reconciliation is maintained in `07_performance.sql`;
- branch-month grain is unique;
- performance coverage is consistent across branches.

---

## Expected Outputs

By the end of `05_branches.sql`, the project should have:

1. a reusable branch dimension;
2. a current commercial-footprint snapshot;
3. a reusable branch-month performance base;
4. a compact network-expansion diagnostic;
5. branch hierarchy and geography diagnostics;
6. clean handoff to Power BI / DAX;
7. clean handoff to Tableau;
8. no unnecessary rescan of the full transaction table.

---

## Analytical Boundary

This file should answer:

> **How is BTYT's physical network structured, how much business does each branch serve, and how does branch-level performance evolve over time?**

It should not attempt to answer:

> **How is the bank performing as a whole?**

That belongs to `07_performance.sql`.

It should not attempt to answer:

> **Which channel do customers prefer across all transactions?**

That belongs to `04_transactions.sql`.
