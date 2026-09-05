# BTYT — Cards Data Dictionary

## Table: `cards`

**Description:**  
Master table containing debit and credit card relationships issued by BTYT to its customers.

**Grain:**  
One row represents one unique BTYT card relationship.

**Primary key:**  
`card_id`

**Purpose:**  
Represent contractual card relationships between BTYT customers and the card products defined in `products.csv`, including debit, Classic credit and Premium credit cards.

A row represents the continuing card relationship and **not each physical plastic card**. Expiration, renewal, replacement after loss or damage, or periodic reissuance of the physical card does not create a new row while the underlying relationship remains active.

**Included products:**

- `P009` — Debit Card
- `P010` — Classic Credit Card
- `P011` — Premium Credit Card

**Product metadata:**

| product_id | product_name | target_customer_type | launch_year |
|---|---|---|---:|
| `P009` | Debit Card | `BOTH` | 1996 |
| `P010` | Classic Credit Card | `INDIVIDUAL` | 1993 |
| `P011` | Premium Credit Card | `INDIVIDUAL` | 2008 |

**Excluded relationships:**

- Deposit and transactional accounts are represented in `accounts`.
- Loans are represented in `loans`.
- Credit limits, balances, utilization, minimum payments and delinquency are not stored here; those belong to `credit_card_monthly_snapshot`.
- Purchases and other card transactions are not stored here; those belong to the relevant transaction tables.

---

# Variables

## `card_id`

**Description:**  
Unique internal identifier assigned to each BTYT card relationship.

**Data type:**  
String

**Format:**  
`K` followed by seven numeric digits.

**Examples:**

- `K0000001`
- `K0000002`
- `K0125487`

**Rules:**

- Must be unique.
- Must not be NULL.
- Is the primary key of `cards`.
- Must remain unchanged throughout the lifetime of the relationship.
- Must not encode customer, product, branch, currency, status or other business information.
- Closed card relationships retain their original `card_id`.
- It is a synthetic internal BTYT identifier and must not represent a realistic payment-card number.

---

## `customer_id`

**Description:**  
Identifier of the BTYT customer to whom the card is issued.

**Data type:**  
String

**Reference:**  
Foreign key to `customers.customer_id`.

**Rules:**

- Must not be NULL.
- Must reference an existing customer.
- One customer may hold multiple card relationships.
- A customer may hold different card products simultaneously.
- `issue_year >= customers.registration_year`.
- Product ownership must be compatible with `products.target_customer_type`.
- Historical closed cards remain associated with the original customer.
- A customer with `customer_status = CLOSED` must not retain any `ACTIVE` card after the end of the customer relationship.

---

## `product_id`

**Description:**  
Identifier of the card product.

**Data type:**  
String

**Reference:**  
Foreign key to `products.product_id`.

**Allowed values:**

- `P009`
- `P010`
- `P011`

**Rules:**

- Must not be NULL.
- Only products belonging to product family `CARD` may appear.
- `P009` may be held by `INDIVIDUAL` or `BUSINESS` customers.
- `P010` may be held only by `INDIVIDUAL` customers.
- `P011` may be held only by `INDIVIDUAL` customers.
- `issue_year` must not precede the product's `launch_year`.
- Holding one card product does not automatically imply ownership of another.
- Classic and Premium may coexist.
- Premium ownership does not require prior Classic ownership.

---

## `linked_account_id`

**Description:**  
Identifier of the deposit or transactional account supporting a debit-card relationship.

**Data type:**  
String / NULL

**Reference:**  
Foreign key to `accounts.account_id`.

**Rules:**

For `P009`:

- Must not be NULL.
- Must reference an existing account.
- The account must belong to the same `customer_id`.
- Eligible linked-account products are:
  - `P001` Savings Account UYU
  - `P002` Savings Account USD
  - `P003` Current Account UYU
  - `P004` Current Account USD
  - `P005` Payroll Account
  - `P006` Youth / Student Account
- `P007` and `P008` fixed-term deposits are not eligible.
- `issue_year >= accounts.opening_year`.
- At most one P009 relationship may be generated for the same `linked_account_id`.
- A customer may nevertheless hold multiple debit cards when they are linked to different eligible accounts.
- An `ACTIVE` debit card cannot outlive its linked account.
- If the linked account closes, the debit relationship must close no later than the account closure.

For `P010` and `P011`:

- Must be NULL.
- Credit-card relationships are modeled independently from deposit accounts.
- Any account used operationally to pay a credit-card statement is outside the scope of this field.

---

## `issue_year`

**Description:**  
Year in which the BTYT card relationship was first issued.

**Data type:**  
Integer

**Format:**  
YYYY

**Rules:**

- Must not be NULL.
- Must be `<= 2026`.
- Must satisfy `issue_year >= customers.registration_year`.
- Must satisfy `issue_year >= products.launch_year`.
- For P009, must also satisfy `issue_year >= linked account opening_year`.
- Represents the start of the relationship, not physical-card replacement.
- Historical issuance must be non-uniform.

**Temporal generation principle:**

BTYT uses a compressed-history architecture:

- **Before 2021:** generate a plausible inherited historical state rather than a complete annual behavioral biography.
- **2021–2026:** model issuance and closure as explicit annual events.

For debit cards, issuance should usually occur close to account opening but may occur later.  
For credit cards, issuance may occur at registration or after the customer relationship develops.

---

## `card_status`

**Description:**  
Current status of the card relationship.

**Data type:**  
String / Categorical

**Allowed values:**

- `ACTIVE`
- `CLOSED`

**Rules:**

- Must not be NULL.
- Represents the card relationship, not the physical card.
- Renewal or replacement of plastic does not change `card_status`.
- An active customer may have both active and closed historical cards.
- A closed customer cannot retain an active card.
- Closure of one card does not imply closure of another card, an account or the customer.
- Classic and Premium cards may coexist.
- For P009, status must remain temporally consistent with `linked_account_id`.

---

## `closing_year`

**Description:**  
Year in which the card relationship was permanently terminated.

**Data type:**  
Integer / NULL

**Format:**  
YYYY / NULL

**Rules:**

- Must be NULL when `card_status = ACTIVE`.
- Must be non-NULL when `card_status = CLOSED`.
- Must satisfy `closing_year >= issue_year`.
- Must satisfy `closing_year <= 2026`.
- If the customer is closed, `closing_year <= customers.closing_year`.
- For P009 linked to a closed account, `closing_year <= accounts.closing_year`.
- Represents permanent relationship closure, not expiration or renewal of the plastic card.
- Card closure does not imply customer churn.

---

## `issue_channel`

**Description:**  
Commercial or operational channel through which the card relationship was originally issued.

**Data type:**  
String / Categorical

**Allowed values:**

- `BRANCH`
- `REMOTE_ASSISTED`
- `DIGITAL`

**Rules:**

- Must not be NULL.
- Refers to the original issuance channel.
- Must not be changed when the customer later uses another service channel.
- Channel probabilities vary over historical time.
- `BRANCH` dominates older vintages.
- `REMOTE_ASSISTED` becomes increasingly relevant before full digital adoption.
- `DIGITAL` grows strongly in recent years.
- `digital_affinity` has a strong probabilistic effect on channel choice.
- Product-specific differences are allowed:
  - P009 may retain relatively more branch issuance.
  - P010 may migrate more rapidly toward digital issuance.
  - P011 may retain relatively more assisted issuance than P010.
- Exact channel shares must emerge from generation rather than from hard quotas.

---

# Synthetic generation architecture

## Observation window

The cards DGP follows the BTYT temporal simplification:

### PRE-2021 STATE

For card relationships originating before 2021:

1. determine whether a plausible historical relationship existed;
2. assign a coherent `issue_year`;
3. determine whether the relationship survived into 2021;
4. if it did not survive, assign a coherent historical `closing_year`;
5. if it survived, carry it into 2021 as inherited active state.

The generator must not reconstruct detailed annual customer behavior before 2021.

### 2021–2026 EVENTS

From 2021 onward, issuance and closure events are modeled annually.

---

# Debit-card generation — P009

Debit-card ownership is generated from eligible account relationships rather than directly from the customer alone.

For each eligible account \(a\) belonging to customer \(i\):

\[
P(Debit_{ia}=1)=\sigma(z^{debit}_{ia})
\]

where a first-pass score may include:

\[
z^{debit}_{ia}
=
\alpha_{product}
+\beta_1 RelationshipDepth_i
+\beta_2 DigitalAffinity_i
-\beta_3 Saturation_i
+\epsilon_{ia}
\]

### Relative base propensity

Expected qualitative ordering:

1. `P005` Payroll Account — very high
2. `P003` Current Account UYU — very high
3. `P006` Youth / Student Account — high
4. `P001` Savings Account UYU — high
5. `P004` Current Account USD — high
6. `P002` Savings Account USD — moderate-high

The first debit card should have a very high probability for customers with an active eligible transactional account.

Additional debit cards should remain possible but become progressively less likely when the customer already holds active debit relationships.

A smooth saturation term is preferred over hard deterministic limits.

`credit_appetite` must **not** determine debit-card ownership.

---

# Persistent latent variable: `credit_appetite`

`credit_appetite` is an internal, non-exported latent variable on a normalized `[0,1]` scale.

**Meaning:**  
Persistent preference or propensity to adopt and use revolving/card credit.

**It does not represent:**

- creditworthiness;
- default probability;
- delinquency risk;
- financial distress;
- income itself;
- a hidden deterministic risk score.

Conceptually:

\[
CreditAppetite_i=\sigma(z_i)
\]

with a score influenced probabilistically by:

- lifecycle / age profile — moderate;
- employment status — moderate;
- log-transformed standardized income — weak to moderate;
- relationship depth — moderate;
- digital affinity — weak to moderate;
- strong idiosyncratic persistent noise.

The idiosyncratic component must remain substantial so customers with similar socioeconomic profiles may have very different credit appetite.

A high-income customer may have low credit appetite.  
A medium-income customer may have high credit appetite.

The latent may later be reused in:

- credit-card ownership;
- probability of additional credit cards;
- utilization behavior;
- credit-card transaction frequency.

It must not be used as a default-risk score.

---

# Credit-card acquisition — P010 and P011

Credit-card acquisition is generated at customer level.

For a customer-year opportunity:

\[
P(NewCredit_{i,t}=1)=\sigma(z^{credit}_{i,t})
\]

The acquisition score should depend probabilistically on:

- `credit_appetite` — strongest persistent signal;
- standardized log income — moderate;
- relationship depth — moderate;
- customer tenure — weak to moderate;
- employment/lifecycle — moderate;
- annual idiosyncratic noise — substantial;
- saturation from existing active credit cards — negative.

The DGP must not enforce a predetermined aggregate share of customers with credit cards.

Calibration should adjust intercepts only when the emergent distribution is clearly implausible.

---

# Classic vs Premium selection

Conditional on credit-card issuance, product selection is probabilistic.

Define latent utilities:

\[
U_{Classic}
=
\alpha_C
+\beta_{CA,C}CreditAppetite
+\beta_{Inc,C}Income
+\beta_{Rel,C}Relationship
+\epsilon_C
\]

\[
U_{Premium}
=
\alpha_P
+\beta_{CA,P}CreditAppetite
+\beta_{Inc,P}Income
+\beta_{Rel,P}Relationship
+\beta_{USD,P}USDAffinity
+\epsilon_P
\]

Selection is performed using softmax.

### Desired structural interpretation

**Classic:**

- more mass-market;
- more strongly associated with general credit appetite;
- weaker dependence on economic capacity.

**Premium:**

- structurally less common;
- stronger association with economic capacity;
- stronger association with relationship depth;
- weak-to-moderate association with USD affinity;
- only moderate association with credit appetite.

Premium must not be determined mechanically by income thresholds.

Substantial overlap between Classic and Premium customer profiles is required.

Examples that must remain possible:

- high-income customer with Classic;
- medium-income customer with Premium;
- high-income customer with no credit card;
- customer with both Classic and Premium;
- direct Premium acquisition without prior Classic.

---

# Multiple credit cards and saturation

A customer may hold multiple credit-card relationships.

The probability of an additional card must decrease with the number of already active credit cards.

Conceptually:

\[
z^{newcredit}_{i,t}
=
z^{credit}_{i,t}
-\lambda_1N_{active\ credit}
-\lambda_2N_{historical\ credit}
+\lambda_3CreditAppetite_i
\]

Expected qualitative pattern:

- one credit card — common among cardholders;
- two credit cards — visible;
- three — rare;
- four or more — exceptional.

Repeated product ownership may occur; therefore:

- two Classic relationships are allowed;
- two Premium relationships are allowed;
- Classic + Premium is allowed.

No deterministic one-card-per-customer rule should be imposed.

---

# Card closure and survival

For each active card relationship:

\[
P(Close_{c,t}=1)=\sigma(h_{c,t})
\]

The closure hazard may depend on:

- card age;
- relationship depth;
- credit appetite for P010/P011;
- redundancy from other cards;
- customer exit pressure;
- product type;
- idiosyncratic noise.

For debit cards, linked-account lifecycle is an additional structural dependency.

## Debit lifecycle integrity

- A debit card may close before its linked account.
- Closing a debit card does not close the account.
- If the linked account closes, the debit card must close no later than the account.
- An active debit card cannot reference a closed account in the final 2026 state.

## Classic-to-Premium relationship

Acquisition of Premium may increase the closure hazard of an existing Classic card, representing probabilistic upgrade or portfolio consolidation.

It must **not** automatically close Classic.

Therefore the DGP may naturally generate:

- Classic only;
- Premium only;
- Classic + Premium coexistence;
- Classic followed by Premium with Classic retained;
- Classic followed by Premium and later Classic closure.

---

# Credit-card economic closure

For P010 and P011, definitive relationship closure must remain economically coherent with later `credit_card_monthly_snapshot` generation.

A card may stop authorizing purchases before outstanding exposure is fully extinguished, but final `card_status = CLOSED` should normally correspond to payoff, settlement or another internally coherent resolution.

Under normal base generation, final outstanding exposure for a permanently closed card should be zero.

Any non-zero residual exposure after definitive closure should appear only if a later controlled data-quality anomaly is intentionally introduced.

---

# Credit-limit separation of concerns

Credit limits are **not** attributes of `cards`.

They will be modeled in `credit_card_monthly_snapshot`.

Future limit evolution may depend probabilistically on:

- financial capacity;
- relationship tenure;
- utilization;
- prior payment behavior;
- product type.

Premium cards may have higher limits on average, but their limit distributions must substantially overlap with Classic cards.

---

# Issue-channel generation

`issue_channel` is selected probabilistically using softmax.

A channel utility can depend on:

\[
U_{channel,k}
=
\alpha_{k,t}
+\beta_kDigitalAffinity_i
+\gamma_kProduct
+\epsilon_{ik}
\]

Historical evolution should be smooth:

- older years: overwhelmingly `BRANCH`;
- middle period: growth of `REMOTE_ASSISTED`;
- late 2010s onward: accelerating `DIGITAL`;
- 2021–2026: digital becomes increasingly important and may become the leading channel.

Card-channel dynamics should be specific to cards rather than copied mechanically from account-opening channel shares.

---

# Hard validation rules

The final generator must fail validation if any of the following invariants are violated:

1. `card_id` is unique and non-null.
2. Every `customer_id` is a valid customer FK.
3. Every `product_id` is one of P009, P010, P011.
4. Product ownership respects `target_customer_type`.
5. `issue_year >= product.launch_year`.
6. `issue_year >= customer.registration_year`.
7. `issue_year <= 2026`.
8. P009 has non-null `linked_account_id`.
9. P010/P011 have NULL `linked_account_id`.
10. Every linked debit account exists.
11. Linked debit account belongs to the same customer.
12. Linked debit account product belongs to P001–P006.
13. Debit `issue_year >= account.opening_year`.
14. No active debit card references a closed linked account in 2026.
15. For a closed linked account, debit `closing_year <= account.closing_year`.
16. At most one P009 relationship exists per `linked_account_id`.
17. `ACTIVE` implies `closing_year IS NULL`.
18. `CLOSED` implies `closing_year IS NOT NULL`.
19. `closing_year >= issue_year`.
20. `closing_year <= 2026`.
21. Closed customers retain no active cards.
22. Card closure for closed customers occurs no later than customer `closing_year`.
23. `issue_channel` belongs to BRANCH / REMOTE_ASSISTED / DIGITAL.
24. No realistic payment-card numbers are stored.

---

# Audit outputs

The following are diagnostic outputs, not hard targets.

The generator should report at least:

- total cards;
- total cardholders;
- customers with any active card;
- customers with active debit;
- share of customers with active eligible accounts who hold debit;
- customers with any credit card;
- active credit-card holders;
- Classic holders;
- Premium holders;
- Classic + Premium coexistence;
- mean and median cards per cardholder;
- distribution of 1 / 2 / 3 / 4+ credit cards;
- cards by product;
- cards by status;
- issuance by year;
- closure by year;
- issue channel by year;
- issue channel by product;
- debit issuance lag relative to account opening;
- debit ownership by linked account product;
- distribution of `credit_appetite`;
- `credit_appetite` by credit-card ownership;
- income distribution by no credit / Classic / Premium;
- relationship depth by card portfolio;
- credit cards by customer tenure.

These outputs are intended to evaluate whether the DGP produced plausible emergent patterns.

Aggregate ownership rates, Classic/Premium shares and exact closure proportions must **not** be enforced as quotas.

---

# Design principle

The table must preserve the distinction between **structural integrity** and **probabilistic behavior**.

Hard rules exist only where banking or relational logic requires them.

Everything else — adoption, card mix, Premium selection, additional-card ownership, survival, closure and channel — should emerge from probabilities, latent heterogeneity, temporal effects and random noise.

The goal is to create statistically meaningful relationships that can later be discovered through SQL, Power BI, Tableau and analytical modeling rather than merely reproducing deterministic generation rules.
