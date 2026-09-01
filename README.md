BTYT Banking Analytics

End-to-end banking analytics project for Banco de Treinta y Tres (BTYT), a fictional Uruguayan bank.

BTYT Banking Analytics is a portfolio project focused on the design and development of a realistic synthetic banking data environment.

The project models the operations of a fictional Uruguayan commercial bank through interconnected datasets representing branches, customers, products, accounts, cards, loans, balances, transactions, and marketing campaigns.

Rather than relying on a pre-existing dataset, the banking environment is generated programmatically in Python using business rules, probabilistic processes, temporal dependencies, and cross-table consistency constraints.

The project is being developed progressively from data generation and validation to relational database implementation, SQL analytics, business intelligence, and credit risk modeling.

Project Objectives

Design a realistic relational banking data model.

Generate synthetic banking data using Python.

Model heterogeneous customer and financial behavior.

Preserve temporal and relational consistency across datasets.

Implement data quality and integrity validation.

Build a reproducible data generation pipeline.

Develop a PostgreSQL analytical database and SQL layer.

Create business intelligence dashboards and banking KPIs.

Explore credit risk modeling and machine learning techniques.

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

Credit card activity

Loan monthly performance

Marketing

Campaigns

Campaign geography

Campaign channels

Customer targeting

Campaign exposures

The detailed observational period covers 2021–2026, while selected banking relationships may originate before 2021 to represent inherited historical state.

Synthetic Data Generation

A central component of BTYT is its synthetic data generation process.

The objective is not to generate independent random tables, but to create a coherent banking environment in which observable patterns emerge from underlying behavioral and business rules.

The generation process incorporates:

Customer heterogeneity

Product preferences

Account ownership structures

Branch relationships

Income and business characteristics

Digital and physical banking preferences

Financial behavior

Loan lifecycle dynamics

Transaction activity

Temporal evolution

Seasonality

Probabilistic events

Cross-table dependencies

This approach allows the resulting dataset to behave more like an interconnected banking system than a collection of unrelated synthetic records.

Data Integrity

Validation is incorporated throughout the generation process.

Examples include:

Referential integrity between banking entities

Temporal consistency between opening and closing dates

Account and customer lifecycle constraints

Card-account compatibility rules

Loan lifecycle consistency

Monthly loan balance evolution

Transaction and account balance reconciliation

Prevention of negative account balances

Validation of transaction failures and financial behavior

Economic and behavioral diagnostics are also used to evaluate whether generated patterns remain plausible.

Current Development Status

Component

Status

Branches

Completed

Other banks

Completed

Customers

Completed

Products

Completed

Accounts

Completed

Cards

Completed

Loans

Completed

Loan Monthly Snapshot

Completed

Transactions

In development

Account Balances

In development

Credit Card Monthly Snapshot

Planned

Credit Card Transactions

Planned

Campaign Customer Modeling

Planned

Final Cross-Table Validation

Planned

PostgreSQL Database

Planned

SQL Analytics

Planned

Power BI

Planned

Tableau / Apache Superset

Planned

Credit Risk Modeling

Planned

Project Roadmap

Synthetic Data Generation

↓

Data Validation & Quality Control

↓

PostgreSQL Relational Database

↓

SQL Analytical Layer

↓

Business Intelligence

↓

Credit Risk & Machine Learning

The BI stage will explore banking performance through tools such as Power BI, Tableau, and Apache Superset.

A later stage will focus on credit risk modeling using statistical and machine learning approaches.

Technology Stack

Currently Used

Python

Pandas

NumPy

Git

GitHub

Planned

PostgreSQL

SQL

Power BI

Tableau

Apache Superset

scikit-learn

Planned technologies are added to the implemented stack only as their corresponding project stages are completed.

Repository Structure

btyt-banking-analytics/
│
├── data/
│   ├── raw/
│   ├── interim/
│   └── processed/
│
├── database/
│
├── scripts/
│
└── README.md

Large generated datasets are not intended to be stored directly in the repository. The project is designed around reproducible generation from code.

Reproducibility

BTYT is designed as a reproducible synthetic banking environment.

Generation scripts define the underlying business rules and probabilistic processes used to construct the banking system. Random seeds can be used to reproduce specific generated environments while allowing alternative synthetic banking worlds to be generated from the same underlying model.

Disclaimer

BTYT is a fictional bank created exclusively for educational and portfolio purposes.

All customers, accounts, transactions, financial records, branches, and banking activities represented in the project are synthetic. The project does not contain real customer or confidential banking data.

Author

Santiago Castillo Marsicano

Economics & Sociology
Data Analytics | Business Intelligence

