<p align="center">
  <img src="docs/assets/logo.png" alt="BTYT Banking Analytics" width="240">
</p>

<h1 align="center">BTYT Banking Analytics</h1>

<p align="center">
  <strong>End-to-end synthetic banking analytics project built around a fictional Uruguayan commercial bank.</strong>
</p>

<p align="center">
  Python · PostgreSQL · SQL · Power BI · Excel · Tableau · Credit Risk / ML
</p>

## Overview

**Banco de Treinta y Tres (BTYT)** is a fictional Uruguayan commercial bank created as the analytical universe for an end-to-end portfolio project.

The project connects synthetic data generation, relational modeling, SQL analytics, KPI design, business intelligence and, in Part II, credit-risk modeling. All data is synthetic, but the system is designed to preserve coherent relationships, temporal dynamics, business rules, accounting identities and operational behavior.

> Fiction, yes. Fantasy, no.

## Current Status

### Part I — Business Intelligence & Performance Management

Completed or frozen:

- canonical synthetic banking universe;
- 15-stage generation pipeline and cross-system validation;
- PostgreSQL seven-schema relational model;
- 23 physical tables with audited PK/FK, constraints and semantic types;
- thematic SQL analytics `00–07`;
- KPI catalog and SQL KPI layer;
- reusable analytical views and materialized views;
- credit-risk recalibration for loans and monthly snapshots;
- PostgreSQL canonical full-refresh workflow;
- Power BI semantic model and core DAX layer.

Power BI is the current active stage:

- **Executive Overview** — functionally complete;
- **Branches** — functionally complete;
- **Customers & Accounts** — functionally complete;
- **Credit Risk** — calibrated KPI layer complete; visual build in progress;
- remaining thematic pages — pending.

Visual polish and final presentation styling are intentionally deferred until the functional pages are complete.

## Canonical Analytical World

Current working world:

```text
worlds/BTYT/01
```

Observation window:

```text
January 2021 → December 2026
```

Approximate scale:

| Entity | Rows / count |
|---|---:|
| Customers | 107,253 |
| Accounts | 228,945 |
| Cards | 297,775 |
| Loans | 233,441 |
| Loan-month snapshots | 4,109,490 |
| Transactions | 76,799,360 |
| Branches / agencies | 37 |

Generated production data is intentionally kept outside normal Git history where appropriate.

## Architecture

```text
Synthetic world generation
        ↓
Canonical Parquet / CSV datasets
        ↓
PostgreSQL relational model
        ↓
SQL analytical views / materialized views
        ↓
Power BI + DAX
        ↓
Excel / Tableau / focused Python analysis
        ↓
Part II — Credit Risk & Machine Learning
```

The main architectural rule is:

> **Build once at the data layer. Analyze where it makes sense. Visualize where it communicates best. Do not duplicate without purpose.**

## PostgreSQL Model

The final physical model contains **23 tables across 7 schemas**:

| Schema | Tables | Role |
|---|---:|---|
| `core` | 4 | Customers, branches, products, accounts |
| `banking` | 5 | Cards, loans, transactions, balances, loan snapshots |
| `marketing` | 3 | Campaigns, targeting and exposure |
| `reference` | 2 | Campaign dimensions |
| `market` | 5 | Banks, institutions and market dynamics |
| `macro` | 2 | Macroeconomic environment and shocks |
| `performance` | 2 | Bank and branch monthly performance |

Important grains:

```text
transactions                 → one transaction
account_balances             → one account × month
loan_monthly_snapshot        → one loan × month
bank_financials              → one bank × year
bank_monthly_performance     → one BTYT observation × month
branch_monthly_performance   → one branch × month
```

Lower-level monetary tables preserve native currency where applicable. The `performance` schema stores UYU-equivalent reporting values; downstream BI can apply explicit reporting-currency conversion.


## SQL Analytical Layer

The thematic SQL layer is organized as:

```text
00 → Structural Context
01 → Customers
02 → Products & Accounts
03 → Loans & Credit Quality
04 → Transactions & Channels
05 → Branch Network & Performance
06 → Campaigns & Marketing
07 → Bank Performance & Executive Management
```

The SQL layer prepares reusable grains and shared business logic. Dynamic dashboard measures remain in DAX when they need to react to report filters.

Large event data is reduced in PostgreSQL before reaching Power BI. The raw ~76.8M-row transaction table is not imported directly into the BI model.

## Credit Risk

Part I includes a longitudinal credit-quality layer based on:

- loan master data;
- monthly outstanding balance;
- scheduled and actual payments;
- payment shortfall;
- days past due;
- arrears;
- delinquency status;
- contractual status at cutoff.

Canonical DPD buckets:

```text
CURRENT
DPD_1_30
DPD_31_60
DPD_61_90
DPD_90_PLUS
```

The current calibration is frozen for the Part I BI build. Detailed methodology and calibration notes live under:

```text
docs/analytics/03_loans.md
docs/analytics/credit_risk_calibration.md
```

Predictive default modeling remains **Part II**.

## Performance Layer

The performance engine produces monthly bank and branch management reporting.

Core accounting identities:

```text
Net Interest Income
= Interest Income - Interest Expense

Total Revenue
= Net Interest Income + Fee Income

Pre-Provision Profit
= Total Revenue - Total Operating Cost

Pre-Tax Income
= Pre-Provision Profit - Credit Loss

Net Income
= Pre-Tax Income - Income Tax Expense
```

Branch totals reconcile to consolidated bank performance by month.

## Power BI

Power BI is the primary BI product for Part I.

The model uses:

- PostgreSQL analytical views;
- a dedicated `DimDate`;
- reusable DAX measures;
- explicit stock-vs-flow semantics;
- controlled FX conversion for USD presentation;
- filter-aware customer/account windows;
- reduced transaction and customer-month analytical objects.

Repository files:

```text
powerbi/BTYT_Banking_Analytics.pbix
powerbi/BTYT PRESENTATION.pbix
```

The first is the main analytical PBIX; the second is the presentation copy currently used for the visual build.

Power BI documentation:

```text
docs/powerbi/
```

## Analytical Principles

### Master status vs historical state

Master fields such as customer, account, card and loan status are cutoff attributes unless explicitly documented otherwise. Historical behavior comes from monthly snapshots and performance tables.

### Stocks vs flows

Stocks and semi-additive measures require an explicit time rule. Flows such as revenue, operating costs, credit loss and transaction activity can normally be accumulated across periods.

### Transactions

```text
FAILED     → attempted operational event
COMPLETED  → executed economic event
```

Financial transaction volume uses completed transactions only.

### Campaigns

A `POSITIVE` response represents observed campaign receptivity, not automatically a product conversion.

### No arbitrary KPI targets

The project prioritizes observed values, trend, composition and comparison before introducing undocumented red/amber/green thresholds.

## Tool Ownership

| Tool | Main role |
|---|---|
| PostgreSQL / SQL | reusable analytical grains, joins, heavy aggregation, reconciliation |
| Power Query | connection and light shaping |
| Power BI / DAX | interactive BI, ratios, filter context, time intelligence |
| Python | synthetic generation, statistical/exploratory analysis |
| Excel | management and ad-hoc analysis |
| Tableau | geographic and spatial storytelling |

Apache Superset, Docker, Pentaho and broader MLOps infrastructure are outside the first portfolio-ready Part I release.

## Repository Structure

```text
btyt-banking-analytics/
├── config/
├── docs/
│   ├── analytics/
│   ├── architecture/
│   ├── data_dictionary/
│   ├── dbprocess/
│   ├── methodology/
│   └── powerbi/
├── powerbi/
├── resources/
├── scripts/
│   ├── audits/
│   ├── core/
│   ├── database/
│   ├── generators/
│   └── sql/
│       ├── exploration/
│       ├── kpis/
│       └── views/
├── world_builder/
└── worlds/
```

See `docs/README.md` for the documentation map.

## Part II — Credit Risk Analytics & Machine Learning

Part II will reuse the same banking universe rather than introducing an unrelated external dataset.

Planned flow:

```text
PostgreSQL credit-risk analytical dataset
        ↓
feature engineering
        ↓
temporal train / validation / test design
        ↓
statistical and ML models
        ↓
evaluation and explainability
        ↓
scoring workflow
```

Observation and performance windows, target definition and leakage control will be defined explicitly before modeling.

## Technology Stack

Implemented:

**Python · Pandas · NumPy · PyArrow · PostgreSQL · SQL · Psycopg · Power BI · DAX · Power Query · Git / GitHub**

Part I downstream tools:

**Excel · Tableau · focused Python notebooks**

Later:

**scikit-learn · explainability · experiment tracking / MLflow where justified**

## Documentation

The project documentation is organized under `docs/`:

- `docs/analytics/` — analytical ownership, KPI definitions and thematic analysis;
- `docs/architecture/` — project evolution, architecture and manifest;
- `docs/data_dictionary/` — dataset semantics;
- `docs/dbprocess/` — PostgreSQL lifecycle and canonical refresh;
- `docs/methodology/` — reliability and methodological foundations;
- `docs/powerbi/` — semantic model, measures and report pages.

## Disclaimer

BTYT is a fictional bank created exclusively for educational and portfolio purposes.

All customers, accounts, cards, loans, transactions, balances, branch behavior, market behavior, financial values, campaign outcomes and credit events are synthetic.

The project contains no real customer data, confidential banking information or actual bank transaction records. Real financial-institution names may appear only as structural references; synthetic values associated with them must not be interpreted as real reported results.

## Author

**Santiago Castillo Marsicano**  
Economics & Sociology  
Data Analytics · Business Intelligence
