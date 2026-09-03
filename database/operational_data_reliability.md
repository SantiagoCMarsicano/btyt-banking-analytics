# BTYT Operational Data Reliability Layer

**Version:** 1.0.0\
**Project:** BTYT Banking Analytics --- Part I\
**Status:** Design contract\
**Canonical operational mode:** `imperfect`\
**Canonical reliability level:** `realistic`

## 1. Purpose

The Operational Data Reliability Layer transforms the frozen BTYT
ground-truth universe into operational exports that resemble data
received from real banking systems.

It must never alter the frozen files in `data/generated/`,
`data/master/`, or the existing simulation truth. Instead, it creates a
separate observable operational layer containing stochastic,
explainable, and reproducible data-quality degradation.

The purpose is not to create random dirt. It is to create a second
data-generating process in which operational incidents alter the
probability of data-quality problems.

The downstream analyst should be able to discover patterns, formulate
hypotheses about their causes, test those hypotheses through SQL, and
decide whether affected observations should be normalized, recovered,
flagged, or left unresolved.

## 2. Governing principle

> **Operational incidents change the probability of data-quality
> degradation; they do not deterministically assign errors to records.**

This extends the general BTYT modeling principle:

> **BTYT models causes as probabilistic shifts in behavior, not
> deterministic assignments of outcomes. Shared causal conditions may
> influence multiple processes, but downstream realizations use
> independent stochastic streams.**

Consequently, an incident may occur without producing many visible
errors, while a severe incident may create several correlated
manifestations across the records exposed to it.

## 3. Separation from ground truth

The validated BTYT universe remains immutable.

``` text
data/
├── generated/       # frozen analytical ground truth
├── master/          # frozen reference definitions
├── interim/         # latent state and audit provenance
└── operational/     # imperfect operational exports
```

The reliability generator reads frozen inputs and writes new files only
under `data/operational/` and dedicated reliability audit files under
`data/interim/`.

No operational anomaly may modify the original ground-truth files.

## 4. Operating modes

The generator exposes:

``` python
DATA_RELIABILITY_MODE = "imperfect"
```

Supported modes:

### `clean`

Creates operational exports without stochastic degradation.

This mode provides a control world and allows the future ingestion
pipeline to be tested independently of data-quality incidents.

### `imperfect`

Activates the reliability DGP.

This is the canonical BTYT operational world.

## 5. Reliability levels

When `DATA_RELIABILITY_MODE == "imperfect"`:

``` python
DATA_RELIABILITY_LEVEL = "realistic"
```

Supported levels:

``` text
light
realistic
stress
```

These levels modify incident occurrence and severity distributions
rather than fixing final anomaly percentages.

Therefore, `realistic` does not mean that a predetermined percentage of
records must be corrupted.

## 6. Reliability DGP

The conceptual process is:

``` text
frozen ground truth
        ↓
operational systems
        ↓
latent incident occurrence
        ↓
incident severity
        ↓
record exposure
        ↓
conditional anomaly probability
        ↓
record-level realization
        ↓
operational export
```

The three stochastic levels are explicitly separated:

1.  incident occurrence;
2.  incident severity;
3.  record-level realization.

No fixed row ranges or fixed anomaly counts are permitted.

## 7. Independent random streams

The reliability layer uses independent deterministic streams.

``` python
DQ_RNG_STREAMS = {
    "world": 801,
    "incident_occurrence": 802,
    "incident_severity": 803,
    "record_exposure": 804,
    "missingness": 805,
    "format_variation": 806,
    "duplicates": 807,
    "timestamp_degradation": 808,
    "crm_reliability": 809,
}
```

The exact implementation may derive stable sub-seeds from the canonical
data-quality world seed and semantic keys.

Changing duplicate-generation logic must not silently alter the incident
world, missingness realization, or unrelated degradation processes.

## 8. Incident families

V1.0 models five principal operational reliability families.

### 8.1 Branch-system degradation

Represents temporary degradation of branch-side operational systems or
connectivity.

Potential manifestations:

-   missing transaction branch metadata;
-   legacy branch-code representations;
-   reduced timestamp precision;
-   increased probability of manual backfill artifacts.

Exposure should depend on context such as:

-   geography;
-   branch;
-   time period;
-   transaction channel;
-   whether the operation requires branch infrastructure.

A latent incident may be geographically concentrated without exposing an
explicit incident label in the operational dataset.

### 8.2 Digital telemetry degradation

Represents partial failure of digital metadata capture while the
underlying financial transaction remains valid.

Potential manifestations:

-   missing channel metadata;
-   incomplete secondary digital metadata;
-   degraded timestamp precision.

Exposure should be substantially stronger for digital channels than for
branch-originated activity.

The ledger, transaction amount, direction, and execution result remain
ground truth.

### 8.3 Legacy-system migration

Represents coexistence of old and new coding conventions during a system
transition.

Potential manifestations include semantically equivalent representations
such as:

``` text
7
07
7.0
007
```

The generator may also produce compatible legacy labels or date
representations where the source schema permits them.

The purpose is to create normalization problems, not false economic
events.

### 8.4 Manual backfill

Represents records reconstructed or entered after temporary operational
disruption.

Potential manifestations:

-   timestamp rounding;
-   reduced timestamp precision;
-   missing secondary metadata;
-   clustering of multiple quality symptoms.

Manual backfill should often be correlated with another operational
incident rather than appearing as independent random noise.

### 8.5 CRM ingestion degradation

Represents imperfections in campaign/contact-system ingestion.

Potential manifestations:

-   duplicate exposure exports;
-   missing delivery metadata;
-   inconsistent secondary contact metadata;
-   late-ingestion patterns.

The underlying campaign-customer relationship must not be fabricated
merely to generate an error.

## 9. Correlated manifestations

Errors are not IID noise.

A shared latent incident may increase several probabilities
simultaneously.

Example:

``` text
regional branch disruption
        ├── P(branch metadata missing) ↑
        ├── P(timestamp rounding) ↑
        └── P(manual backfill artifact) ↑
```

This correlation is intentional.

It allows downstream analysis to discover that apparently different
quality problems may share a common operational cause.

## 10. Detectability classes

### Visible anomalies

Directly observable through basic profiling.

Examples:

-   `NULL`;
-   duplicate export rows;
-   alternative numeric-code formatting;
-   malformed or inconsistent secondary representations.

### Relational anomalies

Values may appear valid in isolation but become suspicious when compared
with other tables, lifecycle rules, or temporal context.

Examples:

-   a syntactically valid branch code inconsistent with the applicable
    reference representation;
-   metadata incompatible with a branch lifecycle state;
-   duplicated business events identifiable only through composite keys.

### Patterned anomalies

Individual records remain plausible.

The anomaly emerges only through distributions or concentrations across:

-   time;
-   geography;
-   channel;
-   source system;
-   campaign;
-   operational context.

Example:

``` text
An unusually high fraction of timestamps
in one region during a short period
are rounded to exact minutes.
```

These anomalies are specifically intended to support hypothesis
formation rather than simple validation queries.

## 11. Recoverability classes

Operational degradation may be:

### Recoverable

A deterministic normalization rule can restore the semantic value.

Example:

``` text
"007" → 7
```

### Inferable

Other evidence suggests a likely correction, but certainty is
incomplete.

The analyst must decide whether to impute, flag, or preserve the missing
value.

### Irrecoverable

The original metadata cannot be reconstructed reliably.

The correct analytical treatment may be to retain `NULL` and document
the limitation.

The system must not imply that every data-quality problem has a correct
imputation.

## 12. Protected ground-truth fields

V1.0 must not intentionally corrupt core financial truth.

Protected fields include, at minimum:

-   transaction identity;
-   account ownership;
-   transaction amount;
-   transaction direction;
-   transaction completion/failure outcome;
-   accounting balances;
-   loan principal;
-   fundamental customer-account relationships.

The reliability layer is designed to degrade operational representation
and metadata, not rewrite economic history.

## 13. Candidate degradable fields

Depending on source availability, V1.0 may probabilistically affect:

-   transaction branch metadata;
-   channel metadata;
-   secondary timestamps or timestamp precision;
-   branch-code formatting;
-   selected location labels;
-   legacy counterparty-bank representations;
-   CRM delivery metadata;
-   campaign exposure export duplication;
-   nullable non-critical customer attributes.

Every implemented mutation must be explicitly classified as operational
metadata degradation rather than economic ground-truth corruption.

## 14. Positive reliability dynamics

The reliability DGP may also contain improvements.

Examples:

-   successful system migration;
-   infrastructure upgrade;
-   improved telemetry;
-   operational recovery;
-   better validation rules.

These events may reduce anomaly probabilities after their effective
period.

The historical data-quality trajectory therefore need not deteriorate
monotonically.

## 15. Operational outputs

Initial V1.0 target exports:

``` text
data/operational/
├── customers.csv
├── accounts.csv
├── transactions.csv
├── cards.csv
├── loans.csv
├── branches.csv
├── campaign_customers.csv
└── campaign_exposures.csv
```

Not every generated analytical dataset must receive an operational copy.

Datasets such as market, macro, or derived performance tables may remain
outside this layer when there is no meaningful operational-system reason
to degrade them.

## 16. Hidden provenance

The operational exports must not reveal their latent incident causes.

For example, staging must not contain:

``` text
incident_type = EASTERN_STORM
```

The analyst should observe manifestations and infer possible causes.

Internal provenance may be retained under `data/interim/`.

### Reliability world

Suggested output:

``` text
data/interim/data_reliability_world.csv
```

Possible fields:

``` text
world_seed
incident_id
incident_family
start_period
end_period
affected_system
affected_region
latent_severity
```

### Reliability audit

Suggested output:

``` text
data/interim/data_reliability_audit.csv
```

Possible fields:

``` text
dataset
anomaly_family
records_exposed
records_affected
realized_rate
```

These files are generator-validation artifacts and must not be used as
inputs when solving the downstream SQL data-quality exercise.

They are the answer key, not analyst evidence.

## 17. Downstream analytical workflow

The intended workflow is:

``` text
operational exports
       ↓
PostgreSQL staging
       ↓
profiling
       ↓
anomaly discovery
       ↓
pattern analysis
       ↓
hypothesis formation
       ↓
cross-table validation
       ↓
normalization / flagging / retention
       ↓
clean core model
       ↓
analytics layer
```

The analyst should repeatedly ask:

1.  What looks unusual?
2.  Is the anomaly random or patterned?
3.  When did it begin?
4.  Which systems, channels, branches, regions, or campaigns are
    disproportionately affected?
5.  Do multiple anomalies co-occur?
6.  What operational explanation is consistent with the evidence?
7.  Can the value be safely recovered?
8.  If not, should it be flagged or retained as missing?
9.  Does the cleaned result reconcile with trusted financial facts?

## 18. Validation contract

The reliability generator must validate itself without requiring the
operational exports to be clean.

Its checks should include:

-   frozen source files remain unchanged;
-   protected financial fields remain unchanged except for permitted row
    duplication at export level;
-   all anomalies arise through declared reliability mechanisms;
-   clean mode introduces no stochastic degradation;
-   imperfect mode remains reproducible under the same seed;
-   independent RNG streams remain isolated;
-   anomaly rates remain plausible rather than overwhelming the source
    data;
-   incident-driven patterns are detectable in aggregate without
    becoming deterministic;
-   operational output row counts and duplicate inflation are
    documented;
-   internal provenance reconciles with realized aggregate anomalies.

A successful reliability audit means the imperfect exports were
generated according to contract.

It does **not** mean those exports contain no data-quality problems.

## 19. Relationship with the final cross-system audit

The existing BTYT Final Cross-System Audit certifies the frozen
ground-truth universe.

That certification remains authoritative.

The Operational Data Reliability Layer is downstream of that checkpoint:

``` text
ground truth
FINAL VALIDATION: PASS
        ↓
FROZEN
        ↓
Operational Data Reliability Layer
        ↓
intentionally imperfect exports
```

The original final audit must not be rerun against operational exports
with the expectation that every integrity rule will pass.

Instead, operational data receives its own reliability-generation audit
and is later cleaned through the database pipeline.

## 20. Database handoff

The operational layer becomes the preferred input to PostgreSQL staging.

The future architecture is:

``` text
data/operational
        ↓
staging schema
        ↓
SQL data-quality controls
        ↓
core schema
        ↓
analytics schema
        ↓
Power BI
```

The frozen `generated/` universe remains available as internal ground
truth for final reconciliation and project validation, but should not be
used to bypass the intended staging investigation.

## 21. Portfolio objective

This layer changes the project from:

> "A synthetic bank with clean generated data."

into:

> "A synthetic banking environment with validated ground truth,
> stochastic operational data-quality degradation, a reproducible
> ingestion layer, SQL-based quality investigation, relational cleaning,
> reconciliation, and BI modeling."

The intended skill demonstration includes:

-   data-generating-process design;
-   reproducibility;
-   data quality;
-   SQL profiling;
-   anomaly detection;
-   hypothesis formation;
-   root-cause reasoning;
-   dimensional/relational modeling;
-   financial reconciliation;
-   BI engineering.

## 22. Freeze criteria for V1.0

The reliability layer can be frozen when:

1.  clean mode reproduces operationally equivalent clean exports;
2.  realistic mode produces plausible but non-trivial degradation;
3.  no protected financial truth is altered;
4.  incident manifestations exhibit meaningful conditional patterns;
5.  anomalies are neither trivially labeled nor impossible to
    investigate;
6.  the internal reliability audit passes;
7.  repeated runs with the same seed reproduce the same operational
    world;
8.  changing one RNG stream does not unnecessarily perturb unrelated
    mechanisms.

Only after these criteria are satisfied should `data/operational/`
become the canonical source for PostgreSQL staging.

## 23. Final principle

The analyst should not be handed a list of mistakes.

The analyst should be handed evidence.

The operational reliability layer exists so that data-quality work
follows:

``` text
evidence
   ↓
pattern
   ↓
hypothesis
   ↓
test
   ↓
decision
```

That investigative process is part of the BTYT analytical product.
