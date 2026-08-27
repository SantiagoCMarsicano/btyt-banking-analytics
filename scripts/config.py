from pathlib import Path


# Reproducibility
RANDOM_SEED = 332026

# Development settings
DEVELOPMENT_CUSTOMERS = 500

# Analytical period
START_DATE = "2021-01-01"
END_DATE = "2026-12-31"

# Project paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_DATA_DIR = PROJECT_ROOT / "data" / "raw"
PROCESSED_DATA_DIR = PROJECT_ROOT / "data" / "processed"
DATABASE_DIR = PROJECT_ROOT / "database"

