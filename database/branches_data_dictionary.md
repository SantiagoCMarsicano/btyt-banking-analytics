## branch_type

**Description:** Type of physical banking office.

**Allowed values:**
- BRANCH
- AGENCY

**Rules:**
- A BRANCH may supervise one or more agencies.
- An AGENCY must have a valid parent_branch_id.
- A BRANCH has parent_branch_id = NULL.

## branch_size

**Description:** Operational capacity of the banking office.

**Allowed values:**
- SMALL
- MEDIUM
- LARGE

**Rules:**
- Represents installed operational capacity, not financial performance.
- Classification considers infrastructure, service capacity and operational scope.
- Branch size does not change automatically because of changes in customers, loans or profitability.

## status

**Description:** Current operating status of the banking office.

**Allowed values:**
- OPEN
- CLOSED

**Rules:**
- OPEN indicates that the office is currently operating.
- CLOSED indicates that the office has permanently ceased operations.
- Temporary disruptions are not represented here; they belong to operational incident records.
- A CLOSED office must have a closing_date.
- An OPEN office must have closing_date = NULL.

## opening_reason

**Description:** Strategic reason that motivated BTYT to open the banking office.

**Allowed values:**
- FOUNDING
- LOCAL_EXPANSION
- REGIONAL_EXPANSION
- BORDER_EXPANSION
- NATIONAL_EXPANSION
- METROPOLITAN_EXPANSION

**Rules:**

- FOUNDING: original BTYT office established in 1969.
- LOCAL_EXPANSION: early expansion within the department of Treinta y Tres.
- REGIONAL_EXPANSION: expansion from Treinta y Tres into BTYT's historical East/Northeast regional market.
- BORDER_EXPANSION: office opened primarily because of the strategic importance of a border locality.
- NATIONAL_EXPANSION: expansion associated with BTYT's transition from a regional to a nationwide bank.
- METROPOLITAN_EXPANSION: expansion into Montevideo and the metropolitan market.

POOR_PERFORMANCE
NETWORK_OPTIMIZATION
BRANCH_CONSOLIDATION
DIGITAL_TRANSFORMATION
STRATEGIC_REALIGNMENT

## closure_reason

**Description:** Primary reason for the permanent closure of a BTYT banking office.

**Allowed values:**
- POOR_PERFORMANCE
- NETWORK_OPTIMIZATION
- DIGITAL_TRANSFORMATION
- STRATEGIC_REALIGNMENT

**Rules:**

- POOR_PERFORMANCE: closure due primarily to persistently insufficient business or financial performance.
- NETWORK_OPTIMIZATION: closure because the office is no longer considered necessary within BTYT's physical network.
- DIGITAL_TRANSFORMATION: closure associated primarily with migration toward digital banking channels.
- STRATEGIC_REALIGNMENT: closure resulting from a change in BTYT's territorial or commercial strategy.
- Must be NULL when status = OPEN.
- Must contain a valid reason when status = CLOSED.

## region

**Description:** Internal commercial and administrative region of BTYT to which the banking office belongs.

**Allowed values:**
- EAST
- NORTH
- LITTORAL
- CENTRAL
- METROPOLITAN

**Department allocation:**

- EAST: Treinta y Tres, Cerro Largo, Rocha, Maldonado, Lavalleja
- NORTH: Artigas, Rivera, Salto
- LITTORAL: Paysandú, Río Negro, Soriano, Colonia
- CENTRAL: Tacuarembó, Durazno, Flores, Florida
- METROPOLITAN: Montevideo, Canelones, San José

**Rules:**
- Every banking office must belong to exactly one region.
- Region is determined by department.
- Regions represent BTYT's internal territorial organization and do not necessarily correspond to an official geographic classification of Uruguay.

## branch_id

**Description:** Unique and permanent identifier assigned to each BTYT banking office.

**Format:**
- 001
- 002
- 003
- ...

**Rules:**
- Must be unique.
- Must never be reused.
- Assigned sequentially according to historical opening order.
- Does not encode branch type, location, region or status.
- Remains unchanged throughout the lifetime of the office.

## branch_name

**Description:** Name used to identify each BTYT banking office.

**Allowed values:**

### EAST
**Treinta y Tres**
- Treinta y Tres
- Vergara
- Santa Clara de Olimar
- Cerro Chato
- La Charqueada

**Cerro Largo**
- Melo
- Río Branco
- Aceguá

**Rocha**
- Rocha
- Chuy
- La Paloma

**Maldonado**
- Maldonado
- Punta del Este
- Piriápolis

**Lavalleja**
- Minas
- José Pedro Varela

### NORTH
**Artigas**
- Artigas

**Rivera**
- Rivera

**Salto**
- Salto

### LITTORAL
**Paysandú**
- Paysandú

**Río Negro**
- Fray Bentos

**Soriano**
- Mercedes

**Colonia**
- Colonia del Sacramento

### CENTRAL
**Tacuarembó**
- Tacuarembó

**Durazno**
- Durazno

**Flores**
- Trinidad

**Florida**
- Florida

### METROPOLITAN
**San José**
- San José de Mayo

**Canelones**
- Canelones
- Las Piedras
- Pando
- Ciudad de la Costa

**Montevideo**
- Montevideo Centro
- WTC
- Carrasco
- Prado
- Colón

**Rules:**
- Must identify the banking office unambiguously.
- Does not include the office type (`Sucursal` / `Agencia`).
- Office type is stored separately in `branch_type`.
- Presentation labels such as "Sucursal Melo" or "Agencia Río Branco" may be generated in the BI layer when required.
- Names should remain stable unless the office is formally renamed.
- A departmental capital does not necessarily imply `branch_type = BRANCH`.
- A non-capital locality may have `branch_type = BRANCH` when justified by BTYT's historical or strategic development.

## branch_type

**Description:** Type of physical BTYT banking office according to its operational and administrative role.

**Allowed values:**
- BRANCH
- AGENCY

### BRANCH

A branch is a banking office with broader operational capacity and may supervise one or more agencies.

**Offices classified as BRANCH:**
- Treinta y Tres
- Melo
- Rocha
- Maldonado
- Minas
- José Pedro Varela
- Artigas
- Rivera
- Salto
- Paysandú
- Fray Bentos
- Mercedes
- Colonia del Sacramento
- Tacuarembó
- Durazno
- Florida
- San José de Mayo
- Canelones
- Montevideo Centro

### AGENCY

An agency is a smaller banking office administratively dependent on a branch.

**Offices classified as AGENCY:**
- Vergara
- Santa Clara de Olimar
- Cerro Chato
- La Charqueada
- Río Branco
- Aceguá
- Chuy
- La Paloma
- Punta del Este
- Piriápolis
- Trinidad
- Las Piedras
- Pando
- Ciudad de la Costa
- WTC
- Carrasco
- Prado
- Colón

**Rules:**
- Every banking office must be classified as either BRANCH or AGENCY.
- A BRANCH may supervise one or more agencies.
- An AGENCY must be associated with a valid `parent_branch_id`.
- A BRANCH must have `parent_branch_id = NULL`.
- Being located in a departmental capital does not automatically imply BRANCH status.
- Being located outside a departmental capital does not automatically imply AGENCY status.

## branch_id

**Description:** Unique and permanent identifier assigned to each BTYT banking office.

**Format:**
- 001
- 002
- 003
- ...

**Rules:**
- Must be unique.
- Must never be reused.
- Stored as a string to preserve leading zeros.
- Assigned sequentially according to historical opening order.
- Does not encode branch type, department, region or status.
- Remains unchanged throughout the lifetime of the office.
- A closed office retains its original `branch_id`.

## branch_id

**Description:** Unique and permanent identifier assigned to each BTYT banking office.

**Format:**
- 001
- 002
- 003
- ...
- 037

**Rules:**
- Must be unique.
- Must never be reused.
- Stored as a string to preserve leading zeros.
- Assigned sequentially according to historical opening order.
- Does not encode branch type, department, region or status.
- Remains unchanged throughout the lifetime of the office.
- A closed office retains its original `branch_id`.
- When multiple offices are opened within the same period, their IDs preserve the established historical opening sequence.

**Branch ID allocation:**

| branch_id | branch_name |
|-----------|-------------|
| 001 | Treinta y Tres |
| 002 | Vergara |
| 003 | José Pedro Varela |
| 004 | La Charqueada |
| 005 | Melo |
| 006 | Cerro Chato |
| 007 | Santa Clara de Olimar |
| 008 | Rocha |
| 009 | Chuy |
| 010 | Río Branco |
| 011 | Aceguá |
| 012 | Minas |
| 013 | Maldonado |
| 014 | Piriápolis |
| 015 | Punta del Este |
| 016 | La Paloma |
| 017 | Montevideo Centro |
| 018 | Pando |
| 019 | WTC |
| 020 | Canelones |
| 021 | Durazno |
| 022 | Rivera |
| 023 | Las Piedras |
| 024 | Tacuarembó |
| 025 | Prado |
| 026 | Carrasco |
| 027 | Colonia del Sacramento |
| 028 | Ciudad de la Costa |
| 029 | Florida |
| 030 | San José de Mayo |
| 031 | Mercedes |
| 032 | Salto |
| 033 | Trinidad |
| 034 | Paysandú |
| 035 | Fray Bentos |
| 036 | Artigas |
| 037 | Colón |

## parent_branch_id

**Description:** Unique identifier of the BTYT branch responsible for the administrative supervision of an agency.

**Format:**
- Three-character string corresponding to a valid `branch_id`.
- `NULL` for offices classified as BRANCH.

**Rules:**
- Must be `NULL` when `branch_type = BRANCH`.
- Must contain a valid `branch_id` when `branch_type = AGENCY`.
- The referenced office must have `branch_type = BRANCH`.
- An agency cannot reference itself.
- Administrative dependencies may cross departmental boundaries.
- The relationship represents administrative supervision and does not necessarily imply that both offices are located in the same department.

**Agency–Branch relationships:**

| Agency ID | Agency | parent_branch_id | Parent Branch |
|-----------|--------|------------------|---------------|
| 002 | Vergara | 001 | Treinta y Tres |
| 004 | La Charqueada | 001 | Treinta y Tres |
| 006 | Cerro Chato | 001 | Treinta y Tres |
| 007 | Santa Clara de Olimar | 001 | Treinta y Tres |
| 009 | Chuy | 008 | Rocha |
| 010 | Río Branco | 005 | Melo |
| 011 | Aceguá | 005 | Melo |
| 014 | Piriápolis | 013 | Maldonado |
| 015 | Punta del Este | 013 | Maldonado |
| 016 | La Paloma | 008 | Rocha |
| 018 | Pando | 017 | Montevideo Centro |
| 019 | WTC | 017 | Montevideo Centro |
| 023 | Las Piedras | 020 | Canelones |
| 025 | Prado | 017 | Montevideo Centro |
| 026 | Carrasco | 017 | Montevideo Centro |
| 028 | Ciudad de la Costa 017 | Montevideo Centro |
| 033 | Trinidad | 021 | Durazno |
| 037 | Colón | 017 | Montevideo Centro |

**BRANCH offices:**
All offices classified as `BRANCH` have `parent_branch_id = NULL`.

