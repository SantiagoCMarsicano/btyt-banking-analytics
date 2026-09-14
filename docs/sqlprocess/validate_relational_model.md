# validate_relational_model.py

## Purpose

`validate_relational_model.py` is the historical constraint-validation layer for the final BTYT PostgreSQL relational model.

It validates constraints that were created with `NOT VALID` and inspects whether the final database still satisfies the expected relational state after the migration to the **7-schema / 23-table architecture**.

The script tracks:

```text
28 foreign keys
27 CHECK constraints
55 tracked historical constraints
```

It does not create or delete data.

---

## Final schema architecture

The validator expects the final architecture to be:

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

## Updated constraint locations

The schema migration moved four tables out of `market`.

The validator now correctly expects:

```text
performance.branch_monthly_performance
    FK → core.branches.branch_id
```

and the three temporal shock constraints under:

```text
macro.external_shocks
```

Specifically:

```text
ck_external_shocks_start_peak
ck_external_shocks_peak_end
ck_external_shocks_end_recovery
```

No constraint definitions changed semantically. Only their table schema locations changed.

---

## Validation workflow

The intended sequence is:

```text
audit_relational_model.py
        │
        ▼
apply_relational_model.py
        │
        ▼
validate_relational_model.py
```

The validator is the final verification step after structural changes have been applied.

---

## Commands

### Inspect final schema layout

```bash
python scripts/database/validate_relational_model.py --schema-layout
```

Checks that all 23 tables are in the expected final schemas.

Expected output:

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

---

### Inspect validation state

```bash
python scripts/database/validate_relational_model.py --inspect
```

This is read-only.

It inspects:

- final schema layout;
- existence of every tracked FK;
- existence of every tracked CHECK;
- constraint type;
- validation state;
- total validated constraints.

Expected final state:

```text
Foreign keys validated        : 28 / 28
Check constraints validated   : 27 / 27
Tracked historical constraints: 55 / 55
Missing foreign keys          : 0
Missing CHECK constraints     : 0
FK type mismatches            : 0
CHECK type mismatches         : 0

[PASS] Historical relational validation
```

---

### Validate CHECK constraints

```bash
python scripts/database/validate_relational_model.py --check
```

For each tracked CHECK:

- verifies that the constraint exists;
- verifies that it is a CHECK constraint;
- skips it if already validated;
- otherwise runs:

```sql
ALTER TABLE ... VALIDATE CONSTRAINT ...;
```

The final inspection runs automatically afterwards.

---

### Validate foreign keys

```bash
python scripts/database/validate_relational_model.py --fk
```

For each tracked FK:

- verifies that the constraint exists;
- verifies that it is a foreign key;
- skips it if already validated;
- otherwise validates it against historical rows.

The largest transaction-related foreign keys are intentionally processed last.

---

### Validate everything

```bash
python scripts/database/validate_relational_model.py --all
```

Execution order:

```text
1. Inspect final schema layout
2. Validate CHECK constraints
3. Validate foreign keys
4. Inspect final validation state
```

This preserves the original strategy of validating smaller constraints before the very large transaction-table relationships.

---

## Foreign-key validation plan

The final model tracks **28 foreign keys**.

### Core

```text
branches.parent_branch_id
→ branches.branch_id

customers.primary_branch_id
→ branches.branch_id

accounts.customer_id
→ customers.customer_id

accounts.product_id
→ products.product_id

accounts.branch_id
→ branches.branch_id
```

### Banking

```text
cards.customer_id
→ customers.customer_id

cards.product_id
→ products.product_id

cards.linked_account_id
→ accounts.account_id

loans.customer_id
→ customers.customer_id

loans.product_id
→ products.product_id

loans.branch_id
→ branches.branch_id

account_balances.account_id
→ accounts.account_id

loan_monthly_snapshot.loan_id
→ loans.loan_id

transactions.account_id
→ accounts.account_id

transactions.transaction_branch_id
→ branches.branch_id

transactions.counterparty_institution_id
→ market.financial_institutions.institution_id
```

### Marketing

```text
campaigns.target_product_id
→ products.product_id

campaign_customers.campaign_id
→ campaigns.campaign_id

campaign_customers.customer_id
→ customers.customer_id

campaign_exposures.campaign_id
→ campaigns.campaign_id

campaign_exposures.customer_id
→ customers.customer_id
```

### Reference

```text
campaign_channels.campaign_id
→ campaigns.campaign_id

campaign_geography.campaign_id
→ campaigns.campaign_id
```

### Market

```text
bank_financials.bank_id
→ banks.bank_id

bank_market_weights.bank_id
→ banks.bank_id

bank_world_parameters.bank_id
→ banks.bank_id

financial_institutions.bank_id
→ banks.bank_id
```

### Performance

```text
branch_monthly_performance.branch_id
→ core.branches.branch_id
```

`bank_monthly_performance` remains an aggregate system-level table and has no synthetic `bank_id` foreign key.

---

## CHECK constraint validation plan

The final validator tracks **27 CHECK constraints**.

They cover:

- non-negative monetary values;
- positive loan amount and term;
- chronological opening / closing consistency;
- campaign date consistency;
- financial institution active-period consistency;
- external shock chronology;
- account / card / loan status logic;
- transaction failure logic;
- branch-channel consistency;
- transfer-scope consistency;
- campaign exposure and response consistency.

The external-shock chronology is now validated under:

```text
macro.external_shocks
```

---

## Exact validation-plan coverage

The final validator no longer relies only on counting all FK and CHECK objects found in the BTYT schemas.

It explicitly checks every planned constraint by:

```text
schema
table
constraint name
constraint type
validation status
```

This allows the script to distinguish between:

```text
VALIDATED
NOT_VALIDATED
MISSING
TYPE_MISMATCH
```

That prevents a coincidentally correct total count from hiding a missing or misplaced constraint.

---

## Already validated constraints

If a constraint is already validated, the script does not attempt to validate it again.

Example:

```text
[SKIP ] banking.transactions.fk_transactions_account: already validated
```

This makes the validator safe to rerun.

---

## Current BTYT state

After the 7-schema migration, the applied model retained:

```text
23 / 23 primary keys
28 / 28 foreign keys
27 / 27 CHECK constraints
11 / 11 audited NOT NULL columns
23 / 23 tables
```

The final historical validation target remains:

```text
28 / 28 foreign keys validated
27 / 27 CHECK constraints validated
55 / 55 tracked historical constraints
```

---

## Safety principles

The validator follows four rules.

### Existing constraints only

It never creates FK or CHECK constraints.

### No data mutation

It does not insert, update, or delete data.

### Exact object verification

A constraint must exist in the expected schema and table and have the expected PostgreSQL constraint type.

### Idempotent reruns

Already validated constraints are skipped.

---

## Recommended final execution

After saving the updated script as:

```text
scripts/database/validate_relational_model.py
```

first run:

```bash
python scripts/database/validate_relational_model.py --inspect
```

If the output shows the expected 7-schema layout and all constraints are already validated, no further action is needed.

If any tracked constraints remain `NOT_VALIDATED`, run:

```bash
python scripts/database/validate_relational_model.py --all
```

The final success condition is:

```text
23 / 23 tables in the expected schemas
28 / 28 foreign keys validated
27 / 27 CHECK constraints validated
55 / 55 tracked historical constraints

[PASS] Historical relational validation
```
