"""
BTYT Banking Analytics
External Shocks Engine V1.1.0

Multilevel stochastic shock generator for 2021-2026.

Scales
------
- SYSTEMIC
- REGIONAL
- SECTORAL
- IDIOSYNCRATIC

Core principles
---------------
- Shocks shift latent conditions and probabilities; they do not force outcomes.
- Exposure, resilience, shared causes, idiosyncratic realization, and recovery
  are modeled separately.
- RNG streams are independent by causal mechanism.
- Regional and sectoral shocks are true events, not only exposure multipliers.
- Shared shocks may increase the probability of individual shocks, while the
  individual realization remains stochastic.
- Limited interaction terms are allowed only for economically defensible pairs.
- Common-cause mediation is recorded to reduce downstream double counting.
- No frozen observable banking dataset is modified by this script.
"""

from __future__ import annotations

import argparse
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Mapping, Sequence, Tuple

import numpy as np
import pandas as pd


# =============================================================================
# Configuration
# =============================================================================

ENGINE_VERSION = "1.1.2"

START_MONTH = "2021-01"
END_MONTH = "2026-12"
MONTHS = pd.period_range(START_MONTH, END_MONTH, freq="M")
MONTH_LABELS = [str(m) for m in MONTHS]
N_MONTHS = len(MONTHS)

DEFAULT_WORLD_SEED = 20260902

# Independent RNG streams.
STREAM_SYSTEMIC_OCCURRENCE = 601
STREAM_SYSTEMIC_TIMING = 602
STREAM_SYSTEMIC_MAGNITUDE = 603
STREAM_SYSTEMIC_PERSISTENCE = 604

STREAM_REGIONAL_OCCURRENCE = 611
STREAM_REGIONAL_TIMING = 612
STREAM_REGIONAL_MAGNITUDE = 613
STREAM_REGIONAL_SCOPE = 614

STREAM_SECTORAL_OCCURRENCE = 621
STREAM_SECTORAL_TIMING = 622
STREAM_SECTORAL_MAGNITUDE = 623
STREAM_SECTORAL_SCOPE = 624

STREAM_EXPOSURE = 631
STREAM_RESILIENCE = 632
STREAM_INTERACTION = 633
STREAM_RECOVERY = 634

STREAM_IDIO_OCCURRENCE = 641
STREAM_IDIO_TIMING = 642
STREAM_IDIO_MAGNITUDE = 643
STREAM_IDIO_MEDIATION = 644
STREAM_CUSTOMER_JITTER = 651

ROOT = Path(__file__).resolve().parents[1]
DATA_GENERATED = ROOT / "data" / "generated"
DATA_INTERIM = ROOT / "data" / "interim"
DATA_MASTER = ROOT / "data" / "master"

CUSTOMERS_PATH = DATA_GENERATED / "customers.csv"
ACCOUNTS_PATH = DATA_GENERATED / "accounts.csv"
LOANS_PATH = DATA_GENERATED / "loans.csv"

EVENTS_PATH = DATA_MASTER / "external_shocks.csv"
MONTHLY_PATH = DATA_INTERIM / "external_shock_monthly_state.csv"
EXPOSURE_PATH = DATA_INTERIM / "external_shock_exposure.csv"
RESILIENCE_PATH = DATA_INTERIM / "external_shock_resilience.csv"
INTERACTIONS_PATH = DATA_INTERIM / "external_shock_interactions.csv"
IDIO_EVENTS_PATH = DATA_INTERIM / "external_idiosyncratic_events.csv"
CUSTOMER_STATE_PATH = DATA_INTERIM / "external_customer_monthly_state.csv"
WORLD_PARAMS_PATH = DATA_INTERIM / "external_shock_world_parameters.csv"
AUDIT_PATH = DATA_INTERIM / "external_shock_audit.csv"

REGIONS = ("MONTEVIDEO", "METROPOLITAN", "EAST", "NORTH", "CENTER", "LITORAL")
SECTORS = (
    "HOUSEHOLD",
    "RETAIL_SERVICES",
    "TOURISM",
    "AGRICULTURE",
    "TRADE_IMPORT",
    "TRADE_EXPORT",
    "SME_GENERAL",
)
PRODUCT_GROUPS = (
    "DEPOSITS",
    "CARDS",
    "PERSONAL_CREDIT",
    "MORTGAGES",
    "SME_CREDIT",
    "AGRICULTURAL_CREDIT",
    "BUSINESS_CREDIT_LINES",
)

TRANSMISSION_DIMENSIONS = (
    "transaction_activity",
    "transaction_amount",
    "cash_preference",
    "digital_preference",
    "deposit_growth",
    "deposit_withdrawal_pressure",
    "loan_demand",
    "payment_stress",
    "delinquency_entry",
    "cure_probability",
    "branch_operating_cost",
    "business_activity",
    "interest_rate_pressure",
    "usd_preference",
)


# =============================================================================
# Specifications
# =============================================================================

@dataclass(frozen=True)
class EventSpec:
    shock_type: str
    label: str
    scale: str
    annual_hazard: float
    sign_mode: str
    min_duration: int
    max_duration: int
    magnitude_mean: float
    magnitude_sd: float
    magnitude_min: float
    magnitude_max: float
    persistence_low: float
    persistence_high: float
    recovery_low: int
    recovery_high: int
    base_effects: Mapping[str, float]
    region_exposure: Mapping[str, float]
    sector_exposure: Mapping[str, float]
    product_exposure: Mapping[str, float]
    preferred_regions: Tuple[str, ...] = ()
    preferred_sectors: Tuple[str, ...] = ()


@dataclass(frozen=True)
class IdioSpec:
    event_type: str
    label: str
    base_annual_probability: float
    sign: int
    magnitude_mean: float
    magnitude_sd: float
    magnitude_min: float
    magnitude_max: float
    min_duration: int
    max_duration: int
    recovery_low: int
    recovery_high: int
    household_weight: float
    business_weight: float
    macro_sensitivity: float
    regional_sensitivity: float
    sectoral_sensitivity: float


def complete(keys: Sequence[str], overrides: Mapping[str, float] | None = None, default: float = 1.0):
    overrides = overrides or {}
    return {key: float(overrides.get(key, default)) for key in keys}


def effects(**kwargs):
    out = {k: 0.0 for k in TRANSMISSION_DIMENSIONS}
    out.update(kwargs)
    return out


SYSTEMIC_SPECS = (
    EventSpec(
        "INFLATION_RATE_SHOCK", "Inflation and rate pressure", "SYSTEMIC",
        0.12, "NEGATIVE", 5, 14, 0.78, 0.22, 0.30, 1.35, 0.72, 0.92, 2, 8,
        effects(
            transaction_activity=-0.05, transaction_amount=0.08,
            deposit_growth=-0.08, deposit_withdrawal_pressure=0.12,
            loan_demand=-0.10, payment_stress=0.18, delinquency_entry=0.14,
            cure_probability=-0.10, branch_operating_cost=0.18,
            business_activity=-0.08, interest_rate_pressure=0.28,
            usd_preference=0.08,
        ),
        complete(REGIONS),
        complete(SECTORS, {"TRADE_IMPORT": 1.20, "SME_GENERAL": 1.10}),
        complete(PRODUCT_GROUPS, {"MORTGAGES": 1.20, "PERSONAL_CREDIT": 1.15}),
    ),
    EventSpec(
        "FX_SHOCK", "Exchange-rate volatility", "SYSTEMIC",
        0.09, "MIXED", 3, 9, 0.68, 0.23, 0.25, 1.30, 0.58, 0.86, 1, 5,
        effects(
            transaction_activity=-0.02, transaction_amount=0.04,
            deposit_growth=-0.03, deposit_withdrawal_pressure=0.06,
            loan_demand=-0.04, payment_stress=0.10, delinquency_entry=0.07,
            cure_probability=-0.04, business_activity=-0.05,
            interest_rate_pressure=0.07, usd_preference=0.25,
        ),
        complete(REGIONS, {"MONTEVIDEO": 1.10, "METROPOLITAN": 1.05}),
        complete(SECTORS, {"TRADE_IMPORT": 1.35, "TRADE_EXPORT": 1.25, "AGRICULTURE": 1.15}),
        complete(PRODUCT_GROUPS, {"BUSINESS_CREDIT_LINES": 1.20, "SME_CREDIT": 1.12}),
    ),
    EventSpec(
        "ACTIVITY_SLOWDOWN", "National economic activity slowdown", "SYSTEMIC",
        0.08, "NEGATIVE", 5, 13, 0.74, 0.23, 0.30, 1.35, 0.68, 0.91, 3, 10,
        effects(
            transaction_activity=-0.16, transaction_amount=-0.10,
            deposit_growth=-0.11, deposit_withdrawal_pressure=0.09,
            loan_demand=-0.14, payment_stress=0.18, delinquency_entry=0.15,
            cure_probability=-0.10, business_activity=-0.24,
        ),
        complete(REGIONS),
        complete(SECTORS, {"RETAIL_SERVICES": 1.15, "SME_GENERAL": 1.20, "TOURISM": 1.15}),
        complete(PRODUCT_GROUPS, {"SME_CREDIT": 1.18, "BUSINESS_CREDIT_LINES": 1.18}),
    ),
    EventSpec(
        "ACTIVITY_BOOM", "National economic activity expansion", "SYSTEMIC",
        0.07, "POSITIVE", 5, 12, 0.68, 0.20, 0.25, 1.20, 0.65, 0.90, 2, 7,
        effects(
            transaction_activity=0.17, transaction_amount=0.12,
            digital_preference=0.02, deposit_growth=0.12,
            deposit_withdrawal_pressure=-0.05, loan_demand=0.15,
            payment_stress=-0.09, delinquency_entry=-0.07,
            cure_probability=0.07, branch_operating_cost=0.04,
            business_activity=0.22,
        ),
        complete(REGIONS),
        complete(SECTORS, {"RETAIL_SERVICES": 1.15, "SME_GENERAL": 1.15}),
        complete(PRODUCT_GROUPS, {"CARDS": 1.10, "SME_CREDIT": 1.10}),
    ),
    EventSpec(
        "ENERGY_COST_SHOCK", "Energy and operating-cost shock", "SYSTEMIC",
        0.07, "NEGATIVE", 3, 9, 0.64, 0.20, 0.25, 1.20, 0.58, 0.84, 1, 5,
        effects(
            transaction_activity=-0.03, deposit_growth=-0.03,
            deposit_withdrawal_pressure=0.04, loan_demand=-0.03,
            payment_stress=0.07, delinquency_entry=0.05,
            cure_probability=-0.03, branch_operating_cost=0.25,
            business_activity=-0.08,
        ),
        complete(REGIONS),
        complete(SECTORS, {"RETAIL_SERVICES": 1.15, "SME_GENERAL": 1.15, "AGRICULTURE": 1.10}),
        complete(PRODUCT_GROUPS),
    ),
    EventSpec(
        "FINANCIAL_CONFIDENCE_SHOCK", "Financial confidence shock", "SYSTEMIC",
        0.05, "MIXED", 2, 7, 0.62, 0.23, 0.20, 1.20, 0.50, 0.82, 1, 4,
        effects(
            transaction_activity=0.03, transaction_amount=0.04,
            cash_preference=-0.08, digital_preference=0.02,
            deposit_growth=0.20, deposit_withdrawal_pressure=-0.20,
            loan_demand=0.03, payment_stress=-0.04, delinquency_entry=-0.03,
            cure_probability=0.03, business_activity=0.04,
            interest_rate_pressure=-0.02, usd_preference=-0.10,
        ),
        complete(REGIONS), complete(SECTORS),
        complete(PRODUCT_GROUPS, {"DEPOSITS": 1.35}),
    ),
    EventSpec(
        "DIGITAL_ACCELERATION_SHOCK", "Digital adoption acceleration", "SYSTEMIC",
        0.055, "POSITIVE", 6, 16, 0.58, 0.18, 0.20, 1.05, 0.74, 0.94, 3, 12,
        effects(
            transaction_activity=0.06, transaction_amount=0.03,
            cash_preference=-0.18, digital_preference=0.28,
            deposit_growth=0.03, deposit_withdrawal_pressure=-0.01,
            loan_demand=0.04, branch_operating_cost=-0.04,
            business_activity=0.04,
        ),
        complete(REGIONS, {"MONTEVIDEO": 1.20, "METROPOLITAN": 1.15, "CENTER": 0.85, "NORTH": 0.85}),
        complete(SECTORS, {"HOUSEHOLD": 1.15, "RETAIL_SERVICES": 1.10}),
        complete(PRODUCT_GROUPS, {"CARDS": 1.30, "DEPOSITS": 1.10}),
    ),
)

REGIONAL_SPECS = (
    EventSpec(
        "REGIONAL_DROUGHT", "Regional drought", "REGIONAL",
        0.08, "NEGATIVE", 4, 10, 0.78, 0.22, 0.30, 1.35, 0.65, 0.90, 3, 10,
        effects(
            transaction_activity=-0.07, transaction_amount=-0.05,
            deposit_growth=-0.14, deposit_withdrawal_pressure=0.11,
            loan_demand=0.05, payment_stress=0.22, delinquency_entry=0.18,
            cure_probability=-0.12, business_activity=-0.20,
            usd_preference=0.05,
        ),
        complete(REGIONS, {"CENTER": 1.55, "NORTH": 1.40, "LITORAL": 1.35, "EAST": 1.25, "MONTEVIDEO": 0.25}),
        complete(SECTORS, {"AGRICULTURE": 1.90, "TRADE_EXPORT": 1.25, "TOURISM": 0.30}),
        complete(PRODUCT_GROUPS, {"AGRICULTURAL_CREDIT": 1.95, "SME_CREDIT": 1.15}),
        preferred_regions=("CENTER", "NORTH", "LITORAL", "EAST"),
    ),
    EventSpec(
        "REGIONAL_FLOOD", "Regional flooding", "REGIONAL",
        0.06, "NEGATIVE", 2, 6, 0.66, 0.20, 0.25, 1.20, 0.48, 0.78, 2, 8,
        effects(
            transaction_activity=-0.11, transaction_amount=-0.07,
            cash_preference=0.05, digital_preference=-0.02,
            deposit_growth=-0.08, deposit_withdrawal_pressure=0.12,
            payment_stress=0.15, delinquency_entry=0.10,
            cure_probability=-0.07, branch_operating_cost=0.18,
            business_activity=-0.16,
        ),
        complete(REGIONS, {"LITORAL": 1.45, "NORTH": 1.20, "EAST": 1.15}),
        complete(SECTORS, {"AGRICULTURE": 1.20, "RETAIL_SERVICES": 1.10}),
        complete(PRODUCT_GROUPS),
        preferred_regions=("LITORAL", "NORTH", "EAST"),
    ),
    EventSpec(
        "REGIONAL_TOURISM_SURGE", "Regional tourism surge", "REGIONAL",
        0.065, "POSITIVE", 3, 7, 0.64, 0.18, 0.25, 1.10, 0.52, 0.80, 1, 4,
        effects(
            transaction_activity=0.18, transaction_amount=0.14,
            deposit_growth=0.09, deposit_withdrawal_pressure=-0.03,
            loan_demand=0.08, payment_stress=-0.07,
            delinquency_entry=-0.05, cure_probability=0.05,
            branch_operating_cost=0.07, business_activity=0.20,
        ),
        complete(REGIONS, {"EAST": 1.70, "LITORAL": 1.10, "CENTER": 0.40, "NORTH": 0.45}),
        complete(SECTORS, {"TOURISM": 1.85, "RETAIL_SERVICES": 1.25, "AGRICULTURE": 0.25}),
        complete(PRODUCT_GROUPS, {"CARDS": 1.25, "SME_CREDIT": 1.15}),
        preferred_regions=("EAST", "LITORAL"),
    ),
    EventSpec(
        "REGIONAL_TOURISM_SLUMP", "Regional tourism slump", "REGIONAL",
        0.055, "NEGATIVE", 3, 7, 0.66, 0.20, 0.25, 1.20, 0.52, 0.82, 1, 5,
        effects(
            transaction_activity=-0.18, transaction_amount=-0.14,
            deposit_growth=-0.09, deposit_withdrawal_pressure=0.05,
            loan_demand=-0.08, payment_stress=0.10,
            delinquency_entry=0.08, cure_probability=-0.06,
            business_activity=-0.20,
        ),
        complete(REGIONS, {"EAST": 1.70, "LITORAL": 1.10, "CENTER": 0.40, "NORTH": 0.45}),
        complete(SECTORS, {"TOURISM": 1.85, "RETAIL_SERVICES": 1.25, "AGRICULTURE": 0.25}),
        complete(PRODUCT_GROUPS, {"CARDS": 1.25, "SME_CREDIT": 1.15}),
        preferred_regions=("EAST", "LITORAL"),
    ),
    EventSpec(
        "REGIONAL_INFRASTRUCTURE_DISRUPTION", "Regional infrastructure disruption", "REGIONAL",
        0.05, "NEGATIVE", 1, 4, 0.58, 0.18, 0.20, 1.05, 0.35, 0.70, 1, 4,
        effects(
            transaction_activity=-0.12, transaction_amount=-0.05,
            cash_preference=0.08, digital_preference=-0.08,
            deposit_withdrawal_pressure=0.06, branch_operating_cost=0.15,
            business_activity=-0.11,
        ),
        complete(REGIONS), complete(SECTORS), complete(PRODUCT_GROUPS),
        preferred_regions=REGIONS,
    ),
)

SECTORAL_SPECS = (
    EventSpec(
        "AGRICULTURAL_COMMODITY_UPSWING", "Agricultural commodity upswing", "SECTORAL",
        0.065, "POSITIVE", 4, 10, 0.68, 0.20, 0.25, 1.20, 0.60, 0.87, 2, 6,
        effects(
            transaction_activity=0.08, transaction_amount=0.10,
            deposit_growth=0.13, deposit_withdrawal_pressure=-0.06,
            loan_demand=0.10, payment_stress=-0.13,
            delinquency_entry=-0.10, cure_probability=0.08,
            business_activity=0.18, usd_preference=0.04,
        ),
        complete(REGIONS, {"CENTER": 1.35, "NORTH": 1.25, "EAST": 1.20, "LITORAL": 1.30, "MONTEVIDEO": 0.45}),
        complete(SECTORS, {"AGRICULTURE": 1.95, "TRADE_EXPORT": 1.25, "TOURISM": 0.30}),
        complete(PRODUCT_GROUPS, {"AGRICULTURAL_CREDIT": 1.90, "SME_CREDIT": 1.15}),
        preferred_sectors=("AGRICULTURE", "TRADE_EXPORT"),
    ),
    EventSpec(
        "IMPORT_COST_PRESSURE", "Import cost pressure", "SECTORAL",
        0.06, "NEGATIVE", 3, 8, 0.63, 0.19, 0.25, 1.15, 0.55, 0.82, 1, 5,
        effects(
            transaction_activity=-0.04, transaction_amount=0.05,
            deposit_growth=-0.05, deposit_withdrawal_pressure=0.06,
            loan_demand=0.03, payment_stress=0.11,
            delinquency_entry=0.08, cure_probability=-0.05,
            business_activity=-0.13, usd_preference=0.09,
        ),
        complete(REGIONS),
        complete(SECTORS, {"TRADE_IMPORT": 1.90, "RETAIL_SERVICES": 1.20, "SME_GENERAL": 1.10}),
        complete(PRODUCT_GROUPS, {"SME_CREDIT": 1.20, "BUSINESS_CREDIT_LINES": 1.25}),
        preferred_sectors=("TRADE_IMPORT",),
    ),
    EventSpec(
        "EXPORT_DEMAND_UPSWING", "Export demand upswing", "SECTORAL",
        0.055, "POSITIVE", 4, 9, 0.62, 0.18, 0.25, 1.10, 0.56, 0.83, 1, 5,
        effects(
            transaction_activity=0.07, transaction_amount=0.09,
            deposit_growth=0.10, deposit_withdrawal_pressure=-0.03,
            loan_demand=0.08, payment_stress=-0.07,
            delinquency_entry=-0.05, cure_probability=0.05,
            business_activity=0.15, usd_preference=0.05,
        ),
        complete(REGIONS),
        complete(SECTORS, {"TRADE_EXPORT": 1.90, "AGRICULTURE": 1.25}),
        complete(PRODUCT_GROUPS, {"BUSINESS_CREDIT_LINES": 1.20, "SME_CREDIT": 1.15}),
        preferred_sectors=("TRADE_EXPORT", "AGRICULTURE"),
    ),
    EventSpec(
        "RETAIL_SERVICES_SLOWDOWN", "Retail and services slowdown", "SECTORAL",
        0.055, "NEGATIVE", 3, 8, 0.60, 0.18, 0.25, 1.10, 0.54, 0.82, 1, 5,
        effects(
            transaction_activity=-0.11, transaction_amount=-0.08,
            deposit_growth=-0.07, deposit_withdrawal_pressure=0.05,
            loan_demand=-0.06, payment_stress=0.10,
            delinquency_entry=0.08, cure_probability=-0.05,
            business_activity=-0.16,
        ),
        complete(REGIONS),
        complete(SECTORS, {"RETAIL_SERVICES": 1.90, "SME_GENERAL": 1.25, "TOURISM": 1.15}),
        complete(PRODUCT_GROUPS, {"CARDS": 1.20, "SME_CREDIT": 1.20}),
        preferred_sectors=("RETAIL_SERVICES", "SME_GENERAL"),
    ),
)

IDIO_SPECS = (
    IdioSpec("JOB_LOSS", "Job loss", 0.030, -1, 0.72, 0.20, 0.25, 1.20, 2, 8, 2, 8, 1.00, 0.05, 0.70, 0.25, 0.15),
    IdioSpec("INCOME_REDUCTION", "Income reduction", 0.055, -1, 0.48, 0.16, 0.15, 0.95, 2, 7, 1, 6, 1.00, 0.30, 0.55, 0.20, 0.20),
    IdioSpec("EXTRAORDINARY_EXPENSE", "Extraordinary expense", 0.045, -1, 0.40, 0.15, 0.12, 0.85, 1, 4, 1, 4, 1.00, 0.10, 0.05, 0.05, 0.00),
    IdioSpec("BUSINESS_REVENUE_DROP", "Business revenue drop", 0.050, -1, 0.60, 0.18, 0.20, 1.05, 2, 8, 2, 7, 0.05, 1.00, 0.55, 0.30, 0.55),
    IdioSpec("BUSINESS_DISTRESS", "Business distress", 0.020, -1, 0.82, 0.18, 0.35, 1.25, 4, 12, 3, 10, 0.00, 1.00, 0.70, 0.35, 0.65),
    IdioSpec("POSITIVE_INCOME_SHOCK", "Positive income shock", 0.045, 1, 0.42, 0.14, 0.15, 0.90, 2, 7, 1, 5, 1.00, 0.45, 0.25, 0.10, 0.10),
    IdioSpec("BUSINESS_EXPANSION", "Business expansion", 0.030, 1, 0.55, 0.17, 0.20, 1.00, 3, 9, 1, 6, 0.00, 1.00, 0.30, 0.15, 0.25),
)


# =============================================================================
# Generic utilities
# =============================================================================

def derive_seed(world_seed: int, stream: int) -> int:
    modulus = 2**32 - 1
    value = (int(world_seed) * 1_000_003 + int(stream) * 97_409) % modulus
    return int(value if value > 0 else stream + 1)


def sigmoid(x):
    x = np.asarray(x, dtype=float)
    return 1.0 / (1.0 + np.exp(-x))


def infer_column(df: pd.DataFrame, candidates: Sequence[str]) -> str | None:
    lookup = {c.lower(): c for c in df.columns}
    for candidate in candidates:
        if candidate.lower() in lookup:
            return lookup[candidate.lower()]
    return None


def normalize(value: object) -> str:
    if pd.isna(value):
        return ""
    return str(value).strip().upper()


def robust_scale(series: pd.Series) -> pd.Series:
    x = pd.to_numeric(series, errors="coerce").fillna(0.0)
    med = x.median()
    mad = (x - med).abs().median()
    if mad > 1e-12:
        return (x - med) / (1.4826 * mad)
    sd = x.std(ddof=0)
    return (x - x.mean()) / sd if sd > 1e-12 else pd.Series(0.0, index=x.index)


def month_index(label: str) -> int:
    return pd.Period(label, freq="M").ordinal - MONTHS[0].ordinal


def month_label(idx: int) -> str:
    return str(MONTHS[int(idx)])


def direction(sign_mode: str, rng: np.random.Generator) -> int:
    if sign_mode == "POSITIVE":
        return 1
    if sign_mode == "NEGATIVE":
        return -1
    return 1 if rng.random() < 0.5 else -1


def bounded_noise(rng: np.random.Generator, n: int, sigma: float = 0.10):
    return np.clip(np.exp(rng.normal(0.0, sigma, n)), 0.65, 1.45)


def temporal_profile(duration: int, peak_offset: int, persistence: float, recovery_months: int, recovery_shape: float):
    duration = max(1, int(duration))
    peak_offset = int(np.clip(peak_offset, 0, duration - 1))
    core = np.zeros(duration)

    if peak_offset == 0:
        core[0] = 1.0
    else:
        for i in range(peak_offset + 1):
            core[i] = ((i + 1) / (peak_offset + 1)) ** 1.35

    core[peak_offset] = 1.0

    for i in range(peak_offset + 1, duration):
        core[i] = persistence ** (i - peak_offset)

    recovery = np.array([], dtype=float)
    if recovery_months > 0:
        start_level = max(core[-1] * 0.90, 0.03)
        recovery = np.array(
            [
                start_level * ((recovery_months - i) / recovery_months) ** recovery_shape
                for i in range(recovery_months)
            ]
        )

    return np.clip(core, 0.0, 1.0), np.clip(recovery, 0.0, 1.0)


# =============================================================================
# Customer preparation and resilience
# =============================================================================

def load_customers() -> pd.DataFrame:
    if not CUSTOMERS_PATH.exists():
        raise FileNotFoundError(f"Missing required input: {CUSTOMERS_PATH}")

    raw = pd.read_csv(CUSTOMERS_PATH)
    cid = infer_column(raw, ("customer_id", "client_id"))
    if cid is None:
        raise KeyError("customers.csv must contain customer_id.")

    out = pd.DataFrame({"customer_id": raw[cid]})

    type_col = infer_column(raw, ("customer_type", "client_type", "segment_type"))
    region_col = infer_column(raw, ("region", "customer_region", "home_region"))
    branch_col = infer_column(raw, ("branch_id", "home_branch_id", "primary_branch_id"))
    income_col = infer_column(raw, ("monthly_income", "income", "annual_income", "declared_income"))
    age_col = infer_column(raw, ("age", "customer_age"))
    tenure_col = infer_column(raw, ("tenure_years", "customer_tenure_years", "years_with_bank"))
    occupation_col = infer_column(raw, ("occupation", "occupation_group", "employment_type"))
    segment_col = infer_column(raw, ("segment", "customer_segment", "segment_name"))

    if type_col:
        s = raw[type_col].map(normalize)
        out["agent_type"] = np.where(
            s.str.contains("BUSINESS|COMPANY|CORPORATE|SME|EMPRESA", regex=True),
            "BUSINESS",
            "HOUSEHOLD",
        )
    else:
        out["agent_type"] = "HOUSEHOLD"

    if region_col:
        s = raw[region_col].map(normalize)
        mapping = {
            "MONTEVIDEO": "MONTEVIDEO", "METROPOLITAN": "METROPOLITAN",
            "EAST": "EAST", "NORTH": "NORTH", "CENTER": "CENTER",
            "CENTRE": "CENTER", "LITORAL": "LITORAL",
        }
        out["region"] = s.map(mapping).fillna("CENTER")
    else:
        out["region"] = "CENTER"

    out["branch_id"] = raw[branch_col] if branch_col else np.nan
    out["income_proxy"] = pd.to_numeric(raw[income_col], errors="coerce").fillna(0.0) if income_col else 0.0
    out["age_proxy"] = pd.to_numeric(raw[age_col], errors="coerce").fillna(40.0) if age_col else 40.0
    out["tenure_proxy"] = pd.to_numeric(raw[tenure_col], errors="coerce").fillna(4.0) if tenure_col else 4.0

    text = pd.Series("", index=raw.index, dtype=object)
    if occupation_col:
        text = text + " " + raw[occupation_col].fillna("").astype(str)
    if segment_col:
        text = text + " " + raw[segment_col].fillna("").astype(str)
    text = text.map(normalize)

    sector = np.where(out["agent_type"].eq("BUSINESS"), "SME_GENERAL", "HOUSEHOLD").astype(object)
    patterns = (
        ("TOURISM", r"TOUR|HOTEL|HOSPITALITY|RESTAUR|GASTRON"),
        ("AGRICULTURE", r"AGRIC|AGRO|RURAL|FARM|GANAD|CATTLE"),
        ("TRADE_IMPORT", r"IMPORT"),
        ("TRADE_EXPORT", r"EXPORT"),
        ("RETAIL_SERVICES", r"RETAIL|SERVICE|COMMERCE|COMERCIO|SHOP"),
    )
    for name, pattern in patterns:
        sector[text.str.contains(pattern, regex=True, na=False).to_numpy()] = name

    out["sector"] = sector
    return out


def load_financial_features(customers: pd.DataFrame) -> pd.DataFrame:
    features = customers[["customer_id"]].copy()

    if ACCOUNTS_PATH.exists():
        df = pd.read_csv(ACCOUNTS_PATH)
        cid = infer_column(df, ("customer_id", "client_id"))
        if cid:
            agg = df.groupby(cid).size().rename("account_count").reset_index().rename(columns={cid: "customer_id"})
            features = features.merge(agg, on="customer_id", how="left")

    if LOANS_PATH.exists():
        df = pd.read_csv(LOANS_PATH)
        cid = infer_column(df, ("customer_id", "client_id"))
        amount = infer_column(df, ("original_amount", "loan_amount", "principal_amount"))
        status = infer_column(df, ("loan_status", "status"))
        if cid:
            count = df.groupby(cid).size().rename("loan_count").reset_index().rename(columns={cid: "customer_id"})
            features = features.merge(count, on="customer_id", how="left")
            if amount:
                temp = df.assign(_amount=pd.to_numeric(df[amount], errors="coerce").fillna(0.0))
                total = temp.groupby(cid)["_amount"].sum().rename("loan_amount_total").reset_index().rename(columns={cid: "customer_id"})
                features = features.merge(total, on="customer_id", how="left")
            if status:
                bad = df[status].map(normalize).isin({"DEFAULTED", "WRITTEN_OFF", "RESTRUCTURED"}).astype(int)
                temp = df.assign(_bad=bad)
                hist = temp.groupby(cid)["_bad"].max().rename("adverse_loan_history").reset_index().rename(columns={cid: "customer_id"})
                features = features.merge(hist, on="customer_id", how="left")

    for col in ("account_count", "loan_count", "loan_amount_total", "adverse_loan_history"):
        if col not in features:
            features[col] = 0.0

    return features.fillna(0.0)


def build_resilience(customers: pd.DataFrame, financial: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    df = customers.merge(financial, on="customer_id", how="left")

    latent = (
        0.34 * robust_scale(df["income_proxy"]).clip(-2.5, 2.5)
        + 0.18 * robust_scale(df["tenure_proxy"]).clip(-2.5, 2.5)
        + 0.10 * robust_scale(df["account_count"]).clip(-2.5, 2.5)
        - 0.16 * robust_scale(df["loan_count"]).clip(-2.5, 2.5)
        - 0.16 * robust_scale(df["loan_amount_total"]).clip(-2.5, 2.5)
        - 0.45 * df["adverse_loan_history"].clip(0, 1)
        - 0.05 * df["agent_type"].eq("BUSINESS").astype(float)
        + rng.normal(0.0, 0.40, len(df))
    )

    resilience = sigmoid(latent)
    vulnerability = 1.0 - resilience

    return pd.DataFrame({
        "customer_id": df["customer_id"],
        "agent_type": df["agent_type"],
        "region": df["region"],
        "sector": df["sector"],
        "resilience_score": np.round(resilience, 8),
        "vulnerability_score": np.round(vulnerability, 8),
        "resilience_band": pd.cut(
            resilience,
            [-np.inf, 0.30, 0.45, 0.60, 0.75, np.inf],
            labels=["VERY_LOW", "LOW", "MEDIUM", "HIGH", "VERY_HIGH"],
        ).astype(str),
    })


# =============================================================================
# Main world generator
# =============================================================================

class ExternalShockWorld:
    def __init__(self, world_seed: int):
        self.world_seed = int(world_seed)

        def rng(stream):
            return np.random.default_rng(derive_seed(world_seed, stream))

        self.sys_occ = rng(STREAM_SYSTEMIC_OCCURRENCE)
        self.sys_time = rng(STREAM_SYSTEMIC_TIMING)
        self.sys_mag = rng(STREAM_SYSTEMIC_MAGNITUDE)
        self.sys_persist = rng(STREAM_SYSTEMIC_PERSISTENCE)

        self.reg_occ = rng(STREAM_REGIONAL_OCCURRENCE)
        self.reg_time = rng(STREAM_REGIONAL_TIMING)
        self.reg_mag = rng(STREAM_REGIONAL_MAGNITUDE)
        self.reg_scope = rng(STREAM_REGIONAL_SCOPE)

        self.sec_occ = rng(STREAM_SECTORAL_OCCURRENCE)
        self.sec_time = rng(STREAM_SECTORAL_TIMING)
        self.sec_mag = rng(STREAM_SECTORAL_MAGNITUDE)
        self.sec_scope = rng(STREAM_SECTORAL_SCOPE)

        self.exposure_rng = rng(STREAM_EXPOSURE)
        self.resilience_rng = rng(STREAM_RESILIENCE)
        self.interaction_rng = rng(STREAM_INTERACTION)
        self.recovery_rng = rng(STREAM_RECOVERY)

        self.idio_occ = rng(STREAM_IDIO_OCCURRENCE)
        self.idio_time = rng(STREAM_IDIO_TIMING)
        self.idio_mag = rng(STREAM_IDIO_MAGNITUDE)
        self.idio_med = rng(STREAM_IDIO_MEDIATION)
        self.customer_jitter = rng(STREAM_CUSTOMER_JITTER)

    @staticmethod
    def event_count(spec: EventSpec, rng: np.random.Generator) -> int:
        expected = spec.annual_hazard * 6.0
        return min(int(rng.poisson(expected)), 2)

    @staticmethod
    def draw_start(rng: np.random.Generator, occupied: np.ndarray, penalty: float) -> int:
        weights = np.exp(-penalty * occupied)
        weights /= weights.sum()
        return int(rng.choice(np.arange(N_MONTHS), p=weights))

    def generate_family(self, specs, occ_rng, time_rng, mag_rng, persist_rng, scale, counter):
        events, monthly, exposure = [], [], []
        occupied = np.zeros(N_MONTHS)

        for spec in specs:
            for _ in range(self.event_count(spec, occ_rng)):
                start = self.draw_start(time_rng, occupied, 0.55 if scale == "SYSTEMIC" else 0.35)
                duration = min(int(time_rng.integers(spec.min_duration, spec.max_duration + 1)), N_MONTHS - start)
                peak_offset = int(round(float(time_rng.beta(2.2, 3.0)) * max(duration - 1, 0)))
                persistence = float(persist_rng.uniform(spec.persistence_low, spec.persistence_high))
                recovery_months = int(self.recovery_rng.integers(spec.recovery_low, spec.recovery_high + 1))
                recovery_shape = float(self.recovery_rng.uniform(1.10, 2.10))
                magnitude = float(np.clip(mag_rng.normal(spec.magnitude_mean, spec.magnitude_sd), spec.magnitude_min, spec.magnitude_max))
                sign = direction(spec.sign_mode, mag_rng)

                core, recovery = temporal_profile(duration, peak_offset, persistence, recovery_months, recovery_shape)

                region_scope = "ALL"
                sector_scope = "ALL"
                if scale == "REGIONAL":
                    region_scope = str(self.reg_scope.choice(spec.preferred_regions or REGIONS))
                if scale == "SECTORAL":
                    sector_scope = str(self.sec_scope.choice(spec.preferred_sectors or SECTORS))

                shock_id = f"ES{counter:03d}"
                counter += 1

                end = start + duration - 1
                peak = start + peak_offset
                recovery_end = min(N_MONTHS - 1, end + len(recovery))

                events.append({
                    "shock_id": shock_id,
                    "shock_name": spec.label,
                    "shock_type": spec.shock_type,
                    "shock_scale": scale,
                    "direction": "POSITIVE" if sign > 0 else "NEGATIVE",
                    "region_scope": region_scope,
                    "sector_scope": sector_scope,
                    "start_month": month_label(start),
                    "peak_month": month_label(peak),
                    "end_month": month_label(end),
                    "recovery_end_month": month_label(recovery_end),
                    "duration_months": duration,
                    "recovery_months": len(recovery),
                    "peak_magnitude": round(magnitude, 8),
                    "signed_peak_intensity": round(sign * magnitude, 8),
                    "persistence": round(persistence, 8),
                    "recovery_shape": round(recovery_shape, 8),
                })

                for offset, value in enumerate(core):
                    monthly.append({
                        "shock_id": shock_id,
                        "year_month": month_label(start + offset),
                        "shock_type": spec.shock_type,
                        "shock_scale": scale,
                        "phase": "ACTIVE",
                        "direction": "POSITIVE" if sign > 0 else "NEGATIVE",
                        "profile_intensity": round(float(value), 8),
                        "realized_intensity": round(float(magnitude * value), 8),
                        "directional_state": round(float(sign * magnitude * value), 8),
                    })

                for offset, value in enumerate(recovery, start=1):
                    idx = end + offset
                    if idx >= N_MONTHS:
                        break
                    monthly.append({
                        "shock_id": shock_id,
                        "year_month": month_label(idx),
                        "shock_type": spec.shock_type,
                        "shock_scale": scale,
                        "phase": "RECOVERY",
                        "direction": "POSITIVE" if sign > 0 else "NEGATIVE",
                        "profile_intensity": round(float(value), 8),
                        "realized_intensity": round(float(magnitude * value), 8),
                        "directional_state": round(float(sign * magnitude * value), 8),
                    })

                region_noise = bounded_noise(self.exposure_rng, len(REGIONS))
                sector_noise = bounded_noise(self.exposure_rng, len(SECTORS))
                product_noise = bounded_noise(self.exposure_rng, len(PRODUCT_GROUPS))

                for i, region in enumerate(REGIONS):
                    mult = spec.region_exposure[region] * region_noise[i]
                    if scale == "REGIONAL":
                        mult *= 1.25 if region == region_scope else 0.35
                    exposure.append({
                        "shock_id": shock_id, "scope_type": "REGION",
                        "scope_value": region,
                        "exposure_multiplier": round(float(np.clip(mult, 0.05, 2.50)), 8),
                    })

                for i, sector in enumerate(SECTORS):
                    mult = spec.sector_exposure[sector] * sector_noise[i]
                    if scale == "SECTORAL":
                        mult *= 1.25 if sector == sector_scope else 0.35
                    exposure.append({
                        "shock_id": shock_id, "scope_type": "SECTOR",
                        "scope_value": sector,
                        "exposure_multiplier": round(float(np.clip(mult, 0.05, 2.50)), 8),
                    })

                for i, product in enumerate(PRODUCT_GROUPS):
                    mult = spec.product_exposure[product] * product_noise[i]
                    exposure.append({
                        "shock_id": shock_id, "scope_type": "PRODUCT_GROUP",
                        "scope_value": product,
                        "exposure_multiplier": round(float(np.clip(mult, 0.05, 2.50)), 8),
                    })

                for dim in TRANSMISSION_DIMENSIONS:
                    coeff = spec.base_effects[dim] * float(np.clip(self.exposure_rng.normal(1.0, 0.08), 0.75, 1.25))
                    exposure.append({
                        "shock_id": shock_id, "scope_type": "TRANSMISSION",
                        "scope_value": dim,
                        "exposure_multiplier": round(coeff, 8),
                    })

                occupied[start:end + 1] += 1

        return events, monthly, exposure, counter

    def generate_macro_world(self):
        events, monthly, exposure = [], [], []
        counter = 1

        families = (
            (SYSTEMIC_SPECS, self.sys_occ, self.sys_time, self.sys_mag, self.sys_persist, "SYSTEMIC"),
            (REGIONAL_SPECS, self.reg_occ, self.reg_time, self.reg_mag, self.reg_mag, "REGIONAL"),
            (SECTORAL_SPECS, self.sec_occ, self.sec_time, self.sec_mag, self.sec_mag, "SECTORAL"),
        )

        for specs, occ, timing, mag, persist, scale in families:
            e, m, x, counter = self.generate_family(specs, occ, timing, mag, persist, scale, counter)
            events.extend(e)
            monthly.extend(m)
            exposure.extend(x)

        event_cols = [
            "shock_id", "shock_name", "shock_type", "shock_scale", "direction",
            "region_scope", "sector_scope", "start_month", "peak_month", "end_month",
            "recovery_end_month", "duration_months", "recovery_months",
            "peak_magnitude", "signed_peak_intensity", "persistence", "recovery_shape",
        ]
        monthly_cols = [
            "shock_id", "year_month", "shock_type", "shock_scale", "phase",
            "direction", "profile_intensity", "realized_intensity", "directional_state",
        ]
        exposure_cols = ["shock_id", "scope_type", "scope_value", "exposure_multiplier"]

        return (
            pd.DataFrame(events, columns=event_cols),
            pd.DataFrame(monthly, columns=monthly_cols),
            pd.DataFrame(exposure, columns=exposure_cols),
        )

    def build_interactions(self, events: pd.DataFrame, monthly: pd.DataFrame):
        rules = {
            frozenset({"INFLATION_RATE_SHOCK", "ACTIVITY_SLOWDOWN"}): ("STAGFLATION_PRESSURE", 0.28),
            frozenset({"INFLATION_RATE_SHOCK", "REGIONAL_DROUGHT"}): ("RATE_DROUGHT_STRESS", 0.20),
            frozenset({"ACTIVITY_SLOWDOWN", "RETAIL_SERVICES_SLOWDOWN"}): ("RETAIL_RECESSION_AMPLIFIER", 0.22),
            frozenset({"FX_SHOCK", "IMPORT_COST_PRESSURE"}): ("FX_IMPORT_COST_AMPLIFIER", 0.24),
            frozenset({"ACTIVITY_BOOM", "EXPORT_DEMAND_UPSWING"}): ("EXPORT_EXPANSION_AMPLIFIER", -0.18),
        }

        cols = ["interaction_id", "interaction_type", "shock_id_a", "shock_id_b", "year_month", "interaction_intensity"]
        if events.empty or monthly.empty:
            return pd.DataFrame(columns=cols)

        type_by_id = events.set_index("shock_id")["shock_type"].to_dict()
        intensity = monthly.set_index(["shock_id", "year_month"])["realized_intensity"].to_dict()
        rows, counter = [], 1

        for month, ids in monthly.groupby("year_month")["shock_id"].apply(list).items():
            ids = sorted(set(ids))
            for i in range(len(ids)):
                for j in range(i + 1, len(ids)):
                    a, b = ids[i], ids[j]
                    key = frozenset({type_by_id[a], type_by_id[b]})
                    if key not in rules:
                        continue
                    name, strength = rules[key]
                    overlap = min(abs(float(intensity[(a, month)])), abs(float(intensity[(b, month)])))
                    jitter = float(np.clip(self.interaction_rng.normal(1.0, 0.10), 0.75, 1.25))
                    rows.append({
                        "interaction_id": f"XI{counter:04d}",
                        "interaction_type": name,
                        "shock_id_a": a,
                        "shock_id_b": b,
                        "year_month": month,
                        "interaction_intensity": round(strength * overlap * jitter, 8),
                    })
                    counter += 1

        return pd.DataFrame(rows, columns=cols)

    def build_shared_customer_state(self, customers, resilience, events, monthly, exposure, interactions):
        base = customers[["customer_id", "agent_type", "region", "sector"]].merge(
            resilience[["customer_id", "resilience_score", "vulnerability_score"]],
            on="customer_id",
            how="left",
        )

        event_scale = events.set_index("shock_id")["shock_scale"].to_dict() if not events.empty else {}
        exposure_lookup = {
            (r.shock_id, r.scope_type, r.scope_value): float(r.exposure_multiplier)
            for r in exposure.itertuples(index=False)
        }

        interaction_by_month = (
            interactions.groupby("year_month")["interaction_intensity"].sum().to_dict()
            if not interactions.empty else {}
        )

        frames = []

        for month in MONTH_LABELS:
            sys_state = np.zeros(len(base))
            reg_state = np.zeros(len(base))
            sec_state = np.zeros(len(base))

            month_events = monthly.loc[monthly["year_month"] == month]

            for r in month_events.itertuples(index=False):
                reg_mult = np.array([
                    exposure_lookup.get((r.shock_id, "REGION", region), 1.0)
                    for region in base["region"]
                ])
                sec_mult = np.array([
                    exposure_lookup.get((r.shock_id, "SECTOR", sector), 1.0)
                    for sector in base["sector"]
                ])
                jitter = bounded_noise(self.customer_jitter, len(base), sigma=0.08)
                effective = float(r.directional_state) * reg_mult * sec_mult * jitter

                scale = event_scale[r.shock_id]
                if scale == "SYSTEMIC":
                    sys_state += effective
                elif scale == "REGIONAL":
                    reg_state += effective
                else:
                    sec_state += effective

            interaction = float(interaction_by_month.get(month, 0.0))

            negative = np.minimum(sys_state, 0) + np.minimum(reg_state, 0) + np.minimum(sec_state, 0)
            positive = np.maximum(sys_state, 0) + np.maximum(reg_state, 0) + np.maximum(sec_state, 0)

            # Positive interaction values are adverse amplifiers; negative values are positive amplifiers.
            negative -= max(interaction, 0.0)
            positive += max(-interaction, 0.0)

            vulnerability = base["vulnerability_score"].to_numpy()
            resilience_score = base["resilience_score"].to_numpy()

            adverse = np.abs(negative) * (0.55 + 0.75 * vulnerability)
            positive_impulse = positive * (0.70 + 0.35 * resilience_score)

            frames.append(pd.DataFrame({
                "customer_id": base["customer_id"].to_numpy(),
                "year_month": month,
                "systemic_state": np.round(sys_state, 8),
                "regional_state": np.round(reg_state, 8),
                "sectoral_state": np.round(sec_state, 8),
                "interaction_state": round(interaction, 8),
                "adverse_shared_stress": np.round(np.clip(adverse, 0.0, 4.0), 8),
                "positive_shared_impulse": np.round(np.clip(positive_impulse, 0.0, 4.0), 8),
                "resilience_score": base["resilience_score"].to_numpy(),
                "vulnerability_score": base["vulnerability_score"].to_numpy(),
            }))

        return pd.concat(frames, ignore_index=True)

    def generate_idiosyncratic_events(self, customers: pd.DataFrame, shared_state: pd.DataFrame):
        state = shared_state.merge(
            customers[["customer_id", "agent_type", "region", "sector"]],
            on="customer_id",
            how="left",
        )

        cols = [
            "idio_event_id", "customer_id", "agent_type", "region", "sector",
            "event_type", "event_name", "direction", "start_month", "end_month",
            "recovery_end_month", "duration_months", "recovery_months",
            "raw_magnitude", "mediated_share", "residual_idiosyncratic_intensity",
            "shared_stress_at_start", "shared_positive_at_start", "realized_probability",
        ]

        rows, counter = [], 1
        last_event_month: Dict[tuple, int] = {}

        for spec in IDIO_SPECS:
            business = state["agent_type"].eq("BUSINESS").to_numpy()
            weight = np.where(business, spec.business_weight, spec.household_weight)

            base_monthly = 1.0 - (1.0 - spec.base_annual_probability) ** (1.0 / 12.0)
            base_logit = math.log(base_monthly / max(1.0 - base_monthly, 1e-12))

            adverse = state["adverse_shared_stress"].to_numpy()
            positive = state["positive_shared_impulse"].to_numpy()
            regional = np.abs(state["regional_state"].to_numpy())
            sectoral = np.abs(state["sectoral_state"].to_numpy())

            driver = adverse - 0.35 * positive if spec.sign < 0 else positive - 0.35 * adverse

            logits = (
                base_logit
                + np.log(np.clip(weight, 1e-4, None))
                + spec.macro_sensitivity * driver
                + spec.regional_sensitivity * regional
                + spec.sectoral_sensitivity * sectoral
            )
            probabilities = np.clip(sigmoid(logits), 0.0, 0.25)
            candidate_idx = np.flatnonzero(self.idio_occ.random(len(state)) < probabilities)

            for idx in candidate_idx:
                r = state.iloc[int(idx)]
                cid = r["customer_id"]
                m_idx = month_index(r["year_month"])
                cooldown_key = (cid, spec.event_type)

                if m_idx - last_event_month.get(cooldown_key, -999) < 4:
                    continue

                duration = min(
                    int(self.idio_time.integers(spec.min_duration, spec.max_duration + 1)),
                    N_MONTHS - m_idx,
                )
                recovery = int(self.idio_time.integers(spec.recovery_low, spec.recovery_high + 1))
                magnitude = float(np.clip(self.idio_mag.normal(spec.magnitude_mean, spec.magnitude_sd), spec.magnitude_min, spec.magnitude_max))

                shared = float(r["adverse_shared_stress"] if spec.sign < 0 else r["positive_shared_impulse"])
                mediated_share = float(np.clip(
                    (0.15 if spec.sign < 0 else 0.10)
                    + (0.25 if spec.sign < 0 else 0.20) * shared
                    + self.idio_med.normal(0.0, 0.05),
                    0.02,
                    0.55,
                ))

                residual = spec.sign * magnitude * (1.0 - mediated_share)
                end_idx = m_idx + duration - 1
                recovery_end = min(N_MONTHS - 1, end_idx + recovery)

                rows.append({
                    "idio_event_id": f"IE{counter:07d}",
                    "customer_id": cid,
                    "agent_type": r["agent_type"],
                    "region": r["region"],
                    "sector": r["sector"],
                    "event_type": spec.event_type,
                    "event_name": spec.label,
                    "direction": "POSITIVE" if spec.sign > 0 else "NEGATIVE",
                    "start_month": r["year_month"],
                    "end_month": month_label(end_idx),
                    "recovery_end_month": month_label(recovery_end),
                    "duration_months": duration,
                    "recovery_months": recovery,
                    "raw_magnitude": round(magnitude, 8),
                    "mediated_share": round(mediated_share, 8),
                    "residual_idiosyncratic_intensity": round(residual, 8),
                    "shared_stress_at_start": round(float(r["adverse_shared_stress"]), 8),
                    "shared_positive_at_start": round(float(r["positive_shared_impulse"]), 8),
                    "realized_probability": round(float(probabilities[int(idx)]), 10),
                })
                counter += 1
                last_event_month[cooldown_key] = m_idx

        return pd.DataFrame(rows, columns=cols)

    def apply_idiosyncratic_state(self, shared_state: pd.DataFrame, idio_events: pd.DataFrame):
        state = shared_state.copy()
        idio = np.zeros(len(state))
        index = {
            (r.customer_id, r.year_month): i
            for i, r in enumerate(state.itertuples(index=False))
        }

        for e in idio_events.itertuples(index=False):
            start = month_index(e.start_month)
            end = month_index(e.end_month)
            recovery_end = month_index(e.recovery_end_month)
            residual = float(e.residual_idiosyncratic_intensity)

            duration = end - start + 1
            core = np.array([1.0 if i == 0 else 0.90 ** i for i in range(duration)])

            for offset, profile in enumerate(core):
                row_idx = index.get((e.customer_id, month_label(start + offset)))
                if row_idx is not None:
                    idio[row_idx] += residual * profile

            recovery_months = max(recovery_end - end, 0)
            for offset in range(1, recovery_months + 1):
                row_idx = index.get((e.customer_id, month_label(end + offset)))
                if row_idx is None:
                    continue
                decay = ((recovery_months - offset + 1) / recovery_months) ** 1.5
                idio[row_idx] += residual * 0.55 * decay

        state["idiosyncratic_state"] = np.round(np.clip(idio, -4.0, 4.0), 8)
        state["net_external_state"] = np.round(np.clip(
            state["positive_shared_impulse"]
            - state["adverse_shared_stress"]
            + state["idiosyncratic_state"],
            -6.0,
            6.0,
        ), 8)
        return state


# =============================================================================
# Validation and audit
# =============================================================================

def validate(events, monthly, exposure, resilience, idio_events, customer_state, customer_count):
    errors = []

    if events["shock_id"].duplicated().any():
        errors.append("Duplicate shock_id.")

    if not monthly.empty:
        if not set(monthly["shock_id"]).issubset(set(events["shock_id"])):
            errors.append("Unknown shock_id in monthly state.")
        if not monthly["year_month"].isin(MONTH_LABELS).all():
            errors.append("Out-of-period month in monthly state.")
        if not monthly["profile_intensity"].between(0.0, 1.0000001).all():
            errors.append("Invalid temporal profile intensity.")

    if not exposure.empty:
        if exposure[["shock_id", "scope_type", "scope_value"]].duplicated().any():
            errors.append("Duplicate exposure row.")

    for e in events.itertuples(index=False):
        start = pd.Period(e.start_month, freq="M")
        peak = pd.Period(e.peak_month, freq="M")
        end = pd.Period(e.end_month, freq="M")
        recovery_end = pd.Period(e.recovery_end_month, freq="M")
        if not start <= peak <= end <= recovery_end:
            errors.append(f"{e.shock_id}: invalid chronology.")

    if not resilience["resilience_score"].between(0.0, 1.0).all():
        errors.append("Resilience outside [0,1].")

    expected = customer_count * N_MONTHS
    if len(customer_state) != expected:
        errors.append(f"Customer state rows {len(customer_state)} != expected {expected}.")

    if customer_state[["customer_id", "year_month"]].duplicated().any():
        errors.append("Duplicate customer-month state.")

    if not idio_events.empty and not idio_events["mediated_share"].between(0.0, 0.55).all():
        errors.append("Invalid mediated_share.")

    return errors


def macro_metrics(events: pd.DataFrame, monthly: pd.DataFrame):
    active = (
        monthly.groupby("year_month")["shock_id"].nunique().reindex(MONTH_LABELS, fill_value=0)
        if not monthly.empty else pd.Series(0, index=MONTH_LABELS)
    )
    net = (
        monthly.groupby("year_month")["directional_state"].sum().reindex(MONTH_LABELS, fill_value=0.0)
        if not monthly.empty else pd.Series(0.0, index=MONTH_LABELS)
    )
    counts = events["shock_scale"].value_counts() if not events.empty else pd.Series(dtype=int)

    return {
        "realized_shocks": len(events),
        "systemic_shocks": int(counts.get("SYSTEMIC", 0)),
        "regional_shocks": int(counts.get("REGIONAL", 0)),
        "sectoral_shocks": int(counts.get("SECTORAL", 0)),
        "positive_shocks": int((events["direction"] == "POSITIVE").sum()) if not events.empty else 0,
        "negative_shocks": int((events["direction"] == "NEGATIVE").sum()) if not events.empty else 0,
        "active_months": int((active > 0).sum()),
        "quiet_months": int((active == 0).sum()),
        "overlap_months": int((active > 1).sum()),
        "max_simultaneous_shocks": int(active.max()),
        "mean_abs_net_intensity": float(net.abs().mean()),
    }


def audit_macro_worlds(n_worlds: int, base_seed: int):
    rows = []
    for i in range(n_worlds):
        seed = base_seed + i * 7_919
        world = ExternalShockWorld(seed)
        events, monthly, _ = world.generate_macro_world()
        row = macro_metrics(events, monthly)
        row["audit_world"] = i + 1
        row["world_seed"] = seed
        rows.append(row)
    return pd.DataFrame(rows)


def print_audit(audit: pd.DataFrame):
    print()
    print("=" * 96)
    print("MULTI-WORLD MACRO AUDIT")
    print("=" * 96)
    print(f"Worlds simulated: {len(audit):,}")

    for col in (
        "realized_shocks", "systemic_shocks", "regional_shocks", "sectoral_shocks",
        "positive_shocks", "negative_shocks", "active_months", "quiet_months",
        "overlap_months", "max_simultaneous_shocks", "mean_abs_net_intensity",
    ):
        s = audit[col]
        print(
            f"{col:<30} mean={s.mean():7.3f} "
            f"p05={s.quantile(.05):7.3f} median={s.median():7.3f} "
            f"p95={s.quantile(.95):7.3f}"
        )

    quiet_pct = 100 * (audit["realized_shocks"] == 0).mean()
    extreme_pct = 100 * (audit["realized_shocks"] >= 10).mean()

    checks = {
        "quiet_worlds_possible": quiet_pct > 0.05,
        "nonquiet_worlds_common": (audit["realized_shocks"] > 0).mean() > 0.70,
        "extreme_worlds_rare": extreme_pct < 12.0,
        "systemic_possible": (audit["systemic_shocks"] > 0).mean() > 0.50,
        "regional_possible": (audit["regional_shocks"] > 0).mean() > 0.35,
        "sectoral_possible": (audit["sectoral_shocks"] > 0).mean() > 0.35,
        "positive_possible": (audit["positive_shocks"] > 0).mean() > 0.30,
        "negative_possible": (audit["negative_shocks"] > 0).mean() > 0.50,
        "quiet_months_exist": audit["quiet_months"].mean() > 6.0,
        "intensity_bounded": audit["mean_abs_net_intensity"].quantile(.99) < 2.0,
    }

    print()
    for name, ok in checks.items():
        print(f"  {name:<34} {'PASS' if ok else 'FAIL'}")

    failed = [k for k, v in checks.items() if not v]
    if failed:
        raise RuntimeError("Multi-world audit failed: " + ", ".join(failed))


def world_parameters(seed: int):
    return pd.DataFrame([{
        "engine_version": ENGINE_VERSION,
        "world_seed": seed,
        "period_start": START_MONTH,
        "period_end": END_MONTH,
        "systemic_occurrence_stream": STREAM_SYSTEMIC_OCCURRENCE,
        "systemic_timing_stream": STREAM_SYSTEMIC_TIMING,
        "systemic_magnitude_stream": STREAM_SYSTEMIC_MAGNITUDE,
        "systemic_persistence_stream": STREAM_SYSTEMIC_PERSISTENCE,
        "regional_occurrence_stream": STREAM_REGIONAL_OCCURRENCE,
        "regional_timing_stream": STREAM_REGIONAL_TIMING,
        "regional_magnitude_stream": STREAM_REGIONAL_MAGNITUDE,
        "regional_scope_stream": STREAM_REGIONAL_SCOPE,
        "sectoral_occurrence_stream": STREAM_SECTORAL_OCCURRENCE,
        "sectoral_timing_stream": STREAM_SECTORAL_TIMING,
        "sectoral_magnitude_stream": STREAM_SECTORAL_MAGNITUDE,
        "sectoral_scope_stream": STREAM_SECTORAL_SCOPE,
        "exposure_stream": STREAM_EXPOSURE,
        "resilience_stream": STREAM_RESILIENCE,
        "interaction_stream": STREAM_INTERACTION,
        "recovery_stream": STREAM_RECOVERY,
        "idio_occurrence_stream": STREAM_IDIO_OCCURRENCE,
        "idio_timing_stream": STREAM_IDIO_TIMING,
        "idio_magnitude_stream": STREAM_IDIO_MAGNITUDE,
        "idio_mediation_stream": STREAM_IDIO_MEDIATION,
        "customer_jitter_stream": STREAM_CUSTOMER_JITTER,
    }])


def write_outputs(events, monthly, exposure, resilience, interactions, idio_events, customer_state, params, audit):
    DATA_MASTER.mkdir(parents=True, exist_ok=True)
    DATA_INTERIM.mkdir(parents=True, exist_ok=True)

    events.to_csv(EVENTS_PATH, index=False)
    monthly.to_csv(MONTHLY_PATH, index=False)
    exposure.to_csv(EXPOSURE_PATH, index=False)
    resilience.to_csv(RESILIENCE_PATH, index=False)
    interactions.to_csv(INTERACTIONS_PATH, index=False)
    idio_events.to_csv(IDIO_EVENTS_PATH, index=False)
    customer_state.to_csv(CUSTOMER_STATE_PATH, index=False)
    params.to_csv(WORLD_PARAMS_PATH, index=False)

    if audit is not None:
        audit.to_csv(AUDIT_PATH, index=False)

    print()
    print("Saved:")
    for p in (
        EVENTS_PATH, MONTHLY_PATH, EXPOSURE_PATH, RESILIENCE_PATH,
        INTERACTIONS_PATH, IDIO_EVENTS_PATH, CUSTOMER_STATE_PATH,
        WORLD_PARAMS_PATH,
    ):
        print(f"  {p}")
    if audit is not None:
        print(f"  {AUDIT_PATH}")


# =============================================================================
# CLI
# =============================================================================

def parse_args():
    parser = argparse.ArgumentParser(description="BTYT multilevel external shock engine.")
    parser.add_argument("--seed", type=int, default=DEFAULT_WORLD_SEED)
    parser.add_argument("--audit-worlds", type=int, default=0)
    parser.add_argument("--audit-seed", type=int, default=20261001)
    parser.add_argument("--no-write", action="store_true")
    return parser.parse_args()


def main():
    args = parse_args()

    print("Loading customer universe...")
    customers = load_customers()
    financial = load_financial_features(customers)

    world = ExternalShockWorld(args.seed)
    resilience = build_resilience(customers, financial, world.resilience_rng)

    events, monthly, exposure = world.generate_macro_world()
    interactions = world.build_interactions(events, monthly)

    shared_state = world.build_shared_customer_state(
        customers, resilience, events, monthly, exposure, interactions
    )

    idio_events = world.generate_idiosyncratic_events(customers, shared_state)
    customer_state = world.apply_idiosyncratic_state(shared_state, idio_events)

    print("=" * 96)
    print("BTYT EXTERNAL SHOCK ENGINE — V1.1.2")
    print("=" * 96)
    print(f"World seed: {args.seed}")
    print(f"Customers: {len(customers):,}")
    print(f"Customer-month states: {len(customer_state):,}")

    metrics = macro_metrics(events, monthly)
    print()
    print("External events:")
    print(f"  Systemic:   {metrics['systemic_shocks']}")
    print(f"  Regional:   {metrics['regional_shocks']}")
    print(f"  Sectoral:   {metrics['sectoral_shocks']}")
    print(f"  Total:      {metrics['realized_shocks']}")
    print(f"  Positive:   {metrics['positive_shocks']}")
    print(f"  Negative:   {metrics['negative_shocks']}")
    print(f"  Quiet months: {metrics['quiet_months']} / {N_MONTHS}")
    print(f"  Overlap months: {metrics['overlap_months']} / {N_MONTHS}")

    print()
    print("Resilience:")
    print(f"  Mean: {resilience['resilience_score'].mean():.4f}")
    print(
        f"  P05 / P95: "
        f"{resilience['resilience_score'].quantile(.05):.4f} / "
        f"{resilience['resilience_score'].quantile(.95):.4f}"
    )

    print()
    print("Interactions:")
    print(f"  Rows: {len(interactions):,}")
    print(f"  Types: {interactions['interaction_type'].nunique() if not interactions.empty else 0}")

    print()
    print("Idiosyncratic events:")
    print(f"  Events: {len(idio_events):,}")
    print(f"  Customers affected: {idio_events['customer_id'].nunique() if not idio_events.empty else 0:,}")
    if not idio_events.empty:
        print(
            f"  Positive / Negative: "
            f"{(idio_events['direction'] == 'POSITIVE').sum():,} / "
            f"{(idio_events['direction'] == 'NEGATIVE').sum():,}"
        )

    if not events.empty:
        print()
        print(events[
            [
                "shock_id", "shock_scale", "shock_type", "direction",
                "region_scope", "sector_scope", "start_month", "peak_month",
                "end_month", "recovery_end_month", "peak_magnitude",
            ]
        ].to_string(index=False))

    errors = validate(
        events, monthly, exposure, resilience, idio_events,
        customer_state, len(customers)
    )

    if errors:
        print()
        print("VALIDATION: FAIL")
        for error in errors:
            print(f"  - {error}")
        raise RuntimeError("External shock production validation failed.")

    print()
    print("STRUCTURAL VALIDATION: PASS")

    audit = None
    if args.audit_worlds > 0:
        audit = audit_macro_worlds(args.audit_worlds, args.audit_seed)
        print_audit(audit)
        print()
        print("MULTI-WORLD MACRO VALIDATION: PASS")

    if not args.no_write:
        write_outputs(
            events, monthly, exposure, resilience, interactions,
            idio_events, customer_state, world_parameters(args.seed), audit
        )

    print()
    print("=" * 96)
    print("BTYT EXTERNAL SHOCK ENGINE V1.1.2: PASS")
    print("=" * 96)
    print("No frozen observable banking dataset was modified.")


if __name__ == "__main__":
    main()
