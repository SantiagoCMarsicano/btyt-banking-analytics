"""Load the canonical BTYT generated world into PostgreSQL.

This loader intentionally separates the physical folder structure from the
logical PostgreSQL architecture. PostgreSQL schemas are assigned through an
explicit table-to-schema mapping.

Logical schemas:
    core
    banking
    marketing
    market
    reference

Run from the repository root with:
    python scripts/database/load_postgresql.py
"""

from __future__ import annotations

import getpass
import os
import re
from pathlib import Path
from typing import Iterator

import pandas as pd
import pyarrow.parquet as pq
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine, URL


# -----------------------------------------------------------------------------
# Project paths
# -----------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_ROOT = REPO_ROOT / "worlds" / "BTYT" / "01" / "data" / "generated"


# -----------------------------------------------------------------------------
# PostgreSQL connection
# -----------------------------------------------------------------------------

DB_HOST = os.getenv("BTYT_DB_HOST", "localhost")
DB_PORT = int(os.getenv("BTYT_DB_PORT", "5432"))
DB_NAME = os.getenv("BTYT_DB_NAME", "BTYT")
DB_USER = os.getenv("BTYT_DB_USER", "postgres")
DB_PASSWORD = os.getenv("BTYT_DB_PASSWORD")


# -----------------------------------------------------------------------------
# Loading configuration
# -----------------------------------------------------------------------------

CSV_CHUNK_SIZE = 50_000
PARQUET_BATCH_SIZE = 100_000
SQL_CHUNK_SIZE = 1_000

SUPPORTED_EXTENSIONS = {".csv", ".parquet"}


# -----------------------------------------------------------------------------
# Logical PostgreSQL architecture
# -----------------------------------------------------------------------------

TABLE_SCHEMA_MAP: dict[str, str] = {
    # Core banking entities
    "branches": "core",
    "customers": "core",
    "accounts": "core",
    "products": "core",

    # Banking operations
    "cards": "banking",
    "loans": "banking",
    "transactions": "banking",
    "account_balances": "banking",
    "loan_monthly_snapshot": "banking",

    # Marketing and commercial response
    "campaigns": "marketing",
    "campaign_customers": "marketing",
    "campaign_exposures": "marketing",

    # Competitive, financial and macro environment
    "banks": "market",
    "bank_financials": "market",
    "bank_market_weights": "market",
    "bank_monthly_performance": "market",
    "bank_world_parameters": "market",
    "branch_monthly_performance": "market",
    "financial_institutions": "market",
    "macro_environment": "market",
    "external_shocks": "market",

    # Reference / auxiliary dimensions
    "campaign_channels": "reference",
    "campaign_geography": "reference",
}

EXPECTED_TABLES = set(TABLE_SCHEMA_MAP)


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------


def quote_identifier(value: str) -> str:
    """Safely quote a PostgreSQL identifier."""
    return '"' + value.replace('"', '""') + '"'


def normalize_column_name(column: object) -> str:
    """Normalize a column name to lowercase snake_case."""
    name = str(column).strip().lower()
    name = re.sub(r"[^a-z0-9_]+", "_", name)
    name = re.sub(r"_+", "_", name).strip("_")
    return name


def normalize_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize DataFrame column names before SQL insertion."""
    df = df.copy()
    df.columns = [normalize_column_name(column) for column in df.columns]
    return df


def identifier_columns(columns: list[str]) -> list[str]:
    """Return columns that should be read as strings from CSV sources."""
    return [column for column in columns if column == "id" or column.endswith("_id")]


def read_csv_header(path: Path) -> list[str]:
    """Read and normalize only the CSV header."""
    header = pd.read_csv(path, nrows=0, encoding="utf-8")
    return [normalize_column_name(column) for column in header.columns]


def discover_datasets() -> dict[str, Path]:
    """Discover logical datasets and prefer Parquet when duplicates exist."""
    candidates: dict[str, list[Path]] = {}

    for path in DATA_ROOT.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            continue

        table_name = path.stem.lower()
        candidates.setdefault(table_name, []).append(path)

    unknown_tables = sorted(set(candidates) - EXPECTED_TABLES)
    missing_tables = sorted(EXPECTED_TABLES - set(candidates))

    if unknown_tables:
        raise RuntimeError(
            "Generated data contains tables without a PostgreSQL schema mapping: "
            + ", ".join(unknown_tables)
        )

    if missing_tables:
        raise RuntimeError(
            "Expected BTYT datasets were not found under data/generated: "
            + ", ".join(missing_tables)
        )

    selected: dict[str, Path] = {}

    for table_name, paths in candidates.items():
        parquet_files = [path for path in paths if path.suffix.lower() == ".parquet"]
        csv_files = [path for path in paths if path.suffix.lower() == ".csv"]

        if parquet_files:
            selected[table_name] = sorted(parquet_files)[0]
        elif csv_files:
            selected[table_name] = sorted(csv_files)[0]

    return selected


def source_row_count(path: Path) -> int:
    """Return the number of source rows without loading the full dataset."""
    if path.suffix.lower() == ".parquet":
        parquet_file = pq.ParquetFile(path)
        return parquet_file.metadata.num_rows

    total = 0
    for chunk in pd.read_csv(path, chunksize=CSV_CHUNK_SIZE, encoding="utf-8"):
        total += len(chunk)
    return total


def iter_source_batches(path: Path) -> Iterator[pd.DataFrame]:
    """Yield normalized DataFrames from CSV or Parquet sources."""
    if path.suffix.lower() == ".parquet":
        parquet_file = pq.ParquetFile(path)
        for batch in parquet_file.iter_batches(batch_size=PARQUET_BATCH_SIZE):
            yield normalize_dataframe(batch.to_pandas())
        return

    columns = read_csv_header(path)
    id_columns = identifier_columns(columns)
    dtype = {column: "string" for column in id_columns}

    for chunk in pd.read_csv(
        path,
        chunksize=CSV_CHUNK_SIZE,
        encoding="utf-8",
        dtype=dtype or None,
    ):
        yield normalize_dataframe(chunk)


def build_engine() -> Engine:
    """Create a SQLAlchemy PostgreSQL engine."""
    global DB_PASSWORD

    if not DB_PASSWORD:
        DB_PASSWORD = getpass.getpass(f"PostgreSQL password for user '{DB_USER}': ")

    url = URL.create(
        drivername="postgresql+psycopg",
        username=DB_USER,
        password=DB_PASSWORD,
        host=DB_HOST,
        port=DB_PORT,
        database=DB_NAME,
    )

    return create_engine(url, future=True)


def ensure_schema(engine: Engine, schema_name: str) -> None:
    """Create a PostgreSQL schema if it does not already exist."""
    sql = f"CREATE SCHEMA IF NOT EXISTS {quote_identifier(schema_name)}"
    with engine.begin() as connection:
        connection.execute(text(sql))


def table_exists(engine: Engine, schema_name: str, table_name: str) -> bool:
    """Return whether the target table exists."""
    inspector = inspect(engine)
    return inspector.has_table(table_name, schema=schema_name)


def table_row_count(engine: Engine, schema_name: str, table_name: str) -> int:
    """Return the number of rows in a PostgreSQL table."""
    schema = quote_identifier(schema_name)
    table = quote_identifier(table_name)
    sql = text(f"SELECT COUNT(*) FROM {schema}.{table}")

    with engine.connect() as connection:
        return int(connection.execute(sql).scalar_one())


def truncate_table(engine: Engine, schema_name: str, table_name: str) -> None:
    """Remove all rows from an incomplete target table."""
    schema = quote_identifier(schema_name)
    table = quote_identifier(table_name)
    sql = text(f"TRUNCATE TABLE {schema}.{table}")

    with engine.begin() as connection:
        connection.execute(sql)


def load_dataset(
    engine: Engine,
    source_path: Path,
    schema_name: str,
    table_name: str,
    expected_rows: int,
) -> str:
    """Load one dataset and return LOAD, SKIP or FAIL status."""
    ensure_schema(engine, schema_name)

    exists = table_exists(engine, schema_name, table_name)

    if exists:
        current_rows = table_row_count(engine, schema_name, table_name)

        if current_rows == expected_rows:
            print(
                f"[SKIP] {schema_name}.{table_name}: "
                f"already contains {current_rows:,} rows"
            )
            return "SKIP"

        if current_rows > 0:
            print(
                f"[RESET] {schema_name}.{table_name}: "
                f"database has {current_rows:,} rows, source has {expected_rows:,}"
            )
            truncate_table(engine, schema_name, table_name)

    inserted_rows = 0

    for frame in iter_source_batches(source_path):
        frame.to_sql(
            table_name,
            engine,
            schema=schema_name,
            if_exists="append",
            index=False,
            chunksize=SQL_CHUNK_SIZE,
        )
        inserted_rows += len(frame)

        if expected_rows >= 1_000_000:
            print(
                f"       {schema_name}.{table_name}: "
                f"{inserted_rows:,}/{expected_rows:,} rows"
            )

    actual_rows = table_row_count(engine, schema_name, table_name)

    if actual_rows != expected_rows:
        raise RuntimeError(
            f"Row-count validation failed for {schema_name}.{table_name}: "
            f"source={expected_rows:,}, PostgreSQL={actual_rows:,}"
        )

    print(f"[ OK ] {schema_name}.{table_name}: {actual_rows:,} rows")
    return "LOAD"


# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------


def main() -> None:
    """Discover and load all canonical BTYT datasets."""
    if not DATA_ROOT.exists():
        raise FileNotFoundError(f"Generated data directory not found: {DATA_ROOT}")

    datasets = discover_datasets()
    engine = build_engine()

    print(f"Connected to PostgreSQL: {DB_HOST}:{DB_PORT}/{DB_NAME}")
    print(f"Generated data root: {DATA_ROOT}")
    print(f"Discovered datasets: {len(datasets)}")
    print()

    results = {"LOAD": 0, "SKIP": 0, "FAIL": 0}

    ordered_tables = sorted(
        datasets,
        key=lambda table: (TABLE_SCHEMA_MAP[table], table),
    )

    for table_name in ordered_tables:
        source_path = datasets[table_name]
        schema_name = TABLE_SCHEMA_MAP[table_name]
        expected_rows = source_row_count(source_path)

        print(
            f"[LOAD] {schema_name}.{table_name} "
            f"<- {source_path.name} ({expected_rows:,} rows)"
        )

        try:
            status = load_dataset(
                engine=engine,
                source_path=source_path,
                schema_name=schema_name,
                table_name=table_name,
                expected_rows=expected_rows,
            )
            results[status] += 1
        except Exception as exc:
            results["FAIL"] += 1
            print(f"[FAIL] {schema_name}.{table_name}: {exc}")

        print()

    print("=" * 78)
    print("LOAD SUMMARY")
    print("=" * 78)
    print(f"Loaded : {results['LOAD']}")
    print(f"Skipped: {results['SKIP']}")
    print(f"Failed : {results['FAIL']}")

    if results["FAIL"]:
        print("\nSome datasets failed. Review the errors before adding constraints.")
    else:
        print("\nAll BTYT datasets are loaded and row-count validated.")


if __name__ == "__main__":
    main()
