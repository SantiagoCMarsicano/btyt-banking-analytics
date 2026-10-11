# BTYT Banking Analytics — Project Evolution and Technical Architecture

**Project:** Banco de Treinta y Tres (BTYT) Banking Analytics  
**Document type:** Architecture history, current state and roadmap  
**Status:** Active architecture reference  
**Current phase:** Part I — Power BI implementation and analytical delivery  
**Last updated:** 2026-10-11

---

## 1. Purpose

BTYT began as a synthetic-data portfolio project and evolved into a reproducible banking analytics platform.

This document records:

- why the architecture changed;
- what is implemented today;
- which historical decisions are superseded;
- how the current Part I analytical stack fits together;
- what remains before Part I is portfolio-ready;
- how Part II will reuse the same banking universe.

It is an architecture reference, not a daily progress log.

---

## 2. Project vision

BTYT — Banco de Treinta y Tres — is a fictional Uruguayan commercial bank used to demonstrate an integrated workflow across:

- synthetic data generation;
- banking/economic modeling;
- data engineering;
- PostgreSQL;
- SQL analytics;
- business intelligence;
- statistics;
- later credit-risk machine learning.

All data is synthetic.

### Part I — Business Intelligence & Performance Management

Part I covers:

- customers;
- accounts and products;
- deposits;
- cards;
- loans and credit quality;
- transactions and channels;
- branches;
- campaigns;
- market context;
- bank/branch performance.

### Part II — Credit Risk Analytics & Machine Learning

Part II will reuse the same longitudinal BTYT universe for:

- target definition;
- feature engineering;
- temporal train/validation/test design;
- statistical / ML models;
- evaluation;
- explainability;
- scoring.

No unrelated replacement credit dataset is planned.

---

## 3. How BTYT evolved

The project began as a set of independent Python generators.

That was useful for exploration, but scale introduced several problems:

- duplicated path logic;
- scattered seeds;
- hardcoded observation settings;
- incompatible historical output folders;
- ambiguous smoke vs production runs;
- CSV scalability constraints;
- weak world identity;
- difficult cross-system reproducibility.

The project therefore moved toward a world-based architecture.

---

## 4. World architecture

Current concepts:

```text
world identity
    ↓
world registry
    ↓
active-world pointer
    ↓
world-relative paths
    ↓
generators / audits / outputs
```

### Registry

`worlds/registry.json` records persistent world identity.

Current canonical registry entry:

```text
world_name : BTYT
variant    : 1
seed       : 3839777825
path       : worlds/BTYT/01
status     : FROZEN (registry metadata)
```

### Active-world pointer

`config/active_world.json` selects the physical world path used by `scripts/core/paths.py`.

### World configuration

`config/world_config.json` supplies `load_world()` with:

- world name;
- seed;
- customer-population settings;
- observation dates;
- execution settings;
- reliability settings.

These two mechanisms must be synchronized.

---

## 5. Current reproducibility issue

The project currently contains a split between:

```text
active_world.json
    → physical path

world_config.json
    → RNG / world settings
```

During the 2026-10-11 branch-performance regeneration, the process loaded BTYT/01 input files but reported seed:

```text
3165889979
```

while the canonical registry identifies BTYT/01 with:

```text
3839777825
```

This must be resolved before a new canonical manifest/fingerprint is issued.

### Consequence

The current PostgreSQL/Power BI state is internally loaded and operational, but RNG-driven recalibrated outputs must be reverified once configuration identity is synchronized.

This is now a known reproducibility issue rather than an undocumented ambiguity.

---

## 6. Canonical analytical world currently in use

Materialized analytical scale:

```text
customers                    107,253
accounts                     228,945
cards                        297,775
loans                        233,441
loan-month snapshots       4,109,490
account-month balances     7,525,724
transactions              76,799,360
branches                         37
observation months               72
```

Observation period:

```text
2021-01 → 2026-12
```

---

## 7. Synthetic-data generation architecture

The canonical orchestration remains organized around 15 stages:

```text
01 macro
02 banks
03 financial_institutions
04 branches
05 customers
06 accounts
07 cards
08 loans
09 loan_snapshot
10 external_shocks
11 transactions
12 campaigns
13 branch_performance
14 operational_exports
15 cross_system_audit
```

The system uses world-relative output paths and generator-specific RNG namespaces.

The intended principle remains:

> **Technical chunk size must not define the synthetic world.**

---

## 8. Current credit-risk generators

After the October 2026 Power BI diagnostic:

```text
generate_loans.py
    V5.2.0 FINAL RISK CALIBRATION

generate_loan_monthly_snapshot.py
    V4.2 RISK RECALIBRATED
```

The recalibration corrected excessive ordinary payment failure / delinquency accumulation without introducing a fixed default or DPD target.

See:

```text
docs/analytics/credit_risk_calibration.md
```

---

## 9. Current performance engine

Current engine:

```text
generate_branch_performance.py
V3.2.0
```

The 2026-10-11 regeneration produced:

```text
branch-month rows : 2,664
bank-month rows   : 72
branch→bank reconciliation : PASS
validation                 : PASS
```

Business-result diagnostics are suppressed by default so technical generation does not spoil analytical findings before BI exploration.

---

## 10. PostgreSQL relational architecture

Final physical architecture:

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

The relational model contains the established PK/FK, semantic-type, precision and constraint layer documented under:

```text
docs/dbprocess/
```

---

## 11. PostgreSQL full-refresh architecture

The current `scripts/database/load_postgresql.py` is no longer the historical five-schema ingestion loader.

It now refreshes the existing final 23-table model:

```text
preflight
    ↓
TRUNCATE all 23 tables
    ↓
COPY reload
    ↓
row-count validation
    ↓
ANALYZE
    ↓
commit
    ↓
refresh analytics materialized views
```

The loader preserves the relational structure.

Latest successful run:

```text
2026-10-11
BTYT FULL REFRESH: PASS
23 / 23 tables reloaded
```

---

## 12. Analytical SQL architecture

Thematic analysis:

```text
00 Structural Context
01 Customers
02 Products & Accounts
03 Loans & Credit Quality
04 Transactions & Channels
05 Branch Network & Branch Performance
06 Campaigns & Marketing Effectiveness
07 Bank Performance & Executive Management
```

A separate analytics-view layer provides reusable objects for Power BI and other consumers.

The principle is:

```text
raw fact
    ↓
stable reusable SQL grain
    ↓
dynamic measure / downstream analysis
```

---

## 13. Power BI architecture

Power BI is the primary Part I BI deliverable.

Current semantic model contains 15 tables.

Current page status:

```text
01 Resumen Ejecutivo         closed functionally
02 Sucursales                closed functionally
03 Clientes y Cuentas        closed functionally
04 Riesgo de Crédito         KPI row complete / visuals in progress
05 Transacciones y Canales   pending
06 Mercado y Campañas        pending
```

Final theming is intentionally deferred until functional completion.

---

## 14. Current BI conventions

### Naming

```text
technical model objects → English
visible report labels   → Spanish
```

### Currency

- performance source values: UYU-equivalent;
- Power BI presentation: selected measures converted to USD;
- native loan USD values remain USD;
- UYU loan values use explicit annual FX conversion.

### Time

Stocks and flows are treated differently.

Customer/account active-window logic and portfolio stock averages use explicit window semantics rather than blind month summation.

---

## 15. Current risk page checkpoint

Current headline risk KPIs after refresh:

```text
Exposición crediticia          ≈ US$4.338B
Exposición 90+ DPD              5.16%
Cartera reestructurada          0.64%
Pérdida crediticia / cartera    0.63%
```

These are synthetic management analytics.

---

## 16. Tooling strategy for the current Part I release

Implemented / planned in the active release:

```text
PostgreSQL + SQL
Power BI + DAX
Python
Excel
Tableau
```

### Not part of the current Part I release

```text
Apache Superset
Docker / Docker Compose
```

Pentaho remains a later option for the deliberately dirty-world / ETL practice exercise.

This supersedes earlier architecture documents that treated Superset/Docker as active Part I milestones.

---

## 17. Operational data reliability

BTYT retains the conceptual distinction:

```text
synthetic truth
vs
operational representation
```

The reliability layer may introduce controlled imperfections while protecting core relational and economic truths.

This remains a separate methodological feature from the current Power BI clean analytical layer.

---

## 18. Manifest and dataset freeze

The project includes a manifest/fingerprint mechanism.

A prior dataset release was frozen, but the October 2026 risk/performance regeneration changed materialized files.

Therefore:

> **The old manifest is not proof that the current recalibrated files match the previously frozen fingerprint.**

Before a new freeze:

1. synchronize active-world and world-config identity;
2. verify/rerun affected RNG-driven generators;
3. rerun required audits;
4. regenerate the manifest;
5. run manifest verification;
6. only then mark the new data state frozen.

---

## 19. Git policy

Git should primarily preserve:

- code;
- configuration;
- world registry/identity;
- documentation;
- Power BI deliverables through Git LFS where intended.

Very large reproducible generated data should not be committed merely to reproduce the world.

Smoke-test material should not be mixed into the canonical commit.

---

## 20. Current repository / documentation priorities

Current technical priorities:

```text
1. finish Power BI Page 04
2. build Pages 05–06
3. final visual polish
4. complete/update documentation
5. resolve world-config / active-world seed synchronization
6. reverify affected generated layers
7. regenerate manifest/fingerprint
8. finish remaining Part I deliverables
```

---

## 21. Part I remaining analytical deliverables

After Power BI:

- focused Python analysis;
- advanced Excel management workbook;
- Tableau geographic storytelling;
- final portfolio documentation.

These deliverables should complement rather than duplicate one another.

---

## 22. Part II boundary

Part II begins only after the Part I analytical universe is stable enough to define credit-risk targets without leakage.

Core requirements:

- explicit observation window;
- explicit performance window;
- temporal splitting;
- no post-default leakage;
- reproducible feature extraction;
- consistent use of the BTYT longitudinal universe.

---

## 23. Superseded historical states

The following are historical and no longer describe the current project:

```text
BTYT33 as the canonical analytical world
63,205 customers as the current canonical population
canonical generation still in progress
SQL runtime smoke test still pending
Superset as an active Part I deliverable
Docker as an active Part I deliverable
five-schema PostgreSQL loader as the current load architecture
```

They may remain relevant to project history but must not be presented as current state.

---

## 24. Final architecture principle

BTYT has moved from:

```text
independent generators
        ↓
reproducible world architecture
        ↓
validated relational database
        ↓
reusable analytical SQL
        ↓
Power BI / downstream analytics
```

The core value of the project is not the number of technologies.

It is the coherence between:

- synthetic mechanisms;
- reproducibility;
- banking semantics;
- relational integrity;
- analytical grain;
- business questions;
- downstream presentation.

The immediate objective is to finish Part I as a portfolio-ready analytical product while preserving enough reproducibility that Part II can build on the same universe.
