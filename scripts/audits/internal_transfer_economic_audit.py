from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


# =============================================================================
# Configuration
# =============================================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]

PAIR_CANDIDATES = [
    PROJECT_ROOT / "data" / "interim" / "internal_transfer_pairs.csv",
]

TRANSACTION_CANDIDATES = [
    PROJECT_ROOT / "data" / "processed" / "transactions.csv",
]

ACCOUNT_CANDIDATES = [
    PROJECT_ROOT / "data" / "processed" / "accounts.csv",
    PROJECT_ROOT / "data" / "raw" / "accounts.csv",
]

CUSTOMER_CANDIDATES = [
    PROJECT_ROOT / "data" / "processed" / "customers.csv",
    PROJECT_ROOT / "data" / "raw" / "customers.csv",
]


# =============================================================================
# Helpers
# =============================================================================

def find_existing_file(candidates: list[Path], label: str) -> Path:
    for path in candidates:
        if path.exists():
            print(f"{label}: {path}")
            return path

    formatted = "\n".join(f"  - {path}" for path in candidates)
    raise FileNotFoundError(
        f"Could not find {label}. Checked:\n{formatted}"
    )


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(col).strip().lower() for col in df.columns]
    return df


def find_column(
    df: pd.DataFrame,
    candidates: list[str],
    label: str,
    required: bool = True,
) -> str | None:
    for col in candidates:
        if col in df.columns:
            return col

    if required:
        raise KeyError(
            f"Could not identify column for '{label}'. "
            f"Tried: {candidates}\n"
            f"Available columns: {list(df.columns)}"
        )

    return None


def safe_ratio(
    numerator: pd.Series,
    denominator: pd.Series,
) -> pd.Series:
    numerator = pd.to_numeric(numerator, errors="coerce")
    denominator = pd.to_numeric(denominator, errors="coerce")

    valid = denominator.notna() & (denominator > 0)

    result = pd.Series(np.nan, index=numerator.index, dtype="float64")
    result.loc[valid] = numerator.loc[valid] / denominator.loc[valid]

    return result


def format_number(value: float | int | None, decimals: int = 2) -> str:
    if pd.isna(value):
        return "NaN"

    return f"{value:,.{decimals}f}"


def print_separator(char: str = "-", width: int = 100) -> None:
    print(char * width)


def print_quantiles(
    series: pd.Series,
    title: str,
    percent: bool = False,
) -> None:
    clean = pd.to_numeric(series, errors="coerce").dropna()

    print(title)

    if clean.empty:
        print("No valid observations.")
        return

    quantiles = clean.quantile(
        [0.50, 0.90, 0.95, 0.99, 0.999, 1.00]
    )

    for q, value in quantiles.items():
        label = {
            0.50: "P50",
            0.90: "P90",
            0.95: "P95",
            0.99: "P99",
            0.999: "P99.9",
            1.00: "MAX",
        }[q]

        if percent:
            print(f"{label:<8} {value * 100:>15,.2f}%")
        else:
            print(f"{label:<8} {value:>15,.2f}")


# =============================================================================
# Load data
# =============================================================================

print("=" * 100)
print("BTYT INTERNAL TRANSFER ECONOMIC MATCHING AUDIT")
print("=" * 100)

pair_path = find_existing_file(
    PAIR_CANDIDATES,
    "Internal transfer pairs",
)

transaction_path = find_existing_file(
    TRANSACTION_CANDIDATES,
    "Transactions",
)

account_path = find_existing_file(
    ACCOUNT_CANDIDATES,
    "Accounts",
)

customer_path = find_existing_file(
    CUSTOMER_CANDIDATES,
    "Customers",
)

print()

pairs = normalize_columns(pd.read_csv(pair_path))
transactions = normalize_columns(pd.read_csv(transaction_path))
accounts = normalize_columns(pd.read_csv(account_path))
customers = normalize_columns(pd.read_csv(customer_path))


# =============================================================================
# Detect schema
# =============================================================================

pair_id_col = find_column(
    pairs,
    ["pair_id", "transfer_pair_id", "internal_transfer_id"],
    "pair ID",
    required=False,
)

pair_out_tx_col = find_column(
    pairs,
    [
        "transfer_out_transaction_id",
        "out_transaction_id",
        "out_tx_id",
        "sender_transaction_id",
        "transaction_out_id",
    ],
    "outgoing transaction ID",
)

pair_in_tx_col = find_column(
    pairs,
    [
        "transfer_in_transaction_id",
        "in_transaction_id",
        "in_tx_id",
        "receiver_transaction_id",
        "transaction_in_id",
    ],
    "incoming transaction ID",
)

transaction_id_col = find_column(
    transactions,
    ["transaction_id", "tx_id"],
    "transaction ID",
)

transaction_account_col = find_column(
    transactions,
    ["account_id"],
    "transaction account ID",
)

transaction_customer_col = find_column(
    transactions,
    ["customer_id"],
    "transaction customer ID",
    required=False,
)

transaction_amount_col = find_column(
    transactions,
    ["amount", "transaction_amount"],
    "transaction amount",
)

transaction_datetime_col = find_column(
    transactions,
    ["transaction_datetime", "datetime", "timestamp", "transaction_date"],
    "transaction datetime",
)

transaction_currency_col = find_column(
    transactions,
    ["currency", "currency_code"],
    "transaction currency",
    required=False,
)

account_id_col = find_column(
    accounts,
    ["account_id"],
    "account ID",
)

account_customer_col = find_column(
    accounts,
    ["customer_id"],
    "account customer ID",
)

customer_id_col = find_column(
    customers,
    ["customer_id"],
    "customer ID",
)

customer_type_col = find_column(
    customers,
    ["customer_type", "type"],
    "customer type",
)

monthly_income_col = find_column(
    customers,
    [
        "monthly_income",
        "income_monthly",
        "monthly_net_income",
        "income",
    ],
    "monthly income",
    required=False,
)

annual_revenue_col = find_column(
    customers,
    [
        "annual_revenue",
        "yearly_revenue",
        "business_annual_revenue",
        "revenue",
    ],
    "annual revenue",
    required=False,
)

company_size_col = find_column(
    customers,
    ["company_size", "business_size"],
    "company size",
    required=False,
)

business_sector_col = find_column(
    customers,
    ["business_sector", "sector", "industry"],
    "business sector",
    required=False,
)


# =============================================================================
# Prepare lookup tables
# =============================================================================

accounts_lookup = accounts[
    [account_id_col, account_customer_col]
].drop_duplicates(subset=[account_id_col]).copy()

accounts_lookup.columns = [
    "lookup_account_id",
    "lookup_customer_id",
]

customer_columns = [
    customer_id_col,
    customer_type_col,
]

for optional_col in [
    monthly_income_col,
    annual_revenue_col,
    company_size_col,
    business_sector_col,
]:
    if optional_col is not None and optional_col not in customer_columns:
        customer_columns.append(optional_col)

customers_lookup = customers[
    customer_columns
].drop_duplicates(subset=[customer_id_col]).copy()


# =============================================================================
# Extract outgoing and incoming transaction attributes
# =============================================================================

transaction_columns = [
    transaction_id_col,
    transaction_amount_col,
    transaction_datetime_col,
]

if transaction_customer_col is not None:
    transaction_columns.append(transaction_customer_col)

tx_lookup = transactions[transaction_columns].copy()


# -----------------------------------------------------------------------------
# Outgoing transaction leg
# -----------------------------------------------------------------------------

outgoing_rename = {
    transaction_id_col: "out_transaction_id",
    transaction_amount_col: "out_amount",
    transaction_datetime_col: "out_transaction_datetime",
}

if transaction_customer_col is not None:
    outgoing_rename[transaction_customer_col] = "sender_customer_id"

outgoing = tx_lookup.rename(columns=outgoing_rename)


# -----------------------------------------------------------------------------
# Incoming transaction leg
# -----------------------------------------------------------------------------

incoming_rename = {
    transaction_id_col: "in_transaction_id",
    transaction_amount_col: "in_amount",
    transaction_datetime_col: "in_transaction_datetime",
}

if transaction_customer_col is not None:
    incoming_rename[transaction_customer_col] = "receiver_customer_id"

incoming = tx_lookup.rename(columns=incoming_rename)


# -----------------------------------------------------------------------------
# Merge transaction attributes into internal transfer pairs
# -----------------------------------------------------------------------------

audit = pairs.copy()

audit = audit.merge(
    outgoing,
    left_on=pair_out_tx_col,
    right_on="out_transaction_id",
    how="left",
)

audit = audit.merge(
    incoming,
    left_on=pair_in_tx_col,
    right_on="in_transaction_id",
    how="left",
)


# -----------------------------------------------------------------------------
# Standard transfer amount and datetime
#
# internal_transfer_pairs.csv is the authoritative source for:
# - sender_account_id
# - receiver_account_id
# - amount
# - transaction_datetime
# - currency
#
# Transactions are used only to recover customer IDs and cross-check legs.
# -----------------------------------------------------------------------------

if "amount" not in audit.columns:
    audit["amount"] = audit["out_amount"]

if "transaction_datetime" in audit.columns:
    audit["transfer_datetime"] = pd.to_datetime(
        audit["transaction_datetime"],
        errors="coerce",
    )
else:
    audit["transfer_datetime"] = pd.to_datetime(
        audit["out_transaction_datetime"],
        errors="coerce",
    )

# =============================================================================
# Recover customer IDs from accounts if transactions do not contain them
# =============================================================================

if "sender_customer_id" not in audit.columns:
    audit = audit.merge(
        accounts_lookup,
        left_on="sender_account_id",
        right_on="lookup_account_id",
        how="left",
    )

    audit = audit.rename(
        columns={"lookup_customer_id": "sender_customer_id"}
    )

    audit = audit.drop(
        columns=["lookup_account_id"],
        errors="ignore",
    )

if "receiver_customer_id" not in audit.columns:
    audit = audit.merge(
        accounts_lookup,
        left_on="receiver_account_id",
        right_on="lookup_account_id",
        how="left",
    )

    audit = audit.rename(
        columns={"lookup_customer_id": "receiver_customer_id"}
    )

    audit = audit.drop(
        columns=["lookup_account_id"],
        errors="ignore",
    )


# =============================================================================
# Add sender customer attributes
# =============================================================================

sender_customer_lookup = customers_lookup.rename(
    columns={
        customer_id_col: "sender_customer_id",
        customer_type_col: "sender_customer_type",
    }
)

if monthly_income_col is not None:
    sender_customer_lookup = sender_customer_lookup.rename(
        columns={monthly_income_col: "sender_monthly_income"}
    )

if annual_revenue_col is not None:
    sender_customer_lookup = sender_customer_lookup.rename(
        columns={annual_revenue_col: "sender_annual_revenue"}
    )

if company_size_col is not None:
    sender_customer_lookup = sender_customer_lookup.rename(
        columns={company_size_col: "sender_company_size"}
    )

if business_sector_col is not None:
    sender_customer_lookup = sender_customer_lookup.rename(
        columns={business_sector_col: "sender_business_sector"}
    )

audit = audit.merge(
    sender_customer_lookup,
    on="sender_customer_id",
    how="left",
)


# =============================================================================
# Add receiver customer attributes
# =============================================================================

receiver_customer_lookup = customers_lookup.rename(
    columns={
        customer_id_col: "receiver_customer_id",
        customer_type_col: "receiver_customer_type",
    }
)

if monthly_income_col is not None:
    receiver_customer_lookup = receiver_customer_lookup.rename(
        columns={monthly_income_col: "receiver_monthly_income"}
    )

if annual_revenue_col is not None:
    receiver_customer_lookup = receiver_customer_lookup.rename(
        columns={annual_revenue_col: "receiver_annual_revenue"}
    )

if company_size_col is not None:
    receiver_customer_lookup = receiver_customer_lookup.rename(
        columns={company_size_col: "receiver_company_size"}
    )

if business_sector_col is not None:
    receiver_customer_lookup = receiver_customer_lookup.rename(
        columns={business_sector_col: "receiver_business_sector"}
    )

audit = audit.merge(
    receiver_customer_lookup,
    on="receiver_customer_id",
    how="left",
)


# =============================================================================
# Standardize values
# =============================================================================

audit["sender_customer_type"] = (
    audit["sender_customer_type"]
    .astype("string")
    .str.upper()
)

audit["receiver_customer_type"] = (
    audit["receiver_customer_type"]
    .astype("string")
    .str.upper()
)

audit["amount"] = pd.to_numeric(
    audit["out_amount"],
    errors="coerce",
)

audit["transfer_datetime"] = pd.to_datetime(
    audit["transfer_datetime"],
    errors="coerce",
)

audit["direction_group"] = (
    audit["sender_customer_type"]
    + " -> "
    + audit["receiver_customer_type"]
)


# =============================================================================
# Economic ratios
# =============================================================================

if "receiver_monthly_income" in audit.columns:
    audit["receiver_income_ratio"] = safe_ratio(
        audit["amount"],
        audit["receiver_monthly_income"],
    )
else:
    audit["receiver_income_ratio"] = np.nan

if "receiver_annual_revenue" in audit.columns:
    audit["receiver_revenue_ratio"] = safe_ratio(
        audit["amount"],
        audit["receiver_annual_revenue"],
    )
else:
    audit["receiver_revenue_ratio"] = np.nan

if "sender_monthly_income" in audit.columns:
    audit["sender_income_ratio"] = safe_ratio(
        audit["amount"],
        audit["sender_monthly_income"],
    )
else:
    audit["sender_income_ratio"] = np.nan

if "sender_annual_revenue" in audit.columns:
    audit["sender_revenue_ratio"] = safe_ratio(
        audit["amount"],
        audit["sender_annual_revenue"],
    )
else:
    audit["sender_revenue_ratio"] = np.nan


# =============================================================================
# 1. Overview
# =============================================================================

print()
print_separator("=")
print("1. INTERNAL TRANSFER OVERVIEW")
print_separator("=")

print(f"Pairs: {len(audit):,}")
print(
    f"Unique sender customers: "
    f"{audit['sender_customer_id'].nunique():,}"
)
print(
    f"Unique receiver customers: "
    f"{audit['receiver_customer_id'].nunique():,}"
)

missing_sender = audit["sender_customer_type"].isna().sum()
missing_receiver = audit["receiver_customer_type"].isna().sum()

print(f"Pairs without sender customer type: {missing_sender:,}")
print(f"Pairs without receiver customer type: {missing_receiver:,}")

print()
print("Sender -> receiver composition:")

direction_counts = (
    audit["direction_group"]
    .value_counts(dropna=False)
    .rename_axis("direction")
    .reset_index(name="pairs")
)

direction_counts["share_pct"] = (
    direction_counts["pairs"] / len(audit) * 100
)

print(
    direction_counts.to_string(
        index=False,
        formatters={
            "pairs": lambda x: f"{x:,}",
            "share_pct": lambda x: f"{x:.2f}",
        },
    )
)


# =============================================================================
# 2. Amount distribution by sender -> receiver type
# =============================================================================

print()
print_separator("=")
print("2. AMOUNT DISTRIBUTION BY SENDER -> RECEIVER TYPE")
print_separator("=")

amount_summary = (
    audit.groupby("direction_group", dropna=False)["amount"]
    .agg(
        pairs="size",
        median="median",
        mean="mean",
        maximum="max",
    )
)

quantiles = (
    audit.groupby("direction_group", dropna=False)["amount"]
    .quantile([0.90, 0.95, 0.99, 0.999])
    .unstack()
    .rename(
        columns={
            0.90: "p90",
            0.95: "p95",
            0.99: "p99",
            0.999: "p999",
        }
    )
)

amount_summary = amount_summary.join(quantiles).reset_index()

amount_summary = amount_summary[
    [
        "direction_group",
        "pairs",
        "median",
        "mean",
        "p90",
        "p95",
        "p99",
        "p999",
        "maximum",
    ]
]

print(
    amount_summary.to_string(
        index=False,
        formatters={
            "pairs": lambda x: f"{x:,}",
            "median": lambda x: f"{x:,.2f}",
            "mean": lambda x: f"{x:,.2f}",
            "p90": lambda x: f"{x:,.2f}",
            "p95": lambda x: f"{x:,.2f}",
            "p99": lambda x: f"{x:,.2f}",
            "p999": lambda x: f"{x:,.2f}",
            "maximum": lambda x: f"{x:,.2f}",
        },
    )
)


# =============================================================================
# 3. Individual receiver economic capacity
# =============================================================================

print()
print_separator("=")
print("3. INDIVIDUAL RECEIVER ECONOMIC CAPACITY")
print_separator("=")

individual_receivers = audit[
    audit["receiver_customer_type"] == "INDIVIDUAL"
].copy()

print(f"Transfers to individuals: {len(individual_receivers):,}")
print(
    f"Unique individual receivers: "
    f"{individual_receivers['receiver_customer_id'].nunique():,}"
)

valid_individual_ratio = individual_receivers[
    "receiver_income_ratio"
].notna()

print(
    f"Transfers with usable monthly income: "
    f"{valid_individual_ratio.sum():,}"
)

print()

print_quantiles(
    individual_receivers["receiver_income_ratio"],
    "Amount / receiver monthly income:",
)

thresholds = [1, 3, 12, 60, 120, 600]

print()
print("Individual receiver ratio thresholds:")

threshold_rows = []

for threshold in thresholds:
    mask = individual_receivers["receiver_income_ratio"] > threshold

    threshold_rows.append(
        {
            "ratio_threshold": f">{threshold}x",
            "transfers": int(mask.sum()),
            "share_pct": (
                mask.mean() * 100
                if len(individual_receivers) > 0
                else np.nan
            ),
            "unique_receivers": (
                individual_receivers.loc[
                    mask,
                    "receiver_customer_id",
                ].nunique()
            ),
        }
    )

threshold_df = pd.DataFrame(threshold_rows)

print(
    threshold_df.to_string(
        index=False,
        formatters={
            "transfers": lambda x: f"{x:,}",
            "share_pct": lambda x: f"{x:.4f}",
            "unique_receivers": lambda x: f"{x:,}",
        },
    )
)


# =============================================================================
# 4. Business receiver economic capacity
# =============================================================================

print()
print_separator("=")
print("4. BUSINESS RECEIVER ECONOMIC CAPACITY")
print_separator("=")

business_receivers = audit[
    audit["receiver_customer_type"] == "BUSINESS"
].copy()

print(f"Transfers to businesses: {len(business_receivers):,}")
print(
    f"Unique business receivers: "
    f"{business_receivers['receiver_customer_id'].nunique():,}"
)

print()

print_quantiles(
    business_receivers["receiver_revenue_ratio"],
    "Amount / receiver annual revenue:",
    percent=True,
)

business_thresholds = [0.01, 0.05, 0.10, 0.25, 0.50, 1.00]

print()
print("Business receiver ratio thresholds:")

business_threshold_rows = []

for threshold in business_thresholds:
    mask = (
        business_receivers["receiver_revenue_ratio"]
        > threshold
    )

    business_threshold_rows.append(
        {
            "ratio_threshold": f">{threshold * 100:.0f}%",
            "transfers": int(mask.sum()),
            "share_pct": (
                mask.mean() * 100
                if len(business_receivers) > 0
                else np.nan
            ),
            "unique_receivers": (
                business_receivers.loc[
                    mask,
                    "receiver_customer_id",
                ].nunique()
            ),
        }
    )

business_threshold_df = pd.DataFrame(
    business_threshold_rows
)

print(
    business_threshold_df.to_string(
        index=False,
        formatters={
            "transfers": lambda x: f"{x:,}",
            "share_pct": lambda x: f"{x:.4f}",
            "unique_receivers": lambda x: f"{x:,}",
        },
    )
)


# =============================================================================
# 5. Business -> individual transfers
# =============================================================================

print()
print_separator("=")
print("5. BUSINESS -> INDIVIDUAL TRANSFERS")
print_separator("=")

business_to_individual = audit[
    (audit["sender_customer_type"] == "BUSINESS")
    & (audit["receiver_customer_type"] == "INDIVIDUAL")
].copy()

print(
    f"Business -> Individual pairs: "
    f"{len(business_to_individual):,}"
)

if len(business_to_individual) > 0:
    print_quantiles(
        business_to_individual["amount"],
        "\nTransfer amount:",
    )

    print_quantiles(
        business_to_individual["receiver_income_ratio"],
        "\nAmount / receiver monthly income:",
    )

    print_quantiles(
        business_to_individual["sender_revenue_ratio"],
        "\nAmount / sender annual revenue:",
        percent=True,
    )


# =============================================================================
# 6. Extreme individual receivers
# =============================================================================

print()
print_separator("=")
print("6. TOP 30 — MOST EXTREME INDIVIDUAL RECEIVERS")
print_separator("=")

top_individual = individual_receivers.sort_values(
    "receiver_income_ratio",
    ascending=False,
).head(30)

top_columns = []

if pair_id_col is not None:
    top_columns.append(pair_id_col)

for col in [
    "transfer_datetime",
    "amount",
    "sender_customer_id",
    "sender_customer_type",
    "sender_annual_revenue",
    "receiver_customer_id",
    "receiver_customer_type",
    "receiver_monthly_income",
    "receiver_income_ratio",
    "sender_account_id",
    "receiver_account_id",
    "currency",
]:
    if col in top_individual.columns:
        top_columns.append(col)

if top_individual.empty:
    print("No individual receiver observations.")
else:
    print(
        top_individual[top_columns].to_string(
            index=False,
            formatters={
                "amount": lambda x: f"{x:,.2f}",
                "sender_annual_revenue":
                    lambda x: format_number(x),
                "receiver_monthly_income":
                    lambda x: format_number(x),
                "receiver_income_ratio":
                    lambda x: format_number(x),
            },
        )
    )


# =============================================================================
# 7. Top business -> individual transfers by absolute amount
# =============================================================================

print()
print_separator("=")
print("7. TOP 30 — BUSINESS -> INDIVIDUAL BY AMOUNT")
print_separator("=")

top_business_individual = business_to_individual.sort_values(
    "amount",
    ascending=False,
).head(30)

business_individual_columns = []

if pair_id_col is not None:
    business_individual_columns.append(pair_id_col)

for col in [
    "transfer_datetime",
    "amount",
    "sender_customer_id",
    "sender_annual_revenue",
    "sender_revenue_ratio",
    "receiver_customer_id",
    "receiver_monthly_income",
    "receiver_income_ratio",
    "sender_account_id",
    "receiver_account_id",
    "currency",
]:
    if col in top_business_individual.columns:
        business_individual_columns.append(col)

if top_business_individual.empty:
    print("No Business -> Individual transfers.")
else:
    print(
        top_business_individual[
            business_individual_columns
        ].to_string(
            index=False,
            formatters={
                "amount": lambda x: f"{x:,.2f}",
                "sender_annual_revenue":
                    lambda x: format_number(x),
                "sender_revenue_ratio":
                    lambda x: (
                        f"{x * 100:,.4f}%"
                        if pd.notna(x)
                        else "NaN"
                    ),
                "receiver_monthly_income":
                    lambda x: format_number(x),
                "receiver_income_ratio":
                    lambda x: format_number(x),
            },
        )
    )


# =============================================================================
# 8. Receiver concentration among extreme transfers
# =============================================================================

print()
print_separator("=")
print("8. EXTREME INDIVIDUAL RECEIVER CONCENTRATION")
print_separator("=")

extreme_threshold = 120

extreme_individual = individual_receivers[
    individual_receivers["receiver_income_ratio"]
    > extreme_threshold
].copy()

print(
    f"Transfers above {extreme_threshold}x monthly income: "
    f"{len(extreme_individual):,}"
)

print(
    f"Unique receivers above {extreme_threshold}x: "
    f"{extreme_individual['receiver_customer_id'].nunique():,}"
)

if not extreme_individual.empty:
    receiver_concentration = (
        extreme_individual.groupby(
            "receiver_customer_id"
        )
        .agg(
            extreme_transfers=("amount", "size"),
            total_amount=("amount", "sum"),
            max_amount=("amount", "max"),
            max_income_ratio=(
                "receiver_income_ratio",
                "max",
            ),
        )
        .sort_values(
            ["extreme_transfers", "max_income_ratio"],
            ascending=[False, False],
        )
        .head(30)
        .reset_index()
    )

    print()
    print(
        receiver_concentration.to_string(
            index=False,
            formatters={
                "extreme_transfers":
                    lambda x: f"{x:,}",
                "total_amount":
                    lambda x: f"{x:,.2f}",
                "max_amount":
                    lambda x: f"{x:,.2f}",
                "max_income_ratio":
                    lambda x: f"{x:,.2f}",
            },
        )
    )


# =============================================================================
# 9. Diagnostic flags
# =============================================================================

print()
print_separator("=")
print("9. AUTOMATED DIAGNOSTIC FLAGS")
print_separator("=")

flags = []

if len(audit) == 0:
    flags.append(
        ("FAIL", "No internal transfer pairs were found.")
    )
else:
    flags.append(
        (
            "PASS",
            f"Internal transfer pairs loaded: {len(audit):,}.",
        )
    )

missing_economic_identity = (
    audit["sender_customer_type"].isna()
    | audit["receiver_customer_type"].isna()
).sum()

if missing_economic_identity == 0:
    flags.append(
        (
            "PASS",
            "All transfer pairs have sender and receiver customer types.",
        )
    )
else:
    flags.append(
        (
            "WARN",
            f"{missing_economic_identity:,} pairs have missing "
            "customer-type information.",
        )
    )

extreme_individual_count = len(extreme_individual)

if extreme_individual_count == 0:
    flags.append(
        (
            "PASS",
            "No individual receiver exceeds 120x monthly income.",
        )
    )
else:
    extreme_share = (
        extreme_individual_count
        / max(len(individual_receivers), 1)
        * 100
    )

    if extreme_share < 0.05:
        level = "INFO"
    elif extreme_share < 0.50:
        level = "WARN"
    else:
        level = "FAIL"

    flags.append(
        (
            level,
            f"{extreme_individual_count:,} transfers to individuals "
            f"exceed 120x receiver monthly income "
            f"({extreme_share:.4f}% of transfers to individuals).",
        )
    )

for level, message in flags:
    print(f"[{level}] {message}")


# =============================================================================
# 10. Summary
# =============================================================================

print()
print_separator("=")
print("BTYT INTERNAL TRANSFER ECONOMIC MATCHING — SUMMARY")
print_separator("=")

pass_count = sum(level == "PASS" for level, _ in flags)
info_count = sum(level == "INFO" for level, _ in flags)
warn_count = sum(level == "WARN" for level, _ in flags)
fail_count = sum(level == "FAIL" for level, _ in flags)

print(f"PASS flags: {pass_count}")
print(f"INFO flags: {info_count}")
print(f"WARN flags: {warn_count}")
print(f"FAIL flags: {fail_count}")

if fail_count > 0:
    status = "REQUIRES REVIEW"
elif warn_count > 0:
    status = "PASS WITH WARNINGS"
else:
    status = "PASS"

print()
print(f"ECONOMIC MATCHING STATUS: {status}")

print()
print("IMPORTANT:")
print(
    "Ratio thresholds are diagnostic tools, not hard business rules."
)
print(
    "Interpret the empirical distribution before modifying the "
    "transaction DGP or internal-transfer receiver selection."
)

print()
print_separator("=")
print("AUDIT COMPLETE")
print_separator("=")