# BTYT Banking Analytics

Banco de Treinta y Tres (BTYT) is a fictional Uruguayan commercial bank used as the analytical universe for an end-to-end banking data project.

BTYT Banking Analytics combines synthetic data generation, banking-domain modeling, reproducible simulation, validation, relational database engineering, SQL, business intelligence, and later credit-risk modeling in one shared banking universe.

**Fiction, yes. Fantasy, no.**

The data is synthetic, but the relationships, temporal dynamics, business rules, and accounting constraints are designed to remain economically and operationally plausible.

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
* Power BI;
* Power Query and DAX;
* Tableau and geographic analysis;
* Apache Superset;
* customer, product, branch, transaction, lending, and profitability analysis.

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

BTYT has completed its **canonical world generation, validation, and PostgreSQL ingestion stages**.

The current canonical world has been generated through the reproducible world-based architecture, validated through the project auditing system, persisted as CSV/Parquet datasets, and loaded into PostgreSQL through a dedicated Python ingestion pipeline.

The PostgreSQL database currently contains:

* **5 functional schemas**;
* **23 analytical tables**;
* approximately **90 million rows** across the complete database;
* **76,799,360 transaction records**;
* large monthly account-balance and credit-performance histories;
* customer, account, product, branch, card, loan, campaign, market, macroeconomic, and performance data.

All 23 source datasets were successfully loaded and their PostgreSQL row counts validated against the corresponding generated files.

### Completed

* [x] World-based generation architecture
* [x] Deterministic world configuration
* [x] Canonical BTYT world generation
* [x] Cross-system validation
* [x] CSV / Parquet persistence
* [x] Manifest and reproducibility architecture
* [x] PostgreSQL database creation
* [x] Python-to-PostgreSQL ingestion pipeline
* [x] Functional schema architecture
* [x] 23 datasets loaded
* [x] Source-to-database row-count validation

### Current Database Engineering Stage

* [ ] Data-type refinement
* [ ] Primary keys
* [ ] Unique constraints
* [ ] Foreign keys
* [ ] Referential-integrity validation
* [ ] `NOT NULL` and business constraints
* [ ] Database indexes
* [ ] Final relational-model validation

### Next Analytical Stage

* [ ] Analytical SQL
* [ ] Banking KPI layer
* [ ] Power BI
* [ ] Power Query / DAX
* [ ] Tableau
* [ ] Apache Superset

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
* pause / resume / stop controls;
* manifest generation;
* manifest verification;
* world-folder access;
* execution logging.

Current development launch command:

```powershell
.\.venv\Scripts\python.exe -m world_builder.app
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

**76,799,360 transaction records**

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

The canonical PostgreSQL database contains more than **5.1 million monthly loan-snapshot observations**.

This credit history will later provide the analytical foundation for Part II.

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

The ingestion pipeline is implemented in:

```text
scripts/database/load_postgresql.py
```

The loader:

* recursively discovers generated datasets;
* uses explicit source-table-to-schema mapping;
* prefers Parquet when both CSV and Parquet representations exist;
* preserves identifier columns;
* normalizes column names;
* processes large Parquet datasets in batches;
* loads data through SQLAlchemy;
* detects partially loaded tables;
* compares PostgreSQL row counts with source row counts;
* resets incomplete loads when necessary;
* validates every completed table against its source dataset.

The physical folder structure of generated files is deliberately separated from the logical PostgreSQL schema architecture.

---

## PostgreSQL Schema Architecture

The database is organized into five functional schemas.

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

Competitive, financial, macroeconomic, shock, and performance environment.

```text
market
├── bank_financials
├── bank_market_weights
├── bank_monthly_performance
├── bank_world_parameters
├── banks
├── branch_monthly_performance
├── external_shocks
├── financial_institutions
└── macro_environment
```

**9 tables**

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
market        9
reference     2
----------------
TOTAL        23
```

---

## PostgreSQL Load Validation

The canonical ingestion completed successfully:

```text
Loaded : 23
Skipped: 0
Failed : 0

All BTYT datasets are loaded and row-count validated.
```

Major PostgreSQL tables include:

| Table                           |       Rows |
| ------------------------------- | ---------: |
| `banking.transactions`          | 76,799,360 |
| `banking.account_balances`      |  7,525,724 |
| `banking.loan_monthly_snapshot` |  5,116,730 |
| `banking.cards`                 |    297,775 |
| `banking.loans`                 |    233,852 |
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

The ingestion pipeline does not automatically impose primary keys, foreign keys, business constraints, or analytical indexes.

The current database-engineering phase will explicitly review and implement:

1. data types;
2. candidate primary keys;
3. duplicate detection;
4. nullability;
5. primary and unique constraints;
6. foreign-key relationships;
7. referential-integrity validation;
8. business `CHECK` constraints;
9. analytical indexes.

For each table, the project will document:

* primary key;
* foreign keys;
* referenced tables;
* grain;
* cardinality;
* temporal keys;
* validated join paths.

The final Entity-Relationship Diagram will be derived from the implemented PostgreSQL relational model rather than inferred visually from the Python generators.

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
│   ├── database/
│   │   └── load_postgresql.py
│   ├── generate_btyt.py
│   └── generate_manifest.py
│
├── world_builder/
│   └── app.py
│
├── docs/
│   ├── architecture/
│   ├── database/
│   └── data_dictionary/
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
* Git
* GitHub
* CustomTkinter
* deterministic RNG architecture
* cross-system auditing
* reproducible database ingestion

### Current Stage

* PostgreSQL relational modeling
* SQL
* database constraints
* referential-integrity validation
* database indexing

### Next Analytical Stage

* analytical SQL
* Power BI
* Power Query
* DAX
* Tableau
* Apache Superset

### Later Stages

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

Part I will answer this through:

* a validated PostgreSQL relational model;
* SQL analytical queries and views;
* banking KPIs;
* branch-performance analysis;
* customer and product analysis;
* transaction and channel analysis;
* lending and delinquency analysis;
* geographic analysis;
* business-intelligence dashboards.

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
