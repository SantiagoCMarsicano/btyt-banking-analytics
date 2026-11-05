# BTYT Banking Analytics — Documentation

This directory is the documentation layer for **BTYT Banking Analytics — Part I: Business Intelligence & Performance Management**.

It is organized by responsibility so project status, analytical semantics and implementation details remain separated.

## Documentation map

| Folder | Purpose |
|---|---|
| `architecture/` | Project evolution, current architecture, dataset freeze and manifest rules |
| `analytics/` | Analytical domains, KPI definitions, SQL/view ownership and credit-risk calibration |
| `data_dictionary/` | Table-level semantic contracts and validation rules |
| `dbprocess/` | PostgreSQL relational model, full refresh, audits and validation |
| `powerbi/` | Power BI semantic model, measures and page-by-page implementation |
| `methodology/` | Statistical, mathematical and data-reliability methodology |
| `assets/` | Documentation images and project assets |

## Current project checkpoint — 2026-11-04

### Canonical analytical world

```text
World name     : BTYT
Variant        : 1
World path     : worlds/BTYT/01
Registry ID    : BTYT-01-3839777825
Registry seed  : 3839777825
Customers      : 107,253
Branches       : 37
Observation    : 2021-01 → 2026-12
```

Current canonical transaction layer:

```text
Total transactions       74,774,125
Completed transactions   72,746,246
Failed transactions       2,027,879
```

The canonical world identity comes from the world registry and the materialized BTYT/01 dataset currently used by PostgreSQL and Power BI.

### Current risk / performance engines

```text
Loan master                  V5.2.0 FINAL RISK CALIBRATION
Loan monthly snapshot        V4.2 RISK RECALIBRATED
Branch performance engine    V3.2.0
```

The October 2026 recalibration changed the loan master, monthly credit-risk history and downstream performance layer. PostgreSQL was subsequently refreshed from the current canonical files.

### PostgreSQL

Current relational architecture:

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

The established refresh process preserves schemas, table definitions, PKs, FKs, CHECK / NOT NULL constraints, indexes and normal SQL views while reloading data and refreshing analytics materialized views.

### Power BI

The six-page Power BI report is functionally complete and visually frozen for the current Part I portfolio checkpoint.

| Page | Status |
|---|---|
| 01 — Resumen Ejecutivo | Final |
| 02 — Sucursales | Final |
| 03 — Clientes y Cuentas | Final |
| 04 — Riesgo de Crédito | Final |
| 05 — Transacciones y Canales | Final |
| 06 — Mercado y Campañas | Final |

Final screenshots are stored in `docs/assets/Pag1.png` through `Pag6.png`.

The canonical analytical PBIX is:

```text
powerbi/BTYT_Banking_Analytics.pbix
```

### Part I status

Core end-to-end implementation is complete:

```text
Python generation / validation
        ↓
PostgreSQL
        ↓
SQL analytical layer
        ↓
Power BI + DAX
```

Remaining Part I extensions:

```text
Excel
Tableau
```

These extensions should reuse the same analytical universe and KPI framework rather than create independent datasets.

## Important reproducibility check before the next dataset freeze

The active-world path and the world-level RNG configuration must identify the **same** world before a new manifest is generated.

The repository contains two separate mechanisms:

```text
config/active_world.json
    → chooses the physical world path

config/world_config.json
    → supplies load_world() with world seed / observation settings
```

Project history recorded a mismatch between the BTYT/01 registry seed and a seed reported by an October 2026 regeneration.

Therefore:

> **Do not issue a new final dataset manifest/fingerprint until `active_world.json` and `world_config.json` are synchronized to BTYT/01 and the affected RNG-driven outputs are verified.**

This is a reproducibility/governance issue, not a PostgreSQL relational-structure issue.

## Current Part I delivery strategy

Implemented core:

```text
Python
PostgreSQL + SQL
Power BI + DAX
```

Planned extensions:

```text
Excel
Tableau
```

Apache Superset and Docker are not part of the current Part I release. Pentaho remains a later option for the deliberately “dirty world” / ETL practice module rather than a dependency of the current banking analytics product.

## Documentation rules

1. **Do not duplicate project status across every folder.** This file is the main status index.
2. Domain files document stable semantics; they should not become daily logs.
3. Current implementation details belong in the relevant technical folder (`dbprocess/`, `powerbi/`, etc.).
4. Historical design documents may describe superseded decisions, but must label them clearly when they are no longer current.
5. Materialized-world figures must not be presented as regulatory or real-bank facts: BTYT is synthetic.
