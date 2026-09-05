# BTYT — Campaigns Data Dictionary

## Table: `campaigns`

**Description:**

Master table containing commercial and customer-acquisition campaigns executed by BTYT.

**Grain:**

One row represents one unique BTYT commercial campaign.

**Primary key:**

`campaign_id`

**Purpose:**

Represent BTYT marketing and commercial initiatives for acquisition, retention, cross-selling and product promotion, enabling campaign-performance analysis across customers, products, branches and regions.

---

## Variables

## campaign_id

**Description:** Unique internal identifier assigned to each BTYT commercial campaign.

**Data type:**

- String

**Format:**

- `M` followed by three numeric digits.

**Examples:**

- `M001`

- `M002`

- `M025`

**Rules:**

- Must be unique.

- Must not be NULL.

- Used as the primary key of the `campaigns` table.

- Must remain unchanged throughout the lifetime of the campaign record.

- Must not encode campaign type, product, region, channel or performance information.

## campaign_name

**Description:** Human-readable commercial name assigned to the BTYT campaign.

**Data type:**

- String / Categorical

**Allowed values:**

- `Your First BTYT Account`

- `Rural Investment 2021`

- `Payroll with BTYT 2021`

- `Save in USD 2021`

- `Back to University 2022`

- `SME Growth 2022`

- `BTYT Digital 2022`

- `Your First Home 2023`

- `Premium Upgrade 2023`

- `Business Liquidity 2023`

- `Summer East Coast 2024`

- `Drive with BTYT 2024`

- `Stay with BTYT 2024`

- `Rural Investment 2025`

- `Business Equipment 2025`

- `Save in USD 2025`

- `Payroll with BTYT 2026`

- `Premium Upgrade 2026`

**Campaign mapping:**

| campaign_id | campaign_name |

|---|---|

| `M001` | `Your First BTYT Account` |

| `M002` | `Rural Investment 2021` |

| `M003` | `Payroll with BTYT 2021` |

| `M004` | `Save in USD 2021` |

| `M005` | `Back to University 2022` |

| `M006` | `SME Growth 2022` |

| `M007` | `BTYT Digital 2022` |

| `M008` | `Your First Home 2023` |

| `M009` | `Premium Upgrade 2023` |

| `M010` | `Business Liquidity 2023` |

| `M011` | `Summer East Coast 2024` |

| `M012` | `Drive with BTYT 2024` |

| `M013` | `Stay with BTYT 2024` |

| `M014` | `Rural Investment 2025` |

| `M015` | `Business Equipment 2025` |

| `M016` | `Save in USD 2025` |

| `M017` | `Payroll with BTYT 2026` |

| `M018` | `Premium Upgrade 2026` |

**Rules:**

- Must not be NULL.

- Must be unique within the campaign catalog.

- Each `campaign_name` must correspond to exactly one `campaign_id`.

- Campaign names are manually defined master data and must not be randomly generated.

- Campaign names must not encode or imply campaign performance.

- Campaign names may reference the promoted product, customer segment, season, geographic focus or commercial objective.

- The name must remain stable throughout the historical campaign record.

- `campaign_name` must not be used as a substitute for structured attributes such as `campaign_type`, `target_product_id` or `target_customer_type`.

- New campaign names may only be introduced when the BTYT campaign master catalog is explicitly expanded.

## campaign_type

**Description:** Primary commercial objective pursued by the BTYT campaign.

**Data type:**

- String / Categorical

**Allowed values:**

- `ACQUISITION`

- `CROSS_SELL`

- `UPSELL`

- `RETENTION`

- `ACTIVATION`

**Category definitions:**

- `ACQUISITION`: Campaign primarily designed to attract new customers to BTYT.

- `CROSS_SELL`: Campaign designed to promote an additional product to an existing BTYT customer.

- `UPSELL`: Campaign designed to migrate an existing customer toward a higher-value or enhanced product offering.

- `RETENTION`: Campaign designed to maintain an existing customer relationship or reduce customer attrition.

- `ACTIVATION`: Campaign designed to increase adoption or usage of an existing product, service or banking channel.

**Rules:**

- Must not be NULL.

- Every campaign must have exactly one primary `campaign_type`.

- `campaign_type` represents the strategic objective of the campaign and not its final outcome.

- Similar campaign themes may use different campaign types when their strategic objectives differ.

- Campaign type must remain consistent with the intended target population and promoted product or service.

- Campaign success or customer response must not be encoded in `campaign_type`.

## target_product_id

**Description:** Identifier of the primary BTYT product promoted by the commercial campaign.

**Data type:**

- String

- NULL

**Reference:**

- Foreign key to `products.product_id`.

**Rules:**

- Must contain a valid `product_id` when the campaign promotes a specific BTYT product.

- May be NULL when the campaign objective is not associated with one specific product.

- Must remain consistent with `campaign_type`, target population and campaign strategy.

- `target_product_id` represents the primary promoted product and does not imply that the customer ultimately acquired it.

- Campaign performance must not be encoded in `target_product_id`.

- Product eligibility rules must remain applicable regardless of campaign targeting.

- A campaign must not cause customers to acquire products for which they are not eligible.

- Historical campaign-product relationships must remain unchanged even if the product is subsequently modified or discontinued.

**Examples:**

- Premium credit-card campaign → corresponding Premium Credit Card `product_id`.

- Mortgage acquisition campaign → corresponding Mortgage Loan `product_id`.

- Payroll campaign → corresponding Payroll Account `product_id`.

- Digital-channel activation campaign → `NULL`.

- General customer-retention campaign → potentially `NULL`.

## start_date

**Description:** Date on which the BTYT commercial campaign officially begins.

**Data type:**

- Date

**Format:**

- `YYYY-MM-DD`

**Rules:**

- Must not be NULL.

- Must represent a valid calendar date.

- Must be earlier than or equal to `end_date`.

- Must not precede the launch date of the targeted product when `target_product_id` is not NULL.

- `start_date` represents the beginning of campaign eligibility or exposure, not the date on which a specific customer responds.

- Historical campaign start dates must remain unchanged.

**Generation assumptions:**

- Campaign start dates are manually defined as part of the BTYT campaign catalog.

- Campaign timing should be commercially plausible and may reflect seasonality, product launches, business cycles or strategic priorities.

- Seasonal campaigns may begin shortly before the period they intend to influence.

- Campaign timing must not be selected based on the campaign's eventual performance.

---

## end_date

**Description:** Date on which the BTYT commercial campaign officially ends.

**Data type:**

- Date

**Format:**

- `YYYY-MM-DD`

**Rules:**

- Must not be NULL.

- Must represent a valid calendar date.

- Must be equal to or later than `start_date`.

- Represents the final date on which the campaign is considered active.

- Customer responses or product acquisitions may occur after `end_date` if they are reasonably attributable to prior campaign exposure.

- Historical campaign end dates must remain unchanged.

**Generation assumptions:**

- Campaign duration is manually defined as part of the campaign catalog.

- Duration may vary according to campaign objective, channel, seasonality and product.

- Short tactical campaigns and longer strategic campaigns may both exist.

- Campaign duration must not be adjusted retrospectively based on observed performance.

## target_customer_type

**Description:** Broad customer category targeted by the BTYT commercial campaign.

**Data type:**

- String / Categorical

**Allowed values:**

- `INDIVIDUAL`

- `BUSINESS`

- `BOTH`

**Category definitions:**

- `INDIVIDUAL`: Campaign primarily targets individual BTYT customers or prospects.

- `BUSINESS`: Campaign primarily targets business BTYT customers or prospects.

- `BOTH`: Campaign may target both individual and business customers or prospects.

**Rules:**

- Must not be NULL.

- Every campaign must have exactly one `target_customer_type`.

- Must remain compatible with the eligibility rules of `target_product_id` when a specific product is promoted.

- `INDIVIDUAL` campaigns must not intentionally target business customers.

- `BUSINESS` campaigns must not intentionally target individual customers.

- `BOTH` may be used only when the campaign proposition is genuinely applicable to both customer categories.

- `target_customer_type` defines campaign eligibility at a broad level and does not imply that every eligible customer is actually contacted.

- Final customer selection should depend on additional targeting criteria and the campaign-generation process.

- Campaign response or performance must not be encoded in `target_customer_type`.

### Campaign effectiveness and behavioral response

- Campaign existence, strategy, timing, targeting and promoted products are defined as BTYT master data; campaign effectiveness is not.

- Campaign effectiveness must emerge from customer-level behavior and must never be directly assigned at the campaign level.

- No campaign is guaranteed to produce a positive commercial outcome.

- Campaign exposure may generate:

- positive response;

- neutral or no observable response;

- explicit rejection;

- negative behavioral response.

- A positive response does not necessarily imply product conversion.

- A negative response does not automatically imply customer churn or product closure.

- Most individual campaign effects should remain moderate and behaviorally plausible rather than producing extreme customer reactions.

- Customer response probability may depend on:

- customer characteristics;

- customer type;

- existing product holdings;

- financial characteristics;

- previous banking behavior;

- campaign-product fit;

- campaign timing;

- marketing channel;

- geographic targeting;

- previous campaign exposure;

- individual behavioral variation.

- Different customers exposed to the same campaign may react differently.

- Campaigns may perform differently across customer segments, branches, departments, localities and marketing channels.

- These differences must emerge from the underlying customer population and campaign interactions rather than from predetermined campaign-performance targets.

### Campaign fatigue

- Repeated campaign exposure may generate campaign fatigue.

- Customers receiving frequent or overlapping marketing contacts may become less likely to respond positively to subsequent campaigns.

- Campaign fatigue may increase:

- non-response probability;

- rejection probability;

- customer disengagement.

- Campaign fatigue must depend on previous customer-level campaign exposure and must not be assigned uniformly across customers.

- Campaign fatigue effects should generally be gradual and moderate.

- A customer with substantial previous campaign exposure may still respond positively when a subsequent campaign has strong customer-product fit.

### Negative and neutral campaign outcomes

- Some campaigns may produce little or no measurable commercial improvement.

- Some campaigns may perform worse than comparable campaigns or customer populations.

- Campaign exposure may occasionally be associated with negative customer behavior when campaign-product fit is poor, contact frequency is excessive or customer engagement is already weak.

- Campaigns must not be constructed so that every campaign generates positive incremental product adoption, engagement or retention.

- A campaign may therefore emerge as:

- highly effective;

- moderately effective;

- weak;

- statistically or commercially neutral;

- potentially counterproductive.

- These classifications must be analytical conclusions derived after data generation and must not exist as source variables in the campaign master data.

### Outcome independence

- Campaign response rates, conversion rates, rejection rates and other performance metrics must not be predetermined.

- Campaign-level performance metrics must be calculated from customer-level campaign activity after synthetic data generation.

- The synthetic generator must not target predefined campaign success rates.

- Campaign outcomes must not be regenerated merely because analytical results appear unexpectedly weak, strong or negative.

- Once generated data passes structural integrity, temporal consistency and realism validation, unexpected campaign performance must be preserved as a legitimate analytical result.

### Temporal and geographic integrity

- Campaign targeting must be historically consistent with the BTYT branch and agency network existing during the campaign period.

- Campaigns must not target a BTYT office before its opening date or after its permanent closure when campaign execution depends on that physical office.

- Campaigns targeting a locality may remain valid when other active BTYT channels or offices legitimately serve that locality.

- Branch and agency closures must not be retrospectively altered to accommodate campaign performance.

- Geographic targeting and branch-network history must be validated independently from campaign outcomes.

- In particular, `Summer East Coast 2024` must occur while the BTYT Piriápolis agency remains operational; the subsequent closure of the Piriápolis agency must occur after the campaign period.

### Core modeling principle

> BTYT determines which campaigns to launch, whom it intends to target, where and when to execute them, and which products or services to promote. Customer behavior determines whether those strategic decisions ultimately succeed.

## Phase 3 campaign-generation integrity rules

### Campaigns as interventions, not outcomes
- A campaign defines a BTYT intervention: target population, geography, timing, promoted product or behavior, channel strategy and offer characteristics.
- Campaign creation must occur before customer response is simulated.
- Python must never assign a campaign a predetermined successful or unsuccessful outcome and then manufacture customer behavior to match it.
- Campaign design quality, channel fit, offer attractiveness, timing and customer fatigue may modify response probabilities, but they must not guarantee conversion.

### Separation from secular trends
- Campaign effects must be generated separately from broader temporal trends such as gradual digital adoption, macroeconomic changes or evolving customer behavior.
- Growth observed after a campaign must not automatically be interpreted or generated as entirely caused by that campaign.
- The generator must preserve untreated/background behavioral evolution so campaign comparisons remain analytically meaningful.

### Historical and geographic consistency
- Campaign timing and geographic scope must respect the pre-existing branch and agency history.
- A campaign may target an office or locality only when that targeting is temporally and operationally plausible.
- Branch opening or closure history must not be retrospectively altered to improve campaign performance.
- Operational incidents may affect campaign execution or observed response, and campaign outcomes must not be artificially repaired when such events occur.
