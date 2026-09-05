# BTYT --- Products Data Dictionary

## Table: `products`

**Description:**\
Master table containing the banking products offered by BTYT to
individual and business customers.

**Grain:**\
One row represents one unique BTYT banking product.

**Primary key:**\
`product_id`

**Purpose:**\
Provide a standardized product catalog used across accounts,
customer-product relationships, transactions, deposits, lending and
analytical reporting.

------------------------------------------------------------------------

## Variables

## product_id

**Description:** Unique internal identifier assigned to each BTYT
banking product.

**Data type:** - String

**Format:** - `P` followed by three numeric digits.

**Examples:** - `P001` - `P002` - `P018`

**Rules:** - Must be unique. - Must not be NULL. - Used as the primary
key of the `products` table. - Must remain stable throughout the
lifetime of the product. - Must not encode product family, currency,
customer segment or other product characteristics. - Discontinued
products retain their original `product_id`.

## Product catalog

### Transactional Accounts

  product_id   product_name
  ------------ -------------------------
  P001         Savings Account UYU
  P002         Savings Account USD
  P003         Current Account UYU
  P004         Current Account USD
  P005         Payroll Account
  P006         Youth / Student Account

### Savings & Deposits

  product_id   product_name
  ------------ ------------------------
  P007         Fixed-Term Deposit UYU
  P008         Fixed-Term Deposit USD

### Cards

  product_id   product_name
  ------------ ---------------------
  P009         Debit Card
  P010         Classic Credit Card
  P011         Premium Credit Card

### Retail Lending

  product_id   product_name
  ------------ ---------------
  P012         Personal Loan
  P013         Auto Loan
  P014         Mortgage Loan

### Business Lending

  product_id   product_name
  ------------ ----------------------
  P015         SME Loan
  P016         Business Credit Line
  P017         Agricultural Loan
  P018         Business Leasing

## product_name

**Description:** Standardized commercial name of the BTYT banking
product.

**Data type:** - String

**Rules:** - Must not be NULL. - Must be unique. - Must correspond to
the product name defined in the official BTYT Product Catalog above. -
Each `product_name` must correspond to exactly one `product_id`. -
Product names must remain standardized across all BTYT datasets.

## product_family

**Description:** High-level classification of the BTYT banking product
according to its primary financial function.

**Data type:** - String / Categorical

**Allowed values:** - `TRANSACTIONAL_ACCOUNT` - `SAVINGS_DEPOSIT` -
`CARD` - `RETAIL_LENDING` - `BUSINESS_LENDING`

**Category definitions:** - `TRANSACTIONAL_ACCOUNT`: Products primarily
designed for everyday banking operations, payments and money
management. - `SAVINGS_DEPOSIT`: Products primarily designed for saving
funds and generating returns over a defined or flexible period. -
`CARD`: Debit and credit card products used for payments, purchases and
access to funds or credit. - `RETAIL_LENDING`: Credit products primarily
designed for individual customers. - `BUSINESS_LENDING`: Financing
products primarily designed for business customers and productive
activities.

**Rules:** - Every product must belong to exactly one
`product_family`. - Must not be NULL. - `product_family` must reflect
the product's primary financial function. - The classification must
remain standardized across all BTYT datasets. - Product families are
used for aggregation, reporting and analytical segmentation.

**Product mapping:**

  product_id   product_name              product_family
  ------------ ------------------------- -------------------------
  P001         Savings Account UYU       `TRANSACTIONAL_ACCOUNT`
  P002         Savings Account USD       `TRANSACTIONAL_ACCOUNT`
  P003         Current Account UYU       `TRANSACTIONAL_ACCOUNT`
  P004         Current Account USD       `TRANSACTIONAL_ACCOUNT`
  P005         Payroll Account           `TRANSACTIONAL_ACCOUNT`
  P006         Youth / Student Account   `TRANSACTIONAL_ACCOUNT`
  P007         Fixed-Term Deposit UYU    `SAVINGS_DEPOSIT`
  P008         Fixed-Term Deposit USD    `SAVINGS_DEPOSIT`
  P009         Debit Card                `CARD`
  P010         Classic Credit Card       `CARD`
  P011         Premium Credit Card       `CARD`
  P012         Personal Loan             `RETAIL_LENDING`
  P013         Auto Loan                 `RETAIL_LENDING`
  P014         Mortgage Loan             `RETAIL_LENDING`
  P015         SME Loan                  `BUSINESS_LENDING`
  P016         Business Credit Line      `BUSINESS_LENDING`
  P017         Agricultural Loan         `BUSINESS_LENDING`
  P018         Business Leasing          `BUSINESS_LENDING`

## currency

**Description:** Currency configuration associated with the BTYT banking
product.

**Data type:** - String / Categorical

**Allowed values:** - `UYU` - `USD` - `MULTI` - `N/A`

**Rules:** - Every product must have exactly one `currency`
classification. - `UYU` and `USD` indicate products explicitly
denominated in one currency. - `MULTI` indicates that the product may
operate across more than one currency depending on the specific customer
relationship or linked account. - `N/A` indicates that currency is not
an intrinsic characteristic of the product itself. - For account transactions, currency is not stored redundantly in `transactions`; it is derived through `transactions.account_id → accounts.product_id → products.currency`.
- For credit-card transactions, monetary values are stored in UYU-equivalent analytical terms as defined in `credit_card_transactions`.
- Cross-currency transaction and exchange-rate mechanics are outside the scope of the current BTYT dataset.

**Product mapping:**

  product_id   product_name              currency
  ------------ ------------------------- ----------
  P001         Savings Account UYU       `UYU`
  P002         Savings Account USD       `USD`
  P003         Current Account UYU       `UYU`
  P004         Current Account USD       `USD`
  P005         Payroll Account           `UYU`
  P006         Youth / Student Account   `UYU`
  P007         Fixed-Term Deposit UYU    `UYU`
  P008         Fixed-Term Deposit USD    `USD`
  P009         Debit Card                `MULTI`
  P010         Classic Credit Card       `MULTI`
  P011         Premium Credit Card       `MULTI`
  P012         Personal Loan             `UYU`
  P013         Auto Loan                 `MULTI`
  P014         Mortgage Loan             `MULTI`
  P015         SME Loan                  `MULTI`
  P016         Business Credit Line      `MULTI`
  P017         Agricultural Loan         `MULTI`
  P018         Business Leasing          `MULTI`

## target_customer_type

**Description:** Customer type primarily targeted by the BTYT banking
product.

**Data type:** - String / Categorical

**Allowed values:** - `INDIVIDUAL` - `BUSINESS` - `BOTH`

**Category definitions:** - `INDIVIDUAL`: Product primarily designed for
individual customers. - `BUSINESS`: Product primarily designed for
business customers. - `BOTH`: Product designed for or available to both
individual and business customers.

**Rules:** - Every product must have exactly one
`target_customer_type`. - Must not be NULL. - `target_customer_type`
represents the intended commercial market of the product. - It does not
necessarily imply that every eligible customer holds the product. -
Product ownership must be modeled separately through customer-product,
account, card or loan relationships. - Eligibility and actual ownership
should remain probabilistic and depend on customer characteristics and
business rules.

**Product mapping:**

  product_id   product_name              target_customer_type
  ------------ ------------------------- ----------------------
  P001         Savings Account UYU       `BOTH`
  P002         Savings Account USD       `BOTH`
  P003         Current Account UYU       `BOTH`
  P004         Current Account USD       `BOTH`
  P005         Payroll Account           `INDIVIDUAL`
  P006         Youth / Student Account   `INDIVIDUAL`
  P007         Fixed-Term Deposit UYU    `BOTH`
  P008         Fixed-Term Deposit USD    `BOTH`
  P009         Debit Card                `BOTH`
  P010         Classic Credit Card       `INDIVIDUAL`
  P011         Premium Credit Card       `INDIVIDUAL`
  P012         Personal Loan             `INDIVIDUAL`
  P013         Auto Loan                 `BOTH`
  P014         Mortgage Loan             `INDIVIDUAL`
  P015         SME Loan                  `BUSINESS`
  P016         Business Credit Line      `BUSINESS`
  P017         Agricultural Loan         `BUSINESS`
  P018         Business Leasing          `BUSINESS`

## launch_year

**Description:** Year in which the banking product was first introduced
into the BTYT product portfolio.

**Data type:** - Integer

**Format:** - YYYY

**Rules:** - Must not be NULL. - Must be equal to or later than BTYT's
foundation year (1969). - Represents the first year in which the product
became commercially available through BTYT. - Customers cannot hold a
product before its `launch_year`. - `launch_year` remains unchanged
throughout the lifetime of the product. - All products included in the
current catalog remain commercially active.

**Product mapping:**

  product_id   product_name                launch_year
  ------------ ------------------------- -------------
  P001         Savings Account UYU                1969
  P002         Savings Account USD                1976
  P003         Current Account UYU                1969
  P004         Current Account USD                1982
  P005         Payroll Account                    2001
  P006         Youth / Student Account            2014
  P007         Fixed-Term Deposit UYU             1971
  P008         Fixed-Term Deposit USD             1978
  P009         Debit Card                         1996
  P010         Classic Credit Card                1993
  P011         Premium Credit Card                2008
  P012         Personal Loan                      1973
  P013         Auto Loan                          1998
  P014         Mortgage Loan                      1986
  P015         SME Loan                           1991
  P016         Business Credit Line               1984
  P017         Agricultural Loan                  1969
  P018         Business Leasing                   2005

------------------------------------------------------------------------

## Design decisions

The `products` table is intentionally designed as a compact master
catalog.

The following attributes are not included in the current schema:

-   `product_status`
-   `interest_rate`
-   `fees`
-   `minimum_income`
-   `credit_risk_category`
-   `credit_limit`
-   `minimum_balance`

### Rationale

-   All 18 products in the current BTYT catalog are considered active
    during the current analytical period, making a product status field
    unnecessary.
-   Interest rates, fees, credit limits and other financial conditions
    may vary by customer, contract, currency and time, and therefore
    should not be stored as fixed attributes of the master product
    catalog.
-   Credit-risk characteristics belong to specific lending relationships
    and will be modeled separately when required, particularly in Part
    II --- Credit Risk Modeling.
-   Customer eligibility requirements should be modeled through business
    rules rather than fixed product-level attributes when necessary.
-   Additional attributes may be incorporated in future dataset versions
    if they become analytically relevant.

The objective is to keep `products` as a stable, reusable product
dimension while avoiding attributes that belong to individual contracts
or time-dependent business conditions.
