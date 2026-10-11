# BTYT Architecture Update — Part I Analytical Layer

## 1. Purpose

This document defines the **current** analytical ownership model for BTYT Part I after completion of the relational model, thematic SQL layer, KPI catalog, reusable analytics objects and the first Power BI pages.

The governing principle is:

> **Build once at the data layer. Analyze where it makes sense. Visualize where it communicates best. Do not duplicate without purpose.**

## 2. Final PostgreSQL architecture

The analytical layer sits on the validated seven-schema relational model:

```text
core
banking
marketing
reference
market
macro
performance
```

Physical table distribution:

```text
core          4
banking       5
marketing     3
reference     2
market        5
macro         2
performance   2
----------------
total        23
```

PostgreSQL is the central reusable analytical data layer.

It owns:

- relational joins;
- stable analytical grains;
- reusable dimensions and analytical bases;
- heavy aggregation over large facts;
- shared business definitions;
- reconciliation;
- performance-sensitive transformations.

It does not need to precompute every dashboard combination.

## 3. Canonical thematic SQL map

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

`07` is the executive synthesis layer, not a replacement for the detailed analyses in `01–06`.

## 4. Reusable analytics layer

The project also contains an `analytics` schema with normal and materialized views used by downstream BI.

Current working-tree SQL includes objects for:

- bank monthly performance;
- credit risk;
- branch monthly performance;
- customer account summary;
- transaction/channel monthly aggregation;
- campaign performance;
- market performance;
- USD reporting;
- customer monthly/segment/debt/transaction summaries.

Normal views reflect base-table refreshes automatically.

Materialized views require an explicit refresh after source data changes; the current full-refresh loader handles analytics materialized views after the physical-table transaction commits.

## 5. Canonical analytical grains

Examples:

```text
customer
account
account × month
loan
loan × month
transaction event
branch
branch × month
campaign
campaign × customer
bank × month
```

No reusable analytical object should be created until its grain is explicit.

## 6. Cross-layer semantic rules

### Master status vs historical state

Master status fields are cutoff attributes unless explicitly documented otherwise.

Historical monthly state belongs to snapshots and performance facts.

### Current vs lifetime relationships

Historical ownership and current ownership are distinct analytical concepts.

```text
loan history != currently open loan
total cards != active cards
historical account count != active account count
```

### Currency

Lower-level native monetary data preserves UYU / USD semantics.

`performance.*` values are UYU-equivalent reporting values.

The current Power BI presentation layer converts selected measures to USD with explicit annual FX logic.

### Stock vs flow

Stocks and semi-additive values require an explicit time rule.

Flows can normally be accumulated.

### Transactions

```text
FAILED    → attempted operation
COMPLETED → realized economic operation
```

### Campaigns

```text
POSITIVE response != product conversion
```

## 7. Analytical tool ownership

### PostgreSQL / SQL

Owns reusable preparation, joins, heavy reduction, stable grains, consistency checks and reconciliation.

### Power Query

Owns connection, type handling and light presentation shaping.

### Power BI / DAX

Owns interactive, filter-aware BI metrics and is the primary Part I dashboard product.

### Python

Owns statistical / distributional / trajectory analysis when it adds value beyond BI.

### Excel

Owns management and ad-hoc tabular analysis.

### Tableau

Owns geographic / spatial storytelling.

Apache Superset and Docker are not part of the current Part I release.

## 8. Transaction-scale architecture

The raw transaction fact contains approximately 76.8M rows.

Preferred pattern:

```text
banking.transactions
        ↓
PostgreSQL aggregation / reusable reduced dataset
        ↓
Power BI / Python / Excel / Tableau
```

Do not import the full transaction fact into Power BI by default.

## 9. Performance-layer architecture

`performance.branch_monthly_performance` and `performance.bank_monthly_performance` are management reporting layers.

At a given month:

```text
branch totals
→ reconcile to bank total
```

Across time:

```text
flows  → SUM
stocks → end-of-period / monthly average / explicitly defined rule
```

Current performance engine:

```text
generate_branch_performance.py
V3.2.0
```

The October 2026 regeneration reconciled 2,664 branch-month rows to 72 bank-month rows and passed validation.

## 10. Credit-risk architecture

Current risk engines:

```text
generate_loans.py                   V5.2.0 FINAL RISK CALIBRATION
generate_loan_monthly_snapshot.py   V4.2 RISK RECALIBRATED
```

The risk page uses the monthly loan snapshot for DPD/exposure and master loan status only for cutoff contractual status.

See `credit_risk_calibration.md` for the October 2026 recalibration record.

## 11. PostgreSQL refresh architecture

The current `scripts/database/load_postgresql.py` is a **full refresh loader for the existing relational model**.

It performs:

```text
preflight
    ↓
single multi-table TRUNCATE
    ↓
COPY reload of 23 tables
    ↓
row-count validation
    ↓
ANALYZE
    ↓
commit
    ↓
refresh analytics materialized views
```

It preserves the relational structure rather than dropping/recreating the 23 tables.

## 12. Current Power BI model

The Power BI model currently uses 15 tables, including:

- `_Measures`;
- `Analysis Window`;
- `Bank Performance`;
- `Branch Performance`;
- `Campaign Performance`;
- `Credit Risk`;
- `Customer Accounts`;
- `Customer Monthly`;
- `Customer Ranking Metric`;
- `DimCustomerType`;
- `DimDate`;
- `DimRelationshipDepth`;
- `Market Performance`;
- `Portfolio Metric`;
- `Transactions and Channels`.

`Market Performance` and `Campaign Performance` remain intentionally disconnected where their grain does not justify a forced relationship.

## 13. Current Power BI pages

```text
01 Resumen Ejecutivo         functionally closed
02 Sucursales                functionally closed
03 Clientes y Cuentas        functionally closed
04 Riesgo de Crédito         KPI row complete / visuals in progress
05 Transacciones y Canales   pending
06 Mercado y Campañas        pending
```

Final visual theming is deferred until the functional build is complete.

## 14. Current analytical flow

```text
Synthetic BTYT universe
        ↓
validated PostgreSQL relational model
        ↓
00–07 thematic SQL + analytics views
        ↓
KPI catalog
        ↓
Power BI + DAX
        ↓
Python / Excel / Tableau deliverables
        ↓
Part I portfolio publication
```

## 15. Current project status — 2026-10-11

```text
Relational model                  ✅
23-table full refresh             ✅
00–07 thematic SQL                ✅
KPI catalog                       ✅
Analytics views                   ✅
Power BI pages 01–03              ✅ functional
Power BI page 04                  🟡 in progress
Power BI pages 05–06              ⏳
Python / Excel / Tableau          ⏳
Final visual polish               ⏳
New manifest / fingerprint        ⏳ after reproducibility check
```

## 16. Reproducibility issue before the next freeze

The path selected by `active_world.json` and the world seed/settings loaded from `world_config.json` must be synchronized.

The current BTYT registry identifies:

```text
BTYT / variant 1 / seed 3839777825
```

but the 2026-10-11 performance regeneration reported seed:

```text
3165889979
```

while loading BTYT/01 data.

This does not invalidate the relational full refresh, but it does mean RNG-driven regenerated layers must be reverified before issuing a new manifest/fingerprint.

## 17. Final principle

BTYT should demonstrate analytical judgment, not maximum tool count.

> **One coherent data architecture, one primary analytical home per question, and deliberate handoffs between tools.**
