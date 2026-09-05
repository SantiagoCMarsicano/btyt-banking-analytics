# BTYT Banking Analytics — External Shocks Data Dictionary

## 1. Purpose

The External Shocks layer introduces exogenous and idiosyncratic disturbances into the BTYT synthetic banking universe while preserving the project's central modeling principle:

> **Causes modify probabilities and latent conditions; they do not deterministically assign observable outcomes.**

The engine models external conditions at multiple scales and produces latent state tables that downstream banking generators may consume probabilistically.

The layer is designed to support:

- macroeconomic disturbances;
- national/systemic shocks;
- regional events;
- sector-specific shocks;
- customer- and business-specific idiosyncratic events;
- heterogeneous exposure;
- heterogeneous resilience and vulnerability;
- temporal persistence and recovery;
- economically defensible interactions between shocks;
- common-cause mediation to reduce double counting;
- independent stochastic realization across causal mechanisms.

The External Shocks engine does **not** directly force defaults, transactions, account closures, loan originations, deposit withdrawals, or profitability outcomes.

It modifies the environment in which those outcomes may later occur.

---

# 2. Modeling Philosophy

## 2.1 Probability rather than deterministic assignment

A shock is not equivalent to an outcome.

For example:

```text
Economic slowdown
        ↓
Higher latent financial stress
        ↓
Higher probability of payment difficulty
        ↓
Independent stochastic realization
        ↓
Some customers deteriorate; others do not
```

The following logic is intentionally avoided:

```text
IF recession = TRUE
THEN customer defaults
```

Instead, downstream systems should follow a structure such as:

```text
baseline probability
+ customer characteristics
+ product characteristics
+ external shock state
+ idiosyncratic conditions
+ stochastic noise
        ↓
realized probability
        ↓
independent random draw
        ↓
observable outcome
```

This preserves heterogeneity and prevents the synthetic world from becoming mechanically scripted.

---

## 2.2 Conditional independence

Different banking processes may share the same external causal environment without sharing the same stochastic realization.

For example, an inflation shock may simultaneously influence:

- deposits;
- credit demand;
- delinquency risk;
- transaction activity;
- branch operating costs.

However, each downstream generator should use its own RNG stream.

Conceptually:

```text
                 Shared external state
                         ↓
        ┌────────────────┼────────────────┐
        ↓                ↓                ↓
 Transactions         Credit           Deposits
        ↓                ↓                ↓
 independent RNG     independent RNG   independent RNG
```

Therefore, the system models **conditional dependence through shared causes** while preserving **stochastic independence in downstream realization**.

---

# 3. Shock Hierarchy

The engine contains four distinct shock scales.

## 3.1 SYSTEMIC

Systemic shocks affect the national banking environment.

Examples implemented by the engine include:

- inflation and interest-rate pressure;
- exchange-rate volatility;
- national economic slowdown;
- national economic expansion;
- energy and operating-cost shocks;
- financial confidence shocks;
- digital adoption acceleration.

Systemic shocks are common world conditions, but their effective impact varies across regions, sectors, products, and customers.

---

## 3.2 REGIONAL

Regional shocks are genuine localized events rather than simple exposure multipliers applied to national shocks.

Implemented examples include:

- regional drought;
- regional flooding;
- regional tourism surge;
- regional tourism slump;
- regional infrastructure disruption.

Each regional event selects a geographic scope stochastically from an economically plausible set of regions.

The selected region receives stronger exposure, while other regions may retain weaker spillover exposure.

---

## 3.3 SECTORAL

Sectoral shocks originate primarily within a specific economic activity.

Implemented examples include:

- agricultural commodity upswing;
- import-cost pressure;
- export-demand upswing;
- retail and services slowdown.

Sectoral shocks select an affected sector stochastically and may propagate partially to related sectors, regions, and financial products.

---

## 3.4 IDIOSYNCRATIC

Idiosyncratic shocks occur at the customer or business level.

Implemented events include:

### Negative household/business events

- job loss;
- income reduction;
- extraordinary expense;
- business revenue drop;
- business distress.

### Positive household/business events

- positive income shock;
- business expansion.

Their probability may increase or decrease according to the shared macroeconomic, regional, and sectoral environment, but their realization remains independent.

Therefore:

```text
Shared adverse environment
        ↓
higher probability of job loss
        ↓
customer-specific Bernoulli draw
        ↓
job loss may or may not occur
```

---

# 4. Temporal Structure

The modeled period is:

```text
2021-01 → 2026-12
```

Each non-idiosyncratic shock contains:

- start month;
- peak month;
- active end month;
- recovery end month;
- duration;
- recovery duration;
- peak magnitude;
- persistence parameter;
- recovery shape.

A typical shock follows:

```text
Emergence
   ↓
Peak
   ↓
Persistence / decay
   ↓
Active period ends
   ↓
Recovery tail
   ↓
Return toward baseline
```

The temporal profile is continuous rather than a binary ON/OFF switch.

---

# 5. Shock Magnitude and Direction

Each event receives a stochastic magnitude drawn from a shock-specific bounded distribution.

Possible directions are:

```text
POSITIVE
NEGATIVE
```

Some shock families have a fixed economic direction.

Examples:

```text
ACTIVITY_SLOWDOWN → NEGATIVE
ACTIVITY_BOOM     → POSITIVE
REGIONAL_DROUGHT → NEGATIVE
```

Other events may be mixed.

For mixed events, direction is itself stochastic.

Magnitude and occurrence are separate random processes.

This means that:

- a shock may not occur;
- if it occurs, its timing is uncertain;
- its magnitude is uncertain;
- its persistence is uncertain;
- its transmission is heterogeneous.

---

# 6. Occurrence Process

Each shock family has an annual hazard.

Across the six-year simulation horizon, the number of realized events is generated probabilistically.

The engine does not require every defined shock type to appear in the production world.

Consequently, simulated worlds may contain:

- relatively calm periods;
- multiple overlapping disturbances;
- positive environments;
- adverse environments;
- regional disturbances without national crises;
- sectoral disturbances;
- combinations of the above.

The architecture intentionally allows alternative histories.

---

# 7. Exposure Layer

Shock existence and shock exposure are separate concepts.

A realized event does not affect every economic agent equally.

Exposure is modeled across three observable dimensions plus a transmission layer:

```text
REGION
SECTOR
PRODUCT_GROUP
TRANSMISSION
```

Exposure multipliers receive stochastic perturbations around their structural baseline.

This prevents all customers in the same broad category from being treated identically.

---

## 7.1 Regions

Canonical external-shock regions are:

```text
MONTEVIDEO
METROPOLITAN
EAST
NORTH
CENTER
LITORAL
```

Regional sensitivity depends on the shock.

Example:

```text
Regional drought

CENTER       high exposure
NORTH        high exposure
LITORAL      high exposure
EAST         elevated exposure
MONTEVIDEO   low direct exposure
```

---

## 7.2 Sectors

Canonical sectors are:

```text
HOUSEHOLD
RETAIL_SERVICES
TOURISM
AGRICULTURE
TRADE_IMPORT
TRADE_EXPORT
SME_GENERAL
```

Examples of heterogeneous transmission:

```text
FX shock
    ↓
TRADE_IMPORT   strong exposure
TRADE_EXPORT   strong but different exposure
HOUSEHOLD      lower direct exposure
```

and:

```text
Drought
    ↓
AGRICULTURE    very high exposure
TRADE_EXPORT   secondary exposure
TOURISM        low exposure
```

---

## 7.3 Product groups

Canonical product groups are:

```text
DEPOSITS
CARDS
PERSONAL_CREDIT
MORTGAGES
SME_CREDIT
AGRICULTURAL_CREDIT
BUSINESS_CREDIT_LINES
```

Product exposure allows the same event to transmit differently through different parts of the bank.

For example:

```text
Drought
        ↓
AGRICULTURAL_CREDIT    strong
SME_CREDIT             moderate
CARDS                   limited direct effect
```

---

# 8. Transmission Dimensions

The engine defines the following latent transmission dimensions:

| Dimension | Interpretation |
|---|---|
| `transaction_activity` | Pressure on transaction frequency |
| `transaction_amount` | Pressure on transaction values |
| `cash_preference` | Relative preference for cash |
| `digital_preference` | Relative preference for digital channels |
| `deposit_growth` | Pressure on deposit accumulation |
| `deposit_withdrawal_pressure` | Pressure toward withdrawals |
| `loan_demand` | Demand-side credit pressure |
| `payment_stress` | General repayment stress |
| `delinquency_entry` | Pressure on probability of entering delinquency |
| `cure_probability` | Pressure on probability of curing delinquency |
| `branch_operating_cost` | Pressure on branch operating costs |
| `business_activity` | Local/customer business activity |
| `interest_rate_pressure` | Interest-rate environment pressure |
| `usd_preference` | Preference for USD-denominated holdings/activity |

These coefficients are **latent causal inputs**.

They are not final BI KPIs and should not be presented as realized business outcomes.

---

# 9. Resilience and Vulnerability

External exposure alone does not determine customer impact.

The engine generates a customer-level resilience score using available banking/customer characteristics plus an independent stochastic component.

The resilience layer uses available proxies such as:

- income;
- banking tenure;
- number of accounts;
- number of loans;
- aggregate original loan amount;
- adverse loan history;
- customer/business type.

The resulting variables are:

```text
resilience_score
vulnerability_score
resilience_band
```

with:

```text
vulnerability_score = 1 - resilience_score
```

Resilience is bounded between 0 and 1.

It is a latent modeling variable, not an externally observed customer attribute.

---

## 9.1 Resilience bands

Possible bands are:

```text
VERY_LOW
LOW
MEDIUM
HIGH
VERY_HIGH
```

Two customers exposed to the same adverse event can therefore experience different effective stress.

Conceptually:

```text
same shock
   ↓
same broad exposure
   ↓
different resilience
   ↓
different effective latent stress
   ↓
different downstream probabilities
```

---

# 10. Customer-Month External State

The principal customer-level causal bridge is:

```text
external_customer_monthly_state.csv
```

Its grain is:

```text
one customer × one month
```

for the complete 2021–2026 horizon.

With 10,000 customers and 72 months, the expected grain is:

```text
720,000 customer-month rows
```

This table combines:

- systemic state;
- regional state;
- sectoral state;
- interaction state;
- customer resilience;
- customer vulnerability;
- adverse shared stress;
- positive shared impulse;
- idiosyncratic state;
- final net external state.

This is the intended bridge between the External Shocks engine and downstream observable banking generators.

---

# 11. Shared Stress vs Idiosyncratic Stress

The engine explicitly separates common causes from individual realizations.

For each customer-month:

```text
systemic conditions
+
regional conditions
+
sectoral conditions
+
limited interactions
        ↓
shared external state
```

Customer resilience then modifies the effective impact.

Afterward, independent idiosyncratic events may occur.

Therefore:

```text
net external state
=
positive shared impulse
-
adverse shared stress
+
idiosyncratic state
```

The final state remains latent.

---

# 12. Common-Cause Mediation and Double Counting

A central risk in multilevel shock modeling is counting the same causal deterioration twice.

Example:

```text
Economic slowdown
       ↓
Job-loss probability rises
       ↓
Job loss occurs
```

If downstream credit risk receives:

1. the full slowdown effect, and
2. the full job-loss effect,

the same underlying cause can be overstated.

The engine addresses this with:

```text
mediated_share
```

For each idiosyncratic event, part of the event magnitude is recognized as mediated by the shared environment.

The idiosyncratic layer therefore records:

```text
raw_magnitude
mediated_share
residual_idiosyncratic_intensity
```

where conceptually:

```text
residual idiosyncratic intensity
=
raw event magnitude
×
(1 - mediated share)
```

Downstream systems should use the residual idiosyncratic component together with the shared state rather than blindly adding two full effects.

---

# 13. Shock Interactions

The model permits interactions only when there is a defensible economic mechanism.

It does **not** generate arbitrary pairwise interactions between every shock.

Implemented interaction families include:

```text
INFLATION_RATE_SHOCK
+
ACTIVITY_SLOWDOWN
→ STAGFLATION_PRESSURE
```

```text
INFLATION_RATE_SHOCK
+
REGIONAL_DROUGHT
→ RATE_DROUGHT_STRESS
```

```text
ACTIVITY_SLOWDOWN
+
RETAIL_SERVICES_SLOWDOWN
→ RETAIL_RECESSION_AMPLIFIER
```

```text
FX_SHOCK
+
IMPORT_COST_PRESSURE
→ FX_IMPORT_COST_AMPLIFIER
```

```text
ACTIVITY_BOOM
+
EXPORT_DEMAND_UPSWING
→ EXPORT_EXPANSION_AMPLIFIER
```

Interaction magnitude depends on overlapping realized shock intensity and an independent stochastic perturbation.

This keeps interactions:

- sparse;
- interpretable;
- causal;
- bounded.

---

# 14. Recovery

Shock effects do not disappear instantly when the active event ends.

Each event includes a stochastic recovery period.

The recovery process has:

```text
recovery_months
recovery_shape
```

and produces a decaying tail.

This supports phenomena such as:

- delayed household recovery;
- persistent credit stress;
- lingering business weakness;
- gradual normalization after regional disruption.

Idiosyncratic events also receive their own recovery periods.

---

# 15. Independent RNG Architecture

The engine separates random-number streams by causal mechanism.

This is essential for stochastic independence and reproducibility.

Current streams are:

| Stream | Purpose |
|---|---|
| `601` | Systemic occurrence |
| `602` | Systemic timing |
| `603` | Systemic magnitude |
| `604` | Systemic persistence |
| `611` | Regional occurrence |
| `612` | Regional timing |
| `613` | Regional magnitude |
| `614` | Regional scope |
| `621` | Sectoral occurrence |
| `622` | Sectoral timing |
| `623` | Sectoral magnitude |
| `624` | Sectoral scope |
| `631` | Exposure |
| `632` | Resilience |
| `633` | Shock interactions |
| `634` | Recovery |
| `641` | Idiosyncratic occurrence |
| `642` | Idiosyncratic timing |
| `643` | Idiosyncratic magnitude |
| `644` | Common-cause mediation |
| `651` | Customer-level exposure jitter |

The production world seed is stored separately from the stream identifiers.

The design guarantees that changing one mechanism does not intentionally reuse the same random draw as another mechanism.

---

# 16. Output Tables

## 16.1 `external_shocks.csv`

Location:

```text
data/master/external_shocks.csv
```

Grain:

```text
one realized systemic/regional/sectoral shock
```

Fields:

| Field | Description |
|---|---|
| `shock_id` | Unique shock identifier |
| `shock_name` | Human-readable event name |
| `shock_type` | Structural shock family |
| `shock_scale` | SYSTEMIC, REGIONAL, or SECTORAL |
| `direction` | POSITIVE or NEGATIVE |
| `region_scope` | Primary regional scope or ALL |
| `sector_scope` | Primary sectoral scope or ALL |
| `start_month` | First active month |
| `peak_month` | Peak month |
| `end_month` | Last active month |
| `recovery_end_month` | Final recovery month |
| `duration_months` | Active duration |
| `recovery_months` | Recovery duration |
| `peak_magnitude` | Absolute peak magnitude |
| `signed_peak_intensity` | Direction-adjusted peak magnitude |
| `persistence` | Post-peak persistence parameter |
| `recovery_shape` | Recovery-decay parameter |

This table is suitable for describing the realized external history of the synthetic world.

---

## 16.2 `external_shock_monthly_state.csv`

Location:

```text
data/interim/external_shock_monthly_state.csv
```

Grain:

```text
one realized shock × one affected month
```

Fields:

| Field | Description |
|---|---|
| `shock_id` | Shock identifier |
| `year_month` | Calendar month |
| `shock_type` | Shock family |
| `shock_scale` | Shock scale |
| `phase` | ACTIVE or RECOVERY |
| `direction` | POSITIVE or NEGATIVE |
| `profile_intensity` | Temporal profile between 0 and 1 |
| `realized_intensity` | Signed magnitude after temporal profile |

---

## 16.3 `external_shock_exposure.csv`

Location:

```text
data/interim/external_shock_exposure.csv
```

Grain:

```text
one shock × one exposure/transmission element
```

Fields:

| Field | Description |
|---|---|
| `shock_id` | Shock identifier |
| `scope_type` | REGION, SECTOR, PRODUCT_GROUP, or TRANSMISSION |
| `scope_value` | Specific region, sector, product group, or transmission dimension |
| `exposure_multiplier` | Realized exposure multiplier or signed transmission coefficient |

For `TRANSMISSION` rows, the final field represents a signed causal coefficient rather than a conventional positive exposure multiplier.

---

## 16.4 `external_shock_resilience.csv`

Location:

```text
data/interim/external_shock_resilience.csv
```

Grain:

```text
one customer
```

Fields:

| Field | Description |
|---|---|
| `customer_id` | Customer identifier |
| `agent_type` | HOUSEHOLD or BUSINESS |
| `region` | Customer region |
| `sector` | Customer economic sector |
| `resilience_score` | Latent resilience in [0,1] |
| `vulnerability_score` | `1 - resilience_score` |
| `resilience_band` | Categorical resilience band |

---

## 16.5 `external_shock_interactions.csv`

Location:

```text
data/interim/external_shock_interactions.csv
```

Grain:

```text
one economically valid shock interaction × month
```

Fields:

| Field | Description |
|---|---|
| `interaction_id` | Unique interaction identifier |
| `interaction_type` | Economic interaction mechanism |
| `shock_id_a` | First shock |
| `shock_id_b` | Second shock |
| `year_month` | Month of overlap |
| `interaction_intensity` | Realized interaction strength |

---

## 16.6 `external_idiosyncratic_events.csv`

Location:

```text
data/interim/external_idiosyncratic_events.csv
```

Grain:

```text
one realized idiosyncratic event
```

Fields:

| Field | Description |
|---|---|
| `idio_event_id` | Unique event identifier |
| `customer_id` | Affected customer |
| `agent_type` | HOUSEHOLD or BUSINESS |
| `region` | Customer region |
| `sector` | Customer sector |
| `event_type` | Idiosyncratic event family |
| `event_name` | Human-readable event name |
| `direction` | POSITIVE or NEGATIVE |
| `start_month` | Event start |
| `end_month` | Active end |
| `recovery_end_month` | Recovery end |
| `duration_months` | Active duration |
| `recovery_months` | Recovery duration |
| `raw_magnitude` | Original event magnitude |
| `mediated_share` | Portion attributed to shared causal conditions |
| `residual_idiosyncratic_intensity` | Remaining independent event effect |
| `shared_stress_at_start` | Adverse shared state at event start |
| `shared_positive_at_start` | Positive shared state at event start |
| `realized_probability` | Customer-month event probability used for realization |

---

## 16.7 `external_customer_monthly_state.csv`

Location:

```text
data/interim/external_customer_monthly_state.csv
```

Grain:

```text
one customer × one month
```

Fields:

| Field | Description |
|---|---|
| `customer_id` | Customer identifier |
| `year_month` | Calendar month |
| `systemic_state` | Customer-specific systemic exposure |
| `regional_state` | Customer-specific regional exposure |
| `sectoral_state` | Customer-specific sectoral exposure |
| `interaction_state` | Shared interaction state |
| `adverse_shared_stress` | Resilience-adjusted adverse common stress |
| `positive_shared_impulse` | Resilience-adjusted positive common impulse |
| `resilience_score` | Customer resilience |
| `vulnerability_score` | Customer vulnerability |
| `idiosyncratic_state` | Residual customer-specific event state |
| `net_external_state` | Combined external latent state |

This is the principal downstream integration table.

---

## 16.8 `external_shock_world_parameters.csv`

Location:

```text
data/interim/external_shock_world_parameters.csv
```

Grain:

```text
one production world
```

Stores:

- engine version;
- world seed;
- simulation period;
- all RNG stream identifiers.

Its purpose is reproducibility and auditability.

---

## 16.9 `external_shock_audit.csv`

Location:

```text
data/interim/external_shock_audit.csv
```

Created when a multi-world audit is requested.

Grain:

```text
one simulated audit world
```

It records statistics such as:

- total realized shocks;
- systemic shock count;
- regional shock count;
- sectoral shock count;
- positive/negative counts;
- active months;
- quiet months;
- overlapping months;
- maximum simultaneous shocks;
- mean absolute net intensity.

---

# 17. Idiosyncratic Event Probability

Idiosyncratic event probabilities are generated monthly.

The baseline annual event probability is converted to a monthly probability.

That baseline is then modified by:

- household/business applicability;
- shared adverse or positive state;
- regional pressure;
- sectoral pressure.

Conceptually:

```text
logit(P(event))
=
baseline
+ agent applicability
+ macro/shared environment
+ regional environment
+ sector environment
```

The resulting probability is bounded.

An independent random draw determines whether the event occurs.

A cooldown prevents repeated realization of the same event type for the same customer within an unrealistically short period.

---

# 18. Downstream Integration Rules

The External Shocks engine should not directly rewrite observable banking outcomes.

Instead, downstream generators should consume the latent state.

Examples:

## Transactions

Potential inputs:

```text
transaction_activity
transaction_amount
cash_preference
digital_preference
net_external_state
```

These should modify transaction probabilities or distributions.

They must not directly assign transaction counts.

---

## Deposits and balances

Potential inputs:

```text
deposit_growth
deposit_withdrawal_pressure
net_external_state
```

These may modify expected inflows, outflows, and balance evolution.

---

## Credit demand

Potential inputs:

```text
loan_demand
business_activity
interest_rate_pressure
```

These should affect origination probability and/or requested amounts.

---

## Credit performance

Potential inputs:

```text
payment_stress
delinquency_entry
cure_probability
adverse_shared_stress
idiosyncratic_state
```

These should modify transition probabilities.

A shock must never directly set:

```text
loan_status = DEFAULTED
```

---

## Branch performance

Potential inputs:

```text
branch_operating_cost
transaction_activity
business_activity
deposit conditions
credit conditions
```

These may influence branch revenue and cost distributions.

---

# 19. Relationship with Existing Branch Shocks

The project already contains local branch-level shock mechanisms in:

```text
branch_yearly_state.csv
```

Those local shocks and the External Shocks engine serve different purposes.

### Branch local shocks

Represent branch-specific operational/local circumstances.

Examples may include:

- localized operating disruption;
- branch pressure;
- branch-specific cost stress;
- local incidents.

### External shocks

Represent broader economic, geographic, sectoral, and customer-specific conditions.

The two systems should remain distinct.

If both influence the same downstream outcome, their contributions should enter through separate causal terms and independent stochastic realization.

---

# 20. Relationship with Campaigns

External shocks are exogenous conditions.

Campaigns are bank interventions.

Conceptually:

```text
External environment
        ↓
customer economic state
        ↓
baseline behavioral propensity
        ↓
campaign targeting/exposure
        ↓
engagement probability
        ↓
conversion probability
        ↓
independent realization
```

Campaign effectiveness may therefore depend on the external state.

Examples:

```text
High-rate environment
→ lower probability of converting some loan campaigns
```

```text
High uncertainty
→ potentially higher response to selected savings campaigns
```

External shocks must not deterministically determine campaign conversion.

---

# 21. Validation

The production engine performs structural validation.

Checks include:

- unique `shock_id`;
- valid shock references;
- valid simulation months;
- bounded temporal profiles;
- unique exposure rows;
- chronological consistency;
- resilience bounded to [0,1];
- exact customer-month grain;
- unique customer-month keys;
- valid mediation shares.

The script must fail if structural validation fails.

---

# 22. Multi-World Audit

A Monte Carlo audit can be run independently of the production world.

The audit evaluates whether the stochastic DGP produces a plausible family of alternative worlds rather than merely validating one seed.

Audit concepts include:

- quiet worlds remain possible;
- non-quiet worlds are common;
- extreme shock counts remain rare;
- systemic shocks can occur;
- regional shocks can occur;
- sectoral shocks can occur;
- positive shocks can occur;
- negative shocks can occur;
- quiet months remain present;
- aggregate intensity remains bounded.

The audit does not force a specific production result.

It validates the **distribution-generating process**.

---

# 23. Freeze Principle

The External Shocks engine is a causal layer.

Before it is wired into observable banking tables, the following must be validated and frozen:

```text
shock occurrence
shock timing
shock magnitude
regional scope
sectoral scope
exposure
resilience
interaction logic
recovery
idiosyncratic event incidence
common-cause mediation
multi-world behavior
```

Only after this layer passes audit should downstream observable tables be reopened for controlled integration.

The correct workflow is:

```text
External shock architecture
        ↓
Production world
        ↓
Structural validation
        ↓
Multi-world audit
        ↓
Calibration
        ↓
Freeze external-shock DGP
        ↓
Integrate with downstream banking generators
        ↓
Regenerate affected observable tables
        ↓
Cross-system validation
        ↓
Final freeze
```

---

# 24. Design Principles to Preserve

The following principles are mandatory for future modifications.

### 1. No deterministic outcome assignment

Shocks modify probabilities and distributions.

### 2. Independent RNG streams

Different causal mechanisms must not reuse the same stochastic realization.

### 3. Heterogeneous exposure

National, regional, sectoral, product, and customer sensitivity must differ.

### 4. Heterogeneous resilience

Equal exposure does not imply equal realized stress.

### 5. Real regional and sectoral events

Regional and sectoral shocks must exist independently rather than merely being multipliers on national events.

### 6. Idiosyncratic uncertainty

Individual events remain stochastic even when common conditions increase their probability.

### 7. Positive and negative events

The world must not be structurally biased toward crisis-only histories.

### 8. Persistence and recovery

Effects evolve through time rather than switching instantly on and off.

### 9. Limited interactions

Only economically defensible shock combinations receive interaction terms.

### 10. Avoid double counting

Shared causes and mediated individual events must be separated.

### 11. Latent state remains latent

Internal causal variables should live primarily in `data/interim/`, not be exposed as ready-made BI KPIs.

### 12. Alternative worlds must remain possible

The production seed is one realization of a broader stochastic DGP.

---

# 25. Canonical Causal Structure

The complete architecture can be summarized as:

```text
                         WORLD SEED
                             ↓
               Independent RNG mechanisms
                             ↓
       ┌─────────────────────┼─────────────────────┐
       ↓                     ↓                     ↓
   SYSTEMIC              REGIONAL              SECTORAL
    SHOCKS                SHOCKS                SHOCKS
       └─────────────────────┼─────────────────────┘
                             ↓
                  Temporal realization
              magnitude + persistence
                       + recovery
                             ↓
                 Heterogeneous exposure
               region / sector / product
                             ↓
                 Limited interactions
                             ↓
                     Shared state
                             ↓
             Customer resilience/vulnerability
                             ↓
              Customer-specific shared stress
                             ↓
             ┌───────────────┴───────────────┐
             ↓                               ↓
      Shared causal effect          Idiosyncratic-event
                                   probability changes
                                             ↓
                                   Independent realization
                                             ↓
                                  Common-cause mediation
                                             ↓
                                  Residual idiosyncratic
                                          effect
             └───────────────┬───────────────┘
                             ↓
                 CUSTOMER-MONTH EXTERNAL STATE
                             ↓
          Independent downstream banking processes
                             ↓
        Transactions / Deposits / Credit / Costs
                             ↓
                  Observable bank outcomes
```

---

# 26. Final Modeling Statement

The BTYT External Shocks layer represents external events as **stochastic causal pressures rather than scripted outcomes**.

National, regional, sectoral, and individual conditions coexist within one coherent hierarchy.

Shared conditions create realistic correlation across the banking system, while independent random streams preserve uncertainty at each stage.

The intended result is a synthetic banking world in which:

> **the same external event can affect many agents, but not every agent in the same way, not every banking process through the same realization, and never with a predetermined final outcome.**

This principle must remain intact throughout subsequent campaign modeling, database construction, SQL analytics, Power BI modeling, and the later credit-risk layer.
