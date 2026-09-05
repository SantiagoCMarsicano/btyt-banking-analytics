from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Dict, Tuple

import numpy as np
import pandas as pd


# =============================================================================
# BTYT BANKING ANALYTICS — DOMESTIC MARKET WEIGHT AUDIT V4.0.0
# =============================================================================
#
# Expected project structure:
#
#   scripts/
#   ├── generate_banks.py
#   └── validation/
#       └── audit_bank_weights.py
#
# This audit imports the production V4 competitive-market logic directly from
# generate_banks.py. It does NOT duplicate the production DGP.
#
# Audits:
#   - 2021 distribution
#   - 2026 distribution
#   - leadership frequencies
#   - Top-3 frequencies
#   - gain/loss frequencies
#   - rank persistence
#   - leadership changes
#   - annual maximum gain/loss
#   - systemic-shock frequency
#   - bank-specific-shock frequency
#   - concentration
#   - 2021 initialization boundary hits
#   - basic pathology checks
#
# All data are synthetic.
# =============================================================================


# =============================================================================
# IMPORT PRODUCTION GENERATOR
# =============================================================================

SCRIPTS_DIR = Path(__file__).resolve().parents[1]

if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import scripts.generators.generate_banks as gb  # noqa: E402


# =============================================================================
# DEFAULT AUDIT CONFIGURATION
# =============================================================================

DEFAULT_N_WORLDS = 10_000
DEFAULT_AUDIT_SEED = 20260901

PROJECT_ROOT = SCRIPTS_DIR.parent
INTERIM_DIR = PROJECT_ROOT / "data" / "interim"

SUMMARY_OUTPUT = INTERIM_DIR / "bank_market_weights_audit_summary.csv"
BOUNDARY_OUTPUT = INTERIM_DIR / "bank_market_weights_audit_boundaries.csv"
WINNERS_OUTPUT = INTERIM_DIR / "bank_market_weights_audit_winners.csv"
SYSTEM_OUTPUT = INTERIM_DIR / "bank_market_weights_audit_system.csv"


# =============================================================================
# HELPERS
# =============================================================================

def build_bank_name_lookup(banks_df: pd.DataFrame) -> Dict[str, str]:
    return banks_df.set_index("bank_id")["bank_name"].to_dict()


def get_display_name(
    bank_id: str,
    year: int,
    current_name_lookup: Dict[str, str],
) -> str:
    return gb.get_temporal_bank_name(
        bank_id=bank_id,
        year=year,
        current_name=current_name_lookup[bank_id],
    )


def validate_generator_contract() -> None:
    required_attributes = [
        "DOMESTIC_SYSTEM_IDS",
        "INITIAL_MARKET_SPECS",
        "build_banks_dataframe",
        "build_world_parameters_dataframe",
        "build_macro_environment_dataframe",
        "build_market_weights_dataframe",
        "validate_banks",
        "validate_world_parameters",
        "validate_macro_environment",
        "validate_market_weights",
        "get_temporal_bank_name",
    ]

    missing = [
        attribute
        for attribute in required_attributes
        if not hasattr(gb, attribute)
    ]

    if missing:
        raise RuntimeError(
            "generate_banks.py is not compatible with this V4 audit. "
            f"Missing attributes: {missing}"
        )


def calculate_hhi(weights: pd.Series) -> float:
    return float(np.square(weights.to_numpy(dtype=float)).sum())


# =============================================================================
# AUDIT ENGINE
# =============================================================================

def run_audit(
    n_worlds: int = DEFAULT_N_WORLDS,
    audit_seed: int = DEFAULT_AUDIT_SEED,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    if n_worlds <= 0:
        raise ValueError("n_worlds must be positive.")

    validate_generator_contract()

    banks_df = gb.build_banks_dataframe()
    gb.validate_banks(banks_df)

    bank_names = build_bank_name_lookup(banks_df)
    domestic_ids = list(gb.DOMESTIC_SYSTEM_IDS)

    bank_records = []
    boundary_records = []
    winner_records = []
    system_records = []

    for world_index in range(n_worlds):
        world_seed = int(audit_seed + world_index)

        world_params_df = gb.build_world_parameters_dataframe(
            banks_df=banks_df,
            world_seed=world_seed,
        )
        gb.validate_world_parameters(
            banks_df=banks_df,
            world_df=world_params_df,
        )

        macro_df = gb.build_macro_environment_dataframe(
            world_seed=world_seed,
        )
        gb.validate_macro_environment(macro_df)

        market_df = gb.build_market_weights_dataframe(
            banks_df=banks_df,
            world_params_df=world_params_df,
            macro_df=macro_df,
            world_seed=world_seed,
        )
        gb.validate_market_weights(
            banks_df=banks_df,
            market_df=market_df,
        )

        annual = {
            int(year): group.set_index("bank_id").copy()
            for year, group in market_df.groupby("year")
        }

        first_year = min(annual)
        last_year = max(annual)

        first = annual[first_year]
        last = annual[last_year]

        first_weights = first["market_weight"]
        last_weights = last["market_weight"]

        first_ranks = first_weights.rank(
            ascending=False,
            method="min",
        )
        last_ranks = last_weights.rank(
            ascending=False,
            method="min",
        )

        first_leader = str(first_weights.idxmax())
        last_leader = str(last_weights.idxmax())

        leadership_changed = first_leader != last_leader

        systemic_shock_years = int(
            macro_df["systemic_shock_flag"].sum()
        )
        bank_shock_events = int(
            market_df["is_bank_shock"].sum()
        )

        hhi_by_year = (
            market_df.groupby("year")["market_weight"]
            .apply(calculate_hhi)
        )

        annual_max_gain = None
        annual_max_loss = None

        previous_weights = None

        for year in sorted(annual):
            year_weights = annual[year]["market_weight"]

            if previous_weights is not None:
                changes = year_weights - previous_weights

                current_gain = float(changes.max())
                current_loss = float(changes.min())

                annual_max_gain = (
                    current_gain
                    if annual_max_gain is None
                    else max(annual_max_gain, current_gain)
                )

                annual_max_loss = (
                    current_loss
                    if annual_max_loss is None
                    else min(annual_max_loss, current_loss)
                )

            previous_weights = year_weights

        system_records.append(
            {
                "world_seed": world_seed,
                "leader_2021": first_leader,
                "leader_2026": last_leader,
                "leadership_changed": leadership_changed,
                "btyt_gained": (
                    float(last_weights["B000"])
                    > float(first_weights["B000"])
                ),
                "btyt_change_2021_2026": float(
                    last_weights["B000"]
                    - first_weights["B000"]
                ),
                "systemic_shock_years": systemic_shock_years,
                "bank_shock_events": bank_shock_events,
                "mean_hhi": float(hhi_by_year.mean()),
                "hhi_2021": float(hhi_by_year.loc[first_year]),
                "hhi_2026": float(hhi_by_year.loc[last_year]),
                "largest_annual_gain": float(annual_max_gain),
                "largest_annual_loss": float(annual_max_loss),
            }
        )

        for bank_id in domestic_ids:
            weight_2021 = float(first_weights[bank_id])
            weight_2026 = float(last_weights[bank_id])
            change = weight_2026 - weight_2021

            bank_records.append(
                {
                    "world_seed": world_seed,
                    "bank_id": bank_id,
                    "bank_name_2021": get_display_name(
                        bank_id,
                        first_year,
                        bank_names,
                    ),
                    "bank_name_2026": get_display_name(
                        bank_id,
                        last_year,
                        bank_names,
                    ),
                    "weight_2021": weight_2021,
                    "weight_2026": weight_2026,
                    "change_2021_2026": change,
                    "rank_2021": int(first_ranks[bank_id]),
                    "rank_2026": int(last_ranks[bank_id]),
                    "rank_change": int(
                        first_ranks[bank_id]
                        - last_ranks[bank_id]
                    ),
                    "leader_2021": bank_id == first_leader,
                    "leader_2026": bank_id == last_leader,
                    "top3_2021": first_ranks[bank_id] <= 3,
                    "top3_2026": last_ranks[bank_id] <= 3,
                    "gained_weight": change > 0,
                    "lost_weight": change < 0,
                }
            )

            spec = gb.INITIAL_MARKET_SPECS[bank_id]
            low = float(spec["low"])
            high = float(spec["high"])

            lower_hit = np.isclose(
                weight_2021,
                low,
                atol=1e-10,
                rtol=0.0,
            )
            upper_hit = np.isclose(
                weight_2021,
                high,
                atol=1e-10,
                rtol=0.0,
            )

            boundary_records.append(
                {
                    "world_seed": world_seed,
                    "bank_id": bank_id,
                    "bank_name": bank_names[bank_id],
                    "weight_2021": weight_2021,
                    "lower_bound": low,
                    "upper_bound": high,
                    "lower_hit": bool(lower_hit),
                    "upper_hit": bool(upper_hit),
                    "any_boundary_hit": bool(
                        lower_hit or upper_hit
                    ),
                }
            )

        winner_records.append(
            {
                "world_seed": world_seed,
                "leader_2021_id": first_leader,
                "leader_2021_name": get_display_name(
                    first_leader,
                    first_year,
                    bank_names,
                ),
                "leader_2021_weight": float(
                    first_weights[first_leader]
                ),
                "leader_2026_id": last_leader,
                "leader_2026_name": get_display_name(
                    last_leader,
                    last_year,
                    bank_names,
                ),
                "leader_2026_weight": float(
                    last_weights[last_leader]
                ),
                "leadership_changed": leadership_changed,
            }
        )

        if (
            (world_index + 1) % 1_000 == 0
            or world_index + 1 == n_worlds
        ):
            print(
                f"Processed {world_index + 1:>6,}/{n_worlds:,} worlds"
            )

    bank_detail_df = pd.DataFrame(bank_records)
    boundary_detail_df = pd.DataFrame(boundary_records)
    winners_df = pd.DataFrame(winner_records)
    system_df = pd.DataFrame(system_records)

    summary_rows = []

    for bank_id in domestic_ids:
        bank = bank_detail_df.loc[
            bank_detail_df["bank_id"] == bank_id
        ].copy()

        summary_rows.append(
            {
                "bank_id": bank_id,
                "bank_name": bank_names[bank_id],
                "mean_2021": bank["weight_2021"].mean(),
                "median_2021": bank["weight_2021"].median(),
                "p05_2021": bank["weight_2021"].quantile(0.05),
                "p95_2021": bank["weight_2021"].quantile(0.95),
                "leader_pct_2021": bank["leader_2021"].mean(),
                "top3_pct_2021": bank["top3_2021"].mean(),
                "mean_2026": bank["weight_2026"].mean(),
                "median_2026": bank["weight_2026"].median(),
                "p05_2026": bank["weight_2026"].quantile(0.05),
                "p95_2026": bank["weight_2026"].quantile(0.95),
                "leader_pct_2026": bank["leader_2026"].mean(),
                "top3_pct_2026": bank["top3_2026"].mean(),
                "mean_change_2021_2026": (
                    bank["change_2021_2026"].mean()
                ),
                "median_change_2021_2026": (
                    bank["change_2021_2026"].median()
                ),
                "gain_pct_2021_2026": (
                    bank["gained_weight"].mean()
                ),
                "loss_pct_2021_2026": (
                    bank["lost_weight"].mean()
                ),
                "mean_rank_2021": bank["rank_2021"].mean(),
                "mean_rank_2026": bank["rank_2026"].mean(),
                "mean_rank_change": bank["rank_change"].mean(),
            }
        )

    summary_df = (
        pd.DataFrame(summary_rows)
        .sort_values(
            ["mean_2021", "bank_id"],
            ascending=[False, True],
        )
        .reset_index(drop=True)
    )

    boundary_rows = []

    for bank_id in domestic_ids:
        bank = boundary_detail_df.loc[
            boundary_detail_df["bank_id"] == bank_id
        ]

        boundary_rows.append(
            {
                "bank_id": bank_id,
                "bank_name": bank_names[bank_id],
                "lower_bound": float(
                    gb.INITIAL_MARKET_SPECS[bank_id]["low"]
                ),
                "upper_bound": float(
                    gb.INITIAL_MARKET_SPECS[bank_id]["high"]
                ),
                "lower_hit_pct": bank["lower_hit"].mean(),
                "upper_hit_pct": bank["upper_hit"].mean(),
                "any_boundary_hit_pct": (
                    bank["any_boundary_hit"].mean()
                ),
            }
        )

    boundary_df = pd.DataFrame(boundary_rows).sort_values(
        "any_boundary_hit_pct",
        ascending=False,
    )

    return (
        summary_df,
        boundary_df,
        winners_df,
        system_df,
    )


# =============================================================================
# AUDIT VALIDATION
# =============================================================================

def validate_audit_results(
    summary_df: pd.DataFrame,
    boundary_df: pd.DataFrame,
    winners_df: pd.DataFrame,
    system_df: pd.DataFrame,
    n_worlds: int,
) -> None:
    if len(winners_df) != n_worlds:
        raise ValueError("Winner audit does not contain one row per world.")

    if len(system_df) != n_worlds:
        raise ValueError("System audit does not contain one row per world.")

    if len(summary_df) != len(gb.DOMESTIC_SYSTEM_IDS):
        raise ValueError(
            "Summary does not contain every domestic-system bank."
        )

    if len(boundary_df) != len(gb.DOMESTIC_SYSTEM_IDS):
        raise ValueError(
            "Boundary audit does not contain every domestic-system bank."
        )

    percentage_columns = [
        "leader_pct_2021",
        "top3_pct_2021",
        "leader_pct_2026",
        "top3_pct_2026",
        "gain_pct_2021_2026",
        "loss_pct_2021_2026",
    ]

    for column in percentage_columns:
        if not summary_df[column].between(0.0, 1.0).all():
            raise ValueError(
                f"Audit percentage outside [0,1]: {column}"
            )

    boundary_percentage_columns = [
        "lower_hit_pct",
        "upper_hit_pct",
        "any_boundary_hit_pct",
    ]

    for column in boundary_percentage_columns:
        if not boundary_df[column].between(0.0, 1.0).all():
            raise ValueError(
                f"Boundary percentage outside [0,1]: {column}"
            )

    if (
        winners_df["leader_2021_id"] != "B001"
    ).any():
        raise ValueError(
            "Production contract violated: BROU was not 2021 leader "
            "in at least one world."
        )

    if not np.isclose(
        summary_df["mean_2021"].sum(),
        1.0,
        atol=1e-10,
    ):
        raise ValueError(
            "Mean 2021 competitive weights do not sum to 1."
        )

    if not np.isclose(
        summary_df["mean_2026"].sum(),
        1.0,
        atol=1e-10,
    ):
        raise ValueError(
            "Mean 2026 competitive weights do not sum to 1."
        )


# =============================================================================
# REPORTING
# =============================================================================

def print_summary(
    summary_df: pd.DataFrame,
    boundary_df: pd.DataFrame,
    winners_df: pd.DataFrame,
    system_df: pd.DataFrame,
    n_worlds: int,
    audit_seed: int,
) -> None:
    print("\n" + "=" * 104)
    print("BTYT DOMESTIC BANK WEIGHT AUDIT — V4.0.0")
    print("=" * 104)
    print(f"Worlds simulated: {n_worlds:,}")
    print(f"Audit seed: {audit_seed}")
    print(
        "Production streams: "
        f"2021={gb.RNG_STREAM_2021_MARKET}, "
        f"market_params={gb.RNG_STREAM_MARKET_PARAMS}, "
        f"macro={gb.RNG_STREAM_MACRO}, "
        f"dynamics={gb.RNG_STREAM_MARKET_DYNAMICS}"
    )

    print("\nDomestic competitive distribution:")
    print(
        f"{'Bank':<28}"
        f"{'21 Mean':>9}"
        f"{'21 P05':>9}"
        f"{'21 P95':>9}"
        f"{'21 #1':>8}"
        f"{'21 T3':>8}"
        f"{'26 Mean':>9}"
        f"{'26 P05':>9}"
        f"{'26 P95':>9}"
        f"{'26 #1':>8}"
        f"{'26 T3':>8}"
        f"{'Gain':>8}"
    )

    for row in summary_df.itertuples(index=False):
        print(
            f"{row.bank_name:<28}"
            f"{row.mean_2021:>9.2%}"
            f"{row.p05_2021:>9.2%}"
            f"{row.p95_2021:>9.2%}"
            f"{row.leader_pct_2021:>8.2%}"
            f"{row.top3_pct_2021:>8.2%}"
            f"{row.mean_2026:>9.2%}"
            f"{row.p05_2026:>9.2%}"
            f"{row.p95_2026:>9.2%}"
            f"{row.leader_pct_2026:>8.2%}"
            f"{row.top3_pct_2026:>8.2%}"
            f"{row.gain_pct_2021_2026:>8.2%}"
        )

    print("\n2021 initialization boundary hits:")
    print(
        f"{'Bank':<28}"
        f"{'Lower':>10}"
        f"{'Upper':>10}"
        f"{'Any':>10}"
    )

    for row in boundary_df.itertuples(index=False):
        print(
            f"{row.bank_name:<28}"
            f"{row.lower_hit_pct:>10.2%}"
            f"{row.upper_hit_pct:>10.2%}"
            f"{row.any_boundary_hit_pct:>10.2%}"
        )

    leader_change_pct = system_df["leadership_changed"].mean()
    btyt_gain_pct = system_df["btyt_gained"].mean()
    btyt_mean_change = system_df[
        "btyt_change_2021_2026"
    ].mean()

    print("\nSystem behavior:")
    print(
        f"Leadership changed by 2026: "
        f"{leader_change_pct:.2%}"
    )
    print(
        f"BTYT gained competitive weight by 2026: "
        f"{btyt_gain_pct:.2%}"
    )
    print(
        f"BTYT mean 2021 -> 2026 change: "
        f"{btyt_mean_change:+.2%}"
    )
    print(
        f"Average systemic-shock years per world: "
        f"{system_df['systemic_shock_years'].mean():.3f}"
    )
    print(
        f"Average bank-specific shocks per world: "
        f"{system_df['bank_shock_events'].mean():.3f}"
    )
    print(
        f"Mean HHI 2021: "
        f"{system_df['hhi_2021'].mean():.4f}"
    )
    print(
        f"Mean HHI 2026: "
        f"{system_df['hhi_2026'].mean():.4f}"
    )
    print(
        f"Mean largest annual gain: "
        f"{system_df['largest_annual_gain'].mean():+.2%}"
    )
    print(
        f"Mean largest annual loss: "
        f"{system_df['largest_annual_loss'].mean():+.2%}"
    )

    print("\n2026 leader frequencies:")
    leader_frequency = (
        winners_df["leader_2026_name"]
        .value_counts(normalize=True)
    )

    for bank_name, frequency in leader_frequency.items():
        print(
            f"  {bank_name:<28} "
            f"{frequency:>8.2%}"
        )

    print("\nAUDIT VALIDATION: PASS")


# =============================================================================
# CLI
# =============================================================================

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Audit the BTYT V4.0.0 domestic competitive-weight model."
        )
    )

    parser.add_argument(
        "--worlds",
        type=int,
        default=DEFAULT_N_WORLDS,
        help=(
            "Number of synthetic worlds to simulate. "
            f"Default: {DEFAULT_N_WORLDS}"
        ),
    )

    parser.add_argument(
        "--audit-seed",
        type=int,
        default=DEFAULT_AUDIT_SEED,
        help=(
            "First world seed used in the audit. "
            f"Default: {DEFAULT_AUDIT_SEED}"
        ),
    )

    parser.add_argument(
        "--no-save",
        action="store_true",
        help="Run the audit without writing CSV outputs.",
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    (
        summary_df,
        boundary_df,
        winners_df,
        system_df,
    ) = run_audit(
        n_worlds=args.worlds,
        audit_seed=args.audit_seed,
    )

    validate_audit_results(
        summary_df=summary_df,
        boundary_df=boundary_df,
        winners_df=winners_df,
        system_df=system_df,
        n_worlds=args.worlds,
    )

    print_summary(
        summary_df=summary_df,
        boundary_df=boundary_df,
        winners_df=winners_df,
        system_df=system_df,
        n_worlds=args.worlds,
        audit_seed=args.audit_seed,
    )

    if not args.no_save:
        INTERIM_DIR.mkdir(parents=True, exist_ok=True)

        summary_df.to_csv(
            SUMMARY_OUTPUT,
            index=False,
        )
        boundary_df.to_csv(
            BOUNDARY_OUTPUT,
            index=False,
        )
        winners_df.to_csv(
            WINNERS_OUTPUT,
            index=False,
        )
        system_df.to_csv(
            SYSTEM_OUTPUT,
            index=False,
        )

        print(f"\nSaved: {SUMMARY_OUTPUT}")
        print(f"Saved: {BOUNDARY_OUTPUT}")
        print(f"Saved: {WINNERS_OUTPUT}")
        print(f"Saved: {SYSTEM_OUTPUT}")


if __name__ == "__main__":
    main()
