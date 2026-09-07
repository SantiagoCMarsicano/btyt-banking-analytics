BTYT Banking Analytics



Banco de Treinta y Tres (BTYT) is a fictional Uruguayan commercial bank used as the analytical universe for an end-to-end banking data project.



BTYT Banking Analytics combines synthetic data generation, banking-domain modeling, reproducible simulation, validation, SQL, business intelligence, and later credit-risk modeling in one shared banking universe.



Fiction, yes. Fantasy, no.

The data is synthetic, but the relationships, temporal dynamics, business rules, and accounting constraints are designed to remain economically and operationally plausible.



Project Scope



The project is divided into two main analytical stages:



Part I — Business Intelligence \& Performance Management



Part I builds and validates the synthetic banking universe and then uses it for:



relational database design;



SQL analytics;



banking KPIs;



Power BI;



Power Query and DAX;



Tableau / geographic analysis;



Apache Superset;



customer, product, branch, transaction, lending, and profitability analysis.



Part II — Credit Risk Analytics \& Machine Learning



Part II reuses the same frozen banking universe for:



SQL-based feature extraction;



exploratory credit-risk analysis;



feature engineering;



statistical modeling;



machine learning;



model evaluation;



explainability;



later local experiment tracking and scoring infrastructure.



No disconnected replacement dataset is created for Part II.



Current Project Status



BTYT is currently in the canonical world generation and validation phase.



The data-generation architecture has been migrated from a collection of loosely coupled scripts to a reproducible world-based system with:



deterministic world identity;



centralized world configuration;



isolated per-world storage;



dedicated RNG namespaces and streams;



a 15-stage orchestrated pipeline;



cross-system auditing;



operational data-reliability layers;



manifest generation;



dataset fingerprints;



a desktop BTYT World Builder interface.



The final large BTYT analytical world is not yet frozen. Smoke and integration worlds are used to validate the complete generation architecture before the canonical dataset is produced.



World-Based Architecture



Each simulated banking universe is defined by a world identity and configuration.



World Name

&#x20;   +

Variant

&#x20;   ↓

Deterministic World Seed

&#x20;   ↓

World Configuration

&#x20;   ↓

15-Stage Generation Pipeline

&#x20;   ↓

Cross-System Audit

&#x20;   ↓

Manifest + Fingerprint

&#x20;   ↓

Frozen Analytical World



Worlds are isolated under:



worlds/<WORLD>/<VARIANT>/



A world contains its own metadata, configuration snapshot, generated datasets, interim latent-state data, operational exports, audit outputs, and manifests.



BTYT World Builder



The project includes a desktop interface for configuring and launching synthetic worlds.



The BTYT World Builder currently supports:



world name and variant;



deterministic seed derivation;



fixed or ranged customer population;



observation-period configuration;



data-reliability settings;



pipeline start and end stages;



automatic reference-asset materialization;



live stage status;



per-stage progress;



global pipeline progress;



pause / resume / stop controls;



manifest generation;



manifest verification;



world-folder access;



execution logging.



Current development launch command:



.\\.venv\\Scripts\\python.exe -m world\_builder.app



A standalone Windows executable is considered a packaging enhancement rather than a dependency of the analytical project.



Generation Pipeline



The full project orchestrator executes 15 stages:



\#



Stage



Purpose



1



macro



Macroeconomic environment



2



banks



Banking market and financial dynamics



3



financial\_institutions



Financial-institution reference network



4



branches



Dynamic branch network and annual branch state



5



customers



Individual and business customers



6



accounts



Customer-account relationships and lifecycle



7



cards



Debit and credit-card lifecycle



8



loans



Retail and business lending



9



loan\_snapshot



Monthly loan lifecycle and delinquency state



10



external\_shocks



Shared external operational/economic shocks



11



transactions



Transaction engine and account balances



12



campaigns



Campaign targets, exposures, and responses



13



branch\_performance



Branch and consolidated bank performance



14



operational\_exports



Imperfect operational representation



15



cross\_system\_audit



Integrated cross-system validation



The orchestrator runs each stage in a fresh subprocess and uses fail-fast execution by default.



Synthetic Banking Universe



The detailed analytical observation window is:



January 2021 → December 2026



Some customer, account, card, branch, and credit relationships may originate before 2021 to represent inherited historical state.



The universe includes core banking, financial activity, banking-market, marketing, world-state, and operational datasets, including branches, customers, products, accounts, cards, loans, transactions, balances, monthly credit snapshots, campaigns, bank dynamics, external shocks, and performance tables.



Data-Generation Philosophy



BTYT does not generate independent random tables.



The project generates a coherent banking system in which observable outcomes emerge from underlying mechanisms such as customer heterogeneity, product preferences, account ownership, branch relationships, digital adoption, lending behavior, delinquency dynamics, transaction activity, seasonality, market evolution, external and local shocks, branch operating pressure, and controlled data-quality degradation.



A macroeconomic or local event may influence several downstream systems, but it does not deterministically assign outcomes to individual entities.



Branch Network



BTYT contains a structurally defined network of 37 branches and agencies across Uruguay.



Branches differ by branch type, size, geography, administrative parent, opening history, strategic importance, and structural closure risk.



Branch closures are stochastic rather than hard-coded. The annual latent branch-state panel preserves every branch across every observation year, including years after closure, so downstream historical relationships remain valid.



Banking Network



BTYT operates inside a synthetic financial system containing BTYT itself, domestic banks operating in Uruguay, selected international banking counterparties, and electronic-money institutions.



Some institution names correspond to real financial institutions to create a recognizable structural banking environment. All simulated market weights, financial values, transaction relationships, behavioral parameters, shocks, and bank trajectories are synthetic and must not be interpreted as real-world bank data.



Transactions



The transaction engine supports transfers, debit purchases, service payments, cash operations, loan payments, interest credits, and loan disbursements.



It also models digital adoption, channel migration, cash usage, failed transactions, internal-transfer pairing, counterparty institutions, physical-branch usage when applicable, and account-balance reconciliation.



Large production worlds may generate tens of millions of transaction rows, so generated data is intentionally excluded from normal Git history.



Loans and Credit Performance



The lending system contains retail and business credit products and a monthly loan snapshot tracking outstanding balance, current interest rate, scheduled and actual payment, days past due, delinquency state, arrears, restructuring, default, write-off, prepayment, maturity, and open exposures.



Branch and Bank Performance



BTYT includes a dedicated monthly profitability layer.



branch\_monthly\_performance



Grain: one branch per month.



37 branches × 72 months = 2,664 rows



bank\_monthly\_performance



Grain: one consolidated BTYT observation per month.



72 months = 72 rows



The consolidated bank table must reconcile with the aggregation of branch-level performance.



Analytical KPIs



Most BI ratios are deliberately not precomputed by the Python generators. They are intended to be derived in SQL and/or DAX.



Examples include Cost-to-Income Ratio, Net Interest Margin, Revenue per Customer, Cost per Transaction, Branch Margin, Credit Loss Ratio, Deposit Growth, Loan Growth, Digital Channel Share, Branch Profitability, Regional Profitability, Product Profitability, and Customer Segment Performance.



Validation and Auditing



Successful script execution is not considered sufficient evidence of correctness.



BTYT includes generator-level and integrated validations covering referential integrity, temporal integrity, lifecycle constraints, loan-snapshot continuity, transaction and balance reconciliation, internal-transfer pairing, counterparty validation, branch-state completeness, branch-to-bank performance reconciliation, accounting identities, and operational-export integrity.



The final pipeline stage performs an integrated cross-system audit.



Validations must never be weakened merely to force a PASS.



Synthetic Truth vs. Operational Representation



BTYT separates internally coherent synthetic truth from a controlled operational representation that can introduce realistic data-quality degradation without corrupting protected economic and relational truths.



Manifest and Dataset Fingerprint



A completed world can generate a manifest containing canonical and operational file inventories, provenance files, row counts, file sizes, hashes, pipeline status, audit status, and a dataset fingerprint.



The fingerprint provides a compact reproducibility identifier for a frozen BTYT world.



Repository Structure



btyt-banking-analytics/

│

├── config/

│   ├── active\_world.json

│   └── world\_config.json

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

│   ├── generate\_btyt.py

│   └── generate\_manifest.py

│

├── world\_builder/

│   └── app.py

│

├── docs/

│   ├── architecture/

│   └── data\_dictionary/

│

└── README.md



Reference Assets



Small static business/reference dimensions are version-controlled separately from generated worlds.



Canonical reference assets currently include:



resources/reference/products.csv



resources/reference/campaigns/

├── campaigns.csv

├── campaign\_channels.csv

└── campaign\_geography.csv



The World Builder materializes these reference files into new isolated worlds before generation.



Reproducibility



BTYT is designed so that a world is determined by its identity and configuration rather than by execution order or chunk size.



The architecture centralizes world configuration, world seed, observation period, population specification, and output routing, while individual generators retain dedicated RNG namespaces and streams for independent stochastic mechanisms.



Large Generated Files



Large generated datasets are intentionally excluded from Git where appropriate.



The repository is designed around:



model code

&#x20;   +

reference assets

&#x20;   +

world configuration

&#x20;   ↓

reproducible generated dataset



rather than storing every production output directly in version control.



SQL and Data Model



The next analytical phase will construct the relational model step by step in SQL.



For each table, the project will explicitly document:



primary key;



foreign keys;



referenced tables;



grain;



cardinality;



temporal keys;



validated join paths.



The final SQL Entity-Relationship Diagram will be derived from the implemented relational model rather than inferred visually from the Python generators.



Technology Stack



Implemented



Python



Pandas



NumPy



PyArrow / Parquet



Git



GitHub



CustomTkinter



deterministic RNG architecture



cross-system auditing



Next Analytical Stage



SQL



local relational database



Power BI



Power Query



DAX



Later Stages



Tableau



Apache Superset



scikit-learn



credit-risk modeling



machine learning



model explainability



MLflow



local scoring service



Docker / Docker Compose



Technologies are added to the implemented stack only when their corresponding project stage is actually completed.



Main Analytical Question — Part I



How is BTYT performing, and where are the main opportunities and risks across its loan portfolio, deposits, products, customer segments, branches, channels, and banking relationships?



Part I will answer this through SQL analytical views, a validated relational model, banking KPIs, branch-performance analysis, customer and product analysis, transaction and channel analysis, lending and delinquency analysis, geographic analysis, and business-intelligence dashboards.



Part II — Credit Risk Analytics



Part II will reuse the same frozen BTYT universe for SQL-based feature extraction, exploratory risk analysis, feature engineering, statistical modeling, machine learning, model evaluation, and explainability.



No separate disconnected dataset will be created for the credit-risk stage.



Disclaimer



BTYT is a fictional bank created exclusively for educational and portfolio purposes.



All customers, accounts, cards, loans, transactions, balances, branch behavior, market behavior, banking relationships, financial values, campaign outcomes, and credit events represented in the project are synthetic.



The project contains no real customer data, confidential banking information, or actual bank transaction records.



Names of real financial institutions may appear only as structural references within the simulated banking environment. Synthetic metrics associated with those institutions must not be interpreted as actual reported financial results or observed market behavior.



Author



Santiago Castillo Marsicano



Economics \& Sociology

Data Analytics | Business Intelligence

