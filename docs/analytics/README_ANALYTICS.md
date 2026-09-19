# BTYT Part I — Analytics Documentation

This folder is the documentation companion to the audited SQL freeze candidate.

## Files

- `00_structural_context.md`
- `01_customers.md`
- `02_products_accounts.md`
- `03_loans.md`
- `04_transactions.md`
- `05_branches.md`
- `06_campaigns.md`
- `07_performance.md`
- `architecture_part_i_analytical_update.md`
- `tooling_strategy.md`

## Current status

The SQL layer has completed its static / semantic audit and is in runtime smoke-test status.

The SQL folder should be frozen only after:

1. `00` through `07` execute without PostgreSQL errors;
2. diagnostics documented as zero-row checks return zero rows;
3. accounting residuals are zero or within the stated tolerance;
4. `07_performance.sql` returns `PASS` for branch-to-bank reconciliation for every month;
5. unexpected domain values are reviewed before definitions are changed.

## Canonical analytical sequence

```text
00 → Structural Context
01 → Customers
02 → Products & Accounts
03 → Loans & Credit Quality
04 → Transactions & Channels
05 → Branch Network & Branch Performance
06 → Campaigns & Marketing Effectiveness
07 → Bank Performance & Executive Management
```

## Cross-file semantic rules

### Master status vs historical state

Fields such as `customer_status`, `account_status`, `card_status`, `loan_status` and branch `status` are master / cutoff attributes unless explicitly documented otherwise.

They must not automatically be interpreted as historical month-level states.

### Stocks vs flows

Snapshot / semi-additive measures should not be summed across months.

Examples:

- active customers;
- active accounts;
- average deposits;
- average loan balance;
- closing balance.

Flow measures can be accumulated across periods.

Examples:

- inflows / outflows;
- transaction counts;
- transaction volume;
- revenue;
- costs;
- credit loss;
- net income.

### Currency

Native UYU and USD amounts remain separate unless an explicit FX conversion is introduced.

The `performance` schema is different: its monetary measures are generated as **UYU-equivalent reporting values** and are designed for aggregation inside that layer.

### Transaction attempts vs economic movement

`FAILED` transactions are operational attempts, not realized money movement.

For financial transaction volume, the canonical rule is:

```text
transaction_status = 'COMPLETED'
```

### Campaign response

`exposure_status` defines customer-level exposure.

`response_status` defines the observed response outcome.

A `POSITIVE` response is not automatically a product conversion.

## Architecture principle

> **Build once at the data layer. Analyze where it makes sense. Visualize where it communicates best. Do not duplicate without purpose.**
