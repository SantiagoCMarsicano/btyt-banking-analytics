from __future__ import annotations

import json
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]

# ---------------------------------------------------------------------
# Project-level directories
# ---------------------------------------------------------------------

CONFIG_DIR = PROJECT_ROOT / "config"
WORLDS_DIR = PROJECT_ROOT / "worlds"

WORLD_CONFIG_PATH = CONFIG_DIR / "world_config.json"
ACTIVE_WORLD_PATH = CONFIG_DIR / "active_world.json"

# ---------------------------------------------------------------------
# Legacy project-level paths
# ---------------------------------------------------------------------
#
# These remain available as a compatibility fallback when no active
# world has been selected yet.
# ---------------------------------------------------------------------

LEGACY_DATA_DIR = PROJECT_ROOT / "data"
LEGACY_DATABASE_DIR = PROJECT_ROOT / "database"
LEGACY_MANIFESTS_DIR = PROJECT_ROOT / "manifests"


def _load_json(path: Path) -> dict[str, Any]:
    """Load a JSON object from disk."""
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)

    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object in {path}")

    return payload


def _resolve_active_world() -> tuple[dict[str, Any] | None, Path | None]:
    """
    Resolve the currently active BTYT world.

    The active-world pointer is intentionally separate from world_config.json.

    Example:

        {
          "world_name": "BTYT",
          "variant": 1,
          "path": "worlds/BTYT/01"
        }

    If no active-world pointer exists, legacy project-level paths remain active.
    """
    if not ACTIVE_WORLD_PATH.exists():
        return None, None

    payload = _load_json(ACTIVE_WORLD_PATH)

    raw_path = payload.get("path")

    if not isinstance(raw_path, str) or not raw_path.strip():
        raise ValueError(
            f"Invalid active world pointer: missing non-empty 'path' in "
            f"{ACTIVE_WORLD_PATH}"
        )

    world_root = Path(raw_path)

    if not world_root.is_absolute():
        world_root = PROJECT_ROOT / world_root

    world_root = world_root.resolve()
    worlds_root = WORLDS_DIR.resolve()

    try:
        world_root.relative_to(worlds_root)
    except ValueError as exc:
        raise ValueError(
            f"Active world path must be inside {WORLDS_DIR}: {world_root}"
        ) from exc

    return payload, world_root


ACTIVE_WORLD, ACTIVE_WORLD_ROOT = _resolve_active_world()

USING_ACTIVE_WORLD = ACTIVE_WORLD_ROOT is not None

# ---------------------------------------------------------------------
# Runtime root
# ---------------------------------------------------------------------
#
# With an active world:
#
#     worlds/BTYT/01/
#
# Without an active world:
#
#     repository root (legacy compatibility mode)
# ---------------------------------------------------------------------

if USING_ACTIVE_WORLD:
    WORLD_ROOT = ACTIVE_WORLD_ROOT
    DATA_DIR = WORLD_ROOT / "data"
    DATABASE_DIR = WORLD_ROOT / "database"
    MANIFESTS_DIR = WORLD_ROOT / "manifests"
    WORLD_AUDIT_DIR = WORLD_ROOT / "audit"
else:
    WORLD_ROOT = PROJECT_ROOT
    DATA_DIR = LEGACY_DATA_DIR
    DATABASE_DIR = LEGACY_DATABASE_DIR
    MANIFESTS_DIR = LEGACY_MANIFESTS_DIR
    WORLD_AUDIT_DIR = DATA_DIR / "interim" / "audits"

# ---------------------------------------------------------------------
# Generated data
# ---------------------------------------------------------------------

GENERATED_DATA_DIR = DATA_DIR / "generated"

GENERATED_WORLD_DIR = GENERATED_DATA_DIR / "world"
GENERATED_CORE_DIR = GENERATED_DATA_DIR / "core"
GENERATED_CREDIT_DIR = GENERATED_DATA_DIR / "credit"
GENERATED_TRANSACTIONS_DIR = GENERATED_DATA_DIR / "transactions"
GENERATED_CAMPAIGNS_DIR = GENERATED_DATA_DIR / "campaigns"
GENERATED_PERFORMANCE_DIR = GENERATED_DATA_DIR / "performance"

# ---------------------------------------------------------------------
# Interim data
# ---------------------------------------------------------------------

INTERIM_DATA_DIR = DATA_DIR / "interim"

INTERIM_WORLD_DIR = INTERIM_DATA_DIR / "world"
INTERIM_TRANSACTIONS_DIR = INTERIM_DATA_DIR / "transactions"
INTERIM_CREDIT_DIR = INTERIM_DATA_DIR / "credit"
INTERIM_AUDITS_DIR = INTERIM_DATA_DIR / "audits"

# ---------------------------------------------------------------------
# Operational data
# ---------------------------------------------------------------------

OPERATIONAL_DATA_DIR = DATA_DIR / "operational"

OPERATIONAL_CORE_DIR = OPERATIONAL_DATA_DIR / "core"
OPERATIONAL_TRANSACTIONS_DIR = OPERATIONAL_DATA_DIR / "transactions"
OPERATIONAL_CREDIT_DIR = OPERATIONAL_DATA_DIR / "credit"
OPERATIONAL_CAMPAIGNS_DIR = OPERATIONAL_DATA_DIR / "campaigns"


def require_active_world() -> Path:
    """
    Return the active world root or fail explicitly.

    Use this for operations that must never run against legacy global paths,
    such as World Builder production generation.
    """
    if ACTIVE_WORLD_ROOT is None:
        raise RuntimeError(
            "No active BTYT world is configured. "
            f"Expected active-world pointer: {ACTIVE_WORLD_PATH}"
        )

    return ACTIVE_WORLD_ROOT


def ensure_runtime_directories() -> None:
    """Create the directory structure required by the active runtime."""
    directories = (
        GENERATED_WORLD_DIR,
        GENERATED_CORE_DIR,
        GENERATED_CREDIT_DIR,
        GENERATED_TRANSACTIONS_DIR,
        GENERATED_CAMPAIGNS_DIR,
        GENERATED_PERFORMANCE_DIR,
        INTERIM_WORLD_DIR,
        INTERIM_TRANSACTIONS_DIR,
        INTERIM_CREDIT_DIR,
        INTERIM_AUDITS_DIR,
        OPERATIONAL_CORE_DIR,
        OPERATIONAL_TRANSACTIONS_DIR,
        OPERATIONAL_CREDIT_DIR,
        OPERATIONAL_CAMPAIGNS_DIR,
        DATABASE_DIR,
        MANIFESTS_DIR,
        WORLD_AUDIT_DIR,
    )

    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)