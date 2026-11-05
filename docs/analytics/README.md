# BTYT Part I — Analytics Documentation

This folder documents the reusable analytical layer that sits between the validated PostgreSQL model and downstream tools such as Power BI, Python, Excel and Tableau.

The analytical principle is:

> **Build reusable logic at the appropriate grain, calculate filter-aware metrics where they belong, and avoid duplicating the same business logic across tools.**

## Files

### Domain documentation

- `00_structural_context.md`
- `01_customers.md`
- `02_products_accounts.md`
- `03_loans.md`
- `04_transactions.md`
- `05_branches.md`
- `06_campaigns.md`
- `07_performance.md`

### Cross-domain documentation

- `architecture_part_i_analytical_update.md`
- `credit_risk_calibration.md`
- `kpi_catalog.md`
- `tooling_strategy.md`

## Current status — 2026-11-04

```text
Relational model                   validated / stable
00–07 thematic SQL                 complete
KPI catalog                        complete
Reusable analytics views           implemented
Python generation / validation     implemented
Power BI pages 01–06               final
Excel extension                    planned
Tableau extension                  planned
```

The Power BI report is no longer in a page-construction or visual-polish phase.

## Reusable analytics objects

The SQL view layer includes the established 00–07 objects plus later BI-oriented additions. Working-tree filenames include:

```text
00_create_analytics_schema.sql
01_bank_performance_monthly.sql
02_credit_risk_monthly.sql
03_branch_performance_monthly.sql
04_customer_account_summary.sql
05_transaction_channel_monthly_materialized.sql
06_campaign_performance.sql
07_market_performance_yearly.sql
08_usd_reporting_views.sql
09__customer_segment_monthly.sql
10_customer_debt_monthly_materialized.sql
11_customer_transaction_yearly_materialized.sql
```

The exact contract of any newly added view must be documented from its SQL source before the next analytical freeze.

## Canonical analytical sequence

```text
00 → Structural Context
01 → Customers
02 → Products & Accounts
03 → Loans & Credit Quality
04 → Transactions & Channels
05 → Branch Network & Branch Performance
06 → Campaigns & Marketing Effectiveness
07 → Bank Performance & Executive Management
```

## Cross-file semantic rules

### Master status vs historical state

Master fields such as `customer_status`, `account_status`, `card_status`, `loan_status` and branch `status` describe a cutoff / master state unless explicitly documented otherwise.

Historical monthly behavior comes from snapshot or performance facts.

### Stocks vs flows

Stocks and semi-additive measures require an explicit time rule.

Examples:

- active customers;
- active accounts;
- average deposits;
- outstanding loan balance;
- closing balances.

Flows can normally be accumulated across periods.

Examples:

- transactions;
- revenue;
- costs;
- credit loss;
- originations.

### Currency

Lower-level banking facts preserve native UYU / USD semantics.

`performance.*` monetary fields are UYU-equivalent reporting values.

Power BI converts selected reporting measures to USD using the documented annual FX convention; this presentation conversion does not change PostgreSQL storage semantics.

### Transactions

Current canonical scale:

```text
TOTAL      74,774,125
COMPLETED  72,746,246
FAILED      2,027,879
```

Semantics:

```text
FAILED     → attempted operational event
COMPLETED  → realized economic event
```

Financial transaction value uses completed transactions.

### Credit quality

Monthly credit quality is represented by `loan_monthly_snapshot` DPD and delinquency bands. Master `loan_status` is not a substitute for historical monthly delinquency.

### Campaign response

`POSITIVE` means an observed positive response; it is not automatically a product conversion.

## Current tool ownership

| Layer | Main responsibility |
|---|---|
| PostgreSQL / SQL | Stable grains, joins, reusable views, heavy aggregation, reconciliation |
| Power Query | Connection and light shaping |
| DAX / Power BI | Dynamic filter-aware measures and interactive BI |
| Python | Synthetic generation, validation and statistical analysis |
| Excel | Planned management / ad-hoc extension |
| Tableau | Planned geographic / storytelling extension |

Apache Superset is outside the current Part I release.

## Reproducibility note

Before a new dataset manifest is issued, the world path selected by `active_world.json` and the seed/settings used by `load_world()` must be synchronized. See `../README.md` for the current consistency check.
