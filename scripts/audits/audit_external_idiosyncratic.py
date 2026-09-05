"""
BTYT Banking Analytics
External Idiosyncratic Shock Audit

Purpose
-------
Audit the realized customer-level idiosyncratic shock layer after the
External Shocks engine has generated its production world.

This script does not regenerate or modify any banking dataset.
It reads the current External Shocks outputs and evaluates:

- customer-universe reconciliation;
- customer-month grain;
- event incidence and coverage;
- event-type mix;
- repeat-event concentration;
- temporal concentration;
- household/business allocation;
- realized probability distribution;
- mediation and residual magnitude;
- same-event cooldown integrity;
- overlapping idiosyncratic episodes;
- clipping/saturation in latent customer state;
- broad calibration guardrails.

All code and comments are intentionally written in English.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
DATA_GENERATED = ROOT / "data" / "generated"
DATA_INTERIM = ROOT / "data" / "interim"

CUSTOMERS_PATH = DATA_GENERATED / "customers.csv"
IDIO_EVENTS_PATH = DATA_INTERIM / "external_idiosyncratic_events.csv"
CUSTOMER_STATE_PATH = DATA_INTERIM / "external_customer_monthly_state.csv"
RESILIENCE_PATH = DATA_INTERIM / "external_shock_resilience.csv"

N_MONTHS_EXPECTED = 72
COOLDOWN_MONTHS = 4


def section(title: str) -> None:
    print()
    print("=" * 104)
    print(title)
    print("=" * 104)


def month_ord(series: pd.Series) -> pd.Series:
    return pd.PeriodIndex(series.astype(str), freq="M").asi8


def pct(x: float) -> str:
    return f"{100.0 * x:6.2f}%"


def require_columns(df: pd.DataFrame, required: list[str], name: str) -> list[str]:
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise RuntimeError(f"{name} is missing required columns: {missing}")
    return required


def load_inputs() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    missing = [
        str(path)
        for path in (CUSTOMERS_PATH, IDIO_EVENTS_PATH, CUSTOMER_STATE_PATH, RESILIENCE_PATH)
        if not path.exists()
    ]
    if missing:
        raise FileNotFoundError("Missing required files:\n  " + "\n  ".join(missing))

    customers = pd.read_csv(CUSTOMERS_PATH)
    events = pd.read_csv(IDIO_EVENTS_PATH)
    state = pd.read_csv(CUSTOMER_STATE_PATH)
    resilience = pd.read_csv(RESILIENCE_PATH)

    require_columns(customers, ["customer_id"], "customers.csv")
    require_columns(
        events,
        [
            "idio_event_id",
            "customer_id",
            "agent_type",
            "region",
            "sector",
            "event_type",
            "direction",
            "start_month",
            "end_month",
            "recovery_end_month",
            "duration_months",
            "recovery_months",
            "raw_magnitude",
            "mediated_share",
            "residual_idiosyncratic_intensity",
            "shared_stress_at_start",
            "shared_positive_at_start",
            "realized_probability",
        ],
        "external_idiosyncratic_events.csv",
    )
    require_columns(
        state,
        [
            "customer_id",
            "year_month",
            "adverse_shared_stress",
            "positive_shared_impulse",
            "idiosyncratic_state",
            "net_external_state",
        ],
        "external_customer_monthly_state.csv",
    )
    require_columns(
        resilience,
        [
            "customer_id",
            "agent_type",
            "region",
            "sector",
            "resilience_score",
            "vulnerability_score",
        ],
        "external_shock_resilience.csv",
    )

    return customers, events, state, resilience


def structural_validation(
    customers: pd.DataFrame,
    events: pd.DataFrame,
    state: pd.DataFrame,
    resilience: pd.DataFrame,
    expected_customers: int | None,
) -> dict[str, bool]:
    customer_ids = pd.Index(customers["customer_id"].dropna().unique())
    n_customers = len(customer_ids)

    checks = {
        "customer_ids_unique": customers["customer_id"].is_unique,
        "expected_customer_count": True if expected_customers is None else n_customers == expected_customers,
        "resilience_one_row_per_customer": (
            len(resilience) == n_customers and resilience["customer_id"].is_unique
        ),
        "resilience_customer_set_match": set(resilience["customer_id"]) == set(customer_ids),
        "customer_month_key_unique": not state.duplicated(["customer_id", "year_month"]).any(),
        "customer_month_row_count": len(state) == n_customers * N_MONTHS_EXPECTED,
        "customer_month_customer_set_match": set(state["customer_id"].unique()) == set(customer_ids),
        "event_id_unique": events["idio_event_id"].is_unique,
        "event_customer_fk": set(events["customer_id"].unique()).issubset(set(customer_ids)),
        "valid_direction": events["direction"].isin(["POSITIVE", "NEGATIVE"]).all(),
        "valid_probability": events["realized_probability"].between(0.0, 0.25, inclusive="both").all(),
        "valid_mediation": events["mediated_share"].between(0.02, 0.55, inclusive="both").all(),
        "valid_duration": (events["duration_months"] >= 1).all(),
        "valid_recovery": (events["recovery_months"] >= 0).all(),
        "valid_resilience": resilience["resilience_score"].between(0.0, 1.0, inclusive="both").all(),
        "valid_vulnerability": resilience["vulnerability_score"].between(0.0, 1.0, inclusive="both").all(),
    }

    if len(events):
        start = month_ord(events["start_month"])
        end = month_ord(events["end_month"])
        recovery_end = month_ord(events["recovery_end_month"])
        checks["event_chronology"] = bool(((start <= end) & (end <= recovery_end)).all())
    else:
        checks["event_chronology"] = True

    return checks


def print_structural_validation(checks: dict[str, bool]) -> None:
    section("STRUCTURAL VALIDATION")
    for name, passed in checks.items():
        print(f"  {name:<44} {'PASS' if passed else 'FAIL'}")

    failed = [name for name, passed in checks.items() if not passed]
    if failed:
        raise RuntimeError("Structural validation failed: " + ", ".join(failed))

    print()
    print("STRUCTURAL VALIDATION: PASS")


def event_type_summary(events: pd.DataFrame, n_customers: int, years: float) -> pd.DataFrame:
    if events.empty:
        return pd.DataFrame()

    g = events.groupby(["event_type", "direction"], observed=True)
    out = g.agg(
        events=("idio_event_id", "size"),
        customers_affected=("customer_id", "nunique"),
        mean_probability=("realized_probability", "mean"),
        p95_probability=("realized_probability", lambda s: s.quantile(0.95)),
        mean_raw_magnitude=("raw_magnitude", "mean"),
        mean_mediated_share=("mediated_share", "mean"),
        mean_abs_residual=(
            "residual_idiosyncratic_intensity",
            lambda s: np.abs(s).mean(),
        ),
    ).reset_index()

    out["share_of_events"] = out["events"] / len(events)
    out["affected_customer_pct"] = out["customers_affected"] / n_customers
    out["annual_events_per_100_customers"] = (
        100.0 * out["events"] / (n_customers * years)
    )

    cols = [
        "event_type",
        "direction",
        "events",
        "share_of_events",
        "customers_affected",
        "affected_customer_pct",
        "annual_events_per_100_customers",
        "mean_probability",
        "p95_probability",
        "mean_raw_magnitude",
        "mean_mediated_share",
        "mean_abs_residual",
    ]
    return out[cols].sort_values("events", ascending=False)


def print_event_type_summary(summary: pd.DataFrame) -> None:
    section("EVENT TYPE MIX")
    if summary.empty:
        print("No idiosyncratic events were generated.")
        return

    display = summary.copy()
    display["share_of_events"] = display["share_of_events"].map(lambda x: f"{100*x:6.2f}%")
    display["affected_customer_pct"] = display["affected_customer_pct"].map(lambda x: f"{100*x:6.2f}%")
    display["annual_events_per_100_customers"] = display["annual_events_per_100_customers"].map(lambda x: f"{x:6.3f}")
    display["mean_probability"] = display["mean_probability"].map(lambda x: f"{x:8.5f}")
    display["p95_probability"] = display["p95_probability"].map(lambda x: f"{x:8.5f}")
    display["mean_raw_magnitude"] = display["mean_raw_magnitude"].map(lambda x: f"{x:6.3f}")
    display["mean_mediated_share"] = display["mean_mediated_share"].map(lambda x: f"{x:6.3f}")
    display["mean_abs_residual"] = display["mean_abs_residual"].map(lambda x: f"{x:6.3f}")

    print(display.to_string(index=False))


def customer_event_distribution(
    customers: pd.DataFrame,
    events: pd.DataFrame,
) -> tuple[pd.Series, pd.DataFrame]:
    counts = events.groupby("customer_id").size().reindex(customers["customer_id"], fill_value=0)
    counts.index = customers["customer_id"].to_numpy()

    bins = pd.DataFrame(
        {
            "bucket": ["0", "1", "2", "3", "4", "5+"],
            "customers": [
                int((counts == 0).sum()),
                int((counts == 1).sum()),
                int((counts == 2).sum()),
                int((counts == 3).sum()),
                int((counts == 4).sum()),
                int((counts >= 5).sum()),
            ],
        }
    )
    bins["share"] = bins["customers"] / len(counts)
    return counts, bins


def print_customer_distribution(counts: pd.Series, bins: pd.DataFrame) -> None:
    section("CUSTOMER EVENT DISTRIBUTION")

    print(f"Customers:                         {len(counts):,}")
    print(f"Customers affected:                {(counts > 0).sum():,} ({pct((counts > 0).mean())})")
    print(f"Events per customer, mean:         {counts.mean():.4f}")
    print(f"Events per affected customer:      {counts[counts > 0].mean():.4f}")
    print(f"Median events per customer:        {counts.median():.0f}")
    print(f"P95 events per customer:           {counts.quantile(0.95):.0f}")
    print(f"P99 events per customer:           {counts.quantile(0.99):.0f}")
    print(f"Maximum events for one customer:   {counts.max():.0f}")

    print()
    print(f"{'Events':<10}{'Customers':>14}{'Share':>12}")
    for row in bins.itertuples(index=False):
        print(f"{row.bucket:<10}{row.customers:>14,}{100*row.share:>11.2f}%")


def cooldown_audit(events: pd.DataFrame) -> tuple[int, int]:
    if events.empty:
        return 0, 0

    x = events[["customer_id", "event_type", "start_month"]].copy()
    x["month_ord"] = month_ord(x["start_month"])
    x = x.sort_values(["customer_id", "event_type", "month_ord"])
    gaps = x.groupby(["customer_id", "event_type"], observed=True)["month_ord"].diff()

    violations = int((gaps < COOLDOWN_MONTHS).sum())
    repeat_pairs = int(gaps.notna().sum())
    return violations, repeat_pairs


def temporal_summary(events: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    if events.empty:
        return pd.DataFrame(), pd.DataFrame()

    monthly = (
        events.groupby("start_month", observed=True)
        .size()
        .rename("events")
        .reset_index()
        .sort_values("start_month")
    )
    monthly["year"] = monthly["start_month"].astype(str).str[:4]

    yearly = (
        monthly.groupby("year", observed=True)["events"]
        .sum()
        .reset_index()
    )
    return monthly, yearly


def print_temporal_summary(monthly: pd.DataFrame, yearly: pd.DataFrame) -> None:
    section("TEMPORAL CONCENTRATION")
    if monthly.empty:
        print("No events.")
        return

    median_month = float(monthly["events"].median())
    max_idx = monthly["events"].idxmax()
    peak_month = str(monthly.loc[max_idx, "start_month"])
    peak_events = int(monthly.loc[max_idx, "events"])
    ratio = peak_events / max(median_month, 1.0)

    print(f"Monthly event count, mean:          {monthly['events'].mean():.2f}")
    print(f"Monthly event count, median:        {median_month:.2f}")
    print(f"Monthly event count, P95:           {monthly['events'].quantile(.95):.2f}")
    print(f"Peak month:                         {peak_month}")
    print(f"Peak month event count:             {peak_events:,}")
    print(f"Peak / median month ratio:          {ratio:.3f}")

    print()
    print(yearly.to_string(index=False))


def print_agent_summary(events: pd.DataFrame, resilience: pd.DataFrame) -> None:
    section("AGENT TYPE DISTRIBUTION")

    base = (
        resilience.groupby("agent_type", observed=True)["customer_id"]
        .nunique()
        .rename("customers")
    )
    evt = (
        events.groupby("agent_type", observed=True)
        .agg(
            events=("idio_event_id", "size"),
            affected=("customer_id", "nunique"),
        )
    )
    out = pd.concat([base, evt], axis=1).fillna(0)
    out["events_per_customer_6y"] = out["events"] / out["customers"]
    out["affected_pct"] = out["affected"] / out["customers"]

    print(out.reset_index().to_string(index=False, formatters={
        "events_per_customer_6y": lambda x: f"{x:.4f}",
        "affected_pct": lambda x: f"{100*x:.2f}%",
    }))


def active_overlap_metrics(events: pd.DataFrame, state: pd.DataFrame) -> dict[str, float]:
    if events.empty:
        return {
            "customer_months_with_any_episode": 0,
            "customer_months_with_multiple_episodes": 0,
            "multi_episode_share_of_active": 0.0,
            "max_concurrent_episodes": 0,
        }

    min_month = pd.Period(state["year_month"].min(), freq="M")
    max_month = pd.Period(state["year_month"].max(), freq="M")

    chunks = []
    for e in events.itertuples(index=False):
        start = max(pd.Period(str(e.start_month), freq="M"), min_month)
        end = min(pd.Period(str(e.recovery_end_month), freq="M"), max_month)
        if end < start:
            continue
        months = pd.period_range(start, end, freq="M").astype(str)
        chunks.append(pd.DataFrame({
            "customer_id": e.customer_id,
            "year_month": months,
        }))

    if not chunks:
        return {
            "customer_months_with_any_episode": 0,
            "customer_months_with_multiple_episodes": 0,
            "multi_episode_share_of_active": 0.0,
            "max_concurrent_episodes": 0,
        }

    episodes = pd.concat(chunks, ignore_index=True)
    concurrency = episodes.groupby(["customer_id", "year_month"], observed=True).size()

    any_episode = int(len(concurrency))
    multiple = int((concurrency >= 2).sum())
    return {
        "customer_months_with_any_episode": any_episode,
        "customer_months_with_multiple_episodes": multiple,
        "multi_episode_share_of_active": multiple / max(any_episode, 1),
        "max_concurrent_episodes": int(concurrency.max()),
    }


def print_probability_mediation(events: pd.DataFrame) -> None:
    section("PROBABILITY, MAGNITUDE, AND MEDIATION")

    for col in [
        "realized_probability",
        "raw_magnitude",
        "mediated_share",
    ]:
        s = events[col].astype(float)
        print(
            f"{col:<34}"
            f"mean={s.mean():8.4f} "
            f"p50={s.quantile(.50):8.4f} "
            f"p95={s.quantile(.95):8.4f} "
            f"p99={s.quantile(.99):8.4f} "
            f"max={s.max():8.4f}"
        )

    residual = events["residual_idiosyncratic_intensity"].astype(float)
    print(
        f"{'abs_residual_intensity':<34}"
        f"mean={residual.abs().mean():8.4f} "
        f"p50={residual.abs().quantile(.50):8.4f} "
        f"p95={residual.abs().quantile(.95):8.4f} "
        f"p99={residual.abs().quantile(.99):8.4f} "
        f"max={residual.abs().max():8.4f}"
    )


def concentration_metrics(events: pd.DataFrame, counts: pd.Series) -> dict[str, float]:
    if len(events) == 0:
        return {
            "top_1pct_customer_event_share": 0.0,
            "top_5pct_customer_event_share": 0.0,
        }

    sorted_counts = counts.sort_values(ascending=False)
    n = len(sorted_counts)
    top1 = max(1, int(np.ceil(0.01 * n)))
    top5 = max(1, int(np.ceil(0.05 * n)))

    return {
        "top_1pct_customer_event_share": sorted_counts.iloc[:top1].sum() / len(events),
        "top_5pct_customer_event_share": sorted_counts.iloc[:top5].sum() / len(events),
    }


def state_saturation(state: pd.DataFrame) -> dict[str, float]:
    idio = state["idiosyncratic_state"].astype(float)
    net = state["net_external_state"].astype(float)

    return {
        "idio_at_lower_clip": float(np.isclose(idio, -4.0).mean()),
        "idio_at_upper_clip": float(np.isclose(idio, 4.0).mean()),
        "net_at_lower_clip": float(np.isclose(net, -6.0).mean()),
        "net_at_upper_clip": float(np.isclose(net, 6.0).mean()),
    }


def calibration_review(
    customers: pd.DataFrame,
    events: pd.DataFrame,
    counts: pd.Series,
    monthly: pd.DataFrame,
    overlap: dict[str, float],
    concentration: dict[str, float],
    saturation: dict[str, float],
    cooldown_violations: int,
) -> dict[str, bool]:
    n_customers = len(customers)
    affected_share = float((counts > 0).mean())
    events_per_customer = len(events) / max(n_customers, 1)
    negative_share = float((events["direction"] == "NEGATIVE").mean()) if len(events) else 0.0
    four_plus_share = float((counts >= 4).mean())

    median_month = float(monthly["events"].median()) if len(monthly) else 0.0
    peak_month = float(monthly["events"].max()) if len(monthly) else 0.0
    peak_ratio = peak_month / max(median_month, 1.0)

    return {
        # Broad six-year calibration ranges. These are review guardrails,
        # not external empirical targets.
        "affected_share_reasonable": 0.35 <= affected_share <= 0.80,
        "events_per_customer_reasonable": 0.50 <= events_per_customer <= 1.50,
        "negative_share_not_overwhelming": 0.50 <= negative_share <= 0.85,
        "high_repeat_customers_limited": four_plus_share < 0.15,
        "same_event_cooldown_respected": cooldown_violations == 0,
        "temporal_concentration_limited": peak_ratio < 2.50,
        "customer_concentration_limited": concentration["top_1pct_customer_event_share"] < 0.10,
        "episode_overlap_limited": overlap["multi_episode_share_of_active"] < 0.25,
        "idio_state_not_saturated": (
            saturation["idio_at_lower_clip"] + saturation["idio_at_upper_clip"]
        ) < 0.005,
        "net_state_not_saturated": (
            saturation["net_at_lower_clip"] + saturation["net_at_upper_clip"]
        ) < 0.005,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--expected-customers",
        type=int,
        default=None,
        help="Optional hard check for the canonical customer count.",
    )
    args = parser.parse_args()

    print("Loading External Shocks outputs...")
    customers, events, state, resilience = load_inputs()

    n_customers = customers["customer_id"].nunique()
    years = N_MONTHS_EXPECTED / 12.0

    section("BTYT EXTERNAL IDIOSYNCRATIC SHOCK AUDIT")
    print(f"Customers detected:                 {n_customers:,}")
    print(f"Customer-month rows:                {len(state):,}")
    print(f"Idiosyncratic events:               {len(events):,}")
    print(f"Expected customer-month rows:       {n_customers * N_MONTHS_EXPECTED:,}")

    checks = structural_validation(
        customers,
        events,
        state,
        resilience,
        args.expected_customers,
    )
    print_structural_validation(checks)

    summary = event_type_summary(events, n_customers, years)
    print_event_type_summary(summary)

    counts, bins = customer_event_distribution(customers, events)
    print_customer_distribution(counts, bins)

    monthly, yearly = temporal_summary(events)
    print_temporal_summary(monthly, yearly)

    print_agent_summary(events, resilience)
    print_probability_mediation(events)

    cooldown_violations, repeat_pairs = cooldown_audit(events)
    overlap = active_overlap_metrics(events, state)
    concentration = concentration_metrics(events, counts)
    saturation = state_saturation(state)

    section("DEPENDENCE, REPEAT, AND SATURATION AUDIT")
    print(f"Repeated same-type event pairs:      {repeat_pairs:,}")
    print(f"Cooldown violations (<4 months):     {cooldown_violations:,}")
    print(f"Customer-months with any episode:    {overlap['customer_months_with_any_episode']:,}")
    print(f"Customer-months with 2+ episodes:    {overlap['customer_months_with_multiple_episodes']:,}")
    print(f"2+ share of active episode months:   {pct(overlap['multi_episode_share_of_active'])}")
    print(f"Maximum concurrent episodes:         {overlap['max_concurrent_episodes']:,}")
    print(f"Top 1% customer share of events:     {pct(concentration['top_1pct_customer_event_share'])}")
    print(f"Top 5% customer share of events:     {pct(concentration['top_5pct_customer_event_share'])}")
    print(f"Idio lower-clip share:               {pct(saturation['idio_at_lower_clip'])}")
    print(f"Idio upper-clip share:               {pct(saturation['idio_at_upper_clip'])}")
    print(f"Net-state lower-clip share:          {pct(saturation['net_at_lower_clip'])}")
    print(f"Net-state upper-clip share:          {pct(saturation['net_at_upper_clip'])}")

    review = calibration_review(
        customers,
        events,
        counts,
        monthly,
        overlap,
        concentration,
        saturation,
        cooldown_violations,
    )

    section("CALIBRATION REVIEW")
    for name, passed in review.items():
        print(f"  {name:<44} {'PASS' if passed else 'REVIEW'}")

    review_items = [name for name, passed in review.items() if not passed]

    section("AUDIT RESULT")
    print("Structural integrity: PASS")
    if review_items:
        print("Calibration status:   REVIEW")
        print("Items requiring review:")
        for item in review_items:
            print(f"  - {item}")
    else:
        print("Calibration status:   PASS")

    print()
    print("No dataset was modified.")


if __name__ == "__main__":
    main()
