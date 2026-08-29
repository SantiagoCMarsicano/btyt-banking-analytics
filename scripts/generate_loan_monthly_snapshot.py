#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
BTYT — Loan Monthly Snapshot generator — V5 repayment calibration
===================================================================

Generates:

    data/processed/loan_monthly_snapshot.csv

Canonical grain:
    one row per loan per calendar month.

Canonical columns:
    loan_id
    year_month
    outstanding_balance
    current_interest_rate
    scheduled_payment
    actual_payment
    days_past_due
    delinquency_status
    arrears_amount

Architecture
------------
The master loan table defines the contract. The internal lifecycle bridge defines
the hidden exact origination month and the terminal lifecycle event. This script
turns those contracts into a monthly financial ledger for the detailed
observational window 2021-01 through 2026-12.

Important modeling principles:

1. Pre-2021 history is compressed. Old contracts enter January 2021 with an
   inherited balance and, when applicable, inherited arrears. The script does
   not fabricate a full pre-2021 monthly biography.

2. Scheduled payments are derived from the contract. They are not independently
   sampled.

3. Actual payments are stochastic but persistent. They depend on customer
   capacity, debt burden, macro conditions, branch/sector heterogeneity,
   previous arrears and loan-specific liquidity shocks.

4. DPD is derived from the exact due date of the oldest unpaid obligation.
   It is never generated independently and is never approximated by adding
   30 days per month.

5. Arrears are produced by the unpaid-obligation ledger. They are not sampled.

6. Outstanding balance is produced by principal and unpaid-interest mechanics.
   Arrears are part of the exposure and are not added a second time.

7. FIXED rates remain fixed. VARIABLE rates reprice coherently against a
   synthetic reference-rate path. MIXED rates have an initial fixed phase
   followed by repricing.

8. P016 Business Credit Line is revolving. original_amount is the approved
   limit; utilization can rise through drawdowns and fall through payments.

9. The bridge terminal event is not treated as an arbitrary analytical label.
   It is used as a lifecycle constraint so the detailed monthly history
   reconciles with the already-generated master contract status.

10. No target delinquency/default percentages are imposed. Monthly distributions
    emerge from contract mechanics, customer heterogeneity and stochastic paths.

The synthetic macro/reference series below are model inputs only. They are not
presented as official Uruguayan historical series.
"""

from __future__ import annotations

import calendar
import csv
import math
import os
import sys
import zlib
from collections import Counter, defaultdict, deque
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Deque, Dict, Iterable, List, Optional, Tuple

import numpy as np
import pandas as pd


# =============================================================================
# Paths and global configuration
# =============================================================================

ROOT = Path(__file__).resolve().parents[1]
DATA_PROCESSED = ROOT / "data" / "processed"
DATA_INTERIM = ROOT / "data" / "interim"

LOANS_PATH = DATA_PROCESSED / "loans.csv"
BRIDGE_PATH = DATA_INTERIM / "loan_lifecycle_bridge.csv"
CUSTOMERS_PATH = DATA_PROCESSED / "customers.csv"
ACCOUNTS_PATH = DATA_PROCESSED / "accounts.csv"
BRANCHES_PATH = DATA_PROCESSED / "branches.csv"

OUTPUT_PATH = DATA_PROCESSED / "loan_monthly_snapshot.csv"
TEMP_OUTPUT_PATH = DATA_PROCESSED / "loan_monthly_snapshot.tmp.csv"

SEED = 20260827
SNAPSHOT_SEED = SEED + 22022

OBS_START_YEAR = 2021
OBS_START_MONTH = 1
CUTOFF_YEAR = 2026
CUTOFF_MONTH = 12

OBS_START_IDX = OBS_START_YEAR * 12 + (OBS_START_MONTH - 1)
CUTOFF_IDX = CUTOFF_YEAR * 12 + (CUTOFF_MONTH - 1)

EPS = 0.005

OUTPUT_COLUMNS = [
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

REQUIRED_LOAN_COLUMNS = {
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
}

REQUIRED_BRIDGE_COLUMNS = {
    "loan_id",
    "origination_month_internal",
    "lifecycle_seed",
    "resolution_month_internal",
    "terminal_event_internal",
    "pre2021_inherited_state",
}


# =============================================================================
# Synthetic macro inputs
# =============================================================================

UYU_RATE_ANCHORS = {
    1969: 28.0, 1975: 34.0, 1980: 41.0, 1985: 49.0, 1990: 44.0,
    1995: 34.0, 1998: 31.0, 1999: 29.0, 2000: 27.0, 2001: 30.0,
    2002: 43.0, 2003: 35.0, 2004: 25.0, 2005: 19.0, 2006: 16.0,
    2007: 14.0, 2008: 15.5, 2009: 13.0, 2010: 12.0, 2011: 11.5,
    2012: 12.0, 2013: 12.5, 2014: 13.0, 2015: 14.5, 2016: 15.0,
    2017: 13.5, 2018: 13.0, 2019: 12.5, 2020: 10.5, 2021: 10.0,
    2022: 12.5, 2023: 14.0, 2024: 12.5, 2025: 11.5, 2026: 11.0,
    2027: 10.8,
}

USD_RATE_ANCHORS = {
    1969: 8.0, 1975: 9.0, 1980: 11.0, 1985: 13.0, 1990: 11.5,
    1995: 10.0, 1998: 10.0, 1999: 9.7, 2000: 9.4, 2001: 10.2,
    2002: 12.5, 2003: 10.5, 2004: 8.5, 2005: 7.8, 2006: 7.2,
    2007: 7.0, 2008: 7.8, 2009: 6.8, 2010: 6.2, 2011: 6.0,
    2012: 6.1, 2013: 6.2, 2014: 6.4, 2015: 6.8, 2016: 6.7,
    2017: 6.3, 2018: 6.4, 2019: 6.1, 2020: 5.4, 2021: 5.2,
    2022: 6.1, 2023: 7.3, 2024: 7.1, 2025: 6.8, 2026: 6.5,
    2027: 6.3,
}

FX_UYU_PER_USD_ANCHORS = {
    1993: 4.5, 1995: 6.5, 1998: 10.5, 2000: 12.1, 2002: 21.5,
    2004: 28.0, 2006: 24.0, 2008: 20.5, 2010: 20.0, 2012: 20.5,
    2014: 23.5, 2016: 30.5, 2018: 30.7, 2020: 42.0, 2022: 41.0,
    2024: 39.5, 2026: 42.0, 2027: 42.5,
}

MACRO_STRESS_BY_YEAR = {
    2021: 0.12,
    2022: 0.14,
    2023: 0.08,
    2024: 0.03,
    2025: 0.00,
    2026: -0.03,
}

PRODUCT_RATE_SENSITIVITY = {
    "P012": 0.70,
    "P013": 0.75,
    "P014": 0.65,
    "P015": 0.80,
    "P016": 0.90,
    "P017": 0.80,
    "P018": 0.75,
}

PRODUCT_REPRICE_MONTHS = {
    "P012": 6,
    "P013": 6,
    "P014": 12,
    "P015": 6,
    "P016": 3,
    "P017": 6,
    "P018": 6,
}

MIXED_FIXED_MONTHS = {
    "P012": 12,
    "P013": 24,
    "P014": 60,
    "P015": 24,
    "P016": 12,
    "P017": 24,
    "P018": 24,
}

PRODUCT_PAYMENT_RISK = {
    "P012": 0.05,
    "P013": 0.00,
    "P014": -0.05,
    "P015": 0.08,
    "P016": 0.10,
    "P017": 0.12,
    "P018": 0.05,
}


# =============================================================================
# Helpers
# =============================================================================

def sigmoid(x: float) -> float:
    x = float(np.clip(x, -35.0, 35.0))
    return 1.0 / (1.0 + math.exp(-x))


def stable_hash(text: str) -> int:
    return zlib.crc32(str(text).encode("utf-8")) & 0xFFFFFFFF


def stable_effect(text: str, amplitude: float) -> float:
    # Deterministic symmetric pseudo-random effect in [-amplitude, +amplitude].
    u = (stable_hash(text) % 1000003) / 1000003.0
    return (2.0 * u - 1.0) * amplitude


def ym_to_idx(year: int, month: int) -> int:
    return int(year) * 12 + (int(month) - 1)


def idx_to_ym(idx: int) -> Tuple[int, int]:
    year, m0 = divmod(int(idx), 12)
    return year, m0 + 1


def idx_to_str(idx: int) -> str:
    y, m = idx_to_ym(idx)
    return f"{y:04d}-{m:02d}"


def parse_period_string(value) -> Optional[int]:
    if pd.isna(value) or value is None:
        return None
    s = str(value).strip()
    if not s or s.lower() == "nan":
        return None
    y, m = s[:7].split("-")
    return ym_to_idx(int(y), int(m))


def interpolate_anchor(year_float: float, anchors: Dict[int, float]) -> float:
    years = np.array(sorted(anchors), dtype=float)
    values = np.array([anchors[int(y)] for y in years], dtype=float)
    return float(np.interp(float(year_float), years, values))


def monthly_reference_rate(currency: str, month_idx: int) -> float:
    y, m = idx_to_ym(month_idx)
    year_float = y + (m - 1) / 12.0
    anchors = UYU_RATE_ANCHORS if currency == "UYU" else USD_RATE_ANCHORS
    return interpolate_anchor(year_float, anchors)


def synthetic_fx_uyu_per_usd(month_idx: int) -> float:
    y, m = idx_to_ym(month_idx)
    year_float = max(1993.0, y + (m - 1) / 12.0)
    return interpolate_anchor(year_float, FX_UYU_PER_USD_ANCHORS)


def nominal_scale_to_2026(year: int) -> float:
    if year >= 2026:
        return 1.0
    if year >= 2000:
        return float(np.exp(-0.055 * (2026 - year)))
    if year >= 1990:
        return float(
            max(
                0.10,
                np.exp(-0.055 * 26)
                * np.exp(-0.070 * (2000 - year)),
            )
        )
    return 0.10


def annuity_payment(principal: float, annual_rate_pct: float, months: int) -> float:
    principal = max(float(principal), 0.0)
    months = max(int(months), 1)
    if principal <= EPS:
        return 0.0
    r = max(float(annual_rate_pct), 0.0) / 1200.0
    if r <= 1e-10:
        return principal / months
    denom = 1.0 - (1.0 + r) ** (-months)
    if abs(denom) < 1e-12:
        return principal / months
    return principal * r / denom


def amortized_balance_after(
    principal: float,
    annual_rate_pct: float,
    total_months: int,
    paid_months: int,
) -> float:
    principal = max(float(principal), 0.0)
    total_months = max(int(total_months), 1)
    paid_months = int(np.clip(paid_months, 0, total_months))

    if paid_months <= 0:
        return principal
    if paid_months >= total_months:
        return 0.0

    r = max(float(annual_rate_pct), 0.0) / 1200.0
    payment = annuity_payment(principal, annual_rate_pct, total_months)

    if r <= 1e-10:
        return max(principal - payment * paid_months, 0.0)

    balance = (
        principal * (1.0 + r) ** paid_months
        - payment * (((1.0 + r) ** paid_months - 1.0) / r)
    )
    return max(float(balance), 0.0)


def delinquency_band(dpd: int) -> str:
    dpd = int(max(dpd, 0))
    if dpd == 0:
        return "CURRENT"
    if dpd <= 30:
        return "DPD_1_30"
    if dpd <= 60:
        return "DPD_31_60"
    if dpd <= 90:
        return "DPD_61_90"
    return "DPD_90_PLUS"


def safe_float(value, default: float = 0.0) -> float:
    try:
        if pd.isna(value):
            return float(default)
        return float(value)
    except Exception:
        return float(default)


def safe_int(value, default: int = 0) -> int:
    try:
        if pd.isna(value):
            return int(default)
        return int(value)
    except Exception:
        return int(default)


def due_date_for_month(month_idx: int, due_day: int) -> date:
    y, m = idx_to_ym(month_idx)
    last_day = calendar.monthrange(y, m)[1]
    return date(y, m, min(int(due_day), last_day))


def month_end_date(month_idx: int) -> date:
    y, m = idx_to_ym(month_idx)
    return date(y, m, calendar.monthrange(y, m)[1])


def rate_for_month(
    product_id: str,
    currency: str,
    rate_type: str,
    initial_rate: float,
    orig_idx: int,
    current_idx: int,
) -> float:
    initial_rate = float(initial_rate)
    rate_type = str(rate_type).upper()

    if rate_type == "FIXED":
        return initial_rate

    elapsed = max(current_idx - orig_idx, 0)
    interval = PRODUCT_REPRICE_MONTHS.get(product_id, 6)
    sensitivity = PRODUCT_RATE_SENSITIVITY.get(product_id, 0.75)

    if rate_type == "MIXED":
        fixed_months = MIXED_FIXED_MONTHS.get(product_id, 24)
        if elapsed <= fixed_months:
            return initial_rate
        variable_elapsed = elapsed - fixed_months
        bucket = (variable_elapsed // interval) * interval
        repricing_idx = orig_idx + fixed_months + bucket
        base_idx = orig_idx + fixed_months
    else:
        bucket = (elapsed // interval) * interval
        repricing_idx = orig_idx + bucket
        base_idx = orig_idx

    ref_delta = (
        monthly_reference_rate(currency, repricing_idx)
        - monthly_reference_rate(currency, base_idx)
    )

    rate = initial_rate + sensitivity * ref_delta
    return float(np.clip(rate, 1.0, 75.0))


def convert_payment_to_uyu_2026eq(
    amount: float,
    currency: str,
    month_idx: int,
) -> float:
    y, _ = idx_to_ym(month_idx)
    uyu = float(amount)
    if currency == "USD":
        uyu *= synthetic_fx_uyu_per_usd(month_idx)
    return uyu / max(nominal_scale_to_2026(y), 1e-6)


# =============================================================================
# Input preparation
# =============================================================================

def load_inputs():
    missing = [
        p for p in [
            LOANS_PATH,
            BRIDGE_PATH,
            CUSTOMERS_PATH,
            ACCOUNTS_PATH,
            BRANCHES_PATH,
        ]
        if not p.exists()
    ]
    if missing:
        raise FileNotFoundError(
            "Missing required input file(s):\n"
            + "\n".join(f"  - {p}" for p in missing)
        )

    loans = pd.read_csv(LOANS_PATH, dtype={"loan_id": str, "customer_id": str})
    bridge = pd.read_csv(BRIDGE_PATH, dtype={"loan_id": str})
    customers = pd.read_csv(
        CUSTOMERS_PATH,
        dtype={"customer_id": str, "primary_branch_id": str},
    )
    accounts = pd.read_csv(
        ACCOUNTS_PATH,
        dtype={"customer_id": str, "account_id": str},
    )
    branches = pd.read_csv(BRANCHES_PATH, dtype={"branch_id": str})

    missing_loan_cols = REQUIRED_LOAN_COLUMNS - set(loans.columns)
    missing_bridge_cols = REQUIRED_BRIDGE_COLUMNS - set(bridge.columns)
    if missing_loan_cols:
        raise ValueError(
            f"loans.csv missing columns: {sorted(missing_loan_cols)}"
        )
    if missing_bridge_cols:
        raise ValueError(
            "loan_lifecycle_bridge.csv missing columns: "
            f"{sorted(missing_bridge_cols)}"
        )

    if loans["loan_id"].duplicated().any():
        raise ValueError("loans.csv contains duplicate loan_id values.")
    if bridge["loan_id"].duplicated().any():
        raise ValueError(
            "loan_lifecycle_bridge.csv contains duplicate loan_id values."
        )

    if set(loans["loan_id"]) != set(bridge["loan_id"]):
        only_loans = len(set(loans["loan_id"]) - set(bridge["loan_id"]))
        only_bridge = len(set(bridge["loan_id"]) - set(loans["loan_id"]))
        raise ValueError(
            "Master/bridge mismatch. "
            f"Only in loans={only_loans}, only in bridge={only_bridge}"
        )

    return loans, bridge, customers, accounts, branches


def zscore_log1p(series: pd.Series) -> pd.Series:
    s = pd.to_numeric(series, errors="coerce").fillna(0).clip(lower=0)
    x = np.log1p(s)
    sd = float(x.std(ddof=0))
    if not np.isfinite(sd) or sd <= 1e-12:
        return pd.Series(np.zeros(len(series)), index=series.index)
    return (x - float(x.mean())) / sd


def build_customer_features(
    customers: pd.DataFrame,
    accounts: pd.DataFrame,
) -> Dict[str, dict]:
    c = customers.copy()

    if "account_status" in accounts.columns:
        active_mask = accounts["account_status"].astype(str).eq("ACTIVE")
    elif "status" in accounts.columns:
        active_mask = accounts["status"].astype(str).eq("ACTIVE")
    else:
        active_mask = pd.Series(True, index=accounts.index)

    acc_counts = accounts.groupby("customer_id").size().rename("account_count")
    active_counts = (
        accounts.loc[active_mask]
        .groupby("customer_id")
        .size()
        .rename("active_account_count")
    )

    if "product_id" in accounts.columns:
        breadth = (
            accounts.groupby("customer_id")["product_id"]
            .nunique()
            .rename("product_breadth")
        )
    else:
        breadth = acc_counts.rename("product_breadth")

    c = c.merge(acc_counts, on="customer_id", how="left")
    c = c.merge(active_counts, on="customer_id", how="left")
    c = c.merge(breadth, on="customer_id", how="left")

    for col in ["account_count", "active_account_count", "product_breadth"]:
        c[col] = pd.to_numeric(c[col], errors="coerce").fillna(0)

    c["_income_z"] = zscore_log1p(
        c["monthly_income"] if "monthly_income" in c.columns else pd.Series(0, index=c.index)
    )
    c["_revenue_z"] = zscore_log1p(
        c["annual_revenue"] if "annual_revenue" in c.columns else pd.Series(0, index=c.index)
    )

    registration_year = pd.to_numeric(
        c.get("registration_year", pd.Series(CUTOFF_YEAR, index=c.index)),
        errors="coerce",
    ).fillna(CUTOFF_YEAR)

    tenure = (CUTOFF_YEAR - registration_year).clip(lower=0)
    tenure_sd = max(float(tenure.std(ddof=0)), 1.0)
    tenure_z = (tenure - float(tenure.mean())) / tenure_sd

    relationship_raw = (
        0.42 * np.log1p(c["active_account_count"])
        + 0.24 * np.log1p(c["product_breadth"])
        + 0.14 * tenure_z
    )
    c["_relationship"] = 1.0 / (1.0 + np.exp(-relationship_raw))

    employment_effect = (
        c.get("employment_status", pd.Series("", index=c.index))
        .astype(str)
        .map({
            "EMPLOYED": 0.25,
            "SELF_EMPLOYED": 0.18,
            "RETIRED": 0.02,
            "STUDENT": -0.18,
            "UNEMPLOYED": -0.45,
            "OTHER": -0.08,
        })
        .fillna(0.0)
    )

    indiv_raw = (
        0.74 * c["_income_z"]
        + 0.30 * c["_relationship"]
        + 0.14 * tenure_z
        + employment_effect
    )
    business_raw = (
        0.80 * c["_revenue_z"]
        + 0.26 * c["_relationship"]
        + 0.16 * tenure_z
    )

    is_individual = c["customer_type"].astype(str).eq("INDIVIDUAL")
    raw = np.where(is_individual, indiv_raw, business_raw)
    c["_capacity"] = 1.0 / (1.0 + np.exp(-raw))

    result = {}
    for row in c.itertuples(index=False):
        d = row._asdict()
        result[str(d["customer_id"])] = d
    return result


def build_branch_features(branches: pd.DataFrame) -> Dict[str, dict]:
    result = {}
    for row in branches.itertuples(index=False):
        d = row._asdict()
        bid = str(d["branch_id"])
        region = str(d.get("region", "UNKNOWN"))
        d["_branch_effect"] = (
            stable_effect(f"BRANCH::{bid}", 0.08)
            + stable_effect(f"REGION::{region}", 0.035)
        )
        result[bid] = d
    return result


# =============================================================================
# Obligation ledger
# =============================================================================

# Each obligation is a mutable list:
# [due_date, interest_remaining, principal_remaining]
Obligation = List[object]


def obligation_total(ob: Obligation) -> float:
    return max(float(ob[1]), 0.0) + max(float(ob[2]), 0.0)


def clean_obligations(obligations: Deque[Obligation]) -> None:
    while obligations and obligation_total(obligations[0]) <= EPS:
        obligations.popleft()


def total_arrears(
    obligations: Deque[Obligation],
    as_of: date,
) -> float:
    return float(
        sum(
            obligation_total(ob)
            for ob in obligations
            if ob[0] <= as_of and obligation_total(ob) > EPS
        )
    )


def unpaid_interest_total(obligations: Deque[Obligation]) -> float:
    return float(sum(max(float(ob[1]), 0.0) for ob in obligations))


def oldest_unpaid_due(
    obligations: Deque[Obligation],
    as_of: date,
) -> Optional[date]:
    for ob in obligations:
        if ob[0] <= as_of and obligation_total(ob) > EPS:
            return ob[0]
    return None


def allocate_payment(
    obligations: Deque[Obligation],
    principal_balance: float,
    cash: float,
) -> Tuple[float, float, float]:
    """
    Allocate cash FIFO against oldest obligations.

    Within each obligation:
      1) unpaid interest
      2) due principal

    Any cash remaining after all obligations is treated as direct principal
    prepayment.

    Returns:
        new_principal_balance,
        actual_cash_used,
        direct_extra_principal
    """
    principal_balance = max(float(principal_balance), 0.0)
    cash_available = max(float(cash), 0.0)
    initial_cash = cash_available

    for ob in obligations:
        if cash_available <= EPS:
            break

        interest_remaining = max(float(ob[1]), 0.0)
        if interest_remaining > EPS:
            paid = min(cash_available, interest_remaining)
            ob[1] = interest_remaining - paid
            cash_available -= paid

        if cash_available <= EPS:
            break

        principal_remaining = max(float(ob[2]), 0.0)
        if principal_remaining > EPS:
            paid = min(cash_available, principal_remaining)
            ob[2] = principal_remaining - paid
            principal_balance = max(principal_balance - paid, 0.0)
            cash_available -= paid

    clean_obligations(obligations)

    extra_principal = 0.0
    if cash_available > EPS and principal_balance > EPS:
        extra_principal = min(cash_available, principal_balance)
        principal_balance -= extra_principal
        cash_available -= extra_principal

    used = initial_cash - cash_available
    return principal_balance, float(used), float(extra_principal)


# =============================================================================
# Lifecycle constraints
# =============================================================================

PAID_TERMINAL_EVENTS = {
    "SCHEDULED_MATURITY",
    "EARLY_PREPAYMENT",
    "RELATIONSHIP_EXIT_RESOLUTION",
    "FACILITY_EXPIRY",
    "PAID_OFF",
}

RESTRUCTURE_EVENTS = {
    "RESTRUCTURE",
    "RESTRUCTURE_AFTER_DEFAULT",
    "RESTRUCTURED",
}

WRITEOFF_EVENTS = {
    "WRITE_OFF",
    "WRITTEN_OFF",
}

OPEN_DEFAULT_EVENTS = {
    "OPEN_DEFAULT_AT_CUTOFF",
    "SEVERE_RECOGNIZED_AT_CUTOFF",
}

OPEN_SEVERE_EVENTS = {
    "OPEN_SEVERE_AT_CUTOFF",
}

OPEN_EARLY_EVENTS = {
    "OPEN_EARLY_AT_CUTOFF",
}

OPEN_CURRENT_EVENTS = {
    "OPEN_CURRENT_AT_CUTOFF",
}


def terminal_mode(
    event: str,
    current_idx: int,
    end_idx: int,
) -> Optional[str]:
    """
    Bridge-to-ledger constraint.

    It shapes only the terminal portion of the payment path. Earlier monthly
    behavior remains stochastic.
    """
    event = str(event)
    distance = end_idx - current_idx

    if event in PAID_TERMINAL_EVENTS and distance == 0:
        return "CLOSE_FULL"

    if event in WRITEOFF_EVENTS:
        if distance == 0:
            return "WRITE_OFF"
        if 1 <= distance <= 7:
            return "MISS_HARD"

    if event == "RESTRUCTURE_AFTER_DEFAULT":
        if 0 <= distance <= 4:
            return "MISS_HARD"

    if event in RESTRUCTURE_EVENTS:
        if 0 <= distance <= 2:
            return "PARTIAL_HARD"

    if event in OPEN_DEFAULT_EVENTS:
        if 0 <= distance <= 4:
            return "MISS_HARD"

    if event in OPEN_SEVERE_EVENTS:
        if 0 <= distance <= 2:
            return "MISS_HARD"

    if event in OPEN_EARLY_EVENTS and distance == 0:
        return "PARTIAL"

    if event in OPEN_CURRENT_EVENTS and distance == 0:
        return "CURE_ALL"

    return None


# =============================================================================
# Loan simulation
# =============================================================================

@dataclass
class LoanAudit:
    rows: int = 0
    represented_loans: int = 0
    skipped_pre2021: int = 0
    total_scheduled: float = 0.0
    total_actual: float = 0.0
    max_dpd: int = 0
    max_p016_utilization: float = 0.0
    status_counts: Counter = None
    delinquency_counts: Counter = None
    year_counts: Counter = None
    payment_behavior_counts: Counter = None
    rate_change_counts: Counter = None
    cure_count: int = 0
    delinquency_entry_count: int = 0
    validation_errors: List[str] = None
    final_records: Dict[str, dict] = None

    def __post_init__(self):
        self.status_counts = Counter()
        self.delinquency_counts = Counter()
        self.year_counts = Counter()
        self.payment_behavior_counts = Counter()
        self.rate_change_counts = Counter()
        self.validation_errors = []
        self.final_records = {}


class SnapshotGenerator:
    def __init__(
        self,
        loans: pd.DataFrame,
        bridge: pd.DataFrame,
        customer_features: Dict[str, dict],
        branch_features: Dict[str, dict],
    ):
        self.loans = loans.copy()
        self.bridge = bridge.copy()
        self.customer_features = customer_features
        self.branch_features = branch_features
        self.audit = LoanAudit()

        self.bridge_lookup = {
            str(r.loan_id): r._asdict()
            for r in self.bridge.itertuples(index=False)
        }

    def _customer_capacity(self, customer_id: str) -> Tuple[float, float, dict]:
        c = self.customer_features.get(str(customer_id), {})
        return (
            float(c.get("_capacity", 0.5)),
            float(c.get("_relationship", 0.5)),
            c,
        )

    def _initial_installment_state(
        self,
        loan,
        bridge_row: dict,
        orig_idx: int,
        start_idx: int,
        due_day: int,
    ) -> Tuple[float, float, Deque[Obligation]]:
        """
        Return:
            actual_principal_balance,
            contractual_schedule_balance,
            unresolved_obligations

        The distinction between actual balance and contractual schedule balance
        is essential. A missed installment remains in arrears, but it must NOT
        be re-amortized again into all future scheduled installments.
        """
        original = float(loan.original_amount)
        principal = original
        schedule_balance = original
        obligations: Deque[Obligation] = deque()

        if start_idx <= orig_idx:
            return principal, schedule_balance, obligations

        # Contractual due months strictly before the observation start.
        elapsed_due = max(start_idx - (orig_idx + 1), 0)
        elapsed_due = min(elapsed_due, int(loan.term_months))

        inherited = str(bridge_row.get("pre2021_inherited_state", ""))

        if "SEVERE" in inherited:
            missed = 3
        elif "EARLY" in inherited:
            missed = 1
        else:
            missed = 0

        missed = min(missed, elapsed_due)
        paid_due = max(elapsed_due - missed, 0)

        # Actual principal reflects what was really paid before 2021.
        principal = amortized_balance_after(
            principal=original,
            annual_rate_pct=float(loan.initial_interest_rate),
            total_months=int(loan.term_months),
            paid_months=paid_due,
        )

        # Contractual schedule balance reflects every installment that should
        # already have fallen due, irrespective of whether the borrower paid it.
        schedule_balance = amortized_balance_after(
            principal=original,
            annual_rate_pct=float(loan.initial_interest_rate),
            total_months=int(loan.term_months),
            paid_months=elapsed_due,
        )

        if missed <= 0 or principal <= EPS:
            return principal, schedule_balance, obligations

        # Compressed inherited arrears: reconstruct only the unresolved
        # obligations immediately preceding 2021, not the entire pre-2021 life.
        first_missed_idx = start_idx - missed
        contract_balance = amortized_balance_after(
            principal=original,
            annual_rate_pct=float(loan.initial_interest_rate),
            total_months=int(loan.term_months),
            paid_months=paid_due,
        )

        maturity_idx = orig_idx + int(loan.term_months)

        for mi in range(first_missed_idx, start_idx):
            current_rate = rate_for_month(
                product_id=str(loan.product_id),
                currency=str(loan.currency),
                rate_type=str(loan.rate_type),
                initial_rate=float(loan.initial_interest_rate),
                orig_idx=orig_idx,
                current_idx=mi,
            )

            if mi <= maturity_idx and contract_balance > EPS:
                remaining_months = max(maturity_idx - mi + 1, 1)
                payment = annuity_payment(
                    contract_balance,
                    current_rate,
                    remaining_months,
                )
                interest_due = max(
                    contract_balance * current_rate / 1200.0,
                    0.0,
                )
                principal_due = max(
                    min(payment - interest_due, contract_balance),
                    0.0,
                )
            else:
                interest_due = 0.0
                principal_due = 0.0

            if interest_due + principal_due > EPS:
                obligations.append([
                    due_date_for_month(mi, due_day),
                    float(interest_due),
                    float(principal_due),
                ])

            # The contractual schedule advances even when the installment was
            # not actually paid; the unpaid principal stays in actual principal
            # and in the arrears ledger, but is not scheduled twice.
            contract_balance = max(contract_balance - principal_due, 0.0)

        schedule_balance = contract_balance
        return principal, schedule_balance, obligations

    def _initial_revolving_state(
        self,
        loan,
        bridge_row: dict,
        orig_idx: int,
        start_idx: int,
        rng: np.random.Generator,
        due_day: int,
    ) -> Tuple[float, Deque[Obligation]]:
        limit = max(float(loan.original_amount), 0.0)
        obligations: Deque[Obligation] = deque()

        capacity, relationship, _ = self._customer_capacity(loan.customer_id)

        # Stable utilization at entry into the observed window.
        a = 2.0 + 1.8 * (1.0 - capacity)
        b = 2.4 + 1.4 * relationship
        utilization = float(np.clip(rng.beta(a, b), 0.05, 0.92))
        principal = limit * utilization

        inherited = str(bridge_row.get("pre2021_inherited_state", ""))
        if start_idx > orig_idx and ("EARLY" in inherited or "SEVERE" in inherited):
            missed = 1 if "EARLY" in inherited else 3
            monthly_rate = float(loan.initial_interest_rate) / 1200.0
            approx_due = principal * monthly_rate + 0.02 * principal

            for mi in range(start_idx - missed, start_idx):
                interest_due = principal * monthly_rate
                principal_due = max(approx_due - interest_due, 0.0)
                obligations.append([
                    due_date_for_month(mi, due_day),
                    float(interest_due),
                    float(principal_due),
                ])

        return principal, obligations

    def _scheduled_installment(
        self,
        loan,
        schedule_balance: float,
        current_rate: float,
        orig_idx: int,
        current_idx: int,
    ) -> Tuple[float, float, float, float]:
        """
        Build the CURRENT contractual installment from the contractual schedule
        balance, not from the actual unpaid principal balance.

        This prevents a missed principal installment from being both:
          - retained in arrears, and
          - re-amortized into future scheduled installments.

        Returns:
            scheduled_payment,
            interest_due,
            principal_due,
            new_schedule_balance
        """
        schedule_balance = max(float(schedule_balance), 0.0)

        if current_idx <= orig_idx or schedule_balance <= EPS:
            return 0.0, 0.0, 0.0, schedule_balance

        maturity_idx = orig_idx + int(loan.term_months)

        if current_idx <= maturity_idx:
            remaining_months = max(maturity_idx - current_idx + 1, 1)
            monthly_rate = current_rate / 1200.0
            interest_due = max(schedule_balance * monthly_rate, 0.0)

            payment = annuity_payment(
                schedule_balance,
                current_rate,
                remaining_months,
            )
            principal_due = max(
                min(payment - interest_due, schedule_balance),
                0.0,
            )
            scheduled = interest_due + principal_due
            new_schedule_balance = max(
                schedule_balance - principal_due,
                0.0,
            )
        else:
            # After nominal maturity no NEW principal installment is created.
            # Any unresolved principal is already represented by older unpaid
            # obligations / actual principal exposure.
            interest_due = 0.0
            principal_due = 0.0
            scheduled = 0.0
            new_schedule_balance = schedule_balance

        return (
            float(scheduled),
            float(interest_due),
            float(principal_due),
            float(new_schedule_balance),
        )

    def _revolving_drawdown(
        self,
        loan,
        principal_balance: float,
        current_idx: int,
        capacity: float,
        relationship: float,
        liquidity_shock: float,
        terminal_constraint: Optional[str],
        rng: np.random.Generator,
    ) -> float:
        if terminal_constraint in {
            "MISS_HARD",
            "PARTIAL_HARD",
            "WRITE_OFF",
            "CLOSE_FULL",
        }:
            return 0.0

        limit = max(float(loan.original_amount), 0.0)
        available = max(limit - principal_balance, 0.0)
        if available <= EPS:
            return 0.0

        year, _ = idx_to_ym(current_idx)
        macro = MACRO_STRESS_BY_YEAR.get(year, 0.0)

        p_draw = float(np.clip(
            sigmoid(
                -1.55
                + 0.45 * relationship
                + 0.35 * (1.0 - capacity)
                + 0.35 * macro
                + 0.25 * liquidity_shock
            ),
            0.04,
            0.35,
        ))

        if rng.random() >= p_draw:
            return 0.0

        draw_fraction = float(np.clip(rng.beta(1.6, 5.0), 0.01, 0.55))
        draw = min(available, limit * draw_fraction)
        return float(max(draw, 0.0))

    def _scheduled_revolving(
        self,
        principal_balance: float,
        current_rate: float,
        orig_idx: int,
        current_idx: int,
        obligations: Deque[Obligation],
    ) -> Tuple[float, float, float]:
        if current_idx <= orig_idx or principal_balance <= EPS:
            return 0.0, 0.0, 0.0

        interest_due = principal_balance * current_rate / 1200.0

        # Avoid repeatedly scheduling the same revolving principal when prior
        # minimum-principal obligations remain unpaid.
        already_due_principal = float(
            sum(max(float(ob[2]), 0.0) for ob in obligations)
        )
        principal_not_already_due = max(
            principal_balance - already_due_principal,
            0.0,
        )
        principal_due = min(
            principal_balance * 0.02,
            principal_not_already_due,
        )

        scheduled = interest_due + principal_due
        return float(scheduled), float(interest_due), float(principal_due)

    def _payment_burden(
        self,
        loan,
        customer: dict,
        scheduled_payment: float,
        current_idx: int,
    ) -> float:
        scheduled_2026eq = convert_payment_to_uyu_2026eq(
            scheduled_payment,
            str(loan.currency),
            current_idx,
        )

        if str(customer.get("customer_type", "")) == "BUSINESS":
            annual_revenue = max(safe_float(customer.get("annual_revenue"), 0.0), 1.0)
            return float((scheduled_2026eq * 12.0) / annual_revenue)

        income = max(safe_float(customer.get("monthly_income"), 0.0), 1.0)
        return float(scheduled_2026eq / income)

    def _stochastic_payment_amount(
        self,
        loan,
        current_idx: int,
        scheduled_payment: float,
        arrears_before_current: float,
        principal_balance: float,
        capacity: float,
        relationship: float,
        customer: dict,
        branch_effect: float,
        liquidity_shock: float,
        terminal_constraint: Optional[str],
        rng: np.random.Generator,
    ) -> Tuple[float, str]:
        """
        Generate actual cash received for the month.

        V5 calibration principle
        ------------------------
        The contractual ledger, DPD logic and lifecycle reconciliation are left
        untouched. Only ordinary repayment behavior is recalibrated so that:

        * a borrower who is current is strongly persistent in CURRENT;
        * one-off early delinquency remains possible but uncommon;
        * existing arrears raise the chance of further difficulty;
        * curing is materially easier than entering deep delinquency;
        * severe terminal histories are still produced by the frozen lifecycle
          constraints rather than by arbitrary master-status labels.

        No portfolio delinquency percentage is targeted directly.
        """
        total_due = max(scheduled_payment + arrears_before_current, 0.0)

        # -------------------------------------------------------------
        # Frozen lifecycle reconciliation constraints.
        # These are intentionally unchanged from V4.
        # -------------------------------------------------------------
        if terminal_constraint == "CLOSE_FULL":
            unpaid_interest_buffer = max(arrears_before_current, 0.0)
            return (
                max(total_due + principal_balance + unpaid_interest_buffer, 0.0),
                "terminal_full_close",
            )

        if terminal_constraint == "CURE_ALL":
            return max(total_due, 0.0), "terminal_cure"

        if terminal_constraint == "WRITE_OFF":
            return 0.0, "writeoff_no_payment"

        if terminal_constraint == "MISS_HARD":
            if rng.random() < 0.82:
                return 0.0, "missed"
            return scheduled_payment * rng.uniform(0.05, 0.25), "partial"

        if terminal_constraint == "PARTIAL_HARD":
            return scheduled_payment * rng.uniform(0.15, 0.55), "partial"

        if terminal_constraint == "PARTIAL":
            return scheduled_payment * rng.uniform(0.35, 0.80), "partial"

        if scheduled_payment <= EPS and arrears_before_current <= EPS:
            return 0.0, "no_due"

        # -------------------------------------------------------------
        # Ordinary stochastic repayment behavior.
        # -------------------------------------------------------------
        year, _ = idx_to_ym(current_idx)
        macro = MACRO_STRESS_BY_YEAR.get(year, 0.0)

        burden = self._payment_burden(
            loan,
            customer,
            scheduled_payment,
            current_idx,
        )

        sector = str(customer.get("business_sector", ""))
        sector_effect = (
            stable_effect(f"SECTOR::{sector}", 0.07)
            if sector
            else 0.0
        )
        product_effect = PRODUCT_PAYMENT_RISK.get(
            str(loan.product_id),
            0.0,
        )

        arrears_pressure = min(
            arrears_before_current / max(scheduled_payment, 1.0),
            6.0,
        )

        # Strong persistence for a borrower who enters the month current.
        # Once arrears exist this protection disappears and the historical
        # repayment state becomes an explicit source of risk.
        current_state_protection = (
            -0.70 if arrears_before_current <= EPS else 0.0
        )

        risk = (
            -6.15
            + 1.45 * math.log1p(max(burden, 0.0) * 5.0)
            + 0.90 * (0.5 - capacity)
            - 0.38 * (relationship - 0.5)
            + 0.48 * macro
            + 0.48 * liquidity_shock
            + 0.34 * arrears_pressure
            + current_state_protection
            + branch_effect
            + sector_effect
            + product_effect
        )

        # Misses are rare in an otherwise healthy month. Partial payments are
        # somewhat more common than complete misses, but remain minority events.
        # Existing arrears naturally push both probabilities upward through
        # arrears_pressure rather than through a hard-coded delinquency state.
        p_miss = float(
            np.clip(
                sigmoid(risk),
                0.0005,
                0.16,
            )
        )

        p_partial = float(
            np.clip(
                0.30 * sigmoid(risk + 1.00),
                0.0020,
                0.14,
            )
        )

        u = rng.random()

        if u < p_miss:
            # A complete miss is more likely than a token payment once the
            # stochastic "miss" event has occurred.
            if rng.random() < 0.80:
                return 0.0, "missed"
            return (
                scheduled_payment * rng.uniform(0.08, 0.30),
                "partial",
            )

        if u < p_miss + p_partial:
            return (
                scheduled_payment * rng.uniform(0.55, 0.95),
                "partial",
            )

        # -------------------------------------------------------------
        # Performing / curing month.
        # -------------------------------------------------------------
        payment = scheduled_payment
        behavior = "full"

        if arrears_before_current > EPS:
            # Recovery is deliberately easier than continued deterioration for
            # non-terminal borrowers. Capacity, relationship depth and liquidity
            # still matter, so cures are stochastic rather than mechanical.
            cure_prob = float(
                np.clip(
                    sigmoid(
                        0.65
                        + 1.25 * capacity
                        + 0.55 * relationship
                        - 0.45 * max(burden - 0.25, 0.0)
                        - 0.22 * liquidity_shock
                        - 0.10 * min(arrears_pressure, 4.0)
                    ),
                    0.55,
                    0.94,
                )
            )

            if rng.random() < cure_prob:
                # Most curing episodes fully clear old arrears; a minority
                # improve materially but retain a small unresolved amount.
                if rng.random() < 0.78:
                    cure_fraction = 1.00
                else:
                    cure_fraction = rng.uniform(0.60, 0.95)

                payment += arrears_before_current * cure_fraction
                behavior = "cure_payment"

        # Small occasional voluntary overpayment for installment products.
        if (
            arrears_before_current <= EPS
            and str(loan.product_id) != "P016"
            and rng.random() < 0.008
            and principal_balance > scheduled_payment
        ):
            payment += scheduled_payment * rng.uniform(0.20, 0.80)
            behavior = "overpayment"

        return max(float(payment), 0.0), behavior

    def _write_row(
        self,
        writer,
        loan,
        month_idx: int,
        outstanding: float,
        current_rate: float,
        scheduled: float,
        actual: float,
        dpd: int,
        arrears: float,
        payment_behavior: str,
        previous_delinquency: Optional[str],
    ) -> str:
        status = delinquency_band(dpd)

        row = [
            str(loan.loan_id),
            idx_to_str(month_idx),
            round(max(outstanding, 0.0), 2),
            round(max(current_rate, 0.01), 4),
            round(max(scheduled, 0.0), 2),
            round(max(actual, 0.0), 2),
            int(max(dpd, 0)),
            status,
            round(max(arrears, 0.0), 2),
        ]
        writer.writerow(row)

        self.audit.rows += 1
        self.audit.total_scheduled += max(scheduled, 0.0)
        self.audit.total_actual += max(actual, 0.0)
        self.audit.max_dpd = max(self.audit.max_dpd, int(max(dpd, 0)))
        self.audit.delinquency_counts[status] += 1
        self.audit.year_counts[idx_to_ym(month_idx)[0]] += 1
        self.audit.payment_behavior_counts[payment_behavior] += 1

        if previous_delinquency is not None:
            if previous_delinquency == "CURRENT" and status != "CURRENT":
                self.audit.delinquency_entry_count += 1
            if previous_delinquency != "CURRENT" and status == "CURRENT":
                self.audit.cure_count += 1

        return status

    def _simulate_one(self, writer, loan) -> None:
        bridge_row = self.bridge_lookup[str(loan.loan_id)]

        orig_idx = parse_period_string(bridge_row["origination_month_internal"])
        if orig_idx is None:
            raise ValueError(
                f"{loan.loan_id}: missing origination_month_internal."
            )

        resolution_idx = parse_period_string(
            bridge_row.get("resolution_month_internal")
        )
        event = str(bridge_row.get("terminal_event_internal", ""))

        start_idx = max(orig_idx, OBS_START_IDX)

        if resolution_idx is not None and resolution_idx < OBS_START_IDX:
            self.audit.skipped_pre2021 += 1
            return

        end_idx = CUTOFF_IDX
        if resolution_idx is not None:
            end_idx = min(end_idx, resolution_idx)

        if end_idx < start_idx:
            self.audit.skipped_pre2021 += 1
            return

        seed = safe_int(
            bridge_row.get("lifecycle_seed"),
            SNAPSHOT_SEED + stable_hash(str(loan.loan_id)),
        )
        rng = np.random.default_rng((seed + SNAPSHOT_SEED) % (2**32 - 1))

        due_day = 5 + (stable_hash(f"DUE::{loan.loan_id}") % 21)

        capacity, relationship, customer = self._customer_capacity(
            str(loan.customer_id)
        )
        branch = self.branch_features.get(str(loan.branch_id), {})
        branch_effect = float(branch.get("_branch_effect", 0.0))

        if str(loan.product_id) == "P016":
            principal_balance, obligations = self._initial_revolving_state(
                loan,
                bridge_row,
                orig_idx,
                start_idx,
                rng,
                due_day,
            )
            schedule_balance = None
        else:
            (
                principal_balance,
                schedule_balance,
                obligations,
            ) = self._initial_installment_state(
                loan,
                bridge_row,
                orig_idx,
                start_idx,
                due_day,
            )

        liquidity_shock = rng.normal(0.0, 0.30)
        previous_delinquency = None
        prior_rate = None
        represented = False

        for month_idx in range(start_idx, end_idx + 1):
            represented = True
            year, _ = idx_to_ym(month_idx)
            month_end = month_end_date(month_idx)

            liquidity_shock = (
                0.76 * liquidity_shock
                + rng.normal(0.0, 0.38)
            )

            current_rate = rate_for_month(
                product_id=str(loan.product_id),
                currency=str(loan.currency),
                rate_type=str(loan.rate_type),
                initial_rate=float(loan.initial_interest_rate),
                orig_idx=orig_idx,
                current_idx=month_idx,
            )

            if prior_rate is not None and abs(current_rate - prior_rate) > 1e-7:
                self.audit.rate_change_counts[str(loan.rate_type)] += 1
            prior_rate = current_rate

            constraint = terminal_mode(event, month_idx, end_idx)

            # ---------------------------------------------------------
            # Revolving drawdown before current contractual obligation.
            # ---------------------------------------------------------
            if str(loan.product_id) == "P016":
                draw = self._revolving_drawdown(
                    loan,
                    principal_balance,
                    month_idx,
                    capacity,
                    relationship,
                    liquidity_shock,
                    constraint,
                    rng,
                )
                principal_balance = min(
                    principal_balance + draw,
                    float(loan.original_amount),
                )
                limit = max(float(loan.original_amount), EPS)
                self.audit.max_p016_utilization = max(
                    self.audit.max_p016_utilization,
                    principal_balance / limit,
                )

            # Arrears existing before this month's new obligation.
            arrears_before_current = total_arrears(obligations, month_end)

            # ---------------------------------------------------------
            # Contractual scheduled obligation.
            # ---------------------------------------------------------
            if str(loan.product_id) == "P016":
                scheduled, interest_due, principal_due = self._scheduled_revolving(
                    principal_balance,
                    current_rate,
                    orig_idx,
                    month_idx,
                    obligations,
                )
            else:
                (
                    scheduled,
                    interest_due,
                    principal_due,
                    schedule_balance,
                ) = self._scheduled_installment(
                    loan,
                    schedule_balance,
                    current_rate,
                    orig_idx,
                    month_idx,
                )

            if scheduled > EPS:
                obligations.append([
                    due_date_for_month(month_idx, due_day),
                    float(interest_due),
                    float(principal_due),
                ])

            # A rare edge case can occur when the stochastic path has already
            # exhausted the normal contractual schedule while the frozen
            # lifecycle bridge says the contract must remain unresolved and
            # reach DPD_90_PLUS at cutoff. The old residual-preservation guard
            # kept a tiny principal exposure alive but, because it had no due
            # date attached to it, DPD incorrectly remained zero forever.
            #
            # At the beginning of the terminal default window, attach any such
            # unscheduled residual principal to an exact contractual due date.
            # From here onward the normal FIFO obligation ledger determines
            # arrears and DPD; DPD itself is still never assigned directly.
            if (
                event in OPEN_DEFAULT_EVENTS
                and (end_idx - month_idx) == 4
                and principal_balance > EPS
                and not any(
                    obligation_total(ob) > EPS
                    and ob[0] <= month_end
                    for ob in obligations
                )
            ):
                anchor_principal = min(
                    principal_balance,
                    max(
                        float(loan.original_amount) * 0.000001,
                        0.01,
                    ),
                )
                if anchor_principal > EPS:
                    obligations.append([
                        due_date_for_month(month_idx, due_day),
                        0.0,
                        float(anchor_principal),
                    ])

            # ---------------------------------------------------------
            # Actual customer payment.
            # ---------------------------------------------------------
            cash_requested, payment_behavior = self._stochastic_payment_amount(
                loan=loan,
                current_idx=month_idx,
                scheduled_payment=scheduled,
                arrears_before_current=arrears_before_current,
                principal_balance=principal_balance,
                capacity=capacity,
                relationship=relationship,
                customer=customer,
                branch_effect=branch_effect,
                liquidity_shock=liquidity_shock,
                terminal_constraint=constraint,
                rng=rng,
            )

            # Terminal full payoff needs enough cash to clear obligations and all
            # remaining principal exactly.
            if constraint == "CLOSE_FULL":
                cash_requested = (
                    sum(obligation_total(ob) for ob in obligations)
                    + principal_balance
                )

            principal_balance, actual_used, extra_principal = allocate_payment(
                obligations,
                principal_balance,
                cash_requested,
            )

            if (
                str(loan.product_id) != "P016"
                and schedule_balance is not None
                and extra_principal > EPS
            ):
                # Voluntary principal prepayment changes future contractual
                # exposure; ordinary payment of scheduled principal does not,
                # because schedule_balance was already advanced when due.
                schedule_balance = max(
                    schedule_balance - extra_principal,
                    0.0,
                )

            # ---------------------------------------------------------
            # Terminal accounting events after payment allocation.
            # ---------------------------------------------------------
            if constraint == "WRITE_OFF":
                # Write-off occurs at the end of the final resolution month.
                principal_balance = 0.0
                obligations.clear()
                if schedule_balance is not None:
                    schedule_balance = 0.0

            if constraint == "CLOSE_FULL":
                # Numerical guard for exact settlement.
                principal_balance = 0.0
                obligations.clear()
                if schedule_balance is not None:
                    schedule_balance = 0.0

            unpaid_interest = unpaid_interest_total(obligations)
            outstanding = principal_balance + unpaid_interest
            arrears = total_arrears(obligations, month_end)

            oldest_due = oldest_unpaid_due(obligations, month_end)
            if oldest_due is None:
                dpd = 0
            else:
                dpd = max((month_end - oldest_due).days, 0)

            # Final-state reconciliation guards.
            if month_idx == end_idx:
                if event in OPEN_CURRENT_EVENTS:
                    # Open/current contract must finish current at cutoff.
                    if arrears > EPS:
                        extra_cash = arrears
                        principal_balance, extra_used, _ = allocate_payment(
                            obligations,
                            principal_balance,
                            extra_cash,
                        )
                        actual_used += extra_used
                        unpaid_interest = unpaid_interest_total(obligations)
                        outstanding = principal_balance + unpaid_interest
                        arrears = total_arrears(obligations, month_end)
                        oldest_due = oldest_unpaid_due(obligations, month_end)
                        dpd = (
                            max((month_end - oldest_due).days, 0)
                            if oldest_due is not None
                            else 0
                        )
                        payment_behavior = "terminal_cure"

                elif event in OPEN_EARLY_EVENTS:
                    # OPEN_EARLY_AT_CUTOFF means the loan finishes the observed
                    # window with a genuinely EARLY delinquency episode:
                    # older arrears must first be cured, while only a fraction
                    # of the CURRENT month's contractual obligation remains
                    # unpaid. This is much stronger than merely forcing a
                    # positive DPD, because it prevents an old severe arrears
                    # episode from being mislabeled as "early".
                    current_due = due_date_for_month(month_idx, due_day)

                    # In the exceptional case where the contract has no normal
                    # installment in the cutoff month (e.g. origination month),
                    # create a small contractual stub obligation so the bridge
                    # state remains temporally meaningful. This affects only
                    # OPEN_EARLY_AT_CUTOFF contracts and becomes the scheduled
                    # obligation reported for that month.
                    current_month_obligations = [
                        ob for ob in obligations if ob[0] == current_due
                    ]

                    if not current_month_obligations and principal_balance > EPS:
                        if str(loan.product_id) == "P016":
                            stub_interest = principal_balance * current_rate / 1200.0
                            stub_principal = min(
                                principal_balance * 0.02,
                                principal_balance,
                            )
                        else:
                            remaining_months = max(
                                int(loan.term_months)
                                - max(month_idx - orig_idx, 0),
                                1,
                            )
                            stub_payment = annuity_payment(
                                principal_balance,
                                current_rate,
                                remaining_months,
                            )
                            stub_interest = principal_balance * current_rate / 1200.0
                            stub_principal = min(
                                max(stub_payment - stub_interest, 0.0),
                                principal_balance,
                            )

                        stub_total = stub_interest + stub_principal
                        if stub_total > EPS:
                            obligations.append([
                                current_due,
                                float(stub_interest),
                                float(stub_principal),
                            ])
                            scheduled = max(scheduled, float(stub_total))

                    # Leave only a modest fraction of the most recent
                    # obligation unpaid. FIFO payment clears every older
                    # obligation first, which yields exact DPD in the 1-30 band.
                    total_due_now = sum(
                        obligation_total(ob)
                        for ob in obligations
                        if ob[0] <= month_end
                    )

                    current_due_total = sum(
                        obligation_total(ob)
                        for ob in obligations
                        if ob[0] == current_due
                    )

                    if current_due_total > EPS:
                        target_unpaid = max(
                            min(current_due_total * 0.25, current_due_total),
                            min(1.0, current_due_total),
                        )
                        cure_cash = max(total_due_now - target_unpaid, 0.0)

                        principal_balance, extra_used, _ = allocate_payment(
                            obligations,
                            principal_balance,
                            cure_cash,
                        )
                        actual_used += extra_used
                        payment_behavior = "terminal_early_partial"

                    unpaid_interest = unpaid_interest_total(obligations)
                    outstanding = principal_balance + unpaid_interest
                    arrears = total_arrears(obligations, month_end)
                    oldest_due = oldest_unpaid_due(obligations, month_end)
                    dpd = (
                        max((month_end - oldest_due).days, 0)
                        if oldest_due is not None
                        else 0
                    )

            # ---------------------------------------------------------
            # Online validation before writing.
            # ---------------------------------------------------------
            if outstanding < -EPS:
                self.audit.validation_errors.append(
                    f"{loan.loan_id} {idx_to_str(month_idx)} negative outstanding"
                )
            if arrears < -EPS:
                self.audit.validation_errors.append(
                    f"{loan.loan_id} {idx_to_str(month_idx)} negative arrears"
                )
            if current_rate <= 0:
                self.audit.validation_errors.append(
                    f"{loan.loan_id} {idx_to_str(month_idx)} nonpositive rate"
                )
            if arrears > outstanding + max(1.0, 0.001 * outstanding):
                # Overdue principal is already part of principal_balance and
                # overdue interest is part of unpaid_interest, so arrears cannot
                # materially exceed total outstanding exposure.
                self.audit.validation_errors.append(
                    f"{loan.loan_id} {idx_to_str(month_idx)} implausible arrears/exposure"
                )

            previous_delinquency = self._write_row(
                writer=writer,
                loan=loan,
                month_idx=month_idx,
                outstanding=outstanding,
                current_rate=current_rate,
                scheduled=scheduled,
                actual=actual_used,
                dpd=dpd,
                arrears=arrears,
                payment_behavior=payment_behavior,
                previous_delinquency=previous_delinquency,
            )

            # If principal is fully settled naturally before a bridge resolution
            # event, preserve a tiny residual until the bridge resolution month.
            # This avoids inventing an earlier contractual closure inconsistent
            # with the already-generated master lifecycle.
            if (
                month_idx < end_idx
                and principal_balance <= EPS
                and event not in WRITEOFF_EVENTS
            ):
                residual = max(float(loan.original_amount) * 1e-6, 0.01)
                principal_balance = residual

        if represented:
            self.audit.represented_loans += 1
            self.audit.status_counts[str(loan.loan_status)] += 1

            self.audit.final_records[str(loan.loan_id)] = {
                "loan_status": str(loan.loan_status),
                "terminal_event": event,
                "resolution_idx": resolution_idx,
                "final_month_idx": end_idx,
                "final_delinquency": previous_delinquency,
                "final_outstanding": float(outstanding),
                "final_arrears": float(arrears),
                "final_dpd": int(dpd),
            }

    def generate(self) -> LoanAudit:
        DATA_PROCESSED.mkdir(parents=True, exist_ok=True)

        if TEMP_OUTPUT_PATH.exists():
            TEMP_OUTPUT_PATH.unlink()

        with TEMP_OUTPUT_PATH.open(
            "w",
            newline="",
            encoding="utf-8",
            buffering=1024 * 1024,
        ) as f:
            writer = csv.writer(f)
            writer.writerow(OUTPUT_COLUMNS)

            total = len(self.loans)
            for i, loan in enumerate(self.loans.itertuples(index=False), start=1):
                self._simulate_one(writer, loan)

                if i % 2000 == 0 or i == total:
                    print(
                        f"  simulated {i:,}/{total:,} loans | "
                        f"rows={self.audit.rows:,}"
                    )

        os.replace(TEMP_OUTPUT_PATH, OUTPUT_PATH)
        return self.audit


# =============================================================================
# Validation and audit
# =============================================================================

def validate_final_reconciliation(
    audit: LoanAudit,
    loans: pd.DataFrame,
    bridge: pd.DataFrame,
) -> List[str]:
    errors = list(audit.validation_errors)
    bridge_lookup = bridge.set_index("loan_id").to_dict("index")

    for loan in loans.itertuples(index=False):
        lid = str(loan.loan_id)
        b = bridge_lookup[lid]
        resolution_idx = parse_period_string(b["resolution_month_internal"])

        if resolution_idx is not None and resolution_idx < OBS_START_IDX:
            continue

        rec = audit.final_records.get(lid)
        if rec is None:
            errors.append(f"{lid}: expected snapshot rows but none were generated.")
            continue

        event = str(rec["terminal_event"])
        final_balance = float(rec["final_outstanding"])
        final_arrears = float(rec["final_arrears"])
        final_dpd = int(rec["final_dpd"])
        final_delinq = str(rec["final_delinquency"])

        if event in PAID_TERMINAL_EVENTS:
            if final_balance > 0.05 or final_arrears > 0.05 or final_dpd != 0:
                errors.append(
                    f"{lid}: paid terminal event does not finish at zero/current."
                )

        if event in WRITEOFF_EVENTS:
            if final_balance > 0.05 or final_arrears > 0.05:
                errors.append(
                    f"{lid}: write-off terminal event does not finish at zero exposure."
                )

        if event in OPEN_CURRENT_EVENTS:
            if final_dpd != 0 or final_delinq != "CURRENT":
                errors.append(
                    f"{lid}: OPEN_CURRENT_AT_CUTOFF does not finish CURRENT."
                )

        if event in OPEN_EARLY_EVENTS:
            if not (1 <= final_dpd <= 30):
                errors.append(
                    f"{lid}: OPEN_EARLY_AT_CUTOFF final DPD={final_dpd}, expected 1-30."
                )

        if event in OPEN_SEVERE_EVENTS:
            if final_dpd < 31:
                errors.append(
                    f"{lid}: OPEN_SEVERE_AT_CUTOFF final DPD={final_dpd}, expected >=31."
                )

        if event in OPEN_DEFAULT_EVENTS:
            if final_dpd <= 90:
                errors.append(
                    f"{lid}: default-at-cutoff final DPD={final_dpd}, expected >90."
                )

        if str(loan.loan_status) == "DEFAULTED" and resolution_idx is None:
            if final_dpd <= 90:
                errors.append(
                    f"{lid}: master DEFAULTED at cutoff without DPD_90_PLUS history."
                )

    return errors


def print_audit(
    audit: LoanAudit,
    loans: pd.DataFrame,
    bridge: pd.DataFrame,
):
    print()
    print("=" * 80)
    print("BTYT LOAN MONTHLY SNAPSHOT AUDIT")
    print("=" * 80)

    expected_detail_loans = 0
    for r in bridge.itertuples(index=False):
        resolution_idx = parse_period_string(r.resolution_month_internal)
        orig_idx = parse_period_string(r.origination_month_internal)
        if orig_idx is None:
            continue
        if resolution_idx is not None and resolution_idx < OBS_START_IDX:
            continue
        if max(orig_idx, OBS_START_IDX) <= (
            min(resolution_idx, CUTOFF_IDX)
            if resolution_idx is not None
            else CUTOFF_IDX
        ):
            expected_detail_loans += 1

    print(f"Master loans: {len(loans):,}")
    print(f"Loans expected in detailed window: {expected_detail_loans:,}")
    print(f"Loans represented: {audit.represented_loans:,}")
    print(f"Pre-2021 resolved loans skipped: {audit.skipped_pre2021:,}")
    print(f"Snapshot rows: {audit.rows:,}")

    if audit.represented_loans:
        print(
            "Mean months per represented loan: "
            f"{audit.rows / audit.represented_loans:.2f}"
        )

    print("\nRows by year:")
    for year in sorted(audit.year_counts):
        print(f"  {year}: {audit.year_counts[year]:,}")

    print("\nDelinquency status (% of loan-months):")
    total_rows = max(audit.rows, 1)
    for status in [
        "CURRENT",
        "DPD_1_30",
        "DPD_31_60",
        "DPD_61_90",
        "DPD_90_PLUS",
    ]:
        n = audit.delinquency_counts[status]
        print(f"  {status:12s} {n:10,d}  {100*n/total_rows:7.3f}%")

    print("\nPayment behavior (% of loan-months):")
    for behavior, n in audit.payment_behavior_counts.most_common():
        print(f"  {behavior:22s} {n:10,d}  {100*n/total_rows:7.3f}%")

    print(
        "\nPortfolio scheduled/actual cash ratio: "
        f"{audit.total_actual / max(audit.total_scheduled, 1.0):.4f}"
    )
    print(f"Maximum observed DPD: {audit.max_dpd:,} days")
    print(f"Delinquency entries from CURRENT: {audit.delinquency_entry_count:,}")
    print(f"Observed cures to CURRENT: {audit.cure_count:,}")
    print(
        "Maximum P016 principal utilization / approved limit: "
        f"{100*audit.max_p016_utilization:.2f}%"
    )

    print("\nRate changes observed by contractual rate type:")
    for rt in ["FIXED", "MIXED", "VARIABLE"]:
        print(f"  {rt:8s}: {audit.rate_change_counts[rt]:,}")

    print("\nFinal master status among represented loans:")
    represented_total = max(sum(audit.status_counts.values()), 1)
    for status, n in audit.status_counts.most_common():
        print(f"  {status:14s} {n:8,d}  {100*n/represented_total:7.3f}%")

    final_by_event = Counter(
        rec["terminal_event"] for rec in audit.final_records.values()
    )
    print("\nTerminal events represented:")
    for event, n in final_by_event.most_common():
        print(f"  {event:32s} {n:8,d}")

    # Small reconciliation diagnostics.
    default_final = [
        r for r in audit.final_records.values()
        if r["loan_status"] == "DEFAULTED"
    ]
    if default_final:
        d90 = sum(r["final_dpd"] > 90 for r in default_final)
        print(
            "\nMaster DEFAULTED ending DPD_90_PLUS: "
            f"{d90}/{len(default_final)} "
            f"({100*d90/len(default_final):.2f}%)"
        )

    paid_final = [
        r for r in audit.final_records.values()
        if r["terminal_event"] in PAID_TERMINAL_EVENTS
    ]
    if paid_final:
        paid_zero = sum(
            r["final_outstanding"] <= 0.05
            and r["final_arrears"] <= 0.05
            and r["final_dpd"] == 0
            for r in paid_final
        )
        print(
            "Paid terminal events reconciled to zero: "
            f"{paid_zero}/{len(paid_final)} "
            f"({100*paid_zero/len(paid_final):.2f}%)"
        )


# =============================================================================
# Main
# =============================================================================

def main():
    print("Loading inputs...")
    loans, bridge, customers, accounts, branches = load_inputs()

    print(f"Loans: {len(loans):,}")
    print(f"Bridge rows: {len(bridge):,}")
    print(f"Customers: {len(customers):,}")
    print(f"Accounts: {len(accounts):,}")
    print(f"Branches: {len(branches):,}")

    print("\nPreparing customer/branch behavioral features...")
    customer_features = build_customer_features(customers, accounts)
    branch_features = build_branch_features(branches)

    print("\nGenerating loan monthly snapshot...")
    generator = SnapshotGenerator(
        loans=loans,
        bridge=bridge,
        customer_features=customer_features,
        branch_features=branch_features,
    )
    audit = generator.generate()

    errors = validate_final_reconciliation(audit, loans, bridge)

    if errors:
        print("\nVALIDATION: FAIL")
        print(f"Errors found: {len(errors):,}")
        for err in errors[:40]:
            print("  -", err)
        if len(errors) > 40:
            print(f"  ... plus {len(errors)-40:,} more")
        raise RuntimeError(
            "Loan monthly snapshot validation failed. "
            "Output was generated for inspection but should not be frozen."
        )

    print("\nVALIDATION: PASS")
    print_audit(audit, loans, bridge)

    print(f"\nSaved canonical: {OUTPUT_PATH}")
    print(f"Rows: {audit.rows:,}")
    print("Columns:", ", ".join(OUTPUT_COLUMNS))


if __name__ == "__main__":
    main()
