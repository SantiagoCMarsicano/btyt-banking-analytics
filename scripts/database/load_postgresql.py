"""Full-refresh loader for the canonical BTYT PostgreSQL database.

Purpose
-------
Replace the DATA inside the existing 23 physical BTYT tables while preserving
the relational model already configured in PostgreSQL:

- schemas
- table definitions
- data types
- primary keys
- foreign keys
- CHECK / NOT NULL constraints
- indexes
- views

The loader never DROP/CREATEs existing BTYT tables.

Canonical source
----------------
worlds/BTYT/01/data/generated

Final PostgreSQL architecture
-----------------------------
core        : 4 tables
banking     : 5 tables
marketing   : 3 tables
reference   : 2 tables
market      : 5 tables
macro       : 2 tables
performance : 2 tables

Total       : 23 tables
"""

from __future__ import annotations

import csv
import getpass
import io
import os
import re
from pathlib import Path
from typing import Iterator

import pandas as pd
import pyarrow.parquet as pq
import psycopg
from psycopg import sql


# =============================================================================
# PATHS
# =============================================================================

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_ROOT = REPO_ROOT / "worlds" / "BTYT" / "01" / "data" / "generated"


# =============================================================================
# POSTGRESQL
# =============================================================================

DB_HOST = os.getenv("BTYT_DB_HOST", "localhost")
DB_PORT = int(os.getenv("BTYT_DB_PORT", "5432"))
DB_NAME = os.getenv("BTYT_DB_NAME", "BTYT")
DB_USER = os.getenv("BTYT_DB_USER", "postgres")
DB_PASSWORD = os.getenv("BTYT_DB_PASSWORD")


# =============================================================================
# FINAL RELATIONAL ARCHITECTURE
# =============================================================================

TABLE_SCHEMA_MAP: dict[str, str] = {
    # core
    "branches": "core",
    "customers": "core",
    "accounts": "core",
    "products": "core",

    # banking
    "cards": "banking",
    "loans": "banking",
    "transactions": "banking",
    "account_balances": "banking",
    "loan_monthly_snapshot": "banking",

    # marketing
    "campaigns": "marketing",
    "campaign_customers": "marketing",
    "campaign_exposures": "marketing",

    # reference
    "campaign_channels": "reference",
    "campaign_geography": "reference",

    # market
    "banks": "market",
    "bank_financials": "market",
    "bank_market_weights": "market",
    "bank_world_parameters": "market",
    "financial_institutions": "market",

    # macro
    "macro_environment": "macro",
    "external_shocks": "macro",

    # performance
    "bank_monthly_performance": "performance",
    "branch_monthly_performance": "performance",
}

EXPECTED_TABLES = set(TABLE_SCHEMA_MAP)

# Parent tables are loaded before dependent tables.
LOAD_ORDER = [
    # independent / parent dimensions
    "branches",
    "products",
    "banks",

    # core entities
    "customers",
    "accounts",

    # market / macro parents
    "financial_institutions",
    "bank_financials",
    "bank_market_weights",
    "bank_world_parameters",
    "macro_environment",
    "external_shocks",

    # banking
    "cards",
    "loans",
    "loan_monthly_snapshot",
    "account_balances",
    "transactions",

    # marketing / reference
    "campaigns",
    "campaign_customers",
    "campaign_exposures",
    "campaign_channels",
    "campaign_geography",

    # management accounting
    "bank_monthly_performance",
    "branch_monthly_performance",
]

assert set(LOAD_ORDER) == EXPECTED_TABLES
assert len(LOAD_ORDER) == 23


# =============================================================================
# LOADING SETTINGS
# =============================================================================

PARQUET_BATCH_SIZE = 150_000
CSV_BATCH_SIZE = 100_000
SUPPORTED_EXTENSIONS = {".parquet", ".csv"}


# =============================================================================
# SOURCE DISCOVERY
# =============================================================================

def normalize_column_name(column: object) -> str:
    value = str(column).strip().lower()
    value = re.sub(r"[^a-z0-9_]+", "_", value)
    value = re.sub(r"_+", "_", value).strip("_")
    return value


def discover_datasets() -> dict[str, Path]:
    """Discover all 23 canonical datasets, preferring Parquet over CSV."""
    if not DATA_ROOT.exists():
        raise FileNotFoundError(f"Canonical generated-data root not found: {DATA_ROOT}")

    candidates: dict[str, list[Path]] = {}

    for path in DATA_ROOT.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            continue

        table_name = path.stem.lower()
        candidates.setdefault(table_name, []).append(path)

    missing = sorted(EXPECTED_TABLES - set(candidates))
    unknown = sorted(set(candidates) - EXPECTED_TABLES)

    if missing:
        raise RuntimeError(
            "Missing canonical datasets:\n  " + "\n  ".join(missing)
        )

    if unknown:
        raise RuntimeError(
            "Generated data contains unmapped datasets. "
            "Update TABLE_SCHEMA_MAP before refreshing PostgreSQL:\n  "
            + "\n  ".join(unknown)
        )

    selected: dict[str, Path] = {}

    for table_name in EXPECTED_TABLES:
        paths = candidates[table_name]

        parquet = sorted(
            p for p in paths if p.suffix.lower() == ".parquet"
        )
        csv_files = sorted(
            p for p in paths if p.suffix.lower() == ".csv"
        )

        if parquet:
            selected[table_name] = parquet[0]
        elif csv_files:
            selected[table_name] = csv_files[0]
        else:
            raise RuntimeError(f"No usable source found for {table_name}")

    return selected


def csv_identifier_dtype(path: Path) -> dict[str, str]:
    """Preserve identifier columns exactly as text when reading CSV files.

    This is critical for IDs such as branch_id='001' and
    parent_branch_id='001'; allowing pandas to infer numeric dtype would turn
    them into 1 / 1.0 and break PostgreSQL foreign keys.
    """
    header = pd.read_csv(path, nrows=0, encoding="utf-8")
    normalized = [normalize_column_name(c) for c in header.columns]

    return {
        original: "string"
        for original, normalized_name in zip(header.columns, normalized)
        if normalized_name == "id" or normalized_name.endswith("_id")
    }


def source_columns(path: Path) -> list[str]:
    if path.suffix.lower() == ".parquet":
        return [
            normalize_column_name(name)
            for name in pq.ParquetFile(path).schema.names
        ]

    header = pd.read_csv(path, nrows=0, encoding="utf-8")
    return [normalize_column_name(c) for c in header.columns]


def source_row_count(path: Path) -> int:
    if path.suffix.lower() == ".parquet":
        return int(pq.ParquetFile(path).metadata.num_rows)

    total = 0
    for frame in pd.read_csv(
        path,
        chunksize=CSV_BATCH_SIZE,
        encoding="utf-8",
        low_memory=False,
    ):
        total += len(frame)
    return total


def iter_source_batches(path: Path) -> Iterator[pd.DataFrame]:
    if path.suffix.lower() == ".parquet":
        parquet_file = pq.ParquetFile(path)

        for batch in parquet_file.iter_batches(
            batch_size=PARQUET_BATCH_SIZE
        ):
            frame = batch.to_pandas()
            frame.columns = [
                normalize_column_name(c) for c in frame.columns
            ]
            yield frame

        return

    dtype = csv_identifier_dtype(path)

    for frame in pd.read_csv(
        path,
        chunksize=CSV_BATCH_SIZE,
        encoding="utf-8",
        low_memory=False,
        dtype=dtype or None,
    ):
        frame.columns = [
            normalize_column_name(c) for c in frame.columns
        ]
        yield frame


# =============================================================================
# DATABASE METADATA
# =============================================================================

def connect():
    global DB_PASSWORD

    if not DB_PASSWORD:
        DB_PASSWORD = getpass.getpass(
            f"PostgreSQL password for user '{DB_USER}': "
        )

    return psycopg.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
    )


def target_metadata(cursor, schema_name: str, table_name: str):
    cursor.execute(
        """
        SELECT
            column_name,
            data_type,
            udt_name,
            ordinal_position
        FROM information_schema.columns
        WHERE table_schema = %s
          AND table_name = %s
        ORDER BY ordinal_position;
        """,
        (schema_name, table_name),
    )

    rows = cursor.fetchall()

    if not rows:
        raise RuntimeError(
            f"Target table not found: {schema_name}.{table_name}"
        )

    return [
        {
            "name": row[0],
            "data_type": row[1],
            "udt_name": row[2],
            "position": row[3],
        }
        for row in rows
    ]


def table_row_count(cursor, schema_name: str, table_name: str) -> int:
    statement = sql.SQL("SELECT COUNT(*) FROM {}.{}").format(
        sql.Identifier(schema_name),
        sql.Identifier(table_name),
    )
    cursor.execute(statement)
    return int(cursor.fetchone()[0])


# =============================================================================
# TYPE PREPARATION
# =============================================================================

INTEGER_TYPES = {"smallint", "integer", "bigint"}
NUMERIC_TYPES = {
    "numeric",
    "decimal",
    "real",
    "double precision",
}
DATE_TYPES = {"date"}
TIMESTAMP_TYPES = {
    "timestamp without time zone",
    "timestamp with time zone",
}


def prepare_frame(
    frame: pd.DataFrame,
    metadata: list[dict],
) -> pd.DataFrame:
    """Prepare a source batch for COPY into the existing typed table."""
    result = frame.copy()

    target_columns = [item["name"] for item in metadata]
    result = result[target_columns]

    for item in metadata:
        column = item["name"]
        data_type = item["data_type"]

        if data_type in INTEGER_TYPES:
            result[column] = pd.to_numeric(
                result[column],
                errors="coerce",
            ).astype("Int64")

        elif data_type in NUMERIC_TYPES:
            result[column] = pd.to_numeric(
                result[column],
                errors="coerce",
            )

        elif data_type in DATE_TYPES:
            parsed = pd.to_datetime(
                result[column],
                errors="coerce",
            )
            result[column] = parsed.dt.strftime("%Y-%m-%d")
            result.loc[parsed.isna(), column] = pd.NA

        elif data_type in TIMESTAMP_TYPES:
            parsed = pd.to_datetime(
                result[column],
                errors="coerce",
            )
            result[column] = parsed.dt.strftime("%Y-%m-%d %H:%M:%S")
            result.loc[parsed.isna(), column] = pd.NA

    return result


# =============================================================================
# COPY
# =============================================================================

def copy_frame(
    cursor,
    schema_name: str,
    table_name: str,
    frame: pd.DataFrame,
    column_names: list[str],
) -> None:
    buffer = io.StringIO()

    frame.to_csv(
        buffer,
        index=False,
        header=False,
        na_rep="\\N",
        quoting=csv.QUOTE_MINIMAL,
        lineterminator="\n",
    )

    buffer.seek(0)

    copy_statement = sql.SQL(
        "COPY {}.{} ({}) FROM STDIN "
        "WITH (FORMAT CSV, NULL '\\N')"
    ).format(
        sql.Identifier(schema_name),
        sql.Identifier(table_name),
        sql.SQL(", ").join(
            sql.Identifier(column) for column in column_names
        ),
    )

    with cursor.copy(copy_statement) as copy:
        while True:
            chunk = buffer.read(1024 * 1024)
            if not chunk:
                break
            copy.write(chunk)


# =============================================================================
# PREFLIGHT
# =============================================================================

def preflight(cursor, datasets: dict[str, Path]):
    print("\n" + "=" * 88)
    print("PREFLIGHT")
    print("=" * 88)

    metadata_by_table: dict[str, list[dict]] = {}
    source_rows: dict[str, int] = {}

    for table_name in LOAD_ORDER:
        schema_name = TABLE_SCHEMA_MAP[table_name]
        path = datasets[table_name]

        metadata = target_metadata(
            cursor,
            schema_name,
            table_name,
        )
        metadata_by_table[table_name] = metadata

        target_columns = [item["name"] for item in metadata]
        src_columns = source_columns(path)

        missing_in_source = sorted(
            set(target_columns) - set(src_columns)
        )
        extra_in_source = sorted(
            set(src_columns) - set(target_columns)
        )

        if missing_in_source or extra_in_source:
            raise RuntimeError(
                f"Column mismatch in {schema_name}.{table_name}\n"
                f"Missing in source: {missing_in_source}\n"
                f"Extra in source  : {extra_in_source}"
            )

        rows = source_row_count(path)
        source_rows[table_name] = rows
        current_rows = table_row_count(
            cursor,
            schema_name,
            table_name,
        )

        relative_path = path.relative_to(REPO_ROOT)

        print(
            f"[PASS] {schema_name}.{table_name:<30} "
            f"DB={current_rows:>11,}  SOURCE={rows:>11,}"
        )
        print(f"       <- {relative_path}")

    print("\nPreflight complete: 23/23 tables compatible.")

    return metadata_by_table, source_rows


# =============================================================================
# FULL REFRESH
# =============================================================================

def truncate_all(cursor):
    targets = [
        sql.SQL("{}.{}").format(
            sql.Identifier(TABLE_SCHEMA_MAP[table_name]),
            sql.Identifier(table_name),
        )
        for table_name in LOAD_ORDER
    ]

    statement = sql.SQL("TRUNCATE TABLE {}").format(
        sql.SQL(", ").join(targets)
    )

    cursor.execute(statement)


def load_all(
    cursor,
    datasets: dict[str, Path],
    metadata_by_table: dict[str, list[dict]],
    source_rows: dict[str, int],
):
    for table_name in LOAD_ORDER:
        schema_name = TABLE_SCHEMA_MAP[table_name]
        path = datasets[table_name]
        metadata = metadata_by_table[table_name]

        target_columns = [item["name"] for item in metadata]
        expected_rows = source_rows[table_name]

        print(
            f"\n[LOAD] {schema_name}.{table_name} "
            f"({expected_rows:,} rows)"
        )

        inserted = 0

        for raw_frame in iter_source_batches(path):
            prepared = prepare_frame(
                raw_frame,
                metadata,
            )

            copy_frame(
                cursor,
                schema_name,
                table_name,
                prepared,
                target_columns,
            )

            inserted += len(prepared)

            if expected_rows >= 1_000_000:
                print(
                    f"       {inserted:,}/{expected_rows:,}"
                )

        actual_rows = table_row_count(
            cursor,
            schema_name,
            table_name,
        )

        if actual_rows != expected_rows:
            raise RuntimeError(
                f"Row-count mismatch for "
                f"{schema_name}.{table_name}: "
                f"source={expected_rows:,}, "
                f"database={actual_rows:,}"
            )

        print(
            f"[ OK ] {schema_name}.{table_name}: "
            f"{actual_rows:,} rows"
        )


# =============================================================================
# POST-LOAD CHECKS
# =============================================================================

def verify_all_counts(
    cursor,
    source_rows: dict[str, int],
):
    print("\n" + "=" * 88)
    print("POST-LOAD ROW-COUNT VALIDATION")
    print("=" * 88)

    for table_name in LOAD_ORDER:
        schema_name = TABLE_SCHEMA_MAP[table_name]
        expected = source_rows[table_name]
        actual = table_row_count(
            cursor,
            schema_name,
            table_name,
        )

        if actual != expected:
            raise RuntimeError(
                f"Final validation failed for "
                f"{schema_name}.{table_name}: "
                f"source={expected:,}, database={actual:,}"
            )

        print(
            f"[PASS] {schema_name}.{table_name:<30} "
            f"{actual:>11,}"
        )


def analyze_tables(cursor):
    print("\nUpdating PostgreSQL planner statistics...")

    for table_name in LOAD_ORDER:
        schema_name = TABLE_SCHEMA_MAP[table_name]

        statement = sql.SQL("ANALYZE {}.{}").format(
            sql.Identifier(schema_name),
            sql.Identifier(table_name),
        )

        cursor.execute(statement)

    print("ANALYZE: PASS")


def refresh_analytics_materialized_views(connection):
    """Refresh analytics materialized views if the project currently has any."""
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT schemaname, matviewname
            FROM pg_matviews
            WHERE schemaname = 'analytics'
            ORDER BY matviewname;
            """
        )
        materialized_views = cursor.fetchall()

    if not materialized_views:
        print("\nAnalytics materialized views: none found.")
        return

    print("\nRefreshing analytics materialized views...")

    for schema_name, view_name in materialized_views:
        with connection.cursor() as cursor:
            statement = sql.SQL(
                "REFRESH MATERIALIZED VIEW {}.{}"
            ).format(
                sql.Identifier(schema_name),
                sql.Identifier(view_name),
            )
            cursor.execute(statement)

        connection.commit()
        print(
            f"[ OK ] {schema_name}.{view_name}"
        )


# =============================================================================
# MAIN
# =============================================================================

def main():
    print("=" * 88)
    print("BTYT POSTGRESQL — CANONICAL FULL REFRESH")
    print("=" * 88)
    print(f"Database : {DB_NAME}")
    print(f"Server   : {DB_HOST}:{DB_PORT}")
    print(f"User     : {DB_USER}")
    print(f"Source   : {DATA_ROOT}")
    print("Mode     : TRUNCATE + COPY into the EXISTING 23-table relational model")
    print()
    print("This preserves schemas, relationships, constraints, indexes and views.")

    datasets = discover_datasets()

    with connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT current_database();")
            current_database = cursor.fetchone()[0]

            if current_database != DB_NAME:
                raise RuntimeError(
                    f"Connected to {current_database!r}; "
                    f"expected {DB_NAME!r}."
                )

            metadata_by_table, source_rows = preflight(
                cursor,
                datasets,
            )

        connection.rollback()

        confirmation = input(
            "\nType BTYT to replace the data in all 23 physical tables: "
        ).strip()

        if confirmation != "BTYT":
            print("Refresh cancelled. PostgreSQL was not modified.")
            return

        try:
            with connection.transaction():
                with connection.cursor() as cursor:
                    print(
                        "\nTruncating all 23 physical tables "
                        "in one relationally safe statement..."
                    )
                    truncate_all(cursor)
                    print("TRUNCATE: PASS")

                    load_all(
                        cursor,
                        datasets,
                        metadata_by_table,
                        source_rows,
                    )

                    verify_all_counts(
                        cursor,
                        source_rows,
                    )

                    analyze_tables(cursor)

            print("\nBase-table transaction committed successfully.")

        except Exception:
            print(
                "\nERROR: full refresh failed. "
                "The transaction was rolled back."
            )
            raise

        # Normal views update automatically.
        # Materialized views, when present, need an explicit refresh.
        refresh_analytics_materialized_views(connection)

    print("\n" + "=" * 88)
    print("BTYT FULL REFRESH: PASS")
    print("=" * 88)
    print("23/23 physical tables reloaded from canonical sources.")
    print("Existing PostgreSQL relational structure was preserved.")
    print("Normal SQL views reflect the new data automatically.")


if __name__ == "__main__":
    main()
