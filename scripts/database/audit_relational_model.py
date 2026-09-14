"""
BTYT Relational Model Audit
===========================

Read-only audit of the PostgreSQL BTYT database.

This script inspects:
    1. Final 7-schema / 23-table architecture
    2. Current applied relational state
    3. Database structure
    4. Current PostgreSQL data types
    5. Expected semantic data types
    6. Actual values in columns requiring review
    7. Financial precision and numeric semantics
    8. Candidate primary key integrity
    9. Constraint candidates and business rules

It does not modify tables, data, constraints, or indexes.
"""

from getpass import getpass
import argparse
import re
import pandas as pd
from sqlalchemy import create_engine, text

DB_HOST = "localhost"
DB_PORT = 5432
DB_NAME = "BTYT"
DB_USER = "postgres"
BTYT_SCHEMAS = [
    "core",
    "banking",
    "marketing",
    "reference",
    "market",
    "macro",
    "performance",
]

FINAL_SCHEMA_LAYOUT = {
    "core": ["branches", "customers", "accounts", "products"],
    "banking": [
        "cards",
        "loans",
        "transactions",
        "account_balances",
        "loan_monthly_snapshot",
    ],
    "marketing": ["campaigns", "campaign_customers", "campaign_exposures"],
    "reference": ["campaign_channels", "campaign_geography"],
    "market": [
        "banks",
        "bank_financials",
        "bank_market_weights",
        "bank_world_parameters",
        "financial_institutions",
    ],
    "macro": ["macro_environment", "external_shocks"],
    "performance": ["bank_monthly_performance", "branch_monthly_performance"],
}

EXPECTED_RELATIONAL_COUNTS = {
    "primary_keys": 23,
    "foreign_keys": 28,
    "check_constraints": 27,
}

AUDITED_NOT_NULL_COLUMNS = [
    ("core", "accounts", "customer_id"),
    ("core", "accounts", "product_id"),
    ("core", "accounts", "branch_id"),
    ("banking", "cards", "customer_id"),
    ("banking", "cards", "product_id"),
    ("banking", "loans", "customer_id"),
    ("banking", "loans", "product_id"),
    ("banking", "loans", "branch_id"),
    ("banking", "transactions", "account_id"),
    ("marketing", "campaign_exposures", "campaign_id"),
    ("marketing", "campaign_exposures", "customer_id"),
]

EXPECTED_TYPES = {
    ("core", "branches", "opening_year"): {"expected": "integer", "severity": "REVIEW"},
    ("core", "branches", "closing_year"): {"expected": "integer", "severity": "FAIL"},
    ("core", "branches", "closure_reason"): {"expected": "text", "severity": "FAIL"},
    ("core", "customers", "birth_year"): {"expected": "integer", "severity": "REVIEW"},
    ("core", "customers", "registration_year"): {"expected": "integer", "severity": "REVIEW"},
    ("core", "customers", "closing_year"): {"expected": "integer", "severity": "REVIEW"},
    ("core", "customers", "foundation_year"): {"expected": "integer", "severity": "REVIEW"},
    ("core", "accounts", "opening_year"): {"expected": "integer", "severity": "REVIEW"},
    ("core", "accounts", "closing_year"): {"expected": "integer", "severity": "REVIEW"},
    ("core", "products", "launch_year"): {"expected": "integer", "severity": "REVIEW"},
    ("banking", "account_balances", "year_month"): {"expected": "date", "severity": "REVIEW"},
    ("banking", "cards", "issue_year"): {"expected": "integer", "severity": "REVIEW"},
    ("banking", "cards", "closing_year"): {"expected": "integer", "severity": "REVIEW"},
    ("banking", "loan_monthly_snapshot", "year_month"): {"expected": "date", "severity": "REVIEW"},
    ("banking", "loans", "origination_year"): {"expected": "integer", "severity": "REVIEW"},
    ("banking", "loans", "term_months"): {"expected": "integer", "severity": "REVIEW"},
    ("banking", "loans", "closing_year"): {"expected": "integer", "severity": "FAIL"},
    ("marketing", "campaigns", "start_date"): {"expected": "date", "severity": "REVIEW"},
    ("marketing", "campaigns", "end_date"): {"expected": "date", "severity": "REVIEW"},
    ("market", "bank_financials", "year"): {"expected": "integer", "severity": "REVIEW"},
    ("market", "bank_market_weights", "year"): {"expected": "integer", "severity": "REVIEW"},
    ("performance", "bank_monthly_performance", "year_month"): {"expected": "date", "severity": "REVIEW"},
    ("performance", "branch_monthly_performance", "year_month"): {"expected": "date", "severity": "REVIEW"},
    ("macro", "external_shocks", "start_month"): {"expected": "date", "severity": "REVIEW"},
    ("macro", "external_shocks", "peak_month"): {"expected": "date", "severity": "REVIEW"},
    ("macro", "external_shocks", "end_month"): {"expected": "date", "severity": "REVIEW"},
    ("macro", "external_shocks", "recovery_end_month"): {"expected": "date", "severity": "REVIEW"},
    ("macro", "external_shocks", "duration_months"): {"expected": "integer", "severity": "REVIEW"},
    ("macro", "external_shocks", "recovery_months"): {"expected": "integer", "severity": "REVIEW"},
    ("market", "financial_institutions", "active_from"): {"expected": "date", "severity": "REVIEW"},
    ("market", "financial_institutions", "active_to"): {"expected": "date", "severity": "FAIL"},
    ("macro", "macro_environment", "year"): {"expected": "integer", "severity": "REVIEW"},
}

FINANCIAL_PRECISION_RULES = {
    ("banking", "account_balances", "opening_balance"): "money",
    ("banking", "account_balances", "total_inflows"): "money",
    ("banking", "account_balances", "total_outflows"): "money",
    ("banking", "account_balances", "closing_balance"): "money",
    ("banking", "loan_monthly_snapshot", "outstanding_balance"): "money",
    ("banking", "loan_monthly_snapshot", "scheduled_payment"): "money",
    ("banking", "loan_monthly_snapshot", "actual_payment"): "money",
    ("banking", "loan_monthly_snapshot", "arrears_amount"): "money",
    ("banking", "loans", "original_amount"): "money",
    ("banking", "transactions", "amount"): "money",
    ("core", "customers", "monthly_income"): "money",
    ("core", "customers", "annual_revenue"): "money",
    ("market", "bank_financials", "revenue"): "money_large",
    ("market", "bank_financials", "operating_costs"): "money_large",
    ("market", "bank_financials", "net_income"): "money_large",
    ("market", "bank_financials", "total_assets"): "money_large",
    ("market", "bank_financials", "total_deposits"): "money_large",
    ("market", "bank_financials", "total_loans"): "money_large",
    ("market", "bank_financials", "equity"): "money_large",
    ("banking", "loan_monthly_snapshot", "current_interest_rate"): "rate",
    ("banking", "loans", "initial_interest_rate"): "rate",
    ("market", "bank_market_weights", "market_weight"): "ratio",
    ("core", "branches", "latitude"): "coordinate",
    ("core", "branches", "longitude"): "coordinate",
}

for table_name in ["bank_monthly_performance", "branch_monthly_performance"]:
    for column_name in [
        "average_deposits", "average_loan_balance", "transaction_volume",
        "interest_income", "interest_expense", "net_interest_income", "fee_income",
        "total_revenue", "personnel_cost", "fixed_cost", "variable_cost",
        "operational_cost", "total_operating_cost", "credit_loss",
        "pre_provision_profit", "net_income",
    ]:
        FINANCIAL_PRECISION_RULES[("performance", table_name, column_name)] = (
            "money" if column_name in {"average_deposits", "average_loan_balance"}
            else "money_large"
        )

for (schema_name, table_name), columns in {
    ("market", "bank_market_weights"): [
        "latent_competitive_state", "long_run_anchor", "persistence", "macro_effect",
        "systemic_shock_effect", "bank_shock_effect", "persistent_strategic_effect",
        "idiosyncratic_innovation",
    ],
    ("market", "bank_world_parameters"): [
        "realized_usd_affinity", "realized_business_affinity",
        "realized_large_transfer_affinity", "foreign_selection_weight",
        "foreign_dirichlet_alpha", "affinity_noise_sd", "market_persistence",
        "market_innovation_sd",
    ],
    ("market", "banks"): [
        "usd_affinity", "business_affinity", "large_transfer_affinity"
    ],
    ("macro", "external_shocks"): [
        "peak_magnitude", "signed_peak_intensity", "persistence", "recovery_shape"
    ],
    ("macro", "macro_environment"): [
        "macro_growth_factor", "credit_cycle_factor", "usd_pressure_factor",
        "financial_stress_factor", "digitalization_factor", "cross_border_factor",
        "systemic_shock",
    ],
}.items():
    for column_name in columns:
        FINANCIAL_PRECISION_RULES[
            (schema_name, table_name, column_name)
        ] = "simulation"


PRECISION_TARGETS = {
    "money": "numeric(18,2)",
    "money_large": "numeric(20,2)",
    "rate": "numeric(12,6)",
    "ratio": "numeric(12,8)",
    "simulation": "double precision",
    "coordinate": "double precision",
}


def create_db_engine():
    password = getpass("PostgreSQL password: ")
    url = f"postgresql+psycopg://{DB_USER}:{password}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    return create_engine(url)


def validate_identifier(identifier):
    if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", identifier):
        raise ValueError(f"Unsafe SQL identifier detected: {identifier}")
    return identifier


def audit_connection(engine):
    with engine.connect() as connection:
        db = connection.execute(text("SELECT current_database();")).scalar_one()
        version = connection.execute(text("SELECT version();")).scalar_one()
    print("=" * 72)
    print("BTYT RELATIONAL MODEL AUDIT")
    print("=" * 72)
    print(f"Database : {db}")
    print(f"Server   : {version}\n")



def audit_schema_layout(engine):
    """Audit the exact final 7-schema / 23-table architecture."""

    query = text("""
        SELECT table_schema AS schema_name, table_name
        FROM information_schema.tables
        WHERE table_schema = ANY(:schemas)
          AND table_type = 'BASE TABLE'
        ORDER BY table_schema, table_name;
    """)

    with engine.connect() as connection:
        rows = connection.execute(
            query,
            {"schemas": BTYT_SCHEMAS},
        ).mappings().all()

    observed = {}
    for row in rows:
        observed.setdefault(row["schema_name"], []).append(row["table_name"])

    results = []
    total_observed = 0

    print("-" * 72)
    print("SCHEMA LAYOUT AUDIT")
    print("-" * 72)

    for schema_name in BTYT_SCHEMAS:
        expected = set(FINAL_SCHEMA_LAYOUT[schema_name])
        actual = set(observed.get(schema_name, []))

        missing = sorted(expected - actual)
        unexpected = sorted(actual - expected)
        decision = "PASS" if not missing and not unexpected else "FAIL"

        total_observed += len(actual)

        results.append({
            "schema_name": schema_name,
            "expected_tables": len(expected),
            "observed_tables": len(actual),
            "missing_tables": missing,
            "unexpected_tables": unexpected,
            "decision": decision,
        })

        print(
            f"\n[{decision}] {schema_name:<12} "
            f"{len(actual)} / {len(expected)} tables"
        )

        if missing:
            print(f"  Missing    : {', '.join(missing)}")

        if unexpected:
            print(f"  Unexpected : {', '.join(unexpected)}")

    overall = (
        "PASS"
        if total_observed == 23
        and all(result["decision"] == "PASS" for result in results)
        else "FAIL"
    )

    print(f"\n[{overall}] Total BTYT tables: {total_observed} / 23")

    return results


def audit_applied_relational_state(engine):
    """Audit the currently applied PK/FK/CHECK/NOT NULL state."""

    constraint_query = text("""
        SELECT con.contype, con.convalidated
        FROM pg_constraint AS con
        JOIN pg_class AS c
          ON c.oid = con.conrelid
        JOIN pg_namespace AS n
          ON n.oid = c.relnamespace
        WHERE n.nspname = ANY(:schemas)
          AND con.contype IN ('p', 'f', 'c');
    """)

    with engine.connect() as connection:
        rows = connection.execute(
            constraint_query,
            {"schemas": BTYT_SCHEMAS},
        ).mappings().all()

    counts = {
        "primary_keys": sum(row["contype"] == "p" for row in rows),
        "foreign_keys": sum(row["contype"] == "f" for row in rows),
        "check_constraints": sum(row["contype"] == "c" for row in rows),
        "unvalidated_foreign_keys": sum(
            row["contype"] == "f" and not row["convalidated"]
            for row in rows
        ),
        "unvalidated_checks": sum(
            row["contype"] == "c" and not row["convalidated"]
            for row in rows
        ),
    }

    print("\n" + "-" * 72)
    print("APPLIED RELATIONAL STATE")
    print("-" * 72)

    for key, expected in EXPECTED_RELATIONAL_COUNTS.items():
        observed = counts[key]
        status = "PASS" if observed == expected else "FAIL"
        label = key.replace("_", " ").title()

        print(
            f"  [{status}] {label:<20}: "
            f"{observed} / {expected}"
        )

    fk_status = (
        "PASS"
        if counts["unvalidated_foreign_keys"] == 0
        else "FAIL"
    )
    check_status = (
        "PASS"
        if counts["unvalidated_checks"] == 0
        else "FAIL"
    )

    print(
        f"  [{fk_status}] Unvalidated FKs       : "
        f"{counts['unvalidated_foreign_keys']}"
    )
    print(
        f"  [{check_status}] Unvalidated CHECKs    : "
        f"{counts['unvalidated_checks']}"
    )

    applied_not_null = 0

    for schema_name, table_name, column_name in AUDITED_NOT_NULL_COLUMNS:
        query = text("""
            SELECT is_nullable
            FROM information_schema.columns
            WHERE table_schema = :schema_name
              AND table_name = :table_name
              AND column_name = :column_name;
        """)

        with engine.connect() as connection:
            is_nullable = connection.execute(
                query,
                {
                    "schema_name": schema_name,
                    "table_name": table_name,
                    "column_name": column_name,
                },
            ).scalar_one_or_none()

        applied_not_null += int(is_nullable == "NO")

    nn_status = (
        "PASS"
        if applied_not_null == len(AUDITED_NOT_NULL_COLUMNS)
        else "FAIL"
    )

    print(
        f"  [{nn_status}] Audited NOT NULL      : "
        f"{applied_not_null} / {len(AUDITED_NOT_NULL_COLUMNS)}"
    )

    return {
        **counts,
        "audited_not_null": applied_not_null,
        "audited_not_null_expected": len(AUDITED_NOT_NULL_COLUMNS),
    }

def get_table_inventory(engine):
    query = text("""
        SELECT schemaname AS schema_name, relname AS table_name, n_live_tup AS estimated_rows
        FROM pg_stat_user_tables
        WHERE schemaname = ANY(:schemas)
        ORDER BY schemaname, relname;
    """)
    with engine.connect() as connection:
        return pd.read_sql(query, connection, params={"schemas": BTYT_SCHEMAS})


def print_table_inventory(inventory):
    print("-" * 72)
    print("TABLE INVENTORY")
    print("-" * 72)
    for schema_name, group in inventory.groupby("schema_name", sort=False):
        print(f"\n[{schema_name.upper()}]")
        for row in group.itertuples(index=False):
            print(f"  {row.table_name:<35}{int(row.estimated_rows or 0):>15,}")
    print(f"\nTables found: {len(inventory)}")


def get_column_inventory(engine):
    query = text("""
        SELECT table_schema AS schema_name, table_name, ordinal_position,
               column_name, data_type, is_nullable
        FROM information_schema.columns
        WHERE table_schema = ANY(:schemas)
        ORDER BY table_schema, table_name, ordinal_position;
    """)
    with engine.connect() as connection:
        return pd.read_sql(query, connection, params={"schemas": BTYT_SCHEMAS})


def print_column_inventory(columns):
    print("\n" + "-" * 72)
    print("COLUMN INVENTORY")
    print("-" * 72)
    for (schema_name, table_name), group in columns.groupby(["schema_name", "table_name"], sort=False):
        print(f"\n{schema_name}.{table_name}")
        for row in group.itertuples(index=False):
            nullable = "NULL" if row.is_nullable == "YES" else "NOT NULL"
            print(f"  {row.column_name:<35}{row.data_type:<28}{nullable}")


def classify_data_types(columns):
    results = []
    for row in columns.itertuples(index=False):
        key = (row.schema_name, row.table_name, row.column_name)
        rule = EXPECTED_TYPES.get(key)
        if rule is None:
            expected_type, status = row.data_type, "PASS"
            reason = "Current type is semantically acceptable."
        else:
            expected_type = rule["expected"]
            if row.data_type == expected_type:
                status = "PASS"
                reason = "Current PostgreSQL type matches the expected semantic type."
            else:
                status = rule["severity"]
                reason = (
                    "Current PostgreSQL type is semantically incorrect and should be changed."
                    if status == "FAIL"
                    else "Current type works, but a more appropriate semantic type should be evaluated."
                )
        results.append({
            "schema_name": row.schema_name, "table_name": row.table_name,
            "column_name": row.column_name, "current_type": row.data_type,
            "expected_type": expected_type, "status": status, "reason": reason,
        })
    return pd.DataFrame(results)


def print_data_type_audit(type_audit):
    print("\n" + "-" * 72)
    print("DATA TYPE AUDIT")
    print("-" * 72)
    issues = type_audit[type_audit["status"].isin(["REVIEW", "FAIL"])]
    for row in issues.itertuples(index=False):
        print(f"\n{row.status:<7} {row.schema_name}.{row.table_name}.{row.column_name}")
        print(f"  Current  : {row.current_type}")
        print(f"  Expected : {row.expected_type}")
        print(f"  Reason   : {row.reason}")
    summary = type_audit["status"].value_counts().reindex(["PASS", "REVIEW", "FAIL"], fill_value=0)
    print("\n" + "-" * 72)
    print("TYPE AUDIT SUMMARY")
    for key in ["PASS", "REVIEW", "FAIL"]:
        print(f"  {key:<7}: {summary[key]}")
    print(f"  TOTAL  : {len(type_audit)}")


def get_basic_value_profile(engine, schema_name, table_name, column_name):
    schema_name, table_name, column_name = map(validate_identifier, [schema_name, table_name, column_name])
    query = text(f'''SELECT COUNT(*) AS total_rows,
        COUNT(*) FILTER (WHERE "{column_name}" IS NULL) AS null_rows,
        COUNT("{column_name}") AS non_null_rows,
        COUNT(DISTINCT "{column_name}") AS distinct_values,
        MIN("{column_name}") AS min_value, MAX("{column_name}") AS max_value
        FROM "{schema_name}"."{table_name}";''')
    with engine.connect() as connection:
        return dict(connection.execute(query).mappings().one())


def get_sample_values(engine, schema_name, table_name, column_name, limit=10):
    schema_name, table_name, column_name = map(validate_identifier, [schema_name, table_name, column_name])
    query = text(f'''SELECT DISTINCT "{column_name}" AS sample_value
        FROM "{schema_name}"."{table_name}"
        WHERE "{column_name}" IS NOT NULL ORDER BY "{column_name}" LIMIT :limit;''')
    with engine.connect() as connection:
        return connection.execute(query, {"limit": limit}).scalars().all()


def audit_integer_compatibility(engine, schema_name, table_name, column_name, current_type):
    schema_name, table_name, column_name = map(validate_identifier, [schema_name, table_name, column_name])
    result = {"invalid_values": 0, "fractional_values": 0, "out_of_range_values": 0}
    if current_type in {"integer", "bigint"}:
        query = text(f'''SELECT COUNT(*) FILTER (WHERE "{column_name}" IS NOT NULL AND
            ("{column_name}" < -2147483648 OR "{column_name}" > 2147483647)) AS n
            FROM "{schema_name}"."{table_name}";''')
        with engine.connect() as connection:
            result["out_of_range_values"] = int(connection.execute(query).scalar_one())
    elif current_type == "double precision":
        query = text(f'''SELECT
            COUNT(*) FILTER (WHERE "{column_name}" IS NOT NULL AND "{column_name}" <> TRUNC("{column_name}")) AS frac,
            COUNT(*) FILTER (WHERE "{column_name}" IS NOT NULL AND
            ("{column_name}" < -2147483648 OR "{column_name}" > 2147483647)) AS oor
            FROM "{schema_name}"."{table_name}";''')
        with engine.connect() as connection:
            row = connection.execute(query).mappings().one()
        result["fractional_values"], result["out_of_range_values"] = int(row["frac"]), int(row["oor"])
    elif current_type == "text":
        query = text(f'''SELECT COUNT(*) FILTER (WHERE "{column_name}" IS NOT NULL AND
            "{column_name}" !~ '^-?[0-9]+$') AS n FROM "{schema_name}"."{table_name}";''')
        with engine.connect() as connection:
            result["invalid_values"] = int(connection.execute(query).scalar_one())
    return result


def audit_date_compatibility(engine, schema_name, table_name, column_name):
    schema_name, table_name, column_name = map(validate_identifier, [schema_name, table_name, column_name])
    query = text(f'''SELECT
        COUNT(*) FILTER (WHERE "{column_name}" IS NOT NULL AND "{column_name}"::text ~ '^[0-9]{{4}}-[0-9]{{2}}$') AS ym,
        COUNT(*) FILTER (WHERE "{column_name}" IS NOT NULL AND "{column_name}"::text ~ '^[0-9]{{4}}-[0-9]{{2}}-[0-9]{{2}}$') AS ymd,
        COUNT(*) FILTER (WHERE "{column_name}" IS NOT NULL AND
            "{column_name}"::text !~ '^[0-9]{{4}}-[0-9]{{2}}$' AND
            "{column_name}"::text !~ '^[0-9]{{4}}-[0-9]{{2}}-[0-9]{{2}}$') AS bad
        FROM "{schema_name}"."{table_name}";''')
    with engine.connect() as connection:
        row = connection.execute(query).mappings().one()
    return {"yyyy_mm_values": int(row["ym"]), "yyyy_mm_dd_values": int(row["ymd"]), "invalid_format_values": int(row["bad"])}


def classify_conversion(expected_type, profile, compatibility):
    if expected_type == "integer":
        return "BLOCKED" if any(compatibility[k] > 0 for k in ["invalid_values", "fractional_values", "out_of_range_values"]) else "SAFE"
    if expected_type == "date":
        if compatibility["invalid_format_values"] > 0:
            return "BLOCKED"
        return "REVIEW" if profile["non_null_rows"] == 0 else "SAFE"
    if expected_type == "text":
        return "SAFE"
    return "REVIEW"


def audit_review_columns(engine, type_audit):
    review_columns = type_audit[type_audit["status"].isin(["REVIEW", "FAIL"])]
    results = []
    print("\n" + "-" * 72)
    print("DATA VALUE AUDIT")
    print("-" * 72)
    for row in review_columns.itertuples(index=False):
        print(f"\nAuditing {row.schema_name}.{row.table_name}.{row.column_name}...")
        profile = get_basic_value_profile(engine, row.schema_name, row.table_name, row.column_name)
        sample = get_sample_values(engine, row.schema_name, row.table_name, row.column_name)
        if row.expected_type == "integer":
            compatibility = audit_integer_compatibility(engine, row.schema_name, row.table_name, row.column_name, row.current_type)
        elif row.expected_type == "date":
            compatibility = audit_date_compatibility(engine, row.schema_name, row.table_name, row.column_name)
        elif row.expected_type == "text":
            compatibility = {"all_null": profile["non_null_rows"] == 0}
        else:
            compatibility = {}
        decision = classify_conversion(row.expected_type, profile, compatibility)
        results.append({**row._asdict(), **profile, "sample_values": sample, "compatibility": compatibility, "decision": decision})
    return results


def print_value_audit(results):
    print("\n" + "=" * 72)
    print("DATA VALUE AUDIT RESULTS")
    print("=" * 72)
    for r in results:
        print(f"\n[{r['status']}] {r['schema_name']}.{r['table_name']}.{r['column_name']}")
        print(f"  Current type   : {r['current_type']}")
        print(f"  Expected type  : {r['expected_type']}")
        print(f"  Total rows     : {r['total_rows']:,}")
        print(f"  NULL rows      : {r['null_rows']:,}")
        print(f"  Non-NULL rows  : {r['non_null_rows']:,}")
        print(f"  Distinct       : {r['distinct_values']:,}")
        print(f"  Min            : {r['min_value']}")
        print(f"  Max            : {r['max_value']}")
        print(f"  Sample         : {r['sample_values']}")
        c = r["compatibility"]
        if r["expected_type"] == "integer":
            print(f"  Invalid integer values : {c['invalid_values']:,}")
            print(f"  Fractional values      : {c['fractional_values']:,}")
            print(f"  Out-of-range values    : {c['out_of_range_values']:,}")
        elif r["expected_type"] == "date":
            print(f"  YYYY-MM values         : {c['yyyy_mm_values']:,}")
            print(f"  YYYY-MM-DD values      : {c['yyyy_mm_dd_values']:,}")
            print(f"  Invalid formats        : {c['invalid_format_values']:,}")
        elif r["expected_type"] == "text":
            print(f"  All values NULL        : {c['all_null']}")
        print(f"  Conversion decision    : {r['decision']}")


def print_value_audit_summary(results):
    summary = pd.Series([r["decision"] for r in results]).value_counts().reindex(["SAFE", "REVIEW", "BLOCKED"], fill_value=0)
    print("\n" + "-" * 72)
    print("VALUE AUDIT SUMMARY")
    print("-" * 72)
    for key in ["SAFE", "REVIEW", "BLOCKED"]:
        print(f"  {key:<7}: {summary[key]}")
    print(f"  TOTAL   : {len(results)}")


def get_decimal_profile(engine, schema_name, table_name, column_name):
    schema_name, table_name, column_name = map(validate_identifier, [schema_name, table_name, column_name])
    query = text(f'''SELECT COUNT(*) AS total_rows,
        COUNT(*) FILTER (WHERE "{column_name}" IS NULL) AS null_rows,
        MIN("{column_name}") AS min_value, MAX("{column_name}") AS max_value,
        COUNT(*) FILTER (WHERE "{column_name}" IS NOT NULL AND
            ABS("{column_name}" - ROUND("{column_name}"::numeric, 2)::double precision) > 1e-9) AS beyond_two_decimals
        FROM "{schema_name}"."{table_name}";''')
    with engine.connect() as connection:
        return dict(connection.execute(query).mappings().one())


def normalize_postgresql_type(
    data_type,
    numeric_precision=None,
    numeric_scale=None,
):
    """Return a comparable PostgreSQL type label."""

    if (
        data_type == "numeric"
        and numeric_precision is not None
        and numeric_scale is not None
    ):
        return (
            f"numeric({int(numeric_precision)},"
            f"{int(numeric_scale)})"
        )

    return data_type


def get_precision_column_inventory(engine):
    """Read type metadata needed for precision validation."""

    query = text("""
        SELECT
            table_schema AS schema_name,
            table_name,
            column_name,
            data_type,
            numeric_precision,
            numeric_scale
        FROM information_schema.columns
        WHERE table_schema = ANY(:schemas);
    """)

    with engine.connect() as connection:
        return pd.read_sql(
            query,
            connection,
            params={"schemas": BTYT_SCHEMAS},
        )


def build_financial_precision_audit(engine, columns=None):
    """Audit every configured precision rule in the final model."""

    results = []

    print("\n" + "-" * 72)
    print("FINANCIAL PRECISION AUDIT")
    print("-" * 72)

    inventory = get_precision_column_inventory(engine)

    lookup = {
        (row.schema_name, row.table_name, row.column_name): row
        for row in inventory.itertuples(index=False)
    }

    for key, category in FINANCIAL_PRECISION_RULES.items():
        schema_name, table_name, column_name = key
        target_type = PRECISION_TARGETS[category]
        row = lookup.get(key)

        if row is None:
            results.append({
                "schema_name": schema_name,
                "table_name": table_name,
                "column_name": column_name,
                "category": category,
                "current_type": "MISSING",
                "target_type": target_type,
                "recommendation": "FAIL",
                "total_rows": None,
                "null_rows": None,
                "min_value": None,
                "max_value": None,
                "beyond_two_decimals": None,
            })
            continue

        current_type = normalize_postgresql_type(
            row.data_type,
            row.numeric_precision,
            row.numeric_scale,
        )

        if category in {"money", "money_large"}:
            print(
                f"\nAuditing monetary precision "
                f"{schema_name}.{table_name}.{column_name}..."
            )

            profile = get_decimal_profile(
                engine,
                schema_name,
                table_name,
                column_name,
            )

            recommendation = (
                "PASS"
                if current_type == target_type
                else "CONVERT"
            )

        else:
            profile = {
                "total_rows": None,
                "null_rows": None,
                "min_value": None,
                "max_value": None,
                "beyond_two_decimals": None,
            }

            recommendation = (
                "PASS"
                if current_type == target_type
                else "REVIEW"
            )

        results.append({
            "schema_name": schema_name,
            "table_name": table_name,
            "column_name": column_name,
            "category": category,
            "current_type": current_type,
            "target_type": target_type,
            "recommendation": recommendation,
            **profile,
        })

    return results

def print_financial_precision_audit(results):
    """Print precision-audit details."""

    print("\n" + "=" * 72)
    print("FINANCIAL PRECISION AUDIT RESULTS")
    print("=" * 72)

    for result in results:
        print(
            f"\n{result['schema_name']}."
            f"{result['table_name']}."
            f"{result['column_name']}"
        )
        print(f"  Category       : {result['category']}")
        print(f"  Current type   : {result['current_type']}")
        print(f"  Target type    : {result['target_type']}")
        print(f"  Decision       : {result['recommendation']}")

        if (
            result["category"] in {"money", "money_large"}
            and result["total_rows"] is not None
        ):
            print(f"  Rows           : {result['total_rows']:,}")
            print(f"  NULL rows      : {result['null_rows']:,}")
            print(f"  Min            : {result['min_value']}")
            print(f"  Max            : {result['max_value']}")
            print(
                f"  > 2 decimals   : "
                f"{result['beyond_two_decimals']:,}"
            )

def print_financial_precision_summary(results):
    """Print the precision-audit summary."""

    frame = pd.DataFrame(results)

    print("\n" + "-" * 72)
    print("FINANCIAL PRECISION SUMMARY")
    print("-" * 72)

    for category, count in frame.groupby("category").size().sort_index().items():
        print(f"  {category:<15}: {count}")

    print()

    for decision in ["PASS", "CONVERT", "REVIEW", "FAIL"]:
        print(
            f"  {decision:<7}: "
            f"{(frame['recommendation'] == decision).sum()}"
        )

    print(f"  TOTAL   : {len(frame)}")



# =====================================================================
# PRIMARY KEY AUDIT
# =====================================================================

PRIMARY_KEY_CANDIDATES = {
    # Core entities
    ("core", "branches"): ["branch_id"],
    ("core", "customers"): ["customer_id"],
    ("core", "accounts"): ["account_id"],
    ("core", "products"): ["product_id"],

    # Banking operations
    ("banking", "cards"): ["card_id"],
    ("banking", "loans"): ["loan_id"],
    ("banking", "transactions"): ["transaction_id"],
    ("banking", "account_balances"): ["account_id", "year_month"],
    ("banking", "loan_monthly_snapshot"): ["loan_id", "year_month"],

    # Marketing
    ("marketing", "campaigns"): ["campaign_id"],
    ("marketing", "campaign_customers"): ["campaign_id", "customer_id"],
    ("marketing", "campaign_exposures"): ["exposure_id"],

    # Market / environment
    ("market", "banks"): ["bank_id"],
    ("market", "bank_financials"): ["bank_id", "year"],
    ("market", "bank_market_weights"): ["bank_id", "year"],
    ("market", "bank_world_parameters"): ["world_seed", "bank_id"],
    ("performance", "bank_monthly_performance"): ["year_month"],
    ("performance", "branch_monthly_performance"): ["branch_id", "year_month"],
    ("market", "financial_institutions"): ["institution_id"],
    ("macro", "macro_environment"): ["year"],
    ("macro", "external_shocks"): ["shock_id"],

    # Reference tables
    ("reference", "campaign_channels"): ["campaign_id", "channel"],
    ("reference", "campaign_geography"): [
        "campaign_id",
        "geography_level",
        "geography_value",
    ],
}


def quote_identifier(identifier):
    """Validate and quote a SQL identifier."""
    identifier = validate_identifier(identifier)
    return f'"{identifier}"'


def audit_primary_key_candidate(engine, schema_name, table_name, key_columns):
    """Audit one proposed primary key without modifying the database."""

    schema_name = validate_identifier(schema_name)
    table_name = validate_identifier(table_name)
    key_columns = [validate_identifier(column) for column in key_columns]

    qualified_table = f'"{schema_name}"."{table_name}"'
    quoted_columns = [quote_identifier(column) for column in key_columns]
    grouped_columns = ", ".join(quoted_columns)
    null_condition = " OR ".join(
        f"{column} IS NULL" for column in quoted_columns
    )

    if len(quoted_columns) == 1:
        distinct_expression = quoted_columns[0]
    else:
        distinct_expression = "(" + grouped_columns + ")"

    profile_query = text(
        f"""
        SELECT
            COUNT(*) AS total_rows,
            COUNT(*) FILTER (WHERE {null_condition}) AS null_key_rows,
            COUNT(DISTINCT {distinct_expression}) AS distinct_keys
        FROM {qualified_table};
        """
    )

    duplicate_query = text(
        f"""
        SELECT
            COUNT(*) AS duplicate_groups,
            COALESCE(SUM(group_size - 1), 0) AS duplicate_excess_rows,
            COALESCE(MAX(group_size), 1) AS largest_duplicate_group
        FROM (
            SELECT
                COUNT(*) AS group_size
            FROM {qualified_table}
            WHERE NOT ({null_condition})
            GROUP BY {grouped_columns}
            HAVING COUNT(*) > 1
        ) AS duplicate_groups;
        """
    )

    with engine.connect() as connection:
        profile = connection.execute(profile_query).mappings().one()
        duplicates = connection.execute(duplicate_query).mappings().one()

    total_rows = int(profile["total_rows"])
    null_key_rows = int(profile["null_key_rows"])
    distinct_keys = int(profile["distinct_keys"])
    duplicate_groups = int(duplicates["duplicate_groups"] or 0)
    duplicate_excess_rows = int(duplicates["duplicate_excess_rows"] or 0)
    largest_duplicate_group = int(duplicates["largest_duplicate_group"] or 1)

    decision = (
        "PASS"
        if null_key_rows == 0
        and duplicate_groups == 0
        and distinct_keys == total_rows
        else "FAIL"
    )

    return {
        "schema_name": schema_name,
        "table_name": table_name,
        "key_columns": key_columns,
        "total_rows": total_rows,
        "null_key_rows": null_key_rows,
        "distinct_keys": distinct_keys,
        "duplicate_groups": duplicate_groups,
        "duplicate_excess_rows": duplicate_excess_rows,
        "largest_duplicate_group": largest_duplicate_group,
        "decision": decision,
    }


def audit_primary_keys(engine):
    """Audit all proposed BTYT primary key candidates."""

    results = []

    print("\n" + "-" * 72)
    print("PRIMARY KEY AUDIT")
    print("-" * 72)

    for (schema_name, table_name), key_columns in PRIMARY_KEY_CANDIDATES.items():
        key_label = ", ".join(key_columns)
        print(
            f"\nAuditing {schema_name}.{table_name} "
            f"PK candidate ({key_label})..."
        )

        results.append(
            audit_primary_key_candidate(
                engine,
                schema_name,
                table_name,
                key_columns,
            )
        )

    return results


def print_primary_key_audit(results):
    """Print detailed primary key audit results."""

    print("\n" + "=" * 72)
    print("PRIMARY KEY AUDIT RESULTS")
    print("=" * 72)

    for result in results:
        key_label = ", ".join(result["key_columns"])

        print(
            f"\n[{result['decision']}] "
            f"{result['schema_name']}.{result['table_name']}"
        )
        print(f"  Candidate key            : ({key_label})")
        print(f"  Total rows               : {result['total_rows']:,}")
        print(f"  NULL key rows            : {result['null_key_rows']:,}")
        print(f"  Distinct keys            : {result['distinct_keys']:,}")
        print(f"  Duplicate key groups     : {result['duplicate_groups']:,}")
        print(
            f"  Duplicate excess rows    : "
            f"{result['duplicate_excess_rows']:,}"
        )
        print(
            f"  Largest duplicate group  : "
            f"{result['largest_duplicate_group']:,}"
        )


def print_primary_key_summary(results):
    """Print the primary key audit summary."""

    frame = pd.DataFrame(results)
    summary = (
        frame["decision"]
        .value_counts()
        .reindex(["PASS", "FAIL"], fill_value=0)
    )

    print("\n" + "-" * 72)
    print("PRIMARY KEY AUDIT SUMMARY")
    print("-" * 72)
    print(f"  PASS  : {summary['PASS']}")
    print(f"  FAIL  : {summary['FAIL']}")
    print(f"  TOTAL : {len(frame)}")


# =====================================================================
# CONSTRAINT CANDIDATE AUDIT
# =====================================================================

NULLABILITY_CANDIDATES = [
    ("core", "customers", "primary_branch_id", "NULL_ALLOWED"),
    ("core", "accounts", "customer_id", "NOT_NULL"),
    ("core", "accounts", "product_id", "NOT_NULL"),
    ("core", "accounts", "branch_id", "NOT_NULL"),
    ("core", "branches", "parent_branch_id", "NULL_ALLOWED"),
    ("banking", "cards", "customer_id", "NOT_NULL"),
    ("banking", "cards", "product_id", "NOT_NULL"),
    ("banking", "cards", "linked_account_id", "REVIEW"),
    ("banking", "loans", "customer_id", "NOT_NULL"),
    ("banking", "loans", "product_id", "NOT_NULL"),
    ("banking", "loans", "branch_id", "NOT_NULL"),
    ("banking", "transactions", "account_id", "NOT_NULL"),
    ("banking", "transactions", "transaction_branch_id", "NULL_ALLOWED"),
    ("banking", "transactions", "counterparty_institution_id", "NULL_ALLOWED"),
    ("marketing", "campaigns", "target_product_id", "NULL_ALLOWED"),
    ("marketing", "campaign_exposures", "campaign_id", "NOT_NULL"),
    ("marketing", "campaign_exposures", "customer_id", "NOT_NULL"),
    ("market", "financial_institutions", "bank_id", "NULL_ALLOWED"),
]

CATEGORY_COLUMNS = [
    ("core", "branches", "branch_type"),
    ("core", "branches", "branch_size"),
    ("core", "branches", "status"),
    ("core", "customers", "customer_type"),
    ("core", "customers", "gender"),
    ("core", "customers", "customer_status"),
    ("core", "customers", "employment_status"),
    ("core", "customers", "company_size"),
    ("core", "accounts", "account_status"),
    ("core", "accounts", "opening_channel"),
    ("core", "products", "product_family"),
    ("core", "products", "target_customer_type"),
    ("banking", "cards", "card_status"),
    ("banking", "cards", "issue_channel"),
    ("banking", "loans", "currency"),
    ("banking", "loans", "rate_type"),
    ("banking", "loans", "loan_status"),
    ("banking", "loan_monthly_snapshot", "delinquency_status"),
    ("banking", "transactions", "transaction_type"),
    ("banking", "transactions", "direction"),
    ("banking", "transactions", "channel"),
    ("banking", "transactions", "counterparty_type"),
    ("banking", "transactions", "transfer_scope"),
    ("banking", "transactions", "transaction_status"),
    ("banking", "transactions", "merchant_category"),
    ("banking", "transactions", "failure_reason"),
    ("marketing", "campaigns", "campaign_type"),
    ("marketing", "campaigns", "target_customer_type"),
    ("marketing", "campaign_customers", "exposure_status"),
    ("marketing", "campaign_customers", "response_status"),
    ("marketing", "campaign_exposures", "channel"),
    ("market", "banks", "bank_scope"),
    ("market", "banks", "bank_type"),
    ("market", "banks", "bank_profile"),
    ("market", "banks", "bank_status"),
    ("market", "financial_institutions", "institution_type"),
    ("macro", "external_shocks", "shock_type"),
    ("macro", "external_shocks", "shock_scale"),
    ("macro", "external_shocks", "direction"),
    ("reference", "campaign_channels", "channel"),
    ("reference", "campaign_geography", "geography_level"),
]

RANGE_CHECKS = [
    ("banking", "transactions", "amount", '"amount" >= 0'),
    ("banking", "loan_monthly_snapshot", "days_past_due", '"days_past_due" >= 0'),
    ("banking", "loan_monthly_snapshot", "outstanding_balance", '"outstanding_balance" >= 0'),
    ("banking", "loan_monthly_snapshot", "scheduled_payment", '"scheduled_payment" >= 0'),
    ("banking", "loan_monthly_snapshot", "actual_payment", '"actual_payment" >= 0'),
    ("banking", "loan_monthly_snapshot", "arrears_amount", '"arrears_amount" >= 0'),
    ("banking", "loans", "original_amount", '"original_amount" > 0'),
    ("banking", "loans", "term_months", '"term_months" > 0'),
    ("core", "customers", "monthly_income", '"monthly_income" >= 0'),
    ("core", "customers", "annual_revenue", '"annual_revenue" >= 0'),
    ("core", "branches", "latitude", '"latitude" BETWEEN -90 AND 90'),
    ("core", "branches", "longitude", '"longitude" BETWEEN -180 AND 180'),
]

TEMPORAL_CHECKS = [
    ("core", "branches", "closing_year >= opening_year",
     '"closing_year" IS NOT NULL AND "opening_year" IS NOT NULL AND "closing_year" < "opening_year"'),
    ("core", "accounts", "closing_year >= opening_year",
     '"closing_year" IS NOT NULL AND "opening_year" IS NOT NULL AND "closing_year" < "opening_year"'),
    ("core", "customers", "closing_year >= registration_year",
     '"closing_year" IS NOT NULL AND "registration_year" IS NOT NULL AND "closing_year" < "registration_year"'),
    ("marketing", "campaigns", "end_date >= start_date",
     '"end_date" IS NOT NULL AND "start_date" IS NOT NULL AND "end_date" < "start_date"'),
    ("market", "financial_institutions", "active_to >= active_from",
     '"active_to" IS NOT NULL AND "active_from" IS NOT NULL AND "active_to" < "active_from"'),
    ("macro", "external_shocks", "start_month <= peak_month",
     '"start_month" IS NOT NULL AND "peak_month" IS NOT NULL AND "peak_month" < "start_month"'),
    ("macro", "external_shocks", "peak_month <= end_month",
     '"peak_month" IS NOT NULL AND "end_month" IS NOT NULL AND "end_month" < "peak_month"'),
    ("macro", "external_shocks", "end_month <= recovery_end_month",
     '"end_month" IS NOT NULL AND "recovery_end_month" IS NOT NULL AND "recovery_end_month" < "end_month"'),
]


def audit_nullability_candidates(engine):
    results = []
    print("\n" + "-" * 72)
    print("NULLABILITY AUDIT")
    print("-" * 72)

    for schema_name, table_name, column_name, expectation in NULLABILITY_CANDIDATES:
        schema_name, table_name, column_name = map(
            validate_identifier,
            [schema_name, table_name, column_name],
        )
        query = text(f'''
            SELECT
                COUNT(*) AS total_rows,
                COUNT(*) FILTER (WHERE "{column_name}" IS NULL) AS null_rows,
                COUNT(*) FILTER (WHERE "{column_name}" IS NOT NULL) AS non_null_rows
            FROM "{schema_name}"."{table_name}";
        ''')
        with engine.connect() as connection:
            row = connection.execute(query).mappings().one()

        null_rows = int(row["null_rows"])
        if expectation == "NULL_ALLOWED":
            decision = "PASS"
        elif expectation == "NOT_NULL":
            decision = "PASS" if null_rows == 0 else "FAIL"
        else:
            decision = "REVIEW"

        results.append({
            "schema_name": schema_name,
            "table_name": table_name,
            "column_name": column_name,
            "expectation": expectation,
            "total_rows": int(row["total_rows"]),
            "null_rows": null_rows,
            "non_null_rows": int(row["non_null_rows"]),
            "decision": decision,
        })
    return results


def print_nullability_audit(results):
    for result in results:
        print(f"\n[{result['decision']}] {result['schema_name']}.{result['table_name']}.{result['column_name']}")
        print(f"  Semantic expectation : {result['expectation']}")
        print(f"  Total rows           : {result['total_rows']:,}")
        print(f"  NULL rows            : {result['null_rows']:,}")
        print(f"  Non-NULL rows        : {result['non_null_rows']:,}")


def audit_category_columns(engine, limit=30):
    results = []
    print("\n" + "-" * 72)
    print("CATEGORY AUDIT")
    print("-" * 72)

    for schema_name, table_name, column_name in CATEGORY_COLUMNS:
        schema_name, table_name, column_name = map(
            validate_identifier,
            [schema_name, table_name, column_name],
        )
        query = text(f'''
            SELECT "{column_name}" AS value, COUNT(*) AS rows
            FROM "{schema_name}"."{table_name}"
            GROUP BY "{column_name}"
            ORDER BY rows DESC, value NULLS LAST
            LIMIT :limit;
        ''')
        with engine.connect() as connection:
            rows = connection.execute(query, {"limit": limit}).mappings().all()

        results.append({
            "schema_name": schema_name,
            "table_name": table_name,
            "column_name": column_name,
            "values": [(row["value"], int(row["rows"])) for row in rows],
        })
    return results


def print_category_audit(results):
    for result in results:
        print(f"\n{result['schema_name']}.{result['table_name']}.{result['column_name']}")
        for value, count in result["values"]:
            print(f"  {repr(value):<35} {count:>12,}")


def audit_range_checks(engine):
    results = []
    print("\n" + "-" * 72)
    print("RANGE / DOMAIN RULE AUDIT")
    print("-" * 72)

    for schema_name, table_name, column_name, rule in RANGE_CHECKS:
        schema_name, table_name, column_name = map(
            validate_identifier,
            [schema_name, table_name, column_name],
        )
        query = text(f'''
            SELECT
                COUNT(*) AS total_rows,
                COUNT(*) FILTER (
                    WHERE "{column_name}" IS NOT NULL
                      AND NOT ({rule})
                ) AS violations,
                MIN("{column_name}") AS min_value,
                MAX("{column_name}") AS max_value
            FROM "{schema_name}"."{table_name}";
        ''')
        with engine.connect() as connection:
            row = connection.execute(query).mappings().one()

        violations = int(row["violations"])
        results.append({
            "schema_name": schema_name,
            "table_name": table_name,
            "column_name": column_name,
            "rule": rule,
            "total_rows": int(row["total_rows"]),
            "violations": violations,
            "min_value": row["min_value"],
            "max_value": row["max_value"],
            "decision": "PASS" if violations == 0 else "FAIL",
        })
    return results


def print_range_audit(results):
    for result in results:
        print(f"\n[{result['decision']}] {result['schema_name']}.{result['table_name']}.{result['column_name']}")
        print(f"  Proposed rule : {result['rule']}")
        print(f"  Min           : {result['min_value']}")
        print(f"  Max           : {result['max_value']}")
        print(f"  Violations    : {result['violations']:,}")


def audit_temporal_checks(engine):
    results = []
    print("\n" + "-" * 72)
    print("TEMPORAL RULE AUDIT")
    print("-" * 72)

    for schema_name, table_name, label, violation_condition in TEMPORAL_CHECKS:
        schema_name, table_name = map(
            validate_identifier,
            [schema_name, table_name],
        )
        query = text(f'''
            SELECT
                COUNT(*) AS total_rows,
                COUNT(*) FILTER (WHERE {violation_condition}) AS violations
            FROM "{schema_name}"."{table_name}";
        ''')
        with engine.connect() as connection:
            row = connection.execute(query).mappings().one()

        violations = int(row["violations"])
        results.append({
            "schema_name": schema_name,
            "table_name": table_name,
            "label": label,
            "total_rows": int(row["total_rows"]),
            "violations": violations,
            "decision": "PASS" if violations == 0 else "FAIL",
        })
    return results


def print_temporal_audit(results):
    for result in results:
        print(f"\n[{result['decision']}] {result['schema_name']}.{result['table_name']}")
        print(f"  Proposed rule : {result['label']}")
        print(f"  Violations    : {result['violations']:,}")


def audit_constraints(engine):
    nullability_results = audit_nullability_candidates(engine)
    print_nullability_audit(nullability_results)

    category_results = audit_category_columns(engine)
    print_category_audit(category_results)

    range_results = audit_range_checks(engine)
    print_range_audit(range_results)

    temporal_results = audit_temporal_checks(engine)
    print_temporal_audit(temporal_results)

    print("\n" + "=" * 72)
    print("CONSTRAINT CANDIDATE AUDIT SUMMARY")
    print("=" * 72)

    print(f"  Nullability FAIL : {sum(r['decision'] == 'FAIL' for r in nullability_results)}")
    print(f"  Range FAIL       : {sum(r['decision'] == 'FAIL' for r in range_results)}")
    print(f"  Temporal FAIL    : {sum(r['decision'] == 'FAIL' for r in temporal_results)}")
    print(f"  Category columns : {len(category_results)}")
    print("\nNo constraints were created or modified.")


# =====================================================================
# BUSINESS RULE AUDIT
# =====================================================================

BUSINESS_RULES = [
    ("core", "customers", "INDIVIDUAL customers have no company attributes",
     """customer_type = 'INDIVIDUAL' AND
        (company_name IS NOT NULL OR business_sector IS NOT NULL OR
         company_size IS NOT NULL OR foundation_year IS NOT NULL OR
         annual_revenue IS NOT NULL)""", "REVIEW"),
    ("core", "customers", "BUSINESS customers have no personal-only attributes",
     """customer_type = 'BUSINESS' AND
        (first_name IS NOT NULL OR last_name IS NOT NULL OR birth_year IS NOT NULL OR
         gender IS NOT NULL OR employment_status IS NOT NULL OR monthly_income IS NOT NULL)""", "REVIEW"),

    ("core", "accounts", "ACTIVE accounts have no closing_year",
     """account_status = 'ACTIVE' AND closing_year IS NOT NULL""", "CANDIDATE"),
    ("core", "accounts", "CLOSED accounts have closing_year",
     """account_status = 'CLOSED' AND closing_year IS NULL""", "CANDIDATE"),

    ("banking", "cards", "ACTIVE cards have no closing_year",
     """card_status = 'ACTIVE' AND closing_year IS NOT NULL""", "CANDIDATE"),
    ("banking", "cards", "CLOSED cards have closing_year",
     """card_status = 'CLOSED' AND closing_year IS NULL""", "CANDIDATE"),

    ("banking", "loans", "ACTIVE loans have no closing_year",
     """loan_status = 'ACTIVE' AND closing_year IS NOT NULL""", "CANDIDATE"),
    ("banking", "loans", "Non-active loans have closing_year",
     """loan_status <> 'ACTIVE' AND closing_year IS NULL""", "REVIEW"),

    ("banking", "transactions", "COMPLETED transactions have no failure_reason",
     """transaction_status = 'COMPLETED' AND failure_reason IS NOT NULL""", "CANDIDATE"),
    ("banking", "transactions", "FAILED transactions have failure_reason",
     """transaction_status = 'FAILED' AND failure_reason IS NULL""", "CANDIDATE"),
    ("banking", "transactions", "BRANCH transactions have transaction_branch_id",
     """channel = 'BRANCH' AND transaction_branch_id IS NULL""", "CANDIDATE"),
    ("banking", "transactions", "Non-BRANCH transactions have no transaction_branch_id",
     """channel <> 'BRANCH' AND transaction_branch_id IS NOT NULL""", "REVIEW"),
    ("banking", "transactions", "TRANSFER transactions have transfer_scope",
     """transaction_type IN ('TRANSFER_IN', 'TRANSFER_OUT') AND transfer_scope IS NULL""", "CANDIDATE"),
    ("banking", "transactions", "Non-TRANSFER transactions have no transfer_scope",
     """transaction_type NOT IN ('TRANSFER_IN', 'TRANSFER_OUT') AND transfer_scope IS NOT NULL""", "CANDIDATE"),

    ("marketing", "campaign_customers", "EXPOSED rows have exposure_date",
     """exposure_status = 'EXPOSED' AND exposure_date IS NULL""", "CANDIDATE"),
    ("marketing", "campaign_customers", "NOT_EXPOSED rows have no exposure_date",
     """exposure_status = 'NOT_EXPOSED' AND exposure_date IS NOT NULL""", "CANDIDATE"),
    ("marketing", "campaign_customers", "NOT_EXPOSED rows have no response_status",
     """exposure_status = 'NOT_EXPOSED' AND response_status IS NOT NULL""", "CANDIDATE"),
    ("marketing", "campaign_customers", "NO_RESPONSE rows have no response_date",
     """response_status = 'NO_RESPONSE' AND response_date IS NOT NULL""", "CANDIDATE"),
    ("marketing", "campaign_customers", "Actual responses have response_date",
     """response_status IN ('POSITIVE', 'NEUTRAL', 'NEGATIVE') AND response_date IS NULL""", "CANDIDATE"),
]

CARD_LINK_AUDIT_SQL = """
SELECT
    p.product_name,
    p.product_family,
    COUNT(*) AS total_cards,
    COUNT(*) FILTER (WHERE c.linked_account_id IS NULL) AS unlinked_cards,
    COUNT(*) FILTER (WHERE c.linked_account_id IS NOT NULL) AS linked_cards
FROM banking.cards AS c
JOIN core.products AS p ON p.product_id = c.product_id
GROUP BY p.product_name, p.product_family
ORDER BY total_cards DESC, p.product_name;
"""

COUNTERPARTY_AUDIT_SQL = """
SELECT
    transaction_type,
    counterparty_type,
    transfer_scope,
    COUNT(*) AS total_rows,
    COUNT(*) FILTER (WHERE counterparty_institution_id IS NULL) AS null_institution_rows,
    COUNT(*) FILTER (WHERE counterparty_institution_id IS NOT NULL) AS institution_rows
FROM banking.transactions
GROUP BY transaction_type, counterparty_type, transfer_scope
ORDER BY total_rows DESC;
"""


def audit_business_rules(engine):
    results = []

    print("\n" + "-" * 72)
    print("BUSINESS RULE AUDIT")
    print("-" * 72)

    for schema_name, table_name, label, violation_condition, policy in BUSINESS_RULES:
        schema_name, table_name = map(validate_identifier, [schema_name, table_name])

        query = text(f"""
            SELECT
                COUNT(*) AS total_rows,
                COUNT(*) FILTER (WHERE {violation_condition}) AS violations
            FROM "{schema_name}"."{table_name}";
        """)

        with engine.connect() as connection:
            row = connection.execute(query).mappings().one()

        violations = int(row["violations"])
        decision = "PASS" if violations == 0 else ("REVIEW" if policy == "REVIEW" else "FAIL")

        results.append({
            "schema_name": schema_name,
            "table_name": table_name,
            "label": label,
            "policy": policy,
            "total_rows": int(row["total_rows"]),
            "violations": violations,
            "decision": decision,
        })

        print(f"\n[{decision}] {schema_name}.{table_name}")
        print(f"  Rule candidate : {label}")
        print(f"  Policy         : {policy}")
        print(f"  Total rows     : {int(row['total_rows']):,}")
        print(f"  Violations     : {violations:,}")

    print("\n" + "-" * 72)
    print("CARD LINKAGE PROFILE")
    print("-" * 72)
    with engine.connect() as connection:
        rows = connection.execute(text(CARD_LINK_AUDIT_SQL)).mappings().all()
    for row in rows:
        print(
            f"\n{row['product_name']} [{row['product_family']}]"
            f"\n  Cards    : {int(row['total_cards']):,}"
            f"\n  Linked   : {int(row['linked_cards']):,}"
            f"\n  Unlinked : {int(row['unlinked_cards']):,}"
        )

    print("\n" + "-" * 72)
    print("COUNTERPARTY / TRANSFER PROFILE")
    print("-" * 72)
    with engine.connect() as connection:
        rows = connection.execute(text(COUNTERPARTY_AUDIT_SQL)).mappings().all()
    for row in rows:
        print(
            f"\n{row['transaction_type']} | {row['counterparty_type']} | {row['transfer_scope']}"
            f"\n  Rows                 : {int(row['total_rows']):,}"
            f"\n  Institution present  : {int(row['institution_rows']):,}"
            f"\n  Institution NULL     : {int(row['null_institution_rows']):,}"
        )

    print("\n" + "=" * 72)
    print("BUSINESS RULE AUDIT SUMMARY")
    print("=" * 72)
    print(f"  PASS   : {sum(r['decision'] == 'PASS' for r in results)}")
    print(f"  REVIEW : {sum(r['decision'] == 'REVIEW' for r in results)}")
    print(f"  FAIL   : {sum(r['decision'] == 'FAIL' for r in results)}")
    print(f"  TOTAL  : {len(results)}")
    print("\nNo constraints were created or modified.")

def parse_arguments():
    """Parse optional audit-phase arguments."""

    parser = argparse.ArgumentParser(
        description="Read-only audit of the BTYT PostgreSQL relational model."
    )

    parser.add_argument(
        "--schema-layout",
        action="store_true",
        help="Audit the exact final 7-schema / 23-table architecture.",
    )
    parser.add_argument(
        "--state",
        action="store_true",
        help="Audit the applied PK/FK/CHECK/NOT NULL state.",
    )
    parser.add_argument(
        "--structure",
        action="store_true",
        help="Run table and column inventory only.",
    )
    parser.add_argument(
        "--types",
        action="store_true",
        help="Run semantic data type audit only.",
    )
    parser.add_argument(
        "--values",
        action="store_true",
        help="Run value compatibility audit for reviewed type changes.",
    )
    parser.add_argument(
        "--precision",
        action="store_true",
        help="Run financial precision audit only.",
    )
    parser.add_argument(
        "--pk",
        action="store_true",
        help="Run primary key candidate audit only.",
    )

    parser.add_argument(
        "--constraints",
        action="store_true",
        help="Audit NOT NULL and CHECK constraint candidates.",
    )

    parser.add_argument(
        "--business-rules",
        action="store_true",
        help="Audit cross-column BTYT business-rule candidates.",
    )

    return parser.parse_args()


def main():
    args = parse_arguments()

    requested_phases = any(
        [
            args.schema_layout,
            args.state,
            args.structure,
            args.types,
            args.values,
            args.precision,
            args.pk,
            args.constraints,
            args.business_rules,
        ]
    )

    run_all = not requested_phases

    engine = create_db_engine()

    try:
        audit_connection(engine)

        column_inventory = None
        data_type_audit = None

        if run_all or args.schema_layout:
            audit_schema_layout(engine)

        if run_all or args.state:
            audit_applied_relational_state(engine)

        if run_all or args.structure:
            table_inventory = get_table_inventory(engine)
            column_inventory = get_column_inventory(engine)
            print_table_inventory(table_inventory)
            print_column_inventory(column_inventory)

        if run_all or args.types:
            if column_inventory is None:
                column_inventory = get_column_inventory(engine)

            data_type_audit = classify_data_types(column_inventory)
            print_data_type_audit(data_type_audit)

        if run_all or args.values:
            if column_inventory is None:
                column_inventory = get_column_inventory(engine)

            if data_type_audit is None:
                data_type_audit = classify_data_types(column_inventory)

            value_audit_results = audit_review_columns(
                engine,
                data_type_audit,
            )
            print_value_audit(value_audit_results)
            print_value_audit_summary(value_audit_results)

        if run_all or args.precision:
            if column_inventory is None:
                column_inventory = get_column_inventory(engine)

            precision_results = build_financial_precision_audit(
                engine,
                column_inventory,
            )
            print_financial_precision_audit(precision_results)
            print_financial_precision_summary(precision_results)

        if run_all or args.pk:
            primary_key_results = audit_primary_keys(engine)
            print_primary_key_audit(primary_key_results)
            print_primary_key_summary(primary_key_results)

        if run_all or args.constraints:
            audit_constraints(engine)

        if run_all or args.business_rules:
            audit_business_rules(engine)

        print("\n" + "=" * 72)
        print("RELATIONAL AUDIT PHASE COMPLETE")
        print("=" * 72)
        print("No database objects or data were modified.")

    finally:
        engine.dispose()


if __name__ == "__main__":
    main()