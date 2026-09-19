# 01 — Customer Analytics

## Objective

Build the reusable customer-level analytical layer for BTYT.

The main question is:

> **Who are BTYT customers, how has the customer base evolved, and what customer-level structure should downstream analytics consume?**

The SQL layer should prepare stable customer attributes, lifecycle information and relationship counts without trying to perform every segmentation or statistical comparison inside PostgreSQL.

---

## Scope

This analysis focuses on:

- customer type and current master status;
- registrations, closures and annual active stock;
- registration cohorts;
- individual-customer characteristics;
- business-customer characteristics;
- tenure;
- residence and primary branch;
- historical account/card/loan relationships;
- current account/card relationships;
- lifetime distinct-product depth;
- first reusable cross-sell flags.

Detailed loan-currentness is intentionally deferred to `03_loans.sql`.

---

## Main Tables

Primary:

- `core.customers`

Supporting:

- `core.branches`
- `core.accounts`
- `banking.cards`
- `banking.loans`

---

## Key Analytical Grains

### Customer grain

```text
1 row = 1 customer
```

This is the central grain for the customer dimension, relationship base and cross-sell flags.

### Registration cohort grain

```text
registration_year × customer_type
```

Used for lifecycle and cohort comparison.

---

## Critical Semantic Rule — Current vs Lifetime Relationships

A historical relationship is not automatically a current relationship.

Therefore the audited SQL distinguishes:

```text
total_account_count         → lifetime / historical accounts
total_card_count            → lifetime / historical cards
loan_history_count          → lifetime / historical loans

active_account_count        → accounts currently ACTIVE in account master
active_card_count           → cards currently ACTIVE in card master
lifetime_distinct_product_count
```

The customer layer deliberately does **not** create a generic `active_loan_count`.

Loan contractual and credit-quality semantics are more complex and belong to `03_loans.sql`.

---

## Customer Segment

For a reusable first-level segment:

```text
INDIVIDUAL → employment_status
BUSINESS   → company_size
```

This is a practical analytical segmentation field, not a claim that these are the only meaningful customer segments.

Python and Power BI may later create richer analytical groupings.

---

## Lifecycle Semantics

The annual lifecycle uses:

- `registration_year`;
- `closing_year`.

For each year it can derive:

- registrations;
- closures;
- net customer change;
- active customer stock.

The master field `customer_status` is a cutoff/current attribute.

Do not use the 2026 cutoff status as if it described the customer's status in every historical year.

---

## Main Business Questions

### Composition and lifecycle

1. How is the customer base split between individuals and businesses?
2. What share of each type is currently active or closed?
3. How many customers register each year?
4. How many close each year?
5. How does the annual customer stock evolve?
6. How do registration cohorts differ?

### Customer profile

7. How do individual customers differ by age, gender, employment and income?
8. How do business customers differ by company size, sector, age and revenue?
9. How are customers distributed geographically?
10. How long have customers been with BTYT?

### Relationship depth

11. How many historical accounts, cards and loans has each customer held?
12. How many active accounts and active cards does each customer currently hold?
13. How many distinct products has the customer ever held?
14. Which segments show greater lifetime relationship depth?
15. Which active customers hold an account but no active card?

### Downstream questions

16. How do age, income or tenure relate to product depth?
17. Which segments contain unusually high or low relationship depth?
18. Which customer profiles show cross-sell opportunity?
19. How do customer characteristics differ across regions and branches?

Distributional and statistical questions belong mainly in Python.

---

## Recommended SQL Analytical Objects

### 1. Customer dimensional base

Grain:

```text
1 row = 1 customer
```

Includes:

- customer type;
- current master status;
- registration / closing years;
- tenure;
- approximate age at 2026 cutoff;
- employment / income;
- company attributes;
- customer segment;
- residence;
- primary branch and region.

### 2. Customer relationship base

Grain:

```text
1 row = 1 customer
```

Includes:

- total historical account count;
- total historical card count;
- loan history count;
- active account count;
- active card count;
- lifetime distinct-product count;
- reusable relationship flags.

The account/card/loan sources are stacked with `UNION ALL` before aggregation to avoid row multiplication from direct many-to-many joins.

### 3. Cross-sell flag base

Grain:

```text
1 row = 1 active customer
```

Current audited example:

```text
account_without_active_card_flag
```

Loan cross-sell is not frozen here.

---

## SQL vs DAX vs Python Boundary

### SQL

Owns:

- lifecycle;
- cohorts;
- reusable customer dimension;
- relationship counts;
- stable current/lifetime flags.

### DAX / Power BI

Owns dynamic measures such as:

- Active Customers;
- Customer Share %;
- Average Tenure;
- Average Active Accounts;
- Average Active Cards;
- Card Penetration %;
- Account-without-card %;
- Average Lifetime Distinct Products.

### Python

Owns questions such as:

- income distributions;
- age distributions;
- medians and percentiles;
- outliers;
- tenure × product depth;
- statistical group comparisons.

---

## Important Interpretation Cautions

- `customer_status` is a master/cutoff status, not monthly history.
- `primary_branch_id` is the customer's master relationship branch; it is not identical to the monthly relationship branch used by the performance engine.
- Historical loan ownership is not the same as a currently open loan.
- Cross-sell flags are analytical opportunities, not recommendations to contact customers.

---

## Expected Output

By the end of `01_customers.sql`, BTYT should have:

1. a customer composition baseline;
2. an annual lifecycle series;
3. registration cohorts;
4. a reusable one-row-per-customer dimension;
5. a reusable relationship-depth base;
6. current account/card cross-sell flags;
7. a clean handoff to Python and Power BI.

---

## Analytical Boundary

`01` answers:

> **Who are the customers and what relationships have they built with BTYT?**

It does not answer detailed loan risk, transaction behavior, campaign effectiveness or profitability.
