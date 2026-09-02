from __future__ import annotations

"""
BTYT Banking Analytics
Loan master generator (Phase 3)

Creates:
    data/generated/loans.csv

Canonical sources:
    database/loans_data_dictionary.md
    database/loan_monthly_snapshot_data_dictionary.md

Design principles:
- reproducible stochastic generation
- 2021–2026 is the detailed observational window
- pre-2021 history is compressed inherited state
- loan status is derived from an internal lifecycle, not sampled as a final label
- no deterministic hidden "risk score"
- P016 Business Credit Line is treated as a revolving facility
- monthly snapshot export is intentionally left for the next module, but the
  internal lifecycle is structured so the master table can later reconcile with it
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
OBSERVATION_START_YEAR = 2021

DEVELOPMENT_MODE = True
DEVELOPMENT_CUSTOMERS = 10_000

ROOT = Path(__file__).resolve().parents[1]
DATA_GENERATED = ROOT / "data" / "generated"
DATA_MASTER = ROOT / "data" / "master"
DATA_INTERIM = ROOT / "data" / "interim"

CUSTOMERS_PATH = DATA_GENERATED / "customers.csv"
ACCOUNTS_PATH = DATA_GENERATED / "accounts.csv"
BRANCHES_PATH = DATA_GENERATED / "branches.csv"
PRODUCTS_PATH = DATA_MASTER / "products.csv"
BRANCH_STATE_PATH = DATA_INTERIM / "branch_yearly_state.csv"
OUTPUT_PATH = DATA_GENERATED / "loans.csv"
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


# =============================================================================
# Product configuration
# =============================================================================

@dataclass(frozen=True)
class LoanProduct:
    product_id: str
    target: str
    launch_year: int
    kind: str
    amount_median_uyu: float
    amount_sigma: float
    term_options: Tuple[int, ...]
    fixed_weight: float
    variable_weight: float
    mixed_weight: float
    usd_base: float
    demand_intercept: float


PRODUCTS: Dict[str, LoanProduct] = {
    "P012": LoanProduct(
        "P012", "INDIVIDUAL", 1998, "INSTALLMENT",
        260_000, 0.75, (6, 12, 18, 24, 36, 48, 60),
        0.78, 0.16, 0.06, 0.03, -2.15
    ),
    "P013": LoanProduct(
        "P013", "INDIVIDUAL", 2003, "INSTALLMENT",
        1_050_000, 0.55, (24, 36, 48, 60, 72),
        0.55, 0.30, 0.15, 0.32, -3.00
    ),
    "P014": LoanProduct(
        "P014", "INDIVIDUAL", 1999, "INSTALLMENT",
        4_800_000, 0.60, (60, 120, 180, 240, 300),
        0.28, 0.42, 0.30, 0.20, -3.65
    ),
    "P015": LoanProduct(
        "P015", "BUSINESS", 2000, "INSTALLMENT",
        2_000_000, 0.85, (12, 24, 36, 48, 60, 84),
        0.45, 0.38, 0.17, 0.32, -2.20
    ),
    "P016": LoanProduct(
        "P016", "BUSINESS", 2005, "REVOLVING",
        3_500_000, 0.90, (12, 24, 36),
        0.20, 0.62, 0.18, 0.46, -2.65
    ),
    "P017": LoanProduct(
        "P017", "BUSINESS", 2002, "INSTALLMENT",
        4_000_000, 0.95, (12, 24, 36, 48, 60, 84, 120),
        0.25, 0.53, 0.22, 0.56, -3.05
    ),
    "P018": LoanProduct(
        "P018", "BUSINESS", 2007, "INSTALLMENT",
        3_200_000, 0.75, (24, 36, 48, 60, 72, 84),
        0.42, 0.38, 0.20, 0.48, -3.25
    ),
}


# Approximate synthetic macro environments.
# These are not intended to reproduce official Uruguayan market series.
UYU_BASE_RATE = {
    1998: 31.0, 1999: 29.0, 2000: 27.0, 2001: 30.0, 2002: 43.0,
    2003: 35.0, 2004: 25.0, 2005: 19.0, 2006: 16.0, 2007: 14.0,
    2008: 15.5, 2009: 13.0, 2010: 12.0, 2011: 11.5, 2012: 12.0,
    2013: 12.5, 2014: 13.0, 2015: 14.5, 2016: 15.0, 2017: 13.5,
    2018: 13.0, 2019: 12.5, 2020: 10.5, 2021: 10.0, 2022: 12.5,
    2023: 14.0, 2024: 12.5, 2025: 11.5, 2026: 11.0,
}

USD_BASE_RATE = {
    year: value
    for year, value in [
        (1998, 10.0), (1999, 9.7), (2000, 9.4), (2001, 10.2), (2002, 12.5),
        (2003, 10.5), (2004, 8.5), (2005, 7.8), (2006, 7.2), (2007, 7.0),
        (2008, 7.8), (2009, 6.8), (2010, 6.2), (2011, 6.0), (2012, 6.1),
        (2013, 6.2), (2014, 6.4), (2015, 6.8), (2016, 6.7), (2017, 6.3),
        (2018, 6.4), (2019, 6.1), (2020, 5.4), (2021, 5.2), (2022, 6.1),
        (2023, 7.3), (2024, 7.1), (2025, 6.8), (2026, 6.5),
    ]
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
# Helpers
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


def first_existing(paths: List[Path]) -> Path:
    for path in paths:
        if path.exists():
            return path
    raise FileNotFoundError(
        "Could not locate any of:\n" + "\n".join(str(p) for p in paths)
    )


def round_money(value: float) -> float:
    if value < 100_000:
        base = 1_000
    elif value < 1_000_000:
        base = 5_000
    elif value < 10_000_000:
        base = 10_000
    else:
        base = 50_000
    return float(round(value / base) * base)


# =============================================================================
# Input loading
# =============================================================================

def load_inputs():
    customers = pd.read_csv(CUSTOMERS_PATH, dtype={"customer_id": str, "primary_branch_id": str})
    accounts = pd.read_csv(ACCOUNTS_PATH, dtype={
        "account_id": str,
        "customer_id": str,
        "product_id": str,
        "branch_id": str,
    })

    required_paths = {
        "customers": CUSTOMERS_PATH,
        "accounts": ACCOUNTS_PATH,
        "branches": BRANCHES_PATH,
        "products": PRODUCTS_PATH,
        "branch_yearly_state": BRANCH_STATE_PATH,
    }
    missing_paths = [path for path in required_paths.values() if not path.exists()]
    if missing_paths:
        raise FileNotFoundError(
            "Missing canonical BTYT input file(s):\n"
            + "\n".join(str(path) for path in missing_paths)
        )

    branches = pd.read_csv(BRANCHES_PATH, dtype={"branch_id": str})
    products = pd.read_csv(PRODUCTS_PATH, dtype={"product_id": str})
    branch_state = pd.read_csv(BRANCH_STATE_PATH, dtype={"branch_id": str})

    if DEVELOPMENT_MODE and len(customers) > DEVELOPMENT_CUSTOMERS:
        customers = (
            customers.sample(n=DEVELOPMENT_CUSTOMERS, random_state=SEED)
            .sort_values("customer_id")
            .reset_index(drop=True)
        )

    customer_ids = set(customers["customer_id"])
    accounts = accounts[accounts["customer_id"].isin(customer_ids)].copy()

    # preserve leading zeroes if branches were parsed numerically elsewhere
    customers["primary_branch_id"] = customers["primary_branch_id"].astype(str).str.zfill(3)
    accounts["branch_id"] = accounts["branch_id"].astype(str).str.zfill(3)
    branches["branch_id"] = branches["branch_id"].astype(str).str.zfill(3)
    branch_state["branch_id"] = branch_state["branch_id"].astype(str).str.zfill(3)

    return customers, accounts, branches, products, branch_state


def validate_inputs(customers, accounts, branches, products, branch_state):
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

    catalog_ids = set(products["product_id"].astype(str))
    missing_products = set(PRODUCTS) - catalog_ids
    if missing_products:
        raise ValueError(
            f"products.csv does not contain required lending products: {sorted(missing_products)}"
        )

    state_required = {
        "branch_id",
        "year",
        "credit_pressure",
        "customer_pressure",
    }
    missing_state = state_required - set(branch_state.columns)
    if missing_state:
        raise ValueError(
            f"branch_yearly_state.csv missing columns: {sorted(missing_state)}"
        )

    if branch_state.duplicated(["branch_id", "year"]).any():
        raise ValueError("Duplicate branch_id/year in branch_yearly_state.csv.")

    branch_state["year"] = pd.to_numeric(branch_state["year"], errors="coerce")
    if branch_state["year"].isna().any():
        raise ValueError("Invalid year in branch_yearly_state.csv.")

    unknown_state_branches = (
        set(branch_state["branch_id"]) - set(branches["branch_id"])
    )
    if unknown_state_branches:
        raise ValueError(
            "branch_yearly_state.csv contains unknown branch_id values: "
            f"{sorted(unknown_state_branches)[:10]}"
        )

    for col in ["credit_pressure", "customer_pressure"]:
        if pd.to_numeric(branch_state[col], errors="coerce").isna().any():
            raise ValueError(
                f"Invalid numeric values in branch state column: {col}"
            )


# =============================================================================
# Generator
# =============================================================================

class LoanGenerator:
    def __init__(self, customers, accounts, branches, products, branch_state):
        self.customers = customers.copy()
        self.accounts = accounts.copy()
        self.branches = branches.copy()
        self.products = products.copy()
        self.branch_state = branch_state.copy()

        self.rng = np.random.default_rng(LOAN_SEED)
        self.history_rng = np.random.default_rng(LOAN_SEED + 1)
        self.rows = []
        self.bridge_rows = []
        self.next_loan_number = 1

        self.branch_lookup = self.branches.set_index("branch_id").to_dict("index")
        self._prepare_branch_state()
        self._prepare_customer_signals()

    # ---------------------------------------------------------------------
    # Shared branch-state bridge
    # ---------------------------------------------------------------------

    def _prepare_branch_state(self):
        """
        Build the 2021-2026 branch-state lookup used by the lending DGP.

        Loans intentionally consume only credit pressure and customer pressure
        at the master-table stage. Operational pressure and local shocks are
        reserved for the monthly snapshot where their timing can affect
        arrears and deterioration explicitly.
        """
        state = self.branch_state.copy()
        state["year"] = pd.to_numeric(state["year"], errors="raise").astype(int)

        for col in ["credit_pressure", "customer_pressure"]:
            state[col] = pd.to_numeric(state[col], errors="raise").astype(float)

        self.branch_state_lookup = {
            (str(row.branch_id).zfill(3), int(row.year)): {
                "credit_pressure": float(row.credit_pressure),
                "customer_pressure": float(row.customer_pressure),
            }
            for row in state.itertuples(index=False)
        }

    def _get_branch_state(self, branch_id: str, year: int) -> dict:
        neutral = {
            "credit_pressure": 0.0,
            "customer_pressure": 0.0,
        }

        if year < OBSERVATION_START_YEAR:
            return neutral

        return self.branch_state_lookup.get(
            (str(branch_id).zfill(3), int(year)),
            neutral,
        )

    def _customer_local_state(self, row, year: int) -> dict:
        """
        Use the customer's primary branch as the local credit environment
        before an actual origination branch has been selected.
        """
        primary = str(row["primary_branch_id"]).zfill(3)
        return self._get_branch_state(primary, year)

    # ---------------------------------------------------------------------
    # Customer signals
    # ---------------------------------------------------------------------

    def _prepare_customer_signals(self):
        c = self.customers

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

        common_noise = self.rng.normal(0, 1, len(c))
        specific_noise = self.rng.normal(0, 1, (len(c), 5))

        tenure = (CURRENT_YEAR - pd.to_numeric(c["registration_year"], errors="coerce")).clip(lower=0)
        tenure_z = (tenure - tenure.mean()) / max(tenure.std(ddof=0), 1)

        relation_score = (
            0.38 * np.log1p(c["account_count"])
            + 0.28 * np.log1p(c["active_account_count"])
            + 0.24 * np.log1p(c["product_breadth"])
            + 0.16 * tenure_z
            + 0.33 * common_noise
            + 0.34 * specific_noise[:, 0]
        )
        c["_relationship"] = sigmoid(relation_score)

        digital_score = (
            1.35 * c["digital_share"]
            + 0.18 * np.maximum(0, 45 - (CURRENT_YEAR - pd.to_numeric(c["birth_year"], errors="coerce").fillna(1980))) / 20
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

        # Demand and capacity are deliberately distinct.
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

        # Persistent but noisy repayment-stress propensity.
        # Higher means more vulnerability; it is NOT a deterministic risk score.
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
    # Product utilities and origination
    # ---------------------------------------------------------------------

    def _product_utility(self, row, product: LoanProduct, year: int) -> float:
        is_individual = row["customer_type"] == "INDIVIDUAL"

        utility = (
            product.demand_intercept
            + 1.20 * row["_loan_demand"]
            + 0.88 * row["_capacity"]
            + 0.44 * row["_relationship"]
            + self.rng.normal(0, 0.70)
        )

        if product.product_id == "P012":
            utility += 0.25
        elif product.product_id == "P013":
            utility += 0.28 * row["_capacity"]
        elif product.product_id == "P014":
            age = CURRENT_YEAR - row["birth_year"] if pd.notna(row["birth_year"]) else 40
            age_hump = np.exp(-((age - 38) / 15) ** 2)
            utility += 0.75 * row["_capacity"] + 0.65 * age_hump
        elif product.product_id == "P015":
            utility += 0.30 * row["_capacity"]
        elif product.product_id == "P016":
            utility += 0.52 * row["_relationship"] + 0.38 * row["_capacity"]
        elif product.product_id == "P017":
            sector = str(row.get("business_sector", "")).upper()
            agro = any(token in sector for token in ["AGRI", "GANAD", "RURAL", "FOREST"])
            utility += 1.15 if agro else -0.65
        elif product.product_id == "P018":
            size = str(row.get("company_size", "")).upper()
            utility += {"MICRO": -0.20, "SMALL": 0.15, "MEDIUM": 0.50, "LARGE": 0.75}.get(size, 0)

        # Temporary macro demand shocks.
        macro = {
            2020: -0.35,
            2021: -0.10,
            2022: 0.10,
            2023: 0.05,
            2024: 0.14,
            2025: 0.18,
            2026: 0.20,
        }.get(year, 0.0)
        utility += macro

        return float(utility)

    def _annual_product_probability(self, row, product: LoanProduct, year: int) -> float:
        utility = self._product_utility(row, product, year)

        if year >= OBSERVATION_START_YEAR:
            state = self._customer_local_state(row, year)

            # Credit pressure is a local supply/origination condition, not a
            # hidden borrower-risk score. Customer pressure adds only a small
            # relationship/acquisition effect.
            utility -= 0.22 * np.clip(
                state["credit_pressure"], -2.5, 2.5
            )
            utility -= 0.06 * np.clip(
                state["customer_pressure"], -2.5, 2.5
            )

        # Annual probability is intentionally moderate.
        return float(np.clip(sigmoid(utility) * 0.34, 0.002, 0.33))

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

        # Primary branch is likely but not guaranteed.
        weights *= np.where(eligible["branch_id"].eq(primary), 4.6, 1.0)

        # Same department and region.
        cust_dept = str(row.get("residence_department", ""))
        weights *= np.where(eligible["department"].astype(str).eq(cust_dept), 2.0, 1.0)

        if primary in self.branch_lookup:
            primary_region = str(self.branch_lookup[primary].get("region", ""))
            weights *= np.where(eligible["region"].astype(str).eq(primary_region), 1.35, 1.0)

        # Larger offices have somewhat more lending volume.
        size_factor = eligible["branch_size"].astype(str).str.upper().map({
            "SMALL": 0.90,
            "MEDIUM": 1.10,
            "LARGE": 1.35,
        }).fillna(1.0).to_numpy()
        weights *= size_factor

        # Product-specific branch tendencies.
        if product_id == "P017":
            interior = ~eligible["department"].astype(str).eq("Montevideo")
            weights *= np.where(interior, 1.35, 0.75)
            weights *= np.where(eligible["region"].astype(str).str.upper().eq("EAST"), 1.22, 1.0)

        if product_id in {"P015", "P016", "P018"}:
            weights *= np.where(eligible["branch_size"].astype(str).str.upper().eq("LARGE"), 1.18, 1.0)

        # Digital affinity weakens geographic concentration.
        if row["_digital_affinity"] > 0.65:
            weights = np.power(weights, 0.78)

        if year >= OBSERVATION_START_YEAR:
            credit_pressure = np.array(
                [
                    self._get_branch_state(branch_id, year)["credit_pressure"]
                    for branch_id in eligible["branch_id"]
                ],
                dtype=float,
            )

            # Higher credit pressure modestly reduces the branch's origination
            # attractiveness while preserving geography, size, and product
            # specialization as the dominant branch-selection drivers.
            weights *= np.exp(
                -0.16 * np.clip(credit_pressure, -2.5, 2.5)
            )

        weights *= self.rng.lognormal(mean=0.0, sigma=0.18, size=len(weights))
        weights /= weights.sum()

        return str(self.rng.choice(eligible["branch_id"].to_numpy(), p=weights))

    # ---------------------------------------------------------------------
    # Contract characteristics
    # ---------------------------------------------------------------------

    def _choose_currency(self, row, product: LoanProduct) -> str:
        p_usd = product.usd_base
        p_usd += 0.28 * (row["_usd_affinity"] - 0.5)

        if row["customer_type"] == "BUSINESS":
            sector = str(row.get("business_sector", "")).upper()
            if any(token in sector for token in ["AGRI", "GANAD", "FOREST", "EXPORT"]):
                p_usd += 0.12

        p_usd = float(np.clip(p_usd, 0.01, 0.88))
        return "USD" if self.rng.random() < p_usd else "UYU"

    def _amount(self, row, product: LoanProduct, currency: str) -> float:
        capacity = row["_capacity"]
        relationship = row["_relationship"]

        if row["customer_type"] == "INDIVIDUAL":
            economic_z = float(row["_income_z"]) if pd.notna(row["_income_z"]) else 0.0
        else:
            economic_z = float(row["_revenue_z"]) if pd.notna(row["_revenue_z"]) else 0.0

        log_shift = (
            0.34 * economic_z
            + 0.34 * (capacity - 0.5)
            + 0.14 * (relationship - 0.5)
            + self.rng.normal(0, product.amount_sigma)
        )

        amount_uyu = product.amount_median_uyu * np.exp(log_shift)

        # broad plausibility guards, not targets
        amount_uyu = np.clip(amount_uyu, 25_000, 150_000_000)

        if currency == "USD":
            # Synthetic conversion anchor only for nominal scale generation.
            usd_rate = {
                year: 37.0 + 0.9 * max(0, year - 2018)
                for year in range(1990, CURRENT_YEAR + 1)
            }
            # Use current-ish anchor for scale, not an accounting conversion.
            fx = usd_rate[CURRENT_YEAR]
            amount = amount_uyu / fx
        else:
            amount = amount_uyu

        return round_money(float(amount))

    def _choose_term(self, row, product: LoanProduct, amount: float) -> int:
        options = np.array(product.term_options, dtype=int)

        # Larger loans mildly shift probability toward longer terms.
        pos = np.linspace(-1.0, 1.0, len(options))
        amount_scale = np.log1p(amount)
        center = np.median(np.log1p([product.amount_median_uyu]))
        score = 0.35 * pos * (amount_scale - center)
        score += self.rng.normal(0, 0.22, len(options))

        # credit line contract horizons are not amortization terms
        if product.product_id == "P016":
            score += np.array([0.45, 0.15, -0.10])

        probs = softmax(score)
        return int(self.rng.choice(options, p=probs))

    def _choose_rate_type(self, row, product: LoanProduct, currency: str, term: int) -> str:
        weights = np.array([
            product.fixed_weight,
            product.variable_weight,
            product.mixed_weight,
        ], dtype=float)

        if term >= 120:
            weights *= np.array([0.78, 1.16, 1.22])
        if currency == "USD":
            weights *= np.array([0.90, 1.12, 1.04])

        weights *= self.rng.lognormal(0, 0.10, 3)
        weights /= weights.sum()
        return str(self.rng.choice(["FIXED", "VARIABLE", "MIXED"], p=weights))

    def _initial_rate(
        self,
        row,
        product: LoanProduct,
        year: int,
        currency: str,
        term: int,
        rate_type: str,
    ) -> float:
        base = (UYU_BASE_RATE if currency == "UYU" else USD_BASE_RATE).get(
            year,
            12.0 if currency == "UYU" else 6.5,
        )

        spread = PRODUCT_SPREAD[product.product_id]

        capacity_adjustment = -2.0 * (row["_capacity"] - 0.5)
        relationship_adjustment = -0.9 * (row["_relationship"] - 0.5)
        term_adjustment = 0.55 * np.log1p(term / 12)
        type_adjustment = {"FIXED": 0.45, "VARIABLE": -0.20, "MIXED": 0.10}[rate_type]
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
    # Lifecycle
    # ---------------------------------------------------------------------

    def _monthly_payment(self, principal: float, annual_rate_pct: float, months: int) -> float:
        if months <= 0:
            return principal
        r = annual_rate_pct / 100 / 12
        if r <= 0:
            return principal / months
        return principal * r / (1 - (1 + r) ** (-months))

    def _simulate_lifecycle(
        self,
        row,
        product: LoanProduct,
        origination_year: int,
        amount: float,
        currency: str,
        term_months: int,
        initial_rate: float,
    ) -> Tuple[str, Optional[int]]:
        """
        Coarse internal lifecycle used only to derive master-table status.

        This is intentionally NOT the final loan_monthly_snapshot engine.
        It preserves the causal order:
            contract -> payment burden/stress -> deterioration/recovery -> final status

        The future snapshot generator should replace/extend this with exact due dates,
        arrears ledgers, DPD and monthly balance reconciliation.
        """

        months_available = max(1, (CURRENT_YEAR - origination_year + 1) * 12)

        if product.kind == "REVOLVING":
            burden = 0.10 + 0.20 * self.rng.random()
        else:
            scheduled = self._monthly_payment(amount, initial_rate, term_months)
            if row["customer_type"] == "INDIVIDUAL":
                income = max(float(row.get("monthly_income") or 0), 1.0)
                burden = scheduled / income
            else:
                revenue = max(float(row.get("annual_revenue") or 0), 1.0)
                burden = (scheduled * 12) / revenue

        stress = (
            1.10 * row["_stress_propensity"]
            + 0.32 * np.clip(burden, 0, 3)
            + 0.14 * (currency == "USD")
            + 0.10 * (initial_rate / 25.0)
            + self.rng.normal(0, 0.28)
        )

        # Old installment loans that have exceeded scheduled maturity are
        # predominantly paid off unless a deterioration event occurred.
        scheduled_maturity_reached = (
            product.kind == "INSTALLMENT"
            and months_available >= term_months
        )

        severe_state = False
        restructured = False
        written_off = False

        # Annual deterioration/recovery dynamics.
        start_year = max(origination_year, OBSERVATION_START_YEAR)
        for year in range(start_year, CURRENT_YEAR + 1):
            macro_stress = {
                2021: 0.08,
                2022: 0.10,
                2023: 0.06,
                2024: 0.02,
                2025: 0.00,
                2026: -0.02,
            }.get(year, 0.0)

            p_deteriorate = sigmoid(
                -4.00
                + 2.20 * stress
                + macro_stress
                + (0.28 if severe_state else 0.0)
                + self.rng.normal(0, 0.45)
            )

            if not severe_state and self.rng.random() < p_deteriorate:
                severe_state = True

            elif severe_state:
                p_recover = sigmoid(
                    0.55
                    + 0.70 * row["_capacity"]
                    + 0.35 * row["_relationship"]
                    - 1.05 * stress
                    + self.rng.normal(0, 0.35)
                )
                if self.rng.random() < p_recover:
                    severe_state = False
                else:
                    p_restructure = sigmoid(
                        -3.0
                        + 1.25 * row["_relationship"]
                        + 1.30 * stress
                        + self.rng.normal(0, 0.35)
                    )
                    if not restructured and self.rng.random() < p_restructure:
                        restructured = True

                    p_writeoff = sigmoid(
                        -5.35
                        + 2.20 * stress
                        + (0.60 if restructured else 0.0)
                        + self.rng.normal(0, 0.40)
                    )
                    if self.rng.random() < p_writeoff:
                        written_off = True
                        return "WRITTEN_OFF", year

        # If the customer closed before cutoff, active loans generally need resolution.
        customer_closed = row["customer_status"] == "CLOSED"
        customer_closing_year = row.get("closing_year")
        customer_closing_year = (
            int(customer_closing_year)
            if pd.notna(customer_closing_year)
            else None
        )

        if written_off:
            return "WRITTEN_OFF", CURRENT_YEAR

        if severe_state:
            if restructured:
                # original contract materially modified
                close_year = CURRENT_YEAR if self.rng.random() < 0.58 else None
                if close_year is not None:
                    return "RESTRUCTURED", close_year
                return "RESTRUCTURED", None
            close_year = CURRENT_YEAR if self.rng.random() < 0.46 else None
            return "DEFAULTED", close_year

        if scheduled_maturity_reached:
            months_since_orig = months_available
            maturity_year = min(
                CURRENT_YEAR,
                origination_year + int(np.ceil(term_months / 12)),
            )
            # Allow early payoff for some strong borrowers.
            early = (
                self.rng.random()
                < sigmoid(-2.45 + 1.2 * row["_capacity"] + 0.55 * row["_relationship"])
            )
            if early and maturity_year > origination_year:
                maturity_year = max(origination_year, maturity_year - int(self.rng.integers(1, 3)))
            return "PAID_OFF", maturity_year

        # P016 can expire/close and later be renewed as another contract.
        if product.product_id == "P016":
            horizon_year = origination_year + max(1, term_months // 12)
            if horizon_year <= CURRENT_YEAR and self.rng.random() < 0.62:
                return "PAID_OFF", min(CURRENT_YEAR, horizon_year)

        if customer_closed and customer_closing_year is not None:
            if origination_year <= customer_closing_year:
                return "PAID_OFF", customer_closing_year

        # Occasional early payoff despite scheduled maturity not yet reached.
        p_early_payoff = sigmoid(
            -3.40
            + 0.95 * row["_capacity"]
            + 0.42 * row["_relationship"]
            - 0.75 * stress
            + 0.03 * months_available
        )
        if self.rng.random() < p_early_payoff:
            closing_year = int(self.rng.integers(origination_year, CURRENT_YEAR + 1))
            if customer_closing_year is not None:
                closing_year = min(closing_year, customer_closing_year)
            return "PAID_OFF", closing_year

        return "ACTIVE", None

    # ---------------------------------------------------------------------
    # Generation loop
    # ---------------------------------------------------------------------

    def _new_loan_id(self) -> str:
        loan_id = f"L{self.next_loan_number:07d}"
        self.next_loan_number += 1
        return loan_id

    def _build_bridge_row(
        self,
        loan_id: str,
        origination_year: int,
        loan_status: str,
        closing_year: Optional[int],
        term_months: int,
        product_id: str,
    ) -> dict:
        """
        Build the hidden monthly lifecycle bridge without consuming the production
        loan RNG stream.

        The frozen loans.csv remains authoritative. Bridge fields refine annual
        master information into deterministic monthly metadata required by the
        snapshot engine; they never feed back into contract generation.
        """
        lifecycle_seed = int(
            (LOAN_SEED + int(loan_id[1:]) * 1_000_003) % (2**32 - 1)
        )
        bridge_rng = np.random.default_rng(lifecycle_seed)

        status = str(loan_status)
        close_year = (
            int(closing_year)
            if pd.notna(closing_year)
            else None
        )

        # Hidden monthly chronology must be capable of producing the frozen
        # annual lifecycle classification from real unpaid obligations.
        #
        # Same-year defaults need at least four full monthly steps between
        # origination and recognition. Same-year restructures need at least
        # two. This changes only hidden bridge timing; loans.csv is untouched.
        if status == "DEFAULTED" and close_year == origination_year:
            origination_month = int(bridge_rng.integers(1, 8))
        elif status == "RESTRUCTURED" and close_year == origination_year:
            origination_month = int(bridge_rng.integers(1, 11))
        elif origination_year == CURRENT_YEAR and status == "DEFAULTED":
            origination_month = int(bridge_rng.integers(1, 9))
        elif origination_year == CURRENT_YEAR and status == "RESTRUCTURED":
            origination_month = int(bridge_rng.integers(1, 11))
        else:
            origination_month = int(bridge_rng.integers(1, 13))

        origination_idx = origination_year * 12 + (origination_month - 1)
        resolution_month = ""
        terminal_event = ""
        inherited_state = "CURRENT"

        if origination_year < OBSERVATION_START_YEAR:
            inherited_draw = bridge_rng.random()

            # A loan already originated before the detailed observation window
            # and recognized as DEFAULTED during 2021 must enter January 2021
            # with enough inherited delinquency history to make that annual
            # lifecycle classification chronologically possible.
            #
            # Without this seam rule, an early-2021 default can enter the
            # monthly window with only one inherited missed installment, leaving
            # too little observable calendar time to exceed 90 DPD.
            if (
                status == "DEFAULTED"
                and close_year == OBSERVATION_START_YEAR
            ):
                inherited_state = "SEVERE_DELINQUENCY"
            elif status in {"DEFAULTED", "WRITTEN_OFF"}:
                inherited_state = (
                    "SEVERE_DELINQUENCY"
                    if inherited_draw < 0.72
                    else "EARLY_DELINQUENCY"
                )
            elif status == "RESTRUCTURED":
                inherited_state = (
                    "EARLY_DELINQUENCY"
                    if inherited_draw < 0.62
                    else "CURRENT"
                )
            else:
                inherited_state = (
                    "EARLY_DELINQUENCY"
                    if inherited_draw < 0.08
                    else "CURRENT"
                )

        if status == "PAID_OFF":
            close_year = int(closing_year) if pd.notna(closing_year) else CURRENT_YEAR
            close_month = int(bridge_rng.integers(1, 13))
            resolution_idx = close_year * 12 + (close_month - 1)
            resolution_idx = max(resolution_idx, origination_idx)
            resolution_year, resolution_m0 = divmod(resolution_idx, 12)
            resolution_month = f"{resolution_year:04d}-{resolution_m0 + 1:02d}"

            nominal_maturity_idx = origination_idx + int(term_months)
            if product_id == "P016":
                terminal_event = "FACILITY_EXPIRY"
            elif resolution_idx + 2 < nominal_maturity_idx:
                terminal_event = "EARLY_PREPAYMENT"
            else:
                terminal_event = "SCHEDULED_MATURITY"

        elif status == "WRITTEN_OFF":
            close_year = int(closing_year) if pd.notna(closing_year) else CURRENT_YEAR
            close_month = int(bridge_rng.integers(1, 13))
            resolution_idx = max(
                close_year * 12 + (close_month - 1),
                origination_idx,
            )
            resolution_year, resolution_m0 = divmod(resolution_idx, 12)
            resolution_month = f"{resolution_year:04d}-{resolution_m0 + 1:02d}"
            terminal_event = "WRITE_OFF"

        elif status == "RESTRUCTURED":
            if pd.notna(closing_year):
                close_year = int(closing_year)

                if close_year == origination_year:
                    min_close_month = min(origination_month + 2, 12)
                    close_month = int(
                        bridge_rng.integers(min_close_month, 13)
                    )
                else:
                    close_month = int(bridge_rng.integers(1, 13))

                resolution_idx = max(
                    close_year * 12 + (close_month - 1),
                    origination_idx,
                )
                resolution_year, resolution_m0 = divmod(resolution_idx, 12)
                resolution_month = f"{resolution_year:04d}-{resolution_m0 + 1:02d}"
                terminal_event = "RESTRUCTURE_AFTER_DEFAULT"
            else:
                terminal_event = "OPEN_SEVERE_AT_CUTOFF"

        elif status == "DEFAULTED":
            if pd.notna(closing_year):
                close_year = int(closing_year)

                if close_year == origination_year:
                    # Installment loans generally create their first contractual
                    # due date one month after origination. A five-month gap
                    # between origination and default recognition therefore gives
                    # the oldest genuinely unpaid installment enough calendar age
                    # to exceed 90 DPD even with a late due day.
                    min_close_month = min(origination_month + 5, 12)
                    close_month = int(
                        bridge_rng.integers(min_close_month, 13)
                    )
                else:
                    # Cross-year defaults must also allow enough real calendar
                    # time for the oldest unpaid obligation to age beyond 90 DPD.
                    #
                    # Example:
                    #   origination 2025-11 -> recognition no earlier than 2026-02
                    #   origination 2025-12 -> recognition no earlier than 2026-03
                    #
                    # DPD is still derived from actual unpaid obligations and due
                    # dates; it is never assigned directly.
                    close_year_start_idx = close_year * 12
                    minimum_resolution_idx = max(
                        close_year_start_idx,
                        origination_idx + 3,
                    )
                    min_close_month = (
                        minimum_resolution_idx - close_year_start_idx + 1
                    )
                    min_close_month = int(
                        np.clip(min_close_month, 1, 12)
                    )
                    close_month = int(
                        bridge_rng.integers(min_close_month, 13)
                    )

                resolution_idx = max(
                    close_year * 12 + (close_month - 1),
                    origination_idx,
                )
                resolution_year, resolution_m0 = divmod(resolution_idx, 12)
                resolution_month = f"{resolution_year:04d}-{resolution_m0 + 1:02d}"
                terminal_event = "SEVERE_RECOGNIZED_AT_CUTOFF"
            else:
                terminal_event = "OPEN_DEFAULT_AT_CUTOFF"

        else:
            terminal_event = "OPEN_CURRENT_AT_CUTOFF"

        return {
            "loan_id": loan_id,
            "origination_month_internal": (
                f"{origination_year:04d}-{origination_month:02d}"
            ),
            "lifecycle_seed": lifecycle_seed,
            "resolution_month_internal": resolution_month,
            "terminal_event_internal": terminal_event,
            "pre2021_inherited_state": inherited_state,
        }

    def _generate_contract(self, row, product: LoanProduct, year: int):
        branch_id = self._choose_branch(row, product.product_id, year)
        currency = self._choose_currency(row, product)
        amount = self._amount(row, product, currency)
        term = self._choose_term(row, product, amount)
        rate_type = self._choose_rate_type(row, product, currency, term)
        initial_rate = self._initial_rate(
            row, product, year, currency, term, rate_type
        )

        status, closing_year = self._simulate_lifecycle(
            row=row,
            product=product,
            origination_year=year,
            amount=amount,
            currency=currency,
            term_months=term,
            initial_rate=initial_rate,
        )

        loan_id = self._new_loan_id()

        self.rows.append({
            "loan_id": loan_id,
            "customer_id": row["customer_id"],
            "product_id": product.product_id,
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

        self.bridge_rows.append(
            self._build_bridge_row(
                loan_id=loan_id,
                origination_year=int(year),
                loan_status=status,
                closing_year=closing_year,
                term_months=int(term),
                product_id=product.product_id,
            )
        )

    def generate(self) -> pd.DataFrame:
        """
        Generates:
        1) compressed pre-2021 loan history
        2) detailed-window originations 2021–2026

        Repeated borrowing is allowed. Product/year outcomes are probabilistic.
        """

        for _, row in self.customers.iterrows():
            registration_year = int(row["registration_year"])
            customer_closing_year = (
                int(row["closing_year"])
                if pd.notna(row["closing_year"])
                else CURRENT_YEAR
            )

            eligible_products = [
                p for p in PRODUCTS.values()
                if p.target == row["customer_type"]
            ]

            # -------------------------
            # Pre-2021 historical hazard
            # -------------------------
            pre_start = max(
                registration_year,
                min(p.launch_year for p in eligible_products),
            )
            pre_end = min(
                OBSERVATION_START_YEAR - 1,
                customer_closing_year,
            )

            if pre_start <= pre_end:
                # V4.1.4 replaces the compressed count-plus-year allocator with
                # an annual origination hazard. Exposure is therefore handled
                # naturally: a customer registered in 2019 is exposed only to
                # 2019 and 2020, while a long-tenure customer is exposed to every
                # eligible historical year.
                #
                # Historical RNG is independent from the explicit 2021-2026 RNG
                # stream so historical calibration changes cannot mechanically
                # move the observed-period series.
                main_rng = self.rng
                self.rng = self.history_rng

                try:
                    for year in range(pre_start, pre_end + 1):
                        valid_products = [
                            p
                            for p in eligible_products
                            if p.launch_year <= year
                        ]
                        if not valid_products:
                            continue

                        years_in_relationship = year - registration_year + 1

                        # Smooth annual historical hazard.
                        #
                        # Calendar growth is deliberately mild because the
                        # expanding customer base already creates substantial
                        # aggregate growth. Relationship seasoning increases
                        # origination probability early in the relationship and
                        # then saturates.
                        hazard_utility = (
                            -1.92
                            + 0.58 * row["_loan_demand"]
                            + 0.28 * row["_relationship"]
                            + 0.018 * (year - 2020)
                            + 0.10
                            * np.log1p(
                                min(max(years_in_relationship, 1), 12)
                            )
                        )

                        if row["customer_type"] == "BUSINESS":
                            hazard_utility += 0.10

                        annual_hazard = float(
                            np.clip(
                                sigmoid(hazard_utility) * 0.92,
                                0.003,
                                0.240,
                            )
                        )

                        if self.rng.random() >= annual_hazard:
                            continue

                        utilities = np.array(
                            [
                                self._product_utility(row, p, year)
                                for p in valid_products
                            ]
                        )
                        product = valid_products[
                            int(
                                self.rng.choice(
                                    len(valid_products),
                                    p=softmax(utilities),
                                )
                            )
                        ]

                        self._generate_contract(
                            row,
                            product,
                            year,
                        )

                finally:
                    self.rng = main_rng

            # -------------------------
            # 2021–2026 originations
            # -------------------------
            for year in range(max(OBSERVATION_START_YEAR, registration_year), CURRENT_YEAR + 1):
                if year > customer_closing_year:
                    break

                for product in eligible_products:
                    if year < product.launch_year:
                        continue

                    p = self._annual_product_probability(row, product, year)

                    # Repeated borrowing in the same product remains possible,
                    # but existing contracts create a mild saturation effect.
                    existing_same = sum(
                        1 for r in self.rows
                        if r["customer_id"] == row["customer_id"]
                        and r["product_id"] == product.product_id
                        and r["origination_year"] <= year
                    )
                    p *= np.exp(-0.32 * existing_same)

                    if self.rng.random() < p:
                        self._generate_contract(row, product, year)

        loans = pd.DataFrame(self.rows, columns=LOAN_COLUMNS)
        return loans


# =============================================================================
# Validation
# =============================================================================

def validate_output(loans, customers, branches):
    errors = []

    if list(loans.columns) != LOAN_COLUMNS:
        errors.append(f"Column mismatch: {list(loans.columns)}")

    if loans["loan_id"].duplicated().any():
        errors.append("Duplicate loan_id values.")

    if not loans["loan_id"].astype(str).str.fullmatch(r"L\d{7}").all():
        errors.append("Invalid loan_id format.")

    valid_customers = set(customers["customer_id"])
    bad = ~loans["customer_id"].isin(valid_customers)
    if bad.any():
        errors.append(f"Invalid customer FK: {bad.sum()} rows.")

    valid_branches = set(branches["branch_id"])
    bad = ~loans["branch_id"].isin(valid_branches)
    if bad.any():
        errors.append(f"Invalid branch FK: {bad.sum()} rows.")

    if not loans["product_id"].isin(PRODUCTS.keys()).all():
        errors.append("Invalid lending product_id.")

    merged = loans.merge(
        customers[[
            "customer_id", "customer_type", "registration_year",
            "customer_status", "closing_year"
        ]],
        on="customer_id",
        how="left",
        suffixes=("", "_customer"),
    )

    product_target = {pid: p.target for pid, p in PRODUCTS.items()}
    target = merged["product_id"].map(product_target)
    bad = target.ne(merged["customer_type"])
    if bad.any():
        errors.append(f"Product/customer type incompatibility: {bad.sum()} rows.")

    launch = merged["product_id"].map({pid: p.launch_year for pid, p in PRODUCTS.items()})
    bad = merged["origination_year"] < launch
    if bad.any():
        errors.append(f"Origination before product launch: {bad.sum()} rows.")

    bad = merged["origination_year"] < pd.to_numeric(merged["registration_year"], errors="coerce")
    if bad.any():
        errors.append(f"Origination before customer registration: {bad.sum()} rows.")

    if not loans["currency"].isin(["UYU", "USD"]).all():
        errors.append("Invalid currency.")

    if (pd.to_numeric(loans["original_amount"], errors="coerce") <= 0).any():
        errors.append("Non-positive original_amount.")

    if (pd.to_numeric(loans["term_months"], errors="coerce") <= 0).any():
        errors.append("Non-positive term_months.")

    if not loans["rate_type"].isin(["FIXED", "VARIABLE", "MIXED"]).all():
        errors.append("Invalid rate_type.")

    if (pd.to_numeric(loans["initial_interest_rate"], errors="coerce") <= 0).any():
        errors.append("Non-positive initial_interest_rate.")

    valid_status = {"ACTIVE", "PAID_OFF", "DEFAULTED", "RESTRUCTURED", "WRITTEN_OFF"}
    if not loans["loan_status"].isin(valid_status).all():
        errors.append("Invalid loan_status.")

    active_with_closing = loans["loan_status"].eq("ACTIVE") & loans["closing_year"].notna()
    if active_with_closing.any():
        errors.append(f"ACTIVE loans with closing_year: {active_with_closing.sum()}.")

    paid_without_close = loans["loan_status"].isin(["PAID_OFF", "WRITTEN_OFF"]) & loans["closing_year"].isna()
    if paid_without_close.any():
        errors.append(
            f"PAID_OFF/WRITTEN_OFF loans without closing_year: {paid_without_close.sum()}."
        )

    has_close = loans["closing_year"].notna()
    if has_close.any():
        close = pd.to_numeric(loans.loc[has_close, "closing_year"], errors="coerce")
        orig = pd.to_numeric(loans.loc[has_close, "origination_year"], errors="coerce")
        if (close < orig).any():
            errors.append("closing_year before origination_year.")
        if (close > CURRENT_YEAR).any():
            errors.append("closing_year after 2026.")

    # Branch must have been open at origination.
    branch_meta = branches[["branch_id", "opening_year"]].copy()
    if "closing_year" in branches.columns:
        branch_meta["branch_closing_year"] = branches["closing_year"]
    else:
        branch_meta["branch_closing_year"] = np.nan

    chk = loans.merge(branch_meta, on="branch_id", how="left")
    if (chk["origination_year"] < pd.to_numeric(chk["opening_year"], errors="coerce")).any():
        errors.append("Loan originated before branch opening.")

    branch_close = pd.to_numeric(chk["branch_closing_year"], errors="coerce")
    bad = branch_close.notna() & (chk["origination_year"] > branch_close)
    if bad.any():
        errors.append(f"Loan originated after branch closure: {bad.sum()} rows.")

    if errors:
        print("\nVALIDATION: FAIL")
        for e in errors:
            print(" -", e)
        raise AssertionError("Loan validation failed.")

    print("\nVALIDATION: PASS")


# =============================================================================
# Audit
# =============================================================================

def audit(loans, customers):
    print("\n" + "=" * 72)
    print("BTYT LOANS AUDIT — V4.1.4 FINAL BRANCH-STATE INTEGRATED")
    print("=" * 72)

    print(f"\nCustomers in dev population: {len(customers):,}")
    print(f"Loans generated: {len(loans):,}")

    holders = loans["customer_id"].nunique()
    print(f"Customers with >=1 loan: {holders:,} ({holders / len(customers):.2%})")

    if len(loans):
        counts = loans.groupby("customer_id").size()
        print(f"Mean loans per borrower: {counts.mean():.2f}")
        print(f"Median loans per borrower: {counts.median():.0f}")
        print(f"P95 loans per borrower: {counts.quantile(.95):.0f}")
        print(f"Max loans per borrower: {counts.max():.0f}")

        print("\nLoans by product:")
        print(loans["product_id"].value_counts().sort_index())

        print("\nLoan status:")
        print((loans["loan_status"].value_counts(normalize=True) * 100).round(2).astype(str) + "%")

        print("\nCurrency by product (%):")
        print(
            pd.crosstab(
                loans["product_id"], loans["currency"], normalize="index"
            ).mul(100).round(1)
        )

        print("\nRate type by product (%):")
        print(
            pd.crosstab(
                loans["product_id"], loans["rate_type"], normalize="index"
            ).mul(100).round(1)
        )

        print("\nOrigination years:")
        print(loans["origination_year"].value_counts().sort_index())

        print("\nOriginal amount summary by product:")
        print(
            loans.groupby(["product_id", "currency"])["original_amount"]
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
            loans.groupby(["product_id", "currency"])["initial_interest_rate"]
            .agg(["count", "median", "mean", "min", "max"])
            .round(2)
        )

        print("\nStatus by vintage (%):")
        bins = [1990, 2000, 2010, 2020, 2026]
        labels = ["<=2000", "2001-2010", "2011-2020", "2021-2026"]
        vintage = pd.cut(loans["origination_year"], bins=bins, labels=labels, include_lowest=True)
        print(
            pd.crosstab(vintage, loans["loan_status"], normalize="index")
            .mul(100)
            .round(1)
        )


def audit_history_observation_seam(loans):
    """
    Diagnostic for the compressed-history / explicit-observation boundary.

    This is descriptive only. It makes the 2018-2022 transition visible so an
    artificial 2020 endpoint spike cannot pass unnoticed.
    """
    seam = loans.loc[
        loans["origination_year"].between(2018, 2022)
    ].copy()

    if seam.empty:
        return

    counts = (
        seam["origination_year"]
        .value_counts()
        .sort_index()
        .reindex(range(2018, 2023), fill_value=0)
    )

    print("\n" + "=" * 72)
    print("HISTORY / OBSERVATION SEAM AUDIT — LOANS V4.1.4")
    print("=" * 72)
    print("\nOriginations 2018-2022:")
    print(counts.to_string())

    if counts.loc[2019] > 0 and counts.loc[2021] > 0:
        print(
            "\n2020 vs 2019: "
            f"{(counts.loc[2020] / counts.loc[2019] - 1.0):+.1%}"
        )
        seam_change = counts.loc[2021] / counts.loc[2020] - 1.0

        print(
            "2021 vs 2020: "
            f"{seam_change:+.1%}"
        )

        seam_pass = abs(seam_change) <= 0.25
        print(
            "Seam guardrail (absolute change <= 25%): "
            f"{'PASS' if seam_pass else 'REVIEW'}"
        )

    print("\nProducts around the seam:")
    print(
        pd.crosstab(
            seam["origination_year"],
            seam["product_id"],
        ).to_string()
    )


def audit_branch_state_integration(
    loans,
    customers,
    branch_state,
):
    """
    Report whether branch-state credit conditions are visible in 2021-2026
    originations without treating them as deterministic risk labels.
    """
    observed = loans.loc[
        loans["origination_year"].between(
            OBSERVATION_START_YEAR,
            CURRENT_YEAR,
        )
    ].copy()

    if observed.empty:
        return

    state = branch_state.copy()
    state["branch_id"] = state["branch_id"].astype(str).str.zfill(3)
    state["year"] = pd.to_numeric(
        state["year"],
        errors="coerce",
    ).astype("Int64")

    merged = observed.merge(
        state[
            [
                "branch_id",
                "year",
                "credit_pressure",
                "customer_pressure",
            ]
        ],
        left_on=["branch_id", "origination_year"],
        right_on=["branch_id", "year"],
        how="left",
        validate="many_to_one",
    )

    print("\n" + "=" * 72)
    print("BRANCH-STATE INTEGRATION AUDIT — LOANS V4.1.4")
    print("=" * 72)
    print(
        "Observed originations linked to branch state: "
        f"{merged['year'].notna().mean():.2%}"
    )

    print("\nMean branch state at origination by product:")
    print(
        merged.groupby("product_id")[
            ["credit_pressure", "customer_pressure"]
        ]
        .mean()
        .round(3)
        .to_string()
    )

    print("\nMean branch state at origination by year:")
    print(
        merged.groupby("origination_year")[
            ["credit_pressure", "customer_pressure"]
        ]
        .mean()
        .round(3)
        .to_string()
    )

    # Credit-pressure quartiles provide a simple directional check on the
    # branch-selection effect. This is descriptive only and is not a hard
    # validation rule because branch size and customer geography still matter.
    branch_year = (
        merged.groupby(
            ["branch_id", "origination_year"],
            as_index=False,
        )
        .agg(
            originations=("loan_id", "size"),
            credit_pressure=("credit_pressure", "first"),
            customer_pressure=("customer_pressure", "first"),
        )
    )

    if branch_year["credit_pressure"].notna().sum() >= 4:
        branch_year["credit_pressure_quartile"] = pd.qcut(
            branch_year["credit_pressure"],
            4,
            labels=["Q1_LOW", "Q2", "Q3", "Q4_HIGH"],
            duplicates="drop",
        )

        print("\nOriginations by credit-pressure quartile:")
        print(
            branch_year.groupby(
                "credit_pressure_quartile",
                observed=False,
            )["originations"]
            .agg(["count", "mean", "median", "sum"])
            .round(2)
            .to_string()
        )


# =============================================================================
# Main
# =============================================================================

def main():
    print("Loading inputs...")
    customers, accounts, branches, products, branch_state = load_inputs()
    validate_inputs(
        customers,
        accounts,
        branches,
        products,
        branch_state,
    )

    print(f"Customers: {len(customers):,}")
    print(f"Accounts: {len(accounts):,}")
    print(f"Branches: {len(branches):,}")

    generator = LoanGenerator(
        customers,
        accounts,
        branches,
        products,
        branch_state,
    )

    print("\nGenerating loans...")
    loans = generator.generate()

    bridge = pd.DataFrame(
        generator.bridge_rows,
        columns=[
            "loan_id",
            "origination_month_internal",
            "lifecycle_seed",
            "resolution_month_internal",
            "terminal_event_internal",
            "pre2021_inherited_state",
        ],
    )

    if len(bridge) != len(loans):
        raise ValueError(
            f"Bridge row count mismatch: loans={len(loans):,}, bridge={len(bridge):,}"
        )
    if bridge["loan_id"].duplicated().any():
        raise ValueError("loan_lifecycle_bridge contains duplicate loan_id values.")
    if set(bridge["loan_id"]) != set(loans["loan_id"]):
        raise ValueError("loan_lifecycle_bridge loan_id set does not match loans.csv.")

    validate_output(loans, customers, branches)
    audit(loans, customers)
    audit_history_observation_seam(loans)
    audit_branch_state_integration(
        loans,
        customers,
        branch_state,
    )

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    DATA_INTERIM.mkdir(parents=True, exist_ok=True)

    loans.to_csv(OUTPUT_PATH, index=False)
    bridge.to_csv(BRIDGE_PATH, index=False)

    print(f"\nSaved: {OUTPUT_PATH}")
    print(f"Shape: {loans.shape}")
    print(f"Saved bridge: {BRIDGE_PATH}")
    print(f"Bridge shape: {bridge.shape}")
    print("Bridge/master synchronization: PASS")


if __name__ == "__main__":
    main()