from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np
import pandas as pd


# =============================================================================
# BTYT BANKING ANALYTICS — BRANCH PERFORMANCE ENGINE
# =============================================================================
#
# Builds a monthly management-accounting layer from the frozen BTYT datasets.
# It does not regenerate or modify upstream canonical data.
#
# Outputs:
#   data/generated/branch_monthly_performance.csv
#   data/generated/bank_monthly_performance.csv
#
# All monetary outputs are expressed in UYU-equivalent.
# All code and comments are intentionally written in English.
# =============================================================================


# =============================================================================
# PROJECT PATHS
# =============================================================================

PROJECT_ROOT = Path(__file__).resolve().parents[1]

DATA_GENERATED = PROJECT_ROOT / "data" / "generated"
DATA_INTERIM = PROJECT_ROOT / "data" / "interim"
DATA_MASTER = PROJECT_ROOT / "data" / "master"

CUSTOMERS_PATH = DATA_GENERATED / "customers.csv"
ACCOUNTS_PATH = DATA_GENERATED / "accounts.csv"
CARDS_PATH = DATA_GENERATED / "cards.csv"
LOANS_PATH = DATA_GENERATED / "loans.csv"
LOAN_SNAPSHOT_PATH = DATA_GENERATED / "loan_monthly_snapshot.csv"
TRANSACTIONS_PATH = DATA_GENERATED / "transactions.csv"
ACCOUNT_BALANCES_PATH = DATA_GENERATED / "account_balances.csv"
BRANCHES_PATH = DATA_GENERATED / "branches.csv"
BRANCH_STATE_PATH = DATA_INTERIM / "branch_yearly_state.csv"
LOAN_LIFECYCLE_BRIDGE_PATH = DATA_INTERIM / "loan_lifecycle_bridge.csv"
PRODUCTS_PATH = DATA_MASTER / "products.csv"

BRANCH_OUTPUT_PATH = DATA_GENERATED / "branch_monthly_performance.csv"
BANK_OUTPUT_PATH = DATA_GENERATED / "bank_monthly_performance.csv"


# =============================================================================
# OBSERVATION WINDOW
# =============================================================================

OBS_START = pd.Period("2021-01", freq="M")
OBS_END = pd.Period("2026-12", freq="M")
MONTHS = pd.period_range(OBS_START, OBS_END, freq="M")
YEARS = tuple(range(OBS_START.year, OBS_END.year + 1))

REPORTING_CURRENCY = "UYU"
TRANSACTION_CHUNK_SIZE = 500_000
PERFORMANCE_SEED = 20260902


# =============================================================================
# FX ASSUMPTIONS
# =============================================================================

FX_UYU_PER_USD = {
    2021: 43.6,
    2022: 41.2,
    2023: 38.8,
    2024: 40.3,
    2025: 42.0,
    2026: 43.5,
}


# =============================================================================
# SYNTHETIC COST CALIBRATION
# =============================================================================

BASE_STAFF_EQUIVALENTS = {
    "LARGE": 30.0,
    "MEDIUM": 16.0,
    "SMALL": 8.0,
}

BRANCH_TYPE_STAFF_MULTIPLIER = {
    "BRANCH": 1.00,
    "AGENCY": 0.78,
}

BASE_FIXED_MONTHLY_COST_2021 = {
    "LARGE": 760_000.0,
    "MEDIUM": 450_000.0,
    "SMALL": 240_000.0,
}

BRANCH_TYPE_FIXED_MULTIPLIER = {
    "BRANCH": 1.00,
    "AGENCY": 0.86,
}

BASE_MONTHLY_LABOR_COST_2021 = 78_000.0

ANNUAL_WAGE_INDEX = {
    2021: 1.000,
    2022: 1.090,
    2023: 1.180,
    2024: 1.270,
    2025: 1.360,
    2026: 1.440,
}

ANNUAL_PRICE_INDEX = {
    2021: 1.000,
    2022: 1.090,
    2023: 1.155,
    2024: 1.220,
    2025: 1.270,
    2026: 1.320,
}

LOCATION_COST_MULTIPLIER = {
    "WTC": 1.35,
    "Carrasco": 1.25,
    "Punta del Este": 1.18,
    "Montevideo Centro": 1.15,
    "Prado": 1.10,
    "Ciudad de la Costa": 1.08,
    "Maldonado": 1.08,
}

PERSONNEL_COST_PRESSURE_BETA = 0.04
FIXED_COST_PRESSURE_BETA = 0.08
VARIABLE_COST_PRESSURE_BETA = 0.06
OTHER_COST_PRESSURE_BETA = 0.20

VARIABLE_COST_ELASTICITY = 0.82
BASE_VARIABLE_COST_SHARE = 0.15
BASE_OTHER_OPERATIONAL_COST_SHARE = 0.18


# =============================================================================
# DEPOSIT FUNDING RATES
# =============================================================================

DEPOSIT_RATE_2021 = {
    "P001": 0.0025,
    "P002": 0.0015,
    "P003": 0.0010,
    "P004": 0.0015,
    "P005": 0.0015,
    "P006": 0.0015,
    "P007": 0.0550,
    "P008": 0.0150,
}

DEPOSIT_RATE_YEAR_MULTIPLIER = {
    2021: 1.00,
    2022: 1.15,
    2023: 1.30,
    2024: 1.18,
    2025: 1.08,
    2026: 1.03,
}


# =============================================================================
# CREDIT-RISK COST CALIBRATION
# =============================================================================

PROVISION_COVERAGE_RATE = {
    "CURRENT": 0.0025,
    "DPD_1_30": 0.0075,
    "DPD_31_60": 0.0225,
    "DPD_61_90": 0.0600,
    "DPD_90_PLUS": 0.1500,
}

# Loss-given-default assumption used only when a loan is actually written off.
# The terminal charge recognizes the residual loss not already covered by the
# delinquency-based provision carried immediately before resolution.
WRITEOFF_LGD = 0.30

# Pre-2021 loans enter the observed window with historical credit risk already
# embedded. Only a small opening catch-up is recognized in January 2021.
INHERITED_OPENING_PROVISION_FACTOR = 0.05

INTEREST_RECOGNITION_FACTOR = {
    "CURRENT": 1.00,
    "DPD_1_30": 0.98,
    "DPD_31_60": 0.90,
    "DPD_61_90": 0.65,
    "DPD_90_PLUS": 0.15,
}


# =============================================================================
# CARD FEE CALIBRATION
# =============================================================================

BASE_CARD_MONTHLY_FEE_2021 = {
    "P009": 110.0,
    "P010": 560.0,
    "P011": 1_150.0,
}


# =============================================================================
# OUTPUT SCHEMA
# =============================================================================

BRANCH_OUTPUT_COLUMNS = [
    "branch_id",
    "year_month",
    "active_customers",
    "active_accounts",
    "average_deposits",
    "average_loan_balance",
    "transaction_count",
    "transaction_volume",
    "branch_transaction_count",
    "interest_income",
    "interest_expense",
    "net_interest_income",
    "fee_income",
    "total_revenue",
    "personnel_cost",
    "fixed_cost",
    "variable_cost",
    "operational_cost",
    "total_operating_cost",
    "credit_loss",
    "pre_provision_profit",
    "net_income",
]

BANK_OUTPUT_COLUMNS = [
    "year_month",
    *[col for col in BRANCH_OUTPUT_COLUMNS if col not in {"branch_id", "year_month"}],
]

MONETARY_COLUMNS = [
    "average_deposits",
    "average_loan_balance",
    "transaction_volume",
    "interest_income",
    "interest_expense",
    "net_interest_income",
    "fee_income",
    "total_revenue",
    "personnel_cost",
    "fixed_cost",
    "variable_cost",
    "operational_cost",
    "total_operating_cost",
    "credit_loss",
    "pre_provision_profit",
    "net_income",
]

COUNT_COLUMNS = [
    "active_customers",
    "active_accounts",
    "transaction_count",
    "branch_transaction_count",
]


# =============================================================================
# GENERAL HELPERS
# =============================================================================

def require_file(path: Path) -> None:
    if not path.exists():
        raise FileNotFoundError(f"Required input not found: {path}")


def require_columns(df: pd.DataFrame, required: set[str], name: str) -> None:
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"{name} missing columns: {sorted(missing)}")


def normalize_branch_series(series: pd.Series) -> pd.Series:
    numeric = pd.to_numeric(series, errors="coerce").astype("Int64")
    result = numeric.astype("string").str.zfill(3)
    return result.where(numeric.notna(), pd.NA)


def normalize_id_string(series: pd.Series) -> pd.Series:
    return series.astype("string").str.strip()


def year_from_month_string(series: pd.Series) -> pd.Series:
    return pd.to_numeric(
        series.astype("string").str.slice(0, 4), errors="coerce"
    ).astype("Int64")


def fx_factor(currency: pd.Series, year: pd.Series) -> np.ndarray:
    currency = currency.astype("string").str.upper()
    year_numeric = pd.to_numeric(year, errors="coerce")
    fx = year_numeric.map(FX_UYU_PER_USD).astype(float)
    return np.asarray(np.where(currency.eq("USD"), fx, 1.0), dtype=float)


def annual_rate_to_fraction(series: pd.Series) -> pd.Series:
    rate = pd.to_numeric(series, errors="coerce").astype(float)
    return pd.Series(
        np.where(rate > 1.5, rate / 100.0, rate),
        index=series.index,
    )


def stable_uniform(key: str, low: float, high: float) -> float:
    payload = f"{PERFORMANCE_SEED}|{key}".encode("utf-8")
    digest = hashlib.blake2b(payload, digest_size=8).digest()
    integer = int.from_bytes(digest, byteorder="big", signed=False)
    u = integer / float(2**64 - 1)
    return float(low + (high - low) * u)


def monthly_index(year_month: str, annual_index: dict[int, float]) -> float:
    period = pd.Period(year_month, freq="M")
    year = int(period.year)
    month = int(period.month)
    current = float(annual_index[year])
    next_value = float(annual_index.get(year + 1, current))
    fraction = (month - 1) / 12.0
    return float(current + fraction * (next_value - current))


def branch_operational_in_year(opening_year: int, closing_year, year: int) -> bool:
    if year < int(opening_year):
        return False
    if pd.notna(closing_year):
        return year <= int(closing_year)
    return True


# =============================================================================
# INPUT LOADING AND VALIDATION
# =============================================================================

def load_inputs() -> dict[str, pd.DataFrame]:
    for path in [
        CUSTOMERS_PATH,
        ACCOUNTS_PATH,
        CARDS_PATH,
        LOANS_PATH,
        LOAN_SNAPSHOT_PATH,
        TRANSACTIONS_PATH,
        ACCOUNT_BALANCES_PATH,
        BRANCHES_PATH,
        BRANCH_STATE_PATH,
        LOAN_LIFECYCLE_BRIDGE_PATH,
        PRODUCTS_PATH,
    ]:
        require_file(path)

    data = {
        "customers": pd.read_csv(CUSTOMERS_PATH),
        "accounts": pd.read_csv(ACCOUNTS_PATH),
        "cards": pd.read_csv(CARDS_PATH),
        "loans": pd.read_csv(LOANS_PATH),
        "loan_snapshot": pd.read_csv(LOAN_SNAPSHOT_PATH),
        "account_balances": pd.read_csv(ACCOUNT_BALANCES_PATH),
        "branches": pd.read_csv(BRANCHES_PATH),
        "branch_state": pd.read_csv(BRANCH_STATE_PATH),
        "loan_lifecycle_bridge": pd.read_csv(LOAN_LIFECYCLE_BRIDGE_PATH),
        "products": pd.read_csv(PRODUCTS_PATH),
    }

    require_columns(data["customers"], {"customer_id", "primary_branch_id"}, "customers.csv")
    require_columns(
        data["accounts"],
        {"account_id", "customer_id", "product_id", "branch_id", "opening_year", "account_status", "closing_year"},
        "accounts.csv",
    )
    require_columns(
        data["cards"],
        {"card_id", "customer_id", "product_id", "linked_account_id", "issue_year", "card_status", "closing_year"},
        "cards.csv",
    )
    require_columns(
        data["loans"],
        {"loan_id", "customer_id", "product_id", "branch_id", "currency", "loan_status"},
        "loans.csv",
    )
    require_columns(
        data["loan_snapshot"],
        {"loan_id", "year_month", "outstanding_balance", "current_interest_rate", "delinquency_status"},
        "loan_monthly_snapshot.csv",
    )
    require_columns(
        data["account_balances"],
        {"account_id", "year_month", "opening_balance", "closing_balance"},
        "account_balances.csv",
    )
    require_columns(
        data["branches"],
        {"branch_id", "branch_name", "branch_type", "branch_size", "status", "opening_year", "closing_year", "region"},
        "branches.csv",
    )
    require_columns(data["branch_state"], {"branch_id", "year", "cost_pressure"}, "branch_yearly_state.csv")
    require_columns(
        data["loan_lifecycle_bridge"],
        {"loan_id", "resolution_month_internal", "terminal_event_internal", "pre2021_inherited_state"},
        "loan_lifecycle_bridge.csv",
    )
    require_columns(data["products"], {"product_id", "product_family", "currency"}, "products.csv")

    return data


def normalize_inputs(data: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    customers = data["customers"]
    accounts = data["accounts"]
    cards = data["cards"]
    loans = data["loans"]
    snapshot = data["loan_snapshot"]
    balances = data["account_balances"]
    branches = data["branches"]
    branch_state = data["branch_state"]
    lifecycle = data["loan_lifecycle_bridge"]
    products = data["products"]

    customers["customer_id"] = normalize_id_string(customers["customer_id"])
    customers["primary_branch_id"] = normalize_branch_series(customers["primary_branch_id"])

    accounts["account_id"] = normalize_id_string(accounts["account_id"])
    accounts["customer_id"] = normalize_id_string(accounts["customer_id"])
    accounts["product_id"] = normalize_id_string(accounts["product_id"])
    accounts["branch_id"] = normalize_branch_series(accounts["branch_id"])

    cards["card_id"] = normalize_id_string(cards["card_id"])
    cards["customer_id"] = normalize_id_string(cards["customer_id"])
    cards["product_id"] = normalize_id_string(cards["product_id"])
    cards["linked_account_id"] = normalize_id_string(cards["linked_account_id"])

    loans["loan_id"] = normalize_id_string(loans["loan_id"])
    loans["customer_id"] = normalize_id_string(loans["customer_id"])
    loans["product_id"] = normalize_id_string(loans["product_id"])
    loans["branch_id"] = normalize_branch_series(loans["branch_id"])
    loans["currency"] = loans["currency"].astype("string").str.upper()

    snapshot["loan_id"] = normalize_id_string(snapshot["loan_id"])
    snapshot["year_month"] = snapshot["year_month"].astype("string").str.slice(0, 7)

    balances["account_id"] = normalize_id_string(balances["account_id"])
    balances["year_month"] = balances["year_month"].astype("string").str.slice(0, 7)

    branches["branch_id"] = normalize_branch_series(branches["branch_id"])
    branches["branch_name"] = branches["branch_name"].astype("string")
    branches["branch_type"] = branches["branch_type"].astype("string").str.upper()
    branches["branch_size"] = branches["branch_size"].astype("string").str.upper()
    branches["opening_year"] = pd.to_numeric(branches["opening_year"], errors="raise").astype(int)
    branches["closing_year"] = pd.to_numeric(branches["closing_year"], errors="coerce").astype("Int64")

    branch_state["branch_id"] = normalize_branch_series(branch_state["branch_id"])
    branch_state["year"] = pd.to_numeric(branch_state["year"], errors="raise").astype(int)
    branch_state["cost_pressure"] = pd.to_numeric(branch_state["cost_pressure"], errors="raise").astype(float)

    lifecycle["loan_id"] = normalize_id_string(lifecycle["loan_id"])
    lifecycle["resolution_month_internal"] = (
        lifecycle["resolution_month_internal"].astype("string").str.slice(0, 7)
    )
    lifecycle["terminal_event_internal"] = (
        lifecycle["terminal_event_internal"].astype("string").str.upper()
    )

    products["product_id"] = normalize_id_string(products["product_id"])
    products["currency"] = products["currency"].astype("string").str.upper()

    return data


def validate_inputs(data: dict[str, pd.DataFrame]) -> None:
    branches = data["branches"]
    branch_state = data["branch_state"]
    accounts = data["accounts"]
    loans = data["loans"]
    lifecycle = data["loan_lifecycle_bridge"]

    if branches["branch_id"].isna().any():
        raise ValueError("branches.csv contains invalid branch_id values.")

    if lifecycle["loan_id"].duplicated().any():
        raise ValueError("loan_lifecycle_bridge.csv contains duplicate loan_id values.")

    unknown_lifecycle_loans = set(lifecycle["loan_id"].dropna()) - set(loans["loan_id"].dropna())
    if unknown_lifecycle_loans:
        sample = sorted(unknown_lifecycle_loans)[:10]
        raise ValueError(f"loan_lifecycle_bridge.csv contains unknown loan_id values: {sample}")
    if branches["branch_id"].duplicated().any():
        raise ValueError("Duplicate branch_id in branches.csv.")

    expected_branch_years = pd.MultiIndex.from_product(
        [branches["branch_id"].tolist(), YEARS], names=["branch_id", "year"]
    )
    actual_branch_years = pd.MultiIndex.from_frame(
        branch_state[["branch_id", "year"]].drop_duplicates()
    )
    missing_state = expected_branch_years.difference(actual_branch_years)
    if len(missing_state):
        raise ValueError(
            "branch_yearly_state.csv does not cover all branch/year combinations. "
            f"Missing examples: {list(missing_state[:10])}"
        )

    if branch_state.duplicated(["branch_id", "year"]).any():
        raise ValueError("Duplicate branch_id/year in branch_yearly_state.csv.")

    known_branches = set(branches["branch_id"].dropna())
    unknown_account_branches = set(accounts["branch_id"].dropna()) - known_branches
    unknown_loan_branches = set(loans["branch_id"].dropna()) - known_branches

    if unknown_account_branches:
        raise ValueError(f"accounts.csv contains unknown branches: {sorted(unknown_account_branches)[:10]}")
    if unknown_loan_branches:
        raise ValueError(f"loans.csv contains unknown branches: {sorted(unknown_loan_branches)[:10]}")

    for name, mapping in [
        ("FX_UYU_PER_USD", FX_UYU_PER_USD),
        ("ANNUAL_WAGE_INDEX", ANNUAL_WAGE_INDEX),
        ("ANNUAL_PRICE_INDEX", ANNUAL_PRICE_INDEX),
    ]:
        if set(mapping) != set(YEARS):
            raise ValueError(f"{name} must cover every analysis year.")


# =============================================================================
# BASE BRANCH-MONTH GRID
# =============================================================================

def build_base_grid(branches: pd.DataFrame, branch_state: pd.DataFrame) -> pd.DataFrame:
    grid = pd.MultiIndex.from_product(
        [branches["branch_id"].tolist(), [str(m) for m in MONTHS]],
        names=["branch_id", "year_month"],
    ).to_frame(index=False)
    grid["year"] = year_from_month_string(grid["year_month"]).astype(int)

    state = branch_state[["branch_id", "year", "cost_pressure"]].copy()
    grid = grid.merge(state, on=["branch_id", "year"], how="left", validate="many_to_one")

    if grid["cost_pressure"].isna().any():
        raise ValueError("Missing cost_pressure after branch-state merge.")
    return grid


# =============================================================================
# ACCOUNT / DEPOSIT METRICS
# =============================================================================

def build_account_metrics(
    balances: pd.DataFrame,
    accounts: pd.DataFrame,
    products: pd.DataFrame,
) -> pd.DataFrame:
    account_map = accounts[["account_id", "customer_id", "product_id", "branch_id"]].drop_duplicates("account_id")
    product_map = products[["product_id", "currency"]].drop_duplicates("product_id")

    frame = balances.merge(account_map, on="account_id", how="left", validate="many_to_one")
    frame = frame.merge(product_map, on="product_id", how="left", validate="many_to_one")

    if frame["branch_id"].isna().any():
        bad = frame.loc[frame["branch_id"].isna(), "account_id"].head(10).tolist()
        raise ValueError(f"Account balances contain unknown account_id values: {bad}")
    if frame["currency"].isna().any():
        bad = frame.loc[frame["currency"].isna(), "product_id"].head(10).tolist()
        raise ValueError(f"Missing product currency for account products: {bad}")

    frame["year"] = year_from_month_string(frame["year_month"]).astype(int)
    opening = pd.to_numeric(frame["opening_balance"], errors="raise").astype(float)
    closing = pd.to_numeric(frame["closing_balance"], errors="raise").astype(float)

    if (opening < -0.01).any() or (closing < -0.01).any():
        raise ValueError("Negative account balance detected in account_balances.csv.")

    frame["average_native_balance"] = (opening + closing) / 2.0
    frame["fx"] = fx_factor(frame["currency"], frame["year"])
    frame["average_deposits"] = frame["average_native_balance"] * frame["fx"]

    base_rate = frame["product_id"].map(DEPOSIT_RATE_2021).fillna(0.0).astype(float)
    year_mult = frame["year"].map(DEPOSIT_RATE_YEAR_MULTIPLIER).astype(float)
    if year_mult.isna().any():
        raise ValueError("Deposit-rate year multiplier missing for at least one balance row.")

    frame["annual_deposit_rate"] = base_rate * year_mult
    frame["interest_expense"] = frame["average_deposits"] * frame["annual_deposit_rate"] / 12.0

    customer_branch = (
        frame.groupby(["year_month", "customer_id", "branch_id"], as_index=False, observed=True)["average_deposits"]
        .sum()
        .sort_values(
            ["year_month", "customer_id", "average_deposits", "branch_id"],
            ascending=[True, True, False, True],
        )
    )
    relationship_assignment = customer_branch.drop_duplicates(["year_month", "customer_id"], keep="first")

    active_customers = (
        relationship_assignment.groupby(["branch_id", "year_month"], as_index=False, observed=True)["customer_id"]
        .nunique()
        .rename(columns={"customer_id": "active_customers"})
    )

    aggregate = (
        frame.groupby(["branch_id", "year_month"], as_index=False, observed=True)
        .agg(
            active_accounts=("account_id", "nunique"),
            average_deposits=("average_deposits", "sum"),
            interest_expense=("interest_expense", "sum"),
        )
    )
    aggregate = aggregate.merge(active_customers, on=["branch_id", "year_month"], how="left", validate="one_to_one")
    aggregate["active_customers"] = aggregate["active_customers"].fillna(0).astype(int)
    return aggregate


# =============================================================================
# LOAN / CREDIT METRICS
# =============================================================================

def build_loan_metrics(
    snapshot: pd.DataFrame,
    loans: pd.DataFrame,
    lifecycle: pd.DataFrame,
) -> pd.DataFrame:
    loan_map = loans[
        ["loan_id", "branch_id", "currency", "product_id", "loan_status"]
    ].drop_duplicates("loan_id")

    lifecycle_map = lifecycle[
        ["loan_id", "resolution_month_internal", "terminal_event_internal"]
    ].drop_duplicates("loan_id")

    frame = snapshot.merge(
        loan_map,
        on="loan_id",
        how="left",
        validate="many_to_one",
    )
    frame = frame.merge(
        lifecycle_map,
        on="loan_id",
        how="left",
        validate="many_to_one",
    )

    if frame["branch_id"].isna().any():
        bad = frame.loc[frame["branch_id"].isna(), "loan_id"].head(10).tolist()
        raise ValueError(f"Loan snapshot contains unknown loan_id values: {bad}")

    frame["year"] = year_from_month_string(frame["year_month"]).astype(int)
    frame["fx"] = fx_factor(frame["currency"], frame["year"])

    outstanding_native = pd.to_numeric(
        frame["outstanding_balance"],
        errors="raise",
    ).astype(float)

    if (outstanding_native < -0.01).any():
        raise ValueError("Negative outstanding balance detected in loan snapshot.")

    frame["outstanding_uyu"] = outstanding_native * frame["fx"]
    rate_fraction = annual_rate_to_fraction(frame["current_interest_rate"])

    delinquency = frame["delinquency_status"].astype("string").str.upper()
    recognition = delinquency.map(INTEREST_RECOGNITION_FACTOR)
    provision_rate = delinquency.map(PROVISION_COVERAGE_RATE)

    if recognition.isna().any():
        unknown = sorted(delinquency[recognition.isna()].dropna().unique().tolist())
        raise ValueError(f"Unknown delinquency_status values: {unknown}")

    if provision_rate.isna().any():
        unknown = sorted(delinquency[provision_rate.isna()].dropna().unique().tolist())
        raise ValueError(f"Missing provision calibration for: {unknown}")

    frame["provision_rate"] = provision_rate.astype(float)

    frame["interest_income"] = (
        frame["outstanding_uyu"]
        * rate_fraction
        / 12.0
        * recognition.astype(float)
    )

    # Required reserve is a stock. Credit-loss expense is driven by changes in
    # that stock, so a stable delinquency state is not charged repeatedly.
    frame["required_provision"] = (
        frame["outstanding_uyu"] * frame["provision_rate"]
    )

    frame = frame.sort_values(["loan_id", "year_month"]).copy()

    previous_required = (
        frame.groupby("loan_id", observed=True)["required_provision"].shift(1)
    )
    first_row = previous_required.isna()
    opening_month = frame["year_month"].eq(str(OBS_START))

    frame["previous_required_provision"] = previous_required.fillna(0.0)
    frame["provision_expense"] = (
        frame["required_provision"] - frame["previous_required_provision"]
    )

    # Existing exposures at the start of 2021 already carried historical risk.
    # Recognizing only a small opening catch-up prevents an artificial first-year
    # spike while keeping some reserve cost in the observed period.
    inherited_opening = first_row & opening_month
    frame.loc[inherited_opening, "provision_expense"] *= (
        INHERITED_OPENING_PROVISION_FACTOR
    )

    # Terminal write-off loss:
    # identify the final observed snapshot row for every loan whose lifecycle
    # resolves as WRITTEN_OFF inside 2021-2026. The residual loss equals LGD
    # minus the provision already associated with that exposure.
    frame["terminal_loss"] = 0.0

    observed_resolution = (
        frame["resolution_month_internal"].notna()
        & frame["resolution_month_internal"].between(
            str(OBS_START),
            str(OBS_END),
            inclusive="both",
        )
    )
    written_off = (
        frame["terminal_event_internal"].eq("WRITE_OFF")
        & observed_resolution
    )

    if written_off.any():
        candidate = frame.loc[written_off].copy()

        # A write-off snapshot can already carry a zero outstanding balance.
        # Therefore terminal loss must be based on the last positive exposure
        # observed at or before resolution, not mechanically on the terminal row.
        candidate = candidate.loc[candidate["outstanding_uyu"] > 0.01].copy()

        if not candidate.empty:
            candidate["year_month_ord"] = (
                candidate["year_month"].str.replace("-", "", regex=False).astype(int)
            )
            candidate["resolution_month_ord"] = (
                candidate["resolution_month_internal"]
                .str.replace("-", "", regex=False)
                .astype(int)
            )

            candidate = candidate.loc[
                candidate["year_month_ord"] <= candidate["resolution_month_ord"]
            ].copy()

            terminal_index = (
                candidate.sort_values(
                    ["loan_id", "year_month_ord"],
                    ascending=[True, False],
                )
                .drop_duplicates("loan_id", keep="first")
                .index
            )

            residual_lgd = np.maximum(
                WRITEOFF_LGD
                - frame.loc[terminal_index, "provision_rate"].to_numpy(dtype=float),
                0.0,
            )

            frame.loc[terminal_index, "terminal_loss"] = (
                frame.loc[terminal_index, "outstanding_uyu"].to_numpy(dtype=float)
                * residual_lgd
            )

    frame["credit_loss"] = (
        frame["provision_expense"] + frame["terminal_loss"]
    )

    terminal_loss_count = int((frame["terminal_loss"] > 0.0).sum())
    terminal_loss_total = float(frame["terminal_loss"].sum())
    print(
        "Loan terminal-loss audit | "
        f"write-off rows charged: {terminal_loss_count:,} | "
        f"terminal loss: UYU {terminal_loss_total / 1_000_000:,.3f} million"
    )

    aggregate = (
        frame.groupby(
            ["branch_id", "year_month"],
            as_index=False,
            observed=True,
        )
        .agg(
            average_loan_balance=("outstanding_uyu", "sum"),
            interest_income=("interest_income", "sum"),
            credit_loss=("credit_loss", "sum"),
            active_loan_count=("loan_id", "nunique"),
        )
    )

    # Provision releases may offset current deterioration and write-off charges,
    # but the managerial output column represents credit-loss expense rather
    # than provision income. Therefore branch-month credit loss is floored at 0.

    return aggregate


# =============================================================================
# CARD FEE METRICS
# =============================================================================

def build_card_fee_metrics(
    cards: pd.DataFrame,
    accounts: pd.DataFrame,
    customers: pd.DataFrame,
) -> pd.DataFrame:
    account_branch = (
        accounts[["account_id", "branch_id"]]
        .drop_duplicates("account_id")
        .set_index("account_id")["branch_id"]
    )
    customer_branch = (
        customers[["customer_id", "primary_branch_id"]]
        .drop_duplicates("customer_id")
        .set_index("customer_id")["primary_branch_id"]
    )

    frame = cards.copy()
    linked_branch = frame["linked_account_id"].map(account_branch)
    primary_branch = frame["customer_id"].map(customer_branch)
    frame["performance_branch_id"] = linked_branch.fillna(primary_branch)

    if frame["performance_branch_id"].isna().any():
        bad = frame.loc[
            frame["performance_branch_id"].isna(),
            ["card_id", "customer_id", "linked_account_id"],
        ].head(10)
        raise ValueError("Unable to attribute some cards to a branch:\n" + bad.to_string(index=False))

    frame["issue_year"] = pd.to_numeric(frame["issue_year"], errors="raise").astype(int)
    frame["closing_year_num"] = pd.to_numeric(frame["closing_year"], errors="coerce").astype("Int64")

    rows: list[pd.DataFrame] = []
    for month in MONTHS:
        year = int(month.year)
        ym = str(month)
        active = frame[
            (frame["issue_year"] <= year)
            & (frame["closing_year_num"].isna() | (frame["closing_year_num"] >= year))
        ].copy()
        if active.empty:
            continue

        price_idx = monthly_index(ym, ANNUAL_PRICE_INDEX)
        active["card_fee_income"] = (
            active["product_id"].map(BASE_CARD_MONTHLY_FEE_2021).fillna(0.0).astype(float) * price_idx
        )
        active["year_month"] = ym

        grouped = (
            active.groupby(["performance_branch_id", "year_month"], as_index=False, observed=True)["card_fee_income"]
            .sum()
            .rename(columns={"performance_branch_id": "branch_id"})
        )
        rows.append(grouped)

    if not rows:
        return pd.DataFrame(columns=["branch_id", "year_month", "card_fee_income"])
    return pd.concat(rows, ignore_index=True)


# =============================================================================
# TRANSACTION METRICS
# =============================================================================

def transaction_fee_income(frame: pd.DataFrame) -> pd.Series:
    ttype = frame["transaction_type"].astype("string").str.upper()
    scope = frame["transfer_scope"].astype("string").str.upper()
    amount = frame["amount_uyu"].astype(float)
    amount_array = amount.to_numpy(dtype=float)

    fee = np.zeros(len(frame), dtype=float)

    # Pandas StringDtype comparisons can produce nullable boolean masks when
    # transfer_scope is missing for non-transfer transaction types. NumPy does
    # not accept nullable/object masks for positional indexing, so every mask is
    # explicitly converted to a pure bool ndarray after treating NA as False.
    domestic_out = (
        ttype.eq("TRANSFER_OUT") & scope.eq("DOMESTIC_EXTERNAL")
    ).fillna(False).to_numpy(dtype=bool)
    international_out = (
        ttype.eq("TRANSFER_OUT") & scope.eq("INTERNATIONAL")
    ).fillna(False).to_numpy(dtype=bool)
    debit_purchase = (
        ttype.eq("DEBIT_PURCHASE")
    ).fillna(False).to_numpy(dtype=bool)
    service_payment = (
        ttype.eq("SERVICE_PAYMENT")
    ).fillna(False).to_numpy(dtype=bool)

    fee[domestic_out] = 35.0 + np.minimum(
        amount_array[domestic_out] * 0.00050, 850.0
    )
    fee[international_out] = 150.0 + np.minimum(
        amount_array[international_out] * 0.00160, 4_500.0
    )
    fee[debit_purchase] = np.minimum(
        amount_array[debit_purchase] * 0.0060, 650.0
    )
    fee[service_payment] = 22.0

    return pd.Series(fee, index=frame.index, dtype=float)


def build_transaction_metrics(
    transactions_path: Path,
    accounts: pd.DataFrame,
    products: pd.DataFrame,
) -> pd.DataFrame:
    account_map = accounts[["account_id", "branch_id", "product_id"]].drop_duplicates("account_id")
    product_currency = (
        products[["product_id", "currency"]]
        .drop_duplicates("product_id")
        .set_index("product_id")["currency"]
    )
    account_map["currency"] = account_map["product_id"].map(product_currency)

    if account_map["currency"].isna().any():
        bad = account_map.loc[account_map["currency"].isna(), "product_id"].unique()
        raise ValueError(f"Missing account-product currencies: {bad[:10]}")

    account_lookup = account_map.set_index("account_id")[["branch_id", "currency"]]
    aggregate_parts: list[pd.DataFrame] = []
    total_rows = 0
    completed_rows = 0

    usecols = [
        "account_id",
        "transaction_datetime",
        "transaction_type",
        "channel",
        "amount",
        "transfer_scope",
        "transaction_branch_id",
        "transaction_status",
    ]

    print("\nReading canonical transactions in chunks...")

    for chunk_number, chunk in enumerate(
        pd.read_csv(
            transactions_path,
            usecols=usecols,
            chunksize=TRANSACTION_CHUNK_SIZE,
            low_memory=False,
        ),
        start=1,
    ):
        total_rows += len(chunk)
        chunk["account_id"] = normalize_id_string(chunk["account_id"])
        chunk["transaction_status"] = chunk["transaction_status"].astype("string").str.upper()
        chunk = chunk[chunk["transaction_status"].eq("COMPLETED")].copy()
        completed_rows += len(chunk)

        if chunk.empty:
            continue

        dt = pd.to_datetime(chunk["transaction_datetime"], errors="coerce")
        if dt.isna().any():
            raise ValueError(f"Invalid transaction_datetime detected in chunk {chunk_number}.")

        chunk["year_month"] = dt.dt.to_period("M").astype("string")
        chunk["year"] = dt.dt.year.astype(int)
        chunk = chunk[chunk["year"].between(OBS_START.year, OBS_END.year)].copy()
        if chunk.empty:
            continue

        branch = chunk["account_id"].map(account_lookup["branch_id"])
        currency = chunk["account_id"].map(account_lookup["currency"])
        if branch.isna().any():
            bad = chunk.loc[branch.isna(), "account_id"].head(10).tolist()
            raise ValueError(
                "transactions.csv contains account_id values missing from accounts.csv: "
                f"{bad}"
            )

        chunk["relationship_branch_id"] = branch
        chunk["currency"] = currency
        amount_native = pd.to_numeric(chunk["amount"], errors="raise").astype(float)
        if (amount_native < -0.01).any():
            raise ValueError("Negative transaction amount detected.")

        chunk["fx"] = fx_factor(chunk["currency"], chunk["year"])
        chunk["amount_uyu"] = amount_native * chunk["fx"]
        chunk["transaction_branch_id"] = normalize_branch_series(chunk["transaction_branch_id"])
        chunk["fee_income_tx"] = transaction_fee_income(chunk)

        relationship = (
            chunk.groupby(["relationship_branch_id", "year_month"], as_index=False, observed=True)
            .agg(
                transaction_count=("account_id", "size"),
                transaction_volume=("amount_uyu", "sum"),
                transaction_fee_income=("fee_income_tx", "sum"),
            )
            .rename(columns={"relationship_branch_id": "branch_id"})
        )

        physical = (
            chunk[
                chunk["channel"].astype("string").str.upper().eq("BRANCH")
                & chunk["transaction_branch_id"].notna()
            ]
            .groupby(["transaction_branch_id", "year_month"], as_index=False, observed=True)
            .size()
            .rename(columns={"transaction_branch_id": "branch_id", "size": "branch_transaction_count"})
        )

        aggregate_parts.append(
            relationship.merge(physical, on=["branch_id", "year_month"], how="outer")
        )

        if chunk_number % 2 == 0:
            print(
                f"  processed chunks: {chunk_number:,} | "
                f"source rows: {total_rows:,} | completed rows: {completed_rows:,}"
            )

    if not aggregate_parts:
        raise ValueError("No completed transaction activity found.")

    combined = pd.concat(aggregate_parts, ignore_index=True)
    combined = (
        combined.groupby(["branch_id", "year_month"], as_index=False, observed=True)
        .agg(
            transaction_count=("transaction_count", "sum"),
            transaction_volume=("transaction_volume", "sum"),
            branch_transaction_count=("branch_transaction_count", "sum"),
            transaction_fee_income=("transaction_fee_income", "sum"),
        )
    )

    for col in ["transaction_count", "transaction_volume", "branch_transaction_count", "transaction_fee_income"]:
        combined[col] = combined[col].fillna(0)

    print(
        f"Transaction pass complete | source rows: {total_rows:,} | "
        f"completed rows: {completed_rows:,}"
    )
    return combined


# =============================================================================
# COST ENGINE
# =============================================================================

def build_branch_structure(branches: pd.DataFrame) -> pd.DataFrame:
    structure = branches[
        ["branch_id", "branch_name", "branch_type", "branch_size", "opening_year", "closing_year", "region"]
    ].copy()

    structure["staff_base"] = structure["branch_size"].map(BASE_STAFF_EQUIVALENTS)
    structure["staff_base"] *= structure["branch_type"].map(BRANCH_TYPE_STAFF_MULTIPLIER).fillna(1.0)

    structure["fixed_base"] = structure["branch_size"].map(BASE_FIXED_MONTHLY_COST_2021)
    structure["fixed_base"] *= structure["branch_type"].map(BRANCH_TYPE_FIXED_MULTIPLIER).fillna(1.0)

    if structure["staff_base"].isna().any():
        unknown = sorted(structure.loc[structure["staff_base"].isna(), "branch_size"].unique())
        raise ValueError(f"Unknown branch_size for staff calibration: {unknown}")
    if structure["fixed_base"].isna().any():
        unknown = sorted(structure.loc[structure["fixed_base"].isna(), "branch_size"].unique())
        raise ValueError(f"Unknown branch_size for fixed-cost calibration: {unknown}")

    structure["location_multiplier"] = structure["branch_name"].map(LOCATION_COST_MULTIPLIER).fillna(1.0)
    interior = ~structure["region"].astype("string").str.upper().eq("METROPOLITAN")
    no_named_override = ~structure["branch_name"].isin(LOCATION_COST_MULTIPLIER)
    structure.loc[interior & no_named_override, "location_multiplier"] *= 0.92

    structure["staff_jitter"] = structure["branch_id"].map(
        lambda branch_id: stable_uniform(f"staff|{branch_id}", 0.93, 1.08)
    )
    structure["fixed_jitter"] = structure["branch_id"].map(
        lambda branch_id: stable_uniform(f"fixed|{branch_id}", 0.90, 1.11)
    )
    structure["other_jitter"] = structure["branch_id"].map(
        lambda branch_id: stable_uniform(f"other|{branch_id}", 0.90, 1.12)
    )
    return structure


def add_costs(performance: pd.DataFrame, branches: pd.DataFrame) -> pd.DataFrame:
    frame = performance.merge(build_branch_structure(branches), on="branch_id", how="left", validate="many_to_one")

    positive_tx = frame.loc[frame["transaction_count"] > 0, "transaction_count"]
    positive_branch_tx = frame.loc[frame["branch_transaction_count"] > 0, "branch_transaction_count"]
    positive_accounts = frame.loc[frame["active_accounts"] > 0, "active_accounts"]
    positive_loans = frame.loc[frame["active_loan_count"] > 0, "active_loan_count"]

    tx_ref = max(float(positive_tx.median()) if len(positive_tx) else 1.0, 1.0)
    branch_tx_ref = max(float(positive_branch_tx.median()) if len(positive_branch_tx) else 1.0, 1.0)
    account_ref = max(float(positive_accounts.median()) if len(positive_accounts) else 1.0, 1.0)
    loan_ref = max(float(positive_loans.median()) if len(positive_loans) else 1.0, 1.0)

    frame["workload_index"] = (
        0.55 * frame["transaction_count"] / tx_ref
        + 0.25 * frame["branch_transaction_count"] / branch_tx_ref
        + 0.15 * frame["active_accounts"] / account_ref
        + 0.05 * frame["active_loan_count"] / loan_ref
    ).clip(lower=0.0)

    frame["operational_flag"] = [
        branch_operational_in_year(row.opening_year, row.closing_year, int(row.year))
        for row in frame.itertuples(index=False)
    ]

    wage_index = frame["year_month"].map(lambda ym: monthly_index(str(ym), ANNUAL_WAGE_INDEX))
    price_index = frame["year_month"].map(lambda ym: monthly_index(str(ym), ANNUAL_PRICE_INDEX))
    cp = frame["cost_pressure"].clip(-2.5, 2.5).astype(float)

    frame["personnel_cost"] = (
        frame["staff_base"]
        * frame["staff_jitter"]
        * BASE_MONTHLY_LABOR_COST_2021
        * wage_index
        * np.exp(PERSONNEL_COST_PRESSURE_BETA * cp)
    )

    frame["fixed_cost"] = (
        frame["fixed_base"]
        * frame["fixed_jitter"]
        * frame["location_multiplier"]
        * price_index
        * np.exp(FIXED_COST_PRESSURE_BETA * cp)
    )

    rigid_base = frame["personnel_cost"] + frame["fixed_cost"]
    workload_effect = np.power(
        np.maximum(frame["workload_index"].to_numpy(dtype=float), 0.0),
        VARIABLE_COST_ELASTICITY,
    )

    frame["variable_cost"] = (
        rigid_base
        * BASE_VARIABLE_COST_SHARE
        * workload_effect
        * np.exp(VARIABLE_COST_PRESSURE_BETA * cp)
    )

    frame["operational_cost"] = (
        rigid_base
        * BASE_OTHER_OPERATIONAL_COST_SHARE
        * frame["other_jitter"]
        * np.exp(OTHER_COST_PRESSURE_BETA * cp)
    )

    closed_mask = ~frame["operational_flag"]
    for col in ["personnel_cost", "fixed_cost", "variable_cost", "operational_cost"]:
        frame.loc[closed_mask, col] = 0.0

    frame["total_operating_cost"] = (
        frame["personnel_cost"]
        + frame["fixed_cost"]
        + frame["variable_cost"]
        + frame["operational_cost"]
    )
    return frame


# =============================================================================
# FINAL PERFORMANCE ASSEMBLY
# =============================================================================

def assemble_performance(data: dict[str, pd.DataFrame]) -> pd.DataFrame:
    base = build_base_grid(data["branches"], data["branch_state"])
    account_metrics = build_account_metrics(data["account_balances"], data["accounts"], data["products"])
    loan_metrics = build_loan_metrics(
        data["loan_snapshot"],
        data["loans"],
        data["loan_lifecycle_bridge"],
    )
    card_fees = build_card_fee_metrics(data["cards"], data["accounts"], data["customers"])
    transaction_metrics = build_transaction_metrics(TRANSACTIONS_PATH, data["accounts"], data["products"])

    frame = base.merge(account_metrics, on=["branch_id", "year_month"], how="left", validate="one_to_one")
    frame = frame.merge(loan_metrics, on=["branch_id", "year_month"], how="left", validate="one_to_one")
    frame = frame.merge(transaction_metrics, on=["branch_id", "year_month"], how="left", validate="one_to_one")
    frame = frame.merge(card_fees, on=["branch_id", "year_month"], how="left", validate="one_to_one")

    fill_zero = [
        "active_customers",
        "active_accounts",
        "average_deposits",
        "interest_expense",
        "average_loan_balance",
        "interest_income",
        "credit_loss",
        "active_loan_count",
        "transaction_count",
        "transaction_volume",
        "branch_transaction_count",
        "transaction_fee_income",
        "card_fee_income",
    ]
    for col in fill_zero:
        frame[col] = pd.to_numeric(frame[col], errors="coerce").fillna(0.0)

    frame["fee_income"] = frame["transaction_fee_income"] + frame["card_fee_income"]
    frame["net_interest_income"] = frame["interest_income"] - frame["interest_expense"]
    frame["total_revenue"] = frame["net_interest_income"] + frame["fee_income"]

    frame = add_costs(frame, data["branches"])
    frame["pre_provision_profit"] = frame["total_revenue"] - frame["total_operating_cost"]
    frame["net_income"] = frame["pre_provision_profit"] - frame["credit_loss"]
    return frame


# =============================================================================
# VALIDATION
# =============================================================================

def validate_branch_output(branch_output: pd.DataFrame, branches: pd.DataFrame) -> None:
    errors: list[str] = []
    expected_rows = len(branches) * len(MONTHS)

    if len(branch_output) != expected_rows:
        errors.append(f"row count {len(branch_output):,} != expected {expected_rows:,}")
    if branch_output.duplicated(["branch_id", "year_month"]).any():
        errors.append("duplicate branch_id/year_month")
    if set(branch_output["year_month"]) != {str(m) for m in MONTHS}:
        errors.append("year_month coverage differs from 2021-01 through 2026-12")
    if set(branch_output["branch_id"]) != set(branches["branch_id"]):
        errors.append("branch coverage differs from branches.csv")

    nonnegative = [
        "active_customers",
        "active_accounts",
        "average_deposits",
        "average_loan_balance",
        "transaction_count",
        "transaction_volume",
        "branch_transaction_count",
        "interest_income",
        "interest_expense",
        "fee_income",
        "personnel_cost",
        "fixed_cost",
        "variable_cost",
        "operational_cost",
        "total_operating_cost",
    ]
    for col in nonnegative:
        if (pd.to_numeric(branch_output[col], errors="coerce") < -0.01).any():
            errors.append(f"negative values in {col}")

    checks = {
        "net_interest_identity": branch_output["net_interest_income"] - (branch_output["interest_income"] - branch_output["interest_expense"]),
        "revenue_identity": branch_output["total_revenue"] - (branch_output["net_interest_income"] + branch_output["fee_income"]),
        "operating_cost_identity": branch_output["total_operating_cost"] - (
            branch_output["personnel_cost"]
            + branch_output["fixed_cost"]
            + branch_output["variable_cost"]
            + branch_output["operational_cost"]
        ),
        "pre_provision_identity": branch_output["pre_provision_profit"] - (branch_output["total_revenue"] - branch_output["total_operating_cost"]),
        "net_income_identity": branch_output["net_income"] - (branch_output["pre_provision_profit"] - branch_output["credit_loss"]),
    }
    for name, residual in checks.items():
        if residual.abs().max() > 0.05:
            errors.append(f"{name} failed; max residual={residual.abs().max():.4f}")

    if errors:
        raise AssertionError("BRANCH PERFORMANCE VALIDATION FAILED:\n- " + "\n- ".join(errors))


def build_bank_output(branch_output: pd.DataFrame) -> pd.DataFrame:
    additive_columns = [
        col for col in BRANCH_OUTPUT_COLUMNS if col not in {"branch_id", "year_month"}
    ]
    bank = (
        branch_output.groupby("year_month", as_index=False, observed=True)[additive_columns]
        .sum()
    )
    return bank[BANK_OUTPUT_COLUMNS]


def validate_bank_reconciliation(branch_output: pd.DataFrame, bank_output: pd.DataFrame) -> None:
    additive_columns = [
        col for col in BRANCH_OUTPUT_COLUMNS if col not in {"branch_id", "year_month"}
    ]
    summed = (
        branch_output.groupby("year_month", as_index=False, observed=True)[additive_columns]
        .sum()
        .sort_values("year_month")
        .reset_index(drop=True)
    )
    bank = bank_output.sort_values("year_month").reset_index(drop=True)

    if list(summed["year_month"]) != list(bank["year_month"]):
        raise AssertionError("Bank reconciliation failed: month coverage mismatch.")

    for col in additive_columns:
        left = pd.to_numeric(summed[col], errors="raise").to_numpy(dtype=float)
        right = pd.to_numeric(bank[col], errors="raise").to_numpy(dtype=float)
        max_diff = float(np.max(np.abs(left - right)))
        tolerance = 0.01 if col in MONETARY_COLUMNS else 0.0
        if max_diff > tolerance:
            raise AssertionError(f"Bank reconciliation failed for {col}: max diff={max_diff}")


# =============================================================================
# ROUNDING / OUTPUT
# =============================================================================

def finalize_branch_output(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame[BRANCH_OUTPUT_COLUMNS].copy()
    for col in COUNT_COLUMNS:
        result[col] = np.rint(pd.to_numeric(result[col], errors="raise")).astype("int64")
    for col in MONETARY_COLUMNS:
        result[col] = pd.to_numeric(result[col], errors="raise").round(2)
    return result.sort_values(["year_month", "branch_id"]).reset_index(drop=True)


# =============================================================================
# AUDIT REPORT
# =============================================================================

def safe_ratio(numerator: float, denominator: float) -> float:
    if abs(denominator) < 1e-12:
        return np.nan
    return float(numerator / denominator)


def print_audit(branch_output: pd.DataFrame, bank_output: pd.DataFrame) -> None:
    print("\n" + "=" * 84)
    print("BTYT BRANCH PERFORMANCE ENGINE — AUDIT")
    print("=" * 84)
    print(f"Branch-month rows: {len(branch_output):,}")
    print(f"Branches: {branch_output['branch_id'].nunique():,}")
    print(f"Months: {branch_output['year_month'].nunique():,}")
    print(f"Bank-month rows: {len(bank_output):,}")
    print(f"Reporting currency: {REPORTING_CURRENCY}-equivalent")

    bank = bank_output.copy()
    bank["year"] = bank["year_month"].str.slice(0, 4).astype(int)
    annual = (
        bank.groupby("year", as_index=False)
        .agg(
            average_deposits=("average_deposits", "mean"),
            average_loan_balance=("average_loan_balance", "mean"),
            interest_income=("interest_income", "sum"),
            interest_expense=("interest_expense", "sum"),
            fee_income=("fee_income", "sum"),
            total_revenue=("total_revenue", "sum"),
            total_operating_cost=("total_operating_cost", "sum"),
            credit_loss=("credit_loss", "sum"),
            pre_provision_profit=("pre_provision_profit", "sum"),
            net_income=("net_income", "sum"),
        )
    )
    annual["cost_to_income"] = annual["total_operating_cost"] / annual["total_revenue"].replace(0, np.nan)
    annual["credit_loss_ratio"] = annual["credit_loss"] / annual["average_loan_balance"].replace(0, np.nan)

    print("\nAnnual consolidated performance:")
    display = annual.copy()
    for col in [
        "average_deposits",
        "average_loan_balance",
        "interest_income",
        "interest_expense",
        "fee_income",
        "total_revenue",
        "total_operating_cost",
        "credit_loss",
        "pre_provision_profit",
        "net_income",
    ]:
        display[col] = display[col] / 1_000_000.0

    print(
        display[
            [
                "year",
                "average_deposits",
                "average_loan_balance",
                "total_revenue",
                "total_operating_cost",
                "credit_loss",
                "net_income",
                "cost_to_income",
                "credit_loss_ratio",
            ]
        ]
        .round(3)
        .to_string(index=False)
    )
    print("Monetary values above are UYU millions.")

    total_cost = branch_output["total_operating_cost"].sum()
    cost_mix = {
        "personnel": safe_ratio(branch_output["personnel_cost"].sum(), total_cost),
        "fixed": safe_ratio(branch_output["fixed_cost"].sum(), total_cost),
        "variable": safe_ratio(branch_output["variable_cost"].sum(), total_cost),
        "operational": safe_ratio(branch_output["operational_cost"].sum(), total_cost),
    }

    print("\nOperating cost composition:")
    for key, value in cost_mix.items():
        print(f"  {key:<14} {value:>8.2%}")

    audit_frame = branch_output.copy()
    audit_frame["cost_to_income"] = audit_frame["total_operating_cost"] / audit_frame["total_revenue"].replace(0, np.nan)
    valid_cti = audit_frame["cost_to_income"].replace([np.inf, -np.inf], np.nan).dropna()

    print("\nBranch-month cost-to-income:")
    if len(valid_cti):
        print(
            f"  median {valid_cti.median():.3f} | "
            f"P10 {valid_cti.quantile(0.10):.3f} | "
            f"P90 {valid_cti.quantile(0.90):.3f}"
        )

    negative_share = (audit_frame["net_income"] < 0).mean()
    print(f"\nNegative branch-month share: {negative_share:.2%}")

    branch_summary = (
        audit_frame.groupby("branch_id", as_index=False)
        .agg(
            total_revenue=("total_revenue", "sum"),
            total_operating_cost=("total_operating_cost", "sum"),
            credit_loss=("credit_loss", "sum"),
            net_income=("net_income", "sum"),
            negative_months=("net_income", lambda s: int((s < 0).sum())),
        )
    )
    persistent_loss = branch_summary[branch_summary["negative_months"] >= 36]
    print(f"Persistent loss-making branches (>=36 negative months): {len(persistent_loss):,}")

    top = branch_summary.sort_values("net_income", ascending=False).head(5).copy()
    bottom = branch_summary.sort_values("net_income", ascending=True).head(5).copy()
    top["net_income_m"] = top["net_income"] / 1_000_000.0
    bottom["net_income_m"] = bottom["net_income"] / 1_000_000.0

    print("\nTop 5 branches by cumulative net income:")
    print(top[["branch_id", "net_income_m", "negative_months"]].round(1).to_string(index=False))
    print("\nBottom 5 branches by cumulative net income:")
    print(bottom[["branch_id", "net_income_m", "negative_months"]].round(1).to_string(index=False))

    active_customer_den = audit_frame["active_customers"].replace(0, np.nan)
    tx_den = audit_frame["transaction_count"].replace(0, np.nan)
    revenue_per_customer = (audit_frame["total_revenue"] / active_customer_den).replace([np.inf, -np.inf], np.nan)
    cost_per_customer = (audit_frame["total_operating_cost"] / active_customer_den).replace([np.inf, -np.inf], np.nan)
    cost_per_transaction = (audit_frame["total_operating_cost"] / tx_den).replace([np.inf, -np.inf], np.nan)

    print("\nEfficiency diagnostics — branch-month medians:")
    print(f"  revenue/customer      UYU {revenue_per_customer.median():,.2f}")
    print(f"  cost/customer         UYU {cost_per_customer.median():,.2f}")
    print(f"  cost/transaction      UYU {cost_per_transaction.median():,.2f}")

    total_revenue = audit_frame["total_revenue"].sum()
    total_nii = audit_frame["net_interest_income"].sum()
    total_fee = audit_frame["fee_income"].sum()
    total_credit_loss = audit_frame["credit_loss"].sum()
    average_portfolio = bank_output["average_loan_balance"].mean()

    print("\nRevenue and risk composition:")
    print(f"  NII / revenue         {safe_ratio(total_nii, total_revenue):.2%}")
    print(f"  Fee income / revenue  {safe_ratio(total_fee, total_revenue):.2%}")
    print(
        "  Annualized credit loss / avg portfolio "
        f"{safe_ratio(total_credit_loss / len(YEARS), average_portfolio):.2%}"
    )

    print("\nReconciliation:")
    print("  SUM(branch_monthly_performance) == bank_monthly_performance   PASS")
    print("\nVALIDATION: PASS")


# =============================================================================
# MAIN
# =============================================================================

def main() -> None:
    print("=" * 84)
    print("BTYT BRANCH PERFORMANCE ENGINE")
    print("=" * 84)

    print("Loading frozen canonical inputs...")
    data = normalize_inputs(load_inputs())
    validate_inputs(data)

    print(f"Branches: {len(data['branches']):,}")
    print(f"Accounts: {len(data['accounts']):,}")
    print(f"Cards: {len(data['cards']):,}")
    print(f"Loans: {len(data['loans']):,}")
    print(f"Loan snapshot rows: {len(data['loan_snapshot']):,}")
    print(f"Loan lifecycle bridge rows: {len(data['loan_lifecycle_bridge']):,}")
    print(f"Account-month balance rows: {len(data['account_balances']):,}")
    print(f"Branch-year states: {len(data['branch_state']):,}")

    print("\nBuilding monthly branch economics...")
    raw = assemble_performance(data)
    branch_output = finalize_branch_output(raw)

    bank_output = build_bank_output(branch_output)
    for col in COUNT_COLUMNS:
        bank_output[col] = np.rint(pd.to_numeric(bank_output[col], errors="raise")).astype("int64")
    for col in MONETARY_COLUMNS:
        bank_output[col] = pd.to_numeric(bank_output[col], errors="raise").round(2)

    validate_branch_output(branch_output, data["branches"])
    validate_bank_reconciliation(branch_output, bank_output)

    DATA_GENERATED.mkdir(parents=True, exist_ok=True)
    branch_output.to_csv(BRANCH_OUTPUT_PATH, index=False)
    bank_output.to_csv(BANK_OUTPUT_PATH, index=False)

    print_audit(branch_output, bank_output)

    print("\nSaved:")
    print(f"  {BRANCH_OUTPUT_PATH}")
    print(f"  shape = {branch_output.shape}")
    print(f"  {BANK_OUTPUT_PATH}")
    print(f"  shape = {bank_output.shape}")


if __name__ == "__main__":
    main()
