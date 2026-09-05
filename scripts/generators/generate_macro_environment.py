from __future__ import annotations

import argparse

import numpy as np
import pandas as pd

from scripts.core.paths import GENERATED_WORLD_DIR
from scripts.core.rng import make_rng
from scripts.core.world import load_world


# =============================================================================
# BTYT MACRO ENVIRONMENT GENERATOR
# =============================================================================
#
# Generates the shared annual macro environment consumed by downstream BTYT
# systems. This logic is intentionally extracted from the bank generator without
# changing its statistical behavior.
#
# The canonical BTYT world seed is owned by world_config.json and exposed
# through WorldConfig. This generator owns only its stochastic namespace and
# internal stream identifiers.
# =============================================================================

WORLD = load_world()

OBSERVATION_START_YEAR = WORLD.start_date.year
OBSERVATION_END_YEAR = WORLD.end_date.year
YEARS = tuple(range(OBSERVATION_START_YEAR, OBSERVATION_END_YEAR + 1))

OUTPUT_PATH = GENERATED_WORLD_DIR / "macro_environment.csv"

RNG_NAMESPACE = "macro"
RNG_STREAM_MACRO = 502

MACRO_AR_PERSISTENCE = 0.55
MACRO_INNOVATION_SD = 0.35
MACRO_CLIP = 1.50

SYSTEMIC_SHOCK_PROBABILITY = 0.14
SYSTEMIC_SHOCK_LOW = 0.40
SYSTEMIC_SHOCK_HIGH = 1.00

MACRO_COLUMNS = (
    "macro_growth_factor",
    "credit_cycle_factor",
    "usd_pressure_factor",
    "financial_stress_factor",
    "digitalization_factor",
    "cross_border_factor",
)


def build_macro_environment_dataframe(world_seed: int) -> pd.DataFrame:
    """Generate the shared annual BTYT macro environment."""
    rng = make_rng(
        world_seed=world_seed,
        namespace=RNG_NAMESPACE,
        stream=RNG_STREAM_MACRO,
    )

    states = {
        column: float(rng.normal(0.0, 0.20))
        for column in MACRO_COLUMNS
    }

    rows = []

    for year_index, year in enumerate(YEARS):
        if year_index > 0:
            for column in MACRO_COLUMNS:
                states[column] = float(
                    np.clip(
                        MACRO_AR_PERSISTENCE * states[column]
                        + rng.normal(0.0, MACRO_INNOVATION_SD),
                        -MACRO_CLIP,
                        MACRO_CLIP,
                    )
                )

        if year == OBSERVATION_START_YEAR:
            systemic_shock_flag = False
            systemic_shock = 0.0
        else:
            systemic_shock_flag = bool(
                rng.random() < SYSTEMIC_SHOCK_PROBABILITY
            )

            if systemic_shock_flag:
                sign = -1.0 if rng.random() < 0.58 else 1.0
                magnitude = rng.uniform(
                    SYSTEMIC_SHOCK_LOW,
                    SYSTEMIC_SHOCK_HIGH,
                )
                systemic_shock = float(sign * magnitude)
            else:
                systemic_shock = 0.0

        rows.append(
            {
                "year": int(year),
                **states,
                "systemic_shock": systemic_shock,
                "systemic_shock_flag": systemic_shock_flag,
                "world_seed": int(world_seed),
            }
        )

    return pd.DataFrame(rows)


def validate_macro_environment(macro_df: pd.DataFrame) -> None:
    """Validate the shared annual BTYT macro environment."""
    if set(macro_df["year"]) != set(YEARS):
        raise ValueError("Macro environment has incorrect year coverage.")

    if macro_df["year"].duplicated().any():
        raise ValueError("Duplicate year in macro environment.")

    if macro_df[list(MACRO_COLUMNS)].isna().any().any():
        raise ValueError("Missing macro factors detected.")

    if (
        macro_df[list(MACRO_COLUMNS)].abs()
        > MACRO_CLIP + 1e-10
    ).any().any():
        raise ValueError("Macro factor exceeded configured guardrail.")

    shock_consistency = (
        macro_df["systemic_shock_flag"]
        == (macro_df["systemic_shock"] != 0.0)
    )

    if not shock_consistency.all():
        raise ValueError("Systemic-shock flag/value mismatch.")

    first_year_row = macro_df.loc[
        macro_df["year"] == OBSERVATION_START_YEAR
    ].iloc[0]

    if bool(first_year_row["systemic_shock_flag"]):
        raise ValueError(
            "Macro initialization year must not contain a systemic shock."
        )


def generate_macro_environment(
    save: bool = True,
) -> pd.DataFrame:
    """Generate, validate, and optionally save the canonical macro environment."""
    macro_df = build_macro_environment_dataframe(WORLD.seed)
    validate_macro_environment(macro_df)

    if save:
        OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        macro_df.to_csv(OUTPUT_PATH, index=False)

    return macro_df


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate the shared BTYT annual macro environment."
    )
    parser.add_argument(
        "--no-save",
        action="store_true",
        help="Generate and validate without writing the production CSV.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    macro_df = generate_macro_environment(
        save=not args.no_save,
    )

    print("=" * 88)
    print("BTYT MACRO ENVIRONMENT GENERATOR")
    print("=" * 88)
    print(f"WORLD_SEED: {WORLD.seed}")
    print(f"RNG_NAMESPACE: {RNG_NAMESPACE}")
    print(f"RNG_STREAM_MACRO: {RNG_STREAM_MACRO}")
    print(f"Years: {YEARS[0]}-{YEARS[-1]}")
    print(f"Rows: {len(macro_df)}")
    print("VALIDATION: PASS")

    if not args.no_save:
        print(f"Saved: {OUTPUT_PATH} {macro_df.shape}")


if __name__ == "__main__":
    main()
