# BTYT --- Transactions Data Dictionary

## Table: `transactions`

**Description:**\
Table containing individual monetary transactions processed through BTYT
customer accounts.

**Grain:**\
One row represents one unique BTYT account transaction.

**Primary key:**\
`transaction_id`

**Purpose:**\
Represent detailed customer account activity for transactional analysis,
channel analysis, customer behavior, branch performance, data-quality
controls and reconciliation with monthly account balance snapshots.

**Reference:** - `account_id` → foreign key to `accounts.account_id`

------------------------------------------------------------------------

## Variables

## transaction_id

**Description:** Unique internal identifier assigned to each BTYT
transaction.

**Data type:** - String

**Format:** - `T` followed by ten numeric digits.

**Examples:** - `T0000000001` - `T0000000002` - `T0125487391`

**Rules:** - Must be unique. - Must not be NULL. - Used as the primary
key of the `transactions` table. - Must remain unchanged throughout the
lifetime of the transaction record. - Must not encode account, customer,
branch, transaction type, channel, currency or transaction status
information. - `transaction_id` is an internal synthetic BTYT
identifier.

## account_id

**Description:** Unique identifier of the BTYT account affected by the
transaction.

**Data type:** - String

**Reference:** - Foreign key to `accounts.account_id`.

**Rules:** - Must contain a valid `account_id`. - Must not be NULL. -
Every transaction must affect exactly one BTYT account record. - The
referenced account must have been open at the time of the transaction. -
Transactions must not occur after the permanent closure of the
account. - `account_id` identifies the account whose balance is directly
affected by the transaction. - Transactions related to credit cards or
loans may appear in this table only when they generate an actual
movement in a BTYT account. - Credit-card purchases that only increase
card debt must not be recorded in this table. - Loan repayment behavior
that does not directly generate an account movement must remain in the
lending tables.

## transaction_datetime

**Description:** Date and time at which the BTYT account transaction was
recorded.

**Data type:** - Datetime

**Format:** - `YYYY-MM-DD HH:MM:SS`

**Examples:** - `2025-03-14 10:32:18` - `2026-01-07 21:45:02`

**Rules:** - Must not be NULL. - Must represent a valid calendar date
and time. - Must occur on or after the referenced account's opening
period. - Must not occur after the permanent closure of the referenced
account. - Must not be later than the `2026-12-31`. -
`transaction_datetime` represents the timestamp of the specific account
movement. - Date-derived analytical fields such as year, month, weekday,
hour or weekend indicator should be calculated from
`transaction_datetime` rather than stored redundantly in the source
table. - Historical transaction timestamps must not be modified by
subsequent account events.

**Generation assumptions:** - Transactions must not be uniformly
distributed across dates or times. - Transaction intensity should vary
by: - day of week; - hour of day; - transaction type; - channel; -
customer type; - product type; - seasonality; - holidays and
salary-payment periods; - business activity patterns. - Business
accounts may exhibit stronger weekday and business-hour concentration. -
Individual customers may show greater evening and weekend activity
through digital channels. - ATM and digital transactions may occur
outside branch operating hours. - In-person branch transactions should
be restricted to plausible operating days and hours. - Payroll-related
activity may create recurring monthly transaction peaks. -
Tourism-oriented areas may exhibit stronger seasonal patterns. - Exact
temporal distributions must not be predetermined and should emerge from
the synthetic generation process within plausible behavioral
constraints.

## transaction_type

**Description:** Classification of the economic nature of the BTYT
account transaction.

**Data type:** - String / Categorical

**Allowed values:** - `TRANSFER_IN` - `TRANSFER_OUT` - `CASH_DEPOSIT` -
`CASH_WITHDRAWAL` - `DEBIT_PURCHASE` - `SERVICE_PAYMENT` -
`CREDIT_CARD_PAYMENT` - `LOAN_PAYMENT` - `LOAN_DISBURSEMENT` -
`INTEREST_CREDIT`

**Category definitions:** - `TRANSFER_IN`: Funds received into the
account through a bank transfer. - `TRANSFER_OUT`: Funds sent from the
account through a bank transfer. - `CASH_DEPOSIT`: Cash deposited into
the account. - `CASH_WITHDRAWAL`: Cash withdrawn from the account. -
`DEBIT_PURCHASE`: Purchase paid directly from the account through a BTYT
debit card. - `SERVICE_PAYMENT`: Payment of utilities, taxes or other
services from the account. - `CREDIT_CARD_PAYMENT`: Payment made from
the account toward a BTYT credit-card balance. - `LOAN_PAYMENT`: Payment
made from the account toward a BTYT lending contract. -
`LOAN_DISBURSEMENT`: Funds credited to the account as the proceeds of a
BTYT loan. - `INTEREST_CREDIT`: Interest credited by BTYT to the
account.

**Rules:** - Must not be NULL. - Every transaction must have exactly one
`transaction_type`. - `transaction_type` represents the primary economic
nature of the account movement. - Incoming and outgoing transfer
activity must use separate transaction types. - Salary income must not
be represented as a separate transaction type; salary-related transfers
should be represented through `TRANSFER_IN` and identified through
contextual attributes such as counterparty classification. - Credit-card
purchases must not appear as `DEBIT_PURCHASE`; only purchases directly
debited from an account through `P009` may use this category. -
`CREDIT_CARD_PAYMENT` may appear only when a BTYT account is used to pay
a BTYT credit-card relationship. - `LOAN_PAYMENT` may appear only when a
BTYT account is used to pay a BTYT lending contract. -
`LOAN_DISBURSEMENT` must correspond to an actual BTYT lending
relationship. - Transaction types must remain consistent with the
direction and channel of the movement.

**Generation assumptions:** - Transaction-type distributions must not be
uniform. - Product type, customer type, account characteristics and
customer behavior should influence transaction-type probabilities. -
Payroll accounts should have a high probability of recurring incoming
transfers associated with employers. - Business accounts should
generally exhibit higher transfer activity than typical individual
accounts. - Cash usage should vary geographically and by customer
profile. - Debit purchases and digital transfers should generally be
common among individual transactional accounts. - Loan and credit-card
related transactions should occur only for customers holding the
corresponding lending or card relationships. - Interest credits should
occur only where financially appropriate. - Exact transaction-type
shares must not be predetermined and should emerge from the synthetic
generation process.

## direction

**Description:** Direction of the monetary movement from the perspective
of the BTYT account affected by the transaction.

**Data type:** - String / Categorical

**Allowed values:** - `CREDIT` - `DEBIT`

**Category definitions:** - `CREDIT`: Funds are added to the account
balance. - `DEBIT`: Funds are deducted from the account balance.

**Rules:** - Must not be NULL. - Must be derived from
`transaction_type`. - Must not be generated independently. - Direction
is always defined from the perspective of the account identified by
`account_id`. - `CREDIT` transactions increase the account balance. -
`DEBIT` transactions decrease the account balance. - Historical
direction values must not be modified. - `direction` must remain fully
consistent with `transaction_type`.

**Transaction type mapping:**

  transaction_type        direction
  ----------------------- -----------
  `TRANSFER_IN`           `CREDIT`
  `TRANSFER_OUT`          `DEBIT`
  `CASH_DEPOSIT`          `CREDIT`
  `CASH_WITHDRAWAL`       `DEBIT`
  `DEBIT_PURCHASE`        `DEBIT`
  `SERVICE_PAYMENT`       `DEBIT`
  `CREDIT_CARD_PAYMENT`   `DEBIT`
  `LOAN_PAYMENT`          `DEBIT`
  `LOAN_DISBURSEMENT`     `CREDIT`
  `INTEREST_CREDIT`       `CREDIT`

**Data quality rule:** - Every `transaction_type` must map to exactly
one valid `direction`.

## channel

**Description:** Channel through which the BTYT account transaction was
initiated or processed.

**Data type:** - String / Categorical

**Allowed values:** - `MOBILE` - `WEB` - `ATM` - `BRANCH` - `POS` -
`AUTOMATIC`

**Category definitions:** - `MOBILE`: Transaction initiated through
BTYT's mobile banking application. - `WEB`: Transaction initiated
through BTYT's online banking platform. - `ATM`: Transaction processed
through an automated teller machine. - `BRANCH`: Transaction processed
through a physical BTYT branch or agency. - `POS`: Transaction processed
through a point-of-sale terminal using a BTYT debit card. - `AUTOMATIC`:
Transaction executed automatically through a previously established
banking instruction or contractual mechanism.

**Rules:** - Must not be NULL. - Every transaction must have exactly one
`channel`. - Channel must be compatible with `transaction_type`. -
Channel must not be generated independently from transaction type,
customer characteristics or temporal context. - `BRANCH` transactions
must occur during plausible branch operating days and hours. - `ATM`,
`MOBILE`, `WEB`, `POS` and `AUTOMATIC` transactions may occur outside
branch operating hours. - `POS` should primarily be associated with
`DEBIT_PURCHASE`. - `ATM` should primarily be associated with cash
withdrawals and, where applicable, cash deposits. - `AUTOMATIC` may be
associated with recurring service payments, loan payments, credit-card
payments and interest credits. - Historical channel values must not be
modified.

**Generation assumptions:** - Channel usage must not be uniformly
distributed. - Channel preferences should vary according to customer
age, customer type, geographic characteristics, product holdings and
transaction type. - Digital channels should represent a substantial
share of transactional activity. - Younger individual customers may have
a higher probability of using `MOBILE`. - Business customers may exhibit
greater use of `WEB` and `BRANCH` relative to typical retail
customers. - Cash-dependent customers and locations may exhibit greater
`ATM` or `BRANCH` activity. - Channel preferences should exhibit
customer-level persistence while allowing behavioral change over time. -
Digital-channel adoption may increase gradually across the historical
period. - Exact channel shares must not be predetermined and should
emerge from the synthetic generation process.

## amount

**Description:** Monetary value of the BTYT account transaction.

**Data type:** - Numeric / Decimal

**Currency:** - Expressed in the currency associated with the referenced
account.

**Rules:** - Must not be NULL. - Must be greater than zero. - `amount`
represents the absolute monetary value of the transaction. - Transaction
direction must be determined separately through `direction`; negative
transaction amounts must not be stored. - `amount` must remain
consistent with the currency of the referenced account. - Transaction
amounts must remain financially plausible relative to account balances,
customer financial characteristics and transaction type. - `DEBIT`
transactions must not normally exceed the available account balance
under the current no-overdraft model. - Transaction amounts must remain
consistent with related BTYT events where applicable. -
`LOAN_DISBURSEMENT` amounts should reconcile with the corresponding
lending relationship when the full or partial loan proceeds are credited
to an account. - `LOAN_PAYMENT` and `CREDIT_CARD_PAYMENT` amounts should
remain consistent with the relevant lending or card relationships. -
Historical transaction amounts must not be modified by subsequent
account activity.

**Generation assumptions:** - Transaction amounts must not be uniformly
or independently generated. - Amount distributions should vary
substantially by `transaction_type`. - Customer `monthly_income`,
business `annual_revenue`, account product, balance history and customer
behavior may influence transaction amounts. - Individual customers
should exhibit persistent transaction-size patterns while retaining
natural variation. - Business customers may generate substantially
larger and more volatile transactions. - Recurring transactions may have
relatively stable amounts across consecutive periods. - Salary-like
incoming transfers may recur monthly with similar amounts while allowing
periodic adjustments. - Service payments may exhibit recurring patterns
with gradual or seasonal changes. - Cash withdrawals should generally
involve smaller amounts than major bank transfers. - Loan disbursements
may generate unusually large incoming transactions relative to the
customer's normal account activity. - Tourism, agricultural and business
activity may create seasonal changes in transaction amounts. -
High-value outliers should exist but remain uncommon. - Exact
transaction-size distributions, averages and thresholds must not be
predetermined.

## counterparty_type

**Description:** Classification of the economic entity or relationship
on the opposite side of the BTYT account transaction.

**Data type:** - String / Categorical

**Allowed values:** - `EMPLOYER` - `MERCHANT` - `GOVERNMENT` -
`BTYT_CUSTOMER` - `OTHER_BANK` - `SERVICE_PROVIDER` - `SUPPLIER` -
`LOAN_ACCOUNT` - `CREDIT_CARD_ACCOUNT` - `OTHER`

**Category definitions:** - `EMPLOYER`: Organization or individual
associated with salary or employment-related payments. - `MERCHANT`:
Commercial establishment receiving payment for goods or services. -
`GOVERNMENT`: Public-sector entity involved in payments, transfers,
benefits or collections. - `BTYT_CUSTOMER`: Another BTYT customer
involved in an internal transfer. - `OTHER_BANK`: External financial
institution involved in an interbank transfer. - `SERVICE_PROVIDER`:
Utility, telecommunications, insurance or other recurring service
provider. - `SUPPLIER`: Supplier or commercial counterparty primarily
associated with business-customer activity. - `LOAN_ACCOUNT`: BTYT
lending relationship receiving or generating the account-side loan
movement. - `CREDIT_CARD_ACCOUNT`: BTYT credit-card relationship
receiving the account-side card payment. - `OTHER`: Counterparty that
does not fit another defined category.

**Rules:** - Must not be NULL. - Every transaction must have exactly one
`counterparty_type`. - `counterparty_type` must be compatible with
`transaction_type`. - `counterparty_type` describes the opposite
economic relationship and must not replace `transaction_type`. -
Salary-related activity should normally appear as
`TRANSFER_IN + EMPLOYER`. - `DEBIT_PURCHASE` should normally use
`MERCHANT`. - `CREDIT_CARD_PAYMENT` must use `CREDIT_CARD_ACCOUNT`. -
`LOAN_PAYMENT` and `LOAN_DISBURSEMENT` should normally use
`LOAN_ACCOUNT`. - Internal BTYT transfers may use `BTYT_CUSTOMER`. -
External transfers may use `OTHER_BANK`. - Historical counterparty
classifications must not be modified.

**Generation assumptions:** - Counterparty-type distributions must vary
by transaction type, customer type and account behavior. -
Payroll-account customers should have an increased probability of
recurring `TRANSFER_IN + EMPLOYER` transactions. - Business customers
should show substantially greater `SUPPLIER`, `GOVERNMENT`, `OTHER_BANK`
and business-transfer activity. - Individual customers should show
greater `MERCHANT` and `SERVICE_PROVIDER` activity. - Government-related
transactions may include salaries, benefits, tax payments or transfers
depending on transaction direction and customer profile. - Recurring
counterparties should exhibit persistence across time for the same
customer. - Exact counterparty distributions must not be predetermined
and should emerge from the synthetic generation process.

## transaction_branch_id

**Description:** Identifier of the BTYT branch or agency where an
in-person transaction was physically processed.

**Data type:** - String - NULL

**Reference:** - Foreign key to `branches.branch_id`.

**Rules:** - Must contain a valid `branch_id` when `channel = BRANCH`. -
Must be `NULL` when `channel IN (MOBILE, WEB, ATM, POS, AUTOMATIC)`. -
Represents the physical branch or agency where the transaction
occurred. - Must not be confused with `accounts.branch_id`, which
represents the office associated with the account relationship. - A
transaction may occur at a branch different from the branch associated
with the account. - The referenced branch must have been open at the
time of the transaction. - Historical transaction location must remain
unchanged even if the branch later closes. - ATM transactions are not
assigned through `transaction_branch_id`; ATM location modeling is
outside the current scope and will be reviewed during the global model
audit.

**Generation assumptions:** - Most branch-channel transactions should
occur at geographically reasonable BTYT offices. - Customers may
occasionally transact at branches outside their normal area due to
travel, relocation, work or other circumstances. - Customer residence
and `accounts.branch_id` may influence branch-selection probabilities
without determining them mechanically. - Large or centrally located
offices may process higher volumes of transactions from customers whose
accounts are associated with other branches. - Branch transaction
volumes should emerge from customer behavior, geography, branch
characteristics and channel preferences rather than predetermined
targets.

## transaction_status

**Description:** Processing outcome of the BTYT account transaction.

**Data type:** - String / Categorical

**Allowed values:** - `COMPLETED` - `FAILED`

**Category definitions:** - `COMPLETED`: Transaction was successfully
processed and produced the corresponding monetary effect on the BTYT
account. - `FAILED`: Transaction attempt was not successfully completed
and did not produce a monetary effect on the BTYT account.

**Rules:** - Must not be NULL. - Every transaction must have exactly one
`transaction_status`. - `COMPLETED` transactions must affect account
balances according to `direction` and `amount`. - `FAILED` transactions
must not affect account balances. - Only `COMPLETED` transactions may
contribute to `account_balances.total_inflows` and
`account_balances.total_outflows`. - `FAILED` represents an unsuccessful
transaction attempt rather than a completed transaction subsequently
reversed. - Transaction reversals are outside the scope of the current
dataset version. - `REVERSED` and `PENDING` are not valid values in the
current schema. - Historical transaction status must not be modified
after the analytical dataset is generated.

**Generation assumptions:** - The large majority of BTYT transaction
attempts should be `COMPLETED`. - `FAILED` transactions should represent
a relatively small minority under normal operating conditions. - Exact
failure rates must not be predetermined. - Failure probability may vary
according to: - transaction channel; - transaction type; - time of
day; - operational incidents; - system availability; - branch conditions
for in-person transactions; - random operational variation. - Failure
rates should normally remain low but may temporarily increase during
operational or technological incidents. - Different channels may exhibit
different failure patterns. - Branch-level differences should remain
moderate unless supported by a specific operational incident. - Final
success and failure distributions should emerge from the synthetic
generation process rather than fixed target percentages.

**Data quality rules:** - `transaction_status = COMPLETED` → transaction
contributes to account cash-flow reconciliation. -
`transaction_status = FAILED` → transaction must contribute `0` to
account cash-flow reconciliation.

## merchant_category

**Description:** Economic activity category associated with a merchant-related BTYT account transaction.

**Data type:**
- String / Categorical
- NULL

**Allowed values:**
- `GROCERIES`
- `RESTAURANTS`
- `FUEL`
- `RETAIL`
- `HEALTHCARE`
- `PHARMACY`
- `TRANSPORT`
- `TRAVEL`
- `ENTERTAINMENT`
- `EDUCATION`
- `UTILITIES`
- `TELECOMMUNICATIONS`
- `ECOMMERCE`
- `HOME`
- `AUTOMOTIVE`
- `PROFESSIONAL_SERVICES`
- `OTHER`

**Rules:**
- Must contain a valid category when the transaction represents a merchant purchase.
- Must normally be populated when `transaction_type = DEBIT_PURCHASE`.
- Must be NULL when no merchant is involved in the transaction.
- Must not identify a specific merchant.
- Must remain consistent with `transaction_type` and `counterparty_type`.
- `DEBIT_PURCHASE` transactions should normally have `counterparty_type = MERCHANT`.
- Merchant categories must use the same standardized BTYT taxonomy used in `credit_card_transactions`.
- Merchant categories should represent broad economic activity rather than individual businesses.

**Generation assumptions:**
- Merchant-category probabilities must not be uniformly generated.
- Individual customers should exhibit partially persistent consumption patterns while retaining natural variation.
- Category probabilities may depend on customer characteristics, transaction amount, geography, seasonality, channel and historical spending behavior.
- Debit and credit may be used for the same merchant categories.
- Payment-method differences must emerge from customer behavior rather than incompatible category definitions.
- Exact merchant-category shares must not be predetermined.


## failure_reason

**Description:** Primary reason why a BTYT transaction attempt failed to
complete.

**Data type:** - String / Categorical - NULL

**Allowed values:** - `INSUFFICIENT_FUNDS` - `TECHNICAL_ERROR` -
`AUTHENTICATION_FAILED` - `LIMIT_EXCEEDED` - `INVALID_DESTINATION` -
`NETWORK_ERROR` - `OTHER`

**Rules:** - Must be NULL when `transaction_status = COMPLETED`. - Must
contain a valid value when `transaction_status = FAILED`. - Must be
compatible with transaction type and channel. - `INSUFFICIENT_FUNDS`
should apply only to transactions requiring funds to leave an account. -
Technical and network failures may affect multiple transaction types and
channels. - Failure reasons must not be generated independently from
operational conditions. - Operational incidents may temporarily increase
the probability of specific failure reasons. - Failed transactions must
not affect account balances regardless of `failure_reason`.

**Generation assumptions:** - Failure reasons must not be uniformly
distributed. - Customer-related failures such as `INSUFFICIENT_FUNDS`
may depend on account balance and attempted transaction amount. -
`AUTHENTICATION_FAILED` may be more relevant to digital channels. -
`NETWORK_ERROR` and `TECHNICAL_ERROR` may increase during operational
incidents. - `LIMIT_EXCEEDED` may occur when transaction-specific
operational limits are exceeded. - Exact failure-reason distributions
must not be predetermined.

01 transaction_id 02 account_id 03 transaction_datetime 04
transaction_type 05 direction 06 channel 07 amount 08 counterparty_type
09 transaction_branch_id 10 transaction_status 11 merchant_category 12
failure_reason

## Cross-table reconciliation with `account_balances`

-   `transactions` is the event-level source for ordinary account
    cash-flow activity.
-   `account_balances` must not be generated as an independent random
    financial process.
-   For each `account_id + year_month`, completed account transactions
    must reconcile with the corresponding monthly snapshot.
-   Monthly inflows must equal the sum of completed account-credit
    movements represented in `transactions` for that account and month.
-   Monthly outflows must equal the sum of completed account-debit
    movements represented in `transactions` for that account and month.
-   Closing balance must evolve consistently from the prior balance and
    the month's completed account movements.
-   Failed transaction attempts, when represented, must have no
    financial effect.
-   Any intentionally introduced data-quality anomaly must be explicit,
    limited and generated after the underlying coherent financial
    history exists.
-   Account-side credit-card payments and loan movements may be
    generated from internal links to the relevant card or loan
    relationship without storing optional `card_id` or `loan_id` foreign
    keys in `transactions`.
-   The generator may maintain exact internal dates and internal
    relationship identifiers that are not persisted as columns when
    needed to enforce temporal and financial integrity.

## Phase 3 loan-transaction reconciliation rules

- Loan cash flows in `transactions` are generated from underlying loan events, not independently.
- A loan or credit-line draw credited to a BTYT account is represented as `LOAN_DISBURSEMENT`.
- A loan payment funded from a BTYT account is represented as `LOAN_PAYMENT`.
- Python may retain internal `loan_id` links although `loan_id` is not persisted in `transactions`.
- External loan payments affect the loan ledger and `loan_monthly_snapshot.actual_payment` without requiring a BTYT account transaction.
- `LOAN_PAYMENT` attempts remain subject to the account no-overdraft rule; insufficient funds must not be hidden by silently reducing the attempted amount.
- `P016` may generate multiple valid `LOAN_DISBURSEMENT` events over its lifetime, provided utilized exposure remains within the approved line.

## Phase 3 credit-card payment reconciliation rules

- `CREDIT_CARD_PAYMENT` represents the account side of a payment funded from a BTYT account toward a BTYT credit-card relationship.
- Such transactions must be generated from an underlying card-payment event and not independently.
- Python may retain an internal `card_id` link even though `card_id` is not persisted in `transactions`.
- Payments funded externally may reduce credit-card exposure without creating a row in `transactions`.
- A BTYT-funded card payment remains subject to the account no-overdraft rule; insufficient account funds must not be hidden by silently lowering the attempted payment amount.
- Once a card payment is successfully posted, the corresponding live card exposure must decline and available credit must be released immediately.
- The aggregate of BTYT-funded `CREDIT_CARD_PAYMENT` events must reconcile with the internally linked card-payment events used to generate `credit_card_monthly_snapshot`.

## Phase 3 behavioral-generation rules

### Persistent transaction behavior
- Transaction generation must use persistent customer-level behavioral preferences rather than treating each transaction as an independent random draw.
- Customer channel preferences, cash usage, spending intensity, recurring counterparties and debit-versus-credit tendencies should exhibit persistence over time while retaining meaningful month-to-month variation.
- Behavioral preferences may evolve gradually during 2021–2026 rather than remaining fixed forever.

### Contemporaneous financial information
- Historical transaction behavior must be generated from financial information available at that historical point.
- Python must use internally maintained contemporaneous income/revenue, liquidity, balances, product holdings and customer state rather than future master-table values.
- The final stored `monthly_income` or `annual_revenue` must not be retroactively applied as a constant driver of transactions across the full historical period.

### Debit-versus-credit choice
- When both debit/account funds and credit-card capacity are available, payment-method choice must emerge probabilistically from transaction amount, merchant category, available funds, available credit, installment availability, recent liquidity, customer preference and prior behavior.
- Debit and credit usage must not be independently randomized without reference to these conditions.
- The same customer may change payment-method preferences over time.

### Secular digital adoption
- The 2021–2026 generator may include a common gradual increase in digital-channel adoption.
- The strength and timing of digital adoption must vary by customer.
- A secular digital-adoption trend must be modeled separately from campaign effects so that later campaign analysis does not falsely attribute all digital growth to marketing interventions.

### Business behavior
- Business transaction patterns may vary by sector, company size, revenue scale and seasonality.
- Sector effects should influence transaction composition and timing probabilistically rather than predetermine performance.
- Agricultural, tourism, commerce, professional-services and other business sectors may exhibit distinct but overlapping transaction patterns.

## Phase 3 operational-incident and data-quality rules

### Ground truth before degradation
- Python must first generate a financially coherent ground-truth transaction history.
- Operational incidents and data-quality degradation are applied only after the underlying economic event history is complete.
- Data-quality rules must never be used to conceal incoherent financial generation.

### Operational incidents
- Incidents such as outages, connectivity failures, manual fallback processing or delayed system recovery may affect how real transactions are recorded.
- An incident may cause plausible delayed posting, missing optional classifications, duplicate records or missing transaction rows where explicitly configured.
- The underlying economic event remains distinct from the observed record.
- Incident definitions, exact affected offices, dates and severity belong to generator configuration rather than to an additional analytical CSV table.

### Controlled anomalies
- Deliberate anomalies must be sparse, plausible and reproducible.
- Primary identifiers and essential referential-integrity fields must not be nulled merely to create artificial dirtiness.
- Missingness may be introduced only where compatible with documented field semantics and the intended data-quality exercise.
- Duplicate or delayed records must originate from a known ground-truth event and be traceable in the generation audit.
- A small background rate of ordinary operational errors may exist outside major incidents.

### Auditability
- Python must retain an internal generation audit containing the random seed, generation version, incident configuration, affected ground-truth row identifiers and observed modifications.
- This audit is not part of the normal analytical dataset.
- The raw analytical CSVs contain the degraded observed data, while the audit preserves the coherent original state for validation.
