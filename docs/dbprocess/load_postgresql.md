# `load_postgresql.py` — Canonical Full Refresh

## Purpose

The current `scripts/database/load_postgresql.py` refreshes the data in the **existing final BTYT PostgreSQL model** from the materialized canonical files under:

```text
worlds/BTYT/01/data/generated
```

Its current contract is:

> **Replace the data in all 23 physical BTYT tables while preserving the relational structure already defined in PostgreSQL.**

It no longer uses the historical five-schema staging layout.

## What the loader preserves

The refresh does not drop/recreate the target tables.

It preserves:

- schemas;
- table definitions;
- semantic PostgreSQL types;
- primary keys;
- foreign keys;
- CHECK constraints;
- audited NOT NULL constraints;
- indexes;
- normal SQL views.

Materialized views in the `analytics` schema are refreshed after the base-table transaction commits.

## Final schema mapping

| Schema | Tables |
|---|---:|
| `core` | 4 |
| `banking` | 5 |
| `marketing` | 3 |
| `reference` | 2 |
| `market` | 5 |
| `macro` | 2 |
| `performance` | 2 |
| **Total** | **23** |

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

## Source formats

Supported source formats:

```text
.parquet
.csv
```

When both representations exist for one logical dataset, Parquet is preferred.

## Dataset discovery

The loader recursively discovers files under:

```text
worlds/BTYT/01/data/generated
```

It validates the discovered set against the expected 23 logical tables.

The preflight fails before data modification if:

- an expected dataset is missing;
- an unexpected generated dataset has no table mapping;
- a target physical table does not exist;
- source and target columns are incompatible.

## Identifier preservation

CSV identifiers matching:

```text
id
*_id
```

are explicitly read as strings.

This preserves identifiers such as:

```text
001
```

instead of coercing them to:

```text
1
1.0
```

This rule is required for branch IDs and other foreign-key identifiers with meaningful leading zeros.

## Preflight

Before truncation, the loader checks every table and reports:

```text
current PostgreSQL row count
source row count
source file
column compatibility
```

The preflight is read-only.

A successful preflight reports:

```text
Preflight complete: 23/23 tables compatible.
```

## Explicit confirmation

The loader requires:

```text
BTYT
```

before replacing the data.

Any other input cancels the refresh.

## Transaction model

The base-table refresh is executed as one database transaction.

Conceptually:

```text
BEGIN
    ↓
TRUNCATE all 23 tables in one statement
    ↓
reload all 23 tables
    ↓
validate row counts
    ↓
ANALYZE
COMMIT
```

If an exception occurs before commit:

```text
ROLLBACK
```

This avoids leaving PostgreSQL with a partially refreshed physical model.

## Why all 23 tables are truncated together

The model contains foreign keys, including self-referential relationships such as branch parentage.

A relationally safe multi-table `TRUNCATE` avoids attempting to clear parent tables independently while dependent data still exists.

After truncation, the loader inserts parent/dimensional tables before their dependent facts.

## COPY-based loading

The loader uses PostgreSQL `COPY` for batch insertion instead of row-by-row SQL insertion.

This is important for large facts such as:

```text
banking.transactions          76,799,360 rows
banking.account_balances       7,525,724 rows
banking.loan_monthly_snapshot  4,109,490 rows
```

## Source / target type preparation

The loader does not recreate PostgreSQL types.

Instead, each source batch is prepared to match the existing target metadata.

Examples:

- integer targets are normalized to nullable integer representation before COPY;
- date targets are serialized as PostgreSQL-compatible dates;
- timestamps are normalized explicitly;
- target column order is respected.

The existing PostgreSQL schema remains authoritative for physical types.

## Post-load row-count validation

Each target must exactly match its canonical source row count.

Any mismatch raises an exception before the base-table transaction is accepted.

A final pass validates all 23 counts again.

## Planner statistics

After reloading all tables, the loader executes:

```text
ANALYZE
```

for each target table so PostgreSQL query planning reflects the new data distribution.

## Analytics materialized views

Normal SQL views update automatically because they read the refreshed base tables.

Materialized views do not.

After the base-table commit, the loader discovers materialized views in:

```text
analytics
```

and refreshes them explicitly.

On 2026-10-11 this included:

```text
analytics.customer_debt_monthly_mv
analytics.customer_monthly_mv
analytics.customer_segment_monthly_mv
analytics.transaction_channel_monthly
```

## Latest successful full refresh — 2026-10-11

The current loader completed:

```text
23 / 23 physical tables reloaded
row-count validation PASS
ANALYZE PASS
base-table transaction committed
analytics materialized views refreshed
BTYT FULL REFRESH: PASS
```

Relevant refreshed counts:

```text
core.customers                           107,253
core.accounts                            228,945
banking.cards                            297,775
banking.loans                            233,441
banking.loan_monthly_snapshot          4,109,490
banking.account_balances               7,525,724
banking.transactions                  76,799,360
performance.bank_monthly_performance         72
performance.branch_monthly_performance    2,664
```

## Current relationship with the other database scripts

### `audit_relational_model.py`

Inspects the relational model. Read-only.

### `apply_relational_model.py`

Creates/repairs the structural seven-schema model when required.

### `validate_relational_model.py`

Validates tracked historical constraints.

### Normal established-database workflow

```text
canonical source data changes
        ↓
load_postgresql.py
        ↓
full refresh into existing relational model
        ↓
analytics materialized views refreshed
        ↓
Power BI refresh
```

The structural scripts are not mandatory on every successful refresh.

## Important limitation: fresh bootstrap

The current loader expects all 23 final target tables to already exist.

It is therefore a **full-refresh loader**, not a complete empty-database bootstrap.

If BTYT later needs a one-command reconstruction from a blank PostgreSQL database, initialization / schema creation must be formalized separately.

## Reproducibility note

The loader faithfully loads the files it is given. It does not decide whether those files were generated with the correct canonical world seed.

Before the next dataset manifest/freeze, verify that:

```text
config/active_world.json
config/world_config.json
worlds/registry.json
```

are synchronized to the same BTYT world identity.

## Execution

From the repository root:

```powershell
python -m scripts.database.load_postgresql
```

The script requests the PostgreSQL password unless `BTYT_DB_PASSWORD` is already defined.

Then confirm:

```text
BTYT
```

to start the full refresh.
