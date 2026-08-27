# BTYT --- Credit Card Transactions Data Dictionary

## Table: `credit_card_transactions`

**Description:**\
Transactional fact table containing individual credit-card transaction
attempts performed with BTYT credit cards.

**Grain:**\
One row represents one credit-card transaction attempt performed with
one BTYT credit card.

Both successful and failed transaction attempts are represented.

**Primary key:**\
`card_transaction_id`

**Purpose:**\
Represent detailed credit-card usage for transactional, behavioral and
analytical reporting, including purchases, cash advances, refunds,
merchant categories, transaction channels, installment behavior and
failed transaction attempts.

**References:** - `card_id` → foreign key to `cards.card_id` - Only BTYT
credit-card products are eligible: - `P010` --- Classic Credit Card -
`P011` --- Premium Credit Card

**Scope:** - Credit-card purchases are represented exclusively in this
table. - Credit-card purchases must not simultaneously be represented as
account spending transactions in `transactions`. - Subsequent payments
of credit-card balances from BTYT accounts may be represented separately
in `transactions`. - Individual installment billing events are not
represented as separate purchases in this table. - Original transaction
currency and exchange-rate mechanics are outside the scope of the
current analytical model.

------------------------------------------------------------------------

## Variables

## card_transaction_id

**Description:**\
Unique internal identifier assigned to each BTYT credit-card transaction
attempt.

**Data type:** - String

**Format:** - `CT` followed by numeric digits.

**Examples:** - `CT000000001` - `CT000000002`

**Rules:** - Must be unique. - Must not be NULL. - Used as the primary
key of `credit_card_transactions`. - Must remain unchanged after
generation. - Must not encode customer, card product, transaction type,
date, channel, merchant category or transaction status information. -
Both `COMPLETED` and `FAILED` transaction attempts receive a unique
`card_transaction_id`.

------------------------------------------------------------------------

## card_id

**Description:**\
Identifier of the BTYT credit card used for the transaction attempt.

**Data type:** - String

**Reference:** - Foreign key to `cards.card_id`.

**Rules:** - Must not be NULL. - Must contain a valid `card_id`. - The
referenced card must correspond to: - `P010` --- Classic Credit Card;
or - `P011` --- Premium Credit Card. - Debit cards (`P009`) must not
appear in `credit_card_transactions`. - The referenced card relationship
must already exist at `transaction_datetime`. - Transactions must remain
temporally compatible with the lifetime and status of the referenced
card relationship. - Historical transactions remain associated with
their original `card_id` after subsequent card closure.

------------------------------------------------------------------------

## transaction_datetime

**Description:**\
Date and time when the credit-card transaction attempt occurred.

**Data type:** - Datetime

**Format:** - `YYYY-MM-DD HH:MM:SS`

**Rules:** - Must not be NULL. - Must represent a valid date and time. -
Must fall within the BTYT transactional analytical period: -
`2021-01-01 00:00:00` through `2026-12-31 23:59:59`. - Must not occur
before the referenced card relationship exists. - Must not occur after
permanent closure of the referenced card relationship. - Transaction
timestamps must be chronologically plausible. - Historical transaction
timestamps must remain unchanged after generation.

**Generation assumptions:** - Transactions must not be uniformly
distributed across time. - Transaction frequency may vary according
to: - customer behavior; - day of week; - time of day; - seasonality; -
merchant category; - channel; - historical period; - customer financial
characteristics. - Transaction activity should exhibit realistic
temporal clustering and customer-level persistence. - Digital-channel
usage may evolve during the 2021--2026 analytical period. - Exact
transaction volumes must emerge from the synthetic generation process
rather than from predetermined analytical conclusions.

------------------------------------------------------------------------

## transaction_type

**Description:**\
Economic type of the BTYT credit-card transaction attempt.

**Data type:** - String / Categorical

**Allowed values:** - `PURCHASE` - `CASH_ADVANCE` - `REFUND`

**Category definitions:** - `PURCHASE`: Purchase of goods or services
using the BTYT credit card. - `CASH_ADVANCE`: Cash obtained using the
credit facility associated with the BTYT credit card. - `REFUND`:
Merchant-originated return of funds associated with plausible previous
purchase activity.

**Rules:** - Must not be NULL. - Must contain exactly one valid value. -
`PURCHASE` and `CASH_ADVANCE` increase credit-card exposure when
`transaction_status = COMPLETED`. - `REFUND` reduces credit-card
exposure when `transaction_status = COMPLETED`. - Failed transaction
attempts must not produce financial effects regardless of
`transaction_type`. - `REVERSAL` is intentionally excluded from the BTYT
credit-card transaction model. - `REFUND` represents a genuine merchant
refund and must not be used as a technical transaction reversal. -
Refund activity must remain financially plausible relative to previous
purchase behavior. - An explicit `original_transaction_id` is outside
the scope of the current model.

**Generation assumptions:** - `PURCHASE` should represent the majority
of credit-card activity. - `CASH_ADVANCE` should generally remain less
frequent than purchases. - `REFUND` should remain a minority transaction
type. - Transaction-type probabilities may vary according to customer
behavior and historical activity. - Exact transaction-type shares must
not be predetermined.

------------------------------------------------------------------------

## amount

**Description:**\
Monetary value of the BTYT credit-card transaction.

**Data type:** - Numeric / Decimal

**Currency treatment:** - Expressed in UYU-equivalent analytical terms.

**Rules:** - Must not be NULL. - Must be greater than zero. - `amount`
represents the absolute monetary value of the transaction. - Financial
direction must be inferred from `transaction_type`. - `PURCHASE` and
`CASH_ADVANCE` increase credit-card exposure when
`transaction_status = COMPLETED`. - `REFUND` reduces credit-card
exposure when `transaction_status = COMPLETED`. - Failed transactions
must not affect credit-card balances. - Transaction amounts must remain
plausible relative to available credit and the customer's broader
financial profile. - A completed `PURCHASE` or `CASH_ADVANCE` must not
normally exceed available credit at the time of authorization. - Refund
amounts must be financially plausible relative to previous purchase
activity. - Historical transaction amounts must not be modified after
generation.

**Generation assumptions:** - Transaction amounts must not be uniformly
or independently generated. - Amount distributions should vary by: -
`transaction_type`; - merchant category; - customer behavior; - customer
financial characteristics; - card product; - historical spending
patterns. - Individual customers should exhibit persistent spending-size
patterns with natural variation. - Premium-card holders may have larger
transaction amounts on average when supported by their broader customer
profile, but substantial overlap with Classic-card customers must
remain. - `CASH_ADVANCE` amounts should follow a different behavioral
distribution from ordinary purchases. - Refunds should reflect plausible
previous spending activity. - Seasonal and geographic patterns may
influence transaction amounts. - High-value outliers should exist but
remain uncommon. - Exact transaction-size distributions must not be
predetermined.

------------------------------------------------------------------------

## merchant_category

**Description:**\
Commercial category associated with the merchant where the BTYT
credit-card transaction occurred.

**Data type:** - String / Categorical - NULL

**Allowed values:** - `GROCERIES` - `RESTAURANTS` - `FUEL` - `RETAIL` -
`HEALTHCARE` - `PHARMACY` - `TRANSPORT` - `TRAVEL` - `ENTERTAINMENT` -
`EDUCATION` - `UTILITIES` - `TELECOMMUNICATIONS` - `ECOMMERCE` -
`HOME` - `AUTOMOTIVE` - `PROFESSIONAL_SERVICES` - `OTHER`

**Rules:** - Must contain a valid category when
`transaction_type = PURCHASE`. - Must be `NULL` when
`transaction_type = CASH_ADVANCE`. - For `REFUND`, `merchant_category`
must represent a plausible category associated with the underlying
previous purchase activity. - Merchant category represents the economic
activity of the merchant rather than a specific merchant name. -
Merchant categories must use the same standardized BTYT taxonomy used
for debit-card purchase activity. - Merchant category must not be
generated uniformly across transactions. - Category assignment must
remain behaviorally consistent with transaction amount, channel,
customer characteristics and historical spending behavior. -
Merchant-category distributions must not be predetermined to produce
specific analytical conclusions.

**Generation assumptions:** - Individual customers should exhibit
partially persistent consumption patterns across time while retaining
natural variation. - Merchant-category probabilities may depend on: -
customer characteristics; - customer type; - spending capacity; -
credit-card product; - geographic context; - seasonality; - transaction
channel; - day of week; - historical spending behavior. - Everyday
categories such as `GROCERIES`, `FUEL` and `PHARMACY` may exhibit
relatively frequent transactions with generally moderate amounts. -
`TRAVEL`, `HOME`, `AUTOMOTIVE` and selected `RETAIL` transactions may
exhibit lower frequency but higher transaction amounts. - `RESTAURANTS`
and `ENTERTAINMENT` may exhibit stronger weekend and evening patterns. -
`TRAVEL` may exhibit seasonal patterns and stronger activity during
tourism periods. - `ECOMMERCE` should be strongly associated with
digital transaction channels without representing every online
transaction. - `UTILITIES` and `TELECOMMUNICATIONS` may exhibit
recurring monthly behavior for some customers. - Category-specific
amount distributions should overlap substantially rather than follow
rigid ranges.

### Credit-card product behavior

-   Classic and Premium credit cards may exhibit different
    merchant-category distributions.
-   Premium-card customers may show relatively greater activity in
    categories such as `TRAVEL`, `RESTAURANTS` or higher-value `RETAIL`
    when supported by their broader customer profile.
-   These differences must not be deterministic.
-   Credit-card product alone must not determine customer spending
    behavior.
-   Customer characteristics and historical behavior should remain
    important drivers.

### Cross-payment-method consistency

-   Merchant categories must remain conceptually and categorically
    compatible with merchant categories used for debit-card purchase
    activity.
-   Customers may use both debit and credit for the same merchant
    categories.
-   Payment-method choice may depend on transaction amount, available
    funds, available credit, customer habits, installments and other
    behavioral factors.
-   The generator must not mechanically assign specific merchant
    categories exclusively to debit or credit.

------------------------------------------------------------------------

## channel

**Description:**\
Channel through which the BTYT credit-card transaction was originated or
processed.

**Data type:** - String / Categorical

**Allowed values:** - `POS` - `WEB` - `MOBILE` - `ATM` - `AUTOMATIC`

**Category definitions:** - `POS`: Transaction performed through a
physical point-of-sale terminal. - `WEB`: Transaction initiated through
a web-based merchant or digital environment. - `MOBILE`: Transaction
initiated through a mobile application or mobile-based commercial
environment. - `ATM`: Transaction performed through an automated teller
machine. - `AUTOMATIC`: Recurring or automatically initiated charge
previously authorized by the cardholder.

**Rules:** - Must not be NULL. - Must contain exactly one valid
channel. - Channel definitions must remain conceptually consistent with
the channel taxonomy used elsewhere in BTYT transactional data. -
`BRANCH` is not applicable to credit-card transactions. - `PURCHASE` may
use: - `POS`; - `WEB`; - `MOBILE`; - `AUTOMATIC`. - `CASH_ADVANCE` must
use `ATM`. - `REFUND` should use a channel compatible with the
underlying purchase activity. - `ATM` must not be used for ordinary
purchases. - `AUTOMATIC` must represent a previously authorized
recurring or automatically initiated charge. - Channel assignment must
remain consistent with `merchant_category`, customer behavior and
`transaction_type`.

### AUTOMATIC

`AUTOMATIC` transactions may represent recurring charges such as: - gym
or club memberships; - streaming services; - insurance; - software
subscriptions; - telecommunications services; - recurring educational
services; - other subscription-based products or services.

**Recurring-payment rules:** - Customers may exhibit recurring
`AUTOMATIC` transactions with similar amounts at approximately monthly
intervals. - Recurring charges should exhibit persistence across months
rather than being independently regenerated each month. - Amounts may
occasionally change due to price adjustments or changes in the
underlying service. - Recurring charges may begin or terminate during
the analytical period. - Missed or failed recurring charges may occur
when financially or operationally plausible. - Not every customer must
have recurring credit-card charges. - Customers may have multiple
recurring charges simultaneously.

**Generation assumptions:** - Channel probabilities must not be
uniformly generated. - `POS` should remain common for physical
commercial activity. - `WEB` and `MOBILE` usage may evolve during the
2021--2026 analytical period. - `AUTOMATIC` usage should depend on
persistent customer-level recurring-payment relationships. - Merchant
category and channel should be probabilistically related without
becoming deterministic. - Exact channel shares must not be
predetermined.

------------------------------------------------------------------------

## installments

**Description:**\
Total number of installments agreed for the BTYT credit-card
transaction.

**Data type:** - Integer

**Allowed values:** - `1` - `2` - `3` - `6` - `10` - `12` - `18` - `24`

**Rules:** - Must not be NULL. - Must contain one valid installment
value. - `1` represents a transaction without installment financing. -
Values greater than `1` are only applicable to `PURCHASE`. -
`CASH_ADVANCE` must have `installments = 1`. - `REFUND` must have
`installments = 1`. - `AUTOMATIC` recurring purchases must normally have
`installments = 1`. - `amount` represents the total original purchase
amount, not the individual installment amount. - A purchase financed in
multiple installments must appear as one original transaction in
`credit_card_transactions`. - Individual installment payments must not
be represented as separate purchase transactions. - Installment
availability must remain commercially plausible according to transaction
amount, merchant category and customer/card characteristics. - Not every
purchase or merchant category should allow every installment option. -
Completed installment purchases must respect available credit
considering the total purchase commitment.

**Generation assumptions:** - Most ordinary and low-value purchases
should use `installments = 1`. - Installment usage probability should
generally increase with transaction amount. - Merchant categories such
as `HOME`, `RETAIL`, `AUTOMOTIVE`, `TRAVEL` and selected higher-value
purchases may exhibit greater installment usage. - Everyday categories
such as `GROCERIES`, `FUEL`, `PHARMACY` and `RESTAURANTS` should
generally have lower installment usage. - Higher installment counts such
as `18` and `24` should remain less frequent and primarily associated
with sufficiently high-value eligible purchases. - Customer installment
preferences should exhibit behavioral persistence: some customers may
regularly use installments while others may strongly prefer
single-payment purchases. - Card product and customer financial
characteristics may influence installment behavior without
deterministically defining it. - Installment distributions must not be
uniformly generated.

### Financial consistency

-   For a purchase with `amount = A` and `installments = N`, the
    original transaction represents a total financial commitment of `A`.
-   Monthly billing effects associated with the installment plan must be
    reflected consistently in `credit_card_monthly_snapshot`.
-   The generator must prevent the installment mechanism from
    duplicating the original purchase amount across monthly records.
-   Installment scheduling must remain consistent across subsequent
    months until the applicable purchase commitment has been billed.

------------------------------------------------------------------------

## transaction_status

**Description:**\
Final processing status of the BTYT credit-card transaction attempt.

**Data type:** - String / Categorical

**Allowed values:** - `COMPLETED` - `FAILED`

**Category definitions:** - `COMPLETED`: The credit-card transaction was
successfully authorized and processed. - `FAILED`: The credit-card
transaction attempt was not successfully completed.

**Rules:** - Must not be NULL. - Must contain exactly one valid
status. - `COMPLETED` transactions must produce the corresponding
financial effect according to `transaction_type`. - `FAILED`
transactions must not modify credit-card balances, available credit or
monthly financial exposure. - `FAILED` transactions remain valid
transaction attempts and therefore retain their transaction
characteristics. - `REVERSED` is intentionally excluded from the BTYT
credit-card transaction model. - Transaction status must be generated
using information available at `transaction_datetime`. - Future
delinquency, default, account closure or other future customer behavior
must not influence transaction authorization. - Transaction status must
not be generated uniformly across customers.

**Generation assumptions:** - `COMPLETED` should represent the clear
majority of normal credit-card transaction attempts. - `FAILED` should
remain a minority outcome under ordinary operating conditions. - Failure
probability may depend on: - available credit at transaction time; -
card relationship status; - transaction amount; - transaction channel; -
operational conditions; - plausible security controls; - transaction
characteristics; - customer historical behavior available at that
time. - Different customers may exhibit different failure frequencies. -
Temporary operational conditions may generate short periods with
elevated failure rates. - Failure patterns must remain realistic and
must not be inserted merely to create visually interesting dashboards. -
Exact completion and failure rates must not be predetermined.

------------------------------------------------------------------------

## failure_reason

**Description:**\
Primary reason why a BTYT credit-card transaction attempt failed.

**Data type:** - String / Categorical - NULL

**Allowed values:** - `INSUFFICIENT_AVAILABLE_CREDIT` - `CARD_BLOCKED` -
`SECURITY_DECLINE` - `TECHNICAL_ERROR` - `INVALID_TRANSACTION` - `OTHER`

**Category definitions:** - `INSUFFICIENT_AVAILABLE_CREDIT`: The
transaction amount or applicable financial commitment exceeded the
credit available to the card at the time of the attempt. -
`CARD_BLOCKED`: The card relationship or applicable card credentials
were blocked when the transaction was attempted. - `SECURITY_DECLINE`:
The transaction was declined by applicable fraud-prevention or security
controls. - `TECHNICAL_ERROR`: The transaction could not be completed
because of a technical, connectivity or processing problem. -
`INVALID_TRANSACTION`: The transaction could not be processed because
the attempted operation was incompatible with applicable card or
transaction rules. - `OTHER`: Other uncommon legitimate failure reason
not represented by the defined categories.

**Rules:** - Must be `NULL` when `transaction_status = COMPLETED`. -
Must contain exactly one valid value when
`transaction_status = FAILED`. - Failure reason must be logically
consistent with the state of the card and transaction at
`transaction_datetime`. - `INSUFFICIENT_AVAILABLE_CREDIT` may only occur
when available credit is insufficient for the attempted financial
commitment. - `CARD_BLOCKED` may only occur when the applicable card
condition prevents authorization at the time of the attempt. -
`SECURITY_DECLINE` must represent a plausible security-control rejection
and must not imply that actual fraud occurred. - `TECHNICAL_ERROR` must
represent operational or processing failure rather than customer
financial behavior. - `OTHER` should remain relatively uncommon. -
Failure reasons must not be assigned independently from the underlying
transaction and card state. - `CARD_EXPIRED` is intentionally excluded
because physical-card expiration and renewal are not explicitly modeled
in the current BTYT card relationship structure.

**Generation assumptions:** - Failure reasons must be generated
conditionally from the circumstances of each transaction attempt. -
`INSUFFICIENT_AVAILABLE_CREDIT` probability should increase when the
attempted transaction approaches or exceeds available credit. -
`SECURITY_DECLINE` may become more plausible for unusual transaction
patterns without mechanically classifying unusual transactions as
fraudulent. - `TECHNICAL_ERROR` may exhibit temporary clustering
associated with plausible operational or service disruptions. -
`CARD_BLOCKED` failures may persist across multiple attempts while the
applicable blocking condition remains active. - Failed recurring
`AUTOMATIC` transactions may occur when the underlying card condition
prevents successful processing. - The same customer may experience
different failure reasons over time. - Failure reasons must not be
generated using future customer outcomes.

------------------------------------------------------------------------

## Financial integrity

The financial effect of each transaction must follow:

  transaction_type   transaction_status   Financial effect
  ------------------ -------------------- --------------------------------
  `PURCHASE`         `COMPLETED`          Increases credit-card exposure
  `CASH_ADVANCE`     `COMPLETED`          Increases credit-card exposure
  `REFUND`           `COMPLETED`          Reduces credit-card exposure
  `PURCHASE`         `FAILED`             No financial effect
  `CASH_ADVANCE`     `FAILED`             No financial effect
  `REFUND`           `FAILED`             No financial effect

-   Failed transactions must never modify balances.
-   Completed transactions must be reflected consistently in subsequent
    credit-card financial state.
-   Credit-card transactions and `credit_card_monthly_snapshot` must not
    be generated as independent financial processes.
-   Monthly snapshots must remain reconcilable with completed
    credit-card activity, installment commitments, refunds, payments and
    any other explicitly modeled monthly financial effects.

------------------------------------------------------------------------

## Cross-table integrity

### `cards`

-   Every `card_id` must exist in `cards`.
-   Only `P010` and `P011` cards may appear.
-   Transactions must respect the lifetime of the referenced card
    relationship.

### `credit_card_monthly_snapshot`

-   Completed credit-card activity must contribute consistently to the
    evolution of monthly credit-card exposure.
-   Installment purchases must affect monthly billing without
    duplicating the original purchase amount.
-   Refunds must reduce exposure consistently.
-   Failed transactions must have no financial effect.

### `transactions`

-   A credit-card purchase must not be duplicated as an account purchase
    in `transactions`.
-   Payments made from BTYT accounts toward credit-card balances may be
    represented separately in `transactions`.
-   Cash advances represented here must not be duplicated as ordinary
    account withdrawals unless a separate legitimate account-side
    financial event exists.

### Debit-card analytical consistency

-   Merchant-category taxonomy must remain standardized across debit and
    credit purchase activity.
-   Transaction-channel concepts should remain consistent whenever the
    same economic channel exists in both datasets.
-   Differences between debit and credit behavior should emerge from the
    generated customer behavior rather than from incompatible
    categorical definitions.

------------------------------------------------------------------------

## Generation principles

-   Credit-card transactions must be generated from persistent
    customer-level behavior rather than independent random draws.
-   Customer transaction behavior may depend on:
    -   financial capacity;
    -   income;
    -   customer type;
    -   card product;
    -   available credit;
    -   previous spending behavior;
    -   merchant preferences;
    -   channel preferences;
    -   installment preferences;
    -   recurring-payment relationships;
    -   geography;
    -   seasonality;
    -   historical period.
-   Relationships between variables should be probabilistic rather than
    deterministic.
-   Synthetic generation must preserve meaningful overlap between
    customer groups.
-   Premium cards must not mechanically imply high spending.
-   High income must not mechanically imply Premium-card ownership.
-   Digital customers must not exclusively use digital channels.
-   Customers with available credit must not necessarily spend it.
-   Campaign exposure must not mechanically cause increased credit-card
    spending.
-   Future outcomes must not be used to generate historical transaction
    decisions.
-   Exact analytical findings must emerge from the generated data rather
    than being predetermined.

------------------------------------------------------------------------

## Final schema

`credit_card_transactions` contains exactly:

1.  `card_transaction_id`
2.  `card_id`
3.  `transaction_datetime`
4.  `transaction_type`
5.  `amount`
6.  `merchant_category`
7.  `channel`
8.  `installments`
9.  `transaction_status`
10. `failure_reason`

## Phase 3 credit-card financial mechanics

### Live credit authorization
- `PURCHASE` and `CASH_ADVANCE` attempts must be authorized against live available credit at the exact transaction time.
- If the attempted financial commitment exceeds live available credit, the transaction must be `FAILED` with the applicable insufficient-credit failure reason.
- Python must not silently reduce the attempted amount to force approval.
- Failed transactions have no financial effect.

### Installment commitments
- A completed installment purchase consumes the full original purchase commitment from available credit at authorization time.
- Example: a purchase of `120000` in `12` installments consumes `120000` of available credit initially, not only the first installment.
- The installment schedule is maintained internally by Python.
- Individual installments are billing obligations, not additional purchase transactions.
- As principal exposure is repaid or refunded, the corresponding credit capacity is released.

### Refund linkage
- Refunds must be associated internally with plausible prior completed purchase activity.
- The generator may retain an internal original-transaction link without persisting an additional column.
- Refunds must not exceed economically plausible refundable exposure from prior purchases.
- A completed refund reduces live card exposure and releases corresponding credit capacity.

### Billing-cycle state
- Each credit-card relationship must have an internally maintained statement-closing day and payment-due day.
- These dates are generator state and are not persisted as columns in the current analytical tables.
- Transaction timing relative to the statement closing date determines the billing cycle in which the obligation becomes due.

### Cash advances
- `CASH_ADVANCE` remains subject to available-credit authorization.
- Cash advances may use a product-specific internal sublimit smaller than the total credit limit.
- Their cost structure may differ from ordinary purchases and may contribute to higher interest expense.
- Cash-advance use may correlate probabilistically with liquidity needs but must not mechanically imply future delinquency or default.

## Phase 3 behavioral-generation rules

### Persistent card-use behavior
- Credit-card usage must reflect persistent customer-level preferences such as credit reliance, installment preference, recurring-payment habits, merchant-category preferences and channel usage.
- These preferences should influence probabilities without deterministically forcing specific transaction outcomes.
- Customers with similar income and card products may exhibit substantially different credit-card behavior.

### Contemporaneous affordability and liquidity
- Historical credit-card behavior must use contemporaneous internally generated customer financial conditions rather than future master-table income/revenue values.
- Spending intensity, installment use, cash advances and payment pressure may react to temporary liquidity shocks, but no shock should mechanically force delinquency or default.

### Installment choice
- Installment selection must depend probabilistically on transaction amount, merchant category, customer installment preference, available credit and current financial conditions.
- Customers may exhibit persistent installment habits, but no customer should be forced to always or never use installments unless a hard product rule applies.

### Merchant and channel behavior
- Merchant-category and channel choices should exhibit customer-level persistence and context sensitivity.
- Digital usage may increase gradually during 2021–2026 as part of a secular adoption trend.
- That trend must remain distinct from campaign-induced behavioral effects.
- `AUTOMATIC` recurring charges should persist through internally maintained recurring-payment relationships rather than being recreated independently each month.

### Risk neutrality of demographic labels
- Demographic variables such as gender, nationality and geographic location must not be used as direct credit-risk coefficients in transaction generation.
- Any observed relationship between demographic groups and credit-card behavior must emerge indirectly from economic conditions, product ownership, customer preferences and stochastic variation.

## Phase 3 operational-incident and data-quality rules

### Ground truth before observed card data
- Python must first generate a coherent credit-card ledger, authorization result and transaction history.
- Operational incidents or controlled data-quality degradation may affect the observed transaction record only after the underlying card event has been resolved.
- Data-quality anomalies must not be used to manufacture or repair credit-card exposure.

### Incident effects
- Where operationally plausible, configured incidents may produce delayed posting, duplicate observed records, missing optional classifications or missing observed card-transaction rows.
- A duplicated observed record must correspond to a single known ground-truth card event and must not double the true card exposure.
- A missing observed card-transaction row must not erase its true economic effect from the internal card ledger or coherent month-end exposure.
- Incident effects must respect the offices, channels, dates and systems actually configured as affected.

### Controlled background errors and auditability
- A very small background rate of ordinary processing errors may be introduced outside major incidents.
- Deliberate anomalies must remain sparse and reproducible.
- Python must preserve affected ground-truth transaction identifiers, original values and observed modifications in the internal generation audit.
- The generation audit is not exported as part of the normal analytical dataset.
