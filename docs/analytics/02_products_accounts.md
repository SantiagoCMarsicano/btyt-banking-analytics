# 02 — Products & Accounts Analytics

## Objective

Build the reusable product, account, account-month and card analytical layers for BTYT.

The main question is:

> **What products does BTYT offer, how are account relationships created and closed, and how do balances and account flows evolve over time?**

---

## Scope

This analysis focuses on:

- product catalog and product families;
- product currency;
- intended target customer type;
- product launch year;
- account opening and closing lifecycle;
- account opening cohorts;
- opening channel;
- one-row-per-account analytical structure;
- account-month balances and flows;
- product-target alignment;
- card issuance and issue channel;
- card relationship branch attribution;
- balance coverage and accounting consistency.

---

## Main Tables

Primary:

- `core.products`
- `core.accounts`
- `banking.account_balances`
- `banking.cards`

Supporting:

- `core.customers`
- `core.branches`

---

## Product Terminology

BTYT uses:

```text
product_name
    → specific / commercial product

product_family
    → broader product category

target_customer_type
    → intended customer population

currency
    → native product currency
```

There is no separate canonical `product_type` field in `core.products`.

---

## Key Analytical Grains

### Product grain

```text
1 row = 1 product
```

### Account grain

```text
1 row = 1 account
```

### Account-month grain

```text
1 row = 1 account × 1 month
```

### Card grain

```text
1 row = 1 card
```

These grains should not be mixed without explicit aggregation.

---

## Critical Monetary Rule

Native balances are stored in their product currency.

Therefore:

> **Do not add UYU and USD account balances into one monetary total unless an explicit FX conversion is introduced.**

This differs from the `performance` schema, whose monetary fields are already UYU-equivalent reporting values.

---

## Stock vs Flow Semantics

Inside `banking.account_balances`:

```text
opening_balance  → stock
closing_balance  → stock
total_inflows    → flow
total_outflows   → flow
net_flow         → flow
```

The accounting identity is:

```text
closing_balance
= opening_balance + total_inflows - total_outflows
```

Stocks should be evaluated at a point in time or with an explicit average rule.

Flows may be accumulated across periods.

---

## Master Status vs Monthly Observation

`core.accounts.account_status` is a master/cutoff attribute.

It is not a historical monthly status.

The presence of an `account_balances` row is the monthly observation itself.

The same principle applies to card master status.

---

## Performance-Layer Reconciliation Caution

`performance.average_deposits` is **not** simply:

```text
SUM(account_balances.closing_balance)
```

The performance engine uses monthly average balance logic:

```text
(opening_balance + closing_balance) / 2
```

and converts USD to UYU-equivalent.

Therefore native account-balance totals should not be expected to reconcile directly to `performance.average_deposits` without reproducing those semantics.

---

## Card Branch Attribution

The audited rule is:

```text
Debit card
→ linked account branch

Credit card
→ linked_account_id is NULL by design
→ fallback to customer's primary_branch_id
```

The reusable field is therefore:

```text
relationship_branch_id
= COALESCE(linked_account.branch_id, customer.primary_branch_id)
```

This matches the branch-performance attribution logic for card fees.

---

## Main Business Questions

### Product structure

1. What products exist?
2. Which product families are represented?
3. Which products are denominated in UYU or USD?
4. Which customer types are each product designed for?
5. How has the product catalog expanded over time?

### Account lifecycle

6. How many accounts open each year?
7. How many close each year?
8. How does active account stock evolve?
9. Which products drive account growth?
10. Which opening channels drive new accounts?

### Cohorts

11. How do account-opening cohorts differ by product?
12. How do cohorts differ by opening channel?
13. What share of each cohort remains active at cutoff?

### Balances and flows

14. How do closing balances evolve by product and currency?
15. How do inflows and outflows evolve?
16. Which products have persistent positive or negative net flow?
17. Which account segments hold the largest balances?
18. How concentrated are balances across accounts?

### Product alignment

19. Does actual customer type match `target_customer_type`?
20. Which products show cross-segment use?

### Cards

21. How many cards are issued by product?
22. How does issue channel evolve?
23. How does card issuance differ across customer segments?
24. How does card relationship branch differ geographically?

---

## Recommended SQL Analytical Objects

### 1. Account analytical base

Grain:

```text
1 row = 1 account
```

Includes:

- account lifecycle;
- account status at cutoff;
- opening channel;
- product attributes;
- customer type / segment;
- branch dimensions.

### 2. Account-month analytical base

Grain:

```text
1 row = 1 account × 1 month
```

Includes:

- opening balance;
- inflows;
- outflows;
- closing balance;
- net flow;
- product / currency;
- customer segment;
- branch / region.

### 3. Card analytical base

Grain:

```text
1 row = 1 card
```

Includes:

- issue year;
- card status;
- issue channel;
- linked account;
- product;
- customer segment;
- relationship branch with credit-card fallback.

---

## Data-Quality Checks

The SQL layer validates:

- account-balance temporal coverage;
- duplicate account-month rows;
- the balance accounting identity;
- negative balance/flow anomalies;
- account lifecycle consistency;
- card lifecycle consistency.

Expected structural diagnostics should be clean before the layer is frozen.

---

## SQL vs DAX vs Python Boundary

### SQL

Owns:

- product catalog;
- account lifecycle and cohorts;
- reusable account / account-month / card bases;
- accounting consistency checks;
- stable branch attribution.

### DAX / Power BI

Owns dynamic measures such as:

- Total Accounts;
- Active Accounts;
- Accounts Opened / Closed;
- Account Share %;
- YoY Account Growth;
- Total Closing Balance at selected month;
- Total Inflows / Outflows;
- Net Flow;
- Currency Mix %;
- Opening Channel Mix %;
- Product Mix %;
- Card Count / Penetration.

### Python

Owns:

- balance distributions;
- outliers;
- concentration curves;
- account trajectories;
- statistical comparisons.

### Power Query

Should remain light:

- connection;
- column selection;
- data types;
- presentation-oriented cleanup.

---

## Expected Output

By the end of `02_products_accounts.sql`, BTYT should have:

1. a validated product catalog;
2. an account lifecycle series;
3. account-opening cohorts;
4. a one-row-per-account base;
5. a one-row-per-account-month base;
6. target-alignment diagnostics;
7. a one-row-per-card base;
8. account/card lifecycle and balance consistency checks;
9. a clean handoff to Power BI and Python.

---

## Analytical Boundary

`02` answers:

> **What banking products and account relationships exist, and how do account balances and flows behave?**

Loan credit quality belongs to `03`, transaction behavior to `04`, and consolidated profitability to `07`.
