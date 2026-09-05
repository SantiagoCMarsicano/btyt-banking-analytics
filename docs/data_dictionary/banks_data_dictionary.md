BTYT Banking Analytics

Banks Data Dictionary

Primary structural file: banks.csv Domestic temporal state:
bank_market_weights.csv Upstream shared world state:
macro_environment.csv Related temporal financial file:
bank_financials.csv Project: Banco de Treinta y Tres (BTYT) --- Banking
Analytics Status: Living implementation contract aligned with the
centralized BTYT world architecture Baseline: V3.0.7

1.  Purpose

Architecture note:

The banking layer is a downstream consumer of the canonical BTYT world
configuration and shared macro environment. Macro realization is no
longer owned by `generate_banks.py`.

V4.0.0 redesigns the banking layer so that the Uruguayan banking system
is no longer represented by one static world-level domestic weight
vector.

The V4 domestic system has an explicit temporal state covering
2021--2026.

The central design objective is to produce a banking market that:

begins from a plausible but stochastic 2021 configuration;

evolves gradually rather than independently redrawing every year;

preserves meaningful differences between institutions;

allows competitive positions to improve or deteriorate;

reacts to common macroeconomic conditions;

permits bank-specific shocks;

permits BTYT to benefit from or suffer from external conditions;

does not protect BTYT with a predetermined success path;

remains reproducible and auditable.

The V4 architecture separates four concepts that must not be conflated:

structural bank identity;

domestic competitive position through time;

transaction-counterparty selection behavior;

financial performance through time.

This is the principal conceptual change from V3.

2.  Real institutions and synthetic behavior disclaimer

BTYT is fictional.

All customers, accounts, loans, transfers, balances, transaction
amounts, relationships, market states, financial metrics, behavioral
parameters, shock parameters and stochastic paths are synthetic.

Some external bank names correspond to real financial institutions. They
are used only to provide a recognizable structural banking environment.

The project does not claim that:

simulated market weights reproduce actual Uruguayan market shares;

simulated financial statements reproduce published bank statements;

synthetic customer behavior represents actual customers;

transaction volumes reproduce observed payment flows;

behavioral affinities are empirical estimates;

simulated shocks represent actual events experienced by a named
institution;

any modeled relationship between BTYT and a real institution exists in
reality.

Public information may be used only as a broad plausibility reference.

All V4 percentage bands are simulation design bands, not empirical
estimates.

3.  V4 architectural change

V3.0.7

V3.0.7 generated one domestic vector:

\[ `\sum{=tex}`{=tex}\_i w_i = 1 \]

for the simulated world.

That vector was static.

Financial trajectories were generated separately and did not determine
the domestic competitive path.

V4.0.0

V4 introduces:

\[ w\_{i,t} \]

where:

(i) identifies the bank;

```{=html}
<!-- -->
```
(t) identifies the year;

(t `\in {=tex}{2021,\ldots{=tex},2026}`{=tex}).

Domestic competitive position is therefore a stochastic time series.

The annual state is persistent:

\[ State_t `\rightarrow{=tex}`{=tex} State\_{t+1} \]

rather than:

\[ IndependentDraw_t `\rightarrow{=tex}`{=tex} IndependentDraw\_{t+1} \]

The objective is path dependence.

4.  Banking network

BTYT BANKING NETWORK ├── BTYT │ └── BTYT │ ├── DOMESTIC COMPETITIVE
SYSTEM │ ├── BROU │ ├── Santander Uruguay │ ├── Itaú Uruguay │ ├── BBVA
Uruguay │ ├── Scotiabank Uruguay │ ├── BTYT │ ├── Citibank Uruguay │ ├──
BHU │ ├── HSBC Uruguay / BTG Pactual Uruguay │ ├── Banco Nación │ ├──
Banque Heritage Uruguay │ └── Bandes │ └── FOREIGN COUNTERPARTIES ├──
JPMorgan Chase ├── Citibank International ├── Bank of America ├──
Deutsche Bank ├── BNP Paribas ├── UBS └── HSBC International

There is no OTHER_FOREIGN_BANKS category.

5.  Stable identifiers

B000 BTYT B001-B099 DOMESTIC / URUGUAYAN SYSTEM B101-B199 FOREIGN

bank_id Current-state display name

B000 BTYT B001 BROU B002 BHU B003 Bandes B004 BBVA Uruguay B005 Banco
Nación B006 Itaú Uruguay B007 Santander Uruguay B008 Banque Heritage
Uruguay B009 Citibank Uruguay B010 BTG Pactual Uruguay B011 Scotiabank
Uruguay B101 JPMorgan Chase B102 Citibank International B103 Bank of
America B104 Deutsche Bank B105 BNP Paribas B106 UBS B107 HSBC
International

bank_id is always the relational key.

6.  B010 temporal identity

V4 preserves the V3.0.7 identity rule.

Year `bank_id` Temporal display name

2021 `B010` HSBC Uruguay 2022 `B010` HSBC Uruguay 2023 `B010` HSBC
Uruguay 2024 `B010` HSBC Uruguay 2025 `B010` HSBC Uruguay 2026 `B010`
BTG Pactual Uruguay

banks.csv remains a current-state dimension and therefore uses BTG
Pactual Uruguay.

Temporal fact tables use the historically appropriate display name.

Joins must use bank_id, never bank_name.

7.  banks.csv

banks.csv remains the structural bank dimension.

It does not store annual outcomes.

Schema

Column Type Nullable Description

bank_id string No Stable synthetic bank identifier.

bank_name string No Current-state display name.

bank_scope categorical No BTYT, DOMESTIC, or FOREIGN.

bank_type categorical No Broad institutional role.

operating_country string No Operating jurisdiction used by the
simulation.

bank_profile categorical No Structural behavioral profile.

usd_affinity decimal No Structural USD anchor.

business_affinity decimal No Structural business-customer anchor.

large_transfer_affinity decimal No Structural high-value-transfer
anchor.

The V3 fields market_weight_low and market_weight_high are no longer the
primary representation of domestic competitive position.

Annual domestic state belongs in bank_market_weights.csv.

8.  Structural bank profiles

Bank bank_profile

BTYT INTERNAL_GENERALIST BROU GENERALIST_PUBLIC_RETAIL BHU
MORTGAGE_SPECIALIST Bandes RETAIL_NICHE BBVA Uruguay
GENERALIST_RETAIL_BUSINESS Banco Nación REGIONAL_CROSS_BORDER Itaú
Uruguay GENERALIST_PREMIUM_BUSINESS Santander Uruguay
GENERALIST_RETAIL_BUSINESS Banque Heritage Uruguay PRIVATE_WEALTH
Citibank Uruguay CORPORATE_USD B010 CORPORATE_WEALTH_USD Scotiabank
Uruguay GENERALIST_RETAIL_BUSINESS JPMorgan Chase CORPORATE_TREASURY_USD
Citibank International CORPORATE_TREASURY_USD Bank of America
CORPORATE_USD Deutsche Bank CORPORATE_INTERNATIONAL BNP Paribas
CORPORATE_INTERNATIONAL UBS PRIVATE_WEALTH_INTERNATIONAL HSBC
International CROSS_BORDER_CORPORATE

Profiles influence probabilities and shock exposure.

They do not impose deterministic customer-bank relationships.

9.  Domestic competitive system

9.1 Definition

The V4 domestic competitive system contains:

BTYT;

the eleven modeled external banks operating in Uruguay.

For each year:

\[ `\sum{=tex}{i \in {=tex}UruguaySystem}`{=tex} w{i,t}=1 \]

with:

\[ 0 \< w\_{i,t} \< 1 \]

The resulting quantity is called market_weight.

It is a synthetic competitive-position measure calibrated to look
broadly plausible.

It must not be described as an observed real-world market share.

9.2 2021 initialization

The 2021 state is generated by the DGP.

The final 2021 vector must not be manually entered.

The design bands are:

Bank 2021 low 2021 center 2021 high

BROU 24.0% 30.0% 36.0% Santander Uruguay 10.0% 15.0% 21.0% Itaú Uruguay
10.0% 14.0% 21.0% BBVA Uruguay 6.0% 10.0% 15.0% Scotiabank Uruguay 6.0%
9.0% 14.0% BTYT 2.5% 5.0% 8.0% Citibank Uruguay 1.5% 4.0% 7.0% BHU 1.5%
3.0% 6.0% B010 1.0% 3.0% 6.0% Banco Nación 1.0% 2.5% 5.0% Banque
Heritage Uruguay 0.5% 2.0% 4.0% Bandes 0.5% 1.5% 3.5%

The centers are preference anchors, not a vector that is copied directly
into the output.

2021 leadership rule

BROU is structurally expected to begin as the largest institution.

However, the exact 2021 values still emerge from the DGP.

The initialization routine must preserve stochastic variation while
producing a credible initial banking structure.

The other major private banks are not assigned a permanently fixed
ranking.

10. Latent competitive state

Directly applying an AR process to bounded shares is awkward because
shares must remain positive and sum to one.

V4 therefore evolves a latent competitive state:

\[ z\_{i,t} \]

and maps that state into annual shares through a softmax transformation.

For each domestic bank:

\[ z\_{i,t} = `\mu{=tex}`{=tex}\_i +
`\phi{=tex}`{=tex}i(z{i,t-1}-`\mu{=tex}`{=tex}\_i) +
`\beta{=tex}`{=tex}i M_t + `\gamma{=tex}`{=tex}i S_t +
`\delta{=tex}{i,t}`{=tex} + `\epsilon{=tex}{i,t}`{=tex} \]

where:

(`\mu{=tex}`{=tex}\_i) = bank-specific long-run competitive anchor;

(`\phi{=tex}`{=tex}\_i) = persistence;

(M_t) = macro environment;

(S_t) = systemic banking shock;

(`\beta{=tex}`{=tex}\_i) = macro sensitivity;

(`\gamma{=tex}`{=tex}\_i) = systemic-shock sensitivity;

(`\delta{=tex}`{=tex}\_{i,t}) = bank-specific shock;

(`\epsilon{=tex}`{=tex}\_{i,t}) = ordinary idiosyncratic innovation.

Annual market weights are:

\[ w\_{i,t} = `\frac{\exp(z_{i,t})}{=tex}`{=tex} {`\sum{=tex}`{=tex}j
`\exp{=tex}`{=tex}(z{j,t})} \]

This guarantees:

\[ w\_{i,t}\>0 \]

and:

\[ `\sum{=tex}`{=tex}i w{i,t}=1 \]

without naive normalization of independently bounded draws.

11. Persistence

The banking system should evolve slowly enough to remain recognizable.

V4 uses persistent AR-style dynamics.

Conceptually:

high persistence + moderate ordinary noise + occasional larger shocks =
stable structure with meaningful movement

The persistence parameter must be materially above zero and below one.

The implementation should draw bank-level persistence from a controlled
high-persistence range rather than assigning one identical coefficient
to every institution.

A previous year's competitive position therefore matters strongly for
the next year.

V4 explicitly rejects independent annual redraws.

12. Mean reversion

Without mean reversion, random shocks can permanently push a bank toward
implausible dominance or disappearance.

The term:

\[ `\phi{=tex}`{=tex}i(z{i,t-1}-`\mu{=tex}`{=tex}\_i) \]

creates persistence while pulling the latent state toward a structural
anchor.

Mean reversion must be gradual.

A one-year adverse shock may therefore affect several subsequent years
without becoming permanently deterministic.

13. Ordinary innovations

Each bank receives a small annual innovation:

\[ `\epsilon{=tex}`{=tex}\_{i,t} `\sim`{=tex}{=tex}
N(0,`\sigma{=tex}`{=tex}\_i) \]

The innovation represents ordinary competitive uncertainty not
explicitly attributed to a named event.

Volatility may differ by profile.

Large generalist institutions should generally be less volatile than
small or specialized institutions.

The ordinary innovation must remain materially smaller than a major
shock.

14. Macro environment

The macro environment is a world-level exogenous state generated
upstream of the banking layer.

Canonical source:

`data/generated/world/macro_environment.csv`

Canonical generator:

`scripts/generators/generate_macro_environment.py`

The banking generator does not generate or own this table. It consumes
the same realized macro state that may also be consumed by other
downstream systems such as branches.

The macro environment is shared across institutions, while bank-specific
sensitivities determine heterogeneous downstream effects.

Conceptually:

\[ M_t ightarrow Bank\_{i,t}=f(M_t,arepsilon\^{bank}\_{i,t}) \]

This preserves the BTYT causal principle: shared causal conditions may
influence multiple processes, while downstream realizations use
independent stochastic streams.

The macro variables are synthetic latent drivers. They are not intended
to reproduce historical Uruguayan macroeconomic series.

The detailed schema, stochastic process, RNG stream, validation rules
and ownership contract are documented in:

`docs/data_dictionary/macro_environment_data_dictionary.md`

15. Shock architecture

V4 distinguishes three mechanisms.

15.1 Ordinary idiosyncratic noise

Small and frequent.

Already represented by:

\[ `\epsilon{=tex}`{=tex}\_{i,t} \]

15.2 Systemic shock

A systemic shock affects several banks in the same year.

Its effect is heterogeneous:

\[ Effect\_{i,t}\^{systemic} = `\gamma{=tex}`{=tex}\_i S_t \]

A common event therefore does not need to benefit or hurt every
institution equally.

15.3 Bank-specific shock

A bank may receive an additional signed shock:

\[ `\delta{=tex}`{=tex}\_{i,t} \]

Possible synthetic interpretations include:

successful commercial strategy;

operational disruption;

reputational event;

acquisition/integration effect;

technology investment;

credit-quality deterioration;

corporate-client gain/loss;

funding pressure.

The dataset does not need to assign a real-world historical event to a
real institution.

Shock interpretation remains synthetic.

16. Shock sparsity

Major shocks must be uncommon.

If every bank experiences a large shock every year, the process stops
behaving like a persistent banking system and becomes noise.

The intended hierarchy is:

ordinary annual innovation common material bank-specific shock
occasional large bank-specific shock rare systemic stress episode
occasional / rare

Most annual movement should therefore come from persistence, mean
reversion and ordinary innovations.

17. BTYT treatment

BTYT participates in the domestic competitive system.

Its 2021 position is small but non-trivial.

BTYT has no plot armor.

The model must allow:

\[ `\Delta {=tex}`{=tex}w\_{BTYT,t} \> 0 \]

and:

\[ `\Delta {=tex}`{=tex}w\_{BTYT,t} \< 0 \]

depending on the generated world.

BTYT may:

gain from favorable macro conditions;

lose from unfavorable conditions;

gain when competitors suffer;

lose when competitors outperform;

benefit from its own positive idiosyncratic shock;

suffer an operational or credit shock;

experience temporary gains that later mean-revert;

experience a persistent deterioration.

There is no hard-coded requirement that BTYT finishes 2026 larger than
it was in 2021.

There is no hard-coded heroic growth trajectory.

This is a frozen V4 principle.

18. Relative competition

Because annual market weights are produced by softmax, competition is
relative.

If one bank receives a strong positive innovation, its weight can rise
even if the latent state of every other institution remains unchanged.

Likewise, BTYT can gain share because:

BTYT improves;

competitors deteriorate;

both occur.

This creates a useful synthetic competitive system rather than twelve
independent growth series.

19. Domestic leadership through time

2021 establishes a plausible initial hierarchy.

2022--2026 are generated dynamically.

The DGP does not manually choose the leader in each later year.

Leadership is an outcome.

A large bank may remain the leader for the entire period.

A competitor may narrow the gap.

Under sufficiently strong accumulated dynamics or shocks, leadership may
change.

Such a change should be possible but not mechanically common.

20. bank_market_weights.csv

20.1 Purpose

This table stores the annual realized domestic competitive state.

Grain

one row per domestic-system bank per year

Primary key

(bank_id, year)

Schema

Column Type Nullable Description

bank_id string No Stable bank identifier.

bank_name string No Historically appropriate display name.

year integer No 2021--2026.

market_weight decimal No Realized synthetic domestic competitive weight.

latent_competitive_state decimal No Latent state before softmax.

long_run_anchor decimal No Bank-specific latent/competitive anchor.

persistence decimal No Bank-specific AR persistence.

macro_effect decimal No Contribution from macro conditions.

systemic_shock_effect decimal No Contribution from systemic shock.

bank_shock_effect decimal No Bank-specific material shock contribution.

idiosyncratic_innovation decimal No Ordinary annual innovation.

is_bank_shock boolean No Material bank-specific shock flag.

is_systemic_shock boolean No Systemic-shock-year flag.

world_seed integer No Synthetic world seed.

The decomposition is intentionally stored to make the DGP auditable.

21. macro_environment.csv --- upstream dependency

`macro_environment.csv` is no longer a banking-layer output.

It is generated once at world level and consumed by `generate_banks.py`.

Grain:

one row per year

Primary key:

`year`

Canonical path:

`data/generated/world/macro_environment.csv`

The bank generator must validate that the macro table covers every
configured observation year before using it.

The banking layer consumes, but does not redefine, the following shared
fields:

-   `macro_growth_factor`
-   `credit_cycle_factor`
-   `usd_pressure_factor`
-   `financial_stress_factor`
-   `digitalization_factor`
-   `cross_border_factor`
-   `systemic_shock`
-   `systemic_shock_flag`
-   `world_seed`

The authoritative schema and DGP belong to
`macro_environment_data_dictionary.md`.

22. Foreign bank weights

Foreign counterparties remain separate from the domestic competitive
model.

V4 does not force the foreign network into the domestic AR process.

The V3 symmetric foreign mechanism remains a valid baseline:

\[ (w_1,`\ldots`{=tex}{=tex},w_7) `\sim`{=tex}{=tex}
Dirichlet(`\alpha{=tex}`{=tex},`\ldots`{=tex}{=tex},`\alpha{=tex}`{=tex})
\]

with:

\[ `\alpha{=tex}`{=tex}\_{world} `\sim`{=tex}{=tex} Uniform(2.5,6.0) \]

All foreign institutions therefore begin with equal prior expected
selection weight.

Foreign weight is a counterparty-selection parameter, not a synthetic
share of the Uruguayan banking market.

23. Market weight is not transaction share

This distinction remains fundamental.

Domestic market_weight represents competitive prominence.

Actual transfer-bank selection remains conditional.

Conceptually:

\[ score\_{i,t} = market_weight\_{i,t} `\times{=tex}`{=tex}
currency_fit_i `\times{=tex}`{=tex} customer_fit_i `\times{=tex}`{=tex}
amount_fit_i `\times{=tex}`{=tex} behavioral_fit_i \]

and:

\[ P(bank=i `\mid {=tex}`{=tex}transfer,t) =
`\frac{score_{i,t}}{=tex}`{=tex} {`\sum{=tex}`{=tex}j score{j,t}} \]

Therefore a bank may have:

a lower market weight but a high USD-transfer share;

a lower transaction count but high transferred value;

a strong business-client share;

a strong high-value-transfer share;

a strong mortgage-payment role.

Competitive size and behavioral specialization remain separate.

24. Behavioral affinities

V4 retains:

usd_affinity;

business_affinity;

large_transfer_affinity.

They remain 0--1 structural anchors and not direct probabilities.

The V3 world-level perturbation mechanism may continue to be used:

\[ a\_{i,k}\^{world} =
clip(a\_{i,k}\^{base}+`\eta{=tex}`{=tex}\_{i,k},0,1) \]

with controlled zero-centered noise.

Affinities should remain stable enough for bank profiles to remain
recognizable.

25. Structural behavioral interpretation

BROU

broad public/generalist profile;

largest structural 2021 center;

diversified individual/business compatibility;

moderate USD affinity;

relatively low competitive volatility.

Santander Uruguay

major retail/business generalist;

meaningful business exposure;

broad transaction compatibility.

Itaú Uruguay

major generalist;

premium/high-income and business compatibility;

stronger USD affinity.

BBVA Uruguay

retail/business generalist;

balanced currency/customer profile.

Scotiabank Uruguay

retail/business generalist;

broad compatibility.

BTYT

smaller generalist institution;

meaningful but non-dominant 2021 presence;

can gain or lose competitively;

financial path increasingly linked to its own generated activity.

Citibank Uruguay

corporate orientation;

strong USD affinity;

strong large-transfer affinity.

BHU

mortgage specialist;

lower general-purpose transfer relevance;

recurrent mortgage-like payment behavior.

B010

corporate / wealth / USD orientation;

temporal identity changes from HSBC Uruguay to BTG Pactual Uruguay while
bank_id remains stable.

Banco Nación

regional / cross-border profile;

stronger compatibility with Argentina-related behavior.

Banque Heritage Uruguay

private wealth;

high-value individual compatibility;

strong USD and large-transfer affinities relative to size.

Bandes

niche retail;

smaller structural competitive position.

26. BHU temporal behavior

The V3 BHU mechanism remains available.

A salary receipt may temporarily increase the probability of a
BHU-linked outgoing payment:

\[ SalaryReceipt_t `\rightarrow{=tex}`{=tex} P(BHUPayment\_{t+1+7})
`\uparrow{=tex}`{=tex} \]

This remains probabilistic.

27. Transfer scope

Allowed values remain:

Value Meaning

INTERNAL Transfer between BTYT customers.

DOMESTIC_EXTERNAL External transfer involving another domestic bank.

For non-transfer transaction types, transfer_scope is null.

28. Counterparty bank rules

BTYT_CUSTOMER → counterparty_bank_id = B000 → transfer_scope = INTERNAL

OTHER_BANK + domestic institution → counterparty_bank_id = B001-B011 →
transfer_scope = DOMESTIC_EXTERNAL

OTHER_BANK + foreign institution → counterparty_bank_id = B101-B107 →
transfer_scope = INTERNATIONAL

counterparty_type remains the economic relationship.

counterparty_bank_id remains the modeled institution.

They are not interchangeable.

29. Internal vs external mechanics

Internal BTYT transfers remain two-leg atomic events.

External institutions remain outside the BTYT ledger universe.

An external transfer therefore generates only the BTYT-side ledger leg.

30. bank_world_parameters.csv

The V3 world-parameter table remains useful for parameters that are
constant for the generated world.

It should no longer be used as the sole source of domestic competitive
weight because V4 market weights vary by year.

It may retain:

Column Meaning

world_seed Global world seed.

bank_id Stable bank identifier.

bank_name Current-state display name.

realized_usd_affinity World-specific USD affinity.

realized_business_affinity World-specific business affinity.

realized_large_transfer_affinity World-specific large-transfer affinity.

foreign_selection_weight Foreign counterparty weight when applicable.

foreign_dirichlet_alpha Foreign concentration parameter.

affinity_noise_sd World affinity-noise parameter.

Domestic temporal market state belongs in bank_market_weights.csv.

31. bank_financials.csv

31.1 Grain

(bank_id, year)

Years:

2021 2022 2023 2024 2025 2026

31.2 Schema

Column Type Nullable Description

bank_id string No Stable bank identifier.

bank_name string No Historically appropriate annual display name.

year integer No Financial year.

revenue decimal No Synthetic annual operating revenue.

operating_costs decimal No Synthetic operating costs.

net_income decimal No Synthetic annual net income.

total_assets decimal No Synthetic year-end assets.

total_deposits decimal No Synthetic year-end deposits.

total_loans decimal No Synthetic gross loan portfolio.

equity decimal No Synthetic year-end equity.

32. Financial-market linkage

V3 generated financial trajectories largely independently from the
domestic competitive-weight vector.

V4 introduces partial linkage.

For domestic institutions, annual financial growth should depend partly
on:

previous financial state;

bank profile;

macro environment;

change in competitive position;

bank-specific shock;

financial-stress exposure;

ordinary financial innovation.

Conceptually:

\[ AssetGrowth\_{i,t} = g_i + `\lambda{=tex}`{=tex}i
`\Delta {=tex}`{=tex}MarketWeight{i,t} + `\theta{=tex}`{=tex}i Macro_t +
`\kappa{=tex}`{=tex}i Shock{i,t} + u{i,t} \]

The relationship is partial, not mechanical.

A one-percentage-point increase in competitive weight must not translate
deterministically into a fixed amount of asset growth.

The purpose is correlated realism, not accounting identity.

33. Shock transmission to financials

A competitive shock and a financial shock may be related without being
identical.

For example, synthetic stress may:

reduce competitive weight;

reduce loan growth;

increase credit losses;

increase funding costs;

compress net income.

A positive strategic shock may:

increase competitive weight;

increase deposits;

increase revenue;

temporarily increase operating costs due to expansion.

The generator should allow heterogeneous transmission by profile.

34. BTYT financials

BTYT remains special because its financial path can increasingly connect
to its own synthetic banking activity.

Where feasible:

interest income + fee income + other operating income - deposit
interest - operating expenses - credit losses = net income

V4 should combine:

generated BTYT accounts / balances / loans / transactions;

the macro environment;

BTYT's competitive trajectory;

BTYT-specific shocks;

residual world-level financial parameters for components not explicitly
modeled.

BTYT must not receive an automatic profitability advantage.

A bad world can produce weaker BTYT financial performance.

35. Derived analytical metrics

Derived ratios should remain outside the source CSV where practical.

Cost-to-income

\[ CostToIncome = `\frac{operating\_costs}{revenue}{=tex}`{=tex} \]

ROA

\[ ROA = `\frac{net\_income}{average\ total\ assets}{=tex}`{=tex} \]

ROE

\[ ROE = `\frac{net\_income}{average\ equity}{=tex}`{=tex} \]

Loan-to-deposit

\[ LTD = `\frac{total\_loans}{total\_deposits}{=tex}`{=tex} \]

Net margin

\[ NetMargin = `\frac{net\_income}{revenue}{=tex}`{=tex} \]

These should preferably be calculated downstream in SQL, Power BI,
Tableau, Superset or Python.

36. Reproducibility and RNG architecture

V4 preserves the V3.0.7 principle of independent deterministic RNG
streams.

A single WORLD_SEED defines the world.

Separate stable streams should be used for modules such as:

2021 domestic initialization domestic temporal dynamics systemic shocks
bank-specific shocks foreign weights behavioral affinities financial
generation

Changing one stochastic module should not silently change unrelated
random draws.

The exact stream IDs belong to the implementation contract in
scripts/generators/generate_banks.py.

37. Validation --- structural tables

banks.csv

Validate:

unique bank_id;

unique current-state bank_name;

valid scope;

valid type;

valid profile;

valid status;

affinities in \[0,1\];

B010 current-state name = BTG Pactual Uruguay.

Temporal identity

Validate:

B010 + 2021-2025 → HSBC Uruguay B010 + 2026 → BTG Pactual Uruguay

38. Validation --- 2021 domestic state

For every generated world:

every domestic-system weight is positive;

weights sum to one;

the generated structure respects the intended initialization
bands/constraints;

BROU begins in the structural top tier and the initialization remains
plausible;

BTYT begins as a smaller but meaningful institution;

no manual final vector is injected after generation;

no bank receives an impossible share.

The 2021 vector must emerge from the stochastic initialization
algorithm.

39. Validation --- temporal dynamics

For every year 2022--2026:

\[ `\sum{=tex}`{=tex}i w{i,t}=1 \]

and:

\[ w\_{i,t}\>0 \]

Audit:

annual absolute changes;

rank changes;

leader persistence;

BTYT gains and losses;

shock-year jumps;

post-shock mean reversion;

pathological concentration;

near-zero institutions;

excessive year-to-year reshuffling.

A valid model should produce persistence without complete determinism.

40. Cross-world audit

V4 must be audited across many lightweight worlds before production use.

A 10,000-world audit is appropriate for the domestic competitive engine.

Inspect at minimum:

2021 weight distribution by bank;

mean / median / P05 / P95;

2021 ranking frequencies;

leader frequency;

top-three frequency;

2026 ranking distribution;

probability of each bank gaining/losing;

BTYT 2021--2026 change distribution;

largest annual gain;

largest annual loss;

number of leadership changes;

persistence of ranks;

concentration metrics;

shock frequencies;

market response conditional on shocks;

boundary or pathological states;

financial-growth distributions;

profitability distributions;

relationship between competitive change and financial change.

The audit is part of model design, not an optional cosmetic report.

41. Desired qualitative behavior

Across worlds, V4 should generally produce:

Stable features

BROU usually begins as the largest institution;

Santander and Itaú form a major private-bank tier;

BBVA and Scotiabank remain significant generalists;

BTYT begins smaller;

specialized institutions remain smaller in broad competitive weight;

bank profiles remain recognizable.

Variable features

ordering among private banks;

exact 2021 shares;

annual gains and losses;

BTYT trajectory;

shock timing;

shock beneficiaries;

shock losers;

profitability;

asset growth;

eventual 2026 ranking.

The system should look like the same banking ecosystem across worlds,
but not the same history.

42. V4 design philosophy

Structure without scripted history

The DGP knows structural differences between banks.

It does not know the complete 2021--2026 story in advance.

Persistence without immobility

Previous states matter strongly, but change remains possible.

Shocks without chaos

Large shocks exist but are sparse.

Competition is relative

One bank's gain can alter every other bank's share through the softmax
system.

BTYT is endogenous

BTYT can win or lose.

Market position and transaction behavior differ

Competitive weight is not transaction share.

Financials and competition are connected but not identical

Correlated paths are preferred over deterministic identities.

Auditability is mandatory

Latent state and shock components should be recoverable from generated
outputs.

43. V4.0.0 frozen decisions

The following decisions are frozen for the V4.0.0 implementation:

V3.0.7 is the baseline.

bank_id remains the stable relational key.

B010 remains one stable bank identity.

B010 displays as HSBC Uruguay in 2021--2025 and BTG Pactual Uruguay in
2026.

banks.csv remains a current-state structural dimension.

domestic competitive position becomes annual for 2021--2026.

BTYT enters the domestic competitive system.

the 2021 domestic state is generated by the DGP rather than manually
fixed.

2021 uses realistic-plausibility bands and structural centers.

BROU has the largest structural 2021 center at 30%.

the major private-bank tier is led structurally by Santander and Itaú
centers, but later ranking is not scripted.

2022--2026 evolve through a persistent AR(1)-style latent process.

annual shares are obtained through softmax.

annual domestic weights sum to one.

annual domestic states are path-dependent.

independent annual redraws are prohibited.

mean reversion is required.

ordinary bank-level innovations are required.

systemic shocks are allowed.

bank-specific shocks are allowed.

material shocks are sparse.

macro conditions are common but bank sensitivities differ.

BTYT may benefit from external shocks.

BTYT may suffer from external shocks.

BTYT is not guaranteed to grow.

BTYT is not guaranteed to finish 2026 above its 2021 position.

domestic competitive weight is not transaction share.

foreign stochastic weights remain a separate selection mechanism.

foreign counterparties do not enter the domestic AR system.

behavioral affinities remain separate from competitive weight.

bank_market_weights.csv stores annual domestic competitive state.

macro_environment.csv stores shared annual world-level macro/shock state
and is generated upstream of the banking layer.

bank_world_parameters.csv stores world-level parameters that are not
annual domestic market states.

domestic financial trajectories are partially linked to competitive
dynamics and macro conditions.

BTYT financials should increasingly connect to its own generated banking
activity.

all named external financial values remain synthetic.

independent deterministic RNG streams remain mandatory.

V4 requires cross-world simulation auditing before production
generation.

no real institution is assigned synthetic misconduct or a real
historical shock.

no OTHER_FOREIGN_BANKS category is introduced.

44. Implementation target

The implementation file is:

scripts/scripts/generators/generate_banks.py

The intended banking-layer generation order is:

1.  load the canonical world configuration
2.  load and validate the upstream `macro_environment.csv`
3.  build the structural banks dimension
4.  generate world-level bank structural parameters
5.  generate the 2021 domestic competitive state
6.  generate systemic and bank-specific banking shocks
7.  evolve domestic latent competitive states through 2022-2026
8.  convert latent states to annual market weights
9.  generate foreign counterparty weights
10. generate realized behavioral affinities
11. generate financial trajectories linked to the banking state and
    shared macro environment
12. validate all banking tables
13. save banking outputs
14. run cross-world banking audits

At full-project level, this generator is intended to be invoked by
`scripts/generate_btyt.py` after the macro environment has been
generated.

The V4 generator should be implemented only after this contract is

treated as the source of truth.

This document is the banking-layer source of truth and must evolve with
the canonical implementation.
