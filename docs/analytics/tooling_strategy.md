# BTYT Part I — Analytics Tooling Strategy

## 1. Purpose

BTYT Part I is a banking analytics portfolio project built to demonstrate both analytical depth and cross-tool competence without duplicating the same work everywhere.

The strategy is:

> **Use each tool where it is strongest, while PostgreSQL remains the common analytical foundation.**

---

## 2. Architecture at a glance

```text
Synthetic data generators
        ↓
PostgreSQL — frozen relational model
        ↓
00–07 thematic SQL analytics
        ↓
Reusable analytical bases / justified views
        ↓
┌──────────────────────────────────────────────┐
│ Python   → statistics / exploration          │
│ Excel    → management / ad hoc               │
│ Power BI → corporate BI + DAX                │
│ Tableau  → geography / spatial storytelling  │
│ Superset → SQL-first operational monitoring  │
└──────────────────────────────────────────────┘
        ↓
Docker / optional DQ-Pentaho / publication
```

---

## 3. Current phase

```text
PostgreSQL relational model        ✅
SQL files 00–07                    ✅ designed
Static / semantic audit            ✅
Runtime smoke test                 ⏳
SQL freeze                         pending PASS
```

The immediate next step after runtime validation is not to reopen relational design.

It is to freeze SQL, define the KPI catalog and select the small number of reusable views actually needed downstream.

---

## 4. PostgreSQL + SQL

### Main responsibility

PostgreSQL owns shared analytical logic.

Use it for:

- joins;
- reusable flags;
- lifecycle and cohorts;
- customer/account/loan analytical bases;
- transaction reduction;
- branch and bank performance preparation;
- campaign funnel bases;
- data-quality checks;
- accounting identities;
- reconciliation.

### Development interface

DBeaver remains the practical primary SQL interface.

VS Code may support repository work and documentation.

pgAdmin is optional rather than mandatory.

### Performance rule

Do not create indexes or materialized views speculatively.

Use:

```text
EXPLAIN
EXPLAIN ANALYZE
```

after identifying a real recurring workload.

For `04_transactions.sql`, work section-by-section because the transaction table contains ~76.8M rows.

---

## 5. Python + Pandas + Jupyter

### Main responsibility

Python owns questions where SQL stops being the natural analytical environment.

Examples:

- distributions;
- medians / percentiles;
- outlier analysis;
- concentration;
- statistical segment comparisons;
- delinquency trajectories;
- roll-rate exploration;
- campaign saturation;
- performance decomposition;
- anomaly detection;
- forecasting / scenarios.

### Rule

No artificial symmetry:

```text
one SQL file ≠ one Python file
```

Create Python notebooks only when the question benefits from Python.

---

## 6. Excel

### Main responsibility

Excel demonstrates management and spreadsheet competence.

Use:

- PivotTables / PivotCharts;
- XLOOKUP;
- SUMIFS / COUNTIFS / AVERAGEIFS;
- Power Query;
- slicers;
- conditional formatting;
- management scorecards;
- monthly variance tables;
- scenario / sensitivity work.

### VBA vs Python in Excel

```text
VBA / macros
→ workbook automation

Python in Excel
→ analytical computation
```

Python in Excel does not replace VBA.

A strong BTYT Excel deliverable should still visibly demonstrate advanced Excel capability.

---

## 7. Power BI

### Main responsibility

Power BI is the principal corporate BI product.

Suggested pages:

1. Executive Overview
2. Customer 360
3. Products & Accounts
4. Loans & Credit Quality
5. Transactions & Channels
6. Branch Performance
7. Campaign Performance / response summary

### DAX ownership

DAX should own dynamic metrics such as:

- shares;
- response/exposure rates;
- delinquency rates;
- Cost-to-Income;
- revenue per customer;
- branch contribution;
- MoM / YoY;
- rolling periods;
- YTD measures.

Do not preaggregate every slicer combination in SQL.

---

## 8. Tableau

### Main responsibility

```text
Geography + spatial storytelling
```

Strong candidates:

- branch network map;
- regional deposits / lending;
- branch performance geography;
- campaign coverage;
- response geography.

Prefer 1–2 strong Tableau deliverables rather than duplicating Power BI.

---

## 9. Apache Superset

### Main responsibility

```text
Operational / SQL-first monitoring
```

Strong candidates:

- transaction activity;
- failure monitoring;
- channel activity;
- operational PostgreSQL aggregates.

Superset should demonstrate direct database interaction rather than reproduce the complete executive Power BI product.

---

## 10. Docker

### Main responsibility

Reproducibility.

Potential final environment:

```text
Docker Compose
├── PostgreSQL
├── Superset
└── supporting services
```

Add Docker when it materially improves reproducibility; it is not an analytical tool.

---

## 11. Pentaho / Data Quality

Pentaho remains optional and late-stage.

A useful demonstration would work on controlled dirty copies rather than modifying the canonical database.

Possible pattern:

```text
clean canonical data
        ↓
controlled dirty sample
        ↓
Pentaho / DQ pipeline
        ↓
validated clean output
```

Possible issues:

- NULLs;
- duplicates;
- inconsistent categories;
- malformed dates/codes;
- whitespace / capitalization problems;
- implausible values.

---

## 12. KPI strategy

A KPI is not the same thing as a dimension.

Example:

```text
Dimension → branch
KPI       → branch net income
```

Every important KPI should eventually document:

- name;
- business definition;
- numerator;
- denominator;
- grain;
- temporal semantics;
- currency semantics;
- source;
- intended interpretation.

### Important corrected KPI semantics

#### Transactions

```text
Transaction Volume
→ COMPLETED amounts only

Failure Rate
→ FAILED attempts / all attempts
```

#### Campaigns

Prefer:

- Exposure Rate;
- Observed Response Rate;
- Positive Response Rate.

Do **not** label a positive response as `Campaign Conversion Rate` unless a separate product-conversion event/window is explicitly defined.

#### Performance

Respect:

```text
flows  → additive through time
stocks → semi-additive
```

---

## 13. Primary ownership matrix

| Analytical theme | Primary tool |
|---|---|
| Shared transformations / joins | PostgreSQL / SQL |
| Customer/account/loan reusable bases | PostgreSQL / SQL |
| Large transaction reduction | PostgreSQL / SQL |
| Dynamic KPI measures | DAX |
| Statistical exploration | Python |
| Distribution / outlier work | Python |
| Management / ad hoc | Excel |
| Executive banking BI | Power BI |
| Geography | Tableau |
| Operational monitoring | Superset |
| Reproducibility | Docker |
| Optional dirty-data ETL demo | Pentaho |

---

## 14. Anti-duplication rules

Avoid:

- implementing the same KPI independently in every tool;
- building one Python artifact per SQL file;
- rebuilding the Power BI dashboard in Tableau;
- turning Power Query into a hidden second warehouse;
- creating views with no reuse case;
- loading the full transaction fact into Power BI by default;
- adding technologies only to increase the tool count.

---

## 15. Business-question-first workflow

```text
1. Define the business question
2. Define the analytical grain
3. Explore / validate in SQL
4. Decide whether reusable logic is justified
5. Define the KPI or analytical measure
6. Assign the primary tool
7. Build the final output
8. Validate interpretation
```

---

## 16. Current execution order

After the SQL runtime smoke test:

```text
1. Freeze SQL 00–07
2. Define KPI catalog
3. Decide justified views / materialized views
4. Python statistical analyses where useful
5. Excel management workbook
6. Power BI semantic model + DAX + dashboard
7. Tableau geographic story
8. Superset operational dashboard
9. Query-plan review / evidence-based indexes
10. Docker reproducibility
11. Optional DQ + Pentaho
12. Final documentation / portfolio publication
```

This is a guide, not a requirement to finish every tool before making progress in another.

---

## 17. Final guiding principle

> **Build once at the data layer.  
> Analyze where it makes sense.  
> Visualize where it communicates best.  
> Do not duplicate without purpose.**
