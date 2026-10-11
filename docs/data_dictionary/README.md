# BTYT Data Dictionary

This directory contains the semantic contracts for the datasets that make up the BTYT Banking Analytics synthetic universe.

## Canonical world context

Current analytical world:

```text
World name     : BTYT
Variant        : 1
World path     : worlds/BTYT/01
Registry ID    : BTYT-01-3839777825
Registry seed  : 3839777825
Customers      : 107,253
Observation    : 2021-01 → 2026-12
```

Paths such as `data/generated/...`, `data/interim/...` and `data/operational/...` are world-relative and resolve beneath the active world directory.

## Final PostgreSQL physical tables

The current Part I relational model contains 23 physical tables across seven schemas.

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

Not every physical table has a dedicated dictionary in this folder yet; some are documented in the analytical / database-process layers.

## Naming convention

Table dictionaries normally follow:

```text
<table_name>_data_dictionary.md
```

The cross-system audit document is an integrated validation contract rather than a PostgreSQL physical table dictionary.

## Historical / non-materialized design references

Two files are retained because they document earlier card-model design work:

```text
card_monthly_snapshot_data_dictionary.md
credit_card_transactions_data_dictionary.md
```

These do **not** describe physical tables in the current 23-table Part I PostgreSQL model.

The current Part I banking model uses:

```text
banking.cards
banking.transactions
```

for the implemented card relationship / transaction layer.

## Current credit-risk contracts

Current generator versions:

```text
generate_loans.py                   V5.2.0 FINAL RISK CALIBRATION
generate_loan_monthly_snapshot.py   V4.2 RISK RECALIBRATED
```

The dictionaries define semantics and invariants; current realized risk figures are documented separately in:

```text
../analytics/credit_risk_calibration.md
```

## Reproducibility note

Before a new dataset freeze, verify that `config/active_world.json` and `config/world_config.json` describe the same BTYT world and seed.

The table dictionaries should remain stable semantic contracts rather than logs of transient runtime output.
