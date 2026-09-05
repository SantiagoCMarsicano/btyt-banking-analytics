# BTYT --- Campaign Customers Data Dictionary

## Table: `campaign_customers`

**Description:**\
Customer-level campaign activity table linking BTYT commercial campaigns
with the customers selected for campaign targeting and recording their
subsequent behavioral response.

**Grain:**\
One row represents one unique customer-campaign relationship.

**Primary key:**\
Composite key: - `campaign_id` - `customer_id`

**Purpose:**\
Measure campaign targeting, exposure, response and conversion at
customer level while allowing campaign effectiveness to emerge from
synthetic customer behavior rather than being predetermined.

**References:** - `campaign_id` → foreign key to
`campaigns.campaign_id` - `customer_id` → foreign key to
`customers.customer_id`

------------------------------------------------------------------------

## Variables

## campaign_id

**Description:** Identifier of the BTYT commercial campaign associated
with the customer-level campaign record.

**Data type:** - String

**Reference:** - Foreign key to `campaigns.campaign_id`.

**Rules:** - Must not be NULL. - Must contain a valid `campaign_id`. -
The combination `campaign_id + customer_id` must be unique. - Customer
selection must occur within the targeting rules of the referenced
campaign. - Campaign characteristics must be obtained from the
`campaigns` master table and must not be duplicated in this table.

## customer_id

**Description:** Identifier of the BTYT customer selected for the
commercial campaign.

**Data type:** - String

**Reference:** - Foreign key to `customers.customer_id`.

**Rules:** - Must not be NULL. - Must contain a valid `customer_id`. -
Customer type must be compatible with
`campaigns.target_customer_type`. - Customer must satisfy applicable
product eligibility requirements when the campaign targets a specific
product. - Customer geographic characteristics must be compatible with
`campaign_geography`. - Customer selection must be historically
plausible at the time of the campaign. - Customers must not be selected
solely because they are predetermined to respond positively. - Eligible
customers may or may not be selected for a campaign. - Selection
probability may depend on campaign strategy, customer characteristics
and historical behavior.

## selection_date

**Description:** Date on which the BTYT customer was selected for
inclusion in the commercial campaign target population.

**Data type:** - Date

**Format:** - `YYYY-MM-DD`

**Rules:** - Must not be NULL. - Must represent a valid calendar date. -
Must be equal to or later than `campaigns.start_date`. - Must be equal
to or earlier than `campaigns.end_date`. - Customer eligibility must be
evaluated using information available on or before `selection_date`. -
The customer must satisfy the campaign's applicable customer-type,
product and geographic targeting rules on `selection_date`. -
`selection_date` represents inclusion in the campaign target population
and does not imply that the customer was actually exposed to campaign
communication. - Customers must not be selected based on future
response, conversion or behavioral outcomes. - Historical selection
dates must not be modified after campaign performance is observed.

**Generation assumptions:** - Customer selection may occur throughout
the active campaign period rather than exclusively on the first campaign
day. - Selection timing may depend on campaign strategy, customer
eligibility and operational rollout. - Campaigns may use phased
targeting rather than selecting the entire eligible population
simultaneously. - Exact customer-selection volumes and timing must not
be predetermined.

## exposure_status

**Description:** Indicates whether the customer was actually exposed to
at least one communication associated with the BTYT campaign.

**Data type:** - String / Categorical

**Allowed values:** - `EXPOSED` - `NOT_EXPOSED`

**Category definitions:** - `EXPOSED`: The customer received at least
one valid campaign communication through one or more channels authorized
for the campaign. - `NOT_EXPOSED`: The customer was selected for the
campaign target population but did not receive a valid campaign
communication.

**Rules:** - Must not be NULL. - Every selected customer must have
exactly one `exposure_status`. - `EXPOSED` does not imply that the
customer noticed, opened, read or positively responded to the
communication. - `NOT_EXPOSED` does not imply customer rejection; it
represents a failure or absence of campaign delivery. - Exposure must
occur only through channels defined in `campaign_channels` for the
corresponding campaign. - Customers must not be marked as `EXPOSED`
because of future response or conversion. - `exposure_status` must
remain historically unchanged after campaign outcomes are observed.

**Generation assumptions:** - Most selected customers should normally be
successfully exposed. - `NOT_EXPOSED` should remain a minority outcome
under normal campaign execution. - Exposure probability may vary
according to: - campaign channel mix; - availability of valid customer
contact information; - customer digital engagement; - geographic
context; - operational execution; - campaign timing; - random delivery
variation. - Physical and digital channels may exhibit different
exposure-success patterns. - Multi-channel campaigns may increase the
probability of successful exposure without guaranteeing it. -
Operational incidents may temporarily reduce successful exposure. -
Exact exposure rates must not be predetermined.

## exposure_date

**Description:** Date on which the customer was first successfully
exposed to a communication associated with the BTYT campaign.

**Data type:** - Date - NULL

**Format:** - `YYYY-MM-DD`

**Rules:** - Must contain a valid date when
`exposure_status = EXPOSED`. - Must be NULL when
`exposure_status = NOT_EXPOSED`. - Must be equal to or later than
`selection_date`. - Must occur within the active campaign period defined
by `campaigns.start_date` and `campaigns.end_date`. - Represents the
customer's first successful campaign exposure. - Subsequent exposures to
the same campaign must not modify the original `exposure_date`. -
Exposure must occur through at least one channel authorized in
`campaign_channels`. - `exposure_date` does not imply that the customer
noticed, read, understood or responded to the campaign. - Historical
exposure dates must not be modified based on subsequent customer
behavior.

**Generation assumptions:** - Time between `selection_date` and
`exposure_date` should vary across customers. - Some customers may be
exposed shortly after selection while others may be contacted later
during the campaign. - Exposure timing may depend on campaign rollout,
channel availability, operational conditions and customer contact
characteristics. - Exact exposure timing must not be predetermined based
on eventual customer response.

## response_status

**Description:** Observed customer response to the BTYT campaign
following successful campaign exposure.

**Data type:** - String / Categorical - NULL

**Allowed values:** - `NO_RESPONSE` - `POSITIVE` - `NEGATIVE` -
`NEUTRAL`

**Category definitions:** - `NO_RESPONSE`: The customer was successfully
exposed but no observable response was recorded. - `POSITIVE`: The
customer demonstrated observable interest in the campaign proposition
without necessarily completing a product conversion. - `NEGATIVE`: The
customer explicitly rejected, declined or negatively reacted to the
campaign communication. - `NEUTRAL`: The customer interacted with the
campaign but the interaction did not provide a clearly positive or
negative commercial signal.

**Rules:** - Must be NULL when `exposure_status = NOT_EXPOSED`. - Must
contain one valid value when `exposure_status = EXPOSED`. - `POSITIVE`
does not imply conversion. - `NEGATIVE` does not imply churn, account
closure or termination of the customer relationship. - `NO_RESPONSE`
must not be interpreted as rejection. - `NEUTRAL` requires some
observable interaction. - Customer response must occur after at least
one valid campaign exposure. - Response classification must be generated
from customer-level behavior and must not be predetermined from campaign
identity. - Campaign performance must not determine individual response
records retrospectively.

**Generation assumptions:** - `NO_RESPONSE` should normally be a common
outcome in commercial campaigns. - Positive, neutral and negative
responses should occur with behaviorally plausible frequencies. -
Response probabilities may depend on customer-campaign fit, product
relevance, channel, timing, previous behavior, geographic context and
campaign fatigue. - Repeated or excessive campaign exposure may increase
`NO_RESPONSE` or `NEGATIVE` probability. - Strong customer-product fit
may increase `POSITIVE` probability without guaranteeing it. - Random
individual variation must remain present. - No campaign is guaranteed to
produce more positive than negative or neutral behavioral impact.

## response_date

**Description:** Date on which the first observable customer response to
the BTYT campaign was recorded.

**Data type:** - Date - NULL

**Format:** - `YYYY-MM-DD`

**Rules:** - Must be NULL when `response_status = NO_RESPONSE`. - Must
be NULL when `exposure_status = NOT_EXPOSED`. - Must contain a valid
date when `response_status` is `POSITIVE`, `NEGATIVE` or `NEUTRAL`. -
Must be equal to or later than `exposure_date`. - Must not precede any
valid campaign exposure. - May occur after `campaigns.end_date` when the
response can reasonably be attributed to an exposure that occurred
during the active campaign period. - Must not exceed the BTYT dataset
end date (`2026-12-31`). - Represents the first observable customer
response associated with the campaign. - Subsequent interactions must
not overwrite the original `response_date`. - Response timing must not
be generated based on whether the customer ultimately converts. -
Historical response dates must not be retrospectively modified based on
campaign performance.

**Generation assumptions:** - Most observable responses should occur
relatively close to campaign exposure. - Response delays may vary
according to channel, campaign proposition, customer characteristics and
product complexity. - Simple propositions may generate relatively rapid
responses. - Products requiring greater consideration, such as mortgages
or business financing, may generate longer response delays. - Immediate
response must not be required. - Long response delays should become
progressively less likely. - Exact response timing must contain
individual variation.

01 campaign_id 02 customer_id 03 selection_date 04 exposure_status 05
exposure_date 06 response_status 07 response_date

## Phase 3 campaign-customer generation rules

### Eligibility, exposure and conversion
- Campaign targeting, actual exposure, engagement and conversion are conceptually distinct stages.
- Python may maintain internal states such as `eligible`, `exposed`, `engaged` and `converted` even when they are not persisted as separate columns in the final table.
- Inclusion in a campaign target population must not mechanically imply that the customer saw, engaged with or converted because of the campaign.
- Customer response must emerge probabilistically from campaign design, customer eligibility, product holdings, behavioral preferences, financial context, prior history and stochastic variation.

### No manufactured campaign success
- Customer product acquisition, channel migration, increased spending or other post-campaign behavior must not be created solely to satisfy a desired campaign result.
- Customers may ignore an apparently well-designed campaign, respond to a weak campaign, adopt the promoted behavior without campaign exposure, or reverse behavior later.
- Campaign-level performance must be calculated from generated customer outcomes after simulation.

### Temporal integrity
- Customer response must occur only after a plausible campaign exposure time.
- Product openings, transactions or behavioral changes dated before campaign exposure must not be attributed to that campaign.
- Broader secular trends and unrelated customer shocks must remain independent sources of post-campaign behavior.
