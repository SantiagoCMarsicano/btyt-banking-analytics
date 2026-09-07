#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""BTYT full-project orchestrator — V1.0.0.

Dependency-aware orchestration for the canonical BTYT Part I synthetic banking
universe.

Design principles
-----------------
- Use the repository's real module layout under scripts/generators and
  scripts/audits.
- Execute every stage in a fresh Python subprocess.
- Preserve each generator's own validation and RNG contract.
- Fail fast by default.
- Never silently skip a missing required module.
- Allow bounded partial runs for development and recovery.
- Finish with the final cross-system audit.
- Write orchestration metadata separately from the future dataset manifest.

This orchestrator does not implement business logic. It coordinates already
validated generators and audits in dependency order.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


ENGINE_VERSION = "1.0.0"

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
GENERATORS_DIR = SCRIPTS_DIR / "generators"
AUDITS_DIR = SCRIPTS_DIR / "audits"

DATA_DIR = ROOT / "data"
GENERATED_DIR = DATA_DIR / "generated"
INTERIM_DIR = DATA_DIR / "interim"
INTERIM_AUDITS_DIR = INTERIM_DIR / "audits"

LATEST_RUN_PATH = INTERIM_AUDITS_DIR / "orchestrator_run_latest.json"


@dataclass(frozen=True)
class Stage:
    key: str
    label: str
    module: str
    module_path: Path
    category: str
    required: bool = True


@dataclass
class StageResult:
    key: str
    label: str
    module: str
    category: str
    status: str
    returncode: int | None
    started_at_utc: str | None
    finished_at_utc: str | None
    elapsed_seconds: float
    command: list[str]
    reason: str = ""


STAGES: tuple[Stage, ...] = (
    Stage(
        key="macro",
        label="Macro environment",
        module="scripts.generators.generate_macro_environment",
        module_path=GENERATORS_DIR / "generate_macro_environment.py",
        category="generator",
    ),
    Stage(
        key="banks",
        label="Banks and banking market",
        module="scripts.generators.generate_banks",
        module_path=GENERATORS_DIR / "generate_banks.py",
        category="generator",
    ),
    Stage(
        key="financial_institutions",
        label="Financial institutions",
        module="scripts.generators.generate_financial_institutions",
        module_path=GENERATORS_DIR / "generate_financial_institutions.py",
        category="generator",
    ),
    Stage(
        key="branches",
        label="Branch network",
        module="scripts.generators.generate_branches",
        module_path=GENERATORS_DIR / "generate_branches.py",
        category="generator",
    ),
    Stage(
        key="customers",
        label="Customers",
        module="scripts.generators.generate_customers",
        module_path=GENERATORS_DIR / "generate_customers.py",
        category="generator",
    ),
    Stage(
        key="accounts",
        label="Accounts",
        module="scripts.generators.generate_accounts",
        module_path=GENERATORS_DIR / "generate_accounts.py",
        category="generator",
    ),
    Stage(
        key="cards",
        label="Cards",
        module="scripts.generators.generate_cards",
        module_path=GENERATORS_DIR / "generate_cards.py",
        category="generator",
    ),
    Stage(
        key="loans",
        label="Loans",
        module="scripts.generators.generate_loans",
        module_path=GENERATORS_DIR / "generate_loans.py",
        category="generator",
    ),
    Stage(
        key="loan_snapshot",
        label="Loan monthly snapshot",
        module="scripts.generators.generate_loan_monthly_snapshot",
        module_path=GENERATORS_DIR / "generate_loan_monthly_snapshot.py",
        category="generator",
    ),
    Stage(
        key="external_shocks",
        label="External shocks",
        module="scripts.generators.generate_external_shocks",
        module_path=GENERATORS_DIR / "generate_external_shocks.py",
        category="generator",
    ),
    Stage(
        key="transactions",
        label="Transactions and account balances",
        module="scripts.generators.generate_transactions",
        module_path=GENERATORS_DIR / "generate_transactions.py",
        category="generator",
    ),
    Stage(
        key="campaigns",
        label="Campaign behavior",
        module="scripts.generators.generate_campaigns",
        module_path=GENERATORS_DIR / "generate_campaigns.py",
        category="generator",
    ),
    Stage(
        key="branch_performance",
        label="Branch and bank performance",
        module="scripts.generators.generate_branch_performance",
        module_path=GENERATORS_DIR / "generate_branch_performance.py",
        category="generator",
    ),
    Stage(
        key="operational_exports",
        label="Operational data reliability",
        module="scripts.generators.generate_operational_exports",
        module_path=GENERATORS_DIR / "generate_operational_exports.py",
        category="generator",
    ),
    Stage(
        key="cross_system_audit",
        label="Final cross-system audit",
        module="scripts.audits.audit_cross_system",
        module_path=AUDITS_DIR / "audit_cross_system.py",
        category="audit",
    ),
)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def run_id_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run the BTYT Part I generation pipeline in dependency order and "
            "finish with the final cross-system audit."
        )
    )

    parser.add_argument(
        "--check-only",
        action="store_true",
        help=(
            "Validate repository structure and stage availability without "
            "executing any generator or audit."
        ),
    )
    parser.add_argument(
        "--list-stages",
        action="store_true",
        help="Print the ordered pipeline stages and exit.",
    )
    parser.add_argument(
        "--from-stage",
        choices=[stage.key for stage in STAGES],
        help="Start execution at this stage, inclusive.",
    )
    parser.add_argument(
        "--to-stage",
        choices=[stage.key for stage in STAGES],
        help="Stop execution at this stage, inclusive.",
    )
    parser.add_argument(
        "--only",
        choices=[stage.key for stage in STAGES],
        help="Run exactly one stage.",
    )
    parser.add_argument(
        "--skip",
        action="append",
        default=[],
        choices=[stage.key for stage in STAGES],
        help=(
            "Skip a stage explicitly. May be supplied more than once. "
            "Use only when upstream outputs are already known to be valid."
        ),
    )
    parser.add_argument(
        "--continue-on-error",
        action="store_true",
        help=(
            "Continue after a failed stage. Default behavior is fail-fast and "
            "is recommended for production."
        ),
    )
    parser.add_argument(
        "--no-run-record",
        action="store_true",
        help="Do not write orchestrator JSON run metadata.",
    )

    return parser.parse_args()


def validate_repo_structure() -> list[str]:
    errors: list[str] = []

    if not (ROOT / "config" / "world_config.json").exists():
        errors.append("Missing config/world_config.json")

    if not SCRIPTS_DIR.exists():
        errors.append("Missing scripts/ directory")

    if not GENERATORS_DIR.exists():
        errors.append("Missing scripts/generators/ directory")

    if not AUDITS_DIR.exists():
        errors.append("Missing scripts/audits/ directory")

    core_dir = SCRIPTS_DIR / "core"
    for core_file in ("config.py", "paths.py", "rng.py", "world.py"):
        path = core_dir / core_file
        if not path.exists():
            errors.append(f"Missing core architecture file: {path.relative_to(ROOT)}")

    for stage in STAGES:
        if stage.required and not stage.module_path.exists():
            errors.append(
                f"Missing required stage module: "
                f"{stage.module_path.relative_to(ROOT)}"
            )

    return errors


def print_stage_table(stages: Iterable[Stage] = STAGES) -> None:
    print()
    print("Pipeline stages")
    print("-" * 100)
    print(f"{'#':>3}  {'key':<24} {'category':<10} {'module'}")
    print("-" * 100)

    stage_positions = {stage.key: i for i, stage in enumerate(STAGES, start=1)}
    for stage in stages:
        print(
            f"{stage_positions[stage.key]:>3}  "
            f"{stage.key:<24} "
            f"{stage.category:<10} "
            f"{stage.module}"
        )


def select_stages(args: argparse.Namespace) -> list[Stage]:
    if args.only:
        selected = [stage for stage in STAGES if stage.key == args.only]
    else:
        start_idx = 0
        end_idx = len(STAGES) - 1

        if args.from_stage:
            start_idx = next(
                i for i, stage in enumerate(STAGES)
                if stage.key == args.from_stage
            )

        if args.to_stage:
            end_idx = next(
                i for i, stage in enumerate(STAGES)
                if stage.key == args.to_stage
            )

        if start_idx > end_idx:
            raise ValueError(
                "--from-stage occurs after --to-stage in dependency order."
            )

        selected = list(STAGES[start_idx : end_idx + 1])

    skip_set = set(args.skip)
    return [stage for stage in selected if stage.key not in skip_set]


def command_for_stage(stage: Stage) -> list[str]:
    return [sys.executable, "-m", stage.module]


def write_run_record(
    run_id: str,
    status: str,
    args: argparse.Namespace,
    selected_stages: list[Stage],
    results: list[StageResult],
    started_at_utc: str,
    finished_at_utc: str,
    elapsed_seconds: float,
) -> Path:
    INTERIM_AUDITS_DIR.mkdir(parents=True, exist_ok=True)

    output_path = INTERIM_AUDITS_DIR / f"orchestrator_run_{run_id}.json"

    payload = {
        "schema_version": 1,
        "orchestrator_version": ENGINE_VERSION,
        "run_id": run_id,
        "status": status,
        "root": str(ROOT),
        "python_executable": sys.executable,
        "python_version": sys.version,
        "platform": sys.platform,
        "started_at_utc": started_at_utc,
        "finished_at_utc": finished_at_utc,
        "elapsed_seconds": round(elapsed_seconds, 3),
        "arguments": {
            "check_only": args.check_only,
            "list_stages": args.list_stages,
            "from_stage": args.from_stage,
            "to_stage": args.to_stage,
            "only": args.only,
            "skip": list(args.skip),
            "continue_on_error": args.continue_on_error,
        },
        "selected_stages": [stage.key for stage in selected_stages],
        "stage_results": [asdict(result) for result in results],
    }

    serialized = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    output_path.write_text(serialized, encoding="utf-8")
    LATEST_RUN_PATH.write_text(serialized, encoding="utf-8")

    return output_path


def run_stage(stage: Stage, index: int, total: int) -> StageResult:
    command = command_for_stage(stage)
    started_at = utc_now_iso()
    start = time.perf_counter()

    print()
    print("=" * 100)
    print(
        f"STAGE {index}/{total} — {stage.label} "
        f"[{stage.key}]"
    )
    print("=" * 100)
    print(f"Module:  {stage.module}")
    print(f"Command: {' '.join(command)}")
    print(f"Start:   {started_at}")
    print("-" * 100)
    sys.stdout.flush()

    completed = subprocess.run(
        command,
        cwd=ROOT,
        env=os.environ.copy(),
        check=False,
    )

    elapsed = time.perf_counter() - start
    finished_at = utc_now_iso()

    status = "PASS" if completed.returncode == 0 else "FAIL"

    print("-" * 100)
    print(
        f"STAGE {index}/{total} {status} — "
        f"{stage.label} | elapsed={elapsed:,.1f}s | "
        f"returncode={completed.returncode}"
    )

    return StageResult(
        key=stage.key,
        label=stage.label,
        module=stage.module,
        category=stage.category,
        status=status,
        returncode=completed.returncode,
        started_at_utc=started_at,
        finished_at_utc=finished_at,
        elapsed_seconds=round(elapsed, 3),
        command=command,
    )


def main() -> None:
    args = parse_args()

    print("=" * 100)
    print(f"BTYT FULL-PROJECT ORCHESTRATOR — V{ENGINE_VERSION}")
    print("=" * 100)
    print(f"Root:              {ROOT}")
    print(f"Python executable: {sys.executable}")
    print("Execution model:   fresh subprocess per stage")
    print("Failure policy:    " + (
        "continue on error"
        if args.continue_on_error
        else "fail fast"
    ))

    if args.list_stages:
        print_stage_table()
        return

    structure_errors = validate_repo_structure()

    print()
    print("Repository preflight")
    print("-" * 100)

    if structure_errors:
        for error in structure_errors:
            print(f"FAIL  {error}")
        print("-" * 100)
        print(
            f"REPOSITORY PREFLIGHT: FAIL "
            f"({len(structure_errors)} issue(s))"
        )
        raise SystemExit(1)

    print("Core architecture files                             PASS")
    print("Generator module locations                          PASS")
    print("Audit module locations                              PASS")
    print("world_config.json                                    PASS")
    print("REPOSITORY PREFLIGHT: PASS")

    try:
        selected_stages = select_stages(args)
    except ValueError as exc:
        print(f"\nSelection error: {exc}")
        raise SystemExit(2) from exc

    if not selected_stages:
        print("\nNo stages selected after applying filters.")
        raise SystemExit(2)

    print_stage_table(selected_stages)

    if args.check_only:
        print()
        print("=" * 100)
        print("BTYT ORCHESTRATOR CHECK-ONLY: PASS")
        print("=" * 100)
        print("No generator or audit was executed.")
        return

    run_id = run_id_now()
    run_started_at = utc_now_iso()
    run_start = time.perf_counter()
    results: list[StageResult] = []

    final_status = "PASS"

    for index, stage in enumerate(selected_stages, start=1):
        result = run_stage(
            stage=stage,
            index=index,
            total=len(selected_stages),
        )
        results.append(result)

        if result.status == "FAIL":
            final_status = "FAIL"

            if not args.continue_on_error:
                print()
                print("=" * 100)
                print("BTYT ORCHESTRATOR: FAIL-FAST STOP")
                print("=" * 100)
                print(f"Failed stage: {stage.key}")
                print(f"Module:       {stage.module}")
                print(f"Return code:  {result.returncode}")
                break

    run_elapsed = time.perf_counter() - run_start
    run_finished_at = utc_now_iso()

    if any(result.status == "FAIL" for result in results):
        final_status = "FAIL"

    not_run_count = len(selected_stages) - len(results)
    if not_run_count > 0:
        final_status = "FAIL"

    record_path: Path | None = None
    if not args.no_run_record:
        record_path = write_run_record(
            run_id=run_id,
            status=final_status,
            args=args,
            selected_stages=selected_stages,
            results=results,
            started_at_utc=run_started_at,
            finished_at_utc=run_finished_at,
            elapsed_seconds=run_elapsed,
        )

    print()
    print("=" * 100)
    print("BTYT FULL-PROJECT ORCHESTRATOR — SUMMARY")
    print("=" * 100)

    result_map = {result.key: result for result in results}

    for stage in selected_stages:
        result = result_map.get(stage.key)
        if result is None:
            label = "NOT RUN"
            elapsed = ""
        else:
            label = result.status
            elapsed = f"{result.elapsed_seconds:,.1f}s"

        print(f"{stage.key:<28} {label:<8} {elapsed:>12}")

    print("-" * 100)
    print(f"Stages selected: {len(selected_stages)}")
    print(f"Stages executed: {len(results)}")
    print(f"Elapsed:         {run_elapsed:,.1f}s")

    if record_path is not None:
        print(f"Run record:      {record_path}")
        print(f"Latest record:   {LATEST_RUN_PATH}")

    print("-" * 100)
    print(f"FINAL ORCHESTRATION: {final_status}")

    if final_status != "PASS":
        raise SystemExit(1)

    print()
    print(f"BTYT FULL-PROJECT ORCHESTRATOR V{ENGINE_VERSION}: PASS")
    print("All selected stages completed successfully.")


if __name__ == "__main__":
    main()
