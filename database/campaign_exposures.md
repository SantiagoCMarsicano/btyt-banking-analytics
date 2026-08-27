# BTYT --- Campaign Exposures Data Dictionary

## Table: `campaign_exposures`

**Description:**\
Event-level table containing successful customer exposures to BTYT
commercial campaign communications.

**Grain:**\
One row represents one successful campaign communication delivered to
one customer through one marketing channel at a specific point in time.

**Primary key:**\
`exposure_id`

**Purpose:**\
Represent individual campaign contacts at event level, enabling analysis
of campaign frequency, multichannel exposure, contact intensity and
campaign fatigue.

**References:** - `campaign_id` → foreign key to
`campaigns.campaign_id` - `customer_id` → foreign key to
`customers.customer_id` - `campaign_id + customer_id` → must correspond
to a valid relationship in `campaign_customers` -
`campaign_id + channel` → must correspond to a valid relationship in
`campaign_channels`

------------------------------------------------------------------------

## Variables

## exposure_id

**Description:** Unique identifier assigned to each successful BTYT
campaign exposure event.

**Data type:** - String

**Format:** - `E` followed by a sequential numeric identifier.

**Examples:** - `E000001` - `E000002` - `E125487`

**Rules:** - Must not be NULL. - Must be unique. - Used as the primary
key of `campaign_exposures`. - Each identifier represents exactly one
successful customer-level campaign contact. - Must not encode campaign,
customer, channel, date or response information. - Identifiers must
remain stable after synthetic data generation.

## campaign_id

**Description:** Identifier of the BTYT commercial campaign associated
with the exposure event.

**Data type:** - String

**Reference:** - Foreign key to `campaigns.campaign_id`.

**Rules:** - Must not be NULL. - Must contain a valid `campaign_id`. -
The combination `campaign_id + customer_id` must correspond to an
existing record in `campaign_customers`. - The referenced
customer-campaign relationship must have `exposure_status = EXPOSED`. -
The campaign must be active on the date of the exposure event. -
Campaign characteristics must be obtained from the `campaigns` master
table and must not be duplicated in `campaign_exposures`. - A campaign
may appear in multiple exposure records for the same customer when
multiple valid contacts occur. - Exposure records must not be generated
based on future customer response or conversion. - Historical campaign
identifiers associated with exposure events must not be modified after
data generation.

------------------------------------------------------------------------

## customer_id

**Description:** Identifier of the BTYT customer receiving the campaign
exposure.

**Data type:** - String

**Reference:** - Foreign key to `customers.customer_id`.

**Rules:** - Must not be NULL. - Must contain a valid `customer_id`. -
The combination `campaign_id + customer_id` must correspond to an
existing record in `campaign_customers`. - The corresponding
`campaign_customers.exposure_status` must equal `EXPOSED`. - A customer
may have multiple exposure records for the same campaign. - A customer
may also receive exposures from multiple campaigns over time. - Customer
eligibility and campaign selection must be determined in
`campaign_customers`; `campaign_exposures` must not independently select
customers. - Exposure frequency must remain behaviorally and
operationally plausible. - Customers must not receive additional
exposures merely because they are predetermined to respond positively. -
Previous campaign exposure may influence the probability and timing of
subsequent contacts through campaign-frequency and fatigue mechanisms. -
Historical customer identifiers associated with exposure events must not
be modified after data generation.

## exposure_datetime

**Description:** Date and time at which a successful BTYT campaign
communication was delivered to the customer.

**Data type:** - Datetime

**Format:** - `YYYY-MM-DD HH:MM:SS`

**Rules:** - Must not be NULL. - Must represent a valid date and time. -
Must be equal to or later than `campaign_customers.selection_date`. -
Must occur between `campaigns.start_date` and `campaigns.end_date`. -
Must not exceed the BTYT dataset end date (`2026-12-31`). - The earliest
`exposure_datetime` date for each `campaign_id + customer_id` must
correspond to `campaign_customers.exposure_date`. - Customers with
`campaign_customers.exposure_status = NOT_EXPOSED` must have zero
records in `campaign_exposures`. - Multiple exposure events may occur
for the same customer and campaign. - Duplicate exposure events for the
same customer, campaign, channel and datetime are not allowed. -
Exposure timing must not depend on future customer response or
conversion. - Historical exposure events must remain unchanged after
generation.

**Generation assumptions:** - Exposure events must occur at behaviorally
and operationally plausible times. - Exposure frequency and timing must
vary across customers and campaigns. - Most customers should receive a
limited number of contacts per campaign. - A minority of customers may
receive multiple contacts, particularly in multichannel campaigns or
after non-response. - Exposure events must not be uniformly distributed
throughout the campaign period. - Campaign rollout may produce periods
of higher and lower communication intensity. - Follow-up contacts may
occur after previous non-response or neutral interaction. - Customers
who have already responded positively or negatively may receive fewer
subsequent contacts depending on campaign strategy. - Exact exposure
frequency must not be predetermined from campaign success.

### Channel-specific timing

-   `EMAIL`, `SMS`, `MOBILE_APP` and `WEB` exposures may occur across
    broader time windows than human-mediated channels.
-   `PHONE` exposures should generally occur during plausible commercial
    contact hours.
-   `BRANCH` exposures must occur during plausible branch or agency
    operating periods.
-   `DIRECT_MAIL` exposure represents the estimated delivery date of
    physical correspondence rather than the date on which it was
    dispatched.
-   `SOCIAL_MEDIA` exposures may occur across broader daily time
    windows.
-   Channel-specific timing should contain realistic variation and must
    not follow perfectly repetitive schedules.

### Contact frequency and campaign fatigue

-   Recent exposure to the same campaign may reduce the probability of
    another immediate contact.
-   Repeated exposures should normally be separated by plausible time
    intervals.
-   Excessively dense contact sequences should be uncommon.
-   Exposure frequency may depend on previous response behavior.
-   Exposure frequency across different campaigns must also be
    considered when generating customer-level campaign fatigue.
-   Customers exposed repeatedly across multiple campaigns within short
    periods may become less responsive to subsequent campaign
    communications.
-   Campaign fatigue must influence probabilities rather than impose
    deterministic customer behavior.

## channel

**Description:** Marketing communication channel through which the
individual BTYT campaign exposure occurred.

**Data type:** - String / Categorical

**Allowed values:** - `EMAIL` - `SMS` - `MOBILE_APP` - `WEB` -
`BRANCH` - `PHONE` - `SOCIAL_MEDIA` - `DIRECT_MAIL`

**Reference:** - `campaign_id + channel` must correspond to a valid
combination in `campaign_channels`.

**Rules:** - Must not be NULL. - Must contain exactly one valid
marketing channel. - The channel must be authorized for the
corresponding campaign in `campaign_channels`. - A customer may receive
the same campaign through multiple channels. - A customer may receive
multiple exposures through the same channel when operationally
plausible. - `channel` represents the actual customer-level exposure
channel, not merely a channel available to the campaign. - Marketing
channels must not be confused with transaction-processing channels in
`transactions.channel`. - Channel assignment must not depend on future
customer response or conversion.

**Generation assumptions:** - Customer-level channel selection must be
conditional rather than uniformly random. - Channel probability may
depend on: - customer characteristics; - customer type; - digital
engagement; - available contact information; - campaign strategy; -
geographic context; - branch relationship; - previous channel
interactions; - historical period; - previous campaign exposure.

-   Customers should not automatically receive exposure through every
    channel authorized for a campaign.
-   Multi-channel exposure should occur for a meaningful subset of
    customers without becoming universal.
-   Channel preferences and availability may change over time.

### DIRECT_MAIL

-   `DIRECT_MAIL` should be more plausible for customers with lower
    digital engagement, selected rural populations, premium
    relationships and campaigns where formal physical communication is
    commercially reasonable.
-   Its relative usage may decline over the 2021--2026 analytical period
    without disappearing completely.
-   Rural, older or premium customers must not automatically receive
    `DIRECT_MAIL`.
-   Physical correspondence must retain customer-level variation.

### Channel effectiveness

-   No channel is intrinsically defined as more effective than another.
-   Channel-response relationships must emerge from generated customer
    behavior.
-   Channel effectiveness may differ across customer profiles, campaign
    types, products, geography and time.
-   Multi-channel exposure must not automatically increase positive
    response probability.
-   Excessive multichannel contact may contribute to campaign fatigue
    and negative response.
