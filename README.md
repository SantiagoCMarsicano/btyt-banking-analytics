<p align="center">
  <img src="docs/assets/logo.png" alt="BTYT Banking Analytics" width="240">
</p>

<h1 align="center">BTYT Banking Analytics</h1>

<p align="center">
  <strong>End-to-end synthetic banking analytics project built around a fictional Uruguayan commercial bank.</strong>
</p>

<p align="center">
  Python · PostgreSQL · SQL · Power BI · Tableau · Apache Superset · Credit Risk / ML
</p>

Overview

Banco de Treinta y Tres (BTYT) is a fictional Uruguayan commercial bank created as the analytical universe for an end-to-end data project.

The project combines synthetic data generation, banking-domain modeling, reproducible simulation, relational database design, PostgreSQL, SQL analytics, business intelligence, and later credit-risk modeling and machine learning.

BTYT is not a collection of disconnected random tables. It builds a coherent synthetic banking system in which customers, branches, products, accounts, cards, loans, transactions, campaigns, external shocks, market dynamics, and profitability evolve together over time.

Fiction, yes. Fantasy, no.

All data is synthetic, but the relationships, temporal dynamics, business rules, and accounting constraints are designed to remain economically and operationally plausible.

Project Status

Completed

Reproducible synthetic banking world

Deterministic world identity and configuration

Isolated world storage

15-stage generation pipeline

Cross-system validation

Operational data-reliability layer

Manifest and dataset fingerprinting

PostgreSQL ingestion pipeline

Final seven-schema relational architecture

Semantic PostgreSQL types

Accounting-oriented monetary precision

23 primary keys

28 foreign keys

11 audited NOT NULL rules

27 CHECK constraints

55 / 55 historical constraints validated

SQL-process documentation

Portfolio-ready relational model

Current milestone

The PostgreSQL relational-model phase is complete.

7 schemas
23 tables
251 columns
23 primary keys
28 foreign keys
27 CHECK constraints
11 audited NOT NULL rules
55 / 55 historical constraints validated

The project is now moving into:

SQL analytics
    ↓
analytical views
    ↓
banking KPIs
    ↓
Power BI / Tableau / Superset

Project Scope

Part I — Business Intelligence & Performance Management

Part I builds, validates, stores, and analyzes the synthetic banking universe through:

Python data generation

PostgreSQL relational modeling

SQL analytics

Banking KPIs

Customer, product, branch, lending, transaction, channel, and profitability analysis

Power BI

Power Query

DAX

Tableau

Apache Superset

Part II — Credit Risk Analytics & Machine Learning

Part II will reuse the same frozen banking universe for:

SQL-based feature extraction

Exploratory credit-risk analysis

Feature engineering

Statistical modeling

Machine learning

Model evaluation

Explainability

Experiment tracking

Scoring infrastructure

No disconnected replacement dataset will be created for Part II.

PostgreSQL Relational Model

The final PostgreSQL model contains 7 schemas, 23 tables, 251 columns, 23 primary keys, and 28 foreign keys.

<p align="center">
  <img src="docs/architecture/relational_model_btyt.png" alt="BTYT PostgreSQL relational model" width="100%">
</p>

The portfolio ERD intentionally shows a maximum of ten representative fields per table while preserving the full schema structure, PK/FK relationships, and table-level grain. The complete PostgreSQL model contains all 251 columns.

Schema

Tables

Role

core

4

Central banking entities

banking

5

Operational banking activity

marketing

3

Campaigns and customer response

reference

2

Auxiliary campaign dimensions

market

5

Competitive banking environment

macro

2

Macroeconomic context and external shocks

performance

2

Aggregated BTYT bank and branch performance

Total

23



core

Central entities around which the rest of the model is organized:

branches

customers

accounts

products

This layer answers questions such as:

Who is the customer?

Which branch owns the relationship?

Which product is being used?

Which account connects the customer to banking activity?

banking

Operational banking activity and contract-level financial state:

cards

loans

transactions

account_balances

loan_monthly_snapshot

Typical grains:

transactions
→ one transaction

account_balances
→ one account × month

loan_monthly_snapshot
→ one loan × month

Monthly frequency alone does not make a table a performance table. account_balances and loan_monthly_snapshot remain in banking because they describe individual banking relationships.

marketing

Commercial campaigns, targeting, exposure, and response:

campaigns

campaign_customers

campaign_exposures

reference

Auxiliary campaign dimensions:

campaign_channels

campaign_geography

market

Competitive and institutional banking environment:

banks

bank_financials

bank_market_weights

bank_world_parameters

financial_institutions

bank_financials remains in market because its grain is:

bank_id × year

It describes banks in the competitive environment rather than BTYT's internal operating performance.

macro

Exogenous conditions affecting the synthetic banking world:

macro_environment

external_shocks

performance

Aggregated BTYT management and profitability indicators:

bank_monthly_performance

branch_monthly_performance

Grains:

bank_monthly_performance
→ one consolidated BTYT observation × month

branch_monthly_performance
→ one branch × month

Why Seven Schemas?

The first PostgreSQL ingestion architecture used five schemas. At that stage, market temporarily contained competitive banks, financial institutions, macroeconomic conditions, external shocks, and BTYT performance.

The final architecture separates:

market
→ competitive and institutional banking environment

macro
→ exogenous macroeconomic conditions and shocks

performance
→ aggregated BTYT operating results

Four tables were moved:

market.macro_environment
→ macro.macro_environment

market.external_shocks
→ macro.external_shocks

market.bank_monthly_performance
→ performance.bank_monthly_performance

market.branch_monthly_performance
→ performance.branch_monthly_performance

No analytical grain changed and no table was deleted.

Relational Integrity

The implemented PostgreSQL model contains:

23 primary keys
28 foreign keys
11 audited NOT NULL rules
27 CHECK constraints

Examples of key relationships:

customers.primary_branch_id
→ branches.branch_id

accounts.customer_id
→ customers.customer_id

accounts.product_id
→ products.product_id

accounts.branch_id
→ branches.branch_id

cards.linked_account_id
→ accounts.account_id

loans.customer_id
→ customers.customer_id

loan_monthly_snapshot.loan_id
→ loans.loan_id

transactions.account_id
→ accounts.account_id

campaign_customers.campaign_id
→ campaigns.campaign_id

campaign_customers.customer_id
→ customers.customer_id

bank_financials.bank_id
→ banks.bank_id

branch_monthly_performance.branch_id
→ branches.branch_id

Transaction counterparties

External transaction counterparties use a two-level institution model:

banking.transactions.counterparty_institution_id
        ↓
market.financial_institutions.institution_id
        ↓
market.banks.bank_id

This is intentional: not every operational financial counterparty must be a bank.

PostgreSQL Types and Precision

The generated files are optimized for reproducible data generation and interoperability. PostgreSQL adds stronger semantic typing.

Examples:

year fields
→ INTEGER

year_month
→ DATE

campaign dates
→ DATE

financial-institution activity dates
→ DATE

external-shock timeline fields
→ DATE

transaction_datetime
→ TIMESTAMP

Accounting-style monetary values use fixed decimal precision:

Typical monetary measures
→ NUMERIC(18,2)

Large aggregates
→ NUMERIC(20,2)

Simulation variables, affinities, latent states, coordinates, and similar continuous parameters remain floating-point where appropriate.

Constraint Validation

Final validation state:

Foreign keys validated        : 28 / 28
CHECK constraints validated   : 27 / 27
Tracked historical constraints: 55 / 55

Tables                        : 23 / 23
Primary keys                  : 23 / 23
Audited NOT NULL              : 11 / 11
Unvalidated foreign keys      : 0
Unvalidated CHECK constraints : 0

The seven-schema reorganization therefore changed logical organization without damaging relational integrity.

SQL / PostgreSQL Pipeline

The relational layer is implemented through four scripts:

load_postgresql.py
        ↓
audit_relational_model.py
        ↓
apply_relational_model.py
        ↓
validate_relational_model.py

load_postgresql.py

Discovers canonical datasets

Supports CSV and Parquet

Preserves identifier columns

Loads large datasets in batches

Assigns initial ingestion schemas

Validates source vs. PostgreSQL row counts

Safely reruns incomplete loads

audit_relational_model.py

Read-only audit covering:

Schema and table inventory

Column inventory

Semantic types

Value compatibility

Financial precision

Primary-key integrity

Nullability

Category domains

Range, temporal, and business rules

Current relational state

apply_relational_model.py

Applies the approved model:

Schema reorganization

Semantic type conversions

Monetary precision

Primary keys

Foreign keys

NOT NULL

CHECK constraints

The final schema migration is pre-checked, atomic, and idempotent.

validate_relational_model.py

Validates:

Final schema layout

Tracked foreign keys

Tracked CHECK constraints

Constraint existence

Constraint type

Validation state

Already validated constraints are safely skipped.

Detailed documentation lives under:

docs/sqlprocess/
├── load_postgresql.md
├── audit_relational_model.md
├── apply_relational_model.md
└── validate_relational_model.md

Synthetic World Architecture

Each simulated banking universe is defined by its own identity and configuration.

World Name + Variant
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

Worlds are isolated under:

worlds/<WORLD>/<VARIANT>/

Each world stores its own configuration, metadata, generated datasets, interim latent-state data, operational exports, audits, and manifests.

BTYT World Builder

The project includes a desktop interface for creating and launching synthetic worlds.

Current capabilities include:

World name and variant

Deterministic seed derivation

Fixed or ranged customer population

Observation-period configuration

Data-reliability settings

Pipeline start and end stages

Reference-asset materialization

Live stage status

Per-stage and global progress

Pause / resume / stop

Manifest generation and verification

World-folder access

Execution logging

Development launch command:

.\.venv\Scripts\python.exe -m world_builder.app

Generation Pipeline

The project orchestrator runs 15 stages.

#

Stage

Purpose

1

macro

Macroeconomic environment

2

banks

Banking market and financial dynamics

3

financial_institutions

Financial-institution network

4

branches

Branch network and annual state

5

customers

Individual and business customers

6

accounts

Account ownership and lifecycle

7

cards

Debit and credit-card lifecycle

8

loans

Retail and business lending

9

loan_snapshot

Monthly loan lifecycle and delinquency

10

external_shocks

External economic and operational shocks

11

transactions

Transaction engine and balances

12

campaigns

Campaign targets, exposures, and responses

13

branch_performance

Branch and consolidated performance

14

operational_exports

Imperfect operational representation

15

cross_system_audit

Integrated validation

The orchestrator uses fresh subprocesses and fail-fast execution by default.

Synthetic Banking Universe

Detailed analytical observation window:

January 2021 → December 2026

Some relationships may originate before 2021 to represent inherited historical state.

The universe includes customers, branches, products, accounts, cards, loans, monthly loan snapshots, transactions, balances, campaigns, financial institutions, market dynamics, macroeconomic conditions, external shocks, and bank/branch performance.

Large production worlds can generate tens of millions of transaction rows, so generated production data is intentionally excluded from normal Git history.

Data-Generation Philosophy

BTYT does not generate independent random tables.

Observable outcomes emerge from interacting mechanisms such as:

Customer heterogeneity

Product preferences

Account ownership

Branch relationships

Digital adoption

Lending behavior

Delinquency

Transaction activity

Seasonality

Banking-market evolution

External shocks

Local operational pressure

Controlled data-quality degradation

A macroeconomic or local event may influence several downstream systems, but it does not deterministically assign outcomes to individual entities.

Banking Network

Branches

BTYT contains a structurally defined network of 37 branches and agencies across Uruguay.

Branches differ by type, size, geography, administrative parent, opening history, strategic importance, and structural closure risk.

Branch closures are stochastic rather than hard-coded.

Financial system

BTYT operates inside a synthetic financial system containing:

BTYT itself

Domestic banks operating in Uruguay

International banking counterparties

Electronic-money institutions

Some real institution names are used only as structural references. All simulated values, trajectories, weights, affinities, shocks, and relationships are synthetic.

Transactions

The transaction engine supports:

Transfers

Debit purchases

Service payments

Cash operations

Loan payments

Interest credits

Loan disbursements

It also models digital adoption, channel migration, cash usage, failed transactions, internal-transfer pairing, counterparty institutions, branch usage, and account-balance reconciliation.

The canonical world contains approximately 76.8 million transaction rows, making the transaction layer the largest workload in the project.

Loans and Performance

Monthly loan snapshots track:

Outstanding balance

Interest rate

Scheduled payment

Actual payment

Days past due

Delinquency status

Arrears

Grain:

loan_id × year_month

Performance tables aggregate measures such as:

Active customers

Active accounts

Deposits

Loan balances

Transaction activity

Interest income and expense

Fee income

Operational costs

Credit losses

Net income

Analytical KPIs

Most BI ratios are intentionally not precomputed in Python. They will be derived in SQL and/or DAX.

Examples include:

Cost-to-Income Ratio

Net Interest Margin

Revenue per Customer

Cost per Transaction

Branch Margin

Credit Loss Ratio

Deposit Growth

Loan Growth

Digital Channel Share

Branch Profitability

Regional Profitability

Product Profitability

Customer Segment Performance

Next Analytical Milestone

With the relational model frozen, the next stage is reusable analytical SQL.

Planned areas include:

Customer portfolio

Deposits and account activity

Product performance

Branch profitability

Transaction-channel mix

Lending portfolio

Delinquency

Campaign response

External counterparties

Market context

Bank-wide profitability

Potential analytical views include:

customer portfolio summary
account and deposit evolution
loan portfolio composition
delinquency migration
transaction channel mix
branch operating performance
branch profitability
regional performance
product profitability
customer segmentation
campaign conversion
external counterparty activity
bank-wide monthly performance

These outputs will feed the first BI dashboards.

BI Layer

The PostgreSQL model is the stable analytical foundation.

Python
→ generates the world

PostgreSQL + SQL
→ structures and analyzes the world

Power BI / Tableau / Superset
→ communicates the results

The BI layer will focus on analytical views, KPI definitions, DAX measures, dimensional reporting logic, dashboard interaction, and visual storytelling.

Repository Structure

btyt-banking-analytics/
│
├── config/
├── resources/
│   └── reference/
│
├── worlds/
│   └── <WORLD>/
│       └── <VARIANT>/
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
│   │   ├── load_postgresql.py
│   │   ├── audit_relational_model.py
│   │   ├── apply_relational_model.py
│   │   └── validate_relational_model.py
│   ├── generate_btyt.py
│   └── generate_manifest.py
│
├── world_builder/
│   └── app.py
│
├── docs/
│   ├── architecture/
│   │   └── relational_model_btyt.png
│   ├── data_dictionary/
│   └── sqlprocess/
│       ├── load_postgresql.md
│       ├── audit_relational_model.md
│       ├── apply_relational_model.md
│       └── validate_relational_model.md
│
├── logo.png
└── README.md

Technology Stack

Implemented

Python

Pandas

NumPy

PyArrow / Parquet

PostgreSQL

SQL

SQLAlchemy

Psycopg

Git

GitHub

CustomTkinter

Deterministic RNG architecture

Cross-system auditing

Current analytical stage

SQL analytical queries

SQL views

Banking KPIs

Power BI

Power Query

DAX

Later stages

Tableau

Apache Superset

scikit-learn

Credit-risk modeling

Machine learning

Model explainability

MLflow

Local scoring service

Docker / Docker Compose

Technologies are added to the implemented stack only when their corresponding project stage is actually completed.

Main Analytical Question — Part I

How is BTYT performing, and where are the main opportunities and risks across its loan portfolio, deposits, products, customer segments, branches, channels, and banking relationships?

Part I will answer this through validated SQL, analytical views, banking KPIs, branch-performance analysis, customer and product analysis, transaction and channel analysis, lending and delinquency analysis, geographic analysis, and BI dashboards.

Part II — Credit Risk Analytics

Part II will reuse the same frozen BTYT universe for:

SQL-based feature extraction

Exploratory risk analysis

Feature engineering

Statistical modeling

Machine learning

Evaluation

Explainability

No separate disconnected dataset will be created.

Disclaimer

BTYT is a fictional bank created exclusively for educational and portfolio purposes.

All customers, accounts, cards, loans, transactions, balances, branch behavior, market behavior, banking relationships, financial values, campaign outcomes, and credit events represented in the project are synthetic.

The project contains no real customer data, confidential banking information, or actual bank transaction records.

Names of real financial institutions may appear only as structural references within the simulated banking environment. Synthetic metrics associated with those institutions must not be interpreted as actual reported financial results or observed market behavior.

Author

Santiago Castillo Marsicano

Economics & Sociology
Data Analytics | Business Intelligence