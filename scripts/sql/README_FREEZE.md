# BTYT SQL Analytics — Freeze Candidate

This folder contains the audited SQL analytics layer for BTYT Part I.

## Included

- `000_sql_cheatsheet.sql` — optional learning/reference file. It contains TEMP-table DDL/DML exercises and is **not** part of the analytical smoke-test sequence.
- `00_structural_context.sql`
- `01_customers.sql`
- `02_products_accounts.sql`
- `03_loans.sql`
- `04_transactions.sql`
- `05_branches.sql`
- `06_campaigns.sql`
- `07_performance.sql`

## Runtime smoke-test order

Run `00` through `07` in numeric order against the final 7-schema PostgreSQL model.

`04_transactions.sql` is intentionally designed for **section-by-section execution** because `banking.transactions` contains ~76.8M rows and several exploratory sections require full-table scans. Do not use Run All there unless you deliberately want every scan.

## Freeze criteria

Freeze the folder only after:

1. every executed query completes without PostgreSQL errors;
2. diagnostics documented as `Expected result: zero rows` return zero rows;
3. accounting-identity residuals are zero or within the stated rounding tolerance;
4. `07_performance.sql` branch-to-bank reconciliation returns `PASS` for every month;
5. any unexpected domain values are reviewed before changing analytical definitions.

## Audit corrections already applied

- removed the accidentally concatenated duplicate version of `01_customers.sql`;
- preserved current-vs-lifetime relationship semantics;
- corrected credit-card branch attribution using linked-account branch with customer-primary-branch fallback;
- corrected loan DPD buckets to the canonical `CURRENT / DPD_1_30 / DPD_31_60 / DPD_61_90 / DPD_90_PLUS` rules;
- separated contractual loan status from monthly delinquency status;
- treated `DEFAULTED` / `RESTRUCTURED` as potentially open at cutoff instead of automatically terminal;
- separated transaction attempts from completed economic movement;
- made transaction financial volume `COMPLETED`-only while keeping failure analytics explicit;
- kept transaction currencies separate unless converted;
- restored merchant-category analysis as an applicable/nullable transaction dimension;
- aligned card and physical-branch attribution with the performance engine;
- clarified monthly performance stock-vs-flow semantics and UYU-equivalent reporting currency;
- made `07_performance.sql` the canonical full branch-to-bank reconciliation;
- strengthened campaign exposure/response semantics and status/date diagnostics;
- removed obsolete schema references and kept the final `core / banking / marketing / reference / market / macro / performance` architecture.

## Status

Static / semantic audit: **completed**.
Runtime PostgreSQL smoke test: **pending on the local BTYT database**.

Once the runtime checks pass, this folder is ready to be tagged/frozen as the final SQL analytics layer for Part I.
