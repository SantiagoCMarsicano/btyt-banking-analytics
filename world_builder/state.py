from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = PROJECT_ROOT / "config"
WORLDS_ROOT = PROJECT_ROOT / "worlds"
REFERENCE_ROOT = PROJECT_ROOT / "resources" / "reference"

ACTIVE_CONFIG_PATH = CONFIG_DIR / "world_config.json"
ACTIVE_WORLD_PATH = CONFIG_DIR / "active_world.json"
WORLD_REGISTRY_PATH = WORLDS_ROOT / "registry.json"

STAGES = [
    ("macro", "Macro"),
    ("banks", "Banks"),
    ("financial_institutions", "Financial Institutions"),
    ("branches", "Branches"),
    ("customers", "Customers"),
    ("accounts", "Accounts"),
    ("cards", "Cards"),
    ("loans", "Loans"),
    ("loan_snapshot", "Loan Snapshot"),
    ("external_shocks", "External Shocks"),
    ("transactions", "Transactions"),
    ("campaigns", "Campaigns"),
    ("branch_performance", "Branch Performance"),
    ("operational_exports", "Operational Exports"),
    ("cross_system_audit", "Cross-System Audit"),
]

STAGE_KEYS = [key for key, _ in STAGES]
STAGE_LABELS = dict(STAGES)

# Workload weights are used only for UX progress. They do not alter generation.
# The weights intentionally give long stages more visual space while preserving
# a deterministic 0-100% world-progress scale.
STAGE_WORK_WEIGHTS = {
    "macro": 1.0,
    "banks": 1.5,
    "financial_institutions": 1.0,
    "branches": 1.5,
    "customers": 4.0,
    "accounts": 4.0,
    "cards": 3.0,
    "loans": 5.0,
    "loan_snapshot": 5.0,
    "external_shocks": 2.0,
    "transactions": 14.0,
    "campaigns": 2.5,
    "branch_performance": 2.0,
    "operational_exports": 2.0,
    "cross_system_audit": 3.0,
}

GENERATION_SHARE = 0.92
MANIFEST_SHARE = 0.04
VERIFY_SHARE = 0.04

REFERENCE_ASSETS = (
    (REFERENCE_ROOT / "products.csv", Path("data/generated/core/products.csv")),
    (REFERENCE_ROOT / "campaigns" / "campaigns.csv", Path("data/generated/campaigns/campaigns.csv")),
    (REFERENCE_ROOT / "campaigns" / "campaign_channels.csv", Path("data/generated/campaigns/campaign_channels.csv")),
    (REFERENCE_ROOT / "campaigns" / "campaign_geography.csv", Path("data/generated/campaigns/campaign_geography.csv")),
)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def normalize_world_name(name: str) -> str:
    return " ".join(name.strip().upper().split())


def world_slug(name: str) -> str:
    normalized = normalize_world_name(name)
    safe = "".join(ch if ch.isalnum() else "_" for ch in normalized)
    return "_".join(part for part in safe.split("_") if part) or "WORLD"


def derive_world_seed(name: str, variant: int) -> int:
    identity = f"{normalize_world_name(name)}::{variant}"
    digest = hashlib.sha256(identity.encode("utf-8")).digest()
    return int.from_bytes(digest[:4], byteorder="big", signed=False)


def make_world_id(name: str, variant: int, seed: int) -> str:
    return f"{world_slug(name)}-{variant:02d}-{seed}"


def load_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def has_files(path: Path) -> bool:
    return path.exists() and any(item.is_file() for item in path.rglob("*"))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def world_root_for(name: str, variant: int) -> Path:
    return WORLDS_ROOT / world_slug(name) / f"{variant:02d}"


def materialize_reference_assets(world_root: Path) -> list[Path]:
    materialized: list[Path] = []
    for source, relative_destination in REFERENCE_ASSETS:
        if not source.is_file():
            raise FileNotFoundError(f"Canonical reference asset not found: {source}")

        destination = world_root / relative_destination
        destination.parent.mkdir(parents=True, exist_ok=True)

        if destination.exists():
            if not destination.is_file():
                raise RuntimeError(f"Reference asset destination is not a file: {destination}")
            if sha256_file(source) != sha256_file(destination):
                raise RuntimeError(
                    "Reference asset conflict detected. "
                    f"World file differs from canonical source: {destination}"
                )
            continue

        import shutil
        shutil.copy2(source, destination)
        materialized.append(destination)

    return materialized


@dataclass
class ReconstructedWorldState:
    completed_stages: set[str] = field(default_factory=set)
    latest_status: str = "READY"
    manifest_pass: bool = False
    verification_pass: bool = False
    frozen: bool = False
    fingerprint: str | None = None
    latest_run_id: str | None = None

    @property
    def first_incomplete_stage(self) -> str | None:
        for key in STAGE_KEYS:
            if key not in self.completed_stages:
                return key
        return None


def _read_manifest_state(world_root: Path) -> tuple[bool, bool, str | None]:
    manifest_path = world_root / "manifests" / "dataset_manifest.json"
    if not manifest_path.exists():
        return False, False, None

    try:
        payload = load_json(manifest_path, {}) or {}
    except Exception:
        return False, False, None

    fingerprint = payload.get("dataset_fingerprint_sha256")
    return True, False, str(fingerprint) if fingerprint else None


def reconstruct_world_state(world_root: Path) -> ReconstructedWorldState:
    state = ReconstructedWorldState()
    metadata = load_json(world_root / "metadata.json", {}) or {}

    builder_state = metadata.get("builder_state", {})
    if isinstance(builder_state, dict):
        completed = builder_state.get("completed_stages", [])
        if isinstance(completed, list):
            state.completed_stages.update(
                key for key in completed if key in STAGE_KEYS
            )
        state.manifest_pass = bool(builder_state.get("manifest_pass", False))
        state.verification_pass = bool(builder_state.get("verification_pass", False))
        state.frozen = bool(builder_state.get("frozen", False))
        fp = builder_state.get("fingerprint")
        if fp:
            state.fingerprint = str(fp)

    audits_dir = world_root / "data" / "interim" / "audits"
    if audits_dir.exists():
        run_files = sorted(audits_dir.glob("orchestrator_run_*.json"))
        for path in run_files:
            if path.name.endswith("latest.json"):
                continue
            try:
                payload = load_json(path, {}) or {}
            except Exception:
                continue

            for result in payload.get("stage_results", []) or []:
                if not isinstance(result, dict):
                    continue
                key = result.get("key")
                if key in STAGE_KEYS and str(result.get("status", "")).upper() == "PASS":
                    state.completed_stages.add(key)

            if payload.get("run_id"):
                state.latest_run_id = str(payload["run_id"])
            if payload.get("status"):
                state.latest_status = str(payload["status"])

    latest_path = audits_dir / "orchestrator_run_latest.json"
    if latest_path.exists():
        try:
            latest = load_json(latest_path, {}) or {}
            if latest.get("status"):
                state.latest_status = str(latest["status"])
            if latest.get("run_id"):
                state.latest_run_id = str(latest["run_id"])
        except Exception:
            pass

    manifest_exists, _, fingerprint = _read_manifest_state(world_root)
    state.manifest_pass = state.manifest_pass or manifest_exists
    state.fingerprint = state.fingerprint or fingerprint

    # Verification is intentionally Builder-owned: a manifest existing is not
    # enough to claim a verified/frozen world.
    if str(metadata.get("status", "")).upper() == "FROZEN":
        state.verification_pass = True
        state.frozen = True

    if state.frozen:
        state.latest_status = "FROZEN"
    elif state.verification_pass:
        state.latest_status = "VERIFIED"
    elif state.manifest_pass:
        state.latest_status = "MANIFESTED"
    elif "cross_system_audit" in state.completed_stages:
        state.latest_status = "AUDITED"
    elif state.completed_stages:
        state.latest_status = str(metadata.get("status", "PARTIAL_COMPLETE"))
    else:
        state.latest_status = str(metadata.get("status", state.latest_status))

    return state


def persist_builder_state(world_root: Path, state: ReconstructedWorldState) -> None:
    metadata_path = world_root / "metadata.json"
    metadata = load_json(metadata_path, {}) or {}
    metadata["builder_state"] = {
        "completed_stages": [key for key in STAGE_KEYS if key in state.completed_stages],
        "manifest_pass": state.manifest_pass,
        "verification_pass": state.verification_pass,
        "frozen": state.frozen,
        "fingerprint": state.fingerprint,
        "updated_at_utc": utc_now_iso(),
    }
    write_json(metadata_path, metadata)


def world_progress(
    stage_progress: dict[str, float],
    manifest_pass: bool,
    verification_pass: bool,
) -> float:
    total_weight = sum(STAGE_WORK_WEIGHTS.values())
    completed_weight = 0.0
    for key in STAGE_KEYS:
        completed_weight += STAGE_WORK_WEIGHTS[key] * max(
            0.0, min(float(stage_progress.get(key, 0.0)), 1.0)
        )

    generation_fraction = completed_weight / total_weight if total_weight else 0.0
    value = GENERATION_SHARE * generation_fraction
    if manifest_pass:
        value += MANIFEST_SHARE
    if verification_pass:
        value += VERIFY_SHARE
    return max(0.0, min(value, 1.0))
