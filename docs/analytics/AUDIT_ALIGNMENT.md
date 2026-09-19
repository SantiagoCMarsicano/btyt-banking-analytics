# Analytics Documentation — Audit Alignment Notes

This update aligns the Markdown documentation with the audited `BTYT_SQL_FREEZE_CANDIDATE`.

## Main corrections

- Added the missing `02_products_accounts.md`.
- Expanded `01_customers.md` around current-vs-lifetime relationships and the one-row-per-customer bases.
- Documented loan contractual status as a cutoff attribute and monthly delinquency as the historical risk state.
- Standardized DPD buckets to `CURRENT / DPD_1_30 / DPD_31_60 / DPD_61_90 / DPD_90_PLUS`.
- Documented that `DEFAULTED` / `RESTRUCTURED` loans may still be open when `closing_year IS NULL`.
- Separated transaction attempts from completed economic movement.
- Defined financial transaction volume as `COMPLETED` only.
- Documented the audited channel grouping and physical-branch transaction rule.
- Clarified native currency versus UYU-equivalent performance reporting.
- Documented credit-card branch fallback through customer primary branch.
- Clarified monthly performance-engine meanings of active customers/accounts.
- Made `07_performance.sql` the canonical full branch-to-bank reconciliation.
- Made campaign exposure and response statuses canonical, with dates treated as timing metadata.
- Removed the implication that positive campaign response equals product conversion.
- Updated tooling strategy to reflect the SQL freeze stage and anti-duplication architecture.

## Status

Documentation alignment: **complete**

Runtime SQL validation: **pending / in progress on local PostgreSQL**

Once runtime checks pass, the SQL and Markdown analytical layers can be frozen together.
