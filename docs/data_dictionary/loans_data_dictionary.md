# BTYT --- Loans Data Dictionary

## Table: `loans`

**Description:**\
Table containing individual lending contracts granted by BTYT to
customers.

**Grain:**\
One row represents one unique BTYT loan or credit facility.

**Primary key:**\
`loan_id`

**Purpose:**\
Represent customer-level lending relationships for business
intelligence, portfolio analysis and future credit-risk modeling.

**Included products:** - `P012` Personal Loan - `P013` Auto Loan -
`P014` Mortgage Loan - `P015` SME Loan - `P016` Business Credit Line -
`P017` Agricultural Loan - `P018` Business Leasing

------------------------------------------------------------------------

## Variables

## loan_id

**Description:** Unique internal identifier assigned to each BTYT
lending contract.

**Data type:** - String

**Format:** - `L` followed by seven numeric digits.

**Examples:** - `L0000001` - `L0000002` - `L0125487`

**Rules:** - Must be unique. - Must not be NULL. - Used as the primary
key of the `loans` table. - Must remain unchanged throughout the
lifetime of the lending contract. - Must not encode customer, product,
currency, branch, risk or status information. - Closed or fully repaid
loans retain their original `loan_id`.

## customer_id

**Description:** Unique identifier of the BTYT customer who received the
loan or credit facility.

**Data type:** - String

**Reference:** - Foreign key to `customers.customer_id`.

**Rules:** - Must contain a valid `customer_id`. - Must not be NULL. -
One customer may hold multiple BTYT loans simultaneously or throughout
their banking relationship. - Multiple loans may therefore reference the
same `customer_id`. - The customer must have been registered with BTYT
before or during the loan's origination year. - Historical loans remain
associated with the original customer after repayment or closure. - Loan
ownership must be compatible with the corresponding product's
`target_customer_type`. - Customer status does not determine loan status
mechanically.

## product_id

**Description:** Identifier of the BTYT lending product associated with
the loan or credit facility.

**Data type:** - String

**Reference:** - Foreign key to `products.product_id`.

**Allowed values:** - `P012` Personal Loan - `P013` Auto Loan - `P014`
Mortgage Loan - `P015` SME Loan - `P016` Business Credit Line - `P017`
Agricultural Loan - `P018` Business Leasing

**Rules:** - Must contain a valid `product_id`. - Must not be NULL. -
Only products belonging to `RETAIL_LENDING` or `BUSINESS_LENDING` may
appear in the `loans` table. - The lending product must be compatible
with the customer's `customer_type`. - A loan cannot originate before
the corresponding product's `launch_year`. - One customer may hold
multiple loans associated with different lending products. - One
customer may also hold multiple contracts associated with the same
lending product. - `product_id` identifies the type of financing and not
the individual lending contract.

## branch_id

**Description:** Identifier of the BTYT branch or agency that originated
the loan or credit facility.

**Data type:** - String

**Reference:** - Foreign key to `branches.branch_id`.

**Rules:** - Must contain a valid `branch_id`. - Must not be NULL. -
Represents the BTYT office that originated or commercially manages the
lending relationship. - `branch_id` does not necessarily need to match
the customer's `primary_branch_id`. - A customer may hold different
loans originated through different BTYT offices. - The referenced branch
or agency must have been open when the loan was originated. - A loan
cannot originate from a branch before that branch's `opening_year`. -
Historical loan origin must remain associated with the original branch
even if that office later closes. - Closure of the originating branch
does not automatically imply loan closure, repayment or default.

**Generation assumptions:** - Most loans should be originated through
the customer's `primary_branch_id` or another geographically and
commercially reasonable BTYT office. - Geographic proximity should
influence loan origination probabilities without determining them
mechanically. - Larger offices may originate greater lending volumes. -
Certain products may show stronger geographic patterns: -
`Agricultural Loan` may be more common in interior and EAST-region
offices. - Business lending may have greater concentration in larger or
commercially important branches. - Retail lending should remain broadly
distributed across the network. - Historical BTYT offices may retain
lending relationships beyond their immediate geographic area. - Digital
or remotely assisted lending processes may weaken the relationship
between customer residence and originating branch. - Exact branch-level
loan volumes must not be predetermined and should emerge from the
synthetic generation process.

## origination_year

**Description:** Year in which the specific BTYT loan or credit facility
was originally granted to the customer.

**Data type:** - Integer

**Format:** - YYYY

**Rules:** - Must not be NULL. - Must represent a valid year. - Must not
be later than the 2026. - Must be equal to or later than the customer's
`registration_year`. - Must be equal to or later than the corresponding
lending product's `launch_year`. - Must be equal to or later than the
originating branch's `opening_year`. - `origination_year` represents the
start of this specific lending contract and not the beginning of the
customer's relationship with BTYT. - A customer may originate additional
loans in later years. - Multiple loans belonging to the same customer
may therefore have different `origination_year` values. - Historical
loans retain their original `origination_year` after repayment, closure
or default.

**Generation assumptions:** - Loan originations must not be uniformly
distributed across years. - Origination probabilities may vary according
to customer tenure, customer financial profile, product type, branch
activity, business sector and economic conditions. - Customers should
not automatically receive lending products when they register with
BTYT. - Existing customers may acquire loans many years after their
initial registration. - Mortgage, auto, agricultural and business
lending should generally show different origination patterns. -
Macroeconomic periods may influence overall credit demand and
origination volumes without determining individual outcomes. - Branch
expansion and commercial campaigns may temporarily influence lending
activity. - Exact annual origination volumes must not be predetermined
and should emerge from the synthetic generation process.

## currency

**Description:** Currency in which the specific BTYT loan or credit
facility is denominated.

**Data type:** - String / Categorical

**Allowed values:** - `UYU` - `USD`

**Rules:** - Must not be NULL. - Every loan must be denominated in
exactly one currency. - `currency` represents the contractual currency
of the specific lending relationship. - If `products.currency = UYU`,
the loan must have `currency = UYU`. - If `products.currency = USD`, the
loan must have `currency = USD`. - If `products.currency = MULTI`, the
specific loan may be denominated in either `UYU` or `USD`. - Currency
must remain consistent with all monetary values associated with the
lending contract. - Currency conversion for analytical comparison must
be performed separately and must not alter the original contractual
currency.

**Generation assumptions:** - Currency selection must not be uniform
across lending products. - `Personal Loan` should be strongly
concentrated in `UYU`. - `Auto Loan` may be denominated in either `UYU`
or `USD`. - `Mortgage Loan` may be denominated in either `UYU` or
`USD`. - Business lending may have a greater probability of USD
denomination than retail lending. - `Agricultural Loan` should have a
meaningful probability of USD denomination due to the characteristics of
Uruguay's agricultural and export-oriented economy. - `Business Leasing`
may also have substantial USD participation, particularly for imported
equipment or vehicles. - Customer income or revenue characteristics may
influence currency selection. - Business sector may influence currency
selection, particularly for export-oriented activities. - Exact UYU/USD
shares must not be predetermined and should emerge from the synthetic
generation process.

## original_amount

**Description:** Original principal amount granted by BTYT when the loan
or credit facility was originated.

**Data type:** - Numeric / Decimal

**Currency:** - Expressed in the contractual currency defined by
`currency`.

**Rules:** - Must not be NULL. - Must be greater than zero. - Represents
the original principal amount granted at loan origination. - Must remain
unchanged throughout the lifetime of the lending contract. - Must not be
interpreted as the current outstanding balance. - `original_amount` must
be expressed in the currency specified by `loans.currency`. - Monetary
comparisons across currencies require a separate currency conversion
process. - The amount should be broadly compatible with the lending
product and customer financial profile without being mechanically
determined by them. - `original_amount` must not deterministically
define loan status, repayment behavior or credit risk.

**Generation assumptions:** - Loan amounts must be positively skewed
rather than uniformly distributed. - Typical loan amounts should vary
substantially by `product_id`. - `Personal Loan` should generally
involve smaller amounts than mortgage or business lending. - `Auto Loan`
amounts should reflect plausible vehicle-financing needs. -
`Mortgage Loan` should generally involve larger amounts and longer
financing relationships. - Business lending amounts may be influenced by
`annual_revenue`, `company_size` and `business_sector`. -
`Agricultural Loan` amounts may vary substantially according to business
scale and financing needs. - `Business Leasing` amounts may be
relatively high when financing vehicles, machinery or productive
equipment. - Customer `monthly_income` may influence retail lending
amounts. - High-income or high-revenue customers should have a greater
probability of receiving larger loans, but substantial variation must
remain. - Currency may influence nominal amount distributions and must
be considered during generation. - Extreme high-value loans should exist
but represent a small minority of contracts. - Exact product-level
averages, medians and ranges must not be predetermined. - Final lending
distributions should emerge from the synthetic generation process within
plausible financial constraints.

## term_months

**Description:** Original contractual term of the BTYT loan or credit
facility, expressed in months.

**Data type:** - Integer

**Unit:** - Months

**Rules:** - Must not be NULL. - Must be greater than zero. - Represents
the original contractual repayment term agreed at loan origination. -
Must remain unchanged for the historical loan record even if the loan is
later prepaid, refinanced or restructured. - `term_months` must be
broadly compatible with the lending product. - The term must not be
interpreted as the actual number of months the loan ultimately remains
outstanding. - Shorter or longer repayment periods may occur within the
same product. - `term_months` must not deterministically define loan
status, repayment behavior or credit risk.

**Generation assumptions:** - Term distributions must vary substantially
across lending products. - `Personal Loan` should generally have shorter
terms than mortgage lending. - `Auto Loan` should typically have
medium-term repayment schedules. - `Mortgage Loan` should generally have
the longest contractual terms. - `SME Loan`, `Agricultural Loan` and
`Business Leasing` should support a broad range of terms depending on
financing purpose and business characteristics. - `Business Credit Line`
may have shorter contractual horizons or renewable structures compared
with traditional installment loans. - Loan amount may moderately
influence expected term length. - Customer income or business revenue
may influence the feasible combination of amount and term without
determining it mechanically. - Exact term distributions and
product-level averages must not be predetermined. - The final
relationship between loan amount, term and customer characteristics
should emerge from the synthetic generation process within plausible
lending constraints.

## rate_type

**Description:** Interest-rate structure defined for the BTYT lending
contract.

**Data type:** - String / Categorical

**Allowed values:** - `FIXED` - `VARIABLE` - `MIXED`

**Category definitions:** - `FIXED`: The contractual interest rate
remains unchanged throughout the loan under normal conditions. -
`VARIABLE`: The contractual interest rate may change over time according
to the loan's pricing conditions or reference mechanism. - `MIXED`: The
loan combines an initial fixed-rate period with a later variable-rate
period.

**Rules:** - Must not be NULL. - Every loan must have exactly one
`rate_type`. - `rate_type` represents the contractual rate structure and
remains unchanged throughout the historical loan record. - The current
interest rate must not be inferred directly from `rate_type`. - Actual
rate evolution for `VARIABLE` and `MIXED` loans must be modeled
separately in a time-dependent lending table. - `rate_type` should be
compatible with the lending product, currency and contractual term
without being mechanically determined by them. - `rate_type` must not
deterministically define repayment behavior, loan status or credit risk.

**Generation assumptions:** - Rate-type probabilities should vary across
lending products. - Shorter-term retail lending may have a greater
probability of `FIXED` rates. - Mortgage, agricultural and business
lending may have greater probabilities of `VARIABLE` or `MIXED`
structures. - Longer contractual terms may increase the probability of
non-fixed rate structures. - Currency may influence rate-type
probabilities. - Product, term and customer characteristics should
affect probabilities without determining the outcome. - Exact shares of
`FIXED`, `VARIABLE` and `MIXED` loans must not be predetermined. - Final
rate-type distributions should emerge from the synthetic generation
process within plausible lending constraints.

## initial_interest_rate

**Description:** Annual nominal interest rate established when the BTYT
lending contract was originated.

**Data type:** - Numeric / Decimal

**Unit:** - Percentage (%)

**Rules:** - Must not be NULL. - Must be greater than zero. - Represents
the contractual annual interest rate applicable at loan origination. -
Must be stored as a percentage value (e.g. `8.50` represents 8.50%). -
`initial_interest_rate` remains unchanged as a historical origination
attribute even if the applicable rate changes later. - For `FIXED`
loans, the applicable interest rate should normally remain equal to
`initial_interest_rate` throughout the contractual life of the loan. -
For `VARIABLE` loans, subsequent interest rates may differ from
`initial_interest_rate`. - For `MIXED` loans, `initial_interest_rate`
represents the rate applicable during the initial fixed-rate period. -
Subsequent rate evolution must be represented in the time-dependent loan
history rather than by modifying `initial_interest_rate`. - The initial
rate should be broadly compatible with product, currency, origination
period, term and customer characteristics. - `initial_interest_rate`
must not deterministically define repayment behavior, loan status or
credit risk.

**Generation assumptions:** - Initial interest rates must not be uniform
across loans. - Rate distributions should vary according to
`product_id`, `currency`, `origination_year`, `term_months` and
`rate_type`. - Market and macroeconomic conditions at the time of
origination should influence expected interest rates. - UYU and USD
lending should have different rate distributions. - Longer-term lending
may show different pricing structures from short-term lending. -
Customer financial characteristics may moderately influence pricing. -
Business characteristics such as `company_size`, `annual_revenue` and
`business_sector` may influence business-loan pricing. - Customers with
otherwise similar characteristics may still receive different rates. -
Exact average rates and product-level spreads must not be
predetermined. - Final pricing patterns should emerge from the synthetic
generation process within plausible financial constraints.

## loan_status

**Description:** Current or final status of the BTYT lending contract.

**Data type:** - String / Categorical

**Allowed values:** - `ACTIVE` - `PAID_OFF` - `DEFAULTED` -
`RESTRUCTURED` - `WRITTEN_OFF`

**Category definitions:** - `ACTIVE`: Loan remains in force and has an
outstanding contractual balance. - `PAID_OFF`: Loan has been fully
repaid under normal or early repayment conditions. - `DEFAULTED`: Loan
has entered a defined state of serious repayment delinquency or
contractual default. - `RESTRUCTURED`: Loan terms have been materially
modified through a renegotiation or restructuring process. -
`WRITTEN_OFF`: BTYT has recognized the remaining debt as uncollectible
and removed it from active recoverable lending exposure.

**Rules:** - Must not be NULL. - Every loan must have exactly one
`loan_status` at the `2026-12-31`. - `loan_status` represents the status
of the lending contract and is independent from `customer_status`. - A
customer may remain `ACTIVE` with BTYT while having a `PAID_OFF`,
`DEFAULTED`, `RESTRUCTURED` or `WRITTEN_OFF` historical loan. -
`PAID_OFF` does not imply customer closure. - `DEFAULTED` does not
automatically imply `WRITTEN_OFF`. - A `DEFAULTED` loan may later be
restructured or recovered. - `RESTRUCTURED` represents a materially
modified lending relationship and should not be treated as equivalent to
normal repayment. - `WRITTEN_OFF` should represent a small minority of
loans. - Historical loan status transitions must be modeled separately
if detailed status history is required. - `loan_status` must be
temporally consistent with repayment history and any future loan-level
monthly or payment tables.

**Generation assumptions:** - The majority of loans should be either
`ACTIVE` or `PAID_OFF`. - `DEFAULTED`, `RESTRUCTURED` and especially
`WRITTEN_OFF` should represent smaller portions of the portfolio. -
Exact status proportions must not be predetermined. - Status
probabilities may be influenced by: - product type; - original amount; -
contractual term; - currency; - interest-rate structure; - customer
income or business revenue; - customer tenure; - payment behavior; -
macroeconomic conditions; - geographic and sector characteristics; -
random individual variation. - No single customer or loan characteristic
should determine default mechanically. - Final default, restructuring
and write-off patterns should emerge from the synthetic generation
process within plausible credit-risk constraints.

## closing_year

**Description:** Year in which the BTYT lending contract ceased to
remain active under its original relationship.

**Data type:** - Integer - NULL

**Format:** - YYYY - NULL

**Rules:** - Must be `NULL` when `loan_status = ACTIVE`. - Must contain
a valid year when the lending relationship has reached a final or
materially resolved state. - Must be equal to or later than
`origination_year`. - Must not be later than the 2026. - `closing_year`
must be temporally consistent with repayment and status history. -
`PAID_OFF` loans must have a valid `closing_year`. - `WRITTEN_OFF` loans
must have a valid `closing_year`. - `DEFAULTED` and `RESTRUCTURED` loans
must have a valid `closing_year` when the original contract relationship
has been terminated or replaced. - `closing_year` does not by itself
indicate whether the loan ended through normal repayment, default,
restructuring or write-off; this information is represented by
`loan_status`.

**Generation assumptions:** - Loan closing years must not be uniformly
distributed. - Contract duration should be broadly consistent with
`term_months`, while early repayment, default and restructuring may
cause substantial deviations. - Some loans may be paid off before their
original contractual maturity. - Defaults, restructurings and write-offs
may occur before scheduled maturity. - Exact duration and closure
patterns must emerge from the synthetic generation process rather than
from predetermined targets.

## Phase 3 loan-generation integrity rules

### Contract-driven repayment structure
- Standard amortizing loans derive repayment obligations from `original_amount`, `term_months`, `rate_type`, the applicable interest-rate path and product characteristics.
- Fixed-rate loans retain a stable contractual rate unless an explicit restructuring changes the contract.
- Variable-rate loans use a common time-varying reference-rate environment plus a loan-specific contractual spread.
- Mixed-rate loans use an internally maintained transition from an initial fixed-rate phase to a variable-rate phase.
- Reference-rate paths and exact repricing dates may remain internal to Python.

### Business Credit Line — P016
- `P016` is a revolving business credit line, not a standard fully disbursed amortizing loan.
- For `P016`, `original_amount` represents the approved credit-line limit.
- Python internally maintains utilized balance, available line and draw/repayment events.
- `outstanding_balance` may rise after valid drawdowns and fall after repayments.
- A drawdown credited to a BTYT account generates the corresponding `LOAN_DISBURSEMENT`.
- Utilized exposure must not exceed the approved line under normal generation.

### Financial balance evolution
- `outstanding_balance` is derived from the underlying loan ledger and is not independently sampled.
- `arrears_amount` is the overdue component of exposure and must not be added again to `outstanding_balance`.
- Under normal generation, `arrears_amount` must not exceed economically outstanding exposure.

### Default, restructuring and write-off
- Serious delinquency raises default probability but does not mechanically force `DEFAULTED` at a single DPD threshold.
- Default must emerge from sufficiently severe or persistent deterioration and credit-state logic.
- Restructuring retains the same `loan_id` and creates a revised internal repayment schedule.
- A restructured loan fully repaid before cutoff may finish `PAID_OFF`; one still active under the revised agreement may finish `RESTRUCTURED`.
- `WRITTEN_OFF` must follow a plausible deterioration/default history, not appear directly from a performing state.
- Post-write-off recovery modeling is outside the current BTYT scope.

### Prepayment
- Standard amortizing loans may receive partial or full prepayments.
- Payments above the scheduled obligation may reduce principal ahead of schedule.
- Full early repayment must produce a coherent `PAID_OFF` state and closing year.
