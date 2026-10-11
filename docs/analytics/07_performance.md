# 07 — Bank Performance & Executive Management Analytics

> **Performance Engine:** `generate_branch_performance.py`  
> **Engine version:** `3.2.0`  
> **Observation grain:** monthly  
> **Reporting currency:** UYU-equivalent  
> **Design principle:** structural conditions shape probabilities, but do not pre-determine performance outcomes.
>
> **Current implementation note (2026-10-11):** the engine was regenerated downstream of the V5.2/V4.2 credit-risk recalibration, then loaded through the 23-table PostgreSQL full refresh. A world-seed synchronization check remains open before a new dataset manifest is issued.

---

## Objective

Build the final Part I analytical layer for consolidated BTYT management performance.

The central question is:

> **How is BTYT performing as a bank, what is driving changes in revenue, operating costs, credit losses and net income, and how should management interpret those changes over time?**

This file is the executive synthesis of Part I.

It connects:

1. business scale;
2. balance-sheet operating scale;
3. transaction activity;
4. revenue generation;
5. operating-cost structure;
6. credit losses;
7. profitability;
8. customer/account productivity;
9. branch contribution;
10. macroeconomic, shock and market context.

The objective is not to calculate every management KPI directly in SQL.

PostgreSQL provides stable analytical grains and reusable context. Power BI / DAX owns dynamic ratios, time intelligence, filter-aware KPIs and executive interaction.

---

# 1. Scope

The performance layer covers:

- active customers;
- active accounts;
- average deposits;
- average loan balance;
- transaction count;
- transaction volume;
- branch transaction count;
- interest income;
- interest expense;
- net interest income;
- fee income;
- total revenue;
- personnel cost;
- fixed cost;
- variable cost;
- operational cost;
- total operating cost;
- credit loss;
- pre-provision profit;
- net income;
- productivity;
- efficiency;
- profitability;
- annual management rollups;
- branch-to-bank reconciliation;
- macroeconomic context;
- external-shock context;
- market context where appropriate.

Detailed thematic diagnosis remains in the corresponding analytical modules.

---

# 2. Main Performance Tables

## Primary consolidated table

```text
performance.bank_monthly_performance
```

Grain:

```text
1 row = 1 month of consolidated BTYT performance
```

## Branch table

```text
performance.branch_monthly_performance
```

Grain:

```text
1 row = 1 branch × 1 month
```

The bank table is derived by aggregating the branch table and must reconcile to it.

## Context tables

```text
macro.macro_environment
macro.external_shocks
```

## Optional market context

```text
market.banks
market.bank_financials
market.bank_market_weights
```

---

# 3. Reporting Currency

Monetary fields in:

```text
performance.bank_monthly_performance
performance.branch_monthly_performance
```

are expressed in **UYU-equivalent reporting values**.

They can therefore be aggregated within the performance layer.

This differs from lower-level native-currency tables such as accounts, loans and transactions, where UYU and USD must remain separate unless an explicit conversion rule is applied.

---

# 4. Performance Engine V3.2

Version 3.0.0 changes the cost-generation philosophy substantially.

The previous engine produced economically coherent accounting identities, but operating costs were too concentrated around a narrow and unrealistically low Cost-to-Income outcome.

V3 does **not** fix that problem by imposing a Cost-to-Income target.

Instead, it changes the way operating costs are generated.

The new architecture is:

```text
Structural branch characteristics
        ↓
Component-specific band probabilities
        ↓
Persistent branch/component profile draw
        ↓
Long-run wage / price dynamics
        ↓
Workload + yearly cost pressure
        ↓
Independent monthly mean-reverting shock
        ↓
Realized monthly operating cost
        ↓
Profitability and efficiency KPIs
```

The resulting Cost-to-Income, margins and profitability are therefore **emergent outputs**.

They are not input targets.

---

# 5. Core Design Principle

The V3 cost engine follows one rule:

> **Structural characteristics influence probabilities, but they do not determine outcomes.**

A large branch is more likely to have higher personnel or fixed costs than a small agency.

However, this relationship is probabilistic rather than deterministic.

A large branch can still realize relatively efficient costs.

A small agency can still realize unusually high costs.

These exceptions are analytically desirable because they create meaningful management questions such as:

- Why is one large branch structurally more efficient than peers?
- Why does a small branch carry unusually high fixed costs?
- Are high variable costs explained by activity or inefficiency?
- Are unusually expensive branches persistent or temporary?
- Which branch characteristics could inform management action?

---

# 6. Four Independent Cost Components

V3 models four operating-cost components separately:

```text
personnel_cost
fixed_cost
variable_cost
operational_cost
```

Each component has:

- its own base probability distribution;
- its own structural probability adjustments;
- its own persistent band draw;
- its own within-band value draw;
- its own structural shock;
- its own monthly stochastic process.

A branch is therefore not assigned a single global label such as "cheap" or "expensive".

For example, the same branch may be:

```text
Personnel     HIGH
Fixed         LOW
Variable      VERY_HIGH
Operational   NORMAL
```

This creates multidimensional branch heterogeneity.

---

# 7. Cost Bands

The persistent cost bands are:

```text
VERY_LOW
LOW
NORMAL
HIGH
VERY_HIGH
```

The band itself is categorical.

The realized structural value is then drawn continuously inside the band's range.

Therefore, two branches assigned to the same band do not receive the same parameter.

---

# 8. Base Band Probabilities

The common starting probabilities are component-specific.

## Personnel

| Band | Base probability |
|---|---:|
| VERY_LOW | 8% |
| LOW | 20% |
| NORMAL | 44% |
| HIGH | 20% |
| VERY_HIGH | 8% |

## Fixed

| Band | Base probability |
|---|---:|
| VERY_LOW | 10% |
| LOW | 20% |
| NORMAL | 40% |
| HIGH | 20% |
| VERY_HIGH | 10% |

## Variable

| Band | Base probability |
|---|---:|
| VERY_LOW | 10% |
| LOW | 22% |
| NORMAL | 40% |
| HIGH | 20% |
| VERY_HIGH | 8% |

## Operational

| Band | Base probability |
|---|---:|
| VERY_LOW | 8% |
| LOW | 18% |
| NORMAL | 40% |
| HIGH | 24% |
| VERY_HIGH | 10% |

These are **starting probabilities**, not branch-type-specific deterministic tables.

They are subsequently tilted by branch structure and an independent component-specific shock.

---

# 9. Structural Value Ranges

## Personnel profile

Personnel values are multipliers over the branch staffing-cost base.

| Band | Multiplier range |
|---|---:|
| VERY_LOW | 0.70–0.95 |
| LOW | 0.95–1.15 |
| NORMAL | 1.15–1.55 |
| HIGH | 1.55–2.05 |
| VERY_HIGH | 2.05–2.80 |

## Fixed-cost profile

Fixed values are multipliers over the structural fixed-cost base.

| Band | Multiplier range |
|---|---:|
| VERY_LOW | 0.55–0.80 |
| LOW | 0.80–1.10 |
| NORMAL | 1.10–1.60 |
| HIGH | 1.60–2.30 |
| VERY_HIGH | 2.30–3.40 |

## Variable-cost profile

Variable values are shares of the rigid cost base before workload and cost-pressure adjustments.

| Band | Share range |
|---|---:|
| VERY_LOW | 0.12–0.25 |
| LOW | 0.25–0.45 |
| NORMAL | 0.45–0.75 |
| HIGH | 0.75–1.15 |
| VERY_HIGH | 1.15–1.80 |

## Operational-cost profile

Operational values are broad allocated technology, administration, compliance, support and other overhead shares of the rigid cost base.

| Band | Share range |
|---|---:|
| VERY_LOW | 0.75–1.25 |
| LOW | 1.25–2.00 |
| NORMAL | 2.00–3.20 |
| HIGH | 3.20–4.80 |
| VERY_HIGH | 4.80–7.00 |

These values are model inputs to cost formation.

They are **not** Cost-to-Income bands.

---

# 10. Soft Structural Correlation

Structural branch characteristics modify the base probabilities only slightly.

The probability distribution is tilted using:

- branch size;
- branch type;
- location, where economically relevant;
- an independent branch/component structural shock.

Examples:

- `LARGE` raises the probability of higher personnel-cost bands;
- `SMALL` slightly raises the probability of lower personnel-cost bands;
- `BRANCH` and `AGENCY` shift probabilities differently;
- location matters most for fixed costs;
- variable costs remain primarily activity-driven.

No structural feature forces a branch into a particular band.

---

# 11. Independent Structural Shocks

Each branch receives a different structural shock for each component.

Conceptually:

```text
branch 012

personnel structural shock   ≠
fixed structural shock       ≠
variable structural shock    ≠
operational structural shock
```

This prevents one global latent draw from making a branch mechanically:

```text
cheap in everything
```

or:

```text
expensive in everything
```

The branch can therefore exhibit mixed cost characteristics.

All draws remain deterministic under the world seed and RNG namespace, so the world is reproducible.

---

# 12. Persistent Structural Identity

A branch does **not** redraw its structural band every month.

The following elements remain persistent across the observation horizon:

- cost band;
- within-band structural value;
- monthly-process persistence parameter;
- monthly-process long-run volatility parameter.

This preserves branch identity.

A structurally expensive branch tends to remain relatively expensive, but its realized monthly cost can still fluctuate.

---

# 13. Monthly Cost Dynamics

Monthly costs are not forced to increase monotonically.

Each component has its own independent mean-reverting process in log space:

```text
log_shock_t
=
phi × log_shock_(t-1)
+ innovation_t
```

The multiplicative monthly factor is:

```text
monthly_factor_t = exp(log_shock_t)
```

Therefore:

```text
monthly_factor_t > 1
```

raises the component cost relative to its structural path, while:

```text
monthly_factor_t < 1
```

reduces it.

A monthly sequence may therefore behave like:

```text
120
123
121
125
124
128
126
```

rather than moving mechanically upward every month.

---

# 14. Component-Specific Monthly Processes

Each component receives separate persistence and volatility parameter draws.

## Personnel

```text
phi   ∈ [0.65, 0.90]
sigma ∈ [0.015, 0.040]
```

Interpretation:

- relatively persistent;
- relatively low monthly volatility;
- long-run movement still influenced by the wage index.

## Fixed

```text
phi   ∈ [0.75, 0.95]
sigma ∈ [0.020, 0.055]
```

Interpretation:

- highly persistent;
- sticky facility/infrastructure behavior;
- long-run movement influenced by the price index.

## Variable

```text
phi   ∈ [0.35, 0.70]
sigma ∈ [0.050, 0.120]
```

Interpretation:

- less persistent;
- more volatile;
- strongly linked to actual monthly workload.

## Operational

```text
phi   ∈ [0.50, 0.82]
sigma ∈ [0.035, 0.090]
```

Interpretation:

- intermediate persistence and volatility;
- captures technology, administration, compliance, support and other operating overhead dynamics.

---

# 15. Monthly Cost Formation

## Personnel cost

Conceptually:

```text
Personnel Cost
=
Staff Base
× Base Labor Cost
× Persistent Personnel Profile
× Monthly Personnel Shock
× Wage Index
× Cost-Pressure Effect
```

The structural staffing base still depends on branch size and branch type.

---

## Fixed cost

Conceptually:

```text
Fixed Cost
=
Structural Fixed Base
× Persistent Fixed Profile
× Monthly Fixed Shock
× Location Effect
× Price Index
× Cost-Pressure Effect
```

Location therefore affects both the structural base and the probabilistic environment without fully determining the realized cost.

---

## Variable cost

Variable cost is built from the rigid cost base:

```text
Rigid Base
=
Personnel Cost + Fixed Cost
```

Then:

```text
Variable Cost
=
Rigid Base
× Persistent Variable Profile
× Monthly Variable Shock
× Workload Effect
× Cost-Pressure Effect
```

The workload index uses:

```text
55% transaction count
25% branch transaction count
15% active accounts
5% active loans
```

with elasticity:

```text
VARIABLE_COST_ELASTICITY = 0.82
```

Variable cost is therefore the component most directly connected to monthly operational activity.

---

## Operational cost

Conceptually:

```text
Operational Cost
=
Rigid Base
× Persistent Operational Profile
× Monthly Operational Shock
× Cost-Pressure Effect
```

It represents broad allocated operating overhead that is not captured by payroll, fixed branch infrastructure or activity-linked variable cost.

---

# 16. Cost Pressure

The engine retains the branch/year `cost_pressure` process.

Cost pressure affects components with different sensitivities:

```text
Personnel beta    = 0.04
Fixed beta        = 0.08
Variable beta     = 0.06
Operational beta  = 0.20
```

Therefore a common branch/year pressure state does not affect all cost components equally.

---

# 17. Long-Run Wage and Price Dynamics

Personnel and fixed costs retain deterministic long-run economic indices.

This is intentional.

The indices represent macro-level cost trends, while the stochastic monthly processes introduce local deviations around those trends.

Therefore:

> a long-run upward trend does not imply that every month must be more expensive than the previous month.

---

# 18. Cost-to-Income Is an Output

The V3 engine does not contain:

```text
COST_TO_INCOME_MIN
COST_TO_INCOME_MAX
TARGET_COST_TO_INCOME
```

and does not solve costs backward from a desired efficiency ratio.

Instead:

```text
Cost-to-Income
=
Total Operating Cost / Total Revenue
```

is calculated after revenue and cost generation.

This is a critical analytical distinction.

The engine generates economic conditions.

The analytical layer observes their consequences.

---

# 19. Performance-Engine Definitions

## Active customers

Monthly relationship/activity measure derived from the account-balance layer.

Each represented customer is uniquely assigned to one branch for that month.

It is not equivalent to the cutoff field:

```text
core.customers.customer_status
```

## Active accounts

Accounts represented in the month's account-balance layer.

It is not simply:

```text
core.accounts.account_status
```

## Average deposits

Generated from monthly account balances:

```text
(opening_balance + closing_balance) / 2
```

then converted to UYU-equivalent.

## Average loan balance

Monthly outstanding loan exposure converted to UYU-equivalent.

## Transactions

Performance transaction counts and transaction volume use:

```text
COMPLETED
```

transactions only.

`branch_transaction_count` contains completed `BRANCH`-channel activity.

---

# 20. Revenue Formation

Net interest income is:

```text
Net Interest Income
=
Interest Income - Interest Expense
```

Fee income is generated from:

- transaction fees;
- card fees.

Total revenue is:

```text
Total Revenue
=
Net Interest Income + Fee Income
```

---

# 21. Credit-Loss Formation

Credit loss is produced from the credit-risk layer.

The performance engine uses:

- delinquency-based provision requirements;
- changes in required provisions;
- terminal write-off loss where applicable;
- inherited opening-state treatment for pre-2021 exposures.

Credit loss is an operating performance input but its detailed delinquency mechanics remain documented in the credit-risk analytical layer.

---

# 22. Performance Accounting Identities

The engine must satisfy:

```text
Net Interest Income
=
Interest Income - Interest Expense
```

```text
Total Revenue
=
Net Interest Income + Fee Income
```

```text
Total Operating Cost
=
Personnel Cost
+ Fixed Cost
+ Variable Cost
+ Operational Cost
```

```text
Pre-Provision Profit
=
Total Revenue - Total Operating Cost
```

```text
Net Income
=
Pre-Provision Profit - Credit Loss
```

These are accounting identities, not behavioral assumptions.

---

# 23. Stock vs Flow Semantics

## Semi-additive / snapshot-style measures

```text
active_customers
active_accounts
average_deposits
average_loan_balance
```

They may reconcile across branches for the same month.

They should not simply be summed across months.

Annual reporting should use explicit semantics such as:

- monthly average;
- year-end value.

## Additive flow measures

```text
transaction_count
transaction_volume
branch_transaction_count
interest_income
interest_expense
net_interest_income
fee_income
total_revenue
personnel_cost
fixed_cost
variable_cost
operational_cost
total_operating_cost
credit_loss
pre_provision_profit
net_income
```

These may be summed across months.

---

# 24. Branch-to-Bank Reconciliation

The consolidated bank table is built from branch-month values.

For every additive field:

```text
SUM(branch_monthly_performance)
=
bank_monthly_performance
```

subject only to the engine's rounding tolerance.

This reconciliation is a required integrity condition.

---

# 25. V3 Diagnostic Outputs

Before accepting a generated world, the engine reports the structural cost-profile distribution.

For each component it reports:

```text
number of branches in each band
profile value min / median / max
```

It also reports monthly stochastic-process diagnostics:

```text
monthly factor P10 / median / P90
phi min / median / max
sigma min / median / max
```

These diagnostics are descriptive.

They are not guardrails that force the world toward a target Cost-to-Income or profitability result.

---

# 26. Performance Integrity Checks

Before loading the regenerated outputs into PostgreSQL, verify:

- one branch-month row per branch and month;
- complete 2021–2026 coverage;
- no duplicate branch/month rows;
- non-negative required count and balance fields;
- accounting identities;
- branch-to-bank reconciliation;
- valid cost-band probabilities;
- valid within-band ranges;
- no missing monthly shock factors;
- meaningful variation in component-level monthly shock factors;
- cost-profile diversity across branches;
- no accidental UYU/USD mixing;
- no impossible branch transaction count above total transaction count.

The V3 audit should be inspected **before replacing the existing PostgreSQL performance tables**.

---

# 27. Main Management Questions

## Business scale

- How do active customers and accounts evolve?
- How do deposits and loan balances evolve?
- Does scale growth translate into stronger revenue?
- Does account growth outpace customer growth?

## Revenue

- How does total revenue evolve?
- How much comes from net interest income?
- How much comes from fees?
- Is the revenue mix changing?

## Cost structure

- How do personnel, fixed, variable and operational costs evolve?
- Which components are responsible for cost acceleration?
- Are some branches structurally more expensive than peers?
- Do exceptional branches persist over time?
- Are high variable costs explained by high workload?
- Do high fixed costs coincide with location or branch structure?

## Efficiency

- What is Cost-to-Income?
- How dispersed is Cost-to-Income across branches?
- Which branches combine high activity with relatively low cost?
- Which branches have unusual cost structures?
- Are changes in efficiency driven by revenue or costs?

## Credit risk

- How does credit loss evolve?
- How much pre-provision profit is absorbed by credit loss?
- Which periods show unusually high risk pressure?

## Profitability

- How does pre-provision profit evolve?
- How does net income evolve?
- Which months or branches are loss-making?
- Is profitability volatility driven by revenue, costs or credit losses?

## Management action

The V3 design makes it possible to investigate cases such as:

- large but efficient branches;
- small but expensive agencies;
- high fixed-cost locations;
- high workload with low variable cost;
- low workload with high operational overhead;
- branches with persistent negative profitability;
- branches with temporary cost shocks.

These patterns may motivate management hypotheses, but the analytical layer should distinguish descriptive evidence from causal claims.

---

# 28. Executive KPI Framework

## Scale

- Active Customers
- Active Accounts
- Average Deposits
- Average Loan Balance
- Transaction Count
- Transaction Volume

## Revenue

- Interest Income
- Interest Expense
- Net Interest Income
- Fee Income
- Total Revenue

## Cost

- Personnel Cost
- Fixed Cost
- Variable Cost
- Operational Cost
- Total Operating Cost

## Risk

- Credit Loss
- Credit Loss / Average Loan Balance
- Credit Loss / Pre-Provision Profit

## Profitability and efficiency

- Pre-Provision Profit
- Net Income
- Cost-to-Income
- Pre-Provision Margin
- Net Margin
- Revenue per Customer
- Net Income per Customer
- Revenue per Account
- Loan-to-Deposit Ratio
- Fee Income Share
- Branch Transaction Share

---

# 29. SQL vs DAX vs Python Boundary

## SQL

SQL should own:

- stable monthly performance grains;
- annual stock/flow rollups;
- accounting-identity audits;
- branch-to-bank reconciliation;
- reusable P&L structures;
- macro and shock context;
- structural consistency diagnostics.

## Power BI / DAX

DAX should own dynamic measures such as:

- Total Revenue;
- Net Income;
- Cost-to-Income;
- Pre-Provision Margin;
- Net Margin;
- Revenue per Customer;
- Net Income per Customer;
- Loan-to-Deposit Ratio;
- Fee Income Share;
- Credit Loss Ratio;
- MoM / YoY measures;
- rolling measures;
- YTD measures;
- filter-aware branch contribution.

Power BI should **observe** the generated performance world, not repair or recalibrate it.

## Python

Python owns:

- synthetic performance generation;
- stochastic cost-profile assignment;
- monthly mean-reverting cost processes;
- deterministic reproducibility through the world seed;
- advanced exploratory/statistical analysis where appropriate.

---

# 30. Regeneration and Refresh Workflow

When the upstream credit-risk layer changes, performance must be regenerated because `credit_loss`, interest recognition and downstream profitability depend on the loan snapshot.

Current workflow:

```text
validated BTYT source files
        ↓
generate_loans.py V5.2.0
        ↓
generate_loan_monthly_snapshot.py V4.2
        ↓
generate_branch_performance.py V3.2.0
        ↓
branch_monthly_performance.parquet
bank_monthly_performance.parquet
        ↓
performance reconciliation / validation
        ↓
PostgreSQL 23-table full refresh
        ↓
refresh analytics materialized views
        ↓
Power BI refresh
```

The 2026-10-11 performance regeneration produced:

```text
2,664 branch-month rows
72 bank-month rows
SUM(branch) == bank    PASS
VALIDATION             PASS
```

Business-result diagnostics are suppressed by default in the generator so the technical audit does not spoil the analytical findings that should be discovered in BI.

### Reproducibility condition

Before the next frozen manifest, the world seed/settings used by the performance engine must be synchronized with the active BTYT/01 world identity. See `../README.md` and `credit_risk_calibration.md`.

---

# 31. Analytical Boundary

This file should answer:

> **How is BTYT performing as a bank, how do the main components of performance evolve, and what branch-level patterns merit management investigation?**

It should not replace detailed:

- customer analysis;
- loan and delinquency analysis;
- transaction/channel analysis;
- campaign analysis;
- causal identification.

The performance layer is the **executive synthesis layer of Part I**.

---

# 32. V3 Methodological Summary

The V3 performance engine is intentionally neither purely deterministic nor unconstrained randomness.

It combines:

```text
economic structure
+ probabilistic heterogeneity
+ reproducible stochastic draws
+ time-varying operational drivers
+ persistent but mean-reverting monthly shocks
```

The objective is to create a synthetic banking world in which:

- economic relationships remain interpretable;
- branches can differ meaningfully;
- exceptional cases can occur;
- results remain reproducible;
- analytical findings are not known in advance;
- management KPIs emerge from the generated system rather than being imposed on it.

That principle is central to the BTYT Part I analytical design.
