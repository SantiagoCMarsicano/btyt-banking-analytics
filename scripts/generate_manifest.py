"""BTYT final dataset manifest generator â€” V1.1.0.

Creates a cryptographic inventory of the finalized BTYT Part I dataset without
modifying any canonical or operational source dataset.

The manifest records:
- world identity and observation window;
- repository and runtime metadata;
- canonical generated datasets;
- operational datasets;
- selected audit / provenance artifacts;
- file format, size, row count, column count, and SHA-256;
- a deterministic dataset fingerprint derived from the frozen data inventory.

The dataset fingerprint intentionally excludes volatile metadata such as the
manifest creation timestamp and orchestrator run timestamp. It represents the
content identity of the inventoried BTYT dataset.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from scripts.core.paths import (
    INTERIM_AUDITS_DIR,
    MANIFESTS_DIR,
    PROJECT_ROOT,
    USING_ACTIVE_WORLD,
    WORLD_CONFIG_PATH,
    WORLD_ROOT,
)


ENGINE_VERSION = "1.1.0"

# PROJECT_ROOT remains the Git/repository execution root.
# WORLD_ROOT is the active world's isolated artifact root.
ROOT = PROJECT_ROOT
DATASET_ROOT = WORLD_ROOT

MANIFEST_DIR = MANIFESTS_DIR
MANIFEST_JSON = MANIFEST_DIR / "btyt_part_i_manifest.json"
MANIFEST_FILES_CSV = MANIFEST_DIR / "btyt_part_i_manifest_files.csv"

ORCHESTRATOR_LATEST_PATH = INTERIM_AUDITS_DIR / "orchestrator_run_latest.json"
CROSS_SYSTEM_RESULTS_PATH = INTERIM_AUDITS_DIR / "cross_system_audit_results.csv"


CANONICAL_FILES = (
    "data/generated/world/macro_environment.csv",
    "data/generated/core/banks.csv",
    "data/generated/performance/bank_market_weights.csv",
    "data/generated/performance/bank_financials.csv",
    "data/generated/performance/bank_world_parameters.csv",
    "data/generated/world/financial_institutions.csv",
    "data/generated/core/branches.csv",
    "data/generated/core/customers.parquet",
    "data/generated/core/accounts.parquet",
    "data/generated/core/cards.parquet",
    "data/generated/core/loans.parquet",
    "data/generated/credit/loan_monthly_snapshot.parquet",
    "data/generated/world/external_shocks.csv",
    "data/generated/transactions/transactions.parquet",
    "data/generated/core/account_balances.parquet",
    "data/generated/campaigns/campaigns.csv",
    "data/generated/campaigns/campaign_customers.parquet",
    "data/generated/campaigns/campaign_exposures.parquet",
    "data/generated/performance/branch_monthly_performance.parquet",
    "data/generated/performance/bank_monthly_performance.parquet",
)

OPERATIONAL_FILES = (
    "data/operational/customers.csv",
    "data/operational/accounts.csv",
    "data/operational/cards.csv",
    "data/operational/loans.csv",
    "data/operational/branches.csv",
    "data/operational/transactions.csv",
    "data/operational/campaign_customers.csv",
    "data/operational/campaign_exposures.csv",
)

PROVENANCE_FILES = (
    "data/interim/data_reliability_world.csv",
    "data/interim/data_reliability_audit.csv",
    "data/interim/operational_export_sources.csv",
    "data/interim/audits/cross_system_audit_results.csv",
    "data/interim/audits/cross_system_resolved_sources.csv",
)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def sha256_file(path: Path, chunk_size: int = 8 * 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(chunk_size)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def table_shape(path: Path) -> tuple[int | None, int | None]:
    suffix = path.suffix.lower()

    if suffix == ".parquet":
        try:
            import pyarrow.parquet as pq
            metadata = pq.ParquetFile(path).metadata
            return int(metadata.num_rows), int(metadata.num_columns)
        except Exception:
            frame = pd.read_parquet(path)
            return int(len(frame)), int(len(frame.columns))

    if suffix == ".csv":
        header = pd.read_csv(path, nrows=0)
        columns = int(len(header.columns))

        rows = 0
        with path.open("rb") as handle:
            for _ in handle:
                rows += 1

        rows = max(rows - 1, 0)
        return rows, columns

    if suffix == ".json":
        return None, None

    return None, None


def file_record(relative_path: str, role: str) -> dict[str, Any]:
    path = DATASET_ROOT / relative_path

    if not path.exists():
        raise FileNotFoundError(f"Required manifest file not found: {relative_path}")

    rows, columns = table_shape(path)

    return {
        "role": role,
        "relative_path": relative_path.replace("\\", "/"),
        "format": path.suffix.lower().lstrip("."),
        "size_bytes": int(path.stat().st_size),
        "rows": rows,
        "columns": columns,
        "sha256": sha256_file(path),
    }


def git_metadata() -> dict[str, Any]:
    result: dict[str, Any] = {
        "available": False,
        "commit": None,
        "branch": None,
        "working_tree_dirty": None,
    }

    try:
        commit = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()

        branch = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()

        status = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        ).stdout

        result.update(
            {
                "available": True,
                "commit": commit,
                "branch": branch,
                "working_tree_dirty": bool(status.strip()),
            }
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        pass

    return result


def extract_world_identity(config: dict[str, Any]) -> dict[str, Any]:
    def first_present(*keys: str) -> Any:
        for key in keys:
            if key in config:
                return config[key]
        return None

    return {
        "world_seed": first_present("world_seed", "seed", "WORLD_SEED"),
        "customer_count": first_present(
            "customer_count", "customers", "n_customers"
        ),
        "start_date": first_present(
            "start_date", "observation_start", "date_start"
        ),
        "end_date": first_present(
            "end_date", "observation_end", "date_end"
        ),
        "raw_config_sha256": sha256_file(WORLD_CONFIG_PATH),
    }


def cross_system_status() -> dict[str, Any]:
    if not CROSS_SYSTEM_RESULTS_PATH.exists():
        return {
            "available": False,
            "final_status": None,
            "failed_checks": None,
            "skipped_checks": None,
        }

    frame = pd.read_csv(CROSS_SYSTEM_RESULTS_PATH)

    status_col = next(
        (
            col for col in frame.columns
            if col.lower() in {"status", "result"}
        ),
        None,
    )

    if status_col is None:
        return {
            "available": True,
            "final_status": "UNKNOWN",
            "failed_checks": None,
            "skipped_checks": None,
        }

    statuses = frame[status_col].astype(str).str.upper()
    failed = int(statuses.eq("FAIL").sum())
    skipped = int(statuses.eq("SKIP").sum())

    return {
        "available": True,
        "final_status": "PASS" if failed == 0 else "FAIL",
        "failed_checks": failed,
        "skipped_checks": skipped,
    }


def orchestrator_status() -> dict[str, Any]:
    if not ORCHESTRATOR_LATEST_PATH.exists():
        return {
            "available": False,
            "status": None,
            "run_id": None,
            "orchestrator_version": None,
            "selected_stages": [],
        }

    payload = load_json(ORCHESTRATOR_LATEST_PATH)

    return {
        "available": True,
        "status": payload.get("status"),
        "run_id": payload.get("run_id"),
        "orchestrator_version": payload.get("orchestrator_version"),
        "selected_stages": payload.get("selected_stages", []),
    }


def dataset_fingerprint(records: list[dict[str, Any]]) -> str:
    """Build a deterministic content fingerprint from data-file hashes.

    Provenance/audit artifacts are deliberately excluded because they may
    contain run metadata while describing the same underlying frozen dataset.
    """
    identity_records = [
        {
            "role": record["role"],
            "relative_path": record["relative_path"],
            "size_bytes": record["size_bytes"],
            "rows": record["rows"],
            "columns": record["columns"],
            "sha256": record["sha256"],
        }
        for record in records
        if record["role"] in {"canonical", "operational"}
    ]

    identity_records.sort(key=lambda item: (item["role"], item["relative_path"]))

    serialized = json.dumps(
        identity_records,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")

    return hashlib.sha256(serialized).hexdigest()


def write_files_csv(records: list[dict[str, Any]]) -> None:
    MANIFEST_DIR.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(records).to_csv(MANIFEST_FILES_CSV, index=False)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create the final BTYT Part I dataset manifest."
    )
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help=(
            "Verify the current dataset against an existing manifest without "
            "rewriting it."
        ),
    )
    return parser.parse_args()


def verify_existing_manifest() -> None:
    if not USING_ACTIVE_WORLD:
        raise RuntimeError(
            "Refusing manifest verification without an active isolated BTYT world."
        )

    if not MANIFEST_JSON.exists():
        raise FileNotFoundError(
            f"Manifest does not exist: {MANIFEST_JSON}"
        )

    manifest = load_json(MANIFEST_JSON)
    expected_records = manifest.get("files", [])

    if not expected_records:
        raise ValueError("Existing manifest contains no file inventory.")

    print("=" * 100)
    print(f"BTYT FINAL DATASET MANIFEST VERIFICATION â€” V{ENGINE_VERSION}")
    print("=" * 100)

    failures = 0
    current_records: list[dict[str, Any]] = []

    for expected in expected_records:
        relative_path = expected["relative_path"]
        role = expected["role"]
        path = DATASET_ROOT / relative_path

        if not path.exists():
            failures += 1
            print(f"FAIL  {relative_path} â€” missing")
            continue

        current = file_record(relative_path, role)
        current_records.append(current)

        same_hash = current["sha256"] == expected["sha256"]
        same_size = current["size_bytes"] == expected["size_bytes"]
        same_rows = current["rows"] == expected.get("rows")
        same_columns = current["columns"] == expected.get("columns")

        ok = same_hash and same_size and same_rows and same_columns

        print(
            f"{'PASS' if ok else 'FAIL'}  {relative_path}"
        )

        if not ok:
            failures += 1
            if not same_hash:
                print("      SHA-256 changed")
            if not same_size:
                print(
                    f"      size changed: "
                    f"{expected['size_bytes']} -> {current['size_bytes']}"
                )
            if not same_rows:
                print(
                    f"      rows changed: "
                    f"{expected.get('rows')} -> {current['rows']}"
                )
            if not same_columns:
                print(
                    f"      columns changed: "
                    f"{expected.get('columns')} -> {current['columns']}"
                )

    current_fingerprint = dataset_fingerprint(current_records)
    expected_fingerprint = manifest.get("dataset_fingerprint_sha256")
    fingerprint_ok = (
        len(current_records) == len(expected_records)
        and current_fingerprint == expected_fingerprint
    )

    print("-" * 100)
    print(
        f"Dataset fingerprint: "
        f"{'PASS' if fingerprint_ok else 'FAIL'}"
    )

    if not fingerprint_ok:
        failures += 1
        print(f"Expected: {expected_fingerprint}")
        print(f"Current:  {current_fingerprint}")

    print("-" * 100)

    if failures:
        print(f"FINAL MANIFEST VERIFICATION: FAIL ({failures} issue(s))")
        raise SystemExit(1)

    print("FINAL MANIFEST VERIFICATION: PASS")
    print("The inventoried BTYT Part I dataset matches the frozen manifest.")


def generate_manifest() -> None:
    if not USING_ACTIVE_WORLD:
        raise RuntimeError(
            "Refusing to create a final manifest without an active isolated BTYT world."
        )

    if not WORLD_CONFIG_PATH.exists():
        raise FileNotFoundError(
            f"Missing world configuration: {WORLD_CONFIG_PATH}"
        )

    world_config = load_json(WORLD_CONFIG_PATH)

    records: list[dict[str, Any]] = []

    print("=" * 100)
    print(f"BTYT FINAL DATASET MANIFEST GENERATOR â€” V{ENGINE_VERSION}")
    print("=" * 100)
    print(f"Repository root: {ROOT}")
    print(f"Dataset root:    {DATASET_ROOT}")
    print()
    print("Inventorying files")
    print("-" * 100)

    groups = (
        ("canonical", CANONICAL_FILES),
        ("operational", OPERATIONAL_FILES),
        ("provenance", PROVENANCE_FILES),
    )

    for role, paths in groups:
        for relative_path in paths:
            record = file_record(relative_path, role)
            records.append(record)

            shape = (
                ""
                if record["rows"] is None
                else f" rows={record['rows']:,} cols={record['columns']}"
            )

            print(
                f"PASS  [{role:<11}] "
                f"{relative_path:<75}"
                f"{shape}"
            )

    cross_status = cross_system_status()
    orchestration = orchestrator_status()

    if cross_status["final_status"] != "PASS":
        raise RuntimeError(
            "The latest cross-system audit does not resolve to PASS. "
            "Refusing to create a final manifest."
        )

    if orchestration["available"] and orchestration["status"] != "PASS":
        raise RuntimeError(
            "The latest orchestrator run does not resolve to PASS. "
            "Refusing to create a final manifest."
        )

    fingerprint = dataset_fingerprint(records)
    created_at = utc_now_iso()

    canonical_records = [r for r in records if r["role"] == "canonical"]
    operational_records = [r for r in records if r["role"] == "operational"]
    provenance_records = [r for r in records if r["role"] == "provenance"]

    manifest = {
        "schema_version": 1,
        "manifest_generator_version": ENGINE_VERSION,
        "dataset_name": "BTYT Banking Analytics â€” Part I",
        "dataset_state": "FROZEN",
        "created_at_utc": created_at,
        "repository_root_name": PROJECT_ROOT.name,
        "world_root_name": WORLD_ROOT.name,
        "world": extract_world_identity(world_config),
        "validation": {
            "cross_system_audit": cross_status,
            "latest_orchestrator_run": orchestration,
        },
        "inventory_summary": {
            "canonical_files": len(canonical_records),
            "operational_files": len(operational_records),
            "provenance_files": len(provenance_records),
            "total_files": len(records),
            "canonical_size_bytes": sum(
                r["size_bytes"] for r in canonical_records
            ),
            "operational_size_bytes": sum(
                r["size_bytes"] for r in operational_records
            ),
            "provenance_size_bytes": sum(
                r["size_bytes"] for r in provenance_records
            ),
        },
        "runtime": {
            "python_version": sys.version,
            "python_executable": sys.executable,
            "platform": platform.platform(),
        },
        "git": git_metadata(),
        "dataset_fingerprint_sha256": fingerprint,
        "fingerprint_scope": (
            "canonical + operational files; deterministic over relative path, "
            "role, file size, table shape, and SHA-256"
        ),
        "files": records,
    }

    MANIFEST_DIR.mkdir(parents=True, exist_ok=True)

    MANIFEST_JSON.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    write_files_csv(records)

    print()
    print("=" * 100)
    print("BTYT FINAL DATASET MANIFEST â€” SUMMARY")
    print("=" * 100)
    print(f"Canonical files:   {len(canonical_records)}")
    print(f"Operational files: {len(operational_records)}")
    print(f"Provenance files:  {len(provenance_records)}")
    print(f"Total files:       {len(records)}")
    print(f"Cross-system audit:{' ' if cross_status['final_status'] else ''}{cross_status['final_status']}")
    print(f"Orchestrator:      {orchestration.get('status')}")
    print("-" * 100)
    print(f"Dataset fingerprint SHA-256:")
    print(fingerprint)
    print("-" * 100)
    print(f"Saved manifest:    {MANIFEST_JSON}")
    print(f"Saved file index:  {MANIFEST_FILES_CSV}")
    print("-" * 100)
    print(f"BTYT FINAL DATASET MANIFEST V{ENGINE_VERSION}: PASS")
    print("Dataset state recorded as FROZEN.")
    print("No inventoried source dataset was modified.")


def main() -> None:
    args = parse_args()

    if args.verify_only:
        verify_existing_manifest()
    else:
        generate_manifest()


if __name__ == "__main__":
    main()

