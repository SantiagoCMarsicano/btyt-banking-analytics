BTYT Banking Analytics

End-to-end banking analytics project for Banco de Treinta y Tres (BTYT), a fictional Uruguayan commercial bank.

BTYT Banking Analytics is a portfolio project focused on the design, generation, validation, storage, and analysis of a realistic synthetic banking environment.

Rather than relying on a pre-existing dataset, the project builds the bank programmatically in Python using business rules, probabilistic processes, temporal dependencies, cross-table consistency constraints, and explicit validation layers.

The project is structured in two main analytical stages:

Part I — Business Intelligence & Performance Management

Part II — Credit Risk Analytics & Machine Learning

The same synthetic banking universe is reused across both stages.

Project Objectives

The main objectives are to:

Design a realistic relational banking data model.

Generate synthetic banking data using Python.

Model heterogeneous customer, branch, transaction, and credit behavior.

Preserve temporal and relational consistency across datasets.

Implement structural, financial, and behavioral validation.

Build a reproducible data generation pipeline.

Create an analytical SQL layer.

Develop banking KPIs and business intelligence dashboards.

Analyze branch and bank profitability.

Prepare the same banking universe for later credit risk modeling.

Current Project Status

Part I — Source Data Generation

Completed and frozen.

The synthetic banking environment for the 2021–2026 analytical period has been generated and validated.

Component

Status

Branch Network

Frozen

Banking Network

Frozen

Customers

Frozen

Products

Frozen

Accounts

Frozen

Cards

Frozen

Loans

Frozen

Loan Lifecycle Bridge

Frozen

Loan Monthly Snapshot

Frozen

Transactions

Frozen

Account Balances

Frozen

Campaign Master Data

Frozen

Branch Monthly Performance

Frozen

Bank Monthly Performance

Frozen

Cross-table Validation

Passed

Next Stage

The project now moves from data generation to analytics:

Synthetic Data Generation
        ↓
Validation & Quality Control
        ↓
Local Relational Database
        ↓
SQL Analytical Layer
        ↓
Power BI Semantic Model
        ↓
Business Intelligence Dashboards
        ↓
Credit Risk & Machine Learning

Synthetic Banking Universe

The detailed observational period covers January 2021 through December 2026.

Selected customer, account, branch, and credit relationships may originate before 2021 in order to represent inherited historical state.

Current canonical environment:

Entity

Size

Customers

10,000

Accounts

21,040

Cards

27,888

Loans

21,044

Loan monthly snapshot rows

455,370

Transactions

6,959,634

Account-month balance rows

674,619

Branches

37

Branch-month performance rows

2,664

Bank-month performance rows

72

The transaction engine contains approximately 6.96 million transactions, of which approximately 6.78 million are completed transactions.

Banking Data Model

Core Banking

Branches

Customers

Products

Accounts

Cards

Loans

Financial Activity

Account balances

Transactions

Loan monthly snapshots

Branch monthly performance

Bank monthly performance

Banking Network

Domestic and foreign banking counterparties

Annual bank financial indicators

Market weights

Macro environment

Banking world parameters

Marketing

Campaigns

Campaign geography

Campaign channels

Data Generation Philosophy

The objective is not to create independent random tables.

The project generates a coherent banking system in which observable outcomes emerge from underlying business rules and stochastic mechanisms.

The generation process incorporates:

Customer heterogeneity

Product preferences

Account ownership structures

Branch relationships

Income and business characteristics

Digital and physical banking preferences

Financial behavior

Loan lifecycle dynamics

Delinquency and write-off processes

Transaction activity

Seasonality

Temporal evolution

External and local shocks

Cross-table dependencies

Branch-level operating pressure

Banking market dynamics

The central design principle is:

Fiction, yes. Fantasy, no.

The data is synthetic, but relationships between variables are designed to remain economically and operationally plausible.

Branch Network

BTYT operates a synthetic nationwide network of 37 branches and agencies across Uruguay.

The branch system includes:

large urban branches,

regional branches,

small agencies,

premium commercial locations,

historically inherited offices,

heterogeneous operating structures,

branch-specific cost and activity patterns.

Branches can experience different levels of:

customer pressure,

deposit pressure,

transaction pressure,

credit pressure,

cost pressure,

digital substitution,

operational pressure,

local shocks.

These variables belong to the internal data-generating process and are not directly exposed as final BI metrics.

Observed branch performance is allowed to emerge from the underlying system.

Banking Network

BTYT interacts with a synthetic banking network containing:

BTYT itself,

major domestic banks operating in Uruguay,

selected international banking counterparties.

Some institution names correspond to real banks in order to create a recognizable banking environment.

All simulated market weights, transaction relationships, financial indicators, customer behavior, and interbank activity are synthetic.

The project does not claim that these generated values represent actual bank market shares, customer behavior, transaction flows, or reported financial statements.

Transactions

The transaction engine generates approximately 6.96 million transaction records.

Transaction types include:

Transfers in

Transfers out

Debit purchases

Service payments

Cash withdrawals

Cash deposits

Loan payments

Interest credits

Loan disbursements

Transactions include:

transaction datetime,

account,

direction,

channel,

amount,

counterparty type,

transfer scope,

counterparty bank,

physical branch when applicable,

transaction status,

merchant category,

failure reason.

Transfer scope distinguishes:

internal BTYT transfers,

domestic external transfers,

international transfers.

The engine also models digital adoption, channel migration, failed transactions, cash usage, and internal transfer reconciliation.

Loans and Credit Performance

The lending system contains both retail and business credit products.

Examples include:

Personal loans

Auto loans

Mortgage loans

SME loans

Business credit lines

Agricultural loans

Business leasing

Loan behavior is modeled through a dedicated monthly snapshot containing:

outstanding balance,

current interest rate,

scheduled payment,

actual payment,

days past due,

delinquency status,

arrears amount.

Loan lifecycle events include:

scheduled maturity,

early prepayment,

restructuring after default,

write-off,

facility expiry,

open current exposures,

open default exposures,

severe delinquency states at the analytical cutoff.

The final performance engine recognizes loan provisioning changes and terminal write-off losses.

Branch and Bank Performance

Part I includes a dedicated profitability layer.

branch_monthly_performance.csv

Grain: one branch per month.

Period:

2021-01 → 2026-12

Rows:

37 branches × 72 months = 2,664 rows

Main fields include:

active customers,

active accounts,

average deposits,

average loan balance,

transaction count,

transaction volume,

physical branch transaction count,

interest income,

interest expense,

net interest income,

fee income,

total revenue,

personnel cost,

fixed cost,

variable cost,

operational cost,

total operating cost,

credit loss,

pre-provision profit,

net income.

bank_monthly_performance.csv

The consolidated bank-level table contains 72 monthly observations and reconciles exactly with the aggregation of branch-level performance.

Final Performance Calibration

The frozen model produces:

Fee income / revenue: approximately 6.13%

Annualized credit loss / average loan portfolio: approximately 1.05%

Meaningful branch-level profitability dispersion

Both profitable and loss-making branches

A negative consolidated result in 2021 followed by stronger performance in later years

Provision releases where justified by changes in required credit reserves

The project intentionally avoids forcing all branches or all years to be profitable.

Analytical KPIs

The project does not precompute most BI ratios in CSV outputs.

They are intended to be calculated in SQL and/or DAX.

Examples include:

Cost-to-Income Ratio

Net Interest Margin

Revenue per Customer

Cost per Customer

Cost per Transaction

Branch Margin

Credit Loss Ratio

Deposit Growth

Loan Growth

Transaction Growth

Digital Channel Share

Branch Profitability

Regional Profitability

Product Profitability

Customer Segment Performance

Data Integrity and Validation

Validation is incorporated throughout the generation process.

Examples include:

Referential integrity between banking entities

Temporal consistency between opening and closing dates

Account lifecycle constraints

Card-account compatibility

Loan lifecycle consistency

Loan snapshot continuity

Transaction reconciliation

Account balance reconciliation

Prevention of negative balances

Failed transaction consistency

Internal transfer pairing

Counterparty bank validation

Branch-month to bank-month reconciliation

Structural profitability identities

Economic and behavioral audits are also used to verify that generated patterns remain plausible.

Final branch performance reconciliation:

SUM(branch_monthly_performance)
==
bank_monthly_performance

Status: PASS

Repository Structure

btyt-banking-analytics/
│
├── data/
│   ├── generated/
│   ├── interim/
│   └── master/
│
├── database/
│
├── scripts/
│
└── README.md

data/master/

Small manually controlled reference tables and business definitions.

Examples:

products

campaigns

campaign channels

campaign geography

data/interim/

Internal generation artifacts, latent state tables, bridges, audits, and reproducibility outputs.

Examples:

branch yearly state

loan lifecycle bridge

transaction world parameters

internal transfer pairs

generation audits

data/generated/

Canonical observable banking datasets used by downstream analytics.

Examples:

customers

accounts

cards

loans

loan monthly snapshot

transactions

account balances

branches

banks

branch monthly performance

bank monthly performance

Large Generated Files

Large generated datasets are intentionally excluded from Git when appropriate.

In particular, multi-million-row transaction data can exceed GitHub file-size limits.

The repository is therefore designed around reproducible generation from code, rather than storing every generated dataset directly in version control.

Reproducibility

BTYT is designed as a reproducible synthetic banking environment.

Generation scripts define the underlying:

business rules,

probability distributions,

economic assumptions,

temporal processes,

stochastic events,

validation constraints.

Random seeds are used to reproduce canonical synthetic worlds while preserving the ability to generate alternative environments from the same model architecture.

Once a generated component passes its structural and economic audits, it is frozen as part of the canonical BTYT environment.

Technology Stack

Implemented

Python

Pandas

NumPy

Git

GitHub

Next Stage

SQL

Local relational database

Power BI

Power Query

DAX

Planned / Later Stage

Tableau

Apache Superset

scikit-learn

Credit risk modeling

Machine learning

Explainability

Technologies are added to the implemented stack only when their corresponding project stage is completed.

Part I — Business Intelligence & Performance Management

The main analytical question is:

How is BTYT performing, and where are the main opportunities and risks across its loan portfolio, deposits, products, customer segments, branches, and banking relationships?

Part I will use the frozen synthetic banking environment to build:

SQL analytical views,

a BI semantic model,

banking KPIs,

branch performance dashboards,

customer and product analysis,

transaction and channel analysis,

lending and delinquency analysis,

geographic analysis.

Part II — Credit Risk Analytics

Part II will reuse the same underlying customers, products, branches, accounts, loans, and historical credit behavior.

The objective is to build a credit risk workflow including:

feature engineering,

exploratory risk analysis,

SQL-based feature extraction,

statistical modeling,

machine learning,

model evaluation,

explainability.

No separate disconnected dataset will be created for Part II.

Disclaimer

BTYT is a fictional bank created exclusively for educational and portfolio purposes.

All customers, accounts, transactions, balances, financial records, branches, market behavior, banking relationships, and credit events represented in the project are synthetic.

The project contains no real customer data, confidential banking information, or actual bank transaction records.

Names of real financial institutions may be used only as structural references within the simulated banking environment.

Synthetic metrics associated with those institutions must not be interpreted as actual reported financial results or observed market behavior.

Author

Santiago Castillo Marsicano

Economics & Sociology
Data Analytics | Business Intelligence