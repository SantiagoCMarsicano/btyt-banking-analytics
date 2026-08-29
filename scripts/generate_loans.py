from __future__ import annotations

"""
BTYT Banking Analytics
Definitive loan master generator

Creates canonical output:
    data/processed/loans.csv

Also creates an INTERNAL bridge (not an analytical table):
    data/interim/loan_lifecycle_bridge.csv

Canonical sources:
    database/loans_data_dictionary.md
    database/loan_monthly_snapshot_data_dictionary.md
    data/processed/products.csv (fallback: data/raw/products.csv)

Design principles
--------------------
1) The products catalog is the source of truth for launch_year,
   target_customer_type and catalog currency. No duplicated hard-coded
   product metadata is allowed to override it.
2) 2021-2026 is the detailed observational window.
3) Pre-2021 history is compressed inherited state, not a fabricated
   monthly biography.
4) Loan demand, capacity and repayment vulnerability are distinct,
   correlated stochastic concepts.
5) Final loan_status is derived from a lifecycle process, never sampled
   directly as an independent label.
6) Exact hidden origination month and a monthly lifecycle are used from
   2021 onward so each contract receives its true exposure time.
7) Scheduled maturity and early prepayment are product/term/age aware.
   Long loans cannot routinely disappear during their first year.
8) Default recognition requires deterioration persistence; a single bad
   draw cannot instantaneously create DEFAULTED.
9) Customer closure does not mechanically force loan payoff.
10) P016 is a revolving facility: original_amount is the approved limit,
    term_months is a facility horizon rather than an amortization term.
11) USD payment burden is converted to a synthetic UYU equivalent before
    comparison with UYU income/revenue proxies.
12) Output schema remains exactly the 12 canonical loans columns.
13) Internal lifecycle timing/seed is stored separately so the later
    monthly-snapshot engine can reconcile with this master table.

Important:
- Macro, FX and nominal-scale curves are synthetic model inputs, not
  official Uruguayan historical series.
- This generator does not export loan_monthly_snapshot. That table should use
  an exact contractual ledger, due dates, payments, arrears and DPD.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd


# =============================================================================
# Configuration
# =============================================================================

SEED = 20260827
LOAN_SEED = SEED + 12012

CURRENT_YEAR = 2026
CURRENT_MONTH = 12
OBSERVATION_START_YEAR = 2021

DEVELOPMENT_MODE = True
DEVELOPMENT_CUSTOMERS = 10_000

ROOT = Path(__file__).resolve().parents[1]
DATA_PROCESSED = ROOT / "data" / "processed"
DATA_RAW = ROOT / "data" / "raw"
DATA_INTERIM = ROOT / "data" / "interim"

CUSTOMERS_PATH = DATA_PROCESSED / "customers.csv"
ACCOUNTS_PATH = DATA_PROCESSED / "accounts.csv"

BRANCHES_PATHS = [
    DATA_PROCESSED / "branches.csv",
    DATA_RAW / "branches.csv",
]
PRODUCTS_PATHS = [
    DATA_PROCESSED / "products.csv",
    DATA_RAW / "products.csv",
]

OUTPUT_PATH = DATA_PROCESSED / "loans.csv"
BRIDGE_PATH = DATA_INTERIM / "loan_lifecycle_bridge.csv"

LOAN_COLUMNS = [
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

BRIDGE_COLUMNS = [
    "loan_id",
    "origination_month_internal",
    "lifecycle_seed",
    "resolution_month_internal",
    "terminal_event_internal",
    "pre2021_inherited_state",
]


# =============================================================================
# Behavioral product configuration
# =============================================================================

@dataclass(frozen=True)
class LoanBehavior:
    """
    Behavioral parameters only.

    launch_year, target_customer_type and catalog currency intentionally
    do NOT live here; they are read from products.csv.
    """
    product_id: str
    kind: str
    amount_median_uyu_2026: float
    amount_sigma: float
    term_options: Tuple[int, ...]
    fixed_weight: float
    variable_weight: float
    mixed_weight: float
    usd_base_if_multi: float
    demand_intercept: float
    monthly_prepay_base: float
    prepay_min_age_months: int


BEHAVIOR: Dict[str, LoanBehavior] = {
    "P012": LoanBehavior(
        "P012", "INSTALLMENT", 260_000, 0.75,
        (6, 12, 18, 24, 36, 48, 60),
        0.78, 0.16, 0.06, 0.03, -2.15,
        0.0030, 3,
    ),
    "P013": LoanBehavior(
        "P013", "INSTALLMENT", 1_050_000, 0.55,
        (24, 36, 48, 60, 72),
        0.55, 0.30, 0.15, 0.32, -3.00,
        0.0015, 6,
    ),
    "P014": LoanBehavior(
        "P014", "INSTALLMENT", 4_800_000, 0.60,
        (60, 120, 180, 240, 300),
        0.28, 0.42, 0.30, 0.20, -4.40,
        0.00025, 12,
    ),
    "P015": LoanBehavior(
        "P015", "INSTALLMENT", 2_000_000, 0.85,
        (12, 24, 36, 48, 60, 84),
        0.45, 0.38, 0.17, 0.32, -2.20,
        0.0022, 4,
    ),
    "P016": LoanBehavior(
        "P016", "REVOLVING", 3_500_000, 0.90,
        (12, 24, 36),
        0.20, 0.62, 0.18, 0.46, -2.65,
        0.0000, 0,
    ),
    "P017": LoanBehavior(
        "P017", "INSTALLMENT", 4_000_000, 0.95,
        (12, 24, 36, 48, 60, 84, 120),
        0.25, 0.53, 0.22, 0.56, -3.05,
        0.0015, 6,
    ),
    "P018": LoanBehavior(
        "P018", "INSTALLMENT", 3_200_000, 0.75,
        (24, 36, 48, 60, 72, 84),
        0.42, 0.38, 0.20, 0.48, -3.25,
        0.0010, 6,
    ),
}

PRODUCT_SPREAD = {
    "P012": 8.5,
    "P013": 5.0,
    "P014": 3.0,
    "P015": 5.5,
    "P016": 4.8,
    "P017": 4.0,
    "P018": 4.6,
}


# =============================================================================
# Synthetic macro anchors
# =============================================================================
# These anchors are model inputs only; they do not claim to reproduce official
# historical series.

UYU_RATE_ANCHORS = {
    1969: 28.0, 1975: 34.0, 1980: 41.0, 1985: 49.0, 1990: 44.0,
    1995: 34.0, 1998: 31.0, 1999: 29.0, 2000: 27.0, 2001: 30.0,
    2002: 43.0, 2003: 35.0, 2004: 25.0, 2005: 19.0, 2006: 16.0,
    2007: 14.0, 2008: 15.5, 2009: 13.0, 2010: 12.0, 2011: 11.5,
    2012: 12.0, 2013: 12.5, 2014: 13.0, 2015: 14.5, 2016: 15.0,
    2017: 13.5, 2018: 13.0, 2019: 12.5, 2020: 10.5, 2021: 10.0,
    2022: 12.5, 2023: 14.0, 2024: 12.5, 2025: 11.5, 2026: 11.0,
}

USD_RATE_ANCHORS = {
    1969: 8.0, 1975: 9.0, 1980: 11.0, 1985: 13.0, 1990: 11.5,
    1995: 10.0, 1998: 10.0, 1999: 9.7, 2000: 9.4, 2001: 10.2,
    2002: 12.5, 2003: 10.5, 2004: 8.5, 2005: 7.8, 2006: 7.2,
    2007: 7.0, 2008: 7.8, 2009: 6.8, 2010: 6.2, 2011: 6.0,
    2012: 6.1, 2013: 6.2, 2014: 6.4, 2015: 6.8, 2016: 6.7,
    2017: 6.3, 2018: 6.4, 2019: 6.1, 2020: 5.4, 2021: 5.2,
    2022: 6.1, 2023: 7.3, 2024: 7.1, 2025: 6.8, 2026: 6.5,
}

FX_UYU_PER_USD_ANCHORS = {
    1993: 4.5, 1995: 6.5, 1998: 10.5, 2000: 12.1, 2002: 21.5,
    2004: 28.0, 2006: 24.0, 2008: 20.5, 2010: 20.0, 2012: 20.5,
    2014: 23.5, 2016: 30.5, 2018: 30.7, 2020: 42.0, 2022: 41.0,
    2024: 39.5, 2026: 42.0,
}

MACRO_STRESS_BY_YEAR = {
    2021: 0.12,
    2022: 0.14,
    2023: 0.08,
    2024: 0.03,
    2025: 0.00,
    2026: -0.03,
}

DEMAND_MACRO_BY_YEAR = {
    2020: -0.35,
    2021: -0.10,
    2022: 0.10,
    2023: 0.05,
    2024: 0.14,
    2025: 0.18,
    2026: 0.20,
}


# =============================================================================
# Mathematical helpers
# =============================================================================

def sigmoid(x):
    x = np.clip(x, -35, 35)
    return 1.0 / (1.0 + np.exp(-x))


def softmax(values: np.ndarray) -> np.ndarray:
    values = np.asarray(values, dtype=float)
    values = values - np.max(values)
    expv = np.exp(values)
    return expv / expv.sum()


def zscore_log1p(series: pd.Series) -> pd.Series:
    s = pd.to_numeric(series, errors="coerce")
    logged = np.log1p(s.clip(lower=0))
    mean = logged.mean()
    std = logged.std(ddof=0)
    if not np.isfinite(std) or std == 0:
        return pd.Series(np.zeros(len(series)), index=series.index)
    return (logged - mean) / std


def interpolate_anchor(year: int, anchors: Dict[int, float]) -> float:
    years = np.array(sorted(anchors), dtype=float)
    values = np.array([anchors[int(y)] for y in years], dtype=float)
    return float(np.interp(float(year), years, values))


def base_rate(currency: str, year: int) -> float:
    anchors = UYU_RATE_ANCHORS if currency == "UYU" else USD_RATE_ANCHORS
    return interpolate_anchor(year, anchors)


def synthetic_fx_uyu_per_usd(year: int) -> float:
    # For pre-1993 contracts, use the earliest normalized UYU-equivalent anchor.
    return interpolate_anchor(max(year, 1993), FX_UYU_PER_USD_ANCHORS)


def nominal_scale_to_2026(year: int) -> float:
    """
    Synthetic nominal scale relative to 2026.

    Keeps old contractual amounts from looking like 2026 nominal pesos while
    deliberately avoiding any claim of being an official CPI reconstruction.
    The floor also avoids absurdly tiny values for very old inherited contracts.
    """
    if year >= 2026:
        return 1.0
    if year >= 2000:
        return float(np.exp(-0.055 * (2026 - year)))
    if year >= 1990:
        return float(max(0.10, np.exp(-0.055 * 26) * np.exp(-0.070 * (2000 - year))))
    return 0.10


def first_existing(paths: List[Path]) -> Path:
    for path in paths:
        if path.exists():
            return path
    raise FileNotFoundError(
        "Could not locate any of:\n" + "\n".join(str(p) for p in paths)
    )


def round_money(value: float) -> float:
    value = max(float(value), 1.0)
    if value < 10_000:
        base = 100
    elif value < 100_000:
        base = 1_000
    elif value < 1_000_000:
        base = 5_000
    elif value < 10_000_000:
        base = 10_000
    else:
        base = 50_000
    return float(round(value / base) * base)


def period_add_months(period: pd.Period, months: int) -> pd.Period:
    return period + int(months)


def period_months_inclusive(start: pd.Period, end: pd.Period) -> int:
    return int(end.ordinal - start.ordinal + 1)


# =============================================================================
# Input loading and validation
# =============================================================================

def load_inputs():
    customers = pd.read_csv(
        CUSTOMERS_PATH,
        dtype={"customer_id": str, "primary_branch_id": str},
    )
    accounts = pd.read_csv(
        ACCOUNTS_PATH,
        dtype={
            "account_id": str,
            "customer_id": str,
            "product_id": str,
            "branch_id": str,
        },
    )

    branches_path = first_existing(BRANCHES_PATHS)
    products_path = first_existing(PRODUCTS_PATHS)

    branches = pd.read_csv(branches_path, dtype={"branch_id": str})
    products = pd.read_csv(products_path, dtype={"product_id": str})

    if DEVELOPMENT_MODE and len(customers) > DEVELOPMENT_CUSTOMERS:
        customers = (
            customers.sample(n=DEVELOPMENT_CUSTOMERS, random_state=SEED)
            .sort_values("customer_id")
            .reset_index(drop=True)
        )

    customer_ids = set(customers["customer_id"])
    accounts = accounts[accounts["customer_id"].isin(customer_ids)].copy()

    customers["primary_branch_id"] = (
        customers["primary_branch_id"].astype(str).str.zfill(3)
    )
    accounts["branch_id"] = accounts["branch_id"].astype(str).str.zfill(3)
    branches["branch_id"] = branches["branch_id"].astype(str).str.zfill(3)

    return customers, accounts, branches, products


def validate_inputs(customers, accounts, branches, products):
    required_customers = {
        "customer_id", "customer_type", "primary_branch_id", "registration_year",
        "customer_status", "closing_year", "monthly_income", "employment_status",
        "annual_revenue", "company_size", "business_sector", "birth_year",
        "residence_department",
    }
    missing = required_customers - set(customers.columns)
    if missing:
        raise ValueError(f"customers.csv missing columns: {sorted(missing)}")

    required_accounts = {
        "account_id", "customer_id", "product_id", "branch_id",
        "opening_year", "account_status", "opening_channel",
    }
    missing = required_accounts - set(accounts.columns)
    if missing:
        raise ValueError(f"accounts.csv missing columns: {sorted(missing)}")

    required_branches = {
        "branch_id", "opening_year", "status", "department", "region", "branch_size"
    }
    missing = required_branches - set(branches.columns)
    if missing:
        raise ValueError(f"branches.csv missing columns: {sorted(missing)}")

    required_products = {
        "product_id", "product_name", "product_family", "currency",
        "target_customer_type", "launch_year",
    }
    missing = required_products - set(products.columns)
    if missing:
        raise ValueError(f"products.csv missing columns: {sorted(missing)}")

    lending = products[products["product_id"].isin(BEHAVIOR)].copy()
    missing_ids = set(BEHAVIOR) - set(lending["product_id"])
    if missing_ids:
        raise ValueError(
            f"products.csv does not contain required lending products: {sorted(missing_ids)}"
        )

    duplicate = lending["product_id"].duplicated()
    if duplicate.any():
        raise ValueError("Duplicate lending product_id in products.csv.")

    bad_family = ~lending["product_family"].isin(
        ["RETAIL_LENDING", "BUSINESS_LENDING"]
    )
    if bad_family.any():
        vals = lending.loc[bad_family, ["product_id", "product_family"]]
        raise ValueError(f"Invalid lending family:\n{vals}")

    bad_target = ~lending["target_customer_type"].isin(
        ["INDIVIDUAL", "BUSINESS", "BOTH"]
    )
    if bad_target.any():
        raise ValueError("Invalid target_customer_type in lending catalog.")

    bad_currency = ~lending["currency"].isin(["UYU", "USD", "MULTI"])
    if bad_currency.any():
        raise ValueError("Invalid currency in lending catalog.")


# =============================================================================
# Generator
# =============================================================================

class LoanGenerator:
    def __init__(self, customers, accounts, branches, products):
        self.customers = customers.copy()
        self.accounts = accounts.copy()
        self.branches = branches.copy()
        self.products = products.copy()

        self.rng = np.random.default_rng(LOAN_SEED)
        self.rows = []
        self.bridge_rows = []
        self.next_loan_number = 1

        self.branch_lookup = self.branches.set_index("branch_id").to_dict("index")
        self.product_lookup = (
            self.products[self.products["product_id"].isin(BEHAVIOR)]
            .set_index("product_id")
            .to_dict("index")
        )

        self._prepare_customer_signals()

    # ---------------------------------------------------------------------
    # Catalog helpers
    # ---------------------------------------------------------------------

    def _launch_year(self, product_id: str) -> int:
        return int(self.product_lookup[product_id]["launch_year"])

    def _catalog_target(self, product_id: str) -> str:
        return str(self.product_lookup[product_id]["target_customer_type"])

    def _catalog_currency(self, product_id: str) -> str:
        return str(self.product_lookup[product_id]["currency"])

    def _compatible(self, customer_type: str, product_id: str) -> bool:
        target = self._catalog_target(product_id)
        return target == "BOTH" or target == customer_type

    # ---------------------------------------------------------------------
    # Customer signals
    # ---------------------------------------------------------------------

    def _prepare_customer_signals(self):
        c = self.customers.copy()

        c["_income_z"] = zscore_log1p(c["monthly_income"])
        c["_revenue_z"] = zscore_log1p(c["annual_revenue"])

        account_summary = (
            self.accounts.groupby("customer_id")
            .agg(
                account_count=("account_id", "size"),
                active_account_count=("account_status", lambda x: (x == "ACTIVE").sum()),
                product_breadth=("product_id", "nunique"),
                usd_accounts=("product_id", lambda x: x.isin(["P002", "P004", "P008"]).sum()),
                digital_accounts=("opening_channel", lambda x: (x == "DIGITAL").sum()),
            )
            .reset_index()
        )

        c = c.merge(account_summary, on="customer_id", how="left")
        for col in [
            "account_count", "active_account_count", "product_breadth",
            "usd_accounts", "digital_accounts",
        ]:
            c[col] = c[col].fillna(0)

        c["usd_share"] = np.where(
            c["account_count"] > 0,
            c["usd_accounts"] / c["account_count"],
            0.0,
        )
        c["digital_share"] = np.where(
            c["account_count"] > 0,
            c["digital_accounts"] / c["account_count"],
            0.0,
        )

        # Correlated latent structure:
        # one common factor + idiosyncratic factors.
        common_noise = self.rng.normal(0, 1, len(c))
        specific_noise = self.rng.normal(0, 1, (len(c), 5))

        tenure = (
            CURRENT_YEAR - pd.to_numeric(c["registration_year"], errors="coerce")
        ).clip(lower=0)
        tenure_std = max(float(tenure.std(ddof=0)), 1.0)
        tenure_z = (tenure - tenure.mean()) / tenure_std

        relation_score = (
            0.38 * np.log1p(c["account_count"])
            + 0.28 * np.log1p(c["active_account_count"])
            + 0.24 * np.log1p(c["product_breadth"])
            + 0.16 * tenure_z
            + 0.33 * common_noise
            + 0.34 * specific_noise[:, 0]
        )
        c["_relationship"] = sigmoid(relation_score)

        age_now = (
            CURRENT_YEAR
            - pd.to_numeric(c["birth_year"], errors="coerce").fillna(1980)
        )
        digital_score = (
            1.35 * c["digital_share"]
            + 0.18 * np.maximum(0, 45 - age_now) / 20
            + 0.24 * common_noise
            + 0.55 * specific_noise[:, 1]
        )
        c["_digital_affinity"] = sigmoid(digital_score)

        usd_score = (
            1.55 * c["usd_share"]
            + 0.28 * c["_income_z"].fillna(0)
            + 0.34 * c["_revenue_z"].fillna(0)
            + 0.24 * common_noise
            + 0.60 * specific_noise[:, 2]
        )
        c["_usd_affinity"] = sigmoid(usd_score)

        indiv_capacity = (
            0.72 * c["_income_z"].fillna(0)
            + 0.36 * c["_relationship"]
            + 0.18 * tenure_z
            + 0.25 * common_noise
            + 0.52 * specific_noise[:, 3]
        )
        business_capacity = (
            0.78 * c["_revenue_z"].fillna(0)
            + 0.28 * c["_relationship"]
            + 0.20 * tenure_z
            + 0.25 * common_noise
            + 0.52 * specific_noise[:, 3]
        )
        c["_capacity"] = np.where(
            c["customer_type"].eq("INDIVIDUAL"),
            sigmoid(indiv_capacity),
            sigmoid(business_capacity),
        )

        employment_effect = c["employment_status"].map({
            "EMPLOYED": 0.28,
            "SELF_EMPLOYED": 0.32,
            "RETIRED": -0.05,
            "STUDENT": -0.18,
            "UNEMPLOYED": -0.35,
            "OTHER": -0.08,
        }).fillna(0)

        demand_score = (
            -0.15
            + 0.48 * c["_relationship"]
            + 0.22 * tenure_z
            + np.where(c["customer_type"].eq("INDIVIDUAL"), employment_effect, 0)
            + 0.20 * common_noise
            + 0.85 * specific_noise[:, 4]
        )
        c["_loan_demand"] = sigmoid(demand_score)

        # Persistent vulnerability, deliberately noisy and not a deterministic
        # target/default score.
        stress_noise = self.rng.normal(0, 1, len(c))
        financial_strength = np.where(
            c["customer_type"].eq("INDIVIDUAL"),
            c["_income_z"].fillna(0),
            c["_revenue_z"].fillna(0),
        )
        c["_stress_propensity"] = sigmoid(
            -0.55 * financial_strength
            - 0.30 * c["_relationship"]
            + 0.95 * stress_noise
        )

        self.customers = c

    # ---------------------------------------------------------------------
    # Demand / origination
    # ---------------------------------------------------------------------

    def _product_utility(self, row, behavior: LoanBehavior, year: int) -> float:
        utility = (
            behavior.demand_intercept
            + 1.20 * row["_loan_demand"]
            + 0.88 * row["_capacity"]
            + 0.44 * row["_relationship"]
            + self.rng.normal(0, 0.70)
        )

        pid = behavior.product_id

        if pid == "P012":
            utility += 0.25

        elif pid == "P013":
            # Auto lending is catalog-compatible with BOTH. Business customers
            # can use it, but SME/fleet financing remains less common than retail.
            utility += 0.28 * row["_capacity"]
            if row["customer_type"] == "BUSINESS":
                utility -= 0.40

        elif pid == "P014":
            # Age must be age AT ORIGINATION, not age in 2026.
            if pd.notna(row["birth_year"]):
                age_at_origination = year - int(row["birth_year"])
            else:
                age_at_origination = 40
            age_hump = np.exp(-((age_at_origination - 38) / 15) ** 2)
            utility += 0.75 * row["_capacity"] + 0.65 * age_hump

        elif pid == "P015":
            utility += 0.30 * row["_capacity"]

        elif pid == "P016":
            utility += 0.52 * row["_relationship"] + 0.38 * row["_capacity"]

        elif pid == "P017":
            sector = str(row.get("business_sector", "")).upper()
            agro = any(
                token in sector
                for token in ["AGRI", "GANAD", "RURAL", "FOREST"]
            )
            utility += 1.15 if agro else -0.65

        elif pid == "P018":
            size = str(row.get("company_size", "")).upper()
            utility += {
                "MICRO": -0.20,
                "SMALL": 0.15,
                "MEDIUM": 0.50,
                "LARGE": 0.75,
            }.get(size, 0.0)

        utility += DEMAND_MACRO_BY_YEAR.get(year, 0.0)
        return float(utility)

    def _annual_product_probability(
        self,
        row,
        behavior: LoanBehavior,
        year: int,
    ) -> float:
        utility = self._product_utility(row, behavior, year)
        return float(np.clip(sigmoid(utility) * 0.27, 0.002, 0.28))

    # ---------------------------------------------------------------------
    # Branch
    # ---------------------------------------------------------------------

    def _eligible_branches(self, year: int) -> pd.DataFrame:
        b = self.branches.copy()
        b["opening_year"] = pd.to_numeric(b["opening_year"], errors="coerce")
        b = b[b["opening_year"] <= year]

        if "closing_year" in b.columns:
            closing = pd.to_numeric(b["closing_year"], errors="coerce")
            b = b[closing.isna() | (closing >= year)]

        return b

    def _choose_branch(self, row, product_id: str, year: int) -> str:
        eligible = self._eligible_branches(year)
        if eligible.empty:
            raise RuntimeError(f"No branches eligible in {year}")

        primary = str(row["primary_branch_id"]).zfill(3)
        weights = np.ones(len(eligible), dtype=float)

        weights *= np.where(eligible["branch_id"].eq(primary), 4.6, 1.0)

        cust_dept = str(row.get("residence_department", ""))
        weights *= np.where(
            eligible["department"].astype(str).eq(cust_dept),
            2.0,
            1.0,
        )

        if primary in self.branch_lookup:
            primary_region = str(self.branch_lookup[primary].get("region", ""))
            weights *= np.where(
                eligible["region"].astype(str).eq(primary_region),
                1.35,
                1.0,
            )

        size_factor = (
            eligible["branch_size"].astype(str).str.upper().map({
                "SMALL": 0.90,
                "MEDIUM": 1.10,
                "LARGE": 1.35,
            }).fillna(1.0).to_numpy()
        )
        weights *= size_factor

        if product_id == "P017":
            interior = ~eligible["department"].astype(str).eq("Montevideo")
            weights *= np.where(interior, 1.35, 0.75)
            weights *= np.where(
                eligible["region"].astype(str).str.upper().eq("EAST"),
                1.22,
                1.0,
            )

        if product_id in {"P015", "P016", "P018"}:
            weights *= np.where(
                eligible["branch_size"].astype(str).str.upper().eq("LARGE"),
                1.18,
                1.0,
            )

        # Digital affinity weakens geographic concentration rather than
        # deleting geography.
        if row["_digital_affinity"] > 0.65:
            weights = np.power(weights, 0.78)

        weights *= self.rng.lognormal(0.0, 0.18, len(weights))
        weights /= weights.sum()

        return str(self.rng.choice(eligible["branch_id"].to_numpy(), p=weights))

    # ---------------------------------------------------------------------
    # Contract characteristics
    # ---------------------------------------------------------------------

    def _choose_currency(self, row, behavior: LoanBehavior) -> str:
        catalog_currency = self._catalog_currency(behavior.product_id)

        if catalog_currency in {"UYU", "USD"}:
            return catalog_currency

        # MULTI only.
        p_usd = behavior.usd_base_if_multi
        p_usd += 0.28 * (row["_usd_affinity"] - 0.5)

        if row["customer_type"] == "BUSINESS":
            sector = str(row.get("business_sector", "")).upper()
            if any(
                token in sector
                for token in ["AGRI", "GANAD", "FOREST", "EXPORT"]
            ):
                p_usd += 0.12

            if behavior.product_id == "P013":
                p_usd += 0.05

        p_usd = float(np.clip(p_usd, 0.01, 0.88))
        return "USD" if self.rng.random() < p_usd else "UYU"

    def _amount(
        self,
        row,
        behavior: LoanBehavior,
        currency: str,
        year: int,
    ) -> float:
        if row["customer_type"] == "INDIVIDUAL":
            economic_z = (
                float(row["_income_z"])
                if pd.notna(row["_income_z"])
                else 0.0
            )
        else:
            economic_z = (
                float(row["_revenue_z"])
                if pd.notna(row["_revenue_z"])
                else 0.0
            )

        log_shift = (
            0.34 * economic_z
            + 0.34 * (row["_capacity"] - 0.5)
            + 0.14 * (row["_relationship"] - 0.5)
            + self.rng.normal(0, behavior.amount_sigma)
        )

        # Generate a real 2026-UYU-equivalent size, then map to a synthetic
        # historical nominal contractual scale.
        real_uyu_2026 = behavior.amount_median_uyu_2026 * np.exp(log_shift)
        real_uyu_2026 = np.clip(real_uyu_2026, 25_000, 150_000_000)

        nominal_uyu = real_uyu_2026 * nominal_scale_to_2026(year)

        if currency == "USD":
            amount = nominal_uyu / synthetic_fx_uyu_per_usd(year)
        else:
            amount = nominal_uyu

        return round_money(float(max(amount, 1_000)))

    def _amount_uyu_equivalent(
        self,
        amount: float,
        currency: str,
        year: int,
    ) -> float:
        if currency == "USD":
            return float(amount) * synthetic_fx_uyu_per_usd(year)
        return float(amount)

    def _choose_term(
        self,
        row,
        behavior: LoanBehavior,
        amount: float,
        currency: str,
        year: int,
    ) -> int:
        options = np.array(behavior.term_options, dtype=int)
        pos = np.linspace(-1.0, 1.0, len(options))

        # Compare on the same real-UYU scale. V2 compared USD numeric amounts
        # directly with a UYU median, which biased USD contracts toward short terms.
        amount_uyu = self._amount_uyu_equivalent(amount, currency, year)
        real_amount_2026 = amount_uyu / max(nominal_scale_to_2026(year), 1e-6)

        log_ratio = np.log(
            max(real_amount_2026, 1.0)
            / max(behavior.amount_median_uyu_2026, 1.0)
        )

        score = 0.35 * pos * log_ratio
        score += self.rng.normal(0, 0.22, len(options))

        if behavior.product_id == "P016":
            score += np.array([0.45, 0.15, -0.10])

        probs = softmax(score)
        return int(self.rng.choice(options, p=probs))

    def _choose_rate_type(
        self,
        row,
        behavior: LoanBehavior,
        currency: str,
        term: int,
    ) -> str:
        weights = np.array([
            behavior.fixed_weight,
            behavior.variable_weight,
            behavior.mixed_weight,
        ], dtype=float)

        if term >= 120:
            weights *= np.array([0.78, 1.16, 1.22])
        if currency == "USD":
            weights *= np.array([0.90, 1.12, 1.04])

        weights *= self.rng.lognormal(0, 0.10, 3)
        weights /= weights.sum()

        return str(
            self.rng.choice(["FIXED", "VARIABLE", "MIXED"], p=weights)
        )

    def _initial_rate(
        self,
        row,
        behavior: LoanBehavior,
        year: int,
        currency: str,
        term: int,
        rate_type: str,
    ) -> float:
        base = base_rate(currency, year)
        spread = PRODUCT_SPREAD[behavior.product_id]

        capacity_adjustment = -2.0 * (row["_capacity"] - 0.5)
        relationship_adjustment = -0.9 * (row["_relationship"] - 0.5)
        term_adjustment = 0.55 * np.log1p(term / 12)
        type_adjustment = {
            "FIXED": 0.45,
            "VARIABLE": -0.20,
            "MIXED": 0.10,
        }[rate_type]
        noise = self.rng.normal(0, 1.15 if currency == "UYU" else 0.65)

        rate = (
            base
            + spread
            + capacity_adjustment
            + relationship_adjustment
            + term_adjustment
            + type_adjustment
            + noise
        )
        return round(float(np.clip(rate, 2.0, 65.0)), 2)

    # ---------------------------------------------------------------------
    # Lifecycle mathematics
    # ---------------------------------------------------------------------

    @staticmethod
    def _monthly_payment(
        principal: float,
        annual_rate_pct: float,
        months: int,
    ) -> float:
        if months <= 0:
            return float(principal)
        r = annual_rate_pct / 100 / 12
        if r <= 0:
            return float(principal) / months
        return float(principal) * r / (1 - (1 + r) ** (-months))

    def _payment_burden(
        self,
        row,
        behavior: LoanBehavior,
        amount: float,
        currency: str,
        term_months: int,
        initial_rate: float,
        origination_year: int,
    ) -> float:
        if behavior.kind == "REVOLVING":
            # Utilization is not yet generated in the master table; use a noisy
            # exposure proxy rather than pretending the full approved limit is due.
            return float(0.08 + 0.18 * self.rng.random())

        scheduled = self._monthly_payment(
            amount,
            initial_rate,
            term_months,
        )

        # Income/revenue fields are UYU-scale proxies. Convert USD obligation
        # before comparing so numerator and denominator use compatible units.
        scheduled_uyu = (
            scheduled * synthetic_fx_uyu_per_usd(origination_year)
            if currency == "USD"
            else scheduled
        )

        # Contract amounts before 2021 are represented on their historical
        # nominal scale, while income/revenue are current cross-sectional
        # capacity proxies. Convert the contractual obligation to a
        # 2026-equivalent scale before computing burden. This preserves unit
        # consistency without fabricating a full historical income biography.
        scale = max(nominal_scale_to_2026(origination_year), 1e-6)
        scheduled_uyu_2026eq = scheduled_uyu / scale

        if row["customer_type"] == "INDIVIDUAL":
            income = max(float(row.get("monthly_income") or 0), 1.0)
            return float(scheduled_uyu_2026eq / income)

        annual_revenue = max(float(row.get("annual_revenue") or 0), 1.0)
        return float((scheduled_uyu_2026eq * 12) / annual_revenue)

    def _stress_index(
        self,
        row,
        burden: float,
        currency: str,
        initial_rate: float,
        rng: np.random.Generator,
    ) -> float:
        # Centered latent index, not a risk score and never exported.
        return float(
            1.35 * (row["_stress_propensity"] - 0.5)
            + 0.55 * np.log1p(np.clip(burden, 0, 4))
            + 0.10 * (currency == "USD")
            + 0.10 * (initial_rate / 25.0)
            - 0.25 * (row["_capacity"] - 0.5)
            - 0.15 * (row["_relationship"] - 0.5)
            + rng.normal(0, 0.22)
        )

    def _compressed_pre2021_resolution(
        self,
        row,
        behavior: LoanBehavior,
        origination_period: pd.Period,
        maturity_period: pd.Period,
        stress_index: float,
        rng: np.random.Generator,
    ) -> Tuple[str, Optional[pd.Period], str]:
        """
        Compressed inherited history for contracts that fully resolve before 2021.

        We do not fabricate monthly payment histories here. A cumulative adverse
        probability is generated from exposure length and borrower vulnerability.
        """
        years_exposed = max(
            1.0,
            period_months_inclusive(origination_period, maturity_period) / 12,
        )

        annual_adverse = float(
            np.clip(
                sigmoid(-4.15 + 1.55 * stress_index + rng.normal(0, 0.25)),
                0.002,
                0.12,
            )
        )
        p_any_adverse = 1 - (1 - annual_adverse) ** years_exposed

        if rng.random() >= p_any_adverse:
            # Strong borrowers may prepay somewhat before scheduled maturity,
            # but long loans do not routinely collapse immediately.
            max_advance = min(
                int(max(0, years_exposed - 1)),
                3 if behavior.product_id != "P014" else 2,
            )
            advance_years = 0
            if max_advance > 0:
                p_advance = float(
                    np.clip(
                        0.08
                        + 0.10 * row["_capacity"]
                        + 0.06 * row["_relationship"],
                        0.02,
                        0.25,
                    )
                )
                if rng.random() < p_advance:
                    advance_years = int(rng.integers(1, max_advance + 1))

            resolution = maturity_period - 12 * advance_years
            resolution = max(resolution, origination_period)
            return "PAID_OFF", resolution, "COMPRESSED_CURRENT"

        # Adverse event occurred historically. Recovery remains common.
        recovery_prob = float(
            sigmoid(
                0.70
                + 0.90 * row["_capacity"]
                + 0.45 * row["_relationship"]
                - 1.25 * stress_index
            )
        )

        if rng.random() < recovery_prob:
            return "PAID_OFF", maturity_period, "COMPRESSED_RECOVERED"

        # Remaining severe outcomes.
        writeoff_prob = float(
            np.clip(sigmoid(-3.3 + 1.25 * stress_index), 0.01, 0.18)
        )
        restructure_prob = float(
            np.clip(
                sigmoid(-2.7 + 0.95 * stress_index + 0.55 * row["_relationship"]),
                0.02,
                0.24,
            )
        )

        u = rng.random()
        if u < writeoff_prob:
            return "WRITTEN_OFF", maturity_period, "COMPRESSED_WRITTEN_OFF"
        if u < writeoff_prob + restructure_prob:
            return "RESTRUCTURED", maturity_period, "COMPRESSED_RESTRUCTURED"

        return "DEFAULTED", maturity_period, "COMPRESSED_DEFAULTED"

    def _initial_2021_state(
        self,
        stress_index: float,
        row,
        rng: np.random.Generator,
    ) -> str:
        p_severe = float(
            np.clip(sigmoid(-4.0 + 1.45 * stress_index), 0.002, 0.08)
        )
        p_early = float(
            np.clip(sigmoid(-3.0 + 1.10 * stress_index), 0.01, 0.20)
        )

        u = rng.random()
        if u < p_severe:
            return "SEVERE"
        if u < p_severe + p_early:
            return "EARLY"
        return "CURRENT"

    def _monthly_prepay_probability(
        self,
        row,
        behavior: LoanBehavior,
        age_months: int,
        term_months: int,
        stress_index: float,
    ) -> float:
        if behavior.kind != "INSTALLMENT":
            return 0.0
        if age_months < behavior.prepay_min_age_months:
            return 0.0

        # Age ramp avoids an immediate first-month payoff spike.
        age_ramp = min(
            1.0,
            max(0.0, age_months - behavior.prepay_min_age_months + 1) / 12,
        )

        # As maturity approaches, what looks like "prepayment" should increasingly
        # be captured by scheduled maturity instead, so cap the hazard.
        remaining = max(term_months - age_months, 0)
        maturity_guard = min(1.0, remaining / max(term_months, 1))

        multiplier = np.exp(
            0.80 * (row["_capacity"] - 0.5)
            + 0.45 * (row["_relationship"] - 0.5)
            - 0.70 * stress_index
        )

        p = (
            behavior.monthly_prepay_base
            * age_ramp
            * max(0.25, maturity_guard)
            * multiplier
        )
        return float(np.clip(p, 0.0, 0.02))

    def _simulate_lifecycle(
        self,
        row,
        behavior: LoanBehavior,
        origination_year: int,
        origination_month: int,
        amount: float,
        currency: str,
        term_months: int,
        initial_rate: float,
        lifecycle_seed: int,
    ) -> Tuple[str, Optional[int], Optional[str], str, str]:
        """
        Returns:
            loan_status
            closing_year
            resolution_month_internal (YYYY-MM or None)
            terminal_event_internal
            pre2021_inherited_state

        2021 onward is a monthly latent delinquency-state process.
        It is not yet the financial snapshot ledger, but it imposes temporal
        persistence and prevents instant default/prepayment artifacts.
        """
        rng = np.random.default_rng(lifecycle_seed)

        orig = pd.Period(
            f"{origination_year:04d}-{origination_month:02d}",
            freq="M",
        )
        cutoff = pd.Period(
            f"{CURRENT_YEAR:04d}-{CURRENT_MONTH:02d}",
            freq="M",
        )
        obs_start = pd.Period(
            f"{OBSERVATION_START_YEAR:04d}-01",
            freq="M",
        )

        maturity = period_add_months(orig, term_months)
        burden = self._payment_burden(
            row,
            behavior,
            amount,
            currency,
            term_months,
            initial_rate,
            origination_year,
        )
        stress_index = self._stress_index(
            row,
            burden,
            currency,
            initial_rate,
            rng,
        )

        # -------------------------------------------------------------
        # Contracts that completed before the detailed window.
        # -------------------------------------------------------------
        if behavior.kind == "INSTALLMENT" and maturity < obs_start:
            status, resolution, inherited = self._compressed_pre2021_resolution(
                row,
                behavior,
                orig,
                maturity,
                stress_index,
                rng,
            )
            return (
                status,
                int(resolution.year),
                str(resolution),
                status,
                inherited,
            )

        if behavior.kind == "REVOLVING":
            facility_horizon = period_add_months(orig, term_months)
            if facility_horizon < obs_start:
                # Old facility contracts generally resolve/renew before 2021.
                p_bad = float(
                    np.clip(
                        sigmoid(-3.8 + 1.45 * stress_index),
                        0.005,
                        0.10,
                    )
                )
                if rng.random() < p_bad:
                    if rng.random() < 0.16:
                        status = "WRITTEN_OFF"
                    elif rng.random() < 0.26:
                        status = "RESTRUCTURED"
                    else:
                        status = "DEFAULTED"
                else:
                    status = "PAID_OFF"

                return (
                    status,
                    int(facility_horizon.year),
                    str(facility_horizon),
                    status,
                    "COMPRESSED_REVOLVING",
                )

        # -------------------------------------------------------------
        # Enter detailed monthly window.
        # -------------------------------------------------------------
        start = max(orig, obs_start)

        if orig < obs_start:
            state = self._initial_2021_state(stress_index, row, rng)
            inherited_state = f"INHERITED_{state}"
        else:
            state = "CURRENT"
            inherited_state = "NOT_APPLICABLE"

        severe_months = 1 if state == "SEVERE" else 0
        default_months = 0
        shock = rng.normal(0, 0.25)

        current = start
        while current <= cutoff:
            age_months = period_months_inclusive(orig, current)
            macro = MACRO_STRESS_BY_YEAR.get(int(current.year), 0.0)

            # Persistent monthly latent shock.
            shock = 0.78 * shock + rng.normal(0, 0.34)

            # ---------------------------------------------------------
            # Scheduled contractual resolution.
            # ---------------------------------------------------------
            if behavior.kind == "INSTALLMENT" and current >= maturity:
                if state == "CURRENT":
                    return (
                        "PAID_OFF",
                        int(current.year),
                        str(current),
                        "SCHEDULED_MATURITY",
                        inherited_state,
                    )
                # Delinquent contracts can run beyond nominal maturity.

            # ---------------------------------------------------------
            # Prepayment from a performing state only.
            # ---------------------------------------------------------
            if state == "CURRENT":
                p_prepay = self._monthly_prepay_probability(
                    row,
                    behavior,
                    age_months,
                    term_months,
                    stress_index,
                )
                if rng.random() < p_prepay:
                    return (
                        "PAID_OFF",
                        int(current.year),
                        str(current),
                        "EARLY_PREPAYMENT",
                        inherited_state,
                    )

            # ---------------------------------------------------------
            # Revolving-facility expiry / renewal.
            # ---------------------------------------------------------
            if behavior.kind == "REVOLVING":
                facility_horizon = period_add_months(orig, term_months)
                if current >= facility_horizon and state == "CURRENT":
                    # Closing one facility and renewing another is represented
                    # as PAID_OFF for this contract.
                    p_close_facility = float(
                        np.clip(
                            0.48
                            + 0.18 * row["_capacity"]
                            + 0.10 * row["_relationship"],
                            0.45,
                            0.78,
                        )
                    )
                    if rng.random() < p_close_facility:
                        return (
                            "PAID_OFF",
                            int(current.year),
                            str(current),
                            "FACILITY_EXPIRY",
                            inherited_state,
                        )

            # ---------------------------------------------------------
            # Delinquency-state transitions.
            # ---------------------------------------------------------
            if state == "CURRENT":
                # Small seasoning guard: newly originated credit can become
                # delinquent quickly, but serious deterioration is less likely
                # in the first few months.
                seasoning = min(1.0, age_months / 12)
                p_early = float(
                    np.clip(
                        sigmoid(
                            -4.35
                            + 1.35 * stress_index
                            + 0.48 * shock
                            + macro
                            + 0.20 * seasoning
                        ),
                        0.001,
                        0.10,
                    )
                )
                if rng.random() < p_early:
                    state = "EARLY"

            elif state == "EARLY":
                p_cure = float(
                    np.clip(
                        sigmoid(
                            0.70
                            + 0.90 * row["_capacity"]
                            + 0.35 * row["_relationship"]
                            - 1.05 * stress_index
                            - 0.28 * shock
                        ),
                        0.20,
                        0.90,
                    )
                )
                p_severe = float(
                    np.clip(
                        sigmoid(
                            -3.15
                            + 1.25 * stress_index
                            + 0.40 * shock
                            + macro
                        ),
                        0.01,
                        0.28,
                    )
                )

                u = rng.random()
                if u < p_cure:
                    state = "CURRENT"
                elif u < p_cure + p_severe:
                    state = "SEVERE"
                    severe_months = 1

            elif state == "SEVERE":
                severe_months += 1

                p_cure = float(
                    np.clip(
                        sigmoid(
                            -0.45
                            + 0.95 * row["_capacity"]
                            + 0.40 * row["_relationship"]
                            - 1.20 * stress_index
                            - 0.30 * shock
                        ),
                        0.05,
                        0.65,
                    )
                )

                if rng.random() < p_cure:
                    state = "CURRENT"
                    severe_months = 0
                else:
                    # Restructuring requires persistence; it cannot happen from
                    # one isolated monthly wobble.
                    if severe_months >= 2:
                        p_restructure = float(
                            np.clip(
                                sigmoid(
                                    -4.10
                                    + 0.90 * stress_index
                                    + 0.65 * row["_relationship"]
                                    + 0.08 * severe_months
                                ),
                                0.002,
                                0.08,
                            )
                        )
                        if rng.random() < p_restructure:
                            return (
                                "RESTRUCTURED",
                                int(current.year),
                                str(current),
                                "RESTRUCTURE",
                                inherited_state,
                            )

                    # Default recognition requires at least 3 severe months.
                    if severe_months >= 3:
                        p_default = float(
                            np.clip(
                                sigmoid(
                                    -3.05
                                    + 1.15 * stress_index
                                    + 0.45 * shock
                                    + macro
                                    + 0.10 * (severe_months - 3)
                                ),
                                0.005,
                                0.20,
                            )
                        )
                        if rng.random() < p_default:
                            state = "DEFAULTED"
                            default_months = 1

            elif state == "DEFAULTED":
                default_months += 1

                # Cure remains possible; a historical default episode does not
                # mechanically force final master status DEFAULTED.
                p_cure = float(
                    np.clip(
                        sigmoid(
                            -2.25
                            + 0.95 * row["_capacity"]
                            + 0.45 * row["_relationship"]
                            - 1.05 * stress_index
                            - 0.25 * shock
                        ),
                        0.01,
                        0.28,
                    )
                )
                if rng.random() < p_cure:
                    state = "CURRENT"
                    severe_months = 0
                    default_months = 0
                else:
                    p_restructure = float(
                        np.clip(
                            sigmoid(
                                -4.00
                                + 1.00 * stress_index
                                + 0.75 * row["_relationship"]
                                + 0.08 * default_months
                            ),
                            0.003,
                            0.10,
                        )
                    )
                    if rng.random() < p_restructure:
                        return (
                            "RESTRUCTURED",
                            int(current.year),
                            str(current),
                            "RESTRUCTURE_AFTER_DEFAULT",
                            inherited_state,
                        )

                    # Write-off requires prolonged unresolved default.
                    if default_months >= 6:
                        p_writeoff = float(
                            np.clip(
                                sigmoid(
                                    -5.25
                                    + 1.25 * stress_index
                                    + 0.10 * default_months
                                ),
                                0.001,
                                0.08,
                            )
                        )
                        if rng.random() < p_writeoff:
                            return (
                                "WRITTEN_OFF",
                                int(current.year),
                                str(current),
                                "WRITE_OFF",
                                inherited_state,
                            )

            # ---------------------------------------------------------
            # Customer relationship closure: influence, not determinism.
            # ---------------------------------------------------------
            customer_close_year = row.get("closing_year")
            if (
                pd.notna(customer_close_year)
                and int(current.year) >= int(customer_close_year)
                and state == "CURRENT"
            ):
                # Relationship closure makes voluntary resolution more likely,
                # but the loan is not mechanically forced to close.
                p_relationship_resolution = 0.005
                if behavior.product_id == "P014":
                    p_relationship_resolution *= 0.35
                if rng.random() < p_relationship_resolution:
                    return (
                        "PAID_OFF",
                        int(current.year),
                        str(current),
                        "RELATIONSHIP_EXIT_RESOLUTION",
                        inherited_state,
                    )

            current += 1

        # -------------------------------------------------------------
        # Status at 2026-12-31
        # -------------------------------------------------------------
        if state == "DEFAULTED":
            return (
                "DEFAULTED",
                None,
                None,
                "OPEN_DEFAULT_AT_CUTOFF",
                inherited_state,
            )

        if state == "SEVERE":
            # Severe delinquency is not automatically master DEFAULTED.
            # Only a minority is recognized as default at cutoff.
            p_recognized = float(
                np.clip(
                    sigmoid(-2.60 + 1.10 * stress_index + 0.10 * severe_months),
                    0.02,
                    0.35,
                )
            )
            if rng.random() < p_recognized:
                return (
                    "DEFAULTED",
                    None,
                    None,
                    "SEVERE_RECOGNIZED_AT_CUTOFF",
                    inherited_state,
                )

        return (
            "ACTIVE",
            None,
            None,
            f"OPEN_{state}_AT_CUTOFF",
            inherited_state,
        )

    # ---------------------------------------------------------------------
    # Contract generation
    # ---------------------------------------------------------------------

    def _new_loan_identity(self) -> Tuple[str, int]:
        loan_number = self.next_loan_number
        loan_id = f"L{loan_number:07d}"
        self.next_loan_number += 1

        # Stable per-loan lifecycle seed, independent from the global draw order
        # inside the lifecycle itself.
        lifecycle_seed = int(
            (LOAN_SEED + loan_number * 1_000_003) % (2**32 - 1)
        )
        return loan_id, lifecycle_seed

    def _generate_contract(
        self,
        row,
        behavior: LoanBehavior,
        year: int,
    ):
        loan_id, lifecycle_seed = self._new_loan_identity()

        branch_id = self._choose_branch(row, behavior.product_id, year)
        currency = self._choose_currency(row, behavior)
        amount = self._amount(row, behavior, currency, year)
        term = self._choose_term(
            row,
            behavior,
            amount,
            currency,
            year,
        )
        rate_type = self._choose_rate_type(
            row,
            behavior,
            currency,
            term,
        )
        initial_rate = self._initial_rate(
            row,
            behavior,
            year,
            currency,
            term,
            rate_type,
        )

        # Hidden exact origination month fixes coarse exposure bias.
        origination_month = int(self.rng.integers(1, 13))

        (
            status,
            closing_year,
            resolution_month,
            terminal_event,
            inherited_state,
        ) = self._simulate_lifecycle(
            row=row,
            behavior=behavior,
            origination_year=year,
            origination_month=origination_month,
            amount=amount,
            currency=currency,
            term_months=term,
            initial_rate=initial_rate,
            lifecycle_seed=lifecycle_seed,
        )

        self.rows.append({
            "loan_id": loan_id,
            "customer_id": row["customer_id"],
            "product_id": behavior.product_id,
            "branch_id": branch_id,
            "origination_year": int(year),
            "currency": currency,
            "original_amount": amount,
            "term_months": int(term),
            "rate_type": rate_type,
            "initial_interest_rate": initial_rate,
            "loan_status": status,
            "closing_year": closing_year,
        })

        self.bridge_rows.append({
            "loan_id": loan_id,
            "origination_month_internal": f"{year:04d}-{origination_month:02d}",
            "lifecycle_seed": lifecycle_seed,
            "resolution_month_internal": resolution_month,
            "terminal_event_internal": terminal_event,
            "pre2021_inherited_state": inherited_state,
        })

    def generate(self) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """
        1) Pre-2021: compressed historical contract generation.
        2) 2021-2026: annual originations with monthly lifecycle exposure.
        """

        for _, row in self.customers.iterrows():
            registration_year = int(row["registration_year"])
            customer_closing_year = (
                int(row["closing_year"])
                if pd.notna(row["closing_year"])
                else CURRENT_YEAR
            )

            eligible_behaviors = [
                b for b in BEHAVIOR.values()
                if self._compatible(row["customer_type"], b.product_id)
            ]
            if not eligible_behaviors:
                continue

            # -------------------------
            # Pre-2021 compressed state
            # -------------------------
            earliest_launch = min(
                self._launch_year(b.product_id)
                for b in eligible_behaviors
            )
            pre_start = max(registration_year, earliest_launch)
            pre_end = min(
                OBSERVATION_START_YEAR - 1,
                customer_closing_year,
            )

            if pre_start <= pre_end:
                tenure_pre = pre_end - pre_start + 1

                base_lambda = (
                    0.55
                    + 0.80 * row["_loan_demand"]
                    + 0.40 * row["_relationship"]
                    + 0.025 * tenure_pre
                )
                if row["customer_type"] == "BUSINESS":
                    base_lambda += 0.25

                # NB parameterization:
                # mean = r*(1-p)/p = base_lambda when r=2 and p=2/(2+lambda).
                n_pre = int(
                    self.rng.negative_binomial(
                        2,
                        2 / (2 + base_lambda),
                    )
                )
                n_pre = int(np.clip(n_pre, 0, 8))

                for _ in range(n_pre):
                    valid = [
                        b for b in eligible_behaviors
                        if self._launch_year(b.product_id) <= pre_end
                    ]
                    if not valid:
                        break

                    year_low = max(
                        registration_year,
                        min(self._launch_year(b.product_id) for b in valid),
                    )
                    years = np.arange(year_low, pre_end + 1)

                    weights = np.exp(0.055 * (years - years.max()))
                    weights *= self.rng.lognormal(0, 0.18, len(years))
                    weights /= weights.sum()

                    year = int(self.rng.choice(years, p=weights))
                    valid_year = [
                        b for b in valid
                        if self._launch_year(b.product_id) <= year
                    ]

                    utilities = np.array([
                        self._product_utility(row, b, year)
                        for b in valid_year
                    ])

                    behavior = valid_year[int(
                        self.rng.choice(
                            len(valid_year),
                            p=softmax(utilities),
                        )
                    )]

                    self._generate_contract(row, behavior, year)

            # -------------------------
            # 2021-2026 originations
            # -------------------------
            start_year = max(
                OBSERVATION_START_YEAR,
                registration_year,
            )

            # Per-customer counter avoids scanning all previously generated rows.
            same_product_count = {pid: 0 for pid in BEHAVIOR}

            for year in range(start_year, CURRENT_YEAR + 1):
                if year > customer_closing_year:
                    break

                for behavior in eligible_behaviors:
                    if year < self._launch_year(behavior.product_id):
                        continue

                    p = self._annual_product_probability(
                        row,
                        behavior,
                        year,
                    )

                    # Historical repeated contracts are not counted here because
                    # we want mild saturation in the detailed window, not a hidden
                    # decades-long prohibition on renewed borrowing.
                    existing_same = same_product_count[behavior.product_id]
                    p *= np.exp(-0.32 * existing_same)

                    if self.rng.random() < p:
                        self._generate_contract(row, behavior, year)
                        same_product_count[behavior.product_id] += 1

        loans = pd.DataFrame(self.rows, columns=LOAN_COLUMNS)
        bridge = pd.DataFrame(self.bridge_rows, columns=BRIDGE_COLUMNS)
        return loans, bridge


# =============================================================================
# Validation
# =============================================================================

def validate_output(loans, bridge, customers, branches, products):
    errors = []

    if list(loans.columns) != LOAN_COLUMNS:
        errors.append(f"Column mismatch: {list(loans.columns)}")

    if list(bridge.columns) != BRIDGE_COLUMNS:
        errors.append(f"Bridge column mismatch: {list(bridge.columns)}")

    if loans["loan_id"].duplicated().any():
        errors.append("Duplicate loan_id values.")

    if not loans["loan_id"].astype(str).str.fullmatch(r"L\d{7}").all():
        errors.append("Invalid loan_id format.")

    if set(loans["loan_id"]) != set(bridge["loan_id"]):
        errors.append("Lifecycle bridge does not reconcile one-to-one with loans.")

    valid_customers = set(customers["customer_id"])
    bad = ~loans["customer_id"].isin(valid_customers)
    if bad.any():
        errors.append(f"Invalid customer FK: {bad.sum()} rows.")

    valid_branches = set(branches["branch_id"])
    bad = ~loans["branch_id"].isin(valid_branches)
    if bad.any():
        errors.append(f"Invalid branch FK: {bad.sum()} rows.")

    if not loans["product_id"].isin(BEHAVIOR.keys()).all():
        errors.append("Invalid lending product_id.")

    catalog = (
        products[products["product_id"].isin(BEHAVIOR)]
        .set_index("product_id")
    )

    merged = loans.merge(
        customers[[
            "customer_id",
            "customer_type",
            "registration_year",
            "customer_status",
            "closing_year",
        ]],
        on="customer_id",
        how="left",
        suffixes=("", "_customer"),
    )

    targets = merged["product_id"].map(
        catalog["target_customer_type"].to_dict()
    )
    bad = ~(
        targets.eq("BOTH")
        | targets.eq(merged["customer_type"])
    )
    if bad.any():
        errors.append(
            f"Product/customer type incompatibility: {bad.sum()} rows."
        )

    launches = merged["product_id"].map(
        pd.to_numeric(catalog["launch_year"], errors="coerce").to_dict()
    )
    bad = merged["origination_year"] < launches
    if bad.any():
        errors.append(
            f"Origination before product launch: {bad.sum()} rows."
        )

    bad = (
        merged["origination_year"]
        < pd.to_numeric(
            merged["registration_year"],
            errors="coerce",
        )
    )
    if bad.any():
        errors.append(
            f"Origination before customer registration: {bad.sum()} rows."
        )

    if not loans["currency"].isin(["UYU", "USD"]).all():
        errors.append("Invalid currency.")

    catalog_currency = loans["product_id"].map(
        catalog["currency"].to_dict()
    )
    bad_currency = (
        (catalog_currency.eq("UYU") & ~loans["currency"].eq("UYU"))
        | (catalog_currency.eq("USD") & ~loans["currency"].eq("USD"))
        | ~catalog_currency.isin(["UYU", "USD", "MULTI"])
    )
    if bad_currency.any():
        errors.append(
            f"Loan currency violates products catalog: {bad_currency.sum()} rows."
        )

    if (
        pd.to_numeric(
            loans["original_amount"],
            errors="coerce",
        ) <= 0
    ).any():
        errors.append("Non-positive original_amount.")

    if (
        pd.to_numeric(
            loans["term_months"],
            errors="coerce",
        ) <= 0
    ).any():
        errors.append("Non-positive term_months.")

    if not loans["rate_type"].isin(
        ["FIXED", "VARIABLE", "MIXED"]
    ).all():
        errors.append("Invalid rate_type.")

    if (
        pd.to_numeric(
            loans["initial_interest_rate"],
            errors="coerce",
        ) <= 0
    ).any():
        errors.append("Non-positive initial_interest_rate.")

    valid_status = {
        "ACTIVE",
        "PAID_OFF",
        "DEFAULTED",
        "RESTRUCTURED",
        "WRITTEN_OFF",
    }
    if not loans["loan_status"].isin(valid_status).all():
        errors.append("Invalid loan_status.")

    active_with_closing = (
        loans["loan_status"].eq("ACTIVE")
        & loans["closing_year"].notna()
    )
    if active_with_closing.any():
        errors.append(
            f"ACTIVE loans with closing_year: {active_with_closing.sum()}."
        )

    final_without_close = (
        loans["loan_status"].isin(["PAID_OFF", "WRITTEN_OFF"])
        & loans["closing_year"].isna()
    )
    if final_without_close.any():
        errors.append(
            "PAID_OFF/WRITTEN_OFF loans without closing_year: "
            f"{final_without_close.sum()}."
        )

    has_close = loans["closing_year"].notna()
    if has_close.any():
        close = pd.to_numeric(
            loans.loc[has_close, "closing_year"],
            errors="coerce",
        )
        orig = pd.to_numeric(
            loans.loc[has_close, "origination_year"],
            errors="coerce",
        )
        if (close < orig).any():
            errors.append("closing_year before origination_year.")
        if (close > CURRENT_YEAR).any():
            errors.append("closing_year after 2026.")

    # Branch must have been operational at origination.
    branch_meta = branches[["branch_id", "opening_year"]].copy()
    branch_meta["branch_closing_year"] = (
        branches["closing_year"]
        if "closing_year" in branches.columns
        else np.nan
    )

    chk = loans.merge(
        branch_meta,
        on="branch_id",
        how="left",
    )
    if (
        chk["origination_year"]
        < pd.to_numeric(chk["opening_year"], errors="coerce")
    ).any():
        errors.append("Loan originated before branch opening.")

    branch_close = pd.to_numeric(
        chk["branch_closing_year"],
        errors="coerce",
    )
    bad = (
        branch_close.notna()
        & (chk["origination_year"] > branch_close)
    )
    if bad.any():
        errors.append(
            f"Loan originated after branch closure: {bad.sum()} rows."
        )

    # Internal temporal bridge consistency.
    bridge_chk = loans[[
        "loan_id",
        "origination_year",
        "loan_status",
        "closing_year",
    ]].merge(
        bridge,
        on="loan_id",
        how="left",
    )

    orig_period = pd.PeriodIndex(
        bridge_chk["origination_month_internal"],
        freq="M",
    )
    if (
        orig_period.year
        != bridge_chk["origination_year"].astype(int).to_numpy()
    ).any():
        errors.append("Bridge origination month/year inconsistency.")

    resolved = bridge_chk["resolution_month_internal"].notna()
    if resolved.any():
        resolution_period = pd.PeriodIndex(
            bridge_chk.loc[
                resolved,
                "resolution_month_internal",
            ],
            freq="M",
        )
        if (
            resolution_period.year
            != bridge_chk.loc[
                resolved,
                "closing_year",
            ].astype(int).to_numpy()
        ).any():
            errors.append("Bridge resolution month/closing_year inconsistency.")

    if errors:
        print("\nVALIDATION: FAIL")
        for error in errors:
            print(" -", error)
        raise AssertionError("Loan validation failed.")

    print("\nVALIDATION: PASS")


# =============================================================================
# Audit
# =============================================================================

def audit(loans, bridge, customers, products):
    print("\n" + "=" * 76)
    print("BTYT LOANS AUDIT")
    print("=" * 76)

    print(f"\nCustomers in dev population: {len(customers):,}")
    print(f"Loans generated: {len(loans):,}")

    holders = loans["customer_id"].nunique()
    print(
        f"Customers with >=1 loan: {holders:,} "
        f"({holders / len(customers):.2%})"
    )

    if loans.empty:
        return

    counts = loans.groupby("customer_id").size()
    print(f"Mean loans per borrower: {counts.mean():.2f}")
    print(f"Median loans per borrower: {counts.median():.0f}")
    print(f"P95 loans per borrower: {counts.quantile(.95):.0f}")
    print(f"Max loans per borrower: {counts.max():.0f}")

    print("\nLoans by product:")
    print(loans["product_id"].value_counts().sort_index())

    print("\nLoan status:")
    print(
        (loans["loan_status"].value_counts(normalize=True) * 100)
        .round(2)
        .astype(str)
        + "%"
    )

    print("\nCurrency by product (%):")
    print(
        pd.crosstab(
            loans["product_id"],
            loans["currency"],
            normalize="index",
        ).mul(100).round(1)
    )

    print("\nRate type by product (%):")
    print(
        pd.crosstab(
            loans["product_id"],
            loans["rate_type"],
            normalize="index",
        ).mul(100).round(1)
    )

    print("\nOrigination years:")
    print(
        loans["origination_year"]
        .value_counts()
        .sort_index()
    )

    print("\nOriginal amount summary by product:")
    print(
        loans.groupby(
            ["product_id", "currency"]
        )["original_amount"]
        .agg(["count", "median", "mean", "max"])
        .round(2)
    )

    print("\nTerm summary by product:")
    print(
        loans.groupby("product_id")["term_months"]
        .agg(["count", "median", "mean", "min", "max"])
        .round(2)
    )

    print("\nInitial rate summary:")
    print(
        loans.groupby(
            ["product_id", "currency"]
        )["initial_interest_rate"]
        .agg(["count", "median", "mean", "min", "max"])
        .round(2)
    )

    print("\nStatus by vintage (%):")
    bins = [1900, 2000, 2010, 2020, 2026]
    labels = ["<=2000", "2001-2010", "2011-2020", "2021-2026"]
    vintage = pd.cut(
        loans["origination_year"],
        bins=bins,
        labels=labels,
        include_lowest=True,
    )
    print(
        pd.crosstab(
            vintage,
            loans["loan_status"],
            normalize="index",
        ).mul(100).round(1)
    )

    recent = loans[loans["origination_year"] >= 2021]
    if not recent.empty:
        print("\nStatus by year 2021-2026 (%):")
        print(
            pd.crosstab(
                recent["origination_year"],
                recent["loan_status"],
                normalize="index",
            ).mul(100).round(1)
        )

    recent3 = loans[loans["origination_year"] >= 2024]
    if not recent3.empty:
        print("\nStatus by product and year 2024-2026 (%):")
        print(
            pd.crosstab(
                [
                    recent3["product_id"],
                    recent3["origination_year"],
                ],
                recent3["loan_status"],
                normalize="index",
            ).mul(100).round(1).to_string()
        )

    print("\nLifecycle terminal events:")
    print(
        bridge["terminal_event_internal"]
        .value_counts()
        .head(20)
    )

    problem_statuses = ["DEFAULTED", "RESTRUCTURED", "WRITTEN_OFF"]

    overall_problem = loans["loan_status"].isin(problem_statuses).mean()
    print(f"\nProblem-status share: {overall_problem * 100:.2f}%")

    recent_loans = loans[loans["origination_year"].between(2021, 2026)]
    if not recent_loans.empty:
        recent_problem = recent_loans["loan_status"].isin(problem_statuses).mean()
        print(
            "Problem-status share, 2021-2026 originations: "
            f"{recent_problem * 100:.2f}%"
        )

    historical_loans = loans[loans["origination_year"] <= 2020]
    if not historical_loans.empty:
        historical_problem = historical_loans["loan_status"].isin(problem_statuses).mean()
        print(
            "Problem-status share, <=2020 originations: "
            f"{historical_problem * 100:.2f}%"
        )

    print("\nCatalog metadata actually used:")
    cols = [
        "product_id",
        "product_name",
        "product_family",
        "currency",
        "target_customer_type",
        "launch_year",
    ]
    print(
        products[
            products["product_id"].isin(BEHAVIOR)
        ][cols]
        .sort_values("product_id")
        .to_string(index=False)
    )


# =============================================================================
# Main
# =============================================================================

def main():
    print("Loading inputs...")
    customers, accounts, branches, products = load_inputs()
    validate_inputs(
        customers,
        accounts,
        branches,
        products,
    )

    print(f"Customers: {len(customers):,}")
    print(f"Accounts: {len(accounts):,}")
    print(f"Branches: {len(branches):,}")

    generator = LoanGenerator(
        customers,
        accounts,
        branches,
        products,
    )

    print("\nGenerating loans...")
    loans, bridge = generator.generate()

    validate_output(
        loans,
        bridge,
        customers,
        branches,
        products,
    )
    audit(
        loans,
        bridge,
        customers,
        products,
    )

    OUTPUT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )
    BRIDGE_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    loans.to_csv(
        OUTPUT_PATH,
        index=False,
    )
    bridge.to_csv(
        BRIDGE_PATH,
        index=False,
    )

    print(f"\nSaved canonical: {OUTPUT_PATH}")
    print(f"Shape: {loans.shape}")
    print(f"Saved internal bridge: {BRIDGE_PATH}")
    print(f"Bridge shape: {bridge.shape}")


if __name__ == "__main__":
    main()
