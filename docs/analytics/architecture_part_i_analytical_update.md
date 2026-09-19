# BTYT Architecture Update — Part I Analytical Layer

## 1. Purpose

This document defines the final analytical ownership model for BTYT Part I after completion of the `00–07` SQL design and static/semantic audit.

The governing principle is:

> **Build once at the data layer. Analyze where it makes sense. Visualize where it communicates best. Do not duplicate without purpose.**

---

## 2. Final PostgreSQL architecture

The analytical layer sits on the frozen seven-schema relational model:

```text
core
banking
marketing
reference
market
macro
performance
```

PostgreSQL is the central reusable analytical data layer.

It owns:

- relational joins;
- stable analytical grains;
- reusable dimensions and analytical bases;
- lifecycle and cohort logic;
- heavy aggregation over large fact tables;
- shared business definitions;
- structural/data-quality diagnostics;
- reconciliation;
- performance-sensitive transformations.

It does **not** need to precompute every dashboard combination.

---

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

Each file has one principal responsibility.

`07` is the executive synthesis layer, not a replacement for the detailed analyses in `01–06`.

---

## 4. Canonical analytical grains

Examples:

```text
customer
account
account × month
card
loan
loan × month
transaction event
account × month × transaction dimensions
branch
branch × month
campaign
campaign × customer
exposure event
bank × month
```

No reusable analytical object should be created until its grain is explicit.

---

## 5. Cross-layer semantic rules

### 5.1 Master status vs historical state

Master status fields are cutoff attributes unless explicitly documented otherwise.

Examples:

- customer status;
- account status;
- card status;
- loan status;
- branch status.

Historical monthly state should come from snapshot/performance tables.

### 5.2 Current vs lifetime relationships

Historical ownership and current ownership are different analytical concepts.

Examples:

```text
loan history != currently open loan
total cards != active cards
historical account count != active account count
```

### 5.3 Currency

Lower-level native monetary data:

```text
UYU and USD remain separate
```

unless an explicit FX conversion is introduced.

Performance-layer monetary data:

```text
UYU-equivalent reporting values
```

and may be aggregated within that layer.

### 5.4 Stock vs flow

Stocks / semi-additive measures require an explicit time rule.

Flows can normally be accumulated across periods.

### 5.5 Transactions

Operational attempts and completed economic movement are different.

```text
FAILED    → attempted activity
COMPLETED → realized activity / financial volume
```

### 5.6 Campaigns

```text
exposure_status → canonical customer-level exposure
response_status → canonical customer-level response outcome
POSITIVE response != conversion
```

---

## 6. Analytical tool ownership

### PostgreSQL / SQL

Primary role:

- reusable data preparation;
- joins;
- filters;
- cohorts;
- flags;
- analytical grains;
- large-table aggregation;
- consistency checks;
- accounting/reconciliation logic.

### Power Query

Primary role:

- connection;
- column selection;
- type enforcement;
- light presentation shaping.

Avoid recreating major banking logic already defined in SQL.

### DAX

Primary role:

- filter-context-aware measures;
- shares;
- ratios;
- time intelligence;
- selected-period comparisons;
- rolling/YTD measures.

Examples:

- Cost-to-Income;
- portfolio shares;
- delinquency rate;
- response rate;
- YoY growth.

### Python / Pandas / Jupyter

Primary role:

- distributions;
- percentiles;
- outliers;
- statistical comparisons;
- correlations;
- exploratory regressions;
- trajectories;
- clustering;
- anomaly analysis;
- forecasting/scenario work.

No Python file is required merely because a SQL file exists.

### Excel

Primary role:

- management/ad-hoc analysis;
- PivotTables;
- formulas;
- Power Query;
- scorecards;
- scenario/sensitivity analysis;
- VBA for workbook automation;
- Python in Excel only when it adds distinct analytical value.

### Power BI

Primary corporate BI surface:

- semantic model;
- DAX;
- interactive executive/customer/product/loan/transaction/branch analysis.

### Tableau

Primary niche:

- geography;
- spatial storytelling;
- branch and campaign territorial analysis.

### Superset

Primary niche:

- SQL-first operational monitoring;
- direct PostgreSQL interaction;
- lightweight operational dashboards.

### Docker

Role:

- reproducibility / environment packaging.

### Pentaho

Optional late-stage role:

- controlled ETL / Data Quality demonstration.

---

## 7. Decision rule for every business question

1. **What is the required grain?**
2. **Is reusable preparation required?** → SQL.
3. **Must the metric react to BI filters?** → DAX.
4. **Is the task ingestion/light shaping?** → Power Query.
5. **Is it distributional/statistical/exploratory?** → Python.
6. **How should the result be communicated?** → Power BI / Tableau / Superset / Excel.

---

## 8. Exploratory query vs persistent object

A query remains exploratory when it is used to:

- inspect the realized world;
- test a question;
- validate a domain;
- learn SQL;
- check a possible KPI.

A view/materialized view is justified only when:

- logic is reused;
- grain is stable;
- definitions must be shared;
- query cost justifies persistence;
- downstream tools benefit.

> **Do not materialize complexity merely because SQL can express it.**

---

## 9. Transaction-scale architecture

`banking.transactions` contains ~76.8M rows in the canonical world.

Preferred flow:

```text
banking.transactions
        ↓
PostgreSQL aggregation / reusable reduced datasets
        ↓
Power BI / Superset / targeted Python extracts
```

Do not import the full raw event table into Power BI by default.

`04_transactions.sql` should be run section-by-section during exploration/performance work.

---

## 10. Performance-layer architecture

`performance.branch_monthly_performance` and `performance.bank_monthly_performance` are management reporting layers.

Their monetary fields are UYU-equivalent.

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

`07_performance.sql` is the canonical full branch-to-bank reconciliation.

---

## 11. Final analytical flow

```text
Synthetic BTYT universe
        ↓
Frozen PostgreSQL relational model
        ↓
00–07 SQL exploration + reusable analytical bases
        ↓
Runtime smoke test / SQL freeze
        ↓
KPI catalog + justified views
        ↓
├─ Python / Pandas → statistical exploration
├─ Excel           → management / ad hoc
├─ Power Query     → light ingestion
│      ↓
│  Power BI + DAX  → primary corporate BI
├─ Tableau         → geographic storytelling
└─ Superset        → operational SQL-first monitoring
        ↓
Performance tuning / indexes based on evidence
        ↓
Docker reproducibility
        ↓
Optional DQ / Pentaho module
        ↓
Portfolio publication
```

---

## 12. Current project status

At this point:

```text
Relational model                  ✅ frozen
00–07 SQL design                  ✅ complete
Static / semantic SQL audit       ✅ complete
Runtime PostgreSQL smoke test     ⏳ in progress
SQL analytical freeze             ⏳ pending runtime PASS
Downstream BI/statistics          next phase
```

---

## 13. Final principle

BTYT should demonstrate analytical judgment, not maximum tool count.

> **One coherent data architecture, one primary analytical home per question, and deliberate handoffs between tools.**
