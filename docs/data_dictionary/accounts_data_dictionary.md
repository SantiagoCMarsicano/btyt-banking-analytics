# BTYT --- Accounts Data Dictionary

## Table: `accounts`

**Description:**\
Table containing BTYT customer deposit and transactional account
relationships.

**Grain:**\
One row represents one unique BTYT account.

**Primary key:**\
`account_id`

**Purpose:**\
Represent individual account instances linked to BTYT customers and
products, including transactional accounts, payroll accounts,
youth/student accounts and fixed-term deposits.

**Included product families:** - `TRANSACTIONAL_ACCOUNT` -
`SAVINGS_DEPOSIT`

**Included products:** - `P001` Savings Account UYU - `P002` Savings
Account USD - `P003` Current Account UYU - `P004` Current Account USD -
`P005` Payroll Account - `P006` Youth / Student Account - `P007`
Fixed-Term Deposit UYU - `P008` Fixed-Term Deposit USD

**Excluded products:** - Card products are modeled separately. - Lending
products are modeled separately.

------------------------------------------------------------------------

## Variables

## account_id

**Description:** Unique internal identifier assigned to each BTYT
account.

**Data type:** - String

**Format:** - `A` followed by seven numeric digits.

**Examples:** - `A0000001` - `A0000002` - `A0125487`

**Rules:** - Must be unique. - Must not be NULL. - Used as the primary
key of the `accounts` table. - Must remain unchanged throughout the
lifetime of the account. - Must not encode customer, product, currency,
branch or account status information. - Closed accounts retain their
original `account_id`.

## customer_id

**Description:** Unique identifier of the BTYT customer who owns the
account.

**Data type:** - String

**Reference:** - Foreign key to `customers.customer_id`.

**Rules:** - Must contain a valid `customer_id`. - Must not be NULL. -
One customer may own multiple BTYT accounts. - Multiple accounts may
belong to the same customer. - `customer_id` does not determine the
account product, currency, branch or status. - The referenced customer
must exist before or at the time the account is opened. - Historical
accounts remain associated with the original customer record even after
account closure.

## product_id

**Description:** Identifier of the BTYT product associated with the
account.

**Data type:** - String

**Reference:** - Foreign key to `products.product_id`.

**Allowed values:** - `P001` Savings Account UYU - `P002` Savings
Account USD - `P003` Current Account UYU - `P004` Current Account USD -
`P005` Payroll Account - `P006` Youth / Student Account - `P007`
Fixed-Term Deposit UYU - `P008` Fixed-Term Deposit USD

**Rules:** - Must contain a valid `product_id`. - Must not be NULL. -
Only products belonging to `TRANSACTIONAL_ACCOUNT` or `SAVINGS_DEPOSIT`
may appear in the `accounts` table. - Card and lending products must not
appear in this table. - A customer may hold multiple accounts associated
with different products. - A customer may also hold more than one
account associated with the same product when allowed by BTYT business
rules. - Product ownership must be compatible with
`products.target_customer_type`. - An account cannot be opened before
the corresponding product's `launch_year`.

## branch_id

**Description:** Identifier of the BTYT branch or agency associated with
the account.

**Data type:** - String

**Reference:** - Foreign key to `branches.branch_id`.

**Rules:** - Must contain a valid `branch_id`. - Must not be NULL. -
Represents the BTYT office associated with the account relationship. -
`branch_id` does not necessarily need to match the customer's
`primary_branch_id`. - A customer may hold accounts associated with
different BTYT offices. - The referenced branch or agency must have been
open when the account was created. - An account cannot originate from a
branch before that branch's `opening_year`. - Geographic proximity
between customer residence and account branch should influence account
assignment but must not determine it mechanically. - Accounts originated
through digital channels must still be assigned to a BTYT branch or
agency for administrative and commercial purposes. - Historical account
origin must be preserved even if the associated branch later closes.

**Generation assumptions:** - Most accounts should be associated with
the customer's `primary_branch_id` or another geographically reasonable
BTYT office. - Customers with long banking relationships may hold
accounts associated with multiple branches due to relocation, historical
relationships or subsequent product acquisition. - Larger branches may
originate and administer greater numbers of accounts. - Customers
residing in localities without a BTYT office may hold accounts
associated with nearby offices, regional hubs or metropolitan
branches. - Digital acquisition may weaken the relationship between
customer residence and account branch. - Branch closures must not
automatically cause account closure. - Accounts associated with closed
branches may remain active and continue being serviced through another
office or digital channels. - Exact branch-account distributions must
not be predetermined and should emerge from the synthetic generation
process.

## opening_year

**Description:** Year in which the BTYT account was originally opened.

**Data type:** - Integer

**Format:** - YYYY

**Rules:** - Must not be NULL. - Must represent a valid year. - Must not
be later than the 2026. - Must be equal to or later than the customer's
`registration_year`. - Must be equal to or later than the corresponding
product's `launch_year`. - Must be equal to or later than the associated
branch's `opening_year`. - `opening_year` represents the opening of this
specific account and not the beginning of the customer's overall
relationship with BTYT. - A customer may open additional accounts many
years after their original `registration_year`. - Multiple accounts
belonging to the same customer may therefore have different
`opening_year` values. - Closed accounts retain their original
`opening_year`.

**Generation assumptions:** - Account openings must not be uniformly
distributed across years. - The probability of account opening may vary
according to customer tenure, product availability, customer
characteristics, branch expansion and commercial activity. - Newly
registered customers should have a relatively high probability of
opening at least one account during their `registration_year`. -
Existing customers may acquire additional accounts in later years. -
Products introduced later in BTYT's history may be adopted both by new
and existing customers. - Branch openings may generate increased account
acquisition in their surrounding geographic areas. - Exact
account-opening distributions must not be predetermined and should
emerge from the synthetic generation process. \## account_status

**Description:** Current status of the specific BTYT account.

**Data type:** - String / Categorical

**Allowed values:** - `ACTIVE` - `CLOSED`

**Category definitions:** - `ACTIVE`: Account remains open and available
for normal banking use according to the characteristics of the
product. - `CLOSED`: Account has been permanently closed.

**Rules:** - Every account must have exactly one `account_status`. -
Must not be NULL. - `account_status` applies to the specific account and
is independent from `customer_status`. - A customer with
`customer_status = ACTIVE` may have one or more accounts with
`account_status = CLOSED`. - A customer with `customer_status = CLOSED`
must not have any account remaining `ACTIVE` after the end of the
customer relationship. - Closure of one account does not imply closure
of other accounts belonging to the same customer. - Closure of the
associated branch or agency does not automatically imply account
closure. - Account closure does not imply financial distress, default or
customer churn.

**Generation assumptions:** - The majority of accounts should remain
`ACTIVE`. - The exact proportion of active and closed accounts must not
be predetermined. - Account closure probabilities may depend on: -
account age; - product type; - customer status; - customer tenure; -
activity level; - acquisition of substitute products; - branch-network
changes; - customer relocation; - digital adoption; - random individual
variation. - Older accounts should generally have had more opportunity
to become `CLOSED`, but age must not determine closure automatically. -
Customers may close one product while deepening their relationship with
BTYT through other products. - Account closures should emerge from a
multivariable probabilistic process rather than from fixed product-level
closure rates.

## closing_year

**Description:** Year in which the specific BTYT account was permanently
closed.

**Data type:** - Integer - NULL

**Format:** - YYYY - NULL

**Rules:** - Must be `NULL` when `account_status = ACTIVE`. - Must
contain a valid year when `account_status = CLOSED`. - Must be equal to
or later than `opening_year`. - Must not be later than the 2026. -
`closing_year` represents the closure of the specific account and not
necessarily the end of the customer's overall relationship with BTYT. -
A customer may close an account while maintaining other active accounts
or products. - Account closure does not imply customer churn, credit
default or financial distress. - If `customer_status = CLOSED`, no
account may remain active after the customer's `closing_year`. - If both
the customer and the account are `CLOSED`, the account's `closing_year`
must be equal to or earlier than the customer's `closing_year`. -
Closure of the associated branch or agency does not automatically
determine the account's `closing_year`.

**Generation assumptions:** - Account closing years must not be
uniformly distributed. - Account closure timing should emerge from the
account-level closure process defined by `account_status`. - Older
accounts should generally have had greater historical exposure to
potential closure. - Accounts may remain active for several decades. -
Very short-lived accounts should also exist but should not dominate the
dataset. - Branch closures may increase the probability of subsequent
account closure without determining the outcome. - Customers may close
older accounts after adopting substitute or more suitable BTYT
products. - Account closure patterns should reflect interactions between
customer characteristics, product characteristics, geography, banking
behavior and random individual variation. - Exact closure rates and
relationship durations must not be predetermined.

## opening_channel

**Description:** Channel through which the BTYT account was originally
opened.

**Data type:** - String / Categorical

**Allowed values:** - `BRANCH` - `DIGITAL` - `REMOTE_ASSISTED`

**Category definitions:** - `BRANCH`: Account opened through an
in-person process at a BTYT branch or agency. - `DIGITAL`: Account
opened primarily through BTYT's digital channels without in-person
assistance. - `REMOTE_ASSISTED`: Account opened remotely with support
from a BTYT employee or assisted service channel.

**Rules:** - Every account must have exactly one `opening_channel`. -
Must not be NULL. - `opening_channel` represents the original
account-opening channel and remains unchanged throughout the account's
lifetime. - `opening_channel` is independent from `branch_id`. -
Digitally or remotely opened accounts must still be associated with a
valid `branch_id` for administrative and commercial purposes. - Campaign
participation must not be encoded through `opening_channel`; campaign
relationships are modeled separately.

**Generation assumptions:** - Older accounts should have a much higher
probability of `BRANCH` opening. - `DIGITAL` and `REMOTE_ASSISTED`
should become progressively more common in more recent years. - Product
type may influence opening-channel probabilities. - Youth-oriented and
transactional products may have higher digital-opening probabilities in
recent periods. - Certain business products may remain more likely to be
opened through `BRANCH` or `REMOTE_ASSISTED`. - Geographic distance from
a BTYT office may increase the probability of digital or remotely
assisted acquisition. - Exact channel shares must not be
predetermined. - The final distribution of account-opening channels
should emerge from historical period, product characteristics, customer
characteristics, geography and random variation.

## Phase 3 account and money integrity rules

### Pre-2021 opening state
- Accounts opened before `2021-01-01` may enter the observational dataset with a non-zero opening balance.
- The opening balance at the start of the observational period represents the accumulated financial state produced by pre-2021 history that is outside the transaction-level dataset.
- Python must generate this initial state from plausible customer, product, account-age, currency, income/revenue and savings-behavior characteristics.
- The generator must not fabricate pre-2021 transaction rows merely to justify the initial 2021 balance.

### No-overdraft rule
- The current BTYT model does not include authorized overdraft facilities.
- A completed account debit must not reduce the available account balance below zero.
- When an attempted debit exceeds available funds, the attempted transaction must fail rather than being silently reduced to the available balance.
- Any later partial or lower-value attempt must be represented as a separate transaction attempt.

### Fixed-term deposit behavior
- Accounts linked to `P007` (Fixed-Term Deposit UYU) or `P008` (Fixed-Term Deposit USD) are contractual savings products and must not behave like ordinary transactional accounts.
- Their detailed term, exact maturity date, applicable rate and renewal state may be maintained internally by the Python generator and need not be persisted as additional columns in `accounts`.
- Funds placed in a fixed-term deposit are not freely available for ordinary spending during the contractual term.
- Fixed-term deposits may normally receive the initial funding transfer, derived interest credits and maturity/renewal-related transfers.
- Ordinary debit-card purchases, service payments, credit-card payments, loan payments and routine cash withdrawals must not be generated from fixed-term deposit accounts.
- Interest credited to fixed-term deposits must be financially derived from principal, rate and elapsed time rather than sampled as an unrelated random transaction.

### Closed-account balance rule
- A permanently `CLOSED` account must normally reach a final economic balance of zero before termination.
- Remaining funds must be resolved through a legitimate financial movement before closure.
- A non-zero residual balance on a permanently closed account is not part of normal BTYT generation and may appear only when deliberately introduced later as a controlled data-quality anomaly.
