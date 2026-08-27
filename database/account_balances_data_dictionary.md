# BTYT --- Account Balances Data Dictionary

## Table: `account_balances`

**Description:**\
Monthly historical snapshot of balances and account-level cash flow
activity for BTYT deposit and transactional accounts.

**Grain:**\
One row represents one BTYT account in one calendar month.

**Primary key:**\
Composite key: `account_id` + `year_month`

**Purpose:**\
Track the monthly evolution of account balances and aggregate
inflows/outflows for business intelligence, branch performance, customer
behavior and funding analysis.

**Reference:** - `account_id` → foreign key to `accounts.account_id`

------------------------------------------------------------------------

## Variables

## account_id

**Description:** Unique identifier of the BTYT account associated with
the monthly balance record.

**Data type:** - String

**Reference:** - Foreign key to `accounts.account_id`.

**Rules:** - Must contain a valid `account_id`. - Must not be NULL. -
One account may appear in multiple rows, with one row per calendar
month. - The account must have been opened on or before the
corresponding `year_month`. - Historical balance records remain
associated with the original `account_id` after account closure.

## year_month

**Description:** Calendar month represented by the account balance
snapshot.

**Data type:** - String / Period

**Format:** - `YYYY-MM`

**Examples:** - `2024-01` - `2025-08`

**Rules:** - Must not be NULL. - Must represent a valid calendar
month. - The combination `account_id + year_month` must be unique. -
`year_month` must not precede the account's `opening_year`. - No records
should exist after the account has been permanently closed, except when
required to represent the final closing month. - Monthly records should
be continuous during the active life of the account unless an
intentional data-quality or operational incident creates missing
observations.

## opening_balance

**Description:** Account balance at the beginning of the calendar month.

**Data type:** - Numeric / Decimal

**Currency:** - Expressed in the currency of the account's associated
product.

**Rules:** - Must not be NULL. - Must be greater than or equal to
zero. - Represents the account balance at the beginning of
`year_month`. - For consecutive monthly observations, `opening_balance`
should normally equal the previous month's `closing_balance`. - For the
first monthly observation of a newly opened account, `opening_balance`
may be zero. - `opening_balance` must be interpreted in the currency
associated with the account's `product_id`. - Currency must not be
duplicated as a separate field in `account_balances`. - Historical
balances must not be overwritten by subsequent account activity. -
Intentional data-quality incidents may create exceptional
inconsistencies or missing observations.

**Generation assumptions:** - Opening balances must not be uniformly
distributed. - Balance distributions should vary according to account
product and customer characteristics. - Customer income, business
revenue, tenure and other financial characteristics may influence
expected balances without determining them mechanically. - Fixed-term
deposits should generally exhibit different balance patterns from
transactional accounts. - Business customers may have substantially
larger balances than individual customers. - USD and UYU accounts should
have different nominal balance distributions. - Extreme high-balance
observations should exist but represent a small minority. - Exact
balance averages, medians and distributions must not be predetermined.

## total_inflows

**Description:** Total monetary value of funds credited to the BTYT
account during the calendar month.

**Data type:** - Numeric / Decimal

**Currency:** - Expressed in the currency of the account's associated
product.

**Rules:** - Must not be NULL. - Must be greater than or equal to
zero. - Represents the aggregated value of incoming funds during
`year_month`. - A value of `0` is valid for accounts with no incoming
monetary activity during the month. - `total_inflows` must be
interpreted in the currency associated with the account's
`product_id`. - Must not include the month's `opening_balance`. -
Internal transfers received from another BTYT account may be included as
inflows to the receiving account. - Reversals, adjustments and
exceptional operational corrections should be handled consistently
during data generation. - Historical values must not be overwritten by
subsequent activity.

**Generation assumptions:** - Monthly inflows must not be uniformly
distributed. - Inflow patterns should vary according to product type,
customer type and customer financial characteristics. - Payroll accounts
should tend to show recurring inflow patterns related to customer
income. - Business accounts may show larger and more volatile monthly
inflows. - Savings accounts may exhibit less regular inflow patterns
than payroll accounts. - Fixed-term deposits should exhibit
substantially different cash-flow behavior from transactional
accounts. - Seasonality may influence inflows, particularly for business
and agricultural customers. - Customer income or business revenue should
influence expected inflows without determining them mechanically. -
Months with zero or unusually low inflows should occur naturally. -
Extreme high-inflow months should exist but represent a small
minority. - Exact inflow distributions must not be predetermined.

## total_outflows

**Description:** Total monetary value of funds debited from the BTYT
account during the calendar month.

**Data type:** - Numeric / Decimal

**Currency:** - Expressed in the currency of the account's associated
product.

**Rules:** - Must not be NULL. - Must be greater than or equal to
zero. - Represents the aggregated value of outgoing funds during
`year_month`. - A value of `0` is valid for accounts with no outgoing
monetary activity during the month. - `total_outflows` must be
interpreted in the currency associated with the account's
`product_id`. - Internal transfers sent to another BTYT account may be
included as outflows from the originating account. - Payments,
withdrawals, transfers and other debit operations may contribute to
`total_outflows`. - Reversals, adjustments and exceptional operational
corrections should be handled consistently during data generation. -
Historical values must not be overwritten by subsequent activity. -
Monthly outflows must remain financially consistent with the available
funds and other account movements.

**Generation assumptions:** - Monthly outflows must not be uniformly
distributed. - Outflow patterns should vary according to product type,
customer type and customer financial characteristics. - Payroll and
transactional accounts should generally exhibit more frequent outgoing
activity than savings-oriented products. - Business accounts may show
substantially larger and more volatile monthly outflows. - Fixed-term
deposits should exhibit substantially different outflow behavior from
transactional accounts. - Customer income or business revenue may
influence expected outflows without determining them mechanically. -
Seasonality may affect customer and business spending patterns. - Months
with zero or unusually low outflows should occur naturally. - Extreme
high-outflow months should exist but represent a small minority. - Exact
outflow distributions must not be predetermined.

## closing_balance

**Description:** Account balance at the end of the calendar month.

**Data type:** - Numeric / Decimal

**Currency:** - Expressed in the currency of the account's associated
product.

**Rules:** - Must not be NULL. - Must be greater than or equal to
zero. - Represents the account balance at the end of `year_month`. -
Must be expressed in the same currency as `opening_balance`,
`total_inflows` and `total_outflows`. - Under normal conditions,
`closing_balance` must satisfy:

`closing_balance = opening_balance + total_inflows - total_outflows`

-   For consecutive monthly observations, `closing_balance` should
    normally equal the following month's `opening_balance`.
-   Negative balances and overdrafts are outside the scope of the
    current dataset version.
-   For the final month of a closed account, `closing_balance` should
    normally reach zero or a financially consistent residual amount
    before definitive closure.
-   Historical closing balances must not be modified by subsequent
    account activity.
-   Intentional data-quality or operational incidents may generate a
    small number of missing or inconsistent observations, which should
    remain exceptional and identifiable.

**Generation assumptions:** - Closing balances must not be uniformly
distributed. - Balance distributions should vary according to product
type, customer type and customer financial characteristics. - Customer
income, business revenue, tenure and banking activity may influence
expected balances without determining them mechanically. - Business
accounts may exhibit larger and more volatile closing balances than
individual accounts. - Fixed-term deposits should exhibit different
balance dynamics from transactional accounts. - Seasonal patterns may
affect monthly balances. - Very high balances should exist but represent
a small minority. - Zero-balance months may occur naturally. - Exact
balance distributions must not be predetermined.

01 account_id 02 year_month 03 opening_balance 04 total_inflows 05
total_outflows 06 closing_balance

## Generation and reconciliation rule

`account_balances` is a derived monthly financial snapshot and must not
be generated independently from account transaction history.

For each `account_id + year_month`:

-   monthly inflows must reconcile with completed account-credit
    movements represented in `transactions`;
-   monthly outflows must reconcile with completed account-debit
    movements represented in `transactions`;
-   closing balance must evolve consistently from the prior month's
    balance and the month's completed financial movements;
-   failed transaction attempts must have no financial effect;
-   the first observed month may require an opening balance representing
    financial history prior to the observational window;
-   accounts opened before `2021-01-01` may therefore begin the dataset
    with a non-zero opening balance;
-   intentionally simulated data-quality incidents must be introduced
    only after a coherent underlying financial history has been
    generated.

The observational period for monthly snapshots is `2021-01` through
`2026-12`, subject to the active lifetime of each account.

## Phase 3 account-balance integrity rules

### Initial observational balance
- For accounts opened before `2021-01-01`, the first observed monthly balance may be non-zero.
- This value represents the coherent accumulated state of financial history before the transaction-level observational window.
- It must be generated from plausible account/customer characteristics and must not require artificial pre-2021 transaction rows.

### Exact monthly conservation
For each account and observed month, normal generation must satisfy the accounting identity:

`closing_balance = opening_balance + completed_inflows - completed_outflows`

where:
- `completed_inflows` are completed account-credit financial movements represented for that account and month;
- `completed_outflows` are completed account-debit financial movements represented for that account and month;
- failed transaction attempts have zero financial effect.

The next observed month's opening state must continue consistently from the prior month's closing state.

### Non-negative balances
- Under the current BTYT model, ordinary account balances must not become negative because authorized overdrafts are outside scope.
- Debit attempts that would produce a negative balance must fail before affecting the monthly snapshot.

### Fixed-term deposits
- Monthly snapshots for `P007` and `P008` must reflect their contractual nature.
- Principal should remain economically locked during the applicable term except for legitimate maturity/renewal events.
- Interest effects must reconcile with financially derived `INTEREST_CREDIT` transactions.
- Fixed-term deposit snapshots must not exhibit ordinary high-frequency spending-account behavior.

### Account closure
- The final economically valid balance of a permanently closed account must normally be zero.
- Any non-zero residual balance on a closed account may only be introduced later as an explicit controlled data-quality anomaly and must not arise from the coherent base generator.

### Data-quality separation
- Financially coherent balances must be generated before any deliberate missingness, duplication, delayed posting or other operational-data anomaly is introduced.
- Data-quality incidents must never be used to conceal an incoherent underlying accounting history.

## Phase 3 incident-aware balance rules

### Ground-truth reconciliation
- The coherent internal account ledger and ground-truth monthly balances must reconcile before any operational data-quality degradation is applied.
- Operational incidents must not alter the true economic balance merely because a transaction was recorded late, duplicated in an observed extract or omitted from an observed transaction file.

### Observed reconciliation anomalies
- A configured incident may cause the observed transaction extract to fail to reconcile with an otherwise correct monthly balance snapshot when a real transaction is missing or delayed in observed transaction data.
- Such discrepancies must be deliberate, sparse and traceable to the generation audit.
- Python must never create an unexplained balance discrepancy and subsequently label it as an incident.
- Any deliberate corruption of a balance snapshot itself must be separately configured and recorded rather than arising accidentally from the financial generator.

### Data-quality sequencing
- Financially coherent ground truth is generated first.
- Incident effects and controlled data-quality anomalies are applied second.
- Final exported raw data reflects the observed/degraded state intended for the ETL and data-quality exercise.
