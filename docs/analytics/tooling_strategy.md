# BTYT Part I — Analytics Tooling Strategy

## 1. Purpose

BTYT Part I intentionally uses several analytical tools even though a large share of the work could technically be completed with PostgreSQL + Power BI.

The reason is not to maximize the number of technologies. The goal is to demonstrate:

- analytical adaptability;
- flexibility across different professional environments;
- clear separation of responsibilities;
- reproducibility;
- good judgment when choosing tools;
- the ability to reuse a common analytical layer across several consumers;
- the ability to avoid unnecessary duplication.

The central rule is:

> **One business question should have one primary analytical home.**

Different tools may consume the same PostgreSQL data, but they should not repeatedly reproduce the same analysis without a clear reason.

---

# 2. Architecture at a glance

The architecture should be read from left to right:

```text
DATA GENERATION
Python generators
      ↓

CENTRAL DATA PLATFORM
PostgreSQL
      ↓

ANALYTICAL PREPARATION
SQL exploration
      ↓
Reusable analytical views
      ↓

SPECIALIZED CONSUMERS
├── Python / Pandas / Jupyter
│   → statistical and exploratory analytics
│
├── Excel
│   → management and ad hoc analysis
│
├── Power BI
│   → main corporate BI dashboard
│
├── Tableau
│   → geography, campaigns and spatial storytelling
│
└── Superset
    → operational / SQL-first web monitoring

SUPPORTING TOOLS
├── Docker
│   → reproducible infrastructure
│
└── Pentaho
    → optional data-quality / ETL demonstration
```

The key idea is:

> **PostgreSQL is the common source.  
> SQL prepares reusable data.  
> Each downstream tool has a different analytical purpose.**

---

# 3. Tool ownership matrix

| Tool | Primary role | Main deliverable | Main analytical territory | What it should NOT do |
|---|---|---|---|---|
| **PostgreSQL + SQL** | Central analytical data layer | Views, reusable datasets, KPI-ready logic | joins, aggregations, common business logic, performance | dashboards |
| **Python + Pandas + Jupyter** | Statistical / exploratory analytics | Analytical notebook | correlations, distributions, outliers, segmentation, exploratory regressions | act as the main BI dashboard |
| **Excel** | Management / ad hoc analysis | Executive workbook | branch and customer management, pivots, formulas, Power Query | duplicate Power BI |
| **Power BI** | Main corporate BI | Multi-page interactive dashboard | bank performance, customers, loans, transactions, branches, products | deep geographic storytelling |
| **Tableau** | Geography and storytelling | 1–2 focused dashboards | geography, branch territory, campaigns, regional response | reproduce the Power BI executive dashboard |
| **Superset** | SQL-first web BI | Operational dashboard | monitoring, activity, SQL datasets, browser analytics | compete visually with Power BI |
| **Docker** | Infrastructure | Reproducible environment | containerized services | analysis |
| **Pentaho** | Optional ETL / Data Quality | Small visual ETL workflow | dirty-data cleaning and validation | rebuild the main Python pipeline |
| **DBeaver** | Dedicated SQL/database client | No portfolio deliverable by itself | intensive SQL work, schema browsing, result grids, ad hoc exploration, database inspection | replace the repository as the source of truth |
| **VS Code SQL** | Versioned SQL development inside the repo | `.sql` files committed to Git | reproducible queries, views, KPI logic, documentation-adjacent SQL work | become the only database inspection tool if another client is more comfortable |
| **pgAdmin** | PostgreSQL administration | No portfolio deliverable by itself | server administration, connection management, schema inspection, PostgreSQL-specific tasks | be the primary analytics workspace |

---

# 4. What belongs where

## Development interfaces: DBeaver vs VS Code vs pgAdmin

These tools do not represent separate analytical layers. They are different interfaces for working with the same PostgreSQL database.

### DBeaver

DBeaver is the preferred candidate for intensive SQL exploration if it proves more comfortable than VS Code.

Best uses:

- browsing schemas and tables;
- writing and testing SQL interactively;
- viewing results in grid form;
- filtering and exporting query results;
- inspecting columns, keys and relationships;
- ad hoc database exploration.

DBeaver is especially useful when the task is:

> “I want to work directly with the database and inspect results quickly.”

### VS Code

VS Code remains the source-of-truth environment for reproducible project work.

Best uses:

- storing `.sql` files inside the repository;
- versioning SQL with Git;
- maintaining views and KPI logic;
- keeping SQL close to Python and documentation;
- preserving reproducibility.

The practical rule is:

> **Explore quickly in DBeaver if convenient.  
> Preserve anything important in versioned `.sql` files in VS Code.**

### pgAdmin

pgAdmin remains available primarily for PostgreSQL administration.

Best uses:

- server and connection management;
- PostgreSQL-specific inspection;
- permissions and administrative tasks;
- occasional database maintenance.

It is not required to be the primary SQL analytics environment.

### Final decision

The project does not need to choose only one interface.

The expected workflow is:

```text
DBeaver
→ fast SQL exploration and database inspection

VS Code
→ official versioned SQL and repository work

pgAdmin
→ PostgreSQL administration
```

If DBeaver does not provide a meaningful usability advantage, SQL work can remain primarily in VS Code.

---


## PostgreSQL + SQL

### Main responsibility

SQL is the reusable analytical foundation.

If Power BI, Excel, Tableau and Superset all need the same transformation, that logic should preferably live in PostgreSQL.

Example:

```text
branch profitability logic
        ↓
PostgreSQL view
        ↓
Excel
Power BI
Tableau
Superset
```

This prevents four different definitions of the same metric.

### SQL is used for

- joins;
- filters;
- aggregations;
- reusable analytical views;
- common business logic;
- KPI-ready datasets;
- query performance;
- index decisions;
- large-volume processing.

### Working sequence

```text
Business question
        ↓
Exploratory SQL
        ↓
Validation
        ↓
Reusable view if justified
        ↓
Downstream tool
```

### Suggested repository structure

```text
scripts/
└── sql/
    ├── exploration/
    ├── views/
    ├── kpis/
    └── performance/
```

Possible view names:

```text
vw_branch_profitability
vw_bank_performance
vw_customer_demographics
vw_customer_360
vw_loan_portfolio
vw_loan_delinquency
vw_transaction_channels
vw_campaign_conversion
```

Views should only be created when there is a real analytical use case.

---

# 5. Python + Pandas + Jupyter

## Main responsibility

Python owns the **statistical and exploratory layer**.

Its role is different from Power BI.

Power BI answers:

> How is the bank performing?

Python answers:

> What quantitative patterns, relationships and distributions exist in the data?

## Main analyses

- descriptive statistics;
- correlations;
- distributions;
- outliers;
- segmentation;
- comparison between groups;
- exploratory regressions;
- statistical profiling;
- analytical prototyping.

Examples:

```text
monthly_income × product count
age × digital adoption
deposits × loan balances
branch customers × branch profitability
transaction activity × income
```

Correlation must always be interpreted carefully:

> **Correlation is association, not causality.**

## Suggested deliverable

```text
notebooks/
└── btyt_exploratory_analysis.ipynb
```

Possible notebook sections:

1. Statistical profile
2. Distributions
3. Correlation analysis
4. Outlier analysis
5. Segmentation
6. Exploratory regressions
7. Interpretation and limitations

This component is particularly relevant for the quantitative / academic side of BTYT.

---

# 6. Excel

## Main responsibility

Excel owns the **management and ad hoc analysis layer**.

It should demonstrate genuine advanced Excel competence.

## Suggested deliverable

```text
BTYT_Executive_Analysis.xlsx
```

## Traditional Excel features

- Power Query;
- PivotTables;
- PivotCharts;
- slicers;
- XLOOKUP;
- SUMIFS;
- AVERAGEIFS;
- dynamic arrays;
- conditional formatting;
- management tables;
- ad hoc analysis.

## Python in Excel / Python integration

Python is used selectively, not as a replacement for Excel.

Possible uses:

- statistical calculations;
- complex segmentation;
- specialized transformations;
- automated outputs.

The goal is:

> **Demonstrate advanced Excel + the ability to integrate it with Python.**

Not:

> Use Python for everything and reduce Excel to a viewer.

## Primary analytical theme

```text
Branch and Customer Management
```

Excel should be flexible, interactive and useful for management-style analysis.

---

# 7. Power BI

## Main responsibility

Power BI is the **main corporate BI product** of BTYT Part I.

Its main question is:

> **How is the bank performing?**

Power BI should provide the broadest integrated view of BTYT.

## Proposed dashboard pages

### 1. Executive Overview

Possible KPIs:

- active customers;
- active accounts;
- deposits;
- loan portfolio;
- total revenue;
- operating costs;
- net income;
- cost-to-income;
- customer growth;
- deposit growth;
- loan growth.

### 2. Customer 360

Detailed and interactive customer analysis.

Possible dimensions:

- age;
- age group;
- gender;
- customer type;
- income;
- employment;
- region;
- department;
- primary branch;
- products;
- accounts;
- loans;
- cards;
- transaction behavior;
- preferred channel.

Possible KPIs:

- active customers;
- average age;
- average income;
- products per customer;
- digital share;
- customer distribution by segment.

Example filter combination:

```text
Region = METROPOLITAN
Age group = 25–34
Gender = F
```

### 3. Loans & Credit Quality

Possible topics:

- outstanding balance;
- delinquency;
- days past due;
- arrears;
- credit loss;
- portfolio evolution;
- segment performance.

### 4. Transactions & Channels

Possible topics:

- transaction count;
- transaction volume;
- transaction type;
- digital versus cash;
- channel evolution;
- branch transactions.

### 5. Branch Performance

Possible topics:

- revenue;
- costs;
- net income;
- customers;
- deposits;
- loans;
- branch rankings;
- efficiency.

### 6. Products & Portfolio

Possible topics:

- product mix;
- account penetration;
- cards;
- loans;
- customer-product relationships;
- portfolio growth.

## What Power BI should not own

It should not deeply duplicate:

- Tableau geographic storytelling;
- Excel management/ad hoc analysis;
- Superset operational monitoring;
- Python statistical exploration.

---

# 8. Tableau

## Main responsibility

Tableau owns:

```text
Geography + Campaigns + Spatial Storytelling
```

Its main question is:

> **Where do banking and campaign phenomena occur, and how do they differ territorially?**

## Possible themes

- branch geography;
- regional profitability;
- customer concentration;
- deposits by territory;
- loan concentration;
- performance by department;
- campaign coverage;
- campaign response by geography;
- regional differences.

Campaign analysis can appear elsewhere, but Tableau should own the deepest geographic and narrative version.

## Expected scope

Prefer:

```text
1–2 strong dashboards
```

rather than reproducing the entire Power BI product.

---

# 9. Apache Superset

## Main responsibility

Superset owns:

```text
Operational / SQL-first monitoring
```

Its main question is:

> **What is happening operationally in the data?**

## Possible use cases

- activity monitoring;
- transaction evolution;
- operational metrics;
- SQL-based datasets;
- browser dashboards;
- direct PostgreSQL integration.

Superset demonstrates that BTYT's analytical layer can also serve a web-based BI environment.

It does not need to match Power BI's visual depth.

---

# 10. Docker

## Main responsibility

Docker provides reproducibility.

It does not analyze data.

Potential architecture:

```text
Docker Compose
├── PostgreSQL
├── Superset
└── supporting services
```

Possible objective:

```bash
docker compose up
```

and obtain a reproducible environment.

Docker should only be introduced where it adds practical value.

---

# 11. Pentaho

## Current status

Deferred.

Pentaho should not be inserted into the main BTYT pipeline because Python already performs the generation and ETL work successfully.

## Future role

Pentaho may be added near the end of Part I as a **Data Quality / ETL demonstration**.

Possible flow:

```text
canonical clean tables
        ↓
controlled dirty copies
        ↓
Pentaho
        ↓
validation / cleaning / transformation
        ↓
clean quality tables
```

Potential deliberate problems:

- NULL values;
- duplicates;
- inconsistent categories;
- invalid dates;
- leading/trailing spaces;
- inconsistent capitalization;
- unrealistic income values;
- malformed codes.

Possible Pentaho steps:

```text
Table Input
→ Select Values
→ Filter Rows
→ Replace in String
→ Data Validator
→ Unique Rows
→ Calculator
→ Table Output
```

The point is to demonstrate visual ETL without rebuilding the working Python pipeline.

---

# 12. Data Quality module

This module should only be implemented after the main analytical work is nearly complete.

The canonical BTYT database remains unchanged.

Possible schema:

```text
quality
```

Potential tables:

```text
quality.dirty_customers
quality.dirty_accounts
quality.dirty_transactions_sample

quality.clean_customers
quality.clean_accounts
quality.clean_transactions_sample
```

Possible quality metrics:

- missing percentage;
- duplicate percentage;
- invalid-value percentage;
- completeness;
- referential integrity;
- before/after quality comparison.

This module can combine SQL, Python and Pentaho.

---

# 13. KPI strategy

KPIs are performance measures.

They are not the same as dimensions.

Examples:

```text
Dimension: gender
KPI: female customer share

Dimension: branch
KPI: branch net income

Dimension: region
KPI: customer share by region
```

Potential BTYT KPIs:

- Net Income
- Cost-to-Income Ratio
- Branch Margin
- Revenue per Customer
- Average Deposit Balance
- Average Loan Balance
- Customer Growth
- Deposit Growth
- Loan Growth
- Delinquency Rate
- Credit Loss Ratio
- Digital Share
- Cost per Transaction
- Campaign Conversion Rate

Each important KPI should eventually document:

```text
Name
Business definition
Numerator
Denominator
Grain
Frequency
SQL source
Interpretation
```

---

# 14. Analytical dimensions

Important analytical dimensions include:

- gender;
- age;
- age group;
- customer type;
- region;
- department;
- branch;
- product;
- transaction channel;
- loan status;
- delinquency status;
- campaign;
- customer segment.

These dimensions allow KPIs to be segmented.

Example:

```text
KPI = Net Income
Dimension = Branch

Question:
Which branches generate the highest net income?
```

---

# 15. Business-question-first principle

Analytical work begins with questions, not with dashboards or views.

Preferred sequence:

```text
1. Define business question
2. Explore with SQL
3. Validate result
4. Identify useful metric / KPI
5. Decide whether logic should be reusable
6. Create analytical view if necessary
7. Assign one primary tool
8. Build the final output
```

---

# 16. Analytical questions by domain

## Branches

- Which branches are the most profitable?
- Are large branches always more profitable?
- How does performance differ by region?
- Which branches generate the highest revenue per customer?

## Customers

- How are customers distributed by age and gender?
- How do income levels differ by region?
- Which customer segments hold more products?
- Does digital adoption differ by age?
- Which profiles generate more banking activity?

## Loans

- Where is delinquency concentrated?
- Which profiles show higher days past due?
- How does loan performance vary by region or product?
- How does macro stress relate to credit quality?

## Transactions

- How has digital activity evolved?
- Is cash usage declining?
- Which profiles generate the highest transaction volume?
- Which channels dominate each transaction type?

## Performance

- How have deposits, loans, revenue and net income evolved?
- Which cost components drive profitability?
- Which branches are most efficient?
- How stable is profitability over time?

## Campaigns

- Which campaigns produce the strongest response?
- Which territories respond better?
- Do campaign outcomes differ by segment?

---

# 17. Primary ownership of analytical themes

| Analytical theme | Primary tool |
|---|---|
| Common transformations and joins | SQL / PostgreSQL |
| Statistical exploration | Python / Pandas |
| Correlations and exploratory regressions | Python / Pandas |
| Management and ad hoc analysis | Excel |
| Executive banking performance | Power BI |
| Customer 360 | Power BI |
| Credit quality | Power BI |
| Transactions and channels | Power BI |
| Branch performance | Power BI |
| Geography | Tableau |
| Campaign geography and territorial response | Tableau |
| Operational SQL monitoring | Superset |
| Dirty-data ETL demonstration | Pentaho |
| Reproducible infrastructure | Docker |

---

# 18. Why use multiple tools?

A large share of BTYT Part I could technically be completed with PostgreSQL + Power BI.

The multi-tool strategy is intentional because BTYT is also designed to demonstrate:

- adaptability;
- flexibility;
- cross-tool competence;
- readiness for different organizational stacks;
- understanding of tool strengths and limitations;
- reproducibility;
- ability to choose the right environment for the task.

The portfolio message should therefore be:

> **BTYT does not use multiple tools because the analysis requires maximum technological complexity.  
> It uses them selectively to demonstrate the ability to solve analytical problems across different professional environments while preserving one coherent data architecture.**

---

# 19. Anti-duplication rules

The project should avoid:

- rebuilding identical KPIs in every tool;
- reproducing the Power BI dashboard in Tableau;
- creating views without analytical demand;
- forcing every tool into every problem;
- using Python where SQL is simpler;
- using BI tools for work that belongs in statistical analysis;
- adding technologies only to increase the tool count.

The preferred model is:

```text
Common logic
→ PostgreSQL

Statistical questions
→ Python

Management questions
→ Excel

Corporate BI
→ Power BI

Geography / campaigns
→ Tableau

Operational monitoring
→ Superset
```

---

# 20. Current execution order

The agreed Part I sequence is:

```text
1. Define business questions
2. SQL exploration
3. Create justified analytical views
4. Define KPI catalog
5. Python / Pandas statistical analytics
6. Excel management analysis
7. Power BI corporate dashboard
8. Tableau geography and campaigns
9. Superset operational dashboard
10. SQL performance review and indexing
11. Docker reproducibility
12. Optional Data Quality + Pentaho module
13. Final documentation and portfolio publication
```

---

# 21. Final guiding principle

BTYT Part I is not designed to prove that every problem can be solved with every tool.

It is designed to prove that the analyst can:

- identify the business question;
- select the appropriate source;
- prepare reusable data correctly;
- choose the most suitable analytical environment;
- avoid redundant transformations;
- interpret results;
- communicate findings professionally;
- reproduce the workflow.

The final philosophy is:

> **Build once at the data layer.  
> Analyze where it makes sense.  
> Visualize where it communicates best.  
> Do not duplicate without purpose.**
