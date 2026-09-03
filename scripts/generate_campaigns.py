"""
BTYT Banking Analytics
Campaign Behavioral Engine — V1.0.2

Contactability and delivery calibration rewrite.

Changes from V1.0.1
-------------------
- Preserves the optimized 10,000-customer campaign simulation universe.
- Adds persistent customer-level latent contactability.
- Delivery failures are now correlated across attempts through customer
  contactability instead of behaving like nearly independent high-probability
  successes.
- Channel delivery probabilities are differentiated more strongly.
- Retry attempts after a failed delivery are probabilistic rather than automatic.
- Targeting and response calibration are intentionally unchanged.
- No downstream banking outcome is created by this engine.

Modeling philosophy is unchanged:
campaigns modify probabilities; they do not deterministically manufacture
customer responses or downstream banking outcomes.

All code and comments are intentionally written in English.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd


# =============================================================================
# Version and paths
# =============================================================================

ENGINE_VERSION = "1.0.2"
DEFAULT_WORLD_SEED = 20260902
DEFAULT_CUSTOMER_LIMIT = 10_000
DATASET_END_DATE = pd.Timestamp("2026-12-31")

ROOT = Path(__file__).resolve().parents[1]
DATA_MASTER = ROOT / "data" / "master"
DATA_GENERATED = ROOT / "data" / "generated"
DATA_INTERIM = ROOT / "data" / "interim"

CAMPAIGNS_PATH = DATA_MASTER / "campaigns.csv"
CAMPAIGN_CHANNELS_PATH = DATA_MASTER / "campaign_channels.csv"
CAMPAIGN_GEOGRAPHY_PATH = DATA_MASTER / "campaign_geography.csv"
PRODUCTS_PATH = DATA_MASTER / "products.csv"

CUSTOMERS_PATH = DATA_GENERATED / "customers.csv"
ACCOUNTS_PATH = DATA_GENERATED / "accounts.csv"
CARDS_PATH = DATA_GENERATED / "cards.csv"
LOANS_PATH = DATA_GENERATED / "loans.csv"
BRANCHES_PATH = DATA_GENERATED / "branches.csv"

EXTERNAL_STATE_PATH = DATA_INTERIM / "external_customer_monthly_state.csv"
RESILIENCE_PATH = DATA_INTERIM / "external_shock_resilience.csv"

OUT_CAMPAIGN_CUSTOMERS = DATA_GENERATED / "campaign_customers.csv"
OUT_CAMPAIGN_EXPOSURES = DATA_GENERATED / "campaign_exposures.csv"
OUT_WORLD_PARAMETERS = DATA_INTERIM / "campaign_world_parameters.csv"
OUT_AUDIT = DATA_INTERIM / "campaign_generation_audit.csv"


# =============================================================================
# Independent RNG streams
# =============================================================================

RNG_STREAMS = {
    "customer_subset": 680,
    "relationship_dates": 690,
    "product_dates": 691,
    "campaign_parameters": 700,
    "targeting": 701,
    "selection_timing": 702,
    "customer_contactability": 710,
    "exposure_occurrence": 711,
    "exposure_channel": 712,
    "exposure_timing": 713,
    "followup_occurrence": 714,
    "response_occurrence": 721,
    "response_direction": 722,
    "response_timing": 723,
    "fatigue": 731,
    "customer_response_heterogeneity": 732,
}


def make_rng(seed: int, stream: int) -> np.random.Generator:
    ss = np.random.SeedSequence([int(seed), int(stream)])
    return np.random.default_rng(ss)


# =============================================================================
# Configuration
# =============================================================================

VALID_CHANNELS = {
    "EMAIL",
    "SMS",
    "MOBILE_APP",
    "WEB",
    "BRANCH",
    "PHONE",
    "SOCIAL_MEDIA",
    "DIRECT_MAIL",
}

VALID_RESPONSE_STATUS = {"NO_RESPONSE", "POSITIVE", "NEGATIVE", "NEUTRAL"}
VALID_EXPOSURE_STATUS = {"EXPOSED", "NOT_EXPOSED"}

REACH_PRIOR_BY_TYPE = {
    "ACQUISITION": (2.4, 5.6),
    "CROSS_SELL": (2.0, 5.8),
    "UPSELL": (1.8, 6.2),
    "RETENTION": (2.0, 5.2),
    "ACTIVATION": (2.5, 5.0),
}

RESPONSE_BASE_LOGIT = {
    "ACQUISITION": -1.75,
    "CROSS_SELL": -1.95,
    "UPSELL": -2.05,
    "RETENTION": -1.85,
    "ACTIVATION": -1.70,
}

CHANNEL_DELIVERY_BASE = {
    # These represent successful customer exposure, not merely dispatch.
    # They are intentionally below V1.0.1 because customer-level contactability
    # and retry behavior now carry more of the delivery process.
    "EMAIL": 0.76,
    "SMS": 0.82,
    "MOBILE_APP": 0.86,
    "WEB": 0.55,
    "BRANCH": 0.50,
    "PHONE": 0.47,
    "SOCIAL_MEDIA": 0.57,
    "DIRECT_MAIL": 0.65,
}

DIGITAL_CHANNELS = {"EMAIL", "SMS", "MOBILE_APP", "WEB", "SOCIAL_MEDIA"}
HUMAN_CHANNELS = {"BRANCH", "PHONE"}

MIN_FOLLOWUP_DAYS = 4

RESPONSE_HORIZON_DAYS = {
    "TRANSACTIONAL_ACCOUNT": 21,
    "SAVINGS_DEPOSIT": 30,
    "CARD": 30,
    "RETAIL_LENDING": 60,
    "BUSINESS_LENDING": 75,
    "NO_PRODUCT": 30,
}


# =============================================================================
# Helpers
# =============================================================================

def sigmoid(x):
    x = np.clip(x, -20.0, 20.0)
    return 1.0 / (1.0 + np.exp(-x))


def logit(p):
    p = np.clip(p, 1e-8, 1.0 - 1e-8)
    return np.log(p / (1.0 - p))


def normalize_text(x) -> str:
    if pd.isna(x):
        return ""
    return str(x).strip()


def normalize_upper(x) -> str:
    return normalize_text(x).upper()


def normalize_customer_type(x) -> str:
    value = normalize_upper(x)
    if value in {"HOUSEHOLD", "PERSON", "INDIVIDUAL", "RETAIL"}:
        return "INDIVIDUAL"
    if value in {"BUSINESS", "COMPANY", "CORPORATE", "SME"}:
        return "BUSINESS"
    return value


def safe_numeric(series: pd.Series, default: float = 0.0) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").fillna(default)


def percentile_rank(series: pd.Series) -> pd.Series:
    s = safe_numeric(series, 0.0)
    return s.rank(method="average", pct=True).fillna(0.5)


def ensure_columns(df: pd.DataFrame, required: Iterable[str], name: str) -> None:
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise RuntimeError(f"{name} is missing required columns: {missing}")


def random_date_between(
    start: pd.Timestamp,
    end: pd.Timestamp,
    rng: np.random.Generator,
    beta_a: float = 1.4,
    beta_b: float = 2.2,
) -> pd.Timestamp:
    start = pd.Timestamp(start).normalize()
    end = pd.Timestamp(end).normalize()
    if end <= start:
        return start
    days = int((end - start).days)
    frac = float(rng.beta(beta_a, beta_b))
    return start + pd.Timedelta(days=int(round(frac * days)))


def campaign_month(ts: pd.Timestamp) -> str:
    return pd.Timestamp(ts).to_period("M").strftime("%Y-%m")


def softmax(values: np.ndarray) -> np.ndarray:
    values = np.asarray(values, dtype=float)
    values = values - np.max(values)
    expv = np.exp(values)
    return expv / expv.sum()


def timestamp_on_date(
    date: pd.Timestamp,
    channel: str,
    rng: np.random.Generator,
) -> pd.Timestamp:
    if channel == "PHONE":
        hour = int(rng.integers(9, 19))
    elif channel == "BRANCH":
        hour = int(rng.integers(10, 17))
    elif channel == "DIRECT_MAIL":
        hour = int(rng.integers(9, 18))
    else:
        hour = int(rng.integers(7, 23))

    minute = int(rng.integers(0, 60))
    second = int(rng.integers(0, 60))
    return (
        pd.Timestamp(date).normalize()
        + pd.Timedelta(hours=hour, minutes=minute, seconds=second)
    )


# =============================================================================
# Input loading
# =============================================================================

@dataclass
class Inputs:
    campaigns: pd.DataFrame
    channels: pd.DataFrame
    geography: pd.DataFrame
    products: pd.DataFrame
    customers: pd.DataFrame
    accounts: pd.DataFrame
    cards: pd.DataFrame
    loans: pd.DataFrame
    branches: pd.DataFrame
    external_state: pd.DataFrame
    resilience: pd.DataFrame


def read_csv_required(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Required file not found: {path}")
    df = pd.read_csv(path)
    if "index" in df.columns:
        df = df.drop(columns=["index"])
    return df


def read_csv_optional(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    df = pd.read_csv(path)
    if "index" in df.columns:
        df = df.drop(columns=["index"])
    return df


def load_inputs() -> Inputs:
    campaigns = read_csv_required(CAMPAIGNS_PATH)
    channels = read_csv_required(CAMPAIGN_CHANNELS_PATH)
    geography = read_csv_required(CAMPAIGN_GEOGRAPHY_PATH)
    products = read_csv_required(PRODUCTS_PATH)
    customers = read_csv_required(CUSTOMERS_PATH)
    accounts = read_csv_optional(ACCOUNTS_PATH)
    cards = read_csv_optional(CARDS_PATH)
    loans = read_csv_optional(LOANS_PATH)
    branches = read_csv_required(BRANCHES_PATH)
    external_state = read_csv_optional(EXTERNAL_STATE_PATH)
    resilience = read_csv_optional(RESILIENCE_PATH)

    ensure_columns(
        campaigns,
        [
            "campaign_id",
            "campaign_name",
            "campaign_type",
            "target_product_id",
            "start_date",
            "end_date",
            "target_customer_type",
        ],
        "campaigns.csv",
    )
    ensure_columns(channels, ["campaign_id", "channel"], "campaign_channels.csv")
    ensure_columns(
        geography,
        ["campaign_id", "geography_level", "geography_value"],
        "campaign_geography.csv",
    )
    ensure_columns(
        products,
        [
            "product_id",
            "product_name",
            "product_family",
            "target_customer_type",
            "launch_year",
        ],
        "products.csv",
    )
    ensure_columns(
        customers,
        [
            "customer_id",
            "customer_type",
            "residence_department",
            "residence_locality",
            "primary_branch_id",
            "registration_year",
            "customer_status",
            "closing_year",
        ],
        "customers.csv",
    )
    ensure_columns(
        branches,
        [
            "branch_id",
            "department",
            "locality",
            "region",
            "opening_year",
            "closing_year",
        ],
        "branches.csv",
    )

    campaigns["start_date"] = pd.to_datetime(campaigns["start_date"])
    campaigns["end_date"] = pd.to_datetime(campaigns["end_date"])
    campaigns["campaign_type"] = campaigns["campaign_type"].map(normalize_upper)
    campaigns["target_customer_type"] = campaigns["target_customer_type"].map(normalize_upper)
    channels["channel"] = channels["channel"].map(normalize_upper)
    geography["geography_level"] = geography["geography_level"].map(normalize_upper)
    geography["geography_value"] = geography["geography_value"].map(normalize_text)
    customers["normalized_customer_type"] = customers["customer_type"].map(
        normalize_customer_type
    )
    branches["region"] = branches["region"].map(normalize_upper)

    if not external_state.empty:
        ensure_columns(
            external_state,
            [
                "customer_id",
                "year_month",
                "adverse_shared_stress",
                "positive_shared_impulse",
                "net_external_state",
            ],
            "external_customer_monthly_state.csv",
        )

    if not resilience.empty:
        ensure_columns(
            resilience,
            ["customer_id", "resilience_score", "vulnerability_score"],
            "external_shock_resilience.csv",
        )

    return Inputs(
        campaigns=campaigns,
        channels=channels,
        geography=geography,
        products=products,
        customers=customers,
        accounts=accounts,
        cards=cards,
        loans=loans,
        branches=branches,
        external_state=external_state,
        resilience=resilience,
    )


# =============================================================================
# Deterministic 10k campaign universe
# =============================================================================

def select_campaign_universe(
    inputs: Inputs,
    world_seed: int,
    customer_limit: int | None,
) -> Inputs:
    """
    Select the customer universe used by the campaign engine.

    If customers.csv contains more than customer_limit customers, a deterministic
    random subset is selected using an independent RNG stream.

    This does NOT alter customers.csv or redefine the upstream banking universe.
    It only limits the customer panel processed by this campaign simulation.
    """
    if customer_limit is None or customer_limit <= 0:
        return inputs

    n = len(inputs.customers)
    if n <= customer_limit:
        return inputs

    rng = make_rng(world_seed, RNG_STREAMS["customer_subset"])
    idx = np.sort(rng.choice(n, size=customer_limit, replace=False))
    customers = inputs.customers.iloc[idx].copy().reset_index(drop=True)
    customer_ids = set(customers["customer_id"])

    def restrict(df: pd.DataFrame) -> pd.DataFrame:
        if df.empty or "customer_id" not in df.columns:
            return df
        return df[df["customer_id"].isin(customer_ids)].copy().reset_index(drop=True)

    return Inputs(
        campaigns=inputs.campaigns,
        channels=inputs.channels,
        geography=inputs.geography,
        products=inputs.products,
        customers=customers,
        accounts=restrict(inputs.accounts),
        cards=restrict(inputs.cards),
        loans=restrict(inputs.loans),
        branches=inputs.branches,
        external_state=restrict(inputs.external_state),
        resilience=restrict(inputs.resilience),
    )


# =============================================================================
# Historical state and optimized lookup maps
# =============================================================================

def infer_relationship_dates(
    customers: pd.DataFrame,
    rng: np.random.Generator,
) -> dict:
    lookup = {}

    for row in customers.itertuples(index=False):
        reg_year = int(row.registration_year)
        reg_date = random_date_between(
            pd.Timestamp(f"{reg_year}-01-01"),
            pd.Timestamp(f"{reg_year}-12-31"),
            rng,
            1.2,
            1.2,
        )

        if pd.isna(row.closing_year):
            close_date = pd.NaT
        else:
            close_year = int(row.closing_year)
            close_date = random_date_between(
                pd.Timestamp(f"{close_year}-01-01"),
                pd.Timestamp(f"{close_year}-12-31"),
                rng,
                1.2,
                1.2,
            )
            if close_date < reg_date:
                close_date = reg_date

        lookup[row.customer_id] = (reg_date, close_date)

    return lookup


def build_product_lookup(
    accounts: pd.DataFrame,
    cards: pd.DataFrame,
    loans: pd.DataFrame,
    rng: np.random.Generator,
):
    """
    Build O(1)-style product lifecycle lookup structures.

    exact_products[(customer_id, product_id)] -> list[(open_date, close_date)]
    family_products[(customer_id, family)] is created separately after products map.
    """
    exact_products = defaultdict(list)

    specs = [
        (accounts, "opening_year", "closing_year"),
        (cards, "issue_year", "closing_year"),
        (loans, "origination_year", "closing_year"),
    ]

    for df, open_col, close_col in specs:
        if df.empty:
            continue
        needed = {"customer_id", "product_id", open_col}
        if not needed.issubset(df.columns):
            continue

        for row in df.itertuples(index=False):
            open_year = getattr(row, open_col)
            if pd.isna(open_year) or pd.isna(row.product_id):
                continue

            open_year = int(open_year)
            open_date = random_date_between(
                pd.Timestamp(f"{open_year}-01-01"),
                pd.Timestamp(f"{open_year}-12-31"),
                rng,
                1.15,
                1.15,
            )

            close_year = getattr(row, close_col) if close_col in df.columns else np.nan
            if pd.isna(close_year):
                close_date = pd.NaT
            else:
                close_year = int(close_year)
                close_date = random_date_between(
                    pd.Timestamp(f"{close_year}-01-01"),
                    pd.Timestamp(f"{close_year}-12-31"),
                    rng,
                    1.15,
                    1.15,
                )
                if close_date < open_date:
                    close_date = open_date

            exact_products[(row.customer_id, str(row.product_id))].append(
                (open_date, close_date)
            )

    return exact_products


def interval_active(intervals, as_of_date: pd.Timestamp) -> bool:
    if not intervals:
        return False
    for open_date, close_date in intervals:
        if open_date <= as_of_date and (pd.isna(close_date) or close_date >= as_of_date):
            return True
    return False


def build_family_lookup(
    exact_products: dict,
    products: pd.DataFrame,
) -> dict:
    product_family = dict(
        zip(
            products["product_id"].astype(str),
            products["product_family"].map(normalize_upper),
        )
    )

    family_lookup = defaultdict(list)
    for (customer_id, product_id), intervals in exact_products.items():
        family = product_family.get(str(product_id))
        if family:
            family_lookup[(customer_id, family)].extend(intervals)

    return family_lookup


def build_external_lookup(external_state: pd.DataFrame) -> dict:
    if external_state.empty:
        return {}

    lookup = {}
    cols = [
        "customer_id",
        "year_month",
        "adverse_shared_stress",
        "positive_shared_impulse",
        "net_external_state",
    ]

    for row in external_state[cols].itertuples(index=False):
        lookup[(row.customer_id, str(row.year_month))] = (
            float(row.adverse_shared_stress),
            float(row.positive_shared_impulse),
            float(row.net_external_state),
        )

    return lookup


# =============================================================================
# Customer enrichment and geography
# =============================================================================

def enrich_customers(
    inputs: Inputs,
    relationship_lookup: dict,
    rng_contactability: np.random.Generator,
) -> pd.DataFrame:
    branch_geo = inputs.branches[
        ["branch_id", "department", "locality", "region"]
    ].drop_duplicates("branch_id")

    c = inputs.customers.merge(
        branch_geo,
        how="left",
        left_on="primary_branch_id",
        right_on="branch_id",
        suffixes=("", "_branch"),
    )

    c["campaign_department"] = c["residence_department"].where(
        c["residence_department"].notna()
        & (c["residence_department"].astype(str).str.len() > 0),
        c["department"],
    )
    c["campaign_locality"] = c["residence_locality"].where(
        c["residence_locality"].notna()
        & (c["residence_locality"].astype(str).str.len() > 0),
        c["locality"],
    )
    c["campaign_region"] = c["region"].map(normalize_upper)

    if "birth_year" in c.columns:
        c["birth_year_num"] = pd.to_numeric(c["birth_year"], errors="coerce")
    else:
        c["birth_year_num"] = np.nan

    c["income_rank"] = (
        percentile_rank(c["monthly_income"])
        if "monthly_income" in c.columns
        else 0.5
    )
    c["revenue_rank"] = (
        percentile_rank(c["annual_revenue"])
        if "annual_revenue" in c.columns
        else 0.5
    )

    c["employment_status_norm"] = (
        c["employment_status"].map(normalize_upper)
        if "employment_status" in c.columns
        else ""
    )
    c["business_sector_norm"] = (
        c["business_sector"].map(normalize_upper)
        if "business_sector" in c.columns
        else ""
    )

    age_2024 = 2024 - c["birth_year_num"]
    age_component = np.where(
        np.isfinite(age_2024),
        np.clip((55.0 - age_2024) / 35.0, -0.6, 0.8),
        0.0,
    )
    income_component = 0.35 * (c["income_rank"].to_numpy() - 0.5)
    urban_component = np.where(
        c["campaign_region"].isin(["METROPOLITAN", "EAST"]),
        0.12,
        -0.02,
    )
    c["digital_base_score"] = age_component + income_component + urban_component

    if not inputs.resilience.empty:
        c = c.merge(
            inputs.resilience[
                ["customer_id", "resilience_score", "vulnerability_score"]
            ],
            on="customer_id",
            how="left",
        )
    else:
        c["resilience_score"] = 0.5
        c["vulnerability_score"] = 0.5

    c["resilience_score"] = safe_numeric(c["resilience_score"], 0.5).clip(0, 1)
    c["vulnerability_score"] = safe_numeric(c["vulnerability_score"], 0.5).clip(0, 1)

    c["latent_registration_date"] = c["customer_id"].map(
        lambda cid: relationship_lookup[cid][0]
    )
    c["latent_closing_date"] = c["customer_id"].map(
        lambda cid: relationship_lookup[cid][1]
    )

    # Persistent latent contactability.
    #
    # This is deliberately customer-level rather than attempt-level. A customer
    # with stale contact information, weak digital engagement, low branch
    # interaction, or generally poor reachability is therefore more likely to
    # fail several delivery attempts in the same campaign. This creates
    # realistic positive correlation among delivery failures without making
    # exposure deterministic.
    contact_noise = rng_contactability.normal(0.0, 0.95, size=len(c))
    contact_logit = (
        0.10
        + 0.48 * c["digital_base_score"].to_numpy()
        + 0.18 * (c["resilience_score"].to_numpy() - 0.5)
        + contact_noise
    )
    c["latent_contactability"] = np.clip(
        sigmoid(contact_logit),
        0.06,
        0.97,
    )

    return c


def build_geography_eligibility(
    customers: pd.DataFrame,
    geography: pd.DataFrame,
) -> dict[str, set]:
    """
    Precompute eligible customer IDs for every campaign geography definition.
    """
    dept_map = defaultdict(set)
    locality_map = defaultdict(set)
    region_map = defaultdict(set)
    all_customers = set(customers["customer_id"])

    for row in customers[
        ["customer_id", "campaign_department", "campaign_locality", "campaign_region"]
    ].itertuples(index=False):
        dept_map[normalize_text(row.campaign_department).casefold()].add(row.customer_id)
        locality_map[normalize_text(row.campaign_locality).casefold()].add(row.customer_id)
        region_map[normalize_upper(row.campaign_region)].add(row.customer_id)

    result = {}

    for campaign_id, rows in geography.groupby("campaign_id", observed=True):
        eligible = set()

        for g in rows.itertuples(index=False):
            level = normalize_upper(g.geography_level)
            value = normalize_text(g.geography_value)

            if level == "NATIONAL" and normalize_upper(value) == "URUGUAY":
                eligible |= all_customers
            elif level == "REGION":
                eligible |= region_map[normalize_upper(value)]
            elif level == "DEPARTMENT":
                eligible |= dept_map[value.casefold()]
            elif level == "LOCALITY":
                eligible |= locality_map[value.casefold()]

        result[str(campaign_id)] = eligible

    return result


# =============================================================================
# Campaign parameters and product metadata
# =============================================================================

def build_campaign_parameters(
    campaigns: pd.DataFrame,
    channels: pd.DataFrame,
    rng: np.random.Generator,
) -> dict:
    params = {}

    channel_counts = channels.groupby("campaign_id")["channel"].nunique().to_dict()

    for campaign in campaigns.sort_values(["start_date", "campaign_id"]).itertuples(index=False):
        ctype = normalize_upper(campaign.campaign_type)
        a, b = REACH_PRIOR_BY_TYPE.get(ctype, (2.0, 5.5))

        params[str(campaign.campaign_id)] = {
            "reach_propensity": float(rng.beta(a, b)),
            "design_quality": float(rng.beta(4.5, 3.5)),
            "offer_attractiveness": float(rng.beta(4.0, 4.0)),
            "execution_quality": float(rng.beta(7.0, 2.2)),
            "authorized_channel_count": int(
                channel_counts.get(campaign.campaign_id, 0)
            ),
        }

    return params


def build_product_metadata(products: pd.DataFrame) -> dict:
    out = {}
    for row in products.itertuples(index=False):
        out[str(row.product_id)] = {
            "product_id": str(row.product_id),
            "product_name": normalize_text(row.product_name),
            "product_family": normalize_upper(row.product_family),
            "target_customer_type": normalize_upper(row.target_customer_type),
        }
    return out


def resolve_product(product_map: dict, product_id) -> dict:
    if pd.isna(product_id) or not normalize_text(product_id):
        return {
            "product_id": "",
            "product_name": "",
            "product_family": "NO_PRODUCT",
            "target_customer_type": "BOTH",
        }

    pid = str(product_id)
    if pid not in product_map:
        raise RuntimeError(f"Unknown target_product_id: {pid}")
    return product_map[pid]


# =============================================================================
# Eligibility and fit
# =============================================================================

def relationship_state(customer, as_of_date: pd.Timestamp) -> str:
    reg = customer.latent_registration_date
    close = customer.latent_closing_date

    if pd.isna(reg) or reg > as_of_date:
        return "PROSPECT"
    if pd.notna(close) and close < as_of_date:
        return "FORMER"
    return "CUSTOMER"


def broad_type_eligible(customer_type: str, target_type: str) -> bool:
    customer_type = normalize_customer_type(customer_type)
    target_type = normalize_upper(target_type)
    if target_type == "BOTH":
        return customer_type in {"INDIVIDUAL", "BUSINESS"}
    return customer_type == target_type


def current_age(birth_year, year: int) -> float:
    if pd.isna(birth_year):
        return np.nan
    return float(year - int(birth_year))


def product_fit_score(
    customer,
    product: dict,
    campaign_type: str,
    as_of_date: pd.Timestamp,
    exact_lookup: dict,
    family_lookup: dict,
) -> tuple[bool, float]:
    family = product["product_family"]
    product_id = product["product_id"]
    ctype = normalize_customer_type(customer.normalized_customer_type)
    campaign_type = normalize_upper(campaign_type)

    if product["target_customer_type"] not in {"", "BOTH", ctype}:
        return False, 0.0

    rel_state = relationship_state(customer, as_of_date)

    if campaign_type == "ACQUISITION":
        if rel_state != "PROSPECT":
            return False, 0.0
    else:
        if rel_state != "CUSTOMER":
            return False, 0.0

    if product_id:
        owns_target = interval_active(
            exact_lookup.get((customer.customer_id, product_id), []),
            as_of_date,
        )

        if campaign_type in {"CROSS_SELL", "UPSELL"} and owns_target:
            return False, 0.0

        if campaign_type == "UPSELL":
            owns_family = interval_active(
                family_lookup.get((customer.customer_id, family), []),
                as_of_date,
            )
            if not owns_family:
                return False, 0.0

    fit = 0.0
    age = current_age(customer.birth_year_num, as_of_date.year)

    if family == "TRANSACTIONAL_ACCOUNT":
        fit += 0.10
        if product_id == "P005":
            fit += (
                0.30
                if customer.employment_status_norm
                not in {"", "UNEMPLOYED", "INACTIVE"}
                else -0.20
            )
        if product_id == "P006" and np.isfinite(age):
            fit += 0.55 if 17 <= age <= 28 else -0.45

    elif family == "SAVINGS_DEPOSIT":
        if ctype == "INDIVIDUAL":
            fit += 0.45 * (float(customer.income_rank) - 0.5)
        else:
            fit += 0.40 * (float(customer.revenue_rank) - 0.5)
        fit += 0.08 * (float(customer.resilience_score) - 0.5)

    elif family == "CARD":
        fit += 0.35 * (float(customer.income_rank) - 0.5)
        if product_id == "P011":
            fit += 0.50 * (float(customer.income_rank) - 0.5)

    elif family == "RETAIL_LENDING":
        fit += 0.32 * (float(customer.income_rank) - 0.5)
        fit += 0.10 * (float(customer.resilience_score) - 0.5)
        if product_id == "P014" and np.isfinite(age):
            fit += 0.18 if 25 <= age <= 55 else -0.10

    elif family == "BUSINESS_LENDING":
        fit += 0.42 * (float(customer.revenue_rank) - 0.5)
        if product_id == "P017":
            sector = customer.business_sector_norm
            if "AGRI" in sector or "RURAL" in sector:
                fit += 0.45
            else:
                fit -= 0.18

    elif family == "NO_PRODUCT":
        if campaign_type == "RETENTION":
            fit += 0.18 * (float(customer.vulnerability_score) - 0.5)
        elif campaign_type == "ACTIVATION":
            fit += 0.20 * float(customer.digital_base_score)
        elif campaign_type == "CROSS_SELL":
            fit += 0.08

    return True, float(np.clip(fit, -0.75, 0.85))


# =============================================================================
# External environment and fatigue
# =============================================================================

def get_external_context(
    external_lookup: dict,
    customer_id,
    date: pd.Timestamp,
) -> tuple[float, float, float]:
    return external_lookup.get(
        (customer_id, campaign_month(date)),
        (0.0, 0.0, 0.0),
    )


def fatigue_score(
    exposure_history: dict,
    customer_id,
    as_of_date: pd.Timestamp,
) -> float:
    dates = exposure_history.get(customer_id)
    if not dates:
        return 0.0

    score = 0.0
    target = as_of_date.normalize()

    for d in dates:
        delta = (target - pd.Timestamp(d).normalize()).days
        if delta < 0:
            continue
        if delta <= 30:
            score += 0.32
        elif delta <= 60:
            score += 0.18
        elif delta <= 120:
            score += 0.08

    return float(np.clip(score, 0.0, 1.0))


# =============================================================================
# Channel modeling
# =============================================================================

def channel_preference_score(
    channel: str,
    customer,
    date: pd.Timestamp,
) -> float:
    channel = normalize_upper(channel)
    digital = float(customer.digital_base_score)
    year_progress = (date.year - 2021) / 5.0
    score = 0.0

    if channel in DIGITAL_CHANNELS:
        score += 0.48 * digital
        score += 0.18 * year_progress

    if channel in HUMAN_CHANNELS:
        score -= 0.14 * digital
        score -= 0.05 * year_progress

    if channel == "DIRECT_MAIL":
        score -= 0.28 * digital
        score -= 0.20 * year_progress
        if normalize_upper(customer.campaign_region) != "METROPOLITAN":
            score += 0.10

    if channel == "BRANCH":
        score += 0.06 if pd.notna(customer.primary_branch_id) else -0.12

    if channel == "PHONE":
        score += 0.03

    return float(np.clip(score, -0.75, 0.75))


def choose_channel(
    authorized_channels: list[str],
    customer,
    date: pd.Timestamp,
    rng: np.random.Generator,
) -> str:
    scores = np.array(
        [
            channel_preference_score(ch, customer, date)
            for ch in authorized_channels
        ],
        dtype=float,
    )
    return str(rng.choice(authorized_channels, p=softmax(scores)))


def successful_delivery_probability(
    channel: str,
    customer,
    campaign_param: dict,
    fatigue: float,
) -> float:
    """
    Probability that a contact attempt becomes a successful customer exposure.

    V1.0.2 uses persistent customer contactability as a common latent factor.
    Therefore repeated failures are conditionally correlated: another attempt
    helps, but it does not reset the customer to an unrelated delivery draw.
    """
    score = logit(CHANNEL_DELIVERY_BASE[channel])

    contactability = float(customer.latent_contactability)
    score += 1.35 * (contactability - 0.5)
    score += 0.60 * (campaign_param["execution_quality"] - 0.5)
    score -= 0.42 * fatigue

    digital = float(customer.digital_base_score)

    if channel in DIGITAL_CHANNELS:
        score += 0.24 * digital

    if channel == "EMAIL":
        score += 0.10 * (contactability - 0.5)

    elif channel == "SMS":
        score += 0.14 * (contactability - 0.5)

    elif channel == "MOBILE_APP":
        score += 0.18 * digital

    elif channel == "WEB":
        # A web impression is less equivalent to verified customer exposure
        # than a direct message.
        score -= 0.08

    elif channel == "SOCIAL_MEDIA":
        score -= 0.10

    elif channel == "DIRECT_MAIL":
        score -= 0.16 * digital
        score += 0.10 * (contactability - 0.5)

    elif channel == "BRANCH":
        score += 0.10 if pd.notna(customer.primary_branch_id) else -0.30

    elif channel == "PHONE":
        # Reachability dominates phone delivery.
        score += 0.22 * (contactability - 0.5)

    return float(np.clip(sigmoid(score), 0.08, 0.94))


# =============================================================================
# Response modeling
# =============================================================================

def response_probability(
    campaign_type: str,
    campaign_param: dict,
    product_fit: float,
    channel_fit: float,
    fatigue: float,
    adverse_shared_stress: float,
    positive_shared_impulse: float,
    heterogeneity: float,
) -> float:
    score = RESPONSE_BASE_LOGIT.get(campaign_type, -1.9)
    score += 0.85 * product_fit
    score += 0.50 * channel_fit
    score += 0.75 * (campaign_param["design_quality"] - 0.5)
    score += 0.80 * (campaign_param["offer_attractiveness"] - 0.5)
    score -= 0.95 * fatigue
    score += 0.10 * positive_shared_impulse
    score -= 0.13 * adverse_shared_stress
    score += 0.55 * heterogeneity
    return float(np.clip(sigmoid(score), 0.025, 0.72))


def response_status_draw(
    rng: np.random.Generator,
    campaign_type: str,
    product_fit: float,
    fatigue: float,
    adverse_shared_stress: float,
    positive_shared_impulse: float,
) -> str:
    positive = 0.50
    neutral = 0.32
    negative = 0.18

    positive += 0.18 * product_fit
    positive -= 0.14 * fatigue
    positive += 0.03 * positive_shared_impulse

    negative -= 0.08 * product_fit
    negative += 0.18 * fatigue
    negative += 0.04 * adverse_shared_stress

    if campaign_type == "RETENTION":
        neutral += 0.03

    weights = np.array(
        [max(0.05, positive), max(0.05, neutral), max(0.05, negative)],
        dtype=float,
    )
    weights /= weights.sum()

    return str(rng.choice(["POSITIVE", "NEUTRAL", "NEGATIVE"], p=weights))


def response_delay_days(
    product_family: str,
    rng: np.random.Generator,
) -> int:
    horizon = RESPONSE_HORIZON_DAYS.get(product_family, 30)
    delay = int(round(rng.gamma(shape=1.7, scale=max(1.0, horizon / 8.0))))
    return int(np.clip(delay, 0, horizon))


# =============================================================================
# Exposure modeling
# =============================================================================

def build_first_exposure(
    campaign_start: pd.Timestamp,
    campaign_end: pd.Timestamp,
    selection_date: pd.Timestamp,
    customer,
    authorized_channels: list[str],
    campaign_param: dict,
    fatigue: float,
    rng_channel: np.random.Generator,
    rng_occurrence: np.random.Generator,
    rng_timing: np.random.Generator,
):
    max_attempts = min(max(1, len(authorized_channels)), 3)
    channels_left = list(authorized_channels)

    for attempt in range(max_attempts):
        attempt_date = random_date_between(
            selection_date,
            campaign_end,
            rng_timing,
            beta_a=1.25 + 0.2 * attempt,
            beta_b=2.0,
        )

        channel = choose_channel(
            channels_left,
            customer,
            attempt_date,
            rng_channel,
        )

        p_delivery = successful_delivery_probability(
            channel,
            customer,
            campaign_param,
            fatigue,
        )

        if rng_occurrence.random() < p_delivery:
            return (
                True,
                timestamp_on_date(attempt_date, channel, rng_timing),
                channel,
            )

        if len(channels_left) > 1:
            channels_left.remove(channel)

        # A failed attempt does not guarantee that operations will try again.
        # Retry probability depends on campaign execution quality, campaign
        # channel breadth, customer contactability, and accumulated fatigue.
        #
        # The retry decision uses the exposure-occurrence RNG stream because it
        # belongs to the delivery process, while channel and timing keep their
        # own independent streams.
        retry_score = (
            -0.15
            + 0.85 * (campaign_param["execution_quality"] - 0.5)
            + 0.20 * (len(authorized_channels) - 1)
            + 0.55 * (float(customer.latent_contactability) - 0.5)
            - 0.55 * fatigue
            - 0.35 * attempt
        )
        p_retry = float(np.clip(sigmoid(retry_score), 0.18, 0.78))

        if attempt < max_attempts - 1 and rng_occurrence.random() >= p_retry:
            break

    return False, None, None


def generate_followups(
    campaign_end: pd.Timestamp,
    customer,
    authorized_channels: list[str],
    first_exposure_dt: pd.Timestamp,
    response_status: str,
    response_date,
    fatigue: float,
    campaign_param: dict,
    rng_followup: np.random.Generator,
    rng_channel: np.random.Generator,
    rng_occurrence: np.random.Generator,
    rng_timing: np.random.Generator,
):
    followups = []

    if response_status == "POSITIVE":
        base_p = 0.22
    elif response_status == "NEGATIVE":
        base_p = 0.10
    elif response_status == "NEUTRAL":
        base_p = 0.42
    else:
        base_p = 0.50

    base_p += 0.06 * (len(authorized_channels) - 1)
    base_p += 0.10 * (campaign_param["execution_quality"] - 0.5)
    base_p -= 0.20 * fatigue
    base_p = float(np.clip(base_p, 0.05, 0.72))

    previous_dt = first_exposure_dt

    for n in range(3):
        if rng_followup.random() >= base_p * (0.70 ** n):
            break

        earliest = previous_dt.normalize() + pd.Timedelta(days=MIN_FOLLOWUP_DAYS)
        latest = pd.Timestamp(campaign_end).normalize()

        if earliest > latest:
            break

        if pd.notna(response_date) and pd.Timestamp(response_date) < earliest:
            if response_status in {"POSITIVE", "NEGATIVE"}:
                if rng_followup.random() < 0.72:
                    break

        followup_date = random_date_between(
            earliest,
            latest,
            rng_timing,
            beta_a=1.4,
            beta_b=1.8,
        )

        channel = choose_channel(
            authorized_channels,
            customer,
            followup_date,
            rng_channel,
        )

        p_delivery = successful_delivery_probability(
            channel,
            customer,
            campaign_param,
            min(1.0, fatigue + 0.12 * (n + 1)),
        )

        if rng_occurrence.random() < p_delivery:
            dt = timestamp_on_date(followup_date, channel, rng_timing)
            if dt <= previous_dt:
                dt = previous_dt + pd.Timedelta(days=MIN_FOLLOWUP_DAYS)

            if dt.normalize() <= latest:
                followups.append((dt, channel))
                previous_dt = dt

    return followups


# =============================================================================
# Generation
# =============================================================================

def generate_campaign_behavior(
    inputs: Inputs,
    world_seed: int,
):
    rng_relationship = make_rng(world_seed, RNG_STREAMS["relationship_dates"])
    rng_product_dates = make_rng(world_seed, RNG_STREAMS["product_dates"])
    rng_campaign_params = make_rng(world_seed, RNG_STREAMS["campaign_parameters"])
    rng_targeting = make_rng(world_seed, RNG_STREAMS["targeting"])
    rng_selection_timing = make_rng(world_seed, RNG_STREAMS["selection_timing"])
    rng_contactability = make_rng(world_seed, RNG_STREAMS["customer_contactability"])
    rng_exposure_occurrence = make_rng(world_seed, RNG_STREAMS["exposure_occurrence"])
    rng_exposure_channel = make_rng(world_seed, RNG_STREAMS["exposure_channel"])
    rng_exposure_timing = make_rng(world_seed, RNG_STREAMS["exposure_timing"])
    rng_followup = make_rng(world_seed, RNG_STREAMS["followup_occurrence"])
    rng_response_occurrence = make_rng(world_seed, RNG_STREAMS["response_occurrence"])
    rng_response_direction = make_rng(world_seed, RNG_STREAMS["response_direction"])
    rng_response_timing = make_rng(world_seed, RNG_STREAMS["response_timing"])
    rng_fatigue = make_rng(world_seed, RNG_STREAMS["fatigue"])
    rng_heterogeneity = make_rng(
        world_seed,
        RNG_STREAMS["customer_response_heterogeneity"],
    )

    print("Precomputing relationship state...")
    relationship_lookup = infer_relationship_dates(inputs.customers, rng_relationship)

    print("Precomputing product lifecycle maps...")
    exact_lookup = build_product_lookup(
        inputs.accounts,
        inputs.cards,
        inputs.loans,
        rng_product_dates,
    )
    family_lookup = build_family_lookup(exact_lookup, inputs.products)

    print("Precomputing customer features...")
    customers = enrich_customers(
        inputs,
        relationship_lookup,
        rng_contactability,
    )

    print(
        "Contactability distribution: "
        f"mean={customers['latent_contactability'].mean():.3f} "
        f"p05={customers['latent_contactability'].quantile(0.05):.3f} "
        f"p50={customers['latent_contactability'].quantile(0.50):.3f} "
        f"p95={customers['latent_contactability'].quantile(0.95):.3f}"
    )

    print("Precomputing campaign geography eligibility...")
    geo_eligibility = build_geography_eligibility(
        customers,
        inputs.geography,
    )

    print("Precomputing external-state lookup...")
    external_lookup = build_external_lookup(inputs.external_state)

    print("Precomputing campaign parameters...")
    campaign_params = build_campaign_parameters(
        inputs.campaigns,
        inputs.channels,
        rng_campaign_params,
    )
    product_map = build_product_metadata(inputs.products)

    channel_map = (
        inputs.channels.groupby("campaign_id", observed=True)["channel"]
        .apply(lambda s: [normalize_upper(x) for x in s.tolist()])
        .to_dict()
    )

    customers_by_type = {
        ctype: customers[
            customers["normalized_customer_type"] == ctype
        ]
        for ctype in ["INDIVIDUAL", "BUSINESS"]
    }

    all_customer_lookup = {
        row.customer_id: row
        for row in customers.itertuples(index=False)
    }

    campaign_customer_rows = []
    exposure_rows = []
    audit_rows = []

    exposure_history = defaultdict(list)
    exposure_counter = 1

    campaigns = inputs.campaigns.sort_values(
        ["start_date", "campaign_id"]
    ).reset_index(drop=True)

    total_campaigns = len(campaigns)

    for campaign_idx, campaign in enumerate(
        campaigns.itertuples(index=False),
        start=1,
    ):
        campaign_id = str(campaign.campaign_id)
        campaign_type = normalize_upper(campaign.campaign_type)
        product = resolve_product(product_map, campaign.target_product_id)
        param = campaign_params[campaign_id]
        authorized_channels = channel_map.get(campaign_id, [])

        if not authorized_channels:
            raise RuntimeError(f"Campaign {campaign_id} has no authorized channels.")

        unknown_channels = set(authorized_channels) - VALID_CHANNELS
        if unknown_channels:
            raise RuntimeError(
                f"Campaign {campaign_id} has unsupported channels: "
                f"{sorted(unknown_channels)}"
            )

        geo_ids = geo_eligibility.get(campaign_id, set())

        if campaign.target_customer_type == "BOTH":
            type_candidates = customers
        else:
            type_candidates = customers_by_type.get(
                normalize_upper(campaign.target_customer_type),
                customers.iloc[0:0],
            )

        candidate_ids = set(type_candidates["customer_id"]) & geo_ids
        candidate_rows = [
            all_customer_lookup[cid]
            for cid in candidate_ids
        ]

        eligible_count = 0
        selected_count = 0
        exposed_count = 0
        response_count = 0
        positive_count = 0
        negative_count = 0
        neutral_count = 0
        no_response_count = 0

        for customer in candidate_rows:
            selection_date = random_date_between(
                campaign.start_date,
                campaign.end_date,
                rng_selection_timing,
                beta_a=1.35,
                beta_b=2.10,
            )

            eligible, fit = product_fit_score(
                customer,
                product,
                campaign_type,
                selection_date,
                exact_lookup,
                family_lookup,
            )

            if not eligible:
                continue

            eligible_count += 1

            fatigue = fatigue_score(
                exposure_history,
                customer.customer_id,
                selection_date,
            )

            reach = param["reach_propensity"]
            target_score = (
                logit(np.clip(0.06 + 0.78 * reach, 0.04, 0.80))
                + 0.78 * fit
                - 0.45 * fatigue
                + 0.18 * (param["design_quality"] - 0.5)
                + float(rng_targeting.normal(0.0, 0.18))
            )

            p_selected = float(
                np.clip(sigmoid(target_score), 0.015, 0.82)
            )

            if rng_targeting.random() >= p_selected:
                continue

            selected_count += 1

            effective_fatigue = float(
                np.clip(
                    fatigue + rng_fatigue.normal(0.0, 0.035),
                    0.0,
                    1.0,
                )
            )

            exposed, first_exposure_dt, first_channel = build_first_exposure(
                campaign.start_date,
                campaign.end_date,
                selection_date,
                customer,
                authorized_channels,
                param,
                effective_fatigue,
                rng_exposure_channel,
                rng_exposure_occurrence,
                rng_exposure_timing,
            )

            response_status = None
            response_date = pd.NaT

            if exposed:
                exposed_count += 1

                adverse, positive, net_state = get_external_context(
                    external_lookup,
                    customer.customer_id,
                    first_exposure_dt,
                )

                channel_fit = channel_preference_score(
                    first_channel,
                    customer,
                    first_exposure_dt,
                )

                heterogeneity = float(
                    rng_heterogeneity.normal(0.0, 1.0)
                )

                p_response = response_probability(
                    campaign_type,
                    param,
                    fit,
                    channel_fit,
                    effective_fatigue,
                    adverse,
                    positive,
                    heterogeneity,
                )

                if rng_response_occurrence.random() < p_response:
                    response_status = response_status_draw(
                        rng_response_direction,
                        campaign_type,
                        fit,
                        effective_fatigue,
                        adverse,
                        positive,
                    )
                    response_count += 1

                    delay = response_delay_days(
                        product["product_family"],
                        rng_response_timing,
                    )
                    response_date = (
                        first_exposure_dt.normalize()
                        + pd.Timedelta(days=delay)
                    )
                    response_date = min(
                        response_date,
                        DATASET_END_DATE,
                    )

                    if response_status == "POSITIVE":
                        positive_count += 1
                    elif response_status == "NEGATIVE":
                        negative_count += 1
                    else:
                        neutral_count += 1
                else:
                    response_status = "NO_RESPONSE"
                    no_response_count += 1

                exposure_rows.append(
                    {
                        "exposure_id": f"E{exposure_counter:06d}",
                        "campaign_id": campaign_id,
                        "customer_id": customer.customer_id,
                        "exposure_datetime": first_exposure_dt,
                        "channel": first_channel,
                    }
                )
                exposure_counter += 1
                exposure_history[customer.customer_id].append(first_exposure_dt)

                followups = generate_followups(
                    campaign.end_date,
                    customer,
                    authorized_channels,
                    first_exposure_dt,
                    response_status,
                    response_date,
                    effective_fatigue,
                    param,
                    rng_followup,
                    rng_exposure_channel,
                    rng_exposure_occurrence,
                    rng_exposure_timing,
                )

                for followup_dt, followup_channel in followups:
                    exposure_rows.append(
                        {
                            "exposure_id": f"E{exposure_counter:06d}",
                            "campaign_id": campaign_id,
                            "customer_id": customer.customer_id,
                            "exposure_datetime": followup_dt,
                            "channel": followup_channel,
                        }
                    )
                    exposure_counter += 1
                    exposure_history[customer.customer_id].append(
                        followup_dt
                    )

                exposure_status = "EXPOSED"
                exposure_date = first_exposure_dt.normalize()

            else:
                exposure_status = "NOT_EXPOSED"
                exposure_date = pd.NaT

            campaign_customer_rows.append(
                {
                    "campaign_id": campaign_id,
                    "customer_id": customer.customer_id,
                    "selection_date": selection_date.normalize(),
                    "exposure_status": exposure_status,
                    "exposure_date": exposure_date,
                    "response_status": response_status,
                    "response_date": response_date,
                }
            )

        audit_rows.append(
            {
                "campaign_id": campaign_id,
                "campaign_name": campaign.campaign_name,
                "campaign_type": campaign_type,
                "eligible_customers": eligible_count,
                "selected_customers": selected_count,
                "exposed_customers": exposed_count,
                "not_exposed_customers": selected_count - exposed_count,
                "responding_customers": response_count,
                "positive_responses": positive_count,
                "neutral_responses": neutral_count,
                "negative_responses": negative_count,
                "no_response_customers": no_response_count,
                "selection_rate": selected_count / max(eligible_count, 1),
                "exposure_rate": exposed_count / max(selected_count, 1),
                "response_rate_exposed": response_count / max(exposed_count, 1),
                "positive_rate_exposed": positive_count / max(exposed_count, 1),
                "reach_propensity": param["reach_propensity"],
                "design_quality": param["design_quality"],
                "offer_attractiveness": param["offer_attractiveness"],
                "execution_quality": param["execution_quality"],
            }
        )

        print(
            f"[{campaign_idx:02d}/{total_campaigns:02d}] "
            f"{campaign_id:<5} "
            f"eligible={eligible_count:>5,} "
            f"selected={selected_count:>5,} "
            f"exposed={exposed_count:>5,} "
            f"responses={response_count:>5,}"
        )

    campaign_customers = pd.DataFrame(campaign_customer_rows)
    campaign_exposures = pd.DataFrame(exposure_rows)
    audit = pd.DataFrame(audit_rows)

    world_params_rows = [
        {"parameter": "engine_version", "value": ENGINE_VERSION},
        {"parameter": "world_seed", "value": str(world_seed)},
        {"parameter": "campaign_count", "value": str(len(inputs.campaigns))},
        {"parameter": "campaign_customer_universe", "value": str(len(inputs.customers))},
        {"parameter": "contactability_model", "value": "persistent_customer_latent_v1"},
        {"parameter": "delivery_retry_model", "value": "probabilistic_retry_after_failure"},
    ]

    for name, stream in RNG_STREAMS.items():
        world_params_rows.append(
            {
                "parameter": f"rng_stream_{name}",
                "value": str(stream),
            }
        )

    world_params = pd.DataFrame(world_params_rows)

    if not campaign_customers.empty:
        campaign_customers = campaign_customers.sort_values(
            ["campaign_id", "selection_date", "customer_id"]
        ).reset_index(drop=True)

    if not campaign_exposures.empty:
        campaign_exposures = campaign_exposures.sort_values(
            ["exposure_datetime", "exposure_id"]
        ).reset_index(drop=True)

    return campaign_customers, campaign_exposures, world_params, audit


# =============================================================================
# Validation
# =============================================================================

def validate_outputs(
    inputs: Inputs,
    campaign_customers: pd.DataFrame,
    campaign_exposures: pd.DataFrame,
) -> dict[str, bool]:
    checks = {}

    ensure_columns(
        campaign_customers,
        [
            "campaign_id",
            "customer_id",
            "selection_date",
            "exposure_status",
            "exposure_date",
            "response_status",
            "response_date",
        ],
        "generated campaign_customers",
    )

    ensure_columns(
        campaign_exposures,
        [
            "exposure_id",
            "campaign_id",
            "customer_id",
            "exposure_datetime",
            "channel",
        ],
        "generated campaign_exposures",
    )

    cc = campaign_customers.copy()
    ce = campaign_exposures.copy()

    cc["selection_date"] = pd.to_datetime(cc["selection_date"])
    cc["exposure_date"] = pd.to_datetime(cc["exposure_date"])
    cc["response_date"] = pd.to_datetime(cc["response_date"])
    ce["exposure_datetime"] = pd.to_datetime(ce["exposure_datetime"])

    valid_campaign_ids = set(inputs.campaigns["campaign_id"].astype(str))
    valid_customer_ids = set(inputs.customers["customer_id"])

    checks["campaign_customer_pk_unique"] = not cc.duplicated(
        ["campaign_id", "customer_id"]
    ).any()
    checks["exposure_id_unique"] = ce["exposure_id"].is_unique
    checks["campaign_fk_campaign_customers"] = set(
        cc["campaign_id"].astype(str)
    ).issubset(valid_campaign_ids)
    checks["campaign_fk_exposures"] = set(
        ce["campaign_id"].astype(str)
    ).issubset(valid_campaign_ids)
    checks["customer_fk_campaign_customers"] = set(
        cc["customer_id"]
    ).issubset(valid_customer_ids)
    checks["customer_fk_exposures"] = set(
        ce["customer_id"]
    ).issubset(valid_customer_ids)
    checks["valid_exposure_status"] = cc["exposure_status"].isin(
        VALID_EXPOSURE_STATUS
    ).all()

    checks["valid_response_status"] = (
        cc.loc[cc["response_status"].notna(), "response_status"]
        .isin(VALID_RESPONSE_STATUS)
        .all()
    )

    checks["valid_channel"] = ce["channel"].isin(
        VALID_CHANNELS
    ).all()

    campaign_dates = inputs.campaigns[
        ["campaign_id", "start_date", "end_date"]
    ]
    cc2 = cc.merge(campaign_dates, on="campaign_id", how="left")

    checks["selection_inside_campaign"] = (
        (cc2["selection_date"] >= cc2["start_date"])
        & (cc2["selection_date"] <= cc2["end_date"])
    ).all()

    exposed = cc2["exposure_status"] == "EXPOSED"
    not_exposed = ~exposed

    checks["exposure_date_status_consistent"] = (
        cc2.loc[exposed, "exposure_date"].notna().all()
        and cc2.loc[not_exposed, "exposure_date"].isna().all()
    )

    checks["exposure_after_selection"] = (
        cc2.loc[exposed, "exposure_date"]
        >= cc2.loc[exposed, "selection_date"]
    ).all()

    checks["first_exposure_inside_campaign"] = (
        cc2.loc[exposed, "exposure_date"]
        <= cc2.loc[exposed, "end_date"]
    ).all()

    no_response = cc2["response_status"].eq("NO_RESPONSE")
    has_response = cc2["response_status"].isin(
        ["POSITIVE", "NEGATIVE", "NEUTRAL"]
    )

    checks["response_null_for_not_exposed"] = cc2.loc[
        not_exposed,
        "response_status",
    ].isna().all()

    checks["response_date_null_for_no_response"] = cc2.loc[
        no_response,
        "response_date",
    ].isna().all()

    checks["response_date_present_for_observed"] = cc2.loc[
        has_response,
        "response_date",
    ].notna().all()

    checks["response_after_exposure"] = (
        cc2.loc[has_response, "response_date"]
        >= cc2.loc[has_response, "exposure_date"]
    ).all()

    checks["response_before_dataset_end"] = (
        cc2.loc[has_response, "response_date"]
        <= DATASET_END_DATE
    ).all()

    selected_pairs = set(
        zip(cc["campaign_id"].astype(str), cc["customer_id"])
    )
    exposure_pairs = set(
        zip(ce["campaign_id"].astype(str), ce["customer_id"])
    )

    checks["exposure_pair_fk"] = exposure_pairs.issubset(
        selected_pairs
    )

    exposed_pairs = set(
        zip(
            cc.loc[exposed, "campaign_id"].astype(str),
            cc.loc[exposed, "customer_id"],
        )
    )

    checks["exposures_only_for_exposed"] = exposure_pairs.issubset(
        exposed_pairs
    )
    checks["every_exposed_has_event"] = exposed_pairs.issubset(
        exposure_pairs
    )

    authorized_pairs = set(
        zip(
            inputs.channels["campaign_id"].astype(str),
            inputs.channels["channel"].map(normalize_upper),
        )
    )
    used_pairs = set(
        zip(
            ce["campaign_id"].astype(str),
            ce["channel"],
        )
    )

    checks["authorized_campaign_channels"] = used_pairs.issubset(
        authorized_pairs
    )

    if len(ce):
        first_event = (
            ce.assign(
                exposure_date_event=ce["exposure_datetime"].dt.normalize()
            )
            .groupby(
                ["campaign_id", "customer_id"],
                observed=True,
            )["exposure_date_event"]
            .min()
            .reset_index()
        )

        recon = cc.loc[
            exposed,
            [
                "campaign_id",
                "customer_id",
                "exposure_date",
            ],
        ].merge(
            first_event,
            on=["campaign_id", "customer_id"],
            how="left",
        )

        checks["first_exposure_date_reconciles"] = (
            recon["exposure_date"]
            == recon["exposure_date_event"]
        ).all()
    else:
        checks["first_exposure_date_reconciles"] = True

    checks["no_duplicate_exposure_event"] = not ce.duplicated(
        [
            "campaign_id",
            "customer_id",
            "channel",
            "exposure_datetime",
        ]
    ).any()

    return checks


# =============================================================================
# Reporting and save
# =============================================================================

def print_summary(
    audit: pd.DataFrame,
    exposures: pd.DataFrame,
) -> None:
    print()
    print("=" * 104)
    print("CAMPAIGN PRODUCTION SUMMARY")
    print("=" * 104)

    summary = audit[
        [
            "campaign_id",
            "campaign_name",
            "eligible_customers",
            "selected_customers",
            "exposed_customers",
            "not_exposed_customers",
            "responding_customers",
            "positive_responses",
            "neutral_responses",
            "negative_responses",
            "selection_rate",
            "exposure_rate",
            "response_rate_exposed",
        ]
    ].copy()

    for col in [
        "selection_rate",
        "exposure_rate",
        "response_rate_exposed",
    ]:
        summary[col] = summary[col].map(
            lambda x: f"{100*x:5.1f}%"
        )

    print(summary.to_string(index=False))

    selected = int(audit["selected_customers"].sum())
    exposed = int(audit["exposed_customers"].sum())
    responses = int(audit["responding_customers"].sum())

    print()
    print(f"Selected relationships:              {selected:,}")
    print(f"Successfully exposed relationships:  {exposed:,}")
    print(f"Exposure events:                     {len(exposures):,}")
    print(f"Observed responses:                  {responses:,}")

    if selected:
        print(
            f"Overall exposure rate:               "
            f"{100*exposed/selected:6.2f}%"
        )
    if exposed:
        print(
            f"Overall response rate / exposed:     "
            f"{100*responses/exposed:6.2f}%"
        )
        print(
            f"Exposure events / exposed customer:  "
            f"{len(exposures)/exposed:6.3f}"
        )


def print_validation(checks: dict[str, bool]) -> None:
    print()
    print("=" * 104)
    print("STRUCTURAL VALIDATION")
    print("=" * 104)

    for name, passed in checks.items():
        print(
            f"  {name:<48} "
            f"{'PASS' if passed else 'FAIL'}"
        )

    failed = [
        name
        for name, passed in checks.items()
        if not passed
    ]

    if failed:
        raise RuntimeError(
            "Campaign structural validation failed: "
            + ", ".join(failed)
        )

    print()
    print("STRUCTURAL VALIDATION: PASS")


def save_outputs(
    campaign_customers: pd.DataFrame,
    campaign_exposures: pd.DataFrame,
    world_params: pd.DataFrame,
    audit: pd.DataFrame,
) -> None:
    DATA_GENERATED.mkdir(parents=True, exist_ok=True)
    DATA_INTERIM.mkdir(parents=True, exist_ok=True)

    cc = campaign_customers.copy()
    ce = campaign_exposures.copy()

    for col in [
        "selection_date",
        "exposure_date",
        "response_date",
    ]:
        original_na = cc[col].isna()
        cc[col] = pd.to_datetime(
            cc[col]
        ).dt.strftime("%Y-%m-%d")
        cc.loc[original_na, col] = ""

    ce["exposure_datetime"] = pd.to_datetime(
        ce["exposure_datetime"]
    ).dt.strftime("%Y-%m-%d %H:%M:%S")

    cc.to_csv(OUT_CAMPAIGN_CUSTOMERS, index=False)
    ce.to_csv(OUT_CAMPAIGN_EXPOSURES, index=False)
    world_params.to_csv(OUT_WORLD_PARAMETERS, index=False)
    audit.to_csv(OUT_AUDIT, index=False)

    print()
    print("Saved:")
    print(f"  {OUT_CAMPAIGN_CUSTOMERS}")
    print(f"  {OUT_CAMPAIGN_EXPOSURES}")
    print(f"  {OUT_WORLD_PARAMETERS}")
    print(f"  {OUT_AUDIT}")


# =============================================================================
# CLI
# =============================================================================

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--seed",
        type=int,
        default=DEFAULT_WORLD_SEED,
    )
    parser.add_argument(
        "--customer-limit",
        type=int,
        default=DEFAULT_CUSTOMER_LIMIT,
        help=(
            "Maximum customers processed by the campaign engine. "
            "Default: 10000. Use 0 to process the full customers.csv universe."
        ),
    )
    parser.add_argument(
        "--no-write",
        action="store_true",
    )
    args = parser.parse_args()

    print("Loading campaign and banking universe...")
    inputs_full = load_inputs()

    source_customer_count = len(inputs_full.customers)

    inputs = select_campaign_universe(
        inputs_full,
        args.seed,
        args.customer_limit,
    )

    print("=" * 104)
    print(f"BTYT CAMPAIGN BEHAVIORAL ENGINE — V{ENGINE_VERSION}")
    print("=" * 104)
    print(f"World seed:                  {args.seed}")
    print(f"Campaigns:                   {len(inputs.campaigns):,}")
    print(f"Customers in source file:    {source_customer_count:,}")
    print(f"Customers simulated:         {len(inputs.customers):,}")
    print()

    campaign_customers, campaign_exposures, world_params, audit = (
        generate_campaign_behavior(
            inputs,
            args.seed,
        )
    )

    print_summary(
        audit,
        campaign_exposures,
    )

    checks = validate_outputs(
        inputs,
        campaign_customers,
        campaign_exposures,
    )

    print_validation(checks)

    if not args.no_write:
        save_outputs(
            campaign_customers,
            campaign_exposures,
            world_params,
            audit,
        )
    else:
        print()
        print("No-write mode: outputs were not persisted.")

    print()
    print("=" * 104)
    print(
        f"BTYT CAMPAIGN BEHAVIORAL ENGINE "
        f"V{ENGINE_VERSION}: PASS"
    )
    print("=" * 104)
    print("No frozen observable banking dataset was modified.")
    print("No downstream banking conversion was manufactured.")


if __name__ == "__main__":
    main()
