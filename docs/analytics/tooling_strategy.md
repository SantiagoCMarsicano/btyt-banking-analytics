# BTYT Part I — Tooling Strategy

## 1. Purpose

This document defines the current tool ownership for **BTYT Banking Analytics — Part I**.

The goal is not maximum tool count. The goal is a coherent portfolio in which each tool has a clear analytical role.

> **Build reusable logic once, analyze at the appropriate grain, and avoid recreating the same dashboard or business rule in multiple tools.**

## 2. Current Part I stack

The portfolio-ready Part I release uses:

```text
Python
PostgreSQL + SQL
Power BI + DAX
Excel
Tableau
```

Supporting technologies already used by the project include Pandas, NumPy, PyArrow/Parquet, Psycopg/SQLAlchemy and Git/GitHub.

### Not in the current Part I release

```text
Apache Superset
Docker / Docker Compose
```

They may be revisited later if they solve a concrete portfolio or reproducibility problem, but they are not current delivery dependencies.

Pentaho is also not part of the current dashboard path. It remains a possible tool for the later deliberately “dirty world” / ETL practice module.

## 3. Current phase — 2026-10-11

```text
Synthetic world / generators        implemented
PostgreSQL relational model         implemented
00–07 thematic SQL                  complete
KPI catalog                         complete
Reusable analytics views            implemented
Power BI pages 01–03                functionally closed
Power BI page 04                    in progress
Power BI pages 05–06                pending
Python analytical deliverables      pending
Excel deliverable                   pending
Tableau deliverable                 pending
```

The old “runtime SQL smoke-test pending” status is obsolete.

## 4. PostgreSQL / SQL

PostgreSQL is the central reusable analytical layer.

It owns:

- relational joins;
- stable analytical grains;
- heavy aggregation over large facts;
- reusable views / materialized views;
- common business definitions;
- structural and reconciliation checks;
- database-side reduction before BI ingestion.

SQL should not precompute every interactive dashboard combination.

### Current scale rule

The raw transaction fact contains approximately 76.8M rows.

Preferred pattern:

```text
raw PostgreSQL fact
        ↓
reusable SQL aggregation/view
        ↓
Power BI / Python / Excel / Tableau
```

Do not import the full raw transaction event table into Power BI merely because it exists.

## 5. Power Query

Power Query owns light ingestion and presentation shaping:

- PostgreSQL connection;
- column selection;
- type enforcement;
- light renaming / display shaping;
- refresh orchestration.

It should not reproduce major banking logic that already exists in SQL.

## 6. Power BI / DAX

Power BI is the **primary corporate BI surface** for Part I.

DAX owns:

- filter-context-aware ratios;
- interactive KPI calculations;
- dynamic period selection;
- portfolio shares;
- time intelligence;
- rankings;
- filter-aware comparisons.

Current page plan:

```text
01 Resumen Ejecutivo
02 Sucursales
03 Clientes y Cuentas
04 Riesgo de Crédito
05 Transacciones y Canales
06 Mercado y Campañas
```

Functional completion comes before final visual theming.

### Naming convention

```text
tables / columns / measures / DAX → English
visible titles / labels           → Spanish
```

### Currency convention

- PostgreSQL `performance.*` monetary values remain UYU-equivalent.
- Power BI presentation measures may convert them to USD with the documented annual FX convention.
- Native loan values must respect each row's currency before conversion.
- Ratios, counts and percentages are not currency-converted.

## 7. Python

Python has two distinct roles.

### Generation / engineering

Python owns the synthetic world, generator logic, audits and reproducible data production.

### Analysis

Python should be used when the question is genuinely statistical or distributional, for example:

- delinquency trajectories;
- roll/cure behavior;
- distributions and percentiles;
- outliers;
- concentration;
- correlation / exploratory regression;
- anomaly analysis;
- scenario analysis.

Python should not be added merely to duplicate a chart already handled better by Power BI.

## 8. Excel

Excel should demonstrate management and ad-hoc analytical work rather than become a second BI dashboard.

Good uses include:

- Power Query;
- PivotTables;
- management scorecards;
- variance analysis;
- formulas;
- scenario / sensitivity analysis;
- management-ready tabular reporting.

## 9. Tableau

Tableau should complement Power BI through **geographic and spatial storytelling**.

Good uses include:

- branch network;
- regional business scale;
- regional profitability;
- territorial campaign coverage;
- geographic comparisons.

Prefer a small number of strong spatial stories over a full duplicate of the Power BI report.

## 10. Decision rule

For each business question:

1. What is the required grain?
2. Does reusable/heavy preparation belong in SQL?
3. Must the result respond dynamically to BI filters? → DAX.
4. Is the task light shaping / ingestion? → Power Query.
5. Is it distributional/statistical? → Python.
6. Is it management tabular work? → Excel.
7. Is geography the central story? → Tableau.

## 11. Current KPI-tool interpretation

The KPI catalog historically used:

```text
PW = Power BI
E  = Excel
T  = Tableau
S  = Superset
P  = Python
```

Because Superset is not part of the current Part I release, current documentation reassigns Superset-primary transaction KPIs to **Power BI** where they fit the planned `Transacciones y Canales` page.

The catalog remains an analytical priority map, not a requirement to implement every KPI in its originally proposed tool.

## 12. Anti-duplication rules

Avoid:

- rebuilding the complete Power BI report in Tableau;
- recreating SQL transformations in Power Query without reason;
- loading the full transaction fact into Power BI by default;
- creating a Python notebook for every SQL topic;
- materializing a view only because SQL can express it;
- creating a new KPI purely because one chart needs a one-off calculation.

Prefer:

```text
business question
    ↓
required grain
    ↓
reusable preparation?
    ├─ yes → SQL
    └─ no  → dynamic measure / downstream analysis
```

## 13. Backlog tools

### Apache Superset

Outside the current Part I release.

### Docker

Outside the current Part I release. Add only if a later distribution/deployment requirement justifies it.

### Pentaho

Potential later use for the deliberately broken/dirty synthetic world intended for ETL and data-cleaning practice.

## 14. Final principle

BTYT should demonstrate that tool choice follows the analytical problem.

> **One coherent banking universe, one reusable data foundation, and deliberate handoffs between SQL, BI, statistics, spreadsheets and geography.**
