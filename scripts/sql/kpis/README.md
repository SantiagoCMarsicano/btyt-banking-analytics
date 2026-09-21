# BTYT Part I — KPI SQL Freeze

This folder is the frozen SQL KPI layer for BTYT Part I.

## Classification rule

- **Tier** is priority for the portfolio and decision story, not query order.
- **Tool** is the primary downstream delivery home; PostgreSQL remains the shared calculation layer.
- Tool allocation follows the project strategy: Power BI = corporate BI, Excel = management/ad hoc, Tableau = geography/storytelling, Superset = operational SQL-first monitoring, Python = statistical/transition analysis.
- KPI comments are placed next to the calculation. The consolidated map is kept here and at the end of each SQL file, rather than crowding file headers.

## Final tier board

### Tier S — 10 KPI

**Power BI:** **01** Active Customers, **02** Average Deposits, **03** Average Loan Balance, **04** Total Revenue, **05** Cost-to-Income, **06** Credit Loss Ratio, **07** 30+ DPD Exposure Rate, **08** Net Income, **09** Net Margin, **12** Loan-to-Deposit Operating Ratio.

### Tier A — 12 KPI

**Power BI:** **10** YoY Revenue Growth, **11** YoY Net Income Change, **16** New Customers, **17** Net Customer Growth, **25** Deposit Growth YoY, **28** Loan Origination Amount, **29** 90+ DPD Exposure Rate, **37** Branch Net Income, **38** Branch Cost-to-Income, **48** Pre-Provision Margin, **52** Operating Leverage.

**Python:** **32** Roll-to-30+ Rate.

### Tier B — 20 KPI

**Power BI:** **15** Fee Income Share, **19** Active Card Penetration, **21** Active Accounts, **22** Net Account Growth, **45** BTYT Market Weight, **46** Market Weight Change YoY, **47** Net Interest Income Share, **49** Credit Loss Absorption.

**Excel:** **23** Net Account Flow, **39** Revenue per Active Customer, **40** Net Income per Active Customer.

**Tableau:** **41** Profitable Branch Share, **42** Branch Revenue Growth YoY, **44** Positive Response Rate.

**Superset:** **13** Digital Transaction Share - Count, **14** Transaction Failure Rate, **33** Completed Transaction Count, **34** Completed Transaction Volume.

**Python:** **30** Payment Shortfall Rate, **31** Cure Rate.

### Tier C — 9 KPI

**Excel:** **18** Active Accounts per Customer, **24** Average Balance per Account, **50** Deposits per Active Customer, **51** Loan Balance per Active Customer.

**Tableau:** **43** Campaign Exposure Rate.

**Superset:** **27** Opening Channel Share, **35** Digital Transaction Share - Value, **36** External Transfer Share.

**Python:** **20** Average Customer Tenure.

### Tier D — 1 KPI

**Excel:** **26** Product Target Alignment Rate.

## What changed in the freeze pass

- Removed the repetitive KPI lists from the beginning of the SQL files.
- Standardized inline tags as `KPI | Name | Tier | Tool`.
- Corrected `PW` semantics to **Power BI** and removed ambiguous tool abbreviations from SQL comments.
- Rebalanced tool ownership to match the tooling strategy instead of spreading executive KPIs across Excel/Tableau unnecessarily.
- Promoted core banking balance-sheet / risk indicators (Credit Loss Ratio, 30+ DPD Exposure Rate, Loan-to-Deposit Operating Ratio) into Tier S.
- Promoted YoY Net Income Change to Tier A; moved Average Customer Tenure to Tier C; moved synthetic Market Weight indicators to Tier B; moved Transaction Failure Rate to Tier B operational monitoring.
- Preserved the working SQL logic; this pass focuses on classification, documentation consistency and freeze-readiness.

## Files

- `01_bank_performance.sql` — KPI-01, KPI-02, KPI-03, KPI-04, KPI-05, KPI-08, KPI-09, KPI-48, KPI-49
- `02_bank_growth_and_revenue_mix.sql` — KPI-10, KPI-11, KPI-15, KPI-47, KPI-52
- `03_funding_and_credit_loss.sql` — KPI-02, KPI-03, KPI-06, KPI-12, KPI-25
- `04_loan_originations_and_credit_quality.sql` — KPI-07, KPI-28, KPI-29, KPI-30, KPI-31, KPI-32
- `05_branch_performance.sql` — KPI-37, KPI-38, KPI-39, KPI-40, KPI-41, KPI-42
- `06_customer_and_account_relationships.sql` — KPI-01, KPI-16, KPI-17, KPI-18, KPI-19, KPI-20, KPI-21, KPI-22, KPI-23, KPI-24, KPI-26, KPI-27, KPI-50, KPI-51
- `07_transactions_campaigns_and_market.sql` — KPI-13, KPI-14, KPI-33, KPI-34, KPI-35, KPI-36, KPI-43, KPI-44, KPI-45, KPI-46
