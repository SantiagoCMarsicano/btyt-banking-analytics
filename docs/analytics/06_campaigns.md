# 06 — Campaigns & Marketing Effectiveness Analytics

## Objective

Build a reusable analytical framework for BTYT's marketing campaigns, customer targeting, exposure history and campaign response.

The main question is:

> **How are BTYT campaigns designed, who is targeted and exposed, through which channels and geographies, and how effectively do campaigns generate customer response?**

This file should distinguish clearly between:

1. campaign design;
2. customer selection;
3. actual exposure;
4. response;
5. channel and geographic execution;
6. downstream performance analysis.

The objective is not to precompute every campaign KPI in SQL. PostgreSQL should prepare stable campaign-level and campaign-customer analytical grains so that Power BI / DAX can calculate dynamic funnel and response measures.

---

## Scope

This analysis focuses on:

- campaign inventory;
- campaign type;
- target product;
- target customer type;
- campaign start and end dates;
- customer selection;
- exposure status;
- exposure dates;
- response status;
- response dates;
- exposure events;
- campaign channels;
- campaign geography;
- campaign reach;
- campaign response;
- channel participation;
- geographic coverage;
- customer-segment participation;
- time-to-response;
- campaign overlap;
- campaign execution consistency.

---

## Out of Scope

The following topics belong elsewhere:

- customer demographic structure → `01_customers.sql`
- product/account portfolio behavior → `02_products_accounts.sql`
- loan quality → `03_loans.sql`
- transaction behavior → `04_transactions.sql`
- branch performance → `05_branches.sql`
- consolidated profitability → `07_performance.sql`

Campaign analysis may join customers, products, branches or transactions for interpretation, but this file should remain centered on campaign design, execution and response.

---

## Main Tables

### Primary tables

- `marketing.campaigns`
- `marketing.campaign_customers`
- `marketing.campaign_exposures`

### Supporting reference tables

- `reference.campaign_channels`
- `reference.campaign_geography`

### Supporting dimensions

- `core.customers`
- `core.products`
- `core.branches`

---

## Key Analytical Grains

### Campaign grain

> **1 row = 1 campaign**

Use for:

- campaign design;
- target product;
- target customer type;
- start/end dates;
- duration;
- number of configured channels;
- number of configured geographic targets.

---

### Campaign-customer grain

> **1 row = 1 campaign × 1 customer**

Source:

- `marketing.campaign_customers`

Use for:

- selected customers;
- exposure status;
- exposure date;
- response status;
- response date;
- funnel metrics;
- segment-level response analysis;
- time-to-response.

This is the principal reusable campaign-performance grain.

---

### Exposure-event grain

> **1 row = 1 exposure event**

Source:

- `marketing.campaign_exposures`

Use for:

- number of contacts;
- exposure frequency;
- channel used;
- repeated contacts;
- customer-level exposure intensity.

A customer may receive multiple exposure events for the same campaign.

Therefore:

> **Exposure events must not be confused with exposed customers.**

---

### Campaign-channel grain

> **1 row = 1 campaign × 1 configured channel**

Source:

- `reference.campaign_channels`

Use for:

- campaign design;
- planned channel mix;
- validating actual exposure channels.

---

### Campaign-geography grain

> **1 row = 1 campaign × 1 geography rule/value**

Source:

- `reference.campaign_geography`

Use for:

- campaign target geography;
- campaign reach;
- geographic campaign design.

---

## Funnel Semantics

Campaign analysis uses explicit customer-level statuses.

### Selected customers

Every row in:

- `marketing.campaign_customers`

is part of the selected population.

### Exposed customers

Canonical definition:

```text
exposure_status = 'EXPOSED'
```

Exposure events in `marketing.campaign_exposures` describe contact intensity and channel history. They do not redefine the canonical customer-level exposure flag.

### Observed responding customers

Canonical observed-response definition:

```text
response_status IN ('POSITIVE', 'NEGATIVE', 'NEUTRAL')
```

`NO_RESPONSE` means exposed without an observable response.

A NULL `response_status` is valid for customers who were not exposed.

`response_date` is timing metadata. It is not the response definition itself.

### Positive response

```text
response_status = 'POSITIVE'
```

is a commercially useful outcome but still does **not** automatically mean product conversion.
## Critical Denominator Rule

Two valid but different response rates may exist:

### Response rate among selected

```text
responding customers / selected customers
```

This measures campaign effectiveness from the original targeting population.

### Response rate among exposed

```text
responding customers / exposed customers
```

This measures response conditional on actual contact.

Both are useful, but they answer different questions.

Do not report a generic `response_rate` without documenting the denominator.

---

## Main Business Questions

### 1. Campaign Inventory

1. How many campaigns exist?
2. What campaign types are represented?
3. Which products are targeted?
4. Which customer types are targeted?
5. How long does each campaign run?
6. How many campaigns overlap in time?
7. How has campaign activity evolved over the years?

---

### 2. Campaign Targeting

8. How many customers are selected for each campaign?
9. Which campaigns target the largest populations?
10. How does selected population differ by customer type?
11. Which customer segments are most frequently targeted?
12. Are some customers selected into many campaigns?
13. Does campaign targeting align with `target_customer_type`?
14. Does campaign targeting align with the target product?

---

### 3. Exposure

15. How many selected customers are actually exposed?
16. What is the exposure rate among selected customers?
17. Which campaigns have the largest gap between selection and exposure?
18. How many exposure events occur per exposed customer?
19. Are some customers contacted repeatedly?
20. Does exposure frequency differ by campaign type?
21. How long after selection does exposure occur?

---

### 4. Response

22. How many customers respond to each campaign?
23. What is the response rate among selected customers?
24. What is the response rate among exposed customers?
25. Which campaigns generate more responses?
26. Which campaigns generate higher response rates?
27. Does response differ by customer type?
28. Does response differ by customer segment?
29. How long does it take customers to respond after exposure?

Response counts and response rates should be treated separately.

A large campaign may generate many responses but a lower rate.

---

### 5. Channel Execution

30. Which channels are configured for each campaign?
31. Which channels are actually used in exposure events?
32. Does actual exposure match configured channel design?
33. Which channels generate the most exposure events?
34. Which channels reach the most unique customers?
35. Are some campaigns heavily dependent on one channel?
36. Are some customers exposed through multiple channels?

---

### 6. Channel Response

37. Does response differ across exposure channels?
38. Do multi-channel customers respond differently from single-channel customers?
39. Does exposure frequency affect response?
40. Does channel effectiveness differ by customer type?
41. Does channel effectiveness differ by campaign type?

Caution:

If customers are exposed through multiple channels before responding, assigning the response to a single channel requires an attribution rule.

---

## Attribution Rule

The data model contains exposure events but does not inherently guarantee causal channel attribution.

Therefore:

> **Do not automatically claim that the last or first exposure channel caused the response.**

Possible future attribution rules include:

- first-touch;
- last-touch;
- any-touch;
- multi-touch;
- equal credit.

If such a rule is introduced, it must be documented explicitly.

For Part I, channel-response analysis should preferably describe association rather than causal attribution.

---

### 7. Geography

42. Which campaigns are geographically targeted?
43. At what geographic level are campaigns configured?
44. Which regions/departments/localities receive more campaigns?
45. Does campaign response differ geographically?
46. Are some geographies repeatedly targeted?
47. Does geographic targeting align with customer residence?
48. Does campaign reach differ from branch-network coverage?

Geographic interpretation should preserve `geography_level` and `geography_value`.

---

### 8. Product Alignment

49. Which products receive the most campaign support?
50. Which target products have higher campaign response?
51. Does campaign response differ by product family?
52. Are campaigns targeting products appropriate for the selected customer type?
53. Are some products heavily promoted but weakly responded to?

Product adoption after response would require a clearly defined post-campaign conversion rule and should not be inferred automatically from response alone.

---

### 9. Customer Campaign Intensity

54. How many campaigns is each customer selected into?
55. How many campaigns is each customer exposed to?
56. Which customers receive the most exposure events?
57. Is campaign saturation associated with lower response?
58. Are some customer segments over-contacted?
59. Does repeated campaign contact increase or reduce response?

Distributional questions are especially suitable for Python.

---

### 10. Campaign Timing

60. How does campaign response evolve during the campaign window?
61. Are responses concentrated early or late?
62. How long after exposure does response typically occur?
63. Do longer campaigns perform differently from shorter ones?
64. Are campaign periods seasonal?
65. Do overlapping campaigns complicate response interpretation?

---

### 11. Campaign Overlap

66. How many customers are simultaneously selected into multiple campaigns?
67. How often do campaigns overlap in calendar time?
68. Are customers responding while multiple campaigns are active?
69. Could overlapping campaigns make simple attribution ambiguous?

This is an important analytical limitation and should be visible in the final documentation.

---

## Temporal Variables

Main temporal fields include:

- `marketing.campaigns.start_date`
- `marketing.campaigns.end_date`
- `marketing.campaign_customers.selection_date`
- `marketing.campaign_customers.exposure_date`
- `marketing.campaign_customers.response_date`
- `marketing.campaign_exposures.exposure_datetime`

Useful derived fields may include:

- campaign duration;
- days from selection to exposure;
- days from exposure to response;
- exposure month;
- response month;
- exposure count per customer;
- active campaign count by date.

---

## SQL vs DAX vs Python Boundary

### SQL

SQL should own:

- campaign dimension;
- campaign-customer joins;
- exposure-event aggregation;
- customer-level exposure counts;
- first / last exposure timestamps;
- reusable funnel flags;
- response-lag fields;
- channel-count fields;
- campaign geography structure;
- campaign overlap diagnostics;
- execution-consistency diagnostics.

SQL is responsible for ensuring that campaign grain and exposure-event grain are not accidentally multiplied.

---

### DAX / Power BI

DAX should own dynamic measures such as:

- Campaign Count;
- Selected Customers;
- Exposed Customers;
- Exposure Rate %;
- Responding Customers;
- Positive Responses;
- Response Rate — Selected %;
- Response Rate — Exposed %;
- Positive Response Rate — Exposed %;
- Exposure Events;
- Exposures per Exposed Customer;
- Average Response Lag;
- Multi-Channel Customer %;
- Campaign Share by Product;
- Campaign Share by Region.

These measures should respond to filters such as:

- campaign;
- campaign type;
- target product;
- target customer type;
- customer type;
- customer segment;
- channel;
- geography;
- start/end period.

---

### Python / Pandas / Jupyter

Python is appropriate for:

- exposure-frequency distributions;
- response-lag distributions;
- campaign saturation analysis;
- customer-level campaign overlap;
- multi-touch exploratory analysis;
- statistical comparison of responding vs non-responding populations;
- campaign clustering;
- exploratory uplift analysis.

Python should not be used to imply causal campaign effectiveness unless the experiment or identification strategy supports that claim.

---

### Tableau

Tableau is especially useful for:

- geographic campaign coverage;
- campaign response maps;
- target versus response geography;
- spatial campaign storytelling.

---

## Recommended SQL Analytical Objects

### 1. Campaign dimension

Recommended grain:

```text
1 row = 1 campaign
```

Include:

- campaign ID/name/type;
- target product;
- target product family;
- target customer type;
- start/end dates;
- duration;
- configured channel count;
- configured geography count.

---

### 2. Campaign-customer analytical base

Recommended grain:

```text
1 row = 1 campaign × 1 customer
```

Include:

- selection date;
- exposure status;
- exposure date;
- response status;
- response date;
- exposure event count;
- first exposure;
- last exposure;
- distinct exposure channels;
- response lag;
- customer type;
- customer segment;
- residence geography;
- target product.

This should be the principal Power BI campaign source.

---

### 3. Campaign exposure-event base

Recommended grain:

```text
1 row = 1 exposure event
```

Use when detailed channel sequencing or exposure timing is required.

Do not make this the default dashboard grain if the campaign-customer base already answers the business question.

---

## Data-Quality Checks

Before analytical use, verify:

- campaign IDs are unique;
- campaign end date is not before start date;
- campaign-customer grain is unique;
- exposure IDs are unique;
- campaign exposure rows reference valid campaigns/customers;
- exposure dates fall within reasonable campaign periods;
- response dates do not precede selection dates;
- response dates do not precede exposure dates when exposure is required;
- configured campaign channels are valid;
- actual exposure channels are compatible with configured channels;
- campaign geography rows are valid;
- target product IDs are valid;
- target customer type is coherent with actual selected customer population;
- response/exposure status values are inventoried before KPI definitions.

---

## Interpretation Cautions

### Response is not automatically conversion

A `POSITIVE` `response_status` means a positive observed campaign response according to the dataset definition.

It does not automatically mean:

- product purchase;
- account opening;
- loan origination;
- revenue generation.

A conversion KPI requires a separately documented conversion event and window.

### Channel association is not causality

If a customer receives several contacts, a response cannot automatically be attributed to a single channel.

### Campaign overlap matters

A customer may be affected by multiple simultaneous campaigns.

Any causal interpretation requires stronger methodology.

---

## Expected Outputs

By the end of `06_campaigns.sql`, the project should have:

1. a reusable campaign dimension;
2. a reusable campaign-customer analytical base;
3. a reusable exposure-event base;
4. explicit funnel semantics;
5. exposure and response diagnostics;
6. campaign channel and geography validation;
7. overlap diagnostics;
8. clean handoff to Power BI / DAX;
9. clean handoff to Tableau for geography;
10. clean handoff to Python for distributional / multi-touch analysis.

---

## Analytical Boundary

This file should answer:

> **Who is targeted, who is actually contacted, who responds, through which campaign structures, channels and geographies, and how should campaign performance be measured?**

It should not automatically answer:

> **Which channel caused the customer to respond?**

That requires an attribution rule.

It should not automatically answer:

> **Did the campaign generate incremental sales?**

That requires a conversion definition and potentially a causal design.
