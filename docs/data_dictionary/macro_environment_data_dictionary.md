# BTYT Banking Analytics

# 

# Macro Environment Data Dictionary

# 

# Primary file: macro\_environment.csv

# Canonical path: data/generated/world/macro\_environment.csv

# Generator: scripts/generators/generate\_macro\_environment.py

# Status: Extracted world-level contract; behavior preserved from the banking V4 macro engine

# Project: Banco de Treinta y Tres (BTYT) — Banking Analytics

# 

# 1\. Purpose

# 

# macro\_environment.csv stores the shared annual synthetic macroeconomic and systemic environment of the BTYT world.

# 

# It is a world-level exogenous state. It does not belong conceptually to banks, branches, customers, credit, transactions, or campaigns.

# 

# The same realized annual environment may be consumed by multiple downstream generators.

# 

# Conceptually:

# 

# $$

# M\_t \\rightarrow Bank\_{i,t}=f(M\_t,\\varepsilon^{bank}\_{i,t})

# $$

# 

# $$

# M\_t \\rightarrow Branch\_{r,t}=g(M\_t,\\varepsilon^{branch}\_{r,t})

# $$

# 

# The common state is shared. Downstream realizations remain stochastic and use independent RNG streams.

# 

# This implements the BTYT principle:

# 

# Shared causal conditions may influence multiple processes, but downstream realizations use independent stochastic streams.

# 

# 2\. Ownership and dependency contract

# 

# The canonical dependency is:

# 

# world\_config.json

# &#x20;       ↓

# generate\_macro\_environment.py

# &#x20;       ↓

# macro\_environment.csv

# &#x20;       ├──→ generate\_banks.py

# &#x20;       ├──→ generate\_branches.py

# &#x20;       └──→ other downstream systems when justified

# 

# At full-project level the intended workflow is:

# 

# scripts/generate\_btyt.py

# &#x20;       ↓

# macro environment

# &#x20;       ↓

# downstream generators

# 

# Users should ultimately generate the complete BTYT world through the orchestrator rather than manually coordinating this dependency chain.

# 

# 3\. What this table is not

# 

# The table is not:

# 

# an observed Uruguayan macroeconomic dataset;

# 

# a reconstruction of historical GDP, inflation, FX, or financial-stress series;

# 

# a bank-specific table;

# 

# a deterministic assignment of downstream outcomes;

# 

# a configuration file.

# 

# All values are synthetic latent drivers.

# 

# world\_config.json specifies the desired world. macro\_environment.csv is a stochastic realization inside that world.

# 

# 4\. Grain and key

# 

# Grain: one row per observation year.

# 

# Primary key: year.

# 

# For the current canonical observation period the table contains one row for each year from 2021 through 2026.

# 

# The year range is derived from the centralized world configuration rather than being independently hard-coded as the authoritative observation window.

# 

# 5\. Schema

# 

# Column

# 

# Type

# 

# Nullable

# 

# Description

# 

# year

# 

# integer

# 

# No

# 

# Observation year.

# 

# macro\_growth\_factor

# 

# decimal

# 

# No

# 

# Synthetic economic-cycle factor.

# 

# credit\_cycle\_factor

# 

# decimal

# 

# No

# 

# Synthetic credit-cycle / credit-demand state.

# 

# usd\_pressure\_factor

# 

# decimal

# 

# No

# 

# Synthetic FX/USD pressure state.

# 

# financial\_stress\_factor

# 

# decimal

# 

# No

# 

# Synthetic financial-system stress state.

# 

# digitalization\_factor

# 

# decimal

# 

# No

# 

# Synthetic digitalization / competitive technology pressure.

# 

# cross\_border\_factor

# 

# decimal

# 

# No

# 

# Synthetic international / cross-border activity state.

# 

# systemic\_shock

# 

# decimal

# 

# No

# 

# Signed systemic banking shock realized for the year.

# 

# systemic\_shock\_flag

# 

# boolean

# 

# No

# 

# Whether a material systemic shock occurred.

# 

# world\_seed

# 

# integer

# 

# No

# 

# Seed currently used to reproduce this macro realization.

# 

# 6\. Stochastic process

# 

# The six macro factors are persistent latent annual processes.

# 

# For factor (k):

# 

# $$

# X\_{k,t}=\\phi X\_{k,t-1}+\\varepsilon\_{k,t}

# $$

# 

# with:

# 

# $$

# \\phi=0.55

# $$

# 

# and:

# 

# $$

# \\varepsilon\_{k,t}\\sim N(0,0.35^2)

# $$

# 

# The realized state is clipped to:

# 

# $$

# \-1.50\\le X\_{k,t}\\le 1.50

# $$

# 

# The initial state is drawn from:

# 

# $$

# X\_{k,2021}\\sim N(0,0.20^2)

# $$

# 

# and is subject to the same clipping bounds.

# 

# The six factors are generated separately but from the same deterministic macro RNG stream.

# 

# 7\. Macro factors

# 

# The current factor set is:

# 

# macro\_growth\_factor

# 

# credit\_cycle\_factor

# 

# usd\_pressure\_factor

# 

# financial\_stress\_factor

# 

# digitalization\_factor

# 

# cross\_border\_factor

# 

# These dimensions are intentionally synthetic and interpretable rather than empirical macro series.

# 

# Their downstream effects depend on the consuming model.

# 

# A positive value does not mean that every downstream entity benefits, and a negative value does not mean that every downstream entity deteriorates.

# 

# 8\. Systemic shock process

# 

# Each year after the initial year receives an opportunity for a material systemic shock.

# 

# For years after 2021:

# 

# $$

# I\_t^{shock}\\sim Bernoulli(0.14)

# $$

# 

# For the initial year, 2021:

# 

# $$

# I\_{2021}^{shock}=0

# $$

# 

# If no shock occurs:

# 

# $$

# S\_t=0

# $$

# 

# If a shock occurs, the sign is negatively skewed:

# 

# $$

# P(sign\_t=-1)=0.58

# $$

# 

# $$

# P(sign\_t=+1)=0.42

# $$

# 

# The magnitude is:

# 

# $$

# |S\_t|\\sim Uniform(0.40,1.00)

# $$

# 

# Therefore:

# 

# $$

# S\_t=sign\_t\\cdot |S\_t|

# $$

# 

# The table stores both:

# 

# systemic\_shock

# 

# systemic\_shock\_flag

# 

# The shock is a common world condition. Its downstream impact may be heterogeneous.

# 

# 9\. RNG and reproducibility

# 

# The extracted macro generator currently preserves the legacy banking V4 realization exactly.

# 

# Current reproducibility contract:

# 

# MACRO\_WORLD\_SEED = 1146763347

# RNG\_STREAM\_MACRO = 502

# 

# The RNG is created through the centralized helper in scripts/core/rng.py.

# 

# The extraction from the former banking-owned implementation was validated against the pre-existing bank\_macro\_environment.csv:

# 

# SHAPE OLD: (6, 10)

# SHAPE NEW: (6, 10)

# COLUMNS EQUAL: True

# DATA EQUAL: True

# MAX NUMERIC DIFF: 0.0

# 

# Therefore the extraction changed architectural ownership without changing the realized macro world.

# 

# The current seed is intentionally preserved during this refactor. A later centralized seed architecture may change where the seed is configured, but that must be treated as a separate controlled change.

# 

# 10\. Relationship with banks

# 

# Banks consume the common macro environment through heterogeneous sensitivities.

# 

# Conceptually:

# 

# \\mu\_i

# \+

# \\phi\_i(z\_{i,t-1}-\\mu\_i)

# \+

# \\beta\_i M\_t

# \+

# \\gamma\_i S\_t

# \+

# \\delta\_{i,t}

# \+

# \\varepsilon\_{i,t}

# $$

# 

# The macro generator does not determine bank market weights.

# 

# It only produces common causal conditions.

# 

# 11\. Relationship with branches

# 

# Branches may consume the same annual macro realization as one component of branch-level pressure.

# 

# Conceptually:

# 

# g(M\_t,Z\_{r,t},\\varepsilon\_{r,t})

# $$

# 

# The macro generator does not determine branch closures.

# 

# Closure remains a downstream stochastic realization.

# 

# 12\. Causal interpretation

# 

# BTYT does not use macro state to script outcomes.

# 

# The intended architecture is:

# 

# Common cause

# &#x20;   ↓

# Probability / latent-state shift

# &#x20;   ↓

# Independent downstream draw

# 

# not:

# 

# Common cause

# &#x20;   ↓

# Predetermined outcome

# 

# This distinction is mandatory across systems.

# 

# 13\. Validation contract

# 

# The macro table must validate:

# 

# exactly one row per configured observation year;

# 

# unique year;

# 

# complete configured year coverage;

# 

# no missing macro factors;

# 

# finite numeric values;

# 

# all six macro factors within \[-1.50, 1.50];

# 

# systemic\_shock\_flag = False implies systemic\_shock = 0;

# 

# when systemic\_shock\_flag = True, the absolute shock magnitude is within \[0.40, 1.00];

# 

# 2021 has no systemic shock in the current implementation;

# 

# reproducible output for the same seed, stream, and configuration.

# 

# Downstream generators must also verify that the required macro years are present before generation.

# 

# Validations must never be weakened merely to obtain a PASS.

# 

# 14\. File lifecycle

# 

# The canonical generated file is:

# 

# data/generated/world/macro\_environment.csv

# 

# The former location:

# 

# data/generated/performance/bank\_macro\_environment.csv

# 

# is legacy architecture and should be removed only after every downstream consumer has migrated and equivalence has been verified.

# 

# The definitive BTYT dataset lifecycle remains:

# 

# candidate → current → frozen

# 

# Frozen data is promoted, never generated directly.

# 

# 15\. Configuration boundary

# 

# The following belong to centralized world configuration:

# 

# world identity;

# 

# observation period;

# 

# execution mode;

# 

# population-level world settings;

# 

# canonical data-reliability mode;

# 

# future global seed architecture once frozen.

# 

# The following remain implementation/model concerns rather than JSON configuration:

# 

# AR equations;

# 

# innovation distributions;

# 

# clipping behavior;

# 

# systemic-shock mechanism;

# 

# internal RNG stream IDs;

# 

# validation logic.

# 

# Principle:

# 

# JSON says what world we want. Python knows how to build it.

# 

# 16\. Auditability

# 

# The macro realization must be traceable through the future run manifest.

# 

# At minimum the world pipeline should eventually record:

# 

# world/run identifier;

# 

# configuration hash;

# 

# Git commit;

# 

# generator version/commit state;

# 

# seed architecture;

# 

# output row count;

# 

# audit status;

# 

# promotion status.

# 

# This table is small, so optimization is not a priority. Clarity, reproducibility, and stable ownership are more important than chunking or incremental I/O.

# 

# 17\. Frozen architectural decisions

# 

# The following decisions are currently frozen:

# 

# macro environment is a world-level state;

# 

# it is generated upstream of banks and branches;

# 

# it is generated once per world;

# 

# downstream systems consume the same realized macro state;

# 

# downstream systems retain independent stochastic streams;

# 

# macro state changes probabilities or latent states rather than assigning outcomes;

# 

# the macro realization is not stored in world\_config.json;

# 

# scripts/core/world.py remains a typed configuration layer, not a stochastic generator;

# 

# canonical output is data/generated/world/macro\_environment.csv;

# 

# canonical generator is scripts/generators/generate\_macro\_environment.py;

# 

# the extracted generator preserves the prior macro DGP and realization exactly;

# 

# the legacy bank\_macro\_environment.csv is temporary compatibility data only;

# 

# final orchestration belongs to scripts/generate\_btyt.py.

# 

# 18\. Next integration step

# 

# After this contract is accepted:

# 

# refactor generate\_banks.py to consume data/generated/world/macro\_environment.csv;

# 

# verify banking outputs against the pre-refactor realization;

# 

# refactor generate\_branches.py to consume the same canonical macro file;

# 

# verify branch outputs against the pre-refactor realization;

# 

# remove the legacy bank\_macro\_environment.csv only after all consumers are migrated;

# 

# continue toward the single-command generate\_btyt.py orchestrator.

# 

# This document is the source of truth for the world-level macro environment and must evolve with the canonical implementation.

