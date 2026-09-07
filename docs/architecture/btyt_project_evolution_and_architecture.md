BTYT Banking Analytics --- Project Evolution and Technical Architecture

Project: Banco de Treinta y Tres (BTYT) Banking Analytics
Document type: Project evolution, architecture decisions, and
technical roadmap
Status: Active architecture reference
Current phase: Canonical world generation and validation
Last updated: 2026-09-07

1. Purpose of this document

This document records the technical evolution of the BTYT Banking
Analytics project from its original conception to its current
architecture and planned final state.

It is intentionally broader than a description of the current repository
structure. BTYT has evolved progressively: the first objective was to
construct a functional and internally coherent synthetic banking
universe; later development introduced richer stochastic behavior,
cross-system consistency, data-quality degradation, auditing, and
increasingly demanding execution volumes. Those stages exposed
architectural limitations that now motivate a controlled refactor toward
a reproducible, scalable, auditable data-generation pipeline.

The document therefore answers four questions:

Where did BTYT start?

What has already been built and learned?

Why is the current architectural refactor necessary?

What is the target architecture for Part I, Part II, and the final
local MLOps layer?

This document should be treated as a governing architectural reference
during the refactor.

2. Project vision

BTYT --- Banco de Treinta y Tres --- is a fictional Uruguayan bank
created as the analytical universe for a portfolio project combining
banking, economics, data engineering, business intelligence, statistical
modeling, and machine learning.

The project is deliberately divided into two principal analytical parts
and a final technical closure.

Part I --- Data, BI, and Banking Performance

Part I constructs the synthetic banking universe and develops the
analytical infrastructure required to study customers, accounts,
branches, cards, loans, transactions, balances, campaigns, external
shocks, bank and market dynamics, branch performance, operational data
quality, and business-performance indicators.

Part II --- Credit Scoring and Risk

Part II will reuse the frozen banking universe to develop a credit-risk
analytical dataset and modeling workflow, including feature engineering,
credit-risk analysis, model training, comparison, validation, scoring,
experiment tracking, and model versioning.

Technical closure --- Local, limited MLOps

The final technical layer will demonstrate how the analytical components
can operate together in a reproducible local environment using
PostgreSQL, Apache Superset, MLflow, a scoring service, Docker, and
Docker Compose.

The objective is not to reproduce enterprise infrastructure.

3. The original BTYT approach

BTYT began as a collection of Python generators designed to
progressively construct the fictional bank.

The early architecture relied heavily on independent Python scripts, CSV
outputs, generator-specific configuration, seeds defined inside
individual scripts, hardcoded paths, development and smoke-test
switches, directories such as raw/, processed/, and later master/,
and manual execution order.

This approach was appropriate for exploration because each component
could be designed, inspected, calibrated, and audited independently.

As the number of systems increased, however, the scripts stopped being
truly independent. The project had effectively become a dependency graph
even though the repository architecture did not yet explicitly represent
one.

4. Progressive construction of the synthetic banking universe

BTYT was built progressively rather than as one monolithic generator.

The principal systems developed include:

branches and geographic structure;

domestic and foreign banks;

bank market dynamics;

customers;

accounts;

cards;

loans;

loan lifecycle and monthly snapshots;

external shocks;

transactions;

account balances;

campaigns and campaign exposures;

branch performance;

bank performance;

operational data reliability.

This progressive development made it possible to audit each subsystem
before integrating it with the rest of the world.

5. Evolution of the statistical model

BTYT moved away from simple deterministic assignment toward a world in
which common conditions influence probabilities while individual
outcomes remain stochastic.

BTYT models causes as probabilistic shifts in behavior, not
deterministic assignments of outcomes. Shared causal conditions may
influence multiple processes, but downstream realizations use
independent stochastic streams.

A macroeconomic or geographic shock may simultaneously increase default
risk, reduce activity, alter branch performance, or affect transaction
behavior. It does not directly assign a customer to default or force
another downstream event.

The project progressively introduced stochastic branch behavior, dynamic
banking-market shares, longitudinal credit lifecycle information, shared
external shocks, economically reconciled transaction behavior, and
probabilistic campaign response.

6. Reproducibility and RNG architecture

As BTYT grew, reproducibility became increasingly important.

Several generators developed dedicated random-number streams so that
conceptually different stochastic processes would not depend on a single
undifferentiated sequence.

The current refactor will centralize world-level seed configuration
while preserving model-specific streams where they belong.

Internal statistical stream definitions do not necessarily belong in the
external world configuration. The configuration should specify the
world; the model code should retain responsibility for how that world is
generated.

A further requirement introduced for scalable execution is:

Chunk size must not determine the realized synthetic world.

Changing a technical parameter such as chunk_size must not silently
create a statistically different BTYT universe when the world
configuration and seed are unchanged.

7. Auditing and stabilization

BTYT did not treat successful execution as sufficient evidence of
correctness.

The project progressively introduced generator-level validations,
referential-integrity checks, temporal-integrity checks, economic
validations, Monte Carlo audits, distribution diagnostics, boundary
analysis, transaction reconciliation, balance reconciliation, and
cross-system validation.

The integrated cross-system audit eventually verified core banking,
transactions, credit lifecycle, balances, branch performance, bank
performance, external shocks, campaign behavior, referential integrity,
temporal integrity, and reproducibility contracts.

The clean integrated world reached a full cross-system validation PASS.

Validations must never be weakened merely to force a PASS.

8. Operational Data Reliability Layer

After establishing a coherent synthetic truth, BTYT introduced a second
conceptual layer: the operational representation of that truth.

BTYT therefore distinguishes between synthetic truth and
operational representation.

Operational incidents change the probability of data-quality
degradation; they do not deterministically assign errors.

The reliability layer supports clean and imperfect modes, with
intensity levels such as light, realistic, and stress. The
canonical operational target is imperfect / realistic.

Incident families include branch-system degradation, digital telemetry
degradation, legacy-system migration, manual backfill, CRM ingestion
degradation, and positive reliability upgrades.

Core economic and relational truths remain protected, including
transaction identity, account ownership, transaction amount and
direction, status, balances, loan principal, and core customer/account
relationships.

9. Why the original architecture became insufficient

The original architecture successfully produced a complex synthetic
banking universe, but increasing scale exposed structural problems:

distributed customer counts and observation periods;

fragmented seeds;

hardcoded and historical paths;

historical raw/, processed/, and master/ concepts;

mixed generated, interim, audit, smoke, and operational outputs;

CSV scalability limits;

limited support for resumable long-running executions;

accumulation of test datasets.

These limitations motivate the current architectural refactor.

10. Architecture consolidation completed

The architectural refactor that was previously planned is now substantially
implemented.

The objective remained unchanged throughout the migration:

Optimize and reorganize without unnecessarily changing statistical
behavior.

The project now has a centralized world configuration, typed world loading,
shared path infrastructure, deterministic world-level identity, active-world
routing, a dependency-aware orchestrator, per-world storage, cross-system
auditing, manifest generation, and a graphical World Builder.

The refactor therefore moved from a planned architecture to an operational
generation platform.

11. Canonical world configuration

BTYT uses:

config/world_config.json

as the canonical engine configuration.

The governing principle remains:

JSON says what world we want. Python knows how to build it.

The configuration contains nested world-level sections for:

world name and seed;

customer population or population range;

observation period;

execution mode and smoke-test population;

operational data-reliability mode and intensity.

Internal equations, calibrated distributions, AR dynamics, generator-specific
parameters, and specialized RNG streams remain in Python.

The canonical schema is validated by scripts/core/config.py and loaded into a
typed WorldConfig object by scripts/core/world.py.

12. World identity and deterministic seeds

World identity is now explicit.

A visible world name and variant define a deterministic seed through a stable
SHA-256-based derivation rather than Python's process-dependent hash().

Conceptually:

world name + variant
        ↓
normalized identity
        ↓
SHA-256
        ↓
32-bit world seed

This provides two important guarantees:

the same world identity reproduces the same seed;

a different identity creates a genuinely different stochastic universe.

The seed is an implementation detail and does not need to dominate the normal
World Builder interface.

13. Active-world architecture

BTYT now distinguishes between the active engine configuration and persistent
world definitions.

The active pointer is:

config/active_world.json

Persistent worlds live under:

worlds/
├── registry.json
└── <world-slug>/
    └── <variant>/
        ├── world.json
        ├── metadata.json
        ├── data/
        │   ├── interim/
        │   ├── generated/
        │   └── operational/
        ├── database/
        ├── audit/
        └── manifests/

scripts/core/paths.py resolves the active world and routes generation into
that world's own directories.

This prevents one synthetic universe from silently overwriting another.

Legacy global data paths remain only for compatibility during repository
cleanup.

14. Repository architecture

The current target repository structure is:

btyt-banking-analytics/
├── config/
│   ├── world_config.json
│   └── active_world.json
├── worlds/
│   ├── registry.json
│   └── <world>/
│       └── <variant>/
│           ├── world.json
│           ├── metadata.json
│           ├── data/
│           │   ├── interim/
│           │   ├── generated/
│           │   └── operational/
│           ├── database/
│           ├── audit/
│           └── manifests/
├── world_builder/
│   ├── __init__.py
│   └── app.py
├── scripts/
│   ├── core/
│   ├── generators/
│   ├── audits/
│   ├── diagnostics/
│   ├── validation/
│   ├── generate_btyt.py
│   └── generate_manifest.py
├── docs/
│   ├── data_dictionary/
│   ├── architecture/
│   └── methodology/
├── data/                 # legacy tracked dataset during cleanup
├── database/             # legacy/global database area during migration
├── README.md
└── .gitignore

Generated world material is reproducible and is excluded from Git where
appropriate. World definitions and metadata can remain versioned so that a
world can be identified and reconstructed without committing very large
datasets.

15. Canonical generation pipeline

The generation order is now explicit and implemented in
scripts/generate_btyt.py.

The canonical orchestrator contains 15 stages:

01 macro
02 banks
03 financial_institutions
04 branches
05 customers
06 accounts
07 cards
08 loans
09 loan_snapshot
10 external_shocks
11 transactions
12 campaigns
13 branch_performance
14 operational_exports
15 cross_system_audit

The orchestrator supports architecture checks, stage listing, bounded stage
ranges, single-stage execution, skipped stages, fail-fast execution, optional
continuation after failure, and run records.

Each stage executes in a fresh subprocess.

16. Orchestrator execution contract

The orchestrator is the canonical command-line execution layer.

It supports workflows such as:

check architecture
        ↓
select stage range
        ↓
execute generators
        ↓
stream output
        ↓
record PASS / FAIL
        ↓
cross-system audit
        ↓
manifest

Production execution requires active-world routing so that outputs cannot
silently fall back to an unrelated global dataset.

Run records are stored per world.

17. World Builder

BTYT now includes a desktop graphical control layer under world_builder/.

The World Builder does not replace the statistical engine. It configures and
launches it.

Its responsibilities include:

world name and variant selection;

deterministic world identity;

fixed or ranged customer population;

observation-period configuration;

operational reliability settings;

pipeline start/end selection;

world registration and activation;

architecture validation;

orchestrator launch;

live subprocess output;

per-stage status;

per-stage progress;

overall pipeline progress;

pause, resume, and stop controls;

optional manifest and final verification;

opening the active world folder.

The governing separation is:

World Builder configures the laws and identity of the universe; the
generators realize its history.

The Builder must not invent stage progress. Exact percentages are derived from
generator telemetry when generators report completed/total units.

18. Process control and progress observability

Long-running generation requires execution visibility.

The World Builder supports:

PASS indicators for completed stages;

per-stage progress bars;

a global progress bar;

live console output;

recursive process suspension and resumption where supported;

controlled process-tree termination.

Generators that emit progress such as:

Processed 500/8,222 accounts

or chunk telemetry such as:

... 5,000/63,205 | row group rows: 5,000

can drive exact stage percentages.

Stages without exact telemetry remain below 100% until the orchestrator reports
a real PASS.

19. Reproducibility and RNG architecture

World-level randomness is centralized while generator-specific streams remain
separated by mechanism.

The project preserves the principle:

Chunk size must not determine the realized synthetic world.

Large generators can use chunked execution for memory and I/O control, but
technical chunk size must not silently alter the statistical realization when
world identity and configuration remain unchanged.

Independent stochastic mechanisms use independent namespaces or streams where
appropriate.

20. Population as a world realization

BTYT supports either:

a fixed customer population; or

a configured population interval.

For ranged populations, scripts/core/world.py resolves the final customer
count deterministically from the world seed using the dedicated
world.population RNG namespace.

This means population can itself be part of the realized world while remaining
fully reproducible.

The final world currently being generated is:

World: BTYT33
World seed: 606597249
Resolved customers: 63,205

This replaces the earlier plan to mechanically impose a 100,000--120,000
customer canonical population.

The final scale is therefore an outcome of the configured world rather than a
portfolio-size target chosen after the fact.

21. Selective performance engineering

Not every generator requires the same optimization strategy.

Small dimensional generators prioritize:

clarity;

validation;

reproducibility;

maintainability.

Large fact and longitudinal generators may use:

vectorization;

bounded chunks;

incremental output;

Parquet;

compression;

partitioning where justified;

execution telemetry.

Performance optimization is accepted only when statistical behavior remains
valid.

22. Parquet and large-table strategy

Parquet is the preferred working format for large generated and intermediate
tables where it materially improves execution or storage.

CSV remains appropriate for:

small dimensions;

human inspection;

selected BI outputs;

interoperability;

cases where simplicity is more valuable than columnar storage.

Large generators can write incrementally in row groups or partitions rather
than accumulating the complete dataset in memory.

23. Auditing and validation

BTYT continues to treat successful execution as insufficient evidence of
correctness.

Validation layers include:

generator-level assertions;

referential-integrity checks;

temporal-integrity checks;

economic reconciliation;

transaction and balance reconciliation;

distribution diagnostics;

stochastic and Monte Carlo audits where appropriate;

cross-system validation.

The governing principle remains:

Validations are never weakened merely to obtain a PASS.

The final pipeline culminates in scripts/audits/audit_cross_system.py.

24. Operational Data Reliability Layer

BTYT preserves the distinction between:

synthetic truth

and

operational representation.

The operational reliability layer supports:

clean;

imperfect.

Imperfect mode supports intensity levels such as:

light;

realistic;

stress.

The canonical target remains imperfect / realistic.

Operational incidents modify probabilities of degradation while protected
financial and relational truths remain intact.

25. Manifest and dataset fingerprint

scripts/generate_manifest.py now operates within the active-world
architecture.

The manifest connects a materialized world to:

world identity;

configuration;

source-code state;

dataset inventory;

validation state;

reproducibility information.

The repository Git root remains the source-code root while dataset inventory
is resolved relative to the active world.

Manifest generation is intended to occur only after the required validation
contract has been satisfied.

26. Git and reproducible-world storage policy

The repository now separates source-controlled world definitions from large
materialized datasets.

Git should preserve:

source code
world_builder/
config/
worlds/registry.json
worlds/<world>/<variant>/world.json
worlds/<world>/<variant>/metadata.json
documentation

Large reproducible world artifacts should normally remain outside Git:

worlds/<world>/<variant>/data/
worlds/<world>/<variant>/database/
worlds/<world>/<variant>/audit/
worlds/<world>/<variant>/manifests/

The design principle is:

Git stores the code and the world's reproducible identity, not every
materialized row of the universe.

Legacy globally tracked datasets remain subject to a final repository cleanup.

27. Current canonical-generation process

The current process is:

World Builder
        ↓
world identity
        ↓
world_config.json
        ↓
active_world.json
        ↓
core config / world / paths / RNG
        ↓
15-stage orchestrator
        ↓
per-world generated + interim data
        ↓
operational representation
        ↓
cross-system audit
        ↓
manifest
        ↓
dataset freeze

The definitive analytical world is generated from zero under the consolidated
architecture rather than assembled from incompatible historical outputs.

28. Dataset lifecycle

The earlier candidate/current/frozen directory proposal has been superseded
by explicit named and versioned world directories.

A world is now identified independently of its lifecycle state.

Lifecycle status belongs in metadata and validation records rather than
requiring three complete physical copies of a large universe.

A world becomes analytically frozen only after:

successful canonical generation;

generator-level validations;

cross-system audit PASS;

manifest generation;

explicit approval to stop modifying the Part I dataset.

29. PostgreSQL and the SQL analytical layer

Docker remains deliberately postponed until the synthetic dataset is frozen.

The intended sequence is:

generate the definitive world;

audit it;

freeze it;

load the frozen data into PostgreSQL;

develop the SQL analytical layer;

validate analytical queries and database structure.

PostgreSQL becomes the analytical database layer between generated data and
downstream BI tooling.

30. Part I BI delivery

The intended Part I analytical flow is:

Python generators
        ↓
frozen BTYT world
        ↓
PostgreSQL
        ↓
SQL analytical layer
        ↓
Power BI / Tableau / Apache Superset
        ↓
banking-performance analysis

The analytical phase is deliberately separated from generation.

Once the dataset is frozen, the project changes roles: it stops designing the
world and begins investigating it.

This preserves the possibility of discovering patterns that were not manually
selected as analytical conclusions during generation.

31. First use of Docker

Docker will be introduced only when it solves a concrete environment problem.

Its first planned use remains the reproducible local analytical stack around
PostgreSQL and Apache Superset.

Containerization is supporting infrastructure, not a project objective by
itself.

32. Part II --- Credit scoring and risk

Part II begins from the frozen Part I universe.

frozen BTYT world
        ↓
credit-risk analytical dataset
        ↓
feature engineering
        ↓
training / validation split
        ↓
model development
        ↓
model comparison
        ↓
risk evaluation
        ↓
scoring

The objective is to build credit-risk modeling on the same longitudinal
banking ecosystem rather than downloading an unrelated external scoring
dataset.

33. MLflow

MLflow remains planned for Part II.

It will be used to track:

experiments;

model parameters;

evaluation metrics;

relevant artifacts;

model versions.

The target is reproducible and inspectable model development rather than
enterprise-scale MLOps.

34. Final local technical architecture

The planned technical closure remains:

Docker Compose
├── PostgreSQL
├── Apache Superset
├── MLflow
└── scoring service

The scoring service will expose the selected model for controlled local
prediction.

This remains the technical closure of BTYT rather than the start of a separate
infrastructure project.

35. Explicitly out of scope

The following remain deliberately outside the project:

Azure;

cloud infrastructure solely for demonstration;

Kubernetes;

RAG;

LLM-based analytical features;

conversational agents;

enterprise MLOps platforms;

unnecessary distributed infrastructure.

BTYT prioritizes depth and integration across synthetic-data generation,
banking and economic modeling, SQL, BI, statistics, machine learning,
reproducibility, and local deployment.

36. Frozen architecture principles

Statistical modeling

BTYT models causes as probabilistic shifts in behavior, not deterministic
assignments of outcomes.

Shared causal conditions may influence multiple processes, but downstream
realizations use independent stochastic streams.

Validation

Validations are never weakened merely to obtain a PASS.

Optimization

Optimize without changing statistical behavior.

Chunking

Chunk size must not determine the realized synthetic world.

Configuration

JSON says what world we want. Python knows how to build it.

World identity

The same world identity must reproduce the same world seed.

World isolation

One world must never silently overwrite another world.

Complexity

Introduce infrastructure only when it solves a concrete project
requirement.

Analysis

Build the mechanisms first; discover the realized history afterward.

37. Current project state --- 2026-09-07

The architecture consolidation is substantially complete.

Implemented:

canonical world_config.json;

active-world pointer;

typed world loading;

centralized path routing;

shared RNG infrastructure;

deterministic world identity;

persistent world registry;

per-world storage;

generator migration into the active-world architecture;

dependency-aware 15-stage orchestrator;

run records;

cross-system audit integration;

per-world manifest generation;

World Builder desktop interface;

stage selection;

live generation logs;

stage PASS indicators;

per-stage and overall progress;

pause / resume / stop controls;

Git rules separating reproducible definitions from large materialized data.

A repository checkpoint containing the reproducible-world architecture and
World Builder was committed and pushed to main on 2026-09-07.

The final BTYT world is currently being generated:

World: BTYT33
Seed: 606597249
Customers: 63,205
Status: canonical generation in progress

The dataset must not be considered frozen until the complete pipeline,
cross-system audit, and manifest finish successfully.

38. Immediate next steps

The immediate sequence is now:

complete BTYT33 generation
        ↓
cross-system audit
        ↓
manifest
        ↓
inspect final dataset statistics
        ↓
general repository cleanup
        ↓
update README and architecture documentation
        ↓
freeze Part I dataset
        ↓
PostgreSQL
        ↓
SQL analysis

Repository cleanup will include review of legacy globally tracked datasets,
obsolete test worlds, temporary diagnostics, and final Git-ignore policy.

No statistical redesign should be introduced merely because the canonical
world produces surprising but valid outcomes.

39. Updated roadmap

PHASE A --- Architecture consolidation                 COMPLETE
    ↓
Central config
Central paths
World identity
RNG architecture
Generator migration
Per-world storage

PHASE B --- Reproducible execution platform            COMPLETE
    ↓
15-stage orchestrator
World Builder
Progress telemetry
Process control
Cross-system audit
Manifest architecture

PHASE C --- Canonical world generation                 IN PROGRESS
    ↓
BTYT33
63,205 customers
15-stage generation
Final audit
Manifest

PHASE D --- Freeze and repository cleanup              NEXT
    ↓
Final statistics
Legacy-data cleanup
Documentation update
README update
Dataset freeze
Release / tag

PHASE E --- Part I analytical infrastructure
    ↓
PostgreSQL
SQL layer
Power BI
Tableau
Docker
Apache Superset
Banking-performance analysis

PHASE F --- Part II
    ↓
Credit-risk analytical dataset
Feature engineering
Model development
Model validation
MLflow
Scoring

PHASE G --- Technical closure
    ↓
Docker Compose
PostgreSQL
Superset
MLflow
Scoring service

40. Final perspective

BTYT did not begin as a synthetic-data platform.

It began as a portfolio project intended to create a believable fictional bank
for business-intelligence analysis.

The project first solved the conceptual problem: constructing customers,
accounts, credit products, transactions, branches, campaigns, competitors,
macroeconomic conditions, shocks, and operational imperfections that could
coexist coherently.

As that universe became richer, its engineering requirements changed.

functional generators
        ↓
richer stochastic modeling
        ↓
system-specific validation
        ↓
cross-system consistency
        ↓
operational data realism
        ↓
scale limitations discovered
        ↓
architecture consolidation
        ↓
deterministic world identity
        ↓
isolated reproducible worlds
        ↓
World Builder
        ↓
15-stage generation pipeline
        ↓
canonical BTYT33 world
        ↓
frozen analytical universe
        ↓
SQL and BI
        ↓
credit-risk ML
        ↓
local MLOps closure

The architectural refactor is no longer merely preparation for future work.

It has produced a reusable execution platform around the statistical and
economic model already developed.

The immediate objective is now to complete and validate BTYT33, freeze the Part
I universe, and change the nature of the project from world construction to
world investigation.

That transition is central to the value of BTYT: the analytical phase should
not merely display conclusions manually embedded during generation. It should
allow SQL, BI, statistical analysis, and later machine learning to discover the
realized consequences of the probabilistic mechanisms that created the world.
