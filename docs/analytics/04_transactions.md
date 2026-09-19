# 04 — Transactions & Channels Analytics

## Objective

Build a scalable analytical framework for BTYT's transaction activity without forcing the full transaction event table into every downstream tool.

The main question is:

> **How do BTYT customers move money, through which channels, with what volume and value, and how does transaction behavior evolve over time?**

This file must respect the scale of the transaction engine. The transaction table is one of the largest objects in the project, so the analytical design should distinguish carefully between:

- raw transaction events;
- reusable monthly aggregates;
- branch/channel activity;
- transfer counterparties;
- failures and exceptions;
- downstream BI consumption.

The objective is not to create one SQL query for every possible transaction slice. SQL should prepare efficient analytical grains; DAX, Power BI, Superset and Python should consume those grains according to their strengths.

---

## Scope

This analysis focuses on:

- transaction count;
- transaction value;
- transaction type;
- direction;
- channel;
- transaction status;
- transfer scope;
- counterparty type;
- counterparty institution;
- transaction branch;
- merchant category;
- failure reason;
- monthly and yearly evolution;
- digital versus branch activity;
- domestic versus external transfer patterns;
- transaction intensity at account level;
- operational failures.

---

## Out of Scope

The following topics belong elsewhere:

- customer demographics and relationship depth → `01_customers.sql`
- account balances and product structure → `02_products_accounts.sql`
- loan quality and delinquency → `03_loans.sql`
- branch profitability → `05_branches.sql`
- campaign response → `06_campaigns.sql`
- bank-wide profitability → `07_performance.sql`
- fraud detection / anomaly models → possible later extension, not Part I core

Transactions may support those analyses, but this file should remain centered on payment and money-movement behavior.

---

## Main Tables

### Primary table

- `banking.transactions`

### Supporting tables

- `core.accounts`
- `core.customers`
- `core.products`
- `core.branches`
- `market.financial_institutions`
- `market.banks`

The counterparty path is intentionally:

```text
banking.transactions.counterparty_institution_id
        ↓
market.financial_institutions.institution_id
        ↓
market.banks.bank_id
```

This should not be replaced with a direct transaction-to-bank relationship because counterparties may include non-bank institutions.

---

## Canonical Transaction Semantics

### Attempts vs completed money movement

The audited transaction layer separates operational attempts from realized economic activity.

```text
COMPLETED
→ transaction executed
→ realized money movement

FAILED
→ transaction attempted but did not execute
→ operational event, not realized money movement
```

Therefore:

```text
Attempted Transaction Count
= COMPLETED + FAILED attempts

Financial Transaction Volume
= COMPLETED amounts only

Failure Rate
= FAILED attempts / all attempts
```

Failed attempted amounts may be analyzed operationally but must not be mixed into realized transaction volume.

### Currency

`banking.transactions` has no direct currency column.

Currency is inherited through:

```text
transactions.account_id
→ core.accounts.product_id
→ core.products.currency
```

UYU and USD transaction values remain separate unless explicit FX conversion is applied.

### Canonical channel grouping

```text
DIGITAL   = MOBILE + WEB
PHYSICAL  = BRANCH + ATM
AUTOMATED = AUTOMATIC
MERCHANT  = POS
OTHER     = future / unmapped value
```

Detailed channel values remain available.

### Physical branch activity

The performance-compatible physical branch definition is:

```text
transaction_status = 'COMPLETED'
channel = 'BRANCH'
transaction_branch_id IS NOT NULL
```

### Counterparty chain

```text
banking.transactions.counterparty_institution_id
→ market.financial_institutions.institution_id
→ market.banks.bank_id
```

Do not replace this with a direct transaction-to-bank relationship because counterparties may include non-bank institutions.

### Merchant category

`merchant_category` is nullable and transaction-dependent. Analyze it only where populated; a NULL may be structurally valid rather than a data-quality failure.

---

## Scale Consideration

`banking.transactions` contains tens of millions of rows in the canonical BTYT world.

Therefore:

> **Do not treat the full transaction event table as the default Power BI import table.**

The preferred architecture is:

```text
banking.transactions
        ↓
PostgreSQL analytical aggregation
        ↓
smaller reusable transaction datasets
        ↓
Power BI / DAX / Superset / Python
```

The raw event table remains valuable for:

- SQL exploration;
- detailed forensic queries;
- operational checks;
- Superset or direct database analysis;
- Python samples / targeted extracts.

But broad BI reporting should generally consume a reduced analytical grain.

---

## Key Analytical Grains

### Transaction-event grain

> **1 row = 1 transaction**

Source:

- `banking.transactions`

Use for:

- exact event-level investigation;
- failures;
- specific transfers;
- merchant/category diagnostics;
- detailed channel behavior;
- targeted Python extracts.

This grain is too large to be the default BI import layer.

---

### Account-month transaction grain

> **1 row = 1 account × 1 month × selected transaction dimensions**

Recommended dimensions:

- transaction type;
- direction;
- channel;
- transaction status;
- transfer scope where applicable.

Recommended measures:

- transaction count;
- transaction amount;
- average transaction amount;
- failed transaction count.

This is the principal reusable transaction layer for Power BI.

---

### Branch-month transaction grain

> **1 row = 1 branch × 1 month**

Use for:

- branch activity;
- branch transaction counts;
- branch transaction value;
- branch-channel mix;
- physical-network usage.

Detailed profitability remains in `05_branches.sql` / `07_performance.sql`.

---

### Counterparty-month transfer grain

> **1 row = 1 counterparty institution × 1 month × direction**

Use for:

- external transfers;
- domestic versus international transfers;
- bank counterparties;
- concentration of outgoing/incoming transfer flows.

This should only include transaction types for which counterparty institution is meaningful.

---

## Main Business Questions

### 1. Transaction Activity

1. How many transactions does BTYT process?
2. What is the total transaction value?
3. What is the average transaction amount?
4. How does transaction activity evolve by month and year?
5. Are there periods with unusually high or low activity?
6. Does transaction count grow at the same rate as transaction value?

### 2. Transaction Type

7. Which transaction types dominate by count?
8. Which transaction types dominate by value?
9. Are high-frequency transaction types also high-value?
10. How has the transaction-type mix evolved over time?
11. Which products/accounts generate each transaction type?
12. Are some transaction types strongly associated with individuals or businesses?

### 3. Direction

13. What is the mix between incoming and outgoing transactions?
14. How do incoming and outgoing values evolve over time?
15. Which transaction types are primarily inbound?
16. Which are primarily outbound?
17. Does direction differ by customer type or product?

Direction should not be interpreted as equivalent to account-level net cash flow without considering the transaction definition and account-balance logic.

### 4. Channel Mix

18. Which channels dominate transaction count?
19. Which channels dominate transaction value?
20. How has digital-channel adoption evolved over time?
21. Has branch usage declined relative to digital channels?
22. Which transaction types are most associated with each channel?
23. Does channel usage differ between individuals and businesses?
24. Does channel usage differ by region?
25. Are higher-value transactions concentrated in specific channels?

This is one of the most important BI themes in the project.

### 5. Digitalization

26. What share of transactions occurs through digital channels?
27. What share of transaction value occurs through digital channels?
28. How has digital share changed over time?
29. Which customer segments are most digital?
30. Which regions show stronger digital adoption?
31. Which products show higher digital usage?
32. Are branch-originated transactions becoming less important?

The audited analytical definition is `DIGITAL = MOBILE + WEB`; physical is `BRANCH + ATM`, automated is `AUTOMATIC`, and merchant is `POS`. Preserve the original channel alongside this grouping.

### 6. Transaction Status and Failures

33. What share of transactions succeeds?
34. What share fails?
35. Which channels have higher failure rates?
36. Which transaction types fail more frequently?
37. What are the most common failure reasons?
38. Do failures cluster in specific periods?
39. Are some branches or channels associated with repeated operational failures?
40. Are high-value transactions more likely to fail?

Failure-rate KPIs should use an explicit denominator and should not mix transaction categories where failure is not meaningful.

### 7. Branch Transaction Activity

41. Which branches process the most branch-linked transactions?
42. Which branches process the highest transaction value?
43. How does branch activity evolve over time?
44. Which branches show declining physical usage?
45. Does branch activity differ from customer-base size?
46. Which transaction types remain strongly branch-dependent?

Branch activity is not the same as branch profitability.

### 8. Transfer Scope

47. What share of transfers is internal, domestic external or international?
48. How does transfer scope differ by customer type?
49. How has cross-border transfer activity evolved?
50. Which products or customer segments use international transfers more heavily?
51. Are international transfers much larger on average?
52. Does transfer scope differ by region?

Only transaction types where `transfer_scope` is meaningful should be included.

### 9. Counterparty Institutions

53. Which external institutions receive the largest outgoing transfer volume?
54. Which institutions send the largest incoming transfer volume?
55. Which banks are the most important transfer counterparties?
56. How concentrated are external flows among counterparties?
57. How has counterparty concentration changed over time?
58. Are there material differences between banks and non-bank financial institutions?

Counterparty analysis should use:

```text
transactions
→ financial_institutions
→ banks
```

and preserve institutions that do not map to a bank.

### 10. Merchant Categories

59. Which merchant categories dominate card/payment transaction count?
60. Which merchant categories dominate value?
61. How does merchant mix differ by customer segment?
62. Are some merchant categories unusually seasonal?
63. Do merchant categories differ by channel?

Merchant analysis should be restricted to transaction types where `merchant_category` is meaningful.

### 11. Account-Level Transaction Intensity

64. How many transactions does the typical active account generate per month?
65. What is the distribution of monthly transaction counts per account?
66. Which accounts are unusually active?
67. Which products generate the highest transaction intensity?
68. Does transaction intensity increase with account tenure?
69. How does transaction intensity differ between individuals and businesses?

Distributional and outlier questions are better suited to Python once SQL creates the account-month base.

### 12. Value Distribution

70. What is the distribution of transaction amounts?
71. How different are mean and median transaction values?
72. Which transaction types show the greatest dispersion?
73. Are there extreme-value transactions?
74. Do high-value patterns differ by customer type?
75. Do high-value patterns differ by channel?

These are primarily Python questions.

---

## Temporal Variables

The central temporal field is:

- `banking.transactions.transaction_datetime`

Derived reusable fields may include:

- transaction date;
- year;
- month;
- `year_month`;
- day of week;
- hour of day.

Not all of these need to be persisted immediately.

### Monthly analysis

Monthly aggregation is the default time grain for:

- Power BI;
- performance trends;
- channel mix;
- transfer scope;
- counterparty analysis;
- branch activity.

### Daily / hourly analysis

Daily or hourly grains should be used only for targeted questions such as:

- operational failures;
- intraday patterns;
- high-frequency monitoring;
- anomaly analysis.

---

## SQL vs DAX vs Python vs Superset Boundary

### SQL

SQL should own:

- event-level joins;
- time derivation;
- filtering valid transaction populations;
- account-month aggregation;
- branch-month aggregation;
- counterparty-month aggregation;
- explicit attempted/completed/failed measures;
- stable audited channel grouping;
- large-table processing;
- performance-conscious reduction of the raw event table.

Because of table size, SQL is especially important in this file.

### DAX / Power BI

DAX should own dynamic measures such as:

- Transaction Count;
- Transaction Value;
- Average Transaction Value;
- Digital Transaction %;
- Digital Value %;
- Failed Transaction Count;
- Failure Rate %;
- Incoming Transaction Value;
- Outgoing Transaction Value;
- International Transfer Share %;
- Branch Transaction Share %;
- YoY Transaction Growth;
- Portfolio / channel share measures.

These measures should respond dynamically to:

- month/year;
- transaction type;
- direction;
- channel;
- product;
- customer type;
- customer segment;
- branch;
- region;
- transaction status;
- transfer scope.

### Python / Pandas / Jupyter

Python is the preferred tool for:

- amount distributions;
- account-level transaction-intensity distributions;
- outliers;
- heavy-tail analysis;
- hourly/day-of-week patterns;
- statistical comparison across segments;
- anomaly exploration;
- concentration curves;
- targeted customer/account behavior studies.

Python should work from reduced extracts or aggregated datasets when possible rather than loading the entire transaction table unnecessarily.

### Apache Superset

Superset is particularly appropriate for this topic because it can query PostgreSQL directly.

Good use cases include:

- operational transaction monitoring;
- failure-rate monitoring;
- channel activity;
- recent transfer activity;
- direct SQL exploration;
- lightweight dashboards over PostgreSQL aggregates.

Superset should not duplicate the full Power BI executive dashboard.

---

## Recommended SQL Analytical Objects

The transaction layer should prefer a small number of reusable datasets rather than dozens of highly specific queries.

### 1. Account-month transaction summary

Recommended grain:

```text
account_id
× year_month
× transaction_type
× direction
× channel
× transfer_scope
```

Suggested measures:

- attempted_transaction_count;
- completed_transaction_count;
- failed_transaction_count;
- attempted_transaction_amount;
- completed_transaction_amount;
- failed_transaction_amount;
- average completed transaction amount;
- completed branch transaction count.

`transaction_status` is deliberately **not** part of this reusable grain. The status-specific measures coexist in the same row so failed amounts are harder to mistake for realized financial volume.

This supports most Power BI transaction analysis while dramatically reducing the raw event volume.

### 2. Branch-month transaction summary

Recommended grain:

```text
transaction_branch_id
× year_month
```

Possible additions:

- channel;
- transaction type;
- status.

Use only dimensions necessary for branch analysis.

### 3. Counterparty-month transfer summary

Recommended grain:

```text
counterparty_institution_id
× year_month
× direction
× transfer_scope
```

Suggested measures:

- transfer_count;
- transfer_amount;
- average_transfer_amount.

---

## Performance Considerations

Because this file works with the largest fact table in Part I (~76.8M rows in the canonical world), it is designed for **section-by-section execution**, not routine `Run All`.

Because this file works with the largest fact table in Part I:

- use `EXPLAIN` before expensive experimental queries;
- use `EXPLAIN ANALYZE` once the query is safe and worth measuring;
- avoid repeated full scans where a reusable aggregation would suffice;
- filter before joining whenever semantically valid;
- do not create indexes speculatively;
- create indexes only after observing actual query plans and workload;
- avoid `SELECT *` on the transaction event table;
- avoid importing the full transaction table into Power BI by default.

Performance work should be evidence-driven.

---

## Data-Quality Checks

Before analytical use, verify:

- transaction primary-key uniqueness;
- valid account foreign keys;
- valid transaction branch foreign keys;
- valid counterparty institution references where present;
- transaction amount semantics, including the separation of failed attempted amounts from completed realized volume;
- direction values;
- transaction-status values;
- channel values;
- transfer-scope values;
- NULL patterns for merchant category;
- NULL patterns for counterparty institution;
- failure reason only where transaction status indicates failure;
- temporal coverage.

NULLs may be structurally valid depending on transaction type and should not automatically be treated as missing-data errors.

---

## Expected Outputs

By the end of `04_transactions.sql`, the project should have:

1. validated transaction-table coverage;
2. a clear definition of transaction dimensions;
3. a reusable account-month transaction analytical base;
4. a reusable branch-month transaction base;
5. a reusable counterparty-month transfer base;
6. a small set of SQL validation summaries;
7. a clean handoff to Power BI/DAX;
8. a clean handoff to Superset;
9. a clean handoff to Python for distributional analysis.

---

## Analytical Boundary

This file should answer:

> **How does money move through BTYT, through which channels and transaction types, and what efficient analytical grains should downstream tools use?**

It should not attempt to answer:

> **Which branch is most profitable?**

That belongs to `05_branches.sql` / `07_performance.sql`.

It should not attempt to answer:

> **Which customer will commit fraud or behave anomalously?**

That would require a separately defined analytical or ML problem.
