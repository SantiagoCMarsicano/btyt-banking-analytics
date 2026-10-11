# BTYT Banking Analytics — Documentation

This directory is the documentation layer for **BTYT Banking Analytics — Part I: Business Intelligence & Performance Management**.

It is organized by responsibility instead of duplicating the same project status in multiple files.

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

## Current project checkpoint — 2026-10-11

### Canonical analytical world

```text
World name     : BTYT
Variant        : 1
World path     : worlds/BTYT/01
Registry ID    : BTYT-01-3839777825
Registry seed  : 3839777825
Customers      : 107,253
Observation    : 2021-01 → 2026-12
```

The canonical world identity above comes from the world registry and the materialized BTYT/01 dataset currently used by PostgreSQL and Power BI.

### Current risk / performance engines

```text
Loan master                  V5.2.0 FINAL RISK CALIBRATION
Loan monthly snapshot        V4.2 RISK RECALIBRATED
Branch performance engine    V3.2.0
```

The October 2026 recalibration changed the loan master, monthly credit-risk history and downstream performance layer. The PostgreSQL database was subsequently reloaded from the current canonical files.

### PostgreSQL

Current final relational architecture:

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

On 2026-10-11 the canonical full refresh completed successfully:

```text
23 / 23 physical tables reloaded
row-count validation PASS
ANALYZE PASS
analytics materialized views refreshed
```

The refresh preserves the existing relational structure: schemas, table definitions, PKs, FKs, CHECK / NOT NULL constraints, indexes and SQL views.

### Power BI

Current page status:

| Page | Status |
|---|---|
| 01 — Resumen Ejecutivo | Functionally closed |
| 02 — Sucursales | Functionally closed |
| 03 — Clientes y Cuentas | Functionally closed |
| 04 — Riesgo de Crédito | KPI row complete; analytical visuals in progress |
| 05 — Transacciones y Canales | Pending |
| 06 — Mercado y Campañas | Pending |

Final visual polishing is intentionally deferred until the functional build of all pages is complete.

## Important reproducibility check before the next dataset freeze

The active-world path and the world-level RNG configuration must identify the **same** world before a new manifest is generated.

The current repository history shows two separate mechanisms:

```text
config/active_world.json
    → chooses the physical world path

config/world_config.json
    → supplies load_world() with world seed / observation settings
```

During the 2026-10-11 performance regeneration, the engine reported seed `3165889979` while loading `worlds/BTYT/01` inputs, whereas the registry identifies BTYT/01 with seed `3839777825`.

Therefore:

> **Do not issue a new final dataset manifest/fingerprint until `active_world.json` and `world_config.json` are synchronized to BTYT/01 and the affected RNG-driven outputs are verified.**

This is a reproducibility issue, not a PostgreSQL structural issue. The database full refresh itself completed correctly from the files supplied to it.

## Current Part I delivery strategy

The first portfolio-ready Part I release prioritizes:

```text
PostgreSQL + SQL
Power BI + DAX
Python
Excel
Tableau
```

Apache Superset and Docker are not part of the current Part I release. Pentaho remains a later option for the deliberately “dirty world” / ETL practice module rather than a dependency of the current banking dashboard.

## Documentation rules

1. **Do not duplicate project status across every folder.** This file is the main status index.
2. Domain files document stable semantics; they should not become daily logs.
3. Current implementation details belong in the relevant technical folder (`dbprocess/`, `powerbi/`, etc.).
4. Historical design documents may describe superseded decisions, but must label them clearly when they are no longer current.
5. Materialized-world figures should not be presented as regulatory or real-bank facts: BTYT is synthetic.
