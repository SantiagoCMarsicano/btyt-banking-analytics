# audit_relational_model.py

## Purpose

`audit_relational_model.py` is the read-only validation layer for the final BTYT PostgreSQL relational model.

It is designed to inspect the database after the migration to the final **7-schema / 23-table architecture** and verify that the relational structure, data types, precision rules, primary-key candidates, constraint candidates, and business rules remain coherent.

The script does **not** modify tables, data, constraints, indexes, or schemas.

---

## Final schema architecture

The audit expects the following layout:

```text
core          4 tables
banking       5 tables
marketing     3 tables
reference     2 tables
market        5 tables
macro         2 tables
performance   2 tables
-----------------------
TOTAL        23 tables
```

### `core`

```text
branches
customers
accounts
products
```

### `banking`

```text
cards
loans
transactions
account_balances
loan_monthly_snapshot
```

### `marketing`

```text
campaigns
campaign_customers
campaign_exposures
```

### `reference`

```text
campaign_channels
campaign_geography
```

### `market`

```text
banks
bank_financials
bank_market_weights
bank_world_parameters
financial_institutions
```

### `macro`

```text
macro_environment
external_shocks
```

### `performance`

```text
bank_monthly_performance
branch_monthly_performance
```

---

## Main audit phases

The final script supports the following phases.

### Schema layout

```bash
python scripts/database/audit_relational_model.py --schema-layout
```

Checks the exact 7-schema / 23-table architecture.

It reports:

- expected tables per schema;
- observed tables per schema;
- missing tables;
- unexpected tables;
- final 23-table count.

---

### Applied relational state

```bash
python scripts/database/audit_relational_model.py --state
```

Inspects the currently applied relational model.

Expected state:

```text
23 primary keys
28 foreign keys
27 CHECK constraints
11 audited NOT NULL columns
```

It also checks whether any FK or CHECK constraint remains unvalidated.

---

### Structure

```bash
python scripts/database/audit_relational_model.py --structure
```

Prints:

- table inventory;
- estimated row counts;
- column inventory;
- PostgreSQL data types;
- nullability.

---

### Semantic data types

```bash
python scripts/database/audit_relational_model.py --types
```

Compares current PostgreSQL types with the expected semantic types.

Examples:

```text
year_month     → date
year fields    → integer
start/end dates → date
```

The final architecture correctly evaluates moved tables under:

```text
macro.*
performance.*
```

rather than the previous `market.*` locations.

---

### Value compatibility

```bash
python scripts/database/audit_relational_model.py --values
```

Audits columns that require semantic type review.

For integer candidates it checks:

- invalid values;
- fractional values;
- values outside the PostgreSQL integer range.

For date candidates it checks:

- `YYYY-MM`;
- `YYYY-MM-DD`;
- invalid formats.

The audit classifies proposed conversions as:

```text
SAFE
REVIEW
BLOCKED
```

---

### Financial precision

```bash
python scripts/database/audit_relational_model.py --precision
```

Audits configured financial and simulation columns.

The final version works both:

- before precision conversion;
- after precision conversion.

Typical targets:

```text
money        → numeric(18,2)
money_large  → numeric(20,2)
rate         → numeric(12,6)
ratio        → numeric(12,8)
simulation   → double precision
coordinate   → double precision
```

The final script correctly locates:

```text
performance.bank_monthly_performance
performance.branch_monthly_performance

macro.macro_environment
macro.external_shocks
```

---

### Primary-key audit

```bash
python scripts/database/audit_relational_model.py --pk
```

Audits all **23 primary-key candidates**.

For each candidate it checks:

- total rows;
- null key rows;
- distinct keys;
- duplicate groups;
- duplicate excess rows;
- largest duplicate group.

A candidate passes only when:

```text
NULL key rows = 0
duplicate groups = 0
distinct keys = total rows
```

---

### Constraint candidates

```bash
python scripts/database/audit_relational_model.py --constraints
```

Audits:

- nullability candidates;
- category values;
- range rules;
- temporal consistency.

Examples include:

```text
transaction amount >= 0
loan term > 0
closing_year >= opening_year
campaign end_date >= start_date
financial institution active_to >= active_from
external shock start <= peak <= end <= recovery
```

The external-shock temporal rules now correctly reference:

```text
macro.external_shocks
```

---

### Business rules

```bash
python scripts/database/audit_relational_model.py --business-rules
```

Audits cross-column semantic rules such as:

```text
ACTIVE accounts have no closing_year
CLOSED accounts have closing_year

COMPLETED transactions have no failure_reason
FAILED transactions have failure_reason

BRANCH transactions have transaction_branch_id

EXPOSED campaign rows have exposure_date
NOT_EXPOSED rows have no response_status
```

It also prints:

- card linkage profiles;
- transaction counterparty / transfer profiles.

---

## Full audit

Running the script with no arguments executes every audit phase:

```bash
python scripts/database/audit_relational_model.py
```

This includes:

```text
schema layout
applied relational state
structure
types
value compatibility
financial precision
primary keys
constraint candidates
business rules
```

Because BTYT contains a very large transaction table, the complete audit may take substantially longer than individual phases.

---

## Final architecture decisions reflected in the audit

### `loan_monthly_snapshot` remains in `banking`

Its grain is:

```text
loan_id × year_month
```

It describes the monthly state of an individual banking contract rather than aggregated management performance.

### `account_balances` remains in `banking`

Its grain is:

```text
account_id × year_month
```

It describes the financial state of an individual account.

### `bank_monthly_performance` belongs to `performance`

Its grain is:

```text
year_month
```

It represents aggregated BTYT-level performance.

### `branch_monthly_performance` belongs to `performance`

Its grain is:

```text
branch_id × year_month
```

It represents aggregated branch-level performance.

### `bank_financials` remains in `market`

Although it contains financial performance variables, its grain is:

```text
bank_id × year
```

and it describes banks in the competitive environment rather than BTYT internal operational performance.

### `macro_environment` and `external_shocks` belong to `macro`

They represent exogenous macroeconomic and shock conditions affecting the synthetic banking world.

---

## Relationship with apply_relational_model.py

The intended workflow is:

```text
audit_relational_model.py
        │
        ▼
review audit results
        │
        ▼
apply_relational_model.py
        │
        ▼
validate_relational_model.py
```

For the current BTYT migration, the schema reorganization has already been applied successfully.

The final applied architecture is:

```text
core          4 / 4
banking       5 / 5
marketing     3 / 3
reference     2 / 2
market        5 / 5
macro         2 / 2
performance   2 / 2

Observed BTYT tables: 23 / 23
```

The applied model also retained:

```text
23 / 23 primary keys
28 / 28 foreign keys
27 / 27 CHECK constraints
11 / 11 audited NOT NULL columns
```

---

## Safety principle

The audit is intentionally read-only.

Its role is to answer:

> Does the PostgreSQL model actually satisfy the structure and rules that BTYT claims to implement?

No database object should be changed by this script.

All structural modifications remain the responsibility of:

```text
apply_relational_model.py
```

and historical constraint validation remains a separate phase.
