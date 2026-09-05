# BTYT --- Card Monthly Snapshot Data Dictionary

## Table: `card_monthly_snapshot`

**Description:**\
Monthly historical snapshot of BTYT card-level financial exposure and
utilization.

**Grain:**\
One row represents one BTYT card in one calendar month.

**Primary key:**\
Composite key: `card_id` + `year_month`

**Purpose:**\
Track the monthly evolution of credit limits, outstanding balances and
card utilization for analytical reporting and future credit-risk
modeling.

**Reference:** - `card_id` → foreign key to `cards.card_id`

------------------------------------------------------------------------

## Variables

**Included products:** - `P010` Classic Credit Card - `P011` Premium
Credit Card **Excluded products:** - `P009` Debit Card --- debit cards
do not represent a credit facility and are therefore excluded from this
monthly credit exposure table.

## card_id

**Description:** Unique identifier of the BTYT credit card associated
with the monthly snapshot.

**Data type:** - String

**Reference:** - Foreign key to `cards.card_id`.

**Rules:** - Must contain a valid `card_id`. - Must not be NULL. - The
referenced card must correspond to `product_id = P010`
(`Classic Credit Card`) or `product_id = P011`
(`Premium Credit Card`). - Debit cards (`P009`) must not appear in this
table. - One credit card may appear in multiple rows, with one row per
calendar month. - The card must have been issued on or before the
corresponding `year_month`. - Historical snapshots remain associated
with the original `card_id` after card closure.

## year_month

**Description:** Calendar month represented by the credit-card financial
snapshot.

**Data type:** - String / Period

**Format:** - `YYYY-MM`

**Examples:** - `2024-01` - `2025-08` - `2026-07`

**Rules:** - Must not be NULL. - Must represent a valid calendar
month. - The combination `card_id + year_month` must be unique. -
`year_month` must not precede the card's `issue_year`. - No monthly
snapshots should exist after the credit-card relationship has
permanently ended. - Monthly observations should normally be continuous
throughout the active life of the credit-card relationship. -
Intentional operational or data-quality incidents may generate
exceptional missing observations.

## credit_limit

**Description:** Maximum credit amount authorized by BTYT for the
specific credit-card relationship during the calendar month.

**Data type:** - Numeric / Decimal

**Currency:** - UYU (normalized reference currency)

**Rules:** - Must not be NULL. - Must be greater than zero. - Represents
the authorized credit limit applicable to the credit card during
`year_month`. - `credit_limit` may remain unchanged across multiple
consecutive months. - Changes in `credit_limit` should represent actual
limit increases or reductions rather than routine monthly variation. -
`Premium Credit Card` should generally support higher credit limits than
`Classic Credit Card`, while substantial overlap between both products
must remain possible. - A Classic Credit Card may have a higher limit
than an individual Premium Credit Card. - Credit limit must not
deterministically define customer segment, spending behavior,
utilization or credit risk. - Historical credit limits must not be
overwritten when subsequent limit changes occur.

**Generation assumptions:** - Credit limits should generally remain
stable for extended periods. - Limit reviews may occasionally result in
increases, reductions or no change. - The probability and magnitude of a
limit adjustment may be influenced by: - customer income; - business or
employment characteristics; - customer tenure; - card tenure; - card
product; - previous credit utilization; - payment behavior; - broader
commercial or economic conditions. - `Premium Credit Card` should have a
higher expected credit-limit distribution than `Classic Credit Card`. -
The distributions of Classic and Premium credit limits must overlap. -
Long-standing customers with favorable banking relationships may have a
greater probability of receiving limit increases. - Limit reductions
should occur less frequently than increases but remain possible. -
Customers with otherwise similar characteristics may receive different
limits. - Extreme high-limit observations should exist but represent a
small minority. - Exact limits, adjustment frequencies and product-level
averages must not be predetermined.

## outstanding_balance

**Description:** Total outstanding credit-card balance owed by the
customer at the end of the calendar month.

**Data type:** - Numeric / Decimal

**Currency:** - UYU (normalized reference currency)

**Rules:** - Must not be NULL. - Must be greater than or equal to
zero. - Represents the total credit-card balance outstanding at the end
of `year_month`. - Must normally be less than or equal to the applicable
`credit_limit`. - A value of `0` is valid and represents a credit card
with no outstanding balance at month-end. - `outstanding_balance` must
not be interpreted as total monthly spending. - Payments made during the
month may reduce the outstanding balance before the monthly snapshot is
recorded. - Historical outstanding balances must not be overwritten by
subsequent card activity. - Temporary exceptional situations above the
authorized credit limit may occur only if explicitly modeled and should
remain rare.

**Generation assumptions:** - Outstanding balances must not be uniformly
distributed. - Balance behavior should vary substantially across
customers and months. - Many customers should regularly maintain low or
zero month-end balances. - Some customers may systematically use a
significant portion of their available credit. - Customer income, card
product, credit limit, spending behavior and payment behavior may
influence expected outstanding balances. - Higher credit limits should
allow larger absolute balances without mechanically producing higher
utilization. - Premium cardholders may have larger absolute outstanding
balances while potentially maintaining lower utilization ratios due to
higher limits. - Seasonal consumption patterns may generate higher
balances during particular periods. - Individual customers should
exhibit persistent behavioral tendencies while retaining month-to-month
variation. - Exact balance distributions and utilization patterns must
not be predetermined.

## available_credit

**Description:** Amount of unused credit available to the customer at
the end of the calendar month.

**Data type:** - Numeric / Decimal

**Currency:** - UYU (normalized reference currency)

**Calculation:** `available_credit = credit_limit - outstanding_balance`

**Rules:** - Must not be NULL. - Must normally be greater than or equal
to zero. - Must be calculated from `credit_limit` and
`outstanding_balance`. - Must not be generated independently. - Must be
expressed in the same currency as `credit_limit` and
`outstanding_balance`. - A value of `0` represents full utilization of
the authorized credit limit. - Historical values must not be overwritten
by subsequent card activity. - Exceptional negative values may only
occur if explicit over-limit behavior is modeled and should remain rare.

**Data quality rule:**
`available_credit + outstanding_balance = credit_limit`

## utilization_rate

**Description:** Proportion of the authorized credit limit used by the
customer at the end of the calendar month.

**Data type:** - Numeric / Decimal

**Unit:** - Ratio

**Calculation:** `utilization_rate = outstanding_balance / credit_limit`

**Rules:** - Must not be NULL. - Must be calculated from
`outstanding_balance` and `credit_limit`. - Must not be generated
independently. - Should normally range between `0` and `1`. - `0`
represents no credit utilization. - `1` represents full utilization of
the authorized credit limit. - Values greater than `1` may only occur if
exceptional over-limit behavior is explicitly modeled. - Historical
utilization rates must not be overwritten by subsequent card activity.

**Generation assumptions:** - Utilization patterns should vary across
customers and over time. - Individual customers may exhibit persistent
utilization tendencies. - Higher absolute outstanding balances do not
necessarily imply higher utilization rates. - Premium cardholders may
have larger absolute balances while maintaining relatively low
utilization due to higher credit limits. - High utilization should not
mechanically imply delinquency or default. - Exact utilization
distributions must emerge from the underlying generated balances and
credit limits.

**Data quality rule:**
`utilization_rate = outstanding_balance / credit_limit`

## Generation and reconciliation rule

`credit_card_monthly_snapshot` is a derived monthly financial snapshot
and must not be generated independently from credit-card transaction
history.

For each active credit-card relationship and month, the snapshot must be
consistent with:

-   completed `PURCHASE` activity;
-   completed `CASH_ADVANCE` activity;
-   completed `REFUND` activity;
-   installment schedules generated from eligible purchases;
-   credit-card payments generated on the account side when applicable;
-   any explicitly modeled interest, fees or other monthly financial
    effects.

Rules:

-   failed credit-card transactions must have no financial effect;
-   an installment purchase appears once in `credit_card_transactions`
    for the total original purchase amount;
-   the installment schedule is maintained internally by the generator
    and affects monthly billing without duplicating the original
    purchase amount;
-   payments from BTYT accounts may retain an internal link to the
    relevant `card_id` for reconciliation even though `transactions`
    does not persist a `card_id` column;
-   the monthly snapshot must be generated after the underlying card
    activity and payment schedule are known;
-   intentionally simulated data-quality anomalies must be introduced
    only after a coherent underlying financial history exists.

The observational period for monthly snapshots is `2021-01` through
`2026-12`, subject to the active lifetime of each credit-card
relationship.

## Phase 3 credit-card snapshot mechanics

### Meaning of outstanding_balance
- `outstanding_balance` represents the total live financial exposure of the credit-card relationship at month end.
- It is not limited to the amount billed on the current statement.
- It includes unpaid exposure from eligible purchases, installment commitments, cash advances and applicable internally modeled financial charges, net of payments and refunds.
- For installment purchases, the full unpaid committed principal remains part of live exposure even when only one installment is currently billed.

### Available credit and utilization
- Under coherent base generation, `available_credit = credit_limit - outstanding_balance` must always hold.
- `utilization_rate = outstanding_balance / credit_limit` must always be derived from the other snapshot values.
- Over-limit behavior is outside the current coherent base model.
- Therefore normal generated snapshots must satisfy `available_credit >= 0` and `0 <= utilization_rate <= 1`.
- Any violation may only be introduced later as a controlled data-quality anomaly.

### Billing and payment state
- Python must maintain internal `statement_balance`, `minimum_payment`, statement-closing date and due date for every active credit-card relationship.
- These internal values drive payment decisions and delinquency mechanics but are not persisted as columns in the current snapshot.
- Paying the contractual minimum by the due date may keep the relationship current even when a revolving balance remains outstanding.
- Carrying a revolving balance or having high utilization does not by itself imply delinquency.
- Paying less than the required minimum after the due date creates internal delinquency state.

### Interest and financial charges
- Interest and other modeled financial charges must arise from the applicable financed balance, product pricing and elapsed time.
- They must not be independently sampled merely to obtain a target month-end balance.
- Such charges increase live exposure and must reconcile with the internally maintained card ledger.

### Payments
- Credit-card payments may originate from a BTYT account or an external payment source.
- Payments from BTYT accounts must reconcile with `transactions.transaction_type = CREDIT_CARD_PAYMENT`.
- External payments reduce card exposure without requiring a BTYT account-side transaction.
- Applied payments release available credit when they are posted, not only at month end.
- The month-end snapshot captures the resulting state after all applicable posted activity.

### Internal delinquency state
- Python may maintain internal card delinquency variables such as unpaid minimum amount, oldest unpaid due date and card DPD.
- These states may influence authorization, risk controls, credit-limit changes, temporary blocking or eventual relationship closure.
- They are generator state only and are not exported in the current six-column snapshot.
- High utilization must not mechanically imply delinquency, and delinquency must emerge from actual unmet payment obligations.
