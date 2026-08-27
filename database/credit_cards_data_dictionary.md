# BTYT --- Cards Data Dictionary

## Table: `cards`

**Description:**\
Table containing individual debit and credit cards issued by BTYT to its
customers.

**Grain:**\
One row represents one unique BTYT card.

**Primary key:**\
`card_id`

**Purpose:**\
Represent individual card relationships between BTYT customers and the
card products defined in the product catalog, including debit, classic
credit and premium credit cards.

**Included products:** - `P009` Debit Card - `P010` Classic Credit
Card - `P011` Premium Credit Card

**Excluded products:** - Transactional accounts and deposits are modeled
in `accounts`. - Lending products are modeled separately in `loans`.

------------------------------------------------------------------------

## Variables

## card_id

**Description:** Unique internal identifier assigned to each BTYT card.

**Data type:** - String

**Format:** - `K` followed by seven numeric digits.

**Examples:** - `K0000001` - `K0000002` - `K0125487`

**Rules:** - Must be unique. - Must not be NULL. - Used as the primary
key of the `cards` table. - Must remain unchanged throughout the
lifetime of the card relationship. - Must not encode customer, product,
card type, currency, branch or status information. - Closed or cancelled
cards retain their original `card_id`. - `card_id` is an internal
synthetic BTYT identifier and does not represent a real card number. -
Realistic payment-card numbers must not be generated or stored in the
dataset.

## customer_id

**Description:** Unique identifier of the BTYT customer to whom the card
is issued.

**Data type:** - String

**Reference:** - Foreign key to `customers.customer_id`.

**Rules:** - Must contain a valid `customer_id`. - Must not be NULL. -
One customer may hold multiple BTYT cards. - Multiple cards may belong
to the same customer. - A customer may hold different card products
simultaneously. - The referenced customer must have been registered with
BTYT before or during the card's issuance year. - Historical cards
remain associated with the original customer record after card closure
or cancellation. - Card ownership must be compatible with the
corresponding product's `target_customer_type`.

## product_id

**Description:** Identifier of the BTYT card product associated with the
individual card.

**Data type:** - String

**Reference:** - Foreign key to `products.product_id`.

**Allowed values:** - `P009` Debit Card - `P010` Classic Credit Card -
`P011` Premium Credit Card

**Rules:** - Must contain a valid `product_id`. - Must not be NULL. -
Only products belonging to the `CARD` product family may appear in the
`cards` table. - `P009` represents a debit card. - `P010` represents a
classic credit card. - `P011` represents a premium credit card. - Card
ownership must be compatible with `products.target_customer_type`. - A
card cannot be issued before the corresponding product's
`launch_year`. - A customer may hold multiple different card products
simultaneously. - Holding one card product does not automatically imply
ownership of another card product.

## linked_account_id

**Description:** Identifier of the BTYT deposit or transactional account
directly linked to a debit card.

**Data type:** - String - NULL

**Reference:** - Foreign key to `accounts.account_id`.

**Rules:** - Must contain a valid `account_id` when `product_id = P009`
(`Debit Card`). - Must be `NULL` when `product_id IN (P010, P011)`
(`Classic Credit Card`, `Premium Credit Card`). - The linked account
must belong to the same `customer_id` as the card. - The linked account
must have existed when the debit card was issued. - The linked account
must correspond to a product that supports debit-card usage. - Credit
cards are not directly linked to a deposit account because they operate
through a credit facility granted by BTYT. - Any account used to
automatically pay a credit-card statement is outside the scope of the
current model and must not be represented through `linked_account_id`. -
Closure of the linked account must be temporally consistent with the
status and lifetime of the debit card.

**Generation assumptions:** - Every debit card must be linked to an
eligible BTYT account belonging to the same customer. - Customers with
multiple eligible accounts may have their debit card linked to any
compatible account, with probabilities influenced by product type and
account activity. - Savings, payroll, youth/student and current accounts
may support debit-card relationships when commercially appropriate. -
Credit-card ownership must remain independent from `linked_account_id`.

## linked_account_id

**Description:** Identifier of the BTYT deposit or transactional account
directly linked to a debit card.

**Data type:** - String - NULL

**Reference:** - Foreign key to `accounts.account_id`.

**Rules:** - Must contain a valid `account_id` when `product_id = P009`
(`Debit Card`). - Must be `NULL` when `product_id IN (P010, P011)`
(`Classic Credit Card`, `Premium Credit Card`). - The linked account
must belong to the same `customer_id` as the card. - The linked account
must have existed when the debit card was issued. - The linked account
must correspond to a product that supports debit-card usage. - Credit
cards are not directly linked to a deposit account because they operate
through a credit facility granted by BTYT. - Any account used to
automatically pay a credit-card statement is outside the scope of the
current model and must not be represented through `linked_account_id`. -
Closure of the linked account must be temporally consistent with the
status and lifetime of the debit card.

**Generation assumptions:** - Every debit card must be linked to an
eligible BTYT account belonging to the same customer. - Customers with
multiple eligible accounts may have their debit card linked to any
compatible account, with probabilities influenced by product type and
account activity. - Savings, payroll, youth/student and current accounts
may support debit-card relationships when commercially appropriate. -
Credit-card ownership must remain independent from `linked_account_id`.

## issue_year

**Description:** Year in which the specific BTYT card was originally
issued to the customer.

**Data type:** - Integer

**Format:** - YYYY

**Rules:** - Must not be NULL. - Must represent a valid year. - Must not
be later than the 2026. - Must be equal to or later than the customer's
`registration_year`. - Must be equal to or later than the corresponding
card product's `launch_year`. - For `product_id = P009` (`Debit Card`),
`issue_year` must be equal to or later than the linked account's
`opening_year`. - The card cannot be issued before the customer exists
in the BTYT customer base. - `issue_year` represents the issuance of
this specific card relationship and not necessarily the customer's first
use of card products. - A customer may receive additional cards in later
years. - Historical cards retain their original `issue_year` after
closure or cancellation.

**Generation assumptions:** - Card issuance must not be uniformly
distributed across years. - Recently registered customers may have a
higher probability of receiving a debit card shortly after opening an
eligible transactional account. - Credit-card issuance may occur at
customer registration or later as the commercial relationship
develops. - Customers may acquire a Classic Credit Card before later
becoming eligible for or adopting a Premium Credit Card. - Product
adoption should reflect the historical availability defined by
`products.launch_year`. - Debit-card adoption should increase
substantially after the product's introduction and alongside expansion
of electronic banking. - Credit-card issuance probabilities may vary
according to customer income, tenure, product ownership and other
characteristics without being determined mechanically. - Exact issuance
volumes and adoption patterns must emerge from the synthetic generation
process rather than from predetermined targets.

## card_status

**Description:** Current status of the BTYT card relationship associated
with the customer.

**Data type:** - String / Categorical

**Allowed values:** - `ACTIVE` - `CLOSED`

**Category definitions:** - `ACTIVE`: The customer currently maintains
the card relationship with BTYT. - `CLOSED`: The card relationship has
been permanently terminated.

**Rules:** - Must not be NULL. - Every card must have exactly one
`card_status`. - `card_status` represents the status of the card
relationship and not the physical card itself. - Expiration, renewal or
replacement of the physical card does not create a new record and does
not change `card_status`. - A lost, stolen, damaged or expired physical
card that is replaced while the customer maintains the same card
relationship remains `ACTIVE`. - `CLOSED` represents the permanent
termination of that card relationship. - `card_status` is independent
from `customer_status`. - An `ACTIVE` customer may have both `ACTIVE`
and `CLOSED` historical card relationships. - A customer with
`customer_status = CLOSED` must not retain an `ACTIVE` card relationship
after the end of the customer relationship. - For debit cards, the
status must remain temporally consistent with the associated
`linked_account_id`. - Closure of one card product does not imply
closure of another card product held by the same customer.

**Generation assumptions:** - The majority of current card relationships
should remain `ACTIVE`. - Exact active and closed proportions must not
be predetermined. - Closure probability may vary according to card age,
customer tenure, customer status, product type, account activity, other
product ownership and customer characteristics. - Customers upgrading
from `Classic Credit Card` to `Premium Credit Card` may have a higher
probability of closing their Classic card, but closure must not be
automatic. - Customers may simultaneously hold Classic and Premium
credit cards. - Debit-card closure may be associated with closure of the
linked account, but the relationship must remain probabilistic except
where required by temporal integrity rules. - Exact closure patterns
should emerge from the synthetic generation process.

## closing_year

**Description:** Year in which the BTYT card relationship was
permanently terminated.

**Data type:** - Integer - NULL

**Format:** - YYYY - NULL

**Rules:** - Must be `NULL` when `card_status = ACTIVE`. - Must contain
a valid year when `card_status = CLOSED`. - Must be equal to or later
than `issue_year`. - Must not be later than the 2026. - `closing_year`
represents the permanent termination of the card relationship and not
the expiration, renewal or replacement of the physical card. - Card
closure does not necessarily imply customer churn. - A customer may
close one card relationship while maintaining other active BTYT cards,
accounts or products. - If `customer_status = CLOSED`, the card's
`closing_year` must be equal to or earlier than the customer's
`closing_year`. - For debit cards, `closing_year` must remain temporally
consistent with the lifetime of the associated `linked_account_id`. -
Closure of a Classic Credit Card does not imply closure of a Premium
Credit Card, or vice versa.

**Generation assumptions:** - Card closing years must not be uniformly
distributed. - Older card relationships should generally have had
greater historical exposure to potential closure. - Card relationships
may remain active for many years despite repeated physical-card
renewals. - Short-lived card relationships should exist but should not
dominate the dataset. - Customers adopting a Premium Credit Card may
have an increased probability of closing an existing Classic Credit
Card, without making the relationship deterministic. - Debit-card
closure may be associated with closure of its linked account. - Customer
tenure, product ownership, account activity and other customer
characteristics may influence closure probabilities. - Exact closure
rates and relationship durations must not be predetermined.

## Phase 3 debit-card lifecycle integrity rule

- For debit cards (`product_id = P009`), `linked_account_id` identifies the account that supports the debit-card relationship.
- An `ACTIVE` debit card cannot outlive its linked account.
- If the linked account is permanently closed, the associated debit-card relationship must be closed no later than the account closure.
- Python must enforce this rule using the exact internal account and card closure dates used during generation, even though only years are persisted in the final master tables.
- This rule applies to debit cards only; BTYT credit cards (`P010`, `P011`) do not require `linked_account_id`.

## Phase 3 credit-card relationship integrity rules

### Credit-card economic closure
- For credit-card products (`P010`, `P011`), permanent relationship closure requires the economically active exposure to be resolved.
- A card may stop authorizing new purchases before the debt is fully extinguished, but definitive `card_status = CLOSED` should normally occur only after payoff, settlement or another internally consistent resolution.
- Under coherent base generation, the final credit-card exposure associated with a permanently closed relationship must be zero.
- Any non-zero residual exposure after definitive closure may appear only as a deliberate controlled data-quality anomaly.

### Credit-limit evolution
- Credit limits are time-varying relationship attributes represented in `credit_card_monthly_snapshot`.
- Limit changes may depend probabilistically on customer financial capacity, tenure, utilization and prior payment behavior.
- Premium cards may have higher limits on average, but substantial overlap with Classic cards must remain.
- A limit reduction must not create an impossible negative `available_credit` under the current no-over-limit model.
- Python must therefore ensure that a new credit limit is at least as large as the live outstanding exposure at the effective time of the change.
