from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import numpy as np
import pandas as pd

from scripts.core.paths import (
    GENERATED_DATA_DIR,
    GENERATED_CORE_DIR,
    GENERATED_CREDIT_DIR,
    GENERATED_PERFORMANCE_DIR,
    GENERATED_TRANSACTIONS_DIR,
    INTERIM_DATA_DIR,
    INTERIM_CREDIT_DIR,
    INTERIM_WORLD_DIR,
    WORLD_CONFIG_PATH,
)
from scripts.core.rng import make_rng


# =============================================================================
# BTYT BANKING ANALYTICS — BRANCH PERFORMANCE ENGINE
# =============================================================================
#
# Builds a monthly management-accounting layer from the frozen BTYT datasets.
# It does not regenerate or modify upstream canonical data.
#
# V3 cost architecture:
#   structural drivers
#   -> component-specific probability bands
#   -> persistent branch/component profile draws
#   -> wage/price/workload/cost-pressure dynamics
#   -> independent monthly mean-reverting shocks
#   -> realized operating costs and profitability KPIs
#
# No Cost-to-Income target or profitability band is imposed.
#
# V3.2 accounting and cost architecture:
# - direct personnel cost includes a baseline employer social-security burden;
# - branch P&L is fully loaded with probabilistic allocations of central/shared
#   banking services (technology, compliance, audit, HR, legal, treasury
#   operations, cybersecurity, data and other network support);
# - shared-service allocations are distributed across the existing cost
#   components rather than forcing any final component percentage;
# - pre-tax income and corporate income-tax expense are explicitly modeled;
# - corporate tax is calculated on annual consolidated positive pre-tax income
#   and allocated back to profitable months/branches for management reporting;
# - no Cost-to-Income, Net Margin or component-share target is imposed.
#
# Outputs:
#   data/generated/performance/branch_monthly_performance.parquet
#   data/generated/performance/bank_monthly_performance.parquet
#
# All monetary outputs are expressed in UYU-equivalent.
# All code and comments are intentionally written in English.
# =============================================================================


# =============================================================================
# PROJECT PATHS
# =============================================================================

CUSTOMERS_CANDIDATES = [
    GENERATED_CORE_DIR / "customers.parquet",
    GENERATED_CORE_DIR / "customers.csv",
    GENERATED_DATA_DIR / "customers.parquet",
    GENERATED_DATA_DIR / "customers.csv",
]

ACCOUNTS_CANDIDATES = [
    GENERATED_CORE_DIR / "accounts.parquet",
    GENERATED_CORE_DIR / "accounts.csv",
    GENERATED_DATA_DIR / "accounts.parquet",
    GENERATED_DATA_DIR / "accounts.csv",
]

CARDS_CANDIDATES = [
    GENERATED_CREDIT_DIR / "cards.parquet",
    GENERATED_CORE_DIR / "cards.parquet",
    GENERATED_CREDIT_DIR / "cards.csv",
    GENERATED_CORE_DIR / "cards.csv",
    GENERATED_DATA_DIR / "cards.parquet",
    GENERATED_DATA_DIR / "cards.csv",
]

LOANS_CANDIDATES = [
    GENERATED_CORE_DIR / "loans.parquet",
    GENERATED_CREDIT_DIR / "loans.parquet",
    GENERATED_CORE_DIR / "loans.csv",
    GENERATED_CREDIT_DIR / "loans.csv",
    GENERATED_DATA_DIR / "loans.parquet",
    GENERATED_DATA_DIR / "loans.csv",
]

LOAN_SNAPSHOT_CANDIDATES = [
    GENERATED_CREDIT_DIR / "loan_monthly_snapshot.parquet",
    GENERATED_CREDIT_DIR / "loan_monthly_snapshot.csv",
    GENERATED_DATA_DIR / "loan_monthly_snapshot.parquet",
    GENERATED_DATA_DIR / "loan_monthly_snapshot.csv",
]

TRANSACTIONS_CANDIDATES = [
    GENERATED_TRANSACTIONS_DIR / "transactions.parquet",
    GENERATED_TRANSACTIONS_DIR / "transactions.csv",
    GENERATED_DATA_DIR / "transactions.parquet",
    GENERATED_DATA_DIR / "transactions.csv",
]

ACCOUNT_BALANCES_CANDIDATES = [
    GENERATED_CORE_DIR / "account_balances.parquet",
    GENERATED_CORE_DIR / "account_balances.csv",
    GENERATED_TRANSACTIONS_DIR / "account_balances.parquet",
    GENERATED_TRANSACTIONS_DIR / "account_balances.csv",
    GENERATED_DATA_DIR / "account_balances.parquet",
    GENERATED_DATA_DIR / "account_balances.csv",
]

BRANCHES_CANDIDATES = [
    GENERATED_CORE_DIR / "branches.csv",
    GENERATED_CORE_DIR / "branches.parquet",
    GENERATED_DATA_DIR / "branches.csv",
    GENERATED_DATA_DIR / "branches.parquet",
]

BRANCH_STATE_CANDIDATES = [
    INTERIM_WORLD_DIR / "branch_yearly_state.csv",
    INTERIM_WORLD_DIR / "branch_yearly_state.parquet",
    INTERIM_DATA_DIR / "branch_yearly_state.csv",
    INTERIM_DATA_DIR / "branch_yearly_state.parquet",
]

LOAN_LIFECYCLE_BRIDGE_CANDIDATES = [
    INTERIM_CREDIT_DIR / "loan_lifecycle_bridge.csv",
    INTERIM_CREDIT_DIR / "loan_lifecycle_bridge.parquet",
    INTERIM_DATA_DIR / "loan_lifecycle_bridge.csv",
    INTERIM_DATA_DIR / "loan_lifecycle_bridge.parquet",
]

PRODUCTS_CANDIDATES = [
    GENERATED_CORE_DIR / "products.csv",
    GENERATED_CORE_DIR / "products.parquet",
    GENERATED_DATA_DIR / "products.csv",
    GENERATED_DATA_DIR / "products.parquet",
]

BRANCH_OUTPUT_PATH = GENERATED_PERFORMANCE_DIR / "branch_monthly_performance.parquet"
BANK_OUTPUT_PATH = GENERATED_PERFORMANCE_DIR / "bank_monthly_performance.parquet"
BRANCH_OUTPUT_CSV_PATH = GENERATED_PERFORMANCE_DIR / "branch_monthly_performance.csv"
BANK_OUTPUT_CSV_PATH = GENERATED_PERFORMANCE_DIR / "bank_monthly_performance.csv"

ENGINE_VERSION = "3.3.0"
RNG_NAMESPACE = "branch_performance"
REPORTING_CURRENCY = "UYU"
TRANSACTION_BATCH_SIZE = 500_000


# =============================================================================
# WORLD CONFIGURATION
# =============================================================================

def load_world_settings() -> tuple[int, pd.Period, pd.Period]:
    with WORLD_CONFIG_PATH.open("r", encoding="utf-8") as handle:
        config = json.load(handle)

    world_seed = int(config["world"]["seed"])
    observation = config["observation_period"]
    obs_start = pd.Period(observation["start_date"], freq="M")
    obs_end = pd.Period(observation["end_date"], freq="M")

    if obs_end < obs_start:
        raise ValueError("World observation end date precedes start date.")

    return world_seed, obs_start, obs_end


WORLD_SEED, OBS_START, OBS_END = load_world_settings()
MONTHS = pd.period_range(OBS_START, OBS_END, freq="M")
YEARS = tuple(range(OBS_START.year, OBS_END.year + 1))


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

# Baseline employer-side social-security burden used by the synthetic engine.
# It covers the stable statutory components used for the model:
# retirement 7.5%, Fonasa 5.0%, FRL 0.10%, and the labor-credit guarantee
# contribution 0.025%. Variable CCM and activity-specific insurance are not
# hard-coded here because they depend on worker/activity details unavailable
# in the synthetic branch layer.
EMPLOYER_RETIREMENT_RATE = 0.075
EMPLOYER_FONASA_RATE = 0.050
EMPLOYER_FRL_RATE = 0.001
EMPLOYER_LABOR_GUARANTEE_RATE = 0.00025
EMPLOYER_SOCIAL_SECURITY_RATE = (
    EMPLOYER_RETIREMENT_RATE
    + EMPLOYER_FONASA_RATE
    + EMPLOYER_FRL_RATE
    + EMPLOYER_LABOR_GUARANTEE_RATE
)

# Fully-loaded management P&L:
# direct branch costs are complemented by central/network services that were
# not represented explicitly in V3.1. The central pool is intentionally
# calibrated above the V3.2 level because the previous fully-loaded P&L still
# produced unrealistically high consolidated net margins. The range below is
# a structural calibration, not a hard Cost-to-Income or Net-Margin target.
# Annual profitability is still allowed to emerge from revenue, credit losses,
# branch cost pressure, monthly shocks and the tax layer.
SHARED_SERVICES_ALLOCATION_RANGE = (2.45, 3.15)

# Shared/network intensity also reflects branch structure. Large full-service
# branches consume more central technology, compliance, treasury, HR, audit,
# cybersecurity and data capacity than small agencies. These are soft
# multipliers over the persistent branch-level allocation draw.
SHARED_SERVICES_SIZE_MULTIPLIER = {
    "SMALL": 0.92,
    "MEDIUM": 1.00,
    "LARGE": 1.08,
}

SHARED_SERVICES_TYPE_MULTIPLIER = {
    "AGENCY": 0.94,
    "BRANCH": 1.04,
}

# Center of the reporting allocation. The realized component mix is drawn
# independently for every branch around this center and normalized back to
# 100%, avoiding an artificial 45/10/20/25 split in every branch.
SHARED_SERVICES_COMPONENT_MIX = {
    "personnel": 0.45,
    "fixed": 0.10,
    "variable": 0.20,
    "operational": 0.25,
}
SHARED_SERVICES_COMPONENT_JITTER_RANGE = (0.88, 1.12)

# Diagnostic reference only. Generation does not solve backwards to these
# margins; the audit reports whether annual realized profitability falls in
# the intended broad banking range after the structural recalibration.
NET_MARGIN_DIAGNOSTIC_RANGE = (0.15, 0.30)

# Uruguay corporate income-tax assumption used for the synthetic bank P&L.
CORPORATE_INCOME_TAX_RATE = 0.25

# By default, the terminal audit shows technical validation only so that
# analytical findings remain for Power BI. Set the environment variable to
# "full" when a detailed business-result audit is explicitly desired.
AUDIT_DETAIL_LEVEL = os.getenv(
    "BTYT_PERFORMANCE_AUDIT_DETAIL",
    "technical",
).strip().lower()

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

# -----------------------------------------------------------------------------
# Probabilistic component-level cost profiles
# -----------------------------------------------------------------------------
# Each branch receives one persistent profile draw for each cost component.
# The four draws are independent apart from soft structural tilts coming from
# branch size, branch type, and (where economically relevant) location.
#
# IMPORTANT:
# - These are NOT Cost-to-Income targets.
# - No profitability KPI is constrained to a preselected interval.
# - The resulting Cost-to-Income emerges from revenue, risk, workload, branch
#   structure, profile draws, and the time-varying cost-pressure process.
#
# Personnel/fixed profile values are multipliers over their structural bases.
# Variable/operational profile values are shares of the rigid cost base
# (personnel + fixed) before workload and cost-pressure adjustments.

COST_BAND_ORDER = (
    "VERY_LOW",
    "LOW",
    "NORMAL",
    "HIGH",
    "VERY_HIGH",
)

COST_BAND_POSITIONS = np.array([-2.0, -1.0, 0.0, 1.0, 2.0], dtype=float)

COST_BAND_BASE_PROBABILITIES = {
    # Personnel is intentionally more likely to occupy the middle/high bands
    # on average. This is a probabilistic prior, not a required cost share.
    "personnel": {
        "VERY_LOW": 0.05,
        "LOW": 0.15,
        "NORMAL": 0.38,
        "HIGH": 0.28,
        "VERY_HIGH": 0.14,
    },
    "fixed": {
        "VERY_LOW": 0.10,
        "LOW": 0.20,
        "NORMAL": 0.40,
        "HIGH": 0.20,
        "VERY_HIGH": 0.10,
    },
    "variable": {
        "VERY_LOW": 0.12,
        "LOW": 0.26,
        "NORMAL": 0.40,
        "HIGH": 0.16,
        "VERY_HIGH": 0.06,
    },
    # Broad allocated overhead remains heterogeneous, but extreme high-cost
    # operational profiles are deliberately rarer than in V3.0.0.
    "operational": {
        "VERY_LOW": 0.15,
        "LOW": 0.30,
        "NORMAL": 0.38,
        "HIGH": 0.13,
        "VERY_HIGH": 0.04,
    },
}

COST_PROFILE_VALUE_RANGES = {
    # Multipliers over branch staffing cost. Personnel carries a larger
    # expected role in the operating-cost mix, while branches can still land
    # anywhere from unusually lean to unusually expensive.
    "personnel": {
        "VERY_LOW": (0.90, 1.20),
        "LOW": (1.20, 1.55),
        "NORMAL": (1.55, 2.10),
        "HIGH": (2.10, 2.90),
        "VERY_HIGH": (2.90, 4.00),
    },
    # Multipliers over branch fixed-cost base.
    "fixed": {
        "VERY_LOW": (0.55, 0.80),
        "LOW": (0.80, 1.10),
        "NORMAL": (1.10, 1.60),
        "HIGH": (1.60, 2.30),
        "VERY_HIGH": (2.30, 3.40),
    },
    # Shares of rigid_base, subsequently scaled by workload.
    "variable": {
        "VERY_LOW": (0.10, 0.20),
        "LOW": (0.20, 0.35),
        "NORMAL": (0.35, 0.60),
        "HIGH": (0.60, 0.90),
        "VERY_HIGH": (0.90, 1.30),
    },
    # Broad branch-allocated technology, administration, compliance, support,
    # and other operating overhead as a share of rigid_base. V3.1 reduces the
    # prior dominance of this component while preserving a long right tail.
    "operational": {
        "VERY_LOW": (0.12, 0.22),
        "LOW": (0.22, 0.35),
        "NORMAL": (0.35, 0.55),
        "HIGH": (0.55, 0.80),
        "VERY_HIGH": (0.80, 1.20),
    },
}

# Soft structural tilts. These change probabilities, never force a band.
COST_PROFILE_SIZE_SHIFT = {
    "personnel": {"SMALL": -0.10, "MEDIUM": 0.00, "LARGE": 0.12},
    "fixed": {"SMALL": -0.08, "MEDIUM": 0.00, "LARGE": 0.08},
    "variable": {"SMALL": -0.03, "MEDIUM": 0.00, "LARGE": 0.03},
    "operational": {"SMALL": -0.05, "MEDIUM": 0.00, "LARGE": 0.06},
}

COST_PROFILE_TYPE_SHIFT = {
    "personnel": {"AGENCY": -0.05, "BRANCH": 0.05},
    "fixed": {"AGENCY": -0.05, "BRANCH": 0.05},
    "variable": {"AGENCY": -0.02, "BRANCH": 0.02},
    "operational": {"AGENCY": -0.03, "BRANCH": 0.03},
}

# Location mainly affects fixed costs. A smaller tilt is retained for personnel
# and operational complexity; variable cost remains activity-driven.
COST_PROFILE_LOCATION_BETA = {
    "personnel": 0.08,
    "fixed": 0.35,
    "variable": 0.00,
    "operational": 0.08,
}

# Independent branch/component shocks prevent a branch from being mechanically
# "cheap in everything" or "expensive in everything".
COST_PROFILE_SHOCK_HALF_WIDTH = {
    "personnel": 0.28,
    "fixed": 0.32,
    "variable": 0.30,
    "operational": 0.34,
}


# -----------------------------------------------------------------------------
# Monthly mean-reverting cost dynamics
# -----------------------------------------------------------------------------
# Structural bands are persistent. Monthly costs are not.
#
# Each branch/component receives its own persistent AR(1)-style process
# parameters, drawn once from these ranges:
#
#   log_shock_t = phi * log_shock_(t-1) + innovation_t
#
# The innovation variance is scaled so that `sigma` represents the approximate
# long-run standard deviation of the log shock. The multiplicative monthly
# factor is exp(log_shock_t), so it can move above or below 1.0.
#
# IMPORTANT:
# - No monthly cost path is forced to increase.
# - Personnel/fixed costs still have long-run wage/price trends.
# - Variable costs additionally respond to actual monthly workload.
# - All four components have independent monthly processes.
# - These parameters control persistence/volatility, NOT Cost-to-Income.

MONTHLY_COST_PROCESS_RANGES = {
    # Relatively smooth, persistent payroll variation.
    "personnel": {
        "phi": (0.65, 0.90),
        "sigma": (0.015, 0.040),
    },
    # Sticky but slightly more volatile facility/infrastructure costs.
    "fixed": {
        "phi": (0.75, 0.95),
        "sigma": (0.020, 0.055),
    },
    # Activity-linked costs should react faster and fluctuate more.
    "variable": {
        "phi": (0.35, 0.70),
        "sigma": (0.050, 0.120),
    },
    # Technology, administration, compliance and support costs sit in between.
    "operational": {
        "phi": (0.50, 0.82),
        "sigma": (0.035, 0.090),
    },
}


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
    "pre_tax_income",
    "income_tax_expense",
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
    "pre_tax_income",
    "income_tax_expense",
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


def resolve_first_existing(paths: list[Path], label: str) -> Path:
    for path in paths:
        if path.exists():
            return path

    raise FileNotFoundError(
        f"Required input not found for {label}. Checked:\n"
        + "\n".join(f"  {path}" for path in paths)
    )


def read_table(path: Path, columns: list[str] | None = None) -> pd.DataFrame:
    """Read a BTYT table from Parquet or CSV."""
    require_file(path)

    suffix = path.suffix.lower()
    if suffix == ".parquet":
        return pd.read_parquet(path, columns=columns)
    if suffix == ".csv":
        return pd.read_csv(path, usecols=columns)

    raise ValueError(f"Unsupported table format: {path}")


def iter_transaction_batches(
    path: Path,
    columns: list[str],
    batch_size: int,
):
    """Yield transaction batches without loading the full fact table into memory."""
    require_file(path)

    suffix = path.suffix.lower()

    if suffix == ".parquet":
        import pyarrow.parquet as pq

        parquet_file = pq.ParquetFile(path)
        for batch in parquet_file.iter_batches(
            batch_size=batch_size,
            columns=columns,
        ):
            yield batch.to_pandas()
        return

    if suffix == ".csv":
        yield from pd.read_csv(
            path,
            usecols=columns,
            chunksize=batch_size,
            low_memory=False,
        )
        return

    raise ValueError(f"Unsupported transaction format: {path}")


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
    """Return a deterministic entity-local draw from the branch-performance namespace."""
    digest = hashlib.sha256(key.encode("utf-8")).digest()
    stream = int.from_bytes(digest[:4], byteorder="big", signed=False)
    rng = make_rng(WORLD_SEED, RNG_NAMESPACE, stream)
    return float(rng.uniform(low, high))


def stable_normal(key: str, mean: float = 0.0, std: float = 1.0) -> float:
    """Return a deterministic entity-local normal draw from the same namespace."""
    digest = hashlib.sha256(key.encode("utf-8")).digest()
    stream = int.from_bytes(digest[:4], byteorder="big", signed=False)
    rng = make_rng(WORLD_SEED, RNG_NAMESPACE, stream)
    return float(rng.normal(mean, std))


def draw_shared_services_component_mix(branch_id: str) -> dict[str, float]:
    """Draw a reproducible branch-specific shared-services reporting mix."""
    low, high = SHARED_SERVICES_COMPONENT_JITTER_RANGE
    raw = {
        component: base_share
        * stable_uniform(
            f"shared-services-mix|{component}|{branch_id}",
            low,
            high,
        )
        for component, base_share in SHARED_SERVICES_COMPONENT_MIX.items()
    }
    total = float(sum(raw.values()))
    if total <= 0.0:
        raise ValueError("Shared-services component mix produced a non-positive total.")
    return {component: value / total for component, value in raw.items()}


def validate_cost_profile_configuration() -> None:
    """Validate probabilistic cost-profile settings before generation."""
    shared_mix_sum = float(sum(SHARED_SERVICES_COMPONENT_MIX.values()))
    if abs(shared_mix_sum - 1.0) > 1e-12:
        raise ValueError(
            "SHARED_SERVICES_COMPONENT_MIX must sum to 1.0."
        )
    if not (0.0 <= CORPORATE_INCOME_TAX_RATE <= 1.0):
        raise ValueError(
            "CORPORATE_INCOME_TAX_RATE must be between 0 and 1."
        )
    if SHARED_SERVICES_ALLOCATION_RANGE[0] < 0.0:
        raise ValueError(
            "SHARED_SERVICES_ALLOCATION_RANGE cannot be negative."
        )
    if SHARED_SERVICES_ALLOCATION_RANGE[1] < SHARED_SERVICES_ALLOCATION_RANGE[0]:
        raise ValueError(
            "Invalid SHARED_SERVICES_ALLOCATION_RANGE."
        )
    for name, mapping in [
        ("SHARED_SERVICES_SIZE_MULTIPLIER", SHARED_SERVICES_SIZE_MULTIPLIER),
        ("SHARED_SERVICES_TYPE_MULTIPLIER", SHARED_SERVICES_TYPE_MULTIPLIER),
    ]:
        if any(float(value) <= 0.0 for value in mapping.values()):
            raise ValueError(f"{name} values must be positive.")
    jitter_low, jitter_high = SHARED_SERVICES_COMPONENT_JITTER_RANGE
    if jitter_low <= 0.0 or jitter_high < jitter_low:
        raise ValueError(
            "Invalid SHARED_SERVICES_COMPONENT_JITTER_RANGE."
        )
    margin_low, margin_high = NET_MARGIN_DIAGNOSTIC_RANGE
    if not (0.0 <= margin_low < margin_high <= 1.0):
        raise ValueError("Invalid NET_MARGIN_DIAGNOSTIC_RANGE.")
    expected_components = {"personnel", "fixed", "variable", "operational"}
    if set(COST_BAND_BASE_PROBABILITIES) != expected_components:
        raise ValueError("COST_BAND_BASE_PROBABILITIES must cover all cost components.")
    if set(COST_PROFILE_VALUE_RANGES) != expected_components:
        raise ValueError("COST_PROFILE_VALUE_RANGES must cover all cost components.")

    for component in sorted(expected_components):
        probs = COST_BAND_BASE_PROBABILITIES[component]
        ranges = COST_PROFILE_VALUE_RANGES[component]

        if tuple(probs) != COST_BAND_ORDER:
            raise ValueError(
                f"{component} probability bands must follow COST_BAND_ORDER."
            )
        if tuple(ranges) != COST_BAND_ORDER:
            raise ValueError(
                f"{component} value ranges must follow COST_BAND_ORDER."
            )

        total_probability = float(sum(probs.values()))
        if not np.isclose(total_probability, 1.0, atol=1e-12):
            raise ValueError(
                f"{component} base band probabilities sum to "
                f"{total_probability:.12f}, expected 1.0."
            )

        for band, probability in probs.items():
            if probability < 0.0:
                raise ValueError(
                    f"{component}/{band} has a negative probability."
                )

        for band, (low, high) in ranges.items():
            if low < 0.0 or high <= low:
                raise ValueError(
                    f"Invalid {component}/{band} value range: {(low, high)}."
                )

        if component not in MONTHLY_COST_PROCESS_RANGES:
            raise ValueError(
                f"Missing monthly cost-process configuration for {component}."
            )

        process = MONTHLY_COST_PROCESS_RANGES[component]
        phi_low, phi_high = process["phi"]
        sigma_low, sigma_high = process["sigma"]

        if not (0.0 <= phi_low < phi_high < 1.0):
            raise ValueError(
                f"Invalid {component} phi range: {(phi_low, phi_high)}."
            )
        if not (0.0 < sigma_low < sigma_high):
            raise ValueError(
                f"Invalid {component} sigma range: {(sigma_low, sigma_high)}."
            )


def cost_profile_probabilities(
    component: str,
    branch_id: str,
    branch_size: str,
    branch_type: str,
    location_multiplier: float,
) -> tuple[np.ndarray, float]:
    """
    Return branch-specific probabilities for one cost component.

    Structural characteristics only tilt the common base distribution. An
    independent deterministic shock is then added for the branch/component,
    preserving reproducibility while allowing economically interesting
    exceptions to the structural pattern.
    """
    base = np.array(
        [
            COST_BAND_BASE_PROBABILITIES[component][band]
            for band in COST_BAND_ORDER
        ],
        dtype=float,
    )

    size_shift = COST_PROFILE_SIZE_SHIFT[component].get(str(branch_size), 0.0)
    type_shift = COST_PROFILE_TYPE_SHIFT[component].get(str(branch_type), 0.0)

    safe_location = max(float(location_multiplier), 1e-9)
    location_shift = (
        COST_PROFILE_LOCATION_BETA[component] * np.log(safe_location)
    )

    shock_half_width = COST_PROFILE_SHOCK_HALF_WIDTH[component]
    independent_shock = stable_uniform(
        f"cost-profile-shock|{component}|{branch_id}",
        -shock_half_width,
        shock_half_width,
    )

    total_shift = float(
        size_shift + type_shift + location_shift + independent_shock
    )

    # Exponential tilting preserves strictly positive probabilities while
    # smoothly shifting mass toward lower or higher cost bands.
    weights = base * np.exp(COST_BAND_POSITIONS * total_shift)
    probabilities = weights / weights.sum()
    return probabilities, total_shift


def draw_cost_profile(
    component: str,
    branch_id: str,
    branch_size: str,
    branch_type: str,
    location_multiplier: float,
) -> tuple[str, float, float]:
    """
    Draw one persistent band and one within-band value for a branch/component.
    """
    probabilities, shift = cost_profile_probabilities(
        component=component,
        branch_id=branch_id,
        branch_size=branch_size,
        branch_type=branch_type,
        location_multiplier=location_multiplier,
    )

    band_draw = stable_uniform(
        f"cost-profile-band|{component}|{branch_id}",
        0.0,
        1.0,
    )
    cumulative = np.cumsum(probabilities)
    band_index = int(np.searchsorted(cumulative, band_draw, side="right"))
    band_index = min(band_index, len(COST_BAND_ORDER) - 1)
    band = COST_BAND_ORDER[band_index]

    low, high = COST_PROFILE_VALUE_RANGES[component][band]
    profile_value = stable_uniform(
        f"cost-profile-value|{component}|{branch_id}",
        float(low),
        float(high),
    )
    return band, float(profile_value), shift


def draw_monthly_cost_process_parameters(
    component: str,
    branch_id: str,
) -> tuple[float, float]:
    """
    Draw persistent AR(1)-style parameters for one branch/component.

    The parameter draw itself is reproducible. Different components and
    different branches receive independent streams.
    """
    config = MONTHLY_COST_PROCESS_RANGES[component]

    phi = stable_uniform(
        f"monthly-cost-phi|{component}|{branch_id}",
        float(config["phi"][0]),
        float(config["phi"][1]),
    )
    sigma = stable_uniform(
        f"monthly-cost-sigma|{component}|{branch_id}",
        float(config["sigma"][0]),
        float(config["sigma"][1]),
    )
    return float(phi), float(sigma)


def build_monthly_cost_shocks(
    frame: pd.DataFrame,
) -> pd.DataFrame:
    """
    Add independent, reproducible, mean-reverting monthly shock factors.

    Each branch/component has:
      - one persistent phi draw,
      - one persistent long-run volatility draw,
      - one independent innovation per month.

    The state evolves in log space, so exp(state) produces a positive
    multiplicative factor centered around 1.0 without forcing monotonic paths.
    """
    result = frame.copy()

    required = {"branch_id", "year_month"}
    missing = required - set(result.columns)
    if missing:
        raise ValueError(
            f"Monthly cost-shock input missing columns: {sorted(missing)}"
        )

    if result.duplicated(["branch_id", "year_month"]).any():
        raise ValueError(
            "Monthly cost-shock input contains duplicate branch/month rows."
        )

    for component in ("personnel", "fixed", "variable", "operational"):
        factor_col = f"{component}_monthly_shock"
        phi_col = f"{component}_monthly_phi"
        sigma_col = f"{component}_monthly_sigma"

        result[factor_col] = np.nan
        result[phi_col] = np.nan
        result[sigma_col] = np.nan

        for branch_id, branch_rows in result.groupby(
            "branch_id",
            sort=False,
            observed=True,
        ):
            branch_id_str = str(branch_id)
            phi, sigma = draw_monthly_cost_process_parameters(
                component,
                branch_id_str,
            )

            ordered = branch_rows.sort_values("year_month")
            indices = ordered.index.to_list()

            # Start from the stationary distribution so the first observed
            # month does not mechanically begin at exactly 1.0.
            state = sigma * stable_normal(
                f"monthly-cost-initial|{component}|{branch_id_str}"
            )

            innovation_sigma = sigma * np.sqrt(max(1.0 - phi**2, 0.0))
            factors: list[float] = []

            for row_index in indices:
                ym = str(result.at[row_index, "year_month"])
                innovation = innovation_sigma * stable_normal(
                    f"monthly-cost-innovation|{component}|{branch_id_str}|{ym}"
                )
                state = phi * state + innovation
                factors.append(float(np.exp(state)))

            result.loc[indices, factor_col] = factors
            result.loc[indices, phi_col] = phi
            result.loc[indices, sigma_col] = sigma

    shock_columns = [
        f"{component}_monthly_shock"
        for component in ("personnel", "fixed", "variable", "operational")
    ]
    if result[shock_columns].isna().any().any():
        raise ValueError("Monthly cost-shock generation produced missing values.")

    return result


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
    resolved = {
        "customers": resolve_first_existing(CUSTOMERS_CANDIDATES, "customers"),
        "accounts": resolve_first_existing(ACCOUNTS_CANDIDATES, "accounts"),
        "cards": resolve_first_existing(CARDS_CANDIDATES, "cards"),
        "loans": resolve_first_existing(LOANS_CANDIDATES, "loans"),
        "loan_snapshot": resolve_first_existing(
            LOAN_SNAPSHOT_CANDIDATES,
            "loan_monthly_snapshot",
        ),
        "transactions": resolve_first_existing(
            TRANSACTIONS_CANDIDATES,
            "transactions",
        ),
        "account_balances": resolve_first_existing(
            ACCOUNT_BALANCES_CANDIDATES,
            "account_balances",
        ),
        "branches": resolve_first_existing(BRANCHES_CANDIDATES, "branches"),
        "branch_state": resolve_first_existing(
            BRANCH_STATE_CANDIDATES,
            "branch_yearly_state",
        ),
        "loan_lifecycle_bridge": resolve_first_existing(
            LOAN_LIFECYCLE_BRIDGE_CANDIDATES,
            "loan_lifecycle_bridge",
        ),
        "products": resolve_first_existing(PRODUCTS_CANDIDATES, "products"),
    }

    print("\nResolved inputs:")
    for label, path in resolved.items():
        print(f"  {label:<24} {path}")

    data = {
        "customers": read_table(resolved["customers"]),
        "accounts": read_table(resolved["accounts"]),
        "cards": read_table(resolved["cards"]),
        "loans": read_table(resolved["loans"]),
        "loan_snapshot": read_table(resolved["loan_snapshot"]),
        "account_balances": read_table(resolved["account_balances"]),
        "branches": read_table(resolved["branches"]),
        "branch_state": read_table(resolved["branch_state"]),
        "loan_lifecycle_bridge": read_table(resolved["loan_lifecycle_bridge"]),
        "products": read_table(resolved["products"]),
        "_transactions_path": resolved["transactions"],
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
        raise ValueError("branches contains invalid branch_id values.")

    if lifecycle["loan_id"].duplicated().any():
        raise ValueError("loan_lifecycle_bridge contains duplicate loan_id values.")

    unknown_lifecycle_loans = set(lifecycle["loan_id"].dropna()) - set(loans["loan_id"].dropna())
    if unknown_lifecycle_loans:
        sample = sorted(unknown_lifecycle_loans)[:10]
        raise ValueError(f"loan_lifecycle_bridge contains unknown loan_id values: {sample}")
    if branches["branch_id"].duplicated().any():
        raise ValueError("Duplicate branch_id in branches.")

    expected_branch_years = pd.MultiIndex.from_product(
        [branches["branch_id"].tolist(), YEARS], names=["branch_id", "year"]
    )
    actual_branch_years = pd.MultiIndex.from_frame(
        branch_state[["branch_id", "year"]].drop_duplicates()
    )
    missing_state = expected_branch_years.difference(actual_branch_years)
    if len(missing_state):
        raise ValueError(
            "branch_yearly_state does not cover all branch/year combinations. "
            f"Missing examples: {list(missing_state[:10])}"
        )

    if branch_state.duplicated(["branch_id", "year"]).any():
        raise ValueError("Duplicate branch_id/year in branch_yearly_state.")

    known_branches = set(branches["branch_id"].dropna())
    unknown_account_branches = set(accounts["branch_id"].dropna()) - known_branches
    unknown_loan_branches = set(loans["branch_id"].dropna()) - known_branches

    if unknown_account_branches:
        raise ValueError(f"accounts contains unknown branches: {sorted(unknown_account_branches)[:10]}")
    if unknown_loan_branches:
        raise ValueError(f"loans contains unknown branches: {sorted(unknown_loan_branches)[:10]}")

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
        raise ValueError("Negative account balance detected in account_balances.")

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
    aggregate["credit_loss"] = aggregate["credit_loss"].clip(lower=0.0)

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

    batches = iter_transaction_batches(
        transactions_path,
        columns=usecols,
        batch_size=TRANSACTION_BATCH_SIZE,
    )

    for chunk_number, chunk in enumerate(batches, start=1):
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
                "transactions contains account_id values missing from accounts: "
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
        [
            "branch_id",
            "branch_name",
            "branch_type",
            "branch_size",
            "opening_year",
            "closing_year",
            "region",
        ]
    ].copy()

    structure["staff_base"] = structure["branch_size"].map(BASE_STAFF_EQUIVALENTS)
    structure["staff_base"] *= (
        structure["branch_type"]
        .map(BRANCH_TYPE_STAFF_MULTIPLIER)
        .fillna(1.0)
    )

    structure["fixed_base"] = structure["branch_size"].map(
        BASE_FIXED_MONTHLY_COST_2021
    )
    structure["fixed_base"] *= (
        structure["branch_type"]
        .map(BRANCH_TYPE_FIXED_MULTIPLIER)
        .fillna(1.0)
    )

    if structure["staff_base"].isna().any():
        unknown = sorted(
            structure.loc[
                structure["staff_base"].isna(),
                "branch_size",
            ].unique()
        )
        raise ValueError(
            f"Unknown branch_size for staff calibration: {unknown}"
        )
    if structure["fixed_base"].isna().any():
        unknown = sorted(
            structure.loc[
                structure["fixed_base"].isna(),
                "branch_size",
            ].unique()
        )
        raise ValueError(
            f"Unknown branch_size for fixed-cost calibration: {unknown}"
        )

    structure["location_multiplier"] = (
        structure["branch_name"]
        .map(LOCATION_COST_MULTIPLIER)
        .fillna(1.0)
    )
    interior = ~structure["region"].astype("string").str.upper().eq(
        "METROPOLITAN"
    )
    no_named_override = ~structure["branch_name"].isin(
        LOCATION_COST_MULTIPLIER
    )
    structure.loc[
        interior & no_named_override,
        "location_multiplier",
    ] *= 0.92

    # Draw each cost component independently. The structural characteristics
    # only tilt probabilities; they do not determine the resulting band.
    allocation_rates: list[float] = []
    realized_shared_mixes: list[dict[str, float]] = []

    for row in structure.itertuples(index=False):
        branch_id = str(row.branch_id)
        base_rate = stable_uniform(
            f"shared_services_allocation_rate|{branch_id}",
            SHARED_SERVICES_ALLOCATION_RANGE[0],
            SHARED_SERVICES_ALLOCATION_RANGE[1],
        )
        size_multiplier = SHARED_SERVICES_SIZE_MULTIPLIER.get(
            str(row.branch_size),
            1.0,
        )
        type_multiplier = SHARED_SERVICES_TYPE_MULTIPLIER.get(
            str(row.branch_type),
            1.0,
        )
        allocation_rates.append(
            float(base_rate * size_multiplier * type_multiplier)
        )
        realized_shared_mixes.append(
            draw_shared_services_component_mix(branch_id)
        )

    structure["shared_services_allocation_rate"] = allocation_rates
    for component in ("personnel", "fixed", "variable", "operational"):
        structure[f"shared_services_{component}_share"] = [
            mix[component] for mix in realized_shared_mixes
        ]

    for component in ("personnel", "fixed", "variable", "operational"):
        draws = [
            draw_cost_profile(
                component=component,
                branch_id=str(row.branch_id),
                branch_size=str(row.branch_size),
                branch_type=str(row.branch_type),
                location_multiplier=float(row.location_multiplier),
            )
            for row in structure.itertuples(index=False)
        ]

        structure[f"{component}_cost_band"] = [
            draw[0] for draw in draws
        ]
        structure[f"{component}_profile_value"] = [
            draw[1] for draw in draws
        ]
        structure[f"{component}_probability_shift"] = [
            draw[2] for draw in draws
        ]

    return structure


def add_costs(
    performance: pd.DataFrame,
    branches: pd.DataFrame,
) -> pd.DataFrame:
    frame = performance.merge(
        build_branch_structure(branches),
        on="branch_id",
        how="left",
        validate="many_to_one",
    )

    positive_tx = frame.loc[
        frame["transaction_count"] > 0,
        "transaction_count",
    ]
    positive_branch_tx = frame.loc[
        frame["branch_transaction_count"] > 0,
        "branch_transaction_count",
    ]
    positive_accounts = frame.loc[
        frame["active_accounts"] > 0,
        "active_accounts",
    ]
    positive_loans = frame.loc[
        frame["active_loan_count"] > 0,
        "active_loan_count",
    ]

    tx_ref = max(
        float(positive_tx.median()) if len(positive_tx) else 1.0,
        1.0,
    )
    branch_tx_ref = max(
        float(positive_branch_tx.median())
        if len(positive_branch_tx)
        else 1.0,
        1.0,
    )
    account_ref = max(
        float(positive_accounts.median())
        if len(positive_accounts)
        else 1.0,
        1.0,
    )
    loan_ref = max(
        float(positive_loans.median())
        if len(positive_loans)
        else 1.0,
        1.0,
    )

    frame["workload_index"] = (
        0.55 * frame["transaction_count"] / tx_ref
        + 0.25 * frame["branch_transaction_count"] / branch_tx_ref
        + 0.15 * frame["active_accounts"] / account_ref
        + 0.05 * frame["active_loan_count"] / loan_ref
    ).clip(lower=0.0)

    frame["operational_flag"] = [
        branch_operational_in_year(
            row.opening_year,
            row.closing_year,
            int(row.year),
        )
        for row in frame.itertuples(index=False)
    ]

    wage_index = frame["year_month"].map(
        lambda ym: monthly_index(str(ym), ANNUAL_WAGE_INDEX)
    )
    price_index = frame["year_month"].map(
        lambda ym: monthly_index(str(ym), ANNUAL_PRICE_INDEX)
    )
    cp = frame["cost_pressure"].clip(-2.5, 2.5).astype(float)

    # Persistent structural profiles are combined with independent monthly
    # mean-reverting shocks. This preserves structural identity while still
    # allowing realized monthly costs to move in either direction.
    frame = build_monthly_cost_shocks(frame)

    # -----------------------------------------------------------------
    # Direct branch costs
    # -----------------------------------------------------------------
    # The configured labor base is treated as gross remuneration before
    # employer-side social-security charges. The synthetic branch P&L records
    # the employer burden inside personnel_cost.
    frame["direct_personnel_cost"] = (
        frame["staff_base"]
        * BASE_MONTHLY_LABOR_COST_2021
        * frame["personnel_profile_value"]
        * frame["personnel_monthly_shock"]
        * wage_index
        * np.exp(PERSONNEL_COST_PRESSURE_BETA * cp)
        * (1.0 + EMPLOYER_SOCIAL_SECURITY_RATE)
    )

    frame["direct_fixed_cost"] = (
        frame["fixed_base"]
        * frame["fixed_profile_value"]
        * frame["fixed_monthly_shock"]
        * frame["location_multiplier"]
        * price_index
        * np.exp(FIXED_COST_PRESSURE_BETA * cp)
    )

    direct_rigid_base = (
        frame["direct_personnel_cost"]
        + frame["direct_fixed_cost"]
    )

    workload_effect = np.power(
        np.maximum(
            frame["workload_index"].to_numpy(dtype=float),
            0.0,
        ),
        VARIABLE_COST_ELASTICITY,
    )

    frame["direct_variable_cost"] = (
        direct_rigid_base
        * frame["variable_profile_value"]
        * frame["variable_monthly_shock"]
        * workload_effect
        * np.exp(VARIABLE_COST_PRESSURE_BETA * cp)
    )

    frame["direct_operational_cost"] = (
        direct_rigid_base
        * frame["operational_profile_value"]
        * frame["operational_monthly_shock"]
        * np.exp(OTHER_COST_PRESSURE_BETA * cp)
    )

    closed_mask = ~frame["operational_flag"]
    direct_columns = [
        "direct_personnel_cost",
        "direct_fixed_cost",
        "direct_variable_cost",
        "direct_operational_cost",
    ]
    for col in direct_columns:
        frame.loc[closed_mask, col] = 0.0

    frame["direct_operating_cost"] = frame[direct_columns].sum(axis=1)

    # -----------------------------------------------------------------
    # Central/shared banking-service allocation
    # -----------------------------------------------------------------
    # V3.1 represented branch-local economics but materially understated the
    # fully-loaded cost of running the banking network. V3.2 adds central
    # services such as technology platforms, cybersecurity, compliance, audit,
    # legal, HR, data, treasury operations and other head-office support.
    #
    # The allocation rate is a persistent branch-level draw, so no final
    # Cost-to-Income or Net Margin is forced.
    frame["shared_services_cost"] = (
        frame["direct_operating_cost"]
        * frame["shared_services_allocation_rate"]
    )
    frame.loc[closed_mask, "shared_services_cost"] = 0.0

    frame["personnel_cost"] = (
        frame["direct_personnel_cost"]
        + frame["shared_services_cost"]
        * frame["shared_services_personnel_share"]
    )
    frame["fixed_cost"] = (
        frame["direct_fixed_cost"]
        + frame["shared_services_cost"]
        * frame["shared_services_fixed_share"]
    )
    frame["variable_cost"] = (
        frame["direct_variable_cost"]
        + frame["shared_services_cost"]
        * frame["shared_services_variable_share"]
    )
    frame["operational_cost"] = (
        frame["direct_operational_cost"]
        + frame["shared_services_cost"]
        * frame["shared_services_operational_share"]
    )

    frame["total_operating_cost"] = (
        frame["personnel_cost"]
        + frame["fixed_cost"]
        + frame["variable_cost"]
        + frame["operational_cost"]
    )
    return frame


def print_cost_profile_diagnostics(branches: pd.DataFrame) -> None:
    """
    Print the persistent branch-level profile draws used by the cost engine.
    """
    structure = build_branch_structure(branches)

    allocation = structure["shared_services_allocation_rate"].astype(float)
    print("\nShared-services allocation diagnostics:")
    print(
        f"  allocation rate min/median/max: "
        f"{allocation.min():.3f} / {allocation.median():.3f} / {allocation.max():.3f}"
    )
    for component in ("personnel", "fixed", "variable", "operational"):
        shares = structure[f"shared_services_{component}_share"].astype(float)
        print(
            f"  {component:<12} shared-service share "
            f"P10/median/P90: "
            f"{shares.quantile(0.10):.3f} / "
            f"{shares.median():.3f} / "
            f"{shares.quantile(0.90):.3f}"
        )

    print("\nProbabilistic cost-profile diagnostics:")
    for component in ("personnel", "fixed", "variable", "operational"):
        band_col = f"{component}_cost_band"
        value_col = f"{component}_profile_value"
        counts = (
            structure[band_col]
            .value_counts()
            .reindex(COST_BAND_ORDER, fill_value=0)
        )
        count_text = " | ".join(
            f"{band}:{int(counts[band])}"
            for band in COST_BAND_ORDER
        )
        values = structure[value_col].astype(float)
        print(f"  {component:<12} {count_text}")
        print(
            f"    profile value min/median/max: "
            f"{values.min():.3f} / "
            f"{values.median():.3f} / "
            f"{values.max():.3f}"
        )


def print_monthly_cost_shock_diagnostics(frame: pd.DataFrame) -> None:
    """Print realized monthly shock/process diagnostics before output stripping."""
    print("\nMonthly cost-process diagnostics:")

    for component in ("personnel", "fixed", "variable", "operational"):
        factor_col = f"{component}_monthly_shock"
        phi_col = f"{component}_monthly_phi"
        sigma_col = f"{component}_monthly_sigma"

        factors = pd.to_numeric(frame[factor_col], errors="raise")
        phi_values = (
            frame[["branch_id", phi_col]]
            .drop_duplicates("branch_id")[phi_col]
            .astype(float)
        )
        sigma_values = (
            frame[["branch_id", sigma_col]]
            .drop_duplicates("branch_id")[sigma_col]
            .astype(float)
        )

        print(
            f"  {component:<12} monthly factor "
            f"P10/median/P90: "
            f"{factors.quantile(0.10):.3f} / "
            f"{factors.median():.3f} / "
            f"{factors.quantile(0.90):.3f}"
        )
        print(
            f"    phi min/median/max: "
            f"{phi_values.min():.3f} / "
            f"{phi_values.median():.3f} / "
            f"{phi_values.max():.3f}"
        )
        print(
            f"    sigma min/median/max: "
            f"{sigma_values.min():.3f} / "
            f"{sigma_values.median():.3f} / "
            f"{sigma_values.max():.3f}"
        )



def add_income_tax(frame: pd.DataFrame) -> pd.DataFrame:
    """Add annual consolidated corporate tax and allocate it for management P&L.

    Tax is calculated on positive annual consolidated pre-tax income. The
    resulting annual tax provision is allocated first to profitable months and
    then to profitable branches within each month. This preserves branch-to-bank
    reconciliation without pretending that each branch is a separate taxpayer.

    Tax-loss carryforwards, deferred tax and permanent/temporary tax
    differences are outside the current synthetic scope.
    """
    result = frame.copy()

    result["pre_tax_income"] = (
        result["pre_provision_profit"]
        - result["credit_loss"]
    )
    result["income_tax_expense"] = 0.0

    tax_year = result["year_month"].astype(str).str.slice(0, 4).astype(int)
    result["_tax_year"] = tax_year

    for year in sorted(result["_tax_year"].unique()):
        year_mask = result["_tax_year"].eq(year)
        annual_pre_tax = float(
            result.loc[year_mask, "pre_tax_income"].sum()
        )
        annual_tax = max(annual_pre_tax, 0.0) * CORPORATE_INCOME_TAX_RATE

        if annual_tax <= 0.0:
            continue

        month_pre_tax = (
            result.loc[year_mask]
            .groupby("year_month", observed=True)["pre_tax_income"]
            .sum()
        )
        positive_month_pre_tax = month_pre_tax.clip(lower=0.0)
        positive_month_total = float(positive_month_pre_tax.sum())

        if positive_month_total <= 0.0:
            continue

        month_tax = (
            annual_tax
            * positive_month_pre_tax
            / positive_month_total
        )

        for year_month, allocated_month_tax in month_tax.items():
            if allocated_month_tax <= 0.0:
                continue

            month_mask = (
                year_mask
                & result["year_month"].eq(year_month)
            )
            positive_branch_pre_tax = (
                result.loc[month_mask, "pre_tax_income"]
                .clip(lower=0.0)
            )
            positive_branch_total = float(positive_branch_pre_tax.sum())

            if positive_branch_total <= 0.0:
                continue

            branch_tax = (
                allocated_month_tax
                * positive_branch_pre_tax
                / positive_branch_total
            )
            result.loc[
                positive_branch_pre_tax.index,
                "income_tax_expense",
            ] = branch_tax.to_numpy(dtype=float)

    result["net_income"] = (
        result["pre_tax_income"]
        - result["income_tax_expense"]
    )
    return result.drop(columns=["_tax_year"])


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
    transaction_metrics = build_transaction_metrics(data["_transactions_path"], data["accounts"], data["products"])

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
    frame["pre_provision_profit"] = (
        frame["total_revenue"]
        - frame["total_operating_cost"]
    )
    frame = add_income_tax(frame)
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
        errors.append(f"year_month coverage differs from {OBS_START} through {OBS_END}")
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
        "credit_loss",
        "income_tax_expense",
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
        "pre_tax_income_identity": branch_output["pre_tax_income"] - (branch_output["pre_provision_profit"] - branch_output["credit_loss"]),
        "net_income_identity": branch_output["net_income"] - (branch_output["pre_tax_income"] - branch_output["income_tax_expense"]),
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
# INPUT COVERAGE DIAGNOSTICS
# =============================================================================

def print_input_coverage_diagnostics(data: dict[str, pd.DataFrame]) -> None:
    accounts = data["accounts"]
    customers = data["customers"]
    balances = data["account_balances"]
    transactions_path = data["_transactions_path"]

    total_accounts = int(accounts["account_id"].nunique())
    total_customers = int(customers["customer_id"].nunique())
    balance_accounts = int(balances["account_id"].nunique())
    balance_rows = len(balances)

    expected_account_months_upper = total_accounts * len(MONTHS)
    balance_account_coverage = safe_ratio(balance_accounts, total_accounts)
    balance_row_density = safe_ratio(balance_rows, expected_account_months_upper)

    transaction_rows = 0
    completed_rows = 0
    transaction_accounts: set[str] = set()
    transaction_customers: set[str] = set()
    account_customer = (
        accounts[["account_id", "customer_id"]]
        .drop_duplicates("account_id")
        .set_index("account_id")["customer_id"]
    )

    coverage_cols = ["account_id", "transaction_status"]
    for chunk in iter_transaction_batches(
        transactions_path,
        columns=coverage_cols,
        batch_size=TRANSACTION_BATCH_SIZE,
    ):
        transaction_rows += len(chunk)
        chunk["account_id"] = normalize_id_string(chunk["account_id"])
        status = chunk["transaction_status"].astype("string").str.upper()
        completed = chunk.loc[status.eq("COMPLETED"), "account_id"].dropna()
        completed_rows += len(completed)
        transaction_accounts.update(completed.astype(str).unique().tolist())
        mapped_customers = completed.map(account_customer).dropna()
        transaction_customers.update(mapped_customers.astype(str).unique().tolist())

    years = max(len(YEARS), 1)
    tx_per_account_year = safe_ratio(completed_rows, total_accounts * years)
    tx_per_customer_year = safe_ratio(completed_rows, total_customers * years)
    tx_account_coverage = safe_ratio(len(transaction_accounts), total_accounts)
    tx_customer_coverage = safe_ratio(len(transaction_customers), total_customers)

    print("\nInput coverage diagnostics:")
    print(
        f"  account balances — represented accounts: {balance_accounts:,}/{total_accounts:,} "
        f"({balance_account_coverage:.2%})"
    )
    print(
        f"  account balances — rows: {balance_rows:,} | "
        f"density vs accounts × months upper bound: {balance_row_density:.2%}"
    )
    print(
        f"  transactions — source rows: {transaction_rows:,} | "
        f"completed rows: {completed_rows:,}"
    )
    print(
        f"  transactions — accounts represented: {len(transaction_accounts):,}/{total_accounts:,} "
        f"({tx_account_coverage:.2%})"
    )
    print(
        f"  transactions — customers represented: {len(transaction_customers):,}/{total_customers:,} "
        f"({tx_customer_coverage:.2%})"
    )
    print(f"  completed transactions / account / year: {tx_per_account_year:,.2f}")
    print(f"  completed transactions / customer / year: {tx_per_customer_year:,.2f}")


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

    if AUDIT_DETAIL_LEVEL != "full":
        print("\nBusiness-result diagnostics: SUPPRESSED")
        print(
            "Set BTYT_PERFORMANCE_AUDIT_DETAIL=full only when a detailed "
            "analytical audit is explicitly desired."
        )
        print("\nReconciliation:")
        print(
            "  SUM(branch_monthly_performance) == "
            "bank_monthly_performance   PASS"
        )
        print("\nVALIDATION: PASS")
        return

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
            pre_tax_income=("pre_tax_income", "sum"),
            income_tax_expense=("income_tax_expense", "sum"),
            net_income=("net_income", "sum"),
        )
    )
    annual["cost_to_income"] = annual["total_operating_cost"] / annual["total_revenue"].replace(0, np.nan)
    annual["credit_loss_ratio"] = annual["credit_loss"] / annual["average_loan_balance"].replace(0, np.nan)
    annual["net_margin"] = annual["net_income"] / annual["total_revenue"].replace(0, np.nan)

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
        "pre_tax_income",
        "income_tax_expense",
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
                "net_margin",
            ]
        ]
        .round(3)
        .to_string(index=False)
    )
    print("Monetary values above are UYU millions.")

    margin_low, margin_high = NET_MARGIN_DIAGNOSTIC_RANGE
    outside_margin_band = annual.loc[
        ~annual["net_margin"].between(margin_low, margin_high, inclusive="both"),
        ["year", "net_margin"],
    ]
    if outside_margin_band.empty:
        print(
            f"Annual net-margin diagnostic: PASS "
            f"({margin_low:.0%}-{margin_high:.0%} reference range)"
        )
    else:
        detail = ", ".join(
            f"{int(row.year)}={row.net_margin:.2%}"
            for row in outside_margin_band.itertuples(index=False)
        )
        print(
            f"Annual net-margin diagnostic: REVIEW "
            f"({margin_low:.0%}-{margin_high:.0%} reference range) | {detail}"
        )

    annual["deposit_to_loan_ratio"] = (
        annual["average_deposits"]
        / annual["average_loan_balance"].replace(0, np.nan)
    )
    print("\nFunding diagnostic — average deposits / average loan balance:")
    for row in annual[["year", "deposit_to_loan_ratio"]].itertuples(index=False):
        print(f"  {row.year}: {row.deposit_to_loan_ratio:.2%}")

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

def main(write_csv: bool = False) -> None:
    print("=" * 84)
    print(f"BTYT BRANCH PERFORMANCE ENGINE — V{ENGINE_VERSION}")
    print(f"World seed: {WORLD_SEED}")
    print(f"RNG namespace: {RNG_NAMESPACE}")
    print(f"Observation window: {OBS_START} -> {OBS_END}")
    print("=" * 84)

    validate_cost_profile_configuration()

    print("Loading frozen canonical inputs...")
    print("Canonical-first transition-aware input resolution enabled.")
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

    print_cost_profile_diagnostics(data["branches"])
    print_input_coverage_diagnostics(data)

    print("\nBuilding monthly branch economics...")
    raw = assemble_performance(data)
    print_monthly_cost_shock_diagnostics(raw)
    branch_output = finalize_branch_output(raw)

    bank_output = build_bank_output(branch_output)
    for col in COUNT_COLUMNS:
        bank_output[col] = np.rint(pd.to_numeric(bank_output[col], errors="raise")).astype("int64")
    for col in MONETARY_COLUMNS:
        bank_output[col] = pd.to_numeric(bank_output[col], errors="raise").round(2)

    validate_branch_output(branch_output, data["branches"])
    validate_bank_reconciliation(branch_output, bank_output)

    GENERATED_PERFORMANCE_DIR.mkdir(parents=True, exist_ok=True)
    branch_output.to_parquet(BRANCH_OUTPUT_PATH, index=False, compression="zstd")
    bank_output.to_parquet(BANK_OUTPUT_PATH, index=False, compression="zstd")
    if write_csv:
        branch_output.to_csv(BRANCH_OUTPUT_CSV_PATH, index=False)
        bank_output.to_csv(BANK_OUTPUT_CSV_PATH, index=False)

    print_audit(branch_output, bank_output)

    print("\nSaved:")
    print(f"  {BRANCH_OUTPUT_PATH}")
    print(f"  shape = {branch_output.shape}")
    print(f"  {BANK_OUTPUT_PATH}")
    print(f"  shape = {bank_output.shape}")
    if write_csv:
        print(f"  {BRANCH_OUTPUT_CSV_PATH}")
        print(f"  {BANK_OUTPUT_CSV_PATH}")

    print(f"\nBTYT BRANCH PERFORMANCE ENGINE V{ENGINE_VERSION}: PASS")
    print("No upstream canonical dataset was modified.")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Generate BTYT branch and bank performance outputs.")
    parser.add_argument("--write-csv", action="store_true", help="Also write compatibility CSV outputs.")
    args = parser.parse_args()
    main(write_csv=args.write_csv)