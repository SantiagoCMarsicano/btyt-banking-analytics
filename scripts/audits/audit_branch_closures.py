from __future__ import annotations

"""
BTYT Banking Analytics
Vectorized branch-closure Monte Carlo audit — V2.1.0

The audit evaluates the V2.1 closure model over many synthetic branch worlds
conditioned on the frozen production bank macro environment.

It uses the same structural probabilities, latent-state equations, hazard
coefficients, saturation rule, and three-closure cap as generate_branches.py,
but vectorizes the world dimension for speed.

Outputs:
    data/interim/branch_closure_mc_summary.csv
    data/interim/branch_closure_mc_world_distribution.csv
    data/interim/branch_closure_mc_group_summary.csv
    data/interim/branch_closure_mc_system.csv

All code and comments are intentionally written in English.
"""

import argparse
import importlib.util
from pathlib import Path
import sys

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
GENERATOR_PATH = ROOT / "scripts" / "generate_branches.py"
INTERIM_DIR = ROOT / "data" / "interim"

SUMMARY_OUT = INTERIM_DIR / "branch_closure_mc_summary.csv"
WORLD_DIST_OUT = INTERIM_DIR / "branch_closure_mc_world_distribution.csv"
GROUP_OUT = INTERIM_DIR / "branch_closure_mc_group_summary.csv"
SYSTEM_OUT = INTERIM_DIR / "branch_closure_mc_system.csv"

DEFAULT_WORLDS = 10_000
DEFAULT_AUDIT_SEED = 20260901


def load_generator_module():
    if not GENERATOR_PATH.exists():
        raise FileNotFoundError(f"Missing generator: {GENERATOR_PATH}")

    spec = importlib.util.spec_from_file_location(
        "btyt_generate_branches",
        GENERATOR_PATH,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load generate_branches.py.")

    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def run_vectorized_mc(generator, macro, structural, worlds, audit_seed):
    rng = np.random.default_rng(int(audit_seed))

    branch_ids = structural["branch_id"].astype(str).to_numpy()
    branch_names = structural["branch_name"].astype(str).to_numpy()
    branch_types = structural["branch_type"].astype(str).to_numpy()
    branch_sizes = structural["branch_size"].astype(str).to_numpy()
    regions = structural["region"].astype(str).to_numpy()

    n_branches = len(branch_ids)
    n_states = len(generator.STATE_COLUMNS)

    group_names = np.array(
        [generator.RISK_GROUP[x] for x in branch_ids],
        dtype=object,
    )
    structural_six = np.array(
        [
            generator.STRUCTURAL_SIX_YEAR_CLOSURE_PROB[x]
            for x in branch_ids
        ],
        dtype=float,
    )
    neutral_hazard = np.array(
        [generator.structural_annual_hazard(x) for x in branch_ids],
        dtype=float,
    )
    hazard_cap = np.array(
        [generator.MAX_ANNUAL_HAZARD[x] for x in group_names],
        dtype=float,
    )

    group_shift_map = {
        "A_CORE": -0.30,
        "B_STRATEGIC": -0.12,
        "C_STANDARD": 0.00,
        "D_VULNERABLE": 0.12,
    }
    size_shift_map = {
        "LARGE": -0.12,
        "MEDIUM": 0.00,
        "SMALL": 0.10,
    }

    initial_mean = np.array(
        [
            group_shift_map[group_names[j]]
            + size_shift_map[branch_sizes[j]]
            for j in range(n_branches)
        ],
        dtype=float,
    )

    states = rng.normal(
        loc=initial_mean[None, :, None],
        scale=0.22,
        size=(worlds, n_branches, n_states),
    )
    states = np.clip(
        states,
        -generator.STATE_CLIP,
        generator.STATE_CLIP,
    )

    agency = (branch_types == "AGENCY").astype(float)
    small = (branch_sizes == "SMALL").astype(float)
    east = (regions == "EAST").astype(float)
    metropolitan = (regions == "METROPOLITAN").astype(float)

    overlap_anchor = (
        0.20 * agency
        + 0.35 * metropolitan
        + 0.10 * small
    )

    local_shock_prob = np.full(
        n_branches,
        generator.LOCAL_SHOCK_BASE_PROB,
        dtype=float,
    )
    local_shock_prob *= np.where(
        small > 0,
        generator.LOCAL_SHOCK_SMALL_MULTIPLIER,
        1.0,
    )
    local_shock_prob *= np.where(
        agency > 0,
        generator.LOCAL_SHOCK_AGENCY_MULTIPLIER,
        1.0,
    )
    local_shock_prob *= np.where(
        east > 0,
        generator.LOCAL_SHOCK_EAST_MULTIPLIER,
        1.0,
    )
    local_shock_prob = np.clip(local_shock_prob, 0.0, 0.08)

    state_index = {
        name: i
        for i, name in enumerate(generator.STATE_COLUMNS)
    }
    pressure_weights = np.array(
        [
            generator.PRESSURE_WEIGHTS[name]
            for name in generator.STATE_COLUMNS
        ],
        dtype=float,
    )

    closed = np.zeros((worlds, n_branches), dtype=bool)
    closing_year = np.full((worlds, n_branches), np.nan, dtype=float)
    shock_at_close = np.zeros((worlds, n_branches), dtype=bool)
    pressure_at_close = np.full(
        (worlds, n_branches),
        np.nan,
        dtype=float,
    )
    closure_count = np.zeros(worlds, dtype=np.int16)

    macro_lookup = macro.set_index("year")

    for year in generator.YEARS:
        macro_row = macro_lookup.loc[int(year)]

        macro_growth = float(macro_row["macro_growth_factor"])
        credit_cycle = float(macro_row["credit_cycle_factor"])
        financial_stress = float(macro_row["financial_stress_factor"])
        digitalization = float(macro_row["digitalization_factor"])
        systemic_shock = float(macro_row["systemic_shock"])

        shock_flag = (
            rng.random((worlds, n_branches))
            < local_shock_prob[None, :]
        )
        shock_magnitude = rng.uniform(
            generator.LOCAL_SHOCK_MAG_LOW,
            generator.LOCAL_SHOCK_MAG_HIGH,
            size=(worlds, n_branches),
        )
        local_shock = np.where(
            shock_flag,
            shock_magnitude,
            0.0,
        )

        target = np.empty(
            (worlds, n_branches, n_states),
            dtype=float,
        )

        target[:, :, state_index["customer_pressure"]] = (
            -0.28 * macro_growth
            + 0.18 * financial_stress
        )
        target[:, :, state_index["deposit_pressure"]] = (
            -0.22 * macro_growth
            + 0.22 * financial_stress
        )
        target[:, :, state_index["transaction_pressure"]] = (
            -0.18 * macro_growth
            + 0.18 * financial_stress
            + 0.18 * max(digitalization, 0.0) * agency[None, :]
        )
        target[:, :, state_index["credit_pressure"]] = (
            -0.30 * credit_cycle
            + 0.25 * financial_stress
        )
        target[:, :, state_index["cost_pressure"]] = (
            0.22 * financial_stress
            + 0.10 * small[None, :]
        )
        target[:, :, state_index["digital_substitution"]] = (
            0.55
            * digitalization
            * (0.45 + 0.55 * agency[None, :])
        )
        target[:, :, state_index["network_overlap"]] = (
            overlap_anchor[None, :]
        )
        target[:, :, state_index["operational_pressure"]] = (
            0.20 * abs(systemic_shock)
            + 0.90 * local_shock
        )

        innovations = rng.normal(
            0.0,
            generator.STATE_INNOVATION_SD,
            size=(worlds, n_branches, n_states),
        )

        states = (
            generator.STATE_PERSISTENCE * states
            + (1.0 - generator.STATE_PERSISTENCE) * target
            + innovations
        )
        states = np.clip(
            states,
            -generator.STATE_CLIP,
            generator.STATE_CLIP,
        )

        pressure = np.sum(
            np.maximum(states, -1.0)
            * pressure_weights[None, None, :],
            axis=2,
        )
        pressure += (
            0.10 * max(financial_stress, -0.5)
            + 0.08 * abs(systemic_shock)
            + 0.10 * local_shock
        )
        pressure = np.clip(pressure, -1.50, 3.00)

        raw_hazard = (
            neutral_hazard[None, :]
            * np.exp(generator.HAZARD_PRESSURE_SCALE * pressure)
        )

        # Closure decisions are processed in canonical branch order so the
        # same within-year saturation logic as the production generator is
        # preserved.
        for j in range(n_branches):
            saturation = np.choose(
                np.minimum(
                    closure_count,
                    generator.MAX_WORLD_CLOSURES,
                ),
                [
                    generator.CLOSURE_SATURATION_MULTIPLIER[0],
                    generator.CLOSURE_SATURATION_MULTIPLIER[1],
                    generator.CLOSURE_SATURATION_MULTIPLIER[2],
                    generator.CLOSURE_SATURATION_MULTIPLIER[3],
                ],
            )

            hazard = (
                raw_hazard[:, j]
                * saturation
            )
            hazard = np.minimum(hazard, hazard_cap[j])
            hazard = np.where(
                closed[:, j]
                | (closure_count >= generator.MAX_WORLD_CLOSURES),
                0.0,
                hazard,
            )

            draw = rng.random(worlds)
            new_close = draw < hazard

            closed[:, j] |= new_close
            closing_year[new_close, j] = int(year)
            shock_at_close[new_close, j] = shock_flag[new_close, j]
            pressure_at_close[new_close, j] = pressure[new_close, j]
            closure_count += new_close.astype(np.int16)

    return {
        "branch_ids": branch_ids,
        "branch_names": branch_names,
        "risk_groups": group_names,
        "structural_six": structural_six,
        "closed": closed,
        "closing_year": closing_year,
        "shock_at_close": shock_at_close,
        "pressure_at_close": pressure_at_close,
        "closure_count": closure_count,
    }


def build_outputs(generator, results, worlds, audit_seed, bank_world_seed):
    branch_ids = results["branch_ids"]
    branch_names = results["branch_names"]
    risk_groups = results["risk_groups"]
    structural_six = results["structural_six"]
    closed = results["closed"]
    closing_year = results["closing_year"]
    shock_at_close = results["shock_at_close"]
    pressure_at_close = results["pressure_at_close"]
    closure_count = results["closure_count"]

    branch_rows = []
    for j, branch_id in enumerate(branch_ids):
        close_mask = closed[:, j]
        closures = int(close_mask.sum())

        branch_rows.append(
            {
                "branch_id": str(branch_id),
                "branch_name": str(branch_names[j]),
                "risk_group": str(risk_groups[j]),
                "structural_six_year_closure_prob": float(
                    structural_six[j]
                ),
                "structural_six_year_closure_prob_pct": float(
                    100.0 * structural_six[j]
                ),
                "closures": closures,
                "closure_frequency_pct": float(
                    100.0 * closures / worlds
                ),
                "mean_closing_year": (
                    float(np.nanmean(closing_year[:, j]))
                    if closures
                    else np.nan
                ),
                "local_shock_closures": int(
                    shock_at_close[:, j].sum()
                ),
                "shock_share_of_closures_pct": (
                    float(
                        100.0
                        * shock_at_close[:, j].sum()
                        / closures
                    )
                    if closures
                    else np.nan
                ),
                "mean_closure_pressure": (
                    float(np.nanmean(pressure_at_close[:, j]))
                    if closures
                    else np.nan
                ),
            }
        )

    branch_summary = pd.DataFrame(branch_rows).sort_values(
        ["closure_frequency_pct", "branch_id"],
        ascending=[False, True],
    )

    counts, frequencies = np.unique(
        closure_count,
        return_counts=True,
    )
    world_distribution = pd.DataFrame(
        {
            "closure_count": counts.astype(int),
            "worlds": frequencies.astype(int),
            "world_pct": 100.0 * frequencies / worlds,
        }
    )

    group_rows = []
    for risk_group in [
        "A_CORE",
        "B_STRATEGIC",
        "C_STANDARD",
        "D_VULNERABLE",
    ]:
        mask = risk_groups == risk_group
        group_closures = int(closed[:, mask].sum())
        branch_worlds = int(worlds * mask.sum())

        group_rows.append(
            {
                "risk_group": risk_group,
                "branches": int(mask.sum()),
                "structural_mean_six_year_prob": float(
                    structural_six[mask].mean()
                ),
                "structural_mean_six_year_prob_pct": float(
                    100.0 * structural_six[mask].mean()
                ),
                "closures": group_closures,
                "closure_frequency_pct": float(
                    100.0 * group_closures / branch_worlds
                ),
            }
        )

    group_summary = pd.DataFrame(group_rows)

    system = {
        "worlds_simulated": int(worlds),
        "audit_seed": int(audit_seed),
        "bank_world_seed": int(bank_world_seed),
        "mean_closures_per_world": float(closure_count.mean()),
        "worlds_with_zero_closures_pct": float(
            100.0 * np.mean(closure_count == 0)
        ),
        "worlds_with_one_closure_pct": float(
            100.0 * np.mean(closure_count == 1)
        ),
        "worlds_with_two_closures_pct": float(
            100.0 * np.mean(closure_count == 2)
        ),
        "worlds_with_three_closures_pct": float(
            100.0 * np.mean(closure_count == 3)
        ),
        "worlds_with_4plus_closures_pct": float(
            100.0 * np.mean(closure_count >= 4)
        ),
    }

    return branch_summary, world_distribution, group_summary, system


def validate_mc(branch_summary, group_summary, system):
    errors = []

    if float(system["worlds_with_4plus_closures_pct"]) != 0.0:
        errors.append("A world exceeded the configured three-closure cap.")

    if float(system["worlds_with_zero_closures_pct"]) < 10.0:
        errors.append("Zero-closure worlds are too rare.")

    if float(system["worlds_with_three_closures_pct"]) > 8.0:
        errors.append("Three-closure worlds are too common.")

    if not 0.35 <= float(system["mean_closures_per_world"]) <= 1.60:
        errors.append("Mean closures per world are outside broad guardrails.")

    group_rates = group_summary.set_index("risk_group")[
        "closure_frequency_pct"
    ].to_dict()
    ordered = [
        group_rates["A_CORE"],
        group_rates["B_STRATEGIC"],
        group_rates["C_STANDARD"],
        group_rates["D_VULNERABLE"],
    ]
    if not (ordered[0] < ordered[1] < ordered[2] < ordered[3]):
        errors.append("Realized closure frequencies do not preserve A < B < C < D.")

    tt = branch_summary.loc[
        branch_summary["branch_id"].eq("001")
    ].iloc[0]
    if float(tt["closure_frequency_pct"]) > 0.10:
        errors.append("Treinta y Tres closes too frequently.")

    if int(branch_summary["branch_id"].nunique()) != 37:
        errors.append("Monte Carlo summary does not contain 37 branches.")

    return errors


def main():
    parser = argparse.ArgumentParser(
        description="Audit BTYT V2.1 branch closures over many worlds."
    )
    parser.add_argument("--worlds", type=int, default=DEFAULT_WORLDS)
    parser.add_argument("--seed", type=int, default=DEFAULT_AUDIT_SEED)
    args = parser.parse_args()

    if args.worlds <= 0:
        raise ValueError("--worlds must be positive.")

    generator = load_generator_module()
    macro = generator.load_macro_environment()
    structural = generator.build_structural_branches()
    generator.validate_risk_contract(structural)

    print("=" * 104)
    print("BTYT BRANCH CLOSURE MONTE CARLO AUDIT — V2.1.0")
    print("=" * 104)
    print(f"Worlds simulated: {args.worlds:,}")
    print(f"Audit seed: {args.seed}")
    print(f"Bank macro world seed: {int(macro.iloc[0]['world_seed'])}")
    print(f"Maximum closures per world: {generator.MAX_WORLD_CLOSURES}")
    print()

    results = run_vectorized_mc(
        generator=generator,
        macro=macro,
        structural=structural,
        worlds=int(args.worlds),
        audit_seed=int(args.seed),
    )

    branch_summary, world_distribution, group_summary, system = build_outputs(
        generator=generator,
        results=results,
        worlds=int(args.worlds),
        audit_seed=int(args.seed),
        bank_world_seed=int(macro.iloc[0]["world_seed"]),
    )

    errors = validate_mc(
        branch_summary=branch_summary,
        group_summary=group_summary,
        system=system,
    )

    print("=" * 104)
    print("SYSTEM DISTRIBUTION")
    print("=" * 104)
    print(f"Mean closures per world: {system['mean_closures_per_world']:.3f}")
    print(f"0 closures: {system['worlds_with_zero_closures_pct']:.2f}%")
    print(f"1 closure : {system['worlds_with_one_closure_pct']:.2f}%")
    print(f"2 closures: {system['worlds_with_two_closures_pct']:.2f}%")
    print(f"3 closures: {system['worlds_with_three_closures_pct']:.2f}%")
    print(f"4+        : {system['worlds_with_4plus_closures_pct']:.2f}%")

    print("\nRisk groups:")
    print(
        group_summary[
            [
                "risk_group",
                "branches",
                "structural_mean_six_year_prob_pct",
                "closure_frequency_pct",
            ]
        ].to_string(
            index=False,
            float_format=lambda x: f"{x:.3f}",
        )
    )

    print("\nBranch closure frequencies:")
    print(
        branch_summary[
            [
                "branch_id",
                "branch_name",
                "risk_group",
                "structural_six_year_closure_prob_pct",
                "closure_frequency_pct",
                "mean_closing_year",
                "shock_share_of_closures_pct",
            ]
        ].to_string(
            index=False,
            float_format=lambda x: f"{x:.3f}",
        )
    )

    if errors:
        print("\nAUDIT VALIDATION: FAIL")
        for error in errors:
            print(" -", error)
    else:
        print("\nAUDIT VALIDATION: PASS")

    INTERIM_DIR.mkdir(parents=True, exist_ok=True)
    branch_summary.to_csv(SUMMARY_OUT, index=False)
    world_distribution.to_csv(WORLD_DIST_OUT, index=False)
    group_summary.to_csv(GROUP_OUT, index=False)
    pd.DataFrame([system]).to_csv(SYSTEM_OUT, index=False)

    print(f"\nSaved: {SUMMARY_OUT}")
    print(f"Saved: {WORLD_DIST_OUT}")
    print(f"Saved: {GROUP_OUT}")
    print(f"Saved: {SYSTEM_OUT}")

    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()