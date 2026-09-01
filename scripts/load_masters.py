from __future__ import annotations

from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
MASTER_DATA_DIR = ROOT / "data" / "master"

PRODUCTS_PATH = MASTER_DATA_DIR / "products.csv"
CAMPAIGNS_PATH = MASTER_DATA_DIR / "campaigns.csv"
CAMPAIGN_CHANNELS_PATH = MASTER_DATA_DIR / "campaign_channels.csv"
CAMPAIGN_GEOGRAPHY_PATH = MASTER_DATA_DIR / "campaign_geography.csv"


def _read_required_csv(path: Path, **kwargs) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Missing BTYT master file: {path}")
    return pd.read_csv(path, **kwargs)


def load_masters() -> dict[str, pd.DataFrame]:
    """Load the controlled BTYT master/reference tables."""
    return {
        "products": _read_required_csv(PRODUCTS_PATH, dtype={"product_id": str}),
        "campaigns": _read_required_csv(CAMPAIGNS_PATH, dtype={"campaign_id": str, "target_product_id": str}),
        "campaign_channels": _read_required_csv(CAMPAIGN_CHANNELS_PATH, dtype={"campaign_id": str}),
        "campaign_geography": _read_required_csv(CAMPAIGN_GEOGRAPHY_PATH, dtype={"campaign_id": str}),
    }


if __name__ == "__main__":
    masters = load_masters()

    print("BTYT master tables loaded:")
    for name, frame in masters.items():
        print(f"  {name}: {len(frame):,} rows")
