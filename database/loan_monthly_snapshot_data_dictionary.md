# BTYT — Loan Monthly Snapshot Data Dictionary

## Table: `loan_monthly_snapshot`

**Description:**  

Monthly historical snapshot of the financial and repayment status of individual BTYT lending contracts.

**Grain:**  

One row represents one BTYT loan in one calendar month.

**Primary key:**  

Composite key: `loan_id` + `year_month`

**Purpose:**  

Track the monthly evolution of outstanding debt, applicable interest rates and repayment behavior for portfolio monitoring, business intelligence and future credit-risk modeling.

**Reference:**

- `loan_id` → foreign key to `loans.loan_id`

---

## Variables

## loan_id

**Description:** Unique identifier of the BTYT lending contract associated with the monthly snapshot.

**Data type:**

- String

**Reference:**

- Foreign key to `loans.loan_id`.

**Rules:**

- Must contain a valid `loan_id`.

- Must not be NULL.

- One loan may appear in multiple rows, with one row per calendar month.

- The loan must have originated on or before the corresponding `year_month`.

- Historical monthly records remain associated with the original `loan_id` after repayment, restructuring, default or write-off.

- Monthly observations must remain temporally consistent with the lifecycle of the corresponding lending contract.

## year_month

**Description:** Calendar month represented by the loan financial and repayment snapshot.

**Data type:**

- String / Period

**Format:**

- `YYYY-MM`

**Examples:**

- `2024-01`

- `2025-08`

- `2026-06`

**Rules:**

- Must not be NULL.

- Must represent a valid calendar month.

- The combination `loan_id + year_month` must be unique.

- `year_month` must not precede the loan's `origination_year`.

- Monthly observations should normally be continuous throughout the active life of the lending contract.

- No monthly records should exist after the loan has reached its definitive final state, except when required to represent the final closing or resolution month.

- Historical monthly records must not be overwritten by subsequent loan events.

- Intentional data-quality or operational incidents may create exceptional missing observations, which must remain rare and identifiable.

- `year_month` must remain temporally consistent with `loans.loan_status` and `loans.closing_year`.

## outstanding_balance

**Description:** Remaining balance owed on the BTYT lending contract at the end of the calendar month.

**Data type:**

- Numeric / Decimal

**Currency:**

- Expressed in the contractual currency defined in `loans.currency`.

**Rules:**

- Must not be NULL.

- Must be greater than or equal to zero.

- Represents the outstanding amount owed at the end of `year_month`.

- Must not exceed the economically plausible exposure associated with the original loan and subsequent interest or restructuring effects.

- `outstanding_balance` should generally decline over time for normally performing installment loans.

- Temporary increases may occur when unpaid interest, arrears, restructuring or other explicitly modeled events affect the balance.

- A fully repaid loan should reach an `outstanding_balance` of zero.

- Historical balances must not be overwritten by subsequent payments or loan events.

- `outstanding_balance` must remain consistent with `original_amount`, payments, interest-rate evolution and loan status.

**Generation assumptions:**

- Outstanding-balance trajectories must not be generated independently month by month.

- Each loan should follow a coherent historical path from origination toward repayment, restructuring, default or write-off.

- Normally performing loans should generally show declining balances.

- Larger original amounts and longer terms should produce longer-lived outstanding balances.

- Early repayment may cause a faster-than-scheduled decline.

- Missed or insufficient payments may slow the reduction of outstanding balance.

- `RESTRUCTURED` loans may exhibit discontinuities or altered repayment trajectories.

- `WRITTEN_OFF` loans may retain a positive balance before the final write-off event.

- Exact repayment trajectories must emerge from the loan-generation and payment process rather than from predetermined analytical outcomes.

## current_interest_rate

**Description:** Annual nominal interest rate applicable to the BTYT lending contract during the calendar month.

**Data type:**

- Numeric / Decimal

**Unit:**

- Percentage (%)

**Rules:**

- Must not be NULL.

- Must be greater than zero.

- Must be stored as a percentage value (e.g. `8.50` represents 8.50%).

- Must remain consistent with `loans.rate_type`.

- For `FIXED` loans, `current_interest_rate` should normally remain equal to `loans.initial_interest_rate`.

- For `VARIABLE` loans, `current_interest_rate` may change over time according to the loan's pricing mechanism.

- For `MIXED` loans, `current_interest_rate` should initially remain equal to the fixed introductory rate and may vary after the transition to the variable-rate period.

- Historical monthly rates must not be overwritten by subsequent rate changes.

- Interest-rate changes must follow coherent temporal paths and must not be generated independently month by month.

- Changes in `current_interest_rate` should be consistent with the contractual currency, product type, origination characteristics and broader economic environment.

**Generation assumptions:**

- Fixed-rate loans should display constant monthly rates under normal conditions.

- Variable-rate loans should generally retain the same rate for multiple consecutive months and change only when a rate revision occurs.

- Mixed-rate loans should contain a clearly identifiable initial fixed period followed by a potentially variable period.

- Interest-rate changes should exhibit persistence rather than random monthly fluctuations.

- UYU and USD lending should follow different rate environments.

- Product type and term may influence rate sensitivity and adjustment frequency.

- Macroeconomic conditions may affect variable-rate movements across many loans simultaneously.

- Individual pricing differences between otherwise similar customers must remain possible.

- Exact future rate paths must not be predetermined and should emerge from the synthetic temporal-generation process.

## scheduled_payment

**Description:** Contractual payment amount scheduled for the BTYT lending contract during the calendar month.

**Data type:**

- Numeric / Decimal

**Currency:**

- Expressed in the contractual currency defined in `loans.currency`.

**Rules:**

- Must not be NULL for installment-based loans that require a scheduled monthly payment.

- Must be greater than or equal to zero.

- Represents the amount contractually due during `year_month`, not the amount actually paid by the customer.

- Must remain consistent with `original_amount`, `term_months`, `current_interest_rate`, repayment structure and remaining contractual balance.

- `scheduled_payment` may change over time for `VARIABLE` or `MIXED` rate loans when rate revisions affect the contractual payment.

- `scheduled_payment` may also change after a restructuring event.

- For normally amortizing fixed-rate loans, scheduled payments should generally remain stable across consecutive months.

- A value of `0` may be valid in explicitly modeled grace periods or non-installment credit structures.

- Historical scheduled payments must not be overwritten by subsequent contractual changes.

**Generation assumptions:**

- Scheduled payments must be generated from the underlying loan contract rather than independently sampled.

- Payment amounts should follow coherent amortization logic.

- `Personal Loan`, `Auto Loan`, `Mortgage Loan`, `SME Loan`, `Agricultural Loan` and `Business Leasing` may have different typical repayment structures.

- `Business Credit Line` may require a different treatment from traditional installment loans and may have months with no fixed scheduled amortization.

- Variable-rate loans may experience changes in scheduled payments following changes in `current_interest_rate`.

- Restructured loans may exhibit clear changes in payment schedules.

- Grace periods may exist for a small subset of products or contracts when explicitly modeled.

- Exact payment distributions must emerge from loan terms and rate paths rather than from predetermined target values.

## actual_payment

**Description:** Actual amount paid by the customer toward the BTYT lending contract during the calendar month.

**Data type:**

- Numeric / Decimal

**Currency:**

- Expressed in the contractual currency defined in `loans.currency`.

**Rules:**

- Must be greater than or equal to zero.

- Represents the payment effectively received by BTYT during `year_month`.

- Must be interpreted relative to `scheduled_payment`.

- `actual_payment` may be:

  - equal to `scheduled_payment`;

  - lower than `scheduled_payment`;

  - greater than `scheduled_payment` in cases of partial or full prepayment;

  - zero in months where no payment is received.

- `actual_payment` must not be generated independently from the customer's historical repayment behavior.

- Payment behavior must remain temporally consistent across consecutive months.

- A missed or partial payment may contribute to subsequent delinquency, arrears or changes in `days_past_due`.

- A customer may recover from temporary delinquency and return to normal payment behavior.

- Payment difficulties must not automatically imply default.

- Historical payments must not be overwritten by subsequent loan events.

**Generation assumptions:**

- The large majority of performing BTYT borrowers should normally meet their scheduled payments.

- Exact repayment-performance rates must not be predetermined.

- Serious delinquency and default should remain minority outcomes.

- Payment behavior should exhibit persistence:

  - customers with a strong repayment history should generally remain likely to pay on time;

  - customers experiencing repayment difficulties may have an increased probability of further irregular payments;

  - recovery after temporary delinquency must remain possible.

- Short-term payment irregularities should be substantially more common than persistent severe delinquency.

- `actual_payment` probabilities may be influenced by:

  - customer income or business revenue;

  - loan payment burden;

  - product type;

  - currency;

  - interest-rate changes;

  - customer tenure;

  - previous repayment behavior;

  - business sector;

  - geographic and branch characteristics;

  - broader macroeconomic conditions;

  - random individual variation.

- Branch-level repayment behavior may differ because branches serve different customer populations, economic environments and product mixes.

- Branch effects must remain moderate and probabilistic rather than mechanically assigning good or bad borrowers to specific offices.

- Differences across branches should primarily emerge from underlying customer, geographic, product and economic characteristics, with a smaller branch-specific component.

- The final distribution of full payments, partial payments, missed payments, prepayments and recoveries should emerge from the synthetic temporal-generation process within realistic banking constraints.

## days_past_due

**Description:** Number of calendar days by which the oldest unpaid contractual payment obligation is overdue at the end of the calendar month.

**Data type:**

- Integer

**Unit:**

- Days

**Rules:**

- Must not be NULL.

- Must be greater than or equal to zero.

- `0` represents a loan with no overdue contractual payment obligation at month-end.

- `days_past_due` must be derived from the historical relationship between scheduled and actual payments.

- Must not be generated independently or randomly.

- A full and timely payment should normally maintain or return `days_past_due` to `0`.

- A partial or missed payment may cause `days_past_due` to increase over subsequent periods.

- Payment of accumulated arrears may reduce or reset `days_past_due`.

- A temporary payment irregularity must not automatically imply persistent delinquency or default.

- `days_past_due` must remain temporally consistent across consecutive monthly observations.

- Historical DPD values must not be overwritten by subsequent repayment behavior.

- DPD behavior must remain consistent with `loan_status` and any future default or restructuring rules.

**Generation assumptions:**

- The large majority of performing loans should normally have `days_past_due = 0`.

- Short and temporary delays should be more common than prolonged delinquency.

- Persistent high-DPD trajectories should represent a minority of lending relationships.

- Customers may recover from delinquency and return to current payment status.

- Repeated delinquency episodes may occur for some customers.

- DPD trajectories should exhibit persistence rather than independent monthly randomness.

- Payment burden, previous repayment behavior, customer financial characteristics, product, currency, interest-rate changes, business sector and macroeconomic conditions may influence delinquency probabilities.

- Branch and geographic differences may emerge from customer composition and local conditions, with only moderate direct branch-specific effects.

- Exact delinquency rates and DPD distributions must not be predetermined.

## delinquency_status

**Description:** Monthly delinquency classification of the BTYT lending contract based on the number of days past due at the end of the calendar month.

**Data type:**

- String / Categorical

**Allowed values:**

- `CURRENT`

- `DPD_1_30`

- `DPD_31_60`

- `DPD_61_90`

- `DPD_90_PLUS`

**Category definitions:**

- `CURRENT`: `days_past_due = 0`.

- `DPD_1_30`: `days_past_due` between 1 and 30.

- `DPD_31_60`: `days_past_due` between 31 and 60.

- `DPD_61_90`: `days_past_due` between 61 and 90.

- `DPD_90_PLUS`: `days_past_due > 90`.

**Rules:**

- Must not be NULL.

- Must be derived directly from `days_past_due`.

- Must not be generated independently.

- Each monthly snapshot must belong to exactly one delinquency category.

- `delinquency_status` represents the monthly repayment condition and must not be interpreted as the contractual status of the loan.

- `DPD_90_PLUS` does not automatically imply `loans.loan_status = DEFAULTED`.

- A loan may transition between delinquency categories over time.

- A delinquent loan may return to `CURRENT` after accumulated overdue obligations are resolved.

- Historical delinquency classifications must not be overwritten by subsequent repayment behavior.

- Classification must remain consistent with the corresponding `days_past_due` value.

**Generation assumptions:**

- The majority of performing monthly observations should normally be classified as `CURRENT`.

- Early delinquency should be more common than severe or prolonged delinquency.

- Persistent `DPD_90_PLUS` observations should represent a minority of the portfolio.

- Delinquency transitions must emerge from underlying repayment behavior rather than predetermined status probabilities.

- Recovery from delinquency must remain possible.

- Repeated delinquency episodes may occur for some borrowers.

- Exact delinquency distributions and transition probabilities must not be predetermined.

**Data quality rules:**

- `days_past_due = 0` → `CURRENT`

- `1 <= days_past_due <= 30` → `DPD_1_30`

- `31 <= days_past_due <= 60` → `DPD_31_60`

- `61 <= days_past_due <= 90` → `DPD_61_90`

- `days_past_due > 90` → `DPD_90_PLUS`

## arrears_amount

**Description:** Total overdue and unpaid amount accumulated on the BTYT lending contract at the end of the calendar month.

**Data type:**

- Numeric / Decimal

**Currency:**

- Expressed in the contractual currency defined in `loans.currency`.

**Rules:**

- Must not be NULL.

- Must be greater than or equal to zero.

- A value of `0` represents a loan with no overdue unpaid obligations at month-end.

- `arrears_amount` represents accumulated overdue obligations and must not be interpreted as the total outstanding loan balance.

- Must be derived from the historical relationship between scheduled payments, actual payments and previously accumulated arrears.

- Must not be generated independently or randomly.

- Partial or missed payments may increase `arrears_amount`.

- Payments above the current scheduled obligation may reduce previously accumulated arrears.

- `arrears_amount` may return to zero when all overdue obligations have been resolved.

- A positive `arrears_amount` must remain temporally consistent with `days_past_due`.

- Historical arrears values must not be overwritten by subsequent repayment behavior.

**Generation assumptions:**

- The majority of normally performing loan-month observations should have `arrears_amount = 0`.

- Small and temporary arrears should be more common than large persistent arrears.

- Persistent accumulation of arrears should remain a minority behavior.

- Borrowers may partially or completely recover from accumulated arrears.

- Arrears trajectories must exhibit temporal persistence and must emerge from the underlying repayment process.

- Exact arrears distributions must not be predetermined.

## Phase 3 loan-snapshot generation rules

### Scheduled payment
- `scheduled_payment` comes from the active contractual repayment schedule and is not independently sampled.
- Fixed-, variable- and mixed-rate contracts reflect their applicable rate mechanics and valid repricing.
- After restructuring, snapshots use the revised internal repayment schedule.
- `P016` may use a product-specific minimum-payment/interest obligation rather than a standard amortizing installment.

### Actual payment
- `actual_payment` is the amount actually received against the loan obligation during the month.
- Payment behavior emerges from liquidity, debt burden, prior repayment behavior and other plausible factors with stochastic variation.
- Payments may be complete, partial, absent or above the scheduled obligation when prepayment is permitted.
- Payments from BTYT accounts reconcile with `LOAN_PAYMENT`; external payments may affect `actual_payment` without creating a BTYT account transaction.

### Days past due and delinquency
- `days_past_due` is calculated from exact internally maintained due dates and the oldest unresolved overdue obligation.
- Python must not approximate DPD by mechanically adding 30 per month.
- Partial payments update the oldest unpaid obligation consistently; full curing may return directly to `CURRENT`.
- `delinquency_status` is derived from DPD bands and is not independently sampled.
- `DPD_90_PLUS` is severe delinquency but does not automatically force immediate master status `DEFAULTED`.

### Arrears and outstanding balance
- `arrears_amount` evolves from missed/partial obligations and subsequent curing.
- It is part of the exposure and must not be double-counted on top of `outstanding_balance`.
- `outstanding_balance` derives from the loan ledger and contractual mechanics.
- For `P016`, outstanding balance may rise after a new drawdown while remaining within the approved line.

### Resolution
- Write-off follows a plausible severe-delinquency/default history.
- The final snapshot sequence must reconcile with master `loan_status` and `closing_year`.
- Once fully paid or written off, subsequent active monthly snapshots must not continue.
