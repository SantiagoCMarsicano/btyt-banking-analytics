# 07 — Bank Performance & Executive Management Analytics

## Objective

Build the final Part I analytical layer for consolidated BTYT management performance.

The main question is:

> **How is BTYT performing as a bank, what is driving changes in revenue, costs, credit losses and net income, and how should management interpret those changes over time?**

This file is the executive synthesis of Part I.

It should connect:

1. business scale;
2. balance-sheet operating scale;
3. transaction activity;
4. revenue generation;
5. cost structure;
6. credit losses;
7. profitability;
8. customer/account productivity;
9. branch contribution;
10. macroeconomic and shock context.

The objective is not to build every management KPI directly in SQL.

PostgreSQL should provide a stable monthly performance grain and reusable context. Power BI / DAX should own dynamic KPIs, ratios, time intelligence and executive interaction.

---

## Scope

This analysis focuses on:

- active customers;
- active accounts;
- average deposits;
- average loan balance;
- transaction count;
- transaction volume;
- branch transaction count;
- interest income;
- interest expense;
- net interest income;
- fee income;
- total revenue;
- personnel cost;
- fixed cost;
- variable cost;
- operational cost;
- total operating cost;
- credit loss;
- pre-provision profit;
- net income;
- productivity;
- efficiency;
- profitability;
- annual management rollups;
- branch-to-bank reconciliation;
- macroeconomic context;
- external-shock context;
- market context where appropriate.

---

## Out of Scope

The following detailed questions remain in their thematic files:

- customer segmentation and relationship depth → `01_customers.sql`
- account/product behavior → `02_products_accounts.sql`
- loan delinquency and DPD trajectories → `03_loans.sql`
- transaction/channel behavior → `04_transactions.sql`
- branch-level operational diagnosis → `05_branches.sql`
- campaign effectiveness → `06_campaigns.sql`

`07_performance.sql` should integrate their implications at management level rather than duplicate their detailed analyses.

---

## Main Tables

### Primary table

- `performance.bank_monthly_performance`

### Branch reconciliation

- `performance.branch_monthly_performance`

### Context tables

- `macro.macro_environment`
- `macro.external_shocks`

### Optional market context

- `market.banks`
- `market.bank_financials`
- `market.bank_market_weights`

---

## Reporting Currency

Monetary fields in:

- `performance.bank_monthly_performance`;
- `performance.branch_monthly_performance`

are generated as **UYU-equivalent reporting values**.

They are therefore designed to be aggregated within the performance layer.

This is different from lower-level native-currency tables such as accounts, loans and transactions, where UYU and USD must remain separate unless converted.

---

## Core Analytical Grain

### Bank-month grain

> **1 row = 1 month of consolidated BTYT performance**

Source:

- `performance.bank_monthly_performance`

This is the principal management-performance grain.

It contains both:

- **stock / semi-additive measures**
- **flow / additive measures**

These must be treated differently.

---

## Performance-Engine Definitions

### Active customers

A monthly relationship/activity measure from the account-balance layer.

Each represented customer is uniquely assigned to one branch for that month.

It is not the same as the cutoff field `core.customers.customer_status`.

### Active accounts

Accounts represented in the month's account-balance layer.

It is not simply the cutoff field `core.accounts.account_status`.

### Average deposits

Generated from account monthly average balances:

```text
(opening_balance + closing_balance) / 2
```

with currency conversion to UYU-equivalent.

### Average loan balance

Monthly outstanding exposure converted to UYU-equivalent.

### Transactions

Performance transaction counts and volume use **COMPLETED transactions only**.

`branch_transaction_count` is the completed `BRANCH`-channel count.

---

## Stock vs Flow Semantics

### Semi-additive / snapshot-style measures

- `active_customers`
- `active_accounts`
- `average_deposits`
- `average_loan_balance`

These can describe a month and may reconcile across branches for that month.

They should **not** simply be summed across months.

For annual reporting, use an explicit rule such as:

- year-end value;
- average monthly value.

---

### Additive flow measures

- `transaction_count`
- `transaction_volume`
- `branch_transaction_count`
- `interest_income`
- `interest_expense`
- `net_interest_income`
- `fee_income`
- `total_revenue`
- `personnel_cost`
- `fixed_cost`
- `variable_cost`
- `operational_cost`
- `total_operating_cost`
- `credit_loss`
- `pre_provision_profit`
- `net_income`

These may be summed across months to produce annual totals.

---

## Performance Accounting Identities

The performance engine follows the management identities:

```text
Net Interest Income
= Interest Income - Interest Expense
```

```text
Total Revenue
= Net Interest Income + Fee Income
```

```text
Total Operating Cost
= Personnel Cost
+ Fixed Cost
+ Variable Cost
+ Operational Cost
```

```text
Pre-Provision Profit
= Total Revenue - Total Operating Cost
```

```text
Net Income
= Pre-Provision Profit - Credit Loss
```

These relationships should be audited directly in SQL.

---

## Main Business Questions

### 1. Business Scale

1. How many active customers does BTYT have over time?
2. How many active accounts does it have?
3. How does average deposit scale evolve?
4. How does average loan balance evolve?
5. Is business scale growing consistently?
6. Are customers, accounts, deposits and loans growing at similar rates?
7. Does account growth outpace customer growth?

---

### 2. Transaction Activity

8. How does transaction count evolve?
9. How does transaction volume evolve?
10. What share of activity remains branch-linked?
11. Is transaction count growing faster than transaction value?
12. Does increased activity translate into higher revenue?

Detailed channel analysis remains in `04_transactions.sql`.

---

### 3. Revenue

13. How does total revenue evolve?
14. How much comes from net interest income?
15. How much comes from fee income?
16. Is the revenue mix changing over time?
17. Is fee income becoming more or less important?
18. Does revenue growth track customer, loan or transaction growth?
19. Which periods show revenue acceleration or deterioration?

---

### 4. Net Interest Income

20. How do interest income and interest expense evolve?
21. Is net interest income expanding or compressing?
22. Does net interest income grow with loan balances?
23. Are there periods where funding cost pressure reduces net interest income?
24. Does macro or USD pressure coincide with changes in interest performance?

This file should describe association and timing, not claim causality.

---

### 5. Cost Structure

25. How does total operating cost evolve?
26. How much comes from personnel costs?
27. How much comes from fixed costs?
28. How much comes from variable costs?
29. How much comes from operational costs?
30. Is the cost mix changing?
31. Are costs growing faster or slower than revenue?
32. Is operating leverage improving?

---

### 6. Pre-Provision Profit

33. How does pre-provision profit evolve?
34. Is the core business generating more profit before credit losses?
35. Are periods of weak pre-provision profit caused primarily by revenue weakness or cost pressure?
36. Does scale growth translate into stronger pre-provision profitability?

---

### 7. Credit Loss

37. How does credit loss evolve over time?
38. Which periods show unusually high credit-loss pressure?
39. How large is credit loss relative to the loan book?
40. How much of pre-provision profit is absorbed by credit losses?
41. Does credit-loss deterioration coincide with macro stress?

Detailed delinquency drivers remain in `03_loans.sql`.

---

### 8. Net Income

42. How does net income evolve?
43. Which periods are profitable or loss-making?
44. Is net income volatility driven more by revenue, costs or credit losses?
45. Is profitability improving as the bank scales?
46. Are there sustained periods of margin compression?
47. How does net income behave around external shocks?

---

### 9. Efficiency

48. What is BTYT's Cost-to-Income ratio?
49. Is Cost-to-Income improving?
50. How much revenue is generated per active customer?
51. How much net income is generated per active customer?
52. How much revenue is generated per active account?
53. Are deposits and loan balances growing faster than operating costs?
54. Does scale produce operating leverage?

---

### 10. Balance-Sheet Operating Mix

55. What is the relationship between average loans and average deposits?
56. Is the loan-to-deposit operating mix changing?
57. Are deposits growing faster than lending?
58. Does the funding/lending mix shift during stress periods?

This is a management ratio based on the BTYT performance-engine fields, not a claim of regulatory reporting equivalence.

---

### 11. Revenue Mix

59. What share of revenue comes from fees?
60. What share comes from net interest income?
61. Is the bank becoming more fee-dependent?
62. Does revenue diversification improve during periods of interest pressure?

---

### 12. Transaction Mix at Management Level

63. What share of transaction count is branch-linked?
64. Is branch-linked activity declining as the bank grows?
65. Does lower physical transaction share coincide with lower operating costs?

Detailed digital-channel definitions remain in `04_transactions.sql`.

---

### 13. Annual Management Performance

66. What are annual total revenues?
67. What are annual total operating costs?
68. What are annual credit losses?
69. What is annual net income?
70. What are average monthly customers/accounts/deposits/loans?
71. What are year-end customers/accounts?
72. How does each year compare structurally and financially with the previous one?

Annual reporting must respect stock-versus-flow semantics.

---

### 14. Branch-to-Bank Reconciliation

73. Do monthly branch totals reconcile to consolidated bank performance?
74. Are active customers/accounts fully allocated to branches?
75. Do branch revenue, costs, credit losses and net income reconcile?
76. Are there any residuals caused by rounding or allocation?

The consolidated performance layer should be auditable back to branch performance. `07_performance.sql` is the **canonical full branch-to-bank reconciliation** for the final SQL layer.

---

### 15. Macro Context

77. How does performance behave across different macro growth environments?
78. How does the credit cycle align with lending and credit loss?
79. Does financial stress align with weaker profitability?
80. Does USD pressure align with changes in funding or lending conditions?
81. Does digitalization context align with branch transaction share?
82. Does cross-border context align with transaction volume?

The macro table is annual context. Monthly performance rows inherit the relevant year's macro state.

---

### 16. External Shock Context

83. Which performance months overlap with external-shock windows?
84. How do revenue, costs, credit losses and net income behave during those windows?
85. Are several shocks active simultaneously?
86. Does performance recover after shock periods?

Shock overlap is descriptive context, not causal identification.

---

### 17. Competitive / Market Context

87. How does the competitive environment evolve across years?
88. How do market weights change among banks?
89. How do external bank financials change over time?
90. Does BTYT's internal trajectory occur during periods of broader market change?

The market tables should be treated as context rather than directly merged into monthly accounting measures without a clear definition.

---

## Executive KPI Framework

The Power BI executive layer should eventually organize KPIs into five groups.

### Scale

- Active Customers
- Active Accounts
- Average Deposits
- Average Loan Balance
- Transaction Count
- Transaction Volume

### Revenue

- Interest Income
- Interest Expense
- Net Interest Income
- Fee Income
- Total Revenue

### Cost

- Personnel Cost
- Fixed Cost
- Variable Cost
- Operational Cost
- Total Operating Cost

### Risk

- Credit Loss
- Credit Loss / Average Loan Balance
- Credit Loss / Pre-Provision Profit

### Profitability & Efficiency

- Pre-Provision Profit
- Net Income
- Cost-to-Income
- Pre-Provision Margin
- Net Margin
- Revenue per Customer
- Net Income per Customer
- Revenue per Account
- Loan-to-Deposit operating ratio
- Fee Income Share
- Branch Transaction Share

---

## SQL vs DAX vs Python Boundary

### SQL

SQL should own:

- consolidated monthly performance base;
- macro-context joins;
- shock-calendar joins;
- annual stock/flow rollups;
- accounting identity audits;
- branch-to-bank reconciliation;
- reusable P&L component structure;
- structural consistency diagnostics.

---

### DAX / Power BI

DAX should own dynamic measures such as:

- Total Revenue;
- Net Income;
- Cost-to-Income;
- Revenue per Customer;
- Net Income per Customer;
- Revenue per Account;
- Loan-to-Deposit ratio;
- Fee Income Share;
- Branch Transaction Share;
- Credit Loss ratio;
- MoM / YoY growth;
- rolling 3 / 6 / 12-month measures;
- YTD revenue;
- YTD net income;
- period-versus-period variance;
- branch contribution under filter context.

These should respond dynamically to date and other selected dimensions.

---

### Python / Pandas / Jupyter

Python is useful for:

- decomposition of performance changes;
- correlations;
- shock-window comparison;
- trend breaks;
- anomaly detection;
- scenario analysis;
- statistical association with macro variables;
- exploratory forecasting.

Causal or predictive interpretation requires a separately defined methodology.

---

### Excel

This file is also a strong source for the final Excel management workbook.

Useful Excel outputs include:

- monthly executive P&L;
- annual summary;
- variance tables;
- KPI scorecard;
- management PivotTables;
- waterfall charts;
- scenario / sensitivity exercises.

---

## Recommended SQL Analytical Objects

### 1. Bank-month performance base

Grain:

```text
1 row = 1 month
```

Include:

- all bank performance measures;
- calendar fields;
- annual macro context;
- shock-window context.

This is the principal Power BI executive source.

---

### 2. Annual management summary

Grain:

```text
1 row = 1 year
```

Apply correct temporal semantics:

```text
flows → SUM across months
stocks → monthly AVG and/or year-end
```

---

### 3. P&L component bridge

Grain:

```text
1 row = 1 month × 1 P&L component
```

Useful for:

- waterfall charts;
- revenue/cost decomposition;
- management storytelling.

The bridge contains both **components** and **totals**. Do not sum every row together as if all rows were independent additive components. Use the `amount_type` / ordering semantics to distinguish components from subtotal/total rows.

---

## Macro Join Semantics

`macro.macro_environment` has annual grain:

```text
1 row = 1 year
```

Therefore:

```text
monthly performance
→ extract year
→ join annual macro state
```

The same annual macro values will repeat across the months of that year.

This is expected and should not be mistaken for monthly macro variation.

---

## External Shock Semantics

`macro.external_shocks` contains explicit:

- start month;
- peak month;
- end month;
- recovery end month.

A reusable monthly shock calendar expands each shock from start through recovery and distinguishes:

```text
ACTIVE_SHOCK
PEAK
RECOVERY
```

The recovery window is context after the active shock period; it should not be described as if the shock were still fully active.

If several shocks overlap, the month may contain multiple shock labels.

Do not collapse overlapping shocks into one causal interpretation.

---

## Performance Integrity Checks

Before executive analysis, verify:

- one row per `year_month`;
- complete monthly coverage;
- non-negative count/stock fields where required;
- accounting identities;
- branch-to-bank reconciliation;
- no impossible branch transaction count greater than total transaction count;
- consistent stock/flow handling;
- no accidental UYU/USD mixing when reconciling to lower-level tables.

---

## Expected Outputs

By the end of `07_performance.sql`, the project should have:

1. a reusable consolidated bank-month performance base;
2. macro and external-shock context;
3. an annual management summary with correct stock/flow treatment;
4. a reusable P&L bridge;
5. an executive KPI validation query;
6. accounting-identity diagnostics;
7. branch-to-bank reconciliation;
8. a clean Power BI / DAX handoff;
9. a clean Excel management handoff;
10. a clean Python handoff for advanced performance analysis.

---

## Analytical Boundary

This file should answer:

> **How is BTYT performing as a bank, what are the major drivers of performance, and how does that performance evolve in business, risk and macro context?**

It should not replace detailed customer, credit, transaction, branch or campaign analytics.

It is the executive synthesis layer of Part I.
