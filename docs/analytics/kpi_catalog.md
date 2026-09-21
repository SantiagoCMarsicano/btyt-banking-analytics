BTYT Part I — KPI Catalog and Tier List

Analytical ranking proposed for what BTYT Part I can support and should show. This is the assistant’s independent assessment, separate from Santiago’s annotated vote. A tier is not proof that its source SQL has been verified.

Scope and interpretation

S: central to BTYT’s performance story; A: strong addition; B: useful contextual analysis; C: situational or drill-down; D: supporting measure rather than a headline KPI.

Number is the identifier in the reduced 52-item game. Original is the identifier in the initial 82-item PDF.

The ranking weighs decision value, distinctiveness for the synthetic BTYT bank, and likely support in its modeled data. Implementation status must be checked against source tables and audited SQL separately.

Primary output code: PW = Power BI, E = Excel, T = Tableau, S = Superset, P = Python. Exactly one code is assigned per KPI as its intended main output; PostgreSQL remains the shared calculation layer. This follows the Power BI ownership defined in the tooling strategy.

The earlier Executive / Thematic / Supporting terminology described dashboard placement. It is not equivalent to the S–D vote and is superseded as a priority ranking here.

Tier board

S — 7 indicators

01 Active Customers, 02 Average Deposits, 03 Average Loan Balance, 04 Total Revenue, 05 Cost-to-Income, 08 Net Income, 09 Net Margin.

A — 17 indicators

06 Credit Loss Ratio, 07 30+ DPD Exposure Rate, 10 YoY Revenue Growth, 12 Loan-to-Deposit Operating Ratio, 14 Transaction Failure Rate, 16 New Customers, 17 Net Customer Growth, 25 Deposit Growth YoY, 28 Loan Origination Amount, 29 90+ DPD Exposure Rate, 32 Roll-to-30+ Rate, 37 Branch Net Income, 38 Branch Cost-to-Income, 45 BTYT Market Weight, 46 Market Weight Change YoY, 48 Pre-Provision Margin, 52 Operating Leverage.

B — 18 indicators

11 YoY Net Income Change, 13 Digital Transaction Share - Count, 15 Fee Income Share, 19 Active Card Penetration, 21 Active Accounts, 22 Net Account Growth, 23 Net Account Flow, 30 Payment Shortfall Rate, 31 Cure Rate, 33 Completed Transaction Count, 34 Completed Transaction Volume, 39 Revenue per Active Customer, 40 Net Income per Active Customer, 41 Profitable Branch Share, 42 Branch Revenue Growth YoY, 44 Positive Response Rate, 47 Net Interest Income Share, 49 Credit Loss Absorption.

C — 8 indicators

18 Active Accounts per Customer, 24 Average Balance per Account, 27 Opening Channel Share, 35 Digital Transaction Share - Value, 36 External Transfer Share, 43 Campaign Exposure Rate, 50 Deposits per Active Customer, 51 Loan Balance per Active Customer.

D — 2 indicators

20 Average Customer Tenure, 26 Product Target Alignment Rate.

Numbered KPI register

No.

Original

Tier

Tool

KPI

Domain

Working definition

01

1

S

PW

Active Customers

Customers

Count active customers in the selected period

02

2

S

E

Average Deposits

Funding

Average monthly deposit balance

03

3

S

PW

Average Loan Balance

Lending

Average monthly outstanding loan balance

04

4

S

PW

Total Revenue

Profitability

Net interest income + fee income

05

5

S

E

Cost-to-Income

Profitability

Operating cost / total revenue

06

6

A

P

Credit Loss Ratio

Credit Risk

Credit loss / average loan balance

07

7

A

P

30+ DPD Exposure Rate

Credit Risk

30+ DPD outstanding exposure / total outstanding exposure

08

8

S

PW

Net Income

Profitability

Revenue - operating cost - credit loss

09

9

S

PW

Net Margin

Profitability

Net income / total revenue

10

10

A

E

YoY Revenue Growth

Profitability

Current revenue / prior-year revenue - 1

11

11

B

E

YoY Net Income Change

Profitability

Current net income - prior-year net income

12

12

A

E

Loan-to-Deposit Operating Ratio

Funding

Average loan balance / average deposits

13

13

B

S

Digital Transaction Share - Count

Transactions

Completed MOBILE + WEB count / completed count

14

14

A

S

Transaction Failure Rate

Transactions

Failed attempts / all attempts

15

15

B

E

Fee Income Share

Profitability

Fee income / total revenue

16

16

A

E

New Customers

Customers

Customers registered in period

17

18

A

E

Net Customer Growth

Customers

New customers - closed customers

18

19

C

E

Active Accounts per Customer

Customers

Active accounts / active customers

19

20

B

E

Active Card Penetration

Customers

Active customers with active card / active customers

20

22

D

P

Average Customer Tenure

Customers

Average elapsed time since customer registration

21

24

B

E

Active Accounts

Accounts

Count active accounts in selected period

22

27

B

E

Net Account Growth

Accounts

Accounts opened - accounts closed

23

28

B

E

Net Account Flow

Accounts

Account inflows - account outflows

24

29

C

E

Average Balance per Account

Accounts

Applicable average deposits / applicable accounts

25

30

A

E

Deposit Growth YoY

Funding

Current average deposits / prior-year average deposits - 1

26

31

D

E

Product Target Alignment Rate

Accounts

Aligned applicable relationships / applicable relationships

27

32

C

S

Opening Channel Share

Accounts

Accounts opened through channel / all accounts opened

28

34

A

E

Loan Origination Amount

Lending

Sum principal of loans originated in period

29

35

A

P

90+ DPD Exposure Rate

Credit Risk

90+ DPD outstanding exposure / total outstanding exposure

30

37

B

P

Payment Shortfall Rate

Credit Risk

Sum payment shortfall / sum scheduled payments

31

38

B

P

Cure Rate

Credit Risk

Delinquent loans returning to current / eligible delinquent loans

32

39

A

P

Roll-to-30+ Rate

Credit Risk

Loans moving from below 30 to 30+ DPD / eligible loans below 30 DPD

33

43

B

S

Completed Transaction Count

Transactions

Count transactions with COMPLETED status

34

44

B

S

Completed Transaction Volume

Transactions

Sum amount for COMPLETED transactions

35

47

C

S

Digital Transaction Share - Value

Transactions

Completed MOBILE + WEB amount / completed amount

36

50

C

S

External Transfer Share

Transactions

External completed transfers / completed transfers

37

52

A

T

Branch Net Income

Branches

Net income attributable to each branch

38

53

A

T

Branch Cost-to-Income

Branches

Branch operating cost / branch revenue

39

56

B

E

Revenue per Active Customer

Branches

Applicable revenue / applicable active customers

40

57

B

E

Net Income per Active Customer

Branches

Applicable net income / applicable active customers

41

60

B

T

Profitable Branch Share

Branches

Branches with positive net income / eligible branches

42

61

B

T

Branch Revenue Growth YoY

Branches

Current branch revenue / prior-year branch revenue - 1

43

63

C

E

Campaign Exposure Rate

Campaigns

Exposed selected customers / selected customers

44

65

B

T

Positive Response Rate

Campaigns

Exposed customers with positive response / exposed customers

45

69

A

PW

BTYT Market Weight

Market

BTYT weight in a specified synthetic-market measure

46

70

A

PW

Market Weight Change YoY

Market

Current BTYT market weight - prior-year weight (percentage points)

47

73

B

E

Net Interest Income Share

Profitability

Net interest income / total revenue

48

74

A

E

Pre-Provision Margin

Profitability

Pre-provision profit / total revenue

49

75

B

P

Credit Loss Absorption

Profitability

Credit loss / pre-provision profit

50

77

C

E

Deposits per Active Customer

Customers

Applicable average deposits / applicable active customers

51

78

C

E

Loan Balance per Active Customer

Customers

Applicable average loan balance / applicable active customers

52

82

A

E

Operating Leverage

Profitability

Revenue growth rate - operating-cost growth rate

BTYT-specific measurement rules

Profitability is synthetic operating performance. The performance layer contains revenue, operating costs, credit loss and resulting net income. Do not label these as audited statutory net income, ROE, ROA or regulatory capital returns without corresponding accounting and balance-sheet data.

Time: distinguish monthly stocks (customers, accounts, average deposits and loans) from additive flows (revenue, losses, originations and transactions). Recompute ratios from their aggregate numerator and denominator. Do not sum monthly stock values or average monthly ratios by default.

Currency: performance.* reporting amounts are UYU-equivalent. Lower-level UYU and USD values must be separated unless an explicit FX conversion is used.

Transactions: attempted operations include COMPLETED and FAILED; realized counts and value include only COMPLETED. Value and count channel shares serve different questions.

Credit quality: DPD ratios use outstanding exposure as numerator and denominator at a common loan-month grain. The 30+ and 90+ buckets use inclusive cutoffs. Cure and roll rates require consecutive monthly snapshots and an explicitly defined eligible cohort.

Campaigns: POSITIVE response is observed receptivity, not purchase or product conversion. Exposure and response denominators must match their defined cohorts.

Branches and customers: use documented allocation and distinct-customer rules. Avoid summing branch-level active customers into a bank-wide count if a customer may appear in multiple branches.

Market: synthetic market weight depends on the specified market measure and is distinct from observed peer profitability. Peer financial benchmarking requires comparable bank-level revenue, cost, loss and exposure measures; do not derive a profitability ranking from market weights alone.

No arbitrary thresholds: present current value, trend and peer or branch comparison before introducing undocumented red/amber/green targets.

SQL implementation sequence

Validate existing bank-month profitability fields; build a commented step-by-step query for 04, 05, 08, 09, 10, 11, 15, 47, 48, 49 and 52. Keep component totals visible even when 04 is B.

Add funding, credit scale and risk (02, 03, 06, 07, 12, 25, 28, 29, 30, 31, 32); document denominator, period and currency.

Compare BTYT branches (37, 38, 41, 42), then customer and account relationships (01, 16–27, 39, 40, 50, 51).

Extend to campaigns, transaction channels and synthetic market (13, 14, 33–36, 43–46). Keep D-level measures available as denominators and diagnostic checks.

For any interbank profitability benchmark, first verify comparable financial measures for all synthetic banks. Otherwise show the market-weight comparison (45–46) and label its scope precisely.

Validation checklist

Identify physical source table and column for each selected measure.

Specify reporting grain, time window, currency and bank / branch / customer scope.

Define zero or negative denominators for margin, growth and loss absorption.

Reconcile revenue − operating cost − credit loss with net income.

Compare SQL measures with later DAX measures for controlled periods.

Record which interbank comparisons are backed by comparable financial data.

Change from the previous catalog

The former 82-candidate document contained overlapping count, inverse-ratio and channel variants. This 52-item register replaces that candidate ranking with an independent BTYT-specific assessment