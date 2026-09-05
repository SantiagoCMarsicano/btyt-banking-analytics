# BTYT — Customers Data Dictionary

## Table: `customers`

**Description:**

Master table containing the core demographic, geographic and
relationship attributes of BTYT customers.

**Grain:**

One row represents one unique BTYT customer.

**Primary key:**

`customer_id`

**Purpose:**

Provide the central customer dimension used to connect customers with
accounts, products, transactions and other analytical tables across the
BTYT banking data model.

------------------------------------------------------------------------

## Variables

## customer_id

**Description:** Unique internal identifier assigned to each BTYT
customer.

**Data type:**

-   String

**Format:**

-   `C` followed by six numeric digits.

**Examples:**

-   `C0000001`

-   `C0000002`

-   `C0025417`

**Rules:**

-   Must be unique.

-   Must not be NULL.

-   Used as the primary key of the `customers` table.

-   Must remain unchanged throughout the customer's relationship with
    BTYT.

-   Must not contain demographic, geographic or commercial information.

-   Must be independent from the customer's identification document.

## customer_type

**Description:** Classification of the customer according to the nature
of the banking relationship.

**Data type:**

-   String / Categorical

**Allowed values:**

-   `INDIVIDUAL`

-   `BUSINESS`

**Category definitions:**

-   `INDIVIDUAL`: Natural person holding one or more BTYT banking
    products.

-   `BUSINESS`: Legal or commercial entity holding one or more BTYT
    banking products.

**Rules:**

-   Every customer must have exactly one `customer_type`.

-   Must not be NULL.

-   `customer_type` determines which customer-specific attributes are
    applicable.

-   The classification remains stable throughout the lifetime of the
    customer record.

**Generation assumptions:**

-   The BTYT customer base is predominantly composed of individual
    customers.

-   The exact distribution is not predetermined and will be generated
    within the following ranges:

    -   `INDIVIDUAL`: 85%--92%

    -   `BUSINESS`: 8%--15%

-   The generated distribution must remain within these ranges.

-   The final observed distribution should be treated as an analytical
    result rather than a predefined target.

## first_name

**Description:** Synthetic first name of an individual BTYT customer.

**Data type:**

-   String
-   NULL

**Rules:**

-   Applies only when `customer_type = INDIVIDUAL`.
-   Must be `NULL` when `customer_type = BUSINESS`.
-   Must not contain real customer-identifying information.
-   The value is generated synthetically from nationality- and gender-compatible name pools.
-   Name selection must remain probabilistic and must not deterministically encode age, nationality, gender, income, risk or product ownership.

**Generation assumptions:**

-   First-name generation uses overlapping birth-cohort pools (`OLD`, `MIDDLE`, `YOUNG`) rather than hard age cutoffs.
-   Birth year changes the probability of selecting a cohort-specific pool, while anachronistic names remain possible.
-   Name pools are nationality-specific and gender-aware.
-   `OTHER_OR_UNSPECIFIED` gender records may use a neutral name pool or probabilistically draw from male/female pools.
-   Common and less-common names should coexist within each pool.
-   The final name-frequency distribution must emerge from the synthetic generation process rather than from fixed per-name target counts.
-   The latent cohort used for generation is an internal development-audit variable and is not exported to `customers.csv`.

## last_name

**Description:** Synthetic surname of an individual BTYT customer.

**Data type:**

-   String
-   NULL

**Rules:**

-   Applies only when `customer_type = INDIVIDUAL`.
-   Must be `NULL` when `customer_type = BUSINESS`.
-   Must not contain real customer-identifying information.
-   Surname generation is nationality-aware but probabilistic.
-   Compound surnames are allowed.
-   Surname choice must not deterministically encode geography, income, risk or product ownership.

**Generation assumptions:**

-   Surnames follow non-uniform synthetic frequency weights so that common and less-common surnames coexist.
-   A minority of individual customers may receive a compound surname.
-   Repeated surnames across unrelated customers are expected and realistic.
-   Exact surname frequencies are not predetermined.

## company_name

**Description:** Synthetic commercial name assigned to a BTYT business customer.

**Data type:**

-   String
-   NULL

**Rules:**

-   Applies only when `customer_type = BUSINESS`.
-   Must be `NULL` when `customer_type = INDIVIDUAL`.
-   Must not intentionally reproduce or identify a real company.
-   Company names do not need to be unique.
-   The generated name should be broadly compatible with `business_sector`, `company_size` and geographic context without mechanically revealing those fields.

**Generation assumptions:**

-   Micro and small businesses may more frequently use family surnames, local references or traditional commercial naming patterns.
-   Medium and large businesses may more frequently use institutional naming structures.
-   Legal-style suffixes such as `Ltda.` or `S.A.` may appear probabilistically.
-   Agricultural, tourism, logistics, commerce and professional-services customers may draw from sector-specific naming structures.
-   Border-area businesses may show occasional Portuguese-influenced surnames or naming patterns.
-   Exact company-name frequencies and structures are not predetermined.

## nationality

**Description:** Nationality of an individual BTYT customer.

**Data type:**

-   String / Categorical

**Allowed values:**

-   `URUGUAY`

-   `ARGENTINA`

-   `BRAZIL`

-   `VENEZUELA`

-   `CUBA`

-   `OTHER`

**Rules:**

-   Applies only when `customer_type = INDIVIDUAL`.

-   Must be `NULL` when `customer_type = BUSINESS`.

-   Every individual customer must have exactly one nationality.

-   `nationality` is independent from the customer's place of residence.

-   `OTHER` groups nationalities with insufficient representation to
    justify a separate analytical category.

**Generation assumptions:**

-   The customer base should remain predominantly Uruguayan.

-   No exact nationality distribution is predetermined.

-   `URUGUAY` should represent approximately 85%--94% of individual
    customers.

-   All foreign nationalities combined should represent approximately
    6%--15%.

-   Within the foreign population, `ARGENTINA` and `BRAZIL` should
    generally have greater representation than smaller nationality
    groups.

-   Geographic context may influence nationality probabilities without
    determining them mechanically.

-   Border and tourism-related locations may exhibit higher
    foreign-customer representation.

-   The final nationality distribution should emerge from the generation
    process within plausible constraints rather than from fixed target
    percentages.

## document_type

**Description:** Type of identification document associated with the
BTYT customer.

**Data type:**

-   String / Categorical

**Allowed values:**

-   `CI`

-   `PASSPORT`

-   `FOREIGN_ID`

-   `RUT`

**Rules:**

-   `CI` applies primarily to individual customers identified with a
    Uruguayan identity card.

-   `PASSPORT` applies to individual customers identified through a
    passport.

-   `FOREIGN_ID` applies to foreign individual customers using another
    valid identification document.

-   `RUT` applies only when `customer_type = BUSINESS`.

-   Every customer must have exactly one `document_type`.

-   `RUT` must not be assigned to `INDIVIDUAL` customers.

-   `CI`, `PASSPORT` and `FOREIGN_ID` must not be assigned to `BUSINESS`
    customers.

**Generation assumptions:**

-   Most `URUGUAY` individual customers should use `CI`.

-   Foreign individual customers may use `PASSPORT` or `FOREIGN_ID`.

-   Some foreign nationals residing long-term in Uruguay may also hold a
    synthetic Uruguayan `CI` in the generated dataset.

-   The exact distribution of document types is not predetermined and
    should emerge from nationality and customer-type rules.

## document_id

**Description:** Synthetic identification-document identifier associated
with the BTYT customer.

**Data type:** - String

**Rules:** - Must not be NULL. - Must be unique within each applicable
`document_type`. - Must be compatible with the customer's
`document_type` and `customer_type`. - Must not contain real personal
identification data. - Must be synthetically generated for the BTYT
dataset. - `RUT` identifiers apply only to `BUSINESS` customers. - `CI`,
`PASSPORT` and `FOREIGN_ID` identifiers apply only to `INDIVIDUAL`
customers. - The identifier must remain stable throughout the customer's
relationship with BTYT. - `document_id` must not be used as the primary
key of the customer dimension; `customer_id` remains the internal BTYT
primary key.

**Generation assumptions:** - Values must be synthetic and must not
intentionally reproduce real identification numbers. - Formatting may
vary according to `document_type`. - Synthetic identifiers should
preserve enough structural realism for data-quality and analytical
exercises without attempting to create valid real-world credentials. -
For `CI`, generation may be partially associated with `birth_year` for
plausible historical sequencing, without encoding deterministic
demographic information.

## birth_year

**Description:** Year of birth of an individual BTYT customer.

**Data type:**

-   Integer

-   NULL

**Rules:**

-   Applies only when `customer_type = INDIVIDUAL`.

-   Must be `NULL` when `customer_type = BUSINESS`.

-   Must represent a plausible year of birth.

-   Customer age at the time of joining BTYT must be compatible with the
    bank's minimum age requirements.

-   `birth_year` must precede `registration_year`.

-   `birth_year` is used to derive customer age dynamically and should
    not be replaced by a permanently stored age variable.

**Generation assumptions:**

-   The distribution of `birth_year` should not be uniform.

-   BTYT's customer base should include a broad adult age range, with
    greater concentration in economically active age groups.

-   Very young and very old customers should exist but represent smaller
    portions of the customer base.

-   The exact age distribution must not be predetermined and should
    emerge within plausible demographic ranges.

-   `birth_year` may influence product ownership, credit demand, digital
    adoption and other customer behaviors probabilistically.

-   `birth_year` must not deterministically determine any product,
    income level or risk outcome.

-   For customers with `document_type = CI`, `birth_year` may partially
    influence the synthetic `document_id` generation process.

## gender

**Description:** Gender classification of an individual BTYT customer.

**Data type:**

-   String / Categorical

-   NULL

**Allowed values:**

-   `FEMALE`

-   `MALE`

-   `OTHER_OR_UNSPECIFIED`

**Rules:**

-   Applies only when `customer_type = INDIVIDUAL`.

-   Must be `NULL` when `customer_type = BUSINESS`.

-   Every individual customer must have one valid gender category.

-   `OTHER_OR_UNSPECIFIED` groups customers who identify outside the
    binary categories or whose gender information is not specified.

-   `gender` must not deterministically define income, product
    ownership, credit risk or customer behavior.

**Generation assumptions:**

-   The distribution should be broadly balanced between `FEMALE` and
    `MALE`.

-   `OTHER_OR_UNSPECIFIED` should represent a small minority of
    individual customers.

-   Exact proportions must not be predetermined.

-   Gender may be used for descriptive segmentation but should not be
    used to mechanically create differences in financial performance or
    risk.

## residence_country

**Description:** Country of residence of the BTYT customer.

**Data type:**

-   String / Categorical

**Allowed values:**

-   `URUGUAY`

-   `ARGENTINA`

-   `BRAZIL`

-   `SPAIN`

-   `USA`

-   `OTHER`

**Rules:**

-   Every customer must have exactly one `residence_country`.

-   Must not be NULL.

-   `residence_country` represents the customer's current country of
    residence and is independent from `nationality`.

-   A customer may have `nationality = URUGUAY` while residing abroad.

-   A foreign-national customer may have `residence_country = URUGUAY`.

-   Customers residing outside Uruguay may maintain an active banking
    relationship with BTYT.

-   If `residence_country = URUGUAY`, `residence_department` and
    `residence_locality` must contain valid Uruguayan geographic values.

-   If `residence_country != URUGUAY`, `residence_department` and
    `residence_locality` must be `NULL`.

-   `OTHER` groups countries with insufficient representation to justify
    a separate analytical category.

**Generation assumptions:**

-   The large majority of BTYT customers should reside in Uruguay.

-   Customers residing abroad should represent a relatively small
    minority of the customer base.

-   The exact proportion of resident and non-resident customers must not
    be predetermined.

-   Non-resident customers may include both Uruguayan and foreign
    nationals.

-   `ARGENTINA` and `BRAZIL` should have relatively greater
    representation among foreign-resident customers because of their
    geographic proximity and economic links with Uruguay.

-   `SPAIN` and `USA` may represent relevant destinations for Uruguayan
    customers residing abroad.

-   Other countries should be grouped under `OTHER`.

-   Relationships between `nationality` and `residence_country` should
    be probabilistic rather than deterministic.

-   The final distribution should emerge from the synthetic data
    generation process within plausible constraints.

## residence_department

**Description:** Uruguayan department in which the BTYT customer
currently resides.

**Data type:**

-   String / Categorical

-   NULL

**Allowed values:**

-   Artigas

-   Canelones

-   Cerro Largo

-   Colonia

-   Durazno

-   Flores

-   Florida

-   Lavalleja

-   Maldonado

-   Montevideo

-   Paysandú

-   Río Negro

-   Rivera

-   Rocha

-   Salto

-   San José

-   Soriano

-   Tacuarembó

-   Treinta y Tres

**Rules:**

-   Applies only when `residence_country = URUGUAY`.

-   Must contain exactly one valid department when
    `residence_country = URUGUAY`.

-   Must be `NULL` when `residence_country != URUGUAY`.

-   Must be geographically consistent with `residence_locality`.

-   Does not need to match the department of `primary_branch_id`.

-   A customer may live in one department and maintain their main
    banking relationship with a branch or agency located in another
    department.

-   `nationality` does not determine `residence_department`.

**Generation assumptions:**

-   Customer residence across departments must not be uniformly
    distributed.

-   Department probabilities should be influenced by:

    -   population size;

    -   BTYT branch presence;

    -   historical market penetration;

    -   local economic activity;

    -   geographic proximity to BTYT offices.

-   Montevideo and Canelones should contain substantial customer
    populations because of their demographic scale.

-   Treinta y Tres and the broader EAST region should show stronger BTYT
    penetration relative to their population because of the bank's
    historical presence.

-   Departments with fewer BTYT offices may still contain significant
    customer populations due to digital banking and cross-department
    banking relationships.

-   Border departments may show relatively higher shares of
    foreign-national customers.

-   Exact departmental shares must not be predetermined.

-   The final distribution should emerge from the synthetic generation
    process within plausible territorial constraints.

## residence_locality

**Description:** Uruguayan city or locality in which the BTYT customer
currently resides.

**Data type:**

-   String

-   NULL

**Rules:**

-   Applies only when `residence_country = URUGUAY`.

-   Must be `NULL` when `residence_country != URUGUAY`.

-   Must represent a valid locality within the corresponding
    `residence_department`.

-   Must be geographically consistent with `residence_department`.

-   Customers are not required to live in a locality where BTYT operates
    a physical branch or agency.

-   Multiple localities may be served by the same BTYT banking office.

-   `residence_locality` does not determine `primary_branch_id`
    mechanically.

-   Locality names must use a standardized spelling.

**Generation assumptions:**

-   Locality distribution should not be uniform.

-   Department capitals and larger cities should generally contain more
    customers than small towns.

-   Small localities should remain represented, particularly in BTYT's
    historical EAST region.

-   BTYT's historical territorial strategy should create relatively
    strong penetration in smaller localities of Treinta y Tres and
    nearby areas.

-   Customers living in localities without a BTYT office may use the
    nearest office, another strategically connected office, or primarily
    digital banking channels.

-   Geographic distance may influence the probability of
    `primary_branch_id`, but must not determine it perfectly.

-   Border localities may exhibit distinctive nationality and customer
    profiles.

-   Tourism-oriented localities may exhibit distinctive customer
    compositions and seasonal behavior.

-   Exact locality shares must not be predetermined and should emerge
    from the generation process.

## primary_branch_id

**Description:** Identifier of the BTYT branch or agency that maintains the customer's primary banking relationship.

**Data type:**

-   String

**Reference:**

-   Foreign key to `branches.branch_id`.

**Format:**

-   Three-character zero-padded branch identifier (`001`--`037` in the current branch master).

**Rules:**

-   Must contain a valid `branch_id`.
-   Must reference an office that already existed when the customer relationship was established.
-   The selected office must not have closed before `registration_year`.
-   The primary office does not need to be located in the same department or locality as the customer's current residence.
-   `primary_branch_id` represents the customer's historical/origination commercial relationship with BTYT and not necessarily the nearest current physical office.
-   Customers may continue to be associated with an office after moving to another locality or department.
-   If the referenced office later closes, the historical `primary_branch_id` is preserved; later reassignment, if modeled, belongs in a separate process.

**Generation assumptions:**

-   Branch assignment is based on the customer's residence context at the time of registration, which may differ from current residence because historical relocation is modeled probabilistically.
-   Assignment uses a two-stage geographic process:
    1. select a geographic relationship category;
    2. select a specific eligible branch within that category.
-   This prevents a large number of distant branches from collectively overpowering a nearby office merely because there are more distant alternatives.
-   For customers residing in Uruguay, the available categories are:
    -   same locality;
    -   same department;
    -   same broad region;
    -   metropolitan relationship;
    -   other department.
-   If an eligible office exists in the customer's locality, same-locality relationships receive the strongest probability.
-   If no office exists in the locality but at least one exists in the department, same-department relationships receive the strongest probability.
-   If no eligible office exists in the department, regional and metropolitan relationships become more important.
-   Cross-department banking remains intentionally possible and should be more common in departments with weaker BTYT physical coverage.
-   BTYT's historical EAST region may retain a modest structural relationship advantage.
-   Larger offices receive a moderate capacity advantage.
-   Longer-established offices receive a modest relationship advantage.
-   Customer-level lognormal random variation is applied so branch assignment remains probabilistic rather than deterministic.
-   For non-resident customers, metropolitan offices receive the strongest probability, followed by EAST-region offices and other eligible offices.
-   The exact distribution of customers across branches must emerge from the generation process and must not be fixed to predetermined branch totals.

**Post-Python validation note:**

-   The development generator explicitly audits the share of customers whose current residence department differs from the department of `primary_branch_id`.
-   This diagnostic is not a target variable and is not stored in the final table.
-   It is used only to detect implausible branch-allocation behavior before freezing the generated customer population.

## registration_year

**Description:** Year in which the customer established their first
banking relationship with BTYT.

**Data type:**

-   Integer

**Format:**

-   YYYY

**Rules:**

-   Must represent a valid year.

-   Must not be later than the current analysis year.

-   Must be equal to or later than the opening year of the customer's
    original BTYT office.

-   For `INDIVIDUAL` customers, `registration_year` must be compatible
    with `birth_year` and minimum customer age requirements.

-   `registration_year` represents the beginning of the customer's
    relationship with BTYT, not the opening year of a specific account
    or product.

-   The value remains unchanged even if the customer later changes their
    primary branch, residence or product portfolio.

**Generation assumptions:**

-   Customer registrations should span multiple decades, reflecting
    BTYT's long history since 1969.

-   The distribution must not be uniform across years.

-   Older BTYT regions and offices should have a higher probability of
    containing long-tenure customers.

-   Recently opened offices cannot originate customer relationships
    prior to their own opening.

-   Later national and metropolitan expansion waves should generate
    visible increases in customer acquisition in the corresponding
    periods.

-   Customer acquisition may accelerate or slow during specific
    historical periods, campaigns or macroeconomic events.

-   The exact number of customers registered in each year must not be
    predetermined.

-   The final distribution should emerge from the generation process
    within historically plausible constraints.

## customer_status

**Description:** Current status of the customer's overall banking
relationship with BTYT.

**Data type:**

-   String / Categorical

**Allowed values:**

-   `ACTIVE`

-   `CLOSED`

**Category definitions:**

-   `ACTIVE`: Customer currently maintains at least one active banking
    relationship with BTYT.

-   `CLOSED`: Customer has completely ended their banking relationship
    with BTYT.

**Rules:**

-   Every customer must have exactly one `customer_status`.

-   Must not be NULL.

-   `customer_status = CLOSED` does not imply credit default or
    financial distress.

-   A customer may close their relationship voluntarily, migrate to
    another financial institution, become inactive after relocation, or
    leave BTYT for other reasons.

-   Customers associated with a branch or agency that later closes do
    not automatically become `CLOSED`.

-   Customers may remain `ACTIVE` after their original or primary office
    closes if their relationship is transferred, maintained digitally or
    continued through another BTYT office.

-   `customer_status` describes the overall customer relationship and is
    independent from the status of individual accounts or products.

**Generation assumptions:**

-   The majority of BTYT customers should remain `ACTIVE`.

-   The exact share of `ACTIVE` and `CLOSED` customers must not be
    predetermined.

-   Customer closure should emerge from a probabilistic process
    influenced by multiple factors rather than a single deterministic
    rule.

-   Potential influences on the probability of customer closure may
    include:

    -   customer tenure;

    -   geographic distance from BTYT offices;

    -   relocation;

    -   digital banking adoption;

    -   product ownership;

    -   transaction activity;

    -   branch or agency closure;

    -   changes in the customer's primary banking relationship;

    -   customer acquisition channel;

    -   previous commercial campaigns;

    -   random individual variation.

-   No individual factor should determine closure automatically.

-   Customers living far from a physical office may remain `ACTIVE`,
    particularly when they make strong use of digital channels.

-   Customers living close to an office may still become `CLOSED`.

-   Closure of a customer's primary or nearby branch may moderately
    increase the probability of customer closure without determining the
    outcome.

-   Customers historically associated with BTYT's core regions may
    exhibit stronger relationship persistence, but this effect must
    remain probabilistic.

-   The final distribution of `customer_status` and any geographic,
    demographic or behavioral patterns should be treated as analytical
    results rather than predefined targets.

## closing_year

**Description:** Year in which the customer completely ended their
banking relationship with BTYT.

**Data type:**

-   Integer

-   NULL

**Format:**

-   YYYY

-   NULL

**Rules:**

-   Must be `NULL` when `customer_status = ACTIVE`.

-   Must contain a valid year when `customer_status = CLOSED`.

-   Must be later than or equal to `registration_year`.

-   Must not be later than the current analysis year.

-   `closing_year` represents the end of the customer's overall
    relationship with BTYT, not the closure of an individual account or
    product.

-   A customer may have closed individual accounts or products before
    `closing_year` while maintaining other active relationships with
    BTYT.

-   `closing_year` does not indicate the reason why the customer left
    BTYT.

-   Closure of the customer's primary branch or agency does not
    automatically determine `closing_year`.

**Generation assumptions:**

-   Customer closures should be distributed across multiple years rather
    than concentrated uniformly or in a single period.

-   The probability of closure may vary over time due to customer
    tenure, branch-network changes, economic conditions, commercial
    strategies and individual circumstances.

-   Customers whose primary or nearby office closes may experience an
    increased probability of subsequently ending their BTYT
    relationship.

-   This effect must remain probabilistic: some affected customers
    should migrate successfully to another BTYT office or continue
    through digital channels.

-   `closing_year` should preserve temporal consistency with branch
    closures, customer registration and other customer events.

-   Very short and very long customer relationships should both be
    possible.

-   The final distribution of relationship duration and closure timing
    must emerge from the generation process rather than from
    predetermined analytical targets.

## employment_status

**Description:** Current employment or economic activity status of an
individual BTYT customer.

**Data type:**

-   String / Categorical

-   NULL

**Allowed values:**

-   `EMPLOYED`

-   `SELF_EMPLOYED`

-   `UNEMPLOYED`

-   `RETIRED`

-   `STUDENT`

-   `OTHER`

**Category definitions:**

-   `EMPLOYED`: Customer currently working as a salaried employee.

-   `SELF_EMPLOYED`: Customer primarily working independently, including
    professionals, sole traders and other self-employed workers.

-   `UNEMPLOYED`: Customer currently without employment and actively or
    potentially available for work.

-   `RETIRED`: Customer whose primary economic status is retirement or
    pension.

-   `STUDENT`: Customer whose primary current activity is studying.

-   `OTHER`: Other economic situations not sufficiently represented to
    justify a separate analytical category.

**Rules:**

-   Applies only when `customer_type = INDIVIDUAL`.

-   Must be `NULL` when `customer_type = BUSINESS`.

-   Every individual customer must have exactly one `employment_status`.

-   Employment status represents the customer's primary economic
    activity.

-   `employment_status` must be broadly consistent with `birth_year`,
    while allowing realistic exceptions.

-   Employment status must not deterministically determine income,
    product ownership, customer status or credit risk.

**Generation assumptions:**

-   `EMPLOYED` should represent the largest individual customer group.

-   `SELF_EMPLOYED`, `RETIRED`, `STUDENT` and `UNEMPLOYED` should have
    meaningful but smaller representation.

-   Exact proportions must not be predetermined.

-   The probability of each employment status should vary with customer
    age.

-   Younger adults should have a higher probability of `STUDENT`.

-   Older customers should have a higher probability of `RETIRED`.

-   Working-age customers should have higher probabilities of `EMPLOYED`
    or `SELF_EMPLOYED`.

-   Exceptions must remain possible; age must not mechanically determine
    employment status.

-   Employment status may probabilistically influence income, product
    demand and banking behavior.

-   The final relationships between employment status and financial
    behavior should emerge from the synthetic generation process.

## monthly_income

**Description:** Estimated monthly personal income of an individual BTYT
customer, expressed in Uruguayan pesos.

**Data type:**

-   Numeric / Decimal

-   NULL

**Currency:**

-   UYU (normalized reference currency)

**Rules:**

-   Applies only when `customer_type = INDIVIDUAL`.

-   Must be `NULL` when `customer_type = BUSINESS`.

-   Must be greater than or equal to zero.

-   Represents estimated regular monthly personal income rather than
    account inflows.

-   `monthly_income` must not be inferred directly from BTYT transaction
    volume.

-   Income should be broadly consistent with `employment_status`,
    `birth_year` and other socioeconomic characteristics, while
    preserving substantial individual variation.

-   Income must not deterministically determine product ownership,
    customer status or credit risk.

`monthly_income` represents the customer's estimated regular monthly
income expressed in UYU-equivalent terms. - Income originally received
in another currency must be normalized to UYU for analytical
comparability.

**Generation assumptions:**

-   The income distribution must be positively skewed rather than
    uniform.

-   Most customers should be concentrated in low-to-middle and middle
    income ranges, with progressively fewer high-income customers.

-   `EMPLOYED` and `SELF_EMPLOYED` customers should show broad and
    overlapping income distributions.

-   `RETIRED`, `STUDENT` and `UNEMPLOYED` customers should generally
    have different income profiles, without requiring income to be zero.

-   Very high-income customers should exist but represent a small
    minority.

-   Geographic and demographic characteristics may moderately influence
    income distributions.

-   The exact income distribution must not be predetermined and should
    emerge from the synthetic generation process within plausible
    constraints.

## business_sector

**Description:** Primary economic sector in which a BTYT business
customer operates.

**Data type:**

-   String / Categorical

-   NULL

**Allowed values:**

-   `AGRICULTURE`

-   `COMMERCE`

-   `TOURISM_HOSPITALITY`

-   `INDUSTRY`

-   `CONSTRUCTION`

-   `TRANSPORT_LOGISTICS`

-   `PROFESSIONAL_SERVICES`

-   `TECHNOLOGY`

-   `HEALTH_EDUCATION`

-   `OTHER_SERVICES`

**Rules:**

-   Applies only when `customer_type = BUSINESS`.

-   Must be `NULL` when `customer_type = INDIVIDUAL`.

-   Every business customer must have exactly one primary
    `business_sector`.

-   `business_sector` represents the customer's main economic activity.

-   A business may operate across multiple activities, but only the
    principal sector is recorded in this table.

-   `business_sector` must not deterministically determine revenue,
    company size, profitability or credit risk.

**Generation assumptions:**

-   Business-sector distribution must not be uniform.

-   Sector probabilities may vary according to `residence_department`,
    `residence_locality` and BTYT's territorial presence.

-   `AGRICULTURE` should have relatively greater representation in
    interior departments.

-   `TOURISM_HOSPITALITY` may have greater representation in
    tourism-oriented locations such as Maldonado and Rocha.

-   `COMMERCE` may have strong representation across the country and in
    border localities.

-   `PROFESSIONAL_SERVICES` and `TECHNOLOGY` may have relatively greater
    representation in metropolitan areas.

-   `TRANSPORT_LOGISTICS` may be more common in border, port and major
    commercial corridors.

-   These geographic relationships must remain probabilistic rather than
    deterministic.

-   Every sector should remain possible in multiple regions.

-   Exact sector shares must not be predetermined.

-   The final distribution should emerge from the synthetic generation
    process within plausible economic and geographic constraints.

## company_size

**Description:** Internal BTYT classification of a business customer's
organizational and economic scale.

**Data type:**

-   String / Categorical

-   NULL

**Allowed values:**

-   `MICRO`

-   `SMALL`

-   `MEDIUM`

-   `LARGE`

**Rules:**

-   Applies only when `customer_type = BUSINESS`.

-   Must be `NULL` when `customer_type = INDIVIDUAL`.

-   Every business customer must have exactly one `company_size`.

-   `company_size` represents the overall scale of the business
    relationship and organization.

-   The classification may consider factors such as revenue, employment,
    activity level and commercial scale.

-   `company_size` must not be determined by a single variable.

-   `company_size` must not deterministically define profitability,
    product ownership or credit risk.

**Generation assumptions:**

-   BTYT's business customer base should be concentrated primarily in
    `MICRO` and `SMALL` businesses.

-   `MEDIUM` businesses should represent a smaller but meaningful share.

-   `LARGE` businesses should exist but represent a relatively small
    minority.

-   Exact proportions must not be predetermined.

-   Company size probabilities may vary by `business_sector` and
    geography.

-   `COMMERCE`, `PROFESSIONAL_SERVICES` and `OTHER_SERVICES` may contain
    substantial numbers of `MICRO` and `SMALL` businesses.

-   `INDUSTRY`, `TRANSPORT_LOGISTICS` and `AGRICULTURE` may have
    relatively greater probabilities of containing `MEDIUM` or `LARGE`
    businesses.

-   These relationships must remain probabilistic rather than
    deterministic.

-   The final distribution of company sizes should emerge from the
    synthetic generation process within plausible constraints.

## foundation_year

**Description:** Year in which a BTYT business customer was originally
established.

**Data type:**

-   Integer

-   NULL

**Format:**

-   YYYY

**Rules:**

-   Applies only when `customer_type = BUSINESS`.

-   Must be `NULL` when `customer_type = INDIVIDUAL`.

-   Must represent a valid year.

-   Must be earlier than or equal to `registration_year`.

-   `foundation_year` represents the establishment of the business
    entity and not the beginning of its relationship with BTYT.

-   A business may have existed for many years before becoming a BTYT
    customer.

-   Business age should be derived dynamically from `foundation_year`
    rather than stored as a separate variable.

**Generation assumptions:**

-   Business foundation years must not be uniformly distributed.

-   The business customer base should contain both recently established
    companies and long-established firms.

-   Younger businesses should generally be more numerous than very old
    businesses.

-   Businesses with several decades of history should remain
    meaningfully represented.

-   A small number of businesses may predate BTYT's foundation in 1969.

-   `foundation_year` may be probabilistically associated with
    `company_size`, but must not determine it.

-   Older businesses may have a greater probability of being `MEDIUM` or
    `LARGE`, while recently established businesses may have a greater
    probability of being `MICRO` or `SMALL`.

-   Exceptions must remain common: young companies may become large and
    long-established businesses may remain small.

-   Business age may later influence product demand, commercial
    relationships and credit characteristics probabilistically.

-   The exact distribution of business ages must not be predetermined
    and should emerge from the synthetic generation process.

## annual_revenue

**Description:** Estimated annual revenue of a BTYT business customer,
expressed in Uruguayan pesos.

**Data type:**

-   Numeric / Decimal

-   NULL

**Currency:**

-   UYU (normalized reference currency)

**Rules:**

-   Applies only when `customer_type = BUSINESS`.

-   Must be `NULL` when `customer_type = INDIVIDUAL`.

-   Must be greater than or equal to zero.

-   Represents estimated annual business revenue rather than account
    inflows or transaction volume observed by BTYT.

-   Revenue originally generated or reported in another currency must be
    normalized to UYU for analytical comparability.

-   `annual_revenue` should be broadly consistent with `company_size`,
    `business_sector` and other business characteristics while
    preserving substantial variation.

-   `annual_revenue` must not deterministically determine company size,
    product ownership, customer status or credit risk.

**Generation assumptions:**

-   The distribution of `annual_revenue` must be positively skewed
    rather than uniform.

-   `MICRO` and `SMALL` businesses should generally have lower annual
    revenue than `MEDIUM` and `LARGE` businesses.

-   Revenue ranges between company-size categories should overlap
    substantially.

-   Businesses within the same `company_size` may have very different
    revenue levels.

-   `business_sector` may influence typical revenue levels and
    dispersion.

-   High-revenue outliers should exist but represent a small minority of
    business customers.

-   Geographic characteristics may moderately influence revenue
    distributions without determining them.

-   Recently established businesses may have lower expected revenue on
    average, while substantial exceptions must remain possible.

-   Exact revenue distributions and relationships must not be
    predetermined.

-   The final patterns should emerge from the synthetic generation
    process within plausible economic constraints.

## Field applicability summary

### Applies to both `INDIVIDUAL` and `BUSINESS`

-   `customer_id`
-   `customer_type`
-   `document_type`
-   `document_id`
-   `residence_country`
-   `residence_department`
-   `residence_locality`
-   `primary_branch_id`
-   `registration_year`
-   `customer_status`
-   `closing_year`

### Applies only to `INDIVIDUAL`

-   `first_name`
-   `last_name`
-   `nationality`
-   `birth_year`
-   `gender`
-   `employment_status`
-   `monthly_income`

### Applies only to `BUSINESS`

-   `company_name`
-   `business_sector`
-   `company_size`
-   `foundation_year`
-   `annual_revenue`

## Implemented generation sequence

`customer_type`

↓

`birth_year` / `foundation_year`

↓

`nationality` and `gender` for individuals

↓

`first_name` / `last_name` or `company_name`

↓

`residence_country` and current residence geography

↓

employment profile or business profile

↓

`monthly_income` / `annual_revenue`

↓

`document_type` and synthetic `document_id`

↓

`registration_year`

↓

historical residence context at registration

↓

`primary_branch_id`

↓

`customer_status`

↓

`closing_year`

## Dataset generation scope

**Target customer population:**

-   Between 90,000 and 120,000 customers in the final frozen dataset.

**Development mode:**

-   Development runs use a fixed population of 20,000 customers to make validation and iteration faster.
-   Development output is not considered the final frozen population.

**Final mode:**

-   The exact final customer count is not predetermined.
-   A reproducible random process selects the final customer count within the 90,000--120,000 range.
-   The random seed used by the current Python generator is `20260827`.
-   Once the final-mode dataset passes structural and plausibility validation, the generated customer population is frozen as part of the BTYT dataset version.

**Current exported schema:**

-   23 columns.
-   Internal development-audit variables are not exported.
-   Numeric monetary fields are exported as nullable numeric values.
-   `primary_branch_id` is exported as a zero-padded string.

**Validation principle:**

-   Formal validation checks structural integrity, missingness rules, unique identifiers, geography consistency, branch chronology, lifecycle chronology and data types.
-   Development reports additionally inspect cross-distributions such as age versus employment, income versus employment, revenue versus company size, nationality versus geography and current residence versus primary-branch department.
-   Passing formal validation does not by itself guarantee economic plausibility; cross-distribution diagnostics are used before freezing the table.


## Post-Python implementation status

Current exported schema contains 23 columns.
