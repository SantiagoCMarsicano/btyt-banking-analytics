# BTYT PostgreSQL Data Loader

## 1. Purpose

`load_postgresql.py` loads the canonical BTYT generated world into PostgreSQL.

The loader is responsible for **data ingestion only**. It does not define the final relational model, primary keys, foreign keys, indexes, or analytical views. Those are added in the SQL modeling stage after ingestion and validation.

Script location:

```text
scripts/database/load_postgresql.py
```

Generated data root:

```text
worlds/BTYT/01/data/generated/
```

Target database:

```text
BTYT
```

---

## 2. Core design decision

The physical folder structure under `data/generated` does **not** define the PostgreSQL schema architecture.

BTYT uses five functional PostgreSQL schemas:

| Schema | Purpose |
|---|---|
| `core` | Fundamental banking entities |
| `banking` | Banking operations and financial products in use |
| `marketing` | Campaigns and commercial response |
| `market` | Competitive, financial, macroeconomic, and external environment |
| `reference` | Reference and auxiliary dimensions |

This separation is intentional:

```text
physical generation folder != logical PostgreSQL schema
```

The loader therefore uses an explicit table-to-schema mapping instead of inferring schemas from directory names.

---

## 3. Final PostgreSQL architecture

### `core`

Fundamental entities of the bank.

```text
core.branches
core.customers
core.accounts
core.products
```

### `banking`

Operational banking activity.

```text
banking.cards
banking.loans
banking.transactions
banking.account_balances
banking.loan_monthly_snapshot
```

### `marketing`

Campaign definition, targeting, and exposure.

```text
marketing.campaigns
marketing.campaign_customers
marketing.campaign_exposures
```

### `market`

Competitive environment, bank performance, macroeconomic conditions, and external shocks.

```text
market.banks
market.bank_financials
market.bank_market_weights
market.bank_monthly_performance
market.bank_world_parameters
market.branch_monthly_performance
market.financial_institutions
market.macro_environment
market.external_shocks
```

### `reference`

Reference and auxiliary dimensions.

```text
reference.campaign_channels
reference.campaign_geography
```

Total logical datasets:

```text
23
```

---

## 4. Explicit schema mapping

The loader contains a fixed `TABLE_SCHEMA_MAP`.

Example:

```python
TABLE_SCHEMA_MAP = {
    "branches": "core",
    "customers": "core",
    "accounts": "core",
    "products": "core",

    "cards": "banking",
    "loans": "banking",
    "transactions": "banking",
    "account_balances": "banking",
    "loan_monthly_snapshot": "banking",

    "campaigns": "marketing",
    "campaign_customers": "marketing",
    "campaign_exposures": "marketing",

    "banks": "market",
    "bank_financials": "market",
    "bank_market_weights": "market",
    "bank_monthly_performance": "market",
    "bank_world_parameters": "market",
    "branch_monthly_performance": "market",
    "financial_institutions": "market",
    "macro_environment": "market",
    "external_shocks": "market",

    "campaign_channels": "reference",
    "campaign_geography": "reference",
}
```

This mapping is the source of truth for PostgreSQL placement.

---

## 5. Source discovery

The loader recursively scans:

```text
worlds/BTYT/01/data/generated/
```

Supported formats:

```text
.csv
.parquet
```

When both CSV and Parquet exist for the same logical dataset, Parquet is preferred.

Example:

```text
accounts.csv
accounts.parquet
```

Selected source:

```text
accounts.parquet
```

The physical source path does not affect the target PostgreSQL schema.

For example:

```text
generated/credit/loan_monthly_snapshot.parquet
```

is loaded into:

```text
banking.loan_monthly_snapshot
```

Similarly:

```text
generated/campaigns/campaign_channels.csv
```

is loaded into:

```text
reference.campaign_channels
```

---

## 6. Dataset validation during discovery

The script expects the canonical set of 23 BTYT datasets.

If a generated dataset exists without a mapping, execution stops.

If an expected dataset is missing, execution also stops.

This prevents accidental silent ingestion into an incorrect schema.

---

## 7. PostgreSQL connection

Default configuration:

```text
Host: localhost
Port: 5432
Database: BTYT
User: postgres
```

Optional environment variables:

```text
BTYT_DB_HOST
BTYT_DB_PORT
BTYT_DB_NAME
BTYT_DB_USER
BTYT_DB_PASSWORD
```

If `BTYT_DB_PASSWORD` is not defined, the loader requests the password interactively.

Run from the repository root:

```powershell
python scripts/database/load_postgresql.py
```

The password is never stored directly in the script and should never be committed to Git.

---

## 8. Connection URL safety

The loader uses SQLAlchemy `URL.create(...)` instead of manually concatenating the database connection string.

This avoids connection problems when the PostgreSQL password contains characters with special meaning in URLs.

---

## 9. Column normalization

Column names are normalized before insertion:

- lowercase;
- spaces and punctuation converted to underscores;
- repeated underscores collapsed.

Example:

```text
Customer ID
```

becomes:

```text
customer_id
```

This avoids quoted PostgreSQL identifiers and keeps SQL naming consistent across BTYT.

---

## 10. Identifier preservation

For CSV sources, columns named `id` or ending in `_id` are read as strings.

This preserves identifiers with leading zeros.

Example:

```text
001
```

must remain:

```text
001
```

and must not be converted to:

```text
1
```

This is particularly important for fields such as `branch_id`.

---

## 11. Large-file strategy

The loader does not load large Parquet files entirely into memory.

Configuration:

```text
CSV chunk size:      50,000 rows
Parquet batch size: 100,000 rows
SQL chunk size:       1,000 rows
```

Large Parquet datasets are read incrementally with PyArrow.

This is relevant for tables such as:

```text
banking.account_balances
banking.loan_monthly_snapshot
banking.transactions
```

---

## 12. Transactions issue and correction

An earlier loader used:

```python
method="multi"
```

with SQL chunks of 5,000 rows.

The transactions dataset contains 14 columns, which produced SQL statements containing approximately:

```text
5,000 rows x 14 columns = ~70,000 bound parameters
```

That generated an unnecessarily large multi-row `INSERT` statement and caused the transaction load to fail.

The corrected loader removes `method="multi"` and uses smaller SQL chunks:

```python
frame.to_sql(
    table_name,
    engine,
    schema=schema_name,
    if_exists="append",
    index=False,
    chunksize=1000,
)
```

This avoids generating one massive SQL statement.

---

## 13. Row-count aware restart logic

The original loader used this rule:

```text
table contains rows -> skip
```

That was insufficient because an interrupted table could contain only part of the source dataset.

Example encountered during development:

```text
banking.transactions
PostgreSQL rows: 300,000
Source rows:     much larger
```

The corrected loader compares the PostgreSQL row count with the source row count.

### Complete table

```text
PostgreSQL rows == source rows
```

Result:

```text
SKIP
```

### Empty table

```text
PostgreSQL rows == 0
```

Result:

```text
LOAD
```

### Partial or inconsistent table

```text
PostgreSQL rows != source rows
```

Result:

```text
RESET
TRUNCATE TABLE
RELOAD FROM SOURCE
```

This makes repeated execution safer and prevents partial loads from being mistaken for complete tables.

---

## 14. Source row counts

Parquet row counts are obtained from Parquet metadata without loading the full dataset.

CSV datasets are counted in chunks.

Each table is validated again after insertion.

If:

```text
PostgreSQL row count != source row count
```

the dataset is reported as failed.

---

## 15. Loading workflow

For each dataset:

```text
Discover source
      ↓
Resolve logical table name
      ↓
Resolve PostgreSQL schema from TABLE_SCHEMA_MAP
      ↓
Count source rows
      ↓
Create schema if necessary
      ↓
Inspect target table
      ↓
Compare PostgreSQL rows with source rows
      ↓
SKIP / RESET / LOAD
      ↓
Read source in batches
      ↓
Normalize columns
      ↓
Insert into PostgreSQL
      ↓
Validate final row count
```

---

## 16. Schema creation

The loader creates only the five logical BTYT schemas when required:

```text
core
banking
marketing
market
reference
```

The generated-data folder names are not PostgreSQL schema names.

Therefore folders such as:

```text
campaigns
credit
performance
transactions
world
```

must not automatically become PostgreSQL schemas.

---

## 17. Separation of responsibilities

BTYT separates three technical stages.

### Data generation

Python creates the synthetic banking world.

```text
Python generators
      ↓
CSV / Parquet
```

### Data ingestion

The loader moves canonical generated data into the logical PostgreSQL architecture.

```text
CSV / Parquet
      ↓
load_postgresql.py
      ↓
PostgreSQL
```

### Relational modeling

SQL adds database semantics after ingestion.

```text
Loaded PostgreSQL tables
      ↓
PK / FK / CHECK / UNIQUE / INDEX
      ↓
Relational banking model
```

The filesystem is therefore a generation concern, while PostgreSQL schemas are a data-modeling concern.

---

## 18. What the loader does not yet do

The ingestion script intentionally does not define:

```text
Primary keys
Foreign keys
CHECK constraints
UNIQUE constraints
Indexes
Analytical views
Materialized views
```

These belong to the next SQL modeling stage.

Some SQL column types are initially inferred through Pandas and SQLAlchemy and should be reviewed before final relational constraints are added.

---

## 19. Recommended clean rebuild procedure

When rebuilding BTYT from the incorrect schema architecture, remove the previously created schemas and reload from the canonical generated files.

The previous development loader may have created:

```text
core
campaigns
credit
performance
transactions
world
```

For a complete clean rebuild, remove those BTYT schemas before running the corrected loader.

After cleanup, the intended database architecture must contain only:

```text
core
banking
marketing
market
reference
```

for BTYT application data.

---

## 20. Post-load validation

After a successful load, verify the tables by schema.

```sql
SELECT
    table_schema,
    table_name
FROM information_schema.tables
WHERE table_schema IN (
    'core',
    'banking',
    'marketing',
    'market',
    'reference'
)
ORDER BY table_schema, table_name;
```

Expected distribution:

```text
core       4 tables
banking    5 tables
marketing  3 tables
market      9 tables
reference   2 tables
--------------------
TOTAL      23 tables
```

---

## 21. Next stage

Once all 23 datasets are successfully loaded and row-count validated:

1. Review inferred PostgreSQL data types.
2. Define primary keys.
3. Define foreign keys.
4. Validate referential integrity.
5. Add `CHECK` and `UNIQUE` constraints where appropriate.
6. Create indexes for analytical and relational access patterns.
7. Audit duplicates, missing identifiers, and orphan records.
8. Document the relational model.
9. Begin analytical SQL queries.
10. Connect PostgreSQL to Power BI, Tableau, and Apache Superset.

At that point BTYT moves from the synthetic-world generation phase into the relational modeling and analytics phase.
