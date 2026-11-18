"""Reload BTYT performance tables after regenerating branch performance.

Targeted utility, not part of the canonical refresh path: a full refresh is
performed by scripts/database/load_postgresql.py (see docs/dbprocess/).

Run it from the repository root with:

    python scripts/sql/reload/reload_performance_postgresql.py

The script:
- reads the regenerated BTYT/01 performance Parquet files;
- converts year_month to Python date objects for PostgreSQL DATE columns;
- replaces only the two final performance tables;
- preserves the existing relational model, constraints and analytics views;
- validates source/destination column sets and aligns column order;
- validates row counts;
- commits both replacements atomically.
"""

from __future__ import annotations

import getpass
import os
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import URL


# ---------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------

# File location:
# repo/scripts/sql/reload/reload_performance_postgresql.py
#
# parents[0] = reload
# parents[1] = sql
# parents[2] = scripts
# parents[3] = repository root
REPO_ROOT = Path(__file__).resolve().parents[3]

PERFORMANCE_DIR = (
    REPO_ROOT
    / "worlds"
    / "BTYT"
    / "01"
    / "data"
    / "generated"
    / "performance"
)

BRANCH_PATH = PERFORMANCE_DIR / "branch_monthly_performance.parquet"
BANK_PATH = PERFORMANCE_DIR / "bank_monthly_performance.parquet"


# ---------------------------------------------------------------------
# PostgreSQL connection
# ---------------------------------------------------------------------

DB_HOST = os.getenv("BTYT_DB_HOST", "localhost")
DB_PORT = int(os.getenv("BTYT_DB_PORT", "5432"))
DB_NAME = os.getenv("BTYT_DB_NAME", "BTYT")
DB_USER = os.getenv("BTYT_DB_USER", "postgres")
DB_PASSWORD = os.getenv("BTYT_DB_PASSWORD")


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------

def build_engine():
    """Build the PostgreSQL SQLAlchemy engine."""
    global DB_PASSWORD

    if not DB_PASSWORD:
        DB_PASSWORD = getpass.getpass(
            f"PostgreSQL password for user '{DB_USER}': "
        )

    url = URL.create(
        drivername="postgresql+psycopg",
        username=DB_USER,
        password=DB_PASSWORD,
        host=DB_HOST,
        port=DB_PORT,
        database=DB_NAME,
    )

    return create_engine(url, future=True)


def prepare_frame(path: Path, key_columns: list[str]) -> pd.DataFrame:
    """Read one Parquet file and prepare it for the final PostgreSQL schema."""
    if not path.exists():
        raise FileNotFoundError(f"Source file not found: {path}")

    frame = pd.read_parquet(path)

    missing = [column for column in key_columns if column not in frame.columns]
    if missing:
        raise RuntimeError(
            f"{path.name} is missing required columns: {', '.join(missing)}"
        )

    # Final PostgreSQL performance tables use DATE for year_month.
    if "year_month" in frame.columns:
        parsed = pd.to_datetime(frame["year_month"], errors="raise")
        frame["year_month"] = parsed.dt.date

    if frame.duplicated(key_columns).any():
        raise RuntimeError(
            f"Duplicate key rows detected in {path.name}: {key_columns}"
        )

    return frame


def assert_target_table(engine, schema: str, table: str) -> None:
    """Fail before modifying anything if a target table is missing."""
    inspector = inspect(engine)

    if not inspector.has_table(table, schema=schema):
        raise RuntimeError(
            f"Target table does not exist: {schema}.{table}"
        )


def destination_columns(connection, schema: str, table: str) -> list[str]:
    """Return destination columns in ordinal order."""
    rows = connection.execute(
        text(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = :schema
              AND table_name = :table
            ORDER BY ordinal_position
            """
        ),
        {"schema": schema, "table": table},
    ).scalars().all()

    return list(rows)


def align_source_columns(
    frame: pd.DataFrame,
    expected_columns: list[str],
    label: str,
) -> pd.DataFrame:
    """
    Validate that source and destination contain the same columns, regardless
    of physical order, then reorder the source to match PostgreSQL.

    Parquet column order is not part of the analytical contract. PostgreSQL
    ordinal order may differ after schema evolution, so only missing or extra
    columns are considered a schema error.
    """
    source_columns = list(frame.columns)

    source_only = [c for c in source_columns if c not in expected_columns]
    db_only = [c for c in expected_columns if c not in source_columns]

    if source_only or db_only:
        raise RuntimeError(
            f"Column mismatch for {label}.\n"
            f"Source-only columns: {source_only}\n"
            f"Database-only columns: {db_only}\n"
            f"Source order: {source_columns}\n"
            f"Database order: {expected_columns}"
        )

    return frame.loc[:, expected_columns].copy()


def count_rows(connection, schema: str, table: str) -> int:
    """Count rows in a PostgreSQL table."""
    return int(
        connection.execute(
            text(f'SELECT COUNT(*) FROM "{schema}"."{table}"')
        ).scalar_one()
    )


# ---------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------

def main() -> None:
    """Reload only the two performance tables."""
    branch = prepare_frame(
        BRANCH_PATH,
        key_columns=["branch_id", "year_month"],
    )
    bank = prepare_frame(
        BANK_PATH,
        key_columns=["year_month"],
    )

    engine = build_engine()

    print("=" * 78)
    print("BTYT PERFORMANCE POSTGRESQL RELOAD")
    print("=" * 78)
    print(f"Repository root : {REPO_ROOT}")
    print(f"Performance dir : {PERFORMANCE_DIR}")
    print(f"Database        : {DB_HOST}:{DB_PORT}/{DB_NAME}")
    print()

    # Preflight checks before the transaction modifies anything.
    assert_target_table(
        engine,
        "performance",
        "branch_monthly_performance",
    )
    assert_target_table(
        engine,
        "performance",
        "bank_monthly_performance",
    )

    with engine.connect() as connection:
        branch_db_columns = destination_columns(
            connection,
            "performance",
            "branch_monthly_performance",
        )
        bank_db_columns = destination_columns(
            connection,
            "performance",
            "bank_monthly_performance",
        )

    # The source and destination must contain the same columns, but their
    # physical order does not need to match. Reorder the Parquet frames to the
    # existing PostgreSQL ordinal order before inserting.
    branch = align_source_columns(
        branch,
        branch_db_columns,
        "performance.branch_monthly_performance",
    )
    bank = align_source_columns(
        bank,
        bank_db_columns,
        "performance.bank_monthly_performance",
    )

    print("[PASS] Source files found")
    print("[PASS] Target tables found")
    print("[PASS] Source/database column schemas match")
    print("[PASS] year_month prepared for PostgreSQL DATE")
    print()

    # Atomic replacement:
    # any failure rolls back the TRUNCATE and all inserts.
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                TRUNCATE TABLE
                    performance.branch_monthly_performance,
                    performance.bank_monthly_performance
                """
            )
        )

        # These tables are small. Standard executemany-style inserts are more
        # robust here than one giant multi-row SQL statement.
        branch.to_sql(
            "branch_monthly_performance",
            connection,
            schema="performance",
            if_exists="append",
            index=False,
            chunksize=250,
            method=None,
        )

        bank.to_sql(
            "bank_monthly_performance",
            connection,
            schema="performance",
            if_exists="append",
            index=False,
            chunksize=250,
            method=None,
        )

        branch_rows = count_rows(
            connection,
            "performance",
            "branch_monthly_performance",
        )
        bank_rows = count_rows(
            connection,
            "performance",
            "bank_monthly_performance",
        )

        if branch_rows != len(branch):
            raise RuntimeError(
                "Row-count validation failed for "
                "performance.branch_monthly_performance: "
                f"source={len(branch):,}, database={branch_rows:,}"
            )

        if bank_rows != len(bank):
            raise RuntimeError(
                "Row-count validation failed for "
                "performance.bank_monthly_performance: "
                f"source={len(bank):,}, database={bank_rows:,}"
            )

    print("[PASS] performance.branch_monthly_performance reloaded")
    print("[PASS] performance.bank_monthly_performance reloaded")
    print("[PASS] Row-count validation")
    print("[PASS] Transaction committed")
    print()
    print("BTYT PERFORMANCE POSTGRESQL RELOAD: PASS")
    print("Next step: refresh Power BI.")


if __name__ == "__main__":
    main()
