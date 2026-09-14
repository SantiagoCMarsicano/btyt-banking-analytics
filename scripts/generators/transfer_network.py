"""BTYT Transactions V6 — persistent transfer-network module.

This module is a future-facing rework of BTYT transfer mechanics. It is designed
for integration with ``generate_transactions.py`` after the accepted V5 world is
frozen. It does not mutate or regenerate any existing world by itself.

The main design change is persistent counterparty relationships. Instead of
selecting a plausible counterparty independently for every transfer, customers
receive a deterministic relationship network and future transfer intents can
select from that network.

Design principles
-----------------
- deterministic from BTYT semantic RNG streams;
- bounded relationship generation suitable for 100k+ customers;
- explicit relationship lifecycle;
- separate INTERNAL, DOMESTIC_EXTERNAL, and INTERNATIONAL regimes;
- support for bank and electronic-money institutions;
- relationship-aware amount/channel/timing signals;
- exact internal-pair semantics remain the responsibility of chronological
  ledger replay;
- no dependency on the current production-world output files.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Callable, Iterable, Mapping, MutableMapping, Sequence
import hashlib
import math

import numpy as np
import pandas as pd


TRANSFER_SCOPES = {"INTERNAL", "DOMESTIC_EXTERNAL", "INTERNATIONAL"}
RECURRENCE_PROFILES = {"RECURRING", "OCCASIONAL", "SPORADIC"}

RELATIONSHIP_COLUMNS = [
    "relationship_id",
    "customer_id",
    "source_account_id",
    "counterparty_scope",
    "counterparty_type",
    "counterparty_customer_id",
    "counterparty_account_id",
    "counterparty_institution_id",
    "relationship_type",
    "relationship_strength",
    "start_date",
    "end_date",
    "recurrence_profile",
    "preferred_channel",
    "currency",
]


INDIVIDUAL_INTERNAL_TYPES = (
    "OWN_ACCOUNT",
    "HOUSEHOLD_FAMILY",
    "PEER_TO_PEER",
    "RECURRING_PERSONAL",
)

BUSINESS_INTERNAL_TYPES = (
    "SUPPLIER_CUSTOMER_NETWORK",
    "PAYROLL_OR_STAFF",
    "BUSINESS_PARTNER",
    "TREASURY_INTERNAL",
)

INDIVIDUAL_EXTERNAL_TYPES = (
    "EXTERNAL_BANK_SELF_TRANSFER",
    "SAVINGS_INVESTMENT",
    "WALLET_FUNDING",
)

BUSINESS_EXTERNAL_TYPES = (
    "TREASURY_EXTERNAL",
    "SUPPLIER_SETTLEMENT",
    "LIQUIDITY_MANAGEMENT",
    "FINANCING_RELATIONSHIP",
)

INTERNATIONAL_TYPES = (
    "REMITTANCE",
    "INTERNATIONAL_SUPPLIER",
    "INTERNATIONAL_CUSTOMER",
    "FOREIGN_TREASURY",
)


@dataclass(frozen=True)
class TransferResolution:
    """Resolved persistent relationship for one transfer intent."""

    relationship_id: str | None
    transfer_scope: str | None
    counterparty_type: str | None
    counterparty_customer_id: str | None
    counterparty_account_id: str | None
    counterparty_institution_id: str | None
    relationship_type: str | None
    preferred_channel: str | None
    relationship_strength: float | None


@dataclass(frozen=True)
class TransferNetworkAudit:
    """Compact audit result for the persistent relationship table."""

    passed: bool
    metrics: Mapping[str, int]


# -----------------------------------------------------------------------------
# Generic deterministic helpers
# -----------------------------------------------------------------------------


def stable_relationship_id(*parts: object) -> str:
    """Return a stable synthetic relationship identifier.

    The identifier is independent of Python's process-randomized ``hash()`` and
    therefore remains stable across machines and interpreter sessions.
    """

    payload = "|".join(str(part) for part in parts)
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:20].upper()
    return f"REL-{digest}"


def sigmoid(x: float) -> float:
    return float(1.0 / (1.0 + math.exp(-max(-30.0, min(30.0, float(x))))))


def _normalize_weights(weights: Sequence[float]) -> np.ndarray:
    values = np.maximum(np.asarray(weights, dtype=float), 0.0)
    if not np.isfinite(values).all() or values.sum() <= 0:
        values = np.ones(len(values), dtype=float)
    return values / values.sum()


def _choose(rng: np.random.Generator, labels: Sequence[str], weights: Sequence[float]) -> str:
    return str(rng.choice(np.asarray(labels, dtype=object), p=_normalize_weights(weights)))


def _month_start(value: object, fallback_year: int) -> pd.Timestamp:
    if value is not None and not pd.isna(value):
        try:
            return pd.Period(value, freq="M").start_time.normalize()
        except Exception:
            pass
    return pd.Timestamp(f"{int(fallback_year):04d}-01-01")


def _month_end(value: object, fallback_year: int) -> pd.Timestamp:
    if value is not None and not pd.isna(value):
        try:
            return pd.Period(value, freq="M").end_time.normalize()
        except Exception:
            pass
    return pd.Timestamp(f"{int(fallback_year):04d}-12-31")


def _safe_float(value: object, default: float) -> float:
    numeric = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    if pd.isna(numeric) or not np.isfinite(float(numeric)):
        return float(default)
    return float(numeric)


# -----------------------------------------------------------------------------
# Metadata preparation
# -----------------------------------------------------------------------------


def build_account_network_context(
    accounts: pd.DataFrame,
    roles: pd.DataFrame,
    customers: pd.DataFrame,
    currency_map: Mapping[str, str],
    fixed_products: Iterable[str] = ("P007", "P008"),
) -> dict:
    """Build compact account arrays used by persistent relationship generation."""

    required_accounts = {
        "account_id", "customer_id", "product_id", "opening_year", "account_status",
    }
    missing = required_accounts - set(accounts.columns)
    if missing:
        raise ValueError(f"accounts: missing columns {sorted(missing)}")
    if not {"account_id", "customer_id", "account_role"}.issubset(roles.columns):
        raise ValueError("roles must contain account_id, customer_id, and account_role")
    if not {"customer_id", "customer_type"}.issubset(customers.columns):
        raise ValueError("customers must contain customer_id and customer_type")

    role_map = roles.assign(account_id=roles["account_id"].astype(str)).set_index("account_id")["account_role"].to_dict()
    customer_type = (
        customers.assign(customer_id=customers["customer_id"].astype(str))
        .set_index("customer_id")["customer_type"]
        .astype(str)
        .str.upper()
        .to_dict()
    )

    frame = accounts.copy()
    frame["account_id"] = frame["account_id"].astype(str)
    frame["customer_id"] = frame["customer_id"].astype(str)
    frame["product_id"] = frame["product_id"].astype(str)
    frame["currency"] = frame["product_id"].map(currency_map)
    if frame["currency"].isna().any():
        bad = sorted(frame.loc[frame["currency"].isna(), "product_id"].unique())
        raise ValueError(f"No currency mapping for products {bad}")

    frame["account_role"] = frame["account_id"].map(role_map).fillna("SECONDARY")
    frame["customer_type"] = frame["customer_id"].map(customer_type).fillna("INDIVIDUAL")
    frame["eligible_transfer_account"] = ~frame["product_id"].isin(set(fixed_products))

    if "first_obs_month" in frame.columns:
        frame["start_date"] = frame.apply(
            lambda row: _month_start(row["first_obs_month"], int(row["opening_year"])), axis=1
        )
    else:
        frame["start_date"] = frame["opening_year"].map(lambda year: pd.Timestamp(f"{int(year):04d}-01-01"))

    if "last_obs_month" in frame.columns:
        frame["end_date"] = frame.apply(
            lambda row: _month_end(
                row["last_obs_month"],
                2099 if pd.isna(row.get("closing_year", pd.NA)) else int(row.get("closing_year")),
            ),
            axis=1,

        )
    else:
        closing = pd.to_numeric(frame.get("closing_year"), errors="coerce")
        frame["end_date"] = [
            pd.Timestamp(f"{int(year):04d}-12-31") if pd.notna(year) else pd.Timestamp.max.normalize()
            for year in closing
        ]

    role_weight = {
        "BUSINESS_OPERATING": 3.2,
        "PRIMARY_TRANSACTIONAL": 2.8,
        "PAYROLL": 2.5,
        "SECONDARY": 1.0,
        "SAVINGS": 0.8,
        "USD_RESERVE": 0.8,
        "FIXED_TERM": 0.0,
    }
    frame["network_weight"] = frame["account_role"].map(role_weight).fillna(0.8).astype(float)

    frame = frame.sort_values(["customer_id", "account_id"], kind="mergesort").reset_index(drop=True)
    by_customer = {
        customer_id: group.index.to_numpy(dtype=np.int64)
        for customer_id, group in frame.groupby("customer_id", sort=False)
    }
    by_currency = {
        currency: group.index.to_numpy(dtype=np.int64)
        for currency, group in frame.loc[frame["eligible_transfer_account"]].groupby("currency", sort=False)
    }

    return {
        "frame": frame,
        "by_customer": by_customer,
        "by_currency": by_currency,
    }


def _preferred_source_account(
    rng: np.random.Generator,
    context: Mapping[str, object],
    customer_id: str,
    currency: str | None = None,
) -> str | None:
    frame: pd.DataFrame = context["frame"]
    indexes = context["by_customer"].get(str(customer_id), np.array([], dtype=np.int64))
    if len(indexes) == 0:
        return None
    subset = frame.loc[indexes]
    subset = subset.loc[subset["eligible_transfer_account"]]
    if currency is not None:
        same_currency = subset.loc[subset["currency"].eq(currency)]
        if not same_currency.empty:
            subset = same_currency
    if subset.empty:
        return None
    weights = subset["network_weight"].to_numpy(dtype=float)
    return str(rng.choice(subset["account_id"].to_numpy(dtype=object), p=_normalize_weights(weights)))


def _pick_internal_account(
    rng: np.random.Generator,
    context: Mapping[str, object],
    source_customer_id: str,
    source_account_id: str,
    currency: str,
    allow_same_customer: bool,
) -> tuple[str, str] | tuple[None, None]:
    frame: pd.DataFrame = context["frame"]
    indexes = context["by_currency"].get(str(currency), np.array([], dtype=np.int64))
    if len(indexes) == 0:
        return None, None

    subset = frame.loc[indexes]
    valid = subset["account_id"].ne(str(source_account_id))
    if not allow_same_customer:
        valid &= subset["customer_id"].ne(str(source_customer_id))
    subset = subset.loc[valid]
    if subset.empty:
        return None, None

    weights = subset["network_weight"].to_numpy(dtype=float)
    pos = int(rng.choice(np.arange(len(subset)), p=_normalize_weights(weights)))
    row = subset.iloc[pos]
    return str(row["customer_id"]), str(row["account_id"])


# -----------------------------------------------------------------------------
# Relationship generation
# -----------------------------------------------------------------------------


def _relationship_strength(
    rng: np.random.Generator,
    customer_type: str,
    relationship_type: str,
    recurrence_profile: str,
) -> float:
    base = 1.0
    if customer_type == "BUSINESS":
        base *= 1.18
    if relationship_type in {"OWN_ACCOUNT", "TREASURY_INTERNAL", "TREASURY_EXTERNAL", "PAYROLL_OR_STAFF"}:
        base *= 1.35
    if recurrence_profile == "RECURRING":
        base *= 1.30
    elif recurrence_profile == "SPORADIC":
        base *= 0.62
    return float(np.clip(base * rng.lognormal(0.0, 0.30), 0.08, 5.0))


def _recurrence_profile(rng: np.random.Generator, relationship_type: str, customer_type: str) -> str:
    recurring_types = {
        "OWN_ACCOUNT", "HOUSEHOLD_FAMILY", "PAYROLL_OR_STAFF", "TREASURY_INTERNAL",
        "TREASURY_EXTERNAL", "EXTERNAL_BANK_SELF_TRANSFER", "SUPPLIER_SETTLEMENT",
        "LIQUIDITY_MANAGEMENT", "FINANCING_RELATIONSHIP",
    }
    if relationship_type in recurring_types:
        weights = [0.62, 0.30, 0.08] if customer_type == "BUSINESS" else [0.54, 0.36, 0.10]
    else:
        weights = [0.20, 0.52, 0.28]
    return _choose(rng, ["RECURRING", "OCCASIONAL", "SPORADIC"], weights)


def _preferred_channel(
    rng: np.random.Generator,
    customer_type: str,
    relationship_type: str,
    digital_preference: float,
) -> str:
    digital = float(np.clip(digital_preference, 0.0, 1.0))
    if relationship_type in {"OWN_ACCOUNT", "HOUSEHOLD_FAMILY", "PEER_TO_PEER", "WALLET_FUNDING"}:
        labels = ["MOBILE", "WEB", "AUTOMATIC"]
        weights = [1.5 + 2.2 * digital, 0.8 + 1.0 * digital, 0.25]
    elif customer_type == "BUSINESS":
        labels = ["WEB", "MOBILE", "AUTOMATIC", "BRANCH"]
        weights = [2.3, 0.8 + digital, 1.0, 0.35]
    else:
        labels = ["MOBILE", "WEB", "AUTOMATIC", "BRANCH"]
        weights = [1.4 + 2.0 * digital, 0.8 + digital, 0.55, 0.35 + 0.7 * (1.0 - digital)]
    return _choose(rng, labels, weights)


def _relationship_lifecycle(
    rng: np.random.Generator,
    base_start: pd.Timestamp,
    base_end: pd.Timestamp,
    obs_start: pd.Timestamp,
    obs_end: pd.Timestamp,
    recurrence_profile: str,
) -> tuple[pd.Timestamp, pd.Timestamp | pd.NaT]:
    lower = max(pd.Timestamp(base_start).normalize(), pd.Timestamp(obs_start).normalize())
    upper = min(pd.Timestamp(base_end).normalize(), pd.Timestamp(obs_end).normalize())
    if lower > upper:
        lower = upper

    available_days = max(0, (upper - lower).days)
    start_offset = int(rng.integers(0, min(available_days, 365) + 1)) if available_days else 0
    start = lower + pd.Timedelta(days=start_offset)

    termination_prob = {
        "RECURRING": 0.12,
        "OCCASIONAL": 0.24,
        "SPORADIC": 0.32,
    }[recurrence_profile]
    if available_days > 120 and rng.random() < termination_prob:
        remaining = max(30, (upper - start).days)
        duration = int(rng.integers(30, remaining + 1))
        return start, min(start + pd.Timedelta(days=duration), upper)
    return start, pd.NaT


def _domestic_external_candidates(institution_context: Mapping[str, object]) -> tuple[str, ...]:
    bank_ids = tuple(str(x) for x in institution_context.get("domestic_bank_institution_ids", ()))
    iede_ids = tuple(str(x) for x in institution_context.get("iede_ids", ()))
    return bank_ids + iede_ids


def _choose_persistent_institution(
    rng: np.random.Generator,
    institution_context: Mapping[str, object],
    scope: str,
    digital_preference: float,
    customer_type: str,
) -> str | None:
    if scope == "INTERNATIONAL":
        candidates = tuple(str(x) for x in institution_context.get("foreign_bank_institution_ids", ()))
    else:
        candidates = _domestic_external_candidates(institution_context)
    if not candidates:
        return None

    meta = institution_context.get("institution_meta", {})
    weights = []
    for institution_id in candidates:
        row = meta.get(institution_id, {})
        institution_type = str(row.get("institution_type", "BANK")).upper()
        weight = 1.0
        if institution_type == "ELECTRONIC_MONEY_ISSUER":
            weight *= 0.55 + 1.30 * float(np.clip(digital_preference, 0.0, 1.0))
            if customer_type == "BUSINESS":
                weight *= 0.45
        elif customer_type == "BUSINESS":
            weight *= 1.20
        weights.append(weight)
    return str(rng.choice(np.asarray(candidates, dtype=object), p=_normalize_weights(weights)))


def build_transfer_relationships(
    customers: pd.DataFrame,
    accounts: pd.DataFrame,
    roles: pd.DataFrame,
    institution_context: Mapping[str, object],
    obs_start: object,
    obs_end: object,
    currency_map: Mapping[str, str],
    rng_for: Callable[..., np.random.Generator],
    customer_traits: pd.DataFrame | None = None,
    fixed_products: Iterable[str] = ("P007", "P008"),
) -> pd.DataFrame:
    """Generate a bounded persistent counterparty network.

    The function is deterministic when ``rng_for`` is deterministic. Relationship
    counts are intentionally bounded so the network remains practical at BTYT
    scale. It does not generate transactions and does not touch ledger state.
    """

    obs_start_ts = pd.Timestamp(obs_start).normalize()
    obs_end_ts = pd.Timestamp(obs_end).normalize()
    context = build_account_network_context(accounts, roles, customers, currency_map, fixed_products)
    account_frame: pd.DataFrame = context["frame"]

    traits_lookup: Mapping[str, Mapping[str, object]] = {}
    if customer_traits is not None and not customer_traits.empty:
        trait_frame = customer_traits.copy()
        trait_frame["customer_id"] = trait_frame["customer_id"].astype(str)
        traits_lookup = trait_frame.set_index("customer_id").to_dict(orient="index")

    customer_frame = customers.copy()
    customer_frame["customer_id"] = customer_frame["customer_id"].astype(str)
    customer_frame["customer_type"] = customer_frame["customer_type"].astype(str).str.upper()
    customer_frame = customer_frame.sort_values("customer_id", kind="mergesort")

    rows: list[dict] = []
    seen: set[tuple] = set()

    def append_relationship(
        *,
        customer_id: str,
        source_account_id: str,
        scope: str,
        counterparty_type: str,
        relationship_type: str,
        currency: str,
        counterparty_customer_id: str | None = None,
        counterparty_account_id: str | None = None,
        counterparty_institution_id: str | None = None,
        source_start: pd.Timestamp,
        source_end: pd.Timestamp,
        digital_preference: float,
        customer_type: str,
        sequence: int,
    ) -> None:
        # Every INTERNAL relationship belongs to BTYT itself. Enforce this
        # invariant centrally so no relationship subtype can omit it.
        if scope == "INTERNAL":
            counterparty_institution_id = str(institution_context["btyt_institution_id"])

        dedupe_key = (
            customer_id, source_account_id, scope, relationship_type,
            counterparty_customer_id, counterparty_account_id, counterparty_institution_id,
        )
        if dedupe_key in seen:
            return
        seen.add(dedupe_key)

        rrng = rng_for(
            "transfer-network", customer_id, source_account_id, scope,
            relationship_type, sequence,
            counterparty_customer_id or "",
            counterparty_account_id or "",
            counterparty_institution_id or "",
        )
        recurrence = _recurrence_profile(rrng, relationship_type, customer_type)
        start_date, end_date = _relationship_lifecycle(
            rrng, source_start, source_end, obs_start_ts, obs_end_ts, recurrence
        )
        strength = _relationship_strength(rrng, customer_type, relationship_type, recurrence)
        preferred_channel = _preferred_channel(rrng, customer_type, relationship_type, digital_preference)
        relationship_id = stable_relationship_id(
            customer_id, source_account_id, scope, relationship_type,
            counterparty_customer_id or "", counterparty_account_id or "",
            counterparty_institution_id or "", sequence,
        )
        rows.append({
            "relationship_id": relationship_id,
            "customer_id": customer_id,
            "source_account_id": source_account_id,
            "counterparty_scope": scope,
            "counterparty_type": counterparty_type,
            "counterparty_customer_id": counterparty_customer_id,
            "counterparty_account_id": counterparty_account_id,
            "counterparty_institution_id": counterparty_institution_id,
            "relationship_type": relationship_type,
            "relationship_strength": round(strength, 6),
            "start_date": start_date,
            "end_date": end_date,
            "recurrence_profile": recurrence,
            "preferred_channel": preferred_channel,
            "currency": currency,
        })

    for customer in customer_frame.itertuples(index=False):
        customer_id = str(customer.customer_id)
        customer_type = str(customer.customer_type).upper()
        crng = rng_for("transfer-network-customer", customer_id)
        trait = traits_lookup.get(customer_id, {})
        digital_preference = float(np.clip(_safe_float(trait.get("digital_preference"), 0.55), 0.0, 1.0))
        external_affinity = float(np.clip(_safe_float(trait.get("external_bank_affinity"), 0.50), 0.0, 1.0))

        customer_indexes = context["by_customer"].get(customer_id, np.array([], dtype=np.int64))
        if len(customer_indexes) == 0:
            continue
        customer_accounts = account_frame.loc[customer_indexes]
        customer_accounts = customer_accounts.loc[customer_accounts["eligible_transfer_account"]]
        if customer_accounts.empty:
            continue

        currencies = tuple(sorted(customer_accounts["currency"].dropna().astype(str).unique()))
        if not currencies:
            continue

        # Explicit own-account relationships create a semantic path for treasury
        # and savings movements between accounts belonging to the same customer.
        for currency in currencies:
            same_currency = customer_accounts.loc[customer_accounts["currency"].eq(currency)]
            if len(same_currency) >= 2:
                source = _preferred_source_account(crng, context, customer_id, currency)
                if source is not None:
                    target_rows = same_currency.loc[same_currency["account_id"].ne(source)]
                    target = str(crng.choice(target_rows["account_id"].to_numpy(dtype=object)))
                    source_row = account_frame.loc[account_frame["account_id"].eq(source)].iloc[0]
                    append_relationship(
                        customer_id=customer_id,
                        source_account_id=source,
                        scope="INTERNAL",
                        counterparty_type="BTYT_CUSTOMER",
                        relationship_type="TREASURY_INTERNAL" if customer_type == "BUSINESS" else "OWN_ACCOUNT",
                        currency=currency,
                        counterparty_customer_id=customer_id,
                        counterparty_account_id=target,
                        source_start=source_row["start_date"],
                        source_end=source_row["end_date"],
                        digital_preference=digital_preference,
                        customer_type=customer_type,
                        sequence=0,
                    )

        # Persistent internal relationships with other customers.
        internal_count = int(crng.integers(3, 8)) if customer_type == "BUSINESS" else int(crng.integers(1, 5))
        internal_types = BUSINESS_INTERNAL_TYPES if customer_type == "BUSINESS" else INDIVIDUAL_INTERNAL_TYPES[1:]
        for sequence in range(internal_count):
            currency = str(crng.choice(np.asarray(currencies, dtype=object)))
            source = _preferred_source_account(crng, context, customer_id, currency)
            if source is None:
                continue
            counterparty_customer, counterparty_account = _pick_internal_account(
                crng, context, customer_id, source, currency, allow_same_customer=False
            )
            if counterparty_account is None:
                continue
            relationship_type = str(crng.choice(np.asarray(internal_types, dtype=object)))
            source_row = account_frame.loc[account_frame["account_id"].eq(source)].iloc[0]
            append_relationship(
                customer_id=customer_id,
                source_account_id=source,
                scope="INTERNAL",
                counterparty_type="BTYT_CUSTOMER",
                relationship_type=relationship_type,
                currency=currency,
                counterparty_customer_id=counterparty_customer,
                counterparty_account_id=counterparty_account,
                counterparty_institution_id=institution_context["btyt_institution_id"],
                source_start=source_row["start_date"],
                source_end=source_row["end_date"],
                digital_preference=digital_preference,
                customer_type=customer_type,
                sequence=sequence + 1,
            )

        # Persistent domestic-external relationships.
        domestic_base = 1 if customer_type == "INDIVIDUAL" else 2
        domestic_extra = int(crng.random() < (0.25 + 0.45 * external_affinity))
        domestic_count = domestic_base + domestic_extra
        external_types = BUSINESS_EXTERNAL_TYPES if customer_type == "BUSINESS" else INDIVIDUAL_EXTERNAL_TYPES
        for sequence in range(domestic_count):
            currency = str(crng.choice(np.asarray(currencies, dtype=object)))
            source = _preferred_source_account(crng, context, customer_id, currency)
            institution_id = _choose_persistent_institution(
                crng, institution_context, "DOMESTIC_EXTERNAL", digital_preference, customer_type
            )
            if source is None or institution_id is None:
                continue
            relationship_type = str(crng.choice(np.asarray(external_types, dtype=object)))
            source_row = account_frame.loc[account_frame["account_id"].eq(source)].iloc[0]
            append_relationship(
                customer_id=customer_id,
                source_account_id=source,
                scope="DOMESTIC_EXTERNAL",
                counterparty_type="FINANCIAL_INSTITUTION",
                relationship_type=relationship_type,
                currency=currency,
                counterparty_institution_id=institution_id,
                source_start=source_row["start_date"],
                source_end=source_row["end_date"],
                digital_preference=digital_preference,
                customer_type=customer_type,
                sequence=100 + sequence,
            )

        # International relationships are deliberately sparser and more likely
        # for businesses, USD holders, and customers with external affinity.
        has_usd = "USD" in currencies
        intl_logit = -2.25 + (1.20 if customer_type == "BUSINESS" else 0.0) + (0.85 if has_usd else 0.0)
        intl_logit += 1.20 * (external_affinity - 0.5)
        if crng.random() < sigmoid(intl_logit):
            max_intl = 3 if customer_type == "BUSINESS" else 2
            international_count = int(crng.integers(1, max_intl + 1))
            for sequence in range(international_count):
                currency = "USD" if has_usd and crng.random() < 0.80 else str(crng.choice(np.asarray(currencies, dtype=object)))
                source = _preferred_source_account(crng, context, customer_id, currency)
                institution_id = _choose_persistent_institution(
                    crng, institution_context, "INTERNATIONAL", digital_preference, customer_type
                )
                if source is None or institution_id is None:
                    continue
                if customer_type == "BUSINESS":
                    relationship_type = str(crng.choice(np.asarray(INTERNATIONAL_TYPES[1:], dtype=object)))
                else:
                    relationship_type = "REMITTANCE"
                source_row = account_frame.loc[account_frame["account_id"].eq(source)].iloc[0]
                append_relationship(
                    customer_id=customer_id,
                    source_account_id=source,
                    scope="INTERNATIONAL",
                    counterparty_type="FINANCIAL_INSTITUTION",
                    relationship_type=relationship_type,
                    currency=currency,
                    counterparty_institution_id=institution_id,
                    source_start=source_row["start_date"],
                    source_end=source_row["end_date"],
                    digital_preference=digital_preference,
                    customer_type=customer_type,
                    sequence=200 + sequence,
                )

    if not rows:
        return pd.DataFrame(columns=RELATIONSHIP_COLUMNS)

    relationships = pd.DataFrame(rows, columns=RELATIONSHIP_COLUMNS)
    relationships["start_date"] = pd.to_datetime(relationships["start_date"])
    relationships["end_date"] = pd.to_datetime(relationships["end_date"])
    relationships = relationships.sort_values(
        ["customer_id", "source_account_id", "counterparty_scope", "relationship_id"],
        kind="mergesort",
    ).reset_index(drop=True)
    return relationships


# -----------------------------------------------------------------------------
# Relationship-aware transfer selection
# -----------------------------------------------------------------------------


def build_relationship_index(relationships: pd.DataFrame) -> dict:
    """Build account-level indexes for hot-path transfer resolution."""

    if relationships.empty:
        return {"by_source_account": {}, "by_customer": {}}
    missing = set(RELATIONSHIP_COLUMNS) - set(relationships.columns)
    if missing:
        raise ValueError(f"relationships: missing columns {sorted(missing)}")

    frame = relationships.copy()
    frame["customer_id"] = frame["customer_id"].astype(str)
    frame["source_account_id"] = frame["source_account_id"].astype(str)
    frame["start_date"] = pd.to_datetime(frame["start_date"])
    frame["end_date"] = pd.to_datetime(frame["end_date"])

    return {
        "by_source_account": {
            key: group.to_dict("records")
            for key, group in frame.groupby("source_account_id", sort=False)
        },
        "by_customer": {
            key: group.to_dict("records")
            for key, group in frame.groupby("customer_id", sort=False)
        },
    }


def relationship_is_active(relationship: Mapping[str, object], transaction_datetime: object) -> bool:
    dt = pd.Timestamp(transaction_datetime).normalize()
    start = pd.Timestamp(relationship["start_date"]).normalize()
    end = relationship.get("end_date")
    return bool(dt >= start and (pd.isna(end) or dt <= pd.Timestamp(end).normalize()))


def relationship_event_weight(
    relationship: Mapping[str, object],
    direction: str,
    amount_uyu: float,
    customer_type: str,
) -> float:
    """Return a soft selection weight for one active relationship."""

    strength = max(_safe_float(relationship.get("relationship_strength"), 1.0), 0.01)
    recurrence = str(relationship.get("recurrence_profile", "OCCASIONAL")).upper()
    relationship_type = str(relationship.get("relationship_type", ""))
    scope = str(relationship.get("counterparty_scope", ""))

    weight = strength
    weight *= {"RECURRING": 1.35, "OCCASIONAL": 1.0, "SPORADIC": 0.55}.get(recurrence, 1.0)

    large = sigmoid((math.log1p(max(float(amount_uyu), 0.0)) - math.log(150_000.0)) / 0.90)
    if scope == "INTERNATIONAL":
        weight *= 0.55 + 1.45 * large
    if customer_type == "BUSINESS" and relationship_type in {
        "SUPPLIER_SETTLEMENT", "TREASURY_EXTERNAL", "LIQUIDITY_MANAGEMENT",
        "INTERNATIONAL_SUPPLIER", "INTERNATIONAL_CUSTOMER", "FOREIGN_TREASURY",
    }:
        weight *= 1.25
    if direction == "CREDIT" and relationship_type in {"SUPPLIER_SETTLEMENT", "PAYROLL_OR_STAFF"}:
        weight *= 0.70
    return max(float(weight), 1e-8)


def resolve_persistent_transfer(
    *,
    event: Mapping[str, object],
    account: Mapping[str, object],
    customer: Mapping[str, object],
    period: object,
    sequence: object,
    relationship_index: Mapping[str, object],
    rng_for: Callable[..., np.random.Generator],
    fx: Mapping[int, float],
    currency_map: Mapping[str, str],
) -> TransferResolution:
    """Resolve a transfer through the customer's persistent network.

    This function is intentionally side-effect free. Internal ledger pairing is
    still performed later by chronological replay.
    """

    transaction_type = str(event.get("transaction_type", ""))
    if transaction_type not in {"TRANSFER_IN", "TRANSFER_OUT"}:
        return TransferResolution(None, None, None, None, None, None, None, None, None)

    account_id = str(account["account_id"])
    customer_id = str(customer["customer_id"])
    customer_type = str(customer.get("customer_type", "INDIVIDUAL")).upper()
    transaction_datetime = pd.Timestamp(event["transaction_datetime"])
    currency = str(currency_map[str(account["product_id"])])
    direction = "CREDIT" if transaction_type == "TRANSFER_IN" else "DEBIT"
    amount = float(event.get("amount", 0.0))
    year = transaction_datetime.year
    amount_uyu = amount * (float(fx[year]) if currency == "USD" else 1.0)

    candidates = list(relationship_index.get("by_source_account", {}).get(account_id, ()))
    if not candidates:
        candidates = list(relationship_index.get("by_customer", {}).get(customer_id, ()))

    active = [
        row for row in candidates
        if str(row.get("currency")) == currency
        and relationship_is_active(row, transaction_datetime)
    ]
    if not active:
        return TransferResolution(None, None, None, None, None, None, None, None, None)

    weights = [relationship_event_weight(row, direction, amount_uyu, customer_type) for row in active]
    rng = rng_for(
        "transfer-relationship-event", account_id, str(period), sequence,
        event.get("source"), event.get("amount"), transaction_type,
    )
    chosen = active[int(rng.choice(np.arange(len(active)), p=_normalize_weights(weights)))]

    return TransferResolution(
        relationship_id=str(chosen["relationship_id"]),
        transfer_scope=str(chosen["counterparty_scope"]),
        counterparty_type=str(chosen["counterparty_type"]),
        counterparty_customer_id=(
            None if pd.isna(chosen.get("counterparty_customer_id")) else str(chosen.get("counterparty_customer_id"))
        ),
        counterparty_account_id=(
            None if pd.isna(chosen.get("counterparty_account_id")) else str(chosen.get("counterparty_account_id"))
        ),
        counterparty_institution_id=(
            None if pd.isna(chosen.get("counterparty_institution_id")) else str(chosen.get("counterparty_institution_id"))
        ),
        relationship_type=str(chosen["relationship_type"]),
        preferred_channel=str(chosen["preferred_channel"]),
        relationship_strength=float(chosen["relationship_strength"]),
    )


# -----------------------------------------------------------------------------
# Relationship-aware behavioral helpers
# -----------------------------------------------------------------------------


def relationship_amount_multiplier(
    rng: np.random.Generator,
    relationship_type: str,
    recurrence_profile: str,
    customer_type: str,
) -> float:
    """Return a mean-scale multiplier for a transfer amount model."""

    base = {
        "OWN_ACCOUNT": 0.95,
        "HOUSEHOLD_FAMILY": 0.42,
        "PEER_TO_PEER": 0.24,
        "RECURRING_PERSONAL": 0.36,
        "SUPPLIER_CUSTOMER_NETWORK": 1.25,
        "PAYROLL_OR_STAFF": 0.75,
        "BUSINESS_PARTNER": 1.10,
        "TREASURY_INTERNAL": 1.65,
        "EXTERNAL_BANK_SELF_TRANSFER": 1.00,
        "SAVINGS_INVESTMENT": 0.95,
        "WALLET_FUNDING": 0.22,
        "TREASURY_EXTERNAL": 1.70,
        "SUPPLIER_SETTLEMENT": 1.35,
        "LIQUIDITY_MANAGEMENT": 1.55,
        "FINANCING_RELATIONSHIP": 1.25,
        "REMITTANCE": 0.65,
        "INTERNATIONAL_SUPPLIER": 1.60,
        "INTERNATIONAL_CUSTOMER": 1.45,
        "FOREIGN_TREASURY": 1.85,
    }.get(str(relationship_type), 1.0)
    if customer_type == "BUSINESS":
        base *= 1.10
    sigma = 0.10 if recurrence_profile == "RECURRING" else (0.22 if recurrence_profile == "OCCASIONAL" else 0.35)
    return float(np.clip(base * rng.lognormal(-0.5 * sigma * sigma, sigma), 0.08, 6.0))


def relationship_channel_weights(
    relationship: Mapping[str, object],
    digital_preference: float,
    amount_uyu: float,
    customer_type: str,
) -> tuple[list[str], list[float]]:
    """Return channel labels and weights conditioned on relationship semantics."""

    preferred = str(relationship.get("preferred_channel", "MOBILE"))
    labels = ["MOBILE", "WEB", "AUTOMATIC", "BRANCH"]
    digital = float(np.clip(digital_preference, 0.0, 1.0))
    weights = np.array([
        1.0 + 2.0 * digital,
        0.8 + 1.3 * digital,
        0.45,
        0.35 + 0.8 * (1.0 - digital),
    ], dtype=float)
    if customer_type == "BUSINESS":
        weights *= np.array([0.75, 1.65, 1.05, 1.10])
    if amount_uyu >= 1_000_000:
        weights *= np.array([0.55, 1.35, 0.80, 1.45])
    if str(relationship.get("recurrence_profile")) == "RECURRING":
        weights[2] *= 1.55
    if preferred in labels:
        weights[labels.index(preferred)] *= 1.75
    return labels, weights.tolist()


# -----------------------------------------------------------------------------
# Audits
# -----------------------------------------------------------------------------


def audit_transfer_relationships(
    relationships: pd.DataFrame,
    accounts: pd.DataFrame,
    customers: pd.DataFrame,
    financial_institutions: pd.DataFrame,
) -> TransferNetworkAudit:
    """Validate structural invariants of the V6 relationship network."""

    metrics: MutableMapping[str, int] = defaultdict(int)
    if relationships.empty:
        metrics["empty_relationship_network"] = 1
        return TransferNetworkAudit(False, dict(metrics))

    missing = set(RELATIONSHIP_COLUMNS) - set(relationships.columns)
    metrics["missing_columns"] = len(missing)
    if missing:
        return TransferNetworkAudit(False, dict(metrics))

    rel = relationships.copy()
    rel["customer_id"] = rel["customer_id"].astype(str)
    rel["source_account_id"] = rel["source_account_id"].astype(str)
    rel["start_date"] = pd.to_datetime(rel["start_date"], errors="coerce")
    rel["end_date"] = pd.to_datetime(rel["end_date"], errors="coerce")

    account_ids = set(accounts["account_id"].astype(str))
    customer_ids = set(customers["customer_id"].astype(str))
    institution_ids = set(financial_institutions["institution_id"].astype(str))

    metrics["duplicate_relationship_id"] = int(rel["relationship_id"].duplicated().sum())
    metrics["unknown_customer"] = int((~rel["customer_id"].isin(customer_ids)).sum())
    metrics["unknown_source_account"] = int((~rel["source_account_id"].isin(account_ids)).sum())
    metrics["invalid_scope"] = int((~rel["counterparty_scope"].isin(TRANSFER_SCOPES)).sum())
    metrics["invalid_recurrence"] = int((~rel["recurrence_profile"].isin(RECURRENCE_PROFILES)).sum())
    metrics["invalid_strength"] = int((pd.to_numeric(rel["relationship_strength"], errors="coerce") <= 0).sum())
    metrics["missing_start_date"] = int(rel["start_date"].isna().sum())
    metrics["end_before_start"] = int((rel["end_date"].notna() & (rel["end_date"] < rel["start_date"])).sum())

    internal = rel["counterparty_scope"].eq("INTERNAL")
    external = rel["counterparty_scope"].isin(["DOMESTIC_EXTERNAL", "INTERNATIONAL"])

    internal_customer = rel.loc[internal, "counterparty_customer_id"].dropna().astype(str)
    internal_account = rel.loc[internal, "counterparty_account_id"].dropna().astype(str)
    btyt_institution_id = str(
        financial_institutions.loc[
            financial_institutions["institution_name"].astype(str).str.upper().str.contains("BTYT"),
            "institution_id",
        ].iloc[0]
    )
    metrics["internal_missing_institution"] = int(
        rel.loc[internal, "counterparty_institution_id"].isna().sum()
    )
    metrics["internal_wrong_institution"] = int(
        (
            rel.loc[internal, "counterparty_institution_id"]
            .fillna("<NA>")
            .astype(str)
            .ne(btyt_institution_id)
        ).sum()
    )
    metrics["internal_missing_counterparty_customer"] = int(rel.loc[internal, "counterparty_customer_id"].isna().sum())
    metrics["internal_missing_counterparty_account"] = int(rel.loc[internal, "counterparty_account_id"].isna().sum())
    metrics["internal_unknown_counterparty_customer"] = int((~internal_customer.isin(customer_ids)).sum())
    metrics["internal_unknown_counterparty_account"] = int((~internal_account.isin(account_ids)).sum())

    external_institution = rel.loc[external, "counterparty_institution_id"].dropna().astype(str)
    metrics["external_missing_institution"] = int(rel.loc[external, "counterparty_institution_id"].isna().sum())
    metrics["external_unknown_institution"] = int((~external_institution.isin(institution_ids)).sum())

    # Same-account loops are never valid. Same-customer relationships are valid
    # only when explicitly modeled as OWN_ACCOUNT/TREASURY_INTERNAL.
    same_account = internal & rel["source_account_id"].eq(rel["counterparty_account_id"].astype(str))
    metrics["internal_same_account"] = int(same_account.sum())
    same_customer = internal & rel["customer_id"].eq(rel["counterparty_customer_id"].astype(str))
    allowed_same_customer = rel["relationship_type"].isin(["OWN_ACCOUNT", "TREASURY_INTERNAL"])
    metrics["internal_unlabeled_same_customer"] = int((same_customer & ~allowed_same_customer).sum())

    passed = all(value == 0 for value in metrics.values())
    return TransferNetworkAudit(bool(passed), dict(metrics))


__all__ = [
    "RELATIONSHIP_COLUMNS",
    "TRANSFER_SCOPES",
    "RECURRENCE_PROFILES",
    "TransferResolution",
    "TransferNetworkAudit",
    "stable_relationship_id",
    "build_account_network_context",
    "build_transfer_relationships",
    "build_relationship_index",
    "relationship_is_active",
    "relationship_event_weight",
    "resolve_persistent_transfer",
    "relationship_amount_multiplier",
    "relationship_channel_weights",
    "audit_transfer_relationships",
]
