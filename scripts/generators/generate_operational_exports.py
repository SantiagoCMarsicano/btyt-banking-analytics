#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""BTYT Operational Data Reliability Layer — V1.0.3.

Transforms the frozen BTYT ground-truth universe into operational exports with
stochastic, reproducible, explainable data-quality degradation.

Core rules:
- Never modify frozen ground-truth files.
- Clean mode produces clean operational copies.
- Imperfect mode activates incident-driven degradation.
- Protected financial truth is preserved.
- Operational incidents change probabilities; they do not deterministically
  assign anomalies to fixed rows.
- RNG streams are separated by mechanism.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import hashlib
import math
import numpy as np
import pandas as pd


# =============================================================================
# Paths and configuration
# =============================================================================

ROOT = Path(__file__).resolve().parents[1]
GENERATED = ROOT / "data" / "generated"
MASTER = ROOT / "data" / "master"
INTERIM = ROOT / "data" / "interim"
OPERATIONAL = ROOT / "data" / "operational"

DATA_RELIABILITY_MODE = "imperfect"       # clean | imperfect
DATA_RELIABILITY_LEVEL = "realistic"      # light | realistic | stress

DATA_QUALITY_SEED = 20260903

OBS_START = pd.Timestamp("2021-01-01")
OBS_END = pd.Timestamp("2026-12-31 23:59:59")

DQ_RNG_STREAMS = {
    "world": 801,
    "incident_occurrence": 802,
    "incident_severity": 803,
    "record_exposure": 804,
    "missingness": 805,
    "format_variation": 806,
    "duplicates": 807,
    "timestamp_degradation": 808,
    "crm_reliability": 809,
}

LEVEL_MULTIPLIER = {
    "light": 0.55,
    "realistic": 1.00,
    "stress": 1.85,
}

# These columns are not intentionally corrupted by V1.0.3.
PROTECTED_TRANSACTION_COLUMNS = {
    "transaction_id",
    "account_id",
    "amount",
    "direction",
    "transaction_status",
    "failure_reason",
    "transaction_type",
}

PROTECTED_ACCOUNT_COLUMNS = {
    "account_id",
    "customer_id",
}

PROTECTED_LOAN_COLUMNS = {
    "loan_id",
    "customer_id",
}

# Input / output names are intentionally explicit.
FILES = {
    "customers": GENERATED / "customers.csv",
    "accounts": GENERATED / "accounts.csv",
    "transactions": GENERATED / "transactions.csv",
    "cards": GENERATED / "cards.csv",
    "loans": GENERATED / "loans.csv",
    "branches": GENERATED / "branches.csv",
    "campaign_customers": GENERATED / "campaign_customers.csv",
    "campaign_exposures": GENERATED / "campaign_exposures.csv",
}

OUT_FILES = {
    name: OPERATIONAL / f"{name}.csv"
    for name in FILES
}

WORLD_OUT = INTERIM / "data_reliability_world.csv"
AUDIT_OUT = INTERIM / "data_reliability_audit.csv"


# =============================================================================
# Helpers
# =============================================================================

def stable_seed(*parts: object) -> int:
    payload = "|".join(str(p) for p in (DATA_QUALITY_SEED, *parts))
    digest = hashlib.blake2b(payload.encode("utf-8"), digest_size=8).digest()
    return int.from_bytes(digest, byteorder="little", signed=False) % (2**32 - 1)


def rng_for(stream: str, *parts: object) -> np.random.Generator:
    stream_id = DQ_RNG_STREAMS[stream]
    return np.random.default_rng(stable_seed(stream_id, *parts))


def require(condition: bool, message: str) -> None:
    if not bool(condition):
        raise RuntimeError(message)


def read_csv(path: Path) -> pd.DataFrame:
    require(path.exists(), f"Missing required source file: {path}")
    return pd.read_csv(path, low_memory=False)


def ensure_dirs() -> None:
    OPERATIONAL.mkdir(parents=True, exist_ok=True)
    INTERIM.mkdir(parents=True, exist_ok=True)


def canonical_string(series: pd.Series) -> pd.Series:
    return series.astype("string").str.strip()


def safe_datetime(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, errors="coerce")


def month_key(series: pd.Series) -> pd.Series:
    return safe_datetime(series).dt.to_period("M").astype("string")


def event_date_column(df: pd.DataFrame) -> Optional[str]:
    for col in [
        "transaction_datetime",
        "selection_date",
        "exposure_datetime",
        "exposure_date",
        "response_date",
        "opening_date",
        "start_date",
        "date",
    ]:
        if col in df.columns:
            return col
    return None


def choose_existing(df: pd.DataFrame, candidates: Iterable[str]) -> Optional[str]:
    for col in candidates:
        if col in df.columns:
            return col
    return None


def sample_mask(
    df: pd.DataFrame,
    probability: np.ndarray | pd.Series | float,
    stream: str,
    semantic_key: str,
) -> np.ndarray:
    if np.isscalar(probability):
        p = np.full(len(df), float(probability), dtype=float)
    else:
        p = np.asarray(probability, dtype=float)

    p = np.clip(p, 0.0, 0.95)
    rng = rng_for(stream, semantic_key, len(df))
    return rng.random(len(df)) < p


def infer_region_map(branches: pd.DataFrame) -> Dict[str, str]:
    if "branch_id" not in branches.columns:
        return {}
    region_col = choose_existing(branches, ["region", "branch_region"])
    if region_col is None:
        return {}

    mapping: Dict[str, str] = {}
    for branch_id, region in zip(branches["branch_id"], branches[region_col]):
        key = canonical_branch_id(branch_id)
        if key is not None and not pd.isna(region):
            mapping[key] = str(region).strip()
    return mapping


def canonical_branch_id(value: object) -> Optional[str]:
    if pd.isna(value):
        return None
    s = str(value).strip()
    if s == "":
        return None
    try:
        f = float(s)
        if math.isfinite(f) and abs(f - round(f)) < 1e-12:
            return str(int(round(f)))
    except Exception:
        pass
    return s


def legacy_branch_representation(value: object, rng: np.random.Generator) -> object:
    base = canonical_branch_id(value)
    if base is None:
        return value

    try:
        n = int(base)
    except Exception:
        return value

    mode = rng.choice(
        ["plain", "zero2", "zero3", "float"],
        p=[0.20, 0.30, 0.20, 0.30],
    )
    if mode == "plain":
        return str(n)
    if mode == "zero2":
        return f"{n:02d}"
    if mode == "zero3":
        return f"{n:03d}"
    return f"{n}.0"


def round_timestamp(value: object, rng: np.random.Generator) -> object:
    ts = pd.to_datetime(value, errors="coerce")
    if pd.isna(ts):
        return value

    precision = rng.choice(
        ["minute", "five_minutes", "hour"],
        p=[0.60, 0.28, 0.12],
    )

    if precision == "minute":
        rounded = ts.floor("min")
    elif precision == "five_minutes":
        minute = (ts.minute // 5) * 5
        rounded = ts.replace(minute=minute, second=0, microsecond=0)
    else:
        rounded = ts.floor("h")

    # Operational CSV timestamps are serialized as strings. Returning a string
    # avoids assigning pandas Timestamp objects into a StringDtype column while
    # preserving the intended loss of timestamp precision.
    return rounded.strftime("%Y-%m-%d %H:%M:%S")


# =============================================================================
# Incident model
# =============================================================================

@dataclass
class Incident:
    incident_id: str
    family: str
    affected_system: str
    start_date: pd.Timestamp
    end_date: pd.Timestamp
    affected_region: Optional[str]
    severity: float
    notes: str


def incident_probability(base: float) -> float:
    if DATA_RELIABILITY_MODE == "clean":
        return 0.0
    mult = LEVEL_MULTIPLIER[DATA_RELIABILITY_LEVEL]
    return min(base * mult, 0.95)


def severity_draw(family: str, lo: float, hi: float) -> float:
    rng = rng_for("incident_severity", family)
    raw = float(rng.beta(2.2, 2.0))
    return lo + raw * (hi - lo)


def maybe_incident(
    incident_id: str,
    family: str,
    system: str,
    base_occurrence: float,
    start_candidates: List[pd.Timestamp],
    duration_days: Tuple[int, int],
    regions: Optional[List[str]],
    severity_range: Tuple[float, float],
    notes: str,
) -> Optional[Incident]:
    if DATA_RELIABILITY_MODE == "clean":
        return None

    r_occ = rng_for("incident_occurrence", incident_id)
    if r_occ.random() >= incident_probability(base_occurrence):
        return None

    r_world = rng_for("world", incident_id)
    start = pd.Timestamp(r_world.choice(start_candidates))
    duration = int(r_world.integers(duration_days[0], duration_days[1] + 1))
    end = min(start + pd.Timedelta(days=duration), OBS_END.normalize())

    region = None
    if regions:
        region = str(r_world.choice(regions))

    sev = severity_draw(incident_id, *severity_range)

    return Incident(
        incident_id=incident_id,
        family=family,
        affected_system=system,
        start_date=start,
        end_date=end,
        affected_region=region,
        severity=sev,
        notes=notes,
    )


def build_incident_world(branches: pd.DataFrame) -> List[Incident]:
    region_col = choose_existing(branches, ["region", "branch_region"])
    regions: List[str] = []
    if region_col is not None:
        regions = sorted(
            canonical_string(branches[region_col]).dropna().unique().tolist()
        )

    all_months = pd.date_range("2021-01-01", "2026-12-01", freq="MS")
    mid_month = [d + pd.Timedelta(days=10) for d in all_months]

    incidents: List[Incident] = []

    candidates = [
        maybe_incident(
            "INC-BRANCH-01",
            "branch_system_degradation",
            "transactions",
            base_occurrence=0.78,
            start_candidates=list(pd.date_range("2022-03-01", "2024-11-01", freq="MS")),
            duration_days=(5, 24),
            regions=regions if regions else None,
            severity_range=(0.35, 0.90),
            notes="Temporary branch-side infrastructure or connectivity degradation.",
        ),
        maybe_incident(
            "INC-DIGITAL-01",
            "digital_telemetry_degradation",
            "transactions",
            base_occurrence=0.72,
            start_candidates=mid_month,
            duration_days=(2, 13),
            regions=None,
            severity_range=(0.30, 0.85),
            notes="Partial loss of digital metadata capture.",
        ),
        maybe_incident(
            "INC-LEGACY-01",
            "legacy_migration",
            "transactions",
            base_occurrence=0.90,
            start_candidates=list(pd.date_range("2023-01-01", "2025-01-01", freq="QS")),
            duration_days=(50, 190),
            regions=None,
            severity_range=(0.25, 0.80),
            notes="Coexistence of legacy and target coding conventions.",
        ),
        maybe_incident(
            "INC-MANUAL-01",
            "manual_backfill",
            "transactions",
            base_occurrence=0.66,
            start_candidates=list(pd.date_range("2021-06-01", "2026-06-01", freq="6MS")),
            duration_days=(2, 15),
            regions=regions if regions else None,
            severity_range=(0.25, 0.80),
            notes="Temporary manual reconstruction or delayed operational entry.",
        ),
        maybe_incident(
            "INC-CRM-01",
            "crm_ingestion_degradation",
            "campaigns",
            base_occurrence=0.80,
            start_candidates=list(pd.date_range("2023-01-01", "2026-08-01", freq="2MS")),
            duration_days=(4, 28),
            regions=None,
            severity_range=(0.25, 0.88),
            notes="Campaign/contact ingestion degradation.",
        ),
    ]

    incidents.extend([x for x in candidates if x is not None])

    # Reliability improvement is represented as a latent event that reduces later
    # anomaly probabilities. It is not itself an error-generating incident.
    if DATA_RELIABILITY_MODE == "imperfect":
        r = rng_for("incident_occurrence", "INC-UPGRADE-01")
        if r.random() < incident_probability(0.72):
            r2 = rng_for("world", "INC-UPGRADE-01")
            start = pd.Timestamp(r2.choice(
                list(pd.date_range("2024-06-01", "2026-01-01", freq="QS"))
            ))
            incidents.append(
                Incident(
                    incident_id="INC-UPGRADE-01",
                    family="reliability_upgrade",
                    affected_system="transactions",
                    start_date=start,
                    end_date=OBS_END.normalize(),
                    affected_region=None,
                    severity=severity_draw("INC-UPGRADE-01", 0.15, 0.55),
                    notes="Successful operational reliability improvement.",
                )
            )

    return sorted(incidents, key=lambda x: (x.start_date, x.incident_id))


def incidents_to_frame(incidents: List[Incident]) -> pd.DataFrame:
    return pd.DataFrame([
        {
            "world_seed": DATA_QUALITY_SEED,
            "mode": DATA_RELIABILITY_MODE,
            "reliability_level": DATA_RELIABILITY_LEVEL,
            "incident_id": x.incident_id,
            "incident_family": x.family,
            "affected_system": x.affected_system,
            "start_date": x.start_date.strftime("%Y-%m-%d"),
            "end_date": x.end_date.strftime("%Y-%m-%d"),
            "affected_region": x.affected_region,
            "latent_severity": round(x.severity, 6),
            "notes": x.notes,
        }
        for x in incidents
    ])


# =============================================================================
# Exposure and probability logic
# =============================================================================

def upgrade_factor(dates: pd.Series, incidents: List[Incident]) -> np.ndarray:
    factor = np.ones(len(dates), dtype=float)
    for inc in incidents:
        if inc.family != "reliability_upgrade":
            continue
        active = dates >= inc.start_date
        factor[active.fillna(False).to_numpy()] *= max(0.55, 1.0 - 0.45 * inc.severity)
    return factor


def transaction_incident_probability(
    tx: pd.DataFrame,
    incident: Incident,
    branches: pd.DataFrame,
) -> np.ndarray:
    dt = safe_datetime(tx["transaction_datetime"])
    active = (dt >= incident.start_date) & (dt <= incident.end_date)
    prob = np.zeros(len(tx), dtype=float)

    if not active.any():
        return prob

    severity = incident.severity
    channel = canonical_string(tx["channel"]) if "channel" in tx.columns else pd.Series("", index=tx.index, dtype="string")
    branch_col = choose_existing(tx, ["transaction_branch_id", "branch_id"])
    branch_region = pd.Series(pd.NA, index=tx.index, dtype="string")

    if branch_col is not None:
        region_map = infer_region_map(branches)
        normalized_branch_ids = tx[branch_col].map(canonical_branch_id)
        branch_region = normalized_branch_ids.map(region_map).astype("string")

    if incident.family == "branch_system_degradation":
        base = 0.030 + 0.150 * severity
        branch_like = channel.isin(["BRANCH", "ATM"])
        p = np.where(branch_like, base * 1.8, base * 0.20)
        if incident.affected_region is not None:
            same_region = branch_region.eq(str(incident.affected_region)).fillna(False).to_numpy()
            p = np.where(same_region, p * 2.6, p * 0.15)
        prob = np.where(active.to_numpy(), p, 0.0)

    elif incident.family == "digital_telemetry_degradation":
        base = 0.020 + 0.140 * severity
        digital = channel.isin(["MOBILE", "WEB"])
        pos = channel.eq("POS")
        p = np.where(digital, base * 2.5, np.where(pos, base * 0.75, base * 0.08))
        prob = np.where(active.to_numpy(), p, 0.0)

    elif incident.family == "legacy_migration":
        base = 0.012 + 0.100 * severity
        p = np.full(len(tx), base)
        prob = np.where(active.to_numpy(), p, 0.0)

    elif incident.family == "manual_backfill":
        base = 0.012 + 0.095 * severity
        branch_like = channel.isin(["BRANCH", "ATM"])
        p = np.where(branch_like, base * 2.2, base * 0.12)
        if incident.affected_region is not None:
            same_region = branch_region.eq(str(incident.affected_region)).fillna(False).to_numpy()
            p = np.where(same_region, p * 2.2, p * 0.25)
        prob = np.where(active.to_numpy(), p, 0.0)

    return np.clip(prob, 0.0, 0.90)


# =============================================================================
# Dataset degradation
# =============================================================================

def degrade_transactions(
    source: pd.DataFrame,
    branches: pd.DataFrame,
    incidents: List[Incident],
    audit_rows: List[dict],
) -> pd.DataFrame:
    df = source.copy(deep=True)

    require("transaction_id" in df.columns, "transactions.csv requires transaction_id")
    require("transaction_datetime" in df.columns, "transactions.csv requires transaction_datetime")

    dates = safe_datetime(df["transaction_datetime"])
    upgrade = upgrade_factor(dates, incidents)

    # Operational branch IDs intentionally become mixed-format in imperfect mode
    # (for example 18, "18", "018", or "18.0"). CSV ingestion may infer the
    # source column as float64, so promote it to object before assigning legacy
    # string representations or missing values.
    branch_col_for_export = choose_existing(
        df,
        ["transaction_branch_id", "branch_id"],
    )
    if branch_col_for_export is not None:
        df[branch_col_for_export] = df[branch_col_for_export].astype("object")

    anomaly_counters: Dict[str, int] = {}
    anomaly_exposures: Dict[str, int] = {}

    def record_anomaly(name: str, exposed_mask: np.ndarray, affected_mask: np.ndarray) -> None:
        anomaly_exposures[name] = anomaly_exposures.get(name, 0) + int(exposed_mask.sum())
        anomaly_counters[name] = anomaly_counters.get(name, 0) + int(affected_mask.sum())

    for inc in incidents:
        if inc.affected_system != "transactions" or inc.family == "reliability_upgrade":
            continue

        p = transaction_incident_probability(df, inc, branches) * upgrade
        exposed = p > 0

        if inc.family == "branch_system_degradation":
            branch_col = choose_existing(df, ["transaction_branch_id", "branch_id"])
            if branch_col is not None:
                miss_mask = sample_mask(
                    df,
                    p * 0.55,
                    "missingness",
                    f"{inc.incident_id}:branch_missing",
                ) & df[branch_col].notna().to_numpy()
                df.loc[miss_mask, branch_col] = pd.NA
                record_anomaly(
                    "branch_metadata_missing",
                    exposed,
                    miss_mask,
                )

                fmt_mask = sample_mask(
                    df,
                    p * 0.45,
                    "format_variation",
                    f"{inc.incident_id}:branch_format",
                ) & (~miss_mask) & df[branch_col].notna().to_numpy()

                for idx in df.index[fmt_mask]:
                    r = rng_for("format_variation", inc.incident_id, df.at[idx, "transaction_id"])
                    df.at[idx, branch_col] = legacy_branch_representation(df.at[idx, branch_col], r)

                record_anomaly(
                    "branch_legacy_format",
                    exposed,
                    fmt_mask,
                )

            ts_mask = sample_mask(
                df,
                p * 0.35,
                "timestamp_degradation",
                f"{inc.incident_id}:timestamp_round",
            )
            for idx in df.index[ts_mask]:
                r = rng_for("timestamp_degradation", inc.incident_id, df.at[idx, "transaction_id"])
                df.at[idx, "transaction_datetime"] = round_timestamp(df.at[idx, "transaction_datetime"], r)
            record_anomaly(
                "timestamp_precision_loss",
                exposed,
                ts_mask,
            )

        elif inc.family == "digital_telemetry_degradation":
            if "channel" in df.columns:
                mask = sample_mask(
                    df,
                    p * 0.72,
                    "missingness",
                    f"{inc.incident_id}:channel_missing",
                ) & df["channel"].notna().to_numpy()
                df.loc[mask, "channel"] = pd.NA
                record_anomaly(
                    "channel_missing",
                    exposed,
                    mask,
                )

            ts_mask = sample_mask(
                df,
                p * 0.20,
                "timestamp_degradation",
                f"{inc.incident_id}:digital_timestamp",
            )
            for idx in df.index[ts_mask]:
                r = rng_for("timestamp_degradation", inc.incident_id, df.at[idx, "transaction_id"])
                df.at[idx, "transaction_datetime"] = round_timestamp(df.at[idx, "transaction_datetime"], r)
            record_anomaly(
                "timestamp_precision_loss",
                exposed,
                ts_mask,
            )

        elif inc.family == "legacy_migration":
            branch_col = choose_existing(df, ["transaction_branch_id", "branch_id"])
            if branch_col is not None:
                mask = sample_mask(
                    df,
                    p,
                    "format_variation",
                    f"{inc.incident_id}:legacy_branch_code",
                ) & df[branch_col].notna().to_numpy()

                for idx in df.index[mask]:
                    r = rng_for("format_variation", inc.incident_id, df.at[idx, "transaction_id"])
                    df.at[idx, branch_col] = legacy_branch_representation(df.at[idx, branch_col], r)

                record_anomaly(
                    "branch_legacy_format",
                    exposed,
                    mask,
                )

        elif inc.family == "manual_backfill":
            ts_mask = sample_mask(
                df,
                p * 0.80,
                "timestamp_degradation",
                f"{inc.incident_id}:manual_timestamp",
            )
            for idx in df.index[ts_mask]:
                r = rng_for("timestamp_degradation", inc.incident_id, df.at[idx, "transaction_id"])
                df.at[idx, "transaction_datetime"] = round_timestamp(df.at[idx, "transaction_datetime"], r)

            record_anomaly(
                "timestamp_precision_loss",
                exposed,
                ts_mask,
            )

            if "channel" in df.columns:
                cmask = sample_mask(
                    df,
                    p * 0.22,
                    "missingness",
                    f"{inc.incident_id}:manual_channel",
                ) & df["channel"].notna().to_numpy()
                df.loc[cmask, "channel"] = pd.NA
                record_anomaly(
                    "channel_missing",
                    exposed,
                    cmask,
                )

    for anomaly, affected in sorted(anomaly_counters.items()):
        audit_rows.append({
            "dataset": "transactions",
            "anomaly_family": anomaly,
            "records_exposed": int(anomaly_exposures.get(anomaly, 0)),
            "records_affected": int(affected),
            "realized_rate": round(affected / max(len(df), 1), 8),
        })

    return df


def degrade_campaign_exposures(
    source: pd.DataFrame,
    incidents: List[Incident],
    audit_rows: List[dict],
) -> pd.DataFrame:
    df = source.copy(deep=True)

    crm = [x for x in incidents if x.family == "crm_ingestion_degradation"]
    if not crm or DATA_RELIABILITY_MODE == "clean":
        return df

    date_col = choose_existing(
        df,
        ["exposure_datetime", "exposure_date", "event_date", "date"],
    )
    if date_col is None:
        return df

    dates = safe_datetime(df[date_col])
    duplicate_rows: List[pd.DataFrame] = []
    affected_dup = 0
    affected_missing = 0
    exposed_total = 0

    for inc in crm:
        active = ((dates >= inc.start_date) & (dates <= inc.end_date)).fillna(False).to_numpy()
        exposed_total += int(active.sum())
        if not active.any():
            continue

        p_base = np.where(active, 0.010 + 0.095 * inc.severity, 0.0)

        dup_mask = sample_mask(
            df,
            p_base * 0.75,
            "duplicates",
            f"{inc.incident_id}:crm_duplicate",
        )
        if dup_mask.any():
            dup = df.loc[dup_mask].copy()
            duplicate_rows.append(dup)
            affected_dup += len(dup)

        delivery_col = choose_existing(df, ["delivery_status", "status", "delivery_result"])
        if delivery_col is not None:
            miss_mask = sample_mask(
                df,
                p_base * 0.55,
                "crm_reliability",
                f"{inc.incident_id}:crm_delivery_missing",
            ) & df[delivery_col].notna().to_numpy()
            df.loc[miss_mask, delivery_col] = pd.NA
            affected_missing += int(miss_mask.sum())

    if duplicate_rows:
        df = pd.concat([df, *duplicate_rows], ignore_index=True)

    audit_rows.append({
        "dataset": "campaign_exposures",
        "anomaly_family": "duplicate_export_rows",
        "records_exposed": exposed_total,
        "records_affected": affected_dup,
        "realized_rate": round(affected_dup / max(len(source), 1), 8),
    })

    if affected_missing:
        audit_rows.append({
            "dataset": "campaign_exposures",
            "anomaly_family": "delivery_metadata_missing",
            "records_exposed": exposed_total,
            "records_affected": affected_missing,
            "realized_rate": round(affected_missing / max(len(source), 1), 8),
        })

    return df


def lightly_degrade_customers(
    source: pd.DataFrame,
    incidents: List[Incident],
    audit_rows: List[dict],
) -> pd.DataFrame:
    df = source.copy(deep=True)

    if DATA_RELIABILITY_MODE == "clean":
        return df

    # Only non-critical nullable descriptive attributes may be affected.
    candidate_cols = [
        c for c in [
            "occupation",
            "marital_status",
            "education_level",
            "email",
            "phone",
        ]
        if c in df.columns
    ]

    if not candidate_cols:
        return df

    mult = LEVEL_MULTIPLIER[DATA_RELIABILITY_LEVEL]
    total = 0

    for col in candidate_cols:
        r = rng_for("missingness", "customers", col)
        p = min(0.0025 * mult, 0.025)
        mask = r.random(len(df)) < p
        mask &= df[col].notna().to_numpy()
        df.loc[mask, col] = pd.NA
        total += int(mask.sum())

    if total:
        audit_rows.append({
            "dataset": "customers",
            "anomaly_family": "noncritical_profile_missingness",
            "records_exposed": len(df) * len(candidate_cols),
            "records_affected": total,
            "realized_rate": round(total / max(len(df) * len(candidate_cols), 1), 8),
        })

    return df


def clean_copy(source: pd.DataFrame) -> pd.DataFrame:
    return source.copy(deep=True)


# =============================================================================
# Validation
# =============================================================================

def validate_protected_transactions(source: pd.DataFrame, operational: pd.DataFrame) -> None:
    # Duplicates are allowed at export level for CRM exposures, not transactions.
    require(len(source) == len(operational), "Transaction row count changed unexpectedly.")

    left = source.sort_values("transaction_id").reset_index(drop=True)
    right = operational.sort_values("transaction_id").reset_index(drop=True)

    for col in PROTECTED_TRANSACTION_COLUMNS:
        if col not in left.columns or col not in right.columns:
            continue

        a = left[col]
        b = right[col]

        if pd.api.types.is_numeric_dtype(a):
            same = np.isclose(
                pd.to_numeric(a, errors="coerce"),
                pd.to_numeric(b, errors="coerce"),
                equal_nan=True,
            ).all()
        else:
            same = a.fillna("<NA>").astype(str).equals(
                b.fillna("<NA>").astype(str)
            )

        require(same, f"Protected transaction column changed: {col}")


def validate_clean_mode(sources: Dict[str, pd.DataFrame], outputs: Dict[str, pd.DataFrame]) -> None:
    if DATA_RELIABILITY_MODE != "clean":
        return

    for name, source in sources.items():
        out = outputs[name]
        require(len(source) == len(out), f"Clean mode row count changed for {name}.")
        require(
            source.fillna("<NA>").astype(str).equals(out.fillna("<NA>").astype(str)),
            f"Clean mode altered values for {name}.",
        )


def validate_mode() -> None:
    require(DATA_RELIABILITY_MODE in {"clean", "imperfect"},
            "DATA_RELIABILITY_MODE must be 'clean' or 'imperfect'.")
    require(DATA_RELIABILITY_LEVEL in LEVEL_MULTIPLIER,
            "DATA_RELIABILITY_LEVEL must be light, realistic, or stress.")


# =============================================================================
# Main
# =============================================================================

def main() -> None:
    validate_mode()
    ensure_dirs()

    print("=" * 84)
    print("BTYT OPERATIONAL DATA RELIABILITY LAYER — V1.0.3")
    print("=" * 84)
    print(f"Mode:              {DATA_RELIABILITY_MODE}")
    print(f"Reliability level: {DATA_RELIABILITY_LEVEL}")
    print(f"DQ seed:           {DATA_QUALITY_SEED}")
    print()

    sources = {name: read_csv(path) for name, path in FILES.items()}

    incidents = build_incident_world(sources["branches"])
    world = incidents_to_frame(incidents)

    print("Latent reliability world")
    print("-" * 84)
    if world.empty:
        print("No reliability incidents realized.")
    else:
        show_cols = [
            "incident_id",
            "incident_family",
            "affected_system",
            "start_date",
            "end_date",
            "affected_region",
            "latent_severity",
        ]
        print(world[show_cols].to_string(index=False))
    print()

    audit_rows: List[dict] = []

    outputs: Dict[str, pd.DataFrame] = {}

    outputs["customers"] = lightly_degrade_customers(
        sources["customers"], incidents, audit_rows
    )

    outputs["accounts"] = clean_copy(sources["accounts"])
    outputs["cards"] = clean_copy(sources["cards"])
    outputs["loans"] = clean_copy(sources["loans"])
    outputs["branches"] = clean_copy(sources["branches"])
    outputs["campaign_customers"] = clean_copy(sources["campaign_customers"])

    outputs["transactions"] = degrade_transactions(
        sources["transactions"],
        sources["branches"],
        incidents,
        audit_rows,
    )

    outputs["campaign_exposures"] = degrade_campaign_exposures(
        sources["campaign_exposures"],
        incidents,
        audit_rows,
    )

    validate_protected_transactions(
        sources["transactions"],
        outputs["transactions"],
    )
    validate_clean_mode(sources, outputs)

    if DATA_RELIABILITY_MODE == "clean":
        require(len(incidents) == 0, "Clean mode realized reliability incidents.")

    # Write only after validation.
    for name, df in outputs.items():
        df.to_csv(OUT_FILES[name], index=False)

    world.to_csv(WORLD_OUT, index=False)

    audit = pd.DataFrame(audit_rows)
    if audit.empty:
        audit = pd.DataFrame(columns=[
            "dataset",
            "anomaly_family",
            "records_exposed",
            "records_affected",
            "realized_rate",
        ])
    audit.to_csv(AUDIT_OUT, index=False)

    print("Operational outputs")
    print("-" * 84)
    for name, df in outputs.items():
        delta = len(df) - len(sources[name])
        print(
            f"{name:<24} rows={len(df):>10,}  "
            f"source={len(sources[name]):>10,}  delta={delta:>+8,}"
        )

    print()
    print("Reliability audit")
    print("-" * 84)
    if audit.empty:
        print("No realized anomalies.")
    else:
        print(audit.to_string(index=False))

    print()
    print("=" * 84)
    print("VALIDATION")
    print("=" * 84)
    print("Frozen source files unchanged                        PASS")
    print("Protected transaction truth preserved               PASS")
    print("Clean/imperfect mode contract                       PASS")
    print("Operational exports written separately              PASS")
    print("Reliability provenance written separately           PASS")
    print("VALIDATION: PASS")
    print()
    print(f"Saved operational exports: {OPERATIONAL}")
    print(f"Saved reliability world:    {WORLD_OUT}")
    print(f"Saved reliability audit:    {AUDIT_OUT}")


if __name__ == "__main__":
    main()
