# Credit Risk Recalibration — October 2026

## Purpose

This document records the Part I credit-risk recalibration performed while building the Power BI **Riesgo de Crédito** page.

The objective was not to force BTYT toward a preselected delinquency KPI. The objective was to correct a synthetic repayment process that was producing an implausibly large accumulation of severe delinquency while preserving the model's causal and stochastic structure.

## Trigger

The initial Power BI risk page exposed a material inconsistency:

```text
90+ DPD exposure rate ≈ 20.74%
```

A technical audit showed that the issue was not primarily the terminal bridge that reconciles master loan status with the monthly snapshot.

The larger problem was the ordinary monthly repayment process:

```text
CURRENT loan-months        ≈ 26.88%
90+ DPD loan-months        ≈ 18.71%
ordinary miss/partial rate ≈ 27.43%
```

That combination allowed arrears to accumulate too easily and created a self-reinforcing delinquency process.

## Recalibration sequence

### 1. Loan master — V5.1.0 RISK RECALIBRATED

The first adjustment reduced lifecycle deterioration and strengthened recovery while preserving:

- product structure;
- origination logic;
- the causal lifecycle;
- stochastic status transitions;
- restructuring / write-off logic;
- the lifecycle bridge used by the monthly snapshot.

The full BTYT/01 run produced, among open loans at cutoff:

```text
ACTIVE         88.00%
DEFAULTED      10.42%
RESTRUCTURED    1.58%
```

This was a large improvement over the previous state but still left a high severe-risk concentration.

### 2. Loan monthly snapshot — V4.2 RISK RECALIBRATED

The monthly repayment process was then recalibrated.

Changes were concentrated in:

- lower ordinary miss probability;
- lower ordinary partial-payment probability;
- reduced excessive burden / arrears sensitivity;
- stronger cure probability;
- stronger cure fraction.

The terminal reconciliation rules for open `DEFAULTED` / severe loans were retained.

After this step the historical loan-month distribution improved materially:

```text
CURRENT        ≈ 63.12%
90+ DPD        ≈  6.44%
```

and ordinary miss/partial behavior outside shock periods fell to a much more defensible level.

### 3. Loan master — V5.2.0 FINAL RISK CALIBRATION

A final moderate master adjustment was made:

```text
DETERIORATION_INTERCEPT  -5.10 → -5.45
RECOVERY_INTERCEPT        0.85 →  0.95
```

No target clamping was introduced.

The full BTYT/01 run then produced, among open loans at cutoff:

```text
ACTIVE          91.20%
DEFAULTED        7.75%
RESTRUCTURED     1.05%
```

The final master contains:

```text
233,441 loans
```

### 4. Final monthly snapshot

The V4.2 snapshot was regenerated from the V5.2 master.

Final snapshot size:

```text
4,109,490 loan-month rows
```

The historical 90+ DPD share fell to approximately:

```text
4.90% of loan-month observations
```

## Current 2026-12 exposure check

Using the December 2026 loan snapshot and annual FX convention:

```text
Total exposure        ≈ US$4.338B
90+ DPD exposure      ≈ US$223.8M
90+ exposure rate     ≈ 5.16%
```

The result moved through the following sequence during diagnosis:

```text
20.74%  →  7.13%  →  5.16%
```

The final value was accepted because the mechanics were corrected and the resulting KPI emerged from the model. No further tuning was performed merely to hit a round target.

## Current Power BI risk KPI row

After PostgreSQL refresh, the Power BI page showed:

```text
Exposición crediticia          ≈ US$4.338M displayed
Exposición 90+ DPD              5.16%
Cartera reestructurada          0.64%
Pérdida crediticia / cartera    0.63%
```

Power BI display units use the current dashboard formatting convention; underlying calculations retain full precision.

The earlier 30+ DPD headline KPI was removed from the top row because it added little decision value in the previous calibration. It may still be used as a secondary diagnostic or trend measure.

## Modeling principles preserved

The recalibration preserves the intended architecture:

```text
customer / loan conditions
        ↓
probabilistic lifecycle deterioration
        ↓
recovery / restructure / write-off paths
        ↓
master status at cutoff
        ↓
monthly payment chronology
        ↓
DPD / arrears / outstanding exposure
        ↓
performance credit-loss layer
```

The model does **not**:

- randomly assign a fixed final default percentage;
- force a fixed 90+ DPD target;
- clamp Power BI outputs;
- overwrite the terminal lifecycle to make the dashboard look better.

## Downstream propagation

Because credit risk changed, the following chain was regenerated:

```text
loans
    ↓
loan_monthly_snapshot
    ↓
branch_monthly_performance
    ↓
bank_monthly_performance
    ↓
PostgreSQL full refresh
    ↓
analytics materialized-view refresh
    ↓
Power BI refresh
```

The 2026-10-11 PostgreSQL full refresh successfully reloaded all 23 physical tables and refreshed the analytics materialized views.

## Reproducibility caveat before the next freeze

The risk and performance outputs above are the **current analytical realization**, but a world-configuration consistency check remains open.

The canonical registry identifies BTYT/01 with seed:

```text
3839777825
```

while the 2026-10-11 branch-performance regeneration printed:

```text
3165889979
```

despite reading BTYT/01 source files.

The codebase currently separates:

```text
active_world.json   → physical world path
world_config.json   → load_world() seed/settings
```

These must be synchronized and the RNG-driven regenerated layers reverified before issuing a new canonical dataset manifest/fingerprint.

Until that verification is complete, the October 2026 risk figures should be treated as the current Power BI / analytical state, not as a newly frozen manifest release.
