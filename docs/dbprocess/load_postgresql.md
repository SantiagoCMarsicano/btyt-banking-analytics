# load_postgresql.py

## Purpose

`load_postgresql.py` loads the canonical generated BTYT world into PostgreSQL.

Its responsibility is limited to the **physical ingestion phase**:

```text
generated CSV / Parquet files
        │
        ▼
load_postgresql.py
        │
        ▼
PostgreSQL tables
```

The loader does **not** apply the final relational model.

It does not create:

- primary keys;
- foreign keys;
- CHECK constraints;
- audited `NOT NULL` rules;
- final semantic type conversions;
- final monetary precision;
- indexes.

Those steps belong to:

```text
audit_relational_model.py
apply_relational_model.py
validate_relational_model.py
```

---

## Important architectural note

The loader intentionally uses the **initial ingestion architecture**, not the final 7-schema analytical architecture.

At ingestion time, the tables are loaded into:

```text
core
banking
marketing
market
reference
```

After loading and auditing, `apply_relational_model.py` reorganizes four tables:

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

Therefore the complete architecture evolves as:

```text
GENERATED FILES
      │
      ▼
5-schema ingestion layout
      │
      ▼
audit
      │
      ▼
apply schema reorganization
      │
      ▼
7-schema final relational layout
```

This is intentional.

The loader remains focused on reproducible ingestion, while `apply_relational_model.py` owns the final logical PostgreSQL architecture.

---

# 1. Source data location

The loader expects the canonical generated BTYT world under:

```text
worlds/
└── BTYT/
    └── 01/
        └── data/
            └── generated/
```

The path is resolved from the repository root:

```python
REPO_ROOT = Path(__file__).resolve().parents[2]

DATA_ROOT = (
    REPO_ROOT
    / "worlds"
    / "BTYT"
    / "01"
    / "data"
    / "generated"
)
```

The script should therefore be executed from the BTYT repository environment.

---

# 2. Supported source formats

The loader supports:

```text
.csv
.parquet
```

If both formats exist for the same logical table, the loader prefers:

```text
Parquet
```

This avoids loading duplicate physical representations of the same dataset.

---

# 3. Dataset discovery

The loader recursively searches the generated-data directory.

Each file is interpreted as a logical dataset according to its filename stem.

Example:

```text
customers.parquet
→ customers

transactions.parquet
→ transactions
```

The loader validates the discovered datasets against the expected BTYT table set.

It aborts if:

```text
an unexpected dataset has no schema mapping
```

or if:

```text
an expected BTYT dataset is missing
```

This prevents accidental partial or ambiguous database loads.

---

# 4. Initial PostgreSQL schema mapping

The ingestion layer maps all 23 generated datasets into five schemas.

## `core`

```text
branches
customers
accounts
products
```

## `banking`

```text
cards
loans
transactions
account_balances
loan_monthly_snapshot
```

## `marketing`

```text
campaigns
campaign_customers
campaign_exposures
```

## `market`

Initial ingestion includes:

```text
banks
bank_financials
bank_market_weights
bank_monthly_performance
bank_world_parameters
branch_monthly_performance
financial_institutions
macro_environment
external_shocks
```

At this stage `market` temporarily contains 9 tables.

Four of them are moved later by `apply_relational_model.py`.

## `reference`

```text
campaign_channels
campaign_geography
```

The ingestion total is:

```text
23 tables
```

---

# 5. Final architecture after apply

After the schema reorganization, the final PostgreSQL model becomes:

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

The loader therefore represents the **ingestion layer**, while the final analytical model contains 7 schemas.

---

# 6. PostgreSQL connection

The loader supports environment variables for connection configuration.

Defaults:

```text
host     = localhost
port     = 5432
database = BTYT
user     = postgres
```

Supported variables:

```text
BTYT_DB_HOST
BTYT_DB_PORT
BTYT_DB_NAME
BTYT_DB_USER
BTYT_DB_PASSWORD
```

If `BTYT_DB_PASSWORD` is not defined, the script requests the password interactively.

Example:

```text
PostgreSQL password for user 'postgres':
```

---

# 7. Column normalization

Before insertion, all source column names are normalized to lowercase `snake_case`.

The normalization process:

1. converts names to strings;
2. trims whitespace;
3. converts to lowercase;
4. replaces non-alphanumeric characters with `_`;
5. collapses repeated underscores;
6. removes leading and trailing underscores.

This produces stable SQL-compatible identifiers.

---

# 8. Identifier preservation

Identifier columns are treated carefully when reading CSV files.

Columns matching:

```text
id
*_id
```

are read as strings.

This helps preserve identifiers such as:

```text
customer_id
account_id
transaction_id
bank_id
branch_id
```

without accidental numeric coercion.

---

# 9. Batch loading

Large files are not loaded into memory at once.

The loader uses:

```text
CSV_CHUNK_SIZE       = 50,000
PARQUET_BATCH_SIZE   = 100,000
SQL_CHUNK_SIZE       = 1,000
```

### CSV

CSV files are read with:

```text
50,000 rows per chunk
```

### Parquet

Parquet files are read with:

```text
100,000 rows per batch
```

### PostgreSQL insertion

DataFrames are sent to PostgreSQL using smaller SQL insertion chunks.

This is especially important for very large BTYT tables such as:

```text
banking.transactions
```

---

# 10. Source row counts

Before loading a dataset, the script determines the expected number of rows.

For Parquet:

```text
row count is obtained from Parquet metadata
```

For CSV:

```text
the file is counted incrementally in chunks
```

The expected source count is then compared with the final PostgreSQL table count.

---

# 11. Existing-table behavior

The loader is designed to be safely rerunnable at the ingestion stage.

For each table:

## Existing table with correct row count

If PostgreSQL already contains exactly the same number of rows as the source:

```text
[SKIP]
```

The table is not reloaded.

Example:

```text
[SKIP] core.customers:
already contains 107,000 rows
```

## Existing table with an incomplete row count

If the table exists but its row count differs from the source:

```text
[RESET]
```

The loader truncates the table before loading it again.

Example:

```text
[RESET] banking.transactions:
database has X rows,
source has Y rows
```

This behavior is designed for interrupted or incomplete ingestion.

---

# 12. Row-count validation

After every dataset is loaded, the loader compares:

```text
source row count
vs
PostgreSQL row count
```

If they differ, the script raises an error.

A successful load reports:

```text
[ OK ] schema.table: N rows
```

This ensures that PostgreSQL contains the complete physical dataset before relational constraints are applied.

---

# 13. Large-table progress reporting

For datasets containing at least one million rows, the loader prints incremental progress.

Example:

```text
banking.transactions:
10,000,000 / 76,799,360 rows

banking.transactions:
20,000,000 / 76,799,360 rows
```

This is particularly useful for the canonical BTYT transaction table.

---

# 14. Execution

From the repository root:

```bash
python scripts/database/load_postgresql.py
```

The loader:

```text
1. Locates the generated world
2. Discovers all datasets
3. Verifies the expected table set
4. Connects to PostgreSQL
5. Creates required ingestion schemas
6. Loads each dataset
7. Validates row counts
8. Prints a load summary
```

---

# 15. Load summary

At the end of execution, the loader reports:

```text
Loaded : N
Skipped: N
Failed : N
```

A clean load finishes with:

```text
All BTYT datasets are loaded and row-count validated.
```

If any table fails:

```text
Some datasets failed.
Review the errors before adding constraints.
```

No relational-model application should proceed until the load finishes cleanly.

---

# 16. Relationship with the relational-model pipeline

The complete PostgreSQL process is:

```text
load_postgresql.py
        │
        ▼
physical PostgreSQL ingestion
        │
        ▼
audit_relational_model.py
        │
        ▼
relational and semantic audit
        │
        ▼
apply_relational_model.py
        │
        ├── schema reorganization
        ├── semantic types
        ├── financial precision
        ├── primary keys
        ├── foreign keys
        ├── NOT NULL rules
        └── CHECK constraints
        │
        ▼
validate_relational_model.py
        │
        ▼
historically validated final model
```

---

# 17. Why the loader still uses 5 schemas

The final BTYT database contains 7 schemas, but the loader deliberately remains based on the original 5-schema ingestion layout.

This separation has several advantages.

### Generated data remains independent of database redesign

The physical datasets do not need to change when PostgreSQL logical organization evolves.

### Loading remains simple

Every generated file has one stable initial destination.

### Final architecture remains explicit

The transition from:

```text
5 ingestion schemas
```

to:

```text
7 final analytical schemas
```

is documented and controlled by `apply_relational_model.py`.

### Reproducibility improves

A fresh BTYT database can always be reconstructed using the same sequence:

```text
load
→ audit
→ apply
→ validate
```

rather than embedding relational redesign logic inside the ingestion script.

---

# 18. Final schema transition

The only schema-location changes after ingestion are:

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

All other tables remain in their original ingestion schema.

---

# 19. What the loader does not validate

The loader verifies physical completeness through row counts.

It does **not** determine whether:

```text
customer_id values are unique
foreign keys are valid
dates use the best PostgreSQL semantic type
monetary precision is correct
business rules hold
CHECK constraints are valid
```

Those concerns deliberately belong to later stages.

This preserves a clean distinction between:

```text
physical ingestion
```

and:

```text
relational validation
```

---

# 20. Safety considerations

## Schema creation

Schemas are created only when missing:

```sql
CREATE SCHEMA IF NOT EXISTS ...
```

## Existing complete tables

Complete tables are skipped.

## Incomplete tables

Tables with mismatched row counts are truncated and reloaded.

## Source validation

Unexpected or missing datasets abort dataset discovery.

## Post-load validation

Every loaded table must match its source row count.

---

# 21. Current role in BTYT

`load_postgresql.py` is the entry point of the SQL/PostgreSQL layer.

Its contract is:

> Load the complete canonical generated BTYT world into PostgreSQL without imposing the final relational semantics.

Once loading succeeds, responsibility passes to:

```text
audit_relational_model.py
```

The final BTYT analytical database is only considered complete after:

```text
load
+
audit
+
apply
+
validate
```

all succeed.

---

# 22. SQLProcess documentation set

The complete PostgreSQL process is documented through:

```text
docs/
└── SQLProcess/
    ├── load_postgresql.md
    ├── audit_relational_model.md
    ├── apply_relational_model.md
    └── validate_relational_model.md
```

Together these documents describe the full lifecycle from generated synthetic files to the final validated 7-schema PostgreSQL model.
