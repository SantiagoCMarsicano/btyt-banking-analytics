# BTYT PostgreSQL Process

This folder documents the PostgreSQL lifecycle used by BTYT Part I.

## Current relational architecture

```text
core          4 tables
banking       5 tables
marketing     3 tables
reference     2 tables
market        5 tables
macro         2 tables
performance   2 tables
----------------------
total        23 tables
```

The current database already has its relational model applied: schemas, semantic types, PKs, FKs, CHECK / NOT NULL constraints and indexes exist.

## Current scripts

### `load_postgresql.py`

Current role: **full refresh of the existing 23-table relational model**.

It preserves table definitions and reloads only the data.

It performs:

```text
preflight
→ multi-table TRUNCATE
→ COPY reload
→ row-count validation
→ ANALYZE
→ commit
→ analytics materialized-view refresh
```

It is not the historical five-schema ingestion loader anymore.

### `audit_relational_model.py`

Read-only inspection of the database structure and relational contract.

### `apply_relational_model.py`

Applies / repairs the seven-schema relational model and constraints when required.

This is structural migration logic, not part of every normal data refresh.

### `validate_relational_model.py`

Validates the tracked FK / CHECK constraints and final relational state.

## Targeted reload scripts

Temporary / targeted reload utilities such as `scripts/sql/reload/reload_performance_postgresql.py` are not part of the canonical database-refresh path now that `load_postgresql.py` performs a validated full refresh of the established model.

Prefer one canonical loader over accumulating one-off reload scripts.

## Normal refresh workflow

For the current established BTYT database:

```text
regenerate changed canonical data
        ↓
run load_postgresql.py
        ↓
23-table full refresh
        ↓
materialized views refresh
        ↓
Power BI refresh
```

Do **not** rerun schema migration simply because the data was refreshed successfully.

## Fresh empty-database bootstrap

The current `load_postgresql.py` assumes the 23 target tables already exist with their final types and constraints.

Therefore an empty PostgreSQL database bootstrap is a separate concern from the normal full-refresh workflow. Do not describe the current loader as a complete zero-to-database bootstrap script unless that capability is explicitly reintroduced.

## Latest full refresh — 2026-10-11

```text
Preflight                        23 / 23 compatible
TRUNCATE                         PASS
Reload                           23 / 23
Row-count validation             PASS
ANALYZE                          PASS
Transaction commit               PASS
Analytics materialized views     refreshed
```

Notable refreshed row counts:

```text
banking.loans                        233,441
banking.loan_monthly_snapshot      4,109,490
banking.account_balances           7,525,724
banking.transactions              76,799,360
performance.bank_monthly_performance      72
performance.branch_monthly_performance 2,664
```

## Safety rule

The full refresh uses the existing schema and does not drop/recreate the physical tables.

If the load fails inside the transaction, PostgreSQL rolls back the base-table refresh.
