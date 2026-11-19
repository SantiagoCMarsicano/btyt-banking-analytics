# BTYT World Builder

This document covers the world-generation layer of **BTYT Banking Analytics**: the World Builder application, the generation pipeline, the synthetic banking universe it produces and how that universe reaches PostgreSQL. For the project overview, SQL analytics and the Power BI report, see the [main README](../README.md).

Banco de Treinta y Tres (BTYT) is a fictional Uruguayan commercial bank used as the analytical universe for an end-to-end banking data project.

BTYT Banking Analytics combines synthetic data generation, banking-domain modeling, reproducible simulation, validation, relational database engineering, SQL, business intelligence, and later credit-risk modeling in one shared banking universe.

**Fiction, yes. Fantasy, no.**

The data is synthetic, but the relationships, temporal dynamics, business rules, and accounting constraints are designed to remain economically and operationally plausible.

---

## Quick Start

Tested with **Python 3.14.7 (64-bit) on Windows 11**. All commands run from the repository root.

### 1. Clone and install

```bash
git clone https://github.com/SantiagoCMarsicano/btyt-banking-analytics.git
cd btyt-banking-analytics
python -m venv .venv
```

Activate the virtual environment:

```powershell
.\.venv\Scripts\Activate.ps1
```

```bash
source .venv/bin/activate
```

Install the pinned dependencies:

```bash
python -m pip install -r requirements.txt
```

Notes:

* World Builder uses Tk. It ships with the python.org installers for Windows and macOS; on Debian/Ubuntu install `python3-tk`.
* The Power BI report is a text-based project (`powerbi/*.pbip`); the generation pipeline does not depend on it.

### 2. Launch World Builder

```bash
python -m world_builder.app
```

### 3. Create or select a SMOKE world

The repository ships `worlds/SMOKE/33` as a small reference world (50 customers, 2021–2026). To generate a world without overwriting that versioned example, create a new variant with the same profile:

| Field | Value |
|---|---|
| World Name | `SMOKE` |
| Variant | `34` (any unused number) |
| Canonical World | unchecked |
| Execution Profile | `Full` |
| Population | `Fixed` · `50` customers |
| Observation Period | `2021-01-01` → `2026-12-31` |
| Data Reliability | `realistic` |
| Start from / Run through | `Beginning` / `Final` |
| Auto-finalize after full pipeline | checked |

The world seed is derived from the world name and variant (`SMOKE` + `33` → `3165889979`), so the same identity always reproduces the same world.

To reopen an existing world, select it under **Registered Worlds** and click **LOAD SELECTED WORLD**.

### 4. Generate

Click **GENERATE WORLD**. World Builder then:

1. activates the world by writing `config/world_config.json`, `config/active_world.json` and `worlds/registry.json`;
2. runs the 15-stage pipeline (`scripts.generate_btyt`), ending with the cross-system audit;
3. with auto-finalize enabled, writes the dataset manifest and verifies it.

The status moves through `READY → GENERATING → GENERATED → AUDITED → MANIFESTED → VERIFIED → FROZEN`. Outputs are written to `worlds/SMOKE/<variant>/` (`data/`, `manifests/`, `audit/`), which Git ignores.

Activating a world modifies the three tracked configuration files listed above. If you were only testing, restore them before committing:

```bash
git restore config/world_config.json config/active_world.json worlds/registry.json
```

### 5. Validate from the command line

These commands act on the world currently referenced by `config/active_world.json`.

Check repository structure, the active world and stage availability without running anything:

```bash
python -m scripts.generate_btyt --check-only
```

Re-run the integrated cross-system audit (rewrites the audit reports):

```bash
python -m scripts.generate_btyt --only cross_system_audit
```

Verify every generated file against the world's manifest fingerprint:

```bash
python -m scripts.generate_manifest --verify-only
```

Once a world has been activated, the full pipeline can also run without the GUI with `python -m scripts.generate_btyt` (see `--help` for `--from-stage`, `--to-stage` and `--only`).

---

## Project Scope

The project is divided into two main analytical stages.

### Part I — Business Intelligence & Performance Management

Part I builds, validates, stores, and analyzes the synthetic banking universe through:

* reproducible synthetic data generation;
* cross-system validation and auditing;
* PostgreSQL database engineering;
* relational database design;
* SQL analytics;
* banking KPIs;
* Power BI, Power Query and DAX;
* customer, product, branch, transaction, lending, and profitability analysis.

Planned Part I extensions: **Excel** and **Tableau**, reusing the same universe and KPI framework.

### Part II — Credit Risk Analytics & Machine Learning

Part II reuses the same frozen banking universe for:

* SQL-based feature extraction;
* exploratory credit-risk analysis;
* feature engineering;
* statistical modeling;
* machine learning;
* model evaluation;
* explainability;
* later local experiment tracking and scoring infrastructure.

No disconnected replacement dataset is created for Part II.

---

## Current Project Status

**Part I core end-to-end implementation is complete:** Python synthetic-data pipeline → PostgreSQL → SQL analytical layer → Power BI.

The canonical world (`worlds/BTYT/01`) was generated through the reproducible world-based architecture, validated through the project auditing system, persisted as CSV/Parquet datasets, and loaded into PostgreSQL, where the relational model and the analytical views are applied.

The PostgreSQL database contains:

* **7 functional schemas** with **23 base tables**, plus an `analytics` schema of views and materialized views;
* about **88 million rows** across the base tables;
* **74,774,125 transaction records** (72,746,246 completed and 2,027,879 failed);
* large monthly account-balance and credit-performance histories;
* customer, account, product, branch, card, loan, campaign, market, macroeconomic, and performance data.

### Completed

* [x] World-based generation architecture and deterministic world configuration
* [x] Canonical BTYT world generation
* [x] Cross-system validation
* [x] CSV / Parquet persistence
* [x] Manifest and reproducibility architecture
* [x] PostgreSQL ingestion and validated full refresh
* [x] Relational model: semantic types, primary keys, foreign keys, `CHECK` / `NOT NULL` constraints and indexes
* [x] SQL exploration, KPI and analytical-view layers
* [x] Power BI report (six pages) with Power Query and DAX

### Planned Part I Extensions

* [ ] Excel
* [ ] Tableau

---

## World-Based Architecture

Each simulated banking universe is defined by a world identity and configuration.

```text
World Name
    +
Variant
    ↓
Deterministic World Seed
    ↓
World Configuration
    ↓
15-Stage Generation Pipeline
    ↓
Cross-System Audit
    ↓
Manifest + Fingerprint
    ↓
Frozen Analytical World
```

Worlds are isolated under:

```text
worlds/<WORLD>/<VARIANT>/
```

A world contains its own metadata, configuration snapshot, generated datasets, interim latent-state data, operational exports, audit outputs, and manifests.

The canonical BTYT world is currently stored under:

```text
worlds/BTYT/01/
```

---

## BTYT World Builder

The project includes a desktop interface for configuring and launching synthetic worlds.

The BTYT World Builder supports:

* world name and variant;
* deterministic seed derivation;
* fixed or ranged customer population;
* observation-period configuration;
* data-reliability settings;
* pipeline start and end stages;
* automatic reference-asset materialization;
* live stage status;
* per-stage progress;
* global pipeline progress;
* resume / stop controls;
* manifest generation;
* manifest verification;
* world-folder access;
* execution logging.

Launch it from the repository root (see [Quick Start](#quick-start)):

```bash
python -m world_builder.app
```

A standalone Windows executable is considered a packaging enhancement rather than a dependency of the analytical project.

---

## Generation Pipeline

The full project orchestrator executes 15 stages:

|  # | Stage                    | Purpose                                        |
| -: | ------------------------ | ---------------------------------------------- |
|  1 | `macro`                  | Macroeconomic environment                      |
|  2 | `banks`                  | Banking market and financial dynamics          |
|  3 | `financial_institutions` | Financial-institution reference network        |
|  4 | `branches`               | Dynamic branch network and annual branch state |
|  5 | `customers`              | Individual and business customers              |
|  6 | `accounts`               | Customer-account relationships and lifecycle   |
|  7 | `cards`                  | Debit and credit-card lifecycle                |
|  8 | `loans`                  | Retail and business lending                    |
|  9 | `loan_snapshot`          | Monthly loan lifecycle and delinquency state   |
| 10 | `external_shocks`        | Shared external operational/economic shocks    |
| 11 | `transactions`           | Transaction engine and account balances        |
| 12 | `campaigns`              | Campaign targets, exposures, and responses     |
| 13 | `branch_performance`     | Branch and consolidated bank performance       |
| 14 | `operational_exports`    | Imperfect operational representation           |
| 15 | `cross_system_audit`     | Integrated cross-system validation             |

The orchestrator runs each stage in a fresh subprocess and uses fail-fast execution by default.

---

## Synthetic Banking Universe

The detailed analytical observation window is:

**January 2021 → December 2026**

Some customer, account, card, branch, and credit relationships may originate before 2021 to represent inherited historical state.

The universe includes core banking, financial activity, banking-market, marketing, world-state, and operational datasets, including:

* branches;
* customers;
* products;
* accounts;
* cards;
* loans;
* transactions;
* account balances;
* monthly credit snapshots;
* campaigns;
* banking-market dynamics;
* external shocks;
* macroeconomic conditions;
* branch performance;
* consolidated bank performance.

---

## Data-Generation Philosophy

BTYT does not generate independent random tables.

The project generates a coherent banking system in which observable outcomes emerge from underlying mechanisms such as:

* customer heterogeneity;
* product preferences;
* account ownership;
* branch relationships;
* digital adoption;
* lending behavior;
* delinquency dynamics;
* transaction activity;
* seasonality;
* market evolution;
* external and local shocks;
* branch operating pressure;
* controlled data-quality degradation.

A macroeconomic or local event may influence several downstream systems, but it does not deterministically assign outcomes to individual entities.

---

## Branch Network

BTYT contains a structurally defined network of **37 branches and agencies across Uruguay**.

Branches differ by:

* branch type;
* size;
* geography;
* administrative parent;
* opening history;
* strategic importance;
* structural closure risk.

Branch closures are stochastic rather than hard-coded.

The annual latent branch-state panel preserves every branch across every observation year, including years after closure, so downstream historical relationships remain valid.

---

## Banking Network

BTYT operates inside a synthetic financial system containing:

* BTYT itself;
* domestic banks operating in Uruguay;
* selected international banking counterparties;
* electronic-money institutions.

Some institution names correspond to real financial institutions to create a recognizable structural banking environment.

All simulated market weights, financial values, transaction relationships, behavioral parameters, shocks, and bank trajectories are synthetic and must not be interpreted as real-world bank data.

---

## Transactions

The transaction engine supports:

* transfers;
* debit purchases;
* service payments;
* cash withdrawals and deposits;
* loan payments;
* interest credits;
* loan disbursements.

It also models:

* digital adoption;
* channel migration;
* cash usage;
* failed transactions;
* internal-transfer pairing;
* counterparty institutions;
* physical-branch usage when applicable;
* account-balance reconciliation.

The canonical BTYT world contains:

**74,774,125 transaction records** — 72,746,246 completed and 2,027,879 failed

Because of this scale, transaction data is persisted in **Parquet** rather than normal Git history and loaded into PostgreSQL in batches.

---

## Loans and Credit Performance

The lending system contains retail and business credit products and a monthly loan snapshot tracking:

* outstanding balance;
* current interest rate;
* scheduled payment;
* actual payment;
* days past due;
* delinquency state;
* arrears;
* restructuring;
* default;
* write-off;
* prepayment;
* maturity;
* open exposures.

The canonical PostgreSQL database contains more than **4.1 million monthly loan-snapshot observations**.

This credit history also provides the analytical foundation for Part II.

---

## Account Balances

Monthly account balances provide a longitudinal view of account-level financial activity.

The canonical database contains more than **7.5 million account-month observations**, including:

* opening balance;
* total inflows;
* total outflows;
* closing balance.

These records provide a bridge between transactional behavior and higher-level customer, account, branch, and bank analysis.

---

## Branch and Bank Performance

BTYT includes a dedicated monthly profitability layer.

### `branch_monthly_performance`

Grain:

**one branch per month**

```text
37 branches × 72 months = 2,664 rows
```

### `bank_monthly_performance`

Grain:

**one consolidated BTYT observation per month**

```text
72 months = 72 rows
```

The consolidated bank table must reconcile with the aggregation of branch-level performance.

---

## Analytical KPIs

Most BI ratios are deliberately **not precomputed by the Python generators**.

They are intended to be derived in SQL and/or DAX.

Examples include:

* Cost-to-Income Ratio;
* Net Interest Margin;
* Revenue per Customer;
* Cost per Transaction;
* Branch Margin;
* Credit Loss Ratio;
* Deposit Growth;
* Loan Growth;
* Digital Channel Share;
* Branch Profitability;
* Regional Profitability;
* Product Profitability;
* Customer Segment Performance.

This keeps the generated datasets focused on underlying facts while allowing the analytical layer to explicitly define business metrics.

---

## Validation and Auditing

Successful script execution is not considered sufficient evidence of correctness.

BTYT includes generator-level and integrated validations covering:

* referential integrity;
* temporal integrity;
* lifecycle constraints;
* loan-snapshot continuity;
* transaction and balance reconciliation;
* internal-transfer pairing;
* counterparty validation;
* branch-state completeness;
* branch-to-bank performance reconciliation;
* accounting identities;
* operational-export integrity.

The final pipeline stage performs an integrated cross-system audit.

Validations must never be weakened merely to force a PASS.

---

## Synthetic Truth vs. Operational Representation

BTYT separates internally coherent synthetic truth from a controlled operational representation that can introduce realistic data-quality degradation without corrupting protected economic and relational truths.

This distinction allows the project to represent both:

1. the internally consistent synthetic banking universe; and
2. imperfect operational data derived from that universe.

---

## Manifest and Dataset Fingerprint

A completed world can generate a manifest containing:

* canonical and operational file inventories;
* provenance files;
* row counts;
* file sizes;
* hashes;
* pipeline status;
* audit status;
* dataset fingerprint.

The fingerprint provides a compact reproducibility identifier for a frozen BTYT world.

---

# PostgreSQL Data Layer

The canonical generated world is loaded into a local PostgreSQL database through:

```text
Synthetic World
      ↓
CSV / Parquet
      ↓
Python Ingestion Pipeline
      ↓
PostgreSQL
      ↓
Relational Model
      ↓
SQL / BI / Analytics
```

The loader is implemented in:

```text
scripts/database/load_postgresql.py
```

It performs a validated full refresh of the existing 23-table relational model, preserving table definitions and constraints:

```text
preflight
→ multi-table TRUNCATE
→ COPY reload
→ row-count validation against the source files
→ ANALYZE
→ commit
→ analytics materialized-view refresh
```

It uses an explicit source-table-to-schema mapping and prefers Parquet when both CSV and Parquet representations exist. If the load fails inside the transaction, PostgreSQL rolls back the base-table refresh. See [`docs/dbprocess/`](../docs/dbprocess/) for the full database workflow.

The physical folder structure of generated files is deliberately separated from the logical PostgreSQL schema architecture.

---

## PostgreSQL Schema Architecture

The database is organized into seven functional schemas.

### `core`

Fundamental banking entities.

```text
core
├── accounts
├── branches
├── customers
└── products
```

**4 tables**

### `banking`

Banking operations, financial positions, and credit behavior.

```text
banking
├── account_balances
├── cards
├── loan_monthly_snapshot
├── loans
└── transactions
```

**5 tables**

### `marketing`

Campaign execution and customer response.

```text
marketing
├── campaign_customers
├── campaign_exposures
└── campaigns
```

**3 tables**

### `market`

Competitive and financial banking environment.

```text
market
├── bank_financials
├── bank_market_weights
├── bank_world_parameters
├── banks
└── financial_institutions
```

**5 tables**

### `macro`

Macroeconomic conditions and external shocks.

```text
macro
├── external_shocks
└── macro_environment
```

**2 tables**

### `performance`

Monthly branch and consolidated bank profitability.

```text
performance
├── bank_monthly_performance
└── branch_monthly_performance
```

**2 tables**

### `reference`

Reference and bridge dimensions.

```text
reference
├── campaign_channels
└── campaign_geography
```

**2 tables**

### Database total

```text
core          4
banking       5
marketing     3
reference     2
market        5
macro         2
performance   2
----------------
TOTAL        23
```

On top of these base tables, the `analytics` schema holds the reporting views and materialized views consumed by Power BI ([`scripts/sql/views/`](../scripts/sql/views/)).

---

## PostgreSQL Load Validation

The full refresh validates every one of the 23 tables against its source dataset before committing.

Current canonical row counts (`worlds/BTYT/01`):

| Table                           |       Rows |
| ------------------------------- | ---------: |
| `banking.transactions`          | 74,774,125 |
| `banking.account_balances`      |  7,525,724 |
| `banking.loan_monthly_snapshot` |  4,109,490 |
| `banking.cards`                 |    297,775 |
| `banking.loans`                 |    233,441 |
| `core.accounts`                 |    228,945 |
| `marketing.campaign_exposures`  |    204,010 |
| `marketing.campaign_customers`  |    141,248 |
| `core.customers`                |    107,253 |
| `core.branches`                 |         37 |
| `core.products`                 |         18 |

The database is therefore no longer dependent on reading flat files directly for analytical work.

CSV and Parquet remain the reproducible persisted representation of the synthetic world, while PostgreSQL becomes the relational and analytical data layer.

---

## Relational Modeling

Loading the datasets is intentionally separated from relational modeling.

The relational model is applied as structural migration logic, outside the routine data refresh, and covers:

1. semantic data types;
2. primary and unique constraints;
3. foreign-key relationships and referential-integrity validation;
4. nullability and business `CHECK` constraints;
5. analytical indexes.

| Script | Role |
|---|---|
| `scripts/database/apply_relational_model.py` | Applies or repairs the seven-schema model and its constraints |
| `scripts/database/audit_relational_model.py` | Read-only inspection of the structure and relational contract |
| `scripts/database/validate_relational_model.py` | Validates the tracked FK / `CHECK` constraints and final relational state |

The Entity-Relationship Diagram ([`docs/architecture/relational_model_btyt.png`](../docs/architecture/relational_model_btyt.png)) is derived from the implemented PostgreSQL model rather than inferred from the Python generators.

---

## Repository Structure

```text
btyt-banking-analytics/
│
├── config/
│   ├── active_world.json
│   └── world_config.json
│
├── resources/
│   └── reference/
│       ├── products.csv
│       └── campaigns/
│
├── worlds/
│   ├── registry.json
│   └── <WORLD>/
│       └── <VARIANT>/
│           ├── world.json
│           ├── metadata.json
│           ├── data/
│           │   ├── interim/
│           │   ├── generated/
│           │   └── operational/
│           ├── database/
│           ├── audit/
│           └── manifests/
│
├── scripts/
│   ├── core/
│   ├── generators/
│   ├── audits/
│   ├── validation/
│   ├── diagnostics/
│   ├── database/
│   │   ├── load_postgresql.py
│   │   ├── apply_relational_model.py
│   │   ├── audit_relational_model.py
│   │   └── validate_relational_model.py
│   ├── sql/
│   │   ├── exploration/
│   │   ├── kpis/
│   │   └── views/
│   ├── generate_btyt.py
│   └── generate_manifest.py
│
├── world_builder/
│   ├── app.py
│   └── state.py
│
├── powerbi/
│   └── BTYT_Banking_Analytics.pbip
│
├── docs/
│   ├── analytics/
│   ├── architecture/
│   ├── data_dictionary/
│   ├── dbprocess/
│   ├── methodology/
│   └── powerbi/
│
└── README.md
```

---

## Reference Assets

Small static business/reference dimensions are version-controlled separately from generated worlds.

Canonical reference assets include:

```text
resources/reference/products.csv

resources/reference/campaigns/
├── campaigns.csv
├── campaign_channels.csv
└── campaign_geography.csv
```

The World Builder materializes these reference files into new isolated worlds before generation.

---

## Reproducibility

BTYT is designed so that a world is determined by its identity and configuration rather than by execution order or chunk size.

The architecture centralizes:

* world configuration;
* world seed;
* observation period;
* population specification;
* output routing.

Individual generators retain dedicated RNG namespaces and streams for independent stochastic mechanisms.

The data pipeline extends this reproducibility principle beyond generation:

```text
World configuration
        ↓
Synthetic generation
        ↓
CSV / Parquet
        ↓
PostgreSQL ingestion
        ↓
Validated relational database
```

This separation makes it possible to reconstruct the analytical database from the persisted synthetic world.

---

## Large Generated Files

Large generated datasets are intentionally excluded from Git where appropriate.

The repository is designed around:

```text
model code
    +
reference assets
    +
world configuration
    +
data-engineering pipeline
    ↓
reproducible analytical environment
```

rather than storing every production output directly in version control.

The canonical Parquet datasets and the local PostgreSQL physical database are therefore not intended to be committed to normal Git history.

The small `worlds/SMOKE/33` world (50 customers) is the exception: it is versioned as a reproducible repository example.

---

## Technology Stack

### Implemented

* Python
* Pandas
* NumPy
* PyArrow / Parquet
* PostgreSQL
* SQLAlchemy
* psycopg
* SQL
* PostgreSQL relational modeling, constraints and indexing
* analytical SQL views and materialized views
* Power BI
* Power Query
* DAX
* Git
* GitHub / Git LFS
* CustomTkinter
* deterministic RNG architecture
* cross-system auditing
* reproducible database ingestion

### Planned Part I Extensions

* Excel
* Tableau

### Later Stages (Part II)

* scikit-learn
* credit-risk modeling
* machine learning
* model explainability
* MLflow
* local scoring service
* Docker / Docker Compose

Technologies are added to the implemented stack only when their corresponding project stage is actually completed.

---

## Main Analytical Question — Part I

**How is BTYT performing, and where are the main opportunities and risks across its loan portfolio, deposits, products, customer segments, branches, channels, and banking relationships?**

Part I answers this through:

* a validated PostgreSQL relational model;
* SQL analytical queries and views;
* banking KPIs;
* branch-performance analysis;
* customer and product analysis;
* transaction and channel analysis;
* lending and delinquency analysis;
* market and campaign analysis;
* a six-page Power BI report.

---

## Part II — Credit Risk Analytics

Part II will reuse the same frozen BTYT universe and PostgreSQL data infrastructure for:

* SQL-based feature extraction;
* exploratory risk analysis;
* feature engineering;
* statistical modeling;
* machine learning;
* model evaluation;
* explainability.

No separate disconnected dataset will be created for the credit-risk stage.

The existing monthly loan-performance history provides the longitudinal foundation for the future credit-risk modeling stage.

---

## Disclaimer

BTYT is a fictional bank created exclusively for educational and portfolio purposes.

All customers, accounts, cards, loans, transactions, balances, branch behavior, market behavior, banking relationships, financial values, campaign outcomes, and credit events represented in the project are synthetic.

The project contains no real customer data, confidential banking information, or actual bank transaction records.

Names of real financial institutions may appear only as structural references within the simulated banking environment.

Synthetic metrics associated with those institutions must not be interpreted as actual reported financial results or observed market behavior.

---

## Author

**Santiago Castillo Marsicano**

Economics & Sociology
Data Analytics | Business Intelligence
