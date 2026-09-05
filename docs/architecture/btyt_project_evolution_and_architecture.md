# BTYT Banking Analytics --- Project Evolution and Technical Architecture

**Project:** Banco de Treinta y Tres (BTYT) Banking Analytics\
**Document type:** Project evolution, architecture decisions, and
technical roadmap\
**Status:** Active architecture reference\
**Current phase:** Pre-canonical-generation refactor\
**Last updated:** 2026-09-03

------------------------------------------------------------------------

## 1. Purpose of this document

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

1.  Where did BTYT start?
2.  What has already been built and learned?
3.  Why is the current architectural refactor necessary?
4.  What is the target architecture for Part I, Part II, and the final
    local MLOps layer?

This document should be treated as a governing architectural reference
during the refactor.

------------------------------------------------------------------------

## 2. Project vision

BTYT --- Banco de Treinta y Tres --- is a fictional Uruguayan bank
created as the analytical universe for a portfolio project combining
banking, economics, data engineering, business intelligence, statistical
modeling, and machine learning.

The project is deliberately divided into two principal analytical parts
and a final technical closure.

### Part I --- Data, BI, and Banking Performance

Part I constructs the synthetic banking universe and develops the
analytical infrastructure required to study customers, accounts,
branches, cards, loans, transactions, balances, campaigns, external
shocks, bank and market dynamics, branch performance, operational data
quality, and business-performance indicators.

### Part II --- Credit Scoring and Risk

Part II will reuse the frozen banking universe to develop a credit-risk
analytical dataset and modeling workflow, including feature engineering,
credit-risk analysis, model training, comparison, validation, scoring,
experiment tracking, and model versioning.

### Technical closure --- Local, limited MLOps

The final technical layer will demonstrate how the analytical components
can operate together in a reproducible local environment using
PostgreSQL, Apache Superset, MLflow, a scoring service, Docker, and
Docker Compose.

The objective is not to reproduce enterprise infrastructure.

------------------------------------------------------------------------

## 3. The original BTYT approach

BTYT began as a collection of Python generators designed to
progressively construct the fictional bank.

The early architecture relied heavily on independent Python scripts, CSV
outputs, generator-specific configuration, seeds defined inside
individual scripts, hardcoded paths, development and smoke-test
switches, directories such as `raw/`, `processed/`, and later `master/`,
and manual execution order.

This approach was appropriate for exploration because each component
could be designed, inspected, calibrated, and audited independently.

As the number of systems increased, however, the scripts stopped being
truly independent. The project had effectively become a dependency graph
even though the repository architecture did not yet explicitly represent
one.

------------------------------------------------------------------------

## 4. Progressive construction of the synthetic banking universe

BTYT was built progressively rather than as one monolithic generator.

The principal systems developed include:

1.  branches and geographic structure;
2.  domestic and foreign banks;
3.  bank market dynamics;
4.  customers;
5.  accounts;
6.  cards;
7.  loans;
8.  loan lifecycle and monthly snapshots;
9.  external shocks;
10. transactions;
11. account balances;
12. campaigns and campaign exposures;
13. branch performance;
14. bank performance;
15. operational data reliability.

This progressive development made it possible to audit each subsystem
before integrating it with the rest of the world.

------------------------------------------------------------------------

## 5. Evolution of the statistical model

BTYT moved away from simple deterministic assignment toward a world in
which common conditions influence probabilities while individual
outcomes remain stochastic.

> **BTYT models causes as probabilistic shifts in behavior, not
> deterministic assignments of outcomes. Shared causal conditions may
> influence multiple processes, but downstream realizations use
> independent stochastic streams.**

A macroeconomic or geographic shock may simultaneously increase default
risk, reduce activity, alter branch performance, or affect transaction
behavior. It does not directly assign a customer to default or force
another downstream event.

The project progressively introduced stochastic branch behavior, dynamic
banking-market shares, longitudinal credit lifecycle information, shared
external shocks, economically reconciled transaction behavior, and
probabilistic campaign response.

------------------------------------------------------------------------

## 6. Reproducibility and RNG architecture

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

> **Chunk size must not determine the realized synthetic world.**

Changing a technical parameter such as `chunk_size` must not silently
create a statistically different BTYT universe when the world
configuration and seed are unchanged.

------------------------------------------------------------------------

## 7. Auditing and stabilization

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

> **Validations must never be weakened merely to force a PASS.**

------------------------------------------------------------------------

## 8. Operational Data Reliability Layer

After establishing a coherent synthetic truth, BTYT introduced a second
conceptual layer: the operational representation of that truth.

BTYT therefore distinguishes between **synthetic truth** and
**operational representation**.

> **Operational incidents change the probability of data-quality
> degradation; they do not deterministically assign errors.**

The reliability layer supports `clean` and `imperfect` modes, with
intensity levels such as `light`, `realistic`, and `stress`. The
canonical operational target is `imperfect` / `realistic`.

Incident families include branch-system degradation, digital telemetry
degradation, legacy-system migration, manual backfill, CRM ingestion
degradation, and positive reliability upgrades.

Core economic and relational truths remain protected, including
transaction identity, account ownership, transaction amount and
direction, status, balances, loan principal, and core customer/account
relationships.

------------------------------------------------------------------------

## 9. Why the original architecture became insufficient

The original architecture successfully produced a complex synthetic
banking universe, but increasing scale exposed structural problems:

-   distributed customer counts and observation periods;
-   fragmented seeds;
-   hardcoded and historical paths;
-   historical `raw/`, `processed/`, and `master/` concepts;
-   mixed generated, interim, audit, smoke, and operational outputs;
-   CSV scalability limits;
-   limited support for resumable long-running executions;
-   accumulation of test datasets.

These limitations motivate the current architectural refactor.

------------------------------------------------------------------------

## 10. Current refactor

The current phase reorganizes BTYT before the definitive large-scale
generation.

The objective is not to redesign the statistical universe unnecessarily.
It is to create a cleaner execution architecture around the model that
has already been built and audited.

> **Optimize without changing statistical behavior.**

If an optimization changes random draw ordering, effective
distributions, calibrated behavior, or economic relationships, it must
be treated as a model change rather than a transparent performance
optimization.

------------------------------------------------------------------------

## 11. Central world configuration

BTYT is introducing:

`config/world_config.json`

> **JSON says what world we want. Python knows how to build it.**

World-level configuration includes the world name, customer population,
observation period, execution mode, smoke-test population, operational
reliability settings, and eventually the canonical world seed
architecture.

Internal model equations, probability distributions, calibrated
parameters, AR dynamics, and specialized RNG streams remain in Python.

------------------------------------------------------------------------

## 12. Core Python infrastructure

Shared infrastructure is centralized under `scripts/core/`.

Initial components:

-   `paths.py` --- repository locations;
-   `config.py` --- loading and validation of external world
    configuration;
-   `world.py` --- typed canonical world configuration;
-   `rng.py` --- shared reproducible RNG infrastructure where
    appropriate.

Shared RNG infrastructure will not be used to blindly replace existing
generator implementations. RNG migration must preserve reproducibility
and statistical behavior.

------------------------------------------------------------------------

## 13. Repository architecture

``` text
btyt-banking-analytics/
├── config/
│   └── world_config.json
├── data/
│   ├── generated/
│   │   ├── core/
│   │   ├── credit/
│   │   ├── transactions/
│   │   ├── campaigns/
│   │   └── performance/
│   ├── interim/
│   │   ├── world/
│   │   ├── transactions/
│   │   ├── credit/
│   │   └── audits/
│   └── operational/
│       ├── core/
│       ├── transactions/
│       ├── credit/
│       └── campaigns/
├── docs/
│   ├── data_dictionary/
│   ├── architecture/
│   └── methodology/
├── database/
├── scripts/
│   ├── core/
│   ├── generators/
│   ├── audits/
│   ├── diagnostics/
│   └── validation/
├── README.md
└── .gitignore
```

The historical `data/master/` layer disappears. Data dictionaries belong
under `docs/data_dictionary/`, conceptual documentation under
`docs/architecture/` and `docs/methodology/`, and `database/` is
reserved for database/SQL artifacts.

------------------------------------------------------------------------

## 14. Generator dependency graph

The principal generation order is:

``` text
branches
→ banks
→ customers
→ accounts
→ cards
→ loans
→ loan monthly snapshot
→ external shocks
→ transactions
→ campaigns
→ performance
→ operational exports
```

A future top-level orchestrator, expected to be
`scripts/generate_btyt.py`, will make these dependencies explicit.

------------------------------------------------------------------------

## 15. Selective performance optimization

Not every generator requires the same engineering strategy.

Small dimensional generators such as branches or banks should prioritize
clarity, reproducibility, validation, and maintainability.

Large fact or longitudinal generators may justify vectorization, chunk
processing, incremental writes, Parquet, partitioning, checkpoints, and
memory profiling.

Performance engineering will therefore be selective rather than
mechanical.

------------------------------------------------------------------------

## 16. Vectorization

Where safe, vectorized operations should replace avoidable Python-level
loops.

Vectorization is acceptable when it preserves draw semantics, model
equations, ordering requirements, validation behavior, and output
meaning.

If vectorization changes RNG consumption or realization semantics, it is
not considered a transparent optimization.

------------------------------------------------------------------------

## 17. Chunk processing

Large datasets should be generated in bounded chunks where this
materially improves memory control.

Likely candidates include customers at large scale, accounts where
appropriate, cards, loans, monthly snapshots, transactions, balances,
and large customer-month state tables.

> **The same world configuration and seed must produce the same
> synthetic world independently of chunk size.**

------------------------------------------------------------------------

## 18. Parquet strategy

Parquet will become the preferred working format for large generated and
intermediate datasets where it provides a material engineering benefit.

CSV remains useful for small dimensional tables, human inspection,
compatibility, selected BI deliverables, and cases where simplicity
outweighs performance concerns.

Transactions are a strong candidate for partitioned Parquet,
potentially:

``` text
transactions/
├── year=2021/
├── year=2022/
├── year=2023/
├── year=2024/
├── year=2025/
└── year=2026/
```

Year/month partitioning may be considered if benchmarks justify it. The
exact partition strategy is intentionally not frozen yet.

------------------------------------------------------------------------

## 19. Checkpoints and resumable generation

Large canonical runs should support controlled recovery from
interruptions.

Checkpoint-compatible generators should record what has completed, what
remains, which configuration and seed produced the partial output, and
whether the checkpoint is compatible with the current run.

A resumed execution must not silently combine incompatible
configurations or code versions.

------------------------------------------------------------------------

## 20. Run lifecycle: candidate, current, frozen

BTYT will use:

``` text
candidate/
current/
frozen/
```

`candidate/` is the execution currently being generated or evaluated.

`current/` is the latest approved development execution.

`frozen/` is the definitive protected BTYT world.

> **Frozen data is promoted, never generated directly.**

Normal generators must never write directly into `frozen/`.

------------------------------------------------------------------------

## 21. Promotion and disk discipline

The lifecycle must avoid unnecessary duplication.

During development:

``` text
candidate + current
```

When a candidate passes the required validations:

``` text
candidate → current
```

At definitive freeze:

``` text
current → frozen
```

The system should not retain three complete large worlds merely because
three lifecycle names exist.

------------------------------------------------------------------------

## 22. Scale ladder

The definitive world will not be generated immediately at maximum scale.

          Population Primary purpose
  ------------------ --------------------------------------
               1,000 Functional smoke test
               5,000 Integration test
              10,000 Regression and behavioral comparison
              50,000 Serious performance and memory test
             100,000 Final rehearsal
    100,000--120,000 Definitive canonical world

The exact final population within 100,000--120,000 will be chosen after
the 100,000-customer rehearsal.

------------------------------------------------------------------------

## 23. Statistical stability across scale

Every important scale evaluates two dimensions.

### Engineering stability

-   execution time;
-   memory;
-   throughput;
-   output size;
-   checkpoint behavior;
-   I/O performance.

### Statistical stability

-   customer distributions;
-   account distributions;
-   loan distributions;
-   default behavior;
-   transaction behavior;
-   bank shares;
-   branch behavior;
-   campaign behavior;
-   external-shock effects;
-   relevant validation metrics.

> **Scale tests validate both engineering performance and statistical
> stability.**

------------------------------------------------------------------------

## 24. Run manifest and execution observability

Every meaningful generation should create a run manifest recording at
minimum:

``` text
run_id
world_name
world_seed
customer_count
observation_start
observation_end
execution_mode
git_commit
generator_versions
config_hash
started_at
completed_at
elapsed_seconds
peak_memory_mb
row_counts
rows_per_second
output_sizes
chunk_size
checkpoint_status
audit_status
audit_failures
promotion_status
```

The configuration hash identifies the exact world specification. The Git
commit connects data to source code. Generator versions identify
implementations. Audit state records whether a completed run is actually
valid.

------------------------------------------------------------------------

## 25. Benchmarking before the definitive world

Approximately 115 GB of free local disk space is available in the
current development environment.

Before generating the definitive 100,000--120,000-customer world, the
50,000 and 100,000-customer runs will be used to project total execution
time, transaction volume, row count, Parquet size, temporary disk
requirements, peak memory, PostgreSQL loading requirements, and audit
duration.

The definitive population will be selected only after these measurements
are available.

------------------------------------------------------------------------

## 26. Why large-scale storage matters

A previous 20,000-customer operational generation produced approximately
6.96 million transaction rows.

This demonstrated that the final 100,000--120,000-customer world is an
engineering problem as well as a statistical one and motivated the
transition toward chunked generation, incremental output, Parquet,
resumable execution, and explicit run telemetry.

------------------------------------------------------------------------

## 27. Canonical generation process

``` text
world_config.json
        ↓
shared core infrastructure
        ↓
dependency-aware generators
        ↓
candidate world
        ↓
generator validations
        ↓
cross-system audits
        ↓
statistical checks
        ↓
performance report
        ↓
promotion
        ↓
current
        ↓
final approval
        ↓
frozen
```

The definitive world should be generated from zero under the final
architecture rather than assembled from incompatible historical outputs.

------------------------------------------------------------------------

## 28. PostgreSQL and the SQL analytical layer

Docker is deliberately postponed until the synthetic dataset has been
frozen.

The sequence is:

1.  generate the definitive world;
2.  audit it;
3.  freeze it;
4.  load the frozen data into PostgreSQL;
5.  develop the SQL analytical layer;
6.  validate analytical queries and database structure.

PostgreSQL becomes the analytical database layer between generated data
and downstream BI tooling.

------------------------------------------------------------------------

## 29. First use of Docker

Docker will be introduced after the data is frozen, PostgreSQL is
loaded, and the initial SQL layer exists.

Its first practical use case will be to support Apache Superset and its
connection to PostgreSQL.

Docker is being introduced because it solves a concrete reproducibility
and environment-management problem, not because containerization is
itself a project objective.

------------------------------------------------------------------------

## 30. Apache Superset and BI delivery

The intended Part I technical flow is:

``` text
Python generators
        ↓
frozen BTYT world
        ↓
PostgreSQL
        ↓
SQL analytical layer
        ↓
Docker
        ↓
Apache Superset
        ↓
BI and banking-performance analysis
```

------------------------------------------------------------------------

## 31. Part II --- Credit scoring and risk

Part II begins from the frozen BTYT universe rather than generating an
unrelated credit dataset.

``` text
frozen BTYT world
        ↓
credit-risk analytical dataset
        ↓
feature engineering
        ↓
training / validation
        ↓
model development
        ↓
model comparison
        ↓
risk evaluation
        ↓
scoring
```

------------------------------------------------------------------------

## 32. MLflow

MLflow will be introduced during Part II to register experiments, model
parameters, evaluation metrics, useful artifacts, and model versions.

The objective is reproducible and inspectable model development rather
than enterprise MLOps.

------------------------------------------------------------------------

## 33. Final local MLOps architecture

After the Part II model workflow is established:

``` text
Docker Compose
├── PostgreSQL
├── Apache Superset
├── MLflow
└── scoring service
```

The scoring service will expose the selected model for prediction in a
controlled local environment.

This is the technical closure of BTYT, not the beginning of a separate
infrastructure project.

------------------------------------------------------------------------

## 34. Explicitly out of scope

The following are deliberately excluded:

-   Azure;
-   cloud infrastructure solely for demonstration;
-   Kubernetes;
-   RAG;
-   LLM-based analytical features;
-   conversational agents;
-   enterprise MLOps platforms;
-   unnecessary distributed infrastructure.

Their exclusion is intentional. BTYT prioritizes depth and integration
across data generation, SQL, BI, statistical modeling, machine learning,
reproducibility, and local deployment.

------------------------------------------------------------------------

## 35. Frozen architecture principles

### Statistical modeling

> **BTYT models causes as probabilistic shifts in behavior, not
> deterministic assignments of outcomes.**

> **Shared causal conditions may influence multiple processes, but
> downstream realizations use independent stochastic streams.**

### Validation

> **Validations are never weakened merely to obtain a PASS.**

### Optimization

> **Optimize without changing statistical behavior.**

### Chunking

> **Chunk size must not determine the realized synthetic world.**

### Configuration

> **JSON says what world we want. Python knows how to build it.**

### Dataset lifecycle

> **Frozen data is promoted, never generated directly.**

### Scaling

> **Scale tests validate both engineering performance and statistical
> stability.**

### Complexity

> **Introduce infrastructure only when it solves a concrete project
> requirement.**

------------------------------------------------------------------------

## 36. Current project state

The synthetic banking universe already exists and has been validated at
meaningful development scale.

BTYT has already demonstrated integrated banking entities, longitudinal
credit behavior, millions of transactions, balance reconciliation, bank
and branch dynamics, external shocks, campaigns, operational data
degradation, and cross-system auditing.

The project is now reorganizing the architecture before generating the
definitive large-scale world.

Completed or underway in the refactor:

-   `config/world_config.json`;
-   `scripts/core/config.py`;
-   `scripts/core/world.py`;
-   `scripts/core/rng.py`;
-   centralized path infrastructure;
-   domain-based `generated/` organization;
-   domain-based `interim/` organization;
-   documentation reorganization;
-   removal of the historical `master/` concept;
-   migration away from historical `raw/` and `processed/` paths;
-   preparation for generator-by-generator migration.

------------------------------------------------------------------------

## 37. Immediate refactor sequence

The generator migration order is:

``` text
branches
→ banks
→ customers
→ accounts
→ cards
→ loans
→ loan monthly snapshot
→ external shocks
→ transactions
→ campaigns
→ performance
→ operational exports
```

Each generator will be reviewed through four lenses:

1.  paths and repository architecture;
2.  world configuration;
3.  RNG and reproducibility;
4.  performance and scalability.

Small generators should remain simple. Large generators should receive
the engineering required to make the final world feasible.

------------------------------------------------------------------------

## 38. Remaining work before canonical generation

Before the definitive world is generated, BTYT still needs:

-   generator path migration;
-   removal of obsolete directory references;
-   world-level seed architecture;
-   RNG compatibility review;
-   generator organization under `scripts/generators/`;
-   audit and diagnostic organization;
-   dependency-aware orchestration;
-   run manifest implementation;
-   checkpoint architecture for large generators;
-   Parquet strategy for large tables;
-   benchmark instrumentation;
-   candidate/current/frozen lifecycle implementation;
-   scale-ladder execution;
-   final cross-system audit.

Only after these stages should the definitive world be promoted to
`frozen/`.

------------------------------------------------------------------------

## 39. Roadmap

``` text
PHASE A — Architecture refactor
    ↓
Central config
Central paths
RNG architecture
Generator migration
Repository cleanup

PHASE B — Scalable generation
    ↓
Selective vectorization
Chunks
Parquet
Checkpoints
Run manifest
Orchestrator

PHASE C — Scale ladder
    ↓
1k
5k
10k
50k
100k
100k–120k final

PHASE D — Freeze
    ↓
Full audit
Statistical validation
Resource report
Promotion to frozen

PHASE E — Part I analytical infrastructure
    ↓
PostgreSQL
SQL layer
Docker
Superset
BI / performance deliverables

PHASE F — Part II
    ↓
Credit-risk dataset
Feature engineering
Model development
Model validation
MLflow
Scoring

PHASE G — Technical closure
    ↓
Docker Compose
PostgreSQL
Superset
MLflow
Scoring service
```

------------------------------------------------------------------------

## 40. Final perspective

BTYT did not begin as a production-style synthetic-data platform.

It began by solving the harder conceptual problem first: constructing a
believable fictional bank whose customers, accounts, credit products,
transactions, branches, campaigns, competitors, shocks, and operational
imperfections could coexist coherently.

As that universe became richer, its engineering requirements changed.

``` text
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
architecture refactor
        ↓
reproducible scalable pipeline
        ↓
definitive frozen world
        ↓
SQL and BI
        ↓
credit-risk ML
        ↓
local MLOps closure
```

The current refactor is not a restart of BTYT.

It is the engineering consolidation of everything already learned and
built.

The objective is to preserve the statistical and economic richness of
the existing world while making its generation reproducible, scalable,
observable, resumable, and suitable for the final analytical stages of
the project.
