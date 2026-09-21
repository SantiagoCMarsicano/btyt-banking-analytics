# BTYT — PostgreSQL / SQL Process

## Overview

This document describes the SQL and PostgreSQL phase of **BTYT — Banking Analytics Part I**: the transition from the generated synthetic banking world to a validated relational database ready for analytical SQL, BI tools, and downstream applications.

Python remains responsible for generating the synthetic banking world. PostgreSQL is the relational and analytical layer built on top of those generated datasets.

The current relational model contains **23 tables**. Its final logical architecture is organized into **7 schemas**:

- `core`
- `banking`
- `marketing`
- `reference`
- `market`
- `macro`
- `performance`

The new 7-schema architecture replaces the previous 5-schema organization by separating:

- macroeconomic context and external shocks from `market`;
- aggregated bank and branch performance from `market`.

This improves both semantic clarity and documentation without changing the number of tables.

---

## 1. Architecture

```text
Python World Generation
        │
        ▼
Generated CSV / Parquet datasets
        │
        ▼
load_postgresql.py
        │
        ▼
PostgreSQL
        │
        ▼
audit_relational_model.py
        │
        ▼
apply_relational_model.py
        │
        ▼
validate_relational_model.py
        │
        ▼
Validated Relational Model
        │
        ├── SQL analytics
        ├── Power BI
        ├── Tableau
        └── Apache Superset
```

The separation of responsibilities is intentional:

- **Python** generates the synthetic banking and economic world.
- **PostgreSQL** enforces relational structure and integrity.
- **SQL** becomes the primary language for analytical querying.
- **BI tools** consume the validated relational model.

---

## 2. Database scripts

The PostgreSQL pipeline is implemented in:

```text
scripts/database/
├── load_postgresql.py
├── audit_relational_model.py
├── apply_relational_model.py
└── validate_relational_model.py
```

### `load_postgresql.py`

Loads the canonical generated BTYT world into PostgreSQL.

Main responsibilities:

- discover the expected generated datasets;
- support CSV and Parquet sources;
- normalize column names;
- preserve identifier columns;
- load large tables efficiently;
- create and populate the initial PostgreSQL schemas;
- map generated datasets into the relational layer.

### `audit_relational_model.py`

Performs a read-only audit before structural changes are applied.

The audit covers:

- schema and table inventory;
- columns;
- semantic data types;
- type-conversion compatibility;
- primary-key candidates;
- foreign-key compatibility;
- nullability;
- monetary precision;
- categorical domains;
- numerical ranges;
- temporal rules;
- business-rule constraints.

The audit must be updated to validate the new 7-schema architecture before the schema migration is executed.

### `apply_relational_model.py`

Applies the final approved relational model.

The final script supports:

```text
--schemas
--types
--precision
--pk
--fk
--constraints
--inspect
--all
```

The new `--schemas` phase is responsible for the final schema reorganization.

### `validate_relational_model.py`

Performs historical validation after relational changes are applied.

It verifies that foreign keys and CHECK constraints remain compatible with the complete generated historical dataset.

---

## 3. Final schema architecture

The final BTYT architecture contains **7 schemas and 23 tables**.

| Schema | Tables |
|---|---:|
| `core` | 4 |
| `banking` | 5 |
| `marketing` | 3 |
| `reference` | 2 |
| `market` | 5 |
| `macro` | 2 |
| `performance` | 2 |
| **Total** | **23** |

---

## 4. `core`

Central banking entities and structural relationships.

```text
branches
customers
accounts
products
```

### Purpose

`core` contains the main entities around which the rest of the model is organized.

It answers questions such as:

- who is the customer?
- which branch owns the relationship?
- which product is being used?
- which account connects the customer to banking activity?

---

## 5. `banking`

Operational banking activity and customer-level financial positions.

```text
cards
loans
transactions
account_balances
loan_monthly_snapshot
```

### Purpose

`banking` contains data at the operational or contractual level.

Examples of table grain:

```text
transactions
→ one banking transaction

account_balances
→ one account × month

loan_monthly_snapshot
→ one loan × month
```

Although `account_balances` and `loan_monthly_snapshot` are monthly tables, they remain in `banking` because they describe individual banking relationships rather than aggregated performance.

---

## 6. `marketing`

Commercial campaigns, customer targeting, exposure, and response.

```text
campaigns
campaign_customers
campaign_exposures
```

---

## 7. `reference`

Auxiliary dimensions supporting marketing relationships.

```text
campaign_channels
campaign_geography
```

These tables represent many-to-many descriptive dimensions associated with campaigns.

---

## 8. `market`

Competitive banking environment and financial institutions.

```text
banks
bank_financials
bank_market_weights
bank_world_parameters
financial_institutions
```

### Purpose

`market` now has a narrower and clearer meaning:

> the competitive and institutional banking environment surrounding BTYT.

It contains:

- banks;
- financial institutions;
- annual financial information;
- competitive market weights;
- latent/world-level bank parameters.

### Why `bank_financials` remains in `market`

`bank_financials` includes variables such as:

```text
revenue
operating_costs
net_income
total_assets
total_deposits
total_loans
equity
```

These may look like performance variables, but the table represents **banks in the competitive market**, not only BTYT's internal operating performance.

Its grain is:

```text
bank_id × year
```

Therefore it remains part of `market`.

---

## 9. `macro`

Macroeconomic environment and external shocks.

```text
macro_environment
external_shocks
```

### Purpose

These tables represent exogenous conditions affecting the banking world.

They do not describe customers, accounts, transactions, banks as entities, or internal operational performance.

`macro_environment` represents the synthetic macro-financial state by year.

`external_shocks` represents discrete exogenous events with:

- start;
- peak;
- end;
- recovery;
- magnitude;
- persistence;
- regional or sectoral scope.

---

## 10. `performance`

Aggregated BTYT performance.

```text
bank_monthly_performance
branch_monthly_performance
```

### Purpose

`performance` contains aggregated management and profitability indicators.

The distinction from `banking` is based on **grain**, not frequency.

```text
bank_monthly_performance
→ one BTYT bank-level observation × month

branch_monthly_performance
→ one branch × month
```

These tables contain aggregated measures such as:

- active customers;
- active accounts;
- deposits;
- loan balances;
- transaction count;
- transaction volume;
- interest income;
- interest expense;
- fee income;
- operating costs;
- credit loss;
- net income.

They therefore belong to a dedicated performance schema rather than to the operational banking layer.

---

## 11. Schema migration

The final model introduces four physical table moves:

```text
market.macro_environment
→ macro.macro_environment

market.external_shocks
→ macro.external_shocks

market.bank_monthly_performance
→ performance.bank_monthly_performance

market.branch_monthly_performance
→ performance.branch_monthly_performance
```

No table is created or deleted by this migration.

The total remains:

```text
23 tables
```

The final schema distribution becomes:

```text
core          4
banking       5
marketing     3
reference     2
market        5
macro         2
performance   2
----------------
TOTAL        23
```

---

## 12. Schema migration safety

The final `apply_relational_model.py` performs the schema migration with two protections.

### Preflight validation

Before any change is made, the script checks each source and destination table.

It aborts if:

- both the source and target table exist;
- neither the source nor target table exists.

This prevents accidental duplication or missing-table migrations.

### Atomic migration

All required schema changes are applied in a single PostgreSQL transaction.

Therefore:

> either all required table moves succeed, or none of them are committed.

The migration is also idempotent: tables already located in their final schema are skipped.

---

## 13. Running the schema migration

The final application script should be stored as:

```text
scripts/database/apply_relational_model.py
```

### Inspect without changes

```bash
python scripts/database/apply_relational_model.py --inspect
```

### Apply only the schema reorganization

```bash
python scripts/database/apply_relational_model.py --schemas
```

Because the previous relational model has already been applied, the schema reorganization should normally be executed with `--schemas`, not `--all`.

The expected final layout is:

```text
core          4 / 4
banking       5 / 5
marketing     3 / 3
reference     2 / 2
market        5 / 5
macro         2 / 2
performance   2 / 2

Observed BTYT tables: 23 / 23
```

---

## 14. Primary keys

The model maintains **23 primary keys**.

Examples:

```text
core.accounts
PK = account_id

banking.transactions
PK = transaction_id

banking.account_balances
PK = account_id + year_month

banking.loan_monthly_snapshot
PK = loan_id + year_month

performance.branch_monthly_performance
PK = branch_id + year_month

performance.bank_monthly_performance
PK = year_month
```

The schema migration does not change primary-key definitions.

---

## 15. Foreign keys

The relational model maintains **28 foreign keys**.

Important relationships include:

```text
accounts.customer_id
→ customers.customer_id

accounts.product_id
→ products.product_id

accounts.branch_id
→ branches.branch_id

loans.customer_id
→ customers.customer_id

transactions.account_id
→ accounts.account_id

transactions.counterparty_institution_id
→ market.financial_institutions.institution_id
```

The performance schema includes:

```text
performance.branch_monthly_performance.branch_id
→ core.branches.branch_id
```

`performance.bank_monthly_performance` remains a system-level aggregate and does not receive a synthetic `bank_id` foreign key.

---

## 16. Financial institutions and transaction counterparties

BTYT deliberately distinguishes between a **financial institution** and a **bank**.

The transaction path is:

```text
banking.transactions
    counterparty_institution_id
            │
            ▼
market.financial_institutions
    institution_id
            │
            ▼
market.banks
    bank_id
```

This is intentionally preferred over linking transactions directly to `banks.bank_id`.

`financial_institutions` can represent operational counterparties that are not necessarily banks.

---

## 17. Semantic data types

PostgreSQL introduces explicit semantic typing over the generated source data.

Examples include:

```text
year_month → DATE
start_date → DATE
end_date → DATE
exposure_datetime → TIMESTAMP
year fields → INTEGER
```

The new schema architecture changes table locations but does not change the meaning of these data types.

For example:

```text
macro.macro_environment.year
→ INTEGER

macro.external_shocks.start_month
→ DATE

performance.bank_monthly_performance.year_month
→ DATE

performance.branch_monthly_performance.year_month
→ DATE
```

---

## 18. Monetary precision

Financial measures use fixed decimal precision when accounting-style precision is required.

Typical measures use:

```text
NUMERIC(18,2)
```

Large aggregate measures may use:

```text
NUMERIC(20,2)
```

The schema migration preserves all existing data types and constraints attached to the moved tables.

---

## 19. Integrity constraints

The relational layer currently defines:

```text
23 primary keys
28 foreign keys
11 audited NOT NULL rules
27 CHECK constraints
```

The schema reorganization does not change the number or meaning of these constraints.

Foreign keys, primary keys, indexes, and CHECK constraints remain attached to the moved PostgreSQL tables when `ALTER TABLE ... SET SCHEMA` is used.

---

## 20. Historical validation

Before the schema redesign, the previous relational architecture reached:

```text
28 / 28 foreign keys validated
27 / 27 CHECK constraints validated
55 / 55 tracked historical constraints validated
```

After the 7-schema migration, historical validation should be rerun using the updated validation script.

The desired sequence is:

```text
1. Update apply_relational_model.py
2. Update audit_relational_model.py
3. Audit the 7-schema architecture
4. Apply --schemas
5. Update validate_relational_model.py
6. Validate the migrated model
7. Regenerate the final ERD
```

---

## 21. Why the model uses 7 schemas

The previous 5-schema design was technically valid, but `market` had become semantically overloaded.

It combined:

```text
competitive banking entities
+
financial institutions
+
macroeconomic environment
+
external shocks
+
internal BTYT performance
```

The 7-schema design separates those concepts.

```text
CORE
central banking entities

BANKING
operational banking activity

MARKETING
commercial campaigns

REFERENCE
auxiliary campaign dimensions

MARKET
competitive and institutional banking environment

MACRO
exogenous macroeconomic conditions and shocks

PERFORMANCE
aggregated BTYT management and profitability metrics
```

The result is a model that is easier to interpret, query, document, and visualize.

---

## 22. Final relational architecture

```text
                       CORE
            ┌───────────┼───────────┐
            │           │           │
       MARKETING     BANKING      REFERENCE
                        │
                        │
                  PERFORMANCE

            MARKET ─────────── MACRO
```

This drawing is conceptual rather than a literal foreign-key map.

The definitive ERD must still represent all **28 actual foreign-key relationships** exactly.

---

## 23. Current status

At this point:

```text
[PASS] Final 7-schema architecture defined
[PASS] 23-table distribution defined
[PASS] apply_relational_model.py updated
[PASS] Schema migration made atomic
[PASS] Schema migration made idempotent
[PASS] 23 primary-key definitions retained
[PASS] 28 foreign-key definitions retained
[PASS] 11 NOT NULL rules retained
[PASS] 27 CHECK constraints retained

[PENDING] Update audit_relational_model.py
[PENDING] Audit new 7-schema architecture
[PENDING] Execute --schemas
[PENDING] Update validation script
[PENDING] Revalidate historical constraints
[PENDING] Regenerate final ERD
```

---

## 24. Next step

The next required step is **not** to redesign the ERD.

The next step is:

```text
update audit_relational_model.py
        ↓
audit 7-schema architecture
        ↓
apply schema migration
        ↓
validate
        ↓
generate final ERD
```

This keeps the visual documentation aligned with the actual PostgreSQL model rather than designing the diagram before the database architecture is finalized.
