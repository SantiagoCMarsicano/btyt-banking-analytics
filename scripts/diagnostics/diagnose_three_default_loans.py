from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
DATA_GENERATED = ROOT / "data" / "generated"
DATA_INTERIM = ROOT / "data" / "interim"

LOAN_IDS = ["L0002387", "L0004577", "L0011630"]

loans = pd.read_csv(DATA_GENERATED / "loans.csv")
bridge = pd.read_csv(DATA_INTERIM / "loan_lifecycle_bridge.csv")
snapshot = pd.read_csv(DATA_GENERATED / "loan_monthly_snapshot.csv")

print("=" * 88)
print("BTYT DEFAULT-AT-CUTOFF DIAGNOSTIC")
print("=" * 88)

loan_cols = [
    "loan_id",
    "customer_id",
    "product_id",
    "branch_id",
    "origination_year",
    "currency",
    "original_amount",
    "term_months",
    "rate_type",
    "initial_interest_rate",
    "loan_status",
    "closing_year",
]

bridge_cols = [
    "loan_id",
    "origination_month_internal",
    "lifecycle_seed",
    "resolution_month_internal",
    "terminal_event_internal",
    "pre2021_inherited_state",
]

print("\nMASTER + BRIDGE")
merged = (
    loans.loc[loans["loan_id"].isin(LOAN_IDS), loan_cols]
    .merge(
        bridge.loc[bridge["loan_id"].isin(LOAN_IDS), bridge_cols],
        on="loan_id",
        how="left",
        validate="one_to_one",
    )
    .sort_values("loan_id")
)
print(merged.to_string(index=False))

for loan_id in LOAN_IDS:
    s = snapshot.loc[snapshot["loan_id"] == loan_id].copy()
    s["year_month"] = s["year_month"].astype(str)
    s = s.sort_values("year_month")

    print("\n" + "-" * 88)
    print(f"{loan_id} — LAST 12 MONTHS")
    print("-" * 88)

    cols = [
        "loan_id",
        "year_month",
        "outstanding_balance",
        "current_interest_rate",
        "scheduled_payment",
        "actual_payment",
        "days_past_due",
        "delinquency_status",
        "arrears_amount",
    ]
    print(s[cols].tail(12).to_string(index=False))

    delinquent = s.loc[s["days_past_due"] > 0]
    if delinquent.empty:
        print("\nFirst delinquent month: NONE")
    else:
        first = delinquent.iloc[0]
        print(
            "\nFirst delinquent month:",
            first["year_month"],
            "| DPD:",
            int(first["days_past_due"]),
            "| scheduled:",
            first["scheduled_payment"],
            "| actual:",
            first["actual_payment"],
            "| arrears:",
            first["arrears_amount"],
        )

    final = s.iloc[-1]
    print(
        "Final month:",
        final["year_month"],
        "| DPD:",
        int(final["days_past_due"]),
        "| status:",
        final["delinquency_status"],
        "| arrears:",
        final["arrears_amount"],
        "| outstanding:",
        final["outstanding_balance"],
    )
