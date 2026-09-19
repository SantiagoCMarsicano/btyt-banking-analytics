# 03 — Loans & Credit Quality Analytics

## Objective

Build a reusable analytical layer for BTYT's loan portfolio and credit-quality analysis without forcing every risk question into SQL.

The main question is:

> **How is BTYT's loan portfolio structured, how does credit quality evolve over time, and what reusable loan-level data should downstream analytics consume?**

This file should distinguish clearly between:

- origination structure;
- current exposure;
- payment behavior;
- delinquency;
- arrears;
- loan status;
- temporal deterioration.

The goal is not to precompute every credit-risk KPI in PostgreSQL. SQL should prepare stable, auditable loan-level datasets so that DAX and Python can answer dynamic or statistical questions at the appropriate layer.

---

## Scope

This analysis focuses on:

- loan portfolio composition;
- product and currency mix;
- origination cohorts;
- loan status;
- original amount;
- term;
- interest-rate structure;
- branch and regional distribution;
- customer type and customer segment;
- monthly outstanding balance;
- scheduled versus actual payment;
- days past due;
- delinquency status;
- arrears;
- current portfolio snapshot;
- first-level credit-quality diagnostics.

---

## Out of Scope

The following topics belong elsewhere:

- full customer relationship depth → `01_customers.sql`
- account balances and account product behavior → `02_products_accounts.sql`
- transaction behavior → `04_transactions.sql`
- branch profitability → `05_branches.sql`
- campaign effectiveness → `06_campaigns.sql`
- bank-wide profitability → `07_performance.sql`
- predictive default models / credit scoring → Part II

Part II may reuse outputs from this file, but this file must not introduce target leakage or prematurely build ML features.

---

## Critical Temporal Status Rule

`banking.loans.loan_status` is the current/final contractual status at the **2026-12-31 analytical cutoff**.

It is **not** a month-specific status.

Historical month-by-month credit quality must use:

- `banking.loan_monthly_snapshot.delinquency_status`;
- `days_past_due`;
- arrears and payment fields.

`DEFAULTED` and `RESTRUCTURED` are not automatically terminal/closed contracts. A loan is treated as open at cutoff when:

```text
closing_year IS NULL
```

The analytical bases therefore expose both:

```text
loan_status_at_cutoff
is_open_at_cutoff
```

---

## Main Tables

### Primary tables

- `banking.loans`
- `banking.loan_monthly_snapshot`

### Supporting tables

- `core.customers`
- `core.products`
- `core.branches`

### Later contextual joins

- `macro.macro_environment`
- `macro.external_shocks`

Macro joins should only be added once the time-grain relationship is explicit and validated.

---

## Key Analytical Grains

### Loan grain

> **1 row = 1 loan**

Used for:

- origination analysis;
- product mix;
- customer mix;
- branch mix;
- original amount;
- term;
- initial interest rate;
- loan status;
- closing year.

### Loan-month grain

> **1 row = 1 loan × 1 month**

Used for:

- outstanding balance;
- current interest rate;
- scheduled payment;
- actual payment;
- payment shortfall;
- days past due;
- delinquency status;
- arrears;
- credit-quality evolution.

### Latest-snapshot grain

> **1 row = 1 loan observed in the latest available month**

Used for:

- current outstanding exposure;
- current arrears;
- current delinquency;
- current DPD distribution;
- current portfolio monitoring.

These grains must not be mixed casually.

---

## Main Business Questions

### 1. Portfolio Structure

1. How many loans exist?
2. How are loans distributed by product?
3. How are loans distributed by retail versus business lending?
4. How are loans distributed by currency?
5. How are loans distributed by customer type?
6. How are loans distributed by branch and region?
7. Which products originate the largest original amounts?
8. Which products have the largest average ticket?
9. How do terms and initial rates differ across products?

---

### 2. Origination Over Time

10. How many loans are originated each year?
11. Which products drive origination growth?
12. How does origination differ by customer type?
13. How does origination differ by branch or region?
14. How has the UYU/USD mix changed over time?
15. Have average original amounts changed over time?
16. Have average initial rates changed over time?

---

### 3. Loan Cohorts

17. How large is each origination cohort?
18. What is the current status composition of each cohort?
19. Which products show different status patterns across cohorts?
20. Do older cohorts contain more paid-off, defaulted or written-off loans?
21. Are newer cohorts structurally different in amount, term or rate?

Cohort analysis should be interpreted carefully because older cohorts have had more time to reach terminal states.

---

### 4. Current Exposure

22. What is the latest available loan snapshot?
23. What is the current outstanding balance by product?
24. What is the current outstanding balance by currency?
25. Which branches or regions hold the largest current exposure?
26. Which customer types hold the largest current exposure?
27. Which products have high original volumes but relatively small remaining balances?
28. Which products have relatively high current balances per loan?

Native loan monetary values must remain separated by currency unless an explicit FX conversion is introduced. The `performance` schema is different because its reporting measures are already UYU-equivalent.

---

### 5. Delinquency and DPD

29. What share of current loans has `days_past_due > 0`?
30. How is the portfolio distributed across DPD buckets?
31. Which products concentrate delinquent loans?
32. Which products concentrate delinquent outstanding balance?
33. Which branches or regions concentrate higher DPD?
34. Does delinquency differ between individuals and businesses?
35. How does delinquency differ by customer segment?
36. Which origination cohorts show higher current delinquency?

Dynamic delinquency ratios should generally be calculated in DAX from the reusable loan-month dataset.

---

### 6. Arrears and Payment Behavior

37. What is the current arrears balance?
38. Which products concentrate arrears?
39. How large is the gap between scheduled and actual payments?
40. Which segments show larger payment shortfalls?
41. How does payment performance evolve before serious delinquency?
42. Are payment shortfalls persistent or temporary?

The longitudinal questions in this section are especially suitable for Python.

---

### 7. Credit-Quality Evolution

43. How does total outstanding balance evolve over time?
44. How does delinquent outstanding balance evolve over time?
45. How does arrears balance evolve over time?
46. How does the DPD distribution change over time?
47. Which products deteriorate or recover more quickly?
48. Which branches show persistent deterioration?
49. Are there periods with simultaneous deterioration across many segments?

---

### 8. Loan Status

50. How are loans distributed across `ACTIVE`, `PAID_OFF`, `DEFAULTED`, `RESTRUCTURED` and `WRITTEN_OFF`?
51. How does status composition differ by product?
52. How does status composition differ by cohort?
53. How does status composition differ by customer type?
54. How does status composition differ by branch or region?

`loan_status` is a cutoff contractual attribute and must not be treated as monthly delinquency. Monthly risk history belongs to `loan_monthly_snapshot.delinquency_status` and DPD. `DEFAULTED` / `RESTRUCTURED` may still be open when `closing_year IS NULL`.

---

### 9. Interest Rates

55. How do initial interest rates vary by product?
56. How do current rates differ from initial rates?
57. How do rates evolve over time for variable-rate loans?
58. Do delinquent loans show different rate patterns?
59. How do rates differ by currency?

Rate analysis should remain descriptive in Part I unless a stronger causal question is explicitly defined.

---

### 10. Controlled segment comparison — SME Loan

A particularly useful BTYT business question is:

> **How does the same `SME Loan` product behave for `SMALL` versus `MEDIUM` businesses?**

Because product is held constant, the comparison can focus more cleanly on:

- loan count;
- original amount;
- term;
- initial/current rates;
- current outstanding balance;
- DPD;
- arrears;
- 30+ / 90+ delinquency;
- origination cohorts.

This is more analytically meaningful than comparing arbitrary combinations of unrelated products and customer groups.

### 11. Branch and Regional Credit Profile

60. Which branches originate the most loans?
61. Which branches hold the largest outstanding balance?
62. Which branches concentrate arrears?
63. Which branches show higher DPD?
64. Are branch differences driven by product mix?
65. Are regional differences persistent over time?

Profitability remains outside this file.

---

## Temporal Variables

Time is central to loan analysis.

Main temporal fields include:

- `banking.loans.origination_year`
- `banking.loans.closing_year`
- `banking.loan_monthly_snapshot.year_month`

These support two distinct temporal views.

### Annual origination lifecycle

Use:

- origination year;
- closing year;
- cohorts;
- product mix;
- currency mix;
- customer mix.

### Monthly credit-quality lifecycle

Use:

- outstanding balance;
- current rate;
- payment performance;
- days past due;
- delinquency status;
- arrears.

The monthly snapshot is the main source for credit-quality evolution.

---

## DPD Buckets

The canonical audited DPD classification is:

```text
CURRENT       → days_past_due = 0
DPD_1_30      → 1–30
DPD_31_60     → 31–60
DPD_61_90     → 61–90
DPD_90_PLUS   → > 90
UNKNOWN       → NULL
```

These are descriptive analytical buckets, not a claim that they reproduce a specific regulatory classification.

The monthly `delinquency_status` remains available alongside the bucket.
## SQL vs DAX vs Python Boundary

### SQL

SQL should own:

- loan-level joins;
- loan-month joins;
- reusable dimensional fields;
- origination cohorts;
- current snapshot extraction;
- DPD buckets;
- payment-gap variables;
- stable customer / product / branch attributes;
- coverage and consistency diagnostics.

### DAX / Power BI

DAX should own dynamic measures such as:

- Loan Count;
- Outstanding Balance;
- Average Outstanding Balance;
- Delinquent Loan Count;
- Delinquent Loan %;
- Delinquent Balance;
- Delinquent Balance %;
- 30+ DPD Balance;
- 90+ DPD Balance;
- Arrears Balance;
- Average DPD;
- Average Interest Rate;
- Payment Shortfall;
- Portfolio Share %;
- YoY Origination Growth.

These measures should react to:

- date;
- product;
- currency;
- customer type;
- customer segment;
- branch;
- region;
- status;
- DPD bucket.

### Python / Pandas / Jupyter

Python is the preferred tool for:

- DPD distributions;
- outlier analysis;
- delinquency trajectories;
- pre-default behavior;
- roll-rate / transition analysis;
- recovery paths;
- payment-shortfall persistence;
- vintage curves;
- correlations;
- statistical comparisons;
- exploratory regressions.

Python should not be created merely for symmetry with SQL.

---

## Part II Boundary

Part II may later reuse the loan-month analytical base for credit scoring and default modeling.

However:

- the target must be defined separately;
- observation and performance windows must be explicit;
- temporal train/test splitting must be used;
- post-default information must not leak into features;
- current status must not be used as a predictor of its own future target.

Part I prepares the analytical history; Part II defines the predictive problem.

---

## Expected Outputs

By the end of `03_loans.sql`, the project should have:

1. a clear loan portfolio structure;
2. a reusable one-row-per-loan analytical base;
3. a reusable one-row-per-loan-month analytical base;
4. a latest-snapshot current portfolio base;
5. cohort and temporal diagnostics;
6. transparent DPD and payment-behavior fields;
7. clean handoff points to Power BI and Python.

The file should not contain dozens of pre-aggregated combinations that DAX can calculate dynamically.

---

## Analytical Boundary

This file should answer:

> **What is in BTYT's loan portfolio, how does its credit quality evolve, and what clean analytical grains should downstream tools use?**

It should not attempt to answer:

> **Which customers are most valuable overall?**

That belongs to customer/performance analysis.

It should not attempt to answer:

> **Which borrower will default in the future?**

That belongs to Part II.
